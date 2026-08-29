"""Offline state-machine tests for the boom-first Cloud Run launcher."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts/cloud_boom_first_paired_shadow.sh"
JOB = "atlas-minimal-c-smoke"
JOB_UID = "5135c9eb-96c2-41c0-a68a-5c587a601903"
PROJECT = "nfl-predictions-503414"
REGION = "us-central1"
RECOVERY_BUCKET = "boom-first-test-recovery"
IMAGE = (
    f"{REGION}-docker.pkg.dev/{PROJECT}/nfl-dfs/nfl-dfs@sha256:"
    + "b" * 64
)
CODE_SHA = "a" * 40


FAKE_GCLOUD = r'''#!/usr/bin/env python3
import copy
import json
import os
from pathlib import Path
import shutil
import sys


root = Path(os.environ["FAKE_GCLOUD_ROOT"])
mode = os.environ.get("FAKE_GCLOUD_MODE", "success")
args = sys.argv[1:]


def load(name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def save(name, value):
    (root / name).write_text(
        json.dumps(value, sort_keys=True), encoding="utf-8"
    )


def flag(name):
    return args[args.index(name) + 1]


def cloud_path(uri):
    if not uri.startswith("gs://"):
        raise SystemExit(f"not a fake GCS URI: {uri}")
    return root / "cloud" / uri.removeprefix("gs://")


with (root / "commands.jsonl").open("a", encoding="utf-8") as stream:
    stream.write(json.dumps(args) + "\n")

control = load("control.json")

if args[:4] == ["run", "jobs", "executions", "list"]:
    print("[]")
elif args[:4] == ["run", "jobs", "executions", "describe"]:
    print(json.dumps(load("execution.json"), sort_keys=True))
elif args[:3] == ["run", "jobs", "describe"]:
    if (
        mode == "verify_describe_failure"
        and control.get("replace_seen")
        and not control.get("verification_failure_consumed")
    ):
        control["verification_failure_consumed"] = True
        save("control.json", control)
        print("injected post-replace describe failure", file=sys.stderr)
        raise SystemExit(1)
    print(json.dumps(load("job.json"), sort_keys=True))
elif args[:3] == ["run", "jobs", "update"]:
    job = load("job.json")
    task = job["spec"]["template"]["spec"]
    spec = task["template"]["spec"]
    env = []
    for item in flag("--set-env-vars").split(","):
        name, value = item.split("=", 1)
        env.append({"name": name, "value": value})
    spec["containers"] = [{
        "image": flag("--image"),
        "command": [flag("--command")],
        "args": [flag("--args")],
        "env": env,
        "resources": {"limits": {
            "cpu": flag("--cpu"),
            "memory": flag("--memory"),
        }},
    }]
    spec["maxRetries"] = int(flag("--max-retries"))
    spec["timeoutSeconds"] = flag("--task-timeout").removesuffix("s")
    task["taskCount"] = int(flag("--tasks"))
    task["parallelism"] = int(flag("--parallelism"))
    save("job.json", job)
elif args[:3] == ["run", "jobs", "execute"]:
    job = load("job.json")
    task = job["spec"]["template"]["spec"]
    spec = copy.deepcopy(task["template"]["spec"])
    execution = {
        "metadata": {
            "name": "atlas-minimal-c-smoke-testexec",
            "uid": "execution-uid-test",
            "labels": {
                "run.googleapis.com/job": "atlas-minimal-c-smoke",
                "run.googleapis.com/jobUid": job["metadata"]["uid"],
            },
        },
        "spec": {
            "taskCount": task["taskCount"],
            "parallelism": task["parallelism"],
            "template": {"spec": spec},
        },
    }
    if mode == "execution_contract_mismatch":
        execution["spec"]["template"]["spec"]["containers"][0][
            "image"
        ] = "invalid.example/image@sha256:" + "0" * 64
    save("execution.json", execution)
    print(execution["metadata"]["name"])
elif args[:3] == ["run", "jobs", "replace"]:
    replacement = json.loads(Path(args[3]).read_text(encoding="utf-8"))
    if mode == "verify_mismatch":
        replacement["spec"]["template"]["spec"]["template"]["spec"][
            "timeoutSeconds"
        ] = "999"
    save("job.json", replacement)
    control["replace_seen"] = True
    save("control.json", control)
elif args[:3] == ["scheduler", "jobs", "list"]:
    print("[]")
elif args[:2] == ["storage", "cp"]:
    source = Path(args[2])
    destination = cloud_path(args[3])
    if "--if-generation-match=0" in args and destination.exists():
        print("fake create-only destination exists", file=sys.stderr)
        raise SystemExit(1)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
elif args[:2] == ["storage", "rm"]:
    target = cloud_path(args[2])
    if not target.exists():
        raise SystemExit(1)
    target.unlink()
else:
    print(f"unsupported fake gcloud command: {args}", file=sys.stderr)
    raise SystemExit(64)
'''


def _prior_job() -> dict:
    return {
        "metadata": {"name": JOB, "uid": JOB_UID},
        "spec": {
            "template": {
                "spec": {
                    "taskCount": 1,
                    "parallelism": 1,
                    "template": {
                        "spec": {
                            "containers": [{
                                "image": "example.invalid/prior@sha256:"
                                + "1" * 64,
                                "command": ["prior-command"],
                                "args": ["prior-argument"],
                                "env": [{"name": "PRIOR", "value": "1"}],
                                "resources": {"limits": {
                                    "cpu": "1",
                                    "memory": "1Gi",
                                }},
                            }],
                            "maxRetries": 1,
                            "timeoutSeconds": "3600",
                            "serviceAccountName": "shadow@example.invalid",
                        }
                    },
                }
            }
        },
    }


def _run_launcher(tmp_path: Path, mode: str = "success"):
    fake_root = tmp_path / "fake-cloud"
    fake_bin = tmp_path / "bin"
    fake_root.mkdir()
    fake_bin.mkdir()
    prior = _prior_job()
    (fake_root / "job.json").write_text(
        json.dumps(prior, sort_keys=True), encoding="utf-8"
    )
    (fake_root / "control.json").write_text("{}", encoding="utf-8")
    fake = fake_bin / "gcloud"
    fake.write_text(textwrap.dedent(FAKE_GCLOUD), encoding="utf-8")
    fake.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_GCLOUD_ROOT": str(fake_root),
        "FAKE_GCLOUD_MODE": mode,
        "GCP_PROJECT": PROJECT,
        "REGION": REGION,
        "GCS_BUCKET": RECOVERY_BUCKET,
        "IMAGE_URI": IMAGE,
        "CODE_SHA": CODE_SHA,
    }
    completed = subprocess.run(
        ["bash", str(LAUNCHER)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    combined = completed.stdout + "\n" + completed.stderr
    state_match = re.search(r"^recovery_state=(.+)$", combined, re.MULTILINE)
    assert state_match is not None, combined
    state_dir = Path(state_match.group(1))
    commands = [
        json.loads(line)
        for line in (fake_root / "commands.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    lease = (
        fake_root
        / "cloud"
        / RECOVERY_BUCKET
        / "boom_first_shadow/operator-locks"
        / f"{JOB}.json"
    )
    return completed, combined, fake_root, state_dir, lease, prior, commands


def test_success_restores_exact_prior_spec_and_releases_all_ephemeral_state(
    tmp_path,
):
    completed, output, fake_root, state_dir, lease, prior, commands = (
        _run_launcher(tmp_path)
    )

    assert completed.returncode == 0, output
    assert json.loads((fake_root / "job.json").read_text()) == prior
    assert "restored=true" in output
    assert "lease_released=true" in output
    assert not state_dir.exists()
    assert not lease.exists()
    assert ["run", "jobs", "executions", "describe"] in [
        command[:4] for command in commands
    ]
    assert sum(command[:3] == ["run", "jobs", "replace"]
               for command in commands) == 1


@pytest.mark.parametrize(
    ("mode", "expected_message", "job_restored", "lease_retained"),
    [
        (
            "verify_mismatch",
            "reusable job restoration verification failed",
            False,
            True,
        ),
        (
            "verify_describe_failure",
            "injected post-replace describe failure",
            True,
            False,
        ),
    ],
)
def test_post_replace_verification_failure_retains_recovery_state(
    tmp_path, mode, expected_message, job_restored, lease_retained,
):
    completed, output, fake_root, state_dir, lease, prior, _ = _run_launcher(
        tmp_path, mode
    )
    try:
        assert completed.returncode != 0
        assert expected_message in output
        assert "restored=true" not in output
        assert state_dir.is_dir()
        assert (state_dir / "job-before.yaml").is_file()
        assert (state_dir / "job-before.json").is_file()
        assert (
            json.loads((fake_root / "job.json").read_text()) == prior
        ) is job_restored
        assert lease.exists() is lease_retained
    finally:
        shutil.rmtree(state_dir, ignore_errors=True)


def test_execution_contract_mismatch_fails_before_success_and_restores_job(
    tmp_path,
):
    completed, output, fake_root, state_dir, lease, prior, commands = (
        _run_launcher(tmp_path, "execution_contract_mismatch")
    )
    try:
        assert completed.returncode != 0
        assert "created Cloud Run execution contract differs" in output
        assert "restored=true" not in output
        assert json.loads((fake_root / "job.json").read_text()) == prior
        assert not lease.exists()
        assert state_dir.is_dir()
        execution_describes = [
            command for command in commands
            if command[:4] == ["run", "jobs", "executions", "describe"]
        ]
        assert len(execution_describes) == 1
        assert sum(command[:3] == ["run", "jobs", "replace"]
                   for command in commands) == 1
    finally:
        shutil.rmtree(state_dir, ignore_errors=True)
