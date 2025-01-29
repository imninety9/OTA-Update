# main.py

# NOTE: "openweathermap" updates its 'real time weather' only each 10 minutes, so
#       its useless to make api call each 60sec or so. Hence we will keep a
#       cache of the previous api call and only make the api calls each 10 minute.
#         Although real time weather data would not be as real but it is alright.

# Improvements:
# 1. implement a watchdog timer
# 2. find a better way to retry update ntptime because ISR is too complicated and time consuming right now


import machine
from time import sleep, localtime, mktime, time
import urequests
from ntptime import settime

import gc
gc.collect()

# to enable imports from a subfolder named 'modules'
import sys
sys.path.append('/modules')

import connect_wifi
import mqtt_functions
from sensors_handler import Sensors
import utils
import config # configuration file
from custom_exceptions import SetupError, MQTTPublishingError
from download_file import dwnld_and_update
from led import LED
from ds3231rtc import ds3231

from simple_logging import Logger  # Import the Logger class

# Topics/Feeds
FEED_AHT_TEMP = config.mqtt[config.BROKER]["feeds"]["aht"]["temp"]
FEED_AHT_HUM = config.mqtt[config.BROKER]["feeds"]["aht"]["hum"]
FEED_OUT_TEMP = config.mqtt[config.BROKER]["feeds"]["out"]["temp"]
FEED_OUT_FEELS_LIKE_TEMP = config.mqtt[config.BROKER]["feeds"]["out"]["feels_like_temp"]
FEED_OUT_HUM = config.mqtt[config.BROKER]["feeds"]["out"]["hum"]
FEED_OUT_PRESS = config.mqtt[config.BROKER]["feeds"]["out"]["press"]
FEED_BMP_TEMP = config.mqtt[config.BROKER]["feeds"]["bmp"]["temp"]
FEED_BMP_PRESS = config.mqtt[config.BROKER]["feeds"]["bmp"]["press"]
FEED_DS18B20_TEMP = config.mqtt[config.BROKER]["feeds"]["ds18b20"]["temp"]
FEED_STATUS = config.mqtt[config.BROKER]["feeds"]["status"] # feed for errors and status
FEED_COMMAND = config.mqtt[config.BROKER]["feeds"]["command"] # Feed for subscription to recieve commands  

# outside weather api
WEATHER_PROVIDER = config.weather_provider # 1 for openweathermap, 2 for tomorrow.io
URL, HEADERS = (config.OWM_URL, config.OWM_HEADERS) if WEATHER_PROVIDER is 1 else (config.TOM_URL, config.TOM_HEADERS)

'''
Introducing a state machine-
0: NORMAL: All features are functional.
1: DEGRADED: Running with limited functionality.
2: MAINTENANCE: Enter maintenance mode due to persistent issues.
'''
SYSTEM_STATE = 0

    
# sync rtc with ntp server (internet is needed for this)
def sync_time_with_ntp(ntp_retry_timer, attempt = 0, max_attempts = 3,
                       logger: Logger = None): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of None]
    try:
        settime() # set rtc to UTC [host = 'pool.ntp.org']
        # mktime returns sec from epoch given date and time tuple
        current_time_ist = localtime(mktime(localtime()) + 19800) # IST = UTC + 19800 (in sec)
        # NOTE: tuple formats for time module (i.e. localtime() = (year, month, mday, hour, minute, second, weekday, yearday));
        #       and RTC module (i.e. datetime() = (year, month, day, weekday, hours, minutes, seconds, subseconds)) are different 
        current_time_ist = (current_time_ist[0], current_time_ist[1], current_time_ist[2],
                          current_time_ist[6], current_time_ist[3], current_time_ist[4],
                          current_time_ist[5], 0) # acc. to datetime tuple format
        rtc = machine.RTC()
        rtc.datetime(current_time_ist)
        logger.info("RTC time synced with NTP")
        ntp_retry_timer.deinit()
        return
    except Exception as e:
        logger.error(f'Failed to sync time with NTP in attempt {attempt}: {e}, Retrying after some time...')
        # retry using Timer - after setting the timer, current instance of the function returns
        if attempt < max_attempts:
            ntp_retry_timer.init(period=(2**attempt)*240 * 1000, mode=machine.Timer.ONE_SHOT, callback=lambda t: sync_time_with_ntp(ntp_retry_timer, attempt=attempt + 1, max_attempts=max_attempts, logger=logger))
        else:
            logger.error("Maximum number of retries reached. RTC syncing with NTP failed.")
            ntp_retry_timer.deinit()

