"""Reject host pg_dump/pg_restore for the known PostgreSQL-16 fixture on 5434."""
import ast
from pathlib import Path
import re
import shlex

MESSAGE = '5434／crossec_3018隔離庫曾兩次被本機PostgreSQL 18工具產生的不相容設定擋住；請使用該資料庫容器內的pg_dump／pg_restore，先核對版本，不要移除SQL錯誤繼續還原。'


def _host_tool(words):
    if not words:
        return False
    name = Path(words[0]).name
    return name in {'pg_dump', 'pg_restore'} and not any(x in {'--version', '-V', '--help', '-?', '--list', '-l'} for x in words[1:])


def _python_bad(source):
    if not re.search(r'5434|crossec_3018', source):
        return False
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, (ast.List, ast.Tuple)) and node.elts:
            first = node.elts[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                words = [x.value for x in node.elts if isinstance(x, ast.Constant) and isinstance(x.value, str)]
                if _host_tool(words):
                    return True
    return False


def problem(text, cwd):
    # Only executable Python heredocs; prose/file creation is not execution.
    for match in re.finditer(r"(?:^|\n)\s*python(?:3)?\s+-\s*<<['\"]?(\w+)['\"]?\s*\n(.*?)\n\1(?:\n|$)", text, re.S):
        if _python_bad(match.group(2)):
            return MESSAGE
    for line in text.splitlines():
        try:
            words = shlex.split(line)
        except ValueError:
            continue
        if not words:
            continue
        if _host_tool(words) and re.search(r'5434|crossec_3018', line):
            return MESSAGE
        if Path(words[0]).name in {'python', 'python3'} and len(words) > 1 and words[1].endswith('.py'):
            path = Path(words[1])
            if not path.is_absolute():
                path = Path(cwd) / path
            try:
                if path.stat().st_size <= 262144 and _python_bad(path.read_text()):
                    return MESSAGE
            except (OSError, UnicodeError):
                pass
    return None
