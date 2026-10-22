import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import cash_rule_delivery as d


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = patch.object(d, "ROOT", self.base / "state")
        self.root.start()
        self.cp = self.base / "t.checkpoints.jsonl"
        self.plan_path = self.base / "t.delivery.json"
        self.version = self.art("artifact.bin", "version 1")
        self.validation = self.art(
            "validation.json",
            {
                "version_sha256": self.version["sha256"],
                "checks": [{"name": "unit", "result": "pass"}],
            },
        )
        deploy = self.art("deploy.sh", "#!/bin/sh\nprintf deployed > deployed.txt\n")
        readback = self.art(
            "readback.sh",
            '#!/usr/bin/env python3\nimport json,os\nprint(json.dumps({"version_sha256":os.environ["CASH_DELIVERY_SHA256"],"result":"pass","checks":[{"name":"functional","result":"pass"}]}))\n',
        )
        source = self.art("user.txt", "Only this isolated local fixture is authorized.")
        grant = self.art(
            "grant.json",
            {
                "authorized": True,
                "project": str(self.base),
                "environment": "fixture",
                "artifact_sha256": self.version["sha256"],
                "deploy": deploy,
                "readback": readback,
                "source": source,
            },
        )
        self.spec = {
            "kind": "milestone",
            "environment": "fixture",
            "artifact": self.version,
            "validation": self.validation,
            "authorization": grant,
            "deploy": deploy,
            "readback": readback,
            "timeout_seconds": 2,
        }
        self.plan = {
            "schema_version": 1,
            "task": "test",
            "project": str(self.base),
            "steps": {
                "S1": self.spec,
                "S2": {"kind": "internal", "reason": "Independent analysis"},
            },
        }
        self.save()

    def tearDown(self):
        self.root.stop()
        self.tmp.cleanup()

    def art(self, name, value):
        data = json.dumps(value).encode() if isinstance(value, dict) else value.encode()
        p = self.base / name
        p.write_bytes(data)
        return {"path": name, "sha256": hashlib.sha256(data).hexdigest()}

    def save(self):
        self.plan_path.write_text(json.dumps(self.plan))

    def gate(self, state="DONE", task_state="RUNNING", step="S1", checks=None):
        return d.gate(self.cp, "test", step, task_state, state, checks or [])

    def submit(self):
        with patch.object(
            d.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
        ) as run:
            d.submit(self.plan_path, self.plan, "S1")
        folder, job, state = d.job_for(self.plan_path, self.plan, "S1")
        return folder, job, state, run

    def test_no_plan_blocks_done_but_allows_independent_running(self):
        self.plan_path.unlink()
        self.assertIsNotNone(self.gate())
        self.assertIsNone(self.gate(state="RUNNING", step="S2"))

    def test_undeployed_blocks_done(self):
        self.assertIsNotNone(self.gate())

    def test_ready_submits_automatically_without_waiting(self):
        with patch.object(
            d.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
        ) as run:
            self.assertIsNone(self.gate(state="VALIDATING", checks=["unit=pass"]))
            argv = run.call_args.args[0]
            self.assertIn("--no-block", argv)
            self.assertIn("--property=Type=oneshot", argv)
            self.assertIn("/usr/bin/python3", argv)
        self.assertIsNone(self.gate(state="RUNNING", step="S2"))
        self.assertIsNotNone(self.gate())

    def test_same_version_submitted_once(self):
        self.submit()
        with patch.object(d.subprocess, "run") as run:
            d.submit(self.plan_path, self.plan, "S1")
            self.assertFalse(
                any(c.args[0][0] == "systemd-run" for c in run.call_args_list)
            )

    def test_real_worker_readback_and_completion(self):
        folder, _, _, _ = self.submit()
        self.assertEqual(d.worker(folder), 0)
        self.assertIsNone(self.gate())
        self.assertIsNone(self.gate(task_state="COMPLETE", step="S2"))
        self.assertEqual(d.worker(folder), 1)

    def test_changed_artifact_rejected(self):
        (self.base / "artifact.bin").write_text("version 2")
        self.assertIsNotNone(self.gate(state="VALIDATING", checks=["unit=pass"]))

    def test_wrong_version_validation_rejected(self):
        self.spec["validation"] = self.art(
            "validation.json",
            {"version_sha256": "wrong", "checks": [{"name": "x", "result": "pass"}]},
        )
        self.save()
        self.assertIsNotNone(self.gate(state="VALIDATING", checks=["unit=pass"]))

    def test_skipped_validation_rejected(self):
        self.spec["validation"] = self.art(
            "validation.json",
            {
                "version_sha256": self.version["sha256"],
                "checks": [{"name": "x", "result": "skip"}],
            },
        )
        self.save()
        self.assertIsNotNone(self.gate(state="VALIDATING", checks=["unit=pass"]))

    def test_wrong_environment_authorization_rejected(self):
        self.spec["environment"] = "production"
        self.save()
        with patch.object(d.subprocess, "run") as run:
            self.assertIsNotNone(self.gate(state="VALIDATING", checks=["unit=pass"]))
            self.assertFalse(
                any(c.args[0][0] == "systemd-run" for c in run.call_args_list)
            )

    def test_failure_no_retry_and_other_work_allowed(self):
        folder, job, _, _ = self.submit()
        Path(job["deploy"]).write_text("#!/bin/sh\nexit 7\n")
        job["adapter_hashes"]["deploy"] = d.digest(job["deploy"])
        d.write(folder / "job.json", job)
        self.assertEqual(d.worker(folder), 1)
        self.assertEqual(d.read(folder / "state.json")["status"], "failed")
        self.assertIsNone(self.gate(state="RUNNING", step="S2"))
        self.assertIsNotNone(self.gate(task_state="COMPLETE", step="S2"))
        with patch.object(d.subprocess, "run") as run:
            d.submit(self.plan_path, self.plan, "S1")
            self.assertFalse(
                any(c.args[0][0] == "systemd-run" for c in run.call_args_list)
            )

    def test_wrong_readback_blocks_completion(self):
        folder, job, _, _ = self.submit()
        Path(job["readback"]).write_text(
            '#!/bin/sh\nprintf \'{"version_sha256":"wrong","result":"pass"}\'\n'
        )
        job["adapter_hashes"]["readback"] = d.digest(job["readback"])
        d.write(folder / "job.json", job)
        self.assertEqual(d.worker(folder), 1)
        self.assertIsNotNone(self.gate())

    def test_dispatch_timeout_never_resubmits(self):
        with patch.object(
            d.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("systemd-run", 10),
        ):
            self.assertIsNone(self.gate(state="VALIDATING", checks=["unit=pass"]))
            folder, _, state = d.job_for(self.plan_path, self.plan, "S1")
            self.assertEqual(state["status"], "dispatch_unknown")
        with patch.object(d.subprocess, "run") as run:
            d.submit(self.plan_path, self.plan, "S1")
            self.assertFalse(
                any(c.args[0][0] == "systemd-run" for c in run.call_args_list)
            )

    def test_changed_saved_readback_blocks_completion(self):
        folder, _, _, _ = self.submit()
        self.assertEqual(d.worker(folder), 0)
        (folder / "readback.stdout").write_text("{}")
        self.assertIsNotNone(self.gate())

    def test_pending_other_milestone_blocks_task_completion(self):
        self.assertIsNotNone(self.gate(task_state="COMPLETE", step="S2"))
        self.assertIsNone(self.gate(step="S2"))

    def test_internal_requires_reason(self):
        self.plan["steps"]["S2"]["reason"] = ""
        self.save()
        self.assertIsNotNone(self.gate(step="S2"))

    def test_registered_point_cannot_be_downgraded_or_removed(self):
        self.assertIsNotNone(self.gate())
        original = dict(self.plan["steps"])
        for action in ("downgrade", "remove"):
            self.plan["steps"] = dict(original)
            if action == "downgrade":
                self.plan["steps"]["S1"] = {
                    "kind": "internal",
                    "reason": "hide release",
                }
            else:
                del self.plan["steps"]["S1"]
            self.save()
            self.assertIsNotNone(self.gate(task_state="COMPLETE", step="S2"))

    def test_original_files_can_change_after_snapshot(self):
        folder, _, _, _ = self.submit()
        (self.base / "artifact.bin").write_text("next development version")
        (self.base / "grant.json").unlink()
        self.assertEqual(d.worker(folder), 0)
        self.assertIsNone(self.gate())

    def test_changed_version_cannot_hide_pending_job(self):
        self.submit()
        self.spec["artifact"] = self.art("v2.bin", "version 2")
        self.save()
        self.assertIsNotNone(self.gate())

    def test_next_dispatch_blocked_when_previous_dispatch_unknown(self):
        with patch.object(
            d.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("systemd-run", 10),
        ):
            self.assertIsNone(self.gate(state="VALIDATING", checks=["unit=pass"]))
        # Use a second task/version in the same project and environment.
        previous = dict(self.spec)
        self.spec = dict(previous)
        self.spec["artifact"] = self.art("v2.bin", "version 2")
        self.spec["validation"] = self.art(
            "validation2.json",
            {
                "version_sha256": self.spec["artifact"]["sha256"],
                "checks": [{"name": "x", "result": "pass"}],
            },
        )
        grant = d.read(self.base / "grant.json")
        grant["artifact_sha256"] = self.spec["artifact"]["sha256"]
        self.spec["authorization"] = self.art("grant2.json", grant)
        self.plan["steps"]["S3"] = self.spec
        self.save()
        with patch.object(d.subprocess, "run") as run:
            self.assertIsNone(
                self.gate(state="VALIDATING", step="S3", checks=["x=pass"])
            )
            _, _, state = d.job_for(self.plan_path, self.plan, "S3")
            self.assertEqual(state["status"], "prepared")
            self.assertFalse(
                any(c.args[0][0] == "systemd-run" for c in run.call_args_list)
            )

    def test_readback_timeout_records_failure(self):
        folder, job, _, _ = self.submit()
        with patch.object(
            d.subprocess, "run", side_effect=subprocess.TimeoutExpired("adapter", 2)
        ):
            self.assertEqual(d.worker(folder), 1)
        self.assertEqual(d.read(folder / "state.json")["status"], "failed")

    def test_checkpoint_writer_rejects_without_changing_history(self):
        import cash_rule_checkpoint as cp

        args = [
            str(self.cp),
            "--task",
            "test",
            "--step",
            "S1",
            "--target",
            "fixture",
            "--executor",
            "codex",
        ]
        with patch.object(
            sys,
            "argv",
            ["checkpoint"]
            + args
            + ["--task-state", "PLANNED", "--step-state", "READY"],
        ):
            self.assertEqual(cp.main(), 0)
        with patch.object(
            sys,
            "argv",
            ["checkpoint"]
            + args
            + [
                "--task-state",
                "RUNNING",
                "--step-state",
                "RUNNING",
                "--acceptance",
                "A1",
            ],
        ):
            self.assertEqual(cp.main(), 0)
        with patch.object(d.subprocess, "run", wraps=subprocess.run):
            # Empty checks records validation progress without initiating deployment.
            with patch.object(
                sys,
                "argv",
                ["checkpoint"]
                + args
                + [
                    "--task-state",
                    "VALIDATING",
                    "--step-state",
                    "VALIDATING",
                    "--acceptance",
                    "A1",
                ],
            ):
                self.assertEqual(cp.main(), 0)
        before = self.cp.read_bytes()
        with patch.object(
            sys,
            "argv",
            ["checkpoint"]
            + args
            + [
                "--task-state",
                "RUNNING",
                "--step-state",
                "DONE",
                "--acceptance",
                "A1",
                "--check",
                "fixture=pass",
                "--neg",
                "fixture=>fixture",
            ],
        ):
            self.assertEqual(cp.main(), 1)
        self.assertEqual(self.cp.read_bytes(), before)

    def test_dispatch_timeout_does_not_overwrite_worker_completion(self):
        def complete_then_timeout(*args, **kwargs):
            folder, _, _ = d.job_for(self.plan_path, self.plan, "S1")
            d.set_state(folder, {"status": "deployed", "readback_sha256": "fixture"})
            raise subprocess.TimeoutExpired("systemd-run", 10)

        with patch.object(d.subprocess, "run", side_effect=complete_then_timeout):
            result = d.submit(self.plan_path, self.plan, "S1")
        self.assertEqual(result["status"], "deployed")

    def test_prepared_job_resumes_first_dispatch(self):
        folder, _, _, _ = self.submit()
        d.set_state(folder, {"status": "prepared"})
        with patch.object(
            d.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
        ) as run:
            d.submit(self.plan_path, self.plan, "S1")
        self.assertEqual(
            sum(c.args[0][0] == "systemd-run" for c in run.call_args_list), 1
        )

    def test_uncertain_dispatch_queries_unit_before_first_dispatch(self):
        folder, _, _, _ = self.submit()
        d.set_state(folder, {"status": "dispatch_unknown"})

        def respond(argv, **kwargs):
            if argv[0] == "systemctl":
                return subprocess.CompletedProcess(
                    argv, 0, stdout="LoadState=not-found\nActiveState=inactive\n"
                )
            return subprocess.CompletedProcess(argv, 0)

        with patch.object(d.subprocess, "run", side_effect=respond) as run:
            d.submit(self.plan_path, self.plan, "S1")
        self.assertEqual(
            [c.args[0][0] for c in run.call_args_list], ["systemctl", "systemd-run"]
        )

    def test_failed_job_requires_exact_retry_authorization(self):
        folder, _, _, _ = self.submit()
        d.set_state(folder, {"status": "failed"})
        wrong = self.art("retry.json", {"authorized": True, "job": "other"})
        with self.assertRaises(ValueError):
            d.retry(
                folder,
                {"path": str(self.base / wrong["path"]), "sha256": wrong["sha256"]},
            )
        grant = self.art(
            "retry.json",
            {
                "authorized": True,
                "job": folder.name,
                "source": self.art("retry-user.txt", "Retry isolated fixture once"),
            },
        )
        with (
            patch.object(d, "service_state", return_value={"ActiveState": "failed"}),
            patch.object(
                d.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
            ),
        ):
            result = d.retry(
                folder,
                {"path": str(self.base / grant["path"]), "sha256": grant["sha256"]},
            )
        self.assertEqual(result["status"], "dispatching")
        self.assertIn("-retry-1", d.read(folder / "job.json")["unit"])
        self.assertTrue((folder / "attempt-1/state.json").exists())

    def test_crash_before_dispatch_cannot_let_newer_version_overtake(self):
        with patch.object(d, "launch", return_value={"status": "prepared"}):
            d.submit(self.plan_path, self.plan, "S1")
        first_folder, _, _ = d.job_for(self.plan_path, self.plan, "S1")
        second = dict(self.spec)
        second["artifact"] = self.art("v2.bin", "version 2")
        second["validation"] = self.art(
            "v2-validation.json",
            {
                "version_sha256": second["artifact"]["sha256"],
                "checks": [{"name": "v2", "result": "pass"}],
            },
        )
        grant = d.read(self.base / "grant.json")
        grant["artifact_sha256"] = second["artifact"]["sha256"]
        second["authorization"] = self.art("v2-grant.json", grant)
        self.plan["steps"]["S3"] = second
        self.save()
        with patch.object(d.subprocess, "run") as run:
            result = d.submit(self.plan_path, self.plan, "S3")
            self.assertEqual(result["status"], "prepared")
            self.assertFalse(
                any(c.args[0][0] == "systemd-run" for c in run.call_args_list)
            )
        with patch.object(
            d.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
        ):
            d.submit(self.plan_path, self.plan, "S1")
        self.assertEqual(d.worker(first_folder), 0)
        with patch.object(
            d.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
        ) as run:
            result = d.submit(self.plan_path, self.plan, "S3")
            self.assertEqual(result["status"], "dispatching")
            self.assertEqual(
                sum(c.args[0][0] == "systemd-run" for c in run.call_args_list), 1
            )
        # Even an explicit retry cannot roll the environment back after a newer job entered deployment.
        d.set_state(first_folder, {"status": "failed"})
        with self.assertRaises(ValueError):
            d.ordering_blocker(d.read(first_folder / "job.json"))


if __name__ == "__main__":
    unittest.main()
