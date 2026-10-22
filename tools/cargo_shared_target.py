#!/usr/bin/env python3
"""cargo wrapper: every worktree of one Git repository builds into one target.

Installed as ~/.local/bin/cargo, ahead of ~/.cargo/bin in PATH, so terminals,
IDEs, rust-analyzer and AI agents all pass through it. It sets
CARGO_TARGET_DIR to the repository's single target and then execs the real
cargo. It never deletes anything.

Target choice, per Cargo workspace path inside the repository:
  1. the keeper registered in <git-common-dir>/cargo-cache.json (root workspace)
  2. otherwise <main worktree>/<workspace path>/target

An explicit --target-dir / CARGO_TARGET_DIR is kept when it is inside that
target, remapped when it points inside this worktree's own target, and
refused otherwise. CARGO_ALLOW_SEPARATE_TARGET=1 bypasses the refusal.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

MARK = 'CARGO_SHARED_TARGET'
PASS_THROUGH = {'install', 'uninstall', 'search', 'login', 'logout', 'owner', 'yank'}


def real_cargo():
    me = Path(__file__).resolve()
    for entry in os.environ.get('PATH', '').split(os.pathsep):
        candidate = Path(entry or '.') / 'cargo'
        try:
            if candidate.resolve() == me or not os.access(candidate, os.X_OK) or candidate.is_dir():
                continue
        except OSError:
            continue
        return str(candidate)
    return None


def run(*args, cwd=None):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=10)
    return result.stdout.strip() if result.returncode == 0 else None


def option(args, name):
    """Value of --name X or --name=X before a bare '--'."""
    for index, word in enumerate(args):
        if word == '--':
            break
        if word == name and index + 1 < len(args):
            return index, args[index + 1]
        if word.startswith(name + '='):
            return index, word.split('=', 1)[1]
    return None, None


def subcommand(args):
    for word in args:
        if word == '--':
            return None
        if not word.startswith(('-', '+')):
            return word
    return None


def shared_target(cargo, args, cwd):
    """Return (shared target, this worktree's default target) or None."""
    _, manifest = option(args, '--manifest-path')
    start = (cwd / manifest).resolve().parent if manifest else cwd
    if not start.is_dir():
        return None
    top = run('git', '-C', str(start), 'rev-parse', '--show-toplevel')
    common = run('git', '-C', str(start), 'rev-parse', '--path-format=absolute', '--git-common-dir')
    if not top or not common:
        return None
    locate = [cargo, 'locate-project', '--workspace', '--message-format', 'plain']
    if manifest:
        locate += ['--manifest-path', str((cwd / manifest).resolve())]
    found = run(*locate, cwd=start)
    if not found:
        return None
    workspace = Path(found).resolve().parent
    top = Path(top).resolve()
    try:
        rel = workspace.relative_to(top)
    except ValueError:
        return None
    own = top / rel / 'target'
    registration = Path(common) / 'cargo-cache.json'
    if rel == Path('.') and registration.is_file():
        try:
            keeper = json.loads(registration.read_text()).get('keeper')
        except (OSError, ValueError):
            keeper = None
        if keeper and Path(keeper).is_dir():
            return Path(keeper).resolve(), own
    listing = run('git', '-C', str(start), 'worktree', 'list', '--porcelain') or ''
    roots = [Path(line[9:]) for line in listing.splitlines() if line.startswith('worktree ')]
    main = roots[0] if roots and roots[0].is_dir() else top
    target = main / rel / 'target'
    return (target.resolve() if target.exists() else target), own


def inside(path, root):
    return path == root or root in path.parents


def main():
    args = sys.argv[1:]
    cargo = real_cargo()
    if not cargo:
        print('cargo wrapper: real cargo not found in PATH', file=sys.stderr)
        return 127
    env_value = os.environ.get('CARGO_TARGET_DIR')
    if env_value and os.environ.get(MARK) == env_value:
        os.execv(cargo, [cargo, *args])
    if subcommand(args) in PASS_THROUGH or subcommand(args) is None:
        os.execv(cargo, [cargo, *args])
    cwd = Path.cwd()
    try:
        found = shared_target(cargo, args, cwd)
    except (OSError, subprocess.SubprocessError):
        found = None
    if not found:
        os.execv(cargo, [cargo, *args])
    shared, own = found
    index, flag_value = option(args, '--target-dir')
    requested = flag_value or env_value
    if requested:
        path = Path(os.path.abspath(cwd / Path(requested).expanduser()))
        resolved = path.resolve() if path.exists() else path
        if inside(resolved, shared):
            chosen = resolved
        elif inside(path, own):
            chosen = shared / path.relative_to(own)
        elif os.environ.get('CARGO_ALLOW_SEPARATE_TARGET') == '1':
            os.execv(cargo, [cargo, *args])
        else:
            print(f'cargo wrapper: refused separate target {requested}; this repository builds into {shared}.\n'
                  'Set CARGO_ALLOW_SEPARATE_TARGET=1 only with explicit approval.', file=sys.stderr)
            return 2
        if flag_value:
            args = list(args)
            if args[index] == '--target-dir':
                args[index + 1] = str(chosen)
            else:
                args[index] = '--target-dir=' + str(chosen)
        shared = chosen
    os.environ['CARGO_TARGET_DIR'] = str(shared)
    os.environ[MARK] = str(shared)
    os.execv(cargo, [cargo, *args])


if __name__ == '__main__':
    sys.exit(main())
