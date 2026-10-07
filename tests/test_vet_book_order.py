"""vet_book.block_order: hard / material rows sink WITHIN their block; nothing crosses the mean/sleeve boundary."""
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import vet_book as vb  # noqa: E402


def test_block_order_sorts_within_the_mean_and_sleeve_blocks_only():
    tiers = [(True, False), (False, False), (False, True), (False, False),   # mean block: row 0 hard, row 2 material
             (False, False), (True, False), (False, False)]                   # sleeve block: row 5 hard
    assert vb.block_order(tiers, 4) == [1, 3, 2, 0, 4, 6, 5]
    assert vb.block_order(tiers, 7) == [1, 3, 4, 6, 2, 0, 5]                  # one block: the old whole-book order
    assert vb.block_order(tiers, 0) == [1, 3, 4, 6, 2, 0, 5] and vb.block_order([], 3) == []


def test_cell_block_order_keeps_every_mix_cell_on_its_own_positions():
    # mean block of 6: cells A1 B C A1 B C; row 0 (A1) and row 2 (C) are flagged; sleeve rows 6-7, row 6 hard
    tiers = [(False, True), (False, False), (True, False), (False, False), (False, False), (False, False),
             (True, False), (False, False)]
    cells = ["A1", "B", "C", "A1", "B", "C", None, None]
    order = vb.cell_block_order(tiers, 6, cells)
    assert order == [3, 1, 5, 0, 4, 2, 7, 6]                     # A1 rows swap, C rows swap, B untouched, sleeve sorted
    assert [cells[i] for i in order[:6]] == cells[:6]            # the cell at every main position is unchanged
    assert vb.block_order(tiers, 6)[:6] == [1, 3, 4, 5, 0, 2]    # the plain sort would move B into positions 1 and 3
    assert vb.cell_block_order([(False, False)] * 3, 3, ["A1", "B", "C"]) == [0, 1, 2]   # nothing flagged: no move
    assert vb.cell_block_order([], 0, []) == []


def test_a_flagged_row_alone_in_its_cell_stays_and_is_reported():
    # A2 has ONE main row (position 1) and it is flagged: it cannot sink without moving another cell into its position
    # (intended -- the cell keeps the entries plan_weights gave it); flagged_kept_ahead names it
    tiers = [(False, False), (False, True), (False, False), (False, False)]
    cells = ["A1", "A2", "B", "A1"]
    order = vb.cell_block_order(tiers, 4, cells)
    assert order == [0, 1, 2, 3] and vb.flagged_kept_ahead(tiers, 4, order) == [1]
    assert vb.flagged_kept_ahead(tiers, 4, vb.block_order(tiers, 4)) == []          # the plain sort never keeps one


def test_cell_block_order_is_used_only_for_a_mix_main():
    tiers = [(False, True), (False, False), (True, False), (False, False), (False, False), (False, False)]

    def refuse():
        raise AssertionError("a non-mix book must not read cells")
    for receipt in ({}, {"config": {}}, {"config": {"union": {"main": "pmo_x50"}}}, {"config": {"union": {"main": "ws"}}}):
        order, cells = vb.vetted_order(tiers, 6, receipt, refuse)
        assert order == vb.block_order(tiers, 6) and cells is None                  # the house book: today's order exactly
    order, cells = vb.vetted_order(tiers, 6, {"config": {"union": {"main": "mix"}}}, lambda: ["A1", "B", "C", "A1", "B", "C"])
    assert order == [3, 1, 5, 0, 4, 2] and cells == ["A1", "B", "C", "A1", "B", "C"]


def test_book_players_without_an_fp_projection_are_tagged_but_never_weighted(tmp_path, capsys):
    """The reviewer's guard (10-06, O-22): a book player the union selected on OUR mean (no FP projection) is named."""
    frame = pd.DataFrame({"id": ["a", "b", "c"], "dk": ["11", "22", "33"]})
    book = [["11", "22"], ["22", "33"]]
    flags, name = defaultdict(list), {"11": "A", "22": "B", "33": "C"}
    assert vb.fp_gap_flags(tmp_path, frame, book, flags, name) == [] and not flags     # no proj_source.csv: not an FP run
    pd.DataFrame({"id": ["a", "b"], "fp": [10.0, 12.0]}).to_csv(tmp_path / "proj_source.csv", index=False)
    assert vb.fp_gap_flags(tmp_path, frame, book, flags, name) == ["C"]
    assert dict(flags) == {"33": ["projection:ours-no-FP"]}
    assert "1 book player(s) selected on OUR projection" in capsys.readouterr().out
    from nfl_dfs.inference import enter_layout as EL
    assert "projection" not in EL.INJURY_TAGS                                           # never bars a row from the head


def test_vetting_records_each_vetted_positions_term_block():
    """The reviewer (10-07): every entered row attributable to its block, L or T, after vetting's within-cell moves."""
    rec = {"config": {"union": {"mix": {"mix": {"term": {"blocks": ["L", "T", "L", "L", "T"]}}}}}}
    out = vb.term_blocks_by_vetted_position(rec, [0, 2, 1, 3, 4])
    assert out == {"term_block_by_vetted_position": ["L", "L", "T", "L", "T"], "term_block_source_positions": [2, 5]}
    assert vb.term_blocks_by_vetted_position({"config": {"union": {"mix": {"mix": {"term": None}}}}}, [0, 1]) == {}
    assert vb.term_blocks_by_vetted_position({}, [0]) == {}
