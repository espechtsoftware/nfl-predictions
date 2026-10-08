"""The operator 10-07: "If you're going against a tough defense, you're likely going to get fewer first downs, which means
less time of possession." Regular seasons 2014-2025 (play-by-play). Two questions, kept apart:
(A) REALIZED: in games where the offense actually got fewer first downs (vs its own season average), did it have the ball
    less, and what happened to its passes to tight ends?
(B) PREDICTABLE: how well do pre-game "tough defense" measures predict the offense's first downs and time of possession?
    Point-in-time measures over the defense's previous 6 games that season: EPA allowed per dropback (pass), EPA allowed
    per play (overall), first downs allowed per game; and the Vegas implied team total (the market's view)."""
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client()
Q = """
WITH pb AS (SELECT season, week, game_id, posteam, defteam, fixed_drive, drive_time_of_possession top_str, pass_attempt, rush_attempt, qb_dropback,
                   epa, first_down, receiver_player_id, play_type
            FROM `nfl_raw.pbp` WHERE season_type = 'REG' AND season BETWEEN 2014 AND 2025 AND posteam IS NOT NULL AND defteam IS NOT NULL),
 drives AS (SELECT season, week, game_id, posteam, fixed_drive, ANY_VALUE(top_str) top_str FROM pb WHERE fixed_drive IS NOT NULL GROUP BY 1, 2, 3, 4, 5),
 top AS (SELECT game_id, posteam, SUM(SAFE_CAST(SPLIT(top_str, ':')[SAFE_OFFSET(0)] AS INT64) * 60 + SAFE_CAST(SPLIT(top_str, ':')[SAFE_OFFSET(1)] AS INT64)) top_sec,
         COUNT(*) drives FROM drives GROUP BY 1, 2),
 og AS (SELECT pb.season, pb.week, pb.game_id, pb.posteam, ANY_VALUE(pb.defteam) opp, COUNTIF(pb.first_down = 1) fd,
          COUNTIF(pb.play_type IN ('pass', 'run')) plays, AVG(IF(pb.play_type IN ('pass', 'run'), pb.epa, NULL)) epa_play,
          AVG(IF(pb.qb_dropback = 1, pb.epa, NULL)) epa_db, COUNTIF(pb.pass_attempt = 1 AND pb.receiver_player_id IS NOT NULL) tgt,
          COUNTIF(pb.pass_attempt = 1 AND r.position = 'TE') te_tgt
        FROM pb LEFT JOIN `nfl_features.player_week_role` r ON r.gsis_id = pb.receiver_player_id AND r.season = pb.season AND r.week = pb.week
        GROUP BY 1, 2, 3, 4),
 dpit AS (SELECT season, week, opp d, AVG(epa_db) OVER v pass_epa_l6, AVG(epa_play) OVER v play_epa_l6, AVG(fd) OVER v fd_allowed_l6, COUNT(*) OVER v n6
          FROM og WINDOW v AS (PARTITION BY season, opp ORDER BY week ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING)),
 sch AS (SELECT game_id, home_team, total_line, spread_line, home_score, away_score FROM `nfl_raw.schedules` WHERE game_type = 'REG')
SELECT og.*, top.top_sec, top.drives, o2.top_sec opp_top_sec, dpit.pass_epa_l6, dpit.play_epa_l6, dpit.fd_allowed_l6, dpit.n6,
       IF(og.posteam = sch.home_team, (sch.total_line + sch.spread_line) / 2, (sch.total_line - sch.spread_line) / 2) itt,
       IF(og.posteam = sch.home_team, sch.home_score - sch.away_score, sch.away_score - sch.home_score) margin
FROM og JOIN top ON top.game_id = og.game_id AND top.posteam = og.posteam
JOIN top o2 ON o2.game_id = og.game_id AND o2.posteam = og.opp
JOIN dpit ON dpit.season = og.season AND dpit.week = og.week AND dpit.d = og.opp
JOIN sch ON sch.game_id = og.game_id"""
D = BQ.query(Q).to_dataframe()
num = ["fd", "plays", "epa_play", "epa_db", "tgt", "te_tgt", "top_sec", "drives", "opp_top_sec", "pass_epa_l6", "play_epa_l6", "fd_allowed_l6", "itt", "margin"]
for c in num:
    D[c] = pd.to_numeric(D[c], errors="coerce").astype(float)
D = D[(D.tgt > 0) & (D.n6 >= 3)].dropna(subset=["top_sec", "opp_top_sec"]).copy()
D["top_min"] = D.top_sec / 60; D["top_share"] = D.top_sec / (D.top_sec + D.opp_top_sec); D["te_share"] = D.te_tgt / D.tgt
D["os"] = D.season.astype(str) + D.posteam
for c in ("fd", "top_min", "top_share", "te_tgt", "te_share", "tgt", "plays", "margin", "itt", "pass_epa_l6", "play_epa_l6", "fd_allowed_l6"):
    D[c + "_w"] = D[c] - D.groupby("os")[c].transform("mean")
print(f"offense games 2014-2025 with 3+ prior opponent games: {len(D):,}")
print("\n(A) REALIZED -- the offense's own first downs in the game, relative to its season average (thirds):")
D["fd_third"] = pd.qcut(D.fd_w, 3, labels=["fewer first downs", "about usual", "more first downs"])
print(D.groupby("fd_third", observed=True).agg(first_downs=("fd", "mean"), top_min=("top_min", "mean"), plays=("plays", "mean"), targets=("tgt", "mean"),
      te_targets=("te_tgt", "mean"), te_share=("te_share", "mean"), margin=("margin", "mean"), games=("fd", "size")).round(3).to_string())
print(f"  within offense-season correlation: first downs vs time of possession r {D.fd_w.corr(D.top_min_w):+.2f}; first downs vs TE share r {D.fd_w.corr(D.te_share_w):+.3f}")
print("\n(B) PREDICTABLE -- pre-game measures vs the game's first downs and time of possession (within offense-season correlations;"
      " sign: a tougher defense should give FEWER first downs)")
for m, lab in (("pass_epa_l6", "pass EPA allowed per dropback, last 6"), ("play_epa_l6", "EPA allowed per play, last 6"),
               ("fd_allowed_l6", "first downs allowed per game, last 6"), ("itt", "Vegas implied team total")):
    r_fd = D[m + "_w"].corr(D.fd_w); r_top = D[m + "_w"].corr(D.top_min_w)
    hi = D[m + "_w"] <= D[m + "_w"].quantile(1 / 3); lo = D[m + "_w"] >= D[m + "_w"].quantile(2 / 3)
    tough, soft = (hi, lo) if m != "itt" else (hi, lo)
    print(f"  {lab:38s}: r with first downs {r_fd:+.3f}, with time of possession {r_top:+.3f}; "
          f"toughest third vs softest third (own season): first downs {D[tough].fd.mean():.1f} vs {D[soft].fd.mean():.1f}, "
          f"possession {D[tough].top_min.mean():.1f} vs {D[soft].top_min.mean():.1f} min, TE share {D[tough].te_share.mean():.3f} vs {D[soft].te_share.mean():.3f}")
