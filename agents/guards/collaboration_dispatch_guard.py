#!/usr/bin/env python3
"""Require wake-capable dispatch for explicit follow-up work requests."""
import json
import re
import sys

ACTION = re.compile(r'獨立核|確認|核對|提供|回報|驗證|檢查|重跑|修改|更新|實作|測試|執行|調整|新增|完成|接續|續做|保存|啟動|停止|清理')



def without_quoted_text(message):
    # Mask complete quoted spans before sentence splitting; keep outside requests.
    pairs = {'「': '」', '『': '』', '“': '”', '"': '"'}
    stack = []
    spans = []
    start = None
    escaped = False
    for index, char in enumerate(message):
        if escaped:
            escaped = False
            continue
        if char == '\\':
            escaped = True
            continue
        if stack and char == stack[-1]:
            stack.pop()
            if not stack:
                spans.append((start, index + 1))
        elif char in pairs:
            if not stack:
                start = index
            stack.append(pairs[char])
    pieces = []
    previous = 0
    for begin, end in spans:
        pieces.extend((message[previous:begin], ' '))
        previous = end
    pieces.append(message[previous:])
    return ''.join(pieces)


def verdict(payload):
    # Only the actual tool identity and its direct message argument count.
    # Do not infer agent status or inspect quoted tool names in other commands.
    name = payload.get('tool_name')
    if name not in ('collaboration.send_message', 'collaboration__send_message'):
        return None
    value = payload.get('tool_input')
    if not isinstance(value, dict) or not isinstance(value.get('message'), str):
        return None
    for clause in re.split(r'[。！？\n]', without_quoted_text(value['message'])):
        clause = clause.strip()
        if not clause.startswith('請') or clause.startswith(('請勿', '請不要', '請知悉')):
            continue
        if ACTION.search(clause[:160]):
            return ('明確後續工作請用 collaboration.followup_task；它會對執行中的代理送訊息、對閒置代理喚醒新回合。'
                    'send_message 只適用一般資訊，本規則不查代理狀態。')
    return None


def main():
    payload = json.load(sys.stdin)
    reason = verdict(payload)
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": reason}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
