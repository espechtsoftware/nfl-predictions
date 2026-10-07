"""Is an expensive DST worth its price? (A) History 2014-2021 (dk_salaries_historical rows that carry DK points: the 2022-25
rows have salaries only; every DK DST row, main-slate-agnostic): DK points by salary tier, points per $1k, boom rate; and the same slope for WR/RB/TE for comparison. (B) DST salary
in our books (T-70 entered W1-4; the W2-4 replays at Week-5 settings) vs the whole real field."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text()); RD = Path.home() / "rehearsals/outside-cblocks-20261007T153309Z"
H = BQ.query("SELECT season, week, position, salary, dk_points, team_abbr FROM `nfl_raw.dk_salaries_historical` WHERE salary > 0").to_dataframe()
print("positions:", H.position.value_counts().to_dict())
H["dk_points"] = pd.to_numeric(H.dk_points, errors="coerce"); H["salary"] = pd.to_numeric(H.salary, errors="coerce"); print("rows without points dropped:", int(H.dk_points.isna().sum())); H = H.dropna(subset=["dk_points", "salary"])
dpos = [p for p in H.position.unique() if str(p).upper() in ("DST", "DEF", "D")]
X = H[H.position.isin(dpos)].copy()
X["tier"] = pd.cut(X.salary, [0, 2499, 2999, 3499, 3999, 99999], labels=["<2.5k", "2.5-2.9k", "3.0-3.4k", "3.5-3.9k", "4k+"])
t = X.groupby("tier", observed=True).agg(n=("dk_points", "size"), mean=("dk_points", "mean"), sd=("dk_points", "std"), p_15plus=("dk_points", lambda s: (s >= 15).mean()),
                                         p_20plus=("dk_points", lambda s: (s >= 20).mean())).round(3)
t["pts_per_1k"] = (X.groupby("tier", observed=True).apply(lambda g: g.dk_points.sum() / g.salary.sum() * 1000)).round(2)
print("\n(A) DSTs 2014-2021 by salary tier"); print(t.to_string())
for era, Y in (("2014-2017", X[X.season <= 2017]), ("2018-2021", X[X.season >= 2018])):
    b = np.polyfit(Y.salary / 1000, Y.dk_points, 1)[0]; print(f"  {era}: DST points per extra $1k of salary (slope) {b:+.2f}; n {len(Y):,}")
for p in ("WR", "RB", "TE", "QB"):
    Y = H[(H.position == p) & (H.season >= 2018)]; b = np.polyfit(Y.salary / 1000, Y.dk_points, 1)[0]; print(f"  {p} 2018-2021 slope: {b:+.2f} points per $1k (n {len(Y):,})")
print("\n(B) DST salary: share of lineups/rows with DST < $3,000 / >= $3,500, and mean DST salary")
for w in (1, 2, 3, 4):
    t70 = Path(CFG["weeks"][str(w)]["t70_run"]); fr = pd.read_parquet(t70 / "frame.parquet").drop_duplicates("dk_player_id")
    dst = fr[fr.pos == "DST"]; sal = dict(zip(pd.to_numeric(dst.dk_player_id, errors="coerce").astype("Int64").astype(str), dst.salary.astype(float)))
    out = []
    for tag, p in (("T-70 entered", t70 / "book.csv"), ("W5 live", RD / f"w{w}-live/book.csv"), ("W5 cheap+2", RD / f"w{w}-cblock2/book.csv")):
        if not p.exists(): continue
        b = pd.read_csv(p, dtype=str); s = np.array([next((sal[v] for v in r if v in sal), np.nan) for r in b.values])
        out.append(f"{tag}: <3k {np.mean(s < 3000):.2f} / >=3.5k {np.mean(s >= 3500):.2f} / mean {np.nanmean(s):,.0f}")
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    own = BQ.query(f"SELECT display_name, ANY_VALUE(pct_drafted) own FROM `nfl_raw.contest_ownership` WHERE contest_id = '{cid}' GROUP BY 1").to_dataframe()
    m = dst.merge(own, on="display_name", how="left"); m["own"] = pd.to_numeric(m.own, errors="coerce").fillna(0); tot = m.own.sum()
    out.append(f"field: <3k {m[m.salary < 3000].own.sum() / tot:.2f} / >=3.5k {m[m.salary >= 3500].own.sum() / tot:.2f} / mean {(m.salary * m.own).sum() / tot:,.0f} (DST ownership summed {tot:.0f}%)")
    print(f"  W{w}: " + " | ".join(out))
