"""When do tight ends have big games? The operator 10-07: "My suspicion is that happens when it's a strong defense and they're
not going to be able to throw to the wide receiver as much ... are they using a running back more often? So maybe in those
cases, a stack with a quarterback, running back, and a tight end."

History 2014-2025 regular seasons (+ 2026 W1-4 printed separately), weeks 4+ (each defense needs 3+ prior games that
season). POINT-IN-TIME defense strength: a defense's average DK points ALLOWED per game to WRs / TEs / RBs / QBs over its
earlier games that season only (no look-ahead), as percentiles within the season-week (low = strong). Outcomes per offense
game: the team's TE1 / WR1 / RB1 / QB DK points, TE / RB target shares, booms, and stack sums. Comparisons within the
same offense-season (the game vs that offense's own average) and with the Vegas implied team total as a control."""
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client()
Q = """
WITH g AS (SELECT season, week, home_team, away_team, total_line, spread_line FROM `nfl_raw.schedules` WHERE game_type = 'REG' AND season BETWEEN 2014 AND 2026),
 tg AS (SELECT season, week, home_team team, away_team opp, (total_line + spread_line) / 2 itt FROM g
        UNION ALL SELECT season, week, away_team, home_team, (total_line - spread_line) / 2 FROM g),
 p AS (SELECT a.season, a.week, a.team, r.position pos, a.dk_points dk, IFNULL(a.targets, 0) tg, IFNULL(a.carries, 0) ca
       FROM `nfl_features.player_week_actuals` a JOIN `nfl_features.player_week_role` r ON r.gsis_id = a.gsis_id AND r.season = a.season AND r.week = a.week
       WHERE r.position IN ('QB', 'RB', 'WR', 'TE') AND a.season BETWEEN 2014 AND 2026),
 o AS (SELECT season, week, team,
         MAX(IF(pos = 'QB', dk, NULL)) qb, MAX(IF(pos = 'TE', dk, NULL)) te1, MAX(IF(pos = 'WR', dk, NULL)) wr1, MAX(IF(pos = 'RB', dk, NULL)) rb1,
         SUM(IF(pos = 'WR', dk, 0)) wr_dk, SUM(IF(pos = 'TE', dk, 0)) te_dk, SUM(IF(pos = 'RB', dk, 0)) rb_dk,
         SUM(IF(pos = 'TE', tg, 0)) te_tg, SUM(IF(pos = 'WR', tg, 0)) wr_tg, SUM(IF(pos = 'RB', tg, 0)) rb_tg, SUM(tg) tm_tg,
         SUM(IF(pos = 'RB', ca, 0)) rb_ca, SUM(ca) tm_ca,
         ARRAY_AGG(IF(pos = 'WR', dk, NULL) IGNORE NULLS ORDER BY dk DESC LIMIT 2) wrs
       FROM p GROUP BY 1, 2, 3),
 og AS (SELECT o.*, tg.opp, tg.itt FROM o JOIN tg USING (season, week, team)),
 allowed AS (SELECT season, week, opp AS d, wr_dk, te_dk, rb_dk, qb FROM og),
 pit AS (SELECT season, week, d,
           AVG(wr_dk) OVER w wr_al, AVG(te_dk) OVER w te_al, AVG(rb_dk) OVER w rb_al, AVG(qb) OVER w qb_al, COUNT(*) OVER w n_prior
         FROM allowed WINDOW w AS (PARTITION BY season, d ORDER BY week ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING))
SELECT og.*, pit.wr_al, pit.te_al, pit.rb_al, pit.qb_al, pit.n_prior FROM og JOIN pit ON pit.season = og.season AND pit.week = og.week AND pit.d = og.opp"""
D = BQ.query(Q).to_dataframe()
D["wr2"] = D.wrs.map(lambda a: a[1] if a is not None and len(a) > 1 else np.nan)
for c in ("qb", "te1", "wr1", "rb1", "wr_dk", "te_dk", "rb_dk", "te_tg", "wr_tg", "rb_tg", "tm_tg", "rb_ca", "tm_ca", "itt", "wr_al", "te_al", "rb_al", "qb_al", "wr2"):
    D[c] = pd.to_numeric(D[c], errors="coerce")
D = D[(D.n_prior >= 3) & D.qb.notna() & D.te1.notna() & D.wr1.notna() & D.rb1.notna()].copy()
D["te_share"] = D.te_tg / D.tm_tg; D["rb_tg_share"] = D.rb_tg / D.tm_tg; D["rb_touch_share"] = (D.rb_ca + D.rb_tg) / (D.tm_ca + D.tm_tg)
D["qb_te"] = D.qb + D.te1; D["qb_wr"] = D.qb + D.wr1; D["qb_wr_wr"] = D.qb + D.wr1 + D.wr2; D["qb_rb_te"] = D.qb + D.rb1 + D.te1
D["te_boom"] = D.te1 >= 20; D["wr1_boom"] = D.wr1 >= 25
for c in ("wr_al", "te_al", "rb_al"):                                  # percentile within season-week; low = strong defense
    D[c + "_pct"] = D.groupby(["season", "week"])[c].rank(pct=True)
