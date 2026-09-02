"""Selective, v1-compatible pre-lock lineage runtime adapter.

The adapter is deliberately pure.  It observes the existing five native
``CandidateBatch`` objects, the canonical CBWU batch, and the reviewed typed
coverage-selector events.  It neither generates nor selects a different
lineup, performs I/O, reads outcomes, mutates Neo4j, nor changes an existing
schema.  Detailed evidence is retained in a new capture envelope while the
published candidate sidecar remains the immutable
``prelock-candidate-lineage-sidecar/v1`` contract.
"""

from __future__ import annotations

import base64
import json
import math
import re
import zlib
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Final

import numpy as np
import pandas as pd

from ..backtest.engine import CandidateBatch, _validate_candidate_batch
from ..models.components import COMPONENT_NAMES
from ..optimizer.lineup import CoverageSelectorEvent, select_tail_entries
from .generation_exposure import validate_ledger
from .prelock_candidate_lineage_v1 import (
    ROSTER_IDENTITY_SCHEMA,
    build_prelock_candidate_lineage_v1,
    canonical_json_bytes,
    canonical_sha256,
    validate_prelock_candidate_lineage_v1,
)
from .prelock_input_boundary_v1 import validate_prelock_input_read_manifest_v1
from .prelock_model_artifact_authority_v1 import (
    validate_model_artifact_manifest_v1,
)

CAPTURE_SCHEMA: Final = "prelock-lineage-capture-envelope/v2"
MATRIX_SCHEMA: Final = "prelock-selector-matrix-raw/v1"
SALARY_SNAPSHOT_SCHEMA: Final = "prelock-classic-salary-snapshot/v1"
SEED_LABELS: Final = ("R0", "R1", "R2", "R3", "R4")
NATIVE_UNION_STAGE_ID: Final = "native-union"
EFFECTIVE_STAGE_ID: Final = "effective-candidates"
NATIVE_UNION_PRESET_ID: Final = "observed-generated-native-union-v1"
CBWU_PRESET_ID: Final = "fixed-budget-cbwu-v1"
EFFECTIVE_POLICY_SCHEMA: Final = "nfl-dfs-effective-policy-rule-inventory/v2"
EFFECTIVE_POLICY_SOURCE_SET_ID: Final = (
    "adopted-classic-policy-20260902-week1-boom-first-selector-lineage-v6"
)
LINEAGE_ADAPTER_MANIFEST_SCHEMA: Final = "prelock-lineage-adapter-manifest/v2"
EXECUTION_RECEIPT_SCHEMA: Final = "prelock-lineage-execution-receipt/v1"

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_UTC_SECONDS: Final = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_IDENTIFIER: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$")

# Closed, versioned values permitted in the exact effective player snapshot.
# The component columns are a finite producer-owned vocabulary; optional route
# fields are included because the same reviewed live builder can expose them.
PLAYER_FEATURE_COLUMNS: Final = frozenset(
    {
        "id",
        "gsis_id",
        "name",
        "pos",
        "team",
        "opp",
        "salary",
        "season",
        "week",
        "game_id",
        "draw_idx",
        "proj",
        "model_points_pre",
        "market_points",
        "mean_projection",
        "proj_p10",
        "proj_p50",
        "proj_p90",
        "proj_std",
        "proj_tourney",
        "low_own",
        "fp_route_source_season",
        "fp_route_source_week",
        "fp_route_source_sha256",
        "fp_route_prior_observations",
        "fp_route_share_last",
        "fp_route_share_l4",
        "fp_route_share_jump",
        "fp_route_cross_season",
        "fp_route_fallback",
        "fp_route_shadow_supported",
        *(f"component_mean_{name}" for name in COMPONENT_NAMES),
    }
)
SALARY_COLUMNS: Final = frozenset(
    {
        "pulled_at",
        "draft_group_id",
        "dk_player_id",
        "dk_draftable_id",
        "display_name",
        "team_abbr",
        "position",
        "salary",
        "game_start",
        "status",
    }
)


class PrelockLineageRuntimeV2Error(ValueError):
    """Captured runtime evidence does not prove the unchanged production law."""


def _fail(message: str) -> None:
    raise PrelockLineageRuntimeV2Error(message)


def _clone(value: object) -> Any:
    try:
        return json.loads(canonical_json_bytes(value))
    except ValueError as exc:
        raise PrelockLineageRuntimeV2Error(
            "runtime evidence is not canonical JSON"
        ) from exc


def _timestamp(value: object, *, label: str) -> str:
    if type(value) is not str or _UTC_SECONDS.fullmatch(value) is None:
        _fail(f"{label} must use whole UTC seconds")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise PrelockLineageRuntimeV2Error(f"{label} is invalid") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        _fail(f"{label} is not canonical")
    return value


def _identifier(value: object, *, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        _fail(f"{label} is not a normalized identifier")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} is not a SHA-256")
    return value


