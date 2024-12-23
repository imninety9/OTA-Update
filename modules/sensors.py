# sensors

from machine import Pin, SoftI2C
from bmp280 import *
import aht

import utils
import config
from custom_exceptions import SetupError

from simple_logging import Logger  # Import the Logger class

# Initialize sensors
def init_sensors(logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    try:
        # Initialize SoftI2C with appropriate pins
        i2c = SoftI2C(sda=Pin(config.sdaPIN), scl=Pin(config.sclPIN))
        bmp = BMP280(i2c, addr=0x76, use_case=BMP280_CASE_WEATHER)
        '''
        # choose the preferred use case
        bmp.use_case(BMP280_CASE_WEATHER)
        # all available use cases-
        #BMP280_CASE_HANDHELD_LOW
        #BMP280_CASE_HANDHELD_DYN
        #BMP280_CASE_WEATHER
        #BMP280_CASE_FLOOR
        #BMP280_CASE_DROP
        #BMP280_CASE_INDOOR
        '''
        sensor = aht.AHT2x(i2c, crc=True)
        logger.log_message("INFO", "AHT25 and BMP280 sensors initialized.", publish = True)
        return sensor, bmp
    except Exception as e:
        logger.log_message("CRITICAL", f"Failed to initialize AHT25 or BMP280 sensor: {e}", publish = True)
        utils.deep_sleep(120000, logger) # ms
        raise SetupError("Sensor initialization failed")
    
    
# Read Sensor data
def read_sensors(aht_sensor, bmp_sensor, logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    try:
        pressure = bmp_sensor.pressure
        temperature_bmp = bmp_sensor.temperature

        if aht_sensor.is_ready:
            humidity = aht_sensor.humidity
            temperature = aht_sensor.temperature
        else:
            humidity = temperature = None
        
        return pressure, temperature_bmp, humidity, temperature
    except Exception as e:
        logger.log_message("ERROR", f"Failed to read sensor: {e}", publish = True)
    