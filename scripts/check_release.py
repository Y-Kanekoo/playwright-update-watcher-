"""Fetch the latest release of the target GitHub repository.

This is the PR #1 skeleton: it only fetches and prints the latest release.
New-release detection, Discord notification, and AI summary are added in
later PRs.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_REPO = "microsoft/playwright"
USER_AGENT = "playwright-update-watcher"


def fetch_latest_release(repo: str, token: str | None) -> dict:
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    request = urllib.request.Request(url)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("User-Agent", USER_AGENT)
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def main() -> int:
    repo = os.environ.get("TARGET_REPO", DEFAULT_REPO)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")

    try:
        release = fetch_latest_release(repo, token)
    except urllib.error.HTTPError as error:
        print(f"HTTP error fetching latest release: {error.code} {error.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"Network error fetching latest release: {error.reason}", file=sys.stderr)
        return 1

    print(f"repo={repo}")
    print(f"tag={release.get('tag_name')}")
    print(f"name={release.get('name')}")
    print(f"published_at={release.get('published_at')}")
    print(f"html_url={release.get('html_url')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
