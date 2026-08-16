"""Outcome-free stack-core x shell construction primitives.

The treatment recombines partial solutions already present in a fixed
four-block CBWU-OI control.  It never accepts realized scores, standings,
ownership or payout data.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from time import perf_counter

import numpy as np

from ..backtest.engine import CandidateBatch
from ..inference.multiseed_portfolio import _select_tail_entries_bitpacked
from ..optimizer.lineup import Lineup, select_tail_entries
from .atlas_matched_diversity import _score_effective_rank
from .constraint_lattice import (
    REGISTERED_BLOCKS,
    REPORT_THRESHOLDS,
    _roster_rows,
    _structure_reach,
    build_training_control,
    is_strict_lineup,
    validate_common_legality,
)


VERSION = "stack-core-shell-scorefree-v1"
CORE_LIMIT = 32
SHELL_LIMIT = 128
BEAM_LIMIT = 256
PROPOSAL_LIMIT = 40
MAX_CORES_PER_QB = 4
MAX_CORES_PER_GAME = 8
TRAINING_LINES = (230.0, 210.0, 194.0)

Roster = tuple[str, ...]
Interaction = tuple[str, str]


@dataclass(frozen=True)
class Component:
    players: tuple[str, ...]
    rank: tuple[float, ...]
    parent: Roster
    qb: str = ""
    game: str = ""


@dataclass
class Recombinant:
    lineup: Lineup
    core: tuple[str, ...]
    shell: tuple[str, ...]
    totals_by_block: Mapping[str, np.ndarray]
    rank: tuple[float, ...]


def _roster(lineup: Lineup) -> Roster:
    value = tuple(sorted(str(player_id) for player_id in lineup.ids))
    if len(value) != 9 or len(set(value)) != 9:
        raise ValueError("stack-core/shell roster must contain nine players")
    return value


def _normalized_vectors(
    totals_by_block: Mapping[str, np.ndarray], blocks: Sequence[str],
) -> dict[str, np.ndarray]:
    names = tuple(str(value) for value in blocks)
    if len(names) != 4 or len(set(names)) != 4 or \
            set(totals_by_block) != set(names):
        raise ValueError("stack-core/shell requires four training blocks")
    normalized = {}
    widths = set()
    for name in names:
        values = np.asarray(totals_by_block[name], dtype=np.float64)
        if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
            raise ValueError("stack-core/shell totals must be finite vectors")
        normalized[name] = values
        widths.add(len(values))
    if len(widths) != 1:
        raise ValueError("stack-core/shell training blocks differ in width")
    return normalized


def _tail_rank(
    totals_by_block: Mapping[str, np.ndarray], blocks: Sequence[str],
) -> tuple[float, ...]:
    """Return the frozen worst-block/aggregate tail ordering."""
    names = tuple(str(value) for value in blocks)
    values = _normalized_vectors(totals_by_block, names)
    rank: list[float] = []
    for line in TRAINING_LINES:
        counts = [float(np.count_nonzero(values[name] >= line)) for name in names]
        rank.extend((min(counts), sum(counts)))
    rank.append(float(np.mean(np.concatenate([values[name] for name in names]))))
    return tuple(rank)


def _descending_key(
    rank: Sequence[float], *identity: Sequence[str] | str,
) -> tuple[object, ...]:
    flattened: list[str] = []
    for value in identity:
        if isinstance(value, str):
            flattened.append(value)
        else:
            flattened.extend(str(item) for item in value)
    return (*(-float(value) for value in rank), *flattened)


def enumerate_core_shells(lineup: Lineup) -> list[dict[str, object]]:
    """Enumerate every frozen QB+two-catcher+bring-back decomposition."""
    if not validate_common_legality(lineup) or not is_strict_lineup(lineup):
        raise ValueError("stack-core/shell source lineup is not incumbent-strict")
    rows = list(lineup.players)
    quarterbacks = [
        row for row in rows if str(row.get("pos", "")).upper() == "QB"
    ]
    if len(quarterbacks) != 1:
        raise ValueError("stack-core/shell source lineup requires one QB")
    qb = quarterbacks[0]
    qb_id = str(qb["id"])
    qb_team = str(qb.get("team", ""))
    qb_opp = str(qb.get("opp", ""))
    qb_game = str(qb.get("game_id", ""))
    if not qb_team or not qb_opp or not qb_game:
        raise ValueError("stack-core/shell QB metadata is incomplete")
    catchers = sorted(str(row["id"]) for row in rows if (
        str(row.get("team", "")) == qb_team
        and str(row.get("pos", "")).upper() in {"WR", "TE"}
    ))
    bring_backs = sorted(str(row["id"]) for row in rows if (
        str(row.get("team", "")) == qb_opp
        and str(row.get("pos", "")).upper() in {"RB", "WR", "TE"}
    ))
    roster = set(_roster(lineup))
    result = []
    for first, second in combinations(catchers, 2):
        for bring_back in bring_backs:
            core = tuple(sorted((qb_id, first, second, bring_back)))
            shell = tuple(sorted(roster - set(core)))
            if len(core) != 4 or len(set(core)) != 4 or len(shell) != 5:
                raise ValueError("stack-core/shell decomposition differs")
            result.append({
                "core": core,
                "shell": shell,
                "qb": qb_id,
                "game": qb_game,
            })
    if not result:
        raise ValueError("stack-core/shell source produced no decomposition")
    return result


def build_component_library(
    control_lineups: Sequence[Lineup],
    control_totals_by_block: Mapping[str, np.ndarray],
    blocks: Sequence[str],
) -> dict[str, object]:
    """Build the exact 32-core and 128-shell library from control."""
    lineups = list(control_lineups)
    names = tuple(str(value) for value in blocks)
    if len(lineups) < 80 or len({_roster(row) for row in lineups}) != len(lineups):
        raise ValueError("stack-core/shell control candidates differ")
    matrices = {
        name: np.asarray(control_totals_by_block[name], dtype=np.float64)
        for name in names
    }
    if any(matrix.ndim != 2 or matrix.shape[0] != len(lineups)
           for matrix in matrices.values()):
        raise ValueError("stack-core/shell control totals are misaligned")

    cores: dict[tuple[str, ...], Component] = {}
    shells: dict[tuple[str, ...], Component] = {}
    decompositions = 0
    for index, lineup in enumerate(lineups):
        parent = _roster(lineup)
        totals = {name: matrices[name][index] for name in names}
        rank = _tail_rank(totals, names)
        for row in enumerate_core_shells(lineup):
            decompositions += 1
            core = tuple(row["core"])
            shell = tuple(row["shell"])
            core_row = Component(
                core, rank, parent, str(row["qb"]), str(row["game"]),
            )
            shell_row = Component(shell, rank, parent)
            current = cores.get(core)
            if current is None or rank > current.rank or (
                rank == current.rank and parent < current.parent
            ):
                cores[core] = core_row
            current = shells.get(shell)
            if current is None or rank > current.rank or (
                rank == current.rank and parent < current.parent
            ):
                shells[shell] = shell_row

    ordered_cores = sorted(
        cores.values(),
        key=lambda row: _descending_key(row.rank, row.players),
    )
    retained_cores = []
    qb_counts: Counter[str] = Counter()
    game_counts: Counter[str] = Counter()
    for row in ordered_cores:
        if qb_counts[row.qb] >= MAX_CORES_PER_QB or \
                game_counts[row.game] >= MAX_CORES_PER_GAME:
            continue
        retained_cores.append(row)
        qb_counts[row.qb] += 1
        game_counts[row.game] += 1
        if len(retained_cores) == CORE_LIMIT:
            break
    retained_shells = sorted(
        shells.values(),
        key=lambda row: _descending_key(row.rank, row.players),
    )[:SHELL_LIMIT]
    if len(retained_cores) != CORE_LIMIT or len(retained_shells) != SHELL_LIMIT:
        raise ValueError("stack-core/shell component library cannot fill")
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "source_lineups": len(lineups),
        "decompositions": decompositions,
        "discovered_cores": len(cores),
        "discovered_shells": len(shells),
        "cores": retained_cores,
        "shells": retained_shells,
        "core_qb_counts": dict(sorted(qb_counts.items())),
        "core_game_counts": dict(sorted(game_counts.items())),
    }


def _cross_pairs(core: Sequence[str], shell: Sequence[str]) -> set[Interaction]:
    return {
        tuple(sorted((str(left), str(right))))
        for left in core for right in shell
    }


def construct_recombinant_proposals(
    *,
    player_rows: Sequence[Mapping],
    player_ids: Sequence[object],
    row_draws_by_block: Mapping[str, np.ndarray],
    blocks: Sequence[str],
    control_lineups: Sequence[Lineup],
    library: Mapping[str, object],
) -> dict[str, object]:
    """Cross components, retain the 256 beam, then choose exactly 40."""
    names = tuple(str(value) for value in blocks)
    ids = tuple(str(value) for value in player_ids)
    player_by_id = {
        str(player_id): {**dict(row), "id": str(player_id)}
        for player_id, row in zip(ids, player_rows, strict=True)
    }
    if len(player_by_id) != len(ids):
        raise ValueError("stack-core/shell player IDs repeat")
    index = {value: row for row, value in enumerate(ids)}
    draws = {
        name: np.asarray(row_draws_by_block[name], dtype=np.float32)
        for name in names
    }
    if any(value.ndim != 2 or value.shape[0] != len(ids)
           or not np.isfinite(value).all() for value in draws.values()):
        raise ValueError("stack-core/shell player worlds are invalid")
    cores = list(library.get("cores", []))
    shells = list(library.get("shells", []))
    if len(cores) != CORE_LIMIT or len(shells) != SHELL_LIMIT or \
            any(not isinstance(row, Component) for row in [*cores, *shells]):
        raise ValueError("stack-core/shell library identity differs")

    control = {_roster(lineup) for lineup in control_lineups}
    by_roster: dict[Roster, Recombinant] = {}
    legal_crosses = 0
    duplicate_crosses = 0
    existing_crosses = 0
    for core in cores:
        for shell in shells:
            if set(core.players) & set(shell.players):
                continue
            roster = tuple(sorted((*core.players, *shell.players)))
            if len(roster) != 9 or len(set(roster)) != 9:
                continue
            lineup = Lineup(
                [player_by_id[value] for value in roster],
                tag="stack_core_shell",
            )
            if not validate_common_legality(lineup) or not is_strict_lineup(lineup):
                continue
            legal_crosses += 1
            if roster in control:
                existing_crosses += 1
                continue
            rows = np.asarray([index[value] for value in roster], dtype=np.int64)
            totals = {
                name: draws[name][rows].sum(axis=0).astype(np.float32)
                for name in names
            }
            candidate = Recombinant(
                lineup=lineup,
                core=core.players,
                shell=shell.players,
                totals_by_block=totals,
                rank=_tail_rank(totals, names),
            )
            current = by_roster.get(roster)
            if current is None:
                by_roster[roster] = candidate
                continue
            duplicate_crosses += 1
            current_component_rank = (
                next(row.rank for row in cores if row.players == current.core),
                next(row.rank for row in shells if row.players == current.shell),
            )
            candidate_component_rank = (core.rank, shell.rank)
            if candidate_component_rank > current_component_rank or (
                candidate_component_rank == current_component_rank
                and (candidate.core, candidate.shell) <
                (current.core, current.shell)
            ):
                by_roster[roster] = candidate

    ordered = sorted(
        by_roster.values(),
        key=lambda row: _descending_key(
            row.rank, _roster(row.lineup), row.core, row.shell,
        ),
    )
    beam = ordered[:BEAM_LIMIT]
    if len(beam) != BEAM_LIMIT:
        raise ValueError("stack-core/shell recombinant beam cannot fill")
    selected: list[Recombinant] = []
    covered: set[Interaction] = set()
    remaining = list(beam)
    while len(selected) < PROPOSAL_LIMIT:
        ranked = sorted(
            remaining,
            key=lambda row: (
                -len(_cross_pairs(row.core, row.shell) - covered),
                *_descending_key(
                    row.rank, _roster(row.lineup), row.core, row.shell,
                ),
            ),
        )
        if not ranked:
            raise ValueError("stack-core/shell proposal book cannot fill")
        chosen = ranked[0]
        newly_covered = _cross_pairs(chosen.core, chosen.shell) - covered
        if selected and not newly_covered:
            raise ValueError("stack-core/shell proposal adds no cross pair")
        selected.append(chosen)
        covered.update(newly_covered)
        remaining = [row for row in remaining if row is not chosen]
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "legal_crosses": legal_crosses,
        "existing_control_crosses": existing_crosses,
        "duplicate_crosses": duplicate_crosses,
        "unique_recombinants": len(by_roster),
        "beam": beam,
        "proposals": selected,
        "covered_core_shell_pairs": len(covered),
    }


def admit_and_select_treatment(
    *,
    control_lineups: Sequence[Lineup],
    control_totals_by_block: Mapping[str, np.ndarray],
    proposals: Sequence[Recombinant],
    blocks: Sequence[str],
) -> dict[str, object]:
    """Re-admit to the original candidate budget and run unchanged exact-80."""
    names = tuple(str(value) for value in blocks)
    control = list(control_lineups)
    additions = list(proposals)
    budget = len(control)
    if budget < 80 or len({_roster(row) for row in control}) != budget or \
            len(additions) != PROPOSAL_LIMIT:
        raise ValueError("stack-core/shell treatment population differs")
    control_totals = {
        name: np.asarray(control_totals_by_block[name], dtype=np.float32)
        for name in names
    }
    if any(values.ndim != 2 or values.shape[0] != budget
           for values in control_totals.values()):
        raise ValueError("stack-core/shell control totals differ")
    combined = [(lineup, {
        name: control_totals[name][index] for name in names
    }) for index, lineup in enumerate(control)]
    combined.extend((row.lineup, row.totals_by_block) for row in additions)
    combined.sort(key=lambda row: _roster(row[0]))
    if len({_roster(row[0]) for row in combined}) != budget + PROPOSAL_LIMIT:
        raise ValueError("stack-core/shell proposal union repeats")
    matrix = {
        name: np.stack([
            np.asarray(row[1][name], dtype=np.float32) for row in combined
        ])
        for name in names
    }
    aggregate = np.concatenate([matrix[name] for name in names], axis=1)
    admitted = _select_tail_entries_bitpacked(aggregate, budget, 194.0)
    if len(admitted) != budget or len(set(admitted)) != budget:
        raise ValueError("stack-core/shell admission is not exact budget")
    lineups = [combined[index][0] for index in admitted]
    totals = {name: matrix[name][admitted] for name in names}
    selected = select_tail_entries(
        np.concatenate([totals[name] for name in names], axis=1),
        80,
        194.0,
        env={"SELECT_LSE": "0"},
    )
    if len(selected) != 80 or len(set(selected)) != 80:
        raise ValueError("stack-core/shell selector is not exact 80")
    control_keys = {_roster(row) for row in control}
    admitted_proposals = [
        _roster(row) for row in lineups if _roster(row) not in control_keys
    ]
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "candidate_budget": budget,
        "candidate_lineups": lineups,
        "candidate_totals_by_block": totals,
        "selected_indices": selected,
        "selected_lineups": [lineups[index] for index in selected],
        "selected_totals_by_block": {
            name: totals[name][selected] for name in names
        },
        "admitted_proposal_rosters": admitted_proposals,
        "admitted_proposals": len(admitted_proposals),
    }


def _tail_counts(matrix: np.ndarray) -> dict[str, int]:
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] == 0 or \
            not np.isfinite(values).all():
        raise ValueError("stack-core/shell held-out matrix is invalid")
    maxima = np.max(values, axis=0)
    return {
        f"{line:g}": int(np.count_nonzero(maxima >= line))
        for line in REPORT_THRESHOLDS
    }


def evaluate_fold(
    *,
    heldout_block: str,
    season: int,
    week: int,
    player_ids: Sequence[object],
    heldout_row_draws: np.ndarray,
    control_candidate_lineups: Sequence[Lineup],
    control_selected_lineups: Sequence[Lineup],
    treatment: Mapping[str, object],
    proposal_receipt: Mapping[str, object],
) -> dict[str, object]:
    """Evaluate fixed candidate and exact-80 books on one untouched block."""
    candidate_control = list(control_candidate_lineups)
    selected_control = list(control_selected_lineups)
    candidate_treatment = list(treatment["candidate_lineups"])
    selected_treatment = list(treatment["selected_lineups"])
    if len(selected_control) != 80 or len(selected_treatment) != 80:
        raise ValueError("stack-core/shell held-out books are not exact 80")
    draws = np.asarray(heldout_row_draws, dtype=np.float32)

    def score(lineups: Sequence[Lineup]) -> np.ndarray:
        return draws[_roster_rows(lineups, player_ids)].sum(axis=1)

    matrices = {
        "candidate": {
            "control": score(candidate_control),
            "treatment": score(candidate_treatment),
        },
        "selected": {
            "control": score(selected_control),
            "treatment": score(selected_treatment),
        },
    }
    structure = {
        layer: {
            book: _structure_reach(lineups)
            for book, lineups in (
                ("control", candidate_control if layer == "candidate" else selected_control),
                ("treatment", candidate_treatment if layer == "candidate" else selected_treatment),
            )
        }
        for layer in ("candidate", "selected")
    }
    effective_rank = {
        layer: {
            book: _score_effective_rank(matrix)
            for book, matrix in books.items()
        }
        for layer, books in matrices.items()
    }
    control_keys = {_roster(row) for row in candidate_control}
    treatment_keys = {_roster(row) for row in candidate_treatment}
    selected_control_keys = {_roster(row) for row in selected_control}
    selected_treatment_keys = {_roster(row) for row in selected_treatment}
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "mechanical_valid": True,
        "season": int(season),
        "week": int(week),
        "heldout_block": str(heldout_block),
        "worlds": int(draws.shape[1]),
        "candidate_budget": len(candidate_control),
        "selected_entries": 80,
        "candidate_shared_rosters": len(control_keys & treatment_keys),
        "candidate_new_rosters": len(treatment_keys - control_keys),
        "selected_shared_rosters": len(
            selected_control_keys & selected_treatment_keys
        ),
        "selected_new_rosters": len(
            selected_treatment_keys - selected_control_keys
        ),
        "admitted_proposals": int(treatment["admitted_proposals"]),
        "proposal_counts": {
            key: int(proposal_receipt[key]) for key in (
                "legal_crosses", "existing_control_crosses",
                "duplicate_crosses", "unique_recombinants",
                "covered_core_shell_pairs",
            )
        },
        "threshold_counts": {
            layer: {book: _tail_counts(matrix) for book, matrix in books.items()}
            for layer, books in matrices.items()
        },
        "structure": structure,
        "score_effective_rank": effective_rank,
        "candidate_control_rosters": [list(_roster(row)) for row in candidate_control],
        "candidate_treatment_rosters": [list(_roster(row)) for row in candidate_treatment],
        "selected_control_rosters": [list(_roster(row)) for row in selected_control],
        "selected_treatment_rosters": [list(_roster(row)) for row in selected_treatment],
    }


def run_scorefree_slate(
    books: Mapping[str, CandidateBatch],
    *,
    season: int,
    week: int,
    expected_worlds_per_block: int = 10_000,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Run the frozen train-four/test-one treatment for one slate."""
    folds = []
    started = perf_counter()
    for heldout in REGISTERED_BLOCKS:
        fold_started = perf_counter()
        control = build_training_control(
            books,
            heldout,
            expected_worlds_per_block=expected_worlds_per_block,
        )
        library = build_component_library(
            control["candidate_lineups"],
            control["candidate_totals_by_block"],
            control["training_blocks"],
        )
        proposals = construct_recombinant_proposals(
            player_rows=control["player_rows"],
            player_ids=control["player_ids"],
            row_draws_by_block=control["row_draws_by_block"],
            blocks=control["training_blocks"],
            control_lineups=control["candidate_lineups"],
            library=library,
        )
        treatment = admit_and_select_treatment(
            control_lineups=control["candidate_lineups"],
            control_totals_by_block=control["candidate_totals_by_block"],
            proposals=proposals["proposals"],
            blocks=control["training_blocks"],
        )
        row = evaluate_fold(
            heldout_block=heldout,
            season=season,
            week=week,
            player_ids=control["player_ids"],
            heldout_row_draws=control["heldout_row_draws"],
            control_candidate_lineups=control["candidate_lineups"],
            control_selected_lineups=control["control_lineups"],
            treatment=treatment,
            proposal_receipt=proposals,
        )
        row.update({
            "training_blocks": list(control["training_blocks"]),
            "training_union_candidates": int(control["training_union_candidates"]),
            "component_library": {
                "source_lineups": int(library["source_lineups"]),
                "decompositions": int(library["decompositions"]),
                "discovered_cores": int(library["discovered_cores"]),
                "discovered_shells": int(library["discovered_shells"]),
                "retained_cores": len(library["cores"]),
                "retained_shells": len(library["shells"]),
                "core_qb_counts": library["core_qb_counts"],
                "core_game_counts": library["core_game_counts"],
                "cores": [{
                    "players": list(component.players),
                    "rank": list(component.rank),
                    "parent": list(component.parent),
                    "qb": component.qb,
                    "game": component.game,
                } for component in library["cores"]],
                "shells": [{
                    "players": list(component.players),
                    "rank": list(component.rank),
                    "parent": list(component.parent),
                } for component in library["shells"]],
            },
            "beam_candidates": len(proposals["beam"]),
            "proposal_candidates": len(proposals["proposals"]),
            "proposals": [{
                "roster": list(_roster(candidate.lineup)),
                "core": list(candidate.core),
                "shell": list(candidate.shell),
                "rank": list(candidate.rank),
            } for candidate in proposals["proposals"]],
            "elapsed_seconds": float(perf_counter() - fold_started),
        })
        folds.append(row)
        if progress_callback is not None:
            progress_callback(heldout)
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "season": int(season),
        "week": int(week),
        "folds": folds,
        "elapsed_seconds": float(perf_counter() - started),
    }


