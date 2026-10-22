#!/usr/bin/env python3
"""Stop-hook finish check for Claude Code and Codex.

Blocks the end of a turn when a mechanical rule is broken in the current repo:
  1. a RUNNING LOOP file is more than 24h older than the newest code commit;
  2. a `*.checkpoints.jsonl` touched in the last 6h fails the cash-rule schema;
  3. the shared tool catalog ~/tools/tools.json is malformed;
  4. an ai-mall board card Status disagrees with the PRs touched this turn
     (card_status_check.py).
The whole repo is scanned (not only docs/); .git, node_modules, target and hidden
directories are skipped. A repo keeps being blocked until the problems are fixed,
up to MAX_BLOCKS consecutive stops; after that the hook only reports and logs
`gave_up`, so the model cannot loop forever.
A broken checker never blocks, but it is reported as "檢查器故障" instead of
passing silently. Results are logged.
"""
import json, os, re, subprocess, sys, time

LOG = os.path.expanduser("~/.local/state/agent-guards/finish_check.jsonl")
RULE = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "skills", "cash-rule")
VALIDATOR_PY = os.environ.get("CASH_RULE_VALIDATOR_PY") or os.path.expanduser("~/.cache/cash-rule-validator/bin/python")
CHECKPOINT_BUDGET_S = 60
STALE_S = 24 * 3600
RECENT_S = 6 * 3600
MAX_BLOCKS = 3
SKIP_DIRS = {"node_modules", "target", "venv", "dist", "build", "__pycache__"}
RUNNING = re.compile(r"watchdog-status:\s*RUNNING|狀態[：:]\s*\**RUNNING|目前 step[：:]\s*\**RUNNING")


def git(cwd, *args):
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=10)
    return r.stdout.strip() if r.returncode == 0 else ""


def find_files(root, keep):
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith(".")]
        out += [os.path.join(d, f) for f in files if keep(f)]
    return out


def stale_loops(root):
    newest_code = git(root, "log", "-1", "--format=%ct", "--", ".", ":(exclude)docs", ":(exclude)*.md")
    if not newest_code:
        return []
    newest_code = int(newest_code)
    if time.time() - newest_code > STALE_S:
        return []  # no recent code work in this repo
    out = []
    for f in find_files(root, lambda n: n.endswith(".loop.md")):
        head = open(f, encoding="utf-8", errors="replace").read(3000)
        if not RUNNING.search(head):
            continue
        if newest_code - os.path.getmtime(f) > STALE_S:
            out.append(os.path.relpath(f, root))
    return out


def bad_checkpoints(root, faults):
    out = []
    files = [f for f in find_files(root, lambda n: n.endswith(".checkpoints.jsonl"))
             if time.time() - os.path.getmtime(f) <= RECENT_S]
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


def prior_blocks(root):
    """How many consecutive recent stops in this repo were blocked (a passing stop resets the count)."""
    try:
        with open(LOG, encoding="utf-8") as fh:
            lines = fh.readlines()[-200:]
    except OSError:
        return 0
    n = 0
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("cwd") != root:
            continue
        if not row.get("blocked"):
            break
        n += 1
    return n


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    problems, faults = [], []
    delivery_blockers = []
    root = ""
    try:
        root = git(payload.get("cwd") or os.getcwd(), "rev-parse", "--show-toplevel")
        if root:
            problems += [f"LOOP 超過一天沒更新，但有新的程式 commit：{p}" for p in stale_loops(root)]
            problems += [f"進度紀錄格式不合格：{p}" for p in bad_checkpoints(root, faults)]
        # Independent delivery rule; keep existing lifecycle/schema checks.
        from delivery_check import problems as delivery_problems
        problems += delivery_problems(payload)
        from card_status_check import problems as card_problems
        problems += card_problems(payload, faults)
        c = catalog_problem(faults)
        if c:
            problems.append(c)
    except Exception as exc:
        faults.append(f"{type(exc).__name__}: {exc}"[:200])
    try:
        from delivery_state_check import problems as delivery_state_problems
        delivery_blockers = delivery_state_problems(payload)
    except Exception as exc:
        delivery_blockers = ["交付狀態檢查故障，不能視為整體交付：" + type(exc).__name__]
    problems += delivery_blockers
    earlier = prior_blocks(root) if problems else 0
    blocked = bool(delivery_blockers) or (bool(problems) and earlier < MAX_BLOCKS)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "cwd": root, "problems": problems,
                             "faults": faults, "second_stop": bool(payload.get("stop_hook_active")),
                             "blocked": blocked, "gave_up": bool(problems) and not blocked},
                            ensure_ascii=False) + "\n")
    msgs = []
    if problems:
        msgs.append("收工檢查未通過（規則：LOOP／進度紀錄／工具清單／看板卡片要跟實際一致）：\n- " + "\n- ".join(problems))
    if faults:
        msgs.append("收工檢查器故障，以下項目未驗收：\n- " + "\n- ".join(faults))
    if blocked:
        print(json.dumps({"decision": "block", "reason": "\n".join(msgs)
                          + ("\n未交付的整體結案持續拒絕；請保留進行中狀態並繼續其他工作。" if delivery_blockers else f"\n請修正後再結束（第 {earlier + 1} 次，最多擋 {MAX_BLOCKS} 次）。")}, ensure_ascii=False))
    elif msgs:
        if problems:
            msgs.append(f"已連續擋 {MAX_BLOCKS} 次仍未修正，本次放行並記錄 gave_up；請向使用者說明為何不修。")
        print(json.dumps({"systemMessage": "\n".join(msgs)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
