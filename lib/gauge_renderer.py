import st7789py as st7789
import drawing


class GaugeRenderer:
    """
    Owns all stateful rendering for a Gauge: pre-computed segment polygons,
    visibility caches that skip redundant SPI writes, and readout layout state.
    """

    def __init__(self, display, palette, gauge_text, origin, radius, arc_width,
                 angles, primary_segments, primary_color_index, readout_pos,
                 font_major, font_mini, font_minor=None,
                 secondary=False, secondary_segments=None,
                 secondary_color_index=None):

        self.display     = display
        self.palette     = palette
        self.readout_pos = readout_pos
        self.font_major  = font_major
        self.font_minor  = font_minor
        self.font_mini   = font_mini

        ox, oy = origin['x'], origin['y']

        self._primary_polys = [
            drawing.segment_polygon(ox, oy, radius, arc_width,
                                    angles['start'], primary_segments - 1 - i,
                                    primary_segments, angles['spread'])
            for i in range(primary_segments)
        ]
        self._primary_colors = [primary_color_index] * primary_segments
        self.primary_visible = [False] * primary_segments

        if secondary:
            self._secondary_polys = [
                drawing.segment_polygon(ox, oy, radius, arc_width,
                                        angles['start'] + angles['spread'],
                                        i, secondary_segments,
                                        angles['secondary_spread'])
                for i in range(secondary_segments)
            ]
            self._secondary_colors = [secondary_color_index] * secondary_segments
            self.secondary_visible = [False] * secondary_segments

        # Readout layout caches
        self._last_major_x    = None
        self._last_minor_end  = None
        self._minor_dot_drawn = False

        # Draw static units label once at init
        self._draw_units(gauge_text['units'])

    def _draw_units(self, units_text):
        drawing.draw_text(
            self.display,
            self.font_mini,
            units_text,
            self.readout_pos['x_units'],
            self.readout_pos['y_units'],
            self.palette[16],
            st7789.BLACK,
        )

    def set_primary_segment(self, index, visible, color_index=None):
        """Show or hide a primary segment, redrawing only on state change."""
        if color_index is not None and color_index != self._primary_colors[index]:
            self._primary_colors[index] = color_index
            if self.primary_visible[index]:
                # Force redraw with new colour
                self.primary_visible[index] = not visible

        if visible == self.primary_visible[index]:
            return  # No change — skip SPI write

        self.primary_visible[index] = visible
        color = self.palette[self._primary_colors[index]] if visible else st7789.BLACK
        drawing.fill_polygon(self.display, self._primary_polys[index], color)

    def set_secondary_segment(self, index, visible):
        if visible == self.secondary_visible[index]:
            return
        self.secondary_visible[index] = visible
        color = self.palette[self._secondary_colors[index]] if visible else st7789.BLACK
        drawing.fill_polygon(self.display, self._secondary_polys[index], color)

    def draw_readout(self, major_text, minor_text=None):
        rp = self.readout_pos
        font = self.font_major

        # Pre-compute minor layout and clear rightover digit pixels before anything is drawn
        if minor_text is not None and self.font_minor:
            font_m   = self.font_minor
            y_minor  = rp['y'] - font_m.height() - 3
            _, _, dot_w  = font_m.get_ch(minor_text[0])
            x_digit      = rp['x_minor'] + dot_w
            digit_text   = minor_text[1:]
            digit_w      = sum(font_m.get_ch(ch)[2] for ch in digit_text)
            x_digit_end  = x_digit + digit_w
            if self._last_minor_end is not None and self._last_minor_end > x_digit_end:
                self.display.fill_rect(x_digit_end, y_minor,
                                       self._last_minor_end - x_digit_end, font_m.height(), st7789.BLACK)
            self._last_minor_end = x_digit_end

        # Major text (right-aligned, bottom-anchored)
        total_w = sum(font.get_ch(ch)[2] for ch in major_text)
        x_start = rp['x'] - total_w
        y_start = rp['y'] - font.height()

        if self._last_major_x is not None and self._last_major_x < x_start:
            self.display.fill_rect(self._last_major_x, y_start,
                                   x_start - self._last_major_x, font.height(), st7789.BLACK)

        self._last_major_x = x_start
        drawing.draw_text(self.display, font, major_text, x_start, y_start,
                          self.palette[16], st7789.BLACK)

        # Minor text: dot drawn once on first call; only proceeding digits redrawn each call
        if minor_text is not None and self.font_minor:
            if not self._minor_dot_drawn:
                drawing.draw_text(self.display, font_m, minor_text, rp['x_minor'], y_minor,
                                  self.palette[16], st7789.BLACK)
                self._minor_dot_drawn = True
            else:
                drawing.draw_text(self.display, font_m, digit_text, x_digit, y_minor,
                                  self.palette[16], st7789.BLACK)
