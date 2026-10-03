"""The Millionaire graph in Neo4j (operator decision 2026-10-03: BigQuery
and Neo4j both).

A separate, small analytical graph -- not the corpus-retrieval graph:

  (:Week {key, season, week})
  (:Contest {contest_id, name, n_entries, winning_score, top_1pct_line,
             top_01pct_line, cash_line})-[:IN_WEEK]->(:Week)
  (:Game {game_id, season, week, home, away})-[:IN_WEEK]->(:Week)
  (:Team {code})-[:IN_GAME]->(:Game)
  (:Player {name, position})-[:PLAYS_FOR {season, weeks}]->(:Team)
  (:Lineup {key, rank, points, dupes, stack_label, stack, bring_back,
            salary, own_sum, top_1pct, at_cash_line})-[:ENTERED_IN]->(:Contest)
  (:Lineup)-[:CONTAINS {slot}]->(:Player)
  (:Player)-[:OWNED_IN {own, fpts}]->(:Contest)   realized field ownership
  (:Player)-[:STACKED_WITH {week_key, contest_id, kind, count}]->(:Player)
      same-game pairs inside the loaded lineups (kind teammate|opponent),
      counted per week; the pair is stored once (names in sorted order).

Every write is a MERGE keyed on the node identity, so a reload is
idempotent. What is loaded comes from DraftKings standings and salaries
only, unless the loader is run with --include-fp (opt-in, operator decision
2026-10-03), which adds (:Player)-[:FP_PROJECTED {fp_proj, fp_own}]->(:Week).
The lineup key is a SHA-256 of contest and entry id (no entry names).

``neo4j`` is imported lazily: the production venv does not carry it (the
image installs the ``graph`` extra).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Mapping

import numpy as np
import pandas as pd

from .milly import explode_lineups, lineup_construction, opponent_map
from .teams import canon_team

URI_ENV = "MILLY_NEO4J_URI"
USERNAME_ENV = "MILLY_NEO4J_USERNAME"
PASSWORD_ENV = "MILLY_NEO4J_PASSWORD"
DATABASE_ENV = "MILLY_NEO4J_DATABASE"

# Fields that must never be loaded (licensed vendor data); the loader
# refuses any batch row carrying one.
FORBIDDEN_FIELD_MARKERS = ("fantasy_points", "fp_", "sis_", "projected_ownership")


@dataclass(frozen=True)
class GraphConfig:
    uri: str
    username: str
    password: str
    database: str = "neo4j"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "GraphConfig | None":
        env = os.environ if env is None else env
        uri = (env.get(URI_ENV) or "").strip()
        user = (env.get(USERNAME_ENV) or "").strip()
        pw = env.get(PASSWORD_ENV) or ""
        if not (uri and user and pw):
            return None
        return cls(uri, user, pw, (env.get(DATABASE_ENV) or "neo4j").strip() or "neo4j")


def connect(cfg: GraphConfig):
    """A neo4j driver (lazy import; raises ImportError without the extra)."""
    from neo4j import GraphDatabase  # noqa: PLC0415

    return GraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))


SCHEMA = (
    "CREATE CONSTRAINT milly_week IF NOT EXISTS FOR (n:Week) REQUIRE n.key IS UNIQUE",
    "CREATE CONSTRAINT milly_contest IF NOT EXISTS FOR (n:Contest) REQUIRE n.contest_id IS UNIQUE",
    "CREATE CONSTRAINT milly_game IF NOT EXISTS FOR (n:Game) REQUIRE n.game_id IS UNIQUE",
    "CREATE CONSTRAINT milly_team IF NOT EXISTS FOR (n:Team) REQUIRE n.code IS UNIQUE",
    "CREATE CONSTRAINT milly_player IF NOT EXISTS FOR (n:Player) REQUIRE n.name IS UNIQUE",
    "CREATE CONSTRAINT milly_lineup IF NOT EXISTS FOR (n:Lineup) REQUIRE n.key IS UNIQUE",
)

# Order matters: nodes before the relationships that MATCH them.
STATEMENTS: dict[str, str] = {
    "weeks": """
UNWIND $rows AS row
MERGE (w:Week {key: row.key}) SET w.season = row.season, w.week = row.week""",
    "contests": """
