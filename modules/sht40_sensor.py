# SHT40 sensor driver based on sht4x.py library

'''
SHT40 comes with an internal heater included in the sensor and it can be used while taking measurements.
Its uses can be:
    - to remove condensed water in the sensor
    - in a periodic mode for better operation in high humidity conditions
    - etc
Note: The heater is designed for a maximum duty cycle of 10%, meaning the total heater-on-time
should not be longer than 10% of the sensor’s lifetime.
The maximum on-time of the heater commands is 1 second in order to prevent overheating of the
sensor by unintended usage of the heater. Thus, there is no dedicated command to turn off the
heater.

Thus, we get 2 modes of operation for SHT40 sensor:
1. without the heater:
            - sensor works normally and gives temp, hum measurements together when requested
            - it has 3 sub-modes [high precision, medium precision, low precision]
2. with the heater:
            - when a measurement is requested, the heater turns on and then reads the temp,
              hum after some time and then the heater is turned off and the measurements are available
            - the heater can be turned on with 3 different power modes and with 2 different on time,
              the power modes are 200mW, 110 mW and 20 mW and the on times are 1 sec and 0.1 sec;
              thus, we get a total of 6 different sub-modes for this type of operation
            - in heater mode, the precision for all sub-modes is high precision by default
            - the maximum heater on time is 1 sec, after which it already turns off

Thus, in total we get nine different working modes for the SHT40:
                            MODE                                   |   COMMAND   |   SENSOR MEASUREMENT DURATION (sec)
1.  No Heater, High Precision                                           0xFD              0.01
2.  No Heater, Medium Precision                                         0xF6              0.005
3.  No Heater, Low Precision                                            0xE0              0.002
4.  With Heater(Power 200mW), ON Time(1 sec), High Precision            0x39              1.1
5.  With Heater(Power 200mW), ON Time(0.1 sec), High Precision          0x32              0.11
6.  With Heater(Power 110mW), ON Time(1 sec), High Precision            0x2F              1.1
7.  With Heater(Power 110mW), ON Time(0.1 sec), High Precision          0x24              0.11
8.  With Heater(Power 20mW), ON Time(1 sec), High Precision             0x1E              1.1
9.  With Heater(Power 20mW), ON Time(0.1 sec), High Precision           0x15              0.11

NOTE: - Use heater very sparingly and only if absolutely needed because its duty cycle is only 10%
        as mentioned earlier and it may make the temp reading a little higher than actual. Also, it
        damage the sensor if used in high temperature environment.
      - In normal use, just simply use the non-heater mode which is set by default.
      - In our library, the time delay between the start of the measurement reading [
        initiated by giving the respective command to the sensor] and end of the measurement[
        i.e. reading the measurement from the sensor] are a little higher than specified in
        the datasheet as mentioned above. But they can not be lower than these.
      - In our library the default mode for sensor is set to 1. No Heater, High Precision
      - Read the datasheet for any more information.
'''

import time
from machine import SoftI2C, Pin
'''
# to enable imports from a subfolder named 'modules'
import sys
sys.path.append('/modules')
'''
import sht4x  # Import the sht4x library

from simple_logging import Logger

class SHT40:
    def __init__(self, i2c_scl, i2c_sda, i2c_freq=100000, i2c_address=0x44,
                 logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
        """
        Initializes the SHT40 sensor.

        :param i2c_scl: GPIO pin for I2C clock
        :param i2c_sda: GPIO pin for I2C data
        :param i2c_freq: Frequency for I2C communication (100k by deault - a good value for reliable and non high speed measurement)
        :param i2c_address: I2C address of the SHT40 sensor (default address is 0x44)
        :param logger: an instance of Logger class
        """
        try:
            self.logger = logger  # Store logger as instance variable
            
            self.i2c = SoftI2C(scl=Pin(i2c_scl), sda=Pin(i2c_sda), freq=i2c_freq)
            self.sensor = sht4x.SHT4X(self.i2c, address=i2c_address)
            self.mode = 1  # Default: No heater, high precision [by default this is the mode]
            self.logger.info("SHT40 sensor initialized successfully.", publish=True)
        except Exception as e:
            self.logger.critical(f"Failed to initialize the SHT40 sensor: {e}", publish=True)
            raise # raise if initialization failed to let the caller know about it

    def set_mode(self, mode=1):
        """
        Sets the operation mode of the sensor.

        :param mode: an 'int' from 1 to 9 (both included) to set the respective mode [see the table above for the corresponding mode].
        """
        if 9 < mode < 1:
            raise ValueError("Invalid mode. Choose from 1 to 9 corresponding to the above table.")
        if mode==1:
            self.sensor.temperature_precision = sht4x.HIGH_PRECISION
            self.mode = mode
        elif mode==2:
            self.sensor.temperature_precision = sht4x.MEDIUM_PRECISION
            self.mode = mode
        elif mode==3:
            self.sensor.temperature_precision = sht4x.LOW_PRECISION
            self.mode = mode
        elif mode==4:
            self.sensor.heat_time = sht4x.TEMP_1
            self.sensor.heater_power = sht4x.HEATER200mW
            self.mode = mode
        elif mode==5:
            self.sensor.heat_time = sht4x.TEMP_0_1
            self.sensor.heater_power = sht4x.HEATER200mW
            self.mode = mode
        elif mode==6:
            self.sensor.heat_time = sht4x.TEMP_1
            self.sensor.heater_power = sht4x.HEATER110mW
            self.mode = mode
        elif mode==7:
            self.sensor.heat_time = sht4x.TEMP_0_1
            self.sensor.heater_power = sht4x.HEATER110mW
            self.mode = mode
        elif mode==8:
            self.sensor.heat_time = sht4x.TEMP_1
            self.sensor.heater_power = sht4x.HEATER20mW
            self.mode = mode
        elif mode==9:
            self.sensor.heat_time = sht4x.TEMP_0_1
            self.sensor.heater_power = sht4x.HEATER20mW
            self.mode = mode
        print(f"SHT40 sensor operation mode set to MODE: {self.mode}")

    def read_measurements(self):
        """
        Reads temperature and humidity measurements.

        :return: A tuple (temperature in °C, relative humidity in %)
        """
        try:
            temperature, humidity = self.sensor.measurements
            return temperature, humidity
        except Exception as e:
            self.logger.error(f"Error reading SHT40 sensor measurements: {e}")
            return None, None

    def reset_sensor(self):
        """
        Performs a reset on the SHT40 sensor.
        """
        try:
            self.sensor.reset()
            self.logger.info("SHT40 sensor reset successfully.")
        except Exception as e:
            self.logger.error(f"Error resetting the SHT40 sensor: {e}")

# Example Usage
if __name__ == "__main__":
    import utils
    import config
    
    # Initialize logger instance
    logger = Logger(debug_mode=True)
    
    try:
        sht40 = utils.retry_with_backoff(SHT40, 17, 16,
                                      max_retries=3, backoff_base=10,
                                      logger=logger)
        
        if sht40:
            #sht40.set_mode(1)

            while True:
                temp, hum = sht40.read_measurements()
                print(f"Temperature: {temp:.2f} °C, Humidity: {hum:.2f} %")
                
                time.sleep(10)
    
    except Exception as e:
        logger.error(f'Error occured: {e}')

