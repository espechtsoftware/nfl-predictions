"""PASS-CATCHING tight ends only (the operator 10-07: "Since there are two types of tight ends, ones that do more blocking and
ones that are pass catching tight ends, is it possible that the blocking ones are skewing these results?"). Regular
seasons 2014-2025. A team-game's pass-catching TE is, point-in-time, the team's TE with the highest average target share
in HIS earlier games that season (3+ games), kept only if that share is >= 15%; the team's WR1 is chosen the same way.
For him: DK points, his target share in the game, booms (15+ / 20+), and QB + him vs QB + WR1. By the opponent's
point-in-time pass defense (EPA allowed per dropback, previous 6 games), within the same offense-season with the Vegas
implied total controlled; and by the game's realized first downs and time of possession."""
import numpy as np, pandas as pd
import numpy.linalg as la
from google.cloud import bigquery
BQ = bigquery.Client()
Q = """
WITH a AS (SELECT a.season, a.week, a.team, a.gsis_id, r.position pos, a.dk_points dk, IFNULL(a.targets, 0) tg
           FROM `nfl_features.player_week_actuals` a JOIN `nfl_features.player_week_role` r ON r.gsis_id = a.gsis_id AND r.season = a.season AND r.week = a.week
           WHERE a.season BETWEEN 2014 AND 2025 AND r.position IN ('QB', 'RB', 'WR', 'TE')),
 tt AS (SELECT season, week, team, SUM(tg) team_tg FROM a GROUP BY 1, 2, 3),
 sh AS (SELECT a.*, SAFE_DIVIDE(a.tg, tt.team_tg) tsh FROM a JOIN tt USING (season, week, team)),
 pit AS (SELECT sh.*, AVG(tsh) OVER w prior_tsh, COUNT(*) OVER w n_prior FROM sh
         WINDOW w AS (PARTITION BY season, gsis_id ORDER BY week ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)),
 te AS (SELECT season, week, team, ARRAY_AGG(STRUCT(gsis_id, dk, tsh, prior_tsh) ORDER BY prior_tsh DESC LIMIT 1)[OFFSET(0)] t
        FROM pit WHERE pos = 'TE' AND n_prior >= 3 AND prior_tsh IS NOT NULL GROUP BY 1, 2, 3),
 wr AS (SELECT season, week, team, ARRAY_AGG(STRUCT(gsis_id, dk, tsh, prior_tsh) ORDER BY prior_tsh DESC LIMIT 1)[OFFSET(0)] w
        FROM pit WHERE pos = 'WR' AND n_prior >= 3 AND prior_tsh IS NOT NULL GROUP BY 1, 2, 3),
 qb AS (SELECT season, week, team, MAX(dk) qb FROM a WHERE pos = 'QB' GROUP BY 1, 2, 3),
 pb AS (SELECT season, week, game_id, posteam, defteam, fixed_drive, drive_time_of_possession top_str, qb_dropback, epa, first_down
        FROM `nfl_raw.pbp` WHERE season_type = 'REG' AND season BETWEEN 2014 AND 2025 AND posteam IS NOT NULL AND defteam IS NOT NULL),
 drives AS (SELECT game_id, posteam, fixed_drive, ANY_VALUE(top_str) top_str FROM pb WHERE fixed_drive IS NOT NULL GROUP BY 1, 2, 3),
 top AS (SELECT game_id, posteam, SUM(SAFE_CAST(SPLIT(top_str, ':')[SAFE_OFFSET(0)] AS INT64) * 60 + SAFE_CAST(SPLIT(top_str, ':')[SAFE_OFFSET(1)] AS INT64)) top_sec
         FROM drives GROUP BY 1, 2),
 og AS (SELECT season, week, game_id, posteam, ANY_VALUE(defteam) opp, COUNTIF(first_down = 1) fd FROM pb GROUP BY 1, 2, 3, 4),
 dg AS (SELECT season, week, defteam d, AVG(epa) epa_db FROM pb WHERE qb_dropback = 1 AND epa IS NOT NULL GROUP BY 1, 2, 3),
 pe AS (SELECT season, week, d, AVG(epa_db) OVER v epa_l6, COUNT(*) OVER v n_epa FROM dg
        WINDOW v AS (PARTITION BY season, d ORDER BY week ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING)),
 sch AS (SELECT game_id, home_team, total_line, spread_line FROM `nfl_raw.schedules` WHERE game_type = 'REG')
SELECT og.season, og.week, og.posteam team, og.opp, og.fd, top.top_sec, o2.top_sec opp_top_sec, pe.epa_l6, pe.n_epa,
       IF(og.posteam = sch.home_team, (sch.total_line + sch.spread_line) / 2, (sch.total_line - sch.spread_line) / 2) itt,
       te.t.dk te_dk, te.t.tsh te_tsh, te.t.prior_tsh te_prior, wr.w.dk wr_dk, wr.w.prior_tsh wr_prior, qb.qb
FROM og JOIN te ON te.season = og.season AND te.week = og.week AND te.team = og.posteam
JOIN wr ON wr.season = og.season AND wr.week = og.week AND wr.team = og.posteam
JOIN qb ON qb.season = og.season AND qb.week = og.week AND qb.team = og.posteam
JOIN top ON top.game_id = og.game_id AND top.posteam = og.posteam
JOIN top o2 ON o2.game_id = og.game_id AND o2.posteam = og.opp
JOIN pe ON pe.season = og.season AND pe.week = og.week AND pe.d = og.opp
JOIN sch ON sch.game_id = og.game_id"""
D = BQ.query(Q).to_dataframe()
for c in ("fd", "top_sec", "opp_top_sec", "epa_l6", "itt", "te_dk", "te_tsh", "te_prior", "wr_dk", "wr_prior", "qb"):
    D[c] = pd.to_numeric(D[c], errors="coerce").astype(float)
