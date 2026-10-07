"""The anytime-touchdown market as a pre-lock TAIL input: for each week, the last prop snapshot before the main-slate lock,
each player's implied anytime-TD probability (mean over bookmakers of the price-implied probability), joined to the frame;
then the same lift / residual slopes as attribution.py (controls: projection, salary, projected ownership). Usage: OUT_DIR"""
import importlib.util, sys
from collections import Counter
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("WSS", HERE / "winners_strategy_study.py"); WSS = importlib.util.module_from_spec(spec); sys.modules["WSS"] = WSS; spec.loader.exec_module(WSS)
MS = WSS.MS
from google.cloud import bigquery
c = bigquery.Client()
q = """WITH lk AS (SELECT week, MIN(commence_time) lock FROM `nfl_raw.prop_lines` WHERE season = 2026 AND week BETWEEN 1 AND 4
            AND EXTRACT(DAYOFWEEK FROM commence_time AT TIME ZONE 'America/Chicago') = 1 GROUP BY week),
     snap AS (SELECT p.week, MAX(p.snapshot_ts) ts FROM `nfl_raw.prop_lines` p JOIN lk USING (week)
              WHERE p.season = 2026 AND TIMESTAMP(p.snapshot_ts) < lk.lock AND p.market = 'player_anytime_td' GROUP BY p.week)
SELECT p.week, p.player, p.bookmaker, p.price, p.outcome_name, p.snapshot_ts FROM `nfl_raw.prop_lines` p JOIN snap ON p.week = snap.week AND p.snapshot_ts = snap.ts
WHERE p.season = 2026 AND p.market = 'player_anytime_td'"""
pl = c.query(q).to_dataframe(); print("prop rows", len(pl), "markets per week:", pl.groupby("week").snapshot_ts.max().to_dict(), flush=True)
pl = pl[pl.outcome_name.astype(str).str.lower().isin(["yes", "over"]) | pl.outcome_name.isna() | (pl.outcome_name.astype(str) == pl.player.astype(str))]
def implied(a):
    a = float(a); return 100 / (a + 100) if a > 0 else -a / (-a + 100)
pl["p"] = pl.price.apply(implied); td = pl.groupby(["week", "player"]).p.mean().reset_index(); td["key"] = td.player.astype(str).map(MS.canon)
out = Path(sys.argv[1]); rows = []
for w in (1, 2, 3, 4):
    W, fr, f = WSS.load_week(w); N = len(f); fr = fr.copy()
    m = td[td.week == w].set_index("key").p; fr["td_prob"] = fr.fname.map(m)
    top = f[f["rank"] <= 0.01 * N]; ct = Counter(i for v in top.ix for i in v if i >= 0); cf = Counter(i for v in f.ix for i in v if i >= 0)
    fr["top_share"] = [ct.get(i, 0) / len(top) for i in range(len(fr))]; fr["field_share"] = [cf.get(i, 0) / N for i in range(len(fr))]
    fr["lift"] = (fr.top_share + 0.002) / (fr.field_share + 0.002); fr["resid"] = fr.actual - fr.proj
    sk = fr[fr.pos.isin(["RB", "WR", "TE"]) & (fr.field_share >= 0.002) & fr.eligible & fr.td_prob.notna()].copy()
    sk["td_per_proj"] = sk.td_prob / (sk.proj + 1.0)
    print(f"W{w}: {len(sk)} skill players with a TD line (of {int((fr.pos.isin(['RB','WR','TE']) & (fr.field_share >= 0.002)).sum())}); mean TD prob {sk.td_prob.mean():.2f}", flush=True)
    feats = ["td_prob", "td_per_proj"]; ctrl = [c_ for c_ in ("proj", "salary", "pown") if sk[c_].notna().mean() > 0.5]
    z = sk.groupby("pos")[feats + ctrl].transform(lambda s: (s - s.mean()) / (s.std() + 1e-9)).fillna(0.0)
    for cc in feats:
        a = float(np.average(z[cc], weights=sk.top_share + 1e-9) - np.average(z[cc], weights=sk.field_share + 1e-9))
        X = np.column_stack([np.ones(len(sk))] + [z[k].values for k in ctrl] + [z[cc].values]); dof = max(1, len(sk) - X.shape[1])
        y = np.log(sk.lift.values); b, *_ = np.linalg.lstsq(X, y, rcond=None); r = y - X @ b; t = b[-1] / np.sqrt((np.linalg.pinv(X.T @ X) * (r @ r / dof))[-1, -1] + 1e-12)
        yr = sk.resid.values; br, *_ = np.linalg.lstsq(X, yr, rcond=None); rr = yr - X @ br; tr = br[-1] / np.sqrt((np.linalg.pinv(X.T @ X) * (rr @ rr / dof))[-1, -1] + 1e-12)
        rows.append({"week": w, "feature": cc, "n": len(sk), "winners_minus_field_z": round(a, 3), "lift_slope": round(float(b[-1]), 3), "lift_t": round(float(t), 2), "resid_slope_pts": round(float(br[-1]), 2), "resid_t": round(float(tr), 2)})
df = pd.DataFrame(rows); df.to_csv(out / "attribution_td.csv", index=False); print(df.to_string())
print("\npooled:"); print(df.groupby("feature")[["winners_minus_field_z", "lift_slope", "lift_t", "resid_slope_pts", "resid_t"]].mean().round(3).to_string())
