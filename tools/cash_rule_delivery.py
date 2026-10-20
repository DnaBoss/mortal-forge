#!/usr/bin/env python3
"""Durable, bounded delivery jobs for checkpoint transitions. No automatic retry."""

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path.home() / ".local/state/cash-rule-delivery"
KINDS = {"internal", "stage", "feature", "milestone"}
LIMIT = 1024 * 1024


def read(path):
    path = Path(path)
    if path.stat().st_size > LIMIT:
        raise ValueError("JSON exceeds size limit")
    return json.loads(path.read_text())


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path, data):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def reference(ref, base):
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise ValueError("Evidence requires path and sha256")
    path = (base / ref["path"]).resolve()
    if not path.is_file() or digest(path) != ref["sha256"]:
        raise ValueError("Evidence is missing or changed")
    return path


def verified_json(ref, base):
    path = (base / ref["path"]).resolve()
    if path.stat().st_size > LIMIT:
        raise ValueError("JSON exceeds size limit")
    data = path.read_bytes()
    if len(data) > LIMIT or hashlib.sha256(data).hexdigest() != ref["sha256"]:
        raise ValueError("Evidence is missing or changed")
    return json.loads(data)


def plan_for(checkpoints, task):
    path = Path(str(checkpoints).replace(".checkpoints.jsonl", ".delivery.json"))
    if path == Path(checkpoints):
        path = Path(str(checkpoints) + ".delivery.json")
    plan = read(path)
    if plan.get("schema_version") != 1 or plan.get("task") != task:
        raise ValueError("Delivery plan does not match task")
    steps = plan.get("steps")
    if not isinstance(steps, dict) or not steps or len(steps) > 128:
        raise ValueError("Delivery plan requires 1..128 steps")
    for spec in steps.values():
        if spec.get("kind") not in KINDS:
            raise ValueError("Every step needs a delivery classification")
        if spec["kind"] == "internal" and not str(spec.get("reason", "")).strip():
            raise ValueError(
                "Internal steps need a reason why they are not a delivery point"
            )
    identity = hashlib.sha256(
        (str(Path(checkpoints).resolve()) + "\n" + task).encode()
    ).hexdigest()
    registry = ROOT / "plans" / (identity + ".json")
    with locked(ROOT / "plans.lock"):
        session_ids = {
            os.environ[k]
            for k in ("CODEX_SESSION_ID", "CODEX_THREAD_ID", "CLAUDE_SESSION_ID")
            if os.environ.get(k)
        }
        kinds = {sid: spec["kind"] for sid, spec in steps.items()}
        if registry.exists():
            previous = read(registry)
            session_ids.update(previous.get("session_ids", []))
            if previous["project"] != str(Path(plan["project"]).resolve()):
                raise ValueError("Registered project cannot change")
            if any(kinds.get(sid) != kind for sid, kind in previous["kinds"].items()):
                raise ValueError(
                    "Registered delivery points cannot be removed or downgraded"
                )
        registry.parent.mkdir(parents=True, exist_ok=True)
        write(
            registry,
            {
                "checkpoints": str(Path(checkpoints).resolve()),
                "task": task,
                "project": str(Path(plan["project"]).resolve()),
                "kinds": kinds,
                "session_ids": sorted(session_ids),
            },
        )
    return path, plan


def prepare(plan_path, plan, step):
    spec = plan["steps"][step]
    base = plan_path.parent
    artifact = reference(spec["artifact"], base)
    validation = verified_json(spec["validation"], base)
    version = spec["artifact"]["sha256"]
    if validation.get("version_sha256") != version:
        raise ValueError("Validation is for another version")
    checks = validation.get("checks")
    if (
        not isinstance(checks, list)
        or not checks
        or any(
            not isinstance(c, dict) or not c.get("name") or c.get("result") != "pass"
            for c in checks
        )
    ):
        raise ValueError("Necessary checks must all pass")
    grant = verified_json(spec["authorization"], base)
    project = str(Path(plan["project"]).resolve())
    environment = spec["environment"]
    if not isinstance(environment, str) or not re.fullmatch(
        r"[a-zA-Z0-9_-]{1,64}", environment
    ):
        raise ValueError("Invalid environment")
    if (
        grant.get("authorized") is not True
        or grant.get("project") != project
        or grant.get("environment") != environment
        or grant.get("artifact_sha256") != version
    ):
        raise ValueError(
            "Authorization does not cover this project, environment and version"
        )
    source = reference(grant["source"], base)
    if source.stat().st_size == 0:
        raise ValueError("Authorization source is empty")
    scripts = {}
    for name in ("deploy", "readback"):
        if grant.get(name) != spec.get(name):
            raise ValueError("Deployment adapter is outside authorization")
        scripts[name] = reference(spec[name], base)
        if scripts[name].stat().st_size > LIMIT:
            raise ValueError("Adapter exceeds size limit")
    timeout = spec.get("timeout_seconds", 300)
    if (
        not isinstance(timeout, int)
        or isinstance(timeout, bool)
        or not 1 <= timeout <= 900
    ):
        raise ValueError("Adapter timeout must be 1..900 seconds")
    key = hashlib.sha256(
        json.dumps([project, environment, version], separators=(",", ":")).encode()
    ).hexdigest()
    return key, {
        "project": project,
        "environment": environment,
        "version_sha256": version,
        "artifact": str(artifact),
        "deploy": str(scripts["deploy"]),
        "readback": str(scripts["readback"]),
        "timeout_seconds": timeout,
        "task": plan["task"],
        "step": step,
        "spec_sha256": hashlib.sha256(
            json.dumps(spec, sort_keys=True).encode()
        ).hexdigest(),
    }


