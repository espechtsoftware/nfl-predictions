from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh"
BUILD = ROOT / "cloudbuild.corpus-r6-broad-admission.yaml"
DOCKERFILE = ROOT / "Dockerfile.corpus-r6-broad-admission"
DOCKERIGNORE = ROOT / "Dockerfile.corpus-r6-broad-admission.dockerignore"
CODE_SHA = "1" * 40
BUILD_ID = "11111111-2222-3333-4444-555555555555"
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/"
    "nfl-dfs@sha256:" + "a" * 64
)
JOB = "atlas-cbc-32g-full-2023-w8-v1"
JOB_UID = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
SERVICE_ACCOUNT = "817589974517-compute@developer.gserviceaccount.com"


def _identity(seed: str = "b") -> dict[str, object]:
    return {
        "uri": f"gs://bucket/{seed}.json",
        "generation": "123",
        "sha256": seed * 64,
        "bytes": 123,
    }


def _install_fake_git(directory: Path) -> None:
    fake = directory / "git"
    fake.write_text(
        "#!/bin/sh\n"
        f"case \"$*\" in\n"
        f"  'rev-parse --show-toplevel') printf '%s\\n' '{ROOT}';;\n"
        f"  '-C {ROOT} rev-parse HEAD') printf '%s\\n' '{CODE_SHA}';;\n"
        f"  '-C {ROOT} rev-parse --verify refs/remotes/origin/main^{{commit}}') printf '%s\\n' '{CODE_SHA}';;\n"
        f"  '-C {ROOT} status --porcelain --untracked-files=all') printf '%s\\n' '?? unrelated-user-file.tmp';;\n"
        f"  '-C {ROOT} status --porcelain --untracked-files=all -- '*)\n"
        "    requested=$(printf '%s\\n' \"$*\" | sed 's/^.* -- //')\n"
        "    if [ \"${DIRTY_RELEASE_PATH:-}\" = \"$requested\" ]; then\n"
        "      printf ' M %s\\n' \"$requested\"\n"
        "    fi;;\n"
        f"  '-C {ROOT} cat-file -e " + CODE_SHA + "^{commit}') :;;\n"
        f"  '-C {ROOT} cat-file -e " + CODE_SHA + ":'*) :;;\n"
        "  *) exit 98;;\n"
        "esac\n"
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)


