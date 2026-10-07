"""Standing weekly query (the laptop, from 10-12; run from this folder: it imports gconn). Aggregates only.
Which sub-$4,000 players boom, and do the regulars pick better ones than the field? (W1-4, real fields.)
Per sub-$4k RB/WR/TE: pre-lock facts from the week's T-70 frame and the last pre-lock prop snapshot; the real Millionaire
points (contest FPTS) and field ownership; the regulars' share (users with >= 20 lineups that week, from the graph).
Boom = 15+ DK points (the historical punt-boom line). Output: boom rate by tercile of each fact; the regulars' lean
(their share / field ownership) and whether it predicts booms; what the regulars' lean tracks."""
import json, re, sys, unicodedata
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
from gconn import driver
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
WEEKS = sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run"))
def canon(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower(); s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s); return re.sub(r"[^a-z]", "", s)
TDQ = BQ.query("""WITH lk AS (SELECT week, MIN(commence_time) lock FROM `nfl_raw.prop_lines` WHERE season = 2026 AND week BETWEEN 1 AND 22
      AND EXTRACT(DAYOFWEEK FROM commence_time AT TIME ZONE 'America/Chicago') = 1 GROUP BY week),
  snap AS (SELECT p.week, MAX(p.snapshot_ts) ts FROM `nfl_raw.prop_lines` p JOIN lk USING (week) WHERE p.season = 2026 AND TIMESTAMP(p.snapshot_ts) < lk.lock AND p.market = 'player_anytime_td' GROUP BY p.week)
  SELECT p.week, p.player, AVG(IF(p.price > 0, 100 / (p.price + 100), -p.price / (-p.price + 100))) td FROM `nfl_raw.prop_lines` p JOIN snap ON p.week = snap.week AND p.snapshot_ts = snap.ts
  WHERE p.season = 2026 AND p.market = 'player_anytime_td' GROUP BY 1, 2""").to_dataframe(); TDQ["key"] = TDQ.player.map(canon)
d = driver(); rows = []
for w in WEEKS:
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id").copy(); fr["key"] = fr.display_name.map(canon)
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    own = BQ.query(f"SELECT display_name, ANY_VALUE(fpts) fpts, ANY_VALUE(pct_drafted) own FROM `nfl_raw.contest_ownership` WHERE contest_id = '{cid}' GROUP BY 1").to_dataframe(); own["key"] = own.display_name.map(canon)
    fr = fr.merge(own[["key", "fpts", "own"]], on="key", how="left").merge(TDQ[TDQ.week == w][["key", "td"]], on="key", how="left")
    with d.session() as s:
        reg = pd.DataFrame(s.run("""MATCH (u:User)-[:ENTERED]->(l:Lineup {week_key: $wk}) WITH u, collect(l) AS ls WHERE size(ls) >= 20
            UNWIND ls AS l MATCH (l)-[:CONTAINS]->(p:Player) RETURN p.dk_player_id AS id, count(*) AS n""", wk=f"2026-{w:02d}").data())
        nlu = s.run("""MATCH (u:User)-[:ENTERED]->(l:Lineup {week_key: $wk}) WITH u, count(l) AS n WHERE n >= 20 RETURN sum(n) AS t""", wk=f"2026-{w:02d}").single()["t"]
    fr["reg_share"] = fr.dk_player_id.astype("Int64").astype(str).map(dict(zip(reg.id.astype(str), 100.0 * reg.n / nlu))).fillna(0.0)
    c = fr[fr.pos.isin(["RB", "WR", "TE"]) & (fr.salary < 4000) & fr.fpts.notna()].copy(); c["week"] = w
    c["vac"] = np.where(c.pos == "RB", c.team_vacated_carry_share, c.team_vacated_target_share)
    c["mkt_minus_proj"] = pd.to_numeric(c.market_points, errors="coerce") - pd.to_numeric(c.mean_projection, errors="coerce")
    rows.append(c)
d.close()
C = pd.concat(rows, ignore_index=True)
C["boom"] = C.fpts >= 15; C["own"] = pd.to_numeric(C.own, errors="coerce").fillna(0)
C["lean"] = np.log((C.reg_share + 0.5) / (C.own + 0.5))
print(f"sub-$4k RB/WR/TE player-weeks: {len(C)}; booms (15+): {int(C.boom.sum())} ({C.boom.mean():.1%}); by week {C.groupby('week').boom.mean().round(3).to_dict()}")
print(f"ownership-weighted points of the cheap players: field {np.average(C.fpts, weights=C.own + 1e-9):.2f}, regulars {np.average(C.fpts, weights=C.reg_share + 1e-9):.2f}; "
      f"boom share: field {np.average(C.boom, weights=C.own + 1e-9):.3f}, regulars {np.average(C.boom, weights=C.reg_share + 1e-9):.3f}")
print("  by week (points, field vs regulars): " + ", ".join(f"W{w} {np.average(g.fpts, weights=g.own + 1e-9):.1f} vs {np.average(g.fpts, weights=g.reg_share + 1e-9):.1f}" for w, g in C.groupby("week")))
facts = ["mean_projection", "market_points", "mkt_minus_proj", "td", "vac", "depth_rank", "depth_rank_delta", "snap_share_l4", "snap_share_last", "snap_share_jump",
         "target_share_l4", "carry_share_l4", "fp_route_share_l4", "fp_route_share_jump", "implied_team_total", "spread", "salary", "own", "reg_share", "lean"]
print("\nboom rate (15+) by tercile within week (low / mid / high), and high-minus-low per week:")
for f in facts:
    x = pd.to_numeric(C[f], errors="coerce"); s_ = C.assign(x=x).dropna(subset=["x"])
    if s_.x.nunique() < 3 or len(s_) < 60: continue
    r = s_.groupby("week").x.rank(pct=True, method="first"); s_["t"] = np.select([r <= 1/3, r <= 2/3], ["low", "mid"], "high")
    g = s_.groupby("t").boom.mean().reindex(["low", "mid", "high"]); wk = s_.groupby(["week", "t"]).boom.mean().unstack().reindex(columns=["low", "high"])
    hl = (wk["high"] - wk["low"]).round(2).to_dict()
    print(f"  {f:22s} {g['low']:.1%} / {g['mid']:.1%} / {g['high']:.1%}  (n {len(s_)}; high-low W: {hl})")
print("\nwhat the regulars' lean on cheap players tracks (Spearman with the lean, pooled):")
for f in facts:
    if f in ("lean", "reg_share"): continue
    x = pd.to_numeric(C[f], errors="coerce"); m = x.notna()
    if m.sum() > 60: print(f"  {f:22s} {pd.Series(x[m]).rank().corr(C.lean[m].rank()):+.2f}")
C.drop(columns=[c for c in C.columns if c.startswith("fp_")], errors="ignore")[["week", "pos", "salary", "fpts", "boom", "own", "reg_share", "lean"]].groupby(["week", "pos"]).agg(n=("boom", "size"), booms=("boom", "sum")).to_csv("cheap_tier_counts.csv")
