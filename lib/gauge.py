import math
from lib.temperature import Temperature

# Font modules — these must exist on the Pico at fonts/vga2_16x32.py etc.
# Download from: https://github.com/russhughes/st7789py_mpy/tree/master/fonts/bitmap
import fonts.vga2_16x32 as FONT_MAJOR   # 16x32px — main numeric readout
import fonts.vga1_16x32 as FONT_MINOR   # 16x32px — decimal portion
import fonts.vga2_8x8   as FONT_MINI    # 8x8px   — units label

# st7789py text() draws characters at their top-left corner.
# Each font has a fixed glyph size:
MAJOR_W, MAJOR_H = 16, 32
MINOR_W, MINOR_H = 16, 32
MINI_W,  MINI_H  =  8,  8

BOOST_OFFSET = 13.88
MAX_BOOST    = 10
MAX_VACUUM   = 15
MAX_TEMP     = 300

# ---------------------------------------------------------------------------
# Colour palette  (RGB888 -> RGB565)
# ---------------------------------------------------------------------------
def _rgb888_to_rgb565(c):
    r = (c >> 16) & 0xFF
    g = (c >>  8) & 0xFF
    b =  c        & 0xFF
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

PALETTE = [_rgb888_to_rgb565(c) for c in [
    0xdddddd,  # 0  light grey
    0x00aaff,  # 1  azure
    0x00c8fa,  # 2  turquoise
    0x00e4fa,  # 3  cyan
    0x00fae5,  # 4  aqua
    0x00ff80,  # 5  spring green
    0x03ff03,  # 6  green
    0x55ff00,  # 7  bright green
    0xb7ff00,  # 8  lime
    0xe1ff00,  # 9  chartreuse
    0xffff00,  # 10 bright yellow
    0xfff700,  # 11 yellow
    0xffd500,  # 12 gold
    0xff9500,  # 13 orange
    0xff5500,  # 14 red-orange
    0xff0303,  # 15 red
    0xffffff,  # 16 white
]]

# ---------------------------------------------------------------------------
# Segment geometry
# ---------------------------------------------------------------------------
# GAP_DEGREES controls the angular space between pills.
# RADIAL_INSET controls the pixel gap on the inner/outer arc edges.
# Tweak these two constants to adjust the look.
GAP_DEGREES  = 3.0   # degrees of empty space between adjacent pills
RADIAL_INSET = 2     # pixels inset from inner and outer arc edges

def _segment_points(i, radius, arc_width, spread, start_angle, num_segments):
    """
    Return 4 (x, y) corners for segment i, inset on all sides so each
    segment appears as a discrete rounded pill with a gap around it.
    """
    segment_span = spread / num_segments      # degrees per full slot
    half_gap     = GAP_DEGREES / 2.0

    # Angular edges of this pill (inset from the slot boundaries)
    a_start = i       * segment_span + start_angle + half_gap
    a_end   = (i + 1) * segment_span + start_angle - half_gap

    # Radial edges of this pill (inset from arc inner/outer edges)
    r_outer = radius            - RADIAL_INSET
    r_inner = radius - arc_width + RADIAL_INSET

    points = [None] * 4
    for j, angle_deg in enumerate([a_start, a_end]):
        alpha = angle_deg / 180.0 * math.pi
        x0 = int(r_outer * math.cos(alpha))
        y0 = -int(r_outer * math.sin(alpha))
        x1 = int(r_inner * math.cos(alpha))
        y1 = -int(r_inner * math.sin(alpha))
        points[0 + j] = (x0, y0)
        points[3 - j] = (x1, y1)
    return points


