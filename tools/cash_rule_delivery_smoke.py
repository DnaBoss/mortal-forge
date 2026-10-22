"""Opt-in, local-only systemd fixture: ordering, idempotence and nonblocking work."""

import copy
import json
from pathlib import Path
import sys
import subprocess
import time

import cash_rule_delivery as d
from test_cash_rule_delivery import DeliveryTests


def main():
    fixture = DeliveryTests()
    fixture.setUp()
    units = []
    try:
        fixture.spec["timeout_seconds"] = 10
        trace = fixture.base / "order.txt"
        # No network, repository mutation or real deployment; only fixture files.
        first = (
            '#!/bin/sh\nprintf "start1\\n" >> '
            + str(trace)
            + '\nsleep 2\nprintf "end1\\n" >> '
            + str(trace)
            + "\n"
        )
        fixture.spec["deploy"] = fixture.art("deploy.sh", first)
        grant = d.read(fixture.base / "grant.json")
        grant["deploy"] = fixture.spec["deploy"]
        fixture.spec["authorization"] = fixture.art("grant.json", grant)
        fixture.save()
        started = time.monotonic()
        error = fixture.gate(state="VALIDATING", checks=["unit=pass"])
        elapsed = time.monotonic() - started
        if error or elapsed >= 1.5:
            raise RuntimeError("Submission blocked: " + str(error))
        first_folder, _, _ = d.job_for(fixture.plan_path, fixture.plan, "S1")
        units.append(d.read(first_folder / "job.json")["unit"])
        if fixture.gate(state="RUNNING", step="S2") is not None:
            raise RuntimeError("Independent development was blocked")
        if fixture.gate() is None:
            raise RuntimeError("Undeployed milestone was accepted")
        second = copy.deepcopy(fixture.spec)
        second["artifact"] = fixture.art("v2.bin", "version 2")
        second["validation"] = fixture.art(
            "v2-validation.json",
            {
                "version_sha256": second["artifact"]["sha256"],
                "checks": [{"name": "fixture", "result": "pass"}],
            },
        )
        second["deploy"] = fixture.art(
            "deploy2.sh", '#!/bin/sh\nprintf "start2\\nend2\\n" >> ' + str(trace) + "\n"
        )
        grant.update(
            artifact_sha256=second["artifact"]["sha256"], deploy=second["deploy"]
        )
        second["authorization"] = fixture.art("grant2.json", grant)
        fixture.plan["steps"]["S3"] = second
        fixture.save()
        error = fixture.gate(state="VALIDATING", step="S3", checks=["fixture=pass"])
        if error:
            raise RuntimeError(error)
        second_folder, _, _ = d.job_for(fixture.plan_path, fixture.plan, "S3")
        units.append(d.read(second_folder / "job.json")["unit"])
        # Duplicate submit must not execute another adapter.
        d.submit(fixture.plan_path, fixture.plan, "S1")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            states = [
                d.read(f / "state.json")["status"]
                for f in (first_folder, second_folder)
            ]
            if states == ["deployed", "deployed"]:
                break
            if any(s in ("failed", "dispatch_unknown") for s in states):
                raise RuntimeError(str(states))
            time.sleep(0.1)
        else:
            raise RuntimeError("Fixture jobs did not finish")
        observed = trace.read_text().splitlines()
        if observed != ["start1", "end1", "start2", "end2"]:
            raise RuntimeError("Deployment ordering violated: " + str(observed))
        if fixture.gate(task_state="COMPLETE", step="S2") is not None:
            raise RuntimeError("Actual delivery could not complete")
        result = {
            "result": "pass",
            "submit_seconds": round(elapsed, 3),
            "order": observed,
            "independent_work": "pass",
            "early_completion_rejected": True,
            "duplicate_executions": 0,
            "real_systemd_jobs": 2,
            "production_touched": False,
        }
        if len(sys.argv) == 2:
            Path(sys.argv[1]).write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
    finally:
        for unit in units:
            subprocess.run(
                ["systemctl", "--user", "stop", unit], capture_output=True, timeout=10
            )
        fixture.tearDown()


if __name__ == "__main__":
    main()
