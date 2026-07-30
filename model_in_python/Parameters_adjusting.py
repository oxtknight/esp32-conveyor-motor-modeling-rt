import matplotlib.pyplot as plt
import numpy as np
import lmfit
from scipy.integrate import solve_ivp
import mysql.connector
import os


DB_CONFIG = {
    "host": "localhost",
    "user": "twinuser",
    "password": "password123",
    "database": "virtualtwin",
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
        t_eval=time_data
    )
    print("success:", solution.success)
    print("message:", solution.message)
    print("t:", solution.t)
    print("y shape:", solution.y.shape)

    y_model = solution.y[0]

    return y_model - ydata
params = lmfit.Parameters()

params.add('a', value=1, min=-500, max=500)
params.add('b', value=1, min=-500, max=500)
params.add('c', value=1, min=-500, max=500)
params.add('d', value=1, min=-500, max=500)
params.add('e', value=1, min=-500, max=500)
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
solution = solve_ivp(
    lambda t, y: differential_equation(t, y, result.params),
    [time_data[0], time_data[-1]],
    [ydata[0]],
    t_eval=time_data
)

print(solution.success)
print(solution.message)
print(solution.t)
print(solution.y.shape)
print(time_data)
fitted = solution.y[0]

import requests

for i in range(len(time_data)):

    payload = {
        "time": float(time_data[i]),
        "speed": float(fitted[i]),
        "parameters": {
            "a": float(result.params["a"].value),
            "b": float(result.params["b"].value),
            "c": float(result.params["c"].value),
            "d": float(result.params["d"].value),
            "e": float(result.params["e"].value),
            "f": float(result.params["f"].value)
        }
    }
#connect the flask server here 
    requests.post(
        "http://127.0.0.1:5000/motor_update",
        json=payload
    )

db = get_db()
cursor = db.cursor()

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

cursor.close()
db.close()

plt.plot(time_data, ydata, 'o', label="Measured speed")
plt.plot(time_data, fitted, '-', label="Model speed")

plt.xlabel("Time")
plt.ylabel("Speed")

plt.legend()
plt.grid()
plt.show()
