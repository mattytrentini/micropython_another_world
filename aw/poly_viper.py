"""Viper-accelerated polygon fill functions.

Separated into its own module for reliable mpy-cross compilation.
"""

import micropython
import array

# Interp table for edge stepping
_interp_table_arr = array.array('i', [0x4000] + [0x4000 // i for i in range(1, 0x400)])


@micropython.viper
def read_and_fill_n(buf: ptr8, data: ptr8, data_pos: int,
                     px: ptr32, py: ptr32,
                     cx: int, cy: int, zoom: int, color: int) -> int:
    """Read vertices from data, edge-step, and solid-color fill.
    Returns new data_pos."""
    interp = ptr32(_interp_table_arr)
    z64 = int(zoom)
    bbw = int(int(data[data_pos]) * z64 // 64)
    bbh = int(int(data[data_pos + 1]) * z64 // 64)
    num_points = int(data[data_pos + 2])
    dp = int(data_pos + 3)

    # Read vertices
    for vi in range(num_points):
        px[vi] = int(data[dp]) * z64 // 64
        py[vi] = int(data[dp + 1]) * z64 // 64
        dp = int(dp + 2)

    # Degenerate point
    if num_points == 4 and bbw == 0 and bbh <= 1:
        if cx >= 0 and cx <= 319 and cy >= 0 and cy <= 199:
            off = int(cy * 160 + (cx >> 1))
            if cx & 1:
                buf[off] = (int(buf[off]) & 0xF0) | (color & 0x0F)
            else:
                buf[off] = (int(buf[off]) & 0x0F) | ((color & 0x0F) << 4)
        return dp

    x1 = int(cx - bbw // 2)
    y1 = int(cy - bbh // 2)

    if x1 > 319 or int(cx + bbw // 2) < 0 or y1 > 199 or int(cy + bbh // 2) < 0:
        return dp

    colb = int(((color & 0x0F) << 4) | (color & 0x0F))
    i = int(0)
    j = int(num_points - 1)
    lx = int(int(px[j]) + x1)
    rx = int(int(px[i]) + x1)
    i = int(1)
    j = int(j - 1)
    cpt1 = int(lx * 65536)
    cpt2 = int(rx * 65536)
    hline_y = int(y1)
    remaining = int(num_points)

    while True:
        remaining = int(remaining - 2)
        if remaining == 0:
            break
        dy1 = int(int(py[j]) - int(py[j + 1]))
        step1 = int(0)
        if dy1 >= 0 and dy1 < 1024:
            step1 = int((int(px[j]) - int(px[j + 1])) * int(interp[dy1]) * 4)
        dy2 = int(int(py[i]) - int(py[i - 1]))
        step2 = int(0)
        if dy2 >= 0 and dy2 < 1024:
            step2 = int((int(px[i]) - int(px[i - 1])) * int(interp[dy2]) * 4)
        else:
            dy2 = int(0)
        i = int(i + 1)
        j = int(j - 1)
        cpt1 = int(int(cpt1 >> 16) << 16) | int(0x7FFF)
        cpt2 = int(int(cpt2 >> 16) << 16) | int(0x8000)
        h = int(dy2)
        if h == 0:
            cpt1 = int(cpt1 + step1)
            cpt2 = int(cpt2 + step2)
        else:
            for _ in range(h):
                if hline_y >= 0:
                    lxi = int(cpt1 >> 16)
                    rxi = int(cpt2 >> 16)
                    if lxi <= 319 and rxi >= 0:
                        xmin = int(lxi if lxi > 0 else 0)
                        xmax = int(rxi if rxi < 319 else 319)
                        p = int(hline_y * 160 + (xmin >> 1))
                        w = int((xmax >> 1) - (xmin >> 1) + 1)
                        cms = int(0)
                        cme = int(0)
                        if xmin & 1:
                            w = int(w - 1)
                            cms = int(0xF0)
                        if not (xmax & 1):
                            w = int(w - 1)
                            cme = int(0x0F)
                        if cms:
                            buf[p] = int(buf[p]) & cms | (colb & 0x0F)
                            p = int(p + 1)
                        for _ in range(w):
                            buf[p] = colb
                            p = int(p + 1)
                        if cme:
                            buf[p] = int(buf[p]) & cme | (colb & 0xF0)
                cpt1 = int(cpt1 + step1)
                cpt2 = int(cpt2 + step2)
                hline_y = int(hline_y + 1)
                if hline_y > 199:
                    return dp
    return dp


@micropython.viper
def read_and_fill_p(buf: ptr8, page0: ptr8, data: ptr8, data_pos: int,
                     px: ptr32, py: ptr32,
                     cx: int, cy: int, zoom: int) -> int:
    """Read vertices + page-copy fill. Returns new data_pos."""
    interp = ptr32(_interp_table_arr)
    z64 = int(zoom)
    bbw = int(int(data[data_pos]) * z64 // 64)
    bbh = int(int(data[data_pos + 1]) * z64 // 64)
    num_points = int(data[data_pos + 2])
    dp = int(data_pos + 3)
    for vi in range(num_points):
        px[vi] = int(data[dp]) * z64 // 64
        py[vi] = int(data[dp + 1]) * z64 // 64
        dp = int(dp + 2)
    if num_points == 4 and bbw == 0 and bbh <= 1:
        if cx >= 0 and cx <= 319 and cy >= 0 and cy <= 199:
            off = int(cy * 160 + (cx >> 1))
            buf[off] = page0[off]
        return dp
    x1 = int(cx - bbw // 2)
    y1 = int(cy - bbh // 2)
    if x1 > 319 or int(cx + bbw // 2) < 0 or y1 > 199 or int(cy + bbh // 2) < 0:
        return dp
    i = int(0); j = int(num_points - 1)
    lx = int(int(px[j]) + x1); rx = int(int(px[i]) + x1)
    i = int(1); j = int(j - 1)
    cpt1 = int(lx * 65536); cpt2 = int(rx * 65536)
    hline_y = int(y1); remaining = int(num_points)
    while True:
        remaining = int(remaining - 2)
        if remaining == 0: break
        dy1 = int(int(py[j]) - int(py[j + 1]))
        step1 = int(0)
        if dy1 >= 0 and dy1 < 1024:
            step1 = int((int(px[j]) - int(px[j + 1])) * int(interp[dy1]) * 4)
        dy2 = int(int(py[i]) - int(py[i - 1]))
        step2 = int(0)
        if dy2 >= 0 and dy2 < 1024:
            step2 = int((int(px[i]) - int(px[i - 1])) * int(interp[dy2]) * 4)
        else: dy2 = int(0)
        i = int(i + 1); j = int(j - 1)
        cpt1 = int(int(cpt1 >> 16) << 16) | int(0x7FFF)
        cpt2 = int(int(cpt2 >> 16) << 16) | int(0x8000)
        h = int(dy2)
        if h == 0:
            cpt1 = int(cpt1 + step1); cpt2 = int(cpt2 + step2)
        else:
            for _ in range(h):
                if hline_y >= 0:
                    lxi = int(cpt1 >> 16); rxi = int(cpt2 >> 16)
                    if lxi <= 319 and rxi >= 0:
                        xmin = int(lxi if lxi > 0 else 0)
                        xmax = int(rxi if rxi < 319 else 319)
                        p = int(hline_y * 160 + (xmin >> 1))
                        w = int((xmax >> 1) - (xmin >> 1) + 1)
                        cms = int(0); cme = int(0)
                        if xmin & 1: w = int(w - 1); cms = int(0xF0)
                        if not (xmax & 1): w = int(w - 1); cme = int(0x0F)
                        q = int(p)
                        if cms:
                            buf[p] = (int(buf[p]) & cms) | (int(page0[q]) & 0x0F)
                            p = int(p + 1); q = int(q + 1)
                        for _ in range(w):
                            buf[p] = page0[q]; p = int(p + 1); q = int(q + 1)
                        if cme:
                            buf[p] = (int(buf[p]) & cme) | (int(page0[q]) & 0xF0)
                cpt1 = int(cpt1 + step1); cpt2 = int(cpt2 + step2)
                hline_y = int(hline_y + 1)
                if hline_y > 199: return dp
    return dp


@micropython.viper
def read_and_fill_blend(buf: ptr8, data: ptr8, data_pos: int,
                         px: ptr32, py: ptr32,
                         cx: int, cy: int, zoom: int) -> int:
    """Read vertices + blend fill. Returns new data_pos."""
    interp = ptr32(_interp_table_arr)
    z64 = int(zoom)
    bbw = int(int(data[data_pos]) * z64 // 64)
    bbh = int(int(data[data_pos + 1]) * z64 // 64)
    num_points = int(data[data_pos + 2])
    dp = int(data_pos + 3)
    for vi in range(num_points):
        px[vi] = int(data[dp]) * z64 // 64
        py[vi] = int(data[dp + 1]) * z64 // 64
        dp = int(dp + 2)
    if num_points == 4 and bbw == 0 and bbh <= 1:
        if cx >= 0 and cx <= 319 and cy >= 0 and cy <= 199:
            off = int(cy * 160 + (cx >> 1))
            if cx & 1:
                buf[off] = (int(buf[off]) & 0xF7) | 0x08
            else:
                buf[off] = (int(buf[off]) & 0x7F) | 0x80
        return dp
    x1 = int(cx - bbw // 2)
    y1 = int(cy - bbh // 2)
    if x1 > 319 or int(cx + bbw // 2) < 0 or y1 > 199 or int(cy + bbh // 2) < 0:
        return dp
    i = int(0); j = int(num_points - 1)
    lx = int(int(px[j]) + x1); rx = int(int(px[i]) + x1)
    i = int(1); j = int(j - 1)
    cpt1 = int(lx * 65536); cpt2 = int(rx * 65536)
    hline_y = int(y1); remaining = int(num_points)
    while True:
        remaining = int(remaining - 2)
        if remaining == 0: break
        dy1 = int(int(py[j]) - int(py[j + 1]))
        step1 = int(0)
        if dy1 >= 0 and dy1 < 1024:
            step1 = int((int(px[j]) - int(px[j + 1])) * int(interp[dy1]) * 4)
        dy2 = int(int(py[i]) - int(py[i - 1]))
        step2 = int(0)
        if dy2 >= 0 and dy2 < 1024:
            step2 = int((int(px[i]) - int(px[i - 1])) * int(interp[dy2]) * 4)
        else: dy2 = int(0)
        i = int(i + 1); j = int(j - 1)
        cpt1 = int(int(cpt1 >> 16) << 16) | int(0x7FFF)
        cpt2 = int(int(cpt2 >> 16) << 16) | int(0x8000)
        h = int(dy2)
        if h == 0:
            cpt1 = int(cpt1 + step1); cpt2 = int(cpt2 + step2)
        else:
            for _ in range(h):
                if hline_y >= 0:
                    lxi = int(cpt1 >> 16); rxi = int(cpt2 >> 16)
                    if lxi <= 319 and rxi >= 0:
                        xmin = int(lxi if lxi > 0 else 0)
                        xmax = int(rxi if rxi < 319 else 319)
                        p = int(hline_y * 160 + (xmin >> 1))
                        w = int((xmax >> 1) - (xmin >> 1) + 1)
                        cms = int(0); cme = int(0)
                        if xmin & 1: w = int(w - 1); cms = int(0xF7)
                        if not (xmax & 1): w = int(w - 1); cme = int(0x7F)
                        if cms:
                            buf[p] = (int(buf[p]) & cms) | 0x08
                            p = int(p + 1)
                        for _ in range(w):
                            buf[p] = (int(buf[p]) & 0x77) | 0x88
                            p = int(p + 1)
                        if cme:
                            buf[p] = (int(buf[p]) & cme) | 0x80
                cpt1 = int(cpt1 + step1); cpt2 = int(cpt2 + step2)
                hline_y = int(hline_y + 1)
                if hline_y > 199: return dp
    return dp
