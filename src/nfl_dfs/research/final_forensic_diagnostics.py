"""Deterministic diagnostics preregistered for the final forensic closure."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.special import ndtr
from scipy.stats import genextreme

from .final_forensic import TAILS


BOOTSTRAP_SEED = 20260814
BOOTSTRAP_REPS = 4000
ROUTE_ADMISSION_FLOOR = 0.60
ROUTE_ADMISSION_SALARY_CAP = 3_500
ROUTE_ADMISSION_POSITIONS = frozenset({"WR", "TE"})
REGIME_BINS = {
    "game_count": ((0, 10, "games_le_10"), (11, 99, "games_ge_11")),
    "max_game_total": ((0, 50.999, "max_total_lt_51"), (51, 999, "max_total_ge_51")),
    "mean_implied_team_total": (
        (0, 22.224999, "mean_team_total_lt_22_225"),
        (22.225, 999, "mean_team_total_ge_22_225"),
    ),
    "spread_dispersion": (
        (0, 6.179999, "spread_sd_lt_6_18"),
        (6.18, 999, "spread_sd_ge_6_18"),
    ),
    "salary_dispersion": (
        (0, 1334.799999, "salary_sd_lt_1334_8"),
        (1334.8, 999999, "salary_sd_ge_1334_8"),
    ),
    "ownership_hhi": (
        (0, 0.021839, "ownership_hhi_lt_0_021839"),
        (0.0218390001, 1, "ownership_hhi_ge_0_021839"),
    ),
    "week": ((1, 6, "weeks_1_6"), (7, 12, "weeks_7_12"), (13, 99, "weeks_13_plus")),
}
BETWEEN_ARM_NAMED_CONTRASTS = (
    (
        "livefaithful_b3_vs_b2",
        "20260807-livefaithful-b2-91d596e",
        "20260808-livefaithful-b3-ee6f433",
    ),
    (
        "k1_vs_k3_original",
        "20260808-e80-k3-c616390",
        "20260808-e80-k1-c616390",
    ),
    (
        "ce12_at_k1",
        "20260808-e80-k1-c616390",
        "20260809-e80-k1-ce12-c616390",
    ),
    (
        "role12_union_lockfix",
        "20260810-lockfix-e80-k1-8677d21",
        "20260810-lockfix-e80-k1-role12union-8677d21",
    ),
    (
        "k1_vs_k3_pitclean",
        "20260811-pitclean-e80-k3-a12ab31",
        "20260811-pitclean-e80-k1-a12ab31",
    ),
    (
        "role12_union_pitclean",
        "20260811-pitclean-e80-k1-a12ab31",
        "20260811-pitclean-e80-k1-role12union-a12ab31",
    ),
)


def _roster(value: object) -> tuple[str, ...]:
    players = tuple(item for item in str(value).split(",") if item)
    if len(players) != 9 or len(set(players)) != 9:
        raise ValueError("diagnostic roster is not nine unique players")
    return players


def _finite(value: float | np.floating | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def _corr(left: pd.Series, right: pd.Series, method: str = "spearman") -> float | None:
    paired = pd.DataFrame({"left": left, "right": right}).dropna()
    if len(paired) < 3 or paired.left.nunique() < 2 or paired.right.nunique() < 2:
        return None
    return _finite(paired.left.corr(paired.right, method=method))


def _average_precision(labels: np.ndarray, scores: np.ndarray) -> float | None:
    labels = np.asarray(labels, dtype=bool)
    scores = np.asarray(scores, dtype=float)
    mask = np.isfinite(scores)
    labels, scores = labels[mask], scores[mask]
    positives = int(labels.sum())
    if positives == 0 or len(labels) == 0:
        return None
    order = np.argsort(-scores, kind="stable")
    ranked = labels[order]
    precision = np.cumsum(ranked) / np.arange(1, len(ranked) + 1)
    return float(precision[ranked].sum() / positives)


def _ndcg(relevance: np.ndarray, scores: np.ndarray) -> float | None:
    relevance = np.asarray(relevance, dtype=float)
    scores = np.asarray(scores, dtype=float)
    mask = np.isfinite(relevance) & np.isfinite(scores)
    relevance, scores = relevance[mask], scores[mask]
    if len(relevance) < 2:
        return None
    relevance = relevance - relevance.min()
    discounts = 1.0 / np.log2(np.arange(2, len(relevance) + 2))
    dcg = float((relevance[np.argsort(-scores, kind="stable")] * discounts).sum())
    ideal = float((np.sort(relevance)[::-1] * discounts).sum())
    return dcg / ideal if ideal > 0 else None


def _metric_summary(values: Sequence[float]) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if not len(array):
        return {"rows": 0, "mean": None, "median": None, "minimum": None, "maximum": None}
    return {
        "rows": int(len(array)),
        "mean": float(array.mean()),
        "median": float(np.median(array)),
        "minimum": float(array.min()),
        "maximum": float(array.max()),
    }


def _bootstrap_mean_interval(
    values: Sequence[float], *, seed_offset: int = 0
) -> list[float] | None:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if not len(array):
        return None
    rng = np.random.default_rng(BOOTSTRAP_SEED + seed_offset)
    boot = np.mean(
        rng.choice(array, size=(BOOTSTRAP_REPS, len(array)), replace=True), axis=1
    )
    return [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))]


def candidate_slate_diagnostics(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
) -> dict[str, Any]:
    """Rank, near-miss, shape, spend, exposure and ownership diagnostics."""
    frame = candidates.copy()
    actual = pd.to_numeric(frame.actual_score, errors="raise")
    selected = frame[frame.selected.fillna(False).astype(bool)].sort_values(
        "selected_rank", kind="stable"
    )
    if len(selected) != 80:
        raise ValueError("candidate diagnostics require exact-80 selection")
    player_by_id = players.copy().set_index(players.id.astype(str))

    signal_rows: dict[str, Any] = {}
    top_decile = actual.ge(actual.quantile(0.90)).to_numpy()
    for field in ("p_line", "sim_mean", "sim_q90", "sim_q99", "sim_rank_p_line", "salary"):
        values = pd.to_numeric(frame.get(field), errors="coerce")
        if not isinstance(values, pd.Series):
            values = pd.Series(np.nan, index=frame.index)
        mask = values.notna()
        signal_rows[field] = {
            "rows": int(mask.sum()),
            "spearman": _corr(values, actual),
            "top_decile_average_precision": _average_precision(
                top_decile[mask.to_numpy()], values[mask].to_numpy(float)
            ),
            "actual_score_ndcg": _ndcg(
                actual[mask].to_numpy(float), values[mask].to_numpy(float)
            ),
        }
    probability = pd.to_numeric(frame.get("p_line"), errors="coerce")
    if isinstance(probability, pd.Series):
        mask = probability.notna() & probability.between(0, 1)
        signal_rows["p_line"]["brier_ge194"] = (
            float(np.mean((probability[mask] - actual[mask].ge(194).astype(float)) ** 2))
            if mask.any() else None
        )

    oracle_row = frame.loc[actual.idxmax()]
    selected_best = selected.loc[pd.to_numeric(selected.actual_score).idxmax()]
    oracle_roster = set(_roster(oracle_row.players))
    selected_roster = set(_roster(selected_best.players))
    unselected = frame[~frame.selected.fillna(False).astype(bool)].nlargest(
        10, "actual_score"
    )
    near_miss = {
        "candidate_oracle_score": float(oracle_row.actual_score),
        "selected_best_score": float(selected_best.actual_score),
        "gap": float(oracle_row.actual_score - selected_best.actual_score),
        "shared_players": len(oracle_roster & selected_roster),
        "roster_changes": 9 - len(oracle_roster & selected_roster),
        "top_unselected": [
            {
                "candidate_index": int(row.cand_ix),
                "actual_score": float(row.actual_score),
                "gap_to_oracle": float(oracle_row.actual_score - row.actual_score),
                "shared_with_selected_best": len(
                    set(_roster(row.players)) & selected_roster
                ),
                "tag": str(getattr(row, "tag", "")),
            }
            for row in unselected.itertuples(index=False)
        ],
    }

    shapes = []
    exposure: Counter[str] = Counter()
    for row in selected.itertuples(index=False):
        ids = _roster(row.players)
        roster = player_by_id.loc[list(ids)]
        exposure.update(ids)
        quarterback = roster[roster.pos.astype(str).str.upper().eq("QB")]
        if len(quarterback) != 1:
            raise ValueError("selected roster does not contain one quarterback")
        qb = quarterback.iloc[0]
        skill = roster[~roster.pos.astype(str).str.upper().eq("DST")]
        pos_spend = roster.groupby(roster.pos.astype(str).str.upper()).salary.sum()
        actual_ownership = pd.to_numeric(
            skill.get("actual_ownership"), errors="coerce"
        )
        ownership_complete = isinstance(actual_ownership, pd.Series) and actual_ownership.notna().all()
        shapes.append({
            "actual_score": float(row.actual_score),
            "salary": int(roster.salary.sum()),
            "leftover": int(50_000 - roster.salary.sum()),
            "distinct_games": int(roster.game_id.nunique()),
            "largest_team_block": int(skill.team.value_counts().max()),
            "qb_stack_size": int(skill.team.astype(str).eq(str(qb.team)).sum() - 1),
            "bring_back": bool(skill.team.astype(str).eq(str(qb.opp)).any()),
            "te_in_qb_stack": bool(
                skill.team.astype(str).eq(str(qb.team))
                .where(skill.pos.astype(str).str.upper().eq("TE"), False).any()
            ),
            "positional_spend": {
                pos: int(pos_spend.get(pos, 0)) for pos in ("QB", "RB", "WR", "TE", "DST")
            },
            "actual_ownership_complete": ownership_complete,
            "actual_ownership_sum_skill": (
                float(actual_ownership.sum()) if ownership_complete else None
            ),
            "actual_log_ownership_product_skill": (
                float(np.log(np.clip(actual_ownership.to_numpy(float) / 100.0, 1e-6, 1)).sum())
                if ownership_complete else None
            ),
        })

    shape_summary = {
        field: _metric_summary([row[field] for row in shapes])
        for field in (
            "salary", "leftover", "distinct_games", "largest_team_block", "qb_stack_size"
        )
    }
    shape_summary["bring_back_rate"] = float(np.mean([row["bring_back"] for row in shapes]))
    shape_summary["te_in_qb_stack_rate"] = float(
        np.mean([row["te_in_qb_stack"] for row in shapes])
    )
    shape_summary["positional_spend"] = {
        pos: _metric_summary([row["positional_spend"][pos] for row in shapes])
        for pos in ("QB", "RB", "WR", "TE", "DST")
    }

    player_eval = players.copy()
    player_eval["selected_exposure"] = player_eval.id.astype(str).map(exposure).fillna(0)
    exposure_summary = {
        "players": len(player_eval),
        "selected_player_support": int(player_eval.selected_exposure.gt(0).sum()),
        "exposure_actual_spearman": _corr(
            player_eval.selected_exposure,
            pd.to_numeric(player_eval.actual, errors="raise"),
        ),
        "by_exposure_band": [],
    }
    bands = pd.cut(
        player_eval.selected_exposure,
        bins=[-0.1, 0, 4, 12, 28, 80],
        labels=["0", "1_4", "5_12", "13_28", "29_80"],
    )
    for band, group in player_eval.groupby(bands, observed=True):
        exposure_summary["by_exposure_band"].append({
            "band": str(band),
            "players": len(group),
            "mean_actual": float(pd.to_numeric(group.actual).mean()),
            "ge20_rate": float(pd.to_numeric(group.actual).ge(20).mean()),
        })

    ownership_shapes = [row for row in shapes if row["actual_ownership_complete"]]
    ownership_summary = {
        "complete_entries": len(ownership_shapes),
        "entries": 80,
        "aggregation": "equal-contest player ownership; field-size weights unavailable",
        "ownership_sum": _metric_summary([
            row["actual_ownership_sum_skill"] for row in ownership_shapes
        ]),
        "log_product_score_spearman": _corr(
            pd.Series([row["actual_log_ownership_product_skill"] for row in ownership_shapes]),
            pd.Series([row["actual_score"] for row in ownership_shapes]),
        ),
        "selection_use": "forbidden_outcome_only",
    }

    tag_sets: dict[str, set[str]] = {}
    for tag, group in frame.groupby("tag", dropna=False):
        tag_sets[str(tag)] = {",".join(sorted(_roster(value))) for value in group.players}
    overlap = []
    names = sorted(tag_sets)
    for left_index, left in enumerate(names):
        for right in names[left_index + 1:]:
            union = tag_sets[left] | tag_sets[right]
            overlap.append({
                "left": left,
                "right": right,
                "jaccard": len(tag_sets[left] & tag_sets[right]) / len(union) if union else None,
            })
    tag_yield = []
    for tag, group in frame.groupby("tag", dropna=False):
        scores = pd.to_numeric(group.actual_score, errors="raise")
        candidates_count = len(group)
        tag_yield.append({
            "tag": str(tag),
            "candidates": candidates_count,
            "selected": int(group.selected.fillna(False).astype(bool).sum()),
            "tail_counts": {
                str(tail): int(scores.ge(tail).sum()) for tail in TAILS
            },
            "tail_yield_per_1000": {
                str(tail): float(scores.ge(tail).sum() * 1000 / candidates_count)
                for tail in TAILS
            },
        })
    return {
        "rank_skill": signal_rows,
        "near_miss_frontier": near_miss,
        "construction_shapes": shape_summary,
        "selected_rosters": shapes,
        "exposure_value": exposure_summary,
        "historical_ownership": ownership_summary,
        "generator_tag_overlap": overlap,
        "generator_tag_yield": tag_yield,
    }


def route_pool_admission_diagnostics(
    players: pd.DataFrame,
    candidates: pd.DataFrame,
    winner_players: pd.DataFrame,
) -> dict[str, Any]:
    """Size a frozen route-participation admission rule without tuning it.

    This is an outcome-viewed forensic bound, not a candidate-generation arm.
    The 60% route floor represents near-full receiving-route participation and
    the $3,500 cap is the cheap-player band named before this computation. The
    output reports both winner recovery and the total admission burden.
    """
    required_players = {
        "season", "week", "id", "pos", "salary", "fp_route_share_last",
    }
    required_candidates = {"season", "week", "players"}
    required_winners = {"season", "week", "id"}
    for label, frame, required in (
        ("players", players, required_players),
        ("candidates", candidates, required_candidates),
        ("winner_players", winner_players, required_winners),
    ):
        if missing := required - set(frame):
            raise ValueError(f"route admission {label} lacks {sorted(missing)}")

    support: dict[tuple[int, int], set[str]] = {}
    for (season, week), group in candidates.groupby(["season", "week"]):
        support[(int(season), int(week))] = set().union(*(
            set(_roster(value)) for value in group.players
        ))

    frame = players.copy()
    frame["id"] = frame.id.astype(str)
    frame["route_share"] = pd.to_numeric(
        frame.fp_route_share_last, errors="coerce"
    )
    frame["salary_number"] = pd.to_numeric(frame.salary, errors="coerce")
    frame["route_applicable"] = frame.pos.astype(str).str.upper().isin(
        ROUTE_ADMISSION_POSITIONS
    )
    frame["candidate_supported"] = [
        player_id in support.get((int(season), int(week)), set())
        for season, week, player_id in zip(
            frame.season, frame.week, frame.id, strict=True
        )
    ]
    frame["frozen_route_admission"] = (
        frame.route_applicable
        & frame.salary_number.le(ROUTE_ADMISSION_SALARY_CAP)
        & frame.route_share.ge(ROUTE_ADMISSION_FLOOR)
        & ~frame.candidate_supported
    )

    winners = winner_players.copy()
    winners["id"] = winners.id.astype(str)
    winner_columns = ["season", "week", "id"]
    if "pos" in winners:
        winners = winners.rename(columns={"pos": "winner_resolved_pos"})
    winners = winners.merge(
        frame[
            winner_columns + [
                "pos", "salary_number", "route_share", "route_applicable",
                "candidate_supported", "frozen_route_admission",
            ]
        ],
        on=winner_columns,
        how="left",
        validate="one_to_one",
    )
    if "winner_resolved_pos" in winners and not winners[
        "winner_resolved_pos"
    ].astype(str).str.upper().eq(winners.pos.astype(str).str.upper()).all():
        raise ValueError("winner route-admission position differs from feature row")
    if winners.candidate_supported.isna().any():
        raise ValueError("winner route-admission audit lacks a player feature row")
    omitted = winners[~winners.candidate_supported.astype(bool)].copy()
    observed_applicable = omitted[
        omitted.route_applicable.astype(bool) & omitted.route_share.notna()
    ]
    recovered = omitted[omitted.frozen_route_admission.astype(bool)]

    by_slate = []
    for (season, week), group in frame.groupby(["season", "week"]):
        admitted = group[group.frozen_route_admission]
        recovered_count = int(recovered[
            recovered.season.astype(int).eq(int(season))
            & recovered.week.astype(int).eq(int(week))
        ].shape[0])
        by_slate.append({
            "season": int(season),
            "week": int(week),
            "admitted_absent_players": int(len(admitted)),
            "omitted_winner_slots_recovered": recovered_count,
            "admitted_nonwinner_rows": int(len(admitted) - recovered_count),
        })

    return {
        "status": "outcome_viewed_forensic_bound_only",
        "frozen_rule": {
            "positions": sorted(ROUTE_ADMISSION_POSITIONS),
            "strictly_prior_feature": "fp_route_share_last",
            "route_share_floor": ROUTE_ADMISSION_FLOOR,
            "salary_cap": ROUTE_ADMISSION_SALARY_CAP,
            "candidate_condition": "not already supported by any slate candidate",
        },
        "winner_slots": int(len(winners)),
        "omitted_winner_slots": int(len(omitted)),
        "omitted_route_applicable_with_observed_share": int(len(observed_applicable)),
        "omitted_winner_slots_recovered": int(len(recovered)),
        "recovery_rate_all_omitted": (
            float(len(recovered) / len(omitted)) if len(omitted) else None
        ),
        "recovery_rate_observed_applicable": (
            float(len(recovered) / len(observed_applicable))
            if len(observed_applicable) else None
        ),
        "total_absent_players_admitted": int(frame.frozen_route_admission.sum()),
        "mean_absent_players_admitted_per_slate": float(np.mean([
            row["admitted_absent_players"] for row in by_slate
        ])) if by_slate else None,
        "by_slate": by_slate,
        "omitted_winner_details": omitted[
            [
                "season", "week", "id", "pos", "salary_number", "route_share",
                "route_applicable", "frozen_route_admission",
            ]
        ].replace({np.nan: None}).to_dict("records"),
        "decision_boundary": (
            "This sizes targeting/selectivity only. A 2026 budget-neutral arm "
            "must replace an equal number of frozen low-yield lev candidates; "
            "the result cannot promote a historical lineup policy."
        ),
    }


def aggregate_candidate_diagnostics(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate slate diagnostics without pooling candidate rows as iid."""
    signal_names = sorted({
        signal
        for record in records
        for signal in record["diagnostic"]["rank_skill"]
    })
    metrics = ("spearman", "top_decile_average_precision", "actual_score_ndcg")
    rank_skill: dict[str, Any] = {}
    for signal_index, signal in enumerate(signal_names):
        rank_skill[signal] = {}
        for metric_index, metric in enumerate(metrics):
            values = [
                record["diagnostic"]["rank_skill"].get(signal, {}).get(metric)
                for record in records
            ]
            finite = [float(value) for value in values if value is not None]
            rank_skill[signal][metric] = {
                **_metric_summary(finite),
                "slate_cluster_bootstrap_mean_interval_95": (
                    _bootstrap_mean_interval(
                        finite, seed_offset=100 * signal_index + metric_index
                    )
                ),
                "by_season": {
                    str(season): _metric_summary([
                        float(record["diagnostic"]["rank_skill"][signal][metric])
                        for record in records
                        if int(record["season"]) == season
                        and record["diagnostic"]["rank_skill"].get(signal, {}).get(metric)
                        is not None
                    ])
                    for season in sorted({int(record["season"]) for record in records})
                },
            }

    tag_totals: dict[str, dict[str, Any]] = {}
    for record in records:
        for row in record["diagnostic"]["generator_tag_yield"]:
            current = tag_totals.setdefault(row["tag"], {
                "tag": row["tag"], "candidates": 0, "selected": 0,
                "tail_counts": {str(tail): 0 for tail in TAILS},
                "slates_present": 0,
            })
            current["candidates"] += row["candidates"]
            current["selected"] += row["selected"]
            current["slates_present"] += 1
            for tail in TAILS:
                current["tail_counts"][str(tail)] += row["tail_counts"][str(tail)]
    for current in tag_totals.values():
        current["tail_yield_per_1000"] = {
            str(tail): float(
                current["tail_counts"][str(tail)] * 1000 / current["candidates"]
            )
            for tail in TAILS
        }

    near_miss_gaps = [
        float(record["diagnostic"]["near_miss_frontier"]["gap"])
        for record in records
    ]
    return {
        "slates": len(records),
        "rank_skill_slate_clustered": rank_skill,
        "near_miss_gap": _metric_summary(near_miss_gaps),
        "candidate_oracle_omitted_slates": int(sum(value > 1e-9 for value in near_miss_gaps)),
        "generator_tag_yield": sorted(tag_totals.values(), key=lambda row: row["tag"]),
        "slate_records": [dict(record) for record in records],
        "multiple_analysis_disclosure": (
            "All signals, strata and fixed cuts were frozen together; exploratory "
            "intervals rank prospective work and are not historical adoption gates."
        ),
    }


