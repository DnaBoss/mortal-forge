#!/usr/bin/env python3
import json
import re
import shlex
import sys
from datetime import datetime

SEGMENT = re.compile(r'\n|;|&&|\|\||\||&')
WRAPPERS = {'sudo', 'env', 'time', 'nohup', 'command'}
VALUE_OPTIONS = {'-H', '--host', '--context', '-c', '--config', '--log-level', '-l'}

MESSAGE = (
    '建立 Docker 容器或磁碟區時必須標記回收方式：用 --rm（容器結束就刪），'
    '或加 --label expire=YYYY-MM-DD（或 YYYY-MM-DDTHH:MM），長期服務寫 --label expire=never。'
    '長期會用的東西先重用現有的，不要反覆刪除重建（會耗損 SSD）。'
)
BAD_VALUE = 'expire 的值只能是 never 或 YYYY-MM-DD、YYYY-MM-DDTHH:MM 這類日期時間。'


def valid_expire(value):
    if value == 'never':
        return True
    for form in ('%Y-%m-%d', '%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S'):
        try:
            datetime.strptime(value, form)
            return True
        except ValueError:
            pass
    return False


def docker_subcommand(tokens):
    index = 0
    while index < len(tokens) and (tokens[index] in WRAPPERS or '=' in tokens[index].split('/')[-1] and not tokens[index].startswith('-')):
        index += 1
    if index >= len(tokens) or tokens[index].rsplit('/', 1)[-1] != 'docker':
        return None
    index += 1
    while index < len(tokens) and tokens[index].startswith('-'):
        step = 2 if tokens[index] in VALUE_OPTIONS and tokens[index] != '-l' else 1
        index += step
    return tokens[index:]


def labels(args):
    found = []
    for position, token in enumerate(args):
        if token in ('--label', '-l') and position + 1 < len(args):
            found.append(args[position + 1])
        elif token.startswith('--label='):
            found.append(token[len('--label='):])
    return found


def check(tokens):
    rest = docker_subcommand(tokens)
    if not rest:
        return None
    if rest[0] == 'container':
        rest = rest[1:]
    elif rest[0] == 'volume' and len(rest) > 1 and rest[1] == 'create':
        rest = ['volume-create'] + rest[2:]
    if not rest or rest[0] not in ('run', 'create', 'volume-create'):
        return None
    args = rest[1:]
    expire = [label.split('=', 1)[1] for label in labels(args) if label.startswith('expire=')]
    if expire:
        return None if all(valid_expire(value) for value in expire) else BAD_VALUE
    if rest[0] != 'volume-create' and '--rm' in args:
        return None
    return MESSAGE


def commands(payload):
    stack = [payload]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ('command', 'cmd') and isinstance(item, str):
                    yield item
                elif isinstance(item, (dict, list)):
                    stack.append(item)
        elif isinstance(value, list):
            stack.extend(value)


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    for command in commands(payload):
        for segment in SEGMENT.split(command):
            try:
                tokens = shlex.split(segment)
            except ValueError:
                continue
            problem = check(tokens)
            if problem:
                print(problem, file=sys.stderr)
                return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
