#!/usr/bin/env python3
"""Strict transport and terminal harvester for the LR8 source smoke.

This file owns transport only.  The outcome-blind source science remains in
``run_lr8_training_source.py`` and ``nfl_dfs.research.lr8_training_source``.
The harvester proves strict Cloud Run terminal success before it inventories
or opens any result object, generation-pins every retained byte, and replays
the frozen smoke/result/evidence contract without refitting the projection
model or reading any realized target/candidate outcome.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any, Final


ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import run_lr8_training_source as source_runner  # noqa: E402
from nfl_dfs.research import lr8_historical_arm as lr8  # noqa: E402
from nfl_dfs.research import lr8_exact_solvers as exact_solvers  # noqa: E402
from nfl_dfs.research import lr8_training_source as training  # noqa: E402
from nfl_dfs.research import residual_world_columns as rw  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
BUCKET: Final = "nfl-predictions-503414-raw"
LOCATION: Final = "US"
ATTEMPT_ID: Final = "20260821-lr8-training-source-smoke-v2"
PREDECESSOR_ATTEMPT_ID: Final = "20260820-lr8-training-source-smoke-v1"
PREDECESSOR_EXECUTION: Final = "atlas-md-prefix-r4-smoke-wqzpc"
PREDECESSOR_FAILURE_CLOSURE_SHA256: Final = (
    "79d496df434dbe007041cc51a356052ff15a5069ce0059d3418aa00a6f1d2636"
)
PREDECESSOR_EXECUTION_METADATA_SHA256: Final = (
    "2c357f17410f61868657a55ea14206641054d1da06f165f0cd65c620b0933ca6"
)
JOB: Final = "atlas-md-prefix-r4-smoke"
JOB_UID: Final = "51545eb0-59e4-424e-91c9-98dd318285f4"
SERVICE_ACCOUNT: Final = "817589974517-compute@developer.gserviceaccount.com"
BUILD_SERVICE_ACCOUNT: Final = (
    "projects/nfl-predictions-503414/serviceAccounts/" + SERVICE_ACCOUNT
)
BUILD_LOGS_BUCKET: Final = (
    "gs://817589974517.cloudbuild-logs.googleusercontent.com"
)
GIT_SOURCE_URL: Final = (
    "https://github.com/espechtsoftware/nfl-predictions.git"
)
IMAGE_REPOSITORY: Final = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs"
)
CPU: Final = "8"
MEMORY: Final = "32Gi"
TIMEOUT_SECONDS: Final = "21600"
EVIDENCE_ROOT: Final = "/tmp/lr8-training-source-smoke-evidence"

CATALOG_TABLE: Final = (
    f"{PROJECT}.nfl_predictions.slate_player_features"
)
CANDIDATE_TABLE: Final = (
    f"{PROJECT}.nfl_predictions.replay_candidates_staging"
)
PIT_TABLE: Final = f"{PROJECT}.nfl_features.player_week_training"
TABPFN_TABLE: Final = (
    f"{PROJECT}.nfl_features.{source_runner.TABPFN_TABLE_NAME}"
)

RESULT_PREFIX: Final = (
    f"gs://{BUCKET}/research/lr8-training-source/{ATTEMPT_ID}"
)
SMOKE_MANIFEST_URI: Final = RESULT_PREFIX + "/smoke-manifest.json"
SMOKE_SOLVE_FREEZE_URI: Final = RESULT_PREFIX + "/smoke-solve-freeze.json"
GOVERNANCE_PREFIX: Final = (
    f"gs://{BUCKET}/research-governance/lr8-training-source-smoke/"
    f"{ATTEMPT_ID}"
)
LAUNCH_MANIFEST_URI: Final = GOVERNANCE_PREFIX + "/launch-manifest.json"
LAUNCH_INTENT_URI: Final = GOVERNANCE_PREFIX + "/launch-intent.json"
EXECUTION_CLAIM_URI: Final = GOVERNANCE_PREFIX + "/execution-claim.json"
DEFAULT_OUT: Final = (
    ROOT / "reports/lr8-training-source-smoke-runs" / ATTEMPT_ID
)
PREDECESSOR_OUT: Final = (
    ROOT / "reports/lr8-training-source-smoke-runs" /
    PREDECESSOR_ATTEMPT_ID
)

IMPLEMENTATION_PATHS: Final = {
    "source_runner": "scripts/run_lr8_training_source.py",
    "training_source": "src/nfl_dfs/research/lr8_training_source.py",
    "replay_source": "src/nfl_dfs/research/lr8_replay_source.py",
    "exact_solver": "src/nfl_dfs/research/lr8_exact_solvers.py",
    "finisher": "scripts/finish_lr8_training_source_smoke.py",
    "launcher": "scripts/cloud_lr8_training_source_smoke.sh",
    "watcher": "scripts/watch_lr8_training_source_smoke_queue.sh",
    "transport_tests": "tests/test_lr8_training_source_smoke_transport.py",
    "v2_protocol": (
        "reports/2026-08-21-lr8-training-source-smoke-v2-"
        "salary-boundary-repair-protocol.md"
    ),
    "dockerfile": "Dockerfile",
    "cloudbuild": "cloudbuild.yaml",
}
TRANSPORT_REPAIR_ENV: Final = {
    "finisher": "LR8_SMOKE_FINISHER_REPAIR_SHA256",
    "launcher": "LR8_SMOKE_LAUNCHER_REPAIR_SHA256",
    "watcher": "LR8_SMOKE_WATCHER_REPAIR_SHA256",
}
REQUIRED_BUILD_SMOKES: Final = (
    "python scripts/run_lr8_training_source.py --help >/dev/null",
    "python scripts/finish_lr8_training_source_smoke.py --help >/dev/null",
    "bash -n scripts/cloud_lr8_training_source_smoke.sh",
    "bash -n scripts/watch_lr8_training_source_smoke_queue.sh",
)

_SHA256_RE: Final = re.compile(r"[0-9a-f]{64}")
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}")
_BUILD_RE: Final = re.compile(r"[0-9A-Za-z-]{8,80}")
_JOB_RE: Final = re.compile(r"[a-z][a-z0-9-]{2,62}")
_UID_RE: Final = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}"
)


class LR8SmokeTransportError(RuntimeError):
    """Fail-closed LR8 smoke transport violation."""


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def _strict_json_bytes(raw: bytes, *, label: str) -> Any:
    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise LR8SmokeTransportError(f"LR8 {label} is not strict JSON") from exc

    def walk(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise LR8SmokeTransportError(
                f"LR8 {label} contains non-finite JSON"
            )
        if isinstance(item, dict):
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(value)
    return value


def _canonical_json(value: object) -> bytes:
    try:
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LR8SmokeTransportError("LR8 value is not canonical JSON") from exc


def _sha_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _sha_path(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise LR8SmokeTransportError(f"LR8 required file is absent: {path}")
    return _sha_bytes(path.read_bytes())


def _load_json(path: Path, *, label: str) -> Any:
    if path.is_symlink() or not path.is_file():
        raise LR8SmokeTransportError(f"LR8 {label} is absent")
    return _strict_json_bytes(path.read_bytes(), label=label)


def _write_exclusive_or_equal(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise LR8SmokeTransportError(
                f"LR8 immutable local file differs: {path}"
            )


def _hex(value: object, *, label: str) -> str:
    text = str(value)
    if _SHA256_RE.fullmatch(text) is None:
        raise LR8SmokeTransportError(f"LR8 {label} differs")
    return text


def _commit(value: object) -> str:
    text = str(value)
    if _COMMIT_RE.fullmatch(text) is None:
        raise LR8SmokeTransportError("LR8 source commit differs")
    return text


def _positive_int(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        raise LR8SmokeTransportError(f"LR8 {label} differs")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise LR8SmokeTransportError(f"LR8 {label} differs") from exc
    if str(result) != str(value) or result <= 0:
        raise LR8SmokeTransportError(f"LR8 {label} differs")
    return result


def _nonnegative_int(value: object, *, label: str) -> int:
    if isinstance(value, bool):
        raise LR8SmokeTransportError(f"LR8 {label} differs")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise LR8SmokeTransportError(f"LR8 {label} differs") from exc
    if str(result) != str(value) or result < 0:
        raise LR8SmokeTransportError(f"LR8 {label} differs")
    return result


def _utc_timestamp(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise LR8SmokeTransportError(f"LR8 {label} differs")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LR8SmokeTransportError(f"LR8 {label} differs") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise LR8SmokeTransportError(f"LR8 {label} differs")
    return value


def _image_tag(code_sha: str) -> str:
    return f"{IMAGE_REPOSITORY}:lr8-smoke-{_commit(code_sha)[:7]}"


def _immutable_image(value: object) -> str:
    text = str(value)
    if re.fullmatch(
        rf"{re.escape(IMAGE_REPOSITORY)}@sha256:[0-9a-f]{{64}}", text,
    ) is None:
        raise LR8SmokeTransportError("LR8 immutable image differs")
    return text


def _job_name(value: object) -> str:
    text = str(value)
    if _JOB_RE.fullmatch(text) is None or text != JOB:
        raise LR8SmokeTransportError("LR8 reused-job name differs")
    return text


def _job_uid(value: object) -> str:
    text = str(value)
    if _UID_RE.fullmatch(text) is None or text != JOB_UID:
        raise LR8SmokeTransportError("LR8 reused-job UID differs")
    return text


GitSourceLoader = Callable[[str, str], bytes]


def _git_blob(code_sha: str, relative: str) -> bytes:
    commit = _commit(code_sha)
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise LR8SmokeTransportError("LR8 Git source path differs")
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{commit}:{relative}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0 or not completed.stdout:
        raise LR8SmokeTransportError(
            f"LR8 exact Git source is unavailable: {relative}"
        )
    return completed.stdout


def _implementation_receipts(
    *, code_sha: str, git_source_loader: GitSourceLoader = _git_blob,
) -> dict[str, dict[str, str]]:
    commit = _commit(code_sha)
    result: dict[str, dict[str, str]] = {}
    for key, relative in IMPLEMENTATION_PATHS.items():
        raw = git_source_loader(commit, relative)
        if not isinstance(raw, bytes) or not raw:
            raise LR8SmokeTransportError(
                f"LR8 implementation source differs: {relative}"
            )
        result[key] = {"path": relative, "sha256": _sha_bytes(raw)}
    return result


def _validate_current_transport(
    manifest: Mapping[str, Any], *, root: Path = ROOT,
    env: Mapping[str, str] | None = None,
) -> None:
    implementation = manifest.get("implementation")
    if not isinstance(implementation, Mapping):
        raise LR8SmokeTransportError("LR8 implementation manifest differs")
    values = os.environ if env is None else env
    for key in ("finisher", "launcher", "watcher"):
        row = implementation.get(key)
        relative = IMPLEMENTATION_PATHS[key]
        if not isinstance(row, Mapping) or row.get("path") != relative:
            raise LR8SmokeTransportError(
                f"LR8 transport implementation row differs: {key}"
            )
        expected = _hex(row.get("sha256"), label=f"{key} SHA")
        current = _sha_path(root / relative)
        if current == expected:
            continue
        repair_name = TRANSPORT_REPAIR_ENV[key]
        if values.get(repair_name) != current:
            raise LR8SmokeTransportError(
                f"LR8 frozen transport changed: {relative}"
            )


def _expected_cloud_build_steps(image_tag: str) -> list[dict[str, Any]]:
    """Return the exact committed three-step build plus LR8 image smokes."""
    full_test = (
        "apt-get update\n"
        "apt-get install -y --no-install-recommends git libgomp1\n"
        "pip install --no-cache-dir '.[gcp,app,dev]'\n"
        "PYTHONPATH=. pytest\n"
    )
    smoke_commands = (
        ("python", "run_atlas_matched_diversity_mvp.py --help >/dev/null"),
        ("python", "run_atlas_historical_score_diagnostic.py --help >/dev/null"),
        ("python", "run_atlas_historical_score_diagnostic_v3.py --help >/dev/null"),
        ("python", "run_atlas_historical_score_diagnostic_v4.py --help >/dev/null"),
        ("python", "run_constraint_lattice_scorefree.py --help >/dev/null"),
        ("python", "aggregate_constraint_lattice_scorefree.py --help >/dev/null"),
        ("python", "run_constraint_lattice_support_census.py --help >/dev/null"),
        ("python", "aggregate_constraint_lattice_support_census.py --help >/dev/null"),
        ("python", "run_constraint_lattice_resource_preflight.py --help >/dev/null"),
        ("python", "run_recourse_aware_initial_scorefree.py --help >/dev/null"),
        ("python", "aggregate_recourse_aware_initial_scorefree.py --help >/dev/null"),
        ("python", "run_coherent_market_state_scorefree.py --help >/dev/null"),
        ("python", "aggregate_coherent_market_state_scorefree.py --help >/dev/null"),
        ("python", "run_coherent_market_state_historical_score.py --help >/dev/null"),
        ("python", "run_production_law_dependence_source_lock.py --help >/dev/null"),
        ("python", "run_production_law_dependence_remeasurement.py --help >/dev/null"),
        ("python", "run_a2a_rank_factor_split_census.py --help >/dev/null"),
        ("python", "run_a2a_production_law_dependence_remeasurement.py --help >/dev/null"),
        ("python", "finish_a2a_production_law_dependence_remeasurement.py --help >/dev/null"),
        ("bash", "cloud_a2a_production_law_dependence_remeasurement.sh"),
        ("bash", "watch_a2a_production_law_dependence_queue.sh"),
        ("python", "run_b1_corpus_tail_model.py --help >/dev/null"),
        ("python", "finish_b1_corpus_tail_model.py --help >/dev/null"),
        ("bash", "cloud_b1_corpus_tail_model.sh"),
        ("bash", "watch_b1_corpus_tail_queue.sh"),
        ("python", "run_b1_corpus_tail_panel_producer.py --help >/dev/null"),
        ("python", "run_b1_corpus_tail_shadow_transport.py --help >/dev/null"),
        ("python", "run_b1_authoritative_settlement.py --help >/dev/null"),
        ("bash", "cloud_b1_corpus_tail_shadow.sh"),
        ("python", "run_atlas_minimal_world_selection_c.py --help >/dev/null"),
        ("python", "run_a7_select_ladder.py --help >/dev/null"),
        ("python", "freeze_a7_select_ladder.py --help >/dev/null"),
        ("python", "finish_a7_select_ladder.py --help >/dev/null"),
        ("bash", "cloud_a7_select_ladder.sh"),
        ("bash", "watch_a7_select_ladder_queue.sh"),
        ("python", "run_lr8_training_source.py --help >/dev/null"),
        ("python", "finish_lr8_training_source_smoke.py --help >/dev/null"),
        ("bash", "cloud_lr8_training_source_smoke.sh"),
        ("bash", "watch_lr8_training_source_smoke_queue.sh"),
    )
    smoke = "".join(
        f"docker run --rm '{image_tag}' \\\n"
        f"  {kind} scripts/{command}\n"
        if kind == "python"
        else f"docker run --rm '{image_tag}' \\\n"
        f"  bash -n scripts/{command}\n"
        for kind, command in smoke_commands
    )
    return [
        {
            "name": "python:3.11-slim", "id": "full-test-suite",
            "entrypoint": "bash", "args": ["-ceu", full_test],
        },
        {
            "name": "gcr.io/cloud-builders/docker", "id": "build-image",
            "entrypoint": "", "args": ["build", "-t", image_tag, "."],
        },
        {
            "name": "gcr.io/cloud-builders/docker",
            "id": "smoke-atlas-mvp-runner", "entrypoint": "bash",
            "args": ["-ceu", smoke],
        },
    ]


_STEP_KEYS: Final = (
    "name", "id", "entrypoint", "args", "env", "dir", "secretEnv",
    "allowFailure", "allowExitCodes", "waitFor", "timeout", "script",
    "volumes", "automapSubstitutions",
)


def _normalized_expected_step(value: Mapping[str, Any]) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "entrypoint": "", "args": [], "env": [], "dir": "",
        "secretEnv": [], "allowFailure": False, "allowExitCodes": [],
        "waitFor": [], "timeout": "", "script": "", "volumes": [],
        "automapSubstitutions": False,
    }
    return {key: value.get(key, defaults.get(key)) for key in _STEP_KEYS}


def _normalized_actual_step(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("status") != "SUCCESS" or value.get("exitCode", 0) != 0:
        raise LR8SmokeTransportError("LR8 Cloud Build step did not succeed")
    return _normalized_expected_step(value)


def _validate_build_metadata(
    value: object, *, build_id: str, image: str, code_sha: str,
    git_source_loader: GitSourceLoader = _git_blob,
) -> str:
    commit = _commit(code_sha)
    immutable = _immutable_image(image)
    if _BUILD_RE.fullmatch(build_id) is None or not isinstance(value, Mapping):
        raise LR8SmokeTransportError("LR8 immutable build identity differs")
    source = {"url": GIT_SOURCE_URL, "revision": commit}
    provenance = value.get("sourceProvenance")
    if value.get("id") != build_id or value.get("source") != {
        "gitSource": source
    } or not isinstance(provenance, Mapping) or provenance.get(
        "resolvedGitSource"
    ) != source or provenance.get("fileHashes") not in (None, {}):
        raise LR8SmokeTransportError("LR8 Cloud Build direct-Git source differs")
    tag = _image_tag(commit)
    substitutions = value.get("substitutions")
    if not isinstance(substitutions, Mapping) or substitutions.get("_IMAGE") != tag:
        raise LR8SmokeTransportError("LR8 Cloud Build image substitution differs")
    declared = {
        str(substitutions[key]) for key in ("COMMIT_SHA", "_CODE_SHA")
        if key in substitutions
    }
    if declared and declared != {commit}:
        raise LR8SmokeTransportError("LR8 Cloud Build declared commit differs")
    cloudbuild_source = git_source_loader(commit, "cloudbuild.yaml")
    if not isinstance(cloudbuild_source, bytes) or any(
        marker.encode("utf-8") not in cloudbuild_source
        for marker in REQUIRED_BUILD_SMOKES
    ):
        raise LR8SmokeTransportError("LR8 Cloud Build source smoke differs")
    expected_steps = _expected_cloud_build_steps(tag)
    actual_steps = value.get("steps")
    if not isinstance(actual_steps, list) or len(actual_steps) != len(expected_steps):
        raise LR8SmokeTransportError("LR8 Cloud Build step population differs")
    if [
        _normalized_actual_step(step) for step in actual_steps
        if isinstance(step, Mapping)
    ] != [
        _normalized_expected_step(step) for step in expected_steps
        if isinstance(step, Mapping)
    ] or any(not isinstance(step, Mapping) for step in actual_steps):
        raise LR8SmokeTransportError("LR8 Cloud Build steps differ")
    digest = immutable.rsplit("@", 1)[1]
    result_images = value.get("results", {}).get("images", [])
    if value.get("status") != "SUCCESS" or value.get("images") != [tag] or \
            value.get("artifacts") != {"images": [tag]} or \
            value.get("timeout") != "10800s" or \
            value.get("options", {}).get("machineType") != "E2_HIGHCPU_8" or \
            value.get("serviceAccount") != BUILD_SERVICE_ACCOUNT or \
            value.get("logsBucket") != BUILD_LOGS_BUCKET or not any(
                isinstance(row, Mapping) and row.get("name") == tag
                and row.get("digest") == digest for row in result_images
            ):
        raise LR8SmokeTransportError("LR8 build/test/image gate differs")
    return tag


def _run_script() -> str:
    return "\n".join((
        "test ! -e " + EVIDENCE_ROOT,
        "mkdir -p " + EVIDENCE_ROOT,
        "exec python scripts/run_lr8_training_source.py smoke --execute "
        f"--attempt-id {ATTEMPT_ID} --project {PROJECT} --bucket {BUCKET} "
        f"--catalog-table {CATALOG_TABLE} --candidate-table {CANDIDATE_TABLE} "
        f"--pit-table {PIT_TABLE} --tabpfn-table {TABPFN_TABLE} "
        f"--location {LOCATION} --evidence-root {EVIDENCE_ROOT}",
    ))


def _static_job_contract(*, code_sha: str, image: str) -> dict[str, Any]:
    return {
        "image": _immutable_image(image),
        "command": ["bash"],
        "args": ["-ceu", _run_script()],
        "env": {
            "ANALYSIS_IMAGE": image,
            "CODE_SHA": _commit(code_sha),
            source_runner.ENABLED_ENV: "1",
        },
        "working_dir": "",
        "volume_mounts": [],
        "volumes": [],
        "startup_probe": None,
        "tasks": 1,
        "parallelism": 1,
        "resources": {"cpu": CPU, "memory": MEMORY},
        "max_retries": 0,
        "timeout_seconds": int(TIMEOUT_SECONDS),
        "service_account": SERVICE_ACCOUNT,
    }


def _job_spec_sha256(value: Mapping[str, Any]) -> str:
    spec = value.get("spec")
    if not isinstance(spec, Mapping) or not spec:
        raise LR8SmokeTransportError("LR8 reused-job spec is absent")
    return _sha_bytes(_canonical_json(spec))


def _job_identity(
    value: object, *, job: str, job_uid: str,
) -> tuple[str, str, str]:
    name = _job_name(job)
    uid = _job_uid(job_uid)
    if not isinstance(value, Mapping):
        raise LR8SmokeTransportError("LR8 reused-job metadata differs")
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping) or metadata.get("name") != name or \
            metadata.get("uid") != uid:
        raise LR8SmokeTransportError("LR8 reused-job identity differs")
    generation = _positive_int(
        metadata.get("generation"), label="reused-job generation",
    )
    return uid, str(generation), _job_spec_sha256(value)


def _container_contract(
    *, outer: Mapping[str, Any], task: Mapping[str, Any],
    expected: Mapping[str, Any], label: str,
) -> None:
    containers = task.get("containers", [])
    if _positive_int(outer.get("taskCount"), label=f"{label} task count") != 1 \
            or _positive_int(
                outer.get("parallelism"), label=f"{label} parallelism",
            ) != 1 or not isinstance(containers, list) or len(containers) != 1:
        raise LR8SmokeTransportError(f"LR8 {label} task shape differs")
    container = containers[0]
    if not isinstance(container, Mapping):
        raise LR8SmokeTransportError(f"LR8 {label} container differs")
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, Mapping) or set(row) != {"name", "value"}
        or not isinstance(row["name"], str) or not isinstance(row["value"], str)
        for row in env_rows
    ):
        raise LR8SmokeTransportError(f"LR8 {label} environment differs")
    env = {row["name"]: row["value"] for row in env_rows}
    if len(env) != len(env_rows) or env != expected["env"] or \
            container.get("image") != expected["image"] or \
            container.get("command") != expected["command"] or \
            container.get("args") != expected["args"] or \
            container.get("workingDir", "") != expected["working_dir"] or \
            container.get("volumeMounts", []) != expected["volume_mounts"] or \
            container.get("startupProbe") not in (None, {}) or \
            container.get("resources", {}).get("limits") != expected["resources"] or \
            task.get("volumes", []) != expected["volumes"] or \
            _nonnegative_int(
                task.get("maxRetries"), label=f"{label} max retries",
            ) != expected["max_retries"] or \
            task.get("timeoutSeconds") != TIMEOUT_SECONDS or \
            task.get("serviceAccountName") != expected["service_account"]:
        raise LR8SmokeTransportError(f"LR8 {label} executable contract differs")


def _validate_job_spec(
    value: object, *, job: str, job_uid: str, code_sha: str, image: str,
) -> tuple[str, str, str]:
    identity = _job_identity(value, job=job, job_uid=job_uid)
    assert isinstance(value, Mapping)
    spec = value.get("spec", {})
    outer = spec.get("template", {}).get("spec", {}) \
        if isinstance(spec, Mapping) else {}
    task = outer.get("template", {}).get("spec", {}) \
        if isinstance(outer, Mapping) else {}
    _container_contract(
        outer=outer,
        task=task,
        expected=_static_job_contract(code_sha=code_sha, image=image),
        label="reused-job",
    )
    return identity


def _validate_job_idle(value: object) -> None:
    if not isinstance(value, list):
        raise LR8SmokeTransportError("LR8 reused-job execution census differs")
    for row in value:
        if not isinstance(row, Mapping):
            raise LR8SmokeTransportError("LR8 reused-job execution row differs")
        conditions = row.get("status", {}).get("conditions", [])
        completed = [
            item for item in conditions
            if isinstance(item, Mapping) and item.get("type") == "Completed"
        ] if isinstance(conditions, list) else []
        if len(completed) != 1 or completed[0].get("status") not in {
            "True", "False",
        }:
            raise LR8SmokeTransportError("LR8 reused job is not exact-idle")


def _validate_unscheduled(value: object, *, job: str) -> None:
    name = _job_name(job)
    if not isinstance(value, list):
        raise LR8SmokeTransportError("LR8 scheduler census differs")
    marker = f"/jobs/{name}"
    for row in value:
        if not isinstance(row, Mapping):
            raise LR8SmokeTransportError("LR8 scheduler row differs")
        target = row.get("httpTarget", {})
        uri = target.get("uri", "") if isinstance(target, Mapping) else ""
        if not isinstance(uri, str) or marker in uri:
            raise LR8SmokeTransportError("LR8 reused job is scheduled")


def _object_metadata(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "uri", "generation", "metageneration", "bytes",
    }:
        raise LR8SmokeTransportError(f"LR8 {label} metadata differs")
    uri = value.get("uri")
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        raise LR8SmokeTransportError(f"LR8 {label} URI differs")
    generation = str(_positive_int(value.get("generation"), label=f"{label} generation"))
    metageneration = str(_positive_int(
        value.get("metageneration"), label=f"{label} metageneration",
    ))
    size = _nonnegative_int(value.get("bytes"), label=f"{label} bytes")
    return {
        "uri": uri, "generation": generation,
        "metageneration": metageneration, "bytes": size,
    }


def _validate_empty_inventory(value: object, *, label: str) -> None:
    if value != []:
        raise LR8SmokeTransportError(f"LR8 {label} prefix is not empty")


def _validate_governance_inventory(
    value: object, *, expected: Sequence[Mapping[str, Any]], label: str,
) -> None:
    if not isinstance(value, list):
        raise LR8SmokeTransportError(f"LR8 {label} inventory differs")
    observed = [_object_metadata(row, label=label) for row in value]
    wanted = [_object_metadata(row, label=label) for row in expected]
    if observed != wanted:
        raise LR8SmokeTransportError(f"LR8 {label} inventory differs")


def _validate_prepare_inputs(
    *, code_sha: str, image: str, build_id: str, job: str, job_uid: str,
    build_metadata: object, job_before: object, executions_before: object,
    schedulers_before: object, result_inventory_before: object,
    governance_inventory_before: object,
    git_source_loader: GitSourceLoader = _git_blob,
) -> None:
    _validate_build_metadata(
        build_metadata,
        build_id=build_id,
        image=image,
        code_sha=code_sha,
        git_source_loader=git_source_loader,
    )
    _implementation_receipts(
        code_sha=code_sha, git_source_loader=git_source_loader,
    )
    _job_identity(job_before, job=job, job_uid=job_uid)
    _validate_job_idle(executions_before)
    _validate_unscheduled(schedulers_before, job=job)
    _validate_empty_inventory(
        result_inventory_before, label="result attempt",
    )
    _validate_empty_inventory(
        governance_inventory_before, label="governance attempt",
    )


def _build_launch_manifest(
    *, code_sha: str, image: str, build_id: str, job: str, job_uid: str,
    build_metadata: object, job_before: object, job_after: object,
    executions_before: object, executions_after: object,
    schedulers_before: object, schedulers_after: object,
    result_inventory_before: object, result_inventory_after: object,
    governance_inventory_before: object, governance_inventory_after: object,
    prepared_at: str, git_source_loader: GitSourceLoader = _git_blob,
) -> dict[str, Any]:
    _validate_prepare_inputs(
        code_sha=code_sha, image=image, build_id=build_id, job=job,
        job_uid=job_uid, build_metadata=build_metadata, job_before=job_before,
        executions_before=executions_before, schedulers_before=schedulers_before,
        result_inventory_before=result_inventory_before,
        governance_inventory_before=governance_inventory_before,
        git_source_loader=git_source_loader,
    )
    _validate_job_idle(executions_after)
    _validate_unscheduled(schedulers_after, job=job)
    _validate_empty_inventory(result_inventory_after, label="result attempt")
    _validate_empty_inventory(
        governance_inventory_after, label="governance attempt",
    )
    prior_uid, prior_generation, prior_spec = _job_identity(
        job_before, job=job, job_uid=job_uid,
    )
    uid, generation, spec_sha = _validate_job_spec(
        job_after, job=job, job_uid=job_uid, code_sha=code_sha, image=image,
    )
    if uid != prior_uid or int(generation) != int(prior_generation) + 1:
        raise LR8SmokeTransportError("LR8 reused-job generation chain differs")
    tag = _validate_build_metadata(
        build_metadata,
        build_id=build_id,
        image=image,
        code_sha=code_sha,
        git_source_loader=git_source_loader,
    )
    implementation = _implementation_receipts(
        code_sha=code_sha, git_source_loader=git_source_loader,
    )
    manifest = {
        "version": "lr8-training-source-smoke-launch-manifest-v1",
        "status": "prepared-before-one-outcome-blind-smoke",
        "attempt_id": ATTEMPT_ID,
        "code": {"commit_sha": _commit(code_sha)},
        "image": {"uri": _immutable_image(image), "tag": tag},
        "build": {
            "id": build_id,
            "metadata_sha256": _sha_bytes(_canonical_json(build_metadata)),
        },
        "job": {
            "name": _job_name(job),
            "uid": _job_uid(job_uid),
            "prior_generation": prior_generation,
            "prior_spec_sha256": prior_spec,
            "generation": generation,
            "spec_sha256": spec_sha,
            "service_account": SERVICE_ACCOUNT,
            "update_mode": "update-existing-only-no-create-delete",
            "scheduler_target_absent": True,
        },
        "static_job_contract": _static_job_contract(
            code_sha=code_sha, image=image,
        ),
        "implementation": implementation,
        "output": {
            "prefix": RESULT_PREFIX,
            "smoke_manifest_uri": SMOKE_MANIFEST_URI,
            "smoke_solve_freeze_uri": SMOKE_SOLVE_FREEZE_URI,
            "prelaunch_inventory": [],
            "create_only": True,
        },
        "governance": {
            "prefix": GOVERNANCE_PREFIX,
            "launch_manifest_uri": LAUNCH_MANIFEST_URI,
            "launch_intent_uri": LAUNCH_INTENT_URI,
            "execution_claim_uri": EXECUTION_CLAIM_URI,
            "create_only": True,
        },
        "source_contract": {
            "mode": "smoke",
            "season": 2019,
            "week": 1,
            "block": "R0",
            "projection_seed": 0,
            "worlds": training.WORLDS_PER_BLOCK,
            "unique_dk_only_optima": training.UNIQUE_OPTIMA_PER_BLOCK,
            "maximum_ordered_solves": training.MAX_SOLVE_ATTEMPTS_PER_BLOCK,
            "target_player_labels_read": False,
            "candidate_labels_read": False,
            "actual_score_queried": False,
        },
        "preflight": {
            "prepared_at": _utc_timestamp(prepared_at, label="prepare time"),
            "job_idle_before_update": True,
            "job_idle_after_update": True,
            "schedulers_before_sha256": _sha_bytes(
                _canonical_json(schedulers_before)
            ),
            "schedulers_after_sha256": _sha_bytes(
                _canonical_json(schedulers_after)
            ),
            "result_inventory_before_sha256": _sha_bytes(
                _canonical_json(result_inventory_before)
            ),
            "result_inventory_after_sha256": _sha_bytes(
                _canonical_json(result_inventory_after)
            ),
            "governance_inventory_before_sha256": _sha_bytes(
                _canonical_json(governance_inventory_before)
            ),
            "governance_inventory_after_sha256": _sha_bytes(
                _canonical_json(governance_inventory_after)
            ),
        },
        "uses_realized_target_or_candidate_outcomes": False,
        "historical_outcome_lease_required": False,
        "historical_outcome_lease_acquired": False,
        "historical_retry_licensed": False,
        "full_source_build_licensed": False,
        "production_change_licensed": False,
    }
    _validate_launch_manifest(
        manifest, git_source_loader=git_source_loader, validate_current=False,
    )
    return manifest


def _validate_launch_manifest(
    value: object, *, git_source_loader: GitSourceLoader = _git_blob,
    validate_current: bool = True, root: Path = ROOT,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LR8SmokeTransportError("LR8 launch manifest differs")
    fixed = {
        "version": "lr8-training-source-smoke-launch-manifest-v1",
        "status": "prepared-before-one-outcome-blind-smoke",
        "attempt_id": ATTEMPT_ID,
        "uses_realized_target_or_candidate_outcomes": False,
        "historical_outcome_lease_required": False,
        "historical_outcome_lease_acquired": False,
        "historical_retry_licensed": False,
        "full_source_build_licensed": False,
        "production_change_licensed": False,
    }
    if any(value.get(key) != expected for key, expected in fixed.items()):
        raise LR8SmokeTransportError("LR8 launch manifest fixed law differs")
    code = value.get("code")
    image = value.get("image")
    if not isinstance(code, dict) or set(code) != {"commit_sha"} or \
            not isinstance(image, dict) or set(image) != {"uri", "tag"}:
        raise LR8SmokeTransportError("LR8 launch manifest code/image differs")
    code_sha = _commit(code.get("commit_sha"))
    image_uri = _immutable_image(image.get("uri"))
    if image.get("tag") != _image_tag(code_sha):
        raise LR8SmokeTransportError("LR8 launch manifest image tag differs")
    build = value.get("build")
    if not isinstance(build, dict) or set(build) != {
        "id", "metadata_sha256",
    } or _BUILD_RE.fullmatch(str(build.get("id", ""))) is None:
        raise LR8SmokeTransportError("LR8 launch manifest build differs")
    _hex(build.get("metadata_sha256"), label="build metadata SHA")
    job = value.get("job")
    if not isinstance(job, dict) or job.get("name") is None or \
            job.get("uid") is None:
        raise LR8SmokeTransportError("LR8 launch manifest job differs")
    _job_name(job["name"])
    _job_uid(job["uid"])
    prior_generation = _positive_int(
        job.get("prior_generation"), label="prior job generation",
    )
    generation = _positive_int(job.get("generation"), label="job generation")
    if generation != prior_generation + 1 or job.get("service_account") != \
            SERVICE_ACCOUNT or job.get("update_mode") != \
            "update-existing-only-no-create-delete" or \
            job.get("scheduler_target_absent") is not True:
        raise LR8SmokeTransportError("LR8 launch manifest job law differs")
    _hex(job.get("prior_spec_sha256"), label="prior job spec SHA")
    _hex(job.get("spec_sha256"), label="job spec SHA")
    if value.get("static_job_contract") != _static_job_contract(
        code_sha=code_sha, image=image_uri,
    ):
        raise LR8SmokeTransportError("LR8 launch manifest job contract differs")
    if value.get("output") != {
        "prefix": RESULT_PREFIX,
        "smoke_manifest_uri": SMOKE_MANIFEST_URI,
        "smoke_solve_freeze_uri": SMOKE_SOLVE_FREEZE_URI,
        "prelaunch_inventory": [],
        "create_only": True,
    } or value.get("governance") != {
        "prefix": GOVERNANCE_PREFIX,
        "launch_manifest_uri": LAUNCH_MANIFEST_URI,
        "launch_intent_uri": LAUNCH_INTENT_URI,
        "execution_claim_uri": EXECUTION_CLAIM_URI,
        "create_only": True,
    }:
        raise LR8SmokeTransportError("LR8 launch manifest output differs")
    if value.get("source_contract") != {
        "mode": "smoke", "season": 2019, "week": 1, "block": "R0",
        "projection_seed": 0, "worlds": training.WORLDS_PER_BLOCK,
        "unique_dk_only_optima": training.UNIQUE_OPTIMA_PER_BLOCK,
        "maximum_ordered_solves": training.MAX_SOLVE_ATTEMPTS_PER_BLOCK,
        "target_player_labels_read": False,
        "candidate_labels_read": False,
        "actual_score_queried": False,
    }:
        raise LR8SmokeTransportError("LR8 launch source contract differs")
    implementation = value.get("implementation")
    expected_implementation = _implementation_receipts(
        code_sha=code_sha, git_source_loader=git_source_loader,
    )
    if implementation != expected_implementation:
        raise LR8SmokeTransportError("LR8 exact implementation source differs")
    preflight = value.get("preflight")
    if not isinstance(preflight, dict):
        raise LR8SmokeTransportError("LR8 launch preflight differs")
    _utc_timestamp(preflight.get("prepared_at"), label="prepare time")
    if preflight.get("job_idle_before_update") is not True or \
            preflight.get("job_idle_after_update") is not True:
        raise LR8SmokeTransportError("LR8 launch idle preflight differs")
    for key in (
        "schedulers_before_sha256", "schedulers_after_sha256",
        "result_inventory_before_sha256", "result_inventory_after_sha256",
        "governance_inventory_before_sha256",
        "governance_inventory_after_sha256",
    ):
        _hex(preflight.get(key), label=key)
    if validate_current:
        _validate_current_transport(value, root=root, env=env)
    return value


def _receipt(value: object, *, uri: str, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "uri", "generation", "metageneration", "sha256", "bytes",
    }:
        raise LR8SmokeTransportError(f"LR8 {label} receipt differs")
    if value.get("uri") != uri:
        raise LR8SmokeTransportError(f"LR8 {label} URI differs")
    return {
        "uri": uri,
        "generation": str(_positive_int(
            value.get("generation"), label=f"{label} generation",
        )),
        "metageneration": str(_positive_int(
            value.get("metageneration"), label=f"{label} metageneration",
        )),
        "sha256": _hex(value.get("sha256"), label=f"{label} SHA"),
        "bytes": _nonnegative_int(value.get("bytes"), label=f"{label} bytes"),
    }


def _result_receipt(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "uri", "generation", "sha256", "bytes",
    }:
        raise LR8SmokeTransportError(f"LR8 {label} result receipt differs")
    uri = value.get("uri")
    if not isinstance(uri, str) or not uri.startswith(RESULT_PREFIX + "/"):
        raise LR8SmokeTransportError(f"LR8 {label} result URI differs")
    return {
        "uri": uri,
        "generation": str(_positive_int(
            value.get("generation"), label=f"{label} generation",
        )),
        "sha256": _hex(value.get("sha256"), label=f"{label} SHA"),
        "bytes": _nonnegative_int(value.get("bytes"), label=f"{label} bytes"),
    }


class _StorageReader:
    """Generation-aware GCS access used only after the caller's gates."""

    def __init__(self, *, project: str = PROJECT):
        from google.cloud import storage

        self.client = storage.Client(project=project)

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        if not isinstance(uri, str) or not uri.startswith("gs://"):
            raise LR8SmokeTransportError("LR8 GCS URI differs")
        bucket, separator, name = uri.removeprefix("gs://").partition("/")
        if not bucket or not separator or not name:
            raise LR8SmokeTransportError("LR8 GCS URI differs")
        return bucket, name

    @staticmethod
    def _meta(bucket: str, blob: Any) -> dict[str, Any]:
        return _object_metadata({
            "uri": f"gs://{bucket}/{blob.name}",
            "generation": str(blob.generation),
            "metageneration": str(blob.metageneration),
            "bytes": int(blob.size or 0),
        }, label="GCS object")

    def inventory(self, prefix: str) -> list[dict[str, Any]]:
        bucket, name = self._parts(prefix)
        rows = [
            self._meta(bucket, blob)
            for blob in self.client.list_blobs(bucket, prefix=name)
        ]
        rows.sort(key=lambda row: row["uri"])
        if len(rows) != len({row["uri"] for row in rows}):
            raise LR8SmokeTransportError("LR8 GCS inventory duplicates URI")
        return rows

    def load(self, metadata: Mapping[str, Any]) -> tuple[dict[str, Any], bytes]:
        expected = _object_metadata(metadata, label="GCS load")
        bucket, name = self._parts(expected["uri"])
        generation = int(expected["generation"])
        blob = self.client.bucket(bucket).blob(name, generation=generation)
        blob.reload(if_generation_match=generation)
        observed = self._meta(bucket, blob)
        if observed != expected:
            raise LR8SmokeTransportError("LR8 pinned GCS metadata differs")
        raw = blob.download_as_bytes(if_generation_match=generation)
        if len(raw) != expected["bytes"]:
            raise LR8SmokeTransportError("LR8 pinned GCS bytes differ")
        return observed, raw

    def create(self, uri: str, raw: bytes) -> dict[str, Any]:
        from google.api_core.exceptions import PreconditionFailed

        bucket, name = self._parts(uri)
        blob = self.client.bucket(bucket).blob(name)
        try:
            blob.upload_from_string(
                raw, content_type="application/json", if_generation_match=0,
            )
        except PreconditionFailed:
            blob.reload()
        else:
            blob.reload()
        metadata = self._meta(bucket, blob)
        pinned, reopened = self.load(metadata)
        if reopened != raw:
            raise LR8SmokeTransportError(
                "LR8 create-only object collision differs"
            )
        return {
            **pinned, "sha256": _sha_bytes(reopened),
        }


