"""Narrow pre-Cargo guard for recurring Aletheia telemetry type guesses.

Only registered spellings are checked. This is not a Rust parser or a replacement
for compilation. Read the current declarations, then scan bounded source files.
"""
from pathlib import Path
import re


def complete_key_values(source):
    # Only registered KeyValue literals in trace fixtures; not a Rust parser.
    for match in re.finditer(r'\bKeyValue\s*\{', source):
        pos=match.end(); depth=1; complete=False
        while pos<len(source) and depth:
            if depth==1 and re.match(r'(?:key_strindex\s*:|\.\.\s*Default\s*::\s*default\s*\()',source[pos:]):
                complete=True
            if source[pos]=='{': depth+=1
            elif source[pos]=='}': depth-=1
            pos+=1
        if depth or not complete:
            return False
    return True


def problem(base):
    root = Path(base)
    policy = root / 'src/telemetry/reader/statistics/groups.rs'
    store = root / 'src/telemetry/store.rs'
    if not policy.is_file() or not store.is_file():
        return None
    declaration = policy.read_text(encoding='utf-8')
    body = re.search(r'pub\s+struct\s+StatisticsPolicy\s*\{([^}]*)\}', declaration)
    if not body:
        return None
    fields = set(re.findall(r'pub\s+(\w+)\s*:', body.group(1)))
    files = sorted((root / 'src/telemetry').rglob('*.rs')) + sorted((root / 'tests').glob('telemetry*.rs'))
    if len(files) > 512:
        return None
    store_text = store.read_text(encoding='utf-8')
    has_stored_batch = bool(re.search(r'pub\s+struct\s+StoredBatch\b', store_text))
    auth_file = root / 'src/telemetry/auth.rs'
    auth_text = auth_file.read_text(encoding='utf-8') if auth_file.is_file() else ''
    correlation_is_option = bool(re.search(r'pub\s+fn\s+correlation_scope\s*\([^)]{0,1024}\)\s*->\s*Option\s*<',auth_text))
    report_file = root / 'src/telemetry/reader/trace.rs'
    report_text = report_file.read_text(encoding='utf-8') if report_file.is_file() else ''
    trace_report = re.search(r'pub\s+struct\s+TraceReport\s*\{([^}]*)\}',report_text)
    trace_report_has_query = bool(trace_report and re.search(r'pub\s+query\s*:',trace_report.group(1)))
    for file in files:
        if file.stat().st_size > 2 * 1024 * 1024:
            continue
        source = file.read_text(encoding='utf-8')
        if correlation_is_option and re.search(r'\.correlation_scope\s*\([^()]{0,512}\)\s*\.is_err\s*\(',source):
            return 'correlation_scope 目前回傳 Option；用 is_none 核沒有授權，先核真方法簽名。'
        trace_http = root / 'src/telemetry/query_http/trace.rs'
        trace_directory = root / 'src/telemetry/query_http/trace'
        if trace_report and not trace_report_has_query and (file == trace_http or trace_directory in file.parents) and re.search(r'\breport\s*\.\s*query\b',source):
            return 'TraceReport 沒有 query 欄位；查詢條件另傳，先核目前報告型別。'
        if file == root / 'src/telemetry/trace_correlation/tests.rs' and not complete_key_values(source):
            return '官方 KeyValue 還有 key_strindex；測試初始化須列完整欄位或使用外層 Default。'
        if 'reader' not in fields and re.search(r'\bStatisticsPolicy\s*\{\s*reader\s*:', source):
            return 'StatisticsPolicy 的讀取欄位是 read；先核目前型別，不要使用 reader。'
        if not has_stored_batch and re.search(r'\bStoredBatch\b', source):
            return '保存資料型別是 Batch；先核目前 store 型別，不要猜 StoredBatch。'
    return None