UNWIND $rows AS row
MERGE (c:Contest {contest_id: row.contest_id})
SET c.name = row.name, c.n_entries = row.n_entries, c.winning_score = row.winning_score,
    c.top_1pct_line = row.top_1pct_line, c.top_01pct_line = row.top_01pct_line,
    c.cash_line = row.cash_line
WITH c, row MATCH (w:Week {key: row.week_key}) MERGE (c)-[:IN_WEEK]->(w)""",
    "games": """
UNWIND $rows AS row
MERGE (g:Game {game_id: row.game_id})
SET g.season = row.season, g.week = row.week, g.home = row.home, g.away = row.away
WITH g, row MATCH (w:Week {key: row.week_key}) MERGE (g)-[:IN_WEEK]->(w)
WITH g, row
MERGE (h:Team {code: row.home}) MERGE (h)-[:IN_GAME]->(g)
MERGE (a:Team {code: row.away}) MERGE (a)-[:IN_GAME]->(g)""",
    "players": """
UNWIND $rows AS row
MERGE (p:Player {name: row.name}) SET p.position = row.position""",
    "plays_for": """
UNWIND $rows AS row
MATCH (p:Player {name: row.name})
MERGE (t:Team {code: row.team})
MERGE (p)-[r:PLAYS_FOR {season: row.season}]->(t)
ON CREATE SET r.weeks = [row.week]
ON MATCH SET r.weeks = CASE WHEN row.week IN r.weeks THEN r.weeks ELSE r.weeks + row.week END""",
    "lineups": """
UNWIND $rows AS row
MERGE (l:Lineup {key: row.key})
SET l.rank = row.rank, l.points = row.points, l.dupes = row.dupes,
    l.stack_label = row.stack_label, l.stack = row.stack, l.bring_back = row.bring_back,
    l.salary = row.salary, l.own_sum = row.own_sum, l.top_1pct = row.top_1pct,
    l.at_cash_line = row.at_cash_line, l.week_key = row.week_key
WITH l, row MATCH (c:Contest {contest_id: row.contest_id}) MERGE (l)-[:ENTERED_IN]->(c)""",
    "contains": """
UNWIND $rows AS row
MATCH (l:Lineup {key: row.lineup_key}) MATCH (p:Player {name: row.player})
MERGE (l)-[r:CONTAINS {slot: row.slot}]->(p)""",
    "owned_in": """
UNWIND $rows AS row
MATCH (p:Player {name: row.name}) MATCH (c:Contest {contest_id: row.contest_id})
MERGE (p)-[r:OWNED_IN]->(c)
SET r.own = row.own, r.fpts = row.fpts""",
    "stacked_with": """
