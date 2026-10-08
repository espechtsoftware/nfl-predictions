"""Task 3a: what exactly is the frame's epa_per_dropback_allowed_l6? Compare the W3/W4 T-70 frame values to recomputations from pbp."""
import sys, json; sys.path.insert(0, ".")
from pathlib import Path
import numpy as np, pandas as pd
from bqh import q
CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
# per-game EPA per dropback allowed, 2026 (and 2025 for cross-season windows)
g = q("""SELECT season, week, defteam d, AVG(epa) epa_db, COUNT(*) n FROM `nfl_raw.pbp`
         WHERE season_type = 'REG' AND qb_dropback = 1 AND epa IS NOT NULL AND season IN (2025, 2026) GROUP BY 1, 2, 3""")
g["epa_db"] = g.epa_db.astype(float)
prod = q("""SELECT team d, season, week, epa_per_dropback_allowed_l6 v FROM `nfl_features.defense_week_allowed` WHERE season = 2026""")
for w in (3, 4):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet")
    print(f"\n===== W{w} frame: {len(fr)} rows; positions {fr.pos.value_counts().to_dict()}; slate_type {fr.slate_type.unique().tolist()}")
    games = fr[["team", "opp"]].drop_duplicates().apply(lambda r: "-".join(sorted([str(r.team), str(r.opp)])), axis=1).unique()
    print(f"games in frame ({len(games)}): {sorted(games)}")
    f = fr[fr.pos == "QB"][["display_name", "team", "opp", "epa_per_dropback_allowed_l6"]].copy()
    f["v"] = pd.to_numeric(f.epa_per_dropback_allowed_l6, errors="coerce")
    fo = f.groupby("opp").v.agg(["min", "max", "count"]).reset_index().rename(columns={"opp": "d"})
    gg = g[g.season == 2026]
    # candidate definitions for week-w value of defense d
    rows = []
    for d in fo.d:
        h = gg[(gg.d == d) & (gg.week < w)].sort_values("week")
        prev = g[(g.d == d) & (g.season == 2025)].sort_values("week")
        rows.append({"d": d, "games_before_w": len(h), "weeks": ",".join(map(str, h.week)),
                     "A_l6_strict_prior(all games<w)": h.epa_db.tail(6).mean() if len(h) else np.nan,
                     "B_stale(all games<w except the latest)": h.epa_db.iloc[:-1].tail(6).mean() if len(h) > 1 else np.nan,
                     "C_cross_season_l6": pd.concat([prev.epa_db, h.epa_db]).tail(6).mean()})
    R = fo.merge(pd.DataFrame(rows), on="d")
    pr = prod.copy(); pr["v"] = pr.v.astype(float)
    lastrow = pr[pr.week < w].sort_values("week").groupby("d").tail(1)[["d", "week", "v"]].rename(columns={"week": "prod_latest_row_week", "v": "prod_latest_row_value"})
    R = R.merge(lastrow, on="d", how="left")
    for c in ["A_l6_strict_prior(all games<w)", "B_stale(all games<w except the latest)", "C_cross_season_l6", "prod_latest_row_value"]:
        R["match_" + c[:1] if c[0] in "ABC" else "match_prod"] = np.isclose(R["min"], R[c], atol=1e-9)
    print(R.round(4).to_string(index=False))
    print("frame value == B (stale) for", int(np.isclose(R["min"], R["B_stale(all games<w except the latest)"], atol=1e-9).sum()), "of", len(R),
          "| == A (strict prior, all games) for", int(np.isclose(R["min"], R["A_l6_strict_prior(all games<w)"], atol=1e-9).sum()),
          "| == production latest built row for", int(np.isclose(R["min"], R["prod_latest_row_value"], atol=1e-9).sum()))
