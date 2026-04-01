"""File HAL for unix port using standard filesystem."""

import os

try:
    from aw.hal import FileHAL
except ImportError:
    import sys
    sys.path.insert(0, ".")
    from aw.hal import FileHAL


class UnixFile(FileHAL):

    def __init__(self, data_path):
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
