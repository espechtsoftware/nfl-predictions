"""PIT-safe SIS ASOE target-center treatment for final-served replay."""

from __future__ import annotations

import functools
import hashlib
import logging
import os

import numpy as np
import pandas as pd

from ..analysis import sis_asoe_allocation as allocation
from ..ingest import sis_asoe
from ..models.simulate import (
    _game_team_unit_codes,
    canonicalize_simulation_components,
)


log = logging.getLogger(__name__)

ENV_FLAG = "SIS_ASOE_TARGET_ALLOCATION"
ENV_BETA = "SIS_ASOE_BETA"
FROZEN_BETA = 0.07771181538347656
FP_SOURCE_RUN = "20260813T202926Z__same-season-alignment-last-four-v1"
SIS_SOURCE_RUN = "sis-team-pass-defense-asoe-v1"
EXPECTED_PLAYER_ROWS = 16_482
EXPECTED_TEAM_ROWS = 1_792
EXPECTED_SIS_ROWS = 4_077
EXPECTED_PLAYER_HASH_SIGNATURE = (
    "572d04e86ba2a673c515b4f6a0e02868ed48cfde8aa92577700c65b2fbbfe51f"
)
EXPECTED_TEAM_HASH_SIGNATURE = (
    "a2def0ae8dcc0f444913e2892f6d2101ac49f87ece0c6d7c56708ee8ab2e462b"
)
EXPECTED_SIS_HASH_SIGNATURE = (
    "5dc3d338606b48d30c9a92edccf518075314d3e777c3b5b4f175e6e9c4f14d17"
)
TARGET_SEASONS = (2023, 2024, 2025)
TARGET_WEEKS = tuple(range(5, 19))


def treatment_enabled(env: dict | None = None) -> bool:
    source = os.environ if env is None else env
    value = source.get(ENV_FLAG, "")
    if value in ("", "0"):
        return False
    if value != "1":
        raise ValueError(f"{ENV_FLAG} must be exactly 1 when enabled")
    beta = float(source.get(ENV_BETA, str(FROZEN_BETA)))
    if beta != FROZEN_BETA:
        raise ValueError(f"{ENV_BETA} must equal frozen beta {FROZEN_BETA}")
    return True


def rank_transport(control: np.ndarray, treatment: np.ndarray) -> np.ndarray:
    """Give each row treatment ranks and the exact control value multiset."""
    left = np.asarray(control)
    right = np.asarray(treatment)
    if left.shape != right.shape or left.ndim != 2:
        raise ValueError("rank transport requires equal player-by-world matrices")
    order = np.argsort(right, axis=1, kind="stable")
    values = np.sort(left, axis=1)
    transported = np.empty_like(left)
    np.put_along_axis(transported, order, values, axis=1)
    if not np.array_equal(np.sort(transported, axis=1), values):
        raise ValueError("ASOE rank transport failed exact marginal preservation")
    return transported


