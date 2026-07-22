import os
import time
import threading
from flask import Flask, request
import mysql.connector
from twin_motor import JBG37twin  # this is the callibrated model 

app = Flask(__name__)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": os.environ.get("DB_PASSWORD"),  # set via: export DB_PASSWORD=yourpass
    "database": "virtualtwin",
}

motor = JBG37twin()
lock = threading.Lock()
last_step_time = time.time()
KT = 1.8102

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def run_twin_logic(voltage, load_torque=0.0):
    global last_step_time
    with lock:
        now = time.time()
        dt = now - last_step_time
        dt = min(max(dt, 0.001), 0.1)  
        last_step_time = now

        predicted_rpm, _predicted_current = motor.step(voltage, load_torque=load_torque, dt=dt)

    return predicted_rpm

@app.route('/update-motor', methods=['GET'])
def update_motor():
    try:
        v_real = float(request.args.get('v', 0))
        i_real = float(request.args.get('i', 0))
        rpm_real = float(request.args.get('rpm', 0))

        rpm_virtual = run_twin_logic(v_real)
        torque_real = KT * i_real  # Real_torque = Kt x Current

        error = abs(rpm_real - rpm_virtual)
        if error > 10:
            status = "Anomaly: Friction/Jam"
        elif v_real > 2 and rpm_real < 1:
            status = "Critical: Motor Stalled"
        else:
            status = "Healthy"

        db = get_db()
        cursor = db.cursor()
        sql = (
                "INSERT INTO MotorLogs "
            "(Real_speed, Current, Voltage, Model_speed, Real_torque, Time) "
            "VALUES (%s, %s, %s, %s, %s, %s)"

        )
        val = (rpm_real, i_real, v_real, rpm_virtual, torque_real, int(time.time()))
        cursor.execute(sql, val)
        db.commit()
        cursor.close()
        db.close()

        print(f"DEBUG: V={v_real}V | Real RPM={rpm_real} | Twin RPM={rpm_virtual:.2f} | Torque={torque_real:.4f}Nm | {status}")

        return f"Twin Synced. Status: {status}", 200
    except Exception as e:
        print(f"System Error: {e}")
        return "Error", 500



if __name__ == "__main__":
    # host="0.0.0.0" 
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
