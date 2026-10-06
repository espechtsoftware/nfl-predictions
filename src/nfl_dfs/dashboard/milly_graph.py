"""The Millionaire graph in Neo4j (operator decision 2026-10-03: BigQuery
and Neo4j both). A LOCAL instance only, for learning from the data; it is not
part of the dashboard UI (operator 2026-10-04). The loader targets whatever
MILLY_NEO4J_* names (e.g. bolt://localhost:7687).

A separate, small analytical graph -- not the corpus-retrieval graph:

  (:Week {key, season, week})
  (:Contest {contest_id, name, n_entries, winning_score, top_1pct_line,
             top_01pct_line, cash_line})-[:IN_WEEK]->(:Week)
  (:Game {game_id, season, week, home, away})-[:IN_WEEK]->(:Week)
  (:Team {code})-[:IN_GAME]->(:Game)
  (:Player {dk_player_id, name, position, team})-[:PLAYS_FOR {season, weeks}]->(:Team)
  (:Lineup {key, rank, points, dupes, stack_label, stack, bring_back, salary, own_sum, top_1pct, at_cash_line,
            week_key, source, rank_top_1pct})-[:ENTERED_IN]->(:Contest)
      week_key = week_key(season, week), e.g. '2026-04'. source = 'top' (the top-N set every panel figure uses) or
      'users_file' (loader --users-file: a listed user's other lineups, reached only through ENTERED / CONTAINS).
      top_1pct is set on 'top' lineups only, so run_panel's top-1% views and STACKED_WITH (built from the top set
      only) are unchanged by a users file; rank_top_1pct is the plain fact (rank <= 1% of the field) for every lineup.
  (:Lineup)-[:CONTAINS {slot}]->(:Player)
  (:User {name})-[:ENTERED]->(:Lineup)            DraftKings user name: the entry
      name without its "(k/n)" counter (operator 2026-10-03/04: user names are
      kept in BigQuery derivations, the IAP dashboard and the graph; never in
      tracked files, fixtures or tests -- those use synthetic names)
  (:Player)-[:OWNED_IN {own, fpts}]->(:Contest)   realized field ownership
  (:Player)-[:STACKED_WITH {week_key, contest_id, kind, count}]->(:Player)
      same-game pairs inside the loaded lineups (kind teammate|opponent),
      counted per week; the pair is stored once (names in sorted order).

Player identity is the DraftKings player id (``dk_player_id``): stable
across weeks on DraftKings and present for DSTs, which have no gsis id. The
name is a property. Standings lineups carry names only; each is resolved to
the contest slate's id by normalised name (milly.resolve_slate, the
scripts/o1_common.py rule), and a name two slate players share is a collision:
counted, printed by the loader, and never merged (its slots are not loaded).

Every write is a MERGE keyed on the node identity, backed by a uniqueness
constraint per merged label (cypher/milly_schema.cypher, applied before the
first batch), so a reload is idempotent. What is loaded comes from DraftKings standings and salaries
only, unless the loader is run with --include-fp (opt-in, operator decision
2026-10-03), which adds (:Player)-[:FP_PROJECTED {fp_proj, fp_own}]->(:Week).
The lineup key is a SHA-256 of contest and entry id; the user name is a
separate User node, never part of a key.

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

from pathlib import Path

from .milly import (explode_lineups, lineup_construction, opponent_map, resolve_names,
                    slate_collisions)
from .teams import canon_team, norm_name

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


def _schema_path() -> Path:
    for c in (Path(__file__).resolve().parents[3] / "cypher" / "milly_schema.cypher",
              Path.cwd() / "cypher" / "milly_schema.cypher"):
        if c.is_file():
            return c
    return Path(__file__).resolve().parents[3] / "cypher" / "milly_schema.cypher"


def load_schema(path: Path | None = None) -> tuple[str, ...]:
    """The uniqueness constraints in cypher/milly_schema.cypher, one per
    merged label and key (comments stripped, split on ';')."""
    text = (path or _schema_path()).read_text()
    body = "\n".join(line for line in text.splitlines() if not line.strip().startswith("//"))
    return tuple(" ".join(st.split()) for st in body.split(";") if st.strip())


# Every label a statement MERGEs, with its identity property.
MERGED_KEYS = {"Week": "key", "Contest": "contest_id", "Game": "game_id", "Team": "code",
               "Player": "dk_player_id", "Lineup": "key", "User": "name"}

# Loaded on use, not at import: the app image does not carry cypher/, and only
# the loader (run from a checkout) applies the schema.

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
    c.cash_line = row.cash_line, c.loaded_lineups = row.loaded_lineups,
    c.loaded_share = row.loaded_share
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
MERGE (p:Player {dk_player_id: row.dk_player_id})
SET p.name = row.name, p.position = row.position, p.team = row.team""",
    "plays_for": """
UNWIND $rows AS row
MATCH (p:Player {dk_player_id: row.dk_player_id})
MERGE (t:Team {code: row.team})
MERGE (p)-[r:PLAYS_FOR {season: row.season}]->(t)
ON CREATE SET r.weeks = [row.week]
ON MATCH SET r.weeks = CASE WHEN row.week IN r.weeks THEN r.weeks ELSE r.weeks + row.week END""",
    "users": """
UNWIND $rows AS row
MERGE (u:User {name: row.name})""",
    "lineups": """
UNWIND $rows AS row
MERGE (l:Lineup {key: row.key})
SET l.rank = row.rank, l.points = row.points, l.dupes = row.dupes,
    l.stack_label = row.stack_label, l.stack = row.stack, l.bring_back = row.bring_back,
    l.salary = row.salary, l.own_sum = row.own_sum, l.top_1pct = row.top_1pct,
    l.at_cash_line = row.at_cash_line, l.week_key = row.week_key, l.source = row.source,
    l.rank_top_1pct = row.rank_top_1pct
WITH l, row MATCH (c:Contest {contest_id: row.contest_id}) MERGE (l)-[:ENTERED_IN]->(c)""",
    "entered": """
UNWIND $rows AS row
MATCH (u:User {name: row.name}) MATCH (l:Lineup {key: row.lineup_key})
MERGE (u)-[:ENTERED]->(l)""",
    "contains": """
UNWIND $rows AS row
MATCH (l:Lineup {key: row.lineup_key}) MATCH (p:Player {dk_player_id: row.dk_player_id})
MERGE (l)-[r:CONTAINS {slot: row.slot}]->(p)""",
    "owned_in": """
UNWIND $rows AS row
MATCH (p:Player {dk_player_id: row.dk_player_id}) MATCH (c:Contest {contest_id: row.contest_id})
MERGE (p)-[r:OWNED_IN]->(c)
SET r.own = row.own, r.fpts = row.fpts""",
    "stacked_with": """
UNWIND $rows AS row
MATCH (a:Player {dk_player_id: row.a}) MATCH (b:Player {dk_player_id: row.b})
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


def week_key(season: int, week: int) -> str:
    """The Week node key and Lineup.week_key: '2026-04' (never '2026-w04')."""
    return f"{int(season)}-{int(week):02d}"


def build_graph_batches(contests: pd.DataFrame, lines: pd.DataFrame, top: pd.DataFrame,
                        slate: pd.DataFrame, games: pd.DataFrame,
                        own: pd.DataFrame | None = None) -> dict[str, list[dict]]:
    """Rows for every STATEMENTS key from the BigQuery reads (pure)."""
    wk = week_key
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
    source = top.set_index("lineup_key")["source"].to_dict() if "source" in top else {}
    top_only = top[top.source == "top"] if "source" in top else top
    share = loaded_share(top_only)
    out["contests"] = _records(pd.DataFrame({
        "contest_id": c.contest_id.astype(str), "name": c.contest_name,
        "n_entries": c.n_entries, "winning_score": c.winning_score,
        "top_1pct_line": c.top_1pct_line, "top_01pct_line": c.top_01pct_line,
        "cash_line": c.cash_line, "week_key": [wk(s, w) for s, w in zip(c.season, c.week)],
        "loaded_lineups": [share.get(str(x), (0, None))[0] for x in c.contest_id],
        "loaded_share": [share.get(str(x), (0, None))[1] for x in c.contest_id]}))

    wanted = set(map(int, seasons_weeks.week))
    g = games[games.week.isin(wanted)] if not games.empty else games
    out["games"] = [{"game_id": r.game_id, "season": int(r.season), "week": int(r.week),
                     "home": canon_team(r.home_team), "away": canon_team(r.away_team),
                     "week_key": wk(r.season, r.week)} for r in g.itertuples(index=False)]
    if top.empty:
        return out

    cons = lineup_construction(top, slate, games, own)
    # Resolve every slot to the slate's DraftKings id; collisions and unknown
    # names stay unresolved and are not loaded (resolution_report counts them).
    long = resolve_names(explode_lineups(top), slate)
    long = long.dropna(subset=["dk_player_id"]).copy()
    long["dk_player_id"] = pd.to_numeric(long.dk_player_id).astype(int)
    names = slate.assign(dk_player_id=pd.to_numeric(slate.get("dk_player_id"), errors="coerce"))
    names = names.dropna(subset=["dk_player_id"]).drop_duplicates("dk_player_id").set_index(
        "dk_player_id").display_name.to_dict()
    players = (long.sort_values("position", na_position="last")
               .drop_duplicates("dk_player_id")[["dk_player_id", "position", "team_c"]])
    out["players"] = [{"dk_player_id": int(r.dk_player_id), "name": names.get(r.dk_player_id),
                       "position": _clean(r.position), "team": _clean(r.team_c)}
                      for r in players.itertuples(index=False)]
    pf = long.dropna(subset=["team_c"])[["dk_player_id", "team_c", "season", "week"]].drop_duplicates()
    out["plays_for"] = [{"dk_player_id": int(r.dk_player_id), "team": r.team_c, "season": int(r.season),
                         "week": int(r.week)} for r in pf.itertuples(index=False)]

    n_by_contest = top.groupby("contest_id").n_entries.max().to_dict()
    cash = top.set_index("lineup_key").at_cash_line.to_dict() if "at_cash_line" in top else {}
    lrows = []
    for r in cons.itertuples(index=False):
        n = n_by_contest.get(r.contest_id) or 0
        src = source.get(r.lineup_key, "top")
        in_1pct = bool(n and r.rank <= np.ceil(0.01 * n))
        lrows.append({"key": r.lineup_key, "contest_id": str(r.contest_id), "rank": r.rank,
                      "points": r.points, "dupes": r.dupes, "stack_label": r.stack_label,
                      "stack": r.stack, "bring_back": r.bring_back, "salary": r.salary,
                      "own_sum": r.own_sum,
                      "top_1pct": in_1pct and src == "top", "rank_top_1pct": in_1pct, "source": src,
                      "at_cash_line": bool(cash.get(r.lineup_key, False)),
                      "week_key": wk(r.season, r.week)})
    out["lineups"] = [{k: _clean(v) for k, v in d.items()} for d in lrows]
    # DraftKings user names (operator 10-03): one User per name, ENTERED each
    # loaded lineup. Names are data at runtime only, never in the repository.
    if "username" in top:
        loaded = {d["key"] for d in lrows}
        u = top[top.lineup_key.isin(loaded) & top.username.notna() & (top.username.astype(str).str.strip() != "")]
        out["users"] = [{"name": n} for n in sorted(set(u.username.astype(str)))]
        out["entered"] = [{"name": str(r.username), "lineup_key": r.lineup_key} for r in u.itertuples(index=False)]
    out["contains"] = [{"lineup_key": r.lineup_key, "dk_player_id": int(r.dk_player_id), "slot": r.slot}
                       for r in long.itertuples(index=False)]
    if own is not None and not own.empty:
        known = {d["dk_player_id"] for d in out["players"]}
        o = resolve_names(own.drop(columns=[c for c in ("dk_player_id", "team") if c in own]),
                          slate, name_col="display_name").dropna(subset=["dk_player_id"])
        o = o[pd.to_numeric(o.dk_player_id).astype(int).isin(known)]
        out["owned_in"] = [{"dk_player_id": int(r.dk_player_id), "contest_id": str(r.contest_id),
                            "own": _clean(r.own), "fpts": _clean(getattr(r, "fpts", None))}
                           for r in o.itertuples(index=False)]

    opp = opponent_map(games)
    top1 = {d["key"] for d in lrows if d["top_1pct"]}
    pairs: dict[tuple, list[int]] = {}
    for key, gl in long.groupby("lineup_key", sort=False):
        if source.get(key, "top") != "top":
            continue                                   # a users-file lineup never changes the panel's pair counts
        f = gl.iloc[0]
        members = [(int(p), t) for p, t in zip(gl.dk_player_id, gl.team_c) if isinstance(t, str)]
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
MATCH (p:Player {dk_player_id: row.dk_player_id}) MATCH (w:Week {key: row.week_key})
MERGE (p)-[r:FP_PROJECTED]->(w)
SET r.fp_proj = row.fp_proj, r.fp_own = row.fp_own"""


