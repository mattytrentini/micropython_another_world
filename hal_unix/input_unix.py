"""Keyboard input HAL for unix port.

Uses non-blocking terminal input to read arrow keys and action button.
Compatible with MicroPython unix port and CPython.
"""

import sys
import os

try:
    from aw.hal import InputHAL, InputState
except ImportError:
    sys.path.insert(0, ".")
    from aw.hal import InputHAL, InputState

try:
    import select
    _HAS_SELECT = True
except ImportError:
    _HAS_SELECT = False

try:
    import termios
    import tty
    _HAS_TERMIOS = True
except ImportError:
    _HAS_TERMIOS = False


class UnixInput(InputHAL):
    """Non-blocking keyboard input from terminal."""

    def __init__(self):
        self._old_settings = None
        self._keys = set()
        self._tty_ok = False
        if _HAS_TERMIOS:
            try:
                self._old_settings = termios.tcgetattr(sys.stdin.fileno())
                tty.setcbreak(sys.stdin.fileno())
                self._tty_ok = True
            except (termios.error, OSError):
                pass  # not a real terminal (piped, CI, etc.)

    def poll(self):
        state = InputState()
        self._read_keys()

        state.left = "left" in self._keys
        state.right = "right" in self._keys
        state.up = "up" in self._keys
        state.down = "down" in self._keys
        state.action = "action" in self._keys
        state.quit = "quit" in self._keys
        state.pause = "pause" in self._keys
        state.step = "step" in self._keys

        self._keys.clear()
        return state

    def _read_keys(self):
        """Read all pending keystrokes without blocking."""
        if not _HAS_SELECT:
            return

        while True:
            rlist, _, _ = select.select([sys.stdin], [], [], 0)
            if not rlist:
                break

            ch = os.read(sys.stdin.fileno(), 1)
            if not ch:
                break

            if ch == b'\x1b':
                # Escape sequence
                seq = os.read(sys.stdin.fileno(), 2)
                if seq == b'[A':
                    self._keys.add("up")
                elif seq == b'[B':
                    self._keys.add("down")
                elif seq == b'[C':
                    self._keys.add("right")
                elif seq == b'[D':
                    self._keys.add("left")
                else:
                    self._keys.add("quit")  # bare Escape = quit
            elif ch == b' ' or ch == b'\r' or ch == b'\n':
                self._keys.add("action")
            elif ch == b'q' or ch == b'\x03':  # q or Ctrl-C
                self._keys.add("quit")
            elif ch == b'w' or ch == b'k':
                self._keys.add("up")
            elif ch == b's' or ch == b'j':
                self._keys.add("down")
            elif ch == b'a' or ch == b'h':
                self._keys.add("left")
            elif ch == b'd' or ch == b'l':
                self._keys.add("right")
            elif ch == b'p':
                self._keys.add("pause")
            elif ch == b'n':
                self._keys.add("step")

    def shutdown(self):
        """Restore terminal settings."""
        if self._tty_ok and self._old_settings:
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN,
                                  self._old_settings)
            except (termios.error, OSError):
                pass
