from gauge_renderer import GaugeRenderer
import boost_gauge
import temp_gauge
import rpm_gauge
import afr_gauge


class Gauge:
    """
    A single arc-style segmented gauge. Holds the logic-side state
    (current level, last reading) and dispatches updates to the per-type
    update module. All rendering lives on `self.renderer`.

    Parameters
    ----------
    display             : st7789.ST7789 instance
    palette             : list of RGB565 colour ints
    gauge_type          : 'boost' | 'bar' | 'temperature' | 'rpm' | 'afr'
                          ('temperature' is kept as an alias for 'bar')
    gauge_text          : {'description': str, 'units': str}
    origin              : {'x': int, 'y': int}  — arc pivot point
    radius              : outer arc radius in pixels
    arc_width           : radial thickness of the arc segments
    angles              : {'start': deg, 'spread': deg}
                          optionally {'secondary_spread': deg}
    primary_segments    : number of segments in the primary arc
    primary_color_index : default palette index for primary segments
    readout_pos         : {'x', 'y', 'x_minor'(opt), 'x_units', 'y_units'}
    font_major          : large readout font module
    font_minor          : decimal readout font module (boost/afr only)
    font_mini           : units label font module
    secondary           : bool — enable secondary arc (boost/afr)
    secondary_segments  : segment count for secondary arc
    secondary_color_index : palette index for secondary arc
    bar_config          : {'min', 'max', 'thresholds', 'default_color'} —
                          required for 'bar', 'temperature', and 'rpm' types
    """

    def __init__(self, display, palette, gauge_type, gauge_text, origin, radius,
                 arc_width, angles, primary_segments, primary_color_index,
                 readout_pos, font_major, font_mini,
                 font_minor=None, secondary=False,
                 secondary_segments=None, secondary_color_index=None,
                 bar_config=None):

        self.gauge_type           = gauge_type
        self.primary_segments     = primary_segments
        self.primary_color_index  = primary_color_index
        self.secondary            = secondary
        self.secondary_segments   = secondary_segments
        self.bar_config           = bar_config

        self.renderer = GaugeRenderer(
            display, palette, gauge_text, origin, radius, arc_width, angles,
            primary_segments, primary_color_index, readout_pos,
            font_major, font_mini, font_minor,
            secondary, secondary_segments, secondary_color_index,
        )

        # Logic-side state
        self._bar_level   = 0
        self._temp_level  = -1
        self._mdp_current = None

    def update(self, value, options=None):
        if options is None:
            options = {}
        t = self.gauge_type
        if t == 'boost':
            boost_gauge.update(self, value, options)
        elif t in ('bar', 'temperature', 'temp'):
            temp_gauge.update(self, value, options)
        elif t == 'rpm':
            rpm_gauge.update(self, value, options)
        elif t == 'afr':
            afr_gauge.update(self, value, options)
