#!/usr/bin/env python3
"""PreToolUse guard for Claude Code and Codex shell calls.

Blocks: force push (any form) and `git commit` directly on develop/master/main
(a merge being concluded on develop is allowed). Fails open on bad input so a
guard bug never locks the agent out; every decision is logged.
"""
import json, os, re, shlex, subprocess, sys, time

LOG = os.path.expanduser("~/.local/state/agent-guards/git_guard.jsonl")
PROTECTED = {"develop", "master", "main"}


def command_text(payload):
    ti = payload.get("tool_input") or {}
    cmd = ti.get("command", ti.get("cmd", ""))
    if isinstance(cmd, list):
        # Codex passes argv such as ["bash", "-lc", "<script>"]; inspect the script.
        if len(cmd) >= 3 and cmd[-2] in ("-c", "-lc"):
            return str(cmd[-1])
        return " ".join(map(str, cmd))
    return str(cmd or "")


def git_segments(text):
    for part in re.split(r"&&|\|\||;|\n|\|", text):
        try:
            words = shlex.split(part)
        except ValueError:
            words = part.split()
        while words and ("=" in words[0] and not words[0].startswith("-")):
            words = words[1:]  # env assignments
        if not words:
            continue
        head = os.path.basename(words[0])
        if head in ("bash", "sh", "zsh") and len(words) >= 3 and words[-2] in ("-c", "-lc"):
            yield from git_segments(words[-1])  # nested shell script
        elif head == "git":
            yield words[1:]


def strip_git_opts(args):
    i = 0
    cwd = None
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            cwd = args[i + 1]; i += 2; continue
        if args[i] == "-c" and i + 1 < len(args):
            i += 2; continue
        i += 1
    return args[i:], cwd


def current_branch(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd, "branch", "--show-current"], capture_output=True, text=True, timeout=5)
        top = subprocess.run(["git", "-C", cwd, "rev-parse", "--git-dir"], capture_output=True, text=True, timeout=5)
        merging = os.path.exists(os.path.join(cwd, top.stdout.strip(), "MERGE_HEAD")) if top.returncode == 0 else False
        return out.stdout.strip(), merging
    except Exception:
        return "", False


def verdict(payload):
    text = command_text(payload)
    base = payload.get("cwd") or os.getcwd()
    for seg in git_segments(text):
        args, c = strip_git_opts(seg)
        if not args:
            continue
        cwd = os.path.join(base, c) if c else base
        sub, rest = args[0], args[1:]
        if sub == "push":
            if any(a in ("-f", "--force", "--force-with-lease") or a.startswith("--force-with-lease=") or a.startswith("--force-if-includes") for a in rest) \
               or any(a.startswith("+") for a in rest if not a.startswith("-")):
                return "禁止強制推送（規則：Never force push）。改用一般 push；若遠端已分岔，先 fetch 再 merge。"
        if sub == "commit":
            branch, merging = current_branch(cwd)
            if branch in PROTECTED and not merging:
                return f"禁止直接在 {branch} 上 commit（規則：Never commit directly to master or develop）。先開 feat/、fix/ 或 docs/ 分支。"
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    reason = verdict(payload)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "blocked": bool(reason),
                             "reason": reason, "cmd": command_text(payload)[:200]}, ensure_ascii=False) + "\n")
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
              "permissionDecision": "deny", "permissionDecisionReason": reason}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
