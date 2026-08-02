import requests
import time
import random

url = "http://localhost:5000/telemetry"

print("Starting REALISTIC dummy telemetry simulator...")
while True:
    # Generate a realistic voltage between 6V and 12V
    Vr = round(random.uniform(6.0, 12.0), 2)
    
    # Generate a realistic speed that mimics a real DC motor:
    # At 6V, speed is around ~30 RPM. At 12V, speed is around ~60 RPM.
    # We add a tiny bit of random fluctuation (noise) to simulate real-world vibration.
    base_rpm = Vr * 5.0 
    noise = random.uniform(-1.5, 1.5)
    Wr = round(base_rpm + noise, 2)
    
    # Ensure Wr doesn't go below 0
    if Wr < 0: Wr = 0
    
    payload = {"Vr": Vr, "Wr": Wr}
    
    try:
        response = requests.post(url, json=payload)
        print(f"Sent: {payload} | Dashboard Status: {response.status_code}")
    except Exception as e:
        print(f"Error connecting to Flask: {e}")
    
    time.sleep(0.5) # Send data twice per second to make the chart smooth
