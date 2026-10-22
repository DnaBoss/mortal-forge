#!/usr/bin/env python3
"""Emit the shared workflow without inspecting or storing user content."""

import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
EVENTS = {"SessionStart", "UserPromptSubmit"}


def context(payload, skill=SKILL):
    if not isinstance(payload, dict):
        raise ValueError("Hook input must be an object")
    event = payload.get("hook_event_name")
    if event not in EVENTS:
        return {}
    text = skill.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0].strip() or not parts[2].strip():
        raise ValueError("Skill frontmatter or body is missing")
    return {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": parts[2].strip(),
        }
    }


def main():
    try:
        result = context(json.load(sys.stdin))
    except (OSError, ValueError, TypeError):
        print("cash-workflow: unable to load hook input or skill", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
