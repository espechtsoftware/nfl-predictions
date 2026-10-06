#!/usr/bin/env python3
"""DESCRIPTIVE money read of any built arms (the operator's 10-06 expedited plan: "what would the package have paid"),
through the money gate's UNCHANGED scorer (scripts/moneygate_score.py: names -> DK points, placement in the real field
with ours removed, DraftKings' tie split, ladders, tickets at face). Nothing decides on it.

For each week and arm (A0 = what was entered, from the reconcile's own rows; A1-A4 and any PKG<ms>-<fill> arm with a
layout.json): fees, winnings, the return multiple as is and without the arm's single largest payout, cashes, the mean
finish percentile, and the operator's utility REALIZED: big wins = entries paying cash >= $500 or a ticket worth >= $300
(his 10-05 rule: any prize but a $20 Millionaire ticket counts; $125-and-under tickets are not big), the contests with one,
and whether the week had at least one. Three weeks of dollars are mostly one payout: read the ex-largest column.

PKG arms are TRANSLATIONS of the Week-5 package (the QB cap scaled by share from K 26; the week's own T and contest mix,
not Rev3): say so beside every number. Ratios and counts go to ~/moneygate/results/describe.json; dollars only to
~/private/moneygate/describe_dollars.json.

    python scripts/moneygate_describe.py --weeks 2,3,4 [--arms A1,A2,A3,A4,PKG5-group,...]
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("moneygate_score", HERE / "moneygate_score.py")
MS = importlib.util.module_from_spec(spec); sys.modules["moneygate_score"] = MS; spec.loader.exec_module(MS)

BIG_CASH, BIG_TICKET = 500.0, 300.0


def big_flags(cash: np.ndarray, ticket: np.ndarray) -> np.ndarray:
    return (np.asarray(cash) >= BIG_CASH - 1e-9) | (np.asarray(ticket) >= BIG_TICKET - 1e-9)


def summarize(entries: list[dict]) -> tuple[dict, dict]:
    """entries: {contest_id, fee, cash, ticket, pct?} per entry -> (public ratios/counts, private dollars)."""
    fee = sum(e["fee"] for e in entries); cash = np.array([e["cash"] for e in entries]); tick = np.array([e["ticket"] for e in entries])
    pay = cash + tick
    big = big_flags(cash, tick)
    largest = float(pay.max()) if len(pay) else 0.0
    pct = [e["pct"] for e in entries if e.get("pct") is not None]
    pub = {"entries": len(entries), "multiple": round(float(pay.sum()) / fee, 4) if fee else None,
           "multiple_ex_largest": round(float(pay.sum() - largest) / fee, 4) if fee else None,
           "cashes": int((pay > 0).sum()), "big_wins": int(big.sum()),
           "contests_with_big_win": len({e["contest_id"] for e, b in zip(entries, big) if b}),
           "week_has_big_win": bool(big.any()), "mean_finish_pct": round(float(np.mean(pct)), 2) if pct else None}
    priv = {"fees": round(fee, 2), "winnings": round(float(pay.sum()), 2), "largest_payout": round(largest, 2),
            "cash": round(float(cash.sum()), 2), "tickets_face": round(float(tick.sum()), 2)}
    return pub, priv


def a0_entries(w: int) -> list[dict]:
    rows = [r for r in csv.DictReader(open(MS.PRIVATE / "reconcile_entries.csv")) if int(r["week"]) == w]
    return [{"contest_id": r["contest_id"], "fee": float(r["fee_calc"]), "cash": float(r["cash_calc"]),
             "ticket": float(r["ticket_calc"]), "pct": None} for r in rows]


def arm_entries(W, layout: dict) -> list[dict]:
    R, missing = MS.score_book(W, layout)
    if missing:
        raise SystemExit(f"W{W.week}: players without DK points {missing[:5]} (the scorer refuses to impute here)")
    out = []
    for cid, r in R.items():
        for i in range(r.n):
            out.append({"contest_id": cid, "fee": r.fee / r.n, "cash": float(r.payouts[i] - r.tickets[i]),
                        "ticket": float(r.tickets[i]), "pct": float(r.pct[i])})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--weeks", default="2,3,4"); ap.add_argument("--arms", default=None)
    a = ap.parse_args(argv)
    weeks = [int(x) for x in a.weeks.split(",") if x.strip()]
    rec = json.loads(MS.receipt_path().read_text())
    MS.require_reconcile(rec["weeks"])                     # the known-answer gate passed for THIS scorer and data
    cfg = MS.load_config()
    pub, priv = {"note": "DESCRIPTIVE ONLY; nothing decides on it. PKG arms translate the Week-5 package to each week's real "
                         "contests: the QB cap scaled by share from K 26 (studied at K 26 only); the week's own tail sleeve and "
                         "contest mix, not Rev3. Big win = cash >= $500 or a ticket worth >= $300 (realized).",
                 "scorer_sha256": MS.sha256(MS.SCORER), "weeks": {}}, {"weeks": {}}
    for w in weeks:
        W = MS.load_week(cfg, w)
        d = MS.BOOKS / f"w{w}"
        arms = [x.strip() for x in a.arms.split(",")] if a.arms else sorted(p.name for p in d.iterdir() if (p / "layout.json").is_file())
        pw, vw = {}, {}
        pw["A0"], vw["A0"] = summarize(a0_entries(w))
        for arm in arms:
            lay = d / arm / "layout.json"
            if not lay.is_file():
                pw[arm] = {"missing": "no layout.json"}; continue
            layout = json.loads(lay.read_text())
            pw[arm], vw[arm] = summarize(arm_entries(W, layout))
            pw[arm]["book_sha256"] = layout.get("book_sha256")
        pub["weeks"][w], priv["weeks"][w] = pw, vw
    MS.PUBLIC.mkdir(parents=True, exist_ok=True); MS.PRIVATE.mkdir(parents=True, exist_ok=True)
    (MS.PUBLIC / "describe.json").write_text(json.dumps(pub, indent=1) + "\n")
    (MS.PRIVATE / "describe_dollars.json").write_text(json.dumps(priv, indent=1) + "\n")
    cols = ("multiple", "multiple_ex_largest", "cashes", "big_wins", "contests_with_big_win", "week_has_big_win", "mean_finish_pct")
    print(pub["note"])
    for w, pw in pub["weeks"].items():
        print(f"\nWeek {w}")
        print("  arm".ljust(16) + "".join(c[:14].rjust(15) for c in cols))
        for arm, v in pw.items():
            print(f"  {arm}".ljust(16) + "".join(str(v.get(c, "-"))[:14].rjust(15) for c in cols))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
