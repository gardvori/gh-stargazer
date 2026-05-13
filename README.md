# gh-stargazer ⭐

**GitHub Stargazer Trend Analyzer** — Analyze star growth trends for any GitHub repository, right from your terminal.

No external dependencies. Pure Python 3 stdlib only.

## Features

- 📊 **Daily/Weekly/Monthly** star activity breakdown
- 📈 **ASCII bar charts** — visualize trends in the terminal
- 🚀 **Spike detection** — find days with unusual star activity
- ⚖️ **Compare repos** — side-by-side comparison of multiple repos
- 👤 **Top stargazers** — see who starred recently
- 📤 **JSON output** — machine-readable output for scripting
- 🔑 **GitHub token support** — set `GITHUB_TOKEN` for higher rate limits

## Installation

```bash
# Clone and run
git clone https://github.com/gardvori/gh-stargazer.git
cd gh-stargazer
python3 gh_stargazer.py owner/repo

# Or just download the single file
curl -O https://raw.githubusercontent.com/gardvori/gh-stargazer/main/gh_stargazer.py
chmod +x gh_stargazer.py
./gh_stargazer.py owner/repo
```

## Usage

```bash
# Basic analysis (last 30 days)
gh-stargazer torvalls/linux

# Analyze last 90 days
gh-stargazer golang/go --days 90

# Compare two repos
gh-stargazer facebook/react --compare vuejs/vue

# Show top 10 recent stargazers
gh-stargazer microsoft/vscode --top 10

# JSON output for scripting
gh-stargazer rust-lang/rust --json

# With GitHub token (higher rate limits)
GITHUB_TOKEN=ghp_xxx gh-stargazer kubernetes/kubernetes --days 60
```

## Examples

```
📊 Analyzing torvalds/linux...
   Fetching stargazers (last 30 days)...

============================================================
  ⭐ torvalds/linux
============================================================
  📝 Linux kernel source tree
  📦 Language: C
  ⭐ Total Stars: 180,000
  📅 Created: 2011-09-04
  📈 Stars in last 30 days: 1,250

  📅 Daily Star Activity (last 30 days):
  ──────────────────────────────────────────────────
  2026-05-01  ████████████████████  52
  2026-05-02  ██████████████████░░  48
  2026-05-03  ██████████████░░░░░░  38
  ...

  📊 Average: 41.7 stars/day (active days)
  🏆 Best day: 2026-05-10 (89 stars)

  🚀 Star Spikes (>2.0x average):
     2026-05-10: 89 stars (2.1x avg)
```

## API Rate Limits

Without a GitHub token, you're limited to 60 requests/hour. With a token, 5,000/hour.

Set the `GITHUB_TOKEN` environment variable:
```bash
export GITHUB_TOKEN=ghp_your_token_here
```

## Requirements

- Python 3.7+
- No external packages needed (stdlib only)

## License

MIT — see [LICENSE](LICENSE)
