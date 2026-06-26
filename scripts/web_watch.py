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
ACCEPT_LANGUAGE = "ja,en-US;q=0.9,en;q=0.8"
LAST_UPDATED_NOT_FOUND = "\u691c\u51fa\u3067\u304d\u307e\u305b\u3093\u3067\u3057\u305f"

LAST_UPDATED_PATTERNS = [
    r"\u6700\u7d42\u66f4\u65b0\u65e5\s*[：: ]\s*\d{4}-\d{2}-\d{2}\s*UTC",
    r"\u6700\u7d42\u66f4\u65b0\u65e5\s*[：: ]\s*\d{4}\u5e74\d{1,2}\u6708\d{1,2}\u65e5",
    r"\u516c\u958b\u65e5\s*[：: ]\s*\d{4}\u5e74\d{1,2}\u6708\d{1,2}\u65e5",
    r"\u66f4\u65b0\u65e5\s*[：: ]\s*\d{4}\u5e74\d{1,2}\u6708\d{1,2}\u65e5",
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


def fetch_with_curl(url: str) -> str:
    result = subprocess.run(
        [
            "curl",
            "-L",
            "-A",
            USER_AGENT,
            "-H",
            f"Accept-Language: {ACCEPT_LANGUAGE}",
            url,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "curl failed")
    return result.stdout


def build_opener() -> urllib.request.OpenerDirector:
    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar)
    )
    opener.addheaders = [
        ("User-Agent", USER_AGENT),
        ("Accept-Language", ACCEPT_LANGUAGE),
    ]
    return opener


def fetch_with_urllib(url: str) -> str:
    opener = build_opener()
    with opener.open(url, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


def strip_hl_query(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered_query = [(key, value) for key, value in query if key.lower() != "hl"]
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(filtered_query),
            parsed.fragment,
        )
    )


def fetch_html(url: str) -> str:
    if "developer.android.com" not in url:
        return fetch_with_urllib(url)

    try:
        return fetch_with_curl(url)
    except Exception as error:
        print(f"Android curl fallback: {error}")

    try:
        return fetch_with_urllib(url)
    except Exception as error:
        print(f"Android urllib retry failed: {error}")

    normalized_url = strip_hl_query(url)
    if normalized_url != url:
        return fetch_with_urllib(normalized_url)

    raise RuntimeError("Android page fetch failed after retries")


def html_to_text(raw_html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", "", raw_html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<noscript[\s\S]*?</noscript>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = html.unescape(text)
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


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
        fromdesc="\u524d\u56de\u53d6\u5f97\u5185\u5bb9",
        todesc="\u4eca\u56de\u53d6\u5f97\u5185\u5bb9",
        context=False,
        numlines=3,
        charset="utf-8",
    )

    header = (
        f"<h1>{html.escape(page_name)} \u306e\u5909\u66f4\u5dee\u5206</h1>"
        f"<p><strong>\u5bfe\u8c61URL:</strong> "
        f"<a href='{html.escape(url)}'>{html.escape(url)}</a></p>"
        f"<p><strong>\u691c\u51fa\u3057\u305f\u6700\u7d42\u66f4\u65b0\u65e5:</strong> "
        f"{html.escape(last_updated)}</p>"
        f"<p><strong>\u78ba\u8a8d\u65e5\u6642:</strong> "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>"
        "<hr>"
    )
    return diff_html.replace("<body>", "<body>" + header)


def make_plain_diff_summary(old_text: str, new_text: str, max_lines: int = 40) -> str:
    diff_lines = list(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile="\u524d\u56de",
            tofile="\u4eca\u56de",
            lineterm="",
        )
    )

    changed_lines = [
        line
        for line in diff_lines
        if not line.startswith(("+++", "---", "@@")) and line.startswith(("+", "-"))
    ]

    if not changed_lines:
        return (
            "\u5dee\u5206\u306f\u691c\u51fa\u3055\u308c\u307e\u3057\u305f\u304c\u3001"
            "\u884c\u5358\u4f4d\u306e\u8981\u7d04\u306f\u751f\u6210\u3067\u304d\u307e\u305b\u3093\u3067\u3057\u305f\u3002"
        )

    if len(changed_lines) > max_lines:
        changed_lines = changed_lines[:max_lines] + [
            f"... \u307b\u304b {len(changed_lines) - max_lines} \u884c"
        ]

    return "<br>".join(html.escape(line) for line in changed_lines)


def build_pages_base_url() -> str:
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repository:
        return ""
    owner, repo_name = repository.split("/", 1)
    return f"https://{owner}.github.io/{repo_name}"


