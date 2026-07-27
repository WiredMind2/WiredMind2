#!/usr/bin/env python3
"""Generate animated SVG assets for the GitHub profile README."""

import math
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

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
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes {
        ... on Repository {
          name
          description
          url
          stargazerCount
          forkCount
          primaryLanguage {
            name
            color
          }
          repositoryTopics(first: 3) {
            nodes {
              topic {
                name
              }
            }
          }
          languages(first: 3, orderBy: { field: SIZE, direction: DESC }) {
            edges {
              node {
                name
                color
              }
            }
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


def wrap_text(text, max_chars, max_lines=2):
    text = (text or "").strip() or "Pinned repository"
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines:
            break
    if len(lines) < max_lines and current:
        lines.append(current)
    if len(lines) == max_lines and (
        len(" ".join(words)) > sum(len(line) for line in lines)
        or len(lines[-1]) > max_chars
    ):
        lines[-1] = truncate(lines[-1], max_chars)
    return lines[:max_lines]


def sanitize_filename(name):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._")
    return cleaned or "repo"


def quantile(sorted_vals, q):
    if not sorted_vals:
        return 0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def contribution_thresholds(weeks):
    nonzero = sorted(
        day["contributionCount"]
        for week in weeks
        for day in week["contributionDays"]
        if day["contributionCount"] > 0
    )
    if not nonzero:
        return (1, 2, 3)
    p50 = max(1, int(round(quantile(nonzero, 0.50))))
    p75 = max(p50 + 1, int(round(quantile(nonzero, 0.75))))
    p90 = max(p75 + 1, int(round(quantile(nonzero, 0.90))))
    return (p50, p75, p90)


CONTRIB_COLORS = {
    0: "var(--raised)",
    1: "#3d4a1e",
    2: "#6f8c2c",
    3: "#a3cf3d",
    4: "#c8f750",
}


def intensity_level(count, thresholds):
    if count <= 0:
        return 0
    p50, p75, p90 = thresholds
    if count <= p50:
        return 1
    if count <= p75:
        return 2
    if count <= p90:
        return 3
    return 4


SHARED_STYLE = """
    :root {
        --night: #08090b;
        --surface: #0e1014;
        --raised: #14171c;
        --ink: #e8e6e1;
        --muted: #8b919c;
        --line: #20242b;
        --acid: #c8f750;
        --acid-dim: #8fb52e;
    }

    .font-display {
        font-family: "Syne", ui-sans-serif, system-ui, sans-serif;
        font-weight: 800;
        letter-spacing: -0.03em;
        text-transform: uppercase;
        fill: var(--ink);
    }
    .font-mono {
        font-family: ui-monospace, "JetBrains Mono", SFMono-Regular, Menlo, monospace;
        letter-spacing: 0.2em;
        text-transform: uppercase;
    }
    .bg { fill: var(--night); }
    .surface { fill: var(--surface); }
    .ink { fill: var(--ink); }
    .muted { fill: var(--muted); }
    .acid { fill: var(--acid); }
    .line { stroke: var(--line); }

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
        0%, 100% { opacity: 0.25; }
        50% { opacity: 0.85; }
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
    .underline-grow {
        transform-box: fill-box;
        transform-origin: left center;
        animation: sweep 0.85s cubic-bezier(0.22, 1, 0.36, 1) both;
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
        .rise, .fade, .bar-grow, .underline-grow, .drift, .pulse, .cell-in {
            animation: none !important;
            opacity: 1 !important;
            transform: none !important;
        }
    }
"""


def diamond(cx, cy, size=5):
    half = size / 2
    return (
        f'<rect x="{cx - half}" y="{cy - half}" width="{size}" height="{size}" '
        f'fill="var(--acid)" transform="rotate(45 {cx} {cy})"/>'
    )


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
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="var(--acid)" '
            f'class="pulse" style="animation-delay:{delay}s"/>'
        )

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="headerTitle headerDesc">
  <title id="headerTitle">{esc(display_name)} on GitHub</title>
  <desc id="headerDesc">Animated GitHub profile header for {esc(login)}</desc>
  <style>
{SHARED_STYLE}
  </style>
  <defs>
    <linearGradient id="wash" x1="0" y1="0" x2="{width}" y2="{height}" gradientUnits="userSpaceOnUse">
      <stop stop-color="var(--acid)" stop-opacity="0.12"/>
      <stop offset="0.55" stop-color="var(--night)" stop-opacity="0.2"/>
      <stop offset="1" stop-color="var(--night)" stop-opacity="0"/>
    </linearGradient>
    <radialGradient id="orb" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(720 50) rotate(90) scale(160 170)">
      <stop stop-color="var(--acid)" stop-opacity="0.22"/>
      <stop offset="1" stop-color="var(--acid)" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="{width}" height="{height}" class="bg"/>
  <rect width="{width}" height="{height}" fill="url(#wash)"/>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" fill="none" stroke="var(--line)"/>
  <ellipse cx="720" cy="50" rx="170" ry="110" fill="url(#orb)" class="drift"/>
  <g aria-hidden="true">{"".join(dots)}</g>

  <g class="rise d1">
    {diamond(48, 42)}
    <text x="62" y="46" class="font-mono" style="font-size:11px; fill: var(--acid)">GITHUB · @{esc(login)}</text>
    <text x="40" y="108" class="font-display" style="font-size:44px">{esc(display_name)}</text>
    <text x="40" y="142" class="font-mono" style="font-size:12px; letter-spacing:0.12em; fill: var(--muted)">COMMITS · PULL REQUESTS · OPEN SOURCE</text>
    <text x="40" y="172" class="font-mono" style="font-size:11px; fill: var(--acid)">{followers} FOLLOWERS  ·  {total_contributions} CONTRIBUTIONS THIS YEAR</text>
  </g>
</svg>
"""


def month_labels(weeks, cell, gap, cal_x):
    labels = []
    last_month = None
    for wi, week in enumerate(weeks):
        if not week["contributionDays"]:
            continue
        first = week["contributionDays"][0]
        dt = datetime.strptime(first["date"], "%Y-%m-%d")
        month = dt.strftime("%b").upper()
        if month == last_month:
            continue
        # Skip a label if the previous month marker is too close.
        x = cal_x + wi * (cell + gap)
        if labels and x - labels[-1][0] < 28:
            continue
        labels.append((x, month))
        last_month = month
    return labels


def build_stats_svg():
    width = 880
    gutter = 40
    content_w = width - 2 * gutter
    cell, gap = 11, 3
    weeks = calendar["weeks"][-52:]
    thresholds = contribution_thresholds(weeks)
    cal_w = max(len(weeks) * (cell + gap) - gap, 0)

    # Vertical rhythm
    y_eyebrow = 36
    y_title = 68
    y_kpi = 108
    y_cols = 188
    row_h = 28
    y_cal_label = y_cols + 6 * row_h + 36
    y_months = y_cal_label + 18
    y_cal = y_months + 10
    y_legend = y_cal + 7 * (cell + gap) + 18
    height = y_legend + 24

    kpis = [
        (total_contributions, "CONTRIBUTIONS"),
        (total_commits, "COMMITS"),
        (total_prs, "PULL REQUESTS"),
        (total_created, "REPOS"),
    ]
    kpi_w = content_w / 4
    kpi_parts = []
    for i, (value, label) in enumerate(kpis):
        x = gutter + i * kpi_w
        kpi_parts.append(
            f"""
      <g transform="translate({x:.1f}, {y_kpi})">
        <g class="rise d{i + 2}">
          <text x="0" y="0" class="font-display" style="font-size:28px; fill: var(--acid)">{value}</text>
          <text x="0" y="22" class="font-mono" style="font-size:10px; fill: var(--muted)">{label}</text>
        </g>
      </g>"""
        )

    overview = [
        ("STARS", total_stars),
        ("COMMITS (YEAR)", total_commits),
        ("PULL REQUESTS", total_prs),
        ("ISSUES", total_issues),
        ("CONTRIBUTED TO", total_contributed_to),
        ("REPOS CREATED", total_created),
    ]
    overview_parts = []
    for i, (label, value) in enumerate(overview):
        y = y_cols + i * row_h
        overview_parts.append(
            f"""
      <g transform="translate({gutter}, {y})">
        <g class="rise d{min(i + 2, 8)}">
          <text x="0" y="0" class="font-mono" style="font-size:11px; fill: var(--muted)">{label}</text>
          <text x="250" y="0" text-anchor="end" class="font-display" style="font-size:15px; letter-spacing:-0.02em">{value}</text>
          <line x1="0" y1="10" x2="250" y2="10" stroke="var(--line)" stroke-width="1"/>
        </g>
      </g>"""
        )

    bar_max = 250
    lang_parts = []
    for i, (lang, size) in enumerate(top_languages):
        pct = (size / total_size) * 100
        bar_w = max(8, (pct / 100) * bar_max)
        color = language_colors.get(lang, "#8b919c")
        y = y_cols + i * row_h
        lang_parts.append(
            f"""
      <g transform="translate(470, {y})">
        <g class="rise d{min(i + 2, 8)}">
          <text x="0" y="0" class="font-mono" style="font-size:11px; letter-spacing:0.12em; fill: var(--ink)">{esc(lang.upper())}</text>
          <text x="{bar_max}" y="0" text-anchor="end" class="font-mono" style="font-size:11px; letter-spacing:0.08em; fill: var(--muted)">{pct:.1f}%</text>
          <rect x="0" y="8" width="{bar_max}" height="6" fill="var(--raised)"/>
          <rect x="0" y="8" width="{bar_w:.1f}" height="6" fill="{color}" class="bar-grow" style="animation-delay:{0.18 + i * 0.07}s"/>
        </g>
      </g>"""
        )

    cal_x = gutter
    cells = []
    for wi, week in enumerate(weeks):
        for di, day in enumerate(week["contributionDays"]):
            count = day["contributionCount"]
            level = intensity_level(count, thresholds)
            x = cal_x + wi * (cell + gap)
            y = y_cal + di * (cell + gap)
            delay = min(1.6, (wi + di) * 0.012)
            cells.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'fill="{CONTRIB_COLORS[level]}" class="cell-in" '
                f'style="animation-delay:{delay:.3f}s">'
                f'<title>{esc(day["date"])}: {count}</title></rect>'
            )

    month_parts = []
    for x, month in month_labels(weeks, cell, gap, cal_x):
        month_parts.append(
            f'<text x="{x}" y="{y_months}" class="font-mono" '
            f'style="font-size:9px; letter-spacing:0.12em; fill: var(--muted)">{month}</text>'
        )

    legend_swatches = []
    legend_x = gutter + cal_w - 120
    for i, level in enumerate(range(5)):
        legend_swatches.append(
            f'<rect x="{legend_x + i * 14}" y="{y_legend - 8}" width="11" height="11" '
            f'fill="{CONTRIB_COLORS[level]}"/>'
        )

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="statsTitle statsDesc">
  <title id="statsTitle">{esc(login)} GitHub stats</title>
  <desc id="statsDesc">Auto-updated stats, languages, and contribution activity</desc>
  <style>
{SHARED_STYLE}
  </style>
  <defs>
    <linearGradient id="statsWash" x1="0" y1="0" x2="{width}" y2="{height}" gradientUnits="userSpaceOnUse">
      <stop stop-color="var(--acid)" stop-opacity="0.08"/>
      <stop offset="1" stop-color="var(--night)" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <rect width="{width}" height="{height}" class="bg"/>
  <rect width="{width}" height="{height}" fill="url(#statsWash)"/>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" fill="none" stroke="var(--line)"/>

  <g class="rise d1">
    {diamond(gutter + 2, y_eyebrow - 4)}
    <text x="{gutter + 16}" y="{y_eyebrow}" class="font-mono" style="font-size:11px; fill: var(--acid)">01 / ACTIVITY</text>
    <text x="{gutter}" y="{y_title}" class="font-display" style="font-size:28px">GITHUB ACTIVITY</text>
    <text x="{width - gutter}" y="{y_title}" text-anchor="end" class="font-mono" style="font-size:10px; fill: var(--muted)">UPDATED DAILY</text>
  </g>

  {"".join(kpi_parts)}

  <g class="rise d2">
    <text x="{gutter}" y="{y_cols - 18}" class="font-mono" style="font-size:11px; fill: var(--acid)">OVERVIEW</text>
    <text x="470" y="{y_cols - 18}" class="font-mono" style="font-size:11px; fill: var(--acid)">TOP LANGUAGES</text>
  </g>

  {"".join(overview_parts)}
  {"".join(lang_parts)}

  <g class="rise d6">
    <text x="{gutter}" y="{y_cal_label}" class="font-mono" style="font-size:11px; fill: var(--ink)">CONTRIBUTION GRAPH · {total_contributions} LAST YEAR</text>
    {"".join(month_parts)}
    {"".join(cells)}
    <text x="{legend_x - 8}" y="{y_legend}" text-anchor="end" class="font-mono" style="font-size:9px; letter-spacing:0.12em; fill: var(--muted)">LESS</text>
    {"".join(legend_swatches)}
    <text x="{legend_x + 5 * 14 + 4}" y="{y_legend}" class="font-mono" style="font-size:9px; letter-spacing:0.12em; fill: var(--muted)">MORE</text>
  </g>
</svg>
"""


def build_repo_card_svg(repo, index):
    width, height = 430, 170
    name = repo["name"]
    desc_lines = wrap_text(repo.get("description"), 42, 2)
    lang = (repo.get("primaryLanguage") or {}).get("name")
    lang_color = (repo.get("primaryLanguage") or {}).get("color") or "#c8f750"
    topics = [
        node["topic"]["name"]
        for node in (repo.get("repositoryTopics") or {}).get("nodes") or []
        if node and node.get("topic")
    ]
    chips = []
    if lang:
        chips.append(lang)
    for topic in topics:
        if topic.lower() != (lang or "").lower() and len(chips) < 3:
            chips.append(topic.replace("-", " "))

    chip_parts = []
    x = 20
    for chip in chips[:3]:
        label = truncate(chip.upper(), 14)
        # Approximate mono width at 9px + letter-spacing.
        chip_w = max(42, 10 + len(label) * 7.2)
        if x + chip_w > width - 20:
            break
        chip_parts.append(
            f"""
      <g transform="translate({x}, 112)">
        <rect width="{chip_w:.1f}" height="20" fill="none" stroke="var(--acid)" stroke-opacity="0.45"/>
        <text x="{chip_w / 2:.1f}" y="13.5" text-anchor="middle" class="font-mono" style="font-size:9px; letter-spacing:0.12em; fill: var(--acid)">{esc(label)}</text>
      </g>"""
        )
        x += chip_w + 8

    desc_svg = []
    for i, line in enumerate(desc_lines):
        desc_svg.append(
            f'<text x="20" y="{78 + i * 16}" class="font-mono" '
            f'style="font-size:11px; letter-spacing:0.08em; fill: var(--muted)">{esc(line)}</text>'
        )

    idx = f"{index + 1:02d}"
    stars = repo.get("stargazerCount", 0)
    forks = repo.get("forkCount", 0)

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="repoTitle{idx} repoDesc{idx}">
  <title id="repoTitle{idx}">{esc(name)}</title>
  <desc id="repoDesc{idx}">{esc(repo.get("description") or "Pinned repository")}</desc>
  <style>
{SHARED_STYLE}
    .ghost {{
      font-family: "Syne", ui-sans-serif, system-ui, sans-serif;
      font-weight: 800;
      font-size: 72px;
      letter-spacing: -0.04em;
      fill: none;
      stroke: var(--line);
      stroke-width: 1.25;
    }}
  </style>

  <rect width="{width}" height="{height}" class="surface"/>
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" fill="none" stroke="var(--line)"/>

  <text x="{width - 18}" y="78" text-anchor="end" class="ghost fade d1">{idx}</text>

  <g class="rise d2">
    {diamond(24, 28)}
    <text x="36" y="32" class="font-mono" style="font-size:10px; fill: var(--acid)">0{index + 1} / FEATURED</text>
    <circle cx="20" cy="58" r="4" fill="{lang_color}"/>
    <text x="32" y="62" class="font-display" style="font-size:20px">{esc(truncate(name.upper(), 22))}</text>
    {"".join(desc_svg)}
  </g>

  <g class="rise d4">
    {"".join(chip_parts)}
    <text x="20" y="152" class="font-mono" style="font-size:10px; letter-spacing:0.14em; fill: var(--muted)">★ {stars}  ·  FORKS {forks}</text>
    <text x="{width - 20}" y="152" text-anchor="end" class="font-mono" style="font-size:14px; letter-spacing:0; fill: var(--acid)">↗</text>
    <rect x="20" y="{height - 2}" width="{width - 40}" height="1" fill="var(--acid)" class="underline-grow" style="animation-delay:0.25s"/>
  </g>
</svg>
"""


def write_repo_cards(pinned_repos):
    cards_dir = Path("cards")
    cards_dir.mkdir(exist_ok=True)
    keep = set()
    card_paths = []
    for i, repo in enumerate(pinned_repos):
        filename = f"{sanitize_filename(repo['name'])}.svg"
        keep.add(filename)
        path = cards_dir / filename
        path.write_text(build_repo_card_svg(repo, i), encoding="utf-8")
        card_paths.append((repo, f"cards/{filename}"))
        print(f"  wrote {path}")

    for existing in cards_dir.glob("*.svg"):
        if existing.name not in keep:
            existing.unlink()
            print(f"  removed stale {existing}")
    return card_paths


def build_pinned_markdown(card_paths):
    if not card_paths:
        return ""
    lines = [
        "",
        '<div align="center">',
        "",
        "### Featured repositories",
        "",
        "<table>",
    ]
    for i in range(0, len(card_paths), 2):
        lines.append("<tr>")
        for repo, path in card_paths[i : i + 2]:
            lines.append("<td width=\"50%\">")
            lines.append(
                f'<a href="{repo["url"]}">'
                f'<img src="{path}" alt="{esc(repo["name"])} repository card" width="100%"/>'
                f"</a>"
            )
            lines.append("</td>")
        if len(card_paths[i : i + 2]) == 1:
            lines.append("<td width=\"50%\"></td>")
        lines.append("</tr>")
    lines.extend(["</table>", "", "</div>", ""])
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

with open("profile_header.svg", "w", encoding="utf-8") as f:
    f.write(header_svg)

with open("github_stats.svg", "w", encoding="utf-8") as f:
    f.write(stats_svg)

print("Writing featured repository cards...")
card_paths = write_repo_cards(pinned)
sync_readme_pinned(build_pinned_markdown(card_paths))

print("Successfully generated profile_header.svg, github_stats.svg, cards/, and synced README.md")
