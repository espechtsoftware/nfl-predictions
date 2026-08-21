"""Outcome-blind source construction for the LR8 earlier-period fit.

This module owns no warehouse, object-store, Cloud Run, or realized-score
client.  A future runner must materialize the audited 2019/2021 catalog and
fresh point-in-time player worlds, then pass those values through the strict
dataclasses below.  The only callback is an exact world optimizer; it receives
pre-lock player scores and the canonical incumbent roster no-goods, never a
realized outcome.

The construction law is intentionally narrow:

* target seasons are exactly 2019 and 2021 (17 + 18 Sunday-main slates);
* each target season is independently refit from seasons strictly before it;
* only R0=(0,7331) and R1=(1137260708,2690847602) are generated;
* each block contributes exactly forty unique DK-Classic-only world optima;
* duplicate optima advance the fixed world order, capped at eighty solve
  attempts per block, but do not change the forty-candidate dose;
* the two forty-row blocks are concatenated before cross-block deduplication;
* incumbent identities are source data/no-goods, never recycled candidate
  totals; and
* catalog, world, solve-evidence, legality, anatomy, pre-dedup, and post-dedup
  identities are frozen before any candidate label may be read.

``replay_projections`` currently appends target ``y_dk_points`` to an
``actual`` column, so the real runner may not call its present public wrapper.
``PIT_REPLAY_PATH_ID`` names the required default-preserving score-free seam:
the same fit/simulation path with ``include_actual=False``.  Until that seam is
implemented and reality-smoked, callers can only provide mocked or separately
audited replay blocks and this module grants no label-read license.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
import re
from typing import Final

import numpy as np

from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research import lr8_historical_arm as lr8


PROTOCOL_ID: Final = "20260820-lr8-historical-residual-columns-v1"
SOURCE_VERSION: Final = "lr8-earlier-period-training-source-v1"
CANONICAL_PANEL_ID: Final = (
    "20260811-pitclean-e80-k1-role12union-a12ab31"
)
PIT_REPLAY_PATH_ID: Final = (
    "nfl_dfs.backtest.replay.replay_projections(include_actual=False)-v1"
)
TARGET_SEASONS: Final = (2019, 2021)
MODEL_TRAINING_SEASONS: Final = {
    2019: (2015, 2016, 2017, 2018),
    2021: (2015, 2016, 2017, 2018, 2019, 2020),
}
EXPECTED_WEEKS: Final = {
    2019: tuple(range(1, 18)),
    2021: tuple(range(1, 19)),
}
EXPECTED_SLATE_KEYS: Final = tuple(
    (season, week)
    for season in TARGET_SEASONS
    for week in EXPECTED_WEEKS[season]
)
EXPECTED_SLATES: Final = 35
BLOCK_SEED_PAIRS: Final = {
    "R0": (0, 7331),
    "R1": (1137260708, 2690847602),
}
BLOCK_ORDER: Final = tuple(BLOCK_SEED_PAIRS)
WORLDS_PER_BLOCK: Final = 10_000
CANDIDATE_WORLD_FAMILY: Final = "baseline_player_draws"
ROLE_SEED_USAGE: Final = "canonical_source_environment_receipt_only"
UNIQUE_OPTIMA_PER_BLOCK: Final = 40
MAX_SOLVE_ATTEMPTS_PER_BLOCK: Final = 80
PRE_CROSS_BLOCK_CANDIDATES: Final = 80
WORLD_ORDER_LAW: Final = (
    "descending_float32_total_slate_points_then_ascending_world_index"
)
HARD_DOMAIN_ID: Final = "draftkings-nfl-classic-only-v1"
CANONICAL_CATALOG_FIELDS: Final = frozenset({
    "id", "pos", "team", "opp", "game_id", "salary",
})
FORMER_HOUSE_RULES_NOT_APPLIED: Final = (
    "salary_floor",
    "qb_stack_min_or_max",
    "bring_back_min_or_max",
    "rb_vs_opposing_dst_ban",
    "same_team_rb_ban",
    "ownership_quota",
    "exposure_quota",
    "archetype_quota",
    "punt_quota",
    "game_concentration_quota",
)
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_FORBIDDEN_SOURCE_KEYS: Final = frozenset({
    "actual",
    "actual_score",
    "candidate_actual",
    "candidate_score",
    "contest_rank",
    "field_rank",
    "outcome",
    "payout",
    "realized",
    "realized_score",
    "settled_score",
    "winner",
    "winner_score",
    "y_dk_points",
})


class LR8TrainingSourceError(ValueError):
    """A fail-closed earlier-period source-contract violation."""


def canonical_json(value: object) -> bytes:
    """Canonical manifest bytes; NaN and infinities are always fatal."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LR8TrainingSourceError("value is not canonical JSON") from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json(value)).hexdigest()


def array_sha256(value: np.ndarray) -> str:
    """Scientific array identity, binding dtype, shape, and exact bytes."""
    array = np.ascontiguousarray(value)
    digest = sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(canonical_json(list(array.shape)))
    digest.update(b"\0")
    if array.size:
        digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def player_ids_sha256(player_ids: Sequence[object]) -> str:
    ids = _strict_player_ids(player_ids)
    return canonical_sha256(list(ids))


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise LR8TrainingSourceError(f"{label} must be an exact integer")
    result = int(value)
    if result < minimum:
        raise LR8TrainingSourceError(f"{label} must be >= {minimum}")
    return result


def _strict_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise LR8TrainingSourceError(f"{label} must be a canonical string")
    return value