UNWIND $rows AS row
MATCH (a:Player {name: row.a}) MATCH (b:Player {name: row.b})
MERGE (a)-[r:STACKED_WITH {week_key: row.week_key, contest_id: row.contest_id}]->(b)
SET r.kind = row.kind, r.count = row.count, r.top_1pct_count = row.top_1pct_count""",
}


def _clean(v: Any) -> Any:
    """Neo4j parameters: plain Python scalars, NaN -> None."""
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if v is pd.NaT:
        return None
    return v


def _records(df: pd.DataFrame) -> list[dict]:
    return [{k: _clean(v) for k, v in r.items()} for r in df.to_dict("records")]


def build_graph_batches(contests: pd.DataFrame, lines: pd.DataFrame, top: pd.DataFrame,
                        slate: pd.DataFrame, games: pd.DataFrame,
                        own: pd.DataFrame | None = None) -> dict[str, list[dict]]:
    """Rows for every STATEMENTS key from the BigQuery reads (pure)."""
    wk = lambda s, w: f"{int(s)}-{int(w):02d}"  # noqa: E731
    out: dict[str, list[dict]] = {k: [] for k in STATEMENTS}
    if contests.empty:
        return out
    seasons_weeks = contests[["season", "week"]].drop_duplicates()
    out["weeks"] = [{"key": wk(s, w), "season": int(s), "week": int(w)}
                    for s, w in seasons_weeks.itertuples(index=False)]
    c = contests.merge(lines.drop(columns=[x for x in ("contest_name", "n_entries")
                                           if x in lines], errors="ignore"),
                       on=["season", "week", "contest_id"], how="left") if not lines.empty else contests.copy()
    for col in ("winning_score", "top_1pct_line", "top_01pct_line", "cash_line"):
        if col not in c:
            c[col] = np.nan
    out["contests"] = _records(pd.DataFrame({
        "contest_id": c.contest_id.astype(str), "name": c.contest_name,
        "n_entries": c.n_entries, "winning_score": c.winning_score,
        "top_1pct_line": c.top_1pct_line, "top_01pct_line": c.top_01pct_line,
        "cash_line": c.cash_line, "week_key": [wk(s, w) for s, w in zip(c.season, c.week)]}))

    wanted = set(map(int, seasons_weeks.week))
    g = games[games.week.isin(wanted)] if not games.empty else games
    out["games"] = [{"game_id": r.game_id, "season": int(r.season), "week": int(r.week),
                     "home": canon_team(r.home_team), "away": canon_team(r.away_team),
                     "week_key": wk(r.season, r.week)} for r in g.itertuples(index=False)]
    if top.empty:
        return out

    cons = lineup_construction(top, slate, games, own)
    long = explode_lineups(top)
    sl = slate.copy()
    sl["team_c"] = sl.team.map(canon_team)
    sl = sl.drop_duplicates(["contest_id", "display_name"])
    long = long.merge(sl[["contest_id", "display_name", "team_c", "position"]]
                      .rename(columns={"display_name": "player"}),
                      on=["contest_id", "player"], how="left")
    pos = long.position.fillna(long.slot.where(long.slot != "FLEX"))
    players = (pd.DataFrame({"name": long.player, "position": pos})
               .sort_values("position", na_position="last").drop_duplicates("name"))
    out["players"] = _records(players)
    pf = long.dropna(subset=["team_c"])[["player", "team_c", "season", "week"]].drop_duplicates()
    out["plays_for"] = [{"name": r.player, "team": r.team_c, "season": int(r.season),
                         "week": int(r.week)} for r in pf.itertuples(index=False)]

    n_by_contest = top.groupby("contest_id").n_entries.max().to_dict()
    cash = top.set_index("lineup_key").at_cash_line.to_dict() if "at_cash_line" in top else {}
    lrows = []
    for r in cons.itertuples(index=False):
        n = n_by_contest.get(r.contest_id) or 0
        lrows.append({"key": r.lineup_key, "contest_id": str(r.contest_id), "rank": r.rank,
                      "points": r.points, "dupes": r.dupes, "stack_label": r.stack_label,
                      "stack": r.stack, "bring_back": r.bring_back, "salary": r.salary,
                      "own_sum": r.own_sum,
                      "top_1pct": bool(n and r.rank <= np.ceil(0.01 * n)),
                      "at_cash_line": bool(cash.get(r.lineup_key, False)),
                      "week_key": wk(r.season, r.week)})
    out["lineups"] = [{k: _clean(v) for k, v in d.items()} for d in lrows]
    out["contains"] = [{"lineup_key": r.lineup_key, "player": r.player, "slot": r.slot}
                       for r in long.itertuples(index=False)]
    if own is not None and not own.empty:
        known = set(players.name)
        o = own[own.display_name.isin(known)]
        out["owned_in"] = [{"name": r.display_name, "contest_id": str(r.contest_id),
                            "own": _clean(r.own), "fpts": _clean(getattr(r, "fpts", None))}
                           for r in o.itertuples(index=False)]

    opp = opponent_map(games)
    top1 = {d["key"] for d in lrows if d["top_1pct"]}
    pairs: dict[tuple, list[int]] = {}
    for key, gl in long.groupby("lineup_key", sort=False):
        f = gl.iloc[0]
        members = [(p, t) for p, t in zip(gl.player, gl.team_c) if isinstance(t, str)]
        for (p1, t1), (p2, t2) in combinations(sorted(set(members)), 2):
            if t1 == t2:
                kind = "teammate"
            elif opp.get((int(f.week), t1)) == t2:
                kind = "opponent"
            else:
                continue
            k = (p1, p2, wk(f.season, f.week), str(f.contest_id), kind)
            c_ = pairs.setdefault(k, [0, 0])
            c_[0] += 1
            c_[1] += key in top1
    out["stacked_with"] = [{"a": a, "b": b, "week_key": w, "contest_id": cid, "kind": kind,
                            "count": n, "top_1pct_count": t}
                           for (a, b, w, cid, kind), (n, t) in sorted(pairs.items())]
    assert_no_vendor_fields(out)
    return out


# Opt-in (load_milly_neo4j.py --include-fp; operator decision 2026-10-03):
# Fantasy Points' pre-lock projection and projected ownership per player-week,
# so the graph can relate them to Millionaire outcomes.
FP_STATEMENT = """
UNWIND $rows AS row
MATCH (p:Player {name: row.name}) MATCH (w:Week {key: row.week_key})
MERGE (p)-[r:FP_PROJECTED]->(w)
SET r.fp_proj = row.fp_proj, r.fp_own = row.fp_own"""


def fp_batch(players: list[dict], fp_proj: pd.DataFrame, fp_own: pd.DataFrame,
             season: int) -> list[dict]:
    """FP projection/ownership rows for the graph's players, matched by
    normalised name (graph players are DraftKings display names)."""
    from .teams import norm_name  # noqa: PLC0415

    names = {norm_name(p["name"]): p["name"] for p in players}
    proj = (fp_proj.assign(key=fp_proj.name.map(norm_name))
            .groupby(["week", "key"]).fantasy_points.mean() if not fp_proj.empty else pd.Series(dtype=float))
    own = (fp_own.assign(key=fp_own.name.map(norm_name))
           .groupby(["week", "key"]).projected_ownership_pct.max() if not fp_own.empty else pd.Series(dtype=float))
    rows = []
    for (week, key) in sorted(set(proj.index) | set(own.index)):
        if key in names:
            rows.append({"name": names[key], "week_key": f"{int(season)}-{int(week):02d}",
                         "fp_proj": _clean(proj.get((week, key))),
                         "fp_own": _clean(own.get((week, key)))})
    return rows


def assert_no_vendor_fields(batches: Mapping[str, list[dict]]) -> None:
    """Refuse to ship any licensed-vendor field to the hosted graph."""
    for name, rows in batches.items():
        for row in rows[:1]:
            bad = [k for k in row if any(m in k.lower() for m in FORBIDDEN_FIELD_MARKERS)]
            if bad:
                raise ValueError(f"batch {name} carries vendor fields {bad}; not loadable")


def apply_batches(driver, database: str, batches: Mapping[str, list[dict]],
                  chunk: int = 1000, schema: bool = True,
                  fp_rows: list[dict] | None = None) -> dict[str, int]:
    """MERGE every batch (idempotent). Returns rows sent per statement.
    ``fp_rows`` (opt-in) adds the FP_PROJECTED relationships."""
    assert_no_vendor_fields(batches)
    if schema:
        for stmt in SCHEMA:
            driver.execute_query(stmt, database_=database)
    sent: dict[str, int] = {}
    for name, cypher in STATEMENTS.items():
        rows = list(batches.get(name, []))
        for i in range(0, len(rows), chunk):
            driver.execute_query(cypher, {"rows": rows[i:i + chunk]}, database_=database)
        sent[name] = len(rows)
    if fp_rows:
        for i in range(0, len(fp_rows), chunk):
            driver.execute_query(FP_STATEMENT, {"rows": fp_rows[i:i + chunk]}, database_=database)
        sent["fp_projected"] = len(fp_rows)
    return sent


# ----------------------------------------------------------- panel queries --

PANEL_QUERIES: dict[str, str] = {
    "stack_pairs": """
