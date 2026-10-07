"""Refined cheap preference (10-07, from the cheap-tier analysis: booming sub-$4k players are the ones the props market
rates; the regulars' lean tracks market points at rho .82). Fixed before the run: +4 projected points for a non-DST player
under $4,000 who is in the top third of that week's sub-$4k players by (a) props-implied points (cheapmkt4; players with no
prop line get nothing) or (b) anytime-TD probability (cheaptd4); nothing for the rest."""
import json, re, sys, unicodedata
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
out = Path(sys.argv[1]); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text()); BQ = bigquery.Client()
def canon(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower(); s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s); return re.sub(r"[^a-z]", "", s)
TDQ = BQ.query("""WITH lk AS (SELECT week, MIN(commence_time) lock FROM `nfl_raw.prop_lines` WHERE season = 2026 AND week BETWEEN 1 AND 4
      AND EXTRACT(DAYOFWEEK FROM commence_time AT TIME ZONE 'America/Chicago') = 1 GROUP BY week),
  snap AS (SELECT p.week, MAX(p.snapshot_ts) ts FROM `nfl_raw.prop_lines` p JOIN lk USING (week) WHERE p.season = 2026 AND TIMESTAMP(p.snapshot_ts) < lk.lock AND p.market = 'player_anytime_td' GROUP BY p.week)
  SELECT p.week, p.player, AVG(IF(p.price > 0, 100 / (p.price + 100), -p.price / (-p.price + 100))) td FROM `nfl_raw.prop_lines` p JOIN snap ON p.week = snap.week AND p.snapshot_ts = snap.ts
  WHERE p.season = 2026 AND p.market = 'player_anytime_td' GROUP BY 1, 2""").to_dataframe(); TDQ["key"] = TDQ.player.map(canon)
for w in (2, 3, 4):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id").copy(); fr["key"] = fr.display_name.map(canon)
    fr = fr.merge(TDQ[TDQ.week == w][["key", "td"]], on="key", how="left")
    cheap = (fr.salary < 4000) & fr.pos.isin(["RB", "WR", "TE", "QB"])
    mk = pd.to_numeric(fr.market_points, errors="coerce"); dk = pd.to_numeric(fr.dk_ppg, errors="coerce"); real = mk.notna() & ((mk - dk).abs() >= 0.01)
    for arm, score in (("cheapmkt4", mk.where(real)), ("cheaptd4", fr.td)):
        s_ = score.where(cheap); cut = s_.quantile(2 / 3)
        bonus = np.where(cheap & s_.notna() & (s_ >= cut), 4.0, 0.0)
        pd.DataFrame({"dk_player_id": fr.dk_player_id.astype("Int64"), "display_name": fr.display_name, "pos": fr.pos, "salary": fr.salary,
                      "pred_own": (bonus / 0.20).round(4), "bonus_points": bonus}).to_csv(out / f"{arm}-w{w}.csv", index=False)
        print(f"W{w} {arm}: {int((bonus > 0).sum())} cheap players get +4: " + ", ".join(fr.display_name[bonus > 0].head(8)), flush=True)
