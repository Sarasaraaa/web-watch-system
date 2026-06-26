from __future__ import annotations

import difflib
import hashlib
import html
import http.cookiejar
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
TARGETS_PATH = ROOT_DIR / "config" / "targets.json"
DATA_DIR = ROOT_DIR / "data"
DOCS_DIR = ROOT_DIR / "docs"
DIFF_DIR = DOCS_DIR / "diffs"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
LAST_UPDATED_NOT_FOUND = "検出できませんでした"

LAST_UPDATED_PATTERNS = [
    r"最終更新日\s*[：: ]\s*\d{4}-\d{2}-\d{2}\s*UTC",
    r"最終更新日\s*[：: ]\s*\d{4}年\d{1,2}月\d{1,2}日",
    r"公開日\s*[：: ]\s*\d{4}年\d{1,2}月\d{1,2}日",
    r"更新日\s*[：: ]\s*\d{4}年\d{1,2}月\d{1,2}日",
    r"Published\s+[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}",
    r"Released\s+[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}",
    r"Updated\s+[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}",
    r"Last updated\s+[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}",
]


def load_targets() -> list[dict[str, object]]:
    with TARGETS_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def ensure_directories() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    DOCS_DIR.mkdir(exist_ok=True)
    DIFF_DIR.mkdir(exist_ok=True)


