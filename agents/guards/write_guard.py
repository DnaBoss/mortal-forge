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
7. `git stash pop|drop|clear`: the stash list is shared by every worktree of a repository, so
   these can take or delete an entry that belongs to another session. Denied unless the
   command text contains `STASH_OK=1`.
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
STASH_MSG = ("git stash 清單是同一個 repo 所有工作樹共用的；pop／drop／clear 可能取出或刪掉別的工作階段的暫存"
             "（2026-10-10 前一段指令失敗後 pop 照跑，取出了別人的暫存）。要對照沒改之前的結果，請到乾淨的工作樹跑，"
             "或把改動的檔 cp 到暫存目錄。確定是自己剛放的那一筆：先 git stash list 核對，再在命令最前面加 STASH_OK=1。")
POST_MSG = ("同一個指令裡既寫留言內容檔（{path}）又把它貼出去，貼之前沒有機會對照查證的輸出"
            "（2026-10-10 兩次：先貼出「沒有分頁」、把截圖張數寫錯）。請分成兩個指令：先寫檔、讀過查證的輸出，再貼。"
            "內容確定已經查證過時，在命令最前面加 POST_OK=1。")
GLOB_MSG = ("zsh 會因為沒加引號的萬用字元對不到任何檔案而中止整個指令（no matches found），連同管線前面的指令都不會跑："
            "{word}。請替樣式加引號，或改用 rg --glob；確定檔案稍後才會出現時，在命令最前面加 GLOB_OK=1。")
PKILL_MSG = ("禁止 pkill -f／pgrep -f（會比對到自己的 shell，2026-10-02 已犯 4 次）。"
             "改用 ss -ltnp 取監聽 PID 後 kill <PID>，或 pgrep -x <程序名> 再比對 /proc/<PID>/cwd。")
ZSH_SPLIT_MSG = ("zsh 不會把沒加引號的變數拆成多個字：把整串指令存進變數再用 $變數 開頭執行，"
                 "會變成「no such file or directory: 整串字」，後面的工作全沒做（2026-10-03、10-14、10-15 已犯 4 次，含 for 迴圈裡的 set -- $變數）。"
                 "請改用 ${=變數}，或寫成函式，或直接寫出完整指令。")
REV_PARSE_MSG = ("git rev-parse --short／--verify 一次只收一個版本；給兩個會回「Needed a single revision」而且什麼都不印"
                 "（2026-10-10 到 10-12 已犯 3 次）。請一個版本下一次，或改用 git log -1 --format=%h <版本>。")
DISCARD_MSG = ("禁止用 git checkout --／git restore 丟掉有未提交修改的檔案（2026-10-02 改好的檔被退回舊版）。"
               "要保留就先 cp 到暫存目錄；確定要丟棄，在命令最前面加 DISCARD=1。")
PROSE_MSG = "進度紀錄的說明含已登記的簡體字。請改用繁體中文，再經原寫入工具追加；不要改寫歷史。"
PREFLIGHT_MSG = "Python前置檢查後的編譯沒有綁定成功條件。請先確認檢查成功再另行編譯，或用&&串接；失敗不能繼續編譯。"
PROSE_OPTIONS = {"--target", "--proven", "--not-proven", "--risk", "--next",
                 "--reason", "--impact", "--source", "--check", "--neg"}
SIMPLIFIED_PROSE = re.compile("[\u65f6\u9a8c\u7801\u753b\u7eed\u72ec\u65e0\u636e\u73b0\u6d4b\u8bc1\u4e0e\u4e3a\u9519\u8bef\u62a4\u5355\u6761\u53d1\u8fc7\u4e24\u8f6e\u9759\u6765\u9605\u7ed3\u95f4\u590d\u7ec8\u9879\u8fdb\u7edf\u8ba1\u8bfb\u79bb\u8054\u5f53\u5199\u5bf9\u52a1\u70b9]")
FLUKE_WORKSPACES = '/home/cash/orca/workspaces/Fluke'


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


