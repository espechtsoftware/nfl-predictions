"""Time of possession and passes to tight ends (the operator 10-07: "I'm wondering if tough defenses make it so that we have
the ball less and they have to quickly throw it to a tight end"). Regular seasons 2014-2025 from play-by-play (nfl_raw.pbp):
per offense game, time of possession (sum of its drives' drive_time_of_possession), pass attempts, targets by the
receiver's position (player_week_role), short targets (air yards <= 5, the stand-in for quick throws; pbp has no
time-to-throw), the opponent's point-in-time pass defense (EPA allowed per dropback over its previous 6 games that season)
and the Vegas implied team total. The chain is tested link by link, within the same offense-season."""
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client()
Q = """
WITH pb AS (SELECT season, week, game_id, posteam, defteam, fixed_drive, drive_time_of_possession top_str, pass_attempt, rush_attempt,
                   qb_dropback, epa, air_yards, receiver_player_id
            FROM `nfl_raw.pbp` WHERE season_type = 'REG' AND season BETWEEN 2014 AND 2025 AND posteam IS NOT NULL AND defteam IS NOT NULL),
 drives AS (SELECT season, week, game_id, posteam, fixed_drive, ANY_VALUE(top_str) top_str FROM pb WHERE fixed_drive IS NOT NULL GROUP BY 1, 2, 3, 4, 5),
 top AS (SELECT season, week, game_id, posteam,
           SUM(SAFE_CAST(SPLIT(top_str, ':')[SAFE_OFFSET(0)] AS INT64) * 60 + SAFE_CAST(SPLIT(top_str, ':')[SAFE_OFFSET(1)] AS INT64)) top_sec
         FROM drives GROUP BY 1, 2, 3, 4),
 off AS (SELECT pb.season, pb.week, pb.game_id, pb.posteam, ANY_VALUE(pb.defteam) opp,
           COUNTIF(pb.pass_attempt = 1) att, COUNTIF(pb.rush_attempt = 1) rush,
           COUNTIF(pb.pass_attempt = 1 AND pb.receiver_player_id IS NOT NULL) tgt,
           COUNTIF(pb.pass_attempt = 1 AND r.position = 'TE') te_tgt, COUNTIF(pb.pass_attempt = 1 AND r.position = 'WR') wr_tgt,
           COUNTIF(pb.pass_attempt = 1 AND r.position = 'RB') rb_tgt,
           COUNTIF(pb.pass_attempt = 1 AND pb.receiver_player_id IS NOT NULL AND pb.air_yards <= 5) short_tgt,
           COUNTIF(pb.pass_attempt = 1 AND r.position = 'TE' AND pb.air_yards <= 5) te_short_tgt,
           AVG(IF(pb.pass_attempt = 1 AND r.position = 'TE', pb.air_yards, NULL)) te_adot
         FROM pb LEFT JOIN `nfl_features.player_week_role` r ON r.gsis_id = pb.receiver_player_id AND r.season = pb.season AND r.week = pb.week
         GROUP BY 1, 2, 3, 4),
 dg AS (SELECT season, week, defteam d, AVG(epa) epa_db FROM pb WHERE qb_dropback = 1 AND epa IS NOT NULL GROUP BY 1, 2, 3),
 pe AS (SELECT season, week, d, AVG(epa_db) OVER v epa_l6, COUNT(*) OVER v n_epa FROM dg
        WINDOW v AS (PARTITION BY season, d ORDER BY week ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING)),
 sch AS (SELECT game_id, season, week, home_team, away_team, total_line, spread_line, home_score, away_score FROM `nfl_raw.schedules` WHERE game_type = 'REG')
SELECT off.*, top.top_sec, o2.top_sec opp_top_sec, pe.epa_l6, pe.n_epa,
       IF(off.posteam = sch.home_team, (sch.total_line + sch.spread_line) / 2, (sch.total_line - sch.spread_line) / 2) itt,
       IF(off.posteam = sch.home_team, sch.home_score - sch.away_score, sch.away_score - sch.home_score) margin
FROM off JOIN top USING (season, week, game_id, posteam)
JOIN top o2 ON o2.game_id = off.game_id AND o2.posteam = off.opp
LEFT JOIN pe ON pe.season = off.season AND pe.week = off.week AND pe.d = off.opp
JOIN sch ON sch.game_id = off.game_id"""
D = BQ.query(Q).to_dataframe()
for c in ("att", "rush", "tgt", "te_tgt", "wr_tgt", "rb_tgt", "short_tgt", "te_short_tgt", "te_adot", "top_sec", "opp_top_sec", "epa_l6", "itt", "margin"):
    D[c] = pd.to_numeric(D[c], errors="coerce").astype(float)