def _normal_crps(actual: np.ndarray, mean: np.ndarray, std: np.ndarray) -> float | None:
    mask = np.isfinite(actual) & np.isfinite(mean) & np.isfinite(std) & (std > 0)
    if not mask.any():
        return None
    z = (actual[mask] - mean[mask]) / std[mask]
    density = np.exp(-0.5 * z * z) / np.sqrt(2 * np.pi)
    value = std[mask] * (z * (2 * ndtr(z) - 1) + 2 * density - 1 / np.sqrt(np.pi))
    return float(value.mean())


def player_calibration_diagnostics(features: pd.DataFrame) -> dict[str, Any]:
    """Served-distribution calibration under fixed, explicitly labeled cuts."""
    frame = features.copy()
    actual = pd.to_numeric(frame.actual, errors="raise")
    mean = pd.to_numeric(frame.mean_projection, errors="coerce")
    std = pd.to_numeric(frame.proj_std, errors="coerce")
    p10 = pd.to_numeric(frame.proj_p10, errors="coerce")
    p90 = pd.to_numeric(frame.proj_p90, errors="coerce")

    def summarize(group: pd.DataFrame) -> dict[str, Any]:
        index = group.index
        valid_mean = mean.loc[index].notna()
        valid_interval = p10.loc[index].notna() & p90.loc[index].notna()
        result = {
            "rows": len(group),
            "mean_supported": int(valid_mean.sum()),
            "mae": (
                float((actual.loc[index][valid_mean] - mean.loc[index][valid_mean]).abs().mean())
                if valid_mean.any() else None
            ),
            "rmse": (
                float(np.sqrt(np.mean((actual.loc[index][valid_mean] - mean.loc[index][valid_mean]) ** 2)))
                if valid_mean.any() else None
            ),
            "spearman": _corr(mean.loc[index], actual.loc[index]),
            "p10_p90_coverage": (
                float(((actual.loc[index][valid_interval] >= p10.loc[index][valid_interval])
                       & (actual.loc[index][valid_interval] <= p90.loc[index][valid_interval])).mean())
                if valid_interval.any() else None
            ),
            "normal_crps_from_mean_std": _normal_crps(
                actual.loc[index].to_numpy(float),
                mean.loc[index].to_numpy(float),
                std.loc[index].to_numpy(float),
            ),
            "normal_approximation": True,
            "tail_brier": {},
        }
        for threshold in (20, 25, 30):
            mask = mean.loc[index].notna() & std.loc[index].gt(0)
            probability = 1 - ndtr(
                (threshold - mean.loc[index][mask].to_numpy(float))
                / std.loc[index][mask].to_numpy(float)
            )
            result["tail_brier"][str(threshold)] = (
                float(np.mean((probability - actual.loc[index][mask].ge(threshold).to_numpy(float)) ** 2))
                if mask.any() else None
            )
        return result

    salary_band = pd.cut(
        pd.to_numeric(frame.salary),
        bins=[0, 3999, 4999, 5999, 6999, 7999, 100_000],
        labels=["lt4000", "4000s", "5000s", "6000s", "7000s", "8000_plus"],
    )
    missing = frame.feature_missing.fillna("[]").astype(str).str.strip().str.lower().ne("[]")
    ownership_band = pd.cut(
        pd.to_numeric(frame.get("own_est"), errors="coerce"),
        bins=[-np.inf, 2, 5, 10, 20, np.inf],
        labels=["le2", "2_5", "5_10", "10_20", "gt20"],
    ) if "own_est" in frame else pd.Series("unavailable", index=frame.index)
    week_phase = pd.cut(
        pd.to_numeric(frame.week, errors="coerce"),
        bins=[0, 6, 12, 99], labels=["weeks_1_6", "weeks_7_12", "weeks_13_plus"],
    )
    role_columns = [
        column for column in ("target_share_jump", "carry_share_jump", "snap_share_jump")
        if column in frame
    ]
    role_change = (
        frame[role_columns].apply(pd.to_numeric, errors="coerce").abs().ge(0.10).any(axis=1)
        if role_columns else pd.Series(False, index=frame.index)
    )
    vendor_columns = [column for column in frame if column.startswith(("fp_", "sis_"))]
    vendor_supported = (
        frame[vendor_columns].notna().any(axis=1)
        if vendor_columns else pd.Series(False, index=frame.index)
    )
    strata: dict[str, Any] = {
        "overall": summarize(frame),
        "by_position": {
            str(key): summarize(group) for key, group in frame.groupby("pos")
        },
        "by_season": {
            str(int(key)): summarize(group) for key, group in frame.groupby("season")
        },
        "by_salary_band": {
            str(key): summarize(frame.loc[group.index])
            for key, group in frame.groupby(salary_band, observed=True)
        },
        "by_feature_missing": {
            str(bool(key)).lower(): summarize(frame.loc[group.index])
            for key, group in frame.groupby(missing)
        },
        "by_ownership_band": {
            str(key): summarize(frame.loc[group.index])
            for key, group in frame.groupby(ownership_band, observed=True)
        },
        "by_week_phase": {
            str(key): summarize(frame.loc[group.index])
            for key, group in frame.groupby(week_phase, observed=True)
        },
        "by_role_change_state": {
            str(bool(key)).lower(): summarize(frame.loc[group.index])
            for key, group in frame.groupby(role_change)
        },
        "by_vendor_input_support": {
            str(bool(key)).lower(): summarize(frame.loc[group.index])
            for key, group in frame.groupby(vendor_supported)
        },
        "active_status": {
            "salary_listed_rows": len(frame),
            "limitation": (
                "The frozen slate corpus contains the draftable salary-listed "
                "universe but no independent active/inactive status history."
            ),
        },
    }
    slate_rank = []
    for (season, week, position), group in frame.groupby(["season", "week", "pos"]):
        values = pd.to_numeric(group.mean_projection, errors="coerce")
        outcome = pd.to_numeric(group.actual, errors="raise")
        slate_rank.append({
            "season": int(season),
            "week": int(week),
            "position": str(position),
            "rows": len(group),
            "spearman": _corr(values, outcome),
            "top20_average_precision": _average_precision(
                outcome.ge(20).to_numpy(), values.to_numpy(float)
            ),
            "actual_ndcg": _ndcg(outcome.to_numpy(float), values.to_numpy(float)),
        })
    strata["slate_relative_rank"] = slate_rank
    return strata


