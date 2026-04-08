import math
import machine
import st7789
import time
from gauge import Gauge

# ── SPI & display init ────────────────────────────────────────────────────────

SPI_ID      = 1
PIN_CLK     = 10
PIN_MOSI    = 11
PIN_CS      = 13
PIN_DC      = 12
PIN_RESET   = 9

DISPLAY_WIDTH  = 240
DISPLAY_HEIGHT = 320

spi = machine.SPI(
    SPI_ID,
    baudrate=40_000_000,
    polarity=1,
    phase=0,
    sck=machine.Pin(PIN_CLK),
    mosi=machine.Pin(PIN_MOSI),
)

display = st7789.ST7789(
    spi,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    reset=machine.Pin(PIN_RESET, machine.Pin.OUT),
    dc=machine.Pin(PIN_DC, machine.Pin.OUT),
    cs=machine.Pin(PIN_CS, machine.Pin.OUT),
    rotation=2,  # 180° — matches your original display.rotation = 180
)

display.fill(st7789.BLACK)

# ── ADC inputs ────────────────────────────────────────────────────────────────

boost_adc     = machine.ADC(machine.Pin(26))   # A0 → GP26
thermistor_adc = machine.ADC(machine.Pin(28))  # A2 → GP28

# ── Colour palette (RGB565) ───────────────────────────────────────────────────
# Converted from your 24-bit palette using st7789.color565(r, g, b).
# Index layout matches bar_palette from main.py exactly.

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

# ── Gauge definitions ─────────────────────────────────────────────────────────

# Font paths — adjust if your converted font files live elsewhere.
# See README for converting Saira .bdf → russhughes font format.
FONT_MAJOR = "fonts/saira_bold_italic_56"
FONT_MINOR = "fonts/saira_bold_italic_43"
FONT_MINI  = "fonts/saira_semibold_20"

active_gauges = []

# Boost gauge
active_gauges.append(Gauge(
    display       = display,
    palette       = PALETTE,
    gauge_type    = 'boost',
    gauge_text    = {'description': 'BOOST', 'units': 'PSI'},
    origin        = {'x': DISPLAY_WIDTH - 100, 'y': DISPLAY_HEIGHT // 2 - 12},
    radius        = 135,
    arc_width     = 32,
    angles        = {'start': 45, 'spread': 90, 'secondary_spread': 45},
    primary_segments       = 6,
    primary_color_index    = 1,
    secondary              = True,
    secondary_segments     = 3,
    secondary_color_index  = 15,
    readout_pos   = {
        'x': DISPLAY_WIDTH - 60,
        'y': DISPLAY_HEIGHT // 2 - 9,
        'x_minor': DISPLAY_WIDTH - 64,
        'x_units': DISPLAY_WIDTH // 2 + 15,
        'y_units': DISPLAY_HEIGHT // 2 - 80,
    },
    font_major = FONT_MAJOR,
    font_minor = FONT_MINOR,
    font_mini  = FONT_MINI,
))

# Oil temp gauge
active_gauges.append(Gauge(
    display       = display,
    palette       = PALETTE,
    gauge_type    = 'temperature',
    gauge_text    = {'description': 'OILTMP', 'units': '°F'},
    origin        = {'x': DISPLAY_WIDTH - 100, 'y': DISPLAY_HEIGHT - 10},
    radius        = 135,
    arc_width     = 32,
    angles        = {'start': 45, 'spread': 135},
    primary_segments      = 10,
    primary_color_index   = 1,
    readout_pos   = {
        'x': DISPLAY_WIDTH - 6,
        'y': DISPLAY_HEIGHT - 10,
        'x_units': DISPLAY_WIDTH // 2 + 15,
        'y_units': DISPLAY_HEIGHT - 80,
    },
    font_major = FONT_MAJOR,
    font_mini  = FONT_MINI,
))

# ── Update loop ───────────────────────────────────────────────────────────────

options = {'units': 'f', 'demo': True}

while True:
    active_gauges[0].update(boost_adc.read_u16(), options)
    active_gauges[1].update(thermistor_adc.read_u16(), options)
