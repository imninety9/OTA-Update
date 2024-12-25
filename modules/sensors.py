# sensors

from machine import Pin, SoftI2C
from bmp280 import *
import aht

import config

from simple_logging import Logger  # Import the Logger class

# Initialize sensors with status flags
def init_sensors(logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    # dictionary for sensors with their metadata for tracking their status
    '''
        sensor: sensor object
        status: True if sensor is active else False
        failures: continuous failures during sensor reading
    '''
    sensors = {}
    # Initialize SoftI2C with appropriate pins
    try:
        i2c = SoftI2C(sda=Pin(config.sdaPIN), scl=Pin(config.sclPIN))
    except Exception as e:
        logger.log_message("CRITICAL", f"Failed to initialize I2C: {e}", publish=True)
        return None  # If I2C itself fails, we cannot proceed.

    # Initialize BMP280 sensor
    try:
        bmp_sensor = BMP280(i2c, addr=0x76, use_case=BMP280_CASE_WEATHER)
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
        sensors["bmp"] = {"sensor": bmp_sensor, "status": True, "failures": 0}
        logger.log_message("INFO", "BMP280 sensor initialized successfully.", publish=True)
    except Exception as e:
        logger.log_message("ERROR", f"Failed to initialize BMP280 sensor: {e}", publish=True)
        sensors["bmp"] = {"sensor": None, "status": False, "failures": 0}

    # Initialize AHT sensor
    try:
        aht_sensor = aht.AHT2x(i2c, crc=True)
        sensors["aht"] = {"sensor": aht_sensor, "status": True, "failures": 0}
        logger.log_message("INFO", "AHT25 sensor initialized successfully.", publish=True)
    except Exception as e:
        logger.log_message("ERROR", f"Failed to initialize AHT25 sensor: {e}", publish=True)
        sensors["aht"] = {"sensor": None, "status": False, "failures": 0}

    return sensors
    
# Read Sensor data with graceful degradation logic
def read_sensors(sensors, logger: Logger, max_failures=5): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    readings = {
        "pressure": None,
        "temperature_bmp": None,
        "humidity": None,
        "temperature_aht": None
    } # initialize variables
    
    for sensor_name, sensor_data in sensors.items():
        if not sensor_data["status"]:  # Skip inactive sensors
            #logger.log_message("WARNING", f"Skipping {sensor_name.upper()} (marked as failed).", publish=True)
            continue
        try:
            sensor = sensor_data["sensor"]
            if sensor_name == "bmp":
                # Read BMP280 sensor
                readings["pressure"] = sensor.pressure
                readings["temperature_bmp"] = sensor.temperature
            elif sensor_name == "aht" and sensor.is_ready:
                # Read AHT25 sensor
                readings["humidity"] = sensor.humidity
                readings["temperature_aht"] = sensor.temperature
            
            # Reset failure count on successful read, if required
            if sensor_data["failures"] > 0:
                sensor_data["failures"] = 0
                    
        except OSError as e:
            logger.log_message("ERROR", f"I2C Communication error during {sensor_name.upper()} sensor reading: {e}", publish=True)
            # Increment failure count
            sensor_data["failures"] += 1
            # Mark sensor as failed after exceeding failure threshold
            if sensor_data["failures"] >= max_failures:
                sensor_data["status"] = False
                logger.log_message("CRITICAL", f"{sensor_name.upper()} sensor marked as failed. System running in Degraded Mode.", publish=True)
        except Exception as e:
            logger.log_message("ERROR", f"Unexpected error during {sensor_name.upper()} sensor reading: {e}", publish = True)
            # Increment failure count
            sensor_data["failures"] += 1
            # Mark sensor as failed after exceeding failure threshold
            if sensor_data["failures"] >= max_failures:
                sensor_data["status"] = False
                logger.log_message("CRITICAL", f"{sensor_name.upper()} sensor marked as failed. System running in Degraded Mode.", publish=True)

    return readings

# Attempt recovery for failed sensors
'''Add a method to attempt recovery only after a certain interval'''
def attempt_recovery(sensors, logger: Logger, i2c=None):
    for sensor_name, sensor_data in sensors.items():
        if not sensor_data["status"]:  # Only attempt recovery for failed sensors
            try:
                logger.log_message("INFO", f"Attempting recovery for {sensor_name.upper()}...", publish=True)
                
                if sensor_data["sensor"] is None: # sensor even failed to initialize
                    if i2c is None:
                        try:
                            i2c = SoftI2C(sda=Pin(config.sdaPIN), scl=Pin(config.sclPIN))
                        except Exception as e:
                            logger.log_message("CRITICAL", f"Failed to initialize I2C during recovery: {e}", publish=True)
                            continue
                    # Reinitialize the sensor
                    if sensor_name == "aht":
                        sensor = aht.AHT2x(i2c, crc=True)
                        if sensor.is_ready:
                            sensors[sensor_name] = {"sensor": sensor, "status": True, "failures": 0}
                            logger.log_message("INFO", f"{sensor_name.upper()} sensor reinitialized successfully.", publish=True)
                        else:
                            raise Exception(f"{sensor_name.upper()} sensor not functional after reinitialization.")
                    elif sensor_name == "bmp":
                        sensor = BMP280(i2c, addr=0x76, use_case=BMP280_CASE_WEATHER)
                        if sensor.temperature is not None:  # Validate reinitialization
                            sensors[sensor_name] = {"sensor": sensor, "status": True, "failures": 0}
                            logger.log_message("INFO", f"{sensor_name.upper()} sensor reinitialized successfully.", publish=True)
                        else:
                            raise Exception(f"{sensor_name.upper()} sensor not functional after reinitialization.")
                
                else:
                    # Attempt recovery for previously initialized sensors
                    # Use reset() method included in both aht and bmp sensor libraries for reinitialization
                    if sensor_name == "aht":
                        sensor_data["sensor"].reset()
                        # Validate recovery
                        if sensor_data["sensor"].is_ready:
                            sensor_data["status"] = True
                            sensor_data["failures"] = 0
                            logger.log_message("INFO", f"{sensor_name.upper()} sensor recovered successfully.", publish=True)
                    elif sensor_name == "bmp":
                        sensor_data["sensor"].reset()
                        # Validate recovery by attempting to read a property
                        if sensor_data["sensor"].temperature is not None:
                            sensor_data["status"] = True
                            sensor_data["failures"] = 0
                            logger.log_message("INFO", f"{sensor_name.upper()} sensor recovered successfully.", publish=True)
            
            except Exception as e:
                logger.log_message("ERROR", f"Failed to recover {sensor_name.upper()}: {e}", publish=True)
                