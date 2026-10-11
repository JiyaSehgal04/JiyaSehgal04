"""Render a dracula-themed stats overview SVG: language donut + milestone rings.

Usage: python stats_card.py <github-user> <out.svg>
Set GITHUB_TOKEN to avoid the unauthenticated API rate limit.
"""
import json
import math
import os
import sys
import urllib.request

USER, OUT = sys.argv[1], sys.argv[2]
TOKEN = os.environ.get("GITHUB_TOKEN")

BG, LINE, TRACK = "#282a36", "#44475a", "#343746"
TEXT, MUTED = "#f8f8f2", "#6272a4"
PALETTE = ["#ff79c6", "#bd93f9", "#8be9fd", "#50fa7b", "#ffb86c", "#f1fa8c", "#ff5555"]
RING_COLORS = ["#ff79c6", "#bd93f9", "#8be9fd", "#50fa7b"]


def api(path):
    headers = {"User-Agent": "stats-card", "Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"bearer {TOKEN}"
    req = urllib.request.Request(f"https://api.github.com{path}", headers=headers)
    return json.load(urllib.request.urlopen(req, timeout=30))


user = api(f"/users/{USER}")
repos = [r for r in api(f"/users/{USER}/repos?per_page=100&type=owner") if not r["fork"]]
stars = sum(r["stargazers_count"] for r in repos)
commits = api(f"/search/commits?q=author:{USER}&per_page=1")["total_count"]

langs = {}
for r in repos:
    for lang, size in api(f"/repos/{USER}/{r['name']}/languages").items():
        langs[lang] = langs.get(lang, 0) + size
top = sorted(langs.items(), key=lambda kv: -kv[1])
shown = top[:6]
other = sum(v for _, v in top[6:])
if other:
    shown.append(("Other", other))
lang_total = sum(v for _, v in shown) or 1


def next_milestone(v):
    for m in (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000):
        if v < m:
            return m
    return v


metrics = [
    ("Repositories", len(repos)),
    ("Commits", commits),
    ("Stars", stars),
    ("Followers", user["followers"]),
]

W, H = 900, 300
parts = [f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="'Segoe UI', Ubuntu, sans-serif">
<defs>
  <filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<style>
  .seg {{animation: seg 1.4s ease-out both;}}
  @keyframes seg {{from {{stroke-dasharray: 0 10000;}}}}
  .fade {{opacity: 0; animation: fade .6s ease-out forwards;}}
  @keyframes fade {{to {{opacity: 1;}}}}
</style>
<rect width="{W}" height="{H}" rx="8" fill="{BG}"/>
<text x="28" y="40" fill="#ff79c6" font-size="20" font-weight="700">Stats Overview</text>
<text x="{W - 28}" y="40" fill="{MUTED}" font-size="12" text-anchor="end">languages by code size · rings show progress to the next milestone</text>
<line x1="470" x2="470" y1="70" y2="{H - 30}" stroke="{LINE}"/>
"""]

# ---- language donut ----
cx, cy, r, sw = 150, 170, 82, 24
circ = 2 * math.pi * r
offset = 0.0
for i, (lang, size) in enumerate(shown):
    frac = size / lang_total
    seg = max(0.0, frac * circ - 2)  # 2px gap between segments
    col = PALETTE[i % len(PALETTE)]
    parts.append(
        f'<circle class="seg" style="animation-delay:{i * 0.12:.2f}s" cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'stroke="{col}" stroke-width="{sw}" stroke-dasharray="{seg:.1f} {circ:.1f}" '
        f'stroke-dashoffset="{-offset:.1f}" transform="rotate(-90 {cx} {cy})">'
        f"<title>{lang}: {frac * 100:.1f}%</title></circle>"
    )
    offset += frac * circ
top_name = shown[0][0] if shown else "-"
parts.append(f'<text x="{cx}" y="{cy - 4}" fill="{TEXT}" font-size="{16 if len(top_name) < 12 else 12}" font-weight="700" text-anchor="middle">{top_name}</text>')
parts.append(f'<text x="{cx}" y="{cy + 16}" fill="{MUTED}" font-size="11" text-anchor="middle">top language · {len(langs)} total</text>')

for i, (lang, size) in enumerate(shown):
    ly = 92 + i * 26
    col = PALETTE[i % len(PALETTE)]
    parts.append(f'<g class="fade" style="animation-delay:{0.4 + i * 0.1:.2f}s">'
                 f'<rect x="270" y="{ly - 10}" width="12" height="12" rx="3" fill="{col}"/>'
                 f'<text x="290" y="{ly}" fill="{TEXT}" font-size="13">{lang}</text>'
                 f'<text x="445" y="{ly}" fill="{MUTED}" font-size="13" text-anchor="end">{size / lang_total * 100:.1f}%</text></g>')

# ---- milestone rings ----
rr, rsw = 36, 8
rcirc = 2 * math.pi * rr
col_w = (W - 20 - 485) / 4
for i, (label, value) in enumerate(metrics):
    goal = next_milestone(value)
    frac = min(1.0, value / goal)
    rx, ry = 485 + col_w * i + col_w / 2, 160
    col = RING_COLORS[i]
    parts.append(f'<circle cx="{rx:.1f}" cy="{ry}" r="{rr}" fill="none" stroke="{TRACK}" stroke-width="{rsw}"/>')
    parts.append(
        f'<circle class="seg" style="animation-delay:{0.3 + i * 0.15:.2f}s" cx="{rx:.1f}" cy="{ry}" r="{rr}" fill="none" '
        f'stroke="{col}" stroke-width="{rsw}" stroke-linecap="round" stroke-dasharray="{frac * rcirc:.1f} {rcirc:.1f}" '
        f'transform="rotate(-90 {rx:.1f} {ry})" filter="url(#glow)"/>'
    )
    parts.append(f'<text x="{rx:.1f}" y="{ry + 8}" fill="{TEXT}" font-size="22" font-weight="700" text-anchor="middle">{value:,}</text>')
    parts.append(f'<text x="{rx:.1f}" y="{ry + 66}" fill="{col}" font-size="13" font-weight="600" text-anchor="middle">{label}</text>')
    parts.append(f'<text x="{rx:.1f}" y="{ry + 84}" fill="{MUTED}" font-size="11" text-anchor="middle">next: {goal:,}</text>')

parts.append("</svg>\n")
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w") as f:
    f.write("\n".join(parts))
print(f"{OUT}: {len(repos)} repos, {commits} commits, {stars} stars, {len(langs)} languages")