def _draw_filled_polygon(display, pts, ox, oy, color):
    """Fill a convex quadrilateral using horizontal scanlines."""
    px = [p[0] + ox for p in pts]
    py = [p[1] + oy for p in pts]
    min_y = min(py)
    max_y = max(py)
    n = len(px)
    for y in range(min_y, max_y + 1):
        xs = []
        for i in range(n):
            x0, y0 = px[i], py[i]
            x1, y1 = px[(i + 1) % n], py[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                if y1 == y0:
                    continue
                xs.append(int(x0 + (x1 - x0) * (y - y0) / (y1 - y0)))
        if len(xs) >= 2:
            xs.sort()
            display.hline(xs[0], y, xs[-1] - xs[0] + 1, color)


# def _draw_arc_outline(display, ox, oy, radius, arc_width, start_angle,
#                       spread, num_segments, color):
#     for i in range(num_segments):
#         pts = _segment_points(i, radius + 2, arc_width + 4,
#                               spread, start_angle, num_segments)
#         n = len(pts)
#         for k in range(n):
#             x0 = pts[k][0] + ox
#             y0 = pts[k][1] + oy
#             x1 = pts[(k + 1) % n][0] + ox
#             y1 = pts[(k + 1) % n][1] + oy
#             display.line(x0, y0, x1, y1, color)


# ---------------------------------------------------------------------------
# Gauge class
# ---------------------------------------------------------------------------
class Gauge:
    """
    MicroPython / st7789py port of the CircuitPython Gauge class.

    Text is rendered with st7789py's  display.text(font_module, string, x, y, color)
    where x, y is the TOP-LEFT corner of the text.  All readout_pos coordinates
    are treated as the bottom-right anchor (matching the original anchored_position
    logic) and converted internally.
    """

    def __init__(self, display, bg_color=0x0000,
                 gauge_type='boost', gauge_text=None,
                 origin=None, radius=135, arc_width=30,
                 angles=None, primary_segments=15,
                 primary_color_index=1, palette=None,
                 readout_pos=None,
                 secondary=False, secondary_segments=None,
                 secondary_color_index=None):

        self.display          = display
        self.bg_color         = bg_color
        self.gauge_type       = gauge_type
        self.gauge_text       = gauge_text or {}
        self.primary_segments = primary_segments
        self.secondary        = secondary
        self.secondary_segments = secondary_segments

        self.ox        = int(origin['x'])
        self.oy        = int(origin['y'])
        self.radius    = radius
        self.arc_width = arc_width
        self.angles    = angles or {'start': 45, 'spread': 90}
        self.palette   = palette if palette is not None else PALETTE
        self.primary_color_index   = primary_color_index
        self.secondary_color_index = secondary_color_index
        self.readout_pos = readout_pos or {}

        # Pre-compute segment geometry (reversed so index 0 = lowest segment)
        self._primary_pts = []

        # Precompute per-segment colors for temperature gauges
        self._segment_colors = [
            self._temp_color_for_segment(i) for i in range(self.primary_segments)
        ]

        for i in range(self.primary_segments):
            pts = _segment_points(i, radius, arc_width,
                                  self.angles['spread'],
                                  self.angles['start'],
                                  primary_segments)
            self._primary_pts.insert(0, pts)
        self._primary_visible = [False] * primary_segments

        self._secondary_pts     = []
        self._secondary_visible = []
        if secondary and secondary_segments:
            for i in range(secondary_segments):
                pts = _segment_points(
                    i, radius, arc_width,
                    self.angles.get('secondary_spread', 45),
                    self.angles['start'] + self.angles['spread'],
                    secondary_segments)
                self._secondary_pts.append(pts)
                self._secondary_visible.append(False)

        # Cached readout strings (used to erase before redrawing)
        self._last_major = ''
        self._last_minor = ''

        # Draw static elements once
        self._draw_template()
        self._draw_units()

    # ------------------------------------------------------------------
    # Static draw helpers
    # ------------------------------------------------------------------
    def _draw_template(self):
        total = self.primary_segments + (self.secondary_segments or 0)
        # _draw_arc_outline(self.display, self.ox, self.oy,
        #                   self.radius, self.arc_width,
        #                   self.angles['start'], 135,
        #                   total, self.palette[0])

    def _draw_units(self):
        text = self.gauge_text.get('units', '')
        ux = int(self.readout_pos.get('x-units', self.ox))
        uy = int(self.readout_pos.get('y-units', self.oy))
        # Centre-align: x-units is the horizontal centre point
        x = ux - (len(text) * MINI_W) // 2
        # y-units is the bottom edge in the original; subtract font height
        y = uy - MINI_H
        self.display.text(FONT_MINI, text, x, y, self.palette[16])

    def _draw_segment(self, pts, color):
        _draw_filled_polygon(self.display, pts, self.ox, self.oy, color)

    def _show_primary(self, index, visible):
        if self._primary_visible[index] == visible:
            return
        if visible and self.gauge_type in ('temperature', 'temp'):
            color = self.palette[self._segment_colors[index]]
        elif visible:
            color = self.palette[self.primary_color_index]
        else:
            color = self.bg_color
        self._draw_segment(self._primary_pts[index], color)
        self._primary_visible[index] = visible

    def _show_secondary(self, index, visible):
        if self._secondary_visible[index] == visible:
            return
        color = self.palette[self.secondary_color_index] if visible else self.bg_color
        self._draw_segment(self._secondary_pts[index], color)
        self._secondary_visible[index] = visible

    def _temp_color_for_segment(self, seg_index):
        frac = seg_index / (self.primary_segments - 1)
        temp = 150 + frac * (MAX_TEMP - 150)
        if temp >= 300:
            return 14
        elif temp >= 285:
            return 13
        elif temp >= 270:
            return 12
        elif temp >= 200:
            return 6
        else:
            return 1

    # ------------------------------------------------------------------
    # Text readout
    # st7789py text() uses TOP-LEFT coords.
    # readout_pos x/y in the original were BOTTOM-RIGHT anchors, so we
    # subtract the text dimensions to find the top-left draw position.
    # ------------------------------------------------------------------
    def _erase_text(self, x, y, text, font_w, font_h):
        if text:
            w = len(text) * font_w
            self.display.fill_rect(x, y, w, font_h, self.bg_color)

    def _update_readout(self, major_text, minor_text=None):
        rx = int(self.readout_pos.get('x', self.ox))
        ry = int(self.readout_pos.get('y', self.oy))

        # Major (large) number — right-aligned to rx, bottom-aligned to ry
        major_w = len(major_text) * MAJOR_W
        major_x = rx - major_w
        major_y = ry - MAJOR_H

        if self._last_major:
            old_w = len(self._last_major) * MAJOR_W
            self.display.fill_rect(rx - old_w, major_y, old_w, MAJOR_H, self.bg_color)

        self.display.text(FONT_MAJOR, str(major_text), major_x, major_y, self.palette[16])
        self._last_major = major_text

        # Minor (decimal) number — left-aligned to x-minor
        if minor_text is not None:
            mx = int(self.readout_pos.get('x-minor', rx))
            minor_y = ry - MINOR_H
            if self._last_minor:
                old_w = len(self._last_minor) * MINOR_W
                self.display.fill_rect(mx, minor_y, old_w, MINOR_H, self.bg_color)
            self.display.text(FONT_MINOR, str(minor_text), mx, minor_y, self.palette[16])
            self._last_minor = minor_text

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update_gauge(self, value, options=None):
        if options is None:
            options = {}
        if self.gauge_type == 'boost':
            self.update_boost(value, options)
        elif self.gauge_type in ('temperature', 'temp'):
            self.update_temperature(value, options)

    def update_boost(self, value, options=None):
        if options is None:
            options = {}

        if options['demo'] == True:
            try:
                mdp_next = (self.test_value - 150) / 10
            except AttributeError:
                self.test_value = 0
                mdp_next = (self.test_value - 150) / 10
            self.test_value = (self.test_value + 2) % 251
        else:
            mdp_next = value / 1000 - BOOST_OFFSET

        if not hasattr(self, 'mdp_current'):
            self.mdp_current = mdp_next
        if not hasattr(self, 'bar_level_current'):
            self.bar_level_current = 0

        parts = '{:.1f}'.format(mdp_next).split('.')
        self._update_readout(parts[0], '.' + parts[-1])

        bar_level_next = 0

        if self.mdp_current > 0 and mdp_next > 0:
            bar_level_next = int(mdp_next / (MAX_BOOST / (self.primary_segments - 1)))
            if bar_level_next >= self.primary_segments:
                bar_level_next = self.primary_segments - 1
            if bar_level_next > self.bar_level_current or \
                    (not self._primary_visible[0] and mdp_next >= 0.1):
                for i in range(self.bar_level_current, bar_level_next + 1):
                    self._show_primary(i, True)
            elif bar_level_next < self.bar_level_current:
                for i in range(self.bar_level_current, bar_level_next, -1):
                    self._show_primary(i, False)

        elif self.mdp_current < 0 and mdp_next < 0:
            bar_level_next = int(math.fabs(mdp_next) / (MAX_VACUUM / (self.secondary_segments - 1)))
            if bar_level_next >= self.secondary_segments:
                bar_level_next = self.secondary_segments - 1
            if bar_level_next > self.bar_level_current or \
                    (not self._secondary_visible[0] and mdp_next <= -0.1):
                for i in range(self.bar_level_current, bar_level_next + 1):
                    self._show_secondary(i, True)
            elif bar_level_next < self.bar_level_current:
                for i in range(self.bar_level_current, bar_level_next, -1):
                    self._show_secondary(i, False)

        elif self.mdp_current >= 0 and mdp_next < 0:
            bar_level_next = int(math.fabs(mdp_next) / (MAX_VACUUM / (self.secondary_segments - 1)))
            if bar_level_next >= self.secondary_segments:
                bar_level_next = self.secondary_segments - 1
            for i in range(self.bar_level_current, -1, -1):
                self._show_primary(i, False)
            for i in range(0, bar_level_next + 1):
                self._show_secondary(i, True)

        elif self.mdp_current < 0 and mdp_next >= 0:
            bar_level_next = int(mdp_next / (MAX_BOOST / (self.primary_segments - 1)))
            if bar_level_next >= self.primary_segments:
                bar_level_next = self.primary_segments - 1
            for i in range(self.bar_level_current, -1, -1):
                self._show_secondary(i, False)
            for i in range(0, bar_level_next + 1):
                self._show_primary(i, True)

        self.mdp_current = mdp_next
        try:
            self.bar_level_current = bar_level_next
        except NameError:
            pass

    def update_temperature(self, value, options=None):
        if options is None:
            options = {}

        if options['demo'] == True:
            print("Thermistor Value:", value)
            try:
                self.test_value = (self.test_value + 2) % 150
            except AttributeError:
                self.test_value = 0
            temp = self.test_value + 145
        else:
            temp = Temperature.lookup(value, options.get('units', 'c'))

        display_temp = '- - '
        temp_level_next = -1

        if temp > 0:
            display_temp = temp
            temp_level_next = int(
                (display_temp - 150) / ((MAX_TEMP - 150) / (self.primary_segments - 1))
            )
            if not hasattr(self, 'temp_level_current'):
                self.temp_level_current = -1

        self._update_readout(str(display_temp))

        if options['demo'] == True:
            print("Display Temp:", display_temp)

        if not isinstance(display_temp, int) or display_temp - 150 < 0:
            for i in range(self.primary_segments):
                self._show_primary(i, False)
            temp_level_next = -1
        elif temp_level_next > self.primary_segments - 1:
            temp_level_next = self.primary_segments - 1
            for i in range(getattr(self, 'temp_level_current', -1) + 1, temp_level_next + 1):
                self._show_primary(i, True)
        elif temp_level_next >= getattr(self, 'temp_level_current', -1):
            for i in range(getattr(self, 'temp_level_current', -1) + 1, temp_level_next + 1):
                self._show_primary(i, True)
        elif temp_level_next < getattr(self, 'temp_level_current', -1):
            for i in range(getattr(self, 'temp_level_current', -1), temp_level_next, -1):
                self._show_primary(i, False)

        # _set_primary_color call is REMOVED — colors are now per-segment
        self.temp_level_current = temp_level_next