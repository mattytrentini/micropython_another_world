"""SDL2 display and input backend using ctypes.

Provides a proper windowed display with true key-up/key-down detection
via SDL_GetKeyboardState. No C compilation needed.
"""

import ctypes
import ctypes.util

from aw.hal import DisplayHAL
from aw.consts import SCREEN_W, SCREEN_H

STRIDE = SCREEN_W // 2  # 160

# --- Load SDL2 ---

_lib_name = ctypes.util.find_library("SDL2")
if _lib_name is None:
    _lib_name = "libSDL2.so"
_sdl = ctypes.CDLL(_lib_name)

# --- Constants ---

SDL_INIT_VIDEO = 0x00000020
SDL_WINDOW_SHOWN = 0x00000004
SDL_WINDOW_RESIZABLE = 0x00000020
SDL_WINDOWPOS_CENTERED = 0x2FFF0000
SDL_RENDERER_ACCELERATED = 0x00000002
SDL_RENDERER_PRESENTVSYNC = 0x00000004
SDL_TEXTUREACCESS_STREAMING = 1
SDL_PIXELFORMAT_RGB24 = 0x17101803
SDL_QUIT = 0x100
SDL_KEYDOWN = 0x300
SDL_KEYUP = 0x301

# Scancodes
SC_ESCAPE = 41
SC_SPACE = 44
SC_RETURN = 40
SC_UP = 82
SC_DOWN = 81
SC_LEFT = 80
SC_RIGHT = 79
SC_W = 26
SC_A = 4
SC_S = 22
SC_D = 7
SC_P = 19
SC_N = 17
SC_Q = 20

# --- ctypes types ---

_voidp = ctypes.c_void_p
_uint32 = ctypes.c_uint32
_int = ctypes.c_int
_uint8p = ctypes.POINTER(ctypes.c_uint8)


class _SDL_Rect(ctypes.Structure):
    _fields_ = [("x", _int), ("y", _int), ("w", _int), ("h", _int)]


# SDL_Event is a 56-byte union; we only need the type field (first 4 bytes)
class _SDL_Event(ctypes.Structure):
    _fields_ = [("type", _uint32), ("_pad", ctypes.c_uint8 * 52)]


# --- Function bindings ---

_sdl.SDL_Init.argtypes = [_uint32]
_sdl.SDL_Init.restype = _int

_sdl.SDL_Quit.argtypes = []
_sdl.SDL_Quit.restype = None

_sdl.SDL_CreateWindow.argtypes = [ctypes.c_char_p, _int, _int, _int, _int, _uint32]
_sdl.SDL_CreateWindow.restype = _voidp

_sdl.SDL_DestroyWindow.argtypes = [_voidp]
_sdl.SDL_DestroyWindow.restype = None

_sdl.SDL_CreateRenderer.argtypes = [_voidp, _int, _uint32]
_sdl.SDL_CreateRenderer.restype = _voidp

_sdl.SDL_DestroyRenderer.argtypes = [_voidp]
_sdl.SDL_DestroyRenderer.restype = None

_sdl.SDL_CreateTexture.argtypes = [_voidp, _uint32, _int, _int, _int]
_sdl.SDL_CreateTexture.restype = _voidp

_sdl.SDL_UpdateTexture.argtypes = [_voidp, ctypes.c_void_p, ctypes.c_void_p, _int]
_sdl.SDL_UpdateTexture.restype = _int

_sdl.SDL_DestroyTexture.argtypes = [_voidp]
_sdl.SDL_DestroyTexture.restype = None

_sdl.SDL_RenderClear.argtypes = [_voidp]
_sdl.SDL_RenderClear.restype = _int

_sdl.SDL_RenderCopy.argtypes = [_voidp, _voidp, ctypes.c_void_p, ctypes.c_void_p]
_sdl.SDL_RenderCopy.restype = _int

_sdl.SDL_RenderPresent.argtypes = [_voidp]
_sdl.SDL_RenderPresent.restype = None