def fp_batch(players: list[dict], fp_proj: pd.DataFrame, fp_own: pd.DataFrame,
             season: int) -> list[dict]:
    """FP projection/ownership rows for the graph's players, matched on
    (normalised name, team) to the player's DraftKings id. A key two graph
    players or two FP rows share is dropped, never merged."""
    def key(name, team):
        return f"{norm_name(name)}:{canon_team(team) or ''}"

    graph: dict[str, int | None] = {}
    for p in players:
        k = key(p.get("name"), p.get("team"))
        graph[k] = None if k in graph else p["dk_player_id"]

    def series(df: pd.DataFrame, col: str) -> pd.Series:
        if df.empty:
            return pd.Series(dtype=float)
        d = df.assign(key=[key(n, t) for n, t in zip(df.name, df.get("team", [None] * len(df)))])
        n = d.groupby(["week", "key"])[col].transform("size")
        return d[n == 1].set_index(["week", "key"])[col]

    proj, own = series(fp_proj, "fantasy_points"), series(fp_own, "projected_ownership_pct")
    rows = []
    for (week, k) in sorted(set(proj.index) | set(own.index)):
        pid = graph.get(k)
        if pid is not None:
            rows.append({"dk_player_id": pid, "week_key": f"{int(season)}-{int(week):02d}",
                         "fp_proj": _clean(proj.get((week, k))), "fp_own": _clean(own.get((week, k)))})
    return rows


