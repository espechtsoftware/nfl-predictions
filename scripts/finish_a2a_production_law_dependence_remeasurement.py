#!/usr/bin/env python3
"""Frozen transport and strict harvest for the one A2a law remeasurement.

This module owns provenance, reused-job, immutable-object, terminal-execution,
and lease-close validation.  It has no deploy, execute, retry, cancellation,
lineup, candidate, or outcome-query path.  The result body is opened only
after the live launch manifest, live lease, terminal execution, and sole-object
inventory have all passed.
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

from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import storage


ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import run_a2a_production_law_dependence_remeasurement as runner  # noqa: E402
from nfl_dfs.analysis import a2a_production_law_dependence as decision  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
RUN_ID: Final = "20260820-a2a-production-law-dependence-remeasurement-v1"
JOB: Final = "atlas-minimal-c-s2023-w1-v1"
JOB_UID: Final = "d6e4b8c1-5950-46b7-8869-7e34dbf29ad2"
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
TIMEOUT_SECONDS: Final = "14400"
RESULT_PREFIX: Final = (
    "gs://nfl-predictions-503414-raw/research/"
    f"a2a-production-law-dependence-runs/{RUN_ID}"
)
RESULT_URI: Final = f"{RESULT_PREFIX}/report.json"
MANIFEST_URI: Final = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    f"a2a-production-law-dependence/{RUN_ID}/launch-manifest.json"
)
LAUNCH_INTENT_URI: Final = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    f"a2a-production-law-dependence/{RUN_ID}/launch-intent.json"
)
RELEASE_INTENT_URI: Final = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    f"a2a-production-law-dependence/{RUN_ID}/lease-release-intent.json"
)
LEASE_URI: Final = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "historical-outcome-active-v1.json"
)
DEFAULT_OUT: Final = (
    ROOT / "reports/a2a-production-law-dependence-runs" / RUN_ID
)
OUTCOME_BLIND_SMOKE_SHA256: Final = (
    "a8d61cd8b4646af70dea6ac30c79e53b61d5c0f72be9f7c13c7f88e500531c7f"
)

IMPLEMENTATION_PATHS: Final = {
    "protocol": (
        "reports/2026-08-20-a2a-production-law-dependence-"
        "remeasurement-protocol.md"
    ),
    "transform": "src/nfl_dfs/research/a2a_rank_factor_split.py",
    "estimator": "src/nfl_dfs/analysis/final_served_dependence.py",
    "decision": "src/nfl_dfs/analysis/a2a_production_law_dependence.py",
    "source_adapter": "scripts/run_a2a_rank_factor_split_census.py",
    "object_identity": "src/nfl_dfs/research/object_identity.py",
    "runner": "scripts/run_a2a_production_law_dependence_remeasurement.py",
    "mechanism_license": (
        "reports/a2a-rank-factor-split-runs/"
        "20260820-a2a-rank-factor-split-scorefree-v2/result.json"
    ),
    "control_report": (
        "reports/production-law-dependence-runs/"
        "20260817-production-law-dependence-remeasurement-v1/report.json"
    ),
    "source_lock": (
        "reports/production-law-dependence-runs/"
        "20260817-production-law-dependence-source-lock-v1/source-lock.json"
    ),
    "outcome_blind_smoke": (
        "reports/a2a-production-law-dependence-runs/"
        f"{RUN_ID}/local-outcome-blind-smoke.json"
    ),
    "lease_tool": "scripts/historical_outcome_lease.py",
    "finisher": (
        "scripts/finish_a2a_production_law_dependence_remeasurement.py"
    ),
    "launcher": (
        "scripts/cloud_a2a_production_law_dependence_remeasurement.sh"
    ),
    "watcher": "scripts/watch_a2a_production_law_dependence_queue.sh",
    "chain_status": "scripts/chain_status.sh",
    "dockerfile": "Dockerfile",
    "cloudbuild": "cloudbuild.yaml",
}
TRANSPORT_REPAIR_ENV: Final = {
    "finisher": "A2A_REMEASUREMENT_FINISHER_REPAIR_SHA256",
    "launcher": "A2A_REMEASUREMENT_LAUNCHER_REPAIR_SHA256",
    "watcher": "A2A_REMEASUREMENT_WATCHER_REPAIR_SHA256",
    "chain_status": "A2A_REMEASUREMENT_CHAIN_STATUS_REPAIR_SHA256",
}

MANIFEST_KEYS: Final = frozenset({
    "version", "status", "run_id", "protocol_sha256", "code", "image",
    "build", "job", "execution_contract", "implementation",
    "mechanism_license", "source_lock", "output", "lease", "preflight",
    "historical_looks", "uses_realized_outcomes",
    "actual_outcomes_queried_before_execution",
    "candidate_or_lineup_scores_read", "production_change_licensed",
})
OBJECT_KEYS: Final = frozenset({
    "uri", "generation", "metageneration", "bytes", "sha256",
})
RECEIPT_OBJECT_KEYS: Final = OBJECT_KEYS | {"create_only"}
PREPARED_FILES: Final = frozenset({
    "build-metadata.json", "job-before.json", "job-after.json",
    "job-executions-before.json", "job-executions-after.json",
    "schedulers-before.json", "schedulers-after.json", "manifest.json",
    "manifest-object.json", "prefix-before.json", "prefix-after.json",
    "lease-before.json", "lease-after.json",
})
LAUNCH_FILES: Final = frozenset({
    "prepared.sha256", "manifest.json", "manifest-object.json",
    "lease-receipt.json", "job-launch.json", "job-executions-launch.json",
    "schedulers-launch.json", "launch-intent.json",
    "launch-intent-object.json", "job-launch-final.json",
    "job-executions-launch-final.json", "schedulers-launch-final.json",
    "prefix-launch.json", "prefix-launch-final.json", "executions.txt",
})


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
            raw, object_pairs_hook=_strict_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(f"A2a {label} is not strict JSON") from exc

    def check(item: Any) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise RuntimeError(f"A2a {label} contains nonfinite JSON")
        if isinstance(item, dict):
            for child in item.values():
                check(child)
        elif isinstance(item, list):
            for child in item:
                check(child)

    check(value)
    return value


def _load_json(path: Path, *, label: str) -> Any:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"A2a {label} is absent")
    return _strict_json_bytes(path.read_bytes(), label=label)


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ) + "\n"
    ).encode("utf-8")


def _sha_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _sha(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _hex(value: object, *, length: int, label: str) -> str:
    text = str(value)
    if re.fullmatch(rf"[0-9a-f]{{{length}}}", text) is None:
        raise RuntimeError(f"A2a {label} differs")
    return text


def _positive_int(value: object, *, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise RuntimeError(f"A2a {label} differs")
    return value


def _nonnegative_int(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        raise RuntimeError(f"A2a {label} differs")
    return value


def _utc_timestamp(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"A2a {label} differs")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"A2a {label} differs") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise RuntimeError(f"A2a {label} differs")
    return value


def _gcs_parts(uri: str) -> tuple[str, str]:
    if not re.fullmatch(r"gs://[^/]+/.+", uri):
        raise RuntimeError("A2a GCS URI differs")
    return tuple(uri[5:].split("/", 1))  # type: ignore[return-value]


def _write_exclusive_or_equal(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != raw:
            raise RuntimeError(f"A2a immutable local file differs: {path}")


def _canonicalize_external_json(raw_path: Path, output: Path) -> Any:
    value = _strict_json_bytes(raw_path.read_bytes(), label="external JSON")
    _write_exclusive_or_equal(output, _canonical_json(value))
    return value


def _validate_smoke_staging(
    out: Path, *, code_sha: str, root: Path = ROOT,
    git_loader: Callable[[Path, str, str], bytes] | None = None,
) -> None:
    """Allow preparation to begin only in the committed smoke-only run dir."""
    if out.is_symlink() or not out.is_dir():
        raise RuntimeError("A2a smoke staging directory differs")
    children = tuple(out.iterdir())
    if len(children) != 1 or children[0].name != \
            "local-outcome-blind-smoke.json" or children[0].is_symlink() or \
            not children[0].is_file():
        raise RuntimeError("A2a smoke staging inventory differs")
    relative = children[0].resolve().relative_to(root.resolve()).as_posix()
    raw = children[0].read_bytes()
    loader = _git_blob if git_loader is None else git_loader
    if raw != loader(root, code_sha, relative):
        raise RuntimeError("A2a smoke staging differs from source commit")
    smoke = _strict_json_bytes(raw, label="outcome-blind smoke")
    if not isinstance(smoke, dict) or \
            _sha_bytes(raw) != OUTCOME_BLIND_SMOKE_SHA256 or set(smoke) != {
                "version", "uses_realized_outcomes",
                "actual_outcomes_queried", "candidate_or_lineup_scores_read",
                "static_sources", "control_reference", "mechanism_license",
                "source_lock", "artifact", "slate", "block", "mechanics",
                "coverage",
            } or smoke.get("version") != (
                "a2a-production-law-dependence-outcome-blind-smoke-v1"
            ) or smoke.get("uses_realized_outcomes") is not False or \
            smoke.get("actual_outcomes_queried") is not False or \
            smoke.get("candidate_or_lineup_scores_read") is not False or \
            smoke.get("mechanics", {}).get("passes") is not True:
        raise RuntimeError("A2a outcome-blind smoke receipt differs")


def _metadata(
    value: Mapping[str, Any], *, uri: str, label: str,
    create_only: bool | None = None,
) -> dict[str, Any]:
    keys = RECEIPT_OBJECT_KEYS if create_only is not None else OBJECT_KEYS
    if set(value) != keys or value.get("uri") != uri:
        raise RuntimeError(f"A2a {label} object fields differ")
    generation = str(value.get("generation", ""))
    metageneration = str(value.get("metageneration", ""))
    if re.fullmatch(r"[1-9][0-9]*", generation) is None or metageneration != "1":
        raise RuntimeError(f"A2a {label} object identity differs")
    result = {
        "uri": uri,
        "generation": generation,
        "metageneration": metageneration,
        "bytes": _positive_int(value.get("bytes"), label=f"{label} bytes"),
        "sha256": _hex(value.get("sha256"), length=64, label=f"{label} SHA"),
    }
    if create_only is not None:
        if value.get("create_only") is not create_only:
            raise RuntimeError(f"A2a {label} create-only proof differs")
        result["create_only"] = create_only
    return result


def _blob_metadata(blob: Any, *, uri: str, raw: bytes) -> dict[str, Any]:
    return {
        "uri": uri,
        "generation": str(blob.generation),
        "metageneration": str(blob.metageneration),
        "bytes": len(raw),
        "sha256": _sha_bytes(raw),
    }


def _download_generation(
    client: storage.Client, identity: Mapping[str, Any], *, label: str,
) -> tuple[dict[str, Any], bytes]:
    expected = _metadata(
        identity, uri=str(identity.get("uri", "")), label=label,
    )
    bucket_name, object_name = _gcs_parts(expected["uri"])
    blob = client.bucket(bucket_name).blob(
        object_name, generation=int(expected["generation"]),
    )
    blob.reload()
    raw = blob.download_as_bytes(
        if_generation_match=int(expected["generation"]),
    )
    observed = _blob_metadata(blob, uri=expected["uri"], raw=raw)
    if observed != expected:
        raise RuntimeError(f"A2a {label} changed")
    return observed, raw


def _upload_create_once_or_same(
    client: storage.Client, uri: str, raw: bytes,
) -> dict[str, Any]:
    bucket_name, object_name = _gcs_parts(uri)
    blob = client.bucket(bucket_name).blob(object_name)
    try:
        blob.upload_from_string(
            raw, content_type="application/json", if_generation_match=0,
        )
    except PreconditionFailed:
        blob.reload()
        existing = blob.download_as_bytes(
            if_generation_match=int(blob.generation),
        )
        if existing != raw:
            raise RuntimeError(f"A2a immutable object already differs: {uri}")
    blob.reload()
    observed_raw = blob.download_as_bytes(
        if_generation_match=int(blob.generation),
    )
    if observed_raw != raw:
        raise RuntimeError(f"A2a immutable object reopen differs: {uri}")
    value = {**_blob_metadata(blob, uri=uri, raw=raw), "create_only": True}
    return _metadata(value, uri=uri, label="published", create_only=True)


def _prefix_inventory(client: storage.Client) -> list[dict[str, Any]]:
    bucket_name, object_prefix = _gcs_parts(RESULT_PREFIX + "/")
    rows = []
    for blob in client.list_blobs(bucket_name, prefix=object_prefix):
        uri = f"gs://{bucket_name}/{blob.name}"
        rows.append({
            "uri": uri,
            "generation": str(blob.generation),
            "metageneration": str(blob.metageneration),
            "bytes": int(blob.size or 0),
        })
    return sorted(rows, key=lambda row: row["uri"])


def _require_empty_prefix(client: storage.Client) -> None:
    if _prefix_inventory(client):
        raise RuntimeError("A2a immutable result prefix is not empty")


def _require_lease_absent(client: storage.Client) -> None:
    bucket_name, object_name = _gcs_parts(LEASE_URI)
    blob = client.bucket(bucket_name).blob(object_name)
    try:
        blob.reload()
    except NotFound:
        return
    raise RuntimeError("A2a historical-outcome lease is already held")


def _absence_receipt(*, kind: str, checked_at: str) -> dict[str, Any]:
    if kind == "result-prefix":
        target = RESULT_PREFIX
    elif kind == "historical-outcome-lease":
        target = LEASE_URI
    else:
        raise RuntimeError("A2a absence-receipt kind differs")
    return {
        "version": "a2a-production-law-dependence-absence-receipt-v1",
        "kind": kind,
        "target": target,
        "state": "absent",
        "checked_at": _utc_timestamp(checked_at, label="absence check time"),
    }


def _validate_absence_receipt(value: object, *, kind: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "kind", "target", "state", "checked_at",
    }:
        raise RuntimeError("A2a absence receipt fields differ")
    expected = _absence_receipt(kind=kind, checked_at=str(value["checked_at"]))
    if value != expected:
        raise RuntimeError("A2a absence receipt differs")
    return value


def _capture_absence(
    *, kind: str, output: Path, client: storage.Client | None = None,
) -> dict[str, Any]:
    gcs = storage.Client(project=PROJECT) if client is None else client
    if kind == "result-prefix":
        _require_empty_prefix(gcs)
    elif kind == "historical-outcome-lease":
        _require_lease_absent(gcs)
    else:
        raise RuntimeError("A2a absence capture kind differs")
    value = _absence_receipt(
        kind=kind, checked_at=datetime.now(timezone.utc).isoformat(),
    )
    _write_exclusive_or_equal(output, _canonical_json(value))
    return value


def _git_blob(root: Path, code_sha: str, relative: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), "show", f"{code_sha}:{relative}"],
        check=True, capture_output=True,
    ).stdout


def _implementation_receipts(
    *, root: Path, code_sha: str,
    git_loader: Callable[[Path, str, str], bytes] = _git_blob,
) -> dict[str, dict[str, str]]:
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None:
        raise RuntimeError("A2a source commit differs")
    result = {}
    for key, relative in IMPLEMENTATION_PATHS.items():
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"A2a implementation is absent: {relative}")
        current = path.read_bytes()
        committed = git_loader(root, code_sha, relative)
        if current != committed:
            raise RuntimeError(f"A2a implementation differs from commit: {relative}")
        result[key] = {"path": relative, "sha256": _sha_bytes(current)}
    if result["protocol"]["sha256"] != runner.PROTOCOL_SHA256 or \
            result["decision"]["sha256"] != runner.DECISION_SOURCE_SHA256 or \
            result["source_adapter"]["sha256"] != \
            runner.SOURCE_ADAPTER_SHA256 or \
            result["runner"]["sha256"] != _sha(ROOT / IMPLEMENTATION_PATHS["runner"]):
        raise RuntimeError("A2a frozen implementation identities differ")
    return result


def _validate_current_implementation(
    manifest: Mapping[str, Any], *, root: Path = ROOT,
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    frozen = manifest.get("implementation")
    if not isinstance(frozen, dict) or set(frozen) != set(IMPLEMENTATION_PATHS):
        raise RuntimeError("A2a implementation manifest population differs")
    values = os.environ if env is None else env
    repairs: dict[str, str] = {}
    for key, relative in IMPLEMENTATION_PATHS.items():
        row = frozen.get(key)
        if not isinstance(row, dict) or set(row) != {"path", "sha256"} or \
                row.get("path") != relative:
            raise RuntimeError(f"A2a implementation row differs: {key}")
        expected = _hex(row.get("sha256"), length=64, label=f"{key} SHA")
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise RuntimeError(f"A2a frozen implementation path differs: {relative}")
        current = _sha(path)
        if current == expected:
            continue
        repair_name = TRANSPORT_REPAIR_ENV.get(key)
        if repair_name is None or values.get(repair_name) != current:
            raise RuntimeError(f"A2a frozen implementation changed: {relative}")
        repairs[key] = current
    return repairs


def _image_tag(code_sha: str) -> str:
    return f"{IMAGE_REPOSITORY}:a2a-remeasurement-{code_sha[:7]}"


def _expected_cloud_build_steps(image_tag: str) -> list[dict[str, Any]]:
    """Return the exact normalized three-step build frozen by cloudbuild.yaml."""
    full_test = (
        "apt-get update\n"
        "apt-get install -y --no-install-recommends git libgomp1\n"
        "pip install --no-cache-dir '.[gcp,app,dev]'\n"
        "PYTHONPATH=. pytest\n"
    )
    python_smokes = (
        "run_atlas_matched_diversity_mvp.py",
        "run_atlas_historical_score_diagnostic.py",
        "run_atlas_historical_score_diagnostic_v3.py",
        "run_atlas_historical_score_diagnostic_v4.py",
        "run_constraint_lattice_scorefree.py",
        "aggregate_constraint_lattice_scorefree.py",
        "run_constraint_lattice_support_census.py",
        "aggregate_constraint_lattice_support_census.py",
        "run_constraint_lattice_resource_preflight.py",
        "run_recourse_aware_initial_scorefree.py",
        "aggregate_recourse_aware_initial_scorefree.py",
        "run_coherent_market_state_scorefree.py",
        "aggregate_coherent_market_state_scorefree.py",
        "run_coherent_market_state_historical_score.py",
        "run_production_law_dependence_source_lock.py",
        "run_production_law_dependence_remeasurement.py",
        "run_a2a_rank_factor_split_census.py",
        "run_a2a_production_law_dependence_remeasurement.py",
        "finish_a2a_production_law_dependence_remeasurement.py",
    )
    bash_smokes = (
        "cloud_a2a_production_law_dependence_remeasurement.sh",
        "watch_a2a_production_law_dependence_queue.sh",
    )
    trailing_python_smokes = (
        "run_atlas_minimal_world_selection_c.py",
        "run_a7_select_ladder.py",
        "freeze_a7_select_ladder.py",
        "finish_a7_select_ladder.py",
    )
    trailing_bash_smokes = (
        "cloud_a7_select_ladder.sh",
        "watch_a7_select_ladder_queue.sh",
    )
    smoke = "".join(
        f"docker run --rm '{image_tag}' \\\n"
        f"  python scripts/{name} --help >/dev/null\n"
        for name in python_smokes
    ) + "".join(
        f"docker run --rm '{image_tag}' \\\n"
        f"  bash -n scripts/{name}\n"
        for name in bash_smokes
    ) + "".join(
        f"docker run --rm '{image_tag}' \\\n"
        f"  python scripts/{name} --help >/dev/null\n"
        for name in trailing_python_smokes
    ) + "".join(
        f"docker run --rm '{image_tag}' \\\n"
        f"  bash -n scripts/{name}\n"
        for name in trailing_bash_smokes
    )
    common = {
        "env": [], "dir": "", "secretEnv": [], "status": "SUCCESS",
        "allowFailure": False, "allowExitCodes": [], "waitFor": [],
        "timeout": "", "script": "", "volumes": [],
        "automapSubstitutions": False, "exitCode": 0,
    }
    return [
        {
            **common, "name": "python:3.11-slim", "id": "full-test-suite",
            "entrypoint": "bash", "args": ["-ceu", full_test],
        },
        {
            **common, "name": "gcr.io/cloud-builders/docker",
            "id": "build-image", "entrypoint": "",
            "args": ["build", "-t", image_tag, "."],
        },
        {
            **common, "name": "gcr.io/cloud-builders/docker",
            "id": "smoke-atlas-mvp-runner", "entrypoint": "bash",
            "args": ["-ceu", smoke],
        },
    ]


def _validate_build_metadata(
    value: Mapping[str, Any], *, build_id: str, image: str, code_sha: str,
) -> str:
    if re.fullmatch(r"[0-9A-Za-z-]{8,80}", build_id) is None or \
            re.fullmatch(rf"{re.escape(IMAGE_REPOSITORY)}@sha256:[0-9a-f]{{64}}", image) \
            is None or re.fullmatch(r"[0-9a-f]{40}", code_sha) is None:
        raise RuntimeError("A2a immutable build identity differs")
    metadata = value.get("metadata")
    observed_id = value.get("id")
    if observed_id != build_id and not (
        isinstance(metadata, Mapping)
        and metadata.get("build", {}).get("id") == build_id
    ):
        raise RuntimeError("A2a Cloud Build ID differs")
    expected_source = {
        "url": GIT_SOURCE_URL,
        "revision": code_sha,
    }
    provenance = value.get("sourceProvenance")
    if value.get("source") != {"gitSource": expected_source} or \
            not isinstance(provenance, Mapping) or \
            not set(provenance) <= {"resolvedGitSource", "fileHashes"} or \
            provenance.get("resolvedGitSource") != expected_source or \
            provenance.get("fileHashes") not in (None, {}):
        raise RuntimeError("A2a Cloud Build resolved Git source differs")
    substitutions = value.get("substitutions")
    tag = _image_tag(code_sha)
    if not isinstance(substitutions, Mapping) or \
            substitutions.get("_IMAGE") != tag:
        raise RuntimeError("A2a Cloud Build image substitution differs")
    declared = {
        substitutions[key] for key in ("COMMIT_SHA", "_CODE_SHA")
        if key in substitutions
    }
    if declared and declared != {code_sha}:
        raise RuntimeError("A2a Cloud Build declared commit differs")
    steps = value.get("steps")
    if not isinstance(steps, list) or len(steps) != 3:
        raise RuntimeError("A2a Cloud Build validation steps differ")
    normalized_steps = []
    for row in steps:
        if not isinstance(row, Mapping):
            raise RuntimeError("A2a Cloud Build validation step differs")
        normalized_steps.append({
            "name": row.get("name"), "id": row.get("id"),
            "entrypoint": row.get("entrypoint", ""),
            "args": row.get("args", []), "env": row.get("env", []),
            "dir": row.get("dir", ""),
            "secretEnv": row.get("secretEnv", []),
            "status": row.get("status"),
            "allowFailure": row.get("allowFailure", False),
            "allowExitCodes": row.get("allowExitCodes", []),
            "waitFor": row.get("waitFor", []),
            "timeout": row.get("timeout", ""),
            "script": row.get("script", ""),
            "volumes": row.get("volumes", []),
            "automapSubstitutions": row.get(
                "automapSubstitutions", False,
            ),
            "exitCode": row.get("exitCode", 0),
        })
    options = value.get("options")
    allowed_option_keys = {
        "machineType", "diskSizeGb", "substitutionOption",
        "dynamicSubstitutions", "automapSubstitutions",
        "logStreamingOption", "logging", "env", "secretEnv", "volumes",
        "sourceProvenanceHash", "requestedVerifyOption", "pool",
        "workerPool", "defaultLogsBucketBehavior",
        "enableStructuredLogging",
    }
    if not isinstance(options, Mapping) or not set(options) <= \
            allowed_option_keys:
        raise RuntimeError("A2a Cloud Build options differ")
    normalized_options = {
        "machineType": options.get("machineType", "UNSPECIFIED"),
        "diskSizeGb": str(options.get("diskSizeGb", "100")),
        "substitutionOption": options.get(
            "substitutionOption", "MUST_MATCH",
        ),
        "dynamicSubstitutions": options.get("dynamicSubstitutions", False),
        "automapSubstitutions": options.get("automapSubstitutions", False),
        "logStreamingOption": options.get(
            "logStreamingOption", "STREAM_DEFAULT",
        ),
        "logging": options.get("logging", "LEGACY"),
        "env": options.get("env", []),
        "secretEnv": options.get("secretEnv", []),
        "volumes": options.get("volumes", []),
        "sourceProvenanceHash": options.get("sourceProvenanceHash", []),
        "requestedVerifyOption": options.get(
            "requestedVerifyOption", "NOT_VERIFIED",
        ),
        "pool": options.get("pool", {}),
        "workerPool": options.get("workerPool", ""),
        "defaultLogsBucketBehavior": options.get(
            "defaultLogsBucketBehavior",
            "DEFAULT_LOGS_BUCKET_BEHAVIOR_UNSPECIFIED",
        ),
        "enableStructuredLogging": options.get(
            "enableStructuredLogging", False,
        ),
    }
    expected_options = {
        "machineType": "E2_HIGHCPU_8", "diskSizeGb": "100",
        "substitutionOption": "MUST_MATCH", "dynamicSubstitutions": False,
        "automapSubstitutions": False,
        "logStreamingOption": "STREAM_DEFAULT", "logging": "LEGACY",
        "env": [], "secretEnv": [], "volumes": [],
        "sourceProvenanceHash": [], "requestedVerifyOption": "NOT_VERIFIED",
        "pool": {}, "workerPool": "",
        "defaultLogsBucketBehavior": "DEFAULT_LOGS_BUCKET_BEHAVIOR_UNSPECIFIED",
        "enableStructuredLogging": False,
    }
    digest = image.rsplit("@", 1)[1]
    images = value.get("results", {}).get("images", [])
    if value.get("status") != "SUCCESS" or value.get("images") != [tag] or \
            value.get("artifacts") != {"images": [tag]} or \
            value.get("secrets") is not None or \
            value.get("availableSecrets") is not None or \
            value.get("timeout") != "10800s" or \
            value.get("serviceAccount") != BUILD_SERVICE_ACCOUNT or \
            value.get("logsBucket") != BUILD_LOGS_BUCKET or \
            normalized_options != expected_options or \
            normalized_steps != _expected_cloud_build_steps(tag) or not any(
                isinstance(row, Mapping) and row.get("name") == tag
                and row.get("digest") == digest
                for row in images
            ):
        raise RuntimeError("A2a Cloud Build/test/image gate differs")
    return tag


def _execution_contract(*, code_sha: str, image: str) -> dict[str, Any]:
    return {
        "image": image,
        "command": ["python"],
        "args": [
            "scripts/run_a2a_production_law_dependence_remeasurement.py",
            "--mode", "historical", "--execute-frozen",
            "--protocol-sha256", runner.PROTOCOL_SHA256,
            "--output-uri", RESULT_URI,
        ],
        "env": {
            "A2A_REMEASUREMENT_ENABLED": "1",
            "ANALYSIS_IMAGE": image,
            "CODE_SHA": code_sha,
        },
        "working_dir": "",
        "volume_mounts": [],
        "volumes": [],
        "startup_probe": None,
        "secret_environment": False,
        "tasks": 1,
        "parallelism": 1,
        "resources": {"cpu": CPU, "memory": MEMORY},
        "max_retries": 0,
        "timeout_seconds": int(TIMEOUT_SECONDS),
        "service_account": SERVICE_ACCOUNT,
    }


def _job_spec_sha256(value: Mapping[str, Any]) -> str:
    spec = value.get("spec")
    if not isinstance(spec, dict) or not spec:
        raise RuntimeError("A2a reused-job spec is absent")
    return _sha_bytes(_canonical_json(spec))


def _job_identity(value: Mapping[str, Any]) -> tuple[str, str, str]:
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping) or metadata.get("name") != JOB or \
            metadata.get("uid") != JOB_UID:
        raise RuntimeError("A2a reused-job identity differs")
    generation = _positive_int(
        metadata.get("generation"), label="reused-job generation",
    )
    return str(metadata["uid"]), str(generation), _job_spec_sha256(value)


def _validate_job_spec(
    value: Mapping[str, Any], *, code_sha: str, image: str,
) -> tuple[str, str, str]:
    uid, generation, spec_sha = _job_identity(value)
    expected = _execution_contract(code_sha=code_sha, image=image)
    spec = value.get("spec", {})
    outer = spec.get("template", {}).get("spec", {})
    task = outer.get("template", {}).get("spec", {}) \
        if isinstance(outer, Mapping) else {}
    containers = task.get("containers", []) if isinstance(task, Mapping) else []
    if _positive_int(
        outer.get("taskCount"), label="reused-job task count",
    ) != 1 or _positive_int(
        outer.get("parallelism"), label="reused-job parallelism",
    ) != 1 or not isinstance(containers, list) or len(containers) != 1:
        raise RuntimeError("A2a reused-job task shape differs")
    container = containers[0]
    env_rows = container.get("env", []) if isinstance(container, Mapping) else []
    if not isinstance(env_rows, list) or any(
        not isinstance(row, dict) or set(row) != {"name", "value"}
        or not isinstance(row["name"], str) or not isinstance(row["value"], str)
        for row in env_rows
    ):
        raise RuntimeError("A2a reused-job environment differs")
    env = {row["name"]: row["value"] for row in env_rows}
    if len(env) != len(env_rows) or env != expected["env"] or \
            container.get("image") != image or \
            container.get("command") != expected["command"] or \
            container.get("args") != expected["args"] or \
            container.get("workingDir", "") != "" or \
            container.get("volumeMounts", []) != [] or \
            container.get("startupProbe") not in (None, {}) or \
            container.get("resources", {}).get("limits") != \
            expected["resources"] or task.get("volumes", []) != [] or \
            _nonnegative_int(
                task.get("maxRetries"), label="reused-job max retries",
            ) != 0 or type(task.get("timeoutSeconds")) is not str or \
            task.get("timeoutSeconds") != TIMEOUT_SECONDS or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise RuntimeError("A2a reused-job executable contract differs")
    return uid, generation, spec_sha


def _validate_job_idle(value: object) -> None:
    if not isinstance(value, list):
        raise RuntimeError("A2a reused-job execution census differs")
    for row in value:
        if not isinstance(row, Mapping):
            raise RuntimeError("A2a reused-job execution row differs")
        completed = [
            item for item in row.get("status", {}).get("conditions", [])
            if isinstance(item, Mapping) and item.get("type") == "Completed"
        ]
        if len(completed) != 1 or completed[0].get("status") not in {
            "True", "False",
        }:
            raise RuntimeError("A2a reused job is not idle")


def _validate_unscheduled(value: object) -> None:
    if not isinstance(value, list):
        raise RuntimeError("A2a scheduler census differs")
    marker = f"/jobs/{JOB}"
    for row in value:
        if not isinstance(row, Mapping):
            raise RuntimeError("A2a scheduler row differs")
        target = row.get("httpTarget", {})
        uri = target.get("uri", "") if isinstance(target, Mapping) else ""
        if not isinstance(uri, str):
            raise RuntimeError("A2a scheduler target differs")
        if marker in uri:
            raise RuntimeError("A2a reused job has a scheduler target")


def _build_launch_manifest(
    *, code_sha: str, image: str, build_id: str,
    build_metadata: Mapping[str, Any], job_before: Mapping[str, Any],
    job_after: Mapping[str, Any], executions_before: object,
    executions_after: object, schedulers_before: object,
    schedulers_after: object, prefix_before: Mapping[str, Any],
    prefix_after: Mapping[str, Any], lease_before: Mapping[str, Any],
    lease_after: Mapping[str, Any], frozen_at: str, root: Path = ROOT,
    git_loader: Callable[[Path, str, str], bytes] = _git_blob,
) -> dict[str, Any]:
    tag = _validate_build_metadata(
        build_metadata, build_id=build_id, image=image, code_sha=code_sha,
    )
    _validate_job_idle(executions_before)
    _validate_job_idle(executions_after)
    _validate_unscheduled(schedulers_before)
    _validate_unscheduled(schedulers_after)
    _validate_absence_receipt(prefix_before, kind="result-prefix")
    _validate_absence_receipt(prefix_after, kind="result-prefix")
    _validate_absence_receipt(lease_before, kind="historical-outcome-lease")
    _validate_absence_receipt(lease_after, kind="historical-outcome-lease")
    prior_uid, prior_generation, prior_spec = _job_identity(job_before)
    uid, generation, spec_sha = _validate_job_spec(
        job_after, code_sha=code_sha, image=image,
    )
    if uid != prior_uid or int(generation) <= int(prior_generation):
        raise RuntimeError("A2a reused-job generation chain differs")
    implementation = _implementation_receipts(
        root=root, code_sha=code_sha, git_loader=git_loader,
    )
    timestamp = _utc_timestamp(frozen_at, label="manifest freeze time")
    contract = _execution_contract(code_sha=code_sha, image=image)
    manifest = {
        "version": "a2a-production-law-dependence-launch-manifest-v1",
        "status": "frozen-before-one-historical-execution",
        "run_id": RUN_ID,
        "protocol_sha256": runner.PROTOCOL_SHA256,
        "code": {"commit_sha": code_sha},
        "image": {"uri": image},
        "build": {
            "id": build_id,
            "tag": tag,
            "metadata_sha256": _sha_bytes(_canonical_json(build_metadata)),
        },
        "job": {
            "name": JOB,
            "uid": uid,
            "prior_generation": prior_generation,
            "prior_spec_sha256": prior_spec,
            "generation": generation,
            "spec_sha256": spec_sha,
            "service_account": SERVICE_ACCOUNT,
            "update_mode": "reuse-only-update-existing",
            "scheduler_target_absent": True,
        },
        "execution_contract": contract,
        "implementation": implementation,
        "mechanism_license": {
            "uri": runner.A2A_RESULT_URI,
            "generation": runner.A2A_RESULT_GENERATION,
            "sha256": runner.A2A_RESULT_SHA256,
            "bytes": runner.A2A_RESULT_BYTES,
            "disposition": "a2a-scorefree-mechanism-passes",
        },
        "source_lock": {
            "uri": runner.a2a_source.SOURCE_LOCK_URI,
            "generation": runner.a2a_source.SOURCE_LOCK_GENERATION,
            "sha256": runner.a2a_source.SOURCE_LOCK_SHA256,
            "bytes": runner.a2a_source.SOURCE_LOCK_BYTES,
        },
        "output": {
            "prefix": RESULT_PREFIX,
            "uri": RESULT_URI,
            "prelaunch_inventory": [],
            "create_only": True,
        },
        "lease": {
            "active_uri": LEASE_URI,
            "release_intent_uri": RELEASE_INTENT_URI,
            "launch_intent_uri": LAUNCH_INTENT_URI,
        },
        "preflight": {
            "frozen_at": timestamp,
            "job_idle_before_update": True,
            "job_idle_after_update": True,
            "scheduler_census_before_sha256": _sha_bytes(
                _canonical_json(schedulers_before)
            ),
            "scheduler_census_after_sha256": _sha_bytes(
                _canonical_json(schedulers_after)
            ),
            "prefix_absence_before_sha256": _sha_bytes(
                _canonical_json(prefix_before)
            ),
            "prefix_absence_after_sha256": _sha_bytes(
                _canonical_json(prefix_after)
            ),
            "lease_absence_before_sha256": _sha_bytes(
                _canonical_json(lease_before)
            ),
            "lease_absence_after_sha256": _sha_bytes(
                _canonical_json(lease_after)
            ),
        },
        "historical_looks": 1,
        "uses_realized_outcomes": True,
        "actual_outcomes_queried_before_execution": False,
        "candidate_or_lineup_scores_read": False,
        "production_change_licensed": False,
    }
    _validate_manifest(manifest, root=root, env={}, validate_files=True)
    return manifest


def _validate_prepare_inputs(
    *, code_sha: str, image: str, build_id: str,
    build_metadata: Mapping[str, Any], job_before: Mapping[str, Any],
    executions_before: object, schedulers_before: object,
    root: Path = ROOT,
    git_loader: Callable[[Path, str, str], bytes] = _git_blob,
) -> None:
    _validate_build_metadata(
        build_metadata, build_id=build_id, image=image, code_sha=code_sha,
    )
    _implementation_receipts(
        root=root, code_sha=code_sha, git_loader=git_loader,
    )
    _job_identity(job_before)
    _validate_job_idle(executions_before)
    _validate_unscheduled(schedulers_before)


def _validate_manifest(
    value: object, *, root: Path = ROOT,
    env: Mapping[str, str] | None = None, validate_files: bool = True,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != MANIFEST_KEYS:
        raise RuntimeError("A2a launch-manifest fields differ")
    fixed = {
        "version": "a2a-production-law-dependence-launch-manifest-v1",
        "status": "frozen-before-one-historical-execution",
        "run_id": RUN_ID,
        "protocol_sha256": runner.PROTOCOL_SHA256,
        "historical_looks": 1,
        "uses_realized_outcomes": True,
        "actual_outcomes_queried_before_execution": False,
        "candidate_or_lineup_scores_read": False,
        "production_change_licensed": False,
    }
    if any(value.get(key) != expected for key, expected in fixed.items()):
        raise RuntimeError("A2a launch-manifest frozen identity differs")
    code = value.get("code")
    image = value.get("image")
    build = value.get("build")
    job = value.get("job")
    if not isinstance(code, dict) or set(code) != {"commit_sha"} or \
            re.fullmatch(r"[0-9a-f]{40}", str(
                code.get("commit_sha", "")
            )) is None or not isinstance(image, dict) or set(image) != {"uri"} or \
            re.fullmatch(
                rf"{re.escape(IMAGE_REPOSITORY)}@sha256:[0-9a-f]{{64}}",
                str(image.get("uri", "")),
            ) is None:
        raise RuntimeError("A2a launch-manifest code/image differs")
    code_sha = str(code["commit_sha"])
    image_uri = str(image["uri"])
    if not isinstance(build, dict) or set(build) != {
        "id", "tag", "metadata_sha256",
    } or build.get("tag") != _image_tag(code_sha) or \
            re.fullmatch(r"[0-9A-Za-z-]{8,80}", str(
                build.get("id", "")
            )) is None or re.fullmatch(r"[0-9a-f]{64}", str(
                build.get("metadata_sha256", "")
            )) is None:
        raise RuntimeError("A2a launch-manifest build differs")
    if not isinstance(job, dict) or set(job) != {
        "name", "uid", "prior_generation", "prior_spec_sha256",
        "generation", "spec_sha256", "service_account", "update_mode",
        "scheduler_target_absent",
    } or job.get("name") != JOB or job.get("uid") != JOB_UID or \
            re.fullmatch(r"[1-9][0-9]*", str(
                job.get("prior_generation", "")
            )) is None or re.fullmatch(r"[1-9][0-9]*", str(
                job.get("generation", "")
            )) is None or int(job["generation"]) <= int(
                job["prior_generation"]
            ) or re.fullmatch(r"[0-9a-f]{64}", str(
                job.get("prior_spec_sha256", "")
            )) is None or re.fullmatch(r"[0-9a-f]{64}", str(
                job.get("spec_sha256", "")
            )) is None or job.get("service_account") != SERVICE_ACCOUNT or \
            job.get("update_mode") != "reuse-only-update-existing" or \
            job.get("scheduler_target_absent") is not True:
        raise RuntimeError("A2a launch-manifest reused-job differs")
    if value.get("execution_contract") != _execution_contract(
        code_sha=code_sha, image=image_uri,
    ):
        raise RuntimeError("A2a launch-manifest execution contract differs")
    if value.get("mechanism_license") != {
        "uri": runner.A2A_RESULT_URI,
        "generation": runner.A2A_RESULT_GENERATION,
        "sha256": runner.A2A_RESULT_SHA256,
        "bytes": runner.A2A_RESULT_BYTES,
        "disposition": "a2a-scorefree-mechanism-passes",
    } or value.get("source_lock") != {
        "uri": runner.a2a_source.SOURCE_LOCK_URI,
        "generation": runner.a2a_source.SOURCE_LOCK_GENERATION,
        "sha256": runner.a2a_source.SOURCE_LOCK_SHA256,
        "bytes": runner.a2a_source.SOURCE_LOCK_BYTES,
    } or value.get("output") != {
        "prefix": RESULT_PREFIX,
        "uri": RESULT_URI,
        "prelaunch_inventory": [],
        "create_only": True,
    } or value.get("lease") != {
        "active_uri": LEASE_URI,
        "release_intent_uri": RELEASE_INTENT_URI,
        "launch_intent_uri": LAUNCH_INTENT_URI,
    }:
        raise RuntimeError("A2a launch-manifest immutable source/output differs")
    preflight = value.get("preflight")
    if not isinstance(preflight, dict) or set(preflight) != {
        "frozen_at", "job_idle_before_update", "job_idle_after_update",
        "scheduler_census_before_sha256", "scheduler_census_after_sha256",
        "prefix_absence_before_sha256", "prefix_absence_after_sha256",
        "lease_absence_before_sha256", "lease_absence_after_sha256",
    } or preflight.get("job_idle_before_update") is not True or \
            preflight.get("job_idle_after_update") is not True:
        raise RuntimeError("A2a launch-manifest preflight differs")
    _utc_timestamp(preflight.get("frozen_at"), label="manifest freeze time")
    _hex(
        preflight.get("scheduler_census_before_sha256"), length=64,
        label="scheduler-before SHA",
    )
    _hex(
        preflight.get("scheduler_census_after_sha256"), length=64,
        label="scheduler-after SHA",
    )
    for key in (
        "prefix_absence_before_sha256", "prefix_absence_after_sha256",
        "lease_absence_before_sha256", "lease_absence_after_sha256",
    ):
        _hex(preflight.get(key), length=64, label=key)
    implementation = value.get("implementation")
    if not isinstance(implementation, dict) or set(implementation) != set(
        IMPLEMENTATION_PATHS
    ):
        raise RuntimeError("A2a launch-manifest implementation differs")
    for key, relative in IMPLEMENTATION_PATHS.items():
        row = implementation.get(key)
        if not isinstance(row, dict) or set(row) != {"path", "sha256"} or \
                row.get("path") != relative:
            raise RuntimeError(f"A2a launch-manifest {key} row differs")
        _hex(row.get("sha256"), length=64, label=f"{key} SHA")
    if implementation["protocol"]["sha256"] != runner.PROTOCOL_SHA256 or \
            implementation["transform"]["sha256"] != \
            runner.TRANSFORM_SOURCE_SHA256 or \
            implementation["estimator"]["sha256"] != \
            runner.ESTIMATOR_SOURCE_SHA256 or \
            implementation["decision"]["sha256"] != \
            runner.DECISION_SOURCE_SHA256 or \
            implementation["source_adapter"]["sha256"] != \
            runner.SOURCE_ADAPTER_SHA256 or \
            implementation["mechanism_license"]["sha256"] != \
            runner.A2A_RESULT_SHA256 or \
            implementation["control_report"]["sha256"] != \
            runner.CONTROL_REPORT_SHA256 or \
            implementation["source_lock"]["sha256"] != \
            runner.a2a_source.SOURCE_LOCK_SHA256 or \
            implementation["outcome_blind_smoke"]["sha256"] != \
            OUTCOME_BLIND_SMOKE_SHA256:
        raise RuntimeError("A2a launch-manifest frozen source hash differs")
    if validate_files:
        _validate_current_implementation(value, root=root, env=env)
    return value


def _manifest_receipt(
    value: object, *, manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "manifest_sha256", "object",
    } or value.get("version") != \
            "a2a-production-law-dependence-manifest-receipt-v1":
        raise RuntimeError("A2a manifest receipt fields differ")
    raw = _canonical_json(manifest)
    if value.get("manifest_sha256") != _sha_bytes(raw):
        raise RuntimeError("A2a manifest receipt body SHA differs")
    obj = value.get("object")
    if not isinstance(obj, Mapping):
        raise RuntimeError("A2a manifest object receipt differs")
    metadata = _metadata(
        obj, uri=MANIFEST_URI, label="launch manifest", create_only=True,
    )
    if metadata["sha256"] != _sha_bytes(raw) or metadata["bytes"] != len(raw):
        raise RuntimeError("A2a manifest object body differs")
    return {"version": value["version"], "manifest_sha256": value[
        "manifest_sha256"
    ], "object": metadata}


def _publish_manifest(
    manifest_path: Path, receipt_path: Path,
    *, client: storage.Client | None = None,
) -> dict[str, Any]:
    manifest = _validate_manifest(
        _load_json(manifest_path, label="launch manifest"),
    )
    raw = _canonical_json(manifest)
    gcs = storage.Client(project=PROJECT) if client is None else client
    obj = _upload_create_once_or_same(gcs, MANIFEST_URI, raw)
    receipt = {
        "version": "a2a-production-law-dependence-manifest-receipt-v1",
        "manifest_sha256": _sha_bytes(raw),
        "object": obj,
    }
    _manifest_receipt(receipt, manifest=manifest)
    _write_exclusive_or_equal(receipt_path, _canonical_json(receipt))
    return receipt


def _load_live_manifest(
    manifest: Mapping[str, Any], receipt: Mapping[str, Any],
    *, client: storage.Client,
) -> dict[str, Any]:
    validated = _manifest_receipt(receipt, manifest=manifest)
    metadata = {
        key: value for key, value in validated["object"].items()
        if key != "create_only"
    }
    _, raw = _download_generation(client, metadata, label="launch manifest")
    if raw != _canonical_json(manifest):
        raise RuntimeError("A2a live launch manifest differs")
    return validated


def _parse_checksum_ledger(path: Path) -> list[tuple[str, str]]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"A2a checksum ledger is absent: {path.name}")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise RuntimeError(f"A2a checksum ledger differs: {path.name}")
        rows.append((match.group(1), match.group(2)))
    if not rows:
        raise RuntimeError(f"A2a checksum ledger is empty: {path.name}")
    return rows


def _validate_hash_ledger(
    path: Path, *, base: Path, expected: set[str] | frozenset[str],
) -> None:
    rows = _parse_checksum_ledger(path)
    if len(rows) != len(expected) or {name for _, name in rows} != set(expected):
        raise RuntimeError(f"A2a checksum population differs: {path.name}")
    for digest, name in rows:
        candidate = base / name
        try:
            candidate.resolve().relative_to(base.resolve())
        except ValueError as exc:
            raise RuntimeError("A2a checksum path escapes run directory") from exc
        if candidate.is_symlink() or not candidate.is_file() or \
                _sha(candidate) != digest:
            raise RuntimeError(f"A2a completed artifact differs: {name}")


def _validate_prepared_local(
    out: Path, *, root: Path = ROOT,
    env: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_hash_ledger(
        out / "prepared.sha256", base=out, expected=PREPARED_FILES,
    )
    manifest = _validate_manifest(
        _load_json(out / "manifest.json", label="launch manifest"),
        root=root, env=env,
    )
    receipt = _manifest_receipt(
        _load_json(out / "manifest-object.json", label="manifest receipt"),
        manifest=manifest,
    )
    build = _load_json(out / "build-metadata.json", label="build metadata")
    _validate_build_metadata(
        build, build_id=manifest["build"]["id"],
        image=manifest["image"]["uri"],
        code_sha=manifest["code"]["commit_sha"],
    )
    if _sha_bytes(_canonical_json(build)) != manifest["build"][
        "metadata_sha256"
    ]:
        raise RuntimeError("A2a prepared build metadata differs")
    before = _load_json(out / "job-before.json", label="job before")
    after = _load_json(out / "job-after.json", label="job after")
    before_identity = _job_identity(before)
    after_identity = _validate_job_spec(
        after, code_sha=manifest["code"]["commit_sha"],
        image=manifest["image"]["uri"],
    )
    expected_before = (
        manifest["job"]["uid"], manifest["job"]["prior_generation"],
        manifest["job"]["prior_spec_sha256"],
    )
    expected_after = (
        manifest["job"]["uid"], manifest["job"]["generation"],
        manifest["job"]["spec_sha256"],
    )
    if before_identity != expected_before or after_identity != expected_after:
        raise RuntimeError("A2a prepared reused-job chain differs")
    for name in ("job-executions-before.json", "job-executions-after.json"):
        _validate_job_idle(_load_json(out / name, label=name))
    schedulers_before = _load_json(
        out / "schedulers-before.json", label="schedulers before",
    )
    schedulers_after = _load_json(
        out / "schedulers-after.json", label="schedulers after",
    )
    _validate_unscheduled(schedulers_before)
    _validate_unscheduled(schedulers_after)
    if _sha_bytes(_canonical_json(schedulers_before)) != manifest[
        "preflight"
    ]["scheduler_census_before_sha256"] or _sha_bytes(
        _canonical_json(schedulers_after)
    ) != manifest["preflight"]["scheduler_census_after_sha256"]:
        raise RuntimeError("A2a prepared scheduler census differs")
    for name, kind, manifest_key in (
        ("prefix-before.json", "result-prefix", "prefix_absence_before_sha256"),
        ("prefix-after.json", "result-prefix", "prefix_absence_after_sha256"),
        (
            "lease-before.json", "historical-outcome-lease",
            "lease_absence_before_sha256",
        ),
        (
            "lease-after.json", "historical-outcome-lease",
            "lease_absence_after_sha256",
        ),
    ):
        receipt_value = _validate_absence_receipt(
            _load_json(out / name, label=name), kind=kind,
        )
        if _sha_bytes(_canonical_json(receipt_value)) != manifest[
            "preflight"
        ][manifest_key]:
            raise RuntimeError("A2a prepared absence proof differs")
    return manifest, receipt


def _validate_lease_receipt(
    value: object, *, manifest: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"lease", "object"}:
        raise RuntimeError("A2a historical-outcome lease receipt differs")
    lease = value.get("lease")
    obj = value.get("object")
    if not isinstance(lease, dict) or set(lease) != {
        "version", "run_id", "job", "code_sha", "image", "acquired_at",
    } or not isinstance(obj, dict) or set(obj) != {
        "uri", "generation", "sha256", "bytes", "create_only",
    }:
        raise RuntimeError("A2a historical-outcome lease fields differ")
    expected = {
        "version": "historical-outcome-active-v1",
        "run_id": RUN_ID,
        "job": JOB,
        "code_sha": manifest["code"]["commit_sha"],
        "image": manifest["image"]["uri"],
    }
    if any(lease.get(key) != item for key, item in expected.items()):
        raise RuntimeError("A2a historical-outcome lease identity differs")
    _utc_timestamp(lease.get("acquired_at"), label="lease acquisition time")
    generation = str(obj.get("generation", ""))
    digest = str(obj.get("sha256", ""))
    if obj.get("uri") != LEASE_URI or obj.get("create_only") is not True or \
            re.fullmatch(r"[1-9][0-9]*", generation) is None or \
            re.fullmatch(r"[0-9a-f]{64}", digest) is None or \
            type(obj.get("bytes")) is not int or obj["bytes"] <= 0:
        raise RuntimeError("A2a historical-outcome lease object differs")
    raw = _canonical_json(lease)
    if len(raw) != obj["bytes"] or _sha_bytes(raw) != digest:
        raise RuntimeError("A2a historical-outcome lease body differs")
    return {"lease": lease, "object": obj}


def _load_live_lease(
    client: storage.Client, receipt: Mapping[str, Any],
    *, manifest: Mapping[str, Any],
) -> tuple[Any, dict[str, Any]]:
    validated = _validate_lease_receipt(receipt, manifest=manifest)
    obj = validated["object"]
    bucket_name, object_name = _gcs_parts(LEASE_URI)
    blob = client.bucket(bucket_name).blob(
        object_name, generation=int(obj["generation"]),
    )
    blob.reload()
    raw = blob.download_as_bytes(if_generation_match=int(obj["generation"]))
    if str(blob.generation) != obj["generation"] or len(raw) != obj["bytes"] or \
            _sha_bytes(raw) != obj["sha256"] or \
            _strict_json_bytes(raw, label="live historical lease") != \
            validated["lease"]:
        raise RuntimeError("A2a live historical-outcome lease changed")
    return blob, validated


def _recover_live_lease(
    *, manifest_path: Path, receipt_path: Path,
    client: storage.Client | None = None,
) -> dict[str, Any]:
    manifest = _validate_manifest(
        _load_json(manifest_path, label="launch manifest"),
    )
    gcs = storage.Client(project=PROJECT) if client is None else client
    bucket_name, object_name = _gcs_parts(LEASE_URI)
    blob = gcs.bucket(bucket_name).blob(object_name)
    blob.reload()
    raw = blob.download_as_bytes(if_generation_match=int(blob.generation))
    lease = _strict_json_bytes(raw, label="recoverable historical lease")
    if not isinstance(lease, dict):
        raise RuntimeError("A2a recoverable historical lease differs")
    receipt = {
        "lease": lease,
        "object": {
            "uri": LEASE_URI,
            "generation": str(blob.generation),
            "sha256": _sha_bytes(raw),
            "bytes": len(raw),
            "create_only": True,
        },
    }
    _validate_lease_receipt(receipt, manifest=manifest)
    canonical = _canonical_json(receipt)
    if receipt_path.exists():
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise RuntimeError("A2a local lease receipt path differs")
        existing = receipt_path.read_bytes()
        if existing == canonical:
            return receipt
        preserved = receipt_path.with_name(receipt_path.name + ".incomplete")
        _write_exclusive_or_equal(preserved, existing)
        receipt_path.unlink()
    elif receipt_path.with_name(receipt_path.name + ".incomplete").exists():
        preserved = receipt_path.with_name(receipt_path.name + ".incomplete")
        if preserved.is_symlink() or not preserved.is_file():
            raise RuntimeError("A2a preserved partial lease receipt differs")
    _write_exclusive_or_equal(receipt_path, canonical)
    return receipt


def _launch_intent(
    *, manifest: Mapping[str, Any], manifest_receipt: Mapping[str, Any],
    lease_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    manifest_receipt = _manifest_receipt(
        manifest_receipt, manifest=manifest,
    )
    lease_receipt = _validate_lease_receipt(
        lease_receipt, manifest=manifest,
    )
    return {
        "version": "a2a-production-law-dependence-launch-intent-v1",
        "run_id": RUN_ID,
        "manifest_object": {
            key: value for key, value in manifest_receipt["object"].items()
            if key != "create_only"
        },
        "lease_object": dict(lease_receipt["object"]),
        "lease_receipt_sha256": _sha_bytes(_canonical_json(lease_receipt)),
        "registered_at": lease_receipt["lease"]["acquired_at"],
        "job": dict(manifest["job"]),
        "execution_contract": dict(manifest["execution_contract"]),
        "result_uri": RESULT_URI,
        "historical_looks": 1,
        "max_retries": 0,
        "relaunch_if_ambiguous": False,
        "production_change_licensed": False,
    }


def _validate_launch_intent(
    value: object, *, manifest: Mapping[str, Any],
    manifest_receipt: Mapping[str, Any], lease_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    expected = _launch_intent(
        manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease_receipt,
    )
    if value != expected:
        raise RuntimeError("A2a launch intent differs")
    return expected


def _intent_receipt(
    value: object, *, intent: Mapping[str, Any], uri: str,
    version: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "version", "intent_sha256", "object",
    } or value.get("version") != version:
        raise RuntimeError("A2a intent receipt fields differ")
    raw = _canonical_json(intent)
    if value.get("intent_sha256") != _sha_bytes(raw):
        raise RuntimeError("A2a intent receipt SHA differs")
    obj = value.get("object")
    if not isinstance(obj, Mapping):
        raise RuntimeError("A2a intent object differs")
    metadata = _metadata(
        obj, uri=uri, label="intent", create_only=True,
    )
    if metadata["sha256"] != _sha_bytes(raw) or metadata["bytes"] != len(raw):
        raise RuntimeError("A2a intent object body differs")
    return {
        "version": version,
        "intent_sha256": value["intent_sha256"],
        "object": metadata,
    }


def _publish_launch_intent(
    out: Path, *, client: storage.Client | None = None,
) -> dict[str, Any]:
    manifest, manifest_receipt = _validate_prepared_local(out)
    lease_receipt = _validate_lease_receipt(
        _load_json(out / "lease-receipt.json", label="lease receipt"),
        manifest=manifest,
    )
    intent = _launch_intent(
        manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease_receipt,
    )
    _write_exclusive_or_equal(out / "launch-intent.json", _canonical_json(intent))
    gcs = storage.Client(project=PROJECT) if client is None else client
    obj = _upload_create_once_or_same(gcs, LAUNCH_INTENT_URI, _canonical_json(intent))
    receipt = {
        "version": "a2a-production-law-dependence-launch-intent-receipt-v1",
        "intent_sha256": _sha_bytes(_canonical_json(intent)),
        "object": obj,
    }
    _intent_receipt(
        receipt, intent=intent, uri=LAUNCH_INTENT_URI,
        version="a2a-production-law-dependence-launch-intent-receipt-v1",
    )
    _write_exclusive_or_equal(
        out / "launch-intent-object.json", _canonical_json(receipt),
    )
    return receipt


def _load_live_launch_intent(
    out: Path, *, manifest: Mapping[str, Any],
    manifest_receipt: Mapping[str, Any], lease_receipt: Mapping[str, Any],
    client: storage.Client,
) -> tuple[dict[str, Any], dict[str, Any]]:
    intent = _validate_launch_intent(
        _load_json(out / "launch-intent.json", label="launch intent"),
        manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease_receipt,
    )
    receipt = _intent_receipt(
        _load_json(
            out / "launch-intent-object.json", label="launch-intent receipt",
        ), intent=intent, uri=LAUNCH_INTENT_URI,
        version="a2a-production-law-dependence-launch-intent-receipt-v1",
    )
    metadata = {
        key: value for key, value in receipt["object"].items()
        if key != "create_only"
    }
    _, raw = _download_generation(client, metadata, label="launch intent")
    if raw != _canonical_json(intent):
        raise RuntimeError("A2a live launch intent differs")
    return intent, receipt


def _validate_launch_ready(
    *, out: Path, job_current: Mapping[str, Any], executions: object,
    schedulers: object, require_intent: bool,
    client: storage.Client | None = None,
) -> None:
    manifest, manifest_receipt = _validate_prepared_local(out)
    gcs = storage.Client(project=PROJECT) if client is None else client
    _load_live_manifest(manifest, manifest_receipt, client=gcs)
    _require_empty_prefix(gcs)
    _validate_job_idle(executions)
    _validate_unscheduled(schedulers)
    current = _validate_job_spec(
        job_current, code_sha=manifest["code"]["commit_sha"],
        image=manifest["image"]["uri"],
    )
    if current != (
        manifest["job"]["uid"], manifest["job"]["generation"],
        manifest["job"]["spec_sha256"],
    ):
        raise RuntimeError("A2a live reused-job generation/spec differs")
    lease = _validate_lease_receipt(
        _load_json(out / "lease-receipt.json", label="lease receipt"),
        manifest=manifest,
    )
    _load_live_lease(gcs, lease, manifest=manifest)
    if require_intent:
        _load_live_launch_intent(
            out, manifest=manifest, manifest_receipt=manifest_receipt,
            lease_receipt=lease, client=gcs,
        )


def _execution_ledger(path: Path) -> tuple[str, str, str]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("A2a execution ledger is absent")
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1:
        raise RuntimeError("A2a execution ledger differs")
    fields = lines[0].split()
    if len(fields) != 3 or fields[0] != JOB or \
            re.fullmatch(rf"{re.escape(JOB)}-[a-z0-9]+", fields[1]) is None or \
            fields[2] != RESULT_URI:
        raise RuntimeError("A2a execution ledger identity differs")
    return fields[0], fields[1], fields[2]


def _validate_launch_local(
    out: Path, *, root: Path = ROOT,
    env: Mapping[str, str] | None = None,
) -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], str,
]:
    _validate_hash_ledger(
        out / "launch.sha256", base=out, expected=LAUNCH_FILES,
    )
    manifest, manifest_receipt = _validate_prepared_local(
        out, root=root, env=env,
    )
    lease = _validate_lease_receipt(
        _load_json(out / "lease-receipt.json", label="lease receipt"),
        manifest=manifest,
    )
    _validate_launch_intent(
        _load_json(out / "launch-intent.json", label="launch intent"),
        manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease,
    )
    for suffix in ("launch", "launch-final"):
        job = _load_json(out / f"job-{suffix}.json", label=f"job {suffix}")
        observed = _validate_job_spec(
            job, code_sha=manifest["code"]["commit_sha"],
            image=manifest["image"]["uri"],
        )
        if observed != (
            manifest["job"]["uid"], manifest["job"]["generation"],
            manifest["job"]["spec_sha256"],
        ):
            raise RuntimeError("A2a launch reused-job identity differs")
        _validate_job_idle(_load_json(
            out / f"job-executions-{suffix}.json",
            label=f"executions {suffix}",
        ))
        _validate_unscheduled(_load_json(
            out / f"schedulers-{suffix}.json", label=f"schedulers {suffix}",
        ))
        _validate_absence_receipt(
            _load_json(
                out / f"prefix-{suffix}.json", label=f"prefix {suffix}",
            ), kind="result-prefix",
        )
    _, execution, _ = _execution_ledger(out / "executions.txt")
    return manifest, manifest_receipt, lease, execution


def _gcloud_execution(name: str) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="a2a-execution-") as directory:
        raw_path = Path(directory) / "execution.raw.json"
        with raw_path.open("xb") as handle:
            subprocess.run([
                "gcloud", "run", "jobs", "executions", "describe", name,
                "--project", PROJECT, "--region", REGION, "--format=json",
            ], check=True, stdout=handle)
        value = _strict_json_bytes(
            raw_path.read_bytes(), label="execution metadata",
        )
    if not isinstance(value, dict):
        raise RuntimeError("A2a execution metadata differs")
    return value


def _execution_count(status: Mapping[str, Any], key: str) -> int:
    return 0 if key not in status else _nonnegative_int(
        status[key], label=f"execution {key}",
    )


def _validate_execution_terminal(
    value: Mapping[str, Any], *, execution: str,
    manifest: Mapping[str, Any], completed_status: str,
) -> None:
    metadata = value.get("metadata")
    status = value.get("status")
    if not isinstance(metadata, Mapping) or not isinstance(status, Mapping):
        raise RuntimeError("A2a execution metadata schema differs")
    labels = metadata.get("labels")
    completed = [
        row for row in status.get("conditions", [])
        if isinstance(row, Mapping) and row.get("type") == "Completed"
    ]
    if metadata.get("name") != execution or _positive_int(
        metadata.get("generation"), label="execution generation",
    ) != 1 or not isinstance(labels, Mapping) or \
            labels.get("run.googleapis.com/job") != JOB or \
            labels.get("run.googleapis.com/jobUid") != JOB_UID or \
            str(labels.get("run.googleapis.com/jobGeneration")) != \
            manifest["job"]["generation"] or _positive_int(
                status.get("observedGeneration"),
                label="execution observed generation",
            ) != 1:
        raise RuntimeError("A2a execution identity differs")
    if completed_status not in {"True", "False"}:
        raise RuntimeError("A2a requested terminal status differs")
    expected_succeeded = 1 if completed_status == "True" else 0
    expected_failed = 0 if completed_status == "True" else 1
    if len(completed) != 1 or completed[0].get("status") != completed_status or \
            _execution_count(status, "succeededCount") != expected_succeeded or \
            _execution_count(status, "failedCount") != expected_failed or \
            _execution_count(status, "cancelledCount") != 0 or \
            _execution_count(status, "retriedCount") != 0 or \
            not isinstance(status.get("completionTime"), str) or \
            not status["completionTime"]:
        raise RuntimeError("A2a execution is not strict terminal success")
    expected = manifest["execution_contract"]
    spec = value.get("spec")
    outer = spec if isinstance(spec, Mapping) else {}
    task = outer.get("template", {}).get("spec", {})
    containers = task.get("containers", []) if isinstance(task, Mapping) else []
    if _positive_int(
        outer.get("taskCount"), label="execution task count",
    ) != 1 or _positive_int(
        outer.get("parallelism"), label="execution parallelism",
    ) != 1 or not isinstance(containers, list) or len(containers) != 1:
        raise RuntimeError("A2a execution task shape differs")
    container = containers[0]
    env_rows = container.get("env", []) if isinstance(container, Mapping) else []
    if not isinstance(env_rows, list) or any(
        not isinstance(row, dict) or set(row) != {"name", "value"}
        for row in env_rows
    ):
        raise RuntimeError("A2a execution environment rows differ")
    env = {row.get("name"): row.get("value") for row in env_rows}
    if len(env) != len(env_rows) or env != expected["env"] or \
            container.get("image") != expected["image"] or \
            container.get("command") != expected["command"] or \
            container.get("args") != expected["args"] or \
            container.get("workingDir", "") != "" or \
            container.get("volumeMounts", []) != [] or \
            container.get("startupProbe") not in (None, {}) or \
            container.get("resources", {}).get("limits") != \
            expected["resources"] or task.get("volumes", []) != [] or \
            _nonnegative_int(
                task.get("maxRetries"), label="execution max retries",
            ) != 0 or type(task.get("timeoutSeconds")) is not str or \
            task.get("timeoutSeconds") != TIMEOUT_SECONDS or \
            task.get("serviceAccountName") != SERVICE_ACCOUNT:
        raise RuntimeError("A2a execution contract differs")


def _validate_execution(
    value: Mapping[str, Any], *, execution: str,
    manifest: Mapping[str, Any],
) -> None:
    _validate_execution_terminal(
        value, execution=execution, manifest=manifest,
        completed_status="True",
    )


def _validate_failed_execution(
    value: Mapping[str, Any], *, execution: str,
    manifest: Mapping[str, Any],
) -> None:
    _validate_execution_terminal(
        value, execution=execution, manifest=manifest,
        completed_status="False",
    )


LICENSE_KEYS: Final = frozenset({
    "uses_realized_outcomes", "actual_outcomes_queried",
    "candidate_or_lineup_scores_read", "single_stack_protocol_licensed",
    "single_stack_arm_licensed", "exact80_scoring_licensed",
    "prospective_shadow_licensed", "production_change_licensed",
})
JUDGMENT_KEYS: Final = frozenset({
    "version", "passes", "disposition", "conditions", "qb_wr_location",
    "qb_wr_equivalent_blocks", "multiplicity_ge3_equivalent_blocks",
    "aggregate_cell_guards", "mechanism_roles", "licenses",
    "blocks_are_independent_historical_replications", "blocks", "aggregate",
})
RESULT_EXTRA_KEYS: Final = frozenset({
    "run_id", "protocol_sha256", "code_sha", "analysis_image",
    "static_source_hashes", "mechanism_license", "control_reference",
    "source_lock", "source_artifacts", "block_mechanics",
    "coverage_accounting", "outcome_query",
    "outcome_query_issued_after_complete_source_preflight",
    "outcome_population",
})
RESULT_KEYS: Final = JUDGMENT_KEYS | LICENSE_KEYS | RESULT_EXTRA_KEYS


def _validate_result(
    value: object, *, manifest: Mapping[str, Any], root: Path = ROOT,
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != RESULT_KEYS:
        raise RuntimeError("A2a result field population differs")
    fixed = {
        "run_id": RUN_ID,
        "protocol_sha256": runner.PROTOCOL_SHA256,
        "code_sha": manifest["code"]["commit_sha"],
        "analysis_image": manifest["image"]["uri"],
        "uses_realized_outcomes": True,
        "actual_outcomes_queried": True,
        "candidate_or_lineup_scores_read": False,
        "single_stack_arm_licensed": False,
        "exact80_scoring_licensed": False,
        "prospective_shadow_licensed": False,
        "production_change_licensed": False,
        "outcome_query_issued_after_complete_source_preflight": True,
    }
    if any(value.get(key) != expected for key, expected in fixed.items()):
        raise RuntimeError("A2a result frozen identity/license differs")
    judged = decision.evaluate_remeasurement(
        value.get("blocks", {}), value.get("aggregate", {}),
    )
    for key in JUDGMENT_KEYS:
        if value.get(key) != judged[key]:
            raise RuntimeError(f"A2a result judgment differs at {key}")
    if any(value.get(key) != judged["licenses"][key] for key in LICENSE_KEYS):
        raise RuntimeError("A2a result top-level licenses differ")
    expected_sources = runner._validate_static_sources()
    if value.get("static_source_hashes") != expected_sources:
        raise RuntimeError("A2a result static sources differ")
    for source_name, digest in expected_sources.items():
        matching = [
            row["sha256"] for row in manifest["implementation"].values()
            if row["path"] == source_name
        ]
        if matching and matching != [digest]:
            raise RuntimeError("A2a result/manifest source binding differs")
    if value.get("mechanism_license") != {
        "uri": runner.A2A_RESULT_URI,
        "generation": runner.A2A_RESULT_GENERATION,
        "sha256": runner.A2A_RESULT_SHA256,
        "bytes": runner.A2A_RESULT_BYTES,
        "disposition": "a2a-scorefree-mechanism-passes",
        "historical_remeasurement_licensed": True,
    } or value.get("control_reference") != runner._validate_control_reference():
        raise RuntimeError("A2a result upstream reference differs")
    if value.get("source_lock") != {
        "uri": runner.a2a_source.SOURCE_LOCK_URI,
        "generation": runner.a2a_source.SOURCE_LOCK_GENERATION,
        "sha256": runner.a2a_source.SOURCE_LOCK_SHA256,
        "bytes": runner.a2a_source.SOURCE_LOCK_BYTES,
    }:
        raise RuntimeError("A2a result source-lock identity differs")
    source_lock = _load_json(
        root / IMPLEMENTATION_PATHS["source_lock"], label="source lock",
    )
    expected_artifacts = source_lock.get("artifact_receipts") \
        if isinstance(source_lock, Mapping) else None
    actual_artifacts = value.get("source_artifacts")
    if not isinstance(expected_artifacts, list) or \
            not isinstance(actual_artifacts, list) or \
            len(expected_artifacts) != 270 or len(actual_artifacts) != 270:
        raise RuntimeError("A2a result source-artifact population differs")
    for expected, observed in zip(expected_artifacts, actual_artifacts, strict=True):
        seed = int(expected["seed"])
        frozen = {
            "season": int(expected["season"]),
            "week": int(expected["week"]),
            "block": decision.REGISTERED_BLOCKS[seed],
            "panel_run_id": expected["panel_run_id"],
            "uri": expected["uri"],
            "generation": str(expected["generation"]),
            "sha256": expected["sha256"],
            "bytes": int(expected["bytes"]),
        }
        if observed != frozen:
            raise RuntimeError("A2a result source-artifact identity differs")
    mechanism = _load_json(
        root / IMPLEMENTATION_PATHS["mechanism_license"],
        label="mechanism license",
    )
    expected_mechanics = {
        block: mechanism["block_reports"][block]["mechanics"]
        for block in decision.REGISTERED_BLOCKS
    }
    if value.get("block_mechanics") != expected_mechanics:
        raise RuntimeError("A2a result mechanical receipts differ")
    coverage = value.get("coverage_accounting")
    if not isinstance(coverage, dict) or coverage != \
            decision.support_accounting(source_lock["catalog"]):
        raise RuntimeError("A2a result coverage accounting differs")
    for key, expected in runner.EXPECTED_ACCOUNTING.items():
        if coverage.get(key) != expected:
            raise RuntimeError("A2a result coverage counts differ")
    population = value.get("outcome_population")
    query = value.get("outcome_query")
    if population != {
        "slates": 54,
        "eligible_player_rows": 9_469,
        "missing_eligible_outcomes": 0,
        "duplicate_eligible_keys": 0,
    } or not isinstance(query, dict) or set(query) != {
        "job_id", "location", "created", "started", "ended",
        "total_bytes_processed", "query_sha256", "selected_fields",
    } or not isinstance(query.get("job_id"), str) or not query["job_id"] or \
            query.get("query_sha256") != _sha_bytes(
                runner.OUTCOME_SQL.encode()
            ) or query.get("selected_fields") != [
                "season", "week", "player_id", "actual",
            ] or query.get("location") != "US" or \
            type(query.get("total_bytes_processed")) is not int or \
            query["total_bytes_processed"] < 0:
        raise RuntimeError("A2a result outcome-query receipt differs")
    query_times = [
        datetime.fromisoformat(
            _utc_timestamp(
                query.get(key), label=f"outcome query {key}",
            ).replace("Z", "+00:00")
        )
        for key in ("created", "started", "ended")
    ]
    if query_times != sorted(query_times):
        raise RuntimeError("A2a result outcome-query timing differs")
    return value


def _result_inventory(client: storage.Client) -> dict[str, Any]:
    rows = _prefix_inventory(client)
    if len(rows) != 1 or rows[0]["uri"] != RESULT_URI or \
            re.fullmatch(r"[1-9][0-9]*", rows[0]["generation"]) is None or \
            rows[0]["metageneration"] != "1" or rows[0]["bytes"] <= 0:
        raise RuntimeError("A2a result prefix inventory differs")
    return rows[0]


def _validate_failure_result_inventory(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > 1:
        raise RuntimeError("A2a failed result-prefix inventory differs")
    if not value:
        return []
    row = value[0]
    if not isinstance(row, dict) or set(row) != {
        "uri", "generation", "metageneration", "bytes",
    } or row.get("uri") != RESULT_URI or re.fullmatch(
        r"[1-9][0-9]*", str(row.get("generation", ""))
    ) is None or row.get("metageneration") != "1" or \
            type(row.get("bytes")) is not int or row["bytes"] <= 0:
        raise RuntimeError("A2a failed result-prefix inventory differs")
    return [dict(row)]


def _failure_result_inventory(client: storage.Client) -> list[dict[str, Any]]:
    """Capture metadata only; a terminal-failure path never opens the body."""
    return _validate_failure_result_inventory(_prefix_inventory(client))


def _download_inventory_object(
    client: storage.Client, inventory: Mapping[str, Any],
) -> tuple[dict[str, Any], bytes]:
    bucket_name, object_name = _gcs_parts(RESULT_URI)
    generation = int(str(inventory["generation"]))
    blob = client.bucket(bucket_name).blob(object_name, generation=generation)
    blob.reload()
    if str(blob.generation) != str(inventory["generation"]) or \
            str(blob.metageneration) != str(inventory["metageneration"]) or \
            int(blob.size or 0) != int(inventory["bytes"]):
        raise RuntimeError("A2a result metadata changed after inventory")
    raw = blob.download_as_bytes(if_generation_match=generation)
    metadata = _blob_metadata(blob, uri=RESULT_URI, raw=raw)
    if any(metadata[key] != inventory[key] for key in (
        "uri", "generation", "metageneration", "bytes",
    )):
        raise RuntimeError("A2a result identity differs after generation-pinned read")
    return metadata, raw


def _harvest_local_files(out: Path) -> dict[str, Path]:
    harvest = out / "harvest"
    return {
        "execution": harvest / "execution.json",
        "object": harvest / "object-metadata.json",
        "report": harvest / "report.json",
    }


def _completion_bytes(
    *, report: Mapping[str, Any], object_metadata: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> bytes:
    completion_time = execution.get("status", {}).get("completionTime")
    return "".join((
        f"run_id={RUN_ID}\n",
        f"validated_execution_completion={completion_time}\n",
        "uses_realized_outcomes=true\n",
        "actual_outcomes_queried=true\n",
        "candidate_or_lineup_scores_read=false\n",
        f"disposition={report['disposition']}\n",
        f"result_generation={object_metadata['generation']}\n",
        f"result_sha256={object_metadata['sha256']}\n",
        "historical_outcome_lease_release_licensed=true\n",
        "historical_retry_licensed=false\n",
        "production_change_licensed=false\n",
    )).encode("utf-8")


def _finish_ledger_bytes(out: Path) -> bytes:
    files = _harvest_local_files(out)
    names = (
        "harvest/execution.json", "harvest/object-metadata.json",
        "harvest/report.json", "completion.txt",
    )
    paths = (
        files["execution"], files["object"], files["report"],
        out / "completion.txt",
    )
    return "".join(
        f"{_sha(path)}  {name}\n" for path, name in zip(paths, names, strict=True)
    ).encode("utf-8")


def _validate_completed_local(
    out: Path, *, manifest: Mapping[str, Any], execution_name: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    files = _harvest_local_files(out)
    execution = _load_json(files["execution"], label="retained execution")
    obj = _load_json(files["object"], label="retained result metadata")
    report_raw = files["report"].read_bytes()
    report = _strict_json_bytes(report_raw, label="retained result")
    if not isinstance(execution, dict) or not isinstance(obj, dict) or \
            not isinstance(report, dict):
        raise RuntimeError("A2a retained harvest schema differs")
    _validate_execution(execution, execution=execution_name, manifest=manifest)
    metadata = _metadata(obj, uri=RESULT_URI, label="retained result")
    if metadata["bytes"] != len(report_raw) or \
            metadata["sha256"] != _sha_bytes(report_raw) or \
            report_raw != _canonical_json(report):
        raise RuntimeError("A2a retained result content identity differs")
    _validate_result(report, manifest=manifest)
    completion = _completion_bytes(
        report=report, object_metadata=metadata, execution=execution,
    )
    _write_exclusive_or_equal(out / "completion.txt", completion)
    _write_exclusive_or_equal(out / "finish.sha256", _finish_ledger_bytes(out))
    _validate_hash_ledger(
        out / "finish.sha256", base=out,
        expected={
            "harvest/execution.json", "harvest/object-metadata.json",
            "harvest/report.json", "completion.txt",
        },
    )
    return execution, metadata, report


def finish(
    *, out: Path = DEFAULT_OUT,
    execution_loader: Callable[[str], dict[str, Any]] = _gcloud_execution,
    client: storage.Client | None = None,
) -> dict[str, Any]:
    """Strictly harvest the sole result after all body-blind gates pass."""
    manifest, manifest_receipt, lease, execution_name = _validate_launch_local(out)
    if (out / "finish.sha256").is_file():
        _, metadata, report = _validate_completed_local(
            out, manifest=manifest, execution_name=execution_name,
        )
        return {"report": report, "object": metadata, "already_complete": True}
    gcs = storage.Client(project=PROJECT) if client is None else client
    _load_live_manifest(manifest, manifest_receipt, client=gcs)
    _load_live_lease(gcs, lease, manifest=manifest)
    _load_live_launch_intent(
        out, manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease, client=gcs,
    )
    execution = execution_loader(execution_name)
    _validate_execution(execution, execution=execution_name, manifest=manifest)
    # This is the body firewall: inventory is validated only after strict
    # terminal success, and the report body is opened only after exact sole
    # object identity has been established.
    inventory = _result_inventory(gcs)
    metadata, raw = _download_inventory_object(gcs, inventory)
    report = _strict_json_bytes(raw, label="result")
    if not isinstance(report, dict) or raw != _canonical_json(report):
        raise RuntimeError("A2a result is not canonical JSON")
    _validate_result(report, manifest=manifest)
    pending = out / ".strict-harvest.pending"
    harvest = out / "harvest"
    if pending.exists() or harvest.exists():
        raise RuntimeError("A2a immutable harvest path already exists")
    pending.mkdir()
    _write_exclusive_or_equal(pending / "execution.json", _canonical_json(execution))
    _write_exclusive_or_equal(pending / "object-metadata.json", _canonical_json(metadata))
    _write_exclusive_or_equal(pending / "report.json", raw)
    pending.rename(harvest)
    execution, metadata, report = _validate_completed_local(
        out, manifest=manifest, execution_name=execution_name,
    )
    return {"report": report, "object": metadata, "already_complete": False}


def _release_intent(
    *, out: Path, manifest: Mapping[str, Any],
    manifest_receipt: Mapping[str, Any], lease: Mapping[str, Any],
    execution: Mapping[str, Any], result_object: Mapping[str, Any],
    report: Mapping[str, Any],
) -> dict[str, Any]:
    completion = out / "completion.txt"
    execution_path = _harvest_local_files(out)["execution"]
    return {
        "version": "a2a-production-law-dependence-lease-release-intent-v1",
        "run_id": RUN_ID,
        "manifest_object": {
            key: value for key, value in manifest_receipt["object"].items()
            if key != "create_only"
        },
        "lease_object": dict(lease["object"]),
        "execution": {
            "name": execution["metadata"]["name"],
            "sha256": _sha(execution_path),
            "completion_time": execution["status"]["completionTime"],
        },
        "result_object": dict(result_object),
        "completion_sha256": _sha(completion),
        "disposition": report["disposition"],
        "historical_outcome_lease_release_licensed": True,
        "release_action": (
            "delete-only-exact-active-generation-after-create-only-intent"
        ),
        "historical_retry_licensed": False,
        "production_change_licensed": False,
    }


def _delete_intended_lease(
    client: storage.Client, *, lease: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> bool:
    """Delete only the lease generation named by a durable release intent."""
    try:
        blob, _ = _load_live_lease(client, lease, manifest=manifest)
    except NotFound:
        # The registered generation is already absent.  A successor generation
        # is never selected by the generation-qualified lookup and is untouched.
        return False
    blob.delete(if_generation_match=int(lease["object"]["generation"]))
    return True


def _validate_release_local(
    out: Path, *, intent: Mapping[str, Any], lease: Mapping[str, Any],
) -> dict[str, Any]:
    release = _load_json(out / "lease-release.json", label="lease release")
    if not isinstance(release, dict) or set(release) != {
        "version", "run_id", "intent", "intent_object",
        "active_lease_generation", "active_lease_exact_generation_closed",
        "release_complete", "historical_retry_licensed",
        "production_change_licensed",
    }:
        raise RuntimeError("A2a local lease release fields differ")
    receipt = _intent_receipt(
        release["intent_object"], intent=intent, uri=RELEASE_INTENT_URI,
        version="a2a-production-law-dependence-release-intent-receipt-v1",
    )
    expected = {
        "version": "a2a-production-law-dependence-lease-release-v1",
        "run_id": RUN_ID,
        "intent": dict(intent),
        "intent_object": receipt,
        "active_lease_generation": lease["object"]["generation"],
        "active_lease_exact_generation_closed": True,
        "release_complete": True,
        "historical_retry_licensed": False,
        "production_change_licensed": False,
    }
    if release != expected:
        raise RuntimeError("A2a local lease release differs")
    _validate_hash_ledger(
        out / "lease-release.sha256", base=out,
        expected={"lease-release.json"},
    )
    return release


def close_lease(
    *, out: Path = DEFAULT_OUT, client: storage.Client | None = None,
) -> dict[str, Any]:
    """Idempotently intent-register and generation-delete the active lease."""
    manifest, manifest_receipt, lease, execution_name = _validate_launch_local(out)
    execution, result_object, report = _validate_completed_local(
        out, manifest=manifest, execution_name=execution_name,
    )
    intent = _release_intent(
        out=out, manifest=manifest, manifest_receipt=manifest_receipt,
        lease=lease, execution=execution, result_object=result_object,
        report=report,
    )
    if (out / "lease-release.sha256").is_file():
        release = _validate_release_local(out, intent=intent, lease=lease)
        return {**release, "active_lease_deleted_in_this_call": False}
    raw = _canonical_json(intent)
    gcs = storage.Client(project=PROJECT) if client is None else client
    obj = _upload_create_once_or_same(gcs, RELEASE_INTENT_URI, raw)
    receipt = {
        "version": "a2a-production-law-dependence-release-intent-receipt-v1",
        "intent_sha256": _sha_bytes(raw),
        "object": obj,
    }
    _intent_receipt(
        receipt, intent=intent, uri=RELEASE_INTENT_URI,
        version="a2a-production-law-dependence-release-intent-receipt-v1",
    )
    active_deleted = _delete_intended_lease(
        gcs, lease=lease, manifest=manifest,
    )
    release = {
        "version": "a2a-production-law-dependence-lease-release-v1",
        "run_id": RUN_ID,
        "intent": intent,
        "intent_object": receipt,
        "active_lease_generation": lease["object"]["generation"],
        "active_lease_exact_generation_closed": True,
        "release_complete": True,
        "historical_retry_licensed": False,
        "production_change_licensed": False,
    }
    _write_exclusive_or_equal(out / "lease-release.json", _canonical_json(release))
    _write_exclusive_or_equal(
        out / "lease-release.sha256",
        f"{_sha_bytes(_canonical_json(release))}  lease-release.json\n".encode(),
    )
    _validate_release_local(out, intent=intent, lease=lease)
    return {**release, "active_lease_deleted_in_this_call": active_deleted}


def _failed_release_intent(
    *, out: Path, manifest_receipt: Mapping[str, Any],
    lease: Mapping[str, Any], execution: Mapping[str, Any],
    result_prefix_inventory: object,
) -> dict[str, Any]:
    execution_path = out / "failed-execution.json"
    return {
        "version": (
            "a2a-production-law-dependence-failed-lease-release-intent-v1"
        ),
        "run_id": RUN_ID,
        "manifest_object": {
            key: value for key, value in manifest_receipt["object"].items()
            if key != "create_only"
        },
        "lease_object": dict(lease["object"]),
        "execution": {
            "name": execution["metadata"]["name"],
            "sha256": _sha(execution_path),
            "completion_time": execution["status"]["completionTime"],
        },
        "result_object": None,
        "result_prefix_inventory": _validate_failure_result_inventory(
            result_prefix_inventory,
        ),
        "result_body_read": False,
        "completion_sha256": None,
        "disposition": "closed-terminal-failed-no-retry",
        "possible_historical_outcome_access": True,
        "historical_outcome_lease_release_licensed": True,
        "release_action": (
            "delete-only-exact-active-generation-after-create-only-intent"
        ),
        "historical_retry_licensed": False,
        "production_change_licensed": False,
    }


def _validate_failed_local(
    out: Path, *, manifest: Mapping[str, Any],
    manifest_receipt: Mapping[str, Any], lease: Mapping[str, Any],
    execution_name: str,
) -> dict[str, Any]:
    execution_path = out / "failed-execution.json"
    execution_raw = execution_path.read_bytes()
    execution = _strict_json_bytes(
        execution_raw, label="failed execution metadata",
    )
    if not isinstance(execution, dict) or execution_raw != \
            _canonical_json(execution):
        raise RuntimeError("A2a failed execution metadata is not canonical")
    _validate_failed_execution(
        execution, execution=execution_name, manifest=manifest,
    )
    closure = _load_json(
        out / "failure-closure.json", label="failure closure",
    )
    if not isinstance(closure, dict) or set(closure) != {
        "version", "run_id", "intent", "intent_object",
        "active_lease_generation", "active_lease_exact_generation_closed",
        "disposition", "possible_historical_outcome_access",
        "historical_retry_licensed", "production_change_licensed",
    }:
        raise RuntimeError("A2a failure closure fields differ")
    candidate_intent = closure.get("intent")
    if not isinstance(candidate_intent, Mapping):
        raise RuntimeError("A2a failure release intent differs")
    intent = _failed_release_intent(
        out=out, manifest_receipt=manifest_receipt, lease=lease,
        execution=execution,
        result_prefix_inventory=candidate_intent.get(
            "result_prefix_inventory",
        ),
    )
    receipt = _intent_receipt(
        closure["intent_object"], intent=intent, uri=RELEASE_INTENT_URI,
        version=(
            "a2a-production-law-dependence-failed-release-intent-receipt-v1"
        ),
    )
    expected = {
        "version": "a2a-production-law-dependence-failure-closure-v1",
        "run_id": RUN_ID,
        "intent": intent,
        "intent_object": receipt,
        "active_lease_generation": lease["object"]["generation"],
        "active_lease_exact_generation_closed": True,
        "disposition": "closed-terminal-failed-no-retry",
        "possible_historical_outcome_access": True,
        "historical_retry_licensed": False,
        "production_change_licensed": False,
    }
    if closure != expected:
        raise RuntimeError("A2a failure closure differs")
    _validate_hash_ledger(
        out / "failure-closure.sha256", base=out,
        expected={"failed-execution.json", "failure-closure.json"},
    )
    return closure


def close_failed_execution(
    *, out: Path = DEFAULT_OUT, client: storage.Client | None = None,
) -> dict[str, Any]:
    """Durably close one strict terminal failure without reading a result."""
    manifest, manifest_receipt, lease, execution_name = _validate_launch_local(out)
    if (out / "failure-closure.sha256").is_file():
        return _validate_failed_local(
            out, manifest=manifest, manifest_receipt=manifest_receipt,
            lease=lease, execution_name=execution_name,
        )
    execution_path = out / "failed-execution.json"
    execution_raw = execution_path.read_bytes()
    execution = _strict_json_bytes(
        execution_raw, label="failed execution metadata",
    )
    if not isinstance(execution, dict) or execution_raw != \
            _canonical_json(execution):
        raise RuntimeError("A2a failed execution metadata is not canonical")
    _validate_failed_execution(
        execution, execution=execution_name, manifest=manifest,
    )
    gcs = storage.Client(project=PROJECT) if client is None else client
    _load_live_manifest(manifest, manifest_receipt, client=gcs)
    _load_live_launch_intent(
        out, manifest=manifest, manifest_receipt=manifest_receipt,
        lease_receipt=lease, client=gcs,
    )
    failure_inventory = _failure_result_inventory(gcs)
    intent = _failed_release_intent(
        out=out, manifest_receipt=manifest_receipt, lease=lease,
        execution=execution, result_prefix_inventory=failure_inventory,
    )
    raw = _canonical_json(intent)
    obj = _upload_create_once_or_same(gcs, RELEASE_INTENT_URI, raw)
    receipt = {
        "version": (
            "a2a-production-law-dependence-failed-release-intent-receipt-v1"
        ),
        "intent_sha256": _sha_bytes(raw),
        "object": obj,
    }
    _intent_receipt(
        receipt, intent=intent, uri=RELEASE_INTENT_URI,
        version=(
            "a2a-production-law-dependence-failed-release-intent-receipt-v1"
        ),
    )
    _delete_intended_lease(gcs, lease=lease, manifest=manifest)
    closure = {
        "version": "a2a-production-law-dependence-failure-closure-v1",
        "run_id": RUN_ID,
        "intent": intent,
        "intent_object": receipt,
        "active_lease_generation": lease["object"]["generation"],
        "active_lease_exact_generation_closed": True,
        "disposition": "closed-terminal-failed-no-retry",
        "possible_historical_outcome_access": True,
        "historical_retry_licensed": False,
        "production_change_licensed": False,
    }
    _write_exclusive_or_equal(
        out / "failure-closure.json", _canonical_json(closure),
    )
    ledger = (
        f"{_sha(execution_path)}  failed-execution.json\n"
        f"{_sha(out / 'failure-closure.json')}  failure-closure.json\n"
    ).encode("utf-8")
    _write_exclusive_or_equal(out / "failure-closure.sha256", ledger)
    return _validate_failed_local(
        out, manifest=manifest, manifest_receipt=manifest_receipt,
        lease=lease, execution_name=execution_name,
    )


def _verify_pushed_manifest(
    out: Path, *, root: Path = ROOT, remote_ref: str = "origin/main",
) -> None:
    relative = (out / "manifest.json").resolve().relative_to(root.resolve())
    committed = subprocess.run(
        ["git", "-C", str(root), "show", f"{remote_ref}:{relative}"],
        check=True, capture_output=True,
    ).stdout
    if committed != (out / "manifest.json").read_bytes():
        raise RuntimeError("A2a launch manifest is not byte-identical in origin/main")


def _write_manifest_from_args(args: argparse.Namespace) -> None:
    build = _load_json(args.build_metadata, label="build metadata")
    before = _load_json(args.job_before, label="job before")
    after = _load_json(args.job_after, label="job after")
    executions_before = _load_json(
        args.executions_before, label="executions before",
    )
    executions_after = _load_json(
        args.executions_after, label="executions after",
    )
    schedulers_before = _load_json(
        args.schedulers_before, label="schedulers before",
    )
    schedulers_after = _load_json(
        args.schedulers_after, label="schedulers after",
    )
    prefix_before = _load_json(args.prefix_before, label="prefix before")
    prefix_after = _load_json(args.prefix_after, label="prefix after")
    lease_before = _load_json(args.lease_before, label="lease before")
    lease_after = _load_json(args.lease_after, label="lease after")
    manifest = _build_launch_manifest(
        code_sha=args.code_sha, image=args.image, build_id=args.build_id,
        build_metadata=build, job_before=before, job_after=after,
        executions_before=executions_before, executions_after=executions_after,
        schedulers_before=schedulers_before, schedulers_after=schedulers_after,
        prefix_before=prefix_before, prefix_after=prefix_after,
        lease_before=lease_before, lease_after=lease_after,
        frozen_at=datetime.now(timezone.utc).isoformat(),
    )
    _write_exclusive_or_equal(args.output, _canonical_json(manifest))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    canonical = sub.add_parser("canonicalize-external-json")
    canonical.add_argument("--raw", type=Path, required=True)
    canonical.add_argument("--output", type=Path, required=True)

    staging = sub.add_parser("validate-smoke-staging")
    staging.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    staging.add_argument("--code-sha", required=True)

    prepare = sub.add_parser("prepare-manifest")
    prepare.add_argument("--code-sha", required=True)
    prepare.add_argument("--image", required=True)
    prepare.add_argument("--build-id", required=True)
    for name in (
        "build-metadata", "job-before", "job-after", "executions-before",
        "executions-after", "schedulers-before", "schedulers-after",
        "prefix-before", "prefix-after", "lease-before", "lease-after",
    ):
        prepare.add_argument(f"--{name}", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)

    preupdate = sub.add_parser("validate-prepare-inputs")
    preupdate.add_argument("--code-sha", required=True)
    preupdate.add_argument("--image", required=True)
    preupdate.add_argument("--build-id", required=True)
    preupdate.add_argument("--build-metadata", type=Path, required=True)
    preupdate.add_argument("--job-before", type=Path, required=True)
    preupdate.add_argument("--executions-before", type=Path, required=True)
    preupdate.add_argument("--schedulers-before", type=Path, required=True)

    publish = sub.add_parser("publish-manifest")
    publish.add_argument("--manifest", type=Path, required=True)
    publish.add_argument("--receipt", type=Path, required=True)

    prepared = sub.add_parser("validate-prepared")
    prepared.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    prepared.add_argument("--code-sha", required=True)
    prepared.add_argument("--image", required=True)
    prepared.add_argument("--build-id", required=True)

    empty = sub.add_parser("check-empty-prefix")
    empty.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)

    sub.add_parser("check-lease-absent")

    capture_prefix = sub.add_parser("capture-empty-prefix")
    capture_prefix.add_argument("--output", type=Path, required=True)
    capture_lease = sub.add_parser("capture-lease-absence")
    capture_lease.add_argument("--output", type=Path, required=True)

    pushed = sub.add_parser("verify-pushed-manifest")
    pushed.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    pushed.add_argument("--remote-ref", default="origin/main")

    ready = sub.add_parser("validate-launch-ready")
    ready.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    ready.add_argument("--job-current", type=Path, required=True)
    ready.add_argument("--executions", type=Path, required=True)
    ready.add_argument("--schedulers", type=Path, required=True)
    ready.add_argument("--require-intent", action="store_true")

    recover = sub.add_parser("recover-lease")
    recover.add_argument("--manifest", type=Path, required=True)
    recover.add_argument("--receipt", type=Path, required=True)

    intent = sub.add_parser("publish-launch-intent")
    intent.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)

    harvest = sub.add_parser("finish")
    harvest.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)

    close = sub.add_parser("close-lease")
    close.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    failed = sub.add_parser("close-failed-execution")
    failed.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "canonicalize-external-json":
        _canonicalize_external_json(args.raw, args.output)
    elif args.command == "validate-smoke-staging":
        _validate_smoke_staging(args.output_dir, code_sha=args.code_sha)
        print("A2A_REMEASUREMENT_SMOKE_STAGING_VALID")
    elif args.command == "validate-prepare-inputs":
        _validate_prepare_inputs(
            code_sha=args.code_sha, image=args.image, build_id=args.build_id,
            build_metadata=_load_json(
                args.build_metadata, label="build metadata",
            ),
            job_before=_load_json(args.job_before, label="job before"),
            executions_before=_load_json(
                args.executions_before, label="executions before",
            ),
            schedulers_before=_load_json(
                args.schedulers_before, label="schedulers before",
            ),
        )
        print("A2A_REMEASUREMENT_PREPARE_INPUTS_VALID")
    elif args.command == "prepare-manifest":
        _write_manifest_from_args(args)
    elif args.command == "publish-manifest":
        value = _publish_manifest(args.manifest, args.receipt)
        print(json.dumps(value, sort_keys=True))
    elif args.command == "validate-prepared":
        manifest, _ = _validate_prepared_local(args.output_dir)
        if manifest["code"]["commit_sha"] != args.code_sha or \
                manifest["image"]["uri"] != args.image or \
                manifest["build"]["id"] != args.build_id:
            raise RuntimeError("A2a watcher/prepared identity differs")
        print("A2A_REMEASUREMENT_PREPARED_VALID")
    elif args.command == "check-empty-prefix":
        _require_empty_prefix(storage.Client(project=PROJECT))
        print("A2A_REMEASUREMENT_RESULT_PREFIX_EMPTY")
    elif args.command == "check-lease-absent":
        _require_lease_absent(storage.Client(project=PROJECT))
        print("A2A_REMEASUREMENT_OUTCOME_LEASE_ABSENT")
    elif args.command == "capture-empty-prefix":
        _capture_absence(kind="result-prefix", output=args.output)
        print("A2A_REMEASUREMENT_RESULT_PREFIX_EMPTY")
    elif args.command == "capture-lease-absence":
        _capture_absence(kind="historical-outcome-lease", output=args.output)
        print("A2A_REMEASUREMENT_OUTCOME_LEASE_ABSENT")
    elif args.command == "verify-pushed-manifest":
        _verify_pushed_manifest(args.output_dir, remote_ref=args.remote_ref)
        print("A2A_REMEASUREMENT_MANIFEST_PUSHED")
    elif args.command == "validate-launch-ready":
        _validate_launch_ready(
            out=args.output_dir,
            job_current=_load_json(args.job_current, label="current job"),
            executions=_load_json(args.executions, label="current executions"),
            schedulers=_load_json(args.schedulers, label="current schedulers"),
            require_intent=args.require_intent,
        )
        print("A2A_REMEASUREMENT_LAUNCH_READY")
    elif args.command == "recover-lease":
        value = _recover_live_lease(
            manifest_path=args.manifest, receipt_path=args.receipt,
        )
        print("A2A_REMEASUREMENT_LEASE_RECOVERED " + json.dumps(
            value["object"], sort_keys=True,
        ))
    elif args.command == "publish-launch-intent":
        value = _publish_launch_intent(args.output_dir)
        print("A2A_REMEASUREMENT_LAUNCH_INTENT " + json.dumps(
            value["object"], sort_keys=True,
        ))
    elif args.command == "finish":
        value = finish(out=args.output_dir)
        print("A2A_REMEASUREMENT_HARVESTED " + value["report"]["disposition"])
    elif args.command == "close-lease":
        value = close_lease(out=args.output_dir)
        print("A2A_REMEASUREMENT_LEASE_CLOSED " + json.dumps({
            "intent_object": value["intent_object"],
            "active_lease_deleted_in_this_call": value[
                "active_lease_deleted_in_this_call"
            ],
        }, sort_keys=True))
    else:
        value = close_failed_execution(out=args.output_dir)
        print("A2A_REMEASUREMENT_TERMINAL_FAILURE_CLOSED " + value[
            "disposition"
        ])


if __name__ == "__main__":
    main()
