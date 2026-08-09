"""Pure paired-panel score summaries and frozen Phase-A gates."""

from __future__ import annotations

import numpy as np
import pandas as pd


FROZEN_TAIL_THRESHOLDS = (187, 194, 200, 210, 220, 230, 240)


def slate_scores(rows: pd.DataFrame) -> pd.DataFrame:
    """One selected and pool-oracle actual score per slate."""
    needed = {"season", "week", "selected", "actual_score"}
    missing = needed - set(rows.columns)
    if missing:
        raise ValueError(f"panel rows missing {sorted(missing)}")
    if rows.empty:
        raise ValueError("panel is empty")
    return rows.groupby(["season", "week"]).apply(
        lambda g: pd.Series({
            "selected_best": float(g.loc[g.selected, "actual_score"].max()),
            "oracle": float(g.actual_score.max()),
            "n_candidates": int(len(g)),
            "n_selected": int(g.selected.sum()),
        }), include_groups=False).reset_index()


def metrics(slates: pd.DataFrame) -> dict:
    """Canonical scalar score report on the frozen operator tail grid."""
    report = {
        "mean_best": float(slates.selected_best.mean()),
        "median_best": float(slates.selected_best.median()),
    }
    for threshold in FROZEN_TAIL_THRESHOLDS:
        report[f"clear_{threshold}"] = int(
            (slates.selected_best >= threshold).sum())
        report[f"oracle_{threshold}"] = int(
            (slates.oracle >= threshold).sum())
    return report


