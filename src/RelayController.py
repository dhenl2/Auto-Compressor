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
        print(f"New Relay with {pin} and off state = {off_state}")
        self.pin = pin
        self.state = None
        self.low = get_pin_output(bool(off_state))
        self.high = get_pin_output(not bool(off_state))
        # Set to default state
        GPIO.setup(pin, GPIO.OUT)
        self.off()

    def on(self):
        GPIO.output(self.pin, self.high)
        self.state = 1

    def off(self):
        GPIO.output(self.pin, self.low)
        self.state = 0

class RelayController:
    def __init__(self, logger=None):
        self.registers = {}
        self.max_channels = 0
        self.logger = logger

    def load_config(self, config):
        self.max_channels = config["max_channels"]
        if config.get("registers") is not None:
            self.registers = config["registers"]
        else:
            self.registers = {}
        self.logger.info(
            f"Relay Controller configured as (max_channel, registers), ({self.max_channels}, {self.registers})")

    def init(self):
        self.set_all_relays_off()

    def register(self, name, pin, off_state=0):
        self.logger.info(f"Registering {name} with pin {pin} and off state {off_state}")
        if len(self.registers) <= self.max_channels:
            self.registers[name] = Relay(pin, off_state)
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

    def set_relay_on(self, name):
        self.has_register(name)
        self.logger.trace(f"Setting {name} to on")
        self.registers[name].on()

    def set_relay_off(self, name):
        self.has_register(name)
        self.logger.trace(f"Setting {name} to off")
        self.registers[name].off()

    def set_all_relays_off(self):
        self.logger.trace(f"Setting all relay to off")
        for name in self.registers:
            self.set_relay_off(name)