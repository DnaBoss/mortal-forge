#!/usr/bin/env python3
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

WINDOWS = os.name == "nt"
STATE = Path.home() / ".memory-tidy"
KEEP_FILE = STATE / "never-kill.txt"
LOG = STATE / "log.jsonl"
WALK_LIMIT = 20000

MCP_PATTERNS = (r"\bmcp\b", r"mcp-server", r"-mcp\b", r"modelcontextprotocol", r"context7", r"playwright.*mcp")
DEV_PATTERNS = (r"next dev", r"next-server", r"\bvite\b", r"tsx watch", r"--import tsx", r"ts-node",
                r"webpack(-dev-server| serve)", r"nodemon", r"npm run dev", r"pnpm (run )?dev", r"yarn dev")
LAUNCHERS = (r"\bnpx\b", r"\buvx?\b", r"\bbunx?\b", r"\bnode(\.exe)?\b", r"\bpython[\d.]*(\.exe)?\b", r"\bdeno\b")
NEVER_PATTERNS = (r"\bsshd?\b", r"\bpostgres", r"\bredis", r"\bdocker", r"\bcontainerd", r"claude(\.exe)?\s*$", r"\bcodex(\.exe)?\s*$")

ETIME = re.compile(r"^(?:(?:(\d+)-)?(\d+):)?(\d+):(\d+)$")


def etime_seconds(text):
    m = ETIME.match(text.strip())
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def list_unix():
    out = subprocess.run(["ps", "-axo", "pid=,ppid=,etime=,args="], capture_output=True, text=True, check=True).stdout
    procs = {}
    for line in out.splitlines():
        parts = line.split(None, 3)
        if len(parts) < 3 or not parts[0].isdigit():
            continue
        procs[int(parts[0])] = {"pid": int(parts[0]), "ppid": int(parts[1]), "age": etime_seconds(parts[2]),
                                "cmd": parts[3] if len(parts) > 3 else ""}
    return procs


WIN_QUERY = (
    "Get-CimInstance Win32_Process | ForEach-Object { [pscustomobject]@{pid=$_.ProcessId; ppid=$_.ParentProcessId; "
    "cmd=if ($_.CommandLine) {$_.CommandLine} else {$_.Name}; "
    "start=if ($_.CreationDate) {[DateTimeOffset]::new($_.CreationDate).ToUnixTimeSeconds()} else {0}} } | ConvertTo-Json -Compress"
)


def list_windows():
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", WIN_QUERY],
                         capture_output=True, text=True, check=True).stdout
    rows = json.loads(out)
    rows = rows if isinstance(rows, list) else [rows]
    now = time.time()
    procs = {}
    for r in rows:
        age = max(0, int(now - r["start"])) if r["start"] else 0
        procs[r["pid"]] = {"pid": r["pid"], "ppid": r["ppid"], "age": age, "cmd": r["cmd"], "start": r["start"]}
    return procs


def list_procs():
    return list_windows() if WINDOWS else list_unix()


def ancestors(pid, procs):
    seen = set()
    while pid in procs and pid not in seen:
        seen.add(pid)
        pid = procs[pid]["ppid"]
    return seen


def descendants(root, procs):
    kids = {}
    for p in procs.values():
        kids.setdefault(p["ppid"], []).append(p["pid"])
    order, stack = [], [root]
    while stack:
        cur = stack.pop()
        order.append(cur)
        stack.extend(kids.get(cur, []))
    return order


def is_orphan(proc, procs):
    parent = procs.get(proc["ppid"])
    if WINDOWS:
        if parent is None:
            return True
        return bool(parent.get("start") and proc.get("start") and parent["start"] > proc["start"])
    if proc["ppid"] <= 1 or parent is None:
        return True
    return bool(re.search(r"(^|/)systemd\b.*--user", parent["cmd"]))


def service_managed(pid):
    try:
        return Path(f"/proc/{pid}/cgroup").read_text().strip().endswith(".service")
    except OSError:
        return False


def matches(patterns, text):
    return any(re.search(p, text, re.I) for p in patterns)


def read_keep():
    try:
        return {int(x) for x in KEEP_FILE.read_text().split() if x.isdigit()}
    except OSError:
        return set()


