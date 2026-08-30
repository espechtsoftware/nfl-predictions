"""No-query PIT replay adapter for the paired boom-first historical core.

This module is the production-shaped bridge between frozen, point-in-time
historical inputs and :mod:`boom_first_historical_paired_v1`.  It deliberately
does not own a warehouse or object-store loader.  A caller must inject:

* the ordinary mixed training/target replay panel, with all target-season
  outcomes absent or null (prior-season component labels remain available for
  walk-forward fitting),
* pre-lock market points and TabPFN marginal rows,
* DST salaries plus already point-in-time trailing/QB/Vegas inputs, never a
  current-week DST score, and
* one immutable composite source identity per development slate.

The adapter validates and freezes those identities but deliberately cannot
dereference them; the upstream materializer remains responsible for proving
that each identity hashes the injected bytes.  Without an explicit immutable
panel authority the paired core marks the result as a fixture/smoke receipt,
not a Gate-H1-complete panel.

For every registered R0--R4 seed pair the adapter reuses the current replay
model, market blend, final-served scales and slate construction.  It then calls
the native candidate generator directly under the exact policy environment,
captures its :class:`~nfl_dfs.backtest.engine.CandidateBatch`, and performs no
candidate persistence.  Baseline and role projections are cached per seed so
the control (160 leverage / 40 boom) and treatment (40 leverage / 160 boom)
consume byte-identical player worlds.

There is intentionally no realized-score API here.  Grading stays behind the
separate post-freeze boundary in ``boom_first_historical_paired_v1``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
import os
import threading
from typing import Final

import numpy as np
import pandas as pd

from ..backtest import engine, replay
from ..inference.production_policy import ADOPTED_CLASSIC_POLICY
from . import boom_first_historical_paired_v1 as paired


ADAPTER_VERSION: Final = "boom-first-historical-pit-replay-adapter/v1"
MODEL_BOOST_ROUNDS: Final = 400
DEVELOPMENT_SEASONS: Final = frozenset({2023, 2024})
SEALED_SEASONS: Final = frozenset({2025})

_TARGET_OUTCOME_FIELDS: Final = frozenset({
    "actual",
    "actual_score",
    "contest_rank",
    "dk_points",
    "dst_dk_points",
    "field_rank",
    "final_score",
    "outcome",
    "payout",
    "realized",
    "realized_score",
    "roi",
    "settled_score",
    "was_active",
    "winner",
    "winner_score",
})
_ENVIRONMENT_LOCK = threading.RLock()
_EXTRA_SCORE_ENV_KEYS: Final = frozenset({
    # coldstart.py reads this outside engine's registry. It must be absent for
    # the adopted policy and cannot leak from an interactive shell.
    "DRAFT_PRIORS",
    # Per-seed provenance used by the live multi-seed path.
    "MULTISEED_SOURCE_LABEL",
})


class BoomFirstReplayAdapterError(ValueError):
    """A score-blind replay input or production-parity contract failed."""


@dataclass(frozen=True, slots=True)
class PITReplaySeasonInputs:
    """Injected score-blind real-data inputs for one development season.

    ``dst_prelock`` columns are ``season, week, team, opp, salary,
    dst_points_l4`` plus optional ``opp_implied`` and ``opp_qb_starts``.
    ``dst_points_l4`` must itself have been frozen from weeks strictly before
    the row's week.  No score-bearing DST column is accepted.
    """

    season: int
    panel: pd.DataFrame
    dst_prelock: pd.DataFrame
    market_points: pd.DataFrame
    tabpfn_marginals: pd.DataFrame
    source_identity_by_slate: Mapping[str, Mapping[str, object]]


@dataclass(frozen=True, slots=True)
class _ValidatedSeason:
    season: int
    panel: pd.DataFrame
    dst_projected: pd.DataFrame
    market_points: pd.DataFrame
    tabpfn_marginals: pd.DataFrame
    source_identity_by_slate: dict[str, Mapping[str, object]]


@dataclass(frozen=True, slots=True)
class _SeedReplay:
    slates: Mapping[str, pd.DataFrame]
    belief_slates: Mapping[str, pd.DataFrame]
    draws: np.ndarray
    belief_draws: np.ndarray


def _is_outcome_field(column: object) -> bool:
    name = str(column).strip().lower()
    return (
        name in _TARGET_OUTCOME_FIELDS
        or name.startswith("y_")
        or name.startswith("realized_")
        or name.endswith("_actual")
    )


def _outcome_fields(frame: pd.DataFrame) -> tuple[str, ...]:
    return tuple(sorted(str(column) for column in frame if _is_outcome_field(column)))


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise BoomFirstReplayAdapterError(f"{label} must be an exact integer")
    result = int(value)
    if result < minimum:
        raise BoomFirstReplayAdapterError(f"{label} must be >= {minimum}")
    return result


def _numeric_column(
    frame: pd.DataFrame,
    column: str,
    *,
    allow_missing: bool,
) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce")
    if not allow_missing and values.isna().any():
        raise BoomFirstReplayAdapterError(f"{column} contains missing values")
    finite = np.isfinite(values.dropna().to_numpy(dtype=float))
    if not finite.all():
        raise BoomFirstReplayAdapterError(f"{column} contains non-finite values")
    return values


def _weeks(frame: pd.DataFrame, *, label: str) -> tuple[int, ...]:
    if "week" not in frame.columns:
        raise BoomFirstReplayAdapterError(f"{label} lacks week")
    return tuple(sorted({
        _exact_int(value, label=f"{label} week", minimum=1)
        for value in frame["week"].tolist()
    }))


def _validate_source_slates(
    season: int,
    value: Mapping[str, Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    if not isinstance(value, Mapping) or not value:
        raise BoomFirstReplayAdapterError("source identities are empty")
    result: dict[str, Mapping[str, object]] = {}
    for raw_slate_id, identity in value.items():
        slate_id = str(raw_slate_id)
        prefix = f"{season}-w"
        if not slate_id.startswith(prefix) or len(slate_id) != len(prefix) + 2:
            raise BoomFirstReplayAdapterError(
                "source slate IDs must be canonical season-week")
        try:
            week = int(slate_id[-2:])
        except ValueError as exc:
            raise BoomFirstReplayAdapterError(
                "source slate IDs must be canonical season-week") from exc
        if not 1 <= week <= 18 or slate_id != f"{season}-w{week:02d}":
            raise BoomFirstReplayAdapterError(
                "source slate IDs must be canonical season-week")
        if not isinstance(identity, Mapping):
            raise BoomFirstReplayAdapterError("source identity is not a mapping")
        result[slate_id] = dict(identity)
    return result


def _validate_panel(
    panel: pd.DataFrame,
    *,
    season: int,
    expected_weeks: tuple[int, ...],
) -> pd.DataFrame:
    if not isinstance(panel, pd.DataFrame) or panel.empty:
        raise BoomFirstReplayAdapterError("mixed replay panel is empty")
    required = {
        "season", "week", "gsis_id", "position", "team", "opponent",
        "game_id", "salary",
    }
    if missing := required - set(panel.columns):
        raise BoomFirstReplayAdapterError(
            "mixed replay panel lacks " + ", ".join(sorted(missing)))
    safe = panel.copy(deep=True)
    seasons = pd.to_numeric(safe["season"], errors="raise").astype(int)
    if seasons.max() != season or (seasons > season).any():
        raise BoomFirstReplayAdapterError(
            "mixed replay panel includes a later or wrong target season")
    if not (seasons < season).any():
        raise BoomFirstReplayAdapterError(
            "mixed replay panel lacks prior-season model-fit rows")
    target = safe.loc[seasons == season]
    if target.empty or _weeks(target, label="target panel") != expected_weeks:
        raise BoomFirstReplayAdapterError("target panel weeks differ")
    if target.duplicated(["week", "gsis_id"]).any():
        raise BoomFirstReplayAdapterError("target panel repeats a player-week")
    poisoned = [
        column for column in _outcome_fields(target)
        if target[column].notna().any()
    ]
    if poisoned:
        raise BoomFirstReplayAdapterError(
            "target outcome fields must be absent or null: "
            + ", ".join(poisoned))
    return safe


def _validate_dst_prelock(
    frame: pd.DataFrame,
    *,
    season: int,
    expected_weeks: tuple[int, ...],
) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise BoomFirstReplayAdapterError("pre-lock DST frame is empty")
    forbidden = _outcome_fields(frame)
    if forbidden:
        raise BoomFirstReplayAdapterError(
            "pre-lock DST frame contains outcome columns: "
            + ", ".join(forbidden))
    required = {"season", "week", "team", "opp", "salary", "dst_points_l4"}
    if missing := required - set(frame.columns):
        raise BoomFirstReplayAdapterError(
            "pre-lock DST frame lacks " + ", ".join(sorted(missing)))
    dst = frame.copy(deep=True)
    seasons = pd.to_numeric(dst["season"], errors="raise").astype(int)
    if set(seasons.tolist()) != {season}:
        raise BoomFirstReplayAdapterError("pre-lock DST season differs")
    if _weeks(dst, label="pre-lock DST") != expected_weeks:
        raise BoomFirstReplayAdapterError("pre-lock DST weeks differ")
    if dst.duplicated(["week", "team"]).any():
        raise BoomFirstReplayAdapterError("pre-lock DST repeats a team-week")
    salary = _numeric_column(dst, "salary", allow_missing=False)
    if (salary <= 0).any():
        raise BoomFirstReplayAdapterError("pre-lock DST salary must be positive")
    trailing = _numeric_column(dst, "dst_points_l4", allow_missing=True)
    opp_implied = (
        _numeric_column(dst, "opp_implied", allow_missing=True)
        if "opp_implied" in dst else pd.Series(np.nan, index=dst.index)
    )
    opp_qb_starts = (
        _numeric_column(dst, "opp_qb_starts", allow_missing=True)
        if "opp_qb_starts" in dst else pd.Series(np.nan, index=dst.index)
    )
    from ..inference.dst_projections import model_projection

    projection = model_projection(opp_implied, trailing, opp_qb_starts)
    if not np.isfinite(projection.to_numpy(dtype=float)).all():
        raise BoomFirstReplayAdapterError("pre-lock DST projection is non-finite")
    result = pd.DataFrame({
        "season": seasons,
        "week": pd.to_numeric(dst["week"], errors="raise").astype(int),
        "team": dst["team"].astype(str),
        "opp": dst["opp"].astype(str),
        "salary": salary.astype(int),
        "proj": projection.astype(float),
    })
    if (result.team.str.len() == 0).any() or (result.opp.str.len() == 0).any():
        raise BoomFirstReplayAdapterError("pre-lock DST team/opponent is empty")
    result["id"] = "DST_" + result.team
    result["name"] = result.team + " DST"
    result["pos"] = "DST"
    return result.sort_values(["season", "week", "team"]).reset_index(drop=True)


def _validate_market(
    frame: pd.DataFrame,
    *,
    season: int,
    expected_weeks: tuple[int, ...],
) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame):
        raise BoomFirstReplayAdapterError("market points are not a DataFrame")
    required = {"season", "week", "gsis_id", "market_points"}
    if missing := required - set(frame.columns):
        raise BoomFirstReplayAdapterError(
            "market points lack " + ", ".join(sorted(missing)))
    forbidden = _outcome_fields(frame)
    if forbidden:
        raise BoomFirstReplayAdapterError(
            "market points contain outcome columns: " + ", ".join(forbidden))
    market = frame[
        ["season", "week", "gsis_id", "market_points"]
    ].copy(deep=True)
    if not market.empty:
        seasons = pd.to_numeric(market["season"], errors="raise").astype(int)
        if set(seasons.tolist()) != {season}:
            raise BoomFirstReplayAdapterError("market season differs")
        if not set(_weeks(market, label="market points")) <= set(expected_weeks):
            raise BoomFirstReplayAdapterError("market weeks differ")
        if market.duplicated(["season", "week", "gsis_id"]).any():
            raise BoomFirstReplayAdapterError("market points repeat a player-week")
        market["market_points"] = _numeric_column(
            market, "market_points", allow_missing=True)
    return market.sort_values(["season", "week", "gsis_id"]).reset_index(drop=True)


def _validate_tabpfn(
    frame: pd.DataFrame,
    *,
    season: int,
) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise BoomFirstReplayAdapterError("TabPFN marginal cache is empty")
    required = {"season", "week", "gsis_id"}
    if missing := required - set(frame.columns):
        raise BoomFirstReplayAdapterError(
            "TabPFN marginal cache lacks " + ", ".join(sorted(missing)))
    forbidden = _outcome_fields(frame)
    if forbidden:
        raise BoomFirstReplayAdapterError(
            "TabPFN marginal cache contains outcome columns: "
            + ", ".join(forbidden))
    quantiles = sorted(
        column for column in frame
        if str(column).startswith("q") and str(column)[1:].isdigit()
    )
    if len(quantiles) < 2:
        raise BoomFirstReplayAdapterError(
            "TabPFN marginal cache needs at least two quantiles")
    cache = frame.copy(deep=True)
    seasons = pd.to_numeric(cache["season"], errors="raise").astype(int)
    if set(seasons.tolist()) != {season}:
        raise BoomFirstReplayAdapterError("TabPFN marginal season differs")
    if cache.duplicated(["season", "week", "gsis_id"]).any():
        raise BoomFirstReplayAdapterError(
            "TabPFN marginal cache repeats a player-week")
    for column in quantiles:
        cache[column] = _numeric_column(cache, column, allow_missing=True)
    return cache.sort_values(["season", "week", "gsis_id"]).reset_index(drop=True)


def _validated_season(value: PITReplaySeasonInputs) -> _ValidatedSeason:
    if not isinstance(value, PITReplaySeasonInputs):
        raise BoomFirstReplayAdapterError("season input has the wrong type")
    season = _exact_int(value.season, label="input season")
    if season in SEALED_SEASONS or season not in DEVELOPMENT_SEASONS:
        raise BoomFirstReplayAdapterError(
            "adapter permits only development seasons 2023 and 2024")
    identities = _validate_source_slates(season, value.source_identity_by_slate)
    expected_weeks = tuple(sorted(int(slate_id[-2:]) for slate_id in identities))
    return _ValidatedSeason(
        season=season,
        panel=_validate_panel(
            value.panel, season=season, expected_weeks=expected_weeks),
        dst_projected=_validate_dst_prelock(
            value.dst_prelock, season=season, expected_weeks=expected_weeks),
        market_points=_validate_market(
            value.market_points, season=season, expected_weeks=expected_weeks),
        tabpfn_marginals=_validate_tabpfn(
            value.tabpfn_marginals, season=season),
        source_identity_by_slate=identities,
    )


@contextmanager
def _isolated_replay_environment(environment: Mapping[str, str]):
    """Temporarily replace every registered score lever, then restore it.

    Historical replay still has legacy process-environment reads.  This
    single-thread-only adapter isolates them while the candidate engine also
    receives the same mapping explicitly as ``policy_env``.
    """

    if not isinstance(environment, Mapping):
        raise BoomFirstReplayAdapterError("policy environment is not a mapping")
    values = {str(key): str(value) for key, value in environment.items()}
    managed = set(engine._lever_keys) | set(_EXTRA_SCORE_ENV_KEYS) | set(values)
    with _ENVIRONMENT_LOCK:
        previous = {key: os.environ.get(key) for key in managed}
        try:
            for key in managed:
                os.environ.pop(key, None)
            os.environ.update(values)
            yield
        finally:
            for key in managed:
                os.environ.pop(key, None)
            for key, old in previous.items():
                if old is not None:
                    os.environ[key] = old


def _slate_id(frame: pd.DataFrame) -> str:
    if frame.empty or "season" not in frame or "week" not in frame:
        raise BoomFirstReplayAdapterError("replay slate lacks season/week")
    seasons = set(pd.to_numeric(frame.season, errors="raise").astype(int))
    weeks = set(pd.to_numeric(frame.week, errors="raise").astype(int))
    if len(seasons) != 1 or len(weeks) != 1:
        raise BoomFirstReplayAdapterError("replay slate spans multiple weeks")
    return f"{next(iter(seasons))}-w{next(iter(weeks)):02d}"


def _assert_score_blind_frame(frame: pd.DataFrame, *, label: str) -> None:
    forbidden = _outcome_fields(frame)
    if forbidden:
        raise BoomFirstReplayAdapterError(
            f"{label} contains outcome columns: " + ", ".join(forbidden))
    if frame.empty or frame.id.astype(str).duplicated().any():
        raise BoomFirstReplayAdapterError(f"{label} player IDs are empty or repeat")


class ProductionReplayNativeBookBuilder:
    """Callable native-book builder consumed by the paired historical core."""

    def __init__(self, inputs: Sequence[PITReplaySeasonInputs]):
        supplied = tuple(inputs)
        if not supplied:
            raise BoomFirstReplayAdapterError("historical replay inputs are empty")
        validated = [_validated_season(value) for value in supplied]
        if len({value.season for value in validated}) != len(validated):
            raise BoomFirstReplayAdapterError("historical replay repeats a season")
        self._seasons = {value.season: value for value in validated}
        self._cache: dict[tuple[int, str, int, int], _SeedReplay] = {}

    def development_slates(self) -> tuple[paired.DevelopmentSlate, ...]:
        rows: list[paired.DevelopmentSlate] = []
        for season in sorted(self._seasons):
            source = self._seasons[season].source_identity_by_slate
            for slate_id in sorted(source):
                rows.append(paired.DevelopmentSlate(
                    season=season,
                    week=int(slate_id[-2:]),
                    slate_id=slate_id,
                    source_identity=source[slate_id],
                ))
        return tuple(rows)

    @staticmethod
    def _seed_environment(
        environment: Mapping[str, str],
        *,
        seed_label: str,
        projection_seed: int,
        role_seed: int,
    ) -> dict[str, str]:
        result = {str(key): str(value) for key, value in environment.items()}
        result.update({
            "REPLAY_PROJECTION_SEED": str(projection_seed),
            "ROLE_BELIEF_SEED": str(role_seed),
            "MULTISEED_SOURCE_LABEL": seed_label,
        })
        return result

    @staticmethod
    def _validate_seed(
        seed_label: str,
        projection_seed: int,
        role_seed: int,
    ) -> None:
        policy = ADOPTED_CLASSIC_POLICY
        expected = {
            f"R{index}": (int(projection), int(role))
            for index, (projection, role) in enumerate(policy.multiseed_seed_pairs)
        }
        if seed_label not in expected or expected[seed_label] != (
            projection_seed, role_seed
        ):
            raise BoomFirstReplayAdapterError("seed pair differs from R0--R4")

    def _materialize_seed(
        self,
        data: _ValidatedSeason,
        *,
        seed_label: str,
        projection_seed: int,
        role_seed: int,
        environment: Mapping[str, str],
    ) -> _SeedReplay:
        key = (data.season, seed_label, projection_seed, role_seed)
        if key in self._cache:
            return self._cache[key]
        worlds = int(environment.get("MULTISEED_WORLDS_PER_BLOCK", "0") or 0)
        if worlds != ADOPTED_CLASSIC_POLICY.multiseed_worlds_per_block:
            raise BoomFirstReplayAdapterError("worlds per R0--R4 block differ")
        if environment.get("MODEL_ENSEMBLE") != "1":
            raise BoomFirstReplayAdapterError("historical reproduction requires K=1")
        with _isolated_replay_environment(environment):
            projected, draws = replay.replay_projections(
                data.panel,
                data.season,
                n_sims=worlds,
                num_boost_round=MODEL_BOOST_ROUNDS,
                seed=projection_seed,
                widen=True,
                return_draws=True,
                include_actual=False,
                tabpfn_cache_rows=data.tabpfn_marginals,
            )
            belief, belief_draws = replay.role_belief_projections(
                data.panel,
                data.season,
                n_sims=worlds,
                num_boost_round=MODEL_BOOST_ROUNDS,
                include_actual=False,
                tabpfn_cache_rows=data.tabpfn_marginals,
            )
            if belief is None or belief_draws is None:
                raise BoomFirstReplayAdapterError("role12 replay is unavailable")
            projected, draws, _ = replay._market_blend_worlds(
                projected,
                np.asarray(draws, dtype=np.float32),
                data.market_points,
                float(environment["BLEND_MODEL_WEIGHT"]),
            )
            belief, belief_draws, _ = replay._market_blend_worlds(
                belief,
                np.asarray(belief_draws, dtype=np.float32),
                data.market_points,
                float(environment["BLEND_MODEL_WEIGHT"]),
            )
            draws = replay.apply_served_tail_scale(
                draws, projected.position, env=dict(environment))
            draws = replay.apply_served_position_scales(
                draws, projected.position, env=dict(environment))
            belief_draws = replay.apply_served_tail_scale(
                belief_draws, belief.position, env=dict(environment))
            belief_draws = replay.apply_served_position_scales(
                belief_draws, belief.position, env=dict(environment))
            slates = replay.build_slates(
                projected,
                data.dst_projected,
                include_actual=False,
                dst_preprojected=True,
            )
            belief_slates = replay.build_slates(
                belief,
                data.dst_projected,
                include_actual=False,
                dst_preprojected=True,
            )

        by_id = {_slate_id(frame): frame for frame in slates}
        belief_by_id = {_slate_id(frame): frame for frame in belief_slates}
        expected = set(data.source_identity_by_slate)
        if set(by_id) != expected or set(belief_by_id) != expected:
            raise BoomFirstReplayAdapterError("replay slate keys differ from sources")
        for slate_id in sorted(expected):
            base = by_id[slate_id].reset_index(drop=True)
            alternate = belief_by_id[slate_id].reset_index(drop=True)
            _assert_score_blind_frame(base, label=f"{slate_id} baseline slate")
            _assert_score_blind_frame(
                alternate, label=f"{slate_id} role-belief slate")
            if base.id.astype(str).tolist() != alternate.id.astype(str).tolist():
                raise BoomFirstReplayAdapterError(
                    f"{slate_id} baseline/role player order differs")
            by_id[slate_id] = base
            belief_by_id[slate_id] = alternate
        values = np.asarray(draws, dtype=np.float32)
        alternate_values = np.asarray(belief_draws, dtype=np.float32)
        if (
            values.shape != (len(projected), worlds)
            or alternate_values.shape != (len(belief), worlds)
            or not np.isfinite(values).all()
            or not np.isfinite(alternate_values).all()
        ):
            raise BoomFirstReplayAdapterError("replay player worlds differ")
        result = _SeedReplay(
            slates=by_id,
            belief_slates=belief_by_id,
            draws=values,
            belief_draws=alternate_values,
        )
        self._cache[key] = result
        return result

    def __call__(
        self,
        slate: paired.DevelopmentSlate,
        arm: str,
        seed_label: str,
        projection_seed: int,
        role_seed: int,
        policy_environment: Mapping[str, str],
    ) -> engine.CandidateBatch:
        if not isinstance(slate, paired.DevelopmentSlate):
            raise BoomFirstReplayAdapterError("development slate has the wrong type")
        if arm not in paired.ARM_ORDER:
            raise BoomFirstReplayAdapterError("boom-first arm differs")
        projection = _exact_int(projection_seed, label="projection seed")
        role = _exact_int(role_seed, label="role seed")
        self._validate_seed(seed_label, projection, role)
        if slate.season not in self._seasons:
            raise BoomFirstReplayAdapterError("development slate season is unavailable")
        data = self._seasons[slate.season]
        if slate.slate_id not in data.source_identity_by_slate:
            raise BoomFirstReplayAdapterError("development slate source is unavailable")
        environment = self._seed_environment(
            policy_environment,
            seed_label=seed_label,
            projection_seed=projection,
            role_seed=role,
        )
        replay_seed = self._materialize_seed(
            data,
            seed_label=seed_label,
            projection_seed=projection,
            role_seed=role,
            environment=environment,
        )
        base = replay_seed.slates[slate.slate_id].copy(deep=True)
        belief = replay_seed.belief_slates[slate.slate_id].copy(deep=True)
        captures: list[engine.CandidateBatch] = []
        construction = ADOPTED_CLASSIC_POLICY.construction_preset()
        stack = construction.stack
        with _isolated_replay_environment(environment):
            role_row_draws = engine._row_draws(
                belief,
                replay_seed.belief_draws,
                env=environment,
            )
            role_world_receipt = paired.role_player_world_receipt(
                tuple(belief.id.astype(str)),
                role_row_draws,
            )
            engine.tail_select_lineups(
                base,
                base.to_dict("records"),
                replay_seed.draws,
                tail_line=paired.TAIL_LINE,
                n_entries=paired.ENTRIES,
                stack=stack,
                construction_preset_receipt=construction.receipt(),
                objective_col="proj_tourney",
                candidate_multiple=int(environment["CAND_MULT"]),
                candidate_generation_entries=int(
                    environment["MULTISEED_CANDIDATE_ENTRY_BASIS"]),
                n_boom_solves=int(environment["N_BOOM"]),
                n_game_stacks=int(environment["N_GAMESTACK"]),
                cand_log_table="",
                cand_log_async=False,
                cand_log_required=False,
                belief_slate=belief,
                belief_draws=replay_seed.belief_draws,
                policy_env=environment,
                candidate_capture=captures.append,
            )
        if len(captures) != 1:
            raise BoomFirstReplayAdapterError(
                f"{slate.slate_id}/{arm}/{seed_label} produced "
                f"{len(captures)} native books")
        batch = captures[0]
        try:
            engine._validate_candidate_batch(batch)
        except (TypeError, ValueError) as exc:
            raise BoomFirstReplayAdapterError("native candidate batch differs") from exc
        row_frame = pd.DataFrame(batch.player_rows)
        _assert_score_blind_frame(
            row_frame, label=f"{slate.slate_id}/{arm}/{seed_label} candidate rows")
        for index, lineup in enumerate(batch.candidates):
            forbidden = sorted({
                key
                for player in lineup.players
                for key in player
                if _is_outcome_field(key)
            })
            if forbidden:
                raise BoomFirstReplayAdapterError(
                    f"candidate {index} contains outcome fields: "
                    + ", ".join(forbidden))
        return replace(batch, metadata={
            **batch.metadata,
            "role_player_world_receipt": role_world_receipt,
            "historical_replay_adapter": {
                "version": ADAPTER_VERSION,
                "season": slate.season,
                "week": slate.week,
                "slate_id": slate.slate_id,
                "arm": arm,
                "seed_label": seed_label,
                "projection_seed": projection,
                "role_seed": role,
                "model_ensemble": 1,
                "worlds": int(replay_seed.draws.shape[1]),
                "uses_target_slate_outcomes": False,
                "prior_only_historical_labels_may_train_later_targets": True,
                "candidate_persistence": False,
            },
        })


def build_score_blind_panel_from_pit_inputs(
    inputs: Sequence[PITReplaySeasonInputs],
    *,
    panel_id: str,
    code_sha: str,
    image_digest: str,
    panel_authority: paired.DevelopmentPanelAuthority | None = None,
) -> dict[str, object]:
    """Run the pure paired core through the production-shaped replay bridge."""

    builder = ProductionReplayNativeBookBuilder(inputs)
    return paired.build_score_blind_development_panel(
        builder.development_slates(),
        builder,
        panel_id=panel_id,
        code_sha=code_sha,
        image_digest=image_digest,
        panel_authority=panel_authority,
    )
