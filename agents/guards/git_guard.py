#!/usr/bin/env python3
"""PreToolUse guard for Claude Code and Codex shell calls.

Blocks: force push (any form) and `git commit` directly on develop/master/main
(a merge being concluded on develop is allowed).

This is an early warning, not a security boundary: anything it cannot parse
(e.g. `$(echo git) push -f`, aliases, scripts on disk) passes. Real protection
for force push and protected branches belongs to the Git server rules.
Fails open on bad input so a guard bug never locks the agent out; every
decision is logged without the command text (only its sha256).
"""
import hashlib, json, os, re, shlex, subprocess, sys, time

LOG = os.path.expanduser("~/.local/state/agent-guards/git_guard.jsonl")
PROTECTED = {"develop", "master", "main"}
SHELLS = ("bash", "sh", "zsh", "dash")
# Wrapper commands that run their arguments as a new command, with the
# options that take a separate value.
WRAPPERS = {
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "command": set(),
    "exec": {"-a"},
    "sudo": {"-u", "--user", "-g", "--group", "-C", "-D", "--chdir", "-h", "--host", "-p", "--prompt"},
    "nice": {"-n", "--adjustment"},
    "nohup": set(),
    "time": {"-f", "--format", "-o", "--output"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "xargs": {"-a", "-d", "-E", "-I", "-L", "-n", "-P", "-s"},
}
SCRIPT_RUNNERS = ("python", "python3", "node", "perl", "ruby")
SCRIPT_FORCE_PUSH = re.compile(r"\bgit\b.{0,40}?\bpush\b.{0,80}?(--force|[\"'\s]-[a-zA-Z]*f[a-zA-Z]*\b|\s\+\S)")
FORCE_MSG = "禁止強制推送（規則：Never force push）。改用一般 push；若遠端已分岔，先 fetch 再 merge。"


def command_text(payload):
    ti = payload.get("tool_input") or {}
    cmd = ti.get("command", ti.get("cmd", ""))
    if isinstance(cmd, list):
        # Codex passes argv such as ["bash", "-lc", "<script>"]; inspect the script.
        if len(cmd) >= 3 and cmd[-2] in ("-c", "-lc"):
            return str(cmd[-1])
        return " ".join(map(str, cmd))
    return str(cmd or "")


def unwrap(words):
    """Drop env assignments and wrapper commands (env, sudo, timeout ...)."""
    while words:
        if "=" in words[0] and not words[0].startswith("-"):
            words = words[1:]
            continue
        head = os.path.basename(words[0])
        if head not in WRAPPERS:
            return words
        takes_value = WRAPPERS[head]
        words = words[1:]
        while words and words[0].startswith("-"):
            opt = words[0]
            words = words[2:] if opt in takes_value else words[1:]
            if opt == "--":
                break
        if head == "timeout" and words:
            words = words[1:]  # duration
    return words


def git_segments(text, cwd):
    """Yield (git_args, cwd) for each git call, following `cd` in the same script."""
    for part in re.split(r"&&|\|\||;|\n|\|", text):
        try:
            words = shlex.split(part)
        except ValueError:
            words = part.split()
        words = unwrap(words)
        if not words:
            continue
        head = os.path.basename(words[0])
        if head == "cd":
            target = os.path.expanduser(words[1]) if len(words) > 1 else os.path.expanduser("~")
            cwd = os.path.normpath(os.path.join(cwd, target))
        elif head in SHELLS and len(words) >= 3 and words[-2] in ("-c", "-lc"):
            yield from git_segments(words[-1], cwd)  # nested shell script
        elif head == "git":
            yield words[1:], cwd


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


def is_force_push(rest):
    for a in rest:
        if a in ("--force", "--force-with-lease") or a.startswith(("--force-with-lease=", "--force-if-includes")):
            return True
        if re.fullmatch(r"-[a-zA-Z]+", a) and "f" in a:
            return True  # -f, -uf, -fu ...
        if a.startswith("+") and len(a) > 1:
            return True
    return False


def current_branch(cwd):
    """Return (branch, merging, problem). problem is set only when git itself failed."""
    try:
        top = subprocess.run(["git", "-C", cwd, "rev-parse", "--git-dir"], capture_output=True, text=True, timeout=5)
        if top.returncode != 0:
            return "", False, None  # not a repository: nothing to protect
        out = subprocess.run(["git", "-C", cwd, "branch", "--show-current"], capture_output=True, text=True, timeout=5)
        merging = os.path.exists(os.path.join(cwd, top.stdout.strip(), "MERGE_HEAD"))
        return out.stdout.strip(), merging, None
    except (OSError, subprocess.SubprocessError) as exc:
        return "", False, f"git_guard 無法確認 {cwd} 的分支（{type(exc).__name__}），本次 commit 未受保護分支檢查。"


def verdict(payload):
    """Return (rule_id, deny_reason, warning)."""
    text = command_text(payload)
    base = payload.get("cwd") or os.getcwd()
    warning = None
    for seg, seg_cwd in git_segments(text, base):
        args, c = strip_git_opts(seg)
        if not args:
            continue
        cwd = os.path.join(seg_cwd, c) if c else seg_cwd
        sub, rest = args[0], args[1:]
        if sub == "push" and is_force_push(rest):
            return "force-push", FORCE_MSG, None
        if sub == "commit":
            branch, merging, problem = current_branch(cwd)
            warning = warning or problem
            if branch in PROTECTED and not merging:
                return "protected-commit", (f"禁止直接在 {branch} 上 commit（規則：Never commit directly to master or develop）。"
                                            "先開 feat/、fix/ 或 docs/ 分支。"), None
    if any(r in text for r in SCRIPT_RUNNERS) and SCRIPT_FORCE_PUSH.search(text):
        return "force-push-script", FORCE_MSG, None
    return None, None, warning


def log(entry):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def main():
    at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    try:
        payload = json.load(sys.stdin)
    except Exception as exc:
        log({"at": at, "verdict": "error", "error": type(exc).__name__})
        return 0
    rule, reason, warning = verdict(payload)
    log({"at": at, "verdict": "deny" if reason else ("warn" if warning else "allow"), "rule": rule,
         "cmd_sha256": hashlib.sha256(command_text(payload).encode()).hexdigest()})
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
              "permissionDecision": "deny", "permissionDecisionReason": reason}}, ensure_ascii=False))
    elif warning:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
              "additionalContext": warning}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
