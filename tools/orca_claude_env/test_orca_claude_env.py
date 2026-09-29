import unittest

from orca_claude_env import classify, parse_environ, resume_id, verdict

DAEMON_ARGV = ["/opt/Orca/orca-ide", "/opt/Orca/resources/app.asar.unpacked/out/main/daemon-entry.js", "--socket", "x"]


def snap(base_url, probe):
    return {"daemons": [{"pid": 7, "base_url": base_url}], "base_url_probe": probe}


class Tests(unittest.TestCase):
    def test_parse_environ(self):
        self.assertEqual(parse_environ(b"A=1\0B=x=y\0junk\0"), {"A": "1", "B": "x=y"})

    def test_classify(self):
        self.assertEqual(classify(DAEMON_ARGV, {}), "orca_daemon")
        self.assertEqual(classify(["/tmp/.mount_orca-abc/orca-ide"], {}), "orca_gui")
        self.assertEqual(classify(["claude", "--resume", "id"], {"ORCA_TERMINAL_HANDLE": "t"}), "orca_claude")
        self.assertEqual(classify(["claude"], {}), "")
        # A plain terminal session may inherit unrelated ORCA_* vars; it is not an ORCA tab.
        self.assertEqual(classify(["claude"], {"ORCA_AGENT_TEAMS_SHIM_BIN": "x"}), "")
        self.assertEqual(classify(["/tmp/.mount_orca-abc/orca-ide", "--type=gpu-process"], {}), "")

    def test_resume_id(self):
        self.assertEqual(resume_id(["claude", "--resume", "abc"]), "abc")
        self.assertEqual(resume_id(["claude"]), "")

    def test_stale_when_gateway_404(self):
        v = verdict(snap("http://127.0.0.1:18080", {"status": 404}))
        self.assertEqual(v["code"], "stale_base_url")
        self.assertEqual(v["stale_daemon_pids"], [7])

    def test_stale_when_gateway_down(self):
        self.assertEqual(verdict(snap("http://x", {"status": None, "error": "refused"}))["code"], "stale_base_url")

    def test_not_stale_when_gateway_answers(self):
        v = verdict(snap("http://x", {"status": 401}))
        self.assertEqual(v["code"], "base_url_set_gateway_answers")
        self.assertEqual(v["stale_daemon_pids"], [])

    def test_clean(self):
        self.assertEqual(verdict(snap("", None))["code"], "clean")
        self.assertEqual(verdict({"daemons": [], "base_url_probe": None})["code"], "no_daemon")


if __name__ == "__main__":
    unittest.main()
