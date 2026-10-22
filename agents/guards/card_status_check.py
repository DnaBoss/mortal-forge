#!/usr/bin/env python3
"""Stop-hook check: board #27 card Status must follow the PRs that work on the card.

Called from finish_check.py. Runs only when the turn used `gh`/`git push` or the
final reply names a PR, and only inside a newretail-ai-mall checkout.

Card semantics (ai-mall CLAUDE.md):
  進行中 = coding / PR open / merged into dev;  待驗收 = shipped to main.
Rules for every card linked from a PR touched this turn:
  - an open PR, or a PR merged into dev whose merge commit is not in main
    -> card must be 進行中;
  - every linked PR merged and in main -> card must be 待驗收/已上版/已結束;
  - card not on the board -> problem.
A PR links a card when the card number is in the PR title, on a
Refs/Closes/Fixes/Resolves/關聯 line of the body, or GitHub will close it.
Release PRs (base main) and LOOP-doc PRs (`docs(loop...)`) are not card work.
Also: a draft PR named in the final reply together with "ready for review"
wording blocks (turn it ready first).

Read-only. GitHub cost per triggered stop: 2 GraphQL queries plus one REST
compare per merged-into-dev PR not yet known to be in main (known ones are
cached). Any API failure is a fault (reported, never blocks).
"""
import json
import os
import re
import subprocess
import time

REPO = "tsg-newretail/newretail-ai-mall"
OWNER, NAME = REPO.split("/")
PROJECT = 27
WORKING = "進行中"
SHIPPED = {"待驗收", "已上版", "已結束"}
MAX_ITEMS = 20
TAIL_BYTES = 8 * 1024 * 1024
GH = os.environ.get("CARD_CHECK_GH", "gh")
CACHE = os.path.expanduser("~/.cache/agent-guards/card_status_in_main.json")

TRIGGER = re.compile(r"(?:^|[\s;&|(])(?:gh\s|git\s+push\b)")
PR_URL = re.compile(re.escape(REPO) + r"(?:/pulls?/|#)(\d{2,6})(?!\d)")
PR_API = re.compile(re.escape(REPO) + r"/(?:pulls|issues)/(\d{2,6})(?!\d)")
GH_PR_CMD = re.compile(r"\bgh\s+pr\s+(?:create|ready|edit|merge|view|comment|close|reopen|checks|diff)\b[^\n;&|]*?\s#?(\d{2,6})(?!\d)")
HASH_NUM = re.compile(r"(?<![\w/#])#(\d{2,6})(?!\d)")
LINK_LINE = re.compile(r"(?im)^\W*(?:(?:refs?|closes?|closed|fix(?:es|ed)?|resolves?|resolved)\b|關聯)[^\n]*$")
LOOP_DOC = re.compile(r"^docs\(loops?\)")
READY_WORDS = re.compile(r"可以\s*review|可\s*review|請.{0,4}review|要不要合|合進\s*dev|合\s*dev|等你決定|做完")


def gh(args, timeout=20):
    r = subprocess.run([GH, *args], capture_output=True, text=True, timeout=timeout, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"gh {args[0]} {args[1] if len(args) > 1 else ''} 失敗：{(r.stderr or r.stdout).strip()[:120]}")
    return json.loads(r.stdout)


def in_ai_mall(cwd):
    r = subprocess.run(["git", "-C", cwd, "remote", "get-url", "origin"], capture_output=True, text=True, timeout=10,
                       check=False)
    return r.returncode == 0 and REPO in r.stdout


def text_of(content):
    if isinstance(content, str):
        return content
    out = []
    for part in content if isinstance(content, list) else []:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            out.append(part.get("text") or "")
        elif part.get("type") == "tool_result":
            out.append(text_of(part.get("content")))
    return "\n".join(out)