def feature_missingness_diagnostics(features: pd.DataFrame) -> dict[str, Any]:
    """Census feature support and projection error conditional on NULL state."""
    frame = features.copy()
    actual = pd.to_numeric(frame.actual, errors="raise")
    projected = pd.to_numeric(frame.mean_projection, errors="coerce")
    absolute_error = (actual - projected).abs()
    excluded = {
        "actual", "source_features_json", "actual_ownership",
        "actual_ownership_contests", "panel_run_id", "slate_run_id",
        "generated_at", "code_sha", "config_hash", "research_eligible",
        "feature_missing", "id", "gsis_id", "name", "pos", "team", "opp",
        "game_id", "season", "week", "mean_projection", "proj_p10",
        "proj_p50", "proj_p90", "proj_std", "proj", "proj_tourney",
        "model_points_pre",
    }
    feature_columns = [column for column in frame if column not in excluded]
    rows = []
    missing_manifest = frame.feature_missing.fillna("[]").astype(str)
    for column in feature_columns:
        missing = frame[column].isna()
        present = ~missing
        error_supported = absolute_error.notna()
        missing_error = absolute_error[missing & error_supported]
        present_error = absolute_error[present & error_supported]
        rows.append({
            "feature": column,
            "dtype": str(frame[column].dtype),
            "rows": len(frame),
            "null_rows": int(missing.sum()),
            "null_rate": float(missing.mean()),
            "listed_in_feature_missing_rows": int(
                missing_manifest.str.contains(column, regex=False).sum()
            ),
            "mae_when_null": (
                float(missing_error.mean()) if len(missing_error) else None
            ),
            "mae_when_present": (
                float(present_error.mean()) if len(present_error) else None
            ),
            "mae_null_minus_present": (
                float(missing_error.mean() - present_error.mean())
                if len(missing_error) and len(present_error) else None
            ),
            "by_season_null_rate": {
                str(int(season)): float(group[column].isna().mean())
                for season, group in frame.groupby("season")
            },
            "by_position_null_rate": {
                str(position): float(group[column].isna().mean())
                for position, group in frame.groupby("pos")
            },
        })
    return {
        "rows": len(frame),
        "features": sorted(rows, key=lambda row: row["feature"]),
        "duplicate_player_week_keys": int(
            frame.duplicated(["season", "week", "id"]).sum()
        ),
        "blank_player_names": int(frame.name.fillna("").astype(str).str.strip().eq("").sum()),
        "generated_at_range": {
            "minimum": str(frame.generated_at.min()) if "generated_at" in frame else None,
            "maximum": str(frame.generated_at.max()) if "generated_at" in frame else None,
        },
        "pit_limitation": (
            "This final snapshot census preserves source columns and frozen pre-lock "
            "hashes; raw-source availability windows remain governed by the tracked "
            "PIT audits and cannot be inferred from NULL rates alone."
        ),
    }


