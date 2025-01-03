# download file OTA

import gc
import config
import urequests
from time import sleep
import os

from simple_logging import Logger # Import the Logger class

# function to download a file from github repo over the air
def dwnld_file(url, filename, logger: Logger, chunk_size = 1024, max_retries=3): # Adjust chunk size (bytes)
    # logger is expected to be of type Logger (i.e. an instance of Logger class)
    retry_count = 0
    while retry_count < max_retries:
        try:
            logger.log_message("INFO", "Starting download...", publish=True)
            response = urequests.get(url, stream=True, timeout=15)
            if response.status_code == 200:
                logger.log_message("INFO", f"Downloading {filename}", publish=True)
                gc.collect()
                with open(f'{filename}.new', 'wb') as f:
                    while True:
                        chunk = response.raw.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        gc.collect()
                logger.log_message("INFO", f"Download of {filename} completed.", publish=True)
                return True
            else:
                logger.log_message("ERROR", f"HTTP status code: {response.status_code}", publish=True)
                return False
        except OSError as e:
            logger.log_message("ERROR", "OS error occurred. Retrying...", publish=True)
            retry_count += 1
            if retry_count < max_retries:
                retry_interval = retry_delay * (2 ** (retry_count - 1))
                logger.log_message("INFO", f"Retrying in {retry_interval} seconds...", publish=True)
                sleep(retry_interval)
            else:
                logger.log_message("ERROR", f"Max retries exceeded. Failed to download {filename}.", publish=True)
                return False
        except Exception as e:
            logger.log_message("ERROR", f"Unexpected error: {e}", publish=True)
            break
        finally: # before retrying
            if response:
                response.close() # close response to free up resources
            gc.collect()
    return False

# check if a file exist or not
def file_exists(filename):
    try:
        os.stat(filename)
        return True
    except OSError:
        return False
    
# download and save the file in the microcontroller (by replacing its older version, if exists)    
def dwnld_and_update(filename, logger: Logger): # filename is the full filename of the file including the directory structure
    sleep(1)
    try:
        url = f'https://raw.githubusercontent.com/{config.REPO_OWNER}/{config.REPO_NAME}/main/{filename}'
        if dwnld_file(url, filename, logger):
            # some file manipulations
            if file_exists(filename):
                os.remove(filename) # remove the older version, if it exists
            os.rename(f'{filename}.new', filename)
            
            logger.log_message("INFO", "Update successful.", publish=True)
            return True
    except Exception as e:
        logger.log_message("ERROR", f"Error in updating: {e}", publish=True)
        return False

######################################
if __name__ == '__main__':
    pass
