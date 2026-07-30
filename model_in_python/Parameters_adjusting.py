import matplotlib.pyplot as plt
import numpy as np
import lmfit
from scipy.integrate import solve_ivp
import mysql.connector
import os


DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": os.environ.get("DB_PASSWORD"),
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
        - c * V
        + d * y[0]**2
        - e * y[0] * V
        + f * V**2
    )

    return [dydt]


def resid(params, time_data, ydata):

    solution = solve_ivp(
        lambda t, y: differential_equation(t, y, params),
        [time_data[0], time_data[-1]],
        [ydata[0]],
        t_eval=time_data
    )

    y_model = solution.y[0]

    return y_model - ydata

params = lmfit.Parameters()

params.add('a', 1)
params.add('b', 1)
params.add('c', 1)
params.add('d', 1)
params.add('e', 1)
params.add('f', 1)

result = lmfit.minimize(
    resid,
    params,
    args=(time_data, ydata),
    method='differential_evolution'
)


print("\n# Fit results:")
lmfit.report_fit(result)


solution = solve_ivp(
    lambda t, y: differential_equation(t, y, result.params),
    [time_data[0], time_data[-1]],
    [ydata[0]],
    t_eval=time_data
)

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
        "http://your_flask_ip:5000/motor_update",
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
