# logging of messages, etc with their flags

from time import localtime
import os

'''
DEBUG: Detailed information, typically of interest only when diagnosing problems.
INFO: Confirmation that things are working as expected.
WARNING: An indication that something unexpected happened, or indicative of some problem in the near future (e.g. ‘disk space low’). The software is still working as expected.
ERROR: Due to a more serious problem, the software has not been able to perform some function.
CRITICAL: A serious error, indicating that the program itself may be unable to continue running.
'''

class Logger:
    def __init__(self, log_file=None, mqtt_client=None, mqtt_feed = None,
                 debug_mode=True, max_size_bytes=100 * 1024, log_level='NOTSET',
                 ds3231rtc=None):
        """
        Initializes the Logger instance.
        
        :param log_file: Path to the log file
        :param mqtt_client: MQTT client to publish log messages
        :param mqtt_feed: MQTT feed/topic to publish messages
        :param debug_mode: Flag to enable/disable debugging
        :param max_size_bytes: Maximum log file size before rotation in bytes (default = 100 KB)
        :param log_level: Minimum log level for logging messages (e.g., 'INFO', 'DEBUG', 'ERROR')
        """
        self.log_file = log_file
        self.mqtt_client = mqtt_client
        self.mqtt_feed = mqtt_feed
        self.debug_mode = debug_mode
        self.max_size_bytes = max_size_bytes
        self.ds3231rtc = ds3231rtc
        self.log_level = log_level
        self.level_map = {
            'NOTSET': 0,
            'DEBUG': 1,
            'INFO': 2,
            'WARNING': 3,
            'ERROR': 4,
            'CRITICAL': 5
        }
        self.set_log_level(log_level)

    def set_log_level(self, log_level):
        """
        Sets the logging level dynamically.
        
        :param log_level: Desired log level as a string ('DEBUG', 'INFO', 'WARNING', etc.)
        """
        log_level = log_level.upper()
        self.current_level = self.level_map.get(log_level, 0)
        
    def get_timestamp(self):
        """Returns the current timestamp in ordered manner i.e. yyyy-mm-dd-hh-mm-ss."""
        try:
            if self.ds3231rtc:
                current_time = self.ds3231rtc.get_time()
            else:
                current_time = localtime()
            return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*current_time[:6])
        except:
            return None

    def log(self, level, message, publish = False):
        """
         Core logging method that logs the message at a given level and optional publishing.
        
        :param level: Log level (INFO, WARNING, ERROR, etc.)
        :param message: The log message to record
        :param publish: Flag to publish the log to MQTT
        """
        
        # Only log messages above the current log level
        if self.level_map[level] < self.current_level:
            return
        
        timestamp = self.get_timestamp()
        log_entry = f"{timestamp} - {level} - {message}"
        
        # Print for debugging
        if self.debug_mode:
            print(log_entry)
        
        # Log to file
        if self.log_file:
            self.log_to_file(log_entry)
        
        # Publish via MQTT if requested
        if publish and self.mqtt_client and self.mqtt_feed:
            self.publish_to_mqtt(log_entry)
            
    def info(self, message, publish=False):
        """Log an INFO message."""
        self.log('INFO', message, publish)

    def warning(self, message, publish=False):
        """Log a WARNING message."""
        self.log('WARNING', message, publish)

    def error(self, message, publish=False):
        """Log an ERROR message."""
        self.log('ERROR', message, publish)

    def critical(self, message, publish=False):
        """Log a CRITICAL message."""
        self.log('CRITICAL', message, publish)

    def debug(self, message, publish=False):
        """Log a DEBUG message."""
        self.log('DEBUG', message, publish)
    
    def log_to_file(self, log_entry):
        """Writes log entry to the file."""
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry + "\n")
                
            # Check if the log file size exceeds the maximum allowed size
            if os.stat(self.log_file)[6] > self.max_size_bytes: # if so, then replace it with new one
                self.rotate_log_file()
                
        except Exception as e:
            if self.debug_mode:
                print(f"Failed to log to file: {e}")
                
    def rotate_log_file(self):
        """Rotates old log files if they get bigger"""
        try:
            # Rename the current log file to indicate it is old
            timestamp = self.get_timestamp()
            new_filename = f"{self.log_file}_{timestamp}.old"
            os.rename(self.log_file, new_filename)
            
            # Create a new empty log file
            with open(self.log_file, "w"):
                pass
            
            # Optionally limit the number of old log files
            self.cleanup_old_logs()
            
        except OSError as e:
            print(f"Error rotating log file: {e}")
            
    def cleanup_old_logs(self):
        """Cleanup old log files to limit disk space usage."""
        try:
            log_files = sorted([f for f in os.listdir('.') if f.startswith(self.log_file) and f.endswith('.old')])
            max_backups = 5
            while len(log_files) > max_backups:
                os.remove(log_files.pop(0))
        except Exception as e:
            print(f"Error cleaning old log files: {e}")
    
    def publish_to_mqtt(self, log_entry):
        """Publishes log entry to MQTT."""
        try:
            self.mqtt_client.publish(self.mqtt_feed, log_entry)
        except Exception as e:
            if self.debug_mode:
                print(f"Failed to publish to MQTT: {e}")
