"""Player, game, team and lineup facts for the Milly graph (study list item 44; the operator and the outside reviewer,
10-06: "make sure that all the inputs for Neo4j … has all the data points that could help it look like a winner … for
each player selected in a lineup, what their red zone … attempts are, the number of touchdowns, the number of
attempts"; plan `reports/2026-10-06-neo4j-winner-likeness-inputs.md`).

Every fact sits in one of two groups and the group is in the property NAME, so a query can never mix them:

* ``pre_*`` -- known BEFORE lock: taken from the archived T-70 frame of that week (what the build saw), plus lagged
  touchdowns / pass attempts over the player's PRIOR games (weeks before the slate only). Provenance on every row:
  ``pre_source`` (the frame's run id and sha256) and ``pre_as_of`` (the frame's build time).
* ``out_*`` -- that week's RESULTS (nflverse weekly stats and play-by-play): what happened, i.e. why a lineup won.

The loader refuses a same-week outcome under a ``pre_`` name (``assert_point_in_time``). A winner-likeness score may
use ``pre_*`` only; ``out_*`` explains, it never predicts. Licensed vendor columns (Fantasy Points' route share,
xFP) are loaded only with the loader's opt-in --include-fp, like FP_PROJECTED. The graph is local only.

Nodes and relationships (all MERGE, idempotent):
  (:Player)-[:HAS_WEEK]->(:PlayerWeek {key: "<dk_player_id>|<week_key>", pre_*, out_*})-[:OF_WEEK]->(:Week)
  (:Team)-[:HAS_WEEK]->(:TeamWeek {key: "<team>|<week_key>", pre_*})-[:OF_WEEK]->(:Week)
  (:Game) gains pre_* (total, spread, implied totals, kickoff window) and out_* (scores, the slate's scoring rank)
  (:Lineup) gains lbl_* construction labels (PRE-LOCK facts of the lineup: built from the frame only) and out_* (its
            finish tiers, and the REALIZED ownership facts out_own_max_realized / out_own_under5_realized)
NOTE: the base graph's Lineup.own_sum is REALIZED ownership too (it describes a contest); never score on it.

Added 10-07 (the outside reviewer's facts-layer review, items E and the two missing inputs), all pre-lock:
  PlayerWeek pre_anytime_td_prob / pre_anytime_td_books -- the market's anytime-touchdown price, the last prop snapshot
            before the slate's first Sunday kickoff, the mean price-implied probability over bookmakers. NOT de-vigged:
            it includes the books' margin, so it ranks players within a week; never compare it across weeks or books as
            a calibrated probability. A canonical name shared by two frame players in the week gets no price;
  PlayerWeek pre_prior_top1_share / pre_prior_top1_weeks / pre_prior_top1_source -- the player's mean share of the REAL
            Millionaire top-1% lineups over the PRIOR weeks (reports/2026-10-07-prior-top-term/priortop-wNN.csv);
  TeamWeek pre_starters_out / pre_starters_out_pos -- depth-chart starters (QB / RB / TE rank 1, WR ranks 1-3, the last
            snapshot at or before the frame's build time) that are OUT before lock: absent from the T-70 frame, or in it
            with a pre-lock status of Out / IR / suspended; pre_starters_doubtful counts the Doubtful ones apart.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Mapping

import numpy as np
import pandas as pd

# The frame's pre-lock player facts (the plan's §2), loaded as pre_<column>. Never an outcome of the slate's week.
PRE_PLAYER_COLUMNS = (
    # red zone and goal line
    "rz20_targets_l4", "rz10_targets_l4", "rz20_target_share_l4", "rz10_target_share_l4", "rz20_targets_smoothed",
    "ez_targets_l4", "gl3_carries_l4", "gl3_carry_share_l4", "gl3_carries_smoothed", "rz_td_rate_allowed_l6",
    "xtd_receiving_proxy",
    # volume
    "targets_l4", "target_share_l4", "carries_l4", "carry_share_l4", "snap_share_l4", "deep_targets_l4",
    "air_yards_share_l4", "wopr_l4", "target_share_last", "carry_share_last", "snap_share_last", "target_share_jump",
    "carry_share_jump", "snap_share_jump", "target_share_trend", "carry_share_trend", "target_share_std",
    "team_vacated_target_share", "team_vacated_carry_share", "team_top2_target_share_l6",
    # efficiency and matchup
    "yards_per_target_l8", "yards_per_carry_l8", "qb_cpoe_l6",
    "qb_fp_allowed_adj_l6", "rb_fp_allowed_adj_l6", "wr_fp_allowed_adj_l6", "te_fp_allowed_adj_l6",
    # market and environment
    "total_line", "spread_line", "game_total", "implied_team_total", "pace_l4", "proe_l4", "pace_env_l6",
    "market_points",
    # status and role
    "status", "injury_status", "practice_level", "practice_participation_trend", "depth_rank", "depth_rank_delta",
    "report_status", "practice_status", "roster_status",
    # projection and price
    "mean_projection", "dk_ppg", "salary", "dk_points_std",
)
# Fantasy Points Data Suite columns of the frame: licensed, loaded only with --include-fp.
VENDOR_PRE_COLUMNS = ("fp_route_share_last", "fp_route_share_l4", "fp_route_share_jump", "xfp_l4")

# That week's results (nfl_features.player_week_actuals), loaded as out_<column>.
OUT_ACTUAL_COLUMNS = ("targets", "receptions", "rec_yards", "rec_tds", "carries", "rush_yards", "rush_tds",
                      "pass_attempts", "completions", "pass_yards", "pass_tds", "interceptions", "dk_points")
# That week's red-zone / goal-line / end-zone touches from play-by-play, loaded as out_<column>.
OUT_PBP_COLUMNS = ("rz20_targets", "rz20_carries", "gl5_carries", "ez_targets", "rz_tds")
# Lagged facts over the player's PRIOR games (the frame lacks them), loaded as pre_<column>.
LAG_COLUMNS = ("tds_l4", "tds_l8", "pass_tds_l4", "pass_tds_l8", "pass_att_l4", "games_prior_l8")

# Names that are a same-week OUTCOME whatever their prefix: refused under pre_ (the plan's §3F).
OUTCOME_NAMES = set(OUT_ACTUAL_COLUMNS) | set(OUT_PBP_COLUMNS) | {"fpts", "points", "rank", "own", "realized_own"}
# A lbl_ (pre-lock lineup label) may never carry these: the contest's realized ownership and results.
REALIZED_MARKERS = ("realized", "points", "fpts", "tier", "finish")   # plus any lbl_own* (realized ownership)

LAG_SQL = """
WITH g AS (
  SELECT gsis_id, season, week,
         COALESCE(rec_tds, 0) + COALESCE(rush_tds, 0) AS skill_tds, COALESCE(pass_tds, 0) AS pass_tds, pass_attempts,
         ROW_NUMBER() OVER (PARTITION BY gsis_id ORDER BY season DESC, week DESC) AS rn
  FROM `{features}.player_week_actuals`
  WHERE has_stat_line AND (season < @season OR (season = @season AND week < @week))
)
SELECT gsis_id,
       SUM(IF(rn <= 4, skill_tds, 0)) AS tds_l4, SUM(skill_tds) AS tds_l8,
       SUM(IF(rn <= 4, pass_tds, 0)) AS pass_tds_l4, SUM(pass_tds) AS pass_tds_l8,
       AVG(IF(rn <= 4, pass_attempts, NULL)) AS pass_att_l4, COUNT(*) AS games_prior_l8
