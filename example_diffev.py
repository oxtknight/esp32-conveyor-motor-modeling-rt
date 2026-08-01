#Fit Using differential_evolution Algorithm
import matplotlib.pyplot as plt
import numpy as np
import lmfit
import mysql.connector
import os
import requests
##################################################################
#Taking from MySQL
# Using your lead configuration
DB_CONFIG = {
    "host": "localhost",
    "user": "pythonuser",
    "password": "your_password",
    "database": "virtualtwin",
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

Wr_measured = Wr

def resid(params, Vr, Wr):
    a = params['a'].value
    b = params['b'].value
    c = params['c'].value
    d = params['d'].value
    e = params['e'].value
    f = params['f'].value
    g = params['g'].value
    Wm = a*Wr*Vr + (b/2)*Vr*Wr**2 + (c/2)*Wr*Vr**2 + (d/4)*(Wr**2)*(Vr**2) + (e/3)*Wr*Vr**3 + (f/4)*Wr*Vr**4 + g
    return Wm - Wr
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
params.add('a', 0, min=-500, max=500)
params.add('b', 0, min=-500, max=500)
params.add('c', 0, min=-500, max=500)
params.add('d', 0, min=-500, max=500)
params.add('e', 0, min=-500, max=500)
params.add('f', 0, min=-500, max=500)
params.add('g', 0, min=-500, max=500)
###############################################################################
# Perform the fits and show fitting results and plot:
#o1 = lmfit.minimize(resid, params, args=(x, yn), method='leastsq')
#print("# Fit using leastsq:")
#lmfit.report_fit(o1)
###############################################################################
o2 = lmfit.minimize(resid, params, args=(Vr, Wr), method='differential_evolution')
print("\n\n# Fit using differential_evolution:")
lmfit.report_fit(o2)
best = o2.params
Wm = (
    best["a"].value * Wr * Vr
    + (best["b"].value / 2) * Vr * Wr**2
    + (best["c"].value / 2) * Wr * Vr**2
    + (best["d"].value / 4) * Wr**2 * Vr**2
    + (best["e"].value / 3) * Wr * Vr**3
    + (best["f"].value / 4) * Wr * Vr**4
    + best["g"].value
)
wm_equation_coeffs = {
    "a": best["a"].value,
    "b": best["b"].value,
    "c": best["c"].value,
    "d": best["d"].value,
    "e": best["e"].value,
    "f": best["f"].value,
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
plt.plot(Vr, Wr, 'o', label='data')
#plt.plot(x, yn+o1.residual, '-', label='leastsq')
plt.plot(Vr, Wm, '--', label='diffev')
plt.legend()
plt.show()
