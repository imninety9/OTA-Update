# utility functions

import machine
import os
import gc

import config
from custom_exceptions import SetupError

from simple_logging import Logger  # Import the Logger class

# Get the cause of the reset
def reset_cause(logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
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
        logger.log_message("INFO", f"Reset cause: {cause_str}")
        return cause_str
    except Exception as e:
        logger.log_message("ERROR", f"Failed to get the reset cause: {e}")

# Reset the microcontroller
def reset():
    '''reset the microcontroller'''
    machine.reset()
    
# DEEP sleep
def deep_sleep(duration_ms, logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    """Put the microcontroller into deep sleep for the specified duration."""
    '''Currently, deep_sleep logs before entering sleep. If power is lost before deep sleep, the message is not persisted.'''
    '''Improvement: Flush logs before sleeping using os.sync().'''
    logger.log_message("INFO", f"Sleeping for {duration_ms / 1000} seconds...")
    os.sync()  # Ensure all logs are written to disk
    # Set the time (in ms) for deep sleep
    machine.deepsleep(duration_ms)

# Retry logic with backoff for any function
def retry_with_backoff(logger: Logger, function, *args, max_retries=5, backoff_base=10, long_sleep_duration=3600*1000, **kwargs): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    """Generalized retry logic with exponential backoff."""
    '''
        function = function on which we want to apply retry logic
        *args, **kwargs = arguments, keyword aruments for the function
        max_retries = 10  # Max connection retries before long sleep
        backoff_base = 15  # Base seconds for exponential backoff
        long_sleep_duration = 3600 * 1000  # 1 hour in milliseconds
    '''
    retry_count = 0
    while retry_count < max_retries:
        try:
            result = function(*args, **kwargs)
            if result:
                return result # function executed successfully, no retries needed, just return the function result
            sleep_time = min(backoff_base * (2 ** retry_count), 300)  # Cap at 5 minutes
            logger.log_message("WARNING", f"{function} execution unsuccessful. Retrying in {sleep_time} seconds...")
            deep_sleep(sleep_time * 1000, logger)
            retry_count += 1
        except Exception as e:
            logger.log_message("ERROR", f"Error during retry {retry_count + 1} of {function}: {e}")
            retry_count += 1
            deep_sleep(10 * 1000, logger)
    logger.log_message("CRITICAL", "Max retries reached. Entering long sleep.")
    deep_sleep(long_sleep_duration, logger) # This will help in case of longer periods with no available wifi/internet
    raise SetupError("Max rtries reached for {function}")

# log the memory status
def log_memory(logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    try:
        free_memory = gc.mem_free()
        logger.log_message("INFO", f"Free memory: {free_memory}")
    except Exception as e:
        logger.log_message("ERROR", f"Failed to collect and log memory: {e}")