MATCH (a:Player)-[r:STACKED_WITH]->(b:Player)
WHERE r.kind = 'teammate'
RETURN a.name AS player_a, b.name AS player_b,
       sum(r.top_1pct_count) AS top_1pct_lineups, sum(r.count) AS lineups,
       count(DISTINCT r.week_key) AS weeks
ORDER BY top_1pct_lineups DESC, lineups DESC LIMIT 20""",
    "bring_backs": """
MATCH (a:Player)-[r:STACKED_WITH]->(b:Player)
WHERE r.kind = 'opponent'
RETURN a.name AS player_a, b.name AS player_b,
       sum(r.top_1pct_count) AS top_1pct_lineups, count(DISTINCT r.week_key) AS weeks
ORDER BY top_1pct_lineups DESC LIMIT 15""",
    "players_over_time": """
MATCH (l:Lineup)-[:CONTAINS]->(p:Player)
WHERE l.top_1pct
WITH p, l.week_key AS wk, count(l) AS n
ORDER BY wk
RETURN p.name AS player, p.position AS position, collect(wk + ':' + toString(n)) AS weeks,
       count(wk) AS n_weeks, sum(n) AS top_1pct_lineups
ORDER BY n_weeks DESC, top_1pct_lineups DESC LIMIT 25""",
    "winning_shapes": """