def _create_launch_intent(
    *, manifest: Mapping[str, Any], manifest_receipt: Mapping[str, Any],
    job_metadata: object, execution_census: object, schedulers: object,
    result_inventory: object, governance_inventory: object,
    created_at: str,
) -> dict[str, Any]:
    validated = _validate_launch_manifest(manifest)
    receipt = _receipt(
        manifest_receipt, uri=LAUNCH_MANIFEST_URI, label="launch manifest",
    )
    job = validated["job"]
    uid, generation, spec_sha = _validate_job_spec(
        job_metadata, job=job["name"], job_uid=job["uid"],
        code_sha=validated["code"]["commit_sha"],
        image=validated["image"]["uri"],
    )
    if uid != job["uid"] or generation != job["generation"] or \
            spec_sha != job["spec_sha256"]:
        raise LR8SmokeTransportError("LR8 launch job drifted")
    _validate_job_idle(execution_census)
    _validate_unscheduled(schedulers, job=job["name"])
    _validate_empty_inventory(result_inventory, label="result attempt")
    _validate_governance_inventory(
        governance_inventory, expected=[{
            key: receipt[key]
            for key in ("uri", "generation", "metageneration", "bytes")
        }], label="prelaunch governance",
    )
    return {
        "version": "lr8-training-source-smoke-launch-intent-v1",
        "attempt_id": ATTEMPT_ID,
        "launch_manifest": receipt,
        "job": {
            "name": job["name"], "uid": job["uid"],
            "generation": job["generation"],
            "spec_sha256": job["spec_sha256"],
        },
        "created_at": _utc_timestamp(created_at, label="launch-intent time"),
        "result_inventory_before_launch": [],
        "one_execution_only": True,
        "max_retries": 0,
        "uses_realized_target_or_candidate_outcomes": False,
        "historical_outcome_lease_acquired": False,
        "relaunch_on_ambiguity_or_failure_licensed": False,
        "production_change_licensed": False,
    }


