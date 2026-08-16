from dataclasses import replace

import numpy as np
import pytest

from nfl_dfs.analysis.constraint_lattice import (
    CELL_ORDER,
    CELL_QUOTAS,
    ExceptionCandidate,
    aggregate_heldout_gate,
    construct_exception_sleeve,
    evaluate_heldout_fold,
    exception_cell,
    protocol_receipt,
    rank_exception_candidates,
    stack_rules_for_cell,
    validate_exception_book,
)
from nfl_dfs.optimizer.lineup import Lineup, StackRules, optimize, optimize_many


def _pool():
    players = []
    player_id = 0
    opponents = {
        "A": "B", "B": "A", "C": "D",
        "D": "C", "E": "F", "F": "E",
    }
    for team_index, team in enumerate(opponents):
        game = f"G{team_index // 2}"
        for pos, count in (("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1), ("DST", 1)):
            for position_index in range(count):
                players.append({
                    "id": f"p{player_id}",
                    "name": f"{team}-{pos}-{position_index}",
                    "pos": pos,
                    "team": team,
                    "opp": opponents[team],
                    "game_id": game,
                    "salary": 5_500,
                    "proj": float(
                        100 - 2 * team_index - position_index
                        + {"QB": 5, "RB": 4, "WR": 3, "TE": 2, "DST": 1}[pos]
                    ),
                })
                player_id += 1
    return players


@pytest.mark.parametrize("cell", CELL_ORDER)
def test_optimizer_constructs_exact_atomic_exception(cell):
    lineup = optimize(_pool(), stack=stack_rules_for_cell(cell))
    assert lineup is not None
    assert lineup.salary == 49_500
    assert exception_cell(lineup) == cell


def test_new_stack_bounds_default_to_inactive():
    rules = StackRules(qb_stack_min=2, bring_back_min=1)
    assert rules.qb_stack_max is None
    assert rules.bring_back_max is None
    assert rules.require_rb_vs_dst is False
    assert rules.require_two_rb_same_team is False
    assert optimize(_pool(), stack=rules) is not None


def test_stack_rule_conflicts_fail_closed():
    with pytest.raises(ValueError, match="both forbidden and required"):
        optimize(
            _pool(),
            stack=StackRules(require_rb_vs_dst=True),
        )
    with pytest.raises(ValueError, match="at least its minimum"):
        optimize(
            _pool(),
            stack=StackRules(qb_stack_min=2, qb_stack_max=1),
        )


def test_exception_book_enforces_cell_labels_and_quotas():
    lineups = []
    cells = []
    for cell in CELL_ORDER:
        lineup = optimize(_pool(), stack=stack_rules_for_cell(cell))
        assert lineup is not None
        lineups.append(lineup)
        cells.append(cell)
    counts = validate_exception_book(lineups, cells)
    assert counts == {cell: 1 for cell in CELL_ORDER}

    duplicated = [lineups[0], replace(lineups[0])]
    with pytest.raises(ValueError, match="repeat"):
        validate_exception_book(duplicated, [CELL_ORDER[0], CELL_ORDER[0]])

    second = optimize(
        _pool(),
        stack=stack_rules_for_cell(CELL_ORDER[-1]),
        banned_lineups=[lineups[-1].ids],
    )
    assert second is not None and second.ids != lineups[-1].ids
    with pytest.raises(ValueError, match="quota"):
        validate_exception_book(
            [lineups[-1], second],
            [CELL_ORDER[-1], CELL_ORDER[-1]],
        )


def test_protocol_receipt_is_outcome_free_and_exact():
    assert protocol_receipt() == {
        "version": "constraint-lattice-scorefree-v1",
        "uses_realized_outcomes": False,
        "cell_order": list(CELL_ORDER),
        "cell_quotas": dict(CELL_QUOTAS),
        "maximum_exception_entries": 8,
        "control_entries": 80,
        "heldout_folds": 5,
    }


def _dummy_control():
    return [
        Lineup([{"id": f"control-{index}-{slot}"} for slot in range(9)])
        for index in range(80)
    ]


def _candidate(cell: str, banned=()):
    lineup = optimize(
        _pool(),
        stack=stack_rules_for_cell(cell),
        banned_lineups=list(banned),
    )
    assert lineup is not None
    return lineup


def test_candidate_ranking_uses_fixed_cell_quota_and_tail_order():
    first = _candidate("two_rb_same_team")
    second = _candidate("two_rb_same_team", [first.ids])
    blocks = ("R0", "R1", "R2", "R3")
    low = {block: np.full(10, 200.0) for block in blocks}
    high = {block: np.asarray([240.0, *([200.0] * 9)]) for block in blocks}
    retained, receipts = rank_exception_candidates([
        ExceptionCandidate(first, "two_rb_same_team", low),
        ExceptionCandidate(second, "two_rb_same_team", high),
    ], blocks)
    assert len(retained) == 1
    assert retained[0].lineup.ids == second.ids
    assert receipts[0]["cell"] == "two_rb_same_team"
    assert receipts[0]["probabilities"]["p230"] == {
        block: 0.1 for block in blocks
    }


def test_sleeve_admits_only_multiblock_p230_improvement():
    blocks = ("R0", "R1", "R2", "R3")
    control = _dummy_control()
    control_totals = {
        block: np.full((80, 10), 100.0) for block in blocks
    }
    admitted_lineup = _candidate("rb_vs_dst")
    admitted_totals = {
        block: np.asarray([240.0, *([100.0] * 9)]) for block in blocks
    }
    rejected_lineup = _candidate("qb1_bringback")
    rejected_totals = {
        block: np.asarray([
            240.0 if block in {"R0", "R1"} else 100.0,
            *([100.0] * 9),
        ]) for block in blocks
    }
    result = construct_exception_sleeve(
        control,
        control_totals,
        [
            ExceptionCandidate(admitted_lineup, "rb_vs_dst", admitted_totals),
            ExceptionCandidate(rejected_lineup, "qb1_bringback", rejected_totals),
        ],
        blocks,
    )
    assert len(result["lineups"]) == 80
    assert result["exception_counts"]["rb_vs_dst"] == 1
    assert result["exception_counts"]["qb1_bringback"] == 0
    assert len(result["admitted"]) == 1
    assert result["rejected"][0]["reason"] == "admission_margin_failed"
    assert result["treatment_coverage_world_counts"]["230"] == {
        block: 1 for block in blocks
    }


def test_heldout_fold_and_aggregate_gate_are_p230_first():
    strict = optimize_many(
        _pool(),
        n_lineups=80,
        max_overlap=8,
        stack=StackRules(qb_stack_min=2, bring_back_min=1),
    )
    assert len(strict) == 80
    exception = _candidate("qb1_no_bringback")
    treatment = [*strict[:-1], exception]
    control_totals = np.full((80, 10), 200.0)
    treatment_totals = control_totals.copy()
    treatment_totals[-1, 0] = 240.0
    folds = [
        evaluate_heldout_fold(
            heldout_block=f"R{seed}",
            control_lineups=strict,
            treatment_lineups=treatment,
            control_totals=control_totals,
            treatment_totals=treatment_totals,
        )
        for seed in range(5)
    ]
    result = aggregate_heldout_gate(folds)
    assert result["selected_230_net_worlds"] == 5
    assert result["heldout_blocks_improving_p230"] == 5
    assert result["selected_194_retention"] == 1.0
    assert result["passes_scorefree_gate"] is True
    assert result["production_change_licensed"] is False

    folds[0]["threshold_counts"]["treatment"]["230"] = 0
    folds[1]["threshold_counts"]["treatment"]["230"] = 0
    folds[2]["threshold_counts"]["treatment"]["230"] = 0
    failed = aggregate_heldout_gate(folds)
    assert failed["heldout_blocks_improving_p230"] == 2
    assert failed["passes_scorefree_gate"] is False
