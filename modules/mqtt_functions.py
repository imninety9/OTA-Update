# connect mqtt client to broker and other functions

'''
how to handle disconnections:
if mqtt is disconnected, we will get exception while publishing data
using publish() or receiving data using check_msg;
hence implement reconnect logic in those error cases
'''

'''
Last Will and Testament (LWT)
Purpose:
MQTT has a feature called Last Will and Testament. If the client disconnects unexpectedly, the broker publishes a predefined message to a topic.
How to Set Up:
Specify the LWT message when initializing the MQTT client.
'''

'''
QoS (Quality of Service)
MQTT supports three QoS levels:
QoS 0: At most once. No guarantee of delivery.
QoS 1: At least once. Messages may be delivered multiple times. Messages are retried until acknowledged.
QoS 2: Exactly once. Ensures no duplicates or missing messages.
Use QoS 1 or 2 for critical messages to improve reliability during publishing or subscribing.
'''

'''
Local Buffering
If the ESP32 fails to publish a message, store it in local memory or persistent storage (e.g., a file) and retry later.
'''


'''
How Keep-Alive Works?
The connection remains alive for at least keep_alive period between messages without any PING request and
if the client has not sent any data (e.g., published a message or subscribed to a topic) within the keep-alive interval, it sends a small PINGREQ message to the broker.
The broker responds with a PINGRESP, confirming the connection is still active.

Connection Timeout:
If the broker does not receive any data or a PINGREQ from the client within 1.5 times the keep-alive interval, it assumes the client is disconnected.
Similarly, if the client doesn't receive a response to its PINGREQ, it considers the connection lost.


1. Keeping the Connection Alive
Pros:
Efficiency:

Avoids the overhead of reconnecting to the MQTT broker repeatedly.
Saves time and energy, especially for devices with limited processing power or on battery.
Can handle frequent publishing without reconnecting each time.
Reliability:

Ensures faster publishing because the connection is already established.
Allows the broker to detect disconnections via the keep-alive mechanism and invoke the Last Will and Testament (LWT) if needed.
Real-Time Command Handling:

Subscribed topics (like a reboot command) remain active, allowing the ESP32 to react immediately to incoming messages.
Cons:
Idle Connection Maintenance:

Even when not publishing, the device sends periodic PINGREQ messages, which might consume bandwidth (although minimal).
Potential Issues with Stability:

If the connection drops unexpectedly (e.g., network hiccups), the client must handle reconnections.
2. Reconnecting for Each Publish
Pros:
Simplicity:

No need to manage keep-alive pings or check for disconnection mid-operation.
Each publish starts fresh with a clean connection.
Reduced Idle Traffic:

No periodic PINGREQ messages are sent when the device is idle.
Power Savings (in some cases):

If your device enters a low-power sleep mode between readings, reconnecting may make sense since the connection is dropped anyway.
Cons:
Reconnection Overhead:

Establishing a new MQTT connection involves a handshake with the broker, which adds time and consumes power.
Latency increases as each connection requires authentication.
Increased Failure Points:

Each new connection attempt can fail due to network instability or broker unavailability.


Which Approach is Better for Your Case?
Given your scenario:

Data is published every 5 minutes.
The ESP32 is running headless and should remain reliable.
Recommendation: Keep the Connection Alive
Why?

Maintaining a persistent connection is more efficient when publishing data every 5 minutes.
Reconnection overhead would add unnecessary delays and complexity.
A persistent connection allows you to subscribe to commands (like reboot) and receive them in near real-time.

When to Reconnect Instead of Keeping the Connection
If your device needs to:

Sleep for long periods (e.g., hours).
Save power aggressively by disconnecting from WiFi when idle.
In such cases, reconnecting for each publish might be more appropriate, but it comes with added complexity in handling reconnection and failures.


if we are publishing or subscribing data frequently then it
is better to keep the connection alive permanently as it will reduce
processing; hence try to keep 'keep_alive' period greater than
data publishing/receiving interval to avoid ping overhead.
But if we are publishing very infrequently like b/w hours; then
disconnecting and then reconnectiong may be more power efficient.
'''

from umqtt.simple import MQTTClient

from custom_exceptions import MQTTPublishingError

from simple_logging import Logger  # Import the Logger class


