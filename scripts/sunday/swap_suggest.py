#!/usr/bin/env python3
"""Cap-feasible QB swap suggestions for flagged rows of a delivered book (read-only).

  swap_suggest.py RUN_DIR FLAGS_CSV LIVE_QB_CSV OUT_CSV [K]

For every book row whose QB is on the flag table: lineup salary, cap slack, the expected starters that fit
one-for-one (QB salary + slack), and if none fit, the best two-player swap (QB -> starter, plus one skill
player -> a cheaper same-position player who is not out), ranked by projected points gained. Output rows:
row, qb, verdict, lineup_salary, slack, single_swaps, pair_swap. Information for the operator; nothing is changed.
"""
import csv, sys
import pandas as pd

CAP = 50000
run, flags_csv, live_csv, out_csv = sys.argv[1:5]
k = int(sys.argv[5]) if len(sys.argv) > 5 else None
f = pd.read_parquet(run + "/frame.parquet")
f["dk"] = f.dk_player_id.astype(int)
projcol = next((c for c in ("proj_points", "proj", "mean", "center", "served_mean", "dk_ppg") if c in f.columns), None)
sal = dict(zip(f.dk, pd.to_numeric(f.salary, errors="coerce").fillna(0).astype(int)))
name = dict(zip(f.dk, f.display_name.astype(str))); pos = dict(zip(f.dk, f.pos.astype(str)))
proj = dict(zip(f.dk, pd.to_numeric(f[projcol], errors="coerce").fillna(0))) if projcol else {d: 0.0 for d in f.dk}
status = dict(zip(f.dk, f.status.astype(str).str.upper())) if "status" in f.columns else {}
out_like = {"O", "OUT", "IR", "D", "DOUBTFUL"}
raw = list(csv.DictReader(open(flags_csv)))
if raw and "role" in raw[0]:
    # qb_flags.py format: flagged = gated / ambiguous / out backups, or a primary who is himself Doubtful/Questionable;
    # swap targets = healthy primaries (never Questionable/Doubtful ones)
    flags = {}
    for r in raw:
        own = (r.get("injury_status") or "").strip() or {"D": "Doubtful", "Q": "Questionable", "O": "Out"}.get((r.get("dk_status") or "").strip().upper(), "")
        role = r.get("role", "")
        if role in ("gated", "out", "ambiguous") or (role == "primary" and own.upper() in ("DOUBTFUL", "QUESTIONABLE")):
            flags[r["qb_name"].strip()] = {"verdict": {"gated": "BEHIND-HEALTHY-STARTER", "out": "OUT", "ambiguous": "STARTER-" + r.get("team_class", "").upper()}.get(role, "STARTER-" + own.upper()), "injury_status": own}
    starters = pd.DataFrame([{"display_name": r["qb_name"].strip(), "team": r["team"], "salary": float(r["salary"]), "proj_points": float(r["proj"] or 0)}
                             for r in raw if r.get("role") == "primary" and r.get("team_class") == "healthy"]).sort_values("salary")
else:
    flags = {r["qb_name"].strip(): r for r in raw}
    live = pd.read_csv(live_csv)
    live["inj"] = live.injury_status.fillna("").str.upper(); live["dk"] = live.status.fillna("").str.upper()
    live["out"] = live.inj.eq("OUT") | live.dk.isin(["O", "IR"]); live["doubt"] = live.inj.eq("DOUBTFUL") | live.dk.eq("D")
    starters = []
    for team, g in live[live.depth_rank.notna()].groupby("team"):
        g = g.sort_values("depth_rank"); prim = g[~g.out]
        if prim.empty or bool(prim.iloc[0]["doubt"]):
            continue
        starters.append(prim.iloc[0])
    starters = pd.DataFrame(starters)[["display_name", "team", "salary", "proj_points"]].sort_values("salary")
by_name = {n: d for d, n in name.items()}
book = pd.read_csv(run + "/book.csv")
if k:
    book = book.head(k)
rows_out = []
for i, row in book.iterrows():
    ids = [int(x) for x in row.values]; q = ids[0]; qn = name[q]
    if qn not in flags:
        continue
    tot = sum(sal[x] for x in ids); slack = CAP - tot; budget = sal[q] + slack
    lineup = set(ids)
    fits = starters[(starters.salary <= budget) & (~starters.display_name.isin([name[x] for x in ids]))]
    single = "; ".join(f"{r.display_name} ${int(r.salary):,} ({r.proj_points:.1f})" for r in fits.sort_values("proj_points", ascending=False).head(3).itertuples())
    pair = ""
    if fits.empty:
        best = None
        for r in starters.itertuples():
            need = int(r.salary) - budget
            if need <= 0:
                continue
            for p in ids[1:]:
                if pos[p] == "DST":
                    continue
                cands = [d for d in f.dk if pos[d] == pos[p] and d not in lineup and sal[d] <= sal[p] - need and status.get(d, "") not in out_like]
                if not cands:
                    continue
                d = max(cands, key=lambda x: proj[x])
                gain = float(r.proj_points) - proj[q] * 0 + proj[d] - proj[p]   # QB gain counted from zero: the flagged QB is treated as scoring 0
                gain = float(r.proj_points) + proj[d] - proj[p]
                if best is None or gain > best[0]:
                    best = (gain, r.display_name, int(r.salary), name[p], sal[p], name[d], sal[d])
        if best:
            gain, sn, ss, pn, ps, dn, ds = best
            pair = f"QB -> {sn} ${ss:,} and {pn} ${ps:,} -> {dn} ${ds:,} (net proj {gain:+.1f} vs a zero-scoring QB)"
    fl = flags[qn]
    rows_out.append({"row": i + 1, "qb": qn, "qb_salary": sal[q], "verdict": fl["verdict"], "own_status": fl["injury_status"],
                     "lineup_salary": tot, "slack": slack, "single_swaps": single or "NONE", "pair_swap": pair})
pd.DataFrame(rows_out).to_csv(out_csv, index=False)
for r in rows_out:
    print(f"row {r['row']:>3} {r['qb']:<16} ${r['qb_salary']:>5} slack ${r['slack']:>4} {r['verdict']:<24} single: {r['single_swaps']}" + (f" | pair: {r['pair_swap']}" if r["pair_swap"] else ""))
print(f"{len(rows_out)} flagged rows -> {out_csv} (proj column: {projcol})")
