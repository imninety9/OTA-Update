# AHT25 sensor driver


import time
from machine import I2C, Pin
'''
# to enable imports from a subfolder named 'modules'
import sys
sys.path.append('/modules')
'''
import aht  # Import the aht library

from simple_logging import Logger

class AHT25:
    def __init__(self, i2c_scl, i2c_sda, i2c_freq=100000, i2c_address=0x38,
                 logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
        """
        Initializes the AHT25 sensor.

        :param i2c_scl: GPIO pin for I2C clock
        :param i2c_sda: GPIO pin for I2C data
        :param i2c_freq: Frequency for I2C communication (100k by deault - a good value for reliable and non high speed measurement)
        :param i2c_address: I2C address of the AHT25 sensor (default address is 0x38)
        :param logger: an instance of Logger class
        """
        try:
            self.logger = logger  # Store logger as instance variable
            
            self.i2c = I2C(0, scl=Pin(i2c_scl), sda=Pin(i2c_sda), freq=i2c_freq)
            self.sensor = aht.AHT2x(self.i2c, address=i2c_address, crc=True)
            self.logger.info("AHT25 sensor initialized successfully.", publish=True)
        except Exception as e:
            self.logger.critical(f"Failed to initialize the AHT25 sensor: {e}", publish=True)
            raise # raise if initialization failed to let the caller know about it

    def read_measurements(self):
        """
        Reads temperature and humidity measurements.

        :return: A tuple (temperature in °C, relative humidity in %)
        """
        try:
            if self.sensor.is_ready:
                return self.sensor.temperature, self.sensor.humidity
            else:
                self.logger.error(f"Error reading AHT25 sensor measurements: {e}")
                return None, None
        except Exception as e:
            self.logger.error(f"Error reading AHT25 sensor measurements: {e}")
            return None, None

    def reset_sensor(self):
        """
        Performs a reset on the AHT25 sensor.
        """
        try:
            self.sensor.reset()
            self.logger.info("AHT25 Sensor reset successfully.")
        except Exception as e:
            self.logger.error(f"Error resetting the AHT25 sensor: {e}")

# Example Usage
if __name__ == "__main__":
    import utils
    import config
    
    # Initialize logger instance
    logger = Logger(debug_mode=True)
    
    try:
        aht25 = utils.retry_with_backoff(AHT25, config.sclPIN, config.sdaPIN,
                                      max_retries=3, backoff_base=10,
                                      logger=logger)
        
        if aht25:
            while True:
                temp, hum = aht25.read_measurements()
                print(f"Temperature: {temp:.2f} °C, Humidity: {hum:.2f} %")
                
                time.sleep(10)
    
    except Exception as e:
        logger.error(f'Error occured: {e}')


