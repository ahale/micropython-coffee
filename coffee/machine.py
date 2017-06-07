import os
import time
import uasyncio as asyncio
from umqtt.simple import MQTTClient
from coffee.pid import PID
from coffee.hardware import Button, Relay
from coffee.functions import *


class espresso(object):
    def __init__(self, pidvars):
        self.pidvars = pidvars
        self.pid = PID(self.pidvars)
        self.brew_button = Button(2, 'brew', self) # blue
        self.pump_button = Button(14, 'pump', self) # brown
        self.steam_button = Button(13, 'steam', self) #green
        self.boiler = Relay(16, 'boiler', self) # purple/pink
        self.valve = Relay(4, 'valve', self)  # grey/blue
        self.pump = Relay(5, 'pump', self) # red/black
        self.boiler.off()
        self.valve.off()
        self.pump.off()
        self._temperature = 0.0
        self._setpoint = self.pidvars['brew_setpoint']
        self._steam_setpoint = self.pidvars['steam_setpoint']
        self._shot_timer_enabled = self.pidvars['shot_timer_enabled']
        self._shot_timer_duration = self.pidvars['shot_timer_duration']
        self.steaming = False
        self.brewing = False
        self.pumping = False
        self.steam_start_time = 0
        self._last_temp_update = 0
        self._power_ms = 0
        self._last_power_update = 0
        self._last_cmd_time = 0
        self._auto_off = True
        self._auto_off_timer = 60 * 60 * 4 # 2 hour timer
        self.enabled = True
        self.mqtt = False
        self.listener = False
        self._get_broker()
        self._get_listener()
        self._buttons = {'brew': self.brew_button.state, 'steam': self.steam_button.state, 'pump': self.pump_button.state}
        self.prev_buttons = {'brew': False, 'steam': False, 'pump': False}
        self.prev_button_change_time = 0
        self.loop = False

    def run_forever(self):
        if not self.loop:
            loop = asyncio.get_event_loop()
            self.loop = False
        loop.call_soon(request_temp, loop, self)
        loop.call_soon(calculate_pid, loop, self)
        loop.call_soon(read_buttons, loop, self)
        loop.call_soon(check_mqtt, loop, self)
        loop.call_soon(status, loop, self)
        loop.call_later_ms_(2000, run_boiler, (loop, self))
        loop.run_forever()
        loop.close()
        self.loop = False

    def saveconfig(self):
        res = True
        try:
            pidvars = {'brew_setpoint': silvia.setpoint,
                       'steam_setpoint': silvia._steam_setpoint,
                       'cycle_time': 1.0,
                       'power': 1000,
                       'enabled': True,
                       'k_param': silvia.pid.pid['k_param'],
                       'i_param': silvia.pid.pid['i_param'],
                       'd_param': silvia.pid.pid['d_param'],
                       'broker_ip': '192.168.0.28',
                       'shot_timer_enabled': silvia.shot_timer_enabled,
                       'shot_timer_duration': silvia.shot_timer_duration,
                       }
            with open('silvia.conf.tmp', "w") as conf:
                conf.write(json.dumps(pidvars))
            os.rename('silvia.conf.tmp', 'silvia.conf')
        except:
            res = False
        return res

    def publish(self, var, val):
        resp = True
        try:
            # if var != 'status':
            print('**published: %s, %s' % (var, str(val)))
            self.mqtt.publish(var, str(val))
        except (AttributeError, OSError):
            resp = False
            self._get_broker()
            try:
                self.mqtt.publish(var, str(val))
                resp = True
            except:
                pass
        return resp

    def _get_broker(self):
        try:
            print('connecting to broker')
            self.mqtt = MQTTClient("s", self.pidvars['broker_ip'])
            self.mqtt.connect()
        except OSError:
            print('connecting to broker oserror')
            self.mqtt = False

    def _get_listener(self):
        try:
            self.listener = MQTTClient("l", self.pidvars['broker_ip'], silvia=self)
            self.listener.set_callback(mqtt_callback)
            self.listener.connect()
            self.listener.subscribe(b"config_update")
            self.listener.subscribe(b"webcontrols")
        except OSError:
            self.listener = False

    @property
    def buttons(self):
        self.prev_buttons = self._buttons
        self._buttons = {'brew': self.brew_button.state, 'steam': self.steam_button.state, 'pump': self.pump_button.state}
        return self._buttons

    @property
    def relays(self):
        return {'boiler': self.boiler, 'valve': self.valve, 'pump': self.pump}

    @property
    def auto_off(self):
        return self._auto_off

    @auto_off.setter
    def auto_off(self, value):
        self._auto_off = value

    @property
    def auto_off_timer(self):
        return self._auto_off_timer

    @auto_off_timer.setter
    def auto_off_timer(self, seconds):
        self._last_cmd_time = time.time()
        self._auto_off_timer = value

    @property
    def idle_time(self):
        return time.time() - self._last_cmd_time

    @property
    def temperature(self):
        return self._temperature

    @property
    def temperature_age(self):
        return time.time() - self._last_temp_update

    @temperature.setter
    def temperature(self, value):
        self._temperature = value
        self._last_temp_update = time.time()

    @property
    def shot_timer_enabled(self):
        return self._shot_timer_enabled

    @shot_timer_enabled.setter
    def shot_timer_enabled(self, value):
        self._last_cmd_time = time.time()
        self._shot_timer_enabled = value

    @property
    def shot_timer_duration(self):
        return self._shot_timer_duration

    @shot_timer_duration.setter
    def shot_timer_duration(self, value):
        self._last_cmd_time = time.time()
        self._shot_timer_duration = value

    @property
    def power_ms(self):
        return self._power_ms

    @property
    def power_age(self):
        age = time.time() - self._last_power_update
        return age

    @property
    def setpoint(self):
        return self._setpoint

    @property
    def target(self):
        if self.steaming:
            return self._steam_setpoint
        else:
            return self._setpoint

    @setpoint.setter
    def setpoint(self, value):
        self._last_cmd_time = time.time()
        self._setpoint = value
        self.pid.pid['brew_setpoint'] = self._setpoint

    def calculate_pid(self):
        resp = True
        if time.time() - self._last_temp_update > 10:
            return False
        if self.steaming:
            _setpoint = self._steam_setpoint
        else:
            _setpoint = self._setpoint
        self._power_ms = self.pid(self._temperature, _setpoint, self.enabled)
        self._last_power_update = time.time()
        return True
