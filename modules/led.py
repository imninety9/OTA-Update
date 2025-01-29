# LED

'''to indicate system health, state or some other functions'''

'''
    OFF: system in normal mode
    BLINKING SLOWLY:
    FLASHING:
    PERIODIC SUDDEN BLINK:
'''
import machine
import time

from simple_logging import Logger  # Import the Logger class

class LED:
    def __init__(self, pin_number,
                 logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
        """
        Initializes the LED on a given pin.

        :param pin: Pin number to which the LED is connected.
        """
        try:
            self.led_pin = machine.Pin(pin_number, machine.Pin.OUT)
            self.sudden_blinking = False  # Flag to track if sudden blinking should continue
            self.flashing = False  # Specific flag for flashing mode
            self.timer = machine.Timer(0)  # Initialize timer on timer 0
            self.is_available = True
            logger.info("LED initialized successfully.")
        except Exception as e:
            self.is_available = False
            raise # raise if initialization failed to let the caller know about it

    def on(self):
        """Turn the LED on."""
        self.led_pin.value(1)

    def off(self):
        """Turn the LED off."""
        self.led_pin.value(0)
    
    def toggle(self):
        """Toggle the LED state."""
        self.led_pin.value(not self.led_pin.value())

    def blink(self, interval=0.25, count=3):
        """
        Blink the LED a specified number of times with a given interval in blocking manner.
        This blocks system tasks.

        :param interval: Time in seconds between on/off states. Default is  0.25 second.
        :param count: Number of blink repetitions. Default is 3.
        """
        for _ in range(count):
            self.on()
            time.sleep(interval)
            self.off()
            time.sleep(interval)
        
    #---------------------------------------------------
    def start_sudden_blink(self, on_time=100, off_time=5000):
        """
        Blink the LED with a sudden flash (brief ON followed by long OFF) in non blocking manner using a timer.
        This runs in parallel with system tasks.
        
        :param on_time: Duration in milliseconds for the LED to stay ON.
        :param off_time: Duration in milliseconds for the LED to stay OFF.
        """
        def sudden_blink(timer): # keep timer callback very quick to avoid blocking the main function
            self.on()
            time.sleep_ms(on_time)
            self.off()
            # The timer automatically calls this periodically

        # Start the periodic timer for the flash cycle
        if not self.blinking:
            self.sudden_blinking = True
            self.timer.init(period=on_time + off_time, mode=machine.Timer.PERIODIC, callback=sudden_blink)

    def stop_sudden_blink(self):
        """Stop any continuous sudden blinking mode."""
        self.sudden_blinking = False
        self.timer.deinit()  # Stop the timer
        self.off()  # Ensure the LED is turned off
    #---------------------------------------------------
    
    #---------------------------------------------------
    # NOTE: non-blocking blinking with appropriate interval.
    def start_flashing(self, interval=200):
        """
        Start flashing the LED (rapid ON/OFF toggling) in non blocking manner using a timer.
        This runs in parallel with system tasks.

        :param interval: Time in milliseconds between ON and OFF states. Default is 100ms.
        """
        def flash(timer): # keep timer callback very quick to avoid blocking the main function
            self.toggle()  # Rapidly toggle the LED state

        # Start the timer for flashing mode
        if not self.flashing:
            self.flashing = True
            self.timer.init(period=interval, mode=machine.Timer.PERIODIC, callback=flash)

    def stop_flashing(self):
        """Stop the flashing mode."""
        self.flashing = False
        self.timer.deinit()  # Stop the timer
        self.off()  # Ensure the LED is turned off
    #---------------------------------------------------

####################################
if __name__=="__main__":
    import config
    
    # Initialize logger instance
    logger = Logger(debug_mode=config.DEBUG_MODE)
    
    try:
        led = LED(config.LED_PIN, logger=logger)
        if led.is_available:
            led.on()
            time.sleep(2)
            led.off()
            
            time.sleep(2)
            
            led.blink()
    except Exception as e:
        logger.error(f"Error: {e}")
    
