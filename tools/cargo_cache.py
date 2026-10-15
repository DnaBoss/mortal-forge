#!/usr/bin/env python3
"""Bounded Rust cache adoption; deletion requires an explicit CLI --apply."""
import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import signal
import shutil
import subprocess
import sys
import tempfile
import time

ALLOWED = {'.rustc_info.json', 'CACHEDIR.TAG', 'debug', 'release', 'tmp',
           '.cargo-lock', 'doc', 'package', 'criterion',
           '.future-incompat-report.json'}


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          capture_output=True, text=True, timeout=2).stdout


def common(repo):
    return Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir').strip())


def worktrees(repo):
    fields = git(repo, 'worktree', 'list', '--porcelain', '-z').split('\0')
    roots = [Path(f[9:]) for f in fields if f.startswith('worktree ')]
    if len(roots) > 200:
        raise ValueError('Worktree limit exceeded')
    return [p for p in roots if (p / 'Cargo.toml').is_file()]


def registration(repo):
    p = common(repo) / 'cargo-cache.json'
    if not p.exists():
        return {}
    if p.stat().st_size > 100000:
        raise ValueError('Registration too large')
    return json.loads(p.read_text())


def atomic(p, data):
    with tempfile.NamedTemporaryFile(mode='w', dir=p.parent, delete=False) as f:
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(f.name, p)


@contextlib.contextmanager
def locked(repo):
    with (common(repo) / 'cargo-cache.lock').open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def scan_processes(uid):
    """Inspect same-user process references; uncertainty prevents deletion."""
    refs = set()
    deadline = time.monotonic() + 10
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != uid:
                continue
            if time.monotonic() > deadline:
                raise RuntimeError('Process scan deadline exceeded')
            for entry in [proc / 'exe', proc / 'cwd', *list((proc / 'fd').iterdir())]:
                try:
                    value = os.readlink(entry).removesuffix(' (deleted)')
                    if value.startswith('/'):
                        refs.add(value)
                except FileNotFoundError:
                    continue
            for line in (proc / 'maps').read_text().splitlines():
                parts = line.split(maxsplit=5)
                if len(parts) == 6 and parts[5].startswith('/'):
                    refs.add(parts[5].removesuffix(' (deleted)'))
            exe = os.readlink(proc / 'exe').removesuffix(' (deleted)')
            if Path(exe).name in {'cargo', 'rustc', 'rustdoc'}:
                cwd = Path(os.readlink(proc / 'cwd'))
                for ancestor in [cwd, *cwd.parents]:
                    if (ancestor / 'Cargo.toml').exists():
                        refs.add(str(ancestor / 'target'))
                        break
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (PermissionError, OSError) as exc:
            raise RuntimeError(f'Cannot inspect process {proc.name}: {exc}') from exc
    return refs


def in_use():
    try:
        return scan_processes(os.getuid())
    except RuntimeError:
        # Elevated reading only; all filesystem mutations stay unprivileged.
        done = subprocess.run(['sudo', '-n', '/usr/bin/python3',
                               str(Path(__file__).resolve()), 'process-refs',
                               '--uid', str(os.getuid())], check=True,
                              capture_output=True, text=True, timeout=15)
        if len(done.stdout) > 16000000:
            raise RuntimeError('Process reference output too large')
        data = json.loads(done.stdout)
        if not isinstance(data, list) or any(not isinstance(v, str) for v in data):
            raise RuntimeError('Invalid process reference output')
        return set(data)


def busy(target, refs):
    return any(v == str(target) or v.startswith(str(target) + '/') for v in refs)


def audit(repo):
    targets = [p / 'target' for p in worktrees(repo)]
    reg = registration(repo)
    keeper = reg.get('keeper')
    real = [str(p) for p in targets if p.is_dir() and not p.is_symlink()]
    deferred = reg.get('skipped', [])
    duplicates = [p for p in real if p != keeper and p not in deferred]
    if not keeper and len(real) <= 1:
        duplicates = []
    invalid = [str(p) for p in targets if p.is_symlink() and str(p.resolve()) != keeper]
    return {'repo': str(common(repo)), 'keeper': keeper, 'duplicates': duplicates,
            'invalid_links': invalid, 'skipped': [p for p in deferred if p in real],
            'worktrees': len(targets), 'timestamp': time.time()}


def nested_target(path):
    # A sub target dir such as one made by `--target-dir target/mutation`.
    return (path.is_dir() and not path.is_symlink()
            and (path / '.rustc_info.json').is_file()
            and (path / 'CACHEDIR.TAG').is_file())


