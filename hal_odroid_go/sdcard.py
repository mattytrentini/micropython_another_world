"""SD card mount utility for ODROID Go.

Uses the pure Python sdcard.py driver (install via: mpremote mip install sdcard).
The SD card shares the VSPI bus with the display via spi_bus module.
"""

from machine import Pin
import os

from .consts import PIN_CS_SD
from . import spi_bus


def mount_sd(mountpoint="/sd"):
    """Mount the SD card at the given mountpoint.

    Returns True on success, False on failure.
    """
    try:
        import sdcard
        import time

        spi = spi_bus.get_spi()
        cs = Pin(PIN_CS_SD, Pin.OUT, value=1)
        time.sleep_ms(250)

        sd = sdcard.SDCard(spi, cs)

        # Speed up for mount
        spi_bus.set_sd_speed()

        os.mount(sd, mountpoint)
        return True
    except Exception as e:
        print("SD mount failed:", e)
        return False