def checkpoint_and_commit(text):
    """Keep checkpoint validation and committing in separate tool calls."""
    if len(text) > 65536 or '<<' in text:
        return False
    lexer = shlex.shlex(text, posix=True, punctuation_chars=';&|\n')
    lexer.whitespace = ' \t\r'
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return False
    groups, current = [], []
    for token in tokens:
        if token and all(char in ';&|\n' for char in token):
            groups.append(current)
            current = []
        else:
            current.append(token)
    groups.append(current)
    checkpoint = commit = False
    for group in groups:
        words = unwrap(group)
        if not words:
            continue
        head = os.path.basename(words[0])
        checkpoint |= head == 'cash-rule-checkpoint' or (head in ('python', 'python3') and len(words) > 1 and os.path.basename(words[1]) == 'cash_rule_checkpoint.py')
        commit |= head == 'git' and len(words) > 1 and words[1] == 'commit'
    return checkpoint and commit


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
            if option == "--neg":
                value = value.partition("=>")[0]
            if SIMPLIFIED_PROSE.search(value):
                return True
    return False


def checkpoint_evidence_kind(text):
    """Reject unsupported checkpoint evidence kinds before running the writer."""
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
        allowed = {"git", "file", "symbol", "test", "command", "screen", "service", "model_opinion", "other"}
        for index, word in enumerate(words[1:], 1):
            option, separator, inline = word.partition("=")
            if option != "--evidence":
                continue
            value = inline if separator else words[index + 1] if index + 1 < len(words) else ""
            kind, separator, locator = value.partition("=")
            if not separator or kind not in allowed or not locator:
                return True
    return False


def markdown_registered_prose(tool_input):
    """Only observed phrases in newly written Markdown prose, not code or old diff lines."""
    pattern = re.compile(r"\u5404\u7ec4|\u5206\u522b|\u6307\u6570\u5206\u5e03|\u4fdd\u5b58\u8be5|\u5ba3\u79f0|\u786e\u8ba4|\u53cc\u7ad9")
    patch = tool_input.get("patch") or tool_input.get("input")
    if isinstance(patch, str) and "*** Begin Patch" in patch:
        markdown, fenced = False, False
        for line in patch.splitlines():
            match = PATCH_FILE.match(line)
            if match:
                markdown, fenced = match[1].lower().endswith(".md"), False
                continue
            if not markdown or not line or line[0] not in ("+", " "):
                continue
            text = line[1:].strip()
            if text.startswith("```") or text.startswith("~~~"):
                fenced = not fenced
                continue
            if line.startswith("+") and not fenced and not text.startswith(">") and pattern.search(text):
                return True
    targets = [tool_input.get(key, "") for key in PATH_KEYS]
    if any(isinstance(path, str) and path.lower().endswith(".md") for path in targets):
        for key in ("content", "new_string", "new_str"):
            content = tool_input.get(key)
            if not isinstance(content, str):
                continue
            fenced = False
            for line in content.splitlines():
                text = line.strip()
                if text.startswith("```") or text.startswith("~~~"):
                    fenced = not fenced
                elif not fenced and not text.startswith(">") and pattern.search(text):
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


SPACED_ASSIGN = re.compile(r"(?:^|[\s;&|(])([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\s[^\"]*\"|'[^']*\s[^']*')")


