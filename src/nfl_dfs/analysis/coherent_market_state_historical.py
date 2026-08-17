"""Frozen historical scoring for the coherent model/market-state books."""

from __future__ import annotations

from statistics import mean, median
from typing import Mapping, Sequence


VERSION = "coherent-market-state-historical-score-v1"
CANONICAL_FOLD = "R0"
THRESHOLDS = (187, 194, 200, 210, 220, 230, 240)
SCOPES = ("candidate", "selected")
BOOKS = ("control", "treatment")


def canonical_roster(values: Sequence[object]) -> tuple[str, ...]:
    roster = tuple(sorted(str(value) for value in values))
    if len(roster) != 9 or len(set(roster)) != 9 or any(
        not value or value == "None" for value in roster
    ):
        raise ValueError("coherent-state historical roster differs")
    return roster


def _score_book(
    rosters: Sequence[Sequence[object]], actual_by_id: Mapping[str, float],
) -> dict[str, object]:
    identities = [canonical_roster(row) for row in rosters]
    if len(set(identities)) != len(identities):
        raise ValueError("coherent-state historical book repeats a roster")
    missing = sorted({
        player_id
        for roster in identities for player_id in roster
        if player_id not in actual_by_id
    })
    if missing:
        raise ValueError("coherent-state historical book leaves outcome universe")
    scores = [
        float(sum(float(actual_by_id[player_id]) for player_id in roster))
        for roster in identities
    ]
    if not scores:
        raise ValueError("coherent-state historical book is empty")
    best_score = max(scores)
    best_roster = min(
        roster for roster, score in zip(identities, scores, strict=True)
        if score == best_score
    )
    return {
        "rosters": len(identities),
        "maximum": best_score,
        "maximum_roster": list(best_roster),
        "mean": float(mean(scores)),
        "median": float(median(scores)),
        "rosters_at_or_above": {
            str(threshold): sum(score >= threshold for score in scores)
            for threshold in THRESHOLDS
        },
    }


def score_slate(
    fold: Mapping[str, object], actual_by_id: Mapping[str, float],
) -> dict[str, object]:
    """Score the single prospectively selected R0 book for one slate."""
    if fold.get("heldout_block") != CANONICAL_FOLD or \
            fold.get("uses_realized_outcomes") is not False or \
            fold.get("mechanical_valid") is not True or \
            fold.get("control_entries") != 80 or \
            fold.get("treatment_entries") != 80:
        raise ValueError("coherent-state historical canonical fold differs")
    season, week = fold.get("season"), fold.get("week")
    if season not in {2023, 2024, 2025} or week not in range(1, 19):
        raise ValueError("coherent-state historical slate identity differs")
    budget = fold.get("candidate_budget")
    if not isinstance(budget, int) or budget < 80:
        raise ValueError("coherent-state historical candidate budget differs")

    scored: dict[str, dict[str, dict[str, object]]] = {}
    roster_sets: dict[tuple[str, str], set[tuple[str, ...]]] = {}
    for scope in SCOPES:
        scored[scope] = {}
        expected_rows = budget if scope == "candidate" else 80
        for book in BOOKS:
            key = f"{book}_{scope}_rosters"
            rosters = fold.get(key)
            if not isinstance(rosters, list) or len(rosters) != expected_rows:
                raise ValueError("coherent-state historical roster grid differs")
            roster_sets[(scope, book)] = {
                canonical_roster(row) for row in rosters
            }
            if len(roster_sets[(scope, book)]) != expected_rows:
                raise ValueError("coherent-state historical roster grid repeats")
            scored[scope][book] = _score_book(rosters, actual_by_id)
    for book in BOOKS:
        if not roster_sets[("selected", book)] <= roster_sets[("candidate", book)]:
            raise ValueError("coherent-state historical selection leaves candidates")

    additions = fold.get("added")
    removals = fold.get("removed")
    if not isinstance(additions, list) or len(additions) != 12 or \
            not isinstance(removals, list) or len(removals) != 12:
        raise ValueError("coherent-state historical replacement grid differs")
    added_rows = []
    for row in additions:
        roster = canonical_roster(row.get("roster", []))
        score = float(sum(float(actual_by_id[value]) for value in roster))
        added_rows.append({
            "team": row.get("team"),
            "state": row.get("state"),
            "state_index": row.get("state_index"),
            "roster": list(roster),
            "actual_score": score,
            "selected": roster in roster_sets[("selected", "treatment")],
        })
    removed_rows = []
    for row in removals:
        roster = canonical_roster(row.get("roster", []))
        removed_rows.append({
            "roster": list(roster),
            "actual_score": float(sum(
                float(actual_by_id[value]) for value in roster
            )),
        })
    return {
        "version": VERSION,
        "uses_realized_outcomes": True,
        "season": int(season),
        "week": int(week),
        "canonical_fold": CANONICAL_FOLD,
        "candidate_budget": budget,
        "books": scored,
        "selected_maximum_delta": (
            float(scored["selected"]["treatment"]["maximum"])
            - float(scored["selected"]["control"]["maximum"])
        ),
        "candidate_maximum_delta": (
            float(scored["candidate"]["treatment"]["maximum"])
            - float(scored["candidate"]["control"]["maximum"])
        ),
        "added": added_rows,
        "removed": removed_rows,
    }


