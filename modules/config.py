# configuration file

# List of WiFi networks with priorities (higher the better) [pre-sorted]
wifi_networks = [
    {"ssid": "s1", "password": "p1", "priority": 4},
    {"ssid": "s2", "password": "p2", "priority": 3},
    {"ssid": "s3", "password": "p3", "priority": 2},
    {"ssid": "s4", "password": "p4", "priority": 1},
]

# I2C Pins
sdaPIN = 21
sclPIN = 22

# SPI Pins
SPI_PIN_MISO = 19
SPI_PIN_MOSI = 23
SPI_PIN_SCK = 18
SPI_PIN_CS = 5

owm_api_key = 'key'
latitude = lat
longitude = long

AdafruitIO_USER = b'user'
AdafruitIO_KEY = 'key'
AdafruitIO_SERVER = 'io.adafruit.com'
AdafruitIO_PORT = 1883

KEEP_ALIVE_INTERVAL = 120 # sec

MAX_RETRIES = 5  # Max connection retries before long sleep
BACKOFF_BASE = 10  # Base seconds for exponential backoff
LONG_SLEEP_DURATION = 3600 * 1000 # millisec [= 1 hour]

LAST_WILL_MESSAGE = b"ESP32 disconnected unexpectedly"

LOG_FILE = '/errors.log' # '/sd/errors.log'
MAX_SIZE_BYTES = 100 * 1024  # in bytes (= 100 KB) [max allowed size of log files in bytes]

DEBUG_MODE = True

UPDATE_INTERVAL = 60 # sec [interval between weather readings update]

#########################
REPO_OWNER = 'imninety9'
REPO_NAME = 'OTA-Update'

