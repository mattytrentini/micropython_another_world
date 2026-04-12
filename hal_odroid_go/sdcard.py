"""SD card mount utility for ODROID Go.

Uses the pure Python sdcard.py driver (install via: mpremote mip install sdcard).
The SD card shares the VSPI bus with the display.
"""

from machine import Pin, SPI
import os

from .consts import SPI_ID, PIN_SCLK, PIN_MOSI, PIN_MISO, PIN_CS_SD


def mount_sd(mountpoint="/sd"):
    """Mount the SD card at the given mountpoint.

    Returns True on success, False on failure.
    """
    try:
        import sdcard
        import time

        spi = SPI(SPI_ID, baudrate=100000, polarity=0, phase=0,
                  sck=Pin(PIN_SCLK), mosi=Pin(PIN_MOSI), miso=Pin(PIN_MISO))
        cs = Pin(PIN_CS_SD, Pin.OUT, value=1)
        time.sleep_ms(250)

        sd = sdcard.SDCard(spi, cs)

        # Speed up after init
        spi.init(baudrate=4000000)

        os.mount(sd, mountpoint)
        return True
    except Exception as e:
        print("SD mount failed:", e)
        return False
