#!/usr/bin/env python3
"""Fail-closed operator-side transport for LR8 later-period construction.

This file owns Cloud Run metadata validation and terminal-first GCS harvest.
It never queries BigQuery, acquires a historical-outcome lease, or scores a
lineup.  The scientific source/construction work remains in
``run_lr8_later_period_source.py`` and its I/O-free research module.
"""

from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
import shlex
import sys
from typing import Any, Final, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from nfl_dfs.research import lr8_label_fit_adapter as fit_adapter  # noqa: E402
from nfl_dfs.research import lr8_later_period_source as later  # noqa: E402


PROJECT: Final = "nfl-predictions-503414"
REGION: Final = "us-central1"
JOB: Final = "atlas-md-prefix-r4-smoke"
JOB_UID: Final = "51545eb0-59e4-424e-91c9-98dd318285f4"
SERVICE_ACCOUNT: Final = (
    "817589974517-compute@developer.gserviceaccount.com"
)
ATTEMPT_ID: Final = "20260821-lr8-later-period-source-v1"
PREFIX: Final = (
    "gs://nfl-predictions-503414-raw/research/lr8-later-period/"
    + ATTEMPT_ID
)
DEFAULT_OUT: Final = (
    ROOT / "reports/lr8-later-period-source-runs" / ATTEMPT_ID
)
SOURCE_URI: Final = f"{PREFIX}/later-period-source-freeze.json"
SMOKE_URI: Final = f"{PREFIX}/smoke/2023-w01.json"
SMOKE_EXECUTION_METADATA_URI: Final = (
    f"{PREFIX}/smoke-authority/execution-metadata.json"
)
SMOKE_FINISH_LEDGER_URI: Final = (
    f"{PREFIX}/smoke-authority/finish-ledger.txt"
)
SMOKE_TERMINAL_URI: Final = (
    f"{PREFIX}/smoke-authority/smoke-terminal.json"
)
CELL_MANIFEST_URI: Final = f"{PREFIX}/terminal-cell-manifest.json"
BOOK_FREEZE_URI: Final = f"{PREFIX}/later-period-108-book-freeze.json"
DISABLED_SCRIPT: Final = (
    "echo LR8_LATER_PERIOD_TRANSPORT_DISABLED >&2; exit 78"
)
CPU: Final = "8"
MEMORY: Final = "32Gi"
TIMEOUT_SECONDS: Final = 21600
CONTRACT_VERSION: Final = "lr8-later-period-cloud-transport-v1"
INPUT_VERSION: Final = "lr8-later-period-transport-inputs-v1"
SOURCE_COMPLETION_VERSION: Final = "lr8-later-source-completion-v1"
SMOKE_COMPLETION_VERSION: Final = "lr8-later-smoke-completion-v1"
CELL_COMPLETION_VERSION: Final = "lr8-later-cell-completion-v1"
FINAL_COMPLETION_VERSION: Final = "lr8-later-book-freeze-completion-v1"
REQUIRED_BUILD_SMOKES: Final = (
    "python scripts/run_lr8_later_period_source.py --help >/dev/null",
    "python scripts/finish_lr8_later_period_source_transport.py --help >/dev/null",
    "bash -n scripts/cloud_lr8_later_period_source.sh",
    "bash -n scripts/watch_lr8_later_period_source_queue.sh",
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_BUILD = re.compile(r"[0-9A-Za-z-]{8,80}")
_GENERATION = re.compile(r"[1-9][0-9]*")
_IMAGE = re.compile(
    r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
    r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}"
)
_EXECUTION = re.compile(re.escape(JOB) + r"-[a-z0-9]{5}")


class LR8LaterTransportError(RuntimeError):
    """The LR8 later-period transport failed closed."""


def canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LR8LaterTransportError("value is not canonical JSON") from exc


def strict_json_value(raw: bytes, *, label: str) -> object:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite constant {value}")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate key {key}")
            value[key] = item
        return value

    try:
        value = json.loads(
            raw, object_pairs_hook=unique, parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise LR8LaterTransportError(f"{label} is not strict JSON") from exc
    return value


def strict_json(raw: bytes, *, label: str) -> dict[str, object]:
    value = strict_json_value(raw, label=label)
    if not isinstance(value, dict):
        raise LR8LaterTransportError(f"{label} must be a JSON object")
    return value


def _load(path: Path, *, label: str) -> dict[str, object]:
    try:
        return strict_json(path.read_bytes(), label=label)
    except OSError as exc:
        raise LR8LaterTransportError(f"{label} is unreadable") from exc


def _load_any(path: Path, *, label: str) -> object:
    try:
        return strict_json_value(path.read_bytes(), label=label)
    except OSError as exc:
        raise LR8LaterTransportError(f"{label} is unreadable") from exc


def _write_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise LR8LaterTransportError(
                f"immutable output is unreadable: {path}"
            ) from exc
        if path.is_symlink() or not path.is_file() or existing != raw:
            raise LR8LaterTransportError(
                f"immutable output differs: {path}"
            )
        return
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError as exc:
        try:
            existing = path.read_bytes()
        except OSError as read_exc:
            raise LR8LaterTransportError(
                f"immutable output is unreadable: {path}"
            ) from read_exc
        if path.is_symlink() or not path.is_file() or existing != raw:
            raise LR8LaterTransportError(
                f"immutable output differs: {path}"
            ) from exc


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _digest(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise LR8LaterTransportError(f"{label} must be a lowercase SHA-256")
    return value


def _generation(value: object, *, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise LR8LaterTransportError(f"{label} generation differs")
    result = str(value)
    if _GENERATION.fullmatch(result) is None:
        raise LR8LaterTransportError(f"{label} generation differs")
    return result


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise LR8LaterTransportError(f"{label} must be an exact integer")
    return value


def _receipt(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "uri", "generation", "sha256", "bytes",
    }:
        raise LR8LaterTransportError(f"{label} receipt fields differ")
    uri = value["uri"]
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        raise LR8LaterTransportError(f"{label} URI differs")
    return {
        "uri": uri,
        "generation": _generation(value["generation"], label=label),
        "sha256": _digest(value["sha256"], label=f"{label} SHA-256"),
        "bytes": _exact_int(value["bytes"], label=f"{label} bytes", minimum=1),
    }


def _inventory_row(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "uri", "generation", "bytes",
    }:
        raise LR8LaterTransportError(f"{label} inventory fields differ")
    uri = value["uri"]
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        raise LR8LaterTransportError(f"{label} inventory URI differs")
    return {
        "uri": uri,
        "generation": _generation(value["generation"], label=label),
        "bytes": _exact_int(value["bytes"], label=f"{label} bytes", minimum=1),
    }


def _parts(uri: str) -> tuple[str, str]:
    bucket, marker, name = uri.removeprefix("gs://").partition("/")
    if (
        not uri.startswith("gs://") or not bucket or not marker or not name
        or ".." in name.split("/")
    ):
        raise LR8LaterTransportError("GCS URI differs")
    return bucket, name


def cell_uri(index: int) -> str:
    index = _exact_int(index, label="cell index")
    if index >= len(later.EXPECTED_SLATE_KEYS):
        raise LR8LaterTransportError("cell index differs")
    season, week = later.EXPECTED_SLATE_KEYS[index]
    # The scientific runner derives its CBC-evidence prefix from the result
    # object's parent.  A distinct cell directory therefore prevents two
    # otherwise content-identical pricing requests from colliding at a shared
    # create-once evidence URI.
    return (
        f"{PREFIX}/cells/cell-{index:02d}-{season}-w{week:02d}/cell.json"
    )


class Storage:
    """Generation-pinned GCS reads and create-once operator receipts."""

    def __init__(self) -> None:
        from google.cloud import storage

        self.client = storage.Client(project=PROJECT)

    def inventory(self, prefix: str) -> list[dict[str, object]]:
        bucket_name, name_prefix = _parts(prefix)
        rows = []
        for blob in self.client.list_blobs(bucket_name, prefix=name_prefix):
            if blob.generation is None or blob.size is None:
                blob.reload()
            rows.append({
                "uri": f"gs://{bucket_name}/{blob.name}",
                "generation": str(blob.generation),
                "bytes": int(blob.size),
            })
        return sorted(rows, key=lambda row: str(row["uri"]))

    def load(self, receipt: Mapping[str, object]) -> bytes:
        expected = _receipt(receipt, label="generation-pinned object")
        bucket_name, name = _parts(str(expected["uri"]))
        generation = int(str(expected["generation"]))
        try:
            blob = self.client.bucket(bucket_name).blob(
                name, generation=generation,
            )
            blob.reload(if_generation_match=generation)
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise LR8LaterTransportError(
                "generation-pinned object read failed"
            ) from exc
        if (
            str(blob.generation) != str(expected["generation"])
            or len(raw) != expected["bytes"]
            or _sha(raw) != expected["sha256"]
        ):
            raise LR8LaterTransportError("generation-pinned object bytes differ")
        return raw

    def load_inventory(self, row: Mapping[str, object]) -> tuple[dict[str, object], bytes]:
        item = _inventory_row(row, label="GCS object")
        bucket_name, name = _parts(str(item["uri"]))
        generation = int(str(item["generation"]))
        try:
            blob = self.client.bucket(bucket_name).blob(
                name, generation=generation,
            )
            blob.reload(if_generation_match=generation)
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise LR8LaterTransportError(
                "generation-pinned inventory read failed"
            ) from exc
        receipt = {
            "uri": item["uri"],
            "generation": str(blob.generation),
            "sha256": _sha(raw),
            "bytes": len(raw),
        }
        if receipt["generation"] != item["generation"] or receipt["bytes"] != item["bytes"]:
            raise LR8LaterTransportError("inventory object identity changed")
        return receipt, raw

    def publish(self, uri: str, raw: bytes) -> dict[str, object]:
        bucket_name, name = _parts(uri)
        bucket = self.client.bucket(bucket_name)
        try:
            blob = bucket.blob(name)
            blob.upload_from_string(raw, if_generation_match=0)
            generation = int(str(blob.generation))
        except Exception as upload_exc:
            # A process may have died after the create-once write but before
            # retaining its receipt.  Recover only the exact current bytes;
            # any collision, missing object, or unreadable generation remains
            # a hard failure and never becomes an overwrite/retry.
            try:
                current = bucket.blob(name)
                current.reload()
                generation = int(str(current.generation))
                pinned = bucket.blob(name, generation=generation)
                pinned.reload(if_generation_match=generation)
                reopened = pinned.download_as_bytes(
                    if_generation_match=generation,
                )
            except Exception as recover_exc:
                raise LR8LaterTransportError(
                    "create-once publication failed"
                ) from recover_exc
            if reopened != raw:
                raise LR8LaterTransportError(
                    "create-once existing bytes differ"
                ) from upload_exc
        else:
            try:
                pinned = bucket.blob(
                    name, generation=generation,
                )
                pinned.reload(if_generation_match=generation)
                reopened = pinned.download_as_bytes(
                    if_generation_match=generation,
                )
            except Exception as exc:
                raise LR8LaterTransportError(
                    "create-once publication reopen failed"
                ) from exc
        receipt = {
            "uri": uri,
            "generation": str(pinned.generation),
            "sha256": _sha(reopened),
            "bytes": len(reopened),
        }
        if reopened != raw:
            raise LR8LaterTransportError("create-once reopened bytes differ")
        return _receipt(receipt, label="published object")


def _job_parts(value: Mapping[str, object]) -> tuple[Mapping[str, object], Mapping[str, object]]:
    try:
        outer = value["spec"]["template"]["spec"]
        task = outer["template"]["spec"]
    except (KeyError, TypeError) as exc:
        raise LR8LaterTransportError("Cloud Run job spec differs") from exc
    if not isinstance(outer, Mapping) or not isinstance(task, Mapping):
        raise LR8LaterTransportError("Cloud Run job spec differs")
    return outer, task


def _job_identity(value: Mapping[str, object]) -> None:
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping) or (
        metadata.get("name"), metadata.get("uid")
    ) != (JOB, JOB_UID):
        raise LR8LaterTransportError("reused Cloud Run job identity differs")


def _job_generation(value: Mapping[str, object]) -> str:
    metadata = value.get("metadata")
    generation = metadata.get("generation") if isinstance(metadata, Mapping) else None
    return _generation(generation, label="Cloud Run job")


def _job_spec_sha(value: Mapping[str, object]) -> str:
    spec = value.get("spec")
    if not isinstance(spec, Mapping) or not spec:
        raise LR8LaterTransportError("Cloud Run job spec differs")
    return _sha(canonical_json(spec))


def configured_env(*, image: str, code_sha: str, build_id: str) -> dict[str, str]:
    return {
        "ANALYSIS_IMAGE": image,
        "CODE_SHA": code_sha,
        "LR8_BUILD_ID": build_id,
        "LR8_LATER_PERIOD_ENABLED": "1",
        "LR8_LATER_PERIOD_TRANSPORT_ATTEMPT": ATTEMPT_ID,
    }


def validate_configured_job(
    value: Mapping[str, object], *, contract: Mapping[str, object],
) -> None:
    normalized = validate_contract(contract)
    _job_identity(value)
    if (
        _job_generation(value) != normalized["job_generation"]
        or _job_spec_sha(value) != normalized["job_spec_sha256"]
    ):
        raise LR8LaterTransportError("configured job generation/spec differs")
    outer, task = _job_parts(value)
    containers = task.get("containers")
    if not isinstance(containers, list) or len(containers) != 1 or not isinstance(
        containers[0], Mapping
    ):
        raise LR8LaterTransportError("configured job container differs")
    container = containers[0]
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, Mapping) or set(row) != {"name", "value"}
        for row in env_rows
    ):
        raise LR8LaterTransportError("configured job environment differs")
    env = {str(row["name"]): row["value"] for row in env_rows}
    if len(env) != len(env_rows) or (
        _exact_int(outer.get("taskCount"), label="job task count") != 1
        or _exact_int(outer.get("parallelism"), label="job parallelism") != 1
        or _exact_int(task.get("maxRetries"), label="job max retries") != 0
        or container.get("image") != normalized["image"]
        or container.get("command") != ["bash"]
        or container.get("args") != ["-ceu", DISABLED_SCRIPT]
        or env != normalized["env"]
        or task.get("serviceAccountName") != SERVICE_ACCOUNT
        or container.get("resources", {}).get("limits")
        != {"cpu": CPU, "memory": MEMORY}
        or task.get("timeoutSeconds") != TIMEOUT_SECONDS
        or container.get("workingDir", "") != ""
        or container.get("volumeMounts", []) != []
        or task.get("volumes", []) != []
        or container.get("startupProbe") not in (None, {})
    ):
        raise LR8LaterTransportError("configured job executable contract differs")


