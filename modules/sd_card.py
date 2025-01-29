# sd card

from machine import Pin, SPI
import sdcard
from os import VfsFat, mount, umount

from simple_logging import Logger  # Import the Logger class

class SDCard:
    def __init__(self, spi_pin_miso, spi_pin_mosi, spi_pin_sck, spi_pin_cs,
                 logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
        # initialize sdcard
        try: 
            # Initialize SPI communication
            self.spi = SPI(
                1,
                baudrate=10000000,
                polarity=0,
                phase=0,
                sck=Pin(spi_pin_sck),
                mosi=Pin(spi_pin_mosi),
                miso=Pin(spi_pin_miso)
            )
            self.cs = Pin(spi_pin_cs)
            # Initialize SD card object
            self.sd = sdcard.SDCard(self.spi, self.cs)
            # Mount the SD card
            self.vfs = VfsFat(self.sd)
            mount(self.vfs, '/sd')
            logger.info("SD card initialialized")
        except Exception as e:
            logger.error(f"Failed to initialize sd card: {e}")
            raise # raise if initialization failed to let the caller know about it

    # unmount the sd card
    def unmount_sd_card(self, logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
        try:
            umount('/sd')
            logger.info("SD card unmounted successfully.")
        except Exception as e:
            logger.error(f"Error unmounting SD card: {e}")
        

####################################
if __name__ == "__main__":
    import utils
    import config
        
    # Initialize the logger
    logger = Logger(debug_mode=config.DEBUG_MODE)
    try:
        # initialize sd card
        
        sdcard = utils.retry_with_backoff(SDCard, config.SPI_PIN_MISO, config.SPI_PIN_MOSI,
                                 config.SPI_PIN_SCK, config.SPI_PIN_CS,
                                max_retries=5, backoff_base=5,
                                logger=logger)
        
        # unmount sd card
        if sdcard:
            sdcard.unmount_sd_card(logger=logger)
        
    except Exception as e:
        logger.error(f"Error: {e}")
        