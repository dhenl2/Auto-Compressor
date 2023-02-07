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

class AutoCompressor:

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
        # logger
        logger.remove()
        logger.add(
            sink=self.config[CONFIG_LOGGER]["file"],
            rotation=timedelta(day=1),
            level=self.config[CONFIG_LOGGER]["level"],
            colourize=True
        )
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
        self.flow_rate_in = self.confg[CONFIG_COMPRESSOR]["flow_rate_in"]
        self.flow_rate_out = self.confg[CONFIG_COMPRESSOR]["flow_rate_out"]
        self.on_delay = self.config[CONFIG_COMPRESSOR]["on_delay"]

        self.logger.info("Finished initialising")

    def reach_target(self, target):
        units = self.air_sensor.units
        self.logger.info(f"Inflate/deflate to target {target}{units}")
        if target is None:
            raise Exception(f"Target {self.air_sensor.units} not given")

        p_current = self.check_pressure(raw=True)

        if round(p_current) == target:
            self.logger.info(f"Current reading of {round(p_current)}{units} is already at target of {target}{units}")
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

    def est_time_target(self, p_cur, p_tar, flow_vel, vol):
        flow_rate = 0.001 * flow_vel

        return (1 / flow_rate) * (((p_cur * vol) / p_tar) - vol)

    def determine_outlet_flow(self):
        pass

    def determine_volume(self, p1, p2, flow_vel, t):
        self.logger.debug(f"Determining volume with p1={p1}, p2={p2} after {t}s")
        flow_rate = 0.001 * flow_vel     # L/s -> m3/s
        added_vol = flow_rate * t
        v1 = added_vol / ((p1 / p2) - 1)
        v2 = v1 + added_vol
        self.logger.trace(f"Volume calculations\n\tv1: {v1}\n\tv2: {v2}")

        return v2

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