def write_rss(changed_pages: list[dict[str, str]]) -> None:
    now = datetime.now(timezone.utc)
    pub_date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    digest_source = pub_date + "".join(
        page["name"] + page["summary"] for page in changed_pages
    )
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:12]
    pages_base_url = build_pages_base_url()

    details_html_parts: list[str] = []
    details_text_parts: list[str] = []

    for page in changed_pages:
        diff_url = (
            f"{pages_base_url}/{page['diff_file']}"
            if pages_base_url
            else page["diff_file"]
        )

        details_html_parts.append(
            (
                f"<h2>{html.escape(page['name'])}</h2>"
                f"<p><strong>\u5bfe\u8c61URL:</strong> "
                f"<a href='{html.escape(page['url'])}'>{html.escape(page['url'])}</a></p>"
                f"<p><strong>\u691c\u51fa\u3057\u305f\u6700\u7d42\u66f4\u65b0\u65e5:</strong> "
                f"{html.escape(page['last_updated'])}</p>"
                f"<p><strong>\u5dee\u5206\u8a73\u7d30:</strong> "
                f"<a href='{html.escape(diff_url)}'>{html.escape(diff_url)}</a></p>"
                f"<br><strong>\u5909\u66f4\u30b5\u30de\u30ea:</strong><br>"
                f"<code>{page['summary']}</code>"
                "<hr>"
            )
        )

        details_text_parts.append(
            "\n".join(
                [
                    f"\u3010{page['name']}\u3011",
                    f"\u5bfe\u8c61URL: {page['url']}",
                    f"\u691c\u51fa\u3057\u305f\u6700\u7d42\u66f4\u65b0\u65e5: {page['last_updated']}",
                    f"\u5dee\u5206\u8a73\u7d30: {diff_url}",
                    "",
                    "\u5909\u66f4\u30b5\u30de\u30ea:",
                    page["summary"].replace("<br>", "\n"),
                    "",
                ]
            )
        )

    details_html = "".join(details_html_parts)
    details_text = "".join(details_text_parts)
    feed_link = f"{pages_base_url}/rss.xml" if pages_base_url else "rss.xml"

    rss = (
        '<?xml version="1.0" encoding="UTF-8" ?>'
        '<rss version="2.0"><channel>'
        "<title>OS Release Page Watch</title>"
        f"<link>{feed_link}</link>"
        "<description>Android/iOS \u306a\u3069\u306e\u30ea\u30ea\u30fc\u30b9\u60c5\u5831\u30da\u30fc\u30b8\u5909\u66f4\u76e3\u8996</description>"
        "<item>"
        f"<title>\u76e3\u8996\u5bfe\u8c61\u30da\u30fc\u30b8\u306b\u5909\u66f4\u304c\u3042\u308a\u307e\u3057\u305f\uff08{len(changed_pages)}\u4ef6\uff09</title>"
        f"<link>{feed_link}</link>"
        f"<guid>{digest}</guid>"
        f"<pubDate>{pub_date}</pubDate>"
        "<description><![CDATA["
        "<p>\u76e3\u8996\u5bfe\u8c61\u30da\u30fc\u30b8\u306b\u5909\u66f4\u304c\u3042\u308a\u307e\u3057\u305f\u3002</p>"
        f"<p><strong>\u5909\u66f4\u30da\u30fc\u30b8\u6570:</strong> {len(changed_pages)}\u4ef6</p>"
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

        print(f"\u78ba\u8a8d\u4e2d: {page_name}")

        filename_key = safe_filename(page_url)
        previous_path = DATA_DIR / f"{filename_key}.txt"
        diff_path = DIFF_DIR / f"{filename_key}.html"

        try:
            raw_html = fetch_html(page_url)
            current_text = html_to_text(raw_html)
            current_last_updated = extract_last_updated(current_text)
            previous_text = (
                previous_path.read_text(encoding="utf-8")
                if previous_path.exists()
                else ""
            )
        except Exception as error:
            print(f"\u53d6\u5f97\u30a8\u30e9\u30fc: {page_name}")
            print(error)
            continue

        if not previous_text:
            changed = False
        elif check_last_updated_only:
            previous_last_updated = extract_last_updated(previous_text)
            changed = previous_last_updated != current_last_updated
        else:
            changed = previous_text != current_text

        if changed:
            print(f"\u5909\u66f4\u3092\u691c\u51fa: {page_name}")
            diff_html = make_diff_html(
                page_name=page_name,
                url=page_url,
                old_text=previous_text,
                new_text=current_text,
                last_updated=current_last_updated,
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
        print(f"\u5909\u66f4\u30da\u30fc\u30b8\u6570: {len(changed_pages)}")
    else:
        print("\u5909\u66f4\u306f\u3042\u308a\u307e\u305b\u3093\u3067\u3057\u305f\u3002")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
