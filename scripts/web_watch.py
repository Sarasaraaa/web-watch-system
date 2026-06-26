from __future__ import annotations

import difflib
import hashlib
import html
import json
import os
import re
import subprocess
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
        result = subprocess.run(
            [
                "curl",
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "--user-agent",
                USER_AGENT,
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

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="ignore")


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
    return "not found"


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
        fromdesc="Previous",
        todesc="Current",
        context=False,
        numlines=3,
        charset="utf-8",
    )

    header = (
        f"<h1>{html.escape(page_name)} diff</h1>"
        f"<p><strong>Source URL:</strong> "
        f"<a href='{html.escape(url)}'>{html.escape(url)}</a></p>"
        f"<p><strong>Last updated:</strong> {html.escape(last_updated)}</p>"
        f"<p><strong>Detected at:</strong> "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>"
        "<hr>"
    )
    return diff_html.replace("<body>", "<body>" + header)


def make_plain_diff_summary(old_text: str, new_text: str, max_lines: int = 40) -> str:
    diff_lines = list(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile="previous",
            tofile="current",
            lineterm="",
        )
    )

    changed_lines = [
        line
        for line in diff_lines
        if not line.startswith(("+++", "---", "@@")) and line.startswith(("+", "-"))
    ]

    if not changed_lines:
        return "No line-level diff summary was generated."

    if len(changed_lines) > max_lines:
        changed_lines = changed_lines[:max_lines] + [
            f"... and {len(changed_lines) - max_lines} more lines"
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
                f"<p><strong>Source URL:</strong> "
                f"<a href='{html.escape(page['url'])}'>{html.escape(page['url'])}</a></p>"
                f"<p><strong>Last updated:</strong> {html.escape(page['last_updated'])}</p>"
                f"<p><strong>Diff:</strong> "
                f"<a href='{html.escape(diff_url)}'>{html.escape(diff_url)}</a></p>"
                f"<br><strong>Summary:</strong><br>"
                f"<code>{page['summary']}</code>"
                "<hr>"
            )
        )

        details_text_parts.append(
            "\n".join(
                [
                    f"[{page['name']}]",
                    f"Source URL: {page['url']}",
                    f"Last updated: {page['last_updated']}",
                    f"Diff: {diff_url}",
                    "",
                    "Summary:",
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
        "<description>Watch release information pages for changes.</description>"
        "<item>"
        f"<title>{len(changed_pages)} watched page(s) changed</title>"
        f"<link>{feed_link}</link>"
        f"<guid>{digest}</guid>"
        f"<pubDate>{pub_date}</pubDate>"
        "<description><![CDATA["
        "<p>Detected updates on watched pages.</p>"
        f"<p><strong>Changed pages:</strong> {len(changed_pages)}</p>"
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

        print(f"Checking: {page_name}")

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
            print(f"Error: {page_name}")
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
            print(f"Change detected: {page_name}")
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
        print(f"Changed pages count: {len(changed_pages)}")
    else:
        print("No changes detected.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
