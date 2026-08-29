"""Score-blind 54-slate boom-first allocation comparison.

This is the small scientific core for the historical K=1 comparison between
the adopted ``160 leverage / 40 boom`` allocation and the equal-work
``40 leverage / 160 boom`` allocation.  Source capture, object transport and
the realized-score boundary live in the companion operator.  This module
owns only canonical input/result contracts, frozen-role injection, CBWU
selection, and the exact-54 terminal.

The experiment intentionally equalizes *requested optimizer work*.  It does
not pad or truncate either arm after deduplication.  Realized unique pool
sizes are outcomes of the candidate generators and are retained as evidence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from hashlib import sha256
import json
import math
import re
from typing import Final

import numpy as np
import pandas as pd

from nfl_dfs.backtest.engine import CandidateBatch, _validate_candidate_batch
from nfl_dfs.inference.multiseed_portfolio import combine_cbwu_books
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.optimizer.lineup import Lineup, select_tail_entries
from nfl_dfs.research import boom_first_historical_paired_v1 as paired
from nfl_dfs.research import corpus_r6_novel_roster_realized_grader_v1 as grader


ADAPTER_ID: Final = "boom-first-allocation-k1-v1"
GENERATION_SNAPSHOT_SCHEMA: Final = (
    "corpus-r6-boom-first-generation-snapshot/v1"
)
TASK_RESULT_SCHEMA: Final = "corpus-r6-boom-first-allocation-task-result/v2"
TERMINAL_SCHEMA: Final = "corpus-r6-boom-first-allocation-terminal/v2"
GRADE_SCHEMA: Final = "corpus-r6-boom-first-allocation-realized-grade/v3"
RUNTIME_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-boom-first-allocation-runtime-authority/v2"
)
PROVIDER_TERMINAL_SCHEMA: Final = (
    "corpus-r6-boom-first-allocation-provider-terminal-execution/v1"
)
TASK0_SMOKE_ENVIRONMENT: Final = (
    "R6_BOOM_FIRST_ALLOCATION_TASK0_SMOKE_SHA256"
)

ARM_ORDER: Final = ("control", "treatment")
BLOCK_ORDER: Final = ("R0", "R1", "R2", "R3", "R4")
SOURCE_PANELS: Final = tuple(
    f"20260815-atlas-money-worlds-r{index}-v1" for index in range(5)
)
REPAIR_PANEL: Final = "20260816-atlas-mvp-repair-r3-2025-v1"
REPAIR_KEY: Final = (2025, 1, "R3")
REPAIR_WORLD_ARTIFACT_URI: Final = (
    "gs://nfl-predictions-503414-raw/cand_scores/"
    "20260815-atlas-money-worlds-r3-v1/2025_w1_0590227023eb.npz"
)
REPAIR_CANDIDATE_ARTIFACT_URI: Final = (
    "gs://nfl-predictions-503414-raw/cand_scores/"
    "20260816-atlas-mvp-repair-r3-2025-v1/2025_w1_1b661a12cf24.npz"
)
REPAIR_ARTIFACT_SHA256: Final = (
    "7eaef50c890150f6cdc329e80e4d68f08b4a8d2aac402fa5a51ba9ce4f860805"
)
REPAIR_ARTIFACT_GENERATION: Final = "1786843065841985"
REPAIR_ARTIFACT_BYTES: Final = 26_516_530
REPAIR_CANDIDATE_ROWS: Final = 248
SLATE_KEYS: Final = tuple(
    (season, week) for season in (2023, 2024, 2025) for week in range(1, 19)
)
TASK_COUNT: Final = len(SLATE_KEYS)
WORLDS_PER_BLOCK: Final = 10_000
ENTRY_BUDGET: Final = 80
TAIL_LINE: Final = 194.0
ROLE_DOSE: Final = 12
_ALLOCATION_ENV_KEYS: Final = frozenset({
    "GEN_TOTAL_BUDGET", "N_BOOM", "N_LEV", "PROSPECTIVE_SHADOW_ID",
})
_CONSTRUCTION_ENV_KEYS: Final = frozenset({
    "STACK_QB_MIN", "STACK_BRING_BACK", "FORBID_RB_DST",
    "FORBID_TWO_RB_SAME_TEAM", "MIN_LINEUP_SALARY", "MIN_GAMES",
    "PUNT_MIN", "PUNT_MAX", "PUNT_STRICT", "VALUE2_MIN", "VALUE2_MAX",
    "OWN_BARBELL", "OWN_BARBELL_LOW", "OWN_BARBELL_HIGH",
    "OWN_BARBELL_NLOW", "OWN_BARBELL_NHIGH", "MAX_PER_GAME",
    "MIN_LOWOWN", "MAX_OVERLAP",
})
_INCUMBENT_CONSTRUCTION_ENVIRONMENT: Final = {
    "STACK_QB_MIN": "2",
    "STACK_BRING_BACK": "1",
    "FORBID_RB_DST": "1",
    "FORBID_TWO_RB_SAME_TEAM": "1",
    "MIN_LINEUP_SALARY": "49000",
    "MIN_GAMES": "2",
    "PUNT_MIN": "0",
    "PUNT_MAX": "4000",
    "PUNT_STRICT": "",
    "VALUE2_MIN": "0",
    "VALUE2_MAX": "5300",
    "OWN_BARBELL": "",
    "OWN_BARBELL_LOW": "0.05",
    "OWN_BARBELL_HIGH": "0.2",
    "OWN_BARBELL_NLOW": "3",
    "OWN_BARBELL_NHIGH": "2",
    "MAX_PER_GAME": "0",
    "MIN_LOWOWN": "0",
    "MAX_OVERLAP": "7",
}

PLAYER_FIELDS: Final = (
    "panel_run_id", "season", "week", "id", "gsis_id", "name", "pos",
    "team", "opp", "game_id", "salary", "proj", "proj_tourney",
    "own_est", "consensus_div", "market_points", "model_points_pre",
    "mean_projection", "proj_p10", "proj_p50", "proj_p90", "proj_std",
)
CANDIDATE_FIELDS: Final = (
    "panel_run_id", "season", "week", "cand_ix", "tag", "player_ids",
    "score_artifact_uri", "score_artifact_sha256",
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_FORBIDDEN_FIELD_PARTS: Final = (
    "actual", "realized", "contest_rank", "payout", "winner", "roi",
    "selected_rank", "field_rank", "settled_score",
)


class CorpusR6BoomFirstAllocationV1Error(ValueError):
    """A score-blind allocation input or result failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6BoomFirstAllocationV1Error(message)


