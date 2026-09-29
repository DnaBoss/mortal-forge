#!/usr/bin/env python3
"""Stop-hook finish check for Claude Code and Codex.

Blocks the end of a turn once (stop_hook_active guard) when a mechanical rule is
broken in the current repo:
  1. a RUNNING LOOP file is more than 24h older than the newest code commit;
  2. a checkpoint JSONL touched in the last 6h fails the cash-rule schema;
  3. the shared tool catalog ~/tools/tools.json is malformed.
Fails open (exit 0, no block) on any internal error; results are logged.
"""
import glob, json, os, re, subprocess, sys, time

LOG = os.path.expanduser("~/.local/state/agent-guards/finish_check.jsonl")
RULE = os.path.expanduser("~/.agents/skills/cash-rule")
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


def bad_checkpoints(root):
    out = []
    validator = os.path.join(RULE, "scripts/validate_checkpoints.py")
    for f in glob.glob(os.path.join(root, "docs/**/*.jsonl"), recursive=True):
        if "checkpoint" not in os.path.basename(f) or time.time() - os.path.getmtime(f) > RECENT_S:
            continue
        r = subprocess.run(["uvx", "-q", "--with-requirements", os.path.join(RULE, "scripts/requirements.txt"),
                            "python", validator, f], capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            out.append(f"{os.path.relpath(f, root)}: {(r.stdout + r.stderr).strip().splitlines()[0][:120]}")
    return out


def catalog_problem():
    sys.path.insert(0, os.path.expanduser("~/tools"))
    try:
        import list_tools
        list_tools.load_catalog(os.path.expanduser("~/tools/tools.json"))
        return None
    except Exception as exc:
        return f"~/tools/tools.json 格式錯誤：{exc}"


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    if payload.get("stop_hook_active"):
        return 0
    problems = []
    try:
        root = git(payload.get("cwd") or os.getcwd(), "rev-parse", "--show-toplevel")
        if root:
            problems += [f"LOOP 超過一天沒更新，但有新的程式 commit：{p}" for p in stale_loops(root)]
            problems += [f"進度紀錄格式不合格：{p}" for p in bad_checkpoints(root)]
        c = catalog_problem()
        if c:
            problems.append(c)
    except Exception as exc:
        problems = []
        err = repr(exc)
    else:
        err = None
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "problems": problems, "error": err},
                            ensure_ascii=False) + "\n")
    if problems:
        print(json.dumps({"decision": "block", "reason":
            "收工檢查未通過（規則：LOOP／進度紀錄／工具清單要跟實際一致）。請修正或向使用者說明為何不修：\n- "
            + "\n- ".join(problems)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
