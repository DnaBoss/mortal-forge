#!/usr/bin/env python3
"""PreToolUse guard for Claude Code and Codex: recurring writing mistakes.

1. checkpoint history (`*.checkpoints.jsonl`) is append-only and must be written by
   ~/tools/cash-rule-checkpoint, which validates before writing. Direct writes
   (Write/Edit tools, shell redirection, tee, sed -i, truncate, rm, mv, inline
   open(..., "a"/"w")) are denied.
2. `pkill -f` / `pgrep -f` match the caller's own shell command line; it killed the
   running shell four times. Denied.
3. `git checkout -- <path>` / `git restore <path>` on a file with uncommitted changes
   threw away wanted edits. Denied unless the command text contains `DISCARD=1`.
4. Registered simplified glyphs in checkpoint prose are denied before writing;
   technical file paths and evidence locators remain unchanged.

Early warning, not a security boundary (same as git_guard): what it cannot parse
passes. Fails open on bad input. Decisions are logged without command text.
"""
import hashlib, json, os, re, shlex, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from git_guard import command_text, git_segments, strip_git_opts, unwrap  # noqa: E402

LOG = os.path.expanduser("~/.local/state/agent-guards/write_guard.jsonl")
CHECKPOINT = re.compile(r"[^\s'\"]*\.checkpoints\.jsonl\b")
REDIRECT = re.compile(r">{1,2}\s*['\"]?[^\s'\"]*\.checkpoints\.jsonl\b")
INLINE_OPEN = re.compile(r"open\([^)]*\.checkpoints\.jsonl[^)]*['\"][wa]")
APPEND_TOOL = ("cash_rule_checkpoint", "cash-rule-checkpoint")
WRITE_HEADS = {"tee", "truncate", "rm", "mv", "dd"}
EDIT_KEYS = ("content", "new_string", "old_string", "patch", "new_str", "edits", "cells", "new_source")
PATH_KEYS = ("file_path", "path", "notebook_path")
PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.M)

CHECKPOINT_MSG = ("禁止直接寫 *.checkpoints.jsonl（規則：進度紀錄只追加、寫前驗證）。"
                  "改用 ~/tools/cash-rule-checkpoint FILE --task T --step S ...，它會自動接續狀態、蓋時間並驗證。")
PKILL_MSG = ("禁止 pkill -f／pgrep -f（會比對到自己的 shell，2026-10-02 已犯 4 次）。"
             "改用 ss -ltnp 取監聽 PID 後 kill <PID>，或 pgrep -x <程序名> 再比對 /proc/<PID>/cwd。")
DISCARD_MSG = ("禁止用 git checkout --／git restore 丟掉有未提交修改的檔案（2026-10-02 改好的檔被退回舊版）。"
               "要保留就先 cp 到暫存目錄；確定要丟棄，在命令最前面加 DISCARD=1。")
PROSE_MSG = "進度紀錄的說明含已登記的簡體字。請改用繁體中文，再經原寫入工具追加；不要改寫歷史。"
PROSE_OPTIONS = {"--target", "--proven", "--not-proven", "--risk", "--next",
                 "--reason", "--impact", "--source", "--check"}
SIMPLIFIED_PROSE = re.compile("[\u65f6\u9a8c\u7801\u753b\u7eed\u72ec\u65e0\u636e\u73b0\u6d4b\u8bc1\u4e0e\u4e3a\u9519\u8bef\u62a4\u5355\u6761\u53d1\u8fc7]")


def checkpoint_prose(text):
    """Reject registered glyphs only in the writer's human-facing options."""
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return False
    groups, current = [], []
    for token in tokens:
        if token and all(char in ";&|\n" for char in token):
            groups.append(current)
            current = []
        else:
            current.append(token)
    groups.append(current)
    for group in groups:
        words = unwrap(group)
        if not words:
            continue
        head = os.path.basename(words[0])
        if head in ("python", "python3") and len(words) > 1:
            words = words[1:]
            head = os.path.basename(words[0])
        if head not in ("cash-rule-checkpoint", "cash_rule_checkpoint.py"):
            continue
        for index, word in enumerate(words[1:], 1):
            option, separator, inline = word.partition("=")
            if option not in PROSE_OPTIONS:
                continue
            value = inline if separator else words[index + 1] if index + 1 < len(words) else ""
            if SIMPLIFIED_PROSE.search(value):
                return True
    return False