# heat index - calculates heat index given dry bulb temperature (in C) and relative humidity [source: wikipedia]
# Note: 1. The formula below approximates the heat index within 0.7 °C (except the values at 32 °C & 45%/70% relative humidity vary unrounded by less than ±1, respectively).
#       2. the equation described is valid only if the temperature is 27 °C or more and The relative humidity threshold is commonly set at an arbitrary 40%
#       3. Exposure to full sunshine can increase heat index values by up to 8 °C
'''
Effects of the heat index (shade values):
Temperature    Notes
27–32 °C       Caution: fatigue is possible with prolonged exposure and activity. Continuing activity could result in heat cramps.
32–41 °C       Extreme caution: heat cramps and heat exhaustion are possible. Continuing activity could result in heat stroke.
41–54 °C       Danger: heat cramps and heat exhaustion are likely; heat stroke is probable with continued activity.
over 54 °C     Extreme danger: heat stroke is imminent.
'''
def heat_index(temp, rh):
    if temp<27 or rh<40:
        return None
    temp2 = temp**2
    rh2 = rh**2
    hi = -8.78469475556 + 1.61139411*temp + 2.33854883889*rh - 0.14611605*temp*rh -\
         0.012308094*temp2 - 0.0164248277778*rh2 + 2.211732e-3*temp2*rh +\
         7.2546e-4*temp*rh2 - 3.582e-6*temp2*rh2
    if hi >= 54:
        level = 4
    elif hi >= 41:
        level = 3
    elif hi >= 32:
        level = 2
    elif hi >= 27:
        level = 1
    else:
        level = None
    return hi, level
    
# fetch outside weather data using openweathermap api
def fetch_weather_data(url, headers):
    try:
        #utils.log_memory(logger) # DEBUG
        response = urequests.get(url, headers=headers, timeout=15) # wait for 10 sec for a response from the server else it will raise OSError; [otherwise without timeout, the program may hang here for a very long indefinite time in case server does not respond due to unreliable network, etc]
        weather_data = response.json()
        response.close()
        #utils.log_memory(logger)
        
        if WEATHER_PROVIDER==1:
            # openweathermap
            if (response.status_code == 200 and 'main' in weather_data):
                temperature = weather_data['main']['temp']
                feels_like_temp = weather_data['main']['feels_like']
                humidity = weather_data['main']['humidity']
                pressure = weather_data['main']['grnd_level'] * 100  # Convert hPa to Pa [ground level pressure]
            else:
                temperature = feels_like_temp = humidity = pressure = None
        elif WEATHER_PROVIDER==2:
            # tomorrow.io
            if (response.status_code == 200 and 'data' in weather_data):
                temperature = weather_data['data']['values']['temperature']
                feels_like_temp = weather_data['data']['values']['temperatureApparent'] # feels like temp
                humidity = weather_data['data']['values']['humidity'] # % RH
                pressure = weather_data['data']['values']['pressureSurfaceLevel'] * 100 # Pa [at surface level not sea level]
            else:
                temperature = feels_like_temp = humidity = pressure = None
                
        return [temperature, feels_like_temp, humidity, pressure]
    except OSError as e:
        raise OSError(f"HTTP request failed or timed out while fetching weather data: {e}")
    except Exception as e:
        raise Exception (f"Error fetching weather data: {e}")

# helper function - format sensor and other readings to .2f string, for consistent formatting and publication to mqtt feed
def format_value(value, precision=2):
    """
    Formats the sensor and other reading:
    - Leaves integers unchanged.
    - Formats floats to the specified number of decimal places.
    """
    if value is None:
        return str(value)
    elif isinstance(value, int):
        return str(value)  # Keep integers as is
    elif isinstance(value, float):
        return f"{value:.{precision}f}"  # Format floats
    else:
        raise TypeError(f"Unsupported data type: {type(value)}")
    
