"""Render the GitHub contribution calendar as an animated, themed SVG card.

Usage:
  python scripts/contributions.py USERNAME [OUTPUT]
  python scripts/contributions.py USERNAME OUTPUT --counts START_DATE COMMA_SEPARATED_COUNTS   (offline)

Reads the public calendar at https://github.com/users/USERNAME/contributions and writes a
card that follows the viewer's light/dark setting. The cells fill in week by week, then a
glass lens moves between three stops: busiest day, today and longest streak.
Viewers with reduced motion get the finished grid with no animation.
"""
import datetime as dt
import re
import sys
import urllib.request

LIGHT = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
DARK = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

W, P = 840, 6                 # image width, outer inset (matches the other cards)
CELL, GAP = 11, 3
STEP = CELL + GAP
TOP = 72
HOLD, MOVE, START = 3.4, 0.6, 2.0   # seconds per stop, glide time, delay before the lens appears


def fetch(user):
    req = urllib.request.Request(f"https://github.com/users/{user}/contributions",
                                 headers={"User-Agent": "profile-contributions-card"})
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    tips = {}
    for m in re.finditer(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>\s*([^<]*?)\s*</tool-tip>', page):
        n = re.match(r"(\d[\d,]*) contribution", m.group(2))
        tips[m.group(1)] = int(n.group(1).replace(",", "")) if n else 0
    days = {}
    for tag in re.findall(r"<td[^>]*ContributionCalendar-day[^>]*>", page):
        date = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag)
        level = re.search(r'data-level="(\d)"', tag)
        cid = re.search(r'\bid="([^"]+)"', tag)
        if date and level:
            days[dt.date.fromisoformat(date.group(1))] = (int(level.group(1)), tips.get(cid.group(1), 0) if cid else 0)
    if len(days) < 300:
        raise SystemExit(f"Only parsed {len(days)} days; GitHub markup may have changed.")
    if not tips:
        raise SystemExit("Found no day counts; GitHub markup may have changed.")
    return days


def level_for(n):
    return 0 if n == 0 else 1 if n <= 2 else 2 if n <= 6 else 3 if n <= 12 else 4


def fmt(d):
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def plural(n, word):
    return f"{n:,} {word}{'' if n == 1 else 's'}"


