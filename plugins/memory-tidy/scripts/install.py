#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME = Path.home()
LIB = HOME / ".local/lib/memory-tidy"
UNITS = HOME / ".config/systemd/user"
SCRIPTS = ("mem_tidy.py", "idle_agents.py", "orphan_servers.py", "tmp_cleanup.py")

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


def install(hours, minutes, apply):
    steps = [f"copy {', '.join(SCRIPTS)} to {LIB}",
             f"write {UNITS / 'memory-tidy.service'} (idle threshold {hours}h, with --apply)",
             f"write {UNITS / 'memory-tidy.timer'} (every {minutes} min)",
             "systemctl --user daemon-reload; enable --now memory-tidy.timer"]
    if not apply:
        print("Preview only. Re-run with --apply to do these steps:")
        print("\n".join(f"  - {s}" for s in steps))
        return 0
    if systemctl("--version").returncode != 0:
        print("systemd user session not available; nothing installed", file=sys.stderr)
        return 1
    LIB.mkdir(parents=True, exist_ok=True)
    UNITS.mkdir(parents=True, exist_ok=True)
    for name in SCRIPTS:
        shutil.copy2(HERE / name, LIB / name)
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
        print("Preview only. Re-run with --uninstall --apply to disable the timer and remove the units and scripts.")
        return 0
    systemctl("disable", "--now", "memory-tidy.timer")
    for path in (UNITS / "memory-tidy.service", UNITS / "memory-tidy.timer"):
        path.unlink(missing_ok=True)
    shutil.rmtree(LIB, ignore_errors=True)
    systemctl("daemon-reload")
    print("uninstalled; handoff notes in ~/.local/state/idle-agents/handoffs/ are kept")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Install or remove the memory-tidy systemd timer (preview by default)")
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
