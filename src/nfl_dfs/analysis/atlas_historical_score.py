"""Pure realized-score summaries for the frozen ATLAS historical diagnostic.

This module deliberately knows nothing about BigQuery, GCS, or ATLAS solving.
The runner reconstructs the already-frozen P1/P2 books and passes their exact
roster identities here.  Keeping the score arithmetic and frozen signal rule
pure makes the outcome-facing boundary small and directly testable.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from hashlib import sha256
import json
import math
from statistics import mean, median
from typing import Any


THRESHOLDS = (187.0, 194.0, 200.0, 210.0, 220.0, 230.0, 240.0)
EXPECTED_SEASONS = (2023, 2024, 2025)
EXPECTED_WEEKS = tuple(range(1, 19))

Roster = tuple[str, ...]


def canonical_roster(values: Iterable[object]) -> Roster:
    """Return one canonical nine-player identity, failing closed."""
    roster = tuple(sorted(str(value) for value in values))
    if len(roster) != 9 or len(set(roster)) != 9 or any(not value for value in roster):
        raise ValueError("historical score roster must contain nine unique IDs")
    return roster


def roster_hash(rosters: Sequence[Roster]) -> str:
    """Hash an ordered roster book without hiding order differences."""
    raw = json.dumps([list(row) for row in rosters], separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def _validate_book(name: str, rosters: Sequence[Roster]) -> tuple[Roster, ...]:
    canonical = tuple(canonical_roster(row) for row in rosters)
    if len(canonical) != len(set(canonical)):
        raise ValueError(f"{name} contains duplicate rosters")
    return canonical


def score_rosters(
    rosters: Sequence[Roster], actual_by_id: Mapping[str, float],
) -> tuple[float, ...]:
    """Sum exact realized points for every roster."""
    values = []
    for roster in rosters:
        try:
            score = sum(float(actual_by_id[player_id]) for player_id in roster)
        except KeyError as exc:
            raise ValueError(f"missing realized score for player {exc.args[0]}") from exc
        if not math.isfinite(score):
            raise ValueError("historical score contains a non-finite outcome")
        values.append(float(score))
    return tuple(values)


def _overlap(left: Sequence[Roster], right: Sequence[Roster]) -> dict[str, Any]:
    a, b = set(left), set(right)
    intersection = len(a & b)
    union = len(a | b)
    return {
        "left": len(a),
        "right": len(b),
        "intersection": intersection,
        "union": union,
        "jaccard": float(intersection / union) if union else 1.0,
        "left_only": len(a - b),
        "right_only": len(b - a),
    }


def _scope_summary(scores: Sequence[float]) -> dict[str, Any]:
    if not scores:
        raise ValueError("cannot summarize an empty score book")
    maximum = max(scores)
    winners = [index for index, value in enumerate(scores) if value == maximum]
    return {
        "maximum": float(maximum),
        "winning_indices": winners,
        "thresholds": {
            f"{line:g}": bool(maximum >= line) for line in THRESHOLDS
        },
    }


def compare_slate(
    *,
    season: int,
    week: int,
    p1_candidates: Sequence[Roster],
    p2_candidates: Sequence[Roster],
    p1_selected: Sequence[Roster],
    p2_selected: Sequence[Roster],
    actual_by_id: Mapping[str, float],
    atlas_rosters: Sequence[Roster],
) -> dict[str, Any]:
    """Score and compare one equal-budget P1/P2 slate."""
    if season not in EXPECTED_SEASONS or week not in EXPECTED_WEEKS:
        raise ValueError("historical score slate is outside the frozen grid")
    p1c = _validate_book("P1 candidate book", p1_candidates)
    p2c = _validate_book("P2 candidate book", p2_candidates)
    p1s = _validate_book("P1 exact-80", p1_selected)
    p2s = _validate_book("P2 exact-80", p2_selected)
    atlas = _validate_book("ATLAS additions", atlas_rosters)
    if len(p1c) != len(p2c) or len(p1c) < 80:
        raise ValueError("P1/P2 realized candidate budgets differ or are too small")
    if len(p1s) != 80 or len(p2s) != 80:
        raise ValueError("historical score comparison requires exact 80 selections")
    if not set(p1s) <= set(p1c) or not set(p2s) <= set(p2c):
        raise ValueError("historical selected roster is outside its candidate book")
    if len(atlas) != 200:
        raise ValueError("historical comparison requires 200 ATLAS additions")

    scores = {
        "P1": {
            "C": score_rosters(p1c, actual_by_id),
            "S": score_rosters(p1s, actual_by_id),
        },
        "P2": {
            "C": score_rosters(p2c, actual_by_id),
            "S": score_rosters(p2s, actual_by_id),
        },
    }
    books = {
        "P1": {"C": p1c, "S": p1s},
        "P2": {"C": p2c, "S": p2s},
    }
    summaries: dict[str, dict[str, Any]] = {"P1": {}, "P2": {}}
    for arm in ("P1", "P2"):
        for scope in ("C", "S"):
            summary = _scope_summary(scores[arm][scope])
            summary["winning_rosters"] = [
                list(books[arm][scope][index])
                for index in summary.pop("winning_indices")
            ]
            summaries[arm][scope] = summary

    atlas_set = set(atlas)
    atlas_candidates = [row for row in p2c if row in atlas_set]
    atlas_selected = [row for row in p2s if row in atlas_set]
    atlas_generated_scores = score_rosters(atlas, actual_by_id)
    atlas_scores = score_rosters(atlas_candidates, actual_by_id)
    atlas_selected_scores = score_rosters(atlas_selected, actual_by_id)
    candidate_crossings: dict[str, Any] = {}
    for line in THRESHOLDS:
        key = f"{line:g}"
        treatment_only = (
            summaries["P2"]["C"]["maximum"] >= line
            and summaries["P1"]["C"]["maximum"] < line
        )
        winning = {
            tuple(row) for row in summaries["P2"]["C"]["winning_rosters"]
        }
        candidate_crossings[key] = {
            "treatment_only": treatment_only,
            "treatment_winner_is_atlas": bool(winning & atlas_set),
            "treatment_winner_survives_exact80": bool(winning & set(p2s)),
            "selected_book_also_crosses": summaries["P2"]["S"]["maximum"] >= line,
        }

    deltas = {
        scope: float(summaries["P2"][scope]["maximum"] -
                     summaries["P1"][scope]["maximum"])
        for scope in ("C", "S")
    }
    return {
        "season": season,
        "week": week,
        "slate": f"{season}-{week:02d}",
        "uses_realized_outcomes": True,
        "mechanical_valid": True,
        "candidate_budget": len(p1c),
        "books": summaries,
        "paired_delta": deltas,
        "identity": {
            "candidate": _overlap(p1c, p2c),
            "selected": _overlap(p1s, p2s),
            "ordered_hashes": {
                "P1_C": roster_hash(p1c), "P2_C": roster_hash(p2c),
                "P1_S": roster_hash(p1s), "P2_S": roster_hash(p2s),
            },
        },
        "atlas": {
            "generated": len(atlas),
            "generated_maximum": float(max(atlas_generated_scores)),
            "in_P2_candidates": len(atlas_candidates),
            "in_P2_exact80": len(atlas_selected),
            "candidate_to_selection_conversion": len(atlas_selected),
            "candidate_maximum": (
                float(max(atlas_scores)) if atlas_scores else None
            ),
            "selected_maximum": (
                float(max(atlas_selected_scores)) if atlas_selected_scores else None
            ),
            "candidate_threshold_counts": {
                f"{line:g}": sum(value >= line for value in atlas_scores)
                for line in THRESHOLDS
            },
            "generated_threshold_counts": {
                f"{line:g}": sum(value >= line for value in atlas_generated_scores)
                for line in THRESHOLDS
            },
            "selected_threshold_counts": {
                f"{line:g}": sum(value >= line for value in atlas_selected_scores)
                for line in THRESHOLDS
            },
        },
        "candidate_treatment_only_crossings": candidate_crossings,
    }


def _paired(values: Sequence[float]) -> dict[str, Any]:
    return {
        "wins": sum(value > 0 for value in values),
        "ties": sum(value == 0 for value in values),
        "losses": sum(value < 0 for value in values),
        "mean": float(mean(values)),
        "median": float(median(values)),
        "minimum": float(min(values)),
        "maximum": float(max(values)),
    }


def _aggregate_scope(rows: Sequence[dict], arm: str, scope: str) -> dict[str, Any]:
    maxima = [float(row["books"][arm][scope]["maximum"]) for row in rows]
    return {
        "threshold_counts": {
            f"{line:g}": sum(value >= line for value in maxima)
            for line in THRESHOLDS
        },
        "mean_weekly_maximum": float(mean(maxima)),
        "median_weekly_maximum": float(median(maxima)),
        "weekly_maxima": {
            row["slate"]: value for row, value in zip(rows, maxima, strict=True)
        },
    }


def aggregate_diagnostic(rows: Sequence[dict]) -> dict[str, Any]:
    """Aggregate exactly 54 frozen slate comparisons and apply the signal rule."""
    rows = sorted(rows, key=lambda row: (int(row["season"]), int(row["week"])))
    expected = [(season, week) for season in EXPECTED_SEASONS for week in EXPECTED_WEEKS]
    observed = [(int(row["season"]), int(row["week"])) for row in rows]
    if observed != expected or len(rows) != 54:
        raise ValueError("historical diagnostic must contain the exact 54-slate grid")
    if any(row.get("mechanical_valid") is not True or
           row.get("uses_realized_outcomes") is not True for row in rows):
        raise ValueError("historical diagnostic contains an invalid slate")

    books = {
        arm: {scope: _aggregate_scope(rows, arm, scope) for scope in ("C", "S")}
        for arm in ("P1", "P2")
    }
    paired = {}
    for scope in ("C", "S"):
        values = [float(row["paired_delta"][scope]) for row in rows]
        paired[scope] = _paired(values)

    def threshold_delta(use_rows: Sequence[dict], scope: str, line: float) -> int:
        return sum(
            int(row["books"]["P2"][scope]["maximum"] >= line)
            - int(row["books"]["P1"][scope]["maximum"] >= line)
            for row in use_rows
        )

    season_rows = {
        season: [row for row in rows if int(row["season"]) == season]
        for season in EXPECTED_SEASONS
    }
    by_season = {}
    for season, subset in season_rows.items():
        by_season[str(season)] = {
            "books": {
                arm: {scope: _aggregate_scope(subset, arm, scope)
                      for scope in ("C", "S")}
                for arm in ("P1", "P2")
            },
            "threshold_delta": {
                scope: {f"{line:g}": threshold_delta(subset, scope, line)
                        for line in THRESHOLDS}
                for scope in ("C", "S")
            },
            "mean_delta": {
                scope: float(mean([row["paired_delta"][scope] for row in subset]))
                for scope in ("C", "S")
            },
        }

    crossings: dict[str, dict[str, Any]] = {"C": {}, "S": {}}
    for scope in ("C", "S"):
        for line in THRESHOLDS:
            key = f"{line:g}"
            treatment = [row["slate"] for row in rows
                         if row["books"]["P2"][scope]["maximum"] >= line
                         and row["books"]["P1"][scope]["maximum"] < line]
            control = [row["slate"] for row in rows
                       if row["books"]["P1"][scope]["maximum"] >= line
                       and row["books"]["P2"][scope]["maximum"] < line]
            crossings[scope][key] = {
                "treatment_only": treatment,
                "control_only": control,
                "net": len(treatment) - len(control),
            }

    influence = {}
    leave_one_out = {}
    for scope in ("C", "S"):
        deltas = [(row["slate"], float(row["paired_delta"][scope])) for row in rows]
        influence[scope] = {
            "largest_positive": {"slate": max(deltas, key=lambda item: item[1])[0],
                                 "delta": max(value for _, value in deltas)},
            "largest_negative": {"slate": min(deltas, key=lambda item: item[1])[0],
                                 "delta": min(value for _, value in deltas)},
        }
        mean_loo = []
        threshold_loo = {f"{line:g}": [] for line in THRESHOLDS}
        for excluded in rows:
            subset = [row for row in rows if row is not excluded]
            mean_loo.append((excluded["slate"], mean(
                [float(row["paired_delta"][scope]) for row in subset]
            )))
            for line in THRESHOLDS:
                threshold_loo[f"{line:g}"].append((
                    excluded["slate"], threshold_delta(subset, scope, line)
                ))
        leave_one_out[scope] = {
            "mean_delta": {
                "minimum": float(min(value for _, value in mean_loo)),
                "maximum": float(max(value for _, value in mean_loo)),
                "minimum_exclusions": [slate for slate, value in mean_loo
                                       if value == min(v for _, v in mean_loo)],
                "maximum_exclusions": [slate for slate, value in mean_loo
                                       if value == max(v for _, v in mean_loo)],
            },
            "threshold_delta": {
                key: {
                    "minimum": min(value for _, value in values),
                    "maximum": max(value for _, value in values),
                    "minimum_exclusions": [slate for slate, value in values
                                           if value == min(v for _, v in values)],
                    "maximum_exclusions": [slate for slate, value in values
                                           if value == max(v for _, v in values)],
                }
                for key, values in threshold_loo.items()
            },
        }

    s200 = crossings["S"]["200"]["net"]
    s210 = crossings["S"]["210"]["net"]
    c200 = crossings["C"]["200"]["net"]
    positive = s200 >= 2 and s210 >= 0 and c200 >= 0
    extreme_labels = []
    for scope in ("C", "S"):
        for line in THRESHOLDS:
            key = f"{line:g}"
            control_count = books["P1"][scope]["threshold_counts"][key]
            if control_count < 5 and abs(crossings[scope][key]["net"]) == 1:
                extreme_labels.append({
                    "scope": scope, "threshold": line,
                    "label": "single-event-extreme-tail",
                })

    return {
        "version": "atlas-historical-score-diagnostic-v1",
        "uses_realized_outcomes": True,
        "population": {"seasons": list(EXPECTED_SEASONS), "slates": 54},
        "books": books,
        "paired": paired,
        "by_season": by_season,
        "distinct_crossings": crossings,
        "influence": influence,
        "leave_one_slate_out": leave_one_out,
        "identity_overlap": {
            scope: {
                "intersection": sum(row["identity"][scope]["intersection"] for row in rows),
                "left_only": sum(row["identity"][scope]["left_only"] for row in rows),
                "right_only": sum(row["identity"][scope]["right_only"] for row in rows),
            } for scope in ("candidate", "selected")
        },
        "atlas_conversion": {
            "generated": sum(row["atlas"]["generated"] for row in rows),
            "generated_weekly_maximum": {
                row["slate"]: row["atlas"]["generated_maximum"] for row in rows
            },
            "mean_generated_weekly_maximum": float(mean(
                row["atlas"]["generated_maximum"] for row in rows
            )),
            "in_P2_candidates": sum(row["atlas"]["in_P2_candidates"] for row in rows),
            "in_P2_exact80": sum(row["atlas"]["in_P2_exact80"] for row in rows),
            "candidate_to_selection_conversion": sum(
                row["atlas"]["candidate_to_selection_conversion"] for row in rows
            ),
        },
        "extreme_tail_labels": extreme_labels,
        "gate": {
            "selected_200_net": s200,
            "selected_210_net": s210,
            "candidate_200_net": c200,
            "historical_tail_signal_positive": positive,
            "disposition": (
                "historical-tail-signal-positive" if positive
                else "historical-tail-signal-not-positive"
            ),
        },
        "production_change_licensed": False,
        "rows": list(rows),
    }