def canonical_json_bytes_v1(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusR6BoomFirstAllocationV1Error(
            "boom-first value is not canonical-JSON serializable"
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
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return grader._identity(value, label=label)
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise CorpusR6BoomFirstAllocationV1Error(str(exc)) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _finite(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{label} must be finite numeric")
    number = float(value)
    if not math.isfinite(number):
        _fail(f"{label} must be finite numeric")
    return number


def _forbidden_paths(value: object, *, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key).lower()
            child_path = f"{path}.{key}"
            if any(part in name for part in _FORBIDDEN_FIELD_PARTS):
                found.append(child_path)
            found.extend(_forbidden_paths(child, path=child_path))
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for index, child in enumerate(value):
            found.extend(_forbidden_paths(child, path=f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        if any(part in lowered for part in _FORBIDDEN_FIELD_PARTS):
            found.append(path)
    return found


def expected_slate_id_v1(source_ordinal: int) -> str:
    ordinal = _exact_int(source_ordinal, label="source ordinal")
    if ordinal >= TASK_COUNT:
        _fail("source ordinal lies outside the exact-54 lattice")
    season, week = SLATE_KEYS[ordinal]
    return f"{season}-w{week:02d}"


def candidate_source_panel_v1(season: int, week: int, block: str) -> str:
    if block not in BLOCK_ORDER:
        _fail("world block differs")
    if (season, week, block) == REPAIR_KEY:
        return REPAIR_PANEL
    return SOURCE_PANELS[BLOCK_ORDER.index(block)]


def construction_preset_v1() -> dict[str, object]:
    """Identity of every construction choice held fixed across the arms."""

    policy = ADOPTED_CLASSIC_POLICY
    construction_payload: dict[str, object] = {
        "schema_version": "boom-first-incumbent-composite-construction/v1",
        "construction_id": "pre-rewrite-atlas-incumbent-composite-v1",
        "stack": {
            "qb_stack_min": 2,
            "bring_back_min": 1,
            "forbid_rb_vs_dst": True,
            "forbid_two_rb_same_team": True,
            "qb_stack_max": None,
            "bring_back_max": None,
            "require_rb_vs_dst": False,
            "require_two_rb_same_team": False,
        },
        "min_salary": 49_000,
        "min_games": 2,
        "punt_min": 0,
        "punt_max_salary": 4_000,
        "punt_strict": False,
        "value2_min": 0,
        "value2_max": 5_300,
        "own_barbell": False,
        "own_barbell_low": 0.05,
        "own_barbell_high": 0.20,
        "own_barbell_nlow": 3,
        "own_barbell_nhigh": 2,
        "max_per_game": 0,
        "min_lowown": 0,
        # These are the effective pre-rewrite call-site semantics, not a
        # claim that the compatibility MAX_OVERLAP environment is consumed
        # uniformly.  In particular, optimize() defaults to 8 for the
        # one-shot boom/dark families, where no banned-lineup list makes the
        # solver overlap bound nonbinding; the outer natural-roster dedup is
        # still effective.  Repeated families own separate banned lists.
        "family_specific_overlap_law": {
            "leverage_repeated_solve": {
                "configured_max_overlap": 7,
                "banned_lineup_scope": "all-prior-leverage-rosters",
                "natural_roster_dedup": True,
            },
            "primary_boom_single_world_solve": {
                "configured_max_overlap": 8,
                "banned_lineup_scope": "none",
                "solver_overlap_bound_effective": False,
                "natural_roster_dedup": True,
            },
            "qb_variants_repeated_solve": {
                "configured_max_overlap": 6,
                "banned_lineup_scope": "prior-rosters-for-same-qb",
                "natural_roster_dedup": True,
            },
            "game_stack_repeated_solve": {
                "configured_max_overlap": 7,
                "banned_lineup_scope": "prior-rosters-for-same-game",
                "natural_roster_dedup": True,
            },
            "dark_game_single_solve": {
                "configured_max_overlap": 8,
                "banned_lineup_scope": "none",
                "solver_overlap_bound_effective": False,
                "natural_roster_dedup": True,
            },
            "registered_role12": {
                "solver_overlap_bound": None,
                "mode": "verbatim-natural-unique-dedup-multitag",
            },
        },
        "minimum_games_law": {
            "effective_minimum": 2,
            "source": "optimizer.lineup.MIN_GAMES-module-constant",
            "compatibility_environment_value": "2",
            "environment_value_consumed_by_pre_rewrite_optimizer": False,
        },
        "optimizer_environment_semantics": (
            "historical-helper-compatibility-input-not-universal-effective-"
            "solver-kwargs"
        ),
        "optimizer_environment": dict(_INCUMBENT_CONSTRUCTION_ENVIRONMENT),
    }
    construction_digest = canonical_sha256_v1(construction_payload)
    construction_receipt = {
        **construction_payload,
        "construction_receipt_sha256": construction_digest,
    }
    policy_environment = incumbent_policy_environment_v1(
        policy.engine_environment()
    )
    common_environment = {
        key: value for key, value in sorted(policy_environment.items())
        if key not in _ALLOCATION_ENV_KEYS
    }
    body: dict[str, object] = {
        "policy_id": policy.policy_id,
        "policy_source_panel": policy.source_panel,
        "model_registry_variant": policy.model_variant,
        "model_ensemble": policy.model_ensemble,
        "named_construction_preset": construction_receipt,
        "objective_field": "proj_tourney",
        "dk_roster_size": 9,
        "salary_floor": 49_000,
        "salary_cap": 50_000,
        "stack_rules": construction_receipt["stack"],
        "minimum_games": 2,
        "maximum_overlap": "family-specific-see-named-construction-receipt",
        "candidate_generation_entry_basis": (
            policy.multiseed_candidate_entry_basis
        ),
        "worlds_per_block": policy.multiseed_worlds_per_block,
        "seed_pairs": [list(pair) for pair in policy.multiseed_seed_pairs],
        "role12_mechanism": (
            "verbatim-registered-arm-invariant-natural-dedup-multitag-v1"
        ),
        "auxiliary_requested_per_seed": {
            "qb_variants_max": 32,
            "game_stacks_max": 12,
            "dark_games_max": 10,
        },
        "selector": "CBWU",
        "entry_budget": ENTRY_BUDGET,
        "tail_line": TAIL_LINE,
        "common_environment": common_environment,
        "allocation_environment_keys_excluded": sorted(_ALLOCATION_ENV_KEYS),
        "uses_realized_outcomes": False,
    }
    return _with_hash(body, field="construction_preset_sha256")


def incumbent_policy_environment_v1(
    environment: Mapping[str, str],
) -> dict[str, str]:
    """Normalize either optimizer generation to the pre-rewrite incumbent.

    The matched pair is intentionally independent of the concurrent
    legality-only construction rewrite.  New and old policy modules can both
    supply the non-construction policy surface; every construction coordinate
    is then replaced with this experiment's self-contained incumbent law.
    """

    retained = {str(key): str(value) for key, value in environment.items()}
    for key in _CONSTRUCTION_ENV_KEYS:
        retained.pop(key, None)
    retained.update(_INCUMBENT_CONSTRUCTION_ENVIRONMENT)
    return retained


def _normalized_player_rows(
    raw_rows: Sequence[Mapping[str, object]], *, panel: str,
    season: int, week: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for ordinal, raw in enumerate(raw_rows):
        row = _mapping(raw, label=f"player row[{ordinal}]")
        if set(row) != set(PLAYER_FIELDS):
            _fail("generation player fields differ")
        if (
            row.get("panel_run_id") != panel
            or row.get("season") != season
            or row.get("week") != week
        ):
            _fail("generation player coordinate differs")
        player_id = str(row.get("id") or "").strip()
        if not player_id:
            _fail("generation player ID is empty")
        pos = str(row.get("pos") or "").upper()
        if pos not in {"QB", "RB", "WR", "TE", "DST"}:
            _fail("generation player position differs")
        _finite(row.get("salary"), label="player salary")
        _finite(row.get("proj"), label="player projection")
        _finite(row.get("proj_tourney"), label="player tournament objective")
        normalized = {field: row[field] for field in PLAYER_FIELDS}
        normalized["id"] = player_id
        normalized["pos"] = pos
        rows.append(normalized)
    rows.sort(key=lambda row: str(row["id"]))
    ids = [str(row["id"]) for row in rows]
    if not rows or len(ids) != len(set(ids)):
        _fail("generation player IDs are empty or repeat")
    return rows


def _roster(value: object, *, label: str) -> list[str]:
    values = [str(item).strip() for item in _sequence(value, label=label)]
    if len(values) != 9 or len(set(values)) != 9 or any(not item for item in values):
        _fail(f"{label} must contain nine unique player IDs")
    return sorted(values)


def _normalized_candidate_rows(
    raw_rows: Sequence[Mapping[str, object]], *, panel: str,
    season: int, week: int, block: str, artifact: Mapping[str, object],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    artifact_sha = _digest(artifact.get("sha256"), label="artifact SHA-256")
    for ordinal, raw in enumerate(raw_rows):
        row = _mapping(raw, label=f"candidate row[{ordinal}]")
        if set(row) != set(CANDIDATE_FIELDS):
            _fail("generation candidate fields differ")
        exact_artifact_binding = (
            row.get("score_artifact_uri") == artifact.get("uri")
            and row.get("score_artifact_sha256") == artifact_sha
        )
        exact_repair_alias = (
            (season, week, block) == REPAIR_KEY
            and panel == REPAIR_PANEL
            and artifact.get("block") == REPAIR_KEY[2]
            and artifact.get("panel_run_id") == SOURCE_PANELS[3]
            and artifact.get("uri") == REPAIR_WORLD_ARTIFACT_URI
            and artifact.get("generation") == REPAIR_ARTIFACT_GENERATION
            and artifact.get("sha256") == REPAIR_ARTIFACT_SHA256
            and artifact.get("bytes") == REPAIR_ARTIFACT_BYTES
            and artifact.get("candidate_rows") == REPAIR_CANDIDATE_ROWS
            and row.get("score_artifact_uri")
            == REPAIR_CANDIDATE_ARTIFACT_URI
            and row.get("score_artifact_sha256") == REPAIR_ARTIFACT_SHA256
        )
        artifact_binding_matches = (
            exact_repair_alias
            if (season, week, block) == REPAIR_KEY or panel == REPAIR_PANEL
            else exact_artifact_binding
        )
        if (
            row.get("panel_run_id") != panel
            or row.get("season") != season
            or row.get("week") != week
            or row.get("cand_ix") != ordinal
            or not artifact_binding_matches
        ):
            _fail("generation candidate coordinate/artifact differs")
        tag = str(row.get("tag") or "").strip()
        if not tag:
            _fail("generation candidate tag is empty")
        rows.append({
            **row,
            "tag": tag,
            "player_ids": _roster(
                row.get("player_ids"), label=f"candidate row[{ordinal}] roster"
            ),
        })
    if len(rows) != artifact.get("candidate_rows"):
        _fail("generation candidate count differs from world artifact")
    return rows


def build_generation_snapshot_v1(
    *, source_ordinal: int, later_source_identity: object,
    later_source_freeze_sha256: str, later_slate: Mapping[str, object],
    player_rows_by_block: Mapping[str, Sequence[Mapping[str, object]]],
    candidate_rows_by_block: Mapping[str, Sequence[Mapping[str, object]]],
    query_receipts: Mapping[str, object],
) -> dict[str, object]:
    """Freeze all score-blind rows needed to regenerate one historical slate."""

    ordinal = _exact_int(source_ordinal, label="source ordinal")
    slate_id = expected_slate_id_v1(ordinal)
    season, week = SLATE_KEYS[ordinal]
    source_identity = _identity(later_source_identity, label="later source")
    freeze_sha = _digest(
        later_source_freeze_sha256, label="later-source freeze SHA-256"
    )
    slate = _mapping(later_slate, label="later-source slate")
    if (
        slate.get("season") != season
        or slate.get("week") != week
        or slate.get("slate_id") != slate_id
    ):
        _fail("later-source slate coordinate differs")
    artifacts = _sequence(
        slate.get("artifact_receipts"), label="later-source artifacts"
    )
    if len(artifacts) != len(BLOCK_ORDER):
        _fail("later-source artifact lattice differs")
    if set(player_rows_by_block) != set(BLOCK_ORDER) or set(
        candidate_rows_by_block
    ) != set(BLOCK_ORDER):
        _fail("generation snapshot block lattice differs")
    receipts = _mapping(query_receipts, label="generation query receipts")
    if _forbidden_paths(receipts):
        _fail("generation query receipts contain outcome fields")

    seed_rows: list[dict[str, object]] = []
    for block, raw_artifact in zip(BLOCK_ORDER, artifacts, strict=True):
        artifact = _mapping(raw_artifact, label=f"{block} artifact")
        if (
            artifact.get("block") != block
            or artifact.get("season") != season
            or artifact.get("week") != week
        ):
            _fail("generation artifact coordinate differs")
        _identity(
            {key: artifact.get(key) for key in ("uri", "generation", "sha256", "bytes")},
            label=f"{block} artifact",
        )
        _exact_int(
            artifact.get("candidate_rows"),
            label=f"{block} artifact candidate rows", minimum=1,
        )
        panel = candidate_source_panel_v1(season, week, block)
        players = _normalized_player_rows(
            player_rows_by_block[block], panel=panel, season=season, week=week
        )
        candidates = _normalized_candidate_rows(
            candidate_rows_by_block[block], panel=panel, season=season,
            week=week, block=block, artifact=artifact,
        )
        catalog_ids = {str(row["id"]) for row in players}
        if any(not set(row["player_ids"]) <= catalog_ids for row in candidates):
            _fail("generation candidate names a player absent from its snapshot")
        seed_rows.append({
            "block": block,
            "world_source_panel_id": SOURCE_PANELS[BLOCK_ORDER.index(block)],
            "candidate_source_panel_id": panel,
            "repair_substitution": panel == REPAIR_PANEL,
            "artifact_receipt": artifact,
            "player_rows": players,
            "player_rows_sha256": canonical_sha256_v1(players),
            "candidate_rows": candidates,
            "candidate_rows_sha256": canonical_sha256_v1(candidates),
        })

    body: dict[str, object] = {
        "schema_version": GENERATION_SNAPSHOT_SCHEMA,
        "source_ordinal": ordinal,
        "season": season,
        "week": week,
        "slate_id": slate_id,
        "later_source_identity": source_identity,
        "later_source_freeze_sha256": freeze_sha,
        "query_receipts": receipts,
        "seeds": seed_rows,
        "seed_order": list(BLOCK_ORDER),
        "objective_field": "proj_tourney",
        "objective_frozen_before_generation": True,
        "target_slate_outcome_columns": [],
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
    }
    return _with_hash(body, field="generation_snapshot_sha256")


def validate_generation_snapshot_v1(value: object) -> dict[str, object]:
    snapshot = _mapping(value, label="generation snapshot")
    digest = snapshot.get("generation_snapshot_sha256")
    body = {
        key: child for key, child in snapshot.items()
        if key != "generation_snapshot_sha256"
    }
    if _digest(digest, label="generation snapshot SHA-256") != canonical_sha256_v1(body):
        _fail("generation snapshot hash differs")
    expected = {
        "schema_version", "source_ordinal", "season", "week", "slate_id",
        "later_source_identity", "later_source_freeze_sha256", "query_receipts",
        "seeds", "seed_order", "objective_field",
        "objective_frozen_before_generation", "target_slate_outcome_columns",
        "uses_realized_outcomes", "production_change_licensed",
        "generation_snapshot_sha256",
    }
    ordinal = snapshot.get("source_ordinal")
    if set(snapshot) != expected or snapshot.get("schema_version") != GENERATION_SNAPSHOT_SCHEMA:
        _fail("generation snapshot fields/schema differ")
    slate_id = expected_slate_id_v1(ordinal)
    season, week = SLATE_KEYS[int(ordinal)]
    if (
        snapshot.get("season") != season
        or snapshot.get("week") != week
        or snapshot.get("slate_id") != slate_id
        or snapshot.get("seed_order") != list(BLOCK_ORDER)
        or snapshot.get("objective_field") != "proj_tourney"
        or snapshot.get("objective_frozen_before_generation") is not True
        or snapshot.get("target_slate_outcome_columns") != []
        or snapshot.get("uses_realized_outcomes") is not False
        or snapshot.get("production_change_licensed") is not False
    ):
        _fail("generation snapshot fixed law differs")
    _identity(snapshot.get("later_source_identity"), label="later source")
    _digest(
        snapshot.get("later_source_freeze_sha256"),
        label="generation snapshot later-source internal hash",
    )
    seeds = _sequence(snapshot.get("seeds"), label="generation seeds")
    if len(seeds) != len(BLOCK_ORDER):
        _fail("generation snapshot seed count differs")
    for block, raw in zip(BLOCK_ORDER, seeds, strict=True):
        seed = _mapping(raw, label=f"generation {block}")
        if set(seed) != {
            "block", "world_source_panel_id", "candidate_source_panel_id",
            "repair_substitution", "artifact_receipt", "player_rows",
            "player_rows_sha256", "candidate_rows", "candidate_rows_sha256",
        } or seed.get("block") != block:
            _fail("generation seed fields/order differ")
        panel = candidate_source_panel_v1(season, week, block)
        if (
            seed.get("world_source_panel_id") != SOURCE_PANELS[BLOCK_ORDER.index(block)]
            or seed.get("candidate_source_panel_id") != panel
            or seed.get("repair_substitution") is not (panel == REPAIR_PANEL)
        ):
            _fail("generation seed source substitution differs")
        artifact = _mapping(seed.get("artifact_receipt"), label=f"{block} artifact")
        players = _normalized_player_rows(
            _sequence(seed.get("player_rows"), label=f"{block} players"),
            panel=panel, season=season, week=week,
        )
        candidates = _normalized_candidate_rows(
            _sequence(seed.get("candidate_rows"), label=f"{block} candidates"),
            panel=panel, season=season, week=week, block=block,
            artifact=artifact,
        )
        if (
            canonical_sha256_v1(players) != seed.get("player_rows_sha256")
            or canonical_sha256_v1(candidates) != seed.get("candidate_rows_sha256")
        ):
            _fail("generation seed row hash differs")
    return snapshot


def arm_environments_v1(
    base_environment: Mapping[str, str], *, code_sha: str,
) -> dict[str, dict[str, str]]:
    """Return source-bound policy environments with the exact arm delta."""

    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None:
        _fail("code SHA differs")
    # Reuse the paired core's production-policy registration check.
    paired._validated_arm_environments(code_sha)
    base = {str(key): str(value) for key, value in base_environment.items()}
    base["CODE_SHA"] = code_sha
    control = incumbent_policy_environment_v1(
        ADOPTED_CLASSIC_POLICY.boom_first_control_environment(base)
    )
    treatment = incumbent_policy_environment_v1(
        ADOPTED_CLASSIC_POLICY.boom_first_shadow_environment(base)
    )
    changed = {
        key for key in set(control) | set(treatment)
        if control.get(key) != treatment.get(key)
    }
    if changed != {"GEN_TOTAL_BUDGET", "N_BOOM", "N_LEV", "PROSPECTIVE_SHADOW_ID"}:
        _fail("boom-first arm environment delta differs")
    return {"control": control, "treatment": treatment}


def inject_frozen_role12_v1(
    batch: CandidateBatch, *, native_rows: pd.DataFrame,
    slate: pd.DataFrame, artifact_totals: np.ndarray,
) -> CandidateBatch:
    """Register the proven role12 at its boundary with natural unique dedup.

    A role roster that the core already generated is not an experiment
    failure.  It remains one unique candidate, gains the ``epi`` family tag,
    and is checked against both the frozen artifact total and the reconstructed
    player worlds.  This is the same unique-pool meaning used by the native
    generator: requested family membership is retained without duplicating a
    roster in the candidate matrix.
    """

    _validate_candidate_batch(batch)
    ordered = native_rows.sort_values("cand_ix", kind="stable")
    role_rows = ordered[ordered["tag"].astype(str).eq("epi")]
    if len(role_rows) != ROLE_DOSE:
        _fail("frozen role source is not exact role12")
    allocation = _mapping(
        batch.metadata.get("generation_allocation"), label="generation allocation"
    )
    if allocation.get("role_or_epistemic_requested") != 0:
        _fail("frozen role injection requires a zero runtime role dose")
    core_count = int(allocation.get("leverage_unique", -1)) + int(
        allocation.get("boom_unique_added", -1)
    )
    if not 0 <= core_count <= len(batch.candidates):
        _fail("generated core boundary differs")
    record_by_id = {str(row["id"]): row for row in slate.to_dict("records")}
    generated_index = {
        frozenset(str(value) for value in lineup.ids): index
        for index, lineup in enumerate(batch.candidates)
    }
    totals = np.asarray(artifact_totals)
    if totals.ndim != 2 or totals.shape[1] != batch.candidate_totals.shape[1]:
        _fail("frozen role artifact totals differ")
    injected: list[Lineup] = []
    injected_totals: list[np.ndarray] = []
    requested_rosters: list[list[str]] = []
    requested_totals: list[np.ndarray] = []
    collision_rosters: list[list[str]] = []
    tags = {key: tuple(value) for key, value in batch.all_tags.items()}
    for _, row in role_rows.iterrows():
        roster = _roster(row["player_ids"], label="frozen role roster")
        identity = frozenset(roster)
        missing = [player_id for player_id in roster if player_id not in record_by_id]
        if missing:
            _fail("frozen role roster names an absent player")
        index = int(row["cand_ix"])
        if not 0 <= index < totals.shape[0]:
            _fail("frozen role candidate index lies outside artifact")
        lineup = Lineup([record_by_id[player_id] for player_id in roster], tag="epi")
        recomputed = np.asarray(batch.row_draws)[[
            list(batch.player_ids).index(player_id) for player_id in roster
        ]].sum(axis=0)
        if not np.allclose(recomputed, totals[index], atol=1e-4, rtol=0.0):
            _fail("frozen role candidate totals differ from player worlds")
        requested_rosters.append(roster)
        requested_totals.append(np.asarray(totals[index]))
        if identity in generated_index:
            generated_total = np.asarray(
                batch.candidate_totals[generated_index[identity]]
            )
            if not np.allclose(
                generated_total, totals[index], atol=1e-4, rtol=0.0
            ):
                _fail("frozen role collision has different candidate totals")
            collision_rosters.append(roster)
            tags[identity] = tuple(dict.fromkeys((*tags.get(identity, ()), "epi")))
            continue
        injected.append(lineup)
        injected_totals.append(np.asarray(totals[index]))
        tags[identity] = tuple(dict.fromkeys((*tags.get(identity, ()), "epi")))

    if len({tuple(roster) for roster in requested_rosters}) != ROLE_DOSE:
        _fail("frozen role source repeats a roster")

    candidates = (
        tuple(batch.candidates[:core_count])
        + tuple(injected)
        + tuple(batch.candidates[core_count:])
    )
    total_parts = [np.asarray(batch.candidate_totals[:core_count])]
    if injected_totals:
        total_parts.append(np.stack(injected_totals))
    total_parts.append(np.asarray(batch.candidate_totals[core_count:]))
    candidate_totals = np.concatenate(total_parts, axis=0)
    amended_allocation = dict(allocation)
    amended_allocation.update({
        "role_or_epistemic_requested": ROLE_DOSE,
        "total_requested_with_replacement_families": int(
            amended_allocation["core_requested"]
        ) + ROLE_DOSE,
        "unique_candidates_after_all_families": len(candidates),
    })
    role_totals = np.stack(requested_totals)
    injected_rosters = [
        sorted(str(value) for value in lineup.ids) for lineup in injected
    ]
    result = replace(batch, candidates=candidates, candidate_totals=candidate_totals,
                     all_tags=tags, metadata={
        **dict(batch.metadata),
        "generation_allocation": amended_allocation,
        "role_injection": {
            "mode": (
                "verbatim-registered-arm-invariant-natural-dedup-multitag-v1"
            ),
            "requested_count": ROLE_DOSE,
            "represented_count": ROLE_DOSE,
            "unique_added_count": len(injected),
            "already_present_count": len(collision_rosters),
            "requested_candidate_rosters_sha256": canonical_sha256_v1(
                requested_rosters
            ),
            "requested_candidate_totals_sha256": sha256(
                np.ascontiguousarray(role_totals).tobytes()
            ).hexdigest(),
            "unique_added_candidate_rosters_sha256": canonical_sha256_v1(
                injected_rosters
            ),
            "collision_candidate_rosters_sha256": canonical_sha256_v1(
                collision_rosters
            ),
            "natural_unique_deduplication": True,
            "collision_family_multitagged": True,
        },
    })
    _validate_candidate_batch(result)
    return result


def _batch_receipt(batch: CandidateBatch, *, arm: str, block: str) -> dict[str, object]:
    _validate_candidate_batch(batch)
    allocation = _mapping(
        batch.metadata.get("generation_allocation"), label=f"{arm}/{block} allocation"
    )
    expected_lev, expected_boom = (160, 40) if arm == "control" else (40, 160)
    expected_allocation_fields = {
        "leverage_requested", "leverage_unique", "leverage_solve_attempts",
        "leverage_solver_errors", "leverage_infeasible", "leverage_successful",
        "boom_requested", "boom_attempted", "boom_successful",
        "boom_solver_errors", "boom_infeasible", "boom_duplicates",
        "boom_failures", "boom_unique_added", "boom_unique_fill",
        "ce_requested", "role_or_epistemic_requested", "gumbel_requested",
        "core_requested", "total_requested_with_replacement_families",
        "unique_candidates_after_all_families",
    }
    if (
        set(allocation) != expected_allocation_fields
        or allocation.get("leverage_requested") != expected_lev
        or allocation.get("leverage_solve_attempts") != expected_lev
        or allocation.get("boom_requested") != expected_boom
        or allocation.get("boom_attempted") != expected_boom
        or allocation.get("boom_unique_fill") is not False
        or allocation.get("core_requested") != 200
        or allocation.get("role_or_epistemic_requested") != ROLE_DOSE
        or allocation.get("total_requested_with_replacement_families") != 212
    ):
        _fail(f"{arm}/{block} equal-requested-work receipt differs")
    for field in (
        "leverage_unique", "leverage_solver_errors", "leverage_infeasible",
        "leverage_successful", "boom_successful", "boom_solver_errors",
        "boom_infeasible", "boom_duplicates", "boom_failures",
        "boom_unique_added", "unique_candidates_after_all_families",
    ):
        _exact_int(allocation.get(field), label=f"{arm}/{block} {field}")
    if any(allocation[field] != 0 for field in (
        "leverage_solver_errors", "leverage_infeasible",
        "boom_solver_errors", "boom_infeasible",
    )):
        _fail(f"{arm}/{block} generation was not failure-free")
    if allocation["leverage_successful"] + allocation[
        "leverage_solver_errors"
    ] + allocation["leverage_infeasible"] != expected_lev:
        _fail(f"{arm}/{block} leverage attempt accounting differs")
    if allocation["leverage_unique"] > allocation["leverage_successful"]:
        _fail(f"{arm}/{block} leverage unique accounting differs")
    if allocation["boom_successful"] + allocation["boom_solver_errors"] + allocation[
        "boom_infeasible"
    ] != expected_boom:
        _fail(f"{arm}/{block} boom attempt accounting differs")
    if allocation["boom_unique_added"] + allocation["boom_duplicates"] != allocation[
        "boom_successful"
    ]:
        _fail(f"{arm}/{block} boom dedup accounting differs")
    if allocation["boom_failures"] != (
        allocation["boom_solver_errors"] + allocation["boom_infeasible"]
    ):
        _fail(f"{arm}/{block} boom failure accounting differs")
    if allocation["unique_candidates_after_all_families"] != len(batch.candidates):
        _fail(f"{arm}/{block} final unique-candidate count differs")
    role = _mapping(batch.metadata.get("role_injection"), label="role injection")
    expected_role_fields = {
        "mode", "requested_count", "represented_count", "unique_added_count",
        "already_present_count", "requested_candidate_rosters_sha256",
        "requested_candidate_totals_sha256",
        "unique_added_candidate_rosters_sha256",
        "collision_candidate_rosters_sha256", "natural_unique_deduplication",
        "collision_family_multitagged",
    }
    if (
        set(role) != expected_role_fields
        or role.get("mode")
        != "verbatim-registered-arm-invariant-natural-dedup-multitag-v1"
        or role.get("requested_count") != ROLE_DOSE
        or role.get("represented_count") != ROLE_DOSE
        or type(role.get("unique_added_count")) is not int
        or type(role.get("already_present_count")) is not int
        or role["unique_added_count"] + role["already_present_count"] != ROLE_DOSE
        or role.get("natural_unique_deduplication") is not True
        or role.get("collision_family_multitagged") is not True
    ):
        _fail(f"{arm}/{block} role injection differs")
    for field in (
        "requested_candidate_rosters_sha256",
        "requested_candidate_totals_sha256",
        "unique_added_candidate_rosters_sha256",
        "collision_candidate_rosters_sha256",
    ):
        _digest(role.get(field), label=f"{arm}/{block} {field}")
    rosters = [sorted(str(value) for value in lineup.ids) for lineup in batch.candidates]
    tag_counts: dict[str, int] = {}
    family_membership_counts: dict[str, int] = {}
    for lineup in batch.candidates:
        tag = str(lineup.tag or "lev")
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
        memberships = tuple(batch.all_tags.get(lineup.ids, ()))
        if not memberships:
            _fail(f"{arm}/{block} candidate lacks family membership")
        for membership in memberships:
            key = str(membership)
            family_membership_counts[key] = family_membership_counts.get(key, 0) + 1
    if family_membership_counts.get("epi") != ROLE_DOSE:
        _fail(f"{arm}/{block} role family is not represented exactly 12 times")
    timing = _mapping(
        batch.metadata.get("generation_timing_seconds"), label="generation timing"
    )
    expected_timing_fields = {
        "leverage", "primary_boom", "all_generation_through_candidate_matrix",
    }
    if set(timing) != expected_timing_fields:
        _fail(f"{arm}/{block} generation timing fields differ")
    retained_timing = {
        field: _finite(timing[field], label=f"{arm}/{block} {field} timing")
        for field in sorted(expected_timing_fields)
    }
    if (
        any(value < 0.0 for value in retained_timing.values())
        or retained_timing["all_generation_through_candidate_matrix"] + 1e-9
        < retained_timing["leverage"] + retained_timing["primary_boom"]
    ):
        _fail(f"{arm}/{block} generation timing order differs")
    construction_receipt = _mapping(
        batch.metadata.get("construction_preset_receipt"),
        label=f"{arm}/{block} construction preset receipt",
    )
    if construction_receipt != construction_preset_v1()["named_construction_preset"]:
        _fail(f"{arm}/{block} actual construction preset receipt differs")
    reproduction: dict[str, object] | None = None
    if arm == "control":
        reproduction = _mapping(
            batch.metadata.get("control_reproduction"),
            label=f"{arm}/{block} control reproduction",
        )
        if (
            reproduction.get("mode") != "bq-identities-and-artifact-totals"
            or reproduction.get("generated_candidates") != len(batch.candidates)
            or reproduction.get("artifact_candidates") != len(batch.candidates)
            or reproduction.get("registered_candidates") != len(batch.candidates)
            or _finite(
                reproduction.get("max_total_delta"),
                label=f"{arm}/{block} control reproduction delta",
            ) > 1e-6
        ):
            _fail(f"{arm}/{block} control reproduction gate differs")
    return {
        "block": block,
        "candidate_count": len(rosters),
        "candidate_rosters_sha256": canonical_sha256_v1(rosters),
        "tag_counts": dict(sorted(tag_counts.items())),
        "family_membership_counts": dict(sorted(family_membership_counts.items())),
        "generation_allocation": allocation,
        "generation_timing_seconds": retained_timing,
        "construction_preset_receipt": construction_receipt,
        "role_injection": role,
        "control_reproduction": reproduction,
        "failure_free": (
            allocation["leverage_solver_errors"] == 0
            and allocation["leverage_infeasible"] == 0
            and allocation["boom_solver_errors"] == 0
            and allocation["boom_infeasible"] == 0
        ),
    }


def _invocation_totals(
    receipts: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    fields = (
        "leverage_requested", "leverage_solve_attempts", "leverage_successful",
        "leverage_solver_errors", "leverage_infeasible", "leverage_unique",
        "boom_requested", "boom_attempted", "boom_successful",
        "boom_solver_errors", "boom_infeasible", "boom_duplicates",
        "boom_failures", "boom_unique_added",
    )
    result = {
        field: sum(
            int(_mapping(row["generation_allocation"], label="allocation")[field])
            for row in receipts
        )
        for field in fields
    }
    result.update({
        "native_book_count": len(receipts),
        "returned_unique_candidates_across_native_books": sum(
            int(row["candidate_count"]) for row in receipts
        ),
        "failure_free_native_book_count": sum(
            int(row["failure_free"] is True) for row in receipts
        ),
    })
    return result


def validate_runtime_identity_v1(
    value: object, *, expected_source_ordinal: int | None = None,
) -> dict[str, object]:
    """Validate either a no-publish smoke or provider task authority."""

    runtime = _mapping(value, label="boom-first runtime authority")
    expected_fields = {
        "schema_version", "execution_mode", "source_ordinal", "task_count",
        "task_attempt", "execution_id", "job_name", "reused_job_uid",
        "service_account", "project_id", "region", "manifest_identity",
        "manifest_sha256", "terminal_build_receipt_identity", "code_commit",
        "image_digest", "immutable_image_uri", "task0_smoke_sha256",
        "observed_command", "authority_source",
        "generation_and_selection_wall_seconds", "runtime_authority_sha256",
    }
    body = {
        key: child for key, child in runtime.items()
        if key != "runtime_authority_sha256"
    }
    mode = runtime.get("execution_mode")
    ordinal = runtime.get("source_ordinal")
    wall = _finite(
        runtime.get("generation_and_selection_wall_seconds"),
        label="runtime generation/selection wall time",
    )
    command = _sequence(runtime.get("observed_command"), label="runtime command")
    if (
        set(runtime) != expected_fields
        or runtime.get("schema_version") != RUNTIME_AUTHORITY_SCHEMA
        or runtime.get("runtime_authority_sha256") != canonical_sha256_v1(body)
        or mode not in {"preflight-smoke", "manifest-smoke", "provider-task"}
        or type(ordinal) is not int
        or not 0 <= int(ordinal) < TASK_COUNT
        or (
            expected_source_ordinal is not None
            and ordinal != expected_source_ordinal
        )
        or runtime.get("task_count") != TASK_COUNT
        or runtime.get("task_attempt") != 0
        or _COMMIT.fullmatch(str(runtime.get("code_commit"))) is None
        or any(
            type(runtime.get(field)) is not str or not runtime[field]
            for field in ("project_id", "region")
        )
        or wall < 0.0
        or not command
        or any(type(item) is not str or not item for item in command)
    ):
        _fail("boom-first runtime authority fixed fields differ")
    if mode == "preflight-smoke":
        if (
            runtime.get("execution_id") != "preflight-smoke"
            or any(runtime.get(field) is not None for field in (
                "job_name", "reused_job_uid", "service_account",
                "manifest_identity", "manifest_sha256",
                "terminal_build_receipt_identity", "image_digest",
                "immutable_image_uri", "task0_smoke_sha256",
            ))
            or command != ["preflight-smoke"]
            or runtime.get("authority_source")
            != "score-blind-real-artifact-preflight-no-publication"
        ):
            _fail("boom-first preflight-smoke runtime differs")
    else:
        _identity(runtime.get("manifest_identity"), label="runtime manifest")
        _identity(
            runtime.get("terminal_build_receipt_identity"),
            label="runtime terminal build receipt",
        )
        _digest(runtime.get("manifest_sha256"), label="runtime manifest hash")
        image_digest = runtime.get("image_digest")
        image_uri = runtime.get("immutable_image_uri")
        if (
            re.fullmatch(r"sha256:[0-9a-f]{64}", str(image_digest)) is None
            or type(image_uri) is not str
            or not image_uri.endswith(f"@{image_digest}")
            or any(
                type(runtime.get(field)) is not str or not runtime[field]
                for field in (
                    "job_name", "reused_job_uid", "service_account",
                    "project_id", "region",
                )
            )
        ):
            _fail("boom-first manifest-bound runtime differs")
        if mode == "manifest-smoke":
            if (
                runtime.get("execution_id") != "manifest-smoke"
                or runtime.get("task0_smoke_sha256") is not None
                or command != ["manifest-smoke"]
                or runtime.get("authority_source")
                != "manifest-bound-real-artifact-smoke-no-publication"
            ):
                _fail("boom-first manifest-smoke runtime differs")
        else:
            _digest(
                runtime.get("task0_smoke_sha256"),
                label="runtime task-0 smoke hash",
            )
            if (
                type(runtime.get("execution_id")) is not str
                or not runtime["execution_id"]
                or runtime.get("authority_source")
                != "reserved-cloud-run-metadata-and-exact-process-command"
            ):
                _fail("boom-first provider-task runtime differs")
    return runtime


def _validate_native_book_receipt_v1(
    value: object, *, arm: str, block: str,
) -> dict[str, object]:
    receipt = _mapping(value, label=f"task {arm}/{block} native receipt")
    expected_fields = {
        "block", "candidate_count", "candidate_rosters_sha256", "tag_counts",
        "family_membership_counts", "generation_allocation",
        "generation_timing_seconds", "construction_preset_receipt",
        "role_injection", "control_reproduction", "failure_free",
    }
    candidate_count = _exact_int(
        receipt.get("candidate_count"),
        label=f"task {arm}/{block} candidate count", minimum=1,
    )
    if (
        set(receipt) != expected_fields
        or receipt.get("block") != block
        or receipt.get("failure_free") is not True
    ):
        _fail(f"task {arm}/{block} native receipt fields differ")
    _digest(
        receipt.get("candidate_rosters_sha256"),
        label=f"task {arm}/{block} roster hash",
    )
    tag_counts = _mapping(
        receipt.get("tag_counts"), label=f"task {arm}/{block} tag counts"
    )
    family_counts = _mapping(
        receipt.get("family_membership_counts"),
        label=f"task {arm}/{block} family counts",
    )
    if (
        any(type(value) is not int or value < 0 for value in tag_counts.values())
        or sum(tag_counts.values()) != candidate_count
        or any(type(value) is not int or value < 0 for value in family_counts.values())
        or family_counts.get("epi") != ROLE_DOSE
    ):
        _fail(f"task {arm}/{block} family count receipt differs")
    allocation = _mapping(
        receipt.get("generation_allocation"),
        label=f"task {arm}/{block} allocation",
    )
    expected_lev, expected_boom = (160, 40) if arm == "control" else (40, 160)
    integer_fields = {
        "leverage_requested", "leverage_unique", "leverage_solve_attempts",
        "leverage_solver_errors", "leverage_infeasible", "leverage_successful",
        "boom_requested", "boom_attempted", "boom_successful",
        "boom_solver_errors", "boom_infeasible", "boom_duplicates",
        "boom_failures", "boom_unique_added", "ce_requested",
        "role_or_epistemic_requested", "gumbel_requested", "core_requested",
        "total_requested_with_replacement_families",
        "unique_candidates_after_all_families",
    }
    if set(allocation) != integer_fields | {"boom_unique_fill"}:
        _fail(f"task {arm}/{block} allocation fields differ")
    for field in integer_fields:
        _exact_int(allocation.get(field), label=f"task {arm}/{block} {field}")
    if (
        allocation["leverage_requested"] != expected_lev
        or allocation["leverage_solve_attempts"] != expected_lev
        or allocation["leverage_successful"] + allocation["leverage_solver_errors"]
        + allocation["leverage_infeasible"] != expected_lev
        or allocation["leverage_unique"] > allocation["leverage_successful"]
        or allocation["boom_requested"] != expected_boom
        or allocation["boom_attempted"] != expected_boom
        or allocation["boom_successful"] + allocation["boom_solver_errors"]
        + allocation["boom_infeasible"] != expected_boom
        or allocation["boom_unique_added"] + allocation["boom_duplicates"]
        != allocation["boom_successful"]
        or allocation["boom_failures"]
        != allocation["boom_solver_errors"] + allocation["boom_infeasible"]
        or allocation["boom_unique_fill"] is not False
        or allocation["core_requested"] != 200
        or allocation["role_or_epistemic_requested"] != ROLE_DOSE
        or allocation["total_requested_with_replacement_families"] != 212
        or allocation["unique_candidates_after_all_families"] != candidate_count
        or any(allocation[field] != 0 for field in (
            "leverage_solver_errors", "leverage_infeasible",
            "boom_solver_errors", "boom_infeasible",
        ))
    ):
        _fail(f"task {arm}/{block} allocation accounting differs")
    timing = _mapping(
        receipt.get("generation_timing_seconds"),
        label=f"task {arm}/{block} timing",
    )
    if set(timing) != {
        "leverage", "primary_boom", "all_generation_through_candidate_matrix",
    }:
        _fail(f"task {arm}/{block} timing fields differ")
    retained_timing = {
        field: _finite(value, label=f"task {arm}/{block} {field} timing")
        for field, value in timing.items()
    }
    if (
        any(value < 0 for value in retained_timing.values())
        or retained_timing["all_generation_through_candidate_matrix"] + 1e-9
        < retained_timing["leverage"] + retained_timing["primary_boom"]
    ):
        _fail(f"task {arm}/{block} timing order differs")
    if receipt.get("construction_preset_receipt") != construction_preset_v1()[
        "named_construction_preset"
    ]:
        _fail(f"task {arm}/{block} construction receipt differs")
    role = _mapping(
        receipt.get("role_injection"), label=f"task {arm}/{block} role receipt"
    )
    if set(role) != {
        "mode", "requested_count", "represented_count", "unique_added_count",
        "already_present_count", "requested_candidate_rosters_sha256",
        "requested_candidate_totals_sha256",
        "unique_added_candidate_rosters_sha256",
        "collision_candidate_rosters_sha256", "natural_unique_deduplication",
        "collision_family_multitagged",
    }:
        _fail(f"task {arm}/{block} role receipt fields differ")
    if (
        role.get("mode")
        != "verbatim-registered-arm-invariant-natural-dedup-multitag-v1"
        or role.get("requested_count") != ROLE_DOSE
        or role.get("represented_count") != ROLE_DOSE
        or type(role.get("unique_added_count")) is not int
        or type(role.get("already_present_count")) is not int
        or role["unique_added_count"] + role["already_present_count"] != ROLE_DOSE
        or role.get("natural_unique_deduplication") is not True
        or role.get("collision_family_multitagged") is not True
    ):
        _fail(f"task {arm}/{block} role receipt differs")
    for field in (
        "requested_candidate_rosters_sha256",
        "requested_candidate_totals_sha256",
        "unique_added_candidate_rosters_sha256",
        "collision_candidate_rosters_sha256",
    ):
        _digest(role.get(field), label=f"task {arm}/{block} {field}")
    reproduction = receipt.get("control_reproduction")
    if arm == "control":
        reproduction = _mapping(
            reproduction, label=f"task {arm}/{block} reproduction"
        )
        if set(reproduction) != {
            "mode", "generated_candidates", "artifact_candidates",
            "registered_candidates", "max_total_delta",
        } or (
            reproduction.get("mode") != "bq-identities-and-artifact-totals"
            or any(reproduction.get(field) != candidate_count for field in (
                "generated_candidates", "artifact_candidates",
                "registered_candidates",
            ))
            or _finite(
                reproduction.get("max_total_delta"),
                label=f"task {arm}/{block} reproduction delta",
            ) > 1e-6
        ):
            _fail(f"task {arm}/{block} control reproduction differs")
    elif reproduction is not None:
        _fail(f"task {arm}/{block} treatment has a control reproduction")
    return receipt


def _lineup_row(lineup: Lineup) -> dict[str, object]:
    roster = sorted(str(value) for value in lineup.ids)
    digest = canonical_sha256_v1(roster)
    return {
        "lineup_id": f"roster-{digest}",
        "roster_player_ids": roster,
        "roster_sha256": digest,
    }


def build_task_result_v1(
    *, snapshot: Mapping[str, object],
    books_by_arm: Mapping[str, Mapping[str, CandidateBatch]],
    runtime_identity: Mapping[str, object],
) -> dict[str, object]:
    """Run same-world CBWU exact-80 selection for one score-blind slate."""

    frozen = validate_generation_snapshot_v1(snapshot)
    if set(books_by_arm) != set(ARM_ORDER):
        _fail("task arm lattice differs")
    receipts: dict[str, list[dict[str, object]]] = {arm: [] for arm in ARM_ORDER}
    for block in BLOCK_ORDER:
        if any(set(books_by_arm[arm]) != set(BLOCK_ORDER) for arm in ARM_ORDER):
            _fail("task native-book lattice differs")
        control = books_by_arm["control"][block]
        treatment = books_by_arm["treatment"][block]
        control_receipt = _batch_receipt(control, arm="control", block=block)
        treatment_receipt = _batch_receipt(
            treatment, arm="treatment", block=block
        )
        receipts["control"].append(control_receipt)
        receipts["treatment"].append(treatment_receipt)
        if control.player_ids != treatment.player_ids or not np.array_equal(
            control.row_draws, treatment.row_draws
        ):
            _fail(f"{block} player worlds differ across allocation arms")
        control_role = control_receipt["role_injection"]
        treatment_role = treatment_receipt["role_injection"]
        invariant_role_fields = (
            "requested_count", "represented_count",
            "requested_candidate_rosters_sha256",
            "requested_candidate_totals_sha256",
        )
        if any(
            control_role[field] != treatment_role[field]
            for field in invariant_role_fields
        ):
            _fail(f"{block} frozen requested role12 differs across arms")

    populations: list[dict[str, object]] = []
    selected_books: list[dict[str, object]] = []
    arm_science: dict[str, object] = {}
    for arm in ARM_ORDER:
        try:
            combined = combine_cbwu_books(
                books_by_arm[arm], BLOCK_ORDER,
                expected_worlds_per_book=WORLDS_PER_BLOCK,
            )
            picked = select_tail_entries(
                combined.candidate_totals, ENTRY_BUDGET, TAIL_LINE,
                env={"SELECT_LSE": "0", "SELECT_LADDER": ""},
            )
        except (TypeError, ValueError) as exc:
            raise CorpusR6BoomFirstAllocationV1Error(
                f"{arm} CBWU exact-80 selection failed"
            ) from exc
        if len(picked) != ENTRY_BUDGET or len(set(picked)) != ENTRY_BUDGET:
            _fail(f"{arm} selected book is not exact-80")
        lineups = [_lineup_row(lineup) for lineup in combined.candidates]
        if len({row["lineup_id"] for row in lineups}) != len(lineups):
            _fail(f"{arm} combined population repeats a roster")
        selected_ids = [str(lineups[index]["lineup_id"]) for index in picked]
        dimensions = {
            "arm": arm,
            "model_ensemble": 1,
            "leverage_requested_per_seed": 160 if arm == "control" else 40,
            "boom_requested_per_seed": 40 if arm == "control" else 160,
            "role_requested_per_seed": ROLE_DOSE,
            "selector": "CBWU",
            "tail_line": TAIL_LINE,
            "entry_budget": ENTRY_BUDGET,
        }
        population_id = f"boom-first-{arm}"
        populations.append({
            "population_id": population_id,
            "dimensions": dimensions,
            "lineups": lineups,
        })
        coordinate = {"adapter_id": ADAPTER_ID, **dimensions}
        selected_books.append({
            "coordinate": coordinate,
            "coordinate_sha256": canonical_sha256_v1(coordinate),
            "population_id": population_id,
            "selected_lineup_ids": selected_ids,
        })
        arm_science[arm] = {
            "native_books": receipts[arm],
            "invocation_totals": _invocation_totals(receipts[arm]),
            "native_candidate_counts": [row["candidate_count"] for row in receipts[arm]],
            "combined_candidate_count": len(combined.candidates),
            "combined_candidate_rosters_sha256": canonical_sha256_v1(
                [row["roster_player_ids"] for row in lineups]
            ),
            "selected_rosters_sha256": canonical_sha256_v1([
                lineups[index]["roster_player_ids"] for index in picked
            ]),
            "selected_count": ENTRY_BUDGET,
            "all_native_books_failure_free": all(
                bool(row["failure_free"]) for row in receipts[arm]
            ),
        }
    control_selected = set(selected_books[0]["selected_lineup_ids"])
    treatment_selected = set(selected_books[1]["selected_lineup_ids"])
    normalized = {
        "source_ordinal": frozen["source_ordinal"],
        "slate_id": frozen["slate_id"],
        "populations": populations,
        "books": selected_books,
        "later_source_identity": frozen["later_source_identity"],
    }
    runtime = validate_runtime_identity_v1(
        runtime_identity, expected_source_ordinal=int(frozen["source_ordinal"]),
    )
    body: dict[str, object] = {
        "schema_version": TASK_RESULT_SCHEMA,
        "adapter_id": ADAPTER_ID,
        "source_ordinal": frozen["source_ordinal"],
        "season": frozen["season"],
        "week": frozen["week"],
        "slate_id": frozen["slate_id"],
        "generation_snapshot_sha256": frozen["generation_snapshot_sha256"],
        "later_source_identity": frozen["later_source_identity"],
        "runtime_identity": runtime,
        "construction_preset": construction_preset_v1(),
        "arm_science": arm_science,
        "selected_book_intersection": len(control_selected & treatment_selected),
        "normalized_slate": normalized,
        "normalized_slate_sha256": canonical_sha256_v1(normalized),
        "equal_requested_core_work": True,
        "equal_unique_population_required": False,
        "boom_unique_fill": False,
        "target_slate_outcome_columns": [],
        "uses_realized_outcomes": False,
        "descriptive_only": True,
        "production_change_licensed": False,
        "complete": True,
    }
    return _with_hash(body, field="task_result_sha256")


def validate_task_result_v1(value: object) -> dict[str, object]:
    """Replay every persisted scientific and normalized task invariant."""

    result = _mapping(value, label="boom-first task result")
    digest = result.get("task_result_sha256")
    body = {key: child for key, child in result.items() if key != "task_result_sha256"}
    if _digest(digest, label="task result SHA-256") != canonical_sha256_v1(body):
        _fail("task result hash differs")
    expected_fields = {
        "schema_version", "adapter_id", "source_ordinal", "season", "week",
        "slate_id", "generation_snapshot_sha256", "later_source_identity",
        "runtime_identity", "construction_preset", "arm_science",
        "selected_book_intersection", "normalized_slate",
        "normalized_slate_sha256", "equal_requested_core_work",
        "equal_unique_population_required", "boom_unique_fill",
        "target_slate_outcome_columns", "uses_realized_outcomes",
        "descriptive_only", "production_change_licensed", "complete",
        "task_result_sha256",
    }
    ordinal = result.get("source_ordinal")
    slate_id = expected_slate_id_v1(ordinal)
    season, week = SLATE_KEYS[int(ordinal)]
    if (
        set(result) != expected_fields
        or result.get("schema_version") != TASK_RESULT_SCHEMA
        or result.get("adapter_id") != ADAPTER_ID
        or result.get("construction_preset") != construction_preset_v1()
        or result.get("season") != season
        or result.get("week") != week
        or result.get("slate_id") != slate_id
        or result.get("equal_requested_core_work") is not True
        or result.get("equal_unique_population_required") is not False
        or result.get("boom_unique_fill") is not False
        or result.get("target_slate_outcome_columns") != []
        or result.get("uses_realized_outcomes") is not False
        or result.get("descriptive_only") is not True
        or result.get("production_change_licensed") is not False
        or result.get("complete") is not True
    ):
        _fail("task result fixed law differs")
    normalized = _mapping(result.get("normalized_slate"), label="normalized slate")
    if (
        set(normalized) != {
            "source_ordinal", "slate_id", "populations", "books",
            "later_source_identity",
        }
        or normalized.get("source_ordinal") != ordinal
        or normalized.get("slate_id") != slate_id
        or normalized.get("later_source_identity")
        != result.get("later_source_identity")
        or canonical_sha256_v1(normalized) != result.get("normalized_slate_sha256")
    ):
        _fail("task normalized slate binding differs")
    _identity(result.get("later_source_identity"), label="task later source")
    _digest(
        result.get("generation_snapshot_sha256"),
        label="task generation snapshot SHA-256",
    )
    validate_runtime_identity_v1(
        result.get("runtime_identity"), expected_source_ordinal=int(ordinal)
    )
    arm_science = _mapping(result.get("arm_science"), label="task arm science")
    if set(arm_science) != set(ARM_ORDER):
        _fail("task arm-science lattice differs")
    for arm in ARM_ORDER:
        arm_row = _mapping(arm_science[arm], label=f"task {arm} science")
        if set(arm_row) != {
            "native_books", "invocation_totals", "native_candidate_counts",
            "combined_candidate_count", "combined_candidate_rosters_sha256",
            "selected_rosters_sha256", "selected_count",
            "all_native_books_failure_free",
        }:
            _fail(f"task {arm} science fields differ")
        raw_native_books = _sequence(
            arm_row.get("native_books"), label=f"{arm} native books"
        )
        if len(raw_native_books) != len(BLOCK_ORDER):
            _fail(f"task {arm} native-book count differs")
        books = [
            _validate_native_book_receipt_v1(row, arm=arm, block=block)
            for block, row in zip(
                BLOCK_ORDER, raw_native_books, strict=True,
            )
        ]
        combined_count = _exact_int(
            arm_row.get("combined_candidate_count"),
            label=f"task {arm} combined candidate count", minimum=ENTRY_BUDGET,
        )
        _digest(
            arm_row.get("combined_candidate_rosters_sha256"),
            label=f"task {arm} combined roster hash",
        )
        _digest(
            arm_row.get("selected_rosters_sha256"),
            label=f"task {arm} selected roster hash",
        )
        if (
            len(books) != len(BLOCK_ORDER)
            or arm_row.get("invocation_totals") != _invocation_totals(books)
            or arm_row.get("native_candidate_counts")
            != [row.get("candidate_count") for row in books]
            or arm_row.get("selected_count") != ENTRY_BUDGET
            or arm_row.get("all_native_books_failure_free") is not True
            or combined_count > sum(int(row["candidate_count"]) for row in books)
        ):
            _fail(f"task {arm} invocation receipt differs")
    for block_index, block in enumerate(BLOCK_ORDER):
        control_role = arm_science["control"]["native_books"][block_index][
            "role_injection"
        ]
        treatment_role = arm_science["treatment"]["native_books"][block_index][
            "role_injection"
        ]
        if any(
            control_role[field] != treatment_role[field]
            for field in (
                "requested_count", "represented_count",
                "requested_candidate_rosters_sha256",
                "requested_candidate_totals_sha256",
            )
        ):
            _fail(f"task {block} requested role12 differs across arms")
    populations = _sequence(normalized.get("populations"), label="task populations")
    books = _sequence(normalized.get("books"), label="task selected books")
    if len(populations) != len(ARM_ORDER) or len(books) != len(ARM_ORDER):
        _fail("task normalized arm count differs")
    for arm, population, book in zip(ARM_ORDER, populations, books, strict=True):
        pop = _mapping(population, label=f"task {arm} population")
        selected = _mapping(book, label=f"task {arm} book")
        expected_dimensions = {
            "arm": arm,
            "model_ensemble": 1,
            "leverage_requested_per_seed": 160 if arm == "control" else 40,
            "boom_requested_per_seed": 40 if arm == "control" else 160,
            "role_requested_per_seed": ROLE_DOSE,
            "selector": "CBWU",
            "tail_line": TAIL_LINE,
            "entry_budget": ENTRY_BUDGET,
        }
        population_id = f"boom-first-{arm}"
        lineups = _sequence(pop.get("lineups"), label=f"task {arm} lineups")
        normalized_lineups: list[dict[str, object]] = []
        for index, raw_lineup in enumerate(lineups):
            lineup = _mapping(raw_lineup, label=f"task {arm} lineup[{index}]")
            roster = _roster(
                lineup.get("roster_player_ids"),
                label=f"task {arm} lineup[{index}] roster",
            )
            roster_sha = canonical_sha256_v1(roster)
            if (
                set(lineup) != {
                    "lineup_id", "roster_player_ids", "roster_sha256",
                }
                or lineup.get("roster_player_ids") != roster
                or lineup.get("roster_sha256") != roster_sha
                or lineup.get("lineup_id") != f"roster-{roster_sha}"
            ):
                _fail(f"task {arm} lineup receipt differs")
            normalized_lineups.append(lineup)
        lineup_ids = [str(row["lineup_id"]) for row in normalized_lineups]
        selected_ids = _sequence(
            selected.get("selected_lineup_ids"), label=f"task {arm} selected"
        )
        coordinate = {"adapter_id": ADAPTER_ID, **expected_dimensions}
        if (
            set(pop) != {"population_id", "dimensions", "lineups"}
            or set(selected) != {
                "coordinate", "coordinate_sha256", "population_id",
                "selected_lineup_ids",
            }
            or pop.get("population_id") != population_id
            or pop.get("dimensions") != expected_dimensions
            or len(lineups) < ENTRY_BUDGET
            or len(set(lineup_ids)) != len(lineups)
            or len(lineups) != arm_science[arm]["combined_candidate_count"]
            or canonical_sha256_v1([
                row["roster_player_ids"] for row in normalized_lineups
            ]) != arm_science[arm]["combined_candidate_rosters_sha256"]
            or selected.get("population_id") != population_id
            or selected.get("coordinate") != coordinate
            or selected.get("coordinate_sha256") != canonical_sha256_v1(coordinate)
            or len(selected_ids) != ENTRY_BUDGET
            or len(set(selected_ids)) != ENTRY_BUDGET
            or not set(selected_ids) <= set(lineup_ids)
        ):
            _fail(f"task {arm} normalized exact-80 book differs")
        lineup_by_id = {
            str(row["lineup_id"]): row for row in normalized_lineups
        }
        if canonical_sha256_v1([
            lineup_by_id[str(lineup_id)]["roster_player_ids"]
            for lineup_id in selected_ids
        ]) != arm_science[arm]["selected_rosters_sha256"]:
            _fail(f"task {arm} selected roster receipt differs")
    control_selected = set(books[0]["selected_lineup_ids"])
    treatment_selected = set(books[1]["selected_lineup_ids"])
    if result.get("selected_book_intersection") != len(
        control_selected & treatment_selected
    ):
        _fail("task selected-book intersection differs")
    return result


def validate_provider_terminal_execution_v1(value: object) -> dict[str, object]:
    """Validate the provider-observed exact-54 terminal proof."""

    proof = _mapping(value, label="boom-first provider terminal proof")
    expected_fields = {
        "schema_version", "manifest_identity", "manifest_sha256",
        "launch_claim_identity", "launch_receipt_identity",
        "launch_receipt_sha256",
        "execution_id", "job_name", "job_uid", "service_account",
        "project_id", "region", "task_count", "succeeded_count",
        "failed_count", "cancelled_count", "running_count", "terminal",
        "provider_observed", "job_observation", "job_observation_sha256",
        "provider_terminal_execution_sha256",
    }
    body = {
        key: child for key, child in proof.items()
        if key != "provider_terminal_execution_sha256"
    }
    job = _mapping(proof.get("job_observation"), label="provider job observation")
    if (
        set(proof) != expected_fields
        or proof.get("schema_version") != PROVIDER_TERMINAL_SCHEMA
        or proof.get("provider_terminal_execution_sha256")
        != canonical_sha256_v1(body)
        or proof.get("job_observation_sha256") != canonical_sha256_v1(job)
        or proof.get("task_count") != TASK_COUNT
        or proof.get("succeeded_count") != TASK_COUNT
        or proof.get("failed_count") != 0
        or proof.get("cancelled_count") != 0
        or proof.get("running_count") != 0
        or proof.get("terminal") is not True
        or proof.get("provider_observed") is not True
        or any(
            type(proof.get(field)) is not str or not proof[field]
            for field in (
                "execution_id", "job_name", "job_uid", "service_account",
                "project_id", "region",
            )
        )
        or job.get("job_name") != proof.get("job_name")
        or job.get("job_uid") != proof.get("job_uid")
        or job.get("service_account") != proof.get("service_account")
        or job.get("project_id") != proof.get("project_id")
        or job.get("region") != proof.get("region")
        or job.get("task_count") != TASK_COUNT
        or job.get("provider_observed") is not True
    ):
        _fail("boom-first provider execution is not exact 54/54 terminal")
    _identity(proof.get("manifest_identity"), label="provider manifest")
    _identity(proof.get("launch_claim_identity"), label="provider launch claim")
    _identity(
        proof.get("launch_receipt_identity"), label="provider launch receipt"
    )
    _digest(proof.get("manifest_sha256"), label="provider manifest hash")
    _digest(
        proof.get("launch_receipt_sha256"), label="provider launch receipt hash"
    )
    return proof


def build_terminal_v1(
    *, task_results: Sequence[Mapping[str, object]],
    task_result_identities: Sequence[Mapping[str, object]],
    manifest_identity: object, manifest_sha256: str,
    provider_terminal_execution: Mapping[str, object],
) -> dict[str, object]:
    """Seal exact-54 tasks only after provider-observed 54/54 terminality."""

    if len(task_results) != TASK_COUNT or len(task_result_identities) != TASK_COUNT:
        _fail("boom-first terminal requires exact 54 task results")
    manifest = _identity(manifest_identity, label="boom-first manifest")
    manifest_hash = _digest(manifest_sha256, label="boom-first manifest hash")
    provider = validate_provider_terminal_execution_v1(provider_terminal_execution)
    if (
        provider["manifest_identity"] != manifest
        or provider["manifest_sha256"] != manifest_hash
    ):
        _fail("boom-first provider terminal manifest binding differs")
    retained: list[dict[str, object]] = []
    descriptors: list[dict[str, object]] = []
    normalized: list[dict[str, object]] = []
    later_key: bytes | None = None
    task0_smoke_sha256: str | None = None
    for ordinal, (raw_result, raw_identity) in enumerate(
        zip(task_results, task_result_identities, strict=True)
    ):
        result = validate_task_result_v1(raw_result)
        identity = _identity(raw_identity, label=f"task result[{ordinal}]")
        runtime = validate_runtime_identity_v1(
            result["runtime_identity"], expected_source_ordinal=ordinal
        )
        if (
            result["source_ordinal"] != ordinal
            or identity["sha256"] != canonical_sha256_v1(result)
            or identity["bytes"] != len(canonical_json_bytes_v1(result))
            or runtime["execution_mode"] != "provider-task"
            or runtime["execution_id"] != provider["execution_id"]
            or runtime["job_name"] != provider["job_name"]
            or runtime["reused_job_uid"] != provider["job_uid"]
            or runtime["service_account"] != provider["service_account"]
            or runtime["project_id"] != provider["project_id"]
            or runtime["region"] != provider["region"]
            or runtime["manifest_identity"] != manifest
            or runtime["manifest_sha256"] != manifest_hash
        ):
            _fail("terminal task result/provider authority differs")
        source_key = canonical_json_bytes_v1(result["later_source_identity"])
        if later_key is None:
            later_key = source_key
        elif later_key != source_key:
            _fail("terminal task later-source identities differ")
        if task0_smoke_sha256 is None:
            task0_smoke_sha256 = str(runtime["task0_smoke_sha256"])
        elif runtime["task0_smoke_sha256"] != task0_smoke_sha256:
            _fail("terminal task-0 smoke hashes differ")
        retained.append(result)
        normalized.append(dict(result["normalized_slate"]))
        descriptors.append({
            "source_ordinal": ordinal,
            "slate_id": result["slate_id"],
            "task_result_identity": identity,
            "task_result_sha256": result["task_result_sha256"],
            "generation_snapshot_sha256": result["generation_snapshot_sha256"],
            "runtime_authority_sha256": runtime["runtime_authority_sha256"],
            "execution_id": runtime["execution_id"],
        })
    try:
        validated_normalized = grader.validate_external_normalized_terminal_v1(
            adapter_id=ADAPTER_ID, slates=normalized
        )
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise CorpusR6BoomFirstAllocationV1Error(str(exc)) from exc
    provider_job = _mapping(
        provider["job_observation"], label="terminal provider job"
    )
    provider_environment = _mapping(
        provider_job.get("container_environment"),
        label="terminal provider job environment",
    )
    if (
        task0_smoke_sha256 is None
        or provider_environment.get(TASK0_SMOKE_ENVIRONMENT)
        != task0_smoke_sha256
    ):
        _fail("terminal task/provider task-0 smoke binding differs")
    body: dict[str, object] = {
        "schema_version": TERMINAL_SCHEMA,
        "adapter_id": ADAPTER_ID,
        "manifest_identity": manifest,
        "manifest_sha256": manifest_hash,
        "later_source_identity": retained[0]["later_source_identity"],
        "execution_id": provider["execution_id"],
        "task0_smoke_sha256": task0_smoke_sha256,
        "provider_terminal_execution": provider,
        "provider_terminal_execution_sha256": provider[
            "provider_terminal_execution_sha256"
        ],
        "source_slate_count": TASK_COUNT,
        "entry_budget": ENTRY_BUDGET,
        "tail_line": TAIL_LINE,
        "task_results": descriptors,
        "task_results_sha256": canonical_sha256_v1(descriptors),
        "normalized_slates": list(validated_normalized),
        "normalized_slates_sha256": canonical_sha256_v1(list(validated_normalized)),
        "all_task_results_exact_opened_before_terminal": True,
        "provider_exact_54_of_54_terminal_validated_before_terminal": True,
        "selection_completed_before_first_outcome_read": True,
        "target_slate_outcome_columns": [],
        "uses_realized_outcomes": False,
        "descriptive_only": True,
        "production_change_licensed": False,
        "complete": True,
    }
    return _with_hash(body, field="terminal_sha256")


def validate_terminal_v1(value: object) -> dict[str, object]:
    terminal = _mapping(value, label="boom-first terminal")
    digest = terminal.get("terminal_sha256")
    body = {key: child for key, child in terminal.items() if key != "terminal_sha256"}
    if _digest(digest, label="terminal SHA-256") != canonical_sha256_v1(body):
        _fail("boom-first terminal hash differs")
    expected_fields = {
        "schema_version", "adapter_id", "manifest_identity", "manifest_sha256",
        "later_source_identity", "execution_id", "provider_terminal_execution",
        "task0_smoke_sha256",
        "provider_terminal_execution_sha256", "source_slate_count",
        "entry_budget", "tail_line", "task_results", "task_results_sha256",
        "normalized_slates", "normalized_slates_sha256",
        "all_task_results_exact_opened_before_terminal",
        "provider_exact_54_of_54_terminal_validated_before_terminal",
        "selection_completed_before_first_outcome_read",
        "target_slate_outcome_columns", "uses_realized_outcomes",
        "descriptive_only", "production_change_licensed", "complete",
        "terminal_sha256",
    }
    if (
        set(terminal) != expected_fields
        or terminal.get("schema_version") != TERMINAL_SCHEMA
        or terminal.get("adapter_id") != ADAPTER_ID
        or terminal.get("source_slate_count") != TASK_COUNT
        or terminal.get("entry_budget") != ENTRY_BUDGET
        or terminal.get("tail_line") != TAIL_LINE
        or terminal.get("all_task_results_exact_opened_before_terminal") is not True
        or terminal.get(
            "provider_exact_54_of_54_terminal_validated_before_terminal"
        ) is not True
        or terminal.get("selection_completed_before_first_outcome_read") is not True
        or terminal.get("target_slate_outcome_columns") != []
        or terminal.get("uses_realized_outcomes") is not False
        or terminal.get("descriptive_only") is not True
        or terminal.get("production_change_licensed") is not False
        or terminal.get("complete") is not True
    ):
        _fail("boom-first terminal fixed law differs")
    manifest = _identity(terminal.get("manifest_identity"), label="terminal manifest")
    manifest_hash = _digest(
        terminal.get("manifest_sha256"), label="terminal manifest hash"
    )
    _identity(terminal.get("later_source_identity"), label="terminal later source")
    provider = validate_provider_terminal_execution_v1(
        terminal.get("provider_terminal_execution")
    )
    task0_smoke = _digest(
        terminal.get("task0_smoke_sha256"), label="terminal task-0 smoke hash"
    )
    provider_environment = _mapping(
        _mapping(
            provider.get("job_observation"), label="terminal provider job"
        ).get("container_environment"),
        label="terminal provider environment",
    )
    if (
        provider["manifest_identity"] != manifest
        or provider["manifest_sha256"] != manifest_hash
        or provider["execution_id"] != terminal.get("execution_id")
        or provider["provider_terminal_execution_sha256"]
        != terminal.get("provider_terminal_execution_sha256")
        or provider_environment.get(TASK0_SMOKE_ENVIRONMENT) != task0_smoke
    ):
        _fail("boom-first terminal provider proof binding differs")
    descriptors = _sequence(terminal.get("task_results"), label="terminal tasks")
    if (
        len(descriptors) != TASK_COUNT
        or terminal.get("task_results_sha256") != canonical_sha256_v1(descriptors)
    ):
        _fail("boom-first terminal task lattice differs")
    for ordinal, raw in enumerate(descriptors):
        descriptor = _mapping(raw, label=f"terminal task[{ordinal}]")
        if (
            set(descriptor) != {
                "source_ordinal", "slate_id", "task_result_identity",
                "task_result_sha256", "generation_snapshot_sha256",
                "runtime_authority_sha256", "execution_id",
            }
            or descriptor.get("source_ordinal") != ordinal
            or descriptor.get("slate_id") != expected_slate_id_v1(ordinal)
            or descriptor.get("execution_id") != terminal.get("execution_id")
        ):
            _fail("boom-first terminal task descriptor differs")
        _identity(descriptor.get("task_result_identity"), label="terminal task result")
        for field in (
            "task_result_sha256", "generation_snapshot_sha256",
            "runtime_authority_sha256",
        ):
            _digest(descriptor.get(field), label=f"terminal task {field}")
    normalized = _sequence(
        terminal.get("normalized_slates"), label="terminal normalized slates"
    )
    if canonical_sha256_v1(normalized) != terminal.get("normalized_slates_sha256"):
        _fail("terminal normalized surface hash differs")
    try:
        grader.validate_external_normalized_terminal_v1(
            adapter_id=ADAPTER_ID, slates=normalized
        )
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise CorpusR6BoomFirstAllocationV1Error(str(exc)) from exc
    return terminal


__all__ = [
    "ADAPTER_ID", "ARM_ORDER", "BLOCK_ORDER", "CANDIDATE_FIELDS",
    "CorpusR6BoomFirstAllocationV1Error", "ENTRY_BUDGET",
    "GENERATION_SNAPSHOT_SCHEMA", "GRADE_SCHEMA", "PLAYER_FIELDS",
    "PROVIDER_TERMINAL_SCHEMA", "RUNTIME_AUTHORITY_SCHEMA",
    "REPAIR_PANEL", "SLATE_KEYS", "SOURCE_PANELS", "TAIL_LINE",
    "TASK0_SMOKE_ENVIRONMENT", "TASK_COUNT", "TASK_RESULT_SCHEMA", "TERMINAL_SCHEMA",
    "WORLDS_PER_BLOCK", "arm_environments_v1", "build_generation_snapshot_v1",
    "build_task_result_v1", "build_terminal_v1", "candidate_source_panel_v1",
    "canonical_json_bytes_v1", "canonical_sha256_v1", "construction_preset_v1",
    "expected_slate_id_v1",
    "incumbent_policy_environment_v1", "inject_frozen_role12_v1",
    "validate_provider_terminal_execution_v1", "validate_runtime_identity_v1",
    "validate_task_result_v1", "validate_terminal_v1",
]
