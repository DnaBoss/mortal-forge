#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
STEPS = [
    ("閒置 claude／codex", "idle_agents.py", ["--min-idle-hours"]),
    ("孤兒開發伺服器", "orphan_servers.py", []),
    ("/tmp 舊檔", "tmp_cleanup.py", []),
]


def run(script, args):
    out = subprocess.run([sys.executable, "-I", str(TOOLS / script), *args], capture_output=True, text=True)
    return out.returncode, (out.stdout + out.stderr).strip()


def used_line():
    return run("idle_agents.py", ["--report"])[1].splitlines()[0]


def main():
    ap = argparse.ArgumentParser(description="一次檢查所有能釋放記憶體的項目；預設只預覽")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--min-idle-hours", default="6")
    args = ap.parse_args()

    print("開始前：" + used_line())
    failed = 0
    for title, script, extra in STEPS:
        step_args = [extra[0], args.min_idle_hours] if extra else []
        if args.apply:
            step_args.append("--apply")
        code, text = run(script, step_args)
        failed += code != 0
        print(f"\n== {title}（結束碼 {code}）\n{text}")
    if args.apply:
        print("\n結束後：" + used_line())
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