def _weekly_counts(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for scope in SCOPES:
        result[scope] = {}
        for book in BOOKS:
            maxima = [
                float(row["books"][scope][book]["maximum"])  # type: ignore[index]
                for row in rows
            ]
            result[scope][book] = {
                "weeks_at_or_above": {
                    str(threshold): sum(value >= threshold for value in maxima)
                    for threshold in THRESHOLDS
                },
                "mean_weekly_maximum": float(mean(maxima)),
                "median_weekly_maximum": float(median(maxima)),
            }
    return result


def _gate_values(summary: Mapping[str, object]) -> dict[str, int]:
    selected = summary["selected"]  # type: ignore[index]
    candidate = summary["candidate"]  # type: ignore[index]
    values = {}
    for threshold in (200, 210, 220, 230, 240):
        values[f"selected_{threshold}_net"] = int(
            selected["treatment"]["weeks_at_or_above"][str(threshold)]
            - selected["control"]["weeks_at_or_above"][str(threshold)]
        )
    values["candidate_200_net"] = int(
        candidate["treatment"]["weeks_at_or_above"]["200"]
        - candidate["control"]["weeks_at_or_above"]["200"]
    )
    return values


def aggregate_historical(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    ordered = sorted(rows, key=lambda row: (int(row["season"]), int(row["week"])))
    expected = [
        (season, week)
        for season in (2023, 2024, 2025) for week in range(1, 19)
    ]
    if len(ordered) != 54 or [
        (int(row.get("season", 0)), int(row.get("week", 0))) for row in ordered
    ] != expected or any(
        row.get("version") != VERSION
        or row.get("uses_realized_outcomes") is not True
        or row.get("canonical_fold") != CANONICAL_FOLD
        for row in ordered
    ):
        raise ValueError("coherent-state historical aggregate grid differs")
    summary = _weekly_counts(ordered)
    by_season = {
        str(season): _weekly_counts([
            row for row in ordered if int(row["season"]) == season
        ])
        for season in (2023, 2024, 2025)
    }
    values = _gate_values(summary)
    conditions = {
        "selected_p200_gains_two_weeks": values["selected_200_net"] >= 2,
        "selected_p210_nondecline": values["selected_210_net"] >= 0,
        "selected_p220_nondecline": values["selected_220_net"] >= 0,
        "selected_p230_nondecline": values["selected_230_net"] >= 0,
        "selected_p240_nondecline": values["selected_240_net"] >= 0,
        "candidate_p200_nondecline": values["candidate_200_net"] >= 0,
    }
    positive = all(conditions.values())
    selected_deltas = [float(row["selected_maximum_delta"]) for row in ordered]
    influence = []
    for omitted, row in enumerate(ordered):
        leave_one_out = _gate_values(_weekly_counts(
            ordered[:omitted] + ordered[omitted + 1:]
        ))
        influence.append({
            "season": int(row["season"]),
            "week": int(row["week"]),
            "gate_values_without_slate": leave_one_out,
        })
    return {
        "version": VERSION,
        "uses_realized_outcomes": True,
        "production_change_licensed": False,
        "population": {"seasons": [2023, 2024, 2025], "slates": 54},
        "canonical_fold": CANONICAL_FOLD,
        "summary": summary,
        "by_season": by_season,
        "paired_selected_maximum": {
            "wins": sum(value > 0 for value in selected_deltas),
            "ties": sum(value == 0 for value in selected_deltas),
            "losses": sum(value < 0 for value in selected_deltas),
            "mean_delta": float(mean(selected_deltas)),
            "median_delta": float(median(selected_deltas)),
        },
        "gate": {
            **values,
            "conditions": conditions,
            "historical_tail_signal_positive": positive,
            "disposition": (
                "coherent-market-state-historical-tail-positive"
                if positive else
                "coherent-market-state-historical-tail-negative"
            ),
        },
        "leave_one_slate_out": influence,
        "rows": ordered,
    }
