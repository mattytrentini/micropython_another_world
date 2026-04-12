"""Polygon renderer for Another World.

Handles hierarchical shape traversal, vertex reading with zoom,
and scanline polygon filling in the packed 4bpp format.

Three drawing modes:
  - Solid color (0x00-0x0F): fill with a 4-bit color index
  - Blend (0x10): set bit 3 of each nibble (transparency effect)
  - Page copy (0x11+): copy pixels from page 0

The polygon fill uses a fixed-point edge-stepping scanline algorithm
matching the original Sanglard reference implementation.
"""

from .consts import SCREEN_W, SCREEN_H

# Row stride in bytes
STRIDE = SCREEN_W // 2  # 160

# Try to use viper-accelerated scanline functions
try:
    import micropython

    @micropython.viper
    def _viper_draw_line_n(buf: ptr8, x1: int, x2: int, y: int, color: int):
        """Viper-accelerated solid color horizontal span fill."""
        xmin = x1 if x1 < x2 else x2
        xmax = x2 if x1 < x2 else x1
        p = y * 160 + (xmin >> 1)
        w = (xmax >> 1) - (xmin >> 1) + 1
        cmasks = int(0)
        cmaske = int(0)
        if xmin & 1:
            w -= 1
            cmasks = 0xF0
        if not (xmax & 1):
            w -= 1
            cmaske = 0x0F
        colb = ((color & 0x0F) << 4) | (color & 0x0F)
        if cmasks:
            buf[p] = (int(buf[p]) & cmasks) | (colb & 0x0F)
            p += 1
        for _ in range(w):
            buf[p] = colb
            p += 1
        if cmaske:
            buf[p] = (int(buf[p]) & cmaske) | (colb & 0xF0)

    @micropython.viper
    def _viper_draw_line_p(buf: ptr8, page0: ptr8, x1: int, x2: int, y: int):
        """Viper-accelerated page copy horizontal span."""
        xmin = x1 if x1 < x2 else x2
        xmax = x2 if x1 < x2 else x1
        off = y * 160 + (xmin >> 1)
        w = (xmax >> 1) - (xmin >> 1) + 1
        cmasks = int(0)
        cmaske = int(0)
        if xmin & 1:
            w -= 1
            cmasks = 0xF0
        if not (xmax & 1):
            w -= 1
            cmaske = 0x0F
        p = off
        q = off
        if cmasks:
            buf[p] = (int(buf[p]) & cmasks) | (int(page0[q]) & 0x0F)
            p += 1
            q += 1
        for _ in range(w):
            buf[p] = page0[q]
            p += 1
            q += 1
        if cmaske:
            buf[p] = (int(buf[p]) & cmaske) | (int(page0[q]) & 0xF0)

    @micropython.viper
    def _viper_draw_line_blend(buf: ptr8, x1: int, x2: int, y: int):
        """Viper-accelerated blend mode horizontal span."""
        xmin = x1 if x1 < x2 else x2
        xmax = x2 if x1 < x2 else x1
        p = y * 160 + (xmin >> 1)
        w = (xmax >> 1) - (xmin >> 1) + 1
        cmasks = int(0)
        cmaske = int(0)
        if xmin & 1:
            w -= 1
            cmasks = 0xF7
        if not (xmax & 1):
            w -= 1
            cmaske = 0x7F
        if cmasks:
            buf[p] = (int(buf[p]) & cmasks) | 0x08
            p += 1
        for _ in range(w):
            buf[p] = (int(buf[p]) & 0x77) | 0x88
            p += 1
        if cmaske:
            buf[p] = (int(buf[p]) & cmaske) | 0x80

    _HAS_VIPER = True
except Exception:
    _HAS_VIPER = False

