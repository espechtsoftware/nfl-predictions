#!/usr/bin/env python3
"""Score-free preparation, cell solving, and aggregation for LR8 source shards.

This is a transport adapter around the already-frozen LR8 source law.  It
does not read realized target or candidate outcomes and it never acquires the
historical-outcome lease.  Preparation queries the score-free source once,
fits once per target season, materializes both registered replay blocks as one
season batch, and publishes exactly seventy generation-pinned prepared cells.
Each later Cloud Run execution solves exactly one prepared cell.  Only a
terminal-metadata-first harvester may pass those cell objects to the exact
registered-order aggregate.

Cloud/job orchestration lives in ``cloud_lr8_full_source_shards.sh``.  The
functions in this file take explicit callbacks so the immutable object and
terminal boundaries can be tested without BigQuery, GCS, Cloud Run, or CBC.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Final

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import run_lr8_training_source as source_runner  # noqa: E402
from nfl_dfs.research import lr8_full_source_shards as shard_core  # noqa: E402
from nfl_dfs.research import lr8_exact_solvers as exact_solvers  # noqa: E402
from nfl_dfs.research import lr8_training_source as training  # noqa: E402
from nfl_dfs.research import residual_world_columns as rw  # noqa: E402


TRANSPORT_VERSION: Final = "lr8-full-source-shard-transport-v1"
PREPARED_OBJECT_VERSION: Final = "lr8-full-source-prepared-object-v1"
PREPARATION_VERSION: Final = "lr8-full-source-preparation-v1"
ATTEMPT_VERSION: Final = "lr8-full-source-cell-attempt-v1"
SHARD_OBJECT_VERSION: Final = "lr8-full-source-cell-object-v1"
AGGREGATE_OBJECT_VERSION: Final = "lr8-full-source-aggregate-object-v1"
SMOKE_PARITY_VERSION: Final = "lr8-full-source-smoke-parity-v1"

ATTEMPT_ID: Final = "20260821-lr8-full-source-shards-v1"
PROJECT: Final = "nfl-predictions-503414"
BUCKET: Final = "nfl-predictions-503414-raw"
JOB: Final = "atlas-md-prefix-r4-smoke"
JOB_UID: Final = "51545eb0-59e4-424e-91c9-98dd318285f4"
SERVICE_ACCOUNT: Final = "817589974517-compute@developer.gserviceaccount.com"
CPU: Final = "8"
MEMORY: Final = "32Gi"
TIMEOUT_SECONDS: Final = "21600"
RESULT_PREFIX: Final = (
    f"gs://{BUCKET}/research/lr8-training-source/{ATTEMPT_ID}"
)
PREPARATION_URI: Final = RESULT_PREFIX + "/preparation-manifest.json"
FINAL_FREEZE_URI: Final = RESULT_PREFIX + "/training-source-freeze.json"
AGGREGATE_URI: Final = RESULT_PREFIX + "/aggregate-manifest.json"
SMOKE_PARITY_URI: Final = RESULT_PREFIX + "/smoke-prepared-parity.json"

SMOKE_ATTEMPT_ID: Final = "20260821-lr8-training-source-smoke-v2"
SMOKE_RESULT_PREFIX: Final = (
    f"gs://{BUCKET}/research/lr8-training-source/{SMOKE_ATTEMPT_ID}"
)
SMOKE_COMPLETION_VERSION: Final = "lr8-training-source-smoke-completion-v1"
SMOKE_COMPLETION_DISPOSITION: Final = "outcome-blind-real-source-smoke-passed"

ENABLED_ENV: Final = "LR8_FULL_SOURCE_SHARDS_ENABLED"
_SHA256_RE: Final = re.compile(r"[0-9a-f]{64}")
_COMMIT_RE: Final = re.compile(r"[0-9a-f]{40}")
_BUILD_RE: Final = re.compile(r"[0-9A-Za-z-]{8,80}")
_GENERATION_RE: Final = re.compile(r"[1-9][0-9]*")
_EXECUTION_RE: Final = re.compile(r"[a-z][a-z0-9-]{2,62}-[a-z0-9]{5}")


class LR8FullSourceTransportError(RuntimeError):
    """A fail-closed LR8 score-free transport violation."""


@dataclass(frozen=True, slots=True)
class PublishedObject:
    """Create-once publication result with the exact reopened bytes."""

    receipt: Mapping[str, object]
    reopened_raw: bytes
    created: bool


@dataclass(frozen=True, slots=True)
class PreparedPublication:
    """Complete generation-pinned preparation output."""

    prepared_cells: tuple[shard_core.PreparedCell, ...]
    cell_manifest_receipts: tuple[shard_core.ObjectReceipt, ...]
    draw_receipts: tuple[shard_core.ObjectReceipt, ...]
    manifest: Mapping[str, object]
    manifest_receipt: shard_core.ObjectReceipt


@dataclass(frozen=True, slots=True)
class SolvedPublication:
    """One solved cell and its create-once transport receipts."""

    shard: shard_core.CellShard
    shard_receipt: shard_core.ObjectReceipt
    attempt_receipt: shard_core.ObjectReceipt


@dataclass(frozen=True, slots=True)
class HarvestedCell:
    """A strict-terminal cell result admitted for final aggregation."""

    cell_index: int
    execution: str
    terminal_sha256: str
    shard: shard_core.CellShard
    shard_receipt: shard_core.ObjectReceipt
    attempt: Mapping[str, object]
    execution_provenance: Mapping[str, object]


Publisher = Callable[[str, bytes], PublishedObject]
SeasonReplayFactory = Callable[[int], Sequence[training.PITReplayBlock]]
TerminalLoader = Callable[[str], Mapping[str, object]]
InventoryLoader = Callable[[str], Sequence[Mapping[str, object]]]
ObjectLoader = Callable[[Mapping[str, object]], tuple[Mapping[str, object], bytes]]


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
        raise LR8FullSourceTransportError("value is not canonical JSON") from exc


def _strict_json(raw: bytes, *, label: str) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON constant: {value}")

    def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    try:
        return json.loads(
            raw,
            object_pairs_hook=strict_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise LR8FullSourceTransportError(f"{label} is not strict JSON") from exc


def _sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _strict_sha(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise LR8FullSourceTransportError(f"{label} is not a lowercase SHA-256")
    return value


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise LR8FullSourceTransportError(f"{label} must be an exact integer")
    result = int(value)
    if result < minimum:
        raise LR8FullSourceTransportError(f"{label} must be >= {minimum}")
    return result


def _signed_int(value: object, *, label: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise LR8FullSourceTransportError(f"{label} must be an exact integer")
    return int(value)


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise LR8FullSourceTransportError(f"{label} must be a canonical string")
    return value


def _prefix(value: str) -> str:
    result = _string(value, label="result prefix").rstrip("/")
    if not result.startswith("gs://") or result.count("/") < 3:
        raise LR8FullSourceTransportError("result prefix must be a GCS prefix")
    return result


def _receipt(
    value: Mapping[str, object] | shard_core.ObjectReceipt,
    *,
    label: str,
) -> shard_core.ObjectReceipt:
    try:
        return shard_core._receipt(value, label=label)  # noqa: SLF001
    except shard_core.LR8FullSourceShardError as exc:
        raise LR8FullSourceTransportError(str(exc)) from exc


def _published(
    value: PublishedObject,
    *,
    uri: str,
    raw: bytes,
    require_created: bool = False,
) -> shard_core.ObjectReceipt:
    if not isinstance(value, PublishedObject):
        raise LR8FullSourceTransportError("publisher returned the wrong type")
    receipt = _receipt(value.receipt, label="published object")
    if (
        receipt.uri != uri
        or receipt.sha256 != _sha(raw)
        or receipt.bytes != len(raw)
        or value.reopened_raw != raw
        or not isinstance(value.created, bool)
    ):
        raise LR8FullSourceTransportError("published object content differs")
    if require_created and value.created is not True:
        raise LR8FullSourceTransportError("create-once attempt already exists")
    return receipt


def cell_stem(cell_index: int) -> str:
    index = shard_core._exact_cell_index(cell_index)  # noqa: SLF001
    season, week, block = shard_core.EXPECTED_CELL_KEYS[index]
    return f"cell-{index:02d}-{season}-w{week:02d}-{block.lower()}"


def prepared_draw_uri(cell_index: int, *, prefix: str = RESULT_PREFIX) -> str:
    return f"{_prefix(prefix)}/prepared/{cell_stem(cell_index)}/draws.f32"


def prepared_manifest_uri(cell_index: int, *, prefix: str = RESULT_PREFIX) -> str:
    return f"{_prefix(prefix)}/prepared/{cell_stem(cell_index)}/cell.json"


def cell_attempt_uri(cell_index: int, *, prefix: str = RESULT_PREFIX) -> str:
    return f"{_prefix(prefix)}/cells/{cell_stem(cell_index)}/attempt.json"


def cell_shard_uri(cell_index: int, *, prefix: str = RESULT_PREFIX) -> str:
    return f"{_prefix(prefix)}/cells/{cell_stem(cell_index)}/shard.json"


def cell_result_prefix(cell_index: int, *, prefix: str = RESULT_PREFIX) -> str:
    return f"{_prefix(prefix)}/cells/{cell_stem(cell_index)}"


def preparation_job_args() -> tuple[str, ...]:
    return (
        "scripts/run_lr8_full_source_shards.py",
        "prepare-cloud",
        "--execute",
        "--project", PROJECT,
        "--bucket", BUCKET,
        "--catalog-table", f"{PROJECT}.nfl_predictions.slate_player_features",
        "--candidate-table",
        f"{PROJECT}.nfl_predictions.replay_candidates_staging",
        "--pit-table", f"{PROJECT}.nfl_features.player_week_training",
        "--tabpfn-table",
        f"{PROJECT}.nfl_features.{source_runner.TABPFN_TABLE_NAME}",
        "--location", "US",
    )


def _receipt_cli_args(stem: str, receipt: shard_core.ObjectReceipt) -> tuple[str, ...]:
    return (
        f"--{stem}-uri", receipt.uri,
        f"--{stem}-generation", receipt.generation,
        f"--{stem}-sha256", receipt.sha256,
        f"--{stem}-bytes", str(receipt.bytes),
    )


def cell_job_script(
    *,
    cell_index: int,
    preparation_receipt: shard_core.ObjectReceipt,
    parity_receipt: shard_core.ObjectReceipt,
    provenance_args: Sequence[str] = (),
) -> str:
    index = shard_core._exact_cell_index(cell_index)  # noqa: SLF001
    arguments = (
        "scripts/run_lr8_full_source_shards.py", "solve-cell-cloud",
        "--cell-index", str(index), "--execute", "--project", PROJECT,
        "--evidence-root", "/tmp/lr8-full-source-cell-evidence",
        *_receipt_cli_args("preparation", preparation_receipt),
        *_receipt_cli_args("parity", parity_receipt),
        *tuple(provenance_args),
    )
    if any(not isinstance(row, str) or not row or any(
        character.isspace() for character in row
    ) for row in arguments):
        raise LR8FullSourceTransportError("cell execution argument differs")
    return (
        "test ! -e /tmp/lr8-full-source-cell-evidence; "
        "mkdir /tmp/lr8-full-source-cell-evidence; exec python "
        + " ".join(arguments)
    )


def _provenance_cli_args(value: Mapping[str, object]) -> tuple[str, ...]:
    provenance = validate_execution_provenance(value)
    return (
        "--code-sha", str(provenance["code_sha"]),
        "--build-id", str(provenance["build_id"]),
        "--image", str(provenance["image"]),
        "--job-name", str(provenance["job_name"]),
        "--job-uid", str(provenance["job_uid"]),
        "--job-generation", str(provenance["job_generation"]),
        "--job-spec-sha256", str(provenance["job_spec_sha256"]),
        "--job-contract-sha256", str(provenance["job_contract_sha256"]),
    )


def build_execution_provenance(
    *,
    mode: str,
    code_sha: str,
    build_id: str,
    image: str,
    job_generation: str,
    job_spec_sha256: str,
    preparation_receipt: shard_core.ObjectReceipt | None = None,
    parity_receipt: shard_core.ObjectReceipt | None = None,
) -> dict[str, object]:
    if mode not in {"prepare", "cell"}:
        raise LR8FullSourceTransportError("execution provenance mode differs")
    if _COMMIT_RE.fullmatch(code_sha) is None or _BUILD_RE.fullmatch(build_id) is None:
        raise LR8FullSourceTransportError("execution code/build identity differs")
    if not isinstance(image, str) or re.fullmatch(
        r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
        r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}", image,
    ) is None:
        raise LR8FullSourceTransportError("execution immutable image differs")
    if _GENERATION_RE.fullmatch(job_generation) is None:
        raise LR8FullSourceTransportError("job generation differs")
    _strict_sha(job_spec_sha256, label="job spec hash")
    if mode == "prepare":
        if preparation_receipt is not None or parity_receipt is not None:
            raise LR8FullSourceTransportError("prepare provenance has cell receipts")
        command = ["python"]
        arguments = list(preparation_job_args())
    else:
        if preparation_receipt is None or parity_receipt is None:
            raise LR8FullSourceTransportError("cell provenance lacks source receipts")
        command = ["bash"]
        arguments = ["-ceu", cell_job_script(
            cell_index=0,
            preparation_receipt=preparation_receipt,
            parity_receipt=parity_receipt,
        )]
    contract: dict[str, object] = {
        "mode": mode,
        "job_name": JOB,
        "job_uid": JOB_UID,
        "job_generation": job_generation,
        "job_spec_sha256": job_spec_sha256,
        "command": command,
        "args": arguments,
        "env": {
            "ANALYSIS_IMAGE": image,
            "CODE_SHA": code_sha,
            "LR8_BUILD_ID": build_id,
            ENABLED_ENV: "1",
        },
        "service_account": SERVICE_ACCOUNT,
        "resources": {"cpu": CPU, "memory": MEMORY},
        "task_count": 1,
        "parallelism": 1,
        "max_retries": 0,
        "timeout_seconds": TIMEOUT_SECONDS,
    }
    result: dict[str, object] = {
        "version": "lr8-full-source-execution-provenance-v1",
        "mode": mode,
        "code_sha": code_sha,
        "build_id": build_id,
        "image": image,
        **contract,
    }
    result["job_contract_sha256"] = training.canonical_sha256(contract)
    return validate_execution_provenance(result)


def validate_execution_provenance(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise LR8FullSourceTransportError("execution provenance must be an object")
    result = dict(value)
    expected_keys = {
        "version", "mode", "code_sha", "build_id", "image", "job_name",
        "job_uid", "job_generation", "job_spec_sha256", "command", "args",
        "env", "service_account", "resources", "task_count", "parallelism",
        "max_retries", "timeout_seconds", "job_contract_sha256",
    }
    if set(result) != expected_keys:
        raise LR8FullSourceTransportError("execution provenance keys differ")
    mode = result.get("mode")
    if (
        result.get("version") != "lr8-full-source-execution-provenance-v1"
        or mode not in {"prepare", "cell"}
        or not isinstance(result.get("code_sha"), str)
        or _COMMIT_RE.fullmatch(str(result["code_sha"])) is None
        or not isinstance(result.get("build_id"), str)
        or _BUILD_RE.fullmatch(str(result["build_id"])) is None
        or result.get("job_name") != JOB
        or result.get("job_uid") != JOB_UID
        or not isinstance(result.get("job_generation"), str)
        or _GENERATION_RE.fullmatch(str(result["job_generation"])) is None
        or result.get("service_account") != SERVICE_ACCOUNT
        or result.get("resources") != {"cpu": CPU, "memory": MEMORY}
        or result.get("timeout_seconds") != TIMEOUT_SECONDS
    ):
        raise LR8FullSourceTransportError("execution provenance identity differs")
    for key, expected in (
        ("task_count", 1), ("parallelism", 1), ("max_retries", 0),
    ):
        if _exact_int(result.get(key), label=f"execution {key}") != expected:
            raise LR8FullSourceTransportError(
                "execution provenance identity differs"
            )
    _strict_sha(result.get("job_spec_sha256"), label="job spec hash")
    image = result.get("image")
    if not isinstance(image, str) or re.fullmatch(
        r"us-central1-docker\.pkg\.dev/nfl-predictions-503414/"
        r"nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}", image,
    ) is None:
        raise LR8FullSourceTransportError("execution provenance image differs")
    if (
        not isinstance(result.get("command"), list)
        or not isinstance(result.get("args"), list)
        or any(not isinstance(row, str) or not row for row in result["command"])
        or any(not isinstance(row, str) or not row for row in result["args"])
        or not isinstance(result.get("env"), dict)
    ):
        raise LR8FullSourceTransportError("execution command/env contract differs")
    contract = {
        key: result[key] for key in (
            "mode", "job_name", "job_uid", "job_generation",
            "job_spec_sha256", "command", "args", "env", "service_account",
            "resources", "task_count", "parallelism", "max_retries",
            "timeout_seconds",
        )
    }
    if _strict_sha(
        result.get("job_contract_sha256"), label="job contract hash",
    ) != training.canonical_sha256(contract):
        raise LR8FullSourceTransportError("job contract hash differs")
    expected_env = {
        "ANALYSIS_IMAGE": image,
        "CODE_SHA": result["code_sha"],
        "LR8_BUILD_ID": result["build_id"],
        ENABLED_ENV: "1",
    }
    if result["env"] != expected_env:
        raise LR8FullSourceTransportError("execution environment differs")
    return result


def _prepared_object_payload(
    prepared: shard_core.PreparedCell,
    *,
    draw_receipt: shard_core.ObjectReceipt,
) -> dict[str, object]:
    shard_core._validate_prepared(prepared)  # noqa: SLF001
    if (
        draw_receipt.sha256 != prepared.player_draws_bytes_sha256
        or draw_receipt.bytes != len(prepared.player_draws_bytes)
    ):
        raise LR8FullSourceTransportError("prepared draw receipt differs")
    return {
        "version": PREPARED_OBJECT_VERSION,
        "prepared": shard_core._prepared_payload(prepared),  # noqa: SLF001
        "prepared_cell_sha256": prepared.prepared_cell_sha256,
        "draw_object": draw_receipt.as_dict(),
        "target_player_labels_read": False,
        "candidate_labels_read": False,
        "actual_score_queried": False,
        "historical_outcome_lease_acquired": False,
        "production_change_licensed": False,
    }


def _prepared_object_bytes(
    prepared: shard_core.PreparedCell,
    *,
    draw_receipt: shard_core.ObjectReceipt,
) -> bytes:
    return _canonical_json(_prepared_object_payload(
        prepared, draw_receipt=draw_receipt,
    ))


def _prepared_from_object(
    raw: bytes,
    *,
    draw_metadata: Mapping[str, object],
    draw_raw: bytes,
) -> shard_core.PreparedCell:
    value = _strict_json(raw, label="prepared cell object")
    if not isinstance(value, dict) or set(value) != {
        "version", "prepared", "prepared_cell_sha256", "draw_object",
        "target_player_labels_read", "candidate_labels_read",
        "actual_score_queried", "historical_outcome_lease_acquired",
        "production_change_licensed",
    }:
        raise LR8FullSourceTransportError("prepared cell object keys differ")
    if value["version"] != PREPARED_OBJECT_VERSION:
        raise LR8FullSourceTransportError("prepared cell object version differs")
    for key in (
        "target_player_labels_read", "candidate_labels_read",
        "actual_score_queried", "historical_outcome_lease_acquired",
        "production_change_licensed",
    ):
        if not isinstance(value[key], bool) or value[key] is not False:
            raise LR8FullSourceTransportError(f"prepared cell {key} must be false")
    payload = value["prepared"]
    if not isinstance(payload, dict):
        raise LR8FullSourceTransportError("prepared cell payload differs")
    draw_receipt = _receipt(value["draw_object"], label="prepared draw object")
    metadata_receipt = _receipt(draw_metadata, label="loaded prepared draw")
    if draw_receipt != metadata_receipt or (
        draw_receipt.sha256 != _sha(draw_raw)
        or draw_receipt.bytes != len(draw_raw)
    ):
        raise LR8FullSourceTransportError("generation-pinned prepared draw differs")
    try:
        players = tuple(rw.PlayerSpec.from_mapping(row) for row in payload["catalog"])
        prepared = shard_core.PreparedCell(
            version=str(payload["version"]),
            cell_index=_exact_int(payload["cell_index"], label="cell index"),
            season=_exact_int(payload["season"], label="season"),
            week=_exact_int(payload["week"], label="week"),
            block=_string(payload["block"], label="block"),
            players=players,
            incumbent_candidates=tuple(
                tuple(row) for row in payload["incumbent_candidates"]
            ),
            catalog_sha256=_strict_sha(
                payload["catalog_sha256"], label="catalog hash",
            ),
            incumbent_candidates_sha256=_strict_sha(
                payload["incumbent_candidates_sha256"],
                label="incumbent hash",
            ),
            catalog_source_receipts=tuple(_receipt(
                row, label="catalog source receipt",
            ) for row in payload["catalog_source_receipts"]),
            incumbent_source_receipts=tuple(_receipt(
                row, label="incumbent source receipt",
            ) for row in payload["incumbent_source_receipts"]),
            projection_seed=_exact_int(
                payload["projection_seed"], label="projection seed",
            ),
            source_environment_role_seed_nonoperative=_exact_int(
                payload["source_environment_role_seed_nonoperative"],
                label="nonoperative role seed",
            ),
            replay_path_id=_string(
                payload["replay_path_id"], label="replay path",
            ),
            model_training_seasons=tuple(_exact_int(
                row, label="training season",
            ) for row in payload["model_training_seasons"]),
            model_fit_input_sha256=_strict_sha(
                payload["model_fit_input_sha256"], label="fit input hash",
            ),
            model_fit_sha256=_strict_sha(
                payload["model_fit_sha256"], label="fit hash",
            ),
            fit_source_receipts=tuple(_receipt(
                row, label="fit source receipt",
            ) for row in payload["fit_source_receipts"]),
            player_ids=tuple(payload["player_ids"]),
            player_ids_sha256=_strict_sha(
                payload["player_ids_sha256"], label="player ids hash",
            ),
            player_draws_dtype=str(payload["player_draws"]["dtype"]),
            player_draws_shape=tuple(_exact_int(
                row, label="draw dimension", minimum=1,
            ) for row in payload["player_draws"]["shape"]),
            player_draws_bytes=draw_raw,
            player_draws_bytes_sha256=_strict_sha(
                payload["player_draws"]["bytes_sha256"],
                label="draw byte hash",
            ),
            player_draws_sha256=_strict_sha(
                payload["player_draws"]["array_sha256"],
                label="draw array hash",
            ),
            draw_source_receipts=tuple(_receipt(
                row, label="draw source receipt",
            ) for row in payload["draw_source_receipts"]),
            prepared_cell_sha256=_strict_sha(
                value["prepared_cell_sha256"], label="prepared cell hash",
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LR8FullSourceTransportError(
            "prepared cell payload is malformed"
        ) from exc
    try:
        shard_core._validate_prepared(prepared)  # noqa: SLF001
    except shard_core.LR8FullSourceShardError as exc:
        raise LR8FullSourceTransportError(str(exc)) from exc
    if _prepared_object_bytes(prepared, draw_receipt=draw_receipt) != raw:
        raise LR8FullSourceTransportError("prepared cell serialization differs")
    return prepared


def _validate_replay_season(
    season: int,
    values: Sequence[training.PITReplayBlock],
) -> tuple[training.PITReplayBlock, ...]:
    blocks = tuple(values)
    if tuple(block.block for block in blocks) != training.BLOCK_ORDER:
        raise LR8FullSourceTransportError("season replay block order differs")
    expected_weeks = training.EXPECTED_WEEKS[season]
    for block in blocks:
        if (
            block.target_season != season
            or tuple((row.season, row.week) for row in block.slates)
            != tuple((season, week) for week in expected_weeks)
            or block.model_training_seasons
            != training.MODEL_TRAINING_SEASONS[season]
            or block.replay_path_id != training.PIT_REPLAY_PATH_ID
            or block.target_player_labels_read is not False
            or block.candidate_labels_read is not False
            or block.role_belief_worlds_used is not False
            or block.b1_inputs_used is not False
            or block.a2a_inputs_used is not False
            or block.later_period_inputs_used is not False
        ):
            raise LR8FullSourceTransportError("season replay contract differs")
    if (
        len({block.model_fit_input_sha256 for block in blocks}) != 1
        or len({block.model_fit_sha256 for block in blocks}) != 1
        or len({training.canonical_sha256(list(block.fit_source_receipts))
                for block in blocks}) != 1
    ):
        raise LR8FullSourceTransportError("season replay did not share one fit")
    return blocks


def prepare_and_publish_cells(
    canonical_sources: Sequence[training.CanonicalSlateSource],
    *,
    season_replay_factory: SeasonReplayFactory,
    publish: Publisher,
    execution_provenance: Mapping[str, object],
    output_prefix: str = RESULT_PREFIX,
) -> PreparedPublication:
    """Prepare and create-once publish the exact 70 score-free cells.

    ``season_replay_factory`` is called exactly once for 2019 and once for
    2021.  Each call must return both whole-season R0/R1 blocks sharing one
    fitted-model identity.  This prevents accidental per-week replay/refits
    and preserves the registered season-wide RNG order.
    """
    if not callable(season_replay_factory) or not callable(publish):
        raise LR8FullSourceTransportError("preparation callbacks must be callable")
    provenance = validate_execution_provenance(execution_provenance)
    if provenance["mode"] != "prepare":
        raise LR8FullSourceTransportError("preparation provenance mode differs")
    prefix = _prefix(output_prefix)
    sources = tuple(canonical_sources)
    if tuple((row.season, row.week) for row in sources) != (
        training.EXPECTED_SLATE_KEYS
    ):
        raise LR8FullSourceTransportError("canonical source order differs")
    source_by_key = {(row.season, row.week): row for row in sources}

    blocks_by_key: dict[tuple[int, str], training.PITReplayBlock] = {}
    replay_invocations: list[int] = []
    for season in training.TARGET_SEASONS:
        replay_invocations.append(season)
        blocks = _validate_replay_season(
            season, season_replay_factory(season),
        )
        for block in blocks:
            blocks_by_key[(season, block.block)] = block

    prepared_cells: list[shard_core.PreparedCell] = []
    cell_receipts: list[shard_core.ObjectReceipt] = []
    draw_receipts: list[shard_core.ObjectReceipt] = []
    for index, (season, week, block_name) in enumerate(
        shard_core.EXPECTED_CELL_KEYS
    ):
        block = blocks_by_key[(season, block_name)]
        slate = block.slates[training.EXPECTED_WEEKS[season].index(week)]
        prepared = shard_core.prepare_cell(
            cell_index=index,
            canonical_source=source_by_key[(season, week)],
            replay=shard_core.PITCellReplay(
                target_season=season,
                block=block_name,
                projection_seed=block.projection_seed,
                source_environment_role_seed_nonoperative=(
                    block.source_environment_role_seed_nonoperative
                ),
                replay_path_id=block.replay_path_id,
                model_training_seasons=block.model_training_seasons,
                model_fit_input_sha256=block.model_fit_input_sha256,
                model_fit_sha256=block.model_fit_sha256,
                fit_source_receipts=block.fit_source_receipts,
                slate=slate,
                target_player_labels_read=block.target_player_labels_read,
                candidate_labels_read=block.candidate_labels_read,
                candidate_world_family=block.candidate_world_family,
                role_belief_worlds_used=block.role_belief_worlds_used,
                b1_inputs_used=block.b1_inputs_used,
                a2a_inputs_used=block.a2a_inputs_used,
                later_period_inputs_used=block.later_period_inputs_used,
            ),
        )
        draw_uri = prepared_draw_uri(index, prefix=prefix)
        draw_receipt = _published(
            publish(draw_uri, prepared.player_draws_bytes),
            uri=draw_uri,
            raw=prepared.player_draws_bytes,
        )
        cell_raw = _prepared_object_bytes(
            prepared, draw_receipt=draw_receipt,
        )
        cell_uri = prepared_manifest_uri(index, prefix=prefix)
        cell_receipt = _published(
            publish(cell_uri, cell_raw), uri=cell_uri, raw=cell_raw,
        )
        prepared_cells.append(prepared)
        draw_receipts.append(draw_receipt)
        cell_receipts.append(cell_receipt)

    manifest: dict[str, object] = {
        "version": PREPARATION_VERSION,
        "attempt_id": ATTEMPT_ID,
        "transport_version": TRANSPORT_VERSION,
        "execution_provenance": provenance,
        "canonical_panel_id": training.CANONICAL_PANEL_ID,
        "season_replay_invocations": replay_invocations,
        "fit_count": len(training.TARGET_SEASONS),
        "prepared_cell_count": len(prepared_cells),
        "cell_order": [list(row) for row in shard_core.EXPECTED_CELL_KEYS],
        "prepared_cells": [{
            "cell_index": row.cell_index,
            "season": row.season,
            "week": row.week,
            "block": row.block,
            "prepared_cell_sha256": row.prepared_cell_sha256,
            "cell_object": cell_receipts[row.cell_index].as_dict(),
            "draw_object": draw_receipts[row.cell_index].as_dict(),
        } for row in prepared_cells],
        "target_player_labels_read": False,
        "candidate_labels_read": False,
        "actual_score_queried": False,
        "historical_outcome_lease_acquired": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    manifest["manifest_sha256"] = training.canonical_sha256(manifest)
    manifest_raw = _canonical_json(manifest)
    manifest_uri = f"{prefix}/preparation-manifest.json"
    manifest_receipt = _published(
        publish(manifest_uri, manifest_raw),
        uri=manifest_uri,
        raw=manifest_raw,
    )
    return PreparedPublication(
        prepared_cells=tuple(prepared_cells),
        cell_manifest_receipts=tuple(cell_receipts),
        draw_receipts=tuple(draw_receipts),
        manifest=manifest,
        manifest_receipt=manifest_receipt,
    )


def validate_preparation_manifest(value: object) -> dict[str, object]:
    """Validate the exact complete preparation manifest without body reads."""
    if not isinstance(value, dict):
        raise LR8FullSourceTransportError("preparation manifest must be an object")
    manifest = dict(value)
    expected_keys = {
        "version", "attempt_id", "transport_version", "canonical_panel_id",
        "execution_provenance",
        "season_replay_invocations", "fit_count", "prepared_cell_count",
        "cell_order", "prepared_cells", "target_player_labels_read",
        "candidate_labels_read", "actual_score_queried",
        "historical_outcome_lease_acquired", "historical_scoring_licensed",
        "production_change_licensed", "manifest_sha256",
    }
    if set(manifest) != expected_keys:
        raise LR8FullSourceTransportError("preparation manifest keys differ")
    digest = _strict_sha(manifest.pop("manifest_sha256"), label="manifest hash")
    if training.canonical_sha256(manifest) != digest:
        raise LR8FullSourceTransportError("preparation manifest hash differs")
    manifest["manifest_sha256"] = digest
    if (
        manifest["version"] != PREPARATION_VERSION
        or manifest["attempt_id"] != ATTEMPT_ID
        or manifest["transport_version"] != TRANSPORT_VERSION
        or manifest["canonical_panel_id"] != training.CANONICAL_PANEL_ID
        or manifest["season_replay_invocations"] != list(training.TARGET_SEASONS)
        or manifest["fit_count"] != len(training.TARGET_SEASONS)
        or manifest["prepared_cell_count"] != shard_core.EXPECTED_CELLS
        or manifest["cell_order"]
        != [list(row) for row in shard_core.EXPECTED_CELL_KEYS]
    ):
        raise LR8FullSourceTransportError("preparation manifest identity differs")
    provenance = validate_execution_provenance(manifest["execution_provenance"])
    if provenance["mode"] != "prepare":
        raise LR8FullSourceTransportError("preparation provenance mode differs")
    for key in (
        "target_player_labels_read", "candidate_labels_read",
        "actual_score_queried", "historical_outcome_lease_acquired",
        "historical_scoring_licensed", "production_change_licensed",
    ):
        if not isinstance(manifest[key], bool) or manifest[key] is not False:
            raise LR8FullSourceTransportError(f"preparation {key} must be false")
    cells = manifest["prepared_cells"]
    if not isinstance(cells, list) or len(cells) != shard_core.EXPECTED_CELLS:
        raise LR8FullSourceTransportError("preparation cell count differs")
    seen_receipts: set[shard_core.ObjectReceipt] = set()
    for index, (row, key) in enumerate(zip(cells, shard_core.EXPECTED_CELL_KEYS)):
        if not isinstance(row, dict) or set(row) != {
            "cell_index", "season", "week", "block",
            "prepared_cell_sha256", "cell_object", "draw_object",
        }:
            raise LR8FullSourceTransportError("preparation cell row differs")
        if (row["cell_index"], row["season"], row["week"], row["block"]) != (
            index, *key,
        ):
            raise LR8FullSourceTransportError("preparation cell order differs")
        _strict_sha(row["prepared_cell_sha256"], label="prepared cell hash")
        expected_uris = (
            prepared_manifest_uri(index), prepared_draw_uri(index),
        )
        for name, uri in zip(("cell_object", "draw_object"), expected_uris):
            receipt = _receipt(row[name], label=f"prepared {name}")
            if receipt.uri != uri or receipt in seen_receipts:
                raise LR8FullSourceTransportError(
                    "preparation receipt identity differs"
                )
            seen_receipts.add(receipt)
    return manifest


def validate_smoke_parity(
    *,
    smoke_completion: Mapping[str, object],
    smoke_solve_freeze: Mapping[str, object],
    prepared_cell: shard_core.PreparedCell,
) -> dict[str, object]:
    """Require the passed real smoke and exact prepared 2019-W1/R0 parity."""
    completion = dict(smoke_completion)
    freeze = dict(smoke_solve_freeze)
    if (
        completion.get("version") != SMOKE_COMPLETION_VERSION
        or completion.get("attempt_id") != SMOKE_ATTEMPT_ID
        or completion.get("disposition") != SMOKE_COMPLETION_DISPOSITION
        or completion.get("smoke_solve_freeze_sha256")
        != sha256(_canonical_json(freeze)).hexdigest()
        or completion.get("historical_outcome_lease_acquired") is not False
        or completion.get("uses_realized_target_or_candidate_outcomes") is not False
        or completion.get("production_change_licensed") is not False
    ):
        raise LR8FullSourceTransportError("real LR8 smoke has not passed cleanly")
    execution = completion.get("execution")
    if not isinstance(execution, dict) or execution.get("state") != "True" or (
        execution.get("counters")
        != {"succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0}
    ):
        raise LR8FullSourceTransportError("real LR8 smoke terminal proof differs")
    try:
        shard_core._validate_prepared(prepared_cell)  # noqa: SLF001
    except shard_core.LR8FullSourceShardError as exc:
        raise LR8FullSourceTransportError(str(exc)) from exc
    expected = {
        "season": prepared_cell.season,
        "week": prepared_cell.week,
        "block": prepared_cell.block,
        "projection_seed": prepared_cell.projection_seed,
        "source_environment_role_seed_nonoperative": (
            prepared_cell.source_environment_role_seed_nonoperative
        ),
        "player_ids_sha256": prepared_cell.player_ids_sha256,
        "player_draws_sha256": prepared_cell.player_draws_sha256,
        "catalog_sha256": prepared_cell.catalog_sha256,
        "incumbent_candidates_sha256": (
            prepared_cell.incumbent_candidates_sha256
        ),
    }
    observed = {
        "season": freeze.get("season"),
        "week": freeze.get("week"),
        "block": freeze.get("block"),
        "projection_seed": freeze.get("projection_seed"),
        "source_environment_role_seed_nonoperative": freeze.get(
            "source_environment_role_seed_nonoperative"
        ),
        "player_ids_sha256": freeze.get("player_ids_sha256"),
        "player_draws_sha256": (
            freeze.get("player_draws", {}).get("sha256")
            if isinstance(freeze.get("player_draws"), dict) else None
        ),
        "catalog_sha256": freeze.get("catalog_sha256"),
        "incumbent_candidates_sha256": freeze.get(
            "incumbent_candidates_sha256"
        ),
    }
    if expected != observed or (prepared_cell.season, prepared_cell.week,
                                prepared_cell.block) != (2019, 1, "R0"):
        raise LR8FullSourceTransportError(
            "prepared 2019-W1/R0 does not exactly match the real smoke"
        )
    result: dict[str, object] = {
        "version": SMOKE_PARITY_VERSION,
        "smoke_attempt_id": SMOKE_ATTEMPT_ID,
        "full_source_attempt_id": ATTEMPT_ID,
        "cell_index": 0,
        "exact_identity": expected,
        "smoke_completion_sha256": training.canonical_sha256(completion),
        "smoke_solve_freeze_sha256": training.canonical_sha256(freeze),
        "prepared_cell_sha256": prepared_cell.prepared_cell_sha256,
        "parity_exact": True,
        "cell_execution_licensed": True,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    result["parity_sha256"] = training.canonical_sha256(result)
    return result


def _attempt_payload(
    prepared: shard_core.PreparedCell,
    preparation_receipt: shard_core.ObjectReceipt,
    *,
    prepared_execution_provenance: Mapping[str, object],
    cell_execution_provenance: Mapping[str, object],
    execution: str,
    job: str,
    task_index: int,
    task_attempt: int,
    output_prefix: str,
) -> dict[str, object]:
    prepared_provenance = validate_execution_provenance(
        prepared_execution_provenance
    )
    cell_provenance = validate_execution_provenance(cell_execution_provenance)
    if (
        prepared_provenance["mode"] != "prepare"
        or cell_provenance["mode"] != "cell"
        or any(cell_provenance[key] != prepared_provenance[key] for key in (
            "code_sha", "build_id", "image", "job_name", "job_uid",
        ))
    ):
        raise LR8FullSourceTransportError("attempt provenance chain differs")
    runtime_task_index = _exact_int(task_index, label="cell task index")
    runtime_task_attempt = _exact_int(task_attempt, label="cell task attempt")
    if (
        job != JOB
        or cell_provenance["job_name"] != job
        or _EXECUTION_RE.fullmatch(execution) is None
        or not execution.startswith(job + "-")
        or runtime_task_index != 0
        or runtime_task_attempt != 0
    ):
        raise LR8FullSourceTransportError("cell runtime execution identity differs")
    return {
        "version": ATTEMPT_VERSION,
        "attempt_id": ATTEMPT_ID,
        "cell_index": prepared.cell_index,
        "season": prepared.season,
        "week": prepared.week,
        "block": prepared.block,
        "attempt_uri": cell_attempt_uri(
            prepared.cell_index, prefix=output_prefix,
        ),
        "execution": execution,
        "job": job,
        "task_index": runtime_task_index,
        "task_attempt": runtime_task_attempt,
        "prepared_cell_sha256": prepared.prepared_cell_sha256,
        "preparation_object": preparation_receipt.as_dict(),
        "prepared_execution_provenance": prepared_provenance,
        "cell_execution_provenance": cell_provenance,
        "create_once_asserted": True,
        "automatic_retry_licensed": False,
        "one_task": True,
        "max_retries": 0,
        "target_player_labels_read": False,
        "candidate_labels_read": False,
        "actual_score_queried": False,
        "historical_outcome_lease_acquired": False,
        "production_change_licensed": False,
    }


def validate_attempt_payload(
    value: object,
    *,
    prepared: shard_core.PreparedCell,
    preparation_receipt: shard_core.ObjectReceipt,
    execution: str,
    job: str,
    prepared_execution_provenance: Mapping[str, object],
    cell_execution_provenance: Mapping[str, object],
    output_prefix: str = RESULT_PREFIX,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise LR8FullSourceTransportError("cell attempt must be an object")
    attempt = dict(value)
    expected = _attempt_payload(
        prepared,
        preparation_receipt,
        prepared_execution_provenance=prepared_execution_provenance,
        cell_execution_provenance=cell_execution_provenance,
        execution=execution,
        job=job,
        task_index=0,
        task_attempt=0,
        output_prefix=_prefix(output_prefix),
    )
    if (
        set(attempt) != set(expected)
        or _canonical_json(attempt) != _canonical_json(expected)
    ):
        raise LR8FullSourceTransportError(
            "cell attempt schema or execution binding differs"
        )
    return attempt


def _block_payload(block: training.FrozenBlockSource) -> dict[str, object]:
    return {
        "block": block.block,
        "projection_seed": block.projection_seed,
        "source_environment_role_seed_nonoperative": (
            block.source_environment_role_seed_nonoperative
        ),
        "player_ids": list(block.player_ids),
        "player_ids_sha256": block.player_ids_sha256,
        "player_draws_sha256": block.player_draws_sha256,
        "world_order": list(block.world_order),
        "world_order_sha256": block.world_order_sha256,
        "source_receipts": list(block.source_receipts),
        "solve_attempts": [
            shard_core._attempt_payload(row)  # noqa: SLF001
            for row in block.solve_attempts
        ],
        "solve_attempts_sha256": block.solve_attempts_sha256,
        "candidates": [
            shard_core._candidate_payload(row)  # noqa: SLF001
            for row in block.candidates
        ],
        "candidate_identities_sha256": block.candidate_identities_sha256,
        "anatomy_sha256": block.anatomy_sha256,
        "legality_sha256": block.legality_sha256,
    }


def _block_from_payload(
    value: object,
    *,
    prepared: shard_core.PreparedCell,
) -> training.FrozenBlockSource:
    if not isinstance(value, dict):
        raise LR8FullSourceTransportError("frozen block payload differs")
    try:
        draws = shard_core._draws_from_prepared(prepared)  # noqa: SLF001
        attempts = tuple(training.SolveAttempt(
            block=row["block"],
            projection_seed=_exact_int(
                row["projection_seed"], label="attempt projection seed",
            ),
            world_index=_exact_int(row["world_index"], label="world index"),
            roster=tuple(row["roster"]),
            objective_micro=_signed_int(
                row["objective_micro"], label="objective",
            ),
            admitted_unique=row["admitted_unique"],
            request_sha256=_strict_sha(
                row["request_sha256"], label="request hash",
            ),
            evidence_receipts=tuple(dict(receipt) for receipt in row[
                "evidence_receipts"
            ]),
            evidence_manifest_sha256=_strict_sha(
                row["evidence_manifest_sha256"], label="evidence hash",
            ),
        ) for row in value["solve_attempts"])
        candidates = tuple(training.FrozenCandidate(
            season=_exact_int(row["season"], label="candidate season"),
            week=_exact_int(row["week"], label="candidate week"),
            roster=tuple(row["roster"]),
            anatomy_features=tuple(float(item) for item in row[
                "anatomy_features"
            ]),
            first_source_block=row["first_source_block"],
            first_source_world_index=_exact_int(
                row["first_source_world_index"], label="first source world",
            ),
            source_occurrences=tuple(
                (item[0], _exact_int(item[1], label="source world"))
                for item in row["source_occurrences"]
            ),
        ) for row in value["candidates"])
        block = training.FrozenBlockSource(
            block=value["block"],
            projection_seed=_exact_int(
                value["projection_seed"], label="block projection seed",
            ),
            source_environment_role_seed_nonoperative=_exact_int(
                value["source_environment_role_seed_nonoperative"],
                label="block nonoperative role seed",
            ),
            player_ids=tuple(value["player_ids"]),
            player_draws=draws,
            player_ids_sha256=_strict_sha(
                value["player_ids_sha256"], label="block player ids hash",
            ),
            player_draws_sha256=_strict_sha(
                value["player_draws_sha256"], label="block draw hash",
            ),
            world_order=tuple(_exact_int(
                row, label="world order index",
            ) for row in value["world_order"]),
            world_order_sha256=_strict_sha(
                value["world_order_sha256"], label="world order hash",
            ),
            source_receipts=tuple(dict(row) for row in value["source_receipts"]),
            solve_attempts=attempts,
            solve_attempts_sha256=_strict_sha(
                value["solve_attempts_sha256"], label="solve attempts hash",
            ),
            candidates=candidates,
            candidate_identities_sha256=_strict_sha(
                value["candidate_identities_sha256"],
                label="candidate identities hash",
            ),
            anatomy_sha256=_strict_sha(
                value["anatomy_sha256"], label="anatomy hash",
            ),
            legality_sha256=_strict_sha(
                value["legality_sha256"], label="legality hash",
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LR8FullSourceTransportError("frozen block payload is malformed") from exc
    return block


def _shard_object_bytes(shard: shard_core.CellShard) -> bytes:
    shard_core._validate_shard(shard)  # noqa: SLF001
    payload = {
        "version": SHARD_OBJECT_VERSION,
        "cell_index": shard.prepared.cell_index,
        "prepared_cell_sha256": shard.prepared.prepared_cell_sha256,
        "preparation_receipt": shard.preparation_receipt.as_dict(),
        "execution_attempt_receipt": shard.execution_attempt_receipt.as_dict(),
        "accepted": shard.accepted,
        "frozen_block": _block_payload(shard.frozen_block),
        "frozen_block_sha256": shard.frozen_block_sha256,
        "shard_sha256": shard.shard_sha256,
        "actual_score_queried": False,
        "historical_outcome_lease_acquired": False,
        "production_change_licensed": False,
    }
    return _canonical_json(payload)


def _shard_from_object(
    raw: bytes,
    *,
    prepared: shard_core.PreparedCell,
) -> shard_core.CellShard:
    value = _strict_json(raw, label="cell shard object")
    if not isinstance(value, dict) or value.get("version") != SHARD_OBJECT_VERSION:
        raise LR8FullSourceTransportError("cell shard object version differs")
    for key in (
        "actual_score_queried", "historical_outcome_lease_acquired",
        "production_change_licensed",
    ):
        if value.get(key) is not False:
            raise LR8FullSourceTransportError(f"cell shard {key} must be false")
    if (
        value.get("cell_index") != prepared.cell_index
        or value.get("prepared_cell_sha256") != prepared.prepared_cell_sha256
        or value.get("accepted") is not True
    ):
        raise LR8FullSourceTransportError("cell shard identity differs")
    block = _block_from_payload(value.get("frozen_block"), prepared=prepared)
    try:
        shard = shard_core.wrap_cell_shard(
            prepared,
            block,
            preparation_receipt=value["preparation_receipt"],
            execution_attempt_receipt=value["execution_attempt_receipt"],
            accepted=True,
        )
    except (KeyError, shard_core.LR8FullSourceShardError) as exc:
        raise LR8FullSourceTransportError(str(exc)) from exc
    if (
        shard.frozen_block_sha256 != value.get("frozen_block_sha256")
        or shard.shard_sha256 != value.get("shard_sha256")
        or _shard_object_bytes(shard) != raw
    ):
        raise LR8FullSourceTransportError("cell shard serialization differs")
    return shard


def solve_and_publish_cell(
    prepared: shard_core.PreparedCell,
    *,
    preparation_receipt: Mapping[str, object] | shard_core.ObjectReceipt,
    prepared_execution_provenance: Mapping[str, object],
    cell_execution_provenance: Mapping[str, object],
    execution: str,
    job: str,
    task_index: int,
    task_attempt: int,
    solve_world: training.WorldSolver,
    publish: Publisher,
    output_prefix: str = RESULT_PREFIX,
) -> SolvedPublication:
    """Create the no-retry attempt, solve one cell, then publish its shard."""
    if not callable(solve_world) or not callable(publish):
        raise LR8FullSourceTransportError("cell callbacks must be callable")
    prefix = _prefix(output_prefix)
    preparation = _receipt(preparation_receipt, label="preparation object")
    if preparation.uri != prepared_manifest_uri(
        prepared.cell_index, prefix=prefix,
    ):
        raise LR8FullSourceTransportError("cell preparation URI differs")
    attempt_payload = _attempt_payload(
        prepared,
        preparation,
        prepared_execution_provenance=prepared_execution_provenance,
        cell_execution_provenance=cell_execution_provenance,
        execution=execution,
        job=job,
        task_index=task_index,
        task_attempt=task_attempt,
        output_prefix=prefix,
    )
    attempt_raw = _canonical_json(attempt_payload)
    attempt_uri = cell_attempt_uri(prepared.cell_index, prefix=prefix)
    attempt = _published(
        publish(attempt_uri, attempt_raw),
        uri=attempt_uri,
        raw=attempt_raw,
        require_created=True,
    )
    try:
        shard = shard_core.solve_prepared_cell(
            prepared,
            solve_world,
            preparation_receipt=preparation,
            execution_attempt_receipt=attempt,
        )
    except shard_core.LR8FullSourceShardError as exc:
        raise LR8FullSourceTransportError(str(exc)) from exc
    shard_raw = _shard_object_bytes(shard)
    uri = cell_shard_uri(prepared.cell_index, prefix=prefix)
    shard_receipt = _published(
        publish(uri, shard_raw), uri=uri, raw=shard_raw,
    )
    return SolvedPublication(
        shard=shard,
        shard_receipt=shard_receipt,
        attempt_receipt=attempt,
    )


def strict_terminal(
    value: Mapping[str, object],
    *,
    execution: str,
    job: str,
    execution_provenance: Mapping[str, object],
    expected_command: Sequence[str],
    expected_args: Sequence[str],
) -> dict[str, object]:
    """Validate a one-task, zero-retry Cloud Run execution terminal."""
    if not isinstance(value, Mapping):
        raise LR8FullSourceTransportError("execution metadata must be an object")
    metadata = value.get("metadata")
    spec = value.get("spec")
    status = value.get("status")
    if not all(isinstance(row, Mapping) for row in (metadata, spec, status)):
        raise LR8FullSourceTransportError("execution metadata structure differs")
    if metadata.get("name") != execution or _EXECUTION_RE.fullmatch(execution) is None:
        raise LR8FullSourceTransportError("execution name differs")
    provenance = validate_execution_provenance(execution_provenance)
    labels = metadata.get("labels")
    if not isinstance(labels, Mapping) or (
        labels.get("run.googleapis.com/job") != job
        or labels.get("run.googleapis.com/jobUid") != provenance["job_uid"]
        or str(labels.get("run.googleapis.com/jobGeneration"))
        != provenance["job_generation"]
    ):
        raise LR8FullSourceTransportError("execution job binding differs")
    if (
        _exact_int(spec.get("taskCount"), label="execution task count") != 1
        or _exact_int(
            spec.get("parallelism"), label="execution parallelism",
        ) != 1
    ):
        raise LR8FullSourceTransportError("execution is not one-task serial")
    task = spec.get("template", {}).get("spec", {})
    if not isinstance(task, Mapping) or _exact_int(
        task.get("maxRetries"), label="execution max retries",
    ) != 0:
        raise LR8FullSourceTransportError("execution retry contract differs")
    containers = task.get("containers")
    if not isinstance(containers, list) or len(containers) != 1 or not isinstance(
        containers[0], Mapping
    ):
        raise LR8FullSourceTransportError("execution container contract differs")
    container = containers[0]
    env_rows = container.get("env", [])
    if not isinstance(env_rows, list) or any(
        not isinstance(row, Mapping) or set(row) != {"name", "value"}
        for row in env_rows
    ):
        raise LR8FullSourceTransportError("execution environment rows differ")
    env = {str(row["name"]): row["value"] for row in env_rows}
    if len(env) != len(env_rows) or (
        container.get("image") != provenance["image"]
        or container.get("command") != list(expected_command)
        or container.get("args") != list(expected_args)
        or env != provenance["env"]
        or task.get("serviceAccountName") != provenance["service_account"]
        or container.get("resources", {}).get("limits")
        != provenance["resources"]
        or task.get("timeoutSeconds") != provenance["timeout_seconds"]
    ):
        raise LR8FullSourceTransportError("execution command/spec binding differs")
    conditions = status.get("conditions", [])
    if not isinstance(conditions, list):
        raise LR8FullSourceTransportError("execution conditions differ")
    completed = [row for row in conditions if isinstance(row, Mapping)
                 and row.get("type") == "Completed"]
    if len(completed) != 1 or completed[0].get("status") != "True":
        raise LR8FullSourceTransportError("execution is not strict terminal success")
    counts = {
        short: _exact_int(
            status[key] if key in status else 0,
            label=f"execution {short} count",
        )
        for key, short in (
            ("succeededCount", "succeeded"),
            ("failedCount", "failed"),
            ("cancelledCount", "cancelled"),
            ("retriedCount", "retried"),
        )
    }
    if counts != {"succeeded": 1, "failed": 0, "cancelled": 0, "retried": 0}:
        raise LR8FullSourceTransportError("execution terminal counters differ")
    return {
        "execution": execution,
        "job": job,
        "state": "True",
        "counters": counts,
        "metadata_sha256": training.canonical_sha256(value),
    }


def _loaded_receipt(
    metadata: Mapping[str, object], raw: bytes, *, label: str,
) -> shard_core.ObjectReceipt:
    receipt = _receipt(metadata, label=label)
    if receipt.sha256 != _sha(raw) or receipt.bytes != len(raw):
        raise LR8FullSourceTransportError(f"{label} bytes differ")
    return receipt


def _inventory_identity(value: Mapping[str, object], *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise LR8FullSourceTransportError(f"{label} must be an object")
    uri = _string(value.get("uri"), label=f"{label} URI")
    generation = value.get("generation")
    if not isinstance(generation, str) or _GENERATION_RE.fullmatch(generation) is None:
        raise LR8FullSourceTransportError(f"{label} generation differs")
    size = _exact_int(value.get("bytes"), label=f"{label} bytes")
    return {"uri": uri, "generation": generation, "bytes": size}


def _validate_exact_evidence_bodies(
    shard: shard_core.CellShard,
    *,
    loaded: Mapping[str, tuple[shard_core.ObjectReceipt, bytes]],
    output_prefix: str,
) -> None:
    """Bind every exact proof claim to its generation-pinned CBC artifact."""
    cell_prefix = cell_result_prefix(
        shard.prepared.cell_index, prefix=output_prefix,
    )
    for attempt in shard.frozen_block.solve_attempts:
        receipts = tuple(_receipt(
            row, label="solve evidence receipt",
        ) for row in attempt.evidence_receipts)
        by_uri = {row.uri: row for row in receipts}
        base = f"{cell_prefix}/solver-evidence/{attempt.request_sha256}"
        proof_uri = base + "/proof.json"
        if proof_uri not in by_uri or proof_uri not in loaded:
            raise LR8FullSourceTransportError("exact solve proof is absent")
        proof = _strict_json(loaded[proof_uri][1], label="exact solve proof")
        if (
            not isinstance(proof, dict)
            or proof.get("schema") != exact_solvers.PROOF_SCHEMA
            or proof.get("solve_kind") != exact_solvers.TRAINING_SOLVE_KIND
            or proof.get("request_sha256") != attempt.request_sha256
        ):
            raise LR8FullSourceTransportError("exact solve proof identity differs")
        result = proof.get("result")
        if (
            not isinstance(result, dict)
            or result.get("roster") != list(attempt.roster)
            or result.get("objective_micro") != attempt.objective_micro
            or result.get("dk_classic_only") is not True
            or result.get("incumbent_no_goods_enforced") is not True
            or result.get("house_rules_applied") != []
        ):
            raise LR8FullSourceTransportError("exact solve proof result differs")
        cbc = proof.get("cbc_solve_evidence")
        if not isinstance(cbc, list) or not cbc:
            raise LR8FullSourceTransportError("exact solve proof lacks CBC evidence")
        expected_uris = {proof_uri}
        for evidence_index, row in enumerate(cbc):
            if (
                not isinstance(row, dict)
                or row.get("pulp_status") != 1
                or row.get("pulp_solution_status") != 1
                or row.get("threads") != 1
            ):
                raise LR8FullSourceTransportError("exact CBC proof status differs")
            expected = {
                f"{evidence_index:02d}-cbc.log": None,
                f"{evidence_index:02d}-model.sol": None,
                f"{evidence_index:02d}-model.mps": row.get("model_sha256"),
                f"{evidence_index:02d}-variable-domain-manifest.json": row.get(
                    "variable_domain_manifest_sha256"
                ),
            }
            if row.get("warm_start") is True:
                expected[f"{evidence_index:02d}-model.mst"] = row.get(
                    "mip_start_sha256"
                )
            elif row.get("mip_start_sha256") is not None:
                raise LR8FullSourceTransportError(
                    "cold exact CBC proof has a MIP start"
                )
            for suffix, expected_sha in expected.items():
                uri = f"{base}/{suffix}"
                expected_uris.add(uri)
                receipt = by_uri.get(uri)
                actual = loaded.get(uri)
                if receipt is None or actual is None or actual[0] != receipt:
                    raise LR8FullSourceTransportError(
                        "exact CBC artifact receipt is absent"
                    )
                if expected_sha is not None and (
                    _strict_sha(expected_sha, label="CBC artifact proof hash")
                    != actual[0].sha256
                ):
                    raise LR8FullSourceTransportError(
                        "exact CBC artifact proof differs"
                    )
        if set(by_uri) != expected_uris:
            raise LR8FullSourceTransportError(
                "exact solve evidence inventory differs"
            )


def harvest_cell_after_terminal(
    *,
    cell_index: int,
    execution: str,
    job: str,
    prepared: shard_core.PreparedCell,
    source_manifest_receipt: Mapping[str, object] | shard_core.ObjectReceipt,
    cell_preparation_receipt: (
        Mapping[str, object] | shard_core.ObjectReceipt
    ),
    parity_receipt: Mapping[str, object] | shard_core.ObjectReceipt,
    prepared_execution_provenance: Mapping[str, object],
    cell_execution_provenance: Mapping[str, object],
    terminal_loader: TerminalLoader,
    inventory_loader: InventoryLoader,
    object_loader: ObjectLoader,
    output_prefix: str = RESULT_PREFIX,
) -> HarvestedCell:
    """Read terminal metadata first, then generation-pinned cell bodies."""
    index = shard_core._exact_cell_index(cell_index)  # noqa: SLF001
    if index != prepared.cell_index:
        raise LR8FullSourceTransportError("harvest cell index differs")
    if not all(callable(row) for row in (
        terminal_loader, inventory_loader, object_loader,
    )):
        raise LR8FullSourceTransportError("harvest callbacks must be callable")

    prepared_provenance = validate_execution_provenance(
        prepared_execution_provenance
    )
    cell_provenance = validate_execution_provenance(cell_execution_provenance)
    if (
        prepared_provenance["mode"] != "prepare"
        or cell_provenance["mode"] != "cell"
        or any(cell_provenance[key] != prepared_provenance[key] for key in (
            "code_sha", "build_id", "image", "job_name", "job_uid",
        ))
    ):
        raise LR8FullSourceTransportError("cell execution provenance differs")
    source_manifest = _receipt(
        source_manifest_receipt, label="preparation manifest object",
    )
    preparation = _receipt(
        cell_preparation_receipt, label="prepared cell object",
    )
    parity = _receipt(parity_receipt, label="smoke parity object")
    if source_manifest.uri != f"{_prefix(output_prefix)}/preparation-manifest.json":
        raise LR8FullSourceTransportError("preparation manifest URI differs")
    if preparation.uri != prepared_manifest_uri(index, prefix=output_prefix):
        raise LR8FullSourceTransportError("prepared cell object URI differs")

    # Deliberate body-blind boundary: no inventory/body callback precedes this.
    terminal_value = terminal_loader(execution)
    terminal = strict_terminal(
        terminal_value,
        execution=execution,
        job=job,
        execution_provenance=cell_provenance,
        expected_command=("bash",),
        expected_args=("-ceu", cell_job_script(
            cell_index=index,
            preparation_receipt=source_manifest,
            parity_receipt=parity,
            provenance_args=_provenance_cli_args(cell_provenance),
        )),
    )

    prefix = cell_result_prefix(index, prefix=output_prefix) + "/"
    inventory = tuple(inventory_loader(prefix))
    inventory_by_uri: dict[str, Mapping[str, object]] = {}
    for row in inventory:
        identity = _inventory_identity(row, label="cell inventory object")
        uri = str(identity["uri"])
        if not uri.startswith(prefix) or uri in inventory_by_uri:
            raise LR8FullSourceTransportError("cell inventory differs")
        inventory_by_uri[uri] = row
    shard_uri = cell_shard_uri(index, prefix=output_prefix)
    attempt_uri = cell_attempt_uri(index, prefix=output_prefix)
    if shard_uri not in inventory_by_uri or attempt_uri not in inventory_by_uri:
        raise LR8FullSourceTransportError("cell result is incomplete")
    loaded: dict[str, tuple[shard_core.ObjectReceipt, bytes]] = {}
    for uri in sorted(inventory_by_uri):
        metadata, raw = object_loader(inventory_by_uri[uri])
        expected = _inventory_identity(
            inventory_by_uri[uri], label="inventory object",
        )
        actual = _loaded_receipt(metadata, raw, label="loaded cell object")
        if {
            "uri": actual.uri,
            "generation": actual.generation,
            "bytes": actual.bytes,
        } != expected:
            raise LR8FullSourceTransportError("generation-pinned cell object differs")
        loaded[uri] = (actual, raw)
    shard_receipt, shard_raw = loaded[shard_uri]
    shard = _shard_from_object(shard_raw, prepared=prepared)
    if shard.execution_attempt_receipt != loaded[attempt_uri][0]:
        raise LR8FullSourceTransportError("cell attempt receipt differs")
    if shard.preparation_receipt != preparation:
        raise LR8FullSourceTransportError("cell preparation receipt differs")
    attempt = validate_attempt_payload(
        _strict_json(loaded[attempt_uri][1], label="cell attempt object"),
        prepared=prepared,
        preparation_receipt=shard.preparation_receipt,
        execution=execution,
        job=job,
        prepared_execution_provenance=prepared_provenance,
        cell_execution_provenance=cell_provenance,
        output_prefix=output_prefix,
    )
    evidence = {
        receipt["uri"]
        for attempt in shard.frozen_block.solve_attempts
        for receipt in attempt.evidence_receipts
    }
    if evidence != set(loaded).difference({attempt_uri, shard_uri}):
        raise LR8FullSourceTransportError("cell evidence inventory differs")
    _validate_exact_evidence_bodies(
        shard, loaded=loaded, output_prefix=output_prefix,
    )
    return HarvestedCell(
        cell_index=index,
        execution=execution,
        terminal_sha256=str(terminal["metadata_sha256"]),
        shard=shard,
        shard_receipt=shard_receipt,
        attempt=attempt,
        execution_provenance=cell_provenance,
    )


def aggregate_and_publish(
    cells: Sequence[HarvestedCell],
    *,
    preparation_manifest_receipt: (
        Mapping[str, object] | shard_core.ObjectReceipt
    ),
    parity_receipt: Mapping[str, object] | shard_core.ObjectReceipt,
    prepared_execution_provenance: Mapping[str, object],
    publish: Publisher,
    output_prefix: str = RESULT_PREFIX,
) -> dict[str, object]:
    """Aggregate exact registered order and publish authoritative freeze bytes."""
    rows = tuple(cells)
    if tuple(row.cell_index for row in rows) != tuple(
        range(shard_core.EXPECTED_CELLS)
    ):
        raise LR8FullSourceTransportError("harvested cells are not exact order")
    if len({row.execution for row in rows}) != shard_core.EXPECTED_CELLS:
        raise LR8FullSourceTransportError("cell execution names repeat")
    preparation_object = _receipt(
        preparation_manifest_receipt, label="preparation manifest object",
    )
    parity_object = _receipt(parity_receipt, label="smoke parity object")
    prepared_provenance = validate_execution_provenance(
        prepared_execution_provenance
    )
    if (
        prepared_provenance["mode"] != "prepare"
        or preparation_object.uri
        != f"{_prefix(output_prefix)}/preparation-manifest.json"
        or parity_object.uri != f"{_prefix(output_prefix)}/smoke-prepared-parity.json"
    ):
        raise LR8FullSourceTransportError("aggregate source binding differs")
    cell_provenances = tuple(
        validate_execution_provenance(row.execution_provenance) for row in rows
    )
    if (
        any(value["mode"] != "cell" for value in cell_provenances)
        or any(value != cell_provenances[0] for value in cell_provenances[1:])
        or any(
            value[key] != prepared_provenance[key]
            for value in cell_provenances
            for key in ("code_sha", "build_id", "image", "job_name", "job_uid")
        )
    ):
        raise LR8FullSourceTransportError("aggregate execution provenance differs")
    try:
        aggregate = shard_core.aggregate_cell_shards(
            tuple(row.shard for row in rows)
        )
    except shard_core.LR8FullSourceShardError as exc:
        raise LR8FullSourceTransportError(str(exc)) from exc
    prefix = _prefix(output_prefix)
    freeze_uri = f"{prefix}/training-source-freeze.json"
    freeze_receipt = _published(
        publish(freeze_uri, aggregate.freeze_bytes),
        uri=freeze_uri,
        raw=aggregate.freeze_bytes,
    )
    manifest: dict[str, object] = {
        "version": AGGREGATE_OBJECT_VERSION,
        "attempt_id": ATTEMPT_ID,
        "preparation_manifest_object": preparation_object.as_dict(),
        "smoke_parity_object": parity_object.as_dict(),
        "prepared_execution_provenance": prepared_provenance,
        "cell_execution_provenance": cell_provenances[0],
        "cell_count": len(rows),
        "cell_order": [list(row) for row in shard_core.EXPECTED_CELL_KEYS],
        "cell_results": [{
            "cell_index": row.cell_index,
            "execution": row.execution,
            "terminal_sha256": row.terminal_sha256,
            "attempt_uri": row.attempt["attempt_uri"],
            "attempt_object": row.shard.execution_attempt_receipt.as_dict(),
            "shard_object": row.shard_receipt.as_dict(),
            "shard_sha256": row.shard.shard_sha256,
        } for row in rows],
        "training_source_freeze_object": freeze_receipt.as_dict(),
        "training_source_freeze_sha256": _sha(aggregate.freeze_bytes),
        "training_source_manifest_sha256": _strict_sha(
            aggregate.freeze_manifest["manifest_sha256"],
            label="training source manifest hash",
        ),
        "byte_equivalent_existing_scientific_serializer": True,
        "target_player_labels_read": False,
        "candidate_labels_read": False,
        "actual_score_queried": False,
        "historical_outcome_lease_acquired": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    manifest["manifest_sha256"] = training.canonical_sha256(manifest)
    raw = _canonical_json(manifest)
    uri = f"{prefix}/aggregate-manifest.json"
    aggregate_receipt = _published(
        publish(uri, raw), uri=uri, raw=raw,
    )
    return {
        "manifest": manifest,
        "manifest_object": aggregate_receipt.as_dict(),
        "freeze_object": freeze_receipt.as_dict(),
        "training_source_manifest_sha256": manifest[
            "training_source_manifest_sha256"
        ],
    }


def ledger_line(job: str, execution: str, uri: str) -> str:
    """Return the dashboard-compatible ``JOB EXECUTION URI`` record."""
    job_value = _string(job, label="job")
    execution_value = _string(execution, label="execution")
    if _EXECUTION_RE.fullmatch(execution_value) is None or not execution_value.startswith(
        job_value + "-"
    ):
        raise LR8FullSourceTransportError("execution ledger identity differs")
    if not _string(uri, label="result URI").startswith("gs://"):
        raise LR8FullSourceTransportError("execution ledger URI differs")
    return f"{job_value} {execution_value} {uri}\n"


def _prepare_from_cloud(args: argparse.Namespace) -> int:
    """Real score-free preparation entry point; never instantiates a solver."""
    if not args.execute or os.environ.get(ENABLED_ENV) != "1":
        raise LR8FullSourceTransportError("full-source preparation is disabled")
    expected_inputs = {
        "project": PROJECT,
        "bucket": BUCKET,
        "catalog_table": f"{PROJECT}.nfl_predictions.slate_player_features",
        "candidate_table": (
            f"{PROJECT}.nfl_predictions.replay_candidates_staging"
        ),
        "pit_table": f"{PROJECT}.nfl_features.player_week_training",
        "tabpfn_table": (
            f"{PROJECT}.nfl_features.{source_runner.TABPFN_TABLE_NAME}"
        ),
        "location": "US",
    }
    if any(getattr(args, key) != value for key, value in expected_inputs.items()):
        raise LR8FullSourceTransportError("full-source input identity differs")
    execution_provenance = _execution_provenance_from_args(args, mode="prepare")
    from google.cloud import bigquery, storage

    unused_evidence_root = Path("/tmp/lr8-full-source-unused-evidence")
    if unused_evidence_root.exists():
        raise LR8FullSourceTransportError(
            "score-free preparation scratch path already exists"
        )
    unused_evidence_root.mkdir()
    config = source_runner.RunnerConfig(
        mode="full-source",
        attempt_id=ATTEMPT_ID,
        project=args.project,
        bucket=args.bucket,
        catalog_table=args.catalog_table,
        candidate_table=args.candidate_table,
        pit_table=args.pit_table,
        tabpfn_table=args.tabpfn_table,
        location=args.location,
        evidence_root=unused_evidence_root,
        execute=True,
        enabled=True,
    )
    source_runner._validate_config(config)  # noqa: SLF001
    bq = bigquery.Client(project=args.project)
    storage_client = storage.Client(project=args.project)
    def publish(uri: str, raw: bytes) -> PublishedObject:
        value = source_runner._default_publish(storage_client, uri, raw)  # noqa: SLF001
        return PublishedObject(
            receipt=value.receipt,
            reopened_raw=value.reopened_raw,
            created=value.created,
        )

    tables = (
        config.catalog_table, config.candidate_table,
        config.pit_table, config.tabpfn_table,
    )
    before = {
        table: source_runner._validate_table_receipt(  # noqa: SLF001
            source_runner._default_table_metadata(bq, table), table=table,  # noqa: SLF001
        )
        for table in tables
    }
    outputs: dict[str, tuple[pd.DataFrame, dict[str, object], object]] = {}
    for spec in source_runner._query_requests(config):  # noqa: SLF001
        frame, job = source_runner._default_query(bq, spec)  # noqa: SLF001
        outputs[spec.label] = (
            frame,
            source_runner._validate_job_receipt(job, spec),  # noqa: SLF001
            spec,
        )
    after = {
        table: source_runner._validate_table_receipt(  # noqa: SLF001
            source_runner._default_table_metadata(bq, table), table=table,  # noqa: SLF001
        )
        for table in tables
    }
    if source_runner._canonical_json(before) != source_runner._canonical_json(after):  # noqa: SLF001
        raise LR8FullSourceTransportError("BigQuery metadata drifted during prepare")
    extracts: dict[str, dict[str, object]] = {}
    extract_receipts: dict[str, dict[str, object]] = {}
    for label, (frame, job, spec) in outputs.items():
        columns, sort_by, filename = source_runner._extract_contract(label)  # noqa: SLF001
        raw = source_runner._extract_bytes(  # noqa: SLF001
            spec=spec,
            frame=frame,
            job_receipt=job,
            table_receipts=[before[table] for table in source_runner._table_dependencies(  # noqa: SLF001
                config, label,
            )],
            columns=columns,
            sort_by=sort_by,
        )
        uri = f"{RESULT_PREFIX}/extracts/{filename}"
        published = publish(uri, raw)
        receipt = _published(published, uri=uri, raw=raw)
        extracts[label] = source_runner._strict_json(  # noqa: SLF001
            published.reopened_raw, label="reopened extract",
        )
        extract_receipts[label] = receipt.as_dict()
    catalog = source_runner._frame_from_extract(  # noqa: SLF001
        extracts["canonical_catalog"],
        expected_columns=source_runner.CATALOG_COLUMNS,
    )
    incumbents = source_runner._frame_from_extract(  # noqa: SLF001
        extracts["canonical_incumbents"],
        expected_columns=source_runner.INCUMBENT_COLUMNS,
    )
    plan = source_runner.lattice("full-source")
    canonical, audited = source_runner._catalog_inputs(  # noqa: SLF001
        catalog,
        incumbents,
        plan=plan,
        catalog_receipt=extract_receipts["canonical_catalog"],
        incumbent_receipt=extract_receipts["canonical_incumbents"],
    )

    def season_factory(season: int) -> tuple[training.PITReplayBlock, ...]:
        weeks = training.EXPECTED_WEEKS[season]
        panel_label = f"pit_panel_{season}"
        cache_label = f"tabpfn_{season}"
        panel = source_runner._frame_from_extract(  # noqa: SLF001
            extracts[panel_label], expected_columns=source_runner.PIT_COLUMNS,
        )
        source_runner._validate_outcome_blind_panel(  # noqa: SLF001
            panel, target_season=season,
        )
        cache = source_runner._frame_from_extract(  # noqa: SLF001
            extracts[cache_label], expected_columns=source_runner.CACHE_COLUMNS,
        )
        fit_input_sha = source_runner._model_fit_input_sha(panel, season)  # noqa: SLF001
        audited_slates = tuple(source_runner.replay_source.AuditedReplaySlate(
            season=season,
            week=week,
            players=audited[(season, week)][0],
            catalog_sha256=training.catalog_sha256(audited[(season, week)][0]),
            dst_mean_projection=audited[(season, week)][1],
            replay_source_receipts=(
                extract_receipts[panel_label],
                extract_receipts[cache_label],
                extract_receipts["canonical_catalog"],
            ),
        ) for week in weeks)
        result: list[training.PITReplayBlock] = []
        with source_runner._replay_scope(  # noqa: SLF001
            season=season, weeks=weeks, cache=cache,
        ):
            binding = source_runner._fit_model_binding(panel, season)  # noqa: SLF001
            with source_runner._bound_replay_model(  # noqa: SLF001
                binding, target_season=season, expected_calls=2,
            ):
                for block_name in training.BLOCK_ORDER:
                    result.append(
                        source_runner.replay_source.materialize_baseline_replay_block(
                            panel,
                            audited_slates,
                            target_season=season,
                            block=block_name,
                            model_fit_input_sha256=fit_input_sha,
                            model_fit_sha256=binding.model_sha256,
                            fit_source_receipts=(extract_receipts[panel_label],),
                            provenance=(
                                source_runner.replay_source.ReplaySourceProvenance()
                            ),
                        )
                    )
        return tuple(result)

    result = prepare_and_publish_cells(
        canonical,
        season_replay_factory=season_factory,
        publish=publish,
        execution_provenance=execution_provenance,
        output_prefix=RESULT_PREFIX,
    )
    print(_canonical_json({
        "preparation_manifest": result.manifest_receipt.as_dict(),
        "prepared_cell_count": len(result.prepared_cells),
    }).decode(), end="")
    return 0


def _gcs_parts(uri: str) -> tuple[str, str]:
    value = _string(uri, label="GCS URI")
    if not value.startswith("gs://"):
        raise LR8FullSourceTransportError("object URI must use gs://")
    bucket, separator, name = value.removeprefix("gs://").partition("/")
    if not bucket or not separator or not name:
        raise LR8FullSourceTransportError("object URI needs bucket and object")
    return bucket, name


class _CloudObjectStore:
    """Minimal generation-pinned reader/create-once writer for cloud entrypoints."""

    def __init__(self, client: object):
        self._client = client

    def load(
        self, receipt_value: Mapping[str, object] | shard_core.ObjectReceipt,
    ) -> tuple[dict[str, object], bytes]:
        receipt = _receipt(receipt_value, label="requested cloud object")
        bucket, name = _gcs_parts(receipt.uri)
        generation = int(receipt.generation)
        blob = self._client.bucket(bucket).blob(name, generation=generation)
        blob.reload(if_generation_match=generation)
        raw = blob.download_as_bytes(if_generation_match=generation)
        metadata = {
            "uri": receipt.uri,
            "generation": str(blob.generation),
            "sha256": _sha(raw),
            "bytes": len(raw),
        }
        if _receipt(metadata, label="loaded cloud object") != receipt:
            raise LR8FullSourceTransportError(
                "generation-pinned cloud object differs"
            )
        return metadata, raw

    def publish(self, uri: str, raw: bytes) -> PublishedObject:
        value = source_runner._default_publish(self._client, uri, raw)  # noqa: SLF001
        return PublishedObject(
            receipt=value.receipt,
            reopened_raw=value.reopened_raw,
            created=value.created,
        )


def _receipt_from_args(args: argparse.Namespace, stem: str) -> dict[str, object]:
    return {
        "uri": getattr(args, stem + "_uri"),
        "generation": getattr(args, stem + "_generation"),
        "sha256": getattr(args, stem + "_sha256"),
        "bytes": getattr(args, stem + "_bytes"),
    }


def _execution_provenance_from_args(
    args: argparse.Namespace,
    *,
    mode: str,
    preparation_receipt: shard_core.ObjectReceipt | None = None,
    parity_receipt: shard_core.ObjectReceipt | None = None,
) -> dict[str, object]:
    if args.job_name != JOB or args.job_uid != JOB_UID:
        raise LR8FullSourceTransportError("runtime job identity differs")
    expected_env = {
        "ANALYSIS_IMAGE": args.image,
        "CODE_SHA": args.code_sha,
        "LR8_BUILD_ID": args.build_id,
        ENABLED_ENV: "1",
    }
    if any(os.environ.get(key) != expected for key, expected in expected_env.items()):
        raise LR8FullSourceTransportError("runtime execution environment differs")
    result = build_execution_provenance(
        mode=mode,
        code_sha=args.code_sha,
        build_id=args.build_id,
        image=args.image,
        job_generation=args.job_generation,
        job_spec_sha256=args.job_spec_sha256,
        preparation_receipt=preparation_receipt,
        parity_receipt=parity_receipt,
    )
    if result["job_contract_sha256"] != args.job_contract_sha256:
        raise LR8FullSourceTransportError("runtime job contract hash differs")
    return result


def _validate_parity_object(
    value: object,
    *,
    prepared: shard_core.PreparedCell,
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise LR8FullSourceTransportError("smoke parity object must be an object")
    parity = dict(value)
    digest = parity.pop("parity_sha256", None)
    if (
        parity.get("version") != SMOKE_PARITY_VERSION
        or parity.get("smoke_attempt_id") != SMOKE_ATTEMPT_ID
        or parity.get("full_source_attempt_id") != ATTEMPT_ID
        or parity.get("cell_index") != 0
        or parity.get("prepared_cell_sha256")
        != prepared.prepared_cell_sha256
        or parity.get("parity_exact") is not True
        or parity.get("cell_execution_licensed") is not True
        or parity.get("historical_scoring_licensed") is not False
        or parity.get("production_change_licensed") is not False
        or _strict_sha(digest, label="smoke parity hash")
        != training.canonical_sha256(parity)
    ):
        raise LR8FullSourceTransportError("smoke/prepared parity gate differs")
    parity["parity_sha256"] = digest
    return parity


def _solve_cell_from_cloud(args: argparse.Namespace) -> int:
    """Load one pinned prepared cell, enforce parity, and solve once."""
    if not args.execute or os.environ.get(ENABLED_ENV) != "1":
        raise LR8FullSourceTransportError("full-source cell solving is disabled")
    if args.project != PROJECT:
        raise LR8FullSourceTransportError("full-source cell project differs")
    index = shard_core._exact_cell_index(args.cell_index)  # noqa: SLF001
    evidence_root = args.evidence_root.resolve()
    if (
        not evidence_root.is_absolute()
        or not evidence_root.exists()
        or not evidence_root.is_dir()
        or evidence_root.is_symlink()
    ):
        raise LR8FullSourceTransportError("cell evidence root differs")
    from google.cloud import storage
    from nfl_dfs.research.lr8_exact_solvers import make_training_world_solver

    store = _CloudObjectStore(storage.Client(project=args.project))
    preparation_receipt = _receipt(
        _receipt_from_args(args, "preparation"),
        label="full-source preparation manifest",
    )
    _, preparation_raw = store.load(preparation_receipt)
    preparation = validate_preparation_manifest(
        _strict_json(preparation_raw, label="preparation manifest")
    )
    prepared_provenance = validate_execution_provenance(
        preparation["execution_provenance"]
    )
    cell_row = preparation["prepared_cells"][index]
    cell_receipt = _receipt(cell_row["cell_object"], label="prepared cell object")
    draw_receipt = _receipt(cell_row["draw_object"], label="prepared draw object")
    cell_metadata, cell_raw = store.load(cell_receipt)
    draw_metadata, draw_raw = store.load(draw_receipt)
    if _loaded_receipt(
        cell_metadata, cell_raw, label="prepared cell object",
    ) != cell_receipt:
        raise LR8FullSourceTransportError("prepared cell receipt differs")
    prepared = _prepared_from_object(
        cell_raw, draw_metadata=draw_metadata, draw_raw=draw_raw,
    )
    if prepared.cell_index != index:
        raise LR8FullSourceTransportError("prepared cell index differs")
    if cell_row["prepared_cell_sha256"] != prepared.prepared_cell_sha256:
        raise LR8FullSourceTransportError("prepared cell manifest hash differs")
    parity_receipt = _receipt(
        _receipt_from_args(args, "parity"), label="smoke parity object",
    )
    _, parity_raw = store.load(parity_receipt)
    parity_prepared = prepared
    if index != 0:
        parity_cell_receipt = _receipt(
            preparation["prepared_cells"][0]["cell_object"],
            label="prepared parity cell object",
        )
        parity_draw_receipt = _receipt(
            preparation["prepared_cells"][0]["draw_object"],
            label="prepared parity draw object",
        )
        parity_cell_metadata, parity_cell_raw = store.load(parity_cell_receipt)
        parity_draw_metadata, parity_draw_raw = store.load(parity_draw_receipt)
        if _loaded_receipt(
            parity_cell_metadata,
            parity_cell_raw,
            label="prepared parity cell object",
        ) != parity_cell_receipt:
            raise LR8FullSourceTransportError("prepared parity cell differs")
        parity_prepared = _prepared_from_object(
            parity_cell_raw,
            draw_metadata=parity_draw_metadata,
            draw_raw=parity_draw_raw,
        )
    _validate_parity_object(
        _strict_json(parity_raw, label="smoke parity object"),
        prepared=parity_prepared,
    )
    cell_provenance = _execution_provenance_from_args(
        args,
        mode="cell",
        preparation_receipt=preparation_receipt,
        parity_receipt=parity_receipt,
    )
    execution = os.environ.get("CLOUD_RUN_EXECUTION", "")
    runtime_job = os.environ.get("CLOUD_RUN_JOB", "")
    if (
        runtime_job != JOB
        or _EXECUTION_RE.fullmatch(execution) is None
        or not execution.startswith(JOB + "-")
        or os.environ.get("CLOUD_RUN_TASK_INDEX") != "0"
        or os.environ.get("CLOUD_RUN_TASK_ATTEMPT") != "0"
    ):
        raise LR8FullSourceTransportError("cell runtime execution identity differs")
    evidence_prefix = cell_result_prefix(index) + "/solver-evidence-root"
    solver = make_training_world_solver(
        evidence_root=evidence_root,
        publish_evidence=source_runner._evidence_publisher(  # noqa: SLF001
            evidence_root=evidence_root,
            output_root=cell_result_prefix(index),
            publish=store.publish,
        ),
    )
    result = solve_and_publish_cell(
        prepared,
        preparation_receipt=cell_receipt,
        prepared_execution_provenance=prepared_provenance,
        cell_execution_provenance=cell_provenance,
        execution=execution,
        job=runtime_job,
        task_index=0,
        task_attempt=0,
        solve_world=solver,
        publish=store.publish,
    )
    print(_canonical_json({
        "cell_index": index,
        "shard_object": result.shard_receipt.as_dict(),
        "attempt_object": result.attempt_receipt.as_dict(),
        "evidence_prefix": evidence_prefix,
    }).decode(), end="")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare-cloud")
    prepare.add_argument("--execute", action="store_true")
    prepare.add_argument("--project", default=PROJECT)
    prepare.add_argument("--bucket", default=BUCKET)
    prepare.add_argument(
        "--catalog-table",
        default=f"{PROJECT}.nfl_predictions.slate_player_features",
    )
    prepare.add_argument(
        "--candidate-table",
        default=f"{PROJECT}.nfl_predictions.replay_candidates_staging",
    )
    prepare.add_argument(
        "--pit-table", default=f"{PROJECT}.nfl_features.player_week_training",
    )
    prepare.add_argument(
        "--tabpfn-table",
        default=f"{PROJECT}.nfl_features.{source_runner.TABPFN_TABLE_NAME}",
    )
    prepare.add_argument("--location", default="US")
    solve = sub.add_parser("solve-cell-cloud")
    solve.add_argument("--execute", action="store_true")
    solve.add_argument("--project", default=PROJECT)
    solve.add_argument("--cell-index", type=int, required=True)
    solve.add_argument("--evidence-root", type=Path, required=True)
    for stem in ("preparation", "parity"):
        solve.add_argument(f"--{stem}-uri", required=True)
        solve.add_argument(f"--{stem}-generation", required=True)
        solve.add_argument(f"--{stem}-sha256", required=True)
        solve.add_argument(f"--{stem}-bytes", type=int, required=True)
    for command in (prepare, solve):
        command.add_argument("--code-sha", required=True)
        command.add_argument("--build-id", required=True)
        command.add_argument("--image", required=True)
        command.add_argument("--job-name", required=True)
        command.add_argument("--job-uid", required=True)
        command.add_argument("--job-generation", required=True)
        command.add_argument("--job-spec-sha256", required=True)
        command.add_argument("--job-contract-sha256", required=True)
    sub.add_parser("cell-order")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "prepare-cloud":
        return _prepare_from_cloud(args)
    if args.command == "solve-cell-cloud":
        return _solve_cell_from_cloud(args)
    if args.command == "cell-order":
        print(_canonical_json([
            {"cell_index": index, "season": season, "week": week, "block": block}
            for index, (season, week, block) in enumerate(
                shard_core.EXPECTED_CELL_KEYS
            )
        ]).decode(), end="")
        return 0
    raise LR8FullSourceTransportError("unknown command")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        LR8FullSourceTransportError,
        shard_core.LR8FullSourceShardError,
        source_runner.LR8SourceRunnerError,
    ) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
