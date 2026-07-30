import sys
import numpy as np
import pysindy as ps
 
from dataset_loader import load_trial, list_sheets
 
POLY_DEGREE = 2
STLSQ_THRESHOLD = 0.01
 
 
def fit_pysindy(filepath, sheet_name=0, poly_degree=POLY_DEGREE, threshold=STLSQ_THRESHOLD):
    df = load_trial(filepath, sheet_name=sheet_name)
 
    X_raw = df[["current", "rpm"]].to_numpy()
    U_raw = df[["voltage"]].to_numpy()
    dt = float(df["dt_s"].median())
 
    X_mean, X_std = X_raw.mean(axis=0), X_raw.std(axis=0)
    U_mean, U_std = U_raw.mean(axis=0), U_raw.std(axis=0)
    X_std[X_std < 1e-8] = 1.0
    U_std[U_std < 1e-8] = 1.0
 
    X = (X_raw - X_mean) / X_std
    U = (U_raw - U_mean) / U_std
 
    feature_library = ps.PolynomialLibrary(degree=poly_degree)
    optimizer = ps.STLSQ(threshold=threshold)
 
    model = ps.SINDy(
        feature_library=feature_library,
        optimizer=optimizer,
    )
    model.fit(X, u=U, t=dt, feature_names=["current_norm", "rpm_norm", "voltage_norm"])
 
    scaling = {"X_mean": X_mean, "X_std": X_std, "U_mean": U_mean, "U_std": U_std}
    return model, df, scaling
 
 
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 pysindy_fit.py path/to/dataset.xlsx [SheetName]")
        print("\nAvailable sheets in that file:")
        if len(sys.argv) == 2:
            print(list_sheets(sys.argv[1]))
        sys.exit(1)
 
    filepath = sys.argv[1]
    sheet_name = sys.argv[2] if len(sys.argv) > 2 else 0
 
    print(f"Loading {filepath} (sheet: {sheet_name}) ...")
    model, df, scaling = fit_pysindy(filepath, sheet_name=sheet_name)
 
    print(f"\n{len(df)} samples loaded, dt = {df['dt_s'].median():.5f}s\n")
    print("Discovered equations (in NORMALIZED units -- see scaling below):")
    model.print()
 
    X_raw = df[["current", "rpm"]].to_numpy()
    U_raw = df[["voltage"]].to_numpy()
    dt = float(df["dt_s"].median())
    X = (X_raw - scaling["X_mean"]) / scaling["X_std"]
    U = (U_raw - scaling["U_mean"]) / scaling["U_std"]
 
    print("\nModel score (R^2 on training data, closer to 1.0 is better fit):")
    print(model.score(X, u=U, t=dt))
 
    print("\nScaling used (needed to interpret coefficients in real units):")
    print(f"  current: mean={scaling['X_mean'][0]:.5f}, std={scaling['X_std'][0]:.5f}")
    print(f"  rpm:     mean={scaling['X_mean'][1]:.5f}, std={scaling['X_std'][1]:.5f}")
    print(f"  voltage: mean={scaling['U_mean'][0]:.5f}, std={scaling['U_std'][0]:.5f}")
 
    print("\nREMINDER: trained on the PUBLIC reference dataset, not our own")
    print("JGB37-520 hardware -- methodology demonstration, not a validated")
    print("model of our own motor.")
 
 
if __name__ == "__main__":
    main()

