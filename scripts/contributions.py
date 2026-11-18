"""Render the GitHub contribution calendar as a themed SVG card.

Usage:
  python scripts/contributions.py USERNAME [OUTPUT]
  python scripts/contributions.py USERNAME OUTPUT --levels START_DATE LEVELS TOTAL   (offline)

Reads the public calendar at https://github.com/users/USERNAME/contributions and
writes a card that follows the viewer's light/dark setting.
"""
import datetime as dt
import html
import re
import sys
import urllib.request

LIGHT = ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"]
DARK = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch(user):
    req = urllib.request.Request(f"https://github.com/users/{user}/contributions",
                                 headers={"User-Agent": "profile-contributions-card"})
    page = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    days = {}
    for tag in re.findall(r"<td[^>]*ContributionCalendar-day[^>]*>", page):
        date = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag)
        level = re.search(r'data-level="(\d)"', tag)
        if date and level:
            days[dt.date.fromisoformat(date.group(1))] = int(level.group(1))
    m = re.search(r'id="js-contribution-activity-description"[^>]*>\s*([\d,]+)\s+contribution', page)
    total = int(m.group(1).replace(",", "")) if m else None
    if len(days) < 300:
        raise SystemExit(f"Only parsed {len(days)} days; GitHub markup may have changed.")
    return days, total


def render(days, total):
    W, P = 840, 6                       # image width, outer inset (matches the other cards)
    cell, gap = 11, 3
    step = cell + gap
    start = min(days)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)   # back to Sunday
    end = max(days)
    weeks = (end - start).days // 7 + 1
    grid_w = weeks * step - gap
    left = P + 20 + 30                   # card padding + weekday labels
    left += max(0, (W - 2 * P - 40 - 30 - grid_w) // 2)
    top = 72
    h = top + 7 * step - gap + 46

    css = (
        "text{font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",\"Noto Sans\",Helvetica,Arial,sans-serif}"
        ".bg{fill:#ffffff;stroke:#d0d7de}.t{fill:#1f2328}.m{fill:#59636e}"
        ".lab{font-size:11px;font-weight:600;letter-spacing:1.6px}"
        + "".join(f".l{i}{{fill:{c}}}" for i, c in enumerate(LIGHT))
        + "@media (prefers-color-scheme:dark){.bg{fill:#0d1117;stroke:#30363d}.t{fill:#e6edf3}.m{fill:#9198a1}"
        + "".join(f".l{i}{{fill:{c}}}" for i, c in enumerate(DARK)) + "}"
    )
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" '
           f'aria-label="GitHub contributions"><title>GitHub contributions</title><style>{css}</style>',
           f'<rect class="bg" x="{P + .5}" y=".5" width="{W - 2 * P - 1}" height="{h - P - 1}" rx="12"/>',
           f'<text x="{P + 20}" y="34" class="m lab">GITHUB CONTRIBUTIONS</text>']
    if total is not None:
        out.append(f'<text x="{W - P - 20}" y="34" class="m" font-size="12" text-anchor="end">'
                   f'{total:,} contributions in the last year</text>')
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="{P + 20}" y="{top + row * step + 9}" class="m" font-size="10">{name}</text>')
    last_month = None
    for w in range(weeks):
        week_start = start + dt.timedelta(days=7 * w)
        if (w == 0 or (week_start.month != last_month and week_start.day <= 7)) and w < weeks - 2:
            out.append(f'<text x="{left + w * step}" y="{top - 9}" class="m" font-size="10">{MONTHS[week_start.month - 1]}</text>')
        last_month = week_start.month
        for d in range(7):
            day = week_start + dt.timedelta(days=d)
            if day in days:
                out.append(f'<rect class="l{days[day]}" x="{left + w * step}" y="{top + d * step}" '
                           f'width="{cell}" height="{cell}" rx="2.5"><title>{day.isoformat()}</title></rect>')
    lx = W - P - 20 - (5 * step - gap) - 34
    ly = top + 7 * step + 14
    out.append(f'<text x="{lx - 8}" y="{ly + 9}" class="m" font-size="10" text-anchor="end">Less</text>')
    for i in range(5):
        out.append(f'<rect class="l{i}" x="{lx + i * step}" y="{ly}" width="{cell}" height="{cell}" rx="2.5"/>')
    out.append(f'<text x="{lx + 5 * step + 5}" y="{ly + 9}" class="m" font-size="10">More</text>')
    out.append("</svg>")
    return "".join(out)


def main():
    user = sys.argv[1]
    dest = sys.argv[2] if len(sys.argv) > 2 else "assets/contributions.svg"
    if "--levels" in sys.argv:
        i = sys.argv.index("--levels")
        first = dt.date.fromisoformat(sys.argv[i + 1])
        days = {first + dt.timedelta(days=k): int(c) for k, c in enumerate(sys.argv[i + 2])}
        total = int(sys.argv[i + 3])
    else:
        days, total = fetch(user)
    with open(dest, "w") as f:
        f.write(render(days, total))
    print(f"Wrote {dest}: {len(days)} days, total {total}")


if __name__ == "__main__":
    main()