def safe_filename(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def fetch_html(url: str) -> str:
    if "developer.android.com" in url:
        try:
            result = subprocess.run(
                [
                    "curl",
                    "-L",
                    "-A",
                    USER_AGENT,
                    url,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            if result.returncode == 0:
                return result.stdout
            print(f"Android curl retry: {result.stderr.strip()}")
        except Exception as error:
            print(f"Android curl retry: {error}")

    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    opener.addheaders = [
        ("User-Agent", USER_AGENT),
        ("Accept-Language", "ja,en-US;q=0.9,en;q=0.8"),
    ]

    try:
        with opener.open(url, timeout=30) as response:
            return response.read().decode("utf-8", errors="ignore")
    except Exception:
        if "developer.android.com" not in url:
            raise

    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered_query = [(key, value) for key, value in query if key.lower() != "hl"]
    retry_url = urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(filtered_query),
            parsed.fragment,
        )
    )

    with opener.open(retry_url, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def html_to_text(raw_html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", "", raw_html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<noscript[\s\S]*?</noscript>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html.unescape(text)
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def extract_last_updated(text: str) -> str:
    for pattern in LAST_UPDATED_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return LAST_UPDATED_NOT_FOUND


def make_diff_html(
    page_name: str,
    url: str,
    old_text: str,
    new_text: str,
    last_updated: str,
) -> str:
    diff_html = difflib.HtmlDiff(wrapcolumn=100).make_file(
        old_text.splitlines(),
        new_text.splitlines(),
        fromdesc="前回取得内容",
        todesc="今回取得内容",
        context=False,
        numlines=3,
        charset="utf-8",
    )

    header = (
        f"<h1>{html.escape(page_name)} の変更差分</h1>"
        f"<p><strong>対象URL:</strong> "
        f"<a href='{html.escape(url)}'>{html.escape(url)}</a></p>"
        f"<p><strong>検出した最終更新日:</strong> {html.escape(last_updated)}</p>"
        f"<p><strong>確認日時:</strong> "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>"
        "<hr>"
    )

    return diff_html.replace("<body>", "<body>" + header)


def make_plain_diff_summary(old_text: str, new_text: str, max_lines: int = 40) -> str:
    diff_lines = list(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile="前回",
            tofile="今回",
            lineterm="",
        )
    )

    changed_lines = []
    for line in diff_lines:
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith("+") or line.startswith("-"):
            changed_lines.append(line)

    if not changed_lines:
        return "差分は検出されましたが、行単位の要約は生成できませんでした。"

    if len(changed_lines) > max_lines:
        shown_lines = changed_lines[:max_lines]
        shown_lines.append(f"... ほか {len(changed_lines) - max_lines} 行")
        return "<br>".join(html.escape(line) for line in shown_lines)

    return "<br>".join(html.escape(line) for line in changed_lines)


def write_rss(changed_pages: list[dict[str, str]]) -> None:
    now = datetime.now(timezone.utc)
    pub_date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    digest_source = pub_date + "".join(
        page["name"] + page["summary"] for page in changed_pages
    )
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]

    repository = os.environ.get("GITHUB_REPOSITORY", "")
    pages_base_url = ""
    if "/" in repository:
        owner, repo_name = repository.split("/", 1)
        pages_base_url = f"https://{owner}.github.io/{repo_name}"

    details_html = ""
    details_text = ""

    for page in changed_pages:
        diff_url = (
            f"{pages_base_url}/{page['diff_file']}"
            if pages_base_url
            else page["diff_file"]
        )

        details_html += (
            f"<h2>{html.escape(page['name'])}</h2>"
            f"<p><strong>対象URL:</strong> "
            f"<a href='{html.escape(page['url'])}'>{html.escape(page['url'])}</a></p>"
            f"<p><strong>検出した最終更新日:</strong> "
            f"{html.escape(page['last_updated'])}</p>"
            f"<p><strong>差分詳細:</strong> "
            f"<a href='{html.escape(diff_url)}'>{html.escape(diff_url)}</a></p>"
            f"<br><strong>変更サマリ:</strong><br>"
            f"<code>{page['summary']}</code>"
            "<hr>"
        )

        details_text += (
            f"【{page['name']}】\n"
            f"対象URL: {page['url']}\n"
            f"検出した最終更新日: {page['last_updated']}\n"
            f"差分詳細: {diff_url}\n\n"
            f"変更サマリ:\n"
            f"{page['summary'].replace('<br>', chr(10))}\n\n"
        )

    feed_link = f"{pages_base_url}/rss.xml" if pages_base_url else "rss.xml"

    rss = (
        '<?xml version="1.0" encoding="UTF-8" ?>'
        "<rss version=\"2.0\"><channel>"
        "<title>OS Release Page Watch</title>"
        f"<link>{feed_link}</link>"
        "<description>Android/iOS などのリリース情報ページ変更監視</description>"
        "<item>"
        f"<title>監視対象ページに変更がありました（{len(changed_pages)}件）</title>"
        f"<link>{feed_link}</link>"
        f"<guid>{digest}</guid>"
        f"<pubDate>{pub_date}</pubDate>"
        "<description><![CDATA["
        "<p>監視対象ページに変更がありました。</p>"
        f"<p><strong>変更ページ数:</strong> {len(changed_pages)}件</p>"
        f"{details_html}"
        "]]></description>"
        "</item>"
        "</channel></rss>"
    )

    (DOCS_DIR / "rss.xml").write_text(rss, encoding="utf-8")
    (DOCS_DIR / "latest_notification.txt").write_text(details_text, encoding="utf-8")


def main() -> int:
    ensure_directories()
    changed_pages: list[dict[str, str]] = []

    for page in load_targets():
        if page.get("enabled", True) is False:
            continue

        page_name = str(page["name"])
        page_url = str(page["url"])
        check_last_updated_only = bool(page.get("check_last_updated_only", False))

        print(f"確認中: {page_name}")

        filename_key = safe_filename(page_url)
        previous_path = DATA_DIR / f"{filename_key}.txt"
        diff_path = DIFF_DIR / f"{filename_key}.html"

        try:
            raw_html = fetch_html(page_url)
            current_text = html_to_text(raw_html)
            current_last_updated = extract_last_updated(current_text)
        except Exception as error:
            print(f"取得エラー: {page_name}")
            print(error)
            continue

        previous_text = ""
        if previous_path.exists():
            previous_text = previous_path.read_text(encoding="utf-8")

        changed = False
        if previous_text:
            if check_last_updated_only:
                previous_last_updated = extract_last_updated(previous_text)
                changed = previous_last_updated != current_last_updated
            else:
                changed = previous_text != current_text

        if changed:
            print(f"変更を検出: {page_name}")
            diff_html = make_diff_html(
                page_name,
                page_url,
                previous_text,
                current_text,
                current_last_updated,
            )
            diff_path.write_text(diff_html, encoding="utf-8")

            changed_pages.append(
                {
                    "name": page_name,
                    "url": page_url,
                    "last_updated": current_last_updated,
                    "summary": make_plain_diff_summary(previous_text, current_text),
                    "diff_file": f"diffs/{filename_key}.html",
                }
            )

        previous_path.write_text(current_text, encoding="utf-8")

    if changed_pages:
        write_rss(changed_pages)
        print(f"変更ページ数: {len(changed_pages)}")
    else:
        print("変更はありませんでした。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