FROM g WHERE rn <= 8 GROUP BY gsis_id"""

OUT_SQL = """
SELECT gsis_id, {cols} FROM `{features}.player_week_actuals` WHERE season = @season AND week = @week"""

PBP_SQL = """
WITH p AS (
  SELECT receiver_player_id, rusher_player_id, yardline_100, air_yards, pass_attempt, rush_attempt,
         COALESCE(pass_touchdown, 0) AS pass_td, COALESCE(rush_touchdown, 0) AS rush_td,
         COALESCE(two_point_attempt, 0) AS two_pt
  FROM `{raw}.pbp` WHERE season = @season AND week = @week AND season_type = 'REG'
)
SELECT gsis_id, SUM(rz20_targets) AS rz20_targets, SUM(rz20_carries) AS rz20_carries, SUM(gl5_carries) AS gl5_carries,
       SUM(ez_targets) AS ez_targets, SUM(rz_tds) AS rz_tds FROM (
  SELECT receiver_player_id AS gsis_id,
         IF(yardline_100 <= 20 AND pass_attempt = 1, 1, 0) AS rz20_targets, 0 AS rz20_carries, 0 AS gl5_carries,
         IF(pass_attempt = 1 AND air_yards IS NOT NULL AND air_yards >= yardline_100, 1, 0) AS ez_targets,
         IF(yardline_100 <= 20 AND pass_td = 1, 1, 0) AS rz_tds
  FROM p WHERE receiver_player_id IS NOT NULL AND two_pt = 0
  UNION ALL
  SELECT rusher_player_id, 0, IF(yardline_100 <= 20 AND rush_attempt = 1, 1, 0),
         IF(yardline_100 <= 5 AND rush_attempt = 1, 1, 0), 0, IF(yardline_100 <= 20 AND rush_td = 1, 1, 0)
  FROM p WHERE rusher_player_id IS NOT NULL AND two_pt = 0
) GROUP BY gsis_id"""

TD_SQL = """
WITH lk AS (SELECT MIN(commence_time) AS lock FROM `{raw}.prop_lines`
            WHERE season = @season AND week = @week
              AND EXTRACT(DAYOFWEEK FROM commence_time AT TIME ZONE 'America/Chicago') = 1),
     snap AS (SELECT MAX(p.snapshot_ts) AS ts FROM `{raw}.prop_lines` p, lk
              WHERE p.season = @season AND p.week = @week AND p.market = 'player_anytime_td'
                AND TIMESTAMP(p.snapshot_ts) < lk.lock)
