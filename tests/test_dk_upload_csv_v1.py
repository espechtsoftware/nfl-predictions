"""Draftable-ID upload CSV: exact rows, slot legality, and fail-closed mutations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.inference import dk_upload_csv_v1 as up

# player id -> (draftable id, position); the DST row uses a 3-digit player id
# like the real feed, and every draftable id is 8 digits like the real slate.
FRAME_ROWS = [
    ("1174752", 43727299, "QB"), ("1214154", 43727325, "RB"),
    ("1228244", 43727327, "RB"), ("1109979", 43727631, "WR"),
    ("1122592", 43727639, "WR"), ("1164979", 43727735, "WR"),
    ("820699", 43728237, "TE"), ("884609", 43728241, "TE"),
    ("357", 43728525, "DST"), ("1000001", 43729001, "RB"),
    ("2000002", 43729002, "QB"),
]
BOOK_ROW = ["1174752", "1214154", "1228244", "1109979", "1122592", "1164979",
            "820699", "884609", "357"]
EXPECTED = [43727299, 43727325, 43727327, 43727631, 43727639, 43727735,
            43728237, 43728241, 43728525]


def _frame(rows=FRAME_ROWS, group: str = "151307") -> pd.DataFrame:
    return pd.DataFrame({
        "dk_player_id": [int(r[0]) for r in rows],
        "dk_draftable_id": pd.array([r[1] for r in rows], dtype="Int64"),
        "position": [r[2] for r in rows],
        "draft_group_id": [group] * len(rows),
    })


def _run_dir(tmp_path: Path, *, book_rows=None, frame=None) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    rows = [BOOK_ROW] if book_rows is None else book_rows
    lines = [",".join(up.DK_SLOT_ORDER)] + [",".join(r) for r in rows]
    (run / "book.csv").write_text("\n".join(lines) + "\n")
    (frame if frame is not None else _frame()).to_parquet(run / "frame.parquet")
    return run


def test_run_dir_rows_map_player_ids_to_draftable_ids_in_slot_order(tmp_path) -> None:
    rows, receipt = up.rows_from_live_week_run(_run_dir(tmp_path))
    assert rows == [EXPECTED]
    assert receipt["draft_group_id"] == "151307"
    assert receipt["id_form"].startswith("dk_player_id -> dk_draftable_id")


def test_book_entries_are_ordered_by_rank_and_written_create_only(tmp_path) -> None:
    entries = [
        {"lineup_rank": 2, "slot_dk_draftable_ids": [
            43727299, 43729001, 43727327, 43727631, 43727639, 43727735,
            43728237, 43728241, 43728525]},
        {"lineup_rank": 1, "slot_dk_draftable_ids": EXPECTED},
    ]
    positions = {d: p for _, d, p in FRAME_ROWS}
    rows = up.rows_from_book_entries(entries, position_by_draftable_id=positions)
    assert rows[0] == EXPECTED and rows[1][1] == 43729001
    out = tmp_path / "upload.csv"
    receipt = up.write_upload_csv(rows, out)
    assert receipt["rows"] == 2 and receipt["id_form"] == "dk_draftable_id"
    assert out.read_text().splitlines()[0] == "QB,RB,RB,WR,WR,WR,TE,FLEX,DST"
    assert up.read_upload_csv(out) == rows
    with pytest.raises(up.DkUploadCsvError, match="refusing to overwrite"):
        up.write_upload_csv(rows, out)


def test_salary_catalog_positions() -> None:
    catalog = {"players": [{"draftable_id": 43727299, "pos": "qb", "player_id": 1}]}
    assert up.positions_from_salary_catalog(catalog) == {43727299: "QB"}
    with pytest.raises(up.DkUploadCsvError, match="repeats"):
        up.positions_from_salary_catalog({"players": catalog["players"] * 2})
    with pytest.raises(up.DkUploadCsvError, match="no players"):
        up.positions_from_salary_catalog({"rows": []})


@pytest.mark.parametrize(
    "mutate,match",
    [
        # a player id the frame does not carry
        (lambda k: k["book_rows"][0].__setitem__(0, "999"), "not in the frame"),
        # an RB (not already rostered) in the QB slot
        (lambda k: k["book_rows"][0].__setitem__(0, "1000001"), "cannot fill the QB"),
        # a second QB in the FLEX slot
        (lambda k: k["book_rows"][0].__setitem__(7, "2000002"), "cannot fill the FLEX"),
        # the same player in two slots
        (lambda k: k["book_rows"][0].__setitem__(7, "820699"),
         "repeats a draftable id"),
        # the same roster twice
        (lambda k: k["book_rows"].append(list(BOOK_ROW)), "repeats an earlier roster"),
        # a missing draftable id in the frame
        (lambda k: k.__setitem__("frame", _frame(
            [("1174752", None, "QB")] + FRAME_ROWS[1:])), "no draftable id"),
        # two draft groups in one frame
        (lambda k: k.__setitem__("frame", pd.concat(
            [_frame(), _frame(group="151308")])), "draft groups"),
        # a repeated player id in the frame
        (lambda k: k.__setitem__("frame", pd.concat([_frame(), _frame()])),
         "repeats a dk_player_id"),
        # a bad header
        (lambda k: k.__setitem__("header", "QB,RB,RB,WR,WR,WR,TE,DST,FLEX"),
         "slot order"),
    ],
)
def test_run_dir_mutations_fail_closed(
    tmp_path, mutate: Callable[[dict], object], match: str
) -> None:
    kwargs = {"book_rows": [list(BOOK_ROW)], "frame": None, "header": None}
    mutate(kwargs)
    run = _run_dir(tmp_path, book_rows=kwargs["book_rows"], frame=kwargs["frame"])
    if kwargs["header"] is not None:
        lines = (run / "book.csv").read_text().splitlines()
        lines[0] = kwargs["header"]
        (run / "book.csv").write_text("\n".join(lines) + "\n")
    with pytest.raises(up.DkUploadCsvError, match=match):
        up.rows_from_live_week_run(run)


@pytest.mark.parametrize(
    "rows,match",
    [
        ([EXPECTED[:8]], "exactly 9"),
        ([EXPECTED[:8] + [EXPECTED[0]]], "repeats a draftable id"),
        ([EXPECTED[:8] + [0]], "positive draftable id"),
        ([EXPECTED[:8] + ["abc"]], "numeric draftable id"),
        ([], "no lineups"),
    ],
)
def test_check_rows_refuses_bad_rows(rows, match) -> None:
    with pytest.raises(up.DkUploadCsvError, match=match):
        up.check_rows(rows)


def test_book_entries_refuse_bad_ranks_and_missing_slots() -> None:
    with pytest.raises(up.DkUploadCsvError, match="lacks slot_dk_draftable_ids"):
        up.rows_from_book_entries([{"lineup_rank": 1}])
    with pytest.raises(up.DkUploadCsvError, match="not exactly 1..n"):
        up.rows_from_book_entries([
            {"lineup_rank": 2, "slot_dk_draftable_ids": EXPECTED},
        ])
    with pytest.raises(up.DkUploadCsvError, match="not on the slate"):
        up.rows_from_book_entries(
            [{"lineup_rank": 1, "slot_dk_draftable_ids": EXPECTED}],
            position_by_draftable_id={43727299: "QB"},
        )


def test_slice_ranks_is_inclusive_and_bounded() -> None:
    rows = [[i] * 9 for i in range(1, 6)]
    assert up.slice_ranks(rows, 2, 3) == [[2] * 9, [3] * 9]
    assert up.slice_ranks(rows, 1, 5) == rows
    for first, last, match in ((0, 3, "1 <= first"), (3, 2, "first <= last"),
                               (1, 6, "exceeds")):
        with pytest.raises(up.DkUploadCsvError, match=match):
            up.slice_ranks(rows, first, last)
