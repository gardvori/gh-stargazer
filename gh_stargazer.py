#!/usr/bin/env python3
"""
gh-stargazer — GitHub Stargazer Trend Analyzer

Analyze star growth trends for any GitHub repository.
No external dependencies — uses only Python stdlib.

Usage:
    gh-stargazer owner/repo [--days 30] [--compare owner/repo2] [--top N] [--json]
    gh-stargazer --help

Examples:
    gh-stargazer torvalds/linux
    gh-stargazer golang/go --days 90
    gh-stargazer facebook/react --compare vuejs/vue
    gh-stargazer microsoft/vscode --top 10
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from collections import defaultdict


GITHUB_API = "https://api.github.com"
TOKEN_ENV = "GITHUB_TOKEN"


def get_token():
    """Get GitHub token from environment."""
    import os
    return os.environ.get(TOKEN_ENV, "")


def api_get(url, token=""):
    """Make a GET request to GitHub API with optional auth."""
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3.star+json")
    req.add_header("User-Agent", "gh-stargazer/1.0")
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Error: Repository not found or not accessible.", file=sys.stderr)
            sys.exit(1)
        elif e.code == 403:
            print(f"Error: API rate limit exceeded. Set {TOKEN_ENV} env var.", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"Error: HTTP {e.code}: {e.reason}", file=sys.stderr)
            sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def fetch_stargazers(owner, repo, token="", max_pages=100):
    """Fetch stargazers with timestamps using GitHub API."""
    stars = []
    page = 1
    while page <= max_pages:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/stargazers?per_page=100&page={page}"
        data = api_get(url, token)
        if not data:
            break
        for entry in data:
            if "starred_at" in entry:
                stars.append({
                    "user": entry["user"]["login"],
                    "starred_at": entry["starred_at"],
                })
        if len(data) < 100:
            break
        page += 1
    return stars


def fetch_repo_info(owner, repo, token=""):
    """Fetch repository metadata."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "gh-stargazer/1.0")
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {}


def aggregate_by_period(stars, period="day"):
    """Aggregate stars by day, week, or month."""
    counts = defaultdict(int)
    for star in stars:
        dt = datetime.fromisoformat(star["starred_at"].replace("Z", "+00:00"))
        if period == "day":
            key = dt.strftime("%Y-%m-%d")
        elif period == "week":
            # ISO week
            key = dt.strftime("%Y-W%W")
        elif period == "month":
            key = dt.strftime("%Y-%m")
        else:
            key = dt.strftime("%Y-%m-%d")
        counts[key] += 1
    return dict(sorted(counts.items()))


def detect_spikes(daily_counts, threshold=2.0):
    """Detect days with unusual star activity (spikes)."""
    if len(daily_counts) < 3:
        return []
    values = list(daily_counts.values())
    avg = sum(values) / len(values)
    spikes = []
    for date, count in daily_counts.items():
        if count > avg * threshold and count > 2:
            spikes.append({"date": date, "count": count, "multiplier": round(count / avg, 1)})
    return spikes


