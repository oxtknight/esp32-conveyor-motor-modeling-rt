import sys
import json
import numpy as np
import joblib
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error

from dataset_loader import load_trial

WINDOW_SIZE = 10          
HIDDEN_LAYERS = (32, 32)  
MAX_ITER = 500
TRAIN_SPLIT = 0.8          

def build_windows(voltage, current, rpm, window_size):
    n_samples = len(voltage) - window_size
    X = np.zeros((n_samples, window_size), dtype=np.float32)
    y = np.zeros((n_samples, 2), dtype=np.float32)
    for i in range(n_samples):
        X[i] = voltage[i: i + window_size]
        target_idx = i + window_size - 1
        y[i] = [current[target_idx], rpm[target_idx]]
    return X, y

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 train_model_a.py path/to/trial.tsv")
        sys.exit(1)

    filepath = sys.argv[1]
    df = load_trial(filepath)

    voltage = df["voltage"].to_numpy(dtype=np.float32)
    current = df["current"].to_numpy(dtype=np.float32)
    rpm = df["rpm"].to_numpy(dtype=np.float32)

    X, y = build_windows(voltage, current, rpm, WINDOW_SIZE)

    split_idx = int(len(X) * TRAIN_SPLIT)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    x_scaler = StandardScaler().fit(X_train)
    y_scaler = StandardScaler().fit(y_train)

    X_train_s = x_scaler.transform(X_train)
    X_test_s = x_scaler.transform(X_test)
    y_train_s = y_scaler.transform(y_train)
    y_test_s = y_scaler.transform(y_test)

    model = MLPRegressor(
        hidden_layer_sizes=HIDDEN_LAYERS,
        max_iter=MAX_ITER,
        early_stopping=True,
        random_state=0,
    )
    model.fit(X_train_s, y_train_s)

    train_pred_s = model.predict(X_train_s)
    test_pred_s = model.predict(X_test_s)

    train_mse = mean_squared_error(y_train_s, train_pred_s)
    test_mse = mean_squared_error(y_test_s, test_pred_s)

    print(f"train MSE (normalized): {train_mse:.5f}")
    print(f"test  MSE (normalized): {test_mse:.5f}")
    print(f"iterations run: {model.n_iter_}")
    
    test_pred_real = y_scaler.inverse_transform(test_pred_s)
    current_mae = np.mean(np.abs(test_pred_real[:, 0] - y_test[:, 0]))
    rpm_mae = np.mean(np.abs(test_pred_real[:, 1] - y_test[:, 1]))
    print(f"test current MAE: {current_mae:.4f} A")
    print(f"test rpm MAE:     {rpm_mae:.4f} RPM")

    joblib.dump(model, "model_a.joblib")
    joblib.dump(x_scaler, "model_a_x_scaler.joblib")
    joblib.dump(y_scaler, "model_a_y_scaler.joblib")
    with open("model_a_config.json", "w") as f:
        json.dump({"window_size": WINDOW_SIZE}, f, indent=2)

    print("\nSaved model_a.joblib, model_a_x_scaler.joblib, model_a_y_scaler.joblib, model_a_config.json")
    print("REMINDER: trained on the PUBLIC reference dataset, not our own")
    print("JGB37-520 hardware -- this is a methodology demonstration, not a")
    print("validated twin of our own motor. State this clearly in the report.")

if __name__ == "__main__":
    main()
