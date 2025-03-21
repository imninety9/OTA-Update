# utility functions

import machine
import os
import gc
from time import sleep

from simple_logging import Logger  # Import the Logger class

# Get the cause of the reset
def reset_cause(logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
    try:
        rst_cause = machine.reset_cause()
        causes = {
            machine.PWRON_RESET: "Power on reset", # when device first time starts up after being powered on
            machine.HARD_RESET: "Hard reset", # physical reset by a button or through power cycling
            machine.WDT_RESET: "Watchdog reset", # wdt resets the the device when it hangs
            machine.DEEPSLEEP_RESET: "Wake from deep sleep", # waking from a deep sleep
            machine.SOFT_RESET: "Soft reset" # software rest by a command
        }
        cause_str = causes.get(rst_cause, "Unknown reset cause")
        logger.info(f"Reset cause: {cause_str}")
        return cause_str
    except Exception as e:
        logger.error(f"Failed to get the reset cause: {e}")

# Reset the microcontroller
def reset():
    '''reset the microcontroller'''
    machine.reset()

# Light sleep [program continues after waking from light sleep]
def light_sleep(duration_ms,
                logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
    """Put the microcontroller into light sleep for the specified duration."""
    if duration_ms > 0:
        logger.info(f"Light sleeping for {duration_ms / 1000} seconds...")
        os.sync()  # Ensure all logs are written to disk
        # Set the time (in ms) for deep sleep
        machine.lightsleep(duration_ms)
        
# DEEP sleep [program restarts after waking from deep sleep]
def deep_sleep(duration_ms,
               logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
    """Put the microcontroller into deep sleep for the specified duration."""
    '''Currently, deep_sleep logs before entering sleep. If power is lost before deep sleep, the message is not persisted.'''
    '''Improvement: Flush logs before sleeping using os.sync().'''
    if duration_ms > 0:
        logger.info(f"Deep sleeping for {duration_ms / 1000} seconds...")
        os.sync()  # Ensure all logs are written to disk
        # Set the time (in ms) for deep sleep
        machine.deepsleep(duration_ms)

# Retry logic with backoff for any function
def retry_with_backoff(function, *args,
                       max_retries=5, backoff_base=10, logger: Logger = Logger(), # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
                       **kwargs):
    # *args, **kwargs are the arguments, ketword arguments of the function
    """Generalized retry logic with exponential backoff."""
    '''
        function = function on which we want to apply retry logic
        *args, **kwargs = arguments, keyword aruments for the function
        max_retries = 5  # Max connection retries before long sleep
        backoff_base = 10  # Base seconds for exponential backoff
        logger = an instance of Logger class
    '''
    retry_count = 0
    # Add logger to kwargs [assuming all functions have logger as an keyward argument in their definition]
    kwargs['logger'] = logger
    while retry_count < max_retries:
        try:
            result = function(*args, **kwargs)
            if result:
                return result # function executed successfully, no retries needed, just return the function result
            sleep_time = min(backoff_base * (2 ** retry_count), 300)  # Cap at 5 minutes
            logger.warning(f"{function.__name__} failed during retry {retry_count + 1}. Retrying in {sleep_time} seconds...")
            sleep(sleep_time)
            retry_count += 1
        except Exception as e:
            sleep_time = min(backoff_base * (2 ** retry_count), 300)  # Cap at 5 minutes
            logger.error(f"Error during retry {retry_count + 1} of {function.__name__}: {e}. Retrying in {sleep_time} seconds...")
            sleep(sleep_time)
            retry_count += 1
    logger.critical(f"Max retries reached for {function.__name__}. Take the appropriate measure.")
    return None # return None to let the caller know that all retries failed 

# log the memory status
def log_memory(logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
    try:
        free_memory = gc.mem_free()
        logger.info(f"Free memory: {free_memory}")
    except Exception as e:
        logger.error(f"Failed to collect and log memory: {e}")
