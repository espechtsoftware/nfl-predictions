"""Isolated supported-232 population-generation experiment.

This module defines a newly named fixed-attempt cohort crossing four
leverage/boom/QBVAR allocations with the existing F7/F8/F9 construction
profiles.  It deliberately does *not* claim to implement the older 266-call
fair-fill arms: role, game, and dark families are excluded from every cell.

The historical leverage and QBVAR families both require the point-in-time
``proj_tourney`` objective.  That vector is not present in the proven F7--F9
``PreparedLaterSlate`` source.  Consequently every request must bind a local
score-free player bundle that contains the objective explicitly.  Draw means
must never be substituted for it.  Local requests and results are test-only;
this module owns no cloud launcher, realized-outcome reader, or promotion
authority.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import io
import json
import os
import re
import stat
from typing import Final

import numpy as np

from nfl_dfs.backtest import engine
from nfl_dfs.optimizer import lineup as legacy_lineup
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles
from nfl_dfs.research import residual_world_columns as rw


REGISTRY_SCHEMA: Final = "corpus-r6-supported232-arm-registry/v1"
PLAYER_BUNDLE_SCHEMA: Final = "corpus-r6-supported232-player-bundle/v1"
REQUEST_SCHEMA: Final = "corpus-r6-supported232-local-task-request/v1"
DRY_VALIDATION_SCHEMA: Final = "corpus-r6-supported232-dry-validation/v1"
CALL_RECEIPT_SCHEMA: Final = "corpus-r6-supported232-optimizer-call/v1"
CELL_RESULT_SCHEMA: Final = "corpus-r6-supported232-cell-result/v1"
RESULT_SCHEMA: Final = "corpus-r6-supported232-generation-result/v1"

ARM_ORDER: Final = (
    "supported232-baseline-v1",
    "supported232-boom-heavy-v1",
    "supported232-all-boom-v1",
    "supported232-qbvar-expanded-v1",
)
FAMILY_ORDER: Final = ("leverage", "boom", "qbvar")
EXCLUDED_FAMILIES: Final = ("role", "game", "dark")
PROFILE_ORDER: Final = profiles.PROFILE_ORDER
COMPARISON_COHORT_ID: Final = (
    "supported232-fixed-attempt-leverage-boom-qbvar-v1"
)
ATTEMPTS_PER_CELL: Final = 232
CELLS_PER_TASK: Final = len(ARM_ORDER) * len(PROFILE_ORDER)
ATTEMPTS_PER_TASK: Final = ATTEMPTS_PER_CELL * CELLS_PER_TASK
QB_COUNT: Final = 8
WORLDS_PER_ORIGIN: Final = rw.WORLDS_PER_BLOCK
MAXIMUM_PLAYER_BUNDLE_BYTES: Final = 8 * 1024 * 1024
MAXIMUM_DRAW_FILE_BYTES: Final = 128 * 1024 * 1024

_ARM_DOSES: Final = {
    "supported232-baseline-v1": (160, 40, 32),
    "supported232-boom-heavy-v1": (80, 120, 32),
    "supported232-all-boom-v1": (0, 200, 32),
    "supported232-qbvar-expanded-v1": (160, 8, 64),
}
_ARM_HYPOTHESES: Final = {
    "supported232-baseline-v1": (
        "supported-family reference allocation"
    ),
    "supported232-boom-heavy-v1": (
        "move 80 leverage attempts to top-total boom worlds"
    ),
    "supported232-all-boom-v1": (
        "move all 160 leverage attempts to top-total boom worlds"
    ),
    "supported232-qbvar-expanded-v1": (
        "double per-QB variants from four to eight and repay 32 boom attempts"
    ),
}

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_PLAYER_FIELDS: Final = frozenset({
    "id", "pos", "team", "opp", "game_id", "salary", "proj_tourney",
})
_FORBIDDEN_OUTCOME_FRAGMENTS: Final = (
    "actual", "contest", "fantasy_points", "outcome", "payout", "rank",
    "realized", "standings", "winner",
)


class CorpusR6Supported232GenerationV1Error(ValueError):
    """The supported-232 local contract or runtime failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6Supported232GenerationV1Error(message)


def canonical_json_bytes_v1(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusR6Supported232GenerationV1Error(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_json_bytes_v1(value)).hexdigest()


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} already exists")
    return {**body, field: canonical_sha256_v1(body)}


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _identifier(value: object, *, label: str, maximum: int = 160) -> str:
    if (
        type(value) is not str
        or not value
        or len(value.encode("utf-8")) > maximum
        or _IDENTIFIER.fullmatch(value) is None
    ):
        _fail(f"{label} must be one bounded canonical identifier")
    return value


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase SHA-256")
    return value


def _slate(value: object) -> dict[str, object]:
    item = _mapping(value, label="slate")
    if set(item) != {"season", "week", "slate_id"}:
        _fail("slate fields differ")
    season = _integer(item["season"], label="season", minimum=2000)
    week = _integer(item["week"], label="week", minimum=1)
    slate_id = _identifier(item["slate_id"], label="slate ID")
    expected = {"season": season, "week": week, "slate_id": slate_id}
    if item != expected:
        _fail("slate values differ")
    return expected


def _matrix_sha256(value: np.ndarray) -> str:
    matrix = np.asarray(value)
    if (
        matrix.dtype != np.dtype(np.float32)
        or matrix.ndim != 2
        or not matrix.flags.c_contiguous
        or not np.isfinite(matrix).all()
    ):
        _fail("draw matrix must be finite C-contiguous float32")
    digest = sha256()
    digest.update(canonical_json_bytes_v1({
        "dtype": "float32-le",
        "shape": [int(value) for value in matrix.shape],
    }))
    digest.update(b"\0")
    digest.update(memoryview(np.ascontiguousarray(matrix, dtype="<f4")).cast("B"))
    return digest.hexdigest()


