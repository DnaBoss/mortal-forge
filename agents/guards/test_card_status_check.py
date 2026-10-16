"""Stop JSON entrypoint tests for card_status_check via finish_check.py.

GitHub is replaced by a fake `gh` (CARD_CHECK_GH) that answers from a fixture
and logs every call, so no network is used.
"""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

GUARD = Path(os.environ.get("CARD_TEST_FINISH", str(Path(__file__).with_name("finish_check.py"))))
MALL = "git@github.com:tsg-newretail/newretail-ai-mall.git"
PR_URL = "https://github.com/tsg-newretail/newretail-ai-mall/pull/"

FAKE_GH = textwrap.dedent(r'''
    import json, os, re, sys
    data = json.load(open(os.environ["CARD_FAKE_DATA"]))
    with open(os.environ["CARD_FAKE_LOG"], "a") as fh:
        fh.write(json.dumps(sys.argv[1:]) + "\n")
    if data.get("fail"):
        sys.stderr.write("HTTP 502\n"); sys.exit(1)
    args = sys.argv[1:]
    if args[:2] == ["api", "graphql"]:
        query = args[3]
        out = {}
        for n in re.findall(r"n(\d+): issueOrPullRequest", query):
            if "... on Issue" in query:
                out["n" + n] = data["issues"].get(n)
            elif n in data["prs"]:
                out["n" + n] = data["prs"][n]
            else:
                out["n" + n] = {"__typename": "Issue"} if n in data["issues"] else None
        print(json.dumps({"data": {"repository": out}}))
    else:
        sha = re.search(r"compare/(\w+)\.\.\.main", args[1]).group(1)
        print(json.dumps({"status": data.get("main", {}).get(sha, "diverged")}))
''')


def pr(number, state="OPEN", draft=False, base="dev", title="fix(web): x", body="Refs #3018", sha=None):
    return {"__typename": "PullRequest", "number": number, "title": title, "body": body, "state": state,
            "isDraft": draft, "baseRefName": base, "mergeCommit": {"oid": sha} if sha else None,
            "repository": {"nameWithOwner": "tsg-newretail/newretail-ai-mall"}}


def card(number, status, prs, on_board=True):
    items = [{"project": {"number": 27}, "fieldValueByName": {"name": status}}] if on_board else []
    return {"__typename": "Issue", "number": number, "state": "OPEN", "projectItems": {"nodes": items},
            "timelineItems": {"nodes": [{"willCloseTarget": False, "source": p} for p in prs]}}


class CardStatusTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        (self.home / "tools").mkdir()
        (self.home / "tools" / "list_tools.py").write_text("def load_catalog(p): return []\n")
        self.repo = self.home / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "remote", "add", "origin", MALL], check=True)
        (self.home / "gh.py").write_text(FAKE_GH)
        gh = self.home / "gh"
        gh.write_text(f"#!/bin/sh\nexec {sys.executable} {self.home / 'gh.py'} \"$@\"\n")
        gh.chmod(0o755)
        self.log = self.home / "gh.log"
        self.data = {"prs": {}, "issues": {}, "main": {}}
        self.commands = ["gh pr ready 3194"]
        self.results = []

    def tearDown(self):
        self.temp.cleanup()

    def transcript(self):
        rows = [{"type": "user", "message": {"role": "user", "content": "請修 #3018"}}]
        for cmd in self.commands:
            rows.append({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}})
            rows.append({"type": "user", "message": {"content": [
                {"type": "tool_result", "content": self.results.pop(0) if self.results else "ok"}]}})
        path = self.home / "t.jsonl"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
        return path

    def hook(self, expected, reply="#3194 修好了", cwd=None, transcript=None):
        (self.home / "data.json").write_text(json.dumps(self.data, ensure_ascii=False))
        payload = {"cwd": str(cwd or self.repo), "session_id": "s", "hook_event_name": "Stop",
                   "transcript_path": str(transcript or self.transcript()), "last_assistant_message": reply}
        env = {**os.environ, "HOME": str(self.home), "CARD_CHECK_GH": str(self.home / "gh"),
               "CARD_FAKE_DATA": str(self.home / "data.json"), "CARD_FAKE_LOG": str(self.log),
               "PYTHONDONTWRITEBYTECODE": "1"}
        r = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload, ensure_ascii=False),
                           text=True, capture_output=True, timeout=30, env=env, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout) if r.stdout.strip() else {}
        self.assertEqual(out.get("decision"), "block" if expected == "block" else None, r.stdout)
        return out

    def calls(self):
        return [json.loads(x) for x in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_open_pr_while_card_shipped_blocks(self):
        # The 2026-10-16 incident: fix PR opened, card left in 待驗收.
        p = pr(3194)
        self.data["prs"]["3194"] = p
        self.data["issues"]["3018"] = card(3018, "待驗收", [p])
        out = self.hook("block")
        self.assertIn("#3018", out["reason"])
        self.assertIn("應為「進行中」", out["reason"])

    def test_open_pr_found_in_tool_output_blocks(self):
        self.commands = ["gh pr create --repo tsg-newretail/newretail-ai-mall --draft --title x"]
        self.results = [PR_URL + "3194"]
        p = pr(3194, draft=True)
        self.data["prs"]["3194"] = p
        self.data["issues"]["3018"] = card(3018, "待驗收", [p])
        self.hook("block", reply="開好了")

    def test_open_pr_and_card_working_allows(self):
        p = pr(3194)
        self.data["prs"]["3194"] = p
        self.data["issues"]["3018"] = card(3018, "進行中", [p])
        self.hook("allow")

    def test_merged_into_dev_not_main_needs_working(self):
        p = pr(3193, state="MERGED", sha="aaa111")
        self.data["prs"]["3193"] = p
        self.data["issues"]["3018"] = card(3018, "待驗收", [p])
        self.commands = ["gh pr view 3193"]
        self.hook("block", reply="#3193 已合 dev")
        self.data["issues"]["3018"] = card(3018, "進行中", [p])
        self.hook("allow", reply="#3193 已合 dev")

    def test_all_in_main_needs_shipped_status(self):
        p = pr(3182, state="MERGED", sha="bbb222")
        self.data["prs"]["3182"] = p
        self.data["main"]["bbb222"] = "ahead"
        self.data["issues"]["3018"] = card(3018, "進行中", [p])
        self.commands = ["gh pr view 3182"]
        out = self.hook("block", reply="#3182 上正式站了")
        self.assertIn("待驗收", out["reason"])
        for status in ["待驗收", "已上版", "已結束"]:
            with self.subTest(status=status):
                self.data["issues"]["3018"] = card(3018, status, [p])
                self.hook("allow", reply="#3182 上正式站了")
        compares = [c for c in self.calls() if "compare" in " ".join(c)]
        self.assertEqual(len(compares), 1, "a sha known to be in main must come from the cache")

    def test_one_open_pr_among_shipped_ones_needs_working(self):
        done = pr(3182, state="MERGED", sha="bbb222")
        fix = pr(3194)
        self.data["prs"].update({"3182": done, "3194": fix})
        self.data["main"]["bbb222"] = "identical"
        self.data["issues"]["3018"] = card(3018, "待驗收", [done, fix])
        self.hook("block")

    def test_draft_pr_reported_as_ready_blocks(self):
        p = pr(3194, draft=True)
        self.data["prs"]["3194"] = p
        self.data["issues"]["3018"] = card(3018, "進行中", [p])
        out = self.hook("block", reply="PR #3194 可以 review 了")
        self.assertIn("gh pr ready 3194", out["reason"])
        self.hook("allow", reply="PR #3194 還在寫，先開草稿")
        self.data["prs"]["3194"] = pr(3194, draft=False)
        self.hook("allow", reply="PR #3194 可以 review 了")

    def test_card_not_on_board_blocks(self):
        p = pr(3194)
        self.data["prs"]["3194"] = p
        self.data["issues"]["3018"] = card(3018, "", [p], on_board=False)
        out = self.hook("block")
        self.assertIn("不在看板", out["reason"])

    def test_release_and_loop_doc_prs_are_not_card_work(self):
        release = pr(3192, base="main", title="release: dev → main（#3018）")
        loop = pr(3195, title="docs(loops): 三卡收尾 (#3018)")
        self.data["prs"].update({"3192": release, "3195": loop})
        self.data["issues"]["3018"] = card(3018, "待驗收", [release, loop])
        self.commands = ["gh pr view 3192", "gh pr ready 3195"]
        self.hook("allow", reply="#3192 #3195 好了")

    def test_mention_without_link_line_is_not_a_link(self):
        p = pr(3194, body="見 #2803 的限制。\nRefs #3018")
        self.data["prs"]["3194"] = p
        self.data["issues"]["3018"] = card(3018, "進行中", [p])
        self.data["issues"]["2803"] = card(2803, "待驗收", [p])
        self.hook("allow")

    def test_unicode_text_after_number_still_links(self):
        p = pr(3194, title="fix(web): 退款視窗 #3018的文案", body="")
        self.data["prs"]["3194"] = p
        self.data["issues"]["3018"] = card(3018, "待驗收", [p])
        self.hook("block", reply="#3194修好了")

    def test_no_github_command_this_turn_makes_no_call(self):
        self.commands = ["ls"]
        self.hook("allow", reply="#3194 的說明")
        self.assertEqual(self.calls(), [])

    def test_earlier_turn_commands_do_not_count(self):
        path = self.transcript()
        with open(path, "a") as fh:
            fh.write(json.dumps({"type": "user", "message": {"role": "user", "content": "下一題"}}) + "\n")
        self.hook("allow", reply="好", transcript=path)
        self.assertEqual(self.calls(), [])

    def test_other_repo_bare_pr_number_is_ignored(self):
        other = self.home / "other"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        subprocess.run(["git", "-C", str(other), "remote", "add", "origin", "git@github.com:x/y.git"], check=True)
        self.hook("allow", reply="#3194 好了", cwd=other)
        self.assertEqual(self.calls(), [])

    def test_github_failure_is_a_fault_not_a_block(self):
        self.data["fail"] = True
        out = self.hook("allow")
        self.assertIn("卡片狀態檢查", out.get("systemMessage", ""))
        self.assertIn("檢查器故障", out.get("systemMessage", ""))


if __name__ == "__main__":
    unittest.main()
