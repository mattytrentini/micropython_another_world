"""Keyboard input HAL for unix port.

Uses non-blocking terminal input to read arrow keys and action button.
Compatible with MicroPython unix port and CPython.
"""

import sys
import time

try:
    from aw.hal import InputHAL, InputState
except ImportError:
    sys.path.insert(0, ".")
    from aw.hal import InputHAL, InputState

_poll_obj = None
try:
    import select
    if hasattr(select, "select"):
        _HAS_SELECT = True
    elif hasattr(select, "poll"):
        # MicroPython: use select.poll() instead of select.select()
        _poll_obj = select.poll()
        _poll_obj.register(sys.stdin, select.POLLIN)
        _HAS_SELECT = True
    else:
        _HAS_SELECT = False
except ImportError:
    _HAS_SELECT = False

try:
    import termios
    import tty
    _HAS_TERMIOS = True
except ImportError:
    _HAS_TERMIOS = False


def _make_read1():
    """Create a portable single-byte stdin reader."""
    import os
    if hasattr(os, "read"):
        fd = sys.stdin.fileno()
        def _reader():
            return os.read(fd, 1)
        return _reader
    # MicroPython: fall back to sys.stdin.buffer
    buf = sys.stdin.buffer
    def _reader():
        return buf.read(1)
    return _reader

_read1 = _make_read1()


def _ms():
    """Current time in milliseconds."""
    try:
        return int(time.monotonic() * 1000)
    except AttributeError:
        return time.ticks_ms()


class UnixInput(InputHAL):
    """Non-blocking keyboard input from terminal.

    Terminals only send key-down events (no key-up), and only repeat
    the LAST key pressed. Two problems to solve:
    1. Holding one key: initial repeat delay (~300-500ms) of silence
    2. Holding two keys: only the last one repeats; pressing a new key
       causes a fresh initial delay with ZERO events for either key

    Solution: two timeout windows.
    - QUIET_MS (130ms): if the ONLY thing that happened is silence after
      key repeats were flowing, keys expire quickly (responsive release).
    - COMBO_MS (500ms): if a NEW key was recently pressed, keep ALL keys
      alive longer to bridge the initial repeat delay.
    """

    QUIET_MS = 130   # ms to expire after established repeats stop
    COMBO_MS = 500   # ms to keep keys alive after a new keypress

    def __init__(self):
        self._old_settings = None
        self._tty_ok = False
        # Map key name -> timestamp (ms) of last event
        self._held = {}
        # Timestamp of most recent NEW keypress (not a repeat)
        self._last_new_press = 0
        # Timestamp of most recent event of any kind
        self._last_activity = 0
        # Edge-triggered keys consumed on first read
        self._oneshot = set()
        if _HAS_TERMIOS:
            try:
                self._old_settings = termios.tcgetattr(sys.stdin.fileno())
                tty.setcbreak(sys.stdin.fileno())
                self._tty_ok = True
            except (termios.error, OSError):
                pass

    def poll(self):
        state = InputState()
        self._read_keys()

        now = _ms()
        since_new = now - self._last_new_press
        since_any = now - self._last_activity

        # Pick the appropriate timeout:
        # - If a new key was pressed recently, use the longer COMBO_MS
        #   to bridge the initial repeat delay
        # - Otherwise use the shorter QUIET_MS for responsive release
        timeout = self.COMBO_MS if since_new < self.COMBO_MS else self.QUIET_MS

        if since_any > timeout:
            # Total silence beyond timeout — expire all
            self._held.clear()
        # else: keep everything held

        state.left = "left" in self._held
        state.right = "right" in self._held
        state.up = "up" in self._held
        state.down = "down" in self._held
        state.action = "action" in self._held

        # Edge-triggered (consumed on read)
        state.quit = "quit" in self._oneshot
        state.pause = "pause" in self._oneshot
        state.step = "step" in self._oneshot
        self._oneshot.clear()

        return state

    def _press(self, key):
        """Register a key press."""
        now = _ms()
        self._last_activity = now
        if key in ("quit", "pause", "step"):
            self._oneshot.add(key)
        else:
            if key not in self._held:
                self._last_new_press = now
            self._held[key] = now

    def _stdin_ready(self):
        """Check if stdin has data available (non-blocking)."""
        if _poll_obj is not None:
            return bool(_poll_obj.poll(0))
        return bool(select.select([sys.stdin], [], [], 0)[0])

    def _read_keys(self):
        """Read all pending keystrokes without blocking."""
        if not _HAS_SELECT:
            return

        while True:
            if not self._stdin_ready():
                break

            ch = _read1()
            if not ch:
                break

            if ch == b'\x1b':
                seq = b''
                while self._stdin_ready():
                    b = _read1()
                    if not b:
                        break
                    seq += b
                    if len(seq) >= 2 and seq[0:1] == b'[' and b.isalpha():
                        break
                if seq == b'[A':
                    self._press("up")
                elif seq == b'[B':
                    self._press("down")
                elif seq == b'[C' or seq.endswith(b'C'):
                    self._press("right")
                elif seq == b'[D' or seq.endswith(b'D'):
                    self._press("left")
                elif seq == b'':
                    self._press("quit")
            elif ch == b' ' or ch == b'\r' or ch == b'\n':
                self._press("action")
            elif ch == b'q' or ch == b'\x03':
                self._press("quit")
            elif ch == b'w' or ch == b'k':
                self._press("up")
            elif ch == b's' or ch == b'j':
                self._press("down")
            elif ch == b'a' or ch == b'h':
                self._press("left")
            elif ch == b'd' or ch == b'l':
                self._press("right")
            elif ch == b'p':
                self._press("pause")
            elif ch == b'n':
                self._press("step")

    def shutdown(self):
        """Restore terminal settings."""
        if self._tty_ok and self._old_settings:
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN,
                                  self._old_settings)
            except (termios.error, OSError):
                pass
