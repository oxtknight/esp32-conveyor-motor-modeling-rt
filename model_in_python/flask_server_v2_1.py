import os
import time
import json
import threading
from collections import deque
from flask import Flask, request, jsonify, render_template
import mysql.connector

app = Flask(__name__)

# ==========================================
# 1. DATABASE CONFIGURATION
# ==========================================
# NOTE: For local testing, you can temporarily hardcode your password here.
# If keeping it as os.environ.get(), remember to run:
# export DB_PASSWORD='your_mysql_root_password'
DB_CONFIG = {
    "host": "localhost",
    "user": "twinuser",
    "password": "password123", 
    "database": "virtualtwin",
}

# ==========================================
# 2. COEFFICIENT MANAGEMENT
# ==========================================
COEFF_FILE = "wm_equation_coeffs.json"
lock = threading.Lock()
history = deque(maxlen=500)

_coeffs_cache = None
_coeffs_last_loaded = 0
COEFF_RELOAD_INTERVAL_S = 60  # Re-check the file at most once every minute


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


# ==========================================
# 3. FITTED MODEL LOGIC (UPDATED)
# ==========================================
# REPLACE YOUR compute_wm FUNCTION WITH THIS:
def compute_wm(Vr, Wr):
    coeffs = load_coeffs()
    if coeffs is None:
        return None
    
    # Extract the 5 coefficients your fitting script actually saves
    a = coeffs.get("a", 0)
    b = coeffs.get("b", 0)
    c = coeffs.get("c", 0)
    d = coeffs.get("d", 0)
    g = coeffs.get("g", 0)

    # Apply the exact normalization used in the fitting script (12V, 60RPM)
    Vn = Vr / 12.0
    Wn = Wr / 60.0

    # Compute normalized Wm using the exact polynomial formula
    Wm_norm = (
        a * Wn * Vn
        + (b / 2) * Vn * (Wn**2)
        + (c / 2) * Wn * (Vn**2)
        + (d / 4) * (Wn**2) * (Vn**2)
        + g
    )

    # De-normalize back to actual RPM
    return Wm_norm * 60.0

# ==========================================
# 4. FLASK ROUTES
# ==========================================
@app.route('/wm_equation_coeffs.json', methods=['POST'])
def receive_coeffs():
    data = request.get_json()
    print("Received coefficients:")
    print(data)
    with open(COEFF_FILE, "w") as f:
        json.dump(data, f, indent=4)
    return jsonify({"status": "received"})


@app.route("/", methods=["GET"])
def dashboard():
        return render_template("dashboard.html")
@app.route("/telemetry", methods=["POST"])
def telemetry():
    data = request.get_json(force=True, silent=True)
    if not data or "Vr" not in data or "Wr" not in data:
        return jsonify({"error": "expected JSON with 'Vr' and 'Wr'"}), 400

    Vr = float(data["Vr"])
    Wr = float(data["Wr"])
    time_r = data.get("time", int(time.time() * 1000))
    Wm = compute_wm(Vr, Wr)
    time_m = int(time.time() * 1000) if Wm is not None else None

    try:
        db = get_db()
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO MotorLogs (Vr, Wr, time_r, Wm, time_m) VALUES (%s, %s, %s, %s, %s)",
            (Vr, Wr, time_r, Wm, time_m),
        )
        db.commit()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"Database error (check your credentials): {e}")

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
            return jsonify({"latest": None}), 200
        return jsonify(history[-1])
@app.route("/history", methods=["GET"])
def get_history():
    n = request.args.get("n", default=100, type=int)
    with lock:
        data = list(history)[-n:]
    return jsonify(data)
if __name__ == "__main__":
        app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
