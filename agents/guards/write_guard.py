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
5. Cargo must not run unconditionally after a Python preflight heredoc.
6. A literal schema_id default is denied when the nearby Kratos schema list excludes it.

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
PREFLIGHT_MSG = "Python前置檢查後的編譯沒有綁定成功條件。請先確認檢查成功再另行編譯，或用&&串接；失敗不能繼續編譯。"
PROSE_OPTIONS = {"--target", "--proven", "--not-proven", "--risk", "--next",
                 "--reason", "--impact", "--source", "--check"}
SIMPLIFIED_PROSE = re.compile("[\u65f6\u9a8c\u7801\u753b\u7eed\u72ec\u65e0\u636e\u73b0\u6d4b\u8bc1\u4e0e\u4e3a\u9519\u8bef\u62a4\u5355\u6761\u53d1\u8fc7]")


def wrong_kratos_default(text, base):
    """Only the observed default literal against a known simple schema list."""
    if not re.search(r"(['\"])schema_id\1\s*:\s*(['\"])default\2", text):
        return False
    current = os.path.abspath(base)
    while True:
        config = os.path.join(current, "deploy", "systemd", "kratos.yml")
        if os.path.isfile(config):
            try:
                with open(config, encoding="utf-8") as source:
                    content = source.read(65537)
            except OSError:
                return False
            if len(content) > 65536:
                return False
            ids = re.findall(r"(?m)^\s*-\s*id:\s*['\"]?([A-Za-z_][A-Za-z0-9_-]*)['\"]?\s*$", content)
            return bool(ids) and "default" not in ids
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def unchecked_cargo_preflight(text, next_pattern=r"cargo\s+(?:build|test|clippy|run)\b"):
    """Recognize the observed Python-heredoc fallthrough, not all shell gates."""
    opening = re.compile(r"(?m)^[ \t]*(?:[^\s]+/)?python(?:3(?:\.[0-9]+)?)?\s+-\s+<<(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[ \t]*$")
    for match in opening.finditer(text):
        remainder = text[match.end():]
        closing = re.search(r"(?m)^" + re.escape(match[2]) + r"[ \t]*$", remainder)
        if closing and re.match(next_pattern, remainder[closing.end():].lstrip()):
            return True
    return False


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


def unknown_literal_git_revision(text, base):
    """Catch a pinned full SHA queried in the wrong repository, not branch discovery."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    deadline = time.monotonic() + 4
    examined = 0
    for seg, seg_cwd in git_segments(text, base):
        args, c = strip_git_opts(seg)
        if not args or args[0] not in ("show", "ls-tree"):
            continue
        cwd = os.path.join(seg_cwd, c) if c else seg_cwd
        for value in args[1:]:
            rev = value.split(":", 1)[0]
            if not re.fullmatch(r"[0-9a-fA-F]{40}", rev):
                continue
            examined += 1
            remaining = deadline - time.monotonic()
            if examined > 16 or remaining <= 0:
                return False
            try:
                result = subprocess.run(["git", "rev-parse", "--verify", rev + "^{tree}"],
                                        cwd=cwd, env=env, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, timeout=min(2, remaining))
                if result.returncode != 0:
                    return True
            except (OSError, subprocess.SubprocessError):
                return False
    return False


def missing_git_source_path(text, base):
    """Warn only for missing literal paths in a known Git tree; bounded, fail open."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    deadline = time.monotonic() + 4
    examined = 0
    for seg, seg_cwd in git_segments(text, base):
        args, c = strip_git_opts(seg)
        if not args or args[0] != "show":
            continue
        cwd = os.path.join(seg_cwd, c) if c else seg_cwd
        for value in args[1:]:
            if value.startswith("-") or ":" not in value or "$" in value or "`" in value:
                continue
            rev, path = value.split(":", 1)
            if not rev or not path:
                continue
            examined += 1
            if examined > 16:
                return False
            def run(options):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired("git", 4)
                return subprocess.run(["git", *options], cwd=cwd, env=env,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      timeout=min(2, remaining)).returncode
            try:
                if run(["rev-parse", "--verify", rev + "^{tree}"]) != 0:
                    continue
                if run(["cat-file", "-e", value]) != 0:
                    return True
            except (OSError, subprocess.SubprocessError):
                return False
    return False



def missing_literal_docs_read(text, base):
    """Only straight-line Python heredocs reading a literal relative docs path."""
    import ast
    if len(text) > 65536 or not os.path.isdir(base):
        return False
    if re.search(r"(?:^|[;\n])\s*cd\s|\b(?:chdir|fchdir)\s*\(", text):
        return False
    opening = re.compile(r"(?m)^[ \t]*(?:[^\s]+/)?python(?:3(?:\.[0-9]+)?)?\s+-\s+<<(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[ \t]*$")
    examined = 0
    for match in opening.finditer(text):
        rest = text[match.end():]
        closing = re.search(r"(?m)^" + re.escape(match[2]) + r"[ \t]*$", rest)
        if not closing:
            continue
        try:
            tree = ast.parse(rest[:closing.start()])
        except (SyntaxError, ValueError):
            continue
        if any(not isinstance(stmt, (ast.Assign, ast.Expr, ast.Import, ast.ImportFrom, ast.Assert)) for stmt in tree.body):
            continue
        bindings = {}
        created = set()
        def literal(node):
            if isinstance(node, ast.Name):
                return bindings.get(node.id)
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == 'Path' and len(node.args) == 1
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                return node.args[0].value
            return None
        for stmt in tree.body:
            for node in ast.walk(stmt):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in ('read_text', 'read_bytes')):
                    continue
                path = literal(node.func.value)
                if not path or not path.startswith('docs/') or path in created:
                    continue
                examined += 1
                if examined > 16:
                    return False
                if not os.path.isfile(os.path.join(base, path)):
                    return True
            for node in ast.walk(stmt):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in ('write_text', 'write_bytes')):
                    path = literal(node.func.value)
                    if path:
                        created.add(path)
            if isinstance(stmt, ast.Assign):
                value = literal(stmt.value)
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        bindings[target.id] = value
    return False


