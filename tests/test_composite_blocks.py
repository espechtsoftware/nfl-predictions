"""O-23: the composite re-sort keeps a two-track book's blocks, so its upload emits.

Every build since Saturday 10-03 printed "EMIT FAILED composite-all30 1-30": the union book repeats some mean rows as
sleeve rows (accepted repeats), and the composite's single global sort put both copies of such a roster side by side in
the mean block, which the emitter refuses ("lineup 5 repeats an earlier roster within its block"). The fix sorts each
block on its own (reviewer 10-04: separate blocks, not a dedupe).
"""
from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.inference import dk_upload_csv_v1 as up

SCRIPT = Path(__file__).parents[1] / "scripts" / "player_score.py"
SPEC = importlib.util.spec_from_file_location("player_score_blocks", SCRIPT)
player_score = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(player_score)

SLOTS = ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST")
QBS = [str(100 + i) for i in range(10)]
CORE = ["201", "202", "301", "302", "303", "401", "203", "501"]   # RB RB WR WR WR TE FLEX(RB) DST
POS = {**{q: "QB" for q in QBS}, "201": "RB", "202": "RB", "203": "RB", "301": "WR", "302": "WR", "303": "WR",
       "401": "TE", "501": "DST"}


def roster(q: int) -> list[str]:
    return [QBS[q], *CORE]


# The union shape: mean rows K = 6 (unique), then a 3-row sleeve whose middle row REPEATS mean row 0.
MEAN_K = 6
BOOK = [roster(i) for i in range(MEAN_K)] + [roster(6), roster(0), roster(7)]
# Composite scores per source row: the repeated roster scores highest (both copies score the same, being one roster).
SCORES = [9.0, 5.0, 4.0, 3.0, 2.0, 1.0, 8.5, 9.0, 0.5]
HARD = [False] * len(BOOK)
RECEIPT = {"season": 2026, "week": 4, "config": {"operational_k": MEAN_K, "tail_sleeve": {"rows": 3, "selector_used": "mean"}}}


def _composite_dir(tmp_path: Path, order: list[int]) -> Path:
    """The composite dir exactly as player_score.py writes it: re-sorted book.csv, the run's frame, source_receipt.json."""
    d = tmp_path / "composite"
    d.mkdir()
    with (d / "book.csv").open("w", newline="") as h:
        w = csv.writer(h); w.writerow(SLOTS); [w.writerow(BOOK[i]) for i in order]
    pd.DataFrame({"dk_player_id": [int(p) for p in POS], "dk_draftable_id": pd.array([40000000 + int(p) for p in POS], dtype="Int64"),
                  "position": list(POS.values()), "draft_group_id": ["151307"] * len(POS)}).to_parquet(d / "frame.parquet")
    (d / "source_receipt.json").write_text(json.dumps(RECEIPT))
    return d


def _emit(d: Path, out: Path, first: int, last: int) -> dict:
    """What scripts/emit_dk_upload_csv_v1.py does for `--source run-dir --ranks first-last`."""
    rows, receipt = up.rows_from_live_week_run(d)
    rows = up.slice_ranks(rows, first, last)
    return up.write_upload_csv(rows, out, mean_rows=up.block_after_slice(receipt["mean_rows"], first, len(rows)))


def test_each_block_is_sorted_on_its_own():
    order = player_score.composite_order(SCORES, HARD, MEAN_K)
    assert order[:MEAN_K] == [0, 1, 2, 3, 4, 5]          # mean block: score order (already descending here)
    assert order[MEAN_K:] == [7, 6, 8]                    # sleeve block: re-sorted, but never moved into the mean block
    assert sorted(order) == list(range(len(BOOK)))        # same rows: comparable to the union row for row


def test_hard_rows_go_last_within_their_block():
    hard = list(HARD); hard[0] = True; hard[7] = True
    order = player_score.composite_order(SCORES, hard, MEAN_K)
    assert order[:MEAN_K] == [1, 2, 3, 4, 5, 0]
    assert order[MEAN_K:] == [6, 8, 7]


def test_one_track_book_keeps_the_global_sort():
    scores = [1.0, 3.0, 2.0]
    assert player_score.composite_order(scores, [False] * 3, None) == [1, 2, 0]
    assert player_score.composite_order(scores, [False] * 3, 99) == [1, 2, 0]


def test_the_block_sorted_composite_emits_with_its_repeat(tmp_path):
    d = _composite_dir(tmp_path, player_score.composite_order(SCORES, HARD, MEAN_K))
    assert _emit(d, tmp_path / "all.csv", 1, len(BOOK))["rows"] == len(BOOK)
    assert _emit(d, tmp_path / "top.csv", 1, 5)["rows"] == 5     # the composite-all30 shape: a head slice


def test_the_old_global_sort_is_the_defect(tmp_path):
    """The pre-fix order puts both copies of the repeated roster in the mean block; the emitter refuses it."""
    old = sorted(range(len(BOOK)), key=lambda i: (HARD[i], -SCORES[i], i))
    assert old[:2] == [0, 7]
    d = _composite_dir(tmp_path, old)
    with pytest.raises(up.DkUploadCsvError, match="repeats an earlier roster within its block"):
        _emit(d, tmp_path / "top.csv", 1, 5)


@pytest.mark.parametrize("receipt, expected", [
    ({"config": {"operational_k": 105, "tail_sleeve": {"rows": 5}}}, 105),
    ({"config": {"operational_k": 90, "tail_sleeve": 0}}, None),
    ({"config": {"operational_k": 90}}, None),
    ({"config": None}, None),
    ({}, None),
    ([], None),
])
def test_mean_rows_from_receipt(receipt, expected):
    assert up.mean_rows_from_receipt(receipt) == expected
