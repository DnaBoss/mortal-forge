#!/usr/bin/env python3
"""Measure the operational burden of cash-rule from real records (read-only).

Sources (all under the home directory unless overridden):
  *.checkpoints.jsonl   task lifecycle records written by cash-rule-checkpoint
  *.loop.md             LOOP projections
  .claude/projects/**/*.jsonl   Claude Code transcripts (usage per API call, text per message)
  .codex/sessions/**/*.jsonl    Codex transcripts (token_count events, messages)
  .local/state/agent-guards/*.jsonl   guard verdicts
  rule files loaded at session start

usage: cash_rule_burden.py [--days 15] [--home DIR] [--out DIR] [--label NAME]
Writes <out>/<label>-<date>.json and .md. Pure metric functions take parsed records so
tests can feed fixtures; loaders are separate.
"""
import argparse
import json
import os
import pathlib
import re
import statistics
import subprocess
import sys
from datetime import datetime, timedelta, timezone

RULE_FILES = [
    ".claude/CLAUDE.md", ".agents/context-evaluation-workflow.md", ".agents/plain-output/POLICY.md", ".codex/AGENTS.md",
    ".agents/skills/cash-rule/SKILL.md", ".agents/skills/mortal-tools/SKILL.md", ".agents/skills/cargo-cache/SKILL.md",
]
PRUNE = ["node_modules", ".git", "target", ".cache"]


