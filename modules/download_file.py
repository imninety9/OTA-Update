# download file OTA

import gc
import config
import urequests
from machine import reset
from time import sleep
import os

# function to download a file from github repo over the air
def dwnld_file(url, filename, chunk_size = 1024, max_retries=3): # Adjust chunk size (bytes)
    retry_count = 0
    while retry_count < max_retries:
        try:
            print("Starting download...")
            response = urequests.get(url, stream=True, timeout=15)
            if response.status_code == 200:
                print(f"Downloading {filename}")
                gc.collect()
                with open(f'{filename}.new', 'wb') as f:
                    while True:
                        chunk = response.raw.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        gc.collect()
                print(f"Download of {filename} completed.")
                return True
            else:
                print(f"HTTP status code: {response.status_code}")
                return False
        except OSError as e:
            print("OS error occurred. Retrying...")
            retry_count += 1
            if retry_count < max_retries:
                retry_interval = retry_delay * (2 ** (retry_count - 1))
                print(f"Retrying in {retry_interval} seconds...")
                sleep(retry_interval)
            else:
                print(f"Max retries exceeded. Failed to download {filename}.")
                return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            break
        finally: # before retrying
            if response:
                response.close() # close response to free up resources
            gc.collect()
    return False

def file_exists(filename):
    try:
        os.stat(filename)
        return True
    except OSError:
        return False
    
    
def dwnld_and_update(filename):
    sleep(1)
    try:
        url = f'https://raw.githubusercontent.com/{config.REPO_OWNER}/{config.REPO_NAME}/main/{filename}'
        if dwnld_file(url, filename):
            # some file manipulations
            if file_exists(filename):
                os.remove(filename)
            os.rename(f'{filename}.new', filename)
            
            print("Update successful. Restarting...")
            sleep(10)
            reset()
    except Exception as e:
        print(f"Error in main function: {e}")
        
if __name__ == '__main__':
    dwnld_and_update()
