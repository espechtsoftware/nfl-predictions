"""scripts/p1_record.py (the frozen P1 prereg + amendment 1): the latent finish z, the contest classes, the unique-lineup
dedup, and the one-sided t bound. Offline."""
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm, t as student_t

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("p1_record", ROOT / "scripts" / "p1_record.py")
P1 = importlib.util.module_from_spec(spec); sys.modules["p1_record"] = P1; spec.loader.exec_module(P1)


def test_the_latent_z_is_the_10_05_normal_score_with_ties_to_the_better_side():
    field = np.array([100, 200, 300, 400], np.int64)
    z = P1.latent_z(np.array([350, 300, 450, 50]), field)
    # 350: one entry above -> position 2 -> p = 1.5 / 4; 300 ties the 300 -> also position 2; 450 -> position 1; 50 -> 5
    # N = the field with the row placed in it (5), so the row below everyone has p < 1 (no NaN)
    want = [norm.ppf(1 - 1.5 / 5), norm.ppf(1 - 1.5 / 5), norm.ppf(1 - 0.5 / 5), norm.ppf(1 - 4.5 / 5)]
    assert np.allclose(z, want) and np.isfinite(z).all()


def _det(kind, values, cap):
    return {"maximumEntries": cap, "payoutSummary": [{"minPosition": i + 1, "maxPosition": i + 1,
            "tierPayoutDescriptions": {kind: "x"}, "payoutDescriptions": [{"value": v}]} for i, v in enumerate(values)]}


def test_the_frozen_classes():
    assert P1.p1_class("NFL $2.75M Fantasy Football Millionaire [$1M to 1st]", _det("Cash", [1e6, 1e5], 161764)) == "Millionaire"
    assert P1.p1_class("Sat", _det("Ticket", [20, 20], 594)) == "flat ticket <= 600"
    assert P1.p1_class("Sat", _det("Ticket", [20, 20], 2378)) == "flat ticket > 600"
    assert P1.p1_class("GPP", _det("Cash", [1000, 10], 50000)) == "large cash GPP"
    q = _det("Cash", [500, 10], 5000); q["payoutSummary"][0]["tierPayoutDescriptions"] = {"Ticket": "seat"}
    assert P1.p1_class("FFWC", q) == "qualifier"
    assert P1.p1_class("Small", _det("Cash", [100, 10], 500)) == "everything else"
    assert set(P1.BREAK_EVEN) == {"flat ticket <= 600", "flat ticket > 600", "Millionaire", "large cash GPP", "qualifier"}


def test_unique_lineups_per_class_and_the_t_bound():
    a, b = frozenset({"x", "y"}), frozenset({"x", "z"})
    rows = [{"class": "c1", "lineup": a, "z": 0.1}, {"class": "c1", "lineup": a, "z": 0.1}, {"class": "c1", "lineup": b, "z": 0.3},
            {"class": "c2", "lineup": a, "z": 0.1}]
    by = P1.class_rows(rows)
    assert len(by["c1"]) == 2 and len(by["c2"]) == 1                 # a counts once in c1 and once in c2
    v = [0.1, 0.2, 0.3, 0.4]
    want = 0.25 - student_t.ppf(0.95, 3) * np.std(v, ddof=1) / math.sqrt(4)
    assert abs(P1.t_lower_bound(v) - want) < 1e-12 and P1.t_lower_bound([0.2]) is None