def validate_build(
    value: object, *, build_id: str, code_sha: str, image: str,
) -> None:
    if (
        not isinstance(value, Mapping) or _BUILD.fullmatch(build_id) is None
        or _COMMIT.fullmatch(code_sha) is None or _IMAGE.fullmatch(image) is None
        or value.get("id") != build_id or value.get("status") != "SUCCESS"
    ):
        raise LR8LaterTransportError("build identity differs")
    try:
        requested = value["source"]["gitSource"]["revision"]
        resolved = value["sourceProvenance"]["resolvedGitSource"]["revision"]
    except (KeyError, TypeError) as exc:
        raise LR8LaterTransportError("direct-Git build provenance is absent") from exc
    if requested != code_sha or resolved != code_sha:
        raise LR8LaterTransportError("direct-Git build source differs")
    digest = image.rsplit("@", 1)[1]
    images = value.get("results", {}).get("images", [])
    if not isinstance(images, list) or not any(
        isinstance(row, Mapping) and row.get("digest") == digest for row in images
    ):
        raise LR8LaterTransportError("build image digest differs")
    steps = value.get("steps")
    if not isinstance(steps, list) or not steps or any(
        not isinstance(row, Mapping) or row.get("status") != "SUCCESS"
        or int(row.get("exitCode", 0) or 0) != 0 for row in steps
    ):
        raise LR8LaterTransportError("build steps are not all successful")
    rendered = "\n".join(
        str(item)
        for row in steps
        for item in (row.get("args", []) if isinstance(row, Mapping) else [])
    )
    if any(marker not in rendered for marker in REQUIRED_BUILD_SMOKES):
        raise LR8LaterTransportError(
            "later-period build integration smokes are absent"
        )


def _completion_state(value: Mapping[str, object]) -> str:
    status = value.get("status")
    if not isinstance(status, Mapping):
        raise LR8LaterTransportError("execution status differs")
    conditions = status.get("conditions", [])
    if not isinstance(conditions, list):
        raise LR8LaterTransportError("execution conditions differ")
    completed = [
        row for row in conditions if isinstance(row, Mapping)
        and row.get("type") == "Completed"
    ]
    if not completed:
        return "Unknown"
    if len(completed) != 1 or completed[0].get("status") not in {
        "Unknown", "True", "False",
    }:
        raise LR8LaterTransportError("execution Completed condition differs")
    return str(completed[0]["status"])


def _validate_idle(executions: object, *, allowed_active: set[str] | None = None) -> None:
    if not isinstance(executions, list):
        raise LR8LaterTransportError("execution census differs")
    allowed = set() if allowed_active is None else allowed_active
    for row in executions:
        if not isinstance(row, Mapping):
            raise LR8LaterTransportError("execution census row differs")
        if _completion_state(row) == "Unknown":
            name = row.get("metadata", {}).get("name")
            if name not in allowed:
                raise LR8LaterTransportError("reused job has an unbound active execution")


def _validate_unscheduled(schedulers: object) -> None:
    if not isinstance(schedulers, list):
        raise LR8LaterTransportError("scheduler census differs")
    needle = f"/jobs/{JOB}:run"
    for row in schedulers:
        if not isinstance(row, Mapping):
            raise LR8LaterTransportError("scheduler census row differs")
        target = row.get("httpTarget", {})
        if isinstance(target, Mapping) and needle in str(target.get("uri", "")):
            raise LR8LaterTransportError("scheduler targets reused job")


def validate_reuse(
    *, job_metadata: Mapping[str, object], executions: object,
    schedulers: object, inventory: object,
) -> None:
    _job_identity(job_metadata)
    _job_generation(job_metadata)
    _job_spec_sha(job_metadata)
    _validate_idle(executions)
    _validate_unscheduled(schedulers)
    if inventory != []:
        raise LR8LaterTransportError("later-period result prefix is not empty")


def validate_inputs(
    *, base_source: Mapping[str, object], fit_freeze: Mapping[str, object],
    fit_freeze_sha256: str, anatomy_artifact_sha256: str,
    storage: Storage | None = None,
) -> dict[str, object]:
    base_receipt = _receipt(base_source, label="base source lock")
    fit_receipt = _receipt(fit_freeze, label="label-fit freeze")
    fit_sha = _digest(fit_freeze_sha256, label="label-fit freeze hash")
    anatomy_sha = _digest(
        anatomy_artifact_sha256, label="anatomy artifact hash",
    )
    expected_base = {
        "uri": later.BASE_SOURCE_URI,
        "generation": later.BASE_SOURCE_GENERATION,
        "sha256": later.BASE_SOURCE_SHA256,
        "bytes": later.BASE_SOURCE_BYTES,
    }
    if base_receipt != expected_base:
        raise LR8LaterTransportError("base source-lock object identity differs")
    if base_receipt["uri"] == fit_receipt["uri"] or any(
        str(row["uri"]).startswith(PREFIX + "/")
        for row in (base_receipt, fit_receipt)
    ):
        raise LR8LaterTransportError("input/output object URIs alias")
    store = Storage() if storage is None else storage
    base_body = strict_json(store.load(base_receipt), label="base source lock")
    if (
        base_body.get("version") != later.BASE_SOURCE_VERSION
        or base_body.get("run_id") != later.BASE_SOURCE_RUN_ID
        or base_body.get("artifact_count") != later.EXPECTED_ARTIFACTS
        or base_body.get("slates") != len(later.EXPECTED_SLATE_KEYS)
        or base_body.get("uses_realized_outcomes") is not False
        or base_body.get("candidate_or_lineup_scores_read") is not False
    ):
        raise LR8LaterTransportError("base source-lock identity differs")
    # Reuse the scientific module's complete 270-receipt validation.
    later._artifact_receipts(base_body)  # noqa: SLF001
    fit_body = strict_json(store.load(fit_receipt), label="label-fit freeze")
    try:
        validated_fit = fit_adapter.validate_label_fit_freeze(
            fit_body, expected_freeze_sha256=fit_sha,
        )
    except Exception as exc:
        raise LR8LaterTransportError("label-fit freeze validation failed") from exc
    if validated_fit.get("anatomy_artifact_sha256") != anatomy_sha:
        raise LR8LaterTransportError("anatomy artifact identity differs")
    result: dict[str, object] = {
        "schema": INPUT_VERSION,
        "base_source_object": base_receipt,
        "fit_freeze_object": fit_receipt,
        "fit_freeze_sha256": fit_sha,
        "anatomy_artifact_sha256": anatomy_sha,
        "base_source_reopened": True,
        "fit_freeze_reopened": True,
        "uses_realized_later_period_outcomes": False,
        "historical_outcome_lease_acquired": False,
    }
    result["validation_sha256"] = _sha(canonical_json(result))
    return result


