"""
writer.py — CWriter for st7789py on MicroPython (Raspberry Pi Pico)

A lightweight adaptation of Peter Hinch's cwriter.py that drives an
st7789py display directly instead of going through a FrameBuffer.

Original: https://github.com/peterhinch/micropython-font-to-py
Licence:  MIT

Font modules are produced by font_to_py.py with the -x flag (horizontal
bit-order), e.g.:
    python3 font_to_py.py -x Saira-Regular.ttf 32 saira_32.py

Usage
-----
    from lib.writer import CWriter
    import saira_32 as SAIRA_32

    wri = CWriter(display, SAIRA_32, fgcolor=0xFFFF, bgcolor=0x0000)

    # Draw a string — x, y is the TOP-LEFT of the text baseline row
    CWriter.set_textpos(display, row=100, col=50)
    wri.printstring("12.3")

    # Measure a string before drawing (for alignment)
    width = wri.stringlen("12.3")
"""

import framebuf


class CWriter:
    # Class-level cursor shared across all writers on the same display,
    # matching the behaviour of Hinch's original.
    _display_map: dict = {}

    @classmethod
    def set_textpos(cls, display, row: int, col: int):
        cls._display_map[id(display)] = [row, col]

    @classmethod
    def _get_textpos(cls, display):
        return cls._display_map.get(id(display), [0, 0])

    @classmethod
    def _set_textpos(cls, display, row: int, col: int):
        cls._display_map[id(display)] = [row, col]

    # ------------------------------------------------------------------

    def __init__(self, display, font, fgcolor=0xFFFF, bgcolor=0x0000):
        self.display = display
        self.font    = font
        self.fgcolor = fgcolor
        self.bgcolor = bgcolor

        # font_to_py fonts expose height() and optionally max_width().
        self._height = font.height()

        # Build a tiny 1-bit FrameBuffer for each glyph, then blit
        # pixel-by-pixel into the display.  We keep a reusable buffer
        # sized to the tallest/widest glyph to avoid repeated allocation.
        max_w = getattr(font, 'max_width', lambda: 64)()
        # bytes per row (1 bit per pixel, rounded up to byte boundary)
        stride = (max_w + 7) >> 3
        self._buf = bytearray(stride * self._height)
        self._fb  = framebuf.FrameBuffer(
            self._buf, max_w, self._height, framebuf.MONO_HLSB
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def height(self) -> int:
        return self._height

    def stringlen(self, string: str) -> int:
        """Return the pixel width of *string* in this font."""
        total = 0
        for ch in string:
            _, _, char_w = self.font.get_ch(ch)
            total += char_w
        return total

    def printstring(self, string: str):
        """Render *string* at the current text position."""
        pos = self._get_textpos(self.display)
        row, col = pos[0], pos[1]
        for ch in string:
            col = self._print_char(ch, row, col)
        self._set_textpos(self.display, row, col)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _print_char(self, ch: str, row: int, col: int) -> int:
        """Render one character; return the new column (col + char_width)."""
        glyph, _, char_w = self.font.get_ch(ch)
        if glyph is None or char_w == 0:
            return col + char_w

        h = self._height
        stride = (char_w + 7) >> 3

        # Re-use the buffer if it fits, otherwise allocate a fresh one.
        needed = stride * h
        if needed <= len(self._buf):
            buf = self._buf
        else:
            buf = bytearray(needed)

        # Copy glyph bytes into the buffer (font_to_py glyph is a bytes obj)
        buf[:needed] = glyph[:needed]

        fb = framebuf.FrameBuffer(buf, char_w, h, framebuf.MONO_HLSB)

        # Blit pixel-by-pixel into the display.
        # st7789py has no blit_buffer that accepts MONO; we do it manually.
        for dy in range(h):
            for dx in range(char_w):
                color = self.fgcolor if fb.pixel(dx, dy) else self.bgcolor
                self.display.pixel(col + dx, row + dy, color)

        return col + char_w