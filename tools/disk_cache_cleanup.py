#!/usr/bin/env python3
"""Fixed cache profiles only. Default is read-only; no models, databases or workspaces."""
import argparse
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time

from cargo_cache import in_use, registration, audit, adopt, validate, worktrees

MAX_ENTRIES = 200_000
PROFILES = {
    'pip-http': ('.cache/pip/http-v2', 'python'),
    'pip-wheels': ('.cache/pip/wheels', 'python'),
    'go-build': ('.cache/go-build', 'go'),
    'npm-downloads': ('.npm/_cacache', 'node'),
    'uv-cache': ('.cache/uv', 'python'),
    'fluke-uv-cache': ('.local/share/fluke-scene-motion-trial/cache/uv', 'python'),
    'pos-rust-cache': ('work_space/newretail/newretail-pos/target', 'rust'),
}


def process_families(words, home):
    families = set()
    if not words:
        return families
    names = [Path(w).name for w in words[:3]]
    if names[0] in {'go', 'compile', 'link'}:
        families.add('go')
    if names[0] in {'cargo', 'rustc', 'rustdoc'}:
        families.add('rust')
    if any(n in {'npm', 'npx', 'npm-cli.js', 'npx-cli.js', 'pnpm', 'yarn', 'corepack'} for n in names):
        families.add('node')
    if any(n in {'pip', 'pip3', 'pip3.14'} for n in names):
        families.add('python')
    if names[0] == 'uv' and any(w in {'pip', 'sync', 'add', 'remove', 'build', 'cache'} for w in words[1:3]):
        families.add('python')
    for suffix, family in PROFILES.values():
        prefix = str(home / suffix)
        if any(word == prefix or word.startswith(prefix + '/') for word in words):
            families.add(family)
    return families


def installers():
    families = set()
    deadline = time.monotonic() + 8
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        if time.monotonic() > deadline:
            raise RuntimeError('程序檢查超過八秒，保留快取')
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            args = proc.joinpath('cmdline').read_bytes()[:65536].split(b'\0')
            words = [a.decode(errors='replace') for a in args if a]
            if not words:
                continue
            families.update(process_families(words, Path.home()))
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (PermissionError, OSError) as error:
            raise RuntimeError('無法完整檢查安裝程序，保留快取') from error
    return families


def snapshot():
    # Reuse the existing bounded /proc + elevated read-only fallback. Never delete as root.
    return in_use(), installers()


def inspect(root):
    deadline, count, size, seen, newest = time.monotonic() + 20, 0, 0, set(), 0
    device = root.lstat().st_dev
    pending = [root]
    while pending:
        path = pending.pop()
        count += 1
        if count > MAX_ENTRIES or time.monotonic() > deadline:
            raise RuntimeError('快取盤點超過二十秒或二十萬項，保留整類')
        meta = path.lstat()
        newest = max(newest, meta.st_mtime)
        if meta.st_uid != os.getuid() or meta.st_dev != device:
            raise ValueError('含其他帳號或掛載位置，保留整類')
        if not (stat.S_ISREG(meta.st_mode) or stat.S_ISDIR(meta.st_mode) or stat.S_ISLNK(meta.st_mode)):
            raise ValueError('含特殊檔案，保留整類')
        identity = (meta.st_dev, meta.st_ino)
        if identity not in seen:
            size += meta.st_blocks * 512
            seen.add(identity)
        if stat.S_ISDIR(meta.st_mode):
            pending.extend(path.iterdir())
    return size, count, newest


