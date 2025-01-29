# AT24C32 eeprom

'''
1 byte = 8 bits
size of AT24C32 = 32Kb (kilo bits) = 4KB (kilo bytes) = 4096 bytes
'''

from machine import SoftI2C, Pin
from eeprom import EEPROM

from simple_logging import Logger

class AT24C32:
    def __init__(self, i2c_scl, i2c_sda,
                 i2c_freq=100000, eeprom_address=0x57,
                 logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
        """
        Initialize the I2C bus and the EEPROM

        :param i2c_scl: GPIO pin for I2C clock
        :param i2c_sda: GPIO pin for I2C data
        :param i2c_freq: Frequency for I2C communication
        :param eeprom_address: I2C address of the EEPROM
        :param logger: an instance of Logger class
        """
        try:
            self.logger = logger
            self.i2c = SoftI2C(scl=Pin(i2c_scl), sda=Pin(i2c_sda), freq=i2c_freq)
            self.at24c32 = EEPROM(addr=eeprom_address, pages=128, # for AT24C32 i.e. of 32Kb
                                 bpp = 32, at24x=32, # 32 Kb eeprom
                                 i2c=self.i2c)
            self.logger.info("EEPROM initialized successfully.")
        except Exception as e:
            self.logger.error(f"Failed to initialize EEPROM: {e}")
            raise # raise if initialization failed to let the caller know about it

    def write(self, address, data):
        """
        Write data to the EEPROM

        :param address: Starting byte address for writing [indexed from 0]
        :param data: Data to write (can be bytes, list of integers, or string)
        """
        try:
            #self.logger.info(f"Writing data to EEPROM at address {address}: {data}")
            self.at24c32.write(addr=address, buf=data)
            self.logger.info("Write successful.")
        except ValueError as e:
            self.logger.error(f"Write failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during write: {e}")

    def read(self, address, nbytes):
        """
        Read data from the EEPROM

        :param address: Starting byte address for reading [indexed from 0]
        :param nbytes: Number of bytes to read
        :return: Data read from the EEPROM
        """
        try:
            #self.logger.info(f"Reading {nbytes} bytes from EEPROM starting at address {address}.")
            data = self.at24c32.read(addr=address, nbytes=nbytes)
            #self.logger.info(f"Read successful: {data}")
            return data
        except ValueError as e:
            self.logger.error(f"Read failed: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error during read: {e}")
            return None

    def update(self, address, data):
        """
        Update data in the EEPROM only if it has changed

        :param address: Starting bytes address for updating [indexed from 0]
        :param data: Data to write (can be bytes, list of integers, or string)
        """
        try:
            #self.logger.info(f"Updating EEPROM at address {address} with data: {data}")
            self.at24c32.update(addr=address, buf=data)
            self.logger.info("Update successful.")
        except ValueError as e:
            self.logger.error(f"Update failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during update: {e}")

    def wipe(self):
        """
        Wipe the entire EEPROM by writing 0xFF to all cells
        """
        try:
            #self.logger.info("Wiping entire EEPROM...")
            self.at24c32.wipe()
            self.logger.info("EEPROM wipe successful.")
        except Exception as e:
            self.logger.error(f"Unexpected error during wipe: {e}")

    def print_pages(self, address, nbytes):
        """
        Print pages of EEPROM content for debugging

        :param address: Starting address for reading
        :param nbytes: Number of bytes to read and print
        """
        try:
            #self.logger.info(f"Printing EEPROM pages from address {address} to {address + nbytes}.")
            self.at24c32.print_pages(addr=address, nbytes=nbytes)
        except ValueError as e:
            self.logger.error(f"Page printing failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during page printing: {e}")

# Example Usage
if __name__ == "__main__":
    import utils
    import config
    
    # Initialize logger instance
    logger = Logger(debug_mode=config.DEBUG_MODE)
    try:
        # Initialize the EEPROM
        at32 = utils.retry_with_backoff(AT24C32, config.softsclPIN, config.softsdaPIN,
                                          max_retries=3, backoff_base=10,
                                          logger=logger)

        if at32:
            # Write data to EEPROM
            at32.write(address=0, data=b'Hello, AT24C32!')
            
            # Read data back from EEPROM
            data = at32.read(address=0, nbytes=15) # Hello, AT24C32!  has 15 bytes
            print(data)

            # Update EEPROM with new data
            #at32.update(address=2, data=b'Updated Data')
            
            '''
            # Print EEPROM content for debugging
            at32.print_pages(address=0, nbytes=32)
            '''
            
            '''
            # Wipe the entire EEPROM
            at32.wipe()
            
            # Verify wipe by reading back wiped data
            wiped_data = at32.read(address=0, nbytes=32)
            print(f"Wiped data: {wiped_data}")
            '''
            
    except Exception as e:
        logger.error(f'Error occured: {e}')    
