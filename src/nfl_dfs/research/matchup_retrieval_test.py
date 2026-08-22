"""Paired historical retrieval test: incumbent vs matchup-aware books.

FROZEN SPECIFICATION (preregistered in code before any evaluation output
is read; committed ahead of the first run):

  - Unit of inference: the slate. Pool: the canonical panel's per-slate
    candidates from `lineup_matchup_evidence`. Incumbent book: the
    recorded production selection (`selected = TRUE`, exact-80).
  - Challenger scores: OUT-OF-FOLD matchup-model probabilities from the
    LOSO walk-forward (a slate's season is never in its training fold).
  - PRIMARY challenger — admission sleeve K=8: start from the incumbent
    book, remove its K lowest-`p_line` members, admit the K highest
    OOF-score non-selected candidates with matchup_supported_count >= 4
    (fewer if fewer are eligible; ties break by score descending then
    cand_ix ascending). Bounded and mechanistically distinct from the
    closed structure-relaxation and full-rerank arms.
  - SECONDARY challenger (exploratory) — blend rerank: select 80 by the
    mean of the within-slate p_line rank and OOF-score rank.
  - Frozen metrics: per-slate actual book-maximum delta, slate
    wins/ties/losses, and week counts at >=194 / >200 / >210 / >220 per
    arm, with per-season tables. Nomination bar for the primary
    challenger: positive mean weekly-max delta AND no reduction in >200
    week count. Exactly two challengers exist; nothing else was tried.

This read consumes realized outcomes of already-viewed slates: it is
EXPLORATORY-tier evidence that can nominate a frozen shadow strategy and
carries zero production adoption authority (the preregistered held-out
and prospective gates still govern adoption).
"""

from __future__ import annotations

from typing import Final

import numpy as np
import pandas as pd

from nfl_dfs.research.matchup_tail_model import run_walk_forward
from nfl_dfs.research.winner_registry import canonical_sha256

RETRIEVAL_TEST_SCHEMA: Final = "matchup-retrieval-paired-test/v1"
BOOK_SIZE: Final = 80
SLEEVE_K: Final = 8
MIN_SUPPORTED_COMPONENTS: Final = 4
THRESHOLDS: Final = (194.0, 200.0, 210.0, 220.0)


class MatchupRetrievalTestError(ValueError):
    pass


def _book_max(frame: pd.DataFrame, mask: np.ndarray) -> float:
    return float(frame.loc[mask, "actual_score"].max())


def build_books(slate: pd.DataFrame) -> dict[str, np.ndarray]:
    """Construct incumbent, sleeve, and blend book masks for one slate."""
    incumbent = slate["selected"].fillna(False).to_numpy(dtype=bool)
    if int(incumbent.sum()) != BOOK_SIZE:
        raise MatchupRetrievalTestError(
            f"incumbent book is {int(incumbent.sum())}, expected {BOOK_SIZE}"
        )
    scores = slate["oof_score"].to_numpy(dtype=np.float64)
    p_line = slate["p_line"].to_numpy(dtype=np.float64)
    cand_ix = slate["cand_ix"].to_numpy(dtype=np.int64)
    supported = (
        slate["matchup_supported_count"].fillna(0).to_numpy(dtype=np.int64)
        >= MIN_SUPPORTED_COMPONENTS
    )

    # PRIMARY: admission sleeve.
    sleeve = incumbent.copy()
    incumbent_indices = np.flatnonzero(incumbent)
    drop_order = incumbent_indices[np.lexsort(
        (cand_ix[incumbent_indices], p_line[incumbent_indices])
    )]
    candidates = np.flatnonzero(~incumbent & supported)
    add_order = candidates[np.lexsort(
        (cand_ix[candidates], -scores[candidates])
    )]
    swaps = min(SLEEVE_K, len(add_order))
    if swaps:
        sleeve[drop_order[:swaps]] = False
        sleeve[add_order[:swaps]] = True

    # SECONDARY: blend rerank over the full pool.
    p_rank = pd.Series(p_line).rank(ascending=False, method="average")
    s_rank = pd.Series(scores).rank(ascending=False, method="average")
    blend_key = (p_rank + s_rank).to_numpy(dtype=np.float64)
    blend_order = np.lexsort((cand_ix, blend_key))
    blend = np.zeros(len(slate), dtype=bool)
    blend[blend_order[:BOOK_SIZE]] = True

    return {"incumbent": incumbent, "sleeve": sleeve, "blend": blend}


