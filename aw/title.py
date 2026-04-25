"""Title screen and password entry menu.

The logo is drawn from scratch using a small set of filled polygons
(thick rects and thick lines) with an italic shear and drop shadow,
on top of a simple starfield + silhouette backdrop. Nothing in the
20th Anniversary data bundle contains the original Amiga logo, so
this is a hand-crafted homage rather than an authentic asset.
"""

from .font import FONT
from .consts import SCREEN_W, SCREEN_H, PAGE_SIZE, PASSWORDS, PART_INTRO
from .title_logo import LOGO_W, LOGO_H, LOGO_DATA
from .title_backdrop import BACKDROP_PALETTE, BACKDROP_DATA

STRIDE = SCREEN_W // 2

# Palette slots used while compositing the title screen. Must match the
# reservations in tools/build_title_logo.py.
_C_LOGO_OUTLINE = 3
_C_LOGO_INTERIOR = 7
_C_HINT = 9
_C_HIGHLIGHT = 10
_C_ERROR = 11


class TitleScreen:
    """Logo + main menu + password entry, rendered by hand."""

    def __init__(self, display, input_hal, timer, passwords=None):
        self.display = display
        self.input = input_hal
        self.timer = timer
        self.passwords = passwords if passwords is not None else PASSWORDS
        self.buf = bytearray(PAGE_SIZE)
        self._prev = {"action": False, "up": False, "down": False,
                      "left": False, "right": False}
        self._backdrop = None  # cached backdrop+logo to speed up re-renders

    def run(self):
        """Show the title, block until the user picks. Returns (part, checkpoint) or None."""
        self.display.update_palette(BACKDROP_PALETTE)
        # Some window managers (notably WSLg / X11 forwarders) won't actually
        # map the SDL window until the event queue has been pumped a few
        # times. Without this loop, the very first frame can sit in the
        # back buffer until the user presses a key.
        self._pump(5)
        self._drain_input()
        self._build_backdrop()
        result = self._menu_loop()
        # Wait for the confirming key to release before handing off — the
        # engine polls input on its first frame, and a still-held action
        # key would be read as "skip intro".
        if result is not None:
            self._drain_input()
        return result

    def _pump(self, n=1, ms=10):
        """Pump input events n times with a short sleep between."""
        for _ in range(n):
            self.input.poll()
            self.timer.sleep_ms(ms)

    # --- Main menu ---------------------------------------------------------

    def _menu_loop(self):
        items = ("START GAME", "ENTER CODE", "QUIT")
        selected = 0
        dirty = True
        while True:
            if dirty:
                self._render_menu(items, selected)
                dirty = False
            # Present every iteration. Texture-upload is cheap, and on some
            # window managers (WSLg / X11 forwarders) the first present
            # after window creation gets dropped — without a steady stream
            # of presents the screen stays black until a redraw is forced.
            self.display.present(self.buf)
            edges = self._poll_edges()
            if edges["quit"]:
                return None
            if edges["up"] and selected > 0:
                selected -= 1
                dirty = True
            if edges["down"] and selected < len(items) - 1:
                selected += 1
                dirty = True
            if edges["action"]:
                if selected == 0:
                    return (PART_INTRO, None)
                if selected == 1:
                    result = self._password_loop()
                    if result is not None:
                        return result
                    dirty = True
                if selected == 2:
                    return None
            self.timer.sleep_ms(33)

    def _render_menu(self, items, selected):
        self._blit_backdrop()
        base_y = 132
        for i, label in enumerate(items):
            y = base_y + i * 14
            color = _C_HIGHLIGHT if i == selected else _C_LOGO_INTERIOR
            text = ("> " + label + " <") if i == selected else ("  " + label + "  ")
            self._draw_text_centered(text, y, color)
        self._draw_text_centered("ARROWS: SELECT    SPACE: CONFIRM", 186, _C_HINT)

    # --- Password entry ----------------------------------------------------

    def _password_loop(self):
        letters = [0, 0, 0, 0]
        cursor = 0
        error = False
        dirty = True
        while True:
            if dirty:
                self._render_password(letters, cursor, error)
                dirty = False
            self.display.present(self.buf)
            edges = self._poll_edges()
            if edges["quit"]:
                return None
            if edges["up"]:
                letters[cursor] = (letters[cursor] - 1) % 26
                error = False
                dirty = True
            if edges["down"]:
                letters[cursor] = (letters[cursor] + 1) % 26
                error = False
                dirty = True
            if edges["left"] and cursor > 0:
                cursor -= 1
                dirty = True
            if edges["right"] and cursor < 3:
                cursor += 1
                dirty = True
            if edges["action"]:
                if cursor < 3:
                    cursor += 1
                    dirty = True
                else:
                    code = "".join(chr(ord('A') + n) for n in letters)
                    if code in self.passwords:
                        checkpoint, part_id = self.passwords[code]
                        return (part_id, checkpoint)
                    error = True
                    dirty = True
            self.timer.sleep_ms(33)

    def _render_password(self, letters, cursor, error):
        self._blit_backdrop()
        self._draw_text_centered("ENTER CODE", 128, _C_LOGO_INTERIOR, scale=2)
        slot_w = 16
        gap = 16
        total_w = 4 * slot_w + 3 * gap
        start_x = (SCREEN_W - total_w) // 2
        box_y = 152
        for i in range(4):
            x = start_x + i * (slot_w + gap)
            ch = chr(ord('A') + letters[i])
            color = _C_HIGHLIGHT if i == cursor else _C_LOGO_INTERIOR
            self._draw_char(ch, x, box_y, color, scale=2)
            under_c = _C_HIGHLIGHT if i == cursor else _C_HINT
            for px in range(x - 2, x + slot_w + 2):
                self._set_pixel(px, box_y + 18, under_c)
        if error:
            self._draw_text_centered("INVALID CODE", 182, _C_ERROR)
        else:
            self._draw_text_centered("UP/DOWN CHANGE   LEFT/RIGHT MOVE", 182, _C_HINT)
        self._draw_text_centered("SPACE=NEXT   ESC=BACK", 192, _C_HINT)

    # --- Backdrop (cached) -------------------------------------------------

    def _build_backdrop(self):
        """Compose the cached backdrop: scene bitmap + logo overlay.

        Runs once per title-screen session; subsequent frames just copy it.
        """
        # Start from the baked scene framebuffer (the iconic 'Cite' vista).
        self.buf[:] = BACKDROP_DATA

        # Logo, centred horizontally near the top.
        logo_x = (SCREEN_W - LOGO_W) // 2
        self._blit_logo(logo_x, 12)

        self._backdrop = bytes(self.buf)

    def _blit_backdrop(self):
        if self._backdrop is None:
            self._build_backdrop()
        # bytearray[:] = bytes is a fast copy
        self.buf[:] = self._backdrop

    # --- Logo blit ---------------------------------------------------------

    def _blit_logo(self, x, y):
        """Blit the baked 2bpp logo mask at (x, y) onto self.buf.

        Mask codes per pixel: 0=transparent (skip), 1=white interior,
        2=black outline. The 4bpp framebuffer is updated in place.
        """
        data = LOGO_DATA
        w = LOGO_W
        h = LOGO_H
        buf = self.buf
        c_in = _C_LOGO_INTERIOR
        c_out = _C_LOGO_OUTLINE
        idx = 0
        for ly in range(h):
            py = y + ly
            if py < 0 or py >= SCREEN_H:
                idx += w
                continue
            row_off = py * STRIDE
            for lx in range(w):
                code = (data[idx >> 2] >> ((3 - (idx & 3)) * 2)) & 3
                idx += 1
                if code == 0:
                    continue
                px = x + lx
                if px < 0 or px >= SCREEN_W:
                    continue
                c = c_in if code == 1 else c_out
                off = row_off + (px >> 1)
                if px & 1:
                    buf[off] = (buf[off] & 0xF0) | c
                else:
                    buf[off] = (buf[off] & 0x0F) | (c << 4)

    # --- Fill primitives ---------------------------------------------------

    def _set_pixel(self, x, y, c):
        if x < 0 or x >= SCREEN_W or y < 0 or y >= SCREEN_H:
            return
        off = y * STRIDE + (x >> 1)
        if x & 1:
            self.buf[off] = (self.buf[off] & 0xF0) | (c & 0x0F)
        else:
            self.buf[off] = (self.buf[off] & 0x0F) | ((c & 0x0F) << 4)

    def _rect_fill(self, x0, y0, x1, y1, c):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self._set_pixel(x, y, c)

    # --- Text (8×8 font) ---------------------------------------------------

    def _draw_char(self, ch, x, y, color, scale=1):
        idx = ord(ch) - 0x20
        if idx < 0 or idx * 8 + 7 >= len(FONT):
            return
        off = idx * 8
        for row in range(8):
            bits = FONT[off + row]
            py = y + row * scale
            for col in range(8):
                if bits & 0x80:
                    px = x + col * scale
                    if scale == 1:
                        self._set_pixel(px, py, color)
                    else:
                        self._rect_fill(px, py, px + scale - 1,
                                        py + scale - 1, color)
                bits = (bits << 1) & 0xFF

    def _draw_text(self, text, x, y, color, scale=1):
        for i, ch in enumerate(text):
            self._draw_char(ch, x + i * 8 * scale, y, color, scale)

    def _draw_text_centered(self, text, y, color, scale=1):
        w = len(text) * 8 * scale
        x = (SCREEN_W - w) // 2
        self._draw_text(text, x, y, color, scale)

    # --- Input -------------------------------------------------------------

    def _poll_edges(self):
        s = self.input.poll()
        prev = self._prev
        edges = {
            "action": s.action and not prev["action"],
            "up": s.up and not prev["up"],
            "down": s.down and not prev["down"],
            "left": s.left and not prev["left"],
            "right": s.right and not prev["right"],
            "quit": s.quit,
        }
        prev["action"] = s.action
        prev["up"] = s.up
        prev["down"] = s.down
        prev["left"] = s.left
        prev["right"] = s.right
        return edges

    def _drain_input(self):
        for _ in range(30):
            s = self.input.poll()
            if not (s.action or s.up or s.down or s.left or s.right):
                break
            self.timer.sleep_ms(16)
        for k in self._prev:
            self._prev[k] = False
