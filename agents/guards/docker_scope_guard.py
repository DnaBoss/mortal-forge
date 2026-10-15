#!/usr/bin/env python3
"""Reject missing Docker scope checks before project verification executes."""
import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path('/home/cash/work_space/private/aletheia')


def python_heredocs(command):
    """Read Python bodies; consume other heredocs without inspecting their text."""
    lines = command.splitlines()
    index = 0
    while index < len(lines):
        header = lines[index]
        marker = re.search(r"<<(-?)\s*(['\"]?)([A-Za-z_]\w*)\2", header)
        index += 1
        if marker is None or header.lstrip().startswith('#'):
            continue
        python = re.match(r'^\s*python(?:3(?:\.\d+)?)?\s+(?:-u\s+)?-\s+<<', header)
        body = []
        while index < len(lines):
            line = lines[index]
            index += 1
            if (line.lstrip('\t') if marker[1] else line) == marker[3]:
                break
            body.append(line.lstrip('\t') if marker[1] else line)
        if python:
            yield '\n'.join(body)


def contains_stderr(node):
    return any(
        isinstance(item, ast.Attribute) and item.attr == 'stderr'
        or isinstance(item, ast.Name) and (item.id == 'stderr' or item.id.endswith('_stderr'))
        for item in ast.walk(node)
    )


def folded(node):
    return (
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in ('lower', 'casefold') and not node.args and not node.keywords
    )


def unsafe_absence_comparison(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        for operator, right in zip(node.ops, node.comparators):
            needle = left.func.value if folded(left) else left
            if (isinstance(operator, (ast.In, ast.NotIn))
                    and isinstance(needle, ast.Constant) and isinstance(needle.value, str)
                    and 'no such object' in needle.value.casefold() and contains_stderr(right)):
                if not folded(right) or (not folded(left) and needle.value != needle.value.casefold()):
                    return True
            left = right
    return False


def command_values(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ('command', 'cmd') and isinstance(item, str):
                yield item
            elif isinstance(item, (dict, list)):
                yield from command_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from command_values(item)


def protected(script, config):
    required = ['bind 127.0.0.1', 'admin off', '@encoded_path expression',
                'OTEL_DOCKER_LIST_FILTER', 'OTEL_DOCKER_EVENT_FILTER',
                '/containers/({$OTEL_DOCKER_IDS})/json$',
                '/containers/({$OTEL_DOCKER_IDS})/stats$',
                'respond "Docker operation outside approved read scope" 403']
    if not all(item in config for item in required):
        return False
    tree = ast.parse(script)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'verify_docker_record')
    for node in ast.walk(function):
        if isinstance(node, ast.If):
            strings = {item.value for item in ast.walk(node) if isinstance(item, ast.Constant) and isinstance(item.value, str)}
            if {'container.state.status', 'Unscoped Docker resource contains non-aggregate metric'} <= strings and any(isinstance(item, ast.Raise) for item in ast.walk(node)):
                return True
    return False


def main():
    payload = json.load(sys.stdin)
    for command in command_values(payload):
        if any(unsafe_absence_comparison(body) for body in python_heredocs(command)):
            print('Docker 查無物件的 stderr 比較須用 lower() 或 casefold() 正規化，查找字串也須小寫；先修獨立檢查，不把大小寫差異當產品失敗。', file=sys.stderr)
            return 2
    if 'verify_docker_source.py' not in json.dumps(payload):
        return 0
    try:
        allowed = protected((ROOT / 'scripts/monitoring/verify_docker_source.py').read_text(), (ROOT / 'sre/otel/docker-proxy.Caddyfile').read_text())
    except (OSError, SyntaxError, StopIteration):
        allowed = False
    if not allowed:
        print('Docker 驗證缺少回環綁定、來源範圍、編碼路徑拒絕或整體統計欄位檢查；先修設定，不重跑。', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