def invalid_fixture_preflight(text, fixture_root=None):
    """Known standalone fixture setup mistakes; not a general Python checker."""
    import ast
    if len(text) > 65536:
        return False
    root = os.path.realpath(fixture_root or os.path.expanduser('~/.cache/identity-platform'))
    pattern = r"(?:^|[;\n])\s*(?:[^\s]+/)?python(?:3(?:\.[0-9]+)?)?\s+(?:-u\s+)?['\"]?([^\s'\"]*launcher[^\s'\"]*\.py)"
    for examined, match in enumerate(re.finditer(pattern, text)):
        if examined >= 4:
            break
        source = os.path.realpath(match[1])
        try:
            if os.path.commonpath([root, source]) != root:
                continue
            with open(source, encoding='utf-8') as stream:
                content = stream.read(131073)
            if len(content) > 131072:
                continue
            tree = ast.parse(content)
        except (OSError, SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'window' and node.func.attr == 'wait'):
                for kw in node.keywords:
                    if (kw.arg == 'seconds' and isinstance(kw.value, ast.Constant)
                            and isinstance(kw.value.value, (int, float))
                            and not 0 < kw.value.value <= 300):
                        return True
            if not isinstance(node, ast.FunctionDef) or node.name != 'gateway_running':
                continue
            calls = [x for x in ast.walk(node) if isinstance(x, ast.Call)
                     and isinstance(x.func, ast.Attribute) and x.func.attr == 'write_text'
                     and isinstance(x.func.value, ast.Name) and x.func.value.id == 'inner']
            assigned = any(isinstance(x, ast.Name) and x.id == 'inner'
                           and isinstance(x.ctx, ast.Store) for x in ast.walk(node))
            if calls and not assigned:
                return True
            for call in calls:
                if not call.args or not isinstance(call.args[0], ast.Constant) or not isinstance(call.args[0].value, str):
                    continue
                if len(call.args[0].value) > 65536:
                    continue
                try:
                    nested = ast.parse(call.args[0].value)
                except (SyntaxError, ValueError):
                    continue
                uses = any(isinstance(x, ast.Name) and x.id == 'Request'
                           and isinstance(x.ctx, ast.Load) for x in ast.walk(nested))
                bound = any((isinstance(x, ast.Name) and x.id == 'Request' and isinstance(x.ctx, ast.Store))
                            or (isinstance(x, ast.alias) and (x.asname or x.name) == 'Request')
                            or (isinstance(x, (ast.FunctionDef, ast.ClassDef)) and x.name == 'Request')
                            for x in ast.walk(nested))
                if uses and not bound:
                    return True
    return False


def verdict(payload):
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None, None
    is_shell = "command" in tool_input or "cmd" in tool_input
    schema_text = command_text(payload) if is_shell else " ".join(str(tool_input[k]) for k in EDIT_KEYS if k in tool_input)
    schema_base = tool_input.get("workdir") or tool_input.get("cwd") or payload.get("cwd") or os.getcwd()
    if wrong_kratos_default(schema_text, schema_base):
        return "kratos-schema-default", "專案沒有註冊default身分格式，請從Kratos設定讀取實際schema_id，再建立測試帳號。"
    if is_shell:
        text = command_text(payload)
        if unknown_literal_git_revision(text, schema_base):
            return "git-source-revision", "目前Git專案沒有這個固定版本，請先核對工作目錄與版本來源，再讀來源檔案。"
        if missing_git_source_path(text, schema_base):
            return "git-source-path", "該Git版本沒有這個路徑，請先列出版本內檔案並核對工作目錄，勿猜路徑。"
        if missing_literal_docs_read(text, schema_base):
            return "docs-read-path", "目前工作目錄找不到這個相對文件路徑；請核對專案，跨專案文件改用已確認的絕對路徑。"
        if invalid_fixture_preflight(text):
            return "fixture-setup-preflight", "這份隔離啟動器有已知漏項或等待時間超過工具上限；請先核對內層程式路徑、Request匯入及300秒限制，不要啟動服務。"
        if checkpoint_shell_write(text):
            return "checkpoint-write", CHECKPOINT_MSG
        if checkpoint_prose(text):
            return "checkpoint-prose", PROSE_MSG
        if unchecked_cargo_preflight(text):
            return "cargo-unchecked-preflight", PREFLIGHT_MSG
        if unchecked_cargo_preflight(text, r"git\s+worktree\s+add\b"):
            return "git-unchecked-preflight", "Python前置檢查後直接建立工作樹，未綁定成功條件。請確認成功後再另行建立，或用&&串接。"
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
