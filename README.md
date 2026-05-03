# Playwrightリリース監視

![Playwrightリリース監視](https://github.com/Y-Kanekoo/playwright-update-watcher-/actions/workflows/check-release.yml/badge.svg)
![ユニットテスト](https://github.com/Y-Kanekoo/playwright-update-watcher-/actions/workflows/test.yml/badge.svg)

## 概要

`microsoft/playwright` のGitHubリリースを日次で確認し、新しいタグを検知した場合にDiscord webhookへ通知するための小さな監視リポジトリです。

## 仕組み

GitHub Actionsが毎日JST 09:00に起動し、GitHub Releases APIから最新10件のリリースを取得します。前回記録したタグは state/last_tag.txt に保存され、前回タグ以降の新リリース全てを1メッセージで通知します。新しいタグを検知した場合はDiscordへ通知し、通知が成功した場合だけ状態ファイルを更新します。

## セットアップ

リポジトリのSecretsに `DISCORD_WEBHOOK_URL` を登録します。webhook URLが端末履歴やシェル履歴に残らないよう、`stdin` 経由での登録を推奨します。

```sh
echo "https://discord.com/api/webhooks/..." | gh secret set DISCORD_WEBHOOK_URL --repo <owner>/<repo>
```

未設定でも監視処理は動作しますが、Discord通知はスキップされます。

GitHub APIの認証にはActions標準の `GITHUB_TOKEN` を利用します。追加のトークンは不要です。

## 監視対象の変更方法

`.github/workflows/check-release.yml` の `TARGET_REPO` を `owner/repo` 形式で変更します。ローカル実行時は環境変数 `TARGET_REPO` でも上書きできます。

監視対象を変更したあとは、`state/last_tag.txt` を空にしてからpushすると、変更後リポジトリの最新タグから監視を再開できます（旧リポジトリのタグが残っていると正しく動作しません）。

## 手動実行

GitHub Actionsの `Playwrightリリース監視` ワークフローを開き、`workflow_dispatch` から手動実行できます。

## ローカル実行

次のコマンドでローカルから確認できます。

```sh
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." python scripts/check_release.py
```

通知なしで動作確認する場合は、`DISCORD_WEBHOOK_URL` を設定せずに実行します。

## 状態ファイル説明

`state/last_tag.txt` には最後に確認済みのタグを1行で保存します。ファイルが存在しない場合や空の場合は初回実行として扱い、通知せずに現在の最新タグを保存します。状態ファイルが記録したタグが取得範囲(10件)外まで遡る場合（例：状態ファイルが超古い値の場合）は、安全側で最新1件のみ通知して状態を同期し直します。

## Discord通知の内容

各通知メッセージには以下の情報を含みます:
- リリースタグ名
- 公開日時（JST形式：YYYY-MM-DD HH:MM JST）
- changelog本文（先頭1500文字。長い場合は切り詰め）

ベータ版（prerelease）やドラフトのリリースは通知対象外です。

## ユニットテスト

Python標準の `unittest` で記述しています。ローカル実行は次のとおりです。

```sh
python3 -m unittest discover -s tests -v
```

push と pull request 時に GitHub Actions でも自動実行されます。