def render(days):
    start = min(days)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)      # back to Sunday
    end = max(days)
    weeks = (end - start).days // 7 + 1
    left = P + 20 + 30 + max(0, (W - 2 * P - 40 - 30 - (weeks * STEP - GAP)) // 2)
    h = TOP + 7 * STEP - GAP + 46

    def xy(day):
        off = (day - start).days
        return left + (off // 7) * STEP, TOP + (off % 7) * STEP

    def lens_box(d0, d1, pad=3):
        """Up to three rectangles whose union covers days d0..d1 (one per column run)."""
        o0, o1 = (d0 - start).days, (d1 - start).days
        c0, c1, r0, r1 = o0 // 7, o1 // 7, o0 % 7, o1 % 7
        if c0 == c1:
            runs = [(c0, r0, c0, r1)]
        else:
            runs = [(c0, r0, c0, 6)] + ([(c0 + 1, 0, c1 - 1, 6)] if c1 - c0 > 1 else []) + [(c1, 0, c1, r1)]
        rects = [(left + a * STEP - pad, TOP + b * STEP - pad, (c - a) * STEP + CELL + 2 * pad, (d - b) * STEP + CELL + 2 * pad)
                 for a, b, c, d in runs]
        while len(rects) < 3:
            rects.append(rects[-1])
        return rects

    counts = {d: v[1] for d, v in days.items()}
    total = sum(counts.values())
    busiest = max(sorted(counts), key=lambda d: counts[d])
    today = end
    best_len, best_end, run = 0, None, 0
    for d in sorted(counts):
        run = run + 1 if counts[d] > 0 else 0
        if run > best_len:
            best_len, best_end = run, d
    stops = [(busiest, busiest, f"Busiest day · {plural(counts[busiest], 'contribution')} on {fmt(busiest)}"),
             (today, today, f"Today · {plural(counts[today], 'contribution')}")]
    if best_len:
        first = best_end - dt.timedelta(days=best_len - 1)
        stops.append((first, best_end, f"Longest streak · {plural(best_len, 'day')}, {fmt(first)} to {fmt(best_end)}"))
    n = len(stops)
    T = n * (HOLD + MOVE)
    shapes = [lens_box(a, b) for a, b, _ in stops]

    key_times, order = [], []
    for i in range(n):
        key_times += [i * (HOLD + MOVE) / T, (i * (HOLD + MOVE) + HOLD) / T]
        order += [i, i]
    key_times.append(1)
    order.append(0)
    kt = ";".join(f"{v:.4f}" for v in key_times)
    ks = ";".join("0 0 1 1" if j % 2 == 0 else ".4 0 .2 1" for j in range(len(key_times) - 1))

    lens = []
    for k in range(3):
        x0, y0, w0, h0 = shapes[0][k]
        anims = "".join(
            f'<animate attributeName="{a}" values="{";".join(str(shapes[p][k][j]) for p in order)}" keyTimes="{kt}" '
            f'calcMode="spline" keySplines="{ks}" dur="{T:.1f}s" begin="{START}s" repeatCount="indefinite"/>'
            for j, a in enumerate(("x", "y", "width", "height")))
        lens.append(f'<rect rx="4" x="{x0}" y="{y0}" width="{w0}" height="{h0}">{anims}</rect>')

    share, fade = HOLD / T * 100, 0.35 / T * 100
    css = (
        "text{font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",\"Noto Sans\",Helvetica,Arial,sans-serif}"
        ".bg{fill:#ffffff;stroke:#d0d7de}.t{fill:#1f2328}.m{fill:#59636e}"
        ".lab{font-size:11px;font-weight:600;letter-spacing:1.6px}"
        + "".join(f".l{i}{{fill:{c}}}" for i, c in enumerate(LIGHT))
        + ".gf{flood-color:#ffffff;flood-opacity:.42}.gr{flood-color:#0969da;flood-opacity:.55}"
          ".gh{flood-color:#ffffff;flood-opacity:.9}.gs{flood-color:#000000;flood-opacity:.16}"
        + "@media (prefers-color-scheme:dark){.bg{fill:#0d1117;stroke:#30363d}.t{fill:#e6edf3}.m{fill:#9198a1}"
        + "".join(f".l{i}{{fill:{c}}}" for i, c in enumerate(DARK))
        + ".gf{flood-opacity:.14}.gr{flood-color:#ffffff}.gh{flood-opacity:.35}.gs{flood-opacity:.45}}"
        ".c{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .35s ease-out forwards}"
        "@keyframes pop{from{opacity:0;transform:scale(.4)}to{opacity:1;transform:scale(1)}}"
        f".s{{opacity:0;animation:s {T:.1f}s linear infinite}}"
        f"@keyframes s{{0%{{opacity:0}}{fade:.2f}%,{share - fade:.2f}%{{opacity:1}}{share:.2f}%,100%{{opacity:0}}}}"
        ".lens{opacity:0;animation:lin .6s ease-out 1.6s forwards}@keyframes lin{to{opacity:1}}"
        ".still{display:none}"
        "@media (prefers-reduced-motion:reduce){.c{animation:none;opacity:1}.s,.lens{display:none}.still{display:inline}}"
    )
    glass = (
        '<filter id="glass" x="-30%" y="-60%" width="160%" height="220%" color-interpolation-filters="sRGB">'
        '<feGaussianBlur in="SourceGraphic" stdDeviation="1.6" result="b"/>'
        '<feColorMatrix in="b" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 30 -14" result="shape"/>'
        '<feGaussianBlur in="shape" stdDeviation="2.2" result="sb"/><feOffset in="sb" dy="1.6" result="so"/>'
        '<feFlood class="gs"/><feComposite in2="so" operator="in" result="shadow"/>'
        '<feFlood class="gf"/><feComposite in2="shape" operator="in" result="fill"/>'
        '<feMorphology in="shape" operator="erode" radius="1.1" result="er"/>'
        '<feComposite in="shape" in2="er" operator="out" result="rim"/>'
        '<feFlood class="gr"/><feComposite in2="rim" operator="in" result="rimc"/>'
        '<feOffset in="er" dy="1.2" result="eo"/><feComposite in="er" in2="eo" operator="out" result="hl"/>'
        '<feFlood class="gh"/><feComposite in2="hl" operator="in" result="hlc"/>'
        '<feMerge><feMergeNode in="shadow"/><feMergeNode in="fill"/><feMergeNode in="rimc"/><feMergeNode in="hlc"/></feMerge>'
        '</filter>'
    )

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" '
           f'aria-label="GitHub contributions: {total:,} in the last year"><title>GitHub contributions</title>'
           f'<defs>{glass}</defs><style>{css}</style>',
           f'<rect class="bg" x="{P + .5}" y=".5" width="{W - 2 * P - 1}" height="{h - P - 1}" rx="12"/>',
           f'<text x="{P + 20}" y="34" class="m lab">GITHUB CONTRIBUTIONS</text>',
           f'<text class="m still" x="{W - P - 20}" y="34" font-size="12" text-anchor="end">{total:,} contributions in the last year</text>']
    for i, (_, _, label) in enumerate(stops):
        out.append(f'<text class="t s" style="animation-delay:{START + i * (HOLD + MOVE):.2f}s" x="{W - P - 20}" y="34" '
                   f'font-size="12" font-weight="500" text-anchor="end">{label}</text>')
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="{P + 20}" y="{TOP + row * STEP + 9}" class="m" font-size="10">{name}</text>')
    last_month = None
    for w in range(weeks):
        week_start = start + dt.timedelta(days=7 * w)
        if (w == 0 or (week_start.month != last_month and week_start.day <= 7)) and w < weeks - 2:
            out.append(f'<text x="{left + w * STEP}" y="{TOP - 9}" class="m" font-size="10">{MONTHS[week_start.month - 1]}</text>')
        last_month = week_start.month
        for d in range(7):
            day = week_start + dt.timedelta(days=d)
            if day in days:
                x, y = xy(day)
                out.append(f'<rect class="l{days[day][0]} c" style="animation-delay:{w * .02:.2f}s" x="{x}" y="{y}" '
                           f'width="{CELL}" height="{CELL}" rx="2.5"><title>{plural(counts[day], "contribution")} on {fmt(day)}</title></rect>')
    out.append(f'<g class="lens" filter="url(#glass)" fill="#000">{"".join(lens)}</g>')
    lx = W - P - 20 - (5 * STEP - GAP) - 34
    ly = TOP + 7 * STEP + 14
    out.append(f'<text x="{lx - 8}" y="{ly + 9}" class="m" font-size="10" text-anchor="end">Less</text>')
    for i in range(5):
        out.append(f'<rect class="l{i}" x="{lx + i * STEP}" y="{ly}" width="{CELL}" height="{CELL}" rx="2.5"/>')
    out.append(f'<text x="{lx + 5 * STEP + 5}" y="{ly + 9}" class="m" font-size="10">More</text>')
    out.append("</svg>")
    return "".join(out), stops, total


def main():
    user = sys.argv[1]
    dest = sys.argv[2] if len(sys.argv) > 2 else "assets/contributions.svg"
    if "--counts" in sys.argv:
        i = sys.argv.index("--counts")
        first = dt.date.fromisoformat(sys.argv[i + 1])
        days = {first + dt.timedelta(days=k): (level_for(int(c)), int(c)) for k, c in enumerate(sys.argv[i + 2].split(","))}
    else:
        days = fetch(user)
    svg, stops, total = render(days)
    with open(dest, "w") as f:
        f.write(svg)
    print(f"Wrote {dest}: {len(days)} days, {total} contributions")
    for _, _, label in stops:
        print("  stop:", label)


if __name__ == "__main__":
    main()
