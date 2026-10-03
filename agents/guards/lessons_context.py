#!/usr/bin/env python3
"""SessionStart: on host Essence, inject ~/.agents/lessons.md so past mistakes are read first.

Entries that carry a `- guard:` line are already blocked mechanically by a hook, so
they stay in the file but are not injected. When the rest is over budget, keep the
header and the NEWEST entries (cut at entry boundaries) so new lessons are never
the ones dropped.
"""
import json, os, re, socket, sys

BUDGET_BYTES = 9000  # lowered from 12000 on 2026-10-03 when guard-covered entries left the injection
ENTRY = re.compile(r"^(## |\d+\. )", re.M)
GUARDED = re.compile(r"^- guard:", re.M)


def select(text, budget=BUDGET_BYTES):
    starts = [m.start() for m in ENTRY.finditer(text)]
    if not starts:
        return text if len(text.encode()) <= budget else text.encode()[:budget].decode(errors="ignore")
    header = text[:starts[0]]
    entries = [text[a:b] for a, b in zip(starts, starts[1:] + [len(text)])]
    guarded = sum(1 for e in entries if GUARDED.search(e))
    entries = [e for e in entries if not GUARDED.search(e)]
    kept, used = [], len(header.encode())
    for e in reversed(entries):
        size = len(e.encode())
        if used + size > budget:
            break
        kept.insert(0, e)
        used += size
    notes = []
    if len(entries) - len(kept):
        notes.append(f"較舊的 {len(entries) - len(kept)} 條未載入，需要時讀 ~/.agents/lessons.md")
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
