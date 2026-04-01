"""Timer HAL for unix port using time module."""

import time

try:
    from aw.hal import TimerHAL
except ImportError:
    import sys
    sys.path.insert(0, ".")
    from aw.hal import TimerHAL


class UnixTimer(TimerHAL):

    def ticks_ms(self):
        return time.ticks_ms()

    def sleep_ms(self, ms):
        time.sleep_ms(ms)
