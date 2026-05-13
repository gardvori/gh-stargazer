#!/usr/bin/env python3
"""
gh-stargazer — GitHub Stargazer Trend Analyzer

Analyze star growth trends for any GitHub repository.
No external dependencies — uses only Python stdlib.

Uses the GitHub Events API for efficient recent star data.

Usage:
    gh-stargazer owner/repo [--days 30] [--compare owner/repo2] [--json]
    gh-stargazer --help

Examples:
    gh-stargazer torvalds/linux
    gh-stargazer golang/go --days 90
    gh-stargazer facebook/react --compare vuejs/vue
    gh-stargazer microsoft/vscode --json
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
    import os
    return os.environ.get(TOKEN_ENV, "")


def api_get(url, token=""):
    """Make a GET request to GitHub API."""
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "gh-stargazer/1.0")
    if token:
        req.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            link_header = resp.headers.get("Link", "")
            data = json.loads(resp.read().decode())
            return data, link_header
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Error: Repository not found or not accessible.", file=sys.stderr)
            sys.exit(1)
        elif e.code == 403:
            body = e.read().decode() if e.fp else ""
            if "rate limit" in body.lower():
                print(f"Error: API rate limit exceeded. Set {TOKEN_ENV} env var.", file=sys.stderr)
            else:
                print(f"Error: Forbidden (403). Check your token permissions.", file=sys.stderr)
            sys.exit(1)
        elif e.code == 422:
            # GitHub returns 422 for pages beyond available range — not an error for us
            raise StopIteration
        else:
            print(f"Error: HTTP {e.code}: {e.reason}", file=sys.stderr)
            sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Error: {e.reason}", file=sys.stderr)
        sys.exit(1)


def get_last_page_num(link_header):
    """Extract the last page number from a Link header."""
    if not link_header:
        return 1
    for part in link_header.split(","):
        if 'rel="last"' in part:
            url_part = part.split(";")[0].strip().strip("<>")
            if "page=" in url_part:
                try:
                    return int(url_part.split("page=")[1].split("&")[0])
                except (ValueError, IndexError):
                    pass
    return 1


def fetch_star_events(owner, repo, token="", days=30, max_pages=15):
    """
    Fetch star events using the GitHub Events API.
    This is much more efficient than the stargazers endpoint for recent data.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stars = []

    # First page to get total pages
    url = f"{GITHUB_API}/repos/{owner}/{repo}/events?per_page=100&page=1"
    data, link_header = api_get(url, token)

    if not data:
        return stars

    last_page = get_last_page_num(link_header)
    pages_to_fetch = min(last_page, max_pages)

    # Process first page
    for event in data:
        if event.get("type") == "WatchEvent":
            event_time = event.get("created_at", "")
            if event_time:
                dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                if dt >= cutoff:
                    actor = event.get("actor", {})
                    stars.append({
                        "user": actor.get("login", "unknown"),
                        "starred_at": event_time,
                    })

    # Fetch more pages if needed
    for page in range(2, pages_to_fetch + 1):
        url = f"{GITHUB_API}/repos/{owner}/{repo}/events?per_page=100&page={page}"
        try:
            data, _ = api_get(url, token)
        except StopIteration:
            break
        except SystemExit:
            break

        if not data:
            break

        for event in data:
            if event.get("type") == "WatchEvent":
                event_time = event.get("created_at", "")
                if event_time:
                    dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                    if dt >= cutoff:
                        actor = event.get("actor", {})
                        stars.append({
                            "user": actor.get("login", "unknown"),
                            "starred_at": event_time,
                        })

        # If the last event on this page is before cutoff, we can stop
        if data and data[-1].get("created_at", "") < cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"):
            break

    return stars


