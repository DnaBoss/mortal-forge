#!/usr/bin/env python3
"""Reject direct goal creation without an explicit positive token budget.
Only direct tool payloads are covered. Does not intercept app-server clients,
inline JavaScript, or model generation. Not a security boundary.
"""
import json,sys

def decision(payload):
    if payload.get('hook_event_name') != 'PreToolUse':
        return {}
    name=payload.get('tool_name','').split('.')[-1]
    if name not in ('create_goal','functions_create_goal'):
        return {}
    args=payload.get('tool_input',{})
    if isinstance(args,str):
        try: args=json.loads(args)
        except (ValueError,TypeError): args={}
    value=args.get('token_budget') if isinstance(args,dict) else None
    if isinstance(value,int) and not isinstance(value,bool) and value>0:
        return {}
    return {'hookSpecificOutput':{'hookEventName':'PreToolUse','permissionDecision':'deny','permissionDecisionReason':'自動任務必須先由使用者指定正整數 TOKEN 上限；禁止無上限 create_goal。不要自行猜預算或改走其他入口。'}}

if __name__=='__main__':
    try: payload=json.load(sys.stdin)
    except (ValueError,TypeError): payload={}
    print(json.dumps(decision(payload),ensure_ascii=False))
