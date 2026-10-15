#!/usr/bin/env python3
"""Render JS-driven web pages with headless Chromium and save the result.

Input: a TSV file, one page per line: <url>\t<output-basename>
Output per page in --out-dir: <name>.rendered.html, <name>.txt, <name>.png
Plus render-report.json with status, text length and SHA256 per file.

Read-only on the network side: one navigation per URL, no clicks, no forms,
no login. Existing output files are never overwritten (skip and report).

Run with: ~/.venvs/page-render/bin/python ~/tools/render_pages.py pages.tsv --out-dir DIR
"""

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

DEFAULT_CHROME = Path.home() / ".cache/ms-playwright/chromium-1234/chrome-linux64/chrome"


def parse_pages(tsv_path: Path) -> list[tuple[str, str]]:
    pages = []
    for line_no, line in enumerate(tsv_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 2 or not parts[0].startswith(("http://", "https://")) or not parts[1].strip():
            raise ValueError(f"bad line {line_no}: expected <url>\\t<name>")
        name = parts[1].strip()
        if "/" in name or name.startswith("."):
            raise ValueError(f"bad name on line {line_no}: {name!r}")
        pages.append((parts[0].strip(), name))
    return pages


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(pages, out_dir: Path, chrome: Path, wait_ms: int, timeout_ms: int) -> list[dict]:
    report = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=str(chrome), headless=True)
        context = browser.new_context(locale="zh-TW", viewport={"width": 1366, "height": 900})
        for url, name in pages:
            targets = {k: out_dir / f"{name}.{k}" for k in ("rendered.html", "txt", "png")}
            entry = {"url": url, "name": name, "rendered_at": datetime.now(timezone.utc).isoformat()}
            if any(p.exists() for p in targets.values()):
                entry["status"] = "skipped_exists"
                report.append(entry)
                continue
            page = context.new_page()
            try:
                response = page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                page.wait_for_timeout(wait_ms)
                entry["http_status"] = response.status if response else None
                entry["final_url"] = page.url
                entry["title"] = page.title()
                text = page.inner_text("body")
                targets["rendered.html"].write_text(page.content(), encoding="utf-8")
                targets["txt"].write_text(text, encoding="utf-8")
                page.screenshot(path=str(targets["png"]), full_page=True)
                entry["text_chars"] = len(text)
                entry["files"] = {k: {"path": str(p), "sha256": sha256(p)} for k, p in targets.items()}
                entry["status"] = "ok"
            except Exception as exc:  # record and continue; one page must not stop the batch
                entry["status"] = "error"
                entry["error"] = f"{type(exc).__name__}: {exc}"[:500]
            finally:
                page.close()
            report.append(entry)
        browser.close()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pages_tsv", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--chrome", type=Path, default=DEFAULT_CHROME)
    ap.add_argument("--wait-ms", type=int, default=2000, help="extra wait after network idle")
    ap.add_argument("--timeout-ms", type=int, default=45000)
    args = ap.parse_args()

    pages = parse_pages(args.pages_tsv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    report = render(pages, args.out_dir, args.chrome, args.wait_ms, args.timeout_ms)
    report_path = args.out_dir / f"render-report-{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = {}
    for e in report:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    print(json.dumps({"report": str(report_path), "counts": counts}, ensure_ascii=False))
    return 0 if counts.get("error", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