def job_for(plan_path, plan, step):
    spec = plan["steps"][step]
    project = str(Path(plan["project"]).resolve())
    key = hashlib.sha256(
        json.dumps(
            [project, spec["environment"], spec["artifact"]["sha256"]],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    folder = ROOT / "jobs" / key
    binding_key = hashlib.sha256(
        (str(plan_path.resolve()) + "\n" + plan["task"] + "\n" + step).encode()
    ).hexdigest()
    binding = ROOT / "bindings" / (binding_key + ".json")
    with locked(ROOT / "bindings.lock"):
        if binding.exists() and read(binding)["job"] != key:
            raise ValueError(
                "Registered delivery version changed; create a new delivery point"
            )
        if (folder / "job.json").exists():
            saved = read(folder / "job.json")
            expected = hashlib.sha256(
                json.dumps(spec, sort_keys=True).encode()
            ).hexdigest()
            if saved["spec_sha256"] != expected:
                raise ValueError(
                    "Existing version has a different deployment contract; do not resend"
                )
            if digest(saved["artifact"]) != saved["version_sha256"]:
                raise ValueError("Saved delivery artifact changed")
            return folder, saved, read(folder / "state.json")
        key, expected = prepare(plan_path, plan, step)
        binding.parent.mkdir(parents=True, exist_ok=True)
        write(binding, {"job": key})
    return folder, expected, None


def boot_id():
    return Path("/proc/sys/kernel/random/boot_id").read_text().strip()


def service_state(unit):
    result = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            unit,
            "--property=LoadState,ActiveState,SubState,Result",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    output = result.stdout if isinstance(result.stdout, str) else ""
    return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)


def set_state(folder, value, only=None):
    with locked(folder / "state.lock"):
        if only is None or read(folder / "state.json")["status"] in only:
            write(folder / "state.json", value)
        return read(folder / "state.json")


def ordering_blocker(job):
    files = list((ROOT / "jobs").glob("*/job.json"))
    if len(files) > 512:
        raise ValueError("Delivery history exceeds bounded inspection limit")
    for path in files:
        other = read(path)
        if (other["project"], other["environment"]) != (
            job["project"],
            job["environment"],
        ) or other["unit"] == job["unit"]:
            continue
        status = read(path.parent / "state.json")["status"]
        if other["sequence"] > job["sequence"] and status != "prepared":
            raise ValueError(
                "Newer version has entered deployment; old version cannot resume or retry"
            )
        if other["sequence"] < job["sequence"]:
            if status in ("prepared", "dispatch_unknown"):
                return True
            if (
                status == "dispatching"
                and service_state(other["unit"]).get("LoadState") != "loaded"
            ):
                return True
    return False


def launch(folder, job):
    state = read(folder / "state.json")
    if state["status"] in ("deployed", "failed", "running"):
        return state
    if state["status"] in ("dispatching", "dispatch_unknown"):
        actual = service_state(job["unit"])
        if actual.get("LoadState") != "not-found" or job["boot_id"] != boot_id():
            return state
        # Same-boot unit absence is safe: completed units are retained by
        # RemainAfterExit and failed units by systemd's default collection policy.
    if ordering_blocker(job):
        return set_state(
            folder,
            {"status": "prepared", "next_action": "inspect_previous_dispatch_no_retry"},
        )
    scope = hashlib.sha256(
        (job["project"] + "\n" + job["environment"]).encode()
    ).hexdigest()
    lane = ROOT / ("lane-" + scope + ".json")
    previous = read(lane)["unit"] if lane.exists() else None
    if previous and previous != job["unit"]:
        previous_folder = (
            ROOT / "jobs" / previous.removeprefix("cash-delivery-").split("-retry-")[0]
        )
        if read(previous_folder / "state.json")["status"] == "dispatch_unknown":
            return set_state(
                folder,
                {
                    "status": "prepared",
                    "next_action": "inspect_previous_dispatch_no_retry",
                },
            )
        job["previous_unit"] = previous
        write(folder / "job.json", job)
    write(lane, {"unit": job["unit"]})
    set_state(
        folder,
        {"status": "dispatching"},
        only={"prepared", "dispatching", "dispatch_unknown"},
    )
    argv = [
        "systemd-run",
        "--user",
        "--quiet",
        "--no-block",
        "--unit=" + job["unit"],
        "--property=Type=oneshot",
        "--property=RemainAfterExit=yes",
        "--property=CPUQuota=50%",
        "--property=MemoryMax=1G",
        "--property=TimeoutStartSec=" + str(2 * job["timeout_seconds"] + 30),
        "--property=LimitFSIZE=16M",
        "--property=StandardOutput=null",
        "--property=StandardError=null",
    ]
    if job.get("previous_unit"):
        argv += ["--property=After=" + job["previous_unit"] + ".service"]
    argv += ["/usr/bin/python3", str(folder / "worker.py"), "worker", str(folder)]
    try:
        result = subprocess.run(argv, capture_output=True, timeout=10)
        if result.returncode:
            raise ValueError("systemd refused delivery job")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return set_state(
            folder,
            {"status": "dispatch_unknown", "next_action": "inspect_unit_no_retry"},
            only={"dispatching"},
        )
    return read(folder / "state.json")


def submit(plan_path, plan, step):
    with locked(ROOT / "submit.lock"):
        folder, job, state = job_for(plan_path, plan, step)
        if state is None:
            folder.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".preparing-", dir=folder.parent))
            try:
                for name in ("artifact", "deploy", "readback"):
                    target = staging / name
                    shutil.copyfile(job[name], target)
                    if digest(target) != plan["steps"][step][name]["sha256"]:
                        raise ValueError("Input changed while snapshotting")
                    os.chmod(target, 0o700 if name != "artifact" else 0o400)
                    job[name] = str(folder / name)
                shutil.copyfile(Path(__file__).resolve(), staging / "worker.py")
                job["adapter_hashes"] = {
                    name: digest(staging / name) for name in ("deploy", "readback")
                }
                job["unit"] = "cash-delivery-" + folder.name
                counter = ROOT / "sequence.json"
                sequence = read(counter)["value"] + 1 if counter.exists() else 1
                write(counter, {"value": sequence})
                job["sequence"] = sequence
                job["created_at"] = time.time()
                job["boot_id"] = boot_id()
                write(staging / "job.json", job)
                write(staging / "state.json", {"status": "prepared"})
                os.rename(staging, folder)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
        return launch(folder, job)


