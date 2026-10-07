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
  (:PoolLineup {key: "pool|<week_key>|<players sha16>", source: "pool", tags, lbl_*, out_points, out_tier_*_line})
            -[:OF_WEEK]->(:Week), -[:CONTAINS]->(:Player) -- OUR candidate pool (the rows the union could have entered;
            the reviewer's item D): the same pre-lock construction labels as the field's Lineups, and the real finish
            tiers against that week's Millionaire lines (winner, within 10, top 1%, top 0.1%).

Added 10-07 evening (the outside reviewer's brainstorm, study list 55; definitions agreed before the build, reference
values reports/2026-10-07-brainstorm/graph_result_facts_reference_*.csv on review/outside-fill-order-20261006):
  Game pre_total_rank -- 1 = the highest total (the max of the frame's game_total), ties broken by game_id order, a game
            without a total last (game_total_ranks: the weekly field monitor's rule; lbl_qb_game_rank uses it too);
  Game out_best_stack_pts / out_is_best_stack_game -- per team: its best QB + its two best non-QB skill players + the
            opponent's best non-QB skill player, by that week's DK points (player_week_actuals; positions from
            player_week_role), the max over the game's two teams; the slate's best (every tie true);
  Game out_field_qb_share / out_top1_qb_share -- the share of the week's largest Millionaire's lineups (and of its top-1%
            lineups) whose QB is from the game, from BigQuery's WHOLE field (the field is revealed only at lock);
  Lineup / PoolLineup lbl_stack_n, lbl_bring_n, lbl_max_game -- the QB's teammates (not the DST), players on the QB's
            opponent (not its DST), the most of the nine from one game (the DST included); lbl_flex_pos is read from
            the position counts (3 RB / 4 WR / 2 TE), never the loaded slot.
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


def game_total_ranks(frame: pd.DataFrame) -> dict[str, int]:
    """Games ranked by total, 1 = the highest (the max of the frame's game_total over the game's rows); ties broken by
    game_id order and a game without a total ranked after every game with one -- the rule of the weekly field monitor
    (scripts/field_pattern_monitor.game_total_ranks) and of its 2014-2025 best-stack base rates (the outside reviewer,
    10-07). Tied totals are common, so the tie rule moves games between ranks."""
    gt = pd.to_numeric(frame.groupby("game_id").game_total.max(), errors="coerce")
    return {str(g): int(r) for g, r in gt.rank(ascending=False, method="first", na_option="bottom").items()}


def top_total_game(frame: pd.DataFrame) -> str | None:
    """The slate's highest-total game (rank 1 of game_total_ranks), or None when no game has a total."""
    if pd.to_numeric(frame.get("game_total"), errors="coerce").notna().sum() == 0:
        return None
    return next(g for g, k in game_total_ranks(frame).items() if k == 1)


def flex_position(pos: Counter) -> str | None:
    """The FLEX position from the position counts: a legal classic nine has exactly one of 3 RB / 4 WR / 2 TE. Never
    the loaded slot property (the outside reviewer, 10-07); None for a nine that is not a legal lineup."""
    return "RB" if pos["RB"] == 3 else "WR" if pos["WR"] == 4 else "TE" if pos["TE"] == 2 else None


def shape_labels(recs: list) -> dict:
    """lbl_stack_n (players on the QB's team other than the QB and the DST), lbl_bring_n (players on the QB's opponent
    other than its DST) and lbl_max_game (the most of the nine from one game, the DST included); a DST's team and game
    are its own (the outside reviewer's definitions, 10-07)."""
    qb = next((r for r in recs if str(r.pos) == "QB"), None)
    per_game = Counter(str(r.game_id) for r in recs)
    out = {"lbl_max_game": max(per_game.values()) if per_game else None}
    if qb is not None:
        out["lbl_stack_n"] = sum(1 for r in recs if str(r.team) == str(qb.team) and str(r.pos) not in ("QB", "DST"))
        out["lbl_bring_n"] = sum(1 for r in recs if str(r.team) == str(qb.opp) and str(r.pos) != "DST")
    return out


# That week's best QB + 2 + 1 stack per game: DK points with positions (player_week_role), skill positions only.
STACK_SQL = """
SELECT a.team, r.position, a.dk_points
FROM `{features}.player_week_actuals` a
JOIN `{features}.player_week_role` r ON r.gsis_id = a.gsis_id AND r.season = a.season AND r.week = a.week
WHERE a.season = @season AND a.week = @week AND r.position IN ('QB', 'RB', 'WR', 'TE')"""

# The week's largest Millionaire (by expected entries), whose WHOLE field gives the QB-game shares.
LARGEST_CONTEST_SQL = """
SELECT contest_id FROM `{raw}.contest_entries` WHERE season = @season AND week = @week
GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1"""

# Lineups by their QB's game (exact display-name match to the frame's priced players), all and top 1%.
FIELD_QB_SQL = """
WITH m AS (SELECT n, p, g FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@pos) p WITH OFFSET k ON i = k
           JOIN UNNEST(@games) g WITH OFFSET j ON i = j),
     e AS (SELECT DISTINCT entry_id, rank, expected_entries ne, players_key FROM `{raw}.contest_entries`
           WHERE contest_id = @contest AND season = @season AND week = @week),
     x AS (SELECT e.entry_id, ANY_VALUE(e.rank) <= 0.01 * ANY_VALUE(e.ne) top1, ANY_VALUE(IF(m.p = 'QB', m.g, NULL)) qb_game
           FROM e, UNNEST(SPLIT(e.players_key, '|')) nm LEFT JOIN m ON m.n = nm GROUP BY e.entry_id)
SELECT qb_game, COUNT(*) n, COUNTIF(top1) t FROM x GROUP BY 1"""


def best_stack_points(actuals: pd.DataFrame, team_game: Mapping[str, str]) -> dict[str, float]:
    """Per game: for each of its teams, the team's best QB (max DK points among its QBs, 0 if none) + its two best
    non-QB skill players + the opponent's best non-QB skill player; the max over the two teams, to 2 decimals.
    actuals: team, position (QB / RB / WR / TE), dk_points; team -> game through the T-70 frame (team_game)."""
    a = actuals.copy()
    a["dk_points"] = pd.to_numeric(a.dk_points, errors="coerce").fillna(0.0)
    a["game_id"] = a.team.astype(str).map(team_game)
    a = a[a.game_id.notna()]
    best: dict[str, float] = {}
    for gid, g in a.groupby("game_id"):
        vals = []
        for tm, t in g.groupby("team"):
            qb = t[t.position == "QB"].dk_points.max()
            mates = float(np.sort(t[t.position != "QB"].dk_points.values)[::-1][:2].sum())
            opp = g[(g.team != tm) & (g.position != "QB")].dk_points.max()
            vals.append((0.0 if pd.isna(qb) else float(qb)) + mates + (0.0 if pd.isna(opp) else float(opp)))
        best[str(gid)] = round(max(vals), 2)
    return best


def qb_game_shares(q: pd.DataFrame, games) -> dict[str, tuple[float | None, float]]:
    """{game_id: (field share, top-1% share)} of the lineups whose QB is from the game, among the lineups whose QB
    resolved to a priced frame QB (FIELD_QB_SQL's rows with a qb_game); a game no lineup's QB came from gets 0."""
    r = q[q.qb_game.notna()]
    n_all, t_all = float(r.n.sum()), float(r.t.sum())
    out = {}
    for g in games:
        s_ = r[r.qb_game.astype(str) == str(g)]
        out[str(g)] = (round(float(s_.n.sum()) / n_all, 4) if n_all else None, round(float(s_.t.sum()) / max(t_all, 1.0), 4))
    return out


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


def pool_lineup_rows(cands: pd.DataFrame, frame: pd.DataFrame, week_key: str, actual: Mapping[str, float],
                     lines: Mapping[str, float | None]) -> list[dict]:
    """PoolLineup rows from a candidates table (players = comma-separated frame ids; tag): lbl_ labels from the frame
    (pre-lock; the FLEX position read from the position counts, since a pool row has no slots) and the real finish
    tiers against the week's Millionaire lines (out_*, the week's results). Duplicate player sets collapse, tags joined."""
    import hashlib
    fr = frame.copy(); fr["id"] = fr["id"].astype(str)
    fr["dk"] = pd.to_numeric(fr.get("dk_player_id"), errors="coerce")
    info = {r.id: r for r in fr.dropna(subset=["dk"]).drop_duplicates("id").itertuples(index=False)}
    g_rank, top_game = game_total_ranks(frame), top_total_game(frame)
    seen: dict[str, dict] = {}
    for players, tag in zip(cands.players.astype(str), cands.tag.astype(str) if "tag" in cands else [""] * len(cands)):
        ids = sorted(p.strip() for p in players.split(",") if p.strip())
        recs = [info[i] for i in ids if i in info]
        if len(recs) != 9:
            continue
        key = f"pool|{week_key}|" + hashlib.sha256(",".join(ids).encode()).hexdigest()[:16]
        if key in seen:
            seen[key]["tags"] = sorted(set(seen[key]["tags"]) | {tag})
            continue
        pos = Counter(str(r.pos) for r in recs)
        qb = next((r for r in recs if str(r.pos) == "QB"), None)
        teams = Counter(str(r.team) for r in recs if str(r.pos) != "DST")
        te = [float(r.salary) for r in recs if str(r.pos) == "TE"]
        dst = next((r for r in recs if str(r.pos) == "DST"), None)
        missing = sum(1 for r in recs if actual.get(r.id) is None)
        pts = None if missing else sum(float(actual[r.id]) for r in recs)     # a missing player never reads as 0
        win, t1, t01 = lines.get("winning_score"), lines.get("top_1pct_line"), lines.get("top_01pct_line")
        tier = lambda line, off=0.0: (pts >= float(line) - off) if (pts is not None and line is not None) else None  # noqa: E731
        props = {"lbl_games": len({str(r.game_id) for r in recs}),
                 "lbl_flex_pos": flex_position(pos), **shape_labels(recs),
                 "lbl_dual_stack": bool(qb is not None and teams.get(str(qb.team), 0) >= 2 and teams.get(str(qb.opp), 0) >= 2),
                 "lbl_qb_game_rank": g_rank.get(str(qb.game_id)) if qb is not None else None,
                 "lbl_qb_favourite": (float(qb.spread) < 0) if qb is not None and pd.notna(getattr(qb, "spread", np.nan)) else None,
                 "lbl_top_game_players": sum(str(r.game_id) == str(top_game) for r in recs) if top_game else None,
                 "lbl_cheap_players": sum(float(r.salary) < 4000 for r in recs if str(r.pos) != "DST"),
                 "lbl_salary_left": 50_000 - sum(float(r.salary) for r in recs),
                 "lbl_qb_salary": float(qb.salary) if qb is not None else None,
                 "lbl_te_salary": max(te) if te else None, "lbl_dst_salary": float(dst.salary) if dst is not None else None,
                 "out_points": round(pts, 2) if pts is not None else None, "out_points_missing": missing,
                 "out_tier_winner_line": tier(win), "out_tier_within10_line": tier(win, 10.0),
                 "out_tier_top1pct_line": tier(t1), "out_tier_top01pct_line": tier(t01)}
        seen[key] = {"key": key, "week_key": week_key, "tags": [tag], "players": [int(r.dk) for r in recs],
                     "props": {k: _v(v) for k, v in props.items() if _v(v) is not None}}
    rows = list(seen.values())
    assert_point_in_time(rows)
    return rows


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
    "pool_lineups": """
UNWIND $rows AS row
MATCH (w:Week {key: row.week_key})
MERGE (pl:PoolLineup {key: row.key})
SET pl += row.props, pl.source = 'pool', pl.tags = row.tags, pl.week_key = row.week_key
MERGE (pl)-[:OF_WEEK]->(w)
WITH pl, row
UNWIND row.players AS d
MATCH (p:Player {dk_player_id: d})
MERGE (pl)-[:CONTAINS]->(p)""",
}
SCHEMA = (
    "CREATE CONSTRAINT milly_playerweek_key IF NOT EXISTS FOR (n:PlayerWeek) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT milly_teamweek_key IF NOT EXISTS FOR (n:TeamWeek) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT milly_poollineup_key IF NOT EXISTS FOR (n:PoolLineup) REQUIRE n.key IS UNIQUE",
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


def game_fact_rows(frame: pd.DataFrame, schedule: pd.DataFrame, source: str, as_of: str,
                   stack_points: Mapping[str, float] | None = None,
                   qb_shares: Mapping[str, tuple] | None = None) -> list[dict]:
    """Game pre_ facts from the frame (total and its rank, home spread, implied totals, kickoff window) and out_ facts
    from the schedule's final scores, with the slate's scoring rank (1 = the highest-scoring game of the slate); with
    stack_points (best_stack_points) the game's best QB + 2 + 1 stack and whether it is the slate's best (ties all true),
    with qb_shares (qb_game_shares) the whole field's and its top 1%'s share of lineups whose QB is from the game."""
    fr = frame.copy()
    fr["game_id"] = fr.game_id.astype(str)
    sch = schedule.copy()
    sch["game_id"] = sch.game_id.astype(str)
    sch = sch[sch.game_id.isin(set(fr.game_id))]
    tot = (pd.to_numeric(sch.home_score, errors="coerce") + pd.to_numeric(sch.away_score, errors="coerce"))
    sch = sch.assign(tot_pts=tot.values)
    sch["score_rank"] = sch.tot_pts.rank(ascending=False, method="min")
    ranks = game_total_ranks(frame)
    best = max(stack_points.values()) if stack_points else None
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
                 "out_top_game_rank": _v(s.score_rank), "out_source": "nfl_raw.schedules",
                 "pre_total_rank": ranks.get(str(s.game_id))}
        if stack_points is not None and str(s.game_id) in stack_points:
            props["out_best_stack_pts"] = stack_points[str(s.game_id)]
            props["out_is_best_stack_game"] = bool(stack_points[str(s.game_id)] == best)
        if qb_shares is not None and str(s.game_id) in qb_shares:
            props["out_field_qb_share"], props["out_top1_qb_share"] = qb_shares[str(s.game_id)]
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
    g_rank, top_game = game_total_ranks(frame), top_total_game(frame)
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
        flex = flex_position(Counter(str(r.pos) for r, _ in recs))      # the counts, never the loaded slot
        teams = Counter(str(r.team) for r, _ in recs if str(r.pos) != "DST")
        games = {str(r.game_id) for r, _ in recs}
        sal = sum(float(r.salary) for r, _ in recs)
        cid = str(l["contest_id"])
        owns = [float(realized_own.get((cid, int(r.dk)), 0.0)) for r, _ in recs]
        dst = next((r for r, _ in recs if str(r.pos) == "DST"), None)
        te = [float(r.salary) for r, _ in recs if str(r.pos) == "TE"]
        opp_of_qb = str(qb.opp) if qb is not None else None
        props = {"lbl_games": len(games), "lbl_flex_pos": flex, **shape_labels([r for r, _ in recs]),
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
