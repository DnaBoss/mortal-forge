#!/usr/bin/env python3
import argparse
import glob
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HOME = Path.home()
STATE = HOME / ".local/state/idle-agents"
LOG = STATE / "log.jsonl"
HANDOFFS = STATE / "handoffs"
SKIP_PREFIXES = ("<", "# AGENTS.md", "Caveat:")


def read(path):
    try:
        return Path(path).read_text()
    except OSError:
        return ""


def comm(pid):
    return read(f"/proc/{pid}/comm").strip()


def cmdline(pid):
    return read(f"/proc/{pid}/cmdline").replace("\0", " ")


def cwd_of(pid):
    try:
        return os.readlink(f"/proc/{pid}/cwd")
    except OSError:
        return ""


def rss_mb(pid):
    for line in read(f"/proc/{pid}/status").splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) // 1024
    return 0


def ancestors():
    seen = set()
    pid = os.getpid()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        stat = read(f"/proc/{pid}/stat")
        if not stat:
            break
        pid = int(stat.rsplit(")", 1)[1].split()[1])
    return seen


def claude_sessions():
    found = []
    for meta in glob.glob(str(HOME / ".claude/sessions/*.json")):
        try:
            info = json.loads(read(meta))
        except ValueError:
            continue
        pid = info.get("pid")
        if not pid or comm(pid) != "claude" or info.get("kind") != "interactive":
            continue
        if info.get("status") != "idle":
            continue
        cwd = info.get("cwd", "")
        slug = re.sub(r"[^A-Za-z0-9]", "-", cwd)
        transcript = HOME / ".claude/projects" / slug / f"{info['sessionId']}.jsonl"
        found.append({
            "tool": "claude", "pid": pid, "cwd": cwd, "session": info["sessionId"],
            "transcript": transcript, "last_active": info["updatedAt"] / 1000,
        })
    return found


def codex_sessions():
    found = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or comm(entry) != "codex":
            continue
        pid = int(entry)
        if "app-server" in cmdline(pid):
            continue
        rollout = None
        try:
            for fd in os.listdir(f"/proc/{pid}/fd"):
                target = os.readlink(f"/proc/{pid}/fd/{fd}")
                if "/sessions/" in target and os.path.basename(target).startswith("rollout-"):
                    rollout = Path(target)
        except OSError:
            continue
        if rollout is None or not rollout.exists():
            continue
        found.append({
            "tool": "codex", "pid": pid, "cwd": cwd_of(pid), "session": rollout.stem,
            "transcript": rollout, "last_active": rollout.stat().st_mtime,
        })
    return found


def text_of(content):
    if isinstance(content, str):
        return content
    return "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") in ("text", "input_text", "output_text"))


def transcript_messages(path):
    users, assistants = [], []
    for line in read(path).splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("isSidechain"):
            continue
        if obj.get("type") in ("user", "assistant"):
            role, message = obj["type"], obj.get("message", {})
        elif obj.get("type") == "response_item" and obj.get("payload", {}).get("type") == "message":
            message = obj["payload"]
            role = message.get("role")
        else:
            continue
        text = text_of(message.get("content", "")).strip()
        if not text:
            continue
        if role == "user" and not text.startswith(SKIP_PREFIXES):
            users.append(text)
        elif role == "assistant":
            assistants.append(text)
    return users, assistants


def git_state(cwd):
    def run(*args):
        try:
            out = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    branch = run("branch", "--show-current")
    if branch is None:
        return None
    return {"branch": branch, "dirty": (run("status", "--short") or "").splitlines()}


def clip(text, limit):
    return text if len(text) <= limit else text[:limit] + "…"


