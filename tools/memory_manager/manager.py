import argparse
import errno
import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

MIB = 1024**2
ROOT = Path(
    f"/sys/fs/cgroup/user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service"
)
STATE = Path(f"/run/user/{os.getuid()}/memory-manager")
INTERVAL = 30


def numbers(path):
    return {
        k.rstrip(":"): int(v.split()[0])
        for k, v in (line.split(maxsplit=1) for line in path.read_text().splitlines())
    }


def pressure(path):
    return float(path.read_text().splitlines()[0].split()[1].split("=")[1])


def swap_reason(swaps=Path("/proc/swaps"), block=Path("/sys/block")):
    devices = [line.split()[0] for line in swaps.read_text().splitlines()[1:]]
    if not devices:
        return "沒有交換區"
    for device in devices:
        name = Path(device).name
        if not name.startswith("zram"):
            return "交換區包含磁碟，暫停以避免增加 SSD 寫入"
        if (block / name / "backing_dev").read_text().strip() != "none":
            return "zram 已設定磁碟寫回，暫停回收"
    return ""


def groups(root=ROOT):
    found = []
    for base, dirs, files in os.walk(root):
        path = Path(base)
        if path != root and path.suffix in (".scope", ".service"):
            dirs[:] = []
            if (
                "memory.reclaim" in files
                and path.name != "aletheia-cold-reclaim.service"
            ):
                found.append(path)
    return found


def snapshot(path):
    values = numbers(path / "memory.stat")
    return {
        "id": path.stat().st_ino,
        "current": int((path / "memory.current").read_text()),
        "anon": values["anon"],
        "cold": values["inactive_anon"],
        "refault": values["workingset_refault_anon"],
        "swap": int((path / "memory.swap.current").read_text()),
        "psi": pressure(path / "memory.pressure"),
    }


def amount(now, before, swap_free, budget):
    if not before or before["id"] != now["id"]:
        return 0, "先觀察一輪"
    if now["refault"] > before["refault"]:
        return 0, "已換出的資料又被使用，暫停此組"
    if now["psi"] >= 1:
        return 0, "此組正在等待記憶體，暫停此組"
    size = min(
        128 * MIB,
        budget,
        max(0, swap_free - 1024 * MIB),
        max(0, min(now["cold"], before["cold"]) - 64 * MIB),
        now["anon"] // 20,
    )
    return (
        (size, "主動回收") if size >= 16 * MIB else (0, "未達本輪回收量或交換區保留量")
    )


def reclaim(path, size):
    try:
        (path / "memory.reclaim").write_text(f"{size} swappiness=max")
        return 0
    except OSError as exc:
        print(json.dumps({"errno": exc.errno, "error": str(exc)}, ensure_ascii=False))
        return 2 if exc.errno == errno.EAGAIN else 1


def model_status():
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:11434/api/ps", timeout=2
        ) as response:
            return json.load(response)["models"]
    except (OSError, ValueError, KeyError) as exc:
        return {"error": str(exc)}


def cycle(previous, dry=False):
    mem = numbers(Path("/proc/meminfo"))
    reason = swap_reason()
    if not reason and pressure(Path("/proc/pressure/io")) >= 10:
        reason = "磁碟正在忙碌，暫停本輪"
    if not reason and mem["SwapFree"] * 1024 <= 1024 * MIB:
        reason = "交換區保留至少 1 GiB，暫停本輪"
    result = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "pid": os.getpid(),
        "version": "1.0",
        "dry": dry,
        "reason": reason,
        "memory_used": (mem["MemTotal"] - mem["MemAvailable"]) * 1024,
        "gpu_memory": mem.get("GPUActive", 0) * 1024,
        "swap_free": mem["SwapFree"] * 1024,
        "models": model_status(),
        "requested": 0,
        "observed_anon_decrease": 0,
        "groups": [],
    }
    budget = 256 * MIB
    swap_remaining = result["swap_free"]
    current = {}
    deadline = time.monotonic() + 15
    for path in groups():
        key = str(path.relative_to(ROOT))
        row = {"group": key}
        try:
            now = snapshot(path)
            current[key] = now
            size, why = amount(now, previous.get(key), swap_remaining, budget)
            row.update(now, reason=reason or why, requested=0)
            if size and not reason and time.monotonic() < deadline:
                row["requested"] = size
                budget -= size
                result["requested"] += size
                swap_remaining -= size
                if not dry:
                    completed = subprocess.run(
                        [sys.executable, __file__, "--reclaim", str(path), str(size)],
                        capture_output=True,
                        text=True,
                        timeout=3,
                        check=False,
                    )
                    row["returncode"] = completed.returncode
                    row["detail"] = (completed.stdout + completed.stderr)[-1000:]
                    after = snapshot(path)
                    row["anon_after"] = after["anon"]
                    row["swap_after"] = after["swap"]
                    result["observed_anon_decrease"] += max(
                        0, now["anon"] - after["anon"]
                    )
            result["groups"].append(row)
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as exc:
            row["error"] = str(exc)
            result["groups"].append(row)
    return result, current


def save(result):
    target = STATE / "status.tmp"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    target.replace(STATE / "status.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--reclaim", nargs=2)
    args = parser.parse_args()
    if args.reclaim:
        path = Path(args.reclaim[0]).resolve()
        size = int(args.reclaim[1])
        if not path.is_relative_to(ROOT) or path == ROOT or not 0 < size <= 128 * MIB:
            return 1
        return reclaim(path, size)
    if args.status:
        data = json.loads((STATE / "status.json").read_text())
        data["age_seconds"] = round(
            time.time() - (STATE / "status.json").stat().st_mtime, 1
        )
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0 if data["age_seconds"] < 90 and "error" not in data else 1
    if args.dry_run:
        result, _ = cycle({}, dry=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (STATE / "lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("已有記憶體管理程序執行中", file=sys.stderr)
            return 1
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        previous = {}
        tick = 0
        while not stop.is_set():
            try:
                result, previous = cycle(previous)
                save(result)
                errors = [
                    row
                    for row in result["groups"]
                    if "error" in row or row.get("returncode", 0) not in (0, 2)
                ]
                if tick % 20 == 0 or errors:
                    print(
                        json.dumps(
                            {
                                "time": result["time"],
                                "reason": result["reason"],
                                "requested": result["requested"],
                                "errors": errors,
                            },
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
            except (OSError, ValueError, KeyError) as exc:
                save({"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "error": str(exc)})
                print(json.dumps({"error": str(exc)}, ensure_ascii=False), flush=True)
            tick += 1
            stop.wait(INTERVAL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
