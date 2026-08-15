"""Manifest-locked SIS receiver-copula history and PIT defense context."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .sis_team_context import TEAM_ABBREVIATIONS
from ..ops import sis_downloads as sis


PLAYER_GAME_TABLE = "sis_receiver_copula_player_game"
DEFENSE_PRIOR_TABLE = "sis_receiver_copula_defense_prior"
SOURCE_RUN = "sis-receiver-copula-v1"
TARGET_WEEKS = tuple(range(5, 19))
PRIOR_GAMES = 8
MIN_PRIOR_GAMES = 4


def _number(value: object, *, nonnegative: bool = True) -> float:
    raw = str(value).replace(",", "").strip()
    if not raw:
        raise ValueError("SIS receiver-copula numeric value is blank")
    parsed = float(raw)
    if not np.isfinite(parsed) or (nonnegative and parsed < 0):
        raise ValueError(f"SIS receiver-copula numeric value is invalid: {value!r}")
    return parsed


def read_player_games(input_dir: str | Path) -> tuple[pd.DataFrame, dict]:
    """Reproduce the frozen acquisition gate and parse its licensed rows."""
    root = Path(input_dir)
    manifest = json.loads((root / "receiver-copula.manifest.json").read_text())
    result = json.loads((root / "receiver-copula.result.json").read_text())
    verified = sis.analyze_receiver_copula_acquisition(root, manifest)
    if verified != result or not result.get("passes"):
        raise ValueError("SIS receiver-copula acquisition did not reproduce")

    records: list[dict] = []
    for item in manifest["artifacts"]:
        path = root / item["artifact"]
        identities: dict[tuple[str, str], dict] = {}
        for identity in item["identities"]:
            key = (str(identity["player"]), str(identity["team"]))
            if key in identities:
                raise ValueError(f"{path.name} repeats a player/team identity")
            identities[key] = identity
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            key = (str(row["Player"]), str(row["Team"]))
            if key not in identities:
                raise ValueError(f"{path.name} row lacks its API identity")
            identity = identities[key]
            team_name = str(row["Team"])
            opponent_name = str(row["Opp."])
            if (
                team_name not in TEAM_ABBREVIATIONS
                or opponent_name not in TEAM_ABBREVIATIONS
            ):
                raise ValueError(f"{path.name} has an unknown team alias")
            records.append({
                "season": int(row["Season"]),
                "week": int(row["Week"]),
                "alignment": str(item["alignment"]),
                "defender_player_id": int(identity["playerId"]),
                "defender_team_id": int(identity["teamId"]),
                "defender_name": str(row["Player"]),
                "defense": TEAM_ABBREVIATIONS[team_name],
                "offense": TEAM_ABBREVIATIONS[opponent_name],
                "coverage_snaps": _number(row["Cov. Snaps"]),
                "targets": _number(row["Tgts"]),
                "completions": _number(row["Comp"]),
                "yards": _number(row["Yds"], nonnegative=False),
                "touchdowns": _number(row["TDs"]),
                "source_sha256": str(item["sha256"]),
            })
    frame = pd.DataFrame.from_records(records)
    keys = [
        "season", "week", "alignment", "defender_player_id",
        "defender_team_id",
    ]
    if frame.empty or frame.duplicated(keys).any():
        raise ValueError("SIS receiver-copula player games are empty or duplicated")
    if not set(frame.alignment) == {"wide", "slot"}:
        raise ValueError("SIS receiver-copula alignment universe differs")
    return frame, {
        "rows": int(len(frame)),
        "artifacts": int(len(manifest["artifacts"])),
        "distinct_player_ids": int(frame.defender_player_id.nunique()),
        "teams": int(frame.defender_team_id.nunique()),
        "protocol_sha256": manifest["protocol_sha256"],
        "source_week_min": int(frame.week.min()),
        "source_week_max": int(frame.week.max()),
    }


def _target_spine(schedule: pd.DataFrame) -> pd.DataFrame:
    required = {"season", "week", "team", "opponent"}
    if missing := required - set(schedule):
        raise ValueError(f"receiver-copula schedule missing {sorted(missing)}")
    spine = schedule[list(required)].drop_duplicates().copy()
    spine["season"] = pd.to_numeric(spine.season, errors="raise").astype(int)
    spine["week"] = pd.to_numeric(spine.week, errors="raise").astype(int)
    spine["team"] = spine.team.astype(str)
    spine["opponent"] = spine.opponent.astype(str)
    spine = spine[
        spine.season.isin(sis.RECEIVER_COPULA_SEASONS)
        & spine.week.isin(TARGET_WEEKS)
    ].copy()
    if spine.empty or spine.duplicated(["season", "week", "team"]).any():
        raise ValueError("receiver-copula target spine is empty or duplicated")
    return spine.sort_values(["season", "week", "team"], kind="stable")


def build_defense_prior(
    player_games: pd.DataFrame,
    schedule: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Build cross-season last-eight defense/alignment context without W data."""
    required = {
        "season", "week", "alignment", "defense", "coverage_snaps",
        "targets", "completions", "yards", "touchdowns",
        "defender_player_id",
    }
    if missing := required - set(player_games):
        raise ValueError(f"receiver-copula player games missing {sorted(missing)}")
    games = player_games.groupby(
        ["season", "week", "defense", "alignment"], as_index=False,
        sort=True,
    ).agg(
        coverage_snaps=("coverage_snaps", "sum"),
        targets=("targets", "sum"),
        completions=("completions", "sum"),
        yards=("yards", "sum"),
        touchdowns=("touchdowns", "sum"),
        defender_rows=("defender_player_id", "size"),
    )
    if games.duplicated(["season", "week", "defense", "alignment"]).any():
        raise ValueError("receiver-copula defense games repeat a cell")
    games["order"] = games.season.astype(int) * 100 + games.week.astype(int)
    spine = _target_spine(schedule)
    records: list[dict] = []
    for target in spine.itertuples(index=False):
        target_order = int(target.season) * 100 + int(target.week)
        for alignment, _values in sis.RECEIVER_COPULA_ALIGNMENTS:
            source = games[
                games.defense.eq(str(target.team))
                & games.alignment.eq(alignment)
                & games.order.lt(target_order)
            ].sort_values(["season", "week"], kind="stable").tail(PRIOR_GAMES)
            record = {
                "season": int(target.season),
                "target_week": int(target.week),
                "defense": str(target.team),
                "offense": str(target.opponent),
                "alignment": alignment,
                "prior_games": int(len(source)),
                "coverage_snaps": float(source.coverage_snaps.sum()),
                "targets": float(source.targets.sum()),
                "completions": float(source.completions.sum()),
                "yards": float(source.yards.sum()),
                "touchdowns": float(source.touchdowns.sum()),
                "source_first_season": (
                    int(source.season.iloc[0]) if len(source) else None
                ),
                "source_first_week": (
                    int(source.week.iloc[0]) if len(source) else None
                ),
                "source_last_season": (
                    int(source.season.iloc[-1]) if len(source) else None
                ),
                "source_last_week": (
                    int(source.week.iloc[-1]) if len(source) else None
                ),
            }
            record["base_supported"] = bool(
                len(source) >= MIN_PRIOR_GAMES
                and record["coverage_snaps"] > 0
                and record["targets"] > 0
            )
            records.append(record)
    prior = pd.DataFrame.from_records(records)
    if prior.duplicated(["season", "target_week", "defense", "alignment"]).any():
        raise ValueError("receiver-copula prior repeats a target cell")

    prior["vulnerability"] = np.nan
    prior["league_target_rate"] = np.nan
    prior["league_points_per_target"] = np.nan
    prior["coverage_prior_size"] = np.nan
    prior["target_prior_size"] = np.nan
    for (_season, _week, _alignment), index in prior.groupby(
        ["season", "target_week", "alignment"], sort=True,
    ).groups.items():
        rows = prior.loc[index]
        supported = rows[rows.base_supported]
        if supported.empty:
            continue
        total_coverage = float(supported.coverage_snaps.sum())
        total_targets = float(supported.targets.sum())
        if total_coverage <= 0 or total_targets <= 0:
            continue
        target_rate = total_targets / total_coverage
        points = (
            supported.completions + 0.1 * supported.yards
            + 6.0 * supported.touchdowns
        )
        point_rate = float(points.sum() / total_targets)
        coverage_prior = float(np.median(supported.coverage_snaps))
        target_prior = float(np.median(supported.targets))
        if not all(np.isfinite(value) and value > 0 for value in (
            target_rate, point_rate, coverage_prior, target_prior,
        )):
            continue
        row_index = supported.index
        exposure = (
            supported.targets + coverage_prior * target_rate
        ) / (supported.coverage_snaps + coverage_prior)
        points_per_target = (
            points + target_prior * point_rate
        ) / (supported.targets + target_prior)
        prior.loc[index, "league_target_rate"] = target_rate
        prior.loc[index, "league_points_per_target"] = point_rate
        prior.loc[index, "coverage_prior_size"] = coverage_prior
        prior.loc[index, "target_prior_size"] = target_prior
        prior.loc[row_index, "vulnerability"] = (
            exposure * points_per_target
        ).to_numpy(float)
    prior["context_supported"] = (
        prior.base_supported & prior.vulnerability.notna()
    )
    if prior.loc[prior.context_supported, "vulnerability"].le(0).any():
        raise ValueError("receiver-copula supported vulnerability is nonpositive")
    target_order = prior.season.astype(int) * 100 + prior.target_week.astype(int)
    source_order = (
        prior.source_last_season.fillna(-1).astype(int) * 100
        + prior.source_last_week.fillna(-1).astype(int)
    )
    if not source_order.lt(target_order).all():
        raise ValueError("receiver-copula prior includes target/future data")
    return prior, {
        "rows": int(len(prior)),
        "supported_rows": int(prior.context_supported.sum()),
        "supported_fraction": float(prior.context_supported.mean()),
        "strictly_prior": True,
        "prior_games": PRIOR_GAMES,
        "minimum_prior_games": MIN_PRIOR_GAMES,
        "source_last_season_max": int(
            prior.source_last_season.dropna().max()
        ),
        "source_last_week_max": int(prior.source_last_week.dropna().max()),
    }