def _install_fake_gcloud(directory: Path, *, installed: bool = True) -> Path:
    state = directory / "gcloud-state.json"
    state.write_text(json.dumps({"installed": installed}))
    fake = directory / "gcloud"
    fake.write_text(
        r'''#!/usr/bin/env python3
import base64, hashlib, json, os, pathlib, sys

a = sys.argv[1:]
state_path = pathlib.Path(os.environ["GCLOUD_STATE"])
state = json.loads(state_path.read_text())
with open(os.environ["GCLOUD_LOG"], "a") as handle:
    handle.write(" ".join(a) + "\n")

project = "nfl-predictions-503414"
job = "atlas-cbc-32g-full-2023-w8-v1"
job_uid = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
service_account = "817589974517-compute@developer.gserviceaccount.com"
image = os.environ["EXPECTED_IMAGE"]
sha = os.environ["EXPECTED_SHA"]
build_id = os.environ["EXPECTED_BUILD"]
digest = image.split("@", 1)[1]
image_tag = image.split("@", 1)[0] + ":broad-admission-" + sha
generation = "8" if state.get("installed") else "7"

def container(args, env):
    return {
        "image": image,
        "command": ["/bin/bash"],
        "args": args,
        "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
        "env": [{"name": key, "value": value} for key, value in env.items()],
    }

installed_env = {
    "CODE_SHA": sha,
    "IMAGE_DIGEST": digest,
    "BUILD_ID": build_id,
    "R6_BROAD_ADMISSION_ENABLE": "DISABLED_INSTALL_ONLY",
    "R6_BROAD_ADMISSION_OUTCOMES_ALLOWED": "false",
    "R6_BROAD_ADMISSION_TASK0_SMOKE": "false",
}

if a[:2] == ["builds", "describe"]:
    print(json.dumps({
        "id": build_id,
        "status": "SUCCESS",
        "finishTime": "2026-08-30T22:00:00Z",
        "source": {"gitSource": {
            "url": "https://github.com/espechtsoftware/nfl-predictions.git",
            "revision": sha,
        }},
        "sourceProvenance": {"resolvedGitSource": {
            "url": "https://github.com/espechtsoftware/nfl-predictions.git",
            "revision": sha,
        }},
        "substitutions": {"_CODE_SHA": sha, "_BUILD_IMAGE": image_tag},
        "results": {"images": [{"name": image_tag, "digest": digest}]},
    }))
    raise SystemExit

if a[:3] == ["run", "jobs", "update"]:
    state["installed"] = True
    state_path.write_text(json.dumps(state))
    raise SystemExit

if a[:3] == ["run", "jobs", "describe"]:
    generation = "8" if state.get("installed") else "7"
    print(json.dumps({
        "metadata": {"name": job, "uid": job_uid, "generation": generation},
        "status": {
            "conditions": [{"type": "Ready", "status": "True"}],
            "latestCreatedExecution": {"name": job + "-old00"},
        },
        "spec": {"template": {"spec": {
            "taskCount": 54,
            "parallelism": 54,
            "template": {"spec": {
                "maxRetries": 0,
                "timeout": "21600s",
                "serviceAccountName": service_account,
                "containers": [container([
                    "/app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh",
                    "container-help",
                ], installed_env)],
            }},
        }}},
    }))
    raise SystemExit

if a[:3] == ["run", "jobs", "execute"]:
    def value(flag):
        return a[a.index(flag) + 1]
    env_text = value("--update-env-vars")
    assert env_text.startswith("^|^")
    env = dict(item.split("=", 1) for item in env_text[3:].split("|"))
    state["last"] = {
        "tasks": int(value("--tasks")),
        "args": value("--args").split(","),
        "env": env,
    }
    state_path.write_text(json.dumps(state))
    print(json.dumps({"metadata": {"name": job + "-new01"}}))
    raise SystemExit

if a[:2] == ["logging", "read"]:
    receipt = os.environ["RESULT_RECEIPT"]
    rows = [{"textPayload": "bounded non-json runtime note"}, {"textPayload": receipt}]
    if os.environ.get("RESULT_DUPLICATE") == "1":
        rows.append({"textPayload": receipt})
    print(json.dumps(rows))
    raise SystemExit

if a[:4] == ["run", "jobs", "executions", "describe"]:
    name = a[4]
    if name == job + "-old00":
        print(json.dumps({
            "metadata": {"name": name, "labels": {"run.googleapis.com/job": job}},
            "status": {
                "conditions": [{"type": "Completed", "status": "True"}],
                "completionTime": "2026-08-30T20:00:00Z",
                "succeededCount": 1,
            },
        }))
        raise SystemExit
    if name == os.environ.get("RESULT_EXECUTION"):
        phase = os.environ["RESULT_PHASE"]
        request = os.environ["RESULT_REQUEST"].encode()
        smoke = "true" if phase == "task0" else "false"
        outcomes = "true" if phase == "grade" else "false"
        env = {
            "CODE_SHA": sha,
            "IMAGE_DIGEST": digest,
            "BUILD_ID": build_id,
            "IMAGE_URI": image,
            "R6_BROAD_ADMISSION_ENABLE":
                "I_UNDERSTAND_FIXED_CORPUS_ADMISSION_TOURNAMENT_V1",
            "R6_BROAD_ADMISSION_BOUND_IDENTITY": os.environ["EXPECTED_BOUND"],
            "R6_BROAD_ADMISSION_OUTCOMES_ALLOWED": outcomes,
            "R6_BROAD_ADMISSION_TASK0_SMOKE": smoke,
            "R6_BROAD_ADMISSION_REQUEST_SHA256": hashlib.sha256(request).hexdigest(),
            "R6_BROAD_ADMISSION_REQUEST_B64": base64.b64encode(request).decode(),
        }
        terminal_mode = os.environ.get("RESULT_TERMINAL_MODE", "success")
        status = {
            "conditions": [{
                "type": "Completed",
                "status": "False" if terminal_mode == "nonterminal" else "True",
            }],
            "completionTime": "2026-08-30T23:00:00Z",
            "succeededCount": 0 if terminal_mode != "success" else 1,
            "failedCount": 1 if terminal_mode == "failed" else 0,
            "runningCount": 1 if terminal_mode == "nonterminal" else 0,
        }
        print(json.dumps({
            "metadata": {
                "name": name,
                "uid": "result-execution-uid",
                "labels": {
                    "run.googleapis.com/job": job,
                    "run.googleapis.com/jobUid": job_uid,
                    "run.googleapis.com/jobGeneration": "8",
                },
            },
            "spec": {
                "taskCount": 1,
                "parallelism": 54,
                "template": {"spec": {
                    "maxRetries": 0,
                    "timeout": "21600s",
                    "serviceAccountName": service_account,
                    "containers": [container([
                        "/app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh",
                        "container-run", phase,
                    ], env)],
                }},
            },
            "status": status,
        }))
        raise SystemExit
    if name == os.environ.get("SOURCE_TASK_EXECUTION"):
        bound = os.environ["EXPECTED_BOUND"]
        task_request = json.dumps(
            {"manifest_identity": json.loads(bound)},
            sort_keys=True, separators=(",", ":"),
        ).encode()
        env = {
            "CODE_SHA": sha,
            "IMAGE_DIGEST": digest,
            "BUILD_ID": build_id,
            "IMAGE_URI": image,
            "R6_BROAD_ADMISSION_ENABLE":
                "I_UNDERSTAND_FIXED_CORPUS_ADMISSION_TOURNAMENT_V1",
            "R6_BROAD_ADMISSION_BOUND_IDENTITY": bound,
            "R6_BROAD_ADMISSION_OUTCOMES_ALLOWED": "false",
            "R6_BROAD_ADMISSION_TASK0_SMOKE": "false",
            "R6_BROAD_ADMISSION_REQUEST_SHA256": hashlib.sha256(task_request).hexdigest(),
            "R6_BROAD_ADMISSION_REQUEST_B64": base64.b64encode(task_request).decode(),
        }
        print(json.dumps({
            "metadata": {
                "name": name,
                "uid": "source-task-uid",
                "labels": {
                    "run.googleapis.com/job": job,
                    "run.googleapis.com/jobUid": job_uid,
                    "run.googleapis.com/jobGeneration": "8",
                },
            },
            "spec": {
                "taskCount": 54,
                "parallelism": 54,
                "template": {"spec": {
                    "maxRetries": 0,
                    "timeout": "21600s",
                    "serviceAccountName": service_account,
                    "containers": [container([
                        "/app/scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh",
                        "container-run", "task",
                    ], env)],
                }},
            },
            "status": {
                "conditions": [{"type": "Completed", "status": "True"}],
                "completionTime": "2026-08-30T21:00:00Z",
                "succeededCount": 54,
            },
        }))
        raise SystemExit
    if name == job + "-new01":
        last = state["last"]
        print(json.dumps({
            "metadata": {
                "name": name,
                "uid": "new-execution-uid",
                "labels": {
                    "run.googleapis.com/job": job,
                    "run.googleapis.com/jobUid": job_uid,
                    "run.googleapis.com/jobGeneration": "8",
                },
            },
            "spec": {
                "taskCount": last["tasks"],
                "parallelism": 54,
                "template": {"spec": {
                    "maxRetries": 0,
                    "timeout": "21600s",
                    "serviceAccountName": service_account,
                    "containers": [container(last["args"], last["env"])],
                }},
            },
        }))
        raise SystemExit
raise SystemExit(97)
'''
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    return state


def _environment(tmp_path: Path, *, installed: bool = True) -> dict[str, str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    _install_fake_git(tmp_path)
    state = _install_fake_gcloud(tmp_path, installed=installed)
    return {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "GCLOUD_STATE": str(state),
        "GCLOUD_LOG": str(tmp_path / "calls.log"),
        "EXPECTED_IMAGE": IMAGE,
        "EXPECTED_SHA": CODE_SHA,
        "EXPECTED_BUILD": BUILD_ID,
    }


def _task0_result_environment(
    tmp_path: Path,
    *,
    execution: str,
    manifest: dict[str, object],
    terminal_mode: str = "success",
) -> dict[str, str]:
    request = json.dumps(
        {"manifest_identity": manifest}, sort_keys=True, separators=(",", ":"),
    )
    inner = {
        "complete": True,
        "manifest_identity": manifest,
        "package_sha256": "1" * 64,
        "publication_performed": False,
        "schema_version": "corpus-r6-broad-admission-task0-smoke/v1",
        "slate_id": "2023-w01",
        "smoke_result_sha256": "2" * 64,
        "source_ordinal": 0,
        "task_result_sha256": "3" * 64,
        "union_lineups_sha256": "4" * 64,
        "uses_realized_outcomes": False,
    }
    receipt = json.dumps({
        "command": "task",
        "complete": True,
        "result": inner,
        "schema_version": "corpus-r6-broad-admission-cli-receipt/v1",
        "task0_nonpublishing_smoke": True,
        "uses_realized_outcomes": False,
    }, sort_keys=True, separators=(",", ":"))
    return {
        **_environment(tmp_path),
        "RESULT_EXECUTION": execution,
        "RESULT_PHASE": "task0",
        "RESULT_REQUEST": request,
        "RESULT_RECEIPT": receipt,
        "RESULT_TERMINAL_MODE": terminal_mode,
        "EXPECTED_BOUND": json.dumps(manifest, sort_keys=True, separators=(",", ":")),
    }


def _run(
    action: str,
    request: Path | str | None,
    *,
    env: dict[str, str],
    extra: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    argv = ["bash", str(SCRIPT), action, IMAGE, CODE_SHA, BUILD_ID]
    if request is not None:
        argv.append(str(request.resolve()) if isinstance(request, Path) else request)
    argv.extend(extra)
    return subprocess.run(
        argv, cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )


def test_release_files_are_narrow_dormant_and_outcome_separated() -> None:
    script = SCRIPT.read_text()
    build = BUILD.read_text()
    dockerfile = DOCKERFILE.read_text()
    dockerignore = DOCKERIGNORE.read_text()
    parsed = yaml.safe_load(build)
    embedded = script.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    compile(embedded, "broad-admission-build-attestation", "exec")
    assert parsed["timeout"] == "3600s"
    assert "--tasks \"$TASK_COUNT\" --parallelism \"$PARALLELISM\"" in script
    assert "TASK_COUNT=54" in script and "PARALLELISM=54" in script
    assert "--max-retries 0" in script and "TASK_TIMEOUT=21600s" in script
    assert "jobs update" in script
    for forbidden in ("jobs deploy", "jobs create", "jobs delete", "jobs list"):
        assert forbidden not in script
    assert "DISABLED_INSTALL_ONLY" in script
    assert "R6_BROAD_ADMISSION_TASK_EXECUTION_NAME" in script
    assert "R6_BROAD_ADMISSION_OUTCOMES_ALLOWED" in script
    assert "R6_BROAD_ADMISSION_TASK0_SMOKE" in script
    assert "runtime_build_attestation_v1" in script
    assert "validate_runtime_build_attestation_v1" in script
    assert "GCSExactCreateOnceStoreV1" in script
    assert "runtime_build_attestation_identity:$attestation" in script
    assert "outcomes_allowed=true" in script
    assert "grade-reopen" in script
    assert "broad-admission-build" in script and "cleanup_build" in script
    assert "broad-admission-launch" in script and "cleanup_host" in script
    for test_name in (
        "test_corpus_r6_broad_admission_tournament_v1.py",
        "test_corpus_r6_broad_admission_program_v1.py",
        "test_run_corpus_r6_broad_admission_tournament_v1.py",
        "test_cloud_corpus_r6_broad_admission_tournament_v1.py",
    ):
        assert test_name in build
    for command in ("prepare", "task", "collect", "reopen", "grade", "grade-reopen"):
        assert '"$${command}" --help' in build
    assert "run_corpus_r6_construction_allocation_grade_v1.py" in dockerfile
    assert "google-cloud-cli" in dockerfile
    assert "tests" not in dockerignore
    assert "reports" not in dockerignore


def test_launcher_rejects_mutable_image_before_any_provider_call(tmp_path: Path) -> None:
    fake = tmp_path / "gcloud"
    fake.write_text("#!/bin/sh\nexit 99\n")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    result = subprocess.run(
        ["bash", str(SCRIPT), "install", "example/image:latest", CODE_SHA, BUILD_ID],
        cwd=ROOT,
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 2
    assert "immutable project image" in result.stderr


def test_install_updates_existing_job_to_dormant_state_without_execution(
    tmp_path: Path,
) -> None:
    env = _environment(tmp_path, installed=False)
    result = _run("install", None, env=env)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["install_only"] is True
    assert receipt["execution_launched"] is False
    assert receipt["outcomes_allowed"] is False
    calls = (tmp_path / "calls.log").read_text()
    assert "run jobs update " + JOB in calls
    assert "run jobs execute" not in calls
    assert "run jobs deploy" not in calls


def test_unrelated_dirty_state_is_nonblocking_but_dirty_release_input_fails(
    tmp_path: Path,
) -> None:
    # The fake Git reports an unrelated untracked file for whole-tree status;
    # a path-scoped release must not even ask that broad question.
    clean_env = _environment(tmp_path / "clean", installed=False)
    clean = _run("install", None, env=clean_env)
    assert clean.returncode == 0, clean.stderr

    dirty_root = tmp_path / "dirty"
    dirty_root.mkdir()
    dirty_env = {
        **_environment(dirty_root, installed=False),
        "DIRTY_RELEASE_PATH": "README.md",
    }
    dirty = _run("install", None, env=dirty_env)
    assert dirty.returncode == 2
    assert "local release input differs from commit: README.md" in dirty.stderr
    assert not (dirty_root / "calls.log").exists()


def test_task_launch_is_exactly_54_way_and_outcome_blind(tmp_path: Path) -> None:
    manifest = _identity()
    gate_execution = JOB + "-gat01"
    gate_request = json.dumps(
        {"manifest_identity": manifest}, sort_keys=True, separators=(",", ":"),
    )
    gate_inner = {
        "complete": True,
        "manifest_identity": manifest,
        "package_sha256": "1" * 64,
        "publication_performed": False,
        "schema_version": "corpus-r6-broad-admission-task0-smoke/v1",
        "slate_id": "2023-w01",
        "smoke_result_sha256": "2" * 64,
        "source_ordinal": 0,
        "task_result_sha256": "3" * 64,
        "union_lineups_sha256": "4" * 64,
        "uses_realized_outcomes": False,
    }
    gate_receipt = json.dumps({
        "command": "task",
        "complete": True,
        "result": gate_inner,
        "schema_version": "corpus-r6-broad-admission-cli-receipt/v1",
        "task0_nonpublishing_smoke": True,
        "uses_realized_outcomes": False,
    }, sort_keys=True, separators=(",", ":"))
    env = {
        **_environment(tmp_path),
        "RESULT_EXECUTION": gate_execution,
        "RESULT_PHASE": "task0",
        "RESULT_REQUEST": gate_request,
        "RESULT_RECEIPT": gate_receipt,
        "EXPECTED_BOUND": json.dumps(manifest, sort_keys=True, separators=(",", ":")),
    }
    request = tmp_path / "task.json"
    request.write_text(json.dumps({"manifest_identity": manifest}))
    result = _run("task", request, env=env, extra=(gate_execution,))
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["phase"] == "task"
    assert receipt["execution"]["task_count"] == 54
    assert receipt["outcomes_allowed"] is False
    assert receipt["task0_nonpublishing_smoke"] is False
    assert receipt["task0_gate_result"]["phase"] == "task0"
    calls = (tmp_path / "calls.log").read_text()
    assert "run jobs execute " + JOB in calls
    assert "--tasks 54" in calls
    assert "container-run,task" in calls


def test_full_task_cannot_launch_without_exact_task0_gate(tmp_path: Path) -> None:
    request = tmp_path / "task.json"
    request.write_text(json.dumps({"manifest_identity": _identity("a")}))
    env = _environment(tmp_path)
    missing = _run("task", request, env=env)
    assert missing.returncode == 2
    assert "exact successful task0 execution name" in missing.stderr
    wrong_name = _run("task", request, env=env, extra=("not-an-execution",))
    assert wrong_name.returncode == 2
    assert "exact successful task0 execution name" in wrong_name.stderr
    assert not (tmp_path / "calls.log").exists()


def test_full_task_rejects_wrong_phase_or_manifest_gate_without_launch(
    tmp_path: Path,
) -> None:
    task_manifest = _identity("a")
    request = tmp_path / "task.json"
    request.write_text(json.dumps({"manifest_identity": task_manifest}))
    execution = JOB + "-gat02"

    # A perfectly valid result from the wrong phase cannot act as task0.
    terminal = _identity("c")
    reopen_request = json.dumps(
        {"terminal_identity": terminal}, sort_keys=True, separators=(",", ":"),
    )
    reopen_inner = {
        "all_packages_independently_recomputed": True,
        "all_tasks_and_parents_generation_exact_reopened": True,
        "catalog_reread": False,
        "complete": True,
        "outcome_reread": False,
        "package_lattice_sha256": "1" * 64,
        "reopen_result_sha256": "2" * 64,
        "schema_version": "corpus-r6-broad-admission-reopen-result/v1",
        "task_count": 54,
        "terminal_identity": terminal,
        "uses_realized_outcomes": False,
    }
    reopen_receipt = json.dumps({
        "command": "reopen",
        "complete": True,
        "result": reopen_inner,
        "schema_version": "corpus-r6-broad-admission-cli-receipt/v1",
        "task0_nonpublishing_smoke": False,
        "uses_realized_outcomes": False,
    }, sort_keys=True, separators=(",", ":"))
    wrong_phase_env = {
        **_environment(tmp_path / "phase"),
        "RESULT_EXECUTION": execution,
        "RESULT_PHASE": "reopen",
        "RESULT_REQUEST": reopen_request,
        "RESULT_RECEIPT": reopen_receipt,
        "EXPECTED_BOUND": json.dumps(terminal, sort_keys=True, separators=(",", ":")),
    }
    wrong_phase = _run(
        "task", request, env=wrong_phase_env, extra=(execution,),
    )
    assert wrong_phase.returncode == 2
    assert "task0 launch gate differs" in wrong_phase.stderr
    phase_calls = (tmp_path / "phase" / "calls.log").read_text()
    assert "run jobs execute" not in phase_calls and "run jobs update" not in phase_calls

    wrong_manifest = _identity("b")
    wrong_manifest_env = _task0_result_environment(
        tmp_path / "manifest", execution=execution, manifest=wrong_manifest,
    )
    manifest_rejected = _run(
        "task", request, env=wrong_manifest_env, extra=(execution,),
    )
    assert manifest_rejected.returncode == 2
    assert "task0 launch gate differs" in manifest_rejected.stderr
    manifest_calls = (tmp_path / "manifest" / "calls.log").read_text()
    assert "run jobs execute" not in manifest_calls and "run jobs update" not in manifest_calls


@pytest.mark.parametrize("terminal_mode", ["failed", "nonterminal"])
def test_full_task_rejects_unsuccessful_task0_before_launch(
    tmp_path: Path, terminal_mode: str,
) -> None:
    manifest = _identity("a")
    request = tmp_path / "task.json"
    request.write_text(json.dumps({"manifest_identity": manifest}))
    execution = JOB + "-gat03"
    env = _task0_result_environment(
        tmp_path / terminal_mode,
        execution=execution,
        manifest=manifest,
        terminal_mode=terminal_mode,
    )
    rejected = _run("task", request, env=env, extra=(execution,))
    assert rejected.returncode != 0
    calls = (tmp_path / terminal_mode / "calls.log").read_text()
    assert "run jobs execute" not in calls and "run jobs update" not in calls


def test_prepare_binds_exact_runtime_build_code_and_image(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    request = tmp_path / "prepare.json"
    request.write_text(json.dumps({
        "combined_terminal_identity": _identity("4"),
        "frontier_manifest_identity": _identity("5"),
        "runtime_build_attestation_identity": _identity("6"),
        "code_sha": CODE_SHA,
        "immutable_image": IMAGE,
        "output_prefix": "gs://bucket/admission/run-1/",
    }))
    result = _run("prepare", request, env=env)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["phase"] == "prepare"
    assert receipt["provider_resolved_image"] == IMAGE
    assert receipt["outcomes_allowed"] is False

    wrong = json.loads(request.read_text())
    wrong["immutable_image"] = IMAGE.replace("a" * 64, "9" * 64)
    request.write_text(json.dumps(wrong))
    rejected = _run("prepare", request, env=env)
    assert rejected.returncode == 2
    assert "prepare request differs" in rejected.stderr


def test_task0_is_one_task_nonpublishing_reality_smoke(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    request = tmp_path / "task0.json"
    request.write_text(json.dumps({"manifest_identity": _identity("c")}))
    result = _run("task0", request, env=env)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["phase"] == "task0"
    assert receipt["execution"]["task_count"] == 1
    assert receipt["task0_nonpublishing_smoke"] is True
    assert receipt["outcomes_allowed"] is False


def test_collect_validates_and_passes_one_exact_named_task_execution(
    tmp_path: Path,
) -> None:
    manifest = _identity("d")
    bound = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
    source = JOB + "-src01"
    env = {
        **_environment(tmp_path),
        "R6_BROAD_ADMISSION_TASK_EXECUTION_NAME": source,
        "SOURCE_TASK_EXECUTION": source,
        "EXPECTED_BOUND": bound,
    }
    request = tmp_path / "collect.json"
    request.write_text(json.dumps({"manifest_identity": manifest}))
    result = _run("collect", request, env=env)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["phase"] == "collect"
    assert receipt["source_task_execution"] == {
        "name": source,
        "task_count": 54,
        "uid": "source-task-uid",
    }
    assert receipt["outcomes_allowed"] is False
    calls = (tmp_path / "calls.log").read_text()
    assert "run jobs executions describe " + source in calls
    assert "container-run,collect" in calls


def test_only_grade_can_receive_an_outcome_authority(tmp_path: Path) -> None:
    env = _environment(tmp_path)
    invalid = tmp_path / "invalid-task.json"
    invalid.write_text(json.dumps({
        "manifest_identity": _identity("e"),
        "outcome_authority_identity": _identity("f"),
    }))
    rejected = _run("task", invalid, env=env, extra=(JOB + "-gat01",))
    assert rejected.returncode == 2
    assert "task request differs" in rejected.stderr

    grade = tmp_path / "grade.json"
    grade.write_text(json.dumps({
        "terminal_identity": _identity("1"),
        "outcome_authority_identity": _identity("2"),
    }))
    accepted = _run("grade", grade, env=env)
    assert accepted.returncode == 0, accepted.stderr
    receipt = json.loads(accepted.stdout)
    assert receipt["phase"] == "grade"
    assert receipt["outcomes_allowed"] is True

    reopen = tmp_path / "grade-reopen.json"
    reopen.write_text(json.dumps({"grade_terminal_identity": _identity("3")}))
    reopened = _run("grade-reopen", reopen, env=env)
    assert reopened.returncode == 0, reopened.stderr
    reopened_receipt = json.loads(reopened.stdout)
    assert reopened_receipt["outcomes_allowed"] is False


def test_result_collects_one_canonical_prepare_receipt_from_exact_execution(
    tmp_path: Path,
) -> None:
    execution = JOB + "-res01"
    manifest = _identity("7")
    request = json.dumps({
        "code_sha": CODE_SHA,
        "combined_terminal_identity": _identity("4"),
        "frontier_manifest_identity": _identity("5"),
        "immutable_image": IMAGE,
        "output_prefix": "gs://bucket/admission/run-result/",
        "runtime_build_attestation_identity": _identity("6"),
    }, sort_keys=True, separators=(",", ":"))
    inner = {
        "all_nonpublication_authorities_validated_before_first_write": True,
        "build_id": BUILD_ID,
        "complete": True,
        "deployment_mutation_performed": False,
        "execution_launched": False,
        "manifest_identity": manifest,
        "manifest_sha256": "8" * 64,
        "prepare_result_sha256": "9" * 64,
        "schema_version": "corpus-r6-broad-admission-prepare-result/v1",
        "task_count": 54,
        "uses_realized_outcomes": False,
    }
    receipt = json.dumps({
        "command": "prepare",
        "complete": True,
        "result": inner,
        "schema_version": "corpus-r6-broad-admission-cli-receipt/v1",
        "task0_nonpublishing_smoke": False,
        "uses_realized_outcomes": False,
    }, sort_keys=True, separators=(",", ":"))
    env = {
        **_environment(tmp_path),
        "RESULT_EXECUTION": execution,
        "RESULT_PHASE": "prepare",
        "RESULT_REQUEST": request,
        "RESULT_RECEIPT": receipt,
        "EXPECTED_BOUND": json.dumps(
            _identity("4"), sort_keys=True, separators=(",", ":"),
        ),
    }
    result = _run("result", execution, env=env)
    assert result.returncode == 0, result.stderr
    collected = json.loads(result.stdout)
    assert collected["phase"] == "prepare"
    assert collected["execution"]["name"] == execution
    assert collected["operator_receipt"]["result"]["manifest_identity"] == manifest
    calls = (tmp_path / "calls.log").read_text()
    assert "run jobs executions describe " + execution in calls
    assert (
        'labels."run.googleapis.com/execution_name"="' + execution + '"'
        in calls
    )
    assert "run jobs execute" not in calls
    assert "run jobs update" not in calls

    duplicate_env = {**env, "RESULT_DUPLICATE": "1"}
    duplicate = _run("result", execution, env=duplicate_env)
    assert duplicate.returncode == 2
    assert "operator stdout receipt count differs" in duplicate.stderr


@pytest.mark.parametrize(
    ("phase", "request_body", "bound", "inner", "command", "uses_realized"),
    [
        (
            "task0",
            {"manifest_identity": _identity("a")},
            _identity("a"),
            {
                "complete": True,
                "manifest_identity": _identity("a"),
                "package_sha256": "1" * 64,
                "publication_performed": False,
                "schema_version": "corpus-r6-broad-admission-task0-smoke/v1",
                "slate_id": "2023-w01",
                "smoke_result_sha256": "2" * 64,
                "source_ordinal": 0,
                "task_result_sha256": "3" * 64,
                "union_lineups_sha256": "4" * 64,
                "uses_realized_outcomes": False,
            },
            "task",
            False,
        ),
        (
            "collect",
            {"execution_id": JOB + "-tsk01", "manifest_identity": _identity("b")},
            _identity("b"),
            {
                "collect_result_sha256": "1" * 64,
                "complete": True,
                "root_published_last": True,
                "schema_version": "corpus-r6-broad-admission-collect-result/v1",
                "task_count": 54,
                "terminal_identity": _identity("c"),
                "terminal_sha256": "2" * 64,
                "uses_realized_outcomes": False,
            },
            "collect",
            False,
        ),
        (
            "reopen",
            {"terminal_identity": _identity("c")},
            _identity("c"),
            {
                "all_packages_independently_recomputed": True,
                "all_tasks_and_parents_generation_exact_reopened": True,
                "catalog_reread": False,
                "complete": True,
                "outcome_reread": False,
                "package_lattice_sha256": "1" * 64,
                "reopen_result_sha256": "2" * 64,
                "schema_version": "corpus-r6-broad-admission-reopen-result/v1",
                "task_count": 54,
                "terminal_identity": _identity("c"),
                "uses_realized_outcomes": False,
            },
            "reopen",
            False,
        ),
        (
            "grade",
            {
                "outcome_authority_identity": _identity("d"),
                "terminal_identity": _identity("c"),
            },
            _identity("c"),
            {
                "complete": True,
                "descriptive_only": True,
                "grade_result_sha256": "1" * 64,
                "grade_root_published_last": True,
                "grade_terminal_identity": _identity("e"),
                "grade_terminal_sha256": "2" * 64,
                "program_grade_sha256": "3" * 64,
                "schema_version": "corpus-r6-broad-admission-grade-result/v1",
            },
            "grade",
            True,
        ),
        (
            "grade-reopen",
            {"grade_terminal_identity": _identity("e")},
            _identity("e"),
            {
                "catalog_reread": False,
                "complete": True,
                "grade_reopen_result_sha256": "1" * 64,
                "grade_terminal_identity": _identity("e"),
                "historical_outcome_lease_reread": False,
                "outcome_snapshot_reread": False,
                "persisted_derived_scores_replayed": True,
                "program_grade_independently_recomputed": True,
                "program_grade_sha256": "2" * 64,
                "schema_version": "corpus-r6-broad-admission-grade-reopen-result/v1",
                "score_free_lattice_and_parents_replayed": True,
                "uses_realized_outcomes": True,
            },
            "grade-reopen",
            True,
        ),
    ],
)
def test_result_contract_for_every_remaining_single_task_phase(
    tmp_path: Path,
    phase: str,
    request_body: dict[str, object],
    bound: dict[str, object],
    inner: dict[str, object],
    command: str,
    uses_realized: bool,
) -> None:
    execution = JOB + "-" + {
        "task0": "tsm01",
        "collect": "col01",
        "reopen": "rop01",
        "grade": "grd01",
        "grade-reopen": "grp01",
    }[phase]
    request = json.dumps(request_body, sort_keys=True, separators=(",", ":"))
    receipt = json.dumps({
        "command": command,
        "complete": True,
        "result": inner,
        "schema_version": "corpus-r6-broad-admission-cli-receipt/v1",
        "task0_nonpublishing_smoke": phase == "task0",
        "uses_realized_outcomes": uses_realized,
    }, sort_keys=True, separators=(",", ":"))
    env = {
        **_environment(tmp_path),
        "RESULT_EXECUTION": execution,
        "RESULT_PHASE": phase,
        "RESULT_REQUEST": request,
        "RESULT_RECEIPT": receipt,
        "EXPECTED_BOUND": json.dumps(bound, sort_keys=True, separators=(",", ":")),
    }
    result = _run("result", execution, env=env)
    assert result.returncode == 0, result.stderr
    collected = json.loads(result.stdout)
    assert collected["phase"] == phase
    assert collected["operator_receipt"]["uses_realized_outcomes"] is uses_realized
