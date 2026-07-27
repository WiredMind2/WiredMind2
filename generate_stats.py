#!/usr/bin/env python3
"""Generate animated SVG assets for the GitHub profile README."""

import os
from collections import defaultdict

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
USERNAME = os.environ.get("GITHUB_USERNAME")

if not GITHUB_TOKEN:
    raise Exception("GITHUB_TOKEN environment variable is required")

if not USERNAME:
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    r = requests.get("https://api.github.com/user", headers=headers, timeout=30)
    if r.status_code == 200:
        USERNAME = r.json()["login"]
    else:
        raise Exception(
            "GITHUB_USERNAME environment variable is required or token is invalid"
        )

print(f"Generating stats for user: {USERNAME}")


def run_query(query, variables):
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    request = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=60,
    )
    if request.status_code == 200:
        payload = request.json()
        if "errors" in payload:
            raise Exception(f"GraphQL errors: {payload['errors']}")
        return payload
    raise Exception(
        f"Query failed with status {request.status_code}: {request.text}"
    )


query = """
query($login: String!) {
  user(login: $login) {
    name
    login
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
    repositoriesContributedTo(
      first: 1
      contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
    ) {
      totalCount
    }
    pullRequests(first: 1) {
      totalCount
    }
    issues(first: 1) {
      totalCount
    }
    followers {
      totalCount
    }
    createdRepositories: repositories(
      first: 1
      ownerAffiliations: OWNER
      isFork: false
    ) {
      totalCount
    }
    pinnedItems(first: 4, types: REPOSITORY) {
      nodes {
        ... on Repository {
          name
          description
          url
          stargazerCount
          primaryLanguage {
            name
            color
          }
        }
      }
    }
    repositories(
      first: 100
      ownerAffiliations: OWNER
      orderBy: { direction: DESC, field: STARGAZERS }
    ) {
      nodes {
        stargazers {
          totalCount
        }
        languages(first: 10, orderBy: { field: SIZE, direction: DESC }) {
          edges {
            size
            node {
              color
              name
            }
          }
        }
      }
    }
  }
}
"""

variables = {"login": USERNAME}
result = run_query(query, variables)
data = result["data"]["user"]

login = data["login"]
# Human-facing name for the README header (portfolio brand); override via env.
display_name = os.environ.get("PROFILE_DISPLAY_NAME") or "William"

total_commits = (
    data["contributionsCollection"]["totalCommitContributions"]
    + data["contributionsCollection"]["restrictedContributionsCount"]
)
total_prs = data["pullRequests"]["totalCount"]
total_issues = data["issues"]["totalCount"]
total_contributed_to = data["repositoriesContributedTo"]["totalCount"]
followers = data["followers"]["totalCount"]
total_created = data["createdRepositories"]["totalCount"]
calendar = data["contributionsCollection"]["contributionCalendar"]
total_contributions = calendar["totalContributions"]

repositories = data["repositories"]["nodes"]
total_stars = sum(
    (repo["stargazers"]["totalCount"] or 0)
    for repo in repositories
    if repo and repo.get("stargazers")
)

language_sizes = defaultdict(int)
language_colors = {}

for repo in repositories:
    if not repo or not repo.get("languages") or not repo["languages"].get("edges"):
        continue
    for edge in repo["languages"]["edges"]:
        lang_name = edge["node"]["name"]
        language_sizes[lang_name] += edge["size"]
        color = edge["node"]["color"]
        if color:
            language_colors[lang_name] = color

total_size = sum(language_sizes.values()) or 1
top_languages = sorted(language_sizes.items(), key=lambda x: x[1], reverse=True)[:6]
pinned = [node for node in data["pinnedItems"]["nodes"] if node]


def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def truncate(text, max_len):
    text = text or ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


