"""ODROID Go file HAL — reads game data from SD card.

The SD card shares the SPI bus with the display. Game data should be
at /sd/game/DAT/FILE###.DAT (20th Anniversary Edition format).
"""

import os
from aw.hal import FileHAL


class OdroidGoFile(FileHAL):
    """File access from SD card on ODROID Go."""

    def __init__(self, data_path="/sd"):
        self.data_path = data_path

    def _full_path(self, path):
        return self.data_path + "/" + path

    def read_at(self, path, offset, length):
        fp = self._full_path(path)
        with open(fp, "rb") as f:
            f.seek(offset)
            return bytearray(f.read(length))

    def read_file(self, path):
        fp = self._full_path(path)
        with open(fp, "rb") as f:
            return bytearray(f.read())

    def file_exists(self, path):
        try:
            os.stat(self._full_path(path))
            return True
        except OSError:
            return False
