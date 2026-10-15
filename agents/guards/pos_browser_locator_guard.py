#!/usr/bin/env python3
"""POS瀏覽器腳本前置檢查：已退款必須先限定區域。只讀輸入。"""
import re
import sys
from pathlib import Path

PATTERN = re.compile(r"\bpage\s*\.\s*getByText\s*\(\s*(['\"])已退款\1\s*[,)]")

def check(source: str) -> bool:
    return PATTERN.search(source) is None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(2)
    if not check(Path(sys.argv[1]).read_text(encoding="utf-8")):
        print("POS 的已退款文字同時存在於篩選、清單與詳情，請先限定付款區域再定位。", file=sys.stderr)
        sys.exit(2)
