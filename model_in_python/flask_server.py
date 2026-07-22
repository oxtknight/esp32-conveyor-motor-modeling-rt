import time
import threading
from collections import deque
from flask import Flask, request, jsonify, render_template

from twin_motor import JBG37twin  # calibrated ratio 168:1

app = Flask(__name__)


motor = JBG37twin()
lock = threading.Lock()
HISTORY_LEN = 500
history = deque(maxlen=HISTORY_LEN)

last_step_time = time.time()

DEFAULT_VOLTAGE = 12.0  


def record(real_rpm, real_current, virt_rpm, virt_current):
    entry = {
        "t": time.time(),
        "real_rpm": real_rpm,
        "real_current": real_current,
        "virtual_rpm": virt_rpm,
        "virtual_current": virt_current,
        "rpm_error": abs(real_rpm - virt_rpm),
        "current_error": abs(real_current - virt_current),
    }
    history.append(entry)
    return entry


@app.route("/", methods=["GET"])
def dashboard():
    return render_template("dashboard.html")


@app.route("/telemetry", methods=["POST"])
def telemetry():
    """
    ESP8266 posts JSON like:
        {"rpm": 63.5, "current": 0.121, "voltage": 12.0, "load_torque": 0.0}
    voltage/load_torque are optional -- default to nominal if omitted.
    """
    global last_step_time
    data = request.get_json(force=True, silent=True)
    if not data or "rpm" not in data or "current" not in data:
        return jsonify({"error": "expected JSON with 'rpm' and 'current'"}), 400

    real_rpm = float(data["rpm"])
    real_current = float(data["current"])
    voltage = float(data.get("voltage", DEFAULT_VOLTAGE))
    load_torque = float(data.get("load_torque", 0.0))

    with lock:
        now = time.time()
        dt = now - last_step_time
        dt = min(max(dt, 0.001), 0.1)  # clamp: never 0 (unstable div), never huge (startup/drop gaps)
        last_step_time = now

        virt_rpm, virt_current = motor.step(voltage, load_torque=load_torque, dt=dt)
        entry = record(real_rpm, real_current, virt_rpm, virt_current)

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
    # host="0.0.0.0" 
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
