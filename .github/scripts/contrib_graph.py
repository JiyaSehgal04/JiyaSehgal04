"""Render a dracula-themed weekly contribution graph SVG.

Usage: python contrib_graph.py <github-user> <out.svg>
Uses the GraphQL API when GITHUB_TOKEN is set, otherwise the public
contributions page.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import date

USER, OUT = sys.argv[1], sys.argv[2]

BG, CARD_LINE = "#282a36", "#44475a"
TEXT, MUTED = "#f8f8f2", "#6272a4"
PINK, PURPLE, CYAN = "#ff79c6", "#bd93f9", "#8be9fd"


def fetch_graphql(token):
    query = """query($login:String!){user(login:$login){contributionsCollection{
      contributionCalendar{weeks{contributionDays{date contributionCount}}}}}}"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    data = json.load(urllib.request.urlopen(req))
    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def fetch_public_page():
    html = urllib.request.urlopen(f"https://github.com/users/{USER}/contributions").read().decode()
    dates = dict(re.findall(r'data-date="([\d-]+)" id="([^"]+)"', html))
    dates = {v: k for k, v in dates.items()}  # id -> date
    counts = {}
    for cell_id, label in re.findall(r'<tool-tip [^>]*for="([^"]+)"[^>]*>([^<]*)', html):
        if cell_id in dates:
            m = re.match(r"(\d+) contribution", label)
            counts[dates[cell_id]] = int(m.group(1)) if m else 0
    return counts


token = os.environ.get("GITHUB_TOKEN")
days = fetch_graphql(token) if token else fetch_public_page()
days = dict(sorted(days.items()))
dates = [date.fromisoformat(d) for d in days]
counts = list(days.values())

# group into weeks (Sunday-start, like GitHub)
weeks = []
for d, c in zip(dates, counts):
    if not weeks or d.weekday() == 6:
        weeks.append({"start": d, "total": 0})
    weeks[-1]["total"] += c

total = sum(counts)
active_days = sum(1 for c in counts if c)
best_i = max(range(len(counts)), key=counts.__getitem__)
best_week = max(weeks, key=lambda w: w["total"])
streak = longest = 0
for c in counts:
    streak = streak + 1 if c else 0
    longest = max(longest, streak)

# ---- layout ----
W, H = 900, 330
L, R, T, B = 60, 30, 70, 250          # plot area
pw, ph = W - L - R, B - T
n = len(weeks)
slot = pw / n
bw = max(3, slot * 0.62)
ymax = max(4, best_week["total"])
step = max(1, -(-ymax // 4))           # ceil(ymax / 4)
ymax = step * 4


def y(v):
    return B - v / ymax * ph


parts = [f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="'Segoe UI', Ubuntu, sans-serif">
<defs>
  <linearGradient id="bar" x1="0" y1="1" x2="0" y2="0">
    <stop offset="0" stop-color="{PURPLE}"/><stop offset="1" stop-color="{PINK}"/>
  </linearGradient>
</defs>
<style>
  .bar {{transform-box: fill-box; transform-origin: bottom; animation: grow .8s ease-out both;}}
  @keyframes grow {{from {{transform: scaleY(0);}} to {{transform: scaleY(1);}}}}
  .lbl {{fill: {MUTED}; font-size: 11px;}}
</style>
<rect width="{W}" height="{H}" rx="6" fill="{BG}"/>
<text x="{L - 30}" y="38" fill="{PINK}" font-size="20" font-weight="600">Contribution Activity</text>
<text x="{W - R}" y="38" fill="{TEXT}" font-size="13" text-anchor="end"><tspan fill="{PINK}" font-weight="700">{total}</tspan> contributions in the last year</text>
"""]

# grid + y labels
for i in range(5):
    v = step * i
    parts.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{CARD_LINE}" stroke-dasharray="{"" if i == 0 else "3 4"}"/>')
    parts.append(f'<text class="lbl" x="{L - 10}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>')

# bars + month labels
last_month = None
for i, w in enumerate(weeks):
    x = L + i * slot + (slot - bw) / 2
    if w["total"]:
        h = max(3, B - y(w["total"]))
        fill = CYAN if w is best_week else "url(#bar)"
        parts.append(
            f'<rect class="bar" style="animation-delay:{i * 0.015:.3f}s" x="{x:.1f}" y="{B - h:.1f}" '
            f'width="{bw:.1f}" height="{h:.1f}" rx="2" fill="{fill}">'
            f'<title>Week of {w["start"]:%b %d}: {w["total"]} contributions</title></rect>'
        )
    else:
        parts.append(f'<rect x="{x:.1f}" y="{B - 2}" width="{bw:.1f}" height="2" rx="1" fill="{CARD_LINE}"/>')
    if w["start"].month != last_month and w["start"].day <= 7:
        last_month = w["start"].month
        parts.append(f'<text class="lbl" x="{x:.1f}" y="{B + 18}">{w["start"]:%b}</text>')

# best-week marker
bi = weeks.index(best_week)
bx = L + bi * slot + slot / 2
parts.append(f'<text x="{bx:.1f}" y="{y(best_week["total"]) - 8:.1f}" fill="{CYAN}" font-size="11" text-anchor="middle" font-weight="600">{best_week["total"]}</text>')

# stats footer
stats = [
    ("Active days", f"{active_days}"),
    ("Best day", f"{counts[best_i]}  ·  {dates[best_i]:%b %d}"),
    ("Best week", f"{best_week['total']}  ·  {best_week['start']:%b %d}"),
    ("Longest streak", f"{longest} days"),
]
col = (W - 2 * 30) / len(stats)
for i, (k, v) in enumerate(stats):
    cx = 30 + col * i + col / 2
    parts.append(f'<text x="{cx:.0f}" y="{H - 30}" fill="{MUTED}" font-size="11" text-anchor="middle">{k.upper()}</text>')
    parts.append(f'<text x="{cx:.0f}" y="{H - 12}" fill="{TEXT}" font-size="14" font-weight="600" text-anchor="middle">{v}</text>')

parts.append("</svg>\n")
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w") as f:
    f.write("\n".join(parts))
print(f"{OUT}: {total} contributions, {n} weeks")
