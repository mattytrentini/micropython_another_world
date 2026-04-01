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


class UnixInput(InputHAL):
    """Non-blocking keyboard input from terminal.

    Terminals only send key-down events (no key-up). When holding a key,
    there's an initial delay (~300-500ms) before repeats start. To simulate
    held keys, each key stays "pressed" for HOLD_FRAMES frames after the
    last event — long enough to bridge the initial repeat delay.
    """

    HOLD_FRAMES = 25  # ~500ms at 50Hz, covers typical repeat delay

    def __init__(self):
        self._old_settings = None
        self._tty_ok = False
        # Map key name -> frames remaining until release
        self._held = {}
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

        # Decay held keys
        expired = []
        for key, frames in self._held.items():
            if frames <= 0:
                expired.append(key)
            else:
                self._held[key] = frames - 1
        for key in expired:
            del self._held[key]

        state.left = "left" in self._held
        state.right = "right" in self._held
        state.up = "up" in self._held
        state.down = "down" in self._held
        state.action = "action" in self._held
        state.quit = self._held.pop("quit", 0) > 0
        # Pause and step are edge-triggered (one-shot, not held)
        state.pause = self._held.pop("pause", 0) > 0
        state.step = self._held.pop("step", 0) > 0

        return state

    def _press(self, key):
        """Register a key press, resetting its hold timer."""
        self._held[key] = self.HOLD_FRAMES

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
                # Read the full escape sequence (variable length)
                seq = b''
                while self._stdin_ready():
                    b = os.read(sys.stdin.fileno(), 1)
                    if not b:
                        break
                    seq += b
                    # Stop after the final letter byte of a CSI sequence
                    if len(seq) >= 2 and seq[0:1] == b'[' and b.isalpha():
                        break
                if seq == b'[A':
                    self._press("up")
                elif seq == b'[B':
                    self._press("down")
                elif seq == b'[C' or seq.endswith(b'C'):
                    self._press("right")  # including Ctrl/Shift+Right
                elif seq == b'[D' or seq.endswith(b'D'):
                    self._press("left")   # including Ctrl/Shift+Left
                elif seq == b'':
                    self._press("quit")  # bare Escape (no following bytes)
            elif ch == b' ' or ch == b'\r' or ch == b'\n':
                self._press("action")
            elif ch == b'q' or ch == b'\x03':  # q or Ctrl-C
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
