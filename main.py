# main.py

# NOTE: "openweathermap" updates its 'real time weather' only each 10 minutes, so
#       its useless to make api call each 60sec or so. Hence we will keep a
#       cache of the previous api call and only make the api calls each 10 minute.
#         Although real time weather data would not be as real but it is alright.

# Improvements:
# 1. implement a watchdog timer
# 2. find a better way to retry update ntptime because ISR is too complicated and time consuming right now


import machine
from time import sleep, localtime, mktime
import urequests
from ntptime import host, settime

import gc
gc.collect()

# to enable imports from a subfolder named 'modules'
import sys
sys.path.append('/modules')

import connect_wifi
import mqtt_functions
import sensors
import utils
import config # configuration file
from custom_exceptions import SetupError, MQTTPublishingError
from download_file import dwnld_and_update
from led import LED

from simple_logging import Logger  # Import the Logger class
# Initialize logger instance
logger = Logger(debug_mode=config.DEBUG_MODE)

# Adafruit feeds
AIO_FEED_TEMP = None
AIO_FEED_HUM = None
AIO_FEED_TEMP_OUT = None
AIO_FEED_FEELS_LIKE_TEMP_OUT = None
AIO_FEED_HUM_OUT = None
AIO_FEED_PRESS_OUT = None
AIO_FEED_TEMP_BMP = None
AIO_FEED_PRESS = None
AIO_FEED_STATUS = None # feed for errors and status
AIO_FEED_COMMAND = None  # Feed for subscription to recieve commands

# openweathermap api
url = None

led = None

'''
Introducing a state machine-
NORMAL: All features are functional.
DEGRADED: Running with limited functionality.
MAINTENANCE: Enter maintenance mode due to persistent issues.
'''
SYSTEM_STATE = "NORMAL"


# Generate Adafruit IO feed variables and openweathermap url based on config data
def generate_aio_feeds_and_url(AIO_USER, owm_api_key, lat, long):
    global AIO_FEED_TEMP, AIO_FEED_HUM, AIO_FEED_TEMP_OUT, AIO_FEED_FEELS_LIKE_TEMP_OUT, AIO_FEED_HUM_OUT, AIO_FEED_PRESS_OUT, AIO_FEED_TEMP_BMP, AIO_FEED_PRESS, AIO_FEED_STATUS, AIO_FEED_COMMAND, url
    try:
        AIO_FEED_TEMP = AIO_USER + b"/feeds/Temp"
        AIO_FEED_HUM = AIO_USER + b"/feeds/Humidity"
        AIO_FEED_TEMP_OUT = AIO_USER + b"/feeds/Temp_out"
        AIO_FEED_FEELS_LIKE_TEMP_OUT = AIO_USER + b"/feeds/Temp_feels_like"
        AIO_FEED_HUM_OUT = AIO_USER + b"/feeds/Humidity_out"
        AIO_FEED_PRESS_OUT = AIO_USER + b"/feeds/Pressure_out"
        AIO_FEED_TEMP_BMP = AIO_USER + b"/feeds/Temp_bmp"
        AIO_FEED_PRESS = AIO_USER + b"/feeds/Pressure"
        AIO_FEED_STATUS = AIO_USER + b"/feeds/Status"
        AIO_FEED_COMMAND = AIO_USER + b"/feeds/Command"

        url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={long}&appid={owm_api_key}&units=metric"
    except Exception as e:
        logger.log_message("ERROR", f"Failed to initialize variables: {e}")
        raise SetupError("Failed to generate variables")
    
# sync rtc with ntp server (internet is needed for this)
def sync_time_with_ntp(ntp_retry_timer, attempt = 0, max_attempts = 3):
    try:
        host = 'pool.ntp.org' # UTC
        settime() # set rtc to UTC
        # mktime returns sec from epoch given date and time tuple
        current_time_ist = localtime(mktime(localtime()) + 19800) # IST = UTC + 19800 (in sec)
        # NOTE: tuple formats for time module (i.e. localtime() = (year, month, mday, hour, minute, second, weekday, yearday));
        #       and RTC module (i.e. datetime() = (year, month, day, weekday, hours, minutes, seconds, subseconds)) are different 
        current_time_ist = (current_time_ist[0], current_time_ist[1], current_time_ist[2],
                          current_time_ist[6], current_time_ist[3], current_time_ist[4],
                          current_time_ist[5], 0) # acc. to datetime tuple format
        rtc = machine.RTC()
        rtc.datetime(current_time_ist)
        logger.log_message("INFO", "RTC time synced with NTP")
        ntp_retry_timer.deinit()
        return
    except Exception as e:
        logger.log_message("ERROR", f'Failed to sync time with NTP in attempt {attempt}: {e}, Retrying after some time...')
        # retry using Timer - after setting the timer, current instance of the function returns
        if attempt < max_attempts:
            ntp_retry_timer.init(period=(2**attempt)*240 * 1000, mode=machine.Timer.ONE_SHOT, callback=lambda t: sync_time_with_ntp(ntp_retry_timer, attempt + 1, max_attempts))
        else:
            logger.log_message("ERROR", "Maximum number of retries reached. RTC syncing with NTP failed.")
            ntp_retry_timer.deinit()
            