# function to gather and oragnize publishing data
def gather_and_organize_data(sensors,
                             logger: Logger = None): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of None]
    global weather_fetch_counter
    global last_weather_data
    
    data = {}
    try:
        # fetch new outside weather data and update the cached weather data, if fetching has been successful, else just publish the old cached weather data
        if weather_fetch_counter + INTERVAL >= WEATHER_FETCH_DELAY:
            try:
                last_weather_data = fetch_weather_data(URL, HEADERS) # update the cached weather data
                weather_fetch_counter -= WEATHER_FETCH_DELAY # also update weather_fetch_counter, if fetch_weather_data() is executed successfully, else not
                # last_weather_data is a list in the format: [temperature_out, feels_like_temp_out, humidity_out, pressure_out]
            except Exception as e: # catch errors
                logger.error(f"{e}", publish=True)
        else:
            # keeping this line here inside 'else' block [rather than at the start i.e. before the 'if' statement and then changing the 'if' conditon to weather_fetch_counter >= WEATHER_FETCH_DELAY]
            # ensures that if there is a persistent exception in trying to fetch weather data; then still weather_fetch_counter does not keep increasing indefinitely
            # [because anything that has happened inside the 'try' block before the exception occurs, does not reverses like changing the value of a variable etc]
            weather_fetch_counter += INTERVAL
        
        sensor_readings = sensors.read_measurements()
        
        data[FEED_AHT_TEMP] = format_value(sensor_readings['aht25'][0])
        data[FEED_AHT_HUM] = format_value(sensor_readings['aht25'][1])
        data[FEED_BMP_TEMP] = format_value(sensor_readings['bmp280'][0])
        data[FEED_BMP_PRESS] = format_value(sensor_readings['bmp280'][1])
        data[FEED_DS18B20_TEMP] = format_value(sensor_readings['ds18b20'])
        data[FEED_OUT_TEMP] = format_value(last_weather_data[0])
        data[FEED_OUT_FEELS_LIKE_TEMP] = format_value(last_weather_data[1])
        data[FEED_OUT_HUM] = format_value(last_weather_data[2])
        data[FEED_OUT_PRESS] = format_value(last_weather_data[3])      
        return data
    
    except Exception as e:
        logger.error(f"Failed to gather and organize data: {e}", publish=True)
        return data
    