def _execution_counts(status: Mapping[str, Any]) -> dict[str, int]:
    result = {}
    for key, short in (
        ("succeededCount", "succeeded"),
        ("failedCount", "failed"),
        ("cancelledCount", "cancelled"),
        ("retriedCount", "retried"),
    ):
        result[short] = 0 if key not in status else _nonnegative_int(
            status[key], label=f"execution {short} count",
        )
    return result


def _validate_predecessor_failure(
    closure: object, execution_metadata: object,
) -> dict[str, str]:
    """Prove the exact retained smoke-v1 incident is closed permanently."""
    expected_keys = {
        "version", "attempt_id", "execution", "execution_metadata_sha256",
        "disposition", "result_body_read", "historical_outcome_lease_acquired",
        "relaunch_licensed", "production_change_licensed",
    }
    if not isinstance(closure, Mapping) or set(closure) != expected_keys:
        raise LR8SmokeTransportError("LR8 smoke v1 failure closure differs")
    closure_sha = _sha_bytes(_canonical_json(closure))
    if closure_sha != PREDECESSOR_FAILURE_CLOSURE_SHA256:
        raise LR8SmokeTransportError(
            "LR8 smoke v1 canonical failure closure differs"
        )
    if (
        closure.get("version") != "lr8-training-source-smoke-failure-v1"
        or closure.get("attempt_id") != PREDECESSOR_ATTEMPT_ID
        or closure.get("disposition")
        != "terminal-failed-no-relaunch-no-result-read"
        or closure.get("result_body_read") is not False
        or closure.get("historical_outcome_lease_acquired") is not False
        or closure.get("relaunch_licensed") is not False
        or closure.get("production_change_licensed") is not False
    ):
        raise LR8SmokeTransportError("LR8 smoke v1 failure closure differs")
    execution = closure.get("execution")
    if execution != PREDECESSOR_EXECUTION:
        raise LR8SmokeTransportError("LR8 smoke v1 execution identity differs")
    if not isinstance(execution_metadata, Mapping):
        raise LR8SmokeTransportError("LR8 smoke v1 execution metadata differs")
    metadata_sha = _sha_bytes(_canonical_json(execution_metadata))
    if (
        metadata_sha != PREDECESSOR_EXECUTION_METADATA_SHA256
        or closure.get("execution_metadata_sha256")
        != PREDECESSOR_EXECUTION_METADATA_SHA256
    ):
        raise LR8SmokeTransportError("LR8 smoke v1 execution hash differs")
    metadata = execution_metadata.get("metadata")
    status = execution_metadata.get("status")
    spec = execution_metadata.get("spec")
    if not all(isinstance(value, Mapping) for value in (metadata, status, spec)):
        raise LR8SmokeTransportError("LR8 smoke v1 execution metadata differs")
    labels = metadata.get("labels")
    if (
        not isinstance(labels, Mapping)
        or metadata.get("name") != execution
        or labels.get("run.googleapis.com/job") != JOB
        or labels.get("run.googleapis.com/jobUid") != JOB_UID
    ):
        raise LR8SmokeTransportError("LR8 smoke v1 execution identity differs")
    conditions = status.get("conditions")
    completed = [
        row for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ] if isinstance(conditions, list) else []
    if len(completed) != 1 or completed[0].get("status") != "False":
        raise LR8SmokeTransportError("LR8 smoke v1 terminal state differs")
    if _execution_counts(status) != {
        "succeeded": 0, "failed": 1, "cancelled": 0, "retried": 0,
    } or not status.get("completionTime"):
        raise LR8SmokeTransportError("LR8 smoke v1 terminal counts differ")
    task = spec.get("template", {}).get("spec", {})
    if (
        not isinstance(task, Mapping)
        or _positive_int(spec.get("taskCount"), label="v1 task count") != 1
        or _positive_int(spec.get("parallelism"), label="v1 parallelism") != 1
        or _nonnegative_int(
            task.get("maxRetries"), label="v1 maximum retries"
        ) != 0
    ):
        raise LR8SmokeTransportError("LR8 smoke v1 retry contract differs")
    return {
        "attempt_id": PREDECESSOR_ATTEMPT_ID,
        "execution": PREDECESSOR_EXECUTION,
        "failure_closure_sha256": closure_sha,
        "execution_metadata_sha256": metadata_sha,
        "disposition": "terminal-failed-no-relaunch-no-result-read",
    }