def segments(text):
    for part in re.split(r"&&|\|\||;|\n|\|", text):
        try:
            import shlex
            words = shlex.split(part)
        except ValueError:
            words = part.split()
        yield part, unwrap(words)


def checkpoint_shell_write(text):
    if any(tool in text for tool in APPEND_TOOL):
        return False
    if INLINE_OPEN.search(text):
        return True
    for part, words in segments(text):
        if REDIRECT.search(part):
            return True
        if not words:
            continue
        head = os.path.basename(words[0])
        if head in WRITE_HEADS and any(CHECKPOINT.fullmatch(w) for w in words[1:]):
            return True
        if head == "sed" and any(w.startswith("-i") for w in words[1:]) and any(CHECKPOINT.fullmatch(w) for w in words[1:]):
            return True
    return False


def pkill_full(text):
    for _, words in segments(text):
        if not words:
            continue
        if os.path.basename(words[0]) in ("pkill", "pgrep"):
            for w in words[1:]:
                if w == "--full" or (re.fullmatch(r"-[a-zA-Z]+", w) and "f" in w):
                    return True
    return False


def dirty(cwd, path):
    try:
        r = subprocess.run(["git", "-C", cwd, "status", "--porcelain", "--untracked-files=no", "--", path],
                           capture_output=True, text=True, timeout=5)
        return r.returncode == 0 and bool(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def discard_paths(sub, rest):
    """Working-tree paths a checkout/restore would overwrite; empty when it is a branch switch."""
    if sub == "checkout":
        if "--" in rest:
            return rest[rest.index("--") + 1:]
        if any(a.startswith("-") for a in rest):
            return []  # -b, -B, --detach, --orphan ... are not file restores
        return rest[1:] if len(rest) > 1 else rest
    if sub == "restore":
        if "--staged" in rest or "-S" in rest:
            if not ("--worktree" in rest or "-W" in rest):
                return []  # index only: working tree untouched
        paths, skip = [], False
        for a in rest:
            if skip:
                skip = False
                continue
            if a in ("-s", "--source"):
                skip = True
            elif not a.startswith("-"):
                paths.append(a)
        return paths
    return []


def discard_without_flag(text, base):
    if "DISCARD=1" in text:
        return False
    for seg, seg_cwd in git_segments(text, base):
        args, c = strip_git_opts(seg)
        if not args:
            continue
        cwd = os.path.join(seg_cwd, c) if c else seg_cwd
        sub, rest = args[0], args[1:]
        if sub not in ("checkout", "restore"):
            continue
        for path in discard_paths(sub, rest):
            if sub == "checkout" and "--" not in rest and not os.path.exists(os.path.join(cwd, path)):
                continue  # a branch or tag name, not a file
            if dirty(cwd, path):
                return True
    return False


def edit_targets(tool_input):
    out = [str(tool_input[k]) for k in PATH_KEYS if isinstance(tool_input.get(k), str)]
    patch = tool_input.get("patch")
    if isinstance(patch, str):
        out += PATCH_FILE.findall(patch)
    for edit in tool_input.get("edits") or []:
        if isinstance(edit, dict) and isinstance(edit.get("file_path"), str):
            out.append(edit["file_path"])
    return out


def verdict(payload):
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None, None
    is_shell = "command" in tool_input or "cmd" in tool_input
    if is_shell:
        text = command_text(payload)
        if checkpoint_shell_write(text):
            return "checkpoint-write", CHECKPOINT_MSG
        if checkpoint_prose(text):
            return "checkpoint-prose", PROSE_MSG
        if pkill_full(text):
            return "pkill-full", PKILL_MSG
        if discard_without_flag(text, payload.get("cwd") or os.getcwd()):
            return "discard-uncommitted", DISCARD_MSG
        return None, None
    if any(k in tool_input for k in EDIT_KEYS) and any(CHECKPOINT.search(p) for p in edit_targets(tool_input)):
        return "checkpoint-write", CHECKPOINT_MSG
    return None, None


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
    try:
        rule, reason = verdict(payload)
    except Exception as exc:  # never lock the agent out because of a guard bug
        log({"at": at, "verdict": "error", "error": type(exc).__name__})
        return 0
    digest = hashlib.sha256(json.dumps(payload.get("tool_input"), sort_keys=True, default=str).encode()).hexdigest()
    log({"at": at, "verdict": "deny" if reason else "allow", "rule": rule, "tool": payload.get("tool_name"),
         "input_sha256": digest})
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
              "permissionDecision": "deny", "permissionDecisionReason": reason}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
