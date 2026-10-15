#!/usr/bin/env python3
"""Require retained actual/expected evidence before rejecting queue comparison."""
import ast
import json
from pathlib import Path
from pathlib import PurePath
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from docker_scope_guard import command_values, python_heredocs

SCRIPT = Path('/home/cash/work_space/private/aletheia/scripts/monitoring/verify_otel_collector.py')
DOCKER_SCRIPT = Path('/home/cash/work_space/private/aletheia/scripts/monitoring/verify_docker_source.py')


def direct_multi_ack(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    values = {}

    def path_value(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return values.get(node.id)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.Add)):
            left, right = path_value(node.left), path_value(node.right)
            if left is not None and right is not None:
                return str(PurePath(left) / right) if isinstance(node.op, ast.Div) else left + right
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ('Path', 'PurePath', 'str') and len(node.args) == 1:
                return path_value(node.args[0])
            if isinstance(node.func, ast.Attribute):
                base = path_value(node.func.value)
                args = [path_value(arg) for arg in node.args]
                if base is not None and all(arg is not None for arg in args):
                    try:
                        if node.func.attr == 'with_suffix' and len(args) == 1:
                            return str(PurePath(base).with_suffix(args[0]))
                        if node.func.attr == 'with_name' and len(args) == 1:
                            return str(PurePath(base).with_name(args[0]))
                        if node.func.attr == 'joinpath':
                            return str(PurePath(base).joinpath(*args))
                    except ValueError:
                        pass
        return None

    def executable_nodes(node):
        # Definitions and quoted strings do not execute a write at declaration.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return
        yield node
        for child in ast.iter_child_nodes(node):
            yield from executable_nodes(child)

    def multi(path):
        return path is not None and re.fullmatch(r'docker-status-multi-homepage.*\.browser-done\.json', PurePath(path).name) is not None

    for node in executable_nodes(tree):
        if isinstance(node, ast.Assign):
            value = path_value(node.value)
            for target in node.targets:
                if isinstance(target, ast.Name):
                    values[target.id] = value
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in ('write_text', 'write_bytes') and multi(path_value(func.value)):
            return True
        if isinstance(func, ast.Name) and func.id == 'open':
            path = path_value(node.args[0]) if node.args else None
            mode = path_value(node.args[1]) if len(node.args) > 1 else 'r'
        elif isinstance(func, ast.Attribute) and func.attr == 'open':
            path = path_value(func.value)
            mode = path_value(node.args[0]) if node.args else 'r'
        else:
            continue
        for keyword in node.keywords:
            if keyword.arg == 'mode':
                mode = path_value(keyword.value)
            elif keyword.arg == 'file':
                path = path_value(keyword.value)
        if multi(path) and mode is not None and any(char in mode for char in 'wax+'):
            return True
    return False


def protected(source):
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'verify')
    for node in ast.walk(function):
        if not isinstance(node, ast.If):
            continue
        names = {item.id for item in ast.walk(node.test) if isinstance(item, ast.Name)}
        if 'normalized_message' not in names or 'actual_message' not in names:
            continue
        saved = False
        for item in node.body:
            if isinstance(item, ast.Assign):
                strings = {child.value for child in ast.walk(item) if isinstance(child, ast.Constant) and isinstance(child.value, str)}
                saved = {'comparison_mismatch', 'actual', 'expected', 'signal'} <= strings
            if isinstance(item, ast.Raise) and saved:
                return True
    return False


def docker_lifecycle_protected(source):
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'lifecycle_rows']
    if len(functions) != 1:
        return False
    function = functions[0]
    nodes = list(ast.walk(function))
    expected = ast.parse('{"receipt_id":str(row[0]),"accepted":row[1],"rejected":row[2],"canonical_base64":base64.b64encode(row[3]).decode()}', mode='eval').body
    reads_line = append_line = fetch_line = save_line = None
    for node in nodes:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
            if (isinstance(target, ast.Name) and target.id == 'reads'
                    and isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                    and isinstance(value.func.value, ast.Name) and value.func.value.id == 'proof'
                    and value.func.attr == 'setdefault' and len(value.args) == 2
                    and isinstance(value.args[0], ast.Constant) and value.args[0].value == 'receipt_reads'
                    and isinstance(value.args[1], ast.List) and not value.args[1].elts):
                reads_line = node.lineno
            if (isinstance(target, ast.Name) and target.id == 'rows'
                    and isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                    and value.func.attr == 'fetchall'
                    and any(isinstance(item, ast.Constant) and isinstance(item.value, str)
                            and 'select id,accepted,rejected,canonical' in item.value.lower()
                            and 'limit 9' in item.value.lower() for item in ast.walk(value))):
                fetch_line = node.lineno
            if (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                    and target.value.id == 'frame' and isinstance(target.slice, ast.Constant)
                    and target.slice.value == 'rows' and isinstance(value, ast.ListComp)
                    and len(value.generators) == 1):
                generator = value.generators[0]
                if (isinstance(generator.target, ast.Name) and generator.target.id == 'row'
                        and isinstance(generator.iter, ast.Name) and generator.iter.id == 'rows'
                        and not generator.ifs and not generator.is_async
                        and ast.dump(value.elt) == ast.dump(expected)):
                    save_line = node.lineno
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == 'append'
                and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == 'reads'
                and len(node.value.args) == 1 and isinstance(node.value.args[0], ast.Name)
                and node.value.args[0].id == 'frame'):
            append_line = node.lineno
    if None in (reads_line, append_line, fetch_line, save_line):
        return False
    # The frame must reach the output proof, and retain all four raw columns,
    # before any explicit rejection or early return can discard the temporary DB.
    if not reads_line < append_line < fetch_line < save_line:
        return False
    if any(isinstance(node, (ast.Raise, ast.Return)) and node.lineno < save_line for node in nodes):
        return False
    # Require unconditional capture in the function body; a success-only branch
    # cannot provide evidence for a failed comparison.
    direct_lines = {node.lineno for node in function.body}
    return {reads_line, append_line, save_line} <= direct_lines


def main():
    payload = json.load(sys.stdin)
    if payload.get('tool_name') in ('Bash', 'exec_command', 'functions.exec_command'):
        for command in command_values(payload.get('tool_input', {})):
            if any(direct_multi_ack(body) for body in python_heredocs(command)):
                print('Docker multi 瀏覽器確認檔只能由固定入口產生：verify_docker_source.py --ack-browser --output <本輪輸出JSON>；不要即興直接寫 browser-done。', file=sys.stderr)
                return 2
    serialized = json.dumps(payload)
    if 'verify_docker_source.py' in serialized and '--status-lifecycle' in serialized:
        try:
            allowed = docker_lifecycle_protected(DOCKER_SCRIPT.read_text())
        except (OSError, SyntaxError, StopIteration):
            allowed = False
        if not allowed:
            print('Docker 狀態恢復比較須先把每次 LIMIT 9 的原始收據四欄保存到 receipt_reads，再拒絕比較；先補證據，不啟動新輪。', file=sys.stderr)
            return 2
    if 'verify_otel_collector.py' not in json.dumps(payload):
        return 0
    try:
        allowed = protected(SCRIPT.read_text())
    except (OSError, SyntaxError, StopIteration):
        allowed = False
    if not allowed:
        print('標準資料比較失敗前必須保存實際與預期內容；先補診斷，不重跑。', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