def clean(profile, apply, home, refs, families, refresh=None):
    if profile not in PROFILES:
        raise ValueError('不允許的清理類別')
    suffix, family = PROFILES[profile]
    root = home / suffix
    result = {'profile': profile, 'path': str(root), 'status': 'absent', 'bytes_before': 0, 'bytes_after': 0}
    if root.is_symlink() or (root.exists() and root.resolve() != root):
        raise ValueError('快取位置含符號連結，保留整類')
    if not root.exists():
        return result
    if not root.is_dir():
        raise ValueError('快取位置不是目錄')
    original = root.lstat()
    def busy(paths, active):
        return family in active or any(p == str(root) or p.startswith(str(root) + '/') for p in paths)
    if busy(refs, families):
        result.update(status='skipped', reason='程序使用中或套件安裝／編譯中')
        return result
    result['bytes_before'], result['entries'], newest = inspect(root)
    result['bytes_after'] = result['bytes_before']
    if profile == 'pos-rust-cache':
        if not (root / '.rustc_info.json').is_file() or registration(root.parent).get('keeper') != str(root):
            raise ValueError('POS 共用快取標記或登記不符，保留')
        tracked = subprocess.run(['git', '-C', str(root.parent), 'ls-files', '--', 'target'],
                                 check=True, capture_output=True, text=True, timeout=5)
        if tracked.stdout.strip():
            raise ValueError('POS 快取含 Git 追蹤檔，保留')
        result['idle_days'] = round((time.time() - newest) / 86400, 2)
        if result['idle_days'] < 7:
            result.update(status='skipped', reason='POS 最近七天內有編譯，保留共用快取')
            return result
    if not apply:
        result['status'] = 'candidate'
        return result
    if refresh is not None:
        refs, families = refresh()
        if busy(refs, families):
            result.update(status='skipped', reason='執行前重新檢查發現使用中')
            return result
    current = root.lstat()
    if root.is_symlink() or root.resolve() != root or (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino):
        raise ValueError('盤點後快取位置已更換，保留')
    print(json.dumps(dict(result, status='starting'), ensure_ascii=False), flush=True)
    if profile == 'pos-rust-cache':
        executable = shutil.which('cargo')
        if not executable:
            result.update(status='skipped', reason='沒有 cargo 指令，保留')
            return result
        subprocess.run([executable, 'clean', '--manifest-path', str(root.parent / 'Cargo.toml')],
                       check=True, timeout=120)
        # Other worktrees point here; keep the registered directory valid after cargo clean.
        root.mkdir(exist_ok=True)
    elif profile in {'uv-cache', 'fluke-uv-cache'}:
        uv = shutil.which('uv')
        if not uv:
            result.update(status='skipped', reason='沒有 uv 指令，不改用強制刪除')
            return result
        # Native uv retains its in-use lock checks; deliberately omit --force.
        subprocess.run([uv, 'cache', 'clean', '--cache-dir', str(root)], check=True, timeout=90)
    else:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            current = os.fstat(directory)
            if (current.st_dev, current.st_ino) != (original.st_dev, original.st_ino):
                raise ValueError('盤點後快取位置已更換，保留')
            # Pin the checked directory; replacing an ancestor cannot redirect deletion.
            for name in os.listdir(directory):
                meta = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if stat.S_ISDIR(meta.st_mode):
                    shutil.rmtree(name, dir_fd=directory)
                else:
                    os.unlink(name, dir_fd=directory)
        finally:
            os.close(directory)
    result['bytes_after'] = inspect(root)[0] if root.exists() else 0
    result['status'] = 'cleaned'
    return result


def old_rust_duplicates(home, apply):
    repo = home / 'work_space/private/Fluke'
    result = {'profile': 'rust-old-duplicates', 'status': 'absent'}
    if not (repo / '.git').exists():
        return result
    report = audit(repo)
    result['inventory'] = report
    if not apply:
        result['status'] = 'candidate'
        return result
    reg = registration(repo)
    if not reg.get('auto_cleanup'):
        result.update(status='skipped', reason='這個程式庫未授權自動清舊副本')
        return result
    try:
        for tree in worktrees(repo):
            target = tree / 'target'
            if target.is_dir() and not target.is_symlink():
                validate(target)
    except ValueError as error:
        result.update(status='skipped', reason='舊副本不能證明為純編譯快取：' + str(error))
        return result
    result['receipt'] = adopt(repo, Path(reg['keeper']), apply=True,
                              allowed=set(reg.get('skipped', [])), auto_cleanup=True)
    result['status'] = 'cleaned' if result['receipt']['removed'] else 'skipped'
    result['reason'] = '只回收已登記且不在使用的舊副本；共用快取保留'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--rust-old-duplicates', action='store_true')
    args = parser.parse_args()
    if args.rust_old_duplicates:
        try:
            print(json.dumps(old_rust_duplicates(Path.home(), args.apply), ensure_ascii=False))
            return 0
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            print(json.dumps({'profile': 'rust-old-duplicates', 'status': 'failed', 'reason': str(error)}))
            return 1
    failed = False
    for profile in PROFILES:
        try:
            refs, families = snapshot()
            result = clean(profile, args.apply, Path.home(), refs, families, refresh=snapshot)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            result = {'profile': profile, 'status': 'failed', 'reason': str(error)}
            failed = True
        print(json.dumps(result, ensure_ascii=False), flush=True)
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
