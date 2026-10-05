"""Week-5 money gate harness (scripts/moneygate_build.py, scripts/moneygate_score.py) on SYNTHETIC fixtures only:
fake fields, fake points, fake ladders. No real outcome is read anywhere in this module."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import moneygate_build as MB  # noqa: E402
import moneygate_score as MS  # noqa: E402


# ------------------------------------------------------------------------------------------------- fixtures
def details(n_max: int, tiers: list[tuple[int, int, str, float]], fee: float = 1.0, name: str = "NFL Synthetic GPP") -> dict:
    return {"name": name, "max": n_max, "fee": fee, "payoutSummary": [
        {"minPosition": lo, "maxPosition": hi, "tierPayoutDescriptions": {kind: "x"},
         "payoutDescriptions": [{"value": v, "quantity": 1}]} for lo, hi, kind, v in tiers]}


def cr(cid, payouts, pct, rows, fee=1.0, tickets=None, cls="Cash GPP", points=None):
    payouts = np.asarray(payouts, float)
    return MS.ContestResult(cid, cls, len(payouts), fee * len(payouts), payouts,
                            np.zeros(len(payouts)) if tickets is None else np.asarray(tickets, float), np.asarray(pct, float),
                            np.asarray(points if points is not None else [10000] * len(payouts), np.int64),
                            frozenset(frozenset({r}) for r in rows))


# --------------------------------------------------------------------------------------------------- ladder
def test_ladder_cash_and_ticket_and_refusal():
    lad = MS.Ladder.from_details(details(100, [(1, 1, "Cash", 50.0), (2, 3, "Ticket", 20.0)]))
    assert lad.paid == 3 and lad.cash.tolist() == [50, 0, 0] and lad.ticket.tolist() == [0, 20, 20]
    bad = details(10, [(1, 1, "Cash", 5.0)]); bad["payoutSummary"][0]["tierPayoutDescriptions"] = {"Cash": "a", "Ticket": "b"}
    with pytest.raises(ValueError):
        MS.Ladder.from_details(bad)


def test_place_ranks_ties_split_and_percentile():
    lad = MS.Ladder.from_details(details(10, [(1, 1, "Cash", 100.0), (2, 2, "Cash", 50.0), (3, 3, "Ticket", 20.0)]))
    others = np.sort(np.array([5000, 9000, 12000, 12000], np.int64))
    r = MS.place(np.array([13000, 12000, 1000]), others, lad)
    # 130.00 is 1st; 120.00 ties two field entries at 2nd -> positions 2,3,4 split (50 + 20 + 0) / 3
    assert r["rank"].tolist() == [1, 2, 7]          # 4 field + 2 own entries above 10.00
    assert r["ties"].tolist() == [1, 3, 1]
    assert r["cash"][0] == 100 and r["cash"][1] == pytest.approx(50 / 3) and r["ticket"][1] == pytest.approx(20 / 3)
    assert r["payout"][2] == 0
    assert r["pct"].tolist() == pytest.approx([100.0, 75.0, 0.0])        # 2 below + half of 2 ties = 3 of 4


def test_place_own_entries_tie_each_other():
    lad = MS.Ladder.from_details(details(10, [(1, 1, "Cash", 10.0)]))
    r = MS.place(np.array([500, 500]), np.array([100], np.int64), lad)
    assert r["rank"].tolist() == [1, 1] and r["payout"].tolist() == [5.0, 5.0]


def test_lineup_points_refuses_missing_unless_imputed():
    fp = {"A": 1000, "B": 250}
    assert MS.lineup_points(["A", "B"], fp) == (1250, [])
    with pytest.raises(KeyError):
        MS.lineup_points(["A", "C"], fp)
    assert MS.lineup_points(["A", "C"], fp, impute_missing=True) == (1000, ["C"])


def test_fpts_table_flags_ambiguous_names():
    p = pd.DataFrame({"name": ["X", "X", "Y", "Y"], "fpts": [10.0, 10.0, 3.5, 4.5]})
    fp, amb = MS.fpts_table(p)
    assert fp == {"X": 1000} and amb == {"Y"}


def test_parse_lineup_and_class():
    assert MS.parse_lineup("DST Panthers  FLEX Layne Pryor QB Tyrod Taylor RB A B") == ["Panthers", "Layne Pryor", "Tyrod Taylor", "A B"]
    assert MS.contest_class("NFL $2.75M Fantasy Football Millionaire [$1M to 1st]") == "Millionaire"
    assert MS.contest_class("NFL SUPERSat to $20 NFL Fantasy Football Millionaire [25x]") == "SuperSat 25x"
    assert MS.contest_class("NFL Satellite to $20 NFL Fantasy Football Millionaire") == "Satellite 1-ticket"
    assert MS.contest_class("NFL $400K Play-Action [20 Entry Max]") == "Cash GPP"


# ------------------------------------------------------------------------------------------------ statistics
def test_binomial_sign_test_exact():
    assert MS.binom_two_sided(4, 4) == pytest.approx(0.125)
    assert MS.binom_two_sided(3, 3) == pytest.approx(0.25)
    assert MS.binom_two_sided(5, 10) == pytest.approx(1.0)
    assert MS.binom_two_sided(0, 0) == 1.0


def test_clusters_link_contests_sharing_rows():
    cl = MS.clusters({"a": {1, 2}, "b": {2, 3}, "c": {4}, "d": {3}})
    assert cl == [["a", "b", "d"], ["c"]]


def week_res(diff: float, n_contests: int = 6, shared: bool = False, base_pct: float = 50.0, payout: float = 0.0):
    """A1 and X results for one week; X's mean finish pct is A1's + diff in every contest."""
    A, X = {}, {}
    for k in range(n_contests):
        rowsA = [f"a{k}", "shared"] if shared else [f"a{k}"]
        rowsX = [f"x{k}", "shared"] if shared else [f"x{k}"]
        A[str(k)] = cr(str(k), [payout, 0.0], [base_pct, base_pct], rowsA)
        X[str(k)] = cr(str(k), [payout, 0.0], [base_pct + diff, base_pct + diff], rowsX)
    return A, X


def test_condition_c_uses_weeks_as_units_with_the_exact_sign_test():
    """Addendum 2.1: weeks are the units whatever the clusters; 3 units can never reach p < 0.20 (min p 0.25), and 4 of 4
    favouring X gives 0.125 (passes); clusters are reported only."""
    A, X = {}, {}
    for w in (1, 2, 3):
        A[w], X[w] = week_res(+3.0, n_contests=4)
    c = MS.condition_c(X, A, (1, 2, 3))
    assert c["unit"] == "weeks" and c["units"] == 3 and c["favour_X"] == 3
    assert c["p_two_sided"] == 0.25 and c["min_attainable_p"] == 0.25 and not c["can_license"] and not c["pass"]
    assert c["clusters_per_week"] == {1: 4, 2: 4, 3: 4}
    assert c["contest_level"]["label"].startswith("ANTI-CONSERVATIVE")
    for w in (1, 2, 3, 4):
        A[w], X[w] = week_res(+3.0, n_contests=4, shared=True)
    c = MS.condition_c(X, A, (1, 2, 3, 4))
    assert c["units"] == 4 and abs(c["p_two_sided"] - 0.125) < 1e-12 and c["can_license"] and c["pass"]
    A[4], X[4] = week_res(-3.0, n_contests=4)
    c = MS.condition_c(X, A, (1, 2, 3, 4))
    assert c["favour_X"] == 3 and c["favour_A1"] == 1 and not c["pass"]


def test_a4_condition_b_is_read_on_weeks_3_and_4_only():
    assert MS.RULE["arms"]["A4"]["b_weeks"] == (3, 4) and MS.RULE["arms"]["A4"]["b_min"] == 2
    assert "b_weeks" not in MS.RULE["arms"]["A2"] and MS.RULE["arms"]["A2"]["b_min"] == 2


def make_res(diffs: dict[str, float], weeks=(1, 2, 3, 4), big: dict | None = None):
    """res[arm][week] with A1 at pct 50 and arm X at 50 + diffs[X]; payouts 1.0 per contest's first entry unless big."""
    res = {a: {} for a in MS.ARMS}
    for w in weeks:
        for a in MS.ARMS:
            d = 0.0 if a == "A1" else diffs.get(a, 0.0)
            R = {}
            for k in range(6):
                pay = 1.0 + (0.5 if d > 0 else (-0.5 if d < 0 else 0.0))
                if big and big.get("arm") == a and big.get("week") == w and k == 0:
                    pay = big["payout"]
                R[str(k)] = cr(str(k), [pay, 0.0], [50 + d, 50 + d], [f"{a}{w}{k}"], points=[10000 + 100 * d, 10000])
            res[a][w] = R
    return res


