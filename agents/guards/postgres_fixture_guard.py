#!/usr/bin/env python3
"""Require the owned Postgres fixture's socket invariant before launching it."""
import ast
import json
from pathlib import Path
import sys

SCRIPT = Path('/home/cash/work_space/private/aletheia/scripts/monitoring/verify_postgres_source.py')


def protected(source):
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'verify')
    launches = [node.lineno for node in ast.walk(function) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'command' and len(node.args) == 1 and isinstance(node.args[0], ast.Name) and node.args[0].id == 'args']
    for node in ast.walk(function):
        if isinstance(node, ast.If) and node.lineno < min(launches):
            strings = {item.value for item in ast.walk(node) if isinstance(item, ast.Constant) and isinstance(item.value, str)}
            if {'unix_socket_directories=/var/run/postgresql', '/var/run/postgresql:rw,', 'Postgres bootstrap socket path lacks owned writable mount'} <= strings and any(isinstance(item, ast.Raise) for item in ast.walk(node)):
                return True
    return False


def main():
    payload = json.load(sys.stdin)
    if 'verify_postgres_source.py' not in json.dumps(payload):
        return 0
    try:
        allowed = protected(SCRIPT.read_text())
    except (OSError, SyntaxError, StopIteration, ValueError):
        allowed = False
    if not allowed:
        print('Postgres 隔離驗證缺少預設 socket 與自有可寫掛載的啟動前檢查；先修設定，不重跑。', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
