#!/usr/bin/env python
#
# Based on:
# http://www.philrandal.co.uk/blog/archives/2019/07/entry_214.html 
# https://forum-raspberrypi.de/forum/thread/43568-fan-shim-steuern/
# and:
# https://github.com/pimoroni/fanshim-python/blob/master/examples/automatic.py
# fanshim.py By Maxime Vincent (maxime [dot] vince [at] gmail [dot] com)
#
import atexit
import colorsys
import argparse
import time
import sys
import subprocess
import os

import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmcvfs





sys.path.append('/storage/.kodi/addons/virtual.rpi-tools/lib')
import RPi.GPIO as GPIO



msgdialogprogress = xbmcgui.DialogProgress()

addon_id = 'service.fanshim'
selfAddon = xbmcaddon.Addon(addon_id)
datapath = xbmc.translatePath(selfAddon.getAddonInfo('profile')).decode('utf-8')
addonfolder = xbmc.translatePath(selfAddon.getAddonInfo('path')).decode('utf-8')




FAN = 18
DAT = 15
CLK = 14
PIXELS_PER_LIGHT = 4
DEFAULT_BRIGHTNESS = 3
MAX_BRIGHTNESS = 3

brightness = 3
pixels = [[0, 0, 0, DEFAULT_BRIGHTNESS]] * PIXELS_PER_LIGHT
fan_enabled = False

debug_mode = selfAddon.getSetting('debug_mode') == 'true'
on_threshold = int(selfAddon.getSetting('fan_on_temp'))
off_threshold  =  int(selfAddon.getSetting('fan_off_temp'))
delay =  int(selfAddon.getSetting('delay'))
noled =  selfAddon.getSetting('noled') == 'true'

noled = False

xbmc.log("Fan On :" + str(on_threshold) + " Off " + str(off_threshold),level=xbmc.LOGNOTICE)
xbmc.log("Delay :" + str(delay) + " Hide Led: " + str(noled) + " Debug : " + str(debug_mode),level=xbmc.LOGNOTICE)



def init():
    # For FAN
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(FAN, GPIO.OUT)
    GPIO.output(FAN, False)
    # For LED
    GPIO.setup(DAT, GPIO.OUT)
    GPIO.setup(CLK, GPIO.OUT)
    atexit.register(_exit)
    set_light(0, 0, 0)
    return()

def set_pixel(x, r, g, b, brightness=None):
    """Set the RGB value, and optionally brightness, of a single pixel.
    If you don't supply a brightness value, the last value will be kept.
    :param x: The horizontal position of the pixel: 0 to 7
    :param r: Amount of red: 0 to 255
    :param g: Amount of green: 0 to 255
    :param b: Amount of blue: 0 to 255
    :param brightness: Brightness: 0.0 to 1.0 (default around 0.2)
    """
    if brightness is None:
        brightness = pixels[x][3]
    else:
        brightness = int(float(MAX_BRIGHTNESS) * brightness) & 0b11111

    pixels[x] = [int(r) & 0xff, int(g) & 0xff, int(b) & 0xff, brightness]


def set_light(r, g, b):
    """Set the RGB colour of an individual light in your Plasma chain.
    This will set all four LEDs on the Plasma light to the same colour.
    :param r: Amount of red: 0 to 255
    :param g: Amount of green: 0 to 255
    :param b: Amount of blue: 0 to 255
    """
    for x in range(4):
        set_pixel(x, r, g, b)

    """Output the buffer """
    _sof()

    for pixel in pixels:
        r, g, b, brightness = pixel
        _write_byte(0b11100000 | brightness)
        _write_byte(b)
        _write_byte(g)
        _write_byte(r)

    _eof()


# Emit exactly enough clock pulses to latch the small dark die APA102s which are weird
# for some reason it takes 36 clocks, the other IC takes just 4 (number of pixels/2)
def _eof():
    GPIO.output(DAT, 0)
    for x in range(36):
        GPIO.output(CLK, 1)
        time.sleep(0.0000005)
        GPIO.output(CLK, 0)
        time.sleep(0.0000005)

def _sof():
    GPIO.output(DAT, 0)
    for x in range(32):
        GPIO.output(CLK, 1)
        time.sleep(0.0000005)
        GPIO.output(CLK, 0)
        time.sleep(0.0000005)

def _write_byte(byte):
    for x in range(8):
        GPIO.output(DAT, byte & 0b10000000)
        GPIO.output(CLK, 1)
        time.sleep(0.0000005)
        byte <<= 1
        GPIO.output(CLK, 0)
        time.sleep(0.0000005)

def _exit():
    set_light(0, 0, 0)
    GPIO.cleanup()

def set_fan(status):
    global fan_enabled
    changed = False
    if status != fan_enabled:
        changed = True
    GPIO.output(FAN, status)
    fan_enabled = status
    return changed
    
def watch_temp():
    global fan_enabled
    cpu_temp = get_cpu_temp()
    if debug_mode:
        f = get_cpu_freq()
        
        xbmc.log("Fan Status: " + str(fan_enabled) + " temp:" + str(cpu_temp) + " Freq " + str(f) + " %=",level=xbmc.LOGNOTICE)

    if fan_enabled == False and cpu_temp >= on_threshold:
         xbmc.log(str(cpu_temp) + "Enabling fan!" + " temp:" + str(cpu_temp),level=xbmc.LOGNOTICE)
         set_fan(True)
    if fan_enabled == True and cpu_temp <= off_threshold:
         xbmc.log(str(cpu_temp) + " Disabling fan!" + " temp:" + str(cpu_temp),level=xbmc.LOGNOTICE)
         set_fan(False)
    return();

def get_cpu_temp():
    return float(subprocess.check_output(['vcgencmd', 'measure_temp'])[5:-3])

def get_cpu_freq():
    return float(subprocess.check_output(['vcgencmd', 'measure_clock', 'arm'])[14:-1])/1000000


def update_led_temperature(temp):
    temp -= off_threshold
    temp /= float(on_threshold - off_threshold)
    temp = max(0, min(1, temp))
    temp = 1.0 - temp
    temp *= 120.0
    temp /= 360.0
    r, g, b = [int(c * 255.0) for c in colorsys.hsv_to_rgb(temp, 1.0, brightness / 255.0)]
    set_light(r, g, b)

init()
xbmc.log("Starting FanShim Monitor",level=xbmc.LOGNOTICE)
if __name__ == '__main__':
    monitor = xbmc.Monitor()
   
while not monitor.abortRequested():
    # Sleep/wait for abort for x seconds
    if monitor.waitForAbort(delay):
            # Abort was requested while waiting. We should exit
            xbmc.log("Ending FanShim Monitor",level=xbmc.LOGNOTICE)
            break


    watch_temp()

    if not noled:
            t = get_cpu_temp()
            update_led_temperature(t)

   
xbmc.log("FanShim Closed",level=xbmc.LOGNOTICE)   