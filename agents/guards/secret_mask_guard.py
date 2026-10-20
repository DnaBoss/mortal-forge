"""Printing text and then hiding a secret with a regex fails open: when the regex misses, the
secret is already in the tool output. 2026-10-16 an Aletheia page token got through a bad mask;
2026-10-19 a seed password got through twice (`grep ... | sed 's/PASSWORD=[^ ]*/***/'` and
`sed -E 's/(password)[^,}]*/\\1:<masked>/g' file`).

Flagged when a `sed` or `perl` command has an `s` substitution whose replacement is a mask
marker (`***`, `<masked>`, `redacted`, `[hidden]`). Heredoc bodies are data and are removed
first. Read only the fields you need with a parser, or print only length / presence.
"""
import re

from errexit_pipefail_guard import strip_heredocs

TOOL = re.compile(r"(?:^|[\s|;&(])(?:sed|perl)\s")
SUBST = re.compile(r"(?<![\w.-])s([/#|,@:!])((?:\\.|(?!\1).)*)\1((?:\\.|(?!\1).)*)\1")
MASK = re.compile(r"\*{3}|<masked>|redacted|\[hidden\]", re.I)

MSG = ("不要先印出再用 sed／perl 遮蔽秘密：遮蔽規則一失手，密碼或權杖就已經進了輸出。"
       "改用解析器只取需要的欄位，或只印長度／是否存在。")


def problem(text):
    if len(text) > 65536:
        return None
    body = strip_heredocs(text)
    if not TOOL.search(body):
        return None
    if any(MASK.search(m.group(3)) for m in SUBST.finditer(body)):
        return MSG
    return None