SHARED_STYLE = """
    :root {
        --bg: #f3f7f5;
        --ink: #14201c;
        --muted: #5c6b66;
        --line: #d5e0db;
        --accent: #0f766e;
        --accent-soft: #99f6e4;
        --cell-0: #e6eeea;
        --glow: rgba(15, 118, 110, 0.14);
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --bg: #0b1210;
            --ink: #e7f0ec;
            --muted: #93a39c;
            --line: #24302c;
            --accent: #2dd4bf;
            --accent-soft: #115e59;
            --cell-0: #1b2421;
            --glow: rgba(45, 212, 191, 0.14);
        }
    }

    .font { font-family: "Segoe UI", ui-sans-serif, system-ui, sans-serif; }
    .bg { fill: var(--bg); }

    @keyframes rise {
        from { opacity: 0; transform: translateY(12px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fade {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes sweep {
        from { transform: scaleX(0); }
        to { transform: scaleX(1); }
    }
    @keyframes drift {
        0%, 100% { transform: translate(0, 0); }
        50% { transform: translate(8px, -6px); }
    }
    @keyframes pulse {
        0%, 100% { opacity: 0.3; }
        50% { opacity: 0.8; }
    }
    @keyframes cellIn {
        from { opacity: 0; transform: scale(0.65); }
        to { opacity: 1; transform: scale(1); }
    }

    .rise { animation: rise 0.7s cubic-bezier(0.22, 1, 0.36, 1) both; }
    .fade { animation: fade 0.8s ease both; }
    .bar-grow {
        transform-box: fill-box;
        transform-origin: left center;
        animation: sweep 0.9s cubic-bezier(0.22, 1, 0.36, 1) both;
    }
    .drift { animation: drift 8s ease-in-out infinite; }
    .pulse { animation: pulse 3.2s ease-in-out infinite; }
    .cell-in {
        transform-box: fill-box;
        transform-origin: center;
        animation: cellIn 0.45s cubic-bezier(0.22, 1, 0.36, 1) both;
    }

    .d1 { animation-delay: 0.05s; }
    .d2 { animation-delay: 0.12s; }
    .d3 { animation-delay: 0.2s; }
    .d4 { animation-delay: 0.28s; }
    .d5 { animation-delay: 0.36s; }
    .d6 { animation-delay: 0.44s; }
    .d7 { animation-delay: 0.52s; }
    .d8 { animation-delay: 0.6s; }

    @media (prefers-reduced-motion: reduce) {
        .rise, .fade, .bar-grow, .drift, .pulse, .cell-in {
            animation: none !important;
            opacity: 1 !important;
            transform: none !important;
        }
    }
"""


def build_header_svg():
    width, height = 880, 200
    coords = [
        (72, 48), (140, 150), (210, 70), (300, 40), (360, 160),
        (450, 55), (520, 145), (600, 45), (680, 155), (760, 80),
        (820, 130), (100, 110), (250, 125), (400, 100), (700, 105),
    ]
    dots = []
    for i, (x, y) in enumerate(coords):
        r = 1.6 + (i % 3) * 0.7
        delay = (i % 8) * 0.25
        dots.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="var(--accent)" '
            f'class="pulse" style="animation-delay:{delay}s"/>'
        )

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="headerTitle headerDesc">
  <title id="headerTitle">{esc(display_name)} on GitHub</title>
  <desc id="headerDesc">Animated GitHub profile header for {esc(login)}</desc>
  <style>
{SHARED_STYLE}
    .name {{ font: 700 44px "Segoe UI", ui-sans-serif, system-ui, sans-serif; fill: var(--ink); letter-spacing: -0.03em; }}
    .tag {{ font: 500 15px "Segoe UI", ui-sans-serif, system-ui, sans-serif; fill: var(--muted); }}
    .meta {{ font: 600 13px "Segoe UI", ui-sans-serif, system-ui, sans-serif; fill: var(--accent); }}
  </style>
  <defs>
    <linearGradient id="wash" x1="0" y1="0" x2="{width}" y2="{height}" gradientUnits="userSpaceOnUse">
      <stop stop-color="var(--accent-soft)" stop-opacity="0.55"/>
      <stop offset="0.55" stop-color="var(--bg)" stop-opacity="0.15"/>
      <stop offset="1" stop-color="var(--bg)" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="orb" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(720 50) rotate(90) scale(160 170)">
      <stop stop-color="var(--accent)" stop-opacity="0.32"/>
      <stop offset="1" stop-color="var(--accent)" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="{width}" height="{height}" rx="18" class="bg"/>
  <rect width="{width}" height="{height}" rx="18" fill="url(#wash)"/>
  <ellipse cx="720" cy="50" rx="170" ry="110" fill="url(#orb)" class="drift"/>
  <g aria-hidden="true">{"".join(dots)}</g>

  <g class="rise d1">
    <text x="48" y="58" class="meta font">GITHUB · @{esc(login)}</text>
    <text x="48" y="112" class="name">{esc(display_name)}</text>
    <text x="48" y="148" class="tag">Commits, pull requests, and open-source work — updated daily</text>
    <text x="48" y="176" class="meta font">{followers} followers  ·  {total_contributions} contributions this year</text>
  </g>