def validate(target):
    if not target.is_dir() or target.is_symlink():
        raise ValueError(f'Expected real target directory: {target}')
    if not (target / '.rustc_info.json').is_file():
        raise ValueError(f'Missing Cargo cache marker: {target}')
    unknown = set(p.name for p in target.iterdir()
                  if p.name not in ALLOWED and not nested_target(p))
    if unknown:
        raise ValueError(f'Unknown cache content: {target}: {sorted(unknown)}')
    if git(target.parent, 'ls-files', '--', 'target').strip():
        raise ValueError(f'Tracked files in target: {target}')


def ignore_links(repo):
    location = common(repo) / 'info/exclude'
    location.parent.mkdir(parents=True, exist_ok=True)
    old = location.read_text() if location.exists() else ''
    if '/target' not in old.splitlines():
        with location.open('a') as out:
            out.write('\n# Shared Cargo cache links\n/target\n')


def adopt(repo, keeper, apply=True, allowed=None, auto_cleanup=False):
    repo, keeper = Path(repo).resolve(), Path(keeper).absolute()
    with locked(repo):
        targets = [p / 'target' for p in worktrees(repo)]
        if keeper not in targets or keeper.is_symlink():
            raise ValueError('Keeper must be a real target of this repository')
        for target in targets:
            if target.is_symlink():
                if target.resolve() != keeper:
                    raise ValueError(f'Unexpected target symlink: {target}')
            elif target.exists():
                validate(target)
        validate(keeper)
        refs = in_use()
        result = {'keeper': str(keeper), 'skipped': [], 'removed': [], 'linked': [],
                  'apply': apply, 'timestamp': time.time(), 'auto_cleanup': auto_cleanup}
        if apply:
            ignore_links(repo)
            atomic(common(repo) / 'cargo-cache-receipt.json', result)
        for target in targets:
            if target == keeper or target.is_symlink():
                continue
            if allowed is not None and str(target) not in allowed:
                continue
            if target.exists() and busy(target, refs):
                result['skipped'].append(str(target))
                continue
            if apply:
                refs = in_use()
                if busy(target, refs):
                    result['skipped'].append(str(target))
                    continue
                if target.exists():
                    validate(target)
                    shutil.rmtree(target)
                    result['removed'].append(str(target))
                target.symlink_to(keeper, target_is_directory=True)
                result['linked'].append(str(target))
                atomic(common(repo) / 'cargo-cache-receipt.json', result)
            else:
                result['linked'].append(str(target))
        if apply:
            atomic(common(repo) / 'cargo-cache.json', result)
        return result


def blocked(event, reason):
    if event == 'PreToolUse':
        return {'hookSpecificOutput': {'hookEventName': event,
                'permissionDecision': 'deny', 'permissionDecisionReason': reason}}
    return {'decision': 'block', 'reason': reason}


def initialize(repo):
    """Link missing targets without deleting or replacing any existing data."""
    with locked(repo):
        ignore_links(repo)
        roots = worktrees(repo)
        reg = registration(repo)
        keeper = reg.get('keeper')
        if not keeper:
            real = [p / 'target' for p in roots if (p / 'target').exists()]
            if len(real) > 1 or any(p.is_symlink() for p in real):
                return
            keeper = str(real[0] if real else roots[0] / 'target')
            Path(keeper).mkdir(exist_ok=True)
            atomic(common(repo) / 'cargo-cache.json',
                   {'keeper': keeper, 'skipped': [], 'timestamp': time.time()})
        if Path(keeper) not in [p / 'target' for p in roots] or not Path(keeper).is_dir():
            raise ValueError('Registered keeper is missing; relocate cache before removing worktree')
        for root in roots:
            target = root / 'target'
            if not target.exists() and not target.is_symlink():
                target.symlink_to(keeper, target_is_directory=True)


def spawn_cleanup(repo):
    log = common(repo) / 'cargo-cache-worker.json'
    with (common(repo) / 'cargo-cache-worker.lock').open('a') as lease:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        with log.open('a') as out:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                              'cleanup-registered', '--repo', str(repo)],
                             stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                             start_new_session=True, close_fds=True,
                             pass_fds=(lease.fileno(),))


def install_hooks(home, guard):
    """Append owned entries; preserve all existing hooks and back up first."""
    result = []
    for relative in ['.claude/settings.json', '.codex/hooks.json']:
        location = Path(home) / relative
        data = json.loads(location.read_text()) if location.exists() else {}
        before = json.dumps(data, ensure_ascii=False, indent=2)
        hooks = data.setdefault('hooks', {})
        for event in ['SessionStart', 'PreToolUse', 'Stop', 'SessionEnd']:
            groups = hooks.setdefault(event, [])
            command = '/usr/bin/python3 ' + str(guard)
            if any(h.get('command') == command for g in groups for h in g.get('hooks', [])):
                continue
            group = {'hooks': [{'type': 'command', 'command': command,
                               'timeout': 3 if event == 'SessionEnd' else 8}]}
            if event == 'PreToolUse' and relative.startswith('.claude'):
                group['matcher'] = 'Bash'
            groups.append(group)
        after = json.dumps(data, ensure_ascii=False, indent=2)
        if before != after:
            location.parent.mkdir(parents=True, exist_ok=True)
            if location.exists():
                backup = location.with_name(location.name + '.cargo-cache-backup-' + str(time.time_ns()))
                shutil.copy2(location, backup)
            atomic(location, data)
            result.append(str(location))
    return {'updated': result}


