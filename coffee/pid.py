# from https://github.com/steve71/RasPiBrew/blob/master/RasPiBrew/pid/pidpy.py

class PID(object):
    ek_1 = 0.0  # e[k-1] = SP[k-1] - PV[k-1] = setpoint_hlt[k-1] - Thlt[k-1]
    ek_2 = 0.0  # e[k-2] = SP[k-2] - PV[k-2] = setpoint_hlt[k-2] - Thlt[k-2]
    current_temp_1 = 0.0  # PV[k-1] = Thlt[k-1]
    current_temp_2 = 0.0  # PV[k-2] = Thlt[k-1]
    output_1 = 0.0  # y[k-1] = Gamma[k-1]
    output_2 = 0.0  # y[k-2] = Gamma[k-1]
    lpf_1 = 0.0 # lpf[k-1] = LPF output[k-1]
    lpf_2 = 0.0 # lpf[k-2] = LPF output[k-2]

    output = 0.0 # output
    GMA_HLIM = 1000.0
    GMA_LLIM = 0.0

    def __init__(self, pid):
        self.pid = pid
        self.k_lpf = 0.0
        self.k0 = 0.0
        self.k1 = 0.0
        self.k2 = 0.0
        self.k3 = 0.0
        self.lpf1 = 0.0
        self.lpf2 = 0.0
        self.ts_ticks = 0
        self.pid_model = 3
        self.pp = 0.0
        self.pi = 0.0
        self.pd = 0.0
        if (self.pid['i_param'] == 0.0):
            self.k0 = 0.0
        else:
            self.k0 = self.pid['k_param'] * self.pid['cycle_time'] / self.pid['i_param']
        self.k1 = self.pid['k_param'] * self.pid['d_param']/ self.pid['cycle_time']
        self.lpf1 = (2.0 * self.k_lpf - self.pid['cycle_time']) / (2.0 * self.k_lpf + self.pid['cycle_time'])
        self.lpf2 = self.pid['cycle_time'] / (2.0 * self.k_lpf + self.pid['cycle_time'])

    def __call__(self, current_temp, setpoint, enable=True):
        ek = 0.0
        ek = setpoint - current_temp
        if (enable):
            self.pp = self.pid['k_param'] * (PID.current_temp_1 - current_temp)
            self.pi = self.k0 * ek
            self.pd = self.k1 * (2.0 * PID.current_temp_1 - current_temp - PID.current_temp_2)
            PID.output += self.pp + self.pi + self.pd
        else:
            PID.output = 0.0
            self.pp = 0.0
            self.pi = 0.0
            self.pd = 0.0

        PID.current_temp_2 = PID.current_temp_1
        PID.current_temp_1 = current_temp

        if (PID.output > PID.GMA_HLIM):
            PID.output = PID.GMA_HLIM
        if (PID.output < PID.GMA_LLIM):
            PID.output = PID.GMA_LLIM
        return int(PID.output)
