#!/usr/bin/env python3
"""Read-only audit of git worktrees: last activity, dirtiness, users.

Usage:
  python3 ~/tools/worktree_idle_audit.py --repo <any worktree> [--days 5] [--json]

For every linked worktree (main worktree is skipped) it reports:
  last_activity  newest of: working-tree file mtimes (heavy build dirs
                 pruned), index/HEAD/ORIG_HEAD/FETCH_HEAD mtimes, and the
                 timestamp inside the last reflog entry
  dirty          `git status --porcelain` lines (tracked + untracked)
  detached_lost  detached HEAD not reachable from any branch or remote
  ahead_remote   commits on HEAD not on any remote ref (branch keeps them)
  procs          PIDs whose cwd is inside the worktree
  containers     running docker compose containers whose working dir is inside
  ignored_extra  ignored files that are not build output (e.g. .env copies)
  verdict        SAFE (idle and nothing would be lost) / KEEP:<reasons>

Side effects: none. Activity is measured before any git command runs, and
git runs with GIT_OPTIONAL_LOCKS=0 so `status` does not rewrite the index.
"""
import argparse
import json
import os
import subprocess
import sys
import time

PRUNE_DIRS = {
    "node_modules", ".next", ".turbo", "dist", "build", "coverage", "target",
    ".git", "test-results", "playwright-report", ".cache",
}
BUILD_IGNORED_PREFIXES = (
    "node_modules", ".next", ".turbo", "dist", "build", "coverage", "target",
    "test-results", "playwright-report", ".cache",
)
ENV = dict(os.environ, GIT_OPTIONAL_LOCKS="0")


def git(path, *args):
    r = subprocess.run(["git", "-C", path, *args], capture_output=True, text=True, env=ENV)
    return r.returncode, r.stdout


def list_worktrees(repo):
    _, out = git(repo, "worktree", "list", "--porcelain")
    items, cur = [], {}
    for line in out.splitlines() + [""]:
        if not line:
            if cur:
                items.append(cur)
            cur = {}
            continue
        key, _, val = line.partition(" ")
        cur[key] = val or True
    return items


def newest_tree_mtime(root):
    newest, newest_path = 0.0, ""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS]
        for name in filenames + dirnames:
            p = os.path.join(dirpath, name)
            try:
                m = os.lstat(p).st_mtime
            except OSError:
                continue
            if m > newest:
                newest, newest_path = m, p
    return newest, newest_path


def admin_mtime(path):
    gitfile = os.path.join(path, ".git")
    try:
        with open(gitfile) as f:
            admin = f.read().split("gitdir:", 1)[1].strip()
    except (OSError, IndexError):
        return 0.0
    newest = 0.0
    # logs/HEAD mtime is NOT used: `git gc` / reflog expire rewrites every
    # worktree's reflog at once and bumps its mtime without any real use.
    for name in ("index", "HEAD", "ORIG_HEAD", "FETCH_HEAD"):
        try:
            newest = max(newest, os.stat(os.path.join(admin, name)).st_mtime)
        except OSError:
            pass
    newest = max(newest, last_reflog_time(os.path.join(admin, "logs", "HEAD")))
    return newest


def last_reflog_time(path):
    """Timestamp written inside the newest reflog entry (content, not mtime)."""
    try:
        with open(path, errors="replace") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
    except OSError:
        return 0.0
    if not lines:
        return 0.0
    head = lines[-1].split("\t", 1)[0].split()
    try:
        return float(head[-2])
    except (IndexError, ValueError):
        return 0.0


def proc_cwds():
    out = {}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            out[pid] = os.readlink(f"/proc/{pid}/cwd")
        except OSError:
            pass
    return out


def running_container_dirs():
    try:
        r = subprocess.run(
            ["docker", "ps", "--format",
             '{{.Names}}\t{{.Label "com.docker.compose.project.working_dir"}}'],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return [tuple(l.split("\t", 1)) for l in r.stdout.splitlines() if "\t" in l]


def inside(child, parent):
    child, parent = os.path.realpath(child), os.path.realpath(parent)
    return child == parent or child.startswith(parent.rstrip("/") + "/")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--days", type=float, default=5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    now = time.time()
    cutoff = now - a.days * 86400
    wts = list_worktrees(a.repo)
    main_path = wts[0]["worktree"] if wts else None

    # Phase 1: measure activity before any git command touches the worktrees.
    rows = []
    for wt in wts[1:]:
        path = wt["worktree"]
        row = {"path": path, "branch": wt.get("branch", "").replace("refs/heads/", "") or "(detached)",
               "head": wt.get("HEAD", "")[:9], "exists": os.path.isdir(path)}
        if row["exists"]:
            t_tree, p_tree = newest_tree_mtime(path)
            t_admin = admin_mtime(path)
            row["last_activity"] = max(t_tree, t_admin)
            row["last_activity_src"] = p_tree if t_tree >= t_admin else "(git admin files)"
        rows.append(row)

    cwds = proc_cwds()
    containers = running_container_dirs()

    # Phase 2: git state and users.
    for row in rows:
        path = row["path"]
        reasons = []
        if not row["exists"]:
            row["verdict"] = "PRUNABLE"
            continue
        _, st = git(path, "status", "--porcelain")
        row["dirty"] = [l for l in st.splitlines() if l.strip()]
        _, ign = git(path, "status", "--porcelain", "--ignored", "--untracked-files=normal")
        extra = []
        for l in ign.splitlines():
            if l.startswith("!! "):
                f = l[3:]
                parts = f.split("/")
                if any(p in BUILD_IGNORED_PREFIXES for p in parts) or f.endswith(".tsbuildinfo"):
                    continue
                extra.append(f)
        row["ignored_extra"] = extra
        _, ahead = git(path, "rev-list", "--count", "HEAD", "--not", "--remotes")
        row["ahead_remote"] = int(ahead.strip() or 0)
        row["detached_lost"] = False
        if row["branch"] == "(detached)":
            _, on_ref = git(path, "for-each-ref", "--contains", "HEAD", "--count=1",
                            "refs/heads", "refs/remotes")
            row["detached_lost"] = not on_ref.strip()
        row["procs"] = [pid for pid, c in cwds.items() if inside(c, path)]
        row["containers"] = None if containers is None else [n for n, d in containers if d and inside(d, path)]

        if row["last_activity"] >= cutoff:
            reasons.append("active")
        if row["dirty"]:
            reasons.append(f"dirty:{len(row['dirty'])}")
        if row["detached_lost"]:
            reasons.append("detached_unreachable")
        if row["procs"]:
            reasons.append(f"procs:{len(row['procs'])}")
        if row["containers"]:
            reasons.append(f"containers:{len(row['containers'])}")
        if row["containers"] is None:
            reasons.append("docker_unknown")
        row["verdict"] = "SAFE" if not reasons else "KEEP:" + ",".join(reasons)

    if a.json:
        json.dump({"main": main_path, "cutoff_days": a.days, "rows": rows}, sys.stdout,
                  ensure_ascii=False, indent=1)
        return
    for r in sorted(rows, key=lambda r: r.get("last_activity", 0)):
        age = (now - r["last_activity"]) / 86400 if r.get("last_activity") else -1
        print(f"{r['verdict']:<28} {age:6.1f}d  ahead={r.get('ahead_remote', '-'):<3} "
              f"ign={len(r.get('ignored_extra', [])):<3} {r['branch'][:40]:<40} {r['path']}")


if __name__ == "__main__":
    main()
