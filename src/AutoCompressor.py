#! /usr/bin/python3.9
import configparser
import os
import sys
import signal
import time
from loguru import logger as loguru
from datetime import timedelta
if os.environ.get("environment") == "testing":
    import Mock.GPIO as GPIO
else:
    import RPi.GPIO as GPIO

from src.RelayController import RelayController
from src.AirSensor import AirSensor

CONFIG_FILE = "/home/dhenl2/Auto-Compressor/src/config.ini"
CONFIG_AIR_SENSOR = "Air Sensor"
CONFIG_RELAY_CONTROLLER = "Relay Controller"
CONFIG_COMPRESSOR = "Compressor"
CONFIG_LOGGER = "Logger"

RC_INLET = "inlet"
RC_OUTLET = "outlet"

# Number of moles per m3 of air on average
# https://www.quora.com/How-many-air-molecules-are-present-in-a-cubic-meter-of-air
MOLES_PER_M3 = 0.0042 * (10 ** 3)
# https://www.khanacademy.org/science/physics/thermodynamics/temp-kinetic-theory-ideal-gas-law/a/what-is-the-ideal-gas-law
UNIVERSAL_GAS_CONSTANT = 8.3145

### CALCULATIONS

def determine_mols_pressure_diff(p1, p2, t, flow_rate, logger):
    """
    Determine the number of mols initially after an inflation of t seconds.
    Formula is derived from combining the ideal gas law and the proportionality of
    gasses:

    n = flowRate * p1 * t
        -----------------
             p2 - p1

    Where:
        - flowRate = flow rate of the pump in L/s
        - n = initial number of mols in the system

    :param logger: Logging instance.
    :param p1: Initial pressure reading (Pa).
    :param p2: Post pressure reading after time t (Pa).
    :param t: Time in seconds of inflation.
    :param flow_rate: Flow rate of system (mol/s).
    :return: Initial number of mols.
    """

    result = (flow_rate * p1 * t) / (p2 - p1)
    logger.trace(f"Calculate mols pressure difference: (p1, p2, flow_rate) ({p1}, {p2}, {flow_rate}) = {result}")
    return result

def determine_flow_rate(p1, p2, t, n0, logger):
    result = (n0 * (p2 - p1)) / (p1 * t)
    logger.trace(f"Calculate flow rate: (p1, p2, t, n0) ({p1}, {p2}, {t}, {n0}) = {result}")
    return result

def determine_mols(v, p, T, logger):
    """
    Determine the number of mols using the Idea Gas law.
    Formula is:

    n = p * V
        -----
        R * T

    Where:
    - R = Universal gas constant (m3.Pa.mol^-1.K^-1)
    - T = Temperature (K)
    - n = Number of mols
    - P = Pressure (Pa)

    :param v: Volume to be used (m3).
    :param p: Pressure to be used (Pa).
    :param n: Number of mols to be used.
    :param T: Temperature to be used (K)
    :return: Number of mols given arguments.
    """

    result = (p * v) / (UNIVERSAL_GAS_CONSTANT * T)
    logger.trace(f"Determine mols: (v, p, T) ({v}, {p}, {T}) = {result}")
    return result

def  est_time_to_target(p1, p2, n0, flow_rate, logger):
    """
    Determine the time in seconds to reach target.
    Formula is derived from combining the ideal gas law and the proportionality of
    gasses

    t = n0 * ( p2 - p1 )
        ----------------
          flow_rate * p1

    Where:
        - flow_rate = flow rate of the pump in mol/s

    :param logger: Logging instance.
    :param p1: Initial pressure reading (Pa).
    :param p2: Target pressure reading (Pa).
    :param n0: Initial number of mols (mol)
    :param flow_rate: Flow rate of system (mol/s)
    :return: Estimated time to target pressure.
    """

    result = (n0 * (p2 - p1)) / (flow_rate * p1)
    logger.trace(f"Est. time to target: (p1, p2, n0, flow_rate) ({p1}, {p2}, {n0}, {flow_rate}) = {result}")
    return result

def determine_volume(p, n, T, logger):
    """
    Determine the volume based on the ideal gas law:

    V = n * R * T
        ---------
            p

    Where:
        - R = Universal gas constant (m3.Pa.mol^-1.K^-1)
        - T = Temperature (K)
        - n = Number of mols
        - P = Pressure (Pa)

    :param logger: Logging instance.
    :param p: Pressure to be determined from.
    :param n: Number of mols to be determined from.
    :return: Volume estimation given assumption of temperature
    """

    result = (n * UNIVERSAL_GAS_CONSTANT * T) / p
    logger.trace(f"Determine volume: (p, n, T) ({p}, {n}, {T}) = {result}")
    return result

