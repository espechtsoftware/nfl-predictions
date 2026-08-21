"""Outcome-blind PIT replay adapter for the LR8 2019/2021 source.

The adapter deliberately stops before lineup construction. It invokes the
baseline replay with ``include_actual=False``, aligns its skill-player draws
to the audited canonical catalog, and gives every DST its frozen pre-lock
``mean_projection`` in every world. It performs no warehouse/object-store
access, never calls ``build_slates``, and never reads a target-season label.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
import re
from typing import Final

import numpy as np
import pandas as pd

from nfl_dfs.backtest import replay
from nfl_dfs.research import lr8_training_source as training
from nfl_dfs.research import residual_world_columns as rw


ADAPTER_VERSION: Final = "lr8-outcome-blind-replay-source-v1"
MODEL_BOOST_ROUNDS: Final = 400
EXPECTED_WEEKS: dict[int, tuple[int, ...]] = dict(training.EXPECTED_WEEKS)
TARGET_OUTCOME_COLUMNS: Final = frozenset({
    "actual",
    "actual_score",
    "contest_rank",
    "field_rank",
    "outcome",
    "payout",
    "realized",
    "realized_score",
    "settled_score",
    "was_active",
    "winner",
    "winner_score",
    "y_carries",
    "y_dk_points",
    "y_interceptions",
    "y_pass_attempts",
    "y_pass_tds",
    "y_pass_yards",
    "y_rec_tds",
    "y_rec_yards",
    "y_receptions",
    "y_rush_tds",
    "y_rush_yards",
    "y_targets",
})
_SHA256: Final = re.compile(r"[0-9a-f]{64}")


class LR8ReplaySourceError(ValueError):
    """A fail-closed outcome-blind replay-source violation."""


@dataclass(frozen=True, slots=True)
class ReplaySourceProvenance:
    """Explicit negative provenance assertions for one baseline replay."""

    target_outcome_fields_read: tuple[str, ...] = ()
    target_player_labels_read: bool = False
    candidate_labels_read: bool = False
    build_slates_used: bool = False
    dst_correlated_draws_used: bool = False
    role_belief_worlds_used: bool = False
    b1_inputs_used: bool = False
    a2a_inputs_used: bool = False
    later_period_inputs_used: bool = False


@dataclass(frozen=True, slots=True)
class AuditedReplaySlate:
    """Canonical target-slate catalog plus score-free replay receipts."""

    season: int
    week: int
    players: tuple[rw.PlayerSpec | Mapping[str, object], ...]
    catalog_sha256: str
    dst_mean_projection: Mapping[str, object]
    replay_source_receipts: tuple[Mapping[str, object], ...]


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise LR8ReplaySourceError(f"{label} must be an exact integer")
    result = int(value)
    if result < minimum:
        raise LR8ReplaySourceError(f"{label} must be >= {minimum}")
    return result


def _literal_false(value: object, *, label: str) -> None:
    if not isinstance(value, bool) or value is not False:
        raise LR8ReplaySourceError(f"{label} must be literal False")


def _sha256(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise LR8ReplaySourceError(f"{label} must be a lowercase SHA-256")
    return value


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise LR8ReplaySourceError(f"{label} must be a canonical string")
    return value


def _receipts(
    values: Sequence[Mapping[str, object]], *, label: str,
) -> tuple[dict[str, object], ...]:
    try:
        return training._normalized_receipts(values, label=label)
    except training.LR8TrainingSourceError as exc:
        raise LR8ReplaySourceError(str(exc)) from exc


def _provenance(value: ReplaySourceProvenance) -> ReplaySourceProvenance:
    if not isinstance(value, ReplaySourceProvenance):
        raise LR8ReplaySourceError("replay provenance has the wrong type")
    if value.target_outcome_fields_read != ():
        raise LR8ReplaySourceError(
            "target_outcome_fields_read must be the empty tuple"
        )
    for label in (
        "target_player_labels_read",
        "candidate_labels_read",
        "build_slates_used",
        "dst_correlated_draws_used",
        "role_belief_worlds_used",
        "b1_inputs_used",
        "a2a_inputs_used",
        "later_period_inputs_used",
    ):
        _literal_false(getattr(value, label), label=label)
    return value


def _player(value: rw.PlayerSpec | Mapping[str, object]) -> rw.PlayerSpec:
    if isinstance(value, rw.PlayerSpec):
        player = value
    elif isinstance(value, Mapping):
        if set(value) != training.CANONICAL_CATALOG_FIELDS:
            raise LR8ReplaySourceError("catalog fields differ")
        try:
            player = rw.PlayerSpec.from_mapping(value)
        except (KeyError, TypeError, rw.ResidualWorldError) as exc:
            raise LR8ReplaySourceError("catalog player is malformed") from exc
    else:
        raise LR8ReplaySourceError("catalog player has the wrong type")
    if player.salary <= 0:
        raise LR8ReplaySourceError("catalog salary must be positive")
    return player


def _catalog(
    value: AuditedReplaySlate,
    *,
    target_season: int,
) -> tuple[
    tuple[rw.PlayerSpec, ...],
    dict[str, np.float32],
    tuple[dict[str, object], ...],
]:
    if not isinstance(value, AuditedReplaySlate):
        raise LR8ReplaySourceError("audited replay slate has the wrong type")
    season = _exact_int(value.season, label="catalog season")
    week = _exact_int(value.week, label="catalog week", minimum=1)
    if season != target_season or week not in EXPECTED_WEEKS[target_season]:
        raise LR8ReplaySourceError("catalog slate is outside the exact target")
    players = tuple(sorted(
        (_player(player) for player in value.players),
        key=lambda player: player.player_id,
    ))
    if not players or len({player.player_id for player in players}) != len(players):
        raise LR8ReplaySourceError("catalog player ids are empty or repeat")
    if training.catalog_sha256(players) != _sha256(
        value.catalog_sha256, label="catalog hash"
    ):
        raise LR8ReplaySourceError("catalog hash differs")
    dst_ids = {
        player.player_id for player in players if player.position == "DST"
    }
    skill_ids = {
        player.player_id for player in players if player.position != "DST"
    }
    if not dst_ids or not skill_ids:
        raise LR8ReplaySourceError("catalog needs skill players and DSTs")
    if not isinstance(value.dst_mean_projection, Mapping) or (
        set(value.dst_mean_projection) != dst_ids
    ):
        raise LR8ReplaySourceError(
            "DST mean_projection keys differ from the catalog"
        )
    means: dict[str, np.float32] = {}
    for player_id in sorted(dst_ids):
        raw = value.dst_mean_projection[player_id]
        if isinstance(raw, (bool, np.bool_)) or not isinstance(
            raw, (int, float, np.integer, np.floating)
        ):
            raise LR8ReplaySourceError("DST mean_projection must be numeric")
        number = float(raw)
        if not math.isfinite(number):
            raise LR8ReplaySourceError("DST mean_projection must be finite")
        stored = np.float32(number)
        if not np.isfinite(stored):
            raise LR8ReplaySourceError(
                "DST mean_projection does not fit the float32 world matrix"
            )
        means[player_id] = stored
    return (
        players,
        means,
        _receipts(
            value.replay_source_receipts,
            label=f"{season}W{week} safe replay source receipts",
        ),
    )


def _panel_seasons(panel: pd.DataFrame, *, target_season: int) -> pd.DataFrame:
    if not isinstance(panel, pd.DataFrame) or panel.empty:
        raise LR8ReplaySourceError("mixed PIT panel must be a nonempty DataFrame")
    if "season" not in panel or "week" not in panel:
        raise LR8ReplaySourceError("mixed PIT panel lacks season/week")
    seasons = tuple(sorted({
        _exact_int(value, label="panel season") for value in panel["season"]
    }))
    expected = (*training.MODEL_TRAINING_SEASONS[target_season], target_season)
    if seasons != expected:
        raise LR8ReplaySourceError(
            "mixed PIT panel seasons differ from the exact prior-plus-target set"
        )
    target = panel[panel["season"] == target_season]
    if target.empty:
        raise LR8ReplaySourceError("mixed PIT panel has no target rows")
    weeks = tuple(sorted({
        _exact_int(value, label="target week", minimum=1)
        for value in target["week"]
    }))
    if weeks != EXPECTED_WEEKS[target_season]:
        raise LR8ReplaySourceError("target panel weeks differ")
    poisoned = sorted(
        column for column in TARGET_OUTCOME_COLUMNS
        if column in target and target[column].notna().any()
    )
    if poisoned:
        raise LR8ReplaySourceError(
            f"target outcome fields must be absent or null: {poisoned}"
        )
    return target


def _expected_skill_rows(
    target: pd.DataFrame,
    catalogs: Mapping[tuple[int, int], tuple[rw.PlayerSpec, ...]],
    *,
    target_season: int,
) -> None:
    required = {"gsis_id", "position", "week"}
    if not required <= set(target):
        raise LR8ReplaySourceError("target panel lacks skill alignment columns")
    if target.duplicated(["week", "gsis_id"]).any():
        raise LR8ReplaySourceError("target panel repeats a skill row")
    for week in EXPECTED_WEEKS[target_season]:
        rows = target[target["week"] == week]
        observed = {
            _string(row.gsis_id, label="target player id"):
            _string(row.position, label="target position").upper()
            for row in rows[["gsis_id", "position"]].itertuples(index=False)
        }
        expected = {
            player.player_id: player.position
            for player in catalogs[(target_season, week)]
            if player.position != "DST"
        }
        if observed != expected:
            raise LR8ReplaySourceError(
                f"{target_season}W{week} target skill universe/alignment differs"
            )


def _replay_output(
    value: object,
    *,
    target_season: int,
) -> tuple[pd.DataFrame, np.ndarray]:
    if not isinstance(value, tuple) or len(value) != 2:
        raise LR8ReplaySourceError("score-free replay did not return frame/draws")
    frame, raw_draws = value
    if not isinstance(frame, pd.DataFrame):
        raise LR8ReplaySourceError("score-free replay frame has the wrong type")
    if "actual" in frame:
        raise LR8ReplaySourceError("score-free replay returned actual")
    required = {"gsis_id", "season", "week", "position"}
    if not required <= set(frame):
        raise LR8ReplaySourceError("score-free replay lacks alignment columns")
    if frame.duplicated(["week", "gsis_id"]).any():
        raise LR8ReplaySourceError("score-free replay repeats a skill row")
    if any(
        _exact_int(value, label="replay season") != target_season
        for value in frame["season"]
    ):
        raise LR8ReplaySourceError("score-free replay season differs")
    draws = np.asarray(raw_draws)
    if (
        draws.dtype != np.float32
        or draws.shape != (len(frame), training.WORLDS_PER_BLOCK)
        or not np.isfinite(draws).all()
    ):
        raise LR8ReplaySourceError(
            "score-free replay draws must be aligned finite float32 x 10000"
        )
    return frame.reset_index(drop=True), draws


def materialize_baseline_replay_block(
    panel: pd.DataFrame,
    audited_slates: Sequence[AuditedReplaySlate],
    *,
    target_season: int,
    block: str,
    model_fit_input_sha256: str,
    model_fit_sha256: str,
    fit_source_receipts: Sequence[Mapping[str, object]],
    provenance: ReplaySourceProvenance,
) -> training.PITReplayBlock:
    """Materialize one exact R0/R1 baseline block without target outcomes."""
    season = _exact_int(target_season, label="target season")
    if season not in training.TARGET_SEASONS:
        raise LR8ReplaySourceError("target season must be 2019 or 2021")
    if not isinstance(block, str) or block not in training.BLOCK_SEED_PAIRS:
        raise LR8ReplaySourceError("block must be R0 or R1")
    _provenance(provenance)
    target = _panel_seasons(panel, target_season=season)

    inputs = tuple(audited_slates)
    if len(inputs) != len(EXPECTED_WEEKS[season]):
        raise LR8ReplaySourceError("audited catalog slate count differs")
    catalogs: dict[tuple[int, int], tuple[rw.PlayerSpec, ...]] = {}
    dst_means: dict[tuple[int, int], dict[str, np.float32]] = {}
    receipts: dict[tuple[int, int], tuple[dict[str, object], ...]] = {}
    for value in inputs:
        key = (
            _exact_int(value.season, label="catalog season"),
            _exact_int(value.week, label="catalog week", minimum=1),
        )
        if key in catalogs:
            raise LR8ReplaySourceError("audited catalog repeats a slate")
        players, means, source_receipts = _catalog(
            value, target_season=season
        )
        catalogs[key] = players
        dst_means[key] = means
        receipts[key] = source_receipts
    expected_keys = {(season, week) for week in EXPECTED_WEEKS[season]}
    if set(catalogs) != expected_keys:
        raise LR8ReplaySourceError("audited catalog slate keys differ")
    _expected_skill_rows(target, catalogs, target_season=season)

    projection_seed, nonoperative_role_seed = training.BLOCK_SEED_PAIRS[block]
    projected, skill_draws = _replay_output(
        replay.replay_projections(
            panel,
            season=season,
            n_sims=training.WORLDS_PER_BLOCK,
            num_boost_round=MODEL_BOOST_ROUNDS,
            seed=projection_seed,
            widen=True,
            return_draws=True,
            include_actual=False,
        ),
        target_season=season,
    )

    replay_slates: list[training.ReplaySlateWorlds] = []
    for week in EXPECTED_WEEKS[season]:
        key = (season, week)
        frame = projected[projected["week"] == week]
        indices = frame.index.to_numpy(dtype=np.int64)
        observed = {
            _string(row.gsis_id, label="replay player id"): (
                index,
                _string(row.position, label="replay position").upper(),
            )
            for index, row in zip(
                indices,
                frame[["gsis_id", "position"]].itertuples(index=False),
                strict=True,
            )
        }
        expected_skill = {
            player.player_id: player.position
            for player in catalogs[key]
            if player.position != "DST"
        }
        if {
            player_id: position for player_id, (_, position) in observed.items()
        } != expected_skill:
            raise LR8ReplaySourceError(
                f"{season}W{week} replay skill universe/alignment differs"
            )

        ordered_players = catalogs[key]
        player_ids = tuple(player.player_id for player in ordered_players)
        rows: list[np.ndarray] = []
        for player in ordered_players:
            if player.position == "DST":
                rows.append(np.full(
                    training.WORLDS_PER_BLOCK,
                    dst_means[key][player.player_id],
                    dtype=np.float32,
                ))
            else:
                source_index, position = observed[player.player_id]
                if position != player.position:
                    raise LR8ReplaySourceError(
                        f"{season}W{week} replay player position differs"
                    )
                rows.append(np.array(
                    skill_draws[source_index], dtype=np.float32, copy=True,
                ))
        combined = np.ascontiguousarray(np.stack(rows), dtype=np.float32)
        combined.flags.writeable = False
        replay_slates.append(training.ReplaySlateWorlds(
            season=season,
            week=week,
            player_ids=player_ids,
            player_draws=combined,
            player_ids_sha256=training.player_ids_sha256(player_ids),
            player_draws_sha256=training.array_sha256(combined),
            source_receipts=receipts[key],
            target_outcome_fields_read=(),
        ))

    return training.PITReplayBlock(
        target_season=season,
        block=block,
        projection_seed=projection_seed,
        source_environment_role_seed_nonoperative=nonoperative_role_seed,
        replay_path_id=training.PIT_REPLAY_PATH_ID,
        model_training_seasons=training.MODEL_TRAINING_SEASONS[season],
        model_fit_input_sha256=_sha256(
            model_fit_input_sha256, label="model fit input hash"
        ),
        model_fit_sha256=_sha256(model_fit_sha256, label="model fit hash"),
        fit_source_receipts=_receipts(
            fit_source_receipts, label="fit source receipts"
        ),
        slates=tuple(replay_slates),
        target_player_labels_read=False,
        candidate_labels_read=False,
        candidate_world_family=training.CANDIDATE_WORLD_FAMILY,
        role_belief_worlds_used=False,
        b1_inputs_used=False,
        a2a_inputs_used=False,
        later_period_inputs_used=False,
    )
