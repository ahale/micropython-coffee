import gc
import time
import json
import socket
import machine
import onewire, ds18x20

DEBUG = False

if not DEBUG:
    dat = machine.Pin(12)
    ds = ds18x20.DS18X20(onewire.OneWire(dat))
    roms = ds.scan()
else:
    roms = []

def request_temp(loop, silvia):
    if not DEBUG:
        ds.convert_temp()
    loop.call_later_ms_(750, read_temp, (loop, silvia))

def read_temp(loop, silvia):
    if not DEBUG:
        silvia.temperature = float(ds.read_temp(roms[0]))
    else:
        silvia.temperature = 33.3
    loop.call_later_ms_(250, request_temp, (loop, silvia))

def config_update_handler(payload, silvia):
    if 'setpoint' in payload.keys():
        silvia.setpoint = float(payload['setpoint'])
        print('set setpoint to %s' % payload['setpoint'])

    if 'steam_setpoint' in payload.keys():
        silvia._steam_setpoint = float(payload['steam_setpoint'])
        print('set steam_setpoint to %s' % payload['steam_setpoint'])

    if 'pid_p' in payload.keys():
        silvia.pid.pid['k_param'] = float(payload['pid_p'])
        print('set pid_p to %s' % payload['pid_p'])

    if 'pid_i' in payload.keys():
        silvia.pid.pid['i_param'] = float(payload['pid_i'])
        print('set pid_i to %s' % payload['pid_i'])

    if 'pid_d' in payload.keys():
        silvia.pid.pid['d_param'] = float(payload['pid_d'])
        print('set pid_d to %s' % payload['pid_d'])

    if 'shot_timer_enabled' in payload.keys():
        silvia.shot_timer_enabled = bool(payload['shot_timer_enabled'])
        print('set shot_timer_enabled to %s' % payload['shot_timer_enabled'])

    if 'shot_timer_duration' in payload.keys():
        silvia.shot_timer_duration = int(payload['shot_timer_duration'])
        print('set shot_timer_duration to %s' % payload['shot_timer_duration'])

    silvia.saveconfig()
    self._last_cmd_time = time.time()

def webcontrols_handler(payload, silvia):
    print('webcontrols_handler')
    print(payload)
    if 'buttons' in payload.keys():
        if 'brew' in payload['buttons']:
            pass
        elif 'pump' in payload['buttons']:
            pass
        elif 'steam' in payload['buttons']:
            if payload['buttons']['steam']:
                silvia.steaming = True
                silvia.steam_start_time = time.time()
            else:
                silvia.steaming = False
        silvia._last_cmd_time = time.time()

def mqtt_callback(topic, msg, silvia):
    # try:
    payload = json.loads(msg)
    if topic == b'config_update':
        config_update_handler(payload['config_update'], silvia)
    elif topic == b'webcontrols':
        webcontrols_handler(payload, silvia)
    # except:
    #     print((topic, msg))

def check_mqtt(loop, silvia):
    if not silvia.listener:
        silvia._get_listener()
    else:
        silvia.listener.check_msg()
    loop.call_later_ms_(100, check_mqtt, (loop, silvia))

def calculate_pid(loop, silvia):
    resp = silvia.calculate_pid()
    loop.call_later_ms_(1000, calculate_pid, (loop, silvia))
    gc.collect()

def status(loop, silvia):
    if time.time() > silvia.steam_start_time + 300:
        silvia.steaming = False

    # if silvia.idle_time > silvia.auto_off_timer:
    #     silvia.enabled = False

    _status = {}
    _status['ts'] = time.time()
    _status['pid'] = silvia.pid.pid
    _status['pid']['enabled'] = silvia.enabled
    _status['data'] = {"temperature": silvia.temperature,
                       "power_ms": silvia.power_ms,
                       "idle_time": silvia.idle_time,
                       "auto_off_timer_enabled": silvia.auto_off,
                       "auto_off_timer_duration": silvia.auto_off_timer,
                       "shot_timer_enabled": silvia.shot_timer_enabled,
                       "shot_timer_duration": silvia.shot_timer_duration,
                       "steaming": bool(silvia.steaming),
                       }
    _status['buttons'] = silvia.buttons
    _status['relays'] = {"pump": bool(silvia.pump.value),
                         "valve": bool(silvia.valve.value),
                         "boiler": bool(silvia.boiler.value),
                         }
    silvia.publish('status', json.dumps(_status))
    loop.call_later_ms_(1000, status, (loop, silvia))

def run_boiler(loop, silvia):
    if silvia.steaming:
        if silvia.temperature < silvia._steam_setpoint:
            silvia.boiler.on()
    else:
        millis = silvia.power_ms
        if silvia.power_age > 10:
            millis = 0
        if silvia.temperature > silvia.target:
            millis = 0
        if millis == 1000:
            silvia.boiler.on()
        elif millis == 0:
            silvia.boiler.off()
        else:
            interval = 1000 - millis
            silvia.boiler.on()
            loop.call_later_ms_(interval, boiler_off, (loop, silvia))
    loop.call_later_ms_(1000, run_boiler, (loop, silvia))

def boiler_off(loop, silvia):
    silvia.boiler.off()

def start_shot_timer(loop, silvia):
    if silvia.shot_timer_enabled:
        loop.call_later(silvia._shot_timer_duration, read_buttons, (loop, silvia))

def stop_shot_timer(loop, silvia):
    print('stop shot timer!')

def update_relays(loop, silvia):
    silvia.valve.update()
    silvia.pump.update()
    loop.call_later_ms_(60, update_relays, (loop, silvia))

def read_buttons(loop, silvia):
    prev_buttons = silvia.prev_buttons
    curr_buttons = silvia.buttons
    try:
        changes = {x: curr_buttons[x] for x in curr_buttons if curr_buttons[x] != prev_buttons[x]}
        if len(changes) > 0:
            print('changes: %s' % changes)
            # if time.time() - silvia.prev_button_change_time > 0:
            try:
                if changes['pump'] == True:
                    silvia.pumping = True
                    silvia._last_cmd_time = time.time()
                    silvia.pump.on()
                elif changes['pump'] == False:
                    silvia.pumping = False
                    silvia._last_cmd_time = time.time()
                    silvia.pump.off()
            except KeyError:
                pass
            try:
                if changes['brew'] == True:
                    silvia._last_cmd_time = time.time()
                    silvia.valve.on()
                    silvia.pump.on()
                elif changes['brew'] == False:
                    silvia.brewing = False
                    silvia._last_cmd_time = time.time()
                    silvia.valve.off()
                    silvia.pump.off()
            except KeyError:
                pass
            try:
                if changes['steam'] == True:
                    silvia.steaming = True
                    silvia.steam_start_time = time.time()
                    silvia._last_cmd_time = time.time()
                elif changes['steam'] == False:
                    silvia.steaming = False
                    silvia._last_cmd_time = time.time()
            except KeyError:
                pass
            silvia.prev_button_change_time = time.time()
    except KeyError:
        pass
    loop.call_later_ms_(200, read_buttons, (loop, silvia))
