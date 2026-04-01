"""Timer HAL for unix port using time module.

Supports both MicroPython (time.ticks_ms) and CPython (time.monotonic).
"""

import time

try:
    from aw.hal import TimerHAL
except ImportError:
    import sys
    sys.path.insert(0, ".")
    from aw.hal import TimerHAL

_HAS_TICKS = hasattr(time, "ticks_ms")


class UnixTimer(TimerHAL):

    def ticks_ms(self):
        if _HAS_TICKS:
            return time.ticks_ms()
        return int(time.monotonic() * 1000)

    def sleep_ms(self, ms):
        if _HAS_TICKS:
            time.sleep_ms(ms)
        else:
            time.sleep(ms / 1000)
