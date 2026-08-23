#!/usr/bin/env python3
"""Strict reuse-only transport for the conditional A7 score-free transfer.

This module adds no science.  It owns create-only job/phase claims, exact
Cloud Run metadata validation, terminal-first generation-pinned harvest, and
the smoke -> support -> freeze -> full chain.  Every public operation that can
construct a cloud client first revalidates the exact positive final A7 closure.
There is no outcome query, lease, scheduler, job creation/deletion, relaunch,
or retry path here.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Final

from google.cloud import storage


ROOT: Final = Path(__file__).resolve().parents[1]
for entry in (ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from nfl_dfs.research import a7_production_law_transfer as science  # noqa: E402

import finish_a7_select_ladder as a7_transport  # noqa: E402
import freeze_a7_production_law_transfer as freezer  # noqa: E402
import run_a7_production_law_transfer as runner  # noqa: E402


PROJECT: Final = runner.PROJECT
REGION: Final = "us-central1"
JOB: Final = "atlas-minimal-c-s2023-w1-v1"
SERVICE_ACCOUNT: Final = "817589974517-compute@developer.gserviceaccount.com"
CPU: Final = "4"
MEMORY: Final = "16Gi"
TIMEOUT_SECONDS: Final = "7200"
RUN_ID: Final = runner.RUN_ID
PROTOCOL_ID: Final = science.PROTOCOL_ID
PREFIX: Final = runner.OUTPUT_PREFIX
TRANSPORT_PREFIX: Final = f"{PREFIX}/transport"
JOB_CLAIM_URI: Final = f"{TRANSPORT_PREFIX}/job-claim.json"
DEPLOYMENT_URI: Final = f"{TRANSPORT_PREFIX}/deployment.json"
FREEZE_RECEIPT_URI: Final = f"{TRANSPORT_PREFIX}/freeze-receipt.json"
PHASES: Final = ("smoke", "support", "full")
PHASE_MODE: Final = {
    "smoke": "real-artifact-smoke",
    "support": "support-census",
    "full": "full",
}
PHASE_OUTPUT: Final = {
    "smoke": runner.SMOKE_OUTPUT_URI,
    "support": runner.SUPPORT_OUTPUT_URI,
    "full": runner.FULL_OUTPUT_URI,
}
DEFAULT_OUT: Final = (
    ROOT / "reports/a7-production-law-selector-transfer-runs" / RUN_ID
)
SCRIPT_PATH: Final = "scripts/run_a7_production_law_transfer.py"

HEX40 = re.compile(r"[0-9a-f]{40}")
HEX64 = re.compile(r"[0-9a-f]{64}")
GENERATION = re.compile(r"[1-9][0-9]*")
IMAGE = re.compile(
    r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
    r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}"
)


class TransferTransportError(RuntimeError):
    """A fail-closed transfer transport boundary was not satisfied."""


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _strict_json(raw: bytes, *, label: str) -> Any:
    def reject(value: str) -> None:
        raise TransferTransportError(f"{label} contains non-finite JSON: {value}")

    def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise TransferTransportError(f"{label} repeats key {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw, parse_constant=reject, object_pairs_hook=strict_object,
        )
    except TransferTransportError:
        raise
    except Exception as exc:
        raise TransferTransportError(f"{label} is not strict JSON") from exc


def _load(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise TransferTransportError(f"{label} is absent: {path}")
    raw = path.read_bytes()
    value = _strict_json(raw, label=label)
    if not isinstance(value, dict) or raw != _canonical_json(value):
        raise TransferTransportError(f"{label} is not canonical JSON")
    return value


def _write_or_validate(path: Path, raw: bytes, *, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise TransferTransportError(f"existing {label} differs")
        return
    with path.open("xb") as handle:
        handle.write(raw)


def _sha_file(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _timestamp(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise TransferTransportError(f"{label} is absent")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TransferTransportError(f"{label} differs") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TransferTransportError(f"{label} lacks timezone")
    return value


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _object_identity(
    value: object, *, uri: str, create_only: bool | None = None,
) -> dict[str, Any]:
    fields = {"uri", "generation", "metageneration", "bytes", "sha256"}
    if create_only is not None:
        fields.add("create_only")
    if not isinstance(value, dict) or set(value) != fields or value.get(
        "uri"
    ) != uri or GENERATION.fullmatch(
        str(value.get("generation", ""))
    ) is None or str(value.get("metageneration", "")) != "1" or type(
        value.get("bytes")
    ) is not int or int(value["bytes"]) <= 0 or HEX64.fullmatch(
        str(value.get("sha256", ""))
    ) is None or (
        create_only is not None and value.get("create_only") is not create_only
    ):
        raise TransferTransportError(f"immutable object identity differs: {uri}")
    return dict(value)


def _metadata_identity(
    metadata: Mapping[str, Any], *, uri: str, raw: bytes,
) -> dict[str, Any]:
    value = {
        "uri": uri,
        "generation": str(metadata.get("generation", "")),
        "metageneration": str(metadata.get("metageneration", "")),
        "bytes": len(raw),
        "sha256": sha256(raw).hexdigest(),
    }
    return _object_identity(value, uri=uri)


def _reader() -> a7_transport._StorageReader:
    # Callers must validate the predecessor before reaching this constructor.
    return a7_transport._StorageReader()


def _load_pinned(
    reader: a7_transport._StorageReader,
    identity: Mapping[str, Any],
    *,
    uri: str,
    label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = _object_identity(dict(identity), uri=uri)
    metadata, raw = reader.load(uri, expected["generation"])
    observed = _metadata_identity(metadata, uri=uri, raw=raw)
    if observed != expected:
        raise TransferTransportError(f"{label} changed after generation pin")
    value = _strict_json(raw, label=label)
    if not isinstance(value, dict) or raw != _canonical_json(value):
        raise TransferTransportError(f"{label} is not canonical JSON")
    return value, observed


def _publish_recoverable(
    reader: a7_transport._StorageReader,
    *,
    uri: str,
    make_body: Callable[[], dict[str, Any]],
    validate: Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    inventory = reader.inventory(uri)
    if inventory:
        if set(inventory) != {uri}:
            raise TransferTransportError("create-only object inventory differs")
        generation = str(inventory[uri].get("generation", ""))
        metadata, raw = reader.load(uri, generation)
        body = _strict_json(raw, label=uri)
        if not isinstance(body, dict) or raw != _canonical_json(body):
            raise TransferTransportError("existing create-only body differs")
        body = validate(body)
    else:
        body = validate(make_body())
        raw = _canonical_json(body)
        metadata, downloaded = reader.create_or_validate(uri, raw)
        if downloaded != raw:
            raise TransferTransportError("create-only publication changed")
    identity = _metadata_identity(metadata, uri=uri, raw=_canonical_json(body))
    return body, {**identity, "create_only": True}


def _validate_predecessor() -> dict[str, Any]:
    try:
        return runner.validate_a7_positive_license()
    except Exception as exc:
        raise TransferTransportError(
            "exact final A7 positive predecessor is required"
        ) from exc


def _phase_uri(phase: str, kind: str) -> str:
    if phase not in PHASES or kind not in {
        "intent", "prepared", "launch-claim", "execution-claim", "terminal",
        "failure",
    }:
        raise TransferTransportError("transport phase/kind differs")
    return f"{TRANSPORT_PREFIX}/{phase}-{kind}.json"


def _phase_path(out: Path, phase: str, name: str) -> Path:
    if phase not in PHASES:
        raise TransferTransportError("transport phase differs")
    return out / phase / name


def _job_parts(value: object) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict):
        raise TransferTransportError("Cloud Run job metadata differs")
    metadata = value.get("metadata")
    outer = value.get("spec", {}).get("template", {}).get("spec")
    task = outer.get("template", {}).get("spec") if isinstance(outer, dict) else None
    if not isinstance(metadata, dict) or not isinstance(outer, dict) or not isinstance(
        task, dict,
    ):
        raise TransferTransportError("Cloud Run job schema differs")
    return metadata, outer, task


def _job_spec_sha256(value: Mapping[str, Any]) -> str:
    spec = value.get("spec")
    if not isinstance(spec, dict) or not spec:
        raise TransferTransportError("Cloud Run job spec is absent")
    return sha256(_canonical_json(spec)).hexdigest()


def _job_identity(
    value: object, *, uid: str | None = None,
) -> dict[str, str]:
    metadata, _, _ = _job_parts(value)
    generation = str(metadata.get("generation", ""))
    actual_uid = str(metadata.get("uid", ""))
    if metadata.get("name") != JOB or not actual_uid or GENERATION.fullmatch(
        generation
    ) is None or (uid is not None and actual_uid != uid):
        raise TransferTransportError("reused job identity differs")
    return {
        "name": JOB,
        "uid": actual_uid,
        "generation": generation,
        "spec_sha256": _job_spec_sha256(value),
    }


def _require_idle(value: object) -> None:
    if not isinstance(value, list):
        raise TransferTransportError("reused-job execution census differs")
    for row in value:
        status = row.get("status") if isinstance(row, dict) else None
        conditions = status.get("conditions", []) if isinstance(status, dict) else []
        completed = [
            item for item in conditions
            if isinstance(item, dict) and item.get("type") == "Completed"
        ]
        if len(completed) != 1 or completed[0].get("status") not in {
            "True", "False",
        }:
            raise TransferTransportError("reused job is not idle")


def _require_unscheduled(value: object) -> None:
    if not isinstance(value, list):
        raise TransferTransportError("scheduler inventory differs")
    needle = f"/jobs/{JOB}:run"
    if any(
        needle in json.dumps(row, sort_keys=True, separators=(",", ":"))
        for row in value
    ):
        raise TransferTransportError("reused job has a scheduler target")


def _env_rows(value: object) -> dict[str, str]:
    if not isinstance(value, list) or any(
        not isinstance(row, dict) or set(row) != {"name", "value"}
        or not isinstance(row["name"], str) or not isinstance(row["value"], str)
        for row in value
    ):
        raise TransferTransportError("job environment differs")
    result = {row["name"]: row["value"] for row in value}
    if len(result) != len(value):
        raise TransferTransportError("job environment repeats a name")
    return result


def registered_contract(
    *,
    phase: str,
    code_sha: str,
    image: str,
    prerequisites: Mapping[str, Any],
) -> dict[str, Any]:
    if phase not in PHASES or HEX40.fullmatch(code_sha) is None or IMAGE.fullmatch(
        image
    ) is None:
        raise TransferTransportError("execution identity differs")
    args = [
        SCRIPT_PATH, "run", "--mode", PHASE_MODE[phase],
        "--output-uri", PHASE_OUTPUT[phase],
    ]
    if phase == "smoke":
        if prerequisites:
            raise TransferTransportError("smoke prerequisites differ")
    elif phase == "support":
        if set(prerequisites) != {"query_sha256", "smoke"}:
            raise TransferTransportError("support prerequisites differ")
        query = prerequisites["query_sha256"]
        smoke = _object_identity(
            prerequisites["smoke"], uri=runner.SMOKE_OUTPUT_URI,
        )
        args.extend([
            "--expected-candidate-query-sha256", query["candidates"],
            "--expected-player-query-sha256", query["players"],
            "--smoke-generation", smoke["generation"],
            "--smoke-sha256", smoke["sha256"],
            "--smoke-bytes", str(smoke["bytes"]),
        ])
    else:
        if set(prerequisites) != {"query_sha256", "freeze"}:
            raise TransferTransportError("full prerequisites differ")
        query = prerequisites["query_sha256"]
        freeze = _object_identity(
            prerequisites["freeze"], uri=runner.FREEZE_MANIFEST_URI,
        )
        args.extend([
            "--expected-candidate-query-sha256", query["candidates"],
            "--expected-player-query-sha256", query["players"],
            "--freeze-generation", freeze["generation"],
            "--freeze-sha256", freeze["sha256"],
            "--freeze-bytes", str(freeze["bytes"]),
        ])
    if not isinstance(prerequisites.get("query_sha256", {}), Mapping):
        raise TransferTransportError("query hash prerequisites differ")
    if phase != "smoke" and any(
        HEX64.fullmatch(str(prerequisites["query_sha256"].get(key, ""))) is None
        for key in ("candidates", "players")
    ):
        raise TransferTransportError("query hash prerequisites differ")
    return {
        "image": image,
        "command": ["python"],
        "args": args,
        "env": {"CODE_SHA": code_sha, "ANALYSIS_IMAGE": image},
        "tasks": 1,
        "parallelism": 1,
        "resources": {"cpu": CPU, "memory": MEMORY},
        "max_retries": 0,
        "timeout_seconds": TIMEOUT_SECONDS,
        "service_account": SERVICE_ACCOUNT,
        "working_dir": "",
        "volume_mounts": [],
        "volumes": [],
        "startup_probe": None,
        "secret_environment": False,
    }


def _validate_job_contract(
    value: object, *, contract: Mapping[str, Any], uid: str,
) -> dict[str, str]:
    identity = _job_identity(value, uid=uid)
    _, outer, task = _job_parts(value)
    containers = task.get("containers")
    if not isinstance(containers, list) or len(containers) != 1 or not isinstance(
        containers[0], dict,
    ):
        raise TransferTransportError("job container population differs")
    container = containers[0]
    if outer.get("taskCount") != 1 or outer.get("parallelism") != 1 or \
            container.get("image") != contract["image"] or container.get(
                "command"
            ) != contract["command"] or container.get("args") != contract[
                "args"
            ] or _env_rows(container.get("env", [])) != contract["env"] or \
            container.get("resources", {}).get("limits") != contract[
                "resources"
            ] or container.get("workingDir", "") != "" or container.get(
                "volumeMounts", []
            ) != [] or container.get("startupProbe") not in (None, {}) or \
            task.get("maxRetries") != 0 or str(task.get("timeoutSeconds")) != (
                TIMEOUT_SECONDS
            ) or task.get("serviceAccountName") != SERVICE_ACCOUNT or task.get(
                "volumes", []
            ) != []:
        raise TransferTransportError("job executable contract differs")
    return identity


def inert_contract(*, code_sha: str, image: str) -> dict[str, Any]:
    if HEX40.fullmatch(code_sha) is None or IMAGE.fullmatch(image) is None:
        raise TransferTransportError("inert execution identity differs")
    return {
        "image": image,
        "command": ["python"],
        "args": [SCRIPT_PATH, "--help"],
        "env": {"CODE_SHA": code_sha, "ANALYSIS_IMAGE": image},
        "tasks": 1,
        "parallelism": 1,
        "resources": {"cpu": CPU, "memory": MEMORY},
        "max_retries": 0,
        "timeout_seconds": TIMEOUT_SECONDS,
        "service_account": SERVICE_ACCOUNT,
        "working_dir": "",
        "volume_mounts": [],
        "volumes": [],
        "startup_probe": None,
        "secret_environment": False,
    }


def _verify_predecessor_committed(code_sha: str) -> None:
    if HEX40.fullmatch(code_sha) is None:
        raise TransferTransportError("source commit differs")
    relative_root = runner.A7_OUT.relative_to(ROOT)
    for name in ("report.json", "completion.txt", "lease-release.txt", "finish.sha256"):
        local = runner.A7_OUT / name
        if local.is_symlink() or not local.is_file():
            raise TransferTransportError("committed predecessor evidence is absent")
        try:
            committed = subprocess.run(
                ["git", "-C", str(ROOT), "show", f"{code_sha}:{relative_root / name}"],
                check=True, capture_output=True,
            ).stdout
        except subprocess.CalledProcessError as exc:
            raise TransferTransportError(
                "source commit lacks predecessor evidence"
            ) from exc
        if committed != local.read_bytes():
            raise TransferTransportError("predecessor evidence differs from commit")


def _load_wrapper(
    path: Path,
    *,
    label: str,
    body_key: str,
    uri: str,
    validate_body: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    wrapper = _load(path, label=label)
    if set(wrapper) != {body_key, "object"}:
        raise TransferTransportError(f"{label} wrapper differs")
    body = validate_body(wrapper[body_key])
    obj = _object_identity(wrapper["object"], uri=uri, create_only=True)
    raw = _canonical_json(body)
    if obj["sha256"] != sha256(raw).hexdigest() or obj["bytes"] != len(raw):
        raise TransferTransportError(f"{label} object/body differs")
    return {body_key: body, "object": obj}


def _write_wrapper(
    path: Path,
    *,
    body_key: str,
    body: Mapping[str, Any],
    obj: Mapping[str, Any],
    label: str,
) -> dict[str, Any]:
    wrapper = {body_key: dict(body), "object": dict(obj)}
    _write_or_validate(path, _canonical_json(wrapper), label=label)
    return wrapper


def _validate_claim_body(value: object) -> dict[str, Any]:
    required = {
        "version", "run_id", "protocol_id", "protocol_sha256", "code_sha",
        "image", "build_id", "build_metadata_sha256", "predecessor_license",
        "job_before", "inert_contract", "phase_order", "output_uris",
        "claimed_at", "uses_realized_outcomes", "actual_score_query_executed",
        "historical_outcome_lease_acquired", "job_create_licensed",
        "job_delete_licensed", "scheduler_licensed", "retry_licensed",
        "licenses",
    }
    if not isinstance(value, dict) or set(value) != required or value.get(
        "version"
    ) != "a7-production-law-transfer-job-claim-v1" or value.get(
        "run_id"
    ) != RUN_ID or value.get("protocol_id") != PROTOCOL_ID or value.get(
        "protocol_sha256"
    ) != runner.PROTOCOL_SHA256 or HEX40.fullmatch(
        str(value.get("code_sha", ""))
    ) is None or IMAGE.fullmatch(str(value.get("image", ""))) is None or not isinstance(
        value.get("build_id"), str,
    ) or not value["build_id"] or HEX64.fullmatch(
        str(value.get("build_metadata_sha256", ""))
    ) is None or value.get("phase_order") != list(PHASES) or value.get(
        "output_uris"
    ) != PHASE_OUTPUT or value.get("uses_realized_outcomes") is not False or value.get(
        "actual_score_query_executed"
    ) is not False or value.get("historical_outcome_lease_acquired") is not False or any(
        value.get(key) is not False
        for key in (
            "job_create_licensed", "job_delete_licensed", "scheduler_licensed",
            "retry_licensed",
        )
    ) or value.get("licenses") != science.licenses():
        raise TransferTransportError("job claim body differs")
    _timestamp(value.get("claimed_at"), label="job claim time")
    predecessor = value.get("predecessor_license")
    if not isinstance(predecessor, dict) or predecessor.get(
        "production_law_scorefree_transfer_licensed"
    ) is not True or predecessor.get("prospective_shadow_licensed") is not False:
        raise TransferTransportError("job claim predecessor differs")
    job = value.get("job_before")
    if not isinstance(job, dict) or set(job) != {
        "name", "uid", "generation", "spec_sha256",
    } or job.get("name") != JOB or not job.get("uid") or GENERATION.fullmatch(
        str(job.get("generation", ""))
    ) is None or HEX64.fullmatch(str(job.get("spec_sha256", ""))) is None:
        raise TransferTransportError("job claim reused-job identity differs")
    if value.get("inert_contract") != inert_contract(
        code_sha=value["code_sha"], image=value["image"],
    ):
        raise TransferTransportError("job claim inert contract differs")
    return value


def _load_live_wrapper(
    reader: a7_transport._StorageReader,
    wrapper: Mapping[str, Any],
    *,
    body_key: str,
    uri: str,
    label: str,
    validate_body: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    obj = _object_identity(wrapper.get("object"), uri=uri, create_only=True)
    body, observed = _load_pinned(
        reader, {key: obj[key] for key in (
            "uri", "generation", "metageneration", "bytes", "sha256"
        )}, uri=uri, label=label,
    )
    body = validate_body(body)
    if body != wrapper.get(body_key) or observed != {
        key: obj[key] for key in observed
    }:
        raise TransferTransportError(f"live {label} differs")
    return {body_key: body, "object": obj}


def create_job_claim(
    *,
    code_sha: str,
    image: str,
    build_id: str,
    build_metadata: Mapping[str, Any],
    job_before: Mapping[str, Any],
    executions_before: object,
    schedulers_before: object,
    receipt_path: Path,
    reader: a7_transport._StorageReader | None = None,
    build_validator: Callable[..., None] | None = None,
    commit_validator: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    predecessor = _validate_predecessor()
    if HEX40.fullmatch(code_sha) is None or IMAGE.fullmatch(image) is None:
        raise TransferTransportError("job claim execution identity differs")
    (commit_validator or _verify_predecessor_committed)(code_sha)
    validator = build_validator or a7_transport._validate_build_metadata
    try:
        validator(
            dict(build_metadata), build_id=build_id, image=image,
            code_sha=code_sha,
        )
    except Exception as exc:
        raise TransferTransportError("exact build metadata differs") from exc
    job = _job_identity(job_before)
    _require_idle(executions_before)
    _require_unscheduled(schedulers_before)
    store = reader or _reader()

    def make() -> dict[str, Any]:
        return {
            "version": "a7-production-law-transfer-job-claim-v1",
            "run_id": RUN_ID,
            "protocol_id": PROTOCOL_ID,
            "protocol_sha256": runner.PROTOCOL_SHA256,
            "code_sha": code_sha,
            "image": image,
            "build_id": build_id,
            "build_metadata_sha256": sha256(
                _canonical_json(build_metadata)
            ).hexdigest(),
            "predecessor_license": predecessor,
            "job_before": job,
            "inert_contract": inert_contract(code_sha=code_sha, image=image),
            "phase_order": list(PHASES),
            "output_uris": PHASE_OUTPUT,
            "claimed_at": _now(),
            "uses_realized_outcomes": False,
            "actual_score_query_executed": False,
            "historical_outcome_lease_acquired": False,
            "job_create_licensed": False,
            "job_delete_licensed": False,
            "scheduler_licensed": False,
            "retry_licensed": False,
            "licenses": science.licenses(),
        }

    body, obj = _publish_recoverable(
        store, uri=JOB_CLAIM_URI, make_body=make,
        validate=_validate_claim_body,
    )
    fixed = {
        "code_sha": code_sha,
        "image": image,
        "build_id": build_id,
        "build_metadata_sha256": sha256(_canonical_json(build_metadata)).hexdigest(),
        "predecessor_license": predecessor,
        "job_before": job,
    }
    if any(body.get(key) != expected for key, expected in fixed.items()):
        raise TransferTransportError("existing job claim inputs differ")
    return _write_wrapper(
        receipt_path, body_key="claim", body=body, obj=obj,
        label="job-claim receipt",
    )


def _validate_deployment_body(value: object) -> dict[str, Any]:
    required = {
        "version", "run_id", "claim_object", "code_sha", "image",
        "job", "contract", "prepared_at", "uses_realized_outcomes",
        "historical_outcome_lease_acquired", "scheduler_licensed",
        "retry_licensed", "licenses",
    }
    if not isinstance(value, dict) or set(value) != required or value.get(
        "version"
    ) != "a7-production-law-transfer-deployment-v1" or value.get(
        "run_id"
    ) != RUN_ID or HEX40.fullmatch(str(value.get("code_sha", ""))) is None or \
            IMAGE.fullmatch(str(value.get("image", ""))) is None or value.get(
                "contract"
            ) != inert_contract(
                code_sha=value["code_sha"], image=value["image"],
            ) or value.get("uses_realized_outcomes") is not False or value.get(
                "historical_outcome_lease_acquired"
            ) is not False or value.get("scheduler_licensed") is not False or value.get(
                "retry_licensed"
            ) is not False or value.get("licenses") != science.licenses():
        raise TransferTransportError("deployment body differs")
    _object_identity(value.get("claim_object"), uri=JOB_CLAIM_URI, create_only=True)
    _timestamp(value.get("prepared_at"), label="deployment time")
    job = value.get("job")
    if not isinstance(job, dict) or set(job) != {
        "name", "uid", "generation", "spec_sha256",
    } or job.get("name") != JOB or GENERATION.fullmatch(
        str(job.get("generation", ""))
    ) is None or HEX64.fullmatch(str(job.get("spec_sha256", ""))) is None:
        raise TransferTransportError("deployment job identity differs")
    return value


def prepare_deployment(
    *,
    claim_path: Path,
    job_after: Mapping[str, Any],
    executions_after: object,
    schedulers_after: object,
    receipt_path: Path,
    reader: a7_transport._StorageReader | None = None,
) -> dict[str, Any]:
    _validate_predecessor()
    claim = _load_wrapper(
        claim_path, label="job claim", body_key="claim", uri=JOB_CLAIM_URI,
        validate_body=_validate_claim_body,
    )
    store = reader or _reader()
    claim = _load_live_wrapper(
        store, claim, body_key="claim", uri=JOB_CLAIM_URI, label="job claim",
        validate_body=_validate_claim_body,
    )
    body = claim["claim"]
    job = _validate_job_contract(
        job_after, contract=body["inert_contract"],
        uid=body["job_before"]["uid"],
    )
    if int(job["generation"]) <= int(body["job_before"]["generation"]):
        raise TransferTransportError("reused job generation did not advance")
    _require_idle(executions_after)
    _require_unscheduled(schedulers_after)

    def make() -> dict[str, Any]:
        return {
            "version": "a7-production-law-transfer-deployment-v1",
            "run_id": RUN_ID,
            "claim_object": claim["object"],
            "code_sha": body["code_sha"],
            "image": body["image"],
            "job": job,
            "contract": body["inert_contract"],
            "prepared_at": _now(),
            "uses_realized_outcomes": False,
            "historical_outcome_lease_acquired": False,
            "scheduler_licensed": False,
            "retry_licensed": False,
            "licenses": science.licenses(),
        }

    deployment, obj = _publish_recoverable(
        store, uri=DEPLOYMENT_URI, make_body=make,
        validate=_validate_deployment_body,
    )
    if deployment.get("claim_object") != claim["object"] or deployment.get(
        "job"
    ) != job:
        raise TransferTransportError("existing deployment inputs differ")
    return _write_wrapper(
        receipt_path, body_key="deployment", body=deployment, obj=obj,
        label="deployment receipt",
    )


def _phase_remote_uris(phase: str) -> set[str]:
    return {
        _phase_uri(phase, kind)
        for kind in ("intent", "launch-claim", "execution-claim", "terminal")
    } | {PHASE_OUTPUT[phase]}


def _prior_remote_uris(phase: str) -> set[str]:
    result = {JOB_CLAIM_URI, DEPLOYMENT_URI}
    index = PHASES.index(phase)
    for prior in PHASES[:index]:
        result.update(_phase_remote_uris(prior))
    if phase == "full":
        result.update({runner.FREEZE_MANIFEST_URI, FREEZE_RECEIPT_URI})
    return result


def _validate_prefix_inventory(
    reader: a7_transport._StorageReader,
    *,
    expected: set[str],
    optional: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    inventory = reader.inventory(f"{PREFIX}/")
    observed = set(inventory)
    allowed = expected | (optional or set())
    if not expected <= observed or not observed <= allowed:
        raise TransferTransportError(
            "transfer prefix inventory differs: "
            f"missing={sorted(expected-observed)} extra={sorted(observed-allowed)}"
        )
    return inventory


def _validate_execution_census(
    value: object,
    *,
    deployment: Mapping[str, Any],
    expected_names: set[str],
) -> None:
    _require_idle(value)
    if not isinstance(value, list):
        raise TransferTransportError("execution census differs")
    job = deployment["job"]
    observed: set[str] = set()
    for row in value:
        metadata = row.get("metadata", {}) if isinstance(row, dict) else {}
        labels = metadata.get("labels", {}) if isinstance(metadata, dict) else {}
        if labels.get("run.googleapis.com/jobUid") == job["uid"] and str(
            labels.get("run.googleapis.com/jobGeneration", "")
        ) == job["generation"]:
            name = str(metadata.get("name", ""))
            if not name or name in observed:
                raise TransferTransportError("execution census identity differs")
            observed.add(name)
    if observed != expected_names:
        raise TransferTransportError(
            "unexpected execution exists for the claimed job generation"
        )


def _validate_terminal_body(value: object, *, phase: str) -> dict[str, Any]:
    required = {
        "version", "run_id", "phase", "deployment_object", "intent_object",
        "launch_claim_object", "execution_claim_object", "execution",
        "execution_metadata_sha256", "result_object",
        "prefix_inventory_before_terminal_sha256", "decision", "completed_at",
        "uses_realized_outcomes", "actual_score_query_executed",
        "historical_outcome_lease_acquired", "production_mutated",
        "retry_licensed", "licenses",
    }
    if not isinstance(value, dict) or set(value) != required or value.get(
        "version"
    ) != "a7-production-law-transfer-terminal-v1" or value.get(
        "run_id"
    ) != RUN_ID or value.get("phase") != phase or HEX64.fullmatch(
        str(value.get("execution_metadata_sha256", ""))
    ) is None or HEX64.fullmatch(
        str(value.get("prefix_inventory_before_terminal_sha256", ""))
    ) is None or value.get("uses_realized_outcomes") is not False or value.get(
        "actual_score_query_executed"
    ) is not False or value.get("historical_outcome_lease_acquired") is not False or \
            value.get("production_mutated") is not False or value.get(
                "retry_licensed"
            ) is not False:
        raise TransferTransportError("terminal body differs")
    _object_identity(value.get("deployment_object"), uri=DEPLOYMENT_URI, create_only=True)
    _object_identity(
        value.get("intent_object"), uri=_phase_uri(phase, "intent"),
        create_only=True,
    )
    _object_identity(
        value.get("launch_claim_object"), uri=_phase_uri(phase, "launch-claim"),
        create_only=True,
    )
    _object_identity(
        value.get("execution_claim_object"),
        uri=_phase_uri(phase, "execution-claim"), create_only=True,
    )
    _object_identity(value.get("result_object"), uri=PHASE_OUTPUT[phase])
    execution = value.get("execution")
    if not isinstance(execution, dict) or set(execution) != {
        "name", "generation", "job", "job_uid", "job_generation",
        "completion_time", "counters", "spec_sha256", "contract_sha256",
    } or not str(execution.get("name", "")).startswith(f"{JOB}-") or execution.get(
        "generation"
    ) != "1" or execution.get("job") != JOB or not execution.get("job_uid") or \
            GENERATION.fullmatch(str(execution.get("job_generation", ""))) is None or \
            execution.get("counters") != {
                "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
            } or HEX64.fullmatch(str(execution.get("spec_sha256", ""))) is None or \
            HEX64.fullmatch(str(execution.get("contract_sha256", ""))) is None:
        raise TransferTransportError("terminal execution receipt differs")
    _timestamp(execution.get("completion_time"), label="execution completion")
    _timestamp(value.get("completed_at"), label="terminal completion")
    decision = value.get("decision")
    if not isinstance(decision, dict) or not isinstance(
        value.get("licenses"), dict,
    ) or value.get("licenses") != decision.get(
        "licenses"
    ) or set(value["licenses"]) != set(science.LICENSE_FIELDS) or any(
        type(flag) is not bool for flag in value["licenses"].values()
    ):
        raise TransferTransportError("terminal decision differs")
    if phase != "full" and value["licenses"] != science.licenses():
        raise TransferTransportError("preflight terminal licenses action")
    if phase == "full" and any(
        flag for key, flag in value["licenses"].items()
        if key != "prospective_shadow_licensed"
    ):
        raise TransferTransportError("full terminal licenses forbidden action")
    return value


def _load_terminal_wrapper(
    out: Path,
    phase: str,
    reader: a7_transport._StorageReader,
) -> dict[str, Any]:
    wrapper = _load_wrapper(
        _phase_path(out, phase, "terminal-receipt.json"),
        label=f"{phase} terminal", body_key="terminal",
        uri=_phase_uri(phase, "terminal"),
        validate_body=lambda value: _validate_terminal_body(value, phase=phase),
    )
    return _load_live_wrapper(
        reader, wrapper, body_key="terminal", uri=_phase_uri(phase, "terminal"),
        label=f"{phase} terminal",
        validate_body=lambda value: _validate_terminal_body(value, phase=phase),
    )


def _query_hashes_from_terminal(value: Mapping[str, Any]) -> dict[str, str]:
    decision = value.get("decision")
    query = decision.get("query_sha256") if isinstance(decision, dict) else None
    if not isinstance(query, dict) or set(query) != {"candidates", "players"} or any(
        HEX64.fullmatch(str(query.get(key, ""))) is None
        for key in ("candidates", "players")
    ):
        raise TransferTransportError("terminal query hashes differ")
    return {"candidates": query["candidates"], "players": query["players"]}


def _load_freeze_wrapper(
    out: Path,
    reader: a7_transport._StorageReader,
) -> dict[str, Any]:
    wrapper = _load(out / "freeze-receipt.json", label="freeze receipt")
    if set(wrapper) != {"version", "manifest", "object", "receipt_object"} or wrapper.get(
        "version"
    ) != "a7-production-law-transfer-freeze-receipt-v1":
        raise TransferTransportError("freeze receipt differs")
    manifest_object = _object_identity(
        wrapper.get("object"), uri=runner.FREEZE_MANIFEST_URI,
    )
    receipt_object = _object_identity(
        wrapper.get("receipt_object"), uri=FREEZE_RECEIPT_URI, create_only=True,
    )
    manifest, observed = _load_pinned(
        reader, manifest_object, uri=runner.FREEZE_MANIFEST_URI,
        label="execution freeze",
    )
    if observed != manifest_object or wrapper.get("manifest") != manifest:
        raise TransferTransportError("live execution freeze differs")
    receipt_body, _ = _load_pinned(
        reader,
        {key: receipt_object[key] for key in (
            "uri", "generation", "metageneration", "bytes", "sha256"
        )},
        uri=FREEZE_RECEIPT_URI, label="freeze receipt object",
    )
    if receipt_body != {
        "version": "a7-production-law-transfer-freeze-object-v1",
        "run_id": RUN_ID,
        "manifest_object": manifest_object,
        "query_sha256": manifest.get("source_query_sha256"),
        "support_passed": True,
        "uses_realized_outcomes": False,
        "licenses": science.licenses(),
    }:
        raise TransferTransportError("freeze receipt object body differs")
    return wrapper


def _phase_prerequisites(
    *,
    phase: str,
    out: Path,
    reader: a7_transport._StorageReader,
) -> tuple[dict[str, Any], set[str]]:
    if phase == "smoke":
        return {}, set()
    smoke = _load_terminal_wrapper(out, "smoke", reader)
    names = {smoke["terminal"]["execution"]["name"]}
    query = _query_hashes_from_terminal(smoke["terminal"])
    if phase == "support":
        return {
            "query_sha256": query,
            "smoke": smoke["terminal"]["result_object"],
        }, names
    support = _load_terminal_wrapper(out, "support", reader)
    if support["terminal"]["decision"].get("support_passed") is not True:
        raise TransferTransportError("unsupported support forbids full")
    if _query_hashes_from_terminal(support["terminal"]) != query:
        raise TransferTransportError("support query hashes differ from smoke")
    names.add(support["terminal"]["execution"]["name"])
    freeze = _load_freeze_wrapper(out, reader)
    if freeze["manifest"].get("source_query_sha256") != query:
        raise TransferTransportError("freeze query hashes differ")
    return {
        "query_sha256": query,
        "freeze": freeze["object"],
    }, names


def _validate_intent_body(value: object, *, phase: str) -> dict[str, Any]:
    required = {
        "version", "run_id", "phase", "deployment_object", "job",
        "contract", "contract_sha256", "prerequisites", "expected_output_uri",
        "expected_prior_executions", "created_at", "launch_attempted_at_creation",
        "uses_realized_outcomes", "historical_outcome_lease_acquired",
        "retry_licensed", "production_mutation_licensed", "licenses",
    }
    if not isinstance(value, dict) or set(value) != required or value.get(
        "version"
    ) != "a7-production-law-transfer-launch-intent-v1" or value.get(
        "run_id"
    ) != RUN_ID or value.get("phase") != phase or value.get(
        "expected_output_uri"
    ) != PHASE_OUTPUT[phase] or value.get("launch_attempted_at_creation") is not False or \
            value.get("uses_realized_outcomes") is not False or value.get(
                "historical_outcome_lease_acquired"
            ) is not False or value.get("retry_licensed") is not False or value.get(
                "production_mutation_licensed"
            ) is not False or value.get("licenses") != science.licenses():
        raise TransferTransportError("phase launch intent differs")
    _object_identity(
        value.get("deployment_object"), uri=DEPLOYMENT_URI, create_only=True,
    )
    _timestamp(value.get("created_at"), label="launch intent time")
    if not isinstance(value.get("expected_prior_executions"), list) or value[
        "expected_prior_executions"
    ] != sorted(set(value["expected_prior_executions"])):
        raise TransferTransportError("launch intent prior executions differ")
    job = value.get("job")
    if not isinstance(job, dict) or set(job) != {
        "name", "uid", "generation", "spec_sha256",
    } or job.get("name") != JOB:
        raise TransferTransportError("launch intent job differs")
    contract = registered_contract(
        phase=phase, code_sha=value["contract"]["env"]["CODE_SHA"],
        image=value["contract"]["image"],
        prerequisites=value["prerequisites"],
    ) if isinstance(value.get("contract"), dict) else None
    if contract != value.get("contract") or value.get(
        "contract_sha256"
    ) != sha256(_canonical_json(contract)).hexdigest():
        raise TransferTransportError("launch intent contract differs")
    return value


def create_phase_intent(
    *,
    phase: str,
    out: Path,
    deployment_path: Path,
    job_current: Mapping[str, Any],
    executions_current: object,
    schedulers_current: object,
    reader: a7_transport._StorageReader | None = None,
) -> dict[str, Any]:
    _validate_predecessor()
    if phase not in PHASES:
        raise TransferTransportError("phase differs")
    deployment = _load_wrapper(
        deployment_path, label="deployment", body_key="deployment",
        uri=DEPLOYMENT_URI, validate_body=_validate_deployment_body,
    )
    store = reader or _reader()
    deployment = _load_live_wrapper(
        store, deployment, body_key="deployment", uri=DEPLOYMENT_URI,
        label="deployment", validate_body=_validate_deployment_body,
    )
    body = deployment["deployment"]
    observed_job = _validate_job_contract(
        job_current, contract=body["contract"], uid=body["job"]["uid"],
    )
    if observed_job != body["job"]:
        raise TransferTransportError("reused inert job changed after deployment")
    _require_unscheduled(schedulers_current)
    prerequisites, expected_names = _phase_prerequisites(
        phase=phase, out=out, reader=store,
    )
    _validate_execution_census(
        executions_current, deployment=body, expected_names=expected_names,
    )
    _validate_prefix_inventory(
        store, expected=_prior_remote_uris(phase),
        optional={_phase_uri(phase, "intent")},
    )
    contract = registered_contract(
        phase=phase, code_sha=body["code_sha"], image=body["image"],
        prerequisites=prerequisites,
    )

    def make() -> dict[str, Any]:
        return {
            "version": "a7-production-law-transfer-launch-intent-v1",
            "run_id": RUN_ID,
            "phase": phase,
            "deployment_object": deployment["object"],
            "job": body["job"],
            "contract": contract,
            "contract_sha256": sha256(_canonical_json(contract)).hexdigest(),
            "prerequisites": prerequisites,
            "expected_output_uri": PHASE_OUTPUT[phase],
            "expected_prior_executions": sorted(expected_names),
            "created_at": _now(),
            "launch_attempted_at_creation": False,
            "uses_realized_outcomes": False,
            "historical_outcome_lease_acquired": False,
            "retry_licensed": False,
            "production_mutation_licensed": False,
            "licenses": science.licenses(),
        }

    intent, obj = _publish_recoverable(
        store, uri=_phase_uri(phase, "intent"), make_body=make,
        validate=lambda value: _validate_intent_body(value, phase=phase),
    )
    fixed = {
        "deployment_object": deployment["object"],
        "job": body["job"],
        "contract": contract,
        "prerequisites": prerequisites,
        "expected_prior_executions": sorted(expected_names),
    }
    if any(intent.get(key) != expected for key, expected in fixed.items()):
        raise TransferTransportError("existing phase intent inputs differ")
    return _write_wrapper(
        _phase_path(out, phase, "intent-receipt.json"),
        body_key="intent", body=intent, obj=obj,
        label=f"{phase} intent receipt",
    )


def _load_intent_wrapper(
    out: Path,
    phase: str,
    reader: a7_transport._StorageReader,
) -> dict[str, Any]:
    wrapper = _load_wrapper(
        _phase_path(out, phase, "intent-receipt.json"),
        label=f"{phase} intent", body_key="intent",
        uri=_phase_uri(phase, "intent"),
        validate_body=lambda value: _validate_intent_body(value, phase=phase),
    )
    return _load_live_wrapper(
        reader, wrapper, body_key="intent", uri=_phase_uri(phase, "intent"),
        label=f"{phase} intent",
        validate_body=lambda value: _validate_intent_body(value, phase=phase),
    )


def _validate_launch_claim_body(value: object, *, phase: str) -> dict[str, Any]:
    required = {
        "version", "run_id", "phase", "intent_object", "job",
        "contract_sha256", "execution_census_sha256", "scheduler_census_sha256",
        "prefix_inventory_sha256", "claimed_at", "execution_name_known",
        "retry_licensed", "uses_realized_outcomes", "licenses",
    }
    if not isinstance(value, dict) or set(value) != required or value.get(
        "version"
    ) != "a7-production-law-transfer-launch-claim-v1" or value.get(
        "run_id"
    ) != RUN_ID or value.get("phase") != phase or any(
        HEX64.fullmatch(str(value.get(key, ""))) is None
        for key in (
            "contract_sha256", "execution_census_sha256",
            "scheduler_census_sha256", "prefix_inventory_sha256",
        )
    ) or value.get("execution_name_known") is not False or value.get(
        "retry_licensed"
    ) is not False or value.get("uses_realized_outcomes") is not False or value.get(
        "licenses"
    ) != science.licenses():
        raise TransferTransportError("phase launch claim differs")
    _object_identity(
        value.get("intent_object"), uri=_phase_uri(phase, "intent"),
        create_only=True,
    )
    _timestamp(value.get("claimed_at"), label="launch claim time")
    job = value.get("job")
    if not isinstance(job, dict) or set(job) != {
        "name", "uid", "generation", "spec_sha256",
    } or job.get("name") != JOB:
        raise TransferTransportError("launch claim job differs")
    return value


def create_launch_claim(
    *,
    phase: str,
    out: Path,
    job_current: Mapping[str, Any],
    executions_current: object,
    schedulers_current: object,
    reader: a7_transport._StorageReader | None = None,
) -> dict[str, Any]:
    _validate_predecessor()
    store = reader or _reader()
    intent = _load_intent_wrapper(out, phase, store)
    body = intent["intent"]
    job = _job_identity(job_current, uid=body["job"]["uid"])
    if job != body["job"]:
        raise TransferTransportError("launch job differs from intent")
    _validate_job_contract(
        job_current,
        contract=inert_contract(
            code_sha=body["contract"]["env"]["CODE_SHA"],
            image=body["contract"]["image"],
        ),
        uid=job["uid"],
    )
    _require_unscheduled(schedulers_current)
    deployment = {"job": job}
    expected_names = set(body["expected_prior_executions"])
    _validate_execution_census(
        executions_current, deployment=deployment, expected_names=expected_names,
    )
    inventory = _validate_prefix_inventory(
        store,
        expected=_prior_remote_uris(phase) | {_phase_uri(phase, "intent")},
        optional={_phase_uri(phase, "launch-claim")},
    )

    def make() -> dict[str, Any]:
        return {
            "version": "a7-production-law-transfer-launch-claim-v1",
            "run_id": RUN_ID,
            "phase": phase,
            "intent_object": intent["object"],
            "job": job,
            "contract_sha256": body["contract_sha256"],
            "execution_census_sha256": sha256(
                _canonical_json(executions_current)
            ).hexdigest(),
            "scheduler_census_sha256": sha256(
                _canonical_json(schedulers_current)
            ).hexdigest(),
            "prefix_inventory_sha256": sha256(
                _canonical_json(sorted(inventory))
            ).hexdigest(),
            "claimed_at": _now(),
            "execution_name_known": False,
            "retry_licensed": False,
            "uses_realized_outcomes": False,
            "licenses": science.licenses(),
        }

    claim, obj = _publish_recoverable(
        store, uri=_phase_uri(phase, "launch-claim"), make_body=make,
        validate=lambda value: _validate_launch_claim_body(value, phase=phase),
    )
    fixed = {
        "intent_object": intent["object"],
        "job": job,
        "contract_sha256": body["contract_sha256"],
        "execution_census_sha256": sha256(
            _canonical_json(executions_current)
        ).hexdigest(),
        "scheduler_census_sha256": sha256(
            _canonical_json(schedulers_current)
        ).hexdigest(),
    }
    if any(claim.get(key) != expected for key, expected in fixed.items()):
        raise TransferTransportError("existing launch claim inputs differ")
    return _write_wrapper(
        _phase_path(out, phase, "launch-claim-receipt.json"),
        body_key="launch_claim", body=claim, obj=obj,
        label=f"{phase} launch-claim receipt",
    )


def _load_launch_claim_wrapper(
    out: Path,
    phase: str,
    reader: a7_transport._StorageReader,
) -> dict[str, Any]:
    wrapper = _load_wrapper(
        _phase_path(out, phase, "launch-claim-receipt.json"),
        label=f"{phase} launch claim", body_key="launch_claim",
        uri=_phase_uri(phase, "launch-claim"),
        validate_body=lambda value: _validate_launch_claim_body(value, phase=phase),
    )
    return _load_live_wrapper(
        reader, wrapper, body_key="launch_claim",
        uri=_phase_uri(phase, "launch-claim"), label=f"{phase} launch claim",
        validate_body=lambda value: _validate_launch_claim_body(value, phase=phase),
    )


def _execution_parts(value: object) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict):
        raise TransferTransportError("execution metadata differs")
    metadata = value.get("metadata")
    spec = value.get("spec")
    task = spec.get("template", {}).get("spec") if isinstance(spec, dict) else None
    if not isinstance(metadata, dict) or not isinstance(spec, dict) or not isinstance(
        task, dict,
    ):
        raise TransferTransportError("execution schema differs")
    return metadata, spec, task


def _validate_execution_contract(
    value: object,
    *,
    phase: str,
    intent: Mapping[str, Any],
    execution_name: str | None = None,
    require_terminal: bool,
) -> dict[str, Any]:
    metadata, spec, task = _execution_parts(value)
    name = str(metadata.get("name", ""))
    labels = metadata.get("labels")
    job = intent["job"]
    if not name.startswith(f"{JOB}-") or (
        execution_name is not None and name != execution_name
    ) or metadata.get("generation") != 1 or not isinstance(labels, dict) or labels.get(
        "run.googleapis.com/job"
    ) != JOB or labels.get("run.googleapis.com/jobUid") != job["uid"] or str(
        labels.get("run.googleapis.com/jobGeneration", "")
    ) != job["generation"]:
        raise TransferTransportError("execution identity differs")
    containers = task.get("containers")
    contract = intent["contract"]
    if spec.get("taskCount") != 1 or spec.get("parallelism") != 1 or \
            not isinstance(containers, list) or len(containers) != 1 or not isinstance(
                containers[0], dict,
            ):
        raise TransferTransportError("execution task shape differs")
    container = containers[0]
    if container.get("image") != contract["image"] or container.get(
        "command"
    ) != contract["command"] or container.get("args") != contract["args"] or \
            _env_rows(container.get("env", [])) != contract["env"] or container.get(
                "resources", {}
            ).get("limits") != contract["resources"] or task.get(
                "maxRetries"
            ) != 0 or str(task.get("timeoutSeconds")) != TIMEOUT_SECONDS or task.get(
                "serviceAccountName"
            ) != SERVICE_ACCOUNT or task.get("volumes", []) != [] or container.get(
                "workingDir", ""
            ) != "" or container.get("volumeMounts", []) != [] or container.get(
                "startupProbe"
            ) not in (None, {}):
        raise TransferTransportError("execution contract differs")
    if not require_terminal:
        return {"name": name, "job": job, "spec_sha256": sha256(
            _canonical_json(spec)
        ).hexdigest()}
    status = value.get("status")
    if not isinstance(status, dict) or status.get("observedGeneration") != 1:
        raise TransferTransportError("execution terminal status differs")
    completed = [
        row for row in status.get("conditions", [])
        if isinstance(row, dict) and row.get("type") == "Completed"
    ]
    counters = {
        key: status.get(field, 0)
        for key, field in (
            ("succeeded", "succeededCount"), ("failed", "failedCount"),
            ("cancelled", "cancelledCount"), ("retried", "retriedCount"),
        )
    }
    if any(type(count) is not int or count < 0 for count in counters.values()) or \
            len(completed) != 1 or completed[0].get("status") != "True" or counters != {
                "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
            } or not status.get("completionTime"):
        raise TransferTransportError("execution is not strict terminal success")
    completion = _timestamp(
        status["completionTime"], label="execution completion time",
    )
    return {
        "name": name,
        "generation": "1",
        "job": JOB,
        "job_uid": job["uid"],
        "job_generation": job["generation"],
        "completion_time": completion,
        "counters": counters,
        "spec_sha256": sha256(_canonical_json(spec)).hexdigest(),
        "contract_sha256": intent["contract_sha256"],
    }


def _validate_execution_claim_body(value: object, *, phase: str) -> dict[str, Any]:
    required = {
        "version", "run_id", "phase", "launch_claim_object", "intent_object",
        "job", "execution_name", "execute_response_sha256", "registered_at",
        "relaunch_licensed", "retry_licensed", "uses_realized_outcomes",
        "licenses",
    }
    if not isinstance(value, dict) or set(value) != required or value.get(
        "version"
    ) != "a7-production-law-transfer-execution-claim-v1" or value.get(
        "run_id"
    ) != RUN_ID or value.get("phase") != phase or not str(
        value.get("execution_name", "")
    ).startswith(f"{JOB}-") or HEX64.fullmatch(
        str(value.get("execute_response_sha256", ""))
    ) is None or value.get("relaunch_licensed") is not False or value.get(
        "retry_licensed"
    ) is not False or value.get("uses_realized_outcomes") is not False or value.get(
        "licenses"
    ) != science.licenses():
        raise TransferTransportError("execution claim differs")
    _object_identity(
        value.get("launch_claim_object"), uri=_phase_uri(phase, "launch-claim"),
        create_only=True,
    )
    _object_identity(
        value.get("intent_object"), uri=_phase_uri(phase, "intent"),
        create_only=True,
    )
    _timestamp(value.get("registered_at"), label="execution registration")
    return value


def register_execution(
    *,
    phase: str,
    out: Path,
    execute_response: Mapping[str, Any],
    reader: a7_transport._StorageReader | None = None,
) -> dict[str, Any]:
    _validate_predecessor()
    store = reader or _reader()
    intent = _load_intent_wrapper(out, phase, store)
    launch = _load_launch_claim_wrapper(out, phase, store)
    if launch["launch_claim"]["intent_object"] != intent["object"]:
        raise TransferTransportError("launch claim/intent chain differs")
    execution = _validate_execution_contract(
        execute_response, phase=phase, intent=intent["intent"],
        require_terminal=False,
    )
    response_sha = sha256(_canonical_json(execute_response)).hexdigest()

    def make() -> dict[str, Any]:
        return {
            "version": "a7-production-law-transfer-execution-claim-v1",
            "run_id": RUN_ID,
            "phase": phase,
            "launch_claim_object": launch["object"],
            "intent_object": intent["object"],
            "job": intent["intent"]["job"],
            "execution_name": execution["name"],
            "execute_response_sha256": response_sha,
            "registered_at": _now(),
            "relaunch_licensed": False,
            "retry_licensed": False,
            "uses_realized_outcomes": False,
            "licenses": science.licenses(),
        }

    claim, obj = _publish_recoverable(
        store, uri=_phase_uri(phase, "execution-claim"), make_body=make,
        validate=lambda value: _validate_execution_claim_body(value, phase=phase),
    )
    fixed = {
        "launch_claim_object": launch["object"],
        "intent_object": intent["object"],
        "job": intent["intent"]["job"],
        "execution_name": execution["name"],
        "execute_response_sha256": response_sha,
    }
    if any(claim.get(key) != expected for key, expected in fixed.items()):
        raise TransferTransportError("existing execution claim inputs differ")
    wrapper = _write_wrapper(
        _phase_path(out, phase, "execution-claim-receipt.json"),
        body_key="execution_claim", body=claim, obj=obj,
        label=f"{phase} execution-claim receipt",
    )
    _write_or_validate(
        _phase_path(out, phase, "execute-response.json"),
        _canonical_json(execute_response), label=f"{phase} execute response",
    )
    _write_or_validate(
        _phase_path(out, phase, "executions.txt"),
        f"{JOB} {execution['name']}\n".encode(), label=f"{phase} execution ledger",
    )
    return wrapper


def _load_execution_claim_wrapper(
    out: Path,
    phase: str,
    reader: a7_transport._StorageReader,
) -> dict[str, Any]:
    wrapper = _load_wrapper(
        _phase_path(out, phase, "execution-claim-receipt.json"),
        label=f"{phase} execution claim", body_key="execution_claim",
        uri=_phase_uri(phase, "execution-claim"),
        validate_body=lambda value: _validate_execution_claim_body(
            value, phase=phase,
        ),
    )
    return _load_live_wrapper(
        reader, wrapper, body_key="execution_claim",
        uri=_phase_uri(phase, "execution-claim"),
        label=f"{phase} execution claim",
        validate_body=lambda value: _validate_execution_claim_body(
            value, phase=phase,
        ),
    )


def _validate_result(
    value: object,
    *,
    phase: str,
    claim: Mapping[str, Any],
    intent: Mapping[str, Any],
    freeze_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TransferTransportError("science result differs")
    query = value.get("source_query_receipts")
    if not isinstance(query, dict) or set(query) != {"candidates", "players"}:
        raise TransferTransportError("science result query receipts differ")
    query_hashes = {
        key: str(query[key].get("sha256", ""))
        for key in ("candidates", "players")
    }
    if any(HEX64.fullmatch(digest) is None for digest in query_hashes.values()):
        raise TransferTransportError("science result query hashes differ")
    fixed = {
        "version": runner.VERSION,
        "run_id": RUN_ID,
        "mode": PHASE_MODE[phase],
        "protocol_sha256": runner.PROTOCOL_SHA256,
        "code_sha": claim["code_sha"],
        "image": claim["image"],
        "predecessor_license": claim["predecessor_license"],
        "uses_realized_outcomes": False,
        "actual_score_query_executed": False,
        "historical_outcome_lease_acquired": False,
        "production_mutated": False,
    }
    if any(value.get(key) != expected for key, expected in fixed.items()):
        raise TransferTransportError("science result identity differs")
    if phase == "smoke":
        try:
            runner._validate_preflight_receipt(
                value, mode="real-artifact-smoke",
                predecessor=claim["predecessor_license"],
                code_sha=claim["code_sha"], image=claim["image"],
                expected_candidate_sha256=query_hashes["candidates"],
                expected_player_sha256=query_hashes["players"],
                expected_preflight_receipts={},
            )
        except Exception as exc:
            raise TransferTransportError("smoke science replay differs") from exc
    elif phase == "support":
        prerequisites = intent["prerequisites"]
        if query_hashes != prerequisites["query_sha256"]:
            raise TransferTransportError("support query hashes differ")
        try:
            runner._validate_preflight_receipt(
                value, mode="support-census",
                predecessor=claim["predecessor_license"],
                code_sha=claim["code_sha"], image=claim["image"],
                expected_candidate_sha256=query_hashes["candidates"],
                expected_player_sha256=query_hashes["players"],
                expected_preflight_receipts={"smoke": prerequisites["smoke"]},
            )
        except Exception as exc:
            raise TransferTransportError("support science replay differs") from exc
    else:
        prerequisites = intent["prerequisites"]
        if freeze_manifest is None:
            raise TransferTransportError("full freeze manifest is absent")
        if query_hashes != prerequisites["query_sha256"] or value.get(
            "execution_freeze"
        ) != prerequisites["freeze"] or value.get("scope") != [
            [season, week] for season, week in runner.FULL_SLATES
        ] or len(value.get("source_artifacts", [])) != runner.ARTIFACT_COUNT or value.get(
            "source_lock"
        ) != {
            "uri": runner.SOURCE_LOCK_URI,
            "generation": runner.SOURCE_LOCK_GENERATION,
            "sha256": runner.SOURCE_LOCK_SHA256,
            "bytes": runner.SOURCE_LOCK_BYTES,
        } or value.get("preflight_receipts") != freeze_manifest.get(
            "preflights"
        ) or freeze_manifest.get("source_query_sha256") != query_hashes:
            raise TransferTransportError("full frozen source identity differs")
        rows = value.get("slates")
        if not isinstance(rows, list):
            raise TransferTransportError("full score-free rows differ")
        try:
            replay = science.aggregate_transfer(rows)
        except Exception as exc:
            raise TransferTransportError("full science replay failed") from exc
        expected_decision = {
            key: replay[key]
            for key in (
                "version", "protocol_id", "uses_realized_outcomes",
                "actual_score_query_executed", "scorefree_transfer_passed",
                "disposition", "licenses",
            )
        }
        if value.get("transfer_gate") != replay or value.get(
            "decision"
        ) != expected_decision or value.get("support") != replay["gate"]["support"]:
            raise TransferTransportError("full unchanged gate replay differs")
    decision = value.get("decision")
    if not isinstance(decision, dict) or not isinstance(
        decision.get("licenses"), dict,
    ):
        raise TransferTransportError("science decision differs")
    return {
        "disposition": decision.get("disposition"),
        "licenses": decision["licenses"],
        "query_sha256": query_hashes,
        "support_passed": (
            bool(decision.get("support_passed")) if phase == "support" else None
        ),
        "scorefree_transfer_passed": (
            bool(decision.get("scorefree_transfer_passed"))
            if phase == "full" else False
        ),
    }


def _snapshot_inventory(
    reader: a7_transport._StorageReader,
    inventory: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for uri in sorted(inventory):
        generation = str(inventory[uri].get("generation", ""))
        metadata, raw = reader.load(uri, generation)
        rows.append(_metadata_identity(metadata, uri=uri, raw=raw))
    return rows


def harvest_phase(
    *,
    phase: str,
    out: Path,
    execution_metadata: Mapping[str, Any],
    reader: a7_transport._StorageReader | None = None,
) -> dict[str, Any]:
    # Body firewall: strict terminal validation precedes storage construction,
    # result inventory, or any result-body read.
    predecessor = _validate_predecessor()
    intent_local = _load_wrapper(
        _phase_path(out, phase, "intent-receipt.json"),
        label=f"{phase} intent", body_key="intent",
        uri=_phase_uri(phase, "intent"),
        validate_body=lambda value: _validate_intent_body(value, phase=phase),
    )
    execution_claim_local = _load_wrapper(
        _phase_path(out, phase, "execution-claim-receipt.json"),
        label=f"{phase} execution claim", body_key="execution_claim",
        uri=_phase_uri(phase, "execution-claim"),
        validate_body=lambda value: _validate_execution_claim_body(
            value, phase=phase,
        ),
    )
    execution = _validate_execution_contract(
        execution_metadata, phase=phase, intent=intent_local["intent"],
        execution_name=execution_claim_local["execution_claim"]["execution_name"],
        require_terminal=True,
    )

    store = reader or _reader()
    intent = _load_intent_wrapper(out, phase, store)
    execution_claim = _load_execution_claim_wrapper(out, phase, store)
    launch_claim = _load_launch_claim_wrapper(out, phase, store)
    deployment_wrapper = _load_wrapper(
        out / "deployment-receipt.json", label="deployment",
        body_key="deployment", uri=DEPLOYMENT_URI,
        validate_body=_validate_deployment_body,
    )
    deployment = _load_live_wrapper(
        store, deployment_wrapper, body_key="deployment", uri=DEPLOYMENT_URI,
        label="deployment", validate_body=_validate_deployment_body,
    )
    claim_wrapper = _load_wrapper(
        out / "job-claim-receipt.json", label="job claim", body_key="claim",
        uri=JOB_CLAIM_URI, validate_body=_validate_claim_body,
    )
    claim = _load_live_wrapper(
        store, claim_wrapper, body_key="claim", uri=JOB_CLAIM_URI,
        label="job claim", validate_body=_validate_claim_body,
    )
    if claim["claim"]["predecessor_license"] != predecessor or intent[
        "intent"
    ]["deployment_object"] != deployment["object"] or execution_claim[
        "execution_claim"
    ]["intent_object"] != intent["object"] or execution_claim[
        "execution_claim"
    ]["launch_claim_object"] != launch_claim["object"]:
        raise TransferTransportError("terminal transport chain differs")
    expected_before = _prior_remote_uris(phase) | {
        _phase_uri(phase, "intent"), _phase_uri(phase, "launch-claim"),
        _phase_uri(phase, "execution-claim"), PHASE_OUTPUT[phase],
    }
    inventory = _validate_prefix_inventory(
        store, expected=expected_before,
        optional={_phase_uri(phase, "terminal")},
    )
    terminal_uri = _phase_uri(phase, "terminal")
    before_inventory = {
        uri: metadata for uri, metadata in inventory.items()
        if uri != terminal_uri
    }
    rows = _snapshot_inventory(store, before_inventory)
    result_meta = next(row for row in rows if row["uri"] == PHASE_OUTPUT[phase])
    result, observed_result = _load_pinned(
        store, result_meta, uri=PHASE_OUTPUT[phase], label=f"{phase} result",
    )
    freeze_manifest = None
    if phase == "full":
        freeze_manifest = _load_freeze_wrapper(out, store)["manifest"]
    decision = _validate_result(
        result, phase=phase, claim=claim["claim"], intent=intent["intent"],
        freeze_manifest=freeze_manifest,
    )
    inventory_sha = sha256(_canonical_json(rows)).hexdigest()
    execution_raw = _canonical_json(execution_metadata)

    def make() -> dict[str, Any]:
        return {
            "version": "a7-production-law-transfer-terminal-v1",
            "run_id": RUN_ID,
            "phase": phase,
            "deployment_object": deployment["object"],
            "intent_object": intent["object"],
            "launch_claim_object": launch_claim["object"],
            "execution_claim_object": execution_claim["object"],
            "execution": execution,
            "execution_metadata_sha256": sha256(execution_raw).hexdigest(),
            "result_object": observed_result,
            "prefix_inventory_before_terminal_sha256": inventory_sha,
            "decision": decision,
            "completed_at": _now(),
            "uses_realized_outcomes": False,
            "actual_score_query_executed": False,
            "historical_outcome_lease_acquired": False,
            "production_mutated": False,
            "retry_licensed": False,
            "licenses": decision["licenses"],
        }

    terminal, obj = _publish_recoverable(
        store, uri=terminal_uri, make_body=make,
        validate=lambda value: _validate_terminal_body(value, phase=phase),
    )
    fixed_terminal = {
        "deployment_object": deployment["object"],
        "intent_object": intent["object"],
        "launch_claim_object": launch_claim["object"],
        "execution_claim_object": execution_claim["object"],
        "execution": execution,
        "execution_metadata_sha256": sha256(execution_raw).hexdigest(),
        "result_object": observed_result,
        "prefix_inventory_before_terminal_sha256": inventory_sha,
        "decision": decision,
    }
    if any(terminal.get(key) != expected for key, expected in fixed_terminal.items()):
        raise TransferTransportError("existing terminal inputs differ")
    final_inventory = _validate_prefix_inventory(
        store, expected=expected_before | {terminal_uri},
    )
    del final_inventory
    wrapper = {"terminal": terminal, "object": obj}
    _write_or_validate(
        _phase_path(out, phase, "terminal-receipt.json"),
        _canonical_json(wrapper), label=f"{phase} terminal receipt",
    )

    harvest = _phase_path(out, phase, "harvest")
    pending = _phase_path(out, phase, ".harvest.pending")
    if harvest.exists():
        _validate_harvest_directory(harvest, wrapper=wrapper)
        return wrapper
    if pending.exists():
        _validate_harvest_directory(pending, wrapper=wrapper)
        pending.rename(harvest)
        return wrapper
    pending.mkdir(parents=True)
    (pending / "execution.json").write_bytes(execution_raw)
    (pending / "result-metadata.json").write_bytes(_canonical_json(observed_result))
    (pending / "result.json").write_bytes(_canonical_json(result))
    (pending / "terminal-receipt.json").write_bytes(_canonical_json(wrapper))
    ledger_names = (
        "execution.json", "result-metadata.json", "result.json",
        "terminal-receipt.json",
    )
    ledger = "".join(
        f"{_sha_file(pending / name)}  {name}\n" for name in ledger_names
    )
    (pending / "harvest.sha256").write_text(ledger, encoding="utf-8")
    _validate_harvest_directory(pending, wrapper=wrapper)
    pending.rename(harvest)
    return wrapper


def _validate_harvest_directory(
    path: Path, *, wrapper: Mapping[str, Any],
) -> None:
    expected = {
        "execution.json", "result-metadata.json", "result.json",
        "terminal-receipt.json", "harvest.sha256",
    }
    if not path.is_dir() or {item.name for item in path.iterdir()} != expected or \
            (path / "terminal-receipt.json").read_bytes() != _canonical_json(wrapper):
        raise TransferTransportError("strict harvest directory differs")
    rows = (path / "harvest.sha256").read_text(encoding="utf-8").splitlines()
    observed: set[str] = set()
    for row in rows:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/]+)", row)
        if match is None or match.group(2) in observed or _sha_file(
            path / match.group(2)
        ) != match.group(1):
            raise TransferTransportError("strict harvest ledger differs")
        observed.add(match.group(2))
    if observed != expected - {"harvest.sha256"}:
        raise TransferTransportError("strict harvest ledger population differs")


def close_terminal_failure(
    *,
    phase: str,
    out: Path,
    execution_metadata: Mapping[str, Any],
    reader: a7_transport._StorageReader | None = None,
) -> dict[str, Any]:
    _validate_predecessor()
    intent = _load_wrapper(
        _phase_path(out, phase, "intent-receipt.json"),
        label=f"{phase} intent", body_key="intent",
        uri=_phase_uri(phase, "intent"),
        validate_body=lambda value: _validate_intent_body(value, phase=phase),
    )
    claim = _load_wrapper(
        _phase_path(out, phase, "execution-claim-receipt.json"),
        label=f"{phase} execution claim", body_key="execution_claim",
        uri=_phase_uri(phase, "execution-claim"),
        validate_body=lambda value: _validate_execution_claim_body(
            value, phase=phase,
        ),
    )
    name = claim["execution_claim"]["execution_name"]
    _validate_execution_contract(
        execution_metadata, phase=phase, intent=intent["intent"],
        execution_name=name, require_terminal=False,
    )
    metadata, _spec, task = _execution_parts(execution_metadata)
    status = execution_metadata.get("status", {})
    completed = [
        row for row in status.get("conditions", [])
        if isinstance(row, dict) and row.get("type") == "Completed"
    ] if isinstance(status, dict) else []
    counters = {
        key: status.get(field, 0)
        for key, field in (
            ("succeeded", "succeededCount"), ("failed", "failedCount"),
            ("cancelled", "cancelledCount"), ("retried", "retriedCount"),
        )
    }
    if metadata.get("name") != name or len(completed) != 1 or completed[0].get(
        "status"
    ) != "False" or task.get("maxRetries") != 0 or any(
        type(count) is not int or count < 0 for count in counters.values()
    ) or counters["succeeded"] != 0 or counters["retried"] != 0 or (
        counters["failed"] + counters["cancelled"]
    ) != 1 or not status.get("completionTime"):
        raise TransferTransportError("execution is not exact terminal failure")
    body = {
        "version": "a7-production-law-transfer-terminal-failure-v1",
        "run_id": RUN_ID,
        "phase": phase,
        "execution_name": name,
        "execution_metadata_sha256": sha256(
            _canonical_json(execution_metadata)
        ).hexdigest(),
        "intent_object": intent["object"],
        "execution_claim_object": claim["object"],
        "status": "closed-terminal-failed-no-retry",
        "result_body_read": False,
        "retry_licensed": False,
        "uses_realized_outcomes": False,
        "licenses": science.licenses(),
    }
    store = reader or _reader()
    observed, obj = _publish_recoverable(
        store, uri=_phase_uri(phase, "failure"), make_body=lambda: body,
        validate=lambda value: value if value == body else (
            (_ for _ in ()).throw(
                TransferTransportError("terminal failure closure differs")
            )
        ),
    )
    wrapper = {"failure": observed, "object": obj}
    _write_or_validate(
        _phase_path(out, phase, "terminal-failure.json"),
        _canonical_json(wrapper), label=f"{phase} terminal failure",
    )
    return wrapper


def create_freeze(
    *,
    out: Path,
    reader: a7_transport._StorageReader | None = None,
) -> dict[str, Any]:
    predecessor = _validate_predecessor()
    store = reader or _reader()
    claim = _load_wrapper(
        out / "job-claim-receipt.json", label="job claim", body_key="claim",
        uri=JOB_CLAIM_URI, validate_body=_validate_claim_body,
    )
    claim = _load_live_wrapper(
        store, claim, body_key="claim", uri=JOB_CLAIM_URI, label="job claim",
        validate_body=_validate_claim_body,
    )
    smoke = _load_terminal_wrapper(out, "smoke", store)
    support = _load_terminal_wrapper(out, "support", store)
    if support["terminal"]["decision"].get("support_passed") is not True:
        raise TransferTransportError("unsupported support forbids freeze")
    query = _query_hashes_from_terminal(smoke["terminal"])
    if _query_hashes_from_terminal(support["terminal"]) != query:
        raise TransferTransportError("freeze preflight query hashes differ")
    expected_before = {JOB_CLAIM_URI, DEPLOYMENT_URI}
    expected_before.update(_phase_remote_uris("smoke"))
    expected_before.update(_phase_remote_uris("support"))
    _validate_prefix_inventory(
        store, expected=expected_before,
        optional={runner.FREEZE_MANIFEST_URI, FREEZE_RECEIPT_URI},
    )
    manifest = freezer.build_manifest(
        predecessor=predecessor,
        code_sha=claim["claim"]["code_sha"],
        image=claim["claim"]["image"],
        candidate_query_sha256=query["candidates"],
        player_query_sha256=query["players"],
        smoke_object=smoke["terminal"]["result_object"],
        support_object=support["terminal"]["result_object"],
    )

    def validate_manifest(value: dict[str, Any]) -> dict[str, Any]:
        try:
            smoke_obj, support_obj = runner._validate_freeze_manifest(
                value,
                predecessor=predecessor,
                code_sha=claim["claim"]["code_sha"],
                image=claim["claim"]["image"],
                candidate_query_sha256=query["candidates"],
                player_query_sha256=query["players"],
            )
        except Exception as exc:
            raise TransferTransportError("execution freeze differs") from exc
        if smoke_obj != smoke["terminal"]["result_object"] or support_obj != support[
            "terminal"
        ]["result_object"]:
            raise TransferTransportError("execution freeze preflights differ")
        return value

    frozen, raw_manifest_obj = _publish_recoverable(
        store, uri=runner.FREEZE_MANIFEST_URI, make_body=lambda: manifest,
        validate=validate_manifest,
    )
    manifest_obj = {
        key: raw_manifest_obj[key]
        for key in ("uri", "generation", "metageneration", "bytes", "sha256")
    }
    receipt_body = {
        "version": "a7-production-law-transfer-freeze-object-v1",
        "run_id": RUN_ID,
        "manifest_object": manifest_obj,
        "query_sha256": query,
        "support_passed": True,
        "uses_realized_outcomes": False,
        "licenses": science.licenses(),
    }
    observed_receipt, receipt_obj = _publish_recoverable(
        store, uri=FREEZE_RECEIPT_URI, make_body=lambda: receipt_body,
        validate=lambda value: value if value == receipt_body else (
            (_ for _ in ()).throw(
                TransferTransportError("freeze receipt object differs")
            )
        ),
    )
    del observed_receipt
    _validate_prefix_inventory(
        store,
        expected=expected_before | {
            runner.FREEZE_MANIFEST_URI, FREEZE_RECEIPT_URI,
        },
    )
    wrapper = {
        "version": "a7-production-law-transfer-freeze-receipt-v1",
        "manifest": frozen,
        "object": manifest_obj,
        "receipt_object": receipt_obj,
    }
    _write_or_validate(
        out / "freeze-receipt.json", _canonical_json(wrapper),
        label="freeze receipt",
    )
    return wrapper


def canonicalize_external(raw: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise TransferTransportError("canonical external output exists")
    value = _strict_json(raw.read_bytes(), label="external JSON")
    if not isinstance(value, dict) and not isinstance(value, list):
        raise TransferTransportError("external JSON root differs")
    _write_or_validate(
        output, _canonical_json(value), label="canonical external JSON",
    )
    return {"output": str(output)}


def validate_phase_complete(
    *, phase: str, out: Path,
) -> dict[str, Any]:
    _validate_predecessor()
    store = _reader()
    wrapper = _load_terminal_wrapper(out, phase, store)
    _validate_harvest_directory(
        _phase_path(out, phase, "harvest"), wrapper=wrapper,
    )
    return wrapper


def _json_path(path: Path, *, label: str) -> Any:
    if path.is_symlink() or not path.is_file():
        raise TransferTransportError(f"{label} is absent")
    raw = path.read_bytes()
    value = _strict_json(raw, label=label)
    if raw != _canonical_json(value):
        raise TransferTransportError(f"{label} is not canonical")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-predecessor")

    canonical = sub.add_parser("canonicalize-external-json")
    canonical.add_argument("--raw", type=Path, required=True)
    canonical.add_argument("--output", type=Path, required=True)

    claim = sub.add_parser("claim-job")
    claim.add_argument("--code-sha", required=True)
    claim.add_argument("--image", required=True)
    claim.add_argument("--build-id", required=True)
    claim.add_argument("--build-metadata", type=Path, required=True)
    claim.add_argument("--job-before", type=Path, required=True)
    claim.add_argument("--executions-before", type=Path, required=True)
    claim.add_argument("--schedulers-before", type=Path, required=True)
    claim.add_argument("--receipt", type=Path, required=True)

    deploy = sub.add_parser("prepare-deployment")
    deploy.add_argument("--claim", type=Path, required=True)
    deploy.add_argument("--job-after", type=Path, required=True)
    deploy.add_argument("--executions-after", type=Path, required=True)
    deploy.add_argument("--schedulers-after", type=Path, required=True)
    deploy.add_argument("--receipt", type=Path, required=True)

    intent = sub.add_parser("create-phase-intent")
    intent.add_argument("--phase", choices=PHASES, required=True)
    intent.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    intent.add_argument("--deployment", type=Path, required=True)
    intent.add_argument("--job-current", type=Path, required=True)
    intent.add_argument("--executions-current", type=Path, required=True)
    intent.add_argument("--schedulers-current", type=Path, required=True)

    launch = sub.add_parser("create-launch-claim")
    launch.add_argument("--phase", choices=PHASES, required=True)
    launch.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    launch.add_argument("--job-current", type=Path, required=True)
    launch.add_argument("--executions-current", type=Path, required=True)
    launch.add_argument("--schedulers-current", type=Path, required=True)

    register = sub.add_parser("register-execution")
    register.add_argument("--phase", choices=PHASES, required=True)
    register.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    register.add_argument("--execute-response", type=Path, required=True)

    harvest = sub.add_parser("harvest")
    harvest.add_argument("--phase", choices=PHASES, required=True)
    harvest.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    harvest.add_argument("--execution", type=Path, required=True)

    failure = sub.add_parser("close-terminal-failure")
    failure.add_argument("--phase", choices=PHASES, required=True)
    failure.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    failure.add_argument("--execution", type=Path, required=True)

    freeze = sub.add_parser("freeze")
    freeze.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)

    complete = sub.add_parser("validate-phase-complete")
    complete.add_argument("--phase", choices=PHASES, required=True)
    complete.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "validate-predecessor":
        result = _validate_predecessor()
    elif args.command == "canonicalize-external-json":
        result = canonicalize_external(args.raw, args.output)
    elif args.command == "claim-job":
        result = create_job_claim(
            code_sha=args.code_sha, image=args.image, build_id=args.build_id,
            build_metadata=_json_path(
                args.build_metadata, label="build metadata",
            ),
            job_before=_json_path(args.job_before, label="job before"),
            executions_before=_json_path(
                args.executions_before, label="executions before",
            ),
            schedulers_before=_json_path(
                args.schedulers_before, label="schedulers before",
            ),
            receipt_path=args.receipt,
        )
    elif args.command == "prepare-deployment":
        result = prepare_deployment(
            claim_path=args.claim,
            job_after=_json_path(args.job_after, label="job after"),
            executions_after=_json_path(
                args.executions_after, label="executions after",
            ),
            schedulers_after=_json_path(
                args.schedulers_after, label="schedulers after",
            ),
            receipt_path=args.receipt,
        )
    elif args.command == "create-phase-intent":
        result = create_phase_intent(
            phase=args.phase, out=args.output_dir,
            deployment_path=args.deployment,
            job_current=_json_path(args.job_current, label="job current"),
            executions_current=_json_path(
                args.executions_current, label="executions current",
            ),
            schedulers_current=_json_path(
                args.schedulers_current, label="schedulers current",
            ),
        )
    elif args.command == "create-launch-claim":
        result = create_launch_claim(
            phase=args.phase, out=args.output_dir,
            job_current=_json_path(args.job_current, label="job current"),
            executions_current=_json_path(
                args.executions_current, label="executions current",
            ),
            schedulers_current=_json_path(
                args.schedulers_current, label="schedulers current",
            ),
        )
    elif args.command == "register-execution":
        result = register_execution(
            phase=args.phase, out=args.output_dir,
            execute_response=_json_path(
                args.execute_response, label="execute response",
            ),
        )
    elif args.command == "harvest":
        result = harvest_phase(
            phase=args.phase, out=args.output_dir,
            execution_metadata=_json_path(
                args.execution, label="execution metadata",
            ),
        )
    elif args.command == "close-terminal-failure":
        result = close_terminal_failure(
            phase=args.phase, out=args.output_dir,
            execution_metadata=_json_path(
                args.execution, label="execution metadata",
            ),
        )
    elif args.command == "freeze":
        result = create_freeze(out=args.output_dir)
    else:
        result = validate_phase_complete(phase=args.phase, out=args.output_dir)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
