# Playwrightリリース監視

## 概要

`microsoft/playwright` のGitHubリリースを日次で確認し、新しいタグを検知した場合にDiscord webhookへ通知するための小さな監視リポジトリです。

## 仕組み

GitHub Actionsが毎日JST 09:00に起動し、GitHub Releases APIから最新リリースを取得します。前回記録したタグは `state/last_tag.txt` に保存され、同じタグの場合は通知しません。新しいタグを検知した場合はDiscordへ通知し、通知が成功した場合だけ状態ファイルを更新します。

## セットアップ

リポジトリのSecretsに `DISCORD_WEBHOOK_URL` を登録します。webhook URLが端末履歴やシェル履歴に残らないよう、`stdin` 経由での登録を推奨します。

```sh
echo "https://discord.com/api/webhooks/..." | gh secret set DISCORD_WEBHOOK_URL --repo <owner>/<repo>
```

未設定でも監視処理は動作しますが、Discord通知はスキップされます。

GitHub APIの認証にはActions標準の `GITHUB_TOKEN` を利用します。追加のトークンは不要です。

## 監視対象の変更方法

`.github/workflows/check-release.yml` の `TARGET_REPO` を `owner/repo` 形式で変更します。ローカル実行時は環境変数 `TARGET_REPO` でも上書きできます。

## 手動実行

GitHub Actionsの `Playwrightリリース監視` ワークフローを開き、`workflow_dispatch` から手動実行できます。

## ローカル実行

次のコマンドでローカルから確認できます。

```sh
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..." python scripts/check_release.py
```

通知なしで動作確認する場合は、`DISCORD_WEBHOOK_URL` を設定せずに実行します。

## 状態ファイル説明

`state/last_tag.txt` には最後に確認済みのタグを1行で保存します。ファイルが存在しない場合や空の場合は初回実行として扱い、通知せずに現在の最新タグを保存します。
