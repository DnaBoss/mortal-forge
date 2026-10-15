#!/usr/bin/env python3
"""SessionStart: on host Essence, inject ~/.agents/lessons.md so past mistakes are read first.

Only entries dated within the last MAX_AGE_DAYS and without a `- guard:` line are
injected (user 2026-10-15: old lessons either became guards or are looked up on
demand). Within that set, the NEWEST entries are kept up to the byte budget.
"""
import datetime as dt
import json, os, re, socket, sys

BUDGET_BYTES = 9000  # lowered from 12000 on 2026-10-03 when guard-covered entries left the injection
MAX_AGE_DAYS = 30
ENTRY = re.compile(r"^(## |\d+\. )", re.M)
GUARDED = re.compile(r"^- guard:", re.M)
DATED = re.compile(r"^## (\d{4}-\d{2}-\d{2})")


def recent(entry, today, max_age_days=MAX_AGE_DAYS):
    m = DATED.match(entry)
    if not m:
        return False  # undated or legacy numbered entries count as old
    try:
        day = dt.date.fromisoformat(m.group(1))
    except ValueError:
        return False
    return (today - day).days <= max_age_days


def select(text, budget=BUDGET_BYTES, today=None):
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
    kept, used = [], len(header.encode())
    for e in reversed(entries):
        size = len(e.encode())
        if used + size > budget:
            break
        kept.insert(0, e)
        used += size
    notes = []
    if old:
        notes.append(f"{old} 條超過 {MAX_AGE_DAYS} 天未載入，查特定錯誤時 rg ~/.agents/lessons.md")
    if len(entries) - len(kept):
        notes.append(f"近 {MAX_AGE_DAYS} 天較舊的 {len(entries) - len(kept)} 條超出預算未載入")
    if guarded:
        notes.append(f"{guarded} 條已由 guard 機械擋下，只留在檔案")
    note = f"（{'；'.join(notes)}）\n\n" if notes else ""
    return header + note + "".join(kept)


def main():
    try:
        sys.stdin.read()
    except Exception:
        pass
    path = os.path.expanduser("~/.agents/lessons.md")
    if socket.gethostname() == "Essence" and os.path.isfile(path):
        text = select(open(path, encoding="utf-8").read())
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
              "additionalContext": "開工必讀：錯誤知識庫（同樣的錯不得再犯）\n\n" + text}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