SPACED_FOR = re.compile(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+[^;\n]*?(\"[^\"\n]*\s[^\"\n]*\"|'[^'\n]*\s[^'\n]*')")
SET_SPLIT = re.compile(r"\bset\s+--\s+\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?(?![A-Za-z0-9_])")


def zsh_unsplit_command(text):
    """A variable holding a spaced string is used as the command word without ${=VAR}."""
    if len(text) > 65536 or "<<" in text:
        return False  # heredoc bodies are data, same fail-open as checkpoint_and_commit
    names = {m.group(1) for m in SPACED_ASSIGN.finditer(text)}
    names |= {m.group(1) for m in SPACED_FOR.finditer(text)}
    if not names:
        return False
    heads = {f"${n}" for n in names} | {"${%s}" % n for n in names}
    for _, words in segments(text):
        if words and words[0] in heads:
            return True
    # `set -- $p` is meant to split $p into $1 $2; zsh keeps it as one word.
    return any(m.group(1) in names for m in SET_SPLIT.finditer(text))


def rev_parse_many(text):
    for _, words in segments(text):
        if len(words) < 3 or os.path.basename(words[0]) != "git":
            continue
        rest = words[1:]
        while len(rest) >= 2 and rest[0] in ("-C", "-c"):
            rest = rest[2:]
        if not rest or rest[0] != "rev-parse":
            continue
        args = rest[1:]
        if not any(a in ("--short", "--verify") or a.startswith("--short=") for a in args):
            continue
        revisions = [a for a in args if not a.startswith("-") and ">" not in a and "<" not in a]
        if len(revisions) >= 2:
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


def shared_stash_removal(text, base):
    if "STASH_OK=1" in text:
        return False
    for seg, _cwd in git_segments(text, base):
        args, _c = strip_git_opts(seg)
        if len(args) >= 2 and args[0] == "stash" and args[1] in ("pop", "drop", "clear"):
            return True
    return False


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


LOOP_LIMIT = 3000  # characters per *.loop.md (user 2026-10-15): one LOOP per task, history lives in checkpoints
LOOP_MSG = ("LOOP 檔上限 {limit} 字元，這次寫入後約 {size} 字元（使用者 2026-10-15 定）。"
            "一任務一份 LOOP，只留目標、整體驗收、計畫表、目前狀態；歷史與細節放 checkpoint JSONL，不開 step LOOP。")


def loop_over_limit(tool_input, limit=LOOP_LIMIT):
    """Projected size of a *.loop.md after this Write/Edit when it exceeds the limit, else None."""
    targets = [p for p in edit_targets(tool_input) if p.endswith(".loop.md")]
    if not targets:
        return None
    path = targets[0]
    content = tool_input.get("content")
    if isinstance(content, str):
        size = len(content)
    else:
        try:
            current = len(open(path, encoding="utf-8", errors="replace").read())
        except OSError:
            current = 0
        old = tool_input.get("old_string") or tool_input.get("old_str") or ""
        new = tool_input.get("new_string") or tool_input.get("new_str") or ""
        edits = tool_input.get("edits") or []
        delta = 0
        if edits:
            for edit in edits:
                if isinstance(edit, dict):
                    delta += len(edit.get("new_string") or "") - len(edit.get("old_string") or "")
        else:
            delta = len(new) - len(old)
        size = current + delta
    return size if size > limit else None


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


def missing_fluke_evidence_read(text, base, json_keys=False):
    """Only known straight-line Path literals and slash joins in Fluke evidence."""
    import ast
    from docker_scope_guard import python_heredocs
    if len(text) > 65536:
        return False
    if re.search(r"(?:^|[;\n])\s*cd\s|\b(?:chdir|fchdir)\s*\(", text):
        return False
    prefix = os.path.abspath(FLUKE_WORKSPACES) + os.sep
    checked = 0
    for source in python_heredocs(text):
        try:
            tree = ast.parse(source)
        except (SyntaxError, ValueError):
            continue
        if any(not isinstance(stmt, (ast.Assign, ast.Expr, ast.Import, ast.ImportFrom, ast.Assert, ast.With)) for stmt in tree.body):
            continue
        bindings, created = {}, set()
        path_imported = False
        path_modules = set()
        json_modules, json_loads, documents = set(), set(), {}
        if json_keys and any(isinstance(node, ast.Call) and (
                isinstance(node.func, ast.Attribute) and node.func.attr in ('write_text', 'write_bytes', 'open')
                or isinstance(node.func, ast.Name) and node.func.id == 'open') for node in ast.walk(tree)):
            continue

        def evidence_object(path):
            roots = (os.path.realpath(FLUKE_WORKSPACES), os.path.realpath(os.path.expanduser('~/.agents/evidence')))
            real = os.path.realpath(path)
            fluke_relative = real[len(roots[0]) + 1:] if real.startswith(roots[0] + os.sep) else ''
            allowed = (re.match(r'(?:[^/]+/)?docs/superpowers/evidence/.+', fluke_relative)
                       or real.startswith(roots[1] + os.sep))
            if not allowed or not real.endswith('.json'):
                return None
            import stat
            descriptor = None
            try:
                metadata = os.stat(real)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 1048576:
                    return None
                descriptor = os.open(real, os.O_RDONLY | os.O_NONBLOCK)
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 1048576:
                    return None
                with os.fdopen(descriptor, encoding='utf-8') as stream:
                    descriptor = None
                    content = stream.read(1048577)
                if len(content) > 1048576:
                    return None
                data = json.loads(content)
                return data if isinstance(data, dict) else None
            except (OSError, ValueError, UnicodeError):
                return None
            finally:
                if descriptor is not None:
                    os.close(descriptor)

        def literal(node, depth=0):
            if depth > 16:
                return None
            if isinstance(node, ast.Name):
                return bindings.get(node.id)
            if isinstance(node, ast.Call):
                bare = path_imported and isinstance(node.func, ast.Name) and node.func.id == 'Path'
                module = (isinstance(node.func, ast.Attribute) and node.func.attr == 'Path'
                          and isinstance(node.func.value, ast.Name) and node.func.value.id in path_modules)
                if ((bare or module) and len(node.args) == 1 and not node.keywords
                        and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
                    return os.path.abspath(os.path.join(base, node.args[0].value))
            if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
                    and isinstance(node.right, ast.Constant) and isinstance(node.right.value, str)):
                left = literal(node.left, depth + 1)
                if left is not None:
                    return os.path.abspath(os.path.join(left, node.right.value))
            return None

        def call_path(node):
            if not isinstance(node, ast.Call):
                return None, None
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in ('read_text', 'read_bytes', 'write_text', 'write_bytes'):
                return literal(func.value), 'read' if func.attr.startswith('read_') else 'write'
            if isinstance(func, ast.Attribute) and func.attr == 'open':
                path, mode_args = literal(func.value), node.args
            elif isinstance(func, ast.Name) and func.id == 'open' and node.args:
                path, mode_args = literal(node.args[0]), node.args[1:]
            else:
                return None, None
            mode = next((kw.value for kw in node.keywords if kw.arg == 'mode'), mode_args[0] if mode_args else ast.Constant('r'))
            if not isinstance(mode, ast.Constant) or not isinstance(mode.value, str):
                return None, None
            if mode.value in ('r', 'rb', 'rt'):
                return path, 'read'
            if any(char in mode.value for char in 'wax'):
                return path, 'write'
            return None, None

        for stmt in tree.body:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                for item in stmt.names:
                    name = item.asname or item.name.split('.')[0]
                    bindings.pop(name, None)
                    path_modules.discard(name)
                    json_modules.discard(name)
                    json_loads.discard(name)
                    documents.pop(name, None)
                    if isinstance(stmt, ast.Import) and item.name == 'json':
                        json_modules.add(name)
                    if isinstance(stmt, ast.ImportFrom) and stmt.module == 'json' and item.name == 'loads':
                        json_loads.add(name)
                    if isinstance(stmt, ast.Import) and item.name == 'pathlib':
                        path_modules.add(name)
                    if name == 'Path':
                        path_imported = isinstance(stmt, ast.ImportFrom) and stmt.module == 'pathlib' and item.name == 'Path'
            if json_keys:
                # Reachable aliases or calls can invalidate the loaded object's keys.
                if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Name):
                    documents.pop(stmt.value.id, None)
                for node in ast.walk(stmt):
                    if not isinstance(node, ast.Call):
                        continue
                    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                        documents.pop(node.func.value.id, None)
                    for arg in [*node.args, *(kw.value for kw in node.keywords)]:
                        if isinstance(arg, ast.Name):
                            documents.pop(arg.id, None)
                for node in ast.walk(stmt):
                    if (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load)
                            and isinstance(node.value, ast.Name) and node.value.id in documents
                            and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)
                            and node.slice.value not in documents[node.value.id]):
                        return True
            for node in ast.walk(stmt):
                path, operation = call_path(node)
                if not path:
                    continue
                if operation == 'write':
                    created.add(path)
                    continue
                relative = path[len(prefix):] if path.startswith(prefix) else ''
                if not re.match(r'(?:[^/]+/)?docs/superpowers/evidence/.+', relative) or path in created:
                    continue
                checked += 1
                if checked > 16:
                    return False
                if not json_keys and not os.path.exists(path):
                    return True
            if isinstance(stmt, ast.Assign):
                document = None
                call = stmt.value
                if json_keys and isinstance(call, ast.Call) and len(call.args) == 1 and not call.keywords:
                    func = call.func
                    recognized = ((isinstance(func, ast.Name) and func.id in json_loads)
                                  or (isinstance(func, ast.Attribute) and func.attr == 'loads'
                                      and isinstance(func.value, ast.Name) and func.value.id in json_modules))
                    path, operation = call_path(call.args[0])
                    if recognized and path and operation == 'read':
                        checked += 1
                        if checked > 16:
                            return False
                        document = evidence_object(path)
                value = literal(stmt.value)
                for target in stmt.targets:
                    for assigned in ast.walk(target):
                        if not isinstance(assigned, ast.Name):
                            continue
                        bindings[assigned.id] = value if isinstance(target, ast.Name) else None
                        path_modules.discard(assigned.id)
                        json_modules.discard(assigned.id)
                        json_loads.discard(assigned.id)
                        documents.pop(assigned.id, None)
                        if document is not None and isinstance(target, ast.Name):
                            documents[assigned.id] = document
                        if assigned.id == 'Path':
                            path_imported = False
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