def build_target_allocation_multipliers(
    rows: pd.DataFrame,
    comps: pd.DataFrame,
    player_profiles: pd.DataFrame,
    offense_profiles: pd.DataFrame,
    defense_asoe: pd.DataFrame,
    *,
    beta: float = FROZEN_BETA,
    target_seasons: tuple[int, ...] = TARGET_SEASONS,
) -> tuple[np.ndarray, dict]:
    """Return q/p by repaired game-team target unit plus a score-free audit."""
    required = {"season", "week", "team", "opponent", "game_id", "gsis_id"}
    if missing := required - set(rows):
        raise ValueError(f"ASOE replay rows missing {sorted(missing)}")
    if len(rows) != len(comps):
        raise ValueError("ASOE replay rows/components do not align")
    stable = canonicalize_simulation_components(comps)
    base = np.nan_to_num(stable["targets"].to_numpy(dtype=np.float64))
    multipliers = np.ones(len(rows), dtype=np.float64)
    codes = _game_team_unit_codes(len(rows), rows.game_id, rows.team)

    resolved = (
        player_profiles.resolution_status.eq("resolved")
        if "resolution_status" in player_profiles else
        pd.Series(True, index=player_profiles.index)
    )
    player_profiles = player_profiles[
        player_profiles.gsis_id.notna() & resolved
    ].copy()
    player_key = ["season", "target_week", "team", "gsis_id"]
    offense_key = ["season", "target_week", "team"]
    defense_key = ["season", "target_week", "defense"]
    if player_profiles.duplicated(player_key).any():
        raise ValueError("ASOE player profiles repeat a replay join key")
    if offense_profiles.duplicated(offense_key).any():
        raise ValueError("ASOE offense profiles repeat a replay join key")
    if defense_asoe.duplicated(defense_key).any():
        raise ValueError("ASOE defense profiles repeat a replay join key")
    player = player_profiles.set_index(player_key)
    offense = offense_profiles.set_index(offense_key)
    defense = defense_asoe.set_index(defense_key)

    eligible_units = supported_units = changed_units = 0
    supported_players = 0
    changed_rows = 0
    for code in np.unique(codes):
        indices = np.flatnonzero((codes == code) & (base > 0))
        if len(indices) < 2:
            continue
        first = rows.iloc[int(indices[0])]
        season, week = int(first.season), int(first.week)
        if season not in target_seasons or week not in TARGET_WEEKS:
            continue
        teams = set(rows.iloc[indices].team.astype(str))
        opponents = set(rows.iloc[indices].opponent.dropna().astype(str))
        if len(teams) != 1 or len(opponents) != 1:
            raise ValueError("ASOE game-team unit has ambiguous team/opponent")
        team = next(iter(teams))
        opponent = next(iter(opponents))
        eligible_units += 1
        p = base[indices] / base[indices].sum()
        scores = np.zeros(len(indices), dtype=np.float64)
        supported = np.zeros(len(indices), dtype=bool)

        offense_key = (season, week, team)
        defense_key = (season, week, opponent)
        if offense_key not in offense.index or defense_key not in defense.index:
            continue
        off = offense.loc[offense_key]
        deff = defense.loc[defense_key]
        if isinstance(off, pd.DataFrame) or isinstance(deff, pd.DataFrame):
            raise ValueError("ASOE replay profile key is not unique")
        if not bool(off.offense_alignment_supported) or not bool(deff.asoe_supported):
            continue

        for offset, row_index in enumerate(indices):
            gsis_id = str(rows.iloc[int(row_index)].gsis_id)
            key = (season, week, team, gsis_id)
            if key not in player.index:
                continue
            profile = player.loc[key]
            if isinstance(profile, pd.DataFrame):
                raise ValueError("ASOE replay player key is not unique")
            if not bool(profile.alignment_supported):
                continue
            scores[offset] = float(deff.defense_asoe) * (
                float(profile.player_wide_share)
                - float(off.offense_wide_share)
            )
            supported[offset] = True

        mass = float(p[supported].sum())
        valid = bool(
            supported.sum() >= 2
            and mass >= allocation.MIN_GROUP_PROBABILITY_MASS
            and np.ptp(scores[supported]) > 0
        )
        if not valid:
            continue
        q = allocation.tilt_probabilities(p, scores, beta, valid=True)
        multipliers[indices] = q / p
        supported_units += 1
        supported_players += int(supported.sum())
        if not np.allclose(q, p, rtol=0, atol=1e-12):
            changed_units += 1
            changed_rows += int(np.count_nonzero(np.abs(q - p) > 1e-12))

    if not np.isfinite(multipliers).all() or (multipliers <= 0).any():
        raise ValueError("ASOE target allocation multipliers are invalid")
    return multipliers, {
        "beta": beta,
        "eligible_units": eligible_units,
        "supported_units": supported_units,
        "changed_units": changed_units,
        "supported_players": supported_players,
        "changed_rows": changed_rows,
        "source_week_strictly_prior": True,
    }


def _hash_signature(values: pd.Series) -> str:
    hashes = sorted(set(values.dropna().astype(str)))
    return hashlib.sha256("\n".join(hashes).encode()).hexdigest()


