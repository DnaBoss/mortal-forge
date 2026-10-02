#!/usr/bin/env python3
"""SessionStart: on host Essence, inject ~/.agents/lessons.md so past mistakes are read first.

When the file is over budget, keep the header and the NEWEST entries (cut at entry
boundaries) so new lessons are never the ones dropped.
"""
import json, os, re, socket, sys

BUDGET_BYTES = 12000
ENTRY = re.compile(r"^(## |\d+\. )", re.M)


def select(text, budget=BUDGET_BYTES):
    if len(text.encode()) <= budget:
        return text
    starts = [m.start() for m in ENTRY.finditer(text)]
    if not starts:
        return text.encode()[:budget].decode(errors="ignore")
    header = text[:starts[0]]
    entries = [text[a:b] for a, b in zip(starts, starts[1:] + [len(text)])]
    kept, used = [], len(header.encode())
    for e in reversed(entries):
        size = len(e.encode())
        if used + size > budget:
            break
        kept.insert(0, e)
        used += size
    note = f"（較舊的 {len(entries) - len(kept)} 條未載入，需要時讀 ~/.agents/lessons.md）\n\n"
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
