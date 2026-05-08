# Web Watch System

# 目的

OSアップデートや Apple / Android Developer 情報の変更を毎日自動監視し、
Teams へ通知することで情報収集漏れを防止する。

---

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

# 現在の監視対象

## Android

| 名称        | URL                                                                                                                            | 比較方法  |
| --------- | ------------------------------------------------------------------------------------------------------------------------------ | ----- |
| Android バージョン情報 | [https://developer.android.com/about/versions?hl=ja](https://developer.android.com/about/versions?hl=ja)                       | 最終更新日 |
| Android15 | [https://developer.android.com/about/versions/15/summary?hl=ja](https://developer.android.com/about/versions/15/summary?hl=ja) | 最終更新日 |
| Android16 | [https://developer.android.com/about/versions/16/summary?hl=ja](https://developer.android.com/about/versions/16/summary?hl=ja) | 最終更新日 |

## Apple
| 名称                            | URL                                                                                                                          | 比較方法 |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ---- |
| iOS リリース情報                    | [https://support.apple.com/ja-jp/HT201222](https://support.apple.com/ja-jp/HT201222)                                         | 全文比較 |
| Appleのセキュリティリリース              | [https://support.apple.com/ja-jp/100100](https://support.apple.com/ja-jp/100100)                                             | 全文比較 |
| iOS_App Store Connect リリースノート | [https://developer.apple.com/app-store-connect/release-notes/](https://developer.apple.com/app-store-connect/release-notes/) | 全文比較 |
| Appleリリース情報                   | [https://developer.apple.com/news/releases/](https://developer.apple.com/news/releases/)                                     | 全文比較 |
| iOSの最新情報                      | [https://developer.apple.com/jp/ios/](https://developer.apple.com/jp/ios/)                                                   | 全文比較 |
| Apple_App Review              | [https://developer.apple.com/jp/distribute/app-review/](https://developer.apple.com/jp/distribute/app-review/)               | 全文比較 |
| AppleDeveloperNews            | [https://developer.apple.com/jp/news/](https://developer.apple.com/jp/news/)                                                 | 全文比較 |
| AppleDeveloperNews（近日適用開始の要件） | [https://developer.apple.com/jp/news/upcoming-requirements/](https://developer.apple.com/jp/news/upcoming-requirements/)     | 全文比較 |


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

# docs/index.html について

GitHub Pages を正常に公開するために必要です。
最低限、以下のようなHTMLを配置してください。

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>Web Watch System</title>
</head>
<body>
  <h1>Web Watch System</h1>
</body>
</html>
```

---

# docs/.nojekyll について

GitHub Pages の Jekyll 処理を無効化します。
このファイルが無い場合、GitHub Pages の build が失敗する場合があります。
空ファイルで問題ありません。

---

# 公開URL

## RSS

```text
https://Sarasaraaa.github.io/web-watch-system/rss.xml
```

## 差分HTML

```text
https://Sarasaraaa.github.io/web-watch-system/diffs/xxxx.html
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
https://Sarasaraaa.github.io/web-watch-system/rss.xml
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

# テスト方法

## GitHub Actions 手動実行

```text
Actions
→ Watch release information pages
→ Run workflow
```

---

## 変更通知テスト

以下ファイルを編集します。

```text
data/*.txt
```

末尾へ:

```text
TEST
```

を追加して commit 後、
workflow を再実行してください。

変更通知が発生します。

---

# 動作確認方法

## GitHub Actions 成功確認

```text
Actions
→ Watch release information pages
```

以下になっていれば正常です。

```text
✓ Success
```

---

## GitHub Pages 確認

```text
Settings
→ Pages
```

以下URLへアクセスしてください。

```text
https://Sarasaraaa.github.io/web-watch-system/rss.xml
```

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

## Apple Developer サイトで取得失敗する

### 原因

User-Agent が不足している可能性があります。

### 対応

watch.yml の fetch_html() 内 headers を確認してください。

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
* Discord通知
* エラー通知
* 監視失敗通知
* スクリーンショット比較
* Markdown差分
* 変更履歴保存
* カテゴリ別通知
* iOS/Android別通知
* Teams Adaptive Card 対応
* 通知レベル分類
* RSS分割
* Apple / Android 別通知
* CSVログ出力
* 変更統計グラフ