D["pass_al"] = D.wr_al + D.te_al; D["pass_al_pct"] = D.groupby(["season", "week"]).pass_al.rank(pct=True)
D["wr_def"] = pd.cut(D.wr_al_pct, [0, 1 / 3, 2 / 3, 1.0], labels=["strong vs WR", "middle", "weak vs WR"])
H = D[D.season <= 2025].copy(); N = D[D.season == 2026].copy()
H["os"] = H.season.astype(str) + H.team.astype(str)
OUT = ["te1", "te_share", "te_boom", "wr1", "wr1_boom", "rb1", "rb_touch_share", "qb", "qb_te", "qb_wr", "qb_wr_wr", "qb_rb_te"]
pd.set_option("display.width", 250)
print(f"history 2014-2025, weeks with 3+ prior defense games: {len(H):,} team-games ({H.season.nunique()} seasons)")
print("\n(1) raw means by the opponent's PIT strength against WRs (DK points it allowed to WRs per game so far that season)")
print(H.groupby("wr_def", observed=True)[OUT + ["itt"]].mean().round(3).to_string())
print("\n(2) WITHIN the same offense-season (each game minus that offense-season's mean), by the opponent's strength vs WRs")
W = H.copy()
for c in OUT + ["itt"]:
    W[c] = W[c].astype(float) - W.groupby("os")[c].transform(lambda s: s.astype(float).mean())
print(W.groupby("wr_def", observed=True)[OUT + ["itt"]].mean().round(3).to_string())
print("\n(3) regression within offense-season, controlling the implied team total: coefficient per 1 sd of the defense's"
      " allowed-to-WR (positive = more output against WEAKER WR defenses) and per 1 sd of allowed-to-TE")
import numpy.linalg as la
def within(df, cols):
    return df[cols].astype(float) - df.groupby("os")[cols].transform(lambda s: s.astype(float).mean())
Z = H.dropna(subset=["itt", "wr_al", "te_al", "rb_al"]).copy()
for c in ("wr_al", "te_al", "rb_al", "itt"):
    Z[c + "_z"] = (Z[c] - Z.groupby(["season", "week"])[c].transform("mean")) / Z.groupby(["season", "week"])[c].transform("std")
X = within(Z, ["wr_al_z", "te_al_z", "rb_al_z", "itt_z"]).values
rows = []
for y in ("te1", "te_share", "te_boom", "wr1", "rb1", "rb_touch_share", "qb", "qb_te", "qb_wr", "qb_rb_te", "qb_wr_wr"):
    yy = within(Z, [y]).values[:, 0]; Xc = np.column_stack([X, np.ones(len(X))])
    b, *_ = la.lstsq(Xc, yy, rcond=None); res = yy - Xc @ b; s2 = res @ res / (len(yy) - Xc.shape[1])
    se = np.sqrt(np.diag(s2 * la.inv(Xc.T @ Xc)))
    rows.append({"outcome": y, "per sd WR-allowed": f"{b[0]:+.3f} ({b[0] / se[0]:+.1f}t)", "per sd TE-allowed": f"{b[1]:+.3f} ({b[1] / se[1]:+.1f}t)",
                 "per sd RB-allowed": f"{b[2]:+.3f} ({b[2] / se[2]:+.1f}t)", "per sd implied total": f"{b[3]:+.3f} ({b[3] / se[3]:+.1f}t)"})
print(pd.DataFrame(rows).to_string(index=False))
print("\n(4) stacks by the opponent's strength vs WRs: share of games where each stack is the better one, and stack booms")
S = H.assign(te_beats_wr=H.qb_te > H.qb_wr, rbte_beats_wrwr=H.qb_rb_te > H.qb_wr_wr, qbte_45=H.qb_te >= 45, qbwr_45=H.qb_wr >= 45,
             qbrbte_60=H.qb_rb_te >= 60, qbwrwr_60=H.qb_wr_wr >= 60)
print(S.groupby("wr_def", observed=True)[["te_beats_wr", "rbte_beats_wrwr", "qbte_45", "qbwr_45", "qbrbte_60", "qbwrwr_60"]].mean().round(3).to_string())
print("\n(5) the extreme: the 10% strongest defenses vs WRs vs the rest")
S["top10"] = S.wr_al_pct <= 0.10
print(S.groupby("top10")[["te1", "te_share", "te_boom", "wr1", "rb1", "rb_touch_share", "te_beats_wr", "rbte_beats_wrwr", "qbte_45", "qbwr_45"]].mean().round(3).to_string())
print(f"\n2026 W4 (the only 2026 week with 3+ prior games): {len(N)} team-games; by strength vs WR:")
print(N.groupby("wr_def", observed=True)[["te1", "te_share", "wr1", "rb1", "qb_te", "qb_wr"]].mean().round(2).to_string())
