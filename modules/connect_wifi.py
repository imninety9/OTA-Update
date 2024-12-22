# connect wifi
'''
This code is given a list of wifi networks with their priorities;
it then connects to the network with the highest priority which
has internet connectivity, if it is not already connected to a network
that has internet connectivity.
'''

import network
import usocket
from time import sleep

import utils
import config
from custom_exceptions import SetupError

from simple_logging import Logger  # Import the logger
# Initialize logger
logger = Logger(debug_mode = config.DEBUG_MODE)

# Internet connectivity check
def check_internet(hosts=[("8.8.8.8", 53), ("1.1.1.1", 53)], timeout=3):
    """Check if the device has internet connectivity by attempting to open a socket to a DNS server."""
    '''Added a fallback to a secondary server (e.g., Cloudflare 1.1.1.1) in case the primary check fails.'''
    for host, port in hosts:
        try:
            sock = usocket.socket()
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.close()
            logger.log_message("INFO", f"Internet check successful with {host}:{port}.")
            return True
        except Exception as e:
            logger.log_message("ERROR", f"Failed to connect to {host}:{port}: {e}")
    logger.log_message("ERROR", "Internet check failed for all hosts.")
    return False
    '''
    Explanation-
    usocket.socket(): Creates a socket object to establish a connection.
    sock.settimeout(timeout): This ensures that the socket does not block for too long (thus reducing power usage).
    sock.connect((host, port)): Attempts to connect to the specified host and port. Google DNS (8.8.8.8) on port 53 is commonly used because it's reliable and always reachable.
    sock.close(): Closes the socket after use to free up resources.
    Timeout: If the connection attempt fails (e.g., due to no internet), it will raise an exception, and the function will return False.
    '''

# Disable access point (AP) mode if required
def disable_ap_mode():
    try:
        ap = network.WLAN(network.AP_IF)
        if ap.active():
            ap.active(False)
            logger.log_message("INFO", "WiFi AP mode disabled.")
    except Exception as e:
        logger.log_message("ERROR", f"Failed to disable WiFi AP mode: {e}")

# Connect to a WiFi given a list of wifi_networks with their ssid and priority
def connect_to_wifi(wifi_networks):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    try:
        if wlan.isconnected():
            logger.log_message("INFO", f"Already connected to {wlan.config('essid')}")
            if check_internet():
                logger.log_message("INFO", "Internet is accessible.")
                return wlan # DONE, already connected to a network with internet connectivity (it may not be in the wifi_networks list)
            else:
                logger.log_message("WARNING", "Connected WiFi has no internet. Disconnecting...")
                wlan.disconnect()
    except Exception as e:
        logger.log_message("ERROR", f"Error while checking initial connection: {e}")

    logger.log_message("INFO", "Scanning for available networks...")
    try:
        available_networks = wlan.scan()
        available_ssids = {net[0].decode('utf-8') for net in available_networks}
    except Exception as e:
        logger.log_message("ERROR", f"Error during WiFi scan: {e}")
        return None
    
    # Sort given networks by priority (highest first) [uncomment if not pre-sorted]
    #wifi_networks.sort(key=lambda x: x['priority'], reverse=True)
    for wifi_network in wifi_networks: # wifi_networks is the list of networks given with their priority
        try:
            if wifi_network['ssid'] in available_ssids:
                logger.log_message("INFO", f"Trying to connect to {wifi_network['ssid']}...")
                wlan.connect(wifi_network['ssid'], wifi_network['password'])

                timeout = 10  # seconds
                for _ in range(timeout):
                    if wlan.isconnected():
                        logger.log_message("INFO", f"Connected to {wifi_network['ssid']}. Checking internet...")
                        if check_internet():
                            logger.log_message("INFO", "Internet is accessible.")
                            return wlan
                        else:
                            logger.log_message("WARNING", "No internet. Disconnecting...")
                            wlan.disconnect()
                            break
                    sleep(1)

                logger.log_message("WARNING", f"Failed to connect to {wifi_network['ssid']}")
        except Exception as e:
            logger.log_message("ERROR", f"Error during WiFi connection attempt: {e}")
            continue
            
    logger.log_message("ERROR", "Unable to connect to any given WiFi network.")
    return None

# Main execution
if __name__ == "__main__":
    try:
        disable_ap_mode()
        wifi = utils.retry_with_backoff(connect_to_wifi, config.wifi_networks, long_sleep_duration=config.LONG_SLEEP_DURATION)
    except SetupError as se:
        logger.log_error("CRITICAL", f"Setup error occurred: {se}. Resetting the Device...")
        utils.reset()
    except Exception as e:
        logger.log_message("CRITICAL", f"Error occurred: {e}")