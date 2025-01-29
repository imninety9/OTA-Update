# download a file from github public repository over the air

import urequests as requests
import gc  # Garbage collector for memory management
import time  # For retry delay
import os
import hashlib # For checksum validation

# to enable imports from a subfolder named 'modules'
import sys
sys.path.append('/modules')

from simple_logging import Logger # Import the Logger class
    
# function to download a file from github public repo over the air
def download_large_file(url, filename, max_retries=3, retry_delay=5,
                        initial_chunk_size=512, max_chunk_size=2048,  # Adjust chunk size as necessary
                        read_timeout=15, checksum=None,
                        logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
    def print_progress_bar(bytes_downloaded, total_size, speed, bar_length=50):
        if total_size > 0:
            progress_percent = bytes_downloaded * 100 // total_size
            block = (bar_length * progress_percent) // 100
            bar = '#' * block + '-' * (bar_length - block)
            print(f'\r[{bar}] {progress_percent}% ({bytes_downloaded}/{total_size} bytes at {speed} bytes/sec)', end='')
        else:
            print(f'\rDownloaded {bytes_downloaded} bytes at {speed} bytes/sec)', end='')
    
    # checksum to validate the download is not corrupted:
    # sha256 checksum is applied below, change as per requirement
    def validate_checksum(file_path, expected_checksum, logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
        sha256 = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(4096) # Adjust chunk size as needed
                    if not chunk:
                        break
                    sha256.update(chunk)
            checksum_bytes = sha256.digest()
            checksum_hex = ''.join('{:02x}'.format(byte) for byte in checksum_bytes)
            return checksum_hex == expected_checksum
        except Exception as e:
            logger.error(f"Error during checksum validation: {e}", publish=True)
            return False
    
    headers = {}
    retry_count = 0
    start_time = time.ticks_ms()
    current_chunk_size = initial_chunk_size
    response = None  # Initialize response object outside the try block
    while retry_count < max_retries:
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=read_timeout) # client will wait 'timeout' period before abondoning connection request, if not fulfilled by then
            # stream = True instructs client to read the data in stream
            # as, client sends an http "request"; the server responds with
            # a "response" which contains "status code: (int) - status of the connection request",
            # "headers: (dict) - containing info and metadata", "content: (str or equivalent)- content of the request"
            # and maybe something else.
            if response.status_code == 200: # 200 is OK
                total_size = int(response.headers.get('Content-Length', 0)) # .get() method of dictionaries: if Content-Length is not present it returns 0   
            else:
                raise Exception(f"Unexpected HTTPS status code: {response.status_code}")

            logger.info(f"Downloading {filename}", publish=True)

            with open(f'{filename}.new', 'wb') as f:
                bytes_downloaded = 0                    
                gc.collect()
                while True:
                    chunk = response.raw.read(current_chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    #print(gc.mem_free(),len(chunk))
                    gc.collect()  # Perform garbage collection to manage memory
                    #print(gc.mem_free(),len(chunk))
                    
                    now = time.ticks_ms()
                    elapsed_time = now - start_time
                    speed = (bytes_downloaded*1000) // elapsed_time if elapsed_time > 0 else 0
                    
                    #print_progress_bar(bytes_downloaded, total_size, speed)
                        
                    # Dynamic chunk size adjustment based on download speed
                    if speed > 0 and current_chunk_size < max_chunk_size:
                        current_chunk_size = min((speed * read_timeout), max_chunk_size)

            logger.info(f"Download of {filename} completed.", publish=True)
            
            gc.collect()
            time.sleep_ms(500)
            # verify the just downloaded file if checksum is given
            if checksum:
                if validate_checksum(filename, checksum, logger=logger):
                    logger.info("Checksum validation passed.", publish=True)
                    return True
                else:
                    logger.error("Checksum validation failed. Download might be corrupted.", publish=True)
                    return False
            
            return True # Exit function on successful download

        except OSError as e:
            logger.error("OS error occurred. Retrying...", publish=True)
            # Handle retry logic
            retry_count += 1
            if retry_count < max_retries:
                retry_interval = retry_delay * (2 ** (retry_count - 1))  # Exponential backoff
                logger.info(f"Retrying in {retry_interval} seconds...", publish=True)
                time.sleep(retry_interval)
            else:
                logger.error(f"Max retries exceeded. Failed to download {filename}.", publish=True)
            return False

        except Exception as e:
            print(f"\nUnexpected error: {e}")
            return False
        
        # NOTE: This 'finally' block is always executed once even if 'try' block succeeds, even if exception occurs in 'try' block or even if function returns in 'try' or 'except' block
        finally: # before retrying or exiting the function
            if response:
                response.close()  # Close the response to free up resources
            gc.collect()  # Perform garbage collection

# check if a file exists or not
def file_exists(filename):
    try:
        os.stat(filename)  # Try to get file stats
        return True
    except OSError:
        return False
        
# download and save the file in the microcontroller (by replacing its older version, if exists)    
def dwnld_and_update(url, filename, checksum=None,  # filename is the full filename of the file including the directory structure
                     logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
    time.sleep_ms(500)
    try:
        if download_large_file(url, filename, checksum=checksum, logger=logger):
            # some file manipulations
            if file_exists(filename):
                os.remove(filename) # remove the older version, if it exists
            os.rename(f'{filename}.new', filename)
            
            logger.info("Update successful.", publish=True)
            return True
    except Exception as e:
        logger.error(f"Error in updating: {e}", publish=True)
        return False
       
if __name__ == '__main__':
    import connect_wifi
    import utils
    import config
    
    # Initialize logger instance
    logger = Logger(debug_mode=config.DEBUG_MODE)
    
    try:
        # Connect to Wi-Fi
        wifi = utils.retry_with_backoff(connect_wifi.connect_to_wifi, config.wifi_networks, logger=logger)
        
        filename = 'README.md'
        
        url = f'https://raw.githubusercontent.com/{config.REPO_OWNER}/{config.REPO_NAME}/main/{filename}'
        
        if wifi and wifi.isconnected():
            dwnld_and_update(url, filename, checksum='e15bddc9a1414a16e414dd435c4c5375b696f9c6a5b59c2c032e351fb5990d8d', logger=logger)

    except Exception as e:
        logger.error(f"Error: {e}")
        