def write_handoff(session, now):
    users, assistants = transcript_messages(session["transcript"])
    git = git_state(session["cwd"]) if session["cwd"] else None
    idle_h = (now - session["last_active"]) / 3600
    lines = [
        f"# 收尾記錄：{session['tool']} {session['session']}",
        "",
        f"- 產生時間：{datetime.fromtimestamp(now):%Y-%m-%d %H:%M:%S}",
        f"- 目錄：{session['cwd']}",
        f"- 最後活動：{datetime.fromtimestamp(session['last_active']):%Y-%m-%d %H:%M:%S}（閒置 {idle_h:.1f} 小時）",
        f"- 對話檔：{session['transcript']}",
        f"- 還原指令：{'claude --resume ' + session['session'] if session['tool'] == 'claude' else 'codex resume ' + session['session'].split('-')[-1]}",
        "",
        "## 原本的任務",
        clip(users[0], 1500) if users else "（讀不到使用者訊息）",
        "",
        "## 最近的使用者指示",
    ]
    lines += [f"- {clip(u, 400)}" for u in users[-5:]] or ["（無）"]
    lines += ["", "## 最後一則 AI 回覆", clip(assistants[-1], 2000) if assistants else "（無）", "", "## 程式碼狀態"]
    if git is None:
        lines.append("不是 git 目錄或讀不到。")
    else:
        lines.append(f"- 分支：{git['branch'] or '（分離 HEAD）'}")
        if git["dirty"]:
            lines.append(f"- 未提交的修改 {len(git['dirty'])} 項（關閉不會刪檔，但記得處理）：")
            lines += [f"  - `{d}`" for d in git["dirty"][:30]]
        else:
            lines.append("- 沒有未提交的修改")
    HANDOFFS.mkdir(parents=True, exist_ok=True)
    out = HANDOFFS / f"{datetime.fromtimestamp(now):%Y%m%d-%H%M%S}-{session['tool']}-{session['pid']}.md"
    out.write_text("\n".join(lines) + "\n")
    return out


def stop(pid):
    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        time.sleep(0.5)
        if not os.path.exists(f"/proc/{pid}") or comm(pid) not in ("claude", "codex"):
            return True
    return False


def meminfo_gb():
    out = {}
    for line in read("/proc/meminfo").splitlines():
        key, value = line.split(":", 1)
        out[key] = int(value.split()[0]) / 1048576
    return out


def memory_report():
    m = meminfo_gb()
    used = m["MemTotal"] - m["MemFree"] - m["Buffers"] - m["Cached"] - m["SReclaimable"]
    parts = {
        "程式實際佔用": m["AnonPages"],
        "核心不可回收": m["SUnreclaim"] + m["PageTables"] + m["KernelStack"],
    }
    mm = read("/sys/block/zram0/mm_stat").split()
    if mm:
        parts["zram 壓縮區"] = int(mm[2]) / 2**30
    for gtt in glob.glob("/sys/class/drm/card*/device/mem_info_gtt_used"):
        parts["GPU 共用記憶體"] = parts.get("GPU 共用記憶體", 0) + int(read(gtt)) / 2**30
    print(f"已用 {used:.1f}G／總量 {m['MemTotal']:.0f}G；快取 {m['Buffers'] + m['Cached'] + m['SReclaimable']:.0f}G（可回收，不算佔用）")
    for name, value in parts.items():
        print(f"  {name} {value:.1f}G")
    print(f"  其他未對帳 {used - sum(parts.values()):.1f}G")
    totals = {}
    for entry in os.listdir("/proc"):
        if entry.isdigit():
            totals[comm(entry)] = totals.get(comm(entry), 0) + rss_mb(entry)
    print("程式別合計（前 8）：")
    for name, mb in sorted(totals.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {mb}MB {name}")


def main():
    ap = argparse.ArgumentParser(description="找出閒置的 claude／codex，寫收尾記錄後關閉；預設只預覽")
    ap.add_argument("--min-idle-hours", type=float, default=6)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", action="store_true", help="只印記憶體用量拆解")
    args = ap.parse_args()
    if args.report:
        memory_report()
        return 0

    now = time.time()
    skip = ancestors()
    sessions = [s for s in claude_sessions() + codex_sessions() if s["pid"] not in skip]
    rows = []
    for s in sorted(sessions, key=lambda s: s["last_active"]):
        idle_h = (now - s["last_active"]) / 3600
        row = {"tool": s["tool"], "pid": s["pid"], "cwd": s["cwd"], "idle_hours": round(idle_h, 1), "rss_mb": rss_mb(s["pid"])}
        if idle_h < args.min_idle_hours:
            row["action"] = "keep"
        elif not args.apply:
            row["action"] = "would_close"
        else:
            try:
                row["handoff"] = str(write_handoff(s, now))
                row["action"] = "closed" if stop(s["pid"]) else "close_failed"
            except OSError as exc:
                row["action"] = "kept_handoff_failed"
                row["error"] = str(exc)
        rows.append(row)
        print(f"{row['action']:<20} {s['tool']:<6} pid={s['pid']:<8} idle={row['idle_hours']:>6}h rss={row['rss_mb']}MB {s['cwd']}")
    if args.apply:
        STATE.mkdir(parents=True, exist_ok=True)
        with LOG.open("a") as f:
            f.write(json.dumps({"time": now, "rows": rows}, ensure_ascii=False) + "\n")
    print(f"共 {len(rows)} 個，閒置超過 {args.min_idle_hours} 小時：{sum(r['action'] != 'keep' for r in rows)} 個")


if __name__ == "__main__":
    sys.exit(main())
