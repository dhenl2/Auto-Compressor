import RPi.GPIO as GPIO
import time
import signal
import sys

from RelayController import RelayController

class RepeatList:
    def __init__(self, list_items):
        self.list = list_items
        self.index = 0

    def next(self):
        self.index += 1
        if self.index > len(self.list) - 1:
            self.index = 0

        return self.list[self.index]

def setup():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(3, GPIO.OUT)
    GPIO.setup(5, GPIO.OUT)
    relay_controller = RelayController()
    relay_controller.register(1, 3)
    relay_controller.register(2, 5)

    return relay_controller

def main():
    def stop_GPIO(sig, frame):
        print("Setting all GPIOs to low")
        relay_controller.set_all_low()
        GPIO.cleanup()
        sys.exit(0)

    relay_controller = setup()
    signal.signal(signal.SIGINT, stop_GPIO)
    pins = RepeatList([1, 2])
    while True:
        pin = pins.next()
        print(f"Toggling to pin {pin}")
        relay_controller.set_high(pin)
        time.sleep(0.8)
        relay_controller.set_low(pin)
        time.sleep(2)

if __name__ == "__main__":
    main()