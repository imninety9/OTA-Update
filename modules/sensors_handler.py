# sensor manager class to handle all sensors

'''
# to enable imports from a subfolder named 'modules'
import sys
sys.path.append('/modules')
'''
from sht40_sensor import SHT40  # Import sht40 sensor driver
from aht25_sensor import AHT25 # Import aht25 sensor driver
from bmp280_sensor import * # Import bmp280 sensor driver
from ds18b20_sensor import DS18B20 # Import ds18b20 sensor driver


from simple_logging import Logger

class Sensors:
    def __init__(self, i2cPins: tuple = None, i2c_freq: int = 100000,
                 softi2cPins: tuple = None, softi2c_freq: int = 100000,
                 spiPins: tuple = None, spi_baudrate: int = 10000000,
                 onewirePin: int = None,
                 maxFailures: int = 5,
                 logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
        """
        Initializes all the sensors.

        :param i2cPins: GPIO pin for I2C bus (scl, sda)
        :param i2c_freq: freq for I2C bus (100kHz by deault - a good value for reliable and non high speed measurement)
        :param softi2cPins: GPIO pin for Soft I2C bus (scl, sda)
        :param softi2c_freq: freq for SoftI2C bus (100kHz by deault - a good value for reliable and non high speed measurement)
        :param spiPins: GPIO Pins for SPI communication
        :param spi_baudrate: baudrate for SPI communication
        :param onewirePin: GPIO Pin for 1-wire communication
        :param: maxFailures: maximum continuous measurement failures allowed for a sensor, before declaring it as 'failed'
        :param logger: an instance of Logger class
        """
        try:
            self.logger = logger  # Store logger as instance variable
            
            self.i2cPins = i2cPins
            self.i2c_freq = i2c_freq
            self.softi2cPins= softi2cPins
            self.softi2c_freq = softi2c_freq
            self.spiPins = spiPins
            self.spi_baudrate = spi_baudrate
            self.onewirePin = onewirePin
            # dictionary for sensors with their name and metadata for tracking their status
            '''
                key:
                    sensor name
                values:
                    object: sensor object
                    status: True if sensor is active else False
                    failures: continuous failures during sensor reading
            '''
            self.sensor_data = {}
            if self.i2cPins is not None:
                try:
                    self.aht25 = AHT25(self.i2cPins[0], self.i2cPins[1], i2c_freq=100000, i2c_address=0x38, logger=logger)
                except:
                    self.aht25 = None
                self.sensor_data["aht25"] = {"object": self.aht25, "status": self.aht25!=None, "failures": 0}
                try:
                    self.bmp280 = BMP280Driver(self.i2cPins[0], self.i2cPins[1], i2c_freq=100000, i2c_address=0x76, use_case=BMP280_CASE_WEATHER, logger=logger)
                except:
                    self.bmp280 = None
                self.sensor_data["bmp280"] = {"object": self.bmp280, "status": self.bmp280!=None, "failures": 0}
            if self.softi2cPins is not None:
                try:
                    self.sht40 = SHT40(self.softi2cPins[0], self.softi2cPins[1], i2c_freq=100000, i2c_address=0x44, logger=logger)
                except:
                    self.sht40 = None
                self.sensor_data["sht40"] = {"object": self.sht40, "status": self.sht40!=None, "failures": 0}
            if self.onewirePin is not None:
                try:
                    self.ds18b20 = DS18B20(self.onewirePin, logger=logger)
                except:
                    self.ds18b20 = None
                self.sensor_data["ds18b20"] = {"object": self.ds18b20, "status": self.ds18b20!=None, "failures": 0}
            
            self.maxFailures = maxFailures
            # variable to keep track, if any sensor needs recovery [True or False]
            self.recovery_needed = any(value["object"] is None or not value["status"] for value in self.sensor_data.values())
            
        except Exception as e:
            self.logger.critical(f"Error in sensor initialization process: {e}", publish=True)
            raise # raise if initialization failed to let the caller know about it
            
    def read_measurements(self):
        """
        Read Sensor measurements.
        
        return: a dict of measurements/readings in form:
            measurements = {
            "aht25": (None, None), # temp, hum
            "bmp280": (None, None), # temp, press
            "sht40": (None, None), # temp, hum
            "ds18b20": None # temp
            }
        """
        
        measurements = {} # readings in dict
        
        for sensor_name in self.sensor_data.keys():
            if sensor_name in ['aht25', 'bmp280', 'sht40']:
                measurements[sensor_name] = (None, None)
                if self.sensor_data[sensor_name]['status']:
                    try:
                        readings = self.sensor_data[sensor_name]['object'].read_measurements()
                        measurements[sensor_name] = readings
                        if not any(readings): # if not any reading is valid i.e. all readings are None; it means senor measurement has failed
                            raise
                        # Reset failure count on successful read, if required
                        if self.sensor_data[sensor_name]['failures'] > 0:
                            self.sensor_data[sensor_name]['failures'] = 0
                    except:
                        # Increment failure count
                        self.sensor_data[sensor_name]['failures'] += 1
                        # Mark sensor as failed after exceeding failure threshold
                        if self.sensor_data[sensor_name]['failures'] >= self.maxFailures:
                            self.sensor_data[sensor_name]['status'] = False
                            self.recovery_needed = True
                            self.logger.warning(f"{sensor_name.upper()} sensor marked as failed. System running in Degraded Mode.", publish=True)
            elif sensor_name == 'ds18b20':
                measurements[sensor_name] = None
                if self.sensor_data[sensor_name]['status']:
                    try:
                        reading = self.sensor_data[sensor_name]['object'].read_temp()
                        measurements[sensor_name] = reading
                        if reading is None: # if reading is None; it means senor measurement has failed
                            raise
                        # Reset failure count on successful read, if required
                        if self.sensor_data[sensor_name]['failures'] > 0:
                            self.sensor_data[sensor_name]['failures'] = 0
                    except:
                        # Increment failure count
                        self.sensor_data[sensor_name]['failures'] += 1
                        # Mark sensor as failed after exceeding failure threshold
                        if self.sensor_data[sensor_name]['failures'] >= self.maxFailures:
                            self.sensor_data[sensor_name]['status'] = False
                            self.recovery_needed = True
                            self.logger.warning(f"{sensor_name.upper()} sensor marked as failed. System running in Degraded Mode.", publish=True)
        return measurements
                
    def attempt_recovery(self):
        """
        Attempt recovery of failed sensors.

        """
        for sensor_name in self.sensor_data.keys():
            if not self.sensor_data[sensor_name]["status"]:  # Only attempt recovery for failed sensors
                try:
                    self.logger.info(f"Attempting recovery for {sensor_name.upper()}...", publish=True)
                    
                    if self.sensor_data[sensor_name]["object"] is None: # sensor even failed to initialize
                        # Reinitialize the sensor
                        if sensor_name == "aht25":
                            try:
                                self.aht25 = AHT25(self.i2cPins[0], self.i2cPins[1], i2c_freq=100000, i2c_address=0x38, logger=logger)
                                self.sensor_data[sensor_name]["object"] = self.aht25
                                if any(self.aht25.read_measurements()): # Validate reinitialization
                                    self.sensor_data[sensor_name]["status"] = True
                                    self.recovery_needed = False
                                    self.logger.info(f"{sensor_name.upper()} sensor reinitialized and recovered successfully.", publish=True)
                                else:
                                    self.sensor_data[sensor_name]["object"] = False
                                    self.recovery_needed = True
                                    self.logger.error(f"{sensor_name.upper()} sensor not functional after reinitialization.")
                            except Exception as e:
                                self.aht25 = None
                                self.sensor_data[sensor_name]["status"] = self.aht25
                                self.recovery_needed = True
                                self.logger.error(f"{sensor_name.upper()} could not be reinitialized: {e}")
                        elif sensor_name == "bmp280":
                            try:
                                self.bmp280 = BMP280Driver(self.i2cPins[0], self.i2cPins[1], i2c_freq=100000, i2c_address=0x76, use_case=BMP280_CASE_WEATHER, logger=logger)
                                self.sensor_data[sensor_name]["object"] = self.bmp280
                                if any(self.bmp280.read_measurements()):  # Validate reinitialization
                                    self.sensor_data[sensor_name]["status"] = True
                                    self.recovery_needed = False
                                    self.logger.info(f"{sensor_name.upper()} sensor reinitialized and recovered successfully.", publish=True)
                                else:
                                    self.sensor_data[sensor_name]["status"] = False
                                    self.recovery_needed = True
                                    self.logger.error(f"{sensor_name.upper()} sensor not functional after reinitialization.")
                            except Exception as e:
                                self.bmp280 = None
                                self.sensor_data[sensor_name]["object"] = self.bmp280
                                self.recovery_needed = True
                                self.logger.error(f"{sensor_name.upper()} could not be reinitialized: {e}")
                        elif sensor_name == "sht40":
                            try:
                                self.sht40 = SHT40(self.softi2cPins[0], self.softi2cPins[1], i2c_freq=100000, i2c_address=0x44, logger=logger)
                                self.sensor_data[sensor_name]["object"] = self.sht40
                                if any(self.sht40.read_measurements()):  # Validate reinitialization
                                    self.sensor_data[sensor_name]["status"] = True
                                    self.recovery_needed = False
                                    self.logger.info(f"{sensor_name.upper()} sensor reinitialized and recovered successfully.", publish=True)
                                else:
                                    self.sensor_data[sensor_name]["status"] = False
                                    self.recovery_needed = True
                                    self.logger.error(f"{sensor_name.upper()} sensor not functional after reinitialization.")
                            except Exception as e:
                                self.sht40 = None
                                self.sensor_data[sensor_name]["object"] = self.sht40
                                self.recovery_needed = True
                                self.logger.error(f"{sensor_name.upper()} could not be reinitialized: {e}")
                        elif sensor_name == "ds18b20":
                            try:
                                self.ds18b20 = DS18B20(self.onewirePin, logger=logger)
                                self.sensor_data[sensor_name]["object"] = self.ds18b20
                                if self.ds18b20.read_temp():  # Validate reinitialization
                                    self.sensor_data[sensor_name]["status"] = True
                                    self.recovery_needed = False
                                    self.logger.info(f"{sensor_name.upper()} sensor reinitialized and recovered successfully.", publish=True)
                                else:
                                    self.sensor_data[sensor_name]["status"] = False
                                    self.recovery_needed = True
                                    self.logger.error(f"{sensor_name.upper()} sensor not functional after reinitialization.")
                            except Exception as e:
                                self.ds18b20 = None
                                self.sensor_data[sensor_name]["object"] = self.ds18b20
                                self.recovery_needed = True
                                self.logger.error(f"{sensor_name.upper()} could not be reinitialized: {e}")
                    
                    else:
                        # Attempt recovery for previously initialized sensors
                        # Use reset() and other methods included in libraries
                        if sensor_name == "aht25":
                            self.sensor_data[sensor_name]["object"].reset_sensor()
                            # Validate recovery
                            if any(self.sensor_data[sensor_name]["object"].read_measurements()):
                                self.sensor_data[sensor_name]["status"] = True
                                self.sensor_data[sensor_name]["failures"] = 0
                                self.recovery_needed = False
                                self.logger.info(f"{sensor_name.upper()} sensor recovered successfully.", publish=True)
                            else:
                                self.recovery_needed = True
                                raise Exception (f"Failed to recover {sensor_name.upper()}")
                        elif sensor_name == "bmp280":
                            self.sensor_data[sensor_name]["object"].reset_sensor()
                            # Validate recovery
                            if any(self.sensor_data[sensor_name]["object"].read_measurements()):
                                self.sensor_data[sensor_name]["status"] = True
                                self.sensor_data[sensor_name]["failures"] = 0
                                self.recovery_needed = False
                                self.logger.info(f"{sensor_name.upper()} sensor recovered successfully.", publish=True)
                            else:
                                self.recovery_needed = True
                                raise Exception (f"Failed to recover {sensor_name.upper()}")
                        elif sensor_name == "sht40":
                            self.sensor_data[sensor_name]["object"].reset_sensor()
                            # Validate recovery
                            if any(self.sensor_data[sensor_name]["object"].read_measurements()):
                                self.sensor_data[sensor_name]["status"] = True
                                self.sensor_data[sensor_name]["failures"] = 0
                                self.recovery_needed = False
                                self.logger.info(f"{sensor_name.upper()} sensor recovered successfully.", publish=True)
                            else:
                                self.recovery_needed = True
                                raise Exception (f"Failed to recover {sensor_name.upper()}")
                        elif sensor_name == "ds18b20":
                            self.sensor_data[sensor_name]["object"].ds.ow.reset()
                            # Validate recovery
                            if self.sensor_data[sensor_name]["object"].read_temp():
                                self.sensor_data[sensor_name]["status"] = True
                                self.sensor_data[sensor_name]["failures"] = 0
                                self.recovery_needed = False
                                self.logger.info(f"{sensor_name.upper()} sensor recovered successfully.", publish=True)
                            else:
                                self.recovery_needed = True
                                raise Exception (f"Failed to recover {sensor_name.upper()}")
                
                except Exception as e:
                    self.logger.error(f"Error in recovery: {e}", publish=True)
                    

# Example Usage
if __name__ == "__main__":
    import utils
    import config
    import time
    
    # Initialize logger instance
    logger = Logger(debug_mode=True)
    
    try:
        sensors = utils.retry_with_backoff(Sensors,
                                    max_retries=3,
                                    backoff_base=10,
                                    logger=logger,
                                    i2cPins=(config.sclPIN, config.sdaPIN),
                                    softi2cPins=(17,16),
                                    onewirePin=4)
        
        if sensors:
            while True:
                readings = sensors.read_measurements()
                print(readings)
                
                time.sleep(20)
    
    except Exception as e:
        logger.error(f'Error occured: {e}')
        