def _strict_sha256(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise LR8TrainingSourceError(f"{label} must be a lowercase SHA-256")
    return value


def _literal_bool(value: object, *, label: str, expected: bool) -> None:
    if not isinstance(value, bool) or value is not expected:
        raise LR8TrainingSourceError(f"{label} must be literal {expected}")


def _strict_player_ids(values: Sequence[object]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise LR8TrainingSourceError("player ids must be a sequence")
    result = tuple(
        _strict_string(value, label="player id") for value in values
    )
    if not result or len(set(result)) != len(result):
        raise LR8TrainingSourceError("player ids are empty or repeat")
    return result


def _normalized_receipt(
    value: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise LR8TrainingSourceError(f"{label} is not a content receipt")
    uri = value.get("uri")
    generation = value.get("generation")
    digest = value.get("sha256")
    size = value.get("bytes")
    if (
        not isinstance(uri, str)
        or not uri.startswith("gs://")
        or not uri.removeprefix("gs://").partition("/")[0]
        or not uri.removeprefix("gs://").partition("/")[2]
        or not isinstance(generation, str)
        or re.fullmatch(r"[1-9][0-9]*", generation) is None
        or not isinstance(digest, str)
        or _SHA256.fullmatch(digest) is None
        or isinstance(size, bool)
        or not isinstance(size, int)
        or size <= 0
    ):
        raise LR8TrainingSourceError(
            f"{label} is not exact positive generation-pinned GCS identity"
        )
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": size,
    }


def _normalized_receipts(
    values: Sequence[Mapping[str, object]], *, label: str,
) -> tuple[dict[str, object], ...]:
    if isinstance(values, (str, bytes)):
        raise LR8TrainingSourceError(f"{label} must be a receipt sequence")
    result = tuple(
        _normalized_receipt(value, label=f"{label}[{index}]")
        for index, value in enumerate(values)
    )
    if not result:
        raise LR8TrainingSourceError(f"{label} must not be empty")
    identities = [tuple(receipt.values()) for receipt in result]
    if len(set(identities)) != len(identities):
        raise LR8TrainingSourceError(f"{label} repeats a content identity")
    return result


def _players(
    values: Sequence[rw.PlayerSpec | Mapping[str, object]],
) -> tuple[rw.PlayerSpec, ...]:
    if isinstance(values, (str, bytes)):
        raise LR8TrainingSourceError("canonical catalog must be a sequence")
    rows: list[rw.PlayerSpec] = []
    for index, value in enumerate(values):
        if isinstance(value, rw.PlayerSpec):
            player = value
        elif isinstance(value, Mapping):
            if set(value) != CANONICAL_CATALOG_FIELDS:
                forbidden = sorted(
                    str(key) for key in value
                    if str(key).lower() in _FORBIDDEN_SOURCE_KEYS
                )
                suffix = f"; forbidden={forbidden}" if forbidden else ""
                raise LR8TrainingSourceError(
                    f"catalog row {index} fields differ{suffix}"
                )
            try:
                player = rw.PlayerSpec.from_mapping(value)
            except (KeyError, TypeError, rw.ResidualWorldError) as exc:
                raise LR8TrainingSourceError(
                    f"catalog row {index} is malformed"
                ) from exc
        else:
            raise LR8TrainingSourceError(
                f"catalog row {index} has the wrong type"
            )
        if player.salary <= 0:
            raise LR8TrainingSourceError("catalog salaries must be positive")
        rows.append(player)
    result = tuple(sorted(rows, key=lambda row: row.player_id))
    if len(result) < rw.ROSTER_SIZE or len({row.player_id for row in result}) != len(
        result
    ):
        raise LR8TrainingSourceError(
            "canonical catalog is too small or repeats player ids"
        )
    return result


def _catalog_payload(players: Sequence[rw.PlayerSpec]) -> list[dict[str, object]]:
    return [{
        "id": player.player_id,
        "pos": player.position,
        "team": player.team,
        "opp": player.opponent,
        "game_id": player.game_id,
        "salary": player.salary,
    } for player in players]


def catalog_sha256(players: Sequence[rw.PlayerSpec | Mapping[str, object]]) -> str:
    return canonical_sha256(_catalog_payload(_players(players)))


def _identities(
    values: Sequence[Sequence[object]],
    *,
    label: str,
) -> tuple[tuple[str, ...], ...]:
    if isinstance(values, (str, bytes)):
        raise LR8TrainingSourceError(f"{label} must be a roster sequence")
    try:
        result = tuple(rw.canonical_identity(value) for value in values)
    except rw.ResidualWorldError as exc:
        raise LR8TrainingSourceError(f"{label} is malformed") from exc
    if not result or len(set(result)) != len(result):
        raise LR8TrainingSourceError(f"{label} is empty or repeats rosters")
    return result


def identities_sha256(values: Sequence[Sequence[object]]) -> str:
    identities = _identities(values, label="roster identities")
    return canonical_sha256([list(identity) for identity in identities])


def _anatomy_payload(features: Sequence[float]) -> list[int | float]:
    values: list[int | float] = []
    for value in features:
        number = float(value)
        if not math.isfinite(number):
            raise LR8TrainingSourceError("anatomy contains a non-finite value")
        values.append(int(number) if number.is_integer() else number)
    if len(values) != len(lr8.ANATOMY_FEATURES):
        raise LR8TrainingSourceError("anatomy feature width differs")
    return values


def _read_only_float32(values: np.ndarray) -> np.ndarray:
    result = np.array(values, dtype=np.float32, copy=True, order="C")
    result.flags.writeable = False
    return result


@dataclass(frozen=True, slots=True)
class CanonicalSlateSource:
    """Audited old-panel catalog/incumbent identities, with no totals."""

    season: int
    week: int
    panel_id: str
    players: tuple[rw.PlayerSpec | Mapping[str, object], ...]
    incumbent_candidates: tuple[tuple[str, ...], ...]
    catalog_sha256: str
    incumbent_candidates_sha256: str
    catalog_source_receipts: tuple[Mapping[str, object], ...]
    incumbent_source_receipts: tuple[Mapping[str, object], ...]
    candidate_totals_loaded: bool = False
    outcome_fields_read: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReplaySlateWorlds:
    """One score-free slate's aligned player worlds from a PIT block."""

    season: int
    week: int
    player_ids: tuple[str, ...]
    player_draws: np.ndarray = field(compare=False, repr=False)
    player_ids_sha256: str = ""
    player_draws_sha256: str = ""
    source_receipts: tuple[Mapping[str, object], ...] = ()
    target_outcome_fields_read: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PITReplayBlock:
    """One target-season refit/simulation block from the safe replay seam."""

    target_season: int
    block: str
    projection_seed: int
    source_environment_role_seed_nonoperative: int
    replay_path_id: str
    model_training_seasons: tuple[int, ...]
    model_fit_input_sha256: str
    model_fit_sha256: str
    fit_source_receipts: tuple[Mapping[str, object], ...]
    slates: tuple[ReplaySlateWorlds, ...]
    target_player_labels_read: bool = False
    candidate_labels_read: bool = False
    candidate_world_family: str = CANDIDATE_WORLD_FAMILY
    role_belief_worlds_used: bool = False
    b1_inputs_used: bool = False
    a2a_inputs_used: bool = False
    later_period_inputs_used: bool = False


@dataclass(frozen=True, slots=True)
class WorldSolveRequest:
    """The complete outcome-blind input to one exact DK-only world solve."""

    season: int
    week: int
    block: str
    projection_seed: int
    world_index: int
    players: tuple[rw.PlayerSpec, ...]
    player_scores: np.ndarray = field(compare=False, repr=False)
    incumbent_no_goods: tuple[tuple[str, ...], ...]
    catalog_sha256: str
    player_scores_sha256: str
    incumbent_no_goods_sha256: str
    candidate_world_family: str
    role_belief_worlds_used: bool
    hard_domain_id: str
    former_house_rules_not_applied: tuple[str, ...]
    request_sha256: str


@dataclass(frozen=True, slots=True)
class ExactWorldOptimum:
    """Solver response; exact retained evidence is mandatory."""

    roster: tuple[str, ...]
    request_sha256: str
    objective_micro: int
    evidence_receipts: tuple[Mapping[str, object], ...]
    exact_optimal: bool
    canonical_roster_tiebreak: bool
    dk_classic_only: bool
    incumbent_no_goods_enforced: bool
    house_rules_applied: tuple[str, ...] = ()


WorldSolver = Callable[[WorldSolveRequest], ExactWorldOptimum]


@dataclass(frozen=True, slots=True)
class SolveAttempt:
    block: str
    projection_seed: int
    world_index: int
    roster: tuple[str, ...]
    objective_micro: int
    admitted_unique: bool
    request_sha256: str
    evidence_receipts: tuple[dict[str, object], ...]
    evidence_manifest_sha256: str


@dataclass(frozen=True, slots=True)
class FrozenCandidate:
    season: int
    week: int
    roster: tuple[str, ...]
    anatomy_features: tuple[float, ...]
    first_source_block: str
    first_source_world_index: int
    source_occurrences: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class FrozenBlockSource:
    block: str
    projection_seed: int
    source_environment_role_seed_nonoperative: int
    player_ids: tuple[str, ...]
    player_draws: np.ndarray = field(compare=False, repr=False)
    player_ids_sha256: str
    player_draws_sha256: str
    world_order: tuple[int, ...]
    world_order_sha256: str
    source_receipts: tuple[dict[str, object], ...]
    solve_attempts: tuple[SolveAttempt, ...]
    solve_attempts_sha256: str
    candidates: tuple[FrozenCandidate, ...]
    candidate_identities_sha256: str
    anatomy_sha256: str
    legality_sha256: str


@dataclass(frozen=True, slots=True)
class FrozenTrainingSlate:
    season: int
    week: int
    players: tuple[rw.PlayerSpec, ...]
    incumbent_candidates: tuple[tuple[str, ...], ...]
    catalog_sha256: str
    incumbent_candidates_sha256: str
    catalog_source_receipts: tuple[dict[str, object], ...]
    incumbent_source_receipts: tuple[dict[str, object], ...]
    blocks: tuple[FrozenBlockSource, ...]
    pre_cross_block_candidate_count: int
    pre_cross_block_sha256: str
    post_cross_block_candidates: tuple[FrozenCandidate, ...]
    post_cross_block_sha256: str
    cross_block_duplicates: int


@dataclass(frozen=True, slots=True)
class TrainingSourceBundle:
    protocol_id: str
    version: str
    canonical_panel_id: str
    target_seasons: tuple[int, ...]
    slate_keys: tuple[tuple[int, int], ...]
    replay_blocks: tuple[PITReplayBlock, ...]
    slates: tuple[FrozenTrainingSlate, ...]


def _normalize_canonical_source(
    source: CanonicalSlateSource,
) -> tuple[
    tuple[rw.PlayerSpec, ...],
    tuple[tuple[str, ...], ...],
    tuple[dict[str, object], ...],
    tuple[dict[str, object], ...],
]:
    if not isinstance(source, CanonicalSlateSource):
        raise LR8TrainingSourceError("canonical source has the wrong type")
    season = _exact_int(source.season, label="canonical season")
    week = _exact_int(source.week, label="canonical week", minimum=1)
    if (season, week) not in EXPECTED_SLATE_KEYS:
        raise LR8TrainingSourceError("canonical source is outside exact 35 slates")
    if source.panel_id != CANONICAL_PANEL_ID:
        raise LR8TrainingSourceError("canonical panel identity differs")
    _literal_bool(
        source.candidate_totals_loaded,
        label="old-law candidate_totals_loaded",
        expected=False,
    )
    if source.outcome_fields_read != ():
        raise LR8TrainingSourceError("canonical source read an outcome field")
    players = _players(source.players)
    catalog_digest = canonical_sha256(_catalog_payload(players))
    if catalog_digest != _strict_sha256(
        source.catalog_sha256, label="canonical catalog hash"
    ):
        raise LR8TrainingSourceError("canonical catalog hash differs")
    incumbents = _identities(
        source.incumbent_candidates, label="incumbent candidates"
    )
    incumbent_digest = canonical_sha256(
        [list(identity) for identity in incumbents]
    )
    if incumbent_digest != _strict_sha256(
        source.incumbent_candidates_sha256,
        label="incumbent candidates hash",
    ):
        raise LR8TrainingSourceError("incumbent candidate hash differs")
    for identity in incumbents:
        try:
            lr8.audit_dk_classic_identity(players, identity)
        except lr8.LR8Error as exc:
            raise LR8TrainingSourceError(
                "canonical incumbent is not DK Classic legal"
            ) from exc
    return (
        players,
        incumbents,
        _normalized_receipts(
            source.catalog_source_receipts, label="catalog source receipts"
        ),
        _normalized_receipts(
            source.incumbent_source_receipts,
            label="incumbent source receipts",
        ),
    )


def _normalize_replay_block(
    value: PITReplayBlock,
) -> dict[tuple[int, int], tuple[tuple[str, ...], np.ndarray, tuple[dict[str, object], ...]]]:
    if not isinstance(value, PITReplayBlock):
        raise LR8TrainingSourceError("PIT replay block has the wrong type")
    season = _exact_int(value.target_season, label="PIT target season")
    if season not in TARGET_SEASONS:
        raise LR8TrainingSourceError("PIT target season differs")
    block = _strict_string(value.block, label="PIT block")
    if block not in BLOCK_SEED_PAIRS:
        raise LR8TrainingSourceError("PIT block must be R0 or R1")
    expected_seeds = BLOCK_SEED_PAIRS[block]
    seeds = (
        _exact_int(value.projection_seed, label="projection seed"),
        _exact_int(
            value.source_environment_role_seed_nonoperative,
            label="nonoperative source-environment role seed",
        ),
    )
    if seeds != expected_seeds:
        raise LR8TrainingSourceError("PIT seed pair differs")
    if value.replay_path_id != PIT_REPLAY_PATH_ID:
        raise LR8TrainingSourceError("PIT replay path is not the score-free seam")
    training_seasons = tuple(
        _exact_int(item, label="model training season")
        for item in value.model_training_seasons
    )
    if training_seasons != MODEL_TRAINING_SEASONS[season]:
        raise LR8TrainingSourceError(
            "PIT model training seasons differ from exact 2015-to-target-minus-one"
        )
    _strict_sha256(value.model_fit_input_sha256, label="model fit input hash")
    _strict_sha256(value.model_fit_sha256, label="model fit hash")
    _normalized_receipts(value.fit_source_receipts, label="fit source receipts")
    for label, actual in (
        ("target_player_labels_read", value.target_player_labels_read),
        ("candidate_labels_read", value.candidate_labels_read),
        ("role_belief_worlds_used", value.role_belief_worlds_used),
        ("b1_inputs_used", value.b1_inputs_used),
        ("a2a_inputs_used", value.a2a_inputs_used),
        ("later_period_inputs_used", value.later_period_inputs_used),
    ):
        _literal_bool(actual, label=label, expected=False)
    if value.candidate_world_family != CANDIDATE_WORLD_FAMILY:
        raise LR8TrainingSourceError("PIT candidate world family differs")

    slates: dict[
        tuple[int, int],
        tuple[tuple[str, ...], np.ndarray, tuple[dict[str, object], ...]],
    ] = {}
    for row in value.slates:
        if not isinstance(row, ReplaySlateWorlds):
            raise LR8TrainingSourceError("PIT slate worlds have the wrong type")
        key = (
            _exact_int(row.season, label="PIT slate season"),
            _exact_int(row.week, label="PIT slate week", minimum=1),
        )
        if key[0] != season or key not in EXPECTED_SLATE_KEYS or key in slates:
            raise LR8TrainingSourceError("PIT replay slate keys differ")
        if row.target_outcome_fields_read != ():
            raise LR8TrainingSourceError("PIT replay read a target outcome field")
        ids = _strict_player_ids(row.player_ids)
        if player_ids_sha256(ids) != _strict_sha256(
            row.player_ids_sha256, label="PIT player ids hash"
        ):
            raise LR8TrainingSourceError("PIT player ids hash differs")
        draws = np.asarray(row.player_draws)
        if (
            draws.dtype != np.float32
            or draws.shape != (len(ids), WORLDS_PER_BLOCK)
            or not np.isfinite(draws).all()
        ):
            raise LR8TrainingSourceError(
                "PIT player draws must be aligned finite float32 x 10000"
            )
        if array_sha256(draws) != _strict_sha256(
            row.player_draws_sha256, label="PIT player draws hash"
        ):
            raise LR8TrainingSourceError("PIT player draws hash differs")
        receipts = _normalized_receipts(
            row.source_receipts, label="PIT slate world receipts"
        )
        slates[key] = (ids, _read_only_float32(draws), receipts)
    expected = {(season, week) for week in EXPECTED_WEEKS[season]}
    if set(slates) != expected:
        raise LR8TrainingSourceError("PIT replay does not cover its exact season")
    return slates


def deterministic_world_order(player_draws: np.ndarray) -> tuple[int, ...]:
    """Tail-first order with an explicit world-index tie-break."""
    draws = np.asarray(player_draws)
    if (
        draws.dtype != np.float32
        or draws.ndim != 2
        or draws.shape[1] != WORLDS_PER_BLOCK
        or not np.isfinite(draws).all()
    ):
        raise LR8TrainingSourceError("world-order input differs")
    # Float32 accumulation matches the incumbent boom-order signal.  Unlike
    # the older bare argsort, lexsort makes ties explicitly portable.
    totals = draws.sum(axis=0, dtype=np.float32)
    indices = np.arange(WORLDS_PER_BLOCK, dtype=np.int64)
    order = np.lexsort((indices, -totals.astype(np.float64)))
    result = tuple(int(index) for index in order)
    if len(result) != WORLDS_PER_BLOCK or set(result) != set(
        range(WORLDS_PER_BLOCK)
    ):
        raise AssertionError("deterministic world order is not a permutation")
    return result


def _solve_request(
    *,
    season: int,
    week: int,
    block: str,
    players: tuple[rw.PlayerSpec, ...],
    player_draws: np.ndarray,
    world_index: int,
    incumbents: tuple[tuple[str, ...], ...],
    catalog_digest: str,
    incumbent_digest: str,
) -> WorldSolveRequest:
    scores = np.array(
        player_draws[:, world_index], dtype=np.float32, copy=True, order="C"
    )
    scores.flags.writeable = False
    score_digest = array_sha256(scores)
    projection_seed = BLOCK_SEED_PAIRS[block][0]
    payload = {
        "season": season,
        "week": week,
        "block": block,
        "projection_seed": projection_seed,
        "world_index": world_index,
        "catalog_sha256": catalog_digest,
        "player_scores_sha256": score_digest,
        "incumbent_no_goods_sha256": incumbent_digest,
        "candidate_world_family": CANDIDATE_WORLD_FAMILY,
        "role_belief_worlds_used": False,
        "hard_domain_id": HARD_DOMAIN_ID,
        "former_house_rules_not_applied": list(FORMER_HOUSE_RULES_NOT_APPLIED),
    }
    return WorldSolveRequest(
        season=season,
        week=week,
        block=block,
        projection_seed=projection_seed,
        world_index=world_index,
        players=players,
        player_scores=scores,
        incumbent_no_goods=incumbents,
        catalog_sha256=catalog_digest,
        player_scores_sha256=score_digest,
        incumbent_no_goods_sha256=incumbent_digest,
        candidate_world_family=CANDIDATE_WORLD_FAMILY,
        role_belief_worlds_used=False,
        hard_domain_id=HARD_DOMAIN_ID,
        former_house_rules_not_applied=FORMER_HOUSE_RULES_NOT_APPLIED,
        request_sha256=canonical_sha256(payload),
    )


def _solve_block(
    *,
    season: int,
    week: int,
    block: str,
    players: tuple[rw.PlayerSpec, ...],
    player_ids: tuple[str, ...],
    player_draws: np.ndarray,
    world_receipts: tuple[dict[str, object], ...],
    incumbents: tuple[tuple[str, ...], ...],
    catalog_digest: str,
    incumbent_digest: str,
    solve_world: WorldSolver,
) -> FrozenBlockSource:
    order = deterministic_world_order(player_draws)
    micro = rw.to_micro_dk(player_draws)
    by_id = {player.player_id: index for index, player in enumerate(players)}
    attempts: list[SolveAttempt] = []
    candidates: list[FrozenCandidate] = []
    seen: set[tuple[str, ...]] = set()
    for world_index in order[:MAX_SOLVE_ATTEMPTS_PER_BLOCK]:
        if len(candidates) == UNIQUE_OPTIMA_PER_BLOCK:
            break
        request = _solve_request(
            season=season,
            week=week,
            block=block,
            players=players,
            player_draws=player_draws,
            world_index=world_index,
            incumbents=incumbents,
            catalog_digest=catalog_digest,
            incumbent_digest=incumbent_digest,
        )
        solved = solve_world(request)
        if not isinstance(solved, ExactWorldOptimum):
            raise LR8TrainingSourceError("world solver returned the wrong type")
        if solved.request_sha256 != request.request_sha256:
            raise LR8TrainingSourceError("world solver response is stale")
        for label, actual in (
            ("exact_optimal", solved.exact_optimal),
            ("canonical_roster_tiebreak", solved.canonical_roster_tiebreak),
            ("dk_classic_only", solved.dk_classic_only),
            ("incumbent_no_goods_enforced", solved.incumbent_no_goods_enforced),
        ):
            _literal_bool(actual, label=f"world solve {label}", expected=True)
        if solved.house_rules_applied != ():
            raise LR8TrainingSourceError("world solve applied a former house rule")
        try:
            identity = lr8.audit_dk_classic_identity(players, solved.roster)
        except lr8.LR8Error as exc:
            raise LR8TrainingSourceError(
                "world solver returned a non-DK-legal roster"
            ) from exc
        if identity in incumbents:
            raise LR8TrainingSourceError(
                "world solver reused a canonical incumbent identity"
            )
        indices = [by_id[player_id] for player_id in identity]
        objective_micro = int(
            micro[indices, world_index].sum(dtype=np.int64)
        )
        if _exact_int(
            solved.objective_micro,
            label="world optimum objective micro",
        ) != objective_micro:
            raise LR8TrainingSourceError("world solver objective does not replay")
        evidence = _normalized_receipts(
            solved.evidence_receipts, label="world solver evidence receipts"
        )
        admitted = identity not in seen
        attempt = SolveAttempt(
            block=block,
            projection_seed=BLOCK_SEED_PAIRS[block][0],
            world_index=world_index,
            roster=identity,
            objective_micro=objective_micro,
            admitted_unique=admitted,
            request_sha256=request.request_sha256,
            evidence_receipts=evidence,
            evidence_manifest_sha256=canonical_sha256(list(evidence)),
        )
        attempts.append(attempt)
        if not admitted:
            continue
        seen.add(identity)
        try:
            anatomy = tuple(lr8.lineup_anatomy(players, identity))
        except lr8.LR8Error as exc:
            raise LR8TrainingSourceError("candidate anatomy failed") from exc
        _anatomy_payload(anatomy)
        candidates.append(FrozenCandidate(
            season=season,
            week=week,
            roster=identity,
            anatomy_features=anatomy,
            first_source_block=block,
            first_source_world_index=world_index,
            source_occurrences=((block, world_index),),
        ))
    if len(candidates) != UNIQUE_OPTIMA_PER_BLOCK:
        raise LR8TrainingSourceError(
            f"{season}W{week} {block} produced fewer than forty unique "
            f"DK-only optima in {MAX_SOLVE_ATTEMPTS_PER_BLOCK} ordered solves"
        )

    attempt_payload = [{
        "block": attempt.block,
        "projection_seed": attempt.projection_seed,
        "world_index": attempt.world_index,
        "roster": list(attempt.roster),
        "objective_micro": attempt.objective_micro,
        "admitted_unique": attempt.admitted_unique,
        "request_sha256": attempt.request_sha256,
        "evidence_receipts": list(attempt.evidence_receipts),
        "evidence_manifest_sha256": attempt.evidence_manifest_sha256,
    } for attempt in attempts]
    candidate_payload = [list(candidate.roster) for candidate in candidates]
    anatomy_payload = [{
        "roster": list(candidate.roster),
        "features": _anatomy_payload(candidate.anatomy_features),
    } for candidate in candidates]
    legality_payload = [{
        "roster": list(candidate.roster),
        "hard_domain_id": HARD_DOMAIN_ID,
        "dk_classic_legal": True,
        "former_house_rules_applied": [],
    } for candidate in candidates]
    return FrozenBlockSource(
        block=block,
        projection_seed=BLOCK_SEED_PAIRS[block][0],
        source_environment_role_seed_nonoperative=BLOCK_SEED_PAIRS[block][1],
        player_ids=player_ids,
        player_draws=player_draws,
        player_ids_sha256=player_ids_sha256(player_ids),
        player_draws_sha256=array_sha256(player_draws),
        world_order=order,
        world_order_sha256=canonical_sha256(list(order)),
        source_receipts=world_receipts,
        solve_attempts=tuple(attempts),
        solve_attempts_sha256=canonical_sha256(attempt_payload),
        candidates=tuple(candidates),
        candidate_identities_sha256=canonical_sha256(candidate_payload),
        anatomy_sha256=canonical_sha256(anatomy_payload),
        legality_sha256=canonical_sha256(legality_payload),
    )


def _aligned_worlds(
    players: tuple[rw.PlayerSpec, ...],
    replay: tuple[tuple[str, ...], np.ndarray, tuple[dict[str, object], ...]],
) -> tuple[tuple[str, ...], np.ndarray, tuple[dict[str, object], ...]]:
    ids, draws, receipts = replay
    canonical_ids = tuple(player.player_id for player in players)
    if set(ids) != set(canonical_ids):
        raise LR8TrainingSourceError(
            "fresh PIT player universe differs from the audited catalog"
        )
    source_rows = {player_id: index for index, player_id in enumerate(ids)}
    order = [source_rows[player_id] for player_id in canonical_ids]
    aligned = _read_only_float32(draws[order])
    return canonical_ids, aligned, receipts


def _merge_cross_block_candidates(
    values: Sequence[FrozenCandidate],
) -> tuple[FrozenCandidate, ...]:
    order: list[tuple[str, ...]] = []
    first: dict[tuple[str, ...], FrozenCandidate] = {}
    occurrences: dict[tuple[str, ...], list[tuple[str, int]]] = {}
    for candidate in values:
        if candidate.roster not in first:
            first[candidate.roster] = candidate
            order.append(candidate.roster)
        occurrences.setdefault(candidate.roster, []).extend(
            candidate.source_occurrences
        )
    return tuple(
        FrozenCandidate(
            season=first[roster].season,
            week=first[roster].week,
            roster=roster,
            anatomy_features=first[roster].anatomy_features,
            first_source_block=first[roster].first_source_block,
            first_source_world_index=first[roster].first_source_world_index,
            source_occurrences=tuple(occurrences[roster]),
        )
        for roster in order
    )


def _candidate_freeze_payload(candidate: FrozenCandidate) -> dict[str, object]:
    return {
        "season": candidate.season,
        "week": candidate.week,
        "roster": list(candidate.roster),
        "anatomy_features": _anatomy_payload(candidate.anatomy_features),
        "first_source_block": candidate.first_source_block,
        "first_source_world_index": candidate.first_source_world_index,
        "source_occurrences": [list(value) for value in candidate.source_occurrences],
    }


def build_training_source(
    canonical_slates: Sequence[CanonicalSlateSource],
    replay_blocks: Sequence[PITReplayBlock],
    solve_world: WorldSolver,
) -> TrainingSourceBundle:
    """Construct the complete, outcome-blind 35-slate LR8 fit source."""
    if not callable(solve_world):
        raise LR8TrainingSourceError("world solver must be callable")
    sources = tuple(canonical_slates)
    if len(sources) != EXPECTED_SLATES:
        raise LR8TrainingSourceError("canonical source must contain 35 slates")
    source_by_key: dict[
        tuple[int, int],
        tuple[
            CanonicalSlateSource,
            tuple[rw.PlayerSpec, ...],
            tuple[tuple[str, ...], ...],
            tuple[dict[str, object], ...],
            tuple[dict[str, object], ...],
        ],
    ] = {}
    for source in sources:
        normalized = _normalize_canonical_source(source)
        key = (int(source.season), int(source.week))
        if key in source_by_key:
            raise LR8TrainingSourceError("canonical source repeats a slate")
        source_by_key[key] = (source, *normalized)
    if tuple(sorted(source_by_key)) != EXPECTED_SLATE_KEYS:
        raise LR8TrainingSourceError("canonical source slate set differs")

    blocks = tuple(replay_blocks)
    expected_block_keys = {
        (season, block) for season in TARGET_SEASONS for block in BLOCK_ORDER
    }
    if len(blocks) != len(expected_block_keys):
        raise LR8TrainingSourceError("PIT source must contain four replay blocks")
    block_slates: dict[
        tuple[int, str],
        dict[
            tuple[int, int],
            tuple[tuple[str, ...], np.ndarray, tuple[dict[str, object], ...]],
        ],
    ] = {}
    block_objects: dict[tuple[int, str], PITReplayBlock] = {}
    for block in blocks:
        key = (int(block.target_season), str(block.block))
        if key in block_slates:
            raise LR8TrainingSourceError("PIT source repeats a replay block")
        block_slates[key] = _normalize_replay_block(block)
        block_objects[key] = block
    if set(block_slates) != expected_block_keys:
        raise LR8TrainingSourceError("PIT replay block set differs")
    # Simulation seeds may change draws, not the model refit or its inputs.
    for season in TARGET_SEASONS:
        season_blocks = [block_objects[(season, block)] for block in BLOCK_ORDER]
        if len({block.model_fit_input_sha256 for block in season_blocks}) != 1 or len({
            block.model_fit_sha256 for block in season_blocks
        }) != 1 or len({block.model_training_seasons for block in season_blocks}) != 1:
            raise LR8TrainingSourceError(
                "R0/R1 must bind the same target-season PIT model refit"
            )
        normalized_fit_receipts = [canonical_json(list(_normalized_receipts(
            block.fit_source_receipts,
            label=f"{season} {block.block} fit source receipts",
        ))) for block in season_blocks]
        if len(set(normalized_fit_receipts)) != 1:
            raise LR8TrainingSourceError(
                "R0/R1 target-season fit source receipts differ"
            )

    frozen_slates: list[FrozenTrainingSlate] = []
    for season, week in EXPECTED_SLATE_KEYS:
        (
            source,
            players,
            incumbents,
            catalog_receipts,
            incumbent_receipts,
        ) = source_by_key[(season, week)]
        catalog_digest = source.catalog_sha256
        incumbent_digest = source.incumbent_candidates_sha256
        frozen_blocks: list[FrozenBlockSource] = []
        for block in BLOCK_ORDER:
            ids, draws, receipts = _aligned_worlds(
                players, block_slates[(season, block)][(season, week)]
            )
            frozen_blocks.append(_solve_block(
                season=season,
                week=week,
                block=block,
                players=players,
                player_ids=ids,
                player_draws=draws,
                world_receipts=receipts,
                incumbents=incumbents,
                catalog_digest=catalog_digest,
                incumbent_digest=incumbent_digest,
                solve_world=solve_world,
            ))
        pre = tuple(
            candidate
            for block in frozen_blocks
            for candidate in block.candidates
        )
        if len(pre) != PRE_CROSS_BLOCK_CANDIDATES:
            raise AssertionError("R0/R1 pre-dedup candidate budget changed")
        post = _merge_cross_block_candidates(pre)
        if not UNIQUE_OPTIMA_PER_BLOCK <= len(post) <= PRE_CROSS_BLOCK_CANDIDATES:
            raise LR8TrainingSourceError("cross-block candidate union is malformed")
        for candidate in post:
            if candidate.roster in incumbents:
                raise LR8TrainingSourceError(
                    "post-dedup candidate repeats a canonical incumbent"
                )
        frozen_slates.append(FrozenTrainingSlate(
            season=season,
            week=week,
            players=players,
            incumbent_candidates=incumbents,
            catalog_sha256=catalog_digest,
            incumbent_candidates_sha256=incumbent_digest,
            catalog_source_receipts=catalog_receipts,
            incumbent_source_receipts=incumbent_receipts,
            blocks=tuple(frozen_blocks),
            pre_cross_block_candidate_count=len(pre),
            pre_cross_block_sha256=canonical_sha256([
                _candidate_freeze_payload(candidate) for candidate in pre
            ]),
            post_cross_block_candidates=post,
            post_cross_block_sha256=canonical_sha256([
                _candidate_freeze_payload(candidate) for candidate in post
            ]),
            cross_block_duplicates=len(pre) - len(post),
        ))
    return TrainingSourceBundle(
        protocol_id=PROTOCOL_ID,
        version=SOURCE_VERSION,
        canonical_panel_id=CANONICAL_PANEL_ID,
        target_seasons=TARGET_SEASONS,
        slate_keys=EXPECTED_SLATE_KEYS,
        replay_blocks=tuple(
            block_objects[(season, block)]
            for season in TARGET_SEASONS
            for block in BLOCK_ORDER
        ),
        slates=tuple(frozen_slates),
    )


def frozen_anatomy_candidates(
    bundle: TrainingSourceBundle,
) -> tuple[FrozenCandidate, ...]:
    """Rows the later serialized label adapter is allowed to join."""
    if not isinstance(bundle, TrainingSourceBundle) or (
        bundle.protocol_id != PROTOCOL_ID
        or bundle.version != SOURCE_VERSION
        or bundle.canonical_panel_id != CANONICAL_PANEL_ID
        or bundle.target_seasons != TARGET_SEASONS
        or bundle.slate_keys != EXPECTED_SLATE_KEYS
        or len(bundle.slates) != EXPECTED_SLATES
    ):
        raise LR8TrainingSourceError("training-source bundle identity differs")
    return tuple(
        candidate
        for slate in bundle.slates
        for candidate in slate.post_cross_block_candidates
    )


def _fit_block_payload(block: PITReplayBlock) -> dict[str, object]:
    return {
        "target_season": block.target_season,
        "block": block.block,
        "projection_seed": block.projection_seed,
        "source_environment_role_seed_nonoperative": (
            block.source_environment_role_seed_nonoperative
        ),
        "replay_path_id": block.replay_path_id,
        "model_training_seasons": list(block.model_training_seasons),
        "model_fit_input_sha256": block.model_fit_input_sha256,
        "model_fit_sha256": block.model_fit_sha256,
        "fit_source_receipts": list(_normalized_receipts(
            block.fit_source_receipts, label="fit source receipts"
        )),
        "target_player_labels_read": False,
        "candidate_labels_read": False,
        "candidate_world_family": CANDIDATE_WORLD_FAMILY,
        "role_belief_worlds_used": False,
        "role_seed_usage": ROLE_SEED_USAGE,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "later_period_inputs_used": False,
    }


def freeze_training_source(bundle: TrainingSourceBundle) -> dict[str, object]:
    """Serialize the source lock that must exist before any label adapter."""
    rows = frozen_anatomy_candidates(bundle)
    slates_payload: list[dict[str, object]] = []
    for slate in bundle.slates:
        if len(slate.blocks) != len(BLOCK_ORDER) or tuple(
            block.block for block in slate.blocks
        ) != BLOCK_ORDER:
            raise LR8TrainingSourceError("frozen block order differs")
        block_payloads = []
        for block in slate.blocks:
            if len(block.candidates) != UNIQUE_OPTIMA_PER_BLOCK:
                raise LR8TrainingSourceError("frozen block candidate dose differs")
            solve_attempt_payload = [{
                "block": attempt.block,
                "projection_seed": attempt.projection_seed,
                "world_index": attempt.world_index,
                "roster": list(attempt.roster),
                "objective_micro": attempt.objective_micro,
                "admitted_unique": attempt.admitted_unique,
                "request_sha256": attempt.request_sha256,
                "evidence_receipts": list(attempt.evidence_receipts),
                "evidence_manifest_sha256": attempt.evidence_manifest_sha256,
            } for attempt in block.solve_attempts]
            if canonical_sha256(solve_attempt_payload) != block.solve_attempts_sha256:
                raise LR8TrainingSourceError("ordered solve receipt hash differs")
            block_payloads.append({
                "block": block.block,
                "projection_seed": block.projection_seed,
                "source_environment_role_seed_nonoperative": (
                    block.source_environment_role_seed_nonoperative
                ),
                "candidate_world_family": CANDIDATE_WORLD_FAMILY,
                "role_belief_worlds_used": False,
                "role_seed_usage": ROLE_SEED_USAGE,
                "player_ids": list(block.player_ids),
                "player_ids_sha256": block.player_ids_sha256,
                "player_draws": {
                    "dtype": block.player_draws.dtype.str,
                    "shape": list(block.player_draws.shape),
                    "sha256": block.player_draws_sha256,
                },
                "world_order_law": WORLD_ORDER_LAW,
                "world_order_sha256": block.world_order_sha256,
                "source_receipts": list(block.source_receipts),
                "solve_attempt_count": len(block.solve_attempts),
                "ordered_solve_attempts": solve_attempt_payload,
                "ordered_solve_attempts_sha256": block.solve_attempts_sha256,
                "unique_candidates": [
                    _candidate_freeze_payload(candidate)
                    for candidate in block.candidates
                ],
                "unique_candidate_count": len(block.candidates),
                "candidate_identities_sha256": block.candidate_identities_sha256,
                "anatomy_sha256": block.anatomy_sha256,
                "legality_sha256": block.legality_sha256,
            })
        # The ordered pre-dedup body is exactly reconstructible from the two
        # already-frozen block candidate lists.  Audit its hash here without
        # carrying or serializing a redundant third roster table.
        pre_payload = [
            _candidate_freeze_payload(candidate)
            for block in slate.blocks
            for candidate in block.candidates
        ]
        post_payload = [
            _candidate_freeze_payload(candidate)
            for candidate in slate.post_cross_block_candidates
        ]
        if (
            slate.pre_cross_block_candidate_count
            != PRE_CROSS_BLOCK_CANDIDATES
            or len(pre_payload) != slate.pre_cross_block_candidate_count
            or canonical_sha256(pre_payload) != slate.pre_cross_block_sha256
            or canonical_sha256(post_payload) != slate.post_cross_block_sha256
            or slate.cross_block_duplicates != len(pre_payload) - len(post_payload)
        ):
            raise LR8TrainingSourceError("pre/post cross-block freeze differs")
        slates_payload.append({
            "season": slate.season,
            "week": slate.week,
            "catalog": _catalog_payload(slate.players),
            "catalog_sha256": slate.catalog_sha256,
            "catalog_source_receipts": list(slate.catalog_source_receipts),
            "incumbent_candidate_count": len(slate.incumbent_candidates),
            "incumbent_candidates_sha256": slate.incumbent_candidates_sha256,
            "incumbent_source_receipts": list(slate.incumbent_source_receipts),
            "blocks": block_payloads,
            "pre_cross_block_candidate_count": len(pre_payload),
            "pre_cross_block_sha256": slate.pre_cross_block_sha256,
            "post_cross_block_candidate_count": len(post_payload),
            "post_cross_block_candidates": post_payload,
            "post_cross_block_sha256": slate.post_cross_block_sha256,
            "cross_block_duplicates": slate.cross_block_duplicates,
        })
    manifest: dict[str, object] = {
        "protocol_id": PROTOCOL_ID,
        "version": SOURCE_VERSION,
        "canonical_panel_id": CANONICAL_PANEL_ID,
        "target_seasons": list(TARGET_SEASONS),
        "excluded_candidate_source_seasons": [2020, 2022],
        "slate_count": EXPECTED_SLATES,
        "slate_keys": [list(value) for value in EXPECTED_SLATE_KEYS],
        "blocks": [{
            "block": block,
            "projection_seed": BLOCK_SEED_PAIRS[block][0],
            "source_environment_role_seed_nonoperative": (
                BLOCK_SEED_PAIRS[block][1]
            ),
            "worlds": WORLDS_PER_BLOCK,
            "unique_optima": UNIQUE_OPTIMA_PER_BLOCK,
            "max_solve_attempts": MAX_SOLVE_ATTEMPTS_PER_BLOCK,
        } for block in BLOCK_ORDER],
        "pre_cross_block_candidates_per_slate": PRE_CROSS_BLOCK_CANDIDATES,
        "candidate_world_family": CANDIDATE_WORLD_FAMILY,
        "role_belief_worlds_used": False,
        "role_seed_usage": ROLE_SEED_USAGE,
        "hard_domain_id": HARD_DOMAIN_ID,
        "former_house_rules_not_applied": list(FORMER_HOUSE_RULES_NOT_APPLIED),
        "anatomy_feature_columns": list(lr8.ANATOMY_FEATURES),
        "replay_refits": [
            _fit_block_payload(block) for block in bundle.replay_blocks
        ],
        "slates": slates_payload,
        "post_dedup_candidate_rows": len(rows),
        "post_dedup_candidate_rows_sha256": canonical_sha256([
            _candidate_freeze_payload(candidate) for candidate in rows
        ]),
        "old_law_candidate_totals_loaded": False,
        "target_player_labels_read": False,
        "candidate_labels_read": False,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "later_period_inputs_used": False,
        "bigquery_outcome_query_present": False,
        "historical_label_read_licensed": False,
        "historical_execution_licensed": False,
        "prospective_confirmation_licensed": False,
        "production_change_licensed": False,
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    return manifest


def validate_frozen_training_source(
    value: Mapping[str, object],
    *,
    expected_manifest_sha256: str,
) -> dict[str, object]:
    """Externally pinned hash/firewall check for the later label adapter."""
    if not isinstance(value, Mapping):
        raise LR8TrainingSourceError("training source freeze is not an object")
    expected_digest = _strict_sha256(
        expected_manifest_sha256,
        label="externally pinned training source manifest hash",
    )
    manifest = dict(value)
    digest = manifest.pop("manifest_sha256", None)
    observed_digest = _strict_sha256(
        digest, label="training source manifest hash"
    )
    if observed_digest != expected_digest or observed_digest != canonical_sha256(manifest):
        raise LR8TrainingSourceError("training source manifest hash differs")
    if (
        manifest.get("protocol_id") != PROTOCOL_ID
        or manifest.get("version") != SOURCE_VERSION
        or manifest.get("canonical_panel_id") != CANONICAL_PANEL_ID
        or manifest.get("target_seasons") != list(TARGET_SEASONS)
        or manifest.get("slate_count") != EXPECTED_SLATES
        or manifest.get("slate_keys") != [list(value) for value in EXPECTED_SLATE_KEYS]
        or manifest.get("pre_cross_block_candidates_per_slate")
        != PRE_CROSS_BLOCK_CANDIDATES
        or manifest.get("hard_domain_id") != HARD_DOMAIN_ID
        or manifest.get("anatomy_feature_columns") != list(lr8.ANATOMY_FEATURES)
    ):
        raise LR8TrainingSourceError("training source freeze identity differs")
    for label in (
        "old_law_candidate_totals_loaded",
        "target_player_labels_read",
        "candidate_labels_read",
        "role_belief_worlds_used",
        "b1_inputs_used",
        "a2a_inputs_used",
        "later_period_inputs_used",
        "bigquery_outcome_query_present",
        "historical_label_read_licensed",
        "historical_execution_licensed",
        "prospective_confirmation_licensed",
        "production_change_licensed",
    ):
        _literal_bool(manifest.get(label), label=label, expected=False)
    if (
        manifest.get("candidate_world_family") != CANDIDATE_WORLD_FAMILY
        or manifest.get("role_seed_usage") != ROLE_SEED_USAGE
    ):
        raise LR8TrainingSourceError("training source world family differs")
    slates = manifest.get("slates")
    if not isinstance(slates, list) or len(slates) != EXPECTED_SLATES:
        raise LR8TrainingSourceError("training source freeze slates differ")
    manifest["manifest_sha256"] = digest
    return manifest