def fake_m2(weeks=(1, 2, 3, 4), cash_level: int = 0):
    m2 = pd.DataFrame({**{f"cash_{k}": np.full(1000, cash_level) for k in range(6)},
                       **{f"sum_{k}": np.full(1000, 150.0) for k in range(6)}})
    return {w: (m2, {str(k): 2 for k in range(6)}) for w in weeks}


def test_rule_recommends_simplest_qualifier_and_respects_weeks():
    res = make_res({"A2": 4.0, "A3": 4.0, "A4": -4.0})
    ev = MS.evaluate_rule(res, fake_m2())
    assert ev["arms"]["A2"]["weeks"] == [1, 2, 3] and ev["arms"]["A4"]["weeks"] == [1, 2, 3, 4]
    # Addendum 2.1: A2/A3 have 3 week-units (min p 0.25) -> can never qualify, however good; A4 is worse here
    assert not ev["arms"]["A2"]["qualifies"] and not ev["arms"]["A2"]["c"]["can_license"]
    assert not ev["arms"]["A3"]["qualifies"] and not ev["arms"]["A4"]["qualifies"]
    assert ev["recommend"] is None                                    # Addendum 2.4: no default arm
    res = make_res({"A2": 4.0, "A3": 4.0, "A4": 4.0})               # an A4 better in all 4 weeks: 4/4, p = 0.125
    ev = MS.evaluate_rule(res, fake_m2())
    assert ev["arms"]["A4"]["qualifies"] and ev["recommend"] == "A4"


