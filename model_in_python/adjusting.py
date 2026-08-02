import numpy as np
import matplotlib.pyplot as plt
import mysql.connector
import json
from scipy.integrate import solve_ivp

DB_CONFIG = {
    "host": "localhost",
    "user": "twinuser",
    "password": "password123",
    "database": "virtualtwin",
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

# ====== 1. Load and preprocess data ======
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

if not rows:
    print("No data found in MotorLogs. Exiting.")
    exit()

data = np.array(rows, dtype=float)
row_ids = data[:, 0].astype(int)
time_data = data[:, 1] / 1000.0          # ms → seconds
voltage_data = data[:, 2]
ydata = data[:, 3]

# Deduplicate and sort
unique_times, idx = np.unique(time_data, return_index=True)
time_data = time_data[idx]
voltage_data = voltage_data[idx]
ydata = ydata[idx]
row_ids = row_ids[idx]

sort_idx = np.argsort(time_data)
time_data = time_data[sort_idx]
voltage_data = voltage_data[sort_idx]
ydata = ydata[sort_idx]
row_ids = row_ids[sort_idx]

print(f"Total points: {len(time_data)}")
print(f"Time range: {time_data[0]:.2f} to {time_data[-1]:.2f} s")

if np.std(voltage_data) < 1e-6 and np.std(ydata) < 1e-6:
    print("Data is constant – cannot fit. Exiting.")
    exit()

# ====== 2. Derivative and features ======
dydt = np.gradient(ydata, time_data)
W = ydata
V = voltage_data

features = np.column_stack([
    np.ones_like(W),   # a
    W,                 # b
    V,                 # c
    W * V,             # d
    W**2,              # e
    V**3               # f
])

mask = np.isfinite(dydt) & np.isfinite(features).all(axis=1)
if not np.all(mask):
    print(f"Removing {np.sum(~mask)} invalid rows.")
    features = features[mask]
    dydt = dydt[mask]
    time_data = time_data[mask]
    ydata = ydata[mask]
    voltage_data = voltage_data[mask]
    row_ids = row_ids[mask]

# ====== 3. Linear least squares ======
coeffs, residuals, rank, s = np.linalg.lstsq(features, dydt, rcond=None)
a, b, c, d, e, f_coef = coeffs   # rename f to avoid conflict

print("\nFitted coefficients:")
print(f"a = {a:.6f}")
print(f"b = {b:.6f}")
print(f"c = {c:.6f}")
print(f"d = {d:.6f}")
print(f"e = {e:.6f}")
print(f"f = {f_coef:.6f}")        # use f_coef here
print(f"Residual sum of squares: {residuals[0]:.6f}")

# ====== 4. Save coefficients ======
coeff_dict = {
    "a": float(a),
    "b": float(b),
    "c": float(c),
    "d": float(d),
    "e": float(e),
    "f": float(f_coef),
}
with open("wm_equation_coeffs.json", "w") as json_file:
    json.dump(coeff_dict, json_file, indent=2)
print("Saved coefficients to wm_equation_coeffs.json")

# ====== 5. Optional: integrate ODE and update DB ======
def ode_func(t, y, params):
    a_, b_, c_, d_, e_, f_ = params['a'], params['b'], params['c'], params['d'], params['e'], params['f']
    V = np.interp(t, time_data, voltage_data)
    dydt = a_ + b_*y[0] + c_*V + d_*y[0]*V + e_*y[0]**2 + f_*V**3
    return [dydt]

params = {'a': a, 'b': b, 'c': c, 'd': d, 'e': e, 'f': f_coef}

solution = solve_ivp(
    lambda t, y: ode_func(t, y, params),
    [time_data[0], time_data[-1]],
    [ydata[0]],
    t_eval=time_data,
    method='LSODA'
)

if solution.success and len(solution.y[0]) == len(time_data):
    fitted = solution.y[0]
    db = get_db()
    cursor = db.cursor()
    for i in range(len(row_ids)):
        cursor.execute("""
            UPDATE MotorLogs
            SET Wm=%s, time_m=%s
            WHERE id=%s
        """, (float(fitted[i]), float(time_data[i] * 1000), int(row_ids[i])))
    db.commit()
    cursor.close()
    db.close()
    print("Database updated with integrated model speeds.")

    # Plot
    plt.figure(figsize=(10,5))
    plt.plot(time_data, ydata, 'o', label="Measured speed", markersize=3)
    plt.plot(time_data, fitted, '-', label="Model speed (integrated)", linewidth=2)
    plt.xlabel("Time (s)")
    plt.ylabel("Speed")
    plt.legend()
    plt.grid(True)
    plt.title("Fitted Model vs Measured Data")
    plt.show()
else:
    print("Integration failed – database NOT updated.")
    print("Solver message:", solution.message)
