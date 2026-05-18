import machine
import time
import st7789py as st7789
from gauge import Gauge
from can_bus import CanBus
from temperature import Temperature

import fonts.saira_bold_italic_56 as font_56
import fonts.saira_bold_italic_43 as font_43
import fonts.saira_semibold_20 as font_20

# ── Pin map ───────────────────────────────────────────────────────────────────
# Displays share SPI0 (CAN owns SPI1 GP8-12 via the Waveshare board).
PIN_DISP_SCK   = 2
PIN_DISP_MOSI  = 3
PIN_DISP_RESET = 22   # shared across all three displays

PIN_D1_CS, PIN_D1_DC = 5, 6
PIN_D2_CS, PIN_D2_DC = 14, 15
PIN_D3_CS, PIN_D3_DC = 20, 21

DISPLAY_WIDTH  = 240
DISPLAY_HEIGHT = 320

# ── Shared reset pulse ────────────────────────────────────────────────────────
# Pulse RST once for all three displays, then construct each ST7789 with
# reset=None so their drivers don't re-pulse the shared line.
_rst = machine.Pin(PIN_DISP_RESET, machine.Pin.OUT)
_rst.value(1); time.sleep_ms(1)
_rst.value(0); time.sleep_ms(1)
_rst.value(1); time.sleep_ms(150)

# ── SPI bus + displays ────────────────────────────────────────────────────────
spi0 = machine.SPI(
    0,
    baudrate=40_000_000,
    polarity=1,
    phase=0,
    sck=machine.Pin(PIN_DISP_SCK),
    mosi=machine.Pin(PIN_DISP_MOSI),
)


def _make_display(cs_pin, dc_pin):
    return st7789.ST7789(
        spi0,
        DISPLAY_WIDTH,
        DISPLAY_HEIGHT,
        reset=None,
        dc=machine.Pin(dc_pin, machine.Pin.OUT),
        cs=machine.Pin(cs_pin, machine.Pin.OUT),
        rotation=2,
    )


display1 = _make_display(PIN_D1_CS, PIN_D1_DC)   # Boost + Oil
display2 = _make_display(PIN_D2_CS, PIN_D2_DC)   # RPM   + AFR
display3 = _make_display(PIN_D3_CS, PIN_D3_DC)   # ECT   + IAT

for _d in (display1, display2, display3):
    _d.fill(st7789.BLACK)

# ── ADC inputs (unchanged) ────────────────────────────────────────────────────
boost_adc      = machine.ADC(machine.Pin(26))
thermistor_adc = machine.ADC(machine.Pin(28))

# ── CAN bus ───────────────────────────────────────────────────────────────────
can = CanBus(rate_kbps="500KBPS")

# ── Colour palette (RGB565) ───────────────────────────────────────────────────
def rgb(r, g, b):
    return st7789.color565(r, g, b)

PALETTE = [
    rgb(0xdd, 0xdd, 0xdd),  # 0  light grey
    rgb(0x00, 0xaa, 0xff),  # 1  azure
    rgb(0x00, 0xc8, 0xfa),  # 2  turquoise
    rgb(0x00, 0xe4, 0xfa),  # 3  cyan
    rgb(0x00, 0xfa, 0xe5),  # 4  aqua
    rgb(0x00, 0xff, 0x80),  # 5  spring green
    rgb(0x03, 0xff, 0x03),  # 6  green
    rgb(0x55, 0xff, 0x00),  # 7  bright green
    rgb(0xb7, 0xff, 0x00),  # 8  lime
    rgb(0xe1, 0xff, 0x00),  # 9  chartreuse
    rgb(0xff, 0xff, 0x00),  # 10 bright yellow
    rgb(0xff, 0xf7, 0x00),  # 11 yellow
    rgb(0xff, 0xd5, 0x00),  # 12 gold
    rgb(0xff, 0x95, 0x00),  # 13 orange
    rgb(0xff, 0x55, 0x00),  # 14 red-orange
    rgb(0xff, 0x03, 0x03),  # 15 red
    rgb(0xff, 0xff, 0xff),  # 16 white
]

FONT_MAJOR = font_56
FONT_MINOR = font_43
FONT_MINI  = font_20

# ── Slot geometry (shared across displays) ────────────────────────────────────
# Each display has a "top" slot (upper half) and a "bottom" slot (lower half).
# Two-arc gauges (boost-style) use the boost geometry; single-arc gauges
# (temperature-style) use the oil geometry. Origins differ by slot, geometry
# parameters are the same regardless of which display the gauge lives on.