def fetch_repo_info(owner, repo, token=""):
    """Fetch repository metadata."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}"
    data, _ = api_get(url, token)
    return data if isinstance(data, dict) else {}


def aggregate_by_period(stars, period="day"):
    """Aggregate stars by day, week, or month."""
    counts = defaultdict(int)
    for star in stars:
        dt = datetime.fromisoformat(star["starred_at"].replace("Z", "+00:00"))
        if period == "day":
            key = dt.strftime("%Y-%m-%d")
        elif period == "week":
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
    if avg < 1:
        return []
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


def analyze_repo(owner, repo, days=30, token="", verbose=True, max_pages=15):
    """Analyze a single repository's star trends."""
    if verbose:
        print(f"\n📊 Analyzing {owner}/{repo}...")
        print(f"   Fetching star events (last {days} days, max {max_pages} pages)...")

    stars = fetch_star_events(owner, repo, token, days, max_pages)
    repo_info = fetch_repo_info(owner, repo, token)

    total_stars = repo_info.get("stargazers_count", 0)
    description = repo_info.get("description", "N/A")
    language = repo_info.get("language", "N/A")
    created_at = repo_info.get("created_at", "N/A")
    forks = repo_info.get("forks_count", "N/A")

    if not stars:
        if verbose:
            print(f"\n{'='*60}")
            print(f"  ⭐ {owner}/{repo}")
            print(f"{'='*60}")
            if description != "N/A":
                print(f"  📝 {description}")
            print(f"  📦 Language: {language}")
            print(f"  ⭐ Total Stars: {total_stars:,}")
            print(f"  📈 Stars in last {days} days: 0")
            print(f"  (No star activity in the analyzed window)")
        return {
            "owner": owner, "repo": repo,
            "total_stars": total_stars,
            "recent_stars": 0, "daily_avg": 0,
            "daily": {}, "weekly": {}, "monthly": {}, "spikes": [],
        }

    daily = aggregate_by_period(stars, "day")
    weekly = aggregate_by_period(stars, "week")
    monthly = aggregate_by_period(stars, "month")
    spikes = detect_spikes(daily)

    if verbose:
        print(f"\n{'='*60}")
        print(f"  ⭐ {owner}/{repo}")
        print(f"{'='*60}")
        if description != "N/A":
            print(f"  📝 {description}")
        if isinstance(forks, int):
            print(f"  📦 Language: {language}  |  🍴 Forks: {forks:,}")
        else:
            print(f"  📦 Language: {language}")
        print(f"  ⭐ Total Stars: {total_stars:,}")
        if created_at != "N/A":
            print(f"  📅 Created: {created_at[:10]}")
        print(f"  📈 Stars in last {days} days: {len(stars):,}")

        if daily:
            max_day_count = max(daily.values())
            print(f"\n  📅 Daily Star Activity (last {days} days):")
            print(f"  {'─'*50}")
            daily_items = list(daily.items())[-14:]
            for date, count in daily_items:
                bar = format_bar(count, max_day_count, 20)
                print(f"  {date}  {bar}  {count}")

            num_active_days = len(daily)
            avg_daily = len(stars) / max(num_active_days, 1)
            print(f"\n  📊 Average: {avg_daily:.1f} stars/day ({num_active_days} active days)")
            if daily:
                best_day = max(daily, key=daily.get)
                print(f"  🏆 Best day: {best_day} ({daily[best_day]} stars)")

        if spikes:
            print(f"\n  🚀 Star Spikes (>2.0x average):")
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
        "recent_stars": len(stars),
        "daily_avg": round(len(stars) / max(len(daily), 1), 1),
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
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON")
    parser.add_argument("--max-pages", type=int, default=15, help="Max API pages to fetch (default: 15)")

    args = parser.parse_args()

    token = get_token()

    parts = args.repo.split("/")
    if len(parts) != 2:
        print("Error: Repository must be in 'owner/repo' format.", file=sys.stderr)
        sys.exit(1)

    owner, repo = parts
    result = analyze_repo(owner, repo, args.days, token, verbose=not args.json_output, max_pages=args.max_pages)
    results = [result]

    if args.compare:
        for comp_repo in args.compare:
            parts = comp_repo.split("/")
            if len(parts) != 2:
                print(f"Warning: Skipping invalid repo format: {comp_repo}", file=sys.stderr)
                continue
            comp_result = analyze_repo(parts[0], parts[1], args.days, token, verbose=not args.json_output, max_pages=args.max_pages)
            results.append(comp_result)

        if not args.json_output and len(results) > 1:
            compare_repos(results)

    if args.json_output:
        output = results[0] if len(results) == 1 else results
        print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
