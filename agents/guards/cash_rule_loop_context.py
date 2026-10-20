#!/usr/bin/env python3
"""SessionStart/UserPromptSubmit: remind the model to apply /cash-rule and drive
multi-step work with /loop. Injects context only; grants no new authorization."""
import json, os, sys

try:
    payload = json.loads(sys.stdin.read() or "{}")
except Exception:
    payload = {}

event = payload.get("hook_event_name") or "UserPromptSubmit"
skill = os.path.expanduser("~/.claude/skills/cash-rule/SKILL.md")

if event == "SessionStart":
    text = (
        "cash-rule 與 /loop 自動套用（使用者 2026-09-30 定）：\n"
        f"- 非瑣碎工作一律依 {skill} 的生命週期推進（Inspect → Plan → Execute → Validate → Review → Checkpoint），"
        "等同使用者已輸入 /cash-rule，不需再次提醒。\n"
        "- 需要跨多輪持續推進的工作（有 LOOP 檔、未達整體驗收、非 WAITING/BLOCKED），"
        "用 /loop 動態模式（ScheduleWakeup）自排下一輪，prompt 帶 /cash-rule 與 LOOP 檔路徑；"
        "等人就停 loop 不喚醒，等外部事件才排且間隔至少 20 分鐘（使用者 2026-10-15 定）；"
        "達 COMPLETE、BLOCKED 或需使用者決定時停止 loop 並回報。\n"
        "- 簡單問答、純評估或診斷不開 loop。checkpoint 只在狀態變化或有新證據時寫；"
        "對人回報只有目標、做法、每 step 一句成果、重大事件。\n"
        "- 這個 hook 不增加部署、重啟、刪除或真實下單授權；這些仍要使用者明確同意。"
        "合併已由使用者授權直接做（RULES.md「範圍與決策」，2026-10-19）。"
    )
else:
    text = (
        "提醒：非瑣碎工作依 /cash-rule 推進；持續多輪工作用 /loop 動態模式自排下一輪，"
        "達 COMPLETE／BLOCKED／需決策時停止。不增加任何授權。"
    )

print(json.dumps({"hookSpecificOutput": {"hookEventName": event,
      "additionalContext": text}}, ensure_ascii=False))