def supported232_arm_registry_v1() -> dict[str, object]:
    """Return the truthful four-arm, three-family fixed-attempt registry."""
    rows: list[dict[str, object]] = []
    for ordinal, arm_id in enumerate(ARM_ORDER):
        leverage, boom, qbvar = _ARM_DOSES[arm_id]
        dose = {"leverage": leverage, "boom": boom, "qbvar": qbvar}
        if sum(dose.values()) != ATTEMPTS_PER_CELL or qbvar % QB_COUNT:
            _fail("internal supported-232 dose differs")
        rows.append(_with_hash({
            "ordinal": ordinal,
            "arm_id": arm_id,
            "display_name": _ARM_HYPOTHESES[arm_id],
            "hypothesis": _ARM_HYPOTHESES[arm_id],
            "comparison_cohort_id": COMPARISON_COHORT_ID,
            "attempts_by_family": dose,
            "attempt_count": ATTEMPTS_PER_CELL,
            "qb_count": QB_COUNT,
            "qb_variants_per_qb": qbvar // QB_COUNT,
            "fixed_attempt_not_unique_fill": True,
            "continue_after_nonoptimal_call": True,
            "optimizer_retry_count": 0,
            "families_excluded": list(EXCLUDED_FAMILIES),
            "existing_266_arm_claimed": False,
        }, field="arm_sha256"))
    body = {
        "schema": REGISTRY_SCHEMA,
        "arm_order": list(ARM_ORDER),
        "family_order": list(FAMILY_ORDER),
        "profile_order": list(PROFILE_ORDER),
        "comparison_cohort_id": COMPARISON_COHORT_ID,
        "attempts_per_cell": ATTEMPTS_PER_CELL,
        "cells_per_origin_task": CELLS_PER_TASK,
        "attempts_per_origin_task": ATTEMPTS_PER_TASK,
        "arms": rows,
        "families_excluded": list(EXCLUDED_FAMILIES),
        "source_requirement": (
            "exact point-in-time proj_tourney plus one aligned R-block draw matrix"
        ),
        "draw_mean_substitution_forbidden": True,
        "family_mechanism_laws": {
            "leverage": (
                "proj_tourney objective; sequential prior-roster no-goods; "
                "maximum overlap seven"
            ),
            "boom": (
                "descending legacy total-draw argsort; one solve per fixed "
                "world; no inter-world no-good"
            ),
            "qbvar": (
                "top eight QBs by draw p90 with canonical-player-ID tie; "
                "per-QB sequential no-goods reset; maximum overlap six"
            ),
        },
        "fixed_attempt_law": (
            "one optimizer callback per scheduled slot; zero retry; continue "
            "after optimal, infeasible, or error"
        ),
        "legacy_266_ids_reused": False,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "promotion_authority": False,
    }
    return _with_hash(body, field="registry_sha256")


