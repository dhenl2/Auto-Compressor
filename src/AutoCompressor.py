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
# https://www.khanacademy.org/science/physics/thermodynamics/temp-kinetic-theory-ideal-gas-law/a/what-is-the-ideal-gas-law
UNIVERSAL_GAS_CONSTANT = 8.3145

def flow_rate_in_moles(rate):
    """
    Convert rate (L/s) to (mols/s)
    :param rate: Rate (L/s) to be converted
    :return: Rate in mols/s
    """

    return rate * MOLES_PER_M3

def determine_mols_pressure_diff(p1, p2, t, flow_rate):
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

def determine_mols(v, p, n, T):
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

    return (p * v) / (UNIVERSAL_GAS_CONSTANT * T)

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

def determine_volume(p, n, T):
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

    :param p: Pressure to be determined from.
    :param n: Number of mols to be determined from.
    :return: Volume estimation given assumption of temperature
    """

    return (n * UNIVERSAL_GAS_CONSTANT * T) / p

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
        self.init_deflate_dur = None                # (s)
        self.init_inflate_dur = None                # (s)
        self.flow_rate_in = None                    # (L/s)
        self.flow_rate_out = None                   # (L/s)
        self.on_delay = None                        # (s)
        self.pressure_balance_delay = None          # (s)
        self.error_margin = None                    # (%)
        self.ambient_temperature = None             # (C°)

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
            "m": float(self.config[CONFIG_AIR_SENSOR]["m"]),
            "c": float(self.config[CONFIG_AIR_SENSOR]["c"]),
            "units": float(self.config[CONFIG_AIR_SENSOR]["units"])
        }
        self.air_sensor = AirSensor(sensor_config, self.config[CONFIG_AIR_SENSOR]["AO_channel"])

        # initialise relay controller
        self.relay_controller.register(RC_INLET, int(self.config[CONFIG_RELAY_CONTROLLER]["inlet_pin"]))
        self.relay_controller.register(RC_OUTLET, int(self.config[CONFIG_RELAY_CONTROLLER]["outlet_pin"]))

        # compressor variables
        self.init_inflate_dur = float(self.config[CONFIG_COMPRESSOR]["init_check_inflate"])
        self.init_deflate_dur = float(self.config[CONFIG_COMPRESSOR]["init_check_deflate"])
        self.flow_rate_in = float(flow_rate_in_moles(float(self.config[CONFIG_COMPRESSOR]["flow_rate_in"])))
        self.flow_rate_out = float(self.config[CONFIG_COMPRESSOR]["flow_rate_out"])
        self.on_delay = float(self.config[CONFIG_COMPRESSOR]["on_delay"])
        self.error_margin = float(self.config[CONFIG_COMPRESSOR]["error_margin"])
        self.pressure_balance_delay = float(self.config[CONFIG_COMPRESSOR]["pressure_balance_delay"])

        # assumptions
        self.ambient_temperature = celsius_to_kelvin(float(self.config[CONFIG_COMPRESSOR]["temperature"]))

        self.logger.info("Finished initialising")

    def reach_target(self, target):
        units = self.air_sensor.units
        p_curr = self.check_pressure(raw=True)
        self.logger(f"Inflate/deflate to target {target}{units} from {p_curr}{units}")
        if target is None:
            raise Exception(f"Target {self.air_sensor.units} not given")
        elif round(p_curr) == target:
            self.logger(f"Current reading of {round(p_curr)}{units} is already at target of {target}{units}")
            return

        # determine required values mol and volume
        init_mols = self.determine_current_mol(psi_pa(p_curr), psi_pa(target))
        p_curr = psi_pa(self.check_pressure(raw=True))
        volume = determine_volume(p_curr, init_mols, self.ambient_temperature)
        self.logger.debug(f"Estimated current mols as {init_mols} and volume as {volume}m3")

        # time to start inflating/deflating
        self.logger(f"Time to start reaching the target pressure: {self.check_pressure()}{units} -> {target}{units}")
        time_taken = 0
        rounds = 0
        mol_curr = None
        while True:
            p_curr = psi_pa(self.check_pressure(raw=True))
            self.logger(f"Currently at {round(p_curr)}{units}")
            mol_curr = determine_mols(volume, psi_pa(p_curr), mol_curr, self.ambient_temperature)

            # inflation/deflation controls
            flow_rate = None
            apply_change = None
            if (target * (1 - self.error_margin)) <= p_curr <= (target * (1 + self.error_margin)):
                self.logger.info(f"Current pressure {p_curr}{units} is within threshold of {self.error_margin}%" +
                                 f" of target {target}{units}")
                self.logger.info(f"Target {target}{units} reached in {time_taken}s and {rounds} rounds")
                break
            elif p_curr > target:
                flow_rate = self.flow_rate_out
                apply_change = self.deflate
            else:
                flow_rate = self.flow_rate_in
                apply_change = self.inflate

            est_time = est_time_to_target(psi_pa(p_curr), psi_pa(target), mol_curr, flow_rate)
            self.logger.debug(f"Estimated time to target is {est_time}s")

            # correct tyre pressure
            apply_change(est_time)
            time_taken += est_time
            rounds += 1

    def determine_current_mol(self, p_curr, p_target):
        """
        Determine the current mol value of the system to be inflated/deflated
        :return: Number of mols
        """

        flow_rate = None
        t = None
        if p_curr > p_target:
            self.logger.trace(f"Performing initial estimation using deflation for {self.init_deflate_dur}s")
            flow_rate = self.flow_rate_out
            t = self.init_deflate_dur
            self.deflate(t)
        else:
            self.logger.trace(f"Performing initial estimation using inflation for {self.init_inflate_dur}s")
            flow_rate = self.flow_rate_in
            t = self.init_inflate_dur
            self.inflate(t)

        n0 = determine_mols_pressure_diff(p_curr, p_target, t, flow_rate)

        return n0 + (flow_rate * t)

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
        self.relay_controller.set_low(RC_INLET)

    def close_inlet(self):
        self.relay_controller.set_high(RC_INLET)

    def open_outlet(self):
        self.relay_controller.set_low(RC_OUTLET)

    def close_outlet(self):
        self.relay_controller.set_high(RC_OUTLET)

    def is_outlet_open(self):
        return self.relay_controller.get_state(RC_OUTLET) == 1

    def is_outlet_closed(self):
        return self.relay_controller.get_state(RC_OUTLET) == 0

    def is_inlet_open(self):
        return self.relay_controller.get_state(RC_INLET) == 1

    def is_outlet_closed(self):
        return self.relay_controller.get_state(RC_INLET) == 0

def main():
    compressor = AutoCompressor()

if __name__ == "__main__":
    main()