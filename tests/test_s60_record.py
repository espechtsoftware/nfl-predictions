"""Study 60's reader: the frozen constants and printed level; the same-lineup rule and the pairs; P3's arm validity; the
position / p convention is P1's; the look readings; the ladder lines by role; the census reads no points; one scored week
on a synthetic field."""
import csv
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.stats import norm, t as student_t

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("s60_record", ROOT / "scripts" / "s60_record.py")
R = importlib.util.module_from_spec(spec); sys.modules["s60_record"] = R; spec.loader.exec_module(R)
P1 = R._load("p1_record")
PREREG = ROOT / "reports" / "2026-10-08-prereg-study60-cash-line.md"


def test_frozen_constants_and_the_printed_level():
    assert hashlib.sha256((ROOT / "scripts" / "p1_record.py").read_bytes()).hexdigest() == R.P1_SHA256
    assert R.LOOKS == (8, 12, 18) and R.MIN_WEEKS == 4 and R.DEAD_SHARE == 0.80 and R.PROSPECTIVE_FROM == 5
    assert R.ONE_SIDED == 0.95 and R.PROXY_P == 0.20 and R.ARMS == ("ENTERED", "MEAN_MILP", "PROPS_MILP")
    src = (ROOT / "scripts" / "s60_record.py").read_text()
    assert "the two-sided 90% t interval (each side a one-sided 95% bound)" in src
    assert "two-sided 90% t interval" in PREREG.read_text() and "one-sided 95% bound" in PREREG.read_text()


def _lu(*ids):
    return tuple(str(i) for i in ids)


def test_the_same_lineup_is_order_free():
    a = _lu(1, 2, 3, 4, 5, 6, 7, 8, 9)
    assert R.same(a, tuple(reversed(a))) and not R.same(a, _lu(1, 2, 3, 4, 5, 6, 7, 8, 10))
    b = _lu(11, 12, 13, 14, 15, 16, 17, 18, 19)
    assert R.same_pair((a, b), (tuple(reversed(b)), a)) and not R.same_pair((a, b), (a, a))


def _book(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]); w.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _arms(d: Path, books: dict, void=None, week_void=False, twin_ok=True):
    arms = {}
    for arm, rows in books.items():
        sha = _book(d / f"{arm}-1" / "book.csv", rows)
        arms[arm] = {"builds": [sha, sha if twin_ok else "x" * 64], "book": str(d / f"{arm}-1" / "book.csv"),
                     "void": (void or {}).get(arm)}
    (d / "arms.json").write_text(json.dumps({"arms": arms, "entered_book_sha256": arms["ENTERED"]["builds"][0],
                                             "week_void": week_void}))
    return d


L1, L2, L3, L4 = (_lu(*range(k, k + 9)) for k in (1, 11, 21, 31))


def test_mixed_takes_props_2_when_props_1_is_the_books_1(tmp_path):
    d = _arms(tmp_path / "a", {"ENTERED": [L1, L2], "MEAN_MILP": [L1, L3], "PROPS_MILP": [tuple(reversed(L1)), L4]})
    wr = R.week_rows(d)
    assert wr["same"] == {"D1": True, "D2": False, "FP": True}
    assert R.same_pair(wr["pairs"]["MIXED"], (L1, L4)) and R.same_pair(wr["pairs"]["R0 PAIR"], (L1, L2))
    d2 = _arms(tmp_path / "b", {"ENTERED": [L1, L2], "MEAN_MILP": [L1, L3], "PROPS_MILP": [L2, L4]})
    wr2 = R.week_rows(d2)                                   # PROPS #1 is the book's #2: MIXED = R0 PAIR
    assert wr2["same"]["D1"] is False and wr2["same"]["D2"] is True


def test_p3_validity_voids_only_what_it_should(tmp_path):
    books = {"ENTERED": [L1, L2], "MEAN_MILP": [L1, L3], "PROPS_MILP": [L3, L4]}
    wr = R.week_rows(_arms(tmp_path / "v", books, void={"MEAN_MILP": "failed to build"}))
    assert wr["valid"] == {"D1": True, "D2": True, "FP": False} and "MEAN_MILP" in wr["void"]
    wr = R.week_rows(_arms(tmp_path / "w", books, week_void=True))
    assert wr["valid"] == {"D1": False, "D2": False, "FP": False}
    d = _arms(tmp_path / "x", books)
    p = Path(json.loads((d / "arms.json").read_text())["arms"]["PROPS_MILP"]["book"]); p.write_text(p.read_text() + "\n")
    assert R.week_rows(d)["valid"]["D1"] is False            # the book read is not the recorded build
    assert R.week_rows(_arms(tmp_path / "y", books, twin_ok=False))["valid"]["D1"] is False


def test_position_and_p_are_p1s():
    rng = np.random.default_rng(60)
    o = np.sort(rng.integers(5000, 25000, 2000)).astype(np.int64)
    for pts in (4000, 12000, int(o[1000]), 26000):
        pos, p = R.position_and_p(pts, o)
        assert pos == 1 + int((o > pts).sum())                                    # ties take the better side
        assert math.isclose(norm.ppf(1 - p), float(P1.latent_z(np.asarray([pts]), o)[0]), rel_tol=0, abs_tol=1e-12)