def run(input_dir: str | Path, *, write: bool = False) -> dict:
    """Audit and optionally create the private raw player/prior tables."""
    from .fantasy_points_same_season_coverage import _write_once
    from ..bq import query_df
    from ..config import settings

    players, source_audit = read_player_games(input_dir)
    schedule = query_df(f"""
        SELECT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
               home_team AS team, away_team AS opponent
        FROM `{settings.raw}.schedules`
        WHERE season IN UNNEST(@seasons) AND game_type = 'REG'
        UNION ALL
        SELECT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
               away_team AS team, home_team AS opponent
        FROM `{settings.raw}.schedules`
        WHERE season IN UNNEST(@seasons) AND game_type = 'REG'
        """, params={"seasons": list(sis.RECEIVER_COPULA_SEASONS)})
    prior, prior_audit = build_defense_prior(players, schedule)
    players["source_run_id"] = SOURCE_RUN
    prior["source_run_id"] = SOURCE_RUN
    prior["source_sha256"] = source_audit["protocol_sha256"]
    player_ref = f"{settings.raw}.{PLAYER_GAME_TABLE}"
    prior_ref = f"{settings.raw}.{DEFENSE_PRIOR_TABLE}"
    audit = {
        "source": source_audit,
        "prior": prior_audit,
        "player_table": player_ref,
        "prior_table": prior_ref,
        "write_requested": bool(write),
    }
    if write:
        audit["player_write_disposition"] = _write_once(
            player_ref, players, run_id=SOURCE_RUN,
            hash_columns=("source_sha256",),
        )
        audit["prior_write_disposition"] = _write_once(
            prior_ref, prior, run_id=SOURCE_RUN,
            hash_columns=("source_sha256",),
        )
    print("SIS_RECEIVER_COPULA_IMPORT_JSON=" + json.dumps(audit, sort_keys=True))
    return audit


__all__ = [
    "DEFENSE_PRIOR_TABLE", "MIN_PRIOR_GAMES", "PLAYER_GAME_TABLE",
    "PRIOR_GAMES", "SOURCE_RUN", "TARGET_WEEKS", "build_defense_prior",
    "read_player_games", "run",
]
