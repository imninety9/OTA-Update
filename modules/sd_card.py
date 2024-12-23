# sd card

from machine import Pin, SPI
import sdcard
from os import VfsFat, mount, umount

import utils
import config
from custom_exceptions import SetupError

from simple_logging import Logger  # Import the Logger class

# initialize sdcard
def initialize_sd(logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    # Define SPI pin configurations
    SPI_PIN_MISO = config.SPI_PIN_MISO #19
    SPI_PIN_MOSI = config.SPI_PIN_MOSI #23
    SPI_PIN_SCK = config.SPI_PIN_SCK #18
    SPI_PIN_CS = config.SPI_PIN_CS #5  # You can choose any available GPIO pin for CS
    try:
        # Initialize SPI communication
        spi = SPI(
            1,
            baudrate=10000000,
            polarity=0,
            phase=0,
            sck=Pin(SPI_PIN_SCK),
            mosi=Pin(SPI_PIN_MOSI),
            miso=Pin(SPI_PIN_MISO)
        )
        cs = Pin(SPI_PIN_CS)
        # Initialize SD card object
        sd = sdcard.SDCard(spi, cs)
        # Mount the SD card
        vfs = VfsFat(sd)
        mount(vfs, '/sd')
        logger.log_message('INFO', "SD card initialialized")
        return True
    except Exception as e:
        logger.log_message('ERROR', f"Failed to initialize sd card: {e}")
        return False

# unmount the sd card
def unmount_sd_card(logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    try:
        umount('/sd')
        logger.log_message('INFO', "SD card unmounted successfully.")
    except Exception as e:
        logger.log_message('ERROR', f"Error unmounting SD card: {e}")
        

####################################
if __name__ == "__main__":
    try:
        # Initialize the logger
        logger = Logger(debug_mode=config.DEBUG_MODE)
        
        # initialize sd card
        utils.retry_with_backoff(logger, initialize_sd, logger, max_retries=5, backoff_base=5, long_sleep_duration=300*1000)
        
        # unmount sd card
        unmount_sd_card(logger)
        
    except SetupError as se:
        logger.log_message("CRITICAL", f"Setup error occurred: {se}. Resetting the Device...")
        sleep(60)
        utils.reset()
        
    except Exception as e:
        logger.log_message("ERROR", f"Error: {e}")