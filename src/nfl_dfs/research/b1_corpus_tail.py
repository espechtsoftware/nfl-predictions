"""Frozen candidate-tail model and exact-80 shadow mechanics.

The model learns only from pre-lock attributes of actually generated B1
rosters.  Realized lineup score is a label; winner identity/score is neither a
feature nor a target.  Historical evaluation is season-held-out and may only
license the default-off prospective shadow defined here.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss


MODEL_VERSION = "b1-corpus-tail-logit-v1"
POLICY_VERSION = "b1-corpus-tail-exact80-shadow-v1"
PRIMARY_THRESHOLD = 200.0
SECONDARY_THRESHOLD = 210.0
PROTECTED_THRESHOLD = 194.0
ENTRIES = 80
MAX_SHARED_PLAYERS = 7
PROSPECTIVE_WEEKS = tuple(range(1, 7))
FORBIDDEN_MODEL_FIELDS = frozenset({
    "actual", "actual_score", "actual_rank", "winner", "winner_score",
    "winner_roster", "rank", "payout", "winnings", "roi",
})

# Fixed before the historical read.  Panel identities, generator tags,
# selected flags and realized ownership are deliberately excluded: they are
# either non-portable across seasons or downstream consequences of an old
# selector.
FEATURE_COLUMNS = (
    "salary_k",
    "p_line_mean", "p_line_max",
    "sim_mean_mean", "sim_mean_max",
    "sim_sd_mean",
    "sim_q50_mean",
    "sim_q90_mean", "sim_q90_max",
    "sim_q99_mean", "sim_q99_max",
    "sim_rank_percentile_mean", "sim_rank_percentile_max",
    "log1p_appearances",
    "games_represented", "teams_represented",
    "largest_team_block", "largest_game_block",
    "qb_stack_count", "bring_back_count",
    "qb_salary_k", "rb_salary_k", "wr_salary_k", "te_salary_k",
    "dst_salary_k", "flex_is_wr", "flex_is_te",
)


class CorpusTailError(ValueError):
    """Fail-closed contract error for the frozen candidate-tail lane."""


def canonical_roster(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple, np.ndarray)):
        values = [str(item).strip() for item in value]
    else:
        values = [part.strip() for part in str(value).split(",")]
    ids = tuple(sorted(item for item in values if item))
    if len(ids) != 9 or len(set(ids)) != 9:
        raise CorpusTailError("candidate roster must contain nine unique players")
    return ids


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="raise").astype(float)
    if not np.isfinite(values).all():
        raise CorpusTailError(f"candidate field {column} contains non-finite values")
    return values


def _roster_structure(
    season: int,
    week: int,
    roster: tuple[str, ...],
    lookup: Mapping[tuple[int, int, str], Mapping[str, Any]],
) -> dict[str, Any]:
    rows = []
    for player_id in roster:
        key = season, week, player_id
        if key not in lookup:
            raise CorpusTailError(f"roster player is absent from catalog: {key}")
        rows.append(lookup[key])
    positions = Counter(str(row["pos"]).upper() for row in rows)
    if (
        positions["QB"] != 1 or positions["DST"] != 1
        or positions["RB"] not in {2, 3}
        or positions["WR"] not in {3, 4}
        or positions["TE"] not in {1, 2}
    ):
        raise CorpusTailError("candidate roster fails DK classic position shape")
    qb = next(row for row in rows if str(row["pos"]).upper() == "QB")
    team_counts = Counter(
        str(row["team"]) for row in rows if str(row["pos"]).upper() != "DST"
    )
    game_counts = Counter(str(row["game_id"]) for row in rows)
    salary_by_pos = {
        pos: sum(
            int(row["salary"]) for row in rows
            if str(row["pos"]).upper() == pos
        )
        for pos in ("QB", "RB", "WR", "TE", "DST")
    }
    salary = sum(int(row["salary"]) for row in rows)
    flex = "WR" if positions["WR"] == 4 else "TE" if positions["TE"] == 2 else "RB"
    return {
        "salary": salary,
        "salary_k": salary / 1_000.0,
        "games_represented": len(game_counts),
        "teams_represented": len({str(row["team"]) for row in rows}),
        "largest_team_block": max(team_counts.values()),
        "largest_game_block": max(game_counts.values()),
        "qb_stack_count": sum(
            str(row["team"]) == str(qb["team"])
            and str(row["pos"]).upper() in {"RB", "WR", "TE"}
            for row in rows
        ),
        "bring_back_count": sum(
            str(row["team"]) == str(qb["opp"])
            and str(row["pos"]).upper() in {"RB", "WR", "TE"}
            for row in rows
        ),
        **{f"{pos.lower()}_salary_k": value / 1_000.0
           for pos, value in salary_by_pos.items()},
        "flex_is_wr": int(flex == "WR"),
        "flex_is_te": int(flex == "TE"),
    }


def build_deduplicated_dataset(
    candidates: pd.DataFrame,
    players: pd.DataFrame,
    *,
    canonical_panel: str,
    include_outcomes: bool,
) -> pd.DataFrame:
    """Return one strictly pre-lock feature row per slate/roster.

    Repeated appearances are collapsed with fixed mean/max summaries.  The
    historical label is admitted only when ``include_outcomes`` is explicit.
    """
    candidate_fields = {
        "panel_run_id", "season", "week", "cand_ix", "players", "tag",
        "selected", "selected_rank", "salary", "p_line", "sim_mean",
        "sim_sd", "sim_q50", "sim_q90", "sim_q99", "sim_rank_p_line",
    }
    if include_outcomes:
        candidate_fields.add("actual_score")
    missing = candidate_fields - set(candidates)
    if missing:
        raise CorpusTailError(f"candidate source lacks fields: {sorted(missing)}")
    player_fields = {"season", "week", "id", "pos", "team", "opp", "game_id", "salary"}
    missing = player_fields - set(players)
    if missing:
        raise CorpusTailError(f"player source lacks fields: {sorted(missing)}")
    if not include_outcomes and FORBIDDEN_MODEL_FIELDS & set(candidates):
        forbidden = sorted(FORBIDDEN_MODEL_FIELDS & set(candidates))
        raise CorpusTailError(f"outcome-blind source contains forbidden fields: {forbidden}")
    if candidates.empty or players.empty:
        raise CorpusTailError("candidate-tail source is empty")
    if candidates.duplicated(["panel_run_id", "season", "week", "cand_ix"]).any():
        raise CorpusTailError("candidate source repeats a panel/slate/candidate key")
    if players.duplicated(["season", "week", "id"]).any():
        raise CorpusTailError("player catalog repeats a slate/player key")

    work = candidates.copy()
    for column in (
        "salary", "p_line", "sim_mean", "sim_sd", "sim_q50", "sim_q90",
        "sim_q99", "sim_rank_p_line",
    ):
        work[column] = _numeric(work, column)
    if include_outcomes:
        work["actual_score"] = _numeric(work, "actual_score")
    work["season"] = pd.to_numeric(work.season, errors="raise").astype(int)
    work["week"] = pd.to_numeric(work.week, errors="raise").astype(int)
    work["roster"] = work.players.map(canonical_roster)
    work["roster_key"] = work.roster.map(lambda ids: ",".join(ids))
    panel_size = work.groupby(["panel_run_id", "season", "week"])["cand_ix"].transform("size")
    if (panel_size < 2).any():
        raise CorpusTailError("candidate panel/slate has fewer than two rows")
    work["sim_rank_percentile"] = 1.0 - (
        (work.sim_rank_p_line - 1.0) / (panel_size - 1.0)
    )
    if ((work.sim_rank_percentile < -1e-12) | (work.sim_rank_percentile > 1 + 1e-12)).any():
        raise CorpusTailError("sim_rank_p_line is outside its panel")

    lookup: dict[tuple[int, int, str], dict[str, Any]] = {}
    for row in players.itertuples(index=False):
        salary = int(row.salary)
        if salary <= 0:
            raise CorpusTailError("player catalog contains nonpositive salary")
        lookup[(int(row.season), int(row.week), str(row.id))] = {
            "pos": str(row.pos).upper(), "team": str(row.team),
            "opp": str(row.opp), "game_id": str(row.game_id), "salary": salary,
        }

    records: list[dict[str, Any]] = []
    group_columns = ["season", "week", "roster_key"]
    for (season, week, roster_key), group in work.groupby(group_columns, sort=True):
        group = group.sort_values(["panel_run_id", "cand_ix"], kind="stable")
        roster = tuple(str(roster_key).split(","))
        structure = _roster_structure(int(season), int(week), roster, lookup)
        reported = group.salary.to_numpy(float)
        if not np.allclose(reported, structure["salary"], rtol=0.0, atol=0.0):
            raise CorpusTailError("candidate salary differs from canonical catalog")
        canonical = group[group.panel_run_id.astype(str).eq(canonical_panel)]
        if len(canonical) > 1:
            raise CorpusTailError("canonical panel repeats a slate roster")
        selected_rank = None
        canonical_selected = False
        canonical_cand_ix = None
        if len(canonical):
            c = canonical.iloc[0]
            canonical_selected = bool(c.selected)
            canonical_cand_ix = int(c.cand_ix)
            if canonical_selected:
                selected_rank = int(c.selected_rank)
                if selected_rank < 0:
                    raise CorpusTailError("canonical selected row has negative rank")
        record: dict[str, Any] = {
            "season": int(season), "week": int(week),
            "roster_key": str(roster_key), "players": list(roster),
            **structure,
            "appearances": len(group),
            "log1p_appearances": math.log1p(len(group)),
            "source_panel_count": int(group.panel_run_id.nunique()),
            "source_panels": sorted(set(group.panel_run_id.astype(str))),
            "source_tags": sorted(set(group.tag.fillna("missing").astype(str))),
            "selected_any": bool(group.selected.fillna(False).astype(bool).any()),
            "canonical_candidate": bool(len(canonical)),
            "canonical_cand_ix": canonical_cand_ix,
            "canonical_selected": canonical_selected,
            "canonical_selected_rank": selected_rank,
        }
        for column in ("p_line", "sim_mean", "sim_q90", "sim_q99", "sim_rank_percentile"):
            values = group[column].to_numpy(float)
            record[f"{column}_mean"] = float(values.mean())
            record[f"{column}_max"] = float(values.max())
        for column in ("sim_sd", "sim_q50"):
            record[f"{column}_mean"] = float(group[column].mean())
        if include_outcomes:
            scores = group.actual_score.to_numpy(float)
            if not np.allclose(scores, scores[0], rtol=0.0, atol=1e-6):
                raise CorpusTailError("repeated roster has inconsistent actual score")
            record["actual_score"] = float(scores[0])
            record["target_ge200"] = bool(scores[0] >= PRIMARY_THRESHOLD)
            record["target_ge210"] = bool(scores[0] >= SECONDARY_THRESHOLD)
        records.append(record)
    result = pd.DataFrame(records).sort_values(group_columns, kind="stable").reset_index(drop=True)
    if result.duplicated(group_columns).any():
        raise CorpusTailError("deduplicated dataset repeats a slate roster")
    for column in FEATURE_COLUMNS:
        if column not in result or not np.isfinite(pd.to_numeric(result[column], errors="raise")).all():
            raise CorpusTailError(f"model feature is absent or non-finite: {column}")
    return result


def _matrix(frame: pd.DataFrame) -> np.ndarray:
    if FORBIDDEN_MODEL_FIELDS & set(FEATURE_COLUMNS):
        raise CorpusTailError("frozen feature list contains an outcome field")
    missing = set(FEATURE_COLUMNS) - set(frame)
    if missing:
        raise CorpusTailError(f"model frame lacks features: {sorted(missing)}")
    return frame.loc[:, FEATURE_COLUMNS].apply(pd.to_numeric, errors="raise").to_numpy(float)


def fit_tail_model(frame: pd.DataFrame) -> dict[str, Any]:
    """Fit the one fixed, portable logistic model for ``score >= 200``."""
    if "actual_score" not in frame:
        raise CorpusTailError("model fitting requires the historical score label")
    y = pd.to_numeric(frame.actual_score, errors="raise").ge(PRIMARY_THRESHOLD).to_numpy(int)
    if len(np.unique(y)) != 2:
        raise CorpusTailError("training fold does not contain both target classes")
    x = _matrix(frame)
    medians = np.nanmedian(x, axis=0)
    x = np.where(np.isfinite(x), x, medians)
    means = x.mean(axis=0)
    scales = x.std(axis=0)
    scales[scales == 0] = 1.0
    z = (x - means) / scales
    slate_sizes = frame.groupby(["season", "week"])["roster_key"].transform("size").to_numpy(float)
    sample_weight = 1.0 / slate_sizes
    sample_weight *= len(sample_weight) / sample_weight.sum()
    model = LogisticRegression(
        C=1.0, solver="lbfgs", class_weight=None,
        max_iter=2_000, random_state=20260820,
    )
    model.fit(z, y, sample_weight=sample_weight)
    artifact = {
        "version": MODEL_VERSION,
        "target": "actual_score_ge_200",
        "target_threshold": PRIMARY_THRESHOLD,
        "feature_columns": list(FEATURE_COLUMNS),
        "impute_medians": medians.tolist(),
        "standardize_means": means.tolist(),
        "standardize_scales": scales.tolist(),
        "coefficients": model.coef_[0].astype(float).tolist(),
        "intercept": float(model.intercept_[0]),
        "training_rows": len(frame),
        "training_slates": int(frame[["season", "week"]].drop_duplicates().shape[0]),
        "training_seasons": sorted(map(int, frame.season.unique())),
        "training_prevalence_ge200": float(y.mean()),
        "fixed_estimator": {
            "type": "sklearn.linear_model.LogisticRegression",
            "C": 1.0, "solver": "lbfgs", "penalty": "l2",
            "class_weight": None, "max_iter": 2_000,
            "sample_weight": "each season-week has equal total weight",
        },
        "winner_fields_used": [],
        "production_licensed": False,
        "prospective_shadow_only": True,
    }
    artifact["artifact_sha256"] = artifact_sha256(artifact)
    return artifact


def artifact_sha256(artifact: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in artifact.items() if key != "artifact_sha256"}
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return sha256(raw).hexdigest()


def predict_tail_score(frame: pd.DataFrame, artifact: Mapping[str, Any]) -> np.ndarray:
    if artifact.get("version") != MODEL_VERSION:
        raise CorpusTailError("tail model artifact version differs")
    if tuple(artifact.get("feature_columns", ())) != FEATURE_COLUMNS:
        raise CorpusTailError("tail model artifact feature order differs")
    if artifact.get("winner_fields_used") != [] or artifact.get("production_licensed") is not False:
        raise CorpusTailError("tail model artifact crosses its scientific boundary")
    if artifact.get("artifact_sha256") != artifact_sha256(artifact):
        raise CorpusTailError("tail model artifact hash differs")
    x = _matrix(frame)
    medians = np.asarray(artifact["impute_medians"], dtype=float)
    means = np.asarray(artifact["standardize_means"], dtype=float)
    scales = np.asarray(artifact["standardize_scales"], dtype=float)
    coefficients = np.asarray(artifact["coefficients"], dtype=float)
    if any(len(value) != len(FEATURE_COLUMNS) for value in (medians, means, scales, coefficients)):
        raise CorpusTailError("tail model artifact vector length differs")
    x = np.where(np.isfinite(x), x, medians)
    return expit(((x - means) / scales) @ coefficients + float(artifact["intercept"]))


def season_oof_predictions(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return LOSO predictions plus the chronological walk-forward companion."""
    seasons = sorted(map(int, frame.season.unique()))
    if len(seasons) < 3:
        raise CorpusTailError("season-held-out evaluation requires at least three seasons")
    loso = []
    for season in seasons:
        train = frame[frame.season.astype(int).ne(season)]
        test = frame[frame.season.astype(int).eq(season)].copy()
        artifact = fit_tail_model(train)
        test["tail_score"] = predict_tail_score(test, artifact)
        test["fold"] = f"loso-{season}"
        test["fold_train_prevalence"] = artifact["training_prevalence_ge200"]
        loso.append(test)
    walk = []
    for season in seasons[1:]:
        train = frame[frame.season.astype(int).lt(season)]
        test = frame[frame.season.astype(int).eq(season)].copy()
        artifact = fit_tail_model(train)
        test["tail_score"] = predict_tail_score(test, artifact)
        test["fold"] = f"walk-forward-{season}"
        test["fold_train_prevalence"] = artifact["training_prevalence_ge200"]
        walk.append(test)
    return (
        pd.concat(loso, ignore_index=True).sort_values(
            ["season", "week", "roster_key"], kind="stable").reset_index(drop=True),
        pd.concat(walk, ignore_index=True).sort_values(
            ["season", "week", "roster_key"], kind="stable").reset_index(drop=True),
    )


