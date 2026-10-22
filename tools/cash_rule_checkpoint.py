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

Executing states need --acceptance (which overall acceptance item this round serves).
Stopping (--decision block|fail) needs --stop-reason and --stop-unblock; reasons
no_path / infeasible also need --stop-attempt "path=>evidence" (3 distinct paths for
no_path), --stop-shrunk, --stop-searched and --stop-reviewer.

Burden cut (user 2026-10-15):
- A record with the same task_state / step / step_state as the previous record of the
  task and no new evidence locator or check is rejected (no heartbeat records).
- --decision wait needs --wait-on (who or what) and at least one --wait-tried
  "alternative=>result" (web search, another AI, conventional default). Trade-offs are
  decided, not waited on.
- No usage / telemetry fields are written; token usage is measured afterwards from
  executor transcripts (~/tools/cash_rule_burden.py).
"""

import argparse
import datetime as dt
import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL = Path.home() / ".claude/skills/cash-rule/scripts/validate_checkpoints.py"
EXECUTING = {"RUNNING", "VALIDATING", "REVIEWING"}
STOP_DECISIONS = {"block", "fail"}


def stop_proof(args) -> dict | None:
    if not args.stop_reason:
        return None
    proof = {"reason": args.stop_reason, "unblock": args.stop_unblock}
    if args.stop_attempt:
        proof["attempts"] = [dict(zip(("path", "evidence"), item.partition("=>")[::2]))
                             for item in args.stop_attempt]
    if args.stop_shrunk:
        proof["shrunk"] = args.stop_shrunk
    if args.stop_searched:
        proof["searched"] = args.stop_searched
    if args.stop_reviewer:
        proof["reviewer"] = args.stop_reviewer
    return proof


def gate(args) -> str | None:
    """Rules for new records only; old records in the file stay valid without these fields."""
    if args.task_state in EXECUTING and not args.acceptance:
        return "缺 --acceptance：填這一輪對應主 LOOP 哪一條整體驗收（例 A1）；對不上就不做，改記待辦"
    if args.decision in STOP_DECISIONS and not args.stop_reason:
        return ("停止要舉證：--stop-reason needs_human|no_path|infeasible 與 --stop-unblock；"
                "細則見 cash-rule references/stop-policy.md")
    paths = [item.partition("=>")[0].strip() for item in args.stop_attempt]
    if len(set(paths)) != len(paths):
        return "--stop-attempt 的路不可重複；同一條路換參數只算一條"
    if args.decision == "wait" and (not args.wait_on or not args.wait_tried):
        return ("等人門檻很高（使用者 2026-10-15 定）：--wait-on 寫明等誰／等什麼；--wait-tried 至少一項，"
                "寫明已試過的替代與結果（上網查最佳做法、問另一個 AI、採慣例預設）。只是取捨就自己決定，不等人")
    return None


def heartbeat(prev: dict | None, args) -> str | None:
    """Reject a record that changes no state and adds no evidence (user 2026-10-15)."""
    if prev is None:
        return None
    same = (prev.get("task_state") == args.task_state and prev.get("step_id") == args.step
            and prev.get("step_state") == args.step_state)
    if not same:
        return None
    old_locators = {e.get("locator") for e in prev.get("evidence_after") or []}
    new_locators = {item.partition("=")[2] for item in args.evidence}
    # A check whose result changed (e.g. fail -> pass) is new evidence even when the name repeats.
    old_checks = {(c.get("name"), c.get("result")) for c in (prev.get("validation") or {}).get("checks") or []}
    new_checks = {(item.partition("=")[0], item.partition("=")[2] or "pass") for item in args.check}
    if new_locators - old_locators or new_checks - old_checks:
        return None
    return "無狀態變化且無新證據，不寫（使用者 2026-10-15 定：有狀態變化或新證據才寫 checkpoint）"


def last_record(path: Path, task: str) -> dict | None:
    if not path.exists():
        return None
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if r.get("task_id") == task]
    return rows[-1] if rows else None


def last_step_state(path: Path, task: str, step: str) -> str | None:
    """Last recorded state of this step, even when other steps were recorded after it."""
    if not path.exists():
        return None
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = [r for r in rows if r.get("task_id") == task and r.get("step_id") == step]
    return rows[-1]["step_state"] if rows else None


def build(args, prev: dict | None, prev_step_state: str | None = None) -> dict:
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
    extra = {}
    if args.acceptance:
        extra["acceptance"] = args.acceptance
    if stop_proof(args):
        extra["stop_proof"] = stop_proof(args)
    if args.decision == "wait":
        extra["blockers"] = [f"wait_on: {args.wait_on}"] + [f"tried: {t}" for t in args.wait_tried]
    return extra | {
        "protocol_version": "1.2.0", "task_id": args.task, "step_id": args.step,
        "iteration": (prev["iteration"] + 1) if prev else 1, "recorded_at": now,
        "previous_task_state": prev["task_state"] if prev else None, "task_state": args.task_state,
        "previous_step_state": prev["step_state"] if same_step else prev_step_state, "step_state": args.step_state,
        "target": args.target, "evidence_before": [],
        "dispatch": {"executor": args.executor, "model": args.executor, "reason": args.reason,
                     "risk": {"importance": "high", "difficulty": "medium", "uncertainty": "medium",
                              "impact": args.impact}},
        "actions": [{"summary": args.target, "executor": args.executor}],
        "evidence_after": evidence,
        "validation": {"checks": checks, "result": overall, "evaluation_required": False,
                       "negative_control": negative},
        "review": {"proven": args.proven, "not_proven": args.not_proven, "new_risks": args.risk},
        "decision": args.decision, "next_target": args.next,
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
    ap.add_argument("--acceptance", default="", help="overall acceptance item this round serves, e.g. A1")
    ap.add_argument("--stop-reason", default="", choices=["", "needs_human", "no_path", "infeasible"])
    ap.add_argument("--stop-unblock", default="", help="what must change before work can continue")
    ap.add_argument("--stop-attempt", action="append", default=[], help="path=>failure evidence")
    ap.add_argument("--stop-shrunk", default="", help="smallest version tried and its result")
    ap.add_argument("--stop-searched", action="append", default=[], help="existing source checked")
    ap.add_argument("--stop-reviewer", default="", help="adversarial review result and where it is")
    ap.add_argument("--wait-on", default="", help="decision wait: who or what is awaited")
    ap.add_argument("--wait-tried", action="append", default=[], help="decision wait: alternative=>result")
    args = ap.parse_args()
    problem = gate(args)
    if problem:
        print("rejected; nothing written:\n" + problem, file=sys.stderr)
        return 1
    # One writer at a time per file; the previous record is read under the lock so iteration
    # numbers and transitions cannot race. The candidate file is validated before it replaces
    # the real one, so the JSONL never holds an invalid record (Codex review 2026-10-15).
    args.file.parent.mkdir(parents=True, exist_ok=True)
    lock_path = args.file.with_name(args.file.name + ".lock")
    with open(lock_path, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prev = last_record(args.file, args.task)
        problem = heartbeat(prev, args)
        if problem:
            print("rejected; nothing written:\n" + problem, file=sys.stderr)
            return 1
        record = build(args, prev, last_step_state(args.file, args.task, args.step))
        original = args.file.read_text(encoding="utf-8") if args.file.exists() else ""
        candidate = args.file.with_name(args.file.name + ".tmp")
        candidate.write_text(original + json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
        check = subprocess.run([sys.executable, str(SKILL), str(candidate)], capture_output=True, text=True)
        if check.returncode != 0:
            candidate.unlink(missing_ok=True)
            print("rejected; nothing written:\n" + check.stdout + check.stderr, file=sys.stderr)
            return 1
        from cash_rule_delivery import gate as delivery_gate
        problem = delivery_gate(args.file, args.task, args.step, args.task_state,
                                args.step_state, args.check)
        if problem:
            candidate.unlink(missing_ok=True)
            print("rejected; nothing written:\n" + problem, file=sys.stderr)
            return 1
        os.replace(candidate, args.file)
    print(f"appended iteration {record['iteration']} ({record['task_state']}/{record['step_state']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
