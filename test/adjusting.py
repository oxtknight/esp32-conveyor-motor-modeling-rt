import matplotlib.pyplot as plt
import numpy as np
import lmfit
from scipy.integrate import solve_ivp
import mysql.connector
import os


DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "twinuser"),
    "password": os.environ.get("DB_PASSWORD", "password123"),
    "database": os.environ.get("DB_NAME", "virtualtwin"),
}


def get_db():
    return mysql.connector.connect(**DB_CONFIG)

db = get_db()
cursor = db.cursor()

cursor.execute("""
SELECT id, time_r, Vr, Wr
FROM MotorLogs
WHERE Wr IS NOT NULL
ORDER BY time_r
""")

rows = cursor.fetchall()

cursor.close()
db.close()

if len(rows) < 2:
    # Nothing (or a single point) to fit against yet. This happens the
    # first time the pipeline runs, before the ESP32 has posted enough
    # /telemetry readings with a matching Wr. Bail out cleanly instead of
    # crashing on data[:, 0] below, and leave any existing
    # wm_equation_coeffs.json / live server coefficients untouched.
    print(
        f"Only {len(rows)} MotorLogs row(s) with Wr set - need at least 2 "
        "to fit the ODE. Post more /telemetry readings and try again later."
    )
    raise SystemExit(0)

data = np.array(rows, dtype=float)

row_ids = data[:, 0].astype(int)
time_data = data[:, 1]
voltage_data = data[:, 2]
ydata = data[:, 3]


def differential_equation(t, y, params):

    a = params['a']
    b = params['b']
    c = params['c']
    d = params['d']
    e = params['e']
    f = params['f']

    # Voltage at current time
    V = np.interp(t, time_data, voltage_data)

    dydt = (
        a
        + b * y[0]
        + c * V
        + d * y[0]*V
        + e * y[0]**2
        + f * V**3
    )

    return [dydt]


def resid(params, time_data, ydata):

    solution = solve_ivp(
        lambda t, y: differential_equation(t, y, params),
        [time_data[0], time_data[-1]],
        [ydata[0]],
        t_eval=time_data,
        method='LSODA',  # handles the stiff/blow-up behavior this model can
                          # hit for bad parameter guesses far better than the
                          # default RK45
    )

    if solution.success and solution.y.shape[1] == len(ydata):
        y_model = solution.y[0]
        return y_model - ydata

    # Integration blew up or bailed out early for this parameter guess.
    # Use whatever partial trajectory we did get (interpolated/held flat
    # for the rest) so the residual still varies with the parameters —
    # a constant fallback here gives leastsq a flat gradient and it stops
    # instantly, reporting "converged" at the initial guess.
    if solution.t.size >= 2:
        y_partial = np.interp(time_data, solution.t, solution.y[0])
    else:
        y_partial = np.full_like(ydata, ydata[0])

    residual = y_partial - ydata
    # Extra penalty scaled by how much of the series never got integrated,
    # so guesses that blow up earlier are scored worse than ones that
    # survive further before failing.
    frac_missing = 1.0 - (solution.t.size / len(ydata))
    penalty = 1e3 * frac_missing
    return residual + penalty * np.sign(residual + 1e-12)

params = lmfit.Parameters()

# Starting all six coefficients at +1 makes the e*Wm^2 term a runaway
# positive-feedback loop (speed accelerates itself), which is why the
# solver blew up after a single step. b and e act as the damping/self
# terms in this equation, so they need to start negative for the ODE to
# even be integrable near the initial guess.
params.add('a', value=1, min=-500, max=500)
params.add('b', value=-1, min=-500, max=500)
params.add('c', value=1, min=-500, max=500)
params.add('d', value=1, min=-500, max=500)
params.add('e', value=-1, min=-500, max=500)
params.add('f', value=1, min=-500, max=500)
result = lmfit.minimize(
    resid,
    params,
    args=(time_data, ydata),
    #method='differential_evolution',
    method = 'leastsq',
    #adding to make it stop
    max_nfev=200
)


print("\n# Fit results:")
lmfit.report_fit(result)

# Verify the final parameters actually integrate cleanly across the whole
# time range before trusting them for anything downstream.
solution = solve_ivp(
    lambda t, y: differential_equation(t, y, result.params),
    [time_data[0], time_data[-1]],
    [ydata[0]],
    t_eval=time_data,
    method='LSODA',
)

print(solution.success)
print(solution.message)
print(solution.t)
print(solution.y.shape)
print(time_data)

if not solution.success or solution.y.shape[1] != len(time_data):
    print(
        "\nFit did not converge to a stable/integrable set of coefficients "
        "(the model still blows up over the full time range with the final "
        "parameters). Refusing to write wm_equation_coeffs.json, push to the "
        "live server, or write into MotorLogs, since they'd be meaningless.\n"
        "Try: more data, tighter parameter bounds, or a better initial guess."
    )
    raise SystemExit(1)

fitted = solution.y[0]

#i added ability to save in json file for server to use
import json

coeff_dict = {
    "a": float(result.params["a"].value),
    "b": float(result.params["b"].value),
    "c": float(result.params["c"].value),
    "d": float(result.params["d"].value),
    "e": float(result.params["e"].value),
    "f": float(result.params["f"].value),
}
with open("wm_equation_coeffs.json", "w") as f:
    json.dump(coeff_dict, f, indent=2)
print("saved coefficients to wm_equation_coeffs.json for the live server to use.")

import requests

# The server also picks up wm_equation_coeffs.json on its own (it re-checks
# the file at most once a minute), but posting here pushes the new
# coefficients live immediately instead of waiting on that cache.
try:
    resp = requests.post(
        "http://127.0.0.1:5000/motor_update",
        json={"parameters": coeff_dict},
        timeout=5,
    )
    resp.raise_for_status()
    print("Pushed new coefficients to live server:", resp.json())
except requests.RequestException as e:
    print(f"Could not reach Flask server to push live update ({e}); "
          f"it will still pick up wm_equation_coeffs.json within {60}s.")

db = get_db()
try:
    cursor = db.cursor()
    try:
        for i in range(len(row_ids)):
            cursor.execute("""
            UPDATE MotorLogs
            SET Wm=%s,
                time_m=%s
            WHERE id=%s
            """,
            (
                float(fitted[i]),
                float(time_data[i]),
                int(row_ids[i])
            ))
        db.commit()
    finally:
        cursor.close()
finally:
    db.close()

plt.plot(time_data, ydata, 'o', label="Measured speed")
plt.plot(time_data, fitted, '-', label="Model speed")

plt.xlabel("Time")
plt.ylabel("Speed")

plt.legend()
plt.grid()
plt.show()
