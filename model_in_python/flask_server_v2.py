import os
import time
import json
import threading
from collections import deque
from flask import Flask, request, jsonify, render_template
import mysql.connector

app = Flask(__name__)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": os.environ.get("DB_PASSWORD"),
    "database": "virtualtwin",
}

COEFF_FILE = "wm_equation_coeffs.json"

lock = threading.Lock()
history = deque(maxlen=500)

_coeffs_cache = None
_coeffs_last_loaded = 0
COEFF_RELOAD_INTERVAL_S = 60  # re-check the coefficients file at most once a minute,
                               # not on every single request


def get_db():
    return mysql.connector.connect(**DB_CONFIG)


def load_coeffs():
    global _coeffs_cache, _coeffs_last_loaded
    now = time.time()
    if _coeffs_cache is not None and (now - _coeffs_last_loaded) < COEFF_RELOAD_INTERVAL_S:
        return _coeffs_cache

    if not os.path.exists(COEFF_FILE):
        _coeffs_cache = None
    else:
        with open(COEFF_FILE) as f:
            _coeffs_cache = json.load(f)
    _coeffs_last_loaded = now
    return _coeffs_cache


def compute_wm(Vr):
    """
    Solves for the steady-state speed given the fitted differential equation:
        dWm/dt = a + b*Wm + c*Vr + d*Wm*Vr + e*Wm^2 + f*Vr^3

    At steady state, dWm/dt = 0. Grouping as a quadratic in Wm:
        A*Wm^2 + B(Vr)*Wm + C(Vr) = 0
        A = e
        B(Vr) = b + d*Vr
        C(Vr) = a + c*Vr + f*Vr^3
    """
    coeffs = load_coeffs()
    if coeffs is None:
        return None

    A = coeffs["e"]
    B = coeffs["b"] + coeffs["d"] * Vr
    C = coeffs["a"] + coeffs["c"] * Vr + coeffs["f"] * Vr**3

    if abs(A) < 1e-12:
        if abs(B) < 1e-12:
            return None
        return -C / B

    discriminant = B**2 - 4 * A * C
    if discriminant < 0:
        return None

    root1 = (-B + discriminant**0.5) / (2 * A)
    root2 = (-B - discriminant**0.5) / (2 * A)

    candidates = [r for r in (root1, root2) if r >= 0]
    if not candidates:
        return max(root1, root2)
    return min(candidates)


@app.route("/", methods=["GET"])
def dashboard():
    return render_template("dashboard.html")


@app.route("/telemetry", methods=["POST"])
def telemetry():
    """
    ESP32 posts JSON: {"Vr": 12.0, "Wr": 57.3, "time": 123456}
    """
    data = request.get_json(force=True, silent=True)
    if not data or "Vr" not in data or "Wr" not in data:
        return jsonify({"error": "expected JSON with 'Vr' and 'Wr'"}), 400

    Vr = float(data["Vr"])
    Wr = float(data["Wr"])
    time_r = data.get("time", int(time.time() * 1000))

    Wm = compute_wm(Vr)
    time_m = int(time.time() * 1000) if Wm is not None else None

    db = get_db()
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO MotorLogs (Vr, Wr, time_r, Wm, time_m) VALUES (%s, %s, %s, %s, %s)",
        (Vr, Wr, time_r, Wm, time_m),
    )
    db.commit()
    cursor.close()
    db.close()

    entry = {
        "t": time.time(),
        "Vr": Vr,
        "Wr": Wr,
        "Wm": Wm,
        "deviation": abs(Wr - Wm) if Wm is not None else None,
    }
    with lock:
        history.append(entry)

    return jsonify(entry), 201


@app.route("/latest", methods=["GET"])
def latest():
    with lock:
        if not history:
            return jsonify({"error": "no data yet"}), 404
        return jsonify(history[-1])


@app.route("/history", methods=["GET"])
def get_history():
    n = request.args.get("n", default=100, type=int)
    with lock:
        data = list(history)[-n:]
    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
