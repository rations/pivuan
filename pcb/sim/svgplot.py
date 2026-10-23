"""Plain SVG line plots, so the simulations need nothing beyond Python and ngspice."""

import math

COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf", "#8c564b", "#7f7f7f"]
W, H = 760, 420
LEFT, RIGHT, TOP, BOTTOM = 70, 20, 40, 50


def _ticks(lo, hi, log):
    if log:
        ticks, d = [], 10 ** math.floor(math.log10(lo))
        while d <= hi * 1.0001:
            for m in (1, 2, 5):
                if lo * 0.9999 <= d * m <= hi * 1.0001:
                    ticks.append(d * m)
            d *= 10
        return ticks
    span = hi - lo
    step = 10 ** math.floor(math.log10(span / 5))
    for m in (1, 2, 5, 10):
        if span / (step * m) <= 8:
            step *= m
            break
    t = math.ceil(lo / step) * step
    ticks = []
    while t <= hi + step * 1e-6:
        ticks.append(round(t, 12))
        t += step
    return ticks


def _fmt(v):
    if v == 0:
        return "0"
    for div, s in ((1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "µ"), (1e-9, "n")):
        if abs(v) >= div:
            x = v / div
            return (f"{x:.0f}" if x == int(x) else f"{x:g}") + s
    return f"{v:g}"


def _thin(pts):
    """Keep the first, lowest, highest and last point in each half-pixel column, in order: the line
    looks the same, and a transient of a million points stays a small file."""
    out, col = [], []
    for p in pts:
        if col and round(p[0] * 2) != round(col[0][0] * 2):
            out += _column(col)
            col = []
        col.append(p)
    return out + _column(col)


def _column(col):
    if len(col) <= 4:
        return col
    keep = {0, len(col) - 1, min(range(len(col)), key=lambda i: col[i][1]),
            max(range(len(col)), key=lambda i: col[i][1])}
    return [col[i] for i in sorted(keep)]


def plot(path, title, series, xlabel, ylabel, xlog=False, ylog=False, xlim=None, ylim=None, marks=()):
    """series: [(label, xs, ys)]; marks: [(label, y)] horizontal limit lines."""
    xs_all = [x for _, xs, _ in series for x in xs]
    ys_all = [y for _, _, ys in series for y in ys] + [y for _, y in marks]
    x0, x1 = xlim or (min(xs_all), max(xs_all))
    y0, y1 = ylim or (min(ys_all), max(ys_all))
    if y0 == y1:
        y0, y1 = y0 - 1, y1 + 1
    if not ylim and not ylog:
        pad = (y1 - y0) * 0.05
        y0, y1 = y0 - pad, y1 + pad
    pw, ph = W - LEFT - RIGHT, H - TOP - BOTTOM

    def sx(x):
        f = (math.log10(x) - math.log10(x0)) / (math.log10(x1) - math.log10(x0)) if xlog else (x - x0) / (x1 - x0)
        return LEFT + f * pw

    def sy(y):
        f = (math.log10(y) - math.log10(y0)) / (math.log10(y1) - math.log10(y0)) if ylog else (y - y0) / (y1 - y0)
        return TOP + (1 - f) * ph

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="12">',
           f'<rect width="{W}" height="{H}" fill="white"/>',
           f'<text x="{W / 2}" y="22" text-anchor="middle" font-size="15">{title}</text>']
    for t in _ticks(x0, x1, xlog):
        out.append(f'<line x1="{sx(t):.1f}" y1="{TOP}" x2="{sx(t):.1f}" y2="{TOP + ph}" stroke="#ddd"/>')
        out.append(f'<text x="{sx(t):.1f}" y="{TOP + ph + 16}" text-anchor="middle">{_fmt(t)}</text>')
    for t in _ticks(y0, y1, ylog):
        out.append(f'<line x1="{LEFT}" y1="{sy(t):.1f}" x2="{LEFT + pw}" y2="{sy(t):.1f}" stroke="#ddd"/>')
        out.append(f'<text x="{LEFT - 6}" y="{sy(t) + 4:.1f}" text-anchor="end">{_fmt(t)}</text>')
    out.append(f'<rect x="{LEFT}" y="{TOP}" width="{pw}" height="{ph}" fill="none" stroke="#444"/>')
    out.append(f'<text x="{LEFT + pw / 2}" y="{H - 12}" text-anchor="middle">{xlabel}</text>')
    out.append(f'<text transform="translate(16 {TOP + ph / 2}) rotate(-90)" text-anchor="middle">{ylabel}</text>')
    out.append(f'<clipPath id="c"><rect x="{LEFT}" y="{TOP}" width="{pw}" height="{ph}"/></clipPath>')
    for label, y in marks:
        out.append(f'<line x1="{LEFT}" y1="{sy(y):.1f}" x2="{LEFT + pw}" y2="{sy(y):.1f}" stroke="#888" '
                   f'stroke-dasharray="5 4"/>')
        out.append(f'<text x="{LEFT + pw - 4}" y="{sy(y) - 4:.1f}" text-anchor="end" fill="#666">{label}</text>')
    for i, (label, xs, ys) in enumerate(series):
        c = COLORS[i % len(COLORS)]
        pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in _thin(
            [(sx(x), sy(y)) for x, y in zip(xs, ys) if (not xlog or x > 0) and (not ylog or y > 0)]))
        out.append(f'<polyline clip-path="url(#c)" fill="none" stroke="{c}" stroke-width="1.6" points="{pts}"/>')
        out.append(f'<rect x="{LEFT + 10}" y="{TOP + 8 + i * 17}" width="14" height="3" fill="{c}"/>')
        out.append(f'<text x="{LEFT + 30}" y="{TOP + 13 + i * 17}">{label}</text>')
    out.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