def format_table(headers, rows, max_col_width=20):
    """Format data as a simple text table."""
    if not rows:
        return "  No data available."
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], min(len(str(cell)), max_col_width))
    lines = []
    header_line = "  ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
    lines.append(header_line)
    lines.append("  ".join("-" * col_widths[i] for i in range(len(headers))))
    for row in rows:
        lines.append("  ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def format_bar(value, max_value, width=30):
    """Create a simple ASCII bar."""
    if max_value == 0:
        return ""
    filled = int((value / max_value) * width)
    return "█" * filled + "░" * (width - filled)


def analyze_repo(owner, repo, days=30, token="", verbose=True):
    """Analyze a single repository's star trends."""
    if verbose:
        print(f"\n📊 Analyzing {owner}/{repo}...")
        print(f"   Fetching stargazers (last {days} days)...")

    stars = fetch_stargazers(owner, repo, token)
    repo_info = fetch_repo_info(owner, repo, token)

    if not stars:
        print("   No stargazer data available (repo may have no stars or API limit reached).")
        return {}

    # Filter by date range
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent_stars = [
        s for s in stars
        if datetime.fromisoformat(s["starred_at"].replace("Z", "+00:00")) >= cutoff
    ]

    total_stars = repo_info.get("stargazers_count", len(stars))
    description = repo_info.get("description", "N/A")
    language = repo_info.get("language", "N/A")
    created_at = repo_info.get("created_at", "N/A")

    daily = aggregate_by_period(recent_stars, "day")
    weekly = aggregate_by_period(recent_stars, "week")
    monthly = aggregate_by_period(recent_stars, "month")
    spikes = detect_spikes(daily)

    if verbose:
        print(f"\n{'='*60}")
        print(f"  ⭐ {owner}/{repo}")
        print(f"{'='*60}")
        if description != "N/A":
            print(f"  📝 {description}")
        print(f"  📦 Language: {language}")
        print(f"  ⭐ Total Stars: {total_stars:,}")
        if created_at != "N/A":
            print(f"  📅 Created: {created_at[:10]}")
        print(f"  📈 Stars in last {days} days: {len(recent_stars):,}")

        if daily:
            max_day_count = max(daily.values()) if daily else 0
            print(f"\n  📅 Daily Star Activity (last {days} days):")
            print(f"  {'─'*50}")
            for date, count in list(daily.items())[-14:]:  # Last 14 days
                bar = format_bar(count, max_day_count, 20)
                print(f"  {date}  {bar}  {count}")

            avg_daily = len(recent_stars) / max(len(daily), 1)
            print(f"\n  📊 Average: {avg_daily:.1f} stars/day (active days)")
            if len(daily) > 0:
                best_day = max(daily, key=daily.get)
                print(f"  🏆 Best day: {best_day} ({daily[best_day]} stars)")

        if spikes:
            print(f"\n  🚀 Star Spikes (>{2.0}x average):")
            for spike in spikes[:5]:
                print(f"     {spike['date']}: {spike['count']} stars ({spike['multiplier']}x avg)")

        if monthly and len(monthly) > 1:
            max_month_count = max(monthly.values())
            print(f"\n  📆 Monthly Breakdown:")
            print(f"  {'─'*40}")
            for month, count in monthly.items():
                bar = format_bar(count, max_month_count, 20)
                print(f"  {month}  {bar}  {count}")

    return {
        "owner": owner,
        "repo": repo,
        "total_stars": total_stars,
        "recent_stars": len(recent_stars),
        "daily_avg": round(len(recent_stars) / max(len(daily), 1), 1),
        "daily": daily,
        "weekly": weekly,
        "monthly": monthly,
        "spikes": spikes,
    }


def compare_repos(results):
    """Compare multiple repositories side by side."""
    if len(results) < 2:
        return
    print(f"\n{'='*60}")
    print(f"  ⚖️  Comparison")
    print(f"{'='*60}")
    headers = ["Metric"] + [f"{r['owner']}/{r['repo']}" for r in results]
    rows = []
    rows.append(["Total Stars"] + [f"{r['total_stars']:,}" for r in results])
    rows.append(["Recent Stars"] + [f"{r['recent_stars']:,}" for r in results])
    rows.append(["Daily Avg"] + [f"{r['daily_avg']}" for r in results])
    rows.append(["Spikes"] + [str(len(r["spikes"])) for r in results])
    print(format_table(headers, rows))


def main():
    parser = argparse.ArgumentParser(
        description="gh-stargazer — GitHub Stargazer Trend Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  gh-stargazer torvalds/linux
  gh-stargazer golang/go --days 90
  gh-stargazer facebook/react --compare vuejs/vue
  gh-stargazer microsoft/vscode --json
        """,
    )
    parser.add_argument("repo", help="Repository in owner/repo format")
    parser.add_argument("--days", type=int, default=30, help="Number of days to analyze (default: 30)")
    parser.add_argument("--compare", action="append", help="Additional repo to compare (owner/repo)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--top", type=int, help="Show top N recent stargazers")

    args = parser.parse_args()

    token = get_token()

    # Parse main repo
    parts = args.repo.split("/")
    if len(parts) != 2:
        print("Error: Repository must be in 'owner/repo' format.", file=sys.stderr)
        sys.exit(1)

    owner, repo = parts
    result = analyze_repo(owner, repo, args.days, token, verbose=not args.json)
    results = [result]

    # Compare repos
    if args.compare:
        for comp_repo in args.compare:
            parts = comp_repo.split("/")
            if len(parts) != 2:
                print(f"Warning: Skipping invalid repo format: {comp_repo}", file=sys.stderr)
                continue
            comp_result = analyze_repo(parts[0], parts[1], args.days, token, verbose=not args.json)
            results.append(comp_result)

        if not args.json and len(results) > 1:
            compare_repos(results)

    # Show top stargazers
    if args.top and result:
        print(f"\n  👤 Top {args.top} Recent Stargazers:")
        stars = fetch_stargazers(owner, repo, token)
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
        recent = [
            s for s in stars
            if datetime.fromisoformat(s["starred_at"].replace("Z", "+00:00")) >= cutoff
        ]
        for i, star in enumerate(recent[:args.top]):
            print(f"     {i+1}. @{star['user']} — {star['starred_at'][:10]}")

    # JSON output
    if args.json:
        output = results[0] if len(results) == 1 else results
        # Remove non-serializable items
        print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
