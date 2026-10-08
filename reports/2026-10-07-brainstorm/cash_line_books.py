"""Big-contest entries: which construction clears a CASH line (~top 20%) in a sharp field? The operator: inside a big
contest he holds a seat in, a win = any finish paying $500+, which in $333+ contests is any cash (DK GPPs pay ~20%).
Production's P3 replay books (W2-4, ~/rehearsals/p3-replay-20261007T172856Z): ENTERED (his W5 package, PKG4-rr), MEAN_MILP
(the plain capped optimizer on the frame's means), PROPS_MILP (the same on props means). Each row's realized DK points
(contest_ownership fpts by display name) placed in (a) the week's Millionaire field and (b) the W3 FFWC $14M qualifier
field (5,000 entries, ~56% max-entry regulars: the sharp-field proxy). Aggregates only."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text()); RD = Path.home() / "rehearsals/p3-replay-20261007T172856Z"
FFWC = {3: "195905120"}  # filled below from the shark-share types if present
import csv
types = {r["contest_id"]: (r["type"], r["week"]) for r in csv.DictReader(open(Path.home() / "private/regulars-share/shark_share_by_contest.csv"))}
FFWC = {int(w): cid for cid, (t, w) in types.items() if "14M" in t}
rows = []
for w in (2, 3, 4):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id")
    name = dict(zip(pd.to_numeric(fr.dk_player_id, errors="coerce").fillna(-1).astype(int).astype(str), fr.display_name))
    milly = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    own = BQ.query(f"SELECT display_name, ANY_VALUE(fpts) fpts FROM `nfl_raw.contest_ownership` WHERE contest_id = '{milly}' GROUP BY 1").to_dataframe()
    pts = dict(zip(own.display_name, pd.to_numeric(own.fpts, errors="coerce").fillna(0.0)))
    fields = {"Millionaire": milly}
    if w in FFWC: fields["FFWC $14M qualifier"] = FFWC[w]
    dist = {k: np.sort(BQ.query(f"SELECT DISTINCT entry_id, points FROM `nfl_raw.contest_entries` WHERE contest_id = '{c}' AND season = 2026 AND week = {w}").to_dataframe().points.astype(float).values) for k, c in fields.items()}
    for arm in ("ENTERED", "MEAN_MILP", "PROPS_MILP"):
        p = RD / f"w{w}" / f"{arm}-1" / "book.csv"
        if not p.exists(): continue
        b = pd.read_csv(p, dtype=str)
        for rank, r in enumerate(b.values, start=1):
            total = sum(pts.get(name.get(v, ""), 0.0) for v in r)
            for k, d in dist.items():
                beat = np.searchsorted(d, total, side="left") / len(d)   # share of the field strictly below
                rows.append({"week": w, "arm": arm, "rank": rank, "field": k, "points": total, "beat": beat})
R = pd.DataFrame(rows)
R["top20"] = R.beat >= 0.80; R["top10"] = R.beat >= 0.90; R["top1"] = R.beat >= 0.99
pd.set_option("display.width", 200)
for k, g in R.groupby("field"):
    print(f"\n=== {k} field: rows per arm per week = 26 (W3 only for the FFWC qualifier)")
    t = g.groupby(["arm", "week"]).agg(mean_pct_beaten=("beat", "mean"), top20=("top20", "mean"), top10=("top10", "mean"), top1=("top1", "mean"), mean_pts=("points", "mean")).round(3)
    print(t.to_string())
    print("  pooled: " + "; ".join(f"{a}: top20 {x.top20.mean():.3f}, top10 {x.top10.mean():.3f}, mean beaten {x.beat.mean():.3f}" for a, x in g.groupby("arm")))
    print("  row #1 of each arm (the 'best' single entry), % of field beaten by week: " + "; ".join(f"{a}: " + "/".join(f"{v:.2f}" for v in x[x['rank'] == 1].sort_values('week').beat) for a, x in g.groupby("arm")))
    for k2 in (2, 3):
        print(f"  rows 1-{k2} of each arm, mean % of field beaten per week: " + "; ".join(f"{a}: " + "/".join(f"{v:.2f}" for v in x[x['rank'] <= k2].groupby('week').beat.mean()) for a, x in g.groupby("arm")))
print("\nidentical row #1 (ENTERED vs MEAN_MILP), by week: " + ", ".join(f"W{w} {sorted(R[(R.week == w) & (R.arm == 'ENTERED') & (R['rank'] == 1)].points)[:1] == sorted(R[(R.week == w) & (R.arm == 'MEAN_MILP') & (R['rank'] == 1)].points)[:1]}" for w in (2, 3, 4)))
