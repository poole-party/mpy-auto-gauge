"""
digital_auto_gauge_st7789 — MicroPython port
Target: Raspberry Pi Pico with an ST7789 240x320 display.

Required files — copy these to your Pico:
  lib/st7789py.py        from https://github.com/russhughes/st7789py_mpy
  fonts/vga2_16x32.py    )
  fonts/vga1_16x32.py    ) from https://github.com/russhughes/st7789py_mpy/tree/master/fonts/bitmap
  fonts/vga2_8x8.py      )

Pin mapping (matches original CircuitPython project):
  SPI SCK   -> GP10
  SPI MOSI  -> GP11
  TFT CS    -> GP13
  TFT DC    -> GP12
  TFT RST   -> GP9
  Boost ADC -> GP26 / ADC0  (was board.A0)
  Therm ADC -> GP28 / ADC2  (was board.A2)
"""

import machine
import time
import st7789py as st7789
from lib.gauge import Gauge, PALETTE

# ---------------------------------------------------------------------------
# SPI & display
# ---------------------------------------------------------------------------
spi = machine.SPI(
    1,
    baudrate=24_000_000,
    polarity=0,
    phase=0,
    sck=machine.Pin(10),
    mosi=machine.Pin(11),
    miso=machine.Pin(8),   # not used by display but required by some builds
)

DISPLAY_WIDTH  = 240
DISPLAY_HEIGHT = 320

display = st7789.ST7789(
    spi,
    DISPLAY_WIDTH,
    DISPLAY_HEIGHT,
    reset=machine.Pin(9,  machine.Pin.OUT),
    dc=machine.Pin(12, machine.Pin.OUT),
    cs=machine.Pin(13, machine.Pin.OUT),
    rotation=0,            # 180 degrees — matches original display.rotation = 180
)

display.fill(0x0000)       # clear to black

# ---------------------------------------------------------------------------
# ADC inputs
# MicroPython ADC.read_u16() returns 0-65535, same range as CircuitPython
# AnalogIn.value, so all lookup/scaling logic in gauge.py is unchanged.
# ---------------------------------------------------------------------------
boost_raw  = machine.ADC(machine.Pin(26))  # A0 -> GP26
thermistor = machine.ADC(machine.Pin(28))  # A2 -> GP28

# ---------------------------------------------------------------------------
# Gauges  (parameters mirror the original code.py exactly)
# ---------------------------------------------------------------------------
active_gauges = []

# -- Boost gauge -------------------------------------------------------------
active_gauges.append(Gauge(
    display=display,
    bg_color=0x0000,
    gauge_type='boost',
    gauge_text={'description': 'BOOST', 'units': 'PSI'},
    origin={'x': DISPLAY_WIDTH - 100, 'y': DISPLAY_HEIGHT / 2 - 12},
    radius=135,
    arc_width=30,
    angles={'start': 45, 'spread': 90, 'secondary_spread': 45},
    primary_segments=10,
    primary_color_index=1,
    palette=PALETTE,
    readout_pos={
        'x':       DISPLAY_WIDTH - 60,
        'y':       DISPLAY_HEIGHT / 2 - 9,
        'x-minor': DISPLAY_WIDTH - 64,
        'x-units': DISPLAY_WIDTH / 2 + 15,
        'y-units': DISPLAY_HEIGHT / 2 - 80,
    },
    secondary=True,
    secondary_segments=5,
    secondary_color_index=15,
))

# -- Oil temperature gauge ---------------------------------------------------
active_gauges.append(Gauge(
    display=display,
    bg_color=0x0000,
    gauge_type='temperature',
    gauge_text={'description': 'OILTMP', 'units': 'F'},
    origin={'x': DISPLAY_WIDTH - 100, 'y': DISPLAY_HEIGHT - 10},
    radius=135,
    arc_width=30,
    angles={'start': 45, 'spread': 135},
    primary_segments=15,
    primary_color_index=1,
    palette=PALETTE,
    readout_pos={
        'x':       DISPLAY_WIDTH - 6,
        'y':       DISPLAY_HEIGHT - 10,
        'x-units': DISPLAY_WIDTH / 2 + 15,
        'y-units': DISPLAY_HEIGHT - 80,
    },
))

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
options = {}
options['units'] = 'f'
options['demo'] = False
options['demo'] = True

while True:
    boost_value      = boost_raw.read_u16()
    thermistor_value = thermistor.read_u16()

    active_gauges[0].update_gauge(value=boost_value,      options=options)
    active_gauges[1].update_gauge(value=thermistor_value, options=options)

    if options['demo'] == True:
        print("Boost Raw Value:", boost_value)
        time.sleep(0.5)
