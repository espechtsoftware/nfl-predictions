"""Outcome-free coherent model/market-state construction experiment.

The generator preserves model/market disagreement as complete team states,
then evaluates every candidate under the unchanged incumbent simulation
worlds.  Realized scores, ownership, ranks and payouts are outside this
module's interface.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from ..backtest.engine import CandidateBatch
from ..optimizer.lineup import Lineup, StackRules, optimize, select_tail_entries
from .atlas_matched_diversity import _score_effective_rank
from .constraint_lattice import (
    REGISTERED_BLOCKS,
    REPORT_THRESHOLDS,
    _roster_key,
    _roster_rows,
    _structure_reach,
    build_training_control,
    is_strict_lineup,
    validate_common_legality,
)
from .stack_core_shell import _tail_rank


VERSION = "coherent-market-state-scorefree-v1"
TEAM_LIMIT = 3
STATE_ORDER = ("model", "market")
LINEUPS_PER_STATE = 2
ADDITION_COUNT = TEAM_LIMIT * len(STATE_ORDER) * LINEUPS_PER_STATE
ANCHOR_LIMIT = 64
REPORT_SCOPES = ("candidate", "selected")


@dataclass(frozen=True)
class TeamState:
    team: str
    disagreement: float
    qb_id: str
    covered_player_ids: tuple[str, ...]
    player_disagreements: tuple[tuple[str, float], ...]


@dataclass
class StateCandidate:
    lineup: Lineup
    team: str
    state: str
    state_index: int
    anchor_block: str
    anchor_world: int
    totals_by_block: Mapping[str, np.ndarray]


def _finite_number(value: object) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _covered(row: Mapping) -> bool:
    return all(_finite_number(row.get(name)) for name in (
        "market_points", "model_points_pre", "mean_projection",
    ))


def rank_eligible_teams(
    player_rows: Sequence[Mapping],
    native_r0_candidates: Sequence[Lineup],
) -> list[TeamState]:
    """Return the frozen top-three covered team disagreement states."""
    rows = [dict(row) for row in player_rows]
    by_id = {str(row.get("id")): row for row in rows}
    if len(by_id) != len(rows) or "None" in by_id:
        raise ValueError("coherent-state player IDs repeat or are missing")
    candidate_universe = {
        str(player_id)
        for lineup in native_r0_candidates
        for player_id in lineup.ids
    }
    if not candidate_universe or not candidate_universe <= set(by_id):
        raise ValueError("coherent-state R0 candidate universe differs")

    by_team: dict[str, list[dict]] = {}
    for player_id in sorted(candidate_universe):
        row = by_id[player_id]
        if not _covered(row) or str(row.get("pos", "")).upper() not in {
            "QB", "RB", "WR", "TE",
        }:
            continue
        team = str(row.get("team", "")).strip()
        if not team:
            raise ValueError("coherent-state covered player has no team")
        by_team.setdefault(team, []).append(row)

    states = []
    for team, team_rows in sorted(by_team.items()):
        qbs = [row for row in team_rows if str(row["pos"]).upper() == "QB"]
        catchers = [
            row for row in team_rows
            if str(row["pos"]).upper() in {"WR", "TE"}
        ]
        if not qbs or len(catchers) < 2:
            continue
        disagreements = sorted((
            (
                str(row["id"]),
                abs(float(row["model_points_pre"]) - float(row["market_points"])),
            )
            for row in team_rows
        ), key=lambda item: (-item[1], item[0]))
        qb = min(
            qbs,
            key=lambda row: (-float(row["mean_projection"]), str(row["id"])),
        )
        states.append(TeamState(
            team=team,
            disagreement=float(sum(value for _, value in disagreements[:3])),
            qb_id=str(qb["id"]),
            covered_player_ids=tuple(sorted(str(row["id"]) for row in team_rows)),
            player_disagreements=tuple(disagreements),
        ))
    states.sort(key=lambda row: (-row.disagreement, row.team))
    if len(states) < TEAM_LIMIT:
        raise ValueError("coherent-state slate has fewer than three eligible teams")
    return states[:TEAM_LIMIT]


def _anchor_worlds(
    team: TeamState,
    player_ids: Sequence[object],
    row_draws_by_block: Mapping[str, np.ndarray],
    training_blocks: Sequence[str],
) -> list[tuple[str, int, float]]:
    names = tuple(str(value) for value in training_blocks)
    if len(names) != 4 or len(set(names)) != 4 or not set(names) < set(
        REGISTERED_BLOCKS
    ):
        raise ValueError("coherent-state anchors require four training blocks")
    index = {str(value): row for row, value in enumerate(player_ids)}
    if len(index) != len(player_ids) or not set(team.covered_player_ids) <= set(index):
        raise ValueError("coherent-state anchor player universe differs")
    team_rows = [index[value] for value in team.covered_player_ids]
    anchors = []
    widths = set()
    for block_order, block in enumerate(names):
        draws = np.asarray(row_draws_by_block[block], dtype=np.float64)
        if draws.ndim != 2 or draws.shape[0] != len(player_ids) or \
                not np.isfinite(draws).all():
            raise ValueError("coherent-state anchor draws differ")
        widths.add(draws.shape[1])
        scores = draws[team_rows].sum(axis=0)
        anchors.extend(
            (block, world, float(score), block_order)
            for world, score in enumerate(scores)
        )
    if len(widths) != 1 or next(iter(widths)) == 0:
        raise ValueError("coherent-state training world widths differ")
    anchors.sort(key=lambda row: (-row[2], row[3], row[1]))
    return [(block, world, score) for block, world, score, _ in anchors[:ANCHOR_LIMIT]]


def generate_state_candidates(
    *,
    player_rows: Sequence[Mapping],
    player_ids: Sequence[object],
    row_draws_by_block: Mapping[str, np.ndarray],
    training_blocks: Sequence[str],
    team_states: Sequence[TeamState],
    forbidden_rosters: set[tuple[str, ...]],
    optimizer: Callable[..., Lineup | None] = optimize,
) -> tuple[list[StateCandidate], list[dict[str, object]]]:
    """Generate exactly 12 novel strict candidates from frozen team states."""
    teams = list(team_states)
    if len(teams) != TEAM_LIMIT or len({row.team for row in teams}) != TEAM_LIMIT:
        raise ValueError("coherent-state generator requires three ordered teams")
    original = [dict(row) for row in player_rows]
    row_by_id = {str(row.get("id")): row for row in original}
    id_index = {str(value): index for index, value in enumerate(player_ids)}
    if len(row_by_id) != len(original) or set(row_by_id) != set(id_index):
        raise ValueError("coherent-state player rows and draw IDs differ")
    ordered_ids = sorted(row_by_id)
    base_players = [dict(row_by_id[player_id]) for player_id in ordered_ids]
    banned = {
        frozenset(str(value) for value in roster)
        for roster in forbidden_rosters
    }
    receipts = []
    additions = []
    stack = StackRules(qb_stack_min=2, bring_back_min=1)
    env = {"MIN_LINEUP_SALARY": "49000"}
    names = tuple(str(value) for value in training_blocks)

    for team_rank, team in enumerate(teams, start=1):
        anchors = _anchor_worlds(team, player_ids, row_draws_by_block, names)
        covered = set(team.covered_player_ids)
        for state in STATE_ORDER:
            accepted = 0
            for anchor_rank, (block, world, story_score) in enumerate(
                anchors, start=1,
            ):
                draws = np.asarray(row_draws_by_block[block], dtype=np.float64)
                objective = draws[:, world].copy()
                shifts = {}
                target = "model_points_pre" if state == "model" else "market_points"
                for player_id in sorted(covered):
                    row = row_by_id[player_id]
                    shift = float(row[target]) - float(row["mean_projection"])
                    objective[id_index[player_id]] += shift
                    shifts[player_id] = shift
                players = []
                for row in base_players:
                    player_id = str(row["id"])
                    players.append({
                        **row,
                        "state_world": float(objective[id_index[player_id]]),
                    })
                started = perf_counter()
                lineup = optimizer(
                    players,
                    locks={team.qb_id},
                    banned_lineups=[
                        frozenset(roster)
                        for roster in sorted(
                            (tuple(sorted(value)) for value in banned)
                        )
                    ],
                    stack=stack,
                    objective_col="state_world",
                    max_overlap=8,
                    env=env,
                )
                receipt = {
                    "team_rank": team_rank,
                    "team": team.team,
                    "state": state,
                    "anchor_rank": anchor_rank,
                    "anchor_block": block,
                    "anchor_world": int(world),
                    "team_story_score": story_score,
                    "locked_qb": team.qb_id,
                    "shifts": shifts,
                    "elapsed_seconds": float(perf_counter() - started),
                }
                if lineup is None:
                    receipts.append({**receipt, "accepted": False, "reason": "infeasible"})
                    continue
                roster = frozenset(str(value) for value in lineup.ids)
                if roster in banned or len(roster) != 9:
                    raise AssertionError("coherent-state optimizer returned banned roster")
                if not validate_common_legality(lineup) or not is_strict_lineup(lineup):
                    raise AssertionError("coherent-state optimizer returned non-strict roster")
                lineup.tag = f"coherent_{state}"
                rows = _roster_rows([lineup], player_ids)[0]
                totals = {
                    name: np.asarray(row_draws_by_block[name], dtype=np.float32)[
                        rows
                    ].sum(axis=0).astype(np.float32)
                    for name in names
                }
                accepted += 1
                additions.append(StateCandidate(
                    lineup=lineup,
                    team=team.team,
                    state=state,
                    state_index=accepted,
                    anchor_block=block,
                    anchor_world=int(world),
                    totals_by_block=totals,
                ))
                banned.add(roster)
                receipts.append({
                    **receipt,
                    "accepted": True,
                    "state_index": accepted,
                    "roster": sorted(roster),
                    "unshifted_training_tail_rank": list(_tail_rank(totals, names)),
                })
                if accepted == LINEUPS_PER_STATE:
                    break
            if accepted != LINEUPS_PER_STATE:
                raise RuntimeError(
                    f"coherent-state {team.team}/{state} could not produce two candidates"
                )
    if len(additions) != ADDITION_COUNT or len({
        _roster_key(row.lineup) for row in additions
    }) != ADDITION_COUNT:
        raise AssertionError("coherent-state generator did not produce 12 unique additions")
    return additions, receipts


def build_treatment_pool(
    control: Mapping[str, object],
    additions: Sequence[StateCandidate],
) -> dict[str, object]:
    """Replace the frozen 12 lowest training-tail candidates exactly 12-for-12."""
    candidates = list(control["candidate_lineups"])
    blocks = tuple(str(value) for value in control["training_blocks"])
    totals = {
        block: np.asarray(control["candidate_totals_by_block"][block], dtype=np.float32)
        for block in blocks
    }
    lineage = list(control["candidate_source_aggregation"])
    if len(candidates) < 80 or len(additions) != ADDITION_COUNT or \
            any(matrix.shape[0] != len(candidates) for matrix in totals.values()) or \
            len(lineage) != len(candidates):
        raise ValueError("coherent-state control/addition counts differ")
    ranked = []
    for index, lineup in enumerate(candidates):
        candidate_totals = {block: totals[block][index] for block in blocks}
        roster = _roster_key(lineup)
        ranked.append((
            _tail_rank(candidate_totals, blocks), roster, index,
        ))
    ranked.sort(key=lambda row: (row[0], row[1]))
    removed_indices = [row[2] for row in ranked[:ADDITION_COUNT]]
    removed_set = set(removed_indices)
    survivor_indices = [
        index for index in range(len(candidates)) if index not in removed_set
    ]
    additions_list = list(additions)
    treatment = [candidates[index] for index in survivor_indices] + [
        row.lineup for row in additions_list
    ]
    treatment_totals = {
        block: np.concatenate([
            totals[block][survivor_indices],
            np.stack([row.totals_by_block[block] for row in additions_list]),
        ], axis=0).astype(np.float32)
        for block in blocks
    }
    if len(treatment) != len(candidates) or len({
        _roster_key(row) for row in treatment
    }) != len(treatment):
        raise AssertionError("coherent-state treatment budget/identity differs")
    selected = select_tail_entries(
        np.concatenate([treatment_totals[block] for block in blocks], axis=1),
        80,
        194.0,
        env={"SELECT_LSE": "0"},
    )
    if len(selected) != 80 or len(set(selected)) != 80:
        raise AssertionError("coherent-state treatment selector is not exact 80")
    removal_receipts = []
    rank_by_index = {index: rank for rank, _, index in ranked}
    for index in removed_indices:
        removal_receipts.append({
            "index": index,
            "roster": list(_roster_key(candidates[index])),
            "training_tail_rank": list(rank_by_index[index]),
            "sources": list(lineage[index]["sources"]),
            "tags": list(lineage[index]["tags"]),
        })
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "candidate_budget": len(candidates),
        "removed": removal_receipts,
        "addition_count": len(additions_list),
        "candidate_lineups": treatment,
        "candidate_totals_by_block": treatment_totals,
        "selected_indices": selected,
        "selected_lineups": [treatment[index] for index in selected],
        "selected_totals_by_block": {
            block: treatment_totals[block][selected] for block in blocks
        },
    }


def _threshold_counts(values: np.ndarray) -> dict[str, int]:
    maxima = np.max(np.asarray(values, dtype=np.float64), axis=0)
    return {
        f"{threshold:g}": int(np.count_nonzero(maxima >= threshold))
        for threshold in REPORT_THRESHOLDS
    }


def _roster_intersection(left: Sequence[Lineup], right: Sequence[Lineup]) -> int:
    return len({_roster_key(row) for row in left} & {_roster_key(row) for row in right})


def evaluate_heldout_fold(
    *,
    control: Mapping[str, object],
    treatment: Mapping[str, object],
    additions: Sequence[StateCandidate],
    heldout_block: str,
    season: int,
    week: int,
) -> dict[str, object]:
    """Evaluate fixed-budget control/treatment on one untouched block."""
    player_ids = tuple(control["player_ids"])
    heldout_draws = np.asarray(control["heldout_row_draws"], dtype=np.float32)
    control_candidates = list(control["candidate_lineups"])
    control_selected = list(control["control_lineups"])
    treatment_candidates = list(treatment["candidate_lineups"])
    treatment_selected = list(treatment["selected_lineups"])
    if len(control_candidates) != len(treatment_candidates) or \
            len(control_selected) != 80 or len(treatment_selected) != 80:
        raise ValueError("coherent-state held-out budgets differ")
    matrices = {}
    for book, candidates, selected in (
        ("control", control_candidates, control_selected),
        ("treatment", treatment_candidates, treatment_selected),
    ):
        candidate_rows = _roster_rows(candidates, player_ids)
        selected_rows = _roster_rows(selected, player_ids)
        matrices[book] = {
            "candidate": heldout_draws[candidate_rows].sum(axis=1),
            "selected": heldout_draws[selected_rows].sum(axis=1),
        }
    counts = {
        scope: {
            book: _threshold_counts(matrices[book][scope])
            for book in ("control", "treatment")
        }
        for scope in REPORT_SCOPES
    }
    structure = {
        scope: {
            book: _structure_reach(lineups)
            for book, lineups in (
                ("control", (
                    control_candidates if scope == "candidate" else control_selected
                )),
                ("treatment", (
                    treatment_candidates if scope == "candidate" else treatment_selected
                )),
            )
        }
        for scope in REPORT_SCOPES
    }
    addition_rosters = {_roster_key(row.lineup) for row in additions}
    addition_by_roster = {
        _roster_key(row.lineup): row for row in additions
    }
    selected_additions = [
        row for row in treatment_selected if _roster_key(row) in addition_rosters
    ]
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "mechanical_valid": True,
        "season": int(season),
        "week": int(week),
        "heldout_block": str(heldout_block),
        "worlds": int(heldout_draws.shape[1]),
        "candidate_budget": len(control_candidates),
        "control_entries": len(control_selected),
        "treatment_entries": len(treatment_selected),
        "removed_candidates": len(treatment["removed"]),
        "added_candidates": len(additions),
        "selected_additions": len(selected_additions),
        "selected_additions_by_state": dict(sorted(Counter(
            row.tag.removeprefix("coherent_") for row in selected_additions
        ).items())),
        "selected_additions_by_team": dict(sorted(Counter(
            addition_by_roster[_roster_key(row)].team
            for row in selected_additions
        ).items())),
        "threshold_counts": counts,
        "shared_candidates": _roster_intersection(
            control_candidates, treatment_candidates,
        ),
        "shared_selected": _roster_intersection(
            control_selected, treatment_selected,
        ),
        "structure": structure,
        "effective_rank": {
            scope: {
                book: _score_effective_rank(matrices[book][scope])
                for book in ("control", "treatment")
            }
            for scope in REPORT_SCOPES
        },
    }


def aggregate_heldout_gate(folds: Sequence[Mapping]) -> dict[str, object]:
    """Apply the frozen tail-first gate to the complete 54-by-five grid."""
    rows = list(folds)
    if not rows or len(rows) % 5 or any(
        row.get("version") != VERSION
        or row.get("uses_realized_outcomes") is not False
        or row.get("mechanical_valid") is not True
        for row in rows
    ):
        raise ValueError("coherent-state held-out grid differs")
    slates = len(rows) // 5
    if Counter(str(row["heldout_block"]) for row in rows) != Counter({
        block: slates for block in REGISTERED_BLOCKS
    }):
        raise ValueError("coherent-state held-out block population differs")
    slate_keys = {(int(row["season"]), int(row["week"])) for row in rows}
    if len(slate_keys) != slates or any(
        sum(
            int(row["season"]) == season and int(row["week"]) == week
            for row in rows
        ) != 5
        for season, week in slate_keys
    ):
        raise ValueError("coherent-state slate grid differs")

    aggregate_counts = {
        scope: {
            book: {
                f"{threshold:g}": sum(
                    int(row["threshold_counts"][scope][book][f"{threshold:g}"])
                    for row in rows
                )
                for threshold in REPORT_THRESHOLDS
            }
            for book in ("control", "treatment")
        }
        for scope in REPORT_SCOPES
    }
    block_deltas = {
        block: {
            f"{threshold:g}": sum(
                int(row["threshold_counts"]["selected"]["treatment"][f"{threshold:g}"])
                - int(row["threshold_counts"]["selected"]["control"][f"{threshold:g}"])
                for row in rows if str(row["heldout_block"]) == block
            )
            for threshold in REPORT_THRESHOLDS
        }
        for block in REGISTERED_BLOCKS
    }
    structure_retention = {}
    for block in REGISTERED_BLOCKS:
        block_rows = [row for row in rows if str(row["heldout_block"]) == block]
        structure_retention[block] = {}
        for metric in ("unique_player_pairs", "unique_qb_stack_cores"):
            control_value = sum(
                int(row["structure"]["selected"]["control"][metric])
                for row in block_rows
            )
            treatment_value = sum(
                int(row["structure"]["selected"]["treatment"][metric])
                for row in block_rows
            )
            structure_retention[block][metric] = (
                float(treatment_value / control_value) if control_value else 1.0
            )

    def delta(scope: str, threshold: str) -> int:
        return int(
            aggregate_counts[scope]["treatment"][threshold]
            - aggregate_counts[scope]["control"][threshold]
        )

    def retention(scope: str, threshold: str) -> float:
        control_value = aggregate_counts[scope]["control"][threshold]
        return (
            float(aggregate_counts[scope]["treatment"][threshold] / control_value)
            if control_value else 1.0
        )

    conditions = {
        "candidate_p210_strictly_improves": delta("candidate", "210") > 0,
        "selected_p210_strictly_improves": delta("selected", "210") > 0,
        "selected_p210_improves_in_three_blocks": sum(
            row["210"] > 0 for row in block_deltas.values()
        ) >= 3,
        "candidate_and_selected_p230_nondecline": all(
            delta(scope, "230") >= 0 for scope in REPORT_SCOPES
        ),
        "candidate_and_selected_p194_retain_95pct": all(
            retention(scope, "194") >= 0.95 for scope in REPORT_SCOPES
        ),
        "every_block_pair_and_core_retain_90pct": all(
            value >= 0.90
            for metrics in structure_retention.values()
            for value in metrics.values()
        ),
    }
    passes = all(conditions.values())
    season_threshold_counts = {
        str(season): {
            scope: {
                book: {
                    f"{threshold:g}": sum(
                        int(row["threshold_counts"][scope][book][f"{threshold:g}"])
                        for row in rows if int(row["season"]) == season
                    )
                    for threshold in REPORT_THRESHOLDS
                }
                for book in ("control", "treatment")
            }
            for scope in REPORT_SCOPES
        }
        for season in sorted({int(row["season"]) for row in rows})
    }
    leave_one_slate_out = []
    if slates > 1:
        for season, week in sorted(slate_keys):
            retained = [
                row for row in rows
                if (int(row["season"]), int(row["week"])) != (season, week)
            ]

            def retained_count(scope: str, book: str, threshold: str) -> int:
                return sum(
                    int(row["threshold_counts"][scope][book][threshold])
                    for row in retained
                )

            leave_one_slate_out.append({
                "excluded_slate": f"{season}-{week}",
                "candidate_p210_delta": (
                    retained_count("candidate", "treatment", "210")
                    - retained_count("candidate", "control", "210")
                ),
                "selected_p210_delta": (
                    retained_count("selected", "treatment", "210")
                    - retained_count("selected", "control", "210")
                ),
                "candidate_p230_delta": (
                    retained_count("candidate", "treatment", "230")
                    - retained_count("candidate", "control", "230")
                ),
                "selected_p230_delta": (
                    retained_count("selected", "treatment", "230")
                    - retained_count("selected", "control", "230")
                ),
            })
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "slates": slates,
        "folds": len(rows),
        "aggregate_threshold_counts": aggregate_counts,
        "season_threshold_counts": season_threshold_counts,
        "selected_block_deltas": block_deltas,
        "structure_retention": structure_retention,
        "leave_one_slate_out": leave_one_slate_out,
        "conditions": conditions,
        "passes_scorefree_gate": passes,
        "disposition": (
            "coherent-market-state-shadow-licensed"
            if passes else "coherent-market-state-scorefree-fails"
        ),
        "production_change_licensed": False,
    }


def run_scorefree_slate(
    books: Mapping[str, CandidateBatch],
    *,
    season: int,
    week: int,
    expected_worlds_per_block: int = 10_000,
    optimizer: Callable[..., Lineup | None] = optimize,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, object]:
    """Run the five frozen train-four/test-one folds for one slate."""
    if tuple(sorted(books)) != REGISTERED_BLOCKS or season not in {
        2023, 2024, 2025,
    } or week not in range(1, 19):
        raise ValueError("coherent-state slate/source identity differs")
    team_states = rank_eligible_teams(
        books["R0"].player_rows, books["R0"].candidates,
    )
    folds = []
    started = perf_counter()
    for heldout in REGISTERED_BLOCKS:
        fold_started = perf_counter()
        control = build_training_control(
            books,
            heldout,
            expected_worlds_per_block=expected_worlds_per_block,
        )
        forbidden = {_roster_key(row) for row in control["candidate_lineups"]}
        additions, generation = generate_state_candidates(
            player_rows=control["player_rows"],
            player_ids=control["player_ids"],
            row_draws_by_block=control["row_draws_by_block"],
            training_blocks=control["training_blocks"],
            team_states=team_states,
            forbidden_rosters=forbidden,
            optimizer=optimizer,
        )
        treatment = build_treatment_pool(control, additions)
        heldout_result = evaluate_heldout_fold(
            control=control,
            treatment=treatment,
            additions=additions,
            heldout_block=heldout,
            season=season,
            week=week,
        )
        folds.append({
            **heldout_result,
            "training_blocks": list(control["training_blocks"]),
            "team_states": [{
                "team": row.team,
                "disagreement": row.disagreement,
                "qb_id": row.qb_id,
                "covered_player_ids": list(row.covered_player_ids),
                "player_disagreements": [list(value) for value in row.player_disagreements],
            } for row in team_states],
            "generation": generation,
            "removed": treatment["removed"],
            "added": [{
                "team": row.team,
                "state": row.state,
                "state_index": row.state_index,
                "anchor_block": row.anchor_block,
                "anchor_world": row.anchor_world,
                "roster": list(_roster_key(row.lineup)),
            } for row in additions],
            "control_candidate_rosters": [
                list(_roster_key(row)) for row in control["candidate_lineups"]
            ],
            "treatment_candidate_rosters": [
                list(_roster_key(row)) for row in treatment["candidate_lineups"]
            ],
            "control_selected_rosters": [
                list(_roster_key(row)) for row in control["control_lineups"]
            ],
            "treatment_selected_rosters": [
                list(_roster_key(row)) for row in treatment["selected_lineups"]
            ],
            "elapsed_seconds": float(perf_counter() - fold_started),
        })
        if progress_callback is not None:
            progress_callback(heldout)
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "season": season,
        "week": week,
        "team_states": [row.team for row in team_states],
        "folds": folds,
        "elapsed_seconds": float(perf_counter() - started),
    }


def protocol_receipt() -> dict[str, object]:
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "team_limit": TEAM_LIMIT,
        "state_order": list(STATE_ORDER),
        "lineups_per_state": LINEUPS_PER_STATE,
        "addition_count": ADDITION_COUNT,
        "anchor_limit": ANCHOR_LIMIT,
        "control_entries": 80,
        "heldout_folds": 5,
    }


__all__ = [
    "ADDITION_COUNT",
    "ANCHOR_LIMIT",
    "LINEUPS_PER_STATE",
    "STATE_ORDER",
    "TEAM_LIMIT",
    "TeamState",
    "StateCandidate",
    "VERSION",
    "aggregate_heldout_gate",
    "build_treatment_pool",
    "evaluate_heldout_fold",
    "generate_state_candidates",
    "protocol_receipt",
    "rank_eligible_teams",
    "run_scorefree_slate",
]
