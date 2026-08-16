"""Outcome-free primitives for the frozen constraint-lattice sleeve.

The module names the only five strategic exceptions admitted by
``20260816-constraint-lattice-scorefree-v1``.  It deliberately contains no
realized-score, ownership, contest-rank or payout input.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations

import numpy as np

from ..optimizer.lineup import Lineup, StackRules


VERSION = "constraint-lattice-scorefree-v1"
CELL_ORDER = (
    "qb1_bringback",
    "qb2_no_bringback",
    "qb1_no_bringback",
    "rb_vs_dst",
    "two_rb_same_team",
)
CELL_QUOTAS = {
    "qb1_bringback": 2,
    "qb2_no_bringback": 2,
    "qb1_no_bringback": 2,
    "rb_vs_dst": 1,
    "two_rb_same_team": 1,
}
TRAINING_THRESHOLDS = (230.0, 210.0, 194.0)
REPORT_THRESHOLDS = (187.0, 194.0, 200.0, 210.0, 220.0, 230.0, 240.0)


@dataclass
class ExceptionCandidate:
    lineup: Lineup
    cell: str
    totals_by_block: Mapping[str, np.ndarray]


def _roster_key(lineup: Lineup) -> tuple[str, ...]:
    key = tuple(sorted(str(value) for value in lineup.ids))
    if len(key) != 9:
        raise ValueError("constraint-lattice roster must contain nine players")
    return key


def _normalize_blocks(
    totals_by_block: Mapping[str, np.ndarray],
    blocks: Sequence[str],
    *,
    expected_rows: int | None = None,
) -> dict[str, np.ndarray]:
    names = tuple(str(value) for value in blocks)
    if not names or len(names) != len(set(names)) or set(totals_by_block) != set(names):
        raise ValueError("constraint-lattice simulation block identity differs")
    normalized = {}
    widths = set()
    for name in names:
        values = np.asarray(totals_by_block[name], dtype=np.float64)
        if values.ndim not in ({1, 2} if expected_rows is None else {2}) or \
                values.shape[-1] == 0 or not np.isfinite(values).all():
            raise ValueError("constraint-lattice simulation totals are invalid")
        if expected_rows is not None and values.shape[0] != expected_rows:
            raise ValueError("constraint-lattice control block row count differs")
        normalized[name] = values
        widths.add(int(values.shape[-1]))
    if len(widths) != 1:
        raise ValueError("constraint-lattice simulation block widths differ")
    return normalized


def _individual_metrics(
    totals_by_block: Mapping[str, np.ndarray], blocks: Sequence[str],
) -> dict[str, object]:
    normalized = _normalize_blocks(totals_by_block, blocks)
    if any(values.ndim != 1 for values in normalized.values()):
        raise ValueError("constraint-lattice candidate totals must be vectors")
    probabilities = {
        f"p{threshold:g}": {
            name: float(np.mean(normalized[name] >= threshold))
            for name in blocks
        }
        for threshold in TRAINING_THRESHOLDS
    }
    combined = np.concatenate([normalized[name] for name in blocks])
    return {
        "probabilities": probabilities,
        "q99": float(np.quantile(combined, 0.99)),
        "mean": float(np.mean(combined)),
    }


def rank_exception_candidates(
    candidates: Sequence[ExceptionCandidate], blocks: Sequence[str],
) -> tuple[list[ExceptionCandidate], list[dict[str, object]]]:
    """Deduplicate and retain fixed per-cell quotas on training blocks."""
    names = tuple(str(value) for value in blocks)
    by_roster: dict[tuple[str, ...], ExceptionCandidate] = {}
    for candidate in candidates:
        if candidate.cell not in CELL_ORDER or exception_cell(
            candidate.lineup
        ) != candidate.cell:
            raise ValueError("constraint-lattice candidate cell differs")
        key = _roster_key(candidate.lineup)
        existing = by_roster.get(key)
        if existing is not None and existing.cell != candidate.cell:
            raise ValueError("constraint-lattice roster spans atomic cells")
        by_roster.setdefault(key, candidate)

    retained: list[ExceptionCandidate] = []
    receipts: list[dict[str, object]] = []
    for cell in CELL_ORDER:
        rows = []
        for key, candidate in by_roster.items():
            if candidate.cell != cell:
                continue
            metrics = _individual_metrics(candidate.totals_by_block, names)
            probabilities = metrics["probabilities"]
            assert isinstance(probabilities, dict)
            rank = (
                min(probabilities["p230"].values()),
                sum(probabilities["p230"].values()),
                min(probabilities["p210"].values()),
                sum(probabilities["p210"].values()),
                min(probabilities["p194"].values()),
                sum(probabilities["p194"].values()),
                float(metrics["q99"]),
                float(metrics["mean"]),
            )
            rows.append((rank, key, candidate, metrics))
        rows.sort(key=lambda row: (tuple(-value for value in row[0]), row[1]))
        for within_cell_rank, (_, key, candidate, metrics) in enumerate(
            rows[:CELL_QUOTAS[cell]], start=1,
        ):
            retained.append(candidate)
            receipts.append({
                "cell": cell,
                "within_cell_rank": within_cell_rank,
                "roster": list(key),
                **metrics,
            })
    return retained, receipts


def _book_coverage_counts(
    totals_by_block: Mapping[str, np.ndarray], blocks: Sequence[str],
    thresholds: Sequence[float] = TRAINING_THRESHOLDS,
) -> dict[str, dict[str, int]]:
    normalized = _normalize_blocks(totals_by_block, blocks)
    if any(values.ndim != 2 for values in normalized.values()):
        raise ValueError("constraint-lattice book totals must be matrices")
    return {
        f"{threshold:g}": {
            name: int(np.count_nonzero(np.max(normalized[name], axis=0) >= threshold))
            for name in blocks
        }
        for threshold in thresholds
    }


def construct_exception_sleeve(
    control_lineups: Sequence[Lineup],
    control_totals_by_block: Mapping[str, np.ndarray],
    candidates: Sequence[ExceptionCandidate],
    blocks: Sequence[str],
) -> dict[str, object]:
    """Apply the frozen p230-first exact-80 training-block swap law."""
    names = tuple(str(value) for value in blocks)
    if len(names) != 4:
        raise ValueError("constraint-lattice sleeve requires four training blocks")
    lineups = list(control_lineups)
    if len(lineups) != 80 or len({_roster_key(row) for row in lineups}) != 80:
        raise ValueError("constraint-lattice control must be exact 80")
    totals = _normalize_blocks(
        control_totals_by_block, names, expected_rows=len(lineups),
    )
    original_coverage = _book_coverage_counts(totals, names)
    original_p194 = sum(original_coverage["194"].values())
    current_cells: list[str | None] = [None] * len(lineups)
    admitted = []
    rejected = []

    for candidate in candidates:
        if candidate.cell not in CELL_ORDER or exception_cell(
            candidate.lineup
        ) != candidate.cell:
            raise ValueError("constraint-lattice sleeve candidate differs")
        candidate_key = _roster_key(candidate.lineup)
        candidate_totals = _normalize_blocks(candidate.totals_by_block, names)
        if any(values.ndim != 1 for values in candidate_totals.values()):
            raise ValueError("constraint-lattice sleeve candidate totals differ")
        if candidate_key in {_roster_key(row) for row in lineups}:
            rejected.append({
                "cell": candidate.cell, "roster": list(candidate_key),
                "reason": "duplicate_current_roster",
            })
            continue
        current_coverage = _book_coverage_counts(totals, names)
        best = None
        for index, current_cell in enumerate(current_cells):
            if current_cell is not None:
                continue
            proposed = {
                name: np.asarray(totals[name]).copy() for name in names
            }
            for name in names:
                proposed[name][index] = candidate_totals[name]
            after = _book_coverage_counts(proposed, names)
            delta = {
                threshold: {
                    name: after[threshold][name] - current_coverage[threshold][name]
                    for name in names
                }
                for threshold in ("230", "210", "194")
            }
            numeric = (
                min(delta["230"].values()), sum(delta["230"].values()),
                min(delta["210"].values()), sum(delta["210"].values()),
                min(delta["194"].values()), sum(delta["194"].values()),
            )
            removed_key = _roster_key(lineups[index])
            if best is None or numeric > best[0] or (
                numeric == best[0] and removed_key < best[1]
            ):
                best = (numeric, removed_key, index, proposed, after, delta)
        if best is None:
            rejected.append({
                "cell": candidate.cell, "roster": list(candidate_key),
                "reason": "no_removable_strict_lineup",
            })
            continue
        _, removed_key, index, proposed, after, delta = best
        p194_retention = (
            float(sum(after["194"].values()) / original_p194)
            if original_p194 else 1.0
        )
        accepted = (
            sum(value >= 1 for value in delta["230"].values()) >= 3
            and min(delta["230"].values()) >= 0
            and min(delta["210"].values()) >= 0
            and p194_retention >= 0.95
        )
        receipt = {
            "cell": candidate.cell,
            "roster": list(candidate_key),
            "removed_roster": list(removed_key),
            "delta_world_counts": delta,
            "p194_retention_vs_original_control": p194_retention,
        }
        if not accepted:
            rejected.append({**receipt, "reason": "admission_margin_failed"})
            continue
        lineups[index] = candidate.lineup
        current_cells[index] = candidate.cell
        totals = proposed
        admitted.append(receipt)

    exception_lineups = [
        lineup for lineup, cell in zip(lineups, current_cells, strict=True)
        if cell is not None
    ]
    exception_cells = [cell for cell in current_cells if cell is not None]
    counts = validate_exception_book(exception_lineups, exception_cells)
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "lineups": lineups,
        "totals_by_block": totals,
        "exception_cells_by_index": current_cells,
        "exception_counts": counts,
        "admitted": admitted,
        "rejected": rejected,
        "control_coverage_world_counts": original_coverage,
        "treatment_coverage_world_counts": _book_coverage_counts(totals, names),
    }


def stack_rules_for_cell(cell: str) -> StackRules:
    """Return the exact one-cell optimizer contract from the frozen protocol."""
    if cell == "qb1_bringback":
        return StackRules(
            qb_stack_min=1,
            qb_stack_max=1,
            bring_back_min=1,
            forbid_rb_vs_dst=True,
            forbid_two_rb_same_team=True,
        )
    if cell == "qb2_no_bringback":
        return StackRules(
            qb_stack_min=2,
            bring_back_min=0,
            bring_back_max=0,
            forbid_rb_vs_dst=True,
            forbid_two_rb_same_team=True,
        )
    if cell == "qb1_no_bringback":
        return StackRules(
            qb_stack_min=1,
            qb_stack_max=1,
            bring_back_min=0,
            bring_back_max=0,
            forbid_rb_vs_dst=True,
            forbid_two_rb_same_team=True,
        )
    if cell == "rb_vs_dst":
        return StackRules(
            qb_stack_min=2,
            bring_back_min=1,
            forbid_rb_vs_dst=False,
            forbid_two_rb_same_team=True,
            require_rb_vs_dst=True,
        )
    if cell == "two_rb_same_team":
        return StackRules(
            qb_stack_min=2,
            bring_back_min=1,
            forbid_rb_vs_dst=True,
            forbid_two_rb_same_team=False,
            require_two_rb_same_team=True,
        )
    raise ValueError(f"unknown constraint-lattice cell {cell!r}")


def lineup_constraint_profile(lineup: Lineup) -> dict[str, object]:
    """Describe only the strategic constraints needed to classify a cell."""
    players = list(lineup.players)
    if len(players) != 9 or len(lineup.ids) != 9:
        raise ValueError("constraint-lattice lineup must contain nine players")
    quarterbacks = [
        row for row in players if str(row.get("pos", "")).upper() == "QB"
    ]
    defenses = [
        row for row in players if str(row.get("pos", "")).upper() == "DST"
    ]
    if len(quarterbacks) != 1 or len(defenses) != 1:
        raise ValueError("constraint-lattice lineup needs one QB and one DST")
    qb = quarterbacks[0]
    dst = defenses[0]
    qb_team = str(qb.get("team", ""))
    qb_opp = str(qb.get("opp", ""))
    if not qb_team or not qb_opp or not str(dst.get("opp", "")):
        raise ValueError("constraint-lattice team/opponent metadata is incomplete")
    qb_stack = sum(
        str(row.get("team", "")) == qb_team
        and str(row.get("pos", "")).upper() in {"WR", "TE"}
        for row in players
    )
    bring_backs = sum(
        str(row.get("team", "")) == qb_opp
        and str(row.get("pos", "")).upper() in {"RB", "WR", "TE"}
        for row in players
    )
    running_backs = [
        row for row in players if str(row.get("pos", "")).upper() == "RB"
    ]
    rb_teams = Counter(str(row.get("team", "")) for row in running_backs)
    rb_vs_dst = any(
        str(row.get("team", "")) == str(dst.get("opp", ""))
        for row in running_backs
    )
    return {
        "qb_stack": int(qb_stack),
        "bring_backs": int(bring_backs),
        "rb_vs_dst": bool(rb_vs_dst),
        "two_rb_same_team": bool(max(rb_teams.values(), default=0) >= 2),
    }


def exception_cell(lineup: Lineup) -> str | None:
    """Return the unique atomic cell, or ``None`` for a strict/invalid mix.

    A roster that violates multiple named strategic constraints is excluded;
    the experiment is designed to isolate one exception at a time.
    """
    profile = lineup_constraint_profile(lineup)
    qb_stack = int(profile["qb_stack"])
    bring_backs = int(profile["bring_backs"])
    rb_vs_dst = bool(profile["rb_vs_dst"])
    two_rb_same_team = bool(profile["two_rb_same_team"])
    if rb_vs_dst or two_rb_same_team:
        if qb_stack < 2 or bring_backs < 1 or rb_vs_dst == two_rb_same_team:
            return None
        return "rb_vs_dst" if rb_vs_dst else "two_rb_same_team"
    if qb_stack == 1 and bring_backs >= 1:
        return "qb1_bringback"
    if qb_stack >= 2 and bring_backs == 0:
        return "qb2_no_bringback"
    if qb_stack == 1 and bring_backs == 0:
        return "qb1_no_bringback"
    return None


def is_strict_lineup(lineup: Lineup) -> bool:
    """Return whether all four incumbent strategic constraints are present."""
    profile = lineup_constraint_profile(lineup)
    return bool(
        int(profile["qb_stack"]) >= 2
        and int(profile["bring_backs"]) >= 1
        and not bool(profile["rb_vs_dst"])
        and not bool(profile["two_rb_same_team"])
    )


def validate_exception_book(
    lineups: Sequence[Lineup], cells: Sequence[str],
) -> dict[str, int]:
    """Validate exact cell labels, quotas and unique roster identities."""
    if len(lineups) != len(cells):
        raise ValueError("constraint-lattice lineups/cells are misaligned")
    rosters = [tuple(sorted(str(value) for value in row.ids)) for row in lineups]
    if len(rosters) != len(set(rosters)):
        raise ValueError("constraint-lattice exception rosters repeat")
    counts = Counter(str(cell) for cell in cells)
    if set(counts) - set(CELL_ORDER):
        raise ValueError("constraint-lattice book contains an unknown cell")
    for lineup, cell in zip(lineups, cells, strict=True):
        if exception_cell(lineup) != cell:
            raise ValueError("constraint-lattice exception classification differs")
    if any(counts[cell] > CELL_QUOTAS[cell] for cell in CELL_ORDER):
        raise ValueError("constraint-lattice cell quota exceeded")
    if len(lineups) > sum(CELL_QUOTAS.values()):
        raise ValueError("constraint-lattice sleeve exceeds eight entries")
    return {cell: int(counts[cell]) for cell in CELL_ORDER}


def _structure_reach(lineups: Sequence[Lineup]) -> dict[str, int]:
    players = set()
    pairs = set()
    cores = set()
    games = set()
    for lineup in lineups:
        roster = _roster_key(lineup)
        players.update(roster)
        pairs.update(combinations(roster, 2))
        rows = list(lineup.players)
        quarterbacks = [
            row for row in rows if str(row.get("pos", "")).upper() == "QB"
        ]
        if len(quarterbacks) != 1:
            raise ValueError("constraint-lattice structure requires one QB")
        qb = quarterbacks[0]
        qb_id = str(qb.get("id", ""))
        qb_team = str(qb.get("team", ""))
        qb_opp = str(qb.get("opp", ""))
        core = tuple(sorted([
            qb_id,
            *(str(row["id"]) for row in rows if (
                str(row.get("team", "")) == qb_team
                and str(row.get("pos", "")).upper() in {"WR", "TE"}
            )),
            *(str(row["id"]) for row in rows if (
                str(row.get("team", "")) == qb_opp
                and str(row.get("pos", "")).upper() in {"RB", "WR", "TE"}
            )),
        ]))
        cores.add(core)
        counts = Counter(
            str(row.get("game_id", "")) for row in rows if row.get("game_id")
        )
        if counts:
            games.add(min(counts, key=lambda key: (-counts[key], key)))
    return {
        "unique_players": len(players),
        "unique_player_pairs": len(pairs),
        "unique_qb_stack_cores": len(cores),
        "unique_dominant_games": len(games),
    }


def evaluate_heldout_fold(
    *,
    heldout_block: str,
    control_lineups: Sequence[Lineup],
    treatment_lineups: Sequence[Lineup],
    control_totals: np.ndarray,
    treatment_totals: np.ndarray,
) -> dict[str, object]:
    """Measure two frozen exact-80 books on one untouched simulation block."""
    control = list(control_lineups)
    treatment = list(treatment_lineups)
    left = np.asarray(control_totals, dtype=np.float64)
    right = np.asarray(treatment_totals, dtype=np.float64)
    if len(control) != 80 or len(treatment) != 80 or \
            len({_roster_key(row) for row in control}) != 80 or \
            len({_roster_key(row) for row in treatment}) != 80:
        raise ValueError("constraint-lattice held-out books must be exact 80")
    if left.shape != right.shape or left.ndim != 2 or left.shape[0] != 80 or \
            left.shape[1] == 0 or not np.isfinite(left).all() or \
            not np.isfinite(right).all():
        raise ValueError("constraint-lattice held-out totals differ")
    control_keys = {_roster_key(row) for row in control}
    treatment_new = [
        row for row in treatment if _roster_key(row) not in control_keys
    ]
    cells = [exception_cell(row) for row in treatment_new]
    if any(cell is None for cell in cells):
        raise ValueError("constraint-lattice treatment adds a non-atomic roster")
    counts = validate_exception_book(treatment_new, cells)
    if any(not is_strict_lineup(row) for row in control):
        raise ValueError("constraint-lattice held-out control is not strict")

    maxima = {
        "control": np.max(left, axis=0),
        "treatment": np.max(right, axis=0),
    }
    threshold_counts = {
        book: {
            f"{threshold:g}": int(np.count_nonzero(values >= threshold))
            for threshold in REPORT_THRESHOLDS
        }
        for book, values in maxima.items()
    }
    summaries = {
        book: {
            "mean": float(np.mean(values)),
            "q90": float(np.quantile(values, 0.90)),
            "q95": float(np.quantile(values, 0.95)),
            "q99": float(np.quantile(values, 0.99)),
        }
        for book, values in maxima.items()
    }
    control_structure = _structure_reach(control)
    treatment_structure = _structure_reach(treatment)
    shared = len(control_keys & {_roster_key(row) for row in treatment})
    treatment_rosters = [_roster_key(row) for row in treatment]
    maximum_overlap = max(
        len(set(first) & set(second))
        for index, first in enumerate(treatment_rosters)
        for second in treatment_rosters[index + 1:]
    )
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "heldout_block": str(heldout_block),
        "worlds": int(left.shape[1]),
        "mechanical_valid": True,
        "control_entries": 80,
        "treatment_entries": 80,
        "exception_counts": counts,
        "new_exception_entries": len(treatment_new),
        "shared_rosters": shared,
        "maximum_treatment_pairwise_roster_overlap": maximum_overlap,
        "threshold_counts": threshold_counts,
        "book_maximum": summaries,
        "structure": {
            "control": control_structure,
            "treatment": treatment_structure,
        },
    }


def aggregate_heldout_gate(folds: Sequence[Mapping]) -> dict[str, object]:
    """Apply the frozen five-fold p230-first score-free gate."""
    rows = list(folds)
    if len(rows) != 5 or {str(row.get("heldout_block")) for row in rows} != {
        "R0", "R1", "R2", "R3", "R4",
    } or any(row.get("mechanical_valid") is not True for row in rows):
        raise ValueError("constraint-lattice held-out fold grid differs")
    for row in rows:
        if row.get("version") != VERSION or \
                row.get("uses_realized_outcomes") is not False:
            raise ValueError("constraint-lattice held-out fold identity differs")

    aggregate_counts = {
        book: {
            f"{threshold:g}": sum(
                int(row["threshold_counts"][book][f"{threshold:g}"])
                for row in rows
            )
            for threshold in REPORT_THRESHOLDS
        }
        for book in ("control", "treatment")
    }
    fold_deltas = {
        str(row["heldout_block"]): {
            f"{threshold:g}": int(
                row["threshold_counts"]["treatment"][f"{threshold:g}"]
                - row["threshold_counts"]["control"][f"{threshold:g}"]
            )
            for threshold in REPORT_THRESHOLDS
        }
        for row in rows
    }
    selected_230_net = (
        aggregate_counts["treatment"]["230"]
        - aggregate_counts["control"]["230"]
    )
    selected_210_net = (
        aggregate_counts["treatment"]["210"]
        - aggregate_counts["control"]["210"]
    )
    control_194 = aggregate_counts["control"]["194"]
    retention_194 = (
        float(aggregate_counts["treatment"]["194"] / control_194)
        if control_194 else 1.0
    )
    improves_230 = sum(
        values["230"] > 0 for values in fold_deltas.values()
    )
    structure_retention = {}
    for row in rows:
        block = str(row["heldout_block"])
        structure_retention[block] = {}
        for metric in ("unique_player_pairs", "unique_qb_stack_cores"):
            control_value = int(row["structure"]["control"][metric])
            treatment_value = int(row["structure"]["treatment"][metric])
            structure_retention[block][metric] = (
                float(treatment_value / control_value) if control_value else 1.0
            )
    conditions = {
        "aggregate_p230_improves": selected_230_net > 0,
        "at_least_three_heldout_blocks_improve_p230": improves_230 >= 3,
        "aggregate_p210_nondecline": selected_210_net >= 0,
        "aggregate_p194_retains_95pct": retention_194 >= 0.95,
        "every_fold_pair_and_core_retain_90pct": all(
            value >= 0.90
            for metrics in structure_retention.values()
            for value in metrics.values()
        ),
    }
    passes = all(conditions.values())
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "folds": 5,
        "aggregate_threshold_counts": aggregate_counts,
        "fold_threshold_deltas": fold_deltas,
        "selected_230_net_worlds": selected_230_net,
        "selected_210_net_worlds": selected_210_net,
        "selected_194_retention": retention_194,
        "heldout_blocks_improving_p230": improves_230,
        "structure_retention": structure_retention,
        "conditions": conditions,
        "passes_scorefree_gate": passes,
        "disposition": (
            "constraint-lattice-shadow-licensed"
            if passes else "constraint-lattice-scorefree-fails"
        ),
        "production_change_licensed": False,
    }


def protocol_receipt() -> Mapping[str, object]:
    """Expose fixed non-outcome mechanism identity for runners/finishers."""
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "cell_order": list(CELL_ORDER),
        "cell_quotas": dict(CELL_QUOTAS),
        "maximum_exception_entries": int(sum(CELL_QUOTAS.values())),
        "control_entries": 80,
        "heldout_folds": 5,
    }


__all__ = [
    "CELL_ORDER",
    "CELL_QUOTAS",
    "ExceptionCandidate",
    "REPORT_THRESHOLDS",
    "TRAINING_THRESHOLDS",
    "VERSION",
    "aggregate_heldout_gate",
    "construct_exception_sleeve",
    "evaluate_heldout_fold",
    "exception_cell",
    "is_strict_lineup",
    "lineup_constraint_profile",
    "protocol_receipt",
    "rank_exception_candidates",
    "stack_rules_for_cell",
    "validate_exception_book",
]
