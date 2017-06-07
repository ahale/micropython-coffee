import machine

class Button(object):
    def __init__(self, pin, name, espresso):
        self._pin = pin
        self.name = name
        self.espresso = espresso
        self.gpio = machine.Pin(self._pin, machine.Pin.IN, machine.Pin.PULL_UP)

    @property
    def pin(self):
        return self._pin

    @property
    def value(self):
        return self.gpio.value()

    @property
    def state(self):
        resp = False
        if not self.gpio.value():
            resp = True
        return resp


class Relay(object):
    def __init__(self, pin, name, espresso, pwm=False):
        self.pwm = pwm
        self.name = name
        self._pin = pin
        self.espresso = espresso
        self.gpio = machine.Pin(self._pin, machine.Pin.OUT)

    def update(self):
        if self.espresso.brewing:
            if self.name == 'pump':
                pass
            elif self.name == 'valve':
                pass
        elif self.espresso.pumping:
            if self.name == 'pump':
                pass
            elif self.name == 'valve':
                pass
        else:
            pass

    def on(self):
        # self.espresso.publish('relay_%s' % self.name, True)
        self.gpio.high()

    def off(self):
        # self.espresso.publish('relay_%s' % self.name, False)
        self.gpio.low()

    def toggle(self):
        self.gpio.value(not self.gpio.value)

    @property
    def state(self):
        return self.gpio.value()

    @property
    def value(self):
        return self.gpio.value()

    @property
    def pin(self):
        return self._pin