@functools.lru_cache(maxsize=1)
def load_frozen_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and validate the exact Stage A warehouse sources once/process."""
    from ..bq import query_df
    from ..config import settings

    player = query_df(f"""
        SELECT * FROM `{settings.raw}.fantasy_points_alignment_player_l4`
        WHERE source_run_id=@run
        """, params={"run": FP_SOURCE_RUN})
    offense = query_df(f"""
        SELECT * FROM `{settings.raw}.fantasy_points_alignment_team_l4`
        WHERE source_run_id=@run
        """, params={"run": FP_SOURCE_RUN})
    attempts = query_df(f"""
        SELECT * FROM `{settings.raw}.sis_alignment_attempt_game`
        WHERE source_run_id=@run
        """, params={"run": SIS_SOURCE_RUN})
    if (len(player), len(offense), len(attempts)) != (
        EXPECTED_PLAYER_ROWS, EXPECTED_TEAM_ROWS, EXPECTED_SIS_ROWS
    ):
        raise ValueError("ASOE warehouse source row counts changed")
    if not (
        player.source_week_start.eq(player.target_week - 4).all()
        and player.source_week_end.eq(player.target_week - 1).all()
        and player.source_week_end.lt(player.target_week).all()
    ):
        raise ValueError("ASOE player profile violates strictly-prior window")
    if set(attempts.alignment.astype(str)) != {"wide", "slot"}:
        raise ValueError("ASOE SIS source contains an unexpected alignment")
    signatures = (
        _hash_signature(player.source_sha256),
        _hash_signature(offense.source_sha256),
        _hash_signature(attempts.source_sha256),
    )
    if signatures != (
        EXPECTED_PLAYER_HASH_SIGNATURE,
        EXPECTED_TEAM_HASH_SIGNATURE,
        EXPECTED_SIS_HASH_SIGNATURE,
    ):
        raise ValueError("ASOE warehouse source hashes changed")

    schedule = query_df(f"""
        SELECT CAST(season AS INT64) season, CAST(week AS INT64) week,
               CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE home_team END team,
               CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE away_team END opponent
        FROM `{settings.raw}.schedules`
        WHERE season IN UNNEST(@seasons) AND game_type='REG'
        UNION ALL
        SELECT CAST(season AS INT64), CAST(week AS INT64),
               CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE away_team END,
               CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE home_team END
        FROM `{settings.raw}.schedules`
        WHERE season IN UNNEST(@seasons) AND game_type='REG'
        """, params={"seasons": list(allocation.ALL_SEASONS)})
    defense, audit = sis_asoe.build_defense_asoe(attempts, offense, schedule)
    log.info(
        "ASOE sources loaded player=%d team=%d sis=%d supported_defense=%d "
        "hash_signatures=%s/%s/%s",
        len(player), len(offense), len(attempts), audit["supported_rows"],
        *signatures,
    )
    return player, offense, defense


def frozen_target_allocation_multipliers(
    rows: pd.DataFrame,
    comps: pd.DataFrame,
) -> tuple[np.ndarray, dict]:
    player, offense, defense = load_frozen_sources()
    return build_target_allocation_multipliers(
        rows, comps, player, offense, defense, beta=FROZEN_BETA
    )


@functools.lru_cache(maxsize=18)
def load_live_sources(
    season: int, target_week: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Load a strictly-prior, provenance-bearing live ASOE target window."""
    from ..bq import query_df
    from ..config import settings

    season, target_week = int(season), int(target_week)
    if season != 2026 or target_week not in TARGET_WEEKS:
        raise ValueError("prospective ASOE v1 is frozen to 2026 Weeks 5-18")
    params = {"season": season, "week": target_week}
    player = query_df(f"""
        SELECT * FROM `{settings.raw}.fantasy_points_alignment_player_l4`
        WHERE season=@season AND target_week=@week
        """, params=params)
    offense = query_df(f"""
        SELECT *, target_week - 4 AS source_week_start,
               target_week - 1 AS source_week_end
        FROM `{settings.raw}.fantasy_points_alignment_team_l4`
        WHERE season=@season AND target_week=@week
        """, params=params)
    attempts = query_df(f"""
        SELECT * FROM `{settings.raw}.sis_alignment_attempt_game`
        WHERE season=@season AND week BETWEEN @week - 4 AND @week - 1
        """, params=params)
    if player.empty or offense.empty or attempts.empty:
        raise ValueError("live ASOE source window is incomplete")
    for name, frame in (("player", player), ("offense", offense),
                        ("SIS", attempts)):
        if "source_run_id" not in frame or frame.source_run_id.isna().any():
            raise ValueError(f"live ASOE {name} source identity is incomplete")
        if frame.source_run_id.astype(str).str.strip().eq("").any():
            raise ValueError(f"live ASOE {name} source identity is blank")
    if not (
        player.target_week.eq(target_week).all()
        and player.source_week_start.eq(target_week - 4).all()
        and player.source_week_end.eq(target_week - 1).all()
        and player.source_week_end.lt(player.target_week).all()
    ):
        raise ValueError("live ASOE player window violates point-in-time scope")
    if not (
        offense.target_week.eq(target_week).all()
        and offense.source_week_start.eq(target_week - 4).all()
        and offense.source_week_end.eq(target_week - 1).all()
        and offense.source_week_end.lt(offense.target_week).all()
    ):
        raise ValueError("live ASOE offense window violates point-in-time scope")
    if not attempts.week.between(target_week - 4, target_week - 1).all():
        raise ValueError("live ASOE SIS window violates point-in-time scope")
    if set(attempts.alignment.astype(str)) != {"wide", "slot"}:
        raise ValueError("live ASOE SIS source lacks exact wide/slot coverage")

    schedule = query_df(f"""
        SELECT CAST(season AS INT64) season, CAST(week AS INT64) week,
               CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE home_team END team,
               CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE away_team END opponent
        FROM `{settings.raw}.schedules`
        WHERE season=@season AND game_type='REG'
          AND week BETWEEN @week - 4 AND @week - 1
        UNION ALL
        SELECT CAST(season AS INT64), CAST(week AS INT64),
               CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE away_team END,
               CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE home_team END
        FROM `{settings.raw}.schedules`
        WHERE season=@season AND game_type='REG'
          AND week BETWEEN @week - 4 AND @week - 1
        """, params=params)
    defense, defense_audit = sis_asoe.build_defense_asoe(
        attempts, offense, schedule
    )
    defense = defense[
        defense.season.eq(season) & defense.target_week.eq(target_week)
    ].copy()
    if defense.empty:
        raise ValueError("live ASOE defense build has no target-week rows")
    audit = {
        "season": season,
        "target_week": target_week,
        "player_rows": int(len(player)),
        "offense_rows": int(len(offense)),
        "sis_rows": int(len(attempts)),
        "defense_rows": int(len(defense)),
        "player_source_runs": sorted(
            player.source_run_id.astype(str).unique().tolist()
        ),
        "offense_source_runs": sorted(
            offense.source_run_id.astype(str).unique().tolist()
        ),
        "sis_source_runs": sorted(
            attempts.source_run_id.astype(str).unique().tolist()
        ),
        "source_week_end": target_week - 1,
        "strictly_prior": True,
        "defense_build": defense_audit,
    }
    return player, offense, defense, audit


def live_target_allocation_multipliers(
    rows: pd.DataFrame, comps: pd.DataFrame,
) -> tuple[np.ndarray, dict]:
    """Apply the frozen ASOE law to one live 2026 target week."""
    keys = rows[["season", "week"]].drop_duplicates()
    if len(keys) != 1:
        raise ValueError("live ASOE rows must contain one season/week")
    season, week = (int(value) for value in keys.iloc[0])
    player, offense, defense, source_audit = load_live_sources(season, week)
    multipliers, allocation_audit = build_target_allocation_multipliers(
        rows, comps, player, offense, defense, beta=FROZEN_BETA,
        target_seasons=(2026,),
    )
    if not allocation_audit["changed_units"]:
        raise ValueError("live ASOE treatment is inert on the target slate")
    return multipliers, {
        **allocation_audit,
        "source": source_audit,
        "prospective": True,
    }


__all__ = [
    "FROZEN_BETA",
    "build_target_allocation_multipliers",
    "frozen_target_allocation_multipliers",
    "live_target_allocation_multipliers",
    "load_live_sources",
    "rank_transport",
    "treatment_enabled",
]
