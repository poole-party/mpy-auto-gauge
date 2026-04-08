import math
import st7789
from temperature import Temperature

# ── Constants ─────────────────────────────────────────────────────────────────

BOOST_OFFSET        = 13.88
MAX_BOOST           = 10
MAX_VACUUM          = 15
MAX_TEMP            = 300
MIN_TEMP            = 180
DANGER_TEMP_START   = 285
CAUTION_TEMP_START  = 270
OP_TEMP_START       = 200
SAMPLE_SIZE         = 50
GAP_RATIO           = 0.6   # controls visual gap between arc segments


# ── Helpers ───────────────────────────────────────────────────────────────────

def _segment_polygon(origin_x, origin_y, radius, arc_width, angle_start, segment_index,
                     segment_count, spread):
    """Return a list of 4 (x, y) tuples defining one arc segment polygon."""
    seg_width  = spread / segment_count
    seg_center = segment_index * seg_width + seg_width / 2
    reduced    = seg_width * GAP_RATIO
    points     = [None] * 4
    for j in range(2):
        alpha = math.radians((seg_center + (j - 0.5) * reduced) + angle_start)
        cos_a, sin_a = math.cos(alpha), math.sin(alpha)
        points[j]     = (origin_x + int(radius * cos_a),
                         origin_y - int(radius * sin_a))
        points[3 - j] = (origin_x + int((radius - arc_width) * cos_a),
                         origin_y - int((radius - arc_width) * sin_a))
    return points


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

        # Load fonts (russhughes driver accepts module references or path strings)
        import st7789
        self.font_major = font_major
        self.font_minor = font_minor
        self.font_mini  = font_mini

        # Pre-compute segment polygons so we're not doing trig every frame
        ox, oy = origin['x'], origin['y']

        self._primary_polys = [
            _segment_polygon(ox, oy, radius, arc_width,
                             angles['start'], i, primary_segments, angles['spread'])
            for i in range(primary_segments)
        ]
        self._primary_colors = [primary_color_index] * primary_segments
        self._primary_visible = [False] * primary_segments

        if secondary:
            self._secondary_polys = [
                _segment_polygon(ox, oy, radius, arc_width,
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

        # Draw static elements (units label) once at init
        self._draw_units()

    # ── Drawing primitives ────────────────────────────────────────────────────

    def _draw_units(self):
        self.display.text(
            self.font_mini,
            self.gauge_text['units'],
            self.readout_pos['x_units'],
            self.readout_pos['y_units'],
            self.palette[16],
            st7789.BLACK,
        )

    def _set_primary_segment(self, index, visible, color_index=None):
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
        self.display.polygon(self._primary_polys[index], 0, 0, color, True, 0, 0)

    def _set_secondary_segment(self, index, visible):
        if visible == self._secondary_visible[index]:
            return
        self._secondary_visible[index] = visible
        color = self.palette[self._secondary_colors[index]] if visible else st7789.BLACK
        self.display.polygon(self._secondary_polys[index], 0, 0, color, True, 0, 0)

    def _draw_readout(self, major_text, minor_text=None):
        rp = self.readout_pos
        self.display.text(
            self.font_major,
            major_text,
            rp['x'],
            rp['y'],
            self.palette[16],
            st7789.BLACK,
        )
        if minor_text is not None and self.font_minor:
            self.display.text(
                self.font_minor,
                minor_text,
                rp['x_minor'],
                rp['y'],
                self.palette[16],
                st7789.BLACK,
            )

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, value, options=None):
        if options is None:
            options = {}
        if self.gauge_type == 'boost':
            self._update_boost(value, options)
        elif self.gauge_type in ('temperature', 'temp'):
            self._update_temperature(value, options)

    # ── Boost ─────────────────────────────────────────────────────────────────

    def _update_boost(self, value, options):
        # Demo mode: sweep 0–25 then repeat, mapped to -15..+10 PSI
        if options.get('demo'):
            if not hasattr(self, '_test_value'):
                self._test_value = 0
            mdp_next = (self._test_value - 150) / 10
            self._test_value = (self._test_value + 2) % 251
        else:
            mdp_next = value / 1000 - BOOST_OFFSET

        if self._mdp_current is None:
            self._mdp_current = mdp_next

        # Numeric readout
        parts = f'{mdp_next:.1f}'.split('.')
        self._draw_readout(parts[0], '.' + parts[-1])

        mdp_cur = self._mdp_current
        lvl_cur = self._bar_level
        n_pri   = self.primary_segments
        n_sec   = self.secondary_segments

        # Positive → boost arc; negative → vacuum arc
        if mdp_cur >= 0 and mdp_next >= 0:
            # Both positive: adjust boost bar
            lvl_next = min(int(mdp_next / (MAX_BOOST / (n_pri - 1))), n_pri - 1)
            if lvl_next > lvl_cur or (not self._primary_visible[0] and mdp_next >= 0.1):
                for i in range(lvl_cur, lvl_next + 1):
                    self._set_primary_segment(i, True)
            elif lvl_next < lvl_cur:
                for i in range(lvl_cur, lvl_next, -1):
                    self._set_primary_segment(i, False)
            self._bar_level = lvl_next

        elif mdp_cur < 0 and mdp_next < 0:
            # Both negative: adjust vacuum bar
            lvl_next = min(int(abs(mdp_next) / (MAX_VACUUM / (n_sec - 1))), n_sec - 1)
            if lvl_next > lvl_cur or (not self._secondary_visible[0] and mdp_next <= -0.1):
                for i in range(lvl_cur, lvl_next + 1):
                    self._set_secondary_segment(i, True)
            elif lvl_next < lvl_cur:
                for i in range(lvl_cur, lvl_next, -1):
                    self._set_secondary_segment(i, False)
            self._bar_level = lvl_next

        elif mdp_cur >= 0 and mdp_next < 0:
            # Boost → vacuum transition
            lvl_next = min(int(abs(mdp_next) / (MAX_VACUUM / (n_sec - 1))), n_sec - 1)
            for i in range(lvl_cur, -1, -1):
                self._set_primary_segment(i, False)
            for i in range(lvl_next + 1):
                self._set_secondary_segment(i, True)
            self._bar_level = lvl_next

        else:
            # Vacuum → boost transition
            lvl_next = min(int(mdp_next / (MAX_BOOST / (n_pri - 1))), n_pri - 1)
            for i in range(lvl_cur, -1, -1):
                self._set_secondary_segment(i, False)
            for i in range(lvl_next + 1):
                self._set_primary_segment(i, True)
            self._bar_level = lvl_next

        self._mdp_current = mdp_next

    # ── Temperature ───────────────────────────────────────────────────────────

    def _update_temperature(self, value, options):
        if options.get('demo'):
            if not hasattr(self, '_test_value'):
                self._test_value = 0
            self._test_value = (self._test_value + 2) % MIN_TEMP
            temp = self._test_value + 145
        else:
            temp = Temperature.lookup(value, options.get('units', 'f'))

        display_temp = '- -'
        lvl_next = -1

        if isinstance(temp, (int, float)) and temp > 0:
            display_temp = int(temp)
            raw_level = int((display_temp - MIN_TEMP) /
                            ((MAX_TEMP - MIN_TEMP) / (self.primary_segments - 1)))
            lvl_next = max(0, min(raw_level, self.primary_segments - 1))

        self._draw_readout(str(display_temp))

        lvl_cur = self._temp_level
        n       = self.primary_segments

        if not isinstance(display_temp, int) or temp - MIN_TEMP < 0:
            # Below operating range — show only the first (cold) segment
            for i in range(n):
                self._set_primary_segment(i, i == 0)
            lvl_next = -1

        elif lvl_next >= lvl_cur:
            for i in range(max(lvl_cur + 1, 0), lvl_next + 1):
                threshold = MIN_TEMP + (MAX_TEMP - MIN_TEMP) / (n - 1) * i
                if threshold >= DANGER_TEMP_START:
                    color_idx = 15
                elif threshold >= CAUTION_TEMP_START:
                    color_idx = 12
                elif threshold >= OP_TEMP_START:
                    color_idx = 6
                else:
                    color_idx = self.primary_color_index
                self._set_primary_segment(i, True, color_idx)

        else:
            for i in range(lvl_cur, lvl_next, -1):
                self._set_primary_segment(i, False)

        self._temp_level = lvl_next
