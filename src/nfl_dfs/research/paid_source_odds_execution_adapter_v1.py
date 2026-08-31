"""Score-blind execution adapter for the incremental Odds prop ablation.

The scientific trace in :mod:`odds_prop_override_ablation_v1` deliberately
accepts already-materialized crossing bodies.  That is the correct terminal
validation boundary, but it is not an execution path: a caller could build
those bodies without ever letting the prop-on/prop-off projection state reach
candidate generation or retrieval.

This module supplies that missing path.  It accepts only exact-identity,
point-in-time player metadata, a complete candidate-generation plan, and an
exact centered player-world matrix.  For each source state it:

* reconstructs the frozen 45/55 blended player means from the support census;
* shifts the same centered player worlds to those means;
* runs the production DraftKings MILP for the fixed leverage and boom solves;
* scores each generated population in both on/off selection-world matrices;
* runs the production coverage-194 selector at exact K80; and
* emits exact bodies accepted by ``build_odds_prop_override_influence_trace_v1``.

There is no outcome argument, warehouse client, object listing, live-source
fallback, policy switch, or cloud implementation here.  A caller supplies a
create-once-style output binder; every returned identity is checked against
the bytes the adapter itself generated.  Missing immutable inputs or a
population that cannot genuinely produce K80 fail closed with machine-readable
contract requirements instead of synthetic or caller-prebuilt outputs.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re
from time import perf_counter
from typing import Final

import numpy as np
import pulp

from nfl_dfs.backtest import engine as production_engine
from nfl_dfs.optimizer.construction_presets import resolve_construction_preset
from nfl_dfs.optimizer.lineup import Lineup, optimize, select_tail_entries
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import odds_prop_override_ablation_v1 as odds
from nfl_dfs.research import paid_source_ablation_registry_v1 as registry


PLAYER_INPUT_SCHEMA: Final = "odds-prop-execution-player-input/v1"
CANDIDATE_INPUT_SCHEMA: Final = "odds-prop-execution-candidate-input/v1"
CENTERED_WORLD_SCHEMA: Final = "odds-prop-execution-centered-worlds/v1"
SHIFTED_WORLD_SCHEMA: Final = "odds-prop-execution-shifted-worlds/v1"
RUNTIME_ATTESTATION_SCHEMA: Final = "odds-prop-execution-runtime-attestation/v1"
EXECUTION_RECEIPT_SCHEMA: Final = "odds-prop-execution-receipt/v1"

GENERATION_FAMILY: Final = "production-leverage-plus-boom-milp-v1"
SELECTION_LAW: Final = "production-greedy-coverage-194-k80-v1"
TAIL_LINE: Final = 194.0
ENTRY_BUDGET: Final = registry.ENTRY_BUDGET
RETRY_LIMIT: Final = 1
CENTERING_TOLERANCE: Final = 1e-9

_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")
_POSITIONS: Final = frozenset({"QB", "RB", "WR", "TE", "DST"})
_FORBIDDEN_OUTCOME_KEYS: Final = frozenset({
    "actual",
    "actual_points",
    "actual_score",
    "contest_finish",
    "contest_rank",
    "lineup_score",
    "payout",
    "realized_points",
    "realized_score",
    "winner",
    "winning_score",
})


class PaidSourceOddsExecutionAdapterV1Error(ValueError):
    """The score-blind Odds execution contract differs."""


class OddsExecutionContractMissingV1Error(PaidSourceOddsExecutionAdapterV1Error):
    """Immutable inputs cannot support the requested genuine execution."""

    def __init__(self, requirements: Sequence[str]):
        normalized = tuple(sorted(set(str(value) for value in requirements)))
        self.missing_requirements = normalized
        super().__init__(
            "Odds execution missing immutable contract requirements: "
            + ", ".join(normalized)
        )


OutputBinder = Callable[[str, bytes], Mapping[str, object]]


def _fail(message: str) -> None:
    raise PaidSourceOddsExecutionAdapterV1Error(message)


def _missing(*requirements: str) -> None:
    raise OddsExecutionContractMissingV1Error(requirements)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object], expected: set[str] | frozenset[str], *, label: str,
) -> None:
    missing = sorted(set(expected) - set(value))
    extra = sorted(set(value) - set(expected))
    if missing:
        raise OddsExecutionContractMissingV1Error(
            [f"{label}.{field}" for field in missing]
        )
    if extra:
        _fail(f"{label} has unrecognized fields: {extra}")


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _number(value: object, *, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        _fail(f"{label} must be a finite number")
    return float(value)


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _timestamp(value: object, *, label: str) -> tuple[str, datetime]:
    text = _string(value, label=label)
    if _UTC.fullmatch(text) is None:
        _fail(f"{label} must be canonical UTC seconds")
    try:
        parsed = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise PaidSourceOddsExecutionAdapterV1Error(
            f"{label} is not a valid timestamp"
        ) from exc
    return text, parsed


def _reject_outcomes(value: object, *, label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string field")
            normalized = key.strip().lower()
            if (
                normalized in _FORBIDDEN_OUTCOME_KEYS
                or "grade" in normalized
                or (
                    "realized" in normalized
                    and normalized != "uses_realized_outcomes"
                )
            ):
                _fail(f"{label} contains forbidden outcome field {key!r}")
            if normalized == "uses_realized_outcomes" and item is not False:
                _fail(f"{label}.uses_realized_outcomes must be false")
            if normalized == "outcome_columns_read" and item != []:
                _fail(f"{label}.outcome_columns_read must be empty")
            _reject_outcomes(item, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, item in enumerate(value):
            _reject_outcomes(item, label=f"{label}[{ordinal}]")


def _policy() -> dict[str, object]:
    return {
        "evidence_class": "outcome-blind-source-influence-only",
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "value_claim": "not_evaluated",
        **{field: False for field in registry.FALSE_AUTHORITY_FIELDS},
    }


def _slate(value: object) -> dict[str, object]:
    item = _mapping(value, label="Odds execution slate")
    _exact_keys(item, {"slate_id", "season", "week"}, label="Odds execution slate")
    if (
        type(item["slate_id"]) is not str
        or not item["slate_id"]
        or type(item["season"]) is not int
        or item["season"] < 2000
        or type(item["week"]) is not int
        or not 1 <= item["week"] <= 18
    ):
        _fail("Odds execution slate differs")
    return item


def _identity(
    value: object,
    *,
    label: str,
    expected_raw: bytes | None = None,
) -> dict[str, object]:
    try:
        normalized = source.normalize_object_identity_v2(value, label=label)
    except ValueError as exc:
        raise PaidSourceOddsExecutionAdapterV1Error(str(exc)) from exc
    if expected_raw is not None and (
        normalized["sha256"] != sha256(expected_raw).hexdigest()
        or normalized["bytes"] != len(expected_raw)
    ):
        _fail(f"{label} differs from exact bytes")
    return normalized


def _bind_json_input(
    body: Mapping[str, object], identity: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    raw = registry.canonical_json_bytes(dict(body))
    return _identity(identity, label=label, expected_raw=raw)


def _bind_output(
    *,
    name: str,
    raw: bytes,
    bind_output: OutputBinder,
) -> dict[str, object]:
    try:
        supplied = bind_output(name, raw)
    except Exception as exc:
        raise PaidSourceOddsExecutionAdapterV1Error(
            f"output binder failed for {name!r}"
        ) from exc
    return _identity(supplied, label=f"generated output {name}", expected_raw=raw)


def build_odds_execution_player_input_v1(
    *,
    support_census: Mapping[str, object],
    player_snapshot_time_utc: str,
    source_player_snapshot_identity: Mapping[str, object],
    player_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build the canonical point-in-time optimizer player input body."""
    census = odds.validate_odds_prop_override_support_census_v1(support_census)
    snapshot, snapshot_dt = _timestamp(
        player_snapshot_time_utc, label="player snapshot time"
    )
    _, lock_dt = _timestamp(census["common_lock_time_utc"], label="common lock")
    if snapshot_dt >= lock_dt:
        _fail("optimizer player snapshot is not strictly before common lock")
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for ordinal, raw in enumerate(player_rows):
        row = _mapping(raw, label=f"optimizer player row[{ordinal}]")
        _exact_keys(
            row,
            {
                "gsis_id",
                "position",
                "team",
                "opponent",
                "game_id",
                "salary",
                "leverage_objective_offset",
            },
            label=f"optimizer player row[{ordinal}]",
        )
        player_id = _string(row["gsis_id"], label="optimizer player ID")
        position = _string(row["position"], label="optimizer player position")
        team = _string(row["team"], label="optimizer player team")
        opponent = _string(row["opponent"], label="optimizer player opponent")
        game_id = _string(row["game_id"], label="optimizer player game")
        if player_id in seen or position not in _POSITIONS or team == opponent:
            _fail("optimizer player metadata differs")
        seen.add(player_id)
        salary = _integer(row["salary"], label="optimizer player salary", minimum=1)
        if salary > 50_000:
            _fail("optimizer player salary exceeds the DraftKings cap")
        rows.append({
            "gsis_id": player_id,
            "position": position,
            "team": team,
            "opponent": opponent,
            "game_id": game_id,
            "salary": salary,
            "leverage_objective_offset": _number(
                row["leverage_objective_offset"],
                label="optimizer leverage objective offset",
            ),
        })
    if not rows:
        _missing("optimizer-player-input.nonempty-player-rows")
    support_ids = [
        str(row["gsis_id"])
        for row in census["cells"][0]["rows"]
    ]
    if [row["gsis_id"] for row in rows] != support_ids:
        _fail("optimizer player rows do not preserve support-census player order")
    body = {
        "schema_version": PLAYER_INPUT_SCHEMA,
        "slate": census["slate"],
        "support_census_sha256": census["support_census_sha256"],
        "common_lock_identity": census["common_lock_identity"],
        "player_snapshot_time_utc": snapshot,
        "source_player_snapshot_identity": _identity(
            source_player_snapshot_identity,
            label="source player snapshot identity",
        ),
        "point_in_time_status": "strictly-pre-common-lock",
        "player_rows": rows,
        "row_count": len(rows),
        "ordered_player_ids_sha256": registry.canonical_sha256(support_ids),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    _reject_outcomes(body, label="optimizer player input")
    return body


def validate_odds_execution_player_input_v1(
    value: object,
    *,
    support_census: Mapping[str, object],
    identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    item = _mapping(value, label="optimizer player input")
    _reject_outcomes(item, label="optimizer player input")
    _exact_keys(
        item,
        {
            "schema_version",
            "slate",
            "support_census_sha256",
            "common_lock_identity",
            "player_snapshot_time_utc",
            "source_player_snapshot_identity",
            "point_in_time_status",
            "player_rows",
            "row_count",
            "ordered_player_ids_sha256",
            "outcome_columns_read",
            "uses_realized_outcomes",
        },
        label="optimizer player input",
    )
    if item.get("schema_version") != PLAYER_INPUT_SCHEMA:
        _fail("optimizer player input schema differs")
    rebuilt = build_odds_execution_player_input_v1(
        support_census=support_census,
        player_snapshot_time_utc=str(item.get("player_snapshot_time_utc")),
        source_player_snapshot_identity=_mapping(
            item.get("source_player_snapshot_identity"),
            label="source player snapshot identity",
        ),
        player_rows=[
            _mapping(row, label="optimizer player row")
            for row in _sequence(item.get("player_rows"), label="optimizer player rows")
        ],
    )
    if item != rebuilt:
        _fail("optimizer player input canonical replay differs")
    return rebuilt, _bind_json_input(rebuilt, identity, label="optimizer player input")


def build_odds_execution_candidate_input_v1(
    *,
    support_census: Mapping[str, object],
    construction_preset_id: str,
    leverage_solve_count: int,
    boom_solve_count: int,
    locked_player_ids: Sequence[str] = (),
    banned_player_ids: Sequence[str] = (),
) -> dict[str, object]:
    """Build the complete fixed generation/selection plan (not outputs)."""
    census = odds.validate_odds_prop_override_support_census_v1(support_census)
    try:
        preset = resolve_construction_preset(construction_preset_id)
    except ValueError as exc:
        raise PaidSourceOddsExecutionAdapterV1Error(str(exc)) from exc
    locks = [str(value) for value in locked_player_ids]
    bans = [str(value) for value in banned_player_ids]
    if (
        any(not value for value in locks + bans)
        or len(locks) != len(set(locks))
        or len(bans) != len(set(bans))
        or set(locks) & set(bans)
    ):
        _fail("candidate input locks/bans differ")
    body = {
        "schema_version": CANDIDATE_INPUT_SCHEMA,
        "slate": census["slate"],
        "support_census_sha256": census["support_census_sha256"],
        "generation_family": GENERATION_FAMILY,
        "construction_preset_receipt": preset.receipt(),
        "leverage_solve_count": _integer(
            leverage_solve_count, label="leverage solve count", minimum=1
        ),
        "boom_solve_count": _integer(
            boom_solve_count, label="boom solve count", minimum=1
        ),
        "retry_limit": RETRY_LIMIT,
        "candidate_deduplication_law": "first-generated-roster-wins",
        "boom_world_order_law": "descending-total-player-world-stable-ordinal-tie",
        "locked_player_ids": sorted(locks),
        "banned_player_ids": sorted(bans),
        "selection_law": SELECTION_LAW,
        "tail_line": TAIL_LINE,
        "entry_budget": ENTRY_BUDGET,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    _reject_outcomes(body, label="candidate generation input")
    return body


def validate_odds_execution_candidate_input_v1(
    value: object,
    *,
    support_census: Mapping[str, object],
    identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    item = _mapping(value, label="candidate generation input")
    _reject_outcomes(item, label="candidate generation input")
    expected_fields = {
        "schema_version",
        "slate",
        "support_census_sha256",
        "generation_family",
        "construction_preset_receipt",
        "leverage_solve_count",
        "boom_solve_count",
        "retry_limit",
        "candidate_deduplication_law",
        "boom_world_order_law",
        "locked_player_ids",
        "banned_player_ids",
        "selection_law",
        "tail_line",
        "entry_budget",
        "outcome_columns_read",
        "uses_realized_outcomes",
    }
    _exact_keys(item, expected_fields, label="candidate generation input")
    if item.get("schema_version") != CANDIDATE_INPUT_SCHEMA:
        _fail("candidate generation input schema differs")
    receipt = _mapping(
        item.get("construction_preset_receipt"),
        label="construction preset receipt",
    )
    preset_id = receipt.get("base_preset_id")
    rebuilt = build_odds_execution_candidate_input_v1(
        support_census=support_census,
        construction_preset_id=_string(preset_id, label="construction preset ID"),
        leverage_solve_count=_integer(
            item.get("leverage_solve_count"), label="leverage solve count", minimum=1
        ),
        boom_solve_count=_integer(
            item.get("boom_solve_count"), label="boom solve count", minimum=1
        ),
        locked_player_ids=[
            _string(value, label="locked player ID")
            for value in _sequence(
                item.get("locked_player_ids"), label="locked player IDs"
            )
        ],
        banned_player_ids=[
            _string(value, label="banned player ID")
            for value in _sequence(
                item.get("banned_player_ids"), label="banned player IDs"
            )
        ],
    )
    if item != rebuilt:
        _fail("candidate generation input canonical replay differs")
    return rebuilt, _bind_json_input(
        rebuilt, identity, label="candidate generation input"
    )


def canonical_centered_world_bytes_v1(
    *,
    support_census: Mapping[str, object],
    player_ids: Sequence[str],
    centered_worlds: np.ndarray,
) -> bytes:
    """Encode exact centered player worlds without any realized labels."""
    census = odds.validate_odds_prop_override_support_census_v1(support_census)
    ids = [str(value) for value in player_ids]
    expected_ids = [str(row["gsis_id"]) for row in census["cells"][0]["rows"]]
    values = np.asarray(centered_worlds, dtype="<f8")
    if (
        ids != expected_ids
        or values.ndim != 2
        or values.shape[0] != len(ids)
        or values.shape[1] < 1
        or not np.isfinite(values).all()
    ):
        _fail("centered player-world input dimensions differ")
    if float(np.max(np.abs(values.mean(axis=1)), initial=0.0)) > CENTERING_TOLERANCE:
        _fail("player-world input is not row-centered")
    header = {
        "schema_version": CENTERED_WORLD_SCHEMA,
        "slate": census["slate"],
        "support_census_sha256": census["support_census_sha256"],
        "player_ids": ids,
        "dtype": "<f8",
        "shape": [int(values.shape[0]), int(values.shape[1])],
        "centering_law": "subtract-each-player-row-mean-before-source-state-shift",
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    return registry.canonical_json_bytes(header) + b"\n" + values.tobytes(order="C")


def _open_centered_worlds(
    *,
    raw: bytes,
    identity: Mapping[str, object],
    support_census: Mapping[str, object],
) -> tuple[dict[str, object], np.ndarray, dict[str, object]]:
    if type(raw) is not bytes:
        _missing("centered-player-world-input.exact-bytes")
    normalized_identity = _identity(
        identity, label="centered player-world input", expected_raw=raw
    )
    try:
        header_raw, matrix_raw = raw.split(b"\n", 1)
        header_value = json.loads(header_raw)
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise PaidSourceOddsExecutionAdapterV1Error(
            "centered player-world input encoding differs"
        ) from exc
    header = _mapping(header_value, label="centered player-world header")
    _reject_outcomes(header, label="centered player-world header")
    _exact_keys(
        header,
        {
            "schema_version",
            "slate",
            "support_census_sha256",
            "player_ids",
            "dtype",
            "shape",
            "centering_law",
            "outcome_columns_read",
            "uses_realized_outcomes",
        },
        label="centered player-world header",
    )
    census = odds.validate_odds_prop_override_support_census_v1(support_census)
    ids = [
        _string(value, label="centered player-world player ID")
        for value in _sequence(header.get("player_ids"), label="player-world IDs")
    ]
    shape = [
        _integer(value, label="centered player-world dimension", minimum=1)
        for value in _sequence(header.get("shape"), label="player-world shape")
    ]
    expected_ids = [str(row["gsis_id"]) for row in census["cells"][0]["rows"]]
    if (
        registry.canonical_json_bytes(header) != header_raw
        or header.get("schema_version") != CENTERED_WORLD_SCHEMA
        or header.get("slate") != census["slate"]
        or header.get("support_census_sha256") != census["support_census_sha256"]
        or header.get("dtype") != "<f8"
        or header.get("centering_law")
        != "subtract-each-player-row-mean-before-source-state-shift"
        or ids != expected_ids
        or len(shape) != 2
        or shape[0] != len(ids)
        or len(matrix_raw) != math.prod(shape) * np.dtype("<f8").itemsize
    ):
        _fail("centered player-world input authority differs")
    values = np.frombuffer(matrix_raw, dtype="<f8").reshape(tuple(shape))
    if (
        not np.isfinite(values).all()
        or float(np.max(np.abs(values.mean(axis=1)), initial=0.0))
        > CENTERING_TOLERANCE
    ):
        _fail("centered player-world matrix differs")
    return header, values, normalized_identity


def _runtime_attestation(value: object) -> dict[str, object]:
    item = _mapping(value, label="Odds execution runtime attestation")
    _reject_outcomes(item, label="Odds execution runtime attestation")
    _exact_keys(
        item,
        {
            "schema_version",
            "execution_id",
            "task_index",
            "attempt",
            "source_commit_sha",
            "image_digest",
            "worker_started_at_utc",
        },
        label="Odds execution runtime attestation",
    )
    execution_id = _string(item["execution_id"], label="runtime execution ID")
    commit = _string(item["source_commit_sha"], label="runtime source commit")
    image = _string(item["image_digest"], label="runtime image digest")
    started, _ = _timestamp(item["worker_started_at_utc"], label="worker start")
    if (
        item.get("schema_version") != RUNTIME_ATTESTATION_SCHEMA
        or _IDENTIFIER.fullmatch(execution_id) is None
        or _COMMIT.fullmatch(commit) is None
        or _IMAGE.fullmatch(image) is None
    ):
        _fail("Odds execution runtime attestation differs")
    return {
        "schema_version": RUNTIME_ATTESTATION_SCHEMA,
        "execution_id": execution_id,
        "task_index": _integer(item["task_index"], label="runtime task index"),
        "attempt": _integer(item["attempt"], label="runtime attempt", minimum=1),
        "source_commit_sha": commit,
        "image_digest": image,
        "worker_started_at_utc": started,
    }


def _cell_projection_rows(
    census: Mapping[str, object], cell_id: str,
) -> list[dict[str, object]]:
    for cell in census["cells"]:
        if cell["cell"]["cell_id"] == cell_id:
            return [dict(row) for row in cell["rows"]]
    _fail(f"support census lacks Odds cell {cell_id!r}")


def _optimizer_players(
    *,
    player_input: Mapping[str, object],
    projection_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    by_id = {str(row["gsis_id"]): dict(row) for row in projection_rows}
    players: list[dict[str, object]] = []
    for row in player_input["player_rows"]:
        player_id = str(row["gsis_id"])
        projection = by_id[player_id]
        players.append({
            "id": player_id,
            "pos": row["position"],
            "team": row["team"],
            "opp": row["opponent"],
            "game_id": row["game_id"],
            "salary": row["salary"],
            "proj": float(projection["blended_mean"]),
            "proj_generation": (
                float(projection["blended_mean"])
                + float(row["leverage_objective_offset"])
            ),
        })
    return players


def _solve_once_with_retry(
    *,
    players: list[dict[str, object]],
    objective_col: str,
    preset_id: str,
    locks: set[str],
    bans: set[str],
    banned_lineups: Sequence[frozenset[str]],
) -> tuple[Lineup | None, dict[str, object]]:
    preset = resolve_construction_preset(preset_id)
    attempts = 0
    retries = 0
    solver_errors = 0
    duration_ms = 0.0
    for retry_ordinal in range(RETRY_LIMIT + 1):
        attempts += 1
        started = perf_counter()
        try:
            lineup = optimize(
                players,
                stack=preset.stack,
                objective_col=objective_col,
                locks=locks,
                bans=bans,
                banned_lineups=list(banned_lineups),
                max_overlap=preset.max_overlap,
                punt_max_salary=preset.punt_max_salary,
                punt_min=preset.punt_min,
                min_salary=preset.min_salary,
                min_games=preset.min_games,
                max_per_game=(preset.max_per_game or None),
                env=preset.optimizer_environment(),
            )
            duration_ms += (perf_counter() - started) * 1000.0
            return lineup, {
                "attempt_count": attempts,
                "retry_count": retries,
                "solver_error_count": solver_errors,
                "infeasible_count": int(lineup is None),
                "duration_ms": duration_ms,
            }
        except pulp.PulpSolverError:
            duration_ms += (perf_counter() - started) * 1000.0
            solver_errors += 1
            if retry_ordinal < RETRY_LIMIT:
                retries += 1
                continue
            return None, {
                "attempt_count": attempts,
                "retry_count": retries,
                "solver_error_count": solver_errors,
                "infeasible_count": 0,
                "duration_ms": duration_ms,
            }
    raise AssertionError("unreachable retry loop")


def _lineup_identity(lineup: Lineup) -> tuple[str, list[str], frozenset[str]]:
    roster = frozenset(str(player["id"]) for player in lineup.players)
    ordered = sorted(roster)
    digest = registry.canonical_sha256(ordered)
    return f"lineup-sha256-{digest}", ordered, roster


def _generate_population(
    *,
    cell_id: str,
    census: Mapping[str, object],
    player_input: Mapping[str, object],
    candidate_input: Mapping[str, object],
    shifted_worlds: np.ndarray,
) -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]:
    projection_rows = _cell_projection_rows(census, cell_id)
    players = _optimizer_players(
        player_input=player_input, projection_rows=projection_rows
    )
    preset_id = str(
        candidate_input["construction_preset_receipt"]["base_preset_id"]
    )
    locks = set(str(value) for value in candidate_input["locked_player_ids"])
    bans = set(str(value) for value in candidate_input["banned_player_ids"])
    all_player_ids = {str(row["id"]) for row in players}
    if not locks.issubset(all_player_ids) or not bans.issubset(all_player_ids):
        _missing("candidate-generation-input.locks-and-bans-within-player-universe")

    generated: list[dict[str, object]] = []
    seen: set[frozenset[str]] = set()
    leverage_banned: list[frozenset[str]] = []
    family = {
        "leverage": {
            "requested": int(candidate_input["leverage_solve_count"]),
            "attempts": 0,
            "retries": 0,
            "solver_errors": 0,
            "infeasible": 0,
            "duplicates": 0,
            "unique_candidates": 0,
            "runtime_ms": 0.0,
        },
        "boom": {
            "requested": int(candidate_input["boom_solve_count"]),
            "attempts": 0,
            "retries": 0,
            "solver_errors": 0,
            "infeasible": 0,
            "duplicates": 0,
            "unique_candidates": 0,
            "runtime_ms": 0.0,
        },
    }

    def record(family_id: str, lineup: Lineup | None, facts: Mapping[str, object]) -> None:
        state = family[family_id]
        state["attempts"] += int(facts["attempt_count"])
        state["retries"] += int(facts["retry_count"])
        state["solver_errors"] += int(facts["solver_error_count"])
        state["infeasible"] += int(facts["infeasible_count"])
        state["runtime_ms"] += float(facts["duration_ms"])
        if lineup is None:
            return
        candidate_id, ordered, roster = _lineup_identity(lineup)
        if roster in seen:
            state["duplicates"] += 1
            return
        seen.add(roster)
        state["unique_candidates"] += 1
        generated.append({
            "candidate_id": candidate_id,
            "player_ids": ordered,
            "family": family_id,
            "roster": roster,
        })

    for _ in range(int(candidate_input["leverage_solve_count"])):
        lineup, facts = _solve_once_with_retry(
            players=players,
            objective_col="proj_generation",
            preset_id=preset_id,
            locks=locks,
            bans=bans,
            banned_lineups=leverage_banned,
        )
        record("leverage", lineup, facts)
        if lineup is None:
            break
        roster = frozenset(str(player["id"]) for player in lineup.players)
        leverage_banned.append(roster)

    # Use the production primitive itself.  In particular, its NumPy argsort
    # reverse ordering defines the exact world-ID tiebreak; a superficially
    # equivalent Python sort uses the opposite tie order.
    world_order = [
        int(value)
        for value in production_engine._boom_world_order(
            shifted_worlds,
            [str(row["position"]) for row in player_input["player_rows"]],
            {},
        )
    ]
    boom_count = int(candidate_input["boom_solve_count"])
    if boom_count > len(world_order):
        _missing("centered-player-world-input.world-count-at-least-boom-solve-count")
    for world_ordinal in world_order[:boom_count]:
        boom_players = [
            {**player, "proj_boom_world": float(shifted_worlds[index, world_ordinal])}
            for index, player in enumerate(players)
        ]
        lineup, facts = _solve_once_with_retry(
            players=boom_players,
            objective_col="proj_boom_world",
            preset_id=preset_id,
            locks=locks,
            bans=bans,
            banned_lineups=(),
        )
        record("boom", lineup, facts)

    if len(generated) < ENTRY_BUDGET:
        _missing(
            f"generated-population.{cell_id}.at-least-{ENTRY_BUDGET}-unique-rosters",
            "candidate-generation-input.sufficient-solve-budget-and-feasible-diversity",
        )
    rows = [
        {"candidate_id": row["candidate_id"], "player_ids": row["player_ids"]}
        for row in generated
    ]
    failures = sum(
        int(value["solver_errors"]) + int(value["infeasible"])
        for value in family.values()
    )
    retries = sum(int(value["retries"]) for value in family.values())
    body = odds.build_odds_candidate_population_body_v1(
        support_census=census,
        population_cell_id=cell_id,
        candidate_rows=rows,
        solve_failure_count=failures,
        retry_count=retries,
    )
    receipt = {
        "cell_id": cell_id,
        "families": [
            {"family_id": family_id, **family[family_id]}
            for family_id in ("leverage", "boom")
        ],
        "requested_solve_count": sum(int(value["requested"]) for value in family.values()),
        "attempt_count": sum(int(value["attempts"]) for value in family.values()),
        "retry_count": retries,
        "solver_error_count": sum(int(value["solver_errors"]) for value in family.values()),
        "infeasible_count": sum(int(value["infeasible"]) for value in family.values()),
        "duplicate_count": sum(int(value["duplicates"]) for value in family.values()),
        "unique_candidate_count": len(generated),
        "runtime_ms": sum(float(value["runtime_ms"]) for value in family.values()),
    }
    return body, generated, receipt


def _shifted_world_bytes(
    *,
    census: Mapping[str, object],
    cell_id: str,
    player_ids: Sequence[str],
    values: np.ndarray,
) -> bytes:
    matrix = np.asarray(values, dtype="<f8")
    header = {
        "schema_version": SHIFTED_WORLD_SCHEMA,
        "slate": census["slate"],
        "support_census_sha256": census["support_census_sha256"],
        "selection_world_cell_id": cell_id,
        "player_ids": [str(value) for value in player_ids],
        "dtype": "<f8",
        "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
        "shift_law": "same-centered-rows-plus-cell-specific-45-55-blended-mean",
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    return registry.canonical_json_bytes(header) + b"\n" + matrix.tobytes(order="C")


def _candidate_totals(
    generated: Sequence[Mapping[str, object]],
    *,
    player_ids: Sequence[str],
    worlds: np.ndarray,
) -> np.ndarray:
    player_index = {str(player_id): ordinal for ordinal, player_id in enumerate(player_ids)}
    totals = np.empty((len(generated), worlds.shape[1]), dtype=np.float64)
    for ordinal, row in enumerate(generated):
        try:
            indices = [player_index[str(player_id)] for player_id in row["player_ids"]]
        except KeyError as exc:
            raise PaidSourceOddsExecutionAdapterV1Error(
                "generated roster leaves the immutable player universe"
            ) from exc
        totals[ordinal] = worlds[indices].sum(axis=0, dtype=np.float64)
    return totals


def execute_odds_prop_override_cross_v1(
    *,
    support_census: Mapping[str, object],
    player_input: Mapping[str, object],
    player_input_identity: Mapping[str, object],
    candidate_input: Mapping[str, object],
    candidate_input_identity: Mapping[str, object],
    centered_world_bytes: bytes,
    centered_world_identity: Mapping[str, object],
    runtime_attestation: Mapping[str, object],
    bind_output: OutputBinder,
) -> dict[str, object]:
    """Execute and bind the complete score-blind on/off 2 x 2 crossing."""
    started = perf_counter()
    census = odds.validate_odds_prop_override_support_census_v1(support_census)
    # Retain preregistered zero-dose slates.  They are genuine on/off null
    # contrasts, not execution failures, and omitting them after the support
    # panel is frozen would change the estimand.
    players, players_identity = validate_odds_execution_player_input_v1(
        player_input, support_census=census, identity=player_input_identity
    )
    candidate_plan, candidate_plan_identity = validate_odds_execution_candidate_input_v1(
        candidate_input, support_census=census, identity=candidate_input_identity
    )
    if (
        int(candidate_plan["leverage_solve_count"])
        + int(candidate_plan["boom_solve_count"])
        < ENTRY_BUDGET
    ):
        _missing(f"candidate-generation-input.at-least-{ENTRY_BUDGET}-requested-solves")
    world_header, centered, worlds_identity = _open_centered_worlds(
        raw=centered_world_bytes,
        identity=centered_world_identity,
        support_census=census,
    )
    runtime = _runtime_attestation(runtime_attestation)
    player_ids = [str(value) for value in world_header["player_ids"]]

    populations: dict[str, dict[str, object]] = {}
    generated_rows: dict[str, list[dict[str, object]]] = {}
    population_identities: dict[str, dict[str, object]] = {}
    selection_worlds: dict[str, np.ndarray] = {}
    raw_selection_worlds: dict[str, bytes] = {}
    selection_bodies: dict[str, dict[str, object]] = {}
    selection_identities: dict[str, dict[str, object]] = {}
    matrix_identities: dict[str, dict[str, object]] = {}
    matrix_bytes_by_sha256: dict[str, bytes] = {}
    generation_receipts: list[dict[str, object]] = []

    for cell_id in registry.ODDS_CELL_ORDER:
        projection_rows = _cell_projection_rows(census, cell_id)
        means = np.asarray(
            [float(row["blended_mean"]) for row in projection_rows], dtype=np.float64
        )
        shifted = np.asarray(centered + means[:, None], dtype=np.float64)
        selection_worlds[cell_id] = shifted
        raw_world = _shifted_world_bytes(
            census=census,
            cell_id=cell_id,
            player_ids=player_ids,
            values=shifted,
        )
        raw_selection_worlds[cell_id] = raw_world
        population, generated, generation_receipt = _generate_population(
            cell_id=cell_id,
            census=census,
            player_input=players,
            candidate_input=candidate_plan,
            shifted_worlds=shifted,
        )
        populations[cell_id] = population
        generated_rows[cell_id] = generated
        generation_receipts.append(generation_receipt)

    # Do not invoke a potentially persistent output binder until every
    # immutable input has supported both genuine K80-capable populations.
    # A missing boom-world column, infeasible construction, or exhausted
    # population therefore leaves no half-published source-state output.
    for ordinal, cell_id in enumerate(registry.ODDS_CELL_ORDER):
        raw_world = raw_selection_worlds[cell_id]
        matrix_identity = _bind_output(
            name=f"selection-world-matrices/{cell_id}.bin",
            raw=raw_world,
            bind_output=bind_output,
        )
        matrix_identities[cell_id] = matrix_identity
        matrix_bytes_by_sha256[str(matrix_identity["sha256"])] = raw_world
        selection_body = odds.build_odds_selection_world_body_v1(
            support_census=census,
            selection_world_cell_id=cell_id,
            player_order_sha256=registry.canonical_sha256(player_ids),
            world_count=selection_worlds[cell_id].shape[1],
            world_matrix_sha256=str(matrix_identity["sha256"]),
            world_matrix_bytes=int(matrix_identity["bytes"]),
        )
        selection_identity = _bind_output(
            name=f"selection-world-bodies/{cell_id}.json",
            raw=registry.canonical_json_bytes(selection_body),
            bind_output=bind_output,
        )
        selection_bodies[cell_id] = selection_body
        selection_identities[cell_id] = selection_identity

        population = populations[cell_id]
        population_identity = _bind_output(
            name=f"candidate-populations/{cell_id}.json",
            raw=registry.canonical_json_bytes(population),
            bind_output=bind_output,
        )
        population_identities[cell_id] = population_identity
        generation_receipts[ordinal] = {
            **generation_receipts[ordinal],
            "candidate_population_identity": population_identity,
            "selection_world_body_identity": selection_identity,
            "selection_world_matrix_identity": matrix_identity,
        }

    cell_outputs: list[dict[str, object]] = []
    selection_receipts: list[dict[str, object]] = []
    for population_cell_id, selection_cell_id in registry.ODDS_CROSS_ORDER:
        selection_started = perf_counter()
        candidates = generated_rows[population_cell_id]
        totals = _candidate_totals(
            candidates,
            player_ids=player_ids,
            worlds=selection_worlds[selection_cell_id],
        )
        selected_indices = select_tail_entries(
            totals, ENTRY_BUDGET, TAIL_LINE, env={}
        )
        selection_ms = (perf_counter() - selection_started) * 1000.0
        if len(selected_indices) != ENTRY_BUDGET:
            _missing(
                f"crossing.{population_cell_id}-by-{selection_cell_id}.exact-k80"
            )
        candidate_ids = [str(row["candidate_id"]) for row in candidates]
        selected_ids = [candidate_ids[index] for index in selected_indices]
        book_body = odds.build_odds_selected_book_body_v1(
            support_census=census,
            population_cell_id=population_cell_id,
            selection_world_cell_id=selection_cell_id,
            candidate_population_identity=population_identities[population_cell_id],
            selection_world_identity=selection_identities[selection_cell_id],
            candidate_ids=candidate_ids,
            selected_lineup_ids=selected_ids,
            added_latency_ms=selection_ms,
        )
        book_identity = _bind_output(
            name=(
                "selected-books/"
                f"{population_cell_id}--{selection_cell_id}.json"
            ),
            raw=registry.canonical_json_bytes(book_body),
            bind_output=bind_output,
        )
        cell_outputs.append({
            "population_cell_id": population_cell_id,
            "selection_world_cell_id": selection_cell_id,
            "selection_world_identity": selection_identities[selection_cell_id],
            "selection_world_body": selection_bodies[selection_cell_id],
            "candidate_population_identity": population_identities[population_cell_id],
            "candidate_population_body": populations[population_cell_id],
            "selected_book_identity": book_identity,
            "selected_book_body": book_body,
        })
        selection_receipts.append({
            "population_cell_id": population_cell_id,
            "selection_world_cell_id": selection_cell_id,
            "candidate_count": len(candidate_ids),
            "entry_budget": ENTRY_BUDGET,
            "selection_runtime_ms": selection_ms,
            "selected_book_identity": book_identity,
        })

    trace = odds.build_odds_prop_override_influence_trace_v1(
        support_census=census,
        cell_outputs=cell_outputs,
    )
    odds.validate_odds_prop_override_influence_trace_v1(trace)
    trace_identity = _bind_output(
        name="influence-trace.json",
        raw=registry.canonical_json_bytes(trace),
        bind_output=bind_output,
    )
    elapsed_ms = (perf_counter() - started) * 1000.0
    receipt_body: dict[str, object] = {
        "schema_version": EXECUTION_RECEIPT_SCHEMA,
        "experiment_id": registry.ODDS_EXPERIMENT_ID,
        "slate": census["slate"],
        "support_census_sha256": census["support_census_sha256"],
        "exact_input_identities": {
            "player_input": players_identity,
            "candidate_generation_input": candidate_plan_identity,
            "centered_player_worlds": worlds_identity,
        },
        "runtime_attestation": runtime,
        "implementation": {
            "generation_family": GENERATION_FAMILY,
            "optimizer_callable": "nfl_dfs.optimizer.lineup.optimize",
            "selection_callable": "nfl_dfs.optimizer.lineup.select_tail_entries",
            "selection_law": SELECTION_LAW,
            "tail_line": TAIL_LINE,
            "entry_budget": ENTRY_BUDGET,
            "retry_limit": RETRY_LIMIT,
            "construction_preset_receipt": candidate_plan[
                "construction_preset_receipt"
            ],
        },
        "source_state_application": {
            "model_weight": registry.MODEL_WEIGHT,
            "market_weight": registry.MARKET_WEIGHT,
            "prop_off_rows_physically_removed_before_market_vector": True,
            "same_centered_player_worlds_both_cells": True,
            "centered_player_world_identity": worlds_identity,
            "selection_world_matrix_identities": [
                matrix_identities[cell_id] for cell_id in registry.ODDS_CELL_ORDER
            ],
        },
        "generation_receipts": generation_receipts,
        "selection_receipts": selection_receipts,
        "influence_trace_identity": trace_identity,
        "influence_trace_sha256": trace["influence_trace_sha256"],
        "total_runtime_ms": elapsed_ms,
        "exact_k80_all_crossing_cells": True,
        "automatic_policy_change": "forbidden",
        **_policy(),
    }
    receipt_body["execution_receipt_sha256"] = registry.canonical_sha256(
        receipt_body
    )
    return {
        "execution_receipt": receipt_body,
        "influence_trace": trace,
        "cell_outputs": cell_outputs,
        "world_matrix_bytes_by_sha256": matrix_bytes_by_sha256,
    }


__all__ = [
    "CANDIDATE_INPUT_SCHEMA",
    "CENTERED_WORLD_SCHEMA",
    "EXECUTION_RECEIPT_SCHEMA",
    "OddsExecutionContractMissingV1Error",
    "PLAYER_INPUT_SCHEMA",
    "PaidSourceOddsExecutionAdapterV1Error",
    "RUNTIME_ATTESTATION_SCHEMA",
    "build_odds_execution_candidate_input_v1",
    "build_odds_execution_player_input_v1",
    "canonical_centered_world_bytes_v1",
    "execute_odds_prop_override_cross_v1",
    "validate_odds_execution_candidate_input_v1",
    "validate_odds_execution_player_input_v1",
]
