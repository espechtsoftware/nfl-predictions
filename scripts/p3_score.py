#!/usr/bin/env python3
"""P3's scorer (the frozen prereg reports/2026-10-07-prereg-p3-simple-baseline.md §3-§5), one week, after settlement.

For each arm built by scripts/p3_arms.sh (its arms.json): the arm's book.csv dealt into the week's REAL contests by the
money gate's head layout (moneygate_build.layout_book: enter_layout write + check, the plan's pins honoured), each dealt
entry's real DK points (moneygate_score's week tables: canonical names, hundredths; a name nobody in the field rostered
scores 0 and is counted, as study 38 does) placed among that contest's REAL entrants by moneygate_score.place (every
real entry of ours removed, DraftKings' even tie split). The scorer runs only behind the reconcile gate: the receipt must
PASS for this scorer's sha and cover the week, and the week's data must be unchanged since.

PRIMARY: big seats by study 38's definition -- dealt entries finishing inside a big contest's seats (rank <= seats, the
week's s24 plan's big / seats, made by the lab's scripts/s38_plan.py from the installed plan); d = big seats(ENTERED) -
big seats(MEAN_MILP), "+", "-" or "0" (a tie). A void arm (arms.json) is never scored as valid; a void primary pair
makes the week VOID.
DESCRIPTIVE: per contest class (moneygate_score.contest_class) the entries, tickets (ticket contests) and line hits
(cash contests: a payout, i.e. at or above the contest's own line) and their multiple over the field's paid share
(hits / entries over paid / field); PROPS_MILP beside MEAN_MILP.
Writes <out>/p3_w<W>.json and appends to the ledger (--ledger), counts and multiples only (no dollars).

    python scripts/p3_score.py --week W --arms <p3_arms out dir> --plan <plan-wNN-s24.json> [--ledger <csv>] [--smoke]
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ARMS = ("ENTERED", "MEAN_MILP", "PROPS_MILP")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return mod


def plan_big(plan: Path) -> dict[str, tuple[bool, int]]:
    c = json.loads(Path(plan).read_text()); c = c if isinstance(c, list) else c["contests"]
    return {str(x["contest_id"]): (bool(x.get("big")), int(x.get("seats") or 0)) for x in c}


def score_arm(M, W, layout: dict, big: dict[str, tuple[bool, int]]) -> dict:
    """Per contest: place every dealt entry; return the big seats, the per-class counts and the missing names."""
    out = {"big_seats": 0, "entries": 0, "missing_names": 0, "by_class": defaultdict(lambda: {"entries": 0, "hits": 0, "paid_share": []}),
           "contests": {}}
    for c in W.contests:
        cid = str(c["contest_id"])
        lus = layout[cid]["lineups"]
        pts = []
        for lu in lus:
            names = [W.name_of[str(x)] for x in lu]
            p, miss = M.lineup_points(names, W.fpts, impute_missing=True)
            pts.append(p); out["missing_names"] += len(miss)
        others = W.others_sorted(cid)
        lad = M.Ladder.from_details(W.details[cid])
        res = M.place(np.asarray(pts, np.int64), others, lad)
        is_big, seats = big.get(cid, (False, 0))
        nb = int((res["rank"] <= seats).sum()) if is_big else 0
        hits = int((res["payout"] > 0).sum())
        cls = M.contest_class(W.details[cid]["name"])
        field_n = len(others) + len(lus)
        out["big_seats"] += nb; out["entries"] += len(lus)
        b = out["by_class"][cls]; b["entries"] += len(lus); b["hits"] += hits; b["paid_share"].append(min(1.0, lad.paid / max(field_n, 1)))
        out["contests"][cid] = {"class": cls, "entries": len(lus), "hits": hits, "big": is_big, "seats": seats, "big_seats": nb,
                                "ticket": bool((lad.ticket > 0).any())}
    for cls, b in out["by_class"].items():
        ps = float(np.mean(b["paid_share"])); b["paid_share"] = round(ps, 6)
        b["multiple"] = round((b["hits"] / b["entries"]) / ps, 4) if b["entries"] and ps > 0 else None
    out["by_class"] = dict(out["by_class"])
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--week", type=int, required=True); ap.add_argument("--arms", type=Path, required=True)
    ap.add_argument("--plan", type=Path, required=True); ap.add_argument("--ledger", type=Path, default=None)
    ap.add_argument("--smoke", action="store_true", help="a mechanics check: printed and written as 'smoke, not counted'")
    a = ap.parse_args(argv)
    M = _load("moneygate_score"); B = _load("moneygate_build")
    rec = json.loads(M.receipt_path().read_text()) if M.receipt_path().is_file() else {}
    if a.week not in rec.get("weeks", []):
        raise SystemExit(f"P3 SCORE REFUSED: the reconcile receipt does not cover week {a.week} (run moneygate_score.py reconcile)")
    M.require_reconcile(sorted(rec["weeks"]))                      # PASS, this scorer's sha, the week's data unchanged
    arms = json.loads((a.arms / "arms.json").read_text())
    W = M.load_week(M.load_config(), a.week)
    big = plan_big(a.plan)
    missing_plan = [str(c["contest_id"]) for c in W.contests if str(c["contest_id"]) not in big]
    if missing_plan:
        raise SystemExit(f"P3 SCORE REFUSED: the plan {a.plan.name} lacks contests {missing_plan}")
    res = {"week": a.week, "smoke": a.smoke, "counted": not a.smoke, "arms_dir": str(a.arms),
           "scorer_sha256": M.sha256(M.SCORER), "plan": str(a.plan), "plan_sha256": M.sha256(a.plan), "arms": {}}
    for arm in ARMS:
        info = arms["arms"].get(arm, {})
        if info.get("void"):
            res["arms"][arm] = {"void": info["void"]}
            continue
        layout = B.layout_book(W.contests, Path(info["book"]), a.arms / f"{arm}-stage")
        res["arms"][arm] = {"void": None, "book_sha256": info["builds"][0], **score_arm(M, W, layout, big)}
    e, m = res["arms"].get("ENTERED", {}), res["arms"].get("MEAN_MILP", {})
    if e.get("void") is None and m.get("void") is None and "big_seats" in e and "big_seats" in m:
        d = e["big_seats"] - m["big_seats"]
        res["d"] = d; res["sign"] = "+" if d > 0 else "-" if d < 0 else "0"
    else:
        res["d"] = None; res["sign"] = "VOID"
    out = a.arms / f"p3_w{a.week}.json"
    out.write_text(json.dumps(res, indent=1, default=str) + "\n")
    tag = "SMOKE, NOT COUNTED" if a.smoke else "COUNTED"
    print(f"P3 W{a.week} ({tag}): scorer {res['scorer_sha256'][:12]}, plan {res['plan_sha256'][:12]}")
    for arm, r in res["arms"].items():
        if r.get("void"):
            print(f"  {arm:10s} VOID: {r['void']}"); continue
        cls = "; ".join(f"{k} {v['hits']}/{v['entries']} (x{v['multiple']})" for k, v in sorted(r["by_class"].items()))
        print(f"  {arm:10s} big seats {r['big_seats']} of {r['entries']} entries; missing names {r['missing_names']}; {cls}")
    print(f"  d = big seats(ENTERED) - big seats(MEAN_MILP) = {res['d']}  sign {res['sign']}  [{tag}]")
    if a.ledger and not a.smoke:
        new = not a.ledger.exists()
        with a.ledger.open("a", newline="") as f:
            wr = csv.writer(f)
            if new:
                wr.writerow(["week", "arm", "void", "big_seats", "entries", "missing_names", "d", "sign", "book_sha256", "scorer_sha256"])
            for arm, r in res["arms"].items():
                wr.writerow([a.week, arm, r.get("void") or "", r.get("big_seats", ""), r.get("entries", ""), r.get("missing_names", ""),
                             res["d"], res["sign"], r.get("book_sha256", ""), res["scorer_sha256"]])
        print(f"  ledger: {a.ledger}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
