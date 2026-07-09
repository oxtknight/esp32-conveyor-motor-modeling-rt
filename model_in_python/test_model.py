import numpy as np

class DCMotorModel:
    def __init__(self):
        self.Va = 6.0        # armature voltage Va
        self.Ra = 3.41       # armature resistance ohms
        self.La = 7.5e-5     # armature inductance henries
        self.KF = 6.589e-3   # back-EMF constant, Vs/rad
        self.J  = 1.0e-7     # rotor inertia, kg.m^2
        self.KM = 6.59e-3    # torque constant, Nm/A
        self.Tf = 1.3e-4     # friction torque, Nm (Coulomb)

        self.w = 0.0         # rad/s
        self.current = 0.0   # Ampps

    def get_acc(self, voltage, load_torque=0.0):#this gets the acceleration brr
        didt = (voltage - (self.Ra * self.current) - (self.KF * self.w)) / self.La

        #here i realized that this has  Coulomb friction: the concept is that it opposes motion, direction depends on sign of w (which is the angular velocity)
        if self.w > 0:
            friction = self.Tf
        elif self.w < 0:
            friction = -self.Tf
        else:
            friction = 0.0  # for uk the static case

        dwdt = ((self.KM * self.current) - friction - load_torque) / self.J
        return didt, dwdt

    def step(self, voltage, load_torque=0.0, dt=0.01, substeps=3000):
        dtsub = dt / substeps
        for _ in range(substeps):
            didt, dwdt = self.get_acc(voltage, load_torque)
            self.current += didt * dtsub
            self.w += dwdt * dtsub
        rpm = self.w * 9.5493
        return rpm, self.current

#here i be testing for 6v 
if __name__ == "__main__":
    motor = DCMotorModel()
    print("6V start")
    for t in range(300):
        rpm, amps = motor.step(6.0, dt=0.01)
        print(f"time: {t*10}ms | speed: {rpm:.2f} rpm | current: {amps:.4f}A")