def worker(folder):
    folder = Path(folder).resolve()
    with locked(folder / "worker.lock"):
        state = read(folder / "state.json")
        if state["status"] not in ("dispatching", "dispatch_unknown"):
            return 1
        job = read(folder / "job.json")
        set_state(folder, {"status": "running", "started_at": time.time()})
        try:
            if digest(job["artifact"]) != job["version_sha256"]:
                raise ValueError("Artifact changed")
            for name, sha in job["adapter_hashes"].items():
                if digest(job[name]) != sha:
                    raise ValueError("Adapter changed")
            env = dict(
                os.environ,
                CASH_DELIVERY_ARTIFACT=job["artifact"],
                CASH_DELIVERY_SHA256=job["version_sha256"],
                CASH_DELIVERY_ENVIRONMENT=job["environment"],
            )
            # Adapters must be standalone executables. No shell expansion or rebuild.
            for name in ("deploy", "readback"):
                with (
                    (folder / (name + ".stdout")).open("wb") as out,
                    (folder / (name + ".stderr")).open("wb") as err,
                ):
                    result = subprocess.run(
                        [job[name]],
                        cwd=folder,
                        env=env,
                        stdout=out,
                        stderr=err,
                        timeout=job["timeout_seconds"],
                    )
                if result.returncode != 0:
                    raise ValueError(name + "_failed")
            receipt = read(folder / "readback.stdout")
            if (
                receipt.get("version_sha256") != job["version_sha256"]
                or receipt.get("result") != "pass"
            ):
                raise ValueError("Online readback is not the deployed version")
            if (
                not isinstance(receipt.get("checks"), list)
                or not receipt["checks"]
                or any(
                    c.get("result") != "pass" or not c.get("name")
                    for c in receipt["checks"]
                )
            ):
                raise ValueError("Online functional checks did not pass")
            set_state(
                folder,
                {
                    "status": "deployed",
                    "finished_at": time.time(),
                    "readback_sha256": digest(folder / "readback.stdout"),
                },
            )
            return 0
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            subprocess.TimeoutExpired,
        ) as exc:
            set_state(
                folder,
                {
                    "status": "failed",
                    "finished_at": time.time(),
                    "error_type": type(exc).__name__,
                    "next_action": "inspect_evidence_no_retry",
                },
            )
            return 1