def _slate_observables(features: pd.DataFrame) -> dict[str, float]:
    def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
        if column not in frame:
            return pd.Series(np.nan, index=frame.index, dtype=float)
        return pd.to_numeric(frame[column], errors="coerce")

    team_rows = features.drop_duplicates("team")
    game_rows = features.drop_duplicates("game_id")
    own = numeric(features, "own_est").fillna(0.0)
    own_total = float(own.sum())
    wind = pd.to_numeric(features.get("wind_mph"), errors="coerce") \
        if "wind_mph" in features else pd.Series(dtype=float)
    return {
        "game_count": float(features.game_id.nunique()),
        "max_game_total": float(
            numeric(game_rows, "game_total").max()
        ),
        "mean_implied_team_total": float(
            numeric(team_rows, "implied_team_total").mean()
        ),
        "spread_dispersion": float(
            numeric(team_rows, "spread").std(ddof=0)
        ),
        "salary_dispersion": float(
            pd.to_numeric(features.salary, errors="coerce").std(ddof=0)
        ),
        "ownership_hhi": (
            float(np.square(own / own_total).sum()) if own_total > 0 else np.nan
        ),
        "mean_wind": float(wind.mean()) if wind.notna().any() else np.nan,
    }


def regime_and_drift_diagnostics(
    slate_rows: Sequence[Mapping[str, Any]],
    slate_features: Sequence[pd.DataFrame],
) -> dict[str, Any]:
    """Apply only fixed pre-lock-observable bins and report drift/autocorrelation."""
    if len(slate_rows) != len(slate_features):
        raise ValueError("regime rows and feature slates differ")
    records = []
    for result, features in zip(slate_rows, slate_features, strict=True):
        observables = _slate_observables(features)
        records.append({
            "season": int(result["season"]),
            "week": int(result["week"]),
            **observables,
            "S": float(result["S"]["actual_score"]),
            "H": float(result["H"]["actual_score"]),
            "player_support_gap": float(result["gaps"]["player_support"]),
            "construction_gap": float(result["gaps"]["construction"]),
            "selection_gap": float(result["gaps"]["selection"]),
        })
    data = pd.DataFrame(records).sort_values(["season", "week"], kind="stable")

    def group_summary(group: pd.DataFrame) -> dict[str, Any]:
        return {
            "slates": len(group),
            "selected_best_mean": _finite(group.S.mean()),
            "tail_counts": {str(tail): int(group.S.ge(tail).sum()) for tail in TAILS},
            "gap_means": {
                key: _finite(group[key].mean())
                for key in ("player_support_gap", "construction_gap", "selection_gap")
            },
        }

    regimes = []
    for field, bins in REGIME_BINS.items():
        for lower, upper, label in bins:
            group = data[data[field].between(lower, upper, inclusive="both")]
            regimes.append({
                "field": field,
                "label": label,
                "lower": lower,
                "upper": upper,
                **group_summary(group),
            })
    autocorrelation = []
    for season, group in data.groupby("season"):
        ordered = group.sort_values("week")
        consecutive = ordered.week.diff().eq(1)
        for metric in ("player_support_gap", "construction_gap", "selection_gap", "S"):
            current = ordered.loc[consecutive, metric]
            prior = ordered[metric].shift(1).loc[consecutive]
            autocorrelation.append({
                "season": int(season),
                "metric": metric,
                "pairs": len(current),
                "lag1_correlation": _corr(current.reset_index(drop=True), prior.reset_index(drop=True), "pearson"),
            })
    season = {
        str(int(key)): group_summary(group) for key, group in data.groupby("season")
    }
    leave_one_out = {
        str(int(key)): group_summary(data[data.season.ne(key)])
        for key in sorted(data.season.unique())
    }
    return {
        "fixed_bins": REGIME_BINS,
        "fixed_bin_provenance": (
            "Cut points were fixed from outcome-free component-panel pre-lock "
            "summaries before the first forensic outcome query."
        ),
        "regimes": regimes,
        "unavailable_prelock_regimes": (
            ["mean_wind"] if data.mean_wind.notna().sum() == 0 else []
        ),
        "failure_autocorrelation": autocorrelation,
        "season_drift": season,
        "leave_one_season_out": leave_one_out,
    }