# callback handler: we are creating a callback handler class so that we can
#                    can access some variables inside the callback function
#                    that can not be passed to it.
#                    Other option would be to use global variables but we are
#                    not using a lot of global variables in our code.
class CallbackHandler:
    def __init__(self, led, ds,
                 logger: Logger = None): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of None]
        self.led = led
        self.ds = ds
        self.logger = logger
        
    # callback function for subscription feed
    def feed_callback(self, feed, msg):
        """Callback for MQTT received message."""
        '''
            feed: the subscribed feed or topic
            msg: the received message
        '''
        global INTERVAL
        try:
            feed = feed.decode('utf-8')
            msg = msg.decode('utf-8')
            self.logger.info(f"Received message on {feed}: {msg}", publish=True)
            
            # split the message into separate parts if present
            msg = msg.split("-")
            msg = [part.strip() for part in msg]
            instruction = msg[0].lower() # the first part of the message will be instruction
            
            if instruction == "reboot":
                self.logger.info("Reboot command received. Rebooting now...", publish=True)
                sleep(1)  # Short delay before rebooting
                machine.reset()
            
            elif instruction == "update":
                self.logger.info("Update command received. Updating now...", publish=True)
                sleep(1)  # Short delay before updating
                if self.led: self.led.start_flashing()
                
                filename = msg[1]
                
                if len(msg) == 3: checksum = msg[2]
                else: checksum = None
                
                link = f'http://raw.githubusercontent.com/{config.REPO_OWNER}/{config.REPO_NAME}/main/{filename}' # Note: we are using http request rather than https to reduce computation on esp32
                if dwnld_and_update(link, filename, checksum=checksum, logger=self.logger): # if successful, then reboot to apply update
                    self.logger.info("Resetting to apply the updates.", publish=True)
                    if self.led: self.led.stop_flashing()
                    sleep(1) # Short delay before rebooting
                    machine.reset()
                else:
                    """maybe apply some retry logic"""
                    if self.led: self.led.stop_flashing()
                    return
                
            elif instruction == "toggleled":
                if self.led:
                    self.led.toggle()
                    self.logger.info("LED toggled.", publish=True)
                else:
                    self.logger.warning("No LED found.", publish=True)
                return
                
            elif instruction == "changeinterval": # change weather update interval for this session "changeinterval-60"
                INTERVAL = int(msg[1])
                self.logger.info(f"Changed the update interval for this session to {msg[1]} sec.", publish=True)
                return
            
            elif instruction == "syncds3231": # sync ds3231 with ntp server
                if self.ds:
                    self.ds.sync_time_with_ntp()
                    self.logger.info(f"Synced DS3231 time with NTP server.", publish=True)
                else:
                    self.logger.warning(f"DS3231 not available.", publish=True)
                return
            
            elif instruction == "config": # change parameter values of one or multiple parameters in config.py
                # Note: parameters and their new values are supposed to be in string representation of a Python dictionary
                new_parameters = CallbackHandler.python_dict_str_to_json_to_python_dict(msg[1])
    
                if CallbackHandler.replace_lines_in_file('modules/config.py', new_parameters):
                    self.logger.info(f"Replaced '{new_parameters}' in config.py.", publish=True)
                    sleep(1) # Short delay before rebooting
                    machine.reset() # reboot to apply changes
                else:
                    self.logger.info(f"No matching line found for '{new_parameters}'.", publish=True)
                
            elif instruction == "logs":
                '''send logs'''
                pass
            
            elif instruction == "maintenance":
                '''enter maintenance mode'''
                pass
            
        except Exception as e:
            self.logger.error(f"Failed to execute the received message: {e}", publish=True)
    
    @staticmethod
    def replace_lines_in_file(file_path, new_lines):
        """
        Replace a specific line in a file efficiently for large files.

        Parameters:
        - file_path: Path to the file to modify.
        - new_lines: Lines to be replaced.
        """
        modified = False  # Track if any changes are made
        
        # Open the original file for reading and a new file for writing
        temp_file_path = file_path + '.tmp'

        with open(file_path, 'r') as file, open(temp_file_path, 'w') as temp_file:
            for line in file:
                parameter = line.split('=')[0].strip()
                if parameter in new_lines:
                    if '#' in line:
                        comment = line.split('#', 1)[-1]
                        temp_file.write(f'{parameter} = {new_lines[parameter]} #{comment}\n')
                    else:
                        temp_file.write(f'{parameter} = {new_lines[parameter]}\n')
                    modified = True
                else:
                    temp_file.write(line)

        # Replace the original file with the temporary file
        if modified:
            import os
            os.remove(file_path)
            os.rename(temp_file_path, file_path)
            return True
        else:
            # Clean up the temporary file if no changes were made
            os.remove(temp_file_path)
            return False
    
    @staticmethod
    # convert a string representation of a Python dictionary to a Python dictionary by first converting it to a JSON
    def python_dict_str_to_json_to_python_dict(python_dict_str):
        import json
        import re
        # Use regex to replace True, False, and None with JSON equivalents
        python_dict_str = re.sub(r'\bTrue\b', 'true', python_dict_str)
        python_dict_str = re.sub(r'\bFalse\b', 'false', python_dict_str)
        python_dict_str = re.sub(r'\bNone\b', 'null', python_dict_str)
        # now convert JSON to python dict
        return json.loads(python_dict_str)
    