def receipt_raw_print(text):
    """Block only direct expansion of the observed large receipt fields."""
    import ast
    pattern = re.compile(r"(?m)^[ \t]*python(?:3(?:\.[0-9]+)?)?\s+-\s+<<(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[ \t]*$")
    for opening in pattern.finditer(text):
        rest = text[opening.end():]
        closing = re.search(r"(?m)^" + re.escape(opening[2]) + r"[ \t]*$", rest)
        if closing is None:
            continue
        code = rest[:closing.start()]
        if len(code) > 65536:
            continue
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError):
            continue
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != 'print':
                continue
            for arg in call.args:
                if isinstance(arg, ast.Subscript) and isinstance(arg.slice, ast.Constant) and arg.slice.value in ('records', 'afterFinalStop', 'afterBackendStop'):
                    return True
    return False


def wrong_mall_metric_field(payload):
    """Reject the observed wrong field only in the mall runtime validator."""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return False
    if "cmd" in tool_input or "command" in tool_input:
        text = command_text(payload)
        if "queue-runtime-isolated.py" not in text or not re.search(r"write_text\s*\(|write_bytes\s*\(", text):
            return False
    else:
        if not any(os.path.basename(path) == "queue-runtime-isolated.py" for path in edit_targets(tool_input)):
            return False
        chunks = []
        for key in ("content", "new_string", "new_str", "new_source", "patch"):
            value = tool_input.get(key)
            if not isinstance(value, str):
                continue
            if key == "patch":
                value = "\n".join(line[1:] for line in value.splitlines() if line.startswith("+") and not line.startswith("+++"))
            chunks.append(value)
        text = "\n".join(chunks)
    return re.search(r"['\"]EventLoopLagMillis['\"]\s+in\s+[A-Za-z_]\w*", text) is not None


