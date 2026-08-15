"""Frozen post-2022 overtime fantasy-uplift and Vegas-predictability study."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)

from ..bq import query_df
from ..config import settings
from ..research.recourse_scoring import score_skill_players, score_team_defenses


VERSION = "20260815-overtime-fantasy-and-vegas-v1"
PROTOCOL_PATH = Path("reports/2026-08-15-overtime-fantasy-and-vegas-protocol.md")
PROTOCOL_SHA256 = "70ec0c1af2b0d6d3fc985261b5e74dcb8a2b4f20262fce716e8eaebf1f29f757"
TRAIN_SEASONS = (2022, 2023, 2024)
HELDOUT_SEASON = 2025
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20_260_815
SKILL_POSITIONS = ("QB", "RB", "WR", "TE")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()


def _frame_sha256(frame: pd.DataFrame) -> str:
    ordered = frame.copy()
    for column in ordered.columns:
        if pd.api.types.is_datetime64_any_dtype(ordered[column]):
            ordered[column] = ordered[column].astype("string")
    content = ordered.to_csv(
        index=False, na_rep="<NA>", float_format="%.17g", lineterminator="\n",
    ).encode()
    return sha256(content).hexdigest()


def _protocol_check() -> None:
    if not PROTOCOL_PATH.is_file() or sha256(PROTOCOL_PATH.read_bytes()).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("overtime protocol is missing or changed")


def load_schedules() -> pd.DataFrame:
    frame = query_df(f"""
        SELECT game_id, CAST(season AS INT64) AS season,
               CAST(week AS INT64) AS week, game_type, gameday, weekday,
               gametime, away_team, home_team, CAST(overtime AS INT64) AS overtime,
               CAST(spread_line AS FLOAT64) AS spread_line,
               CAST(total_line AS FLOAT64) AS total_line
        FROM `{settings.raw}.schedules`
        WHERE season BETWEEN 2022 AND 2025
          AND game_type IN ('REG', 'WC', 'DIV', 'CON', 'SB')
        ORDER BY season, game_type, week, game_id
    """)
    required = {
        "game_id", "season", "week", "game_type", "overtime",
        "spread_line", "total_line",
    }
    if missing := required - set(frame.columns):
        raise ValueError(f"overtime schedules missing {sorted(missing)}")
    if frame.game_id.isna().any() or frame.game_id.duplicated().any():
        raise ValueError("overtime schedule game identity is invalid")
    if set(frame.season.astype(int)) != {2022, 2023, 2024, 2025}:
        raise ValueError("overtime schedule seasons differ")
    if frame.overtime.isna().any() or not set(frame.overtime.astype(int)).issubset({0, 1}):
        raise ValueError("overtime schedule label is invalid")
    return frame


def _standardize(train: np.ndarray, test: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    mean = train.mean(axis=0)
    std = train.std(axis=0, ddof=0)
    if not np.isfinite(mean).all() or not np.isfinite(std).all() or (std <= 0).any():
        raise ValueError("overtime predictor standardization is invalid")
    return (train - mean) / std, (test - mean) / std, {
        "mean": mean.tolist(), "std": std.tolist(),
    }


def _metrics(y: np.ndarray, probability: np.ndarray) -> dict[str, float]:
    p = np.asarray(probability, dtype=float)
    if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
        raise ValueError("overtime predictor emitted invalid probability")
    clipped = np.clip(p, 1e-6, 1 - 1e-6)
    return {
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, clipped, labels=[0, 1])),
        "roc_auc": float(roc_auc_score(y, p)),
        "average_precision": float(average_precision_score(y, p)),
    }


def _risk_quartiles(test: pd.DataFrame, probability: np.ndarray) -> list[dict[str, Any]]:
    ranked = test[["game_id", "overtime"]].copy()
    ranked["probability"] = probability
    ranked = ranked.sort_values(["probability", "game_id"], kind="mergesort").reset_index(drop=True)
    ranked["quartile"] = np.minimum(4, np.floor(np.arange(len(ranked)) * 4 / len(ranked)).astype(int) + 1)
    rows = []
    for quartile, group in ranked.groupby("quartile", sort=True):
        rows.append({
            "quartile": int(quartile),
            "games": int(len(group)),
            "overtime_games": int(group.overtime.astype(int).sum()),
            "mean_probability": float(group.probability.mean()),
            "observed_rate": float(group.overtime.astype(int).mean()),
        })
    return rows


def _paired_week_bootstrap(
    test: pd.DataFrame,
    p0: np.ndarray,
    p2: np.ndarray,
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    if replicates <= 0:
        raise ValueError("overtime bootstrap replicate count is invalid")
    weeks = np.array(sorted(test.week.astype(int).unique()))
    by_week = {
        week: np.flatnonzero(test.week.astype(int).to_numpy() == week)
        for week in weeks
    }
    rng = np.random.default_rng(seed)
    brier_delta = np.empty(replicates, dtype=float)
    log_delta = np.empty(replicates, dtype=float)
    y_all = test.overtime.astype(int).to_numpy()
    for index in range(replicates):
        sampled = rng.choice(weeks, size=len(weeks), replace=True)
        take = np.concatenate([by_week[int(week)] for week in sampled])
        y = y_all[take]
        base = p0[take]
        model = p2[take]
        brier_delta[index] = np.mean((y - model) ** 2 - (y - base) ** 2)
        base_clip = np.clip(base, 1e-6, 1 - 1e-6)
        model_clip = np.clip(model, 1e-6, 1 - 1e-6)
        base_loss = -(y * np.log(base_clip) + (1 - y) * np.log(1 - base_clip))
        model_loss = -(y * np.log(model_clip) + (1 - y) * np.log(1 - model_clip))
        log_delta[index] = np.mean(model_loss - base_loss)

    def summary(values: np.ndarray) -> dict[str, float]:
        return {
            "mean": float(values.mean()),
            "p05": float(np.quantile(values, 0.05)),
            "p95": float(np.quantile(values, 0.95)),
        }

    return {
        "replicates": int(replicates),
        "seed": int(seed),
        "unit": "week",
        "m2_minus_m0_brier": summary(brier_delta),
        "m2_minus_m0_log_loss": summary(log_delta),
    }


def evaluate_predictability(
    schedules: pd.DataFrame,
    *,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    regular = schedules.loc[schedules.game_type.eq("REG")].copy()
    regular["abs_spread"] = pd.to_numeric(regular.spread_line, errors="coerce").abs()
    regular["total_line"] = pd.to_numeric(regular.total_line, errors="coerce")
    missing = regular[["abs_spread", "total_line"]].isna().any(axis=1)
    exclusions = regular.loc[missing, ["game_id", "season", "week"]].to_dict("records")
    regular = regular.loc[~missing].copy()
    train = regular.loc[regular.season.astype(int).isin(TRAIN_SEASONS)].reset_index(drop=True)
    test = regular.loc[regular.season.astype(int).eq(HELDOUT_SEASON)].reset_index(drop=True)
    if train.empty or test.empty or train.overtime.nunique() != 2 or test.overtime.nunique() != 2:
        raise ValueError("overtime predictor train/heldout population is invalid")
    y_train = train.overtime.astype(int).to_numpy()
    y_test = test.overtime.astype(int).to_numpy()
    base_rate = float((y_train.sum() + 1) / (len(y_train) + 2))
    p0 = np.full(len(test), base_rate, dtype=float)
    outputs: dict[str, Any] = {
        "m0": {"probability": p0, "fit": {"laplace_base_rate": base_rate}},
    }
    for label, features in (("m1", ["abs_spread"]), ("m2", ["abs_spread", "total_line"])):
        x_train, x_test, scaling = _standardize(
            train[features].to_numpy(float), test[features].to_numpy(float),
        )
        model = LogisticRegression(C=1.0, class_weight=None, solver="lbfgs", max_iter=1_000)
        model.fit(x_train, y_train)
        outputs[label] = {
            "probability": model.predict_proba(x_test)[:, 1],
            "fit": {
                "features": features,
                "scaling": scaling,
                "intercept": model.intercept_.astype(float).tolist(),
                "coefficients": model.coef_.astype(float).tolist(),
                "iterations": model.n_iter_.astype(int).tolist(),
            },
        }
    for value in outputs.values():
        value["metrics"] = _metrics(y_test, value["probability"])
    quartiles = _risk_quartiles(test, outputs["m2"]["probability"])
    bootstrap = _paired_week_bootstrap(
        test, outputs["m0"]["probability"], outputs["m2"]["probability"],
        replicates=bootstrap_replicates,
    )
    heldout_rate = float(y_test.mean())
    highest = next(row for row in quartiles if row["quartile"] == 4)
    highest["lift_vs_heldout_rate"] = float(highest["observed_rate"] / heldout_rate)
    predictive = bool(
        outputs["m2"]["metrics"]["brier"] < outputs["m0"]["metrics"]["brier"]
        and outputs["m2"]["metrics"]["log_loss"] < outputs["m0"]["metrics"]["log_loss"]
        and bootstrap["m2_minus_m0_brier"]["p95"] < 0
        and bootstrap["m2_minus_m0_log_loss"]["p95"] < 0
        and highest["lift_vs_heldout_rate"] > 1
        and highest["overtime_games"] >= 2
    )
    serializable_models = {
        label: {"fit": value["fit"], "metrics": value["metrics"]}
        for label, value in outputs.items()
    }
    return {
        "train": {
            "seasons": list(TRAIN_SEASONS), "games": int(len(train)),
            "overtime_games": int(y_train.sum()),
        },
        "heldout": {
            "season": HELDOUT_SEASON, "games": int(len(test)),
            "overtime_games": int(y_test.sum()), "overtime_rate": heldout_rate,
        },
        "excluded_missing_market": exclusions,
        "models": serializable_models,
        "m2_risk_quartiles": quartiles,
        "paired_week_bootstrap": bootstrap,
        "passes_frozen_predictability_gate": predictive,
        "disposition": "predictive" if predictive else "non-predictive-or-inconclusive",
    }


def _load_regular_actuals() -> tuple[pd.DataFrame, pd.DataFrame]:
    skill = query_df(f"""
        WITH roster AS (
          SELECT season, week, gsis_id,
                 ARRAY_AGG(position IGNORE NULLS ORDER BY position LIMIT 1)
                   [SAFE_OFFSET(0)] AS position
          FROM `{settings.raw}.rosters_weekly`
          WHERE season = 2025
          GROUP BY season, week, gsis_id
        )
        SELECT s.game_id, a.gsis_id AS player_id,
               IF(r.position = 'FB', 'RB', r.position) AS position,
               CAST(a.dk_points AS FLOAT64) AS dk_points
        FROM `{settings.features}.player_week_actuals` a
        JOIN `{settings.raw}.schedules` s
          ON s.season = a.season AND s.week = a.week
         AND a.team IN (s.home_team, s.away_team)
        JOIN roster r
          ON r.season = a.season AND r.week = a.week
         AND r.gsis_id = a.gsis_id
        WHERE a.season = 2025 AND s.game_type = 'REG' AND a.has_stat_line
          AND r.position IN ('QB', 'RB', 'FB', 'WR', 'TE')
        ORDER BY s.game_id, a.gsis_id
    """)
    dst = query_df(f"""
        SELECT s.game_id, d.team, CAST(d.dst_dk_points AS FLOAT64) AS dk_points
        FROM `{settings.features}.team_defense_week` d
        JOIN `{settings.raw}.schedules` s
          ON s.season = d.season AND s.week = d.week
         AND d.team IN (s.home_team, s.away_team)
        WHERE d.season = 2025 AND s.game_type = 'REG'
        ORDER BY s.game_id, d.team
    """)
    if skill.empty or dst.empty or skill[["game_id", "player_id"]].duplicated().any() or dst[["game_id", "team"]].duplicated().any():
        raise ValueError("overtime authoritative actual identity is invalid")
    return skill, dst


def _load_pbp(game_ids: list[str]) -> pd.DataFrame:
    if not game_ids:
        return pd.DataFrame()
    frame = query_df(f"""
        SELECT *
        FROM `{settings.raw}.pbp`
        WHERE game_id IN UNNEST(@game_ids)
        ORDER BY season, week, game_id, play_id
    """, params={"game_ids": game_ids})
    if frame.empty or set(frame.game_id.astype(str)) != set(game_ids):
        raise ValueError("overtime PBP game coverage differs")
    if frame[["game_id", "play_id"]].dropna().duplicated().any():
        raise ValueError("overtime PBP play identity repeats")
    return frame


def _score_game_delta(
    game_pbp: pd.DataFrame,
    actual_skill: pd.DataFrame | None = None,
    actual_dst: pd.DataFrame | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    game_id = str(game_pbp.game_id.iloc[0])
    regulation_pbp = game_pbp.loc[pd.to_numeric(game_pbp.qtr, errors="coerce").le(4)].copy()
    overtime_pbp = game_pbp.loc[pd.to_numeric(game_pbp.qtr, errors="coerce").gt(4)].copy()
    if regulation_pbp.empty or overtime_pbp.empty:
        raise ValueError(f"overtime game {game_id} has invalid period coverage")
    full_skill, full_skill_receipt = score_skill_players(game_pbp)
    regulation_skill, regulation_skill_receipt = score_skill_players(regulation_pbp)
    full_dst, full_dst_receipt = score_team_defenses(game_pbp)
    regulation_dst, regulation_dst_receipt = score_team_defenses(regulation_pbp)

    if actual_skill is not None:
        players = actual_skill[["player_id", "position", "dk_points"]].copy()
        players["player_id"] = players.player_id.astype(str)
        full_map = dict(zip(full_skill.player_id.astype(str), full_skill.dk_points, strict=True))
        reg_map = dict(zip(regulation_skill.player_id.astype(str), regulation_skill.dk_points, strict=True))
        players["full"] = players.player_id.map(full_map).fillna(0.0)
        players["regulation"] = players.player_id.map(reg_map).fillna(0.0)
        parity_delta = (players.full - players.dk_points.astype(float)).abs()
        if float(parity_delta.max()) > 1e-6:
            raise ValueError(f"overtime game {game_id} skill scorer parity failed")
    else:
        ids = sorted(set(full_skill.player_id.astype(str)) | set(regulation_skill.player_id.astype(str)))
        full_map = dict(zip(full_skill.player_id.astype(str), full_skill.dk_points, strict=True))
        reg_map = dict(zip(regulation_skill.player_id.astype(str), regulation_skill.dk_points, strict=True))
        players = pd.DataFrame({"player_id": ids, "position": "unknown"})
        players["full"] = players.player_id.map(full_map).fillna(0.0)
        players["regulation"] = players.player_id.map(reg_map).fillna(0.0)
        parity_delta = pd.Series(dtype=float)
    players["delta"] = players.full - players.regulation

    if actual_dst is not None:
        defenses = actual_dst[["team", "dk_points"]].copy()
        full_dst_map = dict(zip(full_dst.team.astype(str), full_dst.dk_points, strict=True))
        reg_dst_map = dict(zip(regulation_dst.team.astype(str), regulation_dst.dk_points, strict=True))
        defenses["full"] = defenses.team.map(full_dst_map)
        defenses["regulation"] = defenses.team.map(reg_dst_map)
        if defenses[["full", "regulation"]].isna().any().any() or float((defenses.full - defenses.dk_points.astype(float)).abs().max()) > 1e-6:
            raise ValueError(f"overtime game {game_id} DST scorer parity failed")
    else:
        defenses = full_dst[["team", "dk_points"]].rename(columns={"dk_points": "full"})
        defenses["regulation"] = defenses.team.map(dict(zip(regulation_dst.team, regulation_dst.dk_points, strict=True)))
    defenses["delta"] = defenses.full - defenses.regulation

    merged_components = full_skill.merge(
        regulation_skill, on="player_id", how="outer", suffixes=("_full", "_reg"),
    ).fillna(0.0)
    bonus_crossings = {
        "passing_300": int(((merged_components.pass_yards_reg < 300) & (merged_components.pass_yards_full >= 300)).sum()),
        "rushing_100": int(((merged_components.rush_yards_reg < 100) & (merged_components.rush_yards_full >= 100)).sum()),
        "receiving_100": int(((merged_components.rec_yards_reg < 100) & (merged_components.rec_yards_full >= 100)).sum()),
    }
    overtime_drives = overtime_pbp.loc[overtime_pbp.posteam.notna(), ["posteam", "drive"]].drop_duplicates()
    regular_season = set(overtime_pbp.season_type.astype(str)) == {"REG"}
    period_seconds = 600 if regular_season else 900
    elapsed_seconds = 0.0
    for _quarter, period in overtime_pbp.groupby("qtr", sort=True):
        remaining = pd.to_numeric(period.quarter_seconds_remaining, errors="coerce")
        if remaining.notna().any():
            elapsed_seconds += period_seconds - float(remaining.min())
    position_delta = {
        position: float(players.loc[players.position.eq(position), "delta"].sum())
        for position in SKILL_POSITIONS if players.position.eq(position).any()
    }
    top_full = np.sort(players.full.to_numpy(float))[::-1]
    top_reg = np.sort(players.regulation.to_numpy(float))[::-1]
    game = {
        "game_id": game_id,
        "season": int(game_pbp.season.iloc[0]),
        "week": int(game_pbp.week.iloc[0]),
        "skill_full": float(players.full.sum()),
        "skill_regulation": float(players.regulation.sum()),
        "skill_delta": float(players.delta.sum()),
        "dst_full": float(defenses.full.sum()),
        "dst_regulation": float(defenses.regulation.sum()),
        "dst_delta": float(defenses.delta.sum()),
        "top_one_skill_delta": float(top_full[:1].sum() - top_reg[:1].sum()),
        "top_three_skill_delta": float(top_full[:3].sum() - top_reg[:3].sum()),
        "players_gaining_at_least_3": int(players.delta.ge(3).sum()),
        "players_gaining_at_least_6": int(players.delta.ge(6).sum()),
        "players_gaining_at_least_10": int(players.delta.ge(10).sum()),
        "maximum_player_delta": float(players.delta.max()),
        "position_skill_delta": position_delta,
        "bonus_crossings": bonus_crossings,
        "ot_rows": int(len(overtime_pbp)),
        "ot_offensive_plays": int(overtime_pbp.play_type.isin(["pass", "run"]).sum()),
        "ot_possessions": int(len(overtime_drives)),
        "ot_possessions_by_team": {
            str(team): int(len(group)) for team, group in overtime_drives.groupby("posteam")
        },
        "ot_elapsed_seconds": elapsed_seconds,
        "skill_parity_max_abs_delta": float(parity_delta.max()) if not parity_delta.empty else None,
        "receipts": {
            "full_skill": full_skill_receipt,
            "regulation_skill": regulation_skill_receipt,
            "full_dst": full_dst_receipt,
            "regulation_dst": regulation_dst_receipt,
        },
    }
    player_rows = players[["player_id", "position", "full", "regulation", "delta"]].to_dict("records")
    return game, player_rows


def _observational_game_metrics(skill: pd.DataFrame, schedules: pd.DataFrame) -> dict[str, Any]:
    def summarize(group: pd.DataFrame) -> pd.Series:
        scores = np.sort(group.dk_points.astype(float).to_numpy())[::-1]
        return pd.Series({
            "skill_total": float(scores.sum()),
            "top_one": float(scores[:1].sum()),
            "top_three": float(scores[:3].sum()),
            "players_ge_20": int((scores >= 20).sum()),
            "players_ge_25": int((scores >= 25).sum()),
            "players_ge_30": int((scores >= 30).sum()),
        })

    metrics = skill.groupby("game_id", sort=True).apply(summarize, include_groups=False).reset_index()
    market = schedules.loc[
        schedules.season.astype(int).eq(2025) & schedules.game_type.eq("REG"),
        ["game_id", "overtime", "spread_line", "total_line"],
    ]
    frame = market.merge(metrics, on="game_id", how="inner", validate="one_to_one")
    if len(frame) != len(market):
        raise ValueError("overtime observational game coverage differs")
    missing_market = frame[["spread_line", "total_line"]].isna().any(axis=1)
    excluded = frame.loc[missing_market, "game_id"].astype(str).tolist()
    frame = frame.loc[~missing_market].copy()
    result: dict[str, Any] = {
        "games": int(len(frame)),
        "excluded_missing_market": excluded,
        "metrics": {},
    }
    design = np.column_stack([
        np.ones(len(frame)), frame.overtime.astype(float),
        frame.spread_line.astype(float).abs(), frame.total_line.astype(float),
    ])
    for metric in ("skill_total", "top_one", "top_three", "players_ge_20", "players_ge_25", "players_ge_30"):
        values = frame[metric].astype(float).to_numpy()
        coefficient = np.linalg.lstsq(design, values, rcond=None)[0]
        ot = frame.overtime.astype(int).eq(1)
        result["metrics"][metric] = {
            "overtime_mean": float(frame.loc[ot, metric].mean()),
            "non_overtime_mean": float(frame.loc[~ot, metric].mean()),
            "raw_difference": float(frame.loc[ot, metric].mean() - frame.loc[~ot, metric].mean()),
            "adjusted_overtime_coefficient": float(coefficient[1]),
        }
    return result


def evaluate_uplift(schedules: pd.DataFrame) -> dict[str, Any]:
    skill, dst = _load_regular_actuals()
    regular_ot = schedules.loc[
        schedules.season.astype(int).eq(2025)
        & schedules.game_type.eq("REG")
        & schedules.overtime.astype(int).eq(1)
    ].copy()
    postseason_ot = schedules.loc[
        schedules.season.astype(int).between(2022, 2025)
        & ~schedules.game_type.eq("REG")
        & schedules.overtime.astype(int).eq(1)
    ].copy()
    all_ot_ids = regular_ot.game_id.astype(str).tolist() + postseason_ot.game_id.astype(str).tolist()
    pbp = _load_pbp(all_ot_ids)
    game_rows, player_rows = [], []
    for game_id in regular_ot.game_id.astype(str):
        game, players = _score_game_delta(
            pbp.loc[pbp.game_id.astype(str).eq(game_id)].copy(),
            skill.loc[skill.game_id.astype(str).eq(game_id)].copy(),
            dst.loc[dst.game_id.astype(str).eq(game_id)].copy(),
        )
        schedule_row = regular_ot.loc[regular_ot.game_id.astype(str).eq(game_id)].iloc[0]
        game["sunday_main_window"] = bool(
            str(schedule_row.weekday).lower().startswith("sun")
            and "13:00" <= str(schedule_row.gametime) <= "16:30"
        )
        game_rows.append(game)
        for row in players:
            player_rows.append({"game_id": game_id, **row})
    postseason_rows = []
    for game_id in postseason_ot.game_id.astype(str):
        game, _players = _score_game_delta(
            pbp.loc[pbp.game_id.astype(str).eq(game_id)].copy(),
        )
        game["authoritative_parity_available"] = False
        postseason_rows.append(game)
    games = pd.DataFrame(game_rows)
    if len(games) != len(regular_ot):
        raise ValueError("overtime current-rule uplift game coverage differs")
    aggregates = {
        "games": int(len(games)),
        "sunday_main_window_games": int(games.sunday_main_window.sum()),
        "mean_skill_delta": float(games.skill_delta.mean()),
        "median_skill_delta": float(games.skill_delta.median()),
        "total_skill_delta": float(games.skill_delta.sum()),
        "mean_dst_delta": float(games.dst_delta.mean()),
        "mean_top_one_skill_delta": float(games.top_one_skill_delta.mean()),
        "mean_top_three_skill_delta": float(games.top_three_skill_delta.mean()),
        "maximum_player_delta": float(games.maximum_player_delta.max()),
        "total_bonus_crossings": {
            label: int(sum(row["bonus_crossings"][label] for row in game_rows))
            for label in ("passing_300", "rushing_100", "receiving_100")
        },
    }
    return {
        "current_rule_2025_regular": {
            "aggregate": aggregates,
            "games": game_rows,
            "players": player_rows,
            "fixed_selected_lineup_book": {
                "available": False,
                "reason": "not joined in this mechanism pass",
            },
        },
        "observational_2025_regular": _observational_game_metrics(skill, schedules),
        "postseason_2022_2025_separate_unreconciled": {
            "games": postseason_rows,
            "cannot_license_regular_season": True,
        },
        "sources": {
            "regular_skill_rows": int(len(skill)),
            "regular_dst_rows": int(len(dst)),
            "pbp_rows": int(len(pbp)),
            "skill_sha256": _frame_sha256(skill),
            "dst_sha256": _frame_sha256(dst),
            "pbp_sha256": _frame_sha256(pbp),
        },
    }


def run(output: Path) -> dict[str, Any]:
    _protocol_check()
    if output.exists():
        raise ValueError(f"refusing to overwrite overtime result: {output}")
    schedules = load_schedules()
    first = {
        "predictability": evaluate_predictability(schedules),
        "uplift": evaluate_uplift(schedules),
    }
    second_prediction = evaluate_predictability(schedules)
    second_uplift = evaluate_uplift(schedules)
    prediction_repeat = _canonical_json(first["predictability"]) == _canonical_json(second_prediction)
    uplift_repeat = _canonical_json(first["uplift"]) == _canonical_json(second_uplift)
    invariants = {
        "protocol_sha256": PROTOCOL_SHA256,
        "schedule_rows": int(len(schedules)),
        "schedule_sha256": _frame_sha256(schedules),
        "prediction_bit_exact_on_repeat": prediction_repeat,
        "uplift_bit_exact_on_repeat": uplift_repeat,
        "pre_2022_seasons_used": [],
        "current_rule_uplift_seasons": [2025],
        "predictor_training_seasons": list(TRAIN_SEASONS),
        "predictor_heldout_seasons": [HELDOUT_SEASON],
    }
    invariants["passes"] = bool(prediction_repeat and uplift_repeat)
    predictive = bool(first["predictability"]["passes_frozen_predictability_gate"] and invariants["passes"])
    report = {
        "version": VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "invariants": invariants,
        **first,
        "disposition": "predictive" if predictive else "non-predictive-or-inconclusive",
        "prospective_duration_shadow_licensed": predictive,
        "production_change_licensed": False,
        "expected_points_addition_licensed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps({
        "output": str(output), "disposition": report["disposition"],
        "report_sha256": sha256(output.read_bytes()).hexdigest(),
    }, sort_keys=True))
    return report


__all__ = [
    "evaluate_predictability", "evaluate_uplift", "load_schedules", "run",
]
