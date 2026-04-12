"""Shared SPI bus for ODROID Go.

The display and SD card share SPI(2). This module manages the bus
and provides speed switching for SD card access.
"""

from machine import Pin, SPI
from .consts import SPI_ID, PIN_SCLK, PIN_MOSI, PIN_MISO

# Display runs at 40MHz, SD card at 4MHz
# 80MHz causes tearing on some boards due to signal integrity
DISPLAY_FREQ = 40_000_000
SD_FREQ = 4_000_000
SD_INIT_FREQ = 100_000

_spi = None


def get_spi():
    """Get the shared SPI bus, creating it if needed."""
    global _spi
    if _spi is None:
        _spi = SPI(SPI_ID, baudrate=SD_INIT_FREQ, polarity=0, phase=0,
                    sck=Pin(PIN_SCLK), mosi=Pin(PIN_MOSI), miso=Pin(PIN_MISO))
    return _spi


def set_display_speed():
    """Switch SPI to display speed (40MHz)."""
    if _spi:
        _spi.init(baudrate=DISPLAY_FREQ)


def set_sd_speed():
    """Switch SPI to SD card speed (4MHz)."""
    if _spi:
        _spi.init(baudrate=SD_FREQ)