def hook(payload):
    event = payload.get('hook_event_name', '')
    tool_input = payload.get('tool_input') or {}
    cwd = Path(tool_input.get('workdir') or tool_input.get('cwd') or payload.get('cwd') or os.getcwd())
    command = tool_input.get('command', tool_input.get('cmd', ''))
    if isinstance(command, list):
        command = command[-1] if len(command) >= 3 and command[-2] in {'-c', '-lc'} else ' '.join(command)
    command = str(command)
    is_build = bool(re.search(r'\bcargo\b', command))
    if event == 'PreToolUse' and not is_build:
        return {}
    try:
        for part in re.split(r'&&|;|\n', command):
            words = shlex.split(part)
            if len(words) == 2 and words[0] == 'cd':
                cwd = (cwd / Path(words[1]).expanduser()).resolve()
        roots = worktrees(cwd)
        if not roots:
            return {}
        if event in {'SessionStart', 'PreToolUse'}:
            initialize(cwd)
        report = audit(cwd)
        if event == 'SessionEnd':
            atomic(common(cwd) / 'cargo-cache-last.json', report)
            state = Path.home() / '.local/state/cargo-cache'
            state.mkdir(parents=True, exist_ok=True)
            atomic(state / 'status.json', report)
            reg = registration(cwd)
            if reg.get('auto_cleanup') and report['skipped']:
                spawn_cleanup(cwd)
            return {}
        if event == 'PreToolUse':
            words = shlex.split(command)
            overrides = []
            for index, word in enumerate(words):
                if word.startswith(('CARGO_TARGET_DIR=', '--target-dir=')):
                    overrides.append(word.split('=', 1)[1])
                elif word == '--target-dir' and index + 1 < len(words):
                    overrides.append(words[index + 1])
            keeper = report['keeper']
            if any(str((cwd / v).resolve()) != keeper for v in overrides):
                return blocked(event, 'Use the registered shared Cargo target; a separate cache is forbidden')
            current = Path(git(cwd, 'rev-parse', '--show-toplevel').strip()) / 'target'
            if str(current) in report['skipped'] and not overrides:
                return blocked(event, 'This cache is retained for a running process. Compile with CARGO_TARGET_DIR=' + str(keeper))
        problems = report['duplicates'] + report['invalid_links']
        if problems and event in {'Stop', 'PreToolUse'}:
            reason = 'Rust compilation caches must be shared; inspect cargo-cache audit and adopt safely: ' + ', '.join(problems[:3])
            return blocked(event, reason)
        return {}
    except subprocess.CalledProcessError:
        return {}
    except Exception as exc:
        if event in {'Stop', 'PreToolUse'}:
            return blocked(event, f'Cargo cache inspection failed: {exc}')
        return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['audit', 'adopt', 'hook', 'process-refs', 'cleanup-registered', 'install-hooks'])
    parser.add_argument('--repo', default='.')
    parser.add_argument('--keeper')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--uid', type=int)
    parser.add_argument('--allow-session-cleanup', action='store_true')
    args = parser.parse_args()
    try:
        if args.action == 'install-hooks':
            guard = Path(__file__).resolve().parents[1] / 'agents/guards/cargo_cache_guard.py'
            if not guard.is_file():
                raise ValueError('Guard missing')
            result = install_hooks(Path.home(), guard)
        elif args.action == 'process-refs':
            if args.uid is None:
                raise ValueError('--uid required')
            result = sorted(scan_processes(args.uid))
        elif args.action == 'cleanup-registered':
            signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Cleanup deadline exceeded')))
            signal.alarm(120)
            reg = registration(Path(args.repo))
            if not reg.get('auto_cleanup'):
                raise ValueError('Session cleanup is not authorized for this repository')
            result = adopt(Path(args.repo), Path(reg['keeper']), allowed=set(reg.get('skipped', [])), auto_cleanup=True)
            signal.alarm(0)
        elif args.action == 'hook':
            result = hook(json.loads(sys.stdin.read(100000)))
        elif args.action == 'audit':
            result = audit(Path(args.repo))
        else:
            if not args.keeper:
                raise ValueError('--keeper is required')
            result = adopt(Path(args.repo), Path(args.keeper), args.apply,
                           auto_cleanup=args.allow_session_cleanup)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({'ok': False, 'reason': str(exc)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
