# OTA-Update
weather project repository for OTA update using mqtt command

## info
This repository contains the full code for a simple weather update project whivh reads the room as well as outside weather and updates it regularly over adafruit io using mqtt.  

I thought of utilizing the mqtt feed/topic to give a command of 'update' from adafruit io to the microcontroller whenever I update the code which will prompt the microcontroller to download and update the new code, so I don't have to physically do it.  

The code is in micropython and runs on espp32.

## how?
to update a file in the microcontroller, just upload the changed file in this github repository at its correct position and then give the following command over mqtt:  

      update-<filename>  
      
          where, <filename> should be complete filename including the directory structure   
          
                  e.g. update-main.py  
                  
                  or, update-modules/config.py

### 
other available commands:
	reboot
	toggleled
