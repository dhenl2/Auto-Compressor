import configparser
import time
from loguru import logger
from datetime import timedelta

from AirSensor import AirSensor
from RelayController import RelayController

CONFIG_FILE = "/home/dhenl2/AutoCompressor/config.ini"
CONFIG_AIR_SENSOR = "Air Sensor"
CONFIG_RELAY_CONTROLLER = "Relay Controller"
CONFIG_COMPRESSOR = "Compressor"
CONFIG_LOGGER = "Logger"

RC_INLET = "inlet"
RC_OUTLET = "outlet"

# Number of moles per m3 of air on average
# https://www.quora.com/How-many-air-molecules-are-present-in-a-cubic-meter-of-air
MOLES_PER_M3 = 0.0042 * (10 ** 3)

def flow_rate_in_moles(rate):
    """
    Convert rate (L/s) to (mols/s)
    :param rate: Rate (L/s) to be converted
    :return: Rate in mols/s
    """

    return rate * MOLES_PER_M3

def determine_initial_mols(p1, p2, t, flow_rate):
    """
    Determine the number of mols initially after an inflation of t seconds.
    Formula is derived from combining the ideal gas law and the proportionality of
    gasses:

    n = flowRate * p1 * t
        -----------------
             p1 - p2

    Where:
        - flowRate = flow rate of the pump in L/s
        - n = initial number of mols in the system

    :param p1: Initial pressure reading (Pa)
    :param p2: Post pressure reading after time t (Pa)
    :param t: Time in seconds of inflation
    :param flow_rate: Flow rate of system (mol/s)
    :return: Initial number of mols
    """

    return (flow_rate * p1 * t) / (p1 - p2)


def est_time_to_target(p1, p2, n0, flow_rate):
    """
    Determine the time in seconds to reach target.
    Formula is derived from combining the ideal gas law and the proportionality of
    gasses

    t = n0 * ( p2 - p1 )
        ----------------
          flow_rate * p1

    Where:
        - flow_rate = flow rate of the pump in L/s

    :param p1: Initial pressure reading (Pa).
    :param p2: Target pressure reading (Pa).
    :param n0: Initial number of mols (mol)
    :param flow_rate: Flow rate of system (mol/s)
    :return: Estimated time to target pressure.
    """

    return (n0 * (p2 - p1)) / (flow_rate * p1)


class AutoCompressor:
    """
    Auto Compressor Object to control the automation of inflation and deflation
    """

    def __init__(self, config_file=CONFIG_FILE):
        self.config = configparser.ConfigParser().read(config_file)
        self.relay_controller = RelayController()
        self.air_sensor = None
        self.logger = logger

        # Compressor variables
        self.init_deflate_dur = None
        self.init_inflate_dur = None
        self.flow_rate_in = None
        self.flow_rate_out = None
        self.on_delay = None

        self.initialise()

    def initialise(self):
        self.logger.info("Initialising AutoCompressor...")

        # initialise air sensor
        sensor_config = {
            "m": self.config[CONFIG_AIR_SENSOR]["m"],
            "c": self.config[CONFIG_AIR_SENSOR]["c"],
            "units": self.config[CONFIG_AIR_SENSOR]["units"]
        }
        self.air_sensor = AirSensor(sensor_config, self.config[CONFIG_AIR_SENSOR]["AO_channel"])

        # initialise relay controller
        self.relay_controller.register(RC_INLET, self.config[CONFIG_RELAY_CONTROLLER]["inlet_pin"])
        self.relay_controller.register(RC_OUTLET, self.config[CONFIG_RELAY_CONTROLLER]["outlet_pin"])

        # compressor variables
        self.init_inflate_dur = self.config[CONFIG_COMPRESSOR]["init_check_inflate"]
        self.init_deflate_dur = self.config[CONFIG_COMPRESSOR]["init_check_deflate"]
        self.flow_rate_in = flow_rate_in_moles(float(self.config[CONFIG_COMPRESSOR]["flow_rate_in"]))
        self.flow_rate_out = self.config[CONFIG_COMPRESSOR]["flow_rate_out"]
        self.on_delay = self.config[CONFIG_COMPRESSOR]["on_delay"]

        # logger
        logger.remove()
        logger.add(
            sink=self.config[CONFIG_LOGGER]["file"],
            rotation=timedelta(day=1),
            level=self.config[CONFIG_LOGGER]["level"],
            colourize=True
        )
        self.logger.info("Finished initialising")

    def reach_target(self, target):
        units = self.air_sensor.units
        self.logger(f"Inflate/deflate to target {target}{units}")
        if target is None:
            raise Exception(f"Target {self.air_sensor.units} not given")

        p_current = self.check_pressure(raw=True)

        if round(p_current) == target:
            self.logger(f"Current reading of {round(p_current)}{units} is already at target of {target}{units}")
            return

        # perform volume estimation for estimating time to target inflation
        init_dur = None
        flow_rate = None
        if p_current > target:
            self.logger.trace("Performing initial estimation using deflation")
            init_dur = self.init_deflate_dur
            # TODO creation function to determine outflow based on current pressure outlet port size
            flow_rate = self.flow_rate_out
            self.deflate(self.init_deflate_dur)
        else:
            self.logger.trace("Performing initial estimation using inflation")
            init_dur = self.init_inflate_dur
            flow_rate = self.flow_rate_in
            self.inflate(self.init_inflate_dur)
        p_now = self.check_pressure(raw=True)
        c_vol = self.determine_volume(p_current, p_now, flow_rate, init_dur)
        self.logger.debug(f"Estimated current volume as {c_vol}")
        time_to_target = self.est_time_target(p_now, target, flow_rate, c_vol)
        self.logger.debug(f"Estimated time to target is {time_to_target}s")

    def determine_outlet_flow(self):
        pass


    def inflate(self, duration, close=True):
        self.open_inlet()
        time.sleep(self.on_delay + duration)

        if close:
            self.close_inlet()

    def deflate(self, duration, close=True):
        self.open_outlet()
        time.sleep(duration)

        if close:
            self.close_outlet()

    def check_pressure(self, raw=False):
        self.close_outlet()
        time.sleep(1)       # allow pressure to settle
        pressure = self.air_sensor.read_sensor()

        if raw:
            return pressure
        else:
            return round(pressure)

    def release_pressure(self, duration=10):
        self.open_inlet()
        time.sleep(duration)
        self.close_inlet()

    def open_inlet(self):
        self.relay_controller.set_low(RC_INLET)

    def close_inlet(self):
        self.relay_controller.set_high(RC_INLET)

    def open_outlet(self):
        self.relay_controller.set_low(RC_OUTLET)

    def close_outlet(self):
        self.relay_controller.set_high(RC_OUTLET)