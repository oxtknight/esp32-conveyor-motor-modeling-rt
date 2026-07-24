import numpy as np


class JBG37twin:
    def __init__(self):
        self.Ratio = 168       
        self.R = 5.217          
        self.L = 0.14651       
        self.Kt = 1.81022       
        self.Ke = 1.81022       
        self.J = 0.07056        
        self.B = 0.0345         # viscous friction coefficient, Nm/(rad/s)
        self.Tf = 0.21722       
        self.w = 0.0            
        self.current = 0.0      

    def get_acc(self, voltage, load_torque=0.0):
        didt = (voltage - (self.R * self.current) - (self.Ke * self.w)) / self.L

        friction = self.B * self.w 
        if self.w > 0:
            friction = self.Tf + (self.B * self.w)
        elif self.w < 0:
            friction = -self.Tf + (self.B * self.w)

        dwdt = ((self.Kt * self.current) - friction - load_torque) / self.J
        return didt, dwdt

    def step(self, voltage, load_torque=0.0, dt=0.01, substeps=None):
        if substeps is None:
            tau_e = self.L / self.R
            substeps = max(int((dt / tau_e) * 20), 20)
        dtsub = dt / substeps

        for _ in range(substeps):
            didt, dwdt = self.get_acc(voltage, load_torque)
            self.current += didt * dtsub
            self.w += dwdt * dtsub
            if self.w < 0:
                self.w = 0

        conveyor_rpm = self.w * 9.5493  
        return conveyor_rpm, self.current


if __name__ == "__main__":
    motor = JBG37twin()
    print("12V start")
    for t in range(300):
        rpm, amps = motor.step(12.0, dt=0.01)
        if t % 10 == 0:
            print(f"time: {t*10}ms | speed: {rpm:.2f} rpm | current: {amps:.3f}A")
