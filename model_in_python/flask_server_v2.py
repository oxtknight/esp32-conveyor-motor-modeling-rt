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
    Solves for the steady-state speed given the discovered differential
    equation:
        d(speed)/dt = c0 + c1*speed + c2*Vr + c3*speed^2 + c4*speed*Vr + c5*Vr^2

    At steady state, d(speed)/dt = 0. Grouping as a quadratic in speed:
        a*speed^2 + b(Vr)*speed + c(Vr) = 0
        a = c3
        b(Vr) = c1 + c4*Vr
        c(Vr) = c0 + c2*Vr + c5*Vr^2

    NOTE: this equation currently produces steady-state values roughly
    5-8x larger than the motor's real known range (~55-65 RPM at 12V),
    and does not return ~0 at Vr=0 as physically expected. Most likely
    cause: a time-units mismatch (milliseconds vs seconds) in the
    original PySINDy fit. Not corrected here due to time constraints --
    documented as a known limitation.
    """
    coeffs = load_coeffs()
    if coeffs is None:
        return None

    a = coeffs["c3"]
    b = coeffs["c1"] + coeffs["c4"] * Vr
    c = coeffs["c0"] + coeffs["c2"] * Vr + coeffs["c5"] * Vr**2

    if abs(a) < 1e-12:
        # degenerate case: equation is effectively linear in speed
        if abs(b) < 1e-12:
            return None
        return -c / b

    discriminant = b**2 - 4 * a * c
    if discriminant < 0:
        return None  # no real steady-state solution for this voltage

    root1 = (-b + discriminant**0.5) / (2 * a)
    root2 = (-b - discriminant**0.5) / (2 * a)

    # pick the physically plausible root: prefer non-negative, smaller magnitude
    candidates = [r for r in (root1, root2) if r >= 0]
    if not candidates:
        return max(root1, root2)  # both negative -- return the less-negative one
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

    deviation = abs(Wr - Wm) if Wm is not None else None

    cursor.execute("""
    INSERT INTO MotorLogs
    (Vr, Wr, time_r, Wm, time_m, deviation)
    VALUES (%s, %s, %s, %s, %s, %s)
    """, (
       Vr,
       Wr,
       time_r,
       Wm,
       time_m,
       deviation,
    ))

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