SELECT p.player, p.bookmaker, p.price, p.outcome_name
FROM `{raw}.prop_lines` p, snap
WHERE p.season = @season AND p.week = @week AND p.market = 'player_anytime_td' AND p.snapshot_ts = snap.ts"""

DEPTH_SQL = """
WITH s AS (SELECT team, gsis_id, pos_abb, pos_rank, dt FROM `{raw}.depth_charts_snapshots`
           WHERE TIMESTAMP(dt) <= TIMESTAMP(@as_of) AND TIMESTAMP(dt) >= TIMESTAMP_SUB(TIMESTAMP(@as_of), INTERVAL 8 DAY)
             AND pos_abb IN ('QB', 'RB', 'WR', 'TE') AND gsis_id IS NOT NULL),
     last AS (SELECT team, MAX(dt) AS dt FROM s GROUP BY team)
SELECT s.team, s.gsis_id, s.pos_abb FROM s JOIN last USING (team, dt)
WHERE (s.pos_abb IN ('QB', 'RB', 'TE') AND s.pos_rank = 1) OR (s.pos_abb = 'WR' AND s.pos_rank <= 3)"""

TEAM_CODE = {"ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU", "GNB": "GB", "GBP": "GB", "JAC": "JAX",
             "KAN": "KC", "KCC": "KC", "LVR": "LV", "OAK": "LV", "LAR": "LA", "STL": "LA", "NWE": "NE", "NEP": "NE",
             "NOR": "NO", "NOS": "NO", "SDG": "LAC", "SD": "LAC", "SFO": "SF", "TAM": "TB", "TBB": "TB", "WSH": "WAS"}


def team_code(t) -> str:
    t = str(t).strip().upper()
    return TEAM_CODE.get(t, t)


def canon_name(s) -> str:
    """A player name for joining vendor / market feeds: lower case, letters and spaces, no suffix."""
    import re
    t = re.sub(r"[^a-z ]", "", str(s).lower().replace("-", " "))
    t = re.sub(r"\s+(jr|sr|ii|iii|iv|v)$", "", re.sub(r"\s+", " ", t).strip())
    return t


def td_probabilities(props: pd.DataFrame) -> pd.DataFrame:
    """TD_SQL rows -> one row per player (canonical name): the mean price-implied probability over bookmakers and the
    number of bookmakers. The 'yes' side only (outcome yes / over / the player's own name / missing)."""
    if props is None or props.empty:
        return pd.DataFrame(columns=["key", "td_prob", "books"])
    d = props.copy()
    oc = d.outcome_name.astype(str).str.lower()
    d = d[oc.isin(["yes", "over"]) | d.outcome_name.isna() | (d.outcome_name.astype(str) == d.player.astype(str))]
    price = pd.to_numeric(d.price, errors="coerce")
    d = d.assign(p=np.where(price > 0, 100.0 / (price + 100.0), -price / (-price + 100.0))).dropna(subset=["p"])
    d["key"] = d.player.map(canon_name)
    return d.groupby("key").agg(td_prob=("p", "mean"), books=("bookmaker", "nunique")).reset_index()


STATEMENTS: dict[str, str] = {
    "player_weeks": """
UNWIND $rows AS row
MATCH (p:Player {dk_player_id: row.dk_player_id}) MATCH (w:Week {key: row.week_key})
MERGE (pw:PlayerWeek {key: row.key})
SET pw += row.props
MERGE (p)-[:HAS_WEEK]->(pw)
MERGE (pw)-[:OF_WEEK]->(w)""",
    "team_weeks": """
UNWIND $rows AS row
MATCH (w:Week {key: row.week_key})
MERGE (t:Team {code: row.team})
MERGE (tw:TeamWeek {key: row.key})
SET tw += row.props
MERGE (t)-[:HAS_WEEK]->(tw)
MERGE (tw)-[:OF_WEEK]->(w)""",
    "game_facts": """
UNWIND $rows AS row
MATCH (g:Game {game_id: row.game_id})
SET g += row.props""",
    "lineup_labels": """
UNWIND $rows AS row
MATCH (l:Lineup {key: row.key})
SET l += row.props""",
}
SCHEMA = (
    "CREATE CONSTRAINT milly_playerweek_key IF NOT EXISTS FOR (n:PlayerWeek) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT milly_teamweek_key IF NOT EXISTS FOR (n:TeamWeek) REQUIRE n.key IS UNIQUE",
)


def _v(x):
    """A Neo4j-safe scalar (NaN / NA -> None; numpy -> python)."""
    if x is None:
        return None
    if isinstance(x, (float, np.floating)):
        return None if math.isnan(float(x)) else float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    try:
        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return x if isinstance(x, (int, float, str, bool)) else str(x)


def assert_point_in_time(rows: list[dict]) -> None:
    """The plan's §3F: refuse a same-week outcome under a pre_ name, and any property outside the two groups."""
    for r in rows:
        for k in r.get("props", {}):
            if k in ("pre_source", "pre_as_of", "out_source"):
                continue
            if k.startswith("pre_"):
                if k[4:] in OUTCOME_NAMES:
                    raise ValueError(f"refused: '{k}' is a same-week outcome under a pre_ name")
            elif k.startswith("lbl_"):
                if any(m in k for m in REALIZED_MARKERS) or k.startswith("lbl_own"):
                    raise ValueError(f"refused: '{k}' is a realized (post-lock) fact under a lbl_ name")
            elif not k.startswith("out_"):
                raise ValueError(f"refused: '{k}' is in neither the pre_ nor the out_ group")


def kickoff_window(ts) -> str | None:
    """early / late / night from the kickoff (America/New_York): before 15:00 early, before 19:00 late, else night;
    Thursday / Monday / Saturday games are 'other day'."""
    if ts is None or (isinstance(ts, float) and math.isnan(ts)):
        return None
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    t = t.tz_convert("America/New_York")
    if t.dayofweek != 6:
        return "other day"
    return "early" if t.hour < 15 else ("late" if t.hour < 19 else "night")


def player_week_rows(frame: pd.DataFrame, week_key: str, source: str, as_of: str, lag: pd.DataFrame | None = None,
                     out: pd.DataFrame | None = None, pbp: pd.DataFrame | None = None,
                     include_vendor: bool = False, td: pd.DataFrame | None = None,
                     prior_top: pd.DataFrame | None = None, prior_top_source: str | None = None) -> list[dict]:
    """One PlayerWeek per frame player with a DraftKings id: pre_ from the frame (+ the lagged facts), out_ from the
    week's actuals and play-by-play. Joined on the frame's gsis id (`id`)."""
    cols = list(PRE_PLAYER_COLUMNS) + (list(VENDOR_PRE_COLUMNS) if include_vendor else [])
    fr = frame.copy()
    fr["gsis"] = fr["id"].astype(str)
    fr["dk"] = pd.to_numeric(fr.get("dk_player_id"), errors="coerce")
    fr = fr.dropna(subset=["dk"]).drop_duplicates("dk")
    lagd = lag.set_index(lag.gsis_id.astype(str)) if lag is not None and not lag.empty else None
    outd = out.set_index(out.gsis_id.astype(str)) if out is not None and not out.empty else None
    pbpd = pbp.set_index(pbp.gsis_id.astype(str)) if pbp is not None and not pbp.empty else None
    tdd = td.set_index("key") if td is not None and not td.empty else None
    if tdd is not None:                                       # a canonical name shared by two frame players: no price
        names = fr.get("display_name", fr.get("name", pd.Series(dtype=str))).map(canon_name)
        shared = set(names[names.duplicated(keep=False)])
        tdd = tdd[~tdd.index.isin(shared)]
    ptd = (prior_top.assign(dk=pd.to_numeric(prior_top.dk_player_id, errors="coerce")).dropna(subset=["dk"])
           .drop_duplicates("dk").set_index("dk")) if prior_top is not None and not prior_top.empty else None
    rows = []
    for _, r in fr.iterrows():
        props = {f"pre_{c}": _v(r.get(c)) for c in cols if c in fr.columns}
        if tdd is not None:
            k = canon_name(r.get("display_name", r.get("name", "")))
            if k in tdd.index:
                props.update({"pre_anytime_td_prob": _v(tdd.at[k, "td_prob"]), "pre_anytime_td_books": _v(tdd.at[k, "books"])})
        if ptd is not None and float(r.dk) in ptd.index:
            props.update({"pre_prior_top1_share": _v(ptd.at[float(r.dk), "prior_top"]),
                          "pre_prior_top1_weeks": _v(ptd.at[float(r.dk), "weeks"]), "pre_prior_top1_source": prior_top_source})
        if lagd is not None and r.gsis in lagd.index:
            props.update({f"pre_{c}": _v(lagd.at[r.gsis, c]) for c in LAG_COLUMNS if c in lagd.columns})
        if outd is not None and r.gsis in outd.index:
            props.update({f"out_{c}": _v(outd.at[r.gsis, c]) for c in OUT_ACTUAL_COLUMNS if c in outd.columns})
        if pbpd is not None and r.gsis in pbpd.index:
            props.update({f"out_{c}": _v(pbpd.at[r.gsis, c]) for c in OUT_PBP_COLUMNS if c in pbpd.columns})
        props.update({"pre_source": source, "pre_as_of": as_of,
                      "out_source": "nfl_features.player_week_actuals + nfl_raw.pbp" if (outd is not None or pbpd is not None) else None})
        dk = int(r.dk)
        rows.append({"key": f"{dk}|{week_key}", "dk_player_id": dk, "week_key": week_key,
                     "props": {k: v for k, v in props.items() if v is not None}})
    assert_point_in_time(rows)
    return rows


def team_week_rows(frame: pd.DataFrame, week_key: str, source: str, as_of: str,
                   starters: pd.DataFrame | None = None) -> list[dict]:
    """One TeamWeek per team on the slate: implied total, favourite, pace, PROE, vacated shares (pre-lock); with
    starters (DEPTH_SQL rows), pre_starters_out: depth-chart starters absent from the frame's active pool."""
    fr = frame.dropna(subset=["team"]).copy()
    status = pd.Series("", index=frame.index)
    for c in ("status", "injury_status", "roster_status"):
        if c in frame.columns:
            status = status + "|" + frame[c].astype(object).where(frame[c].notna(), "").astype(str).str.upper()
    is_out = status.str.contains(r"\|(?:O|OUT|IR|INJURED RESERVE|SUS|SUSPENDED|PUP|NA|INA|RES)(?:\||$)", regex=True)
    is_doubtful = status.str.contains(r"\|(?:D|DOUBTFUL)(?:\||$)", regex=True)
    ids = frame["id"].astype(str) if "id" in frame.columns else pd.Series(dtype=str)
    active = set(ids[~is_out]) if len(ids) else set()
    doubtful = set(ids[is_doubtful & ~is_out]) if len(ids) else set()
    st = starters.assign(code=starters.team.map(team_code)) if starters is not None and not starters.empty else None
    rows = []
    for team, g in fr.groupby(fr.team.astype(str)):
        first = lambda c: _v(g[c].dropna().iloc[0]) if c in g and g[c].notna().any() else None  # noqa: E731
        spread = first("spread")
        props = {"pre_implied_total": first("implied_team_total"), "pre_game_total": first("game_total"),
                 "pre_spread": spread, "pre_favourite": (spread < 0) if isinstance(spread, float) else None,
                 "pre_pace_l4": first("pace_l4"), "pre_proe_l4": first("proe_l4"),
                 "pre_vacated_target_share": first("team_vacated_target_share"),
                 "pre_vacated_carry_share": first("team_vacated_carry_share"),
                 "pre_source": source, "pre_as_of": as_of}
        if st is not None:
            mine = st[st.code == team_code(team)]
            if len(mine):
                gone = mine[~mine.gsis_id.astype(str).isin(active)]
                props.update({"pre_starters_out": int(len(gone)), "pre_starters_out_pos": ",".join(sorted(gone.pos_abb.astype(str))),
                              "pre_starters_doubtful": int(mine.gsis_id.astype(str).isin(doubtful).sum())})
        rows.append({"key": f"{team}|{week_key}", "team": team, "week_key": week_key,
                     "props": {k: v for k, v in props.items() if v is not None}})
    assert_point_in_time(rows)
    return rows


def game_fact_rows(frame: pd.DataFrame, schedule: pd.DataFrame, source: str, as_of: str) -> list[dict]:
    """Game pre_ facts from the frame (total, home spread, implied totals, kickoff window) and out_ facts from the
    schedule's final scores, with the slate's scoring rank (1 = the highest-scoring game of the slate)."""
    fr = frame.copy()
    fr["game_id"] = fr.game_id.astype(str)
    sch = schedule.copy()
    sch["game_id"] = sch.game_id.astype(str)
    sch = sch[sch.game_id.isin(set(fr.game_id))]
    tot = (pd.to_numeric(sch.home_score, errors="coerce") + pd.to_numeric(sch.away_score, errors="coerce"))
    sch = sch.assign(tot_pts=tot.values)
    sch["score_rank"] = sch.tot_pts.rank(ascending=False, method="min")
    rows = []
    for s in sch.itertuples(index=False):
        g = fr[fr.game_id == s.game_id]
        home = g[g.team.astype(str) == str(s.home_team)]
        away = g[g.team.astype(str) == str(s.away_team)]
        first = lambda d, c: _v(d[c].dropna().iloc[0]) if c in d and d[c].notna().any() else None  # noqa: E731
        props = {"pre_total": first(g, "game_total"), "pre_spread_home": first(home, "spread"),
                 "pre_implied_home": first(home, "implied_team_total"), "pre_implied_away": first(away, "implied_team_total"),
                 "pre_kickoff": kickoff_window(first(g, "game_start")), "pre_source": source, "pre_as_of": as_of,
                 "out_home_pts": _v(s.home_score), "out_away_pts": _v(s.away_score), "out_total": _v(s.tot_pts),
                 "out_top_game_rank": _v(s.score_rank), "out_source": "nfl_raw.schedules"}
        rows.append({"game_id": s.game_id, "props": {k: v for k, v in props.items() if v is not None}})
    assert_point_in_time(rows)
    return rows


def lineup_label_rows(lineups: list[dict], contains: list[dict], frame: pd.DataFrame,
                      realized_own: Mapping[tuple[str, int], float], n_entries: Mapping[str, int],
                      winning_points: Mapping[str, float]) -> list[dict]:
    """lbl_* construction labels per loaded lineup, from the T-70 FRAME ONLY (pre-lock: games, dual stack, flex
    position, the QB's game-total rank and favourite status, players from the top-total game, cheap players, salary
    left, QB / TE / DST prices) and out_* (the finish tiers -- winner, within 10 points of the winner, top 100, top 1%,
    top 0.1% -- and the contest's REALIZED ownership: out_own_max_realized, out_own_under5_realized, looked up by
    (contest_id, dk_player_id)). Realized ownership is post-lock and never a lbl_ (the reviewer, 10-06)."""
    fr = frame.copy()
    fr["dk"] = pd.to_numeric(fr.get("dk_player_id"), errors="coerce")
    fr = fr.dropna(subset=["dk"]).drop_duplicates("dk")
    info = {int(r.dk): r for r in fr.itertuples(index=False)}
    gt = fr.dropna(subset=["game_total"]).drop_duplicates("game_id").sort_values(["game_total", "game_id"],
                                                                                  ascending=[False, True])
    g_rank = {str(g): i + 1 for i, g in enumerate(gt.game_id)}
    top_game = gt.game_id.iloc[0] if len(gt) else None
    by_lineup: dict[str, list[tuple[int, str]]] = {}
    for c in contains:
        by_lineup.setdefault(c["lineup_key"], []).append((int(c["dk_player_id"]), c["slot"]))
    rows = []
    for l in lineups:
        ps = by_lineup.get(l["key"], [])
        recs = [(info[p], slot) for p, slot in ps if p in info]
        if len(recs) < 9:
            continue
        qb = next((r for r, _ in recs if str(r.pos) == "QB"), None)
        flex = next((str(r.pos) for r, slot in recs if str(slot).upper() == "FLEX"), None)
        teams = Counter(str(r.team) for r, _ in recs if str(r.pos) != "DST")
        games = {str(r.game_id) for r, _ in recs}
        sal = sum(float(r.salary) for r, _ in recs)
        cid = str(l["contest_id"])
        owns = [float(realized_own.get((cid, int(r.dk)), 0.0)) for r, _ in recs]
        dst = next((r for r, _ in recs if str(r.pos) == "DST"), None)
        te = [float(r.salary) for r, _ in recs if str(r.pos) == "TE"]
        opp_of_qb = str(qb.opp) if qb is not None else None
        props = {"lbl_games": len(games), "lbl_flex_pos": flex,
                 "lbl_dual_stack": bool(qb is not None and teams.get(str(qb.team), 0) >= 2 and teams.get(opp_of_qb, 0) >= 2),
                 "lbl_qb_game_rank": g_rank.get(str(qb.game_id)) if qb is not None else None,
                 "lbl_qb_favourite": (float(qb.spread) < 0) if qb is not None and pd.notna(getattr(qb, "spread", np.nan)) else None,
                 "lbl_top_game_players": sum(str(r.game_id) == str(top_game) for r, _ in recs) if top_game else None,
                 "lbl_cheap_players": sum(float(r.salary) < 4000 for r, _ in recs if str(r.pos) != "DST"),
                 "lbl_salary_left": 50_000 - sal, "lbl_qb_salary": float(qb.salary) if qb is not None else None,
                 "lbl_te_salary": max(te) if te else None, "lbl_dst_salary": float(dst.salary) if dst is not None else None,
                 "out_own_max_realized": max(owns) if owns else None,
                 "out_own_under5_realized": sum(o < 5.0 for o in owns)}
        n, rank, pts = n_entries.get(str(l["contest_id"])), l.get("rank"), l.get("points")
        win = winning_points.get(str(l["contest_id"]))
        if rank is not None:
            props.update({"out_tier_winner": rank == 1, "out_tier_top100": rank <= 100,
                          "out_tier_top1pct": bool(n and rank <= math.ceil(0.01 * n)),
                          "out_tier_top01pct": bool(n and rank <= math.ceil(0.001 * n))})
        if pts is not None and win is not None:
            props["out_tier_within10"] = float(pts) >= float(win) - 10.0
        rows.append({"key": l["key"], "props": {k: _v(v) for k, v in props.items() if _v(v) is not None}})
    assert_point_in_time(rows)
    return rows


# Properties an earlier version of this module wrote under a wrong group (realized ownership as lbl_): removed first.
LEGACY_REMOVE = "MATCH (l:Lineup) WHERE l.lbl_own_max IS NOT NULL OR l.lbl_own_under5 IS NOT NULL REMOVE l.lbl_own_max, l.lbl_own_under5"


def apply_fact_batches(driver, database: str, batches: Mapping[str, list[dict]], chunk: int = 500) -> dict[str, int]:
    """MERGE the fact batches after the base load (the base Player / Week / Game / Lineup nodes must exist)."""
    for stmt in SCHEMA:
        driver.execute_query(stmt, database_=database)
    driver.execute_query(LEGACY_REMOVE, database_=database)
    sent = {}
    for name, cypher in STATEMENTS.items():
        rows = list(batches.get(name, []))
        for i in range(0, len(rows), chunk):
            driver.execute_query(cypher, {"rows": rows[i:i + chunk]}, database_=database)
        sent[name] = len(rows)
    return sent
