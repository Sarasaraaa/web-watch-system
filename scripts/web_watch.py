# ==================================================
          # 必要ライブラリ読み込み
          # ==================================================

          # OS操作
import os

          # 正規表現
          import re

          # HTMLエスケープ処理
          import html

          # JSON読み込み
          import json

          # ハッシュ生成
          import hashlib

          # 差分生成
          import difflib

          # Webアクセス
          import urllib.request

          # Android Developers の取得で curl を利用するため
          import subprocess

          # 日時生成
          from datetime import datetime, timezone

          import http.cookiejar

          # ==================================================
          # config/targets.json を読み込み
          #
          # 監視対象URLをJSONで管理する
          #
          # 例：
          # [
          #   {
          #     "name": "Android バージョン情報",
          #     "url": "https://developer.android.com/about/versions?hl=ja",
          #     "enabled": true,
          #     "check_last_updated_only": true
          #   }
          # ]
          # ==================================================

          with open("config/targets.json", "r", encoding="utf-8") as f:
              PAGES = json.load(f)

          # ==================================================
          # ディレクトリ定義
          # ==================================================

          # 前回比較用テキスト保存先
          DATA_DIR = "data"

          # GitHub Pages 公開用ディレクトリ
          DOCS_DIR = "docs"

          # 差分HTML保存先
          DIFF_DIR = os.path.join(DOCS_DIR, "diffs")

          # ディレクトリ作成
          os.makedirs(DATA_DIR, exist_ok=True)
          os.makedirs(DOCS_DIR, exist_ok=True)
          os.makedirs(DIFF_DIR, exist_ok=True)

          # ==================================================
          # 共通関数
          # ==================================================

          def safe_filename(text):
              """
              URLを安全なファイル名へ変換する

              URLには:
              /
              :
              ?
              などファイル名に使えない文字が含まれるため、
              SHA256ハッシュ値へ変換する
              """

              return hashlib.sha256(
                  text.encode("utf-8")
              ).hexdigest()[:16]


          def fetch_html(url):
              """
              WebページHTML取得

              Android系サイトはリダイレクト時にCookieを要求することがあるため、
              CookieJar を使ってリダイレクト先の状態を保持する。
              """

              # =====================================================
              # 【追加】
              # Android Developers は curl で取得する
              # =====================================================
              if "developer.android.com" in url:

              print("Using curl:", url)

                result = subprocess.run(
                    [
                        "curl",
                        "-L",                 # リダイレクト追従
                        "-A",
                        (
                            "Mozilla/5.0 "
                            "(Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 "
                            "(KHTML, like Gecko) "
                            "Chrome/122.0.0.0 Safari/537.36"
                        ),
                        url
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8"
                )

                if result.returncode != 0:
                    raise Exception(result.stderr)

                return result.stdout

                # =====================================================
                # Apple系は従来どおり urllib
                # =====================================================

                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 "
                            "(Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 "
                            "(KHTML, like Gecko) "
                            "Chrome/122.0.0.0 Safari/537.36"
                        )
                    }
                )

                with urllib.request.urlopen(
                    req,
                    timeout=30
                ) as res:

                    return res.read().decode(
                        "utf-8",
                        errors="ignore"
                    )


          def html_to_text(raw_html):
              """
              HTML → プレーンテキスト変換

              比較時に不要な:
              - script
              - style
              - noscript
              を除去する
              """

              # script除去
              text = re.sub(
                  r"<script[\s\S]*?</script>",
                  "",
                  raw_html,
                  flags=re.I
              )

              # style除去
              text = re.sub(
                  r"<style[\s\S]*?</style>",
                  "",
                  text,
                  flags=re.I
              )

              # noscript除去
              text = re.sub(
                  r"<noscript[\s\S]*?</noscript>",
                  "",
                  text,
                  flags=re.I
              )

              # HTMLタグを改行へ変換
              text = re.sub(
                  r"<[^>]+>",
                  "\n",
                  text
              )

              # HTMLエスケープ解除
              #
              # 例:
              # &amp; → &
              #
              text = html.unescape(text)

              # 改行コード統一
              text = re.sub(
                  r"\r\n|\r",
                  "\n",
                  text
              )

              # 連続空白整理
              text = re.sub(
                  r"[ \t]+",
                  " ",
                  text
              )

              # 空行整理
              text = re.sub(
                  r"\n\s*\n+",
                  "\n",
                  text
              )

              # 行ごとに前後空白削除
              lines = [
                  line.strip()
                  for line in text.splitlines()
              ]

              # 空行除去
              lines = [
                  line
                  for line in lines
                  if line
              ]

              return "\n".join(lines)


          def extract_last_updated(text):
              """
              最終更新日らしき文言を抽出

              通知ノイズを減らすため、
              ページ全文比較ではなく
              最終更新日だけ比較したい場合に利用する
              """

              patterns = [

                  # ===============================
                  # Android Developer
                  # ===============================

                  r"最終更新日\s*[0-9]{4}-[0-9]{2}-[0-9]{2}\s*UTC。",
                  r"最終更新日\s*[0-9]{4}-[0-9]{2}-[0-9]{2}\s*UTC",

                  # ===============================
                  # Apple Developer
                  # ===============================
                  r"Published\s+[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}",
                  r"Released\s+[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}",
                  r"Updated\s+[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}",
                  r"Updated\s*[A-Za-z]+\s+\d{1,2},\s+\d{4}",
                  r"Last updated\s+[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}",
                  r"Last updated\s*[A-Za-z]+\s+\d{1,2},\s+\d{4}",

                  # ===============================
                  # Apple Support 日本語
                  # ===============================
                  r"公開日[:：]?\s*[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日",
                  r"更新日[:：]?\s*[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日",
                  
              ]

              

              for pattern in patterns:

                  match = re.search(
                      pattern,
                      text
                  )

                  if match:
                      return match.group(0)

              return "検出できませんでした"


          def make_diff_html(
              page_name,
              url,
              old_text,
              new_text,
              last_updated
          ):
              """
              HTML差分生成

              Teams通知に全文を載せると
              非常に見づらくなるため、
              差分HTMLをGitHub Pagesで公開する
              """

              old_lines = old_text.splitlines()
              new_lines = new_text.splitlines()

              diff_html = difflib.HtmlDiff(
                  wrapcolumn=100
              ).make_file(
                  old_lines,
                  new_lines,
                  fromdesc="前回取得内容",
                  todesc="今回取得内容",
                  context=False,
                  numlines=3,
                  charset="utf-8"
              )

              # 差分ページ上部に情報を追加
              header = (
                  f"<h1>{html.escape(page_name)} の変更差分</h1>"

                  f"<p><strong>対象URL:</strong> "

                  f"<a href='{html.escape(url)}'>"

                  f"{html.escape(url)}</a></p>"

                  f"<p><strong>検出した最終更新日:</strong> "

                  f"{html.escape(last_updated)}</p>"

                  f"<p><strong>確認日時:</strong> "

                  f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>"

                  f"<hr>"
              )

              return diff_html.replace(
                  "<body>",
                  "<body>" + header
              )


          def make_plain_diff_summary(
              old_text,
              new_text,
              max_lines=40
          ):
              """
              Teams通知用の簡易差分生成

              Teamsへ全文差分を載せると長すぎるため、
              一部のみ抜粋する
              """

              diff_lines = list(
                  difflib.unified_diff(
                      old_text.splitlines(),
                      new_text.splitlines(),
                      fromfile="前回",
                      tofile="今回",
                      lineterm=""
                  )
              )

              changed_lines = []

              for line in diff_lines:

                  # diffメタ情報除去
                  if line.startswith("+++") \
                     or line.startswith("---") \
                     or line.startswith("@@"):

                      continue

                  # 追加行・削除行だけ取得
                  if line.startswith("+") \
                     or line.startswith("-"):

                      changed_lines.append(line)

              if not changed_lines:

                  return (
                      "差分行は抽出できませんでしたが、"
                      "本文変更を検知しました。"
                  )

              # Teams通知が長くなりすぎないよう制限
              if len(changed_lines) > max_lines:

                  shown = changed_lines[:max_lines]

                  shown.append(
                      f"... 他 {len(changed_lines) - max_lines} 行の変更があります。"
                  )

                  # 【修正】Teams通知上で差分を1行ずつ表示するため、
                  # 改行文字ではなく <br> を使う
                  # ここで html.escape() しているため、
                  # 後続のRSS本文生成では再度 html.escape() しない
                  return "<br>".join(
                      html.escape(line)
                      for line in shown
                  )

              # 【修正】Teams通知上で差分を1行ずつ表示するため、
              # 改行文字ではなく <br> を使う
              # ここで html.escape() しているため、
              # 後続のRSS本文生成では再度 html.escape() しない
              return "<br>".join(
                  html.escape(line)
                  for line in changed_lines
              )

          # ==================================================
          # 監視処理本体
          # ==================================================

          # 変更があったページ一覧
          changed_pages = []

          # targets.json の各ページを処理
          for page in PAGES:

              # enabled=false の場合はスキップ
              if page.get("enabled", True) is False:
                  continue

              page_name = page["name"]
              page_url = page["url"]

              print(f"Checking: {page_name}")

              # URLから安全なファイル名生成
              filename_key = safe_filename(page_url)

              # 前回比較用ファイル
              previous_path = os.path.join(
                  DATA_DIR,
                  f"{filename_key}.txt"
              )

              # 差分HTML保存先
              diff_path = os.path.join(
                  DIFF_DIR,
                  f"{filename_key}.html"
              )

              try:

                  # ==========================================
                  # Webページ取得
                  # ==========================================

                  raw_html = fetch_html(page_url)

                  # HTML → テキスト化
                  current_text = html_to_text(raw_html)

                  # 最終更新日抽出
                  current_last_updated = extract_last_updated(
                      current_text
                  )

                  # ==========================================
                  # 前回内容読み込み
                  # ==========================================

                  previous_text = ""

                  if os.path.exists(previous_path):

                      with open(
                          previous_path,
                          "r",
                          encoding="utf-8"
                      ) as f:

                          previous_text = f.read()

                  # ==========================================
                  # 比較方法判定
                  # ==========================================

                  # 最終更新日だけ比較するか
                  check_last_updated_only = page.get(
                      "check_last_updated_only",
                      False
                  )

                  if check_last_updated_only:

                      # 前回ファイルは全文保存にするので、前回テキストから最終更新日を抽出して比較する
                      previous_last_updated = extract_last_updated(previous_text)
                      
                      changed = (
                          previous_text != current_last_updated
                      )

                  else:

                      changed = (
                          previous_text != current_text
                      )

                  # 初回実行時は通知しない
                  is_first_run = (previous_text == "")

                  if is_first_run:
                      changed = False

                  # ==========================================
                  # 変更検知時処理
                  # ==========================================

                  if changed:

                      print(f"Changed detected: {page_name}")

                      # 差分HTML生成
                      diff_html = make_diff_html(
                          page_name,
                          page_url,
                          previous_text,
                          current_text,
                          current_last_updated
                      )

                      with open(
                          diff_path,
                          "w",
                          encoding="utf-8"
                      ) as f:

                          f.write(diff_html)

                      # Teams通知用サマリ生成
                      diff_summary = make_plain_diff_summary(
                          previous_text,
                          current_text
                      )

                      changed_pages.append({
                          "name": page_name,
                          "url": page_url,
                          "last_updated": current_last_updated,
                          "summary": diff_summary,
                          "diff_file": f"diffs/{filename_key}.html"
                      })

                  # ==========================================
                  # 次回比較用保存
                  # ==========================================

                  # 前回データはすべて全文で保存する
                  save_value = current_text
                  
                  #if check_last_updated_only:
                  #    save_value = current_last_updated
                  #else:
                  #    save_value = current_text

                  with open(
                      previous_path,
                      "w",
                      encoding="utf-8"
                  ) as f:

                      f.write(save_value)

              except Exception as e:

                  # 1サイト失敗しても全体停止しない
                  print(f"Error: {page_name}")
                  print(e)

          # ==================================================
          # RSS生成
          # ==================================================

          if changed_pages:

              now = datetime.now(timezone.utc)

              pub_date = now.strftime(
                  "%a, %d %b %Y %H:%M:%S GMT"
              )

              # RSS item 一意化用ハッシュ
              digest_source = (
                  pub_date
                  + "".join([
                      p["name"] + p["summary"]
                      for p in changed_pages
                  ])
              )

              digest = hashlib.sha256(
                  digest_source.encode("utf-8")
              ).hexdigest()[:12]

              # GitHub Pages URL生成
              repo = os.environ.get(
                  "GITHUB_REPOSITORY",
                  ""
              )

              owner = repo.split("/")[0]
              repo_name = repo.split("/")[1]

              pages_base_url = (
                  f"https://{owner}.github.io/{repo_name}"
              )

              details_html = ""
              details_text = ""

              for p in changed_pages:

                  diff_url = (
                      f"{pages_base_url}/{p['diff_file']}"
                  )

                  # RSS本文用HTML生成
                  details_html += (
                      f"<h2>{html.escape(p['name'])}</h2>"

                      f"<p><strong>対象URL:</strong> "

                      f"<a href='{html.escape(p['url'])}'>"

                      f"{html.escape(p['url'])}</a></p>"

                      f"<p><strong>検出した最終更新日:</strong> "

                      f"{html.escape(p['last_updated'])}</p>"

                      f"<p><strong>差分詳細:</strong> "

                      f"<a href='{html.escape(diff_url)}'>"

                      f"{html.escape(diff_url)}</a></p>"

                      f"<br><strong>変更サマリ:</strong><br>"

                      # 【修正】p["summary"] は make_plain_diff_summary() 側で
                      # html.escape() 済み、かつ <br> を含むHTML文字列のため、
                      # ここで html.escape(p["summary"]) を実行すると
                      # <br> が文字として表示され、改行されなくなる。
                      #
                      # そのため、ここでは再エスケープせず、そのまま埋め込む。
                      f"<code>{p['summary']}</code>"

                      f"<hr>"
                  )

                  # テキスト通知内容生成
                  details_text += (
                      f"【{p['name']}】\n"
                      f"対象URL: {p['url']}\n"
                      f"検出した最終更新日: {p['last_updated']}\n"
                      f"差分詳細: {diff_url}\n\n"
                      f"変更サマリ:\n"

                      # 【修正】latest_notification.txt はテキスト確認用のため、
                      # RSS/Teams用の <br> を改行へ戻して保存する
                      f"{p['summary'].replace('<br>', chr(10))}\n\n"
                  )

              # RSS XML生成
              rss = (
                  f'<?xml version="1.0" encoding="UTF-8" ?>'
                  f'<rss version="2.0">'
                  f'<channel>'

                  f'<title>OS Release Page Watch</title>'

                  f'<link>{pages_base_url}/rss.xml</link>'

                  f'<description>'
                  f'Android/iOSなどのリリース情報ページ変更監視'
                  f'</description>'

                  f'<item>'

                  f'<title>'
                  f'監視対象ページに変更がありました（{len(changed_pages)}件）'
                  f'</title>'

                  f'<link>{pages_base_url}/rss.xml</link>'

                  f'<guid>{digest}</guid>'

                  f'<pubDate>{pub_date}</pubDate>'

                  f'<description><![CDATA['

                  f'<p>'
                  f'監視対象ページに変更がありました。'
                  f'</p>'

                  f'<p>'
                  f'<strong>変更ページ数:</strong> '
                  f'{len(changed_pages)}件'
                  f'</p>'

                  f'{details_html}'

                  f']]></description>'

                  f'</item>'

                  f'</channel>'
                  f'</rss>'
              )

              # RSS XML保存
              with open(
                  os.path.join(DOCS_DIR, "rss.xml"),
                  "w",
                  encoding="utf-8"
              ) as f:

                  f.write(rss)

              # デバッグ・確認用テキスト保存
              with open(
                  os.path.join(
                      DOCS_DIR,
                      "latest_notification.txt"
                  ),
                  "w",
                  encoding="utf-8"
              ) as f:

                  f.write(details_text)

              print(
                  f"Changed pages count: {len(changed_pages)}"
              )

          else:

              print("No changes detected.")