D = D[(D.tgt > 0) & D.top_sec.notna() & D.opp_top_sec.notna()].copy()
D["top_min"] = D.top_sec / 60; D["top_share"] = D.top_sec / (D.top_sec + D.opp_top_sec)
D["te_share"] = D.te_tgt / D.tgt; D["short_share"] = D.short_tgt / D.tgt; D["te_share_of_short"] = D.te_short_tgt / D.short_tgt.replace(0, np.nan)
D["os"] = D.season.astype(str) + D.posteam
print(f"offense games 2014-2025: {len(D):,}; mean time of possession {D.top_min.mean():.1f} min (sd {D.top_min.std():.1f}); "
      f"TE targets per game {D.te_tgt.mean():.1f}, TE share {D.te_share.mean():.3f}")
def within(df, c):
    return df[c] - df.groupby("os")[c].transform("mean")
W = D.copy()
for c in ("top_share", "top_min", "att", "rush", "te_tgt", "te_share", "short_share", "te_share_of_short", "te_adot", "wr_tgt", "rb_tgt", "itt", "margin", "epa_l6"):
    W[c + "_w"] = within(W, c)
print("\n(1) LINK 2: time of possession vs passes to tight ends (correlations; 'within' = the same offense-season)")
for y in ("te_tgt", "te_share", "att", "short_share", "te_share_of_short"):
    raw = D.top_share.corr(D[y]); wi = W.top_share_w.corr(W[y + "_w"])
    print(f"  time-of-possession share vs {y:18s}: raw r {raw:+.3f}; within offense-season r {wi:+.3f}")
W["top_third"] = pd.qcut(W.top_share_w, 3, labels=["less ball (own low third)", "middle", "more ball (own high third)"])
print("\n(2) by the game's time of possession relative to the same offense-season's average:")
print(W.groupby("top_third", observed=True).agg(top_min=("top_min", "mean"), att=("att", "mean"), rush=("rush", "mean"), te_tgt=("te_tgt", "mean"),
      te_share=("te_share", "mean"), wr_tgt=("wr_tgt", "mean"), rb_tgt=("rb_tgt", "mean"), short_share=("short_share", "mean"),
      te_share_of_short=("te_share_of_short", "mean"), te_adot=("te_adot", "mean"), margin=("margin", "mean"), games=("att", "size")).round(3).to_string())
E = W.dropna(subset=["epa_l6"]).copy(); E = E[E.n_epa >= 3]
E["epa_z"] = (E.epa_l6 - E.groupby(["season", "week"]).epa_l6.transform("mean")) / E.groupby(["season", "week"]).epa_l6.transform("std")
E["def_third"] = pd.qcut(E.groupby(["season", "week"]).epa_l6.rank(pct=True), 3, labels=["tough pass D", "middle", "soft pass D"])
print(f"\n(3) LINK 1: does a tough pass defense (opponent's EPA allowed per dropback, previous 6 games, point-in-time) cut our time of possession? ({len(E):,} games)")
print(E.groupby("def_third", observed=True).agg(top_min=("top_min", "mean"), top_share=("top_share", "mean"), top_share_w=("top_share_w", "mean"),
      att=("att", "mean"), te_tgt=("te_tgt", "mean"), te_share=("te_share", "mean"), te_share_w=("te_share_w", "mean"), short_share=("short_share", "mean"),
      itt=("itt", "mean")).round(3).to_string())
import numpy.linalg as la
def reg(y, xs, df):
    df = df[[y] + xs].astype(float).dropna()
    X = np.column_stack([df[x].to_numpy(dtype=float) for x in xs] + [np.ones(len(df))]); yy = df[y].to_numpy(dtype=float)
    b, *_ = la.lstsq(X, yy, rcond=None); r = yy - X @ b; s2 = r @ r / (len(yy) - X.shape[1]); se = np.sqrt(np.diag(s2 * la.inv(X.T @ X))); return b, b / se
E["itt_w2"] = E.itt_w
for y in ("top_share_w", "te_share_w"):
    b, t = reg(y, ["epa_z", "itt_w2"], E)
    print(f"  {y}: per 1 sd SOFTER pass defense {b[0]:+.4f} (t {t[0]:+.1f}); per 1 point of implied total {b[1]:+.4f} (t {t[1]:+.1f})")
b, t = reg("te_share_w", ["top_share_w", "margin_w"], W.dropna(subset=["margin_w"]))
print(f"\n(4) TE share within offense-season ~ time-of-possession share + score margin (game script): TOP {b[0]:+.4f} per unit share (t {t[0]:+.1f}), "
      f"i.e. {b[0] * 0.05:+.4f} per 5 points of possession share; margin {b[1]:+.5f} per point (t {t[1]:+.1f})")
