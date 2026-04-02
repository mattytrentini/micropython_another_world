"""SDL2 input backend using keyboard state polling.

Uses SDL_GetKeyboardState for true held-key detection — no terminal
repeat hacks needed. Supports simultaneous key presses.
"""

from aw.hal import InputHAL, InputState
from .sdl2_display import (
    _sdl, _SDL_Event, SDL_QUIT, SDL_KEYDOWN,
    SC_ESCAPE, SC_SPACE, SC_RETURN, SC_UP, SC_DOWN, SC_LEFT, SC_RIGHT,
    SC_W, SC_A, SC_S, SC_D, SC_P, SC_N, SC_Q,
)


class SDL2Input(InputHAL):
    """SDL2 keyboard input with true key-up/key-down detection."""

    def __init__(self, display):
        """
        Args:
            display: SDL2Display instance (shares the SDL2 event loop).
        """
        self._display = display
        self._oneshot = set()

    def poll(self):
        state = InputState()

        # Pump events (required for SDL_GetKeyboardState to update)
        event = _SDL_Event()
        while _sdl.SDL_PollEvent(event):
            if event.type == SDL_QUIT:
                self._oneshot.add("quit")
            elif event.type == SDL_KEYDOWN:
                # Read scancode from the event (offset 16 in keyboard event)
                import ctypes
                scancode = ctypes.cast(
                    ctypes.addressof(event) + 16,
                    ctypes.POINTER(ctypes.c_uint32)
                ).contents.value
                if scancode == SC_ESCAPE or scancode == SC_Q:
                    self._oneshot.add("quit")
                elif scancode == SC_P:
                    self._oneshot.add("pause")
                elif scancode == SC_N:
                    self._oneshot.add("step")

        # Read held key state directly — true simultaneous key detection
        ks = self._display._keystate
        if ks:
            state.left = bool(ks[SC_LEFT] or ks[SC_A])
            state.right = bool(ks[SC_RIGHT] or ks[SC_D])
            state.up = bool(ks[SC_UP] or ks[SC_W])
            state.down = bool(ks[SC_DOWN] or ks[SC_S])
            state.action = bool(ks[SC_SPACE] or ks[SC_RETURN])

        state.quit = "quit" in self._oneshot
        state.pause = "pause" in self._oneshot
        state.step = "step" in self._oneshot
        self._oneshot.clear()

        return state

    def shutdown(self):
        pass