def test_rule_ex_largest_payout_guard():
    # A2 is better only through one huge payout: (a) as-is passes, ex-largest fails -> not a qualifier
    res = make_res({"A2": 0.0}, big={"arm": "A2", "week": 1, "payout": 1000.0})
    for w in (1, 2, 3):                                            # A2 slightly ahead on finish pct so (b),(c) can pass
        for k, r in res["A2"][w].items():
            r.pct[:] = 53.0
            if not (w == 1 and k == "0"):
                r.payouts[0] = 0.9                                 # but behind A1 on payouts outside the one big one
    ev = MS.evaluate_rule(res, fake_m2())
    a2 = ev["arms"]["A2"]
    assert a2["a_as_is"] and not a2["a_ex_largest"] and not a2["qualifies"]


def test_rule_m2_condition():
    res = make_res({"A2": 4.0})
    ev = MS.evaluate_rule(res, fake_m2(cash_level=5))               # M2 books cash 5 per contest: A2 far below
    assert ev["arms"]["A2"]["d_m2_pct"] < 50 and not ev["arms"]["A2"]["qualifies"]


def test_bootstrap_and_permutation_rate_run_and_are_seeded():
    res = make_res({"A2": 1.0, "A3": -1.0, "A4": 0.0})
    b1 = MS.bootstrap(res, ("A1", "A2"), (1, 2, 3), 200, seed=3)
    b2 = MS.bootstrap(res, ("A1", "A2"), (1, 2, 3), 200, seed=3)
    assert b1.shape == (200, 2) and np.array_equal(b1, b2)
    be = MS.bootstrap(res, ("A1",), (1, 2, 3, 4), 50, seed=3, ex_largest=True)
    assert np.all(be <= MS.bootstrap(res, ("A1",), (1, 2, 3, 4), 50, seed=3) + 1e-12)
    fq = MS.false_qualifier_rate(res, fake_m2(), 30, seed=4)
    assert fq["permutations"] == 30 and 0 <= fq["any"] <= 1


