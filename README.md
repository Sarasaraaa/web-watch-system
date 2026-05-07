# Web Watch System

Webページの変更を自動監視し、変更があった場合に Teams へ通知するシステムです。

以下を組み合わせて構成しています。

* GitHub Actions

  * 定期実行
  * Webページ取得
  * 差分比較
  * RSS生成
  * 差分HTML生成

* GitHub Pages

  * RSS公開
  * 差分HTML公開

* Power Automate

  * RSS監視
  * Teams通知

---

# システム構成

```text
GitHub Actions
  ↓
Webページ取得
  ↓
HTML → プレーンテキスト変換
  ↓
前回データ比較
  ↓
差分HTML生成
  ↓
RSS XML生成
  ↓
GitHub Pages公開
  ↓
Power Automate RSS監視
  ↓
Teams通知
```

---

# ディレクトリ構成

```text
web-watch-system/
├── .github/
│   └── workflows/
│       └── watch.yml
│
├── config/
│   └── targets.json
│
├── data/
│   └── *.txt
│
├── docs/
│   ├── .nojekyll
│   ├── index.html
│   ├── rss.xml
│   ├── latest_notification.txt
│   └── diffs/
│       └── *.html
│
└── README.md
```

---

# 監視対象設定

監視対象は以下ファイルで管理します。

```text
config/targets.json
```

## 設定例

```json
[
  {
    "name": "Android バージョン情報",
    "url": "https://developer.android.com/about/versions?hl=ja",
    "enabled": true,
    "check_last_updated_only": true
  },
  {
    "name": "iOS リリース情報",
    "url": "https://support.apple.com/ja-jp/HT201222",
    "enabled": true,
    "check_last_updated_only": false
  }
]
```

---

# targets.json パラメータ説明

| パラメータ                   | 説明                      |
| ----------------------- | ----------------------- |
| name                    | Teams通知に表示する名称          |
| url                     | 監視対象URL                 |
| enabled                 | true:監視する / false:監視しない |
| check_last_updated_only | true:最終更新日のみ比較          |

---

# check_last_updated_only について

## true の場合

ページ内の以下のような文言のみ比較します。

```text
最終更新日 2025-06-11 UTC。
```

### メリット

* 通知ノイズが少ない
* レイアウト変更で通知されない
* Android Developers 系におすすめ

---

## false の場合

HTMLから変換したプレーンテキスト全文を比較します。

### メリット

* 小さな変更も検知可能

### デメリット

* 広告変更
* 日付表示変更
* 微細なHTML変更

でも通知される可能性があります。

---

# GitHub Actions 設定

設定ファイル:

```text
.github/workflows/watch.yml
```

## 実行時間

```yaml
- cron: '30 0 * * *'
```

GitHub Actions は UTC 基準です。

| UTC   | JST   |
| ----- | ----- |
| 00:30 | 09:30 |

---

# GitHub Pages 設定

GitHub Repository:

```text
Settings
→ Pages
```

以下を設定します。

| 項目     | 設定値                  |
| ------ | -------------------- |
| Source | Deploy from a branch |
| Branch | main                 |
| Folder | /docs                |

---

# 公開URL

## RSS

```text
https://GitHubID.github.io/web-watch-system/rss.xml
```

## 差分HTML

```text
https://GitHubID.github.io/web-watch-system/diffs/xxxx.html
```

---

# Power Automate 設定

## RSSトリガー

```text
RSS
→ フィード項目が発行されたとき
```

RSS URL:

```text
https://GitHubID.github.io/web-watch-system/rss.xml
```

---

# Teams 通知設定

## アクション

```text
Microsoft Teams
→ チャットまたはチャネルでメッセージを投稿する
```

---

## Teams 通知本文例

```html
<p><strong>Webページ変更監視：変更を検知しました</strong></p>

<p>
監視対象ページに変更がありました。<br>
内容確認をお願いします。
</p>

<hr>

@{triggerOutputs()?['body/summary']}
```

---

# 差分HTMLについて

変更があった場合、以下へHTML差分が出力されます。

```text
docs/diffs/*.html
```

Teams通知からリンクで確認可能です。

---

# data ディレクトリについて

```text
data/*.txt
```

前回比較用データを保存します。

削除すると「初回実行扱い」になります。

---

# 初回実行について

初回実行時は比較対象が存在しないため、通知は行いません。

初回実行では:

* 前回比較用ファイル作成
* RSS初期化

のみ行います。

---

# よくあるエラー

## GitHub Pages build failure

### 原因

```text
/docs が存在しない
```

### 対応

以下ファイルを作成してください。

```text
docs/index.html
docs/.nojekyll
```

---

## Node.js 20 deprecation warning

### 原因

```yaml
uses: actions/checkout@v4
```

### 対応

```yaml
uses: actions/checkout@v5
```

へ変更してください。

---

# 推奨運用

## Android Developers 系

```json
"check_last_updated_only": true
```

推奨。

---

## Apple Release Notes 系

```json
"check_last_updated_only": false
```

推奨。

---

# 今後追加しやすい機能

* Slack通知
* Discord
