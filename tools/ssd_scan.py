#!/usr/bin/env python3
"""Bounded read-only SSD inventory; no delete operation exists."""
import argparse
from collections import deque
import fcntl
import heapq
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import disk_cache_cleanup as cache

HOME = Path.home()
STATE = HOME / '.local/state/ssd-scan'
LABELS = {'candidate': '可清候選', 'review': '需確認', 'protected': '保留',
          'busy': '使用中，保留', 'unknown': '未查明', 'overview': '容量總覽'}
ARTIFACTS = {'target': '編譯產物', 'node_modules': 'JavaScript 套件',
             '.next': '網站編譯產物', '.venv': 'Python 執行環境', '.git': 'Git 歷史資料'}
PROTECTED = {'models', 'model', 'market-data', '_npx', 'ollama', '.git', '.rustup', '.nvm', '.venvs', '.npm', '.bun'}
SCAN_SCOPE = 'home-projects-caches-large-files-system-docker-v1'


def atomic(path, data):
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as f:
        os.fchmod(f.fileno(), 0o600)
        json.dump(data, f, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(f.name, path)


def measure(path, seconds=12):
    """du measures allocated blocks, counts hardlinks once and stays on-device."""
    try:
        if path.is_symlink() or path.resolve() != path:
            return None, '路徑含符號連結，未追蹤', None
        command = ['du', '-sx', '-B1', '--exclude=aletheia-hotfix', '--time', '--time-style=+%s', '--', str(path)]
        done = subprocess.run(command, capture_output=True, text=True, timeout=seconds)
        system_paths = {'/var/cache/apt', '/usr/share/ollama', '/var/log/journal', '/var/crash', '/var/lib/systemd/coredump'}
        if done.returncode and str(path) in system_paths:
            done = subprocess.run(['sudo', '-n'] + command, capture_output=True, text=True, timeout=seconds)
        if done.returncode:
            return None, '量測不完整：權限不足或路徑變更', None
        fields = done.stdout.split('\t', 2)
        return int(fields[0]), None, int(fields[1])
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return None, '量測未完成：' + str(error)[:150], None


def classify(path, refs, known):
    if set(path.parts) & PROTECTED or path.suffix in {'.sqlite', '.db', '.safetensors', '.pth', '.gguf'}:
        return 'protected', '模型、資料庫、歷史資料或已安裝工具；不得自動刪除'
    if not known:
        return 'unknown', '程序檢查不完整，不能判定可清'
    if any(v == str(path) or v.startswith(str(path) + '/') for v in refs):
        return 'busy', '程序仍引用此路徑；保留'
    return 'review', '需核對專案、最後使用時間及保留需求；可重建不代表沒有用途'


def discover(root, deadline, max_entries=800000, max_items=400):
    found, large, errors, count = [], [], [], 0
    device = root.stat().st_dev
    pending, complete = deque([root]), True
    while pending:
        parent = pending.popleft()
        try:
            with os.scandir(parent) as entries:
                for entry in entries:
                    count += 1
                    if count > max_entries or time.monotonic() >= deadline:
                        return found, large, ['探索達到時間或項目上限'], False, count
                    meta = entry.stat(follow_symlinks=False)
                    if entry.name == 'aletheia-hotfix' or stat.S_ISLNK(meta.st_mode) or meta.st_dev != device:
                        continue
                    path = Path(entry.path)
                    if stat.S_ISDIR(meta.st_mode):
                        artifact = entry.name in ARTIFACTS
                        if entry.name == 'target':
                            artifact = (path/'.rustc_info.json').is_file() or (path/'debug').is_dir() or (path/'release').is_dir()
                        if artifact or entry.name in PROTECTED:
                            if len(found) < max_items:
                                found.append((path, ARTIFACTS.get(entry.name, '模型／資料／工具')))
                            else:
                                complete = False
                            continue
                        if path == root / '.cache':
                            continue
                        pending.append(path)
                    elif stat.S_ISREG(meta.st_mode) and meta.st_blocks * 512 >= 536870912:
                        item = (meta.st_blocks * 512, str(path))
                        if len(large) < 30:
                            heapq.heappush(large, item)
                        elif item > large[0]:
                            heapq.heapreplace(large, item)
            if parent == root:
                priority = {'work_space': 100, 'orca': 90, 'services': 80, 'Documents': 70, '.local': 60}
                pending = deque(sorted(pending, key=lambda p: priority.get(p.name, 0), reverse=True))
        except OSError:
            if len(errors) < 30:
                errors.append('無法完整讀取：' + str(parent))
            complete = False
    return found, large, errors, complete, count


def sanitize_docker(data):
    allowed = {'ID', 'Name', 'Names', 'Repository', 'Tag', 'Image', 'Size',
               'SharedSize', 'UniqueSize', 'Links', 'Containers', 'CreatedAt',
               'LastUsedAt', 'InUse', 'UsageCount', 'Type', 'State', 'Status'}
    return {category: [{key: value for key, value in item.items() if key in allowed}
                       for item in data.get(category, [])]
            for category in ['Images', 'Containers', 'Volumes', 'BuildCache']}


def compare(row, old):
    previous = old.get(row['path'])
    row['delta_bytes'] = None
    if previous and previous.get('bytes') is not None and row.get('bytes') is not None:
        row['delta_bytes'] = row['bytes'] - previous['bytes']
    return row


def record_history(state, report, max_samples=30):
    path = state / 'history.json'
    samples = []
    try:
        if path.stat().st_size <= 2_000_000:
            stored = json.loads(path.read_text())
            if stored.get('version') == 1 and isinstance(stored.get('samples'), list):
                samples = stored['samples'][-max_samples:]
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        pass

    current = {
        'finished_at': report['finished_at'],
        'scan_scope_id': report['scan_scope_id'],
        'device_id': report['root_filesystem']['device_id'],
        'used_bytes': report['root_filesystem']['used_bytes'],
    }
    growth = {'status': 'unknown', 'reason': '沒有同裝置、同範圍的連續前一筆樣本'}
    if samples:
        previous = samples[-1]
        same_source = (previous.get('device_id') == current['device_id'] and
                       previous.get('scan_scope_id') == current['scan_scope_id'])
        chronological = previous.get('finished_at', current['finished_at']) < current['finished_at']
        if same_source and chronological and isinstance(previous.get('used_bytes'), int):
            growth = {
                'status': 'available',
                'previous_finished_at': previous['finished_at'],
                'used_delta_bytes': current['used_bytes'] - previous['used_bytes'],
            }
    report['growth'] = growth
    samples.append(current)
    atomic(path, {'version': 1, 'max_samples': max_samples, 'samples': samples[-max_samples:]})


def run(state=STATE, home=HOME, budget=480):
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    if state.is_symlink() or state.resolve() != state:
        raise ValueError('Unsafe scan state path')
    with (state / 'lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'status': 'running', 'message': '已有掃描正在執行'}
        started, deadline = time.time(), time.monotonic() + budget
        previous_report = {}
        try:
            p = state / 'report.json'
            if p.stat().st_size <= 2000000:
                previous_report = json.loads(p.read_text())
        except FileNotFoundError:
            pass
        rows, notes = [], []
        fs = os.statvfs('/')
        report = {'version': 2, 'started_at': started, 'status': 'running',
                  'items': rows, 'notes': notes, 'deletes_files': False,
                  'scan_scope_id': f'{os.stat("/").st_dev}:{SCAN_SCOPE}',
                  'root_filesystem': {'path': '/', 'device_id': os.stat('/').st_dev,
                                      'total_bytes': fs.f_blocks * fs.f_frsize,
                                      'used_bytes': (fs.f_blocks - fs.f_bfree) * fs.f_frsize,
                                      'free_bytes': fs.f_bavail * fs.f_frsize}}
        previous = {}
        if (previous_report.get('scan_scope_id') == report['scan_scope_id'] and
                previous_report.get('root_filesystem', {}).get('device_id') == report['root_filesystem']['device_id']):
            previous = {r['path']: r for r in previous_report.get('items', [])}

        def progress(phase):
            atomic(state / 'status.json', {'status': 'running', 'started_at': started,
                                          'phase': phase, 'items_done': len(rows)})

        def add(path, kind, status='overview', reason='', size=None, measured=False):
            if any(r['path'] == str(path) for r in rows):
                return
            if path.exists() and path.stat().st_dev != home.stat().st_dev:
                size, error, modified = None, '位於其他掛載，未計入本機 SSD', None
            elif time.monotonic() >= deadline:
                size, error, modified = None, '總掃描時間已達上限', None
            elif not measured:
                size, error, modified = measure(path, max(0.1, min(12, deadline-time.monotonic())))
            else:
                error, modified = None, None
            if error:
                status, reason = 'unknown', error
            row = {'path': str(path), 'kind': kind, 'bytes': size,
                   'status': status, 'status_label': LABELS[status], 'reason': reason, 'last_modified_at': modified}
            rows.append(compare(row, previous))
            progress(kind)

        progress('檢查程序與固定快取')
        refs, families, known = set(), set(), False
        try:
            refs, families = cache.snapshot()
            known = True
        except (OSError, RuntimeError, subprocess.SubprocessError) as error:
            notes.append('程序檢查未完成：' + str(error)[:200])
        for profile, (suffix, family) in cache.PROFILES.items():
            path = home / suffix
            if not path.exists():
                continue
            try:
                if not known:
                    raise RuntimeError('程序檢查不完整')
                r = cache.clean(profile, False, home, refs, families)
                eligible = r['status'] == 'candidate'
                add(path, '已登記快取', 'candidate' if eligible else ('busy' if '程序使用中' in r.get('reason', '') else 'protected'),
                    '白名單與程序檢查通過；清理前仍須重新確認' if eligible else r.get('reason', '保留'),
                    size=r.get('bytes_before'), measured=eligible)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                add(path, '已登記快取', 'unknown', str(error)[:200])
        progress('探索專案與大型檔案')
        found, large, errors, complete, entries = discover(home, min(deadline, time.monotonic()+60))
        notes.extend(errors)
        report.update(discovery_complete=complete, discovery_entries=entries)
        for path, kind in found:
            status, reason = classify(path, refs, known)
            add(path, kind, status, reason)
        for size, path in sorted(large, reverse=True):
            status, reason = classify(Path(path), refs, known)
            add(Path(path), '大型檔案', status, reason, size, True)
        progress('容量總覽與系統目錄')
        for parent in [home, home/'.cache', home/'.local/share']:
            try:
                children = sorted(parent.iterdir())[:128]
            except OSError:
                notes.append('未能列出：'+str(parent))
                continue
            for path in children:
                if path.is_dir() and not path.is_symlink():
                    add(path, '容量總覽')
        for name in ['/var/log/journal', '/var/cache/apt', '/var/crash', '/var/lib/systemd/coredump', '/usr/share/ollama']:
            path = Path(name)
            if path.exists():
                add(path, '系統資料', 'protected' if name == '/usr/share/ollama' else 'review', '需使用原服務管理；不直接刪除目錄')
        report['scan_scope'] = '家目錄專案、快取與大型檔案；系統日誌、套件快取與 Docker 容量；不跨掛載、不追蹤連結、不掃描 aletheia-hotfix；容量非 SSD 全檔案清冊'
        progress('Docker 容量')
        try:
            done = subprocess.run(['docker', 'system', 'df', '-v', '--format', '{{json .}}'],
                                  capture_output=True, text=True, timeout=30)
            if done.returncode or len(done.stdout) > 1000000:
                raise RuntimeError('Docker 容量未完整取得')
            report['docker'] = sanitize_docker(json.loads(done.stdout))
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            report['docker'] = None
            notes.append('Docker：'+str(error)[:200])
        notes.extend(['總覽與細項互相包含，請勿相加；硬連結跨項目可能重複，磁碟共享資料也會影響實際回收量。',
                      '大型或閒置不等於可刪；模型、資料庫、個人檔案及已安裝工具不自動清理。',
                      'Docker 可回收不代表資料卷可刪；未使用資料卷可能保存重要資料。',
                      '增長只比較兩次都完整取得的相同路徑；首次或未完成的量測不當成零。', '最後修改取完整子目錄的最新修改時間；不等於最後使用，閒置與用途仍需確認。'])
        report.update(status='completed' if complete and report.get('docker') is not None and all(r['bytes'] is not None for r in rows) else 'partial',
                      finished_at=time.time(), candidate_bytes=sum(r['bytes'] or 0 for r in rows if r['status']=='candidate'))
        record_history(state, report)
        atomic(state / 'report.json', report)
        atomic(state / 'status.json', {'status': report['status'], 'started_at': started,
                                      'finished_at': report['finished_at'], 'items_done': len(rows), 'phase': '掃描結束'})
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['scan', 'status', 'report'], nargs='?', default='scan')
    args = parser.parse_args()
    if args.action == 'scan':
        try:
            result = run()
            print(json.dumps({k: result.get(k) for k in ['status', 'candidate_bytes', 'finished_at']}, ensure_ascii=False))
        except Exception as error:
            if STATE.is_dir():
                atomic(STATE / 'status.json', {'status': 'failed', 'error': str(error)[:300]})
            raise
    else:
        path = STATE / (args.action + '.json')
        if not path.exists():
            print(json.dumps({'status': 'not_run'}))
        elif path.stat().st_size <= 2000000:
            print(path.read_text())
        else:
            raise ValueError('Report exceeds size limit')


if __name__ == '__main__':
    main()
