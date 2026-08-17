"""Outcome-free primitives for recourse-aware initial-book selection."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from statistics import median
from typing import Any

import numpy as np
import pandas as pd

from ..optimizer.lineup import Lineup


VERSION = "recourse-aware-initial-book-scorefree-v1"
PROTOCOL_SHA256 = (
    "0085b5f77b4e859982fc4f664161cdafe2bb6ec07ea0351fb618ddf58319c077"
)
SLOTS = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")
TAILS = (240.0, 230.0, 220.0, 210.0, 200.0, 194.0, 187.0)
ALTERNATIVE_CAP = 24


def _roster(lineup: Lineup) -> tuple[str, ...]:
    values = tuple(sorted(str(value) for value in lineup.ids))
    if len(values) != 9:
        raise ValueError("recourse-aware initial roster is not nine unique IDs")
    return values


def _aware_utc(value: object, label: str) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return stamp.tz_convert("UTC")


def _kickoff_map(
    lineup: Lineup,
    kickoff_by_id: Mapping[str, object],
) -> dict[str, pd.Timestamp]:
    result = {}
    for player in lineup.players:
        player_id = str(player["id"])
        if player_id not in kickoff_by_id:
            raise ValueError("recourse-aware initial kickoff identity is absent")
        result[player_id] = _aware_utc(
            kickoff_by_id[player_id], f"kickoff for {player_id}",
        )
    if len(result) != 9:
        raise ValueError("recourse-aware initial lineup player identity repeats")
    return result


def _slot_order(
    lineup: Lineup,
    kickoff_by_id: Mapping[str, object],
) -> tuple[Mapping[str, Any], ...]:
    kickoffs = _kickoff_map(lineup, kickoff_by_id)
    players = [
        {
            **player,
            "id": str(player["id"]),
            "kickoff": kickoffs[str(player["id"])].isoformat(),
        }
        for player in lineup.players
    ]
    ordered = tuple(Lineup(players, tag=lineup.tag).slot_order())
    if len(ordered) != len(SLOTS):
        raise ValueError("recourse-aware initial slot order is incomplete")
    for slot, player in zip(SLOTS, ordered, strict=True):
        if not _eligible(str(player.get("pos", "")), slot):
            raise ValueError("recourse-aware initial slot order is illegal")
    return ordered


def _eligible(position: str, slot: str) -> bool:
    pos = str(position).upper()
    return pos in {"RB", "WR", "TE"} if slot == "FLEX" else pos == slot


def locked_slot_signature(
    lineup: Lineup,
    kickoff_by_id: Mapping[str, object],
    decision: datetime | pd.Timestamp | str,
) -> tuple[tuple[int, str], ...]:
    """Return exact locked DraftKings slot/player identities."""
    current = _aware_utc(decision, "recourse-aware decision")
    kickoffs = _kickoff_map(lineup, kickoff_by_id)
    ordered = _slot_order(lineup, kickoff_by_id)
    return tuple(
        (index, str(player["id"]))
        for index, player in enumerate(ordered)
        if kickoffs[str(player["id"])] <= current
    )


def _reachable_from_signature(
    signature: Sequence[tuple[int, str]],
    final_by_id: Mapping[str, Mapping[str, Any]],
    kickoffs: Mapping[str, pd.Timestamp],
    current: pd.Timestamp,
) -> bool:
    locked_ids = {player_id for _, player_id in signature}
    if not locked_ids <= set(final_by_id):
        return False
    locked_slots = {value for value, _ in signature}
    open_slots = [
        slot for index, slot in enumerate(SLOTS) if index not in locked_slots
    ]
    open_players = [
        player for player_id, player in final_by_id.items()
        if player_id not in locked_ids
    ]
    if any(
        player_id not in kickoffs or kickoffs[player_id] <= current
        for player_id in final_by_id if player_id not in locked_ids
    ):
        return False
    return _open_slot_matching(open_players, open_slots)


def _open_slot_matching(
    players: Sequence[Mapping[str, Any]],
    slots: Sequence[str],
) -> bool:
    if len(players) != len(slots):
        return False
    positions = tuple(str(player.get("pos", "")).upper() for player in players)
    if any(not position for position in positions):
        return False

    def search(remaining_slots: tuple[int, ...], used: frozenset[int]) -> bool:
        if not remaining_slots:
            return True
        slot_index = min(
            remaining_slots,
            key=lambda value: sum(
                index not in used and _eligible(positions[index], slots[value])
                for index in range(len(players))
            ),
        )
        candidates = [
            index for index in range(len(players))
            if index not in used and _eligible(positions[index], slots[slot_index])
        ]
        tail = tuple(value for value in remaining_slots if value != slot_index)
        return any(search(tail, used | {index}) for index in candidates)

    return search(tuple(range(len(slots))), frozenset())


def is_late_swap_reachable(
    initial: Lineup,
    final: Lineup,
    kickoff_by_id: Mapping[str, object],
    decision: datetime | pd.Timestamp | str,
) -> bool:
    """Whether ``final`` is reachable while retaining exact locked slots."""
    current = _aware_utc(decision, "recourse-aware decision")
    signature = locked_slot_signature(initial, kickoff_by_id, current)
    final_by_id = {str(player["id"]): player for player in final.players}
    if len(final_by_id) != 9:
        raise ValueError("recourse-aware final roster is not nine unique IDs")
    needed = set(final_by_id) | {str(player["id"]) for player in initial.players}
    if not needed <= set(kickoff_by_id):
        raise ValueError("recourse-aware initial kickoff identity is absent")
    kickoffs = {
        player_id: _aware_utc(
            kickoff_by_id[player_id], f"kickoff for {player_id}",
        )
        for player_id in needed
    }
    return _reachable_from_signature(signature, final_by_id, kickoffs, current)


def build_alternative_sets(
    lineups: Sequence[Lineup],
    training_totals: np.ndarray,
    kickoff_by_id: Mapping[str, object],
    decision: datetime | pd.Timestamp | str,
    *,
    cap: int = ALTERNATIVE_CAP,
) -> tuple[tuple[int, ...], ...]:
    """Freeze at most 24 PIT-reachable alternatives per initial lineup."""
    candidates = tuple(lineups)
    totals = np.asarray(training_totals, dtype=np.float32)
    if len(candidates) == 0 or totals.ndim != 2 or \
            totals.shape[0] != len(candidates) or totals.shape[1] == 0 or \
            not np.isfinite(totals).all():
        raise ValueError("recourse-aware training candidate totals differ")
    if type(cap) is not int or cap <= 0 or cap > ALTERNATIVE_CAP:
        raise ValueError("recourse-aware alternative cap differs")
    rosters = tuple(_roster(lineup) for lineup in candidates)
    if len(set(rosters)) != len(rosters):
        raise ValueError("recourse-aware candidate roster repeats")
    player_universe = set().union(*(set(value) for value in rosters))
    if not player_universe <= set(kickoff_by_id):
        raise ValueError("recourse-aware initial kickoff identity is absent")
    current = _aware_utc(decision, "recourse-aware decision")
    kickoffs = {
        player_id: _aware_utc(
            kickoff_by_id[player_id], f"kickoff for {player_id}",
        )
        for player_id in player_universe
    }
    signatures = tuple(
        locked_slot_signature(lineup, kickoffs, current) for lineup in candidates
    )
    final_profiles = tuple(
        {str(player["id"]): player for player in lineup.players}
        for lineup in candidates
    )
    counts = np.stack([
        np.count_nonzero(totals >= threshold, axis=1) for threshold in TAILS
    ], axis=1)
    q99 = np.quantile(totals, 0.99, axis=1)
    means = totals.mean(axis=1, dtype=np.float64)
    output = []
    for initial_index, _initial in enumerate(candidates):
        reachable = [
            index for index, final in enumerate(final_profiles)
            if _reachable_from_signature(
                signatures[initial_index], final, kickoffs, current,
            )
        ]
        if initial_index not in reachable:
            raise ValueError("recourse-aware fail-safe alternative is absent")

        def key(index: int) -> tuple[object, ...]:
            churn = 9 - len(set(rosters[initial_index]) & set(rosters[index]))
            return (
                *(int(-value) for value in counts[index]),
                -float(q99[index]),
                -float(means[index]),
                churn,
                rosters[index],
            )

        ordered = sorted(reachable, key=key)
        retained = ordered[:cap]
        if initial_index not in retained:
            retained = [*retained[:-1], initial_index]
        if not retained or len(retained) > cap or len(set(retained)) != len(retained):
            raise ValueError("recourse-aware alternative retention differs")
        output.append(tuple(retained))
    return tuple(output)


def select_recourse_aware_initials(
    lineups: Sequence[Lineup],
    training_totals: np.ndarray,
    alternatives: Sequence[Sequence[int]],
    *,
    entries: int = 80,
) -> list[int]:
    """Select initial entries by reachable-union tail coverage."""
    candidates = tuple(lineups)
    totals = np.asarray(training_totals, dtype=np.float32)
    if totals.ndim != 2 or totals.shape != (len(candidates), totals.shape[1]) or \
            totals.shape[1] == 0 or not np.isfinite(totals).all():
        raise ValueError("recourse-aware selector totals differ")
    if type(entries) is not int or entries <= 0 or entries > len(candidates):
        raise ValueError("recourse-aware selector entry count differs")
    if len(alternatives) != len(candidates):
        raise ValueError("recourse-aware alternative population differs")
    normalized = []
    for index, values in enumerate(alternatives):
        row = tuple(int(value) for value in values)
        if not row or len(row) > ALTERNATIVE_CAP or len(set(row)) != len(row) or \
                index not in row or any(value < 0 or value >= len(candidates)
                                    for value in row):
            raise ValueError("recourse-aware alternative set differs")
        normalized.append(row)
    rosters = tuple(_roster(lineup) for lineup in candidates)
    if len(set(rosters)) != len(rosters):
        raise ValueError("recourse-aware selector candidate repeats")
    option_best = np.stack([
        totals[list(values)].max(axis=0) for values in normalized
    ]).astype(np.float32)
    byte_popcount = np.unpackbits(
        np.arange(256, dtype=np.uint8)[:, None], axis=1,
    ).sum(axis=1, dtype=np.uint8)
    option_packed = [
        np.packbits(option_best >= threshold, axis=1, bitorder="little")
        for threshold in TAILS
    ]
    initial_counts = [
        np.count_nonzero(totals >= threshold, axis=1) for threshold in TAILS
    ]
    q99 = np.quantile(totals, 0.99, axis=1)
    means = totals.mean(axis=1, dtype=np.float64)
    covered = [
        np.zeros(packed.shape[1], dtype=np.uint8) for packed in option_packed
    ]
    exposed: set[int] = set()
    remaining = set(range(len(candidates)))
    selected = []
    while len(selected) < entries:
        indices = np.asarray(sorted(remaining), dtype=np.int64)
        gains = [
            byte_popcount[np.bitwise_and(
                packed[indices], np.bitwise_not(current),
            )].sum(axis=1, dtype=np.int64)
            for packed, current in zip(option_packed, covered, strict=True)
        ]
        best_index = None
        best_numeric = None
        best_roster = None
        for offset, index_value in enumerate(indices):
            index = int(index_value)
            numeric = (
                *(int(values[offset]) for values in gains),
                len(set(normalized[index]) - exposed),
                *(int(values[index]) for values in initial_counts),
                float(q99[index]),
                float(means[index]),
            )
            roster = rosters[index]
            if best_numeric is None or numeric > best_numeric or (
                numeric == best_numeric and roster < best_roster
            ):
                best_index = index
                best_numeric = numeric
                best_roster = roster
        if best_index is None:
            raise ValueError("recourse-aware selector cannot fill exact entries")
        selected.append(best_index)
        remaining.remove(best_index)
        exposed.update(normalized[best_index])
        for packed, current in zip(option_packed, covered, strict=True):
            current |= packed[best_index]
    if len(selected) != entries or len(set(selected)) != entries:
        raise ValueError("recourse-aware selector is not exact and unique")
    return selected


def scorefree_book_metrics(
    selected: Sequence[int],
    heldout_totals: np.ndarray,
    alternatives: Sequence[Sequence[int]],
    locked_signatures: Sequence[Sequence[tuple[int, str]]],
) -> dict[str, object]:
    """Report initial-book and reachable-union held-out metrics."""
    totals = np.asarray(heldout_totals, dtype=np.float32)
    chosen = tuple(int(value) for value in selected)
    if totals.ndim != 2 or totals.shape[1] == 0 or \
            not np.isfinite(totals).all() or not chosen or \
            len(chosen) != len(set(chosen)) or any(
                value < 0 or value >= totals.shape[0] for value in chosen
            ) or len(alternatives) != totals.shape[0] or \
            len(locked_signatures) != totals.shape[0]:
        raise ValueError("recourse-aware metric population differs")
    reachable = sorted({
        int(alternative)
        for index in chosen
        for alternative in alternatives[index]
    })
    if not reachable or any(value < 0 or value >= totals.shape[0]
                            for value in reachable):
        raise ValueError("recourse-aware metric alternative differs")
    initial_best = totals[list(chosen)].max(axis=0)
    reachable_best = totals[reachable].max(axis=0)

    def coverage(values: np.ndarray) -> dict[str, dict[str, float | int]]:
        return {
            str(int(threshold)): {
                "events": int(np.count_nonzero(values >= threshold)),
                "rate": float(np.mean(values >= threshold)),
            }
            for threshold in TAILS
        }

    option_counts = [len(set(alternatives[index])) for index in chosen]
    signatures = {
        tuple((int(slot), str(player)) for slot, player in locked_signatures[index])
        for index in chosen
    }
    signature_counts: dict[tuple[tuple[int, str], ...], int] = {}
    slot_counts = {str(index): 0 for index in range(len(SLOTS))}
    player_counts: dict[str, int] = {}
    locked_count_distribution = {str(index): 0 for index in range(10)}
    for index in chosen:
        signature = tuple(
            (int(slot), str(player)) for slot, player in locked_signatures[index]
        )
        signature_counts[signature] = signature_counts.get(signature, 0) + 1
        locked_count_distribution[str(len(signature))] += 1
        for slot, player_id in signature:
            slot_counts[str(slot)] += 1
            player_counts[player_id] = player_counts.get(player_id, 0) + 1
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "entries": len(chosen),
        "worlds": int(totals.shape[1]),
        "initial_coverage": coverage(initial_best),
        "reachable_union_coverage": coverage(reachable_best),
        "reachable_alternatives": len(reachable),
        "alternatives_per_entry": {
            "minimum": min(option_counts),
            "median": float(median(option_counts)),
            "mean": float(np.mean(option_counts)),
            "maximum": max(option_counts),
        },
        "distinct_locked_slot_signatures": len(signatures),
        "locked_slot_count_distribution": locked_count_distribution,
        "locked_slot_index_distribution": slot_counts,
        "locked_player_frequency": [
            {"player_id": player_id, "entries": entries}
            for player_id, entries in sorted(player_counts.items())
        ],
        "locked_signature_frequency": [
            {
                "signature": [list(value) for value in signature],
                "entries": entries,
            }
            for signature, entries in sorted(signature_counts.items())
        ],
    }


def evaluate_scorefree_fold(
    control: Mapping[str, object],
    kickoff_by_id: Mapping[str, object],
    decision: datetime | pd.Timestamp | str,
) -> dict[str, object]:
    """Evaluate one train-four/test-one option-value selector fold."""
    if control.get("uses_realized_outcomes") is not False:
        raise ValueError("recourse-aware control is outcome-facing")
    candidates = tuple(control.get("candidate_lineups", ()))
    incumbent = tuple(control.get("control_lineups", ()))
    player_ids = tuple(str(value) for value in control.get("player_ids", ()))
    training_blocks = tuple(str(value) for value in control.get(
        "training_blocks", (),
    ))
    totals_by_block = control.get("candidate_totals_by_block")
    heldout_draws = np.asarray(control.get("heldout_row_draws"), dtype=np.float32)
    if len(candidates) < 80 or len(incumbent) != 80 or \
            len(set(_roster(value) for value in candidates)) != len(candidates) or \
            len(set(_roster(value) for value in incumbent)) != 80 or \
            len(training_blocks) != 4 or not isinstance(totals_by_block, Mapping) or \
            set(totals_by_block) != set(training_blocks) or \
            len(player_ids) == 0 or len(set(player_ids)) != len(player_ids) or \
            heldout_draws.ndim != 2 or heldout_draws.shape[0] != len(player_ids) or \
            heldout_draws.shape[1] != 10_000 or \
            not np.isfinite(heldout_draws).all():
        raise ValueError("recourse-aware fold control contract differs")
    training_parts = [
        np.asarray(totals_by_block[name], dtype=np.float32)
        for name in training_blocks
    ]
    if any(part.shape != (len(candidates), 10_000)
           or not np.isfinite(part).all() for part in training_parts):
        raise ValueError("recourse-aware fold training totals differ")
    training_totals = np.concatenate(training_parts, axis=1)
    player_index = {player_id: row for row, player_id in enumerate(player_ids)}
    try:
        candidate_rows = np.asarray([
            [player_index[player_id] for player_id in _roster(lineup)]
            for lineup in candidates
        ], dtype=np.int64)
    except KeyError as exc:
        raise ValueError("recourse-aware fold candidate is outside universe") \
            from exc
    heldout_totals = heldout_draws[candidate_rows].sum(axis=1).astype(np.float32)
    alternatives = build_alternative_sets(
        candidates, training_totals, kickoff_by_id, decision,
    )
    by_roster = {_roster(lineup): index for index, lineup in enumerate(candidates)}
    try:
        control_indices = [by_roster[_roster(lineup)] for lineup in incumbent]
    except KeyError as exc:
        raise ValueError("recourse-aware control is outside candidate pool") from exc
    treatment_indices = select_recourse_aware_initials(
        candidates, training_totals, alternatives, entries=80,
    )
    signatures = tuple(
        locked_slot_signature(lineup, kickoff_by_id, decision)
        for lineup in candidates
    )
    control_metrics = scorefree_book_metrics(
        control_indices, heldout_totals, alternatives, signatures,
    )
    treatment_metrics = scorefree_book_metrics(
        treatment_indices, heldout_totals, alternatives, signatures,
    )
    control_rosters = [_roster(candidates[index]) for index in control_indices]
    treatment_rosters = [_roster(candidates[index]) for index in treatment_indices]
    overlap = len(set(control_rosters) & set(treatment_rosters))
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "heldout_block": str(control.get("heldout_block", "")),
        "training_blocks": list(training_blocks),
        "candidate_budget": len(candidates),
        "alternative_cap": ALTERNATIVE_CAP,
        "control": control_metrics,
        "treatment": treatment_metrics,
        "selected_identity_overlap": overlap,
        "selected_identity_jaccard": float(overlap / (160 - overlap)),
        "control_selected_rosters": [list(value) for value in control_rosters],
        "treatment_selected_rosters": [list(value) for value in treatment_rosters],
    }


def _summarize_fold_group(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {"folds": len(rows)}
    for family in ("initial_coverage", "reachable_union_coverage"):
        result[family] = {
            arm: {
                str(int(threshold)): int(sum(
                    int(row[arm][family][str(int(threshold))]["events"])
                    for row in rows
                ))
                for threshold in TAILS
            }
            for arm in ("control", "treatment")
        }
    for metric in ("reachable_alternatives", "distinct_locked_slot_signatures"):
        result[metric] = {
            arm: {
                "total": int(sum(int(row[arm][metric]) for row in rows)),
                "mean": float(np.mean([int(row[arm][metric]) for row in rows])),
            }
            for arm in ("control", "treatment")
        }
    result["selected_identity_overlap"] = {
        "mean_of_80": float(np.mean([
            int(row["selected_identity_overlap"]) for row in rows
        ])),
        "minimum_of_80": int(min(
            int(row["selected_identity_overlap"]) for row in rows
        )),
    }
    for metric in (
        "locked_slot_count_distribution", "locked_slot_index_distribution",
    ):
        result[metric] = {
            arm: {
                key: int(sum(int(row[arm][metric][key]) for row in rows))
                for key in sorted(rows[0][arm][metric], key=int)
            }
            for arm in ("control", "treatment")
        }
    return result


def _effective_rank_from_books(
    books: Sequence[Sequence[Sequence[str]]],
) -> float:
    identities = sorted({
        tuple(sorted(str(value) for value in roster))
        for book in books for roster in book
    })
    index = {roster: column for column, roster in enumerate(identities)}
    matrix = np.zeros((len(books), len(identities)), dtype=np.float64)
    for row, book in enumerate(books):
        for roster in book:
            matrix[row, index[tuple(sorted(str(value) for value in roster))]] = 1.0
    eigenvalues = np.linalg.eigvalsh(matrix @ matrix.T)
    eigenvalues = eigenvalues[eigenvalues > 1e-12]
    if not len(eigenvalues):
        return 0.0
    probabilities = eigenvalues / eigenvalues.sum()
    return float(np.exp(-np.sum(probabilities * np.log(probabilities))))


def _selection_effective_rank(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    by_slate = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            slate = sorted(
                [row for row in rows if int(row["season"]) == season
                 and int(row["week"]) == week],
                key=lambda row: str(row["heldout_block"]),
            )
            if len(slate) != 5:
                raise ValueError("recourse-aware effective-rank slate differs")
            by_slate.append({
                "season": season,
                "week": week,
                **{
                    arm: _effective_rank_from_books([
                        row[f"{arm}_selected_rosters"] for row in slate
                    ])
                    for arm in ("control", "treatment")
                },
            })
    return {
        "definition": (
            "exp_entropy_of_nonzero_eigenvalues_of_five_fold_"
            "book_incidence_gram_matrix"
        ),
        "by_slate": by_slate,
        "summary": {
            arm: {
                "mean": float(np.mean([row[arm] for row in by_slate])),
                "minimum": float(min(row[arm] for row in by_slate)),
                "maximum": float(max(row[arm] for row in by_slate)),
            }
            for arm in ("control", "treatment")
        },
    }


def _gate_from_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    aggregate = _summarize_fold_group(rows)
    by_block = {
        f"R{block}": _summarize_fold_group([
            row for row in rows if row["heldout_block"] == f"R{block}"
        ])
        for block in range(5)
    }

    def events(summary, family: str, arm: str, threshold: int) -> int:
        return int(summary[family][arm][str(threshold)])

    reachable_p230_gain = events(
        aggregate, "reachable_union_coverage", "treatment", 230,
    ) - events(aggregate, "reachable_union_coverage", "control", 230)
    improving_p230_blocks = sum(
        events(value, "reachable_union_coverage", "treatment", 230) >
        events(value, "reachable_union_coverage", "control", 230)
        for value in by_block.values()
    )
    initial_high_nondecline = all(
        events(aggregate, "initial_coverage", "treatment", threshold) >=
        events(aggregate, "initial_coverage", "control", threshold)
        for threshold in (240, 230, 220)
    )
    control_p194 = events(aggregate, "initial_coverage", "control", 194)
    treatment_p194 = events(aggregate, "initial_coverage", "treatment", 194)
    p194_ratio = float(treatment_p194 / control_p194) if control_p194 else 1.0
    conditions = {
        "reachable_p230_strict_and_three_blocks": (
            reachable_p230_gain > 0 and improving_p230_blocks >= 3
        ),
        "reachable_p240_p220_p210_nondecline": all(
            events(aggregate, "reachable_union_coverage", "treatment", threshold) >=
            events(aggregate, "reachable_union_coverage", "control", threshold)
            for threshold in (240, 220, 210)
        ),
        "initial_p240_p230_p220_nondecline": initial_high_nondecline,
        "initial_p194_retention_at_least_95pct": p194_ratio >= 0.95,
        "mean_reachable_alternatives_nondecline": bool(
            aggregate["reachable_alternatives"]["treatment"]["mean"] >=
            aggregate["reachable_alternatives"]["control"]["mean"]
        ),
        "locked_slot_signature_nondecline": bool(
            aggregate["distinct_locked_slot_signatures"]["treatment"]["total"] >=
            aggregate["distinct_locked_slot_signatures"]["control"]["total"]
        ),
    }
    return {
        "summary": aggregate,
        "by_block": by_block,
        "conditions": conditions,
        "diagnostics": {
            "reachable_p230_event_gain": reachable_p230_gain,
            "improving_p230_blocks": improving_p230_blocks,
            "initial_p194_retention_ratio": p194_ratio,
        },
        "passed": all(conditions.values()),
    }


def aggregate_scorefree_folds(
    folds: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Apply the frozen six-condition gate to all 270 held-out folds."""
    rows = list(folds)
    expected = {
        (season, week, f"R{block}")
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
        for block in range(5)
    }
    actual = {
        (int(row.get("season", 0)), int(row.get("week", 0)),
         str(row.get("heldout_block", "")))
        for row in rows
    }
    if len(rows) != 270 or len(actual) != 270 or actual != expected:
        raise ValueError("recourse-aware aggregate fold grid differs")
    for row in rows:
        if row.get("version") != VERSION or \
                row.get("uses_realized_outcomes") is not False or \
                int(row.get("candidate_budget", 0)) < 80 or \
                int(row.get("alternative_cap", 0)) != ALTERNATIVE_CAP:
            raise ValueError("recourse-aware aggregate fold contract differs")
        for arm in ("control", "treatment"):
            metrics = row.get(arm)
            if not isinstance(metrics, Mapping) or \
                    metrics.get("uses_realized_outcomes") is not False or \
                    metrics.get("entries") != 80 or metrics.get("worlds") != 10_000:
                raise ValueError("recourse-aware aggregate book contract differs")
            for family in ("initial_coverage", "reachable_union_coverage"):
                values = metrics.get(family)
                if not isinstance(values, Mapping) or set(values) != {
                    str(int(threshold)) for threshold in TAILS
                }:
                    raise ValueError("recourse-aware aggregate tail grid differs")
                for value in values.values():
                    events = value.get("events") if isinstance(value, Mapping) else None
                    rate = value.get("rate") if isinstance(value, Mapping) else None
                    if type(events) is not int or not 0 <= events <= 10_000 or \
                            not isinstance(rate, (int, float)) or not np.isclose(
                                float(rate), events / 10_000, rtol=0.0, atol=1e-12,
                            ):
                        raise ValueError("recourse-aware aggregate tail value differs")
    gate = _gate_from_rows(rows)
    aggregate = gate["summary"]
    by_block = gate["by_block"]
    by_season = {
        str(season): _summarize_fold_group([
            row for row in rows if int(row["season"]) == season
        ])
        for season in (2023, 2024, 2025)
    }

    conditions = gate["conditions"]
    passed = gate["passed"]
    leave_one_slate_out = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            subset = [
                row for row in rows
                if not (int(row["season"]) == season and int(row["week"]) == week)
            ]
            sensitivity = _gate_from_rows(subset)
            leave_one_slate_out.append({
                "omitted_season": season,
                "omitted_week": week,
                "reachable_p230_event_gain": sensitivity["diagnostics"][
                    "reachable_p230_event_gain"
                ],
                "conditions": sensitivity["conditions"],
                "passed": sensitivity["passed"],
                "condition_flips_vs_full": sorted(
                    key for key, value in conditions.items()
                    if sensitivity["conditions"][key] != value
                ),
            })
    return {
        "version": "recourse-aware-initial-book-scorefree-report-v1",
        "mechanism_version": VERSION,
        "protocol_sha256": PROTOCOL_SHA256,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_policy_diagnostic_licensed": passed,
        "mechanical": {
            "slates": 54,
            "folds": 270,
            "worlds_per_fold": 10_000,
            "all_valid": True,
        },
        "aggregate": aggregate,
        "by_block": by_block,
        "by_season": by_season,
        "selection_effective_rank": _selection_effective_rank(rows),
        "leave_one_slate_out_influence": leave_one_slate_out,
        "gate_diagnostics": gate["diagnostics"],
        "conditions": conditions,
        "passed": passed,
        "disposition": (
            "recourse-aware-initial-book-premise-passes"
            if passed else
            "recourse-aware-candidate-union-selector-premise-fails"
        ),
    }
