#Fit Using differential_evolution Algorithm
import matplotlib.pyplot as plt
import numpy as np
import lmfit
import mysql.connector
import os
import requests
from scipy.signal import savgol_filter

#################################################################
DB_CONFIG = {
    "host": "localhost",
    "user": "devuser",
    "password": "your_password",
    "database": "virtualData",
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

db = get_db()
cursor = db.cursor()

cursor.execute("""
SELECT id, time_r, Vr, Wr
FROM V_measurements
WHERE Wr IS NOT NULL
ORDER BY time_r
""")

rows = cursor.fetchall()
# Time step
dt = 0.1 
ids    = np.array([row[0] for row in rows])
time_r = np.array([row[1] for row in rows])
Vr     = np.array([row[2] for row in rows])
Wr     = np.array([row[3] for row in rows])
"""
# Use all available measurements
start = 0

ids = ids[start:]
time_r = time_r[start:]
Vr = Vr[start:]
Wr = Wr[start:]
"""
print(f"Loaded {len(Vr)} samples from the database.")

if len(Vr) == 0:
    raise RuntimeError("Collect data before running the fitting script.")

start = 3     #it was discarding the first 3000 rows of the database 
ids = ids[start:]
time_r = time_r[start:]
Vr = Vr[start:]
Wr = Wr[start:]

cursor.close()
db.close()
"""
def resid(params, Vr, Wr):
    a = params['a'].value
    b = params['b'].value
    c = params['c'].value
    d = params['d'].value
    g = params['g'].value
    # Normalize inputs
    Vn = Vr / 12.0
    Wn = Wr / 60.0
    Wm = a*Wn*Vn + (b/2)*Vn*Wn**2 + (c/2)*Wn*Vn**2 + (d/4)*(Wn**2)*(Vn**2) + g
    # Convert back to RPM
    Wm = Wm * 60.0
    return Wm - Wr
"""
def resid(params, Vr, Wr):

    a = params['a'].value
    b = params['b'].value
    c = params['c'].value
    d = params['d'].value
    e = params['e'].value
    f = params['f'].value
    Wm = Wr + (a + b*Wr + c*Vr + d*Wr*Vr + e*Vr**2 + f*Vr**3)*dt
    penalty = np.zeros_like(Wm)
    # motor cannot exceed rated speed
    penalty[Wm > 1] = (Wm[Wm > 1]-1)*50
    # motor cannot go negative
    penalty[Wm < 0] = (-Wm[Wm < 0])*50
    return (Wm - Wr) + penalty
###############################################################################
# Generate synthetic data and set-up Parameters with initial values/boundaries:
#a = 0
#b = 0
#c = 0
#d = 0
#e = 0
#f = 0
#g = 0
#Those are only for testing
#############################################################################
params = lmfit.Parameters()
params.add('a', 0, min=-10, max=10)
params.add('b', 0, min=-10, max=10)
params.add('c', 0, min=-10, max=10)
params.add('d', 0, min=-10, max=10)
params.add('e', 0, min=-10, max=10)
params.add('f', 0, min=-10, max=10)
###############################################################################
# Perform the fits and show fitting results and plot:
#o1 = lmfit.minimize(resid, params, args=(x, yn), method='leastsq')
#print("# Fit using leastsq:")
#lmfit.report_fit(o1)
###############################################################################
#Normalizing values
Vn = Vr / 12.0
Wn = Wr / 60.0
print("FIT Vr:", Vn.min(), Vn.max())
print("FIT Wr:", Wn.min(), Wn.max())
o2 = lmfit.minimize(resid, params, args=(Vn, Wn), method='leastsq')
print("\n\n# Fit using least square method:")
lmfit.report_fit(o2)
best = o2.params
Wm = np.zeros_like(Vn) #NumPy array filled entirely with zeros 
# to match the exact same length and data type of Vn
Wm[0] = Wr[0]  # Start with the first real measured speed

for i in range(1, len(Vn)):
    Wn_prev = Wm[i-1] / 60.0  # Previous prediction (normalized)
    Vni = Vn[i]              # Real measured voltage
    
    Wm_step = (
      Wn_prev + (best["a"].value + best["b"].value * Wn_prev + best["c"].valu * Vni + best["d"].value * Wn_prev * Vni + best["e"].value * Vni**2 + best["f"].value * Vni**3)*dt
    )
    Wm[i] = Wm_step * 60.0    # Reconvert
wm_equation_coeffs = {
    "a": best["a"].value,
    "b": best["b"].value,
    "c": best["c"].value,
    "d": best["d"].value,
    "e": best["e"].value,
    "f": best["f"].value,
    "time_m": int(time_r[-1])
}
###############################################################################
#Sending to MySQL
db = get_db()
cursor = db.cursor()
for i in range(len(time_r)):
    cursor.execute("""
    UPDATE V_measurements
    SET Wm = %s,
    time_m = %s
    WHERE id=%s
    """,(float(Wm[i]),int(time_r[-1]),int(ids[i])))
db.commit()
cursor.close()
db.close()
###############################################################################
#Sending Data to flask
url = "http://127.0.0.1:5000/wm_equation_coeffs.json"

response = requests.post(url,json = wm_equation_coeffs)

print(response.status_code)
print(response.text)
###############################################################################
valid_idx = Wm > 1.0  # Only calculate percentage when speed is > 1 rad/s
pct_error = np.mean(np.abs((Wm[valid_idx] - Wr[valid_idx]) / Wm[valid_idx])) * 100

print(f"Average Percentage Error: {pct_error:.2f}%")
print(f"Average Twin Accuracy: {100 - pct_error:.2f}%")
print("Vr:", Vr[:5], "...", Vr[-1])NumPy array filled entirely with zeros, designed to match the exact same length and data type as your Vn
print("Wr:", Wr[:5], "...", Wr[-1])
print("Wm:", Wm[:5], "...", Wm[-1])
# Using filter eliminate noise
#Wm_smoothed = savgol_filter(Wm, window_length=201, polyorder=2)
#priting values range
print("Wr range:", np.min(Wr), np.max(Wr))
print("Wm range:", np.min(Wm), np.max(Wm))
# Srting Data
#order = np.argsort(Vr)
#plt.plot(Vr, Wr, 'o', label='data')
# Ploting result
#plt.plot(Vr[order], Wm_smoothed[order], '--', label='diffev')
#order = np.argsort(Vr)
#plt.plot(Vr, Wr, 'o', label='data')
#plt.plot(Vr[order],Wm[order],'--',label='diffev')
#plt.legend()
#plt.show()
order = np.argsort(Vr)
Wm_sorted = Wm[order]
Wm_smoothed = savgol_filter(Wm_sorted,window_length=201,polyorder=2) #this didnt let the windwo of the figure open
plt.plot(Vr, Wr, 'o', label='data')
plt.plot(Vr[order],Wm_smoothed,'--',label='diffev')
plt.legend()
plt.show()
#plt.savefig("fit_plot.png")
#plt.close()
 
# Reconstruct the time vector based on data length
num_points = len(Wm)
time = np.arange(0, num_points * dt, dt)

# plot vs. Time
plt.figure(figsize=(12, 4))

# Plot Measured vs Fitted Speed on Primary Axis
#plt.plot(time, Wm, 'b.', label='Measured Speed (Wm)', alpha=0.5, markersize=3)
#plt.plot(time, Wr, 'r--', label='Model Speed (Wr)', linewidth=1.5)
step = 20   # only for visualization

plt.plot(time[::step], Wm[::step], color='blue', linestyle='None', marker='.', markersize=3, alpha=0.5, label='Measured Speed (Wr)')

plt.plot(time[::step], Wr[::step], color='red', linestyle='-', linewidth=1, label='Model Speed (Wm)')
plt.xlabel('Time (seconds)', fontsize=12)
plt.ylabel('Speed (rad/s or RPM)', fontsize=12)
plt.title('Digital Twin Tracking: Measured vs. Fitted Speed over Time', fontsize=14)
plt.legend(loc='upper left')
plt.grid(True, linestyle='--', alpha=0.6)
plt.tight_layout()
plt.show()
#plt.savefig("fit_plot.png")
#plt.close()

error = Wm - Wr

RMSE = np.sqrt(np.mean(error**2))
MAE = np.mean(np.abs(error))

print("RMSE =", RMSE)
print("MAE =", MAE)
