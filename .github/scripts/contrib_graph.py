"""Render a dracula-themed contribution dashboard SVG.

Usage: python contrib_graph.py <github-user> <out.svg>
Uses the GraphQL API when GITHUB_TOKEN is set, otherwise the public
contributions pages.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date, timedelta

USER, OUT = sys.argv[1], sys.argv[2]
TOKEN = os.environ.get("GITHUB_TOKEN")

BG, LINE = "#282a36", "#44475a"
TEXT, MUTED = "#f8f8f2", "#6272a4"
PINK, PURPLE, CYAN, GREEN = "#ff79c6", "#bd93f9", "#8be9fd", "#50fa7b"


def get(url, data=None):
    headers = {"User-Agent": "contrib-graph"}
    if TOKEN and "api.github.com" in url:
        headers["Authorization"] = f"bearer {TOKEN}"
    if data:
        headers["Content-Type"] = "application/json"
    return urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=30).read()


def year_graphql(start, end):
    query = """query($login:String!,$from:DateTime!,$to:DateTime!){user(login:$login){
      contributionsCollection(from:$from,to:$to){contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    body = json.dumps({"query": query, "variables": {
        "login": USER, "from": f"{start}T00:00:00Z", "to": f"{end}T23:59:59Z"}}).encode()
    weeks = json.loads(get("https://api.github.com/graphql", body))["data"]["user"][
        "contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def year_public(start, end):
    html = get(f"https://github.com/users/{USER}/contributions?from={start}&to={end}").decode()
    ids = {i: d for d, i in re.findall(r'data-date="([\d-]+)" id="([^"]+)"', html)}
    out = {d: 0 for d in ids.values()}
    for cell, label in re.findall(r'<tool-tip [^>]*for="([^"]+)"[^>]*>([^<]*)', html):
        m = re.match(r"(\d+) contribution", label)
        if cell in ids and m:
            out[ids[cell]] = int(m.group(1))
    return out


# ---- data: every day since the account was created ----
joined = date.fromisoformat(json.loads(get(f"https://api.github.com/users/{USER}"))["created_at"][:10])
today = date.today()
days = {}
for yr in range(joined.year, today.year + 1):
    start, end = max(joined, date(yr, 1, 1)), min(today, date(yr, 12, 31))
    days.update((year_graphql if TOKEN else year_public)(start, end))
days = {date.fromisoformat(k): v for k, v in days.items() if joined <= date.fromisoformat(k) <= today}
for i in range((today - joined).days + 1):
    days.setdefault(joined + timedelta(i), 0)
dates = sorted(days)
counts = [days[d] for d in dates]

total = sum(counts)
year_ago = today - timedelta(days=365)
last_year = sum(c for d, c in zip(dates, counts) if d > year_ago)
active = sum(1 for c in counts if c)
best_i = max(range(len(counts)), key=counts.__getitem__)

months = {}
for d, c in zip(dates, counts):
    months[(d.year, d.month)] = months.get((d.year, d.month), 0) + c
month_keys = sorted(months)

first = next((d for d, c in zip(dates, counts) if c), dates[0])
plot_start = max(dates[0], date(first.year - (first.month == 1), (first.month - 2) % 12 + 1, 1))
keep = [i for i, d in enumerate(dates) if d >= plot_start]
dates, counts = [dates[i] for i in keep], [counts[i] for i in keep]
month_keys = [k for k in month_keys if date(*k, 1) >= date(plot_start.year, plot_start.month, 1)]

# ---- layout ----
W, H = 900, 400
L, R, T, B = 64, 36, 150, 345
pw, ph = W - L - R, B - T
span = (dates[-1] - dates[0]).days or 1


def x_of(d):
    return L + (d - dates[0]).days / span * pw


need = max(8, total * 1.08) / 4
mag = 10 ** (len(str(int(need))) - 1)
tick = next(m * mag for m in (1, 2, 2.5, 3, 4, 5, 6, 8, 10) if m * mag >= need)
ymax = tick * 4


def y_of(v):
    return B - v / ymax * ph


# cumulative path, sampled weekly to keep the SVG small
pts, run = [], 0
for i, (d, c) in enumerate(zip(dates, counts)):
    run += c
    if i % 7 == 0 or i == len(dates) - 1 or c:
        pts.append((x_of(d), y_of(run)))
line = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
area = line + f" L{pts[-1][0]:.1f},{B} L{pts[0][0]:.1f},{B} Z"
path_len = sum(((pts[i][0] - pts[i - 1][0]) ** 2 + (pts[i][1] - pts[i - 1][1]) ** 2) ** 0.5 for i in range(1, len(pts)))
ex, ey = pts[-1]

parts = [f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="'Segoe UI', Ubuntu, sans-serif">
<defs>
  <linearGradient id="stroke" x1="0" x2="1"><stop offset="0" stop-color="{PURPLE}"/><stop offset="1" stop-color="{PINK}"/></linearGradient>
  <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PINK}" stop-opacity=".35"/><stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></linearGradient>
  <linearGradient id="tile" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#343746"/><stop offset="1" stop-color="#2d2f3d"/></linearGradient>
  <filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<style>
  .draw {{stroke-dasharray: {path_len:.0f}; stroke-dashoffset: {path_len:.0f}; animation: draw 2.6s ease-out .3s forwards;}}
  @keyframes draw {{to {{stroke-dashoffset: 0;}}}}
  .fade {{opacity: 0; animation: fade 1.2s ease-out 1.8s forwards;}}
  @keyframes fade {{to {{opacity: 1;}}}}
  .pulse {{transform-box: fill-box; transform-origin: center; animation: pulse 2s ease-in-out 2.9s infinite;}}
  @keyframes pulse {{0%,100% {{transform: scale(1); opacity: .9;}} 50% {{transform: scale(2.4); opacity: 0;}}}}
  .tile {{opacity: 0; animation: fade .6s ease-out forwards;}}
  .lbl {{fill: {MUTED}; font-size: 11px;}}
</style>
<rect width="{W}" height="{H}" rx="8" fill="{BG}"/>
<text x="28" y="40" fill="{PINK}" font-size="20" font-weight="700">Contribution Journey</text>
<text x="{W - 28}" y="40" fill="{MUTED}" font-size="12" text-anchor="end">since {joined:%b %Y} · updated {today:%b %d, %Y}</text>
"""]

# KPI tiles
tiles = [
    ("ALL-TIME", f"{total}", "contributions", PINK),
    ("LAST 12 MONTHS", f"{last_year}", "contributions", PURPLE),
    ("ACTIVE DAYS", f"{active}", "days with commits", CYAN),
    ("BEST DAY", f"{counts[best_i]}", f"on {dates[best_i]:%b %d, %Y}", GREEN),
]
tw, gap = (W - 56 - 3 * 14) / 4, 14
for i, (k, v, sub, col) in enumerate(tiles):
    tx = 28 + i * (tw + gap)
    parts.append(f'<g class="tile" style="animation-delay:{i * 0.12:.2f}s">'
                 f'<rect x="{tx:.1f}" y="58" width="{tw:.1f}" height="66" rx="8" fill="url(#tile)" stroke="{LINE}"/>'
                 f'<rect x="{tx:.1f}" y="58" width="4" height="66" rx="2" fill="{col}"/>'
                 f'<text x="{tx + 18:.1f}" y="78" fill="{MUTED}" font-size="10" font-weight="600" letter-spacing="1">{k}</text>'
                 f'<text x="{tx + 18:.1f}" y="106" fill="{col}" font-size="26" font-weight="700">{v}</text>'
                 f'<text x="{tx + 18 + 17 * len(v):.1f}" y="106" fill="{MUTED}" font-size="11">{sub}</text></g>')

# grid + axis labels
for i in range(5):
    v = tick * i
    parts.append(f'<line x1="{L}" x2="{W - R}" y1="{y_of(v):.1f}" y2="{y_of(v):.1f}" stroke="{LINE}" stroke-dasharray="{"" if i == 0 else "2 5"}"/>')
    parts.append(f'<text class="lbl" x="{L - 10}" y="{y_of(v) + 4:.1f}" text-anchor="end">{v:g}</text>')

# faint monthly bars (own scale, bottom 45% of the plot)
mmax = max(months.values()) or 1
last_label_x = -1e9
for (yr, mo) in month_keys:
    m0 = max(date(yr, mo, 1), dates[0])
    m1 = min(date(yr + (mo == 12), mo % 12 + 1, 1) - timedelta(1), dates[-1])
    x0, x1 = x_of(m0), x_of(m1)
    if months[(yr, mo)]:
        h = months[(yr, mo)] / mmax * ph * 0.45
        parts.append(f'<rect class="fade" x="{x0 + 1:.1f}" y="{B - h:.1f}" width="{max(2, x1 - x0 - 2):.1f}" height="{h:.1f}" rx="2" fill="{CYAN}" fill-opacity=".22">'
                     f'<title>{date(yr, mo, 1):%b %Y}: {months[(yr, mo)]} contributions</title></rect>')
    if (mo in (1, 4, 7, 10) or (yr, mo) == month_keys[0]) and x0 - last_label_x > 46:
        last_label_x = x0
        label = f"{date(yr, mo, 1):%b}" + (f" '{yr % 100}" if mo == 1 or (yr, mo) == month_keys[0] else "")
        parts.append(f'<text class="lbl" x="{x0:.1f}" y="{B + 18}">{label}</text>')

# cumulative area + glowing line + live dot
parts.append(f'<path class="fade" d="{area}" fill="url(#fill)"/>')
parts.append(f'<path class="draw" d="{line}" fill="none" stroke="url(#stroke)" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" filter="url(#glow)"/>')
parts.append(f'<g class="fade"><circle class="pulse" cx="{ex:.1f}" cy="{ey:.1f}" r="6" fill="{PINK}"/>'
             f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{PINK}" stroke="{BG}" stroke-width="2"/>'
             f'<text x="{ex - 12:.1f}" y="{ey - 14:.1f}" fill="{TEXT}" font-size="13" font-weight="700" text-anchor="end">{total} total</text></g>')
parts.append(f'<text x="{W - R}" y="{B + 36}" fill="{MUTED}" font-size="10" text-anchor="end">'
             f'<tspan fill="{PINK}">━</tspan> cumulative contributions   <tspan fill="{CYAN}">■</tspan> per month</text>')

parts.append("</svg>\n")
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w") as f:
    f.write("\n".join(parts))
print(f"{OUT}: {total} all-time, {last_year} last year, {len(dates)} days")