def wrong_mall_intake_receipt_field(text):
    """Catch the observed top-level cleanup lookup in inline intake summaries."""
    import ast
    pattern = re.compile(r"(?m)^[ \t]*python(?:3(?:\.[0-9]+)?)?\s+-\s+<<(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[ \t]*$")
    for opening in pattern.finditer(text):
        rest = text[opening.end():]
        closing = re.search(r"(?m)^" + re.escape(opening[2]) + r"[ \t]*$", rest)
        if closing is None:
            continue
        code = rest[:closing.start()]
        if len(code) > 65536 or "mall-api-intake-" not in code or "receipt.json" not in code:
            continue
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError):
            continue
        receipts = set()
        path_flags = {}
        def flags(node):
            if isinstance(node, ast.Name):
                return path_flags.get(node.id, set())
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                result = set()
                if "mall-api-intake-" in node.value:
                    result.add("intake")
                if "receipt.json" in node.value:
                    result.add("receipt")
                return result
            result = set()
            for child in ast.iter_child_nodes(node):
                result.update(flags(child))
            return result
        def visit(node):
            if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                    and node.value.id in receipts and isinstance(node.slice, ast.Constant)
                    and node.slice.value in ("remainingVolumes", "remainingContainers", "cleanupErrors")):
                return True
            if isinstance(node, ast.Assign):
                # Read the right-hand side under the previous source before rebinding.
                if visit(node.value):
                    return True
                value_flags = flags(node.value)
                is_receipt = (isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Attribute) and node.value.func.attr == "loads"
                    and any(isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
                            and item.func.attr == "read_text"
                            and flags(item.func.value) == {"intake", "receipt"}
                            for item in ast.walk(node.value)))
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        path_flags[target.id] = value_flags
                        receipts.discard(target.id)
                        if is_receipt:
                            receipts.add(target.id)
                return False
            return any(visit(child) for child in ast.iter_child_nodes(node))
        if visit(tree):
            return True
    return False