def _validate_execution_contract(
    value: object, *, execution: str, manifest: Mapping[str, Any],
) -> tuple[str, dict[str, int], Mapping[str, Any]]:
    validated = _validate_launch_manifest(manifest)
    if not isinstance(value, Mapping):
        raise LR8SmokeTransportError("LR8 execution metadata differs")
    job = validated["job"]
    metadata = value.get("metadata")
    status = value.get("status")
    if not isinstance(metadata, Mapping) or not isinstance(status, Mapping):
        raise LR8SmokeTransportError("LR8 execution identity differs")
    labels = metadata.get("labels")
    if not isinstance(labels, Mapping) or metadata.get("name") != execution or \
            not execution.startswith(job["name"] + "-") or \
            labels.get("run.googleapis.com/job") != job["name"] or \
            labels.get("run.googleapis.com/jobUid") != job["uid"] or \
            str(labels.get("run.googleapis.com/jobGeneration")) != \
            job["generation"]:
        raise LR8SmokeTransportError("LR8 execution identity differs")
    _positive_int(metadata.get("generation"), label="execution generation")
    conditions = status.get("conditions", [])
    if not isinstance(conditions, list):
        raise LR8SmokeTransportError("LR8 execution conditions differ")
    completed = [
        row for row in conditions
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if not completed:
        state = "Unknown"
    elif len(completed) == 1 and completed[0].get("status") in {
        "Unknown", "True", "False",
    }:
        state = str(completed[0]["status"])
    else:
        raise LR8SmokeTransportError("LR8 execution Completed condition differs")
    spec = value.get("spec")
    if not isinstance(spec, Mapping):
        raise LR8SmokeTransportError("LR8 execution spec differs")
    task = spec.get("template", {}).get("spec", {})
    if not isinstance(task, Mapping):
        raise LR8SmokeTransportError("LR8 execution task differs")
    _container_contract(
        outer=spec,
        task=task,
        expected=validated["static_job_contract"],
        label="execution",
    )
    return state, _execution_counts(status), status


def _strict_terminal_execution(
    value: object, *, execution: str, manifest: Mapping[str, Any],
) -> dict[str, Any]:
    state, counts, status = _validate_execution_contract(
        value, execution=execution, manifest=manifest,
    )
    if state != "True" or counts != {
        "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
    } or not status.get("completionTime"):
        raise LR8SmokeTransportError(
            "LR8 execution is not strict terminal success"
        )
    validated = _validate_launch_manifest(manifest)
    return {
        "name": execution,
        "job": validated["job"]["name"],
        "job_uid": validated["job"]["uid"],
        "job_generation": validated["job"]["generation"],
        "job_spec_sha256": validated["job"]["spec_sha256"],
        "completed_condition": True,
        "completion_time": _utc_timestamp(
            status["completionTime"], label="execution completion time",
        ),
        "counters": counts,
        "one_task": True,
        "max_retries": 0,
    }


def _validate_execution_claim(
    value: object, *, manifest: Mapping[str, Any], intent: Mapping[str, Any],
    intent_receipt: Mapping[str, Any], execution_metadata: object,
) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("version") != \
            "lr8-training-source-smoke-execution-claim-v1" or \
            value.get("attempt_id") != ATTEMPT_ID:
        raise LR8SmokeTransportError("LR8 execution claim differs")
    receipt = _receipt(
        intent_receipt, uri=LAUNCH_INTENT_URI, label="launch intent",
    )
    if value.get("launch_intent") != receipt or value.get(
        "launch_intent_sha256"
    ) != _sha_bytes(_canonical_json(intent)):
        raise LR8SmokeTransportError("LR8 execution claim intent differs")
    execution = value.get("execution")
    if not isinstance(execution, str):
        raise LR8SmokeTransportError("LR8 execution claim name differs")
    state, counts, _status = _validate_execution_contract(
        execution_metadata, execution=execution, manifest=manifest,
    )
    if state not in {"Unknown", "True", "False"} or any(
        count != 0 for count in counts.values()
    ) and state == "Unknown":
        raise LR8SmokeTransportError("LR8 initial execution state differs")
    if value.get("initial_state") != state or value.get(
        "one_execution_only"
    ) is not True or value.get("relaunch_licensed") is not False:
        raise LR8SmokeTransportError("LR8 execution claim law differs")
    return value


def _strict_result_manifest(
    value: object, *, freeze_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LR8SmokeTransportError("LR8 smoke result manifest differs")
    expected_keys = {
        "version", "mode", "attempt_id", "canonical_panel_id", "lattice",
        "replay_environment", "table_receipts", "query_job_receipts",
        "extract_objects", "model_fits", "replay_blocks", "solver_status",
        "smoke_unique_candidates", "training_source_freeze_object",
        "smoke_solve_freeze_object", "smoke_solve_freeze",
        "prior_model_training_labels_queried", "prior_was_active_queried",
        "prior_model_training_seasons",
        "target_model_label_placeholders_all_null",
        "target_was_active_placeholder_all_null", "target_player_labels_read",
        "candidate_labels_read", "role_belief_worlds_used",
        "dst_correlated_draws_used", "build_slates_used",
        "actual_score_queried", "candidate_totals_queried",
        "y_dk_points_queried", "target_realized_labels_queried",
        "historical_candidate_label_read_licensed",
        "production_change_licensed", "manifest_sha256",
    }
    if set(value) != expected_keys:
        raise LR8SmokeTransportError("LR8 smoke result manifest fields differ")
    expected = {
        "version": source_runner.RUNNER_VERSION,
        "mode": "smoke",
        "attempt_id": ATTEMPT_ID,
        "canonical_panel_id": training.CANONICAL_PANEL_ID,
        "lattice": [{"season": 2019, "weeks": [1], "blocks": ["R0"]}],
        "solver_status": "exact_smoke_complete",
        "smoke_unique_candidates": training.UNIQUE_OPTIMA_PER_BLOCK,
        "prior_model_training_labels_queried": True,
        "prior_was_active_queried": True,
        "prior_model_training_seasons": {
            "2019": list(training.MODEL_TRAINING_SEASONS[2019])
        },
        "target_model_label_placeholders_all_null": True,
        "target_was_active_placeholder_all_null": True,
        "target_player_labels_read": False,
        "candidate_labels_read": False,
        "role_belief_worlds_used": False,
        "dst_correlated_draws_used": False,
        "build_slates_used": False,
        "actual_score_queried": False,
        "candidate_totals_queried": False,
        "y_dk_points_queried": False,
        "target_realized_labels_queried": False,
        "historical_candidate_label_read_licensed": False,
        "production_change_licensed": False,
    }
    if any(value.get(key) != wanted for key, wanted in expected.items()):
        raise LR8SmokeTransportError("LR8 smoke result fixed law differs")
    if value.get("training_source_freeze_object") is not None:
        raise LR8SmokeTransportError("LR8 smoke unexpectedly built full source")
    if value.get("replay_environment") != source_runner.REPLAY_ENVIRONMENT:
        raise LR8SmokeTransportError("LR8 smoke replay environment differs")
    model_fits = value.get("model_fits")
    if not isinstance(model_fits, Mapping) or set(model_fits) != {"2019"} or \
            not isinstance(model_fits["2019"], Mapping) or set(
                model_fits["2019"]
            ) != {"model_fit_input_sha256", "model_fit_sha256"}:
        raise LR8SmokeTransportError("LR8 smoke fitted-model binding differs")
    for digest in model_fits["2019"].values():
        _hex(digest, label="fitted-model binding SHA")
    frozen = _result_receipt(freeze_receipt, label="smoke solve freeze")
    if value.get("smoke_solve_freeze_object") != frozen:
        raise LR8SmokeTransportError(
            "LR8 smoke result does not bind its full solve freeze"
        )
    claimed = value.get("manifest_sha256")
    _hex(claimed, label="smoke result manifest SHA")
    without = dict(value)
    without.pop("manifest_sha256")
    if _sha_bytes(_canonical_json(without)) != claimed:
        raise LR8SmokeTransportError("LR8 smoke result manifest hash differs")
    return value


def _result_object_map(
    inventory: object,
) -> dict[str, dict[str, Any]]:
    if not isinstance(inventory, list) or not inventory:
        raise LR8SmokeTransportError("LR8 result inventory is empty")
    rows = [_object_metadata(row, label="result inventory") for row in inventory]
    if rows != sorted(rows, key=lambda row: row["uri"]):
        raise LR8SmokeTransportError("LR8 result inventory order differs")
    result = {row["uri"]: row for row in rows}
    if len(result) != len(rows) or any(
        not uri.startswith(RESULT_PREFIX + "/") for uri in result
    ):
        raise LR8SmokeTransportError("LR8 result inventory scope differs")
    if SMOKE_MANIFEST_URI not in result or SMOKE_SOLVE_FREEZE_URI not in result:
        raise LR8SmokeTransportError("LR8 result inventory lacks smoke objects")
    return result


def _loaded_receipt(
    metadata: Mapping[str, Any], raw: bytes,
) -> dict[str, Any]:
    base = _object_metadata(metadata, label="loaded result")
    if len(raw) != base["bytes"]:
        raise LR8SmokeTransportError("LR8 loaded result byte count differs")
    return {**base, "sha256": _sha_bytes(raw)}


def _validate_result_receipt_against_loaded(
    receipt: object, *, loaded: Mapping[str, tuple[dict[str, Any], bytes]],
    label: str,
) -> dict[str, Any]:
    expected = _result_receipt(receipt, label=label)
    if expected["uri"] not in loaded:
        raise LR8SmokeTransportError(f"LR8 {label} object is absent")
    actual = _loaded_receipt(*loaded[expected["uri"]])
    if {
        key: actual[key] for key in ("uri", "generation", "sha256", "bytes")
    } != expected:
        raise LR8SmokeTransportError(f"LR8 {label} object differs")
    return expected


def _catalog_players(extract: Mapping[str, Any]) -> tuple[rw.PlayerSpec, ...]:
    rows = extract.get("rows")
    if not isinstance(rows, list) or not rows:
        raise LR8SmokeTransportError("LR8 catalog extract rows differ")
    players = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise LR8SmokeTransportError("LR8 catalog extract row differs")
        players.append(rw.PlayerSpec.from_mapping({
            "id": row.get("id"),
            "pos": row.get("pos"),
            "team": row.get("team"),
            "opp": row.get("opp"),
            "game_id": row.get("game_id"),
            "salary": row.get("salary"),
        }))
    return tuple(players)


def _source_config() -> source_runner.RunnerConfig:
    return source_runner.RunnerConfig(
        mode="smoke",
        attempt_id=ATTEMPT_ID,
        project=PROJECT,
        bucket=BUCKET,
        catalog_table=CATALOG_TABLE,
        candidate_table=CANDIDATE_TABLE,
        pit_table=PIT_TABLE,
        tabpfn_table=TABPFN_TABLE,
        location=LOCATION,
        evidence_root=Path(EVIDENCE_ROOT),
        execute=True,
        enabled=True,
    )


def _validate_source_extracts(
    *, manifest: Mapping[str, Any],
    extracts: Mapping[str, Mapping[str, Any]],
) -> None:
    config = _source_config()
    specs = {spec.label: spec for spec in source_runner._query_requests(config)}
    if set(extracts) != set(specs):
        raise LR8SmokeTransportError("LR8 smoke query lattice differs")
    table_receipts = manifest.get("table_receipts")
    query_receipts = manifest.get("query_job_receipts")
    if not isinstance(table_receipts, Mapping) or set(table_receipts) != {
        CATALOG_TABLE, CANDIDATE_TABLE, PIT_TABLE, TABPFN_TABLE,
    } or not isinstance(query_receipts, Mapping) or set(query_receipts) != set(
        specs
    ):
        raise LR8SmokeTransportError("LR8 smoke source receipts differ")
    for table, receipt in table_receipts.items():
        try:
            source_runner._validate_table_receipt(receipt, table=table)
        except source_runner.LR8SourceRunnerError as exc:
            raise LR8SmokeTransportError(
                "LR8 smoke table receipt differs"
            ) from exc
    for label, payload in extracts.items():
        spec = specs[label]
        columns, _sort, _filename = source_runner._extract_contract(label)
        dependencies = source_runner._table_dependencies(config, label)
        expected_query = {
            "sql_sha256": spec.query_sha256,
            "parameters": source_runner._parameter_payload(spec.parameters),
            "parameters_sha256": spec.parameters_sha256,
            "job_receipt": query_receipts[label],
        }
        if set(payload) != {
            "schema", "label", "query", "tables", "columns", "rows",
            "rows_sha256",
        } or payload.get("schema") != source_runner.EXTRACT_VERSION or \
                payload.get("label") != label or payload.get("query") != \
                expected_query or payload.get("tables") != [
                    table_receipts[table] for table in dependencies
                ] or payload.get("columns") != list(columns) or not isinstance(
                    payload.get("rows"), list
                ) or payload.get("rows_sha256") != _sha_bytes(
                    _canonical_json(payload.get("rows"))
                ) or any(
                    not isinstance(row, Mapping) or set(row) != set(columns)
                    for row in payload["rows"]
                ):
            raise LR8SmokeTransportError(
                f"LR8 smoke {label} extract contract differs"
            )
        try:
            source_runner._validate_job_receipt(query_receipts[label], spec)
        except source_runner.LR8SourceRunnerError as exc:
            raise LR8SmokeTransportError(
                f"LR8 smoke {label} query receipt differs"
            ) from exc


def _strict_proof(
    proof: object, *, request_sha: str, attempt: Mapping[str, Any],
    receipts: Sequence[Mapping[str, Any]],
    loaded: Mapping[str, tuple[dict[str, Any], bytes]],
) -> None:
    if not isinstance(proof, dict) or proof.get("schema") != \
            exact_solvers.PROOF_SCHEMA or proof.get("solve_kind") != \
            exact_solvers.TRAINING_SOLVE_KIND or proof.get(
                "request_sha256"
            ) != request_sha:
        raise LR8SmokeTransportError("LR8 exact proof identity differs")
    result = proof.get("result")
    if not isinstance(result, Mapping) or result.get("roster") != \
            attempt.get("roster") or result.get("objective_micro") != \
            attempt.get("objective_micro") or result.get("dk_classic_only") is \
            not True or result.get("incumbent_no_goods_enforced") is not True or \
            result.get("house_rules_applied") != []:
        raise LR8SmokeTransportError("LR8 exact proof result differs")
    evidence = proof.get("cbc_solve_evidence")
    if not isinstance(evidence, list) or not evidence:
        raise LR8SmokeTransportError("LR8 exact proof lacks CBC evidence")
    by_uri = {str(row.get("uri")): row for row in receipts}
    proof_uri = f"{RESULT_PREFIX}/solver-evidence/{request_sha}/proof.json"
    if proof_uri not in by_uri:
        raise LR8SmokeTransportError("LR8 exact proof receipt is absent")
    for index, row in enumerate(evidence):
        if not isinstance(row, Mapping) or row.get("pulp_status") != 1 or \
                row.get("pulp_solution_status") != 1 or \
                row.get("threads") != 1:
            raise LR8SmokeTransportError("LR8 CBC proof status differs")
        required = {
            f"{index:02d}-cbc.log": None,
            f"{index:02d}-model.sol": None,
            f"{index:02d}-model.mps": row.get("model_sha256"),
            f"{index:02d}-variable-domain-manifest.json": row.get(
                "variable_domain_manifest_sha256"
            ),
        }
        if row.get("warm_start") is True:
            required[f"{index:02d}-model.mst"] = row.get("mip_start_sha256")
        elif row.get("mip_start_sha256") is not None:
            raise LR8SmokeTransportError("LR8 cold CBC proof has MIP start")
        for suffix, expected_sha in required.items():
            uri = f"{RESULT_PREFIX}/solver-evidence/{request_sha}/{suffix}"
            receipt = by_uri.get(uri)
            if receipt is None:
                raise LR8SmokeTransportError("LR8 CBC artifact receipt is absent")
            actual = _validate_result_receipt_against_loaded(
                receipt, loaded=loaded, label="CBC evidence",
            )
            if expected_sha is not None and actual["sha256"] != _hex(
                expected_sha, label="CBC artifact proof SHA",
            ):
                raise LR8SmokeTransportError("LR8 CBC artifact proof differs")
    expected_uris = {proof_uri}
    for index, row in enumerate(evidence):
        expected_uris.update({
            f"{RESULT_PREFIX}/solver-evidence/{request_sha}/{index:02d}-cbc.log",
            f"{RESULT_PREFIX}/solver-evidence/{request_sha}/{index:02d}-model.sol",
            f"{RESULT_PREFIX}/solver-evidence/{request_sha}/{index:02d}-model.mps",
            f"{RESULT_PREFIX}/solver-evidence/{request_sha}/{index:02d}-variable-domain-manifest.json",
        })
        if row.get("warm_start") is True:
            expected_uris.add(
                f"{RESULT_PREFIX}/solver-evidence/{request_sha}/{index:02d}-model.mst"
            )
    if set(by_uri) != expected_uris:
        raise LR8SmokeTransportError("LR8 exact proof evidence inventory differs")


def _replay_smoke_contract(
    *, manifest: Mapping[str, Any], smoke_freeze: Mapping[str, Any],
    loaded: Mapping[str, tuple[dict[str, Any], bytes]],
) -> dict[str, Any]:
    """Replay retained smoke bytes from extracts through exact CBC proofs."""
    extracts = manifest.get("extract_objects")
    if not isinstance(extracts, Mapping) or set(extracts) != {
        "canonical_catalog", "canonical_incumbents", "pit_panel_2019",
        "tabpfn_2019",
    }:
        raise LR8SmokeTransportError("LR8 smoke extract inventory differs")
    extract_payloads: dict[str, Mapping[str, Any]] = {}
    for label, receipt in extracts.items():
        normalized = _validate_result_receipt_against_loaded(
            receipt, loaded=loaded, label=f"{label} extract",
        )
        payload = _strict_json_bytes(
            loaded[normalized["uri"]][1], label=f"{label} extract",
        )
        if not isinstance(payload, Mapping):
            raise LR8SmokeTransportError("LR8 smoke extract body differs")
        extract_payloads[label] = payload
    _validate_source_extracts(manifest=manifest, extracts=extract_payloads)
    players = _catalog_players(extract_payloads["canonical_catalog"])
    incumbents_rows = extract_payloads["canonical_incumbents"].get("rows")
    if not isinstance(incumbents_rows, list) or not incumbents_rows or any(
        not isinstance(row, Mapping) or not isinstance(row.get("players"), list)
        for row in incumbents_rows
    ):
        raise LR8SmokeTransportError("LR8 incumbent extract rows differ")
    incumbents = [
        list(rw.canonical_identity(row["players"])) for row in incumbents_rows
    ]
    catalog_sha = training.catalog_sha256(players)
    incumbent_sha = training.identities_sha256(incumbents)
    fixed_freeze = {
        "version": source_runner.SMOKE_SOLVE_FREEZE_VERSION,
        "season": 2019,
        "week": 1,
        "block": "R0",
        "projection_seed": 0,
        "source_environment_role_seed_nonoperative": (
            training.BLOCK_SEED_PAIRS["R0"][1]
        ),
        "candidate_world_family": training.CANDIDATE_WORLD_FAMILY,
        "role_belief_worlds_used": False,
        "hard_domain_id": training.HARD_DOMAIN_ID,
        "former_house_rules_not_applied": list(
            training.FORMER_HOUSE_RULES_NOT_APPLIED
        ),
        "world_order_law": training.WORLD_ORDER_LAW,
        "catalog_sha256": catalog_sha,
        "incumbent_candidates_sha256": incumbent_sha,
    }
    if any(smoke_freeze.get(key) != expected for key, expected in fixed_freeze.items()):
        raise LR8SmokeTransportError("LR8 smoke solve-freeze fixed law differs")
    player_ids = smoke_freeze.get("player_ids")
    if not isinstance(player_ids, list) or player_ids != [
        player.player_id for player in players
    ] or training.player_ids_sha256(player_ids) != smoke_freeze.get(
        "player_ids_sha256"
    ):
        raise LR8SmokeTransportError("LR8 smoke player identity differs")
    draws = smoke_freeze.get("player_draws")
    if not isinstance(draws, Mapping) or set(draws) != {
        "dtype", "shape", "sha256",
    } or draws.get("dtype") != "<f4" or draws.get("shape") != [
        len(player_ids), training.WORLDS_PER_BLOCK,
    ]:
        raise LR8SmokeTransportError("LR8 smoke player-draw metadata differs")
    _hex(draws.get("sha256"), label="player draws SHA")
    replay_blocks = manifest.get("replay_blocks")
    expected_replay_blocks = [{
        "season": 2019,
        "block": "R0",
        "projection_seed": 0,
        "source_environment_role_seed_nonoperative": (
            training.BLOCK_SEED_PAIRS["R0"][1]
        ),
        "slates": [{
            "season": 2019,
            "week": 1,
            "player_ids_sha256": smoke_freeze.get("player_ids_sha256"),
            "player_draws_sha256": draws.get("sha256"),
            "shape": draws.get("shape"),
        }],
    }]
    if replay_blocks != expected_replay_blocks:
        raise LR8SmokeTransportError("LR8 smoke replay-block binding differs")
    world_order = smoke_freeze.get("world_order")
    if not isinstance(world_order, list) or len(world_order) != \
            training.WORLDS_PER_BLOCK or set(world_order) != set(
                range(training.WORLDS_PER_BLOCK)
            ) or training.canonical_sha256(world_order) != smoke_freeze.get(
                "world_order_sha256"
            ):
        raise LR8SmokeTransportError("LR8 smoke world order differs")
    attempts = smoke_freeze.get("ordered_solve_attempts")
    requests = smoke_freeze.get("ordered_request_payloads")
    candidate_rows = smoke_freeze.get("unique_candidates")
    if not isinstance(attempts, list) or not (
        training.UNIQUE_OPTIMA_PER_BLOCK <= len(attempts)
        <= training.MAX_SOLVE_ATTEMPTS_PER_BLOCK
    ) or smoke_freeze.get("ordered_solve_attempt_count") != len(attempts) or \
            not isinstance(requests, list) or len(requests) != len(attempts) or \
            not isinstance(candidate_rows, list) or len(candidate_rows) != \
            training.UNIQUE_OPTIMA_PER_BLOCK or smoke_freeze.get(
                "unique_candidate_count"
            ) != len(candidate_rows):
        raise LR8SmokeTransportError("LR8 smoke solve-freeze dose differs")
    if training.canonical_sha256(requests) != smoke_freeze.get(
        "ordered_request_payloads_sha256"
    ):
        raise LR8SmokeTransportError("LR8 ordered request payload hash differs")
    candidates: list[list[str]] = []
    anatomy: list[dict[str, Any]] = []
    legality: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidate_rows):
        if not isinstance(candidate, Mapping) or set(candidate) != {
            "season", "week", "roster", "anatomy_features",
            "first_source_block", "first_source_world_index",
            "source_occurrences",
        } or candidate.get("season") != 2019 or candidate.get("week") != 1 or \
                candidate.get("first_source_block") != "R0" or not isinstance(
                    candidate.get("first_source_world_index"), int
                ) or candidate.get("source_occurrences") != [[
                    "R0", candidate.get("first_source_world_index")
                ]]:
            raise LR8SmokeTransportError("LR8 frozen candidate payload differs")
        roster = list(lr8.audit_dk_classic_identity(players, candidate.get("roster")))
        if roster in candidates:
            raise LR8SmokeTransportError("LR8 frozen candidate repeats")
        features = candidate.get("anatomy_features")
        if features != training._anatomy_payload(  # noqa: SLF001
            lr8.lineup_anatomy(players, roster)
        ):
            raise LR8SmokeTransportError("LR8 frozen candidate anatomy differs")
        candidates.append(roster)
        anatomy.append({"roster": roster, "features": features})
        legality.append({
            "roster": roster,
            "hard_domain_id": training.HARD_DOMAIN_ID,
            "dk_classic_legal": True,
            "former_house_rules_applied": [],
        })
    seen: set[tuple[str, ...]] = set()
    admitted: list[list[str]] = []
    proof_requests: set[str] = set()
    for attempt_index, (attempt, request_payload) in enumerate(zip(
        attempts, requests, strict=True,
    )):
        if not isinstance(attempt, Mapping):
            raise LR8SmokeTransportError("LR8 smoke solve attempt differs")
        request_sha = _hex(attempt.get("request_sha256"), label="solve request SHA")
        if request_sha in proof_requests:
            raise LR8SmokeTransportError("LR8 smoke solve request duplicates")
        proof_requests.add(request_sha)
        if not isinstance(request_payload, Mapping) or training.canonical_sha256(
            request_payload
        ) != request_sha or request_payload != {
            "season": 2019,
            "week": 1,
            "block": "R0",
            "projection_seed": 0,
            "world_index": attempt.get("world_index"),
            "catalog_sha256": catalog_sha,
            "player_scores_sha256": request_payload.get("player_scores_sha256"),
            "incumbent_no_goods_sha256": incumbent_sha,
            "candidate_world_family": training.CANDIDATE_WORLD_FAMILY,
            "role_belief_worlds_used": False,
            "hard_domain_id": training.HARD_DOMAIN_ID,
            "former_house_rules_not_applied": list(
                training.FORMER_HOUSE_RULES_NOT_APPLIED
            ),
        }:
            raise LR8SmokeTransportError("LR8 solve request preimage differs")
        _hex(
            request_payload.get("player_scores_sha256"),
            label="world player-score SHA",
        )
        if attempt.get("block") != "R0" or attempt.get(
            "projection_seed"
        ) != 0 or attempt.get("world_index") != world_order[attempt_index]:
            raise LR8SmokeTransportError("LR8 ordered world solve differs")
        roster = lr8.audit_dk_classic_identity(players, attempt.get("roster"))
        if list(roster) in incumbents:
            raise LR8SmokeTransportError("LR8 solve reused incumbent roster")
        is_new = roster not in seen
        if attempt.get("admitted_unique") is not is_new:
            raise LR8SmokeTransportError("LR8 smoke admission replay differs")
        if is_new:
            seen.add(roster)
            admitted.append(list(roster))
            candidate = candidate_rows[len(admitted) - 1]
            if candidate.get("first_source_world_index") != attempt.get(
                "world_index"
            ) or candidate.get("roster") != list(roster):
                raise LR8SmokeTransportError(
                    "LR8 candidate first-source replay differs"
                )
        receipts = attempt.get("evidence_receipts")
        if not isinstance(receipts, list) or not receipts:
            raise LR8SmokeTransportError("LR8 solve evidence receipts differ")
        normalized = [
            _validate_result_receipt_against_loaded(
                row, loaded=loaded, label="solve evidence",
            ) for row in receipts
        ]
        if training.canonical_sha256(list(receipts)) != attempt.get(
            "evidence_manifest_sha256"
        ):
            raise LR8SmokeTransportError("LR8 solve evidence manifest differs")
        proof_uri = f"{RESULT_PREFIX}/solver-evidence/{request_sha}/proof.json"
        proof = _strict_json_bytes(
            loaded[proof_uri][1], label="exact solve proof",
        ) if proof_uri in loaded else None
        _strict_proof(
            proof, request_sha=request_sha, attempt=attempt,
            receipts=normalized, loaded=loaded,
        )
    if admitted != candidates or len(seen) != training.UNIQUE_OPTIMA_PER_BLOCK:
        raise LR8SmokeTransportError("LR8 unique candidate replay differs")
    summaries = {
        "ordered_solve_attempts_sha256": training.canonical_sha256(attempts),
        "candidate_identities_sha256": training.canonical_sha256(candidates),
        "anatomy_sha256": training.canonical_sha256(anatomy),
        "legality_sha256": training.canonical_sha256(legality),
    }
    for key, digest in summaries.items():
        if smoke_freeze.get(key) != digest:
            raise LR8SmokeTransportError(f"LR8 smoke {key} differs")
    summary = manifest.get("smoke_solve_freeze")
    if not isinstance(summary, Mapping) or any(
        summary.get(key) != digest for key, digest in summaries.items()
    ) or summary.get("ordered_solve_attempt_count") != len(attempts) or \
            summary.get("unique_candidate_count") != len(candidates) or \
            summary.get("block") != "R0" or summary.get(
                "projection_seed"
            ) != 0 or summary.get("player_ids_sha256") != smoke_freeze.get(
                "player_ids_sha256"
            ) or summary.get("player_draws_sha256") != draws["sha256"] or \
            summary.get("world_order_sha256") != smoke_freeze.get(
                "world_order_sha256"
            ):
        raise LR8SmokeTransportError("LR8 smoke summary/freeze binding differs")
    source_receipts = smoke_freeze.get("source_receipts")
    expected_source_receipts = [
        extracts["pit_panel_2019"], extracts["tabpfn_2019"],
        extracts["canonical_catalog"],
    ]
    if source_receipts != expected_source_receipts or any(
        _validate_result_receipt_against_loaded(
            receipt, loaded=loaded, label="smoke source receipt",
        ) != _result_receipt(expected, label="expected smoke source receipt")
        for receipt, expected in zip(
            source_receipts or (), expected_source_receipts, strict=True,
        )
    ):
        raise LR8SmokeTransportError("LR8 smoke source receipts differ")
    evidence_uris = {
        str(receipt.get("uri"))
        for attempt in attempts
        for receipt in attempt["evidence_receipts"]
    }
    inventoried_evidence = {
        uri for uri in loaded if uri.startswith(RESULT_PREFIX + "/solver-evidence/")
    }
    if evidence_uris != inventoried_evidence:
        raise LR8SmokeTransportError("LR8 retained evidence inventory differs")
    return {
        "ordered_solve_attempt_count": len(attempts),
        "unique_candidate_count": len(candidates),
        "proof_request_count": len(proof_requests),
        "retained_evidence_object_count": len(evidence_uris),
        **summaries,
    }


def _validate_result_objects(
    *, inventory: object,
    loaded: Mapping[str, tuple[dict[str, Any], bytes]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    expected = _result_object_map(inventory)
    if set(loaded) != set(expected):
        raise LR8SmokeTransportError("LR8 loaded result inventory differs")
    for uri, metadata in expected.items():
        if _object_metadata(loaded[uri][0], label="loaded result") != metadata:
            raise LR8SmokeTransportError("LR8 loaded result metadata differs")
    freeze_raw = loaded[SMOKE_SOLVE_FREEZE_URI][1]
    smoke_freeze = _strict_json_bytes(freeze_raw, label="smoke solve freeze")
    if not isinstance(smoke_freeze, dict):
        raise LR8SmokeTransportError("LR8 smoke solve freeze differs")
    freeze_receipt = {
        key: value for key, value in _loaded_receipt(
            *loaded[SMOKE_SOLVE_FREEZE_URI]
        ).items() if key in {"uri", "generation", "sha256", "bytes"}
    }
    manifest_raw = loaded[SMOKE_MANIFEST_URI][1]
    manifest = _strict_json_bytes(manifest_raw, label="smoke result manifest")
    validated_manifest = _strict_result_manifest(
        manifest, freeze_receipt=freeze_receipt,
    )
    replay = _replay_smoke_contract(
        manifest=validated_manifest, smoke_freeze=smoke_freeze,
        loaded=loaded,
    )
    referenced = {
        SMOKE_MANIFEST_URI, SMOKE_SOLVE_FREEZE_URI,
        *(row["uri"] for row in (
            _result_receipt(value, label="extract")
            for value in validated_manifest["extract_objects"].values()
        )),
        *(uri for uri in loaded if uri.startswith(
            RESULT_PREFIX + "/solver-evidence/"
        )),
    }
    if referenced != set(loaded):
        raise LR8SmokeTransportError("LR8 result contains unbound objects")
    return validated_manifest, smoke_freeze, replay


ExecutionLoader = Callable[[str], Mapping[str, Any]]
InventoryLoader = Callable[[str], list[dict[str, Any]]]
ObjectLoader = Callable[[Mapping[str, Any]], tuple[dict[str, Any], bytes]]


def _execution_metadata(name: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="lr8-smoke-execution-") as directory:
        path = Path(directory) / "execution.json"
        with path.open("xb") as handle:
            completed = subprocess.run([
                "gcloud", "run", "jobs", "executions", "describe", name,
                "--project", PROJECT, "--region", REGION, "--format=json",
            ], check=False, stdout=handle)
        if completed.returncode != 0:
            raise LR8SmokeTransportError("LR8 execution metadata read failed")
        value = _load_json(path, label="execution metadata")
    if not isinstance(value, dict):
        raise LR8SmokeTransportError("LR8 execution metadata differs")
    return value


def _hash_ledger(path: Path, *, base: Path, names: Sequence[str]) -> None:
    rows = []
    for name in sorted(names):
        target = base / name
        rows.append(f"{_sha_path(target)}  {name}\n")
    _write_exclusive_or_equal(path, "".join(rows).encode("utf-8"))


def _validate_hash_ledger(
    path: Path, *, base: Path, names: Sequence[str],
) -> None:
    expected = "".join(
        f"{_sha_path(base / name)}  {name}\n" for name in sorted(names)
    ).encode("utf-8")
    if path.is_symlink() or not path.is_file() or path.read_bytes() != expected:
        raise LR8SmokeTransportError("LR8 local hash ledger differs")


PREPARED_INPUT_FILES: Final = (
    "build-metadata.json", "job-before.json", "job-after.json",
    "executions-before.json", "executions-after.json",
    "schedulers-before.json", "schedulers-after.json",
    "result-inventory-before.json", "result-inventory-after.json",
    "governance-inventory-before.json", "governance-inventory-after.json",
    "manifest.json", "manifest-object.json",
)
LAUNCH_FILES: Final = (
    "prepared.sha256", "manifest.json", "manifest-object.json",
    "job-launch.json", "executions-launch.json", "schedulers-launch.json",
    "result-inventory-launch.json", "governance-inventory-launch.json",
    "launch-intent.json", "launch-intent-object.json", "executions.txt",
    "execution-initial.json", "execution-claim.json",
    "execution-claim-object.json",
)


def _validate_prepared(out: Path) -> dict[str, Any]:
    _validate_hash_ledger(
        out / "prepared.sha256", base=out, names=PREPARED_INPUT_FILES,
    )
    manifest = _validate_launch_manifest(
        _load_json(out / "manifest.json", label="launch manifest")
    )
    manifest_object = _receipt(
        _load_json(out / "manifest-object.json", label="manifest object"),
        uri=LAUNCH_MANIFEST_URI, label="launch manifest",
    )
    if manifest_object["sha256"] != _sha_path(out / "manifest.json"):
        raise LR8SmokeTransportError("LR8 launch manifest object differs")
    build = _load_json(out / "build-metadata.json", label="build metadata")
    _validate_build_metadata(
        build, build_id=manifest["build"]["id"],
        image=manifest["image"]["uri"],
        code_sha=manifest["code"]["commit_sha"],
    )
    if _sha_bytes(_canonical_json(build)) != manifest["build"][
        "metadata_sha256"
    ]:
        raise LR8SmokeTransportError("LR8 prepared build metadata differs")
    return manifest


def _validate_launch(out: Path) -> tuple[dict[str, Any], str]:
    _validate_prepared(out)
    _validate_hash_ledger(out / "launch.sha256", base=out, names=LAUNCH_FILES)
    manifest = _load_json(out / "manifest.json", label="launch manifest")
    intent = _load_json(out / "launch-intent.json", label="launch intent")
    intent_object = _receipt(
        _load_json(out / "launch-intent-object.json", label="intent object"),
        uri=LAUNCH_INTENT_URI, label="launch intent",
    )
    ledger = (out / "executions.txt").read_text(encoding="utf-8").split()
    if len(ledger) != 3 or ledger[0] != JOB or ledger[2] != SMOKE_MANIFEST_URI:
        raise LR8SmokeTransportError("LR8 execution ledger differs")
    execution = ledger[1]
    claim = _load_json(out / "execution-claim.json", label="execution claim")
    _validate_execution_claim(
        claim, manifest=manifest, intent=intent, intent_receipt=intent_object,
        execution_metadata=_load_json(
            out / "execution-initial.json", label="initial execution metadata",
        ),
    )
    if claim.get("execution") != execution:
        raise LR8SmokeTransportError("LR8 execution ledger differs")
    claim_object = _receipt(
        _load_json(out / "execution-claim-object.json", label="claim object"),
        uri=EXECUTION_CLAIM_URI, label="execution claim",
    )
    if claim_object["sha256"] != _sha_path(out / "execution-claim.json"):
        raise LR8SmokeTransportError("LR8 execution claim object differs")
    return manifest, execution


def finish(
    *, out: Path = DEFAULT_OUT,
    execution_loader: ExecutionLoader | None = None,
    inventory_loader: InventoryLoader | None = None,
    object_loader: ObjectLoader | None = None,
) -> dict[str, Any]:
    """Strictly harvest one already-launched outcome-blind smoke."""
    if (out / "finish.sha256").is_file():
        _validate_hash_ledger(
            out / "finish.sha256", base=out, names=(
                "launch.sha256", "execution-terminal.json",
                "result-inventory.json", "result-objects.json",
                "smoke-manifest.json", "smoke-solve-freeze.json",
                "completion.json",
            ),
        )
        return _load_json(out / "completion.json", label="completion")
    for name in (
        "execution-terminal.json", "result-inventory.json",
        "result-objects.json", "smoke-manifest.json",
        "smoke-solve-freeze.json", "completion.json",
    ):
        if (out / name).exists():
            raise LR8SmokeTransportError("LR8 partial immutable harvest exists")
    manifest, execution = _validate_launch(out)
    if execution_loader is None:
        execution_loader = _execution_metadata
    reader: _StorageReader | None = None
    if inventory_loader is None or object_loader is None:
        reader = _StorageReader()
    if inventory_loader is None:
        assert reader is not None
        inventory_loader = reader.inventory
    if object_loader is None:
        assert reader is not None
        object_loader = reader.load

    # Body-blind boundary: strict terminal metadata is the first external read.
    execution_value = execution_loader(execution)
    terminal = _strict_terminal_execution(
        execution_value, execution=execution, manifest=manifest,
    )

    # Only metadata is listed next.  Bodies are opened generation-pinned below.
    inventory = inventory_loader(RESULT_PREFIX + "/")
    inventory_map = _result_object_map(inventory)
    loaded: dict[str, tuple[dict[str, Any], bytes]] = {}
    for uri in sorted(inventory_map):
        metadata, raw = object_loader(inventory_map[uri])
        if _object_metadata(metadata, label="result object") != inventory_map[uri]:
            raise LR8SmokeTransportError("LR8 generation-pinned object differs")
        loaded[uri] = (metadata, raw)
    result_manifest, smoke_freeze, replay = _validate_result_objects(
        inventory=inventory, loaded=loaded,
    )
    object_receipts = [
        _loaded_receipt(*loaded[uri]) for uri in sorted(loaded)
    ]
    completion = {
        "version": "lr8-training-source-smoke-completion-v1",
        "attempt_id": ATTEMPT_ID,
        "disposition": "outcome-blind-real-source-smoke-passed",
        "execution": terminal,
        "launch_manifest_sha256": _sha_path(out / "manifest.json"),
        "smoke_manifest_sha256": _sha_bytes(
            loaded[SMOKE_MANIFEST_URI][1]
        ),
        "smoke_solve_freeze_sha256": _sha_bytes(
            loaded[SMOKE_SOLVE_FREEZE_URI][1]
        ),
        "result_inventory_sha256": _sha_bytes(_canonical_json(object_receipts)),
        "independent_smoke_replay": replay,
        "uses_realized_target_or_candidate_outcomes": False,
        "historical_outcome_lease_acquired": False,
        "historical_retry_licensed": False,
        "full_source_build_licensed": False,
        "production_change_licensed": False,
    }
    _write_exclusive_or_equal(
        out / "execution-terminal.json", _canonical_json(execution_value),
    )
    _write_exclusive_or_equal(
        out / "result-inventory.json", _canonical_json(inventory),
    )
    _write_exclusive_or_equal(
        out / "result-objects.json", _canonical_json(object_receipts),
    )
    _write_exclusive_or_equal(
        out / "smoke-manifest.json", _canonical_json(result_manifest),
    )
    _write_exclusive_or_equal(
        out / "smoke-solve-freeze.json", _canonical_json(smoke_freeze),
    )
    _write_exclusive_or_equal(
        out / "completion.json", _canonical_json(completion),
    )
    _hash_ledger(
        out / "finish.sha256", base=out, names=(
            "launch.sha256", "execution-terminal.json",
            "result-inventory.json", "result-objects.json",
            "smoke-manifest.json", "smoke-solve-freeze.json",
            "completion.json",
        ),
    )
    return completion


def _canonicalize_external_json(raw_path: Path, output: Path) -> None:
    value = _load_json(raw_path, label="external JSON")
    _write_exclusive_or_equal(output, _canonical_json(value))


def _arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    canonical = sub.add_parser("canonicalize-external-json")
    canonical.add_argument("--raw", type=Path, required=True)
    canonical.add_argument("--output", type=Path, required=True)
    inventory = sub.add_parser("inventory")
    inventory.add_argument("--prefix", required=True)
    inventory.add_argument("--output", type=Path, required=True)
    predecessor = sub.add_parser("validate-predecessor-failure")
    predecessor.add_argument("--closure", type=Path, required=True)
    predecessor.add_argument("--metadata", type=Path, required=True)
    pre = sub.add_parser("validate-preupdate")
    for command in (pre,):
        command.add_argument("--code-sha", required=True)
        command.add_argument("--image", required=True)
        command.add_argument("--build-id", required=True)
        command.add_argument("--job", required=True)
        command.add_argument("--job-uid", required=True)
        command.add_argument("--build-metadata", type=Path, required=True)
        command.add_argument("--job-before", type=Path, required=True)
        command.add_argument("--executions-before", type=Path, required=True)
        command.add_argument("--schedulers-before", type=Path, required=True)
        command.add_argument("--result-inventory-before", type=Path, required=True)
        command.add_argument(
            "--governance-inventory-before", type=Path, required=True,
        )
    prepare = sub.add_parser("prepare")
    for name in (
        "code-sha", "image", "build-id", "job", "job-uid",
    ):
        prepare.add_argument("--" + name, required=True)
    for name in (
        "build-metadata", "job-before", "job-after", "executions-before",
        "executions-after", "schedulers-before", "schedulers-after",
        "result-inventory-before", "result-inventory-after",
        "governance-inventory-before", "governance-inventory-after",
    ):
        prepare.add_argument("--" + name, type=Path, required=True)
    prepare.add_argument("--prepared-at", required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    sub.add_parser("validate-prepared").add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUT,
    )
    intent = sub.add_parser("create-launch-intent")
    intent.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    for name in (
        "job-metadata", "execution-census", "schedulers",
        "result-inventory", "governance-inventory",
    ):
        intent.add_argument("--" + name, type=Path, required=True)
    intent.add_argument("--created-at", required=True)
    bind = sub.add_parser("bind-execution")
    bind.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    bind.add_argument("--execution", required=True)
    bind.add_argument("--execution-metadata", type=Path, required=True)
    poll = sub.add_parser("poll-state")
    poll.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    poll.add_argument("--metadata", type=Path, required=True)
    failure = sub.add_parser("record-failure")
    failure.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    failure.add_argument("--metadata", type=Path, required=True)
    finish_parser = sub.add_parser("finish")
    finish_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments().parse_args(argv)
    if args.command == "canonicalize-external-json":
        _canonicalize_external_json(args.raw, args.output)
    elif args.command == "inventory":
        rows = _StorageReader().inventory(args.prefix)
        _write_exclusive_or_equal(args.output, _canonical_json(rows))
    elif args.command == "validate-predecessor-failure":
        _validate_predecessor_failure(
            _load_json(args.closure, label="v1 failure closure"),
            _load_json(args.metadata, label="v1 failed execution"),
        )
    elif args.command == "validate-preupdate":
        _validate_prepare_inputs(
            code_sha=args.code_sha, image=args.image, build_id=args.build_id,
            job=args.job, job_uid=args.job_uid,
            build_metadata=_load_json(args.build_metadata, label="build metadata"),
            job_before=_load_json(args.job_before, label="job before"),
            executions_before=_load_json(
                args.executions_before, label="executions before",
            ),
            schedulers_before=_load_json(
                args.schedulers_before, label="schedulers before",
            ),
            result_inventory_before=_load_json(
                args.result_inventory_before, label="result inventory before",
            ),
            governance_inventory_before=_load_json(
                args.governance_inventory_before,
                label="governance inventory before",
            ),
        )
    elif args.command == "prepare":
        out = args.output_dir
        manifest = _build_launch_manifest(
            code_sha=args.code_sha, image=args.image, build_id=args.build_id,
            job=args.job, job_uid=args.job_uid,
            build_metadata=_load_json(args.build_metadata, label="build metadata"),
            job_before=_load_json(args.job_before, label="job before"),
            job_after=_load_json(args.job_after, label="job after"),
            executions_before=_load_json(
                args.executions_before, label="executions before",
            ),
            executions_after=_load_json(
                args.executions_after, label="executions after",
            ),
            schedulers_before=_load_json(
                args.schedulers_before, label="schedulers before",
            ),
            schedulers_after=_load_json(
                args.schedulers_after, label="schedulers after",
            ),
            result_inventory_before=_load_json(
                args.result_inventory_before, label="result inventory before",
            ),
            result_inventory_after=_load_json(
                args.result_inventory_after, label="result inventory after",
            ),
            governance_inventory_before=_load_json(
                args.governance_inventory_before,
                label="governance inventory before",
            ),
            governance_inventory_after=_load_json(
                args.governance_inventory_after,
                label="governance inventory after",
            ),
            prepared_at=args.prepared_at,
        )
        raw = _canonical_json(manifest)
        receipt = _StorageReader().create(LAUNCH_MANIFEST_URI, raw)
        _write_exclusive_or_equal(out / "manifest.json", raw)
        _write_exclusive_or_equal(
            out / "manifest-object.json", _canonical_json(receipt),
        )
        _hash_ledger(
            out / "prepared.sha256", base=out, names=PREPARED_INPUT_FILES,
        )
    elif args.command == "validate-prepared":
        _validate_prepared(args.output_dir)
    elif args.command == "create-launch-intent":
        out = args.output_dir
        manifest = _validate_prepared(out)
        manifest_receipt = _load_json(
            out / "manifest-object.json", label="manifest object",
        )
        intent = _create_launch_intent(
            manifest=manifest, manifest_receipt=manifest_receipt,
            job_metadata=_load_json(args.job_metadata, label="launch job"),
            execution_census=_load_json(
                args.execution_census, label="launch executions",
            ),
            schedulers=_load_json(args.schedulers, label="launch schedulers"),
            result_inventory=_load_json(
                args.result_inventory, label="launch result inventory",
            ),
            governance_inventory=_load_json(
                args.governance_inventory, label="launch governance inventory",
            ),
            created_at=args.created_at,
        )
        raw = _canonical_json(intent)
        receipt = _StorageReader().create(LAUNCH_INTENT_URI, raw)
        _write_exclusive_or_equal(out / "launch-intent.json", raw)
        _write_exclusive_or_equal(
            out / "launch-intent-object.json", _canonical_json(receipt),
        )
    elif args.command == "bind-execution":
        out = args.output_dir
        manifest = _validate_prepared(out)
        intent = _load_json(out / "launch-intent.json", label="launch intent")
        intent_receipt = _load_json(
            out / "launch-intent-object.json", label="launch intent object",
        )
        metadata = _load_json(
            args.execution_metadata, label="initial execution metadata",
        )
        state, counts, _ = _validate_execution_contract(
            metadata, execution=args.execution, manifest=manifest,
        )
        if state == "Unknown" and any(counts.values()):
            raise LR8SmokeTransportError("LR8 initial execution counters differ")
        claim = {
            "version": "lr8-training-source-smoke-execution-claim-v1",
            "attempt_id": ATTEMPT_ID,
            "launch_intent": _receipt(
                intent_receipt, uri=LAUNCH_INTENT_URI, label="launch intent",
            ),
            "launch_intent_sha256": _sha_bytes(_canonical_json(intent)),
            "execution": args.execution,
            "initial_state": state,
            "one_execution_only": True,
            "relaunch_licensed": False,
        }
        _validate_execution_claim(
            claim, manifest=manifest, intent=intent,
            intent_receipt=intent_receipt, execution_metadata=metadata,
        )
        raw = _canonical_json(claim)
        receipt = _StorageReader().create(EXECUTION_CLAIM_URI, raw)
        _write_exclusive_or_equal(out / "execution-claim.json", raw)
        _write_exclusive_or_equal(
            out / "execution-claim-object.json", _canonical_json(receipt),
        )
        _hash_ledger(out / "launch.sha256", base=out, names=LAUNCH_FILES)
    elif args.command == "poll-state":
        manifest, execution = _validate_launch(args.output_dir)
        state, _counts, _status = _validate_execution_contract(
            _load_json(args.metadata, label="execution poll"),
            execution=execution, manifest=manifest,
        )
        print(state)
    elif args.command == "record-failure":
        out = args.output_dir
        manifest, execution = _validate_launch(out)
        metadata = _load_json(args.metadata, label="failed execution")
        state, counts, status = _validate_execution_contract(
            metadata, execution=execution, manifest=manifest,
        )
        if state != "False" or counts["succeeded"] != 0 or \
                counts["failed"] != 1 or counts["retried"] != 0 or \
                not status.get("completionTime"):
            raise LR8SmokeTransportError("LR8 terminal failure differs")
        closure = {
            "version": "lr8-training-source-smoke-failure-v1",
            "attempt_id": ATTEMPT_ID,
            "execution": execution,
            "execution_metadata_sha256": _sha_bytes(_canonical_json(metadata)),
            "disposition": "terminal-failed-no-relaunch-no-result-read",
            "result_body_read": False,
            "historical_outcome_lease_acquired": False,
            "relaunch_licensed": False,
            "production_change_licensed": False,
        }
        _write_exclusive_or_equal(
            out / "failed-execution.json", _canonical_json(metadata),
        )
        _write_exclusive_or_equal(
            out / "failure-closure.json", _canonical_json(closure),
        )
    elif args.command == "finish":
        result = finish(out=args.output_dir)
        print(_canonical_json(result).decode("utf-8"), end="")
    else:  # pragma: no cover
        raise AssertionError(args.command)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LR8SmokeTransportError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
