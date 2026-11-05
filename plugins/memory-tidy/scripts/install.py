#!/usr/bin/env python3
import argparse
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
SCRIPTS = ("mem_tidy.py", "idle_agents.py", "orphan_servers.py", "tmp_cleanup.py", "tidy_any.py")

PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.memory-tidy</string>
<key>ProgramArguments</key><array><string>{python}</string><string>-I</string><string>{script}</string><string>--apply</string><string>--tmp</string></array>
<key>StartInterval</key><integer>{seconds}</integer>
<key>Nice</key><integer>10</integer>
<key>RunAtLoad</key><false/>
</dict></plist>
"""

SERVICE = """[Unit]
Description=Free memory: close idle claude/codex, stop orphan dev servers, clean stale /tmp

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 -I %h/.local/lib/memory-tidy/mem_tidy.py --min-idle-hours {hours} --apply
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
    for name in SCRIPTS:
        shutil.copy2(HERE / name, LIB / name)


def install(hours, minutes, apply):
    if WINDOWS:
        what = f"copy scripts to {LIB}; schtasks /Create task '{TASK}' every {minutes} min running tidy_any.py --apply --tmp"
    elif MAC:
        what = f"copy scripts to {LIB}; write {PLIST} (every {minutes} min, tidy_any.py --apply --tmp); launchctl load"
    else:
        what = (f"copy scripts to {LIB}; write {UNITS / 'memory-tidy.service'} (idle threshold {hours}h, with --apply) and "
                f"{UNITS / 'memory-tidy.timer'} (every {minutes} min); systemctl --user daemon-reload; enable --now memory-tidy.timer")
    if not apply:
        print("Preview only. Re-run with --apply to do this:\n  - " + what)
        return 0
    if WINDOWS:
        copy_scripts()
        cmd = f'"{sys.executable}" -I "{LIB / "tidy_any.py"}" --apply --tmp'
        out = run(["schtasks", "/Create", "/F", "/TN", TASK, "/SC", "MINUTE", "/MO", str(minutes), "/TR", cmd])
        print(out.stdout.strip() or out.stderr.strip())
        return out.returncode
    if MAC:
        copy_scripts()
        PLIST.parent.mkdir(parents=True, exist_ok=True)
        PLIST.write_text(PLIST_TEMPLATE.format(python=sys.executable, script=LIB / "tidy_any.py", seconds=minutes * 60))
        run(["launchctl", "unload", str(PLIST)])
        out = run(["launchctl", "load", str(PLIST)])
        print(out.stderr.strip() or "installed; check with: launchctl list | grep memory-tidy")
        return out.returncode
    if systemctl("--version").returncode != 0:
        print("systemd user session not available; nothing installed", file=sys.stderr)
        return 1
    copy_scripts()
    UNITS.mkdir(parents=True, exist_ok=True)
    (UNITS / "memory-tidy.service").write_text(SERVICE.format(hours=hours))
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
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--min-idle-hours", type=float, default=4)
    ap.add_argument("--every-minutes", type=int, default=10)
    args = ap.parse_args()
    if args.uninstall:
        return uninstall(args.apply)
    return install(args.min_idle_hours, args.every_minutes, args.apply)


if __name__ == "__main__":
    sys.exit(main())
