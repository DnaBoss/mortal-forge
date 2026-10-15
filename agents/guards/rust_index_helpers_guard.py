#!/usr/bin/env python3
"""Project-specific guard for the two fallible CLI fixture helpers."""
import json
import re
from pathlib import Path
import sys

REPO = Path('/home/cash/work_space/private/aletheia')
SOURCE = REPO / 'tests/telemetry_index_cli.rs'
CURSOR = REPO / 'src/telemetry/cursor.rs'
CUMULATIVE = REPO / 'src/telemetry/cumulative.rs'
QUERY_TESTS = REPO / 'src/telemetry/query_http/tests.rs'

def protected(source):
    # Narrow to the existing named helpers. Missing/ambiguous signatures fail.
    for name in ('conn', 'json'):
        declarations = list(re.finditer(r'\bfn\s+' + name + r'\s*\(', source))
        if len(declarations) != 1:
            return False
        rest = source[declarations[0].start():]
        signature = re.match(r'fn\s+' + name + r'\s*\([^)]*\)\s*->\s*Result\s*<[^{}]+>\s*\{', rest)
        if signature is None:
            return False
        boundary = re.search(r'\n\s*(?:fn\s+|#\[test\])', rest[signature.end():])
        if boundary is None:
            return False
        body = rest[signature.end():signature.end() + boundary.start()]
        if '}' not in body or re.search(r'\.\s*unwrap\s*\(', body):
            return False
    return True

def error_context(source):
    return re.search(r"\.\s*map_err\s*\(\s*\|\s*_\s*\|", source) is None

def main():
    payload = json.load(sys.stdin)
    cwd = Path(payload.get('cwd', '.')).resolve()
    if cwd != REPO:
        return 0
    try:
        allowed = protected(SOURCE.read_text()) and error_context(CURSOR.read_text()) and error_context(CUMULATIVE.read_text()) and error_context(QUERY_TESTS.read_text())
    except OSError:
        allowed = False
    if not allowed:
        print('補索引測試的 conn／json 輔助函式須回傳 Result 並傳出錯誤，不得直接 unwrap；續頁簽章、累積統計與查詢測試也須保留原始錯誤原因；先修正再交付。', file=sys.stderr)
        return 2
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
