# ---------------------------------Basic Version------------------------------------------
# import packages
import numpy as np
from numpy.random import seed
# setting the seed
seed(10)
import pandas as pd
import pysindy as ps
import matplotlib.pyplot as plt
from sklearn.linear_model import Lasso

# data
exp_data_tr = pd.read_csv('/home/bl/python_scripts/fixeddataset.csv')
exp_data_tr.columns = ['time', 'voltage','velocity','experiment_id']

#t_tr=exp_data_tr["time"]
#t_tr=np.array(t_tr)

#v_tr=exp_data_tr["voltage"]
#v_tr=np.array(v_tr)

#theta_tr=exp_data_tr["velocity"]
#theta_tr=np.array(theta_tr)

#theta_v_tr = np.stack((theta_tr,v_tr), axis=-1)  # First column is theta, second is v
#print(theta_v_tr.shape)
# Separate experiments into independent trajectories
#theta_tr = []
#v_tr = []
#t_tr = []

#for exp_id in exp_data_tr["experiment_id"].unique():

 #   exp = exp_data_tr[exp_data_tr["experiment_id"] == exp_id]

  #  theta_tr.append(exp["velocity"].values)
  #  v_tr.append(exp["voltage"].values)

    # reset time for each experiment
  #  t_tr.append(exp["time"].values - exp["time"].values[0])

#for exp_id in exp_data_tr["experiment_id"].unique():

#    exp = exp_data_tr[exp_data_tr["experiment_id"] == exp_id]

    # ensure time is ordered and remove duplicate time points
 #   exp = exp.sort_values("time")
  #  exp = exp.drop_duplicates(subset="time")

   # theta_tr.append(exp["velocity"].values)
    #v_tr.append(exp["voltage"].values)

    #t = exp["time"].values
    #t_tr.append(t - t[0])
theta_tr = []
v_tr = []
t_tr = []

for exp_id in exp_data_tr["experiment_id"].unique():

    exp = exp_data_tr[exp_data_tr["experiment_id"] == exp_id]

    # sort and remove duplicate time samples
    exp = exp.sort_values("time")
    exp = exp.drop_duplicates(subset="time")

    t = exp["time"].values
    theta = exp["velocity"].values
    voltage = exp["voltage"].values

    # safety check
    if not (len(t) == len(theta) == len(voltage)):
        print("Length mismatch in experiment:", exp_id)
        continue

    t_tr.append(t - t[0])
    theta_tr.append(theta)
    #v_tr.append(voltage)
    v_tr.append(voltage.reshape(-1, 1))


print("Number of trajectories:", len(theta_tr))
print(len(theta_tr))

# Testind/Validation Data
exp_data_ts = pd.read_csv('/home/bl/python_scripts/fixeddataset.csv')

exp_data_ts.columns = ['time', 'voltage','velocity','experiment_id']

#t_ts=exp_data_ts["time"]
#t_ts=np.array(t_ts)

#v_ts=exp_data_ts["voltage"]
#v_ts=np.array(v_ts)

#theta_ts=exp_data_ts["velocity"]
#theta_ts=np.array(theta_ts)

theta_ts = []
v_ts = []
t_ts = []

for exp_id in exp_data_ts["experiment_id"].unique():

    exp = exp_data_ts[exp_data_ts["experiment_id"] == exp_id]

    theta_ts.append(exp["velocity"].values)
    v_ts.append(exp["voltage"].values)

    t_ts.append(exp["time"].values - exp["time"].values[0])


#theta_v_ts = np.stack((theta_ts,v_ts), axis=-1)  # First column is theta, second is v
#print(theta_v_ts.shape)
theta_v_ts = None


ssr_optimizer = ps.SSR(alpha=.1,max_iter=20, criteria="model_residual",verbose=True ) # Stepwise sparse regression (SSR)
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

for i in range(len(theta_ts)):
    x_pre2.append(
        model2.simulate(
            x0=[theta_ts[i][0]],
            u=v_ts[i],
            t=t_ts[i]
        )
    )


print(x_pre2.shape)
# Compute derivatives with a finite difference method, for comparison
#x__dot_com2= model2.differentiate(theta_ts, 0.02)
x__dot_com2 = [
    model2.differentiate(theta_ts[i], t_ts[i])
    for i in range(len(theta_ts))
]