def loaded_share(top: pd.DataFrame) -> dict[str, tuple[int, float | None]]:
    """contest_id -> (lineups loaded, their share of the field)."""
    if top.empty:
        return {}
    out = {}
    for cid, g in top.groupby(top.contest_id.astype(str)):
        n = pd.to_numeric(g.n_entries, errors="coerce").max()
        out[cid] = (len(g), float(len(g) / n) if n and n > 0 else None)
    return out


def resolution_report(top: pd.DataFrame, slate: pd.DataFrame) -> dict:
    """What name resolution left out: slate collisions (never merged) and
    the lineup slots whose name did not resolve to one slate player."""
    coll = slate_collisions(slate)
    if top.empty:
        return {"collisions": coll, "slots": 0, "unresolved_slots": 0, "unresolved_names": []}
    long = resolve_names(explode_lineups(top), slate)
    bad = long[long.dk_player_id.isna()]
    return {"collisions": coll, "slots": len(long), "unresolved_slots": len(bad),
            "unresolved_names": sorted(set(bad.player))}


def assert_no_vendor_fields(batches: Mapping[str, list[dict]]) -> None:
    """Refuse any licensed-vendor field in the base batches (FP rows are
    loaded only through the opt-in fp_batch)."""
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
    if schema:  # constraints first: every MERGE below is backed by one
        for stmt in load_schema():
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


