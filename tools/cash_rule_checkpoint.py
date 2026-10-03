#!/usr/bin/env python3
"""Append one cash-rule 1.2.0 checkpoint record and validate the whole file.

Reads the last record of the same task to fill previous_task_state,
previous_step_state (only when the step id is unchanged) and iteration.
The new record is written only if the file still validates afterwards
(schema + transitions, via the skill's validate_checkpoints.py).

Run with:
  uv run --with-requirements ~/.claude/skills/cash-rule/scripts/requirements.txt \
    python3 ~/tools/cash_rule_checkpoint.py FILE --task T --step S \
    --task-state RUNNING --step-state RUNNING --target "..." \
    [--evidence kind=locator ...] [--check name=pass ...] [--decision continue] \
    [--next "..."] [--executor claude-opus-5-5] [--neg "procedure=>evidence"]
"""

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

SKILL = Path.home() / ".claude/skills/cash-rule/scripts/validate_checkpoints.py"


def last_record(path: Path, task: str) -> dict | None:
    if not path.exists():
        return None
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if r.get("task_id") == task]
    return rows[-1] if rows else None


def build(args, prev: dict | None) -> dict:
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec="seconds")
    same_step = prev is not None and prev.get("step_id") == args.step
    evidence = []
    for item in args.evidence:
        kind, _, locator = item.partition("=")
        evidence.append({"kind": kind, "locator": locator, "source": args.source, "observed_at": now,
                         "git_sha": None, "scope": None, "note": None})
    checks = []
    for item in args.check:
        name, _, result = item.partition("=")
        checks.append({"name": name, "result": result or "pass", "evidence": None})
    results = {c["result"] for c in checks}
    overall = "not_run" if not checks else ("pass" if results <= {"pass", "not_applicable"} else
                                             "fail" if results == {"fail"} else "partial")
    negative = None
    if args.neg:
        procedure, _, ev = args.neg.partition("=>")
        negative = {"result": "pass", "procedure": procedure, "evidence": ev or None}
    return {
        "protocol_version": "1.2.0", "task_id": args.task, "step_id": args.step,
        "iteration": (prev["iteration"] + 1) if prev else 1, "recorded_at": now,
        "previous_task_state": prev["task_state"] if prev else None, "task_state": args.task_state,
        "previous_step_state": prev["step_state"] if same_step else None, "step_state": args.step_state,
        "target": args.target, "evidence_before": [],
        "dispatch": {"executor": args.executor, "model": args.executor, "reason": args.reason,
                     "risk": {"importance": "high", "difficulty": "medium", "uncertainty": "medium",
                              "impact": args.impact}},
        "actions": [{"summary": args.target, "executor": args.executor}],
        "evidence_after": evidence,
        "validation": {"checks": checks, "result": overall, "evaluation_required": False,
                       "negative_control": negative},
        "review": {"proven": args.proven, "not_proven": args.not_proven, "new_risks": args.risk},
        "decision": args.decision, "next_target": args.next, "telemetry_mode": "minimal",
        "usage": {"input_tokens": {"value": None, "status": "unavailable",
                                   "source": "no per-step meter in this session"}},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path)
    ap.add_argument("--task", required=True)
    ap.add_argument("--step", required=True)
    ap.add_argument("--task-state", required=True)
    ap.add_argument("--step-state", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--evidence", action="append", default=[], help="kind=locator")
    ap.add_argument("--check", action="append", default=[], help="name=pass|fail|not_run")
    ap.add_argument("--proven", action="append", default=[])
    ap.add_argument("--not-proven", action="append", default=[])
    ap.add_argument("--risk", action="append", default=[])
    ap.add_argument("--neg", default="", help="negative control: procedure=>evidence")
    ap.add_argument("--decision", default="continue")
    ap.add_argument("--next", default=None)
    ap.add_argument("--executor", default="claude-opus-5-5")
    ap.add_argument("--reason", default="supervisor executes and validates")
    ap.add_argument("--impact", default="see LOOP file")
    ap.add_argument("--source", default="repo")
    args = ap.parse_args()
    record = build(args, last_record(args.file, args.task))
    original = args.file.read_text(encoding="utf-8") if args.file.exists() else ""
    args.file.write_text(original + json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    check = subprocess.run([sys.executable, str(SKILL), str(args.file)], capture_output=True, text=True)
    if check.returncode != 0:
        args.file.write_text(original, encoding="utf-8")
        print("rejected; file restored:\n" + check.stdout + check.stderr, file=sys.stderr)
        return 1
    print(f"appended iteration {record['iteration']} ({record['task_state']}/{record['step_state']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
