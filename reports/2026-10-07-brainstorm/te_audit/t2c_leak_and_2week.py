"""Task 2c: (i) a direct leakage check of the history EPA measure (a deliberately leaky same-game window for contrast);
(ii) how much a two-week (W3-W4) slice swings season to season under the frame-style stale measure."""
import sys; sys.path.insert(0, ".")
import numpy as np, pandas as pd
from bqh import q
from hist_lib import *
L = q("""
WITH dgame AS (SELECT season, week, defteam d, AVG(IF(qb_dropback = 1, epa, NULL)) e FROM `nfl_raw.pbp`
               WHERE season_type = 'REG' AND defteam IS NOT NULL AND season BETWEEN 2014 AND 2025 GROUP BY 1, 2, 3)
SELECT season, week, d, e,
  AVG(e) OVER (PARTITION BY d, season ORDER BY week ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) strict_prior,
  COUNT(e) OVER (PARTITION BY d, season ORDER BY week ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) n_prior,
  AVG(e) OVER (PARTITION BY d, season ORDER BY week ROWS BETWEEN 5 PRECEDING AND CURRENT ROW) leaky_incl_current
FROM dgame""")
L = L[L.n_prior >= 3]
print(f"(i) defense-games 2014-2025 with 3+ prior games: {len(L):,}")
print(f"    corr(strict-prior 6-game measure, this game's EPA allowed) = {L.strict_prior.corr(L.e):.3f}  <- the reviewer's / production's definition")
print(f"    corr(leaky window incl. this game, this game's EPA allowed) = {L.leaky_incl_current.corr(L.e):.3f}  <- what leakage would look like")
P0 = prep("panel.parquet")
rows = []
for s in range(2014, 2027):
    for defn in ("max", "sal"):
        P = add_outcomes(P0[(P0.season == s) & P0.week.isin([3, 4])], defn).dropna(subset=["QB", "TE1", "WR1", "epa_stale"])
        P["third"] = thirds(P, "epa_stale")
        g = P.groupby("third", observed=True)
        r_s = g.qbte45.mean()["strong"] / max(g.qbwr45.mean()["strong"], 1e-9); r_w = g.qbte45.mean()["weak"] / max(g.qbwr45.mean()["weak"], 1e-9)
        rows.append({"season": s, "defn": defn, "n": len(P), "P(TE1>WR1) strong": round(g.te_beats_wr.mean()["strong"], 3),
                     "P(TE1>WR1) weak": round(g.te_beats_wr.mean()["weak"], 3),
                     "diff strong-weak": round(g.te_beats_wr.mean()["strong"] - g.te_beats_wr.mean()["weak"], 3),
                     "TE/WR boom ratio strong / weak": round(r_s / r_w, 2) if r_w > 0 else np.nan})
R = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print("\n(ii) weeks 3-4 of each season, frame-style stale pass-D measure (1-2 games), all team-games; 2026 = all 2026 W3-W4 games")
for defn in ("max", "sal"):
    X = R[R.defn == defn]
    print(f"--- outcome definition '{defn}'"); print(X.drop(columns="defn").to_string(index=False))
    h = X[X.season <= 2025]
    print(f"    2014-2025: diff strong-weak mean {h['diff strong-weak'].mean():+.3f}, sd {h['diff strong-weak'].std():.3f}, range {h['diff strong-weak'].min():+.3f} to {h['diff strong-weak'].max():+.3f}")
