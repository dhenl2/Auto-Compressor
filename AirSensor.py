from gpiozero import MCP3008
import time
import numpy as np
from scipy.optimize import curve_fit
import os
import json

DIR = "/home/dhenl2/Auto-Compressor"

class CalibrationData:
    def __init__(self, air_pressure):
        self.air_pressure = air_pressure
        self.data = []
        self.avg = -1
        self.var = -1
        self.std = -1

    def read_for(self, sensor, duration, read_num):
        interval = duration / read_num

        while len(self.data) != read_num:
            self.data.append(sensor.value)
            time.sleep(interval)

    def calculate(self):
        np_array = np.array(self.data)
        self.avg = np.average(np_array)
        self.std = np.std(np_array)
        self.var = np.var(np_array)

    def __str__(self):
        print(
            f"Calibration data for {self.air_pressure}\n" +
            f"\tAvg: {self.avg:.2f}\n" +
            f"\tVariance: {self.var:.2f}\n" +
            f"\tStandard Deviation: {self.std:.2f}\n")

    def save(self):
        with open(f"{DIR}/calibrationData/{self.air_pressure}_data.json", "w") as save:
            to_write = {
                "name": self.air_pressure,
                "data": self.data,
                "average": self.avg,
                "variance": self.var,
                "standardDeviation": self.std
            }
            save.write(json.dumps(to_write, indent=2))

class AirSensor:
    def __init__(self, channel=0):
        self.calib_save = "calibration.json"
        self.channel = 0
        self.sensor = MCP3008(channel)
        # y = mx + c
        self.m = None       # gradient
        self.c = None       # offset

        self.units = None

        if not self.has_calibration():
            print("No calibration data found.")
            self.calibrate()
        else:
            self.load_calibration()

    def get_reading(self, x=None, m=None, c=None):
        if x is None:
            x = self.sensor.value
            m = self.m
            c = self.c

        return (m * x) + c

    def get_avg_reading(self, num_samples=20):
        samples = []
        while len(samples) < num_samples:
            samples.append(self.get_reading())

        return np.average(np.array(samples))

    def has_calibration(self):
        return self.calib_save in os.listdir(f"{DIR}/calibrationData")

    def save_calibration(self):
        with open(f"{DIR}/calibrationData/{self.calib_save}", "w") as save_file:
            save_file.write(
                json.dumps({
                    "equation": f"y = {self.m}.x + {self.c}",
                    "m": self.m,
                    "c": self.c,
                    "units": self.units
                }, indent=2)
            )

    def load_calibration(self):
        with open(f"{DIR}/calibrationData/{self.calib_save}", "r") as file:
            json_obj = json.load(file)
            self.m = json_obj["m"]
            self.c = json_obj["c"]
            self.units = json_obj["units"]
            print(f"Loaded previous calibration data of y = {self.m}x + {self.c} ({self.units})")

    def calibrate(self):
        print("Starting calibration...")
        # Get calibration metric
        self.units = input("What unit will this be calibrated in? ").strip()

        air_pressures = []
        readings = []
        print("Time to add inputs")
        while True:
            # Ask for a reading
            user_input = input("Whats the next reading? ")
            if user_input.lower() == "stop":
                print("No more readings to be taken")
                break
            try:
                reading = int(user_input)
            except ValueError:
                print(f"{user_input} is not a integer. Try again...")
                continue

            data_obj = CalibrationData(f"{reading}{self.units}")
            input(f"Set air pressure to {reading}{self.units}. Press enter once ready to read.")

            data_obj.read_for(self.sensor, 3, 30)
            data_obj.calculate()
            print(f"Average reading was {data_obj.avg:.2f}V")
            data_obj.save()

            readings.append(data_obj.avg)
            air_pressures.append(reading)

        print("Calculating linear equation from\n" +
              f"\tx:{readings}\n" +
              f"\ty:{air_pressures}")
        popt, _ = curve_fit(self.get_reading, readings, air_pressures)
        print(f"Calculated m_x = {popt[0]}, c = {popt[1]}")
        self.m = popt[0]
        self.c = popt[1]

def get_reading(x, m, c):
    return (m * x) + c

def main():
    air_sensor = AirSensor()

    while True:
        print(f"Latest reading: {air_sensor.get_avg_reading():.3f}PSI")
        time.sleep(1)
    # print("All done here")
    # y_data = [20, 40, 60]
    # x_data = [
    #     0.428301579547305,
    #     0.3914020517830973,
    #     0.36860446181403683,
    #     0.35319980459208583,
    #     0.33558052434456936,
    #     0.3184497638821038,
    #     0.2943168865005699,
    #     0.27598111056831137,
    #     0.24328285295554472,
    #     0.2288552353036965,
    #     0.19475655430711605,
    #     0.1889268848721707,
    #     0.1628724963361016
    # ]
    # y_data = [
    #     70,
    #     65,
    #     60,
    #     55,
    #     50,
    #     45,
    #     40,
    #     35,
    #     30,
    #     25,
    #     20,
    #     15,
    #     10
    # ]
    # popt, pcov = curve_fit(get_reading, x_data, y_data)
    # print("popt", popt)
    # print("pcov", pcov)
    # sensor = MCP3008(0)
    # print(sensor.value)


if __name__ == "__main__":
    main()