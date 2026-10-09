#!/usr/bin/env python3
"""His live W5 version replayed on this season's real contests (the operator 10-09, relayed: "can we run that version
against this season using real info?"). DESCRIPTIVE; partly in-sample (the TE / low-ownership ideas came from the W1-4
fields); nothing decides on it.

For each week that can be built (W3 and W4: W1-2 have no point-in-time ownership file, so the ownership cap cannot be
built there) and each arm, the money gate's own machinery: the week's archived Saturday + T-70 runs, union_reselect at THIS
checkout on the Week-5 lab pin (pkg_lab_src), the week's real contests (contests.json; W4 as entered), enter_layout's head
layout, and the real fields and ladders (moneygate_score: names -> DK points, place() with ours removed, DK's tie split).

  R10-T50    the money gate's PKG4-rr arm (his Week-5 package as of 10-06: the mix, overlap 4, round-robin, the QB cap
             translated by share, the 50% player cap, no ownership term) -- "today's book" before 10-09, without the cheap
             +2 block (not built for W1-4)
  R10-PKG    R10-T50 + the 35% player cap + the ownership cap (+15 points)        -- his package (armed 10-09)
  R10-PKGRR  R10-PKG + at most one TE and one sub-3% player per book row         -- his package + test 2 (armed 10-09)
  A0         what he entered (the reconcile's rows)

Ownership for the cap: W4 = Fantasy Points' projected ownership (the money gate's pinned w4_ownership_fp.csv); W3 = our
own Saturday ownership model (w3_ownership_sets.csv, pred_own) converted to the cap's file form -- an approximation.
Projections: W4 = FP's (the week's fp_proj_source); W3 = our T-70 model.

Per arm, week and contest group (the Millionaire vs the limited-entry satellites): entries, mean finish percentile,
top-1% / top-10% finishes, cashes, big wins (cash >= $500 or a ticket >= $300) and the return multiple. Ratios and counts to
--out (aggregates only); dollars to ~/private/moneygate/replay-10-09-dollars.json.

    python reports/2026-10-09-package-replay/replay.py build|score --weeks 3,4 --out <dir>
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROD = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROD / "scripts")); sys.path.insert(0, str(PROD / "src"))
import moneygate_build as MB  # noqa: E402
import moneygate_score as MS  # noqa: E402

ARMS = ("R10-T50", "R10-PKG", "R10-PKGRR")
BIG_CASH, BIG_TICKET = 500.0, 300.0


def own_cap_file(w: str, e: dict) -> Path:
    src = Path(e["own_file"])
    if w == "4":
        return src
    d = pd.read_csv(src, dtype={"gsis_id": str, "dk_player_id": str})          # W3: our Saturday model's pred_own
    out = Path.home() / "moneygate" / "inputs" / "own" / f"w{w}_ownership_fp_from_sets.csv"
    pd.DataFrame({"id": d.gsis_id, "dk_player_id": d.dk_player_id, "display_name": d.display_name, "pos": d.pos,
                  "team": d.team, "pred_own": d.pred_own, "fp_own_raw": d.pred_own, "filled_from": "ownership_sets"}).to_csv(out, index=False)
    return out


def arm_flags(arm: str, w: str, e: dict, K: int, contests: Path) -> list[str]:
    f = MB.pkg_flags("PKG4-rr", e, K, contests)
    if arm in ("R10-PKG", "R10-PKGRR"):
        f += ["--main-cap-share", "0.35", "--main-own-cap-delta", "15", "--main-own-cap-source", str(own_cap_file(w, e)),
              "--main-own-cap-fallback-share", "0.5"]
    if arm == "R10-PKGRR":
        f += ["--mix-max-te", "1", "--mix-max-low-own", "1", "--mix-low-own-pct", "3"]
    return f


def cmd_build(cfg: dict, weeks: list[str]) -> None:
    lab = MB.lab_head(cfg, "pkg_")
    for w in weeks:
        e = cfg["weeks"][w]; MB.check_inputs(e)
        rec = json.loads((MB.BOOKS / f"w{w}" / "contests_receipt.json").read_text()); K, T = rec["K"], rec["T"]
        contests = MB.BOOKS / f"w{w}" / "contests.json"
        for arm in ARMS:
            out = MB.BOOKS / f"w{w}" / arm / "run1"
            if (out / "book.csv").is_file():
                print(f"W{w} {arm}: exists, kept"); continue
            out.parent.mkdir(parents=True, exist_ok=True)
            args = ["--saturday-run", e["saturday_run"], "--t70-run", e["t70_run"], "--live-dir", str(Path(e["t70_run"]).parent),
                    "--entries", str(K), "--tail-sleeve", str(T), *arm_flags(arm, w, e, K, contests), "--out", str(out), "--rehearsal"]
            cmd = [cfg["lab_py"], str(PROD / "scripts" / "union_reselect.py"), *args]
            env = dict(os.environ, LIVE_FLEX_LATEST="1", PYTHONPATH=f"{cfg['pkg_lab_src']}:{PROD / 'src'}", PYTHONHASHSEED="0")
            (out.parent / "run1.cmd.json").write_text(json.dumps({"argv": cmd, "lab_sha": lab, "PYTHONHASHSEED": "0"}, indent=1) + "\n")
            print(f"W{w} {arm}: union_reselect K {K} T {T}", flush=True)
            p = subprocess.run(cmd, env=env, cwd=PROD, capture_output=True, text=True)
            (out.parent / "run1.log").write_text(p.stdout + "\n--- stderr ---\n" + p.stderr)
            if p.returncode != 0:
                raise SystemExit(f"W{w} {arm}: union_reselect exit {p.returncode}:\n  " + "\n  ".join((p.stdout + p.stderr).strip().splitlines()[-5:]))
            for key in ("OWN CAP", "ROW RULES"):
                for line in p.stdout.splitlines():
                    if key in line:
                        print(f"   {line.strip()[:200]}")
        MB.cmd_layout([w], list(ARMS))


def group(cls: str) -> str:
    return "Millionaire" if cls == "Millionaire" else "limited-entry"


def score_entries(W, pts: np.ndarray, cid: str) -> dict:
    lad = MS.Ladder.from_details(W.details[cid])
    res = MS.place(pts, W.others_sorted(cid), lad)
    n_total = int((W.field.contest_id == cid).sum())
    rank = res["rank"]
    return {"rank": rank, "cash": res["cash"], "ticket": res["ticket"], "pct": res["pct"],
            "top1": rank <= max(1, int(np.floor(0.01 * n_total))), "top10": rank <= max(1, int(np.floor(0.10 * n_total)))}


def cmd_score(cfg: dict, weeks: list[str], out: Path) -> None:
    recon = pd.read_csv(MS.PRIVATE / "reconcile_entries.csv", dtype={"contest_id": str, "entry_id": str})
    rows = []
    for w in weeks:
        W = MS.load_week(cfg, int(w))
        for arm in ARMS:
            lay = json.loads((MB.BOOKS / f"w{w}" / arm / "layout.json").read_text())
            for c in W.contests:
                cid = str(c["contest_id"])
                lus = lay["contests"][cid]["lineups"]
                pts = np.array([MS.lineup_points([W.name_of[x] for x in lu], W.fpts)[0] for lu in lus], dtype=np.int64)
                s = score_entries(W, pts, cid)
                fee = float(W.details[cid].get("fee") or W.details[cid].get("entryFee"))
                cls = MS.contest_class(W.details[cid]["name"])
                for i in range(len(lus)):
                    rows.append({"week": int(w), "arm": arm, "group": group(cls), "fee": fee, "cash": float(s["cash"][i]),
                                 "ticket": float(s["ticket"][i]), "pct": float(s["pct"][i]), "top1": bool(s["top1"][i]),
                                 "top10": bool(s["top10"][i])})
        rw = recon[recon.week == int(w)]
        for cid, g in rw.groupby("contest_id"):
            cls = MS.contest_class(W.details[cid]["name"])
            n_total = int((W.field.contest_id == cid).sum())
            mine = W.field[W.field.entry_id.isin(set(g.entry_id))]
            pts = mine.points.to_numpy(np.int64)
            res = MS.place(pts, W.others_sorted(cid), MS.Ladder.from_details(W.details[cid]))
            for i in range(len(mine)):
                r = int(res["rank"][i])
                rows.append({"week": int(w), "arm": "A0 entered", "group": group(cls), "fee": float(g.fee_calc.iloc[0]),
                             "cash": float(res["cash"][i]), "ticket": float(res["ticket"][i]), "pct": float(res["pct"][i]),
                             "top1": r <= max(1, int(np.floor(0.01 * n_total))), "top10": r <= max(1, int(np.floor(0.10 * n_total)))})
    d = pd.DataFrame(rows)
    d["pay"] = d.cash + d.ticket
    d["big"] = (d.cash >= BIG_CASH - 1e-9) | (d.ticket >= BIG_TICKET - 1e-9)

    def agg(g):
        return pd.Series({"entries": len(g), "mean_finish_pct": round(g.pct.mean(), 1), "top1": int(g.top1.sum()),
                          "top10": int(g.top10.sum()), "cashes": int((g.pay > 0).sum()), "big_wins": int(g.big.sum()),
                          "multiple": round(g.pay.sum() / g.fee.sum(), 3) if g.fee.sum() else None})
    order = ["A0 entered", *ARMS]
    out.mkdir(parents=True, exist_ok=True)
    pub = {}
    for keys, name in ((["week", "group", "arm"], "by_week_group"), (["week", "arm"], "by_week"), (["group", "arm"], "pooled_by_group"),
                       (["arm"], "pooled")):
        t = d.groupby(keys).apply(agg).reset_index()
        t["arm"] = pd.Categorical(t["arm"], order); t = t.sort_values(keys[:-1] + ["arm"])
        pub[name] = t.to_dict(orient="records")
        print(f"\n== {name}"); print(t.to_string(index=False))
    (out / "replay_summary.json").write_text(json.dumps(pub, indent=1, default=str) + "\n")
    priv = d.groupby(["week", "arm"]).agg(fees=("fee", "sum"), winnings=("pay", "sum")).round(2).reset_index()
    (MS.PRIVATE / "replay-10-09-dollars.json").write_text(priv.to_json(orient="records", indent=1))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cmd", choices=("build", "score")); ap.add_argument("--weeks", default="3,4"); ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    cfg = MB.load_config()
    weeks = [x.strip() for x in a.weeks.split(",") if x.strip()]
    if a.cmd == "build":
        cmd_build(cfg, weeks)
    else:
        cmd_score(cfg, weeks, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
