"""Pure exact-80 realized scoring for the frozen stack-core/shell diagnostic."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import mean, median
from typing import Any

from .atlas_historical_score import (
    THRESHOLDS,
    canonical_roster,
    roster_hash,
    score_rosters,
)


EXPECTED_SEASONS = (2023, 2024, 2025)
EXPECTED_WEEKS = tuple(range(1, 19))
LOCK_VERSION = "stack-core-shell-production-form-lock-v1"
ROW_VERSION = "stack-core-shell-historical-score-row-v1"
REPORT_VERSION = "stack-core-shell-historical-score-report-v1"

Roster = tuple[str, ...]


def _book(value: object, *, expected: int, name: str) -> tuple[Roster, ...]:
    if not isinstance(value, list) or len(value) != expected:
        raise ValueError(f"stack-core/shell historical {name} count differs")
    result = tuple(canonical_roster(row) for row in value)
    if len(set(result)) != expected:
        raise ValueError(f"stack-core/shell historical {name} repeats")
    return result


def _summary(rosters: Sequence[Roster], actual: Mapping[str, float]) -> dict:
    scores = score_rosters(rosters, actual)
    maximum = max(scores)
    winners = [
        list(roster) for roster, score in zip(rosters, scores, strict=True)
        if score == maximum
    ]
    return {
        "maximum": float(maximum),
        "winning_rosters": winners,
        "thresholds": {
            f"{line:g}": bool(maximum >= line) for line in THRESHOLDS
        },
    }


def compare_locked_slate(
    lock: Mapping[str, object], actual_by_id: Mapping[str, float],
) -> dict[str, Any]:
    """Score one outcome-free production-form lock after its identities exist."""
    season, week = int(lock.get("season", 0)), int(lock.get("week", 0))
    if season not in EXPECTED_SEASONS or week not in EXPECTED_WEEKS or \
            lock.get("version") != LOCK_VERSION or \
            lock.get("uses_realized_outcomes") is not False or \
            lock.get("actual_scores_queried") is not False or \
            lock.get("mechanical_valid") is not True or \
            lock.get("blocks") != ["R0", "R1", "R2", "R3", "R4"] or \
            lock.get("selected_entries") != 80 or \
            lock.get("proposal_candidates") != 40:
        raise ValueError("stack-core/shell historical lock identity differs")
    budget = lock.get("candidate_budget")
    if not isinstance(budget, int) or budget < 80:
        raise ValueError("stack-core/shell historical candidate budget differs")
    candidates = lock.get("candidate_rosters")
    selected = lock.get("selected_rosters")
    if not isinstance(candidates, Mapping) or set(candidates) != {
        "control", "treatment",
    } or not isinstance(selected, Mapping) or set(selected) != {
        "control", "treatment",
    }:
        raise ValueError("stack-core/shell historical book layers differ")
    books = {
        "candidate": {
            arm: _book(candidates[arm], expected=budget, name=f"{arm} candidates")
            for arm in ("control", "treatment")
        },
        "selected": {
            arm: _book(selected[arm], expected=80, name=f"{arm} exact-80")
            for arm in ("control", "treatment")
        },
    }
    for arm in ("control", "treatment"):
        if not set(books["selected"][arm]) <= set(books["candidate"][arm]):
            raise ValueError("stack-core/shell selected roster is outside candidates")

    proposal_rosters = _book(
        lock.get("proposal_rosters"), expected=40, name="proposal book",
    )
    admitted_count = lock.get("admitted_proposals")
    if not isinstance(admitted_count, int) or not 0 <= admitted_count <= 40:
        raise ValueError("stack-core/shell admitted proposal count differs")
    admitted = _book(
        lock.get("admitted_proposal_rosters"),
        expected=admitted_count,
        name="admitted proposals",
    )
    control_candidates = set(books["candidate"]["control"])
    treatment_candidates = set(books["candidate"]["treatment"])
    new_candidates = treatment_candidates - control_candidates
    if set(admitted) != new_candidates or not set(admitted) <= set(proposal_rosters):
        raise ValueError("stack-core/shell admitted proposal identities differ")

    summaries = {
        layer: {
            arm: _summary(rosters, actual_by_id)
            for arm, rosters in arms.items()
        }
        for layer, arms in books.items()
    }
    proposal_scores = score_rosters(proposal_rosters, actual_by_id)
    admitted_scores = score_rosters(admitted, actual_by_id) if admitted else ()
    selected_new = tuple(
        roster for roster in books["selected"]["treatment"]
        if roster in new_candidates
    )
    selected_new_scores = (
        score_rosters(selected_new, actual_by_id) if selected_new else ()
    )
    conversion = {
        "generated": len(proposal_rosters),
        "admitted": len(admitted),
        "selected": len(selected_new),
        "generated_maximum": float(max(proposal_scores)),
        "admitted_maximum": float(max(admitted_scores)) if admitted_scores else None,
        "selected_maximum": (
            float(max(selected_new_scores)) if selected_new_scores else None
        ),
        "threshold_counts": {
            f"{line:g}": {
                "generated": sum(value >= line for value in proposal_scores),
                "admitted": sum(value >= line for value in admitted_scores),
                "selected": sum(value >= line for value in selected_new_scores),
            }
            for line in THRESHOLDS
        },
    }
    overlap = {}
    for layer in ("candidate", "selected"):
        left, right = set(books[layer]["control"]), set(books[layer]["treatment"])
        overlap[layer] = {
            "intersection": len(left & right),
            "control_only": len(left - right),
            "treatment_only": len(right - left),
            "union": len(left | right),
        }
    return {
        "version": ROW_VERSION,
        "uses_realized_outcomes": True,
        "mechanical_valid": True,
        "season": season,
        "week": week,
        "slate": f"{season}-{week:02d}",
        "candidate_budget": budget,
        "books": summaries,
        "paired_delta": {
            layer: float(
                summaries[layer]["treatment"]["maximum"]
                - summaries[layer]["control"]["maximum"]
            )
            for layer in ("candidate", "selected")
        },
        "identity": {
            "overlap": overlap,
            "ordered_hashes": {
                f"{layer}_{arm}": roster_hash(books[layer][arm])
                for layer in ("candidate", "selected")
                for arm in ("control", "treatment")
            },
        },
        "proposal_conversion": conversion,
        "outcome_free_structure": lock.get("structure"),
        "outcome_free_effective_rank": lock.get("score_effective_rank"),
    }


def _scope(rows: Sequence[Mapping], arm: str, layer: str) -> dict[str, Any]:
    maxima = [float(row["books"][layer][arm]["maximum"]) for row in rows]
    return {
        "threshold_counts": {
            f"{line:g}": sum(value >= line for value in maxima)
            for line in THRESHOLDS
        },
        "mean_weekly_maximum": float(mean(maxima)),
        "median_weekly_maximum": float(median(maxima)),
        "weekly_maxima": {
            str(row["slate"]): value
            for row, value in zip(rows, maxima, strict=True)
        },
    }


def _gate(rows: Sequence[Mapping]) -> dict[str, Any]:
    def net(layer: str, line: float) -> int:
        return sum(
            int(row["books"][layer]["treatment"]["maximum"] >= line)
            - int(row["books"][layer]["control"]["maximum"] >= line)
            for row in rows
        )

    threshold_net = {
        layer: {f"{line:g}": net(layer, line) for line in THRESHOLDS}
        for layer in ("candidate", "selected")
    }
    conditions = {
        "selected_200_gains_at_least_two": threshold_net["selected"]["200"] >= 2,
        "selected_210_nonworse": threshold_net["selected"]["210"] >= 0,
        "candidate_200_nonworse": threshold_net["candidate"]["200"] >= 0,
    }
    passes = all(conditions.values())
    return {
        "threshold_net": threshold_net,
        "conditions": conditions,
        "historical_tail_first_positive": passes,
        "disposition": (
            "historical-tail-first-positive"
            if passes else "historical-tail-first-not-supported"
        ),
        "production_change_licensed": False,
    }


def aggregate_historical(rows: Sequence[Mapping]) -> dict[str, Any]:
    """Aggregate the exact 54 locked/scored slates under the frozen gate."""
    ordered = sorted(rows, key=lambda row: (int(row["season"]), int(row["week"])))
    expected = [
        (season, week)
        for season in EXPECTED_SEASONS for week in EXPECTED_WEEKS
    ]
    if len(ordered) != 54 or [
        (int(row.get("season", 0)), int(row.get("week", 0))) for row in ordered
    ] != expected or any(
        row.get("version") != ROW_VERSION
        or row.get("uses_realized_outcomes") is not True
        or row.get("mechanical_valid") is not True
        for row in ordered
    ):
        raise ValueError("stack-core/shell historical population differs")
    books = {
        layer: {
            arm: _scope(ordered, arm, layer)
            for arm in ("control", "treatment")
        }
        for layer in ("candidate", "selected")
    }
    crossings = {
        layer: {
            f"{line:g}": {
                "treatment_only": [
                    row["slate"] for row in ordered
                    if row["books"][layer]["treatment"]["maximum"] >= line
                    and row["books"][layer]["control"]["maximum"] < line
                ],
                "control_only": [
                    row["slate"] for row in ordered
                    if row["books"][layer]["control"]["maximum"] >= line
                    and row["books"][layer]["treatment"]["maximum"] < line
                ],
            }
            for line in THRESHOLDS
        }
        for layer in ("candidate", "selected")
    }
    for values in crossings.values():
        for value in values.values():
            value["net"] = len(value["treatment_only"]) - len(value["control_only"])
    paired_weeks = {
        layer: [{
            "slate": row["slate"],
            "control_maximum": float(row["books"][layer]["control"]["maximum"]),
            "treatment_maximum": float(
                row["books"][layer]["treatment"]["maximum"]
            ),
            "delta": float(row["paired_delta"][layer]),
            "classification": (
                "gained" if row["paired_delta"][layer] > 0 else
                "lost" if row["paired_delta"][layer] < 0 else "tied"
            ),
            "control_winning_rosters": row["books"][layer]["control"][
                "winning_rosters"
            ],
            "treatment_winning_rosters": row["books"][layer]["treatment"][
                "winning_rosters"
            ],
        } for row in ordered]
        for layer in ("candidate", "selected")
    }
    threshold_transitions = {
        layer: {
            f"{line:g}": {
                classification: [{
                    "slate": row["slate"],
                    "control_maximum": float(
                        row["books"][layer]["control"]["maximum"]
                    ),
                    "treatment_maximum": float(
                        row["books"][layer]["treatment"]["maximum"]
                    ),
                    "control_winning_rosters": row["books"][layer]["control"][
                        "winning_rosters"
                    ],
                    "treatment_winning_rosters": row["books"][layer]["treatment"][
                        "winning_rosters"
                    ],
                } for row in ordered if (
                    (
                        row["books"][layer]["control"]["maximum"] < line
                        and row["books"][layer]["treatment"]["maximum"] >= line
                    ) if classification == "gained" else (
                        row["books"][layer]["control"]["maximum"] >= line
                        and row["books"][layer]["treatment"]["maximum"] < line
                    ) if classification == "lost" else (
                        bool(row["books"][layer]["control"]["maximum"] >= line)
                        == bool(row["books"][layer]["treatment"]["maximum"] >= line)
                    )
                )]
                for classification in ("gained", "lost", "tied")
            }
            for line in THRESHOLDS
        }
        for layer in ("candidate", "selected")
    }
    by_season = {
        str(season): {
            "books": {
                layer: {
                    arm: _scope(
                        [row for row in ordered if int(row["season"]) == season],
                        arm,
                        layer,
                    )
                    for arm in ("control", "treatment")
                }
                for layer in ("candidate", "selected")
            },
            "gate": _gate([
                row for row in ordered if int(row["season"]) == season
            ]),
        }
        for season in EXPECTED_SEASONS
    }
    gate = _gate(ordered)
    leave_one_out = []
    for excluded in ordered:
        subset = [row for row in ordered if row is not excluded]
        value = _gate(subset)
        leave_one_out.append({
            "excluded_slate": excluded["slate"],
            "historical_tail_first_positive": value[
                "historical_tail_first_positive"
            ],
            "threshold_net": value["threshold_net"],
        })
    return {
        "version": REPORT_VERSION,
        "uses_realized_outcomes": True,
        "mechanical_valid": True,
        "population": {"seasons": list(EXPECTED_SEASONS), "slates": 54},
        "books": books,
        "paired": {
            layer: {
                "wins": sum(row["paired_delta"][layer] > 0 for row in ordered),
                "ties": sum(row["paired_delta"][layer] == 0 for row in ordered),
                "losses": sum(row["paired_delta"][layer] < 0 for row in ordered),
                "mean": float(mean(row["paired_delta"][layer] for row in ordered)),
                "median": float(median(
                    row["paired_delta"][layer] for row in ordered
                )),
                "weeks": paired_weeks[layer],
            }
            for layer in ("candidate", "selected")
        },
        "distinct_crossings": crossings,
        "threshold_transitions": threshold_transitions,
        "by_season": by_season,
        "identity_overlap": {
            layer: {
                key: sum(
                    int(row["identity"]["overlap"][layer][key])
                    for row in ordered
                )
                for key in (
                    "intersection", "control_only", "treatment_only", "union",
                )
            }
            for layer in ("candidate", "selected")
        },
        "proposal_conversion": {
            **{
                key: sum(int(row["proposal_conversion"][key]) for row in ordered)
                for key in ("generated", "admitted", "selected")
            },
            "threshold_counts": {
                f"{line:g}": {
                    stage: sum(
                        int(row["proposal_conversion"]["threshold_counts"][
                            f"{line:g}"
                        ][stage])
                        for row in ordered
                    )
                    for stage in ("generated", "admitted", "selected")
                }
                for line in THRESHOLDS
            },
        },
        "leave_one_slate_out": leave_one_out,
        "gate": gate,
        "production_change_licensed": False,
        "rows": list(ordered),
    }
