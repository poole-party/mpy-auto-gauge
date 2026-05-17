from temperature import Temperature

MAX_TEMP            = 320
MIN_TEMP            = 120
DANGER_TEMP_START   = 285
CAUTION_TEMP_START  = 260
OP_TEMP_START       = 160


def update(gauge, value, options):
    if options.get('demo'):
        if not hasattr(gauge, '_test_value'):
            gauge._test_value = 0

        gauge._test_value = (gauge._test_value + 2) % MAX_TEMP
        temp = gauge._test_value

        if temp < MIN_TEMP:
            gauge._test_value = MIN_TEMP
            temp = gauge._test_value
    else:
        temp = Temperature.compute(value, options.get('units', 'f'))

    display_temp = '- -'
    lvl_next = -1

    if isinstance(temp, (int, float)) and temp > 0:
        display_temp = int(temp)
        raw_level = int((display_temp - MIN_TEMP) /
                        ((MAX_TEMP - MIN_TEMP) / (gauge.primary_segments - 1)))
        lvl_next = max(0, min(raw_level, gauge.primary_segments - 1))

    gauge.draw_readout(str(display_temp))

    lvl_cur = gauge._temp_level
    n       = gauge.primary_segments

    if not isinstance(display_temp, int) or temp - MIN_TEMP < 0:
        # Below operating range — show only the first (cold) segment
        for i in range(n):
            gauge.set_primary_segment(i, i == 0)
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
                color_idx = gauge.primary_color_index
            gauge.set_primary_segment(i, True, color_idx)

    else:
        for i in range(lvl_cur, lvl_next, -1):
            gauge.set_primary_segment(i, False)

    gauge._temp_level = lvl_next
