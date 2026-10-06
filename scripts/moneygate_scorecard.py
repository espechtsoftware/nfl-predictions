"""The weekly "HOW ARE WE DIFFERENT" scorecard (study list 20; operator 10-05: "Is there something … that would help us
quickly see patterns like this without waiting for me to ask the right questions?").

For the given weeks: every lineup of our entries, of the Millionaire field and of its top 1% / top 0.1% is described by
the same features (stack shape, RB use, game spread, salary, cheap players, ownership, duplication). The RANKED list
is OUR GAP VS THE FIELD, in standardized units (the field's spread of that feature): the field's shape is chosen before
the games, so the gap is decision-relevant. The top 1% is CONTEXT only, with its across-week range as a stability note:
winners' shapes swing with which games hit, and ranking against them would chase last week's result (reviewer's guard).

    A gap is a question for a preregistered test, never a change on its own.

    python scripts/moneygate_scorecard.py --weeks 1,2,3,4
Prints the table and writes PUBLIC/scorecard_w<weeks>.json (aggregates only).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import moneygate_score as MS  # noqa: E402

FIX = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS"}
FEATURES = {   # name: (label, binary?)
    "qb_plus1": ("QB + 1 teammate only", True), "qb_plus2": ("QB + 2 or more teammates", True),
    "bringback": ("Bring-back", True), "in_qb_game": ("Players from the QB's game", False),
    "max_game": ("Most players from one game", False), "dual": ("Second game with players from both teams", True),
    "games": ("Games used", False), "rb_with_qb": ("RB from the QB's team", True), "rb_bb": ("RB as the bring-back", True),
    "rb_dst": ("RB with his own DST", True), "salary_left": ("Salary left ($)", False), "sub4k": ("Players under $4,000", False),
    "own_sum": ("Ownership sum (%)", False), "dup": ("Lineup duplicated in the field", True),
}


def lineup_features(L: list[str], team: dict, pos: dict, sal: dict, opp: dict, own: dict, dupset: set) -> dict | None:
    T = {p: FIX.get(team.get(p), team.get(p)) for p in L}; Z = {p: pos.get(p) for p in L}
    qb = next((p for p in L if Z[p] == "QB"), None); dst = next((p for p in L if Z[p] == "DST"), None)
    if qb is None or T[qb] is None:
        return None
    q = T[qb]; o = opp.get(q)
    mates = sum(1 for p in L if T[p] == q and Z[p] in ("WR", "TE"))
    g = Counter(tuple(sorted((T[p], opp.get(T[p]) or "?"))) for p in L if Z[p] != "DST" and T[p])
    qg = tuple(sorted((q, o or "?")))
    dual = any(k != qg and len({T[p] for p in L if Z[p] != "DST" and T[p] in k}) == 2 for k, v in g.items() if v >= 2)
    rbs = [p for p in L if Z[p] == "RB"]
    return {"qb_plus1": mates == 1, "qb_plus2": mates >= 2, "bringback": any(T[p] == o and Z[p] in ("RB", "WR", "TE") for p in L),
            "in_qb_game": g.get(qg, 0), "max_game": max(g.values()), "dual": dual, "games": len(g),
            "rb_with_qb": any(T[r] == q for r in rbs), "rb_bb": any(T[r] == o for r in rbs),
            "rb_dst": dst is not None and any(T[r] == T.get(dst) for r in rbs),
            # a player outside the T-70 frame (ruled out pre-build) has no salary there: salary-based features are unknown
            "salary_left": (50000 - sum(sal[p] for p in L)) if all(sal.get(p, 0) > 0 for p in L) else np.nan,
            "sub4k": sum(1 for p in L if 0 < sal.get(p, 0) < 4000) if all(sal.get(p, 0) > 0 for p in L) else np.nan,
            "own_sum": sum(own.get(p, 0.0) for p in L), "dup": frozenset(L) in dupset}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0]); ap.add_argument("--weeks", default="1,2,3,4")
    a = ap.parse_args(argv)
    weeks = [int(w) for w in a.weeks.split(",")]
    cfg = MS.load_config()
    from google.cloud import bigquery
    c = bigquery.Client(project=cfg.get("bq_project", "nfl-predictions-503414")); P = c.project
    hist = pd.read_csv(cfg["entry_history"], dtype=str); ours_ids = set(hist.Entry_Key.astype(str))
    per, drops = [], []
    for w in weeks:
        wc = cfg["weeks"][str(w)]; milly = str(wc["millionaire_contest"])
        fr = pd.read_parquet(Path(wc["t70_run"]) / "frame.parquet").drop_duplicates("display_name")
        team, pos = dict(zip(fr.display_name, fr.team)), dict(zip(fr.display_name, fr.pos))
        # players the T-70 frame dropped (ruled out before the build, yet still in field lineups): team and position from
        # that week's roster, so their lineups are not silently lost (the reviewer's check found 150 of 20,000 in W4)
        ro = c.query(f"SELECT full_name, ANY_VALUE(team) team, ANY_VALUE(position) pos FROM `{P}.nfl_raw.rosters_weekly` "
                     f"WHERE season=2026 AND week={w} GROUP BY 1").to_dataframe()
        for n_, t_, p_ in zip(ro.full_name, ro.team, ro.pos):
            team.setdefault(n_, t_); pos.setdefault(n_, p_)
        sal = dict(zip(fr.display_name, pd.to_numeric(fr.salary, errors="coerce").fillna(0)))
        sch = c.query(f"SELECT home_team h, away_team a FROM `{P}.nfl_raw.schedules` WHERE season=2026 AND week={w}").to_dataframe()
        opp = {}
        for h, aw in zip(sch.h, sch.a):
            opp[h] = aw; opp[aw] = h
        ow = c.query(f"SELECT display_name, MAX(CAST(pct_drafted AS FLOAT64)) p FROM `{P}.nfl_raw.contest_ownership` "
                     f"WHERE season=2026 AND week={w} AND contest_id='{milly}' GROUP BY 1").to_dataframe()
        own = dict(zip(ow.display_name, ow.p))
        e = c.query(f"SELECT entry_id, CAST(points AS FLOAT64) pts, lineup_slots_json FROM `{P}.nfl_raw.contest_entries` "
                    f"WHERE season=2026 AND week={w} AND contest_id='{milly}' AND points IS NOT NULL").to_dataframe()
        e["L"] = [[s.get("player") for s in json.loads(j)] for j in e.lineup_slots_json]
        cnt = Counter(frozenset(L) for L in e.L); dupset = {k for k, v in cnt.items() if v > 1}
        allw = c.query(f"SELECT entry_id, lineup_slots_json FROM `{P}.nfl_raw.contest_entries` WHERE season=2026 AND week={w}").to_dataframe()
        ours = allw[allw.entry_id.astype(str).isin(ours_ids)]
        e = e.sort_values("pts", ascending=False).reset_index(drop=True); n = len(e)
        groups = {"OURS": [[s.get("player") for s in json.loads(j)] for j in ours.lineup_slots_json],
                  "field": e.sample(min(20000, n), random_state=w).L.tolist(),
                  "top 1%": e.iloc[: n // 100].L.tolist(), "top 0.1%": e.iloc[: max(1, n // 1000)].L.tolist()}
        for gname, Ls in groups.items():
            feats = [lineup_features(L, team, pos, sal, opp, own, dupset) for L in Ls]
            dropped = sum(f is None for f in feats)
            d = pd.DataFrame([f for f in feats if f])
            drops.append({"week": w, "group": gname, "lineups": len(Ls), "dropped_no_qb_team": dropped})
            for k in FEATURES:
                per.append({"week": w, "group": gname, "feature": k, "mean": float(d[k].mean()), "sd": float(d[k].astype(float).std())})
    D = pd.DataFrame(per)
    piv = D.pivot_table(index=["feature", "week"], columns="group", values="mean")
    sd = D[D.group == "field"].groupby("feature").sd.mean()
    rows = []
    for k, (label, binary) in FEATURES.items():
        x = piv.loc[k]
        gap = (x["OURS"] - x["field"]).mean() / max(sd[k], 1e-9)
        rows.append({"feature": label, "ours": x["OURS"].mean(), "field": x["field"].mean(), "gap_sd": gap,
                     "gap_by_week": [round(float(v), 3) for v in (x["OURS"] - x["field"]) / max(sd[k], 1e-9)],
                     "top1": x["top 1%"].mean(), "top1_range": (float(x["top 1%"].min()), float(x["top 1%"].max())), "binary": binary})
    R = pd.DataFrame(rows).sort_values("gap_sd", key=lambda s: -s.abs()).reset_index(drop=True)
    print(f"HOW ARE WE DIFFERENT -- weeks {weeks}. Ranked by OUR gap vs the FIELD (standardized; the field's shape is chosen pre-lock).")
    print("The top 1% is CONTEXT only (its range across weeks shows how much it swings). "
          "A gap is a question for a preregistered test, never a change on its own.\n")
    def f(v, b):
        return f"{100 * v:5.0f}%" if b else f"{v:7.1f}"
    print(f"{'#':>2}  {'feature':42s} {'ours':>7} {'field':>7} {'gap (sd)':>9}   {'top 1% (range across weeks)':>28}")
    for i, r in R.iterrows():
        lo, hi = r.top1_range
        print(f"{i + 1:>2}  {r.feature:42s} {f(r.ours, r.binary):>7} {f(r.field, r.binary):>7} {r.gap_sd:>+9.2f}   "
              f"{f(r.top1, r.binary):>7} ({f(lo, r.binary).strip()}–{f(hi, r.binary).strip()})")
    MS.PUBLIC.mkdir(parents=True, exist_ok=True)
    out = MS.PUBLIC / f"scorecard_w{''.join(map(str, weeks))}.json"
    out.write_text(json.dumps({"weeks": weeks, "ranked": R.to_dict("records"), "dropped": drops}, indent=1, default=float) + "\n")
    dd = pd.DataFrame(drops)
    print("\nlineups dropped because the QB's team was unknown (a name-map gap; must stay ~0):")
    print(dd.pivot_table(index="week", columns="group", values="dropped_no_qb_team").to_string())
    print(f"\nwritten {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
