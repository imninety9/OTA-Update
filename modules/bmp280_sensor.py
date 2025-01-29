# BMP280 sensor driver


import time
from machine import I2C, Pin
'''
# to enable imports from a subfolder named 'modules'
import sys
sys.path.append('/modules')
'''
from bmp280 import *

from simple_logging import Logger

class BMP280Driver:
    def __init__(self, i2c_scl, i2c_sda, i2c_freq=100000, i2c_address=0x76, use_case=BMP280_CASE_WEATHER,
                 logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
        """
        Initializes the BMP280 sensor.

        :param i2c_scl: GPIO pin for I2C clock
        :param i2c_sda: GPIO pin for I2C data
        :param i2c_freq: Frequency for I2C communication (100k by deault - a good value for reliable and non high speed measurement)
        :param i2c_address: I2C address of the BMP280 sensor (default address is 0x76)
        :use_case: use case of bmp280
        # choose the preferred use case:
        # all available use cases-
        #BMP280_CASE_WEATHER
        #BMP280_CASE_HANDHELD_LOW
        #BMP280_CASE_HANDHELD_DYN
        #BMP280_CASE_WEATHER
        #BMP280_CASE_FLOOR
        #BMP280_CASE_DROP
        #BMP280_CASE_INDOOR
        :param logger: an instance of Logger class
        """
        try:
            self.logger = logger  # Store logger as instance variable
            
            self.i2c = I2C(0, scl=Pin(i2c_scl), sda=Pin(i2c_sda), freq=i2c_freq)
            self.sensor = BMP280(self.i2c, addr=i2c_address, use_case=use_case)
            self.logger.info("BMP280 sensor initialized successfully.", publish=True)
        except Exception as e:
            self.logger.critical(f"Failed to initialize the BMP280 sensor: {e}", publish=True)
            raise # raise if initialization failed to let the caller know about it

    def read_measurements(self):
        """
        Reads temperature and pressure measurements.

        :return: A tuple (temperature in °C, pressure in Pa)
        """
        try:
            return self.sensor.temperature, self.sensor.pressure
        except Exception as e:
            self.logger.error(f"Error reading BMP280 sensor measurements: {e}")
            return None, None

    def reset_sensor(self):
        """
        Performs a reset on the BMP280 sensor.
        """
        try:
            self.sensor.reset()
            self.logger.info("BMP280 sensor reset successfully.")
        except Exception as e:
            self.logger.error(f"Error resetting the BMP280 sensor: {e}")

# Example Usage
if __name__ == "__main__":
    import utils
    import config
    
    # Initialize logger instance
    logger = Logger(debug_mode=True)
    
    try:
        bmp280 = utils.retry_with_backoff(BMP280Driver, config.sclPIN, config.sdaPIN,
                                      max_retries=3, backoff_base=10,
                                      logger=logger)
        
        if bmp280:
            while True:
                temp, press = bmp280.read_measurements()
                print(f"Temperature: {temp:.2f} °C, Pressure: {press:.2f} Pa")
                
                time.sleep(10)
    
    except Exception as e:
        logger.error(f'Error occured: {e}')