</svg>
"""


def intensity_color(count, max_count):
    if count <= 0:
        return "var(--cell-0)"
    t = count / max_count
    if t < 0.25:
        return "#99f6e4"
    if t < 0.5:
        return "#5eead4"
    if t < 0.75:
        return "#2dd4bf"
    return "#0f766e"


def build_stats_svg():
    width, height = 880, 360
    stats = [
        ("Stars", total_stars),
        ("Commits (year)", total_commits),
        ("Pull requests", total_prs),
        ("Issues", total_issues),
        ("Contributed to", total_contributed_to),
        ("Repos created", total_created),
    ]

    weeks = calendar["weeks"][-52:]
    cell, gap = 11, 3
    cal_x, cal_y = 40, 250
    cal_w = len(weeks) * (cell + gap)
    max_count = 1
    for week in weeks:
        for day in week["contributionDays"]:
            max_count = max(max_count, day["contributionCount"])

    cells = []
    for wi, week in enumerate(weeks):
        for di, day in enumerate(week["contributionDays"]):
            count = day["contributionCount"]
            x = cal_x + wi * (cell + gap)
            y = cal_y + di * (cell + gap)
            delay = min(1.6, (wi + di) * 0.012)
            cells.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
                f'fill="{intensity_color(count, max_count)}" class="cell-in" '
                f'style="animation-delay:{delay}s">'
                f'<title>{esc(day["date"])}: {count}</title></rect>'
            )

    lang_rows = []
    bar_max = 220
    for i, (lang, size) in enumerate(top_languages):
        pct = (size / total_size) * 100
        bar_w = max(8, (pct / 100) * bar_max)
        color = language_colors.get(lang, "#94a3b8")
        y = 86 + i * 26
        lang_rows.append(
            f"""
      <g class="rise d{min(i + 2, 8)}" transform="translate(470, {y})">
        <text x="0" y="0" class="font" style="font:500 13px 'Segoe UI',sans-serif; fill: var(--ink)">{esc(lang)}</text>
        <text x="{bar_max}" y="0" text-anchor="end" class="font" style="font:500 12px 'Segoe UI',sans-serif; fill: var(--muted)">{pct:.1f}%</text>
        <rect x="0" y="8" width="{bar_max}" height="7" rx="3.5" fill="var(--line)"/>
        <rect x="0" y="8" width="{bar_w:.1f}" height="7" rx="3.5" fill="{color}" class="bar-grow" style="animation-delay:{0.18 + i * 0.07}s"/>
      </g>"""
        )

    stat_rows = []
    for i, (label, value) in enumerate(stats):
        y = 86 + i * 26
        stat_rows.append(
            f"""
      <g class="rise d{min(i + 2, 8)}" transform="translate(40, {y})">
        <text x="0" y="0" class="font" style="font:500 13px 'Segoe UI',sans-serif; fill: var(--muted)">{esc(label)}</text>
        <text x="250" y="0" text-anchor="end" class="font" style="font:700 15px 'Segoe UI',sans-serif; fill: var(--ink)">{value}</text>
        <line x1="0" y1="10" x2="250" y2="10" stroke="var(--line)" stroke-width="1"/>
      </g>"""
        )

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="statsTitle statsDesc">
  <title id="statsTitle">{esc(login)} GitHub stats</title>
  <desc id="statsDesc">Auto-updated stats, languages, and contribution activity</desc>
  <style>
{SHARED_STYLE}
  </style>
  <defs>
    <linearGradient id="statsWash" x1="0" y1="0" x2="{width}" y2="{height}" gradientUnits="userSpaceOnUse">
      <stop stop-color="var(--accent-soft)" stop-opacity="0.35"/>
      <stop offset="1" stop-color="var(--bg)" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <rect width="{width}" height="{height}" rx="18" class="bg"/>
  <rect width="{width}" height="{height}" rx="18" fill="url(#statsWash)"/>

  <text x="40" y="40" class="font rise d1" style="font:700 22px 'Segoe UI',sans-serif; fill: var(--ink)">GitHub activity</text>
  <text x="840" y="40" text-anchor="end" class="font rise d2" style="font:500 12px 'Segoe UI',sans-serif; fill: var(--muted)">updated daily</text>

  <text x="40" y="68" class="font rise d2" style="font:700 12px 'Segoe UI',sans-serif; fill: var(--accent); letter-spacing: 0.04em;">OVERVIEW</text>
  <text x="470" y="68" class="font rise d2" style="font:700 12px 'Segoe UI',sans-serif; fill: var(--accent); letter-spacing: 0.04em;">TOP LANGUAGES</text>

  {"".join(stat_rows)}
  {"".join(lang_rows)}

  <g class="rise d6">
    <text x="40" y="240" class="font" style="font:700 13px 'Segoe UI',sans-serif; fill: var(--ink)">Contribution graph · {total_contributions} in the last year</text>
    {"".join(cells)}
    <text x="{cal_x + cal_w}" y="{cal_y + 7 * (cell + gap) + 2}" text-anchor="end" class="font" style="font:500 11px 'Segoe UI',sans-serif; fill: var(--muted)">less → more</text>
  </g>
</svg>
"""


