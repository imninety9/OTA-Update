# ds3231 rtc

from machine import Pin, SoftI2C
from ds3231_gen import *
import ntptime
import time

from simple_logging import Logger

class ds3231:
    def __init__(self, sclPIN, sdaPIN, alarmPIN,
                 logger: Logger = Logger()): # logger is expected to be of type Logger (i.e. an instance of Logger class) [with default value of Logger()]
        '''initialize ds3231 rtc object'''
        try:
            self.logger = logger  # Store logger as instance variable
            
            self.i2c = SoftI2C(scl=Pin(sclPIN), sda=Pin(sdaPIN))
            self.d = DS3231(self.i2c)
            self.alarm = [self.d.alarm1, self.d.alarm2] # ds3231 has two alarms
            # variiables to track, if an alarm is enabled (i.e. sending interrupts to the INT/SQW pin) or not
            self.alarm1 = False
            self.alarm2 = False
            
            # GPIO setup for INT/SQW pin
            self.alarm_pin = Pin(alarmPIN, Pin.IN, Pin.PULL_UP)
            # Attach the interrupt to the alarm pin
            self.alarm_pin.irq(handler=self.alarm_handler, trigger=Pin.IRQ_FALLING)
            
            self.logger.info("DS3231 clock initialized successfully.")
        except Exception as e:
            self.logger.critical(f"Failed to initialize DS3231 clock: {e}")
            raise # raise if initialization failed to let the caller know about it
        
    def get_time(self):
        '''get current time from ds3231'''
        ''' format: (year, month, day, hour, minutes, seconds, weekday, 0) '''
        ''' in 24 hour format '''
        try:
            return self.d.get_time()
        except Exception as e:
            self.logger.error(f'Failed to get DS3231 time: {e}')
            
    def set_time(self, time):
        '''set ds3231 time'''
        ''' time tuple format: (year, month, day, hour, minutes, seconds, weekday, 0) '''
        ''' in 24 hour format '''
        try:
            return self.d.set_time(time)
        except Exception as e:
            self.logger.error(f'Failed to set DS3231 time: {e}')
    
    def sync_time_with_ntp(self):
        '''sync ds3231 time with ntp server'''
        try:
            ntptime.host = 'pool.ntp.org' # UTC
            # ntptime.time() returns seconds from epoch
            self.set_time(time.localtime(ntptime.time() + 19800)) # IST = UTC + 19800 (in sec)
            
            self.logger.info("DS3231 time synced with NTP", publish=True)
            return True
        except Exception as e:
            self.logger.error(f'Failed to sync time with NTP: {e}', publish=True)
            return False
    
    def set_alarm(self, n, week=None, day=None, hr=None, min=None, sec=None): # n = 1 or 2 depending upon which alarm you want to set [alarm2 doesnt have seconds]
        '''sets an alarm and also enables it'''
        '''
        day: 0–6 or 1–31 [0–6: Day of the week (Sunday = 0). 1–31: Day of the month.]
        hr: 0–23 [24-hour clock format.]
        min: 0–59 [Minutes in an hour.]
        sec: 0–59 [Seconds in a minute (used only for Alarm 1, as Alarm 2 doesn't support seconds and ignores them).]
        '''
        # NOTE: set_alarm() also clears any previous alarm trigger flag if it was set True, so that from now on every alarm trigger will get recognized.
        try:
            if sec==None:
                if n == 1:
                    self.alarm[n-1].set(EVERY_SECOND)
                else: # n==2
                    self.alarm[n-1].set(EVERY_MINUTE) # since alarm2 does not support seconds resolution
            elif min==None:
                self.alarm[n-1].set(EVERY_MINUTE, sec=sec)
            elif hr==None:
                self.alarm[n-1].set(EVERY_HOUR, min=min, sec=sec)
            elif day==None:
                self.alarm[n-1].set(EVERY_DAY, hr=hr, min=min, sec=sec)
            elif week==None: # day must be from 0 to 6 for every week alarm
                self.alarm[n-1].set(EVERY_WEEK, day=day, hr=hr, min=min, sec=sec)
            else: # just give a random week number as it is not important because the day value (must be 1-31 for month alarm) will decide the week itself
                self.alarm[n-1].set(EVERY_MONTH, day=day, hr=hr, min=min, sec=sec)
            if n==1:
                self.clear_alarm(n=1)
                self.alarm1 = True
            elif n==2:
                self.clear_alarm(n=2)
                self.alarm2 = True
            self.logger.info(f'alarm{n} set.')
        except Exception as e:
            self.logger.error(f'Failed to set alarm{n}: {e}')
            
    def disable_alarm(self, n=0): # if n=0; both alarms will get disabled
        '''Disable an alarm or both'''
        '''
        NOTE: Disabling an alarm only disables the interrupt signal to the INT/SQW pin;
            but the alarm keeps going on at the preset interval in the ds3231 hardware.
            Meaning microcontroller won't know or get affected by the alarm but alarm keeps
            firing just like the clock keeps ticking in the ds3231. Hence, if we check the
            alarm flag; it will read 'True' even though the INT/SQW pin doesn't get affected.
        '''
        try:
            if n != 1:
                self.alarm[1].enable(run=False)
                self.alarm2 = False
            if n != 2:
                self.alarm[0].enable(run=False)
                self.alarm1 = False
            self.logger.info(f'alarm{n} disabled.')
        except Exception as e:
            self.logger.error(f'Failed to disable alarm{n}: {e}')
            
    def clear_alarm(self, n):
        '''clears an alarm flag if it is True i.e. it has occured/fired'''
        ''' Note: It doesn't matter if the alarm is enabled or not meaning
        it doesn't matter if the INT/SQW pin is getting the signal of alarm
        being fired at the preset interval or not. The flag will be set to True
        once alarm fires and will stay True until explicitly cleared. '''
        try:
            self.alarm[n-1].clear()  # Clear Alarm flag
        except Exception as e:
            self.logger.error(f'Failed to clear alarm{n}: {e}')
            
    def enable_alarm(self, n=0): # if n=0; both alarms will get enabled
        '''Enable an alarm or both'''
        ''' Note: Enabling an alarm enables signals on the INT/SQW pin at the preset interval.'''
        # this also clears any previous alarm trigger flags so that from now on new alarm triggers are recognized.
        try:
            if n != 1:
                self.alarm[1].enable(run=True)
                self.clear_alarm(n=2)
                self.alarm2 = True
            if n != 2:
                self.alarm[0].enable(run=True)
                self.clear_alarm(n=1)
                self.alarm1 = True
            self.logger.info(f'alarm{n} enabled.')
        except Exception as e:
            self.logger.error(f'Failed to enable alarm{n}: {e}')
    
    def check_and_clear_alarm(self, n):
        '''checks if an alarm flag is set (i.e. it has fired) or not and clears it'''
        if self.alarm[n-1]():
            self.clear_alarm(n)
            return True
        else:
            return False
        
    def alarm_handler(self, pin): # self.alarm_pin is calling this handler so it will be passed as an argument; hence we are defining it in the function definition
        '''Alarm Interrupt handler'''
        
        '''
        NOTE: An interrupt handler function receives a definite argument from the source/peripheral
        which has called it and this argument is this source/peripheral itself (e.g., 'pin' for GPIO
        interrupts or 'timer' for timer ISRs). The reasons for this are here:
        1. When multiple peripherals or pins are configured to generate interrupts, the handler needs
        to know which one triggered the interrupt.
        2. Passing the triggering peripheral as an argument allows the same handler function to manage
        multiple sources dynamically.
        Without this argument, you'd need a separate handler for each peripheral, making the code less
        flexible and harder to maintain.
        3. The argument allows the handler to interact with the specific peripheral that triggered the
        interrupt. For example:
        Reading or writing to a GPIO pin state.
        Checking timer flags or resetting them after the event.
        4. Handlers can remain modular, as they don't rely on hardcoded references. The interrupt system
        passes the necessary peripheral/context dynamically.
        This improves portability and reusability across different projects or parts of the codebase.

        => Hence, when defining the interrupt handler function; always include this source/peripheral as
        an argument in its definition even if you don't use it in the function.

        e.g. def interrupt_handler(timer):
                pass
        or, def interrupt_handler(timer):
                timer.deinit()
        or, def interrupt_handler(pin):
                pass
        or, def interrupt_handler(pin):
                print(pin.value())
        '''
        
        try:
            if self.alarm1 and self.check_and_clear_alarm(n=1): # if Alarm 1 is enabled and it has triggered
                self.logger.info('alarm1 triggered and cleared.')
                # Perform Alarm 1 specific actions
                self.logger.info('GOOD MORNING!', publish=True)
            if self.alarm2 and self.check_and_clear_alarm(n=2): # if Alarm 2 is enabled and it has triggered
                self.logger.info('alarm2 triggered and cleared.')
                # Perform Alarm 2 specific actions
                self.sync_time_with_ntp()
        except Exception as e:
            self.logger.error(f'Failed to handle alarm isr: {e}', publish=True)


###################
if __name__ == "__main__":
    import connect_wifi
    import utils
    import config
    
    # Initialize logger instance
    logger = Logger(debug_mode=config.DEBUG_MODE)
    try:
        # Connect to Wi-Fi
        #wifi = utils.retry_with_backoff(connect_wifi.connect_to_wifi, config.wifi_networks, logger=logger)
        
        ds = utils.retry_with_backoff(ds3231, config.softsclPIN, config.softsdaPIN,
                                      max_retries=3, backoff_base=10,
                                      logger=logger)
        
        if ds:
            print(ds.get_time())
            '''
            if wifi and wifi.isconnected():
                ds.sync_time_with_ntp()
            print(ds.get_time())
            '''
            
            '''
            ds.enable_alarm(n=1)
            '''
            
            ds.set_alarm(n=1, sec=30)
            ds.set_alarm(n=2)
            while True:
                print(ds.get_time())
                time.sleep(10)  
        
    except Exception as e:
        logger.error(f'Error occured: {e}')    
        
    finally:
        if ds:
            ds.disable_alarm(n=0)
        