def create_contract(
    *, job_metadata: Mapping[str, object], input_validation: Mapping[str, object],
    code_sha: str, build_id: str, image: str,
) -> dict[str, object]:
    if (
        _COMMIT.fullmatch(code_sha) is None or _BUILD.fullmatch(build_id) is None
        or _IMAGE.fullmatch(image) is None
    ):
        raise LR8LaterTransportError("contract code/build/image differs")
    inputs = validate_input_summary(input_validation)
    _job_identity(job_metadata)
    contract: dict[str, object] = {
        "schema": CONTRACT_VERSION,
        "attempt_id": ATTEMPT_ID,
        "project": PROJECT,
        "region": REGION,
        "job": JOB,
        "job_uid": JOB_UID,
        "job_generation": _job_generation(job_metadata),
        "job_spec_sha256": _job_spec_sha(job_metadata),
        "code_sha": code_sha,
        "build_id": build_id,
        "image": image,
        "service_account": SERVICE_ACCOUNT,
        "resources": {"cpu": CPU, "memory": MEMORY},
        "timeout_seconds": TIMEOUT_SECONDS,
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "default_command": ["bash"],
        "default_args": ["-ceu", DISABLED_SCRIPT],
        "env": configured_env(image=image, code_sha=code_sha, build_id=build_id),
        "prefix": PREFIX,
        "source_uri": SOURCE_URI,
        "smoke_uri": SMOKE_URI,
        "smoke_terminal_uri": SMOKE_TERMINAL_URI,
        "cell_manifest_uri": CELL_MANIFEST_URI,
        "book_freeze_uri": BOOK_FREEZE_URI,
        "inputs": inputs,
        "uses_realized_later_period_outcomes": False,
        "historical_outcome_lease_acquired": False,
        "production_change_licensed": False,
    }
    contract["contract_sha256"] = _sha(canonical_json(contract))
    validate_configured_job(job_metadata, contract=contract)
    return contract


def validate_input_summary(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema", "base_source_object", "fit_freeze_object",
        "fit_freeze_sha256", "anatomy_artifact_sha256",
        "base_source_reopened", "fit_freeze_reopened",
        "uses_realized_later_period_outcomes",
        "historical_outcome_lease_acquired", "validation_sha256",
    }:
        raise LR8LaterTransportError("input validation fields differ")
    body = dict(value)
    digest = body.pop("validation_sha256")
    if _digest(digest, label="input validation hash") != _sha(canonical_json(body)):
        raise LR8LaterTransportError("input validation hash differs")
    if (
        body["schema"] != INPUT_VERSION
        or body["base_source_reopened"] is not True
        or body["fit_freeze_reopened"] is not True
        or body["uses_realized_later_period_outcomes"] is not False
        or body["historical_outcome_lease_acquired"] is not False
    ):
        raise LR8LaterTransportError("input validation identity differs")
    body["base_source_object"] = _receipt(
        body["base_source_object"], label="base source lock",
    )
    body["fit_freeze_object"] = _receipt(
        body["fit_freeze_object"], label="label-fit freeze",
    )
    _digest(body["fit_freeze_sha256"], label="label-fit freeze hash")
    _digest(body["anatomy_artifact_sha256"], label="anatomy artifact hash")
    body["validation_sha256"] = digest
    return body


