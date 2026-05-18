AFR_STOICH   = 14.7
AFR_LEAN_MAX = 18.0   # primary (lean) arc spans 14.7 → 18.0
AFR_RICH_MIN = 12.0   # secondary (rich) arc spans 14.7 → 12.0

# Per-segment palette indices, ordered from closest-to-stoich → most extreme.
# Lean is dangerous under load (detonation), so yellow → red.
# Rich is mostly tolerable on a stock NA engine, so amber → orange.
LEAN_COLORS = [11, 12, 13, 14, 15]
RICH_COLORS = [11, 12, 13, 13, 14]


def update(gauge, value, options):
    r = gauge.renderer

    if options.get('demo'):
        if not hasattr(gauge, '_test_value'):
            gauge._test_value = AFR_RICH_MIN
            gauge._afr_dir = 0.1
        gauge._test_value += gauge._afr_dir
        if gauge._test_value >= AFR_LEAN_MAX:
            gauge._test_value = AFR_LEAN_MAX
            gauge._afr_dir = -gauge._afr_dir
        elif gauge._test_value <= AFR_RICH_MIN:
            gauge._test_value = AFR_RICH_MIN
            gauge._afr_dir = -gauge._afr_dir
        afr = gauge._test_value
    else:
        afr = value

    if not isinstance(afr, (int, float)) or afr <= 0:
        r.draw_readout('- -', '.-')
        return

    d_next = afr - AFR_STOICH
    if gauge._mdp_current is None:
        gauge._mdp_current = d_next

    parts = f'{afr:.1f}'.split('.')
    r.draw_readout(parts[0], '.' + parts[-1])

    d_cur   = gauge._mdp_current
    lvl_cur = gauge._bar_level
    n_pri   = gauge.primary_segments
    n_sec   = gauge.secondary_segments

    pri_range = AFR_LEAN_MAX - AFR_STOICH
    sec_range = AFR_STOICH   - AFR_RICH_MIN

    if d_cur >= 0 and d_next >= 0:
        lvl_next = min(int(d_next / (pri_range / (n_pri - 1))), n_pri - 1)
        if lvl_next > lvl_cur or (not r.primary_visible[0] and d_next >= 0.05):
            for i in range(lvl_cur, lvl_next + 1):
                r.set_primary_segment(i, True, LEAN_COLORS[i])
        elif lvl_next < lvl_cur:
            for i in range(lvl_cur, lvl_next, -1):
                r.set_primary_segment(i, False)
        gauge._bar_level = lvl_next

    elif d_cur < 0 and d_next < 0:
        lvl_next = min(int(abs(d_next) / (sec_range / (n_sec - 1))), n_sec - 1)
        if lvl_next > lvl_cur or (not r.secondary_visible[0] and d_next <= -0.05):
            for i in range(lvl_cur, lvl_next + 1):
                r.set_secondary_segment(i, True, RICH_COLORS[i])
        elif lvl_next < lvl_cur:
            for i in range(lvl_cur, lvl_next, -1):
                r.set_secondary_segment(i, False)
        gauge._bar_level = lvl_next

    elif d_cur >= 0 and d_next < 0:
        lvl_next = min(int(abs(d_next) / (sec_range / (n_sec - 1))), n_sec - 1)
        for i in range(lvl_cur, -1, -1):
            r.set_primary_segment(i, False)
        for i in range(lvl_next + 1):
            r.set_secondary_segment(i, True, RICH_COLORS[i])
        gauge._bar_level = lvl_next

    else:
        lvl_next = min(int(d_next / (pri_range / (n_pri - 1))), n_pri - 1)
        for i in range(lvl_cur, -1, -1):
            r.set_secondary_segment(i, False)
        for i in range(lvl_next + 1):
            r.set_primary_segment(i, True, LEAN_COLORS[i])
        gauge._bar_level = lvl_next

    gauge._mdp_current = d_next
