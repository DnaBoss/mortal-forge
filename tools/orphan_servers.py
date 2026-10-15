#!/usr/bin/env python3
"""Stop orphaned dev servers: web/API processes whose shell or agent is gone.

A process group is stopped only when all hold:
  - the root looks like a dev server: comm starts with "next-server" or the
    command line has "next dev", "--import tsx", "tsx watch", "ts-node" or "vite"
  - the root's parent is init or the user's systemd, i.e. the terminal or agent
    that started it has exited (the kernel re-parented it)
  - nothing in the group has an inbound client: no established TCP connection
    whose local port is one of the group's listening ports. Outgoing pools to a
    database or Redis do not count.
  - the group has been quiet for --min-idle-hours: process start, newest file
    under the root's cwd (bounded walk) and its stdout/stderr targets are all older

Default is a dry run. --apply sends SIGTERM to the whole group. Each run appends
one JSON line to the log, together with the Orca scope memory numbers.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

LOG = Path.home() / ".local/state/orphan-servers/log.jsonl"
WALK_LIMIT = 50_000
SKIP_DIRS = {"node_modules", ".git", "target", ".pnpm-store"}
DEV_SERVER_PATTERNS = ("next dev", "--import tsx", "tsx watch", "ts-node", "vite")
CGROUP_APP = Path("/sys/fs/cgroup/user.slice/user-%d.slice/user@%d.service/app.slice" % (os.getuid(), os.getuid()))


@dataclass
class Proc:
    pid: int
    ppid: int
    parent_comm: str
    comm: str
    args: str
    start: float  # epoch seconds
    cwd: str
    rss: int = 0
    listen_ports: set = field(default_factory=set)


@dataclass
class Decision:
    pid: int
    action: str  # "stop" or "keep"
    reason: str
    group: list = field(default_factory=list)  # pids, root first
    ports: list = field(default_factory=list)
    idle_hours: float = 0.0


def looks_like_dev_server(comm, args):
    if comm.startswith("next-server"):
        return True
    return any(p in args for p in DEV_SERVER_PATTERNS)


def is_orphan(proc, user_systemd_pids):
    return proc.ppid == 1 or proc.ppid in user_systemd_pids


def descendants(root_pid, procs):
    """pids of root and everything below it, root first."""
    by_parent = {}
    for p in procs.values():
        by_parent.setdefault(p.ppid, []).append(p.pid)
    out, stack = [], [root_pid]
    while stack:
        pid = stack.pop()
        out.append(pid)
        stack.extend(by_parent.get(pid, []))
    return out


def has_dev_server_ancestor(proc, procs):
    """True when a process above this one is itself a dev server (then it is a group member)."""
    seen, parent = set(), procs.get(proc.ppid)
    while parent and parent.pid not in seen:
        if looks_like_dev_server(parent.comm, parent.args):
            return True
        seen.add(parent.pid)
        parent = procs.get(parent.ppid)
    return False


def roots(procs):
    """Dev-server processes that are not below another dev server, pid order."""
    return [p for p in sorted(procs.values(), key=lambda x: x.pid)
            if looks_like_dev_server(p.comm, p.args) and not has_dev_server_ancestor(p, procs)]


def decide(procs, user_systemd_pids, inbound_ports, last_activity, now, min_idle_s, protected=()):
    """Pure selection: no /proc or network access. One decision per root group.

    procs: {pid: Proc}; inbound_ports: local ports of established connections;
    last_activity: {pid: epoch of newest observed activity for that root's group}.
    """
    out = []
    for p in roots(procs):
        if not is_orphan(p, user_systemd_pids):
            out.append(Decision(p.pid, "keep", "parent_alive"))
            continue
        group = descendants(p.pid, procs)
        if any(pid in protected for pid in group):
            out.append(Decision(p.pid, "keep", "protected", group))
            continue
        ports = sorted({port for pid in group for port in procs[pid].listen_ports})
        if any(port in inbound_ports for port in ports):
            out.append(Decision(p.pid, "keep", "has_clients", group, ports))
            continue
        idle = now - max(last_activity.get(p.pid, p.start), p.start)
        if idle < min_idle_s:
            out.append(Decision(p.pid, "keep", "recent", group, ports, idle / 3600))
            continue
        out.append(Decision(p.pid, "stop", "orphan_idle", group, ports, idle / 3600))
    return out


# ---- observation (filesystem, /proc, ss) ----

def boot_time():
    with open("/proc/stat") as f:
        for line in f:
            if line.startswith("btime "):
                return float(line.split()[1])
    return 0.0


def read_procs():
    uid, procs = os.getuid(), {}
    tick, btime = os.sysconf("SC_CLK_TCK"), boot_time()
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid, base = int(name), f"/proc/{name}"
        try:
            if os.stat(base).st_uid != uid:
                continue
            with open(f"{base}/stat") as f:
                stat_line = f.read()
            with open(f"{base}/cmdline", "rb") as f:
                args = f.read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
            with open(f"{base}/statm") as f:
                rss = int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
        except (OSError, ValueError, IndexError):
            continue
        try:
            cwd = os.readlink(f"{base}/cwd")
        except OSError:
            cwd = ""  # e.g. systemd --user refuses; the process still counts as a parent
        # comm may contain spaces/parens: it is between the first "(" and the last ")".
        comm = stat_line[stat_line.index("(") + 1:stat_line.rindex(")")]
        rest = stat_line[stat_line.rindex(")") + 2:].split()
        ppid, start_ticks = int(rest[1]), int(rest[19])
        procs[pid] = Proc(pid, ppid, "", comm, args, btime + start_ticks / tick, cwd, rss)
    for p in procs.values():
        parent = procs.get(p.ppid)
        p.parent_comm = parent.comm if parent else ""
    return procs


def user_systemd_pids(procs=None):
    """pids of this user's `systemd --user` manager(s), read straight from /proc so a
    manager that read_procs could not fully parse is still recognised."""
    uid, out = os.getuid(), set()
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            if os.stat(f"/proc/{name}").st_uid != uid:
                continue
            with open(f"/proc/{name}/comm") as f:
                if f.read().strip() == "systemd":
                    out.add(int(name))
        except OSError:
            continue
    return out


def read_listen_ports(procs):
    out = subprocess.run(["ss", "-Hltnp"], capture_output=True, text=True, check=False).stdout
    for line in out.splitlines():
        m_port = re.search(r"\s(\S+):(\d+)\s+\S+\s+users:", line)
        if not m_port:
            continue
        port = int(m_port.group(2))
        for pid in re.findall(r"pid=(\d+)", line):
            if int(pid) in procs:
                procs[int(pid)].listen_ports.add(port)


def read_inbound_ports():
    out = subprocess.run(["ss", "-Htn", "state", "established"], capture_output=True, text=True, check=False).stdout
    ports = set()
    for line in out.splitlines():
        cols = line.split()
        if len(cols) >= 4 and ":" in cols[2]:
            ports.add(int(cols[2].rsplit(":", 1)[1]))
    return ports


def newest_under(path):
    """Newest mtime under path with a bounded walk; inf when cut short (treat as active)."""
    try:
        newest = os.lstat(path).st_mtime
    except OSError:
        return 0.0
    seen, stack = 0, [path] if os.path.isdir(path) else []
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
                    return float("inf")
                try:
                    st = ent.stat(follow_symlinks=False)
                except OSError:
                    continue
                newest = max(newest, st.st_mtime)
                if ent.is_dir(follow_symlinks=False) and ent.name not in SKIP_DIRS:
                    stack.append(ent.path)
    return newest


def group_activity(group, procs):
    """Newest of: root cwd tree, every member's stdout/stderr target mtime."""
    root = procs[group[0]]
    newest = newest_under(root.cwd)
    for pid in group:
        for fd in ("1", "2"):
            try:
                target = os.readlink(f"/proc/{pid}/fd/{fd}")
                if target.startswith("/"):
                    newest = max(newest, os.stat(target).st_mtime)
            except OSError:
                pass
    return newest


def orca_scope_memory():
    rows = []
    for scope in sorted(CGROUP_APP.glob("app-orca-*.scope")):
        try:
            current = int((scope / "memory.current").read_text())
            high = (scope / "memory.high").read_text().strip()
            events = dict(l.split() for l in (scope / "memory.events").read_text().splitlines())
            pressure = (scope / "memory.pressure").read_text().splitlines()[1]
            full300 = float(re.search(r"avg300=([\d.]+)", pressure).group(1))
        except (OSError, ValueError, AttributeError, IndexError):
            continue
        rows.append({"scope": scope.name, "current_gb": round(current / 1e9, 1),
                     "high_gb": None if high == "max" else round(int(high) / 1e9, 1),
                     "high_events": int(events.get("high", 0)), "pressure_full_avg300": full300})
    return rows


def stop_group(group, grace_s=3.0):
    """SIGTERM root first, then anything in the group still alive. Returns pids still alive."""
    for pid in group:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.time() + grace_s
    alive = set(group)
    while alive and time.time() < deadline:
        time.sleep(0.2)
        alive = {pid for pid in alive if os.path.exists(f"/proc/{pid}")}
    return sorted(alive)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="send SIGTERM (default: dry run)")
    ap.add_argument("--min-idle-hours", type=float, default=2.0)
    ap.add_argument("--verbose", action="store_true", help="also print kept groups")
    args = ap.parse_args(argv)

    now = time.time()
    procs = read_procs()
    read_listen_ports(procs)
    systemd_pids = user_systemd_pids(procs)
    inbound = read_inbound_ports()
    orphan_roots = [p for p in roots(procs) if is_orphan(p, systemd_pids)]
    activity = {p.pid: group_activity(descendants(p.pid, procs), procs) for p in orphan_roots}
    protected = {os.getpid(), os.getppid()}
    decisions = decide(procs, systemd_pids, inbound, activity, now, args.min_idle_hours * 3600, protected)

    stopped, still_alive = [], []
    for d in decisions:
        if d.action != "stop":
            continue
        root = procs[d.pid]
        item = {"pid": d.pid, "comm": root.comm, "args": root.args[:160], "cwd": root.cwd,
                "ports": d.ports, "idle_hours": round(d.idle_hours, 1),
                "rss_mb": sum(procs[pid].rss for pid in d.group if pid in procs) // (1024 * 1024),
                "group": d.group}
        if args.apply:
            alive = stop_group(d.group)
            if alive:
                item["still_alive"] = alive
                still_alive.extend(alive)
        stopped.append(item)

    kept = {}
    for d in decisions:
        if d.action == "keep":
            kept[d.reason] = kept.get(d.reason, 0) + 1
    summary = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "apply": args.apply,
        "min_idle_hours": args.min_idle_hours, "dev_servers_seen": len(decisions),
        "stopped": len(stopped), "still_alive": still_alive, "kept": kept,
        "items": stopped, "orca_scope": orca_scope_memory(),
    }
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    verb = "stopped" if args.apply else "would stop"
    for item in stopped:
        print(f"{verb} pid {item['pid']} ports {item['ports']} idle {item['idle_hours']}h "
              f"{item['rss_mb']} MB  {item['cwd']}")
    if args.verbose:
        for d in decisions:
            if d.action == "keep":
                print(f"keep ({d.reason})  pid {d.pid} ports {d.ports}  {procs[d.pid].args[:80]}")
    for row in summary["orca_scope"]:
        print(f"orca {row['scope']}: {row['current_gb']} GB of high {row['high_gb']} GB, "
              f"high events {row['high_events']}, pressure full avg300 {row['pressure_full_avg300']}%")
    print(f"{verb} {len(stopped)} groups; kept {kept}; still alive {still_alive}")
    return 1 if still_alive else 0


if __name__ == "__main__":
    sys.exit(main())
