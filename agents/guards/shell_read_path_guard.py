"""Bounded preflight for literal shell file reads; dynamic commands fail open."""
import os
from pathlib import Path
import shlex


def missing_shell_read(text, base):
    if len(text) > 65536 or "<<" in text:
        return False
    lines = text.splitlines()
    if len(lines) > 32:
        return False
    parsed = []
    for line in lines:
        try:
            lexer = shlex.shlex(line, posix=True, punctuation_chars='|;&<>')
            lexer.whitespace_split = True
            words = list(lexer)
        except ValueError:
            return False
        if not words:
            continue
        groups = [[]]
        for word in words:
            if word in ('|', ';', '&&', '||'):
                if not groups[-1]:
                    return False
                groups.append([])
            elif word and all(c in '|;&<>' for c in word):
                return False
            else:
                groups[-1].append(word)
        if not groups[-1]:
            groups.pop()
        for words in groups:
            name = os.path.basename(words[0])
            if name not in ('rg', 'sed', 'cat', 'head', 'tail'):
                return False
            if any(any(c in w for c in ('$', '`')) for w in words):
                return False
            parsed.append((name, words[1:]))
    checked = 0
    for name, args in parsed:
        values = []
        index = 0
        pattern_seen = name != 'rg'
        script_seen = name != 'sed'
        while index < len(args):
            word = args[index]
            index += 1
            if word == '--files':
                values = []
                break
            if word in ('-g', '--glob', '-e', '--regexp', '-n', '-c'):
                if (word == '-n' and name in ('rg', 'sed', 'cat')) or (word == '-c' and name == 'rg'):
                    continue
                if index >= len(args):
                    return False
                if name == 'rg' and word in ('-e','--regexp'):
                    pattern_seen = True
                if name == 'sed' and word == '-e':
                    script_seen = True
                index += 1
                continue
            if name in ('head', 'tail') and word.startswith('-') and word[1:].isdigit():
                continue
            if word.startswith('-'):
                if word not in ('--', '-n', '-q', '-v', '-H', '--line-number', '--no-heading', '--quiet'):
                    return False
                continue
            if not pattern_seen:
                pattern_seen = True
                continue
            if not script_seen:
                script_seen = True
                continue
            values.append(word)
        for value in values:
            if any(c in value for c in ('*','?','[','~')) or value == '-':
                continue
            checked += 1
            if checked > 32:
                return False
            target = value if os.path.isabs(value) else os.path.join(base, value)
            if not os.path.exists(target):
                return True
    return False


if __name__ == '__main__':
    import argparse
    import subprocess
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument('--cwd', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    options = parser.parse_args()
    argv = options.command
    if argv and argv[0] == '--':
        argv = argv[1:]
    if not argv or os.path.basename(argv[0]) not in ('rg','sed','cat','head','tail'):
        parser.error('only direct read commands are accepted')
    if missing_shell_read(shlex.join(argv), options.cwd):
        print('Literal read target is missing; inspect the file inventory first.', file=sys.stderr)
        sys.exit(2)
    sys.exit(subprocess.run(argv, cwd=options.cwd, timeout=15).returncode)
