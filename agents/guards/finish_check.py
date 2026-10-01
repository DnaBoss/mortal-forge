#!/usr/bin/env python3
"""Stop-hook finish check for Claude Code and Codex.

Blocks the end of a turn once when a mechanical rule is broken in the current repo
(on the second Stop it only reports, so the model cannot loop forever):
  1. a RUNNING LOOP file is more than 24h older than the newest code commit;
  2. a checkpoint JSONL touched in the last 6h fails the cash-rule schema;
  3. the shared tool catalog ~/tools/tools.json is malformed.
A broken checker never blocks, but it is reported as "檢查器故障" instead of
passing silently. Results are logged.
"""
import glob, json, os, re, subprocess, sys, time

LOG = os.path.expanduser("~/.local/state/agent-guards/finish_check.jsonl")
RULE = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "skills", "cash-rule")
VALIDATOR_PY = os.environ.get("CASH_RULE_VALIDATOR_PY") or os.path.expanduser("~/.cache/cash-rule-validator/bin/python")
CHECKPOINT_BUDGET_S = 60
STALE_S = 24 * 3600
RECENT_S = 6 * 3600


def git(cwd, *args):
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=10)
    return r.stdout.strip() if r.returncode == 0 else ""


def stale_loops(root):
    newest_code = git(root, "log", "-1", "--format=%ct", "--", ".", ":(exclude)docs", ":(exclude)*.md")
    if not newest_code:
        return []
    newest_code = int(newest_code)
    if time.time() - newest_code > STALE_S:
        return []  # no recent code work in this repo
    out = []
    for f in glob.glob(os.path.join(root, "docs/**/*.loop.md"), recursive=True):
        head = open(f, encoding="utf-8", errors="replace").read(3000)
        if not re.search(r"watchdog-status:\s*RUNNING|狀態[：:]\s*\**RUNNING", head):
            continue
        if newest_code - os.path.getmtime(f) > STALE_S:
            out.append(os.path.relpath(f, root))
    return out


def bad_checkpoints(root, faults):
    out = []
    files = [f for f in glob.glob(os.path.join(root, "docs/**/*.jsonl"), recursive=True)
             if "checkpoint" in os.path.basename(f) and time.time() - os.path.getmtime(f) <= RECENT_S]
    if not files:
        return out
    if not os.access(VALIDATOR_PY, os.X_OK):
        faults.append(f"找不到驗證環境 {VALIDATOR_PY}（重建：見 cash-rule references/reporting.md）")
        return out
    validator = os.path.join(RULE, "scripts/validate_checkpoints.py")
    deadline = time.time() + CHECKPOINT_BUDGET_S
    for f in files:
        left = deadline - time.time()
        if left <= 1:
            faults.append(f"進度紀錄驗證超過 {CHECKPOINT_BUDGET_S} 秒，未驗完")
            break
        r = subprocess.run([VALIDATOR_PY, validator, f], capture_output=True, text=True, timeout=left)
        if r.returncode != 0:
            first = ((r.stdout + r.stderr).strip().splitlines() or ["(no output)"])[0]
            out.append(f"{os.path.relpath(f, root)}: {first[:120]}")
    return out


def catalog_problem(faults):
    sys.path.insert(0, os.path.expanduser("~/tools"))
    try:
        import list_tools
    except Exception as exc:
        faults.append(f"無法載入 ~/tools/list_tools.py：{type(exc).__name__}")
        return None
    try:
        list_tools.load_catalog(os.path.expanduser("~/tools/tools.json"))
        return None
    except Exception as exc:
        return f"~/tools/tools.json 格式錯誤：{exc}"


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    problems, faults = [], []
    try:
        root = git(payload.get("cwd") or os.getcwd(), "rev-parse", "--show-toplevel")
        if root:
            problems += [f"LOOP 超過一天沒更新，但有新的程式 commit：{p}" for p in stale_loops(root)]
            problems += [f"進度紀錄格式不合格：{p}" for p in bad_checkpoints(root, faults)]
        c = catalog_problem(faults)
        if c:
            problems.append(c)
    except Exception as exc:
        faults.append(f"{type(exc).__name__}: {exc}"[:200])
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "problems": problems, "faults": faults,
                             "second_stop": bool(payload.get("stop_hook_active"))}, ensure_ascii=False) + "\n")
    msgs = []
    if problems:
        msgs.append("收工檢查未通過（規則：LOOP／進度紀錄／工具清單要跟實際一致）：\n- " + "\n- ".join(problems))
    if faults:
        msgs.append("收工檢查器故障，以下項目未驗收：\n- " + "\n- ".join(faults))
    if problems and not payload.get("stop_hook_active"):
        print(json.dumps({"decision": "block", "reason": "\n".join(msgs) + "\n請修正或向使用者說明為何不修。"},
                         ensure_ascii=False))
    elif msgs:
        print(json.dumps({"systemMessage": "\n".join(msgs)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
