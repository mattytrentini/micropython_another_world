"""ODROID Go timer HAL — uses MicroPython's time module."""

import time
from aw.hal import TimerHAL


class OdroidGoTimer(TimerHAL):

    def ticks_ms(self):
        return time.ticks_ms()

    def sleep_ms(self, ms):
        time.sleep_ms(ms)
