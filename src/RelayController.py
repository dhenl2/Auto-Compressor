import RPi.GPIO as GPIO

def get_pin_output(state):
    if state:
        return GPIO.HIGH
    else:
        return GPIO.LOW

class MaxChannelError(Exception):
    pass

class UnknownRegisterError(Exception):
    pass

class Relay:
    def __init__(self, pin, off_state):
        self.pin = pin
        self.state = None
        self.low = get_pin_output(bool(off_state))
        self.high = get_pin_output(not bool(off_state))

    def set_high(self):
        GPIO.output(self.pin, self.high)
        self.state = 1

    def set_low(self):
        GPIO.output(self.pin, self.low)
        self.state = 0

class RelayController:
    def __init__(self, registers=None, channels=4):
        if registers is None:
            registers = {}
        if registers:
            self.registers = registers
        else:
            self.registers = {}
        self.max_channels = channels

    def register(self, name, pin, off_state=0):
        if len(self.registers) <= self.max_channels:
            self.registers[name] = Relay(pin)
        else:
            raise MaxChannelError(f"Cannot register any more channels")

    def has_register(self, name):
        if self.registers.get(name, False) is False:
            raise UnknownRegisterError(f"Register by name {name} does not exist")

    def delete(self, name):
        self.has_register(name)
        self.registers.pop(name)

    def get_state(self, name):
        self.has_register(name)
        return self.registers[name].state

    def set_high(self, name):
        self.has_register(name)
        self.registers[name].set_high()

    def set_low(self, name):
        self.has_register(name)
        self.registers[name].set_low(0)

    def set_all_low(self):
        for name in self.registers:
            self.set_low(name)