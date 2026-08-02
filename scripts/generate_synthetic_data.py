import numpy as np
import mysql.connector
import time

DB_CONFIG = {
    "host": "localhost",
    "user": "twinuser",
    "password": "password123",
    "database": "virtualtwin",
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

# Parameters
duration = 30          # seconds
dt = 0.1               # 100 ms per sample (match ESP32)
num_samples = int(duration / dt)

# Generate time in milliseconds
time_ms = np.arange(num_samples) * dt * 1000

# 1. Generate varying voltage (Vr) – step changes every 5 seconds
Vr = np.zeros(num_samples)
segment = int(5 / dt)   # samples per 5 seconds
for i in range(num_samples):
    # Alternate between 2, 4, 6, 8, 10 volts
    step = (i // segment) % 5
    Vr[i] = 2 + step * 2
# Add a little noise
Vr += np.random.normal(0, 0.05, num_samples)
Vr = np.clip(Vr, 0, 12)

# 2. Generate speed response (Wr) using a simple first‑order lag
# We'll simulate a motor that follows the voltage with some delay and gain
gain = 25.0          # speed per volt
tau = 0.5            # time constant (seconds)
Wr = np.zeros(num_samples)
for i in range(1, num_samples):
    # Euler integration of first‑order: dW/dt = (gain*V - W)/tau
    Wr[i] = Wr[i-1] + (dt * (gain * Vr[i-1] - Wr[i-1]) / tau)
# Add a little noise
Wr += np.random.normal(0, 1.0, num_samples)
Wr = np.clip(Wr, 0, 300)   # cap realistic speeds

# 3. Insert into database
db = get_db()
cursor = db.cursor()

# Clear old data (optional – comment out if you want to keep)
# cursor.execute("TRUNCATE TABLE MotorLogs")

for i in range(num_samples):
    cursor.execute("""
        INSERT INTO MotorLogs (Vr, Wr, time_r)
        VALUES (%s, %s, %s)
    """, (float(Vr[i]), float(Wr[i]), int(time_ms[i])))

db.commit()
cursor.close()
db.close()

print(f"Inserted {num_samples} synthetic samples into MotorLogs.")
print("Voltage range:", Vr.min(), "–", Vr.max())
print("Speed range:", Wr.min(), "–", Wr.max())
