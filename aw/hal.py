"""Hardware Abstraction Layer base classes.

All platform-specific behavior is behind these interfaces.
Implementations are in hal_unix/, hal_rp2/, hal_esp32/, etc.
"""


class InputState:
    """Input state snapshot returned by InputHAL.poll()."""
    __slots__ = ("left", "right", "up", "down", "action", "quit")

    def __init__(self):
        self.left = False
        self.right = False
        self.up = False
        self.down = False
        self.action = False
        self.quit = False


class DisplayHAL:
    """Receives a 320x200 4bpp packed framebuffer and presents it."""

    def init(self, width, height):
        raise NotImplementedError

    def update_palette(self, palette):
        """Update the color palette.

        Args:
            palette: list of 16 (r, g, b) tuples, each component 0-255.
        """
        raise NotImplementedError

    def present(self, framebuf_4bpp):
        """Present a frame to the display.

        Args:
            framebuf_4bpp: bytearray of 32000 bytes (320x200, 2 pixels/byte,
                           high nibble = left pixel, low nibble = right pixel).
        """
        raise NotImplementedError

    def shutdown(self):
        pass


class InputHAL:
    """Provides input state to the VM."""

    def poll(self):
        """Poll for current input state.

        Returns:
            InputState with current button/key states.
        """
        raise NotImplementedError


class TimerHAL:
    """Millisecond-resolution timer."""

    def ticks_ms(self):
        """Return current time in milliseconds."""
        raise NotImplementedError

    def sleep_ms(self, ms):
        """Sleep for the given number of milliseconds."""
        raise NotImplementedError


class FileHAL:
    """File access abstraction for game data."""

    def read_at(self, path, offset, length):
        """Read bytes from a file at a given offset.

        Args:
            path: file path (relative to data directory)
            offset: byte offset to start reading
            length: number of bytes to read

        Returns:
            bytearray of the requested bytes.
        """
        raise NotImplementedError

    def read_file(self, path):
        """Read an entire file.

        Args:
            path: file path (relative to data directory)

        Returns:
            bytearray of file contents.
        """
        raise NotImplementedError

    def file_exists(self, path):
        """Check if a file exists.

        Args:
            path: file path (relative to data directory)

        Returns:
            True if file exists.
        """
        raise NotImplementedError
