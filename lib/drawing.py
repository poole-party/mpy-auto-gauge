import math

GAP_RATIO = 0.6   # controls visual gap between arc segments


def fill_polygon(display, points, color):
    """Scanline fill for a convex polygon. Replaces russhughes filled polygon."""
    min_y = min(p[1] for p in points)
    max_y = max(p[1] for p in points)
    n = len(points)
    for y in range(min_y, max_y + 1):
        xs = []
        for i in range(n):
            x0, y0 = points[i]
            x1, y1 = points[(i + 1) % n]
            if y0 == y1:
                continue
            if min(y0, y1) <= y < max(y0, y1):
                xs.append(x0 + (y - y0) * (x1 - x0) // (y1 - y0))
        if len(xs) >= 2:
            xs.sort()
            display.hline(xs[0], y, xs[-1] - xs[0] + 1, color)


def draw_text(display, font, text, x, y, fg, bg):
    """Render text using a Peter Hinch font_to_py font module via blit_buffer."""
    if display.needs_swap:
        fg_hi, fg_lo = fg & 0xFF, fg >> 8
        bg_hi, bg_lo = bg & 0xFF, bg >> 8
    else:
        fg_hi, fg_lo = fg >> 8, fg & 0xFF
        bg_hi, bg_lo = bg >> 8, bg & 0xFF
    for ch in text:
        bitmap, height, width = font.get_ch(ch)
        bpr = (width - 1) // 8 + 1
        buf = bytearray(width * height * 2)
        for row in range(height):
            for col in range(width):
                bit = (bitmap[row * bpr + col // 8] >> (7 - col % 8)) & 1
                i = (row * width + col) * 2
                if bit:
                    buf[i] = fg_hi
                    buf[i + 1] = fg_lo
                else:
                    buf[i] = bg_hi
                    buf[i + 1] = bg_lo
        display.blit_buffer(bytes(buf), x, y, width, height)
        x += width


def segment_polygon(origin_x, origin_y, radius, arc_width, angle_start, segment_index,
                    segment_count, spread):
    """Return a list of 4 (x, y) tuples defining one arc segment polygon."""
    seg_width  = spread / segment_count
    seg_center = segment_index * seg_width + seg_width / 2
    reduced    = seg_width * GAP_RATIO
    points     = [None] * 4
    for j in range(2):
        alpha = math.radians((seg_center + (j - 0.5) * reduced) + angle_start)
        cos_a, sin_a = math.cos(alpha), math.sin(alpha)
        points[j]     = (origin_x + int(radius * cos_a),
                         origin_y - int(radius * sin_a))
        points[3 - j] = (origin_x + int((radius - arc_width) * cos_a),
                         origin_y - int((radius - arc_width) * sin_a))
    return points
