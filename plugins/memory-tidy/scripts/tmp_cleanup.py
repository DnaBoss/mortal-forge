#!/usr/bin/env python3
"""Delete stale, unused entries under /tmp (tmpfs here, so stale files hold RAM).

An entry is deleted only when all hold:
  - owned by the current user and not on the skip list
  - no running process has a file, cwd, exe or mapping inside it
  - not the scratch dir of a live Claude session (~/.claude/sessions/<pid>.json)
  - nothing inside it changed for --min-age-hours

Default is a dry run. --apply deletes. Each run appends one JSON line to the log.
"""
import argparse
import json
import os
import shutil
import stat
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

TMP = Path("/tmp")
CLAUDE_TMP_NAME = f"claude-{os.getuid()}"
SKIP_PREFIXES = (".X", ".ICE", ".font-unix", ".XIM", "systemd-private", ".mount_", "tmux-", "ssh-")
LOG = Path.home() / ".local/state/tmp-cleanup/log.jsonl"
WALK_LIMIT = 200_000


@dataclass
class Entry:
    path: str
    newest_mtime: float  # inf when the walk was cut short
    size: int
    session_id: str = ""


@dataclass
class Decision:
    path: str
    action: str  # "delete" or "keep"
    reason: str
    size: int = 0


def decide(entries, in_use, live_sessions, now, min_age_s):
    """Pure selection: no filesystem access."""
    out = []
    for e in entries:
        prefix = e.path.rstrip("/") + "/"
        if any(p == e.path or p.startswith(prefix) for p in in_use):
            out.append(Decision(e.path, "keep", "in_use"))
        elif e.session_id and e.session_id in live_sessions:
            out.append(Decision(e.path, "keep", "live_session"))
        elif now - e.newest_mtime < min_age_s:
            out.append(Decision(e.path, "keep", "recent"))
        else:
            out.append(Decision(e.path, "delete", "stale", e.size))
    return out


def scan_in_use():
    paths = set()
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        base = f"/proc/{pid}"
        for link in ("cwd", "exe"):
            try:
                paths.add(os.readlink(f"{base}/{link}"))
            except OSError:
                pass
        try:
            for fd in os.listdir(f"{base}/fd"):
                try:
                    paths.add(os.readlink(f"{base}/fd/{fd}"))
                except OSError:
                    pass
        except OSError:
            pass
        try:
            with open(f"{base}/maps") as f:
                for line in f:
                    parts = line.split(None, 5)
                    if len(parts) == 6 and parts[5].startswith("/tmp/"):
                        paths.add(parts[5].strip())
        except OSError:
            pass
    return {p.removesuffix(" (deleted)") for p in paths if p.startswith("/tmp/")}


def live_session_ids():
    ids = set()
    for f in (Path.home() / ".claude/sessions").glob("*.json"):
        try:
            data = json.loads(f.read_text())
            os.kill(int(data["pid"]), 0)
            ids.add(data["sessionId"])
        except (OSError, ValueError, KeyError, TypeError, ProcessLookupError):
            continue
    return ids


def measure(path):
    """Newest mtime and total size. A unix socket inside (a live server may own it
    without an fd naming the path) or a walk past WALK_LIMIT counts as recent."""
    st = os.lstat(path)
    if stat.S_ISSOCK(st.st_mode):
        return float("inf"), 0
    newest, size, seen = st.st_mtime, st.st_size, 0
    stack = [path] if os.path.isdir(path) and not os.path.islink(path) else []
    while stack:
        d = stack.pop()
        try:
            it = os.scandir(d)
        except OSError:
            continue
        with it:
            for ent in it:
                seen += 1
                if seen > WALK_LIMIT:
                    return float("inf"), size
                try:
                    s = ent.stat(follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISSOCK(s.st_mode):
                    return float("inf"), size
                newest = max(newest, s.st_mtime)
                size += s.st_blocks * 512
                if ent.is_dir(follow_symlinks=False):
                    stack.append(ent.path)
    return newest, size


def candidates():
    uid = os.getuid()
    out = []

    def add(p, session_id=""):
        try:
            if os.lstat(p).st_uid != uid:
                return
            newest, size = measure(p)
        except OSError:
            return
        out.append(Entry(p, newest, size, session_id))

    for ent in os.scandir(TMP):
        if ent.name.startswith(SKIP_PREFIXES) or ent.name == CLAUDE_TMP_NAME:
            continue
        add(ent.path)
    claude_tmp = TMP / CLAUDE_TMP_NAME
    if claude_tmp.is_dir():
        for ent in os.scandir(claude_tmp):
            if ent.name.startswith("-") and ent.is_dir(follow_symlinks=False):
                # Project dir: each child is one session's scratch dir.
                for sess in os.scandir(ent.path):
                    add(sess.path, session_id=sess.name)
            else:
                add(ent.path)
    return out


def remove(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="delete (default: dry run)")
    ap.add_argument("--min-age-hours", type=float, default=2.0)
    ap.add_argument("--max-deletes", type=int, default=2000)
    ap.add_argument("--verbose", action="store_true", help="also print kept entries")
    args = ap.parse_args(argv)

    now = time.time()
    decisions = decide(candidates(), scan_in_use(), live_session_ids(), now, args.min_age_hours * 3600)
    to_delete = [d for d in decisions if d.action == "delete"][: args.max_deletes]
    deleted, failed, freed = [], [], 0
    for d in to_delete:
        if args.apply:
            try:
                remove(d.path)
            except OSError as exc:
                failed.append({"path": d.path, "error": type(exc).__name__})
                continue
        deleted.append({"path": d.path, "bytes": d.size})
        freed += d.size

    kept = {}
    for d in decisions:
        if d.action == "keep":
            kept[d.reason] = kept.get(d.reason, 0) + 1
    summary = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "apply": args.apply,
        "min_age_hours": args.min_age_hours, "scanned": len(decisions),
        "deleted": len(deleted), "failed": len(failed), "freed_bytes": freed,
        "kept": kept, "items": deleted, "errors": failed,
    }
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    verb = "deleted" if args.apply else "would delete"
    for item in deleted:
        print(f"{verb} {item['bytes'] / 1e6:9.1f} MB  {item['path']}")
    if args.verbose:
        for d in decisions:
            if d.action == "keep":
                print(f"keep ({d.reason})  {d.path}")
    print(f"{verb} {len(deleted)} entries, {freed / 1e9:.2f} GB; kept {kept}; failed {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
