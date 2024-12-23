# Custom Exceptions

# Setup Error - error during setups that are essential for the working of the project;
# hence, some big measures should be taken like resetting the device.
class SetupError(Exception):
    pass

# MQTT Publishing Error - error during publishing the data on mqtt server
#        --- it probably means our mqtt connection is lost, hence reconnect
class MQTTPublishingError(Exception):
    pass

# maybe create WiFiError, etc
