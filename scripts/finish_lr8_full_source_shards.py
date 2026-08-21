#!/usr/bin/env python3
"""Terminal-first harvester for the LR8 70-cell score-free source transport."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from hashlib import sha256
from pathlib import Path
import re
import sys
from typing import Any, Final


ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import run_lr8_full_source_shards as transport  # noqa: E402
from nfl_dfs.research import lr8_full_source_shards as shard_core  # noqa: E402


JOB: Final = "atlas-md-prefix-r4-smoke"
JOB_UID: Final = "51545eb0-59e4-424e-91c9-98dd318285f4"
PROJECT: Final = transport.PROJECT
REGION: Final = "us-central1"
DEFAULT_OUT: Final = (
    ROOT / "reports/lr8-full-source-shard-runs" / transport.ATTEMPT_ID
)
_IMAGE_RE: Final = re.compile(
    r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
    r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}"
)
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}")
_BUILD_RE: Final = re.compile(r"[0-9A-Za-z-]{8,80}")
REQUIRED_BUILD_SMOKES: Final = (
    "python scripts/run_lr8_full_source_shards.py --help >/dev/null",
    "python scripts/finish_lr8_full_source_shards.py --help >/dev/null",
    "bash -n scripts/cloud_lr8_full_source_shards.sh",
    "bash -n scripts/watch_lr8_full_source_shards_queue.sh",
)
SMOKE_FINISH_FILES: Final = (
    "launch.sha256",
    "execution-terminal.json",
    "result-inventory.json",
    "result-objects.json",
    "smoke-manifest.json",
    "smoke-solve-freeze.json",
    "completion.json",
)


class LR8FullSourceFinishError(RuntimeError):
    """A fail-closed terminal harvest violation."""


def _canonical_json(value: object) -> bytes:
    return transport._canonical_json(value)  # noqa: SLF001


def _load_json(path: Path, *, label: str) -> Any:
    if not path.is_file() or path.is_symlink():
        raise LR8FullSourceFinishError(f"{label} file is absent")
    return transport._strict_json(path.read_bytes(), label=label)  # noqa: SLF001


def _write_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise LR8FullSourceFinishError(
                f"immutable local object differs: {path}"
            )


def _sha_path(path: Path, *, label: str) -> str:
    if path.is_symlink() or not path.is_file():
        raise LR8FullSourceFinishError(f"{label} file is absent")
    return sha256(path.read_bytes()).hexdigest()


def load_validated_smoke(smoke_out: Path) -> tuple[object, object]:
    """Reopen the exact v2 smoke authority through its immutable finish ledger."""
    ledger = smoke_out / "finish.sha256"
    expected = "".join(
        f"{_sha_path(smoke_out / name, label='smoke finish object')}  {name}\n"
        for name in sorted(SMOKE_FINISH_FILES)
    ).encode("utf-8")
    if ledger.is_symlink() or not ledger.is_file() or ledger.read_bytes() != expected:
        raise LR8FullSourceFinishError("real LR8 smoke finish ledger differs")
    completion = _load_json(smoke_out / "completion.json", label="smoke completion")
    smoke_freeze = _load_json(
        smoke_out / "smoke-solve-freeze.json", label="smoke freeze",
    )
    validate_smoke(completion, smoke_freeze)
    return completion, smoke_freeze


def _completion_state(value: Mapping[str, object]) -> str:
    status = value.get("status")
    if not isinstance(status, Mapping):
        raise LR8FullSourceFinishError("execution status differs")
    conditions = status.get("conditions", [])
    if not isinstance(conditions, list):
        raise LR8FullSourceFinishError("execution conditions differ")
    rows = [row for row in conditions if isinstance(row, Mapping)
            and row.get("type") == "Completed"]
    if not rows:
        return "Unknown"
    if len(rows) != 1 or rows[0].get("status") not in {"Unknown", "True", "False"}:
        raise LR8FullSourceFinishError("execution Completed condition differs")
    return str(rows[0]["status"])


def _task_spec(value: Mapping[str, object]) -> Mapping[str, object]:
    try:
        task = value["spec"]["template"]["spec"]["template"]["spec"]
    except (KeyError, TypeError):
        try:
            task = value["spec"]["template"]["spec"]
        except (KeyError, TypeError) as exc:
            raise LR8FullSourceFinishError("Cloud Run task spec differs") from exc
    if not isinstance(task, Mapping):
        raise LR8FullSourceFinishError("Cloud Run task spec differs")
    return task


def _job_identity(value: Mapping[str, object], *, job: str, job_uid: str) -> None:
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping) or (
        metadata.get("name"), metadata.get("uid")
    ) != (job, job_uid):
        raise LR8FullSourceFinishError("reused Cloud Run job identity differs")


def _job_generation(value: Mapping[str, object]) -> str:
    metadata = value.get("metadata")
    generation = metadata.get("generation") if isinstance(metadata, Mapping) else None
    if isinstance(generation, bool) or not isinstance(generation, (str, int)):
        raise LR8FullSourceFinishError("reused Cloud Run job generation differs")
    result = str(generation)
    if re.fullmatch(r"[1-9][0-9]*", result) is None:
        raise LR8FullSourceFinishError("reused Cloud Run job generation differs")
    return result


def _job_spec_sha256(value: Mapping[str, object]) -> str:
    spec = value.get("spec")
    if not isinstance(spec, Mapping) or not spec:
        raise LR8FullSourceFinishError("reused Cloud Run job spec differs")
    return transport.training.canonical_sha256(spec)


def _outer_spec(value: Mapping[str, object]) -> Mapping[str, object]:
    try:
        outer = value["spec"]["template"]["spec"]
    except (KeyError, TypeError) as exc:
        raise LR8FullSourceFinishError("Cloud Run outer spec differs") from exc
    if not isinstance(outer, Mapping):
        raise LR8FullSourceFinishError("Cloud Run outer spec differs")
    return outer


def _validate_configured_contract(
    value: Mapping[str, object],
    *,
    provenance: Mapping[str, object],
) -> dict[str, object]:
    expected = transport.validate_execution_provenance(provenance)
    _job_identity(value, job=JOB, job_uid=JOB_UID)
    if (
        _job_generation(value) != expected["job_generation"]
        or _job_spec_sha256(value) != expected["job_spec_sha256"]
    ):
        raise LR8FullSourceFinishError("configured job generation/spec differs")
    outer = _outer_spec(value)
    task = _task_spec(value)
    containers = task.get("containers")
    if not isinstance(containers, list) or len(containers) != 1 or not isinstance(
        containers[0], Mapping
    ):
        raise LR8FullSourceFinishError("configured job container differs")
    container = containers[0]
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, Mapping)
        or set(row) != {"name", "value"}
        or not isinstance(row["name"], str)
        or not isinstance(row["value"], str)
        for row in env_rows
    ):
        raise LR8FullSourceFinishError("configured job environment differs")
    env = {row["name"]: row["value"] for row in env_rows}
    if len(env) != len(env_rows):
        raise LR8FullSourceFinishError("configured job environment repeats")
    try:
        tasks = transport._exact_int(  # noqa: SLF001
            outer.get("taskCount"), label="configured task count",
        )
        parallelism = transport._exact_int(  # noqa: SLF001
            outer.get("parallelism"), label="configured parallelism",
        )
        retries = transport._exact_int(  # noqa: SLF001
            task.get("maxRetries"), label="configured max retries",
        )
    except transport.LR8FullSourceTransportError as exc:
        raise LR8FullSourceFinishError(str(exc)) from exc
    if (
        tasks != expected["task_count"]
        or parallelism != expected["parallelism"]
        or retries != expected["max_retries"]
        or container.get("image") != expected["image"]
        or container.get("command") != expected["command"]
        or container.get("args") != expected["args"]
        or env != expected["env"]
        or task.get("serviceAccountName") != expected["service_account"]
        or container.get("resources", {}).get("limits")
        != expected["resources"]
        or task.get("timeoutSeconds") != expected["timeout_seconds"]
        or container.get("workingDir", "") != ""
        or container.get("volumeMounts", []) != []
        or container.get("startupProbe") not in (None, {})
        or task.get("volumes", []) != []
    ):
        raise LR8FullSourceFinishError("configured job executable contract differs")
    return expected


def create_launch_contract(
    *,
    mode: str,
    job_metadata: Mapping[str, object],
    code_sha: str,
    build_id: str,
    image: str,
    output: Path,
    preparation_receipt: shard_core.ObjectReceipt | None = None,
    parity_receipt: shard_core.ObjectReceipt | None = None,
) -> dict[str, object]:
    provenance = transport.build_execution_provenance(
        mode=mode,
        code_sha=code_sha,
        build_id=build_id,
        image=image,
        job_generation=_job_generation(job_metadata),
        job_spec_sha256=_job_spec_sha256(job_metadata),
        preparation_receipt=preparation_receipt,
        parity_receipt=parity_receipt,
    )
    validated = _validate_configured_contract(
        job_metadata, provenance=provenance,
    )
    _write_once(output, _canonical_json(validated))
    return validated


def _load_launch_contract(
    path: Path,
    *,
    mode: str,
    preparation_receipt: shard_core.ObjectReceipt | None = None,
    parity_receipt: shard_core.ObjectReceipt | None = None,
) -> dict[str, object]:
    value = transport.validate_execution_provenance(
        _load_json(path, label=f"{mode} launch contract")
    )
    expected = transport.build_execution_provenance(
        mode=mode,
        code_sha=str(value["code_sha"]),
        build_id=str(value["build_id"]),
        image=str(value["image"]),
        job_generation=str(value["job_generation"]),
        job_spec_sha256=str(value["job_spec_sha256"]),
        preparation_receipt=preparation_receipt,
        parity_receipt=parity_receipt,
    )
    if value != expected:
        raise LR8FullSourceFinishError("launch contract source binding differs")
    return value


def _validate_idle(executions: object) -> None:
    if not isinstance(executions, list):
        raise LR8FullSourceFinishError("execution census differs")
    for value in executions:
        if not isinstance(value, Mapping) or _completion_state(value) == "Unknown":
            raise LR8FullSourceFinishError("reused job has an active execution")


def _validate_unscheduled(schedulers: object, *, job: str) -> None:
    if not isinstance(schedulers, list):
        raise LR8FullSourceFinishError("scheduler census differs")
    needle = f"/jobs/{job}:run"
    for value in schedulers:
        if not isinstance(value, Mapping):
            raise LR8FullSourceFinishError("scheduler row differs")
        target = value.get("httpTarget", {})
        if isinstance(target, Mapping) and needle in str(target.get("uri", "")):
            raise LR8FullSourceFinishError("scheduler targets reused job")


def validate_build_metadata(
    value: object,
    *,
    build_id: str,
    code_sha: str,
    image: str,
) -> None:
    """Require an exact successful direct-Git build with this scaffold smoked."""
    if (
        not isinstance(value, Mapping)
        or _BUILD_RE.fullmatch(build_id) is None
        or _COMMIT_RE.fullmatch(code_sha) is None
        or _IMAGE_RE.fullmatch(image) is None
        or value.get("id") != build_id
        or value.get("status") != "SUCCESS"
    ):
        raise LR8FullSourceFinishError("full-source build identity differs")
    try:
        requested = value["source"]["gitSource"]["revision"]
        resolved = value["sourceProvenance"]["resolvedGitSource"]["revision"]
    except (KeyError, TypeError) as exc:
        raise LR8FullSourceFinishError("direct-Git build provenance is absent") from exc
    if requested != code_sha or resolved != code_sha:
        raise LR8FullSourceFinishError("direct-Git build source differs")
    digest = image.rsplit("@", 1)[1]
    results = value.get("results", {}).get("images", [])
    if not isinstance(results, list) or not any(
        isinstance(row, Mapping) and row.get("digest") == digest for row in results
    ):
        raise LR8FullSourceFinishError("build image digest differs")
    steps = value.get("steps")
    if not isinstance(steps, list) or not steps or any(
        not isinstance(row, Mapping)
        or row.get("status") != "SUCCESS"
        or int(row.get("exitCode", 0) or 0) != 0
        for row in steps
    ):
        raise LR8FullSourceFinishError("build steps are not all successful")
    rendered = "\n".join(
        str(item)
        for row in steps
        for item in (row.get("args", []) if isinstance(row, Mapping) else [])
    )
    missing = [row for row in REQUIRED_BUILD_SMOKES if row not in rendered]
    if missing:
        raise LR8FullSourceFinishError(
            "full-source build integration smokes are absent"
        )


class _Storage:
    def __init__(self):
        from google.cloud import storage

        self._client = storage.Client(project=PROJECT)
        self._store = transport._CloudObjectStore(self._client)  # noqa: SLF001

    def inventory(self, prefix: str) -> list[dict[str, object]]:
        bucket_name, object_prefix = transport._gcs_parts(prefix)  # noqa: SLF001
        rows = []
        for blob in self._client.list_blobs(bucket_name, prefix=object_prefix):
            if blob.generation is None or blob.size is None:
                raise LR8FullSourceFinishError("GCS object metadata is incomplete")
            rows.append({
                "uri": f"gs://{bucket_name}/{blob.name}",
                "generation": str(blob.generation),
                "bytes": int(blob.size),
            })
        rows.sort(key=lambda row: str(row["uri"]))
        return rows

    def load(
        self, metadata: Mapping[str, object],
    ) -> tuple[dict[str, object], bytes]:
        identity = transport._inventory_identity(  # noqa: SLF001
            metadata, label="GCS inventory object",
        )
        bucket, name = transport._gcs_parts(str(identity["uri"]))  # noqa: SLF001
        generation = int(str(identity["generation"]))
        blob = self._client.bucket(bucket).blob(name, generation=generation)
        raw = blob.download_as_bytes(if_generation_match=generation)
        if len(raw) != identity["bytes"]:
            raise LR8FullSourceFinishError("GCS object byte count differs")
        return ({
            **identity,
            "sha256": sha256(raw).hexdigest(),
        }, raw)

    def load_receipt(
        self, receipt: Mapping[str, object] | shard_core.ObjectReceipt,
    ) -> tuple[dict[str, object], bytes]:
        return self._store.load(receipt)

    def publish(self, uri: str, raw: bytes) -> transport.PublishedObject:
        return self._store.publish(uri, raw)


def validate_smoke(completion: object, smoke_freeze: object) -> None:
    if not isinstance(completion, Mapping) or (
        completion.get("version") != transport.SMOKE_COMPLETION_VERSION
        or completion.get("attempt_id") != transport.SMOKE_ATTEMPT_ID
        or completion.get("disposition") != transport.SMOKE_COMPLETION_DISPOSITION
        or completion.get("uses_realized_target_or_candidate_outcomes") is not False
        or completion.get("historical_outcome_lease_acquired") is not False
        or completion.get("production_change_licensed") is not False
    ):
        raise LR8FullSourceFinishError("real LR8 smoke has not passed cleanly")
    execution = completion.get("execution")
    if not isinstance(execution, Mapping) or (
        execution.get("state") != "True"
        or execution.get("counters")
        != {"succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0}
    ):
        raise LR8FullSourceFinishError("real LR8 smoke terminal differs")
    if not isinstance(smoke_freeze, Mapping) or (
        smoke_freeze.get("season"), smoke_freeze.get("week"),
        smoke_freeze.get("block"), smoke_freeze.get("unique_candidate_count"),
    ) != (2019, 1, "R0", 40):
        raise LR8FullSourceFinishError("real LR8 smoke freeze differs")
    if completion.get("smoke_solve_freeze_sha256") != sha256(
        _canonical_json(smoke_freeze)
    ).hexdigest():
        raise LR8FullSourceFinishError("real LR8 smoke freeze hash differs")


def _load_prepared_cells(
    storage: _Storage,
    preparation: Mapping[str, object],
) -> tuple[shard_core.PreparedCell, ...]:
    rows = preparation["prepared_cells"]
    result = []
    for index, row in enumerate(rows):
        cell_receipt = transport._receipt(  # noqa: SLF001
            row["cell_object"], label="prepared cell object",
        )
        draw_receipt = transport._receipt(  # noqa: SLF001
            row["draw_object"], label="prepared draw object",
        )
        cell_metadata, cell_raw = storage.load_receipt(cell_receipt)
        draw_metadata, draw_raw = storage.load_receipt(draw_receipt)
        prepared = transport._prepared_from_object(  # noqa: SLF001
            cell_raw, draw_metadata=draw_metadata, draw_raw=draw_raw,
        )
        if (
            prepared.cell_index != index
            or row["prepared_cell_sha256"] != prepared.prepared_cell_sha256
            or transport._loaded_receipt(  # noqa: SLF001
                cell_metadata, cell_raw, label="prepared cell object",
            ) != cell_receipt
        ):
            raise LR8FullSourceFinishError("prepared cell receipt differs")
        result.append(prepared)
    return tuple(result)


def parse_preparation_ledger(path: Path) -> tuple[str, str, str]:
    """Parse exactly one canonical ``JOB EXECUTION PREPARATION_URI`` row."""
    if not path.is_file() or path.is_symlink():
        raise LR8FullSourceFinishError("preparation execution ledger is absent")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LR8FullSourceFinishError(
            "preparation execution ledger is not UTF-8"
        ) from exc
    lines = text.splitlines()
    if len(lines) != 1:
        raise LR8FullSourceFinishError("preparation execution ledger differs")
    fields = lines[0].split()
    if len(fields) != 3:
        raise LR8FullSourceFinishError("preparation execution ledger differs")
    job, execution, uri = fields
    if job != JOB or uri != transport.PREPARATION_URI:
        raise LR8FullSourceFinishError("preparation execution ledger differs")
    try:
        canonical = transport.ledger_line(job, execution, uri).encode("utf-8")
    except transport.LR8FullSourceTransportError as exc:
        raise LR8FullSourceFinishError(str(exc)) from exc
    if raw != canonical:
        raise LR8FullSourceFinishError(
            "preparation execution ledger is not canonical"
        )
    return job, execution, uri


def finish_preparation(
    *,
    out: Path,
    ledger_path: Path,
    execution_metadata: Mapping[str, object],
    storage: _Storage | None = None,
) -> dict[str, object]:
    if (out / "preparation-completion.json").is_file():
        return _load_json(
            out / "preparation-completion.json", label="preparation completion",
        )
    _job, execution, _uri = parse_preparation_ledger(ledger_path)
    provenance = _load_launch_contract(
        out / "preparation-launch-contract.json", mode="prepare",
    )
    # Strict terminal metadata is validated before storage is constructed.
    terminal = transport.strict_terminal(
        execution_metadata,
        execution=execution,
        job=JOB,
        execution_provenance=provenance,
        expected_command=("python",),
        expected_args=(
            *transport.preparation_job_args(),
            *transport._provenance_cli_args(provenance),  # noqa: SLF001
        ),
    )
    if storage is None:
        storage = _Storage()
    inventory = storage.inventory(transport.RESULT_PREFIX + "/")
    by_uri = {str(row["uri"]): row for row in inventory}
    if len(by_uri) != len(inventory) or transport.PREPARATION_URI not in by_uri:
        raise LR8FullSourceFinishError("preparation inventory differs")
    science_by_uri = {
        uri: row for uri, row in by_uri.items()
        if uri != transport.SMOKE_PARITY_URI
    }
    prep_metadata, prep_raw = storage.load(by_uri[transport.PREPARATION_URI])
    preparation_receipt = transport._loaded_receipt(  # noqa: SLF001
        prep_metadata, prep_raw, label="preparation manifest",
    )
    preparation = transport.validate_preparation_manifest(
        transport._strict_json(prep_raw, label="preparation manifest")  # noqa: SLF001
    )
    if preparation["execution_provenance"] != provenance:
        raise LR8FullSourceFinishError("preparation execution provenance differs")
    prepared = _load_prepared_cells(storage, preparation)

    expected_receipts = {preparation_receipt}
    for row, cell in zip(preparation["prepared_cells"], prepared):
        expected_receipts.add(transport._receipt(  # noqa: SLF001
            row["cell_object"], label="prepared cell object",
        ))
        expected_receipts.add(transport._receipt(  # noqa: SLF001
            row["draw_object"], label="prepared draw object",
        ))
        expected_receipts.update(cell.catalog_source_receipts)
        expected_receipts.update(cell.incumbent_source_receipts)
        expected_receipts.update(cell.fit_source_receipts)
        expected_receipts.update(cell.draw_source_receipts)
    if set(science_by_uri) != {row.uri for row in expected_receipts}:
        raise LR8FullSourceFinishError("preparation prefix inventory is not exact")
    # Reopen and content-check source extracts that were not opened above.
    for receipt in sorted(expected_receipts, key=lambda row: row.uri):
        metadata, raw = storage.load_receipt(receipt)
        if transport._loaded_receipt(  # noqa: SLF001
            metadata, raw, label="preparation object",
        ) != receipt:
            raise LR8FullSourceFinishError("preparation object receipt differs")

    smoke_completion, smoke_freeze = load_validated_smoke(
        ROOT / "reports/lr8-training-source-smoke-runs" /
        transport.SMOKE_ATTEMPT_ID,
    )
    parity = transport.validate_smoke_parity(
        smoke_completion=smoke_completion,
        smoke_solve_freeze=smoke_freeze,
        prepared_cell=prepared[0],
    )
    parity_raw = _canonical_json(parity)
    parity_receipt = transport._published(  # noqa: SLF001
        storage.publish(transport.SMOKE_PARITY_URI, parity_raw),
        uri=transport.SMOKE_PARITY_URI,
        raw=parity_raw,
    )
    completion = {
        "version": "lr8-full-source-preparation-completion-v1",
        "attempt_id": transport.ATTEMPT_ID,
        "execution": terminal,
        "execution_provenance": provenance,
        "prepared_cell_count": len(prepared),
        "preparation_manifest_object": preparation_receipt.as_dict(),
        "smoke_parity_object": parity_receipt.as_dict(),
        "smoke_prepared_parity_exact": True,
        "cell_execution_licensed": True,
        "actual_score_queried": False,
        "historical_outcome_lease_acquired": False,
        "production_change_licensed": False,
    }
    _write_once(out / "preparation-terminal.json", _canonical_json(execution_metadata))
    _write_once(out / "preparation-manifest.json", prep_raw)
    _write_once(
        out / "preparation-manifest-object.json",
        _canonical_json(preparation_receipt.as_dict()),
    )
    _write_once(out / "smoke-parity.json", parity_raw)
    _write_once(
        out / "smoke-parity-object.json",
        _canonical_json(parity_receipt.as_dict()),
    )
    _write_once(out / "preparation-completion.json", _canonical_json(completion))
    return completion


def _ledger(path: Path) -> tuple[tuple[str, str, str], ...]:
    if not path.is_file() or path.is_symlink():
        raise LR8FullSourceFinishError("cell execution ledger is absent")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LR8FullSourceFinishError("cell execution ledger is not UTF-8") from exc
    rows = []
    canonical = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 3:
            raise LR8FullSourceFinishError("cell execution ledger differs")
        rows.append(tuple(fields))
    if len(rows) != shard_core.EXPECTED_CELLS:
        raise LR8FullSourceFinishError("cell execution ledger count differs")
    for index, (job, execution, uri) in enumerate(rows):
        if job != JOB or uri != transport.cell_shard_uri(index):
            raise LR8FullSourceFinishError("cell execution ledger order differs")
        canonical.append(transport.ledger_line(job, execution, uri))
    if len({row[1] for row in rows}) != len(rows):
        raise LR8FullSourceFinishError("cell execution names repeat")
    if raw != "".join(canonical).encode("utf-8"):
        raise LR8FullSourceFinishError("cell execution ledger is not canonical")
    return tuple(rows)


def finish_cells(
    *,
    out: Path,
    ledger_path: Path,
    terminal_dir: Path,
    storage: _Storage | None = None,
) -> dict[str, object]:
    if (out / "completion.json").is_file():
        return _load_json(out / "completion.json", label="full-source completion")
    completion = _load_json(
        out / "preparation-completion.json", label="preparation completion",
    )
    if (
        completion.get("smoke_prepared_parity_exact") is not True
        or completion.get("cell_execution_licensed") is not True
    ):
        raise LR8FullSourceFinishError("cell execution is not parity-licensed")
    preparation_receipt = transport._receipt(  # noqa: SLF001
        completion["preparation_manifest_object"],
        label="preparation manifest object",
    )
    parity_receipt = transport._receipt(  # noqa: SLF001
        completion["smoke_parity_object"], label="smoke parity object",
    )
    prepared_provenance = _load_launch_contract(
        out / "preparation-launch-contract.json", mode="prepare",
    )
    if completion.get("execution_provenance") != prepared_provenance:
        raise LR8FullSourceFinishError("preparation completion provenance differs")
    cell_provenance = _load_launch_contract(
        out / "cell-launch-contract.json",
        mode="cell",
        preparation_receipt=preparation_receipt,
        parity_receipt=parity_receipt,
    )
    rows = _ledger(ledger_path)
    terminal_values = []
    # Validate all 70 terminal metadata bodies before any result storage read.
    for index, (_job, execution, _uri) in enumerate(rows):
        value = _load_json(
            terminal_dir / f"cell-{index:02d}.json",
            label=f"cell {index} terminal metadata",
        )
        transport.strict_terminal(
            value,
            execution=execution,
            job=JOB,
            execution_provenance=cell_provenance,
            expected_command=("bash",),
            expected_args=("-ceu", transport.cell_job_script(
                cell_index=index,
                preparation_receipt=preparation_receipt,
                parity_receipt=parity_receipt,
                provenance_args=transport._provenance_cli_args(  # noqa: SLF001
                    cell_provenance
                ),
            )),
        )
        terminal_values.append(value)
    if storage is None:
        storage = _Storage()
    _, prep_raw = storage.load_receipt(preparation_receipt)
    preparation = transport.validate_preparation_manifest(
        transport._strict_json(prep_raw, label="preparation manifest")  # noqa: SLF001
    )
    if preparation["execution_provenance"] != prepared_provenance:
        raise LR8FullSourceFinishError("preparation manifest provenance differs")
    prepared = _load_prepared_cells(storage, preparation)
    harvested = []
    for index, (_job, execution, _uri) in enumerate(rows):
        harvested.append(transport.harvest_cell_after_terminal(
            cell_index=index,
            execution=execution,
            job=JOB,
            prepared=prepared[index],
            source_manifest_receipt=preparation_receipt,
            cell_preparation_receipt=preparation["prepared_cells"][index][
                "cell_object"
            ],
            parity_receipt=parity_receipt,
            prepared_execution_provenance=prepared_provenance,
            cell_execution_provenance=cell_provenance,
            terminal_loader=lambda _name, value=terminal_values[index]: value,
            inventory_loader=storage.inventory,
            object_loader=storage.load,
        ))
    aggregate = transport.aggregate_and_publish(
        harvested,
        preparation_manifest_receipt=preparation_receipt,
        parity_receipt=parity_receipt,
        prepared_execution_provenance=prepared_provenance,
        publish=storage.publish,
    )
    result = {
        "version": "lr8-full-source-shard-completion-v1",
        "attempt_id": transport.ATTEMPT_ID,
        "disposition": "score-free-training-source-frozen",
        "cell_count": len(harvested),
        "prepared_execution_provenance": prepared_provenance,
        "cell_execution_provenance": cell_provenance,
        "aggregate_manifest_object": aggregate["manifest_object"],
        "training_source_freeze_object": aggregate["freeze_object"],
        "smoke_prepared_parity_exact": True,
        "actual_score_queried": False,
        "historical_outcome_lease_acquired": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    _write_once(out / "aggregate-manifest.json", _canonical_json(aggregate["manifest"]))
    _write_once(out / "completion.json", _canonical_json(result))
    return result


def _canonicalize(raw: Path, output: Path) -> None:
    value = _load_json(raw, label="external JSON")
    _write_once(output, _canonical_json(value))


def _arguments() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    canonical = sub.add_parser("canonicalize-external-json")
    canonical.add_argument("--raw", type=Path, required=True)
    canonical.add_argument("--output", type=Path, required=True)
    inventory = sub.add_parser("inventory")
    inventory.add_argument("--prefix", required=True)
    inventory.add_argument("--output", type=Path, required=True)
    smoke = sub.add_parser("validate-smoke")
    smoke.add_argument("--smoke-dir", type=Path, required=True)
    reuse = sub.add_parser("validate-reuse")
    reuse.add_argument("--job", required=True)
    reuse.add_argument("--job-uid", required=True)
    reuse.add_argument("--job-metadata", type=Path, required=True)
    reuse.add_argument("--executions", type=Path, required=True)
    reuse.add_argument("--schedulers", type=Path, required=True)
    reuse.add_argument("--result-inventory", type=Path)
    build = sub.add_parser("validate-build")
    build.add_argument("--build-metadata", type=Path, required=True)
    build.add_argument("--build-id", required=True)
    build.add_argument("--code-sha", required=True)
    build.add_argument("--image", required=True)
    prep_contract = sub.add_parser("create-preparation-contract")
    prep_contract.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    prep_contract.add_argument("--job-metadata", type=Path, required=True)
    prep_contract.add_argument("--code-sha", required=True)
    prep_contract.add_argument("--build-id", required=True)
    prep_contract.add_argument("--image", required=True)
    cell_contract = sub.add_parser("create-cell-contract")
    cell_contract.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    cell_contract.add_argument("--job-metadata", type=Path, required=True)
    contract_args = sub.add_parser("contract-arguments")
    contract_args.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    contract_args.add_argument("--mode", choices=("prepare", "cell"), required=True)
    prepared_identity = sub.add_parser("prepared-identity")
    prepared_identity.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    prep_ledger = sub.add_parser("preparation-ledger-arguments")
    prep_ledger.add_argument("--ledger", type=Path, required=True)
    cell_ledger = sub.add_parser("validate-cell-ledger")
    cell_ledger.add_argument("--ledger", type=Path, required=True)
    poll = sub.add_parser("poll-state")
    poll.add_argument("--metadata", type=Path, required=True)
    finish_prepare = sub.add_parser("finish-preparation")
    finish_prepare.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    finish_prepare.add_argument("--ledger", type=Path, required=True)
    finish_prepare.add_argument("--metadata", type=Path, required=True)
    execution = sub.add_parser("execution-arguments")
    execution.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    finish = sub.add_parser("finish-cells")
    finish.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    finish.add_argument("--ledger", type=Path, required=True)
    finish.add_argument("--terminal-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments().parse_args(argv)
    if args.command == "canonicalize-external-json":
        _canonicalize(args.raw, args.output)
    elif args.command == "inventory":
        _write_once(args.output, _canonical_json(_Storage().inventory(args.prefix)))
    elif args.command == "validate-smoke":
        load_validated_smoke(args.smoke_dir)
    elif args.command == "validate-reuse":
        job = _load_json(args.job_metadata, label="job metadata")
        _job_identity(job, job=args.job, job_uid=args.job_uid)
        _validate_idle(_load_json(args.executions, label="execution census"))
        _validate_unscheduled(
            _load_json(args.schedulers, label="scheduler census"), job=args.job,
        )
        if args.result_inventory is not None and _load_json(
            args.result_inventory, label="result inventory",
        ) != []:
            raise LR8FullSourceFinishError("full-source result prefix is not empty")
    elif args.command == "validate-build":
        validate_build_metadata(
            _load_json(args.build_metadata, label="build metadata"),
            build_id=args.build_id,
            code_sha=args.code_sha,
            image=args.image,
        )
    elif args.command == "create-preparation-contract":
        create_launch_contract(
            mode="prepare",
            job_metadata=_load_json(args.job_metadata, label="job metadata"),
            code_sha=args.code_sha,
            build_id=args.build_id,
            image=args.image,
            output=args.output_dir / "preparation-launch-contract.json",
        )
    elif args.command == "create-cell-contract":
        completion = _load_json(
            args.output_dir / "preparation-completion.json",
            label="preparation completion",
        )
        prep = transport._receipt(  # noqa: SLF001
            completion["preparation_manifest_object"],
            label="preparation manifest object",
        )
        parity = transport._receipt(  # noqa: SLF001
            completion["smoke_parity_object"], label="smoke parity object",
        )
        source = _load_launch_contract(
            args.output_dir / "preparation-launch-contract.json", mode="prepare",
        )
        create_launch_contract(
            mode="cell",
            job_metadata=_load_json(args.job_metadata, label="job metadata"),
            code_sha=str(source["code_sha"]),
            build_id=str(source["build_id"]),
            image=str(source["image"]),
            output=args.output_dir / "cell-launch-contract.json",
            preparation_receipt=prep,
            parity_receipt=parity,
        )
    elif args.command == "contract-arguments":
        prep = parity = None
        if args.mode == "cell":
            completion = _load_json(
                args.output_dir / "preparation-completion.json",
                label="preparation completion",
            )
            prep = transport._receipt(  # noqa: SLF001
                completion["preparation_manifest_object"],
                label="preparation manifest object",
            )
            parity = transport._receipt(  # noqa: SLF001
                completion["smoke_parity_object"], label="smoke parity object",
            )
        contract = _load_launch_contract(
            args.output_dir / f"{args.mode.replace('prepare', 'preparation')}-launch-contract.json",
            mode=args.mode,
            preparation_receipt=prep,
            parity_receipt=parity,
        )
        for value in transport._provenance_cli_args(contract):  # noqa: SLF001
            print(value)
    elif args.command == "prepared-identity":
        contract = _load_launch_contract(
            args.output_dir / "preparation-launch-contract.json", mode="prepare",
        )
        for key in ("code_sha", "build_id", "image"):
            print(contract[key])
    elif args.command == "preparation-ledger-arguments":
        for value in parse_preparation_ledger(args.ledger):
            print(value)
    elif args.command == "validate-cell-ledger":
        _ledger(args.ledger)
    elif args.command == "poll-state":
        print(_completion_state(_load_json(args.metadata, label="execution metadata")))
    elif args.command == "finish-preparation":
        finish_preparation(
            out=args.output_dir,
            ledger_path=args.ledger,
            execution_metadata=_load_json(args.metadata, label="execution metadata"),
        )
    elif args.command == "execution-arguments":
        completion = _load_json(
            args.output_dir / "preparation-completion.json",
            label="preparation completion",
        )
        for receipt_name in (
            "preparation_manifest_object", "smoke_parity_object",
        ):
            receipt = transport._receipt(  # noqa: SLF001
                completion[receipt_name], label=receipt_name,
            )
            print(receipt.uri)
            print(receipt.generation)
            print(receipt.sha256)
            print(receipt.bytes)
    elif args.command == "finish-cells":
        finish_cells(
            out=args.output_dir,
            ledger_path=args.ledger,
            terminal_dir=args.terminal_dir,
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        LR8FullSourceFinishError,
        transport.LR8FullSourceTransportError,
        shard_core.LR8FullSourceShardError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
