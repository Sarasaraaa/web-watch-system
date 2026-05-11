# GitHub Actions を使った「汎用 Webページ変更監視」の作り方

## 全体構成

```text
GitHub Actions
  ↓
Webページ取得
  ↓
HTML → プレーンテキスト変換
  ↓
前回データと比較
  ↓
変更があればRSS更新
  ↓
Power Automate が RSS を監視
  ↓
Teams通知
```

---

## 設定方法

### STEP 1：GitHub リポジトリを作る

### STEP 2：フォルダ構成を作る

最終的なフォルダ構成：

```text
web-watch-system
│
├─ .github
│   └─ workflows
│       └─ watch.yml
│
├─ config
│   └─ targets.json
│
├─ data
│   ├─ android_previous.txt
│   └─ ios_previous.txt
│
└─ docs
    ├─ android.xml
    └─ ios.xml
```

### STEP 3：監視対象設定ファイルを作る

ファイル：

```text
config/targets.json
```

### STEP 4：GitHub Actions を作る

ファイル：

```text
.github/workflows/watch.yml
```

### STEP 5：`watch.yml` の内容指定

### STEP 6：GitHub Pages を有効化

### STEP 7：RSS URL

### STEP 8：Power Automate 側