def test_permute_week_keeps_contests_together_within_clusters():
    res = make_res({"A2": 2.0, "A3": 1.0, "A4": -1.0}, weeks=(1,))
    rng = np.random.default_rng(0)
    pw = MS.permute_week({a: res[a][1] for a in MS.ARMS}, rng)
    for a in MS.ARMS:
        assert set(pw[a]) == set(res[a][1])
        assert {id(v) for v in pw[a].values()} <= {id(v) for b in MS.ARMS for v in res[b][1].values()}


def test_rollback_trigger():
    x = {"c": cr("c", [0, 0], [40, 40], ["x"])}; a1 = {"c": cr("c", [0, 0], [46, 46], ["a"])}
    r = MS.rollback_check(x, a1, x_m2_pct=60)
    assert r["test_ii"] and r["end_trial"] and not r["test_i"]
    assert not MS.rollback_check(x, {"c": cr("c", [0, 0], [44, 44], ["a"])}, 55)["end_trial"]
    assert MS.rollback_check(x, {"c": cr("c", [0, 0], [40, 40], ["a"])}, 49.9)["end_trial"]


# ------------------------------------------------------------------------------------------------ A0 gate
def synthetic_reconcile_week(history_payouts=None):
    """One contest: 6 field entries, 2 of them ours; a ladder paying 1st 30 cash, 2nd-3rd a 10 ticket."""
    fpts = {n: v for n, v in zip("ABCDEFGHIJ", [2000, 1500, 1200, 900, 800, 700, 600, 500, 400, 300])}
    lineups = {"e1": ("A", "B"), "e2": ("C", "D"), "o1": ("E", "F"), "o2": ("G", "H"), "o3": ("I", "J"), "o4": ("A", "J")}
    pts = {k: sum(fpts[n] for n in v) for k, v in lineups.items()}
    order = sorted(pts, key=lambda k: -pts[k])
    rank = {k: 1 + sum(pts[j] > pts[k] for j in pts) for k in pts}
    field = pd.DataFrame({"contest_id": "c1", "entry_id": list(lineups), "rank": [rank[k] for k in lineups],
                          "points": [pts[k] for k in lineups], "names": [tuple(sorted(v)) for v in lineups.values()]})
    det = {"c1": details(6, [(1, 1, "Cash", 30.0), (2, 3, "Ticket", 10.0)], fee=2.0)}
    lad = MS.Ladder.from_details(det["c1"])
    pay = {k: (lad.cash[rank[k] - 1] if rank[k] <= 3 else 0.0, lad.ticket[rank[k] - 1] if rank[k] <= 3 else 0.0) for k in ("e1", "e2")}
    if history_payouts:
        pay.update(history_payouts)
    hist = pd.DataFrame({"Contest_Key": "c1", "Entry_Key": ["e1", "e2"], "Place": [str(rank["e1"]), str(rank["e2"])],
                         "Points": [f"{pts['e1'] / 100:.2f}", f"{pts['e2'] / 100:.2f}"],
                         "Winnings_Non_Ticket": [f"${pay['e1'][0]:.2f}", f"${pay['e2'][0]:.2f}"],
                         "Winnings_Ticket": [f"${pay['e1'][1]:.2f}", f"${pay['e2'][1]:.2f}"], "Entry_Fee": ["$2.00", "$2.00"]})
    W = MS.Week(9, [{"contest_id": "c1", "name": "x", "entries": 2}], det, fpts, set(), field, {"e1", "e2"}, hist, {})
    return W, order


def test_reconcile_exact_match_passes():
    W, _ = synthetic_reconcile_week()
    s, rows, bad = MS.reconcile_week(W, {})
    assert not bad and s["exact_match"] and s["entries_matching"] == 2 and s["total_winnings_exact"]


def test_reconcile_mismatch_is_named():
    W, _ = synthetic_reconcile_week(history_payouts={"e1": (31.0, 0.0)})
    s, rows, bad = MS.reconcile_week(W, {})
    assert bad and "contest c1" in bad[0] and not s["exact_match"]


def test_reconcile_exclusion_is_recorded():
    W, _ = synthetic_reconcile_week()
    s, rows, bad = MS.reconcile_week(W, {"c1": "hand entry"})
    assert s["excluded"] == {"c1": "hand entry"} and not rows and not bad


