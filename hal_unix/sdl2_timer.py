"""SDL2 timer backend."""

import time
from aw.hal import TimerHAL
from .sdl2_display import _sdl


class SDL2Timer(TimerHAL):

    def ticks_ms(self):
        return int(time.monotonic() * 1000)

    def sleep_ms(self, ms):
        if ms > 0:
            _sdl.SDL_Delay(int(ms))
