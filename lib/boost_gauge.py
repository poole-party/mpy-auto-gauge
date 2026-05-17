BOOST_OFFSET = 13.88
MAX_BOOST    = 10
MAX_VACUUM   = 15


def update(gauge, value, options):
    r = gauge.renderer

    # Demo mode: sweep 0–25 then repeat, mapped to -15..+10 PSI
    if options.get('demo'):
        if not hasattr(gauge, '_test_value'):
            gauge._test_value = 0
        mdp_next = (gauge._test_value - 150) / 10
        gauge._test_value = (gauge._test_value + 4) % 251
    else:
        mdp_next = value / 1000 - BOOST_OFFSET

    if gauge._mdp_current is None:
        gauge._mdp_current = mdp_next

    # Numeric readout
    parts = f'{mdp_next:.1f}'.split('.')
    r.draw_readout(parts[0], '.' + parts[-1])

    mdp_cur = gauge._mdp_current
    lvl_cur = gauge._bar_level
    n_pri   = gauge.primary_segments
    n_sec   = gauge.secondary_segments

    # Positive → boost arc; negative → vacuum arc
    if mdp_cur >= 0 and mdp_next >= 0:
        # Both positive: adjust boost bar
        lvl_next = min(int(mdp_next / (MAX_BOOST / (n_pri - 1))), n_pri - 1)
        if lvl_next > lvl_cur or (not r.primary_visible[0] and mdp_next >= 0.1):
            for i in range(lvl_cur, lvl_next + 1):
                r.set_primary_segment(i, True)
        elif lvl_next < lvl_cur:
            for i in range(lvl_cur, lvl_next, -1):
                r.set_primary_segment(i, False)
        gauge._bar_level = lvl_next

    elif mdp_cur < 0 and mdp_next < 0:
        # Both negative: adjust vacuum bar
        lvl_next = min(int(abs(mdp_next) / (MAX_VACUUM / (n_sec - 1))), n_sec - 1)
        if lvl_next > lvl_cur or (not r.secondary_visible[0] and mdp_next <= -0.1):
            for i in range(lvl_cur, lvl_next + 1):
                r.set_secondary_segment(i, True)
        elif lvl_next < lvl_cur:
            for i in range(lvl_cur, lvl_next, -1):
                r.set_secondary_segment(i, False)
        gauge._bar_level = lvl_next

    elif mdp_cur >= 0 and mdp_next < 0:
        # Boost → vacuum transition
        lvl_next = min(int(abs(mdp_next) / (MAX_VACUUM / (n_sec - 1))), n_sec - 1)
        for i in range(lvl_cur, -1, -1):
            r.set_primary_segment(i, False)
        for i in range(lvl_next + 1):
            r.set_secondary_segment(i, True)
        gauge._bar_level = lvl_next

    else:
        # Vacuum → boost transition
        lvl_next = min(int(mdp_next / (MAX_BOOST / (n_pri - 1))), n_pri - 1)
        for i in range(lvl_cur, -1, -1):
            r.set_secondary_segment(i, False)
        for i in range(lvl_next + 1):
            r.set_primary_segment(i, True)
        gauge._bar_level = lvl_next

    gauge._mdp_current = mdp_next
