#!/usr/bin/env python3
"""Diagnose Claude Code inside ORCA sending requests to a stale ANTHROPIC_BASE_URL.

Subcommands:
  check                          read-only snapshot as JSON
  stop-daemon --pid N --evidence DIR
                                 save resume list, then SIGTERM one stale ORCA terminal daemon

Never prints token values. Never calls a model.
"""
import argparse
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROC = Path("/proc")
SECRET_KEYS = ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY")


# ---- pure functions -------------------------------------------------------

def parse_environ(raw: bytes) -> dict:
    env = {}
    for item in raw.split(b"\0"):
        if b"=" in item:
            key, _, value = item.partition(b"=")
            env[key.decode(errors="replace")] = value.decode(errors="replace")
    return env


def classify(argv: list, env: dict) -> str:
    """Return the role of a process, or '' when it is not relevant."""
    joined = " ".join(argv)
    if "orca-ide" in joined and "daemon-entry.js" in joined:
        return "orca_daemon"
    if argv and argv[0].endswith("orca-ide") and len(argv) == 1:
        return "orca_gui"
    if argv and Path(argv[0]).name == "claude" and "ORCA_TERMINAL_HANDLE" in env:
        return "orca_claude"
    return ""


def resume_id(argv: list) -> str:
    for i, arg in enumerate(argv):
        if arg == "--resume" and i + 1 < len(argv):
            return argv[i + 1]
    return ""


def install_root(argv: list) -> str:
    exe = argv[0] if argv else ""
    if exe.startswith("/tmp/.mount_orca"):
        return "appimage"
    if exe.startswith("/opt/Orca"):
        return "opt"
    return "other"


def verdict(snapshot: dict) -> dict:
    daemons = snapshot["daemons"]
    bad = [d for d in daemons if d["base_url"]]
    probe = snapshot.get("base_url_probe") or {}
    broken = probe.get("status") in (None, 404) or probe.get("error")
    if bad and broken:
        return {"code": "stale_base_url",
                "message": "ORCA terminal daemon passes ANTHROPIC_BASE_URL to a gateway that does not serve /v1/messages",
                "stale_daemon_pids": [d["pid"] for d in bad]}
    if bad:
        return {"code": "base_url_set_gateway_answers",
                "message": "daemon uses a gateway that answers; model error is not explained by this check",
                "stale_daemon_pids": []}
    if not daemons:
        return {"code": "no_daemon", "message": "no ORCA terminal daemon running", "stale_daemon_pids": []}
    return {"code": "clean", "message": "ORCA terminal daemon has no ANTHROPIC_BASE_URL", "stale_daemon_pids": []}


# ---- side-effect entry points ---------------------------------------------

def read_proc(pid: int):
    try:
        argv = [a.decode(errors="replace") for a in (PROC / str(pid) / "cmdline").read_bytes().split(b"\0") if a]
        env = parse_environ((PROC / str(pid) / "environ").read_bytes())
        cwd = os.readlink(PROC / str(pid) / "cwd")
        ppid = int((PROC / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return argv, env, cwd, ppid


def probe_gateway(base_url: str) -> dict:
    # Empty body without auth: a real Messages API answers 400/401, a gateway without it answers 404.
    req = urllib.request.Request(base_url.rstrip("/") + "/v1/messages", data=b"{}", method="POST",
                                 headers={"content-type": "application/json", "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return {"url": base_url, "status": resp.status}
    except urllib.error.HTTPError as err:
        return {"url": base_url, "status": err.code}
    except (urllib.error.URLError, OSError) as err:
        return {"url": base_url, "status": None, "error": str(err)[:200]}


def snapshot() -> dict:
    daemons, guis, sessions = [], [], []
    for entry in PROC.iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        info = read_proc(int(entry.name))
        if info is None:
            continue
        argv, env, cwd, ppid = info
        role = classify(argv, env)
        if not role:
            continue
        row = {"pid": int(entry.name), "ppid": ppid, "base_url": env.get("ANTHROPIC_BASE_URL", ""),
               "secrets_present": [k for k in SECRET_KEYS if k in env]}
        if role == "orca_daemon":
            daemons.append({**row, "install": install_root(argv)})
        elif role == "orca_gui":
            guis.append({**row, "install": install_root(argv)})
        else:
            sessions.append({**row, "cwd": cwd, "resume_id": resume_id(argv)})
    urls = sorted({d["base_url"] for d in daemons if d["base_url"]})
    snap = {"daemons": daemons, "guis": guis, "claude_sessions": sessions,
            "base_url_probe": probe_gateway(urls[0]) if urls else None}
    snap["verdict"] = verdict(snap)
    return snap


def stop_daemon(pid: int, evidence: Path) -> dict:
    snap = snapshot()
    if pid not in snap["verdict"]["stale_daemon_pids"]:
        return {"ok": False, "reason": "pid is not a stale ORCA terminal daemon in the current snapshot",
                "verdict": snap["verdict"]}
    evidence.mkdir(parents=True, exist_ok=True)
    saved = evidence / f"orca-sessions-{int(time.time())}.json"
    saved.write_text(json.dumps(snap["claude_sessions"], ensure_ascii=False, indent=1))
    os.kill(pid, signal.SIGTERM)
    for _ in range(10):
        if not (PROC / str(pid)).exists():
            return {"ok": True, "stopped": pid, "resume_list": str(saved),
                    "next": "ORCA GUI starts a new daemon on demand; run check again, then test in a new ORCA tab"}
        time.sleep(1)
    return {"ok": False, "reason": "daemon still alive after SIGTERM + 10s; not escalating", "resume_list": str(saved)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    stop = sub.add_parser("stop-daemon")
    stop.add_argument("--pid", type=int, required=True)
    stop.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    result = snapshot() if args.cmd == "check" else stop_daemon(args.pid, args.evidence)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
