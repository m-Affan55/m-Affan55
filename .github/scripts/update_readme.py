#!/usr/bin/env python3
"""
Auto-update README.md with live GitHub stats.
Runs daily via GitHub Actions. No external dependencies required.
"""

import os
import re
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta


# --- Time Helpers ---

def get_pkt_now():
    """Return current datetime in Pakistan Standard Time (UTC+5)."""
    return datetime.now(timezone.utc) + timedelta(hours=5)


# --- GitHub API ---

def fetch_github_stats(username: str, token: str) -> dict:
    """Query GitHub GraphQL API for contribution stats."""
    now = get_pkt_now()
    year = now.year

    query = """
    query($username: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $username) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
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
        repositories(ownerAffiliations: OWNER, privacy: PUBLIC) {
          totalCount
        }
        followers { totalCount }
      }
    }
    """

    variables = {
        "username": username,
        "from": f"{year}-01-01T00:00:00Z",
        "to":   f"{year}-12-31T23:59:59Z",
    }

    payload = json.dumps({"query": query, "variables": variables}).encode()

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
            "User-Agent":    "GitHub-Actions-README-Updater/1.0",
        },
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


# --- Streak Calculation ---

def calculate_streak(weeks: list, today_str: str) -> int:
    """
    Count consecutive days with at least 1 contribution,
    going backwards from today. Skips today if no commit yet
    (giving until end of day).
    """
    all_days = []
    for week in weeks:
        for day in week["contributionDays"]:
            if day["date"] <= today_str:
                all_days.append(day)

    all_days.sort(key=lambda d: d["date"], reverse=True)

    streak = 0
    for i, day in enumerate(all_days):
        if day["contributionCount"] > 0:
            streak += 1
        else:
            # Allow skipping today if it has no contribution yet
            if i == 0:
                continue
            break

    return streak


# --- README Patch ---

START = "<!-- DYNAMIC-STATS:START -->"
END   = "<!-- DYNAMIC-STATS:END -->"


def build_dynamic_block(day_name, date_display, streak, total_contribs, total_commits):
    """Generate the markdown block to inject into README."""
    return f"""{START}
<div align="center">

<table>
<tr>
<td align="center" width="25%">
<h3>&#128197; {day_name}</h3>
<sub>{date_display}</sub>
</td>
<td align="center" width="25%">
<h3>&#128293; {streak} days</h3>
<sub>Current Streak</sub>
</td>
<td align="center" width="25%">
<h3>&#128202; {total_contribs}</h3>
<sub>Contributions this year</sub>
</td>
<td align="center" width="25%">
<h3>&#128187; {total_commits}</h3>
<sub>Commits this year</sub>
</td>
</tr>
</table>

<sup>&#9889; Auto-refreshed every 24h via GitHub Actions &nbsp;&#183;&nbsp; Live data from GitHub API</sup>

</div>
{END}"""


def patch_readme(content: str, block: str) -> str:
    """Replace existing dynamic block, or insert it just before the stats section."""
    if START in content:
        pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
        return pattern.sub(block, content)

    # First-time insertion
    anchor = '### `> neofetch --stats`'
    if anchor in content:
        return content.replace(anchor, f"{anchor}\n\n{block}")

    return content + f"\n\n{block}\n"


# --- Main ---

def main():
    username = os.environ.get("GITHUB_USERNAME", "m-Affan55")
    token    = os.environ.get("GITHUB_TOKEN", "")

    now          = get_pkt_now()
    today_str    = now.strftime("%Y-%m-%d")
    date_display = now.strftime("%B %d, %Y")
    day_name     = now.strftime("%A")

    total_contribs = "N/A"
    total_commits  = "N/A"
    streak         = 0

    try:
        data   = fetch_github_stats(username, token)
        user   = data["data"]["user"]
        col    = user["contributionsCollection"]
        cal    = col["contributionCalendar"]

        total_contribs = cal["totalContributions"]
        total_commits  = col["totalCommitContributions"]
        streak         = calculate_streak(cal["weeks"], today_str)

        print(f"Fetched: {total_contribs} contributions | {streak}-day streak")

    except Exception as exc:
        print(f"GitHub API error: {exc}")

    block = build_dynamic_block(day_name, date_display, streak, total_contribs, total_commits)

    # README is two levels up from .github/scripts/
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    readme_path = os.path.normpath(os.path.join(script_dir, "..", "..", "README.md"))

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    updated = patch_readme(content, block)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"README updated: {date_display} | streak: {streak} | contribs: {total_contribs}")


if __name__ == "__main__":
    main()
