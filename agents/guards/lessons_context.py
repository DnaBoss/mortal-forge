#!/usr/bin/env python3
"""SessionStart: on host Essence, inject ~/.agents/lessons.md so past mistakes are read first.

Only entries dated within the last MAX_AGE_DAYS and without a `- guard:` line are
injected. Explicit project scopes are filtered and prioritized; untagged entries
retain the legacy newest-first selection. No lesson contents are rewritten.
"""
import datetime as dt
import json
import os
import re
import socket
import sys
from pathlib import Path

BUDGET_BYTES = 9000  # lowered from 12000 on 2026-10-03 when guard-covered entries left the injection
MAX_AGE_DAYS = 30
ENTRY = re.compile(r"^(## |\d+\. )", re.M)
GUARDED = re.compile(r"^- guard:", re.M)
DATED = re.compile(r"^## (\d{4}-\d{2}-\d{2})")
PROJECTS = re.compile(r"^- projects:\s*(.*)$", re.M)


def scope_match(entry, cwd):
    """Return (eligible, scoped); malformed explicit scopes never become global."""
    markers = PROJECTS.findall(entry)
    if not markers:
        return True, False
    if len(markers) != 1 or not isinstance(cwd, str) or not Path(cwd).is_absolute():
        return False, True
    try:
        roots = json.loads(markers[0])
        if not isinstance(roots, list) or not roots:
            return False, True
        if any(not isinstance(root, str) or not Path(root).is_absolute() for root in roots):
            return False, True
        here = Path(cwd).resolve()
        return any(here.is_relative_to(Path(root).resolve()) for root in roots), True
    except (ValueError, OSError, RuntimeError):
        return False, True


def recent(entry, today, max_age_days=MAX_AGE_DAYS):
    m = DATED.match(entry)
    if not m:
        return False  # undated or legacy numbered entries count as old
    try:
        day = dt.date.fromisoformat(m.group(1))
    except ValueError:
        return False
    return (today - day).days <= max_age_days


def select(text, budget=BUDGET_BYTES, today=None, cwd=None):
    today = today or dt.date.today()
    starts = [m.start() for m in ENTRY.finditer(text)]
    if not starts:
        return text if len(text.encode()) <= budget else text.encode()[:budget].decode(errors="ignore")
    header = text[:starts[0]]
    entries = [text[a:b] for a, b in zip(starts, starts[1:] + [len(text)])]
    guarded = sum(1 for e in entries if GUARDED.search(e))
    entries = [e for e in entries if not GUARDED.search(e)]
    old = sum(1 for e in entries if not recent(e, today))
    entries = [e for e in entries if recent(e, today)]
    scoped = [(i, e, scope_match(e, cwd)) for i, e in enumerate(entries)]
    excluded = sum(not match[0] for _, _, match in scoped)
    candidates = [(i, e, match[1]) for i, e, match in scoped if match[0]]
    candidates.sort(key=lambda item: (item[2], item[0]), reverse=True)
    kept, used = [], len(header.encode())
    for i, e, is_scoped in candidates:
        size = len(e.encode())
        if used + size > budget:
            if not is_scoped:
                break
            continue
        kept.append((i, e))
        used += size
    kept.sort()
    notes = []
    if old:
        notes.append(f"{old} 條超過 {MAX_AGE_DAYS} 天未載入，查特定錯誤時 rg ~/.agents/lessons.md")
    if len(candidates) - len(kept):
        notes.append(f"近 {MAX_AGE_DAYS} 天的 {len(candidates) - len(kept)} 條超出預算未載入")
    if excluded:
        notes.append(f"{excluded} 條專案不符、未知或標記無效，未載入")
    if guarded:
        notes.append(f"{guarded} 條已由 guard 機械擋下，只留在檔案")
    note = f"（{'；'.join(notes)}）\n\n" if notes else ""
    return header + note + "".join(e for _, e in kept)


def main():
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("Expected hook object")
    except (ValueError, OSError):
        print("lessons_context: invalid hook input; project scope unknown", file=sys.stderr)
        payload = {}
    path = os.path.expanduser("~/.agents/lessons.md")
    if socket.gethostname() == "Essence" and os.path.isfile(path):
        text = select(Path(path).read_text(encoding="utf-8"), cwd=payload.get("cwd"))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
              "additionalContext": "開工必讀：錯誤知識庫（同樣的錯不得再犯）\n\n" + text}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