_sdl.SDL_PollEvent.argtypes = [ctypes.POINTER(_SDL_Event)]
_sdl.SDL_PollEvent.restype = _int

_sdl.SDL_GetKeyboardState.argtypes = [ctypes.c_void_p]
_sdl.SDL_GetKeyboardState.restype = _uint8p

_sdl.SDL_Delay.argtypes = [_uint32]
_sdl.SDL_Delay.restype = None

_sdl.SDL_GetError.argtypes = []
_sdl.SDL_GetError.restype = ctypes.c_char_p


class SDL2Display(DisplayHAL):
    """SDL2 windowed display with hardware-accelerated scaling."""

    def __init__(self, scale=3):
        """
        Args:
            scale: integer window scale factor (3 = 960x600 window).
        """
        self.scale = scale
        self._window = None
        self._renderer = None
        self._texture = None
        # RGB24 pixel buffer for texture upload (320*200*3 bytes)
        self._rgb_buf = (ctypes.c_uint8 * (SCREEN_W * SCREEN_H * 3))()
        # Current palette: 16 entries of (r, g, b)
        self._palette = [(0, 0, 0)] * 16
        self._quit_requested = False
        # Keyboard state pointer (updated by SDL_PollEvent)
        self._keystate = None

    def init(self, width, height):
        if _sdl.SDL_Init(SDL_INIT_VIDEO) < 0:
            raise RuntimeError("SDL_Init failed: {}".format(
                _sdl.SDL_GetError().decode()))

        win_w = width * self.scale
        win_h = height * self.scale

        self._window = _sdl.SDL_CreateWindow(
            b"Another World",
            SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
            win_w, win_h,
            SDL_WINDOW_SHOWN | SDL_WINDOW_RESIZABLE,
        )
        if not self._window:
            raise RuntimeError("SDL_CreateWindow failed: {}".format(
                _sdl.SDL_GetError().decode()))

        self._renderer = _sdl.SDL_CreateRenderer(
            self._window, -1,
            SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC,
        )
        if not self._renderer:
            # Fallback to software
            self._renderer = _sdl.SDL_CreateRenderer(self._window, -1, 0)

        self._texture = _sdl.SDL_CreateTexture(
            self._renderer,
            SDL_PIXELFORMAT_RGB24,
            SDL_TEXTUREACCESS_STREAMING,
            width, height,
        )

        # Get keyboard state pointer
        self._keystate = _sdl.SDL_GetKeyboardState(None)

    def update_palette(self, palette):
        if palette:
            self._palette = list(palette)

    def present(self, framebuf_4bpp):
        """Convert 4bpp packed buffer to RGB24 and upload to texture."""
        pal = self._palette
        rgb = self._rgb_buf
        buf = framebuf_4bpp
        dst = 0

        for y in range(SCREEN_H):
            src_off = y * STRIDE
            for x in range(0, SCREEN_W, 2):
                byte = buf[src_off + x // 2]
                # High nibble = left pixel
                r, g, b = pal[(byte >> 4) & 0x0F]
                rgb[dst] = r
                rgb[dst + 1] = g
                rgb[dst + 2] = b
                # Low nibble = right pixel
                r, g, b = pal[byte & 0x0F]
                rgb[dst + 3] = r
                rgb[dst + 4] = g
                rgb[dst + 5] = b
                dst += 6

        _sdl.SDL_UpdateTexture(
            self._texture, None,
            ctypes.cast(rgb, ctypes.c_void_p),
            SCREEN_W * 3,  # pitch in bytes
        )
        _sdl.SDL_RenderClear(self._renderer)
        _sdl.SDL_RenderCopy(self._renderer, self._texture, None, None)
        _sdl.SDL_RenderPresent(self._renderer)

    def shutdown(self):
        if self._texture:
            _sdl.SDL_DestroyTexture(self._texture)
        if self._renderer:
            _sdl.SDL_DestroyRenderer(self._renderer)
        if self._window:
            _sdl.SDL_DestroyWindow(self._window)
        _sdl.SDL_Quit()
