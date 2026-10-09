"""entry_tags: a roster maps to its build record (book first, then tail, spare, corpus; never re-labelled), the cheap
block's 0-based positions mark book ranks (1-based), and the result buckets follow the calibration check's rules."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import entry_tags as T  # noqa: E402

R = [[f"p{i}{j}" for j in range(9)] for i in range(6)]


REP = [{"vetted_position": 3, "source_rank": 2, "removed": R[1], "replacement": [f"q{j}" for j in range(9)], "candidate_index": 7,
        "candidate_source": "mix_spare", "cell": "B"},
       {"vetted_position": 4, "source_rank": 3, "removed": R[2], "replacement": R[4], "candidate_index": 8,
        "candidate_source": "mix_spare", "cell": "house", "cell_fallback": "house"}]


def _index(reps=()):
    book = {"entries": [{"rank": 1, "players": R[0], "tag": "mix_A1"}, {"rank": 2, "players": R[1], "tag": "mix_B"},
                        {"rank": 3, "players": R[2], "tag": "mix_C"}],
            "tail_sleeve": [{"rank": 4, "players": R[3], "tag": "field"}]}
    cands = pd.DataFrame({"names": ["|".join(R[0]), "|".join(R[4]), "|".join(R[5]), "|".join(R[4])],
                          "tag": ["boom", "mix_A2", "boom", "boom"], "source_run": ["t70", "mix_spare", "saturday", "t70"]})
    return T.build_index(book, cands, [1], reps)


def test_build_index_precedence_and_term_positions():
    idx = _index()
    k = lambda r: T.roster_key(reversed(r))                                   # noqa: E731  (a set: order never matters)
    assert idx[k(R[0])] == {"kind": "book", "book_rank": 1, "tag": "mix_A1", "term": False, "source_run": None}   # not the corpus' "boom"
    assert idx[k(R[1])]["term"] is True and idx[k(R[2])]["term"] is False      # position 1 (0-based) = book rank 2
    assert idx[k(R[3])]["kind"] == "tail" and idx[k(R[4])]["kind"] == "spare" and idx[k(R[4])]["tag"] == "mix_A2"
    assert idx[k(R[5])] == {"kind": "corpus", "book_rank": None, "tag": "boom", "term": False, "source_run": "saturday"}


def test_tag_entries_buckets_and_unmatched():
    idx = _index()
    ours = pd.DataFrame({"contest_id": ["c1", "c1", "c2", "c2"], "entry_id": ["e1", "e2", "e3", "e4"],
                         "names": [tuple(R[1]), tuple(R[0]), tuple(f"x{j}" for j in range(9)), tuple(R[5])]})
    recon = pd.DataFrame({"contest_id": ["c1", "c1", "c2"], "entry_id": ["e1", "e2", "e3"], "rank_calc": [2, 11, 1],
                          "cash_calc": [0.0, 20.0, 499.99], "ticket_calc": [300.0, 0.0, 0.0]})
    t = T.tag_entries(ours, idx, recon, {"c1": 200, "c2": 50})
    assert t.kind.tolist() == ["book", "book", "unmatched", "corpus"] and t.settled.tolist() == [True, True, True, False]
    assert t.top1.tolist()[:3] == [True, False, True]                         # floor(0.01 x 200) = 2; tiny contest: rank 1
    assert t.top10.tolist()[:3] == [True, True, True] and t.cash.tolist()[:3] == [True, True, True]
    assert t.big.tolist()[:3] == [True, False, False]                         # a $300 ticket is big; $499.99 is not
    assert [T.label(r) for _, r in t.iterrows()] == ["mix_B +cheap block", "mix_A1", "unmatched", "corpus:boom"]
    agg = {g["group"]: g for g in T.aggregates(t)}
    assert agg["mix_B +cheap block"]["big"] == 1 and "corpus:boom" not in agg  # unsettled rows are not aggregated


def test_replacements_keep_the_removed_rows_cell_and_block():
    idx = _index(REP)
    k = lambda r: T.roster_key(r)                                             # noqa: E731
    a = idx[k([f"q{j}" for j in range(9)])]
    assert a == {"kind": "replacement", "book_rank": 2, "tag": "mix_B", "term": True, "source_run": "mix_spare", "cell_fallback": False}
    b = idx[k(R[4])]                                                          # a spare used as a replacement reads as the replacement
    assert b["kind"] == "replacement" and b["tag"] == "mix_house" and b["term"] is False and b["cell_fallback"] is True
    assert idx[k(R[1])]["kind"] == "book"                                      # the removed book row keeps its own record
    assert T.label({"kind": "replacement", "tag": "mix_B", "term": True}) == "replacement:mix_B +cheap block"


def test_replace_file_is_unique(tmp_path):
    assert T.replace_file(tmp_path) is None
    (tmp_path / "paid-vetted-replaced").mkdir(); (tmp_path / "paid-vetted-replaced" / "replace.json").write_text("{}")
    assert T.replace_file(tmp_path) == tmp_path / "paid-vetted-replaced" / "replace.json"
    (tmp_path / "paid-vetted-replaced-fresh").mkdir(); (tmp_path / "paid-vetted-replaced-fresh" / "replace.json").write_text("{}")
    import pytest
    with pytest.raises(SystemExit):
        T.replace_file(tmp_path)
