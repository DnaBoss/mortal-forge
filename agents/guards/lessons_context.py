#!/usr/bin/env python3
"""SessionStart: on host Essence, inject ~/.agents/lessons.md so past mistakes are read first."""
import json, os, socket, sys

try:
    sys.stdin.read()
except Exception:
    pass
path = os.path.expanduser("~/.agents/lessons.md")
if socket.gethostname() == "Essence" and os.path.isfile(path):
    text = open(path, encoding="utf-8").read()[:12000]
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart",
          "additionalContext": "開工必讀：錯誤知識庫（同樣的錯不得再犯）\n\n" + text}}, ensure_ascii=False))
