#!/usr/bin/env python3
import argparse
from datetime import datetime
import fcntl
import os
from pathlib import Path
import subprocess
import sys

STATE = Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'docker-expire'
LIMIT = 50
FORMS = ('%Y-%m-%d', '%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S')


def docker(*args):
    return subprocess.run(['docker', *args], capture_output=True, text=True, timeout=120)


def parse(value):
    for form in FORMS:
        try:
            return datetime.strptime(value, form)
        except ValueError:
            pass
    return None


def listing(kind):
    if kind == 'container':
        result = docker('ps', '-a', '--filter', 'label=expire', '--format', '{{.ID}}\t{{.Names}}\t{{.Label "expire"}}')
    else:
        result = docker('volume', 'ls', '--filter', 'label=expire', '--format', '{{.Name}}\t{{.Name}}\t{{.Label "expire"}}')
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return [line.split('\t') for line in result.stdout.splitlines() if line]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    apply = parser.parse_args().apply
    STATE.mkdir(parents=True, exist_ok=True)
    lock = open(STATE / 'lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print('已有回收執行中，本次略過')
        return 0
    now = datetime.now()
    log = open(STATE / 'reaper.log', 'a')
    failed = removed = 0
    for kind in ('container', 'volume'):
        for ident, name, value in listing(kind):
            if value == 'never':
                continue
            when = parse(value)
            if when is None:
                print(f'略過 {kind} {name}：expire 值無法解析（{value}）')
                continue
            if when > now:
                continue
            if removed + failed >= LIMIT:
                print(f'已達單次上限 {LIMIT}，其餘留待下次')
                return 1 if failed else 0
            line = f'{now.isoformat(timespec="seconds")} {kind} {name} expire={value}'
            if not apply:
                print('到期（未刪除）', line)
                continue
            result = docker('rm', '-f', '-v', ident) if kind == 'container' else docker('volume', 'rm', ident)
            if result.returncode == 0:
                removed += 1
                print('已刪除', line)
                log.write('removed ' + line + '\n')
            else:
                failed += 1
                print('刪除失敗', line, result.stderr.strip(), file=sys.stderr)
                log.write('failed ' + line + ' ' + result.stderr.strip() + '\n')
    print(f'完成：刪除 {removed}、失敗 {failed}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