# --------------------------------------------------------- capacity guard --
# Aura Free limits as of 2026-10-03. CHECK THESE against Neo4j's current Aura
# Free terms before relying on them; override with --node-limit/--rel-limit.
FREE_TIER_NODES = 200_000
FREE_TIER_RELS = 400_000
CAPACITY_SHARE = 0.90
MAX_TOP_N = 1500


class CapacityError(RuntimeError):
    pass


def count_graph(driver, database: str) -> tuple[int, int]:
    """(nodes, relationships) currently in the database."""
    n = driver.execute_query("MATCH (n) RETURN count(n) AS n", database_=database)[0]
    r = driver.execute_query("MATCH ()-[r]->() RETURN count(r) AS n", database_=database)[0]
    return int(n[0]["n"]) if n else 0, int(r[0]["n"]) if r else 0


def estimate_additions(batches: Mapping[str, list[dict]], fp_rows: list[dict] | None = None) -> tuple[int, int]:
    """An upper bound on what this load adds (MERGE of an existing identity
    adds nothing, so a reload is over-counted, never under-counted)."""
    b = {k: len(v) for k, v in batches.items()}
    teams = len({g[side] for g in batches.get("games", []) for side in ("home", "away")})
    nodes = b.get("weeks", 0) + b.get("contests", 0) + b.get("games", 0) + teams \
        + b.get("players", 0) + b.get("lineups", 0) + b.get("users", 0)
    rels = (b.get("contests", 0)                 # IN_WEEK
            + 3 * b.get("games", 0)              # IN_WEEK + 2 IN_GAME
            + b.get("plays_for", 0) + b.get("lineups", 0)   # ENTERED_IN
            + b.get("contains", 0) + b.get("owned_in", 0) + b.get("stacked_with", 0)
            + b.get("entered", 0)
            + len(fp_rows or []))
    return nodes, rels


