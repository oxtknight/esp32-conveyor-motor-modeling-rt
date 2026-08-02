#Fit Using differential_evolution Algorithm
import matplotlib.pyplot as plt
import numpy as np
import lmfit
import mysql.connector
import os
import requests
from scipy.signal import savgol_filter

##################################################################
#Taking from MySQL
# Using your lead configuration
DB_CONFIG = {
    "host": "localhost",
    "user": "pythonuser",
    "password": "your_password",
    "database": "virtualData",
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

db = get_db()
cursor = db.cursor()

cursor.execute("""
SELECT id, time_r, Vr, Wr
FROM MotorLogs
WHERE Wr IS NOT NULL
ORDER BY time_r
""")

rows = cursor.fetchall()

ids    = np.array([row[0] for row in rows])
time_r = np.array([row[1] for row in rows])
Vr     = np.array([row[2] for row in rows])
Wr     = np.array([row[3] for row in rows])

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
    g = params['g'].value

    Wm = (
        a*Wr*Vr
        +(b/2)*Vr*Wr**2
        +(c/2)*Wr*Vr**2
        +(d/4)*(Wr**2)*(Vr**2)
        +g
    )

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
params.add('g', 0, min=-0.8, max=0.8)
###############################################################################
# Perform the fits and show fitting results and plot:
#o1 = lmfit.minimize(resid, params, args=(x, yn), method='leastsq')
#print("# Fit using leastsq:")
#lmfit.report_fit(o1)
###############################################################################
Vn = Vr / 12.0
Wn = Wr / 60.0
print("FIT Vr:", Vn.min(), Vn.max())
print("FIT Wr:", Wn.min(), Wn.max())
o2 = lmfit.minimize(resid, params, args=(Vn, Wn), method='leastsq')
print("\n\n# Fit using differential_evolution:")
lmfit.report_fit(o2)
best = o2.params
Wm = (
    best["a"].value * Wn * Vn
    + (best["b"].value / 2) * Vn * Wn**2
    + (best["c"].value / 2) * Wn * Vn**2
    + (best["d"].value / 4) * Wn**2 * Vn**2
    + best["g"].value
)
Wm=Wm*60
wm_equation_coeffs = {
    "a": best["a"].value,
    "b": best["b"].value,
    "c": best["c"].value,
    "d": best["d"].value,
    "g": best["g"].value,
    "time_m": int(time_r[-1])
}
###############################################################################
#Sending to MySQL
db = get_db()
cursor = db.cursor()
for i in range(len(time_r)):
    cursor.execute("""
    UPDATE MotorLogs
    SET Wm = %s,
    time_m = %s
    WHERE id=%s
    """,(float(Wm[i]),int(time_r[-1]),int(ids[i])))
db.commit()
cursor.close()
db.close()
###############################################################################
#Sending Data to flask
url = "http://localhost:5000/wm_equation_coeffs.json"

response = requests.post(
    url,
    json = wm_equation_coeffs
)

print(response.status_code)
print(response.text)
###############################################################################
print("Vr:", Vr[:5], "...", Vr[-1])
print("Wr:", Wr[:5], "...", Wr[-1])
print("Wm:", Wm[:5], "...", Wm[-1])
# Using filter tom eliminate noise
Wm_smoothed = savgol_filter(Wm, window_length=201, polyorder=2)
#priting values range
print(os.path.abspath("virtualtwin.sql"))
print("Wr range:", np.min(Wr), np.max(Wr))
print("Wm range:", np.min(Wm), np.max(Wm))
# Srting Data
order = np.argsort(Vr)
plt.plot(Vr, Wr, 'o', label='data')
# Using filter tom eliminate noise - Savitzky-Golay 
Wm_smoothed = savgol_filter(Wm[order], window_length=201, polyorder=2)
# Ploting result
plt.plot(Vr[order], Wm_smoothed, '--', label='diffev')
plt.legend()
plt.show()
