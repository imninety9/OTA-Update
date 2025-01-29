# DS18B20 sensor driver

from machine import Pin
import onewire
import ds18x20
import time
'''
# to enable imports from a subfolder named 'modules'
import sys
sys.path.append('/modules')
'''
from simple_logging import Logger

'''
Note: As we can connect and use  multiple DS18B20 sensors on the same data line,
so if using multiple DS18B20 sensors, ensure unique ROM addresses and handle them
accordingly in the code.
The ROM address is a unique 64-bit identifier assigned to every DS18B20 sensor.
It ensures that each sensor connected to a single 1-Wire bus can be individually
identified and addressed.
When you scan the 1-Wire bus using ds.scan() in the MicroPython code, the returned
roms list contains the unique ROM addresses of all detected DS18B20 sensors.

Note: Note that you must execute the convert_temp() function to initiate a
temperature reading, then wait at least 750ms (for 12-bit resolution) before reading the value.

Resolution Adjustment: The DS18B20 supports different resolutions (9, 10, 11, and 12 bits).
For faster readings, you can lower the resolution. By default, it uses 12 bits.

Resolution table with the wait time taken for conversion and precision:

9-bit: 93.75ms - 0.5°C
10-bit: 187.5ms - 0.25°C
11-bit: 375ms - 0.125°C
12-bit: 750ms - 0.0625°C

'''

class DS18B20:
    def __init__(self, pin,
                 logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
        """
        Initialize the DS18B20 sensor(s).
        :param pin: GPIO pin number where the DATA line is connected.
        :param logger: an instance of Logger class
        """
        try:
            self.logger = logger  # Store logger as instance variable
            
            self.ds_pin = Pin(pin)
            self.ds = ds18x20.DS18X20(onewire.OneWire(self.ds_pin))
            self.roms = self.ds.scan()  # Scan for all ds18x20 devices on the bus and save their rom addresses
            if not self.roms:
                raise RuntimeError("No DS18B20 sensors found. Check connections.")
            self.logger.info(f"Found {len(self.roms)} DS18B20 sensor(s): {self.roms}", publish=True)
        except Exception as e:
            self.logger.error(f"Failed to initialize DSB1820 sensor: {e}", publish=True)
            raise # raise if initialization failed to let the caller know about it

    def read_all_temps(self):
        """
        Read temperatures from all connected sensors.
        :return: Dictionary with ROM as key and temperature as value.
        """
        try:
            # Note that you must execute the convert_temp() function to
            # initiate a temperature reading, then wait at least 750ms before
            # reading the value.
            self.ds.convert_temp()
            time.sleep(1)  # Wait for conversion (at least 750ms for 12-bit resolution)
            temps = {}
            for rom in self.roms:
                temp = self.ds.read_temp(rom)
                temps[rom] = temp
            return temps
        except Exception as e:
            self.logger.error(f"Error reading DS18B20's temperature: {e}")
            return None

    def read_temp(self, rom=None):
        """
        Read temperature from a specific sensor by its ROM.
        :param rom: ROM address of the sensor (bytes). If rom is None, read the first sensor or the only sensor.
        :return: Temperature in Celsius or None on error.
        """
        try:
            if rom is None:
                rom = self.roms[0]
            # Note that you must execute the convert_temp() function to
            # initiate a temperature reading, then wait at least 750ms before
            # reading the value.
            self.ds.convert_temp()
            time.sleep(1)  # Wait for conversion (at least 750ms for 12-bit resolution)
            return self.ds.read_temp(rom)
        except Exception as e:
            self.logger.error(f"Error reading temperature from DS18B20 [{rom}]: {e}")
            return None

    def get_sensor_count(self):
        """
        Get the number of connected sensors.
        :return: Number of sensors detected.
        """
        return len(self.roms)

    def scan(self):
        """
        Rescan the bus for sensors and update the ROM list.
        :return: Updated list of sensor ROMs.
        """
        self.roms = self.ds.scan()
        if not self.roms:
            self.logger.warning("No DS18B20 sensors found during scan.")
        return self.roms
    
    def resolution(self, rom=None, resolution_bits=None):
        # NOTE: The value set is not permanent and will be lost after a power cycle.
        #       After a power cycle it is reset to 12 which is the default set in sensor's EEPROM.
        #       If you want to make it permanent use copy scratch pad: Copies the
        #       scratchpad contents (TH, TL, and configuration register) to the sensor's EEPROM.
        #       EEPROM changes are stored permanently and will persist after power cycles.
        #       Code for this is:
        #                  # Save the changes to EEPROM
        #                  self.ds.ow.reset(True)
        #                  self.ds.ow.select_rom(rom)
        #                  self.ds.ow.writebyte(0x48)  # COPY SCRATCHPAD command
        """
        set or get resolution of a sensor. If resolution_bits is None it returns the resolution of the sensor.
        :param rom: ROM address of the sensor (bytes). If rom is None, read the first sensor or the only sensor.
        :param resolution_bits: the resolution you want to set [9 to 12, both included]. If resolution_bits is None it gets and returns the resolution of the sensor.
        :return: resolution_bits
        """
        try:
            if rom is None:
                rom = self.roms[0]
            config = bytearray(3)
            if resolution_bits is not None and 9 <= resolution_bits <= 12:
                config[2] = ((resolution_bits - 9) << 5) | 0x1f
                '''
                config = {
                    9: b'\x00\x00\x1f',   # 00011111
                    10: b'\x00\x00\x3f',  # 00111111
                    11: b'\x00\x00\x5f',  # 01011111
                    12: b'\x00\x00\x7f',  # 01111111
                }
                '''
                self.ds.write_scratch(rom, config)
                self.logger.info(f"DS18B20 sensor [{rom}] resolution set to {resolution_bits} bits.")
                return resolution_bits
            else:
                data = self.ds.read_scratch(rom)
                return ((data[4] >> 5) & 0x03) + 9
        except Exception as e:
            self.logger.error(f"Error getting or setting DS18B20 sensor resolution: {e}")
        

# Example usage
if __name__ == "__main__":
    import utils
    import config
    
    # Initialize logger instance
    logger = Logger(debug_mode=True)
    
    # Change GPIO pin as per your wiring
    ds_pin = 4
    try:
        sensor = utils.retry_with_backoff(DS18B20, ds_pin,
                                          max_retries=3, backoff_base=10,
                                          logger=logger)
        
        res = sensor.resolution()
        print(f"Sensor resolution is {res} bits.")
        
        # Print sensor count
        print(f"Total sensors found: {sensor.get_sensor_count()}")
        
        if sensor.get_sensor_count() == 1:            
            # Continuous temperature monitoring
            while True:
                temp = sensor.read_temp(sensor.roms[0])  # Automatically use the only sensor
                print(f"Temperature: {temp:.2f} °C")
                time.sleep(10)
        else:
            # Continuous temperature monitoring
            while True:
                temps = sensor.read_all_temps()
                if temps:
                    for rom, temp in temps.items():
                        print(f"Sensor {rom}: {temp:.2f} °C")
                time.sleep(10)
    except RuntimeError as e:
        logger.error(f"Initialization error: {e}")
    except Exception as e:
        logger.error(f"Unknown error: {e}")