### CONVERSIONS

def psi_pa(pressure):
    """
    Convert PSI to Pa
    :param pressure: Pressure in PSI to be converted
    :return: Pressure in Pa
    """

    return pressure * 6894.76

def pa_psi(pressure):
    """
    Convert Pa to PSI
    :param pressure: Pressure in Pa to be converted
    :return: Pressure in PSI
    """
    
    return pressure / 6894.76

def celsius_to_kelvin(temp):
    return temp + 273.15

def flow_rate_in_moles(rate, logger):
    """
    Convert rate (L/s) to (mols/s)
    :param logger: Logging instance.
    :param rate: Rate (L/s) to be converted.
    :return: Rate in mols/s
    """

    result = rate * MOLES_PER_M3
    logger.trace(f"{rate} L/s to mols = {result}")
    return result

class AutoCompressor:
    """
    Auto Compressor Object to control the automation of inflation and deflation
    """

    def __init__(self, config_file=CONFIG_FILE):
        self.logger = loguru
        GPIO.cleanup()
        GPIO.setmode(GPIO.BOARD)
        self.config = configparser.ConfigParser()
        self.config.read(config_file)
        self.relay_controller = None
        self.air_sensor = None

        # Compressor variables
        self.init_deflate_dur = None                # (s)
        self.init_inflate_dur = None                # (s)
        self.flow_rate_in = None                    # (L/s)
        self.flow_rate_out_m = None                 # Values m and c for linear function (L/s)
        self.flow_rate_out_c = None
        self.pressure_balance_delay = None          # (s)
        self.error_margin = None                    # (%)
        self.ambient_temperature = None             # (C°)

        self.initialise()

    def exit(self):
        self.logger.info("Stopping Auto Compressor")
        GPIO.cleanup()

    def initialise(self):
        # logger
        self.logger.remove()
        self.logger.add(
            sink=self.config[CONFIG_LOGGER]["file"],
            rotation=timedelta(days=1),
            level=self.config[CONFIG_LOGGER]["level"].upper(),
            colorize=True
        )
        if bool(self.config[CONFIG_LOGGER]["stdout"]):
            self.logger.add(
                sink=sys.stdout,
                level=self.config[CONFIG_LOGGER]["level"].upper()
            )
        self.logger.info("Initialising AutoCompressor...")

        # initialise air sensor
        self.air_sensor = AirSensor(self.logger)
        sensor_config = {
            "m": float(self.config[CONFIG_AIR_SENSOR]["m"]),
            "c": float(self.config[CONFIG_AIR_SENSOR]["c"]),
            "units": self.config[CONFIG_AIR_SENSOR]["units"],
            "channel": int(self.config[CONFIG_AIR_SENSOR]["AO_channel"])
        }
        self.air_sensor.load_config(sensor_config)

        # initialise relay controller
        self.relay_controller = RelayController(self.logger)
        relay_config = {
            "max_channels": int(self.config[CONFIG_RELAY_CONTROLLER]["max_channels"]),
        }
        if self.config[CONFIG_RELAY_CONTROLLER].get("registers") is not None:
            # Load registers from config
            relay_config["registers"] = self.config[CONFIG_RELAY_CONTROLLER]["registers"]
            self.relay_controller.load_config(relay_config)
        else:
            self.relay_controller.load_config(relay_config)
            self.relay_controller.register(
                RC_INLET,
                int(self.config[CONFIG_RELAY_CONTROLLER]["inlet_pin"]),
                int(self.config[CONFIG_RELAY_CONTROLLER]["inlet_off_state"])
            )
            self.relay_controller.register(
                RC_OUTLET,
                int(self.config[CONFIG_RELAY_CONTROLLER]["outlet_pin"]),
                int(self.config[CONFIG_RELAY_CONTROLLER]["outlet_off_state"])
            )

        self.relay_controller.init()

        # compressor variables
        self.init_inflate_dur = float(self.config[CONFIG_COMPRESSOR]["init_check_inflate"])
        self.init_deflate_dur = float(self.config[CONFIG_COMPRESSOR]["init_check_deflate"])
        self.flow_rate_in = flow_rate_in_moles(float(self.config[CONFIG_COMPRESSOR]["flow_rate_in"]), self.logger)
        self.flow_rate_out_m = float(self.config[CONFIG_COMPRESSOR]["flow_rate_out_m"])
        self.flow_rate_out_c = float(self.config[CONFIG_COMPRESSOR]["flow_rate_out_c"])
        self.error_margin = float(self.config[CONFIG_COMPRESSOR]["error_margin"])
        self.pressure_balance_delay = float(self.config[CONFIG_COMPRESSOR]["pressure_balance_delay"])

        # assumptions
        self.ambient_temperature = celsius_to_kelvin(float(self.config[CONFIG_COMPRESSOR]["temperature"]))

        self.logger.info("Finished initialising")

    def get_out_flow_rate(self, curr_p):
        """
        Get the current flow rate of the output hardware.
        :param curr_p: Current pressure of the system (Pa)
        :return: Current expected flow rate given the differential pressure.
        """

        # TODO this might be the problem child
        # Need to look into using PA in calculation of flow rate in L/s
        # Need to look into linear grab made using m and c. See if its suitable for PA inputs
        return flow_rate_in_moles(-((self.flow_rate_out_m * curr_p) + self.flow_rate_out_c), self.logger)

    def pressure_within_margin(self, target, p_curr):
        return (target - self.error_margin) <= p_curr <= (target + self.error_margin)

    def reach_target(self, target):
        units = self.air_sensor.units
        p_curr = self.check_pressure(raw=True)
        self.logger.info(f"Inflate/deflate to target {target}{units} from {round(p_curr, 2)}{units}")
        if target is None:
            raise Exception(f"Target {self.air_sensor.units} not given")
        elif round(p_curr) == target:
            self.logger.info(f"Current reading of {round(p_curr)}{units} is already at target of {target}{units}")
            return
        target_pascal = psi_pa(target)

        # determine initial mol value
        p_curr_pascal = psi_pa(p_curr)
        init_mols = self.determine_current_mol(p_curr_pascal, target_pascal)
        # determine current volume based off estimation
        p_curr_pascal = psi_pa(self.check_pressure(raw=True))
        self.logger.trace(f"Current pressure {p_curr} Pa")
        volume = determine_volume(p_curr_pascal, init_mols, self.ambient_temperature, self.logger)
        self.logger.debug(f"Estimated current mols as {init_mols} and volume as {volume} m3")

        # time to start inflating/deflating
        p_curr = self.check_pressure()
        self.logger.info(f"Time to start reaching the target pressure: {p_curr}{units} -> {target}{units}")
        time_taken = 0
        rounds = 0
        mol_curr = None
        while True:
            p_curr = self.check_pressure(raw=True)
            p_curr_pascal = psi_pa(p_curr)
            self.logger.info(f"Currently at {round(p_curr)}{units}")
            mol_curr = determine_mols(volume, p_curr_pascal, self.ambient_temperature, self.logger)

            # inflation/deflation controls
            flow_rate = None
            apply_change = None
            if self.pressure_within_margin(target, p_curr):
                self.logger.info(f"Current pressure {p_curr}{units} is within threshold of {target}{units} +/- "
                                 f"{self.error_margin}")
                self.logger.info(f"Target {target}{units} reached in {round(time_taken, 2)}s and {rounds} rounds")
                break
            elif p_curr > target:
                flow_rate = self.get_out_flow_rate(p_curr_pascal)
                apply_change = self.deflate
            else:
                flow_rate = self.flow_rate_in
                apply_change = self.inflate

            est_time = est_time_to_target(p_curr_pascal, target_pascal, mol_curr, flow_rate, self.logger)
            self.logger.debug(f"Estimated time to target is {round(est_time)}s")

            # correct tyre pressure
            apply_change(est_time)
            time_taken += est_time
            rounds += 1

    def determine_current_mol(self, p_curr, p_target, duration=None):
        """
        Determine the current mol value of the system to be inflated/deflated
        :param p_curr: Current pressure in Pa.
        :param p_target: Target pressure in Pa.
        :return: Number of mols
        """

        flow_rate = None
        t = None
        if p_curr > p_target:
            self.logger.trace(f"Performing initial estimation using deflation for {self.init_deflate_dur}s")
            flow_rate = self.get_out_flow_rate(p_curr)
            if duration:
                t = duration
            else:
                t = self.init_deflate_dur
            self.deflate(t)
        else:
            self.logger.trace(f"Performing initial estimation using inflation for {self.init_inflate_dur}s")
            flow_rate = self.flow_rate_in
            if duration:
                t = duration
            else:
                t = self.init_inflate_dur
            self.inflate(t)

        p_now = psi_pa(self.check_pressure(raw=True))
        n0 = determine_mols_pressure_diff(p_curr, p_now, t, flow_rate, self.logger)

        return n0 + (flow_rate * t)

    def inflate(self, duration, close=True):
        self.open_inlet()
        time.sleep(duration)

        if close:
            self.close_inlet()
            # Wait for pressure to stabilise before finishing
            time.sleep(self.pressure_balance_delay)

    def deflate(self, duration, close=True):
        self.open_outlet()
        time.sleep(duration)

        if close:
            self.close_outlet()
            # Wait for pressure to stabilise before finishing
            time.sleep(self.pressure_balance_delay)

    def check_pressure(self, raw=False):
        flow_changed = False
        if self.is_outlet_open():
            self.close_outlet()
            flow_changed = True
        if self.is_inlet_open():
            self.close_inlet()
            flow_changed = True

        if flow_changed:
            # allow pressure to settle
            time.sleep(self.pressure_balance_delay)

        pressure = self.air_sensor.read_sensor()
        if raw:
            return pressure
        else:
            return round(pressure)

    def open_inlet(self):
        self.relay_controller.set_relay_on(RC_INLET)

    def close_inlet(self):
        self.relay_controller.set_relay_off(RC_INLET)

    def open_outlet(self):
        self.relay_controller.set_relay_on(RC_OUTLET)

    def close_outlet(self):
        self.relay_controller.set_relay_off(RC_OUTLET)

    def is_outlet_open(self):
        return self.relay_controller.get_state(RC_OUTLET) == 1

    def is_inlet_open(self):
        return self.relay_controller.get_state(RC_INLET) == 1

    def is_outlet_closed(self):
        return self.relay_controller.get_state(RC_INLET) == 0

    def calibrate_flow_rate(self, start_pressure, final_pressure, interval):
        self.logger.info("Starting calibration for output flow rate")
        p_curr = self.check_pressure(raw=True)
        self.logger.info(f"Starting pressure is {round(p_curr)} {self.air_sensor.units}")

        # determine initial mol value
        p_curr_pascal = psi_pa(p_curr)
        init_mols = self.determine_current_mol(p_curr_pascal, psi_pa(p_curr + 5), 5)
        # determine current volume based off estimation
        p_curr_pascal = psi_pa(self.check_pressure(raw=True))
        self.logger.trace(f"Current pressure {p_curr} Pa")
        volume = determine_volume(p_curr_pascal, init_mols, self.ambient_temperature, self.logger)
        self.logger.debug(f"Estimated current mols as {init_mols} and volume as {volume} m3")

        if self.pressure_within_margin(start_pressure, p_curr):
            self.reach_target(start_pressure)


        self.logger.info(f"Performing deflation analysis every {interval}s till {final_pressure} {self.air_sensor.units}")

        p_readings = []         # PA
        flow_r_readings = []    # Flow rate (L/s)

        p_curr = self.check_pressure(raw=True)
        p_curr_pascal = psi_pa(p_curr)
        p_prev_pascal = None
        while p_curr > final_pressure:
            p_prev_pascal = p_curr_pascal
            self.deflate(interval)

            p_curr = self.check_pressure(raw=True)
            p_curr_pascal = psi_pa(p_curr)
            mol_curr = determine_mols(volume, p_curr_pascal, self.ambient_temperature, self.logger)
            flow_rate = determine_flow_rate(p_prev_pascal, p_curr_pascal, interval, mol_curr, self.logger)

            p_readings.append(p_curr_pascal)
            flow_r_readings.append(flow_rate)



def main():

    compressor = AutoCompressor()

    def signal_handler(sig, frame):
        compressor.exit()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        target = 44
        compressor.logger.info(f"Attempting to reach a target of {target}PSI")
        time.sleep(1)
        compressor.reach_target(target)
    except Exception as error:
        compressor.logger.error("Encountered an error")
        compressor.logger.exception(error)
        compressor.exit()
    compressor.exit()


if __name__ == "__main__":
    main()