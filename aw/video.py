"""Another World video system.

Manages 4 framebuffer pages (320x200, 4bpp packed), palette switching,
page operations (fill, copy, scroll, swap), and text rendering.

Pages use framebuf.FrameBuffer with GS4_HMSB format where available,
falling back to raw bytearray operations otherwise.
"""

from .consts import SCREEN_W, SCREEN_H, PAGE_SIZE, NUM_PAGES, PALETTE_NO_CHANGE

# Row stride in bytes (320 pixels / 2 pixels per byte)
STRIDE = SCREEN_W // 2  # 160

# Try to use MicroPython's framebuf module
try:
    import framebuf
    _HAS_FRAMEBUF = True
except ImportError:
    _HAS_FRAMEBUF = False


class Video:
    """Video subsystem: 4 pages, palette, page ops, text rendering."""

    def __init__(self):
        # Raw page buffers
        self.page_bufs = [bytearray(PAGE_SIZE) for _ in range(NUM_PAGES)]

        # FrameBuffer wrappers (if available)
        if _HAS_FRAMEBUF:
            self.page_fbs = [
                framebuf.FrameBuffer(buf, SCREEN_W, SCREEN_H, framebuf.GS4_HMSB)
                for buf in self.page_bufs
            ]
        else:
            self.page_fbs = [None] * NUM_PAGES

        # Buffer index mapping: [draw, display, back]
        self.buffers = [0, 1, 2]

        # Palette state
        self.next_palette = PALETTE_NO_CHANGE
        self.current_palette = 0
        self.palette_data = None    # raw palette segment (set by resource loader)
        self.palette_rgb = None     # current 16-color palette as list of (r,g,b)

        # Display callback (set by engine)
        self.on_display = None

        # Font and string data (set externally)
        self.font_data = None
        self.strings = None

        # Polygon renderer (set externally)
        self.polygon = None

        # Shape data segments (updated between frames by engine)
        self.seg_video1 = None
        self.seg_video2 = None
        self.resource = None  # used for palette reads only

    def get_page_id(self, page_arg):
        """Resolve a page argument to a page index (0-3).

        Args:
            page_arg: Page specifier from opcode.
                0-3: direct page index
                0xFE: current draw page
                0xFF: current back page
                Other: page_arg & 3
        """
        if page_arg <= 3:
            return page_arg
        elif page_arg == 0xFE:
            return self.buffers[0]  # draw page
        elif page_arg == 0xFF:
            return self.buffers[2]  # back page
        else:
            return page_arg & 3

    def get_draw_page(self):
        """Return the index of the current draw page."""
        return self.buffers[0]

    def get_draw_buf(self):
        """Return the bytearray of the current draw page."""
        return self.page_bufs[self.buffers[0]]

    def get_draw_fb(self):
        """Return the FrameBuffer of the current draw page (or None)."""
        return self.page_fbs[self.buffers[0]]

    def load_bitmap(self, page_data):
        """Write a 4bpp bitmap to the current draw page.

        Called by the resource loader when a BMP bitmap is loaded.
        Matches rawgl's copyBitmapPtr behavior.
        """
        draw_buf = self.get_draw_buf()
        draw_buf[:] = page_data

    # --- Opcodes ---

    def select_page(self, page_id):
        """opcode 0x0D: set active drawing page."""
        self.buffers[0] = self.get_page_id(page_id)

    def fill_page(self, page_id, color):
        """opcode 0x0E: fill page with solid color."""
        pid = self.get_page_id(page_id)
        fb = self.page_fbs[pid]
        if fb is not None:
            fb.fill(color)
        else:
            buf = self.page_bufs[pid]
            fill_byte = (color << 4) | (color & 0x0F)
            for i in range(PAGE_SIZE):
                buf[i] = fill_byte

    def copy_page(self, src_id, dst_id, vscroll=0):
        """opcode 0x0F: copy page, optionally with vertical scroll.

        The scroll logic: if src has bit 6 set (0x40) and is not 0xFE/0xFF,
        it triggers a scrolled copy using vscroll from VAR_SCROLL_Y.
        """
        # Determine if this is a scroll copy
        # From rawgl: if (src >= 0xFE || ((src &= ~0x40) & 0x80) == 0) -> simple copy
        if src_id >= 0xFE:
            self._copy_simple(src_id, dst_id)
        else:
            src_stripped = src_id & ~0x40
            if (src_stripped & 0x80) == 0:
                self._copy_simple(src_id, dst_id)
            else:
                # Scrolled copy
                self._copy_scroll(src_id & 3, dst_id, vscroll)

    def _copy_simple(self, src_id, dst_id):
        """Simple full-page copy."""
        sp = self.get_page_id(src_id)
        dp = self.get_page_id(dst_id)
        if sp == dp:
            return
        src_buf = self.page_bufs[sp]
        dst_buf = self.page_bufs[dp]
        dst_buf[:] = src_buf

    def _copy_scroll(self, src_page, dst_id, vscroll):
        """Copy with vertical scroll offset."""
        dp = self.get_page_id(dst_id)
        if src_page == dp:
            return
        if vscroll < -199 or vscroll > 199:
            return

        src_buf = self.page_bufs[src_page]
        dst_buf = self.page_bufs[dp]
        h = SCREEN_H

        src_off = 0
        dst_off = 0
        if vscroll < 0:
            h += vscroll
            src_off = (-vscroll) * STRIDE
        elif vscroll > 0:
            h -= vscroll
            dst_off = vscroll * STRIDE

        nbytes = h * STRIDE
        dst_buf[dst_off:dst_off + nbytes] = src_buf[src_off:src_off + nbytes]

    def update_display(self, page_id):
        """opcode 0x10: update the visible display.

        Handles page swap (0xFF), direct page set, and palette changes.
        """
        if page_id != 0xFE:
            if page_id == 0xFF:
                # Swap display and back pages
                self.buffers[1], self.buffers[2] = self.buffers[2], self.buffers[1]
            else:
                self.buffers[1] = self.get_page_id(page_id)

        # Apply deferred palette change
        if self.next_palette != PALETTE_NO_CHANGE:
            self._apply_palette(self.next_palette)
            self.next_palette = PALETTE_NO_CHANGE

        # Notify display
        if self.on_display:
            display_buf = self.page_bufs[self.buffers[1]]
            self.on_display(display_buf, self.palette_rgb)

    def set_palette_request(self, pal_num):
        """opcode 0x0B: request palette change (deferred to updateDisplay)."""
        self.next_palette = pal_num

    def _apply_palette(self, pal_num):
        """Apply a palette from the palette data segment."""
        self.current_palette = pal_num
        # Read palette from resource if available
        data = self.resource.seg_palette if self.resource else self.palette_data
        if data is None:
            return

        # Each palette: 16 colors x 2 bytes = 32 bytes
        offset = pal_num * 32
        pal = []
        for i in range(16):
            idx = offset + i * 2
            if idx + 1 >= len(data):
                pal.append((0, 0, 0))
                continue
            # Format: byte0 = 0x0R, byte1 = 0xGB
            b0 = data[idx]
            b1 = data[idx + 1]
            r = (b0 & 0x0F) * 17  # scale 0-15 to 0-255
            g = ((b1 >> 4) & 0x0F) * 17
            b = (b1 & 0x0F) * 17
            pal.append((r, g, b))
        self.palette_rgb = pal

    # --- Text rendering ---

    def draw_string(self, str_id, x, y, color):
        """opcode 0x12: draw a string on the current draw page.

        Args:
            str_id: string table ID
            x: x position in character cells (8px each)
            y: y position in pixels
            color: 4-bit color index
        """
        if self.strings is None or self.font_data is None:
            return

        s = self.strings.get(str_id)
        if s is None:
            return

        page_buf = self.get_draw_buf()
        x_origin = x
        for ch in s:
            if ch == '\n':
                y += 8
                x = x_origin
            else:
                self._draw_char(ch, x, y, color, page_buf)
                x += 1

    def _draw_char(self, ch, cx, cy, color, buf):
        """Draw a single 8x8 character.

        Args:
            ch: character to draw
            cx: x position in character cells (8px units)
            cy: y position in pixels
            color: 4-bit color index
            buf: page bytearray to draw into
        """
        font = self.font_data
        if font is None:
            return

        char_idx = ord(ch) - 0x20
        if char_idx < 0 or char_idx * 8 + 7 >= len(font):
            return

        font_off = char_idx * 8
        # Each character cell is 4 bytes wide (8 pixels / 2 pixels per byte)
        buf_x = cx * 4
        if buf_x < 0 or buf_x + 3 >= STRIDE:
            return

        for row in range(8):
            py = cy + row
            if py < 0 or py >= SCREEN_H:
                continue

            bits = font[font_off + row]
            buf_off = py * STRIDE + buf_x

            for col in range(4):
                # Two pixels per byte, two bits per pixel from font
                b = buf[buf_off + col]

                # High nibble (left pixel)
                if bits & 0x80:
                    b = (color << 4) | (b & 0x0F)
                bits <<= 1

                # Low nibble (right pixel)
                if bits & 0x80:
                    b = (b & 0xF0) | (color & 0x0F)
                bits <<= 1

                buf[buf_off + col] = b

    # --- Shape drawing (polygon dispatch) ---

    def draw_shape_at(self, offset, x, y, color, zoom, use_seg_video2):
        """Called by VM for polygon draw pseudo-opcodes.

        Dispatches to the polygon renderer with the correct data segment.
        """
        if self.polygon is None:
            return

        data = self.seg_video2 if use_seg_video2 else self.seg_video1
        if data is None:
            return

        self.polygon.set_data(data, offset)
        self.polygon.draw_shape(color, zoom, x, y)
