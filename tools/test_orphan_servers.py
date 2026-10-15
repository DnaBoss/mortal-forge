import unittest

import orphan_servers as osv

H = 3600
SYSTEMD = {1634}


def proc(pid, ppid, comm, args, start, ports=(), cwd="/w"):
    return osv.Proc(pid, ppid, "", comm, args, start, cwd, 0, set(ports))


class LooksLikeDevServerTest(unittest.TestCase):
    def test_matches_known_dev_servers(self):
        self.assertTrue(osv.looks_like_dev_server("next-server (v14.2.35)", "next-server (v14.2.35)"))
        self.assertTrue(osv.looks_like_dev_server("node", "/usr/bin/node --import tsx src/index.ts"))
        self.assertTrue(osv.looks_like_dev_server("node", "node /x/apps/web/node_modules/.bin/next dev -p 3120"))

    def test_ignores_other_long_running_processes(self):
        self.assertFalse(osv.looks_like_dev_server("codex", "codex app-server --listen unix://"))
        self.assertFalse(osv.looks_like_dev_server("orca-ide", "/opt/orca/orca-ide daemon-entry.js"))
        self.assertFalse(osv.looks_like_dev_server("node", "node playwright-mcp"))
        self.assertFalse(osv.looks_like_dev_server("postgres", "postgres -D /data"))


class DecideTest(unittest.TestCase):
    def setUp(self):
        self.now = 1_000_000.0
        self.old = self.now - 30 * H

    def decide(self, procs, inbound=(), activity=None, protected=()):
        return osv.decide({p.pid: p for p in procs}, SYSTEMD, set(inbound),
                          activity or {}, self.now, 2 * H, set(protected))

    def test_orphaned_idle_server_without_clients_is_stopped(self):
        [d] = self.decide([proc(10, 1634, "node", "node --import tsx src/index.ts", self.old, [4101])])
        self.assertEqual((d.action, d.reason, d.ports, d.group), ("stop", "orphan_idle", [4101], [10]))
        self.assertAlmostEqual(d.idle_hours, 30.0)

    def test_server_whose_parent_is_alive_is_kept(self):
        shell = proc(5, 1634, "zsh", "zsh", self.old)
        server = proc(10, 5, "node", "node --import tsx src/index.ts", self.old, [4101])
        decisions = self.decide([shell, server])
        self.assertEqual([(d.pid, d.action, d.reason) for d in decisions], [(10, "keep", "parent_alive")])

    def test_server_with_an_inbound_client_is_kept(self):
        [d] = self.decide([proc(10, 1634, "node", "node --import tsx src/index.ts", self.old, [4101])],
                          inbound=[4101])
        self.assertEqual((d.action, d.reason), ("keep", "has_clients"))

    def test_outgoing_pool_connections_do_not_count_as_clients(self):
        # Established connections to Redis/Postgres have local ephemeral ports, not 4101.
        [d] = self.decide([proc(10, 1634, "node", "node --import tsx src/index.ts", self.old, [4101])],
                          inbound=[51234, 51235])
        self.assertEqual(d.action, "stop")

    def test_recent_activity_keeps_server(self):
        [d] = self.decide([proc(10, 1634, "node", "node --import tsx src/index.ts", self.old, [4101])],
                          activity={10: self.now - 1 * H})
        self.assertEqual((d.action, d.reason), ("keep", "recent"))

    def test_recently_started_server_is_kept_even_without_activity_record(self):
        [d] = self.decide([proc(10, 1634, "node", "node --import tsx src/index.ts", self.now - 0.5 * H, [4101])])
        self.assertEqual((d.action, d.reason), ("keep", "recent"))

    def test_wrapper_and_child_form_one_group_and_child_port_counts(self):
        wrapper = proc(20, 1634, "node", "node /x/node_modules/.bin/next dev", self.old)
        child = proc(21, 20, "next-server (v14.2.35)", "next-server (v14.2.35)", self.old, [3120])
        [d] = self.decide([wrapper, child])
        self.assertEqual((d.action, d.pid, d.group, d.ports), ("stop", 20, [20, 21], [3120]))
        [d] = self.decide([wrapper, child], inbound=[3120])
        self.assertEqual((d.action, d.reason), ("keep", "has_clients"))

    def test_protected_pid_in_group_is_kept(self):
        [d] = self.decide([proc(10, 1634, "node", "node --import tsx src/index.ts", self.old, [4101])],
                          protected=[10])
        self.assertEqual((d.action, d.reason), ("keep", "protected"))

    def test_non_dev_server_orphans_are_not_touched(self):
        decisions = self.decide([proc(30, 1634, "codex", "codex app-server --listen unix://", self.old)])
        self.assertEqual(decisions, [])


if __name__ == "__main__":
    unittest.main()
