"""Two creative checks on W1-4 (aggregates only).
(1) LATE NEWS: each player's projection in the week's EARLIEST archived build frame vs the T-70 frame (delta = T-70 - early).
    Do late risers beat even the T-70 projection (does it under-react)? Are they under-owned by the field? Do the regulars
    hold them more than the field (the production panel's reg/rest shares)?
(2) GAME ENVIRONMENT FROM PLAYER PROPS: per game, the sum of every player's anytime-TD probability (the props market's implied
    touchdowns) vs the Vegas total; which better ranks the games by realized DK points of their skill players?"""
import importlib.util, json, re, sys, types, unicodedata
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text()); RUNS = Path.home() / "moneygate/inputs/runs"
spec = importlib.util.spec_from_file_location("wpvf", sys.argv[1]); M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
def canon(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower(); s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s); return re.sub(r"[^a-z]", "", s)
TDQ = BQ.query("""WITH lk AS (SELECT week, MIN(commence_time) lock FROM `nfl_raw.prop_lines` WHERE season = 2026 AND week BETWEEN 1 AND 22
      AND EXTRACT(DAYOFWEEK FROM commence_time AT TIME ZONE 'America/Chicago') = 1 GROUP BY week),
  snap AS (SELECT p.week, MAX(p.snapshot_ts) ts FROM `nfl_raw.prop_lines` p JOIN lk USING (week) WHERE p.season = 2026 AND TIMESTAMP(p.snapshot_ts) < lk.lock AND p.market = 'player_anytime_td' GROUP BY p.week)
  SELECT p.week, p.player, AVG(IF(p.price > 0, 100 / (p.price + 100), -p.price / (-p.price + 100))) td FROM `nfl_raw.prop_lines` p JOIN snap ON p.week = snap.week AND p.snapshot_ts = snap.ts
  WHERE p.season = 2026 AND p.market = 'player_anytime_td' GROUP BY 1, 2""").to_dataframe(); TDQ["key"] = TDQ.player.map(canon)
WEEKS = sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")); P, G = [], []
for w in WEEKS:
    t70 = Path(CFG["weeks"][str(w)]["t70_run"]); grp = int(json.loads((t70 / "receipt.json").read_text())["draft_group"])
    runs = sorted(d for d in RUNS.iterdir() if (d / "frame.parquet").exists() and json.loads((d / "receipt.json").read_text()).get("week") == w
                  and int(json.loads((d / "receipt.json").read_text()).get("draft_group", 0)) == grp)
    early = runs[0]; e = pd.read_parquet(early / "frame.parquet").drop_duplicates("dk_player_id"); f = pd.read_parquet(t70 / "frame.parquet").drop_duplicates("dk_player_id")
    f["key"] = f.display_name.map(canon); f["early"] = f.dk_player_id.map(dict(zip(e.dk_player_id, pd.to_numeric(e.mean_projection, errors="coerce"))))
    f["proj"] = pd.to_numeric(f.mean_projection, errors="coerce"); f["delta"] = f.proj - f.early
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    a = types.SimpleNamespace(season=2026, week=w, contest=cid, frame=str(t70 / "frame.parquet"), cohort=str(Path.home() / "private/regulars/cohort-2026w1-4.txt"),
                              entry_history=str(Path.home() / "private/moneygate/inputs/draftkings-contest-entry-history.csv"))
    d, _ = M.load_week(a); d["key"] = d.player.map(canon)
    f = f.merge(d[["key", "reg_share", "rest_share", "dk"]], on="key", how="left").merge(TDQ[TDQ.week == w][["key", "td"]], on="key", how="left")
    f["week"] = w; f["early_run"] = early.name[:15]; P.append(f[f.pos.isin(["QB", "RB", "WR", "TE"])])
    sk = f[f.pos.isin(["QB", "RB", "WR", "TE"]) & f.dk.notna()]
    g = sk.groupby("game_id").agg(total=("game_total", "max"), td_sum=("td", "sum"), pts=("dk", "sum")).reset_index(); g["week"] = w; G.append(g)
    print(f"W{w}: early frame {early.name[:15]} vs T-70 {t70.name[:15]}; players {len(sk)}; |delta| >= 1.5: {int((sk.delta.abs() >= 1.5).sum())}", flush=True)
X = pd.concat(P, ignore_index=True); X = X[X.dk.notna() & X.delta.notna() & (X.proj >= 3)]
X["move"] = np.select([X.delta >= 1.5, X.delta <= -1.5], ["riser", "faller"], "stable"); X["resid"] = X.dk - X.proj
X["own_per_proj"] = 100 * X.rest_share / X.proj; X["reg_lean"] = np.log((X.reg_share + 0.002) / (X.rest_share + 0.002))
print("\n(1) LATE NEWS (players projected >= 3 at T-70):")
print(X.groupby("move").agg(n=("dk", "size"), mean_delta=("delta", "mean"), actual_minus_t70=("resid", "mean"), field_own_pct=("rest_share", lambda s: 100 * s.mean()),
      own_per_proj_point=("own_per_proj", "mean"), regulars_lean=("reg_lean", "mean")).round(2).to_string())
print("  by week, actual - T-70 projection for risers / fallers: " + ", ".join(f"W{w} {g[g.move=='riser'].resid.mean():+.1f} / {g[g.move=='faller'].resid.mean():+.1f}" for w, g in X.groupby("week")))
G = pd.concat(G, ignore_index=True)
print("\n(2) GAME ENVIRONMENT: Spearman with the game's realized skill DK points, within week")
for w, g in G.groupby("week"):
    print(f"  W{w} games {len(g)}: Vegas total {g.total.corr(g.pts, method='spearman'):+.2f}, props TD sum {g.td_sum.corr(g.pts, method='spearman'):+.2f}; "
          f"top game by total ranked {int(g.pts.rank(ascending=False)[g.total.idxmax()])}, by TD sum {int(g.pts.rank(ascending=False)[g.td_sum.idxmax()])}")
G["res"] = G.groupby("week").apply(lambda g: g.td_sum - np.polyval(np.polyfit(g.total, g.td_sum, 1), g.total)).reset_index(level=0, drop=True)
print(f"  pooled: Spearman total {G.total.corr(G.pts, method='spearman'):+.2f}, TD sum {G.td_sum.corr(G.pts, method='spearman'):+.2f}, TD sum beyond the total {G.res.corr(G.pts - G.groupby('week').pts.transform('mean'), method='spearman'):+.2f} (n {len(G)})")