def test_the_look_readings():
    half = lambda v: student_t.ppf(0.95, len(v) - 1) * np.std(v, ddof=1) / math.sqrt(len(v))
    assert R.read_look([0.5, 0.4, 0.6], [False] * 3, "single ticket")["reading"].startswith("too few valid weeks")
    v = [0.5, 0.4, 0.6, 0.55]
    r = R.read_look(v, [False] * 4, "single ticket")
    assert r["reading"] == "the props row is the better single ticket" and math.isclose(r["lo"], np.mean(v) - half(v))
    assert R.read_look([-x for x in v], [False] * 4, "second ticket")["reading"] == "the book's row is the better second ticket"
    assert R.read_look([0.5, -0.4, 0.6, -0.55], [False] * 4, "x")["reading"] == "no difference shown"
    assert R.read_look([0.0, 0.0, 0.0, 0.0, 0.3], [True] * 5, "x")["reading"].startswith("DEAD LEVER")
    assert R.read_look(v, [True, True, True, False], "x")["reading"] == "the props row is the better x"   # 75% is not > 80%
    assert R.looks_due([2, 3, 4, 5, 6, 7]) == [] and R.looks_due([5, 6, 7, 8]) == [8] and R.looks_due(list(range(5, 19))) == [8, 12, 18]


def test_the_line_by_role():
    assert R.line_of({"role": "gpp", "cash500_last_position": "95", "seat_last_position": "0"}) == 95
    assert R.line_of({"role": "big", "cash500_last_position": "40", "seat_last_position": "0"}) == 40
    assert R.line_of({"role": "sat", "cash500_last_position": "0", "seat_last_position": "2"}) == 2


def test_the_census_reads_no_points():
    src = (ROOT / "scripts" / "s60_record.py").read_text()
    for fn in ("def week_rows(", "def census(", "def arm_status(", "def book_rows("):
        body = src[src.index(fn):]; body = body[:body.index("\ndef ", 1)]
        for word in ("fpts", "lineup_points", "others_sorted", "latent_z", ".field", "score_week", "load_week"):
            assert word not in body, (fn, word)                # code that would read an outcome (the docstrings may say "points")


def test_one_scored_week_on_a_synthetic_field(tmp_path):
    d = _arms(tmp_path / "s", {"ENTERED": [L1, L2], "MEAN_MILP": [L1, L3], "PROPS_MILP": [L3, L4]})
    wr = R.week_rows(d)
    names = {i: f"P{i}" for lu in (L1, L2, L3, L4) for i in lu}
    each = {L1: 1000, L2: 1500, L3: 2000, L4: 500}                       # hundredths per player: L1 90.00, L2 135.00 ...
    fpts = {names[i]: each[lu] for lu in (L1, L2, L3, L4) for i in lu}
    milly = np.sort(np.arange(1, 20001) * 1).astype(np.int64)             # 0.01 .. 200.00 points
    small = np.sort(np.asarray([19000, 16000, 12000, 9000, 1000], np.int64))
    W = SimpleNamespace(week=9, name_of=names, fpts=fpts,
                        others_sorted=lambda cid: {"M": milly, "S": small}.get(cid, np.asarray([], np.int64)))
    M = SimpleNamespace(milly_cid=lambda W_: "M", lineup_points=lambda n, f, impute_missing=False: (sum(f.get(x, 0) for x in n), []))
    lad = [{"contest_id": "S", "role": "sat", "size": "6", "cash500_last_position": "0", "seat_last_position": "2"},
           {"contest_id": "Z", "role": "gpp", "size": "9", "cash500_last_position": "1", "seat_last_position": "0"}]
    s = R.score_week(M, P1, W, wr, lad)
    z = {k: float(P1.latent_z(np.asarray([v]), milly)[0]) for k, v in {"R0 #1": 9000, "R0 #2": 13500, "PROPS #1": 18000, "PROPS #2": 4500}.items()}
    assert math.isclose(s["d"]["D1"], z["PROPS #1"] - z["R0 #1"]) and s["d"]["FP"] == 0.0
    assert math.isclose(s["d"]["D2"], max(z["R0 #1"], z["PROPS #1"]) - max(z["R0 #1"], z["R0 #2"]))
    hit = s["ladder"][0]
    assert hit["position"]["PROPS #1"] == 2 and hit["hit"]["PROPS #1"]                       # one entry above: inside line 2
    assert hit["position"]["R0 #2"] == 3 and not hit["hit"]["R0 #2"]
    assert hit["position"]["R0 #1"] == 4 and not hit["hit"]["R0 #1"]                          # the tie at 90.00 is not above it
    assert s["ladder"][1]["no_field"]
    assert s["proxy_top20"]["PROPS #1"] and not s["proxy_top20"]["R0 #1"]
