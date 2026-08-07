#!/usr/bin/env python3
"""
Feed data from a CSV file to the Flask server.
Reads rows (Vr, Wr, optional time) and POSTs them to /telemetry.
"""

import time
import csv
import requests
import sys
from datetime import datetime

# ============================================================
# Configuration
# ============================================================

CSV_FILE = "../dataset/final_combined_dataset.csv"   # Adjust path if needed
SERVER_URL = "http://localhost:5000/telemetry"

# Column names in your CSV (change if different)
COLUMN_VR = "Vr"          # or "voltage", "V"
COLUMN_WR = "Wr"          # or "speed", "RPM"
COLUMN_TIME = "time"      # or "time_r", "timestamp" – if empty, use current time

# Delay mode:
# - "timestamp": uses time column (must be numeric, in milliseconds)
# - "fixed": uses a fixed delay (FIXED_DELAY_MS) between sends
# - "none": sends as fast as possible
DELAY_MODE = "fixed"      # "timestamp", "fixed", or "none"
FIXED_DELAY_MS = 100      # milliseconds (ESP32 sends every 100ms)

# Speed multiplier for timestamp mode (1.0 = real-time, 2.0 = 2x faster)
SPEED_MULTIPLIER = 1.0

# ============================================================
# Functions
# ============================================================

def read_csv(filename):
    """Read CSV and return list of (Vr, Wr, time_r) tuples."""
    data = []
    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        # Detect column names (case-insensitive)
        headers = {k.lower(): k for k in reader.fieldnames}
        vr_col = None
        wr_col = None
        time_col = None

        for key in headers:
            if key in ['vr', 'voltage', 'v']:
                vr_col = headers[key]
            if key in ['wr', 'speed', 'rpm', 'w']:
                wr_col = headers[key]
            if key in ['time', 'time_r', 'timestamp', 't']:
                time_col = headers[key]

        if not vr_col or not wr_col:
            print("❌ Could not find Vr and Wr columns in CSV.")
            print(f"   Available headers: {list(reader.fieldnames)}")
            sys.exit(1)

        print(f"✅ Using columns: Vr='{vr_col}', Wr='{wr_col}', Time='{time_col}'")

        for row in reader:
            try:
                Vr = float(row[vr_col])
                Wr = float(row[wr_col])
                time_r = int(float(row[time_col])) if time_col and row[time_col] else None
                data.append((Vr, Wr, time_r))
            except (ValueError, KeyError):
                continue

    return data

def feed_data():
    rows = read_csv(CSV_FILE)
    if not rows:
        print("❌ No data read from CSV.")
        return

    print(f"✅ Found {len(rows)} records.")
    print(f"🕐 Starting at {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 60)

    success = 0
    fail = 0

    for i, (Vr, Wr, time_r) in enumerate(rows):
        # Calculate delay
        if DELAY_MODE == "timestamp" and time_r is not None:
            if i == 0:
                delay_ms = 0
            else:
                prev_time = rows[i-1][2]
                if prev_time is not None:
                    delay_ms = (time_r - prev_time) * SPEED_MULTIPLIER
                    if delay_ms < 0:
                        delay_ms = 0
                else:
                    delay_ms = FIXED_DELAY_MS
        elif DELAY_MODE == "fixed":
            delay_ms = FIXED_DELAY_MS
        else:
            delay_ms = 0

        if delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        # Build payload
        payload = {
            "Vr": Vr,
            "Wr": Wr,
            "time": time_r if time_r is not None else int(time.time() * 1000)
        
        }

        try:
            resp = requests.post(SERVER_URL, json=payload, timeout=2)
            if resp.status_code == 201:
                success += 1
                print(f"[{i+1:>4}/{len(rows)}] ✅ Vr={Vr:>6.2f}, Wr={Wr:>6.2f} → {resp.status_code}")
            else:
                fail += 1
                print(f"[{i+1:>4}/{len(rows)}] ❌ HTTP {resp.status_code} – {resp.text}")
        except requests.exceptions.ConnectionError:
            fail += 1
            print(f"[{i+1:>4}/{len(rows)}] ❌ Server not running (start with python3 flask_server_v2.py)")
            break
        except Exception as e:
            fail += 1
            print(f"[{i+1:>4}/{len(rows)}] ❌ Error: {e}")

    print("=" * 60)
    print(f"📊 Done: {success} success, {fail} failed")
    print(f"🕐 Ended at {datetime.now().strftime('%H:%M:%S')}")

# ============================================================
# Main
# ============================================================

if __name__  == "__main__":
    print("=" * 60)
    print("📁 CSV to Flask Data Feeder")
    print("=" * 60)

    # Check server
    try:
        requests.get("http://localhost:5000/", timeout=2)
        print("✅ Flask server is running")
    except:
        print("❌ Flask server is NOT running!")
        print("   Start it with: python3 flask_server_v2.py")
        sys.exit(1)

    feed_data()
