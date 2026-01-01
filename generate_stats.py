import os
import requests
import datetime
import time
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
USERNAME = os.environ.get("GITHUB_USERNAME")

if not GITHUB_TOKEN:
    raise Exception("GITHUB_TOKEN environment variable is required")

if not USERNAME:
    # Fallback: try to fetch the authenticated user if username not provided
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    r = requests.get("https://api.github.com/user", headers=headers)
    if r.status_code == 200:
        USERNAME = r.json()["login"]
    else:
        raise Exception("GITHUB_USERNAME environment variable is required or token is invalid")

print(f"Generating stats for user: {USERNAME}")

def run_query(query, variables):
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
    request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': variables}, headers=headers)
    if request.status_code == 200:
        return request.json()
    else:
        raise Exception(f"Query failed to run by returning code of {request.status_code}. {query}")

query = """
query($login: String!) {
  user(login: $login) {
    name
    login
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      pullRequestContributions(first: 100) {
        nodes {
          pullRequest {
            additions
            deletions
          }
        }
      }
    }
    repositoriesContributedTo(first: 1, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) {
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
    createdRepositories: repositories(first: 1, ownerAffiliations: OWNER, isFork: false) {
      totalCount
    }
    repositories(first: 100, ownerAffiliations: OWNER, orderBy: {direction: DESC, field: STARGAZERS}) {
      totalCount
      nodes {
        name
        owner {
          login
        }
        stargazers {
          totalCount
        }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
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

# Process Stats
total_commits = data["contributionsCollection"]["totalCommitContributions"] + data["contributionsCollection"]["restrictedContributionsCount"]
total_prs = data["pullRequests"]["totalCount"]
total_issues = data["issues"]["totalCount"]
total_contributed_to = data["repositoriesContributedTo"]["totalCount"]
followers = data["followers"]["totalCount"]
total_created = data["createdRepositories"]["totalCount"]

repositories = data["repositories"]["nodes"]
total_stars = sum(repo["stargazers"]["totalCount"] for repo in repositories)

# Language Stats
language_sizes = defaultdict(int)
language_colors = {}

for repo in repositories:
    if repo["languages"]["edges"]:
        for edge in repo["languages"]["edges"]:
            lang_name = edge["node"]["name"]
            size = edge["size"]
            color = edge["node"]["color"]
            language_sizes[lang_name] += size
            if color:
                language_colors[lang_name] = color

total_size = sum(language_sizes.values())
top_languages = sorted(language_sizes.items(), key=lambda x: x[1], reverse=True)[:6]

# Generate SVG
svg_width = 450
svg_height = 260
padding = 25

col_off = 150

svg_content = f"""
<svg width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}" fill="none" xmlns="http://www.w3.org/2000/svg">
    <style>
        :root {{
            --bg-color: #ffffff;
            --stroke-color: #e1e4e8;
            --text-color: #24292e;
            --secondary-text-color: #586069;
            --accent-color: #0366d6;
            --icon-color: #586069;
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg-color: #0d1117;
                --stroke-color: #30363d;
                --text-color: #c9d1d9;
                --secondary-text-color: #8b949e;
                --accent-color: #58a6ff;
                --icon-color: #8b949e;
            }}
        }}
        
        .bg {{ fill: var(--bg-color); stroke: var(--stroke-color); stroke-width: 1px; }}
        .title {{ font: 600 18px 'Segoe UI', Ubuntu, Sans-Serif; fill: var(--accent-color); }}
        .stat-label {{ font: 400 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: var(--text-color); }}
        .stat-value {{ font: 600 14px 'Segoe UI', Ubuntu, Sans-Serif; fill: var(--text-color); }}
        .lang-label {{ font: 400 12px 'Segoe UI', Ubuntu, Sans-Serif; fill: var(--secondary-text-color); }}
        
        /* Animations */
        @keyframes slideIn {{
            from {{ transform: translateX(-20px); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}
        
        .slide-in {{
            animation: slideIn 0.5s ease-out forwards;
            opacity: 0; /* Start hidden */
        }}
        
        .delay-1 {{ animation-delay: 0.1s; }}
        .delay-2 {{ animation-delay: 0.2s; }}
        .delay-3 {{ animation-delay: 0.3s; }}
        .delay-4 {{ animation-delay: 0.4s; }}
        .delay-5 {{ animation-delay: 0.5s; }}
        .delay-6 {{ animation-delay: 0.6s; }}
        .delay-7 {{ animation-delay: 0.7s; }}
        .delay-8 {{ animation-delay: 0.8s; }}
    </style>
    
    <rect x="0.5" y="0.5" rx="6" height="{svg_height - 1}" width="{svg_width - 1}" class="bg"/>
    
    <text x="{padding}" y="{padding + 10}" class="title slide-in">{USERNAME}'s GitHub Stats</text>
    
    <!-- Stats Column -->
    <g transform="translate({padding}, {padding + 45})">
        <g transform="translate(0, 0)">
            <g class="slide-in delay-1">
                <text x="0" y="10" class="stat-label">Total Stars:</text>
                <text x="{col_off}" y="10" class="stat-value">{total_stars}</text>
            </g>
        </g>
        <g transform="translate(0, 30)">
            <g class="slide-in delay-2">
                <text x="0" y="10" class="stat-label">Commits (Year):</text>
                <text x="{col_off}" y="10" class="stat-value">{total_commits}</text>
            </g>
        </g>
        <g transform="translate(0, 60)">
            <g class="slide-in delay-3">
                <text x="0" y="10" class="stat-label">Total PRs:</text>
                <text x="{col_off}" y="10" class="stat-value">{total_prs}</text>
            </g>
        </g>
        <g transform="translate(0, 90)">
            <g class="slide-in delay-4">
                <text x="0" y="10" class="stat-label">Total Issues:</text>
                <text x="{col_off}" y="10" class="stat-value">{total_issues}</text>
            </g>
        </g>
        <g transform="translate(0, 120)">
            <g class="slide-in delay-5">
                <text x="0" y="10" class="stat-label">Contributed to:</text>
                <text x="{col_off}" y="10" class="stat-value">{total_contributed_to}</text>
            </g>
        </g>
        <g transform="translate(0, 150)">
            <g class="slide-in delay-6">
                <text x="0" y="10" class="stat-label">Repos Created:</text>
                <text x="{col_off}" y="10" class="stat-value">{total_created}</text>
            </g>
        </g>
    </g>

    <!-- Languages Column -->
    <g transform="translate({svg_width / 2 + 20}, {padding + 45})">
        <text x="0" y="-10" class="stat-label slide-in delay-1" style="font-weight: 600;">Top Languages</text>
"""

for i, (lang, size) in enumerate(top_languages):
    percentage = (size / total_size) * 100
    color = language_colors.get(lang, "#ccc")
    y_pos = i * 30
    delay_class = f"delay-{i + 2}"
    
    svg_content += f"""
        <g transform="translate(0, {y_pos})">
            <g class="slide-in {delay_class}">
                <text x="0" y="10" class="lang-label">{lang}</text>
                <text x="100" y="10" class="lang-label" text-anchor="end">{percentage:.1f}%</text>
                <rect x="0" y="18" width="{percentage * 1.5}" height="6" fill="{color}" rx="3"/>
            </g>
        </g>
    """

svg_content += """
    </g>
</svg>
"""

with open("github_stats.svg", "w", encoding="utf-8") as f:
    f.write(svg_content)

print("Successfully generated github_stats.svg")