def test_score_book_uses_layout_and_field_without_our_entries():
    W, _ = synthetic_reconcile_week()
    W.name_of = {str(i): n for i, n in enumerate("ABCDEFGHIJ")}
    layout = {"contests": {"c1": {"lineups": [["0", "1"], ["8", "9"]]}}}   # A+B (35.00) and I+J (7.00)
    R, miss = MS.score_book(W, layout)
    r = R["c1"]
    # field without ours: o1 15.00, o2 11.00, o3 7.00, o4 23.00 -> A+B is 1st (30 cash); I+J ties o3 for 4th (no prize)
    assert not miss and r.payouts.tolist() == [30.0, 0.0] and r.cashes == 1 and r.fee == 4.0
    assert r.pct.tolist() == pytest.approx([100.0, 12.5])


# ------------------------------------------------------------------------------------------------ build side
def test_arm_flags_are_the_frozen_arms():
    a1 = MB.arm_flags("A1", "own.csv"); a4 = MB.arm_flags("A4", "own.csv")
    assert a1[a1.index("--main") + 1] == "pmo_x50" and a1[a1.index("--main-cap-share") + 1] == "0.5"
    assert a1[a1.index("--main-own-tilt") + 1] == "0.20" and "--main-own-tilt" not in a4
    assert a4[a4.index("--sleeve-own-source") + 1] == "own.csv"           # A4 keeps the field sleeve
    a2 = MB.arm_flags("A2", "own.csv"); a3 = MB.arm_flags("A3", "own.csv")
    assert a2[a2.index("--main") + 1] == "mean" and "--main-own-tilt" not in a2
    assert a3[a3.index("--main-cap-share") + 1] == "0.30" and a3[a3.index("--main-own-tilt") + 1] == "0.20"
    # no point-in-time ownership file: no term, the projection sleeve, and A1 == A4 by construction
    assert MB.arm_flags("A1", None) == MB.arm_flags("A4", None)
    assert MB.arm_flags("A1", None)[-2:] == ["--sleeve-source", "mean"]
    with pytest.raises(ValueError):
        MB.arm_flags("A9", None)


def test_route_contests_forces_millionaire_tail_holds_and_deep_lines():
    raw = [{"name": "sat", "contest_id": 1, "entries": 3, "keep": 3, "ranks": [1, 2, 3]},
           {"name": "milly", "contest_id": 2, "entries": 1, "keep": 1},
           {"name": "deep", "contest_id": 3, "entries": 2, "keep": 2},
           {"name": "held", "contest_id": 4, "entries": 4, "keep": 4}]
    det = {"1": details(100, [(1, 20, "Ticket", 20.0)]), "2": details(160000, [(1, 37000, "Cash", 1.0)]),
           "3": details(72, [(1, 1, "Ticket", 555.0)]), "4": details(2378, [(1, 25, "Ticket", 20.0)])}
    out, lines = MB.route_contests(raw, det, "2", [2378, 999])
    by = {c["contest_id"]: c for c in out}
    assert by["2"]["track"] == "tail" and by["3"]["track"] == "tail" and by["4"]["track"] == "mean" and by["1"]["track"] == "mean"
    assert "ranks" not in by["1"]                                          # operator pins of an old week are stripped
    assert [c["contest_id"] for c in out if c["track"] == "tail"] == ["2", "3"]   # forced first, then by depth
    K, T = MB.book_size(out)
    assert T == 3 and K >= 4


def test_dk_valid_independent_check():
    fr = pd.DataFrame({"dk_player_id": [str(i) for i in range(1, 10)],
                       "pos": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"],
                       "salary": [5500] * 8 + [3000], "game_id": ["g1"] * 5 + ["g2"] * 4})
    ok = [str(i) for i in range(1, 10)]
    assert MB.dk_valid(ok, fr) == []
    assert any("salary" in e for e in MB.dk_valid(ok, fr.assign(salary=7000)))
    swapped = ok[:]; swapped[0], swapped[1] = swapped[1], swapped[0]
    assert MB.dk_valid(swapped, fr)
