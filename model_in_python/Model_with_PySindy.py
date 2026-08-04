 
# import packages
import numpy as np
from numpy.random import seed

# setting the seed
seed(10)

import pandas as pd
import pysindy as ps
import matplotlib.pyplot as plt
from sklearn.linear_model import Lasso


# data from dataset
exp_data_tr = pd.read_csv('/home/bl/python_scripts/fixeddataset.csv')
exp_data_tr.columns = ['time', 'voltage','velocity','experiment_id']

# Separate experiments into independent trajectories
theta_tr = []
v_tr = []
t_tr = []

for exp_id in exp_data_tr["experiment_id"].unique():
    exp = exp_data_tr[exp_data_tr["experiment_id"] == exp_id]
    exp = exp.sort_values("time")
    exp = exp.drop_duplicates(subset="time")

    t = exp["time"].values
    theta = exp["velocity"].values
    voltage = exp["voltage"].values

    # Checking Data existance
    if not (len(t) == len(theta) == len(voltage)):
        print("Length mismatch in experiment:", exp_id)
        continue

    t_tr.append(t - t[0])
    theta_tr.append(theta)
    v_tr.append(voltage.reshape(-1, 1))


print("Number of trajectories:", len(theta_tr))
print(len(theta_tr))

ssr_optimizer = ps.SSR(alpha=.1, max_iter=20, criteria="model_residual", verbose=True)
lasso_optimizer = Lasso(alpha=0.1, max_iter=200, fit_intercept=False)
stlsq_optimizer = ps.STLSQ(threshold=0.1)
sr3_optimizer = ps.SR3(threshold=0.1, thresholder='l1')
frols_optimizer = ps.FROLS(alpha=.005)
differentiation_method = ps.FiniteDifference(order=2)
feature_library = ps.PolynomialLibrary(degree=3)

model2 = ps.SINDy(
    differentiation_method=differentiation_method,
    feature_library=feature_library,
    optimizer=lasso_optimizer,
    feature_names=["theta", "v"]
)

model2.fit( x=theta_tr,t=t_tr, u=v_tr, quiet=True, multiple_trajectories=True)

# Print discovered equation
model2.print()





