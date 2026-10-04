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

既存stateに対する新リリースがあり、Webhookが未設定・空文字・空白の場合は、未配信のまま状態を維持して終了コード1を返します。初回bootstrapと変更なしは下表の例外です。

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

未設定での通常実行は観測専用モードではありません。実GitHub APIへアクセスし、初回はbootstrapでstateを書き込みます。既存stateと新タグがある場合は終了コード1となりstateを維持します。外部通信・通知・運用stateの変更なしで動作確認するには、後述の一時stateとHTTP stubによるテストを実行してください。

## 状態ファイル説明

`state/last_tag.txt` には最後に確認済みのタグを1行で保存します。ファイルが存在しない場合や空の場合は初回実行として扱い、通知せずに現在の最新タグを保存します。状態ファイルが記録したタグが取得範囲(10件)外まで遡る場合（例：状態ファイルが超古い値の場合）は、安全側で最新1件のみ通知して状態を同期し直します。

### 状態遷移の判断（Issue #6）

| 状態・結果 | state | 終了コード |
|---|---|---|
| 初回（不存在・空） | 通知せず最新タグを保存する既存bootstrap | 保存成功0／失敗1 |
| 既存タグから変更なし | 書込み・送信なし | 0 |
| 新タグあり、Webhook未設定・空・空白 | 旧stateを維持、送信しない | 1 |
| 新タグあり、HTTP非2xx・通信失敗・timeout | 旧stateを維持、次回再試行 | 1 |
| 新タグあり、Discordが2xxを返す | 最新通知対象タグを保存 | 保存成功0／失敗1 |
| state読込失敗 | 送信・書込みなし | 1 |

通知処理の成功はDiscord HTTP APIの2xx応答を意味し、利用者の閲覧・既読を保証しません。
通知対象なしの通知関数は送信不要として成功を返しますが、未設定による未配信は成功にしません。
失敗後にWebhookが復旧すると、旧タグ以降のリリースを再試行し、保存成功後の再実行では重複通知しません。

保存は同じディレクトリに一意な一時ファイルを作り、書込み・close完了後に置換します。
途中書込みや置換の失敗でも既存stateを切り詰めず、終了コード1で再試行可能にします。
ただしDiscord送信とstate保存・workflowのgit commit/pushは不可分ではありません。
送信後に保存やpushが失敗した場合は次回に重複通知し得ます。未配信を既読扱いするより再送を優先します。
電源断に対するディスク永続化や、複数ローカルプロセス間の排他までは保証しません。

この修正は既存stateの自動修復・過去通知の再送を行いません。過去の未設定実行で既にstateが進んだ場合、
この変更だけでは取りこぼしを回収できません。初回bootstrap・取得上限10件・範囲外なら最新1件・
prerelease/draft除外・日次スケジュールは維持します。

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


`tests/test_delivery_state.py` は一時ディレクトリ内のstateとHTTP stubを使い、未設定→復旧→成功→再実行、
HTTP 401/429/5xx・timeout・非2xx、bootstrap、state読込・途中書込・置換失敗を検証します。
実socketへの接続は失敗させ、実装が例外を捕捉してもテスト終了時に接続試行を検知します。
実GitHub/Discordへの疎通や閲覧の証拠にはなりません。既存の通知workflowや運用stateは変更しません。