def combined_godot_observation_and_model(text):
    # Narrow to observed direct shell commands. Observation must be inspected
    # before submitting a model request; successful ps is not authorization.
    parts = re.split(r";|\n", text)
    observes = any(re.match(r"\s*(?:ps|pgrep)\b", part)
                   and re.search(r"godot", part, re.I) for part in parts)
    infers = any(re.match(r"\s*localai\s+(?:code|review|second)\b", part)
                 for part in parts)
    return observes and infers


def wrong_fluke_test_database(text, base):
    """Inspect literal executed shell assignments, never embedded source or dynamic values."""
    from urllib.parse import urlsplit, unquote
    # Here-document bodies are data/source, not outer-shell commands.
    lines = text.splitlines(keepends=True)
    outer = []
    pending = []
    for line in lines:
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        outer.append(line)
        pending.extend(re.findall(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", line))
    try:
        lexer = shlex.shlex(''.join(outer), posix=True, punctuation_chars=';&|\n')
        lexer.whitespace = ' \t\r'
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return False
    segments, part = [], []
    for token in tokens:
        if token and all(c in ';&|\n' for c in token):
            if part:
                segments.append(part)
                part = []
        else:
            part.append(token)
    if part:
        segments.append(part)
    cwd = os.path.abspath(base)
    for segment in segments:
        if not segment:
            continue
        head = os.path.basename(segment[0])
        if head == 'cd' and len(segment) == 2 and not any(c in segment[1] for c in '$`'):
            cwd = os.path.abspath(os.path.join(cwd, segment[1]))
            continue
        if 'Fluke' not in cwd.split(os.sep):
            continue
        assignments = []
        if head == 'export':
            assignments = [token for token in segment[1:] if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', token)]
        elif head == 'env':
            for token in segment[1:]:
                if token.startswith('-'):
                    continue
                if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', token):
                    break
                assignments.append(token)
        elif head == 'docker' and len(segment) > 1 and segment[1] in ('run', 'create'):
            for index, token in enumerate(segment[2:], 2):
                if token in ('-e', '--env') and index + 1 < len(segment):
                    assignments.append(segment[index + 1])
                elif token.startswith('--env='):
                    assignments.append(token[6:])
        else:
            # Shell prefix assignments only; quoted arguments to readers are ignored.
            for token in segment:
                if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*=', token):
                    break
                assignments.append(token)
        for assignment in assignments:
            name, _, value = assignment.partition('=')
            if any(c in value for c in '$`'):
                continue
            if name == 'POSTGRES_DB' and value == 'fluke_test':
                return True
            if name == 'FLUKE_TEST_DATABASE_URL':
                try:
                    url = urlsplit(value)
                    if url.scheme in ('postgres', 'postgresql') and url.path and unquote(url.path) != '/fluke_v1_ledger_test':
                        return True
                except ValueError:
                    pass
    return False


def verdict(payload):
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return None, None
    if wrong_mall_metric_field(payload):
        return "mall-metric-field", "商城原延遲欄位是EventLoopLagMs；請核原常數與來源鍵，勿使用已知錯誤欄位EventLoopLagMillis。"
    tool_name = str(payload.get("tool_name") or "")
    is_shell = (
        "command" in tool_input or "cmd" in tool_input
    ) and tool_name != "apply_patch"
    schema_text = command_text(payload) if is_shell else " ".join(str(tool_input[k]) for k in EDIT_KEYS if k in tool_input)
    schema_base = tool_input.get("workdir") or tool_input.get("cwd") or payload.get("cwd") or os.getcwd()
    if wrong_kratos_default(schema_text, schema_base):
        return "kratos-schema-default", "專案沒有註冊default身分格式，請從Kratos設定讀取實際schema_id，再建立測試帳號。"
    if is_shell:
        text = command_text(payload)
        from pos_provider_mock_guard import problem as provider_mock_problem
        mock_error = provider_mock_problem(text, schema_base)
        if mock_error:
            return "pos-provider-mock", mock_error
        from postgres_backup_guard import problem as postgres_backup_problem
        backup_error = postgres_backup_problem(text, schema_base)
        if backup_error:
            return "postgres-backup-version", backup_error
        if wrong_fluke_test_database(text, schema_base):
            return "fluke-test-database", "Fluke測試資料庫必須使用fluke_v1_ledger_test；請核隔離Postgres名稱與FLUKE_TEST_DATABASE_URL，勿使用fluke_test。"
        if combined_godot_observation_and_model(text):
            return "godot-model-observation", "Godot程序觀察與本機模型呼叫須分開；先讀觀察結果再決定是否呼叫模型。"
        if re.search(r"\bcargo\s+(?:test|check|build|clippy|fmt)\b", text):
            from aletheia_rust_contract_guard import problem as rust_contract_problem
            contract_error = rust_contract_problem(schema_base)
            if contract_error:
                return "aletheia-rust-contract", contract_error
        if unknown_literal_git_revision(text, schema_base):
            return "git-source-revision", "目前Git專案沒有這個固定版本，請先核對工作目錄與版本來源，再讀來源檔案。"
        if missing_git_source_path(text, schema_base):
            return "git-source-path", "該Git版本沒有這個路徑，請先列出版本內檔案並核對工作目錄，勿猜路徑。"
        from shell_read_path_guard import missing_shell_read, other_worktree_hits
        missing = missing_shell_read(text, schema_base)
        if missing:
            hits = other_worktree_hits(missing, schema_base)
            hint = "；其他worktree有同名檔，請改用絕對路徑：" + "、".join(hits) if hits else ""
            return "shell-read-path", "固定讀取路徑不存在；請先列出實際檔案，核對後再讀取。" + hint
        if missing_literal_docs_read(text, schema_base):
            return "docs-read-path", "目前工作目錄找不到這個相對文件路徑；請核對專案，跨專案文件改用已確認的絕對路徑。"
        if missing_fluke_evidence_read(text, schema_base):
            return "fluke-evidence-read-path", "這個固定Fluke證據讀取路徑不存在；請先用rg --files列出證據目錄，核對實際檔名後再讀取，不要猜檔名。"
        if missing_fluke_evidence_read(text, schema_base, json_keys=True):
            return "evidence-json-key", "已知證據JSON沒有這個最上層欄位；請先核對實際鍵名，再用已確認的欄位讀取，不要猜格式。"
        if invalid_fixture_preflight(text):
            return "fixture-setup-preflight", "這份隔離啟動器有已知漏項或等待時間超過工具上限；請先核對內層程式路徑、Request匯入及300秒限制，不要啟動服務。"
        if receipt_raw_print(text):
            return "receipt-raw-print", "禁止直接展開大型收據逐筆清單。請只輸出筆數與摘要，完整內容保存檔案。"
        from secret_mask_guard import problem as secret_mask_problem
        mask_error = secret_mask_problem(text)
        if mask_error:
            return "secret-mask-after-print", mask_error
        if wrong_mall_intake_receipt_field(text):
            return "mall-intake-receipt-field", "商城實送收據的清理欄位位於cleanup內；請先核來源格式，勿沿用佇列收據的頂層欄位。"
        if checkpoint_and_commit(text):
            return "checkpoint-commit-order", "進度紀錄與提交須分開執行；先確認正式工具寫入成功，再提交。"
        if checkpoint_shell_write(text):
            return "checkpoint-write", CHECKPOINT_MSG
        if checkpoint_evidence_kind(text):
            return "checkpoint-evidence-kind", "進度證據種類不合法；使用git、file、symbol、test、command、screen、service、model_opinion或other，格式為種類=位置。"
        if checkpoint_prose(text):
            return "checkpoint-prose", PROSE_MSG
        if unchecked_cargo_preflight(text):
            return "cargo-unchecked-preflight", PREFLIGHT_MSG
        if unchecked_cargo_preflight(text, r"git\s+worktree\s+add\b"):
            return "git-unchecked-preflight", "Python前置檢查後直接建立工作樹，未綁定成功條件。請確認成功後再另行建立，或用&&串接。"
        if unchecked_cargo_preflight(text, r"(?:\(\s*)?(?:pnpm|npx|vitest|pytest|node\s+scripts/mutation-check)\b"):
            return "edit-then-verify-unchained", "Python改檔之後直接跑測試，沒有綁定改檔成功；改檔失敗時測試驗到的是舊內容。請用&&把改檔與驗證串起來，或分成兩次執行。"
        if pkill_full(text):
            return "pkill-full", PKILL_MSG
        from errexit_pipefail_guard import problem as pipefail_problem
        if pipefail_problem(text):
            return "errexit-without-pipefail", "管線只回傳最後一段的結束碼，set -e 或 && 看不到前段失敗；請在命令開頭加 setopt pipefail（bash 用 set -o pipefail）。"
        if zsh_unsplit_command(text):
            return "zsh-unsplit-command", ZSH_SPLIT_MSG
        if rev_parse_many(text):
            return "rev-parse-many", REV_PARSE_MSG
        if discard_without_flag(text, payload.get("cwd") or os.getcwd()):
            return "discard-uncommitted", DISCARD_MSG
        if shared_stash_removal(text, payload.get("cwd") or os.getcwd()):
            return "stash-shared-removal", STASH_MSG
        if "command" in tool_input:
            from post_body_guard import written_and_posted
            body_path = written_and_posted(text)
            if body_path:
                return "post-unverified-body", POST_MSG.format(path=body_path)
        if "command" in tool_input and os.environ.get("SHELL", "").endswith("zsh"):
            from shell_glob_guard import unmatched_glob
            word = unmatched_glob(text, schema_base)
            if word:
                return "unmatched-shell-glob", GLOB_MSG.format(word=word)
        return None, None
    if any(k in tool_input for k in EDIT_KEYS) and any(CHECKPOINT.search(p) for p in edit_targets(tool_input)):
        return "checkpoint-write", CHECKPOINT_MSG
    if any(k in tool_input for k in EDIT_KEYS):
        over = loop_over_limit(tool_input)
        if over:
            return "loop-size", LOOP_MSG.format(limit=LOOP_LIMIT, size=over)
    if markdown_registered_prose(tool_input):
        return "markdown-prose", "新增文件文字含已登記的簡體用字；請修正當次新增文字，保留原文引用及既有檢查。"
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
