import temp_gauge

# RPM uses the same bar/threshold logic as temperatures — same dispatch
# target, separate gauge_type so RPM-specific behaviour (shift light,
# rev-limit flash) can later diverge without touching the temp path.
update = temp_gauge.update