# Division lookup table for edge stepping (calcStep).
# _interp_table[i] = 0x4000 // i for i > 0, 0x4000 for i == 0
_interp_table = [0x4000] + [0x4000 // i for i in range(1, 0x400)]

# Max vertices per polygon
MAX_POINTS = 50

# 32-bit integer masks (the C reference uses uint32_t/int32_t)
_U32_MASK = 0xFFFFFFFF


def _to_i32(val):
    """Wrap to signed 32-bit integer (matching C int32_t overflow)."""
    val &= _U32_MASK
    return val - 0x100000000 if val >= 0x80000000 else val


def _to_u32(val):
    """Wrap to unsigned 32-bit integer."""
    return val & _U32_MASK


class PolygonRenderer:
    """Renders polygons into the video framebuffers."""

    def __init__(self, video):
        self.video = video
        self._data = None       # memoryview into shape data
        self._data_pos = 0      # current read position
        self._data_buf = None   # base of current data segment (for offset lookups)
        # Pre-allocated vertex arrays to avoid allocations
        self._px = [0] * MAX_POINTS
        self._py = [0] * MAX_POINTS

    def set_data(self, data, offset):
        """Set the shape data buffer and starting offset.

        Args:
            data: bytearray of shape/polygon data (seg_video1 or seg_video2)
            offset: byte offset into data where shape starts
        """
        self._data_buf = data
        self._data = memoryview(data) if not isinstance(data, memoryview) else data
        self._data_pos = offset

    def _fetch_byte(self):
        v = self._data[self._data_pos]
        self._data_pos += 1
        return v

    def _fetch_word(self):
        pos = self._data_pos
        v = (self._data[pos] << 8) | self._data[pos + 1]
        self._data_pos = pos + 2
        return v

    def draw_shape(self, color, zoom, x, y):
        """Entry point: read shape type and dispatch.

        Args:
            color: color/mode byte (0xFF = from data, 0x00-0x0F = solid, 0x10 = blend, 0x11+ = page copy)
            zoom: zoom factor (64 = 1:1)
            x, y: center position in screen coordinates
        """
        i = self._fetch_byte()

        if i >= 0xC0:
            # Simple polygon
            if color & 0x80:
                color = i & 0x3F  # color embedded in shape data
            self._fill_polygon(color, zoom, x, y)
        else:
            i &= 0x3F
            if i == 2:
                self._draw_shape_parts(zoom, x, y)

    def _draw_shape_parts(self, zoom, pgc_x, pgc_y):
        """Render hierarchical shape with child sub-shapes."""
        z64 = zoom
        pt_x = pgc_x - self._fetch_byte() * z64 // 64
        pt_y = pgc_y - self._fetch_byte() * z64 // 64
        num_children = self._fetch_byte()

        for _ in range(num_children + 1):
            off = self._fetch_word()
            po_x = pt_x + self._fetch_byte() * z64 // 64
            po_y = pt_y + self._fetch_byte() * z64 // 64

            color = 0xFF
            bp = off
            off &= 0x7FFF

            if bp & 0x8000:
                color = self._data[self._data_pos] & 0x7F
                self._data_pos += 2  # skip color byte + sprite number

            # Save position, seek to child shape, draw, restore
            saved_pos = self._data_pos
            self._data_pos = off * 2
            self.draw_shape(color, zoom, po_x, po_y)
            self._data_pos = saved_pos

    def _fill_polygon(self, color, zoom, cx, cy):
        """Read vertices and fill the polygon using scanline algorithm."""
        z64 = zoom

        bbw = self._fetch_byte() * z64 // 64
        bbh = self._fetch_byte() * z64 // 64
        num_points = self._fetch_byte()

        # Read all vertices
        px = self._px
        py = self._py
        for i in range(num_points):
            px[i] = self._fetch_byte() * z64 // 64
            py[i] = self._fetch_byte() * z64 // 64

        # Degenerate case: single point
        if num_points == 4 and bbw == 0 and bbh <= 1:
            self._draw_point(color, cx, cy)
            return

        x1 = cx - bbw // 2
        x2 = cx + bbw // 2
        y1 = cy - bbh // 2
        y2 = cy + bbh // 2

        # Bounds check
        if x1 > 319 or x2 < 0 or y1 > 199 or y2 < 0:
            return

        # Select draw function based on color
        if color < 0x10:
            draw_fn = self._draw_line_n
        elif color > 0x10:
            draw_fn = self._draw_line_p
        else:
            draw_fn = self._draw_line_blend

        # Scanline fill: walk left and right edges simultaneously
        # Left edge: vertices from end backwards (j), right edge: vertices from start forwards (i)
        hline_y = y1

        i = 0
        j = num_points - 1

        # Initial x positions (offset by x1)
        lx = px[j] + x1
        rx = px[i] + x1

        i += 1
        j -= 1

        # Fixed-point accumulators (16.16) — must wrap as uint32_t
        cpt1 = _to_u32(lx << 16)
        cpt2 = _to_u32(rx << 16)

        remaining = num_points
        draw_buf = self.video.get_draw_buf()
        page0_buf = self.video.page_bufs[0]

        while True:
            remaining -= 2
            if remaining == 0:
                break

            # Calculate steps for left and right edges (int32_t in C).
            # In the C reference, calcStep always computes the step, even
            # when dy=0 (using _interpTable[0]=0x4000). This produces a
            # large step that snaps the edge to its target position.
            # The second calcStep overwrites h, so h = dy2.
            dy1 = py[j] - py[j + 1]
            if dy1 >= 0 and dy1 < 0x400:
                step1 = _to_i32((px[j] - px[j + 1]) * _interp_table[dy1] * 4)
            else:
                step1 = 0

            dy2 = py[i] - py[i - 1]
            if dy2 >= 0 and dy2 < 0x400:
                step2 = _to_i32((px[i] - px[i - 1]) * _interp_table[dy2] * 4)
            else:
                step2 = 0
                dy2 = 0

            i += 1
            j -= 1

            # Reset fractional parts (uint32_t masking)
            cpt1 = (cpt1 & 0xFFFF0000) | 0x7FFF
            cpt2 = (cpt2 & 0xFFFF0000) | 0x8000

            # h = dy2 (right edge), matching C where second calcStep overwrites h
            h = dy2

            if h == 0:
                cpt1 = _to_u32(cpt1 + step1)
                cpt2 = _to_u32(cpt2 + step2)
            else:
                for _ in range(h):
                    if hline_y >= 0:
                        # Extract integer part as signed (arithmetic shift right 16)
                        lx_int = _to_i32(cpt1) >> 16
                        rx_int = _to_i32(cpt2) >> 16
                        if lx_int <= 319 and rx_int >= 0:
                            lx_clamp = max(lx_int, 0)
                            rx_clamp = min(rx_int, 319)
                            draw_fn(draw_buf, page0_buf, lx_clamp, rx_clamp, hline_y, color)
                    cpt1 = _to_u32(cpt1 + step1)
                    cpt2 = _to_u32(cpt2 + step2)
                    hline_y += 1
                    if hline_y > 199:
                        return

    def _draw_point(self, color, x, y):
        """Draw a single pixel."""
        if x < 0 or x > 319 or y < 0 or y > 199:
            return

        buf = self.video.get_draw_buf()
        off = y * STRIDE + x // 2

        if x & 1:
            cmaskn = 0x0F
            cmasko = 0xF0
        else:
            cmaskn = 0xF0
            cmasko = 0x0F

        colb = (color << 4) | color

        if color == 0x10:
            # Blend
            cmaskn &= 0x88
            cmasko = ~cmaskn & 0xFF
            colb = 0x88
        elif color == 0x11:
            # Page copy
            colb = self.video.page_bufs[0][off]

        buf[off] = (buf[off] & cmasko) | (colb & cmaskn)

    def _draw_line_n(self, buf, page0, x1, x2, y, color):
        """Solid color horizontal span fill (packed 4bpp)."""
        if _HAS_VIPER:
            _viper_draw_line_n(buf, x1, x2, y, color)
            return
        xmax = max(x1, x2)
        xmin = min(x1, x2)
        p = y * STRIDE + xmin // 2
        w = xmax // 2 - xmin // 2 + 1

        cmasks = 0
        cmaske = 0
        if xmin & 1:
            w -= 1
            cmasks = 0xF0
        if not (xmax & 1):
            w -= 1
            cmaske = 0x0F

        colb = ((color & 0x0F) << 4) | (color & 0x0F)

        if cmasks:
            buf[p] = (buf[p] & cmasks) | (colb & 0x0F)
            p += 1
        for _ in range(w):
            buf[p] = colb
            p += 1
        if cmaske:
            buf[p] = (buf[p] & cmaske) | (colb & 0xF0)

    def _draw_line_p(self, buf, page0, x1, x2, y, color):
        """Page copy horizontal span (copy from page 0)."""
        if buf is page0:
            return
        if _HAS_VIPER:
            _viper_draw_line_p(buf, page0, x1, x2, y)
            return
        xmax = max(x1, x2)
        xmin = min(x1, x2)
        off = y * STRIDE + xmin // 2
        w = xmax // 2 - xmin // 2 + 1

        cmasks = 0
        cmaske = 0
        if xmin & 1:
            w -= 1
            cmasks = 0xF0
        if not (xmax & 1):
            w -= 1
            cmaske = 0x0F

        p = off
        q = off
        if cmasks:
            buf[p] = (buf[p] & cmasks) | (page0[q] & 0x0F)
            p += 1
            q += 1
        for _ in range(w):
            buf[p] = page0[q]
            p += 1
            q += 1
        if cmaske:
            buf[p] = (buf[p] & cmaske) | (page0[q] & 0xF0)

    def _draw_line_blend(self, buf, page0, x1, x2, y, color):
        """Blend mode horizontal span (set bit 3 of each nibble)."""
        if _HAS_VIPER:
            _viper_draw_line_blend(buf, x1, x2, y)
            return
        xmax = max(x1, x2)
        xmin = min(x1, x2)
        p = y * STRIDE + xmin // 2
        w = xmax // 2 - xmin // 2 + 1

        cmasks = 0
        cmaske = 0
        if xmin & 1:
            w -= 1
            cmasks = 0xF7
        if not (xmax & 1):
            w -= 1
            cmaske = 0x7F

        if cmasks:
            buf[p] = (buf[p] & cmasks) | 0x08
            p += 1
        for _ in range(w):
            buf[p] = (buf[p] & 0x77) | 0x88
            p += 1
        if cmaske:
            buf[p] = (buf[p] & cmaske) | 0x80


