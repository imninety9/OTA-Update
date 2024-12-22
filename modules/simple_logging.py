# logging of messages, etc with their flags

from time import localtime

class Logger:
    def __init__(self, log_file=None, mqtt_client=None, mqtt_feed = None, debug_mode=True):
        self.log_file = log_file # to log into the memory
        self.mqtt_client = mqtt_client # to publish message to mqtt client
        self.mqtt_feed = mqtt_feed # feed to publish message
        self.debug_mode = debug_mode # for DEBUGGING

    def get_timestamp(self):
        """Returns the current timestamp in ordered manner i.e. yyyy-mm-dd-hh-mm-ss."""
        try:
            current_time = localtime()
            return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(*current_time[:6])
        except:
            return None

    def log_message(self, flag, message, publish = False):
        """Logs the message with a given flag."""
        '''Flags:
                INFO
                WARNING
                ERROR
                CRITICAL
                DEBUG
        '''
        timestamp = self.get_timestamp()
        log_entry = f"{timestamp} - {flag} - {message}"
        
        # Print for debugging
        if self.debug_mode:
            print(log_entry)
        
        # Log to file
        if self.log_file:
            self.log_to_file(log_entry)
        
        # Publish via MQTT
        if publish and self.mqtt_client and self.mqtt_feed:
            self.publish_to_mqtt(log_entry)
    
    def log_to_file(self, log_entry):
        """Writes log entry to the file."""
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry + "\n")
        except Exception as e:
            if self.debug_mode:
                print(f"Failed to log to file: {e}")
    
    def publish_to_mqtt(self, log_entry):
        """Publishes log entry to MQTT."""
        try:
            self.mqtt_client.publish(self.mqtt_feed, log_entry)
        except Exception as e:
            if self.debug_mode:
                print(f"Failed to publish to MQTT: {e}")
