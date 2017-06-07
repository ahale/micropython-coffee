
import gc
import os
import time
import json
import network
from coffee.machine import espresso

sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)

while not sta_if.isconnected():
    print('waiting for wifi')
    time.sleep(1)

del(sta_if)
gc.collect()

try:
    with open('silvia.conf') as conf:
        data = conf.readline()
        pidvars = json.loads(data)
except OSError:
    pidvars = {'brew_setpoint': 78.0,
               'steam_setpoint': 110.0,
               'cycle_time': 1.0,
               'power': 1000,
               'enabled': True,
               'k_param': 70.0,
               'i_param': 80.0,
               'd_param': 4.0,
               'broker_ip': '192.168.0.28',
               'shot_timer_enabled': True,
               'shot_timer_duration': 25,
               }

    with open('silvia.conf', "w") as conf:
        conf.write(json.dumps(pidvars))

silvia = espresso(pidvars)

if (silvia.pump_button.state and silvia.steam_button.state):
    print('started in debug mode')
    import webrepl
    webrepl.start()
    gc.collect()
else:
    while True:
        print('started in coffee mode')
        silvia.run_forever()
