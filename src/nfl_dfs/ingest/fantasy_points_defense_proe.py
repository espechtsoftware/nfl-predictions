"""Hash-locked weekly Fantasy Points Defense PROE intake and blind audit."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .fantasy_points_coverage import TEAM_NAMES
from .fantasy_points_route import _sha256
from .fantasy_points_same_season_coverage import _write_once


TABLE = "fantasy_points_defense_proe"
SOURCE_RUN = "fantasy-points-defense-proe-2022-2025-v1"
SEASONS = (2022, 2023, 2024, 2025)
WEEK_COLUMNS = tuple(f"W{week}" for week in range(1, 19))
EXPECTED_COLUMNS = (
    "Rank", "Name", "G", "Season", "Location", "Team Name",
    *WEEK_COLUMNS, "PROE",
)
EXPECTED_HASHES = {
    2022: "ea07de3dff814c88599af1ff7e64e9c2ef2021ef53c2133442cd7086dff8be2b",
    2023: "f7ab17479bf6b68a42db1147e963f53ab5059dba3c1331c32efd1539a4505dc6",
    2024: "38951d500d25d8ec8f2e331a6eb347e5636a1245eb46a0468ca7dc4ee7b425c3",
    2025: "07940fdae0475756d29329c9f5279534ec7069b9d35850d95fb46a30b5a4435b",
}
EXPECTED_POPULATED = {2022: 542, 2023: 544, 2024: 544, 2025: 544}
EXISTING_DEFENSE_FEATURES = (
    "epa_per_dropback_allowed_l6",
    "epa_per_rush_allowed_l6",
    "rz_td_rate_allowed_l6",
    "qb_fp_allowed_adj_l6",
    "rb_fp_allowed_adj_l6",
    "wr_fp_allowed_adj_l6",
    "te_fp_allowed_adj_l6",
    "opp_blitz_rate_l6",
    "opp_pressure_rate_l6",
)


def read_exports(input_dir: str | Path) -> tuple[pd.DataFrame, dict]:
    """Validate four untouched wide reports and normalize team-week values."""
    root = Path(input_dir)
    records: list[dict] = []
    season_rows: dict[str, int] = {}
    for season in SEASONS:
        path = root / f"{season}-Defense-proeReportExport.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        digest = _sha256(path)
        if digest != EXPECTED_HASHES[season]:
            raise ValueError(
                f"{path.name} hash {digest} != frozen {EXPECTED_HASHES[season]}")
        frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
        if tuple(frame.columns) != EXPECTED_COLUMNS:
            raise ValueError(f"{path.name} Defense PROE schema mismatch")
        if len(frame) != 32:
            raise ValueError(f"{path.name} has {len(frame)} teams; expected 32")
        if not pd.to_numeric(frame.Season, errors="raise").eq(season).all():
            raise ValueError(f"{path.name} contains another season")
        seen: set[str] = set()
        populated = 0
        for source_index, row in frame.iterrows():
            vendor_name = row["Name"].strip()
            if vendor_name not in TEAM_NAMES:
                raise ValueError(f"{path.name} has unmapped team {vendor_name!r}")
            team = TEAM_NAMES[vendor_name]
            if team in seen:
                raise ValueError(f"{path.name} repeats {team}")
            seen.add(team)
            games = int(row["G"])
            row_games = 0
            for week, column in enumerate(WEEK_COLUMNS, start=1):
                cell = row[column].strip()
                if not cell:
                    continue
                value_pct = float(cell)
                if not np.isfinite(value_pct) or not -100 <= value_pct <= 100:
                    raise ValueError(
                        f"{path.name} {team} {column} has invalid PROE")
                records.append({
                    "season": season,
                    "week": week,
                    "team": team,
                    "defense_proe_pct": value_pct,
                    "defense_proe": value_pct / 100.0,
                    "source_file": path.name,
                    "source_sha256": digest,
                    "source_row": int(source_index) + 2,
                    "source_run_id": SOURCE_RUN,
                })
                row_games += 1
                populated += 1
            if row_games != games:
                raise ValueError(
                    f"{path.name} {team} has G={games} but {row_games} weeks")
        if populated != EXPECTED_POPULATED[season]:
            raise ValueError(
                f"{path.name} has {populated} populated weeks; "
                f"expected {EXPECTED_POPULATED[season]}")
        season_rows[str(season)] = populated
    out = pd.DataFrame(records)
    if out.duplicated(["season", "week", "team"]).any():
        raise ValueError("Defense PROE import has duplicate team-weeks")
    return out, {
        "rows": int(len(out)),
        "teams": int(out.team.nunique()),
        "season_rows": season_rows,
    }


def attach_prior_l4(
    targets: pd.DataFrame,
    weekly: pd.DataFrame,
) -> pd.DataFrame:
    """Attach a last-four-completed-calendar-week mean, never target Week W."""
    target_needed = {"season", "week", "defense"}
    source_needed = {"season", "week", "team", "defense_proe"}
    if missing := target_needed - set(targets.columns):
        raise ValueError(f"Defense PROE targets missing {sorted(missing)}")
    if missing := source_needed - set(weekly.columns):
        raise ValueError(f"Defense PROE source missing {sorted(missing)}")
    if weekly.duplicated(["season", "week", "team"]).any():
        raise ValueError("Defense PROE source has duplicate team-weeks")
    windows: list[dict] = []
    for row in targets[["season", "week", "defense"]].drop_duplicates().itertuples(
        index=False
    ):
        start = int(row.week) - 4
        end = int(row.week) - 1
        source = weekly[
            weekly.season.eq(int(row.season))
            & weekly.team.eq(str(row.defense))
            & weekly.week.between(start, end)
        ]
        windows.append({
            "season": int(row.season),
            "week": int(row.week),
            "defense": str(row.defense),
            "fp_def_proe_source_week_start": start,
            "fp_def_proe_source_week_end": end,
            "fp_def_proe_prior_games": int(len(source)),
            "fp_def_proe_l4": (
                float(source.defense_proe.mean()) if len(source) else np.nan),
        })
    window_frame = pd.DataFrame(windows)
    out = targets.merge(
        window_frame,
        on=["season", "week", "defense"],
        how="left",
        validate="many_to_one",
    )
    out["fp_def_proe_supported"] = out.fp_def_proe_prior_games.ge(3)
    supported = out.fp_def_proe_supported
    if supported.any():
        target_week = out.loc[supported, "week"].astype(int)
        checks = (
            out.loc[supported, "fp_def_proe_source_week_start"].astype(int).eq(
                target_week - 4)
            & out.loc[supported, "fp_def_proe_source_week_end"].astype(int).eq(
                target_week - 1)
            & target_week.ge(5)
        )
        if not checks.all():
            raise ValueError("Defense PROE attachment violated PIT rules")
    return out


def redundancy_audit(rows: pd.DataFrame) -> dict:
    """Compare only against existing strictly-prior inputs; read no outcomes."""
    needed = {
        "season", "week", "defense", "fp_def_proe_l4",
        "fp_def_proe_supported", *EXISTING_DEFENSE_FEATURES,
    }
    if missing := needed - set(rows.columns):
        raise ValueError(f"Defense PROE audit rows missing {sorted(missing)}")
    correlations = []
    supported = rows[rows.fp_def_proe_supported].copy()
    for feature in EXISTING_DEFENSE_FEATURES:
        valid = supported.fp_def_proe_l4.notna() & supported[feature].notna()
        correlations.append({
            "feature": feature,
            "rows": int(valid.sum()),
            "pearson": float(supported.loc[valid, "fp_def_proe_l4"].corr(
                supported.loc[valid, feature], method="pearson")),
            "spearman": float(supported.loc[valid, "fp_def_proe_l4"].corr(
                supported.loc[valid, feature], method="spearman")),
        })
    by_season = {
        str(season): float(
            rows[rows.season.eq(season)].fp_def_proe_supported.mean())
        for season in SEASONS
    }
    return {
        "rows": int(len(rows)),
        "supported_rows": int(rows.fp_def_proe_supported.sum()),
        "support_by_season": by_season,
        "correlations": correlations,
        "max_abs_spearman": float(max(
            abs(item["spearman"]) for item in correlations
            if np.isfinite(item["spearman"])
        )),
        "outcomes_read": False,
    }


def run(input_dir: str | Path, *, write: bool = False) -> dict:
    """Audit licensed weekly Defense PROE and optionally create its raw table."""
    from ..bq import query_df
    from ..config import settings

    weekly, source_audit = read_exports(input_dir)
    targets = query_df(f"""
        SELECT season, week, opponent AS defense,
               ANY_VALUE(epa_per_dropback_allowed_l6)
                 AS epa_per_dropback_allowed_l6,
               ANY_VALUE(epa_per_rush_allowed_l6)
                 AS epa_per_rush_allowed_l6,
               ANY_VALUE(rz_td_rate_allowed_l6) AS rz_td_rate_allowed_l6,
               ANY_VALUE(qb_fp_allowed_adj_l6) AS qb_fp_allowed_adj_l6,
               ANY_VALUE(rb_fp_allowed_adj_l6) AS rb_fp_allowed_adj_l6,
               ANY_VALUE(wr_fp_allowed_adj_l6) AS wr_fp_allowed_adj_l6,
               ANY_VALUE(te_fp_allowed_adj_l6) AS te_fp_allowed_adj_l6,
               ANY_VALUE(opp_blitz_rate_l6) AS opp_blitz_rate_l6,
               ANY_VALUE(opp_pressure_rate_l6) AS opp_pressure_rate_l6
        FROM `{settings.features}.player_week_training`
        WHERE season BETWEEN 2022 AND 2025 AND week BETWEEN 5 AND 18
        GROUP BY season, week, defense
        """)
    blind_audit = redundancy_audit(attach_prior_l4(targets, weekly))
    table_ref = f"{settings.raw}.{TABLE}"
    report = {
        "source": source_audit,
        "outcome_blind_redundancy": blind_audit,
        "table": table_ref,
        "write_requested": bool(write),
    }
    if write:
        report["write_disposition"] = _write_once(
            table_ref,
            weekly,
            run_id=SOURCE_RUN,
            hash_columns=("source_sha256",),
        )
    print("FP_DEFENSE_PROE_IMPORT_JSON=" + json.dumps(report, sort_keys=True))
    return report