# fetch outside weather data using openweathermap api
def fetch_weather_data():
    global weather_fetch_counter
    global last_weather_data
    try:
        if weather_fetch_counter >= (WEATHER_FETCH_DELAY-1):
            #utils.log_memory(logger) # DEBUG
            response = urequests.get(url)#, timeout=10)
            weather_data = response.json()
            response.close()
            #utils.log_memory(logger)
            if 'main' in weather_data:
                temperature = weather_data['main']['temp']
                feels_like_temp = weather_data['main']['feels_like']
                humidity = weather_data['main']['humidity']
                pressure = weather_data['main']['pressure'] * 100  # Convert hPa to Pa
            else:
                temperature = feels_like_temp = humidity = pressure = None
            last_weather_data = [temperature, feels_like_temp, humidity, pressure]
            weather_fetch_counter = 0
        else:
            weather_fetch_counter += 1
        return last_weather_data
    except OSError as e:
        logger.log_message("ERROR", f"HTTP request failed while fetching weather data: {e}", publish=True)
        return last_weather_data
    except Exception as e:
        logger.log_message("ERROR", f"Error fetching weather data: {e}", publish=True)
        return last_weather_data
    
# function to gather and oragnize publishing data
def gather_and_organize_data(sensors_data):
    try:
        sensor_readings = sensors.read_sensors(sensors_data, logger)
        
        weather_out_data = fetch_weather_data()
        temperature_out, feels_like_temp_out, humidity_out, pressure_out = weather_out_data  
        
        data = {}
        data[AIO_FEED_TEMP] = str(sensor_readings['temperature_aht'])
        data[AIO_FEED_HUM] = str(sensor_readings['humidity'])
        data[AIO_FEED_TEMP_OUT] = str(temperature_out)
        data[AIO_FEED_FEELS_LIKE_TEMP_OUT] = str(feels_like_temp_out)
        data[AIO_FEED_HUM_OUT] = str(humidity_out)
        data[AIO_FEED_PRESS_OUT] = str(pressure_out)
        data[AIO_FEED_TEMP_BMP] = str(sensor_readings['temperature_bmp'])
        data[AIO_FEED_PRESS] = str(sensor_readings['pressure'])
        
        return data
    except Exception as e:
        logger.log_message("ERROR", f"Failed to gather and organize data: {e}", publish=True)
    

# callback function for subscription feed
# NOTE: We are using global variable 'logger' inside callback function
def feed_callback(feed, msg):
    """Callback for MQTT received message."""
    '''
        feed: the subscribed feed or topic
        msg: the received message
    '''
    try:
        feed = feed.decode('utf-8')
        msg = msg.decode('utf-8')
        logger.log_message("INFO", f"Received message on {feed}: {msg}", publish=True)
        
        if msg.strip().lower() == "reboot":
            logger.log_message("INFO", "Reboot command received. Rebooting now...", publish=True)
            sleep(1)  # Short delay before rebooting
            machine.reset()
        
        elif msg.strip().split("-")[0] == "update":
            logger.log_message("INFO", "Update command received. Updating now...", publish=True)
            sleep(1)  # Short delay before updating
            if led:
                led.start_flashing()
            if dwnld_and_update(msg.strip().split("-")[-1], logger): # if successful, then reboot to apply update
                logger.log_message("INFO", "Resetting to apply the update.", publish=True)
                sleep(1)
                machine.reset() # Short delay before rebooting
            else:
                """maybe apply some retry logic"""
                pass
            if led:
                led.stop_flashing()
                
            
        elif msg.strip().lower() == "toggleled":
            if led:
                led.toggle()
                logger.log_message("INFO", "LED toggled.", publish=True)
            else:
                logger.log_message("INFO", "No LED found.", publish=True)
            
        elif msg.strip().lower() == "logs":
            '''send logs'''
            pass
        
        elif msg.strip().lower() == "maintenance":
            '''enter maintenance mode'''
            pass
        
    except Exception as e:
        logger.log_message("ERROR", f"Failed to execute the received message: {e}", publish=True)
    