'''
NOTE=>

We cannot define the MQTT callback function as def feed_callback(feed, msg, arg1, arg2): directly, because the callback signature for MQTT messages is predefined by the MQTT client library you are using (e.g., umqtt.simple or paho.mqtt). In most MQTT libraries, the callback function signature accepts only two parameters:
feed: The topic or feed to which the message was published.
msg: The message content.

===========

Why Adding Extra Arguments (arg1, arg2) Is Not Allowed:
MQTT client callback functions are designed to be triggered by the library itself when a message is received on a subscribed topic. The library automatically passes the topic (feed) and the message (msg) as parameters, but it does not automatically handle additional custom arguments (arg1, arg2), which are not part of the library's expected signature.
The MQTT client, when invoking the callback, does not know how to pass additional arguments unless you explicitly handle it within the function. If you try to define more parameters in the callback, you will likely encounter a TypeError because the callback function does not match the signature expected by the client library.

===========

How to Handle Additional Arguments in the Callback:
1. Use a Global or Shared Variable-
Use a global variable or an object that stores the additional arguments, which can be accessed within the callback.
---------------
# Define global variables for additional arguments
global_arg1 = "extra_arg1"
global_arg2 = "extra_arg2"

def feed_callback(feed, msg):
    print(f"Received message on {feed}: {msg}")
    print(f"Additional args: {global_arg1}, {global_arg2}")
---------------

2. Object-Oriented Approach-
If your application is more complex, you can use an object-oriented approach and store the additional arguments as attributes of an object. Then, your callback function can refer to the object's attributes.
---------------
class MQTTCallbackHandler:
    def __init__(self, arg1, arg2):
        self.arg1 = arg1
        self.arg2 = arg2

    def feed_callback(self, feed, msg):
        print(f"Received message on {feed}: {msg}")
        print(f"Additional args: {self.arg1}, {self.arg2}")
----------------
'''

# callback handler
class CallbackHandler:
    def __init__(self, logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
        self.logger = logger
        
    # callback function
    def feed_callback(self, feed, msg):
        """Callback for MQTT received message."""
        '''
            feed: the subscribed feed or topic
            msg: the received message
        '''
        try:
            feed = feed.decode('utf-8')
            msg = msg.decode('utf-8')
            self.logger.log_message("INFO", f"Received message on {feed}: {msg}", publish = True)
            return feed, msg
        except Exception as e:
            self.logger.log_message("ERROR", f"Failed to read the received message: {e}")

# Initialize mqtt client
def init_mqtt(client_id, broker, port, user, password, keepalive, will_feed, will_message, callback, logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    """Initialize the MQTT client."""
    try:
        client = MQTTClient(
            client_id, broker, port,
            user=user, password=password,
            keepalive=keepalive
        )
        
        # If the client disconnects without calling disconnect(), the server will post this will_message on will_feed as a last thing on its own behalf
        client.set_last_will(will_feed, will_message, qos=1) # Last Will
        
        # callback function for when we receive a message on the subscribed feed
        client.set_callback(callback)
        return client
    except Exception as e:
        logger.log_message("ERROR", f"Failed to initialize MQTT client: {e}")
        return None
'''
Why 'return None' becomes Redundant after a 'raise'?
Flow of Execution in Python-
When an exception is raised using the raise statement, the current function immediately terminates. Any code after the raise statement is never
executed, which includes 'return None' and function exits immediately when the raise statement is executed.

When the function fails:
An exception is raised, which halts the function execution and propagates the exception to the caller.
The caller must handle this exception to proceed, typically using a try-except block.
If the exception is not handled, the program will crash, and no further code will be executed.
'''
    
# Connect mqtt client
def connect_mqtt(client, logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    """Connect to MQTT broker with retries."""
    try:
        client.connect()
        logger.log_message("INFO", "Connected to MQTT broker.", publish=True)
        return client
    except Exception as e:
        logger.log_message("ERROR", f"MQTT connection attempt failed: {e}")
        return None

# Subscribe to a feed
def subscribe_feed(client, feed, logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    '''function to subscribe to a feed to receive message'''
    try:
        client.subscribe(feed, qos = 2)
        logger.log_message("INFO", f"Subscribed to feed: {feed}", publish = True)
    except Exception as e:
        logger.log_message("ERROR", f"Failed to subscribe to feed {feed}: {e}", publish = True)
        
# Publish data to mqtt server
def publish_data(client, data, logger: Logger): # logger is expected to be of type Logger (i.e. an instance of Logger class)
    # data is a dictionary {"feed": "msg"}
    ''' publish the given data to their corresponding feeds'''
    try:
        for feed, msg in data.items():
            if feed is not None and msg is not None:
                client.publish(feed, msg, qos=0)
    except Exception as e:
        logger.log_message("ERROR", f"Publishing data failed: {e}")
        raise MQTTPublishingError("MQTT Data Publishing Failed")


# Example usage
if __name__ == "__main__":
    try:
        import connect_wifi
        import utils
        import config
        
        # Initialize the logger
        logger = Logger(debug_mode=config.DEBUG_MODE)
        
        # Connect to Wi-Fi
        wifi = utils.retry_with_backoff(logger, connect_wifi.connect_to_wifi, config.wifi_networks, logger)
            
        # feed callback handler
        callback_handler = CallbackHandler(logger)
        
        # Initialize MQTT
        client = utils.retry_with_backoff(logger, init_mqtt,
            config.AdafruitIO_USER,
            config.AdafruitIO_SERVER,
            config.AdafruitIO_PORT,
            config.AdafruitIO_USER,
            config.AdafruitIO_KEY,
            config.KEEP_ALIVE_INTERVAL,
            f"{config.AdafruitIO_USER}/feeds/errors",  # LWT Topic
            b"ESP32 disconnected unexpectedly",
            callback_handler.feed_callback,
            logger
        )

        # Connect to MQTT broker
        if client and wifi.isconnected():
            utils.retry_with_backoff(logger, connect_mqtt, client, logger)
        
    except Exception as e:
        logger.log_message("ERROR", f"Error: {e}")