def check_capacity(current: tuple[int, int], adding: tuple[int, int],
                   node_limit: int = FREE_TIER_NODES, rel_limit: int = FREE_TIER_RELS,
                   share: float = CAPACITY_SHARE) -> None:
    (n0, r0), (dn, dr) = current, adding
    problems = []
    if n0 + dn > share * node_limit:
        problems.append(f"nodes {n0:,} + {dn:,} = {n0 + dn:,} > {share:.0%} of {node_limit:,}")
    if r0 + dr > share * rel_limit:
        problems.append(f"relationships {r0:,} + {dr:,} = {r0 + dr:,} > {share:.0%} of {rel_limit:,}")
    if problems:
        raise CapacityError("refusing to load: " + "; ".join(problems)
                            + " (Aura Free limits; lower --top-n, load fewer weeks, or raise the limits "
                              "after checking the current terms)")


def guarded_load(driver, database: str, batches: Mapping[str, list[dict]],
                 fp_rows: list[dict] | None = None, node_limit: int = FREE_TIER_NODES,
                 rel_limit: int = FREE_TIER_RELS, log=print) -> dict:
    """Count, check the free-tier headroom, load, count again."""
    before = count_graph(driver, database)
    adding = estimate_additions(batches, fp_rows)
    log(f"graph before: {before[0]:,} nodes, {before[1]:,} relationships; "
        f"this load adds at most {adding[0]:,} / {adding[1]:,}")
    check_capacity(before, adding, node_limit, rel_limit)
    sent = apply_batches(driver, database, batches, fp_rows=fp_rows)
    after = count_graph(driver, database)
    log(f"graph after:  {after[0]:,} nodes, {after[1]:,} relationships "
        f"({after[0] / node_limit:.1%} / {after[1] / rel_limit:.1%} of the limits)")
    return {"before": before, "adding": adding, "after": after, "sent": sent}


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
    "repeat_finishers": """
MATCH (u:User)-[:ENTERED]->(l:Lineup)
WHERE coalesce(l.source, 'top') = 'top'
WITH u, count(l) AS loaded, sum(CASE WHEN l.top_1pct THEN 1 ELSE 0 END) AS top_1pct_lineups,
     count(DISTINCT CASE WHEN l.top_1pct THEN l.week_key END) AS top_1pct_weeks, min(l.rank) AS best_rank
WHERE top_1pct_lineups > 0
RETURN u.name AS user, top_1pct_weeks, top_1pct_lineups, best_rank, loaded
ORDER BY top_1pct_weeks DESC, top_1pct_lineups DESC, best_rank LIMIT 25""",
    "winning_shapes": """
MATCH (l:Lineup)-[:ENTERED_IN]->(c:Contest)-[:IN_WEEK]->(w:Week)
WHERE l.rank = 1
RETURN w.key AS week, l.points AS points, l.stack_label AS stack, l.salary AS salary,
       l.own_sum AS own_sum, l.dupes AS dupes
ORDER BY week""",
}