def evt_diagnostic(slate_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Exploratory GEV plus empirical/bootstrapped exact-80 maxima summary."""
    data = pd.DataFrame([
        {
            "season": int(row["season"]),
            "week": int(row["week"]),
            "maximum": float(row["S"]["actual_score"]),
        }
        for row in slate_rows
    ])
    values = data.maximum.to_numpy(float)
    fit: dict[str, Any]
    try:
        shape, location, scale = genextreme.fit(values)
        fit = {
            "status": "fit",
            "shape": float(shape),
            "location": float(location),
            "scale": float(scale),
            "return_levels": {
                str(period): float(genextreme.ppf(1 - 1 / period, shape, loc=location, scale=scale))
                for period in (5, 10, 20)
            },
        }
    except (ValueError, FloatingPointError) as exc:
        fit = {"status": "unstable", "reason": str(exc)}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    boot = np.mean(rng.choice(values, size=(BOOTSTRAP_REPS, len(values))), axis=1)
    return {
        "slates": len(data),
        "empirical": {
            "mean": float(values.mean()),
            "quantiles": {
                str(level): float(np.quantile(values, level))
                for level in (0.5, 0.75, 0.9, 0.95)
            },
            "tail_counts": {str(tail): int((values >= tail).sum()) for tail in TAILS},
        },
        "gev": fit,
        "paired_slate_bootstrap_mean": {
            "seed": BOOTSTRAP_SEED,
            "repetitions": BOOTSTRAP_REPS,
            "interval_95": [float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))],
        },
        "by_season": {
            str(int(season)): _metric_summary(group.maximum.tolist())
            for season, group in data.groupby("season")
        },
        "leave_one_season_out": {
            str(int(season)): _metric_summary(
                data.loc[data.season.ne(season), "maximum"].tolist()
            )
            for season in sorted(data.season.unique())
        },
        "influential_weeks": data.nlargest(5, "maximum").to_dict("records"),
        "interpretation": "exploratory diagnostic; never an adoption or extrapolation-only gate",
    }


def paired_scope_diagnostics(
    scope_rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Run the two predeclared shared-slate production-boundary contrasts."""
    comparisons = (
        ("position-54", "component-107"),
        ("phase-s-cbwu-54", "position-54"),
    )
    frames = {
        scope: pd.DataFrame([
            {
                "season": int(row["season"]),
                "week": int(row["week"]),
                "maximum": float(row["S"]["actual_score"]),
            }
            for row in rows
        ])
        for scope, rows in scope_rows.items()
    }
    results = []
    for index, (treatment, control) in enumerate(comparisons):
        paired = frames[treatment].merge(
            frames[control], on=["season", "week"], validate="one_to_one",
            suffixes=("_treatment", "_control"),
        )
        paired["delta"] = paired.maximum_treatment - paired.maximum_control
        season_rows = {}
        for season, group in paired.groupby("season"):
            season_rows[str(int(season))] = {
                "slates": len(group),
                "mean_delta": float(group.delta.mean()),
                "improved": int(group.delta.gt(1e-9).sum()),
                "worsened": int(group.delta.lt(-1e-9).sum()),
                "tail_delta": {
                    str(tail): int(
                        group.maximum_treatment.ge(tail).sum()
                        - group.maximum_control.ge(tail).sum()
                    )
                    for tail in TAILS
                },
            }
        results.append({
            "treatment": treatment,
            "control": control,
            "shared_slates": len(paired),
            "mean_delta": float(paired.delta.mean()),
            "paired_slate_bootstrap_mean_interval_95": _bootstrap_mean_interval(
                paired.delta.tolist(), seed_offset=5000 + index
            ),
            "improved": int(paired.delta.gt(1e-9).sum()),
            "tied": int(paired.delta.abs().le(1e-9).sum()),
            "worsened": int(paired.delta.lt(-1e-9).sum()),
            "tail_delta": {
                str(tail): int(
                    paired.maximum_treatment.ge(tail).sum()
                    - paired.maximum_control.ge(tail).sum()
                )
                for tail in TAILS
            },
            "by_season": season_rows,
            "leave_one_season_out": {
                str(int(season)): {
                    "slates": int(paired.season.ne(season).sum()),
                    "mean_delta": float(
                        paired.loc[paired.season.ne(season), "delta"].mean()
                    ),
                }
                for season in sorted(paired.season.unique())
            },
            "most_influential_absolute_deltas": paired.loc[
                paired.delta.abs().nlargest(5).index
            ].to_dict("records"),
        })
    return {
        "scope_evt": {
            scope: evt_diagnostic(rows) for scope, rows in scope_rows.items()
        },
        "paired_predeclared_comparisons": results,
        "scope_warning": (
            "Each contrast is reported only on shared 2023-2025 slates. It does "
            "not manufacture a 107-slate v4 production book or rewrite any arm gate."
        ),
    }


def between_arm_variance_diagnostic(
    weekly: pd.DataFrame,
    *,
    panel_ids: Sequence[str],
) -> dict[str, Any]:
    """Estimate descriptive arm dispersion after removing common-slate effects.

    The launched panels are a selected, heterogeneous population. This is a
    fixed-effect dispersion census and a future reporting scale, not a causal
    random-effects model and never a mechanism re-adjudication.
    """
    required = {"panel_run_id", "season", "week", "weekly_max", "entries"}
    if not required <= set(weekly):
        raise ValueError("between-arm weekly frame lacks required columns")
    frame = weekly.copy()
    frame["panel_run_id"] = frame.panel_run_id.astype(str)
    frame["slate"] = [
        f"{int(season)}-{int(week):02d}"
        for season, week in zip(frame.season, frame.week, strict=True)
    ]
    arms = list(map(str, panel_ids))
    if set(frame.panel_run_id) != set(arms):
        raise ValueError("between-arm weekly frame differs from frozen arms")
    if frame.duplicated(["panel_run_id", "slate"]).any():
        raise ValueError("between-arm weekly frame repeats arm/slate rows")
    slates = sorted(frame.slate.unique())
    if len(frame) != len(arms) * len(slates) or any(
        set(group.slate) != set(slates)
        for _, group in frame.groupby("panel_run_id")
    ):
        raise ValueError("between-arm panel is not balanced on common slates")
    frame["weekly_max"] = pd.to_numeric(frame.weekly_max, errors="raise")

    def fit(values: np.ndarray, *, threshold: int | None = None) -> dict[str, Any]:
        arm_index = {arm: index for index, arm in enumerate(arms)}
        slate_index = {slate: index for index, slate in enumerate(slates)}
        columns = 1 + (len(arms) - 1) + (len(slates) - 1)
        design = np.zeros((len(frame), columns), dtype=float)
        design[:, 0] = 1.0
        for row_index, row in enumerate(frame.itertuples(index=False)):
            arm_ix = arm_index[row.panel_run_id]
            slate_ix = slate_index[row.slate]
            if arm_ix:
                design[row_index, arm_ix] = 1.0
            if slate_ix:
                design[row_index, len(arms) - 1 + slate_ix] = 1.0
        coefficients, _, rank, _ = np.linalg.lstsq(design, values, rcond=None)
        fitted = design @ coefficients
        residual = values - fitted
        arm_effects = np.zeros(len(arms), dtype=float)
        arm_effects[1:] = coefficients[1:len(arms)]
        arm_effects -= arm_effects.mean()
        arm_variance = float(np.var(arm_effects, ddof=1))
        residual_df = max(int(len(values) - rank), 1)
        residual_variance = float(np.dot(residual, residual) / residual_df)
        total = arm_variance + residual_variance
        multiplier = 1.959963984540054 + 0.8416212335729143
        mdd = float(
            multiplier * np.sqrt(2.0 * residual_variance / len(slates))
        )
        pairwise = sorted(
            abs(float(arm_effects[left] - arm_effects[right]))
            for left in range(len(arms))
            for right in range(left + 1, len(arms))
        )
        output = {
            "rows": int(len(values)),
            "design_rank": int(rank),
            "design_columns": int(columns),
            "arm_effects": {
                arm: float(arm_effects[index]) for index, arm in enumerate(arms)
            },
            "arm_effect_variance": arm_variance,
            "arm_effect_sd": float(np.sqrt(arm_variance)),
            "residual_variance": residual_variance,
            "residual_sd": float(np.sqrt(residual_variance)),
            "arm_share_of_arm_plus_residual_variance": (
                arm_variance / total if total > 0 else None
            ),
            "pairwise_absolute_effect_quantiles": {
                str(quantile): float(np.quantile(pairwise, quantile))
                for quantile in (0.25, 0.5, 0.75, 0.9, 0.95)
            },
            "minimum_detectable_pair_difference_alpha05_power80": mdd,
        }
        if threshold is not None:
            output["units"] = "proportion_of_common_slates"
            output["minimum_detectable_threshold_weeks"] = float(
                mdd * len(slates)
            )
        else:
            output["units"] = "weekly_max_points"
        return output

    models = {
        "weekly_max": fit(frame.weekly_max.to_numpy(float)),
        "ge200": fit(
            frame.weekly_max.ge(200).to_numpy(float), threshold=200
        ),
        "ge210": fit(
            frame.weekly_max.ge(210).to_numpy(float), threshold=210
        ),
    }

    def percentile(value: float, effects: Mapping[str, float]) -> float:
        population = [
            abs(float(effects[left]) - float(effects[right]))
            for index, left in enumerate(arms)
            for right in arms[index + 1:]
        ]
        return float(np.mean(np.asarray(population) <= abs(value)))

    named = []
    indexed = frame.set_index(["panel_run_id", "slate"])
    for contrast_id, control, treatment in BETWEEN_ARM_NAMED_CONTRASTS:
        if control not in arms or treatment not in arms:
            raise ValueError(f"named between-arm contrast is absent: {contrast_id}")
        control_rows = indexed.loc[control].sort_index()
        treatment_rows = indexed.loc[treatment].sort_index()
        delta = treatment_rows.weekly_max.to_numpy(float) - \
            control_rows.weekly_max.to_numpy(float)
        mean_delta = float(delta.mean())
        record = {
            "id": contrast_id,
            "control": control,
            "treatment": treatment,
            "weekly_max_mean_delta": mean_delta,
            "weekly_max_absolute_pairwise_percentile": percentile(
                mean_delta, models["weekly_max"]["arm_effects"]
            ),
            "ge200_week_delta": int(
                treatment_rows.weekly_max.ge(200).sum()
                - control_rows.weekly_max.ge(200).sum()
            ),
            "ge210_week_delta": int(
                treatment_rows.weekly_max.ge(210).sum()
                - control_rows.weekly_max.ge(210).sum()
            ),
        }
        for threshold in (200, 210):
            proportion_delta = record[f"ge{threshold}_week_delta"] / len(slates)
            record[f"ge{threshold}_absolute_pairwise_percentile"] = percentile(
                proportion_delta, models[f"ge{threshold}"]["arm_effects"]
            )
        named.append(record)
    return {
        "panels": arms,
        "panel_count": len(arms),
        "common_slates": [
            {"season": int(value.split("-")[0]), "week": int(value.split("-")[1])}
            for value in slates
        ],
        "common_slate_count": len(slates),
        "entry_counts": {
            arm: sorted(map(int, group.entries.unique()))
            for arm, group in frame.groupby("panel_run_id")
        },
        "models": models,
        "named_historical_panel_contrasts": named,
        "selection_bias": (
            "The fourteen arms are the mechanically complete 107-slate panels "
            "chosen to be launched, not a random sample of mechanisms."
        ),
        "estimand_boundary": (
            "Arm fixed-effect dispersion after common-slate removal; panels "
            "differ in multiple levers and entry counts, so individual arm "
            "effects are descriptive rather than causal."
        ),
        "use_restriction": (
            "This output may not revive, re-adjudicate or relabel any rejected "
            "arm. It sets a reporting scale for future outcome-unseen work."
        ),
    }
def winner_benchmark(repo_root: str | Path) -> dict[str, Any]:
    """Benchmark identifiable winner salary/spend/ownership fields only."""
    root = Path(repo_root)
    older = pd.read_csv(root / "reports/milly-winners-2019-2023-2024.csv").rename(
        columns={"fantasy_points": "points", "ownership_pct": "ownership"}
    )
    older["ownership"] = older.ownership.astype(str).str.rstrip("%").replace("nan", np.nan)
    older["ownership"] = pd.to_numeric(older.ownership, errors="coerce")
    current = pd.read_csv(root / "reports/2025-milly-rosters.csv").rename(
        columns={"pts": "points", "own_pct": "ownership"}
    )
    current["season"] = 2025
    rows = pd.concat([
        older[["season", "week", "position", "salary", "ownership", "points"]],
        current[["season", "week", "position", "salary", "ownership", "points"]],
    ], ignore_index=True)
    slates = []
    for (season, week), group in rows.groupby(["season", "week"]):
        if len(group) != 9:
            raise ValueError(f"winner roster is not nine rows: {season}w{week}")
        spend = group.groupby(group.position.astype(str).str.upper()).salary.sum()
        ownership = pd.to_numeric(group.ownership, errors="coerce")
        slates.append({
            "season": int(season),
            "week": int(week),
            "players": len(group),
            "score": float(pd.to_numeric(group.points).sum()),
            "salary": int(pd.to_numeric(group.salary).sum()),
            "leftover": int(50_000 - pd.to_numeric(group.salary).sum()),
            "positional_spend": {
                pos: int(spend.get(pos, 0))
                for pos in ("QB", "RB", "WR", "TE", "FLEX", "DST")
            },
            "ownership_sum": float(ownership.sum()) if ownership.notna().all() else None,
            "log_ownership_product": (
                float(np.log(np.clip(ownership.to_numpy(float) / 100.0, 1e-6, 1)).sum())
                if ownership.notna().all() else None
            ),
        })
    return {
        "slates": len(slates),
        "seasons": sorted({row["season"] for row in slates}),
        "salary": _metric_summary([row["salary"] for row in slates]),
        "leftover": _metric_summary([row["leftover"] for row in slates]),
        "positional_spend": {
            pos: _metric_summary([row["positional_spend"][pos] for row in slates])
            for pos in ("QB", "RB", "WR", "TE", "FLEX", "DST")
        },
        "ownership_sum": _metric_summary([
            row["ownership_sum"] for row in slates if row["ownership_sum"] is not None
        ]),
        "slate_records": slates,
        "limitations": (
            "Only first-place rosters are present; team/game fields needed for "
            "winner stack/bring-back shapes and places 2-5 are unavailable. "
            "Older data identify the FLEX slot but not its underlying position, "
            "so slot spend is preserved without guessing."
        ),
    }


__all__ = [
    "aggregate_candidate_diagnostics",
    "between_arm_variance_diagnostic",
    "candidate_slate_diagnostics",
    "evt_diagnostic",
    "feature_missingness_diagnostics",
    "paired_scope_diagnostics",
    "player_calibration_diagnostics",
    "regime_and_drift_diagnostics",
    "route_pool_admission_diagnostics",
    "winner_benchmark",
]