MATCH (l:Lineup)-[:ENTERED_IN]->(c:Contest)-[:IN_WEEK]->(w:Week)
WHERE l.rank = 1
RETURN w.key AS week, l.points AS points, l.stack_label AS stack, l.salary AS salary,
       l.own_sum AS own_sum, l.dupes AS dupes
ORDER BY week""",
}


# The dashboard's insight questions as saved Cypher (cypher/milly_insights.cypher
# carries the same text for the Aura console). 1-3 need --include-fp loads;
# 5 and 6 compare against our projections/book, which are not in the graph.
INSIGHT_QUERIES: dict[str, str] = {
    "winners_vs_projected": """
MATCH (l:Lineup)-[:CONTAINS]->(p:Player)-[r:FP_PROJECTED]->(w:Week {key: l.week_key})
WITH l, sum(r.fp_own) AS own_sum, sum(r.fp_proj) AS proj_sum
RETURN l.week_key AS week,
       CASE WHEN l.rank = 1 THEN 'winner' WHEN l.top_1pct THEN 'top 1%' ELSE 'loaded' END AS grp,
       count(l) AS lineups, avg(own_sum) AS fp_own_sum, avg(proj_sum) AS fp_proj_sum
ORDER BY week, grp""",
    "leverage_paid": """
MATCH (p:Player)-[o:OWNED_IN]->(c:Contest)-[:IN_WEEK]->(w:Week)
MATCH (p)-[r:FP_PROJECTED]->(w)
OPTIONAL MATCH (l:Lineup {top_1pct: true})-[:CONTAINS]->(p) WHERE l.week_key = w.key
WITH w, p, o, r, count(l) AS top1_lineups
WHERE (o.own <= 0.6 * r.fp_own AND r.fp_own - o.own >= 3 AND top1_lineups > 0)
   OR (r.fp_own >= 15 AND top1_lineups = 0)
RETURN w.key AS week, p.name AS player, r.fp_own AS fp_own, o.own AS realized,
       top1_lineups, o.fpts AS fpts,
       CASE WHEN r.fp_own >= 15 AND top1_lineups = 0 THEN 'chalk that busted'
            ELSE 'leverage that paid' END AS category
ORDER BY week, category, abs(r.fp_own - o.own) DESC""",
    "stack_outcomes": """
MATCH (a:Player)-[s:STACKED_WITH {kind: 'teammate'}]->(b:Player)
WHERE s.top_1pct_count > 0 AND (a.position = 'QB' OR b.position = 'QB')
OPTIONAL MATCH (a)-[ra:FP_PROJECTED]->(w:Week {key: s.week_key})
OPTIONAL MATCH (b)-[rb:FP_PROJECTED]->(w)
RETURN s.week_key AS week, a.name AS player_a, b.name AS player_b,
       s.top_1pct_count AS top_1pct_lineups,
       coalesce(ra.fp_own, 0) + coalesce(rb.fp_own, 0) AS pair_fp_own
ORDER BY week, top_1pct_lineups DESC LIMIT 60""",
}


def run_panel(driver, database: str) -> dict[str, pd.DataFrame]:
    out = {}
    for name, cypher in {**PANEL_QUERIES, **INSIGHT_QUERIES}.items():
        res = driver.execute_query(cypher, database_=database)
        records, keys = res[0], res[2]
        out[name] = pd.DataFrame([r.data() if hasattr(r, "data") else dict(r) for r in records],
                                 columns=list(keys))
    return out
