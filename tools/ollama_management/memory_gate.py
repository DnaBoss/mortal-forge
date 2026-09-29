#!/usr/bin/env python3
"""Gate model admission and stop Ollama on host memory pressure."""

import argparse
import fcntl
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MIN_AVAILABLE_KIB = 16 * 1024 * 1024
STOP_KIB = 12 * 1024 * 1024
KILL_KIB = 8 * 1024 * 1024
STATE = Path("/var/lib/ollama-resource-guard/blocked.json")
MEMINFO = Path("/proc/meminfo")
EVENTS = Path("/sys/fs/cgroup/system.slice/ollama.service/cgroup.events")


def available_kib(text: str) -> int:
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] == "MemAvailable:":
            if len(fields) != 3 or fields[2] != "kB":
                raise ValueError("invalid MemAvailable unit")
            value = int(fields[1])
            if value < 0:
                raise ValueError("negative MemAvailable")
            return value
    raise ValueError("MemAvailable missing")


def emit(event: str, **fields: object) -> None:
    print(json.dumps({"event": event, **fields}), flush=True)


def save_state(state: dict) -> None:
    temporary = STATE.with_suffix(".tmp")
    with temporary.open("w") as handle:
        json.dump(state, handle)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(STATE)


def populated() -> bool:
    try:
        return "populated 1" in EVENTS.read_text().splitlines()
    except FileNotFoundError:
        return False


def command(*args: str) -> None:
    subprocess.run(["/usr/bin/systemctl", *args], check=True, timeout=5)


def request_action(state: dict, action: str, *args: str) -> None:
    try:
        command(*args)
        state[action + "_accepted"] = True
    except (OSError, subprocess.SubprocessError) as exc:
        state[action + "_accepted"] = False
        state[action + "_error"] = str(exc)
        save_state(state)
        raise
    save_state(state)


def tick(available: int) -> None:
    state = json.loads(STATE.read_text()) if STATE.exists() else None
    if available <= STOP_KIB and state is None:
        state = {"blocked_at": datetime.now(timezone.utc).isoformat(),
                 "available_kib": available, "stop_requested": True}
        save_state(state)
        emit("pressure_stop", **state)
        request_action(state, "stop", "--no-block", "stop", "ollama.service")
    if state is None:
        return
    running = populated()
    if available <= KILL_KIB and not state.get("critical_recorded"):
        state["critical_recorded"] = True
        state["kill_requested"] = running
        save_state(state)
        emit("critical_pressure", available_kib=available, model_running=running)
        if running:
            request_action(state, "kill", "kill", "--signal=SIGKILL",
                           "--kill-whom=all", "ollama.service")
    if not running and not state.get("observed_stopped"):
        state["observed_stopped"] = True
        state["available_after_stop_kib"] = available
        save_state(state)
        emit("model_stopped", available_kib=available,
             pressure_remains=available <= STOP_KIB)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=["check", "tick", "status", "resume"],
                        default="check")
    args = parser.parse_args()
    try:
        available = available_kib(MEMINFO.read_text())
        blocked = STATE.exists()
        if args.mode == "check":
            allowed = not blocked and available >= MIN_AVAILABLE_KIB
            emit("admission", allowed=allowed, blocked=blocked,
                 available_kib=available, minimum_kib=MIN_AVAILABLE_KIB)
            return 0 if allowed else 1
        if args.mode == "status":
            emit("status", available_kib=available, blocked=blocked,
                 state=json.loads(STATE.read_text()) if blocked else None)
            return 0
        if os.geteuid() != 0:
            raise PermissionError("tick and resume require root")
        lock = (STATE.parent / "guard.lock").open("a")
        fcntl.flock(lock, fcntl.LOCK_EX)
        available = available_kib(MEMINFO.read_text())
        blocked = STATE.exists()
        if args.mode == "resume":
            if available < MIN_AVAILABLE_KIB:
                raise ValueError("need at least 16 GiB available before resume")
            if blocked and populated():
                raise ValueError("wait for the stopped service to release its processes")
            STATE.unlink(missing_ok=True)
            emit("resume_unblocked", available_kib=available,
                 next_command="sudo systemctl start ollama.service")
        else:
            tick(available)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"event": "guard_error", "error": str(exc)}),
              file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