def directional_gate(incumbent: pd.DataFrame,
                     challenger: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """Does challenger improve incumbent under the frozen score gate?"""
    pair = incumbent.merge(
        challenger, on=["season", "week"], how="outer",
        suffixes=("_incumbent", "_challenger"), indicator=True,
        validate="one_to_one")
    aligned = bool(pair._merge.eq("both").all())
    pair = pair[pair._merge.eq("both")].copy()
    by_season = pair.groupby("season").apply(
        lambda g: pd.Series({
            "incumbent_194": int(
                (g.selected_best_incumbent >= 194).sum()),
            "challenger_194": int(
                (g.selected_best_challenger >= 194).sum()),
        }), include_groups=False).reset_index()
    by_season["lift"] = (
        by_season.challenger_194 - by_season.incumbent_194)
    im = metrics(incumbent)
    cm = metrics(challenger)
    checks = {
        "aligned_107_slates": aligned and len(pair) == 107,
        "clear_lift_at_least_2": cm["clear_194"] >= im["clear_194"] + 2,
        "positive_in_at_least_4_seasons": int(
            (by_season.lift > 0).sum()) >= 4,
        "at_most_1_negative_season": int(
            (by_season.lift < 0).sum()) <= 1,
        "mean_not_worse_by_more_than_0_5": bool(
            cm["mean_best"] >= im["mean_best"] - 0.5),
        "oracle_not_worse": cm["oracle_194"] >= im["oracle_194"],
    }
    checks["passes"] = all(checks.values())
    return checks, by_season


def high_tail_gate(incumbent: pd.DataFrame,
                   challenger: pd.DataFrame,
                   threshold: float = 200.0,
                   mean_guard: float = 2.0) -> tuple[dict, pd.DataFrame]:
    """Frozen directional law for a higher weekly-maximum threshold.

    This does not replace :func:`directional_gate`, whose 194-point contract
    remains the canonical 40-entry adoption record. It applies the same
    aggregate and season-distribution discipline to an explicitly declared
    high-tail objective, with a looser mean guard because mean weekly maximum
    is secondary for a top-heavy portfolio.
    """
    pair = incumbent.merge(
        challenger, on=["season", "week"], how="outer",
        suffixes=("_incumbent", "_challenger"), indicator=True,
        validate="one_to_one")
    aligned = bool(pair._merge.eq("both").all())
    pair = pair[pair._merge.eq("both")].copy()
    by_season = pair.groupby("season").apply(
        lambda g: pd.Series({
            "incumbent_clears": int(
                (g.selected_best_incumbent >= threshold).sum()),
            "challenger_clears": int(
                (g.selected_best_challenger >= threshold).sum()),
        }), include_groups=False).reset_index()
    by_season["lift"] = (
        by_season.challenger_clears - by_season.incumbent_clears)
    incumbent_clears = int(
        (pair.selected_best_incumbent >= threshold).sum())
    challenger_clears = int(
        (pair.selected_best_challenger >= threshold).sum())
    checks = {
        "aligned_107_slates": aligned and len(pair) == 107,
        "clear_lift_at_least_2": challenger_clears >= incumbent_clears + 2,
        "positive_in_at_least_4_seasons": int(
            (by_season.lift > 0).sum()) >= 4,
        "at_most_1_negative_season": int(
            (by_season.lift < 0).sum()) <= 1,
        "mean_not_worse_by_more_than_guard": bool(
            pair.selected_best_challenger.mean()
            >= pair.selected_best_incumbent.mean() - mean_guard),
    }
    checks["passes"] = all(checks.values())
    return checks, by_season


def tail_first_gate(incumbent: pd.DataFrame,
                    challenger: pd.DataFrame) -> dict:
    """Prospective aggregate-tail gate matching the operator's utility.

    Unlike :func:`high_tail_gate`, season signs and mean weekly maximum are
    diagnostics rather than vetoes.  This policy was frozen on 2026-08-09
    before the candidate-multiple-4 aggregate result was read.
    """
    pair = incumbent.merge(
        challenger, on=["season", "week"], how="outer",
        suffixes=("_incumbent", "_challenger"), indicator=True,
        validate="one_to_one")
    aligned = bool(pair._merge.eq("both").all())
    pair = pair[pair._merge.eq("both")].copy()
    incumbent_200 = int((pair.selected_best_incumbent >= 200).sum())
    challenger_200 = int((pair.selected_best_challenger >= 200).sum())
    checks = {
        "aligned_107_slates": aligned and len(pair) == 107,
        "clear_200_lift_at_least_2": challenger_200 >= incumbent_200 + 2,
        "clear_210_not_worse": int(
            (pair.selected_best_challenger >= 210).sum()) >= int(
                (pair.selected_best_incumbent >= 210).sum()),
        "oracle_200_not_worse": int(
            (pair.oracle_challenger >= 200).sum()) >= int(
                (pair.oracle_incumbent >= 200).sum()),
    }
    checks["passes"] = all(checks.values())
    return checks


def candidate_mean_parity(candidates: pd.DataFrame,
                          features: pd.DataFrame,
                          model_weight: float = 0.45,
                          tolerance: float = 1e-3) -> tuple[dict, list[str]]:
    """Audit persisted replay means against the live-lineup contract.

    Offensive-player means must be the requested model/market blend of the
    post-shaping model mean.  DST does not use the market blend, so candidate
    totals use its static ``proj`` value exactly as the live path does.
    """
    failures: list[str] = []
    candidate_needed = {"season", "week", "players", "sim_mean"}
    feature_needed = {
        "season", "week", "id", "pos", "proj", "mean_projection",
        "model_points_pre", "market_points",
    }
    missing_candidates = candidate_needed - set(candidates.columns)
    missing_features = feature_needed - set(features.columns)
    if missing_candidates:
        failures.append(
            f"candidate rows missing {sorted(missing_candidates)}")
    if missing_features:
        failures.append(f"feature rows missing {sorted(missing_features)}")
    if candidates.empty:
        failures.append("candidate rows are empty")
    if features.empty:
        failures.append("feature rows are empty")
    if failures:
        return {}, failures

    keys = ["season", "week", "id"]
    duplicate_features = int(features.duplicated(keys).sum())
    if duplicate_features:
        failures.append(
            f"feature snapshot has {duplicate_features} duplicate player keys")

    offense = features.pos.ne("DST")
    covered = offense & features.market_points.notna()
    uncovered = offense & features.market_points.isna()
    expected_blend = (
        model_weight * features.model_points_pre
        + (1.0 - model_weight) * features.market_points)
    blend_error = (features.loc[covered, "mean_projection"]
                   - expected_blend[covered]).abs()
    uncovered_error = (
        features.loc[uncovered, "mean_projection"]
        - features.loc[uncovered, "model_points_pre"]).abs()
    if not covered.any():
        failures.append("market coverage is zero")
    if len(blend_error) and blend_error.max() > 1e-5:
        failures.append("persisted covered means do not match model/market blend")
    if len(uncovered_error) and uncovered_error.max() > 1e-5:
        failures.append("uncovered means do not match post-shaping model means")

    # Do not trust a persisted DST mean from an older replay: live lineup
    # construction always uses the static DST projection.
    effective = features.copy()
    effective["effective_mean"] = np.where(
        effective.pos.eq("DST"), effective.proj,
        effective.mean_projection.where(
            effective.mean_projection.notna(), effective.proj))
    by_slate = {
        (int(season), int(week)): group.set_index("id")
        for (season, week), group in effective.groupby(["season", "week"])
    }
    errors: list[float] = []
    missing_roster_players = 0
    missing_slates = 0
    for row in candidates.itertuples(index=False):
        frame = by_slate.get((int(row.season), int(row.week)))
        if frame is None:
            missing_slates += 1
            continue
        ids = [value for value in str(row.players).split(",") if value]
        absent = [player_id for player_id in ids if player_id not in frame.index]
        if absent:
            missing_roster_players += len(absent)
            continue
        expected = float(frame.loc[ids, "effective_mean"].sum())
        errors.append(abs(expected - float(row.sim_mean)))
    max_candidate_error = max(errors) if errors else float("inf")
    if missing_slates:
        failures.append(f"{missing_slates} candidates lack a feature slate")
    if missing_roster_players:
        failures.append(
            f"candidate rosters have {missing_roster_players} missing players")
    if max_candidate_error > tolerance:
        failures.append(
            "candidate simulated means do not equal persisted player means")

    report = {
        "candidate_rows": int(len(candidates)),
        "feature_rows": int(len(features)),
        "slates": int(candidates.groupby(["season", "week"]).ngroups),
        "covered_offense_rows": int(covered.sum()),
        "uncovered_offense_rows": int(uncovered.sum()),
        "duplicate_feature_keys": duplicate_features,
        "blend_max_abs_error": (
            float(blend_error.max()) if len(blend_error) else 0.0),
        "uncovered_max_abs_error": (
            float(uncovered_error.max()) if len(uncovered_error) else 0.0),
        "candidate_mean_max_abs_error": float(max_candidate_error),
        "candidate_mean_p95_abs_error": (
            float(np.quantile(errors, 0.95)) if errors else float("inf")),
        "missing_candidate_slates": missing_slates,
        "missing_roster_players": missing_roster_players,
        "passes": not failures,
    }
    return report, failures
