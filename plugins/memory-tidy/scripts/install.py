#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()
WINDOWS = os.name == "nt"
MAC = sys.platform == "darwin"
LIB = Path(os.environ.get("LOCALAPPDATA", HOME)) / "memory-tidy" if WINDOWS else HOME / ".local/lib/memory-tidy"
UNITS = HOME / ".config/systemd/user"
PLIST = HOME / "Library/LaunchAgents/com.memory-tidy.plist"
TASK = "memory-tidy"
FROZEN = getattr(sys, "frozen", False)
EXE = LIB / ("memory-tidy.exe" if WINDOWS else "memory-tidy")
SCRIPTS = ("mem_tidy.py", "idle_agents.py", "orphan_servers.py", "tmp_cleanup.py", "tidy_any.py", "session_hint.py", "memory_tidy_cli.py", "install.py")
HOOK_FILES = (HOME / ".claude/settings.json", HOME / ".codex/hooks.json")

PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.memory-tidy</string>
<key>ProgramArguments</key><array>{args}</array>
<key>StartInterval</key><integer>{seconds}</integer>
<key>Nice</key><integer>10</integer>
<key>RunAtLoad</key><false/>
</dict></plist>
"""

SERVICE = """[Unit]
Description=Free memory: close idle claude/codex, stop orphan dev servers, clean stale /tmp

[Service]
Type=oneshot
ExecStart={exec_line}
Nice=10
"""

TIMER = """[Unit]
Description=Run memory-tidy every {minutes} minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec={minutes}min
Persistent=false

[Install]
WantedBy=timers.target
"""


def systemctl(*args):
    return subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True)


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def copy_scripts():
    LIB.mkdir(parents=True, exist_ok=True)
    if FROZEN:
        shutil.copy2(sys.executable, EXE)
        return
    for name in SCRIPTS:
        shutil.copy2(HERE / name, LIB / name)


def job_args(hours):
    if FROZEN:
        return [str(EXE), "all", "--min-idle-hours", str(hours), "--apply"]
    return [sys.executable, "-I", str(LIB / "mem_tidy.py"), "--min-idle-hours", str(hours), "--apply"]


def hint_command():
    if FROZEN:
        return f'"{EXE.as_posix()}" hint'
    return f'"{Path(sys.executable).as_posix()}" -I "{(LIB / "memory_tidy_cli.py").as_posix()}" hint'


def hook_entries(data):
    return data.setdefault("hooks", {}).setdefault("SessionStart", [])


def is_ours(group):
    return any(h.get("command", "").endswith(" hint") and "memory" in h.get("command", "") for h in group.get("hooks", []))


def edit_hook_file(path, add):
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        return f"{path}: not valid JSON, left untouched"
    groups = [g for g in hook_entries(data) if not is_ours(g)]
    if add:
        groups.append({"hooks": [{"type": "command", "command": hint_command(), "timeout": 10}]})
    if groups:
        data["hooks"]["SessionStart"] = groups
    else:
        data["hooks"].pop("SessionStart", None)
    backup = path.with_name(path.name + ".bak-memory-tidy")
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"{path}: {'hook added' if add else 'hook removed'}"


def register_hooks(add):
    for path in HOOK_FILES:
        if path.parent.is_dir():
            print(edit_hook_file(path, add))


def install(hours, minutes, apply):
    if WINDOWS:
        what = f"copy scripts to {LIB}; schtasks /Create task '{TASK}' every {minutes} min running mem_tidy.py --apply"
    elif MAC:
        what = f"copy scripts to {LIB}; write {PLIST} (every {minutes} min, mem_tidy.py --apply); launchctl load"
    else:
        what = (f"copy scripts to {LIB}; write {UNITS / 'memory-tidy.service'} (idle threshold {hours}h, with --apply) and "
                f"{UNITS / 'memory-tidy.timer'} (every {minutes} min); systemctl --user daemon-reload; enable --now memory-tidy.timer")
    if not apply:
        print("Preview only. Re-run with --apply to do this:\n  - " + what)
        return 0
    if WINDOWS:
        copy_scripts()
        cmd = " ".join(f'"{a}"' for a in job_args(hours))
        out = run(["schtasks", "/Create", "/F", "/TN", TASK, "/SC", "MINUTE", "/MO", str(minutes), "/TR", cmd])
        print(out.stdout.strip() or out.stderr.strip())
        return out.returncode
    if MAC:
        copy_scripts()
        PLIST.parent.mkdir(parents=True, exist_ok=True)
        args = "".join(f"<string>{a}</string>" for a in job_args(hours))
        PLIST.write_text(PLIST_TEMPLATE.format(args=args, seconds=minutes * 60))
        run(["launchctl", "unload", str(PLIST)])
        out = run(["launchctl", "load", str(PLIST)])
        print(out.stderr.strip() or "installed; check with: launchctl list | grep memory-tidy")
        return out.returncode
    if systemctl("--version").returncode != 0:
        print("systemd user session not available; nothing installed", file=sys.stderr)
        return 1
    copy_scripts()
    UNITS.mkdir(parents=True, exist_ok=True)
    exec_line = " ".join(job_args(hours)) if FROZEN else f"/usr/bin/python3 -I %h/.local/lib/memory-tidy/mem_tidy.py --min-idle-hours {hours} --apply"
    (UNITS / "memory-tidy.service").write_text(SERVICE.format(exec_line=exec_line))
    (UNITS / "memory-tidy.timer").write_text(TIMER.format(minutes=minutes))
    for cmd in (("daemon-reload",), ("enable", "--now", "memory-tidy.timer")):
        out = systemctl(*cmd)
        if out.returncode != 0:
            print(out.stderr.strip(), file=sys.stderr)
            return 1
    print("installed; check with: systemctl --user list-timers memory-tidy.timer")
    return 0


def uninstall(apply):
    if not apply:
        print("Preview only. Re-run with --uninstall --apply to remove the schedule and the copied scripts.")
        return 0
    if WINDOWS:
        run(["schtasks", "/Delete", "/F", "/TN", TASK])
    elif MAC:
        run(["launchctl", "unload", str(PLIST)])
        PLIST.unlink(missing_ok=True)
    else:
        systemctl("disable", "--now", "memory-tidy.timer")
        for path in (UNITS / "memory-tidy.service", UNITS / "memory-tidy.timer"):
            path.unlink(missing_ok=True)
        systemctl("daemon-reload")
    shutil.rmtree(LIB, ignore_errors=True)
    print("uninstalled; handoff notes are kept")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Install or remove the memory-tidy schedule (systemd, launchd or Task Scheduler) (preview by default)")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--no-hook", action="store_true", help="do not add the session start reminder to Claude Code and Codex")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--min-idle-hours", type=float, default=4)
    ap.add_argument("--every-minutes", type=int, default=10)
    args = ap.parse_args()
    if args.uninstall:
        code = uninstall(args.apply)
        if args.apply:
            register_hooks(False)
        return code
    code = install(args.min_idle_hours, args.every_minutes, args.apply)
    if args.apply and not args.no_hook:
        register_hooks(True)
    elif not args.apply:
        print("  - add a SessionStart hook ('" + hint_command() + "') to ~/.claude/settings.json and ~/.codex/hooks.json when those folders exist (backup kept)")
    return code


if __name__ == "__main__":
    sys.exit(main())
