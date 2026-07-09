import numpy as np
class JBG37twin:
    def __init__(self):
        self.R = 12.0  #resistance in ohms
        self.L = 0.01 #inductance in henries
        self.Kt = 0.5 #torque constant Nm/A
        self.Ke = 0.5 #back EMF constant V/rad/s
        self.J = 0.0001 #rotor inertia kg.m^2
        self.B = 0.0001 #viscous friction
        self.Ratio = 150 #this ios the gearbox ration from datasheet of the 60 rpm model
        self.w = 0.0 # so this is the angular velocity uk w  rad/s
        self.current = 0.0 # amps
    
    def get_acc(self , voltage , load_torque = 0.0): #so this will get the acceleration using diff eqs 
        didt = (voltage - (self.R * self.current) - (self.Ke * self.w)) / self.L
        dwdt = ((self.Kt * self.current) - (self.B * self.w) - load_torque) / self.J
        
        return didt, dwdt
    
    def step(self, voltage , dt = 0.01):
        didt, dwdt = self.get_acc(voltage)
        self.current += didt * dt
        self.w += dwdt * dt #omaga im losing my marbles copying these equations from pdf fah

        #here i think ill add limitation/protection to not get negative speed , hear me out on this fellas
        if self.w < 0 : self.w = 0

        conveyor_rpm = (self.w * 9.5493) / self.Ratio
        return conveyor_rpm , self.current
 
 if __name__ == "__main__":
     motor = JBG37twin()
     print(" 24v start")
     for t in range(10): 
         rpm, amps = motor.step(24.0, dt= 0.01)
         print(f"time: {t*10}ms | speed: {rpm:.2f} rpm | current: {amps:.3f}A")