def gate(checkpoints, task, step, task_state, step_state, checks):
    ready = (
        step_state == "VALIDATING"
        and bool(checks)
        and all(c.endswith("=pass") for c in checks)
    )
    if not ready and step_state != "DONE" and task_state != "COMPLETE":
        return None
    try:
        plan_path, plan = plan_for(checkpoints, task)
        if step not in plan["steps"]:
            raise ValueError("Step is missing from delivery plan")
        if plan["steps"][step]["kind"] != "internal":
            folder, job, state = job_for(plan_path, plan, step)
            if ready:
                state = submit(plan_path, plan, step)
                # A failed deployment is visible, but does not block independent development.
                print(
                    "delivery: "
                    + state["status"]
                    + "; job="
                    + str(folder)
                    + "; continue independent steps",
                    file=sys.stderr,
                )
            elif not state or state["status"] != "deployed":
                raise ValueError(
                    "Delivery point is not deployed; leave VALIDATING and continue independent steps"
                )
            if state and state["status"] == "deployed":
                if digest(folder / "readback.stdout") != state["readback_sha256"]:
                    raise ValueError("Readback evidence changed")
        if task_state == "COMPLETE":
            for sid, spec in plan["steps"].items():
                if spec["kind"] != "internal":
                    folder, _, state = job_for(plan_path, plan, sid)
                    if not state or state["status"] != "deployed":
                        raise ValueError("Task has an undelivered milestone")
                    if digest(folder / "readback.stdout") != state["readback_sha256"]:
                        raise ValueError("Readback evidence changed")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return "交付檢查拒絕：" + str(exc) + "；其他無依賴工作可以繼續。"
    return None


def retry(folder, authorization):
    folder = Path(folder).resolve()
    grant = verified_json(authorization, Path.cwd())
    if grant.get("authorized") is not True or grant.get("job") != folder.name:
        raise ValueError("Retry requires authorization for this exact job")
    source = reference(grant["source"], Path(authorization["path"]).resolve().parent)
    if not source.stat().st_size:
        raise ValueError("Retry authorization source is empty")
    with locked(ROOT / "submit.lock"):
        state, job = read(folder / "state.json"), read(folder / "job.json")
        actual = service_state(job["unit"])
        if state["status"] != "failed" or actual.get("ActiveState") not in (
            "failed",
            "inactive",
        ):
            raise ValueError("Inspect the stopped failed unit before retrying")
        if ordering_blocker(job):
            raise ValueError("Earlier deployment unresolved")
        attempt = job.get("attempt", 0) + 1
        if attempt > 3:
            raise ValueError("Retry limit reached; replan instead of resending")
        archive = folder / ("attempt-" + str(attempt))
        archive.mkdir()
        for name in (
            "state.json",
            "job.json",
            "deploy.stdout",
            "deploy.stderr",
            "readback.stdout",
            "readback.stderr",
        ):
            if (folder / name).exists():
                shutil.copyfile(folder / name, archive / name)
        write(archive / "authorization.json", grant)
        job.update(
            attempt=attempt,
            unit="cash-delivery-" + folder.name + "-retry-" + str(attempt),
            boot_id=boot_id(),
        )
        write(folder / "job.json", job)
        set_state(folder, {"status": "prepared"})
        return launch(folder, job)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("worker")
    p.add_argument("folder", type=Path)
    p = sub.add_parser("submit")
    p.add_argument("checkpoints", type=Path)
    p.add_argument("--task", required=True)
    p.add_argument("--step", required=True)
    p = sub.add_parser("retry")
    p.add_argument("folder", type=Path)
    p.add_argument("--authorization", required=True)
    p.add_argument("--sha256", required=True)
    p = sub.add_parser("status")
    p.add_argument("folder", type=Path)
    args = parser.parse_args()
    if args.command == "worker":
        return worker(args.folder)
    if args.command == "submit":
        path, plan = plan_for(args.checkpoints, args.task)
        print(json.dumps(submit(path, plan, args.step), ensure_ascii=False))
        return 0
    if args.command == "retry":
        print(
            json.dumps(
                retry(args.folder, {"path": args.authorization, "sha256": args.sha256}),
                ensure_ascii=False,
            )
        )
        return 0
    job = read(args.folder / "job.json")
    if not re.fullmatch(r"cash-delivery-[0-9a-f]{64}(?:-retry-[1-3])?", job["unit"]):
        raise ValueError("Invalid delivery unit")
    result = subprocess.run(
        [
            "systemctl",
            "--user",
            "show",
            job["unit"],
            "--property=ActiveState,SubState,Result",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    print(
        json.dumps(
            {
                "recorded": read(args.folder / "state.json"),
                "service": dict(
                    line.split("=", 1)
                    for line in result.stdout.splitlines()
                    if "=" in line
                ),
                "query_exit": result.returncode,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
