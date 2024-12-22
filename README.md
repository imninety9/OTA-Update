# OTA-Update
weather project repository for OTA update using mqtt command

This repository contains the full code for a simple weather update project whivh reads the room as well as outside weather and updates it regularly over adafruit io using mqtt.
I thought of utilizing the mqtt feed/topic to give a command of 'update' from adafruit io to the microcontroller whenever I update the code which will prompt the microcontroller 
to download and update the new code, so I don't have to physically update it.
The code is in micropython and runs on espp32.
