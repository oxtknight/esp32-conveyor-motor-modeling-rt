import os
import json
import numpy as np
import mysql.connector

DB_CONFIG = {
    "host": "localhost",
    "user": "twinuser",
    "password": "password123",
    "database": "virtualtwin",
}

COEFF_OUTPUT_FILE = "wm_equation_coeffs.json"
MAX_GAP_S = 0.05  # gaps bigger than this are treated as separate experiment
                   # boundaries -- never compute a derivative across one


def fetch_training_data():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT Vr, Wr, time_r FROM MotorLogs WHERE Vr IS NOT NULL AND Wr IS NOT NULL ORDER BY time_r ASC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if len(rows) < 10:
        raise RuntimeError(f"Only {len(rows)} rows found in MotorLogs -- not enough to fit.")

    Vr = np.array([r[0] for r in rows], dtype=float)
    Wr = np.array([r[1] for r in rows], dtype=float)
    time_s = np.array([r[2] for r in rows], dtype=float) / 1000.0  # ms -> s
    return Vr, Wr, time_s


def build_derivative_dataset(Vr, Wr, time_s):
    dt = np.diff(time_s)
    valid = (dt > 0) & (dt < MAX_GAP_S)  # drop boundaries/gaps between separate recordings

    dWr_dt = np.diff(Wr)[valid] / dt[valid]
    Wr_mid = Wr[:-1][valid]
    Vr_mid = Vr[:-1][valid]

    print(f"Built {len(dWr_dt)} usable derivative samples out of {len(dt)} "
          f"consecutive pairs ({(~valid).sum()} boundaries/gaps skipped)")

    return Wr_mid, Vr_mid, dWr_dt


def fit_differential_equation(Wr, Vr, dWr_dt):
    features = np.column_stack([
        np.ones_like(Wr),
        Wr,
        Vr,
        Wr**2,
        Wr * Vr,
        Vr**2,
    ])

    coeffs, residuals, rank, sv = np.linalg.lstsq(features, dWr_dt, rcond=None)

    predicted = features @ coeffs
    ss_res = np.sum((dWr_dt - predicted)**2)
    ss_tot = np.sum((dWr_dt - dWr_dt.mean())**2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    return coeffs, r2


def main():
    print("Fetching (Vr, Wr, time) training data from MotorLogs...")
    Vr, Wr, time_s = fetch_training_data()
    print(f"Loaded {len(Vr)} rows")

    Wr_mid, Vr_mid, dWr_dt = build_derivative_dataset(Vr, Wr, time_s)
    coeffs, r2 = fit_differential_equation(Wr_mid, Vr_mid, dWr_dt)

    print("\nDiscovered equation:")
    print(f"  d(speed)/dt = {coeffs[0]:.6e}")
    print(f"                + {coeffs[1]:.6e} * speed")
    print(f"                + {coeffs[2]:.6e} * voltage")
    print(f"                + {coeffs[3]:.6e} * speed^2")
    print(f"                + {coeffs[4]:.6e} * speed*voltage")
    print(f"                + {coeffs[5]:.6e} * voltage^2")
    print(f"\nR^2 on training data: {r2:.4f}")

    coeff_dict = {
        "c0": float(coeffs[0]), "c1": float(coeffs[1]), "c2": float(coeffs[2]),
        "c3": float(coeffs[3]), "c4": float(coeffs[4]), "c5": float(coeffs[5]),
    }
    with open(COEFF_OUTPUT_FILE, "w") as f:
        json.dump(coeff_dict, f, indent=2)
    print(f"\nSaved coefficients to {COEFF_OUTPUT_FILE}")
    print("flask_server_v2.py reads this file and solves for steady-state Wm(Vr).")


if __name__ == "__main__":
    main()