# The dashboard's insight questions as saved Cypher (cypher/milly_insights.cypher
# carries the same text for the Neo4j Browser). 1-3 need --include-fp loads;
# 5 and 6 compare against our projections/book, which are not in the graph.
INSIGHT_QUERIES: dict[str, str] = {
    "winners_vs_projected": """
MATCH (l:Lineup)-[:CONTAINS]->(p:Player)-[r:FP_PROJECTED]->(w:Week {key: l.week_key})
WHERE coalesce(l.source, 'top') = 'top'
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


# Neo4j Browser queries with parameters (operator 2026-10-06: "reduce my dependency on so many players while having
# suitable alternatives to pivot to"), for portfolios loaded with --users-file. Set them first in the Browser, e.g.
#   BROWSER_PARAMS below (week_key is week_key(season, week): '2026-04')
# They are for looking; the figures come from the reproducible scripts. Never run by run_panel (no parameters there).
BROWSER_PARAMS = ":param user => '<DraftKings name>'    :param week_key => '2026-04'    :param player => '<player name>'"
BROWSER_QUERIES: dict[str, str] = {
    "user_core": """
MATCH (u:User {name: $user})-[:ENTERED]->(l:Lineup {week_key: $week_key})
WITH count(l) AS n, collect(l) AS ls
UNWIND ls AS l
MATCH (l)-[:CONTAINS]->(p:Player)
WITH n, p, count(l) AS k
RETURN p.name AS player, p.position AS position, p.team AS team, k AS lineups, round(100.0 * k / n, 1) AS pct
ORDER BY lineups DESC LIMIT 40""",
    "what_replaced_player": """
MATCH (x:Player {name: $player})
MATCH (u:User {name: $user})-[:ENTERED]->(l:Lineup {week_key: $week_key})
WHERE NOT (l)-[:CONTAINS]->(x)
MATCH (l)-[:CONTAINS]->(p:Player {position: x.position})
RETURN p.name AS instead, p.team AS team, p.team = x.team AS same_team, count(l) AS lineups
ORDER BY lineups DESC LIMIT 15""",
    "user_qb_receivers": """
MATCH (u:User {name: $user})-[:ENTERED]->(l:Lineup {week_key: $week_key})-[:CONTAINS]->(q:Player {position: 'QB'})
OPTIONAL MATCH (l)-[:CONTAINS]->(r:Player) WHERE r.position IN ['WR', 'TE'] AND r.team = q.team
RETURN q.name AS qb, coalesce(r.name, '(no teammate receiver)') AS receiver, r.position AS position,
       count(l) AS lineups
ORDER BY qb, lineups DESC""",
    "user_stack_graph": """
MATCH (u:User {name: $user})-[:ENTERED]->(l:Lineup {week_key: $week_key})-[:CONTAINS]->(q:Player {position: 'QB'})
MATCH (l)-[:CONTAINS]->(r:Player) WHERE r.position IN ['WR', 'TE', 'RB'] AND r.team = q.team
RETURN q, r, count(l) AS lineups""",
}


def run_panel(driver, database: str) -> dict[str, pd.DataFrame]:
    out = {}
    for name, cypher in {**PANEL_QUERIES, **INSIGHT_QUERIES}.items():
        res = driver.execute_query(cypher, database_=database)
        records, keys = res[0], res[2]
        out[name] = pd.DataFrame([r.data() if hasattr(r, "data") else dict(r) for r in records],
                                 columns=list(keys))
    return out
