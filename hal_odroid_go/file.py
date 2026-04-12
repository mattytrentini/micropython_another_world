"""ODROID Go file HAL — reads game data from SD card.

The SD card shares the SPI bus with the display. SPI speed is switched
to SD speed during reads and back to display speed afterward.
"""

import os
from aw.hal import FileHAL
from . import spi_bus


class OdroidGoFile(FileHAL):
    """File access from SD card on ODROID Go."""

    def __init__(self, data_path="/sd"):
        self.data_path = data_path

    def _full_path(self, path):
        return self.data_path + "/" + path

    def read_at(self, path, offset, length):
        fp = self._full_path(path)
        spi_bus.set_sd_speed()
        try:
            with open(fp, "rb") as f:
                f.seek(offset)
                return bytearray(f.read(length))
        finally:
            spi_bus.set_display_speed()

    def read_file(self, path):
        fp = self._full_path(path)
        spi_bus.set_sd_speed()
        try:
            with open(fp, "rb") as f:
                return bytearray(f.read())
        finally:
            spi_bus.set_display_speed()

    def file_exists(self, path):
        try:
            spi_bus.set_sd_speed()
            os.stat(self._full_path(path))
            spi_bus.set_display_speed()
            return True
        except OSError:
            spi_bus.set_display_speed()
            return False
