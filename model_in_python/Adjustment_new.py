import os
import numpy as np
import matplotlib.pyplot as plt
import lmfit
import mysql.connector
import requests

from scipy.integrate import solve_ivp

# -----------------------------
# Database configuration
# -----------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "twinuser",
    "password": "password123",
    "database": "virtualtwin",
}

if DB_CONFIG["password"] is None:
    raise RuntimeError("Environment variable DB_PASSWORD is not set.")


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


# -----------------------------
# Read experimental data
# -----------------------------
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

if len(rows) == 0:
    raise RuntimeError("No data found in MotorLogs.")

data = np.array(rows, dtype=float)

row_ids = data[:, 0].astype(int)
time_data = data[:, 1]
voltage_data = data[:, 2]
ydata = data[:, 3]


# -----------------------------
# Model
# -----------------------------
def differential_equation(t, y, params):
    a = params["a"].value
    b = params["b"].value
    c = params["c"].value
    d = params["d"].value
    e = params["e"].value
    f = params["f"].value

    V = np.interp(t, time_data, voltage_data)


dydt = (
    a
    + b * y[0]
    + c * V
    + d * y[0] * V
    + e * V**2
    + f * V**3
) 
  
return [dydt]
# -----------------------------
# Residual function
# -----------------------------
def resid(params, time_data, ydata):

    solution = solve_ivp(
        lambda t, y: differential_equation(t, y, params),
        (time_data[0], time_data[-1]),
        [ydata[0]],
        t_eval=time_data,
        method="RK45",
    )

    if not solution.success:
        return np.ones_like(ydata) * 1e9

    if solution.y.shape[1] != len(ydata):
        return np.ones_like(ydata) * 1e9

    return solution.y[0] - ydata


# -----------------------------
# Parameters
# Differential evolution REQUIRES bounds
# -----------------------------
params = lmfit.Parameters()

params.add("a", value=1.0, min=-1000, max=1000)
params.add("b", value=1.0, min=-1000, max=1000)
params.add("c", value=1.0, min=-1000, max=1000)
params.add("d", value=1.0, min=-1000, max=1000)
params.add("e", value=1.0, min=-1000, max=1000)
params.add("f", value=1.0, min=-1000, max=1000)


# -----------------------------
# Fit
# -----------------------------
result = lmfit.minimize(
    resid,
    params,
    args=(time_data, ydata),
    method="differential_evolution",
)

print("\nFit results")
lmfit.report_fit(result)


# -----------------------------
# Simulate with fitted parameters
# -----------------------------
solution = solve_ivp(
    lambda t, y: differential_equation(t, y, result.params),
    (time_data[0], time_data[-1]),
    [ydata[0]],
    t_eval=time_data,
)

if not solution.success:
    raise RuntimeError(solution.message)

fitted = solution.y[0]


# -----------------------------
# Send to Flask server
# -----------------------------
payload = {
    "parameters": {
        name: float(result.params[name].value)
        for name in result.params
    },
    "results": [
        {
            "time": float(t),
            "speed": float(w)
        }
        for t, w in zip(time_data, fitted)
    ]
}

try:
    response = requests.post(
        "http://127.0.0.1:5000/motor_update",
        json=payload,
        timeout=5,
    )
    response.raise_for_status()
    print("Data sent successfully.")
except requests.exceptions.RequestException as e:
    print("Error sending data:", e)


# -----------------------------
# Update database
# -----------------------------
db = get_db()
cursor = db.cursor()

update_rows = [
    (
        float(speed),
        float(time),
        int(row_id),
    )
    for speed, time, row_id in zip(fitted, time_data, row_ids)
]

cursor.executemany(
    """
    UPDATE MotorLogs
    SET
        Wm = %s,
        time_m = %s
    WHERE id = %s
    """,
    update_rows,
)

db.commit()

cursor.close()
db.close()


# -----------------------------
# Plot
# -----------------------------
plt.figure(figsize=(8, 5))
plt.plot(time_data, ydata, "o", label="Measured speed")
plt.plot(time_data, fitted, "-", linewidth=2, label="Model speed")

plt.xlabel("Time")
plt.ylabel("Speed")
plt.title("Measured vs Model Speed")
plt.grid(True)
plt.legend()

plt.show()