def turn_entries(path):
    """Main-thread entries after the last real user prompt (tool results are not prompts)."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            fh.seek(max(0, size - TAIL_BYTES))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("type") in ("user", "assistant") and not row.get("isSidechain"):
            rows.append(row)
    start = 0
    for i, row in enumerate(rows):
        content = (row.get("message") or {}).get("content")
        is_prompt = row["type"] == "user" and not row.get("isMeta") and (
            isinstance(content, str) or any(isinstance(p, dict) and p.get("type") == "text" for p in content or []))
        if is_prompt:
            start = i
    return rows[start:]


def touched(entries, cwd_is_mall):
    """(ran gh/git push this turn, PR numbers touched this turn)."""
    ran, prs = False, []
    for row in entries:
        content = (row.get("message") or {}).get("content")
        for part in content if isinstance(content, list) else []:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "tool_use":
                cmd = (part.get("input") or {}).get("command") or ""
                if not isinstance(cmd, str) or not TRIGGER.search(cmd):
                    continue
                ran = True
                prs += PR_URL.findall(cmd) + PR_API.findall(cmd)
                if cwd_is_mall or REPO in cmd:
                    prs += GH_PR_CMD.findall(cmd)
            elif part.get("type") == "tool_result":
                prs += PR_URL.findall(text_of(part.get("content")))
    return ran, prs


def unique(nums):
    seen, out = set(), []
    for n in nums:
        n = int(n)
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out[:MAX_ITEMS]


def graphql(query):
    # gh exits non-zero when any alias fails (e.g. a number that does not exist);
    # keep the partial data, fail only when there is none.
    r = subprocess.run([GH, "api", "graphql", "-f", f"query={query}"], capture_output=True, text=True, timeout=30,
                       check=False)
    try:
        data = json.loads(r.stdout)
    except ValueError:
        raise RuntimeError(f"gh api graphql 失敗：{(r.stderr or r.stdout).strip()[:120]}")
    repo = (data.get("data") or {}).get("repository")
    if not isinstance(repo, dict):
        raise TypeError(f"GraphQL 沒有資料：{str(data.get('errors') or r.stderr)[:120]}")
    return repo


PR_FIELDS = "number title body state isDraft baseRefName mergeCommit { oid } repository { nameWithOwner }"


def fetch_prs(numbers):
    parts = " ".join(f"n{n}: issueOrPullRequest(number: {n}) {{ __typename ... on PullRequest {{ {PR_FIELDS} }} }}"
                     for n in numbers)
    repo = graphql(f'query {{ repository(owner: "{OWNER}", name: "{NAME}") {{ {parts} }} }}')
    return [v for v in repo.values() if isinstance(v, dict) and v.get("__typename") == "PullRequest"]


def fetch_cards(numbers):
    status = ("projectItems(first: 10) { nodes { project { number } "
              'fieldValueByName(name: "Status") { ... on ProjectV2ItemFieldSingleSelectValue { name } } } }')
    refs = (f"timelineItems(itemTypes: [CROSS_REFERENCED_EVENT], last: 50) {{ nodes {{ ... on CrossReferencedEvent {{ "
            f"willCloseTarget source {{ ... on PullRequest {{ {PR_FIELDS} }} }} }} }} }}")
    parts = " ".join(f"n{n}: issueOrPullRequest(number: {n}) {{ __typename ... on Issue {{ number state {status} {refs} }} }}"
                     for n in numbers)
    repo = graphql(f'query {{ repository(owner: "{OWNER}", name: "{NAME}") {{ {parts} }} }}')
    return [v for v in repo.values() if isinstance(v, dict) and v.get("__typename") == "Issue"]


def is_card_work(pr):
    return ((pr.get("repository") or {}).get("nameWithOwner") == REPO and pr.get("baseRefName") != "main"
            and not LOOP_DOC.match(pr.get("title") or ""))


def linked(pr):
    """Card numbers a PR works on."""
    nums = HASH_NUM.findall(pr.get("title") or "")
    for line in LINK_LINE.findall(pr.get("body") or ""):
        nums += HASH_NUM.findall(line)
    return {int(n) for n in nums} - {pr.get("number")}


def load_cache():
    try:
        with open(CACHE, encoding="utf-8") as fh:
            return set(json.load(fh))
    except (OSError, ValueError, TypeError):
        return set()


def save_cache(shas):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    tmp = f"{CACHE}.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(sorted(shas)[-2000:], fh)
    os.replace(tmp, CACHE)


def in_main(sha, cache):
    if sha in cache:
        return True
    data = gh(["api", f"repos/{REPO}/compare/{sha}...main?per_page=1", "--jq", "{status: .status}"])
    if data.get("status") in ("ahead", "identical"):
        cache.add(sha)
        return True
    return False


def card_problem(card, cache):
    num = card["number"]
    statuses = [((i.get("fieldValueByName") or {}).get("name") or "（沒有 Status）")
                for i in (card.get("projectItems") or {}).get("nodes") or []
                if (i.get("project") or {}).get("number") == PROJECT]
    if not statuses:
        return f"#{num} 不在看板 #{PROJECT} 上"
    status = statuses[0]
    prs = {}
    for event in (card.get("timelineItems") or {}).get("nodes") or []:
        pr = (event or {}).get("source") or {}
        if "baseRefName" not in pr or not is_card_work(pr):
            continue
        if event.get("willCloseTarget") or num in linked(pr):
            prs[pr["number"]] = pr
    if not prs:
        return None
    working = []
    for pr in sorted(prs.values(), key=lambda p: p["number"]):
        if pr["state"] == "OPEN":
            working.append(f"#{pr['number']} 開著")
        elif pr["state"] == "MERGED":
            sha = (pr.get("mergeCommit") or {}).get("oid")
            if sha and not in_main(sha, cache):
                working.append(f"#{pr['number']} 已合 dev、還沒進 main")
    if working and status != WORKING:
        return f"#{num} 卡片是「{status}」，應為「{WORKING}」（{'、'.join(working)}）"
    shipped = [p for p in prs.values() if p["state"] == "MERGED"]
    if not working and shipped and status not in SHIPPED:
        return f"#{num} 卡片是「{status}」，但關聯 PR 都已進 main，應為「待驗收」「已上版」或「已結束」之一"
    return None


def problems(payload, faults):
    cwd = payload.get("cwd") or os.getcwd()
    reply = payload.get("last_assistant_message") or ""
    if not isinstance(reply, str):
        reply = ""
    try:
        cwd_is_mall = in_ai_mall(cwd)
        ran, prs = touched(turn_entries(payload.get("transcript_path") or ""), cwd_is_mall)
        mentioned = [int(n) for n in PR_URL.findall(reply)]
        if cwd_is_mall:
            mentioned += [int(n) for n in HASH_NUM.findall(reply)]
        if not ran and not PR_URL.search(reply):
            return []
        numbers = unique(prs + mentioned)
        if not numbers:
            return []
        out = []
        pr_nodes = fetch_prs(numbers)
        said = set(mentioned)
        if READY_WORDS.search(reply):
            out += [f"PR #{p['number']} 還是草稿，回覆卻寫成可以 review／等決定；先 `gh pr ready {p['number']}`"
                    for p in pr_nodes if p.get("isDraft") and p.get("state") == "OPEN" and p["number"] in said]
        touched_set = set(unique(prs)) | said
        cards = set()
        for pr in pr_nodes:
            if pr["number"] in touched_set and is_card_work(pr):
                cards |= linked(pr)
        if not cards:
            return out
        cache = load_cache()
        before = set(cache)
        for card in fetch_cards(sorted(cards)[:MAX_ITEMS]):
            p = card_problem(card, cache)
            if p:
                out.append(p)
        if cache != before:
            save_cache(cache)
        if out:
            out.append(f"看板語意：PR 開著或合 dev＝{WORKING}；已進 main＝待驗收。改完讀回 Status 再結束")
        return out
    except Exception as exc:  # noqa: BLE001 - a broken checker reports, never blocks
        faults.append(f"卡片狀態檢查：{type(exc).__name__}: {exc}"[:200])
        return []


if __name__ == "__main__":
    import sys
    f = []
    started = time.time()
    print(json.dumps({"problems": problems(json.load(sys.stdin), f), "faults": f,
                      "seconds": round(time.time() - started, 2)}, ensure_ascii=False, indent=1))