def _validate_effective_policy_inventory(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("effective-policy inventory is not a mapping")
    item = _clone(value)
    fields = {
        "classified_input_projection",
        "classified_input_projection_sha256",
        "complete_for_scope",
        "effective_policy",
        "forbidden_ambient_process_keys",
        "legal_feasibility_parameters",
        "rule_count",
        "rule_universe_sha256",
        "rules",
        "schema",
        "scope",
        "source_identities",
        "source_set_id",
        "source_set_sha256",
        "inventory_sha256",
    }
    if set(item) != fields:
        _fail("effective-policy inventory fields differ")
    retained_hash = item.pop("inventory_sha256")
    identities = item.get("source_identities")
    inventory_digest = sha256(canonical_json_bytes(item) + b"\n").hexdigest()
    source_set_digest = (
        sha256(canonical_json_bytes(identities) + b"\n").hexdigest()
        if isinstance(identities, list)
        else None
    )
    if (
        item.get("schema") != EFFECTIVE_POLICY_SCHEMA
        or item.get("source_set_id") != EFFECTIVE_POLICY_SOURCE_SET_ID
        or item.get("complete_for_scope") is not True
        or _digest(retained_hash, label="effective-policy inventory")
        != inventory_digest
        or not isinstance(identities, list)
        or not identities
        or item.get("source_set_sha256") != source_set_digest
    ):
        _fail("effective-policy inventory contract or self-hash differs")
    paths: list[str] = []
    for row in identities:
        if not isinstance(row, Mapping) or set(row) != {
            "path",
            "role",
            "sha256",
            "bytes",
        }:
            _fail("effective-policy source identity fields differ")
        path = row["path"]
        if (
            type(path) is not str
            or not path
            or path.startswith("/")
            or ".." in path.split("/")
            or type(row["role"]) is not str
            or not row["role"]
            or type(row["bytes"]) is not int
            or row["bytes"] < 1
        ):
            _fail("effective-policy source identity is invalid")
        _digest(row["sha256"], label="effective-policy source")
        paths.append(path)
    if len(paths) != len(set(paths)):
        _fail("effective-policy source identities repeat a path")
    _digest(
        item.get("classified_input_projection_sha256"),
        label="classified input projection",
    )
    _digest(item.get("rule_universe_sha256"), label="policy rule universe")
    return {**item, "inventory_sha256": retained_hash}


def _validate_adapter_manifest(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("lineage adapter manifest is not a mapping")
    item = _clone(value)
    if set(item) != {
        "schema_version",
        "files",
        "effective_policy_inventory_required",
        "transitive_scoring_surface_claimed_here",
        "manifest_sha256",
    }:
        _fail("lineage adapter manifest fields differ")
    retained_hash = item.pop("manifest_sha256")
    files = item.get("files")
    if (
        item.get("schema_version") != LINEAGE_ADAPTER_MANIFEST_SCHEMA
        or item.get("effective_policy_inventory_required") != "v6"
        or item.get("transitive_scoring_surface_claimed_here") is not False
        or _digest(retained_hash, label="lineage adapter manifest")
        != canonical_sha256(item)
        or not isinstance(files, list)
        or not files
    ):
        _fail("lineage adapter manifest contract or self-hash differs")
    paths: list[str] = []
    for row in files:
        if not isinstance(row, Mapping) or set(row) != {
            "path",
            "sha256",
            "bytes",
        }:
            _fail("lineage adapter file identity fields differ")
        path = row["path"]
        if (
            type(path) is not str
            or not path
            or path.startswith("/")
            or ".." in path.split("/")
            or type(row["bytes"]) is not int
            or row["bytes"] < 1
        ):
            _fail("lineage adapter file identity is invalid")
        _digest(row["sha256"], label="lineage adapter file")
        paths.append(path)
    if len(paths) != len(set(paths)):
        _fail("lineage adapter manifest repeats a source path")
    return {**item, "manifest_sha256": retained_hash}


def _validate_execution_receipt(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("execution receipt is not a mapping")
    item = _clone(value)
    if set(item) != {
        "schema_version",
        "image_digest",
        "source_commit",
        "container_image_immutable",
        "solver",
        "compute_envelope",
        "receipt_sha256",
    }:
        _fail("execution receipt fields differ")
    retained_hash = item.pop("receipt_sha256")
    solver = item.get("solver")
    compute = item.get("compute_envelope")
    if (
        item.get("schema_version") != EXECUTION_RECEIPT_SCHEMA
        or type(item.get("image_digest")) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", item["image_digest"]) is None
        or type(item.get("source_commit")) is not str
        or re.fullmatch(r"[0-9a-f]{40}", item["source_commit"]) is None
        or item.get("container_image_immutable") is not True
        or _digest(retained_hash, label="execution receipt") != canonical_sha256(item)
        or not isinstance(solver, Mapping)
        or set(solver) != {"name", "pulp_version", "binary_sha256", "binary_bytes"}
        or not isinstance(compute, Mapping)
        or set(compute)
        != {
            "architecture",
            "operating_system",
            "python_version",
            "numpy_version",
            "cpu_count",
            "memory_bytes",
        }
    ):
        _fail("execution receipt contract or self-hash differs")
    if (
        solver["name"] != "cbc"
        or type(solver["pulp_version"]) is not str
        or not solver["pulp_version"]
        or type(solver["binary_bytes"]) is not int
        or solver["binary_bytes"] < 1
        or any(
            type(compute[key]) is not str or not compute[key]
            for key in (
                "architecture",
                "operating_system",
                "python_version",
                "numpy_version",
            )
        )
        or any(
            type(compute[key]) is not int or compute[key] < 0
            for key in ("cpu_count", "memory_bytes")
        )
    ):
        _fail("execution solver or compute identity is incomplete")
    _digest(solver["binary_sha256"], label="execution solver binary")
    return {**item, "receipt_sha256": retained_hash}


def _roster(values: object, *, label: str) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        _fail(f"{label} is not a roster array")
    retained = sorted(str(value).strip() for value in values)
    if len(retained) != 9 or any(not value for value in retained):
        _fail(f"{label} must contain nine nonempty IDs")
    if len(set(retained)) != 9:
        _fail(f"{label} repeats a player ID")
    return retained


def _roster_id(slate_id: str, internal_ids: Sequence[object]) -> str:
    payload = {
        "schema_version": ROSTER_IDENTITY_SCHEMA,
        "slate_id": slate_id,
        "internal_player_id_namespace": "production-lineup-id-v1",
        "internal_player_ids": _roster(internal_ids, label="internal roster"),
    }
    return "roster-v1-" + canonical_sha256(payload)


def _lineup_rosters(batch: CandidateBatch) -> list[list[str]]:
    return [
        _roster(list(lineup.ids), label=f"candidate roster[{index}]")
        for index, lineup in enumerate(batch.candidates)
    ]


def _array_identity(value: object, *, label: str) -> dict[str, object]:
    array = np.asarray(value)
    if array.ndim != 2 or not np.isfinite(array).all():
        _fail(f"{label} must be one finite two-dimensional matrix")
    contiguous = np.ascontiguousarray(array)
    payload = contiguous.tobytes(order="C")
    return {
        "dtype": contiguous.dtype.str,
        "shape": [int(size) for size in contiguous.shape],
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


def _matrix_archive(value: object) -> dict[str, object]:
    array = np.ascontiguousarray(np.asarray(value))
    identity = _array_identity(array, label="effective selector matrix")
    raw = array.tobytes(order="C")
    compressed = zlib.compress(raw, level=9)
    encoded = base64.b64encode(compressed).decode("ascii")
    return {
        "schema_version": MATRIX_SCHEMA,
        **identity,
        "archive_encoding": "zlib-9+base64",
        "archive_sha256": sha256(compressed).hexdigest(),
        "archive_bytes": len(compressed),
        "archive_base64": encoded,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }


def reopen_selector_matrix_v2(value: object) -> np.ndarray:
    if not isinstance(value, Mapping):
        _fail("selector matrix archive is not a mapping")
    item = dict(value)
    expected = {
        "schema_version",
        "dtype",
        "shape",
        "sha256",
        "bytes",
        "archive_encoding",
        "archive_sha256",
        "archive_bytes",
        "archive_base64",
        "uses_realized_outcomes",
        "post_lock_data_read",
    }
    if set(item) != expected:
        _fail("selector matrix archive fields differ")
    if (
        item["schema_version"] != MATRIX_SCHEMA
        or item["archive_encoding"] != "zlib-9+base64"
        or item["uses_realized_outcomes"] is not False
        or item["post_lock_data_read"] is not False
    ):
        _fail("selector matrix archive contract differs")
    try:
        dtype = np.dtype(item["dtype"])
        shape = tuple(int(value) for value in item["shape"])
    except (TypeError, ValueError) as exc:
        raise PrelockLineageRuntimeV2Error(
            "selector matrix dtype or shape differs"
        ) from exc
    if (
        len(shape) != 2
        or any(size < 1 for size in shape)
        or type(item["bytes"]) is not int
        or item["bytes"] != math.prod(shape) * dtype.itemsize
        or type(item["archive_bytes"]) is not int
        or item["archive_bytes"] < 1
    ):
        _fail("selector matrix dimensions or byte count differ")
    _digest(item["sha256"], label="selector matrix")
    _digest(item["archive_sha256"], label="selector matrix archive")
    if type(item["archive_base64"]) is not str:
        _fail("selector matrix archive payload differs")
    try:
        compressed = base64.b64decode(item["archive_base64"], validate=True)
        raw = zlib.decompress(compressed)
    except (ValueError, zlib.error) as exc:
        raise PrelockLineageRuntimeV2Error(
            "selector matrix archive cannot be reopened"
        ) from exc
    if (
        len(compressed) != item["archive_bytes"]
        or sha256(compressed).hexdigest() != item["archive_sha256"]
        or len(raw) != item["bytes"]
        or sha256(raw).hexdigest() != item["sha256"]
    ):
        _fail("selector matrix archive content identity differs")
    return np.frombuffer(raw, dtype=dtype).reshape(shape).copy()


def canonical_selector_matrix_bytes(value: Mapping[str, object]) -> bytes:
    """Return the exact raw bytes represented by a validated archive."""

    return np.ascontiguousarray(reopen_selector_matrix_v2(value)).tobytes(order="C")


def _canonical_cell(value: object) -> list[object]:
    if isinstance(value, np.generic):
        value = value.item()
    if value is None:
        return ["null", None]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int):
        return ["int", str(value)]
    if isinstance(value, float):
        if np.isnan(value):
            return ["float", "nan"]
        if np.isposinf(value):
            return ["float", "+inf"]
        if np.isneginf(value):
            return ["float", "-inf"]
        return ["float", value.hex()]
    if isinstance(value, (pd.Timestamp, np.datetime64, datetime)):
        return ["datetime", pd.Timestamp(value).isoformat()]
    if isinstance(value, str):
        return ["str", value]
    try:
        if bool(pd.isna(value)):
            return ["null", None]
    except (TypeError, ValueError):
        pass
    _fail(f"player input contains unsupported {type(value).__name__} value")


def _validate_encoded_cell(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list) or len(value) != 2 or type(value[0]) is not str:
        _fail(f"{label} is not one canonical typed cell")
    kind, retained = value
    valid = False
    if kind == "null":
        valid = retained is None
    elif kind == "bool":
        valid = type(retained) is bool
    elif kind == "int" and type(retained) is str:
        try:
            valid = str(int(retained)) == retained
        except ValueError:
            valid = False
    elif kind == "float" and type(retained) is str:
        if retained in {"nan", "+inf", "-inf"}:
            valid = True
        else:
            try:
                valid = float.fromhex(retained).hex() == retained
            except ValueError:
                valid = False
    elif kind == "datetime" and type(retained) is str:
        try:
            valid = not pd.isna(pd.Timestamp(retained))
        except (TypeError, ValueError):
            valid = False
    elif kind == "str":
        valid = type(retained) is str
    if not valid:
        _fail(f"{label} canonical typed cell differs")
    return [kind, retained]


def _feature_snapshot(batch: CandidateBatch) -> dict[str, object]:
    rows = [dict(row) for row in batch.player_rows]
    if len(rows) != len(batch.player_ids):
        _fail("effective player feature rows are misaligned")
    columns = sorted({str(column) for row in rows for column in row})
    unknown = set(columns) - PLAYER_FEATURE_COLUMNS
    if unknown:
        _fail(
            f"effective player feature columns are outside the allowlist: {sorted(unknown)}"
        )
    if "id" not in columns:
        _fail("effective player feature snapshot lacks id")
    encoded_rows: list[list[list[object]]] = []
    for index, (player_id, row) in enumerate(zip(batch.player_ids, rows, strict=True)):
        if set(row) != set(columns) or str(row["id"]) != str(player_id):
            _fail(f"effective player feature row {index} differs from player order")
        encoded_rows.append([_canonical_cell(row[column]) for column in columns])
    body: dict[str, object] = {
        "schema_version": "prelock-effective-player-feature-snapshot/v1",
        "allowlist_id": "live-candidate-player-columns-20260902-v1",
        "columns": columns,
        "player_id_order": [str(value) for value in batch.player_ids],
        "rows": encoded_rows,
        "row_count": len(rows),
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    body["snapshot_sha256"] = canonical_sha256(body)
    return body


def build_salary_snapshot_v2(
    frame: pd.DataFrame,
    *,
    draft_group_id: int,
    source_table_uri: str,
) -> dict[str, object]:
    """Freeze the one salary read used for lock, IDs, and salary overrides."""

    required = {
        "draft_group_id",
        "dk_player_id",
        "dk_draftable_id",
        "salary",
        "game_start",
    }
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        _fail("classic salary snapshot is empty")
    columns = sorted(str(column) for column in frame.columns)
    if required - set(columns) or set(columns) - SALARY_COLUMNS:
        _fail("classic salary snapshot columns are outside the closed contract")
    if type(draft_group_id) is not int or draft_group_id < 1:
        _fail("salary draft group is invalid")
    if type(source_table_uri) is not str or not source_table_uri.startswith("bq://"):
        _fail("salary source table URI is invalid")
    normalized = frame.loc[:, columns].copy()
    if normalized.loc[:, list(required)].isna().any().any():
        _fail("classic salary snapshot has missing required values")
    if any(int(value) != draft_group_id for value in normalized["draft_group_id"]):
        _fail("classic salary snapshot contains another draft group")
    if (
        normalized["dk_player_id"].duplicated().any()
        or normalized["dk_draftable_id"].duplicated().any()
    ):
        _fail("classic salary snapshot repeats a player identity")
    starts = pd.to_datetime(normalized["game_start"], utc=True, errors="coerce")
    if starts.isna().any():
        _fail("classic salary snapshot has an invalid game start")
    lock_at = starts.min().to_pydatetime().astimezone(UTC).replace(microsecond=0)
    pull_values = []
    if "pulled_at" in normalized:
        pulls = pd.to_datetime(normalized["pulled_at"], utc=True, errors="coerce")
        if pulls.isna().any() or len(set(pulls.tolist())) != 1:
            _fail("classic salary snapshot does not identify one source pull")
        pull_values = [pull.isoformat() for pull in pulls]
    catalog_rows = sorted(
        [
            {
                "internal_player_id": str(int(row.dk_player_id)),
                "draftable_player_id": str(int(row.dk_draftable_id)),
                "salary": int(row.salary),
            }
            for row in normalized.itertuples(index=False)
        ],
        key=lambda row: row["internal_player_id"],
    )
    encoded_rows = [
        [_canonical_cell(value) for value in row]
        for row in normalized.itertuples(index=False, name=None)
    ]
    body: dict[str, object] = {
        "schema_version": SALARY_SNAPSHOT_SCHEMA,
        "draft_group_id": draft_group_id,
        "source_table_uri": source_table_uri,
        "source_pull_at_utc": pull_values[0] if pull_values else None,
        "slate_lock_at_utc": lock_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "columns": columns,
        "rows": encoded_rows,
        "row_count": len(normalized),
        "catalog_rows": catalog_rows,
        "salary_catalog_sha256": canonical_sha256(catalog_rows),
        "internal_to_draftable": {
            row["internal_player_id"]: row["draftable_player_id"]
            for row in catalog_rows
        },
        "single_read_authority": True,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    body["snapshot_sha256"] = canonical_sha256(body)
    return validate_salary_snapshot_v2(body)


def validate_salary_snapshot_v2(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("salary snapshot is not a mapping")
    item = _clone(value)
    fields = {
        "schema_version",
        "draft_group_id",
        "source_table_uri",
        "source_pull_at_utc",
        "slate_lock_at_utc",
        "columns",
        "rows",
        "row_count",
        "catalog_rows",
        "salary_catalog_sha256",
        "internal_to_draftable",
        "single_read_authority",
        "uses_realized_outcomes",
        "post_lock_data_read",
        "snapshot_sha256",
    }
    if set(item) != fields:
        _fail("salary snapshot fields differ")
    retained_hash = item.pop("snapshot_sha256")
    if (
        item["schema_version"] != SALARY_SNAPSHOT_SCHEMA
        or _digest(retained_hash, label="salary snapshot") != canonical_sha256(item)
        or type(item["draft_group_id"]) is not int
        or item["draft_group_id"] < 1
        or type(item["source_table_uri"]) is not str
        or not item["source_table_uri"].startswith("bq://")
        or item["single_read_authority"] is not True
        or item["uses_realized_outcomes"] is not False
        or item["post_lock_data_read"] is not False
    ):
        _fail("salary snapshot contract or self-hash differs")
    _timestamp(item["slate_lock_at_utc"], label="salary slate lock")
    columns = item["columns"]
    rows = item["rows"]
    catalog = item["catalog_rows"]
    bridge = item["internal_to_draftable"]
    if (
        not isinstance(columns, list)
        or columns != sorted(columns)
        or len(columns) != len(set(columns))
        or {
            "draft_group_id",
            "dk_player_id",
            "dk_draftable_id",
            "salary",
            "game_start",
            "pulled_at",
        }
        - set(columns)
        or set(columns) - SALARY_COLUMNS
        or not isinstance(rows, list)
        or item["row_count"] != len(rows)
        or not isinstance(catalog, list)
        or len(catalog) != len(rows)
        or not isinstance(bridge, Mapping)
        or item["salary_catalog_sha256"] != canonical_sha256(catalog)
    ):
        _fail("salary snapshot row or catalog identity differs")
    for row_index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(columns):
            _fail("salary snapshot encoded row shape differs")
        for column_index, cell in enumerate(row):
            _validate_encoded_cell(
                cell,
                label=f"salary row {row_index} column {column_index}",
            )
    source_pull = item.get("source_pull_at_utc")
    if type(source_pull) is not str:
        _fail("salary snapshot lacks one provider pull timestamp")
    try:
        pulled = pd.Timestamp(source_pull)
    except (TypeError, ValueError) as exc:
        raise PrelockLineageRuntimeV2Error(
            "salary source pull timestamp is invalid"
        ) from exc
    if pulled.tzinfo is None or pulled > pd.Timestamp(item["slate_lock_at_utc"]):
        _fail("salary source pull is not demonstrably pre-lock")
    expected_bridge: dict[str, str] = {}
    seen_draftable: set[str] = set()
    for row in catalog:
        if not isinstance(row, Mapping) or set(row) != {
            "internal_player_id",
            "draftable_player_id",
            "salary",
        }:
            _fail("salary catalog row fields differ")
        internal = str(row["internal_player_id"])
        draftable = str(row["draftable_player_id"])
        if (
            not internal
            or not draftable
            or internal in expected_bridge
            or draftable in seen_draftable
            or type(row["salary"]) is not int
            or row["salary"] <= 0
        ):
            _fail("salary catalog identity or amount differs")
        expected_bridge[internal] = draftable
        seen_draftable.add(draftable)
    if dict(bridge) != expected_bridge:
        _fail("salary snapshot player bridge differs")
    return {**item, "snapshot_sha256": retained_hash}


def _source_config(metadata: object) -> dict[str, object]:
    source = metadata if isinstance(metadata, Mapping) else {}
    allowed = (
        "model_version",
        "role_model_version",
        "candidate_input_receipt",
        "role_candidate_input_receipt",
        "construction_preset_receipt",
        "generation_allocation",
        "latent_scenario_receipt",
        "latent_optimization_receipt",
    )
    return {
        key: _clone(source[key])
        for key in allowed
        if key in source and source[key] not in ({}, (), [], None, "")
    }


def _selector_event(event: CoverageSelectorEvent) -> dict[str, object]:
    if not isinstance(event, CoverageSelectorEvent):
        _fail("selector emitted a non-typed event")
    return {
        "candidate_index": int(event.candidate_index),
        "selected": bool(event.selected),
        "selection_rank": event.selection_rank,
        "fresh_world_count": int(event.fresh_world_count),
        "individual_clear_count": int(event.individual_clear_count),
        "p_line": float(event.p_line),
        "mean_simulated_total": float(event.mean_simulated_total),
        "phase": str(event.phase),
        "tiebreak": [float(value) for value in event.tiebreak],
        "eligible_for_selection": bool(event.eligible_for_selection),
        "terminal_reason": event.terminal_reason,
    }


def _validate_selector_configuration(
    environment: Mapping[str, str], *, entry_budget: int
) -> dict[str, str]:
    env = {str(key): str(value) for key, value in environment.items()}
    required = {
        "MULTISEED_PORTFOLIO": "CBWU",
        "SELECT_OBJ": "",
        "SELECT_LSE": "0",
        "SELECT_LADDER": "",
        "M4_QBLOCK": "0",
        "MAX_QBS": "0",
        "PEAK_SLICE": "0",
        "PROSPECTIVE_GENERATION_EXPOSURE": "1",
        "MULTISEED_CANDIDATE_ENTRY_BASIS": str(entry_budget),
    }
    if any(env.get(key) != value for key, value in required.items()):
        _fail("runtime environment is not the canonical traced CBWU selector")
    return dict(sorted(env.items()))


def build_capture_authority_v2(
    *,
    run: Mapping[str, object],
    native_batches: Mapping[str, CandidateBatch],
    effective_batch: CandidateBatch,
    salary_snapshot: Mapping[str, object],
    policy_environment: Mapping[str, str],
    effective_policy_inventory: Mapping[str, object],
    lineage_adapter_manifest: Mapping[str, object],
    execution_receipt: Mapping[str, object],
    model_artifact_manifest: Mapping[str, object],
    model_artifacts_exact_reopened_after_generation: bool,
    input_read_boundary: Mapping[str, object],
    source_binding_mode: str,
    selector_id: str,
    retrieval_preset_id: str,
    tail_line: float,
    entry_budget: int,
) -> dict[str, object]:
    """Build the first immutable object, sufficient for boundary resume."""

    if set(native_batches) != set(SEED_LABELS):
        _fail("runtime capture requires exact R0-R4 native batches")
    if list(native_batches) != list(SEED_LABELS):
        _fail("native batches are not in registered R0-R4 order")
    if type(entry_budget) is not int or entry_budget < 1:
        _fail("entry budget is invalid")
    if not isinstance(tail_line, (int, float)) or not math.isfinite(tail_line):
        _fail("tail line is invalid")
    environment = _validate_selector_configuration(
        policy_environment, entry_budget=entry_budget
    )
    _identifier(selector_id, label="selector ID")
    _identifier(retrieval_preset_id, label="retrieval preset ID")
    policy_inventory = _validate_effective_policy_inventory(effective_policy_inventory)
    adapter_manifest = _validate_adapter_manifest(lineage_adapter_manifest)
    execution = _validate_execution_receipt(execution_receipt)
    model_artifacts = validate_model_artifact_manifest_v1(model_artifact_manifest)
    if model_artifacts_exact_reopened_after_generation is not True:
        _fail("model artifacts were not exact-reopened after generation")
    read_manifest = validate_prelock_input_read_manifest_v1(input_read_boundary)
    if source_binding_mode not in {
        "git-global-clean-checkout",
        "immutable-image-embedded-revision",
    }:
        _fail("runtime source binding mode differs")
    model_versions = {
        str(row["purpose"]): str(row["model_version"])
        for row in model_artifacts["model_sets"]
    }
    _validate_candidate_batch(effective_batch)
    if effective_batch.metadata.get("portfolio") != "CBWU":
        _fail("effective candidate batch is not canonical CBWU")
    if len(effective_batch.candidates) < entry_budget:
        _fail("effective candidate batch cannot fill exact K")

    native: list[dict[str, object]] = []
    for label in SEED_LABELS:
        batch = native_batches[label]
        _validate_candidate_batch(batch)
        ledger_value = batch.metadata.get("generation_exposure_ledger")
        if ledger_value is None:
            _fail(f"{label} lacks the complete generation exposure ledger")
        ledger = validate_ledger(ledger_value)
        if ledger["source_label"] != label:
            _fail(f"{label} ledger source differs")
        if batch.player_ids != effective_batch.player_ids:
            _fail(f"{label} player order differs from effective CBWU")
        if (
            batch.metadata.get("model_version")
            != model_versions["candidate-projection"]
            or batch.metadata.get("role_model_version") != model_versions["role-belief"]
        ):
            _fail(f"{label} model versions differ from exact registry authority")
        native.append(
            {
                "source_label": label,
                "generation_exposure_ledger": ledger,
                "candidate_rosters": _lineup_rosters(batch),
                "candidate_order_sha256": canonical_sha256(_lineup_rosters(batch)),
                "candidate_totals_identity": _array_identity(
                    batch.candidate_totals,
                    label=f"{label} candidate totals",
                ),
                "player_worlds_identity": _array_identity(
                    batch.row_draws,
                    label=f"{label} player worlds",
                ),
                "generator_config": _source_config(batch.metadata),
                "generator_config_sha256": canonical_sha256(
                    _source_config(batch.metadata)
                ),
            }
        )

    effective_rosters = _lineup_rosters(effective_batch)
    source_blocks = effective_batch.metadata.get("candidate_source_blocks")
    if (
        not isinstance(source_blocks, list)
        or len(source_blocks) != len(effective_rosters)
        or any(label not in SEED_LABELS for label in source_blocks)
    ):
        _fail("effective CBWU source blocks are absent or misaligned")
    events: list[CoverageSelectorEvent] = []
    selected = select_tail_entries(
        np.asarray(effective_batch.candidate_totals),
        entry_budget,
        float(tail_line),
        env=environment,
        event_sink=events.append,
    )
    event_rows = [_selector_event(event) for event in events]
    if (
        len(event_rows) != len(effective_rosters)
        or {int(row["candidate_index"]) for row in event_rows}
        != set(range(len(effective_rosters)))
        or [
            int(row["candidate_index"]) for row in event_rows if row["selected"] is True
        ]
        != selected
    ):
        _fail("typed selector events do not exactly reconcile to selection")

    matrix_archive = _matrix_archive(effective_batch.candidate_totals)
    run_item = dict(run)
    required_run = {
        "run_id",
        "run_type",
        "season",
        "week",
        "slate_id",
        "draft_group_id",
        "contest_id",
        "slate_lock_at_utc",
        "capture_started_at_utc",
        "policy_id",
        "code_sha256",
    }
    if set(run_item) != required_run:
        _fail("capture run fields differ")
    _timestamp(run_item["slate_lock_at_utc"], label="slate lock")
    _timestamp(run_item["capture_started_at_utc"], label="capture start")
    _digest(run_item["code_sha256"], label="runtime method")
    if run_item["contest_id"] is not None:
        _fail("candidate-only shadow cannot claim a paid contest")

    normalized_salary = validate_salary_snapshot_v2(salary_snapshot)
    if (
        normalized_salary["draft_group_id"] != run_item["draft_group_id"]
        or normalized_salary["slate_lock_at_utc"] != run_item["slate_lock_at_utc"]
    ):
        _fail("salary snapshot scope differs from the capture run")
    body: dict[str, object] = {
        "schema_version": CAPTURE_SCHEMA,
        "run": run_item,
        "entry_budget": entry_budget,
        "selector_configuration": {
            "selector_id": selector_id,
            "retrieval_preset_id": retrieval_preset_id,
            "tail_line": float(tail_line),
            "objective_semantics": "binary-world-clear-coverage",
            "strategy_objective_and_retrieval_are_distinct": True,
        },
        "policy_environment": environment,
        "policy_environment_sha256": canonical_sha256(environment),
        "effective_policy_inventory": policy_inventory,
        "lineage_adapter_manifest": adapter_manifest,
        "execution_receipt": execution,
        "model_artifact_manifest": model_artifacts,
        "model_artifacts_exact_reopened_after_generation": True,
        "source_binding_mode": source_binding_mode,
        "salary_snapshot": normalized_salary,
        "effective_player_feature_snapshot": _feature_snapshot(effective_batch),
        "native_sources": native,
        "effective_candidates": {
            "stage_id": EFFECTIVE_STAGE_ID,
            "candidate_rosters": effective_rosters,
            "candidate_order_sha256": canonical_sha256(effective_rosters),
            "candidate_source_blocks": list(source_blocks),
            "selector_matrix_archive": matrix_archive,
            "player_worlds_identity": _array_identity(
                effective_batch.row_draws,
                label="effective player worlds",
            ),
            "typed_selector_events": event_rows,
            "raw_selected_indices": selected,
            "final_selected_indices": list(selected),
            "postselector_replacements": 0,
        },
        "read_manifest": read_manifest,
        "write_manifest": {
            "allowed_object_roles": [
                "capture-authority",
                "selector-matrix",
                "candidate-lineage-sidecar",
                "aggregate-graph-projection",
                "final-manifest",
            ],
            "bigquery_writes_allowed": False,
            "graph_writes_allowed": False,
        },
        "capture_completed_before_legacy_diagnostics": True,
        "typed_selector_interface_replayed": True,
        "raw_selection_equals_final_book": True,
        "detailed_rows_projected_to_graph": False,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
        "production_enabled": False,
    }
    body["capture_sha256"] = canonical_sha256(body)
    return validate_capture_authority_v2(body)


def validate_capture_authority_v2(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("capture authority is not a mapping")
    item = _clone(value)
    fields = {
        "schema_version",
        "run",
        "entry_budget",
        "selector_configuration",
        "policy_environment",
        "policy_environment_sha256",
        "effective_policy_inventory",
        "lineage_adapter_manifest",
        "execution_receipt",
        "model_artifact_manifest",
        "model_artifacts_exact_reopened_after_generation",
        "source_binding_mode",
        "salary_snapshot",
        "effective_player_feature_snapshot",
        "native_sources",
        "effective_candidates",
        "read_manifest",
        "write_manifest",
        "capture_completed_before_legacy_diagnostics",
        "typed_selector_interface_replayed",
        "raw_selection_equals_final_book",
        "detailed_rows_projected_to_graph",
        "uses_realized_outcomes",
        "post_lock_data_read",
        "production_enabled",
        "capture_sha256",
    }
    if set(item) != fields:
        _fail("capture authority fields differ")
    retained_hash = item.pop("capture_sha256")
    if item["schema_version"] != CAPTURE_SCHEMA or _digest(
        retained_hash, label="capture authority"
    ) != canonical_sha256(item):
        _fail("capture authority schema or self-hash differs")
    if any(
        item[key] is not expected
        for key, expected in {
            "capture_completed_before_legacy_diagnostics": True,
            "model_artifacts_exact_reopened_after_generation": True,
            "typed_selector_interface_replayed": True,
            "raw_selection_equals_final_book": True,
            "detailed_rows_projected_to_graph": False,
            "uses_realized_outcomes": False,
            "post_lock_data_read": False,
            "production_enabled": False,
        }.items()
    ):
        _fail("capture authority boundary flags differ")
    if item.get("source_binding_mode") not in {
        "git-global-clean-checkout",
        "immutable-image-embedded-revision",
    }:
        _fail("capture runtime source binding mode differs")
    run = item.get("run")
    if not isinstance(run, Mapping):
        _fail("capture run is not a mapping")
    _timestamp(run.get("slate_lock_at_utc"), label="capture slate lock")
    _timestamp(run.get("capture_started_at_utc"), label="capture start")
    policy_inventory = _validate_effective_policy_inventory(
        item.get("effective_policy_inventory")
    )
    adapter_manifest = _validate_adapter_manifest(item.get("lineage_adapter_manifest"))
    execution = _validate_execution_receipt(item.get("execution_receipt"))
    model_artifacts = validate_model_artifact_manifest_v1(
        item.get("model_artifact_manifest")
    )
    expected_method = canonical_sha256(
        {
            "effective_policy_inventory_sha256": policy_inventory["inventory_sha256"],
            "lineage_adapter_manifest_sha256": adapter_manifest["manifest_sha256"],
            "execution_receipt_sha256": execution["receipt_sha256"],
            "model_artifact_manifest_sha256": model_artifacts["manifest_sha256"],
        }
    )
    if (
        _digest(run.get("code_sha256"), label="capture runtime method")
        != expected_method
    ):
        _fail("capture runtime method does not bind every execution authority")
    entry_budget = item.get("entry_budget")
    if type(entry_budget) is not int or entry_budget < 1:
        _fail("capture entry budget differs")
    environment = item.get("policy_environment")
    if not isinstance(environment, Mapping) or item.get(
        "policy_environment_sha256"
    ) != canonical_sha256(environment):
        _fail("capture policy environment identity differs")
    _validate_selector_configuration(environment, entry_budget=entry_budget)
    inventory_policy = policy_inventory.get("effective_policy")
    if not isinstance(inventory_policy, Mapping) or not isinstance(
        inventory_policy.get("engine_environment"), Mapping
    ):
        _fail("effective-policy inventory lacks its runtime environment")
    base_environment = dict(environment)
    if base_environment.pop("PROSPECTIVE_GENERATION_EXPOSURE", None) != "1" or (
        base_environment != dict(inventory_policy["engine_environment"])
    ):
        _fail("capture runtime environment differs from v6 plus tracing")
    selector = item.get("selector_configuration")
    if not isinstance(selector, Mapping) or set(selector) != {
        "selector_id",
        "retrieval_preset_id",
        "tail_line",
        "objective_semantics",
        "strategy_objective_and_retrieval_are_distinct",
    }:
        _fail("capture selector configuration differs")
    _identifier(selector.get("selector_id"), label="capture selector")
    _identifier(selector.get("retrieval_preset_id"), label="capture retrieval preset")
    if (
        selector.get("objective_semantics") != "binary-world-clear-coverage"
        or selector.get("strategy_objective_and_retrieval_are_distinct") is not True
    ):
        _fail("capture selector concepts are conflated")
    native = item.get("native_sources")
    if not isinstance(native, list) or [
        row.get("source_label") for row in native if isinstance(row, Mapping)
    ] != list(SEED_LABELS):
        _fail("capture native source order differs")
    model_versions = {
        str(row["purpose"]): str(row["model_version"])
        for row in model_artifacts["model_sets"]
    }
    for row in native:
        if not isinstance(row, Mapping):
            _fail("capture native source is malformed")
        if set(row) != {
            "source_label",
            "generation_exposure_ledger",
            "candidate_rosters",
            "candidate_order_sha256",
            "candidate_totals_identity",
            "player_worlds_identity",
            "generator_config",
            "generator_config_sha256",
        }:
            _fail("capture native source fields differ")
        ledger = validate_ledger(row.get("generation_exposure_ledger"))
        if ledger["source_label"] != row["source_label"]:
            _fail("capture native ledger source differs")
        rosters = row.get("candidate_rosters")
        if not isinstance(rosters, list) or not rosters:
            _fail("capture native candidate population is empty")
        normalized = [
            _roster(roster, label="capture native roster") for roster in rosters
        ]
        if row.get("candidate_order_sha256") != canonical_sha256(normalized):
            _fail("capture native candidate order identity differs")
        config = row.get("generator_config")
        if (
            not isinstance(config, Mapping)
            or row.get("generator_config_sha256") != canonical_sha256(config)
            or config.get("model_version") != model_versions["candidate-projection"]
            or config.get("role_model_version") != model_versions["role-belief"]
        ):
            _fail("capture native model authority or configuration differs")
    effective = item.get("effective_candidates")
    if (
        not isinstance(effective, Mapping)
        or effective.get("stage_id") != EFFECTIVE_STAGE_ID
    ):
        _fail("capture effective candidates differ")
    rosters = effective.get("candidate_rosters")
    if not isinstance(rosters, list) or len(rosters) < entry_budget:
        _fail("capture effective population cannot fill exact K")
    normalized_rosters = [
        _roster(roster, label="capture effective roster") for roster in rosters
    ]
    if len({tuple(roster) for roster in normalized_rosters}) != len(
        rosters
    ) or effective.get("candidate_order_sha256") != canonical_sha256(
        normalized_rosters
    ):
        _fail("capture effective roster order differs")
    matrix = reopen_selector_matrix_v2(effective.get("selector_matrix_archive"))
    if matrix.shape[0] != len(rosters):
        _fail("capture selector matrix candidate dimension differs")
    events = effective.get("typed_selector_events")
    if not isinstance(events, list) or len(events) != len(rosters):
        _fail("capture typed selector events are incomplete")
    by_index = {row.get("candidate_index"): row for row in events}
    if set(by_index) != set(range(len(rosters))):
        _fail("capture typed selector candidate census differs")
    selected = effective.get("raw_selected_indices")
    final = effective.get("final_selected_indices")
    if (
        not isinstance(selected, list)
        or selected != final
        or len(selected) != entry_budget
        or len(set(selected)) != len(selected)
        or any(index not in by_index for index in selected)
        or [row["candidate_index"] for row in events if row.get("selected") is True]
        != selected
        or effective.get("postselector_replacements") != 0
    ):
        _fail("capture raw/final selection differs")
    replayed_events: list[CoverageSelectorEvent] = []
    replayed_selected = select_tail_entries(
        matrix,
        entry_budget,
        float(selector["tail_line"]),
        env={str(key): str(value) for key, value in environment.items()},
        event_sink=replayed_events.append,
    )
    if (
        replayed_selected != selected
        or [_selector_event(event) for event in replayed_events] != events
    ):
        _fail("capture typed selector events differ from exact matrix replay")
    feature = item.get("effective_player_feature_snapshot")
    if not isinstance(feature, Mapping):
        _fail("capture feature snapshot is malformed")
    feature_body = dict(feature)
    feature_hash = feature_body.pop("snapshot_sha256", None)
    columns = feature_body.get("columns")
    feature_rows = feature_body.get("rows")
    player_order = feature_body.get("player_id_order")
    if (
        feature_hash != canonical_sha256(feature_body)
        or feature_body.get("schema_version")
        != "prelock-effective-player-feature-snapshot/v1"
        or feature_body.get("allowlist_id")
        != "live-candidate-player-columns-20260902-v1"
        or not isinstance(columns, list)
        or columns != sorted(columns)
        or len(columns) != len(set(columns))
        or "id" not in columns
        or set(columns) - PLAYER_FEATURE_COLUMNS
        or not isinstance(feature_rows, list)
        or not isinstance(player_order, list)
        or len(player_order) != len(set(player_order))
        or feature_body.get("row_count") != len(feature_rows)
        or len(player_order) != len(feature_rows)
        or feature_body.get("uses_realized_outcomes") is not False
        or feature_body.get("post_lock_data_read") is not False
    ):
        _fail("capture feature snapshot identity or allowlist differs")
    id_column = columns.index("id")
    for row_index, row in enumerate(feature_rows):
        if not isinstance(row, list) or len(row) != len(columns):
            _fail("capture feature snapshot row shape differs")
        normalized_cells = [
            _validate_encoded_cell(
                cell,
                label=f"feature row {row_index} column {column_index}",
            )
            for column_index, cell in enumerate(row)
        ]
        if str(normalized_cells[id_column][1]) != player_order[row_index]:
            _fail("capture feature player order differs from encoded rows")
    salary = validate_salary_snapshot_v2(item.get("salary_snapshot"))
    if salary["draft_group_id"] != run.get("draft_group_id") or salary[
        "slate_lock_at_utc"
    ] != run.get("slate_lock_at_utc"):
        _fail("capture salary snapshot scope differs")
    try:
        retained_read_manifest = validate_prelock_input_read_manifest_v1(
            item.get("read_manifest")
        )
    except ValueError as exc:
        raise PrelockLineageRuntimeV2Error(
            "capture read manifest is not the closed pre-lock set"
        ) from exc
    if item.get("read_manifest") != retained_read_manifest:
        _fail("capture read manifest differs after validation")
    if item.get("write_manifest") != {
        "allowed_object_roles": [
            "capture-authority",
            "selector-matrix",
            "candidate-lineage-sidecar",
            "aggregate-graph-projection",
            "final-manifest",
        ],
        "bigquery_writes_allowed": False,
        "graph_writes_allowed": False,
    }:
        _fail("capture write manifest is not the closed five-object set")
    return {**item, "capture_sha256": retained_hash}


def _generation_records(capture: Mapping[str, object]) -> dict[str, Any]:
    slate_id = str(capture["run"]["slate_id"])  # type: ignore[index]
    salary = capture["salary_snapshot"]
    if not isinstance(salary, Mapping):
        _fail("salary snapshot is unavailable")
    raw_bridge = salary.get("internal_to_draftable")
    if not isinstance(raw_bridge, Mapping):
        _fail("salary snapshot lacks the player bridge")
    bridge = {str(key): str(value) for key, value in raw_bridge.items()}
    catalog_sha = _digest(salary.get("salary_catalog_sha256"), label="salary catalog")

    proposals: list[dict[str, object]] = []
    attempts: list[dict[str, object]] = []
    occurrences: list[dict[str, object]] = []
    dedupe: list[dict[str, object]] = []
    roster_raw_by_id: dict[str, dict[str, object]] = {}
    occurrence_ids_by_roster: dict[str, list[str]] = defaultdict(list)
    first_occurrence: dict[str, dict[str, object]] = {}
    request_meta: dict[str, tuple[str, str]] = {}
    status_map = {
        "new": "PRODUCED",
        "dup": "PRODUCED",
        "infeasible": "INFEASIBLE",
        "error": "SOLVER_ERROR",
    }

    for native in capture["native_sources"]:  # type: ignore[index]
        source = str(native["source_label"])
        ledger = validate_ledger(native["generation_exposure_ledger"])
        by_request: dict[tuple[str, int], list[Mapping[str, object]]] = defaultdict(
            list
        )
        for row in ledger["rows"]:
            by_request[(str(row["family"]), int(row["requested_ordinal"]))].append(row)
        for family, expected in sorted(ledger["expected_requests_by_family"].items()):
            for requested in range(int(expected)):
                chain = by_request[(str(family), requested)]
                if not chain:
                    _fail("generation ledger omits one requested solve")
                exhausted = [row for row in chain if row["status"] == "exhausted"]
                if exhausted:
                    if len(chain) != 1:
                        _fail("exhausted request also carries solve attempts")
                    terminal = "EXHAUSTED_NOT_ATTEMPTED"
                    attempted: list[Mapping[str, object]] = []
                else:
                    terminal = status_map[str(chain[-1]["status"])]
                    attempted = chain
                request_id = f"request-{len(proposals):06d}"
                request_meta[request_id] = (source, str(family))
                world_ids = {
                    int(row["world_id"]) for row in chain if row["world_id"] is not None
                }
                if len(world_ids) > 1:
                    _fail("one proposal request spans multiple world IDs")
                proposals.append(
                    {
                        "request_id": request_id,
                        "request_ordinal": len(proposals),
                        "source_label": source,
                        "family": str(family),
                        "requested_ordinal": requested,
                        "world_id": next(iter(world_ids), None),
                        "generator_config_sha256": native["generator_config_sha256"],
                        "terminal_status": terminal,
                    }
                )
                for row in attempted:
                    attempt_id = f"attempt-{len(attempts):06d}"
                    roster_id = None
                    if row["status"] in {"new", "dup"}:
                        internal_ids = _roster(
                            row["player_ids"], label="generated solve roster"
                        )
                        roster_id = _roster_id(slate_id, internal_ids)
                        try:
                            pairs = [
                                {
                                    "internal_player_id": internal_id,
                                    "draftable_player_id": bridge[internal_id],
                                }
                                for internal_id in internal_ids
                            ]
                        except KeyError as exc:
                            raise PrelockLineageRuntimeV2Error(
                                "generated roster lacks a salary identity bridge"
                            ) from exc
                        roster_raw_by_id.setdefault(
                            roster_id,
                            {
                                "slate_id": slate_id,
                                "internal_player_id_namespace": (
                                    "production-lineup-id-v1"
                                ),
                                "draftable_player_id_namespace": (
                                    "draftkings-draftable-id-v1"
                                ),
                                "player_id_bridge": pairs,
                                "salary_catalog_sha256": catalog_sha,
                                "legacy_lineup_ids": [],
                            },
                        )
                    attempts.append(
                        {
                            "attempt_id": attempt_id,
                            "attempt_ordinal": len(attempts),
                            "request_id": request_id,
                            "retry_ordinal": int(row["retry_ordinal"]),
                            "status": status_map[str(row["status"])],
                            "roster_id": roster_id,
                        }
                    )
                    if roster_id is None:
                        continue
                    occurrence_id = f"occurrence-{len(occurrences):06d}"
                    occurrence = {
                        "occurrence_id": occurrence_id,
                        "occurrence_ordinal": len(occurrences),
                        "attempt_id": attempt_id,
                        "request_id": request_id,
                        "roster_id": roster_id,
                    }
                    occurrences.append(occurrence)
                    occurrence_ids_by_roster[roster_id].append(occurrence_id)
                    prior = first_occurrence.get(roster_id)
                    if prior is None:
                        disposition = "FIRST_SEEN"
                        duplicate_of = None
                        first_occurrence[roster_id] = occurrence
                    else:
                        prior_source, prior_family = request_meta[
                            str(prior["request_id"])
                        ]
                        disposition = (
                            "DUPLICATE_CROSS_SEED"
                            if prior_source != source
                            else "DUPLICATE_CROSS_FAMILY"
                            if prior_family != str(family)
                            else "DUPLICATE_SAME_FAMILY"
                        )
                        duplicate_of = prior["occurrence_id"]
                    dedupe.append(
                        {
                            "decision_id": f"dedupe-{len(dedupe):06d}",
                            "occurrence_id": occurrence_id,
                            "roster_id": roster_id,
                            "disposition": disposition,
                            "duplicate_of_occurrence_id": duplicate_of,
                        }
                    )
    return {
        "roster_raw_by_id": roster_raw_by_id,
        "proposal_requests": proposals,
        "solve_attempts": attempts,
        "generated_occurrences": occurrences,
        "dedupe_decisions": dedupe,
        "occurrence_ids_by_roster": occurrence_ids_by_roster,
        "first_occurrence_order": list(first_occurrence),
    }


def _admission_records(
    capture: Mapping[str, object], generation: Mapping[str, Any]
) -> tuple[list[dict[str, object]], dict[int, str]]:
    slate_id = str(capture["run"]["slate_id"])  # type: ignore[index]
    native_rosters = {
        str(native["source_label"]): [
            _roster_id(slate_id, roster) for roster in native["candidate_rosters"]
        ]
        for native in capture["native_sources"]  # type: ignore[index]
    }
    native_union_set = {
        roster_id for rosters in native_rosters.values() for roster_id in rosters
    }
    generated_set = set(generation["roster_raw_by_id"])
    if not native_union_set <= generated_set:
        _fail("native candidate population contains an unrecorded solve roster")
    ordered_generated = list(generation["first_occurrence_order"])
    if set(ordered_generated) != generated_set:
        _fail("generated roster census differs")

    admissions: list[dict[str, object]] = []
    union_instance: dict[str, str] = {}
    for ordinal, roster_id in enumerate(ordered_generated):
        instance_id = f"candidate-native-union-{ordinal:06d}"
        union_instance[roster_id] = instance_id
        retained = roster_id in native_union_set
        admissions.append(
            {
                "decision_id": f"admission-native-union-{ordinal:06d}",
                "stage_id": NATIVE_UNION_STAGE_ID,
                "stage_ordinal": 0,
                "candidate_instance_id": instance_id,
                "candidate_ordinal": ordinal,
                "roster_id": roster_id,
                "source_occurrence_ids": list(
                    generation["occurrence_ids_by_roster"][roster_id]
                ),
                "input_candidate_instance_ids": [],
                "admission_preset_id": NATIVE_UNION_PRESET_ID,
                "disposition": "RETAINED" if retained else "REJECTED",
                "reason": "RETAINED_NATIVE" if retained else "DROPPED_POOL_CAP",
            }
        )

    budget = len(native_rosters[SEED_LABELS[0]])
    buckets: dict[str, list[str]] = {label: [] for label in SEED_LABELS}
    seen: set[str] = set()
    for label in SEED_LABELS:
        for roster_id in native_rosters[label]:
            if roster_id in seen:
                continue
            seen.add(roster_id)
            buckets[label].append(roster_id)
    base_quota, remainder = divmod(budget, len(SEED_LABELS))
    chosen: list[tuple[str, str, str]] = []
    used = {label: 0 for label in SEED_LABELS}
    for seed_index, label in enumerate(SEED_LABELS):
        quota = base_quota + int(seed_index < remainder)
        take = min(quota, len(buckets[label]))
        chosen.extend(
            (label, roster_id, "RETAINED_FIRST_SOURCE_QUOTA")
            for roster_id in buckets[label][:take]
        )
        used[label] = take
    while len(chosen) < budget:
        advanced = False
        for label in SEED_LABELS:
            if used[label] >= len(buckets[label]):
                continue
            chosen.append(
                (
                    label,
                    buckets[label][used[label]],
                    "RETAINED_DEFICIT_FILL",
                )
            )
            used[label] += 1
            advanced = True
            if len(chosen) == budget:
                break
        if not advanced:
            _fail("native union cannot fill the fixed CBWU budget")
    expected_rosters = [
        _roster_id(slate_id, roster)
        for roster in capture["effective_candidates"]["candidate_rosters"]  # type: ignore[index]
    ]
    expected_sources = list(
        capture["effective_candidates"]["candidate_source_blocks"]  # type: ignore[index]
    )
    if [roster_id for _, roster_id, _ in chosen] != expected_rosters or [
        label for label, _, _ in chosen
    ] != expected_sources:
        _fail("external CBWU reconstruction differs from the captured batch")

    effective_instance: dict[int, str] = {}
    chosen_reason = {roster_id: reason for _, roster_id, reason in chosen}
    ordered_stage = [roster_id for _, roster_id, _ in chosen] + sorted(
        native_union_set - set(chosen_reason),
        key=lambda roster_id: ordered_generated.index(roster_id),
    )
    for ordinal, roster_id in enumerate(ordered_stage):
        retained = roster_id in chosen_reason
        instance_id = f"candidate-effective-{ordinal:06d}"
        if retained:
            effective_instance[ordinal] = instance_id
        admissions.append(
            {
                "decision_id": f"admission-effective-{ordinal:06d}",
                "stage_id": EFFECTIVE_STAGE_ID,
                "stage_ordinal": 1,
                "candidate_instance_id": instance_id,
                "candidate_ordinal": ordinal,
                "roster_id": roster_id,
                "source_occurrence_ids": [],
                "input_candidate_instance_ids": [union_instance[roster_id]],
                "admission_preset_id": CBWU_PRESET_ID,
                "disposition": "RETAINED" if retained else "REJECTED",
                "reason": (
                    chosen_reason[roster_id] if retained else "DROPPED_FIXED_BUDGET"
                ),
            }
        )
    if set(effective_instance) != set(range(budget)):
        _fail("effective candidate instance order differs")
    return admissions, effective_instance


def build_sidecar_from_capture_v2(
    *,
    capture: Mapping[str, object],
    capture_identity: Mapping[str, object],
    frozen_at_utc: str,
) -> dict[str, object]:
    """Normalize captured R0-R4 evidence into the immutable linear v1 law."""

    retained = validate_capture_authority_v2(capture)
    _timestamp(frozen_at_utc, label="sidecar freeze")
    identity_fields = {"uri", "generation", "sha256", "bytes"}
    if not isinstance(capture_identity, Mapping) or set(capture_identity) != (
        identity_fields
    ):
        _fail("capture input identity fields differ")
    identity = dict(capture_identity)
    _digest(identity["sha256"], label="capture input identity")
    canonical_capture = canonical_json_bytes(retained)
    if identity["sha256"] != sha256(canonical_capture).hexdigest() or identity[
        "bytes"
    ] != len(canonical_capture):
        _fail("capture input identity does not bind canonical capture bytes")

    generation = _generation_records(retained)
    admissions, effective_instance = _admission_records(retained, generation)
    selector = retained["selector_configuration"]
    strategy_id = str(selector["selector_id"])
    effective = retained["effective_candidates"]
    events = {
        int(row["candidate_index"]): row for row in effective["typed_selector_events"]
    }
    rosters = [
        _roster_id(str(retained["run"]["slate_id"]), roster)
        for roster in effective["candidate_rosters"]
    ]
    strategy: list[dict[str, object]] = []
    for candidate_ordinal, roster_id in enumerate(rosters):
        event = events[candidate_ordinal]
        selected = event["selected"] is True
        phase = str(event["phase"])
        terminal = event["terminal_reason"]
        if selected:
            reason = (
                "SELECTED_COVERAGE_PHASE"
                if phase == "coverage"
                else "SELECTED_SATURATION_FILL"
            )
        else:
            reason = (
                "NOT_SELECTED_FILL_ORDER"
                if terminal == "fill-order"
                else "NOT_SELECTED_BOOK_FULL"
            )
        strategy.append(
            {
                "decision_id": f"strategy-{candidate_ordinal:06d}",
                "strategy_id": strategy_id,
                "candidate_instance_id": effective_instance[candidate_ordinal],
                "roster_id": roster_id,
                "candidate_ordinal": candidate_ordinal,
                "eligibility": "ELIGIBLE",
                "eligibility_reason": "EFFECTIVE_CANDIDATE",
                "decision": "SELECTED" if selected else "NOT_SELECTED",
                "decision_reason": reason,
                "selector_rank": event["selection_rank"],
                "selection_phase": (
                    "COVERAGE"
                    if phase == "coverage"
                    else "SATURATION_FILL"
                    if phase == "saturation-fill"
                    else "TERMINAL"
                ),
                "fresh_world_count": event["fresh_world_count"],
                "individual_clear_count": event["individual_clear_count"],
                "p_line": event["p_line"],
                "mean_simulated_total": event["mean_simulated_total"],
                "tiebreak_values": list(event["tiebreak"]),
            }
        )
    selected = list(effective["raw_selected_indices"])
    books = [
        {
            "transition_id": f"book-{rank:06d}",
            "strategy_id": strategy_id,
            "candidate_instance_id": effective_instance[index],
            "roster_id": rosters[index],
            "selector_rank": rank,
            "postselector_rank": rank,
            "export_rank": rank,
            "disposition": "RETAINED",
            "reason": "RETAINED_POSTSELECTOR",
        }
        for rank, index in enumerate(selected)
    ]
    run = retained["run"]
    header = {
        "run_id": run["run_id"],
        "run_type": run["run_type"],
        "season": run["season"],
        "week": run["week"],
        "slate_id": run["slate_id"],
        "draft_group_id": run["draft_group_id"],
        "contest_id": run["contest_id"],
        "slate_lock_at_utc": run["slate_lock_at_utc"],
        "frozen_at_utc": frozen_at_utc,
        "entry_budget": retained["entry_budget"],
        "policy_id": run["policy_id"],
        "selector_ids": [strategy_id],
        "effective_candidate_stage_id": EFFECTIVE_STAGE_ID,
        "paid_strategy_id": None,
        "code_sha256": run["code_sha256"],
        "input_source_identities": [
            {"role": "frozen-prelock-input-snapshot", **identity}
        ],
    }
    sidecar = build_prelock_candidate_lineage_v1(
        run_header=header,
        roster_identities=list(generation["roster_raw_by_id"].values()),
        proposal_requests=generation["proposal_requests"],
        solve_attempts=generation["solve_attempts"],
        generated_occurrences=generation["generated_occurrences"],
        dedupe_decisions=generation["dedupe_decisions"],
        admission_decisions=admissions,
        strategy_decisions=strategy,
        book_transitions=books,
    )
    return validate_prelock_candidate_lineage_v1(sidecar)


def selected_roster_order(capture: Mapping[str, object]) -> list[list[str]]:
    retained = validate_capture_authority_v2(capture)
    effective = retained["effective_candidates"]
    return [
        list(effective["candidate_rosters"][index])
        for index in effective["final_selected_indices"]
    ]


__all__ = [
    "CAPTURE_SCHEMA",
    "CBWU_PRESET_ID",
    "EFFECTIVE_POLICY_SCHEMA",
    "EFFECTIVE_POLICY_SOURCE_SET_ID",
    "EFFECTIVE_STAGE_ID",
    "EXECUTION_RECEIPT_SCHEMA",
    "LINEAGE_ADAPTER_MANIFEST_SCHEMA",
    "MATRIX_SCHEMA",
    "NATIVE_UNION_STAGE_ID",
    "PLAYER_FEATURE_COLUMNS",
    "SALARY_COLUMNS",
    "SALARY_SNAPSHOT_SCHEMA",
    "SEED_LABELS",
    "PrelockLineageRuntimeV2Error",
    "build_capture_authority_v2",
    "build_salary_snapshot_v2",
    "build_sidecar_from_capture_v2",
    "canonical_selector_matrix_bytes",
    "reopen_selector_matrix_v2",
    "selected_roster_order",
    "validate_capture_authority_v2",
    "validate_salary_snapshot_v2",
]
