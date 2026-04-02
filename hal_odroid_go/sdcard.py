"""SD card mount utility for ODROID Go.

The SD card shares the VSPI bus with the display. Mount it before
initializing the display, or ensure CS lines are managed properly.
"""

from machine import Pin, SPI, SDCard
import os

from .consts import SPI_ID, PIN_SCLK, PIN_MOSI, PIN_MISO, PIN_CS_SD


def mount_sd(mountpoint="/sd"):
    """Mount the SD card at the given mountpoint.

    Returns True on success, False on failure.
    """
    try:
        sd = SDCard(
            slot=SPI_ID,
            sck=Pin(PIN_SCLK),
            mosi=Pin(PIN_MOSI),
            miso=Pin(PIN_MISO),
            cs=Pin(PIN_CS_SD),
        )
        os.mount(sd, mountpoint)
        return True
    except Exception as e:
        print("SD mount failed:", e)
        return False
