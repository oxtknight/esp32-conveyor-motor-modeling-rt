"""
Flask telemetry server for the conveyor digital twin -- LIVE DASHBOARD version.

This is the "quick live view" server, kept separate from update_motor_server.py
(which handles permanent MySQL archiving).

- ESP8266 posts real sensor readings to /telemetry
- Server steps the virtual twin model forward using the same voltage/load
  so Real and Virtual stay time-aligned
- Dashboard (served at /) polls /latest and /history to draw live charts

SYNCHRONIZATION: if the ESP8266 includes its own timestamp ("t_sample",
in milliseconds since boot) with each reading, the server uses THAT clock
to compute dt and to align Real vs Virtual -- not "whenever the server
happened to receive the message." This removes network/WiFi jitter from
corrupting the comparison. If "t_sample" isn't sent, falls back to the
old behavior (server arrival time) automatically -- so this still works
fine with test_feed.py, which doesn't send a timestamp.

Run:
    python3 flask_server.py
Then open:
    http://127.0.0.1:5000/
"""

import time
import threading
from collections import deque
from flask import Flask, request, jsonify, render_template

from twin_motor import JBG37twin  # calibrated physics model (ratio 168:1, block-test params)

app = Flask(__name__)

# ---- shared state -----------------------------------------------------
motor = JBG37twin()
lock = threading.Lock()
HISTORY_LEN = 500
history = deque(maxlen=HISTORY_LEN)

last_step_time = time.time()          # fallback path (no device timestamp)
last_device_t_sample = None            # device's own clock, ms since its boot
device_time_anchor = None              # (server_wall_clock, device_t_sample) pair,
                                        # set on the first timestamped reading,
                                        # used to convert device time -> a
                                        # human-readable wall-clock estimate

DEFAULT_VOLTAGE = 12.0  # update if you drive the motor at a different bus voltage


def record(real_rpm, real_current, virt_rpm, virt_current, display_time):
    entry = {
        "t": display_time,
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
        {"rpm": 63.5, "current": 0.121, "voltage": 12.0, "load_torque": 0.0,
         "t_sample": 123456}
    voltage/load_torque/t_sample are optional.
    t_sample: milliseconds since the ESP8266's own boot (e.g. millis()).
    If omitted, falls back to using server arrival time for dt (old behavior).
    """
    global last_step_time, last_device_t_sample, device_time_anchor
    data = request.get_json(force=True, silent=True)
    if not data or "rpm" not in data or "current" not in data:
        return jsonify({"error": "expected JSON with 'rpm' and 'current'"}), 400

    real_rpm = float(data["rpm"])
    real_current = float(data["current"])
    voltage = float(data.get("voltage", DEFAULT_VOLTAGE))
    load_torque = float(data.get("load_torque", 0.0))
    t_sample = data.get("t_sample")  # device's own clock, ms since boot -- optional

    with lock:
        if t_sample is not None:
            t_sample = float(t_sample)

            if device_time_anchor is None:
                # first timestamped reading -- anchor device clock to wall clock here
                device_time_anchor = (time.time(), t_sample)

            if last_device_t_sample is None:
                dt = 0.01  # first reading, no prior device timestamp to diff against
            else:
                dt = (t_sample - last_device_t_sample) / 1000.0  # ms -> s
                dt = min(max(dt, 0.001), 0.1)  # same safety clamp as before

            last_device_t_sample = t_sample

            # convert device time -> an aligned, human-readable wall-clock estimate
            anchor_wall, anchor_device_t = device_time_anchor
            display_time = anchor_wall + (t_sample - anchor_device_t) / 1000.0
        else:
            # FALLBACK: no device timestamp provided -- use old server-arrival-time behavior
            now = time.time()
            dt = now - last_step_time
            dt = min(max(dt, 0.001), 0.1)
            last_step_time = now
            display_time = now

        virt_rpm, virt_current = motor.step(voltage, load_torque=load_torque, dt=dt)
        entry = record(real_rpm, real_current, virt_rpm, virt_current, display_time)

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
    # host="0.0.0.0" so the ESP8266 on the LAN can reach it
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
