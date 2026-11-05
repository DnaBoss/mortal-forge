#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
HANDOFFS = HOME / ".local/state/idle-agents/handoffs"
STATE = HOME / ".memory-tidy"
SHOWN = STATE / "shown.txt"
NAG = STATE / "schedule-hint.txt"
RECENT_DAYS = 3
MAX_LISTED = 3
NAG_DAYS = 7


def schedule_installed():
    if os.name == "nt":
        return subprocess.run(["schtasks", "/Query", "/TN", "memory-tidy"], capture_output=True).returncode == 0
    if sys.platform == "darwin":
        return (HOME / "Library/LaunchAgents/com.memory-tidy.plist").exists()
    return (HOME / ".config/systemd/user/memory-tidy.timer").exists()


def field(text, label):
    m = re.search(rf"^- {label}：(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def first_task(text):
    m = re.search(r"## 原本的任務\n(.+)", text)
    line = m.group(1).strip() if m else ""
    return "" if line.startswith("（") else line[:120]


def read_set(path):
    try:
        return set(path.read_text().split())
    except OSError:
        return set()


def pending_handoffs(cwd):
    if not HANDOFFS.is_dir():
        return []
    shown = read_set(SHOWN)
    cutoff = time.time() - RECENT_DAYS * 86400
    rows = []
    for p in sorted(HANDOFFS.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.name in shown or p.stat().st_mtime < cutoff:
            continue
        text = p.read_text(errors="replace")
        rows.append((p.name, field(text, "目錄"), field(text, "分支"), field(text, "產生時間"),
                     field(text, "還原指令"), first_task(text)))
    rows.sort(key=lambda r: r[1] != cwd)
    return rows[:MAX_LISTED]


def mark_shown(names):
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        with SHOWN.open("a") as f:
            f.write("\n".join(names) + "\n")
    except OSError:
        pass


def schedule_nag():
    if schedule_installed():
        return ""
    try:
        if time.time() - NAG.stat().st_mtime < NAG_DAYS * 86400:
            return ""
    except OSError:
        pass
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        NAG.write_text(str(int(time.time())))
    except OSError:
        pass
    return "memory-tidy 還沒有設定自動排程，閒置的 claude／codex 不會被自動收尾。請問使用者要不要用 memory-tidy 技能預覽並開啟排程（需使用者同意）。"


def main():
    try:
        cwd = json.load(sys.stdin).get("cwd", "")
    except (ValueError, OSError):
        cwd = ""
    parts = []
    rows = pending_handoffs(cwd)
    if rows:
        lines = ["上次有被自動關閉、可能還沒做完的工作階段（請在開頭用一兩句話告訴使用者，並問要不要接續）："]
        for name, folder, branch, when, resume, task in rows:
            lines.append(f"- {when} {folder}" + (f"（分支 {branch}）" if branch else "") + (f"：{task}" if task else "") + f"\n  接續：{resume}")
        parts.append("\n".join(lines))
        mark_shown([r[0] for r in rows])
    nag = schedule_nag()
    if nag:
        parts.append(nag)
    if parts:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n\n".join(parts)}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