def validate_contract(value: object) -> dict[str, object]:
    required = {
        "schema", "attempt_id", "project", "region", "job", "job_uid",
        "job_generation", "job_spec_sha256", "code_sha", "build_id",
        "image", "service_account", "resources", "timeout_seconds",
        "task_count", "parallelism", "max_retries", "default_command",
        "default_args", "env", "prefix", "source_uri", "smoke_uri",
        "smoke_terminal_uri", "cell_manifest_uri", "book_freeze_uri",
        "inputs", "uses_realized_later_period_outcomes",
        "historical_outcome_lease_acquired", "production_change_licensed",
        "contract_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise LR8LaterTransportError("transport contract fields differ")
    contract = dict(value)
    digest = contract.pop("contract_sha256")
    if _digest(digest, label="contract hash") != _sha(canonical_json(contract)):
        raise LR8LaterTransportError("transport contract hash differs")
    if (
        contract["schema"] != CONTRACT_VERSION
        or contract["attempt_id"] != ATTEMPT_ID
        or contract["project"] != PROJECT or contract["region"] != REGION
        or contract["job"] != JOB or contract["job_uid"] != JOB_UID
        or _GENERATION.fullmatch(str(contract["job_generation"])) is None
        or _SHA256.fullmatch(str(contract["job_spec_sha256"])) is None
        or _COMMIT.fullmatch(str(contract["code_sha"])) is None
        or _BUILD.fullmatch(str(contract["build_id"])) is None
        or _IMAGE.fullmatch(str(contract["image"])) is None
        or contract["service_account"] != SERVICE_ACCOUNT
        or contract["resources"] != {"cpu": CPU, "memory": MEMORY}
        or contract["timeout_seconds"] != TIMEOUT_SECONDS
        or contract["task_count"] != 1 or contract["parallelism"] != 1
        or contract["max_retries"] != 0
        or contract["default_command"] != ["bash"]
        or contract["default_args"] != ["-ceu", DISABLED_SCRIPT]
        or contract["env"] != configured_env(
            image=str(contract["image"]), code_sha=str(contract["code_sha"]),
            build_id=str(contract["build_id"]),
        )
        or contract["prefix"] != PREFIX or contract["source_uri"] != SOURCE_URI
        or contract["smoke_uri"] != SMOKE_URI
        or contract["smoke_terminal_uri"] != SMOKE_TERMINAL_URI
        or contract["cell_manifest_uri"] != CELL_MANIFEST_URI
        or contract["book_freeze_uri"] != BOOK_FREEZE_URI
        or contract["uses_realized_later_period_outcomes"] is not False
        or contract["historical_outcome_lease_acquired"] is not False
        or contract["production_change_licensed"] is not False
    ):
        raise LR8LaterTransportError("transport contract identity differs")
    contract["inputs"] = validate_input_summary(contract["inputs"])
    contract["contract_sha256"] = digest
    return contract


def _receipt_args(stem: str, value: Mapping[str, object]) -> tuple[str, ...]:
    receipt = _receipt(value, label=stem)
    return (
        f"--{stem}-uri", str(receipt["uri"]),
        f"--{stem}-generation", str(receipt["generation"]),
        f"--{stem}-sha256", str(receipt["sha256"]),
        f"--{stem}-bytes", str(receipt["bytes"]),
    )


def _runtime_args(contract: Mapping[str, object]) -> tuple[str, ...]:
    value = validate_contract(contract)
    return (
        "--execute", "--project", PROJECT, "--run-id", ATTEMPT_ID,
        "--job", JOB, "--code-sha", str(value["code_sha"]),
        "--image", str(value["image"]),
    )


def _command(arguments: Sequence[str]) -> str:
    if any(not isinstance(row, str) or not row for row in arguments):
        raise LR8LaterTransportError("runner argument differs")
    return "exec " + shlex.join(tuple(arguments))


def source_script(contract: Mapping[str, object]) -> str:
    value = validate_contract(contract)
    base = value["inputs"]["base_source_object"]
    return _command((
        "python", "scripts/run_lr8_later_period_source.py", "freeze-source",
        *_runtime_args(value), *_receipt_args("base-source", base),
        "--output-uri", SOURCE_URI,
    ))


def _source_completion(value: object) -> dict[str, object]:
    required = {
        "schema", "attempt_id", "execution", "source_object",
        "source_freeze_sha256", "prefix_receipts",
        "strict_terminal_success", "uses_realized_later_period_outcomes",
        "historical_outcome_lease_acquired",
    }
    if (
        not isinstance(value, Mapping) or set(value) != required
        or value.get("schema") != SOURCE_COMPLETION_VERSION
        or value.get("attempt_id") != ATTEMPT_ID
    ):
        raise LR8LaterTransportError("source completion differs")
    result = dict(value)
    result["execution"] = _execution_summary(
        result.get("execution"), label="source",
    )
    result["source_object"] = _receipt(result.get("source_object"), label="source freeze")
    _digest(result.get("source_freeze_sha256"), label="source freeze hash")
    result["prefix_receipts"] = _prefix_receipts(result.get("prefix_receipts"))
    if (
        result["source_object"]["uri"] != SOURCE_URI
        or result["prefix_receipts"] != [result["source_object"]]
        or result.get("strict_terminal_success") is not True
        or result.get("uses_realized_later_period_outcomes") is not False
        or result.get("historical_outcome_lease_acquired") is not False
    ):
        raise LR8LaterTransportError("source completion identity differs")
    return result


def smoke_script(
    contract: Mapping[str, object], source_completion: Mapping[str, object],
) -> str:
    value = validate_contract(contract)
    source = _source_completion(source_completion)
    fit = value["inputs"]["fit_freeze_object"]
    args = (
        "python", "scripts/run_lr8_later_period_source.py", "construct-cell",
        *_runtime_args(value), "--mode", "smoke", "--cell-index", "0",
        "--evidence-root", "/tmp/lr8-later-smoke-evidence",
        "--output-uri", SMOKE_URI,
        *_receipt_args("source", source["source_object"]),
        "--source-freeze-sha256", str(source["source_freeze_sha256"]),
        *_receipt_args("fit", fit),
        "--fit-freeze-sha256", str(value["inputs"]["fit_freeze_sha256"]),
    )
    return "test ! -e /tmp/lr8-later-smoke-evidence; " + _command(args)


def _smoke_completion(value: object) -> dict[str, object]:
    required = {
        "schema", "attempt_id", "execution", "smoke_object",
        "smoke_cell_sha256", "source_freeze_sha256",
        "anatomy_artifact_sha256", "smoke_terminal",
        "smoke_terminal_object", "smoke_terminal_manifest_sha256",
        "prefix_receipts", "strict_terminal_success",
        "uses_realized_later_period_outcomes",
        "historical_outcome_lease_acquired",
    }
    if (
        not isinstance(value, Mapping) or set(value) != required
        or value.get("schema") != SMOKE_COMPLETION_VERSION
        or value.get("attempt_id") != ATTEMPT_ID
    ):
        raise LR8LaterTransportError("smoke completion differs")
    result = dict(value)
    result["execution"] = _execution_summary(
        result.get("execution"), label="smoke",
    )
    for key, label in (
        ("smoke_object", "smoke"),
        ("smoke_terminal_object", "smoke terminal"),
    ):
        result[key] = _receipt(result.get(key), label=label)
    for key in (
        "smoke_cell_sha256", "smoke_terminal_manifest_sha256",
        "source_freeze_sha256", "anatomy_artifact_sha256",
    ):
        _digest(result.get(key), label=key)
    terminal = result.get("smoke_terminal")
    if not isinstance(terminal, Mapping):
        raise LR8LaterTransportError("smoke terminal body differs")
    if (
        result["smoke_object"]["uri"] != SMOKE_URI
        or result["smoke_terminal_object"]["uri"] != SMOKE_TERMINAL_URI
        or terminal.get("execution_name") != result["execution"]["execution"]
        or terminal.get("terminal_sha256")
        != result["smoke_terminal_manifest_sha256"]
    ):
        raise LR8LaterTransportError("smoke completion object identity differs")
    try:
        result["smoke_terminal"] = later.validate_smoke_terminal(
            terminal,
            terminal_object=result["smoke_terminal_object"],
            smoke_object=result["smoke_object"],
            smoke_sha256=str(result["smoke_cell_sha256"]),
            source_freeze_sha256=str(result["source_freeze_sha256"]),
            anatomy_artifact_sha256=str(result["anatomy_artifact_sha256"]),
        )
    except Exception as exc:
        raise LR8LaterTransportError("smoke terminal body differs") from exc
    result["prefix_receipts"] = _prefix_receipts(result.get("prefix_receipts"))
    prefix_by_uri = {
        str(row["uri"]): row for row in result["prefix_receipts"]
    }
    required_receipts = (
        result["smoke_object"], result["smoke_terminal_object"],
        result["smoke_terminal"]["execution_metadata_object"],
        result["smoke_terminal"]["finish_ledger_object"],
    )
    if any(
        prefix_by_uri.get(str(row["uri"])) != row for row in required_receipts
    ):
        raise LR8LaterTransportError("smoke completion prefix binding differs")
    if (
        result.get("strict_terminal_success") is not True
        or result.get("uses_realized_later_period_outcomes") is not False
        or result.get("historical_outcome_lease_acquired") is not False
    ):
        raise LR8LaterTransportError("smoke completion is not terminal success")
    return result


def cell_script(
    index: int, contract: Mapping[str, object],
    source_completion: Mapping[str, object],
    smoke_completion: Mapping[str, object],
) -> str:
    value = validate_contract(contract)
    source = _source_completion(source_completion)
    smoke = _smoke_completion(smoke_completion)
    _require_receipt_subset(
        smoke["prefix_receipts"], source["prefix_receipts"],
        label="smoke/source",
    )
    fit = value["inputs"]["fit_freeze_object"]
    evidence = f"/tmp/lr8-later-cell-{index:02d}-evidence"
    args = (
        "python", "scripts/run_lr8_later_period_source.py", "construct-cell",
        *_runtime_args(value), "--mode", "full", "--cell-index", str(index),
        "--evidence-root", evidence, "--output-uri", cell_uri(index),
        *_receipt_args("source", source["source_object"]),
        "--source-freeze-sha256", str(source["source_freeze_sha256"]),
        *_receipt_args("fit", fit),
        "--fit-freeze-sha256", str(value["inputs"]["fit_freeze_sha256"]),
        *_receipt_args("smoke", smoke["smoke_object"]),
        "--smoke-cell-sha256", str(smoke["smoke_cell_sha256"]),
        *_receipt_args("smoke-terminal", smoke["smoke_terminal_object"]),
        "--smoke-terminal-manifest-sha256",
        str(smoke["smoke_terminal_manifest_sha256"]),
    )
    return f"test ! -e {evidence}; " + _command(args)


def aggregate_script(
    contract: Mapping[str, object], source_completion: Mapping[str, object],
    smoke_completion: Mapping[str, object], manifest_raw: bytes,
) -> str:
    value = validate_contract(contract)
    source = _source_completion(source_completion)
    smoke = _smoke_completion(smoke_completion)
    _require_receipt_subset(
        smoke["prefix_receipts"], source["prefix_receipts"],
        label="smoke/source",
    )
    manifest = strict_json(manifest_raw, label="terminal cell manifest")
    _validate_cell_manifest(manifest)
    digest = _sha(manifest_raw)
    encoded = base64.b64encode(manifest_raw).decode("ascii")
    path = "/tmp/lr8-later-terminal-cells.json"
    fit = value["inputs"]["fit_freeze_object"]
    args = (
        "python", "scripts/run_lr8_later_period_source.py", "aggregate",
        *_runtime_args(value), "--cell-manifest", path,
        "--cell-manifest-sha256", digest, "--output-uri", BOOK_FREEZE_URI,
        *_receipt_args("source", source["source_object"]),
        "--source-freeze-sha256", str(source["source_freeze_sha256"]),
        *_receipt_args("fit", fit),
        "--fit-freeze-sha256", str(value["inputs"]["fit_freeze_sha256"]),
        "--anatomy-artifact-sha256", str(value["inputs"]["anatomy_artifact_sha256"]),
        *_receipt_args("smoke", smoke["smoke_object"]),
        "--smoke-cell-sha256", str(smoke["smoke_cell_sha256"]),
        *_receipt_args("smoke-terminal", smoke["smoke_terminal_object"]),
        "--smoke-terminal-manifest-sha256",
        str(smoke["smoke_terminal_manifest_sha256"]),
    )
    return (
        f"umask 077; printf %s {shlex.quote(encoded)} | base64 -d > {path}; "
        f"test \"$(sha256sum {path} | cut -d' ' -f1)\" = {digest}; "
        + _command(args)
    )


def _output_uri(stage: str, index: int | None) -> str:
    if stage == "source" and index is None:
        return SOURCE_URI
    if stage == "smoke" and index is None:
        return SMOKE_URI
    if stage == "cell" and index is not None:
        return cell_uri(index)
    if stage == "aggregate" and index is None:
        return BOOK_FREEZE_URI
    raise LR8LaterTransportError("launch stage/index differs")


def create_intent(
    *, stage: str, index: int | None, script: str,
    contract: Mapping[str, object],
) -> dict[str, object]:
    value = validate_contract(contract)
    intent: dict[str, object] = {
        "schema": "lr8-later-launch-intent-v1",
        "stage": stage,
        "cell_index": index,
        "output_uri": _output_uri(stage, index),
        "script_sha256": _sha(script.encode("utf-8")),
        "contract_sha256": value["contract_sha256"],
        "automatic_retry_licensed": False,
    }
    intent["intent_sha256"] = _sha(canonical_json(intent))
    return intent


def validate_intent(
    value: object, *, stage: str, index: int | None, script: str,
    contract: Mapping[str, object],
) -> dict[str, object]:
    expected = create_intent(
        stage=stage, index=index, script=script, contract=contract,
    )
    if value != expected:
        raise LR8LaterTransportError("launch intent differs")
    return expected


def ledger_line(execution: str, uri: str) -> bytes:
    if _EXECUTION.fullmatch(execution) is None or uri not in {
        SOURCE_URI, SMOKE_URI, BOOK_FREEZE_URI,
        *(cell_uri(index) for index in range(len(later.EXPECTED_SLATE_KEYS))),
    }:
        raise LR8LaterTransportError("execution ledger identity differs")
    return f"{JOB} {execution} {uri}\n".encode("utf-8")


def parse_ledger(path: Path, *, expected_uri: str) -> tuple[str, str, str]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise LR8LaterTransportError("execution ledger is unreadable") from exc
    lines = raw.splitlines()
    if len(lines) != 1:
        raise LR8LaterTransportError("execution ledger differs")
    try:
        fields = lines[0].decode("utf-8").split(" ")
    except UnicodeDecodeError as exc:
        raise LR8LaterTransportError("execution ledger is not UTF-8") from exc
    if len(fields) != 3 or fields[0] != JOB or fields[2] != expected_uri:
        raise LR8LaterTransportError("execution ledger differs")
    if raw != ledger_line(fields[1], fields[2]):
        raise LR8LaterTransportError("execution ledger is not canonical")
    return fields[0], fields[1], fields[2]


def validate_terminal(
    value: Mapping[str, object], *, execution: str, script: str,
    contract: Mapping[str, object],
) -> dict[str, object]:
    identity = validate_contract(contract)
    metadata = value.get("metadata")
    spec = value.get("spec")
    status = value.get("status")
    if not all(isinstance(row, Mapping) for row in (metadata, spec, status)):
        raise LR8LaterTransportError("execution metadata structure differs")
    if metadata.get("name") != execution or _EXECUTION.fullmatch(execution) is None:
        raise LR8LaterTransportError("execution name differs")
    labels = metadata.get("labels")
    if not isinstance(labels, Mapping) or (
        labels.get("run.googleapis.com/job") != JOB
        or labels.get("run.googleapis.com/jobUid") != JOB_UID
        or str(labels.get("run.googleapis.com/jobGeneration"))
        != identity["job_generation"]
    ):
        raise LR8LaterTransportError("execution job binding differs")
    if (
        _exact_int(spec.get("taskCount"), label="execution task count") != 1
        or _exact_int(spec.get("parallelism"), label="execution parallelism") != 1
    ):
        raise LR8LaterTransportError("execution is not one-task serial")
    task = spec.get("template", {}).get("spec", {})
    if not isinstance(task, Mapping) or _exact_int(
        task.get("maxRetries"), label="execution max retries",
    ) != 0:
        raise LR8LaterTransportError("execution retry contract differs")
    containers = task.get("containers")
    if not isinstance(containers, list) or len(containers) != 1 or not isinstance(
        containers[0], Mapping
    ):
        raise LR8LaterTransportError("execution container differs")
    container = containers[0]
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, Mapping) or set(row) != {"name", "value"}
        for row in env_rows
    ):
        raise LR8LaterTransportError("execution environment differs")
    env = {str(row["name"]): row["value"] for row in env_rows}
    if len(env) != len(env_rows) or (
        container.get("image") != identity["image"]
        or container.get("command") != ["bash"]
        or container.get("args") != ["-ceu", script]
        or env != identity["env"]
        or task.get("serviceAccountName") != SERVICE_ACCOUNT
        or container.get("resources", {}).get("limits")
        != {"cpu": CPU, "memory": MEMORY}
        or task.get("timeoutSeconds") != TIMEOUT_SECONDS
    ):
        raise LR8LaterTransportError("execution command/spec binding differs")
    if _completion_state(value) != "True":
        raise LR8LaterTransportError("execution is not strict terminal success")
    counts = {
        short: _exact_int(status[key] if key in status else 0, label=short)
        for key, short in (
            ("succeededCount", "succeeded"), ("failedCount", "failed"),
            ("cancelledCount", "cancelled"), ("retriedCount", "retried"),
        )
    }
    if counts != {"succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0}:
        raise LR8LaterTransportError("execution terminal counters differ")
    return {
        "execution": execution,
        "job": JOB,
        "job_uid": JOB_UID,
        "job_generation": identity["job_generation"],
        "job_spec_sha256": identity["job_spec_sha256"],
        "state": "True",
        "counters": counts,
        "metadata_sha256": _sha(canonical_json(value)),
    }


def _execution_summary(value: object, *, label: str) -> dict[str, object]:
    required = {
        "execution", "job", "job_uid", "job_generation",
        "job_spec_sha256", "state", "counters", "metadata_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise LR8LaterTransportError(f"{label} execution summary fields differ")
    result = dict(value)
    if (
        not isinstance(result["execution"], str)
        or _EXECUTION.fullmatch(result["execution"]) is None
        or result["job"] != JOB
        or result["job_uid"] != JOB_UID
        or _GENERATION.fullmatch(str(result["job_generation"])) is None
        or _SHA256.fullmatch(str(result["job_spec_sha256"])) is None
        or result["state"] != "True"
        or result["counters"] != {
            "succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0,
        }
        or _SHA256.fullmatch(str(result["metadata_sha256"])) is None
    ):
        raise LR8LaterTransportError(f"{label} execution summary differs")
    return result


def _prefix_receipts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise LR8LaterTransportError("prefix receipt manifest differs")
    by_uri: dict[str, dict[str, object]] = {}
    for item in value:
        receipt = _receipt(item, label="prefix object")
        uri = str(receipt["uri"])
        if uri in by_uri and by_uri[uri] != receipt:
            raise LR8LaterTransportError("prefix object URI has two identities")
        by_uri[uri] = receipt
    if list(by_uri) != sorted(by_uri):
        raise LR8LaterTransportError("prefix receipt order differs")
    return list(by_uri.values())


def _merge_receipts(*groups: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    by_uri: dict[str, dict[str, object]] = {}
    for group in groups:
        for item in group:
            receipt = _receipt(item, label="prefix object")
            uri = str(receipt["uri"])
            if uri in by_uri and by_uri[uri] != receipt:
                raise LR8LaterTransportError("prefix object URI has two identities")
            by_uri[uri] = receipt
    return [by_uri[uri] for uri in sorted(by_uri)]


def _require_receipt_subset(
    container: Sequence[Mapping[str, object]],
    required: Sequence[Mapping[str, object]], *, label: str,
) -> None:
    by_uri = {
        str(row["uri"]): row for row in _merge_receipts(container)
    }
    if any(
        by_uri.get(str(row["uri"])) != _receipt(row, label=label)
        for row in required
    ):
        raise LR8LaterTransportError(f"{label} receipt lineage differs")


def _inventory_map(value: object) -> dict[str, dict[str, object]]:
    if not isinstance(value, list):
        raise LR8LaterTransportError("GCS inventory differs")
    result: dict[str, dict[str, object]] = {}
    for item in value:
        row = _inventory_row(item, label="GCS object")
        uri = str(row["uri"])
        if uri in result:
            raise LR8LaterTransportError("GCS inventory repeats a URI")
        result[uri] = row
    return result


def _require_inventory(value: object, receipts: Sequence[Mapping[str, object]]) -> None:
    inventory = _inventory_map(value)
    expected = {
        str(row["uri"]): {
            "uri": row["uri"], "generation": str(row["generation"]),
            "bytes": int(row["bytes"]),
        } for row in _merge_receipts(receipts)
    }
    if inventory != expected:
        raise LR8LaterTransportError("later-period prefix inventory is not exact")


def _require_recovery_inventory(
    value: object, receipts: Sequence[Mapping[str, object]], *,
    optional_uris: set[str],
) -> None:
    """Allow only known partial create-once outputs during stage recovery."""
    inventory = _inventory_map(value)
    required = {
        str(row["uri"]): {
            "uri": row["uri"], "generation": str(row["generation"]),
            "bytes": int(row["bytes"]),
        }
        for row in _merge_receipts(receipts)
    }
    if any(inventory.get(uri) != row for uri, row in required.items()):
        raise LR8LaterTransportError("recovery prefix lost a required object")
    extras = set(inventory).difference(required)
    if not extras.issubset(optional_uris) or set(required).intersection(optional_uris):
        raise LR8LaterTransportError("recovery prefix contains an unknown object")


def _proof_receipts(cell: Mapping[str, object]) -> list[dict[str, object]]:
    proofs = cell.get("pricing_proofs")
    if not isinstance(proofs, list):
        raise LR8LaterTransportError("pricing proof manifest differs")
    rows: list[dict[str, object]] = []
    for proof in proofs:
        if not isinstance(proof, Mapping) or not isinstance(
            proof.get("evidence_objects"), list,
        ):
            raise LR8LaterTransportError("pricing evidence manifest differs")
        rows.extend(
            _receipt(item, label="pricing evidence")
            for item in proof["evidence_objects"]
        )
    return _merge_receipts(rows)


def _load_receipts(storage: Storage, receipts: Sequence[Mapping[str, object]]) -> None:
    for receipt in _merge_receipts(receipts):
        storage.load(receipt)


def _intent_path(out: Path, stage: str, index: int | None = None) -> Path:
    if stage == "cell" and index is not None:
        return out / "cell-launch-intents" / f"cell-{index:02d}.json"
    return out / f"{stage}-launch-intent.json"


def _ledger_path(out: Path, stage: str, index: int | None = None) -> Path:
    if stage == "cell" and index is not None:
        return out / "cell-execution-ledgers" / f"cell-{index:02d}.txt"
    return out / f"{stage}-execution.txt"


def _stage_terminal(
    *, out: Path, stage: str, index: int | None, metadata: Mapping[str, object],
    script: str, contract: Mapping[str, object],
) -> tuple[dict[str, object], str]:
    uri = _output_uri(stage, index)
    _, execution, _ = parse_ledger(
        _ledger_path(out, stage, index), expected_uri=uri,
    )
    intent = _load(_intent_path(out, stage, index), label=f"{stage} launch intent")
    validate_intent(
        intent, stage=stage, index=index, script=script, contract=contract,
    )
    return validate_terminal(
        metadata, execution=execution, script=script, contract=contract,
    ), execution


def finish_source(
    *, out: Path, metadata: Mapping[str, object], storage: Storage | None = None,
) -> dict[str, object]:
    completion_path = out / "source-completion.json"
    if completion_path.is_file():
        return _source_completion(_load(completion_path, label="source completion"))
    contract = validate_contract(_load(out / "contract.json", label="transport contract"))
    script = source_script(contract)
    terminal, _execution = _stage_terminal(
        out=out, stage="source", index=None, metadata=metadata,
        script=script, contract=contract,
    )
    # No GCS client is constructed until strict terminal validation completes.
    store = Storage() if storage is None else storage
    inventory = store.inventory(PREFIX + "/")
    by_uri = _inventory_map(inventory)
    if set(by_uri) != {SOURCE_URI}:
        raise LR8LaterTransportError("source-freeze prefix inventory differs")
    receipt, raw = store.load_inventory(by_uri[SOURCE_URI])
    body = strict_json(raw, label="later-period source freeze")
    try:
        validated = later.validate_source_freeze(
            body, expected_freeze_sha256=str(body.get("freeze_sha256", "")),
        )
    except Exception as exc:
        raise LR8LaterTransportError("later-period source freeze failed validation") from exc
    expected_runtime = {
        "run_id": ATTEMPT_ID, "code_sha": contract["code_sha"],
        "image": contract["image"], "job": JOB,
    }
    if validated.get("runtime_identity") != expected_runtime:
        raise LR8LaterTransportError("source-freeze runtime identity differs")
    receipts = _merge_receipts([receipt])
    _require_inventory(inventory, receipts)
    result = {
        "schema": SOURCE_COMPLETION_VERSION,
        "attempt_id": ATTEMPT_ID,
        "execution": terminal,
        "source_object": receipt,
        "source_freeze_sha256": validated["freeze_sha256"],
        "prefix_receipts": receipts,
        "strict_terminal_success": True,
        "uses_realized_later_period_outcomes": False,
        "historical_outcome_lease_acquired": False,
    }
    _write_once(out / "source-terminal.json", canonical_json(metadata))
    _write_once(out / "later-period-source-freeze.json", raw)
    _write_once(completion_path, canonical_json(result))
    return result


def finish_smoke(
    *, out: Path, metadata: Mapping[str, object], storage: Storage | None = None,
) -> dict[str, object]:
    completion_path = out / "smoke-completion.json"
    if completion_path.is_file():
        return _smoke_completion(_load(completion_path, label="smoke completion"))
    contract = validate_contract(_load(out / "contract.json", label="transport contract"))
    source = _source_completion(_load(out / "source-completion.json", label="source completion"))
    script = smoke_script(contract, source)
    terminal, execution = _stage_terminal(
        out=out, stage="smoke", index=None, metadata=metadata,
        script=script, contract=contract,
    )
    store = Storage() if storage is None else storage
    inventory = store.inventory(PREFIX + "/")
    by_uri = _inventory_map(inventory)
    if SMOKE_URI not in by_uri:
        raise LR8LaterTransportError("smoke result object is absent")
    smoke_receipt, smoke_raw = store.load_inventory(by_uri[SMOKE_URI])
    smoke_body = strict_json(smoke_raw, label="later-period smoke")
    try:
        validated = later.validate_construction_cell(
            smoke_body, expected_cell_sha256=str(smoke_body.get("cell_sha256", "")),
            mode="smoke",
        )
    except Exception as exc:
        raise LR8LaterTransportError("later-period smoke failed validation") from exc
    if (
        (validated.get("season"), validated.get("week"))
        != later.EXPECTED_SLATE_KEYS[0]
        or validated.get("source_freeze_sha256") != source["source_freeze_sha256"]
        or validated.get("anatomy_artifact_sha256")
        != contract["inputs"]["anatomy_artifact_sha256"]
    ):
        raise LR8LaterTransportError("later-period smoke identity differs")
    evidence = _proof_receipts(validated)
    _load_receipts(store, evidence)
    before = _merge_receipts(source["prefix_receipts"], [smoke_receipt], evidence)
    _require_recovery_inventory(
        inventory, before,
        optional_uris={
            SMOKE_EXECUTION_METADATA_URI, SMOKE_FINISH_LEDGER_URI,
            SMOKE_TERMINAL_URI,
        },
    )

    metadata_raw = canonical_json(metadata)
    try:
        ledger_raw = _ledger_path(out, "smoke").read_bytes()
    except OSError as exc:
        raise LR8LaterTransportError("smoke finish ledger is unreadable") from exc
    if ledger_raw != ledger_line(execution, SMOKE_URI):
        raise LR8LaterTransportError("smoke finish ledger changed after validation")
    execution_object = store.publish(SMOKE_EXECUTION_METADATA_URI, metadata_raw)
    ledger_object = store.publish(SMOKE_FINISH_LEDGER_URI, ledger_raw)
    terminal_body: dict[str, object] = {
        "schema": later.SMOKE_TERMINAL_VERSION,
        "execution_name": execution,
        "execution_metadata_object": execution_object,
        "finish_ledger_object": ledger_object,
        "smoke_object": smoke_receipt,
        "smoke_sha256": validated["cell_sha256"],
        "source_freeze_sha256": source["source_freeze_sha256"],
        "anatomy_artifact_sha256": contract["inputs"]["anatomy_artifact_sha256"],
        "task_count": 1,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "retried_count": 0,
        "completed_condition": "True",
        "strict_terminal_success": True,
    }
    terminal_body["terminal_sha256"] = _sha(canonical_json(terminal_body))
    terminal_raw = later.canonical_json(terminal_body)
    terminal_object = store.publish(SMOKE_TERMINAL_URI, terminal_raw)
    try:
        later.validate_smoke_terminal(
            terminal_body, terminal_object=terminal_object,
            smoke_object=smoke_receipt,
            smoke_sha256=str(validated["cell_sha256"]),
            source_freeze_sha256=str(source["source_freeze_sha256"]),
            anatomy_artifact_sha256=str(contract["inputs"]["anatomy_artifact_sha256"]),
        )
    except Exception as exc:
        raise LR8LaterTransportError("smoke terminal authority failed validation") from exc
    receipts = _merge_receipts(
        before, [execution_object, ledger_object, terminal_object],
    )
    _require_inventory(store.inventory(PREFIX + "/"), receipts)
    result = {
        "schema": SMOKE_COMPLETION_VERSION,
        "attempt_id": ATTEMPT_ID,
        "execution": terminal,
        "smoke_object": smoke_receipt,
        "smoke_cell_sha256": validated["cell_sha256"],
        "source_freeze_sha256": source["source_freeze_sha256"],
        "anatomy_artifact_sha256": contract["inputs"]["anatomy_artifact_sha256"],
        "smoke_terminal": terminal_body,
        "smoke_terminal_object": terminal_object,
        "smoke_terminal_manifest_sha256": terminal_body["terminal_sha256"],
        "prefix_receipts": receipts,
        "strict_terminal_success": True,
        "uses_realized_later_period_outcomes": False,
        "historical_outcome_lease_acquired": False,
    }
    _write_once(out / "smoke-terminal-metadata.json", metadata_raw)
    _write_once(out / "later-period-smoke.json", smoke_raw)
    _write_once(out / "smoke-terminal.json", terminal_raw)
    _write_once(completion_path, canonical_json(result))
    return result


def _cell_ledgers(out: Path) -> tuple[tuple[str, str, str], ...]:
    rows = tuple(
        parse_ledger(
            _ledger_path(out, "cell", index), expected_uri=cell_uri(index),
        ) for index in range(len(later.EXPECTED_SLATE_KEYS))
    )
    if len({row[1] for row in rows}) != len(rows):
        raise LR8LaterTransportError("cell execution names repeat")
    return rows


def assemble_cell_ledger(out: Path) -> bytes:
    rows = _cell_ledgers(out)
    return b"".join(ledger_line(execution, uri) for _, execution, uri in rows)


def _validate_cell_manifest(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema", "strict_terminal_success", "cells",
    } or value.get("schema") != "lr8-later-terminal-cell-manifest-v1" or (
        value.get("strict_terminal_success") is not True
    ):
        raise LR8LaterTransportError("terminal cell manifest fields differ")
    cells = value.get("cells")
    if not isinstance(cells, list) or len(cells) != len(later.EXPECTED_SLATE_KEYS):
        raise LR8LaterTransportError("terminal cell manifest count differs")
    normalized = [_receipt(row, label="terminal cell") for row in cells]
    if (
        normalized != cells
        or [row["uri"] for row in normalized]
        != [cell_uri(index) for index in range(len(later.EXPECTED_SLATE_KEYS))]
    ):
        raise LR8LaterTransportError("terminal cell manifest order/identity differs")
    return dict(value)


def _cell_completion(value: object) -> dict[str, object]:
    required = {
        "schema", "attempt_id", "cell_count", "execution_terminals",
        "cell_manifest_object", "cell_manifest_sha256", "cell_objects",
        "prefix_receipts", "all_cells_strict_terminal_success",
        "all_cell_bodies_generation_pinned",
        "uses_realized_later_period_outcomes",
        "historical_outcome_lease_acquired",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise LR8LaterTransportError("cell completion fields differ")
    result = dict(value)
    terminals = result["execution_terminals"]
    cells = result["cell_objects"]
    if (
        result["schema"] != CELL_COMPLETION_VERSION
        or result["attempt_id"] != ATTEMPT_ID
        or result["cell_count"] != len(later.EXPECTED_SLATE_KEYS)
        or not isinstance(terminals, list)
        or len(terminals) != len(later.EXPECTED_SLATE_KEYS)
        or not isinstance(cells, list)
        or len(cells) != len(later.EXPECTED_SLATE_KEYS)
        or result["all_cells_strict_terminal_success"] is not True
        or result["all_cell_bodies_generation_pinned"] is not True
        or result["uses_realized_later_period_outcomes"] is not False
        or result["historical_outcome_lease_acquired"] is not False
    ):
        raise LR8LaterTransportError("cell completion identity differs")
    result["cell_manifest_object"] = _receipt(
        result["cell_manifest_object"], label="terminal cell manifest",
    )
    if result["cell_manifest_object"]["uri"] != CELL_MANIFEST_URI:
        raise LR8LaterTransportError("cell manifest object URI differs")
    _digest(result["cell_manifest_sha256"], label="cell manifest hash")
    normalized = [_receipt(row, label="construction cell") for row in cells]
    if [row["uri"] for row in normalized] != [
        cell_uri(index) for index in range(len(later.EXPECTED_SLATE_KEYS))
    ]:
        raise LR8LaterTransportError("cell completion object order differs")
    result["cell_objects"] = normalized
    result["prefix_receipts"] = _prefix_receipts(result["prefix_receipts"])
    result["execution_terminals"] = [
        _execution_summary(row, label=f"cell {index}")
        for index, row in enumerate(terminals)
    ]
    if len({row["execution"] for row in result["execution_terminals"]}) != len(
        result["execution_terminals"]
    ):
        raise LR8LaterTransportError("cell completion execution names repeat")
    prefix_by_uri = {
        str(row["uri"]): row for row in result["prefix_receipts"]
    }
    if prefix_by_uri.get(CELL_MANIFEST_URI) != result["cell_manifest_object"] or any(
        prefix_by_uri.get(str(row["uri"])) != row for row in normalized
    ):
        raise LR8LaterTransportError("cell completion prefix binding differs")
    return result


def _local_cell_manifest(
    out: Path, completion: Mapping[str, object],
) -> tuple[dict[str, object], bytes]:
    try:
        raw = (out / "terminal-cell-manifest.json").read_bytes()
    except OSError as exc:
        raise LR8LaterTransportError("terminal cell manifest is unreadable") from exc
    value = _validate_cell_manifest(strict_json(
        raw, label="terminal cell manifest",
    ))
    digest = _sha(raw)
    receipt = _receipt(
        completion.get("cell_manifest_object"), label="terminal cell manifest",
    )
    if (
        digest != completion.get("cell_manifest_sha256")
        or receipt["sha256"] != digest
        or receipt["bytes"] != len(raw)
        or value["cells"] != completion.get("cell_objects")
    ):
        raise LR8LaterTransportError("local terminal cell manifest binding differs")
    return value, raw


def _replay_cell_terminals(
    *, out: Path, terminal_dir: Path, contract: Mapping[str, object],
    source: Mapping[str, object], smoke: Mapping[str, object],
) -> list[dict[str, object]]:
    rows = _cell_ledgers(out)
    summaries: list[dict[str, object]] = []
    # Replay the complete ordered ledger/intent/terminal lattice before any
    # GCS access or acceptance of an existing completion.
    for index, (_job, execution, _uri) in enumerate(rows):
        metadata = _load(
            terminal_dir / f"cell-{index:02d}.json",
            label=f"cell {index} terminal metadata",
        )
        script = cell_script(index, contract, source, smoke)
        intent = _load(
            _intent_path(out, "cell", index), label=f"cell {index} launch intent",
        )
        validate_intent(
            intent, stage="cell", index=index, script=script, contract=contract,
        )
        summaries.append(validate_terminal(
            metadata, execution=execution, script=script, contract=contract,
        ))
    return summaries


def finish_cells(
    *, out: Path, terminal_dir: Path, storage: Storage | None = None,
) -> dict[str, object]:
    completion_path = out / "cell-completion.json"
    contract = validate_contract(_load(out / "contract.json", label="transport contract"))
    source = _source_completion(_load(out / "source-completion.json", label="source completion"))
    smoke = _smoke_completion(_load(out / "smoke-completion.json", label="smoke completion"))
    terminal_summaries = _replay_cell_terminals(
        out=out, terminal_dir=terminal_dir, contract=contract,
        source=source, smoke=smoke,
    )
    if completion_path.is_file():
        completion = _cell_completion(
            _load(completion_path, label="cell completion")
        )
        _local_cell_manifest(out, completion)
        if completion["execution_terminals"] != terminal_summaries:
            raise LR8LaterTransportError(
                "cell completion terminal replay differs"
            )
        return completion
    store = Storage() if storage is None else storage
    inventory = store.inventory(PREFIX + "/")
    by_uri = _inventory_map(inventory)
    cell_receipts = []
    evidence = []
    authority = {
        "object": smoke["smoke_object"],
        "smoke_sha256": smoke["smoke_cell_sha256"],
        "source_freeze_sha256": source["source_freeze_sha256"],
        "anatomy_artifact_sha256": contract["inputs"]["anatomy_artifact_sha256"],
        "terminal": smoke["smoke_terminal"],
        "terminal_object": smoke["smoke_terminal_object"],
    }
    for index, key in enumerate(later.EXPECTED_SLATE_KEYS):
        uri = cell_uri(index)
        if uri not in by_uri:
            raise LR8LaterTransportError(f"cell {index} result object is absent")
        receipt, raw = store.load_inventory(by_uri[uri])
        body = strict_json(raw, label=f"construction cell {index}")
        try:
            validated = later.validate_construction_cell(
                body, expected_cell_sha256=str(body.get("cell_sha256", "")),
                mode="full",
            )
        except Exception as exc:
            raise LR8LaterTransportError(f"construction cell {index} failed validation") from exc
        if (
            (validated.get("season"), validated.get("week")) != key
            or validated.get("source_freeze_sha256") != source["source_freeze_sha256"]
            or validated.get("anatomy_artifact_sha256")
            != contract["inputs"]["anatomy_artifact_sha256"]
            or validated.get("smoke_authority") != authority
        ):
            raise LR8LaterTransportError(f"construction cell {index} binding differs")
        cell_receipts.append(receipt)
        evidence.extend(_proof_receipts(validated))
    evidence_receipts = _merge_receipts(evidence)
    _load_receipts(store, evidence_receipts)
    before = _merge_receipts(
        smoke["prefix_receipts"], cell_receipts, evidence_receipts,
    )
    _require_recovery_inventory(
        inventory, before, optional_uris={CELL_MANIFEST_URI},
    )
    manifest = {
        "schema": "lr8-later-terminal-cell-manifest-v1",
        "strict_terminal_success": True,
        "cells": cell_receipts,
    }
    _validate_cell_manifest(manifest)
    manifest_raw = later.canonical_json(manifest)
    manifest_object = store.publish(CELL_MANIFEST_URI, manifest_raw)
    receipts = _merge_receipts(before, [manifest_object])
    _require_inventory(store.inventory(PREFIX + "/"), receipts)
    result = {
        "schema": CELL_COMPLETION_VERSION,
        "attempt_id": ATTEMPT_ID,
        "cell_count": len(cell_receipts),
        "execution_terminals": terminal_summaries,
        "cell_manifest_object": manifest_object,
        "cell_manifest_sha256": _sha(manifest_raw),
        "cell_objects": cell_receipts,
        "prefix_receipts": receipts,
        "all_cells_strict_terminal_success": True,
        "all_cell_bodies_generation_pinned": True,
        "uses_realized_later_period_outcomes": False,
        "historical_outcome_lease_acquired": False,
    }
    _write_once(out / "terminal-cell-manifest.json", manifest_raw)
    _write_once(completion_path, canonical_json(result))
    return result


def _final_completion(value: object) -> dict[str, object]:
    required = {
        "schema", "attempt_id", "execution", "book_freeze_object",
        "book_freeze_sha256", "cell_count", "book_cell_count",
        "strict_terminal_success", "all_inputs_generation_pinned",
        "later_period_score_read_licensed",
        "uses_realized_later_period_outcomes",
        "historical_outcome_lease_acquired", "production_change_licensed",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise LR8LaterTransportError("final completion fields differ")
    result = dict(value)
    result["execution"] = _execution_summary(
        result["execution"], label="aggregate",
    )
    result["book_freeze_object"] = _receipt(
        result["book_freeze_object"], label="108-book freeze",
    )
    _digest(result["book_freeze_sha256"], label="108-book freeze hash")
    if (
        result["schema"] != FINAL_COMPLETION_VERSION
        or result["attempt_id"] != ATTEMPT_ID
        or result["book_freeze_object"]["uri"] != BOOK_FREEZE_URI
        or result["cell_count"] != len(later.EXPECTED_SLATE_KEYS)
        or result["book_cell_count"] != len(later.EXPECTED_SLATE_KEYS) * 2
        or result["strict_terminal_success"] is not True
        or result["all_inputs_generation_pinned"] is not True
        or result["later_period_score_read_licensed"] is not True
        or result["uses_realized_later_period_outcomes"] is not False
        or result["historical_outcome_lease_acquired"] is not False
        or result["production_change_licensed"] is not False
    ):
        raise LR8LaterTransportError("final completion identity differs")
    return result


def _validate_final_body(
    *, raw: bytes, receipt: Mapping[str, object],
    contract: Mapping[str, object], source: Mapping[str, object],
    smoke: Mapping[str, object], cells: Mapping[str, object],
) -> dict[str, object]:
    pinned = _receipt(receipt, label="108-book freeze")
    if pinned["sha256"] != _sha(raw) or pinned["bytes"] != len(raw):
        raise LR8LaterTransportError("108-book freeze local bytes differ")
    body = strict_json(raw, label="108-book freeze")
    try:
        validated = later.validate_book_freeze(
            body, expected_freeze_sha256=str(body.get("freeze_sha256", "")),
        )
    except Exception as exc:
        raise LR8LaterTransportError("108-book freeze failed validation") from exc
    expected_authority = {
        "object": smoke["smoke_object"],
        "smoke_sha256": smoke["smoke_cell_sha256"],
        "source_freeze_sha256": source["source_freeze_sha256"],
        "anatomy_artifact_sha256": contract["inputs"]["anatomy_artifact_sha256"],
        "terminal": smoke["smoke_terminal"],
        "terminal_object": smoke["smoke_terminal_object"],
    }
    if (
        validated.get("source_freeze_object") != source["source_object"]
        or validated.get("source_freeze_sha256") != source["source_freeze_sha256"]
        or validated.get("anatomy_freeze_object")
        != contract["inputs"]["fit_freeze_object"]
        or validated.get("anatomy_freeze_sha256")
        != contract["inputs"]["fit_freeze_sha256"]
        or validated.get("anatomy_artifact_sha256")
        != contract["inputs"]["anatomy_artifact_sha256"]
        or validated.get("smoke_authority") != expected_authority
        or validated.get("cell_objects") != cells.get("cell_objects")
    ):
        raise LR8LaterTransportError("108-book freeze transitive binding differs")
    return validated


def validate_final_state(
    *, out: Path, storage: Storage | None = None,
) -> dict[str, object]:
    completion = _final_completion(_load(
        out / "completion.json", label="later-period completion",
    ))
    contract = validate_contract(_load(out / "contract.json", label="transport contract"))
    source = _source_completion(_load(out / "source-completion.json", label="source completion"))
    smoke = _smoke_completion(_load(out / "smoke-completion.json", label="smoke completion"))
    cells = _cell_completion(_load(out / "cell-completion.json", label="cell completion"))
    _require_receipt_subset(
        cells["prefix_receipts"], smoke["prefix_receipts"],
        label="cell/smoke",
    )
    _manifest, manifest_raw = _local_cell_manifest(out, cells)
    script = aggregate_script(contract, source, smoke, manifest_raw)
    terminal_metadata = _load(
        out / "aggregate-terminal.json", label="aggregate terminal metadata",
    )
    terminal, _execution = _stage_terminal(
        out=out, stage="aggregate", index=None, metadata=terminal_metadata,
        script=script, contract=contract,
    )
    if terminal != completion["execution"]:
        raise LR8LaterTransportError("final completion terminal replay differs")
    try:
        raw = (out / "later-period-108-book-freeze.json").read_bytes()
    except OSError as exc:
        raise LR8LaterTransportError("local 108-book freeze is unreadable") from exc
    validated = _validate_final_body(
        raw=raw, receipt=completion["book_freeze_object"],
        contract=contract, source=source, smoke=smoke, cells=cells,
    )
    if validated["freeze_sha256"] != completion["book_freeze_sha256"]:
        raise LR8LaterTransportError("final completion freeze hash differs")
    store = Storage() if storage is None else storage
    receipts = _merge_receipts(
        cells["prefix_receipts"], [completion["book_freeze_object"]],
    )
    _require_inventory(store.inventory(PREFIX + "/"), receipts)
    reopened = store.load(completion["book_freeze_object"])
    if reopened != raw:
        raise LR8LaterTransportError("final generation-pinned reopen differs")
    return completion


def finish_aggregate(
    *, out: Path, metadata: Mapping[str, object], storage: Storage | None = None,
) -> dict[str, object]:
    completion_path = out / "completion.json"
    if completion_path.is_file():
        return validate_final_state(out=out, storage=storage)
    contract = validate_contract(_load(out / "contract.json", label="transport contract"))
    source = _source_completion(_load(out / "source-completion.json", label="source completion"))
    smoke = _smoke_completion(_load(out / "smoke-completion.json", label="smoke completion"))
    cells = _cell_completion(_load(out / "cell-completion.json", label="cell completion"))
    _require_receipt_subset(
        cells["prefix_receipts"], smoke["prefix_receipts"],
        label="cell/smoke",
    )
    _manifest, manifest_raw = _local_cell_manifest(out, cells)
    script = aggregate_script(contract, source, smoke, manifest_raw)
    terminal, _execution = _stage_terminal(
        out=out, stage="aggregate", index=None, metadata=metadata,
        script=script, contract=contract,
    )
    store = Storage() if storage is None else storage
    inventory = store.inventory(PREFIX + "/")
    by_uri = _inventory_map(inventory)
    if BOOK_FREEZE_URI not in by_uri:
        raise LR8LaterTransportError("108-book freeze object is absent")
    receipt, raw = store.load_inventory(by_uri[BOOK_FREEZE_URI])
    validated = _validate_final_body(
        raw=raw, receipt=receipt, contract=contract, source=source,
        smoke=smoke, cells=cells,
    )
    receipts = _merge_receipts(cells["prefix_receipts"], [receipt])
    _require_inventory(inventory, receipts)
    result = {
        "schema": FINAL_COMPLETION_VERSION,
        "attempt_id": ATTEMPT_ID,
        "execution": terminal,
        "book_freeze_object": receipt,
        "book_freeze_sha256": validated["freeze_sha256"],
        "cell_count": len(later.EXPECTED_SLATE_KEYS),
        "book_cell_count": len(later.EXPECTED_SLATE_KEYS) * 2,
        "strict_terminal_success": True,
        "all_inputs_generation_pinned": True,
        "later_period_score_read_licensed": True,
        "uses_realized_later_period_outcomes": False,
        "historical_outcome_lease_acquired": False,
        "production_change_licensed": False,
    }
    _write_once(out / "aggregate-terminal.json", canonical_json(metadata))
    _write_once(out / "later-period-108-book-freeze.json", raw)
    _write_once(completion_path, canonical_json(result))
    return result


def validate_ready(
    *, out: Path, stage: str, job_metadata: Mapping[str, object],
    executions: object, schedulers: object, inventory: object,
    allowed_cell_ledgers: Path | None = None,
) -> None:
    contract = validate_contract(_load(out / "contract.json", label="transport contract"))
    validate_configured_job(job_metadata, contract=contract)
    _validate_unscheduled(schedulers)
    allowed: set[str] = set()
    if allowed_cell_ledgers is not None and allowed_cell_ledgers.is_dir():
        for path in sorted(allowed_cell_ledgers.glob("cell-*.txt")):
            try:
                index = int(path.stem.removeprefix("cell-"))
            except ValueError as exc:
                raise LR8LaterTransportError("cell ledger filename differs") from exc
            allowed.add(parse_ledger(path, expected_uri=cell_uri(index))[1])
    _validate_idle(executions, allowed_active=allowed)
    if stage == "source":
        expected: Sequence[Mapping[str, object]] = ()
    elif stage == "smoke":
        expected = _source_completion(
            _load(out / "source-completion.json", label="source completion")
        )["prefix_receipts"]
    elif stage == "cells":
        expected = _smoke_completion(
            _load(out / "smoke-completion.json", label="smoke completion")
        )["prefix_receipts"]
    elif stage == "aggregate":
        completion = _cell_completion(
            _load(out / "cell-completion.json", label="cell completion")
        )
        smoke = _smoke_completion(
            _load(out / "smoke-completion.json", label="smoke completion")
        )
        _require_receipt_subset(
            completion["prefix_receipts"], smoke["prefix_receipts"],
            label="cell/smoke",
        )
        _local_cell_manifest(out, completion)
        expected = completion["prefix_receipts"]
    else:
        raise LR8LaterTransportError("ready stage differs")
    _require_inventory(inventory, expected)


def validate_control_plane(
    *, out: Path, job_metadata: Mapping[str, object], executions: object,
    schedulers: object, allowed_cell_ledgers: Path | None = None,
) -> None:
    """Validate the reused job while a bounded cell wave is in progress."""
    contract = validate_contract(_load(out / "contract.json", label="transport contract"))
    validate_configured_job(job_metadata, contract=contract)
    _validate_unscheduled(schedulers)
    allowed: set[str] = set()
    if allowed_cell_ledgers is not None and allowed_cell_ledgers.is_dir():
        for path in sorted(allowed_cell_ledgers.glob("cell-*.txt")):
            try:
                index = int(path.stem.removeprefix("cell-"))
            except ValueError as exc:
                raise LR8LaterTransportError("cell ledger filename differs") from exc
            if not 0 <= index < len(later.EXPECTED_SLATE_KEYS):
                raise LR8LaterTransportError("cell ledger filename differs")
            allowed.add(parse_ledger(path, expected_uri=cell_uri(index))[1])
    _validate_idle(executions, allowed_active=allowed)


def _cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    canonical = sub.add_parser("canonicalize-external-json")
    canonical.add_argument("--raw", type=Path, required=True)
    canonical.add_argument("--output", type=Path, required=True)
    inventory = sub.add_parser("inventory")
    inventory.add_argument("--prefix", required=True)
    inventory.add_argument("--output", type=Path, required=True)
    build = sub.add_parser("validate-build")
    build.add_argument("--metadata", type=Path, required=True)
    build.add_argument("--build-id", required=True)
    build.add_argument("--code-sha", required=True)
    build.add_argument("--image", required=True)
    inputs = sub.add_parser("validate-inputs")
    for stem in ("base-source", "fit-freeze"):
        inputs.add_argument(f"--{stem}-uri", required=True)
        inputs.add_argument(f"--{stem}-generation", required=True)
        inputs.add_argument(f"--{stem}-sha256", required=True)
        inputs.add_argument(f"--{stem}-bytes", type=int, required=True)
    inputs.add_argument("--fit-freeze-manifest-sha256", required=True)
    inputs.add_argument("--anatomy-artifact-sha256", required=True)
    inputs.add_argument("--output", type=Path, required=True)
    reuse = sub.add_parser("validate-reuse")
    for name in ("job-metadata", "executions", "schedulers", "inventory"):
        reuse.add_argument(f"--{name}", type=Path, required=True)
    create = sub.add_parser("create-contract")
    create.add_argument("--job-metadata", type=Path, required=True)
    create.add_argument("--input-validation", type=Path, required=True)
    create.add_argument("--code-sha", required=True)
    create.add_argument("--build-id", required=True)
    create.add_argument("--image", required=True)
    create.add_argument("--output", type=Path, required=True)
    ready = sub.add_parser("validate-ready")
    ready.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    ready.add_argument("--stage", choices=("source", "smoke", "cells", "aggregate"), required=True)
    ready.add_argument("--job-metadata", type=Path, required=True)
    ready.add_argument("--executions", type=Path, required=True)
    ready.add_argument("--schedulers", type=Path, required=True)
    ready.add_argument("--inventory", type=Path, required=True)
    ready.add_argument("--allowed-cell-ledgers", type=Path)
    control = sub.add_parser("validate-control-plane")
    control.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    control.add_argument("--job-metadata", type=Path, required=True)
    control.add_argument("--executions", type=Path, required=True)
    control.add_argument("--schedulers", type=Path, required=True)
    control.add_argument("--allowed-cell-ledgers", type=Path)
    configured = sub.add_parser("validate-configured-job")
    configured.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    configured.add_argument("--job-metadata", type=Path, required=True)
    uri = sub.add_parser("output-uri")
    uri.add_argument(
        "--stage", choices=("source", "smoke", "cell", "aggregate"),
        required=True,
    )
    uri.add_argument("--cell-index", type=int)
    script = sub.add_parser("launch-script")
    script.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    script.add_argument("--stage", choices=("source", "smoke", "cell", "aggregate"), required=True)
    script.add_argument("--cell-index", type=int)
    intent = sub.add_parser("create-intent")
    intent.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    intent.add_argument("--stage", choices=("source", "smoke", "cell", "aggregate"), required=True)
    intent.add_argument("--cell-index", type=int)
    intent.add_argument("--output", type=Path, required=True)
    ledger = sub.add_parser("ledger")
    ledger.add_argument("--execution", required=True)
    ledger.add_argument("--uri", required=True)
    ledger.add_argument("--output", type=Path, required=True)
    parsed = sub.add_parser("ledger-fields")
    parsed.add_argument("--ledger", type=Path, required=True)
    parsed.add_argument("--expected-uri", required=True)
    poll = sub.add_parser("poll-state")
    poll.add_argument("--metadata", type=Path, required=True)
    source = sub.add_parser("finish-source")
    source.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    source.add_argument("--metadata", type=Path, required=True)
    smoke = sub.add_parser("finish-smoke")
    smoke.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    smoke.add_argument("--metadata", type=Path, required=True)
    assemble = sub.add_parser("assemble-cell-ledger")
    assemble.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    assemble.add_argument("--output", type=Path, required=True)
    cells = sub.add_parser("finish-cells")
    cells.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    cells.add_argument("--terminal-dir", type=Path, required=True)
    final = sub.add_parser("finish-aggregate")
    final.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    final.add_argument("--metadata", type=Path, required=True)
    validate_final = sub.add_parser("validate-final")
    validate_final.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    return parser


def _cli_receipt(args: argparse.Namespace, stem: str) -> dict[str, object]:
    key = stem.replace("-", "_")
    return _receipt({
        "uri": getattr(args, f"{key}_uri"),
        "generation": getattr(args, f"{key}_generation"),
        "sha256": getattr(args, f"{key}_sha256"),
        "bytes": getattr(args, f"{key}_bytes"),
    }, label=stem)


def _script_for(out: Path, stage: str, index: int | None) -> str:
    contract = validate_contract(_load(out / "contract.json", label="transport contract"))
    if stage == "source":
        return source_script(contract)
    source = _source_completion(_load(out / "source-completion.json", label="source completion"))
    if stage == "smoke":
        return smoke_script(contract, source)
    smoke = _smoke_completion(_load(out / "smoke-completion.json", label="smoke completion"))
    if stage == "cell" and index is not None:
        return cell_script(index, contract, source, smoke)
    if stage == "aggregate" and index is None:
        cells = _cell_completion(
            _load(out / "cell-completion.json", label="cell completion")
        )
        _require_receipt_subset(
            cells["prefix_receipts"], smoke["prefix_receipts"],
            label="cell/smoke",
        )
        _manifest, manifest_raw = _local_cell_manifest(out, cells)
        return aggregate_script(
            contract, source, smoke, manifest_raw,
        )
    raise LR8LaterTransportError("launch script stage/index differs")


def main(argv: Sequence[str] | None = None) -> int:
    args = _cli().parse_args(argv)
    if args.command == "canonicalize-external-json":
        _write_once(args.output, canonical_json(strict_json_value(
            args.raw.read_bytes(), label="external JSON",
        )))
    elif args.command == "inventory":
        _write_once(args.output, canonical_json(Storage().inventory(args.prefix)))
    elif args.command == "validate-build":
        validate_build(
            _load(args.metadata, label="build metadata"), build_id=args.build_id,
            code_sha=args.code_sha, image=args.image,
        )
    elif args.command == "validate-inputs":
        result = validate_inputs(
            base_source=_cli_receipt(args, "base-source"),
            fit_freeze=_cli_receipt(args, "fit-freeze"),
            fit_freeze_sha256=args.fit_freeze_manifest_sha256,
            anatomy_artifact_sha256=args.anatomy_artifact_sha256,
        )
        _write_once(args.output, canonical_json(result))
    elif args.command == "validate-reuse":
        validate_reuse(
            job_metadata=_load(args.job_metadata, label="job metadata"),
            executions=_load_any(args.executions, label="execution census"),
            schedulers=_load_any(args.schedulers, label="scheduler census"),
            inventory=_load_any(args.inventory, label="prefix inventory"),
        )
    elif args.command == "create-contract":
        result = create_contract(
            job_metadata=_load(args.job_metadata, label="job metadata"),
            input_validation=_load(args.input_validation, label="input validation"),
            code_sha=args.code_sha, build_id=args.build_id, image=args.image,
        )
        _write_once(args.output, canonical_json(result))
    elif args.command == "validate-ready":
        validate_ready(
            out=args.output_dir, stage=args.stage,
            job_metadata=_load(args.job_metadata, label="job metadata"),
            executions=_load_any(args.executions, label="execution census"),
            schedulers=_load_any(args.schedulers, label="scheduler census"),
            inventory=_load_any(args.inventory, label="prefix inventory"),
            allowed_cell_ledgers=args.allowed_cell_ledgers,
        )
    elif args.command == "validate-control-plane":
        validate_control_plane(
            out=args.output_dir,
            job_metadata=_load(args.job_metadata, label="job metadata"),
            executions=_load_any(args.executions, label="execution census"),
            schedulers=_load_any(args.schedulers, label="scheduler census"),
            allowed_cell_ledgers=args.allowed_cell_ledgers,
        )
    elif args.command == "validate-configured-job":
        validate_configured_job(
            _load(args.job_metadata, label="job metadata"),
            contract=validate_contract(_load(
                args.output_dir / "contract.json", label="transport contract",
            )),
        )
    elif args.command == "output-uri":
        print(_output_uri(args.stage, args.cell_index))
    elif args.command == "launch-script":
        print(_script_for(args.output_dir, args.stage, args.cell_index))
    elif args.command == "create-intent":
        contract = validate_contract(_load(
            args.output_dir / "contract.json", label="transport contract",
        ))
        script = _script_for(args.output_dir, args.stage, args.cell_index)
        _write_once(args.output, canonical_json(create_intent(
            stage=args.stage, index=args.cell_index, script=script,
            contract=contract,
        )))
    elif args.command == "ledger":
        _write_once(args.output, ledger_line(args.execution, args.uri))
    elif args.command == "ledger-fields":
        for field in parse_ledger(args.ledger, expected_uri=args.expected_uri):
            print(field)
    elif args.command == "poll-state":
        print(_completion_state(_load(args.metadata, label="execution poll")))
    elif args.command == "finish-source":
        finish_source(
            out=args.output_dir,
            metadata=_load(args.metadata, label="source terminal metadata"),
        )
    elif args.command == "finish-smoke":
        finish_smoke(
            out=args.output_dir,
            metadata=_load(args.metadata, label="smoke terminal metadata"),
        )
    elif args.command == "assemble-cell-ledger":
        _write_once(args.output, assemble_cell_ledger(args.output_dir))
    elif args.command == "finish-cells":
        finish_cells(out=args.output_dir, terminal_dir=args.terminal_dir)
    elif args.command == "finish-aggregate":
        finish_aggregate(
            out=args.output_dir,
            metadata=_load(args.metadata, label="aggregate terminal metadata"),
        )
    elif args.command == "validate-final":
        validate_final_state(out=args.output_dir)
    else:  # pragma: no cover
        raise LR8LaterTransportError("command differs")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LR8LaterTransportError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