def parse_ts(value):
    if not value:
        return None
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def read_jsonl(path):
    """Yield (record, None) for parsable lines and (None, line) for bad ones."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line), None
                except ValueError:
                    yield None, line
    except OSError:
        return


def quantiles(values):
    values = sorted(v for v in values if v is not None)
    if not values:
        return {"n": 0, "median": None, "p90": None, "max": None}
    return {"n": len(values), "median": statistics.median(values), "p90": values[min(len(values) - 1, int(0.9 * len(values)))],
            "max": values[-1]}


# ---------- pure metric functions ----------

def checkpoint_metrics(records, since):
    """records: iterable of (record, path, raw_len). Returns metrics and per-task rows."""
    tasks = {}
    bad = 0
    for rec, path, raw_len in records:
        if rec is None:
            bad += 1
            continue
        ts = parse_ts(rec.get("recorded_at"))
        if ts is None or ts < since:
            continue
        tid = rec.get("task_id") or path
        t = tasks.setdefault(tid, {"records": [], "bytes": 0})
        t["records"].append((ts, rec))
        t["bytes"] += raw_len
    rows = []
    repeats = total = waiting_records = 0
    waiting_hours = 0.0
    usage_exact = 0
    sizes = []
    for tid, t in tasks.items():
        recs = sorted(t["records"], key=lambda x: x[0])
        prev = None
        for ts, rec in recs:
            total += 1
            key = (rec.get("task_state"), rec.get("step_id"), rec.get("step_state"))
            if prev is not None and key == prev:
                repeats += 1
            prev = key
            if rec.get("task_state") == "WAITING":
                waiting_records += 1
            usage = rec.get("usage") or {}
            tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
            if isinstance(tokens, dict) and tokens.get("status") == "exact":
                usage_exact += 1
        for (ts, rec), (nts, _) in zip(recs, recs[1:]):
            if rec.get("task_state") == "WAITING":
                waiting_hours += (nts - ts).total_seconds() / 3600
        span_h = (recs[-1][0] - recs[0][0]).total_seconds() / 3600
        sizes.append(t["bytes"] / len(recs))
        rows.append({"task_id": tid, "records": len(recs), "span_hours": round(span_h, 2), "final_state": recs[-1][1].get("task_state"),
                     "bytes": t["bytes"]})
    long_rows = [r for r in rows if r["span_hours"] >= 4]
    long_hours = sum(r["span_hours"] for r in long_rows)
    final = {}
    for r in rows:
        final[r["final_state"]] = final.get(r["final_state"], 0) + 1
    return {
        "tasks": len(rows), "records": total, "bad_lines": bad, "bytes_total": sum(r["bytes"] for r in rows),
        "bytes_per_record_median": round(statistics.median(sizes), 1) if sizes else None,
        "tasks_ge_4h": len(long_rows), "records_in_tasks_ge_4h": sum(r["records"] for r in long_rows),
        "records_per_hour_in_tasks_ge_4h": round(sum(r["records"] for r in long_rows) / long_hours, 2) if long_hours else None,
        "repeat_records": repeats, "repeat_ratio": round(repeats / total, 3) if total else None,
        "waiting_records": waiting_records, "waiting_hours": round(waiting_hours, 1),
        "usage_exact_records": usage_exact, "final_state": final,
    }, rows


def loop_metrics(sizes):
    q = quantiles(sizes)
    return {"files": q["n"], "chars_total": sum(sizes), "chars_median": q["median"], "chars_p90": q["p90"]}


def claude_metrics(records, since):
    """records: iterable of (session_id, record) in file order (Claude Code transcript lines). Streaming."""
    out = {"sessions": 0, "human_prompts": 0, "human_chars": 0, "assistant_text_messages": 0, "assistant_text_chars": 0,
           "tool_uses": 0, "api_calls": 0, "compactions": 0, "sidechain_records": 0, "sessions_ge_30_prompts": 0}
    msg_lengths, contexts, outputs = [], [], []
    sessions = {}  # sid -> {"prompts": n, "calls": set()}
    for sid, rec in records:
        ts = parse_ts(rec.get("timestamp"))
        if ts is None or ts < since:
            continue
        st = sessions.setdefault(sid, {"prompts": 0, "calls": set()})
        if rec.get("isSidechain"):
            out["sidechain_records"] += 1
            continue
        if rec.get("isCompactSummary"):
            out["compactions"] += 1
            continue
        msg = rec.get("message") or {}
        content = msg.get("content")
        if rec.get("type") == "user":
            if isinstance(content, str):
                st["prompts"] += 1
                out["human_chars"] += len(content)
            elif isinstance(content, list) and not any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content):
                text = "".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
                if text and not rec.get("isMeta"):
                    st["prompts"] += 1
                    out["human_chars"] += len(text)
        elif rec.get("type") == "assistant":
            mid = msg.get("id") or rec.get("requestId")
            usage = msg.get("usage") or {}
            if mid and mid not in st["calls"] and usage:
                st["calls"].add(mid)
                out["api_calls"] += 1
                contexts.append((usage.get("input_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0)
                                + (usage.get("cache_creation_input_tokens") or 0))
                outputs.append(usage.get("output_tokens") or 0)
            for c in content if isinstance(content, list) else []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text" and c.get("text"):
                    out["assistant_text_messages"] += 1
                    out["assistant_text_chars"] += len(c["text"])
                    msg_lengths.append(len(c["text"]))
                elif c.get("type") == "tool_use":
                    out["tool_uses"] += 1
    out["sessions"] = len(sessions)
    out["human_prompts"] = sum(s["prompts"] for s in sessions.values())
    out["sessions_ge_30_prompts"] = sum(1 for s in sessions.values() if s["prompts"] >= 30)
    out["ai_chars_per_human_char"] = round(out["assistant_text_chars"] / out["human_chars"], 2) if out["human_chars"] else None
    out["assistant_message_chars"] = quantiles(msg_lengths)
    out["context_tokens_per_call"] = quantiles(contexts)
    out["output_tokens_per_call"] = quantiles(outputs)
    out["context_tokens_total"] = sum(contexts)
    return out


def codex_metrics(records, since):
    """records: iterable of (session_id, record) (Codex rollout lines). Streaming.

    Codex user-role messages also carry injected blocks (<environment_context>, <user_instructions>);
    texts starting with '<' are skipped so only typed input counts."""
    out = {"sessions": 0, "user_messages": 0, "user_chars": 0, "assistant_messages": 0, "assistant_chars": 0, "turns": 0}
    contexts, lengths = [], []
    sessions = set()
    for sid, rec in records:
        ts = parse_ts(rec.get("timestamp"))
        if ts is None or ts < since:
            continue
        sessions.add(sid)
        payload = rec.get("payload") or {}
        if rec.get("type") == "response_item" and payload.get("type") == "message":
            text = "".join(c.get("text", "") for c in payload.get("content", []) if isinstance(c, dict))
            if payload.get("role") == "user" and text and not text.lstrip().startswith("<"):
                out["user_messages"] += 1
                out["user_chars"] += len(text)
            elif payload.get("role") == "assistant":
                out["assistant_messages"] += 1
                out["assistant_chars"] += len(text)
                lengths.append(len(text))
        elif rec.get("type") == "event_msg" and payload.get("type") == "token_count":
            last = (payload.get("info") or {}).get("last_token_usage") or {}
            if last:
                out["turns"] += 1
                contexts.append(last.get("input_tokens") or 0)  # cached_input_tokens is a subset of input_tokens
    out["sessions"] = len(sessions)
    out["ai_chars_per_human_char"] = round(out["assistant_chars"] / out["user_chars"], 2) if out["user_chars"] else None
    out["assistant_message_chars"] = quantiles(lengths)
    out["context_tokens_per_turn"] = quantiles(contexts)
    return out


def guard_metrics(lines_by_file, since):
    out = {}
    for name, lines in lines_by_file.items():
        events = deny = blocked = 0
        rules = {}
        for rec in lines:
            if rec is None:
                continue
            ts = parse_ts(rec.get("at"))
            if ts is None or ts < since:
                continue
            events += 1
            if rec.get("verdict") == "deny":
                deny += 1
                rules[rec.get("rule")] = rules.get(rec.get("rule"), 0) + 1
            if rec.get("blocked"):
                blocked += 1
        top = sorted(rules.items(), key=lambda x: -x[1])[:5]
        out[name] = {"events": events, "deny": deny, "blocked": blocked, "top_deny_rules": top}
    return out


# ---------- loaders ----------

def find_files(home, pattern, days):
    cmd = ["find", str(home), "-xdev"]
    for i, name in enumerate(PRUNE):
        cmd += (["("] if i == 0 else []) + ["-name", name] + (["-o"] if i < len(PRUNE) - 1 else [")", "-prune", "-o"])
    cmd += ["-name", pattern, "-mtime", f"-{days + 1}", "-print"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=300).stdout
    except subprocess.TimeoutExpired:
        return []
    return [pathlib.Path(p) for p in out.splitlines() if p]


def load_checkpoints(paths):
    for p in paths:
        for rec, raw in read_jsonl(p):
            yield rec, str(p), (len(json.dumps(rec, ensure_ascii=False)) if rec is not None else len(raw or ""))


def load_sessions(paths):
    """Yield (session_id, record) lazily; one transcript file is one session."""
    for p in paths:
        for rec, _ in read_jsonl(p):
            if rec is not None:
                yield str(p), rec


def rule_metrics(home, rule_files):
    files = list(rule_files)
    refs = home / ".agents/skills/cash-rule/references"
    tmpl = home / ".agents/skills/cash-rule/templates"
    for d in (refs, tmpl):
        if d.is_dir():
            files += [str(p.relative_to(home)) for p in sorted(d.glob("*.md"))]
    chars = {}
    for rel in files:
        p = home / rel
        if p.is_file():
            chars[rel] = len(p.read_text(encoding="utf-8", errors="replace"))
    lessons = home / ".agents/lessons.md"
    text = lessons.read_text(encoding="utf-8", errors="replace") if lessons.is_file() else ""
    return {"rule_files": len(chars), "rule_chars": sum(chars.values()), "per_file": chars,
            "lessons_chars": len(text), "lessons_entries": len(re.findall(r"^## ", text, re.M))}


def render(m):
    c, cl, cx, g, r = m["checkpoints"], m["claude"], m["codex"], m["guards"], m["rules"]
    lines = [f"# cash-rule 負擔基準（{m['label']}，近 {m['days']} 天，產生於 {m['generated_at'][:16]}）", "",
             "| 指標 | 數值 |", "| --- | --- |",
             f"| 任務數／≥4 小時任務數 | {c['tasks']}／{c['tasks_ge_4h']} |",
             f"| checkpoint 筆數／其中 ≥4 小時任務 | {c['records']:,}／{c['records_in_tasks_ge_4h']:,} |",
             f"| ≥4 小時任務每小時 checkpoint 筆數 | {c['records_per_hour_in_tasks_ge_4h']} |",
             f"| 無狀態變化的重複筆數比例 | {c['repeat_ratio']} |",
             f"| checkpoint 總位元組／每筆中位數 | {c['bytes_total']:,}／{c['bytes_per_record_median']} |",
             f"| 有精確用量的筆數 | {c['usage_exact_records']}／{c['records']} |",
             f"| WAITING 筆數／等待小時 | {c['waiting_records']}／{c['waiting_hours']} |",
             f"| 任務終態 | {json.dumps(c['final_state'], ensure_ascii=False)} |",
             f"| LOOP 檔數／總字元／中位數 | {m['loops']['files']:,}／{m['loops']['chars_total']:,}／{m['loops']['chars_median']} |",
             f"| Claude session／人類輸入則數 | {cl['sessions']}／{cl['human_prompts']} |",
             f"| Claude AI 字元 ÷ 人類字元 | {cl['ai_chars_per_human_char']} |",
             f"| Claude 每則回覆字元中位數／p90 | {cl['assistant_message_chars']['median']}／{cl['assistant_message_chars']['p90']} |",
             f"| Claude 每次呼叫輸入 token 中位數／p90／最大 | {cl['context_tokens_per_call']['median']}／{cl['context_tokens_per_call']['p90']}／{cl['context_tokens_per_call']['max']} |",
             f"| Claude 壓縮次數／≥30 則輸入的 session | {cl['compactions']}／{cl['sessions_ge_30_prompts']} |",
             f"| Codex session／AI 字元 ÷ 人類字元 | {cx['sessions']}／{cx['ai_chars_per_human_char']} |",
             f"| Codex 每輪輸入 token 中位數／p90 | {cx['context_tokens_per_turn']['median']}／{cx['context_tokens_per_turn']['p90']} |",
             f"| 規則檔字元／lessons 字元／條數 | {r['rule_chars']:,}／{r['lessons_chars']:,}／{r['lessons_entries']} |"]
    for name, v in g.items():
        lines.append(f"| guard {name} 事件／擋下 | {v['events']:,}／{v['deny'] or v['blocked']} |")
    lines += ["", f"來源：checkpoint 檔 {m['sources']['checkpoint_files']}、LOOP 檔 {m['sources']['loop_files']}、Claude 檔 {m['sources']['claude_files']}、Codex 檔 {m['sources']['codex_files']}；壞行 {c['bad_lines']}。", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=15)
    ap.add_argument("--home", default=str(pathlib.Path.home()))
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default="baseline")
    args = ap.parse_args()
    home = pathlib.Path(args.home)
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    out_dir = pathlib.Path(args.out) if args.out else home / ".local/state/cash-rule/burden"
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_files = find_files(home, "*.checkpoints.jsonl", args.days)
    loop_files = find_files(home, "*.loop.md", args.days)
    claude_files = [p for p in (home / ".claude/projects").rglob("*.jsonl") if p.stat().st_mtime >= since.timestamp()] if (home / ".claude/projects").is_dir() else []
    codex_files = [p for p in (home / ".codex/sessions").rglob("*.jsonl") if p.stat().st_mtime >= since.timestamp()] if (home / ".codex/sessions").is_dir() else []
    guard_dir = home / ".local/state/agent-guards"
    guard_lines = {p.stem: [rec for rec, _ in read_jsonl(p)] for p in sorted(guard_dir.glob("*.jsonl"))} if guard_dir.is_dir() else {}
    ck, rows = checkpoint_metrics(load_checkpoints(ckpt_files), since)
    metrics = {
        "label": args.label, "days": args.days, "generated_at": datetime.now().astimezone().isoformat(), "since": since.isoformat(),
        "sources": {"checkpoint_files": len(ckpt_files), "loop_files": len(loop_files), "claude_files": len(claude_files), "codex_files": len(codex_files)},
        "checkpoints": ck,
        "loops": loop_metrics([len(p.read_text(encoding="utf-8", errors="replace")) for p in loop_files if p.is_file()]),
        "claude": claude_metrics(load_sessions(claude_files), since),
        "codex": codex_metrics(load_sessions(codex_files), since),
        "guards": guard_metrics(guard_lines, since),
        "rules": rule_metrics(home, RULE_FILES),
        "tasks": sorted(rows, key=lambda r: -r["span_hours"]),
    }
    stamp = datetime.now().strftime("%Y%m%d")
    (out_dir / f"{args.label}-{stamp}.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")
    (out_dir / f"{args.label}-{stamp}.md").write_text(render(metrics))
    print(render(metrics))
    print("written", out_dir / f"{args.label}-{stamp}.json")


if __name__ == "__main__":
    main()