def setup_with_retry(function, *args,
                     max_retries=config.MAX_RETRIES,
                     backoff_base=config.BACKOFF_BASE,
                     light_sleep_duration=config.LONG_SLEEP_DURATION,
                     led=None,
                     logger: Logger = None, # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of None]
                     **kwargs): # *args, **kwargs are the arguments, ketword arguments of the function
    '''this functions handles any given setup function with retries'''
    try:
        result = utils.retry_with_backoff(function, *args, max_retries=max_retries, backoff_base=backoff_base, logger=logger, **kwargs)
        if result:
            return result # setup of given function successful
        else: # take critical action if all retries failed for the function i.e. None is returned by retry_with_backoff function
            logger.critical(f"Max retries reached for {function.__name__}. Entering light sleep for {light_sleep_duration} ms.")
            
            if led:
                # indicate that the system is in critical state
                led.on()
            sleep(1) # a little delay before entering lightsleep
            
            '''
            A NOTE ABOUT SLEEP MODES IN ESP32:
            
            "In deep sleep and light sleep modes, wireless peripherals are powered down. Before entering deep sleep or light sleep modes,
            applications must disable WiFi and BT using appropriate calls (esp_bluedroid_disable(), esp_bt_controller_disable(), esp_wifi_stop()).
            WiFi and BT connections will not be maintained in deep sleep or light sleep, even if these functions are not called."  --- a line from espressif docs
                
                This means that we should power down the wifi/bt chip explicitly before entering deep or light sleep modes (meaning powering down cpu)
            because they won't be maintained anyway. There is some confusion from my side - if light or deep sleep automatically power down wifi/bt chip too
            or not; any way just do it explicitly to be safe that we get maximum power savings.
                
                In micropython wlan.active(True) activates the wifi/bt chip; so wlan.active(False) will turn off the wifi radio: it calls the ESP-IDF function
            esp_wifi_stop() (and wlan.active(True) turns on the radio - use these to limit how long the radio is powered in battery sensitive operations).
            You only need to turn off BT if you have turned it on.
            Note - if anyone is using both the STA_IF and AP_IF interfaces, you need to turn them both off (even though they share the same radio).
            '''
            
            #connect_wifi.disable_sta_mode(logger) # first power of wifi chip, to conserve power
            # enter light sleep
            utils.light_sleep(light_sleep_duration, logger=logger) # light sleep for some given time
            if led:
                # indicate that the system has woken up by switching led off
                led.off()
            
            raise SetupError(f"Setup of {function.__name__} failed") # after waking up raise the setup error
    
    except Exception as e:
        logger.critical(f"Error during setup function: {e}.")
        raise SetupError("Setup Function Failed")


    
#################################################################################################
#+++++++++++++++++++++++++++++ MAIN +++++++++++++++++++++++++++#
WEATHER_FETCH_DELAY = 600 # seconds [since openweathermap updates its real time weather data only each 10 minutes]
weather_fetch_counter = WEATHER_FETCH_DELAY # this counter will ensure that we only fetch real time weather from api each WEATHER_FETCH_DELAY
last_weather_data = [None, None, None, None] # cache the last weather data