def build_pinned_markdown():
    if not pinned:
        return ""
    lines = [
        "",
        '<div align="center">',
        "",
        "### Featured repositories",
        "",
    ]
    for repo in pinned[:4]:
        lang = (repo.get("primaryLanguage") or {}).get("name")
        lang_bit = f" · {lang}" if lang else ""
        desc = truncate(repo.get("description") or "Pinned repository", 80)
        stars = repo.get("stargazerCount", 0)
        lines.append(f"**[{repo['name']}]({repo['url']})** — {desc}  ")
        lines.append(f"`★ {stars}{lang_bit}`")
        lines.append("")
    lines.append("</div>")
    lines.append("")
    return "\n".join(lines)


def sync_readme_pinned(pinned_md):
    readme_path = "README.md"
    start = "<!-- DYNAMIC:PINNED:START -->"
    end = "<!-- DYNAMIC:PINNED:END -->"
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    if start not in content or end not in content:
        print("README markers missing; skipped pinned section sync")
        return
    before, rest = content.split(start, 1)
    _, after = rest.split(end, 1)
    updated = f"{before}{start}\n{pinned_md}{end}{after}"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated)


header_svg = build_header_svg()
stats_svg = build_stats_svg()
pinned_md = build_pinned_markdown()

with open("profile_header.svg", "w", encoding="utf-8") as f:
    f.write(header_svg)

with open("github_stats.svg", "w", encoding="utf-8") as f:
    f.write(stats_svg)

sync_readme_pinned(pinned_md)

print("Successfully generated profile_header.svg, github_stats.svg, and synced README.md")
