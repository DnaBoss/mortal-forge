#!/usr/bin/env python3
"""Convert a Markdown file (Traditional Chinese, tables) to a print-ready PDF.

Markdown -> HTML (python-markdown: tables, fenced code) -> headless Chromium
page.pdf() with Noto Sans CJK TC. A4, page numbers in the footer.

Run with: ~/.venvs/page-render/bin/python ~/tools/md_to_pdf.py IN.md OUT.pdf [--title T]
Writes only OUT.pdf; refuses to overwrite unless --force.
"""

import argparse
import html
import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

# Same pinned browser as render_pages.py (playwright 1.63.0 in ~/.venvs/page-render).
DEFAULT_CHROME = Path.home() / ".cache/ms-playwright/chromium-1234/chrome-linux64/chrome"

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
body { font-family: 'Noto Sans CJK TC', 'Noto Sans TC', sans-serif; font-size: 10.5pt;
       line-height: 1.6; color: #1d1d1f; }
h1 { font-size: 20pt; border-bottom: 2px solid #2f6f5e; padding-bottom: 6px; }
h2 { font-size: 14pt; color: #1f5546; margin-top: 22px; border-left: 4px solid #2f6f5e;
     padding-left: 8px; page-break-after: avoid; }
h3 { font-size: 12pt; page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9.5pt;
        page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #c8cfcc; padding: 4px 6px; vertical-align: top; text-align: left; }
th { background: #e8f0ed; }
code { font-family: 'Noto Sans Mono CJK TC', monospace; background: #f2f4f3; padding: 0 3px;
       border-radius: 3px; font-size: 9pt; }
li { margin: 2px 0; }
"""


LIST_ITEM = __import__("re").compile(r"^\s*([-*+]|\d+\.)\s")


def separate_lists(md_text: str) -> str:
    """python-markdown needs a blank line before a list that follows a paragraph."""
    out: list[str] = []
    for line in md_text.splitlines():
        prev = out[-1] if out else ""
        if LIST_ITEM.match(line) and prev.strip() and not LIST_ITEM.match(prev) and not prev.startswith(("|", "#", " ")):
            out.append("")
        out.append(line)
    return "\n".join(out)


def render(md_text: str, title: str) -> str:
    body = markdown.markdown(separate_lists(md_text), extensions=["tables", "fenced_code", "sane_lists"])
    return (
        "<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
        f"<body>{body}</body></html>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", type=Path)
    parser.add_argument("dst", type=Path)
    parser.add_argument("--title", default="")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.dst.exists() and not args.force:
        print(f"refusing to overwrite {args.dst} (use --force)", file=sys.stderr)
        return 2
    page_html = render(args.src.read_text(encoding="utf-8"), args.title or args.src.stem)
    footer = (
        "<div style='font-size:8pt;width:100%;text-align:center;color:#777;'>"
        "<span class='pageNumber'></span> / <span class='totalPages'></span></div>"
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=str(DEFAULT_CHROME), headless=True)
        page = browser.new_page()
        page.set_content(page_html, wait_until="load")
        page.pdf(path=str(args.dst), format="A4", print_background=True,
                 display_header_footer=True, header_template="<div></div>",
                 footer_template=footer,
                 margin={"top": "18mm", "bottom": "20mm", "left": "16mm", "right": "16mm"})
        browser.close()
    print(f"wrote {args.dst} ({args.dst.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
