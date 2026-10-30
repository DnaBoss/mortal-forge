import errno
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "manager", Path(__file__).with_name("manager.py")
)
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.now = {
            "id": 1,
            "cold": 1024 * m.MIB,
            "anon": 4096 * m.MIB,
            "refault": 0,
            "psi": 0,
        }
        self.before = dict(self.now)

    def plan(self, free=4096 * m.MIB, budget=256 * m.MIB):
        return m.amount(self.now, self.before, free, budget)[0]

    def test_reclaims_without_pressure(self):
        self.assertEqual(self.plan(), 128 * m.MIB)

    def test_first_observation_does_not_reclaim(self):
        self.before = None
        self.assertEqual(self.plan(), 0)

    def test_new_cgroup_identity_does_not_reuse_history(self):
        self.now["id"] = 2
        self.assertEqual(self.plan(), 0)

    def test_refault_stops_reclaim(self):
        self.now["refault"] = 1
        self.assertEqual(self.plan(), 0)

    def test_pressure_is_only_a_brake(self):
        self.now["psi"] = 1
        self.assertEqual(self.plan(), 0)

    def test_swap_reserve_and_cycle_budget(self):
        self.assertEqual(self.plan(free=1024 * m.MIB), 0)
        self.assertEqual(self.plan(free=1040 * m.MIB), 16 * m.MIB)
        self.assertEqual(self.plan(budget=32 * m.MIB), 32 * m.MIB)
        self.assertEqual(self.plan(budget=0), 0)

    def test_cold_reserve(self):
        self.now["cold"] = 64 * m.MIB
        self.assertEqual(self.plan(), 0)

    def test_warmup_uses_smaller_cold_value(self):
        self.before["cold"] = 80 * m.MIB
        self.assertEqual(self.plan(), 16 * m.MIB)

    def test_reclaim_anon_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            self.assertEqual(m.reclaim(p, 16 * m.MIB), 0)
            self.assertEqual(
                (p / "memory.reclaim").read_text(), "16777216 swappiness=max"
            )

    def test_partial_reclaim_is_not_success(self):
        with patch.object(
            Path, "write_text", side_effect=OSError(errno.EAGAIN, "partial")
        ):
            self.assertEqual(m.reclaim(Path("/unused"), 16 * m.MIB), 2)

    def test_permission_failure_is_visible(self):
        with patch.object(
            Path, "write_text", side_effect=PermissionError(errno.EACCES, "denied")
        ):
            self.assertEqual(m.reclaim(Path("/unused"), 16 * m.MIB), 1)

    def test_disjoint_groups_include_services(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in (
                "app.slice/parent.scope",
                "app.slice/parent.scope/child.scope",
                "app.slice/worker.service",
            ):
                path = root / name
                path.mkdir(parents=True, exist_ok=True)
                (path / "memory.reclaim").touch()
            self.assertEqual(
                {p.name for p in m.groups(root)}, {"parent.scope", "worker.service"}
            )

    def test_disk_swap_and_backing_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            swaps = root / "swaps"
            block = root / "zram0"
            block.mkdir()
            swaps.write_text(
                "Filename Type Size Used Priority\n/dev/zram0 partition 100 0 100\n"
            )
            (block / "backing_dev").write_text("none\n")
            self.assertEqual(m.swap_reason(swaps, root), "")
            (block / "backing_dev").write_text("/dev/nvme0n1p3\n")
            self.assertTrue(m.swap_reason(swaps, root))
            swaps.write_text(
                "Filename Type Size Used Priority\n/swapfile file 100 0 0\n"
            )
            self.assertTrue(m.swap_reason(swaps, root))
            swaps.write_text("Filename Type Size Used Priority\n")
            self.assertTrue(m.swap_reason(swaps, root))


class CycleTests(unittest.TestCase):
    def run_cycle(self, dry=False, reason="", code=0):
        paths = [m.ROOT / f"test-{i}.service" for i in range(3)]
        value = {
            "id": 1,
            "cold": 1024 * m.MIB,
            "anon": 4096 * m.MIB,
            "refault": 0,
            "psi": 0,
            "swap": 0,
        }
        previous = {str(p.relative_to(m.ROOT)): value for p in paths}
        mem = {"MemTotal": 8192, "MemAvailable": 4096, "SwapFree": 4096 * 1024}
        with (
            patch.object(m, "numbers", return_value=mem),
            patch.object(m, "swap_reason", return_value=reason),
            patch.object(m, "pressure", return_value=0),
            patch.object(m, "model_status", return_value=[]),
            patch.object(m, "groups", return_value=paths),
            patch.object(m, "snapshot", return_value=value),
            patch.object(m.subprocess, "run") as worker,
        ):
            worker.return_value.returncode = code
            worker.return_value.stdout = ""
            worker.return_value.stderr = ""
            result, _ = m.cycle(previous, dry=dry)
            return result, worker.call_count

    def test_cycle_total_is_bounded(self):
        result, calls = self.run_cycle()
        self.assertEqual(calls, 2)
        self.assertEqual(result["requested"], 256 * m.MIB)
        self.assertEqual(result["swap_free"], 4096 * m.MIB)

    def test_dry_run_never_writes(self):
        result, calls = self.run_cycle(dry=True)
        self.assertEqual(calls, 0)
        self.assertGreater(result["requested"], 0)

    def test_swap_safety_brake_blocks_all_writes(self):
        result, calls = self.run_cycle(reason="磁碟交換")
        self.assertEqual(calls, 0)
        self.assertEqual(result["requested"], 0)

    def test_worker_error_is_preserved(self):
        result, calls = self.run_cycle(code=1)
        self.assertEqual(calls, 2)
        self.assertEqual(result["groups"][0]["returncode"], 1)


if __name__ == "__main__":
    unittest.main()