def build_player_bundle_v1(
    *, slate: Mapping[str, object], players: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build the required score-free, point-in-time objective source bundle."""
    retained_slate = _slate(slate)
    normalized: list[dict[str, object]] = []
    for ordinal, raw in enumerate(players):
        row = _mapping(raw, label=f"player[{ordinal}]")
        if set(row) != _PLAYER_FIELDS:
            _fail("supported-232 player fields differ")
        if any(
            fragment in key.lower()
            for key in row
            for fragment in _FORBIDDEN_OUTCOME_FRAGMENTS
        ):
            _fail("player bundle contains a forbidden outcome-like field")
        try:
            player = rw.PlayerSpec.from_mapping(row)
        except Exception as exc:
            raise CorpusR6Supported232GenerationV1Error(
                f"player[{ordinal}] DK identity differs: {exc}"
            ) from exc
        objective = row["proj_tourney"]
        if isinstance(objective, (bool, np.bool_)) or not isinstance(
            objective, (int, float, np.integer, np.floating)
        ) or not np.isfinite(float(objective)):
            _fail("proj_tourney must be one finite number")
        normalized.append({
            "id": player.player_id,
            "pos": player.position,
            "team": player.team,
            "opp": player.opponent,
            "game_id": player.game_id,
            "salary": player.salary,
            "proj_tourney": float(objective),
        })
    player_ids = [str(row["id"]) for row in normalized]
    if (
        not normalized
        or player_ids != sorted(set(player_ids))
        or sum(row["pos"] == "QB" for row in normalized) < QB_COUNT
    ):
        _fail("player rows must be canonical unique ID order with at least eight QBs")
    body = {
        "schema": PLAYER_BUNDLE_SCHEMA,
        "slate": retained_slate,
        "player_count": len(normalized),
        "player_order": player_ids,
        "player_order_sha256": canonical_sha256_v1(player_ids),
        "objective_field": "proj_tourney",
        "objective_source_law": "exact-point-in-time-vector-required",
        "draw_mean_substitution_used": False,
        "players": normalized,
        "players_sha256": canonical_sha256_v1(normalized),
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
        "test_only": True,
        "promotion_authority": False,
    }
    return _with_hash(body, field="player_bundle_sha256")


def validate_player_bundle_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="player bundle")
    expected_fields = {
        "schema", "slate", "player_count", "player_order",
        "player_order_sha256", "objective_field", "objective_source_law",
        "draw_mean_substitution_used", "players", "players_sha256",
        "outcome_fields_read", "uses_realized_outcomes", "test_only",
        "promotion_authority", "player_bundle_sha256",
    }
    if set(item) != expected_fields or item.get("schema") != PLAYER_BUNDLE_SCHEMA:
        _fail("player bundle fields/schema differ")
    digest = _sha(item["player_bundle_sha256"], label="player bundle SHA-256")
    if digest != canonical_sha256_v1({
        key: row for key, row in item.items() if key != "player_bundle_sha256"
    }):
        _fail("player bundle self-hash differs")
    rebuilt = build_player_bundle_v1(
        slate=_mapping(item["slate"], label="player bundle slate"),
        players=[
            _mapping(row, label="player bundle row")
            for row in _sequence(item["players"], label="player bundle rows")
        ],
    )
    if rebuilt != item:
        _fail("player bundle canonical replay differs")
    return item


def local_file_identity_v1(path: str | os.PathLike[str]) -> dict[str, object]:
    """Hash one regular local file for a test-only request."""
    retained = Path(path).resolve(strict=True)
    info = retained.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
        _fail("local input must be one nonempty regular file")
    body = retained.read_bytes()
    if len(body) != info.st_size:
        _fail("local input changed while hashing")
    return {
        "path": str(retained),
        "bytes": len(body),
        "sha256": sha256(body).hexdigest(),
    }


def _local_identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"path", "bytes", "sha256"}:
        _fail(f"{label} fields differ")
    path = item["path"]
    if type(path) is not str or not path or not Path(path).is_absolute():
        _fail(f"{label} path must be absolute")
    return {
        "path": path,
        "bytes": _integer(item["bytes"], label=f"{label} bytes", minimum=1),
        "sha256": _sha(item["sha256"], label=f"{label} SHA-256"),
    }


def _exact_read_local(identity: Mapping[str, object], *, maximum: int) -> bytes:
    retained = _local_identity(identity, label="local input identity")
    if int(retained["bytes"]) > maximum:
        _fail("local input exceeds its byte ceiling")
    path = Path(str(retained["path"]))
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        _fail("local input is no longer a regular file")
    body = path.read_bytes()
    after = path.stat()
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or len(body) != retained["bytes"]
        or sha256(body).hexdigest() != retained["sha256"]
    ):
        _fail("local input content identity differs")
    return body


def build_local_task_request_v1(
    *,
    player_bundle: Mapping[str, object],
    player_bundle_identity: Mapping[str, object],
    draws_identity: Mapping[str, object],
    draws: np.ndarray,
    origin_id: str,
) -> dict[str, object]:
    """Bind one slate/origin task without claiming executable source authority."""
    bundle = validate_player_bundle_v1(player_bundle)
    origin = _identifier(origin_id, label="origin ID")
    if origin not in rw.WORLD_BLOCKS:
        _fail("origin must be one canonical R0--R4 block")
    matrix = np.asarray(draws)
    if matrix.shape != (bundle["player_count"], WORLDS_PER_ORIGIN):
        _fail("draw matrix shape differs from player bundle/origin law")
    matrix_sha = _matrix_sha256(matrix)
    registry = supported232_arm_registry_v1()
    profile_registry = profiles.population_profile_registry_v1()
    body = {
        "schema": REQUEST_SCHEMA,
        "task_id": f"supported232-{bundle['slate']['slate_id']}-{origin}",
        "slate": bundle["slate"],
        "origin_id": origin,
        "player_bundle_identity": _local_identity(
            player_bundle_identity, label="player bundle identity"
        ),
        "player_bundle_sha256": bundle["player_bundle_sha256"],
        "player_count": bundle["player_count"],
        "player_order_sha256": bundle["player_order_sha256"],
        "objective_field": "proj_tourney",
        "objective_source_required": True,
        "draw_mean_substitution_forbidden": True,
        "draws_identity": _local_identity(draws_identity, label="draws identity"),
        "draws_dtype": "float32",
        "draws_shape": [bundle["player_count"], WORLDS_PER_ORIGIN],
        "draws_matrix_sha256": matrix_sha,
        "arm_order": list(ARM_ORDER),
        "arm_registry_sha256": registry["registry_sha256"],
        "profile_order": list(PROFILE_ORDER),
        "profile_registry_sha256": profile_registry["registry_sha256"],
        "family_order": list(FAMILY_ORDER),
        "families_excluded": list(EXCLUDED_FAMILIES),
        "attempts_per_cell": ATTEMPTS_PER_CELL,
        "cell_count": CELLS_PER_TASK,
        "total_optimizer_calls": ATTEMPTS_PER_TASK,
        "comparison_cohort_id": COMPARISON_COHORT_ID,
        "generation_mechanism": (
            "legacy-family-semantics-single-call-fixed-attempt-v1"
        ),
        "optimizer_backend": "nfl_dfs.optimizer.lineup.optimize",
        "optimizer_call_receipts_required": True,
        "solver_proof_authority_claimed": False,
        "local_only": True,
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_performed": False,
        "production_change_licensed": False,
        "promotion_authority": False,
        "test_only": True,
    }
    return validate_local_task_request_v1(
        _with_hash(body, field="request_sha256")
    )


def validate_local_task_request_v1(value: object) -> dict[str, object]:
    request = _mapping(value, label="supported-232 request")
    expected = {
        "schema", "task_id", "slate", "origin_id",
        "player_bundle_identity", "player_bundle_sha256", "player_count",
        "player_order_sha256", "objective_field", "objective_source_required",
        "draw_mean_substitution_forbidden", "draws_identity", "draws_dtype",
        "draws_shape", "draws_matrix_sha256", "arm_order",
        "arm_registry_sha256", "profile_order", "profile_registry_sha256",
        "family_order", "families_excluded", "attempts_per_cell",
        "cell_count", "total_optimizer_calls", "comparison_cohort_id",
        "generation_mechanism", "optimizer_backend",
        "optimizer_call_receipts_required", "solver_proof_authority_claimed",
        "local_only", "outcome_fields_read", "uses_realized_outcomes",
        "historical_scoring_performed", "production_change_licensed",
        "promotion_authority", "test_only", "request_sha256",
    }
    if set(request) != expected or request.get("schema") != REQUEST_SCHEMA:
        _fail("supported-232 request fields/schema differ")
    retained_sha = _sha(request["request_sha256"], label="request SHA-256")
    if retained_sha != canonical_sha256_v1({
        key: row for key, row in request.items() if key != "request_sha256"
    }):
        _fail("supported-232 request self-hash differs")
    slate = _slate(request["slate"])
    origin = _identifier(request["origin_id"], label="request origin")
    player_count = _integer(
        request["player_count"], label="request player count", minimum=rw.ROSTER_SIZE
    )
    registry = supported232_arm_registry_v1()
    profile_registry = profiles.population_profile_registry_v1()
    fixed = (
        origin in rw.WORLD_BLOCKS
        and request["task_id"] == f"supported232-{slate['slate_id']}-{origin}"
        and request["objective_field"] == "proj_tourney"
        and request["objective_source_required"] is True
        and request["draw_mean_substitution_forbidden"] is True
        and request["draws_dtype"] == "float32"
        and request["draws_shape"] == [player_count, WORLDS_PER_ORIGIN]
        and request["arm_order"] == list(ARM_ORDER)
        and request["arm_registry_sha256"] == registry["registry_sha256"]
        and request["profile_order"] == list(PROFILE_ORDER)
        and request["profile_registry_sha256"]
        == profile_registry["registry_sha256"]
        and request["family_order"] == list(FAMILY_ORDER)
        and request["families_excluded"] == list(EXCLUDED_FAMILIES)
        and request["attempts_per_cell"] == ATTEMPTS_PER_CELL
        and request["cell_count"] == CELLS_PER_TASK
        and request["total_optimizer_calls"] == ATTEMPTS_PER_TASK
        and request["comparison_cohort_id"] == COMPARISON_COHORT_ID
        and request["generation_mechanism"]
        == "legacy-family-semantics-single-call-fixed-attempt-v1"
        and request["optimizer_backend"] == "nfl_dfs.optimizer.lineup.optimize"
        and request["optimizer_call_receipts_required"] is True
        and request["solver_proof_authority_claimed"] is False
        and request["local_only"] is True
        and request["outcome_fields_read"] == []
        and request["uses_realized_outcomes"] is False
        and request["historical_scoring_performed"] is False
        and request["production_change_licensed"] is False
        and request["promotion_authority"] is False
        and request["test_only"] is True
    )
    if not fixed:
        _fail("supported-232 request fixed policy differs")
    _local_identity(request["player_bundle_identity"], label="player bundle identity")
    _local_identity(request["draws_identity"], label="draws identity")
    _sha(request["player_bundle_sha256"], label="player bundle self-hash")
    _sha(request["player_order_sha256"], label="player order SHA-256")
    _sha(request["draws_matrix_sha256"], label="draw matrix SHA-256")
    return request


def validate_local_task_inputs_v1(
    request_value: object,
    *,
    player_bundle: object,
    draws: np.ndarray,
) -> dict[str, object]:
    """Dry-validate one task without making an optimizer call."""
    request = validate_local_task_request_v1(request_value)
    bundle = validate_player_bundle_v1(player_bundle)
    matrix = np.asarray(draws)
    if (
        bundle["slate"] != request["slate"]
        or bundle["player_bundle_sha256"] != request["player_bundle_sha256"]
        or bundle["player_count"] != request["player_count"]
        or bundle["player_order_sha256"] != request["player_order_sha256"]
        or list(matrix.shape) != request["draws_shape"]
        or _matrix_sha256(matrix) != request["draws_matrix_sha256"]
    ):
        _fail("supported-232 request/local scientific inputs differ")
    qbs = [row for row in bundle["players"] if row["pos"] == "QB"]
    if len(qbs) < QB_COUNT:
        _fail("supported-232 runtime requires at least eight QBs")
    body = {
        "schema": DRY_VALIDATION_SCHEMA,
        "task_id": request["task_id"],
        "request_sha256": request["request_sha256"],
        "player_bundle_sha256": bundle["player_bundle_sha256"],
        "draws_matrix_sha256": request["draws_matrix_sha256"],
        "origin_id": request["origin_id"],
        "player_count": request["player_count"],
        "world_count": WORLDS_PER_ORIGIN,
        "arm_count": len(ARM_ORDER),
        "profile_count": len(PROFILE_ORDER),
        "cell_count": CELLS_PER_TASK,
        "total_optimizer_calls": ATTEMPTS_PER_TASK,
        "point_in_time_objective_present": True,
        "draw_mean_substitution_used": False,
        "role_game_dark_excluded": True,
        "optimizer_calls_made": 0,
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
        "test_only": True,
        "ready_for_local_generation": True,
        "production_authority": False,
    }
    return _with_hash(body, field="dry_validation_sha256")


def load_and_dry_validate_local_task_v1(
    request_value: object,
) -> tuple[dict[str, object], dict[str, object], np.ndarray]:
    """Exact-open both request-bound local files, then dry-validate them."""
    request = validate_local_task_request_v1(request_value)
    player_bytes = _exact_read_local(
        _mapping(request["player_bundle_identity"], label="player identity"),
        maximum=MAXIMUM_PLAYER_BUNDLE_BYTES,
    )
    try:
        player_value = json.loads(player_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6Supported232GenerationV1Error(
            "player bundle file is not JSON"
        ) from exc
    draw_bytes = _exact_read_local(
        _mapping(request["draws_identity"], label="draw identity"),
        maximum=MAXIMUM_DRAW_FILE_BYTES,
    )
    try:
        loaded = np.load(io.BytesIO(draw_bytes), allow_pickle=False)
    except Exception as exc:
        raise CorpusR6Supported232GenerationV1Error(
            "draw file is not one safe NPY array"
        ) from exc
    matrix = np.asarray(loaded)
    if matrix.dtype != np.dtype(np.float32) or matrix.ndim != 2:
        _fail("draw file dtype/rank differs")
    matrix = np.ascontiguousarray(matrix, dtype=np.float32)
    matrix.flags.writeable = False
    validation = validate_local_task_inputs_v1(
        request, player_bundle=player_value, draws=matrix
    )
    return validation, validate_player_bundle_v1(player_value), matrix


@dataclass(frozen=True, slots=True)
class OptimizerCallSpec:
    """One actual supported-232 optimizer-call coordinate."""

    arm_id: str
    profile_id: str
    origin_id: str
    global_call_ordinal: int
    cell_call_ordinal: int
    family_id: str
    family_slot: int
    family_slot_count: int
    objective_kind: str
    objective_values: tuple[float, ...]
    objective_source: tuple[tuple[str, object], ...]
    locks: tuple[str, ...]
    banned_lineups: tuple[tuple[str, ...], ...]
    max_overlap: int
    players: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class OptimizerCallOutcome:
    status: str
    roster: tuple[str, ...] | None = None
    detail: str = ""


OptimizerCallback = Callable[[OptimizerCallSpec], OptimizerCallOutcome]


def legacy_optimizer_callback_v1(spec: OptimizerCallSpec) -> OptimizerCallOutcome:
    """Make exactly one call through the existing legacy optimizer API."""
    profile = profiles.population_profile_v1(spec.profile_id)
    pool = [
        {**row, "supported232_objective": spec.objective_values[index]}
        for index, row in enumerate(spec.players)
    ]
    try:
        lineup = legacy_lineup.optimize(
            pool,
            budget=rw.SALARY_CAP,
            locks=set(spec.locks),
            banned_lineups=[frozenset(row) for row in spec.banned_lineups],
            stack=profile.as_effective_policy().stack.as_stack_rules(),
            objective_col="supported232_objective",
            max_overlap=spec.max_overlap,
            punt_max_salary=None,
            punt_min=0,
            min_salary=profile.min_lineup_salary,
            max_per_game=profile.max_from_game,
            env={},
        )
    except Exception as exc:  # one scheduled call still receives an error receipt
        return OptimizerCallOutcome(
            status="error", detail=f"{type(exc).__name__}:{exc}"
        )
    if lineup is None:
        return OptimizerCallOutcome(status="infeasible", detail="no optimal lineup")
    return OptimizerCallOutcome(
        status="optimal",
        roster=tuple(sorted(str(player_id) for player_id in lineup.ids)),
        detail="legacy optimizer returned Optimal",
    )


def _lineup_id(slate_id: str, roster: Sequence[str]) -> str:
    return canonical_sha256_v1({
        "slate_id": slate_id,
        "roster_player_ids": list(roster),
    })


def _objective_source(value: Mapping[str, object]) -> tuple[tuple[str, object], ...]:
    return tuple(sorted(value.items()))


def _arm_row(arm_id: str) -> dict[str, object]:
    registry = supported232_arm_registry_v1()
    for row in registry["arms"]:
        if row["arm_id"] == arm_id:
            return dict(row)
    _fail("unknown supported-232 arm")


def _normalize_optimizer_outcome(
    value: object,
    *,
    spec: OptimizerCallSpec,
    player_specs: Sequence[rw.PlayerSpec],
) -> OptimizerCallOutcome:
    if type(value) is not OptimizerCallOutcome or value.status not in {
        "optimal", "infeasible", "error"
    } or type(value.detail) is not str:
        _fail("optimizer callback outcome type/status differs")
    if value.status != "optimal":
        if value.roster is not None:
            _fail("non-optimal optimizer outcome carried a roster")
        return value
    if value.roster is None:
        _fail("optimal optimizer outcome omitted its roster")
    roster = tuple(sorted(value.roster))
    if roster != value.roster or len(roster) != rw.ROSTER_SIZE or len(set(roster)) != len(roster):
        _fail("optimizer roster identity differs")
    try:
        profiles.audit_profile_roster_v1(player_specs, roster, spec.profile_id)
    except Exception as exc:
        raise CorpusR6Supported232GenerationV1Error(
            f"optimizer roster failed {spec.profile_id} audit: {exc}"
        ) from exc
    if not set(spec.locks).issubset(roster):
        _fail("optimizer roster omitted a family lock")
    if any(
        len(set(roster).intersection(previous)) > spec.max_overlap
        for previous in spec.banned_lineups
    ):
        _fail("optimizer roster violated sequential no-good overlap")
    return OptimizerCallOutcome(
        status="optimal", roster=roster, detail=value.detail
    )


def _call_receipt(
    spec: OptimizerCallSpec,
    outcome: OptimizerCallOutcome,
    *,
    slate_id: str,
) -> dict[str, object]:
    roster = None if outcome.roster is None else list(outcome.roster)
    body = {
        "schema": CALL_RECEIPT_SCHEMA,
        "global_call_ordinal": spec.global_call_ordinal,
        "cell_call_ordinal": spec.cell_call_ordinal,
        "arm_id": spec.arm_id,
        "profile_id": spec.profile_id,
        "origin_id": spec.origin_id,
        "family_id": spec.family_id,
        "family_slot": spec.family_slot,
        "family_slot_count": spec.family_slot_count,
        "objective_kind": spec.objective_kind,
        "objective_sha256": canonical_sha256_v1(list(spec.objective_values)),
        "objective_source": dict(spec.objective_source),
        "locks": list(spec.locks),
        "banned_lineup_count": len(spec.banned_lineups),
        "banned_lineups_sha256": canonical_sha256_v1(
            [list(row) for row in spec.banned_lineups]
        ),
        "max_overlap": spec.max_overlap,
        "optimizer_call_made": True,
        "status": outcome.status,
        "roster_player_ids": roster,
        "lineup_id": (
            None if roster is None else _lineup_id(slate_id, roster)
        ),
        "detail_sha256": sha256(outcome.detail.encode("utf-8")).hexdigest(),
        "solver_proof_authority_claimed": False,
    }
    return _with_hash(body, field="call_receipt_sha256")


def _execute_cell_v1(
    *,
    request: Mapping[str, object],
    bundle: Mapping[str, object],
    draws: np.ndarray,
    arm_id: str,
    profile_id: str,
    global_start: int,
    optimizer: OptimizerCallback,
) -> dict[str, object]:
    arm = _arm_row(arm_id)
    dose = dict(arm["attempts_by_family"])
    player_rows = tuple(dict(row) for row in bundle["players"])
    player_specs = tuple(rw.PlayerSpec.from_mapping(row) for row in player_rows)
    base_objective = tuple(float(row["proj_tourney"]) for row in player_rows)
    positions = [str(row["pos"]) for row in player_rows]
    boom_order = tuple(
        int(value) for value in engine._boom_world_order(draws, positions, {})
    )
    if (
        len(boom_order) != WORLDS_PER_ORIGIN
        or len(set(boom_order)) != WORLDS_PER_ORIGIN
    ):
        _fail("legacy boom world order differs")
    qb_rows = [
        (index, str(row["id"]))
        for index, row in enumerate(player_rows)
        if row["pos"] == "QB"
    ]
    qb_rows.sort(
        key=lambda row: (
            -float(np.percentile(draws[row[0]], 90)), row[1]
        )
    )
    top_qbs = tuple(player_id for _index, player_id in qb_rows[:QB_COUNT])
    if len(top_qbs) != QB_COUNT:
        _fail("supported-232 QB ranking contains fewer than eight QBs")

    calls: list[dict[str, object]] = []
    occurrences: list[dict[str, object]] = []
    leverage_banned: list[tuple[str, ...]] = []
    qb_banned: dict[str, list[tuple[str, ...]]] = {qb: [] for qb in top_qbs}
    cell_call = 0

    def perform(
        *,
        family_id: str,
        family_slot: int,
        objective: tuple[float, ...],
        objective_kind: str,
        source: Mapping[str, object],
        locks: tuple[str, ...],
        banned: Sequence[tuple[str, ...]],
        max_overlap: int,
    ) -> OptimizerCallOutcome:
        nonlocal cell_call
        spec = OptimizerCallSpec(
            arm_id=arm_id,
            profile_id=profile_id,
            origin_id=str(request["origin_id"]),
            global_call_ordinal=global_start + cell_call,
            cell_call_ordinal=cell_call,
            family_id=family_id,
            family_slot=family_slot,
            family_slot_count=int(dose[family_id]),
            objective_kind=objective_kind,
            objective_values=objective,
            objective_source=_objective_source(source),
            locks=tuple(sorted(locks)),
            banned_lineups=tuple(tuple(sorted(row)) for row in banned),
            max_overlap=max_overlap,
            players=player_rows,
        )
        try:
            raw = optimizer(spec)
        except Exception as exc:
            raw = OptimizerCallOutcome(
                status="error", detail=f"{type(exc).__name__}:{exc}"
            )
        retained = _normalize_optimizer_outcome(
            raw, spec=spec, player_specs=player_specs
        )
        receipt = _call_receipt(
            spec, retained, slate_id=str(bundle["slate"]["slate_id"])
        )
        calls.append(receipt)
        if retained.roster is not None:
            occurrences.append({
                "candidate_ordinal": cell_call,
                "family_id": family_id,
                "family_slot": family_slot,
                "lineup_id": receipt["lineup_id"],
                "roster_player_ids": list(retained.roster),
            })
        cell_call += 1
        return retained

    for slot in range(int(dose["leverage"])):
        outcome = perform(
            family_id="leverage",
            family_slot=slot,
            objective=base_objective,
            objective_kind="point-in-time-proj-tourney",
            source={"kind": "base-objective", "sequence_index": slot},
            locks=(),
            banned=leverage_banned,
            max_overlap=7,
        )
        if outcome.roster is not None:
            leverage_banned.append(outcome.roster)

    for slot in range(int(dose["boom"])):
        world_index = boom_order[slot]
        outcome_values = tuple(float(value) for value in draws[:, world_index])
        perform(
            family_id="boom",
            family_slot=slot,
            objective=outcome_values,
            objective_kind="top-total-draw-world",
            source={"kind": "draw-world", "world_index": world_index},
            locks=(),
            banned=(),
            max_overlap=8,
        )

    variants_per_qb = int(dose["qbvar"]) // QB_COUNT
    qb_slot = 0
    for qb_rank, qb_id in enumerate(top_qbs):
        for variant in range(variants_per_qb):
            outcome = perform(
                family_id="qbvar",
                family_slot=qb_slot,
                objective=base_objective,
                objective_kind="point-in-time-proj-tourney-qb-lock",
                source={
                    "kind": "base-objective-qb-lock",
                    "qb_id": qb_id,
                    "qb_rank": qb_rank,
                    "variant_index": variant,
                },
                locks=(qb_id,),
                banned=qb_banned[qb_id],
                max_overlap=6,
            )
            if outcome.roster is not None:
                qb_banned[qb_id].append(outcome.roster)
            qb_slot += 1

    if cell_call != ATTEMPTS_PER_CELL or len(calls) != ATTEMPTS_PER_CELL:
        _fail("supported-232 cell did not make exactly 232 optimizer calls")
    family_receipts = []
    for family in FAMILY_ORDER:
        family_calls = [row for row in calls if row["family_id"] == family]
        counts = Counter(str(row["status"]) for row in family_calls)
        family_receipts.append({
            "family_id": family,
            "scheduled_attempts": int(dose[family]),
            "attempted_optimizer_calls": len(family_calls),
            "optimal_calls": counts["optimal"],
            "infeasible_calls": counts["infeasible"],
            "error_calls": counts["error"],
        })
    status_counts = Counter(str(row["status"]) for row in calls)
    unique_lineups = sorted({str(row["lineup_id"]) for row in occurrences})
    body = {
        "schema": CELL_RESULT_SCHEMA,
        "cell_id": f"{arm_id}--{profile_id}--{request['origin_id']}",
        "arm_id": arm_id,
        "arm_sha256": arm["arm_sha256"],
        "profile_id": profile_id,
        "profile_sha256": profiles.population_profile_v1(profile_id).fingerprint,
        "origin_id": request["origin_id"],
        "comparison_cohort_id": COMPARISON_COHORT_ID,
        "attempts_by_family": dose,
        "scheduled_attempts": ATTEMPTS_PER_CELL,
        "attempted_optimizer_calls": len(calls),
        "status_counts": {
            status: status_counts[status]
            for status in ("optimal", "infeasible", "error")
        },
        "family_receipts": family_receipts,
        "calls": calls,
        "calls_sha256": canonical_sha256_v1(calls),
        "occurrence_count": len(occurrences),
        "occurrences": occurrences,
        "occurrences_sha256": canonical_sha256_v1(occurrences),
        "unique_lineup_count": len(unique_lineups),
        "unique_lineup_ids_sha256": canonical_sha256_v1(unique_lineups),
        "top_qb_ids": list(top_qbs),
        "profile_audit_applied_to_every_optimal_call": True,
        "role_game_dark_excluded": True,
        "solver_proof_authority_claimed": False,
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
        "test_only": True,
        "promotion_authority": False,
    }
    return _with_hash(body, field="cell_result_sha256")


def execute_local_task_v1(
    request_value: object,
    *,
    player_bundle: object,
    draws: np.ndarray,
    optimizer: OptimizerCallback = legacy_optimizer_callback_v1,
) -> dict[str, object]:
    """Execute all 12 cells for one local R-origin request.

    One callback invocation is one optimizer-call attempt.  Callback failures
    receive error receipts and do not reduce the fixed 232-call dose.
    """
    if not callable(optimizer):
        _fail("optimizer callback is not callable")
    request = validate_local_task_request_v1(request_value)
    bundle = validate_player_bundle_v1(player_bundle)
    matrix = np.asarray(draws)
    dry = validate_local_task_inputs_v1(
        request, player_bundle=bundle, draws=matrix
    )
    cells: list[dict[str, object]] = []
    global_start = 0
    for arm_id in ARM_ORDER:
        for profile_id in PROFILE_ORDER:
            cell = _execute_cell_v1(
                request=request,
                bundle=bundle,
                draws=matrix,
                arm_id=arm_id,
                profile_id=profile_id,
                global_start=global_start,
                optimizer=optimizer,
            )
            cells.append(cell)
            global_start += ATTEMPTS_PER_CELL
    if global_start != ATTEMPTS_PER_TASK:
        _fail("supported-232 task optimizer-call total differs")
    body = {
        "schema": RESULT_SCHEMA,
        "task_id": request["task_id"],
        "request_sha256": request["request_sha256"],
        "dry_validation_sha256": dry["dry_validation_sha256"],
        "slate": request["slate"],
        "origin_id": request["origin_id"],
        "arm_order": list(ARM_ORDER),
        "profile_order": list(PROFILE_ORDER),
        "cell_count": len(cells),
        "attempts_per_cell": ATTEMPTS_PER_CELL,
        "total_optimizer_calls": global_start,
        "all_cells_equal_fixed_attempt": all(
            cell["attempted_optimizer_calls"] == ATTEMPTS_PER_CELL
            for cell in cells
        ),
        "cells": cells,
        "cells_sha256": canonical_sha256_v1(cells),
        "point_in_time_objective_present": True,
        "draw_mean_substitution_used": False,
        "role_game_dark_excluded": True,
        "solver_proof_authority_claimed": False,
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_performed": False,
        "production_change_licensed": False,
        "promotion_authority": False,
        "test_only": True,
    }
    return validate_generation_result_v1(
        _with_hash(body, field="generation_result_sha256")
    )


def validate_generation_result_v1(value: object) -> dict[str, object]:
    result = _mapping(value, label="supported-232 result")
    expected = {
        "schema", "task_id", "request_sha256", "dry_validation_sha256",
        "slate", "origin_id", "arm_order", "profile_order", "cell_count",
        "attempts_per_cell", "total_optimizer_calls",
        "all_cells_equal_fixed_attempt", "cells", "cells_sha256",
        "point_in_time_objective_present", "draw_mean_substitution_used",
        "role_game_dark_excluded", "solver_proof_authority_claimed",
        "outcome_fields_read", "uses_realized_outcomes",
        "historical_scoring_performed", "production_change_licensed",
        "promotion_authority", "test_only", "generation_result_sha256",
    }
    if set(result) != expected or result.get("schema") != RESULT_SCHEMA:
        _fail("supported-232 result fields/schema differ")
    digest = _sha(
        result["generation_result_sha256"], label="generation result SHA-256"
    )
    if digest != canonical_sha256_v1({
        key: row for key, row in result.items()
        if key != "generation_result_sha256"
    }):
        _fail("supported-232 result self-hash differs")
    cells = [
        _mapping(row, label="supported-232 cell")
        for row in _sequence(result["cells"], label="supported-232 cells")
    ]
    retained_slate = _slate(result["slate"])
    retained_origin = _identifier(result["origin_id"], label="result origin")
    expected_pairs = [
        (arm_id, profile_id)
        for arm_id in ARM_ORDER
        for profile_id in PROFILE_ORDER
    ]
    if (
        retained_origin not in rw.WORLD_BLOCKS
        or result["task_id"]
        != f"supported232-{retained_slate['slate_id']}-{retained_origin}"
        or _SHA256.fullmatch(str(result["request_sha256"])) is None
        or _SHA256.fullmatch(str(result["dry_validation_sha256"])) is None
        or result["arm_order"] != list(ARM_ORDER)
        or result["profile_order"] != list(PROFILE_ORDER)
        or result["cell_count"] != CELLS_PER_TASK
        or len(cells) != CELLS_PER_TASK
        or [(cell.get("arm_id"), cell.get("profile_id")) for cell in cells]
        != expected_pairs
        or result["attempts_per_cell"] != ATTEMPTS_PER_CELL
        or result["total_optimizer_calls"] != ATTEMPTS_PER_TASK
        or result["all_cells_equal_fixed_attempt"] is not True
        or result["cells_sha256"] != canonical_sha256_v1(cells)
        or result["point_in_time_objective_present"] is not True
        or result["draw_mean_substitution_used"] is not False
        or result["role_game_dark_excluded"] is not True
        or result["solver_proof_authority_claimed"] is not False
        or result["outcome_fields_read"] != []
        or result["uses_realized_outcomes"] is not False
        or result["historical_scoring_performed"] is not False
        or result["production_change_licensed"] is not False
        or result["promotion_authority"] is not False
        or result["test_only"] is not True
    ):
        _fail("supported-232 result fixed contents differ")
    global_ordinal = 0
    cell_fields = {
        "schema", "cell_id", "arm_id", "arm_sha256", "profile_id",
        "profile_sha256", "origin_id", "comparison_cohort_id",
        "attempts_by_family", "scheduled_attempts",
        "attempted_optimizer_calls", "status_counts", "family_receipts",
        "calls", "calls_sha256", "occurrence_count", "occurrences",
        "occurrences_sha256", "unique_lineup_count",
        "unique_lineup_ids_sha256", "top_qb_ids",
        "profile_audit_applied_to_every_optimal_call",
        "role_game_dark_excluded", "solver_proof_authority_claimed",
        "outcome_fields_read", "uses_realized_outcomes", "test_only",
        "promotion_authority", "cell_result_sha256",
    }
    call_fields = {
        "schema", "global_call_ordinal", "cell_call_ordinal", "arm_id",
        "profile_id", "origin_id", "family_id", "family_slot",
        "family_slot_count", "objective_kind", "objective_sha256",
        "objective_source", "locks", "banned_lineup_count",
        "banned_lineups_sha256", "max_overlap", "optimizer_call_made",
        "status", "roster_player_ids", "lineup_id", "detail_sha256",
        "solver_proof_authority_claimed", "call_receipt_sha256",
    }
    family_receipt_fields = {
        "family_id", "scheduled_attempts", "attempted_optimizer_calls",
        "optimal_calls", "infeasible_calls", "error_calls",
    }
    for cell, (expected_arm, expected_profile) in zip(
        cells, expected_pairs, strict=True
    ):
        if set(cell) != cell_fields or cell.get("schema") != CELL_RESULT_SCHEMA:
            _fail("supported-232 cell schema differs")
        cell_sha = _sha(cell.get("cell_result_sha256"), label="cell result SHA-256")
        if cell_sha != canonical_sha256_v1({
            key: row for key, row in cell.items() if key != "cell_result_sha256"
        }):
            _fail("supported-232 cell self-hash differs")
        arm = _arm_row(expected_arm)
        dose = dict(arm["attempts_by_family"])
        profile = profiles.population_profile_v1(expected_profile)
        calls = [
            _mapping(row, label="supported-232 call")
            for row in _sequence(cell.get("calls"), label="supported-232 calls")
        ]
        status_counts = _mapping(cell.get("status_counts"), label="status counts")
        if set(status_counts) != {"optimal", "infeasible", "error"} or any(
            type(count) is not int or count < 0 for count in status_counts.values()
        ):
            _fail("supported-232 status counts differ")
        top_qbs = _sequence(cell.get("top_qb_ids"), label="top QB IDs")
        if (
            len(top_qbs) != QB_COUNT
            or any(type(qb) is not str or not qb for qb in top_qbs)
            or len(set(top_qbs)) != QB_COUNT
        ):
            _fail("supported-232 top-QB identity differs")
        family_receipts = [
            _mapping(row, label="family receipt")
            for row in _sequence(
                cell.get("family_receipts"), label="family receipts"
            )
        ]
        if (
            cell.get("cell_id")
            != f"{expected_arm}--{expected_profile}--{result['origin_id']}"
            or cell.get("arm_id") != expected_arm
            or cell.get("arm_sha256") != arm["arm_sha256"]
            or cell.get("profile_id") != expected_profile
            or cell.get("profile_sha256") != profile.fingerprint
            or cell.get("origin_id") != result["origin_id"]
            or cell.get("comparison_cohort_id") != COMPARISON_COHORT_ID
            or cell.get("attempts_by_family") != dose
            or cell.get("scheduled_attempts") != ATTEMPTS_PER_CELL
            or cell.get("attempted_optimizer_calls") != ATTEMPTS_PER_CELL
            or len(calls) != ATTEMPTS_PER_CELL
            or cell.get("calls_sha256") != canonical_sha256_v1(calls)
            or sum(status_counts.values()) != ATTEMPTS_PER_CELL
            or len(family_receipts) != len(FAMILY_ORDER)
            or [row.get("family_id") for row in family_receipts]
            != list(FAMILY_ORDER)
            or cell.get("profile_audit_applied_to_every_optimal_call") is not True
            or cell.get("role_game_dark_excluded") is not True
            or cell.get("solver_proof_authority_claimed") is not False
            or cell.get("outcome_fields_read") != []
            or cell.get("uses_realized_outcomes") is not False
            or cell.get("test_only") is not True
            or cell.get("promotion_authority") is not False
        ):
            _fail("supported-232 cell fixed contents differ")
        expected_family_slots = [
            (family, slot, int(dose[family]))
            for family in FAMILY_ORDER
            for slot in range(int(dose[family]))
        ]
        observed_statuses: Counter[str] = Counter()
        observed_family_statuses: dict[str, Counter[str]] = {
            family: Counter() for family in FAMILY_ORDER
        }
        expected_occurrences: list[dict[str, object]] = []
        leverage_optimal = 0
        qb_optimal = {str(qb): 0 for qb in top_qbs}
        observed_boom_worlds: set[int] = set()
        for cell_ordinal, call in enumerate(calls):
            if set(call) != call_fields:
                _fail("supported-232 call fields differ")
            call_sha = _sha(
                call.get("call_receipt_sha256"), label="call receipt SHA-256"
            )
            expected_family, expected_slot, expected_family_count = (
                expected_family_slots[cell_ordinal]
            )
            status = call.get("status")
            if status not in {"optimal", "infeasible", "error"}:
                _fail("supported-232 call status differs")
            locks = _sequence(call.get("locks"), label="call locks")
            source = _mapping(call.get("objective_source"), label="objective source")
            expected_kind = {
                "leverage": "point-in-time-proj-tourney",
                "boom": "top-total-draw-world",
                "qbvar": "point-in-time-proj-tourney-qb-lock",
            }[expected_family]
            expected_overlap = {"leverage": 7, "boom": 8, "qbvar": 6}[
                expected_family
            ]
            if expected_family == "leverage":
                source_ok = source == {
                    "kind": "base-objective", "sequence_index": expected_slot
                }
                locks_ok = locks == []
                banned_count_ok = call.get("banned_lineup_count") == leverage_optimal
            elif expected_family == "boom":
                world_index = source.get("world_index")
                source_ok = (
                    set(source) == {"kind", "world_index"}
                    and source.get("kind") == "draw-world"
                    and type(world_index) is int
                    and 0 <= world_index < WORLDS_PER_ORIGIN
                    and world_index not in observed_boom_worlds
                )
                if source_ok:
                    observed_boom_worlds.add(int(world_index))
                locks_ok = locks == []
                banned_count_ok = call.get("banned_lineup_count") == 0
            else:
                variants_per_qb = int(dose["qbvar"]) // QB_COUNT
                qb_rank, variant = divmod(expected_slot, variants_per_qb)
                qb_id = str(top_qbs[qb_rank])
                source_ok = source == {
                    "kind": "base-objective-qb-lock",
                    "qb_id": qb_id,
                    "qb_rank": qb_rank,
                    "variant_index": variant,
                }
                locks_ok = locks == [qb_id]
                banned_count_ok = (
                    call.get("banned_lineup_count") == qb_optimal[qb_id]
                )
            if (
                call.get("schema") != CALL_RECEIPT_SCHEMA
                or call_sha != canonical_sha256_v1({
                    key: row for key, row in call.items()
                    if key != "call_receipt_sha256"
                })
                or call.get("global_call_ordinal") != global_ordinal
                or call.get("cell_call_ordinal") != cell_ordinal
                or call.get("arm_id") != expected_arm
                or call.get("profile_id") != expected_profile
                or call.get("origin_id") != result["origin_id"]
                or call.get("family_id") != expected_family
                or call.get("family_slot") != expected_slot
                or call.get("family_slot_count") != expected_family_count
                or call.get("objective_kind") != expected_kind
                or not source_ok
                or not locks_ok
                or not banned_count_ok
                or call.get("max_overlap") != expected_overlap
                or call.get("optimizer_call_made") is not True
                or call.get("solver_proof_authority_claimed") is not False
                or _SHA256.fullmatch(str(call.get("objective_sha256"))) is None
                or _SHA256.fullmatch(
                    str(call.get("banned_lineups_sha256"))
                ) is None
                or _SHA256.fullmatch(str(call.get("detail_sha256"))) is None
            ):
                _fail("supported-232 call receipt differs")
            roster = call.get("roster_player_ids")
            lineup_id = call.get("lineup_id")
            if status == "optimal":
                if (
                    not isinstance(roster, list)
                    or len(roster) != rw.ROSTER_SIZE
                    or roster != sorted(set(roster))
                    or any(type(player_id) is not str or not player_id for player_id in roster)
                    or lineup_id != _lineup_id(
                        str(_mapping(result["slate"], label="result slate")["slate_id"]),
                        roster,
                    )
                ):
                    _fail("supported-232 optimal call roster differs")
                expected_occurrences.append({
                    "candidate_ordinal": cell_ordinal,
                    "family_id": expected_family,
                    "family_slot": expected_slot,
                    "lineup_id": lineup_id,
                    "roster_player_ids": roster,
                })
                if expected_family == "leverage":
                    leverage_optimal += 1
                elif expected_family == "qbvar":
                    qb_optimal[str(locks[0])] += 1
            elif roster is not None or lineup_id is not None:
                _fail("supported-232 non-optimal call carried a roster")
            observed_statuses[str(status)] += 1
            observed_family_statuses[expected_family][str(status)] += 1
            global_ordinal += 1
        if dict(status_counts) != {
            status: observed_statuses[status]
            for status in ("optimal", "infeasible", "error")
        }:
            _fail("supported-232 cell status derivation differs")
        for receipt, family in zip(family_receipts, FAMILY_ORDER, strict=True):
            counts = observed_family_statuses[family]
            if (
                set(receipt) != family_receipt_fields
                or receipt.get("family_id") != family
                or receipt.get("scheduled_attempts") != dose[family]
                or receipt.get("attempted_optimizer_calls") != dose[family]
                or receipt.get("optimal_calls") != counts["optimal"]
                or receipt.get("infeasible_calls") != counts["infeasible"]
                or receipt.get("error_calls") != counts["error"]
            ):
                _fail("supported-232 family receipt differs")
        occurrences = _sequence(cell.get("occurrences"), label="occurrences")
        unique_lineup_ids = sorted({
            str(row["lineup_id"]) for row in expected_occurrences
        })
        if (
            occurrences != expected_occurrences
            or cell.get("occurrence_count") != len(expected_occurrences)
            or cell.get("occurrences_sha256")
            != canonical_sha256_v1(expected_occurrences)
            or cell.get("unique_lineup_count") != len(unique_lineup_ids)
            or cell.get("unique_lineup_ids_sha256")
            != canonical_sha256_v1(unique_lineup_ids)
        ):
            _fail("supported-232 occurrence derivation differs")
    if global_ordinal != ATTEMPTS_PER_TASK:
        _fail("supported-232 validated call total differs")
    return result


__all__ = [
    "ARM_ORDER",
    "ATTEMPTS_PER_CELL",
    "ATTEMPTS_PER_TASK",
    "CELLS_PER_TASK",
    "COMPARISON_COHORT_ID",
    "CorpusR6Supported232GenerationV1Error",
    "EXCLUDED_FAMILIES",
    "FAMILY_ORDER",
    "OptimizerCallOutcome",
    "OptimizerCallSpec",
    "PROFILE_ORDER",
    "build_local_task_request_v1",
    "build_player_bundle_v1",
    "canonical_json_bytes_v1",
    "canonical_sha256_v1",
    "execute_local_task_v1",
    "legacy_optimizer_callback_v1",
    "load_and_dry_validate_local_task_v1",
    "local_file_identity_v1",
    "supported232_arm_registry_v1",
    "validate_generation_result_v1",
    "validate_local_task_inputs_v1",
    "validate_local_task_request_v1",
    "validate_player_bundle_v1",
]
