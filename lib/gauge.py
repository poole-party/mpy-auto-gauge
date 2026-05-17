import st7789py as st7789
import drawing
import boost_gauge
import temp_gauge


class Gauge:
    """
    A single arc-style segmented gauge for the russhughes st7789_mpy driver.

    All drawing is immediate-mode: segments are re-drawn every update call
    only when their visibility or colour changes, keeping SPI traffic low.

    Parameters
    ----------
    display             : st7789.ST7789 instance
    palette             : list of RGB565 colour ints (index matches original bar_palette)
    gauge_type          : 'boost' | 'temperature'
    gauge_text          : {'description': str, 'units': str}
    origin              : {'x': int, 'y': int}  — arc pivot point
    radius              : outer arc radius in pixels
    arc_width           : radial thickness of the arc segments
    angles              : {'start': deg, 'spread': deg}
                          optionally {'secondary_spread': deg} for boost
    primary_segments    : number of segments in the primary (boost/temp) arc
    primary_color_index : default palette index for primary segments
    palette             : list of RGB565 colour ints
    readout_pos         : {'x', 'y', 'x_minor'(opt), 'x_units', 'y_units'}
    font_major          : path stem for the large readout font
    font_minor          : path stem for the decimal readout font (boost only)
    font_mini           : path stem for the units label font
    secondary           : bool — enable secondary (vacuum) arc
    secondary_segments  : segment count for vacuum arc
    secondary_color_index : palette index for vacuum arc
    """

    def __init__(self, display, palette, gauge_type, gauge_text, origin, radius,
                 arc_width, angles, primary_segments, primary_color_index,
                 readout_pos, font_major, font_mini,
                 font_minor=None, secondary=False,
                 secondary_segments=None, secondary_color_index=None):

        self.display              = display
        self.palette              = palette
        self.gauge_type           = gauge_type
        self.gauge_text           = gauge_text
        self.origin               = origin
        self.radius               = radius
        self.arc_width            = arc_width
        self.angles               = angles
        self.primary_segments     = primary_segments
        self.primary_color_index  = primary_color_index
        self.readout_pos          = readout_pos
        self.secondary            = secondary
        self.secondary_segments   = secondary_segments
        self.secondary_color_index = secondary_color_index

        self.font_major = font_major
        self.font_minor = font_minor
        self.font_mini  = font_mini

        # Pre-compute segment polygons so we're not doing trig every frame
        ox, oy = origin['x'], origin['y']

        self._primary_polys = [
            drawing.segment_polygon(ox, oy, radius, arc_width,
                                    angles['start'], primary_segments - 1 - i, primary_segments, angles['spread'])
            for i in range(primary_segments)
        ]
        self._primary_colors = [primary_color_index] * primary_segments
        self._primary_visible = [False] * primary_segments

        if secondary:
            self._secondary_polys = [
                drawing.segment_polygon(ox, oy, radius, arc_width,
                                        angles['start'] + angles['spread'],
                                        i, secondary_segments, angles['secondary_spread'])
                for i in range(secondary_segments)
            ]
            self._secondary_colors   = [secondary_color_index] * secondary_segments
            self._secondary_visible  = [False] * secondary_segments

        # State tracking
        self._bar_level    = 0
        self._temp_level   = -1
        self._mdp_current  = None
        self._last_major_x    = None
        self._last_minor_end  = None
        self._minor_dot_drawn = False

        # Draw static elements (units label) once at init
        self._draw_units()

    # ── Drawing primitives ────────────────────────────────────────────────────

    def _draw_units(self):
        drawing.draw_text(
            self.display,
            self.font_mini,
            self.gauge_text['units'],
            self.readout_pos['x_units'],
            self.readout_pos['y_units'],
            self.palette[16],
            st7789.BLACK,
        )

    def set_primary_segment(self, index, visible, color_index=None):
        """Show or hide a primary segment, redrawing only on state change."""
        if color_index is not None and color_index != self._primary_colors[index]:
            self._primary_colors[index] = color_index
            if self._primary_visible[index]:
                # Force redraw with new colour
                self._primary_visible[index] = not visible

        if visible == self._primary_visible[index]:
            return  # No change — skip SPI write

        self._primary_visible[index] = visible
        color = self.palette[self._primary_colors[index]] if visible else st7789.BLACK
        drawing.fill_polygon(self.display, self._primary_polys[index], color)

    def set_secondary_segment(self, index, visible):
        if visible == self._secondary_visible[index]:
            return
        self._secondary_visible[index] = visible
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

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, value, options=None):
        if options is None:
            options = {}
        if self.gauge_type == 'boost':
            boost_gauge.update(self, value, options)
        elif self.gauge_type in ('temperature', 'temp'):
            temp_gauge.update(self, value, options)
