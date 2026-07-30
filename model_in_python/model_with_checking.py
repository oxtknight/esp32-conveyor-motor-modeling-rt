# import packages
import numpy as np
from numpy.random import seed
# setting the seed
seed(10)
import pandas as pd
import pysindy as ps
import matplotlib.pyplot as plt
from sklearn.linear_model import Lasso

# ==========================
# Data
# ==========================
from sklearn.model_selection import train_test_split

# Read dataset once
exp_data = pd.read_csv('/home/bl/python_scripts/fixeddataset.csv')
exp_data.columns = ['time', 'voltage', 'velocity', 'experiment_id']

# Split by experiment ID (80% training / 20% testing)
experiment_ids = exp_data["experiment_id"].unique()

train_ids, test_ids = train_test_split(
    experiment_ids,
    test_size=0.20,
    random_state=10,
    shuffle=True
)

# Create training and testing dataframes
exp_data_tr = exp_data[exp_data["experiment_id"].isin(train_ids)]
exp_data_ts = exp_data[exp_data["experiment_id"].isin(test_ids)]

# =====================================================
# Training trajectories
# =====================================================
theta_tr = []
v_tr = []
t_tr = []

for exp_id in train_ids:

    exp = exp_data_tr[exp_data_tr["experiment_id"] == exp_id]

    # Ensure samples are ordered correctly
    exp = exp.sort_values("time")

    # Remove duplicated time samples
    exp = exp.drop_duplicates(subset="time")

    t = exp["time"].to_numpy()
    theta = exp["velocity"].to_numpy()
    voltage = exp["voltage"].to_numpy()

    # Skip empty experiments
    if len(t) == 0:
        continue

    # Keep only experiments with matching lengths
    if len(t) != len(theta) or len(t) != len(voltage):
        print(f"Skipping experiment {exp_id}: inconsistent lengths")
        continue

    theta_tr.append(abs(theta.reshape(-1, 1)))
    v_tr.append(voltage.reshape(-1, 1))
    t_tr.append(t - t[0])

print("Training trajectories:", len(theta_tr))

# =====================================================
# Testing trajectories
# =====================================================
theta_ts = []
v_ts = []
t_ts = []

for exp_id in test_ids:

    exp = exp_data_ts[exp_data_ts["experiment_id"] == exp_id]

    exp = exp.sort_values("time")
    exp = exp.drop_duplicates(subset="time")

    t = exp["time"].to_numpy()
    theta = exp["velocity"].to_numpy()
    voltage = exp["voltage"].to_numpy()

    if len(t) == 0:
        continue

    if len(t) != len(theta) or len(t) != len(voltage):
        print(f"Skipping experiment {exp_id}: inconsistent lengths")
        continue

    theta_ts.append(theta.reshape(-1, 1))
    v_ts.append(voltage.reshape(-1, 1))
    t_ts.append(t - t[0])

for i in range(len(theta_ts)):
    if not np.isfinite(theta_ts[i]).all():
        print("Bad theta trajectory:", i)

    if not np.isfinite(v_ts[i]).all():
        print("Bad voltage trajectory:", i)

    if not np.isfinite(t_ts[i]).all():
        print("Bad time trajectory:", i)
print("Testing trajectories:", len(theta_ts))


ssr_optimizer = ps.SSR(alpha=.1,max_iter=20, criteria="model_residual",verbose=True ) # Stepw>
lasso_optimizer = Lasso(alpha=0.1, max_iter=200, fit_intercept=False)
stlsq_optimizer = ps.STLSQ(threshold=0.1) # Didn't work well at all
sr3_optimizer = ps.SR3(threshold=0.1, thresholder='l1')
#sr3_optimizer = ps.SR3(reg_weight_lam=0.1)
frols_optimizer = ps.FROLS(alpha=.005) # Forward Regression Orthogonal Least Squares (FROLS) 


differentiation_method = ps.FiniteDifference(order=2)
feature_names =["theta", "v"]
feature_library = ps.PolynomialLibrary(degree=3)
model2 = ps.SINDy(
    differentiation_method=differentiation_method,
    feature_library=feature_library,
    optimizer=lasso_optimizer,
    feature_names=["theta", "v"]
)

from time import time
# Start timer
t0 = time()
#model2.fit(x=theta_tr, t=t_tr,u=v_tr,quiet=True)
#This is an added part
for i in range(len(theta_tr)):
    print(
        "Experiment", i,
        "x:", np.shape(theta_tr[i]),
        "u:", np.shape(v_tr[i]),
        "t:", np.shape(t_tr[i])
    )
#This is an added part

print(theta_tr[0].shape)
print(v_tr[0].shape)
print(t_tr[0].shape)
model2.fit(x=theta_tr, t=t_tr, u=v_tr, quiet=True, multiple_trajectories=True)
#this is an added part
for i in range(len(theta_tr)):
    if len(theta_tr[i]) != len(v_tr[i]) or len(theta_tr[i]) != len(t_tr[i]):
        print("Mismatch at experiment:", i)
        print(len(theta_tr[i]), len(v_tr[i]), len(t_tr[i]))
# Print computation time
print('\nComputation time: {} seconds'.format(time()-t0))


# Print the discovered model
model2.print()

# Predict derivatives using the learned model
#x_dot_pre2 = model2.predict(x=theta_ts,u=v_ts) 
#x_pre2=model2.simulate(x0=[0],u=v_ts, t=t_ts)
#x_dot_pre2 = model2.predict(x=theta_ts, u=v_ts)
x_dot_pre2 = model2.predict(x=theta_ts, u=v_ts, multiple_trajectories=True)
x_pre2 = []

#for i in range(len(theta_ts)):
 #   x_pre2.append(
  #      model2.simulate(
   #         x0=np.array([theta_ts[i][0,0]]),
    #        u=v_ts[i],
     #       t=t_ts[i]
      #  )
    #)
x_pre2 = []

for i in range(len(theta_ts)):

    print("\nSimulating trajectory:", i)

    print("Initial theta:", theta_ts[i][0,0])
    print("Voltage min/max:",
          np.min(v_ts[i]),
          np.max(v_ts[i]))

    try:

        result = model2.simulate(
            x0=np.array([theta_ts[i][0,0]]),
            u=v_ts[i],
            t=t_ts[i]
        )

        print("Prediction min/max:",
              np.min(result),
              np.max(result))

        x_pre2.append(result)

    except Exception as e:

        print("FAILED trajectory:", i)
        print(e)
        break

print(x_pre2.shape)
# Compute derivatives with a finite difference method, for comparison
#x__dot_com2= model2.differentiate(theta_ts, 0.02)
x__dot_com2 = [
    model2.differentiate(theta_ts[i], t_ts[i])
    for i in range(len(theta_ts))
]
