"""Walk-forward realized-tail model and winner census on matchup evidence.

Trains a leave-one-season-out L2 logistic model of P(actual > threshold)
over `lineup_matchup_evidence` (the 107-slate realized corpus joined to
the frozen matchup families), and runs the winner enrichment census: the
68 registry winners' lineup matchup features placed within their OWN
slate's corpus distribution (matched same-slate denominators, per the
matchup plan's design law 6).

Discipline (frozen before any evaluation output is read):
  - outer folds are SEASONS; every reported metric is out-of-fold;
  - the frozen B1-style comparator is the same model class on the
    pre-existing simulated features only (p_line, sim_mean, sim_q90,
    sim_q99, salary) — the matchup model must beat it out-of-fold to
    claim new information (roadmap §8.2);
  - slate is the inference unit for the census (winner percentile per
    slate, sign summary across slates), never lineup-world rows;
  - results are EXPLORATORY-tier evidence on already-viewed slates: they
    nominate a frozen challenger and carry zero adoption authority.

Feature missingness: continuous features are median-imputed WITHIN the
training fold with paired missing-indicator columns; nothing becomes a
silent zero.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from typing import Final

import numpy as np
import pandas as pd

from nfl_dfs.research.winner_registry import canonical_sha256

MODEL_SCHEMA: Final = "matchup-tail-model-run/v1"
CENSUS_SCHEMA: Final = "winner-matchup-census/v1"

BASELINE_FEATURES: Final = (
    "salary", "p_line", "sim_mean", "sim_q90", "sim_q99",
)
MATCHUP_FEATURES: Final = (
    "receiver_edge_mean", "receiver_edge_max", "receiver_easy_count",
    "wr1_easy_count", "receiver_supported_count",
    "rb_edge_mean", "rb_edge_max", "rb_easy_count", "rb1_easy_count",
    "qb_edge", "lineup_edge_mean", "lineup_edge_max",
    "matchup_supported_count", "boom_edge_interaction",
)
TARGETS: Final = ("actual_ge_194", "actual_gt_200")
PRIMARY_TARGET: Final = "actual_gt_200"

CENSUS_FEATURES: Final = (
    "receiver_edge_mean", "receiver_easy_count", "wr1_easy_count",
    "rb_edge_mean", "rb_easy_count", "qb_edge", "lineup_edge_mean",
)


class MatchupTailModelError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FoldResult:
    season: int
    rows: int
    positives: int
    baseline_average_precision: float
    matchup_average_precision: float
    baseline_lift_at_80: float
    matchup_lift_at_80: float


def _design(
    frame: pd.DataFrame,
    features: Sequence[str],
    medians: Mapping[str, float] | None = None,
) -> tuple[np.ndarray, dict[str, float], list[str]]:
    """Median-impute within fold; add missing indicators; standardize later."""
    columns: list[np.ndarray] = []
    names: list[str] = []
    fitted: dict[str, float] = {}
    for name in features:
        raw = pd.to_numeric(frame[name], errors="coerce")
        median = (
            float(medians[name]) if medians is not None
            else float(raw.median()) if raw.notna().any() else 0.0
        )
        fitted[name] = median
        columns.append(raw.fillna(median).to_numpy(dtype=np.float64))
        names.append(name)
        # Indicator columns are unconditional so train and test designs
        # always share one exact width and order.
        columns.append(raw.isna().to_numpy(dtype=np.float64))
        names.append(f"{name}__missing")
    return np.column_stack(columns), fitted, names


def _average_precision(labels: np.ndarray, scores: np.ndarray) -> float:
    order = np.argsort(-scores, kind="stable")
    ranked = labels[order]
    positives = int(ranked.sum())
    if positives == 0:
        return 0.0
    cumulative = np.cumsum(ranked)
    precision = cumulative / np.arange(1, len(ranked) + 1)
    return float((precision * ranked).sum() / positives)


def _lift_at_book(
    frame: pd.DataFrame, scores: np.ndarray, target: str, book: int = 80
) -> float:
    """Mean positive rate inside per-slate top-`book` versus the pool rate."""
    work = frame[["season", "week", target]].copy()
    work["score"] = scores
    picked = []
    for (_, _), group in work.groupby(["season", "week"], sort=False):
        top = group.nlargest(min(book, len(group)), "score")
        picked.append(top[target].to_numpy(dtype=np.float64))
    top_rate = float(np.concatenate(picked).mean()) if picked else 0.0
    base_rate = float(work[target].to_numpy(dtype=np.float64).mean())
    return top_rate / base_rate if base_rate > 0 else 0.0


def _fit_logistic(matrix: np.ndarray, labels: np.ndarray):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)
    model = LogisticRegression(
        penalty="l2", C=1.0, max_iter=2000, solver="lbfgs",
        class_weight="balanced", random_state=20260822,
    )
    model.fit(scaled, labels)
    return scaler, model


def run_walk_forward(
    frame: pd.DataFrame, *, target: str = PRIMARY_TARGET
) -> dict[str, object]:
    """LOSO folds; matchup model versus the simulated-features comparator."""
    for column in (*BASELINE_FEATURES, *MATCHUP_FEATURES, target,
                   "season", "week"):
        if column not in frame.columns:
            raise MatchupTailModelError(f"evidence lacks column {column!r}")
    seasons = sorted(int(value) for value in frame["season"].unique())
    if len(seasons) < 3:
        raise MatchupTailModelError("walk-forward requires >=3 seasons")
    folds: list[FoldResult] = []
    oof_scores = np.full(len(frame), np.nan)
    frame = frame.reset_index(drop=True)
    for season in seasons:
        holdout = frame["season"] == season
        train = frame[~holdout]
        test = frame[holdout]
        labels_train = train[target].to_numpy(dtype=np.int64)
        labels_test = test[target].to_numpy(dtype=np.int64)
        if labels_train.sum() < 10:
            continue
        results: dict[str, np.ndarray] = {}
        for name, features in (
            ("baseline", BASELINE_FEATURES),
            ("matchup", (*BASELINE_FEATURES, *MATCHUP_FEATURES)),
        ):
            matrix_train, medians, _ = _design(train, features)
            scaler, model = _fit_logistic(matrix_train, labels_train)
            matrix_test, _, _ = _design(test, features, medians)
            results[name] = model.predict_proba(
                scaler.transform(matrix_test)
            )[:, 1]
        oof_scores[np.flatnonzero(holdout.to_numpy())] = results["matchup"]
        folds.append(FoldResult(
            season=season,
            rows=int(len(test)),
            positives=int(labels_test.sum()),
            baseline_average_precision=_average_precision(
                labels_test.astype(np.float64), results["baseline"]
            ),
            matchup_average_precision=_average_precision(
                labels_test.astype(np.float64), results["matchup"]
            ),
            baseline_lift_at_80=_lift_at_book(
                test, results["baseline"], target
            ),
            matchup_lift_at_80=_lift_at_book(
                test, results["matchup"], target
            ),
        ))
    wins = sum(
        1 for fold in folds
        if fold.matchup_average_precision > fold.baseline_average_precision
    )
    body = {
        "schema_version": MODEL_SCHEMA,
        "target": target,
        "row_count": int(len(frame)),
        "positive_count": int(frame[target].sum()),
        "seasons": seasons,
        "folds": [{
            "season": fold.season,
            "rows": fold.rows,
            "positives": fold.positives,
            "baseline_ap": round(fold.baseline_average_precision, 6),
            "matchup_ap": round(fold.matchup_average_precision, 6),
            "baseline_lift_at_80": round(fold.baseline_lift_at_80, 4),
            "matchup_lift_at_80": round(fold.matchup_lift_at_80, 4),
        } for fold in folds],
        "matchup_ap_beats_baseline_folds": wins,
        "fold_count": len(folds),
        "baseline_features": list(BASELINE_FEATURES),
        "matchup_features": list(MATCHUP_FEATURES),
        "evidence_tier": "exploratory-already-viewed-slates",
        "adoption_authority": False,
    }
    body["model_run_sha256"] = canonical_sha256(body)
    return {"receipt": body, "oof_scores": oof_scores}


def winner_census(
    winner_features: pd.DataFrame, corpus: pd.DataFrame
) -> dict[str, object]:
    """Winner percentile within the SAME slate's corpus, per feature.

    `winner_features`: one row per resolved winner with season/week plus
    CENSUS_FEATURES. `corpus`: lineup evidence restricted to one panel
    (same-slate denominators). Slate is the unit: per-feature winner
    percentiles across slates plus a sign summary versus the slate
    median.
    """
    rows = []
    skipped = 0
    for _, winner in winner_features.iterrows():
        slate = corpus[
            (corpus["season"] == winner["season"])
            & (corpus["week"] == winner["week"])
        ]
        if slate.empty:
            skipped += 1
            continue
        record: dict[str, object] = {
            "season": int(winner["season"]),
            "week": int(winner["week"]),
        }
        for feature in CENSUS_FEATURES:
            value = winner.get(feature)
            population = pd.to_numeric(
                slate[feature], errors="coerce"
            ).dropna()
            if value is None or pd.isna(value) or population.empty:
                record[feature] = None
                continue
            record[feature] = float(
                (population < float(value)).mean()
                + 0.5 * (population == float(value)).mean()
            )
        rows.append(record)
    summary = {}
    for feature in CENSUS_FEATURES:
        values = [
            row[feature] for row in rows if row.get(feature) is not None
        ]
        if not values:
            summary[feature] = None
            continue
        array = np.asarray(values, dtype=np.float64)
        summary[feature] = {
            "slates": int(len(array)),
            "mean_winner_percentile": round(float(array.mean()), 4),
            "median_winner_percentile": round(float(np.median(array)), 4),
            "share_above_slate_median": round(
                float((array > 0.5).mean()), 4
            ),
        }
    body = {
        "schema_version": CENSUS_SCHEMA,
        "winner_slates_evaluated": len(rows),
        "winner_slates_skipped_no_corpus": skipped,
        "per_feature": summary,
        "estimand": (
            "winner enrichment versus our same-slate legal corpus, not "
            "versus the Millionaire Maker field"
        ),
        "evidence_tier": "exploratory-already-viewed-slates",
        "adoption_authority": False,
        "winner_rows": rows,
    }
    body["winner_census_sha256"] = canonical_sha256(body)
    return body


__all__ = [
    "BASELINE_FEATURES",
    "CENSUS_FEATURES",
    "MATCHUP_FEATURES",
    "MatchupTailModelError",
    "PRIMARY_TARGET",
    "run_walk_forward",
    "winner_census",
]
