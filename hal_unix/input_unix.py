"""Keyboard input HAL for unix port.

Uses non-blocking terminal input to read arrow keys and action button.
Compatible with MicroPython unix port and CPython.
"""

import sys
import os
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


def _ms():
    """Current time in milliseconds."""
    try:
        return int(time.monotonic() * 1000)
    except AttributeError:
        return time.ticks_ms()


class UnixInput(InputHAL):
    """Non-blocking keyboard input from terminal.

    Terminals only send key-down events (no key-up), and only repeat
    the LAST key pressed. When holding two keys (e.g. direction+action),
    only one generates repeats. To handle this:
    - Keys expire RELEASE_MS after their last event
    - BUT as long as ANY key is actively repeating, all recently-pressed
      keys stay alive (terminals don't repeat multiple keys at once,
      but the user is likely still holding them)
    """

    RELEASE_MS = 130   # ms to keep a key after last event (no other activity)

    def __init__(self):
        self._old_settings = None
        self._tty_ok = False
        # Map key name -> timestamp (ms) of last event
        self._held = {}
        # Timestamp of most recent input event (any key)
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
        activity_age = now - self._last_activity

        # If ANY key is actively repeating (recent activity), keep all
        # held keys alive. Only expire when there's been total silence.
        if activity_age <= self.RELEASE_MS:
            # Active input — keep everything held
            pass
        else:
            # No recent input — expire keys individually
            expired = [k for k, t in self._held.items()
                       if now - t > self.RELEASE_MS]
            for k in expired:
                del self._held[k]

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

            ch = os.read(sys.stdin.fileno(), 1)
            if not ch:
                break

            if ch == b'\x1b':
                seq = b''
                while self._stdin_ready():
                    b = os.read(sys.stdin.fileno(), 1)
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
