"""Frozen Fantasy Points offense-by-defense QB shell-fit diagnostic."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .fantasy_points_coverage_fit import _score
from .fantasy_points_route_share import CONTROL_NUMERIC, _fit_predict
from ..ingest.fantasy_points_qb_shell import PLAN_NAME, TABLE
from ..ingest.fantasy_points_route import PANEL_ID


HELD_OUT_SEASONS = (2023, 2024, 2025)
SHELL_FEATURES = ("fp_qb_shell_mz_grade", "fp_qb_shell_mof_grade")


def attach_qb_shell_fit(targets: pd.DataFrame, shells: pd.DataFrame) -> pd.DataFrame:
    """Attach exact W-4:W-1 team/opponent matrices and compute two grades."""
    target_needed = {"season", "week", "team", "opp", "pos"}
    source_needed = {
        "season", "target_week", "team", "source_week_start",
        "source_week_end", "offense_source_run_id", "defense_source_run_id",
        *{
            f"{side}_{shell}_{metric}"
            for side in ("off", "def")
            for shell in ("man", "zone", "one_high", "two_high")
            for metric in ("rate", "fpdb")
        },
        "off_dropbacks", "def_dropbacks",
    }
    if missing := target_needed - set(targets.columns):
        raise ValueError(f"QB shell targets missing {sorted(missing)}")
    if missing := source_needed - set(shells.columns):
        raise ValueError(f"QB shell source missing {sorted(missing)}")
    keys = ["season", "target_week", "team"]
    if shells.duplicated(keys).any():
        raise ValueError("QB shell source has duplicate team windows")
    offense_columns = [
        "season", "target_week", "team", "source_week_start",
        "source_week_end", "offense_source_run_id", "off_dropbacks",
        *[
            f"off_{shell}_{metric}"
            for shell in ("man", "zone", "one_high", "two_high")
            for metric in ("rate", "fpdb")
        ],
    ]
    offense = shells[offense_columns].rename(columns={
        "target_week": "off_target_week",
        "source_week_start": "off_source_week_start",
        "source_week_end": "off_source_week_end",
        "team": "source_team",
    })
    defense_columns = [
        "season", "target_week", "team", "source_week_start",
        "source_week_end", "defense_source_run_id", "def_dropbacks",
        *[
            f"def_{shell}_{metric}"
            for shell in ("man", "zone", "one_high", "two_high")
            for metric in ("rate", "fpdb")
        ],
    ]
    defense = shells[defense_columns].rename(columns={
        "target_week": "def_target_week",
        "source_week_start": "def_source_week_start",
        "source_week_end": "def_source_week_end",
        "team": "source_opp",
    })
    out = targets.merge(
        offense,
        left_on=["season", "week", "team"],
        right_on=["season", "off_target_week", "source_team"],
        how="left",
        validate="many_to_one",
    ).merge(
        defense,
        left_on=["season", "week", "opp"],
        right_on=["season", "def_target_week", "source_opp"],
        how="left",
        validate="many_to_one",
    )
    finite_columns = [
        f"{side}_{shell}_{metric}"
        for side in ("off", "def")
        for shell in ("man", "zone", "one_high", "two_high")
        for metric in ("rate", "fpdb")
    ]
    finite = np.isfinite(out[finite_columns].astype(float)).all(axis=1)
    pair_sums = {
        "off_mz": out.off_man_rate + out.off_zone_rate,
        "def_mz": out.def_man_rate + out.def_zone_rate,
        "off_mof": out.off_one_high_rate + out.off_two_high_rate,
        "def_mof": out.def_one_high_rate + out.def_two_high_rate,
    }
    supported = (
        out.pos.eq("QB")
        & out.off_dropbacks.ge(80)
        & out.def_dropbacks.ge(80)
        & finite
        & pd.concat(pair_sums, axis=1).gt(0).all(axis=1)
    )
    for name, first, second in (
        ("mz", "man", "zone"),
        ("mof", "one_high", "two_high"),
    ):
        off_sum = pair_sums[f"off_{name}"]
        def_sum = pair_sums[f"def_{name}"]
        recent = (
            out[f"off_{first}_rate"] / off_sum * out[f"off_{first}_fpdb"]
            + out[f"off_{second}_rate"] / off_sum * out[f"off_{second}_fpdb"]
        )
        matchup = (
            out[f"def_{first}_rate"] / def_sum * out[f"off_{first}_fpdb"]
            + out[f"def_{second}_rate"] / def_sum * out[f"off_{second}_fpdb"]
        )
        valid = supported & recent.gt(0) & np.isfinite(recent) & np.isfinite(matchup)
        out[f"fp_qb_shell_{name}_grade"] = (matchup / recent - 1.0).where(valid)
    out["fp_qb_shell_supported"] = (
        supported & out[list(SHELL_FEATURES)].notna().all(axis=1)
    )
    populated = out.fp_qb_shell_supported
    if populated.any():
        target_week = out.loc[populated, "week"].astype(int)
        checks = (
            out.loc[populated, "off_target_week"].astype(int).eq(target_week)
            & out.loc[populated, "def_target_week"].astype(int).eq(target_week)
            & out.loc[populated, "off_source_week_start"].astype(int).eq(target_week - 4)
            & out.loc[populated, "def_source_week_start"].astype(int).eq(target_week - 4)
            & out.loc[populated, "off_source_week_end"].astype(int).eq(target_week - 1)
            & out.loc[populated, "def_source_week_end"].astype(int).eq(target_week - 1)
            & out.loc[populated, "source_team"].eq(out.loc[populated, "team"])
            & out.loc[populated, "source_opp"].eq(out.loc[populated, "opp"])
        )
        if not checks.all() or target_week.lt(5).any():
            raise ValueError("QB shell join violated PIT/team/opponent rules")
    return out


def _correlations(frame: pd.DataFrame, fold: int) -> list[dict]:
    residual = frame.actual.astype(float) - frame.mean_projection.astype(float)
    tail = frame.actual.ge(30).astype(int)
    return [{
        "fold": int(fold),
        "feature": feature,
        "rows": int(frame[feature].notna().sum()),
        "spearman_projection_residual": float(
            frame[feature].astype(float).corr(residual, method="spearman")),
        "point_biserial_tail_30": float(
            frame[feature].astype(float).corr(tail.astype(float))),
    } for feature in SHELL_FEATURES]


def shell_gate(aggregate: dict, coverage: dict[int, float]) -> dict:
    checks = {
        "coverage_at_least_70pct_each_fold": all(
            coverage.get(season, 0.0) >= 0.70 for season in HELD_OUT_SEASONS),
        "aggregate_30_brier_improves": (
            aggregate["treatment_brier_30"] < aggregate["control_brier_30"]),
    }
    return {**checks, "passes": all(checks.values())}


def evaluate(rows: pd.DataFrame) -> dict:
    needed = {
        "season", "week", "gsis_id", "pos", "actual", "mean_projection",
        "fp_qb_shell_supported", *CONTROL_NUMERIC, *SHELL_FEATURES,
    }
    if missing := needed - set(rows.columns):
        raise ValueError(f"QB shell evaluation rows missing {sorted(missing)}")
    base = rows[
        rows.pos.eq("QB") & rows.week.between(5, 18)
        & rows.mean_projection.notna() & rows.actual.notna()
    ].copy()
    coverage = {
        season: float(base[base.season.eq(season)].fp_qb_shell_supported.mean())
        for season in HELD_OUT_SEASONS
    }
    eligible = base[base.fp_qb_shell_supported].copy()
    fold_frames: list[pd.DataFrame] = []
    fold_reports: list[dict] = []
    correlations: list[dict] = []
    for held_out in HELD_OUT_SEASONS:
        train = eligible[
            eligible.season.lt(held_out) & eligible.season.ge(2022)].copy()
        test = eligible[eligible.season.eq(held_out)].copy()
        if train.empty or test.empty:
            raise ValueError(f"QB shell fold {held_out} is empty")
        control = _fit_predict(train, test, CONTROL_NUMERIC)
        treatment = _fit_predict(train, test, CONTROL_NUMERIC + SHELL_FEATURES)
        test["control_score"] = test.mean_projection + control[0]
        test["control_tail_20"], test["control_tail_30"] = control[1:]
        test["treatment_score"] = test.mean_projection + treatment[0]
        test["treatment_tail_20"], test["treatment_tail_30"] = treatment[1:]
        fold_frames.append(test)
        fold_reports.append(_score(test, str(held_out)))
        correlations.extend(_correlations(test, held_out))
    combined = pd.concat(fold_frames, ignore_index=True)
    aggregate = _score(combined, "aggregate")
    gate = shell_gate(aggregate, coverage)
    return {
        "disposition": (
            "fp-qb-shell-player-tail-passes" if gate["passes"]
            else "fp-qb-shell-player-tail-fails"),
        "identity": {
            "base_rows": int(len(base)),
            "supported_rows": int(len(eligible)),
            "held_out_seasons": list(HELD_OUT_SEASONS),
            "target_weeks": [5, 18],
        },
        "coverage": {str(key): value for key, value in coverage.items()},
        "missingness": {
            feature: int(base[feature].isna().sum()) for feature in SHELL_FEATURES
        },
        "folds": fold_reports,
        "aggregate": aggregate,
        "correlations": correlations,
        "gate": gate,
    }


def run(panel_id: str = PANEL_ID) -> dict:
    if panel_id != PANEL_ID:
        raise ValueError(f"QB shell protocol is frozen to {PANEL_ID}")
    from ..bq import query_df
    from ..config import settings

    shells = query_df(f"SELECT * FROM `{settings.raw}.{TABLE}`")
    offense_runs = set(shells.offense_source_run_id.dropna().astype(str))
    if len(offense_runs) != 1 or not next(iter(offense_runs)).endswith(
            f"__{PLAN_NAME}"):
        raise ValueError("QB shell offense table provenance is invalid")
    targets = query_df(f"""
        SELECT season, week, gsis_id, pos, team, opp, mean_projection, salary,
               target_share_last, target_share_jump,
               snap_share_last, snap_share_jump,
               team_vacated_target_share, depth_rank,
               games_played_prior, actual
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season BETWEEN 2022 AND 2025
          AND week BETWEEN 5 AND 18 AND pos = 'QB'
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={"panel_id": panel_id})
    report = evaluate(attach_qb_shell_fit(targets, shells))
    report["panel"] = panel_id
    report["offense_source_run_id"] = next(iter(offense_runs))
    defense_runs = set(shells.defense_source_run_id.dropna().astype(str))
    if len(defense_runs) != 1:
        raise ValueError("QB shell defense table provenance is invalid")
    report["defense_source_run_id"] = next(iter(defense_runs))
    print("FP_QB_SHELL_JSON=" + json.dumps(report, sort_keys=True))
    return report