D = D[(D.n_epa >= 3)].dropna(subset=["epa_l6", "itt", "te_dk", "wr_dk", "qb", "top_sec", "opp_top_sec"]).copy()
ALL = D.copy(); D = D[D.te_prior >= 0.15].copy()
print(f"team-games 2014-2025 with a point-in-time pass-catching TE (prior target share >= 15%): {len(D):,} of {len(ALL):,} "
      f"(his prior share: median {D.te_prior.median():.3f}); excluded as blocking/low-target TE rooms: {len(ALL) - len(D):,}")
D["top_min"] = D.top_sec / 60; D["os"] = D.season.astype(str) + D.team
D["qb_te"] = D.qb + D.te_dk; D["qb_wr"] = D.qb + D.wr_dk; D["te15"] = D.te_dk >= 15; D["te20"] = D.te_dk >= 20
D["def_third"] = pd.qcut(D.groupby(["season", "week"]).epa_l6.rank(pct=True), 3, labels=["tough pass D", "middle", "soft pass D"])
cols = ["te_dk", "te_tsh", "te15", "te20", "wr_dk", "qb", "qb_te", "qb_wr"]
print("\n(1) raw means by the opponent's pass defense (EPA allowed per dropback, previous 6 games):")
T = D.assign(te_beats_wr=D.qb_te > D.qb_wr, qbte45=D.qb_te >= 45, qbwr45=D.qb_wr >= 45)
print(T.groupby("def_third", observed=True)[cols + ["te_beats_wr", "qbte45", "qbwr45", "itt"]].mean().round(3).to_string())
W = D.copy()
for c in ["te_dk", "te_tsh", "te15", "te20", "wr_dk", "qb", "qb_te", "qb_wr", "itt", "epa_l6", "fd", "top_min"]:
    W[c + "_w"] = W[c].astype(float) - W.groupby("os")[c].transform(lambda s: s.astype(float).mean())
W["epa_z"] = W.epa_l6_w / W.epa_l6.std()
def reg(y):
    df = W[[y + "_w", "epa_z", "itt_w"]].dropna(); X = np.column_stack([df.epa_z, df.itt_w, np.ones(len(df))]); yy = df[y + "_w"].to_numpy(float)
    b, *_ = la.lstsq(X, yy, rcond=None); r = yy - X @ b; s2 = r @ r / (len(yy) - 3); se = np.sqrt(np.diag(s2 * la.inv(X.T @ X)))
    return f"{-b[0]:+.3f} (t {-b[0] / se[0]:+.1f})"
print("\n(2) within offense-season, implied total controlled: effect of a 1-sd TOUGHER pass defense (positive = more against tough D)")
for y in ("te_dk", "te_tsh", "te15", "te20", "wr_dk", "qb_te", "qb_wr"):
    print(f"  {y:7s}: {reg(y)}")
print("\n(3) the pass-catching TE by the game's realized first downs and possession (thirds within the same offense-season):")
W["fd_third"] = pd.qcut(W.fd_w, 3, labels=["fewer first downs", "about usual", "more first downs"])
W["top_third"] = pd.qcut(W.top_min_w, 3, labels=["less ball", "middle", "more ball"])
for g in ("fd_third", "top_third"):
    print(W.groupby(g, observed=True).agg(first_downs=("fd", "mean"), possession=("top_min", "mean"), te_target_share=("te_tsh", "mean"),
          te_dk=("te_dk", "mean"), te20=("te20", "mean"), wr1_dk=("wr_dk", "mean"), games=("fd", "size")).round(3).to_string())
B = ALL[ALL.te_prior < 0.15]
print(f"\n(4) for contrast, the excluded low-target TE rooms ({len(B):,} team-games): mean top TE DK {B.te_dk.mean():.2f}, target share {B.te_tsh.mean():.3f}; "
      f"pass-catching TEs: DK {D.te_dk.mean():.2f}, share {D.te_tsh.mean():.3f}")
print("\n(5) the stack head-to-head WITHIN offense-season (implied total controlled), per 1-sd TOUGHER pass defense:")
W["te_beats_wr"] = (W.qb_te > W.qb_wr).astype(float); W["qbte45"] = (W.qb_te >= 45).astype(float); W["qbwr45"] = (W.qb_wr >= 45).astype(float)
W["diff"] = W.qb_te - W.qb_wr
for c in ("te_beats_wr", "qbte45", "qbwr45", "diff"):
    W[c + "_w"] = W[c] - W.groupby("os")[c].transform("mean")
for y in ("te_beats_wr", "qbte45", "qbwr45", "diff"):
    print(f"  {y:12s}: {reg(y)}")
print(f"  pooled shares: QB+TE beats QB+WR1 {W.te_beats_wr.mean():.3f}; QB+TE >= 45 {W.qbte45.mean():.3f}; QB+WR1 >= 45 {W.qbwr45.mean():.3f}")