def setup_with_retry(function, *args, max_retries=config.MAX_RETRIES, backoff_base=config.BACKOFF_BASE, light_sleep_duration=config.LONG_SLEEP_DURATION, **kwargs): # *args, **kwargs are the arguments, ketword arguments of the function
    '''this functions handles any given setup function with retries'''
    try:
        result = utils.retry_with_backoff(logger, function, *args, max_retries=max_retries, backoff_base=backoff_base, **kwargs)
        if result:
            return result # setup of given function successful
        else: # take critical action if all retries failed for the function i.e. None is returned by retry_with_backoff function
            logger.log_message("CRITICAL", f"Max retries reached for {function.__name__}. Entering light sleep for {light_sleep_duration} ms.")
            
            if led:
                # indicate that the system is in critical state
                led.on()
            # enter light sleep
            utils.light_sleep(light_sleep_duration, logger) # light sleep for some given time
            if led:
                # indicate that the system has woken up by switching led off
                led.off()
            
            raise SetupError(f"Setup of {function.__name__} failed") # after waking up raise the setup error
    
    except Exception as e:
        logger.log_message("CRITICAL", f"Error during setup function: {e}.")
        raise SetupError("Setup Function Failed")


    
#################################################################################################
#+++++++++++++++++++++++++++++ MAIN +++++++++++++++++++++++++++#
WEATHER_FETCH_DELAY = 10 # minutes
weather_fetch_counter = WEATHER_FETCH_DELAY # this counter will ensure that we only fetch real time weather from api each WEATHER_FETCH_DELAY
last_weather_data = [None, None, None, None] # cache the last weather data
# Main function
def main():
    global logger
    global led
    
    print("Restarted!!!")
    sleep(5)
    
    logger.log_message("DEBUG", "Restarted!!!")
    
    cause = utils.reset_cause(logger) # reset cause
    
    #=====================================================================================
    #++++++++++++++++++++++++ SET-UP ++++++++++++++++++++#
    # SET-UP
    try:
        if config.LED_PIN:
            led = LED(config.LED_PIN, logger)
            logger.log_message("INFO", "LED initialized successfully.")
            
        # Generate AIO FEED and url variables
        generate_aio_feeds_and_url(config.AdafruitIO_USER, config.owm_api_key, config.latitude, config.longitude)
        
        # connect to wifi
        wifi = setup_with_retry(connect_wifi.connect_to_wifi, config.wifi_networks, logger, 
                                max_retries = 7, backoff_base = 15,
                                light_sleep_duration=config.LONG_SLEEP_DURATION)
            
        # sync rtc time with NTP server
        ntp_retry_timer = machine.Timer(-1)
        sync_time_with_ntp(ntp_retry_timer) # we only need to do this once, until device remains powered
        
        # Initialize MQTT
        client = setup_with_retry(mqtt_functions.init_mqtt,
                                    config.AdafruitIO_USER,
                                    config.AdafruitIO_SERVER,
                                    config.AdafruitIO_PORT,
                                    config.AdafruitIO_USER,
                                    config.AdafruitIO_KEY,
                                    config.KEEP_ALIVE_INTERVAL,
                                    AIO_FEED_COMMAND,  # LWT Topic
                                    config.LAST_WILL_MESSAGE,
                                    feed_callback,
                                    logger,
                                    max_retries = config.MAX_RETRIES,
                                    backoff_base = config.BACKOFF_BASE,
                                    light_sleep_duration=config.LONG_SLEEP_DURATION//4
                                    )
        
        # update the logger for publishing
        logger.mqtt_client = client
        logger.mqtt_feed = AIO_FEED_STATUS
        
        # Connect to MQTT broker
        if client and wifi.isconnected():
            setup_with_retry(mqtt_functions.connect_mqtt, client, logger, 
                            max_retries = 7, backoff_base = config.BACKOFF_BASE,
                            light_sleep_duration=config.LONG_SLEEP_DURATION//2)
            # subscribe to the feed
            mqtt_functions.subscribe_feed(client, AIO_FEED_COMMAND, logger)
        
        # initialize the sensors with retry mechanism
        sensors_data = setup_with_retry(sensors.init_sensors, logger,
                                                    max_retries = config.MAX_RETRIES,
                                                    backoff_base = config.BACKOFF_BASE,
                                                    light_sleep_duration=config.LONG_SLEEP_DURATION//4)
        if any(data["sensor"] is None or not data["status"] for data in sensors_data.values()):
            #SYSTEM_STATE = "DEGRADED"
            logger.log_message("WARNING", "Some sensors are not active or failed to initialize. System in Degraded Mode.",publish=True)
    
    
        '''We are resetting the device for any error in setup, since this is critical for running of our project'''
        '''Improvement: 1. if we get consistent error during steup of some function; then device will keep resetting regularly.
                            Add some failsafe for this, such as running only with available resources if possible or just go into some maintenance mode.'''
    except SetupError as se:
        logger.log_message("CRITICAL", f"Setup error occurred: {se}. Resetting the Device...")
        sleep(10) # take a little break before resetting, to let actions like logging complete
        machine.reset()
    except Exception as e:
        logger.log_message("CRITICAL", f"Unhandled exception during setup: {e}. Resetting the Device...")
        sleep(10) # take a little break before resetting, to let actions like logging complete
        machine.reset()
    #=====================================================================================
    
    
    # log some one time info to Adafruit IO server, once connected
    try:
        mqtt_functions.publish_data(client, {AIO_FEED_STATUS: f"INFO - Reset cause: {cause}"}, logger)
    except Exception as e:
        logger.log_message("ERROR", f"Error publishing to Adafruit IO.")
    
    
    #=====================================================================================
    #++++++++++++++ LOOP ++++++++++++++++#
    # variable to keep track of the mqtt connection status
    MQTT_CONN = True
    # Loop
    while True:
        try:
            if SYSTEM_STATE == "NORMAL": # Normal Mode
                # Normal operation
                try:
                    if not wifi.isconnected():
                        log_message("WARNING", "Device status: Disconnected from Wi-Fi")
                        wifi = setup_with_retry(connect_wifi.connect_to_wifi, config.wifi_networks, logger, 
                                        max_retries = 7, backoff_base = 15,
                                        light_sleep_duration=config.LONG_SLEEP_DURATION)
                        
                        MQTT_CONN = False # since, wifi got disconnected
                    
                    if not MQTT_CONN and wifi.isconnected():
                        # reconnect to mqtt server
                        setup_with_retry(mqtt_functions.connect_mqtt, client, logger, 
                                    max_retries = 7, backoff_base = config.BACKOFF_BASE,
                                    light_sleep_duration=config.LONG_SLEEP_DURATION//2)
                        # re-subscribe to the feed
                        mqtt_functions.subscribe_feed(client, AIO_FEED_COMMAND, logger)
                    
                    try:
                        client.check_msg() # Check for any incoming MQTT messages (will raise an error if mqtt connection is lost)
                    except OSError as e:
                        logger.log_message("ERROR", f"MQTT check message error (OSError): {e}")
                        MQTT_CONN = False
                    except Exception as e:
                        logger.log_message("ERROR", f"MQTT check message error (Other): {e}")
                        MQTT_CONN = False
                    
                    # publish the data to mqtt server
                    mqtt_functions.publish_data(client, gather_and_organize_data(sensors_data), logger)
                    gc.collect()
                
                except MQTTPublishingError as mpe:
                    logger.log_message("CRITICAL", f"MQTT data publishing error occurred: {mpe}. Reconnect the mqtt client.")
                    MQTT_CONN = False
                    
                except SetupError as se:
                    logger.log_message("CRITICAL", f"Setup error occurred: {se}. Resetting the Device...")
                    sleep(10) # take a little break before resetting, to let actions like logging complete
                    machine.reset()
                
                except Exception as e:
                    logger.log_message("ERROR", f"Unknown main loop exception: {e}", publish=True)
                    sleep(5) # short delay before retrying; to handle any issues gracefully.
                sleep(config.UPDATE_INTERVAL) # Adjust as per rquirement
            
            elif SYSTEM_STATE == "DEGRADED": # degraded mode
                # Limited functionality
                '''handle degraded mode'''
                # handle_degraded_operation()
                # like regular attept to recover sensors 
                
            elif SYSTEM_STATE == "MAINTENANCE": # maintenace mode
                # Enter maintenance mode
                '''handle maintenance mode'''
                # enter_maintenance_mode()
        
        except Exception as e:
            logger.log_message("ERROR", f"Exception occurred: {e}. Enter maintenace mode.")
            '''enter maintenance mode'''    
       #=====================================================================================     
#################################################################################################
            
if __name__ == "__main__":
    main()