def aggregate_gate(
    folds: Sequence[Mapping], *, selected_anchor: int,
) -> dict[str, object]:
    """Apply the frozen support-anchored score-free disposition."""
    rows = list(folds)
    anchor = int(selected_anchor)
    if anchor not in {230, 220, 210}:
        raise ValueError("stack-core/shell support anchor differs")
    if len(rows) != 270 or any(
        row.get("version") != VERSION
        or row.get("uses_realized_outcomes") is not False
        or row.get("mechanical_valid") is not True
        for row in rows
    ):
        raise ValueError("stack-core/shell fold population differs")
    expected = {
        (season, week, block)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
        for block in REGISTERED_BLOCKS
    }
    observed = {
        (int(row["season"]), int(row["week"]), str(row["heldout_block"]))
        for row in rows
    }
    if observed != expected or len(observed) != len(rows):
        raise ValueError("stack-core/shell fold grid differs")

    def count(layer: str, book: str, line: int, subset: Sequence[Mapping]) -> int:
        return sum(int(row["threshold_counts"][layer][book][str(line)]) for row in subset)

    aggregate = {
        layer: {
            book: {
                str(int(line)): count(layer, book, int(line), rows)
                for line in REPORT_THRESHOLDS
            }
            for book in ("control", "treatment")
        }
        for layer in ("candidate", "selected")
    }
    by_block = {}
    for block in REGISTERED_BLOCKS:
        subset = [row for row in rows if row["heldout_block"] == block]
        by_block[block] = {
            layer: {
                str(int(line)): count(layer, "treatment", int(line), subset)
                - count(layer, "control", int(line), subset)
                for line in REPORT_THRESHOLDS
            }
            for layer in ("candidate", "selected")
        }

    selected_anchor_delta = (
        aggregate["selected"]["treatment"][str(anchor)]
        - aggregate["selected"]["control"][str(anchor)]
    )
    candidate_anchor_delta = (
        aggregate["candidate"]["treatment"][str(anchor)]
        - aggregate["candidate"]["control"][str(anchor)]
    )
    selected_210_delta = (
        aggregate["selected"]["treatment"]["210"]
        - aggregate["selected"]["control"]["210"]
    )
    control_194 = aggregate["selected"]["control"]["194"]
    retention_194 = (
        aggregate["selected"]["treatment"]["194"] / control_194
        if control_194 else 1.0
    )
    structure = {}
    for block in REGISTERED_BLOCKS:
        subset = [row for row in rows if row["heldout_block"] == block]
        metrics = {}
        for layer, metric in (
            ("candidate", "unique_player_pairs"),
            ("selected", "unique_qb_stack_cores"),
            ("selected", "unique_dominant_games"),
        ):
            left = sum(int(row["structure"][layer]["control"][metric]) for row in subset)
            right = sum(int(row["structure"][layer]["treatment"][metric]) for row in subset)
            metrics[f"{layer}_{metric}_retention"] = right / left if left else 1.0
        structure[block] = metrics
    conditions = {
        "selected_anchor_improves": selected_anchor_delta > 0,
        "at_least_three_blocks_improve_anchor": sum(
            by_block[block]["selected"][str(anchor)] > 0
            for block in REGISTERED_BLOCKS
        ) >= 3,
        "candidate_anchor_improves": candidate_anchor_delta > 0,
        "selected_p210_required_direction": (
            selected_210_delta > 0 if anchor == 210 else selected_210_delta >= 0
        ),
        "selected_p194_retains_95pct": retention_194 >= 0.95,
        "every_block_structure_retains_90pct": all(
            value >= 0.90
            for metrics in structure.values() for value in metrics.values()
        ),
    }
    passes = all(conditions.values())

    def decision(subset: Sequence[Mapping]) -> bool:
        left_anchor = count("selected", "control", anchor, subset)
        right_anchor = count("selected", "treatment", anchor, subset)
        left_candidate = count("candidate", "control", anchor, subset)
        right_candidate = count("candidate", "treatment", anchor, subset)
        left_210 = count("selected", "control", 210, subset)
        right_210 = count("selected", "treatment", 210, subset)
        left_194 = count("selected", "control", 194, subset)
        right_194 = count("selected", "treatment", 194, subset)
        block_gain = sum(
            count("selected", "treatment", anchor, [row for row in subset if row["heldout_block"] == block])
            > count("selected", "control", anchor, [row for row in subset if row["heldout_block"] == block])
            for block in REGISTERED_BLOCKS
        )
        return bool(
            right_anchor > left_anchor and right_candidate > left_candidate
            and block_gain >= 3
            and (right_210 > left_210 if anchor == 210 else right_210 >= left_210)
            and (right_194 / left_194 if left_194 else 1.0) >= 0.95
        )

    slate_keys = sorted({(int(row["season"]), int(row["week"])) for row in rows})
    influence = [{
        "season": season,
        "week": week,
        "passes_nonstructure_conditions_without_slate": decision([
            row for row in rows
            if (int(row["season"]), int(row["week"])) != (season, week)
        ]),
    } for season, week in slate_keys]
    contributions = {
        block: [{
            "season": int(row["season"]),
            "week": int(row["week"]),
            "candidate_delta": int(
                row["threshold_counts"]["candidate"]["treatment"][str(anchor)]
                - row["threshold_counts"]["candidate"]["control"][str(anchor)]
            ),
            "selected_delta": int(
                row["threshold_counts"]["selected"]["treatment"][str(anchor)]
                - row["threshold_counts"]["selected"]["control"][str(anchor)]
            ),
        } for row in sorted(
            (row for row in rows if row["heldout_block"] == block),
            key=lambda row: (int(row["season"]), int(row["week"])),
        )]
        for block in REGISTERED_BLOCKS
    }
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "folds": len(rows),
        "slates": len(slate_keys),
        "selected_anchor": anchor,
        "aggregate_threshold_counts": aggregate,
        "fold_threshold_deltas": by_block,
        "selected_anchor_net_worlds": selected_anchor_delta,
        "candidate_anchor_net_worlds": candidate_anchor_delta,
        "selected_p210_net_worlds": selected_210_delta,
        "selected_p194_retention": float(retention_194),
        "structure_retention_by_block": structure,
        "anchor_slate_contributions": contributions,
        "leave_one_slate_out": influence,
        "conditions": conditions,
        "passes_scorefree_gate": passes,
        "disposition": (
            "stack-core-shell-shadow-licensed"
            if passes else "stack-core-shell-scorefree-fails"
        ),
        "production_change_licensed": False,
    }
