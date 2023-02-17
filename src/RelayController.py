import RPi.GPIO as GPIO

class MaxChannelError(Exception):
    pass

class UnknownRegisterError(Exception):
    pass

class Relay:
    def __init__(self, pin):
        self.pin = pin
        self.state = None

    def set_state(self, value):
        self.state = value

class RelayController:
    def __init__(self, registers=None, channels=4):
        if registers is None:
            registers = {}
        if registers:
            self.registers = registers
        else:
            self.registers = {}
        self.max_channels = channels

    def register(self, name, pin):
        if len(self.registers) <= self.max_channels:
            self.registers[name] = Relay(pin)
        else:
            raise MaxChannelError(f"Cannot register any more channels")

    def has_register(self, name):
        if self.registers.get(name, False) is False:
            raise UnknownRegisterError(f"Register by {name} does not exist")

    def delete(self, name):
        self.has_register(name)
        self.registers.pop(name)

    def get(self, name):
        self.has_register(name)
        return self.registers[name]

    def set_high(self, name):
        self.has_register(name)
        GPIO.output(self.registers[name], GPIO.LOW)
        self.registers[name].set_state(1)

    def set_low(self, name):
        self.has_register(name)
        GPIO.output(self.registers[name], GPIO.HIGH)
        self.registers[name].set_state(0)

    def set_all_low(self):
        for name in self.registers:
            self.set_low(name)