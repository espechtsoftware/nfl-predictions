"""The operator's idea (10-07): "giving a preference to a lower-priced player that has high upside" (not ruling out the
expensive ones). Field check on the REAL Millionaire fields, W1-3 (BigQuery, server-side): per lineup, the number of
$8k+ players and the number of CHEAP-UPSIDE players (salary < $7,000, RB/WR/TE, pre-lock upside = the 90th percentile of
the player's simulated worlds minus their mean, in the top sixth of his position), and the lineup's top-1% rate.
Upside comes from the archived T-70 worlds (pre-lock). Usage: cheap_upside_field.py OUT_DIR"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True); BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
res = []
TDQ = BQ.query("""WITH lk AS (SELECT week, MIN(commence_time) lock FROM `nfl_raw.prop_lines` WHERE season = 2026 AND week BETWEEN 1 AND 4
      AND EXTRACT(DAYOFWEEK FROM commence_time AT TIME ZONE 'America/Chicago') = 1 GROUP BY week),
  snap AS (SELECT p.week, MAX(p.snapshot_ts) ts FROM `nfl_raw.prop_lines` p JOIN lk USING (week) WHERE p.season = 2026 AND TIMESTAMP(p.snapshot_ts) < lk.lock AND p.market = 'player_anytime_td' GROUP BY p.week)
  SELECT p.week, p.player, AVG(IF(p.price > 0, 100 / (p.price + 100), -p.price / (-p.price + 100))) td FROM `nfl_raw.prop_lines` p JOIN snap ON p.week = snap.week AND p.snapshot_ts = snap.ts
  WHERE p.season = 2026 AND p.market = 'player_anytime_td' GROUP BY 1, 2""").to_dataframe()
for w in (1, 2, 3, 4):
    d = Path(CFG["weeks"][str(w)]["t70_run"]); fr = pd.read_parquet(d / "frame.parquet")
    wl = np.load(d / "incumbent_player_scores.npy", mmap_mode="r"); assert wl.shape[0] == len(fr)
    fr["sim_mean"] = np.asarray(wl).mean(axis=1); fr["sim_p90"] = np.percentile(np.asarray(wl), 90, axis=1); fr["upside"] = fr.sim_p90 - fr.sim_mean
    sk = fr.pos.isin(["RB", "WR", "TE"]) & (fr.sim_mean >= 4)
    fr["uz"] = np.nan; fr.loc[sk, "uz"] = fr[sk].groupby("pos").upside.transform(lambda v: (v - v.mean()) / v.std())
    fr["cheap_up"] = sk & (fr.salary < 7000) & (fr.uz >= 1.0)
    tdm = dict(zip(TDQ[TDQ.week == w].player.astype(str), TDQ[TDQ.week == w].td)); fr["td"] = fr.display_name.astype(str).map(tdm)
    # market upside: anytime-TD probability ABOVE what the salary implies (residual of TD prob on salary, within position), top sixth
    fr["td_res"] = np.nan
    for pos_ in ("RB", "WR", "TE"):
        g = fr[(fr.pos == pos_) & fr.td.notna()]
        if len(g) > 5:
            b = np.polyfit(g.salary, g.td, 1); fr.loc[g.index, "td_res"] = g.td - np.polyval(b, g.salary)
    fr["tz"] = fr.groupby("pos").td_res.transform(lambda v: (v - v.mean()) / v.std())
    fr["cheap_td"] = fr.pos.isin(["RB", "WR", "TE"]) & (fr.salary < 7000) & (fr.tz >= 1.0)
    names8 = fr.loc[fr.salary >= 8000, "display_name"].astype(str).tolist(); namescu = fr.loc[fr.cheap_up, "display_name"].astype(str).tolist(); namestd = fr.loc[fr.cheap_td, "display_name"].astype(str).tolist()
    print(f"W{w}: $8k+ players {len(names8)}; cheap sim-upside {len(namescu)}: " + ", ".join(namescu[:10]) + f" | cheap TD-odds upside {len(namestd)}: " + ", ".join(namestd[:10]), flush=True)
    q = """WITH c AS (SELECT contest_id, MAX(expected_entries) n FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = @w GROUP BY 1 ORDER BY n DESC LIMIT 1),
      e AS (SELECT DISTINCT x.entry_id, x.rank, x.points, x.players_key, c.n FROM `nfl_raw.contest_entries` x JOIN c USING (contest_id) WHERE x.season = 2026 AND x.week = @w),
      p AS (SELECT entry_id, rank, n, nm FROM e, UNNEST(SPLIT(players_key, '|')) nm)
    SELECT n8, ncu, ntd, COUNT(*) lineups, COUNTIF(rank <= 0.01 * n) top1, COUNTIF(rank <= 100) top100 FROM (
      SELECT entry_id, ANY_VALUE(rank) rank, ANY_VALUE(n) n, COUNTIF(nm IN UNNEST(@n8)) n8, COUNTIF(nm IN UNNEST(@ncu)) ncu, COUNTIF(nm IN UNNEST(@ntd)) ntd FROM p GROUP BY entry_id)
    GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"""
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("w", "INT64", w), bigquery.ArrayQueryParameter("n8", "STRING", names8), bigquery.ArrayQueryParameter("ncu", "STRING", namescu), bigquery.ArrayQueryParameter("ntd", "STRING", namestd)])
    t = BQ.query(q, job_config=cfg).to_dataframe(); t["week"] = w; res.append(t)
T = pd.concat(res, ignore_index=True); T.to_csv(out / "cheap_upside_field.csv", index=False)
for col, label in (("n8", "number of $8k+ players"), ("ncu", "number of cheap SIMULATOR-upside players (< $7k, sim p90 - mean in the top sixth)"), ("ntd", "number of cheap MARKET-upside players (< $7k, TD odds above what the salary implies, top sixth)")):
    g = T.assign(k=T[col].clip(upper=3)).groupby(["week", "k"])[["lineups", "top1", "top100"]].sum()
    g["top1_rate"] = g.top1 / g.lineups; g["share_of_field"] = g.lineups / g.groupby(level=0).lineups.transform("sum")
    print(f"\nby {label} (3 = three or more):"); print(g[["lineups", "share_of_field", "top1_rate", "top100"]].round(4).to_string())