def run_paired_test(evidence: pd.DataFrame) -> dict[str, object]:
    """Run the frozen paired test over every slate of one panel."""
    walk = run_walk_forward(evidence, target="actual_gt_200")
    frame = evidence.reset_index(drop=True).copy()
    frame["oof_score"] = walk["oof_scores"]
    if frame["oof_score"].isna().any():
        raise MatchupRetrievalTestError(
            "out-of-fold scores are incomplete; a fold was skipped"
        )
    slate_rows = []
    for (season, week), slate in frame.groupby(
        ["season", "week"], sort=True
    ):
        slate = slate.reset_index(drop=True)
        books = build_books(slate)
        maxima = {
            name: _book_max(slate, mask) for name, mask in books.items()
        }
        swapped = int(
            (books["sleeve"] & ~books["incumbent"]).sum()
        )
        slate_rows.append({
            "season": int(season),
            "week": int(week),
            "incumbent_max": round(maxima["incumbent"], 2),
            "sleeve_max": round(maxima["sleeve"], 2),
            "blend_max": round(maxima["blend"], 2),
            "sleeve_delta": round(
                maxima["sleeve"] - maxima["incumbent"], 2
            ),
            "blend_delta": round(
                maxima["blend"] - maxima["incumbent"], 2
            ),
            "sleeve_swaps": swapped,
        })
    table = pd.DataFrame(slate_rows)

    def _arm_summary(column: str) -> dict[str, object]:
        deltas = table[f"{column}_delta"]
        summary: dict[str, object] = {
            "mean_weekly_max_delta": round(float(deltas.mean()), 4),
            "median_weekly_max_delta": round(float(deltas.median()), 4),
            "slate_wins": int((deltas > 0).sum()),
            "slate_ties": int((deltas == 0).sum()),
            "slate_losses": int((deltas < 0).sum()),
        }
        for threshold in THRESHOLDS:
            summary[f"weeks_ge_{int(threshold)}"] = {
                "incumbent": int(
                    (table["incumbent_max"] >= threshold).sum()
                ),
                column: int(
                    (table[f"{column}_max"] >= threshold).sum()
                ),
            }
        per_season = {}
        for season, group in table.groupby("season"):
            per_season[str(int(season))] = {
                "mean_delta": round(
                    float(group[f"{column}_delta"].mean()), 4
                ),
                "wins": int((group[f"{column}_delta"] > 0).sum()),
                "losses": int((group[f"{column}_delta"] < 0).sum()),
            }
        summary["per_season"] = per_season
        return summary

    sleeve_summary = _arm_summary("sleeve")
    nomination = (
        sleeve_summary["mean_weekly_max_delta"] > 0
        and sleeve_summary["weeks_ge_200"]["sleeve"]
        >= sleeve_summary["weeks_ge_200"]["incumbent"]
    )
    body = {
        "schema_version": RETRIEVAL_TEST_SCHEMA,
        "book_size": BOOK_SIZE,
        "sleeve_k": SLEEVE_K,
        "min_supported_components": MIN_SUPPORTED_COMPONENTS,
        "slate_count": int(len(table)),
        "model_run_sha256": walk["receipt"]["model_run_sha256"],
        "primary_sleeve": sleeve_summary,
        "secondary_blend": _arm_summary("blend"),
        "primary_nomination_bar_met": bool(nomination),
        "slates": slate_rows,
        "evidence_tier": "exploratory-already-viewed-slates",
        "adoption_authority": False,
        "declared_challenger_count": 2,
    }
    body["retrieval_test_sha256"] = canonical_sha256(body)
    return body


__all__ = [
    "BOOK_SIZE",
    "MatchupRetrievalTestError",
    "RETRIEVAL_TEST_SCHEMA",
    "SLEEVE_K",
    "build_books",
    "run_paired_test",
]
