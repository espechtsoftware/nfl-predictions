"""The calibration script's vectorised per-sim placement equals the money gate's place() sim by sim (offline, synthetic)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import calibration_w1_4 as C  # noqa: E402
import moneygate_score as MS  # noqa: E402


def _ladder() -> "MS.Ladder":
    cash = np.array([600.0, 300.0, 100.0, 40.0, 20.0, 10.0, 10.0, 5.0])
    ticket = np.zeros(8); ticket[[3, 4]] = [350.0, 0.0]
    return MS.Ladder(cash, ticket)


def _setup(seed: int, n_players=14, S=9, n_field=40, m=4, dupes=True):
    rng = np.random.default_rng(seed)
    bank = np.round(rng.gamma(2.0, 6.0, size=(n_players, S)), 1).astype(np.float32)
    bank[3, ::2] = 0.0                                        # a zero-mass player (the PIT-at-zero lesson)
    field = np.array([rng.choice(n_players, 9, replace=False) for _ in range(n_field)])
    mine = np.array([rng.choice(n_players, 9, replace=False) for _ in range(m)])
    if dupes:
        field[:5] = field[0]                                  # duplicate rosters tie exactly
        mine[1] = field[0]                                    # one of ours ties with them
        mine[3] = mine[2]                                     # two of ours tie with each other
    return bank, field, mine


def _brute(bank, field, mine, lad, pct_real):
    S = bank.shape[1]
    out = {b: np.zeros((len(mine), S), np.uint8) for b in C.BUCKETS}
    lt = np.zeros(len(mine)); eq = np.zeros(len(mine))
    n_total = len(field) + len(mine)
    for s in range(S):
        f = np.rint(bank[field, s].astype(np.float64).sum(axis=1) * 100).astype(np.int64)
        e = np.rint(bank[mine, s].astype(np.float64).sum(axis=1) * 100).astype(np.int64)
        r = MS.place(e, np.sort(f), lad)
        bk = C.buckets(r["rank"], r["cash"], r["ticket"], n_total)
        for b in C.BUCKETS:
            out[b][:, s] = bk[b]
        lt += r["pct"] < pct_real - 1e-9; eq += np.abs(r["pct"] - pct_real) <= 1e-9
    return out, (lt + 0.5 * eq) / S


def _run(seed, chunk, dupes=True):
    bank, field, mine = _setup(seed, dupes=dupes)
    lad = _ladder()
    pct_real = np.linspace(5, 95, len(mine))
    xf, xm = C.incidence(field, bank.shape[0]), C.incidence(mine, bank.shape[0])
    got, pit = C.model_contest(bank, xf, xm, 1.0, len(field), len(field) + len(mine), lad, pct_real, chunk)
    want, wpit = _brute(bank, field, mine, lad, pct_real)
    return got, pit, want, wpit


def test_vectorised_placement_equals_place_with_ties():
    for seed in range(6):
        for chunk in (1, 4, 9):
            got, pit, want, wpit = _run(seed, chunk)
            for b in C.BUCKETS:
                assert np.array_equal(got[b], want[b]), (seed, chunk, b)
            assert np.allclose(pit, wpit), (seed, chunk)


def test_buckets_definitions():
    rank = np.array([1, 2, 10, 11, 100, 101])
    cash = np.array([0, 499.99, 500, 0, 0, 0.0]); ticket = np.array([0, 0, 0, 299.99, 300, 0.0])
    b = C.buckets(rank, cash, ticket, 1000)
    assert b["top1"].tolist() == [True, True, True, False, False, False]
    assert b["top10"].tolist() == [True, True, True, True, True, False]
    assert b["cash"].tolist() == [False, True, True, True, True, False]
    assert b["big"].tolist() == [False, False, True, False, True, False]


def test_tiny_contest_top_cut_is_at_least_rank_one():
    assert C.cut(np.array([1, 2]), 50, 0.01).tolist() == [True, False]


def test_negative_lineup_totals_stay_in_their_column():
    bank, field, mine = _setup(11, dupes=False)
    bank = bank - 30.0                                        # every lineup total negative
    lad = _ladder(); pct_real = np.full(len(mine), 50.0)
    xf, xm = C.incidence(field, bank.shape[0]), C.incidence(mine, bank.shape[0])
    got, pit = C.model_contest(bank, xf, xm, 1.0, len(field), len(field) + len(mine), lad, pct_real, 3)
    want, wpit = _brute(bank, field, mine, lad, pct_real)
    for b in C.BUCKETS:
        assert np.array_equal(got[b], want[b])
    assert np.allclose(pit, wpit)


def test_scaled_sample_equals_place_on_the_full_field():
    """Review D: the field doubled (every roster twice) and half of it scored at scale 2 must equal place() on the full
    doubled field, ties included."""
    for seed in range(4):
        bank, field, mine = _setup(seed)
        lad = _ladder(); pct_real = np.linspace(10, 90, len(mine))
        full = np.concatenate([field, field])
        xf, xm = C.incidence(field, bank.shape[0]), C.incidence(mine, bank.shape[0])
        got, pit = C.model_contest(bank, xf, xm, 2.0, len(full), len(full) + len(mine), lad, pct_real, 4)
        want, wpit = _brute(bank, full, mine, lad, pct_real)
        for b in C.BUCKETS:
            assert np.array_equal(got[b], want[b]), (seed, b)
        assert np.allclose(pit, wpit), seed


def test_alignment_check_fails_closed_on_permuted_banks():
    import pandas as pd
    import pytest
    rng = np.random.default_rng(3)
    proj = rng.uniform(2, 25, 60)
    inc = (proj[:, None] + rng.normal(0, 6, (60, 4000))).astype(np.float32)
    inc += (proj - inc.mean(axis=1))[:, None].astype(np.float32)        # row means equal the projection
    hs = (proj[:, None] * 1.1 + rng.normal(0, 6, (60, 4000))).astype(np.float32)
    fr = pd.DataFrame({"mean_projection": proj})
    C.check_alignment(1, fr, {"incumbent": inc, "hsim": hs})
    with pytest.raises(SystemExit):
        C.check_alignment(1, fr, {"incumbent": inc[::-1], "hsim": hs})
    with pytest.raises(SystemExit):
        C.check_alignment(1, fr, {"incumbent": inc, "hsim": hs[rng.permutation(60)]})


def test_empty_lineups_stay_in_the_field_at_zero_and_unknown_names_are_flagged():
    row_of = {f"P{i}": i for i in range(12)}
    rows = C.roster_rows([("",), tuple(f"P{i}" for i in range(9)), tuple(["Nobody"] + [f"P{i}" for i in range(8)])], row_of)
    assert (rows[0] == C.EMPTY).all()
    assert (rows[1] >= 0).all()
    assert rows[2, 0] == C.UNKNOWN
    known = (rows != C.UNKNOWN).all(axis=1)
    assert known.tolist() == [True, True, False]
    x = C.incidence(rows[known], 12)
    assert x[0].sum() == 0 and x[1].sum() == 9
