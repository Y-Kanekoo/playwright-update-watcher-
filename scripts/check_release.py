"""GitHubの最新リリースを確認し、必要に応じてDiscordへ通知します。"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

DEFAULT_REPO = "microsoft/playwright"
DEFAULT_STATE_FILE = "state/last_tag.txt"
USER_AGENT = "playwright-update-watcher"
DISCORD_COLOR = 5814783


def fetch_latest_release(repo: str, token: str | None) -> dict[str, object]:
    """指定したGitHubリポジトリの最新リリース情報を取得します。"""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        data: object = json.loads(response.read().decode("utf-8"))

    if not isinstance(data, dict):
        raise ValueError("GitHub APIの応答形式が想定外です。")

    release: dict[str, object] = {}
    for key, value in data.items():
        if isinstance(key, str):
            release[key] = value
    return release


def read_last_tag(state_file: pathlib.Path) -> str | None:
    """状態ファイルから前回記録したタグを読み込みます。"""
    if not state_file.exists():
        return None

    last_tag = state_file.read_text(encoding="utf-8").strip()
    if not last_tag:
        return None
    return last_tag


def write_last_tag(state_file: pathlib.Path, tag_name: str) -> None:
    """状態ファイルへ最新タグを保存します。"""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(f"{tag_name}\n", encoding="utf-8")


def notify_discord(release: dict[str, object], webhook_url: str | None) -> bool:
    """Discord webhookへリリース通知を送信します。"""
    tag_value = release.get("tag_name")
    if not isinstance(tag_value, str) or not tag_value.strip():
        print("Discord通知に必要なタグ名が取得できませんでした。", file=sys.stderr)
        return False
    tag_name = tag_value.strip()

    if webhook_url is None or not webhook_url.strip():
        print(f"Discord webhook URLが未設定のため通知をスキップしました: {tag_name}")
        return True

    url_value = release.get("html_url")
    if not isinstance(url_value, str) or not url_value.strip():
        print("Discord通知に必要なリリースURLが取得できませんでした。", file=sys.stderr)
        return False
    release_url = url_value.strip()

    published_value = release.get("published_at")
    if not isinstance(published_value, str) or not published_value.strip():
        print("Discord通知に必要な公開日時が取得できませんでした。", file=sys.stderr)
        return False
    published_at = published_value.strip()

    name_value = release.get("name")
    release_name = name_value.strip() if isinstance(name_value, str) and name_value.strip() else tag_name

    embed: dict[str, object] = {
        "title": f"新しいリリース: {tag_name}",
        "url": release_url,
        "description": f"{release_name}\n公開日時: {published_at}",
        "color": DISCORD_COLOR,
    }
    payload: dict[str, object] = {
        "username": "Playwrightリリース監視",
        "embeds": [embed],
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(webhook_url.strip(), data=body)
    request.add_header("User-Agent", USER_AGENT)
    request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status_code = response.getcode()
    except urllib.error.HTTPError as error:
        print(f"Discord通知に失敗しました: HTTP {error.code} {error.reason}", file=sys.stderr)
        return False
    except urllib.error.URLError as error:
        print(f"Discord通知に失敗しました: {error.reason}", file=sys.stderr)
        return False

    if status_code < 200 or status_code >= 300:
        print(f"Discord通知に失敗しました: HTTP {status_code}", file=sys.stderr)
        return False

    print(f"Discordへ通知しました: {tag_name}")
    return True


def main() -> int:
    """リリース監視処理を実行します。"""
    repo = os.environ.get("TARGET_REPO", DEFAULT_REPO).strip() or DEFAULT_REPO
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    state_file_value = os.environ.get("STATE_FILE", DEFAULT_STATE_FILE).strip() or DEFAULT_STATE_FILE
    state_file = pathlib.Path(state_file_value)

    try:
        release = fetch_latest_release(repo, token)
    except urllib.error.HTTPError as error:
        print(f"GitHub APIの取得に失敗しました: HTTP {error.code} {error.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"GitHub APIの取得に失敗しました: {error.reason}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"GitHub APIの取得に失敗しました: {error}", file=sys.stderr)
        return 1

    tag_value = release.get("tag_name")
    if not isinstance(tag_value, str) or not tag_value.strip():
        print("GitHub APIの応答にタグ名が含まれていません。", file=sys.stderr)
        return 1
    tag_name = tag_value.strip()

    try:
        last_tag = read_last_tag(state_file)
    except OSError as error:
        print(f"状態ファイルの読み込みに失敗しました: {error}", file=sys.stderr)
        return 1

    if last_tag is None:
        try:
            write_last_tag(state_file, tag_name)
        except OSError as error:
            print(f"状態ファイルの書き込みに失敗しました: {error}", file=sys.stderr)
            return 1
        print(f"初回実行のため通知せず状態ファイルへ保存しました: {tag_name}")
        return 0

    if last_tag == tag_name:
        print(f"変更なし: {tag_name}")
        return 0

    if not notify_discord(release, webhook_url):
        return 1

    try:
        write_last_tag(state_file, tag_name)
    except OSError as error:
        print(f"状態ファイルの書き込みに失敗しました: {error}", file=sys.stderr)
        return 1

    print(f"新しいリリースを状態ファイルへ保存しました: {tag_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