def select_exact80(
    candidates: pd.DataFrame,
    *,
    score_column: str = "tail_score",
    entries: int = ENTRIES,
    max_shared_players: int = MAX_SHARED_PLAYERS,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Stable top-score selection with a fixed overlap pass and backfill."""
    if len(candidates) < entries or candidates.roster_key.duplicated().any():
        raise CorpusTailError("exact-80 candidate pool is short or repeats rosters")
    ranked = candidates.assign(
        _score=pd.to_numeric(candidates[score_column], errors="raise"),
        _p=pd.to_numeric(candidates.p_line_max, errors="raise"),
        _q=pd.to_numeric(candidates.sim_q99_max, errors="raise"),
        _m=pd.to_numeric(candidates.sim_mean_max, errors="raise"),
    ).sort_values(
        ["_score", "_p", "_q", "_m", "roster_key"],
        ascending=[False, False, False, False, True], kind="stable",
    )
    rosters = {key: frozenset(str(key).split(",")) for key in ranked.roster_key}
    selected: list[str] = []
    rejected = 0
    for key in ranked.roster_key:
        if all(len(rosters[key] & rosters[prior]) <= max_shared_players for prior in selected):
            selected.append(str(key))
            if len(selected) == entries:
                break
        else:
            rejected += 1
    backfills = 0
    if len(selected) < entries:
        for key in ranked.roster_key:
            key = str(key)
            if key not in selected:
                selected.append(key)
                backfills += 1
                if len(selected) == entries:
                    break
    if len(selected) != entries or len(set(selected)) != entries:
        raise CorpusTailError("exact-80 challenger could not fill its budget")
    order = {key: rank for rank, key in enumerate(selected)}
    picked = ranked[ranked.roster_key.isin(order)].copy()
    picked["challenger_rank"] = picked.roster_key.map(order)
    picked = picked.sort_values("challenger_rank", kind="stable").drop(
        columns=["_score", "_p", "_q", "_m"])
    return picked, {
        "candidate_budget": len(candidates), "entry_budget": entries,
        "max_shared_players_first_pass": max_shared_players,
        "overlap_rejections_before_fill": rejected,
        "deterministic_backfills": backfills,
    }


def _metric_block(frame: pd.DataFrame) -> dict[str, Any]:
    y200 = frame.actual_score.ge(PRIMARY_THRESHOLD).to_numpy(int)
    y210 = frame.actual_score.ge(SECONDARY_THRESHOLD).to_numpy(int)
    score = frame.tail_score.to_numpy(float)
    baseline = frame.p_line_max.to_numpy(float)
    prevalence_prediction = frame.fold_train_prevalence.to_numpy(float)
    rho = spearmanr(score, frame.actual_score.to_numpy(float)).statistic
    return {
        "rows": len(frame),
        "slates": int(frame[["season", "week"]].drop_duplicates().shape[0]),
        "prevalence_ge200": float(y200.mean()),
        "prevalence_ge210": float(y210.mean()),
        "average_precision_ge200": float(average_precision_score(y200, score)),
        "p_line_average_precision_ge200": float(average_precision_score(y200, baseline)),
        "average_precision_ge210": float(average_precision_score(y210, score)),
        "p_line_average_precision_ge210": float(average_precision_score(y210, baseline)),
        "brier_ge200": float(brier_score_loss(y200, score)),
        "fold_prevalence_brier_ge200": float(brier_score_loss(y200, prevalence_prediction)),
        "spearman_tail_score_vs_actual": float(rho),
        "mean_predicted_ge200": float(score.mean()),
    }


def _book_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    maxima = np.asarray([float(row["weekly_max"]) for row in rows], dtype=float)
    return {
        "slates": len(rows), "mean_weekly_max": float(maxima.mean()),
        "median_weekly_max": float(np.median(maxima)),
        "maximum": float(maxima.max()),
        "threshold_counts": {
            str(int(line)): int((maxima >= line).sum())
            for line in (187.0, 194.0, 200.0, 210.0, 220.0, 230.0, 240.0)
        },
    }


def evaluate_exact80(frame: pd.DataFrame) -> dict[str, Any]:
    """Compare OOF challenger with current and naive exact-80 controls."""
    rows = {"control": [], "challenger": [], "naive_p_line": []}
    slate_receipts = []
    for (season, week), slate_all in frame.groupby(["season", "week"], sort=True):
        pool = slate_all[slate_all.canonical_candidate].copy()
        control = pool[pool.canonical_selected].sort_values(
            "canonical_selected_rank", kind="stable")
        ranks = pd.to_numeric(control.canonical_selected_rank, errors="raise").astype(int).tolist()
        if len(control) != ENTRIES or ranks != list(range(ENTRIES)):
            raise CorpusTailError("canonical control is not ranked exact-80")
        challenger, challenger_receipt = select_exact80(pool)
        naive_input = pool.assign(naive_score=pool.p_line_max)
        naive, naive_receipt = select_exact80(naive_input, score_column="naive_score")
        for name, book in (("control", control), ("challenger", challenger), ("naive_p_line", naive)):
            rows[name].append({
                "season": int(season), "week": int(week),
                "weekly_max": float(book.actual_score.max()),
            })
        slate_receipts.append({
            "season": int(season), "week": int(week),
            "candidate_budget_control": len(pool),
            "candidate_budget_challenger": len(pool),
            "entries_control": len(control), "entries_challenger": len(challenger),
            "challenger_control_overlap": len(set(challenger.roster_key) & set(control.roster_key)),
            "challenger_redundancy": challenger_receipt,
            "naive_redundancy": naive_receipt,
        })
    summary = {name: _book_summary(value) for name, value in rows.items()}
    control = summary["control"]
    treatment = summary["challenger"]
    gates = {
        "equal_candidate_and_entry_budgets": all(
            row["candidate_budget_control"] == row["candidate_budget_challenger"]
            and row["entries_control"] == row["entries_challenger"] == ENTRIES
            for row in slate_receipts
        ),
        "mean_weekly_max_improves": treatment["mean_weekly_max"] > control["mean_weekly_max"],
        "ge200_count_improves": treatment["threshold_counts"]["200"] > control["threshold_counts"]["200"],
        "ge210_count_noninferior": treatment["threshold_counts"]["210"] >= control["threshold_counts"]["210"],
        "ge194_count_protected": treatment["threshold_counts"]["194"] >= control["threshold_counts"]["194"],
    }
    return {"books": summary, "slates": slate_receipts, "selection_gates": gates}


def historical_evaluation(frame: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    loso, walk = season_oof_predictions(frame)
    loso_metrics = _metric_block(loso)
    walk_metrics = _metric_block(walk)
    exact80 = evaluate_exact80(loso)
    prediction_gates = {
        "ge200_pr_beats_prevalence": (
            loso_metrics["average_precision_ge200"] > loso_metrics["prevalence_ge200"]
        ),
        "ge200_pr_beats_p_line": (
            loso_metrics["average_precision_ge200"]
            > loso_metrics["p_line_average_precision_ge200"]
        ),
        # >=210 is a sparse companion label for the >=200 model.  Require
        # information above chance here; its portfolio-level count is the
        # separately protected competitive comparison below.
        "ge210_pr_beats_prevalence": (
            loso_metrics["average_precision_ge210"]
            > loso_metrics["prevalence_ge210"]
        ),
        "positive_brier_skill_vs_fold_prevalence": (
            loso_metrics["brier_ge200"]
            < loso_metrics["fold_prevalence_brier_ge200"]
        ),
    }
    all_gates = {**prediction_gates, **exact80["selection_gates"]}
    passed = all(all_gates.values())
    final_artifact = fit_tail_model(frame)
    final_artifact["historical_gate_passed"] = passed
    final_artifact["historical_gate_scope"] = "LOSO-2023-2025-B1-union"
    final_artifact["production_licensed"] = False
    final_artifact["prospective_shadow_only"] = True
    final_artifact["artifact_sha256"] = artifact_sha256(final_artifact)
    report = {
        "version": "b1-corpus-tail-historical-evaluation-v1",
        "population": {
            "deduplicated_rosters": len(frame),
            "slates": int(frame[["season", "week"]].drop_duplicates().shape[0]),
            "seasons": sorted(map(int, frame.season.unique())),
            "canonical_candidate_rows": int(frame.canonical_candidate.sum()),
        },
        "model": {
            "version": MODEL_VERSION, "feature_columns": list(FEATURE_COLUMNS),
            "target": "actual_score_ge_200", "winner_fields_used": [],
            "hyperparameter_grid": [],
        },
        "loso": loso_metrics,
        "walk_forward_companion": walk_metrics,
        "exact80": exact80,
        "historical_gates": all_gates,
        "historical_pass": passed,
        "licenses": {
            "write_2026_shadow_artifact": passed,
            "run_2026_shadow": passed,
            "production": False,
            "historical_retune": False,
        },
        "uses_winner_target_or_feature": False,
        "uses_realized_outcomes": True,
    }
    return report, final_artifact


def build_shadow_receipt(
    frame: pd.DataFrame,
    artifact: Mapping[str, Any],
    *,
    source_identity: Mapping[str, Any],
    enabled: bool,
) -> dict[str, Any]:
    """Create a score-free 2026 exact-80 challenger/control freeze receipt."""
    if not enabled:
        raise CorpusTailError("CORPUS_TAIL_SHADOW_ENABLED is not enabled")
    if artifact.get("historical_gate_passed") is not True:
        raise CorpusTailError("tail artifact did not pass its frozen historical gate")
    forbidden = FORBIDDEN_MODEL_FIELDS & set(frame)
    if forbidden:
        raise CorpusTailError(f"shadow frame contains outcome fields: {sorted(forbidden)}")
    slates = frame[["season", "week"]].drop_duplicates()
    if len(slates) != 1:
        raise CorpusTailError("shadow freeze requires exactly one slate")
    season, week = map(int, slates.iloc[0])
    if season < 2026:
        raise CorpusTailError("candidate-tail shadow is restricted to unseen 2026+")
    pool = frame[frame.canonical_candidate].copy()
    pool["tail_score"] = predict_tail_score(pool, artifact)
    challenger, redundancy = select_exact80(pool)
    control = pool[pool.canonical_selected].sort_values(
        "canonical_selected_rank", kind="stable")
    ranks = pd.to_numeric(control.canonical_selected_rank, errors="raise").astype(int).tolist()
    if len(control) != ENTRIES or ranks != list(range(ENTRIES)):
        raise CorpusTailError("prospective control is not ranked exact-80")
    if not source_identity or any(
        key.lower() in FORBIDDEN_MODEL_FIELDS for key in source_identity
    ):
        raise CorpusTailError("shadow source identity is absent or outcome-bearing")
    snapshot_id = source_identity.get("snapshot_id")
    snapshot_at = source_identity.get("snapshot_at")
    lock_at = source_identity.get("lock_at")
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        raise CorpusTailError("shadow source identity lacks a snapshot ID")
    if not isinstance(snapshot_at, str) or not snapshot_at.strip():
        raise CorpusTailError("shadow source identity lacks a snapshot timestamp")
    if not isinstance(lock_at, str) or not lock_at.strip():
        raise CorpusTailError("shadow source identity lacks a lock timestamp")
    parsed_times = []
    for label, value in (("snapshot", snapshot_at), ("lock", lock_at)):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CorpusTailError(
                f"shadow {label} timestamp is not ISO-8601"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise CorpusTailError(
                f"shadow {label} timestamp is not timezone-aware"
            )
        parsed_times.append(parsed)
    if parsed_times[0] >= parsed_times[1]:
        raise CorpusTailError("shadow source was not frozen before lock")
    query_times = []
    for name in ("candidate_query", "player_query"):
        query = source_identity.get(name)
        if not isinstance(query, Mapping):
            raise CorpusTailError("shadow source query receipt is absent")
        ended = query.get("ended")
        if not isinstance(ended, str):
            raise CorpusTailError("shadow source query completion is absent")
        try:
            query_time = datetime.fromisoformat(ended.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CorpusTailError("shadow source query completion is invalid") from exc
        if query_time.tzinfo is None or query_time.utcoffset() is None:
            raise CorpusTailError("shadow source query completion is not timezone-aware")
        query_times.append(query_time)
    if max(query_times) != parsed_times[0]:
        raise CorpusTailError("shadow snapshot does not equal its bound query completion")
    if source_identity.get("realized_outcome_columns_read") != []:
        raise CorpusTailError("shadow source identity is not outcome-blind")
    return {
        "version": "b1-corpus-tail-shadow-receipt-v1",
        "policy_version": POLICY_VERSION,
        "season": season, "week": week,
        "model_artifact_sha256": artifact["artifact_sha256"],
        "source_identity": dict(source_identity),
        "candidate_budget_control": len(pool),
        "candidate_budget_challenger": len(pool),
        "entry_budget": ENTRIES,
        "redundancy": redundancy,
        "control_entries": [
            {"rank": int(row.canonical_selected_rank), "roster_key": str(row.roster_key)}
            for row in control.itertuples(index=False)
        ],
        "challenger_entries": [
            {"rank": int(row.challenger_rank), "roster_key": str(row.roster_key),
             "prelock_tail_score": float(row.tail_score)}
            for row in challenger.itertuples(index=False)
        ],
        "uses_realized_outcomes": False,
        "uses_winner_target_or_feature": False,
        "production_licensed": False,
        "prospective_adoption_gate_required": True,
    }


def evaluate_six_week_adoption(grades: pd.DataFrame) -> dict[str, Any]:
    """Apply the fixed prospective gate to six consecutively frozen weeks.

    This is deliberately a small, severe gate: a historical pass merely
    enables collection.  Production review is licensed only after the shadow
    adds a 200+ week, protects both 194 and 210, improves mean weekly maximum,
    and wins at least half of the paired weeks.
    """
    required = {
        "season", "week", "control_max", "challenger_max",
        "candidate_budget_control", "candidate_budget_challenger",
        "entries_control", "entries_challenger", "frozen_before_lock",
        "labels_complete", "receipt_valid",
    }
    missing = required - set(grades)
    if missing:
        raise CorpusTailError(f"prospective grades lack fields: {sorted(missing)}")
    if len(grades) != 6 or grades.duplicated(["season", "week"]).any():
        raise CorpusTailError("prospective adoption gate requires exactly six unique weeks")
    ordered = grades.sort_values(["season", "week"], kind="stable").reset_index(drop=True)
    if ordered.season.nunique() != 1 or int(ordered.season.iloc[0]) < 2026:
        raise CorpusTailError("prospective adoption gate is restricted to one unseen season")
    weeks = pd.to_numeric(ordered.week, errors="raise").astype(int).tolist()
    if weeks != list(PROSPECTIVE_WEEKS):
        raise CorpusTailError("prospective adoption requires frozen Weeks 1 through 6")
    control = pd.to_numeric(ordered.control_max, errors="raise").to_numpy(float)
    challenger = pd.to_numeric(ordered.challenger_max, errors="raise").to_numpy(float)
    if not np.isfinite(control).all() or not np.isfinite(challenger).all():
        raise CorpusTailError("prospective weekly maxima are non-finite")
    boolean_columns = ("frozen_before_lock", "labels_complete", "receipt_valid")
    for column in boolean_columns:
        values = ordered[column]
        if values.isna().any() or not values.map(
            lambda value: isinstance(value, (bool, np.bool_))
        ).all():
            raise CorpusTailError(
                f"prospective grade field {column} must contain exact booleans"
            )
    mechanics = bool(
        ordered.frozen_before_lock.all()
        and ordered.labels_complete.all()
        and ordered.receipt_valid.all()
        and (ordered.candidate_budget_control == ordered.candidate_budget_challenger).all()
        and (pd.to_numeric(ordered.entries_control, errors="raise") == ENTRIES).all()
        and (pd.to_numeric(ordered.entries_challenger, errors="raise") == ENTRIES).all()
    )
    control_counts = {
        str(int(line)): int((control >= line).sum())
        for line in (PROTECTED_THRESHOLD, PRIMARY_THRESHOLD, SECONDARY_THRESHOLD)
    }
    challenger_counts = {
        str(int(line)): int((challenger >= line).sum())
        for line in (PROTECTED_THRESHOLD, PRIMARY_THRESHOLD, SECONDARY_THRESHOLD)
    }
    gates = {
        "all_six_receipts_and_equal_budgets_valid": mechanics,
        "mean_weekly_max_improves": float(challenger.mean()) > float(control.mean()),
        "ge200_adds_at_least_one_week": challenger_counts["200"] >= control_counts["200"] + 1,
        "ge210_count_noninferior": challenger_counts["210"] >= control_counts["210"],
        "ge194_count_protected": challenger_counts["194"] >= control_counts["194"],
        "paired_wins_at_least_half": int((challenger > control).sum()) >= 3,
    }
    passed = all(gates.values())
    return {
        "version": "b1-corpus-tail-six-week-adoption-v1",
        "season": int(ordered.season.iloc[0]), "weeks": weeks,
        "control": {
            "mean_weekly_max": float(control.mean()),
            "threshold_counts": control_counts,
        },
        "challenger": {
            "mean_weekly_max": float(challenger.mean()),
            "threshold_counts": challenger_counts,
        },
        "paired": {
            "wins": int((challenger > control).sum()),
            "losses": int((challenger < control).sum()),
            "ties": int((challenger == control).sum()),
        },
        "gates": gates,
        "prospective_gate_passed": passed,
        "production_review_licensed": passed,
        "automatic_production_mutation": False,
        "winner_fields_used": [],
    }


def write_create_once(path: Path, value: Mapping[str, Any]) -> str:
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    digest = sha256(raw).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    sha_path = path.with_suffix(path.suffix + ".sha256")
    with path.open("xb") as handle:
        handle.write(raw)
    try:
        with sha_path.open("x", encoding="utf-8") as handle:
            handle.write(digest + "\n")
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return digest