TOP_ORIGIN = {'x': DISPLAY_WIDTH - 100, 'y': DISPLAY_HEIGHT // 2 - 12}
BOT_ORIGIN = {'x': DISPLAY_WIDTH - 100, 'y': DISPLAY_HEIGHT - 10}

# Single-arc readout: right-aligned integer, no minor decimal.
TOP_READOUT_SINGLE = {
    'x':       DISPLAY_WIDTH - 6,
    'y':       DISPLAY_HEIGHT // 2 - 9,
    'x_units': DISPLAY_WIDTH // 2,
    'y_units': DISPLAY_HEIGHT // 2 - 95,
}
BOT_READOUT_SINGLE = {
    'x':       DISPLAY_WIDTH - 6,
    'y':       DISPLAY_HEIGHT - 5,
    'x_units': DISPLAY_WIDTH // 2,
    'y_units': DISPLAY_HEIGHT - 95,
}

# Two-arc readout: leaves room for the minor decimal font.
TOP_READOUT_DECIMAL = {
    'x':       DISPLAY_WIDTH - 46,
    'y':       DISPLAY_HEIGHT // 2 - 9,
    'x_minor': DISPLAY_WIDTH - 48,
    'x_units': DISPLAY_WIDTH // 2,
    'y_units': DISPLAY_HEIGHT // 2 - 95,
}
BOT_READOUT_DECIMAL = {
    'x':       DISPLAY_WIDTH - 46,
    'y':       DISPLAY_HEIGHT - 5,
    'x_minor': DISPLAY_WIDTH - 48,
    'x_units': DISPLAY_WIDTH // 2,
    'y_units': DISPLAY_HEIGHT - 95,
}

SINGLE_ANGLES = {'start': 45, 'spread': 135}
TWO_ARC_ANGLES = {'start': 45, 'spread': 90, 'secondary_spread': 45}

# ── Bar configs (range + threshold colouring) ─────────────────────────────────
OIL_BAR = {
    'min': 120, 'max': 320,
    'thresholds': [(160, 6), (260, 12), (285, 15)],
    'default_color': 1,
}
RPM_BAR = {
    'min': 0, 'max': 7000,
    'thresholds': [(2000, 6), (4500, 11), (6000, 13), (6800, 15)],
    'default_color': 1,
}
ECT_BAR = {
    'min': 120, 'max': 250,
    'thresholds': [(160, 6), (210, 12), (225, 15)],
    'default_color': 1,
}
IAT_BAR = {
    'min': 0, 'max': 180,
    'thresholds': [(60, 6), (110, 11), (140, 15)],
    'default_color': 1,
}

# ── Gauge instances ───────────────────────────────────────────────────────────
boost_g = Gauge(
    display=display1, palette=PALETTE,
    gauge_type='boost', gauge_text={'description': 'BOOST', 'units': 'PSI'},
    origin=TOP_ORIGIN, radius=135, arc_width=32,
    angles=TWO_ARC_ANGLES,
    primary_segments=10, primary_color_index=1,
    secondary=True, secondary_segments=5, secondary_color_index=15,
    readout_pos=TOP_READOUT_DECIMAL,
    font_major=FONT_MAJOR, font_minor=FONT_MINOR, font_mini=FONT_MINI,
)

oil_g = Gauge(
    display=display1, palette=PALETTE,
    gauge_type='bar', gauge_text={'description': 'OILTMP', 'units': '°F'},
    origin=BOT_ORIGIN, radius=135, arc_width=32,
    angles=SINGLE_ANGLES,
    primary_segments=15, primary_color_index=1,
    readout_pos=BOT_READOUT_SINGLE,
    font_major=FONT_MAJOR, font_mini=FONT_MINI,
    bar_config=OIL_BAR,
)

rpm_g = Gauge(
    display=display2, palette=PALETTE,
    gauge_type='rpm', gauge_text={'description': 'RPM', 'units': 'RPM'},
    origin=TOP_ORIGIN, radius=135, arc_width=32,
    angles=SINGLE_ANGLES,
    primary_segments=14, primary_color_index=1,
    readout_pos=TOP_READOUT_SINGLE,
    font_major=FONT_MAJOR, font_mini=FONT_MINI,
    bar_config=RPM_BAR,
)

afr_g = Gauge(
    display=display2, palette=PALETTE,
    gauge_type='afr', gauge_text={'description': 'AFR', 'units': 'AFR'},
    origin=BOT_ORIGIN, radius=135, arc_width=32,
    angles=TWO_ARC_ANGLES,
    primary_segments=5, primary_color_index=11,
    secondary=True, secondary_segments=5, secondary_color_index=13,
    readout_pos=BOT_READOUT_DECIMAL,
    font_major=FONT_MAJOR, font_minor=FONT_MINOR, font_mini=FONT_MINI,
)

ect_g = Gauge(
    display=display3, palette=PALETTE,
    gauge_type='bar', gauge_text={'description': 'COOLNT', 'units': '°F'},
    origin=TOP_ORIGIN, radius=135, arc_width=32,
    angles=SINGLE_ANGLES,
    primary_segments=13, primary_color_index=1,
    readout_pos=TOP_READOUT_SINGLE,
    font_major=FONT_MAJOR, font_mini=FONT_MINI,
    bar_config=ECT_BAR,
)

iat_g = Gauge(
    display=display3, palette=PALETTE,
    gauge_type='bar', gauge_text={'description': 'INTAKE', 'units': '°F'},
    origin=BOT_ORIGIN, radius=135, arc_width=32,
    angles=SINGLE_ANGLES,
    primary_segments=15, primary_color_index=1,
    readout_pos=BOT_READOUT_SINGLE,
    font_major=FONT_MAJOR, font_mini=FONT_MINI,
    bar_config=IAT_BAR,
)

# ── Update loop ───────────────────────────────────────────────────────────────
options = {'units': 'f', 'demo': False}

while True:
    can.poll()

    boost_g.update(boost_adc.read_u16(), options)
    oil_g.update(Temperature.lookup(thermistor_adc.read_u16(), options['units']), options)
    rpm_g.update(can.latest['RPM'], options)
    afr_g.update(can.latest['AFR'], options)
    ect_g.update(can.latest['ECT'], options)
    iat_g.update(can.latest['IAT'], options)
