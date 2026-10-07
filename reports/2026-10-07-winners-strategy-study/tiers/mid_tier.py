"""The $6,000-7,999 skill tier, where our picking loses 6 points per lineup (W1-4): does our projection rank that tier
worse than the market (props-implied) or Fantasy Points (W4), and which way are its errors? Aggregates only."""
import json, re, sys, unicodedata
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
FP4 = pd.read_csv(Path.home() / ".cache/laptop-agent/rehearsal/inputs/proj_fp-w4.csv")
def canon(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower(); s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s); return re.sub(r"[^a-z]", "", s)
out = []
for w in (1, 2, 3, 4):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("dk_player_id").copy(); fr["key"] = fr.display_name.map(canon)
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    own = BQ.query(f"SELECT display_name, ANY_VALUE(fpts) fpts, ANY_VALUE(pct_drafted) own FROM `nfl_raw.contest_ownership` WHERE contest_id = '{cid}' GROUP BY 1").to_dataframe(); own["key"] = own.display_name.map(canon)
    fr = fr.merge(own[["key", "fpts", "own"]], on="key", how="left")
    fr["ours"] = pd.to_numeric(fr.mean_projection, errors="coerce"); mk = pd.to_numeric(fr.market_points, errors="coerce"); dk = pd.to_numeric(fr.dk_ppg, errors="coerce")
    fr["mkt"] = mk.where(mk.notna() & ((mk - dk).abs() >= 0.01))
    fr["fp"] = fr.dk_draftable_id.astype("Int64").astype(str).map(dict(zip(FP4.dk_draftable_id.astype("Int64").astype(str), FP4.fp))) if w == 4 else np.nan
    t = fr[fr.pos.isin(["RB", "WR", "TE"]) & (fr.salary >= 6000) & (fr.salary < 8000) & fr.fpts.notna()].copy(); t["week"] = w; out.append(t)
T = pd.concat(out, ignore_index=True)
print(f"$6,000-7,999 RB/WR/TE player-weeks: {len(T)} (with a prop line: {int(T.mkt.notna().sum())})")
for w, g in T.groupby("week"):
    m = g.mkt.notna()
    line = f"  W{w} n {len(g)}: Spearman with actual -- ours {g.ours.corr(g.fpts, method='spearman'):+.2f}"
    if m.sum() > 5: line += f", market {g.mkt[m].corr(g.fpts[m], method='spearman'):+.2f} (ours on the same {int(m.sum())}: {g.ours[m].corr(g.fpts[m], method='spearman'):+.2f})"
    if g.fp.notna().sum() > 5: line += f", FP {g.fp.corr(g.fpts, method='spearman'):+.2f}"
    line += f" | mean actual - ours {(g.fpts - g.ours).mean():+.1f}, MAE ours {(g.fpts - g.ours).abs().mean():.1f}" + (f", MAE market {(g.fpts - g.mkt)[m].abs().mean():.1f} vs ours {(g.fpts - g.ours)[m].abs().mean():.1f} on the same players" if m.sum() > 5 else "")
    print(line)
m = T.mkt.notna()
print(f"pooled on players with a line: Spearman ours {T.ours[m].corr(T.fpts[m], method='spearman'):+.2f}, market {T.mkt[m].corr(T.fpts[m], method='spearman'):+.2f}; mean (ours - market) {(T.ours - T.mkt)[m].mean():+.2f}")
T["ours_minus_mkt"] = T.ours - T.mkt
hi = T[m & (T.ours_minus_mkt >= 1.5)]; lo = T[m & (T.ours_minus_mkt <= -1.5)]
print(f"where ours exceeds the market by 1.5+: n {len(hi)}, actual - ours {(hi.fpts - hi.ours).mean():+.1f}, field ownership {hi.own.mean():.1f}%")
print(f"where the market exceeds ours by 1.5+: n {len(lo)}, actual - ours {(lo.fpts - lo.ours).mean():+.1f}, field ownership {lo.own.mean():.1f}%")