def select(procs, mcp_hours, dev_hours, extra_keep, extra_patterns):
    protected = ancestors(os.getpid(), procs) | read_keep()
    picks = []
    for p in procs.values():
        cmd = p["cmd"]
        if p["pid"] in protected or matches(NEVER_PATTERNS, cmd) or matches(extra_keep, cmd) or service_managed(p["pid"]):
            continue
        if matches(MCP_PATTERNS + tuple(extra_patterns), cmd) and matches(LAUNCHERS, cmd):
            kind, hours = "mcp", mcp_hours
        elif matches(DEV_PATTERNS, cmd):
            kind, hours = "dev", dev_hours
        else:
            continue
        if not is_orphan(p, procs) or p["age"] < hours * 3600:
            continue
        picks.append({**p, "kind": kind})
    roots = {x["pid"] for x in picks}
    return [x for x in picks if not (ancestors(x["ppid"], procs) & roots)]


def same_process(pid, cmd):
    return list_procs().get(pid, {}).get("cmd") == cmd


def stop_tree(root, procs, cmd):
    if not same_process(root, cmd):
        return "skipped: process changed"
    if WINDOWS:
        out = subprocess.run(["taskkill", "/PID", str(root), "/T", "/F"], capture_output=True, text=True)
        return "stopped" if out.returncode == 0 else out.stderr.strip()
    pids = descendants(root, procs)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 5
    while time.time() < deadline and any(pid in list_procs() for pid in pids):
        time.sleep(0.5)
    left = [pid for pid in pids if pid in list_procs()]
    for pid in left:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    return "stopped" if not left else f"killed {len(left)} after timeout"


def tmp_candidates(hours):
    root = Path(tempfile.gettempdir())
    cutoff = time.time() - hours * 3600
    me = os.getuid() if not WINDOWS else None
    found = []
    try:
        entries = list(root.iterdir())
    except OSError:
        return found
    for e in entries:
        try:
            st = e.lstat()
            if me is not None and st.st_uid != me:
                continue
            if e.is_symlink() or not (e.is_file() or e.is_dir()):
                continue
            newest = st.st_mtime
            if e.is_dir():
                count = 0
                for dp, _, files in os.walk(e):
                    for f in files:
                        count += 1
                        newest = max(newest, os.lstat(os.path.join(dp, f)).st_mtime)
                    if count > WALK_LIMIT:
                        newest = time.time()
                        break
            if newest < cutoff:
                found.append(e)
        except OSError:
            continue
    return found


def open_paths():
    if WINDOWS:
        return set()
    try:
        out = subprocess.run(["lsof", "-n", "-w", "-Fn"], capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    return {line[1:] for line in out.splitlines() if line.startswith("n/")}


def in_use(path, opened):
    if opened is None:
        return True
    prefix = str(path) + os.sep
    return any(o == str(path) or o.startswith(prefix) for o in opened)


def remove(path):
    import shutil
    try:
        shutil.rmtree(path) if path.is_dir() else path.unlink()
        return True
    except OSError:
        return False


def log(entry):
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(json.dumps({"t": int(time.time()), **entry}) + "\n")
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser(description="Stop orphan MCP servers and dev servers, clean stale temp files (preview by default)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--mcp-idle-hours", type=float, default=1)
    ap.add_argument("--dev-idle-hours", type=float, default=2)
    ap.add_argument("--tmp-hours", type=float, default=6)
    ap.add_argument("--keep", action="append", default=[], help="regex; matching command lines are never stopped")
    ap.add_argument("--also", action="append", default=[], help="regex; extra command lines treated as MCP-like servers")
    ap.add_argument("--tmp", action="store_true", help="also remove stale entries in the temp directory")
    args = ap.parse_args()

    procs = list_procs()
    picks = select(procs, args.mcp_idle_hours, args.dev_idle_hours, args.keep, args.also)
    print(f"orphan servers: {len(picks)}")
    for p in picks:
        line = f"  [{p['kind']}] pid {p['pid']} age {p['age'] // 3600}h  {p['cmd'][:100]}"
        if args.apply:
            result = stop_tree(p["pid"], procs, p["cmd"])
            line += f"  -> {result}"
            log({"kind": p["kind"], "pid": p["pid"], "cmd": p["cmd"][:200], "result": result})
        print(line)
    if args.tmp:
        stale = tmp_candidates(args.tmp_hours)
        opened = open_paths() if stale else set()
        print(f"stale temp entries: {len(stale)}")
        for i, path in enumerate(stale):
            if not args.apply and i >= 20:
                print(f"  ... {len(stale) - 20} more")
                break
            if in_use(path, opened):
                print(f"  in use, kept: {path}")
                continue
            done = remove(path) if args.apply else None
            print(f"  {'removed' if done else 'would remove' if done is None else 'failed'}: {path}")
    if not args.apply:
        print("Preview only. Re-run with --apply to do this.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
