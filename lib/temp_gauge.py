def update(gauge, value, options):
    """Update a bar-style gauge driven by a pre-converted scalar value.

    Reads `gauge.bar_config`:
        min:            scale minimum
        max:            scale maximum
        thresholds:     list of (lower_bound, color_idx), ascending. The
                        highest bound that the segment's threshold meets
                        wins. Segments below the lowest bound use
                        `default_color` (or the gauge's primary colour).
        default_color:  optional fallback colour index.

    `value` is the live measurement (already in display units). Demo mode
    ignores it and sweeps `min..max`.
    """
    r   = gauge.renderer
    cfg = gauge.bar_config
    min_temp      = cfg['min']
    max_temp      = cfg['max']
    thresholds    = cfg.get('thresholds', ())
    default_color = cfg.get('default_color', gauge.primary_color_index)

    if options.get('demo'):
        if not hasattr(gauge, '_test_value'):
            gauge._test_value = min_temp
        gauge._test_value += 2
        if gauge._test_value > max_temp:
            gauge._test_value = min_temp
        temp = gauge._test_value
    else:
        temp = value

    display_temp = '- -'
    lvl_next = -1

    if isinstance(temp, (int, float)) and temp > 0:
        display_temp = int(temp)
        raw_level = int((display_temp - min_temp) /
                        ((max_temp - min_temp) / (gauge.primary_segments - 1)))
        lvl_next = max(0, min(raw_level, gauge.primary_segments - 1))

    r.draw_readout(str(display_temp))

    lvl_cur = gauge._temp_level
    n       = gauge.primary_segments

    if not isinstance(display_temp, int) or temp - min_temp < 0:
        # Below operating range — show only the first (cold) segment
        for i in range(n):
            r.set_primary_segment(i, i == 0)
        lvl_next = -1

    elif lvl_next >= lvl_cur:
        for i in range(max(lvl_cur + 1, 0), lvl_next + 1):
            threshold = min_temp + (max_temp - min_temp) / (n - 1) * i
            color_idx = default_color
            for lower, c in thresholds:
                if threshold >= lower:
                    color_idx = c
            r.set_primary_segment(i, True, color_idx)

    else:
        for i in range(lvl_cur, lvl_next, -1):
            r.set_primary_segment(i, False)

    gauge._temp_level = lvl_next
