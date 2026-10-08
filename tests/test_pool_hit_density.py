"""scripts/pool_hit_density.py (study row 69): the line rule against moneygate_score.place, parsing and the bootstrap."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return mod


PHD = _load("pool_hit_density")
MS = _load("moneygate_score")


def ladder(paid):
    return MS.Ladder(cash=np.full(paid, 10.0), ticket=np.zeros(paid))


@pytest.mark.parametrize("seats", [1, 2, 5, 9])
def test_line_is_exactly_the_place_boundary(seats):
    rng = np.random.default_rng(seats)
    others = np.sort(rng.integers(10000, 25000, 400).astype(np.int64))
    others = np.sort(np.concatenate([others, others[-12:]]))          # ties near the top
    line = PHD.contest_line(others, seats)
    lad = ladder(max(seats, 1))
    assert MS.place(np.array([line]), others, lad)["rank"][0] <= seats
    assert MS.place(np.array([line - 1]), others, lad)["rank"][0] > seats


def test_line_when_seats_exceed_the_field_and_bad_seats():
    assert PHD.contest_line(np.array([100, 200], np.int64), 5) == np.iinfo(np.int64).min
    with pytest.raises(ValueError):
        PHD.contest_line(np.array([1], np.int64), 0)


def test_implied_and_bootstrap():
    assert PHD.implied(0.0) == 0.0 and PHD.implied(1.0) == 1.0
    assert PHD.implied(0.01) == pytest.approx(1 - 0.99 ** 26)
    clears = np.array([1, 0, 0, 1, 0, 0, 0, 0], bool); clusters = np.array(list("aabbccdd"))
    lo, hi = PHD.cluster_boot(clears, clusters, b=500, seed=1)
    assert 0.0 <= lo <= clears.mean() <= hi <= 1.0
    assert PHD.cluster_boot(clears, clusters, b=500, seed=1) == (lo, hi)            # seeded: reproducible
    assert np.isnan(PHD.cluster_boot(np.array([], bool), np.array([]))[0])


def test_read_pool_maps_ids_and_counts_distinct_and_unmapped():
    ids = [f"P{i}" for i in range(9)]
    id_to_dk = {p: str(100 + i) for i, p in enumerate(ids)}
    cands = pd.DataFrame({"players": [",".join(ids), ",".join(reversed(ids)), ",".join(ids[:8] + ["UNKNOWN"])],
                          "tag": ["a", "b", "c"]})
    rows, tags, counts = PHD.read_pool(cands, id_to_dk)
    assert counts == {"pool_rows": 3, "pool_unmapped": 1, "pool_used": 2, "pool_distinct": 1}
    assert rows[0] == tuple(sorted(id_to_dk.values())) and tags == ["a", "b"]


def test_read_book_parses_ids_and_name_id_cells(tmp_path):
    p = tmp_path / "book.csv"
    p.write_text("QB,RB,RB,WR,WR,WR,TE,FLEX,DST\n1,2,3,4,5,6,7,8,9\nA (11),B (12),C (13),D (14),E (15),F (16),G (17),H (18),I (19)\n")
    assert PHD.read_book(p) == [tuple(sorted(str(i) for i in range(1, 10))), tuple(sorted(str(i) for i in range(11, 20)))]
    p.write_text("QB,RB\n1,2\n")
    with pytest.raises(SystemExit, match="has 2 players"):
        PHD.read_book(p)


def test_caveat_is_verbatim():
    assert PHD.CAVEAT == ("The T-70 pool is generated from OUR projections; the book's rows are solved on FP's (since W5). "
                          "d_pool measures our pool, not FP's book.")