INTERVAL = config.UPDATE_INTERVAL # frequency of weather update (in ms)
# Main function
def main():    
    print("Restarted!!!")
    sleep(1)
    
    # Initialize logger instance
    logger = Logger(debug_mode=config.DEBUG_MODE, max_size_bytes=config.MAX_SIZE_BYTES, log_level=config.LOG_LEVEL)
    #logger.debug_mode=True
    
    logger.debug("Restarted!!!")
    
    cause = utils.reset_cause(logger=logger) # reset cause
    
    #=====================================================================================
    #++++++++++++++++++++++++ SET-UP ++++++++++++++++++++#
    # SET-UP
    try:
        # initialize ds3231 rtc
        ds = utils.retry_with_backoff(ds3231, config.softsclPIN, config.softsdaPIN,
                                      config.alarmPIN,
                                      max_retries=3, backoff_base=5,
                                      logger=logger)
        
        if ds:
            logger.ds3231rtc = ds # use ds3231rtc to take logger's timestamps
            ''' take care of the case when there is no mqtt connection and alarm fires;
                and alarm handler requires mqtt connectivity. although for now
                it will produce an error which will be handled without breaking
                the main loop (i think); but handle it such that it doesn't even
                produce an error.'''
            ds.set_alarm(1, hr=08, min=00, sec=00)
            #ds.set_alarm(2, week= 5, day=01, hr=00, min=00, sec=00)
        
        # initialize led
        led = None
        if config.LED_PIN:
            try:
                led = LED(config.LED_PIN, logger=logger)
            except:
                led = None
            
        # connect to wifi
        connect_wifi.disable_ap_mode(logger=logger) # first disable ap (access point) mode of wifi if active, we dont need it
        wifi = setup_with_retry(connect_wifi.connect_to_wifi, config.wifi_networks, 
                                max_retries = 7, backoff_base = 15,
                                light_sleep_duration=config.LONG_SLEEP_DURATION,
                                led=led,
                                logger=logger)
        
        if not ds: # fallback mechanism for ds3231 i.e. if ds3231 is not present or not initialized then use system rtc
            # sync rtc time with NTP server
            ntp_retry_timer = machine.Timer(-1)
            sync_time_with_ntp(ntp_retry_timer, logger=logger) # we only need to do this once, until device remains powered
        
        # create a callback handler instance
        feed_handler = CallbackHandler(led, ds, logger=logger)
        # Initialize MQTT
        client = setup_with_retry(mqtt_functions.init_mqtt,
                                    config.mqtt[config.BROKER]["client_id"],
                                    config.mqtt[config.BROKER]["server"],
                                    config.mqtt[config.BROKER]["port"],
                                    config.mqtt[config.BROKER]["user"],
                                    config.mqtt[config.BROKER]["password"],
                                    config.KEEP_ALIVE_INTERVAL,
                                    FEED_STATUS,  # LWT Topic
                                    config.LAST_WILL_MESSAGE,
                                    feed_handler.feed_callback,
                                    max_retries = config.MAX_RETRIES,
                                    backoff_base = config.BACKOFF_BASE,
                                    light_sleep_duration=config.LONG_SLEEP_DURATION//4,
                                    led=led,
                                    logger=logger
                                    )
        
        # update the logger for publishing
        logger.mqtt_client = client
        logger.mqtt_feed = FEED_STATUS
        
        # Connect to MQTT broker and suscribe to given feeds
        if client and wifi.isconnected():
            setup_with_retry(mqtt_functions.connect_and_subscribe, client, [FEED_COMMAND],
                            max_retries = config.MAX_RETRIES, backoff_base = config.BACKOFF_BASE,
                            light_sleep_duration=config.LONG_SLEEP_DURATION//2,
                            led=led,
                            logger=logger)
                
        # initialize the sensors with retry mechanism
        sensors = setup_with_retry(Sensors,
                                    max_retries = config.MAX_RETRIES,
                                    backoff_base = config.BACKOFF_BASE,
                                    light_sleep_duration=config.LONG_SLEEP_DURATION//4,
                                    led=led,
                                    logger=logger,
                                    i2cPins=(config.sclPIN, config.sdaPIN),
                                    onewirePin=config.ONEWIRE_PIN)
        if sensors.recovery_needed:
            #SYSTEM_STATE = 1 # "DEGRADED"
            logger.warning("Some sensors are not active or failed to initialize. System in Degraded Mode.",publish=True)
    
    
        '''We are resetting the device for any error in setup, since this is critical for running of our project'''
        '''Improvement: 1. if we get consistent error during steup of some function; then device will keep resetting regularly.
                            Add some failsafe for this, such as running only with available resources if possible or just go into some maintenance mode.'''
    except SetupError as se:
        logger.critical(f"Setup error occurred: {se}. Resetting the Device...")
        sleep(10) # take a little break before resetting, to let actions like logging complete
        machine.reset()
    except Exception as e:
        logger.critical(f"Unhandled exception during setup: {e}. Resetting the Device...")
        sleep(10) # take a little break before resetting, to let actions like logging complete
        machine.reset()
    #=====================================================================================
    
    
    # log some one time info to Adafruit IO server, once connected
    try:
        mqtt_functions.publish_data(client, {FEED_STATUS: f"INFO - Reset cause: {cause}"}, logger=logger)
    except Exception as e:
        logger.error(f"Error publishing to Adafruit IO.")
    
    
    #=====================================================================================
    #++++++++++++++ LOOP ++++++++++++++++#
    try:
        # variable to keep track of time of the last attempted recovery for sensors
        last_attempt_time = time()
        # variable to keep track of the mqtt connection status
        MQTT_CONN = True
        # Loop
        while True:
            if SYSTEM_STATE == 0: # Normal Mode
                # Normal operation
                try:
                    if sensors.recovery_needed and time()-last_attempt_time>1800: # each 30 minutes
                        sensors.attempt_recovery()
                        last_attempt_time = time()
                        sleep(1) # wait a little for recovered sensor's next reading
                        
                    if not wifi.isconnected():
                        logger.warning("Device status: Disconnected from Wi-Fi")
                        wifi = setup_with_retry(connect_wifi.connect_to_wifi, config.wifi_networks,
                                        max_retries = 7, backoff_base = 15,
                                        light_sleep_duration=config.LONG_SLEEP_DURATION,
                                        led=led,
                                        logger=logger)
                        
                        MQTT_CONN = False # since, wifi got disconnected
                    
                    if not MQTT_CONN and wifi.isconnected():
                        # reconnect to mqtt server and re-subscribe to feeds
                        setup_with_retry(mqtt_functions.connect_and_subscribe, client, [FEED_COMMAND],
                                    max_retries = config.MAX_RETRIES, backoff_base = config.BACKOFF_BASE,
                                    light_sleep_duration=config.LONG_SLEEP_DURATION//2,
                                    led=led,
                                    logger=logger)
                        MQTT_CONN = True
                    
                    try:
                        client.check_msg() # Check for any incoming MQTT messages (will raise an error if mqtt connection is lost)
                    except OSError as e:
                        logger.error(f"MQTT check message error (OSError): {e}")
                        if wifi.isconnected():
                            # reconnect to mqtt server and re-subscribe to feeds
                            setup_with_retry(mqtt_functions.connect_and_subscribe, client, [FEED_COMMAND],
                                        max_retries = config.MAX_RETRIES, backoff_base = config.BACKOFF_BASE,
                                        light_sleep_duration=config.LONG_SLEEP_DURATION//2,
                                        led=led,
                                        logger=logger)
                    except Exception as e:
                        logger.error(f"MQTT check message error (Other): {e}")
                        if wifi.isconnected():
                            # reconnect to mqtt server and re-subscribe to feeds
                            setup_with_retry(mqtt_functions.connect_and_subscribe, client, [FEED_COMMAND],
                                        max_retries = config.MAX_RETRIES, backoff_base = config.BACKOFF_BASE,
                                        light_sleep_duration=config.LONG_SLEEP_DURATION//2,
                                        led=led,
                                        logger=logger)
                    
                    # publish the data to mqtt server
                    mqtt_functions.publish_data(client, gather_and_organize_data(sensors, logger=logger), logger=logger)
                    gc.collect()
                
                except MQTTPublishingError as mpe:
                    logger.critical(f"MQTT data publishing error occurred: {mpe}. Reconnect the mqtt client.")
                    MQTT_CONN = False
                    
                except SetupError as se:
                    logger.critical(f"Setup error occurred: {se}. Resetting the Device...")
                    sleep(10) # take a little break before resetting, to let actions like logging complete
                    machine.reset()
                
                except Exception as e:
                    logger.error(f"Unknown main loop exception: {e}", publish=True)
                    
                except KeyboardInterrupt:
                    raise
                
                sleep(INTERVAL) # Adjust as per rquirement
            
            elif SYSTEM_STATE == 1: # degraded mode
                # Limited functionality
                '''handle degraded mode'''
                # handle_degraded_operation()
                # like regular attept to recover sensors 
                
            elif SYSTEM_STATE == 2: # maintenace mode
                # Enter maintenance mode
                '''handle maintenance mode'''
                # enter_maintenance_mode()
        
    except Exception as e:
        logger.error(f"Exception occurred: {e}. Enter maintenace mode.")
        '''enter maintenance mode'''
        
    except KeyboardInterrupt:
        logger.error("Keyboard interrupt by the user.")
        
    finally:
        if ds:
             ds.disable_alarm()
        if led:
            if led.flashing:
                led.stop_flashing()
            if led.sudden_blinking:
                led.stop_sudden_blink()
            led.off()
        
       #=====================================================================================     
#################################################################################################
            
if __name__ == "__main__":
    main()
    
    '''
    IMPROVEMENTS:
    1. Implement basic error handling to check if the wifi network is up before attempting a mqtt connection,
       in the mqtt_connect function, reducing unnecessary retries.
    2. Use Persistent Sessions:
        Set clean_session=False when connecting. This allows the broker to remember your subscriptions and pending messages (if any),
        so you don’t need to resubscribe on every reconnection. [Ensure that the broker allows for persistent
        sessions i.e. not every broker especially free tier cloud version keeps track of previous
        session or pending messages or subscriptions or even qos in many cases.]
    '''
