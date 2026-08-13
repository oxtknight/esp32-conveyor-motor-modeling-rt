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
    "user": "twinuser",
    "password": "password123",
    "database": "virtualtwin",
}

COEFF_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wm_equation_coeffs.json")

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


def compute_wm(Vr, Wr):
    """
    Direct algebraic equation (normalized inputs):
        Vn = Vr / 12.0
        Wn = Wr / 60.0
        Wm_norm = a*Wn*Vn + (b/2)*Vn*Wn^2 + (c/2)*Wn*Vn^2 + (d/4)*Wn^2*Vn^2 + g
        Wm = Wm_norm * 60.0

    NOTE: this equation uses Wr (real speed) as an input, not just Vr.
    Worth being explicit about in the report: this makes Wm partially
    dependent on the real measurement it's being compared against,
    which is a different design than a fully independent virtual twin.
    """
    coeffs = load_coeffs()
    if coeffs is None:
        return None

    Vn = Vr / 12.0
    Wn = Wr / 60.0

    Wm_norm = (
        coeffs["a"] * Wn * Vn
        + (coeffs["b"] / 2) * Vn * Wn**2
        + (coeffs["c"] / 2) * Wn * Vn**2
        + (coeffs["d"] / 4) * (Wn**2) * (Vn**2)
        + coeffs["g"]
    )

    return Wm_norm * 60.0


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

    Wm = compute_wm(Vr, Wr)
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
    db = get_db()
    cursor = db.cursor()
    cursor.execute("""
        SELECT Vr, Wr, Wm, time_r
        FROM MotorLogs
        ORDER BY id DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    cursor.close()
    db.close()
    if not row:
        return jsonify({"error": "no data"}), 404
    Vr, Wr, Wm, time_r = row
    t_sec = time_r / 1000.0
    entry = {
        "t": t_sec,
        "Vr": Vr,
        "Wr": Wr,
        "Wm": Wm,
        "deviation": abs(Wr - Wm) if Wm is not None else None,
    }
    return jsonify(entry)   

@app.route("/history", methods=["GET"])
def get_history():
    n = request.args.get("n", default=100, type=int)
    with lock:
        data = list(history)[-n:]
    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
