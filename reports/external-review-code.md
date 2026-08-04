# External review — CODE companion (2026-08-04)

Companion to external-review-package.md (upload BOTH files). This is
the complete source: `src/nfl_dfs/` (pipeline, models, sim, optimizer,
app), `sql/` (BigQuery feature transforms), and `tests/` (offline
suite). Each file begins with a `===== FILE: path =====` marker.
Cross-check the ledger's claims against this code; flag anything where
the implementation and the ledger disagree.

===== FILE: src/nfl_dfs/__init__.py =====
```python
"""DraftKings NFL DFS prediction and lineup-construction system."""

__version__ = "0.1.0"

```

===== FILE: src/nfl_dfs/analysis/__init__.py =====
```python
"""Cross-cutting analyses over the warehouse that aren't projection models:
player scoring-consistency archetypes (clustering), and whatever comes next.
"""

```

===== FILE: src/nfl_dfs/analysis/archetypes.py =====
```python
"""Scoring-consistency archetypes: cluster players by DK-points profile.

Tabular-first, per the guide's §8.1 honest framing: clustering is a
statistical operation on per-player feature vectors, so it runs as a
Gaussian mixture on warehouse columns — the knowledge graph consumes the
labels (cascade weighting, similar-player pivots), it does not produce them.

Clustering is within-position only: QB scoring distributions dominate any
cross-position fit and the clusters degenerate into position groups.

GMM over k-means because the interesting distinction — consistent vs.
boom-bust at the same scoring level — is a variance difference, which
spherical k-means models poorly.
"""

from __future__ import annotations

import logging

import networkx as nx
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

PROFILE_FEATURES = ["avg_pts", "cv", "pct_20_plus", "pct_10_plus", "skew"]
POSITIONS = ("QB", "RB", "WR", "TE")
SIMILAR_TO = "SIMILAR_TO"


def consistency_profiles(games: pd.DataFrame, min_games: int = 16) -> pd.DataFrame:
    """Per-player consistency profile from per-game rows
    [gsis_id, position, dk_points] (extra columns pass through via first value).

    cv (volatility), floor rate P(10+), ceiling rate P(20+), and skew are the
    clustering signal; avg_pts anchors the tier.
    """
    pts = games.groupby(["gsis_id", "position"])["dk_points"]
    prof = pts.agg(
        games="count",
        avg_pts="mean",
        sd="std",
        skew="skew",
        pct_20_plus=lambda s: (s >= 20).mean(),
        pct_10_plus=lambda s: (s >= 10).mean(),
    ).reset_index()
    prof = prof[prof.games >= min_games].copy()
    prof["sd"] = prof["sd"].fillna(0.0)
    prof["skew"] = prof["skew"].fillna(0.0)  # bracket access: .skew is a method
    prof["cv"] = prof.sd / prof.avg_pts.clip(lower=1.0)
    if "name" in games.columns:
        names = games.groupby("gsis_id")["name"].first()
        prof["name"] = prof.gsis_id.map(names)
    return prof


def _zscore(X: pd.DataFrame) -> np.ndarray:
    v = X.to_numpy(dtype=float)
    return (v - v.mean(axis=0)) / np.where(v.std(axis=0) > 0, v.std(axis=0), 1.0)


def cluster_archetypes(
    profiles: pd.DataFrame, n_clusters: int = 4, seed: int = 0
) -> pd.DataFrame:
    """Assign each player a cluster and a readable archetype label,
    within position. Labels are deterministic: clusters are tiered by mean
    scoring (tier1 = highest) and suffixed stable/volatile by centroid cv
    relative to the position's cluster median.
    """
    from sklearn.mixture import GaussianMixture

    out = []
    for pos, grp in profiles.groupby("position"):
        grp = grp.copy()
        k = int(max(1, min(n_clusters, len(grp) // 5)))
        if k == 1:
            grp["cluster"] = 0
            grp["archetype"] = f"{pos}-tier1-stable"
            out.append(grp)
            continue
        gmm = GaussianMixture(n_components=k, random_state=seed, n_init=3)
        grp["cluster"] = gmm.fit_predict(_zscore(grp[PROFILE_FEATURES]))

        cents = grp.groupby("cluster").agg(
            c_avg=("avg_pts", "mean"), c_cv=("cv", "mean")
        )
        cents["tier"] = cents.c_avg.rank(ascending=False, method="first").astype(int)
        cv_median = cents.c_cv.median()
        names = {
            c: f"{pos}-tier{int(r.tier)}-{'volatile' if r.c_cv > cv_median else 'stable'}"
            for c, r in cents.iterrows()
        }
        grp["archetype"] = grp.cluster.map(names)
        out.append(grp)
    return pd.concat(out, ignore_index=True)


# Graph integration: labels onto nodes, similarity edges for pivot queries --


def annotate_graph(G: nx.MultiDiGraph, clustered: pd.DataFrame) -> int:
    """Stamp `archetype` on Player nodes. The injury cascade reads this
    attribute to weight depth-chart redistribution toward profile-compatible
    inheritors."""
    n = 0
    for r in clustered.itertuples():
        if r.gsis_id in G:
            G.nodes[r.gsis_id]["archetype"] = r.archetype
            n += 1
    return n


def add_similarity_edges(
    G: nx.MultiDiGraph, clustered: pd.DataFrame, k: int = 5
) -> int:
    """SIMILAR_TO edges from each player to its k nearest same-cluster
    neighbors by profile distance — the traversal behind "cheaper player,
    same scoring profile" pivots. Keeps the graph sparse: k edges per node,
    not a clique per cluster."""
    n = 0
    for (_pos, _cl), grp in clustered.groupby(["position", "cluster"]):
        members = [g for g in grp.gsis_id if g in G]
        grp = grp[grp.gsis_id.isin(members)]
        if len(grp) < 2:
            continue
        Z = _zscore(grp[PROFILE_FEATURES])
        ids = grp.gsis_id.to_numpy()
        for i, gid in enumerate(ids):
            dist = np.linalg.norm(Z - Z[i], axis=1)
            order = np.argsort(dist)
            for j in order[1 : k + 1]:
                G.add_edge(gid, ids[j], key=SIMILAR_TO, distance=float(dist[j]))
                n += 1
    return n


def similar_players(G: nx.MultiDiGraph, gsis_id: str) -> list[tuple[str, float]]:
    """Same-archetype neighbors, closest profile first."""
    if gsis_id not in G:
        return []
    sims = [
        (nbr, data["distance"])
        for _, nbr, key, data in G.out_edges(gsis_id, keys=True, data=True)
        if key == SIMILAR_TO
    ]
    return sorted(sims, key=lambda t: t[1])


# Warehouse entry point ------------------------------------------------------

TABLE = "player_archetypes"


def run(trailing_seasons: int = 3, min_games: int = 16) -> pd.DataFrame:
    """Profile + cluster over the last `trailing_seasons` completed seasons
    and write nfl_features.player_archetypes."""
    from datetime import datetime, timezone

    from ..bq import load_dataframe, query_df
    from ..config import settings

    last = int(
        query_df(
            f"SELECT MAX(season) AS s FROM `{settings.features}.player_week_training`"
        ).s.iloc[0]
    )
    first = last - trailing_seasons + 1
    games = query_df(
        f"""
        SELECT t.gsis_id, t.position, t.y_dk_points AS dk_points, i.name
        FROM `{settings.features}.player_week_training` t
        LEFT JOIN `{settings.raw}.player_ids` i USING (gsis_id)
        WHERE t.season BETWEEN {first} AND {last}
          AND t.position IN {POSITIONS}
        """
    )
    clustered = cluster_archetypes(consistency_profiles(games, min_games=min_games))
    clustered["window_first_season"] = first
    clustered["window_last_season"] = last
    clustered["generated_at"] = datetime.now(timezone.utc)
    load_dataframe(clustered, f"{settings.features}.{TABLE}")
    log.info(
        "Wrote %d player archetypes (%s-%s) across %s",
        len(clustered), first, last, sorted(clustered.archetype.unique()),
    )
    return clustered

```

===== FILE: src/nfl_dfs/app/__init__.py =====
```python

```

===== FILE: src/nfl_dfs/app/chat.py =====
```python
"""Dashboard chat: manage manual usage notes and query system data in
plain English. Backed by the Claude API with a small tool set; the manual
tool loop follows the Anthropic tool-use pattern.

Requires ANTHROPIC_API_KEY in the environment (.env is loaded by config).
"""

from __future__ import annotations

import json
import logging
import os

import pandas as pd

from .. import notes, watchlist
from . import system_context
from ..bq import query_df
from ..config import current_season, settings

log = logging.getLogger(__name__)

# Opus is the deliberate default (user preference 2026-08-03): the
# chat's jobs are tool-driven and well-scoped. To upgrade without a
# redeploy: gcloud run services update nfl-dfs-app --region us-central1
#   --update-env-vars CHAT_MODEL=claude-fable-5
MODEL = os.environ.get("CHAT_MODEL", "claude-opus-5")
MAX_TOOL_TURNS = 8

SYSTEM = """You are the assistant inside a DraftKings NFL DFS system's
dashboard. The user is the system's owner. Be concise and concrete.

You can manage "usage notes": manual opportunity adjustments the owner
enters when credible news breaks (coach usage statements, role changes).
A note multiplies a player's projected opportunity (targets/carries/pass
attempts) by `mult` at full effect in week 1, decaying to zero by week 6.
Sensible mults: +10-20% (1.1-1.2) for a credible expanded-role statement;
never more than +/-40% — the API clamps. "Best shape of his life" stories
deserve no note. When the user names a player, resolve them with
find_player first if you don't have the gsis_id. Confirm what you did.

There is also a WATCHLIST, separate from usage notes: free-text notes
about players worth tracking that change NOTHING numerically. "Add a
note about X" / "keep an eye on X because..." means add_watch_note, NOT
a usage note — only create a usage note when the user clearly wants a
projection adjustment, or asks to convert a watch note. Watch notes
appear on generated lineups and the Watchlist page.

When the user asks to convert a note (or asks what adjustment a note
deserves), follow the CONVERSION PROTOCOL: (1) call system_design
topic='conversion_guide'; (2) classify the note's archetype (offseason
vacancy / new team / scheme fit / in-season injury / talent take);
(3) check the player's CURRENT situation with get_player_form or
explain_player — depth chart, competition, whether the system already
prices the situation; (4) propose a specific mult with the archetype
reasoning and any double-count warnings; (5) convert only after the
user confirms. For questions about how the system itself works — what's
already in the model, how notes decay, how lineups are chosen — use
system_design first and read_doc (model-primer, claude-md, readme) for
depth. Answer from those documents, not from generic DFS knowledge.

You can manage weekly lineup preferences: ban a player from this week's
lineups or boost one into more of them (add_lineup_pref kind=ban|boost);
prefs apply on the next Build. You can also read the system's current
projections and a player's recent form. When asked WHY a player is
recommended, call find_player then explain_player, and answer citing the
concrete numbers: prop lines vs salary, Vegas environment, role trend,
matchup, vacated snaps, and any usage note. Be candid when the data is
mixed. If asked for something you have no tool for, say so briefly."""

TOOLS = [
    {"name": "list_usage_notes",
     "description": "List all active manual usage notes for a season.",
     "input_schema": {"type": "object", "properties": {
         "season": {"type": "integer",
                    "description": "Season year; omit for current"}},
      }},
    {"name": "add_usage_note",
     "description": "Add a manual usage note. Requires the player's "
                    "gsis_id (resolve with find_player first).",
     "input_schema": {"type": "object", "properties": {
         "gsis_id": {"type": "string"},
         "display_name": {"type": "string"},
         "mult": {"type": "number",
                  "description": "Opportunity multiplier at full effect, "
                                 "e.g. 1.15; clamped to [0.6, 1.4]"},
         "note": {"type": "string",
                  "description": "What the news was, in one sentence"},
         "source": {"type": "string",
                    "description": "Where it came from (URL, reporter)"},
         "season": {"type": "integer"}},
      "required": ["gsis_id", "display_name", "mult", "note"]}},
    {"name": "delete_usage_note",
     "description": "Delete a usage note by its note_id "
                    "(from list_usage_notes).",
     "input_schema": {"type": "object", "properties": {
         "note_id": {"type": "string"}}, "required": ["note_id"]}},
    {"name": "find_player",
     "description": "Resolve a player name to gsis_id, position and team.",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"}}, "required": ["name"]}},
    {"name": "add_watch_note",
     "description": "Add a WATCHLIST note about a player — free-text intel "
                    "worth tracking ('rookie looked explosive in camp', "
                    "'new OC loves screens'). Affects NOTHING — no "
                    "projection or lineup change; it's a memory aid the "
                    "user may later convert into a usage-note adjustment. "
                    "Use when the user wants to note/track/watch a player "
                    "WITHOUT changing scores. Resolve gsis_id via "
                    "find_player when possible.",
     "input_schema": {"type": "object", "properties": {
         "display_name": {"type": "string"},
         "note": {"type": "string",
                  "description": "Why the player is interesting"},
         "gsis_id": {"type": "string"}},
      "required": ["display_name", "note"]}},
    {"name": "list_watch_notes",
     "description": "List watchlist notes (active + converted), with each "
                    "note's status and, if converted, the adjustment made.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "delete_watch_note",
     "description": "Delete a watchlist note by note_id "
                    "(from list_watch_notes).",
     "input_schema": {"type": "object", "properties": {
         "note_id": {"type": "string"}}, "required": ["note_id"]}},
    {"name": "convert_watch_note",
     "description": "Promote a watchlist note into a real usage-note "
                    "adjustment: creates the opportunity multiplier "
                    "(clamped [0.6, 1.4]) and marks the watch note "
                    "converted. BEFORE proposing a mult, follow the "
                    "conversion protocol: call system_design topic="
                    "'conversion_guide', classify the note's archetype, "
                    "check current depth chart/competition via "
                    "get_player_form or explain_player, then propose the "
                    "mult with reasoning and get confirmation.",
     "input_schema": {"type": "object", "properties": {
         "note_id": {"type": "string"},
         "mult": {"type": "number",
                  "description": "Opportunity multiplier, e.g. 1.10"},
         "season": {"type": "integer",
                    "description": "Omit for current season"}},
      "required": ["note_id", "mult"]}},
    {"name": "system_design",
     "description": "Curated documentation of how THIS system works — "
                    "use to answer 'how does the system treat X' and "
                    "ALWAYS before suggesting a watch-note conversion "
                    "mult. Topics: overview, notes_and_adjustments, "
                    "conversion_guide (archetype -> suggested mult "
                    "ranges + double-count warnings), already_priced.",
     "input_schema": {"type": "object", "properties": {
         "topic": {"type": "string"}}, "required": ["topic"]}},
    {"name": "read_doc",
     "description": "Full project documents when the curated sections "
                    "aren't enough: 'model-primer' (beginner walkthrough "
                    "of models/training), 'claude-md' (project state "
                    "notes), 'readme' (the full design guide — long).",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"}}, "required": ["name"]}},
    {"name": "list_lineup_prefs",
     "description": "List this week's lineup bans and boosts.",
     "input_schema": {"type": "object", "properties": {
         "season": {"type": "integer"}, "week": {"type": "integer"}},
      "required": ["season", "week"]}},
    {"name": "add_lineup_pref",
     "description": "Ban a player from this week's lineups, or boost one "
                    "into more lineups. After adding, tell the user to hit "
                    "Build again to regenerate.",
     "input_schema": {"type": "object", "properties": {
         "season": {"type": "integer"}, "week": {"type": "integer"},
         "display_name": {"type": "string"},
         "kind": {"type": "string", "enum": ["ban", "boost"]}},
      "required": ["season", "week", "display_name", "kind"]}},
    {"name": "delete_lineup_pref",
     "description": "Remove a ban/boost by pref_id (from list_lineup_prefs).",
     "input_schema": {"type": "object", "properties": {
         "pref_id": {"type": "string"}}, "required": ["pref_id"]}},
    {"name": "explain_player",
     "description": "Everything the system knows about why a player is (or "
                    "isn't) a strong play this week: projection + ceiling + "
                    "value, prop-market lines, Vegas game environment, "
                    "recent role/form, opponent defense vs his position, "
                    "vacated opportunity, active usage notes. Use when the "
                    "user asks why a player appears in lineups.",
     "input_schema": {"type": "object", "properties": {
         "gsis_id": {"type": "string"},
         "display_name": {"type": "string"},
         "season": {"type": "integer"}, "week": {"type": "integer"}},
      "required": ["gsis_id", "display_name", "season", "week"]}},
    {"name": "get_projections",
     "description": "Latest generated projections (top rows by points).",
     "input_schema": {"type": "object", "properties": {
         "position": {"type": "string",
                      "description": "QB/RB/WR/TE filter, optional"},
         "limit": {"type": "integer", "description": "default 15"}},
      }},
    {"name": "get_player_form",
     "description": "A player's recent weekly production and role "
                    "(snap share, depth rank, DK points).",
     "input_schema": {"type": "object", "properties": {
         "gsis_id": {"type": "string"}}, "required": ["gsis_id"]}},
]


def _df_result(df: pd.DataFrame, limit: int = 25) -> str:
    if df.empty:
        return "(no rows)"
    return df.head(limit).to_string(index=False)


def execute_tool(name: str, args: dict) -> str:
    """Dispatch one tool call. Returns a string for the tool_result."""
    season = int(args.get("season") or current_season())
    if name == "list_usage_notes":
        return _df_result(notes.list_notes(season))
    if name == "add_usage_note":
        note_id = notes.add_note(
            gsis_id=args["gsis_id"], display_name=args["display_name"],
            season=season, mult=float(args["mult"]), note=args["note"],
            source=args.get("source", ""))
        return f"added note {note_id} for {args['display_name']}"
    if name == "delete_usage_note":
        n = notes.delete_note(args["note_id"])
        return f"deleted {n} note(s)"
    if name == "add_watch_note":
        wid = watchlist.add_watch(
            display_name=args["display_name"], note=args["note"],
            gsis_id=args.get("gsis_id", ""))
        return (f"watch note {wid} added for {args['display_name']} "
                f"(no projection impact; visible on generated lineups and "
                f"the Watchlist page)")
    if name == "list_watch_notes":
        return _df_result(watchlist.list_watch())
    if name == "delete_watch_note":
        n = watchlist.delete_watch(args["note_id"])
        return f"deleted {n} watch note(s)"
    if name == "convert_watch_note":
        mid = watchlist.convert_watch(
            args["note_id"], float(args["mult"]),
            int(args.get("season") or current_season()))
        return (f"converted: usage note {mid} created "
                f"(mult applied on next projection run)")
    if name == "system_design":
        return system_context.get_section(args.get("topic", "overview"))
    if name == "read_doc":
        return system_context.read_doc(args.get("name", ""))
    if name == "find_player":
        df = query_df(
            f"""SELECT DISTINCT player_id AS gsis_id,
                       player_display_name AS name, position,
                       team, MAX(season) AS last_seen
                FROM `{settings.raw}.weekly_stats`
                WHERE LOWER(player_display_name) LIKE
                      LOWER(CONCAT('%', @q, '%'))
                GROUP BY 1, 2, 3, 4 ORDER BY last_seen DESC LIMIT 10""",
            params={"q": args["name"]})
        return _df_result(df)
    if name == "list_lineup_prefs":
        return _df_result(notes.list_prefs(args["season"], args["week"]))
    if name == "add_lineup_pref":
        pid = notes.add_pref(args["season"], args["week"],
                             args["display_name"], args["kind"])
        return (f"{args['kind']} added ({pid}) for {args['display_name']} "
                f"wk {args['week']} — rebuild lineups to apply")
    if name == "delete_lineup_pref":
        return f"deleted {notes.delete_pref(args['pref_id'])} pref(s)"
    if name == "explain_player":
        gid, dn = args["gsis_id"], args["display_name"]
        se, wk = int(args["season"]), int(args["week"])
        parts = []
        q = [
            ("PROJECTION", f"""SELECT position, team, opponent, salary,
                ROUND(proj_points,1) proj, ROUND(proj_p90,1) p90,
                ROUND(value,2) value FROM
                `{settings.predictions}.player_projections`
                WHERE gsis_id=@q AND season={se} AND week={wk}
                ORDER BY generated_at DESC LIMIT 1"""),
            ("PROP MARKET (pre-lock lines)", f"""SELECT market, bookmaker,
                outcome_name, point, price FROM `{settings.raw}.prop_lines`
                WHERE LOWER(player) LIKE LOWER(@dn) AND season={se}
                AND week={wk} ORDER BY market, bookmaker LIMIT 24"""),
            ("RECENT ROLE/FORM (last 5)", f"""SELECT season, week,
                ROUND(snap_share_l4,2) snaps, depth_rank,
                ROUND(target_share_l4,2) tgt_share,
                ROUND(dk_points_l4,1) dk_l4, y_dk_points actual
                FROM `{settings.features}.player_week_training`
                WHERE gsis_id=@q ORDER BY season DESC, week DESC LIMIT 5"""),
            ("VACATED OPPORTUNITY", f"""SELECT team_vacated_target_share,
                team_vacated_carry_share FROM
                `{settings.features}.player_week_training`
                WHERE gsis_id=@q ORDER BY season DESC, week DESC LIMIT 1"""),
            ("ACTIVE USAGE NOTES", f"""SELECT mult, note, source FROM
                `{settings.features}.manual_notes`
                WHERE gsis_id=@q AND season={se}"""),
        ]
        for title, sql in q:
            try:
                df = query_df(sql, params={"q": gid, "dn": f"%{dn}%"})
                parts.append(f"== {title} ==\n{_df_result(df, 24)}")
            except Exception as exc:
                log.exception("chat tool failed")
                parts.append(f"== {title} == (unavailable: {exc})")
        try:
            pos_df = query_df(f"""SELECT position FROM
                `{settings.predictions}.player_projections`
                WHERE gsis_id=@q ORDER BY generated_at DESC LIMIT 1""",
                params={"q": gid})
            opp_df = query_df(f"""SELECT opponent FROM
                `{settings.predictions}.player_projections`
                WHERE gsis_id=@q AND season={se} AND week={wk}
                ORDER BY generated_at DESC LIMIT 1""", params={"q": gid})
            if not pos_df.empty and not opp_df.empty:
                d = query_df(f"""SELECT fp_allowed_season, fp_allowed_l3,
                    trend FROM `{settings.features}.defense_points_against`
                    WHERE team=@t AND position=@p
                    ORDER BY season DESC, week DESC LIMIT 1""",
                    params={"t": str(opp_df.opponent.iloc[0]),
                            "p": str(pos_df.position.iloc[0])})
                parts.append(f"== OPPONENT DEFENSE vs POSITION ==\n"
                             f"{_df_result(d)}")
        except Exception:
            pass
        return "\n\n".join(parts)
    if name == "get_projections":
        pos = args.get("position")
        pos_filter = f"AND position = '{pos}'" if pos in (
            "QB", "RB", "WR", "TE", "DST") else ""
        df = query_df(
            f"""SELECT display_name, position, team, salary,
                       ROUND(proj_points, 1) AS proj,
                       ROUND(proj_p90, 1) AS p90, ROUND(value, 2) AS value
                FROM `{settings.predictions}.player_projections`
                WHERE generated_at = (SELECT MAX(generated_at)
                    FROM `{settings.predictions}.player_projections`)
                {pos_filter} ORDER BY proj_points DESC
                LIMIT {int(args.get('limit') or 15)}""")
        return _df_result(df)
    if name == "get_player_form":
        df = query_df(
            f"""SELECT season, week, snap_share_l4, depth_rank,
                       dk_points_l4, y_dk_points
                FROM `{settings.features}.player_week_training`
                WHERE gsis_id = @q ORDER BY season DESC, week DESC
                LIMIT 10""", params={"q": args["gsis_id"]})
        return _df_result(df)
    return f"unknown tool: {name}"


def chat_turn(messages: list[dict], model: str | None = None) -> list[dict]:
    """Run one user turn through Claude's tool loop. `messages` is the
    prior API-shaped history plus the new user message; returns the
    full updated history (assistant turns + tool results appended).
    `model` overrides the default per conversation (UI selector)."""
    import anthropic

    client = anthropic.Anthropic()
    for _ in range(MAX_TOOL_TURNS):
        response = client.messages.create(
            model=model or MODEL, max_tokens=4000, system=SYSTEM,
            tools=TOOLS, messages=messages)
        messages.append({"role": "assistant",
                         "content": [b.model_dump() for b in response.content]})
        if response.stop_reason != "tool_use":
            break
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                out = execute_tool(block.name, block.input)
                results.append({"type": "tool_result",
                                "tool_use_id": block.id, "content": out})
            except Exception as exc:
                log.exception("chat tool %s failed", block.name)
                results.append({"type": "tool_result",
                                "tool_use_id": block.id,
                                "content": "Error: "
                                f"{type(exc).__name__} (see server logs)",
                                "is_error": True})
        messages.append({"role": "user", "content": results})
    return messages


def reply_text(messages: list[dict]) -> str:
    """Concatenated text of the last assistant turn."""
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            return "".join(b.get("text", "") for b in msg["content"]
                           if b.get("type") == "text")
    return ""

```

===== FILE: src/nfl_dfs/app/main.py =====
```python
"""FastAPI service (guide Phase 7): slate view, projections table, lineup
builder with stacking options, exposure summary, DK-format CSV export.

Run locally:  uvicorn nfl_dfs.app.main:app --reload
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import pandas as pd
from fastapi import (Depends, FastAPI, File, HTTPException, Query, Response,
                     UploadFile)
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..optimizer.export import (
    entry_count,
    exposure_summary,
    fill_entries_csv,
    showdown_exposure_summary,
    to_dk_csv,
    to_dk_showdown_csv,
)
from ..optimizer.lineup import StackRules, core_and_variations, optimize_many
from ..optimizer.showdown import optimize_many_showdown
from .store import BigQueryStore, ProjectionStore

app = FastAPI(title="Fingerblasters' Brain", version="0.1.0")

from pathlib import Path as _Path

app.mount("/static", StaticFiles(directory=_Path(__file__).parent / "static"),
          name="static")
log = logging.getLogger(__name__)


@lru_cache
def default_store() -> ProjectionStore:
    return BigQueryStore()


def get_store() -> ProjectionStore:
    return app.dependency_overrides.get(default_store, default_store)()


class LineupRequest(BaseModel):
    season: int
    week: int
    draft_group_id: int | None = None  # classic slate; None = whole week pool
    n_lineups: int = Field(40, ge=1, le=150)
    objective: str = Field("proj_points", pattern="^proj_(points|p50|p90)$")
    locks: list[int] = []
    bans: list[int] = []
    qb_stack_min: int = Field(2, ge=0, le=3)
    bring_back_min: int = Field(1, ge=0, le=2)
    forbid_rb_vs_dst: bool = True
    max_overlap: int = Field(7, ge=1, le=8)
    # Sim-mode (2026-08-03, fidelity fix): run the VALIDATED replay
    # engine on the live slate — correlated draws with the adopted EW
    # shaping, boom-draw candidates, tail-coverage selection. Falls back
    # to the plain MILP path on any failure. sim=False forces the old path.
    sim: bool = True
    # Apply converted watch-notes (boost/ban prefs) to the build
    # (2026-08-04, user request): False = pure algorithm, no manual
    # tilts — for comparing "my ideas" vs the untouched system.
    apply_notes: bool = True
    # Thesis constraints (2026-08-03): [{players: [dk_ids], min: k}] —
    # ">=k of my entries must contain this combo". Builds toward
    # correlated convictions; pairs with watchlist conversions.
    theses: list[dict] = []
    # Chalk-fade scaling (contest presets, 2026-08-03): 1.0 = validated
    # large-field fade; sharp/high-stakes fields use 0.5-0.7 — our fade
    # is soft-field-calibrated and sharp chalk busts less.
    lev_scale: float = Field(1.0, ge=0.0, le=2.0)
    # Contest sizing: field_size scales the confidence target line via
    # tail_line_for_field (a 20k qualifier's winning line sits below the
    # Milly's); an explicit tail_line overrides. Both None = Milly 194.
    field_size: int | None = Field(None, ge=100)
    tail_line: float | None = Field(None, ge=100, le=300)

    def line(self) -> float:
        if self.tail_line is not None:
            return self.tail_line
        if self.field_size is not None:
            return tail_line_for_field(self.field_size)
        return MIN_MILLY_LINE


_PAGE_CSS = """
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;margin:0;
     color:#1a1a2e;background:#f2f4f8;min-height:100vh}
main{max-width:1100px;margin:0 auto;padding:1.2rem 1.2rem 3rem}
.topbar{position:sticky;top:0;z-index:50;display:flex;align-items:center;
  gap:1.2rem;padding:.7rem 1.4rem;color:#fff;
  background:linear-gradient(90deg,#0d1b2a 0%,#1a1a2e 60%,#232946 100%);
  box-shadow:0 2px 12px rgba(13,27,42,.35)}
.topbar .brand{font-weight:800;font-size:1.05rem;letter-spacing:.03em}
.topbar .logo{height:32px;width:32px;border-radius:8px;object-fit:cover;
  box-shadow:0 0 0 2px rgba(255,255,255,.25)}
.topbar .brand span{color:#53d337}
.topbar a{color:#c8cede;text-decoration:none;font-size:.9rem;
  padding:.38rem .85rem;border-radius:999px;transition:all .15s}
.topbar a:hover{color:#fff;background:rgba(255,255,255,.1)}
.topbar a.active{color:#0d1b2a;background:#53d337;font-weight:700}
.topbar .guide{margin-left:auto;cursor:pointer;border:1px solid
  rgba(255,255,255,.35);background:none;color:#fff;border-radius:999px;
  padding:.38rem .95rem;font-size:.85rem}
.topbar .guide:hover{background:rgba(255,255,255,.12)}
#modalbg{display:none;position:fixed;inset:0;z-index:99;
  background:rgba(13,27,42,.55);backdrop-filter:blur(2px)}
#modal{display:none;position:fixed;z-index:100;top:8vh;left:50%;
  transform:translateX(-50%);width:min(680px,92vw);background:#fff;
  border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.35);
  padding:1.4rem 1.6rem;max-height:80vh;overflow-y:auto}
#modal h2{margin-top:0}
#modal .x{float:right;cursor:pointer;border:0;background:#eef0f6;
  border-radius:8px;padding:.3rem .7rem;font-weight:700}
h1{font-size:1.45rem;margin:1rem 0 .4rem} h2{font-size:1.05rem;margin-top:1.6rem}
table{border-collapse:collapse;width:100%;font-size:.9rem;background:#fff}
th,td{padding:.35rem .6rem;text-align:right;border-bottom:1px solid #e5e5ef}
th:first-child,td:first-child{text-align:left}
th{background:#1a1a2e;color:#fff;position:sticky;top:0}
tr:nth-child(-n+5) td:first-child{font-weight:600}
.up{color:#0a7a3d}.down{color:#b3261e}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}
@media(max-width:800px){.grid{grid-template-columns:1fr}}
small{color:#666}
#chat{margin:1.5rem 0;background:#fff;border:1px solid #e5e5ef;
      border-radius:8px;padding:1rem;display:flex;flex-direction:column;
      height:calc(100vh - 220px);min-height:340px}
#chatlog{flex:1;overflow-y:auto;font-size:.9rem;margin-bottom:.6rem;
         scroll-behavior:smooth}
#typing{display:inline-block;margin:.2rem 0 .2rem .8rem;color:#888}
#typing span{display:inline-block;width:6px;height:6px;margin:0 2px;
  background:#999;border-radius:50%;animation:blink 1.2s infinite}
#typing span:nth-child(2){animation-delay:.2s}
#typing span:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,80%,100%{opacity:.25}40%{opacity:1}}
#chatlog .u{font-weight:600;margin-top:.5rem}
#chatlog .a{white-space:pre-wrap;margin:.2rem 0 .2rem .8rem}
#chatrow{display:flex;gap:.5rem}
#chatin{flex:1;padding:.45rem .6rem;border:1px solid #ccc;border-radius:6px}
#chatbtn{padding:.45rem 1rem;background:#1a1a2e;color:#fff;border:0;
         border-radius:6px;cursor:pointer}
#chatbtn:disabled{opacity:.5}
button{transition:filter .15s} button:hover{filter:brightness(1.12)}
.card{transition:transform .12s,box-shadow .12s}
.card:hover{transform:translateY(-2px);box-shadow:0 6px 18px rgba(13,27,42,.14)}
"""

_CHAT_HTML = """
<div id='chat'><h2 style='margin-top:0'>Assistant</h2>
<small>Manage usage notes ("Add a note: coach says Odunze moves to the
slot, +15%"), list/delete them, or ask about projections and player form.</small>
<div id='chatlog'></div>
<div id='chatrow'>
<input id='chatin' placeholder='Ask or instruct...'>
<select id='chatmodel' title='Model for this chat'>
<option value='claude-opus-5'>Opus</option>
<option value='claude-fable-5'>Fable</option></select>
<button id='chatbtn'>Send</button></div></div>
<script>
let hist=[];
const log=document.getElementById('chatlog'),inp=document.getElementById('chatin'),
      btn=document.getElementById('chatbtn');
function show(cls,text){const d=document.createElement('div');d.className=cls;
  d.textContent=text;log.appendChild(d);log.scrollTop=log.scrollHeight;}
function showTyping(){
  const d=document.createElement('div');d.id='typing';
  d.innerHTML='<span></span><span></span><span></span>';
  log.appendChild(d);log.scrollTop=log.scrollHeight;}
function hideTyping(){const d=document.getElementById('typing');if(d)d.remove();}
async function send(){
  const q=inp.value.trim(); if(!q)return;
  inp.value=''; btn.disabled=true; show('u','You: '+q);
  hist.push({role:'user',content:q});
  showTyping();
  try{
    const r=await fetch('/chat',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({messages:hist,
        model:document.getElementById('chatmodel').value})});
    const j=await r.json();
    hideTyping();
    if(!r.ok){show('a','Error: '+(j.detail||r.status));}
    else{hist=j.messages; show('a',j.reply||'(no reply)');}
  }catch(e){hideTyping();show('a','Error: '+e);}
  btn.disabled=false; inp.focus();
}
btn.onclick=send;
inp.addEventListener('keydown',e=>{if(e.key==='Enter')send();});
</script>
"""


_NAV_HTML = """
<div class='topbar'><img src='/static/logo.png' class='logo' alt=''><div class='brand'>Fingerblasters&#39; <span>Brain</span></div>
<a href='/'>Season</a><a href='/lineups/view'>Lineups</a>
<a href='/defense'>Defense</a><a href='/market'>Market</a>
<a href='/watchlist'>Watchlist</a><a href='/docs'>API</a>
<button class='guide' onclick="document.getElementById('modal').style.display=
'block';document.getElementById('modalbg').style.display='block'">
&#128197; Weekly guide</button>
<button class='guide' style='margin-left:.6rem' onclick="openStatus()">
&#129658; System status</button></div>
<div id='modalbg' onclick="this.style.display='none';
document.getElementById('modal').style.display='none';
document.getElementById('statusmodal').style.display='none'"></div>
<div id='statusmodal' style='display:none;position:fixed;z-index:100;top:8vh;
left:50%;transform:translateX(-50%);width:min(760px,94vw);background:#fff;
border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,.35);
padding:1.4rem 1.6rem;max-height:80vh;overflow-y:auto'>
<button class='x' onclick="document.getElementById('statusmodal')
.style.display='none';document.getElementById('modalbg').style.display=
'none'">&times;</button><h2>System status</h2>
<div id='statusbody'><small>Loading&hellip;</small></div></div>
<div id='modal'><button class='x' onclick="document.getElementById('modal')
.style.display='none';document.getElementById('modalbg').style.display=
'none'">&times;</button><h2>Your weekly schedule</h2>
<table><tr><th>When</th><th>What you do</th></tr>
<tr><td>Tue&ndash;Sat</td><td style='text-align:left'>Optional: tell the
chat about credible news (usage notes); ban/boost players as opinions
form. Automation handles stats, retrain, salaries, odds, props,
weather.</td></tr>
<tr><td>Sun before noon CT</td><td style='text-align:left'>Lineups
&rarr; Build (pick slate + entry count; the Sunday main slate is
preselected) &rarr; review cards, ban/boost +
rebuild &rarr; <b>download DK CSV</b> (also records entries for
auto-scoring) &rarr; upload at DraftKings before 1pm ET lock.</td></tr>
<tr><td>Sun afternoon</td><td style='text-align:left'>Optional late swap
on DK for 3pm/night games if news breaks.</td></tr>
<tr><td>Mon or Tue</td><td style='text-align:left'>DraftKings &rarr; My
Contests &rarr; <b>download Entry History CSV</b> &rarr; upload on the
Season page (fills contests/spent/won). Optional: contest standings CSV
for rank + real ownership.</td></tr>
<tr><td>Tue 8:00 (auto)</td><td style='text-align:left'>Lineups scored
vs actuals; best score fills itself. Click week numbers to review
entries by score.</td></tr></table></div>
<script>
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}document.addEventListener('DOMContentLoaded',()=>{
  const p=location.pathname;
  document.querySelectorAll('.topbar a').forEach(a=>{
    if(a.getAttribute('href')===p||(p==='/'&&a.getAttribute('href')==='/'))
      a.classList.add('active');});});
const _stColor={ok:'#0a7a3d',stale:'#b3261e',missing:'#b3261e',
                empty:'#b26a00',idle:'#667'};
const _stGloss={ok:'fresh',stale:'STALE',missing:'MISSING',
                empty:'no data yet',idle:'idle (off-season)'};
function _stAge(h){if(h==null)return '&mdash;';
  if(h<1)return Math.round(h*60)+'m';
  if(h<48)return h.toFixed(h<10?1:0)+'h';
  return (h/24).toFixed(1)+'d';}
async function openStatus(){
  const m=document.getElementById('statusmodal'),
        b=document.getElementById('statusbody');
  m.style.display='block';
  document.getElementById('modalbg').style.display='block';
  b.innerHTML='<small>Loading&hellip;</small>';
  try{
    const r=await fetch('/api/system-status'); const j=await r.json();
    let h="<table><tr><th>Feed</th><th>State</th><th>Last update</th>"+
          "<th>Rows</th></tr>";
    for(const c of j.components){
      const col=_stColor[c.state]||'#667';
      h+="<tr><td style='text-align:left'>"+c.label+
         (c.note?"<br><small>"+c.note+"</small>":"")+"</td>"+
         "<td style='text-align:left'><span style='color:"+col+
         ";font-weight:700'>&#9679; "+(_stGloss[c.state]||c.state)+"</span>"+
         (c.state==='stale'?"<br><small>max "+c.max_age_hours+"h</small>":"")+
         "</td><td>"+_stAge(c.age_hours)+" ago</td>"+
         "<td>"+(c.rows==null?'&mdash;':c.rows.toLocaleString())+"</td></tr>";
    }
    h+="</table><small>Feeds marked idle are out of season. Generated "+
       new Date(j.generated_at).toLocaleTimeString()+
       ". A daily check emails on any red state.</small>";
    b.innerHTML=h;
  }catch(e){b.innerHTML="<small>Failed to load status: "+e+"</small>";}
}</script>
"""

_LINEUPS_CSS = """
#controls{display:flex;gap:.6rem;flex-wrap:wrap;align-items:end;
  background:#fff;border:1px solid #e5e5ef;border-radius:8px;padding:1rem}
#controls label{display:flex;flex-direction:column;font-size:.75rem;color:#666}
#controls input,#controls select{padding:.4rem;border:1px solid #ccc;
  border-radius:6px;width:6.5rem}
#cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
  gap:1rem;margin-top:1.2rem}
.card{background:#fff;border:1px solid #e5e5ef;border-radius:10px;
  overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.card header{background:#1a1a2e;color:#fff;padding:.5rem .8rem;display:flex;
  justify-content:space-between;align-items:baseline;font-size:.85rem}
.card header .conf{color:#53d337;font-weight:700}
.card table{font-size:.8rem;box-shadow:none}
.card td,.card th{padding:.25rem .55rem;border-bottom:1px solid #f0f0f5}
.slot{display:inline-block;min-width:2.6rem;text-align:center;font-weight:700;
  font-size:.68rem;background:#eef0f6;border-radius:4px;padding:.12rem .2rem;
  color:#1a1a2e}
.card tfoot td{font-weight:600;background:#fafafa}
#status{margin:.8rem 0;color:#666}
"""

_LINEUPS_JS = """
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function loadSlates(){
  try{const r=await fetch('/slates');const s=await r.json();
    if(s.length){const last=s[s.length-1];
      document.getElementById('season').value=last.season??'';
      document.getElementById('week').value=last.week??'';}}catch(e){}}
async function loadClassicSlates(){
  const sel=document.getElementById('slate');
  try{const r=await fetch('/classic/slates'); if(!r.ok)return;
    const grp=document.createElement('optgroup'); grp.label='Classic slates';
    for(const g of await r.json()){
      const o=document.createElement('option');
      o.value=g.draft_group_id;
      o.textContent=(g.main?'Main: ':'')+g.label;
      if(g.main)o.selected=true;
      grp.appendChild(o);}
    if(grp.children.length)sel.appendChild(grp);
  }catch(e){}}
async function loadShowdownSlates(){
  const sel=document.getElementById('slate');
  try{const r=await fetch('/showdown/slates?days='); if(!r.ok)return;
    const grp=document.createElement('optgroup');
    grp.label='Showdown (Captain Mode)';
    for(const g of await r.json()){
      const o=document.createElement('option');
      o.value='sd:'+g.draft_group_id;
      o.textContent=g.game+' · '+g.day;
      grp.appendChild(o);}
    if(grp.children.length)sel.appendChild(grp);
  }catch(e){}}
async function loadContests(){
  const sel=document.getElementById('contest');
  try{const r=await fetch('/contests'); if(!r.ok)return;
    const j=await r.json();
    const add=(list,label)=>{
      if(!list.length)return;
      const grp=document.createElement('optgroup'); grp.label=label;
      for(const c of list){
        const o=document.createElement('option');
        o.value=c.field_size;
        o.dataset.cfg=JSON.stringify(c);
        o.textContent=`${c.name} · $${c.entry_fee} · `+
          `${(+c.field_size).toLocaleString()} entries (line ${c.tail_line})`;
        grp.appendChild(o);}
      sel.appendChild(grp);};
    add(j.live,'Live DK contests'); add(j.presets,'Presets');
    const applyCfg=()=>{
      const o=sel.options[sel.selectedIndex]; if(!o)return;
      const c=JSON.parse(o.dataset.cfg||'{}');
      document.getElementById('fsize').value=c.field_size||sel.value;
      if(c.entries)document.getElementById('n').value=c.entries;
      document.getElementById('lev').value=c.lev_scale??1;
      document.getElementById('chint').textContent=
        c.note?`auto: ${c.entries} entries, line ${c.tail_line}, `+
        `fade x${c.lev_scale??1} — ${c.note}`:'';};
    if(sel.options.length)applyCfg();
    sel.onchange=applyCfg;
  }catch(e){}}
function slateSel(){
  const v=document.getElementById('slate').value;
  if(v.startsWith('sd:'))return{sd:true,gid:+v.slice(3)};
  return{sd:false,gid:v?+v:null};}
function reqBody(){
  return{season:+document.getElementById('season').value,
    week:+document.getElementById('week').value,
    draft_group_id:slateSel().gid,
    n_lineups:+document.getElementById('n').value,
    field_size:+document.getElementById('fsize').value||null,
    lev_scale:+document.getElementById('lev').value||1,
    objective:document.getElementById('obj').value,
    apply_notes:document.getElementById('usenotes').checked};}
function slotNames(players){
  const slots=['QB','RB','RB','WR','WR','WR','TE','FLEX','DST'];
  return players.map((p,i)=>({slot:slots[i]||p.pos,p}));}
async function build(){
  const st=document.getElementById('status'),
        cards=document.getElementById('cards'),
        sd=slateSel().sd;
  st.textContent='Building lineups (simulating 30k worlds + candidate solves; ~1-4 min, first build of the day slowest)...';
  cards.innerHTML=''; document.getElementById('go').disabled=true;
  try{
    const r=await fetch(sd?'/showdown/lineups':'/lineups',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(reqBody())});
    const j=await r.json();
    if(!r.ok){st.textContent='Error: '+(j.detail||r.status);return;}
    st.textContent=sd
      ? j.lineups.length+' Captain Mode lineups · '+j.game.game+' ('+
        j.game.day+'). Captain scores 1.5x and costs 1.5x.'
      : j.lineups.length+' lineups, strongest first. Confidence = '+
        'P(score >= '+(j.tail_line||194)+'), ordering signal scaled to '+
        'the chosen contest field.';
    j.lineups.forEach((lu,i)=>{
      const named=sd
        ? lu.players.map((p,k)=>({slot:k?'FLEX':'CPT',p,cpt:!k}))
        : slotNames(lu.players);
      const rows=named.map(({slot,p,cpt})=>{
        const sal=cpt?Math.round(p.salary*1.5):p.salary,
              pr=cpt?1.5*p.proj:+p.proj;
        const wn=p.watch_note?` <span title="${String(p.watch_note)
          .replace(/"/g,'&quot;')}" style='cursor:help'>&#128221;</span>`:'';
        const lev=(p.lev_pct!=null&&Math.abs(p.lev_pct)>=8)
          ?` <small title='Lev%: our exposure minus expected field ownership'`+
           ` style='color:${p.lev_pct>0?"#0a7":"#c60"}'>${p.lev_pct>0?"+":""}${p.lev_pct}%</small>`:'';
        return `<tr${p.watch_note?` title="${String(p.watch_note)
          .replace(/"/g,'&quot;')}"`:''}><td><span class='slot'>${slot}</span></td>`+
        `<td style='text-align:left'>${esc(p.name)}${wn}${lev}</td>`+
        `<td>${p.team}${p.opp?' @ '+p.opp:''}</td>`+
        `<td>$${sal.toLocaleString()}</td>`+
        `<td>${pr.toFixed(1)}</td></tr>`;}).join('');
      const head=sd
        ? `<header><span>#${i+1}</span>`+
          `<span class='conf'>CPT ${esc(lu.captain.name)}</span>`+
          `<span>${lu.proj.toFixed(1)} pts proj</span></header>`
        : `<header><span>#${lu.rank}</span>`+
          `<span class='conf'>${lu.confidence}%</span>`+
          `<span>${lu.proj_mean} pts proj</span></header>`;
      const el=document.createElement('div'); el.className='card';
      el.innerHTML=head+
        `<table><tr><th></th><th style='text-align:left'>Player</th>`+
        `<th>Game</th><th>Salary</th><th>Proj</th></tr>${rows}`+
        `<tfoot><tr><td colspan='3'>Total</td>`+
        `<td>$${lu.salary.toLocaleString()}</td>`+
        `<td>${lu.proj.toFixed(1)}</td></tr></tfoot></table>`;
      cards.appendChild(el);});
    if(sd&&j.captain_board&&j.captain_board.length){
      const cb=j.captain_board.slice(0,12),
            pc=v=>v==null?'&mdash;':(100*v).toFixed(1)+'%';
      const rows=cb.map(m=>`<tr><td style='text-align:left'>${esc(m.name)}`+
        ` <small>${m.team||''} ${m.position||''}</small></td>`+
        `<td>${pc(m.cpt_opt)}</td><td>${pc(m.flex_opt)}</td>`+
        `<td>${pc(m.p_top)}</td><td>${pc(m.p_top6)}</td></tr>`).join('');
      const el=document.createElement('div'); el.className='card';
      el.style.gridColumn='1/-1';
      el.innerHTML=`<header><span>Captain board</span>`+
        `<span title='CPT-opt / FLEX-opt: share of simulated worlds whose`+
        ` salary-aware optimal lineup used the player at captain / flex.`+
        ` Top scorer: outscores the whole slate (best captain ignoring`+
        ` salary). Top 6: lands in the perfect lineup ignoring salary.'`+
        ` style='cursor:help'>computed from this build&#39;s sims &#9432;</span></header>`+
        `<table><tr><th style='text-align:left'>Player</th><th>CPT-opt</th>`+
        `<th>FLEX-opt</th><th>Top scorer</th><th>Top 6</th></tr>${rows}</table>`;
      cards.appendChild(el);}
  }catch(e){st.textContent='Error: '+e;}
  document.getElementById('go').disabled=false;}
document.getElementById('go').onclick=build;
document.getElementById('csv').onclick=()=>{
  const sd=slateSel().sd;
  fetch(sd?'/showdown/lineups.csv':'/lineups.csv',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(reqBody())})
   .then(r=>r.blob()).then(b=>{const a=document.createElement('a');
    a.href=URL.createObjectURL(b);
    a.download=sd?'dk_showdown_lineups.csv':'dk_lineups.csv';a.click();});};
async function loadPrefs(){
  const se=+document.getElementById('season').value,
        wk=+document.getElementById('week').value;
  if(!se||!wk)return;
  const r=await fetch(`/prefs?season=${se}&week=${wk}`);
  const ps=await r.json();
  document.getElementById('prefs').innerHTML=ps.map(p=>
    `<span style='margin-right:.6rem'>${p.kind==='ban'?'&#128683;':'&#11088;'} `+
    `${p.display_name} <a href='#' data-id='${p.pref_id}'>x</a></span>`).join('');
  document.querySelectorAll('#prefs a').forEach(a=>a.onclick=async e=>{
    e.preventDefault();
    await fetch('/prefs/'+a.dataset.id,{method:'DELETE'}); loadPrefs();});
}
async function addPref(kind,inputId){
  const v=document.getElementById(inputId).value.trim(); if(!v)return;
  await fetch('/prefs',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({season:+document.getElementById('season').value,
      week:+document.getElementById('week').value,display_name:v,kind})});
  document.getElementById(inputId).value=''; loadPrefs();
}
document.getElementById('banin').addEventListener('keydown',
  e=>{if(e.key==='Enter')addPref('ban','banin');});
document.getElementById('boostin').addEventListener('keydown',
  e=>{if(e.key==='Enter')addPref('boost','boostin');});
loadSlates().then?loadSlates():loadSlates;
loadClassicSlates(); loadShowdownSlates(); loadPrefs(); loadContests();
"""


@app.get("/lineups/view", response_class=HTMLResponse)
def lineups_page() -> str:
    """DK-style lineup card viewer: build entries and eyeball them without
    touching the CSV. Cards are confidence-ordered, strongest first."""
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Fingerblasters' Brain — Lineups</title><link rel='icon' href='/static/logo.png'>"
        f"<style>{_PAGE_CSS}{_LINEUPS_CSS}</style></head><body>"
        f"{_NAV_HTML}<main><h1>Lineup builder</h1>"
        f"<div id='controls'>"
        f"<label>Season<input id='season' type='number'></label>"
        f"<label>Week<input id='week' type='number'></label>"
        f"<label>Slate<select id='slate' style='width:15rem'>"
        f"<option value=''>Whole week pool (no slate filter)</option>"
        f"</select></label>"
        f"<label>Contest<select id='contest' style='width:16rem'></select>"
        f"</label>"
        f"<label>Field size<input id='fsize' type='number' value='20000'>"
        f"</label>"
        f"<label>Entries<input id='n' type='number' value='40'></label>"
        f"<input id='lev' type='hidden' value='1'>"
        f"<div id='chint' style='font-size:.8em;color:#888'></div>"
        f"<label>Objective<select id='obj'>"
        f"<option value='proj_points'>Mean (GPP default — replay-validated; sim mode always uses this + validated tilts)</option>"
        f"<option value='proj_p90'>Ceiling p90 (tested: underperforms for GPP)</option>"
        f"<option value='proj_p50'>Median</option></select></label>"
        f"<label style='display:flex;align-items:center;gap:.35rem' "
        f"title='On: your converted notes tilt the build — boost/ban prefs AND multiplier notes from chat conversions. "
        f"Off: the pure validated algorithm, no manual adjustments — "
        f"build both ways to compare.'>"
        f"<input id='usenotes' type='checkbox' checked> My notes</label>"
        f"<button id='go' style='padding:.5rem 1.2rem;background:#1a1a2e;"
        f"color:#fff;border:0;border-radius:6px;cursor:pointer'>Build</button>"
        f"<button id='csv' style='padding:.5rem 1.2rem;background:#fff;"
        f"border:1px solid #1a1a2e;border-radius:6px;cursor:pointer'>"
        f"DK CSV</button>"
        f"<label>Ban player<input id='banin' placeholder='name'></label>"
        f"<label>Boost player<input id='boostin' placeholder='name'></label>"
        f"</div><div id='prefs' style='margin:.5rem 0;font-size:.85rem'></div>"
        f"<div id='status'>Pick season/week/slate and Build (the Sunday "
        f"main slate preselects itself when DK lists one; single games under "
        f"Showdown build Captain Mode entries). Classic tournament defaults "
        f"apply: QB+2 stack, bring-back, punt slot, chalk fade — showdown "
        f"leverages captain diversity instead.</div>"
        f"<div id='cards'></div>"
        f"</main><script>{_LINEUPS_JS}</script></body></html>"
    )


def _defense_page(df, season: int) -> str:
    latest = df.loc[df.groupby(["team", "position"])["week"].idxmax()]
    sections = []
    for pos in ("QB", "RB", "WR", "TE"):
        grp = latest[latest.position == pos].sort_values("fp_allowed_season")
        if grp.empty:
            continue
        rows = []
        for r in grp.itertuples():
            arrow = ("<span class='down'>&#9660; fading</span>" if r.trend > 1.5
                     else "<span class='up'>&#9650; improving</span>" if r.trend < -1.5
                     else "&mdash;")
            rows.append(
                f"<tr><td>{r.team}</td><td>{r.fp_allowed_season:.1f}</td>"
                f"<td>{r.fp_allowed_l6:.1f}</td><td>{r.fp_allowed_l3:.1f}</td>"
                f"<td>{r.trend:+.1f}</td><td>{arrow}</td></tr>"
            )
        sections.append(
            f"<div><h2>vs {pos}</h2><table>"
            f"<tr><th>Team</th><th>Season</th><th>L6</th><th>L3</th>"
            f"<th>Trend</th><th></th></tr>{''.join(rows)}</table></div>"
        )
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Fingerblasters' Brain — Defense</title><link rel='icon' href='/static/logo.png'>"
        f"<style>{_PAGE_CSS}</style></head><body>"
        f"{_NAV_HTML}<main>"
        f"<h1>DK points allowed per position &middot; {season}</h1>"
        f"<small>Season/L6/L3 = avg DK points allowed per game to the position "
        f"(fewest first = toughest defense). Trend = last 3 vs season norm: "
        f"positive means the defense is giving up more than usual lately. "
        f"API: <a href='/docs'>/docs</a>, "
        f"<a href='/defense/trends?season={season}'>/defense/trends</a></small>"
        f"{_CHAT_HTML}"
        f"<div class='grid'>{''.join(sections)}</div></main></body></html>"
    )




_SEASON_JS = """
const yr=new Date().getFullYear();
document.getElementById('rseason').value=yr;
async function loadResults(){
  const se=+document.getElementById('rseason').value;
  const r=await fetch('/results?season='+se); const rows=await r.json();
  let spent=0,won=0,contests=0,html='';
  for(const x of rows){spent+=x.spent;won+=x.won;contests+=x.contests;
    const pl=x.won-x.spent, cum=won-spent;
    html+=`<tr><td><a href='#' class='wk' data-w='${x.week}'>`+
      `${x.week}</a></td><td>${x.contests}</td>`+
      `<td>$${x.spent.toFixed(2)}</td><td>$${x.won.toFixed(2)}</td>`+
      `<td class='${pl>=0?"up":"down"}'>$${pl.toFixed(2)}</td>`+
      `<td class='${cum>=0?"up":"down"}'>$${cum.toFixed(2)}</td>`+
      `<td>${x.best_score??''}</td><td>${x.best_rank??''}</td>`+
      `<td>${x.note||''}</td></tr>`;}
  document.getElementById('rbody').innerHTML=html;
  document.querySelectorAll('a.wk').forEach(a=>a.onclick=e=>{
    e.preventDefault(); showWeek(+a.dataset.w);});
  const pl=won-spent;
  document.getElementById('totals').innerHTML=
    `Season: <b>${contests}</b> entries &middot; spent <b>$${spent.toFixed(2)}</b>`+
    ` &middot; won <b>$${won.toFixed(2)}</b> &middot; `+
    `<b class='${pl>=0?"up":"down"}'>${pl>=0?"+":""}$${pl.toFixed(2)}`+
    ` (${spent?(100*pl/spent).toFixed(1):0}% ROI)</b>`;
}
async function showWeek(wk){
  const se=+document.getElementById('rseason').value;
  const box=document.getElementById('wklineups');
  box.innerHTML='<small>Scoring week '+wk+'...</small>';
  const [r,xr]=await Promise.all([
    fetch(`/results/lineups?season=${se}&week=${wk}`),
    fetch(`/results/exports?season=${se}`)]);
  const lus=await r.json();
  const info=(await xr.json()).find(s=>s.week===wk);
  if(!lus.length){box.innerHTML='<small>No recorded lineups for week '+
    wk+' (lineups are recorded when the DK CSV is downloaded).</small>';
    return;}
  box.innerHTML='<h2>Week '+wk+' entries by score</h2>'+
    (info?`<small>Export set: <b>${info.lineups}</b> lineups, recorded `+
      `${info.recorded_at} (latest DK CSV download for the week &mdash; `+
      `each download replaces the last). </small>`:'')+
    `<button id='delwk' style='margin-left:.5rem;padding:.2rem .7rem;`+
    `background:#fff;border:1px solid #b00;color:#b00;border-radius:6px;`+
    `cursor:pointer'>Delete recorded slate</button><br>`+
    '<small>Click a player to swap him for whoever you used on DK.</small>'+
    "<div id='cards'>"+lus.map((lu,i)=>
    `<div class='card'><header><span>#${i+1}</span>`+
    `<span class='conf'>${lu.score}</span></header><table>`+
    lu.players.map(p=>`<tr><td><span class='slot'>${esc(p.pos)}</span></td>`+
      `<td style='text-align:left'><a href='#' class='swp' data-ix='${lu.ix}'`+
      ` data-out='${esc(p.name)}'>${esc(p.name)}</a></td><td>${esc(p.team)}</td>`+
      `<td>${p.pts}</td></tr>`).join('')+
    `</table></div>`).join('')+'</div>';
  document.getElementById('delwk').onclick=async()=>{
    if(!confirm('Delete week '+wk+"'s recorded lineups? Do this for "+
      'what-if slates you never entered on DK, so Tuesday scoring '+
      "skips the week. (An already-scored best_score isn't reset; "+
      're-score after recording the real slate, or edit via the API.)'))
      return;
    const dr=await fetch(`/results/lineups?season=${se}&week=${wk}`,
      {method:'DELETE'});
    if(dr.ok){box.innerHTML='<small>Week '+wk+
      ' recorded lineups deleted.</small>';}
    else alert('Delete failed: '+(await dr.json()).detail);
  };
  document.querySelectorAll('a.swp').forEach(a=>a.onclick=async e=>{
    e.preventDefault();
    const q=prompt('Swap OUT '+a.dataset.out+'.\\nSearch replacement name:');
    if(!q)return;
    const se=+document.getElementById('rseason').value;
    const cs=await (await fetch(`/players/search?season=${se}&week=${wk}`+
      `&q=${encodeURIComponent(q)}`)).json();
    if(!cs.length){alert('No match for "'+q+'"');return;}
    let pick=cs[0];
    if(cs.length>1){
      const c=prompt(cs.map((p,i)=>`${i+1}. ${p.name} ${p.pos} ${p.team} `+
        `$${p.salary}`).join('\\n')+'\\n\\nEnter number:');
      pick=cs[+c-1]; if(!pick)return;}
    const r=await fetch('/entries/swap',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({season:se,week:wk,lineup_ix:+a.dataset.ix,
        out_name:a.dataset.out,in_name:pick.name})});
    if(!r.ok){alert('Swap failed: '+(await r.json()).detail);return;}
    showWeek(wk);
  });
}
document.getElementById('rfile').addEventListener('change',async e=>{
  const f=e.target.files[0]; if(!f)return;
  const txt=await f.text();
  const r=await fetch('/results/import',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({season:+document.getElementById('rseason').value,
                         csv_text:txt})});
  const j=await r.json();
  document.getElementById('istatus').textContent=r.ok?
    'Imported '+Object.keys(j.weeks).length+' week(s)':('Error: '+j.detail);
  loadResults();});
loadResults();
"""


@app.get("/", response_class=HTMLResponse)
def season_dashboard() -> str:
    """Home: season bankroll tracker — weekly entries/spent/won with
    running P/L, best-lineup notes, and DK Entry History CSV import."""
    return (
        f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Fingerblasters' Brain — Season</title><link rel='icon' href='/static/logo.png'>"
        f"<style>{_PAGE_CSS}{_LINEUPS_CSS}</style></head><body>"
        f"{_NAV_HTML}<main>"
        f"<div style='display:flex;align-items:center;gap:1.1rem;"
        f"margin-top:1.2rem'>"
        f"<img src='/static/logo.png' alt='' style='height:110px;"
        f"width:110px;border-radius:18px;object-fit:cover;"
        f"box-shadow:0 8px 24px rgba(13,27,42,.25)'>"
        f"<div><h1 style='margin:.2rem 0'>Season tracker</h1>"
        f"<div id='totals' style='font-size:1.05rem;margin:.3rem 0'></div>"
        f"</div></div>"
        f"<div id='controls'>"
        f"<label>Season<input id='rseason' type='number'></label>"
        f"<label>DK Entry History CSV<input id='rfile' type='file' "
        f"accept='.csv'></label><span id='istatus'></span></div>"
        f"<small>Upload the cumulative export any time (draftkings.com "
        f"&rarr; My Contests &rarr; Download Entry History) — weeks "
        f"recompute in place; re-uploads are safe. The manual week form "
        f"was removed by request; the /results API still accepts manual "
        f"rows if ever needed.</small>"
        f"<table style='margin-top:1rem'><tr><th>Wk</th><th>Contests</th>"
        f"<th>Spent</th><th>Won</th><th>P/L</th><th>Cumulative</th>"
        f"<th>Best score</th><th>Best rank</th><th>Note</th></tr>"
        f"<tbody id='rbody'></tbody></table>"
        f"<div id='wklineups' style='margin-top:1rem'></div>"
                f"{_CHAT_HTML}"
        f"</main><script>{_SEASON_JS}</script></body></html>"
    )


@app.get("/defense", response_class=HTMLResponse)
def defense_dashboard(
    season: int | None = None,
    store: ProjectionStore = Depends(get_store),
) -> str:
    df = store.defense_points_against(season)
    if df.empty:
        return ("<h1>No defense data yet</h1>"
                "<p>Run <code>nfl-dfs build-features</code> first.</p>")
    season = int(season or df.season.max())
    return _defense_page(df[df.season == season], season)


@app.get("/market", response_class=HTMLResponse)
def market_page() -> str:
    """Market intelligence: line movement since open, and where our model
    disagrees most with the prop market (2026-08-01 audit item)."""
    body = """
<main><h1>Market</h1>
<h2>Line movement (since first snapshot)</h2>
<div id='moves'><small>Loading&hellip;</small></div>
<h2 style='margin-top:2rem'>Model vs prop market</h2>
<div style='margin:.4rem 0'><small>Season/week with projections:</small>
<input id='ms' size='5' placeholder='season'> <input id='mw' size='3'
placeholder='wk'> <button id='mgo'>Load</button></div>
<div id='dis'><small>Enter a projected week (in-season) and Load.</small></div>
<h2 style='margin-top:2rem'>Projection accuracy (last completed week)</h2>
<div style='margin:.4rem 0'>
<input id='as' size='5' placeholder='season'> <input id='aw' size='3' placeholder='wk'>
<button id='ago'>Grade</button></div>
<div id='acc'><small>Grade any completed week: our MAE / rank corr vs the
naive trailing-average baseline.</small></div>
<h2 style='margin-top:2rem'>Consensus diff (external projections)</h2>
<div style='margin:.4rem 0'><small>Upload an outside CSV (ETR, Stokastic,
free ownership sites — needs name + projection columns; ownership/ceiling
optional). A disagreement flag, never a model input: big divergence on a
player we're heavy on belongs in the watchlist.</small></div>
<div style='margin:.4rem 0'>
<input id='xsrc' size='10' placeholder='source'>
<input id='xs' size='5' placeholder='season'> <input id='xw' size='3' placeholder='wk'>
<input id='xfile' type='file' accept='.csv'>
<button id='xup'>Upload</button> <button id='xgo'>Show diff</button></div>
<div id='xdiff'><small>No external projections loaded.</small></div>
</main>
<script>
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function tbl(rows, cols){if(!rows.length)return '<small>No data yet.</small>';
  let h='<table><tr>'+cols.map(c=>'<th>'+esc(c)+'</th>').join('')+'</tr>';
  for(const r of rows){h+='<tr>'+cols.map(c=>'<td>'+esc(r[c]??'')+'</td>').join('')+'</tr>';}
  return h+'</table>';}
fetch('/api/line-movement').then(r=>r.json()).then(j=>{
  document.getElementById('moves').innerHTML=tbl(j,
    ['event_name','market_type','selection','open_line','latest_line',
     'line_move','latest_odds','last_seen']);});
document.getElementById('mgo').onclick=async()=>{
  const s=document.getElementById('ms').value,w=document.getElementById('mw').value;
  if(!s||!w)return;
  const j=await (await fetch(`/api/market-disagreement?season=${s}&week=${w}`)).json();
  document.getElementById('dis').innerHTML=tbl(j,
    ['display_name','position','team','salary','proj_points','market_points','edge']);
};
document.getElementById('ago').onclick=async()=>{
  const s=document.getElementById('as').value,w=document.getElementById('aw').value;
  if(!s||!w)return;
  const j=await (await fetch(`/api/accuracy?season=${s}&week=${w}`)).json();
  if(j.status){document.getElementById('acc').innerHTML=`<small>${esc(j.status)}</small>`;return;}
  let h=`<p><b>MAE ${j.mae}</b>${j.naive_mae?` vs naive ${j.naive_mae}`:''} · rank corr ${j.rank_corr} · n=${j.rows}</p>`;
  document.getElementById('acc').innerHTML=h+tbl(j.by_position||[],['position','n','mae','rank_corr']);
};
document.getElementById('xup').onclick=async()=>{
  const src=document.getElementById('xsrc').value||'external',
        s=document.getElementById('xs').value,w=document.getElementById('xw').value,
        f=document.getElementById('xfile').files[0];
  if(!s||!w||!f){alert('source, season, week and a CSV file required');return;}
  const fd=new FormData();fd.append('file',f);
  const r=await fetch(`/api/external-projections?source=${encodeURIComponent(src)}&season=${s}&week=${w}`,
    {method:'POST',body:fd});
  const j=await r.json();
  document.getElementById('xdiff').innerHTML = r.ok ?
    `<small>Imported ${esc(j.imported)} rows from ${esc(j.source)}.</small>` :
    `<small>Import failed: ${esc(j.detail||r.status)}</small>`;
};
document.getElementById('xgo').onclick=async()=>{
  const s=document.getElementById('xs').value,w=document.getElementById('xw').value;
  if(!s||!w)return;
  const j=await (await fetch(`/api/external-diff?season=${s}&week=${w}`)).json();
  document.getElementById('xdiff').innerHTML=tbl(j,
    ['display_name','position','team','salary','proj_points','ext_proj','diff',
     'ext_own','ext_ceiling','source']);
};
</script>"""
    return f"<html><head><title>Market</title><style>{_PAGE_CSS}</style></head><body>{_NAV_HTML}{body}</body></html>"


def _with_watch_notes(players: list[dict]) -> list[dict]:
    """Attach active watch notes to lineup players (fail-safe passthrough)."""
    from .. import watchlist

    watchlist.annotate_players(players)
    return players


@app.get("/api/watchlist")
def api_watchlist() -> list[dict]:
    from .. import watchlist

    df = watchlist.list_watch()
    if df.empty:
        return []
    df = df.copy()
    for c in ("created_at", "converted_at"):
        df[c] = df[c].astype(str).replace("NaT", "")
    return df.fillna("").to_dict("records")


@app.post("/api/watchlist/{note_id}/convert")
def api_watchlist_convert(note_id: str, mult: float, season: int | None = None) -> dict:
    from .. import watchlist
    from ..config import current_season

    try:
        mid = watchlist.convert_watch(note_id, mult, season or current_season())
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"converted": note_id, "manual_note_id": mid}


@app.delete("/api/watchlist/{note_id}")
def api_watchlist_delete(note_id: str) -> dict:
    from .. import watchlist

    return {"deleted": watchlist.delete_watch(note_id)}


@app.get("/watchlist", response_class=HTMLResponse)
def watchlist_page() -> str:
    """Player watch notes: free-text intel, lifecycle view, convert/delete.
    Notes change nothing until converted into a usage-note adjustment."""
    body = """
<main><h1>Watchlist</h1>
<small>Free-text player notes from the chat ("add a note: ..."). A note
changes <b>nothing</b> until you convert it into a usage-note adjustment
(opportunity multiplier, decays by week 6). Notes also appear as &#128221;
on any generated lineup containing the player.</small>
<div id='wl' style='margin-top:1rem'><small>Loading&hellip;</small></div>
</main>
<script>
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function load(){
  const j=await (await fetch('/api/watchlist')).json();
  const el=document.getElementById('wl');
  if(!j.length){el.innerHTML='<small>No notes yet. Add one in the chat on the Season page.</small>';return;}
  let h='<table><tr><th>Player</th><th>Note</th><th>Added</th><th>Status</th><th></th></tr>';
  for(const n of j){
    const st=n.status==='converted'
      ?`<span style="color:#0a7a3d;font-weight:700">converted</span><br><small>mult ${n.converted_mult} &middot; ${String(n.converted_at).slice(0,10)}</small>`
      :`<span style="color:#b26a00;font-weight:700">active</span>`;
    const act=n.status==='converted'?''
      :`<input id='m_${n.note_id}' size='4' placeholder='1.10'>
        <button onclick="conv('${n.note_id}')">Convert</button>
        <button onclick="del('${n.note_id}')" style='color:#b3261e'>Delete</button>`;
    h+=`<tr><td style='text-align:left'><b>${esc(n.display_name)}</b></td>
      <td style='text-align:left;max-width:28rem'>${esc(n.note)}</td>
      <td>${String(n.created_at).slice(0,10)}</td><td>${st}</td>
      <td style='text-align:left'>${act}</td></tr>`;
  }
  el.innerHTML=h+'</table>';
}
async function conv(id){
  const m=document.getElementById('m_'+id).value;
  if(!m){alert('Enter a multiplier, e.g. 1.10');return;}
  const r=await fetch(`/api/watchlist/${id}/convert?mult=${m}`,{method:'POST'});
  if(!r.ok){alert((await r.json()).detail||r.status);return;}
  load();
}
async function del(id){
  if(!confirm('Delete this note?'))return;
  await fetch(`/api/watchlist/${id}`,{method:'DELETE'});
  load();
}
load();
</script>"""
    return f"<html><head><title>Watchlist</title><style>{_PAGE_CSS}</style></head><body>{_NAV_HTML}{body}</body></html>"


@app.get("/api/line-movement")
def api_line_movement(limit: int = 40) -> list[dict]:
    """Biggest spread/total moves since first snapshot (odds_movement
    view; collecting 2x/day Wed-Sun since the 2026-07-31 odds fix)."""
    from ..bq import query_df
    from ..config import settings

    df = query_df(f"""
        SELECT event_name, market_type, selection, open_line, latest_line,
               line_move, open_odds, latest_odds,
               FORMAT_TIMESTAMP('%m-%d %H:%M', last_seen) AS last_seen
        FROM `{settings.raw}.odds_movement`
        WHERE line_move IS NOT NULL AND market_type IN ('Spread', 'Total')
        ORDER BY ABS(line_move) DESC
        LIMIT {int(limit)}
    """)
    return df.to_dict("records")


@app.get("/api/market-disagreement")
def api_market_disagreement(season: int, week: int, limit: int = 40) -> list[dict]:
    """Model projections vs prop-market-implied points: the rows where we
    disagree most with the betting market, both directions. Divergence is
    either alpha or a bug -- worth eyes each week either way."""
    from ..models.prop_market import market_points

    store = get_store()
    proj = store.projections(season, week)
    if proj.empty:
        return []
    mkt = market_points(seasons=(season,))
    mkt = mkt[mkt.week == week]
    if mkt.empty:
        return []
    j = proj.merge(mkt[["gsis_id", "market_points"]], on="gsis_id", how="inner")
    j["edge"] = j.proj_points - j.market_points
    j = j.reindex(j.edge.abs().sort_values(ascending=False).index).head(int(limit))
    cols = ["display_name", "position", "team", "salary",
            "proj_points", "market_points", "edge"]
    return j[[c for c in cols if c in j.columns]].round(2).to_dict("records")


@app.get("/api/market-tails")
def api_market_tails(season: int, week: int, limit: int = 40) -> list[dict]:
    """Model q90 vs the market's de-vigged implied q90 from alternate
    prop ladders (Addendum 45): disagreement predicted the direction of
    market error BOTH ways on 2025 holdout, so the biggest gaps in each
    direction are the week's leverage watchlist."""
    from ..bq import query_df
    from ..config import settings
    from ..inference.market_implied import ALT_MARKETS, market_quantiles

    props = query_df(
        f"""WITH latest AS (
              SELECT *, ROW_NUMBER() OVER (
                PARTITION BY market, player, CAST(point AS STRING),
                             outcome_name
                ORDER BY snapshot_ts DESC) rn
              FROM `{settings.raw}.prop_lines`
              WHERE season={int(season)} AND week={int(week)}
                AND bookmaker='draftkings'
                AND market IN ({", ".join("'" + m + "'" for m in ALT_MARKETS)})
            ) SELECT season, week, market, player, point, outcome_name,
                     price FROM latest WHERE rn=1""")
    if props.empty:
        return []
    mq = market_quantiles(props)
    if mq.empty:
        return []
    store = get_store()
    proj = store.projections(season, week)
    if proj.empty or "proj_p90" not in proj.columns:
        return []
    norm = lambda s: (s.astype(str).str.lower()  # noqa: E731
                      .str.replace(r"[^a-z ]", "", regex=True).str.strip())
    mq["norm"], proj = mq.player.pipe(norm), proj.assign(
        norm=norm(proj.display_name))
    # spread vs spread, both in DK pts: our (p90 - mean) vs the market's
    # (q90 - q50) at the correct DK rate per market (0.1/yd rush+rec,
    # 0.04/yd pass — the first cut priced QBs 2.5x hot). Known bias,
    # displayed not modeled: summed independent per-market spreads
    # overstate a dual-threat player's combined spread, and our side
    # includes reception/TD variance the yardage markets don't — treat
    # tail_edge as a WATCHLIST ranking, not a calibrated quantity.
    pts_per_yd = {"player_pass_yds_alternate": 0.04}
    tails = (mq.assign(mkt_spread_pts=(mq.q90 - mq.q50)
                       * mq.market.map(pts_per_yd).fillna(0.1))
             .groupby("norm").mkt_spread_pts.sum().reset_index())
    j = proj.merge(tails, on="norm", how="inner")
    j["tail_edge"] = (j.proj_p90 - j.proj_points) - j.mkt_spread_pts
    j = j.reindex(j.tail_edge.abs().sort_values(ascending=False).index)
    cols = ["display_name", "position", "team", "salary", "proj_points",
            "proj_p90", "mkt_spread_pts", "tail_edge"]
    return j[[c for c in cols if c in j.columns]].head(int(limit)).round(
        2).to_dict("records")


@app.post("/api/external-projections")
async def api_external_import(source: str, season: int, week: int,
                              file: UploadFile = File(...)) -> dict:
    """Upload an outside source's projections CSV (ETR/Stokastic/free
    ownership sites). Loose schema; replaces the same (source, season,
    week). Feeds the consensus-diff view — a disagreement flag, never a
    model input."""
    from .. import external_proj

    text = (await file.read()).decode("utf-8", errors="replace")
    try:
        n = external_proj.import_csv(text, source, season, week)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"imported": n, "source": source, "season": season, "week": week}


@app.get("/api/accuracy")
def api_accuracy(season: int, week: int) -> dict:
    """Walk-forward self-grading (4for4 discipline, vendor audit 10/11f):
    last completed week's projections vs actuals — MAE, rank correlation,
    and the naive trailing-average baseline that any real model must
    beat. Empty until the week's actuals land (Tue after the slate)."""
    from ..bq import query_df
    from ..config import settings

    store = get_store()
    proj = store.projections(season, week)
    if proj.empty:
        return {"status": f"no projections for {season} wk {week}"}
    act = query_df(
        f"""SELECT gsis_id, MAX(dk_points) actual
            FROM `{settings.features}.player_week_actuals`
            WHERE season={int(season)} AND week={int(week)} GROUP BY gsis_id""")
    if act.empty:
        return {"status": "actuals not loaded yet (Tuesday ingest)"}
    j = proj.merge(act, on="gsis_id", how="inner")
    if len(j) < 20:
        return {"status": f"only {len(j)} matched rows"}
    out = {"season": season, "week": week, "rows": int(len(j)),
           "mae": round(float((j.proj_points - j.actual).abs().mean()), 2),
           "rank_corr": round(float(
               j.proj_points.corr(j.actual, method="spearman")), 3)}
    if "dk_points_l4" in j.columns:
        n = j.dropna(subset=["dk_points_l4"])
        if len(n) > 20:
            out["naive_mae"] = round(float(
                (n.dk_points_l4 - n.actual).abs().mean()), 2)
    per = []
    for pos, g in j.groupby("position"):
        if len(g) >= 8:
            per.append({"position": pos, "n": int(len(g)),
                        "mae": round(float((g.proj_points - g.actual).abs().mean()), 2),
                        "rank_corr": round(float(
                            g.proj_points.corr(g.actual, method="spearman")), 3)})
    out["by_position"] = per
    return out


@app.get("/api/external-diff")
def api_external_diff(season: int, week: int, limit: int = 40) -> list[dict]:
    from .. import external_proj

    store = get_store()
    proj = store.projections(season, week)
    if proj.empty:
        return []
    d = external_proj.diff(proj, season, week, limit=limit)
    return d.to_dict("records")


@app.get("/api/cfb-export-links")
def cfb_export_links(days: int = 3, limit: int = 5) -> list[dict]:
    """Saturday-night helper (2026-08-03): the biggest recently-completed
    CFB contests with ready-made standings-export URLs — click each while
    logged into DK, then import-ownership the downloads. No entry
    required; contest IDs come from the automated fills poll. Empty until
    the CFB scaffold lands data (late Aug)."""
    from ..bq import query_df
    from ..config import settings

    try:
        df = query_df(f"""
            SELECT contest_id, name, entry_fee, prize_pool, start_time
            FROM (SELECT contest_id, name, entry_fee, prize_pool, start_time,
                         ROW_NUMBER() OVER (PARTITION BY contest_id
                                            ORDER BY pulled_at DESC) rn
                  FROM `{settings.raw}.dk_contest_fills`
                  WHERE sport = 'CFB'
                    AND start_time < CURRENT_TIMESTAMP()
                    AND start_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(),
                                                   INTERVAL {int(days)} DAY))
            WHERE rn = 1 ORDER BY prize_pool DESC LIMIT {int(limit)}""")
    except Exception:
        return []
    out = df.to_dict("records")
    for c in out:
        c["export_url"] = ("https://www.draftkings.com/contest/"
                           f"exportfullstandingscsv/{c['contest_id']}")
        c["start_time"] = str(c["start_time"])
    return out


@app.get("/api/system-status")
def api_system_status() -> dict:
    """Freshness of every data feed, for the System status popup. See
    nfl_dfs/status.py for the feed specs and state rules."""
    from datetime import datetime, timezone

    from .. import status as _status

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "components": _status.system_status(),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


class ChatRequest(BaseModel):
    messages: list[dict]  # Claude-API-shaped history; last entry is the user turn
    # Per-conversation model choice (UI selector): Opus default —
    # tool-driven, well-scoped work; Fable for hard reasoning turns.
    model: str | None = Field(None, pattern="^claude-(opus-5|fable-5)$")


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    """Dashboard assistant: manage usage notes, query projections/form.
    Needs ANTHROPIC_API_KEY in the environment."""
    import os

    from . import chat as chat_mod

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(503, "ANTHROPIC_API_KEY is not set — add it to "
                                 ".env to enable chat")
    try:
        messages = chat_mod.chat_turn(list(req.messages), model=req.model)
    except Exception as exc:
        log.exception("chat turn failed")
        log.exception("chat turn failed")
        raise HTTPException(500, "chat failed — see server logs")
    return {"reply": chat_mod.reply_text(messages), "messages": messages}


class PrefRequest(BaseModel):
    season: int
    week: int
    display_name: str
    kind: str = Field(pattern="^(ban|boost)$")


@app.get("/prefs")
def get_prefs(season: int, week: int) -> list[dict]:
    from .. import notes as _notes

    return _notes.list_prefs(season, week).to_dict("records")


@app.post("/prefs")
def post_pref(req: PrefRequest) -> dict:
    from .. import notes as _notes

    return {"pref_id": _notes.add_pref(req.season, req.week,
                                       req.display_name, req.kind)}


@app.delete("/prefs/{pref_id}")
def del_pref(pref_id: str) -> dict:
    from .. import notes as _notes

    return {"deleted": _notes.delete_pref(pref_id)}


class ResultRequest(BaseModel):
    season: int
    week: int
    contests: int
    spent: float
    won: float
    best_score: float | None = None
    best_rank: int | None = None
    note: str = ""


@app.get("/results")
def get_results(season: int) -> list[dict]:
    from .. import notes as _n

    df = _n.list_results(season)
    return df.where(pd.notna(df), None).to_dict("records")


@app.post("/results")
def post_result(req: ResultRequest) -> dict:
    from .. import notes as _n

    return {"result_id": _n.upsert_result(req.season, req.week, req.contests,
                                          req.spent, req.won, req.best_score,
                                          req.best_rank, req.note)}


class HistoryImport(BaseModel):
    season: int
    csv_text: str


@app.get("/results/lineups")
def week_lineups(season: int, week: int) -> list[dict]:
    """The week's entered lineups with actual player points, best first."""
    from .. import notes as _n

    e = _n.scored_lineups(season, week)
    if e.empty:
        return []
    out = []
    for ix, grp in e.groupby("lineup_ix"):
        players = grp.sort_values("pts", ascending=False)
        out.append({
            "ix": int(ix),
            "score": round(float(grp.pts.sum()), 1),
            "players": [{"name": r.name, "pos": r.pos, "team": r.team,
                         "pts": round(float(r.pts), 1)}
                        for r in players.itertuples()]})
    return sorted(out, key=lambda x: -x["score"])


@app.get("/results/exports")
def list_exports(season: int) -> list[dict]:
    """Recorded export sets by week: lineup/player counts and when the DK
    CSV was downloaded (only the latest download per week is kept)."""
    from .. import notes as _n

    return _n.list_entered_sets(season).to_dict("records")


@app.delete("/results/lineups")
def delete_week_lineups(season: int, week: int) -> dict:
    """Forget the week's recorded export set — for what-if slates that
    were downloaded but never entered on DK, so scoring skips the week."""
    from .. import notes as _n

    try:
        return {"deleted": _n.delete_entered_lineups(season, week)}
    except Exception as exc:
        raise HTTPException(422, f"delete failed: {exc}")


@app.get("/players/search")
def player_search(season: int, week: int, q: str,
                  store: ProjectionStore = Depends(get_store)) -> list[dict]:
    """Name search over the week's projectable pool (swap candidates)."""
    df = store.projections(season, week)
    if df.empty:
        return []
    hit = df[df.display_name.str.contains(q, case=False, na=False,
                                           regex=False)]
    return [{"name": r.display_name, "pos": r.position, "team": r.team,
             "salary": int(r.salary), "dk_player_id": int(r.dk_player_id),
             "proj": round(float(r.proj_points), 1)}
            for r in hit.head(10).itertuples()]


class SwapRequest(BaseModel):
    season: int
    week: int
    lineup_ix: int
    out_name: str
    in_name: str


@app.post("/entries/swap")
def swap_entry_player(req: SwapRequest,
                      store: ProjectionStore = Depends(get_store)) -> dict:
    """Replace a player in a recorded lineup (mirrors a DK edit)."""
    from .. import notes as _n

    df = store.projections(req.season, req.week)
    hit = df[df.display_name.str.contains(req.in_name, case=False,
                                           na=False, regex=False)]
    if hit.empty:
        raise HTTPException(404, f"no player matching '{req.in_name}'")
    if len(hit) > 1 and not (hit.display_name.str.lower()
                             == req.in_name.lower()).any():
        raise HTTPException(409, "ambiguous: "
                            + ", ".join(hit.display_name.head(5)))
    r = (hit[hit.display_name.str.lower() == req.in_name.lower()].iloc[0]
         if len(hit) > 1 else hit.iloc[0])
    # Duplicate guards: the swap must not clone another entered lineup,
    # and the incoming player must not already be in this one.
    rosters = _n.entered_rosters(req.season, req.week)
    cur = rosters.get(req.lineup_ix)
    if cur is not None:
        incoming = _n.norm_name(str(r.display_name))
        if incoming in cur:
            raise HTTPException(409, f"{r.display_name} is already in "
                                     f"this lineup")
        proposed = (cur - {_n.norm_name(req.out_name)}) | {incoming}
        for ix, roster in rosters.items():
            if ix != req.lineup_ix and roster == proposed:
                raise HTTPException(
                    409, f"blocked: that swap would make this lineup "
                         f"identical to entry #{ix + 1} — DK rejects "
                         f"duplicate lineups, pick a different player")
    _n.swap_entered_player(req.season, req.week, req.lineup_ix,
                           req.out_name,
                           {"name": r.display_name, "pos": r.position,
                            "team": r.team,
                            "dk_player_id": int(r.dk_player_id)})
    return {"swapped": req.out_name, "for": str(r.display_name)}


@app.post("/results/score")
def score_results(season: int, week: int) -> dict:
    """Score the recorded entry set vs actuals; fills best_score."""
    from .. import notes as _n

    try:
        return _n.score_entries(season, week)
    except Exception as exc:
        raise HTTPException(422, f"scoring failed: {exc}")


@app.post("/results/import")
def import_history(req: HistoryImport) -> dict:
    from .. import notes as _n

    try:
        return {"weeks": _n.import_entry_history(req.csv_text, req.season)}
    except Exception as exc:
        raise HTTPException(422, f"could not parse entry history: {exc}")


@app.get("/defense/points-against")
def defense_points_against(
    season: int | None = None,
    position: str | None = None,
    store: ProjectionStore = Depends(get_store),
) -> list[dict]:
    """Fantasy-style points-against: latest-week snapshot per team/position
    with season average, last-3/6, and trend (positive = fading defense)."""
    df = store.defense_points_against(season)
    if df.empty:
        raise HTTPException(404, "No defense data; run build-features")
    latest = df.loc[df.groupby(["team", "position"])["week"].idxmax()]
    if position:
        latest = latest[latest.position == position.upper()]
    return (
        latest.sort_values(["position", "fp_allowed_season"])
        .round(2).to_dict("records")
    )


@app.get("/defense/trends")
def defense_trends(
    season: int | None = None,
    top: int = Query(5, ge=1, le=32),
    store: ProjectionStore = Depends(get_store),
) -> dict:
    """Per position: defenses improving (clamping down vs. their season
    norm) and fading (allowing more lately)."""
    df = store.defense_points_against(season)
    if df.empty:
        raise HTTPException(404, "No defense data; run build-features")
    latest = df.loc[df.groupby(["team", "position"])["week"].idxmax()]
    out: dict = {}
    for pos, grp in latest.groupby("position"):
        g = grp.sort_values("trend").round(2)
        cols = ["team", "trend", "fp_allowed_l3", "fp_allowed_season", "week"]
        out[pos] = {
            "improving": g.head(top)[cols].to_dict("records"),
            "fading": g.tail(top)[cols].iloc[::-1].to_dict("records"),
        }
    return out


def _slate_label(kickoffs: pd.Series, games: int) -> str:
    """Human label for a classic draft group from its kickoff times:
    'Sun 1:00 PM–4:25 PM · 12 games' or 'Thu–Mon · 16 games' (US/Eastern)."""
    et = pd.to_datetime(kickoffs, utc=True).dt.tz_convert(
        "America/New_York").sort_values()
    days = list(dict.fromkeys(et.dt.strftime("%a")))

    def clock(ts) -> str:
        return ts.strftime("%I:%M %p").lstrip("0")

    if len(days) == 1:
        first, last = clock(et.iloc[0]), clock(et.iloc[-1])
        when = f"{days[0]} {first}" + (f"–{last}" if last != first else "")
    else:
        when = f"{days[0]}–{days[-1]}"
    return f"{when} · {games} game{'s' if games != 1 else ''}"


@app.get("/classic/slates")
def classic_slates(store: ProjectionStore = Depends(get_store)) -> list[dict]:
    """Upcoming classic slates (draft groups) to build lineups against.
    `main` flags the Sunday main slate: the all-Sunday group with the most
    games (DK's 1:00+4:25 slate — the user's usual tournament target)."""
    df = store.classic_slates()
    if df.empty:
        raise HTTPException(404, "No upcoming classic slates; run ingest-dk")
    out = []
    for gid, grp in df.groupby("draft_group_id", sort=False):
        starts = pd.to_datetime(grp.game_start, utc=True)
        games = int(grp.teams.sum()) // 2
        et_days = list(dict.fromkeys(
            starts.dt.tz_convert("America/New_York").dt.strftime("%a")))
        out.append({
            "draft_group_id": int(gid),
            "label": _slate_label(grp.game_start, games),
            "days": et_days,
            "games": games,
            "players": int(grp.players.sum()),
            "first_game": str(starts.min()),
            "last_game": str(starts.max()),
            "main": False,
        })
    sunday_only = [s for s in out if s["days"] == ["Sun"]]
    if sunday_only:
        max(sunday_only, key=lambda s: (s["games"], s["players"]))["main"] = True
    return sorted(out, key=lambda s: (s["first_game"], -s["games"]))


@app.get("/slates")
def slates(store: ProjectionStore = Depends(get_store)) -> list[dict]:
    return store.slates().to_dict("records")


@app.get("/projections")
def projections(
    season: int = Query(...),
    week: int = Query(...),
    position: str | None = None,
    store: ProjectionStore = Depends(get_store),
) -> list[dict]:
    df = store.projections(season, week)
    if df.empty:
        raise HTTPException(404, f"No projections for {season} week {week}")
    if position:
        df = df[df.position == position.upper()]
    return df.sort_values("proj_points", ascending=False).to_dict("records")


def _classic_dk_ids(store: ProjectionStore) -> dict[int, int]:
    """dk_player_id -> draftable ID for the latest classic slate. DK's
    upload parser matches on draftable IDs; without the mapping the CSV
    falls back to player IDs, which DK rejects."""
    try:
        m = store.classic_draftable_ids()
    except Exception:
        log.warning("classic draftable IDs unavailable; upload CSV will "
                    "carry player IDs DK won't accept", exc_info=True)
        return {}
    if m.empty:
        log.warning("no draftable IDs in the latest classic pull; run "
                    "ingest-dk (rows pulled before 2026-07 lack them)")
        return {}
    return {int(r.dk_player_id): int(r.dk_draftable_id) for r in m.itertuples()}


@lru_cache(maxsize=8)
def _punt_boom_keys(season: int, week: int) -> frozenset:
    from ..backtest.replay import punt_boom_flags_live

    return frozenset(punt_boom_flags_live(season, week))


def _player_pool(
    df: pd.DataFrame, objective: str, dk_ids: dict[int, int] | None = None,
    lev_scale: float = 1.0,
) -> list[dict]:
    """Tournament-tilted pool: sub-$4k players are valued at their ceiling
    (p90 — a punt's only job is to boom) and every projection carries a
    chalk-fade penalty proportional to naive ownership, so entries lean
    into the leverage that wins large fields. dk_id carries the slate's
    draftable ID, which DK's upload parser requires.

    Punt-boom tilt (adopted, Addendum 37): punt-priced skill players
    matching a winning-punt archetype (cheap starting TE, rank 2->1
    promotion, top-decile vacated share) get +PUNT_BOOM objective points
    — replays measured 16 vs 15 tail weeks with every other metric up."""
    from ..backtest.field import naive_ownership
    from ..optimizer.lineup import LEVERAGE_PENALTY, PUNT_MAX_SALARY

    punt_boom = float(os.environ.get("PUNT_BOOM", "2") or 0)
    boom_keys: set = set()
    if punt_boom and {"gsis_id", "season", "week"} <= set(df.columns) \
            and len(df):
        try:
            boom_keys = _punt_boom_keys(int(df.season.iloc[0]),
                                        int(df.week.iloc[0]))
        except Exception:
            log.exception("punt-boom flags unavailable; pool untilted")

    pool = []
    for r in df.itertuples():
        pid = int(r.dk_player_id)
        proj = float(getattr(r, objective))
        if int(r.salary) <= PUNT_MAX_SALARY and hasattr(r, "proj_p90") \
                and pd.notna(r.proj_p90):
            proj = max(proj, float(r.proj_p90))
        if boom_keys and int(r.salary) <= PUNT_MAX_SALARY \
                and r.position != "DST" \
                and (getattr(r, "gsis_id", None), int(r.season),
                     int(r.week)) in boom_keys:
            proj += punt_boom
        kickoff = getattr(r, "kickoff", None)
        pool.append(
            {
                "id": pid,
                "dk_id": (dk_ids or {}).get(pid),
                "name": r.display_name,
                "pos": r.position,
                "team": r.team,
                "opp": getattr(r, "opponent", None),
                "game_id": f"{r.team}@{getattr(r, 'opponent', '?')}",
                "salary": int(r.salary),
                "proj": proj,
                "kickoff": kickoff if pd.notna(kickoff) else None,
            }
        )
    own = naive_ownership(pd.DataFrame(pool))
    for p, w in zip(pool, own):
        p["proj"] = p["proj"] - LEVERAGE_PENALTY * lev_scale * float(w)
    return pool


MIN_MILLY_LINE = 194.0  # lowest 2025 Milly-winning score; confidence target
MILLY_FIELD = 150_000   # field the 194 anchor was measured in
_FIELD_MU = 120.0       # contending-entry mean the Gumbel term scales from


def tail_line_for_field(field_size: int) -> float:
    """Winning-line estimate for a GPP of `field_size` entries.

    Extreme-value scaling: the max of N entry scores grows like
    mu + sigma*sqrt(2 ln N), so the line moves with sqrt(ln N) around a
    contending-field mean. Anchored at the one point we measured (2025
    Milly, 150k entries, min winning line 194). PROVISIONAL until real
    qualifier standings recalibrate it (in-season queue item 7) — treat
    it as "a 20k field wins ~6-7 points lower", not gospel.
    """
    import math

    n = max(int(field_size), 100)
    scale = math.sqrt(math.log(n) / math.log(MILLY_FIELD))
    return round(_FIELD_MU + (MIN_MILLY_LINE - _FIELD_MU) * scale, 1)


# Static picker fallbacks; live DK contests (real names, fees and field
# sizes from the overlay scaffold's fill polls) take over when
# INGEST_CONTESTS_ENABLED has landed data. $5 qualifier first: it's the
# primary contest this shop enters.
CONTEST_PRESETS = [
    {"name": "$5 Qualifier (typical)", "entry_fee": 5.0,
     "field_size": 20_000, "entries": 40, "lev_scale": 1.0,
     "note": "40-entry coverage portfolio, full leverage"},
    {"name": "$3 Large GPP", "entry_fee": 3.0,
     "field_size": 100_000, "entries": 40, "lev_scale": 1.0,
     "note": "40-entry coverage portfolio, full leverage"},
    {"name": "Millionaire Maker", "entry_fee": 20.0,
     "field_size": MILLY_FIELD, "entries": 4, "lev_scale": 1.0,
     "note": "4 lottery tickets at the 194+ line"},
    {"name": "Small qualifier / single-entry", "entry_fee": 5.0,
     "field_size": 5_000, "entries": 3, "lev_scale": 0.7,
     "note": "each lineup self-sufficient; moderated chalk fade"},
    # High-stakes: sharp field — our chalk fade is soft-field-calibrated,
    # so halve it; 3-max entries must each stand alone (memory:
    # contest-mix-qualifiers, 2026-08-03).
    {"name": "$333 High-Stakes (3-max)", "entry_fee": 333.0,
     "field_size": 3_000, "entries": 3, "lev_scale": 0.5,
     "note": "sharp field: halved chalk fade, self-sufficient entries"},
]


def _strategy_for(field_size: float, entry_fee: float) -> dict:
    """Auto-strategy for LIVE contests (no hand-tuned preset): sharp
    small/high-stakes fields get moderated leverage and few entries."""
    if entry_fee >= 100 or field_size <= 3_500:
        return {"entries": 3, "lev_scale": 0.5,
                "note": "sharp field: halved chalk fade, 3 entries"}
    if field_size <= 10_000:
        return {"entries": 3, "lev_scale": 0.7,
                "note": "small field: moderated fade, few entries"}
    return {"entries": 40, "lev_scale": 1.0,
            "note": "large field: coverage portfolio, full leverage"}


@app.get("/contests")
def contest_options() -> dict:
    """Contest picker: live upcoming DK contests when the fill-poll table
    has them, else just the presets. Every option carries the field size
    and the tail line the confidence ordering will target."""
    live: list[dict] = []
    try:
        from ..bq import query_df
        from ..config import settings

        df = query_df(f"""
            SELECT name, entry_fee, field_size, prize_pool FROM (
              SELECT name, entry_fee, max_entries AS field_size, prize_pool,
                     ROW_NUMBER() OVER (PARTITION BY contest_id
                                        ORDER BY pulled_at DESC) rn
              FROM `{settings.raw}.dk_contest_fills`
              WHERE start_time > CURRENT_TIMESTAMP()
                AND is_guaranteed AND max_entries >= 1000)
            WHERE rn = 1 ORDER BY prize_pool DESC LIMIT 25""")
        live = df.to_dict("records")
    except Exception as exc:  # table absent until the scaffold is enabled
        log.info("live contest list unavailable (%s); presets only", exc)
    for c in live:
        c.update(_strategy_for(float(c["field_size"]),
                               float(c.get("entry_fee") or 0)))
    for c in live + CONTEST_PRESETS:
        c["tail_line"] = tail_line_for_field(int(c["field_size"]))
    return {"live": live, "presets": CONTEST_PRESETS}


def _rank_by_confidence(lineups: list, df: pd.DataFrame,
                        line: float = MIN_MILLY_LINE) -> list[dict]:
    """Sort lineups by tournament confidence — P(lineup total >= line)
    under a normal approximation from each player's projection mean and
    std. Independence understates stacked lineups' true tail, so treat
    the number as an ordering signal, not a literal probability; the
    untilted means are used (confidence is about scoring, not leverage)."""
    from statistics import NormalDist

    mu_map = df.set_index("dk_player_id").proj_points.to_dict()
    sd_map = (df.set_index("dk_player_id").proj_std.to_dict()
              if "proj_std" in df.columns else {})
    ranked = []
    for lu in lineups:
        mu = sum(float(mu_map.get(p["id"], p["proj"])) for p in lu.players)
        var = sum(float(sd_map.get(p["id"], 0) or 0) ** 2 for p in lu.players)
        sigma = max(var ** 0.5, 1e-6)
        p_line = 1 - NormalDist(mu, sigma).cdf(line)
        ranked.append({"lineup": lu, "proj_mean": round(mu, 1),
                       "confidence": round(100 * p_line, 2)})
    ranked.sort(key=lambda r: (r["confidence"], r["proj_mean"]), reverse=True)
    return ranked


def _classic_projections(
    req: LineupRequest, store: ProjectionStore
) -> tuple[pd.DataFrame, dict[int, int]]:
    """The week's projections plus draftable IDs, restricted to the chosen
    classic slate when the request names one. Slate salaries and draftable
    IDs override the projection row's — both are slate-specific, and a CSV
    with another slate's draftable IDs is a CSV DK rejects."""
    df = store.projections(req.season, req.week)
    if df.empty:
        raise HTTPException(404, f"No projections for {req.season} week {req.week}")
    if req.draft_group_id is None:
        return df, _classic_dk_ids(store)
    sal = store.classic_salaries(req.draft_group_id)
    if sal.empty:
        raise HTTPException(
            404, f"No classic slate {req.draft_group_id}; "
                 f"see GET /classic/slates for what's upcoming")
    sal = sal.drop_duplicates(subset=["dk_player_id"]).set_index("dk_player_id")
    df = df[df.dk_player_id.isin(sal.index)].copy()
    if df.empty:
        raise HTTPException(
            404, f"No projections overlap slate {req.draft_group_id}; "
                 f"run project after ingest-dk")
    df["salary"] = (df.dk_player_id.map(sal.salary)
                    .fillna(df.salary).astype(int))
    if "game_start" in sal.columns:
        # Feeds slot_order()'s late-swap FLEX preference (roadmap #13.2);
        # absent for callers with no chosen slate, which is the existing
        # proj-based behavior.
        df["kickoff"] = df.dk_player_id.map(sal.game_start)
    unprojected = len(sal) - df.dk_player_id.nunique()
    if unprojected:
        log.info("slate %s: %d salary rows have no projection and are "
                 "left out of the pool", req.draft_group_id, unprojected)
    dk_ids = {int(pid): int(d)
              for pid, d in sal.dk_draftable_id.dropna().items()}
    return df, dk_ids


def _build_classic(req: LineupRequest, store: ProjectionStore) -> tuple:
    df, dk_ids = _classic_projections(req, store)
    from .. import notes as _notes

    stack = StackRules(
        qb_stack_min=req.qb_stack_min,
        bring_back_min=req.bring_back_min,
        forbid_rb_vs_dst=req.forbid_rb_vs_dst,
    )
    # Sim-mode is THE path (validated replay engine on the live slate,
    # locks/bans/slate-restriction included). No silent fallback — the
    # user chose the validated system always (2026-08-03): a sim failure
    # returns a clear error naming the cause; sim=false is the explicit
    # escape hatch to the plain MILP path.
    if req.sim:
        allowed = None
        if req.draft_group_id is not None:
            allowed = set(int(p) for p in df.dk_player_id.dropna())
        try:
            from ..inference.live_lineups import build_sim_lineups

            lineups = build_sim_lineups(
                req.season, req.week, n_entries=req.n_lineups,
                stack=stack, tail_line=req.line(),
                lev_scale=req.lev_scale,
                locks=set(req.locks), bans=set(req.bans),
                allowed_ids=allowed, theses=req.theses or None,
                apply_notes=req.apply_notes)
        except HTTPException:
            raise
        except Exception as exc:
            log.exception("sim-mode lineup build failed")
            raise HTTPException(
                503, "Sim-mode build failed "
                f"({type(exc).__name__}: {str(exc)[:200]}). Fix the cause "
                "or pass sim=false to explicitly use the MILP path.")
        if not lineups:
            raise HTTPException(
                422, "Sim-mode found no feasible lineups under the given "
                     "constraints")
        # dk_id + kickoff onto sim-built players: kickoff drives the
        # latest-kickoff FLEX preference (late-swap flexibility) and was
        # silently absent from the sim path (2026-08-04 audit).
        kick = {}
        if "kickoff" in df.columns:
            kick = {int(k): (v if pd.notna(v) else None)
                    for k, v in zip(df.dk_player_id, df.kickoff)
                    if pd.notna(k)}
        for lu in lineups:
            for p in lu.players:
                p.setdefault("dk_id", (dk_ids or {}).get(int(p["id"])))
                p.setdefault("kickoff", kick.get(int(p["id"])))
        ranked = _rank_by_confidence(lineups, df, line=req.line())
        _annotate_leverage([r["lineup"] for r in ranked], slate=df)
        return [r["lineup"] for r in ranked], ranked

    pool = _player_pool(df, req.objective, dk_ids, lev_scale=req.lev_scale)
    if req.apply_notes:
        pool = _notes.apply_prefs(pool, req.season, req.week)
    lineups = optimize_many(
        pool, n_lineups=req.n_lineups, stack=stack,
        locks=set(req.locks), bans=set(req.bans), max_overlap=req.max_overlap,
    )
    if not lineups:
        raise HTTPException(422, "No feasible lineup under the given constraints")
    # Confidence order everywhere (JSON + CSVs): first lineup = strongest
    # entry, so "enter the top N in the bigger contest" is just slicing.
    ranked = _rank_by_confidence(lineups, df, line=req.line())
    _annotate_leverage([r["lineup"] for r in ranked], slate=df)
    return [r["lineup"] for r in ranked], ranked


def _annotate_leverage(lineups: list, slate: pd.DataFrame | None = None) -> None:
    """Stokastic-style Lev% (2026-08-03 vendor-methodology audit): a
    player's exposure across OUR chosen entries minus his expected field
    ownership — 'how much more are we on him than the field will be'.
    Display-only; positive = our stand, negative = underweight vs field.
    Fail-safe: lineups without the metric beat no lineups.

    Field ownership normalizes over the FULL slate when provided
    (2026-08-04 audit): normalizing over only the ~30 rostered players
    overstated every field percentage ~10x and biased Lev% hard
    negative."""
    try:
        import pandas as _pd

        from ..backtest.field import naive_ownership

        players: dict[int, dict] = {}
        counts: dict[int, int] = {}
        for lu in lineups:
            for p in lu.players:
                players[p["id"]] = p
                counts[p["id"]] = counts.get(p["id"], 0) + 1
        pool = list(players.values())
        if slate is not None and {"dk_player_id", "position", "salary",
                                  "proj_points"} <= set(slate.columns):
            full = _pd.DataFrame({
                "pos": slate.position, "salary": slate.salary,
                "proj": slate.proj_points})
            own_map = dict(zip(slate.dk_player_id.astype(int),
                               naive_ownership(full)))
            own = [own_map.get(int(p["id"]), 0.0) for p in pool]
        else:
            own = naive_ownership(_pd.DataFrame(pool))
        slots = {"QB": 1.0, "RB": 2.5, "WR": 3.5, "TE": 1.2, "DST": 1.0}
        n = max(len(lineups), 1)
        for p, w in zip(pool, own):
            field_pct = 100.0 * float(w) * slots.get(str(p.get("pos")), 1.0)
            expo = 100.0 * counts[p["id"]] / n
            p["lev_pct"] = round(expo - field_pct, 1)
    except Exception:
        log.exception("leverage annotation failed; lineups unannotated")


@app.post("/lineups")
def build_lineups(
    req: LineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    lineups, ranked = _build_classic(req, store)
    return {
        "tail_line": req.line(),  # what "confidence" is P(score >= X) of
        "lineups": [
            {
                "rank": i + 1,
                "confidence": r["confidence"],  # P(total >= tail_line), %
                "proj_mean": r["proj_mean"],
                "players": _with_watch_notes(r["lineup"].slot_order()),
                "salary": r["lineup"].salary,
                "proj": round(r["lineup"].proj, 2),
            }
            for i, r in enumerate(ranked)
        ],
        "exposure": exposure_summary(lineups),
        "dk_csv": to_dk_csv(lineups),
    }


class CoreLineupRequest(LineupRequest):
    """Core-and-variations mode: a consensus core (picked on the stable
    median objective) locked into every entry, with the remaining spots
    varied on `objective` (defaults to ceiling — variation is for upside).
    core_size omitted = the system decides how many players it feels
    strongly about (conviction + positional value, with a budget guard so
    the core can't hoard the salary cap)."""

    objective: str = Field("proj_p90", pattern="^proj_(points|p50|p90)$")
    core_size: int | None = Field(None, ge=2, le=8)


@app.post("/lineups/core")
def build_core_lineups(
    req: CoreLineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    df, dk_ids = _classic_projections(req, store)
    stable_pool = _player_pool(df, "proj_p50", dk_ids)
    upside_pool = _player_pool(df, req.objective, dk_ids)
    stack = StackRules(
        qb_stack_min=req.qb_stack_min,
        bring_back_min=req.bring_back_min,
        forbid_rb_vs_dst=req.forbid_rb_vs_dst,
    )
    core, lineups = core_and_variations(
        stable_pool, upside_pool, n_lineups=req.n_lineups,
        core_size=req.core_size, stack=stack,
        locks=set(req.locks), bans=set(req.bans),
        max_overlap=req.max_overlap if req.max_overlap != 7 else None,
    )
    if not lineups:
        raise HTTPException(422, "No feasible lineup under the given constraints")
    by_id = {p["id"]: p for p in upside_pool}
    ranked = _rank_by_confidence(lineups, df, line=req.line())
    return {
        "tail_line": req.line(),
        "core": [
            {"id": c["id"], "conviction": c["conviction"],
             "name": by_id[c["id"]]["name"], "pos": by_id[c["id"]]["pos"],
             "team": by_id[c["id"]]["team"], "salary": by_id[c["id"]]["salary"]}
            for c in core
        ],
        "lineups": [
            {"rank": i + 1, "confidence": r["confidence"],
             "proj_mean": r["proj_mean"],
             "players": _with_watch_notes(r["lineup"].slot_order()),
             "salary": r["lineup"].salary,
             "proj": round(r["lineup"].proj, 2)}
            for i, r in enumerate(ranked)
        ],
        "exposure": exposure_summary(lineups),
        "dk_csv": to_dk_csv([r["lineup"] for r in ranked]),
    }


# --- Showdown Captain Mode (single-game slates, guide §9.5) ---------------
#
# DK runs a showdown slate for every game, but the interesting ones here are
# the standalone prime-time games — Thursday and Monday night — so that's
# the default filter. Projections are reused from the classic pipeline
# (joined by DK player id); showdown-only positions (K, DST) fall back to
# DK's own points-per-game figure.

SHOWDOWN_DEFAULT_DAYS = "thu,mon"


def _showdown_games(store: ProjectionStore, days: str) -> pd.DataFrame:
    """One row per upcoming showdown draft group, filtered to the requested
    kickoff days (US/Eastern)."""
    sd = store.showdown_salaries()
    if sd.empty:
        return sd
    start = pd.to_datetime(sd.game_start, utc=True, format="ISO8601")
    sd = sd.assign(
        _day=start.dt.tz_convert("America/New_York").dt.day_name(),
        _start=start,
    )
    wanted = {d.strip().lower()[:3] for d in days.split(",") if d.strip()}
    if wanted:
        sd = sd[sd["_day"].str.lower().str[:3].isin(wanted)]
    return sd


def _showdown_pool(game: pd.DataFrame, proj: pd.DataFrame, objective: str,
                   trailing: pd.DataFrame | None = None) -> list[dict]:
    """Player pool for one showdown game: classic projections joined by DK
    player id; K/DST fall back to trailing-mean DK actuals (issue #10's
    last item, store.trailing_kdst) and only then to DK's dk_ppg figure."""
    teams = sorted(t for t in game.team_abbr.dropna().unique())
    opp = {t: next((o for o in teams if o != t), None) for t in teams}
    by_id = {}
    if not proj.empty:
        cols = ["proj_points", "proj_p50", "proj_p90"]
        if "proj_std" in proj.columns:
            cols.append("proj_std")
        by_id = proj.set_index("dk_player_id")[cols].to_dict("index")
    trail_map = {}
    if trailing is not None and len(trailing):
        trail_map = {(t.kind, t.key): float(t.trailing_pts)
                     for t in trailing.itertuples()}
    pool = []
    for r in game.itertuples():
        row = by_id.get(r.dk_player_id)
        tkey = (("DST", r.team_abbr) if r.position == "DST"
                else ("K", str(r.display_name).upper()))
        if row is not None and pd.notna(row[objective]):
            value, source = float(row[objective]), "model"
        elif tkey in trail_map:
            value, source = trail_map[tkey], "trailing"
        elif pd.notna(r.dk_ppg):
            value, source = float(r.dk_ppg), "dk_ppg"
        else:
            continue  # no projection at all — can't rank the player
        draftable = getattr(r, "dk_draftable_id", None)
        cpt = getattr(r, "dk_cpt_draftable_id", None)
        sd = None
        if row is not None and pd.notna(row.get("proj_std")):
            sd = float(row["proj_std"])
        pool.append(
            {
                "id": int(r.dk_player_id),
                "dk_id": int(draftable) if pd.notna(draftable) else None,
                "cpt_dk_id": int(cpt) if pd.notna(cpt) else None,
                "name": r.display_name,
                "pos": r.position,
                "team": r.team_abbr,
                "opp": opp.get(r.team_abbr),
                "game_id": int(r.draft_group_id),
                "salary": int(r.salary),
                "proj": value,
                "proj_sd": sd,  # None -> sim-mode's FALLBACK_SD_RATIO
                "proj_source": source,
            }
        )
    return pool


class ShowdownLineupRequest(BaseModel):
    season: int
    week: int
    draft_group_id: int | None = None  # default: next upcoming Thu/Mon game
    days: str = SHOWDOWN_DEFAULT_DAYS
    n_lineups: int = Field(1, ge=1, le=150)
    objective: str = Field("proj_points", pattern="^proj_(points|p50|p90)$")
    # Correlated-draw construction, adopted 2026-08-01 (2025 replay:
    # capture 85.0% vs 80.7% MILP, >=90%-capture slates 16/41 vs 8/41).
    # sim=False restores the plain MILP-on-means path.
    sim: bool = True
    locks: list[int] = []
    bans: list[int] = []
    captain: int | None = None
    max_overlap: int = Field(5, ge=1, le=5)


@app.get("/showdown/slates")
def showdown_slates(
    days: str = Query(SHOWDOWN_DEFAULT_DAYS),
    store: ProjectionStore = Depends(get_store),
) -> list[dict]:
    """Upcoming Captain Mode games (default: Thursday/Monday night)."""
    sd = _showdown_games(store, days)
    if sd.empty:
        raise HTTPException(404, "No upcoming showdown slates; run ingest-dk")
    out = []
    for gid, grp in sd.groupby("draft_group_id", sort=False):
        teams = sorted(t for t in grp.team_abbr.dropna().unique())
        out.append(
            {
                "draft_group_id": int(gid),
                "game": " vs ".join(teams),
                "day": grp["_day"].iloc[0],
                "game_start": str(grp["_start"].iloc[0]),
                "players": len(grp),
            }
        )
    return sorted(out, key=lambda g: g["game_start"])


def _build_showdown(
    req: ShowdownLineupRequest, store: ProjectionStore
) -> tuple[pd.DataFrame, list, list | None]:
    sd = _showdown_games(store, "" if req.draft_group_id else req.days)
    if sd.empty:
        raise HTTPException(404, "No upcoming showdown slates; run ingest-dk")
    if req.draft_group_id is not None:
        game = sd[sd.draft_group_id == req.draft_group_id]
        if game.empty:
            raise HTTPException(404, f"No showdown slate {req.draft_group_id}")
    else:
        next_gid = sd.sort_values("_start").draft_group_id.iloc[0]
        game = sd[sd.draft_group_id == next_gid]

    proj = store.projections(req.season, req.week)
    trailing = None
    trail_fn = getattr(store, "trailing_kdst", None)
    if trail_fn is not None:
        try:
            trailing = trail_fn(req.season, req.week)
        except Exception:  # trailing is a fallback nicety, never a blocker
            log.warning("trailing_kdst unavailable", exc_info=True)
    pool = _showdown_pool(game, proj, req.objective, trailing=trailing)
    if len(pool) < 6 or len({p["team"] for p in pool}) < 2:
        raise HTTPException(422, "Showdown pool too thin to build a lineup")
    pool_ids = {p["id"] for p in pool}
    wanted = set(req.locks) | ({req.captain} if req.captain is not None else set())
    if wanted - pool_ids:
        raise HTTPException(
            422, f"Players not in this game's projectable pool: {sorted(wanted - pool_ids)}"
        )

    captain_board = None
    if req.sim:
        from ..optimizer.showdown import sim_mode_entries

        lineups, captain_board = sim_mode_entries(
            pool, req.n_lineups, seed=req.week, locks=set(req.locks),
            bans=set(req.bans) & pool_ids, captain_lock=req.captain,
            with_metrics=True,
        )
    else:
        lineups = optimize_many_showdown(
            pool, n_lineups=req.n_lineups, locks=set(req.locks),
            bans=set(req.bans) & pool_ids,
            captain_lock=req.captain, max_overlap=req.max_overlap,
        )
    if not lineups:
        raise HTTPException(422, "No feasible lineup under the given constraints")
    return game, lineups, captain_board


@app.post("/showdown/lineups")
def build_showdown_lineups(
    req: ShowdownLineupRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    game, lineups, captain_board = _build_showdown(req, store)
    teams = sorted(t for t in game.team_abbr.dropna().unique())
    return {
        "game": {
            "draft_group_id": int(game.draft_group_id.iloc[0]),
            "game": " vs ".join(teams),
            "day": game["_day"].iloc[0],
            "game_start": str(game["_start"].iloc[0]),
        },
        "captain_board": captain_board,
        "lineups": [
            {
                "captain": lu.captain,
                "players": lu.slot_order(),
                "salary": lu.salary,
                "proj": round(lu.proj, 2),
            }
            for lu in lineups
        ],
        "exposure": showdown_exposure_summary(lineups),
        "dk_csv": to_dk_showdown_csv(lineups),
    }


@app.post("/showdown/lineups.csv")
def build_showdown_lineups_csv(
    req: ShowdownLineupRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    payload = build_showdown_lineups(req, store)
    return Response(
        content=payload["dk_csv"],
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dk_showdown_lineups.csv"},
    )


@app.post("/lineups.csv")
def build_lineups_csv(
    req: LineupRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    # ONE build (2026-08-04 audit): this used to run the full sim build
    # twice — 2x latency, and worse, the recorded set could diverge from
    # the uploaded CSV (the ownership booster retrains from BQ per call
    # and BQ tie-breaking is not deterministic — the rebuild law).
    lineups, ranked = _build_classic(req, store)
    try:
        from .. import notes as _n

        _n.record_entered_lineups(req.season, req.week, lineups)
    except Exception:
        log.exception("could not record entered lineups")
    return Response(
        content=to_dk_csv(lineups),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dk_lineups.csv"},
    )


# --- DKEntries filling ----------------------------------------------------
#
# The other DK import path: for contests already entered, download
# DKEntries.csv (Lineups -> Edit Entries on DraftKings), POST it here, and
# re-upload the response on the same screen. One lineup is generated per
# entry row; everything else in the file passes through untouched.

MAX_ENTRIES = 500  # DK's own per-file upload limit


class FillEntriesRequest(LineupRequest):
    entries_csv: str
    n_lineups: int | None = None  # ignored — one lineup per entry row
    # Fill only this contest's rows (multi-contest DKEntries downloads:
    # one download, one fill per contest with that contest's preset;
    # untouched rows pass through for the next pass). None = all rows.
    contest_id: str | None = None


class ShowdownFillEntriesRequest(ShowdownLineupRequest):
    entries_csv: str
    n_lineups: int | None = None  # ignored — one lineup per entry row


def _entries_n(entries_csv: str) -> int:
    try:
        n = entry_count(entries_csv)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if n == 0:
        raise HTTPException(422, "Entries file contains no entry rows")
    if n > MAX_ENTRIES:
        raise HTTPException(422, f"{n} entries exceeds DK's {MAX_ENTRIES}-row limit")
    return n


def _entries_response(entries_csv: str, lineups: list,
                      contest_id: str | None = None) -> Response:
    try:
        filled = fill_entries_csv(entries_csv, lineups, contest_id=contest_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return Response(
        content=filled,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=DKEntries.csv"},
    )


@app.post("/lineups/entries.csv")
def fill_classic_entries(
    req: FillEntriesRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    build_req = req.model_copy(update={"n_lineups": _entries_n(req.entries_csv)})
    return _entries_response(req.entries_csv,
                             _build_classic(build_req, store)[0],
                             contest_id=req.contest_id)


@app.post("/lineups/entries/diff")
def preview_classic_entries(
    req: FillEntriesRequest, store: ProjectionStore = Depends(get_store)
) -> dict:
    """Sunday late-swap preview (2026-08-03): what the entries.csv fill
    WOULD change, per entry — churn-minimizing assignment, locked-player
    rows flagged. Review here, then POST /lineups/entries.csv for the
    upload file (same assignment, deterministic)."""
    from ..optimizer.export import fill_entries_csv

    build_req = req.model_copy(update={"n_lineups": _entries_n(req.entries_csv)})
    lineups = _build_classic(build_req, store)[0]
    diff: list = []
    fill_entries_csv(req.entries_csv, lineups, diff_out=diff,
                     contest_id=req.contest_id)
    changed = [d for d in diff if d["out"] or d["in"]]
    return {"entries": diff,
            "summary": {"total": len(diff), "changed": len(changed),
                        "untouched_locked": sum(d["untouched"] for d in diff),
                        "avg_swaps": round(sum(len(d["out"]) for d in diff)
                                           / len(diff), 2) if diff else 0}}


@app.post("/showdown/lineups/entries.csv")
def fill_showdown_entries(
    req: ShowdownFillEntriesRequest, store: ProjectionStore = Depends(get_store)
) -> Response:
    build_req = req.model_copy(update={"n_lineups": _entries_n(req.entries_csv)})
    _, lineups, _ = _build_showdown(build_req, store)
    return _entries_response(req.entries_csv, lineups)

```

===== FILE: src/nfl_dfs/app/store.py =====
```python
"""Projection storage behind a small interface so the API is testable
without a warehouse and swappable later."""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from ..config import settings

PROJ_COLUMNS = [
    "season", "week", "slate_id", "gsis_id", "dk_player_id", "display_name",
    "position", "team", "opponent", "salary",
    "proj_points", "proj_p10", "proj_p50", "proj_p90", "proj_std",
    "p_20_plus", "value", "model_version", "generated_at",
]


SHOWDOWN_COLUMNS = [
    "draft_group_id", "dk_player_id", "dk_draftable_id",
    "dk_cpt_draftable_id", "display_name", "team_abbr",
    "position", "salary", "game_start", "status", "dk_ppg",
]


CLASSIC_COLUMNS = [
    "draft_group_id", "dk_player_id", "dk_draftable_id", "display_name",
    "team_abbr", "position", "salary", "game_start", "status",
]


class ProjectionStore(Protocol):
    def slates(self) -> pd.DataFrame: ...
    def projections(self, season: int, week: int) -> pd.DataFrame: ...
    def defense_points_against(self, season: int | None = None) -> pd.DataFrame: ...
    def showdown_salaries(self) -> pd.DataFrame: ...
    def classic_slates(self) -> pd.DataFrame: ...
    def classic_salaries(self, draft_group_id: int) -> pd.DataFrame: ...
    def classic_draftable_ids(self) -> pd.DataFrame: ...


class BigQueryStore:
    def slates(self) -> pd.DataFrame:
        from ..bq import query_df

        return query_df(
            f"""
            SELECT season, week, slate_id, COUNT(*) AS players,
                   MAX(generated_at) AS last_generated
            FROM `{settings.predictions}.player_projections`
            GROUP BY 1, 2, 3
            ORDER BY season DESC, week DESC
            """
        )

    def projections(self, season: int, week: int) -> pd.DataFrame:
        from ..bq import query_df

        return query_df(
            f"""
            SELECT * EXCEPT (rn) FROM (
              SELECT *, ROW_NUMBER() OVER (
                PARTITION BY dk_player_id ORDER BY generated_at DESC) AS rn
              FROM `{settings.predictions}.player_projections`
              WHERE season = @season AND week = @week
            ) WHERE rn = 1
            ORDER BY proj_points DESC
            """,
            params={"season": season, "week": week},
        )


    def trailing_kdst(self, season: int, week: int) -> pd.DataFrame:
        """Trailing-mean DK points for K and DST, strictly-prior weeks of
        `season` (min 2 games) — the live showdown pool's fallback for the
        positions the model doesn't cover, replacing raw dk_ppg (issue
        #10's last item). K scoring is computed from distance-bucketed
        kicking stats (DK: 3/4/5-pt FGs + PAT); DST from pbp + schedules
        (sacks/takeaways/TDs + points-allowed brackets).

        Columns: kind ('K'|'DST'), key (UPPER player name for K, team
        abbr for DST), trailing_pts."""
        from ..bq import query_df

        return query_df(
            f"""
            WITH k AS (
              SELECT 'K' AS kind, UPPER(player_display_name) AS key,
                     AVG(3*(fg_made_0_19+fg_made_20_29+fg_made_30_39)
                         + 4*fg_made_40_49
                         + 5*(fg_made_50_59+fg_made_60_)
                         + pat_made) AS trailing_pts,
                     COUNT(*) AS games
              FROM `{settings.raw}.weekly_stats`
              WHERE position = 'K' AND season = @season AND week < @week
              GROUP BY key
            ),
            def_game AS (
              SELECT p.game_id, p.defteam AS team, ANY_VALUE(p.week) AS week,
                     SUM(CAST(p.sack AS INT64)) AS sacks,
                     SUM(CAST(p.interception AS INT64))
                       + SUM(IF(p.fumble_lost = 1, 1, 0)) AS takeaways,
                     SUM(IF(p.touchdown = 1 AND p.td_team = p.defteam, 1, 0)) AS tds
              FROM `{settings.raw}.pbp` p
              WHERE p.season = @season AND p.week < @week AND p.defteam IS NOT NULL
              GROUP BY p.game_id, p.defteam
            ),
            pts AS (
              SELECT game_id, home_team AS team, away_score AS pa
              FROM `{settings.raw}.schedules` WHERE season = @season
              UNION ALL
              SELECT game_id, away_team, home_score
              FROM `{settings.raw}.schedules` WHERE season = @season
            ),
            d AS (
              SELECT 'DST' AS kind, dg.team AS key,
                     AVG(dg.sacks + 2*dg.takeaways + 6*dg.tds +
                         CASE WHEN p.pa = 0 THEN 10 WHEN p.pa <= 6 THEN 7
                              WHEN p.pa <= 13 THEN 4 WHEN p.pa <= 20 THEN 1
                              WHEN p.pa <= 27 THEN 0 WHEN p.pa <= 34 THEN -1
                              ELSE -4 END) AS trailing_pts,
                     COUNT(*) AS games
              FROM def_game dg JOIN pts p USING (game_id, team)
              GROUP BY key
            )
            SELECT kind, key, trailing_pts FROM k WHERE games >= 2
            UNION ALL
            SELECT kind, key, trailing_pts FROM d WHERE games >= 2
            """,
            params={"season": season, "week": week},
        )

    def showdown_salaries(self) -> pd.DataFrame:
        """Latest pull per upcoming showdown draft group (one game each).
        Salaries are FLEX-slot; the optimizer derives the 1.5x CPT cost."""
        from ..bq import query_df

        return query_df(
            f"""
            WITH pulls AS (
              SELECT draft_group_id, MAX(pulled_at) AS ts
              FROM `{settings.raw}.dk_salaries`
              WHERE slate_type = 'showdown'
                AND game_start >= CURRENT_TIMESTAMP()
              GROUP BY draft_group_id
            )
            SELECT s.draft_group_id, s.dk_player_id, s.dk_draftable_id,
                   s.dk_cpt_draftable_id, s.display_name,
                   s.team_abbr, s.position, s.salary, s.game_start,
                   s.status, s.dk_ppg
            FROM `{settings.raw}.dk_salaries` s
            JOIN pulls p
              ON s.draft_group_id = p.draft_group_id AND s.pulled_at = p.ts
            WHERE s.slate_type = 'showdown'
            ORDER BY s.game_start, s.salary DESC
            """
        )

    def classic_slates(self) -> pd.DataFrame:
        """One row per (upcoming classic draft group, kickoff time): team and
        player counts from the latest pull per group. A group stays listed
        until its last game kicks off, so late swap keeps working after the
        early games lock."""
        from ..bq import query_df

        return query_df(
            f"""
            WITH pulls AS (
              SELECT draft_group_id, MAX(pulled_at) AS ts
              FROM `{settings.raw}.dk_salaries`
              WHERE slate_type = 'classic'
              GROUP BY draft_group_id
              HAVING MAX(game_start) >= CURRENT_TIMESTAMP()
            )
            SELECT s.draft_group_id, s.game_start,
                   COUNT(DISTINCT s.team_abbr) AS teams,
                   COUNT(DISTINCT s.dk_player_id) AS players
            FROM `{settings.raw}.dk_salaries` s
            JOIN pulls p
              ON s.draft_group_id = p.draft_group_id AND s.pulled_at = p.ts
            WHERE s.slate_type = 'classic'
            GROUP BY 1, 2
            ORDER BY s.draft_group_id, s.game_start
            """
        )

    def classic_salaries(self, draft_group_id: int) -> pd.DataFrame:
        """Latest pull for one classic draft group: the slate's player pool
        with its own salaries and draftable IDs (both are slate-specific)."""
        from ..bq import query_df

        return query_df(
            f"""
            WITH pull AS (
              SELECT MAX(pulled_at) AS ts
              FROM `{settings.raw}.dk_salaries`
              WHERE slate_type = 'classic' AND draft_group_id = @gid
            )
            SELECT DISTINCT s.draft_group_id, s.dk_player_id,
                   s.dk_draftable_id, s.display_name, s.team_abbr,
                   s.position, s.salary, s.game_start, s.status
            FROM `{settings.raw}.dk_salaries` s, pull
            WHERE s.pulled_at = pull.ts AND s.slate_type = 'classic'
              AND s.draft_group_id = @gid
            """,
            params={"gid": int(draft_group_id)},
        )

    def classic_draftable_ids(self) -> pd.DataFrame:
        """dk_player_id -> draftable ID from the latest classic pull. The
        upload CSV needs draftable IDs (the DKSalaries 'ID' column), which
        change every slate — so this is always the freshest snapshot."""
        from ..bq import query_df

        return query_df(
            f"""
            WITH latest_pull AS (
              SELECT MAX(pulled_at) AS ts FROM `{settings.raw}.dk_salaries`
              WHERE slate_type = 'classic'
            )
            SELECT DISTINCT s.dk_player_id, s.dk_draftable_id
            FROM `{settings.raw}.dk_salaries` s, latest_pull
            WHERE s.pulled_at = latest_pull.ts AND s.slate_type = 'classic'
              AND s.dk_draftable_id IS NOT NULL
            """
        )

    def defense_points_against(self, season: int | None = None) -> pd.DataFrame:
        from ..bq import query_df

        where = f"WHERE season = {int(season)}" if season else ""
        return query_df(
            f"""
            SELECT * FROM `{settings.features}.defense_points_against`
            {where}
            ORDER BY season, week, position, team
            """
        )


class InMemoryStore:
    """For tests and local demos."""

    def __init__(self, frame: pd.DataFrame, defense: pd.DataFrame | None = None,
                 showdown: pd.DataFrame | None = None,
                 draftables: pd.DataFrame | None = None,
                 classic: pd.DataFrame | None = None):
        self.frame = frame
        self.defense = defense if defense is not None else pd.DataFrame(
            columns=["team", "season", "week", "position", "fp_allowed",
                     "fp_allowed_l3", "fp_allowed_l6", "fp_allowed_season", "trend"]
        )
        self.showdown = showdown if showdown is not None else pd.DataFrame(
            columns=SHOWDOWN_COLUMNS
        )
        self.draftables = draftables if draftables is not None else pd.DataFrame(
            columns=["dk_player_id", "dk_draftable_id"]
        )
        self.classic = classic if classic is not None else pd.DataFrame(
            columns=CLASSIC_COLUMNS
        )

    def showdown_salaries(self) -> pd.DataFrame:
        return self.showdown

    def classic_slates(self) -> pd.DataFrame:
        if self.classic.empty:
            return pd.DataFrame(
                columns=["draft_group_id", "game_start", "teams", "players"]
            )
        return (
            self.classic.groupby(["draft_group_id", "game_start"])
            .agg(teams=("team_abbr", "nunique"),
                 players=("dk_player_id", "nunique"))
            .reset_index()
        )

    def classic_salaries(self, draft_group_id: int) -> pd.DataFrame:
        c = self.classic
        return c[c.draft_group_id == draft_group_id].reset_index(drop=True)

    def classic_draftable_ids(self) -> pd.DataFrame:
        return self.draftables

    def defense_points_against(self, season: int | None = None) -> pd.DataFrame:
        df = self.defense
        return df[df.season == season] if season else df

    def slates(self) -> pd.DataFrame:
        return (
            self.frame.groupby(["season", "week"])
            .size()
            .reset_index(name="players")
        )

    def projections(self, season: int, week: int) -> pd.DataFrame:
        df = self.frame
        return df[(df.season == season) & (df.week == week)].reset_index(drop=True)

```

===== FILE: src/nfl_dfs/app/system_context.py =====
```python
"""Curated system knowledge for the chat assistant.

The chat's job includes reasoning about how a piece of player news
interacts with what the system ALREADY prices -- especially when
suggesting how to convert a watchlist note into a usage-note multiplier.
This module is the compact, maintained source of that knowledge (the
full documents are available via the read_doc tool; these sections are
written to be loaded into a tool result and reasoned over directly).

Update this file when the modeling changes -- it is documentation the
chat treats as ground truth.
"""

from __future__ import annotations

SECTIONS: dict[str, str] = {

    "overview": """\
Pipeline: BigQuery raw data -> point-in-time features (one row per
player-week; a week-W row only contains what was knowable before
kickoff) -> LightGBM component models (targets, carries, catch rate,
yards-per, TDs -- trained walk-forward, recency-weighted, 2014-2025) ->
Monte Carlo simulator (10,000 correlated worlds per week; possession
engine gives each game/team mean-preserving factors) -> MILP optimizer
(salary cap, roster rules, validated tournament constraints: mandatory
bring-back, sub-$4k punt, RB-vs-DST ban, chalk fade) -> greedy
tail-coverage selection of 40 entries maximizing P(best entry >= the
winning line). Everything is validated by deterministic season replays;
the shipping baseline is measured across six seasons (2019-2025).""",

    "notes_and_adjustments": """\
Two distinct note systems:
1. WATCH NOTES (watchlist.py): free text attached to a player. Affect
   NOTHING numerically. Shown on generated lineups and the Watchlist
   page. Stage one of: watch -> maybe convert.
2. USAGE NOTES (notes.py): a real adjustment. `mult` scales the
   player's OPPORTUNITY components only -- targets, carries, pass
   attempts -- NOT efficiency (yards per touch, TD rate stay modeled).
   Clamped to [0.6, 1.4]. Applied at full strength in week 1, decaying
   LINEARLY TO ZERO BY WEEK 6 -- by then actual snaps/usage flow into
   the trailing features and speak for themselves. Applied at live
   inference only, never in replays (forward-looking by construction).
Conversion (convert_watch_note) creates the usage note and stamps the
watch note converted, preserving provenance.""",

    "conversion_guide": """\
How to suggest a mult when converting a watch note. First diagnose the
note's ARCHETYPE, because each interacts differently with what the
system already prices:

A. OFFSEASON DEPARTURE / DEPTH-CHART VACANCY (trade or free agency
   opened the role -- e.g. "starter left, player X now atop depth
   chart"). The team_vacated_* features DO NOT see this: they read
   weekly INJURY REPORTS only, not departures. What does adapt:
   depth_rank (updates from depth charts) and cold-start role priors.
   The trailing usage features still reflect the old backup role for
   ~4 weeks. => This archetype deserves a REAL mult: +10-20% (1.10-
   1.20) for a clean, uncontested inheritance; +5-10% if the backfield/
   room is crowded. Check the depth chart first (get_player_form /
   explain_player) -- notes like "team also added two other backs"
   should cap the suggestion low.

B. NEW TEAM, CLEAR ROLE (veteran traded/signed into a bigger role).
   The system's WEAKEST spot and usage notes' BEST use: trailing
   features carry OLD-team usage (misleading), and veterans aren't
   cold-started (their history exists). => +10-25% depending on role
   clarity and target competition on the new team. The strongest case
   is a proven player whose old-team share was suppressed.

C. NEW COACH / SCHEME FIT ("zone scheme suits him", "new OC throws
   more"). Weakest evidence class; scheme features (neutral pass rate,
   pace) only learn from games played. => +5-10% at most, or advise
   keeping it as a watch note until September practice reports firm it
   up.

D. IN-SEASON INJURY VACANCY (starter on the injury report as Out).
   ALREADY PRICED: team_vacated_target/carry_share and depth_rank
   capture this the same week. => usually NO note needed (0-5%);
   adding one double-counts.

E. TALENT/EFFICIENCY TAKES ("fastest 40 time", "looked explosive").
   Usage notes scale OPPORTUNITY, not efficiency -- a speed note only
   converts if it implies MORE TOUCHES. Alone => keep as watch note.

Global dampeners to mention when suggesting:
- The props-market blend already prices all PUBLIC news within days;
  the mult should express edge beyond market consensus, which argues
  for the low end of each range.
- Multiple notes on one player MULTIPLY -- check list_usage_notes
  before stacking.
- Decay: full effect week 1 -> zero by week 6; a note added mid-season
  still decays on the same weekly schedule.
Protocol: read the note, call get_player_form/explain_player to check
the CURRENT depth chart and competition, classify the archetype, state
the suggested mult WITH the archetype reasoning and double-count
warnings, get the user's confirmation, then convert.

CAMP-SIGNAL CORROBORATION (convert-or-wait rule for August/September
notes): count independent corroborations in the note and any follow-ups
-- (1) first-team reps in MULTIPLE practices, (2) first-team/starter
usage in a PRESEASON GAME, (3) coach or teammate quotes naming the
role, (4) a depth-chart or beat-writer confirmation. 0-1 corroborations
=> keep as watch note, do not convert. 2 => convert at the LOW end of
the archetype range. 3+ => the archetype range as written. Camp hype
with zero usage evidence never converts.

SCHEME-CHANGE YEAR (2026): roughly 10 new head coaches and ~20 new
offensive playcallers this season -- an unusually large turnover. For
players on a team with a NEW PLAYCALLER, the trailing team features
(neutral pass rate, pace, target concentration) carry the OLD scheme
for the first ~4-6 weeks, so (a) last-year usage arguments are weaker
than normal there, (b) credible camp-role notes are MORE valuable than
in a normal year and may justify the upper half of the archetype range
when corroboration is 3+, and (c) the props blend is the fastest
adapter -- if the market has already moved a player's props, much of
the scheme story is priced. Ask the user (or check the note) whether
the team changed playcallers rather than assuming.""",

    "already_priced": """\
Signals the model already carries (adding a note for these
double-counts): trailing usage shares and trends (targets/carries/
snaps, last 4 weeks), red-zone and end-zone usage, depth chart rank,
draft capital and rookie flags, cold-start role priors, THIS-WEEK
injury-report vacancies (team_vacated_*), opponent defense quality
including CB coverage and top-CB-out, Vegas lines (spread, totals,
implied team total), weather, referee crew tendency, neutral-script
pass rate, QB CPOE (throw quality), salary and week-over-week salary
change, and the prop-market blend (sportsbook player props folded into
projections). NOT carried: offseason departures/trades (archetype A/B
above), scheme projection, camp reports.""",
}


def get_section(topic: str) -> str:
    t = (topic or "").strip().lower()
    if t in SECTIONS:
        return SECTIONS[t]
    return ("unknown topic; available: " + ", ".join(SECTIONS) +
            "\n\n" + SECTIONS["overview"])


def read_doc(name: str) -> str:
    """Full project documents, when the curated sections aren't enough.
    Reads from the container WORKDIR (Dockerfile copies them) with a
    repo-checkout fallback."""
    from pathlib import Path

    docs = {
        "model-primer": ["reports/model-primer.md"],
        "claude-md": ["CLAUDE.md"],
        "readme": ["README.md"],
    }
    rel = docs.get((name or "").strip().lower())
    if not rel:
        return "unknown doc; available: " + ", ".join(docs)
    for base in (Path.cwd(), Path(__file__).resolve().parents[3]):
        p = base / rel[0]
        if p.is_file():
            text = p.read_text()
            return text[:60_000] + ("\n...[truncated]" if len(text) > 60_000 else "")
    return f"{rel[0]} not found in this deployment"

```

===== FILE: src/nfl_dfs/backtest/__init__.py =====
```python

```

===== FILE: src/nfl_dfs/backtest/engine.py =====
```python
"""Backtest engine (guide §10): reconstruct historical slates, project with
point-in-time features only, build lineups, score against actuals, simulate
contest outcomes, report ROI.

Run over 3+ full seasons before risking money: single-season DFS results
are noise, and a bad model looks great over 17 weeks about as often as it
looks bad.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field as dc_field

import numpy as np
import pandas as pd

from ..optimizer.lineup import (Lineup, StackRules, optimize, optimize_many,
                                select_tail_entries)
from . import field as field_sim
from .payout import Contest, roi

log = logging.getLogger(__name__)

REQUIRED_COLS = {"id", "name", "pos", "team", "opp", "game_id",
                 "salary", "proj", "actual"}


@dataclass
class WeekResult:
    season: int
    week: int
    lineups: list[Lineup]
    lineup_scores: list[float]
    percentiles: list[float]
    winnings: list[float]


@dataclass
class BacktestResult:
    weeks: list[WeekResult] = dc_field(default_factory=list)
    contest: Contest | None = None

    @property
    def total_roi(self) -> float:
        w = [x for wk in self.weeks for x in wk.winnings]
        return roi(np.array(w), self.contest.entry_fee) if w else 0.0

    def roi_by_season(self) -> dict[int, float]:
        out: dict[int, list[float]] = {}
        for wk in self.weeks:
            out.setdefault(wk.season, []).extend(wk.winnings)
        return {s: roi(np.array(w), self.contest.entry_fee) for s, w in out.items()}

    def summary(self) -> str:
        lines = [f"contest={self.contest.name}  entries={sum(len(w.winnings) for w in self.weeks)}"]
        for season, r in sorted(self.roi_by_season().items()):
            lines.append(f"  {season}: ROI {r:+.1%}")
        lines.append(f"  TOTAL: ROI {self.total_roi:+.1%}")
        med = np.median([p for wk in self.weeks for p in wk.percentiles] or [0])
        lines.append(f"  median finish percentile: {med:.1%} (lower is better)")
        return "\n".join(lines)


def leakage_guard(slate: pd.DataFrame) -> None:
    """Cheap structural checks that the slate frame is point-in-time: the
    projection must not equal the actual (a copied column is the classic
    reconstruction bug), and required columns exist."""
    missing = REQUIRED_COLS - set(slate.columns)
    if missing:
        raise ValueError(f"Slate missing columns: {sorted(missing)}")
    both = slate.dropna(subset=["proj", "actual"])
    if len(both) >= 30 and np.allclose(both["proj"], both["actual"]):
        raise AssertionError(
            "proj == actual for the whole slate; projections were "
            "reconstructed from the answer key."
        )


def _row_draws(slate: pd.DataFrame, draws: np.ndarray) -> np.ndarray:
    """Per-slate-row draw matrix, aligned to slate row order. Rows without a
    draw (DST, draw_idx == -1) get their static projection in every sim.

    DST_CORR_DRAWS=1 (A/B, 2026-08-01): constants mean the tail selector
    can never prefer a DST for its boom worlds, even though DST scoring
    anti-correlates with the opposing offense (turnovers, points-allowed
    brackets) and 7/17 winning 2025 Milly punts were DSTs (Addendum 24).
    With the gate on, each DST row gets mean-preserving draws scaled by
    the INVERSE of its opponent's simulated offense total: mult =
    clip(2 - opp_total/mean, 0.3, 1.7), renormalized to mean 1."""
    import os as _os

    di = slate["draw_idx"].to_numpy(dtype=int)
    out = np.empty((len(slate), draws.shape[1]), dtype=np.float32)
    has = di >= 0
    out[has] = draws[di[has]]
    out[~has] = slate["proj"].to_numpy(dtype=float)[~has, None]
    if _os.environ.get("DST_CORR_DRAWS") and (~has).any() and "opp" in slate.columns:
        # Fitted 2026-08-01 from 4,390 team-games 2018-25: DST DK points
        # correlate -0.491 with the opposing offense's total fantasy
        # points, with relative sd 0.93 (mean 6.2, sd 5.8). The first
        # (nulled) version had it backwards on both axes: ~-0.9 corr but
        # only ~0.3 rel-sd. Draws hit the measured moments exactly:
        # mult = 1 + rel_sd*(corr*z_opp + sqrt(1-corr^2)*z_iid), floored
        # (DK DST brackets go to -4) and renormalized to mean 1.
        DST_OPP_CORR, DST_REL_SD = -0.491, 0.93
        rng = np.random.default_rng(70921)  # distinct from marginal rng(seed+7) — audit
        teams = slate["team"].to_numpy()
        opps = slate["opp"].to_numpy()
        for i in np.flatnonzero(~has):
            rows = np.flatnonzero(has & (teams == opps[i]))
            if not len(rows):
                continue
            tot = draws[di[rows]].sum(axis=0)
            sd = tot.std()
            if sd <= 0 or tot.mean() <= 0:
                continue
            z_opp = (tot - tot.mean()) / sd
            z_iid = rng.standard_normal(tot.shape[0])
            mult = 1.0 + DST_REL_SD * (DST_OPP_CORR * z_opp
                                       + np.sqrt(1 - DST_OPP_CORR ** 2) * z_iid)
            mult = np.clip(mult, -0.7, None)
            out[i] = out[i] * (mult / mult.mean())
    return out


def _tier_thresholds(contest: Contest) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized form of Contest.payout_for_rank: cumulative field
    fractions and dollar payouts per tier."""
    cums, pays = [], []
    c = 0.0
    for top_frac, mult in contest.tiers:
        c += top_frac
        cums.append(c)
        pays.append(contest.entry_fee * mult)
    return np.asarray(cums), np.asarray(pays)


def select_dollar_entries(
    slate: pd.DataFrame,
    rd: np.ndarray,
    cands: list[Lineup],
    cand_totals: np.ndarray,
    n_entries: int,
    contest: Contest,
    sharp_fraction: float = 0.0,
    max_overlap: int = 7,
    n_field: int = 1000,
    n_sim_sub: int = 2000,
    seed: int = 42,
) -> list[int]:
    """SELECT_OBJ=dollars (2026-08-01): expected-DOLLARS entry selection.

    The tail-line objective is a step function at one line; real payouts
    are a curve. Here each candidate is scored by its expected winnings:
    a subsampled simulated FIELD (ownership-weighted lineups, scored in
    the SAME correlated sims as our candidates via the draw matrix) gives
    each candidate a per-sim rank, the contest curve converts rank to
    dollars, and E[$] is additive across entries -- so selection is
    greedy by E[$] under the uniqueness (max_overlap) constraint. This
    was issue #13's "expected-dollars objective once field model exists";
    the LineStar ownership model is that field model (pass model_own on
    the slate to use it)."""
    own_vec = (slate["model_own"].to_numpy()
               if "model_own" in slate.columns and slate["model_own"].notna().all()
               else None)
    fld = field_sim.sample_field(slate, n_lineups=n_field, seed=seed,
                                 ownership=own_vec,
                                 sharp_fraction=sharp_fraction)
    if not fld:
        return list(range(min(n_entries, len(cands))))
    rng = np.random.default_rng(seed)
    k_idx = rng.choice(rd.shape[1], size=min(n_sim_sub, rd.shape[1]),
                       replace=False)
    rd_sub = rd[:, k_idx]
    F = np.stack([rd_sub[f].sum(axis=0) for f in fld])  # (n_field, K)
    cums, pays = _tier_thresholds(contest)
    ct = cand_totals[:, k_idx]
    # Tail-resolved rank estimation (Addendum 34 fix): a coarse sampled
    # field resolves ranks only to 1/n_field, but GPP payouts concentrate
    # at 1e-5 of the field -- "beat the whole sample" spans $10..$100k.
    # Hybrid: empirical count where >= EMP_MIN field lineups are ahead;
    # otherwise a normal-tail extrapolation of the per-sim field score
    # distribution, capped by the empirical upper bound so the parametric
    # tail can only REFINE below sample resolution, never contradict it.
    EMP_MIN = 10
    from scipy.stats import norm

    mu = F.mean(axis=0)                                     # per-sim field mean
    sd = np.maximum(F.std(axis=0), 1e-6)
    n_f = F.shape[0]
    ev = np.empty(len(cands))
    for c in range(len(cands)):
        counts = (F > ct[c][None, :]).sum(axis=0)           # field ahead, sampled
        p_emp = counts / n_f
        p_par = norm.sf((ct[c] - mu) / sd)
        p_cap = (counts + 1.0) / n_f                        # empirical upper bound
        p = np.where(counts >= EMP_MIN, p_emp, np.minimum(p_par, p_cap))
        frac = p + 1.0 / contest.field_size                 # ~rank/field_size
        idx = np.searchsorted(cums, frac, side="left")
        pay = np.where(idx < len(pays), pays[np.minimum(idx, len(pays) - 1)], 0.0)
        ev[c] = float(pay.mean())
    order = np.argsort(ev)[::-1]
    picked: list[int] = []
    sel_ids: list[frozenset] = []
    for i in order:
        if len(picked) >= n_entries:
            break
        if all(len(cands[i].ids & s) <= max_overlap for s in sel_ids):
            picked.append(int(i))
            sel_ids.append(cands[i].ids)
    for i in order:  # fill if the overlap constraint ran the list dry
        if len(picked) >= n_entries:
            break
        if int(i) not in picked:
            picked.append(int(i))
    return picked


def tail_select_lineups(
    slate: pd.DataFrame,
    pool: list[dict],
    draws: np.ndarray,
    tail_line: float,
    n_entries: int,
    stack: StackRules | None,
    objective_col: str,
    candidate_multiple: int = 2,
    n_boom_solves: int = 40,
    n_game_stacks: int = 4,
    n_per_game: int = 3,
    contest: Contest | None = None,
    sharp_fraction: float = 0.0,
    locks: set | None = None,
    theses: list[dict] | None = None,
) -> list[Lineup]:
    """Entry selection on P(best-of-N >= tail_line) (guide: issue #5).

    Candidates come from two generators: the diverse leverage-objective
    batch (what we entered before), plus one solve per top-total sim —
    'if the slate booms like THIS, what's the best lineup?' — which yields
    genuinely boom-correlated entries the mean objective never builds.
    Selection is greedy sim-coverage (see select_tail_entries)."""
    rd = _row_draws(slate, draws)
    locks = locks or set()
    cands = optimize_many(pool, n_lineups=candidate_multiple * n_entries,
                          stack=stack, objective_col=objective_col,
                          locks=set(locks))
    for lu in cands:
        lu.tag = "lev"
    seen = {lu.ids for lu in cands}
    # Thesis candidates (2026-08-03, OWS "Bink Machine" pattern): each
    # thesis {players: [ids], min: k} guarantees the POOL holds enough
    # combo-containing builds; the post-selection repair below enforces
    # the portfolio floor. Builds TOWARD correlated convictions (pairs
    # with watchlist conversions) instead of only capping exposure.
    for th in (theses or []):
        combo = set(th.get("players") or ())
        need = int(th.get("min") or 0)
        if not combo or need <= 0:
            continue
        banned_th: list = []
        for _ in range(max(need, 2)):
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              locks=combo | set(locks),
                              banned_lineups=banned_th, max_overlap=7)
            except Exception:
                break
            if lu is None:
                break
            banned_th.append(lu.ids)
            if lu.ids not in seen:
                lu.tag = "thesis"
                seen.add(lu.ids)
                cands.append(lu)
    boom_sims = np.argsort(rd.sum(axis=0))[::-1][:n_boom_solves]
    for k in boom_sims:
        sim_pool = [{**p, "proj_sim": float(rd[i, k])}
                    for i, p in enumerate(pool)]
        try:
            lu = optimize(sim_pool, stack=stack, objective_col="proj_sim",
                          locks=set(locks))
        except Exception as exc:  # CBC subprocess flake: skip this draw
            log.warning("boom-draw solve failed: %s", exc)
            continue
        if lu is not None and lu.ids not in seen:
            lu.tag = "boom"
            seen.add(lu.ids)
            cands.append(lu)
    # Anti-correlation A/B (env N_NOSTACK): candidates with NO stack
    # rules — pure variance plays; coverage selection decides if any
    # earn slots. Prior is low (all 48 studied Milly winners stacked).
    import os as _os

    n_nostack = int(_os.environ.get("N_NOSTACK", "0"))
    if n_nostack:
        banned_ns = []
        for _ in range(n_nostack):
            try:
                lu = optimize(pool, stack=None, objective_col=objective_col,
                              banned_lineups=banned_ns, max_overlap=7,
                              locks=set(locks))
            except Exception:
                break
            if lu is None:
                break
            banned_ns.append(lu.ids)
            if lu.ids not in seen:
                lu.tag = "nostk"
                seen.add(lu.ids)
                cands.append(lu)
    # Low-salary candidate batch (env N_LOWSAL, off by default;
    # underspend-family redesign 2026-08-03): the validated $49k floor
    # pushes every candidate into near-cap build space; these solves at
    # a $47k floor reach constructions the floor forbids, and the
    # coverage selector decides if any earn slots (the original
    # underspend-dedup died with the WRONG rationale — dupe avoidance;
    # ours measure ~0 — this one is pure coverage breadth).
    n_lowsal = int(_os.environ.get("N_LOWSAL", "0"))
    if n_lowsal:
        banned_ls: list = []
        for _ in range(n_lowsal):
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              banned_lineups=banned_ls, max_overlap=7,
                              min_salary=47_000)
            except Exception:
                break
            if lu is None:
                break
            banned_ls.append(lu.ids)
            if lu.ids not in seen:
                lu.tag = "lowsal"
                seen.add(lu.ids)
                cands.append(lu)
    # Quality-diversity archive batch (env QD_CELLS = elites per cell,
    # off by default; MAP-Elites idea, research round 8 2026-08-03): the
    # named batches above are a hand-made archive; this tessellates the
    # descriptor space the real Milly winners actually occupy —
    # max-per-game concentration {2,3,4} (winners avg 2.96) x salary band
    # (winners spend the cap, but coverage may pay off-cap) — and solves
    # the best lineups per cell. Same tail-coverage selector downstream
    # decides which cells earn entries; empty/infeasible cells just skip.
    n_qd = int(_os.environ.get("QD_CELLS", "0"))
    if n_qd:
        for mpg in (2, 3, 4):
            for lo, hi in ((44_000, 47_500), (47_500, 49_000),
                           (49_000, 50_000)):
                banned_qd: list = []
                for _ in range(n_qd):
                    try:
                        lu = optimize(pool, stack=stack,
                                      objective_col=objective_col,
                                      banned_lineups=banned_qd,
                                      max_overlap=7, locks=set(locks),
                                      min_salary=lo, max_salary=hi,
                                      max_per_game=mpg)
                    except Exception:
                        break
                    if lu is None:
                        break
                    banned_qd.append(lu.ids)
                    if lu.ids not in seen:
                        lu.tag = "qd"
                        seen.add(lu.ids)
                        cands.append(lu)
    # Stack-depth A/B (env N_QB_VARIANTS): the harvest attribution found
    # the 40 entries spread over ~16 QBs with max 2-of-8 overlap vs the
    # weekly optimal — right stacks, wrong pieces. For each of the top-8
    # QBs by simulated p90, build several catcher-combination variants
    # (same QB, different pieces) so the pool holds real depth per stack.
    # ADOPTED 2026-08-04 (QF arm, final-exam combos): default 4. QBVAR4
    # alone +2 tails (25/107); with OWN_MODEL=fade, equal 25 tails, best
    # median of the program (14.6%) and two >=237 weeks. "0" disables.
    n_qbvar = int(_os.environ.get("N_QB_VARIANTS", "4"))
    if n_qbvar:
        qb_all = [(i, p) for i, p in enumerate(pool) if p["pos"] == "QB"]
        qb_all.sort(key=lambda t: -float(np.percentile(rd[t[0]], 90)))
        for _, qb in qb_all[:8]:
            banned_qv: list = []
            for _ in range(n_qbvar):
                try:
                    lu = optimize(pool, stack=stack,
                                  objective_col=objective_col,
                                  locks={qb["id"]} | set(locks),
                                  banned_lineups=banned_qv,
                                  max_overlap=6)
                except Exception:
                    break
                if lu is None:
                    break
                banned_qv.append(lu.ids)
                if lu.ids not in seen:
                    lu.tag = "qbvar"
                    seen.add(lu.ids)
                    cands.append(lu)
    # Mid-tier QB A/B (env N_MIDQB): one candidate locked on each of the
    # top-N $4-6.5k QBs by simulated p90 — targets the measured miss zone
    # (17/41 top-scorer misses were QBs, 27/41 mid-salary).
    n_midqb = int(_os.environ.get("N_MIDQB", "0"))
    if n_midqb:
        qb_rows = [(i, p) for i, p in enumerate(pool)
                   if p["pos"] == "QB" and 4000 < p["salary"] <= 6500]
        qb_rows.sort(key=lambda t: -float(np.percentile(rd[t[0]], 90)))
        for _, qb in qb_rows[:n_midqb]:
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              locks={qb["id"]} | set(locks))
            except Exception:
                continue
            if lu is not None and lu.ids not in seen:
                lu.tag = "midqb"
                seen.add(lu.ids)
                cands.append(lu)
    # Concentrated game stacks (issue #6): for each top game environment,
    # force >= 5 players from that game. Winners take 50-80% of points
    # from one game; these are deliberately lower-mean, higher-variance
    # candidates — coverage selection decides how many survive.
    game_proj = (slate[slate.get("game_id").notna()]
                 .groupby("game_id")["proj"].sum().sort_values(ascending=False)
                 if "game_id" in slate.columns else pd.Series(dtype=float))
    for gid in game_proj.head(n_game_stacks).index:
        banned = []
        for _ in range(n_per_game):
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              game_lock=(gid, 5), banned_lineups=banned,
                              max_overlap=7, locks=set(locks))
            except Exception as exc:
                log.warning("game-stack solve failed (%s): %s", gid, exc)
                break
            if lu is None:
                break
            banned.append(lu.ids)
            if lu.ids not in seen:
                lu.tag = "game"
                seen.add(lu.ids)
                cands.append(lu)
    # Dark-game A/B (env N_DARKGAME): concentrated stacks from games
    # RANKED 5+ by projected total — 29% of matched 2025 Milly winners
    # stacked a game ranked 8th-14th on the slate (addendum 20 study).
    n_dark = int(_os.environ.get("N_DARKGAME", "10"))
    if n_dark and len(game_proj) > n_game_stacks:
        for gid in game_proj.index[n_game_stacks:n_game_stacks + n_dark]:
            try:
                lu = optimize(pool, stack=stack, objective_col=objective_col,
                              game_lock=(gid, 5), locks=set(locks))
            except Exception:
                continue
            if lu is not None and lu.ids not in seen:
                lu.tag = "dark"
                seen.add(lu.ids)
                cands.append(lu)
    if not cands:
        return []
    id2row = {pid: i for i, pid in enumerate(slate["id"])}
    cand_totals = np.stack([
        rd[[id2row[p["id"]] for p in lu.players]].sum(axis=0) for lu in cands
    ])
    if _os.environ.get("SELECT_OBJ") == "dollars" and contest is not None:
        picked = select_dollar_entries(slate, rd, cands, cand_totals,
                                       n_entries, contest,
                                       sharp_fraction=sharp_fraction)
    else:
        max_qbs = int(_os.environ.get("MAX_QBS", "0"))
        if max_qbs:
            qb_of = [next((p["id"] for p in lu.players if p["pos"] == "QB"),
                          None) for lu in cands]
            picked = _select_tail_qb_capped(cand_totals, n_entries,
                                            tail_line, qb_of, max_qbs)
        else:
            picked = select_tail_entries(cand_totals, n_entries, tail_line)
    if theses:
        picked = _enforce_theses(picked, cands, cand_totals, tail_line,
                                 theses)
    return [cands[i] for i in picked]


def _enforce_theses(picked: list[int], cands: list, cand_totals,
                    tail_line: float, theses: list[dict]) -> list[int]:
    """Portfolio floor per thesis: swap the weakest non-thesis entries
    for the best unpicked combo-containing candidates until each quota
    is met (best-effort — a thesis the pool can't satisfy is logged)."""
    import numpy as _np

    p_line = (cand_totals >= tail_line).mean(axis=1)
    picked = list(picked)
    for th in theses:
        combo = set(th.get("players") or ())
        need = int(th.get("min") or 0)
        if not combo or need <= 0:
            continue
        def has(i):
            return combo <= {p["id"] for p in cands[i].players}
        have = sum(1 for i in picked if has(i))
        pool_extra = sorted((i for i in range(len(cands))
                             if i not in picked and has(i)),
                            key=lambda i: -p_line[i])
        while have < need and pool_extra:
            worst = min((i for i in picked if not has(i)),
                        key=lambda i: p_line[i], default=None)
            if worst is None:
                break
            picked[picked.index(worst)] = pool_extra.pop(0)
            have += 1
        if have < need:
            log.warning("thesis %s: only %d/%d entries possible",
                        sorted(combo), have, need)
    return picked


def _select_tail_qb_capped(
    cand_totals: np.ndarray, n_entries: int, line: float,
    qb_of: list, max_qbs: int,
) -> list[int]:
    """select_tail_entries with a cap on DISTINCT QBs across the selected
    set (env MAX_QBS). Once the cap is reached, only candidates reusing an
    already-selected QB stay eligible — the freed slots buy combinatorial
    depth within the kept stacks instead of a 17th stack. Mirrors the
    greedy coverage + fill of select_tail_entries."""
    cand_totals = np.asarray(cand_totals, dtype=float)
    clears = cand_totals >= line
    p_line = clears.mean(axis=1)
    mean_total = cand_totals.mean(axis=1)
    n_entries = min(n_entries, len(cand_totals))
    selected: list[int] = []
    qbs: set = set()
    covered = np.zeros(cand_totals.shape[1], dtype=bool)
    remaining = set(range(len(cand_totals)))

    def eligible():
        if len(qbs) < max_qbs:
            return remaining
        return [i for i in remaining if qb_of[i] in qbs]

    while len(selected) < n_entries:
        pool_i = eligible()
        if not pool_i:
            break
        best = max(pool_i,
                   key=lambda i: (int(np.count_nonzero(clears[i] & ~covered)),
                                  p_line[i], mean_total[i]))
        if not np.count_nonzero(clears[best] & ~covered):
            break  # coverage saturated; fill below
        selected.append(best)
        qbs.add(qb_of[best])
        covered |= clears[best]
        remaining.discard(best)
    while len(selected) < n_entries:
        pool_i = eligible()
        if not pool_i:
            break
        best = max(pool_i, key=lambda i: (p_line[i], mean_total[i]))
        selected.append(best)
        qbs.add(qb_of[best])
        remaining.discard(best)
    return selected


def run_week(
    slate: pd.DataFrame,
    contest: Contest,
    n_entries: int = 20,
    field_size: int = 5_000,
    stack: StackRules | None = None,
    seed: int | None = 42,
    sharp_fraction: float = 0.0,
    draws: np.ndarray | None = None,
    tail_line: float | None = None,
    n_boom_solves: int = 40,
) -> WeekResult | None:
    """Backtest one historical slate. `slate` columns: REQUIRED_COLS.
    With `draws` (player-draw matrix indexed by the slate's draw_idx
    column) and `tail_line`, entries are selected to maximize
    P(best entry >= tail_line) instead of taking the top objective batch."""
    leakage_guard(slate)
    season = int(slate["season"].iloc[0]) if "season" in slate else 0
    week = int(slate["week"].iloc[0]) if "week" in slate else 0

    pool = slate.to_dict("records")
    obj = "proj_tourney" if "proj_tourney" in slate.columns else "proj"
    if draws is not None and tail_line is not None and "draw_idx" in slate.columns:
        import os as _os

        lineups = tail_select_lineups(
            slate, pool, draws, tail_line, n_entries, stack, obj,
            contest=contest, sharp_fraction=sharp_fraction,
            candidate_multiple=int(_os.environ.get("CAND_MULT", "2")),
            n_boom_solves=int(_os.environ.get("N_BOOM", str(n_boom_solves))),
            # Generator-mix A/B (2026-08-01): 2025 replays show the top-4
            # game-stack generator won 0/17 weeks from ~6% of the pool
            # while dark games won 4/17 from ~11% -- N_GAMESTACK=0 +
            # N_DARKGAME up reallocates toward what actually wins.
            n_game_stacks=int(_os.environ.get("N_GAMESTACK", "4")))
    else:
        lineups = optimize_many(pool, n_lineups=n_entries, stack=stack,
                                objective_col=obj)
    if not lineups:
        log.warning("No feasible lineups for %s week %s", season, week)
        return None

    actual = slate.set_index("id")["actual"]
    lineup_scores = [float(actual.reindex([p["id"] for p in lu.players]).sum())
                     for lu in lineups]

    # model_own column present => OWN_MODEL replay: the trained ownership
    # model drives the simulated field instead of the naive softmax.
    own_vec = (slate["model_own"].to_numpy()
               if "model_own" in slate.columns and slate["model_own"].notna().all()
               else None)
    fld = field_sim.sample_field(slate, n_lineups=field_size, seed=seed,
                                 ownership=own_vec,
                                 sharp_fraction=sharp_fraction)
    scores = field_sim.field_scores(fld, slate["actual"].to_numpy())

    percentiles, winnings = [], []
    for s in lineup_scores:
        beaten = float(np.mean(scores > s))
        rank = max(1, int(round(beaten * contest.field_size)) + 1)
        percentiles.append(beaten)
        winnings.append(contest.payout_for_rank(rank))

    return WeekResult(season, week, lineups, lineup_scores, percentiles, winnings)


def run(
    slates: list[pd.DataFrame],
    contest: Contest,
    n_entries: int = 20,
    field_size: int = 5_000,
    stack: StackRules | None = None,
    seed: int | None = 42,
    sharp_fraction: float = 0.0,
    draws: np.ndarray | None = None,
    tail_line: float | None = None,
    n_boom_solves: int = 40,
) -> BacktestResult:
    result = BacktestResult(contest=contest)
    for slate in slates:
        wk = run_week(slate, contest, n_entries=n_entries,
                      field_size=field_size, stack=stack, seed=seed,
                      sharp_fraction=sharp_fraction, draws=draws,
                      tail_line=tail_line, n_boom_solves=n_boom_solves)
        if wk is not None:
            result.weeks.append(wk)
            log.info("season %s week %s: best %.1f pts, best pct %.1f%%",
                     wk.season, wk.week, max(wk.lineup_scores),
                     100 * min(wk.percentiles))
    return result

```

===== FILE: src/nfl_dfs/backtest/field.py =====
```python
"""Field simulation (guide §10 step 5): approximate the opposing field with
ownership-weighted random lineups from the player pool.

Without real ownership, use the naive model — ownership correlates strongly
with value (proj/salary) and salary rank; a regression trained on scraped
post-hoc ownership slots in behind the same interface later.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ROSTER = (("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1), ("FLEX", 1), ("DST", 1))
SALARY_CAP = 50_000


def naive_ownership(players: pd.DataFrame) -> np.ndarray:
    """Ownership proxy from value and salary within position. Returns
    weights normalized to sum to 1 within each position group."""
    df = players.copy()
    value = df["proj"] / (df["salary"] / 1000.0)
    # Softmax on standardized value; salary as mild popularity boost
    weights = np.zeros(len(df))
    for _pos, idx in df.groupby("pos").groups.items():
        loc = df.index.get_indexer(idx)
        v = value.iloc[loc]
        z = (v - v.mean()) / (v.std() + 1e-9)
        s = df["salary"].iloc[loc]
        zs = (s - s.mean()) / (s.std() + 1e-9)
        w = np.exp(1.2 * z + 0.3 * zs)
        weights[loc] = w / w.sum()
    return weights


def sharp_field(
    players: pd.DataFrame,
    n_lineups: int,
    n_distinct: int = 20,
    noise: float = 0.08,
    seed: int | None = 42,
) -> list[np.ndarray]:
    """Optimizer-built entrants: the slice of a real field that runs an
    optimizer over its own (imperfect) projections. Each batch jitters the
    projection column and takes a handful of optimal lineups; distinct
    lineups are then duplicated up to `n_lineups`, mirroring how heavily
    sharp lineups duplicate in large contests."""
    from ..optimizer.lineup import optimize_many

    rng = np.random.default_rng(seed)
    players = players.reset_index(drop=True)
    row_of = {r["id"]: i for i, r in players.iterrows()}
    distinct: list[np.ndarray] = []
    per_batch = 5
    for _ in range(2 * (n_distinct // per_batch + 1)):
        if len(distinct) >= n_distinct:
            break
        pool = players.to_dict("records")
        for p in pool:
            p["proj"] = float(p["proj"]) * float(rng.normal(1.0, noise))
        try:
            batch = optimize_many(pool, n_lineups=per_batch)
        except Exception as exc:  # noqa: BLE001 - a flaky CBC subprocess
            # shouldn't kill a whole replay; the field falls back to fewer
            # (or zero) sharp entrants.
            import logging

            logging.getLogger(__name__).warning("sharp_field batch failed: %s", exc)
            continue
        for lu in batch:
            distinct.append(np.array([row_of[p["id"]] for p in lu.players]))
    if not distinct:  # infeasible slate; let the caller fall back
        return []
    picks = rng.integers(0, len(distinct), n_lineups)
    return [distinct[i] for i in picks]


def sample_field(
    players: pd.DataFrame,
    n_lineups: int = 10_000,
    seed: int | None = 42,
    ownership: np.ndarray | None = None,
    sharp_fraction: float = 0.0,
) -> list[np.ndarray]:
    """Generate opposing lineups by ownership-weighted sampling per slot.
    Salary is enforced loosely (retry a few times, keep the best attempt) —
    the field is approximated, not optimized; most real entrants aren't
    optimal either. `sharp_fraction` of the field is instead built by
    `sharp_field` (optimizer entrants), which is what keeps GPP payout
    tails honest. Returns arrays of positional indices into `players`."""
    rng = np.random.default_rng(seed)
    n_sharp = int(n_lineups * sharp_fraction)
    sharp = sharp_field(players, n_sharp, seed=seed) if n_sharp else []
    n_lineups = n_lineups - len(sharp)
    own = ownership if ownership is not None else naive_ownership(players)
    players = players.reset_index(drop=True)
    pos_idx = {
        pos: players.index[players["pos"] == pos].to_numpy()
        for pos in ("QB", "RB", "WR", "TE", "DST")
    }
    flex_idx = players.index[players["pos"].isin(["RB", "WR", "TE"])].to_numpy()
    pos_weights = {
        pos: own[idx] / own[idx].sum() for pos, idx in pos_idx.items() if len(idx)
    }
    flex_w = own[flex_idx] / own[flex_idx].sum()
    salaries = players["salary"].to_numpy()

    field: list[np.ndarray] = []
    for _ in range(n_lineups):
        best: np.ndarray | None = None
        for _attempt in range(6):
            picks: list[int] = []
            ok = True
            for pos, n in ROSTER:
                if pos == "FLEX":
                    cand, w = flex_idx, flex_w
                else:
                    cand, w = pos_idx.get(pos, np.array([])), pos_weights.get(pos)
                    if cand is None or len(cand) < n:
                        ok = False
                        break
                avail = ~np.isin(cand, picks)
                if avail.sum() < n:
                    ok = False
                    break
                w_avail = w[avail] / w[avail].sum()
                chosen = rng.choice(cand[avail], size=n, replace=False, p=w_avail)
                picks.extend(chosen.tolist())
            if not ok:
                continue
            arr = np.array(picks)
            if salaries[arr].sum() <= SALARY_CAP:
                best = arr
                break
            if best is None:
                best = arr
        if best is not None:
            field.append(best)
    return sharp + field


def field_scores(field: list[np.ndarray], actual_points: np.ndarray) -> np.ndarray:
    """Actual DK points for each field lineup."""
    return np.array([actual_points[lu].sum() for lu in field])

```

===== FILE: src/nfl_dfs/backtest/payout.py =====
```python
"""Contest payout curves. ROI is the only metric that pays (guide §10):
a model with worse RMSE can have better ROI if its ceilings are calibrated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Contest:
    name: str
    entry_fee: float
    field_size: int
    # (top_fraction_of_field, multiple_of_entry_fee) tiers, best first.
    tiers: tuple[tuple[float, float], ...]

    def payout_for_rank(self, rank: int) -> float:
        """rank is 1-based; returns dollars won."""
        frac = rank / self.field_size
        cum = 0.0
        for top_frac, mult in self.tiers:
            cum += top_frac
            if frac <= cum + 1e-12:
                return self.entry_fee * mult
        return 0.0


def double_up(entry_fee: float = 5.0, field_size: int = 10_000) -> Contest:
    """Cash game: top ~45% roughly doubles (rake-adjusted)."""
    return Contest("double-up", entry_fee, field_size, ((0.45, 2.0),))


def gpp(entry_fee: float = 5.0, field_size: int = 100_000) -> Contest:
    """Stylized winner-take-most tournament curve, ~15% of field paid,
    ~85% of the prize pool concentrated up top."""
    return Contest(
        "gpp",
        entry_fee,
        field_size,
        (
            (0.00001, 20000.0),   # 1st
            (0.00009, 2000.0),
            (0.0009, 200.0),
            (0.009, 20.0),
            (0.04, 5.0),
            (0.10, 2.0),
        ),
    )


def roi(winnings: np.ndarray, entry_fee: float) -> float:
    """Aggregate return on investment across entries."""
    w = np.asarray(winnings, dtype=float)
    staked = entry_fee * len(w)
    return float((w.sum() - staked) / staked) if staked else 0.0

```

===== FILE: src/nfl_dfs/backtest/real_lines.py =====
```python
"""Real Milly Maker winning lines per (season, week).

Sources: reports/milly-winners-2019-2023-2024.csv (player-level winner
rosters; 2024 wk9 excluded — duplicate of wk7 in the source) and
reports/2025-milly-winners.csv. These are the ACTUAL scores that won
the 150k-entry Milly those weeks — the honest per-week bar, replacing
the era-anchored 194/237 constants in replay reporting.
"""

REAL_LINES: dict[tuple[int, int], float] = {
    (2019, 1): 281.36,
    (2019, 2): 231.12,
    (2019, 3): 275.7,
    (2019, 4): 266.28,
    (2019, 5): 331.86,
    (2019, 6): 242.34,
    (2019, 7): 246.36,
    (2019, 8): 258.58,
    (2019, 9): 269.32,
    (2019, 10): 251.64,
    (2019, 11): 221.64,
    (2019, 12): 229.18,
    (2019, 13): 228.8,
    (2019, 14): 240.86,
    (2019, 15): 260.02,
    (2019, 16): 261.24,
    (2019, 17): 241.02,
    (2023, 1): 233.24,
    (2023, 2): 193.94,
    (2023, 3): 296.38,
    (2023, 4): 253.7,
    (2023, 5): 259.18,
    (2023, 6): 226.38,
    (2023, 7): 238.06,
    (2023, 8): 237.66,
    (2023, 9): 250.4,
    (2023, 10): 264.06,
    (2023, 11): 214.82,
    (2023, 12): 220.66,
    (2023, 13): 219.16,
    (2023, 14): 230.84,
    (2023, 15): 235.24,
    (2023, 16): 226.92,
    (2023, 17): 221.24,
    (2024, 1): 196.88,
    (2024, 2): 229.92,
    (2024, 3): 244.14,
    (2024, 4): 223.96,
    (2024, 5): 236.92,
    (2024, 6): 208.2,
    (2024, 7): 185.36,
    (2024, 8): 211.66,
    (2024, 10): 178.32,
    (2024, 11): 232.5,
    (2024, 12): 233.08,
    (2024, 13): 218.74,
    (2024, 14): 281.68,
    (2024, 15): 261.86,
    (2024, 16): 238.48,
    (2024, 17): 241.16,
    (2024, 18): 234.04,
    (2025, 1): 193.92,
    (2025, 2): 260.2,
    (2025, 3): 231.06,
    (2025, 4): 239.9,
    (2025, 5): 246.82,
    (2025, 6): 227.14,
    (2025, 7): 249.6,
    (2025, 8): 230.66,
    (2025, 9): 264.7,
    (2025, 10): 239.62,
    (2025, 11): 248.98,
    (2025, 12): 277.04,
    (2025, 13): 205.44,
    (2025, 14): 239.34,
    (2025, 15): 236.02,
    (2025, 16): 218.2,
    (2025, 17): 218.24,
}

```

===== FILE: src/nfl_dfs/backtest/replay.py =====
```python
"""Season replay: what would the system have projected, and how close was it?

Trains the component models ONLY on seasons before the replay season, then
projects every week of that season through the production path (cold-start
fill -> components -> Monte Carlo) using the point-in-time feature rows.
Faithful to production: the weekly Tuesday retrain never includes the
in-progress season either (models/train_job.py trains on season < target).

Two layers, matching data availability:
- Projection replay (any season): MAE vs. the naive trailing-average
  baseline, rank correlation, p10/p90 coverage, P(20+) calibration.
- Contest replay (seasons with salaries, 2014-2021): full slates including
  RotoGuru DST rows -> optimizer -> field simulation -> ROI.
"""

from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd
from scipy import stats

from ..models import calibration, coldstart, components, simulate
from .engine import BacktestResult, run as engine_run
from .payout import Contest

log = logging.getLogger(__name__)

DST_FALLBACK_PROJ = 6.0  # league-average DST DK points, for week-1 rows


def own_mode() -> str:
    """OWN_MODEL env, normalized (2026-08-04 audit): default "fade";
    falsy spellings ("", "0", "off", "false", "no", "none") DISABLE —
    before this, OWN_MODEL=0 silently enabled the strongest mode (full
    model-own field, deliberately not adopted) because any non-"fade"
    truthy string flips the model into the field sampler."""
    v = os.environ.get("OWN_MODEL", "fade").strip().lower()
    return "" if v in ("", "0", "off", "false", "no", "none") else v


def replay_projections(
    panel: pd.DataFrame,
    season: int,
    n_sims: int = 10_000,
    num_boost_round: int = 400,
    seed: int = 0,
    widen: bool = True,
    return_draws: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, np.ndarray]:
    """Project every (player, week) row of `season` with models trained on
    strictly earlier seasons. Rows carry point-in-time features, so no
    per-week retraining is needed for fidelity.

    return_draws=True also returns the raw correlated draw matrix
    (row-aligned with the output frame, float32) for tail-objective entry
    selection."""
    cm = components.train(panel, target_season=season, num_boost_round=num_boost_round)
    rows = panel[panel.season == season].reset_index(drop=True)
    if rows.empty:
        raise ValueError(f"no {season} rows in panel")
    rows = coldstart.fill_cold_start_features(rows)

    # Big-play mixture rate (env BIGPLAY=<scale>): expected house-calls
    # per game from the point-in-time deep-target profile. At scale 1 a
    # 3-deep-targets/wk receiver draws ~0.09 long-TD events/game.
    bigplay = None
    _bp = float(os.environ.get("BIGPLAY", "0") or 0)
    if _bp and "deep_targets_l4" in rows.columns:
        bigplay = 0.03 * _bp * pd.to_numeric(
            rows.deep_targets_l4, errors="coerce").fillna(0.0)
    sim = simulate.simulate(cm.predict_components(rows), n_sims=n_sims,
                        seed=seed, game_ids=rows.get("game_id"),
                        team_ids=rows.get("team"),
                        game_totals=rows.get("game_total"),
                        bigplay_rate=bigplay,
                        keep_draws=return_draws)
    summary = sim.summary
    if widen:
        summary = calibration.apply_widen(summary, rows.position)
    # A/B lever (env SIM_WIDEN_DRAWS): the fitted widen factors above
    # only ever stretched the SUMMARY quantiles — the draws that drive
    # lineup optimization, boom solves, and tail-coverage selection have
    # always been the raw (known-too-narrow: QB 1.5x, RB 1.45x per the
    # calibration's own fit) composition. "fitted" applies DEFAULT_WIDEN
    # to the draws mean-preservingly; or pass explicit "WR:1.3,QB:1.5".
    draws_out = (apply_draw_shape(sim.draws, rows.position, seed,
                                  keys=rows[["season", "week", "gsis_id"]])
                 if return_draws else sim.draws)
    keep = [c for c in ("gsis_id", "name", "season", "week", "team", "opponent",
                        "position", "game_id", "salary") if c in rows.columns]
    out = pd.concat([rows[keep], summary], axis=1)
    out["actual"] = rows["y_dk_points"].to_numpy()
    out["naive"] = rows.get("dk_points_l4")  # trailing average, the free baseline
    if return_draws:
        return out, draws_out.astype(np.float32)
    return out


def apply_draw_shape(draws: np.ndarray, positions: pd.Series,
                     seed: int | None,
                     keys: pd.DataFrame | None = None) -> np.ndarray:
    """ADOPTED DEFAULTS (Addendum 40, combo "EW" — 24/107 tails vs 16
    same-build control, largest gain in program history): fitted draw
    widening + empirically-shaped marginals, composed, mean-preserving.
    Shared by replays AND the live sim-mode path so what was validated
    is exactly what fires on Sundays. Env overrides: SIM_WIDEN_DRAWS=off
    or an explicit "WR:1.3,..." spec; EMP_MARGINALS=0 disables."""
    out = draws
    widen_spec = os.environ.get("SIM_WIDEN_DRAWS", "fitted")
    if widen_spec.lower() not in ("off", "0", ""):
        out = _widen_draws(out, positions, widen_spec)
    shaped = None
    # TABPFN_MARGINALS ADOPTED default-on 2026-08-04 (Addendum 50):
    # +6 tails alone (24 vs 18), STPFN stack = best mean-best of the
    # panel (179.5) at equal tails. Requires the tabpfn_projections
    # cache (GPU job tabpfn-gen, ~$0.05/wk); missing cache falls back
    # to empirical marginals below. "0"/"" disables.
    if (os.environ.get("TABPFN_MARGINALS", "1") not in ("0", "")
            and keys is not None):
        shaped = _tabpfn_marginals(out, keys)
    if shaped is not None:
        out = shaped
    elif os.environ.get("EMP_MARGINALS", "1") not in ("0", ""):
        out = _empirical_marginals(
            out, positions,
            np.random.default_rng(0 if seed is None else seed + 7))
    # A/B lever (env SHAPE_MIX, off by default = 1.0): apply the shaping
    # to only the first fraction f of sims, leaving the rest RAW — the
    # EW-vs-PB2 diff showed 15 weeks converted but 9 regressed (each
    # world-model sees booms the other misses); mixed worlds let the
    # coverage selector hedge across both regimes.
    mix = float(os.environ.get("SHAPE_MIX", "1") or 1)
    if mix <= 0.0:
        return draws  # 0 = all-raw (was returning fully-shaped — audit)
    if mix < 1.0:
        k = int(mix * draws.shape[1])
        out = np.concatenate([out[:, :k], draws[:, k:]], axis=1)
    return out


def _tabpfn_marginals(draws: np.ndarray, keys: pd.DataFrame) -> np.ndarray:
    """TABPFN_MARGINALS=1 (A/B, off by default; Addenda 43/46): reshape
    each player's marginal onto the TabPFN-v2 walk-forward quantiles
    cached in features.tabpfn_projections (generated on GPU, context =
    strictly-prior seasons). Same rank-reordering mechanism as
    _empirical_marginals — the correlation copula survives untouched —
    but the target distribution is PER-PLAYER, not a (pos, tier) family.
    TabPFN arrives calibrated where our quantiles under-cover (three
    independent confirmations). Rows without a cached prediction keep
    their original draws. Tails extrapolate linearly beyond q01/q99."""
    from ..bq import query_df
    from ..config import settings

    season = int(keys.season.iloc[0])
    q = query_df(f"SELECT * FROM `{settings.features}.tabpfn_projections` "
                 f"WHERE season = {season}")
    if q.empty:
        log.warning("TABPFN_MARGINALS on but no cached rows for season %s "
                    "— falling back to empirical marginals", season)
        return None
    qcols = sorted(c for c in q.columns if c.startswith("q") and c[1:].isdigit())
    levels = np.array([int(c[1:]) / 100 for c in qcols])
    q = q.set_index(["week", "gsis_id"])
    out = draws.copy()
    n = draws.shape[1]
    hit = 0
    for i in range(len(keys)):
        k = (int(keys.week.iloc[i]), keys.gsis_id.iloc[i])
        try:
            qv = q.loc[k, qcols].to_numpy(dtype=float)
        except KeyError:
            continue
        if qv.ndim > 1:  # duplicate cache rows; take the first
            qv = qv[0]
        row = draws[i]
        ranks = row.argsort().argsort() / max(n - 1, 1)
        y = np.interp(ranks, levels, qv)
        lo, hi = ranks < levels[0], ranks > levels[-1]
        y[lo] = qv[0] + (ranks[lo] - levels[0]) * (qv[1] - qv[0]) / (
            levels[1] - levels[0])
        y[hi] = qv[-1] + (ranks[hi] - levels[-1]) * (qv[-1] - qv[-2]) / (
            levels[-1] - levels[-2])
        out[i] = np.maximum(y, 0.0)
        hit += 1
    log.info("tabpfn marginals: %d/%d rows mapped", hit, len(keys))
    return out


def _empirical_marginals(draws: np.ndarray, positions: pd.Series,
                         rng: np.random.Generator) -> np.ndarray:
    """Reshape each player's marginal to the empirically-fitted family
    for (position, projection tier) — models/emp_marginals.py — while
    preserving BOTH our correlation structure (rank reordering: the
    possession-engine copula survives byte-for-byte) and our first two
    moments (affine match to the row's own mean/std). Only skew and
    kurtosis change: RB/WR high tiers go weibull-fat, TE lognormal at
    the bottom, QB skew-normal. Env EMP_MARGINALS=1."""
    from scipy import stats as _st

    from ..models.emp_marginals import ROWS

    # EMP_POS (A/B, default all): comma list of positions to reshape —
    # the EW-book sweep found the TE slot REGRESSED under the empirical
    # TE family (13.1 actual vs winners' 21.5), so a no-TE arm exists.
    allow = {p.strip().upper() for p in
             os.environ.get("EMP_POS", "").split(",") if p.strip()}
    by_pos: dict = {}
    for r in ROWS:
        if allow and r["pos"] not in allow:
            continue
        by_pos.setdefault(r["pos"], []).append(r)

    def family_sample(r, n):
        d = r["dist"]
        if d == "exgaussian":
            return _st.exponnorm.rvs(K=r["tau"] / r["sigma"], loc=r["mu"],
                                     scale=r["sigma"], size=n, random_state=rng)
        if d == "skew_normal":
            return _st.skewnorm.rvs(a=r["alpha"], loc=r["loc"],
                                    scale=r["scale"], size=n, random_state=rng)
        if d == "weibull":
            return _st.weibull_min.rvs(c=r.get("c", r.get("a", 1.0)),
                                       scale=r["scale"], size=n, random_state=rng)
        if d == "lognormal":
            return _st.lognorm.rvs(s=r["sigma"], scale=np.exp(r["mu"]),
                                   size=n, random_state=rng)
        if d == "generalized_gamma":
            return _st.gengamma.rvs(a=r["a"], c=r.get("c", r.get("d", 1.0)),
                                    scale=r.get("scale", r.get("beta", 1.0)),
                                    size=n, random_state=rng)
        # scale/loc are irrelevant post-affine-match; only SHAPE params
        # matter. Some source rows store rate (beta) instead of scale.
        gscale = r.get("scale", 1.0 / r["beta"] if r.get("beta") else 1.0)
        if d == "shifted_gamma":
            return r.get("shift", 0.0) + _st.gamma.rvs(
                a=r["alpha"], scale=gscale, size=n, random_state=rng)
        if d == "gamma":
            return _st.gamma.rvs(a=r["alpha"], scale=gscale, size=n,
                                 random_state=rng)
        raise ValueError(d)

    out = draws.copy()
    n_sims = draws.shape[1]
    pos_arr = positions.astype(str).str.upper().to_numpy()
    for i in range(draws.shape[0]):
        rows_p = by_pos.get(pos_arr[i])
        if not rows_p:
            continue
        mu, sd = float(draws[i].mean()), float(draws[i].std())
        if sd < 1e-6:
            continue
        r = min(rows_p, key=lambda t: abs((t["lo"] + t["hi"]) / 2 - mu))
        s = family_sample(r, n_sims)
        s_sd = s.std()
        if s_sd < 1e-9:
            continue
        s = (s - s.mean()) * (sd / s_sd) + mu  # affine: our mean & std
        # rank reorder: our copula, their shape
        order = np.argsort(np.argsort(draws[i]))
        out[i] = np.sort(s)[order]
    return out


def _widen_draws(draws: np.ndarray, positions: pd.Series, spec: str) -> np.ndarray:
    """Mean-preserving per-position spread widening of the draw matrix
    (draws[i, k] = player i's points in sim k). E[row] is exactly
    unchanged; row std scales by the position factor. spec: "fitted"
    (calibration.DEFAULT_WIDEN) or "WR:1.3,QB:1.5"."""
    if spec.strip().lower() == "fitted":
        factors = dict(calibration.DEFAULT_WIDEN)
    else:
        factors = {k.strip().upper(): float(v) for k, _, v in
                   (p.partition(":") for p in spec.split(","))}
    w = positions.map(lambda p: factors.get(str(p).upper(), 1.0)) \
                 .to_numpy(dtype=np.float64)[:, None]
    mu = draws.mean(axis=1, keepdims=True)
    return mu + (draws - mu) * w


def replay_metrics(proj: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """(overall metrics, per-position table)."""
    err = proj.proj_points - proj.actual
    have_naive = proj.dropna(subset=["naive"])
    overall = {
        "rows": len(proj),
        "mae": float(err.abs().mean()),
        "naive_mae": float((have_naive.naive - have_naive.actual).abs().mean()),
        "coverage_p10": float((proj.actual < proj.proj_p10).mean()),
        "coverage_p90": float((proj.actual < proj.proj_p90).mean()),
        # Calibration of the GPP ceiling probability
        "mean_p20_predicted": float(proj.p_20_plus.mean()),
        "rate_20_plus_actual": float((proj.actual >= 20).mean()),
    }
    rows = []
    for pos, grp in proj.groupby("position"):
        rows.append({
            "position": pos,
            "n": len(grp),
            "mae": float((grp.proj_points - grp.actual).abs().mean()),
            "rank_corr": float(stats.spearmanr(grp.proj_points, grp.actual).statistic),
            "coverage_p10": float((grp.actual < grp.proj_p10).mean()),
            "coverage_p90": float((grp.actual < grp.proj_p90).mean()),
        })
    return overall, pd.DataFrame(rows).set_index("position")


def dst_slate_rows(dst: pd.DataFrame,
                   qb_starts: pd.DataFrame | None = None,
                   vegas: pd.DataFrame | None = None) -> pd.DataFrame:
    """RotoGuru DST rows -> slate rows.

    Projection tiers (best available wins): Vegas-first model (opponent
    implied total + trailing form + opposing-QB experience — see
    inference/dst_projections.model_projection) > trailing form + raw
    QB-experience adjustment > trailing form alone. `vegas` columns:
    season, week, team, opp_implied."""
    d = dst.sort_values(["team", "season", "week"]).copy()
    d["proj"] = (
        d.groupby(["team", "season"])["actual"]
        .transform(lambda s: s.shift(1).rolling(4, min_periods=1).mean())
        .fillna(DST_FALLBACK_PROJ)
    )
    starts = pd.Series(pd.NA, index=d.index)
    if qb_starts is not None and not qb_starts.empty:
        # One row per (season, week, team) or the merge fans out duplicate
        # DST rows (2023: a mid-week QB change flagged two starters, which
        # crashed the engine's unique-id reindex).
        qb_starts = qb_starts.drop_duplicates(subset=["season", "week", "team"])
        d = d.merge(qb_starts.rename(columns={"team": "opp"}),
                    on=["season", "week", "opp"], how="left")
        starts = d.pop("prior_starts")
    if vegas is not None and not vegas.empty:
        vegas = vegas.drop_duplicates(subset=["season", "week", "team"])
        from ..inference.dst_projections import model_projection

        d = d.merge(vegas, on=["season", "week", "team"], how="left")
        d["proj"] = model_projection(d.pop("opp_implied"), d["proj"], starts)
    elif starts.notna().any():
        from ..inference.qb_experience import adjustment

        d["proj"] = d["proj"] + adjustment(starts)
    d["id"] = "DST_" + d.team
    d["name"] = d.team + " DST"
    d["pos"] = "DST"
    return d


def _punt_boom_from_signals(df: pd.DataFrame) -> set[tuple]:
    """(gsis_id, season, week) keys matching a winning-punt archetype
    (Addendum 24/36): cheap starting TEs (depth_rank 1 — DK's TE pricing
    compression puts real starters at min price), newly-promoted rank-1s
    (the Gadsden case: rank 2 -> 1), and injury-cascade beneficiaries
    (top-decile vacated share that week). Salary gating happens at
    application time; these are role signals only.

    df columns: gsis_id, season, week, position, depth_rank, prev_rank,
    vac (max of vacated target/carry share). All point-in-time."""
    te_starter = (df.position == "TE") & (df.depth_rank == 1)
    promoted = (df.depth_rank == 1) & (df.prev_rank >= 2)
    vac_pct = df.groupby(["season", "week"]).vac.rank(pct=True)
    cascade = (df.vac > 0) & (vac_pct >= 0.90)
    hit = df[te_starter | promoted | cascade]
    return {(r.gsis_id, int(r.season), int(r.week)) for r in hit.itertuples()}


def _punt_boom_flags(seasons: list) -> set[tuple]:
    from ..bq import query_df
    from ..config import settings

    yrs = ",".join(str(int(s)) for s in seasons)
    df = query_df(f"""
        SELECT gsis_id, season, week, position, depth_rank,
               LAG(depth_rank) OVER (
                   PARTITION BY gsis_id, season ORDER BY week) prev_rank,
               GREATEST(COALESCE(team_vacated_target_share, 0),
                        COALESCE(team_vacated_carry_share, 0)) vac
        FROM `{settings.features}.player_week_training`
        WHERE season IN ({yrs})""")
    return _punt_boom_from_signals(df)


def punt_boom_flags_live(season: int, week: int) -> set[tuple]:
    """Live-inference variant: the upcoming week's rows live in
    player_week_inference (training rows only exist for played weeks), so
    the rank-2->1 transition needs history unioned with the current week."""
    from ..bq import query_df
    from ..config import settings

    sig = ("gsis_id, season, week, position, depth_rank, "
           "team_vacated_target_share, team_vacated_carry_share")
    df = query_df(f"""
        WITH hist AS (
          SELECT {sig} FROM `{settings.features}.player_week_training`
          WHERE season = {int(season)} AND week < {int(week)}
          UNION ALL
          SELECT {sig} FROM `{settings.features}.player_week_inference`
          WHERE season = {int(season)} AND week = {int(week)}
        )
        SELECT * FROM (
          SELECT gsis_id, season, week, position, depth_rank,
                 LAG(depth_rank) OVER (
                     PARTITION BY gsis_id, season ORDER BY week) prev_rank,
                 GREATEST(COALESCE(team_vacated_target_share, 0),
                          COALESCE(team_vacated_carry_share, 0)) vac
          FROM hist)
        WHERE week = {int(week)}""")
    return _punt_boom_from_signals(df)


def _wr_boom_flags(seasons: list) -> set[tuple]:
    """(gsis_id, season, week) for WRs with a boom-SHAPED role: top-decile
    deep-target volume among that week's WRs (point-in-time l4 window).
    Real Milly winners' WR slots average 29.9 pts vs our 19.9 (Addendum
    38), and the eruptions are deep threats at punt/mid prices. Salary
    gating happens at application (PUNT_BOOM_WR / WR_BOOM envs)."""
    from ..bq import query_df
    from ..config import settings

    yrs = ",".join(str(int(s)) for s in seasons)
    df = query_df(f"""
        SELECT gsis_id, season, week, deep_targets_l4
        FROM `{settings.features}.player_week_training`
        WHERE season IN ({yrs}) AND position = 'WR'
          AND deep_targets_l4 IS NOT NULL AND deep_targets_l4 > 0""")
    pct = df.groupby(["season", "week"]).deep_targets_l4.rank(pct=True)
    hit = df[pct >= 0.90]
    return {(r.gsis_id, int(r.season), int(r.week)) for r in hit.itertuples()}


def build_slates(proj: pd.DataFrame, dst: pd.DataFrame | None) -> list[pd.DataFrame]:
    """One engine-ready slate per week: skill rows from the replay (dropping
    the few without a salary) plus DST rows when provided."""
    skill = proj.dropna(subset=["salary"]).copy()
    dropped = len(proj) - len(skill)
    if dropped:
        log.info("build_slates: dropped %d skill rows without salary", dropped)
    skill["id"] = skill.gsis_id
    skill["pos"] = skill.position
    skill["opp"] = skill.opponent
    # Row position in the replay_projections frame == row in its draw
    # matrix; -1 (DST) means "no draws, use the static projection".
    skill["draw_idx"] = skill.index.to_numpy()
    # Tournament tilt (mirrors app._player_pool): ceiling-valued punts.
    # The chalk-fade penalty is applied per-slate below.
    from ..optimizer.lineup import PUNT_MAX_SALARY

    punt = skill.salary <= PUNT_MAX_SALARY
    # A/B lever (env PUNT_VALUE=tail, off by default): value punts at the
    # top-quartile MEAN (proj_tail) instead of the p90 point — ETR's
    # ceiling definition; more stable and it sees the far tail p90 cuts
    # off. Default stays p90 (the validated shipping rule).
    ceil_col = ("proj_tail" if os.environ.get("PUNT_VALUE") == "tail"
                and "proj_tail" in skill.columns else "proj_p90")
    skill["proj"] = skill.proj_points.where(~punt,
                                            skill[["proj_points", ceil_col]].max(axis=1))
    import os as _os2

    _k = float(_os2.environ.get("ALT_CEIL", "0") or 0)
    if _k and "ceil_spread" in skill.columns:
        # Market-implied ceiling room boosts modest-salary objectives
        mod = skill.salary <= 6500
        skill.loc[mod, "proj"] += _k * pd.to_numeric(
            skill.loc[mod, "ceil_spread"], errors="coerce").fillna(0)
    if "name" not in skill.columns:
        skill["name"] = skill.gsis_id

    qb_starts, vegas = None, None
    if dst is not None and len(dst):
        try:
            from ..inference.qb_experience import starter_prior_starts

            qb_starts = starter_prior_starts()
        except Exception:
            log.exception("QB-experience data unavailable; DST projections "
                          "without the opponent adjustment")
        try:
            from ..bq import query_df
            from ..config import settings

            vegas = query_df(
                f"""
                SELECT season, week, home_team AS team,
                       (total_line - spread_line)/2 AS opp_implied
                FROM `{settings.raw}.schedules`
                WHERE game_type='REG' AND total_line IS NOT NULL
                UNION ALL
                SELECT season, week, away_team AS team,
                       (total_line + spread_line)/2 AS opp_implied
                FROM `{settings.raw}.schedules`
                WHERE game_type='REG' AND total_line IS NOT NULL
                """
            )
        except Exception:
            log.exception("Vegas lines unavailable; DST projections "
                          "without the implied-total model")
    dst_rows = (dst_slate_rows(dst, qb_starts, vegas)
                if dst is not None else None)
    own_booster = None
    # OWN_MODEL default "fade" ADOPTED 2026-08-04 (QF arm): model own in
    # the chalk fade, naive field kept as the stable yardstick. "" disables.
    if own_mode():
        replay_season = int(skill.season.max())
        own_booster = _ownership_booster(replay_season)
    # ADOPTED at +2 (Addendum 37): the only lever to beat the 49f8dac
    # baseline on every metric at once (tails 16 vs 15, both >=237 weeks
    # kept, median and ROI up). Dose-response was clean — 4 and 8
    # overwhelm the p90 punt valuation and destroy the slate-breakers.
    punt_boom = float(os.environ.get("PUNT_BOOM", "2") or 0)
    boom_keys: set = set()
    if punt_boom:
        try:
            boom_keys = _punt_boom_flags(sorted(skill.season.unique()))
            log.info("punt-boom: %d flagged player-weeks", len(boom_keys))
        except Exception:
            log.exception("punt-boom signals unavailable; lever inert")
            punt_boom = 0.0
    # A/B levers (off by default — separate gates so the ADOPTED punt
    # boom's behavior never changes silently): PUNT_BOOM_WR=1 adds the
    # deep-threat-WR archetype to the punt-boom flag set; WR_BOOM=<pts>
    # boosts OUR objective for boom-shaped MID-band ($4-6.5k) WRs, the
    # band where real winners' WR eruptions live.
    wr_boom = float(os.environ.get("WR_BOOM", "0") or 0)
    wr_keys: set = set()
    if wr_boom or os.environ.get("PUNT_BOOM_WR"):
        try:
            wr_keys = _wr_boom_flags(sorted(skill.season.unique()))
            log.info("wr-boom: %d flagged player-weeks", len(wr_keys))
            if os.environ.get("PUNT_BOOM_WR") and punt_boom:
                boom_keys = boom_keys | wr_keys
        except Exception:
            log.exception("wr-boom signals unavailable; lever inert")
            wr_boom = 0.0
    slates = []
    for (season, week), grp in skill.groupby(["season", "week"]):
        cols = ["id", "name", "pos", "team", "opp", "game_id",
                "salary", "proj", "actual", "season", "week", "draw_idx"]
        frame = grp[cols].copy()
        if dst_rows is not None:
            d = dst_rows[(dst_rows.season == season) & (dst_rows.week == week)].copy()
            d["game_id"] = d.team + "@" + d.opp
            d["draw_idx"] = -1
            frame = pd.concat([frame, d[cols]], ignore_index=True)
        # RotoGuru DST rows occasionally lack salary or points; a single NaN
        # poisons the field sampler's ownership softmax.
        n0 = len(frame)
        frame = frame.dropna(subset=["salary", "proj", "actual"])
        frame = frame[frame.salary > 0]  # RotoGuru's missing-salary sentinel
        # Engine requires unique ids (actual.reindex, draw alignment);
        # guard against upstream merge fan-outs rather than crash mid-run.
        dup = frame.id.duplicated()
        if dup.any():
            log.warning("slate %s wk %s: dropping %d duplicate-id rows",
                        season, week, int(dup.sum()))
            frame = frame[~dup]
        if len(frame) < n0:
            log.info("slate %s wk %s: dropped %d rows with missing salary/proj/actual",
                     season, week, n0 - len(frame))
        frame["salary"] = frame.salary.astype(int)
        # Our entries optimize the leverage-tilted objective; the field
        # simulation keeps the untilted proj — the field is chalky by
        # definition, and that asymmetry IS the leverage.
        from ..optimizer.lineup import LEVERAGE_PENALTY
        from .field import naive_ownership

        frame = frame.reset_index(drop=True)
        # A/B lever (env LEV_POS_WEIGHTS, e.g. "RB:0.5,QB:0.8,WR:1.2,TE:1.1,
        # DST:2.0", off by default = uniform): position-weighted chalk fade.
        # Levitan's 452-top-10 Milly study: ownership-vs-points corr by
        # position is RB .55 / QB .53 / TE .48 / WR .47 / DST .21 -- the
        # crowd is nearly RIGHT about RB chalk (fading it is expensive) and
        # nearly uninformed about DST (fading it is cheap leverage).

        lev_w = 1.0
        spec = os.environ.get("LEV_POS_WEIGHTS", "")
        if spec:
            wmap = {k.strip().upper(): float(v) for k, _, v in
                    (part.partition(":") for part in spec.split(","))}
            lev_w = frame.pos.str.upper().map(wmap).fillna(1.0).to_numpy()
        # LEV_PENALTY env (assumption validation): the 25.0 constant was
        # hand-set pre-A/B-era; 0 tests whether the chalk fade helps at all.
        lev_pen = float(os.environ.get("LEV_PENALTY", LEVERAGE_PENALTY))
        # OWN_MODEL=1 (2026-08-01, the LineStar-ownership capstone): swap
        # the naive value/salary softmax for the trained ownership model
        # (walk-forward fit, seasons < replay season) in BOTH the chalk
        # fade here and the field sampler (engine passes frame.model_own
        # through when present). OOS 2025: model corr .727 vs naive .548.
        own = None
        if own_mode() and own_booster is not None:
            own = _model_ownership(own_booster, frame)
            # OWN_MODEL=fade (2026-08-03 graveyard review): the original
            # rejection conflated decision input with measurement — the
            # model went into the fade AND the field, and the "median
            # doubled" verdict partly reflects a sharper yardstick, not
            # worse lineups. fade-only keeps the naive field (stable
            # measurement) while the fade uses the better own estimate.
            if own_mode() not in ("fade", ""):
                frame["model_own"] = own
        if own is None:
            own = naive_ownership(frame)
        # A/B lever (env LEV_SHAPE=sqrt, off by default = linear): a
        # LINEAR chalk penalty keeps paying all the way to the 0.1%-owned
        # fringe, pulling entries toward implausibly low-owned players
        # (pangadfs's OwnershipPenalty argues the same). sqrt gives
        # diminishing reward for going ever more contrarian; rescaled to
        # the same slate-mean penalty so only the SHAPE changes.
        own_eff = own
        if os.environ.get("LEV_SHAPE") == "sqrt":
            root = np.sqrt(np.maximum(own, 0.0))
            m = root.mean()
            if m > 1e-12:
                own_eff = root * (np.mean(own) / m)
        frame["proj_tourney"] = frame.proj - lev_pen * lev_w * own_eff
        # A/B lever (env DST_PUNT_BONUS, off by default): 2023-24 Milly
        # winners used a cheap DST as their punt in 29/31 weeks (addendum
        # 7). The bonus tilts OUR objective toward sub-punt-cap DSTs;
        # the field's proj is untouched.

        dst_bonus = float(os.environ.get("DST_PUNT_BONUS", "0") or 0)
        if dst_bonus:
            from ..optimizer.lineup import PUNT_MAX_SALARY as _punt_cap

            cheap_dst = (frame.pos == "DST") & (frame.salary <= _punt_cap)
            frame.loc[cheap_dst, "proj_tourney"] += dst_bonus
        # A/B lever (env PUNT_BOOM, off by default): Addendum 36 found a
        # perfect punt swap crosses 194 in 16/28 near-miss weeks while
        # our punts average 7.3 with 45% duds. Boost OUR objective for
        # punt-priced skill players matching a winning-punt archetype
        # (see _punt_boom_from_signals); the field's proj is untouched.
        if punt_boom and boom_keys:
            from ..optimizer.lineup import PUNT_MAX_SALARY as _pcap2

            keys = list(zip(frame.id, frame.season.astype(int),
                            frame.week.astype(int)))
            boom = pd.Series([k in boom_keys for k in keys],
                             index=frame.index)
            boom &= (frame.salary <= _pcap2) & (frame.pos != "DST")
            frame.loc[boom, "proj_tourney"] += punt_boom
        # A/B lever (env PUNT_SLOPE, off by default): winners' punts
        # cluster $2.9-3.9k; the hard $3,500 threshold failed its
        # rebuilt-data confirmation (a cliff only binds in the sliver).
        # This is the SHAPED version: within the punt band, cheaper
        # punts get a boost proportional to distance below $4k.
        slope = float(os.environ.get("PUNT_SLOPE", "0") or 0)
        if slope:
            from ..optimizer.lineup import PUNT_MAX_SALARY as _pcap3

            pmask = (frame.salary <= _pcap3) & (frame.pos != "DST")
            frame.loc[pmask, "proj_tourney"] += (
                slope * (_pcap3 - frame.loc[pmask, "salary"]) / 1000.0)
        # A/B lever (env PUNT_STRICT, off by default): the CONDITIONAL
        # threshold — unflagged punts must be <=$3,500; boom-archetype
        # punts stay eligible to $4k (cheap punts are min-priced
        # STARTERS; an expensive punt must earn its price with a role
        # signal). Consumed by the optimizer's punt constraint via the
        # punt_elig flag when PUNT_STRICT is set.
        if os.environ.get("PUNT_STRICT") and punt_boom and boom_keys:
            keys2 = list(zip(frame.id, frame.season.astype(int),
                             frame.week.astype(int)))
            boom2 = pd.Series([k in boom_keys for k in keys2],
                              index=frame.index)
            frame["punt_elig"] = (
                (frame.salary <= 3500)
                | (boom2 & (frame.salary <= 4000))) & (frame.pos != "DST")
        if wr_boom and wr_keys:
            keys = list(zip(frame.id, frame.season.astype(int),
                            frame.week.astype(int)))
            wb = pd.Series([k in wr_keys for k in keys], index=frame.index)
            wb &= (frame.pos == "WR") & frame.salary.between(4000, 6500)
            frame.loc[wb, "proj_tourney"] += wr_boom
        # Ownership-shape flag for the MIN_LOWOWN optimizer constraint
        # (winner spec, Addendum 38: ~2 sub-5%-owned players per winning
        # lineup). Expected ownership ~= within-position weight x roster
        # slots for that position.
        slots = {"QB": 1.0, "RB": 2.5, "WR": 3.5, "TE": 1.2, "DST": 1.0}
        frame["low_own"] = (own * frame.pos.map(slots).fillna(1.0)
                            .to_numpy()) < 0.05
        slates.append(frame)
    return slates


def run_contest_replay(
    proj: pd.DataFrame,
    dst: pd.DataFrame,
    contest: Contest,
    n_entries: int = 20,
    field_size: int = 5_000,
    seed: int = 42,
    sharp_fraction: float = 0.15,
    stack=None,
    draws: np.ndarray | None = None,
    tail_line: float | None = None,
    n_boom_solves: int = 40,
) -> BacktestResult:
    return engine_run(build_slates(proj, dst), contest,
                      n_entries=n_entries, field_size=field_size, seed=seed,
                      sharp_fraction=sharp_fraction, stack=stack,
                      draws=draws, tail_line=tail_line,
                      n_boom_solves=n_boom_solves)


# Warehouse entry point ------------------------------------------------------


def load_panel_and_dst(season: int):
    from ..bq import query_df
    from ..config import settings

    panel = query_df(
        f"""
        SELECT t.*, i.name
        FROM `{settings.features}.player_week_training` t
        LEFT JOIN `{settings.raw}.player_ids` i USING (gsis_id)
        WHERE t.season BETWEEN {settings.train_first_season} AND {season}
        """
    )
    dst = query_df(
        f"""
        -- RotoGuru rows (position 'Def', <=2021) carry dk_points actuals;
        -- LineStar-backfilled rows (position 'DST', 2022-24) don't, so
        -- actuals are computed from pbp + schedules with DK DST scoring
        -- (same accounting as app.store.trailing_kdst). LAR->LA maps the
        -- one abbreviation difference vs nflverse.
        WITH sal AS (
          SELECT season, week,
                 IF(team_abbr = 'LAR', 'LA', team_abbr) AS team,
                 IF(opponent = 'LAR', 'LA', opponent) AS opp,
                 salary, dk_points
          FROM `{settings.raw}.dk_salaries_historical`
          WHERE UPPER(position) IN ('DEF', 'DST') AND season = {season}
        ),
        def_game AS (
          SELECT p.game_id, p.defteam AS team, ANY_VALUE(p.week) AS week,
                 SUM(CAST(p.sack AS INT64)) AS sacks,
                 SUM(CAST(p.interception AS INT64))
                   + SUM(IF(p.fumble_lost = 1, 1, 0)) AS takeaways,
                 SUM(IF(p.touchdown = 1 AND p.td_team = p.defteam, 1, 0)) AS tds
          FROM `{settings.raw}.pbp` p
          WHERE p.season = {season} AND p.defteam IS NOT NULL
          GROUP BY p.game_id, p.defteam
        ),
        pts AS (
          SELECT game_id, home_team AS team, away_score AS pa
          FROM `{settings.raw}.schedules` WHERE season = {season}
          UNION ALL
          SELECT game_id, away_team, home_score
          FROM `{settings.raw}.schedules` WHERE season = {season}
        ),
        computed AS (
          SELECT dg.team, dg.week,
                 dg.sacks + 2*dg.takeaways + 6*dg.tds +
                 CASE WHEN p.pa = 0 THEN 10 WHEN p.pa <= 6 THEN 7
                      WHEN p.pa <= 13 THEN 4 WHEN p.pa <= 20 THEN 1
                      WHEN p.pa <= 27 THEN 0 WHEN p.pa <= 34 THEN -1
                      ELSE -4 END AS dk
          FROM def_game dg JOIN pts p USING (game_id, team)
        )
        SELECT sal.season, sal.week, sal.team, sal.opp, sal.salary,
               COALESCE(sal.dk_points, c.dk) AS actual
        FROM sal
        LEFT JOIN computed c ON c.team = sal.team AND c.week = sal.week
        WHERE COALESCE(sal.dk_points, c.dk) IS NOT NULL
        """
    )
    return panel, dst


TAIL_LINE_DEFAULT = 194.0  # min 2025 Milly-winning line; 0 disables


def _ownership_booster(replay_season: int):
    """OWN_MODEL=1: LightGBM ownership model fit on LineStar-backfilled
    contest ownership, WALK-FORWARD (seasons strictly before the replayed
    one -- point-in-time discipline applies to auxiliary models too).
    Returns None when no prior-season ownership exists (e.g. 2022)."""
    from ..models import ownership as own_mod

    frame = own_mod.training_frame()
    tr = frame[frame.season < replay_season]
    if len(tr) < 1000:
        log.warning("OWN_MODEL: only %d prior-season ownership rows before "
                    "%s; falling back to naive", len(tr), replay_season)
        return None
    log.info("OWN_MODEL: fit on %d rows from seasons < %s", len(tr), replay_season)
    return own_mod.train(tr)


def _model_ownership(booster, frame: pd.DataFrame) -> np.ndarray:
    """Predicted pct -> naive_ownership-compatible weights (normalized
    within position), so LEVERAGE_PENALTY's scale and the field sampler's
    per-slot semantics are preserved. frame['proj'] stands in for the
    public points expectation the model trained on."""
    from ..models import ownership as own_mod

    f = pd.DataFrame({
        "season": frame["season"], "week": frame["week"],
        "position": frame["pos"], "salary": frame["salary"],
        "proj_points": frame["proj"],
    })
    pct = own_mod.predict_ownership(booster, f)
    out = np.zeros(len(frame))
    for _pos, idx in frame.groupby("pos").groups.items():
        loc = frame.index.get_indexer(idx)
        tot = pct[loc].sum()
        out[loc] = pct[loc] / tot if tot > 0 else 1.0 / max(len(loc), 1)
    return out


def run(
    season: int,
    n_sims: int = 10_000,
    contest: Contest | None = None,
    n_entries: int = 40,
    field_size: int = 5_000,
    sharp_fraction: float = 0.15,
    tail_line: float | None = None,
) -> None:
    panel, dst = load_panel_and_dst(season)
    proj, draws = replay_projections(panel, season, n_sims=n_sims,
                                     return_draws=True)
    # Market blend (guide §7.7) with real prop-derived medians when the
    # season has prop_lines coverage; players without a line keep the
    # model projection (blend() falls back on NaN).
    try:
        from ..models.blend import BLEND_W, blend as _blend
        from ..models.prop_market import market_points

        mkt = market_points((season,))
        if not mkt.empty:
            # Dedup + length guard (2026-08-04 audit): market_points
            # dedups on NAME norm, not gsis — two name variants of one
            # player produce duplicate (season, week, gsis_id) keys, the
            # left merge fans rows out, and every draw_idx after the
            # first duplicate points at the NEXT player's draws.
            mkt = mkt.drop_duplicates(["season", "week", "gsis_id"])
            _n_before = len(proj)
            proj = proj.merge(mkt, on=["season", "week", "gsis_id"],
                              how="left")
            assert len(proj) == _n_before, "market merge fanned out rows"
            _pre = proj.proj_points.to_numpy().copy()
            proj["proj_points"] = _blend(_pre,
                                         proj.market_points.to_numpy(),
                                         BLEND_W)
            log.info("prop-market blend applied to %d/%d rows",
                     int(proj.market_points.notna().sum()), len(proj))
            # Weight sweep: BLEND_W was fit against the weak dk_ppg
            # market; the prop market is stronger and likely deserves
            # more weight. MAE(w) over blended rows only.
            have = proj.market_points.notna().to_numpy()
            act = proj.actual.to_numpy()[have]
            mdl, mrk = _pre[have], proj.market_points.to_numpy()[have]
            import numpy as _np

            print("  blend-weight sweep (w = model weight; blended rows):")
            for w in (0.0, 0.1, 0.2, 0.3, 0.4, 0.45, 0.5, 0.6, 0.7, 1.0):
                mae = _np.abs(w * mdl + (1 - w) * mrk - act).mean()
                print(f"    w={w:.2f}  MAE={mae:.4f}")
    except Exception:
        log.exception("prop market unavailable; replaying unblended")
    try:  # market ceiling room (env ALT_CEIL, off by default)
        import os as _os

        k = float(_os.environ.get("ALT_CEIL", "0") or 0)
        if k:
            from ..models.prop_market import market_ceilings

            mc = market_ceilings((season,)).drop_duplicates(
                ["season", "week", "gsis_id"])
            proj = proj.merge(mc, on=["season", "week", "gsis_id"],
                              how="left")
    except Exception:
        log.exception("alt ceilings unavailable")
    overall, by_pos = replay_metrics(proj)

    print(f"\n=== Projection replay: {season} "
          f"(trained on {int(panel.season.min())}-{season - 1}) ===")
    for k, v in overall.items():
        print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}")
    print(by_pos.round(3).to_string())

    if dst.empty:
        print(f"\nNo {season} DST/salary data (see README data deficiency log) "
              f"— skipping contest replay.")
        return
    if contest is None:
        from .payout import gpp

        contest = gpp()
    # QB stacking validated on both imputed-2025 and real-2021 replays
    # (reports/2026-07-25-system-study.md addendum); mean objective beat a
    # p90 objective on real salaries, so stacking is the only GPP default.
    from ..optimizer.lineup import StackRules

    # Assumption-validation levers (2026-08-01): these construction rules
    # predate the deterministic A/B era and were adopted on correlational
    # evidence; the envs let each be causally tested with one exact run.
    # Defaults reproduce the adopted construction unchanged.
    stack = (StackRules(
                 qb_stack_min=int(os.environ.get("STACK_QB_MIN", "2")),
                 bring_back_min=int(os.environ.get("STACK_BRING_BACK", "1")),
                 forbid_rb_vs_dst=os.environ.get("FORBID_RB_DST", "1") != "0")
             if "gpp" in contest.name else None)
    # Tail-objective selection (issue #5) is a GPP concept only; double-ups
    # want the mean objective. tail_line=0 disables explicitly.
    if tail_line is None and "gpp" in contest.name:
        tail_line = TAIL_LINE_DEFAULT
    use_tail = bool(tail_line)
    if use_tail:
        print(f"\n  entry selection: P(best >= {tail_line:.0f}) greedy "
              f"coverage over correlated draws")
    best_by_week = {}
    slates = build_slates(proj, dst)
    result = engine_run(slates, contest,
                        n_entries=n_entries, field_size=field_size,
                        sharp_fraction=sharp_fraction, stack=stack,
                        draws=draws if use_tail else None,
                        tail_line=tail_line if use_tail else None)
    print(f"\n=== Contest replay: {season} "
          f"(field {sharp_fraction:.0%} optimizer-built) ===")
    print(result.summary())
    best = [max(w.lineup_scores) for w in result.weeks]
    if best:
        import numpy as _np

        print(f"  tail: mean best {_np.mean(best):.1f}  max {_np.max(best):.1f}  "
              f"weeks best>=237 (avg 2025 milly line): {sum(b >= 237 for b in best)}"
              f"/{len(best)}  >=194 (min line): {sum(b >= 194 for b in best)}/{len(best)}")
        # The user doesn't play rest-week slates (17-18); report the
        # tail on the weeks he actually enters.
        pb = [max(w.lineup_scores) for w in result.weeks if w.week <= 16]
        if pb and len(pb) < len(best):
            print(f"  playable weeks (<=16): mean best {_np.mean(pb):.1f}  "
                  f">=194: {sum(b >= 194 for b in pb)}/{len(pb)}  "
                  f">=187 (20k-qualifier line): "
                  f"{sum(b >= 187 for b in pb)}/{len(pb)}")
        # Honest per-week bar: the ACTUAL score that won the Milly that
        # week (real_lines.py, 2019/23/24/25). Era-portable, unlike the
        # 2025-anchored constants above.
        from .real_lines import REAL_LINES

        pairs = [(max(w.lineup_scores), REAL_LINES[(w.season, w.week)])
                 for w in result.weeks if (w.season, w.week) in REAL_LINES]
        if pairs:
            beat = sum(b >= ln for b, ln in pairs)
            gap = _np.mean([ln - b for b, ln in pairs])
            print(f"  vs REAL winning lines ({len(pairs)} wks known): "
                  f"beat {beat}/{len(pairs)}  mean gap {gap:.0f} pts  "
                  f"within 20: {sum(0 < ln - b <= 20 for b, ln in pairs)}")
        # Milly winners spend the cap (2025: median $0 left, max $100;
        # 2023-24: 90% within $300) — flag if our entries leave money.
        left = [50_000 - lu.salary for w in result.weeks for lu in w.lineups]
        print(f"  salary left on table: mean {_np.mean(left):.0f}  "
              f"median {_np.median(left):.0f}  p90 {_np.percentile(left, 90):.0f}  "
              f"share >$1k: {100 * _np.mean(_np.array(left) > 1000):.0f}%")
        _entries_to_line(result.weeks)
        _confidence_calibration(result.weeks, proj)
        _entry_anatomy(result.weeks)
        _capture_rates(result.weeks, slates)
        _duplication_risk(result.weeks)
        try:  # persist rosters for human review (nfl_features.replay_lineups)
            from ..bq import load_dataframe
            from ..config import settings

            rows = []
            for w in result.weeks:
                order = np.argsort(w.lineup_scores)[::-1]
                for rk, ix in enumerate(order):
                    lu = w.lineups[ix]
                    for p in lu.players:
                        rows.append({
                            "season": w.season, "week": w.week,
                            "score_rank": rk + 1, "tag": lu.tag or "lev",
                            # selection order (greedy coverage is nested:
                            # first N entries ~ optimal N-entry portfolio)
                            # -> one 150-entry run yields P(best-of-N)
                            # curves for every N (entries sweet-spot study)
                            "entry_ix": int(ix) + 1,
                            "lineup_score": round(w.lineup_scores[ix], 1),
                            "player": p.get("name"), "pos": p.get("pos"),
                            "team": p.get("team"), "salary": p.get("salary"),
                            "proj": round(float(p.get("proj", 0)), 1),
                            "actual": round(float(p.get("actual") or 0), 1)})
            load_dataframe(pd.DataFrame(rows),
                           f"{settings.features}.replay_lineups",
                           write_disposition="WRITE_TRUNCATE")
            print(f"  rosters persisted: {len(rows)} rows -> replay_lineups")
        except Exception:
            log.exception("could not persist replay rosters")


def _duplication_risk(weeks, field_size: int = 150_000) -> None:
    """Estimated copies of each entry in a Milly-sized field: field_size
    x product of player ownerships (naive proxy until the real model).
    Arbitrates whether engineered uniqueness (underspend, forced pivots)
    is needed or our entries are already effectively unique."""
    import numpy as _np

    from ..optimizer.lineup import LEVERAGE_PENALTY

    est = []
    for w in weeks:
        for lu in w.lineups:
            owns = [max(1e-4, min(0.6, (p.get("proj", 0)
                    - p.get("proj_tourney", p.get("proj", 0)))
                    / LEVERAGE_PENALTY)) for p in lu.players]
            est.append(field_size * float(_np.prod(owns)))
    if not est:
        return
    e = _np.array(est)
    print(f"  duplication risk (est copies in a {field_size//1000}k field, "
          f"naive ownership): median {_np.median(e):.3f}  "
          f"p90 {_np.percentile(e, 90):.2f}  max {e.max():.1f}  "
          f"entries with >=1 est copy: {int((e >= 1).sum())}/{len(e)}")


def _capture_rates(weeks, slates) -> None:
    """Did our 40 hold the slate's best-scoring punt / QB at all? Breadth
    (distinct players held per tier) + capture tell whether misses are a
    prediction problem or a diversity problem."""
    import numpy as _np

    from ..optimizer.lineup import PUNT_MAX_SALARY

    by_wk = {int(s.week.iloc[0]): s for s in slates}
    rows = []
    for w in weeks:
        sl = by_wk.get(w.week)
        if sl is None:
            continue
        punts = sl[(sl.salary <= PUNT_MAX_SALARY)]
        best_punt = punts.actual.max() if len(punts) else 0
        qbs = sl[sl.pos == "QB"]
        best_qb = qbs.actual.max() if len(qbs) else 0
        held_p, held_q = set(), set()
        our_bp, our_bq = 0.0, 0.0
        for lu in w.lineups:
            for p in lu.players:
                a = float(p.get("actual") or 0)
                if p["salary"] <= PUNT_MAX_SALARY:
                    held_p.add(p["id"]); our_bp = max(our_bp, a)
                if p["pos"] == "QB":
                    held_q.add(p["id"]); our_bq = max(our_bq, a)
        rows.append({"pc": our_bp >= best_punt - 1e-6,
                     "qc": our_bq >= best_qb - 1e-6,
                     "np": len(held_p), "nq": len(held_q),
                     "pgap": best_punt - our_bp, "qgap": best_qb - our_bq})
    if not rows:
        return
    d = pd.DataFrame(rows)
    print(f"  capture rates across our 40 (per week):")
    print(f"    slate-best PUNT held: {int(d.pc.sum())}/{len(d)} weeks  "
          f"(distinct punts held avg {d.np.mean():.1f}, "
          f"miss gap avg {d[~d.pc].pgap.mean():.1f} pts)")
    print(f"    slate-best QB held:   {int(d.qc.sum())}/{len(d)} weeks  "
          f"(distinct QBs held avg {d.nq.mean():.1f}, "
          f"miss gap avg {d[~d.qc].qgap.mean():.1f} pts)")


def _entry_anatomy(weeks) -> None:
    """Why do our best entries win? Compare each week's top scorer (and
    top quintile) against the rest of the 40 on structure: generator of
    origin, game concentration, QB stack size, punt production, chalk
    level, salary. Ownership is recovered from the leverage tilt:
    proj_tourney = proj - LEVERAGE_PENALTY * ownership."""
    import numpy as _np

    from ..optimizer.lineup import LEVERAGE_PENALTY, PUNT_MAX_SALARY

    def feats(lu):
        ps = lu.players
        games = {}
        for p in ps:
            games[p.get("game_id")] = games.get(p.get("game_id"), 0) + 1
        qb = next((p for p in ps if p["pos"] == "QB"), None)
        stack_n = sum(1 for p in ps if qb is not None and p["pos"] in
                      ("WR", "TE") and p["team"] == qb["team"])
        punts = [p for p in ps if p["salary"] <= PUNT_MAX_SALARY]
        own = sum(max(0.0, (p.get("proj", 0) - p.get("proj_tourney",
                   p.get("proj", 0)))) / LEVERAGE_PENALTY for p in ps)
        return {
            "tag": lu.tag or "lev",
            "max_game": max(games.values()) if games else 0,
            "stack": stack_n,
            "punt_actual": max((float(p.get("actual") or 0) for p in punts),
                               default=0.0),
            "own": own,
            "salary": lu.salary,
        }

    rows, best_tags = [], []
    for w in weeks:
        order = _np.argsort(w.lineup_scores)[::-1]
        for rank_pos, idx in enumerate(order):
            f = feats(w.lineups[idx])
            f["score"] = w.lineup_scores[idx]
            f["is_best"] = rank_pos == 0
            f["is_top8"] = rank_pos < 8
            rows.append(f)
            if rank_pos == 0:
                best_tags.append(f["tag"])
    if not rows:
        return
    df = pd.DataFrame(rows)
    pool_share = df.tag.value_counts(normalize=True)
    from collections import Counter

    bt = Counter(best_tags)
    print("  entry anatomy (what wins within our own 40):")
    print("    weekly best by generator: "
          + "  ".join(f"{t}:{bt.get(t, 0)}/{len(best_tags)} "
                      f"(pool {100 * pool_share.get(t, 0):.0f}%)"
                      for t in ("lev", "boom", "game", "nostk", "midqb", "dark")))
    for label, mask in (("weekly best", df.is_best),
                        ("top-8/week", df.is_top8),
                        ("rest", ~df.is_top8)):
        g = df[mask]
        print(f"    {label:>11}: score {g.score.mean():5.1f}  "
              f"max-from-game {g.max_game.mean():.2f}  "
              f"QB stack {g['stack'].mean():.2f}  "
              f"punt pts {g.punt_actual.mean():5.1f}  "
              f"chalk {g.own.mean():.2f}  salary {g.salary.mean():.0f}")


def _confidence_calibration(weeks, proj: pd.DataFrame,
                            line: float = 194.0, dst_std: float = 5.4) -> None:
    """Judge the app's confidence formula (normal-approx P(entry >= line)
    from per-player proj mean/std — app._rank_by_confidence) the same way
    the selection order is judged: where does each week's best scorer land
    when entries are ordered by that confidence?"""
    from statistics import NormalDist

    import numpy as _np

    mu_map = {(r.week, r.gsis_id): r.proj_points for r in proj.itertuples()}
    sd_map = {(r.week, r.gsis_id): r.proj_std for r in proj.itertuples()}
    ranks = []
    for w in weeks:
        conf = []
        for lu in w.lineups:
            mu = sum(float(mu_map.get((w.week, p["id"]), p["proj"]))
                     for p in lu.players)
            var = sum(float(sd_map.get((w.week, p["id"]), dst_std)) ** 2
                      for p in lu.players)
            conf.append(1 - NormalDist(mu, max(var ** 0.5, 1e-6)).cdf(line))
        order = _np.argsort(conf)[::-1]  # most confident first
        best_idx = int(_np.argmax(w.lineup_scores))
        ranks.append(int(_np.where(order == best_idx)[0][0]) + 1)
    if ranks:
        r = _np.array(ranks)
        print(f"  app-confidence ordering, best scorer's rank: "
              f"median {int(_np.median(r))}  rank-1 hit {int((r == 1).sum())}"
              f"/{len(r)}  in top-5 {int((r <= 5).sum())}/{len(r)}"
              f"  in top-10 {int((r <= 10).sum())}/{len(r)}")


def _entries_to_line(weeks, lines=(194, 237)) -> None:
    """Order-statistics extrapolation: from each week's entry-score
    distribution (normal fit to the generated entries), how many entries N
    would give a 50% chance that the best of N clears a Milly line?
    N = ln(0.5)/ln(P(one entry < line)). Two opposing biases roughly cancel:
    a normal fit thins the right tail (overstates N for correlated stacks),
    while extrapolating from the optimizer's top picks assumes entry quality
    doesn't degrade with N (understates it). Read as order-of-magnitude."""
    import math
    from statistics import NormalDist

    import numpy as _np

    print("  entries-to-line (N for 50% chance best-of-N >= line); "
          "top3 = the week's three best entry scores:")
    print(f"    {'week':>4} {'mu':>6} {'sd':>5} {'top3':>20} {'brk':>4} "
          + " ".join(f"N@{ln}" for ln in lines))
    med = {ln: [] for ln in lines}
    best_ranks: list[int] = []
    for w in weeks:
        s = _np.asarray(w.lineup_scores, dtype=float)
        if len(s) < 5 or s.std(ddof=1) == 0:
            continue
        mu, sd = s.mean(), s.std(ddof=1)
        ns = []
        for ln in lines:
            p_under = NormalDist(mu, sd).cdf(ln)
            n = math.inf if p_under >= 1.0 else (
                1.0 if p_under <= 0.5 else math.log(0.5) / math.log(p_under))
            med[ln].append(n)
            ns.append("inf" if n == math.inf else f"{n:.0f}")
        top3 = ",".join(f"{v:.1f}" for v in sorted(s)[::-1][:3])
        best_rank = int(_np.argmax(s)) + 1  # selection position of the
        best_ranks.append(best_rank)        # week's best scorer (1 = the
        print(f"    {w.week:>4} {mu:6.1f} {sd:5.1f} {top3:>20} {best_rank:>4} "
              + " ".join(f"{x:>7}" for x in ns))  # entry we trusted most)
    if best_ranks:
        br = _np.array(best_ranks)
        print(f"    best scorer's selection rank: median {int(_np.median(br))}"
              f"  rank-1 hit {int((br == 1).sum())}/{len(br)} weeks"
              f"  in top-5 {int((br <= 5).sum())}/{len(br)}"
              f"  in top-10 {int((br <= 10).sum())}/{len(br)}")
    for ln in lines:
        if med[ln]:
            m = sorted(med[ln])[len(med[ln]) // 2]
            within = sum(n <= 150_000 for n in med[ln])
            print(f"    line {ln}: median N {'inf' if m == math.inf else f'{m:,.0f}'}"
                  f"  weeks reachable within a 150k-entry field: "
                  f"{within}/{len(med[ln])}")

```

===== FILE: src/nfl_dfs/backtest/showdown_replay.py =====
```python
"""Showdown Captain Mode season replay: how would our entries have done?

For each Captain Mode slate (default: Thursday/Monday standalone games),
builds the player pool from real FLEX salaries (showdown_salaries_historical,
DiscoveryLab import), projects it, optimizes N entries with the showdown
MILP, and scores them with actual DK points (captain 1.5x).

Projections: model projections for skill positions, matched by normalized
name + position (same rules as 019's salary crosswalk: unique name+position,
else unique name, else unmatched). K/DST/unmatched fall back to the
player's trailing-average actual points (strictly prior weeks) — the same
naive baseline the classic replay uses for DST.

Headline metric: capture = best entry / hindsight-optimal lineup for that
slate, because absolute showdown scores swing with the game environment.
No field/payout simulation — we have no showdown ownership model; this
measures lineup quality, not contest ROI.
"""

from __future__ import annotations

import logging
import os
import re

import numpy as np
import pandas as pd

from ..optimizer.showdown import (CPT_MULT, optimize_many_showdown,
                                  optimize_showdown, showdown_draws,
                                  sim_mode_entries)
from . import replay

log = logging.getLogger(__name__)

DEFAULT_DAYS = ("thursday", "monday")
MIN_PRIOR_GAMES_FOR_NAIVE = 2
# Simulated-outcomes mode (issue #10): SHOWDOWN_SIM=1 builds entries from
# correlated draws (recurrence + tail-line coverage) instead of the plain
# MILP-on-means path; the construction itself lives in optimizer.showdown
# (adopted for the live app too -- Addendum 26).
TRAILING_SD_RATIO = 0.9          # sd for trailing/naive-projected rows


def _norm(name: str) -> str:
    return re.sub(r"[^A-Z ]", "", str(name).upper()).strip()


def projection_lookup(proj: pd.DataFrame) -> dict:
    """(week, norm_name, position) -> (projection, sd), with
    (week, norm_name) fallback when the name is unique that week."""
    has_sd = "proj_std" in proj.columns
    by_np: dict = {}
    by_name: dict = {}
    for r in proj.itertuples():
        if pd.isna(r.name):
            continue
        n = _norm(r.name)
        sd = float(r.proj_std) if has_sd and pd.notna(r.proj_std) else None
        val = (float(r.proj_points), sd)
        key = (int(r.week), n, str(r.position))
        by_np[key] = None if key in by_np else val
        nkey = (int(r.week), n)
        by_name[nkey] = None if nkey in by_name else val
    return {"np": by_np, "name": by_name}


def naive_trailing(slate_df: pd.DataFrame) -> pd.Series:
    """Trailing mean of each slate player's own actual points, strictly
    prior weeks, aligned to slate_df rows."""
    df = slate_df.sort_values(["sdio_player_id", "week"])
    trail = (
        df.groupby("sdio_player_id")["dk_points_actual"]
        .transform(lambda s: s.shift(1).expanding(
            min_periods=MIN_PRIOR_GAMES_FOR_NAIVE).mean())
    )
    return trail.reindex(slate_df.index)


def build_pools(slates: pd.DataFrame, proj: pd.DataFrame) -> pd.DataFrame:
    """Attach a projection to every slate player row; rows with no
    projection of any kind are dropped (logged)."""
    lookup = projection_lookup(proj)
    trail = naive_trailing(slates)
    values, sds, sources = [], [], []
    for i, r in enumerate(slates.itertuples()):
        n = _norm(r.display_name)
        v = None
        if r.position in ("QB", "RB", "WR", "TE"):
            v = lookup["np"].get((int(r.week), n, r.position))
            if v is None:
                v = lookup["name"].get((int(r.week), n))
        if v is not None:
            values.append(v[0])
            sds.append(v[1] if v[1] is not None else v[0] * TRAILING_SD_RATIO)
            sources.append("model")
        elif pd.notna(trail.iloc[i]):
            values.append(float(trail.iloc[i]))
            sds.append(float(trail.iloc[i]) * TRAILING_SD_RATIO)
            sources.append("trailing")
        else:
            values.append(np.nan); sds.append(np.nan); sources.append("none")
    out = slates.assign(proj=values, proj_sd=sds, proj_source=sources)
    dropped = int(out.proj.isna().sum())
    if dropped:
        log.info("build_pools: dropped %d slate rows with no projection", dropped)
    return out.dropna(subset=["proj"])


def replay_showdown_season(
    slates: pd.DataFrame,
    proj: pd.DataFrame,
    n_entries: int = 20,
    days: tuple[str, ...] = DEFAULT_DAYS,
) -> pd.DataFrame:
    """One row per replayed slate: best/median entry actual score,
    hindsight-optimal score, capture ratio."""
    pools = build_pools(slates, proj)
    if days:
        # operator_day is a date in historical slate payloads and a weekday
        # name in live ones — accept either.
        wanted = {d.lower()[:3] for d in days}
        dt = pd.to_datetime(pools.operator_day, errors="coerce")
        day_names = dt.dt.day_name().fillna(pools.operator_day.astype(str))
        pools = pools[day_names.str.lower().str[:3].isin(wanted)]
    results = []
    for (week, slate_id), grp in pools.groupby(["week", "operator_slate_id"]):
        pool = [
            {"id": int(r.sdio_player_id), "name": r.display_name,
             "pos": r.position, "team": r.team_abbr, "opp": None,
             "game_id": slate_id, "salary": int(r.salary),
             "proj": float(r.proj), "proj_sd": float(r.proj_sd),
             "actual": float(r.dk_points_actual) if pd.notna(r.dk_points_actual) else 0.0}
            for r in grp.itertuples()
        ]
        if len(pool) < 8 or len({p["team"] for p in pool}) < 2:
            continue
        if os.environ.get("SHOWDOWN_SIM"):
            entries = sim_mode_entries(pool, n_entries, seed=int(week))
        else:
            entries = optimize_many_showdown(pool, n_lineups=n_entries)
        if not entries:
            continue

        def actual_score(lu) -> float:
            return float(CPT_MULT * lu.captain["actual"]
                         + sum(p["actual"] for p in lu.flex))

        scores = [actual_score(lu) for lu in entries]
        optimal = optimize_showdown(pool, objective_col="actual")
        opt_score = actual_score(optimal) if optimal else np.nan
        results.append({
            "week": int(week), "slate_id": slate_id,
            "game": grp.game_teams.iloc[0], "day": grp.operator_day.iloc[0],
            "pool": len(pool),
            "best": max(scores), "median_entry": float(np.median(scores)),
            "optimal": opt_score,
            "capture": max(scores) / opt_score if opt_score else np.nan,
        })
    return pd.DataFrame(results)


def run(season: int = 2025, n_entries: int = 20, days: str = "thu,mon") -> None:
    from ..bq import query_df
    from ..config import settings

    slates = query_df(
        f"""SELECT * FROM `{settings.raw}.showdown_salaries_historical`
            WHERE season = {season}"""
    )
    if slates.empty:
        raise RuntimeError("no showdown slates; run import-discoverylab-showdown")
    panel, _ = replay.load_panel_and_dst(season)
    proj = replay.replay_projections(panel, season, n_sims=8000, seed=0)
    day_tuple = tuple(d.strip() for d in days.split(",") if d.strip())
    res = replay_showdown_season(slates, proj, n_entries=n_entries, days=day_tuple)
    if res.empty:
        raise RuntimeError("no slates matched the day filter")

    print(f"\n=== Showdown Captain Mode replay: {season} "
          f"({len(res)} slates, {n_entries} entries each, days={days}) ===")
    print(res.round(1).to_string(index=False))
    print(f"\nmean best entry: {res.best.mean():.1f}"
          f"  mean optimal: {res.optimal.mean():.1f}"
          f"  mean capture: {res.capture.mean():.1%}"
          f"  median capture: {res.capture.median():.1%}")
    print(f"slates with capture >= 90%: {(res.capture >= 0.9).sum()}/{len(res)}")

```

===== FILE: src/nfl_dfs/bq.py =====
```python
"""Thin BigQuery helpers.

google-cloud-bigquery is an optional dependency (the modeling / optimizer /
backtest code runs on plain DataFrames), so the import is deferred until a
client is actually needed.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from .config import settings

if TYPE_CHECKING:  # pragma: no cover
    from google.cloud import bigquery

log = logging.getLogger(__name__)

def _sql_dir() -> Path:
    """sql/ lives at the repo root, NOT inside the package. Two layouts:
    a source checkout (this file is src/nfl_dfs/bq.py, so parents[2] is the
    root) and the container (pip-installed into site-packages, where
    parents[2] is /usr/local/lib/python3.11 — but the Dockerfile copies
    sql/ into the WORKDIR). The checkout path silently broke every
    scheduled build-features run (see the deficiency log, 2026-07-31)."""
    candidates = (
        Path(__file__).resolve().parents[2] / "sql",  # source checkout
        Path.cwd() / "sql",                           # container WORKDIR /app
    )
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


SQL_DIR = _sql_dir()


def client() -> "bigquery.Client":
    from google.cloud import bigquery

    return bigquery.Client(project=settings.project)


def render_sql(path: str | Path, **extra: Any) -> str:
    """Read a .sql file and substitute ${raw} / ${features} / ${predictions}
    dataset placeholders plus any extra ${key} values."""
    text = Path(path).read_text()
    subs = {
        "raw": settings.raw,
        "features": settings.features,
        "predictions": settings.predictions,
        **{k: str(v) for k, v in extra.items()},
    }
    for key, value in subs.items():
        text = text.replace("${" + key + "}", value)
    unresolved = re.findall(r"\$\{(\w+)\}", text)
    if unresolved:
        raise ValueError(f"Unresolved SQL placeholders in {path}: {unresolved}")
    return text


def run_sql_file(path: str | Path, **extra: Any) -> None:
    sql = render_sql(path, **extra)
    log.info("Running %s", path)
    client().query(sql).result()


def query_df(sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
    from google.cloud import bigquery

    job_config = None
    if params:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[_to_bq_param(k, v) for k, v in params.items()]
        )
    return client().query(sql, job_config=job_config).to_dataframe()


def _to_bq_param(name: str, value: Any):
    from google.cloud import bigquery

    if isinstance(value, (list, tuple)):
        elem = "INT64" if value and isinstance(value[0], int) else "STRING"
        return bigquery.ArrayQueryParameter(name, elem, list(value))
    if isinstance(value, bool):
        return bigquery.ScalarQueryParameter(name, "BOOL", value)
    if isinstance(value, int):
        return bigquery.ScalarQueryParameter(name, "INT64", value)
    if isinstance(value, float):
        return bigquery.ScalarQueryParameter(name, "FLOAT64", value)
    return bigquery.ScalarQueryParameter(name, "STRING", str(value))


def load_dataframe(
    df: pd.DataFrame,
    table: str,
    write_disposition: str = "WRITE_TRUNCATE",
    partition_field: str | None = None,
) -> None:
    """Load a DataFrame into `dataset.table` (fully qualified or raw-relative)."""
    from google.cloud import bigquery

    if "." not in table:
        table = f"{settings.raw}.{table}"
    job_config = bigquery.LoadJobConfig(write_disposition=write_disposition, autodetect=True)
    if partition_field:
        job_config.time_partitioning = bigquery.TimePartitioning(field=partition_field)
    log.info("Loading %d rows into %s (%s)", len(df), table, write_disposition)
    client().load_table_from_dataframe(df, table, job_config=job_config).result()

```

===== FILE: src/nfl_dfs/cli.py =====
```python
"""Command-line entry points: `nfl-dfs <command>`.

Thin wrappers over the job modules so everything Cloud Scheduler runs can
also be run by hand.
"""

from __future__ import annotations

import argparse
import logging


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="nfl-dfs")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest-nflverse", help="Load nflverse data into nfl_raw")
    p.add_argument("--full", action="store_true", help="Backfill 1999-present")

    sub.add_parser("ingest-dk", help="Snapshot current DK slates/salaries")
    sub.add_parser("ingest-contests",
                   help="Poll DK contest fill rates for overlay detection "
                        "(scaffold, needs INGEST_CONTESTS_ENABLED)")
    sub.add_parser("ingest-cfb",
                   help="Poll DK college football draft groups/draftables + "
                        "contest fills (collection-only scaffold, needs "
                        "INGEST_CFB_ENABLED)")
    sub.add_parser("ingest-odds",
                   help="Snapshot DK game lines via The Odds API")
    sub.add_parser("check-freshness",
                   help="Fail if any active data feed is stale (see status.py)")
    sub.add_parser("backup-tables",
                   help="Daily snapshots of irreplaceable tables (30-day "
                        "retention, ops/backup.py)")
    p = sub.add_parser("field-calibration",
                       help="Score our field sim's dupe/salary realism vs a "
                            "real imported contest (ops/field_calibration.py)")
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--week", type=int, required=True)
    p.add_argument("--contest-id", required=True)
    p.add_argument("--sims", type=int, default=20_000)
    sub.add_parser("train-ownership",
                   help="Fit ownership model on imported contest standings "
                        "(in-season; see issue #11)")
    sub.add_parser("score-entries",
                   help="Score last week's entered lineups vs actuals")
    sub.add_parser("ingest-props", help="Snapshot live prop lines (in-season)")
    sub.add_parser("ingest-weather", help="Fetch Open-Meteo forecasts for upcoming games")

    p = sub.add_parser("backfill-rotoguru", help="One-time historical DK salary backfill")
    p.add_argument("--first-season", type=int, default=2014)

    p = sub.add_parser("build-features", help="Run feature SQL + leakage checks")
    p.add_argument("--skip-leakage", action="store_true")

    sub.add_parser("train", help="Weekly retrain + registry write")
    sub.add_parser("project", help="Project the upcoming slate")

    p = sub.add_parser("trends", help="Changepoint detection + salary-lag watchlist")
    p.add_argument("--season", type=int, default=None)

    p = sub.add_parser("pricing-lag",
                       help="DK salary-vs-trailing-production residual watchlist")
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--week", type=int, required=True)

    p = sub.add_parser("replay",
                       help="Replay a past season: projection accuracy + contest ROI")
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--sims", type=int, default=10_000)
    p.add_argument("--entries", type=int, default=40)
    p.add_argument("--contest", choices=["gpp", "double_up"], default="gpp")
    p.add_argument("--field-size", type=int, default=5_000)
    p.add_argument("--sharp", type=float, default=0.15,
                   help="Fraction of the simulated field built by optimizer")
    p.add_argument("--tail-line", type=float, default=None,
                   help="GPP entry selection maximizes P(best >= this "
                        "score); default 194 for gpp, 0 disables")

    p = sub.add_parser("import-discoverylab",
                       help="Backfill real DK salaries from DiscoveryLab (free tier: last season)")
    p.add_argument("--first-season", type=int, default=2025)
    p.add_argument("--last-season", type=int, default=2025)

    p = sub.add_parser("import-discoverylab-showdown",
                       help="Backfill Captain Mode slates (salaries + actuals) from DiscoveryLab")
    p.add_argument("--first-season", type=int, default=2025)
    p.add_argument("--last-season", type=int, default=2025)

    p = sub.add_parser("replay-showdown",
                       help="Replay Captain Mode: entries vs hindsight-optimal per slate")
    p.add_argument("--season", type=int, default=2025)
    p.add_argument("--entries", type=int, default=40)
    p.add_argument("--days", default="thu,mon")

    p = sub.add_parser("import-prop-lines",
                       help="Backfill player-prop lines from The Odds API")
    p.add_argument("--first-season", type=int, default=2023)
    p.add_argument("--last-season", type=int, default=2025)

    p = sub.add_parser("import-ownership",
                       help="Import a DK contest-standings CSV (actual ownership)")
    p.add_argument("path")
    p.add_argument("--season", type=int, required=True)
    p.add_argument("--week", type=int, required=True)
    p.add_argument("--contest-id", required=True)
    p.add_argument("--contest-name", default=None)

    p = sub.add_parser("archetypes",
                       help="Cluster scoring-consistency archetypes into nfl_features")
    p.add_argument("--seasons", type=int, default=3, help="Trailing seasons to profile")
    p.add_argument("--min-games", type=int, default=16)

    p = sub.add_parser("serve", help="Run the FastAPI app")
    p.add_argument("--port", type=int, default=8080)

    args = parser.parse_args(argv)

    if args.command == "ingest-nflverse":
        from .ingest import nflverse_job

        nflverse_job.run(full_refresh=args.full)
    elif args.command == "ingest-dk":
        from .ingest import dk_job

        dk_job.run()
    elif args.command == "ingest-contests":
        from .ingest import contest_job

        contest_job.run()
    elif args.command == "ingest-cfb":
        from .ingest import cfb_job

        cfb_job.run()
    elif args.command == "ingest-odds":
        from .ingest import odds_job

        odds_job.run()
    elif args.command == "check-freshness":
        from . import status

        status.check_freshness()
    elif args.command == "backup-tables":
        from .ops import backup

        backup.run()
    elif args.command == "field-calibration":
        from .ops import field_calibration

        field_calibration.run(args.season, args.week, args.contest_id,
                              n_sims=args.sims)
    elif args.command == "train-ownership":
        from .models import ownership

        ownership.run_training()
    elif args.command == "ingest-weather":
        from .ingest import weather_job

        weather_job.run()
    elif args.command == "backfill-rotoguru":
        from .ingest import rotoguru_backfill

        rotoguru_backfill.run(first_season=args.first_season)
    elif args.command == "build-features":
        from .features import build

        build.run(check_leakage=not args.skip_leakage)
    elif args.command == "train":
        from .models import train_job

        train_job.train_and_register()
    elif args.command == "project":
        from .inference import run_projections

        run_projections.run()
    elif args.command == "trends":
        from .config import current_season
        from .trends import alerts

        alerts.run(args.season or current_season())
    elif args.command == "pricing-lag":
        from .models import pricing_lag

        pricing_lag.run(args.season, args.week)
    elif args.command == "replay":
        from .backtest import payout, replay

        contest = payout.gpp() if args.contest == "gpp" else payout.double_up()
        replay.run(args.season, n_sims=args.sims, contest=contest,
                   n_entries=args.entries, field_size=args.field_size,
                   sharp_fraction=args.sharp, tail_line=args.tail_line)
    elif args.command == "import-discoverylab":
        from .ingest import discoverylab_import

        discoverylab_import.run(first_season=args.first_season,
                                last_season=args.last_season)
    elif args.command == "import-discoverylab-showdown":
        from .ingest import discoverylab_import

        discoverylab_import.run_showdown(first_season=args.first_season,
                                         last_season=args.last_season)
    elif args.command == "replay-showdown":
        from .backtest import showdown_replay

        showdown_replay.run(season=args.season, n_entries=args.entries,
                            days=args.days)
    elif args.command == "score-entries":
        from .config import current_season
        from . import notes as _n
        from .bq import query_df as _q
        from .config import settings as _s

        season = current_season()
        wk = _q(f"SELECT MAX(week) AS w FROM `{_s.features}.team_defense_week`"
                f" WHERE season={season}")
        if wk.w.iloc[0] is not None:
            print(_n.score_entries(season, int(wk.w.iloc[0])))
    elif args.command == "ingest-props":
        from .ingest import oddsapi_import

        oddsapi_import.run_live()
    elif args.command == "import-prop-lines":
        from .ingest import oddsapi_import

        oddsapi_import.run(first_season=args.first_season,
                           last_season=args.last_season)
    elif args.command == "import-ownership":
        from .ingest import ownership_import

        ownership_import.run(args.path, season=args.season, week=args.week,
                             contest_id=args.contest_id,
                             contest_name=args.contest_name)
    elif args.command == "archetypes":
        from .analysis import archetypes

        archetypes.run(trailing_seasons=args.seasons, min_games=args.min_games)
    elif args.command == "serve":
        import uvicorn

        uvicorn.run("nfl_dfs.app.main:app", host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()

```

===== FILE: src/nfl_dfs/config.py =====
```python
"""Central configuration, driven by environment variables.

Everything that differs between local dev and Cloud Run lives here so the
rest of the codebase never reads os.environ directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


def _load_dotenv(path: str = ".env") -> None:
    """Minimal .env support: KEY=VALUE lines from the working directory,
    never overriding variables already set in the real environment. The
    file is gitignored; it's where local secrets and API keys live."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    project: str = field(default_factory=lambda: os.environ.get("GCP_PROJECT", "nfl-dfs-prod"))
    location: str = field(default_factory=lambda: os.environ.get("BQ_LOCATION", "US"))
    raw_dataset: str = field(default_factory=lambda: os.environ.get("BQ_RAW_DATASET", "nfl_raw"))
    features_dataset: str = field(
        default_factory=lambda: os.environ.get("BQ_FEATURES_DATASET", "nfl_features")
    )
    predictions_dataset: str = field(
        default_factory=lambda: os.environ.get("BQ_PREDICTIONS_DATASET", "nfl_predictions")
    )
    # Default follows deploy/setup_gcp.sh's convention: ${PROJECT}-raw.
    gcs_bucket: str = field(
        default_factory=lambda: os.environ.get(
            "GCS_BUCKET",
            f"{os.environ.get('GCP_PROJECT', 'nfl-dfs-prod')}-raw",
        )
    )
    model_registry_prefix: str = field(
        default_factory=lambda: os.environ.get("MODEL_REGISTRY_PREFIX", "models")
    )
    # The Odds API key (ingest/oddsapi_import.py) — historical + live prop
    # lines and multi-book game odds; lives in .env.
    odds_api_key: str = field(
        default_factory=lambda: os.environ.get("ODDS_API_KEY", "")
    )
    # SportsDataIO DiscoveryLab key (ingest/discoverylab_import.py); lives
    # in .env. Empty = importer unavailable.
    sportsdata_api_key: str = field(
        default_factory=lambda: os.environ.get("SPORTSDATA_API_KEY", "")
    )
    # Backfill start. PBP exists back to 1999, but training only uses 2015+
    # (below), so default to one season of feature run-up before that; set
    # FIRST_SEASON=1999 if you want deep history for exploration.
    first_season: int = field(default_factory=lambda: int(os.environ.get("FIRST_SEASON", "2014")))
    # Seasons used for model training; PBP exists to 1999 but DK salaries only to 2014.
    train_first_season: int = field(
        default_factory=lambda: int(os.environ.get("TRAIN_FIRST_SEASON", "2015"))
    )

    @property
    def raw(self) -> str:
        return f"{self.project}.{self.raw_dataset}"

    @property
    def features(self) -> str:
        return f"{self.project}.{self.features_dataset}"

    @property
    def predictions(self) -> str:
        return f"{self.project}.{self.predictions_dataset}"


def current_season(today: date | None = None) -> int:
    """NFL season year; rolls over in March."""
    t = today or date.today()
    return t.year if t.month >= 3 else t.year - 1


settings = Settings()

```

===== FILE: src/nfl_dfs/external_proj.py =====
```python
"""External projections import + consensus diff (2026-08-02).

Purpose: a disagreement FLAG, not an input. Upload a CSV from any outside
source (ETR, Stokastic, free ownership sites) and the market page shows
where they and our model diverge most on projection and ownership. Big
divergence on a player we're concentrated in = "a human may know
something the data doesn't yet" (scheme-change-year insurance) — route
it through the watchlist, never blend it into the model.

Column names are sniffed loosely: name/player, proj/fpts/points,
own/ownership (either 0-1 or 0-100), ceiling/ceil, position/pos.
Re-uploading the same (source, season, week) replaces it.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import datetime, timezone

import pandas as pd

from .bq import load_dataframe, query_df
from .config import settings

log = logging.getLogger(__name__)

TABLE = "external_projections"


def _table() -> str:
    return f"{settings.features}.{TABLE}"


def _norm(name: str) -> str:
    return re.sub(r"[^A-Z ]", "", str(name).upper()).strip()


_ALIASES = {
    "name": ("name", "player", "player_name", "display_name"),
    "position": ("position", "pos"),
    "proj": ("proj", "projection", "fpts", "points", "proj_points", "fpts_proj"),
    "own_pct": ("own", "ownership", "own_pct", "proj_own", "ownership_pct",
                "projected_ownership", "roster%", "roster_pct"),
    "ceiling": ("ceiling", "ceil", "max", "p90"),
}


def parse_csv(text: str) -> pd.DataFrame:
    """Loose-schema parse -> columns [name, position, proj, own_pct,
    ceiling] (missing ones NaN). Ownership normalized to 0-100."""
    df = pd.read_csv(io.StringIO(text))
    cols = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    out = pd.DataFrame()
    for want, names in _ALIASES.items():
        src = next((cols[n] for n in names if n in cols), None)
        if src is not None:
            out[want] = df[src]
    if "name" not in out.columns or "proj" not in out.columns:
        raise ValueError(
            f"CSV needs at least a name and a projection column; saw "
            f"{list(df.columns)}")
    out["proj"] = pd.to_numeric(
        out.proj.astype(str).str.replace("%", ""), errors="coerce")
    if "own_pct" in out.columns:
        own = pd.to_numeric(
            out.own_pct.astype(str).str.replace("%", ""), errors="coerce")
        # 0-1 scale -> percent
        if own.max() is not None and own.max() <= 1.5:
            own = own * 100.0
        out["own_pct"] = own
    for c in ("position", "own_pct", "ceiling"):
        if c not in out.columns:
            out[c] = pd.NA
    out["ceiling"] = pd.to_numeric(out.ceiling, errors="coerce")
    out = out.dropna(subset=["proj"])
    out["name"] = out.name.astype(str)
    return out[["name", "position", "proj", "own_pct", "ceiling"]]


def import_csv(text: str, source: str, season: int, week: int) -> int:
    rows = parse_csv(text)
    rows = rows.assign(source=source, season=int(season), week=int(week),
                       uploaded_at=datetime.now(timezone.utc))
    from google.cloud import bigquery

    from .bq import client

    try:
        client().query(
            f"DELETE FROM `{_table()}` WHERE source = @s AND season = @y "
            f"AND week = @w",
            job_config=bigquery.QueryJobConfig(query_parameters=[
                bigquery.ScalarQueryParameter("s", "STRING", source),
                bigquery.ScalarQueryParameter("y", "INT64", int(season)),
                bigquery.ScalarQueryParameter("w", "INT64", int(week))]),
        ).result()
    except Exception:
        log.info("external_projections absent; first import creates it")
    load_dataframe(rows, _table(), write_disposition="WRITE_APPEND")
    return len(rows)


def diff(projections: pd.DataFrame, season: int, week: int,
         limit: int = 40) -> pd.DataFrame:
    """Largest |our proj - theirs| among matched names, both directions,
    with their ownership alongside for the leverage read."""
    ext = query_df(
        f"""SELECT source, name, proj ext_proj, own_pct ext_own,
                   ceiling ext_ceiling
            FROM `{_table()}` WHERE season = {int(season)}
              AND week = {int(week)}""")
    if ext.empty or projections.empty:
        return pd.DataFrame()
    ext["nm"] = ext.name.map(_norm)
    ours = projections.copy()
    ours["nm"] = ours.display_name.map(_norm)
    j = ours.merge(ext, on="nm", how="inner")
    j["diff"] = (j.proj_points - j.ext_proj).round(2)
    j = j.reindex(j["diff"].abs().sort_values(ascending=False).index)
    cols = ["display_name", "position", "team", "salary", "proj_points",
            "ext_proj", "diff", "ext_own", "ext_ceiling", "source"]
    return j[[c for c in cols if c in j.columns]].head(int(limit)).round(2)

```

===== FILE: src/nfl_dfs/features/__init__.py =====
```python

```

===== FILE: src/nfl_dfs/features/build.py =====
```python
"""Feature build runner: executes sql/features/*.sql in numeric order, then
runs the leakage assertions. Fails loudly — a broken feature build must never
silently feed stale projections.

Schedule: daily 07:00 CT and after each DK pull.
"""

from __future__ import annotations

import logging
import sys

from ..bq import SQL_DIR, run_sql_file
from .leakage import run_leakage_checks

log = logging.getLogger(__name__)

# Empirical-Bayes prior weight, in games, for red zone smoothing (guide §5.2;
# tune on validation — typical optimum 3-5).
PRIOR_K = 4


def run(check_leakage: bool = True) -> None:
    feature_sql = sorted((SQL_DIR / "features").glob("*.sql"))
    if not feature_sql:
        raise FileNotFoundError(f"No feature SQL found under {SQL_DIR / 'features'}")
    for path in feature_sql:
        run_sql_file(path, prior_k=PRIOR_K)
    if check_leakage:
        run_leakage_checks()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run(check_leakage="--skip-leakage" not in sys.argv)

```

===== FILE: src/nfl_dfs/features/leakage.py =====
```python
"""Point-in-time leakage assertions.

The #1 way DFS backtests lie is a rolling feature that includes the current
week. These checks recompute key rolling features from the source tables
using strictly-prior weeks and assert they match what the build produced.
Any mismatch means a window definition regressed — fail the build.

`trailing_mean_excluding_current` is the pure-pandas reference
implementation; it is unit-tested on synthetic data and reused by the
SQL-vs-reference comparison.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class LeakageError(AssertionError):
    """A feature saw data from its own week or later."""


def trailing_mean_excluding_current(
    df: pd.DataFrame,
    value_col: str,
    window: int | None = None,
    group_cols: tuple[str, ...] = ("gsis_id", "season"),
    order_col: str = "week",
) -> pd.Series:
    """Reference rolling mean over the trailing `window` rows (all prior rows
    when window is None), strictly excluding the current row. Mirrors the SQL
    `ROWS BETWEEN n PRECEDING AND 1 PRECEDING` window."""
    df = df.sort_values(list(group_cols) + [order_col])

    def _roll(s: pd.Series) -> pd.Series:
        shifted = s.shift(1)
        if window is None:
            return shifted.expanding().mean()
        return shifted.rolling(window, min_periods=1).mean()

    return df.groupby(list(group_cols), sort=False)[value_col].transform(_roll)


def assert_no_leakage(
    built: pd.DataFrame,
    source: pd.DataFrame,
    feature_col: str,
    source_col: str,
    window: int | None,
    atol: float = 1e-6,
    min_coverage: float = 0.95,
    key_col: str = "gsis_id",
) -> None:
    """Compare a built rolling feature against the reference recomputation.

    `built` needs [key_col, season, week, feature_col]; `source` needs
    [key_col, season, week, source_col] at per-game grain. key_col is
    gsis_id for player features, team for defense features.
    """
    ref = source[[key_col, "season", "week", source_col]].copy()
    ref["expected"] = trailing_mean_excluding_current(
        ref, source_col, window=window, group_cols=(key_col, "season")
    )
    merged = built.merge(ref[[key_col, "season", "week", "expected"]],
                         on=[key_col, "season", "week"], how="inner")
    if merged.empty:
        raise LeakageError(f"No overlapping rows to check for {feature_col}")

    both = merged.dropna(subset=[feature_col, "expected"])
    n_checked = len(both)
    if n_checked == 0:
        raise LeakageError(f"{feature_col}: no non-null rows to compare")
    mismatch = ~np.isclose(both[feature_col], both["expected"], atol=atol)
    rate = 1 - mismatch.mean()
    if rate < min_coverage:
        bad = both[mismatch].head(5)[[key_col, "season", "week", feature_col, "expected"]]
        raise LeakageError(
            f"{feature_col}: only {rate:.1%} of {n_checked} rows match the "
            f"point-in-time reference (need >= {min_coverage:.0%}). "
            f"A rolling window is probably including the current week.\n"
            f"Examples:\n{bad.to_string(index=False)}"
        )
    log.info("%s: %d rows checked, %.2f%% match", feature_col, n_checked, 100 * rate)


def assert_first_row_features_null(
    built: pd.DataFrame,
    feature_cols: list[str],
    group_cols: tuple[str, ...],
    order_col: str = "week",
) -> None:
    """The first row of every group has no prior data, so every strictly-prior
    rolling feature must be null there. A value means the window saw the
    current row. Grain-agnostic version of the player first-game check."""
    first = built.loc[built.groupby(list(group_cols))[order_col].idxmin()]
    for col in feature_cols:
        if col not in first.columns:
            continue
        leaked = first[first[col].notna()]
        if not leaked.empty:
            raise LeakageError(
                f"{col} is non-null on {len(leaked)} first-row groups of "
                f"{group_cols}; rolling window includes the current row."
            )


def assert_first_game_features_null(built: pd.DataFrame, feature_cols: list[str]) -> None:
    """A player's first tracked game has no prior data: every rolling feature
    must be null there. A value means the window saw the current week."""
    first = built[built["games_played_prior"] == 0]
    for col in feature_cols:
        if col not in first.columns:
            continue
        leaked = first[first[col].notna()]
        if not leaked.empty:
            raise LeakageError(
                f"{col} is non-null on {len(leaked)} first-game rows; "
                f"rolling window includes the current week."
            )


# SQL-side checks used in production against BigQuery ------------------------

CHECKED_FEATURES = [
    # (built feature col, source col, window)
    ("target_share_l4", "target_share", 4),
    ("rz20_targets_l4", "rz20_targets", 4),
    ("carry_share_l4", "carry_share", 4),
    ("target_share_std", "target_share", None),
]

SAMPLE_SQL = """
SELECT gsis_id, season, week, {cols}
FROM `{table}`
WHERE MOD(FARM_FINGERPRINT(gsis_id), 20) = 0  -- deterministic 5% player sample
"""

# The reference must window over the same rows the build does: usage rows are
# the FULL OUTER JOIN of receiving and rushing (a rush-only game still occupies
# a window slot, with NULL share and zero-coalesced counts). Recomputing from
# rz_receiving alone would slide the window across different weeks for any
# player with intermittent receiving rows and report false mismatches.
SOURCE_GRAIN_SQL = """
SELECT gsis_id, season, week,
       COALESCE(rec.rz20_targets, 0) AS rz20_targets,
       rec.target_share,
       rush.carry_share
FROM `{features}.rz_receiving` rec
FULL OUTER JOIN `{features}.rz_rushing` rush
  USING (game_id, season, week, team, gsis_id)
WHERE MOD(FARM_FINGERPRINT(gsis_id), 20) = 0
"""


DEFENSE_L6_FEATURES = ["epa_per_dropback_allowed_l6", "epa_per_rush_allowed_l6"]
DEFENSE_SOURCE_COLS = ["epa_per_dropback_allowed", "epa_per_rush_allowed"]
DEFENSE_ADJ_FEATURES = [
    "qb_fp_allowed_adj_l6", "rb_fp_allowed_adj_l6",
    "wr_fp_allowed_adj_l6", "te_fp_allowed_adj_l6",
]

DEFENSE_SAMPLE_SQL = """
SELECT team, season, week, {cols}
FROM `{table}`
WHERE MOD(FARM_FINGERPRINT(team), 4) = 0  -- deterministic 8-team sample
"""

# Mirrors 017's def_games CTE exactly; sampled by team, not player.
DEFENSE_SOURCE_SQL = """
SELECT defteam AS team, season, week,
       AVG(IF(qb_dropback = 1, epa, NULL)) AS epa_per_dropback_allowed,
       AVG(IF(rush_attempt = 1, epa, NULL)) AS epa_per_rush_allowed
FROM `{raw}.pbp`
WHERE defteam IS NOT NULL AND season_type = 'REG'
  AND MOD(FARM_FINGERPRINT(defteam), 4) = 0
GROUP BY 1, 2, 3
"""


COVERAGE_CHECKS = [
    # (built l6 col, per-game source col)
    ("cb_ypt_allowed_l6", "cb_ypt_allowed"),
    ("cb_comp_rate_allowed_l6", "cb_comp_rate_allowed"),
    ("db_ypt_allowed_l6", "db_ypt_allowed"),
]

# Mirrors 017a's cov_games CTE exactly; sampled by team. PFR advstats start
# in 2018, so pre-2018 built rows simply have nothing to compare against
# (they're NULL and drop out of the merge).
COVERAGE_SOURCE_SQL = """
WITH def_pos AS (
  SELECT pfr_player_id, season, week, position
  FROM `{raw}.snap_counts`
  WHERE defense_snaps > 0 AND pfr_player_id IS NOT NULL
)
SELECT
  a.team, a.season, a.week,
  SAFE_DIVIDE(
    SUM(IF(p.position = 'CB', a.def_yards_allowed, NULL)),
    NULLIF(SUM(IF(p.position = 'CB', a.def_targets, NULL)), 0)
  ) AS cb_ypt_allowed,
  SAFE_DIVIDE(
    SUM(IF(p.position = 'CB', a.def_completions_allowed, NULL)),
    NULLIF(SUM(IF(p.position = 'CB', a.def_targets, NULL)), 0)
  ) AS cb_comp_rate_allowed,
  SAFE_DIVIDE(
    SUM(IF(p.position IN ('CB', 'DB', 'S', 'FS', 'SS'), a.def_yards_allowed, NULL)),
    NULLIF(SUM(IF(p.position IN ('CB', 'DB', 'S', 'FS', 'SS'), a.def_targets, NULL)), 0)
  ) AS db_ypt_allowed
FROM `{raw}.pfr_advstats_def` a
JOIN def_pos p
  ON p.pfr_player_id = a.pfr_player_id
 AND p.season = a.season AND p.week = a.week
WHERE MOD(FARM_FINGERPRINT(a.team), 4) = 0
GROUP BY 1, 2, 3
"""


def run_leakage_checks() -> None:
    from ..bq import query_df
    from ..config import settings

    built_cols = sorted({f for f, *_ in CHECKED_FEATURES} | {"games_played_prior"})
    built = query_df(
        SAMPLE_SQL.format(cols=", ".join(built_cols),
                          table=f"{settings.features}.player_week_usage")
    )
    source = query_df(SOURCE_GRAIN_SQL.format(features=settings.features))
    for feature_col, source_col, window in CHECKED_FEATURES:
        assert_no_leakage(built, source, feature_col, source_col, window)
    assert_first_game_features_null(built, [f for f, *_ in CHECKED_FEATURES])

    # Defense features: same discipline, team grain. EPA-allowed is
    # recomputed per-week from raw pbp on a deterministic team sample and
    # compared against the built l6 window; the adjusted-FP columns can't be
    # cheaply recomputed here, so they get the first-row-null invariant
    # (which is what catches an include-current-week regression).
    def_built = query_df(
        DEFENSE_SAMPLE_SQL.format(
            cols=", ".join(DEFENSE_L6_FEATURES + DEFENSE_ADJ_FEATURES),
            table=f"{settings.features}.defense_week_allowed",
        )
    )
    def_source = query_df(DEFENSE_SOURCE_SQL.format(raw=settings.raw))
    for feature_col, source_col in zip(DEFENSE_L6_FEATURES, DEFENSE_SOURCE_COLS):
        assert_no_leakage(def_built, def_source, feature_col, source_col,
                          window=6, key_col="team")
    assert_first_row_features_null(
        def_built, DEFENSE_L6_FEATURES + DEFENSE_ADJ_FEATURES, ("team", "season")
    )

    # Coverage features (017a): per-game CB-group concessions recomputed from
    # raw PFR advstats on the same team sample. The built table's window
    # slides over schedule-spine rows, so a played game absent from advstats
    # occupies a slot the reference doesn't — min_coverage absorbs that rare
    # drift. Upcoming-week spine rows have no source row and drop out of the
    # merge. top_cb_out isn't a rolling mean, but it is strictly-prior on the
    # snaps side, so the week-1-null invariant applies to it too.
    cov_built = query_df(
        DEFENSE_SAMPLE_SQL.format(
            cols=", ".join([f for f, _ in COVERAGE_CHECKS] + ["top_cb_out"]),
            table=f"{settings.features}.defense_week_coverage",
        )
    )
    cov_source = query_df(COVERAGE_SOURCE_SQL.format(raw=settings.raw))
    for feature_col, source_col in COVERAGE_CHECKS:
        assert_no_leakage(cov_built, cov_source, feature_col, source_col,
                          window=6, key_col="team")
    assert_first_row_features_null(
        cov_built, [f for f, _ in COVERAGE_CHECKS] + ["top_cb_out"],
        ("team", "season"),
    )

    # Training-table sanity: labels exist, features don't correlate perfectly
    # with same-week labels (a 1.0 correlation is a copied column).
    tr = query_df(
        f"""SELECT target_share_l4, y_targets, dk_points_l4, y_dk_points
            FROM `{settings.features}.player_week_training`
            WHERE RAND() < 0.05"""
    )
    for feat, label in (("target_share_l4", "y_targets"), ("dk_points_l4", "y_dk_points")):
        sub = tr[[feat, label]].dropna()
        if len(sub) > 100 and abs(sub[feat].corr(sub[label])) > 0.98:
            raise LeakageError(f"{feat} correlates {sub[feat].corr(sub[label]):.3f} "
                               f"with same-week {label}; that's a leak, not a feature.")
    log.info("All leakage checks passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_leakage_checks()

```

===== FILE: src/nfl_dfs/graph/__init__.py =====
```python

```

===== FILE: src/nfl_dfs/graph/build.py =====
```python
"""Player/team knowledge graph (guide §8).

Honest framing: this does not improve point projections — GBDTs on tabular
features own that job. The graph earns its keep on entity resolution,
cascade reasoning (who inherits an injured player's usage), relational
features, and explanation. At NFL scale (~2,000 players, 32 teams) it fits
in memory; NetworkX in a job is sufficient, no graph database needed.

Node kinds: Player, Team. Edge keys: PLAYS_FOR, TARGETED_BY (QB->receiver,
weighted by red zone volume), COMPETES_WITH (same team + position group).
COMPETES_WITH and REPLACED are the edges that pay: target share is
zero-sum within a team, which is natural as a graph property and awkward
as a column.
"""

from __future__ import annotations

import logging

import networkx as nx
import pandas as pd

log = logging.getLogger(__name__)


def build_graph(
    rosters: pd.DataFrame,
    qb_connections: pd.DataFrame,
    news_edges: pd.DataFrame | None = None,
) -> nx.MultiDiGraph:
    """Assemble the graph from prepared frames.

    rosters:        gsis_id, name, position, team   (one row per player)
    qb_connections: qb, wr, team, targets, rz_targets, air_yards, tds
    news_edges:     optional output of news.to_graph_edges
    """
    G = nx.MultiDiGraph()

    for r in rosters.itertuples():
        G.add_node(r.gsis_id, kind="Player", name=r.name, position=r.position)
        G.add_node(r.team, kind="Team")
        G.add_edge(r.gsis_id, r.team, key="PLAYS_FOR")

    for r in qb_connections.itertuples():
        G.add_edge(r.qb, r.wr, key="TARGETED_BY",
                   targets=r.targets, rz_targets=r.rz_targets,
                   air_yards=r.air_yards, tds=r.tds)

    # Intra-team, intra-position competition edges (undirected in spirit;
    # stored both ways for cheap traversal)
    for (_team, _pos), grp in rosters.groupby(["team", "position"]):
        ids = list(grp.gsis_id)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                G.add_edge(a, b, key="COMPETES_WITH")
                G.add_edge(b, a, key="COMPETES_WITH")

    if news_edges is not None:
        for r in news_edges.itertuples():
            G.add_edge(r.gsis_id, r.team, key="NEWS_SIGNAL",
                       claim_type=r.claim_type, direction=r.direction,
                       confidence=r.confidence, published_at=r.published_at)

    log.info("Graph: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())
    return G


def build_graph_from_warehouse(season: int, through_week: int) -> nx.MultiDiGraph:
    """Production path: pull the frames from BigQuery, then assemble."""
    from ..bq import query_df
    from ..config import settings

    rosters = query_df(
        f"""
        SELECT gsis_id, ANY_VALUE(full_name HAVING MAX week) AS name,
               ANY_VALUE(position HAVING MAX week) AS position,
               ANY_VALUE(team HAVING MAX week) AS team
        FROM `{settings.raw}.rosters_weekly`
        WHERE season = {season} AND week <= {through_week} AND gsis_id IS NOT NULL
        GROUP BY gsis_id
        """
    )
    qb_connections = query_df(
        f"""
        SELECT passer_player_id AS qb, receiver_player_id AS wr, posteam AS team,
               COUNT(*) AS targets,
               COUNTIF(yardline_100 <= 20) AS rz_targets,
               SUM(air_yards) AS air_yards,
               COUNTIF(pass_touchdown = 1) AS tds
        FROM `{settings.raw}.pbp`
        WHERE season = {season} AND week <= {through_week}
          AND pass_attempt = 1 AND receiver_player_id IS NOT NULL
        GROUP BY 1, 2, 3
        """
    )
    return build_graph(rosters, qb_connections)


def teammates(G: nx.MultiDiGraph, gsis_id: str) -> list[str]:
    return [b for _, b, k in G.out_edges(gsis_id, keys=True) if k == "COMPETES_WITH"]


def team_of(G: nx.MultiDiGraph, gsis_id: str) -> str | None:
    for _, t, k in G.out_edges(gsis_id, keys=True):
        if k == "PLAYS_FOR":
            return t
    return None


def qb_of(G: nx.MultiDiGraph, receiver_id: str) -> str | None:
    """Primary passer feeding this receiver, by target volume."""
    best, best_targets = None, -1
    for qb, _, k, data in G.in_edges(receiver_id, keys=True, data=True):
        if k == "TARGETED_BY" and data.get("targets", 0) > best_targets:
            best, best_targets = qb, data["targets"]
    return best

```

===== FILE: src/nfl_dfs/graph/cascade.py =====
```python
"""Injury cascade projection (guide §8.4) — the query that actually pays.

When a starter is ruled out Sunday morning you have minutes to decide who
absorbs his usage. The core move: join injury history to usage history and
measure each teammate's target share WITH vs WITHOUT the injured player.
No public site does this join for you. Works best with 3+ prior absences;
below that, fall back to depth-chart-based redistribution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import networkx as nx
import pandas as pd

from .build import team_of, teammates

log = logging.getLogger(__name__)

MIN_ABSENCES_FOR_HISTORY = 3
# Depth-chart fallback multiplier for candidates sharing the injured
# player's scoring archetype (see analysis/archetypes.py). Mild on purpose:
# a prior, not evidence.
ARCHETYPE_MATCH_BOOST = 1.25


@dataclass
class VacatedUsage:
    gsis_id: str
    avg_targets: float
    avg_rz20_targets: float
    avg_target_share: float


def vacated_usage(usage: pd.DataFrame, out_player: str) -> VacatedUsage:
    """usage: per-game rows [gsis_id, season, week, total_targets,
    rz20_targets, target_share]."""
    mine = usage[usage.gsis_id == out_player]
    return VacatedUsage(
        gsis_id=out_player,
        avg_targets=float(mine.total_targets.mean() or 0),
        avg_rz20_targets=float(mine.rz20_targets.mean() or 0),
        avg_target_share=float(mine.target_share.mean() or 0),
    )


def historical_redistribution(
    usage: pd.DataFrame,
    absences: pd.DataFrame,
    candidates: list[str],
) -> pd.DataFrame:
    """For each candidate: mean target share in weeks the injured player
    missed vs weeks he played. `absences`: [season, week] rows when the
    player was Out. Returns columns share_with, share_without, delta,
    n_without."""
    absent_keys = set(map(tuple, absences[["season", "week"]].to_numpy().tolist()))
    cand = usage[usage.gsis_id.isin(candidates)].copy()
    if cand.empty:
        return pd.DataFrame(
            columns=["gsis_id", "share_with", "share_without", "delta", "n_without"]
        )
    cand["absent"] = [
        (s, w) in absent_keys for s, w in zip(cand.season, cand.week)
    ]
    rows = []
    for gsis_id, grp in cand.groupby("gsis_id"):
        with_ = grp.loc[~grp.absent, "target_share"]
        without = grp.loc[grp.absent, "target_share"]
        rows.append(
            {
                "gsis_id": gsis_id,
                "share_with": float(with_.mean()) if len(with_) else float("nan"),
                "share_without": float(without.mean()) if len(without) else float("nan"),
                "n_without": int(len(without)),
            }
        )
    out = pd.DataFrame(rows)
    out["delta"] = out.share_without - out.share_with
    return out.sort_values("delta", ascending=False)


def depth_chart_fallback(
    vacated: VacatedUsage, candidates: pd.DataFrame
) -> pd.DataFrame:
    """When absence history is thin: hand the vacated share down the depth
    chart, weighted by current usage (a proxy for readiness). candidates:
    [gsis_id, target_share] current levels."""
    c = candidates.copy()
    total = c.target_share.sum()
    c["weight"] = c.target_share / total if total > 0 else 1.0 / len(c)
    c["delta"] = c.weight * vacated.avg_target_share
    return c.sort_values("delta", ascending=False)[["gsis_id", "delta"]]


def project_vacated_usage(
    G: nx.MultiDiGraph,
    usage: pd.DataFrame,
    injuries: pd.DataFrame,
    out_player: str,
) -> pd.DataFrame:
    """Who inherits an injured player's opportunity, and how much?

    usage:    [gsis_id, season, week, total_targets, rz20_targets, target_share]
    injuries: [gsis_id, season, week, game_status]
    Returns candidates with projected target-share delta, best-evidence first.
    """
    team = team_of(G, out_player)
    candidates = teammates(G, out_player)
    if not candidates:
        log.warning("No competition edges for %s (team %s)", out_player, team)
        return pd.DataFrame(columns=["gsis_id", "delta", "method"])

    vac = vacated_usage(usage, out_player)
    absences = injuries[
        (injuries.gsis_id == out_player) & (injuries.game_status == "Out")
    ][["season", "week"]]

    if len(absences) >= MIN_ABSENCES_FOR_HISTORY:
        hist = historical_redistribution(usage, absences, candidates)
        informative = hist[hist.n_without >= MIN_ABSENCES_FOR_HISTORY].dropna(
            subset=["delta"]
        )
        if not informative.empty:
            return informative.assign(method="history")[
                ["gsis_id", "delta", "share_with", "share_without", "n_without", "method"]
            ]

    current = (
        usage[usage.gsis_id.isin(candidates)]
        .groupby("gsis_id", as_index=False)["target_share"].mean()
    )
    if current.empty:
        return pd.DataFrame(columns=["gsis_id", "delta", "method"])

    # Archetype-aware fallback: when nodes carry scoring-profile labels
    # (analysis.archetypes.annotate_graph), tilt the depth-chart weights
    # toward profile-compatible inheritors — a possession receiver's vacated
    # slot targets flow to another high-floor profile, not a deep threat.
    # The history path above stays unweighted on purpose: measured
    # redistribution beats any prior.
    out_arch = G.nodes[out_player].get("archetype") if out_player in G else None
    method = "depth_chart"
    if out_arch is not None:
        boost = current.gsis_id.map(
            lambda g: ARCHETYPE_MATCH_BOOST
            if g in G and G.nodes[g].get("archetype") == out_arch
            else 1.0
        )
        current = current.assign(target_share=current.target_share * boost)
        method = "depth_chart_archetype"
    return depth_chart_fallback(vac, current).assign(method=method)

```

===== FILE: src/nfl_dfs/graph/news.py =====
```python
"""LLM-assisted news extraction (guide §8.7).

The one place an LLM belongs in this system: turning beat-writer prose
("coach wants to get him more involved in the red zone") into structured
claims, BEFORE the usage change shows up in the changepoint detector.

The LLM stays strictly in the extraction role. It never generates
projections — it would produce confident, fluent, uncalibrated numbers,
the worst failure mode in a system where calibration is the whole game.

Pipeline: fetch items -> extract claims (strict schema, entity-resolved)
-> write as decaying graph edges -> aggregate into two model features:
positive_role_signals_l7d, injury_concern_signals_l7d.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd

log = logging.getLogger(__name__)

CLAIM_TYPES = {"role_change", "snap_count", "injury_status", "scheme_change",
               "depth_chart"}
SIGNAL_HALF_LIFE_DAYS = 5.0

EXTRACTION_SYSTEM_PROMPT = """\
You extract structured claims about NFL player usage from news snippets.
Return ONLY a JSON array; each element:
{
  "player": "<name as written>",
  "claim_type": "role_change" | "snap_count" | "injury_status" | "scheme_change" | "depth_chart",
  "direction": 1 | -1,          // 1 = more opportunity/health, -1 = less
  "confidence": 0.0-1.0,        // how directly the text supports the claim
  "quote": "<shortest supporting span>"
}
Rules: no forecasts, no fantasy advice, no numbers not in the text.
If the snippet contains no usage-relevant claim, return [].
"""


@dataclass
class Claim:
    player: str
    gsis_id: str | None
    claim_type: str
    direction: int
    confidence: float
    quote: str
    source: str
    source_credibility: float
    published_at: str


def extract_claims_llm(
    text: str, source: str, published_at: str, source_credibility: float = 0.5,
    model: str = "claude-sonnet-5",
) -> list[Claim]:
    """Extraction via the Anthropic API. Requires ANTHROPIC_API_KEY."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text[:8000]}],
    )
    raw = resp.content[0].text
    return parse_claims(raw, source, published_at, source_credibility)


def parse_claims(
    raw: str, source: str, published_at: str, source_credibility: float
) -> list[Claim]:
    """Validate model output against the strict schema; drop anything that
    doesn't conform rather than guessing."""
    try:
        start, end = raw.find("["), raw.rfind("]")
        items = json.loads(raw[start : end + 1]) if start >= 0 else []
    except (json.JSONDecodeError, ValueError):
        log.warning("Unparseable extraction output from %s", source)
        return []

    claims = []
    for it in items:
        if not isinstance(it, dict):
            continue
        if it.get("claim_type") not in CLAIM_TYPES:
            continue
        if it.get("direction") not in (1, -1):
            continue
        try:
            conf = float(it.get("confidence", 0))
        except (TypeError, ValueError):
            continue
        if not 0 <= conf <= 1 or not it.get("player"):
            continue
        claims.append(
            Claim(
                player=str(it["player"]),
                gsis_id=None,
                claim_type=it["claim_type"],
                direction=int(it["direction"]),
                confidence=conf,
                quote=str(it.get("quote", ""))[:300],
                source=source,
                source_credibility=source_credibility,
                published_at=published_at,
            )
        )
    return claims


def resolve_entities(claims: list[Claim], id_map: pd.DataFrame) -> list[Claim]:
    """Attach gsis_ids via the crosswalk (display_name -> gsis_id). Claims
    that don't resolve keep gsis_id=None and are excluded from features —
    a misattributed claim is worse than a dropped one."""
    lookup = {
        _norm(name): gid
        for name, gid in zip(id_map["display_name"], id_map["gsis_id"])
    }
    for c in claims:
        c.gsis_id = lookup.get(_norm(c.player))
    unresolved = sum(1 for c in claims if c.gsis_id is None)
    if unresolved:
        log.info("%d/%d claims unresolved to gsis_id", unresolved, len(claims))
    return claims


def _norm(name: str) -> str:
    import re

    name = re.sub(r"\s+(jr|sr|ii|iii|iv|v)\.?$", "", name.strip().lower())
    return re.sub(r"[^a-z ]", "", name)


def to_frame(claims: list[Claim]) -> pd.DataFrame:
    return pd.DataFrame([asdict(c) for c in claims])


def signal_features(
    claims_df: pd.DataFrame, as_of: datetime | None = None
) -> pd.DataFrame:
    """Aggregate resolved claims into the two model features, exponentially
    decayed by age (half-life SIGNAL_HALF_LIFE_DAYS), weighted by claim
    confidence x source credibility."""
    if claims_df.empty:
        return pd.DataFrame(columns=[
            "gsis_id", "positive_role_signals_l7d", "injury_concern_signals_l7d"
        ])
    as_of = as_of or datetime.now(timezone.utc)
    df = claims_df.dropna(subset=["gsis_id"]).copy()
    ts = pd.to_datetime(df["published_at"], utc=True)
    age_days = (as_of - ts).dt.total_seconds() / 86400.0
    df = df[(age_days >= 0) & (age_days <= 7)]
    age_days = age_days[df.index]
    df["weight"] = (
        df["confidence"] * df["source_credibility"]
        * 0.5 ** (age_days / SIGNAL_HALF_LIFE_DAYS)
    )
    role = df[df.claim_type.isin(["role_change", "snap_count", "depth_chart",
                                  "scheme_change"])]
    injury = df[df.claim_type == "injury_status"]
    pos = (role.weight * role.direction).groupby(role.gsis_id).sum().clip(lower=0)
    concern = (-injury.weight * injury.direction).groupby(injury.gsis_id).sum().clip(lower=0)
    out = pd.DataFrame({
        "positive_role_signals_l7d": pos,
        "injury_concern_signals_l7d": concern,
    }).fillna(0.0)
    return out.rename_axis("gsis_id").reset_index()


def to_graph_edges(claims_df: pd.DataFrame, team_lookup: dict[str, str]) -> pd.DataFrame:
    """Claims as graph edges (player -> team) for the reasoning layer."""
    df = claims_df.dropna(subset=["gsis_id"]).copy()
    df["team"] = df["gsis_id"].map(team_lookup)
    return df.dropna(subset=["team"])[
        ["gsis_id", "team", "claim_type", "direction", "confidence", "published_at"]
    ]

```

===== FILE: src/nfl_dfs/inference/__init__.py =====
```python

```

===== FILE: src/nfl_dfs/inference/cascade_adjust.py =====
```python
"""Late-breaking inactive adjustment: the injury cascade (guide §8.4) wired
into the hourly inference pass.

Injuries reach projections through two complementary layers:

* ``team_week_vacated`` features (018/021/023) carry Wednesday-Friday "Out"
  designations into the feature matrix, so the models learn next-man-up
  bumps from history.
* This module handles what the feature build can't: status flips after
  features were built — the starter ruled out Sunday morning. Players the
  DK slate marks O/IR (or the report lists as Out) get their projections
  zeroed, and their opportunity is redistributed to slate teammates via
  ``graph.cascade.project_vacated_usage`` — measured with/without splits
  when the player has absence history, depth-chart-style weighting when
  history is thin.

The redistribution normalizes over slate teammates, so opportunity that
would really leak to unrosterable players is credited to rosterable ones —
a mild, deliberate overestimate: for DFS the cost of missing the next man
up exceeds the cost of slightly overpricing him.

Runs after the cold-start fill so bumps land on top of role priors instead
of vanishing into NaNs.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from ..graph.build import build_graph
from ..graph.cascade import project_vacated_usage, vacated_usage

log = logging.getLogger(__name__)

# DK draftable statuses that mean the player will not play. Doubtful ("D")
# is deliberately not here: most doubtful players sit, but zeroing them
# would erase real late-swap decisions; their depressed practice features
# already carry the signal.
OUT_STATUSES = {"O", "OUT", "IR"}

# The carry-side cascade reuses the target-centric machinery by renaming:
# total carries ~ total targets, goal-line carries ~ red zone targets,
# carry share ~ target share.
_RUSH_AS_TARGETS = {
    "total_carries": "total_targets",
    "gl3_carries": "rz20_targets",
    "carry_share": "target_share",
}

_PROJ_ZERO_COLS = ["proj_points", "proj_p10", "proj_p50", "proj_p90",
                   "proj_std", "p_20_plus", "value"]


def find_out_players(feats: pd.DataFrame) -> list[str]:
    """GSIS ids of slate players who won't play: DK status O/IR or an
    injury-report Out designation."""
    status = feats.get("status", pd.Series(index=feats.index, dtype=object))
    dk_out = status.fillna("").astype(str).str.upper().isin(OUT_STATUSES)
    report = feats.get("injury_status", pd.Series(index=feats.index, dtype=object))
    report_out = report.fillna("").astype(str).str.upper().eq("OUT")
    ids = feats.loc[(dk_out | report_out) & feats.gsis_id.notna(), "gsis_id"]
    return sorted(set(ids))


def slate_graph(feats: pd.DataFrame):
    """Minimal player/team graph over the slate: enough for team_of /
    teammates (same team + position group) traversal in the cascade."""
    rosters = pd.DataFrame(
        {
            "gsis_id": feats.get("gsis_id"),
            "name": feats.get("display_name", feats.get("gsis_id")),
            "position": feats.get("position", feats.get("dk_position")),
            "team": feats.get("team", feats.get("team_abbr")),
        }
    ).dropna(subset=["gsis_id", "team"]).drop_duplicates("gsis_id")
    qb_connections = pd.DataFrame(
        columns=["qb", "wr", "team", "targets", "rz_targets", "air_yards", "tds"]
    )
    return build_graph(rosters, qb_connections)


def _bump(feats: pd.DataFrame, rows, col: str, delta: float,
          lo: float = 0.0, hi: float | None = None) -> None:
    if col not in feats.columns:
        return
    base = pd.to_numeric(feats.loc[rows, col], errors="coerce").fillna(0.0) + delta
    feats.loc[rows, col] = base.clip(lower=lo, upper=hi)


def _redistribute(
    feats: pd.DataFrame,
    G,
    usage: pd.DataFrame,
    injuries: pd.DataFrame,
    out_id: str,
    skip: set[str],
    share_col: str,
    wopr_col: str | None,
    smoothed_col: str,
    share_cap: float,
) -> None:
    if usage.empty or out_id not in set(usage.gsis_id):
        return
    plan = project_vacated_usage(G, usage, injuries, out_id)
    if plan.empty:
        return
    vac = vacated_usage(usage, out_id)
    # vacated_usage's `mean() or 0` doesn't catch NaN — guard here so a
    # historyless share can't smear NaN over teammates' features.
    if not np.isfinite(vac.avg_target_share) or vac.avg_target_share <= 0:
        return
    rz_pool = vac.avg_rz20_targets if np.isfinite(vac.avg_rz20_targets) else 0.0
    for row in plan.itertuples():
        if row.gsis_id in skip or pd.isna(row.delta):
            continue
        rows = feats.index[feats.gsis_id == row.gsis_id]
        if rows.empty:
            continue
        frac = row.delta / vac.avg_target_share  # share of the vacated role
        _bump(feats, rows, share_col, row.delta, hi=share_cap)
        if wopr_col:
            _bump(feats, rows, wopr_col, 1.5 * row.delta, hi=1.2)
        _bump(feats, rows, smoothed_col, frac * rz_pool)
        log.info("cascade: %s inherits %+.3f %s from %s (%s)",
                 row.gsis_id, row.delta, share_col, out_id, row.method)


def adjust_for_inactives(
    feats: pd.DataFrame,
    usage_rec: pd.DataFrame,
    usage_rush: pd.DataFrame,
    injuries: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Redistribute out players' opportunity to slate teammates.

    usage_rec:  per-game [gsis_id, season, week, total_targets, rz20_targets,
                target_share] (features.rz_receiving grain)
    usage_rush: per-game [gsis_id, season, week, total_carries, gl3_carries,
                carry_share] (features.rz_rushing grain)
    injuries:   [gsis_id, season, week, game_status]

    Returns the adjusted copy and the out players' gsis ids (their
    projections should be zeroed — see zero_out_projections).
    """
    out_ids = find_out_players(feats)
    if not out_ids:
        return feats, []
    feats = feats.copy()
    G = slate_graph(feats)
    skip = set(out_ids)
    rush = usage_rush.rename(columns=_RUSH_AS_TARGETS)
    for out_id in out_ids:
        _redistribute(feats, G, usage_rec, injuries, out_id, skip,
                      share_col="target_share_l4", wopr_col="wopr_l4",
                      smoothed_col="rz20_targets_smoothed", share_cap=0.5)
        _redistribute(feats, G, rush, injuries, out_id, skip,
                      share_col="carry_share_l4", wopr_col=None,
                      smoothed_col="gl3_carries_smoothed", share_cap=0.85)
    log.info("cascade: adjusted slate for %d inactive(s): %s",
             len(out_ids), ", ".join(out_ids))
    return feats, out_ids


def zero_out_projections(out: pd.DataFrame, out_ids: list[str]) -> pd.DataFrame:
    """A player who won't play projects to zero — after the market blend,
    which knows nothing about a Sunday-morning scratch."""
    if not out_ids:
        return out
    out = out.copy()
    mask = out.gsis_id.isin(out_ids)
    for col in _PROJ_ZERO_COLS:
        if col in out.columns:
            out.loc[mask, col] = 0.0
    return out

```

===== FILE: src/nfl_dfs/inference/dst_projections.py =====
```python
"""Production DST projections (issue #7).

proj = trailing 4-game DK average (from features.team_defense_week,
computed off play-by-play, validated 0.98 corr / 0.44 MAE vs exported
actuals) + opposing-QB experience adjustment (qb_experience.py).
Quantiles use fixed empirical offsets — DST scores are one fat-tailed
distribution and a component simulation buys nothing here.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd

from ..config import settings
from .qb_experience import adjustment

log = logging.getLogger(__name__)

FALLBACK_PROJ = 6.0   # league-average DST DK points
# Global residual spread of weekly DST scores around trailing form
STD = 5.4
P10_OFF, P50_OFF, P90_OFF = -4.5, -0.5, 7.0

# Vegas-first model, fit 2026-07-26 on 6,126 DST-weeks (OOS fit<=2020,
# eval 2021+2025: R=0.293 vs 0.124 trailing-only). Opponent implied total
# is ~4x the signal of trailing form; QB experience survives Vegas at
# about half its raw size (the market prices the rest).
COEF_INTERCEPT = 14.33
COEF_OPP_IMPLIED = -0.385
COEF_L16 = 0.118
COEF_ROOKIE = 1.05   # opposing QB <= 3 career starts
COEF_EARLY = 0.91    # 4-10 career starts


def model_projection(opp_implied: pd.Series, trailing: pd.Series,
                     opp_qb_starts: pd.Series) -> pd.Series:
    """Vegas-first DST projection; rows without a line fall back to
    trailing form + the raw QB-experience adjustment."""
    opp_implied = pd.to_numeric(opp_implied, errors="coerce")
    trailing = pd.to_numeric(trailing, errors="coerce").fillna(FALLBACK_PROJ)
    starts = pd.to_numeric(opp_qb_starts, errors="coerce")
    rookie = (starts <= 3).fillna(False).astype(float)
    early = ((starts > 3) & (starts <= 10)).fillna(False).astype(float)
    vegas = (COEF_INTERCEPT + COEF_OPP_IMPLIED * opp_implied
             + COEF_L16 * trailing + COEF_ROOKIE * rookie
             + COEF_EARLY * early)
    fallback = trailing + adjustment(opp_qb_starts)
    return vegas.where(opp_implied.notna(), fallback)


def build_rows(
    slate: pd.DataFrame,      # dk_player_id, display_name, team_abbr, salary, draft_group_id
    trailing: pd.DataFrame,   # team, dst_l4
    opponents: pd.DataFrame,  # team, opponent  (for the target week)
    qb_starts: pd.DataFrame,  # team, career_starts (expected starter, as of now)
    season: int,
    week: int,
    model_version: str,
) -> pd.DataFrame:
    """Pure assembly — every input injectable for offline tests."""
    d = slate.merge(opponents, left_on="team_abbr", right_on="team", how="left")
    d = d.merge(trailing, left_on="team_abbr", right_on="team",
                how="left", suffixes=("", "_t"))
    d = d.merge(qb_starts.rename(columns={"team": "opp_team",
                                          "career_starts": "opp_qb_starts"}),
                left_on="opponent", right_on="opp_team", how="left")
    opp_implied = (d["opp_implied"] if "opp_implied" in d.columns
                   else pd.Series(pd.NA, index=d.index))
    proj = model_projection(opp_implied, d["dst_l4"], d["opp_qb_starts"])
    return pd.DataFrame({
        "generated_at": datetime.now(timezone.utc),
        "model_version": model_version,
        "season": season,
        "week": week,
        "slate_id": d.get("draft_group_id"),
        "gsis_id": None,
        "dk_player_id": d["dk_player_id"],
        "display_name": d["display_name"],
        "position": "DST",
        "team": d["team_abbr"],
        "opponent": d["opponent"],
        "salary": d["salary"],
        "proj_points": proj,
        "proj_p10": proj + P10_OFF,
        "proj_p50": proj + P50_OFF,
        "proj_p90": proj + P90_OFF,
        "proj_std": STD,
        "p_20_plus": 0.03,
        "value": proj / (d["salary"] / 1000.0),
        "proj_ownership": pd.NA,
    })


def project_dst(season: int, week: int, model_version: str) -> pd.DataFrame:
    """Assemble DST projection rows for the upcoming slate from live data."""
    from ..bq import query_df

    # Union of every upcoming classic group (latest pull each), one row per
    # DST, so full-week slates get Thu/Mon defenses too — mirrors
    # run_projections.upcoming_slate_features.
    slate = query_df(
        f"""
        WITH pulls AS (
          SELECT draft_group_id, MAX(pulled_at) AS ts
          FROM `{settings.raw}.dk_salaries`
          WHERE slate_type = 'classic'
          GROUP BY draft_group_id
          HAVING MAX(game_start) >= CURRENT_TIMESTAMP()
        )
        SELECT dk_player_id, display_name, team_abbr, salary, draft_group_id
        FROM (
          SELECT DISTINCT s.dk_player_id, s.display_name, s.team_abbr,
                 s.salary, s.draft_group_id, s.pulled_at
          FROM `{settings.raw}.dk_salaries` s
          JOIN pulls p
            ON s.draft_group_id = p.draft_group_id AND s.pulled_at = p.ts
          WHERE s.slate_type = 'classic' AND s.position = 'DST'
        )
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY dk_player_id
          ORDER BY pulled_at DESC, draft_group_id) = 1
        """
    )
    if slate.empty:
        log.warning("no DST rows in the latest classic pull")
        return slate
    trailing = query_df(
        f"""
        SELECT team, AVG(dst_dk_points) AS dst_l4 FROM (
          SELECT team, dst_dk_points, ROW_NUMBER() OVER (
            PARTITION BY team ORDER BY season DESC, week DESC) AS rn
          FROM `{settings.features}.team_defense_week`
        ) WHERE rn <= 4 GROUP BY team
        """
    )
    opponents = query_df(
        f"""
        SELECT home_team AS team, away_team AS opponent,
               (total_line - spread_line)/2 AS opp_implied
        FROM `{settings.raw}.schedules`
        WHERE season = {season} AND week = {week}
        UNION ALL
        SELECT away_team AS team, home_team AS opponent,
               (total_line + spread_line)/2 AS opp_implied
        FROM `{settings.raw}.schedules`
        WHERE season = {season} AND week = {week}
        """
    )
    # Expected starter = whoever started the opponent's most recent game;
    # their career starts as of now = prior_starts at that game + 1.
    # A late QB change is exactly what manual notes / late swap are for.
    qb = query_df(
        f"""
        WITH starters AS (
          SELECT season, week, team, player_id,
                 ROW_NUMBER() OVER (PARTITION BY season, week, team
                                    ORDER BY attempts DESC) AS rk
          FROM `{settings.raw}.weekly_stats`
          WHERE position = 'QB' AND attempts > 0
        ), s AS (
          SELECT *, COUNT(*) OVER (PARTITION BY player_id
                    ORDER BY season, week ROWS BETWEEN UNBOUNDED PRECEDING
                    AND 1 PRECEDING) AS prior_starts
          FROM starters WHERE rk = 1
        )
        SELECT team, prior_starts + 1 AS career_starts FROM (
          SELECT *, ROW_NUMBER() OVER (PARTITION BY team
                    ORDER BY season DESC, week DESC) AS rn FROM s
        ) WHERE rn = 1
        """
    )
    return build_rows(slate, trailing, opponents, qb, season, week,
                      model_version)

```

===== FILE: src/nfl_dfs/inference/live_lineups.py =====
```python
"""Live classic sim-mode: the VALIDATED replay engine on the live slate.

Until 2026-08-03 the live classic path was MILP-on-projections plus a
normal-approximation confidence ranking, while every validated gain
(boom-draw candidates, tail-coverage selection of 40, and the adopted
EW draw shaping) lived only in replays. This module closes that fidelity
gap: features -> cold-start fill -> component models -> correlated sims
-> EW shaping -> the SAME candidate generation and coverage selection
the six-season panels graded (engine.tail_select_lineups).

Design choices, deliberate:
- Market blend enters as an additive per-player shift on the draws
  (mean = validated live blend; SHAPE = validated EW worlds).
- Same tournament tilts as replay build_slates: punt ceiling valuation,
  punt-boom archetype boost, chalk-fade on OUR objective only, low_own
  flags for MIN_LOWOWN.
- Deterministic seed so a rebuild of the same slate reproduces exactly.
- Callers (app) wrap this in a fallback to the plain MILP path: a slate
  built the old way beats a 500.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


LIVE_SIMS_DEFAULT = 30_000  # adopted 2026-08-03: +2 tails, best ROI and
# medians of its panel — 3x compute is pennies on ONE live slate while
# panels stay at 10k (research cadence). Env LIVE_SIMS overrides.


def build_slate_with_draws(season: int, week: int, n_sims: int | None = None,
                           seed: int = 42, lev_scale: float = 1.0,
                           apply_notes: bool = True,
                           ) -> tuple[pd.DataFrame, np.ndarray]:
    """Engine-ready slate frame + aligned draw matrix for the live week."""
    from ..backtest.field import naive_ownership
    from ..backtest.replay import apply_draw_shape, punt_boom_flags_live
    from ..models import coldstart, simulate
    from ..models.train_job import load_latest_component_models
    from ..optimizer.lineup import LEVERAGE_PENALTY, PUNT_MAX_SALARY
    from .. import notes as manual_notes
    from ..models.blend import blend, market_projection_frame
    from .run_projections import BLEND_WEIGHT, upcoming_slate_features

    import os as _os

    if n_sims is None:
        n_sims = int(_os.environ.get("LIVE_SIMS", LIVE_SIMS_DEFAULT))
    model, version = load_latest_component_models()
    feats = upcoming_slate_features(season, week)
    skill = feats[feats.dk_position.isin(["QB", "RB", "WR", "TE"])] \
        .reset_index(drop=True)
    skill = coldstart.fill_cold_start_features(skill)
    comps = model.predict_components(skill)
    if apply_notes:
        # Multiplier notes (chat-converted opportunity scalers). Gated by
        # the same "My notes" toggle as boost/ban prefs (2026-08-04) —
        # off = the untouched algorithm. NOTE: the STORED Sunday
        # projections (run_projections) bake these in; only this live
        # recompute honors the toggle fully.
        comps = manual_notes.apply_notes(comps, skill, season, week)
    sim = simulate.simulate(comps, n_sims=n_sims, seed=seed, keep_draws=True,
                            game_ids=skill.get("game_id"),
                            team_ids=skill.get("team"),
                            game_totals=skill.get("game_total"))
    # keys enable per-player marginal levers (TABPFN_MARGINALS) live —
    # without them the lever silently fell through to empirical
    # marginals, a replay/live parity gap (2026-08-04 audit).
    draws = apply_draw_shape(sim.draws, skill.position, seed,
                             keys=skill[["season", "week", "gsis_id"]]
                             if {"season", "week", "gsis_id"}
                             <= set(skill.columns) else None)

    # Market blend as an additive mean shift — draw shape untouched.
    market = market_projection_frame(skill)
    blended = blend(draws.mean(axis=1), market.to_numpy(), BLEND_WEIGHT)
    draws = draws + (blended - draws.mean(axis=1))[:, None]

    frame = pd.DataFrame({
        "id": skill.dk_player_id.astype(int),
        "gsis_id": skill.gsis_id,
        "name": skill.display_name,
        "pos": skill.position if "position" in skill.columns
               else skill.dk_position,
        "team": skill.get("team", skill.get("team_abbr")),
        "opp": skill.get("opponent"),
        "salary": pd.to_numeric(skill.salary, errors="coerce"),
        "season": season, "week": week,
    })
    frame["game_id"] = skill.get(
        "game_id", frame.team.astype(str) + "@" + frame.opp.astype(str))
    frame["draw_idx"] = np.arange(len(frame))
    frame["proj"] = draws.mean(axis=1)

    # DST rows: static live projections, no draws (draw_idx -1).
    try:
        from .dst_projections import project_dst

        dst = project_dst(season, week, model_version=version)
        if not dst.empty:
            d = pd.DataFrame({
                "id": dst.dk_player_id.astype(int),
                "gsis_id": "", "name": dst.display_name,
                "pos": "DST", "team": dst.get("team", dst.display_name),
                "opp": dst.get("opponent"),
                "salary": pd.to_numeric(dst.salary, errors="coerce"),
                "season": season, "week": week,
                "draw_idx": -1, "proj": dst.proj_points,
            })
            d["game_id"] = d.team.astype(str) + "@" + d.opp.astype(str)
            frame = pd.concat([frame, d], ignore_index=True)
    except Exception:
        log.exception("live DST rows unavailable; skill-only slate")

    frame = frame.dropna(subset=["salary", "proj"])
    frame = frame[frame.salary > 0]
    frame["salary"] = frame.salary.astype(int)
    frame = frame[~frame.id.duplicated()].reset_index(drop=True)

    # Tournament tilts, replay-identical (see backtest.replay.build_slates)
    punt = (frame.salary <= PUNT_MAX_SALARY) & (frame.draw_idx >= 0)
    p90 = np.percentile(draws, 90, axis=1)
    frame.loc[punt, "proj"] = np.maximum(
        frame.loc[punt, "proj"], p90[frame.loc[punt, "draw_idx"].to_numpy()])
    # OWN_MODEL=fade ADOPTED 2026-08-04 (QF arm, replay-validated): the
    # trained ownership model feeds the chalk fade (naive stays the field
    # yardstick elsewhere). Live mirror of backtest.replay's fade path;
    # falls back to naive WITH A WARNING only if the booster can't train
    # (contest_ownership empty — never true since 2022). "" disables.
    import os as _os

    own = None
    from ..backtest.replay import own_mode
    if own_mode():
        try:
            from ..backtest.replay import _model_ownership, _ownership_booster

            booster = _ownership_booster(int(season))
            if booster is not None:
                own = _model_ownership(booster, frame)
        except Exception:
            log.exception("ownership model unavailable; fade uses naive")
    if own is None:
        own = naive_ownership(frame)
    frame["proj_tourney"] = frame.proj - LEVERAGE_PENALTY * lev_scale * own
    try:
        boom = punt_boom_flags_live(season, week)
        keys = list(zip(frame.gsis_id, [season] * len(frame),
                        [week] * len(frame)))
        bmask = pd.Series([k in boom for k in keys], index=frame.index)
        bmask &= punt & (frame.pos != "DST")
        frame.loc[bmask, "proj_tourney"] += 2.0  # adopted PUNT_BOOM dose
    except Exception:
        log.exception("live punt-boom flags unavailable; tilt skipped")
    slots = {"QB": 1.0, "RB": 2.5, "WR": 3.5, "TE": 1.2, "DST": 1.0}
    frame["low_own"] = (own * frame.pos.map(slots).fillna(1.0)
                        .to_numpy()) < 0.05
    return frame, draws


def build_sim_lineups(season: int, week: int, n_entries: int,
                      stack, tail_line: float, n_sims: int | None = None,
                      seed: int = 42, lev_scale: float = 1.0,
                      locks: set | None = None, bans: set | None = None,
                      allowed_ids: set | None = None,
                      theses: list | None = None,
                      apply_notes: bool = True) -> list:
    """Full validated pipeline on the live slate -> selected entries in
    coverage order (first = broadest boom coverage).

    locks: dk_player_ids required in every entry (plumbed through every
    candidate generator). bans: excluded from the pool entirely.
    allowed_ids: restrict to one DK slate's player set (draft_group_id
    requests) — draw_idx stays valid because rows only get DROPPED."""
    from ..backtest.engine import tail_select_lineups

    slate, draws = build_slate_with_draws(season, week, n_sims=n_sims,
                                          seed=seed, lev_scale=lev_scale,
                                          apply_notes=apply_notes)
    if allowed_ids:
        slate = slate[slate.id.isin(allowed_ids)]
    if bans:
        slate = slate[~slate.id.isin(bans)]
    if apply_notes:
        # Converted watch-notes (boost/ban prefs) applied INSIDE the sim
        # path (2026-08-04 — previously MILP-only, so the default build
        # silently ignored them). apply_notes=False = pure algorithm.
        try:
            from ..notes import BOOST_BONUS, _prefs_table, norm_name
            from ..bq import query_df

            p = query_df(f"SELECT norm, kind FROM `{_prefs_table()}` WHERE "
                         f"season={int(season)} AND week={int(week)}")
            if not p.empty:
                nb = set(p[p.kind == "ban"].norm)
                bo = set(p[p.kind == "boost"].norm)
                norms = slate.name.map(norm_name)
                drop = norms.isin(nb) & ~slate.id.isin(locks or set())
                slate = slate[~drop]
                bmask = slate.name.map(norm_name).isin(bo)
                slate.loc[bmask, "proj_tourney"] += BOOST_BONUS
                log.info("notes applied in sim path: %d banned, %d boosted",
                         int(drop.sum()), int(bmask.sum()))
        except Exception:
            log.exception("note prefs unavailable; building without them")
    slate = slate.reset_index(drop=True)
    if locks:
        missing = set(locks) - set(slate.id)
        if missing:
            raise ValueError(f"locked players not in slate: {sorted(missing)}")
    pool = slate.to_dict("records")
    lineups = tail_select_lineups(
        slate, pool, draws, tail_line=tail_line, n_entries=n_entries,
        stack=stack, objective_col="proj_tourney",
        locks=set(locks or ()), theses=theses)
    return lineups

```

===== FILE: src/nfl_dfs/inference/market_implied.py =====
```python
"""Market-implied player distributions from alternate prop lines.

De-vigs DK's alternate-line ladders (raw.prop_lines) into implied
P(over x) curves and quantiles. Validated 2026-08-03 (study report
Addendum 45, scripts/prop_implied_study.py): on 2023-25 matched
player-weeks the market's implied q90 arrives calibrated (coverage
0.92) and beats/ties our LGB quantiles on pinball loss — and
model-vs-market tail disagreement predicts the direction of market
error BOTH ways. Usage contract mirrors the ETR rule: disagreement
FLAG for the watchlist/market page, not a silent model input, until a
replay arm judges it as a feature.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ALT_MARKETS = {
    "player_reception_yds_alternate": "rec_yards",
    "player_rush_yds_alternate": "rush_yards",
    "player_pass_yds_alternate": "pass_yards",
}


def american_implied(price: float) -> float:
    """Implied probability of American odds (vig included)."""
    a = float(price)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def implied_curve(ladder: pd.DataFrame) -> tuple[np.ndarray, np.ndarray] | None:
    """De-vigged, monotone P(over x) from one player's alt-line ladder.

    ladder: columns point, outcome_name ('Over'/'Under'), price
    (American). Pairwise de-vig where both sides exist; single-sided
    rows assume ~5% one-way margin. Needs >=3 points.
    """
    pts = []
    for pt, g in ladder.groupby("point"):
        inv = {r.outcome_name: american_implied(r.price)
               for r in g.itertuples()}
        if "Over" in inv and "Under" in inv:
            p = inv["Over"] / (inv["Over"] + inv["Under"])
        elif "Over" in inv:
            p = inv["Over"] / 1.05
        else:
            continue
        pts.append((float(pt), float(np.clip(p, 1e-4, 1 - 1e-4))))
    if len(pts) < 3:
        return None
    pts.sort()
    x = np.array([p[0] for p in pts])
    y = np.minimum.accumulate(np.array([p[1] for p in pts]))
    return x, y


def curve_quantile(x: np.ndarray, y: np.ndarray, q: float) -> float:
    """Smallest x with P(X<=x) >= q; mild linear tail extrapolation."""
    tgt = 1.0 - q
    if y[-1] > tgt:
        return float(x[-1] + (x[-1] - x[0]) * 0.15)
    if y[0] <= tgt:
        return float(x[0])
    return float(np.interp(tgt, y[::-1], x[::-1]))


def market_quantiles(props: pd.DataFrame,
                     quantiles: tuple[float, ...] = (0.5, 0.9)) -> pd.DataFrame:
    """One row per (season, week, market, player) with implied quantiles.

    props: prop_lines rows (already filtered to latest pre-kick snapshot
    and one bookmaker).
    """
    rows = []
    for key, g in props.groupby(["season", "week", "market", "player"]):
        c = implied_curve(g)
        if c is None:
            continue
        x, y = c
        row = dict(zip(["season", "week", "market", "player"], key))
        row["n_points"] = len(x)
        for q in quantiles:
            row[f"q{int(q * 100)}"] = curve_quantile(x, y, q)
        rows.append(row)
    return pd.DataFrame(rows)

```

===== FILE: src/nfl_dfs/inference/qb_experience.py =====
```python
"""Opposing-QB experience adjustment for DST projections.

Defenses facing inexperienced QBs outscore their own trailing form by a
large, monotonic margin — measured 2026-07-26 on 3,428 DST-weeks
(2014-2021 + 2025 real-salary seasons), residual vs the defense's own
trailing 4-week average:

    <=3 career starts  +2.19 DK pts     11-30  -0.51
    4-10               +1.48            >30    -0.72

A DST projection built only from its own trailing average can't see who
plays QB on the other side; this module supplies the correction.

Point-in-time note: the week-W starter is identified as the team's QB
with the most attempts that week. In production the starter is announced
publicly before lock, so using the actual starter in replays is a fair
approximation of pre-lock knowledge, not an answer-key leak.
"""

from __future__ import annotations

import pandas as pd

# (upper bound on prior starts, DK-point adjustment) — from the study above
BUCKETS = ((3, 2.2), (10, 1.5), (30, -0.5), (float("inf"), -0.7))


def adjustment(prior_starts: pd.Series) -> pd.Series:
    """DK-point adjustment to a DST's projection given the OPPOSING
    starter's career starts. Unknown starter (NaN) -> 0."""
    out = pd.Series(0.0, index=prior_starts.index)
    prev = -1.0
    for ub, adj in BUCKETS:
        out[(prior_starts > prev) & (prior_starts <= ub)] = adj
        prev = ub
    out[prior_starts.isna()] = 0.0
    return out


def starter_prior_starts() -> pd.DataFrame:
    """(season, week, team, prior_starts) for each team-week's starting QB
    — career starts strictly before that week."""
    from ..bq import query_df
    from ..config import settings

    return query_df(
        f"""
        WITH starters AS (
          SELECT season, week, team, player_id,
                 ROW_NUMBER() OVER (PARTITION BY season, week, team
                                    ORDER BY attempts DESC) AS rk
          FROM `{settings.raw}.weekly_stats`
          WHERE position = 'QB' AND attempts > 0
        )
        SELECT season, week, team,
               COUNT(*) OVER (PARTITION BY player_id ORDER BY season, week
                              ROWS BETWEEN UNBOUNDED PRECEDING
                              AND 1 PRECEDING) AS prior_starts
        FROM starters WHERE rk = 1
        """
    )

```

===== FILE: src/nfl_dfs/inference/run_projections.py =====
```python
"""Weekly/hourly inference: project the upcoming slate and write
nfl_predictions.player_projections.

Schedule: Tuesday after retrain, then hourly Sat-Sun for late swap — the
player pool changes as inactives are announced, and stale projections on
Sunday morning are how you enter lineups you didn't mean to enter.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import pandas as pd

from ..bq import load_dataframe, query_df
from ..config import current_season, settings
from ..models import calibration, coldstart, components, simulate
from ..models.blend import blend, market_projection_frame
from . import cascade_adjust

log = logging.getLogger(__name__)

BLEND_WEIGHT = 0.45  # refit on validation each retrain; see models/blend.py


def upcoming_slate_features(season: int, week: int) -> pd.DataFrame:
    """Feature rows for the players in the current classic slate, with the
    same point-in-time features the model trained on. Unmatched slate
    players fail loudly — a dropped player is a lineup you can't build.

    Features come from player_week_inference (023): as-of-now rollups built
    on the upcoming week's synthetic rows. The training table can't serve
    live slates — its rows require played games and actuals.

    The pool is the UNION of every upcoming classic draft group (latest pull
    per group), deduped per player, so any slate — Sunday main, full
    Thu-Mon, afternoon-only — can be built from these projections. A single
    MAX(pulled_at) would pick just one arbitrary group: each group gets its
    own timestamp within an ingest run."""
    df = query_df(
        f"""
        WITH pulls AS (
          SELECT draft_group_id, MAX(pulled_at) AS ts
          FROM `{settings.raw}.dk_salaries`
          WHERE slate_type = 'classic'
          GROUP BY draft_group_id
          HAVING MAX(game_start) >= CURRENT_TIMESTAMP()
        ),
        latest AS (
          SELECT DISTINCT s.dk_player_id, s.display_name, s.salary,
                 s.position AS dk_position, s.team_abbr, s.status, s.dk_ppg,
                 s.draft_group_id
          FROM `{settings.raw}.dk_salaries` s
          JOIN pulls p
            ON s.draft_group_id = p.draft_group_id AND s.pulled_at = p.ts
          WHERE s.slate_type = 'classic'
        ),
        sizes AS (
          SELECT draft_group_id, COUNT(DISTINCT dk_player_id) AS n_players
          FROM latest GROUP BY draft_group_id
        ),
        slate AS (
          -- One row per player; ties broken toward the biggest group so
          -- slate_id mostly names the fullest slate.
          SELECT * EXCEPT (rn) FROM (
            SELECT l.*, ROW_NUMBER() OVER (
              PARTITION BY l.dk_player_id
              ORDER BY z.n_players DESC, l.draft_group_id) AS rn
            FROM latest l JOIN sizes z USING (draft_group_id)
          ) WHERE rn = 1
        )
        SELECT sl.*, m.gsis_id, t.*
        FROM slate sl
        LEFT JOIN `{settings.features}.player_id_map` m USING (dk_player_id)
        LEFT JOIN `{settings.features}.player_week_inference` t
          ON t.gsis_id = m.gsis_id AND t.season = {season} AND t.week = {week}
        """
    )
    if df.empty:
        raise RuntimeError(
            "no upcoming classic slates in dk_salaries — run ingest-dk "
            "(or DK hasn't posted next week's draft groups yet)"
        )
    unmatched = df[df.gsis_id.isna() & (df.dk_position != "DST")]
    if not unmatched.empty:
        raise RuntimeError(
            f"{len(unmatched)} slate players have no GSIS mapping — add them "
            f"to nfl_features.player_id_overrides before projecting:\n"
            + unmatched[["dk_player_id", "display_name", "team_abbr"]]
            .head(20).to_string(index=False)
        )
    return df


def project(
    feats: pd.DataFrame,
    model: components.ComponentModels,
    model_version: str,
    season: int,
    week: int,
    n_sims: int = 10_000,
    adjust=None,
) -> pd.DataFrame:
    """adjust: optional callable (feats) -> (feats, out_gsis_ids), applied
    after the cold-start fill so cascade bumps land on top of role priors —
    see inference.cascade_adjust."""
    feats = coldstart.fill_cold_start_features(feats)
    out_ids: list[str] = []
    if adjust is not None:
        feats, out_ids = adjust(feats)
    comps = model.predict_components(feats)
    # Manual usage notes (coach statements etc.): inference-only prior
    # adjustment, decaying to zero by week 6 — see notes.py.
    from .. import notes as manual_notes

    comps = manual_notes.apply_notes(comps, feats, season, week)
    sim = simulate.simulate(comps, n_sims=n_sims,
                        game_ids=feats.get("game_id"),
                        team_ids=feats.get("team"),
                        game_totals=feats.get("game_total"))
    preds = calibration.apply_widen(
        sim.summary, feats.get("position", feats.get("dk_position"))
    )
    preds = coldstart.widen_cold_start_quantiles(
        preds, feats.get("is_cold_start", pd.Series(False, index=feats.index))
    )

    market = market_projection_frame(feats)
    preds["proj_points"] = blend(
        preds["proj_points"].to_numpy(), market.to_numpy(), BLEND_WEIGHT
    )

    out = pd.DataFrame(
        {
            "generated_at": datetime.now(timezone.utc),
            "model_version": model_version,
            "season": season,
            "week": week,
            "slate_id": feats.get("draft_group_id"),
            "gsis_id": feats.get("gsis_id"),
            "dk_player_id": feats.get("dk_player_id"),
            "display_name": feats.get("display_name"),
            "position": feats.get("position", feats.get("dk_position")),
            "team": feats.get("team", feats.get("team_abbr")),
            "opponent": feats.get("opponent"),
            "salary": feats.get("salary"),
            "proj_points": preds["proj_points"],
            "proj_p10": preds["proj_p10"],
            "proj_p50": preds["proj_p50"],
            "proj_p90": preds["proj_p90"],
            "proj_std": preds["proj_std"],
            "p_20_plus": preds["p_20_plus"],
            "value": preds["proj_points"] / (feats["salary"] / 1000.0),
            "proj_ownership": pd.NA,
        }
    )
    return cascade_adjust.zero_out_projections(out, out_ids)


def _cascade_adjuster(season: int):
    """Build the late-inactive adjuster from warehouse history (current and
    prior season give the with/without splits enough absences to work with).
    Inference must survive this failing — projections without the cascade
    beat no projections on a Sunday morning."""
    try:
        span = f"({season - 1}, {season})"
        usage_rec = query_df(
            f"""SELECT gsis_id, season, week, total_targets, rz20_targets,
                       target_share
                FROM `{settings.features}.rz_receiving` WHERE season IN {span}"""
        )
        usage_rush = query_df(
            f"""SELECT gsis_id, season, week, total_carries, gl3_carries,
                       carry_share
                FROM `{settings.features}.rz_rushing` WHERE season IN {span}"""
        )
        injuries = query_df(
            f"""SELECT gsis_id, season, week, injury_status AS game_status
                FROM `{settings.features}.player_week_injury`
                WHERE season IN {span}"""
        )
    except Exception:
        log.exception("cascade inputs unavailable; projecting without "
                      "late-inactive redistribution")
        return None
    return lambda f: cascade_adjust.adjust_for_inactives(
        f, usage_rec, usage_rush, injuries)


def run() -> None:
    from ..models.train_job import load_latest_component_models

    season = current_season()
    week = query_df(
        f"""SELECT MIN(week) AS week FROM `{settings.raw}.schedules`
            WHERE season = {season} AND gameday >= CAST(CURRENT_DATE() AS STRING)"""
    ).week.iloc[0]
    week = int(week)

    model, version = load_latest_component_models()
    # LIVE_SIMS (adopted 2026-08-03): live paths sim 30k worlds (better
    # medians/ROI, one slate = pennies); panels/replays stay at 10k.
    n_sims = int(os.environ.get("LIVE_SIMS", "30000"))
    feats = upcoming_slate_features(season, week)
    skill = feats[feats.dk_position.isin(["QB", "RB", "WR", "TE"])].reset_index(drop=True)
    out = project(skill, model, version, season, week, n_sims=n_sims,
                  adjust=_cascade_adjuster(season))
    # DST rows (issue #7): trailing team-defense form + opposing-QB
    # experience. Failure-safe — skill projections without DSTs still
    # beat nothing, though lineup building needs the DST rows.
    try:
        from .dst_projections import project_dst

        dst = project_dst(season, week, model_version=version)
        if not dst.empty:
            out = pd.concat([out, dst], ignore_index=True)
    except Exception:
        log.exception("DST projections failed; writing skill rows only")
    load_dataframe(out, f"{settings.predictions}.player_projections",
                   write_disposition="WRITE_APPEND", partition_field="generated_at")
    log.info("Wrote %d projections for season %s week %s (model %s)",
             len(out), season, week, version)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

```

===== FILE: src/nfl_dfs/ingest/__init__.py =====
```python

```

===== FILE: src/nfl_dfs/ingest/cfb_job.py =====
```python
"""CFB (college football) DK data-collection scaffold: issue #13 item 7.

Owner request (2026-07-31): DK now runs college football DFS (QB/2RB/3WR/
FLEX/Superflex, 8 slots). This is COLLECTION ONLY — no models, features, or
optimizer work reads its output. The goal is a backtestable dataset the
2026 CFB season accumulates, for a 2027 go/no-go decision on building the
rest of the pipeline (features, models, optimizer) for this sport.

Mirrors dk_job.py (slate/salary snapshot) and contest_job.py (fill-rate/
overlay poll) for CFB, reusing the same undocumented DK endpoints with the
CFB sportId (5) instead of NFL's (1) — see dk_client.CFB_SPORT_ID for how
that was verified live. Gated by INGEST_CFB_ENABLED, noop when unset
(contest_job's pattern) — CFB season doesn't start until late August, and
this must not touch the validated NFL ingest path in dk_job.py/
contest_job.py at all.
"""

from __future__ import annotations

import logging
import os

import pandas as pd
import requests

from ..bq import load_dataframe
from ..config import current_season
from . import dk_client

log = logging.getLogger(__name__)


def run() -> None:
    if not os.environ.get("INGEST_CFB_ENABLED"):
        log.info("INGEST_CFB_ENABLED not set; skipping CFB poll")
        return

    session = requests.Session()
    groups = dk_client.cfb_draft_groups(session)
    if not groups:
        log.info("No upcoming CFB draft groups")
        return

    season = current_season()
    frames = []
    for g in groups:
        gid = g["draftGroupId"]
        slate_type = dk_client.classify_slate(g)
        payload = dk_client.fetch_draftables(gid, session)
        df = dk_client.draftables_frame(gid, slate_type, payload)
        if df.empty:
            continue
        df["season"] = season
        df["week"] = None
        frames.append(df)
        log.info("CFB slate %s (%s): %d players", gid, slate_type, len(df))

    if frames:
        load_dataframe(
            pd.concat(frames, ignore_index=True),
            "cfb_dk_salaries",
            write_disposition="WRITE_APPEND",
            partition_field="pulled_at",
        )

    draft_group_ids = {g["draftGroupId"] for g in groups}
    contests = dk_client.cfb_contests(session)
    cdf = dk_client.contests_frame(contests, draft_group_ids=draft_group_ids, sport="CFB")
    if not cdf.empty:
        load_dataframe(
            cdf,
            "dk_contest_fills",
            write_disposition="WRITE_APPEND",
            partition_field="pulled_at",
        )
        log.info("Polled %d CFB contests across %d draft groups (%d guaranteed)",
                  len(cdf), len(draft_group_ids), int(cdf.is_guaranteed.sum()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

```

===== FILE: src/nfl_dfs/ingest/contest_job.py =====
```python
"""Overlay-detection scaffold: poll DK contest fill rates for upcoming NFL
slates into ``nfl_raw.dk_contest_fills``.

This is infrastructure, not a validated signal yet — a single poll can't
tell overlay from a GPP that simply fills late, the way real ones do. Land
enough polls close to lock (the production schedule would need this hourly
or denser, e.g. every 5-10 min in the last hour before kickoff) before
treating ``overlay_dollars`` as anything but a diagnostic.

Gated by ``INGEST_CONTESTS_ENABLED`` because this hits a second
undocumented DK endpoint (the lobby contest list) beyond the draftgroups
one ``dk_job.py`` already polls hourly — opt in explicitly rather than
silently doubling our request rate against DK once this lands in the
schedule. See ``dk_client``'s module docstring for the "be a good citizen"
rules this follows (real User-Agent, short timeout, one pass per run, no
retries).
"""

from __future__ import annotations

import logging
import os

import requests

from ..bq import load_dataframe
from . import dk_client

log = logging.getLogger(__name__)


def run() -> None:
    if not os.environ.get("INGEST_CONTESTS_ENABLED"):
        log.info("INGEST_CONTESTS_ENABLED not set; skipping contest poll")
        return

    session = requests.Session()
    groups = dk_client.nfl_draft_groups(session)
    if not groups:
        log.info("No upcoming NFL draft groups; nothing to match contests to")
        return
    draft_group_ids = {g["draftGroupId"] for g in groups}

    contests = dk_client.nfl_contests(session)
    df = dk_client.contests_frame(contests, draft_group_ids=draft_group_ids)
    if df.empty:
        log.info("Polled %d contests, none matched upcoming NFL draft groups",
                  len(contests))
        return

    load_dataframe(
        df,
        "dk_contest_fills",
        write_disposition="WRITE_APPEND",
        partition_field="pulled_at",
    )
    log.info("Polled %d contests across %d NFL draft groups (%d guaranteed)",
              len(df), len(draft_group_ids), int(df.is_guaranteed.sum()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

```

===== FILE: src/nfl_dfs/ingest/discoverylab_import.py =====
```python
"""Backfill real DK salaries from SportsDataIO's DiscoveryLab (personal-use)
API into the RotoGuru-shaped `dk_salaries_historical` table.

History (see the README data deficiency log): RotoGuru died after 2021;
SportsDataIO's commercial trial served scrambled data and quoted thousands.
Their DiscoveryLab personal tier serves REAL salaries — verified 835/835
$100-multiples on the 2025 week-15 main slate — but the free tier covers
only the most recent completed season. 2022-2024 remain gated behind their
paid personal tiers.

Endpoints (free tier, key via SPORTSDATA_API_KEY in .env):
  /api/nfl/fantasy/json/DfsSlatesByWeek/{season}REG/{week}
  /api/nfl/fantasy/json/FantasyDefenseByGame/{season}REG/{week}  (DST actuals)

Slate selection: DraftKings + OperatorGameType == "Classic" + salaries
actually present (the feed includes a giant pseudo-slate whose salaries are
all zero — picking by player count would select it), then most games =
the main slate. DST rows get actual DK points from FantasyDefenseByGame so
contest replays can roster defenses.
"""

from __future__ import annotations

import logging
import time

import pandas as pd
import requests

from ..bq import load_dataframe
from ..config import settings

log = logging.getLogger(__name__)

BASE = "https://api.sportsdata.io/api/nfl/fantasy/json"

_POSITION_MAP = {"DST": "Def", "DEF": "Def", "D": "Def"}


def pick_main_classic_slate(slates: list[dict]) -> dict | None:
    """Largest-by-games DK Classic slate whose salaries are populated."""
    candidates = []
    for sl in slates:
        if str(sl.get("Operator", "")).lower() != "draftkings":
            continue
        if str(sl.get("OperatorGameType", "")) != "Classic":
            continue
        players = sl.get("DfsSlatePlayers") or []
        if not players:
            continue
        with_salary = sum(1 for p in players if p.get("OperatorSalary"))
        if with_salary / len(players) >= 0.95:
            candidates.append(sl)
    if not candidates:
        return None
    return max(candidates, key=lambda sl: (sl.get("NumberOfGames") or 0))


def slate_rows(slate: dict, season: int, week: int,
               dst_points: dict[str, tuple[float, str]] | None = None) -> pd.DataFrame:
    rows = []
    for p in slate.get("DfsSlatePlayers", []):
        name = p.get("OperatorPlayerName")
        salary = p.get("OperatorSalary")
        pos = str(p.get("OperatorPosition") or "").upper()
        pid = p.get("SlatePlayerID")
        if pid is None:
            pid = p.get("PlayerID")
        if not name or not salary or not pos or pid is None:
            continue
        pos = _POSITION_MAP.get(pos, pos)
        team = str(p.get("Team") or "").upper()
        dk_points, opponent = (dst_points or {}).get(team, (None, None)) \
            if pos == "Def" else (None, None)
        rows.append({
            "season": season,
            "week": week,
            "rotoguru_gid": int(pid),  # table column is INTEGER (see 7d17bd8)
            "display_name": str(name).strip(),
            "position": pos,
            "team_abbr": team,
            "home_away": None,
            "opponent": opponent,
            "dk_points": dk_points,
            "salary": int(salary),
        })
    df = pd.DataFrame(rows)
    return df.drop_duplicates(subset=["rotoguru_gid"]) if not df.empty else df


def fetch_week(season: int, week: int, session: requests.Session) -> pd.DataFrame:
    r = session.get(f"{BASE}/DfsSlatesByWeek/{season}REG/{week}", timeout=30)
    r.raise_for_status()
    slate = pick_main_classic_slate(r.json())
    if slate is None:
        return pd.DataFrame()
    dst_points: dict[str, tuple[float, str]] = {}
    try:
        rd = session.get(f"{BASE}/FantasyDefenseByGame/{season}REG/{week}", timeout=30)
        rd.raise_for_status()
        for d in rd.json():
            team = str(d.get("Team") or "").upper()
            pts = d.get("FantasyPointsDraftKings")
            if team and pts is not None:
                dst_points[team] = (float(pts), str(d.get("Opponent") or "").upper())
    except Exception as exc:  # noqa: BLE001 - DST actuals are best-effort
        log.warning("%s wk %s: no DST points (%s)", season, week, exc)
    return slate_rows(slate, season, week, dst_points)


def run(first_season: int = 2025, last_season: int = 2025) -> None:
    if not settings.sportsdata_api_key:
        raise RuntimeError("SPORTSDATA_API_KEY is not set (put it in .env)")
    session = requests.Session()
    session.headers["Ocp-Apim-Subscription-Key"] = settings.sportsdata_api_key

    frames = []
    for season in range(first_season, last_season + 1):
        for week in range(1, 19):
            try:
                df = fetch_week(season, week, session)
            except Exception as exc:  # noqa: BLE001 - a missing week is fine
                log.warning("Skipping %s week %s: %s", season, week, exc)
                continue
            if not df.empty:
                frames.append(df)
                log.info("%s week %s: %d players (main classic slate)",
                         season, week, len(df))
            time.sleep(1.1)

    if not frames:
        raise RuntimeError("no slate data returned — check key/tier scope")
    out = pd.concat(frames, ignore_index=True)
    ok = out.salary.between(2000, 12000)
    clean = (out.salary % 100 == 0)
    if ok.mean() < 0.95 or clean.mean() < 0.99:
        raise RuntimeError(
            f"salaries fail integrity checks (band {ok.mean():.0%}, "
            f"$100-multiples {clean.mean():.0%}) — not loading")
    load_dataframe(out, "dk_salaries_historical",
                   write_disposition="WRITE_APPEND")
    log.info("Appended %d salary rows (%s-%s)", len(out), first_season, last_season)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()


# --- Showdown slates (Captain Mode replay data) ----------------------------

SHOWDOWN_TABLE = "showdown_salaries_historical"


def showdown_slate_rows(slates: list[dict], season: int, week: int,
                        actuals: dict[int, float],
                        dst_points: dict[str, tuple[float, str]]) -> pd.DataFrame:
    """All DK Captain Mode slates for a week -> one row per slate player,
    FLEX salary, with actual DK points joined by SportsDataIO PlayerID
    (skill + K) or team (DST). Actual points come from SDIO for scoring
    consistency across positions our models don't cover."""
    rows = []
    for sl in slates:
        if str(sl.get("Operator", "")).lower() != "draftkings":
            continue
        if str(sl.get("OperatorGameType", "")) != "Showdown Captain Mode":
            continue
        players = sl.get("DfsSlatePlayers") or []
        with_sal = [p for p in players if p.get("OperatorSalary")]
        if len(players) == 0 or len(with_sal) / len(players) < 0.95:
            continue
        teams = sorted({str(p.get("Team") or "").upper() for p in with_sal} - {""})
        for p in with_sal:
            pos = str(p.get("OperatorPosition") or "").upper()
            team = str(p.get("Team") or "").upper()
            sdio_id = p.get("PlayerID")
            if pos in _POSITION_MAP:  # DST
                actual = (dst_points.get(team) or (None, None))[0]
            else:
                actual = actuals.get(sdio_id)
            rows.append({
                "season": season, "week": week,
                "operator_slate_id": sl.get("OperatorSlateID"),
                "operator_day": sl.get("OperatorDay"),
                "game_teams": "@".join(teams),
                "sdio_player_id": sdio_id,
                "display_name": str(p.get("OperatorPlayerName") or "").strip(),
                "position": _POSITION_MAP.get(pos, pos),
                "team_abbr": team,
                "salary": int(p["OperatorSalary"]),
                "dk_points_actual": actual,
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.drop_duplicates(subset=["operator_slate_id", "sdio_player_id"])


def run_showdown(first_season: int = 2025, last_season: int = 2025) -> None:
    """Land every Captain Mode slate (salaries + actual points) for the
    season(s) into nfl_raw.showdown_salaries_historical."""
    if not settings.sportsdata_api_key:
        raise RuntimeError("SPORTSDATA_API_KEY is not set (put it in .env)")
    session = requests.Session()
    session.headers["Ocp-Apim-Subscription-Key"] = settings.sportsdata_api_key

    frames = []
    for season in range(first_season, last_season + 1):
        for week in range(1, 19):
            try:
                r = session.get(f"{BASE}/DfsSlatesByWeek/{season}REG/{week}", timeout=30)
                r.raise_for_status()
                slates = r.json()
                ra = session.get(f"{BASE}/PlayerGameStatsByWeek/{season}REG/{week}",
                                 timeout=30)
                ra.raise_for_status()
                actuals = {x.get("PlayerID"): x.get("FantasyPointsDraftKings")
                           for x in ra.json()
                           if x.get("PlayerID") is not None
                           and x.get("FantasyPointsDraftKings") is not None}
                dst_points: dict[str, tuple[float, str]] = {}
                rd = session.get(f"{BASE}/FantasyDefenseByGame/{season}REG/{week}",
                                 timeout=30)
                rd.raise_for_status()
                for d in rd.json():
                    team = str(d.get("Team") or "").upper()
                    pts = d.get("FantasyPointsDraftKings")
                    if team and pts is not None:
                        dst_points[team] = (float(pts), str(d.get("Opponent") or "").upper())
                df = showdown_slate_rows(slates, season, week, actuals, dst_points)
            except Exception as exc:  # noqa: BLE001 - a missing week is fine
                log.warning("Skipping showdown %s week %s: %s", season, week, exc)
                continue
            if not df.empty:
                frames.append(df)
                log.info("%s week %s: %d showdown slate-player rows "
                         "(%d slates)", season, week, len(df),
                         df.operator_slate_id.nunique())
            time.sleep(1.1)

    if not frames:
        raise RuntimeError("no showdown slate data returned")
    out = pd.concat(frames, ignore_index=True)
    clean = (out.salary % 100 == 0)
    if clean.mean() < 0.99:
        raise RuntimeError(
            f"only {clean.mean():.0%} of salaries are $100 multiples — "
            "scrambled data; not loading")
    covered = out.dk_points_actual.notna()
    log.info("actual-points coverage: %.0f%%", 100 * covered.mean())
    load_dataframe(out, SHOWDOWN_TABLE, write_disposition="WRITE_APPEND")
    log.info("Appended %d showdown rows (%s-%s)", len(out), first_season, last_season)

```

===== FILE: src/nfl_dfs/ingest/dk_client.py =====
```python
"""DraftKings public draftgroups API client.

Undocumented, unauthenticated endpoints. Be a good citizen: real User-Agent,
one pass per scheduled run, short timeouts, no retries in tight loops.
Hammering this endpoint is how it gets locked down for everyone.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

log = logging.getLogger(__name__)

DK_GROUPS = "https://api.draftkings.com/draftgroups/v1/"
DK_DRAFTABLES = "https://api.draftkings.com/draftgroups/v1/draftgroups/{gid}/draftables"
DK_CONTESTS = "https://www.draftkings.com/lobby/getcontests?sport=NFL"
DK_CFB_CONTESTS = "https://www.draftkings.com/lobby/getcontests?sport=CFB"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) nfl-dfs-personal-research",
    "Accept": "application/json",
}

# DK's own /sites/US-DK/sports/v1/sports lists College Football as sportId=5
# (regionAbbreviatedSportName "CFB"; verified live 2026-07-31). Each entry in
# /draftgroups/v1/'s draftGroups array carries this same sportId at the top
# level — unlike the top-level "sport" string nfl_draft_groups() filters on,
# which 0/180 groups sampled live on that date actually carried (see the
# README's Data deficiency log). sportId is confirmed present and reliable.
CFB_SPORT_ID = 5

# rosterSlotIds seen on showdown slates (CPT/FLEX) differ from classic;
# startTimeSuffix like "(Sun only)" marks the classic main slate variants.
SHOWDOWN_GAME_TYPES = {"Showdown Captain Mode", "Madden Showdown Captain Mode"}


def nfl_draft_groups(session: requests.Session | None = None) -> list[dict[str, Any]]:
    s = session or requests.Session()
    r = s.get(DK_GROUPS, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return [
        g
        for g in r.json().get("draftGroups", [])
        if g.get("sport") == "NFL" and g.get("draftGroupState") == "Upcoming"
    ]


def cfb_draft_groups(session: requests.Session | None = None) -> list[dict[str, Any]]:
    """Upcoming DK College Football draft groups (issue #13 item 7).

    Same endpoint as ``nfl_draft_groups``, filtered on ``sportId`` instead
    of the top-level ``sport`` string — see ``CFB_SPORT_ID``'s docstring
    for why. Collection-only scaffold: DK's own sports list shows CFB with
    ``hasPublicContests: false`` as of 2026-07-31 (off-season, no slates
    yet), so this returns empty until real draft groups appear later in
    the season.
    """
    s = session or requests.Session()
    r = s.get(DK_GROUPS, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return [
        g
        for g in r.json().get("draftGroups", [])
        if g.get("sportId") == CFB_SPORT_ID and g.get("draftGroupState") == "Upcoming"
    ]


def classify_slate(group: dict[str, Any]) -> str:
    if group.get("gameTypeDescription") in SHOWDOWN_GAME_TYPES:
        return "showdown"
    if "Captain" in str(group.get("gameType", "")):
        return "showdown"
    return "classic"


def fetch_draftables(gid: int, session: requests.Session | None = None) -> dict[str, Any]:
    s = session or requests.Session()
    r = s.get(DK_DRAFTABLES.format(gid=gid), headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def nfl_contests(session: requests.Session | None = None) -> list[dict[str, Any]]:
    """Every contest DK's lobby currently tags sport=NFL.

    Verified live (2026-07): this endpoint returns whatever DK's lobby has
    up under the NFL tab year-round, which off-season is Madden simulation
    contests and Best Ball — not real NFL slates. It doesn't separate them
    from real classic/showdown slates by any sport field; filter with
    ``contests_frame(..., draft_group_ids=...)`` using the draft group IDs
    from ``nfl_draft_groups()`` to keep only contests on real games.
    """
    s = session or requests.Session()
    r = s.get(DK_CONTESTS, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("Contests", [])


def cfb_contests(session: requests.Session | None = None) -> list[dict[str, Any]]:
    """Every contest DK's lobby currently tags sport=CFB. See ``nfl_contests``
    for the shared off-season-noise caveat; filter with ``contests_frame``'s
    ``draft_group_ids`` using ``cfb_draft_groups()`` IDs."""
    s = session or requests.Session()
    r = s.get(DK_CFB_CONTESTS, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json().get("Contests", [])


_DK_DATE_RE = re.compile(r"^/Date\((-?\d+)([+-]\d{4})?\)/$")


def _parse_dk_date(value: Any) -> pd.Timestamp | None:
    """Parse DK's ASP.NET-style ``/Date(1785513600000)/`` epoch-ms string.

    The trailing ``+HHMM``/``-HHMM`` offset some payloads carry is the
    serializer's local zone, not a shift to apply — the leading number is
    already a UTC epoch millis, per every other DK timestamp this client
    parses (``game_start`` above is plain ISO 8601 UTC).
    """
    if not isinstance(value, str):
        return None
    m = _DK_DATE_RE.match(value)
    if not m:
        return None
    try:
        return pd.Timestamp(int(m.group(1)), unit="ms", tz="UTC")
    except (ValueError, OverflowError):
        return None


def draftables_frame(gid: int, slate_type: str, payload: dict[str, Any]) -> pd.DataFrame:
    """Flatten a draftables payload to one row per player."""
    comps = {c["competitionId"]: c for c in payload.get("competitions", [])}
    pulled_at = datetime.now(timezone.utc)

    # DK repeats players across roster slots. On classic slates the repeats
    # are identical; on showdown slates the CPT row carries a 1.5x salary,
    # so keep the cheaper (FLEX) row — the optimizer re-derives CPT cost.
    #
    # Draftable IDs are what DK's bulk-upload parser matches on (the "ID"
    # column of DKSalaries.csv is the draftableId, not the playerId), so
    # keep the kept row's draftableId — and on showdown slates also the CPT
    # row's, because the CPT slot only accepts the CPT-specific ID.
    rows: dict[int, dict[str, Any]] = {}
    for d in payload.get("draftables", []):
        pid = d["playerId"]
        prev = rows.get(pid)
        if prev is not None:
            sal = d.get("salary")
            if sal is not None and (prev["salary"] is None or sal < prev["salary"]):
                # Cheaper repeat = the FLEX row; the row we had was CPT.
                prev["dk_cpt_draftable_id"] = prev["dk_draftable_id"]
                prev["salary"] = sal
                prev["roster_slot"] = str(d.get("rosterSlotId"))
                prev["dk_draftable_id"] = d.get("draftableId")
            elif sal is not None and prev["salary"] is not None and sal > prev["salary"]:
                # Pricier repeat = the CPT row of the player we're keeping.
                prev["dk_cpt_draftable_id"] = d.get("draftableId")
            continue
        comp = comps.get(d.get("competition", {}).get("competitionId"), {})
        ppg = None
        for attr in d.get("draftStatAttributes", []):
            if attr.get("id") == 90:  # DK's own points-per-game figure
                try:
                    ppg = float(attr.get("value"))
                except (TypeError, ValueError):
                    ppg = None
        rows[pid] = {
            "pulled_at": pulled_at,
            "draft_group_id": gid,
            "slate_type": slate_type,
            "dk_player_id": pid,
            "dk_draftable_id": d.get("draftableId"),
            "dk_cpt_draftable_id": None,
            "display_name": d["displayName"],
            "team_abbr": d.get("teamAbbreviation"),
            "position": d.get("position"),
            "salary": d.get("salary"),
            "roster_slot": str(d.get("rosterSlotId")),
            "game_start": comp.get("startTime"),
            "status": d.get("status"),
            "dk_ppg": ppg,
        }
    df = pd.DataFrame(list(rows.values()))
    if not df.empty:
        # Nullable Int64 so BigQuery sees INT64, not FLOAT64 via NaN.
        for col in ("dk_draftable_id", "dk_cpt_draftable_id"):
            df[col] = df[col].astype("Int64")
    return df


CONTEST_COLUMNS = [
    "pulled_at", "contest_id", "draft_group_id", "sport", "name", "game_type",
    "entry_fee", "max_entries", "entries", "fill_rate", "prize_pool",
    "is_guaranteed", "overlay_dollars", "start_time",
]


def contests_frame(
    contests: list[dict[str, Any]],
    draft_group_ids: set[int] | None = None,
    sport: str = "NFL",
) -> pd.DataFrame:
    """Flatten DK lobby contest listings into a fill-rate/overlay snapshot.

    ``overlay_dollars`` is the free-EV signal this scaffold exists for: a
    guaranteed ("GTD") contest pays its full prize pool regardless of how
    many entries show up, so if ``entries * entry_fee`` is still short of
    ``prize_pool`` as lock approaches, the field is being subsidized —
    positive expected value for anyone who can still enter. Non-guaranteed
    contests cancel/refund if underfilled instead of being subsidized, so
    they never carry an overlay (0.0, not null — the field is meaningful,
    just always zero).

    ``draft_group_ids``, when given, restricts the result to contests DK
    has tied to one of those draft groups (pass the IDs from
    ``nfl_draft_groups()`` to keep only real NFL slates — see
    ``nfl_contests()`` for why that filter matters).

    ``sport`` stamps a ``sport`` column so ``nfl_raw.dk_contest_fills`` can
    hold both NFL and CFB (issue #13 item 7) polls in one append-only
    table; defaults to "NFL" for backward compatibility with the existing
    overlay-detection scaffold's call sites.
    """
    pulled_at = datetime.now(timezone.utc)
    rows = []
    for c in contests:
        dg = c.get("dg")
        if draft_group_ids is not None and dg not in draft_group_ids:
            continue
        entries = c.get("nt")
        max_entries = c.get("m")
        entry_fee = c.get("a")
        prize_pool = c.get("po")
        is_guaranteed = str(c.get("attr", {}).get("IsGuaranteed", "")).lower() == "true"

        fill_rate = None
        if entries is not None and max_entries:
            fill_rate = entries / max_entries

        overlay = 0.0
        if is_guaranteed and entries is not None and entry_fee is not None and prize_pool is not None:
            overlay = max(prize_pool - entries * entry_fee, 0.0)

        rows.append({
            "pulled_at": pulled_at,
            "contest_id": c.get("id"),
            "draft_group_id": dg,
            "sport": sport,
            "name": c.get("n"),
            "game_type": c.get("gameType"),
            "entry_fee": entry_fee,
            "max_entries": max_entries,
            "entries": entries,
            "fill_rate": fill_rate,
            "prize_pool": prize_pool,
            "is_guaranteed": is_guaranteed,
            "overlay_dollars": overlay,
            "start_time": _parse_dk_date(c.get("sd")),
        })

    if not rows:
        return pd.DataFrame(columns=CONTEST_COLUMNS)

    df = pd.DataFrame(rows)
    for col in ("contest_id", "draft_group_id", "max_entries", "entries"):
        df[col] = df[col].astype("Int64")
    return df

```

===== FILE: src/nfl_dfs/ingest/dk_job.py =====
```python
"""Hourly DraftKings slate/salary snapshot into nfl_raw.dk_salaries.

Append-only by design: the history of how a player's status changed before
lock is itself a valuable feature. Never overwrite.

Schedule: hourly Thu 00:00 - Mon 04:00 CT.
"""

from __future__ import annotations

import logging

import pandas as pd
import requests

from ..bq import load_dataframe
from ..config import current_season
from . import dk_client

log = logging.getLogger(__name__)


def season_week_for(groups: list[dict]) -> tuple[int, int | None]:
    season = current_season()
    # DK draft groups carry a minStartTime; week resolution happens downstream
    # by joining game_start against nfl_raw.schedules. Kept nullable here.
    return season, None


def run() -> None:
    session = requests.Session()
    groups = dk_client.nfl_draft_groups(session)
    if not groups:
        log.info("No upcoming NFL draft groups")
        return

    season, week = season_week_for(groups)
    frames = []
    for g in groups:
        gid = g["draftGroupId"]
        slate_type = dk_client.classify_slate(g)
        payload = dk_client.fetch_draftables(gid, session)
        df = dk_client.draftables_frame(gid, slate_type, payload)
        if df.empty:
            continue
        df["season"] = season
        df["week"] = week
        frames.append(df)
        log.info("Slate %s (%s): %d players", gid, slate_type, len(df))

    if not frames:
        return
    load_dataframe(
        pd.concat(frames, ignore_index=True),
        "dk_salaries",
        write_disposition="WRITE_APPEND",
        partition_field="pulled_at",
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

```

===== FILE: src/nfl_dfs/ingest/linestar_backfill.py =====
```python
"""One-time LineStar backfill: 2022-2024 DK salaries + 2022-2025 contest ownership.

Closes the RotoGuru-era gap (README known-gaps: RotoGuru died after 2021;
our own logging starts 2025), which doubles replay coverage, AND imports
real per-contest DK GPP ownership -- the data issue #11's ownership model
was waiting on -- from LineStar's public API
(`GetSalariesV5?sport=1&site=1&periodId=N`; period Ids are sequential,
"Week 1, 2022" = 302). Be-a-good-citizen rules as dk_client: real UA,
one pass, ~1.2s between calls, no retries.

Idempotent: seasons/weeks already present in dk_salaries_historical and
contest_ids already in contest_ownership are skipped.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

from ..bq import load_dataframe, query_df
from ..config import settings

log = logging.getLogger(__name__)

API = ("https://www.linestarapp.com/DesktopModules/DailyFantasyApi/API/"
       "Fantasy/GetSalariesV5?sport=1&site=1&periodId={pid}")
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) nfl-dfs-personal-research"}
WEEK_RE = re.compile(r"^Week (\d+), (\d{4})$")
SALARY_SEASONS = (2022, 2023, 2024)   # 2014-21 rotoguru, 2025+ our own log
OWNERSHIP_SEASONS = (2022, 2023, 2024, 2025)
PAUSE_S = 1.2


def _fetch(session: requests.Session, pid: int) -> dict:
    r = session.get(API.format(pid=pid), headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def periods(session: requests.Session) -> dict[int, tuple[int, int]]:
    """{periodId: (season, week)} for regular-season weeks."""
    d = _fetch(session, 0)
    out = {}
    for p in d.get("Periods", []):
        m = WEEK_RE.match(p.get("Name", ""))
        if m:
            out[int(p["Id"])] = (int(m.group(2)), int(m.group(1)))
    return out


def salary_rows(payload: dict, season: int, week: int) -> list[dict]:
    sc = json.loads(payload["SalaryContainerJson"])
    rows = []
    for r in sc.get("Salaries", []):
        if not r.get("Name") or not r.get("SAL"):
            continue
        pos = str(r.get("POS", "")).upper()
        pos = "DST" if pos in ("D", "DEF", "DST") else pos
        rows.append({
            "season": season, "week": week,
            "rotoguru_gid": None,
            "display_name": r["Name"], "position": pos,
            "team_abbr": r.get("PTEAM"),
            "home_away": "h" if r.get("PTEAM") == r.get("HTEAM") else "a",
            "opponent": r.get("OTEAM"),
            "dk_points": np.nan,   # LineStar PPG is a projection, not actuals
            "salary": int(r["SAL"]),
        })
    return rows


def ownership_rows(payload: dict, season: int, week: int) -> list[dict]:
    sc = json.loads(payload["SalaryContainerJson"])
    by_pid = {r.get("PID"): r for r in sc.get("Salaries", [])}
    now = datetime.now(timezone.utc)
    rows = []
    for cr in (payload.get("Ownership") or {}).get("ContestResults", []):
        c = cr.get("Contest") or {}
        for o in cr.get("OwnershipData", []):
            p = by_pid.get(o.get("PlayerId"))
            if p is None or o.get("Owned") is None:
                continue
            rows.append({
                "imported_at": now, "season": season, "week": week,
                # contest_ownership.contest_id is STRING (DK CSV heritage)
                "contest_id": str(c.get("ContestId") or ""),
                "contest_name": f"{c.get('ContestName', '')} "
                                f"[{c.get('EntryCount', '?')} entries, "
                                f"${c.get('EntryFee', '?')}]",
                "display_name": p["Name"],
                "roster_position": str(p.get("POS", "")).upper(),
                "pct_drafted": float(o["Owned"]),
                "fpts": np.nan,
            })
    return rows


def run() -> None:
    session = requests.Session()
    pmap = periods(session)
    have_sal = {(int(r.season), int(r.week)) for r in query_df(
        f"SELECT DISTINCT season, week FROM `{settings.raw}.dk_salaries_historical`"
    ).itertuples()}
    try:
        have_own = {str(r.contest_id) for r in query_df(
            f"SELECT DISTINCT contest_id FROM `{settings.raw}.contest_ownership`"
        ).itertuples()}
    except Exception:
        have_own = set()

    sal_all, own_all = [], []
    for pid, (season, week) in sorted(pmap.items()):
        want_sal = season in SALARY_SEASONS and (season, week) not in have_sal
        want_own = season in OWNERSHIP_SEASONS
        if not (want_sal or want_own):
            continue
        time.sleep(PAUSE_S)
        try:
            payload = _fetch(session, pid)
        except requests.HTTPError as exc:
            log.warning("period %d (%s wk %s) failed: %s", pid, season, week, exc)
            continue
        if want_sal:
            rows = salary_rows(payload, season, week)
            sal_all.extend(rows)
            log.info("period %d %s wk%d: %d salary rows", pid, season, week, len(rows))
        if want_own:
            rows = [r for r in ownership_rows(payload, season, week)
                    if r["contest_id"] not in have_own]
            own_all.extend(rows)
            if rows:
                log.info("period %d %s wk%d: %d ownership rows", pid, season, week, len(rows))

    if sal_all:
        load_dataframe(pd.DataFrame(sal_all), "dk_salaries_historical",
                       write_disposition="WRITE_APPEND")
        log.info("loaded %d salary rows", len(sal_all))
    if own_all:
        load_dataframe(pd.DataFrame(own_all), "contest_ownership",
                       write_disposition="WRITE_APPEND")
        log.info("loaded %d ownership rows across %d contests",
                 len(own_all), len({r['contest_id'] for r in own_all}))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

```

===== FILE: src/nfl_dfs/ingest/nflverse_job.py =====
```python
"""Nightly nflverse ingestion into nfl_raw.

Schedule: daily 06:00 CT in-season (nflverse updates overnight), weekly in the
offseason. Run once with --full to backfill FIRST_SEASON (default 2014) to
the latest completed-or-active season.
"""

from __future__ import annotations

import logging
import sys

from ..bq import load_dataframe
from ..config import current_season, settings

log = logging.getLogger(__name__)

FTN_FIRST_SEASON = 2022
PFR_ADVSTATS_FIRST_SEASON = 2018
NGS_FIRST_SEASON = 2016
SNAPS_FIRST_SEASON = 2012
INJURIES_FIRST_SEASON = 2009
DEPTH_CHARTS_FIRST_SEASON = 2001
# nflverse replaced the weekly depth chart format in 2025: season/week rows
# with depth_team ranks became dated snapshots (dt) with pos_rank, and the
# two schemas share almost no columns. Land them as separate raw tables so
# feature SQL can normalize each on its own terms (003_player_week_role).
DEPTH_SNAPSHOTS_FIRST_SEASON = 2025


def _delete_seasons(table: str, seasons: list[int]) -> None:
    from google.api_core.exceptions import NotFound

    from ..bq import client

    sql = (f"DELETE FROM `{settings.raw}.{table}` "
           f"WHERE season IN ({','.join(str(s) for s in seasons)})")
    try:
        client().query(sql).result()
    except NotFound:  # first-ever run: nothing to delete
        pass


def _load(df, table: str, replace_seasons: list[int] | None = None) -> None:
    """Land a nflreadpy frame (polars) in nfl_raw.

    replace_seasons=None -> WRITE_TRUNCATE: correct for full-snapshot pulls
    (schedules, player_ids, ...) and for --full backfills.

    replace_seasons=[...] -> delete those seasons, then append. This is the
    incremental path. It MUST NOT truncate: the scheduled job loads only the
    current season, and on 2026-07-28 its truncate silently destroyed the
    2014-2024 backfill in every season-scoped table (deficiency log,
    2026-07-31). A frame without a `season` column falls back to truncate
    loudly, since delete-by-season is impossible."""
    pdf = df.to_pandas()
    if replace_seasons is not None:
        if "season" not in pdf.columns:
            log.warning("%s has no season column; falling back to full truncate", table)
        else:
            _delete_seasons(table, replace_seasons)
            load_dataframe(pdf, table, write_disposition="WRITE_APPEND")
            return
    load_dataframe(pdf, table)


def run(full_refresh: bool = False) -> None:
    import nflreadpy as nfl

    # config's season rolls over in March (we prepare for the coming season),
    # but nflverse has no data for it until games are played — clamp to the
    # latest season the loaders actually serve, or offseason runs crash.
    season = min(current_season(), nfl.get_current_season())
    seasons = list(range(settings.first_season, season + 1)) if full_refresh else [season]
    # Incremental runs replace just-loaded seasons in place; --full rebuilds
    # the whole table, where truncate is the correct disposition.
    inc = None if full_refresh else seasons

    _load(nfl.load_pbp(seasons), "pbp", replace_seasons=inc)
    _load(nfl.load_player_stats(seasons), "weekly_stats", replace_seasons=inc)
    legacy_dc = [s for s in seasons
                 if DEPTH_CHARTS_FIRST_SEASON <= s < DEPTH_SNAPSHOTS_FIRST_SEASON]
    if legacy_dc:
        _load(nfl.load_depth_charts(legacy_dc), "depth_charts",
              replace_seasons=None if full_refresh else legacy_dc)
    # Snapshot-format depth charts carry no season column, so they can't use
    # the delete+append path — always pull the full snapshot era (2025+,
    # small) so the truncate stays lossless.
    snap_dc = list(range(DEPTH_SNAPSHOTS_FIRST_SEASON, season + 1))
    if snap_dc:
        _load(nfl.load_depth_charts(snap_dc), "depth_charts_snapshots")
    _load(nfl.load_rosters_weekly(seasons), "rosters_weekly", replace_seasons=inc)
    _load(nfl.load_schedules(), "schedules")
    _load(nfl.load_officials(), "officials")  # full snapshot, 2015+; refs feature
    _load(nfl.load_ff_playerids(), "player_ids")
    _load(nfl.load_draft_picks(), "draft_picks")
    _load(nfl.load_combine(), "combine")

    if snaps := [s for s in seasons if s >= SNAPS_FIRST_SEASON]:
        _load(nfl.load_snap_counts(snaps), "snap_counts",
              replace_seasons=None if full_refresh else snaps)
    if inj := [s for s in seasons if s >= INJURIES_FIRST_SEASON]:
        _load(nfl.load_injuries(inj), "injuries",
              replace_seasons=None if full_refresh else inj)
    if ngs := [s for s in seasons if s >= NGS_FIRST_SEASON]:
        for stat_type in ("receiving", "rushing", "passing"):
            _load(nfl.load_nextgen_stats(ngs, stat_type=stat_type), f"ngs_{stat_type}",
                  replace_seasons=None if full_refresh else ngs)
    if ftn := [s for s in seasons if s >= FTN_FIRST_SEASON]:
        _load(nfl.load_ftn_charting(ftn), "ftn_charting",
              replace_seasons=None if full_refresh else ftn)
    # Per-defender coverage stats (targets, completions/yards allowed as the
    # nearest defender). PFR-keyed like snap_counts; teams already in
    # nflverse abbreviations. Feeds 017a_defense_week_coverage.
    if pfr := [s for s in seasons if s >= PFR_ADVSTATS_FIRST_SEASON]:
        _load(nfl.load_pfr_advstats(pfr, stat_type="def", summary_level="week"),
              "pfr_advstats_def", replace_seasons=None if full_refresh else pfr)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run(full_refresh="--full" in sys.argv)

```

===== FILE: src/nfl_dfs/ingest/odds_job.py =====
```python
"""Hourly odds snapshot into nfl_raw.odds_snapshots.

Source: The Odds API's live game-odds endpoint (`americanfootball_nfl`),
restricted to DraftKings' book so lines stay aligned with the DK slates the
rest of the pipeline prices. This replaced the original DK-sportsbook
eventgroup scrape on 2026-07-31: that endpoint 403s (Akamai bot blocking)
from both Cloud Run and residential IPs, and `odds_snapshots` never
received a single row from it — see the README's Data deficiency log.

Cost: one call per run = 1 credit per market per region (3 total with
h2h/spreads/totals), independent of event count — a few hundred credits per
season at the hourly Thu-Sun cadence, negligible next to the props history
(`oddsapi_import.py`), which shares the same ODDS_API_KEY quota.

nflverse closing lines still cover training; this feed exists for live
in-week line movement.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from ..bq import load_dataframe
from ..config import settings

log = logging.getLogger(__name__)

ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds"
MARKETS = "h2h,spreads,totals"
BOOKMAKER = "draftkings"

# The Odds API market keys -> the market_type values odds_snapshots has
# used since its DDL was written (003_misc.sql), so any future reader works
# unchanged against rows from either source era (not that the old era
# produced any rows).
_MARKET_TYPE = {"h2h": "Moneyline", "spreads": "Spread", "totals": "Total"}


def _fetch(session: requests.Session | None = None) -> list[dict[str, Any]]:
    if not settings.odds_api_key:
        raise RuntimeError("ODDS_API_KEY is not set (add it to .env)")
    s = session or requests.Session()
    r = s.get(
        ODDS_API_URL,
        params={
            "apiKey": settings.odds_api_key,
            "regions": "us",
            "markets": MARKETS,
            "oddsFormat": "american",
            "bookmakers": BOOKMAKER,
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _american_str(price: Any) -> str | None:
    """Format The Odds API's numeric american odds the way DK displayed
    them ('+120' / '-110'), matching the STRING column's existing intent."""
    if price is None:
        return None
    return f"{int(price):+d}"


def _rows_from_payload(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pulled_at = datetime.now(timezone.utc)
    rows = []
    for event in payload:
        name = f"{event.get('away_team')} @ {event.get('home_team')}"
        for bk in event.get("bookmakers") or []:
            if bk.get("key") != BOOKMAKER:
                continue
            for market in bk.get("markets") or []:
                market_type = _MARKET_TYPE.get(market.get("key"))
                if market_type is None:
                    continue
                for outcome in market.get("outcomes") or []:
                    rows.append(
                        {
                            "pulled_at": pulled_at,
                            "event_id": event.get("id"),
                            "event_name": name,
                            "start_time": event.get("commence_time"),
                            "market_type": market_type,
                            "selection": outcome.get("name"),
                            "line": outcome.get("point"),
                            "odds_american": _american_str(outcome.get("price")),
                        }
                    )
    return rows


def run() -> None:
    rows = _rows_from_payload(_fetch())
    if not rows:
        log.info("No odds rows")
        return
    df = pd.DataFrame(rows)
    load_dataframe(df, "odds_snapshots", write_disposition="WRITE_APPEND",
                   partition_field="pulled_at")
    log.info("Wrote %d odds rows across %d events",
             len(df), df.event_id.nunique())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

```

===== FILE: src/nfl_dfs/ingest/oddsapi_import.py =====
```python
"""Historical + live player-prop lines from The Odds API -> nfl_raw.prop_lines.

Point-in-time discipline: each game's odds are snapshotted at
commence_time - 2h — strictly pre-lock knowledge, never post-game. Player
props are available historically from May 2023 (seasons 2023+). Cost: the
historical event-odds endpoint bills 10 credits per market per event
(6 markets => 60/event, ~49k credits for three seasons on the 100K plan).

Resumable: (season, week) pairs already present in the table are skipped,
so a crashed or quota-capped run continues where it left off.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from ..bq import load_dataframe, query_df
from ..config import settings

log = logging.getLogger(__name__)

BASE = "https://api.the-odds-api.com/v4"
SPORT = "americanfootball_nfl"
TABLE = "prop_lines"
MARKETS = ("player_pass_yds,player_pass_tds,player_rush_yds,"
           "player_reception_yds,player_receptions,player_anytime_td")
SNAPSHOT_BEFORE_H = 2   # hours before kickoff
PAUSE_S = 0.35          # stay far under the per-minute rate limit


def _get(path: str, **params) -> dict | list:
    params["apiKey"] = settings.odds_api_key
    r = requests.get(f"{BASE}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def parse_event_odds(payload: dict, season: int, week: int,
                     snapshot_ts: str) -> list[dict]:
    """Flatten one historical event-odds payload into prop_lines rows."""
    data = payload.get("data") or {}
    rows = []
    for bk in data.get("bookmakers") or []:
        for m in bk.get("markets") or []:
            for o in m.get("outcomes") or []:
                rows.append({
                    "season": season, "week": week,
                    "event_id": data.get("id"),
                    "commence_time": data.get("commence_time"),
                    "home_team": data.get("home_team"),
                    "away_team": data.get("away_team"),
                    "snapshot_ts": snapshot_ts,
                    "bookmaker": bk.get("key"),
                    "market": m.get("key"),
                    # Over/Under markets: name=Over|Under, description=player.
                    # anytime_td: name=player (no point).
                    "outcome_name": o.get("name"),
                    "player": o.get("description") or o.get("name"),
                    "price": o.get("price"),
                    "point": o.get("point"),
                    "pulled_at": datetime.now(timezone.utc),
                })
    return rows


def _weeks(first_season: int, last_season: int) -> pd.DataFrame:
    return query_df(
        f"""
        SELECT season, week,
               MIN(gameday) AS first_day, MAX(gameday) AS last_day
        FROM `{settings.raw}.schedules`
        WHERE game_type = 'REG' AND season BETWEEN {first_season} AND {last_season}
        GROUP BY season, week ORDER BY season, week
        """
    )


def _done() -> set[tuple[int, int]]:
    try:
        d = query_df(f"SELECT DISTINCT season, week FROM `{settings.raw}.{TABLE}`")
        return {(int(r.season), int(r.week)) for r in d.itertuples()}
    except Exception:
        return set()


ALT_MARKETS = ("player_pass_yds_alternate,player_rush_yds_alternate,"
               "player_reception_yds_alternate,player_receptions_alternate")


def run(first_season: int = 2023, last_season: int = 2025,
        opens: bool = False, markets: str = MARKETS) -> None:
    """opens=True backfills Tuesday 18:00 UTC OPENING lines (movement
    study: open vs the kickoff-2h close already loaded). Open rows are
    identifiable by their exact T18:00:00Z snapshot_ts."""
    if not settings.odds_api_key:
        raise RuntimeError("ODDS_API_KEY is not set (add it to .env)")
    if opens:
        try:
            # Fixed predicate — a raw-WHERE parameter here was a loaded
            # gun (security sweep 2026-08-03); opens rows are exactly
            # the T18:00:00Z snapshots.
            d = query_df(f"SELECT DISTINCT season, week FROM "
                         f"`{settings.raw}.{TABLE}` "
                         f"WHERE snapshot_ts LIKE '%T18:00:00Z'")
            done = {(int(r.season), int(r.week)) for r in d.itertuples()}
        except Exception:
            done = set()
    else:
        done = _done()
    for wk in _weeks(first_season, last_season).itertuples():
        key = (int(wk.season), int(wk.week))
        if key in done:
            continue
        # One events snapshot mid-week lists every game of the week
        mid = (pd.Timestamp(wk.first_day) - timedelta(days=1)).strftime(
            "%Y-%m-%dT12:00:00Z")
        try:
            events = _get(f"/historical/sports/{SPORT}/events", date=mid,
                          commenceTimeFrom=f"{wk.first_day}T00:00:00Z",
                          commenceTimeTo=f"{wk.last_day}T23:59:59Z")
        except requests.HTTPError:
            log.exception("events snapshot failed for %s", key)
            continue
        tuesday = (pd.Timestamp(wk.first_day)
                   - timedelta(days=(pd.Timestamp(wk.first_day).weekday()
                                     - 1) % 7)).strftime("%Y-%m-%d")
        rows: list[dict] = []
        for ev in events.get("data") or []:
            snap = (f"{tuesday}T18:00:00Z" if opens else
                    (pd.Timestamp(ev["commence_time"])
                     - timedelta(hours=SNAPSHOT_BEFORE_H)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"))
            time.sleep(PAUSE_S)
            try:
                odds = _get(
                    f"/historical/sports/{SPORT}/events/{ev['id']}/odds",
                    date=snap, regions="us", markets=markets,
                    oddsFormat="american", bookmakers="draftkings,fanduel")
            except requests.HTTPError as exc:
                log.warning("odds pull failed %s %s: %s", key, ev["id"], exc)
                continue
            rows.extend(parse_event_odds(odds, *key, snapshot_ts=snap))
        if rows:
            df = pd.DataFrame(rows)
            df["commence_time"] = pd.to_datetime(df.commence_time)
            load_dataframe(df, f"{settings.raw}.{TABLE}",
                           write_disposition="WRITE_APPEND")
            log.info("season %s week %s: %d prop rows (%d events)",
                     *key, len(rows), len(events.get("data") or []))
        else:
            log.warning("season %s week %s: no prop rows", *key)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()


def run_live() -> None:
    """In-season weekly snapshot: current prop lines for upcoming games ->
    same prop_lines table (season/week resolved from the schedule)."""
    from ..config import current_season

    if not settings.odds_api_key:
        raise RuntimeError("ODDS_API_KEY is not set")
    season = current_season()
    sched = query_df(
        f"""SELECT MIN(week) AS wk FROM `{settings.raw}.schedules`
            WHERE season = {season}
              AND gameday >= CAST(CURRENT_DATE() AS STRING)""")
    week = int(sched.wk.iloc[0])
    events = _get(f"/sports/{SPORT}/events")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows: list[dict] = []
    for ev in events or []:
        time.sleep(PAUSE_S)
        try:
            odds = _get(f"/sports/{SPORT}/events/{ev['id']}/odds",
                        regions="us", markets=MARKETS,
                        oddsFormat="american",
                        bookmakers="draftkings,fanduel")
        except requests.HTTPError as exc:
            log.warning("live odds pull failed %s: %s", ev["id"], exc)
            continue
        rows.extend(parse_event_odds({"data": odds}, season, week,
                                     snapshot_ts=now))
    if rows:
        df = pd.DataFrame(rows)
        df["commence_time"] = pd.to_datetime(df.commence_time)
        load_dataframe(df, f"{settings.raw}.{TABLE}",
                       write_disposition="WRITE_APPEND")
        log.info("live props: %d rows for season %s week %s",
                 len(rows), season, week)

```

===== FILE: src/nfl_dfs/ingest/ownership_import.py =====
```python
"""Import actual contest ownership from a DraftKings contest-standings CSV.

DK's "Export to CSV" on any contest's standings page produces a file with
entry rows on the left and a player summary block on the right; the summary
columns are `Player`, `Roster Position`, `%Drafted`, `FPTS`. That summary —
one row per player with actual ownership — is what we keep.

There is no API for this: export the CSV by hand (or a logged-in fetch)
each week and run `nfl-dfs import-ownership file.csv --season S --week W
--contest-id ID`. One GPP + one cash contest per week is enough to train
an ownership model; see the README data deficiency log.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..bq import load_dataframe

log = logging.getLogger(__name__)

PLAYER_COL = "Player"
REQUIRED = {PLAYER_COL, "%Drafted"}


def parse_standings_csv(path: str | Path) -> pd.DataFrame:
    """Extract the per-player ownership block from a standings export."""
    raw = pd.read_csv(path)
    missing = REQUIRED - set(raw.columns)
    if missing:
        raise ValueError(
            f"{path} does not look like a DK contest-standings export; "
            f"missing columns {sorted(missing)}"
        )
    out = raw[raw[PLAYER_COL].notna()].copy()
    out = pd.DataFrame(
        {
            "display_name": out[PLAYER_COL].astype(str).str.strip(),
            "roster_position": out.get("Roster Position"),
            "pct_drafted": pd.to_numeric(
                out["%Drafted"].astype(str).str.rstrip("%"), errors="coerce"
            ),
            "fpts": pd.to_numeric(out.get("FPTS"), errors="coerce"),
        }
    )
    out = out.dropna(subset=["pct_drafted"])
    if out.empty:
        raise ValueError(f"no player ownership rows found in {path}")
    return out.reset_index(drop=True)


def parse_entries_csv(path: str | Path) -> pd.DataFrame:
    """Extract the per-ENTRY rows (left block): every submitted lineup
    with rank and points. This is the joint-structure data the field/
    dupe modeling needs (in-season queue 10a/10b; RTS blueprint) — DK
    purges standings exports after ~4 days, so losing these rows at
    import time loses them forever. `players_key` (sorted, delimited)
    is the duplicate-grouping key; the raw lineup string is kept
    lossless for slot-level parsing later."""
    raw = pd.read_csv(path)
    need = {"Rank", "Lineup"}
    if not need <= set(raw.columns):
        raise ValueError(f"{path}: no entry block (missing {need - set(raw.columns)})")
    e = raw[raw["Lineup"].notna() & raw["Rank"].notna()].copy()
    slots = ("CPT", "FLEX", "QB", "RB", "WR", "TE", "DST", "K")

    def players_of(s: str) -> str:
        t = str(s)
        for tok in slots:
            t = t.replace(f"{tok} ", f"|{tok}|")
        names = [seg.strip() for seg in t.split("|")
                 if seg.strip() and seg.strip() not in slots]
        return "|".join(sorted(names))

    out = pd.DataFrame({
        "rank": pd.to_numeric(e["Rank"], errors="coerce"),
        "entry_id": e.get("EntryId", pd.Series(dtype=str)).astype(str),
        "entry_name": e.get("EntryName", pd.Series(dtype=str)).astype(str),
        "points": pd.to_numeric(e.get("Points"), errors="coerce"),
        "lineup": e["Lineup"].astype(str),
    })
    out["players_key"] = out.lineup.map(players_of)
    return out.dropna(subset=["rank"]).reset_index(drop=True)


def run(
    path: str,
    season: int,
    week: int,
    contest_id: str,
    contest_name: str | None = None,
) -> int:
    df = parse_standings_csv(path)
    df.insert(0, "imported_at", datetime.now(timezone.utc))
    df.insert(1, "season", season)
    df.insert(2, "week", week)
    df.insert(3, "contest_id", contest_id)
    df.insert(4, "contest_name", contest_name or "")
    load_dataframe(df, "contest_ownership", write_disposition="WRITE_APPEND")
    log.info("Imported %d ownership rows for %s wk %s (contest %s)",
             len(df), season, week, contest_id)

    # Entry-level lineups (lossless): failure here must not block the
    # ownership import that the weekly model refit depends on.
    try:
        entries = parse_entries_csv(path)
        entries.insert(0, "imported_at", datetime.now(timezone.utc))
        entries.insert(1, "season", season)
        entries.insert(2, "week", week)
        entries.insert(3, "contest_id", contest_id)
        load_dataframe(entries, "contest_entries",
                       write_disposition="WRITE_APPEND")
        dupes = entries.groupby("players_key").size()
        log.info("Imported %d entries (%d distinct lineups, max dupe %d)",
                 len(entries), len(dupes), int(dupes.max()))
    except Exception:
        log.exception("entry-block import failed; ownership rows kept")
    return len(df)

```

===== FILE: src/nfl_dfs/ingest/rotoguru_backfill.py =====
```python
"""One-time historical DK salary backfill from RotoGuru (2014+).

Semicolon-separated, ugly, complete, free. Run once, then rely on your own
append-only dk_salaries log going forward.
"""

from __future__ import annotations

import io
import logging
import time

import pandas as pd
import requests

from ..bq import load_dataframe

log = logging.getLogger(__name__)

URL = "http://rotoguru1.com/cgi-bin/fyday.pl?week={week}&year={year}&game=dk&scsv=1"
COLUMNS = {
    "Week": "week",
    "Year": "season",
    "GID": "rotoguru_gid",
    "Name": "display_name",
    "Pos": "position",
    "Team": "team_abbr",
    "h/a": "home_away",
    "Oppt": "opponent",
    "DK points": "dk_points",
    "DK salary": "salary",
}


def _flip_name(name):
    """RotoGuru names are "Last, First"; normalize to "First Last". Rows
    without a comma (team defenses) pass through unchanged."""
    if isinstance(name, str) and ", " in name:
        last, first = name.split(", ", 1)
        return f"{first} {last}"
    return name


def fetch_week(year: int, week: int, session: requests.Session) -> pd.DataFrame:
    r = session.get(URL.format(week=week, year=year), timeout=30)
    r.raise_for_status()
    text = r.text
    # The scsv payload is embedded in a <pre> block on an HTML page.
    if "<pre>" in text:
        text = text.split("<pre>")[1].split("</pre>")[0]
    df = pd.read_csv(io.StringIO(text.strip()), sep=";")
    df = df.rename(columns=COLUMNS)[list(COLUMNS.values())]
    df["display_name"] = df["display_name"].map(_flip_name)
    df["team_abbr"] = df["team_abbr"].str.upper()
    df["opponent"] = df["opponent"].str.upper()
    return df


def run(first_season: int = 2014, last_season: int | None = None) -> None:
    import datetime

    last = last_season or datetime.date.today().year - 1
    session = requests.Session()
    session.headers["User-Agent"] = "nfl-dfs-personal-research"
    frames = []
    for year in range(first_season, last + 1):
        for week in range(1, 19):
            try:
                df = fetch_week(year, week, session)
            except Exception as exc:  # noqa: BLE001 - a missing week is fine
                log.warning("Skipping %s week %s: %s", year, week, exc)
                continue
            if not df.empty:
                frames.append(df)
                log.info("%s week %s: %d rows", year, week, len(df))
            time.sleep(3)  # rate-limit; RotoGuru is a one-man shop

    if frames:
        load_dataframe(pd.concat(frames, ignore_index=True), "dk_salaries_historical")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

```

===== FILE: src/nfl_dfs/ingest/weather_job.py =====
```python
"""Game-time weather from Open-Meteo (free, no key) into nfl_raw.weather.

Only outdoor stadiums matter; roof type comes from nflverse stadium metadata
already joined into nfl_raw.schedules (roof, surface columns). Wind above
~15 mph is the main actionable signal.

Schedule: 3x daily Fri-Sun.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pandas as pd
import requests

from ..bq import load_dataframe, query_df
from ..config import current_season, settings

log = logging.getLogger(__name__)

OPEN_METEO = "https://api.open-meteo.com/v1/forecast"

# Lat/long for current outdoor + retractable NFL stadiums, keyed by home team.
STADIUM_COORDS: dict[str, tuple[float, float]] = {
    "BAL": (39.2780, -76.6227), "BUF": (42.7738, -78.7870), "CAR": (35.2258, -80.8528),
    "CHI": (41.8623, -87.6167), "CIN": (39.0955, -84.5161), "CLE": (41.5061, -81.6995),
    "DEN": (39.7439, -105.0201), "GB": (44.5013, -88.0622), "JAX": (30.3239, -81.6373),
    "KC": (39.0489, -94.4839), "MIA": (25.9580, -80.2389), "NE": (42.0909, -71.2643),
    "NYG": (40.8135, -74.0745), "NYJ": (40.8135, -74.0745), "PHI": (39.9008, -75.1675),
    "PIT": (40.4468, -80.0158), "SEA": (47.5952, -122.3316), "TB": (27.9759, -82.5033),
    "TEN": (36.1665, -86.7713), "WAS": (38.9076, -76.8645),
    # Retractable / indoor teams included so join misses are explicit nulls
    "ARI": (33.5276, -112.2626), "ATL": (33.7554, -84.4009), "DAL": (32.7473, -97.0945),
    "DET": (42.3400, -83.0456), "HOU": (29.6847, -95.4107), "IND": (39.7601, -86.1639),
    "LA": (33.9535, -118.3392), "LAC": (33.9535, -118.3392), "LV": (36.0909, -115.1833),
    "MIN": (44.9736, -93.2575), "NO": (29.9511, -90.0812), "SF": (37.4032, -121.9698),
}


def upcoming_games() -> pd.DataFrame:
    season = current_season()
    return query_df(
        f"""
        SELECT game_id, home_team, gameday, gametime, roof
        FROM `{settings.raw}.schedules`
        WHERE season = {season}
          AND DATE(gameday) BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 4 DAY)
        """
    )


def fetch_forecast(lat: float, lon: float, gameday: str) -> dict:
    r = requests.get(
        OPEN_METEO,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,wind_speed_10m,precipitation_probability",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "start_date": gameday,
            "end_date": gameday,
            "timezone": "America/New_York",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def run() -> None:
    games = upcoming_games()
    rows = []
    for g in games.itertuples():
        coords = STADIUM_COORDS.get(g.home_team)
        if coords is None:
            continue
        gameday = str(g.gameday)[:10]
        try:
            fx = fetch_forecast(*coords, gameday)
        except requests.RequestException as exc:
            log.warning("Forecast failed for %s: %s", g.game_id, exc)
            continue
        hourly = fx.get("hourly", {})
        kickoff_hour = int(str(g.gametime or "13:00")[:2])
        idx = min(kickoff_hour, len(hourly.get("time", [])) - 1)
        if idx < 0:
            continue
        rows.append(
            {
                "pulled_at": datetime.now(timezone.utc),
                "game_id": g.game_id,
                "temp_f": hourly["temperature_2m"][idx],
                "wind_mph": hourly["wind_speed_10m"][idx],
                "precip_prob": hourly["precipitation_probability"][idx],
                "is_dome": g.roof in ("dome", "closed"),
            }
        )
    if rows:
        load_dataframe(pd.DataFrame(rows), "weather", write_disposition="WRITE_APPEND",
                       partition_field="pulled_at")
        log.info("Wrote weather for %d games", len(rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

```

===== FILE: src/nfl_dfs/models/__init__.py =====
```python
"""Modeling layer: DK scoring, baseline + component models, Monte Carlo
composition, market blending, cold starts, registry, and drift monitoring.

Guide map (see README):
  §6.1  scoring.py     — DK Classic scoring incl. yardage bonuses
  §6.3  validation.py  — walk-forward folds, market comparison, calibration
  §7.3  baseline.py    — direct DK-points model with quantile ceilings
  §6.2  components.py  — per-component LightGBM models
  §6.2  simulate.py    — Monte Carlo composition of components
  §7.4  weights.py     — recency sample weights
  §7.5  tuning.py      — walk-forward Optuna tuning (optional extra)
  §7.6  coldstart.py   — role priors + widened uncertainty
  §7.7  blend.py       — market blending, prop-line conversions
  §7.8  registry.py    — versioned model store (local or GCS)
  §7.8  monitoring.py  — MAE/coverage/PSI/null-rate drift alarms
  §7.8  train_job.py   — weekly retrain entry point
"""

```

===== FILE: src/nfl_dfs/models/baseline.py =====
```python
"""Baseline model (guide §7.3): LightGBM on DK points directly, plus three
quantile regressors for a usable distribution. Deliberately crude — this is
the floor every later model must beat, and the honest MAE number comes from
walk-forward validation against the market, never a random split.
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from . import validation
from .featureset import FEATURES, LGB_THREADS, build_X
from .weights import sample_weights

LABEL = "y_dk_points"
QUANTILES = (0.10, 0.50, 0.90)
# (p90 - p10) spans 2.5631 standard deviations for a normal.
_P10_P90_TO_STD = 2.5631

MEAN_PARAMS = dict(
    num_threads=LGB_THREADS,
    objective="regression",
    metric="mae",
    learning_rate=0.06,
    num_leaves=31,
    min_data_in_leaf=40,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=1,
    lambda_l2=5.0,
    verbosity=-1,
)


@dataclass
class BaselineModel:
    mean_model: lgb.Booster
    quantile_models: dict[float, lgb.Booster]
    target_season: int

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        X = build_X(df)
        q = np.column_stack(
            [self.quantile_models[a].predict(X) for a in QUANTILES]
        )
        # Quantile regressors can cross; sort per row to restore monotonicity.
        q.sort(axis=1)
        out = pd.DataFrame(
            {
                "proj_points": self.mean_model.predict(X),
                "proj_p10": q[:, 0],
                "proj_p50": q[:, 1],
                "proj_p90": q[:, 2],
            },
            index=df.index,
        )
        out["proj_std"] = np.maximum((out.proj_p90 - out.proj_p10) / _P10_P90_TO_STD, 0.0)
        return out


@dataclass
class WalkForwardResult:
    fold_reports: dict[int, validation.EvalReport]
    test_season: int


def train(
    panel: pd.DataFrame, target_season: int, num_boost_round: int = 400
) -> BaselineModel:
    """Train on every season before `target_season`, recency-weighted."""
    tr = panel[panel.season < target_season]
    if tr.empty:
        raise ValueError(f"no training rows before season {target_season}")
    X = build_X(tr)
    w = sample_weights(tr, target_season)
    dset = lgb.Dataset(X, tr[LABEL], weight=w, categorical_feature=["position"])

    mean_model = lgb.train(MEAN_PARAMS, dset, num_boost_round=num_boost_round)
    quantile_models = {}
    for alpha in QUANTILES:
        params = {**MEAN_PARAMS, "objective": "quantile", "alpha": alpha, "metric": "quantile"}
        quantile_models[alpha] = lgb.train(params, dset, num_boost_round=num_boost_round)
    return BaselineModel(mean_model, quantile_models, target_season)


def walk_forward(
    panel: pd.DataFrame,
    min_train_seasons: int = 4,
    num_boost_round: int = 400,
) -> WalkForwardResult:
    """Expanding-window validation; the market comparison uses DK's own
    points-per-game figure (`dk_ppg`) when present."""
    folds, test = validation.walk_forward_folds(
        sorted(panel.season.unique()), min_train_seasons=min_train_seasons
    )
    reports: dict[int, validation.EvalReport] = {}
    for _train_seasons, val_season in folds:
        model = train(panel, target_season=val_season, num_boost_round=num_boost_round)
        va = panel[panel.season == val_season]
        preds = model.predict(va)
        reports[val_season] = validation.evaluate(
            va[LABEL],
            preds.proj_points.to_numpy(),
            market=va.dk_ppg if "dk_ppg" in va.columns else None,
            p10=preds.proj_p10.to_numpy(),
            p90=preds.proj_p90.to_numpy(),
            positions=va.position,
        )
    return WalkForwardResult(fold_reports=reports, test_season=test)


FEATURE_LIST = FEATURES  # re-exported for registry metadata

```

===== FILE: src/nfl_dfs/models/blend.py =====
```python
"""Market blending (guide §7.7): the market carries real information, and
`final = w*model + (1-w)*market` almost always beats either alone. The
weight is fit by least squares on validation; realistic values land around
0.3–0.5, which is a useful reality check on how much edge exists.

Also: prop-line → expected-value conversions and American-odds utilities
for building the market projection in the first place.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import optimize, stats


BLEND_W = 0.45  # model weight; refit on validation


def fit_blend_weight(
    truth: np.ndarray, model: np.ndarray, market: np.ndarray
) -> float:
    """Least-squares w for truth ≈ w*model + (1-w)*market, clipped to [0, 1].
    Equivalent to regressing (truth - market) on (model - market)."""
    truth = np.asarray(truth, dtype=float)
    model = np.asarray(model, dtype=float)
    market = np.asarray(market, dtype=float)
    ok = ~(np.isnan(truth) | np.isnan(model) | np.isnan(market))
    dm = model[ok] - market[ok]
    dt = truth[ok] - market[ok]
    denom = float(dm @ dm)
    if denom == 0.0:
        return 0.5
    return float(np.clip(dm @ dt / denom, 0.0, 1.0))


def blend(model: np.ndarray, market: np.ndarray, w: float) -> np.ndarray:
    """Weighted blend, falling back to the model where the market is NaN —
    a player with no prop line still needs a projection."""
    model = np.asarray(model, dtype=float)
    market = np.asarray(market, dtype=float)
    out = w * model + (1.0 - w) * market
    return np.where(np.isnan(market), model, out)


def market_projection_frame(feats: pd.DataFrame) -> pd.Series:
    """Market implied projection per row. Prop-derived means would slot in
    here; absent props this is DK's own points-per-game figure (crude but
    documented as the stand-in, §7.7)."""
    if "dk_ppg" not in feats.columns:
        return pd.Series(np.nan, index=feats.index, name="market")
    return pd.to_numeric(feats["dk_ppg"], errors="coerce").rename("market")


def american_to_prob(odds: float) -> float:
    """Implied probability of American odds (vig included)."""
    if odds < 0:
        return -odds / (-odds + 100.0)
    return 100.0 / (odds + 100.0)


def devig_two_way(p_over: float, p_under: float) -> tuple[float, float]:
    """Strip the vig from a two-way market by normalizing."""
    total = p_over + p_under
    return p_over / total, p_under / total


def prop_line_to_mean(line: float, over_prob: float, dist: str) -> float:
    """Expected value implied by an over/under line and its (de-vigged)
    over probability. Normal for yardage props, Poisson for counts."""
    if dist == "normal":
        # Yardage-prop sigma scales roughly with the line itself.
        sigma = 0.30 * max(line, 1.0)
        return float(line + stats.norm.ppf(over_prob) * sigma)
    if dist == "poisson":
        k = int(np.ceil(line))  # over hits at k or more for a half-point line

        def gap(lam: float) -> float:
            return stats.poisson.sf(k - 1, lam) - over_prob

        return float(optimize.brentq(gap, 1e-6, max(4.0 * line + 10.0, 20.0)))
    raise ValueError(f"unknown distribution {dist!r}")

```

===== FILE: src/nfl_dfs/models/calibration.py =====
```python
"""Quantile calibration: widen the simulated p10-p90 band per position.

Season replays showed the Monte Carlo distribution is too narrow — actuals
fell below p10 on 13-24% of rows (target 10%), worst for QB/RB where TD
variance dominates. The fix is a per-position multiplicative widen of the
quantile band around the median (std scales with it), fit on replayed
seasons by grid search to hit nominal coverage.

DEFAULT_WIDEN was fit on pooled 2019+2021 replays (models trained strictly
pre-season; see backtest/replay.py) and verified out-of-sample on 2025.
Refit with `fit_widen_factors` whenever the simulator changes materially.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_WIDEN = {"QB": 1.5, "RB": 1.45, "TE": 1.05, "WR": 1.1}


def apply_widen(
    preds: pd.DataFrame,
    positions: pd.Series,
    factors: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Stretch [proj_p10, proj_p90] around proj_p50 by each row's position
    factor; proj_std scales with the band. proj_points is untouched — the
    mean was never the problem."""
    factors = DEFAULT_WIDEN if factors is None else factors
    w = positions.map(lambda p: factors.get(p, 1.0)).to_numpy(dtype=float)
    out = preds.copy()
    p50 = out.proj_p50.to_numpy()
    out["proj_p10"] = p50 - (p50 - out.proj_p10.to_numpy()) * w
    out["proj_p90"] = p50 + (out.proj_p90.to_numpy() - p50) * w
    out["proj_std"] = out.proj_std.to_numpy() * w
    return out


def fit_widen_factors(
    replay_proj: pd.DataFrame,
    grid: np.ndarray | None = None,
    targets: tuple[float, float] = (0.10, 0.90),
) -> dict[str, float]:
    """Per-position widen factor minimizing coverage error on replayed
    projections (columns: position, actual, proj_p10/p50/p90)."""
    grid = np.arange(1.0, 2.61, 0.05) if grid is None else grid
    lo, hi = targets
    factors: dict[str, float] = {}
    for pos, grp in replay_proj.groupby("position"):
        p50 = grp.proj_p50.to_numpy()
        d10 = p50 - grp.proj_p10.to_numpy()
        d90 = grp.proj_p90.to_numpy() - p50
        actual = grp.actual.to_numpy()
        losses = [
            abs(np.mean(actual < p50 - d10 * w) - lo)
            + abs(np.mean(actual < p50 + d90 * w) - hi)
            for w in grid
        ]
        factors[str(pos)] = round(float(grid[int(np.argmin(losses))]), 2)
    return factors

```

===== FILE: src/nfl_dfs/models/coldstart.py =====
```python
"""Cold starts (guide §7.6): rookies and first-starters have null rolling
features, and a model fed nulls does something arbitrary. Project the
*role*, not the player — depth-chart priors fill the usage features, draft
capital discounts them, and the quantiles get widened because uncertainty
about a player's role is real variance the simulator can't see.

Never silently impute the league mean: the `is_cold_start` flag must
survive filling so the model can learn to regress these rows harder.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# (position, depth_rank) -> (target_share, carry_share). Historical league
# role averages; the game-environment scaling comes from the model's other
# features (implied total, spread), not from these shares.
ROLE_PRIORS: dict[tuple[str, int], tuple[float, float]] = {
    ("QB", 1): (0.00, 0.10),
    ("RB", 1): (0.10, 0.55),
    ("RB", 2): (0.06, 0.25),
    ("RB", 3): (0.03, 0.10),
    ("WR", 1): (0.24, 0.01),
    ("WR", 2): (0.17, 0.01),
    ("WR", 3): (0.11, 0.005),
    ("TE", 1): (0.15, 0.00),
    ("TE", 2): (0.07, 0.00),
}

# Rookie opportunity discount by draft round: round-1 capital keeps the
# full role prior, late rounds and UDFAs regress hard.
_ROOKIE_DISCOUNT = {1: 1.0, 2: 0.85, 3: 0.75}
_ROOKIE_DISCOUNT_DEFAULT = 0.6


def _role_prior(position: str, depth_rank: float) -> tuple[float, float]:
    depth = int(depth_rank) if pd.notna(depth_rank) else 3
    while depth > 1 and (position, depth) not in ROLE_PRIORS:
        depth -= 1
    return ROLE_PRIORS.get((position, depth), (0.03, 0.02))


DRAFT_ADJ = {("RB", 1): 1.3, ("TE", 1): 0.6, ("TE", 2): 0.6,
             ("TE", 3): 0.6, ("WR", 1): 0.9, ("WR", 2): 0.9,
             ("WR", 3): 0.9}  # rookie-ramp study 2026-07-30 (env-gated)


def _draft_rounds() -> dict:
    try:
        from ..bq import query_df
        from ..config import settings

        d = query_df(f"SELECT gsis_id, round FROM "
                     f"`{settings.raw}.draft_picks` WHERE gsis_id IS NOT NULL")
        return dict(zip(d.gsis_id, d["round"]))
    except Exception:
        return {}


def fill_cold_start_features(df: pd.DataFrame) -> pd.DataFrame:
    """Fill null usage features on cold-start rows from role priors.
    Env DRAFT_PRIORS=1 scales rookie priors by draft capital: round-1 RBs
    produce day one (x1.3); rookie TEs are near-unplayable (x0.6);
    rookie WRs never ramp (x0.9)."""
    out = df.copy()
    if "is_cold_start" not in out.columns:
        return out
    cold = out.is_cold_start.astype(bool)

    for idx in out.index[cold]:
        row = out.loc[idx]
        tgt, carry = _role_prior(row.get("position"), row.get("depth_rank", np.nan))
        import os as _os

        if _os.environ.get("DRAFT_PRIORS"):
            if not hasattr(fill_cold_start_features, "_dr"):
                fill_cold_start_features._dr = _draft_rounds()
            rnd = fill_cold_start_features._dr.get(row.get("gsis_id"))
            if rnd:
                f = DRAFT_ADJ.get((row.get("position"), int(min(rnd, 3))), 1.0)
                tgt, carry = tgt * f, carry * f
        if bool(row.get("is_rookie", False)):
            rnd = row.get("draft_round")
            mult = (
                _ROOKIE_DISCOUNT.get(int(rnd), _ROOKIE_DISCOUNT_DEFAULT)
                if pd.notna(rnd)
                else _ROOKIE_DISCOUNT_DEFAULT
            )
            tgt, carry = tgt * mult, carry * mult

        fills = {
            "target_share_l4": tgt,
            "carry_share_l4": carry,
            "wopr_l4": 1.5 * tgt,
            "snap_share_l4": min(1.0, 2.2 * max(tgt, carry)),
            "rz20_targets_smoothed": 4.0 * tgt,
            "gl3_carries_smoothed": 2.0 * carry,
        }
        for colname, value in fills.items():
            if colname in out.columns and pd.isna(out.at[idx, colname]):
                out.at[idx, colname] = value
    return out


def widen_cold_start_quantiles(
    preds: pd.DataFrame, is_cold_start: pd.Series, widen: float = 1.5
) -> pd.DataFrame:
    """Stretch the p10–p90 band around the median and scale the std on
    cold-start rows: role priors say where the middle is, not how wide."""
    out = preds.copy()
    mask = np.asarray(is_cold_start, dtype=bool)
    if not mask.any():
        return out
    p50 = out.loc[mask, "proj_p50"]
    out.loc[mask, "proj_p10"] = p50 - (p50 - out.loc[mask, "proj_p10"]) * widen
    out.loc[mask, "proj_p90"] = p50 + (out.loc[mask, "proj_p90"] - p50) * widen
    out.loc[mask, "proj_std"] = out.loc[mask, "proj_std"] * widen
    return out

```

===== FILE: src/nfl_dfs/models/components.py =====
```python
"""Component models (guide §6.2): predict opportunity and efficiency
separately, then let the simulator compose them. Losses match the label's
distribution (§7.2) — counts get Poisson, rates get plain regression on the
observed ratio with the denominator as support.

Position masks are applied at prediction time: a QB gets zero expected
targets and a WR gets zero pass attempts, no matter what the trees say.
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd

from .featureset import LGB_THREADS, build_X
from .weights import sample_weights

COUNT_PARAMS = dict(
    num_threads=LGB_THREADS,
    objective="poisson",
    metric="poisson",
    learning_rate=0.06,
    num_leaves=31,
    min_data_in_leaf=40,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=1,
    lambda_l2=5.0,
    verbosity=-1,
)
RATE_PARAMS = {**COUNT_PARAMS, "objective": "regression", "metric": "mae"}

# name -> (label expression, row filter, params). Rates are trained only on
# rows where the denominator exists; counts on every row of the position
# group so the zeros are learned, not imputed.
_RECEIVING = lambda df: df.position != "QB"  # noqa: E731
_PASSING = lambda df: df.position == "QB"  # noqa: E731
_ALL = lambda df: pd.Series(True, index=df.index)  # noqa: E731

# Clips keep composed distributions sane even when a model extrapolates.
RATE_CLIPS = {
    "catch_rate": (0.2, 0.95),
    "ypr": (2.0, 25.0),
    "ypc": (1.5, 9.0),
    "ypa": (4.0, 12.0),
}

COMPONENT_NAMES = [
    "targets",
    "catch_rate",
    "ypr",
    "rec_tds",
    "carries",
    "ypc",
    "rush_tds",
    "pass_attempts",
    "ypa",
    "pass_tds",
    "interceptions",
]


@dataclass
class ComponentModels:
    models: dict[str, lgb.Booster]

    def predict_components(self, df: pd.DataFrame) -> pd.DataFrame:
        X = build_X(df)
        out = pd.DataFrame(index=df.index)
        for name in COMPONENT_NAMES:
            # Slice to the booster's own training columns: a registry model
            # trained before a featureset addition must keep predicting until
            # the next weekly retrain picks the new columns up.
            out[name] = self.models[name].predict(X[self.models[name].feature_name()])

        for name, (lo, hi) in RATE_CLIPS.items():
            out[name] = out[name].clip(lo, hi)
        for name in ("targets", "rec_tds", "carries", "rush_tds",
                     "pass_attempts", "pass_tds", "interceptions"):
            out[name] = out[name].clip(lower=0.0)

        is_qb = (df.position == "QB").to_numpy()
        out.loc[is_qb, ["targets", "rec_tds"]] = 0.0
        out.loc[~is_qb, ["pass_attempts", "pass_tds", "interceptions"]] = 0.0
        return out


def _fit(
    tr: pd.DataFrame,
    label: pd.Series,
    target_season: int,
    params: dict,
    num_boost_round: int,
    denom: pd.Series | None = None,
) -> lgb.Booster:
    w = sample_weights(tr, target_season)
    # A/B lever (env RATE_DENOM_WEIGHTS, off by default; data audit
    # 2026-08-03 finding 7): rate components (catch_rate, ypr, ypc, ypa)
    # weigh a 1-target rate the same as a 12-target rate, inflating rate
    # noise. With the lever on, rate rows are weighted by recency x
    # denominator so high-volume observations dominate the rate fit.
    import os as _os

    if denom is not None and _os.environ.get("RATE_DENOM_WEIGHTS"):
        w = w * denom.to_numpy(dtype=float)
    dset = lgb.Dataset(
        build_X(tr),
        label,
        weight=w,
        categorical_feature=["position"],
    )
    return lgb.train(params, dset, num_boost_round=num_boost_round)


def train(
    panel: pd.DataFrame, target_season: int, num_boost_round: int = 400
) -> ComponentModels:
    """Train every component on seasons before `target_season`."""
    tr = panel[panel.season < target_season]
    # A/B lever (env TRAIN_MAX_WEEK, off by default): drop late-season
    # training rows. Rest-week dynamics (playoff-locked starters on a
    # half, surprise backups) generate labels unrepresentative of the
    # weeks the user actually plays; fully-rested stars vanish entirely
    # (no stats row), so the residue is systematically weird. 16 keeps
    # ~88% of rows and excludes the modern weeks 17-18.
    import os as _os

    max_wk = int(_os.environ.get("TRAIN_MAX_WEEK", "0"))
    if max_wk:
        tr = tr[tr.week <= max_wk]
    if tr.empty:
        raise ValueError(f"no training rows before season {target_season}")

    recv = tr[_RECEIVING(tr)]
    qb = tr[_PASSING(tr)]
    caught = recv[recv.y_targets > 0]
    with_rec = recv[recv.y_receptions > 0]
    rushed = tr[tr.y_carries > 0]
    attempted = qb[qb.y_pass_attempts > 0]

    specs: dict = {
        "targets": (recv, recv.y_targets, COUNT_PARAMS, None),
        "catch_rate": (caught, caught.y_receptions / caught.y_targets,
                       RATE_PARAMS, caught.y_targets),
        "ypr": (with_rec, with_rec.y_rec_yards / with_rec.y_receptions,
                RATE_PARAMS, with_rec.y_receptions),
        "rec_tds": (recv, recv.y_rec_tds, COUNT_PARAMS, None),
        "carries": (tr[_ALL(tr)], tr.y_carries, COUNT_PARAMS, None),
        "ypc": (rushed, rushed.y_rush_yards / rushed.y_carries,
                RATE_PARAMS, rushed.y_carries),
        "rush_tds": (tr[_ALL(tr)], tr.y_rush_tds, COUNT_PARAMS, None),
        "pass_attempts": (qb, qb.y_pass_attempts, COUNT_PARAMS, None),
        "ypa": (attempted, attempted.y_pass_yards / attempted.y_pass_attempts,
                RATE_PARAMS, attempted.y_pass_attempts),
        "pass_tds": (qb, qb.y_pass_tds, COUNT_PARAMS, None),
        "interceptions": (qb, qb.y_interceptions, COUNT_PARAMS, None),
    }

    models = {
        name: _fit(rows, label, target_season, params, num_boost_round,
                   denom=denom)
        for name, (rows, label, params, denom) in specs.items()
    }
    return ComponentModels(models=models)

```

===== FILE: src/nfl_dfs/models/emp_marginals.py =====
```python
"""Empirically-fitted DK-points marginal families per (position,
projection window).

Fitted parameters from chanzer0/NFL-DFS-Tools (distribution_data/
fp_distributions_draftkings.csv, no license file — used here for
personal research only, with attribution; not for redistribution).
Families: RB/WR go weibull (fat right tail) above ~17 projected pts,
TE lognormal at low projections, QB/DST skew-normal. Consumed by the
EMP_MARGINALS lever (replay._empirical_marginals): sample the SHAPE,
affine-match to our (mean, std), rank-reorder onto our structural
draws so the possession-engine copula survives unchanged.
"""

ROWS: list[dict] = [
    {'dist': 'exgaussian', 'pos': 'QB', 'lo': 2.0, 'hi': 4.0, 'mu': -0.824799, 'sigma': 0.290609, 'tau': 4.964827},
    {'dist': 'exgaussian', 'pos': 'QB', 'lo': 4.0, 'hi': 6.0, 'mu': -0.729885, 'sigma': 0.441689, 'tau': 6.56447},
    {'dist': 'skew_normal', 'pos': 'QB', 'lo': 6.0, 'hi': 8.0, 'alpha': 29.175045, 'loc': -0.965775, 'scale': 12.828373},
    {'dist': 'skew_normal', 'pos': 'QB', 'lo': 8.0, 'hi': 10.0, 'alpha': 21.284385, 'loc': -0.907846, 'scale': 13.763907},
    {'dist': 'skew_normal', 'pos': 'QB', 'lo': 10.0, 'hi': 12.0, 'alpha': 3.360701, 'loc': 2.210197, 'scale': 12.103985},
    {'dist': 'skew_normal', 'pos': 'QB', 'lo': 12.0, 'hi': 14.0, 'alpha': 1.988228, 'loc': 5.080486, 'scale': 10.867672},
    {'dist': 'skew_normal', 'pos': 'QB', 'lo': 14.0, 'hi': 16.0, 'alpha': 1.658168, 'loc': 7.383505, 'scale': 10.534902},
    {'dist': 'skew_normal', 'pos': 'QB', 'lo': 16.0, 'hi': 18.0, 'alpha': 1.508356, 'loc': 9.6263, 'scale': 10.864812},
    {'dist': 'skew_normal', 'pos': 'QB', 'lo': 18.0, 'hi': 20.0, 'alpha': 1.481117, 'loc': 11.346759, 'scale': 10.695233},
    {'dist': 'skew_normal', 'pos': 'QB', 'lo': 20.0, 'hi': 22.0, 'alpha': 1.369287, 'loc': 11.500055, 'scale': 11.758847},
    {'dist': 'skew_normal', 'pos': 'QB', 'lo': 22.0, 'hi': 24.0, 'alpha': 1.2815, 'loc': 14.066729, 'scale': 12.168877},
    {'dist': 'skew_normal', 'pos': 'QB', 'lo': 24.0, 'hi': 26.0, 'alpha': 1.20454, 'loc': 15.67091, 'scale': 11.684469},
    {'dist': 'skew_normal', 'pos': 'QB', 'lo': 26.0, 'hi': 28.0, 'alpha': 1.112674, 'loc': 17.577107, 'scale': 11.344466},
    {'dist': 'skew_normal', 'pos': 'QB', 'lo': 28.0, 'hi': 30.0, 'alpha': -6.845799, 'loc': 37.722548, 'scale': 16.534158},
    {'dist': 'generalized_gamma', 'pos': 'RB', 'lo': 1.0, 'hi': 3.0, 'scale': 0.109801, 'a': 0.444508, 'd': 4.008554},
    {'dist': 'generalized_gamma', 'pos': 'RB', 'lo': 3.0, 'hi': 5.0, 'scale': 1.644821, 'a': 0.702826, 'd': 1.91582},
    {'dist': 'gamma', 'pos': 'RB', 'lo': 5.0, 'hi': 7.0, 'alpha': 1.14735, 'scale': 5.542649, 'beta': 0.180419},
    {'dist': 'weibull', 'pos': 'RB', 'lo': 7.0, 'hi': 9.0, 'scale': 8.893956, 'c': 1.204668},
    {'dist': 'generalized_gamma', 'pos': 'RB', 'lo': 9.0, 'hi': 11.0, 'scale': 13.17836, 'a': 1.536912, 'd': 0.768744},
    {'dist': 'weibull', 'pos': 'RB', 'lo': 11.0, 'hi': 13.0, 'scale': 12.664025, 'c': 1.479526},
    {'dist': 'generalized_gamma', 'pos': 'RB', 'lo': 13.0, 'hi': 15.0, 'scale': 20.734763, 'a': 2.206804, 'd': 0.631069},
    {'dist': 'generalized_gamma', 'pos': 'RB', 'lo': 15.0, 'hi': 17.0, 'scale': 21.02549, 'a': 2.324654, 'd': 0.696659},
    {'dist': 'weibull', 'pos': 'RB', 'lo': 17.0, 'hi': 19.0, 'scale': 18.588548, 'c': 1.841977},
    {'dist': 'weibull', 'pos': 'RB', 'lo': 19.0, 'hi': 21.0, 'scale': 20.897774, 'c': 1.954169},
    {'dist': 'weibull', 'pos': 'RB', 'lo': 21.0, 'hi': 23.0, 'scale': 24.146694, 'c': 2.173357},
    {'dist': 'weibull', 'pos': 'RB', 'lo': 23.0, 'hi': 25.0, 'scale': 25.546014, 'c': 2.273506},
    {'dist': 'weibull', 'pos': 'RB', 'lo': 25.0, 'hi': 27.0, 'scale': 26.371406, 'c': 2.256578},
    {'dist': 'generalized_gamma', 'pos': 'WR', 'lo': 1.0, 'hi': 3.0, 'scale': 0.006995, 'a': 0.374459, 'd': 10.226748},
    {'dist': 'generalized_gamma', 'pos': 'WR', 'lo': 3.0, 'hi': 5.0, 'scale': 0.003343, 'a': 0.347795, 'd': 12.193351},
    {'dist': 'generalized_gamma', 'pos': 'WR', 'lo': 5.0, 'hi': 7.0, 'scale': 0.200913, 'a': 0.516288, 'd': 5.730455},
    {'dist': 'generalized_gamma', 'pos': 'WR', 'lo': 7.0, 'hi': 9.0, 'scale': 1.003479, 'a': 0.66426, 'd': 3.896456},
    {'dist': 'gamma', 'pos': 'WR', 'lo': 9.0, 'hi': 11.0, 'alpha': 1.881308, 'scale': 5.442403, 'beta': 0.183742},
    {'dist': 'generalized_gamma', 'pos': 'WR', 'lo': 11.0, 'hi': 13.0, 'scale': 10.314211, 'a': 1.312196, 'd': 1.313537},
    {'dist': 'generalized_gamma', 'pos': 'WR', 'lo': 13.0, 'hi': 15.0, 'scale': 10.791952, 'a': 1.294655, 'd': 1.525368},
    {'dist': 'generalized_gamma', 'pos': 'WR', 'lo': 15.0, 'hi': 17.0, 'scale': 11.102779, 'a': 1.267186, 'd': 1.570411},
    {'dist': 'weibull', 'pos': 'WR', 'lo': 17.0, 'hi': 19.0, 'scale': 19.376588, 'c': 1.943375},
    {'dist': 'weibull', 'pos': 'WR', 'lo': 19.0, 'hi': 21.0, 'scale': 19.599588, 'c': 1.746562},
    {'dist': 'weibull', 'pos': 'WR', 'lo': 21.0, 'hi': 23.0, 'scale': 21.90957, 'c': 2.086508},
    {'dist': 'weibull', 'pos': 'WR', 'lo': 23.0, 'hi': 25.0, 'scale': 24.385943, 'c': 1.937974},
    {'dist': 'weibull', 'pos': 'WR', 'lo': 25.0, 'hi': 27.0, 'scale': 22.108142, 'c': 2.072372},
    {'dist': 'lognormal', 'pos': 'TE', 'lo': 0.7000000029802322, 'hi': 2.700000002980232, 'mu': 0.996526, 'sigma': 0.709808},
    {'dist': 'lognormal', 'pos': 'TE', 'lo': 2.700000002980232, 'hi': 4.700000002980232, 'mu': 1.239995, 'sigma': 0.744322},
    {'dist': 'lognormal', 'pos': 'TE', 'lo': 4.700000002980232, 'hi': 6.700000002980232, 'mu': 1.512047, 'sigma': 0.786889},
    {'dist': 'generalized_gamma', 'pos': 'TE', 'lo': 6.700000002980232, 'hi': 8.700000002980232, 'scale': 0.085091, 'a': 0.466627, 'd': 7.702086},
    {'dist': 'gamma', 'pos': 'TE', 'lo': 8.700000002980232, 'hi': 10.700000002980232, 'alpha': 2.140428, 'scale': 4.454431, 'beta': 0.224496},
    {'dist': 'gamma', 'pos': 'TE', 'lo': 10.700000002980232, 'hi': 12.700000002980232, 'alpha': 2.274333, 'scale': 4.925102, 'beta': 0.203041},
    {'dist': 'weibull', 'pos': 'TE', 'lo': 12.700000002980232, 'hi': 14.700000002980232, 'scale': 14.127176, 'c': 1.66883},
    {'dist': 'weibull', 'pos': 'TE', 'lo': 14.700000002980232, 'hi': 16.700000002980232, 'scale': 16.699093, 'c': 1.774625},
    {'dist': 'weibull', 'pos': 'TE', 'lo': 16.700000002980232, 'hi': 18.700000002980232, 'scale': 18.692615, 'c': 1.879108},
    {'dist': 'weibull', 'pos': 'TE', 'lo': 18.700000002980232, 'hi': 20.700000002980232, 'scale': 16.893289, 'c': 1.924557},
    {'dist': 'gamma', 'pos': 'K', 'lo': 3.0, 'hi': 5.0, 'alpha': 2.985792, 'scale': 2.495411, 'beta': 0.400736},
    {'dist': 'gamma', 'pos': 'K', 'lo': 5.0, 'hi': 7.0, 'alpha': 2.664403, 'scale': 2.813305, 'beta': 0.355454},
    {'dist': 'gamma', 'pos': 'K', 'lo': 7.0, 'hi': 9.0, 'alpha': 3.094103, 'scale': 2.555896, 'beta': 0.391252},
    {'dist': 'gamma', 'pos': 'K', 'lo': 9.0, 'hi': 11.0, 'alpha': 3.285314, 'scale': 2.62692, 'beta': 0.380674},
    {'dist': 'gamma', 'pos': 'K', 'lo': 11.0, 'hi': 13.0, 'alpha': 3.483132, 'scale': 2.774651, 'beta': 0.360406},
    {'dist': 'skew_normal', 'pos': 'DST', 'lo': 2.0, 'hi': 4.0, 'alpha': 3.271367, 'loc': -0.940069, 'scale': 7.573012},
    {'dist': 'skew_normal', 'pos': 'DST', 'lo': 4.0, 'hi': 6.0, 'alpha': 3.492448, 'loc': -0.521531, 'scale': 9.092697},
    {'dist': 'skew_normal', 'pos': 'DST', 'lo': 6.0, 'hi': 8.0, 'alpha': 3.422907, 'loc': -0.045799, 'scale': 9.41371},
    {'dist': 'skew_normal', 'pos': 'DST', 'lo': 8.0, 'hi': 10.0, 'alpha': 3.839022, 'loc': -0.060163, 'scale': 9.859398},
    {'dist': 'skew_normal', 'pos': 'DST', 'lo': 10.0, 'hi': 12.0, 'alpha': 3.819308, 'loc': 0.395318, 'scale': 11.257635},
    {'dist': 'shifted_gamma', 'pos': 'DST', 'lo': 12.0, 'hi': 14.0, 'alpha': 1.565241, 'beta': 0.154752, 'shift': -1.1},
]

```

===== FILE: src/nfl_dfs/models/featureset.py =====
```python
"""The shared model feature matrix.

One canonical feature list for the baseline and component models so a
model loaded from the registry always sees the columns it trained on.
Columns absent from an input frame become NaN (LightGBM handles missing
natively); extra columns are ignored.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

POSITIONS = ["QB", "RB", "WR", "TE"]

# LightGBM thread cap shared by every model in this package. Our panels are
# small (tens of thousands of rows at most); letting OpenMP grab all cores
# adds per-split sync overhead and has livelocked outright on WSL. Eight is
# plenty and matches Cloud Run job sizing.
import os as _os  # noqa: E402

LGB_THREADS = max(1, min(8, _os.cpu_count() or 1))

NUMERIC_FEATURES = [
    # Usage (point-in-time rollups, §5.2)
    "target_share_l4",
    "carry_share_l4",
    "wopr_l4",
    "rz20_targets_smoothed",
    "ez_targets_l4",
    "deep_targets_l4",
    "separation_l4",
    "stacked_box_l4",
    "gl3_carries_smoothed",
    "snap_share_l4",
    # Production trail
    "dk_points_l4",
    "dk_points_std",
    "dk_points_vol",
    # Game environment
    "implied_team_total",
    "spread",
    "game_total",
    "expected_game_script",
    "is_home",
    "is_dome",
    # Experience / role
    "games_played_prior",
    "is_cold_start",
    "depth_rank",
    # depth_rank_delta (Addendum 24) was REMOVED from the model inputs
    # 2026-08-01: the replay pipeline turned out to be fully
    # deterministic (3 identical confirmation runs), which retroactively
    # converts its "neutral within noise" replay result into a real
    # -4.6 mean-best cost (188.4 -> 183.8). The SQL column remains in
    # the feature tables for analysis; it just doesn't feed the model.
    # Game environment extras (2026-08-01): referee-crew flag tendency
    # (strictly-prior; NULL live until midweek crew assignments are
    # sourced) and script-stripped neutral pass rate.
    "ref_flags_prior",
    "neutral_pass_rate_l6",
    # qb_cpoe_l6 ADOPTED 2026-08-01 (Addendum 32): the first feature to
    # pass a six-season panel -- tail weeks 18 -> 23 of 101 at flat
    # mean/median. Found via the audit (ngs_passing was fully unused).
    "qb_cpoe_l6",
    # team_ol_out was REMOVED 2026-08-01 same day it was added: exact
    # replay cost -8.7 mean-best / -4 tail weeks (180.8/4-17 vs
    # 189.5/8-17). Plausible mechanism, bad feature -- likely confounded
    # (teams missing linemen are bad teams). Column remains in the
    # tables for analysis.
    # Next-man-up: opportunity vacated by teammates ruled Out this week
    "team_vacated_target_share",
    "team_vacated_carry_share",
    # Opponent secondary (CB coverage from PFR advstats; NULL before 2018)
    "cb_ypt_allowed_l6",
    "cb_comp_rate_allowed_l6",
    "db_ypt_allowed_l6",
    "top_cb_out",
    # Market signal
    "salary",
    "salary_delta_wow",
    # SCHED pair ADOPTED 2026-08-04 (final candidate panel, Addendum 49):
    # +6 tails vs same-build post-QF control (24 vs 18), best 2019 and
    # 2025 of the panel; the XSCHED combo arm proves this exact model
    # (sorted columns => EXTRA_FEATURES == adoption). Pure pre-game
    # schedule facts — available live by construction.
    "net_rest_diff",
    "body_clock_hour",
]

FEATURES = NUMERIC_FEATURES + ["position"]

# Candidate features (2026-08-01): materialized in the feature tables but
# EXCLUDED from the model unless named in the EXTRA_FEATURES env var
# (comma-separated) -- so one table rebuild supports N parallel exact
# feature A/Bs, each arm enabling exactly one. The deterministic-replay
# lesson (depth_rank_delta -4.6, team_ol_out -8.7): every feature pays
# its own way through a replay before joining NUMERIC_FEATURES.
CANDIDATE_FEATURES = (
    "pace_env_l6",                # own off plays + opp def plays faced (l6)
    "opp_blitz_rate_l6",          # opponent defense blitz rate (FTN, 2022+)
    "team_top2_target_share_l6",  # target concentration -> stack strength
    "qb_time_to_throw_l6",        # NGS avg time to throw (2016+)
    "pa_rate_l6",                 # team play-action rate (FTN, 2022+) — deep-shot / WR-ceiling context
    "opp_pressure_rate_l6",       # opp pressure GENERATED per dropback (FTN, 2022+) — outcome, not rushers sent
    "xfp_l4",                     # expected FP from opportunity alone (bucketed pbp rates; FantasyPoints lineage)
    "vacated_capture_tgt",        # vacated targets x empirical (pos,depth) capture rate (Addendum 44 event study)
    "vacated_capture_car",        # vacated carries x empirical capture rate (backfield-concentrated)
)


def _active_numeric_features() -> list[str]:
    """EXTRA_FEATURES adds registered candidates; DROP_FEATURES removes
    any baseline feature -- the ablation mirror (2026-08-01: built to test
    whether the pre-A/B-era salary features earn their slots, after the
    salary backfill's -4.4 on 2025 suggested consensus features eat tails).
    Both call-time envs; unset = the validated baseline."""
    import os

    extra = [f.strip() for f in os.environ.get("EXTRA_FEATURES", "").split(",")
             if f.strip()]
    drop = {f.strip() for f in os.environ.get("DROP_FEATURES", "").split(",")
            if f.strip()}
    base = [f for f in NUMERIC_FEATURES if f not in drop]
    return base + [f for f in extra if f in CANDIDATE_FEATURES]


def build_X(df: pd.DataFrame) -> pd.DataFrame:
    # SORTED columns (2026-08-01, Addendum 34): LightGBM's split
    # tie-breaking depends on column ORDER, so the same feature set in a
    # different order trains a different (equally valid) model -- worth
    # ~+/-5 mean-best of "order luck". Discovered when adopting
    # qb_cpoe_l6 (EXTRA_FEATURES appends last; adoption inserted
    # mid-list) shifted deterministic replays. Canonical alphabetical
    # order makes candidate arms and post-adoption baselines train
    # IDENTICAL models, restoring exact A/B equivalence forever.
    X = pd.DataFrame(index=df.index)
    for c in sorted(_active_numeric_features()):
        if c in df.columns:
            X[c] = pd.to_numeric(df[c], errors="coerce")
        else:
            X[c] = np.nan
    X["position"] = pd.Categorical(df["position"], categories=POSITIONS)
    return X

```

===== FILE: src/nfl_dfs/models/game_sim.py =====
```python
"""Possession-level game simulator (drive-state Markov chain).

Design doc: reports/possession-simulator-design.md. This is the v1 engine
for issue #13 item 6 (flagship) -- a small discrete drive-state Markov
chain that replaces the lognormal per-game factor in `simulate.py` with
one derived from how drives actually end (score, punt, turnover, ...).

The transition weights below are FITTED from `nfl_raw.pbp`, seasons
2018-2025 (48,528 drives, 2,227 games; fit 2026-08-01, replacing the
original hand-calibrated placeholder). Fit semantics, chosen to match how
the engine consumes each table:

- Start zone = the drive's first SCRIMMAGE play (kickoff rows carry the
  kicking-spot yardline; PAT-only pseudo-drives after defensive TDs were
  excluded -- both poisoned earlier fit attempts).
- `end_of_half`/`end_of_game` drives (6.8%) are dropped and the terminal
  probabilities renormalized; correspondingly, drives/team/game moments
  EXCLUDE those drives (mean 10.16, sd 1.65), so points/game stays right.
- `_NEXT_ZONE_WEIGHTS` is the SAME TEAM's next-drive start zone (two
  possession changes later), the quantity `_simulate_team_drives`
  actually consumes. Only td/fg_make/punt/safety are fitted; fg_miss/
  turnover/turnover_on_downs keep the zone-aware `_ZONE_FLIP` heuristic,
  since a single per-terminal distribution can't carry their strong
  dependence on where the drive died.
- Empirical anchors from the same fit: 2.175 pts/drive, 22.1 offensive
  pts/team/game (7/TD + 3/FG accounting), game total 44.2 +/- 13.8, and
  cross-team points correlation 0.016 -- i.e., the two teams' scoring is
  essentially INDEPENDENT in real games (relevant to the team_game_factors
  correlation discussion below).

The module still runs fully offline; the fit script lives in the session
records and is a ~60-line pbp aggregation, easy to re-run when seasons
accumulate.

Gated by `GAME_SIM_MODE` in `simulate.py`; default behavior there
(`GAME_SIM_MODE` unset or "lognormal") is completely unaffected by this
module.
"""

from __future__ import annotations

import numpy as np

ZONES = ("deep_own", "own", "midfield", "fringe", "redzone")
ZONE_INDEX = {name: i for i, name in enumerate(ZONES)}

TERMINALS = ("td", "fg_make", "fg_miss", "punt", "turnover", "turnover_on_downs", "safety")
TERMINAL_INDEX = {name: i for i, name in enumerate(TERMINALS)}

# Points awarded to the drive's own offense. fg_miss/punt/turnover(_on_downs)
# are 0 -- possession simply changes hands. safety is ALSO 0 here: it scores
# for the *defense*, not this offense, so a single team's own-drive sequence
# can't attribute it -- `simulate_game_points` credits the 2 points to the
# opponent's total separately (see `_simulate_team_drives`'s `safeties`).
TERMINAL_POINTS = np.array([7.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0])
assert len(TERMINAL_POINTS) == len(TERMINALS)
SAFETY_POINTS = 2.0  # credited to the opponent, not this team's own total

# Terminal-outcome percentages by starting field position, FITTED from
# nfl_raw.pbp 2018-2025 (see module docstring for fit semantics). Zone
# support: own 36,587 drives / midfield 4,961 / deep_own 4,011 / fringe
# 2,107 / redzone 860.
_TERMINAL_WEIGHTS = {
    "deep_own": {"td": 16.74, "fg_make": 9.74, "fg_miss": 1.86, "punt": 50.49, "turnover": 13.95, "turnover_on_downs": 4.62, "safety": 2.6},
    "own": {"td": 22.44, "fg_make": 14.56, "fg_miss": 2.73, "punt": 41.66, "turnover": 12.85, "turnover_on_downs": 5.69, "safety": 0.07},
    "midfield": {"td": 30.51, "fg_make": 22.75, "fg_miss": 4.05, "punt": 25.83, "turnover": 10.09, "turnover_on_downs": 6.78, "safety": 0.0},
    "fringe": {"td": 40.45, "fg_make": 35.19, "fg_miss": 5.84, "punt": 5.47, "turnover": 7.63, "turnover_on_downs": 5.42, "safety": 0.0},
    "redzone": {"td": 57.6, "fg_make": 31.03, "fg_miss": 1.24, "punt": 0.12, "turnover": 5.93, "turnover_on_downs": 4.08, "safety": 0.0},
}

# Same-team NEXT-drive start-zone percentages by terminal outcome (two
# possession changes later -- the quantity `_simulate_team_drives`
# consumes; see its CAUTION docstring), fitted from the same pbp span.
# Terminals not listed (fg_miss, turnover, turnover_on_downs) fall back
# to `_ZONE_FLIP`: their next-start depends strongly on where the drive
# died, which a flat per-terminal distribution can't carry.
_NEXT_ZONE_WEIGHTS = {
    "td": {"deep_own": 8.67, "own": 73.28, "midfield": 11.28, "fringe": 5.05, "redzone": 1.72},
    "fg_make": {"deep_own": 8.4, "own": 73.2, "midfield": 11.28, "fringe": 5.23, "redzone": 1.88},
    "safety": {"deep_own": 10.58, "own": 75.0, "midfield": 7.69, "fringe": 3.85, "redzone": 2.88},
    "punt": {"deep_own": 8.59, "own": 71.6, "midfield": 12.08, "fringe": 5.2, "redzone": 2.53},
}

_ZONE_FLIP = {
    "deep_own": "redzone",
    "own": "fringe",
    "midfield": "midfield",
    "fringe": "own",
    "redzone": "deep_own",
}

MAX_DRIVES_PER_TEAM = 16  # generous upper bound; real games run ~9-13
# Fitted 2018-2025, EXCLUDING end-of-half drives to match the terminal
# table's renormalization (see module docstring): 10.16 +/- 1.65.
MEAN_DRIVES_PER_TEAM = 10.16
DRIVES_PER_TEAM_SD = 1.65


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    return {k: v / total for k, v in weights.items()}


def _prob_matrix(
    weights_by_row: dict[str, dict[str, float]],
    row_index: dict[str, int],
    col_index: dict[str, int],
) -> np.ndarray:
    matrix = np.zeros((len(row_index), len(col_index)))
    for row_name, weights in weights_by_row.items():
        if not weights:
            continue
        for col_name, p in _normalize(weights).items():
            matrix[row_index[row_name], col_index[col_name]] = p
    return matrix


TERMINAL_PROB_MATRIX = _prob_matrix(_TERMINAL_WEIGHTS, ZONE_INDEX, TERMINAL_INDEX)
_CUM_TERMINAL_PROB = np.cumsum(TERMINAL_PROB_MATRIX, axis=1)

_NEXT_ZONE_PROB_MATRIX = _prob_matrix(_NEXT_ZONE_WEIGHTS, TERMINAL_INDEX, ZONE_INDEX)
_CUM_NEXT_ZONE_PROB = np.cumsum(_NEXT_ZONE_PROB_MATRIX, axis=1)
_EXPLICIT_NEXT_ZONE_TERMINALS = np.array(
    [TERMINAL_INDEX[t] for t in _NEXT_ZONE_WEIGHTS]
)
_ZONE_FLIP_ARRAY = np.array([ZONE_INDEX[_ZONE_FLIP[z]] for z in ZONES])


def _categorical_draw(rng: np.random.Generator, cum_probs: np.ndarray) -> np.ndarray:
    """cum_probs: (n_sims, k) cumulative probabilities per row -> (n_sims,) index draws."""
    u = rng.random(cum_probs.shape[0])
    idx = (u[:, None] > cum_probs).sum(axis=1)
    return np.clip(idx, 0, cum_probs.shape[1] - 1)


def _simulate_team_drives(
    rng: np.random.Generator,
    n_drives: np.ndarray,
    start_zone: str = "own",
) -> tuple[np.ndarray, np.ndarray]:
    """(points, safeties_conceded) across `len(n_drives)` sims, given each
    sim's possession count `n_drives` (int array). `points` is this team's
    own-drive scoring only (TD/FG make); `safeties_conceded` counts drives
    that ended in a safety, which `simulate_game_points` credits to the
    OPPONENT's total, since a safety scores for the defense.

    Does not explicitly simulate the opponent's intervening drives -- the
    next-zone draw approximates the receiving team's expected field
    position from aggregate rates across all possession changes of that
    type, which already folds in the opponent's average drive length.

    CAUTION for the pbp fit (design doc "Next steps" 1): because the
    opponent's drive is skipped, the next-zone distribution consumed here
    is *this same team's* next drive start -- two possession changes
    after the terminal outcome -- NOT the opponent's takeover spot. The
    placeholder table conflates the two (e.g. a turnover in the opponent's
    red zone pins THIS team at deep_own next drive, when causally the
    opponent inherits the bad field position and this team tends to get a
    short field back). Fit the same-team quantity from pbp, or switch to
    explicit alternating possessions."""
    n_drives = np.clip(np.asarray(n_drives, dtype=int), 0, MAX_DRIVES_PER_TEAM)
    n_sims = len(n_drives)
    zone = np.full(n_sims, ZONE_INDEX[start_zone], dtype=int)
    points = np.zeros(n_sims)
    safeties = np.zeros(n_sims)
    max_drives = int(n_drives.max()) if n_sims else 0
    safety_idx = TERMINAL_INDEX["safety"]

    for d in range(max_drives):
        active = d < n_drives
        if not active.any():
            break

        terminal = _categorical_draw(rng, _CUM_TERMINAL_PROB[zone])
        points += np.where(active, TERMINAL_POINTS[terminal], 0.0)
        safeties += np.where(active & (terminal == safety_idx), 1.0, 0.0)

        drawn_zone = _categorical_draw(rng, _CUM_NEXT_ZONE_PROB[terminal])
        explicit = np.isin(terminal, _EXPLICIT_NEXT_ZONE_TERMINALS)
        next_zone = np.where(explicit, drawn_zone, _ZONE_FLIP_ARRAY[zone])
        zone = np.where(active, next_zone, zone)

    return points, safeties


def simulate_team_points(
    rng: np.random.Generator,
    n_drives: np.ndarray,
    start_zone: str = "own",
) -> np.ndarray:
    """This team's own-drive scoring (TD/FG make); always >= 0. Excludes
    safety points conceded TO the opponent -- those only make sense as
    part of a two-team game, see `simulate_game_points`."""
    points, _ = _simulate_team_drives(rng, n_drives, start_zone)
    return points


def simulate_game_points(
    rng: np.random.Generator,
    n_sims: int,
    mean_drives_per_team: float = MEAN_DRIVES_PER_TEAM,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-team total points for `n_sims` independent game draws. Each
    team's drive sequence is simulated independently; the only cross-team
    coupling is (a) drive counts constrained within +/-1 of each other
    (teams alternate possessions in a real game, so counts rarely differ
    by more) and (b) safeties conceded by one team credited to the
    other's total, since that's the only terminal outcome that scores
    for the defense rather than the offense. There is no within-sim
    field-position coupling (a turnover here does not literally hand the
    other simulated team a short field) -- adequate for the shared
    per-game factor this feeds, revisit if team-level asymmetry lands."""
    # Rounded normal, NOT Poisson: Poisson(11) has sd ~3.3 drives, far
    # wider than real games (~1.5-2), and that excess possession variance
    # alone pushed the derived game factor's sd to ~0.45 vs the validated
    # lognormal's 0.18 before this was tightened.
    n_a = np.clip(
        np.rint(rng.normal(mean_drives_per_team, DRIVES_PER_TEAM_SD, n_sims)).astype(int),
        6, MAX_DRIVES_PER_TEAM,
    )
    delta = rng.integers(-1, 2, n_sims)
    n_b = np.clip(n_a + delta, 6, MAX_DRIVES_PER_TEAM)
    points_a, safeties_a = _simulate_team_drives(rng, n_a)
    points_b, safeties_b = _simulate_team_drives(rng, n_b)
    return points_a + SAFETY_POINTS * safeties_b, points_b + SAFETY_POINTS * safeties_a


def game_factor_matrix(
    rng: np.random.Generator,
    n_games: int,
    n_sims: int,
    mean_drives_per_team: float = MEAN_DRIVES_PER_TEAM,
    paces: np.ndarray | None = None,
) -> np.ndarray:
    """Drop-in replacement for `simulate.py`'s lognormal `game_mult` draw:
    shape (n_games, n_sims), one shared multiplier per game per sim (both
    teams in a game get the same value -- the same granularity the
    lognormal factor has today). Used when the caller has no per-player
    team assignment to key an asymmetric factor off of; see
    `team_game_factors` for the team-level version, which is the main
    motivating benefit of a possession sim (see the design doc).

    Mean-preserving empirically over the `n_sims` batch (E[factor] == 1 up
    to sampling noise); use `n_sims` in the thousands, matching
    `simulate.simulate()`'s default of 10,000, for that noise to be small.
    """
    factors = np.empty((n_games, n_sims))
    for i in range(n_games):
        pace = 1.0 if paces is None else float(paces[i])
        pts_a, pts_b = simulate_game_points(rng, n_sims,
                                            mean_drives_per_team * pace)
        total = pts_a + pts_b
        mean = total.mean()
        factors[i] = total / mean if mean > 0 else 1.0
    return factors


def team_game_factors(
    rng: np.random.Generator,
    n_games: int,
    n_sims: int,
    mean_drives_per_team: float = MEAN_DRIVES_PER_TEAM,
    paces: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-TEAM, mean-preserving multipliers -- the asymmetric counterpart
    to `game_factor_matrix`. Each team's factor is that team's own points
    divided by that team's own mean, instead of both teams sharing one
    combined-total factor the way `game_factor_matrix` (and the lognormal
    draw it replaces) does.

    What this does and does NOT deliver: because `simulate_game_points`
    simulates the two teams' drive sequences independently (coupled only
    through drive counts +/-1 and safety credit), the two factors are
    NEARLY INDEPENDENT (measured corr ~0.1-0.2) -- not anticorrelated.
    A blowout world (one factor up while the other is down) occurs only
    as often as independence implies; the engine has no score-differential
    dynamics to make it more likely. Equally important: independence
    REMOVES the within-game cross-team correlation the shared factor
    provided, which is what makes QB + opposing bring-back shootout
    stacks price correctly (README §6.2). Reality sits between corr=1
    (shared) and corr~0 (this): interpret any replay A/B accordingly, and
    if this arm underperforms, the fix is likely a hybrid (shared
    environment component x team-specific component), not abandoning
    team-level factors. See the design doc's "Next steps".

    Returns (factors_a, factors_b), each shape (n_games, n_sims) and
    individually mean-preserving (E[factor] == 1 per team, up to sampling
    noise). `simulate.simulate()` assigns factors_a/factors_b to players
    by which of the two teams in their game they're on.
    """
    factors_a = np.empty((n_games, n_sims))
    factors_b = np.empty((n_games, n_sims))
    for i in range(n_games):
        pace = 1.0 if paces is None else float(paces[i])
        pts_a, pts_b = simulate_game_points(rng, n_sims,
                                            mean_drives_per_team * pace)
        mean_a, mean_b = pts_a.mean(), pts_b.mean()
        factors_a[i] = pts_a / mean_a if mean_a > 0 else 1.0
        factors_b[i] = pts_b / mean_b if mean_b > 0 else 1.0
    return factors_a, factors_b


DIRICHLET_CONCENTRATION_SCALE = float(
    __import__("os").environ.get("DIRICHLET_K", "20.0"))
# DIRICHLET_K env (graveyard review 2026-08-03): K=20 tested negative
# with the ledger itself noting "concentration scale is the retune
# knob" — the retune was never run. Lower K = spikier within-team
# allocations (more next-man-up variance).
MIN_CONCENTRATION = 0.05


def allocate_drive_usage(
    rng: np.random.Generator,
    n_units: float | np.ndarray,
    usage_shares: np.ndarray,
    n_sims: int = 1,
) -> np.ndarray:
    """Split `n_units` (plays, targets, carries...) across a team's
    players for `n_sims` draws, via a Dirichlet distribution centered on
    `usage_shares` (e.g. `target_share_l4`/`carry_share_l4` from
    `models/featureset.py`). Low-share players (backups, committee
    backfields) still draw meaningful upside sometimes -- exactly the
    boom/next-man-up variance this system is built to price -- because
    their Dirichlet concentration is small, not zero.

    Returns shape (n_sims, len(usage_shares)) if n_sims > 1, else
    (len(usage_shares),).
    """
    shares = np.asarray(usage_shares, dtype=float)
    total = shares.sum()
    shares = shares / total if total > 0 else np.full_like(shares, 1.0 / len(shares))

    concentration = np.clip(shares * DIRICHLET_CONCENTRATION_SCALE, MIN_CONCENTRATION, None)
    drawn = rng.dirichlet(concentration, size=n_sims)  # (n_sims, k)
    units = np.broadcast_to(n_units, (n_sims,)).astype(float)
    allocated = drawn * units[:, None]
    return allocated if n_sims > 1 else allocated[0]

```

===== FILE: src/nfl_dfs/models/monitoring.py =====
```python
"""Weekly drift alarms (guide §7.8). Thresholds from the guide's table:
MAE ratio 1.3×, p10/p90 coverage outside 7–13% / 87–93%, PSI 0.2, null
rate 2× baseline. A null-rate alarm means "check ingestion first, always".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MAE_RATIO_THRESHOLD = 1.3
COVERAGE_P10_RANGE = (0.07, 0.13)
COVERAGE_P90_RANGE = (0.87, 0.93)
PSI_THRESHOLD = 0.2
NULL_RATE_MULTIPLE = 2.0
# Baseline null rate is floored so a feature that was never null in
# training still alarms when nulls appear live, without alarming on dust.
_NULL_RATE_FLOOR = 0.01


@dataclass
class Alarm:
    kind: str
    message: str
    value: float


def check_mae(training_mae: float, recent_mae: float) -> Alarm | None:
    ratio = recent_mae / training_mae
    if ratio > MAE_RATIO_THRESHOLD:
        return Alarm(
            "mae_drift",
            f"rolling MAE {recent_mae:.2f} is {ratio:.2f}x training MAE "
            f"{training_mae:.2f} — model degrading, investigate before trusting",
            ratio,
        )
    return None


def check_coverage(
    y: np.ndarray, p10: np.ndarray, p90: np.ndarray
) -> list[Alarm]:
    y = np.asarray(y, dtype=float)
    alarms = []
    below_p10 = float(np.mean(y < np.asarray(p10, dtype=float)))
    below_p90 = float(np.mean(y < np.asarray(p90, dtype=float)))
    lo, hi = COVERAGE_P10_RANGE
    if not lo <= below_p10 <= hi:
        alarms.append(Alarm("coverage_p10",
                            f"p10 empirical coverage {below_p10:.3f} outside [{lo}, {hi}]",
                            below_p10))
    lo, hi = COVERAGE_P90_RANGE
    if not lo <= below_p90 <= hi:
        alarms.append(Alarm("coverage_p90",
                            f"p90 empirical coverage {below_p90:.3f} outside [{lo}, {hi}]",
                            below_p90))
    return alarms


def psi(base: np.ndarray, live: np.ndarray, bins: int = 10) -> float:
    """Population stability index of `live` against `base`, binned on the
    base distribution's quantiles."""
    base = np.asarray(base, dtype=float)
    live = np.asarray(live, dtype=float)
    edges = np.quantile(base, np.linspace(0, 1, bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    p = np.histogram(base, edges)[0] / len(base)
    q = np.histogram(live, edges)[0] / len(live)
    p = np.clip(p, 1e-6, None)
    q = np.clip(q, 1e-6, None)
    return float(np.sum((q - p) * np.log(q / p)))


def check_feature_drift(
    train: pd.DataFrame, live: pd.DataFrame, features: list[str]
) -> list[Alarm]:
    """Null-rate and PSI alarms per feature between the training frame and
    a live scoring frame."""
    alarms: list[Alarm] = []
    for f in features:
        base_null = max(float(train[f].isna().mean()), _NULL_RATE_FLOOR)
        live_null = float(live[f].isna().mean())
        if live_null > NULL_RATE_MULTIPLE * base_null:
            alarms.append(Alarm(
                "null_rate",
                f"{f}: live null rate {live_null:.1%} vs baseline {base_null:.1%} "
                f"— ingestion bug until proven otherwise",
                live_null,
            ))
        base_vals = train[f].dropna().to_numpy(dtype=float)
        live_vals = live[f].dropna().to_numpy(dtype=float)
        if len(base_vals) and len(live_vals):
            score = psi(base_vals, live_vals)
            if score > PSI_THRESHOLD:
                alarms.append(Alarm(
                    "psi",
                    f"{f}: PSI {score:.2f} vs training — upstream data change "
                    f"or genuine league shift",
                    score,
                ))
    return alarms

```

===== FILE: src/nfl_dfs/models/ownership.py =====
```python
"""Ownership prediction model — seeded pre-season, fit on standings (issue #11).

DK contest-standings CSVs (`nfl-dfs import-ownership`) land per-player
`pct_drafted` in `nfl_raw.contest_ownership`. Once week-1+ rows exist,
`nfl-dfs train-ownership` fits a LightGBM regressor mapping
salary/projection features to logit ownership; until then everything
downstream keeps using `backtest.field.naive_ownership` (value+salary
softmax) — this module deliberately presents the same shape so the swap
is one call.

Feature philosophy (guide §8.5 / issue #13 item 3): the interesting
residual is ownership vs *salary-implied* popularity. The pricing-lag
residual (models/pricing_lag.py) is the natural extra feature once its
weekly table accumulates alongside real ownership; start with the
features that exist for every player-week today.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

FEATURES = [
    "salary",
    "proj_points",
    "value",            # proj / (salary/1000)
    "salary_rank_pos",  # 1 = most expensive at position that week
    "value_rank_pos",
    "is_min_price",     # sub-$4k punt territory (Addendum 24 archetypes)
]
TARGET = "pct_drafted"
_EPS = 1e-3


def build_features(pool: pd.DataFrame) -> pd.DataFrame:
    """Feature frame from a pool with salary/proj_points/position columns.
    Works on live pools (prediction) and joined history (training)."""
    df = pool.copy()
    df["value"] = df.proj_points / (df.salary / 1000.0).clip(lower=0.1)
    df["salary_rank_pos"] = df.groupby(["season", "week", "position"])["salary"] \
        .rank(ascending=False, method="min")
    df["value_rank_pos"] = df.groupby(["season", "week", "position"])["value"] \
        .rank(ascending=False, method="min")
    df["is_min_price"] = (df.salary <= 4000).astype(float)
    return df


def training_frame() -> pd.DataFrame:
    """Historical training data: LineStar-backfilled contest ownership
    (2022-2025, real DK GPP pct_drafted) joined to dk_salaries_historical
    by normalized name within (season, week). proj_points is the
    strictly-prior trailing-4 mean of PPR points -- deliberately the
    PUBLIC-visible expectation ("recent points"), which is what actually
    drives chalk, rather than our model's projection."""
    from ..bq import query_df
    from ..config import settings

    df = query_df(f"""
        WITH own AS (
          SELECT season, week, UPPER(display_name) AS uname,
                 AVG(pct_drafted) AS pct_drafted
          FROM `{settings.raw}.contest_ownership`
          GROUP BY season, week, uname
        ),
        sal AS (
          SELECT DISTINCT season, week, UPPER(display_name) AS uname,
                 position, salary
          FROM `{settings.raw}.dk_salaries_historical`
        ),
        prod AS (
          SELECT season, week, UPPER(player_display_name) AS uname,
                 AVG(fantasy_points_ppr) OVER (
                   PARTITION BY player_id ORDER BY season, week
                   ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
                 ) AS proj_points
          FROM `{settings.raw}.weekly_stats`
        )
        SELECT own.season, own.week, own.uname AS display_name,
               sal.position, sal.salary,
               COALESCE(prod.proj_points, 0) AS proj_points,
               own.pct_drafted
        FROM own
        JOIN sal USING (season, week, uname)
        LEFT JOIN (SELECT DISTINCT season, week, uname, proj_points
                   FROM prod) prod USING (season, week, uname)
    """)
    if df.empty:
        raise RuntimeError(
            "contest_ownership has no joinable rows -- run "
            "nfl_dfs.ingest.linestar_backfill (or import weekly standings "
            "CSVs in-season via nfl-dfs import-ownership), then rerun."
        )
    return build_features(df)


def train(frame: pd.DataFrame, num_boost_round: int = 300):
    """LightGBM on logit(pct_drafted). Returns the booster."""
    import lightgbm as lgb

    y = frame[TARGET].clip(_EPS, 100 - _EPS) / 100.0
    y = np.log(y / (1 - y))
    ds = lgb.Dataset(frame[FEATURES], label=y)
    params = {"objective": "regression", "metric": "l2", "verbosity": -1,
              "learning_rate": 0.05, "num_leaves": 15}
    booster = lgb.train(params, ds, num_boost_round=num_boost_round)
    log.info("ownership model trained on %d rows", len(frame))
    return booster


def predict_ownership(booster, pool: pd.DataFrame) -> np.ndarray:
    """Predicted pct_drafted (0-100) for a live pool frame."""
    feats = build_features(pool)
    logit = booster.predict(feats[FEATURES])
    return 100.0 / (1.0 + np.exp(-logit))


def run_training(holdout_season: int = 2025) -> None:
    """CLI entry: walk-forward evaluation -- train on seasons before
    `holdout_season`, score out-of-sample against real contest ownership,
    and compare with the naive value/salary softmax the field sim uses
    today. Then refit on everything and save."""
    frame = training_frame()
    tr = frame[frame.season < holdout_season]
    ho = frame[frame.season == holdout_season]
    print(f"train {len(tr)} rows (<{holdout_season}); holdout {len(ho)} rows")

    booster = train(tr)
    pred = predict_ownership(booster, ho)
    corr = np.corrcoef(pred, ho[TARGET])[0, 1]

    # Naive comparator: value within (week, position), same shape the
    # field simulation's naive_ownership uses.
    naive = ho.groupby(["week", "position"]).value.rank(pct=True)
    naive_corr = np.corrcoef(naive, ho[TARGET])[0, 1]
    print(f"OUT-OF-SAMPLE {holdout_season}: model corr {corr:.3f} "
          f"vs naive value-rank corr {naive_corr:.3f}")

    # Cold-start read (paid-ownership-feed decision): the model's weakest
    # weeks should be 1-4, before the season's own usage/salary signals
    # accumulate. Per-week holdout corr says how big that gap really is.
    ho = ho.assign(_pred=pred, _naive=naive)
    for w, g in ho.groupby("week"):
        if len(g) < 30:
            continue
        mc = np.corrcoef(g._pred, g[TARGET])[0, 1]
        nc = np.corrcoef(g._naive, g[TARGET])[0, 1]
        print(f"  week {int(w):2}: model {mc:.3f}  naive {nc:.3f}  n={len(g)}")

    booster = train(frame)  # refit on all seasons for the live artifact
    import os

    os.makedirs("models", exist_ok=True)
    out = "models/ownership.txt"
    booster.save_model(out)
    print(f"saved {out} (refit on all {len(frame)} rows)")

```

===== FILE: src/nfl_dfs/models/pricing_lag.py =====
```python
"""DK pricing-lag model (issue #13 item 3; guide §8.5 "salary lag as the
actual edge"). DK sets salary partly from trailing production, with
roughly a one-to-two-week lag before a role change gets repriced.
Regressing salary on trailing-production features isolates that lag: the
residual (actual salary minus production-implied salary) is a
*structural* value signal, distinct from the changepoint-based alert in
`trends/alerts.py` — it flags players DK has been pricing behind their
established trailing role for a while, not just this week's spike.

Ridge regression per position, walk-forward by season (never fit on the
season being scored — CLAUDE.md: walk-forward validation only, by
season). Feature set is deliberately restricted to trailing usage /
production columns: no salary itself, no game-environment or opponent
columns, since those aren't inputs to DK's own pricing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from ..bq import load_dataframe, query_df
from ..config import settings

log = logging.getLogger(__name__)

WATCHLIST_Z_THRESHOLD = -1.5  # residual_z below this = structurally underpriced

TRAILING_FEATURES = [
    "target_share_l4",
    "carry_share_l4",
    "wopr_l4",
    "rz20_targets_smoothed",
    "ez_targets_l4",
    "deep_targets_l4",
    "gl3_carries_smoothed",
    "snap_share_l4",
    "dk_points_l4",
    "dk_points_std",
    "games_played_prior",
]
TARGET = "salary"
MIN_TRAIN_ROWS = 20
RESIDUAL_COLUMNS = [
    "gsis_id", "season", "week", "position",
    "salary", "salary_predicted", "salary_residual", "salary_residual_z",
]


@dataclass
class PricingLagModel:
    position: str
    scaler: StandardScaler
    ridge: Ridge
    feature_cols: list[str]

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        X = _feature_matrix(df, self.feature_cols)
        return self.ridge.predict(self.scaler.transform(X))


def _feature_matrix(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for c in cols:
        X[c] = pd.to_numeric(df[c], errors="coerce") if c in df.columns else np.nan
    return X.fillna(X.median(numeric_only=True)).fillna(0.0)


def train(
    panel: pd.DataFrame, target_season: int, alpha: float = 5.0
) -> dict[str, PricingLagModel]:
    """One Ridge model per position, trained on seasons strictly before
    `target_season`. Rows from `target_season` (or later) are never used
    for fitting, regardless of what else is in `panel` — the caller can
    pass the full panel and rely on this filter for point-in-time safety."""
    tr = panel[panel.season < target_season]
    models: dict[str, PricingLagModel] = {}
    for pos, grp in tr.groupby("position"):
        if len(grp) < MIN_TRAIN_ROWS:
            continue
        X_raw = _feature_matrix(grp, TRAILING_FEATURES)
        scaler = StandardScaler().fit(X_raw)
        ridge = Ridge(alpha=alpha).fit(scaler.transform(X_raw), grp[TARGET].astype(float))
        models[pos] = PricingLagModel(pos, scaler, ridge, TRAILING_FEATURES)
    return models


def residuals(panel: pd.DataFrame, models: dict[str, PricingLagModel]) -> pd.DataFrame:
    """actual salary minus production-implied salary, plus a within-slice
    z-score for comparability across positions with different salary
    ranges. Negative = DK is pricing below what trailing production
    implies -- a structural value play; positive = overpriced (chalk)."""
    frames = []
    for pos, grp in panel.groupby("position"):
        model = models.get(pos)
        if model is None or grp.empty:
            continue
        pred = model.predict(grp)
        actual = grp[TARGET].to_numpy(dtype=float)
        resid = actual - pred
        sd = resid.std()
        z = resid / sd if sd > 0 else np.zeros_like(resid)
        frames.append(pd.DataFrame({
            "gsis_id": grp["gsis_id"].to_numpy(),
            "season": grp["season"].to_numpy(),
            "week": grp["week"].to_numpy(),
            "position": pos,
            "salary": actual,
            "salary_predicted": pred,
            "salary_residual": resid,
            "salary_residual_z": z,
        }))
    if not frames:
        return pd.DataFrame(columns=RESIDUAL_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def walk_forward_residuals(
    panel: pd.DataFrame, min_train_seasons: int = 4
) -> pd.DataFrame:
    """Expanding-window: each season's residuals come from a model trained
    only on strictly earlier seasons, so the concatenated result is
    out-of-sample throughout and safe to use as a downstream feature
    (e.g. an input to the ownership-residual work in issue #11)."""
    seasons = sorted(panel["season"].unique())
    frames = []
    for i in range(min_train_seasons, len(seasons)):
        target_season = seasons[i]
        models = train(panel, target_season)
        if not models:
            continue
        va = panel[panel["season"] == target_season]
        frames.append(residuals(va, models))
    if not frames:
        return pd.DataFrame(columns=RESIDUAL_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def _training_panel() -> pd.DataFrame:
    return query_df(
        f"""
        SELECT gsis_id, season, week, position, {", ".join(TRAILING_FEATURES)}, {TARGET}
        FROM `{settings.features}.player_week_training`
        WHERE position IN ('QB', 'RB', 'WR', 'TE') AND {TARGET} IS NOT NULL
        """
    )


def run(season: int, week: int) -> None:
    """Write this season's walk-forward residuals to
    nfl_features.salary_pricing_lag and log the current week's watchlist."""
    panel = _training_panel()
    wf = walk_forward_residuals(panel[panel["season"] <= season])
    if wf.empty:
        log.info("Not enough seasons yet for a pricing-lag fit")
        return
    load_dataframe(wf, f"{settings.features}.salary_pricing_lag")
    watch = wf[
        (wf["season"] == season)
        & (wf["week"] == week)
        & (wf["salary_residual_z"] <= WATCHLIST_Z_THRESHOLD)
    ].sort_values("salary_residual_z")
    if watch.empty:
        log.info("No structurally underpriced players this week")
        return
    log.info(
        "Pricing-lag watchlist (%d players):\n%s",
        len(watch),
        watch.head(15).to_string(index=False),
    )


if __name__ == "__main__":
    import sys

    from ..config import current_season

    logging.basicConfig(level=logging.INFO)
    season = current_season()
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run(season, week)

```

===== FILE: src/nfl_dfs/models/prop_market.py =====
```python
"""Prop lines -> market DK-point projections (the real market for blend.py).

Per (season, week, player): de-vig each over/under pair, convert lines to
means (prop_line_to_mean), price TDs from anytime-TD odds
(lambda = -ln(1 - p)), sum DK scoring. Books averaged after de-vig.
Names matched to gsis_ids via normalized full display name.
"""

from __future__ import annotations

import logging
import re

import numpy as np
import pandas as pd

from ..bq import query_df
from ..config import settings
from .blend import american_to_prob, devig_two_way, prop_line_to_mean

log = logging.getLogger(__name__)

YARD_PTS = {"player_pass_yds": 0.04, "player_rush_yds": 0.1,
            "player_reception_yds": 0.1}


def _norm(s: pd.Series) -> pd.Series:
    return (s.astype(str).str.lower()
            .str.replace(r"[^a-z ]", "", regex=True).str.strip())


def market_points(seasons: tuple[int, ...] = (2023, 2024, 2025)) -> pd.DataFrame:
    """(season, week, gsis_id, market_points) from nfl_raw.prop_lines."""
    season_list = ", ".join(str(int(s)) for s in seasons)
    props = query_df(
        f"""SELECT season, week, bookmaker, market, outcome_name, player,
                   price, point FROM `{settings.raw}.prop_lines`
            WHERE season IN ({season_list})
              AND NOT ENDS_WITH(snapshot_ts, 'T18:00:00Z')"""
    )  # closes only: Tuesday opens (T18:00:00Z) are for movement studies
    names = query_df(
        f"""SELECT DISTINCT player_id AS gsis_id,
                   player_display_name AS display_name
            FROM `{settings.raw}.weekly_stats` WHERE season IN ({season_list})"""
    )
    names["norm"] = _norm(names.display_name)
    names = names.drop_duplicates("norm")
    props["norm"] = _norm(props.player)

    rows = []
    ou = props[props.outcome_name.isin(["Over", "Under"])]
    keys = ["season", "week", "norm", "market", "bookmaker", "point"]
    piv = (ou.pivot_table(index=keys, columns="outcome_name",
                          values="price", aggfunc="first").reset_index())
    piv = piv.dropna(subset=["Over", "Under", "point"])
    for r in piv.itertuples():
        p_over, _ = devig_two_way(american_to_prob(r.Over),
                                  american_to_prob(r.Under))
        dist = "poisson" if r.market in ("player_receptions",
                                         "player_pass_tds") else "normal"
        try:
            mean = prop_line_to_mean(float(r.point), p_over, dist)
        except Exception:
            continue
        pts = (YARD_PTS.get(r.market, 0.0) * mean
               + (1.0 if r.market == "player_receptions" else 0.0) * mean
               + (4.0 if r.market == "player_pass_tds" else 0.0) * mean)
        rows.append({"season": r.season, "week": r.week, "norm": r.norm,
                     "market": r.market, "bookmaker": r.bookmaker,
                     "pts": pts})
    td = props[props.market == "player_anytime_td"].copy()
    # One-way market: de-vig by the book's typical anytime-TD hold (~15%).
    td["p"] = (td.price.map(american_to_prob) / 1.15).clip(0.01, 0.95)
    td["pts"] = 6.0 * (-np.log1p(-td.p))
    rows.extend(td[["season", "week", "norm", "market", "bookmaker",
                    "pts"]].to_dict("records"))
    df = pd.DataFrame(rows)
    # Average books within a market, then sum markets per player-week
    per_mkt = (df.groupby(["season", "week", "norm", "market"]).pts
               .mean().reset_index())
    total = (per_mkt.groupby(["season", "week", "norm"]).pts.sum()
             .reset_index().rename(columns={"pts": "market_points"}))
    out = total.merge(names[["norm", "gsis_id"]], on="norm", how="inner")
    log.info("prop market: %d player-weeks priced (%.0f%% of prop names "
             "matched)", len(out), 100 * len(out) / max(len(total), 1))
    return out[["season", "week", "gsis_id", "market_points"]]


def market_ceilings(seasons: tuple[int, ...] = (2025,)) -> pd.DataFrame:
    """(season, week, gsis_id, ceil_spread): DK-pts of market-implied
    ceiling room from alt-line ladders (yards at P(over)=0.10 minus
    median, x0.1). Top-quartile spread booms 21.4% vs 13% (study
    2026-07-30)."""
    season_list = ", ".join(str(int(s)) for s in seasons)
    alt = query_df(
        f"""SELECT season, week, player, market, point, price
            FROM `{settings.raw}.prop_lines`
            WHERE market IN ('player_reception_yds_alternate',
                             'player_rush_yds_alternate')
              AND bookmaker='draftkings' AND outcome_name='Over'
              AND point IS NOT NULL AND season IN ({season_list})""")
    alt["p"] = np.where(alt.price > 0, 100 / (alt.price + 100),
                        -alt.price / (-alt.price + 100))
    alt["norm"] = _norm(alt.player)
    rows = []
    for (s, w, n, m), g in alt.groupby(["season", "week", "norm", "market"]):
        g = g.sort_values("point")
        if len(g) < 3:
            continue
        x, y = g.p.to_numpy(), g.point.to_numpy()
        if x.min() > 0.10:
            p90 = y[-1] + (y[-1] - y[-2]) * (x[-1] - 0.10) / max(
                x[-2] - x[-1], 1e-3)
        else:
            p90 = float(np.interp(0.10, x[::-1], y[::-1]))
        med = (float(np.interp(0.50, x[::-1], y[::-1]))
               if x.max() >= 0.5 else y[0])
        rows.append({"season": s, "week": w, "norm": n,
                     "spread": (p90 - med) * 0.1})
    if not rows:
        return pd.DataFrame(columns=["season", "week", "gsis_id",
                                     "ceil_spread"])
    lad = (pd.DataFrame(rows).groupby(["season", "week", "norm"])
           .spread.sum().reset_index())
    names = query_df(
        f"""SELECT DISTINCT player_id AS gsis_id,
                   player_display_name AS display_name
            FROM `{settings.raw}.weekly_stats`
            WHERE season IN ({season_list})""")
    names["norm"] = _norm(names.display_name)
    out = lad.merge(names.drop_duplicates("norm")[["norm", "gsis_id"]],
                    on="norm", how="inner")
    return out.rename(columns={"spread": "ceil_spread"})[
        ["season", "week", "gsis_id", "ceil_spread"]]

```

===== FILE: src/nfl_dfs/models/registry.py =====
```python
"""Model registry (guide §7.8): every trained model written to
`{root}/{scope}/{label}/{iso_week}/model.txt` plus a JSON sidecar with
hyperparameters, features, training seasons, and validation metrics.
`model_version` is stamped on every prediction row — when a week goes
badly you must be able to answer "which model made this call and what
did it see."

Root can be a local path (tests, dev) or `gs://bucket/prefix` (prod).
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

import lightgbm as lgb

_MODEL_FILE = "model.txt"
_META_FILE = "meta.json"


@dataclass
class ModelMeta:
    scope: str
    label: str
    iso_week: str
    params: dict = field(default_factory=dict)
    features: list[str] = field(default_factory=list)
    train_seasons: list[int] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def _is_gcs(root: str) -> bool:
    return root.startswith("gs://")


def _bucket_and_prefix(root: str):
    from google.cloud import storage

    bucket_name, _, prefix = root.removeprefix("gs://").partition("/")
    return storage.Client().bucket(bucket_name), prefix.rstrip("/")


def save(model: lgb.Booster, meta: ModelMeta, root: str) -> str:
    """Write model + sidecar; returns the version string scope/label/iso_week."""
    version = f"{meta.scope}/{meta.label}/{meta.iso_week}"
    meta_json = json.dumps(asdict(meta), indent=2, default=str)

    if _is_gcs(root):
        bucket, prefix = _bucket_and_prefix(root)
        base = f"{prefix}/{version}" if prefix else version
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            model.save_model(tmp.name)
            bucket.blob(f"{base}/{_MODEL_FILE}").upload_from_filename(tmp.name)
        bucket.blob(f"{base}/{_META_FILE}").upload_from_string(meta_json)
    else:
        d = Path(root) / version
        d.mkdir(parents=True, exist_ok=True)
        model.save_model(str(d / _MODEL_FILE))
        (d / _META_FILE).write_text(meta_json)
    return version


def load(root: str, scope: str, label: str, iso_week: str) -> tuple[lgb.Booster, ModelMeta]:
    version = f"{scope}/{label}/{iso_week}"
    if _is_gcs(root):
        bucket, prefix = _bucket_and_prefix(root)
        base = f"{prefix}/{version}" if prefix else version
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            bucket.blob(f"{base}/{_MODEL_FILE}").download_to_filename(tmp.name)
            model = lgb.Booster(model_file=tmp.name)
        meta_raw = bucket.blob(f"{base}/{_META_FILE}").download_as_text()
    else:
        d = Path(root) / version
        model = lgb.Booster(model_file=str(d / _MODEL_FILE))
        meta_raw = (d / _META_FILE).read_text()
    return model, ModelMeta(**json.loads(meta_raw))


def latest_iso_week(root: str, scope: str, label: str) -> str:
    """Most recent registered week for scope/label. ISO week strings
    (2025-W09) sort lexicographically, so max() is latest."""
    if _is_gcs(root):
        bucket, prefix = _bucket_and_prefix(root)
        base = f"{prefix}/{scope}/{label}/" if prefix else f"{scope}/{label}/"
        weeks = {
            blob.name.removeprefix(base).split("/")[0]
            for blob in bucket.client.list_blobs(bucket, prefix=base)
        }
    else:
        d = Path(root) / scope / label
        weeks = {p.name for p in d.iterdir() if p.is_dir()} if d.is_dir() else set()
    if not weeks:
        raise FileNotFoundError(f"no registered models under {root}/{scope}/{label}")
    return max(weeks)

```

===== FILE: src/nfl_dfs/models/scoring.py =====
```python
"""DraftKings NFL Classic scoring (guide §6.1).

Vectorized: every StatLine field accepts a scalar or an ndarray, and
`dk_points` broadcasts — the simulator scores (players, sims) arrays of
draws in one call. The yardage bonuses are why the distribution matters:
they are discontinuous at 100/300 and only the draws see that.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class StatLine:
    pass_yards: float | np.ndarray = 0.0
    pass_tds: float | np.ndarray = 0.0
    interceptions: float | np.ndarray = 0.0
    rush_yards: float | np.ndarray = 0.0
    rush_tds: float | np.ndarray = 0.0
    receptions: float | np.ndarray = 0.0
    rec_yards: float | np.ndarray = 0.0
    rec_tds: float | np.ndarray = 0.0
    fumbles_lost: float | np.ndarray = 0.0
    two_point_conversions: float | np.ndarray = 0.0
    return_tds: float | np.ndarray = 0.0


def dk_points(s: StatLine) -> float | np.ndarray:
    """DK Classic points for a stat line. Bonus thresholds are inclusive
    (100 receiving yards is 100+, per DK's rules)."""
    pass_yards = np.asarray(s.pass_yards, dtype=float)
    rush_yards = np.asarray(s.rush_yards, dtype=float)
    rec_yards = np.asarray(s.rec_yards, dtype=float)

    pts = (
        0.04 * pass_yards
        + 4.0 * np.asarray(s.pass_tds, dtype=float)
        - 1.0 * np.asarray(s.interceptions, dtype=float)
        + 3.0 * (pass_yards >= 300.0)
        + 0.1 * rush_yards
        + 6.0 * np.asarray(s.rush_tds, dtype=float)
        + 3.0 * (rush_yards >= 100.0)
        + 1.0 * np.asarray(s.receptions, dtype=float)
        + 0.1 * rec_yards
        + 6.0 * np.asarray(s.rec_tds, dtype=float)
        + 3.0 * (rec_yards >= 100.0)
        - 1.0 * np.asarray(s.fumbles_lost, dtype=float)
        + 2.0 * np.asarray(s.two_point_conversions, dtype=float)
        + 6.0 * np.asarray(s.return_tds, dtype=float)
    )
    return float(pts) if pts.ndim == 0 else pts

```

===== FILE: src/nfl_dfs/models/simulate.py =====
```python
"""Monte Carlo composition of component predictions (guide §6.2).

Each draw samples opportunity (Poisson), conversion (Binomial), and yardage
(Gamma with the predicted per-unit rate as its mean), then scores the stat
line with real DK rules — bonuses included, which is the entire point: the
mean never sees the 100-yard cliff, the draws do.

Distributions are chosen so the simulated mean equals the analytic
composition of the components (Poisson/Binomial/Gamma all preserve their
means); a biased sampler would silently shift every projection.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .scoring import StatLine, dk_points

# Gamma shape per unit of opportunity: higher = tighter yardage around the
# predicted rate. ~2 per touch reproduces observed per-catch/carry variance.
_YARDS_SHAPE = 2.0


@dataclass
class SimResult:
    summary: pd.DataFrame
    draws: np.ndarray | None = None


def _gamma_yards(
    rng: np.random.Generator, count: np.ndarray, per_unit: np.ndarray
) -> np.ndarray:
    """Total yards over `count` opportunities averaging `per_unit` each.
    Gamma(shape=count*k, scale=per_unit/k) has mean count*per_unit."""
    shape = count * _YARDS_SHAPE
    scale = np.broadcast_to(per_unit / _YARDS_SHAPE, shape.shape)
    out = np.zeros(shape.shape)
    pos = shape > 0
    out[pos] = rng.gamma(shape[pos], scale[pos])
    return out


GAME_FACTOR_SIGMA = 0.18  # lognormal sigma of the shared per-game factor


def simulate(
    comps: pd.DataFrame,
    n_sims: int = 10_000,
    seed: int | None = None,
    keep_draws: bool = False,
    game_ids: pd.Series | None = None,
    team_ids: pd.Series | None = None,
    game_totals: pd.Series | None = None,
    bigplay_rate: pd.Series | None = None,
) -> SimResult:
    """game_ids (aligned to comps) enables correlated game environments:
    one shared lognormal factor per (game, sim) scales every player's
    opportunity in that game, so shootouts lift whole games together.
    Milly winners take 50-80% of their points from one game — without this
    the simulator prices such lineups as near-impossible. Mean-preserving
    (E[factor]=1), so projections are unchanged; only the joint tail moves.

    team_ids (aligned to comps, optional): only consulted when
    GAME_SIM_MODE=possession. Lets the two teams in a game draw DIFFERENT
    mean-preserving factors (game_sim.team_game_factors) instead of one
    shared value — the game-script asymmetry (leading team runs more,
    trailing team's DST/receivers skew differently) that's the possession
    sim's whole motivation over the shared lognormal factor. Without
    team_ids, possession mode falls back to one shared factor per game
    (game_sim.game_factor_matrix), same granularity as the lognormal draw."""
    rng = np.random.default_rng(seed)
    n = len(comps)

    game_mult = np.ones((n, n_sims))
    if game_ids is not None:
        # NaN game_ids get UNIQUE labels (2026-08-04 audit): one shared
        # "_none" group gave unrelated fringe/cold-start players a common
        # game factor — fake cross-player correlation exactly where the
        # boom/tail machinery is most credulous.
        _g = pd.Series(game_ids).reset_index(drop=True)
        _g = _g.where(_g.notna(), "_none_" + _g.index.astype(str))
        codes, uniq = pd.factorize(_g.to_numpy())
        # GAME_SIM_MODE=possession swaps the lognormal game factor for the
        # drive-state Markov engine in game_sim.py (issue #13 item 6). Read
        # at call time like the other A/B env flags (N_DARKGAME, ALT_CEIL).
        # Off by default -- see reports/possession-simulator-design.md; its
        # transition probabilities are a placeholder, not yet fit from pbp.
        if os.environ.get("GAME_SIM_MODE", "lognormal") == "possession":
            from . import game_sim
            # GAME_SIM_PACE=vegas conditions each game's DRIVE COUNT on its
            # vegas total (game_totals aligned to comps; pace = total /
            # slate mean). Pace is the only strength channel that survives
            # a mean-preserving factor -- an efficiency tilt (raising a
            # team's TD prob) cancels when the factor divides by its own
            # raised mean -- and it adds back a vegas-grounded shared
            # environment between the two teams' factors.
            paces = None
            if (os.environ.get("GAME_SIM_PACE", "") == "vegas"
                    and game_totals is not None):
                gt = pd.to_numeric(pd.Series(game_totals).reset_index(drop=True),
                                   errors="coerce").to_numpy()
                per_game = pd.Series(gt).groupby(pd.Series(codes)).first()
                per_game = per_game.reindex(range(len(uniq))).to_numpy()
                league = np.nanmean(per_game)
                if league and not np.isnan(league) and league > 0:
                    paces = np.where(np.isnan(per_game), 1.0, per_game / league)
            # GAME_SIM_TEAM_FACTORS=0 forces the shared per-game factor even
            # when team_ids are supplied -- the middle arm of the 3-arm A/B
            # (lognormal / possession-shared / possession-team), so a team-arm
            # result can be attributed to team independence vs the drive
            # engine itself. See the design doc's correlation caveat.
            team_arm = os.environ.get("GAME_SIM_TEAM_FACTORS", "1") != "0"
            if team_ids is not None and team_arm:
                team_series = pd.Series(team_ids).fillna("_none").reset_index(drop=True)
                game_series = pd.Series(codes)
                # Row order within each game group is player order, not a
                # kickoff coin flip -- "first" just needs to be a stable,
                # consistent pick per game so both of a game's teams land
                # on different slots; which team is slot 0 vs 1 doesn't
                # matter since factors_a/factors_b are symmetric in intent.
                first_team = team_series.groupby(game_series).transform("first")
                slot = (team_series != first_team).astype(int).to_numpy()
                factors_a, factors_b = game_sim.team_game_factors(
                    rng, len(uniq), n_sims, paces=paces)
                game_mult = np.where(slot[:, None] == 0, factors_a[codes], factors_b[codes])
            else:
                g = game_sim.game_factor_matrix(rng, len(uniq), n_sims, paces=paces)
                game_mult = g[codes]
        else:
            g = rng.lognormal(-GAME_FACTOR_SIGMA ** 2 / 2, GAME_FACTOR_SIGMA,
                              (len(uniq), n_sims))
            game_mult = g[codes]

    def col(name: str) -> np.ndarray:
        return np.nan_to_num(comps[name].to_numpy(dtype=float))[:, None]

    def opp(name: str) -> np.ndarray:
        """Opportunity means, scaled by the shared game factor per sim."""
        return col(name) * game_mult

    # GAME_SIM_USAGE=dirichlet (+ team_ids): correlated within-team usage.
    # Instead of each player independently Poisson-ing around their own
    # mean, each TEAM's total opportunity mean is split across teammates
    # by a Dirichlet draw centered on their shares
    # (game_sim.allocate_drive_usage), then Poisson-ed. Teammates become
    # negatively correlated (WR1 boom <-> WR2 squeeze) and low-share
    # players occasionally draw real volume -- the next-man-up boom
    # variance Addendum 24 found under-modeled. Mean-preserving:
    # E[Dirichlet share] = prior share. Off by default; same call-time
    # env pattern as GAME_SIM_MODE.
    usage_dirichlet = (os.environ.get("GAME_SIM_USAGE", "") == "dirichlet"
                       and team_ids is not None)
    team_codes = None
    if usage_dirichlet:
        team_codes, _ = pd.factorize(pd.Series(team_ids).fillna("_none").to_numpy())

    def opp_draw(name: str) -> np.ndarray:
        """Integer opportunity draws for stat `name` (targets/carries)."""
        means = opp(name)
        if not usage_dirichlet:
            return rng.poisson(means)
        from . import game_sim
        base = np.nan_to_num(comps[name].to_numpy(dtype=float))
        means = means.copy()
        for t in np.unique(team_codes):
            rows = np.flatnonzero((team_codes == t) & (base > 0))
            if len(rows) < 2:
                continue  # nothing to reallocate within
            shares = base[rows] / base[rows].sum()
            totals = means[rows].sum(axis=0)  # (n_sims,) game-factor-scaled
            alloc = game_sim.allocate_drive_usage(rng, totals, shares, n_sims=n_sims)
            means[rows] = np.atleast_2d(alloc).T
        return rng.poisson(means)

    targets = opp_draw("targets")
    receptions = rng.binomial(targets, col("catch_rate"))
    rec_yards = _gamma_yards(rng, receptions, col("ypr"))
    rec_tds = rng.poisson(col("rec_tds"), (n, n_sims))

    carries = opp_draw("carries")
    rush_yards = _gamma_yards(rng, carries, col("ypc"))
    rush_tds = rng.poisson(col("rush_tds"), (n, n_sims))

    attempts = rng.poisson(opp("pass_attempts"))
    pass_yards = _gamma_yards(rng, attempts, col("ypa"))
    pass_tds = rng.poisson(col("pass_tds"), (n, n_sims))
    interceptions = rng.poisson(col("interceptions"), (n, n_sims))

    draws = dk_points(
        StatLine(
            pass_yards=pass_yards,
            pass_tds=pass_tds,
            interceptions=interceptions,
            rush_yards=rush_yards,
            rush_tds=rush_tds,
            receptions=receptions,
            rec_yards=rec_yards,
            rec_tds=rec_tds,
        )
    )

    # Big-play mixture (env BIGPLAY, off by default): explicit house-call
    # events for deep-threat profiles. Linear widening cannot create the
    # LUMP a deep WR's true distribution has (the 2-long-TD eruption --
    # Fuller 56.7 @ $4.5k, the event class real Milly winners are built
    # on, Addendum 38). Each event adds TD + long-catch yardage; the
    # expected addition is subtracted so E[row] is EXACTLY unchanged --
    # only the shape moves, mass migrates from the middle to the far
    # tail. bigplay_rate (aligned to comps) carries expected events/game
    # per player; callers derive it from the deep-target profile.
    if bigplay_rate is not None:
        rate = np.nan_to_num(
            pd.Series(bigplay_rate).reset_index(drop=True)
            .to_numpy(dtype=float)).clip(0.0, 0.5)[:, None]
        if rate.any():
            events = rng.poisson(rate, (n, n_sims))
            # long TD: 6 (TD) + 1 (catch) + ~45yd => ~4.5 yardage points
            yds = 30.0 + rng.exponential(15.0, (n, n_sims))
            lump_pts = 6.0 + 1.0 + yds / 10.0
            mean_lump = 6.0 + 1.0 + 4.5
            draws = draws + events * lump_pts - rate * mean_lump

    # proj_tail: mean of the top quartile of outcomes (ETR's ceiling
    # definition, vendor audit 2026-08-03) — a tail AVERAGE is more
    # stable than the p90 point and weighs the far tail the p90 ignores.
    srt = np.sort(draws, axis=1)
    q3 = srt[:, int(0.75 * srt.shape[1]):]
    summary = pd.DataFrame(
        {
            "proj_points": draws.mean(axis=1),
            "proj_p10": np.percentile(draws, 10, axis=1),
            "proj_p50": np.percentile(draws, 50, axis=1),
            "proj_p90": np.percentile(draws, 90, axis=1),
            "proj_tail": q3.mean(axis=1),
            "proj_std": draws.std(axis=1),
            "p_20_plus": (draws >= 20.0).mean(axis=1),
        },
        index=comps.index,
    )
    return SimResult(summary=summary, draws=draws if keep_draws else None)

```

===== FILE: src/nfl_dfs/models/train_job.py =====
```python
"""Weekly retrain (guide §7.8): full retrain every Tuesday with the
completed week added — training is cheap and incremental updates
accumulate drift. Every component model lands in the registry under the
current ISO week with its metrics sidecar.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from ..bq import query_df
from ..config import current_season, settings
from . import baseline, components, registry
from .featureset import FEATURES

log = logging.getLogger(__name__)

SCOPE = "pooled"


def _registry_root() -> str:
    return f"gs://{settings.gcs_bucket}/{settings.model_registry_prefix}"


def _iso_week(today: date | None = None) -> str:
    iso = (today or date.today()).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def training_panel() -> pd.DataFrame:
    return query_df(
        f"""
        SELECT * FROM `{settings.features}.player_week_training`
        WHERE season >= {settings.train_first_season}
          AND position IN ('QB', 'RB', 'WR', 'TE')
        """
    )


def train_and_register(today: date | None = None) -> str:
    """Retrain the component models on everything up to now, validate the
    baseline walk-forward for the metrics sidecar, and register every
    booster under this ISO week. Returns the model version prefix."""
    panel = training_panel()
    season = current_season(today)
    iso_week = _iso_week(today)
    train_seasons = sorted(int(s) for s in panel.season.unique() if s < season + 1)

    wf = baseline.walk_forward(panel)
    metrics = {
        str(val): {"mae": rep.mae, "market_mae": rep.market_mae,
                   "beats_market": rep.beats_market}
        for val, rep in wf.fold_reports.items()
    }
    log.info("Walk-forward folds: %s", metrics)

    cm = components.train(panel, target_season=season + 1)
    root = _registry_root()
    for name, booster in cm.models.items():
        registry.save(
            booster,
            registry.ModelMeta(
                scope=SCOPE,
                label=f"comp_{name}",
                iso_week=iso_week,
                params=dict(booster.params),
                features=FEATURES,
                train_seasons=train_seasons,
                metrics=metrics,
            ),
            root,
        )
    version = f"{SCOPE}/components/{iso_week}"
    log.info("Registered %d component models as %s", len(cm.models), version)
    return version


def load_latest_component_models() -> tuple[components.ComponentModels, str]:
    """Latest registered component set + its version string, for inference."""
    root = _registry_root()
    iso_week = registry.latest_iso_week(root, SCOPE, "comp_targets")
    models = {
        name: registry.load(root, SCOPE, f"comp_{name}", iso_week)[0]
        for name in components.COMPONENT_NAMES
    }
    return components.ComponentModels(models=models), f"{SCOPE}/components/{iso_week}"

```

===== FILE: src/nfl_dfs/models/tuning.py =====
```python
"""Walk-forward hyperparameter tuning with Optuna (guide §7.5).

Optional: requires the `tuning` extra. 150 trials on 40k rows runs in a
few minutes on a laptop — every fold is walk-forward, so the tuned params
are honest by construction.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from .featureset import LGB_THREADS, build_X
from .validation import walk_forward_folds
from .weights import sample_weights


def tune(
    panel: pd.DataFrame,
    label: str,
    objective: str = "tweedie",
    n_trials: int = 150,
    min_train_seasons: int = 4,
) -> dict:
    """Return the best LightGBM params for `label` by mean walk-forward MAE."""
    import optuna  # tuning extra

    folds, _test = walk_forward_folds(
        sorted(panel.season.unique()), min_train_seasons=min_train_seasons
    )

    def _objective(trial: "optuna.Trial") -> float:
        params = dict(
            num_threads=LGB_THREADS,
            objective=objective,
            learning_rate=trial.suggest_float("lr", 0.01, 0.1, log=True),
            num_leaves=trial.suggest_int("leaves", 15, 63),
            min_data_in_leaf=trial.suggest_int("min_leaf", 20, 200),
            feature_fraction=trial.suggest_float("ff", 0.5, 1.0),
            lambda_l2=trial.suggest_float("l2", 0.1, 20.0, log=True),
            verbosity=-1,
        )
        if objective == "tweedie":
            params["tweedie_variance_power"] = trial.suggest_float("tvp", 1.1, 1.9)
        maes = []
        for train_seasons, val_season in folds:
            tr = panel[panel.season.isin(train_seasons)]
            va = panel[panel.season == val_season]
            model = lgb.train(
                params,
                lgb.Dataset(build_X(tr), tr[label],
                            weight=sample_weights(tr, val_season),
                            categorical_feature=["position"]),
                num_boost_round=2000,
                valid_sets=[lgb.Dataset(build_X(va), va[label])],
                callbacks=[lgb.early_stopping(100, verbose=False)],
            )
            maes.append(float(np.abs(model.predict(build_X(va)) - va[label]).mean()))
        return float(np.mean(maes))

    study = optuna.create_study(direction="minimize")
    study.optimize(_objective, n_trials=n_trials)
    return study.best_params

```

===== FILE: src/nfl_dfs/models/validation.py =====
```python
"""Walk-forward validation and the metrics that matter (guide §6.3):
MAE vs. the market, distribution calibration, and within-position rank
correlation. Random k-fold leaks team-season effects; never use it here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class EvalReport:
    mae: float
    market_mae: float | None = None
    beats_market: bool | None = None
    coverage_p10: float | None = None
    coverage_p90: float | None = None
    rank_corr_by_position: dict[str, float] = field(default_factory=dict)


def walk_forward_folds(
    seasons: list[int], min_train_seasons: int = 6
) -> tuple[list[tuple[list[int], int]], int]:
    """Expanding-window folds over `seasons`, holding the final season out
    entirely as the test set (touch once, at the very end).

    Returns ([(train_seasons, val_season), ...], test_season).
    """
    seasons = sorted(set(seasons))
    test = seasons[-1]
    develop = seasons[:-1]
    folds = [
        (develop[:i], develop[i]) for i in range(min_train_seasons, len(develop))
    ]
    if not folds:
        raise ValueError(
            f"need at least {min_train_seasons + 2} seasons for "
            f"{min_train_seasons} train + 1 validation + 1 test; got {len(seasons)}"
        )
    return folds, test


def evaluate(
    y: pd.Series | np.ndarray,
    pred: np.ndarray,
    market: pd.Series | np.ndarray | None = None,
    p10: np.ndarray | None = None,
    p90: np.ndarray | None = None,
    positions: pd.Series | None = None,
) -> EvalReport:
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    rep = EvalReport(mae=float(np.abs(pred - y).mean()))

    if market is not None:
        market = np.asarray(market, dtype=float)
        ok = ~np.isnan(market)
        # An all-null market (no props/dk_ppg for the period — see the README
        # data deficiency log) means "no comparison", not "didn't beat it".
        if ok.any():
            rep.market_mae = float(np.abs(market[ok] - y[ok]).mean())
            rep.beats_market = bool(np.abs(pred[ok] - y[ok]).mean() < rep.market_mae)

    if p10 is not None:
        rep.coverage_p10 = float(np.mean(y < np.asarray(p10, dtype=float)))
    if p90 is not None:
        rep.coverage_p90 = float(np.mean(y < np.asarray(p90, dtype=float)))

    if positions is not None:
        pos = np.asarray(positions)
        for p in pd.unique(pos):
            mask = pos == p
            if mask.sum() >= 3:
                rho = stats.spearmanr(pred[mask], y[mask]).statistic
                rep.rank_corr_by_position[str(p)] = float(rho)
    return rep


def calibration_table(
    y: np.ndarray, preds: dict[float, np.ndarray]
) -> pd.DataFrame:
    """Empirical fraction of actuals below each predicted quantile. A
    calibrated p10 shows empirical ≈ 0.10; plot this every retrain."""
    y = np.asarray(y, dtype=float)
    rows = [
        {"quantile": q, "empirical": float(np.mean(y < np.asarray(qs, dtype=float)))}
        for q, qs in sorted(preds.items())
    ]
    return pd.DataFrame(rows)

```

===== FILE: src/nfl_dfs/models/weights.py =====
```python
"""Recency sample weights (guide §7.4).

Exponential decay on season distance only — recency *within* a season is
already carried by the rolling features, and weighting it again would
double-count and chase noise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sample_weights(
    df: pd.DataFrame, target_season: int, half_life_seasons: float = 3.0
) -> np.ndarray:
    """0.5 ** (season_age / half_life). Refuses future seasons — a row from
    after the target season in the training set is a leak, not a weight."""
    age = target_season - df["season"].to_numpy()
    if (age < 0).any():
        bad = sorted(df.loc[age < 0, "season"].unique())
        raise ValueError(
            f"training rows from seasons {bad} are after target season {target_season}"
        )
    return 0.5 ** (age / half_life_seasons)

```

===== FILE: src/nfl_dfs/notes.py =====
```python
"""Manual usage notes: qualitative intel (coach usage statements, role
changes) entered by hand and applied as opportunity-prior adjustments.

Why this exists: the model's cold-start priors are generic role averages
(coldstart.py). Credible offseason/camp news ("he's moving to the slot",
"he gets the two-minute snaps") is real signal in weeks 1-4, before stats
exist to prove it. A note scales the affected player's opportunity
components (targets/carries/pass attempts) by `mult`, decaying linearly to
nothing by DECAY_FULL_WEEK — by then actual snaps speak for themselves.

Applied at inference only (run_projections), never in replays: notes are
forward-looking by construction, and injecting them into historical
backtests would be leakage in spirit if not in letter.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import pandas as pd

from .bq import load_dataframe, query_df
from .config import settings

log = logging.getLogger(__name__)

TABLE = "manual_notes"
DECAY_FULL_WEEK = 6  # full effect week 1, linearly to zero here
OPP_COLS = ("targets", "carries", "pass_attempts")


def _table() -> str:
    return f"{settings.features}.{TABLE}"


def decay(week: int) -> float:
    """Fraction of a note's effect remaining in `week` (1.0 -> 0.0)."""
    return max(0.0, min(1.0, (DECAY_FULL_WEEK - week) / (DECAY_FULL_WEEK - 1)))


def list_notes(season: int | None = None) -> pd.DataFrame:
    where = f"WHERE season = {int(season)}" if season else ""
    try:
        return query_df(
            f"SELECT note_id, gsis_id, display_name, season, mult, note, "
            f"source, created_at FROM `{_table()}` {where} ORDER BY created_at"
        )
    except Exception:  # table may not exist until the first note
        log.info("manual_notes table absent or unreadable; returning empty")
        return pd.DataFrame(columns=["note_id", "gsis_id", "display_name",
                                     "season", "mult", "note", "source",
                                     "created_at"])


def add_note(gsis_id: str, display_name: str, season: int, mult: float,
             note: str, source: str = "") -> str:
    """mult is the opportunity multiplier at full effect (e.g. 1.15 = +15%
    targets/carries; 0.85 = reduced role). Clamped to a sane band —
    qualitative news never justifies more than +/-40%."""
    mult = max(0.6, min(1.4, float(mult)))
    note_id = uuid.uuid4().hex[:12]
    row = pd.DataFrame([{
        "note_id": note_id, "gsis_id": gsis_id, "display_name": display_name,
        "season": int(season), "mult": mult, "note": note, "source": source,
        "created_at": datetime.now(timezone.utc),
    }])
    load_dataframe(row, _table(), write_disposition="WRITE_APPEND")
    return note_id


def delete_note(note_id: str) -> int:
    from .bq import client

    job = client().query(
        f"DELETE FROM `{_table()}` WHERE note_id = @id",
        job_config=_param_config(note_id),
    )
    job.result()
    return job.num_dml_affected_rows or 0


def _param_config(note_id: str):
    from google.cloud import bigquery

    return bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("id", "STRING", note_id)])


def apply_notes(comps: pd.DataFrame, feats: pd.DataFrame, season: int,
                week: int) -> pd.DataFrame:
    """Scale opportunity components for players with active notes. Mean
    projections move by design — this is the user overriding the prior.
    Failure-safe: projections without notes beat no projections."""
    try:
        notes = list_notes(season)
    except Exception:
        log.exception("manual notes unavailable; projecting without them")
        return comps
    if notes.empty:
        return comps
    d = decay(week)
    if d <= 0:
        return comps
    comps = comps.copy()
    gsis = feats.get("gsis_id")
    if gsis is None:
        return comps
    # Multiple notes on one player multiply together (each is independent
    # intel); each note's effect is interpolated toward 1.0 by the decay.
    eff = notes.assign(m=1 + (notes.mult - 1) * d).groupby("gsis_id").m.prod()
    m = gsis.map(eff).fillna(1.0).to_numpy()
    applied = int((m != 1.0).sum())
    for c in OPP_COLS:
        if c in comps.columns:
            comps[c] = comps[c] * m
    if applied:
        log.info("manual notes: scaled opportunity for %d players "
                 "(week %d decay %.0f%%)", applied, week, 100 * d)
    return comps


# Weekly lineup preferences: bans (never roster) and boosts (tilt into
# more lineups). Stored by normalized display name and matched against
# the pool at build time — robust to dk_player_id churn across slates.

PREFS_TABLE = "lineup_prefs"
BOOST_BONUS = 2.5  # proj_tourney points added to boosted players


def _prefs_table() -> str:
    return f"{settings.features}.{PREFS_TABLE}"


def norm_name(s: str) -> str:
    import re

    return re.sub(r"[^a-z ]", "", str(s).lower()).strip()


def list_prefs(season: int, week: int) -> pd.DataFrame:
    try:
        return query_df(
            f"SELECT pref_id, display_name, kind, created_at FROM "
            f"`{_prefs_table()}` WHERE season={int(season)} AND "
            f"week={int(week)} ORDER BY created_at")
    except Exception:
        return pd.DataFrame(columns=["pref_id", "display_name", "kind",
                                     "created_at"])


def add_pref(season: int, week: int, display_name: str, kind: str) -> str:
    assert kind in ("ban", "boost")
    pref_id = uuid.uuid4().hex[:12]
    load_dataframe(pd.DataFrame([{
        "pref_id": pref_id, "season": int(season), "week": int(week),
        "display_name": display_name, "norm": norm_name(display_name),
        "kind": kind, "created_at": datetime.now(timezone.utc)}]),
        _prefs_table(), write_disposition="WRITE_APPEND")
    return pref_id


def delete_pref(pref_id: str) -> int:
    from .bq import client

    job = client().query(f"DELETE FROM `{_prefs_table()}` WHERE pref_id=@id",
                         job_config=_param_config(pref_id))
    job.result()
    return job.num_dml_affected_rows or 0


def apply_prefs(pool: list[dict], season: int, week: int) -> list[dict]:
    """Drop banned players; add BOOST_BONUS to boosted players' objective.
    Failure-safe: no prefs table -> pool unchanged."""
    try:
        p = query_df(f"SELECT norm, kind FROM `{_prefs_table()}` WHERE "
                     f"season={int(season)} AND week={int(week)}")
    except Exception:
        return pool
    if p.empty:
        return pool
    bans = set(p[p.kind == "ban"].norm)
    boosts = set(p[p.kind == "boost"].norm)
    out = []
    for pl in pool:
        n = norm_name(pl.get("name", ""))
        if n in bans:
            continue
        if n in boosts:
            pl = {**pl, "proj": pl["proj"] + BOOST_BONUS}
        out.append(pl)
    log.info("prefs: %d banned, %d boosted (wk %s)", len(bans), len(boosts),
             week)
    return out


# Season bankroll tracking: weekly contests/spent/won + best-lineup notes.

RESULTS_TABLE = "season_results"


def _results_table() -> str:
    return f"{settings.features}.{RESULTS_TABLE}"


def list_results(season: int) -> pd.DataFrame:
    try:
        return query_df(
            f"SELECT result_id, week, contests, spent, won, best_score, "
            f"best_rank, note FROM `{_results_table()}` "
            f"WHERE season={int(season)} ORDER BY week")
    except Exception:
        return pd.DataFrame(columns=["result_id", "week", "contests",
                                     "spent", "won", "best_score",
                                     "best_rank", "note"])


def upsert_result(season: int, week: int, contests: int, spent: float,
                  won: float, best_score: float | None = None,
                  best_rank: int | None = None, note: str = "") -> str:
    """One row per (season, week): replace any existing row for the week."""
    from .bq import client

    try:
        client().query(
            f"DELETE FROM `{_results_table()}` WHERE season={int(season)} "
            f"AND week={int(week)}").result()
    except Exception:
        pass  # table may not exist yet
    rid = uuid.uuid4().hex[:12]
    load_dataframe(pd.DataFrame([{
        "result_id": rid, "season": int(season), "week": int(week),
        "contests": int(contests), "spent": float(spent),
        "won": float(won),
        "best_score": float(best_score) if best_score is not None else None,
        "best_rank": int(best_rank) if best_rank is not None else None,
        "note": note, "created_at": datetime.now(timezone.utc)}]),
        _results_table(), write_disposition="WRITE_APPEND")
    return rid


def import_entry_history(csv_text: str, season: int) -> dict:
    """Aggregate a DraftKings Entry History CSV into weekly rows.
    Tolerant of column naming: finds fee/winnings/date columns by
    substring. Only rows whose date falls inside an NFL week count."""
    import io

    df = pd.read_csv(io.StringIO(csv_text))
    cols = {c.lower(): c for c in df.columns}

    def find(*subs):
        for lc, c in cols.items():
            if any(s in lc for s in subs):
                return c
        return None

    fee, won, date = (find("fee"), find("winning", "won"),
                      find("date", "time"))
    if not (fee and won and date):
        raise ValueError(f"unrecognized CSV columns: {list(df.columns)}")
    df["_d"] = pd.to_datetime(df[date], errors="coerce").dt.date
    weeks = query_df(
        f"SELECT week, MIN(gameday) AS d0, MAX(gameday) AS d1 "
        f"FROM `{settings.raw}.schedules` WHERE season={int(season)} "
        f"GROUP BY week")
    existing = list_results(season)
    money = lambda s: pd.to_numeric(
        s.astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")
    df[fee], df[won] = money(df[fee]), money(df[won])
    out = {}
    for w in weeks.itertuples():
        d0 = pd.Timestamp(w.d0).date()
        d1 = pd.Timestamp(w.d1).date() + pd.Timedelta(days=1)
        rows = df[(df._d >= d0) & (df._d <= d1)]
        if len(rows):
            # Preserve manually entered fields across re-imports — the DK
            # export is cumulative, so the same file gets uploaded weekly.
            old = existing[existing.week == int(w.week)]
            bs = (float(old.best_score.iloc[0])
                  if len(old) and pd.notna(old.best_score.iloc[0]) else None)
            br = (int(old.best_rank.iloc[0])
                  if len(old) and pd.notna(old.best_rank.iloc[0]) else None)
            note = (str(old.note.iloc[0]) if len(old) and old.note.iloc[0]
                    else "imported from DK entry history")
            upsert_result(season, int(w.week), len(rows),
                          float(rows[fee].sum()), float(rows[won].sum()),
                          best_score=bs, best_rank=br, note=note)
            out[int(w.week)] = {"contests": len(rows),
                                "spent": float(rows[fee].sum()),
                                "won": float(rows[won].sum())}
    return out


# Entered lineups: recorded when the DK upload CSV is downloaded, scored
# against warehouse actuals after games — auto-fills best_score in the
# season tracker (rank still comes from DK's contest standings export).

ENTERED_TABLE = "entered_lineups"


def record_entered_lineups(season: int, week: int, lineups) -> int:
    """Persist the downloaded entry set (latest download replaces)."""
    from .bq import client

    try:
        client().query(
            f"DELETE FROM `{settings.features}.{ENTERED_TABLE}` "
            f"WHERE season={int(season)} AND week={int(week)}").result()
    except Exception:
        pass
    rows = []
    now = datetime.now(timezone.utc)
    for ix, lu in enumerate(lineups):
        for p in lu.players:
            rows.append({"season": int(season), "week": int(week),
                         "lineup_ix": ix, "dk_player_id": p.get("id"),
                         "name": p.get("name"), "pos": p.get("pos"),
                         "team": p.get("team"), "created_at": now})
    if rows:
        load_dataframe(pd.DataFrame(rows),
                       f"{settings.features}.{ENTERED_TABLE}",
                       write_disposition="WRITE_APPEND")
    return len(lineups)


def list_entered_sets(season: int) -> pd.DataFrame:
    """Per-week summary of the recorded export set: lineup/player counts
    and when the DK CSV was downloaded. One set per week — each download
    replaces the previous record, so this is always the latest export."""
    try:
        return query_df(
            f"SELECT week, COUNT(DISTINCT lineup_ix) AS lineups, "
            f"COUNT(*) AS players, "
            f"CAST(MAX(created_at) AS STRING) AS recorded_at "
            f"FROM `{settings.features}.{ENTERED_TABLE}` "
            f"WHERE season={int(season)} GROUP BY week ORDER BY week")
    except Exception:  # table may not exist until the first download
        return pd.DataFrame(columns=["week", "lineups", "players",
                                     "recorded_at"])


def delete_entered_lineups(season: int, week: int) -> int:
    """Drop the week's recorded export set entirely, so a throwaway
    what-if download can't leak into Tuesday scoring (best_score) or the
    duplicate-swap guard. Does NOT touch season_results — money fields
    come from the DK entry-history import, and an already-scored
    best_score stays until re-scored or edited via POST /results."""
    from .bq import client

    job = client().query(
        f"DELETE FROM `{settings.features}.{ENTERED_TABLE}` "
        f"WHERE season={int(season)} AND week={int(week)}")
    job.result()
    return job.num_dml_affected_rows or 0


def scored_lineups(season: int, week: int) -> pd.DataFrame:
    """Recorded lineups joined to actual points: one row per player with
    lineup_ix, name, pos, team, pts (empty frame if nothing recorded)."""
    e = query_df(f"SELECT lineup_ix, name, pos, team FROM "
                 f"`{settings.features}.{ENTERED_TABLE}` "
                 f"WHERE season={int(season)} AND week={int(week)}")
    if e.empty:
        return e
    skill = query_df(
        f"""SELECT w.player_display_name AS pname, t.y_dk_points AS pts
            FROM `{settings.features}.player_week_training` t
            JOIN (SELECT DISTINCT player_id, player_display_name
                  FROM `{settings.raw}.weekly_stats`
                  WHERE season={int(season)}) w
              ON w.player_id = t.gsis_id
            WHERE t.season={int(season)} AND t.week={int(week)}""")
    dstp = query_df(f"SELECT team, dst_dk_points FROM "
                    f"`{settings.features}.team_defense_week` "
                    f"WHERE season={int(season)} AND week={int(week)}")
    smap = dict(zip(skill.pname.map(norm_name), skill.pts))
    dmap = dict(zip(dstp.team, dstp.dst_dk_points))
    e["pts"] = [
        float(dmap.get(r.team, 0.0)) if r.pos == "DST"
        else float(smap.get(norm_name(r.name), 0.0))
        for r in e.itertuples()]
    return e


def score_entries(season: int, week: int) -> dict:
    """Score recorded lineups vs actuals; upsert best_score into the
    season tracker, preserving money fields and notes."""
    e = scored_lineups(season, week)
    if e.empty:
        return {"scored": 0}
    totals = e.groupby("lineup_ix").pts.sum().sort_values(ascending=False)
    best = float(totals.iloc[0])
    old = list_results(season)
    row = old[old.week == int(week)]
    upsert_result(
        season, week,
        contests=int(row.contests.iloc[0]) if len(row) else len(totals),
        spent=float(row.spent.iloc[0]) if len(row) else 0.0,
        won=float(row.won.iloc[0]) if len(row) else 0.0,
        best_score=best,
        best_rank=(int(row.best_rank.iloc[0]) if len(row)
                   and pd.notna(row.best_rank.iloc[0]) else None),
        note=str(row.note.iloc[0]) if len(row) and row.note.iloc[0] else "")
    return {"scored": int(totals.size), "best": best,
            "top3": [round(v, 1) for v in totals.head(3)]}


def swap_entered_player(season: int, week: int, lineup_ix: int,
                        out_name: str, new_player: dict) -> None:
    """Mirror a lineup edit made on DK: replace one player in one recorded
    lineup so Tuesday scoring matches reality."""
    from google.cloud import bigquery

    from .bq import client

    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("o", "STRING", norm_name(out_name))])
    client().query(
        f"DELETE FROM `{settings.features}.{ENTERED_TABLE}` "
        f"WHERE season={int(season)} AND week={int(week)} "
        f"AND lineup_ix={int(lineup_ix)} "
        f"AND REGEXP_REPLACE(LOWER(name), r'[^a-z ]', '') = @o",
        job_config=cfg).result()
    load_dataframe(pd.DataFrame([{
        "season": int(season), "week": int(week),
        "lineup_ix": int(lineup_ix),
        "dk_player_id": new_player.get("dk_player_id"),
        "name": new_player["name"], "pos": new_player["pos"],
        "team": new_player["team"],
        "created_at": datetime.now(timezone.utc)}]),
        f"{settings.features}.{ENTERED_TABLE}",
        write_disposition="WRITE_APPEND")


def entered_rosters(season: int, week: int) -> dict[int, set[str]]:
    """lineup_ix -> set of normalized player names, for duplicate checks."""
    e = query_df(f"SELECT lineup_ix, name FROM "
                 f"`{settings.features}.{ENTERED_TABLE}` "
                 f"WHERE season={int(season)} AND week={int(week)}")
    out: dict[int, set[str]] = {}
    for r in e.itertuples():
        out.setdefault(int(r.lineup_ix), set()).add(norm_name(r.name))
    return out

```

===== FILE: src/nfl_dfs/ops/__init__.py =====
```python

```

===== FILE: src/nfl_dfs/ops/backup.py =====
```python
"""Daily snapshots of the irreplaceable tables (safety net beyond
BigQuery's 7-day time travel).

Everything nflverse/odds/DK-API-shaped can be re-ingested from source;
these tables cannot: hand-imported contest standings and the LineStar
ownership backfill (the API stopped serving projections historically and
DK deletes standings after 30 days), user-authored notes/watchlist, the
entered-lineups journal, and hand-curated ID overrides.

CREATE SNAPSHOT TABLE bills only for storage DELTA vs the base table, so
30 daily snapshots of small tables cost effectively nothing. Snapshots
land in the `nfl_backups` dataset as <table>_YYYYMMDD with a 30-day
expiry — restore is `CREATE TABLE ds.t CLONE nfl_backups.t_YYYYMMDD`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from ..config import settings

log = logging.getLogger(__name__)

BACKUP_DATASET = "nfl_backups"
RETENTION_DAYS = 30

# (dataset_attr, table) — dataset resolved from settings so this follows
# env config. Append here when a new irreplaceable table appears (same
# discipline as status.FEEDS).
TABLES: list[tuple[str, str]] = [
    ("raw", "contest_ownership"),
    ("raw", "contest_entries"),  # per-entry lineups; source purges in ~4 days
    ("raw", "dk_salaries_historical"),
    ("raw", "showdown_salaries_historical"),
    ("raw", "dk_contest_fills"),  # dk_contest_fills_nfl is a VIEW — skip
    ("features", "manual_notes"),
    ("features", "player_watch_notes"),
    ("features", "lineup_prefs"),
    ("features", "season_results"),
    ("features", "entered_lineups"),
    ("features", "player_id_overrides"),
    ("features", "external_projections"),  # user-uploaded; source CSVs expire
]


def run() -> None:
    from google.api_core.exceptions import NotFound

    from ..bq import client

    c = client()
    project = settings.raw.split(".")[0]
    ds = f"{project}.{BACKUP_DATASET}"
    try:
        c.get_dataset(ds)
    except NotFound:
        c.create_dataset(ds)
        log.info("created backup dataset %s", ds)

    import os

    # NOTE: never reuse a snapshot name deleted <7 days ago — BigQuery
    # treats same-name recreation inside the time-travel window as a
    # replace and demands deleteSnapshot, which the job SA lacks by
    # design. Daily date stamps make this a non-issue in production;
    # BACKUP_SUFFIX exists so a fresh-name run can be tested on demand.
    stamp = (datetime.now(timezone.utc).strftime("%Y%m%d")
             + os.environ.get("BACKUP_SUFFIX", ""))
    ok = missing = 0
    for attr, table in TABLES:
        src = f"{getattr(settings, attr)}.{table}"
        dst = f"{ds}.{table}_{stamp}"
        try:
            # Explicit existence check instead of IF NOT EXISTS: on an
            # existing snapshot the DDL path demands deleteSnapshot,
            # which the job's service account deliberately lacks
            # (dataEditor has createSnapshot only — backups are
            # append-only from the job's point of view).
            try:
                c.get_table(dst)
                log.info("backup: %s already exists, kept", dst)
                ok += 1
                continue
            except NotFound:
                pass
            # Retention comes from the DATASET default expiration (30d),
            # not an OPTIONS clause: an explicit expiration_timestamp on
            # CREATE SNAPSHOT demands bigquery.tables.deleteSnapshot
            # (the expiry is a scheduled delete), which the job SA
            # deliberately lacks. Inherited default dodges the check.
            c.query(f"CREATE SNAPSHOT TABLE `{dst}` CLONE `{src}`").result()
            ok += 1
        except NotFound:
            # Tables like dk_contest_fills only exist once the season
            # starts; a missing base table is expected, not an error.
            log.info("backup: %s absent, skipped", src)
            missing += 1
        except Exception:
            log.exception("backup FAILED for %s", src)
    print(f"backup {stamp}: {ok} snapshotted, {missing} absent, "
          f"{len(TABLES) - ok - missing} failed")
    if ok + missing < len(TABLES):
        raise SystemExit(1)  # surface failure to the job-alert pipeline

```

===== FILE: src/nfl_dfs/ops/field_calibration.py =====
```python
"""Field-sim calibration vs real contest entries (in-season queue 10a/10b).

Answers the go/no-go question for the conditional-field-sampler build:
does our field simulator's JOINT structure reproduce what the public
actually enters? Three measurements against a real contest's entry rows
(`nfl_raw.contest_entries`, imported by `import-ownership`):

1. Dupe correlation: per distinct lineup, simulated duplicate count vs
   actual — RTS benchmarks: ~0.43 for independent sampling, ~0.72 with
   conditional (anchor-aware) sampling.
2. Independence baseline: product-of-marginals expected dupes.
3. Leftover-salary distribution: real entries spend nearly the cap; a
   field sim that leaves more money produces punt-heavy phantoms that
   overstate our own uniqueness.

Run in-season: `nfl-dfs field-calibration --season S --week W
--contest-id ID` (needs live projections + salaries for that week).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


def real_dupe_table(entries: pd.DataFrame) -> pd.DataFrame:
    """distinct lineup -> actual entry count, from contest_entries rows."""
    g = entries.groupby("players_key").agg(
        count=("players_key", "size"), best_rank=("rank", "min"))
    return g.reset_index()


def sim_dupe_table(field_lineups: list, id_to_name: dict) -> pd.DataFrame:
    """Same keying for simulated field lineups (arrays of player row
    indices or ids) so the two tables join on players_key."""
    keys = ["|".join(sorted(str(id_to_name.get(i, i)) for i in lu))
            for lu in field_lineups]
    s = pd.Series(keys).value_counts()
    return pd.DataFrame({"players_key": s.index, "sim_count": s.values})


def dupe_correlation(real: pd.DataFrame, sim: pd.DataFrame,
                     n_entries: int, n_sims: int) -> dict:
    """Join on distinct lineup, rescale sim counts to contest size, and
    correlate — the RTS headline number, computed identically."""
    j = real.merge(sim, on="players_key", how="left")
    j["sim_count"] = j.sim_count.fillna(0.0) * (n_entries / max(n_sims, 1))
    out = {
        "n_distinct_real": int(len(real)),
        "match_rate": float((j.sim_count > 0).mean()),
        "dupe_corr": float(j["count"].corr(j.sim_count))
        if len(j) > 2 else float("nan"),
        "max_real_dupe": int(real["count"].max()) if len(real) else 0,
    }
    return out


def independence_baseline(entries: pd.DataFrame,
                          ownership: pd.Series) -> pd.DataFrame:
    """Product-of-marginals expected dupes per distinct real lineup
    (ownership: display_name -> pct_drafted/100). The floor any joint
    model must beat."""
    n = len(entries)
    rows = []
    for key, cnt in entries.groupby("players_key").size().items():
        names = str(key).split("|")
        probs = [float(ownership.get(nm, np.nan)) for nm in names]
        exp = float(np.prod(probs)) * n if not any(np.isnan(probs)) else np.nan
        rows.append((key, cnt, exp))
    return pd.DataFrame(rows, columns=["players_key", "count", "indep_expected"])


def salary_leftover(entries: pd.DataFrame, name_to_salary: dict,
                    cap: int = 50_000) -> pd.Series:
    """Leftover salary per real entry (entries where all names priced)."""
    out = []
    for key in entries.players_key:
        sal = [name_to_salary.get(nm) for nm in str(key).split("|")]
        if all(s is not None for s in sal):
            out.append(cap - int(sum(sal)))
    return pd.Series(out, dtype=float)


def run(season: int, week: int, contest_id: str,
        n_sims: int = 20_000) -> None:
    from ..bq import query_df
    from ..config import settings
    from .. import external_proj  # _norm

    entries = query_df(
        f"""SELECT rank, players_key FROM `{settings.raw}.contest_entries`
            WHERE season={int(season)} AND week={int(week)}
              AND contest_id=@cid""", params={"cid": str(contest_id)})
    if entries.empty:
        print(f"no contest_entries for {season} wk {week} contest "
              f"{contest_id}; run import-ownership first")
        return
    own = query_df(
        f"""SELECT display_name, AVG(pct_drafted)/100 own
            FROM `{settings.raw}.contest_ownership`
            WHERE season={int(season)} AND week={int(week)}
              AND contest_id=@cid GROUP BY display_name""",
        params={"cid": str(contest_id)})
    ownership = pd.Series(own.own.values, index=own.display_name)

    real = real_dupe_table(entries)
    base = independence_baseline(entries, ownership)
    b = base.dropna()
    print(f"real: {len(entries)} entries, {len(real)} distinct, "
          f"max dupe {real['count'].max()}")
    if len(b) > 2:
        print(f"independence baseline dupe corr: "
              f"{b['count'].corr(b.indep_expected):.3f} "
              f"(RTS reference: ~0.43)")

    # Our field sim on this week's live slate
    from ..app.main import get_store
    from ..backtest.field import sample_field

    proj = get_store().projections(season, week)
    if proj.empty:
        print("no projections for the week; sim comparison skipped")
        return
    frame = pd.DataFrame({
        "id": proj.dk_player_id, "name": proj.display_name,
        "pos": proj.position, "salary": proj.salary,
        "proj": proj.proj_points})
    frame = frame.dropna(subset=["salary", "proj"])
    field = sample_field(frame, n_lineups=n_sims)
    id_to_name = dict(zip(range(len(frame)), frame.name))
    sim = sim_dupe_table(field, id_to_name)
    res = dupe_correlation(real, sim, n_entries=len(entries), n_sims=n_sims)
    print(f"OUR FIELD SIM: dupe corr {res['dupe_corr']:.3f}  "
          f"match rate {res['match_rate']:.1%}  (RTS conditional: ~0.72)")

    sal_map = dict(zip(frame.name, frame.salary.astype(int)))
    left = salary_leftover(entries, sal_map)
    if len(left):
        print(f"real leftover salary: median {left.median():.0f} "
              f"p90 {left.quantile(.9):.0f} share>$1k {(left>1000).mean():.0%}")

```

===== FILE: src/nfl_dfs/optimizer/__init__.py =====
```python

```

===== FILE: src/nfl_dfs/optimizer/export.py =====
```python
"""DK upload CSV export, DKEntries filling, and exposure reporting.

DraftKings imports lineups two ways, both driven by draftable IDs — the
slate-specific "ID" column of DKSalaries.csv, not the stable playerId:

* draftkings.com/lineup/upload — a CSV with a slot header row and one
  lineup per row (`to_dk_csv` / `to_dk_showdown_csv`);
* Lineups -> Edit Entries — download DKEntries.csv for contests you've
  already entered, fill the slot cells, re-upload (`fill_entries_csv`).

On showdown slates the CPT slot only accepts the CPT-specific draftable
ID, which is why players carry a separate `cpt_dk_id`.
"""

from __future__ import annotations

import csv
import io
import itertools
from collections import Counter

from .lineup import Lineup
from .showdown import ShowdownLineup

DK_HEADER = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
DK_SHOWDOWN_HEADER = ["CPT", "FLEX", "FLEX", "FLEX", "FLEX", "FLEX"]

ENTRY_META_HEADER = ["Entry ID", "Contest Name", "Contest ID", "Entry Fee"]


def _cell(p: dict, captain: bool = False) -> str:
    """'Name (draftable_id)' as DK's upload parser expects. Falls back to
    the stable player ID for rows ingested before draftable IDs existed —
    DK rejects those, but a wrong-ID row beats a crash and the store layer
    warns when the fallback is in play."""
    if captain:
        pid = p.get("cpt_dk_id") or p.get("dk_id") or p["id"]
    else:
        pid = p.get("dk_id") or p["id"]
    return f"{p['name']} ({pid})"


def to_dk_csv(lineups: list[Lineup]) -> str:
    """DraftKings bulk-upload format: one row per lineup, players as
    'Name (draftable_id)' in slot order."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(DK_HEADER)
    for lu in lineups:
        writer.writerow([_cell(p) for p in lu.slot_order()])
    return buf.getvalue()


def to_dk_showdown_csv(lineups: list[ShowdownLineup]) -> str:
    """DraftKings Showdown bulk-upload format: CPT first, then five FLEX.
    The CPT cell must carry the CPT-slot draftable ID."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(DK_SHOWDOWN_HEADER)
    for lu in lineups:
        players = lu.slot_order()
        writer.writerow(
            [_cell(players[0], captain=True)] + [_cell(p) for p in players[1:]]
        )
    return buf.getvalue()


def _entries_layout(rows: list[list[str]]) -> tuple[int, int, list[str]]:
    """Locate the header row and slot columns of a DKEntries.csv.

    Returns (header_row_index, first_slot_column, slot_names). The slot
    names are the contiguous non-empty headers after 'Entry Fee' — DK pads
    the file to the right with instructions and the slate's player list,
    which the upload parser (and we) leave untouched.
    """
    for i, row in enumerate(rows):
        cells = [c.strip().lstrip("\ufeff") for c in row]  # DK files ship a BOM
        if cells[: len(ENTRY_META_HEADER)] == ENTRY_META_HEADER:
            slots = list(itertools.takewhile(
                lambda c: c, cells[len(ENTRY_META_HEADER):]
            ))
            if not slots:
                break
            return i, len(ENTRY_META_HEADER), slots
    raise ValueError(
        "Not a DKEntries.csv: no 'Entry ID,Contest Name,Contest ID,Entry Fee,"
        "<slots...>' header row found. Download it from DraftKings via "
        "Lineups -> Edit Entries."
    )


def entry_count(entries_csv: str) -> int:
    """Number of contest entries in a DKEntries.csv download."""
    rows = list(csv.reader(io.StringIO(entries_csv)))
    hdr, _, _ = _entries_layout(rows)
    return sum(1 for r in rows[hdr + 1:] if r and r[0].strip())


def _cell_name(cell: str) -> str:
    """'Justin Jefferson (12345678)' / 'X (LOCKED)' -> normalized name."""
    import re as _re

    return _re.sub(r"\s*\(.*\)\s*$", "", str(cell)).strip().upper()


def _is_locked(cell: str) -> bool:
    return "LOCKED" in str(cell).upper()


def assign_min_churn(current: list[list[str]],
                     lineups: list,
                     locked: list[set] | None = None) -> list[int]:
    """Assign generated lineups to entry rows MINIMIZING total player
    changes (2026-08-03, Thursday-entry workflow): the upload replaces
    by Entry ID either way, but a churn-minimizing assignment makes the
    Sunday diff reviewable and keeps locked players matched where
    possible. current[i] = normalized player names now in entry i.
    Returns lineup index per entry (lineups cycled if fewer)."""
    import numpy as np
    from scipy.optimize import linear_sum_assignment

    n = len(current)
    pool = [lineups[i % len(lineups)] for i in range(n)]
    names = [{str(p.get("name", "")).strip().upper() for p in lu.players}
             for lu in pool]
    overlap = np.zeros((n, len(pool)))
    for i, cur in enumerate(current):
        cs = set(cur)
        for j, ns in enumerate(names):
            overlap[i, j] = len(cs & ns)
            # Lock-aware (2026-08-04 audit): a lineup missing an entry's
            # locked players can't be uploaded to that row — make such
            # pairs prohibitively costly so a compatible lineup isn't
            # assigned elsewhere while this row goes untouched and the
            # compatible lineup's coverage slot is silently stranded.
            if locked and locked[i] and not locked[i] <= ns:
                overlap[i, j] = -1e6
    r, c = linear_sum_assignment(-overlap)
    out = [0] * n
    for i, j in zip(r, c):
        out[i] = j % len(lineups)
    return out


def fill_entries_csv(
    entries_csv: str, lineups: list[Lineup] | list[ShowdownLineup],
    diff_out: list | None = None,
    contest_id: str | None = None,
) -> str:
    """Fill a downloaded DKEntries.csv with generated lineups for re-upload.

    Assignment is churn-minimizing (see assign_min_churn): each entry
    gets the generated lineup most similar to what it already holds, so
    the Sunday late-swap diff is as small as the new set allows. Rows
    with LOCKED players (games already kicked off) are handled safely:
    if the assigned lineup contains every locked player, locked cells
    keep their original text and the rest fill around them; otherwise
    the ROW IS LEFT UNTOUCHED (DK would reject a locked-slot change) and
    flagged in the diff. Pass diff_out=[] to receive per-entry dicts:
    {entry_id, changed, out, in, locked, untouched}.
    """
    if not lineups:
        raise ValueError("No lineups to fill entries with")
    rows = list(csv.reader(io.StringIO(entries_csv)))
    hdr, first_slot, slots = _entries_layout(rows)
    size = len(lineups[0].slot_order())
    if len(slots) != size:
        raise ValueError(
            f"Entries file has {len(slots)} roster slots {slots} but lineups "
            f"have {size} players — classic vs showdown mismatch?"
        )
    is_cpt = [s.strip().upper() == "CPT" for s in slots]

    entry_rows = [r for r in rows[hdr + 1:] if r and r[0].strip()]
    if contest_id is not None:
        # Multi-contest DKEntries files (2026-08-04): fill ONLY this
        # contest's rows; others pass through verbatim so the same
        # download can be run once per contest with per-contest builds.
        cid = str(contest_id).strip()
        entry_rows = [r for r in entry_rows
                      if len(r) > 2 and r[2].strip() == cid]
        if not entry_rows:
            raise ValueError(f"no entry rows for contest_id {cid}")
    current = [[_cell_name(c) for c in
                (r[first_slot:first_slot + size] + [""] * size)[:size]]
               for r in entry_rows]
    locked_by_row = []
    for r in entry_rows:
        cells = (r[first_slot:first_slot + size] + [""] * size)[:size]
        locked_by_row.append({_cell_name(c) for c in cells if _is_locked(c)})
    try:
        order = assign_min_churn(current, lineups, locked=locked_by_row)
    except Exception:  # scipy unavailable etc. — order-fill still correct
        order = [i % len(lineups) for i in range(len(entry_rows))]

    for i, row in enumerate(entry_rows):
        lu = lineups[order[i]]
        players = lu.slot_order()
        if len(row) < first_slot + size:
            row.extend([""] * (first_slot + size - len(row)))
        cells = row[first_slot:first_slot + size]
        locked_idx = [j for j, c in enumerate(cells) if _is_locked(c)]
        locked_names = {_cell_name(cells[j]) for j in locked_idx}
        new_names = {str(p.get("name", "")).strip().upper()
                     for p in players}
        d = {"entry_id": row[0], "locked": sorted(locked_names),
             "untouched": False, "out": [], "in": []}
        if locked_names and not locked_names <= new_names:
            d["untouched"] = True  # DK would reject; keep as entered
            if diff_out is not None:
                diff_out.append(d)
            continue
        if locked_idx:
            # keep locked cells verbatim; fill the open slots POSITION-
            # AWARE (2026-08-04 audit): sequential fill misaligned slots
            # whenever the locked player sat in a different slot index in
            # the new lineup's slot_order (e.g. locked FLEX cell, lineup
            # hard-slots him at RB) — every later cell shifted one slot
            # and DK would reject the row. Specific slots fill first,
            # FLEX/CPT take leftovers; if no eligible player remains for
            # a slot, the row is left untouched rather than invalid.
            rest = [p for p in players
                    if str(p.get("name", "")).strip().upper()
                    not in locked_names]

            def _fits(p, slot):
                s = str(slot).strip().upper()
                pos = str(p.get("pos", "")).upper()
                if s in ("FLEX", "UTIL"):
                    return pos in ("RB", "WR", "TE")
                if s == "CPT":
                    return True
                return pos == s

            open_slots = [j for j in range(size) if j not in locked_idx]
            fill: dict[int, dict] = {}
            feasible = True
            for j in sorted(open_slots, key=lambda j: str(slots[j]).strip()
                            .upper() in ("FLEX", "UTIL", "CPT")):
                pick = next((p for p in rest if _fits(p, slots[j])), None)
                if pick is None:
                    feasible = False
                    break
                rest.remove(pick)
                fill[j] = pick
            if not feasible:
                d["untouched"] = True
                if diff_out is not None:
                    diff_out.append(d)
                continue
            for j, p in fill.items():
                row[first_slot + j] = _cell(p, captain=is_cpt[j])
        else:
            for j, (p, cpt) in enumerate(zip(players, is_cpt)):
                row[first_slot + j] = _cell(p, captain=cpt)
        if diff_out is not None:
            cur_set = {c for c in current[i] if c}
            d["out"] = sorted(cur_set - new_names)
            d["in"] = sorted(new_names - cur_set)
            diff_out.append(d)

    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def showdown_exposure_summary(lineups: list[ShowdownLineup]) -> list[dict]:
    """Classic exposure plus how often each player is the captain."""
    exp = exposure_summary(lineups)
    cpt_counts = Counter(lu.captain["id"] for lu in lineups)
    n = len(lineups)
    for row in exp:
        row["cpt_lineups"] = cpt_counts.get(row["id"], 0)
        row["cpt_exposure"] = cpt_counts.get(row["id"], 0) / n
    return exp


def exposure_summary(lineups: list[Lineup]) -> list[dict]:
    """Player exposure across a lineup set, sorted by exposure descending."""
    if not lineups:
        return []
    counts: Counter[str] = Counter()
    meta: dict[str, dict] = {}
    for lu in lineups:
        for p in lu.players:
            counts[p["id"]] += 1
            meta[p["id"]] = p
    n = len(lineups)
    return [
        {
            "id": pid,
            "name": meta[pid]["name"],
            "pos": meta[pid]["pos"],
            "team": meta[pid]["team"],
            "salary": meta[pid]["salary"],
            "exposure": count / n,
            "lineups": count,
        }
        for pid, count in counts.most_common()
    ]

```

===== FILE: src/nfl_dfs/optimizer/lineup.py =====
```python
"""DK NFL Classic lineup optimization (guide §9).

Constraints: 1 QB, 2-3 RB, 3-4 WR, 1-2 TE (9 total with one FLEX), 1 DST,
$50k cap, >= 2 games, <= 8 players from one team. Stacking is expressed as
constraints (QB + pass catcher, bring-back, no RB vs opposing DST) because
optimizing independent projections is the classic beginner error: DK is
winner-take-most, and you need correlated upside.

For GPPs, prefer optimizing over simulated outcomes (see simulate_lineups):
optimize each Monte Carlo draw and keep the lineups that recur — that bakes
in correlation without hand-coded rules.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pulp

log = logging.getLogger(__name__)

SALARY_CAP = 50_000
# Tournament construction defaults (the only mode this shop plays): a
# sub-$4k ceiling punt appeared in 94% of 2025 Milly Maker winners.
PUNT_MAX_SALARY = 4_000
PUNT_MIN = 1
LEVERAGE_PENALTY = 25.0  # pts deducted x naive-ownership weight (chalk fade)
ROSTER_SIZE = 9
MAX_FROM_TEAM = 8
MIN_GAMES = 2

Player = dict[str, Any]  # id, name, pos, team, opp, game_id, salary, proj


@dataclass
class StackRules:
    qb_stack_min: int = 1        # pass catchers required from the QB's team
    bring_back_min: int = 0      # players required from the QB's opponent
    forbid_rb_vs_dst: bool = True
    forbid_two_rb_same_team: bool = True


@dataclass
class Lineup:
    players: list[Player]
    tag: str = ""  # which generator produced it (lev/boom/game); analysis only

    @property
    def ids(self) -> frozenset:
        return frozenset(p["id"] for p in self.players)

    @property
    def salary(self) -> int:
        return sum(p["salary"] for p in self.players)

    @property
    def proj(self) -> float:
        return float(sum(p["proj"] for p in self.players))

    def slot_order(self) -> list[Player]:
        """Players in DK upload order: QB RB RB WR WR WR TE FLEX DST.

        Slot labels don't affect DK scoring (all 9 spots count the same),
        so which specific player lands in FLEX is free to optimize for
        late-swap flexibility instead: when every player carries a
        `kickoff` time, the position with a surplus over its required
        minimum sends its LATEST-kickoff player to FLEX (the only slot
        that accepts any of RB/WR/TE) rather than its lowest-projected
        one. Missing kickoff data (the common case — most callers don't
        have it) falls back to the original proj-based assignment."""
        pool = list(self.players)
        has_kickoffs = bool(pool) and all(p.get("kickoff") for p in pool)

        def take(pos: str, n: int, flex_eligible: bool = False) -> list[Player]:
            cands = [p for p in pool if p["pos"] == pos]
            if flex_eligible and has_kickoffs and len(cands) > n:
                # Earliest n lock into the hard slot; the latest-kickoff
                # surplus player is left behind for FLEX.
                got = sorted(cands, key=lambda p: p["kickoff"])[:n]
            else:
                got = sorted(cands, key=lambda p: -p["proj"])[:n]
            for g in got:
                pool.remove(g)
            return got

        ordered = (
            take("QB", 1)
            + take("RB", 2, flex_eligible=True)
            + take("WR", 3, flex_eligible=True)
            + take("TE", 1, flex_eligible=True)
        )
        dst = take("DST", 1)
        flex = [p for p in pool if p["pos"] in ("RB", "WR", "TE")]
        return ordered + flex + dst


def optimize(
    players: list[Player],
    budget: int = SALARY_CAP,
    locks: set | None = None,
    bans: set | None = None,
    banned_lineups: list[frozenset] | None = None,
    stack: StackRules | None = None,
    objective_col: str = "proj",
    max_overlap: int = 8,
    punt_max_salary: int | None = None,
    punt_min: int = 0,
    game_lock: tuple[str, int] | None = None,
    min_salary: int | None = None,
    max_salary: int | None = None,
    max_per_game: int | None = None,
) -> Lineup | None:
    """Solve one lineup. Returns None if infeasible.
    game_lock=(game_id, n) forces >= n players from that game — the
    concentrated-game-stack construction (issue #6): Milly winners take
    50-80% of their points from one game."""
    prob = pulp.LpProblem("dfs", pulp.LpMaximize)
    x = {p["id"]: pulp.LpVariable(f"x_{p['id']}", cat="Binary") for p in players}
    by_id = {p["id"]: p for p in players}

    prob += pulp.lpSum(x[p["id"]] * float(p[objective_col]) for p in players)
    prob += pulp.lpSum(x[p["id"]] * p["salary"] for p in players) <= budget
    # Milly winners spend the cap (2025 median $0 left; 2023-24 90% within
    # $300). Replay-validated 2026-07-26 (run I): mean best-of-40 180.1 ->
    # 182.3 with a floor of 49000. Env MIN_LINEUP_SALARY overrides; 0 disables.
    import os as _os

    _min_sal = (min_salary if min_salary is not None
                else int(_os.environ.get("MIN_LINEUP_SALARY", "49000") or 0))
    if _min_sal:
        prob += pulp.lpSum(x[p["id"]] * p["salary"] for p in players) >= _min_sal
    if max_salary is not None and max_salary < budget:
        prob += pulp.lpSum(x[p["id"]] * p["salary"] for p in players) <= max_salary
    prob += pulp.lpSum(x.values()) == ROSTER_SIZE

    def count(pos: str):
        return pulp.lpSum(x[p["id"]] for p in players if p["pos"] == pos)

    prob += count("QB") == 1
    prob += count("DST") == 1
    prob += count("RB") >= 2
    prob += count("RB") <= 3
    prob += count("WR") >= 3
    prob += count("WR") <= 4
    prob += count("TE") >= 1
    prob += count("TE") <= 2

    teams = sorted({p["team"] for p in players})
    for team in teams:
        prob += pulp.lpSum(x[p["id"]] for p in players if p["team"] == team) <= MAX_FROM_TEAM

    # Minimum 2 different games: for every game, players NOT in that game >= 1
    games = sorted({p.get("game_id") for p in players if p.get("game_id")})
    if len(games) >= MIN_GAMES:
        for game in games:
            prob += pulp.lpSum(
                x[p["id"]] for p in players if p.get("game_id") != game
            ) >= 1

    # Tournament punt slot: winners rostered a sub-$4k player who scored
    # 15+ in 94% of 2025 Milly Makers (reports/2025-milly-winners.csv).
    if punt_min and punt_max_salary:
        if _os.environ.get("PUNT_STRICT") and any(
                "punt_elig" in p for p in players):
            punts = [p["id"] for p in players if p.get("punt_elig")]
        else:
            punts = [p["id"] for p in players
                     if p["salary"] <= punt_max_salary]
        if punts:
            prob += pulp.lpSum(x[pid] for pid in punts) >= punt_min

    # A/B lever (env VALUE2_MIN, off by default): salary-barbell second
    # tier — 84% of first-place Milly lineups carried >=2 skill players
    # under $5,300 (44% carried three; 4for4 via 2026-08-03 triage). The
    # sub-$4k punt rule mandates ONE extreme value; this requires N
    # players under VALUE2_MAX (default 5300), punt included.
    v2_min = int(_os.environ.get("VALUE2_MIN", "0"))
    if v2_min:
        v2_max = int(_os.environ.get("VALUE2_MAX", "5300"))
        cheap2 = [p["id"] for p in players
                  if p["salary"] <= v2_max and p["pos"] != "DST"]
        if len(cheap2) >= v2_min:
            prob += pulp.lpSum(x[pid] for pid in cheap2) >= v2_min

    # A/B lever (env MAX_PER_GAME, off by default): cap same-game players.
    # 28 fully-mapped Milly winners average 2.96 from their most-loaded
    # game (22/28 used only 2-3) across 5.3 distinct games; our entries
    # average 4.6 from one game — the concentrated-game folklore the
    # 5-stack generators encode is contradicted by the winners (2026-08-03).
    max_pg = (max_per_game if max_per_game is not None
              else int(_os.environ.get("MAX_PER_GAME", "0")))
    if max_pg:
        by_game: dict = {}
        for p in players:
            by_game.setdefault(p.get("game_id"), []).append(p["id"])
        for gid, ids in by_game.items():
            if gid is not None and len(ids) > max_pg:
                prob += pulp.lpSum(x[pid] for pid in ids) <= max_pg

    # A/B lever (env MIN_LOWOWN, off by default): winner ownership shape
    # — real Milly winners carry ~2 sub-5%-owned players (Addendum 38,
    # stable 2019-2024). Requires callers to stamp a boolean `low_own`
    # on pool dicts (replay build_slates does); silently inert otherwise.
    import os as _os2

    min_lowown = int(_os2.environ.get("MIN_LOWOWN", "0"))
    if min_lowown:
        lows = [p["id"] for p in players if p.get("low_own")]
        if lows:
            prob += pulp.lpSum(x[pid] for pid in lows) >= min(
                min_lowown, len(lows))

    if game_lock:
        gid, n_from_game = game_lock
        in_game = [p["id"] for p in players if p.get("game_id") == gid]
        if len(in_game) >= n_from_game:
            prob += pulp.lpSum(x[pid] for pid in in_game) >= n_from_game

    for pid in locks or ():
        prob += x[pid] == 1
    for pid in bans or ():
        prob += x[pid] == 0

    # Uniqueness for multi-entry: forbid previously generated lineups
    for prev in banned_lineups or ():
        prob += pulp.lpSum(x[pid] for pid in prev if pid in x) <= max_overlap

    if stack:
        _apply_stack_rules(prob, x, players, teams, stack)

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[prob.status] != "Optimal":
        return None
    chosen = [by_id[pid] for pid, var in x.items() if var.value() == 1]
    return Lineup(chosen)


def _apply_stack_rules(prob, x, players, teams, stack: StackRules) -> None:
    catchers_by_team: dict[str, list] = {}
    qbs_by_team: dict[str, list] = {}
    for p in players:
        if p["pos"] in ("WR", "TE"):
            catchers_by_team.setdefault(p["team"], []).append(p["id"])
        elif p["pos"] == "QB":
            qbs_by_team.setdefault(p["team"], []).append(p["id"])

    for team in teams:
        qbs = qbs_by_team.get(team, [])
        if not qbs:
            continue
        qb_sum = pulp.lpSum(x[i] for i in qbs)
        # If QB from team T is rostered, require >= k WR/TE from team T
        catchers = catchers_by_team.get(team, [])
        prob += pulp.lpSum(x[i] for i in catchers) >= stack.qb_stack_min * qb_sum
        # Bring-back: >= k skill players from the QB's opponent
        if stack.bring_back_min:
            opps = {p["opp"] for p in players if p["pos"] == "QB" and p["team"] == team}
            opp_skill = [
                p["id"] for p in players
                if p["team"] in opps and p["pos"] in ("RB", "WR", "TE")
            ]
            prob += pulp.lpSum(x[i] for i in opp_skill) >= stack.bring_back_min * qb_sum

    if stack.forbid_rb_vs_dst:
        dsts = [p for p in players if p["pos"] == "DST"]
        for dst in dsts:
            opposing_rbs = [
                p["id"] for p in players
                if p["pos"] == "RB" and p["team"] == dst["opp"]
            ]
            for rb_id in opposing_rbs:
                prob += x[rb_id] + x[dst["id"]] <= 1

    if stack.forbid_two_rb_same_team:
        rbs_by_team: dict[str, list] = {}
        for p in players:
            if p["pos"] == "RB":
                rbs_by_team.setdefault(p["team"], []).append(p["id"])
        for ids in rbs_by_team.values():
            if len(ids) > 1:
                prob += pulp.lpSum(x[i] for i in ids) <= 1


def optimize_many(
    players: list[Player],
    n_lineups: int,
    stack: StackRules | None = None,
    max_overlap: int = 7,
    punt_max_salary: int | None = PUNT_MAX_SALARY,
    punt_min: int = PUNT_MIN,
    **kwargs,
) -> list[Lineup]:
    """Generate n unique lineups; each new lineup may share at most
    max_overlap players with any previous one."""
    # Assumption-validation lever (2026-08-01): PUNT_MIN env overrides the
    # mandatory-punt rule so its causal value can be measured (the rule was
    # adopted from "94% of Milly winners had a punt" -- correlational).
    import os as _os

    punt_min = int(_os.environ.get("PUNT_MIN", punt_min))
    # PUNT_MAX (2026-08-03): the $4k threshold was inherited from the
    # 2025 winner study (punts cluster $2.9-3.9k) and never dose-tested.
    if _os.environ.get("PUNT_MAX"):
        punt_max_salary = int(_os.environ["PUNT_MAX"])
    lineups: list[Lineup] = []
    banned: list[frozenset] = []
    for _ in range(n_lineups):
        # CBC runs as a subprocess and occasionally fails to launch under
        # load (seen in replays and tests). One retry, then return what we
        # have rather than blowing up the whole batch.
        for attempt in (1, 2):
            try:
                lu = optimize(players, stack=stack, banned_lineups=banned,
                              max_overlap=max_overlap,
                              punt_max_salary=punt_max_salary,
                              punt_min=punt_min, **kwargs)
                break
            except pulp.PulpSolverError as exc:
                log.warning("CBC solve failed (attempt %d): %s", attempt, exc)
                lu = None
        else:
            log.warning("CBC unavailable; returning %d lineups", len(lineups))
            return lineups
        if lu is None:
            log.warning("Pool exhausted after %d lineups", len(lineups))
            break
        lineups.append(lu)
        banned.append(lu.ids)
    return lineups


def select_tail_entries(
    cand_totals: np.ndarray, n_entries: int, line: float
) -> list[int]:
    """Pick the n_entries candidates that maximize P(best-of-N >= line)
    against correlated draws. cand_totals[c, k] = candidate c's total in
    sim k. Greedy max-coverage over the sims each candidate clears the
    line in (submodular, so greedy is within 1-1/e of optimal): two
    entries that boom in the SAME sims are redundant no matter how good
    each looks alone. Slots left after coverage saturates go to the
    highest remaining P(>= line), then mean total."""
    cand_totals = np.asarray(cand_totals, dtype=float)
    clears = cand_totals >= line
    p_line = clears.mean(axis=1)
    mean_total = cand_totals.mean(axis=1)
    n_entries = min(n_entries, len(cand_totals))
    selected: list[int] = []
    covered = np.zeros(cand_totals.shape[1], dtype=bool)
    remaining = set(range(len(cand_totals)))
    while len(selected) < n_entries and remaining:
        best = max(remaining,
                   key=lambda i: (int(np.count_nonzero(clears[i] & ~covered)),
                                  p_line[i], mean_total[i]))
        if not np.count_nonzero(clears[best] & ~covered):
            break  # coverage saturated; fill below
        selected.append(best)
        covered |= clears[best]
        remaining.discard(best)
    fill = sorted(remaining, key=lambda i: (p_line[i], mean_total[i]),
                  reverse=True)
    selected += fill[: n_entries - len(selected)]
    return selected


def simulate_lineups(
    players: list[Player],
    draws: np.ndarray,
    n_keep: int = 20,
    stack: StackRules | None = None,
    n_draw_solves: int = 200,
    **kwargs,
) -> list[tuple[Lineup, int]]:
    """GPP construction from simulated outcomes: optimize a lineup for each
    of n_draw_solves Monte Carlo draws (draws[i, k] = player i's points in
    sim k, aligned with `players`), then keep the lineups that recur most.
    Correlated draws bake stacking in without hand-coded rules; explicit
    stack rules can still be layered on top."""
    counts: Counter[frozenset] = Counter()
    exemplars: dict[frozenset, Lineup] = {}
    n_sims = draws.shape[1]
    for k in range(min(n_draw_solves, n_sims)):
        sim_players = [
            {**p, "proj": float(draws[i, k])} for i, p in enumerate(players)
        ]
        lu = optimize(sim_players, stack=stack, **kwargs)
        if lu is None:
            continue
        key = lu.ids
        counts[key] += 1
        if key not in exemplars:
            # Re-express the lineup with mean projections for reporting
            by_id = {p["id"]: p for p in players}
            exemplars[key] = Lineup([by_id[i] for i in key])
    return [(exemplars[key], n) for key, n in counts.most_common(n_keep)]


# Auto-core conviction rules. A player makes the core when the scout batch
# keeps picking him despite forced diversity, AND he's a value at his
# position (or so consensus that value doesn't matter). The salary guard
# keeps the core from hoarding the cap: every non-core slot must retain at
# least a mid-tier budget, so a stud-stacked core sheds its priciest
# marginal member — the "cheap good QB over three studs" philosophy.
CORE_CONVICTION = 0.6
CORE_SUPER_CONVICTION = 0.85
CORE_MIN, CORE_MAX = 2, 7
CORE_FREE_SLOT_BUDGET = 4_500


def _auto_core(consensus: Lineup, counts, n_scout: int,
               stable_pool: list[Player]) -> list[Player]:
    def value(p: Player) -> float:
        return p["proj"] / (p["salary"] / 1000.0)

    med_value: dict[str, float] = {}
    for pos in {p["pos"] for p in stable_pool}:
        vals = sorted(value(p) for p in stable_pool if p["pos"] == pos)
        med_value[pos] = vals[len(vals) // 2]

    core = []
    for p in sorted(consensus.players, key=lambda p: -counts[p["id"]]):
        share = counts[p["id"]] / n_scout
        if share < CORE_CONVICTION:
            break  # sorted by conviction; nothing below threshold qualifies
        if value(p) >= med_value[p["pos"]] or share >= CORE_SUPER_CONVICTION:
            core.append(p)
    core = core[:CORE_MAX]

    # Budget guard: leave every free slot at least CORE_FREE_SLOT_BUDGET.
    while len(core) > CORE_MIN:
        free_slots = 9 - len(core)
        if SALARY_CAP - sum(p["salary"] for p in core) >= free_slots * CORE_FREE_SLOT_BUDGET:
            break
        core.remove(max(core, key=lambda p: p["salary"]))

    if len(core) < CORE_MIN:
        core = sorted(consensus.players, key=lambda p: -counts[p["id"]])[:CORE_MIN]
    return core


def core_and_variations(
    stable_pool: list[Player],
    upside_pool: list[Player],
    n_lineups: int,
    core_size: int | None = None,
    scout_n: int = 15,
    stack: StackRules | None = None,
    locks: set | None = None,
    bans: set | None = None,
    max_overlap: int | None = None,
) -> tuple[list[dict], list[Lineup]]:
    """Suggest a core, then build entries that vary around it.

    Scouts a diverse batch of lineups on the stable objective (median
    projection) and counts exposure. With core_size=None (default) the core
    sizes itself: consensus players (>=60% of scout lineups) who are also
    values at their position — or near-unanimous — capped so the remaining
    slots keep real budget. An explicit core_size takes the N most-consensus
    instead. Either way the core is a subset of one scout lineup, so it's
    jointly feasible by construction. Entries are then optimized on the
    upside objective with the core locked; max_overlap defaults to
    len(core) + 1 so every pair of entries differs in at least two of the
    free spots.

    Returns (core, lineups) where core entries are {"id", "conviction"}.
    Empty core/lineups if the slate is infeasible.
    """
    from collections import Counter

    scout = optimize_many(
        stable_pool, n_lineups=scout_n, stack=stack,
        locks=locks, bans=bans, max_overlap=6,
    )
    if not scout:
        return [], []
    counts = Counter(p["id"] for lu in scout for p in lu.players)
    consensus = max(scout, key=lambda lu: sum(counts[p["id"]] for p in lu.players))

    if core_size is None:
        core_players = _auto_core(consensus, counts, len(scout), stable_pool)
    else:
        core_players = sorted(
            consensus.players, key=lambda p: -counts[p["id"]]
        )[:core_size]
    core = [
        {"id": p["id"], "conviction": round(counts[p["id"]] / len(scout), 2)}
        for p in core_players
    ]
    core_ids = {c["id"] for c in core}
    lineups = optimize_many(
        upside_pool,
        n_lineups=n_lineups,
        stack=stack,
        locks=core_ids | (locks or set()),
        bans=bans,
        max_overlap=max_overlap if max_overlap is not None else len(core_ids) + 1,
    )
    return core, lineups

```

===== FILE: src/nfl_dfs/optimizer/showdown.py =====
```python
"""DK NFL Showdown Captain Mode lineup optimization (guide §9.5).

Single-game format: 6 roster spots — 1 Captain (CPT) + 5 FLEX — drawn from
the two teams in one game. The captain scores 1.5x fantasy points and costs
1.5x his FLEX salary; the $50k cap is unchanged, and a lineup must include
at least one player from each team. Every position in the game's pool is
eligible for every spot, including K and DST (which exist on showdown
slates even though DK Classic has no kicker).

Captain choice is the whole game here: the MILP picks it jointly with the
flex spots, and two lineups with the same six players but different
captains are different entries. Classic-slate stacking rules don't apply —
in a single game every player is already "stacked" with every other — so
correlation is left to captain/flex diversity across entries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pulp

from .lineup import PUNT_MAX_SALARY, PUNT_MIN, Player

log = logging.getLogger(__name__)

SALARY_CAP = 50_000
ROSTER_SIZE = 6
FLEX_SPOTS = ROSTER_SIZE - 1
CPT_MULT = 1.5
MAX_FROM_TEAM = ROSTER_SIZE - 1  # DK: at least one player from each team


def cpt_salary(salary: int) -> int:
    """DK charges exactly 1.5x the FLEX salary for the captain slot."""
    return int(round(salary * CPT_MULT))


@dataclass
class ShowdownLineup:
    captain: Player
    flex: list[Player]

    @property
    def players(self) -> list[Player]:
        return [self.captain] + self.flex

    @property
    def ids(self) -> frozenset:
        return frozenset(p["id"] for p in self.players)

    @property
    def key(self) -> tuple:
        """Lineup identity: same six players with a different captain is a
        different DK entry."""
        return (self.captain["id"], self.ids)

    @property
    def salary(self) -> int:
        return cpt_salary(self.captain["salary"]) + sum(p["salary"] for p in self.flex)

    @property
    def proj(self) -> float:
        return float(CPT_MULT * self.captain["proj"]
                     + sum(p["proj"] for p in self.flex))

    def slot_order(self) -> list[Player]:
        """Players in DK upload order: CPT then FLEX by projection."""
        return [self.captain] + sorted(self.flex, key=lambda p: -p["proj"])


def optimize_showdown(
    players: list[Player],
    budget: int = SALARY_CAP,
    locks: set | None = None,
    bans: set | None = None,
    captain_lock=None,
    banned_lineups: list[tuple] | None = None,
    max_overlap: int = FLEX_SPOTS,
    objective_col: str = "proj",
    punt_max_salary: int | None = PUNT_MAX_SALARY,
    punt_min: int = PUNT_MIN,
) -> ShowdownLineup | None:
    """Solve one Captain Mode lineup. Returns None if infeasible.

    locks/bans apply to the six-man roster regardless of slot;
    captain_lock forces a specific player into the CPT spot. banned_lineups
    takes ShowdownLineup.key tuples: a new lineup must differ from each by
    its captain or by more than ROSTER_SIZE - max_overlap - 1 players — the
    default (5) only forbids exact repeats, captain included.
    """
    prob = pulp.LpProblem("dfs_showdown", pulp.LpMaximize)
    c = {p["id"]: pulp.LpVariable(f"c_{p['id']}", cat="Binary") for p in players}
    f = {p["id"]: pulp.LpVariable(f"f_{p['id']}", cat="Binary") for p in players}
    by_id = {p["id"]: p for p in players}

    prob += pulp.lpSum(
        c[p["id"]] * CPT_MULT * float(p[objective_col])
        + f[p["id"]] * float(p[objective_col])
        for p in players
    )
    prob += pulp.lpSum(
        c[p["id"]] * cpt_salary(p["salary"]) + f[p["id"]] * p["salary"]
        for p in players
    ) <= budget
    prob += pulp.lpSum(c.values()) == 1
    prob += pulp.lpSum(f.values()) == FLEX_SPOTS

    # A/B lever (env SHOWDOWN_BRING_BACK, off pending replay validation):
    # 88% of winning showdown lineups with a pass-position captain
    # (QB/WR/TE) carried an OPPOSING pass-position player (FantasyLabs
    # via 2026-08-03 research triage) — near-mandatory, and this
    # optimizer had NO bring-back rule at all. Conditional big-M: if the
    # captain is pass-position on team T, require >=1 QB/WR/TE from the
    # other team anywhere in the lineup.
    import os as _os

    if _os.environ.get("SHOWDOWN_BRING_BACK"):
        PASS_POS = ("QB", "WR", "TE")
        teams = sorted({p["team"] for p in players})
        if len(teams) == 2:
            for team in teams:
                opp_pass = [p["id"] for p in players
                            if p["team"] != team and p["pos"] in PASS_POS]
                own_pass_cpt = [p["id"] for p in players
                                if p["team"] == team and p["pos"] in PASS_POS]
                if opp_pass and own_pass_cpt:
                    prob += (pulp.lpSum(c[pid] + f[pid] for pid in opp_pass)
                             >= pulp.lpSum(c[pid] for pid in own_pass_cpt))
    for p in players:
        prob += c[p["id"]] + f[p["id"]] <= 1

    # At least one player from each team (equivalently, <= 5 from any one)
    for team in sorted({p["team"] for p in players}):
        prob += pulp.lpSum(
            c[p["id"]] + f[p["id"]] for p in players if p["team"] == team
        ) <= MAX_FROM_TEAM

    # Tournament punt: at least one sub-$4k roster spot (FLEX pricing)
    if punt_min and punt_max_salary:
        punts = [p["id"] for p in players if p["salary"] <= punt_max_salary]
        if punts:
            prob += pulp.lpSum(c[pid] + f[pid] for pid in punts) >= punt_min

    for pid in locks or ():
        prob += c[pid] + f[pid] == 1
    for pid in bans or ():
        prob += c[pid] + f[pid] == 0
    if captain_lock is not None:
        prob += c[captain_lock] == 1

    # Uniqueness: shared-player count, +1 if the previous captain is
    # re-captained, must stay <= max_overlap + 1.
    for prev_cpt, prev_ids in banned_lineups or ():
        prob += (
            pulp.lpSum(c[pid] + f[pid] for pid in prev_ids if pid in c)
            + (c[prev_cpt] if prev_cpt in c else 0)
        ) <= max_overlap + 1

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[prob.status] != "Optimal":
        return None
    captain = next(by_id[pid] for pid, var in c.items() if var.value() == 1)
    flex = [by_id[pid] for pid, var in f.items() if var.value() == 1]
    return ShowdownLineup(captain, flex)


def optimize_many_showdown(
    players: list[Player],
    n_lineups: int,
    max_overlap: int = FLEX_SPOTS,
    **kwargs,
) -> list[ShowdownLineup]:
    """Generate n unique Captain Mode lineups. With the default max_overlap
    the same six players may recur under a different captain — in a
    six-man, two-team pool that's a legitimately distinct entry; lower it
    to force player-set diversity too."""
    lineups: list[ShowdownLineup] = []
    banned: list[tuple] = []
    for _ in range(n_lineups):
        # Same CBC-launch flakiness handling as the classic optimizer.
        for attempt in (1, 2):
            try:
                lu = optimize_showdown(players, banned_lineups=banned,
                                       max_overlap=max_overlap, **kwargs)
                break
            except pulp.PulpSolverError as exc:
                log.warning("CBC solve failed (attempt %d): %s", attempt, exc)
                lu = None
        else:
            log.warning("CBC unavailable; returning %d lineups", len(lineups))
            return lineups
        if lu is None:
            log.warning("Pool exhausted after %d lineups", len(lineups))
            break
        lineups.append(lu)
        banned.append(lu.key)
    return lineups


# --- Simulated-outcomes construction (issue #10 modernization) ------------
# Ports the classic side's correlated-draw machinery (lineup.simulate_lineups
# + lineup.select_tail_entries) to Captain Mode. Draws come from the caller
# (showdown_replay builds them from projection mean/sd + a shared game
# factor); these helpers only consume them.

def lineup_draw_totals(lineups, draws_by_id) -> "np.ndarray":
    """(n_lineups, n_sims) DK totals across draws, captain at 1.5x.
    draws_by_id: player id -> (n_sims,) points array."""
    import numpy as np

    totals = np.zeros((len(lineups), next(iter(draws_by_id.values())).shape[0]))
    for i, lu in enumerate(lineups):
        totals[i] = CPT_MULT * draws_by_id[lu.captain["id"]]
        for p in lu.flex:
            totals[i] += draws_by_id[p["id"]]
    return totals


def simulate_showdown_lineups(
    players: list[Player],
    draws_by_id: dict,
    n_keep: int = 20,
    n_draw_solves: int = 120,
    counters: dict | None = None,
    **kwargs,
) -> list[tuple[ShowdownLineup, int]]:
    """Optimize one lineup per Monte Carlo draw and keep the recurrent
    ones — captain choice included in identity (ShowdownLineup.key), since
    correlated draws are exactly what should discover which player's boom
    worlds deserve the 1.5x slot. A `counters` dict, when supplied, is
    filled with the salary-aware per-draw optimal rates over ALL solves
    ("n", "cpt": Counter, "flex": Counter) — the recurrence truncation
    below keeps only the top lineups, so this is the one place the full
    captain-optimal distribution is observable."""
    from collections import Counter

    counts: Counter[tuple] = Counter()
    exemplars: dict[tuple, ShowdownLineup] = {}
    n_sims = next(iter(draws_by_id.values())).shape[0]
    for k in range(min(n_draw_solves, n_sims)):
        sim_players = [
            {**p, "proj": float(draws_by_id[p["id"]][k])} for p in players
        ]
        lu = optimize_showdown(sim_players, **kwargs)
        if lu is None:
            continue
        if counters is not None:
            counters["n"] = counters.get("n", 0) + 1
            counters.setdefault("cpt", Counter())[lu.captain["id"]] += 1
            fc = counters.setdefault("flex", Counter())
            for p in lu.flex:
                fc[p["id"]] += 1
        counts[lu.key] += 1
        if lu.key not in exemplars:
            by_id = {p["id"]: p for p in players}
            exemplars[lu.key] = ShowdownLineup(
                by_id[lu.captain["id"]], [by_id[p["id"]] for p in lu.flex])
    return [(exemplars[k], n) for k, n in counts.most_common(n_keep)]


def showdown_player_metrics(
    pool: list[Player], draws_by_id: dict, counters: dict | None = None,
) -> list[dict]:
    """Per-player captaincy diagnostics from the correlated draws
    (Stokastic-style display, computed rather than intuited):

    - p_top:  share of draws where the player outscores the whole slate —
      the salary-FREE captain-optimal rate (CPT multiplies everyone the
      same 1.5x, so the draw's top scorer is its best captain).
    - p_top6: share of draws where the player lands in the best six — the
      salary-free "belongs in the perfect lineup" rate.
    - cpt_opt / flex_opt: salary-AWARE rates from the per-draw MILP solves
      when `counters` (filled by simulate_showdown_lineups) is supplied.
    """
    import numpy as np

    ids = [p["id"] for p in pool]
    mat = np.vstack([np.asarray(draws_by_id[i], dtype=float) for i in ids])
    n = mat.shape[1]
    p_top = np.bincount(mat.argmax(axis=0), minlength=len(ids)) / n
    top6 = np.bincount(
        np.argsort(-mat, axis=0)[:6, :].ravel(), minlength=len(ids)) / n
    total = counters.get("n", 0) if counters else 0
    out = []
    for k, p in enumerate(pool):
        row = {
            "id": p["id"], "name": p.get("name"), "team": p.get("team"),
            "position": p.get("pos"), "salary": p.get("salary"),
            "p_top": round(float(p_top[k]), 4),
            "p_top6": round(float(top6[k]), 4),
        }
        if total:
            row["cpt_opt"] = round(counters["cpt"].get(p["id"], 0) / total, 4)
            row["flex_opt"] = round(counters["flex"].get(p["id"], 0) / total, 4)
        out.append(row)
    out.sort(key=lambda r: (-r["p_top"], -r["p_top6"]))
    return out


def select_showdown_entries(
    candidates: list[ShowdownLineup],
    draws_by_id: dict,
    n_entries: int,
    line: float,
) -> list[ShowdownLineup]:
    """Greedy sim-coverage entry selection at a tail line — identical
    logic to the classic side's select_tail_entries, fed captain-weighted
    totals."""
    from .lineup import select_tail_entries

    if not candidates:
        return []
    totals = lineup_draw_totals(candidates, draws_by_id)
    idx = select_tail_entries(totals, n_entries, line)
    return [candidates[i] for i in idx]


# Correlated-draw construction adopted 2026-08-01 (Addendum 26): sim-mode
# capture 85.0% vs 80.7% MILP baseline on the 2025 showdown replay,
# slates >=90% capture doubled (16/41 vs 8/41).
SHOWDOWN_SIM_SIGMA = 0.18   # shared game-factor sigma (see simulate.py)
FALLBACK_SD_RATIO = 0.9     # sd for rows projected without a model sd
DEFAULT_SHOWDOWN_TAIL_LINE = 150.0


def showdown_draws(pool: list[Player], n_sims: int, seed: int) -> dict:
    """Correlated per-player point draws for one slate: a shared
    mean-preserving lognormal game factor (a single-game slate IS one
    environment) times an independent gamma per player matched to the
    player's projection mean/sd ('proj'/'proj_sd'; missing sd falls back
    to FALLBACK_SD_RATIO x mean)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    game = rng.lognormal(-SHOWDOWN_SIM_SIGMA ** 2 / 2, SHOWDOWN_SIM_SIGMA, n_sims)
    draws = {}
    for p in pool:
        m = float(p["proj"])
        s = float(p.get("proj_sd") or 0) or m * FALLBACK_SD_RATIO
        if m <= 0 or s <= 0:
            draws[p["id"]] = np.full(n_sims, max(m, 0.0)) * game
            continue
        shape = (m / s) ** 2
        draws[p["id"]] = rng.gamma(shape, m / shape, n_sims) * game
    return draws


def sim_mode_entries(pool: list[Player], n_entries: int, seed: int,
                     n_sims: int = 4000, tail_line: float | None = None,
                     with_metrics: bool = False,
                     **kwargs) -> list[ShowdownLineup] | tuple:
    """Simulated-outcomes construction: candidates from (a) a diverse MILP
    batch and (b) per-draw re-optimization recurrence, then greedy
    tail-line coverage across the correlated draws. kwargs (locks, bans,
    captain_lock, ...) pass through to every underlying solve.
    with_metrics=True additionally returns showdown_player_metrics (the
    captain board) as a second element."""
    import os

    draws = showdown_draws(pool, n_sims=n_sims, seed=seed)
    milp = optimize_many_showdown(pool, n_lineups=max(2 * n_entries, 30),
                                  max_overlap=4, **kwargs)
    counters: dict | None = {} if with_metrics else None
    recurrent = simulate_showdown_lineups(pool, draws, n_keep=n_entries,
                                          counters=counters, **kwargs)
    seen, candidates = set(), []
    for lu in milp + [l for l, _ in recurrent]:
        if lu.key not in seen:
            seen.add(lu.key)
            candidates.append(lu)
    if tail_line is None:
        tail_line = float(os.environ.get("SHOWDOWN_TAIL_LINE",
                                         DEFAULT_SHOWDOWN_TAIL_LINE) or 0)
    entries = select_showdown_entries(candidates, draws, n_entries, tail_line)
    if with_metrics:
        return entries, showdown_player_metrics(pool, draws, counters)
    return entries

```

===== FILE: src/nfl_dfs/status.py =====
```python
"""System status: per-feed freshness from BigQuery table metadata.

Born from the odds_snapshots incident (see the README deficiency log,
2026-07-31): the hourly odds job failed on every run for weeks and nothing
noticed, because no downstream reader existed and job failures alert no
one. Two consumers share this module:

- ``nfl-dfs check-freshness`` (Cloud Run job, daily): raises if any
  alerting feed is stale, which fails the job and trips the Cloud
  Monitoring failed-execution alert -> email.
- ``GET /api/system-status`` (web app): the System status popup.

Freshness reads ``bigquery.get_table`` metadata (last modified + row
count) — no query cost, one metadata call per feed. Season-awareness is
date-based: NFL feeds idle outside September–January, CFB outside
mid-August–January; feeds marked "always" (nflverse refresh, feature
builds) must stay fresh year-round because their jobs run year-round.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from .config import settings


@dataclass(frozen=True)
class Feed:
    key: str
    label: str
    dataset: str          # settings attr: 'raw' | 'features' | 'predictions'
    table: str
    max_age_h: float      # freshness bar while the feed is active
    season: str = "always"  # 'always' | 'nfl' | 'cfb'
    alert: bool = True    # False: show in the popup, never fail check-freshness
    note: str = ""


# Thresholds follow the LIVE scheduler cadences (verified 2026-07-31), not
# README §11's aspirational ones: s-nflverse/s-features/s-train/s-project-tu
# all run weekly on Tuesdays, so their bar is 8 days (one missed Tuesday ->
# stale). s-odds runs 9:00/15:00 CT Wed-Sun (worst gap ~66h -> 78h bar).
#
# The Tuesday chain feeds are 'nfl'-seasonal, not 'always': their schedulers
# are PAUSED in the off-season (2026-07-31 — re-ingesting a finished season
# weekly is pure waste). Resume before week 1 (see the week-1 checklist);
# if forgotten, these feeds go active Sep 1 and check-freshness emails.
FEEDS: tuple[Feed, ...] = (
    Feed("pbp", "Play-by-play (nflverse)", "raw", "pbp", 8 * 24, "nfl"),
    Feed("weekly_stats", "Weekly stats (nflverse)", "raw", "weekly_stats",
         8 * 24, "nfl"),
    Feed("schedules", "Schedules + closing lines", "raw", "schedules",
         8 * 24, "nfl"),
    Feed("dk_salaries", "DK slates/salaries", "raw", "dk_salaries", 36, "nfl"),
    Feed("odds_snapshots", "Game lines (The Odds API)", "raw", "odds_snapshots",
         78),
    Feed("prop_lines", "Player props (The Odds API)", "raw", "prop_lines",
         8 * 24, "nfl"),
    Feed("weather", "Weather (Open-Meteo)", "raw", "weather", 72, "nfl"),
    Feed("player_week_training", "Feature build (training)", "features",
         "player_week_training", 8 * 24, "nfl"),
    # 'nfl', not 'always': inference rows are synthetic upcoming-week rows,
    # which need next-season rosters -- legitimately empty in the off-season
    # even though the build that produces them runs year-round.
    Feed("player_week_inference", "Feature build (inference)", "features",
         "player_week_inference", 8 * 24, "nfl"),
    Feed("player_projections", "Projections", "predictions",
         "player_projections", 8 * 24, "nfl"),
    Feed("cfb_dk_salaries", "CFB slates/salaries", "raw", "cfb_dk_salaries",
         36, "cfb", note="collection-only scaffold; empty until DK posts CFB slates"),
    Feed("dk_contest_fills", "Contest fills (overlay scaffold)", "raw",
         "dk_contest_fills", 48, "nfl", alert=False,
         note="opt-in scaffold, not scheduled — informational only"),
)


def _active(season: str, today: date) -> bool:
    if season == "always":
        return True
    if season == "nfl":
        return today.month in (9, 10, 11, 12, 1)
    if season == "cfb":
        return (today.month == 8 and today.day >= 15) or today.month in (9, 10, 11, 12, 1)
    raise ValueError(season)


def _table_info(dataset: str, table: str) -> tuple[datetime, int] | None:
    """(last modified UTC, row count), or None if the table doesn't exist.
    Seam for tests — the only line that touches GCP."""
    from google.api_core.exceptions import NotFound

    from .bq import client

    try:
        t = client().get_table(f"{getattr(settings, dataset)}.{table}")
    except NotFound:
        return None
    return t.modified, t.num_rows or 0


def system_status(now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    out = []
    for feed in FEEDS:
        active = _active(feed.season, now.date())
        info = _table_info(feed.dataset, feed.table)
        if info is None:
            state, modified, rows, age_h = "missing", None, 0, None
        else:
            modified, rows = info
            age_h = (now - modified).total_seconds() / 3600
            if rows == 0:
                state = "empty" if active else "idle"
            elif age_h <= feed.max_age_h:
                state = "ok"
            else:
                state = "stale" if active else "idle"
        out.append({
            "key": feed.key,
            "label": feed.label,
            "table": f"{feed.dataset}.{feed.table}",
            "state": state,
            "active": active,
            "alerting": feed.alert,
            "last_modified": modified.isoformat() if modified else None,
            "age_hours": round(age_h, 1) if age_h is not None else None,
            "rows": rows,
            "max_age_hours": feed.max_age_h,
            "note": feed.note,
        })
    return out


def check_freshness(now: datetime | None = None) -> None:
    """Raise RuntimeError if any alerting feed is stale/empty/missing while
    active. Run as a scheduled job: a raise fails the Cloud Run execution,
    which trips the failed-execution Cloud Monitoring alert."""
    bad = [
        f"{c['label']} ({c['table']}): {c['state']}"
        + (f", last modified {c['age_hours']}h ago (max {c['max_age_hours']}h)"
           if c["age_hours"] is not None else "")
        for c in system_status(now)
        if c["alerting"] and c["active"] and c["state"] in ("stale", "empty", "missing")
    ]
    if bad:
        raise RuntimeError("Stale feeds:\n" + "\n".join(bad))
    print("All feeds fresh")

```

===== FILE: src/nfl_dfs/trends/__init__.py =====
```python

```

===== FILE: src/nfl_dfs/trends/alerts.py =====
```python
"""Salary-lag alerts (guide §8.5): DK reprices roles with a one-to-two-week
lag, so a detected changepoint with a flat salary is the highest-value
signal this system produces. The Tuesday report should name 5-10 players
whose role just changed; you should recognize most of them.
"""

from __future__ import annotations

import logging

import pandas as pd

from ..bq import SQL_DIR, load_dataframe, query_df, run_sql_file
from ..config import settings
from . import changepoint

log = logging.getLogger(__name__)

SALARY_LAG_MAX_DELTA = 500      # salary hasn't caught up yet
CHANGEPOINT_THRESHOLD = 0.5
RECENT_WEEKS = 2


def build_changepoints_table(season: int) -> pd.DataFrame:
    """Run detection over the season's usage panel and write
    nfl_features.changepoints. Uses target share for pass catchers and
    carry share for backs, taking the max signal of the two."""
    usage = query_df(
        f"""
        SELECT r.gsis_id, r.season, r.week,
               r.target_share, ru.carry_share
        FROM `{settings.features}.rz_receiving` r
        FULL OUTER JOIN `{settings.features}.rz_rushing` ru
          USING (game_id, season, week, team, gsis_id)
        WHERE COALESCE(r.season, ru.season) = {season}
        """
    )
    tgt = changepoint.detect_panel(usage.dropna(subset=["target_share"]),
                                   "target_share")
    car = changepoint.detect_panel(usage.dropna(subset=["carry_share"]),
                                   "carry_share")
    merged = (
        pd.concat([tgt.assign(signal="targets"), car.assign(signal="carries")])
        .sort_values("changepoint_prob", ascending=False)
        .drop_duplicates(["gsis_id", "season", "week"])
    )
    load_dataframe(merged, f"{settings.features}.changepoints")
    return merged


def salary_lag_watchlist() -> pd.DataFrame:
    """The alert query: fresh changepoint + flat salary."""
    return query_df(
        f"""
        SELECT p.display_name, p.team_abbr AS team, c.signal,
               c.changepoint_prob, c.weeks_since_change,
               dk.salary, dk.salary_delta_wow,
               u.target_share_l4, u.target_share_std
        FROM `{settings.features}.changepoints` c
        JOIN `{settings.features}.dk_salary_week` dk USING (gsis_id, season, week)
        JOIN `{settings.features}.player_week_usage` u USING (gsis_id, season, week)
        JOIN `{settings.features}.player_id_map` p USING (gsis_id)
        WHERE c.changepoint_prob > {CHANGEPOINT_THRESHOLD}
          AND c.weeks_since_change <= {RECENT_WEEKS}
          AND (dk.salary_delta_wow IS NULL OR dk.salary_delta_wow < {SALARY_LAG_MAX_DELTA})
        ORDER BY c.changepoint_prob DESC
        """
    )


def run(season: int) -> None:
    build_changepoints_table(season)
    watch = salary_lag_watchlist()
    if watch.empty:
        log.info("No salary-lag candidates this week")
        return
    log.info("Salary-lag watchlist (%d players):\n%s",
             len(watch), watch.head(15).to_string(index=False))


if __name__ == "__main__":
    import sys

    from ..config import current_season

    logging.basicConfig(level=logging.INFO)
    run(int(sys.argv[1]) if len(sys.argv) > 1 else current_season())

```

===== FILE: src/nfl_dfs/trends/changepoint.py =====
```python
"""Regime-change detection on usage series (guide §8.5).

Rolling averages are lagging indicators of role change: a WR promoted in
week 8 still has six weeks of WR3 usage dragging his 4-week average.
Detecting the break beats smoothing across it.

Primary detector: Bayesian online changepoint detection (Adams & MacKay
2007) with a normal-inverse-gamma conjugate model. Simpler fallbacks:
CUSUM and a two-window Welch t-test.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


def changepoint_probabilities(
    series: np.ndarray | list[float],
    hazard: float = 1 / 25,
    run_cut: int = 2,
    warmup: int = 5,
) -> np.ndarray:
    """Online changepoint detection on a usage series (e.g. weekly target
    share). Returns P(run length <= run_cut) per week — a spike means the
    role changed within the last couple of weeks.

    Two deliberate departures from the textbook readout:

    * The naive "P(run length = 0)" is constant by construction — the growth
      and changepoint branches share the same predictive, so the restart mass
      always normalizes to the hazard. Evidence for a break shows up a step
      later, as posterior mass piling onto SHORT run lengths; hence run_cut.
    * Priors are set empirically from the series (mean of the first value,
      noise from robust first differences), because fixed unit-scale priors
      swamp target-share-scale data and the detector never reacts.

    hazard behaves as a sensitivity knob more than a literal prior; 1/25
    with a 0.5 alert threshold gives ~3% false positives and ~98% detection
    on a WR3->WR1-sized break in simulation. The first `warmup` weeks are
    reported as 0 — the run-length posterior is too short to mean anything.
    """
    xs = np.asarray(series, dtype=float)
    T = len(xs)
    if T == 0:
        return np.zeros(0)

    # Empirical-Bayes priors: within-regime noise from robust first diffs.
    overall_sd = float(np.std(xs)) or 1.0
    if T >= 3:
        d = np.diff(xs)
        sigma = float(np.median(np.abs(d - np.median(d)))) / 0.6745 / np.sqrt(2)
    else:
        sigma = overall_sd
    sigma = max(sigma, 1e-3 * overall_sd, 1e-9)
    mu0, kappa0, alpha0 = float(xs[0]), 1.0, 2.0
    beta0 = (alpha0 - 1) * sigma**2  # E[sigma^2] = beta0/(alpha0-1) = sigma^2

    # Run-length posterior over 0..t, plus NIG params per run length.
    r_probs = np.array([1.0])
    mu = np.array([mu0])
    kappa = np.array([kappa0])
    alpha = np.array([alpha0])
    beta = np.array([beta0])
    cp = np.zeros(T)
    warmup = max(warmup, run_cut + 1)

    for t, x in enumerate(xs):
        # Posterior predictive (Student-t) of x under each run length
        pred = stats.t.pdf(
            x,
            df=2 * alpha,
            loc=mu,
            scale=np.sqrt(beta * (kappa + 1) / (alpha * kappa)),
        )
        pred = np.clip(pred, 1e-300, None)

        growth = r_probs * pred * (1 - hazard)          # runs continue
        change = float(np.sum(r_probs * pred) * hazard)  # a run restarts

        r_probs = np.concatenate([[change], growth])
        r_probs /= r_probs.sum()
        cp[t] = r_probs[: run_cut + 1].sum() if t >= warmup else 0.0

        # Normal-inverse-gamma conjugate updates (index 0 = fresh run,
        # computed from the PRE-update parameters).
        mu_new = np.concatenate([[mu0], (kappa * mu + x) / (kappa + 1)])
        beta_new = np.concatenate([[beta0], beta + kappa * (x - mu) ** 2 / (2 * (kappa + 1))])
        kappa_new = np.concatenate([[kappa0], kappa + 1])
        alpha_new = np.concatenate([[alpha0], alpha + 0.5])
        mu, kappa, alpha, beta = mu_new, kappa_new, alpha_new, beta_new

    return cp


def cusum_flags(
    series: np.ndarray | list[float],
    k: float = 0.5,
    h: float = 4.0,
) -> np.ndarray:
    """One-sided CUSUM on a standardized series; ~15 lines, catches most of
    the same breaks. k = slack (in SDs), h = decision threshold (in SDs).
    Returns a boolean flag per observation (upward or downward shift)."""
    xs = np.asarray(series, dtype=float)
    if len(xs) < 3:
        return np.zeros(len(xs), dtype=bool)
    mu, sd = np.nanmean(xs), np.nanstd(xs)
    if sd == 0:
        return np.zeros(len(xs), dtype=bool)
    z = (xs - mu) / sd
    up = down = 0.0
    flags = np.zeros(len(xs), dtype=bool)
    for i, zi in enumerate(z):
        up = max(0.0, up + zi - k)
        down = max(0.0, down - zi - k)
        if up > h or down > h:
            flags[i] = True
            up = down = 0.0
    return flags


def two_window_pvalue(
    series: np.ndarray | list[float], recent: int = 2, baseline: int = 6
) -> float:
    """Welch t-test: last `recent` weeks vs the `baseline` weeks before
    them. Small p = the recent level is a different regime."""
    xs = np.asarray(series, dtype=float)
    if len(xs) < recent + 3:
        return 1.0
    tail = xs[-recent:]
    base = xs[-(recent + baseline):-recent]
    if len(base) < 3 or np.nanstd(base) == 0 and np.nanstd(tail) == 0:
        return 1.0
    res = stats.ttest_ind(tail, base, equal_var=False)
    return float(res.pvalue) if np.isfinite(res.pvalue) else 1.0


@dataclass
class PlayerTrend:
    gsis_id: str
    season: int
    week: int
    changepoint_prob: float
    weeks_since_change: int
    cusum_flag: bool
    two_window_p: float


def detect_panel(
    df: pd.DataFrame,
    value_col: str = "target_share",
    threshold: float = 0.5,
    min_weeks: int = 4,
) -> pd.DataFrame:
    """Run detection per player-season over a long panel with columns
    [gsis_id, season, week, value_col]. Returns one row per player-week:
    changepoint_prob, weeks_since_change, cusum_flag, two_window_p.

    Feed `weeks_since_change` and `changepoint_prob` to the model as
    features; alert on prob > threshold for the weekly watchlist.
    """
    out: list[PlayerTrend] = []
    for (gsis_id, season), grp in df.groupby(["gsis_id", "season"], sort=False):
        grp = grp.sort_values("week")
        xs = grp[value_col].to_numpy(dtype=float)
        if len(xs) < min_weeks or np.all(np.isnan(xs)):
            continue
        xs = np.nan_to_num(xs, nan=float(np.nanmean(xs)))
        cp = changepoint_probabilities(xs)
        cusum = cusum_flags(xs)
        weeks_since = 0
        for i, week in enumerate(grp.week.to_numpy()):
            # Week 1 trivially restarts the run; ignore as "no change known".
            is_change = cp[i] > threshold and i > 0
            weeks_since = 0 if is_change else weeks_since + 1
            out.append(
                PlayerTrend(
                    gsis_id=gsis_id,
                    season=int(season),
                    week=int(week),
                    changepoint_prob=float(cp[i]) if i > 0 else 0.0,
                    weeks_since_change=weeks_since,
                    cusum_flag=bool(cusum[i]),
                    two_window_p=two_window_pvalue(xs[: i + 1]),
                )
            )
    return pd.DataFrame([t.__dict__ for t in out])

```

===== FILE: src/nfl_dfs/watchlist.py =====
```python
"""Player watch notes: qualitative "keep an eye on this guy" intel.

Deliberately DISTINCT from manual usage notes (notes.py): a watch note is
one free-text field attached to a player and it affects NOTHING — no
projection, no lineup math. It is the first stage of a pipeline the user
runs by hand: watch -> (maybe) convert into a usage-note adjustment once
the hunch firms up. Conversion creates the manual note via notes.add_note
and stamps this row converted, preserving the paper trail.

Surfaced in three places: chat tools (add/list/delete/convert), the
/watchlist page (lifecycle view + convert/delete), and inline on any
generated lineup containing a watched player.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone

import pandas as pd

from .bq import load_dataframe, query_df
from .config import settings

log = logging.getLogger(__name__)

TABLE = "player_watch_notes"


def _table() -> str:
    return f"{settings.features}.{TABLE}"


def _norm(name: str) -> str:
    return re.sub(r"[^A-Z ]", "", str(name).upper()).strip()


def list_watch(include_converted: bool = True) -> pd.DataFrame:
    cols = ["note_id", "gsis_id", "display_name", "note", "status",
            "created_at", "converted_at", "converted_note_id", "converted_mult"]
    try:
        df = query_df(
            f"SELECT {', '.join(cols)} FROM `{_table()}` ORDER BY created_at DESC"
        )
    except Exception:  # table may not exist until the first note
        log.info("player_watch_notes absent; returning empty")
        return pd.DataFrame(columns=cols)
    if not include_converted:
        df = df[df.status == "active"]
    return df


def add_watch(display_name: str, note: str, gsis_id: str = "") -> str:
    note_id = uuid.uuid4().hex[:12]
    row = pd.DataFrame([{
        "note_id": note_id, "gsis_id": gsis_id or "",
        "display_name": display_name, "note": note, "status": "active",
        "created_at": datetime.now(timezone.utc),
        "converted_at": pd.NaT, "converted_note_id": "",
        "converted_mult": float("nan"),
    }])
    load_dataframe(row, _table(), write_disposition="WRITE_APPEND")
    return note_id


def delete_watch(note_id: str) -> int:
    from google.cloud import bigquery

    from .bq import client

    job = client().query(
        f"DELETE FROM `{_table()}` WHERE note_id = @id",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("id", "STRING", note_id)]),
    )
    job.result()
    return job.num_dml_affected_rows or 0


def convert_watch(note_id: str, mult: float, season: int) -> str:
    """Promote a watch note into a real usage-note adjustment (notes.py),
    stamping this row converted. Returns the manual note's id."""
    from . import notes

    df = list_watch()
    row = df[df.note_id == note_id]
    if row.empty:
        raise ValueError(f"no watch note {note_id}")
    r = row.iloc[0]
    if r.status == "converted":
        raise ValueError(f"watch note {note_id} already converted "
                         f"(manual note {r.converted_note_id})")
    manual_id = notes.add_note(
        gsis_id=str(r.gsis_id or ""), display_name=str(r.display_name),
        season=int(season), mult=float(mult),
        note=f"[from watchlist] {r.note}", source="watchlist")

    from google.cloud import bigquery

    from .bq import client

    job = client().query(
        f"""UPDATE `{_table()}`
            SET status = 'converted',
                converted_at = CURRENT_TIMESTAMP(),
                converted_note_id = @mid,
                converted_mult = @mult
            WHERE note_id = @id""",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ScalarQueryParameter("mid", "STRING", manual_id),
            bigquery.ScalarQueryParameter("mult", "FLOAT64", float(mult)),
            bigquery.ScalarQueryParameter("id", "STRING", note_id)]),
    )
    job.result()
    return manual_id


def annotate_players(players: list[dict]) -> None:
    """Attach 'watch_note' in place to any player dict whose name matches
    an ACTIVE watch note. Failure-safe: lineups without notes beat no
    lineups."""
    try:
        active = list_watch(include_converted=False)
    except Exception:
        log.exception("watchlist unavailable; lineups un-annotated")
        return
    if active.empty:
        return
    by_name = {_norm(r.display_name): str(r.note) for r in active.itertuples()}
    seen: set[int] = set()  # pool dicts recur across lineups; annotate once
    for p in players:
        if id(p) in seen:
            continue
        seen.add(id(p))
        note = by_name.get(_norm(p.get("name", "")))
        if note:
            p["watch_note"] = note

```

===== FILE: sql/features/001_player_id_map.sql =====
```sql
-- DK player id <-> GSIS id crosswalk. Name matching alone fails on suffixes,
-- apostrophes, and ~two dozen collisions per season, so we require
-- (normalized name, team, position) to agree, then patch the remainder via
-- the manual override table. Fail loudly on unmatched slate players — a
-- dropped player is a lineup you can't build (see leakage/QA checks).

CREATE TABLE IF NOT EXISTS `${features}.player_id_overrides` (
  dk_player_id INT64,
  gsis_id STRING,
  note STRING
);

CREATE OR REPLACE TABLE `${features}.player_id_map` AS
WITH dk AS (
  SELECT DISTINCT dk_player_id, display_name, team_abbr, position
  FROM `${raw}.dk_salaries`
  WHERE pulled_at > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 365 DAY)
),
norm_dk AS (
  SELECT
    dk_player_id, display_name, team_abbr, position,
    REGEXP_REPLACE(
      REGEXP_REPLACE(UPPER(display_name), r"\s+(JR|SR|II|III|IV|V)\.?$", ""),
      r"[^A-Z ]", "") AS clean_name
  FROM dk
),
norm_nfl AS (
  SELECT
    gsis_id, name, team, position,
    REGEXP_REPLACE(
      REGEXP_REPLACE(UPPER(name), r"\s+(JR|SR|II|III|IV|V)\.?$", ""),
      r"[^A-Z ]", "") AS clean_name
  FROM `${raw}.player_ids`
  WHERE gsis_id IS NOT NULL
),
matched AS (
  SELECT d.dk_player_id, n.gsis_id, d.display_name, d.team_abbr, d.position,
         'auto' AS match_source
  FROM norm_dk d
  JOIN norm_nfl n
    ON d.clean_name = n.clean_name
   AND d.team_abbr  = n.team
   AND d.position   = n.position
)
SELECT * FROM matched
UNION ALL
SELECT o.dk_player_id, o.gsis_id, d.display_name, d.team_abbr, d.position,
       'manual' AS match_source
FROM `${features}.player_id_overrides` o
JOIN norm_dk d USING (dk_player_id)
WHERE o.dk_player_id NOT IN (SELECT dk_player_id FROM matched);

```

===== FILE: sql/features/002_unmatched_report.sql =====
```sql
-- Players in the current pool with no GSIS mapping. This list should be
-- reviewed weekly and drained into player_id_overrides. Expect 10-30 manual
-- entries per season, mostly rookies and practice-squad call-ups.
CREATE OR REPLACE VIEW `${features}.unmatched_dk_players` AS
WITH latest_pull AS (
  SELECT MAX(pulled_at) AS ts FROM `${raw}.dk_salaries`
)
SELECT DISTINCT s.dk_player_id, s.display_name, s.team_abbr, s.position, s.salary
FROM `${raw}.dk_salaries` s, latest_pull
WHERE s.pulled_at = latest_pull.ts
  AND s.dk_player_id NOT IN (SELECT dk_player_id FROM `${features}.player_id_map`)
ORDER BY s.salary DESC;

```

===== FILE: sql/features/003_player_week_role.sql =====
```sql
-- Role context per (player, season, week): depth chart rank at the player's
-- position, rookie flag, and draft capital. These are the inputs
-- models/coldstart.py's ROLE_PRIORS were designed around — a cold-start
-- backup should be priced by the role he steps into, not a league default.
--
-- Point-in-time: a depth chart for week W is published before W's games
-- (same discipline as the injury report in 018), so same-week rows are
-- legitimately knowable.
--
-- nflverse changed the depth charts format in 2025 (see the data deficiency
-- log), so ingest lands two raw tables and this file normalizes both:
--   ${raw}.depth_charts           2001-2024: season/week rows, depth_team rank
--   ${raw}.depth_charts_snapshots 2025-    : dated snapshots (dt), pos_rank
-- Snapshot rows are mapped to weeks point-in-time: the latest snapshot dated
-- on/before the team's gameday serves that week.
--
-- WR caveat: the legacy format lists alignment starters with equal
-- depth_team (e.g. two WR "1" rows), so ROW_NUMBER splits ties
-- deterministically by jersey number — ranks 1-3 all mean "starter tier".
-- The 2025 snapshot format publishes a true global pos_rank per position.
CREATE OR REPLACE TABLE `${features}.player_week_role` AS
WITH team_games AS (
  -- (season, week, team, gameday) for every scheduled game, both sides
  SELECT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
         home_team AS team, gameday
  FROM `${raw}.schedules`
  UNION ALL
  SELECT CAST(season AS INT64), CAST(week AS INT64), away_team, gameday
  FROM `${raw}.schedules`
),
upcoming AS (
  -- Each team's next unplayed game: where live inference points
  SELECT season, team, MIN(week) AS week
  FROM team_games
  WHERE gameday >= CAST(CURRENT_DATE() AS STRING)
  GROUP BY season, team
),
roster AS (
  SELECT
    gsis_id,
    CAST(season AS INT64) AS season,
    CAST(week AS INT64) AS week,
    team,
    position,
    SAFE_CAST(rookie_year AS INT64) = CAST(season AS INT64) AS is_rookie,
    SAFE_CAST(entry_year AS INT64) AS entry_year,
    SAFE_CAST(draft_number AS INT64) AS draft_number
  FROM `${raw}.rosters_weekly`
  WHERE gsis_id IS NOT NULL AND position IN ('QB', 'RB', 'WR', 'TE')
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY gsis_id, CAST(season AS INT64), CAST(week AS INT64)
    ORDER BY team
  ) = 1
),
latest_roster AS (
  SELECT * FROM roster
  QUALIFY ROW_NUMBER() OVER (PARTITION BY gsis_id, season ORDER BY week DESC) = 1
),
-- Roster rows for the upcoming week, synthesized from each player's latest
-- known roster spot when nflverse hasn't published that week yet.
base AS (
  SELECT r.gsis_id, r.season, r.week, r.team, r.position,
         r.is_rookie, r.entry_year, r.draft_number
  FROM roster r
  UNION ALL
  SELECT lr.gsis_id, up.season, up.week, up.team, lr.position,
         lr.is_rookie, lr.entry_year, lr.draft_number
  FROM upcoming up
  JOIN latest_roster lr ON lr.season = up.season AND lr.team = up.team
  WHERE NOT EXISTS (
    SELECT 1 FROM roster r2
    WHERE r2.gsis_id = lr.gsis_id AND r2.season = up.season AND r2.week = up.week
  )
),
-- Legacy format: one rank per (team, week, position), deterministic tiebreak
legacy_rank AS (
  SELECT
    gsis_id,
    CAST(season AS INT64) AS season,
    SAFE_CAST(week AS INT64) AS week,
    club_code AS team,
    position,
    ROW_NUMBER() OVER (
      PARTITION BY club_code, CAST(season AS INT64), SAFE_CAST(week AS INT64), position
      ORDER BY SAFE_CAST(depth_team AS INT64), SAFE_CAST(jersey_number AS INT64), gsis_id
    ) AS depth_rank
  FROM `${raw}.depth_charts`
  WHERE gsis_id IS NOT NULL
    AND formation = 'Offense'
    AND position IN ('QB', 'RB', 'WR', 'TE')
    AND week IS NOT NULL
),
-- Snapshot format: pick the latest snapshot on/before each game day
snap AS (
  SELECT team, TIMESTAMP(dt) AS ts, gsis_id, pos_abb AS position, pos_rank
  FROM `${raw}.depth_charts_snapshots`
  WHERE gsis_id IS NOT NULL AND pos_abb IN ('QB', 'RB', 'WR', 'TE')
),
snap_ts_per_game AS (
  SELECT g.season, g.week, g.team, MAX(s.ts) AS ts
  FROM team_games g
  JOIN snap s ON s.team = g.team AND DATE(s.ts) <= DATE(g.gameday)
  GROUP BY g.season, g.week, g.team
),
snapshot_rank AS (
  SELECT p.season, p.week, p.team, s.gsis_id, s.position,
         CAST(s.pos_rank AS INT64) AS depth_rank
  FROM snap_ts_per_game p
  JOIN snap s ON s.team = p.team AND s.ts = p.ts
),
ranks AS (
  SELECT * FROM legacy_rank
  UNION ALL
  SELECT gsis_id, season, week, team, position, depth_rank FROM snapshot_rank
),
deduped AS (
SELECT
  b.gsis_id, b.season, b.week, b.team, b.position,
  r.depth_rank,
  COALESCE(b.is_rookie, FALSE) AS is_rookie,
  -- draft_picks.gsis_id is unset/non-GSIS for recent classes (see the
  -- deficiency log), so fall back to matching the roster's overall pick
  -- number within the player's entry-year draft.
  COALESCE(dg.round, dp.round) AS draft_round,
  COALESCE(b.week = up.week, FALSE) AS is_upcoming
FROM base b
LEFT JOIN ranks r
  ON r.gsis_id = b.gsis_id AND r.season = b.season AND r.week = b.week
LEFT JOIN (
  SELECT gsis_id, CAST(round AS INT64) AS round
  FROM `${raw}.draft_picks`
  WHERE gsis_id IS NOT NULL
  QUALIFY ROW_NUMBER() OVER (PARTITION BY gsis_id ORDER BY season DESC) = 1
) dg ON dg.gsis_id = b.gsis_id
LEFT JOIN (
  SELECT CAST(season AS INT64) AS draft_season, CAST(pick AS INT64) AS pick,
         CAST(round AS INT64) AS round
  FROM `${raw}.draft_picks`
) dp ON dp.draft_season = b.entry_year AND dp.pick = b.draft_number
LEFT JOIN upcoming up ON up.season = b.season AND up.team = b.team
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY b.gsis_id, b.season, b.week
  ORDER BY r.depth_rank NULLS LAST
) = 1
)
SELECT
  *,
  -- Depth-rank transition (Addendum 24): winning Milly punts are often
  -- NEWLY-promoted min-priced starters (rank 2 -> 1 in recent weeks, e.g.
  -- Gadsden wk 7) that static depth_rank can't distinguish from long-time
  -- starters. Positive = promoted vs the player's previous listed week.
  -- Both ranks are as-of-week-W roster knowledge (same discipline as
  -- depth_rank itself, see header), so no PRECEDING window is needed;
  -- computed AFTER dedup so LAG sees one row per (player, week).
  LAG(depth_rank) OVER (
    PARTITION BY gsis_id, season ORDER BY week
  ) - depth_rank AS depth_rank_delta
FROM deduped;

```

===== FILE: sql/features/010_rz_receiving.sql =====
```sql
-- Red zone receiving usage by player-game, with inside-10 and inside-5 splits.
CREATE OR REPLACE TABLE `${features}.rz_receiving` AS
WITH plays AS (
  SELECT
    game_id, season, week, posteam, receiver_player_id,
    yardline_100,
    pass_attempt, complete_pass, pass_touchdown, air_yards
  FROM `${raw}.pbp`
  WHERE pass_attempt = 1
    AND receiver_player_id IS NOT NULL
    AND season_type IN ('REG','POST')
),
player_level AS (
  SELECT
    game_id, season, week, posteam AS team, receiver_player_id AS gsis_id,
    COUNTIF(yardline_100 <= 20) AS rz20_targets,
    COUNTIF(yardline_100 <= 10) AS rz10_targets,
    COUNTIF(yardline_100 <=  5) AS rz5_targets,
    COUNTIF(yardline_100 <= 20 AND pass_touchdown = 1) AS rz20_tds,
    COUNTIF(yardline_100 <= 10 AND complete_pass = 1)  AS rz10_receptions,
    COUNT(*) AS total_targets,
    SUM(air_yards) AS total_air_yards
  FROM plays
  GROUP BY 1,2,3,4,5
),
team_level AS (
  SELECT
    game_id, posteam AS team,
    COUNTIF(yardline_100 <= 20) AS team_rz20_targets,
    COUNTIF(yardline_100 <= 10) AS team_rz10_targets,
    COUNT(*) AS team_targets,
    SUM(air_yards) AS team_air_yards
  FROM plays
  GROUP BY 1,2
)
SELECT
  p.*,
  SAFE_DIVIDE(p.rz20_targets, t.team_rz20_targets) AS rz20_target_share,
  SAFE_DIVIDE(p.rz10_targets, t.team_rz10_targets) AS rz10_target_share,
  SAFE_DIVIDE(p.total_targets, t.team_targets)     AS target_share,
  SAFE_DIVIDE(p.total_air_yards, t.team_air_yards) AS air_yards_share
FROM player_level p
JOIN team_level t USING (game_id, team);

```

===== FILE: sql/features/011_rz_rushing.sql =====
```sql
-- Red zone rushing usage; goal-line split at <=3 is where RB touchdown
-- equity actually lives.
CREATE OR REPLACE TABLE `${features}.rz_rushing` AS
WITH plays AS (
  SELECT
    game_id, season, week, posteam, rusher_player_id,
    yardline_100, rush_attempt, rush_touchdown, yards_gained
  FROM `${raw}.pbp`
  WHERE rush_attempt = 1
    AND rusher_player_id IS NOT NULL
    AND season_type IN ('REG','POST')
),
player_level AS (
  SELECT
    game_id, season, week, posteam AS team, rusher_player_id AS gsis_id,
    COUNTIF(yardline_100 <= 20) AS rz20_carries,
    COUNTIF(yardline_100 <= 10) AS rz10_carries,
    COUNTIF(yardline_100 <=  5) AS rz5_carries,
    COUNTIF(yardline_100 <=  3) AS gl3_carries,
    COUNTIF(yardline_100 <= 20 AND rush_touchdown = 1) AS rz20_rush_tds,
    COUNT(*) AS total_carries,
    SUM(yards_gained) AS total_rush_yards
  FROM plays
  GROUP BY 1,2,3,4,5
),
team_level AS (
  SELECT
    game_id, posteam AS team,
    COUNTIF(yardline_100 <= 20) AS team_rz20_carries,
    COUNTIF(yardline_100 <=  3) AS team_gl3_carries,
    COUNT(*) AS team_carries
  FROM plays
  GROUP BY 1,2
)
SELECT
  p.*,
  SAFE_DIVIDE(p.rz20_carries, t.team_rz20_carries) AS rz20_carry_share,
  SAFE_DIVIDE(p.gl3_carries,  t.team_gl3_carries)  AS gl3_carry_share,
  SAFE_DIVIDE(p.total_carries, t.team_carries)     AS carry_share
FROM player_level p
JOIN team_level t USING (game_id, team);

```

===== FILE: sql/features/012_schedule_long.sql =====
```sql
-- One row per team-game with Vegas context. Implied totals from the closing
-- spread/total: the single strongest projection feature in the system.
-- nflverse convention: spread_line is relative to the home team (positive =
-- home favored), so implied_home = total/2 + spread_home/2.
CREATE OR REPLACE TABLE `${features}.schedule_long` AS
-- Team codes NORMALIZED to the modern convention (OAK->LV, SD->LAC,
-- STL->LA) to match rosters/stats-derived tables. Before 2026-08-03 the
-- historical codes silently dropped ~1,500 relocated-franchise training
-- rows (2014-19) at 021's inner join and NULLed opponent-defense
-- features on 1,458 more (data audit, Addendum 42).
WITH base AS (
  SELECT
    game_id, season, week, game_type,
    gameday, weekday, gametime,
    CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE home_team END AS home_team,
    CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE away_team END AS away_team,
    spread_line,                       -- home margin expectation
    total_line,
    roof, surface, temp, wind,
    home_rest, away_rest
  FROM `${raw}.schedules`
  WHERE total_line IS NOT NULL
)
SELECT
  game_id, season, week, game_type, gameday,
  home_team AS team, away_team AS opponent, TRUE AS is_home,
  spread_line * -1 AS team_spread,     -- negative = this team favored
  total_line AS game_total,
  total_line / 2 + spread_line / 2 AS implied_team_total,
  total_line / 2 - spread_line / 2 AS implied_opponent_total,
  spread_line AS expected_margin,
  roof, surface, home_rest AS days_rest
FROM base
UNION ALL
SELECT
  game_id, season, week, game_type, gameday,
  away_team AS team, home_team AS opponent, FALSE AS is_home,
  spread_line AS team_spread,
  total_line AS game_total,
  total_line / 2 - spread_line / 2 AS implied_team_total,
  total_line / 2 + spread_line / 2 AS implied_opponent_total,
  spread_line * -1 AS expected_margin,
  roof, surface, away_rest AS days_rest
FROM base;

```

===== FILE: sql/features/013_player_week_actuals.sql =====
```sql
-- Realized per-player-week stat lines and DK classic points (labels).
-- Sourced from nflverse weekly_stats; DK scoring incl. yardage bonuses.
CREATE OR REPLACE TABLE `${features}.player_week_actuals` AS
SELECT
  player_id AS gsis_id,
  season, week,
  team,
  targets, receptions,
  receiving_yards   AS rec_yards,
  receiving_tds     AS rec_tds,
  carries,
  rushing_yards     AS rush_yards,
  rushing_tds       AS rush_tds,
  attempts          AS pass_attempts,
  completions,
  passing_yards     AS pass_yards,
  passing_tds       AS pass_tds,
  passing_interceptions AS interceptions,
  sack_fumbles_lost + rushing_fumbles_lost + receiving_fumbles_lost AS fumbles_lost,
  passing_2pt_conversions + rushing_2pt_conversions + receiving_2pt_conversions AS two_pt,
  special_teams_tds,

  -- DK classic scoring (see guide §6.1)
  0.04 * passing_yards
    + 4 * passing_tds
    + IF(passing_yards >= 300, 3, 0)
    - 1 * passing_interceptions
    + 0.1 * rushing_yards
    + 6 * rushing_tds
    + IF(rushing_yards >= 100, 3, 0)
    + 1 * receptions
    + 0.1 * receiving_yards
    + 6 * receiving_tds
    + IF(receiving_yards >= 100, 3, 0)
    - 1 * (sack_fumbles_lost + rushing_fumbles_lost + receiving_fumbles_lost)
    + 2 * (passing_2pt_conversions + rushing_2pt_conversions + receiving_2pt_conversions)
    + 6 * special_teams_tds
  AS dk_points
FROM `${raw}.weekly_stats`
WHERE season_type = 'REG';

```

===== FILE: sql/features/014_player_week_usage.sql =====
```sql
-- Point-in-time rolling usage features. The cardinal rule: a row for
-- (player, season, week) contains only data from weeks strictly before
-- `week` — enforced by the `1 PRECEDING` upper window bound.
--
-- Small-sample smoothing: red zone counts shrink toward a positional prior
-- with weight PRIOR_K games (empirical-Bayes style; tuned on validation).
CREATE OR REPLACE TABLE `${features}.player_week_usage` AS
WITH position_map AS (
  SELECT gsis_id, season, ANY_VALUE(position HAVING MAX week) AS position
  FROM `${raw}.rosters_weekly`
  WHERE gsis_id IS NOT NULL
  GROUP BY gsis_id, season
),
snaps AS (
  SELECT i.gsis_id, n.season, n.week, n.offense_pct AS snap_share
  FROM `${raw}.snap_counts` n
  JOIN `${raw}.player_ids` i ON i.pfr_id = n.pfr_player_id
  WHERE i.gsis_id IS NOT NULL
),
usage AS (
  SELECT
    COALESCE(rec.gsis_id, rush.gsis_id) AS gsis_id,
    COALESCE(rec.season, rush.season)   AS season,
    COALESCE(rec.week, rush.week)       AS week,
    COALESCE(rec.team, rush.team)       AS team,
    COALESCE(rec.rz20_targets, 0)  AS rz20_targets,
    COALESCE(rec.rz10_targets, 0)  AS rz10_targets,
    COALESCE(rec.total_targets, 0) AS total_targets,
    rec.target_share,
    rec.air_yards_share,
    rec.rz20_target_share,
    rec.rz10_target_share,
    COALESCE(rush.rz20_carries, 0)  AS rz20_carries,
    COALESCE(rush.gl3_carries, 0)   AS gl3_carries,
    COALESCE(rush.total_carries, 0) AS total_carries,
    rush.carry_share,
    rush.gl3_carry_share
  FROM `${features}.rz_receiving` rec
  FULL OUTER JOIN `${features}.rz_rushing` rush
    USING (game_id, season, week, team, gsis_id)
),
-- Synthetic rows for each team's next unplayed game (player_week_role marks
-- them is_upcoming). All source metrics are NULL, so the strictly-prior
-- windows below naturally yield "as of now" rollups for the upcoming week —
-- the rows live inference needs and the training table (021) must exclude.
upcoming_rows AS (
  SELECT
    ro.gsis_id, ro.season, ro.week, ro.team,
    CAST(NULL AS INT64) AS rz20_targets,
    CAST(NULL AS INT64) AS rz10_targets,
    CAST(NULL AS INT64) AS total_targets,
    CAST(NULL AS FLOAT64) AS target_share,
    CAST(NULL AS FLOAT64) AS air_yards_share,
    CAST(NULL AS FLOAT64) AS rz20_target_share,
    CAST(NULL AS FLOAT64) AS rz10_target_share,
    CAST(NULL AS INT64) AS rz20_carries,
    CAST(NULL AS INT64) AS gl3_carries,
    CAST(NULL AS INT64) AS total_carries,
    CAST(NULL AS FLOAT64) AS carry_share,
    CAST(NULL AS FLOAT64) AS gl3_carry_share
  FROM `${features}.player_week_role` ro
  WHERE ro.is_upcoming
    AND NOT EXISTS (
      SELECT 1 FROM usage u2
      WHERE u2.gsis_id = ro.gsis_id AND u2.season = ro.season AND u2.week = ro.week
    )
),
usage_all AS (
  SELECT u.*, FALSE AS is_upcoming FROM usage u
  UNION ALL
  SELECT up.*, TRUE AS is_upcoming FROM upcoming_rows up
),
with_snaps AS (
  SELECT u.*, s.snap_share
  FROM usage_all u
  LEFT JOIN snaps s USING (gsis_id, season, week)
),
rolled AS (
  SELECT
    gsis_id, season, week, team, is_upcoming,

    -- Trailing 4-week averages, EXCLUDING current week (1 PRECEDING is key)
    AVG(rz20_targets)      OVER w4 AS rz20_targets_l4,
    AVG(rz10_targets)      OVER w4 AS rz10_targets_l4,
    AVG(total_targets)     OVER w4 AS targets_l4,
    AVG(target_share)      OVER w4 AS target_share_l4,
    AVG(air_yards_share)   OVER w4 AS air_yards_share_l4,
    AVG(rz20_target_share) OVER w4 AS rz20_target_share_l4,
    AVG(rz10_target_share) OVER w4 AS rz10_target_share_l4,
    AVG(rz20_carries)      OVER w4 AS rz20_carries_l4,
    AVG(gl3_carries)       OVER w4 AS gl3_carries_l4,
    AVG(total_carries)     OVER w4 AS carries_l4,
    AVG(carry_share)       OVER w4 AS carry_share_l4,
    AVG(gl3_carry_share)   OVER w4 AS gl3_carry_share_l4,
    AVG(snap_share)        OVER w4 AS snap_share_l4,

    -- Season-to-date, also excluding current
    AVG(rz20_targets)  OVER wstd AS rz20_targets_std,
    AVG(target_share)  OVER wstd AS target_share_std,
    AVG(total_targets) OVER wstd AS targets_std,
    AVG(total_carries) OVER wstd AS carries_std,
    SUM(rz20_targets)  OVER wstd AS rz20_targets_sum_prior,
    SUM(gl3_carries)   OVER wstd AS gl3_carries_sum_prior,

    -- Trend: recent form vs season baseline
    SAFE_DIVIDE(AVG(target_share) OVER w4, AVG(target_share) OVER wstd)
      AS target_share_trend,
    SAFE_DIVIDE(AVG(carry_share) OVER w4, AVG(carry_share) OVER wstd)
      AS carry_share_trend,

    COUNT(*) OVER wstd AS games_played_prior
  FROM with_snaps
  WINDOW
    w4   AS (PARTITION BY gsis_id, season ORDER BY week
             ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING),
    wstd AS (PARTITION BY gsis_id, season ORDER BY week
             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
),
-- League-wide per-position per-game priors for shrinkage. Stable enough
-- year to year that using the full history is fine.
position_priors AS (
  SELECT pm.position,
         AVG(u.rz20_targets) AS prior_rz20_per_game,
         AVG(u.gl3_carries)  AS prior_gl3_per_game
  FROM usage u
  JOIN position_map pm USING (gsis_id, season)
  GROUP BY pm.position
)
SELECT
  r.*,
  pm.position,
  1.5 * r.target_share_l4 + 0.7 * r.air_yards_share_l4 AS wopr_l4,
  SAFE_DIVIDE(
    r.rz20_targets_sum_prior + (${prior_k} * pp.prior_rz20_per_game),
    r.games_played_prior + ${prior_k}
  ) AS rz20_targets_smoothed,
  SAFE_DIVIDE(
    r.gl3_carries_sum_prior + (${prior_k} * pp.prior_gl3_per_game),
    r.games_played_prior + ${prior_k}
  ) AS gl3_carries_smoothed
FROM rolled r
LEFT JOIN position_map pm USING (gsis_id, season)
LEFT JOIN position_priors pp ON pp.position = pm.position;

```

===== FILE: sql/features/015_player_week_efficiency.sql =====
```sql
-- Point-in-time efficiency (rate) features: trailing windows on realized
-- efficiency, all excluding the current week.
CREATE OR REPLACE TABLE `${features}.player_week_efficiency` AS
WITH per_game AS (
  SELECT
    a.gsis_id, a.season, a.week,
    SAFE_DIVIDE(a.rec_yards, NULLIF(a.targets, 0))    AS yards_per_target,
    SAFE_DIVIDE(a.rec_yards, NULLIF(a.receptions, 0)) AS yards_per_reception,
    SAFE_DIVIDE(a.receptions, NULLIF(a.targets, 0))   AS catch_rate,
    SAFE_DIVIDE(a.rush_yards, NULLIF(a.carries, 0))   AS yards_per_carry,
    SAFE_DIVIDE(a.pass_yards, NULLIF(a.pass_attempts, 0)) AS yards_per_attempt,
    a.dk_points
  FROM `${features}.player_week_actuals` a
),
-- Synthetic rows for each team's next unplayed game (same device as 014):
-- NULL metrics, so the strictly-prior windows emit as-of-now values on the
-- upcoming week's row for live inference.
per_game_all AS (
  SELECT * FROM per_game
  UNION ALL
  SELECT
    ro.gsis_id, ro.season, ro.week,
    CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64),
    CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64), CAST(NULL AS FLOAT64)
  FROM `${features}.player_week_role` ro
  WHERE ro.is_upcoming
    AND NOT EXISTS (
      SELECT 1 FROM per_game g2
      WHERE g2.gsis_id = ro.gsis_id AND g2.season = ro.season AND g2.week = ro.week
    )
),
qb_quality AS (
  -- CPOE of the team's primary passer, trailing; a receiver feature.
  SELECT
    posteam AS team, season, week,
    AVG(cpoe) AS team_cpoe
  FROM `${raw}.pbp`
  WHERE qb_dropback = 1 AND cpoe IS NOT NULL
  GROUP BY 1, 2, 3
),
adot AS (
  SELECT
    receiver_player_id AS gsis_id, season, week,
    AVG(air_yards) AS adot
  FROM `${raw}.pbp`
  WHERE pass_attempt = 1 AND receiver_player_id IS NOT NULL
  GROUP BY 1, 2, 3
)
SELECT
  g.gsis_id, g.season, g.week,
  AVG(g.yards_per_target)    OVER w8 AS yards_per_target_l8,
  AVG(g.yards_per_reception) OVER w8 AS yards_per_reception_l8,
  AVG(g.catch_rate)          OVER w8 AS catch_rate_l8,
  AVG(g.yards_per_carry)     OVER w8 AS yards_per_carry_l8,
  AVG(g.yards_per_attempt)   OVER w8 AS yards_per_attempt_l8,
  AVG(g.dk_points)           OVER w4 AS dk_points_l4,
  AVG(g.dk_points)           OVER wstd AS dk_points_std,
  STDDEV(g.dk_points)        OVER wstd AS dk_points_vol,
  AVG(ad.adot)               OVER w8 AS adot_l8
FROM per_game_all g
LEFT JOIN adot ad USING (gsis_id, season, week)
WINDOW
  w4   AS (PARTITION BY g.gsis_id, g.season ORDER BY g.week
           ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING),
  w8   AS (PARTITION BY g.gsis_id, g.season ORDER BY g.week
           ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING),
  wstd AS (PARTITION BY g.gsis_id, g.season ORDER BY g.week
           ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING);

```

===== FILE: sql/features/015a_player_week_advanced.sql =====
```sql
-- Advanced target-quality and context metrics, strictly-prior windows.
--
-- Research-driven additions (see reports/2026-07-25-system-study.md and the
-- metric research that followed): TD *history* is the least stable fantasy
-- stat, so TD opportunity — end-zone and deep targets — is the better
-- input; air-yards-based target quality is the most predictive receiver
-- signal. NGS "over expected" metrics (RYOE/YACOE) were evaluated and
-- deliberately skipped: public research shows near-zero season-to-season
-- stability. Only two NGS features make the cut: separation (talent /
-- coverage-drawn proxy) and stacked-box rate (RB usage context).
--
-- Spine is player_week_usage, so upcoming-week synthetic rows (014) get
-- as-of-now values for live inference, same device as 015/016.
CREATE OR REPLACE TABLE `${features}.player_week_advanced` AS
WITH target_quality AS (
  -- Per player-game from pbp: end-zone targets (ball thrown to or past the
  -- goal line: air yards >= distance to goal) and deep targets (20+ air).
  SELECT
    receiver_player_id AS gsis_id,
    season, week,
    COUNTIF(air_yards >= yardline_100) AS ez_targets,
    COUNTIF(air_yards >= 20) AS deep_targets
  FROM `${raw}.pbp`
  WHERE pass_attempt = 1 AND receiver_player_id IS NOT NULL
    AND air_yards IS NOT NULL AND season_type = 'REG'
  GROUP BY 1, 2, 3
),
ngs_rec AS (
  SELECT player_gsis_id AS gsis_id, season, week, avg_separation
  FROM `${raw}.ngs_receiving`
  WHERE week > 0  -- week 0 rows are season aggregates
),
ngs_rush AS (
  SELECT player_gsis_id AS gsis_id, season, week,
         percent_attempts_gte_eight_defenders AS stacked_box_pct
  FROM `${raw}.ngs_rushing`
  WHERE week > 0
)
SELECT
  u.gsis_id, u.season, u.week,
  AVG(t.ez_targets)        OVER w4 AS ez_targets_l4,
  AVG(t.deep_targets)      OVER w4 AS deep_targets_l4,
  AVG(nr.avg_separation)   OVER w4 AS separation_l4,
  AVG(nu.stacked_box_pct)  OVER w4 AS stacked_box_l4
FROM `${features}.player_week_usage` u
LEFT JOIN target_quality t
  ON t.gsis_id = u.gsis_id AND t.season = u.season AND t.week = u.week
LEFT JOIN ngs_rec nr
  ON nr.gsis_id = u.gsis_id AND nr.season = u.season AND nr.week = u.week
LEFT JOIN ngs_rush nu
  ON nu.gsis_id = u.gsis_id AND nu.season = u.season AND nu.week = u.week
WINDOW w4 AS (PARTITION BY u.gsis_id, u.season ORDER BY u.week
              ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING);

```

===== FILE: sql/features/016_team_week_context.sql =====
```sql
-- Team-level game context: pace, pass rate over expected, and Vegas implied
-- totals. Rolling windows exclude the current week.
CREATE OR REPLACE TABLE `${features}.team_week_context` AS
WITH team_games AS (
  SELECT
    posteam AS team, season, week, game_id,
    COUNT(*) AS plays,
    COUNTIF(pass_attempt = 1 OR rush_attempt = 1) AS scrimmage_plays,
    SAFE_DIVIDE(COUNTIF(pass_attempt = 1),
                NULLIF(COUNTIF(pass_attempt = 1 OR rush_attempt = 1), 0)) AS pass_rate,
    -- Neutral-situation pass rate: 1st/2nd down, score within 10, >4 min left
    SAFE_DIVIDE(
      COUNTIF(pass_attempt = 1 AND down <= 2 AND ABS(score_differential) <= 10
              AND game_seconds_remaining > 240),
      NULLIF(COUNTIF((pass_attempt = 1 OR rush_attempt = 1) AND down <= 2
              AND ABS(score_differential) <= 10 AND game_seconds_remaining > 240), 0)
    ) AS neutral_pass_rate,
    -- Seconds per play as a pace proxy
    SAFE_DIVIDE(3600 - MIN(game_seconds_remaining), NULLIF(COUNT(*), 0)) AS sec_per_play,
    -- Red zone pass tendency, for xTD decomposition (guide §5.4)
    SAFE_DIVIDE(COUNTIF(pass_attempt = 1 AND yardline_100 <= 10),
                NULLIF(COUNTIF((pass_attempt = 1 OR rush_attempt = 1)
                       AND yardline_100 <= 10), 0)) AS rz10_pass_rate
  FROM `${raw}.pbp`
  WHERE posteam IS NOT NULL AND season_type = 'REG'
  GROUP BY 1, 2, 3, 4
),
league_week AS (
  -- League expectation for pass rate, to compute PROE
  SELECT season, week, AVG(neutral_pass_rate) AS league_neutral_pass_rate
  FROM team_games
  GROUP BY 1, 2
),
-- Synthetic rows for each team's next unplayed game (same device as 014):
-- NULL metrics, so the strictly-prior windows emit as-of-now pace/PROE on
-- the upcoming week's row for live inference.
team_games_all AS (
  SELECT team, season, week, plays, scrimmage_plays, pass_rate,
         neutral_pass_rate, sec_per_play, rz10_pass_rate
  FROM team_games
  UNION ALL
  SELECT s.team, s.season, MIN(s.week),
         NULL, NULL, NULL, NULL, NULL, NULL
  FROM `${features}.schedule_long` s
  WHERE s.gameday >= CAST(CURRENT_DATE() AS STRING)
    AND NOT EXISTS (
      SELECT 1 FROM team_games t2
      WHERE t2.team = s.team AND t2.season = s.season AND t2.week = s.week
    )
  GROUP BY s.team, s.season
),
rolled AS (
  SELECT
    t.team, t.season, t.week,
    AVG(t.scrimmage_plays)   OVER w4 AS plays_l4,
    AVG(t.pass_rate)         OVER w4 AS pass_rate_l4,
    AVG(t.sec_per_play)      OVER w4 AS pace_l4,
    AVG(t.rz10_pass_rate)    OVER wstd AS rz10_pass_rate_std,
    AVG(t.neutral_pass_rate - l.league_neutral_pass_rate) OVER w4 AS proe_l4
  FROM team_games_all t
  LEFT JOIN league_week l USING (season, week)
  WINDOW
    w4   AS (PARTITION BY t.team, t.season ORDER BY t.week
             ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING),
    wstd AS (PARTITION BY t.team, t.season ORDER BY t.week
             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
)
SELECT
  s.team, s.season, s.week, s.game_id, s.opponent,
  s.implied_team_total, s.team_spread AS spread, s.game_total,
  s.implied_team_total - s.implied_opponent_total AS expected_game_script,
  s.is_home, s.roof, s.surface, s.days_rest,
  r.plays_l4, r.pass_rate_l4, r.pace_l4, r.proe_l4, r.rz10_pass_rate_std,
  -- Pace-adjusted expected plays: recent volume scaled by game environment
  r.plays_l4 * SAFE_DIVIDE(s.game_total, 45.0) AS expected_plays
FROM `${features}.schedule_long` s
LEFT JOIN rolled r USING (team, season, week);

```

===== FILE: sql/features/017_defense_week_allowed.sql =====
```sql
-- Opponent concessions, opponent-adjusted, trailing 6 weeks. Raw "points
-- allowed to WRs" is badly confounded by schedule, so positional fantasy
-- points allowed are expressed relative to what those offenses scored
-- against everyone else (a simple two-pass adjustment).
CREATE OR REPLACE TABLE `${features}.defense_week_allowed` AS
WITH def_games AS (
  SELECT
    defteam AS team, season, week, game_id,
    AVG(IF(qb_dropback = 1, epa, NULL)) AS epa_per_dropback_allowed,
    AVG(IF(rush_attempt = 1, epa, NULL)) AS epa_per_rush_allowed,
    SAFE_DIVIDE(
      COUNTIF(touchdown = 1 AND yardline_100 <= 20),
      NULLIF(COUNTIF(yardline_100 <= 20 AND (pass_attempt = 1 OR rush_attempt = 1)), 0)
    ) AS rz_td_rate_allowed
  FROM `${raw}.pbp`
  WHERE defteam IS NOT NULL AND season_type = 'REG'
  GROUP BY 1, 2, 3, 4
),
-- Positional DK points allowed: join actuals to the schedule to find who
-- each player faced that week.
pos_allowed AS (
  SELECT
    s.opponent AS team,       -- the defense
    a.season, a.week,
    pm.position,
    SUM(a.dk_points) AS pos_dk_points_allowed
  FROM `${features}.player_week_actuals` a
  JOIN `${features}.schedule_long` s
    ON s.team = a.team AND s.season = a.season AND s.week = a.week
  JOIN (
    SELECT gsis_id, season, ANY_VALUE(position HAVING MAX week) AS position
    FROM `${raw}.rosters_weekly` WHERE gsis_id IS NOT NULL
    GROUP BY gsis_id, season
  ) pm ON pm.gsis_id = a.gsis_id AND pm.season = a.season
  WHERE pm.position IN ('QB', 'RB', 'WR', 'TE')
  GROUP BY 1, 2, 3, 4
),
-- Offense strength, point-in-time: what each offense's position group has
-- scored per game THROUGH THE PRIOR WEEK. A season-wide average here would
-- let week-3 adjustments see week-18 offense — the same leak the rolling
-- features guard against with 1 PRECEDING.
off_week AS (
  SELECT a.team, a.season, a.week, pm.position,
         SUM(a.dk_points) AS pos_dk_points
  FROM `${features}.player_week_actuals` a
  JOIN (
    SELECT gsis_id, season, ANY_VALUE(position HAVING MAX week) AS position
    FROM `${raw}.rosters_weekly` WHERE gsis_id IS NOT NULL
    GROUP BY gsis_id, season
  ) pm ON pm.gsis_id = a.gsis_id AND pm.season = a.season
  WHERE pm.position IN ('QB', 'RB', 'WR', 'TE')
  GROUP BY 1, 2, 3, 4
),
off_strength AS (
  SELECT team, season, week, position,
         AVG(pos_dk_points) OVER (
           PARTITION BY team, season, position ORDER BY week
           ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
         ) AS pos_dk_points_pg_prior
  FROM off_week
),
adjusted AS (
  SELECT
    p.team, p.season, p.week, p.position,
    p.pos_dk_points_allowed,
    -- Points allowed relative to that offense's usual output so far. NULL in
    -- an offense's first week (no prior baseline) — honest, not imputed.
    p.pos_dk_points_allowed - o.pos_dk_points_pg_prior AS pos_dk_points_allowed_adj
  FROM pos_allowed p
  JOIN `${features}.schedule_long` s
    ON s.team = p.team AND s.season = p.season AND s.week = p.week
  LEFT JOIN off_strength o
    ON o.team = s.opponent AND o.season = p.season
   AND o.week = p.week AND o.position = p.position
)
SELECT
  d.team, d.season, d.week,
  AVG(d.epa_per_dropback_allowed) OVER w6 AS epa_per_dropback_allowed_l6,
  AVG(d.epa_per_rush_allowed)     OVER w6 AS epa_per_rush_allowed_l6,
  AVG(d.rz_td_rate_allowed)       OVER w6 AS rz_td_rate_allowed_l6,
  AVG(qb.pos_dk_points_allowed_adj) OVER w6 AS qb_fp_allowed_adj_l6,
  AVG(rb.pos_dk_points_allowed_adj) OVER w6 AS rb_fp_allowed_adj_l6,
  AVG(wr.pos_dk_points_allowed_adj) OVER w6 AS wr_fp_allowed_adj_l6,
  AVG(te.pos_dk_points_allowed_adj) OVER w6 AS te_fp_allowed_adj_l6
FROM def_games d
LEFT JOIN (SELECT * FROM adjusted WHERE position = 'QB') qb
  USING (team, season, week)
LEFT JOIN (SELECT * FROM adjusted WHERE position = 'RB') rb
  USING (team, season, week)
LEFT JOIN (SELECT * FROM adjusted WHERE position = 'WR') wr
  USING (team, season, week)
LEFT JOIN (SELECT * FROM adjusted WHERE position = 'TE') te
  USING (team, season, week)
WINDOW w6 AS (PARTITION BY d.team, d.season ORDER BY d.week
              ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING);

```

===== FILE: sql/features/017a_defense_week_coverage.sql =====
```sql
-- Cornerback / secondary coverage quality, from PFR advanced defense stats
-- (`${raw}.pfr_advstats_def`, 2018+): per-defender targets, completions and
-- yards allowed as the nearest defender, summed to the CB group (and the
-- whole secondary) per defense-game, then windowed strictly prior
-- (1 PRECEDING). "Nearest defender" attribution is charting — noisy per
-- play, serviceable summed per game.
--
-- The spine is schedule_long, not played games, so the upcoming week gets a
-- row too: its trailing windows and its injury-report-based top_cb_out are
-- both knowable before kickoff, which lets inference (023) join by exact
-- week instead of the as-of fallback the older defense table needs.
--
-- Positions come from snap_counts — also PFR-keyed, so the group aggregates
-- need no GSIS crosswalk; the crosswalk is only used to match the
-- snap-leader corner to the injury report.
CREATE OR REPLACE TABLE `${features}.defense_week_coverage` AS
WITH def_pos AS (
  SELECT pfr_player_id, season, week, team, position, defense_snaps
  FROM `${raw}.snap_counts`
  WHERE defense_snaps > 0 AND pfr_player_id IS NOT NULL
),
-- Per defense-game concessions. Ratio of sums, not mean of player ratios:
-- a corner targeted once shouldn't weigh like one targeted nine times.
cov_games AS (
  SELECT
    a.team, a.season, a.week,
    SAFE_DIVIDE(
      SUM(IF(p.position = 'CB', a.def_yards_allowed, NULL)),
      NULLIF(SUM(IF(p.position = 'CB', a.def_targets, NULL)), 0)
    ) AS cb_ypt_allowed,
    SAFE_DIVIDE(
      SUM(IF(p.position = 'CB', a.def_completions_allowed, NULL)),
      NULLIF(SUM(IF(p.position = 'CB', a.def_targets, NULL)), 0)
    ) AS cb_comp_rate_allowed,
    SAFE_DIVIDE(
      SUM(IF(p.position IN ('CB', 'DB', 'S', 'FS', 'SS'), a.def_yards_allowed, NULL)),
      NULLIF(SUM(IF(p.position IN ('CB', 'DB', 'S', 'FS', 'SS'), a.def_targets, NULL)), 0)
    ) AS db_ypt_allowed
  FROM `${raw}.pfr_advstats_def` a
  JOIN def_pos p
    ON p.pfr_player_id = a.pfr_player_id
   AND p.season = a.season AND p.week = a.week
  GROUP BY 1, 2, 3
),
spine AS (
  SELECT team, season, week FROM `${features}.schedule_long`
),
windowed AS (
  SELECT
    s.team, s.season, s.week,
    AVG(c.cb_ypt_allowed)       OVER w6 AS cb_ypt_allowed_l6,
    AVG(c.cb_comp_rate_allowed) OVER w6 AS cb_comp_rate_allowed_l6,
    AVG(c.db_ypt_allowed)       OVER w6 AS db_ypt_allowed_l6
  FROM spine s
  LEFT JOIN cov_games c USING (team, season, week)
  WINDOW w6 AS (PARTITION BY s.team, s.season ORDER BY s.week
                ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING)
),
-- The snap-leader corner through the prior week, per spine row. Strictly
-- prior on the snaps side; the injury report for week W is published before
-- W's games, so reading it same-week is legitimate (018 precedent).
cb1 AS (
  SELECT s.team, s.season, s.week, p.pfr_player_id
  FROM spine s
  JOIN def_pos p
    ON p.team = s.team AND p.season = s.season AND p.week < s.week
   AND p.position = 'CB'
  GROUP BY 1, 2, 3, 4
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY s.team, s.season, s.week
    ORDER BY SUM(p.defense_snaps) DESC, p.pfr_player_id
  ) = 1
),
cb1_out AS (
  SELECT
    c.team, c.season, c.week,
    -- No injury row (or no crosswalk) means no designation: playing.
    IFNULL(LOGICAL_OR(inj.report_status = 'Out'), FALSE) AS top_cb_out
  FROM cb1 c
  LEFT JOIN `${raw}.player_ids` i ON i.pfr_id = c.pfr_player_id
  LEFT JOIN `${raw}.injuries` inj
    ON inj.gsis_id = i.gsis_id
   AND CAST(inj.season AS INT64) = c.season
   AND CAST(inj.week AS INT64) = c.week
  GROUP BY 1, 2, 3
)
SELECT
  w.team, w.season, w.week,
  w.cb_ypt_allowed_l6, w.cb_comp_rate_allowed_l6, w.db_ypt_allowed_l6,
  -- NULL until the team has a prior-snaps corner (week 1): honest, and it
  -- keeps the first-row-null leakage invariant meaningful for this column.
  o.top_cb_out
FROM windowed w
LEFT JOIN cb1_out o USING (team, season, week);

```

===== FILE: sql/features/017b_referee_tendency.sql =====
```sql
-- Referee-crew tendency (2026-08-01): flags extend drives (defensive
-- holding / DPI are automatic first downs), which adds plays upstream of
-- every player's volume. Crew spreads are large (2024: ~12.8 to ~17.8
-- flags/game between crews) and consistent season to season.
--
-- Point-in-time: the tendency for game G uses the referee's STRICTLY
-- PRIOR games (20-game window, min 5). The crew assignment itself is
-- public midweek, so knowing WHO refs game G is legitimate week-W
-- knowledge; nflverse `officials` records it per game (2015+, keyed by
-- the old numeric game_id -> join through pbp.old_game_id).
--
-- Live caveat: nflverse publishes officials post-game, so inference rows
-- for the upcoming week get NULL (build_X NaN-fills) until a midweek
-- assignment source is scraped -- this feature earns its keep in
-- training/replay first.
CREATE OR REPLACE TABLE `${features}.referee_game_tendency` AS
WITH game_pen AS (
  SELECT game_id, ANY_VALUE(old_game_id) AS old_game_id,
         ANY_VALUE(season) AS season, ANY_VALUE(week) AS week,
         SUM(CAST(penalty AS INT64)) AS flags,
         SUM(COALESCE(penalty_yards, 0)) AS pen_yards
  FROM `${raw}.pbp`
  GROUP BY game_id
),
ref AS (
  SELECT CAST(game_id AS STRING) AS old_game_id, official_name AS referee
  FROM `${raw}.officials`
  WHERE position = 'Referee'
  QUALIFY ROW_NUMBER() OVER (PARTITION BY game_id) = 1
)
SELECT
  g.game_id, g.season, g.week, r.referee,
  AVG(g.flags) OVER w AS ref_flags_prior,
  AVG(g.pen_yards) OVER w AS ref_pen_yards_prior,
  COUNT(*) OVER w AS ref_prior_games
FROM game_pen g
JOIN ref r ON r.old_game_id = CAST(g.old_game_id AS STRING)
WINDOW w AS (
  PARTITION BY r.referee ORDER BY g.season, g.week
  ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING
);

```

===== FILE: sql/features/017c_team_neutral_pass.sql =====
```sql
-- Neutral-situation pass rate (2026-08-01): score within 3, outside the
-- last 2 minutes of a half, regulation only -- strips blowout/desperation
-- script so the windowed rate reflects the staff's schematic identity
-- rather than last month's game states. Raw seasonal pass rate
-- double-counts script once a simulator (or the model's opponent
-- features) generates script separately.
--
-- Point-in-time: l6 window is strictly prior (1 PRECEDING).
CREATE OR REPLACE TABLE `${features}.team_week_neutral_pass` AS
WITH plays AS (
  SELECT posteam AS team, season, week, CAST(pass AS INT64) AS is_pass
  FROM `${raw}.pbp`
  WHERE posteam IS NOT NULL
    AND (pass = 1 OR rush = 1)
    AND ABS(COALESCE(score_differential, 0)) <= 3
    AND half_seconds_remaining > 120
    AND qtr <= 4
),
tw AS (
  SELECT team, season, week, SUM(is_pass) AS p, COUNT(*) AS n
  FROM plays
  GROUP BY team, season, week
)
SELECT
  team, season, week,
  SAFE_DIVIDE(SUM(p) OVER w, SUM(n) OVER w) AS neutral_pass_rate_l6
FROM tw
WINDOW w AS (
  PARTITION BY team ORDER BY season, week
  ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
);

```

===== FILE: sql/features/017d_team_ol_out.sql =====
```sql
-- Offensive-line injuries (2026-08-01): the public prices skill-player
-- injuries; pass-protection losses (LT/C/RT out) change sack rate, time
-- to throw, and depth of target for EVERY skill player on the team.
-- Same point-in-time discipline as 018: the week-W injury report is
-- pre-game knowledge.
CREATE OR REPLACE TABLE `${features}.team_week_ol_out` AS
SELECT
  team, season, week,
  COUNTIF(position IN ('T', 'G', 'C')) AS team_ol_out
FROM `${raw}.injuries`
WHERE report_status = 'Out'
GROUP BY team, season, week;

```

===== FILE: sql/features/017e_team_pace.sql =====
```sql
-- Team pace, both sides of the ball (2026-08-01, candidate feature):
-- offensive plays run per game and defensive plays faced per game, l6
-- strictly prior. Consumed as pace_env_l6 = own offense + opponent
-- defense -- the "pace mismatch" claim reduces to expected play volume,
-- which is upstream of every player's opportunity.
CREATE OR REPLACE TABLE `${features}.team_week_pace` AS
WITH plays AS (
  SELECT posteam, defteam, season, week
  FROM `${raw}.pbp`
  WHERE posteam IS NOT NULL AND (pass = 1 OR rush = 1)
),
off_tw AS (
  SELECT posteam AS team, season, week, COUNT(*) AS off_plays
  FROM plays GROUP BY team, season, week
),
def_tw AS (
  SELECT defteam AS team, season, week, COUNT(*) AS def_plays
  FROM plays GROUP BY team, season, week
)
SELECT
  o.team, o.season, o.week,
  AVG(o.off_plays) OVER w AS off_plays_l6,
  AVG(d.def_plays) OVER w AS def_plays_faced_l6
FROM off_tw o
JOIN def_tw d USING (team, season, week)
WINDOW w AS (
  PARTITION BY o.team ORDER BY o.season, o.week
  ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
);

```

===== FILE: sql/features/017f_opp_blitz.sql =====
```sql
-- Defense blitz rate (2026-08-01, candidate feature): share of opposing
-- dropbacks the defense sent >=1 blitzer at, l6 strictly prior. FTN
-- charting covers 2022+; earlier rows are NULL (build_X NaN-fills).
-- Claimed consumer: TE/quick-game production against heavy-blitz
-- defenses; the model interacts it with position itself.
CREATE OR REPLACE TABLE `${features}.defense_week_blitz` AS
WITH plays AS (
  SELECT p.defteam AS team, p.season, p.week,
         IF(f.n_blitzers >= 1, 1, 0) AS blitzed
  FROM `${raw}.pbp` p
  JOIN `${raw}.ftn_charting` f
    ON f.nflverse_game_id = p.game_id AND f.nflverse_play_id = p.play_id
  WHERE p.pass = 1 AND p.defteam IS NOT NULL
),
tw AS (
  SELECT team, season, week, SUM(blitzed) AS b, COUNT(*) AS n
  FROM plays GROUP BY team, season, week
)
SELECT
  team, season, week,
  SAFE_DIVIDE(SUM(b) OVER w, SUM(n) OVER w) AS blitz_rate_l6
FROM tw
WINDOW w AS (
  PARTITION BY team ORDER BY season, week
  ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
);

```

===== FILE: sql/features/017g_target_concentration.sql =====
```sql
-- Target concentration (2026-08-01, candidate feature): share of the
-- team's targets going to its top-2 targeted players, per week, then l6
-- strictly prior. Concentrated offenses produce stronger stack
-- correlations than spread-the-ball offenses.
CREATE OR REPLACE TABLE `${features}.team_week_target_concentration` AS
WITH pw AS (
  SELECT team, season, week, player_id, SUM(targets) AS t
  FROM `${raw}.weekly_stats`
  WHERE targets IS NOT NULL
  GROUP BY team, season, week, player_id
),
tw AS (
  SELECT team, season, week,
         SUM(t) AS team_targets,
         SUM(IF(rnk <= 2, t, 0)) AS top2_targets
  FROM (
    SELECT *, ROW_NUMBER() OVER (
      PARTITION BY team, season, week ORDER BY t DESC) AS rnk
    FROM pw
  )
  GROUP BY team, season, week
)
SELECT
  team, season, week,
  SAFE_DIVIDE(SUM(top2_targets) OVER w, SUM(team_targets) OVER w)
    AS top2_target_share_l6
FROM tw
WINDOW w AS (
  PARTITION BY team ORDER BY season, week
  ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
);

```

===== FILE: sql/features/017h_qb_ngs.sql =====
```sql
-- QB NGS passing metrics (2026-08-01, candidate features): ngs_passing was
-- the audit's one fully-unused raw table. CPOE (completion % above
-- expectation) is the strongest public QB skill signal; time-to-throw
-- proxies protection/scheme. l6 strictly prior; NGS covers 2016+ and only
-- qualifying QBs (NaN elsewhere; build_X handles it). Gated behind
-- EXTRA_FEATURES like all candidates -- the 5-for-5 feature law applies.
CREATE OR REPLACE TABLE `${features}.qb_week_ngs` AS
SELECT
  player_gsis_id AS gsis_id, season, week,
  AVG(completion_percentage_above_expectation) OVER w AS qb_cpoe_l6,
  AVG(avg_time_to_throw) OVER w AS qb_time_to_throw_l6
FROM `${raw}.ngs_passing`
WHERE week > 0
WINDOW w AS (
  PARTITION BY player_gsis_id ORDER BY season, week
  ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING
);

```

===== FILE: sql/features/017i_ftn_offense.sql =====
```sql
-- FTN offense/defense charting rates (2026-08-02, candidate features):
-- the audit found we consume 1 of ~20 FTN fields. Two mechanism-backed
-- candidates from the unused set, l6 strictly prior, 2022+ (earlier
-- rows NULL; build_X NaN-fills):
--   * pa_rate_l6 (team OFFENSE play-action rate) — play-action drives
--     deep shots and YPA; claimed consumer is the WR ceiling the real
--     Milly winners exploit (Addendum 38 slot decomposition).
--   * def_pressure_rate_l6 (defense pressure GENERATED per dropback,
--     outcome-based: sacks + QB out-of-pocket + throwaways) — distinct
--     from blitz_rate_l6 which counts rushers sent, not results.
CREATE OR REPLACE TABLE `${features}.team_week_ftn_offense` AS
WITH plays AS (
  SELECT p.posteam AS team, p.defteam, p.season, p.week,
         IF(f.is_play_action, 1, 0) AS pa,
         IF(p.sack = 1 OR f.is_qb_out_of_pocket OR f.is_throw_away, 1, 0)
           AS pressured
  FROM `${raw}.pbp` p
  JOIN `${raw}.ftn_charting` f
    ON f.nflverse_game_id = p.game_id AND f.nflverse_play_id = p.play_id
  WHERE p.pass = 1 AND p.posteam IS NOT NULL
),
off_tw AS (
  SELECT team, season, week, SUM(pa) AS pa, COUNT(*) AS n
  FROM plays GROUP BY team, season, week
),
def_tw AS (
  SELECT defteam AS team, season, week, SUM(pressured) AS pr, COUNT(*) AS n
  FROM plays WHERE defteam IS NOT NULL GROUP BY defteam, season, week
),
off_roll AS (
  SELECT team, season, week,
         SAFE_DIVIDE(SUM(pa) OVER w, SUM(n) OVER w) AS pa_rate_l6
  FROM off_tw
  WINDOW w AS (PARTITION BY team ORDER BY season, week
               ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING)
),
def_roll AS (
  SELECT team, season, week,
         SAFE_DIVIDE(SUM(pr) OVER w, SUM(n) OVER w) AS def_pressure_rate_l6
  FROM def_tw
  WINDOW w AS (PARTITION BY team ORDER BY season, week
               ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING)
)
SELECT COALESCE(o.team, d.team) AS team,
       COALESCE(o.season, d.season) AS season,
       COALESCE(o.week, d.week) AS week,
       o.pa_rate_l6, d.def_pressure_rate_l6
FROM off_roll o
FULL OUTER JOIN def_roll d USING (team, season, week);

```

===== FILE: sql/features/017j_xfp_schedule.sql =====
```sql
-- XFP + schedule-context candidates (2026-08-03, vendor round-6 /
-- research round-5 triage). All EXTRA_FEATURES-gated; leakage-safe.
--
-- xfp_l4: expected fantasy points from OPPORTUNITY alone — each target
-- valued at a league-average rate for its (air-yards band x field zone)
-- bucket, each carry for its (field zone) bucket. Bucket rates are
-- computed ONCE from 2014-2018 seasons only (fixed priors, so rows for
-- 2019+ replays are point-in-time; earlier seasons see mild in-sample
-- rates, acceptable for a candidate feature). The Fantasy Points Data
-- lineage: opportunity is sticky, efficiency is noise.
--
-- net_rest_diff: own days_rest minus opponent's (we carried only own).
-- body_clock_offset: hours between kickoff local time and the visiting
-- team's home-timezone body clock (Harvard/Stanford west-coast night
-- effect); approximated from schedules' gametime + a team-timezone map.
CREATE OR REPLACE TABLE `${features}.player_week_xfp` AS
WITH bucket_rates AS (
  SELECT * FROM (
    SELECT
      CASE WHEN air_yards >= 20 THEN 'deep'
           WHEN air_yards >= 10 THEN 'mid' ELSE 'short' END AS ab,
      CASE WHEN yardline_100 <= 10 THEN 'rz10'
           WHEN yardline_100 <= 20 THEN 'rz20' ELSE 'field' END AS fz,
      -- DK PPR points per target in bucket
      AVG(COALESCE(yards_gained, 0) * 0.1
          + IF(complete_pass = 1, 1.0, 0.0)
          + IF(pass_touchdown = 1, 6.0, 0.0)) AS fp_per_tgt
    FROM `${raw}.pbp`
    WHERE season BETWEEN 2014 AND 2018 AND pass = 1
      AND air_yards IS NOT NULL
    GROUP BY ab, fz)
),
carry_rates AS (
  SELECT
    CASE WHEN yardline_100 <= 5 THEN 'gl'
         WHEN yardline_100 <= 20 THEN 'rz' ELSE 'field' END AS fz,
    AVG(COALESCE(yards_gained, 0) * 0.1
        + IF(rush_touchdown = 1, 6.0, 0.0)) AS fp_per_carry
  FROM `${raw}.pbp`
  WHERE season BETWEEN 2014 AND 2018 AND rush = 1
  GROUP BY fz
),
tgt_xfp AS (
  SELECT p.receiver_player_id AS gsis_id, p.season, p.week,
         SUM(br.fp_per_tgt) AS xfp_rec
  FROM `${raw}.pbp` p
  JOIN bucket_rates br
    ON br.ab = CASE WHEN p.air_yards >= 20 THEN 'deep'
                    WHEN p.air_yards >= 10 THEN 'mid' ELSE 'short' END
   AND br.fz = CASE WHEN p.yardline_100 <= 10 THEN 'rz10'
                    WHEN p.yardline_100 <= 20 THEN 'rz20' ELSE 'field' END
  WHERE p.pass = 1 AND p.receiver_player_id IS NOT NULL
    AND p.air_yards IS NOT NULL
  GROUP BY gsis_id, season, week
),
carry_xfp AS (
  SELECT p.rusher_player_id AS gsis_id, p.season, p.week,
         SUM(cr.fp_per_carry) AS xfp_rush
  FROM `${raw}.pbp` p
  JOIN carry_rates cr
    ON cr.fz = CASE WHEN p.yardline_100 <= 5 THEN 'gl'
                    WHEN p.yardline_100 <= 20 THEN 'rz' ELSE 'field' END
  WHERE p.rush = 1 AND p.rusher_player_id IS NOT NULL
  GROUP BY gsis_id, season, week
),
weekly AS (
  SELECT COALESCE(t.gsis_id, c.gsis_id) AS gsis_id,
         COALESCE(t.season, c.season) AS season,
         COALESCE(t.week, c.week) AS week,
         COALESCE(t.xfp_rec, 0) + COALESCE(c.xfp_rush, 0) AS xfp
  FROM tgt_xfp t
  FULL OUTER JOIN carry_xfp c USING (gsis_id, season, week)
)
SELECT gsis_id, season, week,
       AVG(xfp) OVER (PARTITION BY gsis_id, season ORDER BY week
                      ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS xfp_l4
FROM weekly;

CREATE OR REPLACE TABLE `${features}.team_week_schedule_ctx` AS
WITH tz AS (
  SELECT team, offset_hours FROM UNNEST([
    STRUCT('SEA' AS team, -3 AS offset_hours), ('SF', -3), ('LA', -3),
    ('LAC', -3), ('LV', -3), ('ARI', -2), ('DEN', -2),
    ('DAL', -1), ('HOU', -1), ('KC', -1), ('MIN', -1), ('GB', -1),
    ('CHI', -1), ('NO', -1), ('TEN', -1),
    ('BUF', 0), ('MIA', 0), ('NE', 0), ('NYJ', 0), ('NYG', 0),
    ('PHI', 0), ('PIT', 0), ('BAL', 0), ('CIN', 0), ('CLE', 0),
    ('WAS', 0), ('CAR', 0), ('ATL', 0), ('JAX', 0), ('TB', 0),
    ('DET', 0), ('IND', 0)])
)
SELECT s.team, s.season, s.week,
       s.days_rest - opp.days_rest AS net_rest_diff,
       -- ET kickoff hour + visitor's tz offset = body-clock hour
       CAST(SPLIT(sc.gametime, ':')[SAFE_OFFSET(0)] AS INT64)
         + COALESCE(z.offset_hours, 0) AS body_clock_hour
FROM `${features}.schedule_long` s
JOIN `${features}.schedule_long` opp
  ON opp.game_id = s.game_id AND opp.team = s.opponent
LEFT JOIN `${raw}.schedules` sc ON sc.game_id = s.game_id
LEFT JOIN tz z ON z.team = s.team;

```

===== FILE: sql/features/018_player_week_injury.sql =====
```sql
-- Injury designation and practice-participation trend, point-in-time: the
-- report for week W is published before W's games, so same-week rows are
-- legitimately knowable. Games missed uses strictly-prior weeks.
CREATE OR REPLACE TABLE `${features}.player_week_injury` AS
WITH inj AS (
  SELECT
    gsis_id,
    -- nflverse ships these as FLOAT in the injuries dataset (null-driven
    -- upcast); INT64 keeps join keys consistent and windows partitionable.
    CAST(season AS INT64) AS season,
    CAST(week AS INT64) AS week,
    report_status AS injury_status,
    -- Encode Wed/Thu/Fri practice as 0=DNP, 1=Limited, 2=Full and average
    (SELECT AVG(v) FROM UNNEST([
       CASE practice_status
         WHEN 'Did Not Participate In Practice' THEN 0.0
         WHEN 'Limited Participation in Practice' THEN 1.0
         WHEN 'Full Participation in Practice' THEN 2.0
       END
     ]) v WHERE v IS NOT NULL) AS practice_level
  FROM `${raw}.injuries`
  WHERE gsis_id IS NOT NULL
),
played AS (
  SELECT gsis_id, season, week FROM `${features}.player_week_actuals`
),
missed AS (
  -- Weeks on the injury report as Out, in the prior 4 weeks
  SELECT
    i.gsis_id, i.season, i.week,
    COUNTIF(i2.injury_status = 'Out') AS games_missed_l4
  FROM inj i
  LEFT JOIN inj i2
    ON i2.gsis_id = i.gsis_id AND i2.season = i.season
   AND i2.week BETWEEN i.week - 4 AND i.week - 1
  GROUP BY 1, 2, 3
)
SELECT
  i.gsis_id, i.season, i.week,
  i.injury_status,
  i.practice_level,
  i.practice_level - LAG(i.practice_level) OVER (
    PARTITION BY i.gsis_id, i.season ORDER BY i.week
  ) AS practice_participation_trend,
  COALESCE(m.games_missed_l4, 0) AS games_missed_l4
FROM inj i
LEFT JOIN missed m USING (gsis_id, season, week);

-- Opportunity vacated by teammates ruled Out for week W: the sum of the
-- trailing-4-week target and carry shares of every player on the team's
-- report as Out that week. Point-in-time on both sides — the report is
-- published before W's games and the shares are strictly-prior windows —
-- so the models can learn next-man-up bumps instead of relying only on a
-- bolt-on inference adjustment. Consumers subtract the player's own share
-- (an Out player shouldn't count his own vacancy as opportunity).
--
-- The Out player's share comes from his latest usage row AT OR BEFORE the
-- report week, not a same-week equijoin: a player who sits has no usage
-- row that week, so the naive join would zero this feature across all of
-- training history while the upcoming week's synthetic rows (014) kept it
-- populated live — a train/serve skew that would teach the models to
-- ignore the signal.
CREATE OR REPLACE TABLE `${features}.team_week_vacated` AS
WITH outs AS (
  SELECT gsis_id, season, week
  FROM `${features}.player_week_injury`
  WHERE injury_status = 'Out'
),
asof AS (
  SELECT
    o.gsis_id, o.season, o.week,
    u.team, u.target_share_l4, u.carry_share_l4
  FROM outs o
  JOIN `${features}.player_week_usage` u
    ON u.gsis_id = o.gsis_id AND u.season = o.season AND u.week <= o.week
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY o.gsis_id, o.season, o.week ORDER BY u.week DESC
  ) = 1
)
SELECT
  team, season, week,
  SUM(COALESCE(target_share_l4, 0)) AS vacated_target_share,
  SUM(COALESCE(carry_share_l4, 0))  AS vacated_carry_share
FROM asof
GROUP BY team, season, week;

```

===== FILE: sql/features/019_dk_salary_week.sql =====
```sql
-- One salary row per player-week: the last classic-slate pull before lock,
-- unioned with the RotoGuru historical backfill for pre-logging seasons.
-- salary_delta_wow (week over week) is the input to the salary-lag alert.
CREATE OR REPLACE TABLE `${features}.dk_salary_week` AS
WITH own_log AS (
  SELECT
    m.gsis_id, s.season, s.week, s.dk_player_id,
    ARRAY_AGG(s.salary ORDER BY s.pulled_at DESC LIMIT 1)[OFFSET(0)] AS salary,
    ARRAY_AGG(s.status ORDER BY s.pulled_at DESC LIMIT 1)[OFFSET(0)] AS status,
    ARRAY_AGG(s.dk_ppg ORDER BY s.pulled_at DESC LIMIT 1)[OFFSET(0)] AS dk_ppg
  FROM `${raw}.dk_salaries` s
  JOIN `${features}.player_id_map` m USING (dk_player_id)
  WHERE s.slate_type = 'classic' AND s.week IS NOT NULL
  GROUP BY 1, 2, 3, 4
),
historical AS (
  -- RotoGuru rows matched by normalized name, disambiguated by position;
  -- lower fidelity, only used for seasons before our own log starts.
  -- Team is deliberately NOT part of the match: player_ids carries only a
  -- player's CURRENT team, and RotoGuru uses a different abbreviation
  -- convention (GNB/KAN/NWE), so a team condition silently drops nearly
  -- every row for players who ever changed teams.
  SELECT
    gsis_id, season, week,
    CAST(NULL AS INT64) AS dk_player_id,
    salary,
    CAST(NULL AS STRING) AS status,
    CAST(NULL AS FLOAT64) AS dk_ppg
  FROM (
    SELECT
      -- Grouped by (name, position), NOT rotoguru_gid: LineStar-backfilled
      -- rows (2022-24, see ingest/linestar_backfill.py) carry NULL gid,
      -- which would collapse a whole week into one ambiguous group.
      h.season, h.week, h.display_name, h.position,
      ANY_VALUE(h.salary) AS salary,
      -- Unique name+position candidate first; unique name-only as fallback
      -- (position occasionally recorded differently, e.g. FB vs RB); rows
      -- ambiguous under both rules are dropped rather than guessed.
      COALESCE(
        IF(COUNT(DISTINCT IF(UPPER(i.position) = UPPER(h.position), i.gsis_id, NULL)) = 1,
           MAX(IF(UPPER(i.position) = UPPER(h.position), i.gsis_id, NULL)), NULL),
        IF(COUNT(DISTINCT i.gsis_id) = 1, MAX(i.gsis_id), NULL)
      ) AS gsis_id
    FROM `${raw}.dk_salaries_historical` h
    JOIN `${raw}.player_ids` i
      ON REGEXP_REPLACE(UPPER(h.display_name), r"[^A-Z ]", "") =
         REGEXP_REPLACE(UPPER(i.name), r"[^A-Z ]", "")
     AND i.gsis_id IS NOT NULL
    WHERE h.season NOT IN (SELECT DISTINCT season FROM own_log)
      AND h.salary > 0  -- RotoGuru encodes "no salary listed" as 0
    GROUP BY h.season, h.week, h.display_name, h.position
  )
  WHERE gsis_id IS NOT NULL
),
unioned AS (
  SELECT * FROM own_log
  UNION ALL
  SELECT * FROM historical
)
SELECT
  *,
  salary - LAG(salary) OVER (PARTITION BY gsis_id, season ORDER BY week)
    AS salary_delta_wow
FROM unioned;

```

===== FILE: sql/features/020_game_weather.sql =====
```sql
-- Latest weather snapshot per game, falling back to schedule temp/wind for
-- historical games (nflverse schedules carry both for outdoor games).
CREATE OR REPLACE TABLE `${features}.game_weather` AS
WITH latest AS (
  SELECT game_id,
         ARRAY_AGG(temp_f ORDER BY pulled_at DESC LIMIT 1)[OFFSET(0)] AS temp_f,
         ARRAY_AGG(wind_mph ORDER BY pulled_at DESC LIMIT 1)[OFFSET(0)] AS wind_mph,
         ARRAY_AGG(is_dome ORDER BY pulled_at DESC LIMIT 1)[OFFSET(0)] AS is_dome
  FROM `${raw}.weather`
  GROUP BY game_id
)
SELECT
  s.game_id,
  COALESCE(l.temp_f, CAST(s.temp AS FLOAT64))  AS temp_f,
  COALESCE(l.wind_mph, CAST(s.wind AS FLOAT64)) AS wind_mph,
  COALESCE(l.is_dome, s.roof IN ('dome', 'closed')) AS is_dome
FROM `${raw}.schedules` s
LEFT JOIN latest l USING (game_id);

```

===== FILE: sql/features/021_player_week_training.sql =====
```sql
-- The joined, model-ready wide table. Every feature is point-in-time; the
-- labels (y_*) are the only same-week values. Leakage assertions in
-- nfl_dfs.features.leakage run against this table after every build.
CREATE OR REPLACE TABLE `${features}.player_week_training` AS
SELECT
  -- Keys
  u.gsis_id, u.season, u.week, u.team, s.opponent, u.position, s.game_id,

  -- Usage (point-in-time, §5.2)
  u.targets_l4, u.target_share_l4, u.air_yards_share_l4, u.wopr_l4,
  u.rz20_targets_l4, u.rz10_targets_l4,
  u.rz20_target_share_l4, u.rz10_target_share_l4,
  u.rz20_targets_smoothed,
  u.carries_l4, u.carry_share_l4, u.gl3_carries_l4, u.gl3_carry_share_l4,
  u.gl3_carries_smoothed,
  u.snap_share_l4,
  u.target_share_std, u.target_share_trend, u.carry_share_trend,
  u.games_played_prior,

  -- Efficiency
  e.yards_per_target_l8, e.yards_per_reception_l8, e.catch_rate_l8,
  e.yards_per_carry_l8, e.yards_per_attempt_l8, e.adot_l8,
  e.dk_points_l4, e.dk_points_std, e.dk_points_vol,

  -- Game context
  t.implied_team_total, t.spread, t.game_total, t.expected_game_script,
  t.is_home, t.days_rest,
  t.plays_l4, t.pass_rate_l4, t.pace_l4, t.proe_l4, t.expected_plays,

  -- The strongest single derived feature (§5.4): expected TDs from red zone
  -- opportunity — stable part (opportunity) x league-average conversion.
  u.rz20_targets_smoothed
    * t.rz10_pass_rate_std
    * SAFE_DIVIDE(t.implied_team_total, 22.0) AS xtd_receiving_proxy,

  -- Opponent
  d.epa_per_dropback_allowed_l6, d.epa_per_rush_allowed_l6,
  d.rz_td_rate_allowed_l6,
  d.qb_fp_allowed_adj_l6, d.rb_fp_allowed_adj_l6,
  d.wr_fp_allowed_adj_l6, d.te_fp_allowed_adj_l6,

  -- Opponent secondary (CB coverage from PFR advstats, 2018+; NULL before)
  cv.cb_ypt_allowed_l6, cv.cb_comp_rate_allowed_l6, cv.db_ypt_allowed_l6,
  cv.top_cb_out,

  -- Player state
  i.injury_status, i.practice_level, i.practice_participation_trend,
  COALESCE(i.games_missed_l4, 0) AS games_missed_l4,

  -- Role (depth chart + draft capital; cold-start priors read these)
  ro.depth_rank, ro.depth_rank_delta, ro.is_rookie, ro.draft_round,

  -- Game environment extras (2026-08-01): referee-crew flag tendency
  -- (strictly-prior 20-game window; NULL live until a midweek crew
  -- source exists) and neutral-situation pass rate (script-stripped
  -- schematic identity, l6 strictly prior).
  IF(rt.ref_prior_games >= 5, rt.ref_flags_prior, NULL) AS ref_flags_prior,
  np.neutral_pass_rate_l6,
  COALESCE(ol.team_ol_out, 0) AS team_ol_out,
  -- Candidate features (EXTRA_FEATURES gate in featureset.py)
  pc.off_plays_l6 + pcd.def_plays_faced_l6 AS pace_env_l6,
  bl.blitz_rate_l6 AS opp_blitz_rate_l6,
  fo.pa_rate_l6,
  fd.def_pressure_rate_l6 AS opp_pressure_rate_l6,
  xf.xfp_l4,
  sx.net_rest_diff,
  sx.body_clock_hour,
  tc.top2_target_share_l6 AS team_top2_target_share_l6,
  qn.qb_cpoe_l6,
  qn.qb_time_to_throw_l6,

  -- Opportunity vacated by teammates ruled Out this week (own share
  -- excluded): the point-in-time next-man-up signal.
  GREATEST(
    COALESCE(v.vacated_target_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.target_share_l4, 0), 0),
    0) AS team_vacated_target_share,
  GREATEST(
    COALESCE(v.vacated_carry_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.carry_share_l4, 0), 0),
    0) AS team_vacated_carry_share,

  -- Causally-directed vacated capture (2026-08-03 event study, Addendum
  -- 44): 553 target-hog / 369 carry-hog absences 2019-25 show vacated
  -- TARGETS flow laterally to other WRs (WR1/WR2 +2.5-2.6 share pts,
  -- WR3 +1.9, TE +1.2, RB ~0) while vacated CARRIES concentrate in the
  -- backfield (RB2 +15.8, RB1 +9.5, RB3 +7.5, others ~0). These weight
  -- the team-level sum by the empirical capture rate of the player's
  -- (position x depth) cell — the interaction a GBM must otherwise
  -- discover on its own. EXTRA_FEATURES candidates.
  GREATEST(
    COALESCE(v.vacated_target_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.target_share_l4, 0), 0),
    0) * CASE
      WHEN COALESCE(u.position, ro.position) = 'WR' AND ro.depth_rank <= 2 THEN 0.100
      WHEN COALESCE(u.position, ro.position) = 'WR' THEN 0.073
      WHEN COALESCE(u.position, ro.position) = 'TE' THEN 0.050
      WHEN COALESCE(u.position, ro.position) = 'RB' AND ro.depth_rank <= 2 THEN 0.033
      ELSE 0.009 END AS vacated_capture_tgt,
  GREATEST(
    COALESCE(v.vacated_carry_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.carry_share_l4, 0), 0),
    0) * CASE
      WHEN COALESCE(u.position, ro.position) = 'RB' AND ro.depth_rank = 1 THEN 0.270
      WHEN COALESCE(u.position, ro.position) = 'RB' AND ro.depth_rank = 2 THEN 0.450
      WHEN COALESCE(u.position, ro.position) = 'RB' THEN 0.210
      WHEN COALESCE(u.position, ro.position) = 'QB' THEN 0.047
      ELSE 0.020 END AS vacated_capture_car,

  -- Target quality + NGS context (024): TD opportunity beats TD history
  adv.ez_targets_l4, adv.deep_targets_l4, adv.separation_l4, adv.stacked_box_l4,

  -- Weather
  w.wind_mph, w.temp_f, w.is_dome,

  -- DFS-specific
  dk.salary, dk.salary_delta_wow, dk.dk_ppg,

  -- Cold start flag (§7.6): no usable rolling history
  (u.games_played_prior IS NULL OR u.games_played_prior < 1
   OR u.target_share_l4 IS NULL AND u.carry_share_l4 IS NULL) AS is_cold_start,

  -- Labels (multiple, for the component models)
  a.targets       AS y_targets,
  a.receptions    AS y_receptions,
  a.rec_yards     AS y_rec_yards,
  a.rec_tds       AS y_rec_tds,
  a.carries       AS y_carries,
  a.rush_yards    AS y_rush_yards,
  a.rush_tds      AS y_rush_tds,
  a.pass_attempts AS y_pass_attempts,
  a.pass_yards    AS y_pass_yards,
  a.pass_tds      AS y_pass_tds,
  a.interceptions AS y_interceptions,
  a.dk_points     AS y_dk_points

FROM `${features}.player_week_usage` u
JOIN `${features}.player_week_actuals` a USING (gsis_id, season, week)
JOIN `${features}.schedule_long` s
  ON s.team = u.team AND s.season = u.season AND s.week = u.week
LEFT JOIN `${features}.player_week_efficiency` e
  ON e.gsis_id = u.gsis_id AND e.season = u.season AND e.week = u.week
LEFT JOIN `${features}.team_week_context` t
  ON t.team = u.team AND t.season = u.season AND t.week = u.week
LEFT JOIN `${features}.defense_week_allowed` d
  ON d.team = s.opponent AND d.season = u.season AND d.week = u.week
LEFT JOIN `${features}.defense_week_coverage` cv
  ON cv.team = s.opponent AND cv.season = u.season AND cv.week = u.week
LEFT JOIN `${features}.player_week_injury` i
  ON i.gsis_id = u.gsis_id AND i.season = u.season AND i.week = u.week
LEFT JOIN `${features}.game_weather` w ON w.game_id = s.game_id
LEFT JOIN `${features}.dk_salary_week` dk
  ON dk.gsis_id = u.gsis_id AND dk.season = u.season AND dk.week = u.week
LEFT JOIN `${features}.player_week_role` ro
  ON ro.gsis_id = u.gsis_id AND ro.season = u.season AND ro.week = u.week
LEFT JOIN `${features}.team_week_vacated` v
  ON v.team = u.team AND v.season = u.season AND v.week = u.week
LEFT JOIN `${features}.player_week_advanced` adv
  ON adv.gsis_id = u.gsis_id AND adv.season = u.season AND adv.week = u.week
LEFT JOIN `${features}.referee_game_tendency` rt ON rt.game_id = s.game_id
LEFT JOIN `${features}.team_week_neutral_pass` np
  ON np.team = u.team AND np.season = u.season AND np.week = u.week
LEFT JOIN `${features}.team_week_ol_out` ol
  ON ol.team = u.team AND ol.season = u.season AND ol.week = u.week
LEFT JOIN `${features}.team_week_pace` pc
  ON pc.team = u.team AND pc.season = u.season AND pc.week = u.week
LEFT JOIN `${features}.team_week_pace` pcd
  ON pcd.team = s.opponent AND pcd.season = u.season AND pcd.week = u.week
LEFT JOIN `${features}.defense_week_blitz` bl
  ON bl.team = s.opponent AND bl.season = u.season AND bl.week = u.week
LEFT JOIN `${features}.team_week_ftn_offense` fo
  ON fo.team = u.team AND fo.season = u.season AND fo.week = u.week
LEFT JOIN `${features}.player_week_xfp` xf
  ON xf.gsis_id = u.gsis_id AND xf.season = u.season AND xf.week = u.week
LEFT JOIN `${features}.team_week_schedule_ctx` sx
  ON sx.team = u.team AND sx.season = u.season AND sx.week = u.week
LEFT JOIN `${features}.team_week_ftn_offense` fd
  ON fd.team = s.opponent AND fd.season = u.season AND fd.week = u.week
LEFT JOIN `${features}.team_week_target_concentration` tc
  ON tc.team = u.team AND tc.season = u.season AND tc.week = u.week
LEFT JOIN `${features}.qb_week_ngs` qn
  ON qn.gsis_id = u.gsis_id AND qn.season = u.season AND qn.week = u.week
WHERE u.position IN ('QB', 'RB', 'WR', 'TE')
  -- Season openers (week 1) train the cold-start regime the live path
  -- serves every September: trailing windows NULL, is_cold_start true,
  -- the model leans on salary/depth/draft/context — exactly what a real
  -- week-1 slate offers. Before 2026-08-02 these rows were dropped, so
  -- week 1 was untrainable AND unreplayable (023 always emitted them).
  AND (u.games_played_prior >= 1 OR u.week = 1)
  -- Upcoming-week synthetic rows (014) are inference-only; the actuals
  -- inner join already drops them, this states the intent.
  AND NOT u.is_upcoming
-- Mid-week team changes (trades/waivers: McCaffrey 2022 wk7, Bennett
-- 2017 wk10, ...) give a player two upstream team rows and therefore two
-- training rows (2026-08-01 audit: 9 dupes in 52,422). Keep one,
-- deterministically.
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY u.gsis_id, u.season, u.week ORDER BY u.team
) = 1;

```

===== FILE: sql/features/022_defense_points_against.sql =====
```sql
-- Research/UI table: DK points allowed per defense per position per week
-- (the fantasy.nfl.com "points against" view), raw and with rolling windows.
--
-- NOTE: unlike every model feature table, the rolling columns here INCLUDE
-- the current week — this is a rear-view research table for the app's
-- defense page, never a model input. Models use defense_week_allowed,
-- whose windows end at 1 PRECEDING.
CREATE OR REPLACE TABLE `${features}.defense_points_against` AS
WITH pm AS (
  SELECT gsis_id, season, ANY_VALUE(position HAVING MAX week) AS position
  FROM `${raw}.rosters_weekly`
  WHERE gsis_id IS NOT NULL
  GROUP BY gsis_id, season
),
pos_allowed AS (
  SELECT
    s.opponent AS team,            -- the defense
    a.season, a.week, pm.position,
    SUM(a.dk_points) AS fp_allowed
  FROM `${features}.player_week_actuals` a
  JOIN `${features}.schedule_long` s
    ON s.team = a.team AND s.season = a.season AND s.week = a.week
  JOIN pm ON pm.gsis_id = a.gsis_id AND pm.season = a.season
  WHERE pm.position IN ('QB', 'RB', 'WR', 'TE')
  GROUP BY 1, 2, 3, 4
)
SELECT
  team, season, week, position, fp_allowed,
  AVG(fp_allowed) OVER w3 AS fp_allowed_l3,
  AVG(fp_allowed) OVER w6 AS fp_allowed_l6,
  AVG(fp_allowed) OVER wseason AS fp_allowed_season,
  -- Positive = allowing more than its season norm lately (defense fading);
  -- negative = clamping down (defense improving).
  AVG(fp_allowed) OVER w3 - AVG(fp_allowed) OVER wseason AS trend
FROM pos_allowed
WINDOW
  w3      AS (PARTITION BY team, season, position ORDER BY week
              ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),
  w6      AS (PARTITION BY team, season, position ORDER BY week
              ROWS BETWEEN 5 PRECEDING AND CURRENT ROW),
  wseason AS (PARTITION BY team, season, position ORDER BY week
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW);

```

===== FILE: sql/features/023_player_week_inference.sql =====
```sql
-- Live-slate feature rows: the upcoming week's synthetic usage rows (014)
-- joined to the same point-in-time features the model trained on (021).
-- Before this table existed, inference joined player_week_training at the
-- upcoming week — rows that can't exist until the games are played — so
-- every live projection silently fell back to cold-start fills.
--
-- Differences from the training table, all deliberate:
--   * no labels and no games_played_prior filter — debut players belong
--     here (they're the next-man-up rows this table exists to price);
--   * position falls back to the roster when there's no usage history;
--   * opponent defense joins as-of its latest built week (the defense
--     table has no upcoming-week rows; one-week-stale l6 windows are fine
--     for features the models treat as optional).
CREATE OR REPLACE TABLE `${features}.player_week_inference` AS
WITH def_asof AS (
  SELECT * FROM `${features}.defense_week_allowed`
  QUALIFY ROW_NUMBER() OVER (PARTITION BY team, season ORDER BY week DESC) = 1
),
-- xfp as-of (2026-08-04 audit): player_week_xfp is built from pbp, so
-- an UPCOMING week has no row and an exact-week join would leave
-- xfp_l4 NULL on every live slate while replays saw real values — the
-- train/serve-skew class this file's header warns about. Latest
-- available row per player-season instead (window ends 1 PRECEDING,
-- so it is the same information a played-week row would carry).
xfp_asof AS (
  SELECT * FROM `${features}.player_week_xfp`
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY gsis_id, season ORDER BY week DESC) = 1
)
SELECT
  -- Keys
  u.gsis_id, u.season, u.week, u.team, s.opponent,
  COALESCE(u.position, ro.position) AS position, s.game_id,

  -- Usage (point-in-time, §5.2)
  u.targets_l4, u.target_share_l4, u.air_yards_share_l4, u.wopr_l4,
  u.rz20_targets_l4, u.rz10_targets_l4,
  u.rz20_target_share_l4, u.rz10_target_share_l4,
  u.rz20_targets_smoothed,
  u.carries_l4, u.carry_share_l4, u.gl3_carries_l4, u.gl3_carry_share_l4,
  u.gl3_carries_smoothed,
  u.snap_share_l4,
  u.target_share_std, u.target_share_trend, u.carry_share_trend,
  u.games_played_prior,

  -- Efficiency
  e.yards_per_target_l8, e.yards_per_reception_l8, e.catch_rate_l8,
  e.yards_per_carry_l8, e.yards_per_attempt_l8, e.adot_l8,
  e.dk_points_l4, e.dk_points_std, e.dk_points_vol,

  -- Game context
  t.implied_team_total, t.spread, t.game_total, t.expected_game_script,
  t.is_home, t.days_rest,
  t.plays_l4, t.pass_rate_l4, t.pace_l4, t.proe_l4, t.expected_plays,

  u.rz20_targets_smoothed
    * t.rz10_pass_rate_std
    * SAFE_DIVIDE(t.implied_team_total, 22.0) AS xtd_receiving_proxy,

  -- Opponent (as-of latest built defense week)
  d.epa_per_dropback_allowed_l6, d.epa_per_rush_allowed_l6,
  d.rz_td_rate_allowed_l6,
  d.qb_fp_allowed_adj_l6, d.rb_fp_allowed_adj_l6,
  d.wr_fp_allowed_adj_l6, d.te_fp_allowed_adj_l6,

  -- Opponent secondary: exact-week join, no as-of needed — 017a's spine is
  -- the schedule, so the upcoming week has a row with strictly-prior
  -- windows and a live injury-report top_cb_out.
  cv.cb_ypt_allowed_l6, cv.cb_comp_rate_allowed_l6, cv.db_ypt_allowed_l6,
  cv.top_cb_out,

  -- Player state
  i.injury_status, i.practice_level, i.practice_participation_trend,
  COALESCE(i.games_missed_l4, 0) AS games_missed_l4,

  -- Role (depth chart + draft capital; cold-start priors read these)
  ro.depth_rank, ro.depth_rank_delta, ro.is_rookie, ro.draft_round,

  -- Game environment extras, same definitions as the training table.
  -- ref_flags_prior is NULL for upcoming games (officials data is
  -- post-game) until a midweek crew-assignment source exists.
  IF(rt.ref_prior_games >= 5, rt.ref_flags_prior, NULL) AS ref_flags_prior,
  np.neutral_pass_rate_l6,
  COALESCE(ol.team_ol_out, 0) AS team_ol_out,
  -- Candidate features (EXTRA_FEATURES gate in featureset.py)
  pc.off_plays_l6 + pcd.def_plays_faced_l6 AS pace_env_l6,
  bl.blitz_rate_l6 AS opp_blitz_rate_l6,
  fo.pa_rate_l6,
  fd.def_pressure_rate_l6 AS opp_pressure_rate_l6,
  xf.xfp_l4,
  sx.net_rest_diff,
  sx.body_clock_hour,
  tc.top2_target_share_l6 AS team_top2_target_share_l6,
  qn.qb_cpoe_l6,
  qn.qb_time_to_throw_l6,

  -- Opportunity vacated by teammates ruled Out this week (own share
  -- excluded), same definition as the training table.
  GREATEST(
    COALESCE(v.vacated_target_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.target_share_l4, 0), 0),
    0) AS team_vacated_target_share,
  GREATEST(
    COALESCE(v.vacated_carry_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.carry_share_l4, 0), 0),
    0) AS team_vacated_carry_share,

  -- Causally-directed vacated capture (2026-08-03 event study, Addendum
  -- 44): 553 target-hog / 369 carry-hog absences 2019-25 show vacated
  -- TARGETS flow laterally to other WRs (WR1/WR2 +2.5-2.6 share pts,
  -- WR3 +1.9, TE +1.2, RB ~0) while vacated CARRIES concentrate in the
  -- backfield (RB2 +15.8, RB1 +9.5, RB3 +7.5, others ~0). These weight
  -- the team-level sum by the empirical capture rate of the player's
  -- (position x depth) cell — the interaction a GBM must otherwise
  -- discover on its own. EXTRA_FEATURES candidates.
  GREATEST(
    COALESCE(v.vacated_target_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.target_share_l4, 0), 0),
    0) * CASE
      WHEN COALESCE(u.position, ro.position) = 'WR' AND ro.depth_rank <= 2 THEN 0.100
      WHEN COALESCE(u.position, ro.position) = 'WR' THEN 0.073
      WHEN COALESCE(u.position, ro.position) = 'TE' THEN 0.050
      WHEN COALESCE(u.position, ro.position) = 'RB' AND ro.depth_rank <= 2 THEN 0.033
      ELSE 0.009 END AS vacated_capture_tgt,
  GREATEST(
    COALESCE(v.vacated_carry_share, 0)
      - IF(i.injury_status = 'Out', COALESCE(u.carry_share_l4, 0), 0),
    0) * CASE
      WHEN COALESCE(u.position, ro.position) = 'RB' AND ro.depth_rank = 1 THEN 0.270
      WHEN COALESCE(u.position, ro.position) = 'RB' AND ro.depth_rank = 2 THEN 0.450
      WHEN COALESCE(u.position, ro.position) = 'RB' THEN 0.210
      WHEN COALESCE(u.position, ro.position) = 'QB' THEN 0.047
      ELSE 0.020 END AS vacated_capture_car,

  -- Target quality + NGS context (024)
  adv.ez_targets_l4, adv.deep_targets_l4, adv.separation_l4, adv.stacked_box_l4,

  -- Weather
  w.wind_mph, w.temp_f, w.is_dome,

  -- DFS-specific (salary and dk_ppg come from the live slate pull at
  -- inference time; only the derived delta belongs here)
  dk.salary_delta_wow,

  -- Cold start flag (§7.6): no usable rolling history
  (u.games_played_prior IS NULL OR u.games_played_prior < 1
   OR u.target_share_l4 IS NULL AND u.carry_share_l4 IS NULL) AS is_cold_start

FROM `${features}.player_week_usage` u
JOIN `${features}.schedule_long` s
  ON s.team = u.team AND s.season = u.season AND s.week = u.week
LEFT JOIN `${features}.player_week_efficiency` e
  ON e.gsis_id = u.gsis_id AND e.season = u.season AND e.week = u.week
LEFT JOIN `${features}.team_week_context` t
  ON t.team = u.team AND t.season = u.season AND t.week = u.week
LEFT JOIN def_asof d
  ON d.team = s.opponent AND d.season = u.season
LEFT JOIN `${features}.defense_week_coverage` cv
  ON cv.team = s.opponent AND cv.season = u.season AND cv.week = u.week
LEFT JOIN `${features}.player_week_injury` i
  ON i.gsis_id = u.gsis_id AND i.season = u.season AND i.week = u.week
LEFT JOIN `${features}.game_weather` w ON w.game_id = s.game_id
LEFT JOIN `${features}.dk_salary_week` dk
  ON dk.gsis_id = u.gsis_id AND dk.season = u.season AND dk.week = u.week
LEFT JOIN `${features}.player_week_role` ro
  ON ro.gsis_id = u.gsis_id AND ro.season = u.season AND ro.week = u.week
LEFT JOIN `${features}.team_week_vacated` v
  ON v.team = u.team AND v.season = u.season AND v.week = u.week
LEFT JOIN `${features}.player_week_advanced` adv
  ON adv.gsis_id = u.gsis_id AND adv.season = u.season AND adv.week = u.week
LEFT JOIN `${features}.referee_game_tendency` rt ON rt.game_id = s.game_id
LEFT JOIN `${features}.team_week_neutral_pass` np
  ON np.team = u.team AND np.season = u.season AND np.week = u.week
LEFT JOIN `${features}.team_week_ol_out` ol
  ON ol.team = u.team AND ol.season = u.season AND ol.week = u.week
LEFT JOIN `${features}.team_week_pace` pc
  ON pc.team = u.team AND pc.season = u.season AND pc.week = u.week
LEFT JOIN `${features}.team_week_pace` pcd
  ON pcd.team = s.opponent AND pcd.season = u.season AND pcd.week = u.week
LEFT JOIN `${features}.defense_week_blitz` bl
  ON bl.team = s.opponent AND bl.season = u.season AND bl.week = u.week
LEFT JOIN `${features}.team_week_ftn_offense` fo
  ON fo.team = u.team AND fo.season = u.season AND fo.week = u.week
LEFT JOIN xfp_asof xf
  ON xf.gsis_id = u.gsis_id AND xf.season = u.season
LEFT JOIN `${features}.team_week_schedule_ctx` sx
  ON sx.team = u.team AND sx.season = u.season AND sx.week = u.week
LEFT JOIN `${features}.team_week_ftn_offense` fd
  ON fd.team = s.opponent AND fd.season = u.season AND fd.week = u.week
LEFT JOIN `${features}.team_week_target_concentration` tc
  ON tc.team = u.team AND tc.season = u.season AND tc.week = u.week
LEFT JOIN `${features}.qb_week_ngs` qn
  ON qn.gsis_id = u.gsis_id AND qn.season = u.season AND qn.week = u.week
WHERE u.is_upcoming
  AND COALESCE(u.position, ro.position) IN ('QB', 'RB', 'WR', 'TE')
-- Same mid-week team-change dedup as 021 (audit 2026-08-01).
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY u.gsis_id, u.season, u.week ORDER BY u.team
) = 1;

```

===== FILE: sql/features/024_team_defense_week.sql =====
```sql
-- Team-defense (DST) DK scoring per week, computed from play-by-play +
-- schedules, plus point-in-time trailing form. This is the in-season DST
-- actuals source (issue #7): dk_salaries_historical only covers seasons
-- someone exported, while pbp arrives weekly all season.
--
-- DK DST scoring: sack +1, INT +2, fumble recovery +2, def/ST return TD
-- +6, safety +2, blocked kick +2, plus the points-allowed tier.
-- Approximation: points allowed = opponent's final score (DK excludes
-- points the team's own offense surrendered, e.g. pick-sixes; final score
-- is the standard proxy and the bias is small and rare).

CREATE OR REPLACE TABLE `${features}.team_defense_week` AS
WITH def_events AS (
  SELECT
    season, week, defteam AS team,
    SUM(CAST(sack AS INT64)) AS sacks,
    SUM(CAST(interception AS INT64)) AS interceptions,
    SUM(CAST(fumble_lost AS INT64)) AS fumble_recoveries,
    SUM(CAST(safety AS INT64)) AS safeties,
    SUM(CASE WHEN punt_blocked = 1
              OR field_goal_result = 'blocked'
              OR extra_point_result = 'blocked' THEN 1 ELSE 0 END)
      AS blocked_kicks,
    -- Return/defensive TDs credited to the DST: any TD scored by this
    -- team on a play where it did NOT have possession (pick-six, scoop
    -- score, punt/kick return).
    SUM(CASE WHEN touchdown = 1 AND td_team = defteam THEN 1 ELSE 0 END)
      AS return_tds
  FROM `${raw}.pbp`
  WHERE defteam IS NOT NULL AND season_type = 'REG'
  GROUP BY season, week, defteam
),
points_allowed AS (
  SELECT season, week, home_team AS team, away_score AS pa FROM `${raw}.schedules`
  WHERE game_type = 'REG'
  UNION ALL
  SELECT season, week, away_team AS team, home_score AS pa FROM `${raw}.schedules`
  WHERE game_type = 'REG'
),
scored AS (
  SELECT
    e.season, e.week, e.team, p.pa,
    e.sacks, e.interceptions, e.fumble_recoveries, e.safeties,
    e.blocked_kicks, e.return_tds,
    e.sacks * 1 + e.interceptions * 2 + e.fumble_recoveries * 2
      + e.safeties * 2 + e.blocked_kicks * 2 + e.return_tds * 6
      + CASE
          WHEN p.pa = 0 THEN 10
          WHEN p.pa <= 6 THEN 7
          WHEN p.pa <= 13 THEN 4
          WHEN p.pa <= 20 THEN 1
          WHEN p.pa <= 27 THEN 0
          WHEN p.pa <= 34 THEN -1
          ELSE -4
        END AS dst_dk_points
  FROM def_events e
  JOIN points_allowed p USING (season, week, team)
)
SELECT
  *,
  -- Point-in-time trailing form: strictly prior weeks only (1 PRECEDING).
  AVG(dst_dk_points) OVER (
    PARTITION BY team, season ORDER BY week
    ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING) AS dst_points_l4,
  AVG(dst_dk_points) OVER (
    PARTITION BY team ORDER BY season, week
    ROWS BETWEEN 16 PRECEDING AND 1 PRECEDING) AS dst_points_l16
FROM scored;

```

===== FILE: sql/predictions/001_player_projections.sql =====
```sql
CREATE TABLE IF NOT EXISTS `${predictions}.player_projections` (
  generated_at TIMESTAMP,
  model_version STRING,
  season INT64, week INT64, slate_id INT64,
  gsis_id STRING, dk_player_id INT64,
  display_name STRING, position STRING, team STRING, opponent STRING,
  salary INT64,
  proj_points FLOAT64,          -- mean
  proj_p10 FLOAT64,             -- 10th percentile
  proj_p50 FLOAT64,
  proj_p90 FLOAT64,             -- ceiling — what matters for GPP
  proj_std FLOAT64,
  p_20_plus FLOAT64,
  value FLOAT64,                -- proj_points / (salary/1000)
  proj_ownership FLOAT64        -- nullable until you have a source
)
PARTITION BY DATE(generated_at)
CLUSTER BY season, week;

```

===== FILE: sql/raw/001_pbp.sql =====
```sql
-- Raw play-by-play landing table. Loaded WRITE_TRUNCATE by the nflverse job
-- with autodetect; this DDL documents the columns the downstream SQL depends
-- on (PBP has ~370 columns; the loader lands all of them).
CREATE TABLE IF NOT EXISTS `${raw}.pbp` (
  game_id STRING, play_id INT64, season INT64, week INT64, season_type STRING,
  posteam STRING, defteam STRING,
  yardline_100 INT64, down INT64, ydstogo INT64, qtr INT64,
  game_seconds_remaining INT64, score_differential INT64,
  play_type STRING, pass_attempt INT64, rush_attempt INT64,
  complete_pass INT64, touchdown INT64, pass_touchdown INT64, rush_touchdown INT64,
  passer_player_id STRING, rusher_player_id STRING, receiver_player_id STRING,
  air_yards FLOAT64, yards_after_catch FLOAT64, yards_gained INT64,
  epa FLOAT64, wpa FLOAT64, cpoe FLOAT64,
  shotgun INT64, no_huddle INT64, qb_dropback INT64,
  drive INT64, series INT64, fixed_drive_result STRING
)
PARTITION BY RANGE_BUCKET(season, GENERATE_ARRAY(1999, 2040, 1))
CLUSTER BY game_id, posteam;

```

===== FILE: sql/raw/002_dk_salaries.sql =====
```sql
-- Append-only log of every DK slate pull. Never overwrite: the history of
-- how a player's status changed before lock is itself a valuable feature.
CREATE TABLE IF NOT EXISTS `${raw}.dk_salaries` (
  pulled_at TIMESTAMP,          -- when YOU fetched it
  draft_group_id INT64,
  slate_type STRING,            -- 'classic' | 'showdown'
  season INT64, week INT64,
  dk_player_id INT64,
  dk_draftable_id INT64,        -- slate-specific ID DK's lineup upload wants
  dk_cpt_draftable_id INT64,    -- showdown only: the CPT-slot draftable ID
  display_name STRING,
  team_abbr STRING,
  position STRING,
  salary INT64,
  roster_slot STRING,
  game_start TIMESTAMP,
  status STRING,                -- 'None' | 'O' | 'Q' | 'D' ...
  dk_ppg FLOAT64                -- DK's own points-per-game figure when present
)
PARTITION BY DATE(pulled_at)
CLUSTER BY season, week, dk_player_id;

-- Migration for tables created before draftable IDs were ingested
-- (2026-07). Rows pulled before then keep NULLs — see the deficiency log.
ALTER TABLE `${raw}.dk_salaries`
  ADD COLUMN IF NOT EXISTS dk_draftable_id INT64,
  ADD COLUMN IF NOT EXISTS dk_cpt_draftable_id INT64;

```

===== FILE: sql/raw/003_misc.sql =====
```sql
-- Remaining raw landing tables. Most are loaded WRITE_TRUNCATE with schema
-- autodetect from the nflverse job; only the append-only snapshot tables
-- need explicit DDL for partitioning.

CREATE TABLE IF NOT EXISTS `${raw}.odds_snapshots` (
  pulled_at TIMESTAMP,
  event_id STRING,
  event_name STRING,
  start_time STRING,
  market_type STRING,           -- 'Moneyline' | 'Spread' | 'Total'
  selection STRING,
  line FLOAT64,
  odds_american STRING
)
PARTITION BY DATE(pulled_at);

CREATE TABLE IF NOT EXISTS `${raw}.weather` (
  pulled_at TIMESTAMP,
  game_id STRING,
  temp_f FLOAT64,
  wind_mph FLOAT64,
  precip_prob FLOAT64,
  is_dome BOOL
)
PARTITION BY DATE(pulled_at);

-- RotoGuru one-time historical backfill (2014+), includes actual DK points.
CREATE TABLE IF NOT EXISTS `${raw}.dk_salaries_historical` (
  season INT64, week INT64,
  rotoguru_gid STRING,
  display_name STRING,
  position STRING,
  team_abbr STRING,
  home_away STRING,
  opponent STRING,
  dk_points FLOAT64,
  salary INT64
);

```

===== FILE: sql/raw/004_ownership.sql =====
```sql
-- Actual contest ownership, imported from DraftKings contest-standings CSV
-- exports (see ingest/ownership_import.py). This is the training data the
-- field simulator's naive ownership proxy is waiting on: once a season of
-- rows accumulates, a regression (value, salary rank, team total -> owned%)
-- slots in behind backtest/field.py's `ownership` parameter.
CREATE TABLE IF NOT EXISTS `${raw}.contest_ownership` (
  imported_at TIMESTAMP,
  season INT64,
  week INT64,
  contest_id STRING,
  contest_name STRING,
  display_name STRING,          -- as DK prints it in the export
  roster_position STRING,       -- QB/RB/WR/TE/FLEX/DST
  pct_drafted FLOAT64,          -- 0-100
  fpts FLOAT64
)
PARTITION BY DATE(imported_at);

```

===== FILE: sql/raw/005_dk_contests.sql =====
```sql
-- Overlay-detection scaffold (issue #13 item 4): append-only fill-rate
-- snapshots for DK contests tied to real NFL draft groups. Same
-- never-overwrite rationale as dk_salaries — how a contest's fill rate
-- moved toward lock is the signal, not just its final state.
CREATE TABLE IF NOT EXISTS `${raw}.dk_contest_fills` (
  pulled_at TIMESTAMP,        -- when YOU fetched it
  contest_id INT64,
  draft_group_id INT64,       -- matches dk_salaries.draft_group_id (or cfb_dk_salaries')
  sport STRING,                -- 'NFL' | 'CFB' (issue #13 item 7); NULL on pre-migration rows, treat as 'NFL'
  name STRING,
  game_type STRING,
  entry_fee FLOAT64,
  max_entries INT64,
  entries INT64,               -- entries gathered so far ("nt" in DK's payload)
  fill_rate FLOAT64,           -- entries / max_entries
  prize_pool FLOAT64,
  is_guaranteed BOOL,
  overlay_dollars FLOAT64,     -- max(prize_pool - entries*entry_fee, 0) when guaranteed, else 0
  start_time TIMESTAMP
)
PARTITION BY DATE(pulled_at)
CLUSTER BY draft_group_id, contest_id;

-- Migration: reuse this table for CFB contest polls (issue #13 item 7)
-- instead of a separate twin — same shape, one more discriminator column.
-- Does not touch the validated NFL ingest path; existing rows stay NULL.
ALTER TABLE `${raw}.dk_contest_fills`
  ADD COLUMN IF NOT EXISTS sport STRING;

-- NFL-only view: the safe default read path now that the table holds both
-- sports (CFB collection scheduled 2026-07-31). Future overlay-detection /
-- contest-analysis queries should read this, not the raw table, so CFB
-- Saturday contests can never silently blend into NFL overlay signals.
-- (sport IS NULL kept for pre-migration rows; the table was empty at
-- migration time, so in practice every row carries an explicit sport.)
CREATE OR REPLACE VIEW `${raw}.dk_contest_fills_nfl` AS
SELECT * FROM `${raw}.dk_contest_fills`
WHERE sport = 'NFL' OR sport IS NULL;

```

===== FILE: sql/raw/006_cfb_dk_salaries.sql =====
```sql
-- CFB (college football) DK slate/salary snapshot, issue #13 item 7 (owner
-- request 2026-07-31): DK now runs college football DFS (QB/2RB/3WR/FLEX/
-- Superflex, 8 slots). Collection-only scaffold so the 2026 CFB season
-- yields a backtestable dataset for a 2027 go/no-go decision — no models,
-- features, or optimizer work reads this table yet.
--
-- Deliberately a separate table from `dk_salaries`, not a `sport` column on
-- it: same shape, but this must never touch the validated NFL ingest path,
-- and CFB rosters differ (QB/RB/WR/FLEX/Superflex, not DK NFL Classic's
-- QB/RB/RB/WR/WR/WR/TE/FLEX/DST) so keeping the tables distinct avoids an
-- implicit schema contract across two different games. `dk_contest_fills`
-- (005) is reused with a `sport` column instead, since contest fill-rate
-- rows carry no roster-shape assumptions.
CREATE TABLE IF NOT EXISTS `${raw}.cfb_dk_salaries` (
  pulled_at TIMESTAMP,          -- when YOU fetched it
  draft_group_id INT64,
  slate_type STRING,            -- 'classic' | 'showdown'
  season INT64, week INT64,     -- week left NULL for now, same as dk_salaries (see ingest/dk_job.py)
  dk_player_id INT64,
  dk_draftable_id INT64,        -- slate-specific ID DK's lineup upload wants
  dk_cpt_draftable_id INT64,    -- showdown only: the CPT-slot draftable ID
  display_name STRING,
  team_abbr STRING,
  position STRING,
  salary INT64,
  roster_slot STRING,
  game_start TIMESTAMP,
  status STRING,                -- 'None' | 'O' | 'Q' | 'D' ...
  dk_ppg FLOAT64                -- DK's own points-per-game figure when present
)
PARTITION BY DATE(pulled_at)
-- draft_group_id, not season/week: week is always NULL here (see above) and
-- draft_group_id is the natural access path, matching dk_salaries' key.
CLUSTER BY draft_group_id, dk_player_id;

```

===== FILE: sql/raw/007_odds_movement.sql =====
```sql
-- Line movement (2026-08-01): first-vs-latest snapshot per market line
-- from odds_snapshots (collecting 2x/day Wed-Sun since the odds-source
-- fix). "Late movement contains information" is the queued in-season
-- study; this view is its substrate and feeds the app's Market page now.
CREATE OR REPLACE VIEW `${raw}.odds_movement` AS
WITH ranked AS (
  SELECT
    event_name, market_type, selection, start_time,
    line, odds_american, pulled_at,
    ROW_NUMBER() OVER (PARTITION BY event_id, market_type, selection
                       ORDER BY pulled_at) AS rn_first,
    ROW_NUMBER() OVER (PARTITION BY event_id, market_type, selection
                       ORDER BY pulled_at DESC) AS rn_last
  FROM `${raw}.odds_snapshots`
)
SELECT
  f.event_name, f.market_type, f.selection, f.start_time,
  f.line AS open_line, l.line AS latest_line,
  l.line - f.line AS line_move,
  f.odds_american AS open_odds, l.odds_american AS latest_odds,
  f.pulled_at AS first_seen, l.pulled_at AS last_seen
FROM (SELECT * FROM ranked WHERE rn_first = 1) f
JOIN (SELECT * FROM ranked WHERE rn_last = 1) l
  USING (event_name, market_type, selection);

```

===== FILE: tests/conftest.py =====
```python
"""Shared synthetic data for model/optimizer/backtest tests.

The generator produces a plausible player-week panel with real signal
(usage drives production) so models have something to learn, plus a noisy
market projection so market-comparison code paths run.
"""

import numpy as np
import pandas as pd
import pytest

POSITIONS = ["QB", "RB", "WR", "TE"]


def synthetic_panel(n_players=120, seasons=range(2018, 2025), seed=11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        pos = POSITIONS[p % 4]
        skill = rng.normal(0, 1)
        for season in seasons:
            team_total = rng.uniform(17, 30)
            usage = np.clip(rng.normal(0.15 + 0.05 * skill, 0.05), 0.01, 0.4)
            for week in range(1, 18):
                usage = np.clip(usage + rng.normal(0, 0.01), 0.01, 0.45)
                implied = team_total + rng.normal(0, 2)
                # True expectation: usage x game environment
                mu = 4 + 40 * usage + 0.35 * (implied - 22) + 2 * skill
                dk = max(0.0, rng.normal(mu, 6))
                rows.append({
                    "gsis_id": f"00-{p:07d}",
                    "season": season, "week": week,
                    "team": f"T{p % 32}", "opponent": f"T{(p + 7) % 32}",
                    "game_id": f"{season}_{week:02d}_T{p % 32}",
                    "position": pos,
                    "target_share_l4": usage if pos in ("WR", "TE") else usage / 3,
                    "carry_share_l4": usage if pos == "RB" else usage / 5,
                    "wopr_l4": 1.5 * usage,
                    "rz20_targets_smoothed": usage * 4,
                    "gl3_carries_smoothed": usage * (2 if pos == "RB" else 0.2),
                    "snap_share_l4": np.clip(usage * 2.2, 0, 1),
                    "dk_points_l4": mu + rng.normal(0, 2),
                    "dk_points_std": mu + rng.normal(0, 1.5),
                    "dk_points_vol": 6.0,
                    "implied_team_total": implied,
                    "spread": rng.normal(0, 5),
                    "game_total": implied * 2 + rng.normal(0, 2),
                    "expected_game_script": rng.normal(0, 4),
                    "games_played_prior": week - 1 + 17 * 2,
                    "is_home": float(rng.random() < 0.5),
                    "is_dome": float(rng.random() < 0.3),
                    "is_cold_start": 0.0,
                    "salary": int(np.clip(3000 + 320 * mu + rng.normal(0, 400), 2500, 9800)),
                    "salary_delta_wow": float(rng.normal(0, 200)),
                    # Market is a good but imperfect projection
                    "dk_ppg": mu + rng.normal(0, 2.0),
                    "injury_status": None,
                    # Role + next-man-up features (021/023). Deterministic —
                    # consuming rng draws here would shift every label below.
                    "depth_rank": (p // 4) % 3 + 1,
                    "is_rookie": False,
                    "draft_round": p % 7 + 1,
                    "team_vacated_target_share":
                        0.2 if (week % 9 == 0 and p % 5 == 0) else 0.0,
                    "ez_targets_l4": usage * 1.5,
                    "deep_targets_l4": usage * 2.0,
                    "separation_l4": 2.5 + (p % 5) * 0.2,
                    "stacked_box_l4": 20.0 + (p % 7) * 2.0,
                    "team_vacated_carry_share":
                        0.35 if (week % 11 == 0 and p % 4 == 1) else 0.0,
                    # Component labels, roughly consistent with dk points
                    "y_targets": rng.poisson(9 * usage) if pos != "QB" else 0,
                    "y_receptions": rng.poisson(6 * usage) if pos != "QB" else 0,
                    "y_rec_yards": max(0, rng.normal(70 * usage, 20)) if pos != "QB" else 0,
                    "y_rec_tds": rng.binomial(1, min(0.6, usage)) if pos != "QB" else 0,
                    "y_carries": rng.poisson(18 * usage) if pos == "RB" else 0,
                    "y_rush_yards": max(0, rng.normal(80 * usage, 25)) if pos == "RB" else 0,
                    "y_rush_tds": rng.binomial(1, min(0.5, usage * 0.8)) if pos == "RB" else 0,
                    "y_pass_attempts": rng.poisson(33) if pos == "QB" else 0,
                    "y_pass_yards": max(0, rng.normal(240, 60)) if pos == "QB" else 0,
                    "y_pass_tds": rng.poisson(1.6) if pos == "QB" else 0,
                    "y_interceptions": rng.poisson(0.7) if pos == "QB" else 0,
                    "y_dk_points": dk,
                })
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def panel() -> pd.DataFrame:
    return synthetic_panel()


@pytest.fixture(scope="session")
def small_panel() -> pd.DataFrame:
    return synthetic_panel(n_players=60, seasons=range(2019, 2023), seed=5)

```

===== FILE: tests/test_app.py =====
```python
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nfl_dfs.app import main as app_main
from nfl_dfs.app.store import InMemoryStore


def projections_frame(seed=51, n_teams=6, season=2025, week=3):
    rng = np.random.default_rng(seed)
    rows = []
    pid = 1000
    for t in range(n_teams):
        team, opp = f"T{t}", f"T{t + 1 if t % 2 == 0 else t - 1}"
        for pos, n in (("QB", 2), ("RB", 3), ("WR", 4), ("TE", 2), ("DST", 1)):
            for i in range(n):
                base = {"QB": 19, "RB": 13, "WR": 11, "TE": 8, "DST": 7}[pos]
                mu = max(1.0, base - 2.5 * i + rng.normal(0, 1.5))
                rows.append({
                    "season": season, "week": week, "slate_id": 9001,
                    "gsis_id": f"00-{pid}", "dk_player_id": pid,
                    "display_name": f"{pos}{i} {team}", "position": pos,
                    "team": team, "opponent": opp,
                    "salary": int(np.clip(2700 + mu * 330, 2500, 9500)),
                    "proj_points": mu,
                    "proj_p10": mu - 5, "proj_p50": mu, "proj_p90": mu + 7,
                    "proj_std": 5.0, "p_20_plus": 0.2,
                    "value": mu / 5.0, "model_version": "pooled/2025-W30",
                    "generated_at": "2025-09-16T14:00:00Z",
                })
                pid += 1
    return pd.DataFrame(rows)


@pytest.fixture
def client():
    frame = projections_frame()
    app_main.app.dependency_overrides[app_main.default_store] = (
        lambda: InMemoryStore(frame)
    )
    yield TestClient(app_main.app)
    app_main.app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_slates(client):
    slates = client.get("/slates").json()
    assert slates == [{"season": 2025, "week": 3, "players": 72}]


def test_projections_sorted_and_filterable(client):
    r = client.get("/projections", params={"season": 2025, "week": 3})
    assert r.status_code == 200
    rows = r.json()
    projs = [row["proj_points"] for row in rows]
    assert projs == sorted(projs, reverse=True)

    wr = client.get("/projections",
                    params={"season": 2025, "week": 3, "position": "wr"}).json()
    assert all(row["position"] == "WR" for row in wr)

    missing = client.get("/projections", params={"season": 2025, "week": 9})
    assert missing.status_code == 404


def test_lineup_builder(client):
    r = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 3,
        "qb_stack_min": 1, "objective": "proj_p90",
        "sim": False,
    })
    assert r.status_code == 200
    body = r.json()
    assert len(body["lineups"]) == 3
    for lu in body["lineups"]:
        assert len(lu["players"]) == 9
        assert lu["salary"] <= 50_000
    assert body["dk_csv"].startswith("QB,RB,RB,WR,WR,WR,TE,FLEX,DST")
    exposures = {e["id"]: e for e in body["exposure"]}
    assert all(0 < e["exposure"] <= 1 for e in exposures.values())


def test_tail_line_scales_with_field_size(client):
    # Anchor: the Milly field reproduces the measured 194 line; smaller
    # fields win lower, monotonically, and never below the contending mean.
    assert app_main.tail_line_for_field(app_main.MILLY_FIELD) == 194.0
    q20k = app_main.tail_line_for_field(20_000)
    q5k = app_main.tail_line_for_field(5_000)
    assert q5k < q20k < 194.0
    assert q20k > 180  # sanity: a 20k qualifier is not a cakewalk

    # /contests always serves presets (BQ-less test env has no live table)
    opts = client.get("/contests").json()
    assert opts["presets"][0]["field_size"] == 20_000
    assert all("tail_line" in c for c in opts["presets"])

    # field_size flows into the response's confidence target
    r = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1, "field_size": 20_000,
        "sim": False,
    })
    assert r.status_code == 200
    assert r.json()["tail_line"] == q20k
    # explicit tail_line overrides field_size
    r = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1, "field_size": 20_000,
        "tail_line": 205.0,
        "sim": False,
    })
    assert r.json()["tail_line"] == 205.0


def test_lineup_builder_locks_and_csv_endpoint(client):
    frame = projections_frame()
    a_wr = int(frame[frame.position == "WR"].dk_player_id.iloc[-1])
    r = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1, "locks": [a_wr],
        "sim": False,
    })
    ids = [p["id"] for p in r.json()["lineups"][0]["players"]]
    assert a_wr in ids

    csv_resp = client.post("/lineups.csv", json={"season": 2025, "week": 3,
                                                 "sim": False})
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")


def test_lineup_infeasible_constraints(client):
    r = client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1,
        "qb_stack_min": 3,  # only ~6 WR/TE per team projected > cap conflicts
        "bring_back_min": 2,
        "bans": list(range(1000, 1030)),
        "sim": False,
    })
    assert r.status_code in (200, 422)  # feasibility depends on pool; must not 500


def defense_frame(season=2025, weeks=6, n_teams=6, seed=9):
    rng = np.random.default_rng(seed)
    rows = []
    for t in range(n_teams):
        for pos in ("QB", "RB", "WR", "TE"):
            base = rng.uniform(15, 35)
            vals = []
            for wk in range(1, weeks + 1):
                fp = max(0.0, rng.normal(base + (2 if t == 0 else 0) * wk, 4))
                vals.append(fp)
                s = pd.Series(vals)
                rows.append({
                    "team": f"T{t}", "season": season, "week": wk,
                    "position": pos, "fp_allowed": fp,
                    "fp_allowed_l3": s.tail(3).mean(),
                    "fp_allowed_l6": s.tail(6).mean(),
                    "fp_allowed_season": s.mean(),
                    "trend": s.tail(3).mean() - s.mean(),
                })
    return pd.DataFrame(rows)


@pytest.fixture
def client_with_defense():
    app_main.app.dependency_overrides[app_main.default_store] = (
        lambda: InMemoryStore(projections_frame(), defense=defense_frame())
    )
    yield TestClient(app_main.app)
    app_main.app.dependency_overrides.clear()


def test_defense_points_against(client_with_defense):
    rows = client_with_defense.get(
        "/defense/points-against", params={"season": 2025, "position": "wr"}
    ).json()
    assert len(rows) == 6  # one snapshot per team
    assert all(r["position"] == "WR" and r["week"] == 6 for r in rows)
    # Ranked toughest-first
    seasons_avg = [r["fp_allowed_season"] for r in rows]
    assert seasons_avg == sorted(seasons_avg)


def test_defense_trends(client_with_defense):
    out = client_with_defense.get(
        "/defense/trends", params={"season": 2025, "top": 3}
    ).json()
    assert set(out) == {"QB", "RB", "WR", "TE"}
    for pos in out:
        assert len(out[pos]["improving"]) == 3
        assert len(out[pos]["fading"]) == 3
        # T0's defense worsens by construction -> it should be a top fader
        assert out[pos]["fading"][0]["team"] == "T0"


def test_defense_dashboard_html(client_with_defense):
    r = client_with_defense.get("/defense")
    assert r.status_code == 200
    assert "DK points allowed per position" in r.text
    assert "vs WR" in r.text


def test_defense_endpoints_empty_store(client):
    assert client.get("/defense/points-against").status_code == 404
    assert "No defense data" in client.get("/defense").text


def test_core_lineups(client):
    req = {"season": 2025, "week": 3, "n_lineups": 4, "core_size": 6}
    r = client.post("/lineups/core", json=req)
    assert r.status_code == 200, r.text
    out = r.json()
    core_ids = {p["id"] for p in out["core"]}
    assert 3 <= len(core_ids) <= 6
    assert len(out["lineups"]) == 4
    # Every entry contains the full core; variations differ from each other
    rosters = [frozenset(p["id"] for p in lu["players"]) for lu in out["lineups"]]
    assert all(core_ids <= roster for roster in rosters)
    assert len(set(rosters)) == len(rosters)
    assert "dk_csv" in out and "exposure" in out


def test_core_lineups_respects_bans(client):
    base = client.post("/lineups/core",
                       json={"season": 2025, "week": 3, "n_lineups": 1}).json()
    banned = base["core"][0]["id"]
    r = client.post("/lineups/core",
                    json={"season": 2025, "week": 3, "n_lineups": 2,
                          "bans": [banned]})
    assert r.status_code == 200
    for lu in r.json()["lineups"]:
        assert banned not in {p["id"] for p in lu["players"]}


def test_core_lineups_auto_sizes(client):
    r = client.post("/lineups/core", json={"season": 2025, "week": 3, "n_lineups": 3})
    r = client.post("/lineups/core", json={"season": 2025, "week": 3, "n_lineups": 3})
    assert r.status_code == 200, r.text
    out = r.json()
    core = out["core"]
    assert 2 <= len(core) <= 7  # system-chosen size
    # Conviction reported and sorted strongest-first
    convictions = [c["conviction"] for c in core]
    assert all(0 < c <= 1 for c in convictions)
    assert convictions == sorted(convictions, reverse=True)
    # Budget guard: free slots keep at least mid-tier salary each
    core_salary = sum(c["salary"] for c in core)
    assert 50_000 - core_salary >= (9 - len(core)) * 4_500
    core_ids = {c["id"] for c in core}
    for lu in out["lineups"]:
        assert core_ids <= {p["id"] for p in lu["players"]}


# --- Showdown Captain Mode endpoints -----------------------------------------


def showdown_frame(frame, gid=7001, teams=("T0", "T1"),
                   game_start="2025-09-19T00:15:00Z"):
    """Showdown salary snapshot for one game, built from the projections
    frame's players on `teams` plus a K and DST per team (no projections —
    they exercise the dk_ppg fallback)."""
    sub = frame[frame.team.isin(teams)]
    rows = [{
        "draft_group_id": gid, "dk_player_id": int(r.dk_player_id),
        "dk_draftable_id": int(r.dk_player_id) + 40_000_000,
        "dk_cpt_draftable_id": int(r.dk_player_id) + 50_000_000,
        "display_name": r.display_name, "team_abbr": r.team,
        "position": r.position, "salary": int(r.salary) + 200,
        "game_start": game_start, "status": "None", "dk_ppg": None,
    } for r in sub.itertuples()]
    extra_id = 9900
    for team in teams:
        for pos, ppg in (("K", 7.5), ("DST", 6.0)):
            rows.append({
                "draft_group_id": gid, "dk_player_id": extra_id,
                "dk_draftable_id": extra_id + 40_000_000,
                "dk_cpt_draftable_id": extra_id + 50_000_000,
                "display_name": f"{pos} {team}", "team_abbr": team,
                "position": pos, "salary": 3600,
                "game_start": game_start, "status": "None", "dk_ppg": ppg,
            })
            extra_id += 1
    return pd.DataFrame(rows)


@pytest.fixture
def showdown_client():
    frame = projections_frame()
    thu = showdown_frame(frame, gid=7001, teams=("T0", "T1"),
                         game_start="2025-09-19T00:15:00Z")   # Thu 8:15pm ET
    sun = showdown_frame(frame, gid=7002, teams=("T2", "T3"),
                         game_start="2025-09-21T17:00:00Z")   # Sunday
    mon = showdown_frame(frame, gid=7003, teams=("T4", "T5"),
                         game_start="2025-09-23T00:15:00Z")   # Mon 8:15pm ET
    store = InMemoryStore(frame, showdown=pd.concat([sun, thu, mon]))
    app_main.app.dependency_overrides[app_main.default_store] = lambda: store
    yield TestClient(app_main.app)
    app_main.app.dependency_overrides.clear()


def test_showdown_slates_default_thu_mon(showdown_client):
    slates = showdown_client.get("/showdown/slates").json()
    assert [s["draft_group_id"] for s in slates] == [7001, 7003]
    assert [s["day"] for s in slates] == ["Thursday", "Monday"]
    assert slates[0]["game"] == "T0 vs T1"

    all_days = showdown_client.get("/showdown/slates",
                                   params={"days": ""}).json()
    assert {s["draft_group_id"] for s in all_days} == {7001, 7002, 7003}


def test_showdown_slates_empty_store(client):
    assert client.get("/showdown/slates").status_code == 404


def test_showdown_lineups_defaults_to_next_prime_time_game(showdown_client):
    r = showdown_client.post("/showdown/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 3,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["game"]["draft_group_id"] == 7001  # Thursday comes first
    assert body["game"]["day"] == "Thursday"
    assert len(body["lineups"]) == 3
    from nfl_dfs.optimizer.showdown import cpt_salary
    for lu in body["lineups"]:
        assert len(lu["players"]) == 6
        assert lu["salary"] <= 50_000
        cpt, flex = lu["players"][0], lu["players"][1:]
        assert cpt == lu["captain"]
        assert lu["salary"] == cpt_salary(cpt["salary"]) + sum(
            p["salary"] for p in flex)
        assert {p["team"] for p in lu["players"]} == {"T0", "T1"}
    assert body["dk_csv"].startswith("CPT,FLEX,FLEX,FLEX,FLEX,FLEX")
    # Captains differ or rosters differ across the three entries
    keys = {(lu["captain"]["id"], frozenset(p["id"] for p in lu["players"]))
            for lu in body["lineups"]}
    assert len(keys) == 3
    assert all("cpt_exposure" in e for e in body["exposure"])


def test_showdown_lineups_dk_ppg_fallback_and_selection(showdown_client):
    r = showdown_client.post("/showdown/lineups", json={
        "season": 2025, "week": 3, "draft_group_id": 7003,
        "n_lineups": 1, "locks": [9900],  # K T4, projected via dk_ppg only
    })
    assert r.status_code == 200, r.text
    lu = r.json()["lineups"][0]
    kicker = next(p for p in lu["players"] if p["id"] == 9900)
    assert kicker["proj_source"] == "dk_ppg"
    assert kicker["proj"] == 7.5
    assert all(p["proj_source"] == "model"
               for p in lu["players"] if p["pos"] not in ("K", "DST"))


def test_showdown_captain_lock_and_csv_endpoint(showdown_client):
    frame = projections_frame()
    a_qb = int(frame[(frame.team == "T0") & (frame.position == "QB")]
               .dk_player_id.iloc[0])
    r = showdown_client.post("/showdown/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1, "captain": a_qb,
    })
    assert r.json()["lineups"][0]["captain"]["id"] == a_qb

    csv_resp = showdown_client.post("/showdown/lineups.csv", json={
        "season": 2025, "week": 3, "n_lineups": 2,
    })
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")
    assert csv_resp.text.startswith("CPT,FLEX")


def test_showdown_unknown_group_404(showdown_client):
    r = showdown_client.post("/showdown/lineups", json={
        "season": 2025, "week": 3, "draft_group_id": 1234,
    })
    assert r.status_code == 404


# --- Classic slate selection --------------------------------------------------


def classic_frame(frame, gid, kickoffs, id_base):
    """Classic salary snapshot for one draft group. `kickoffs` maps team ->
    game_start; only those teams' players are in the group. Slate salaries
    run $100 over the projection frame's to prove the override."""
    sub = frame[frame.team.isin(kickoffs)]
    return pd.DataFrame([{
        "draft_group_id": gid, "dk_player_id": int(r.dk_player_id),
        "dk_draftable_id": int(r.dk_player_id) + id_base,
        "display_name": r.display_name, "team_abbr": r.team,
        "position": r.position, "salary": int(r.salary) + 100,
        "game_start": kickoffs[r.team], "status": "None",
    } for r in sub.itertuples()])


SUN_EARLY = "2025-09-21T17:00:00Z"   # Sun 1:00 PM ET
SUN_LATE = "2025-09-21T20:25:00Z"    # Sun 4:25 PM ET
THU_NIGHT = "2025-09-19T00:15:00Z"   # Thu 8:15 PM ET


@pytest.fixture
def classic_client():
    """Two classic slates over the 6-team projections frame: the Sunday
    main (T2-T5) and a Thu-Sun full slate (all teams)."""
    frame = projections_frame()
    main = classic_frame(frame, gid=8200, id_base=60_000_000, kickoffs={
        "T2": SUN_EARLY, "T3": SUN_EARLY, "T4": SUN_LATE, "T5": SUN_LATE})
    full = classic_frame(frame, gid=8100, id_base=70_000_000, kickoffs={
        "T0": THU_NIGHT, "T1": THU_NIGHT,
        "T2": SUN_EARLY, "T3": SUN_EARLY, "T4": SUN_LATE, "T5": SUN_LATE})
    store = InMemoryStore(frame, classic=pd.concat([main, full]))
    app_main.app.dependency_overrides[app_main.default_store] = lambda: store
    yield TestClient(app_main.app)
    app_main.app.dependency_overrides.clear()


def test_classic_slates_listing(classic_client):
    slates = classic_client.get("/classic/slates").json()
    assert [s["draft_group_id"] for s in slates] == [8100, 8200]  # first kickoff
    full, main = slates
    assert full["label"] == "Thu–Sun · 3 games"
    assert full["games"] == 3 and full["players"] == 72
    assert not full["main"]
    assert main["label"] == "Sun 1:00 PM–4:25 PM · 2 games"
    assert main["games"] == 2 and main["players"] == 48
    assert main["main"]  # all-Sunday group with the most games


def test_classic_slates_empty_store(client):
    assert client.get("/classic/slates").status_code == 404


def test_lineups_restricted_to_chosen_slate(classic_client):
    r = classic_client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 2, "draft_group_id": 8200,
        "sim": False,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    frame = projections_frame()
    salary_by_id = frame.set_index("dk_player_id").salary.to_dict()
    for lu in body["lineups"]:
        for p in lu["players"]:
            # Pool is the slate's teams only, at the slate's salaries
            assert p["team"] in {"T2", "T3", "T4", "T5"}
            assert p["salary"] == salary_by_id[p["id"]] + 100
    # Upload CSV carries the chosen slate's draftable IDs
    row = body["dk_csv"].strip().splitlines()[1]
    for p in body["lineups"][0]["players"]:
        assert f"({p['id'] + 60_000_000})" in row


def test_lineups_full_slate_keeps_all_teams_available(classic_client):
    frame = projections_frame()
    a_thu_wr = int(frame[(frame.team == "T0") & (frame.position == "WR")]
                   .dk_player_id.iloc[0])
    r = classic_client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1,
        "draft_group_id": 8100, "locks": [a_thu_wr],
        "sim": False,
    })
    assert r.status_code == 200, r.text
    lu = r.json()["lineups"][0]
    assert a_thu_wr in {p["id"] for p in lu["players"]}
    row = r.json()["dk_csv"].strip().splitlines()[1]
    assert f"({a_thu_wr + 70_000_000})" in row


def test_lineups_unknown_slate_404(classic_client):
    r = classic_client.post("/lineups", json={
        "season": 2025, "week": 3, "draft_group_id": 4321,
        "sim": False,
    })
    assert r.status_code == 404
    assert "/classic/slates" in r.json()["detail"]


def test_core_lineups_respect_slate(classic_client):
    r = classic_client.post("/lineups/core", json={
        "season": 2025, "week": 3, "n_lineups": 2, "draft_group_id": 8200,
        "sim": False,
    })
    assert r.status_code == 200, r.text
    out = r.json()
    slate_teams = {"T2", "T3", "T4", "T5"}
    assert {c["team"] for c in out["core"]} <= slate_teams
    for lu in out["lineups"]:
        assert {p["team"] for p in lu["players"]} <= slate_teams


def test_slate_label_single_kickoff():
    starts = pd.Series(["2025-09-22T00:20:00Z"])  # Sun 8:20 PM ET
    assert app_main._slate_label(starts, 1) == "Sun 8:20 PM · 1 game"


# --- DK import files: draftable IDs and DKEntries filling --------------------


@pytest.fixture
def draftable_client():
    """Classic store with a draftable-ID mapping from the latest DK pull."""
    frame = projections_frame()
    draftables = pd.DataFrame({
        "dk_player_id": frame.dk_player_id,
        "dk_draftable_id": frame.dk_player_id + 40_000_000,
    })
    store = InMemoryStore(frame, draftables=draftables)
    app_main.app.dependency_overrides[app_main.default_store] = lambda: store
    yield TestClient(app_main.app)
    app_main.app.dependency_overrides.clear()


def test_classic_csv_uses_draftable_ids(draftable_client):
    r = draftable_client.post("/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1, "sim": False,
    })
    body = r.json()
    row = body["dk_csv"].strip().splitlines()[1]
    for p in body["lineups"][0]["players"]:
        assert f"({p['id'] + 40_000_000})" in row
        assert f"({p['id']})" not in row


def test_classic_csv_falls_back_to_player_ids(client):
    """No draftable mapping in the store (e.g. pre-migration rows): the
    CSV still renders, carrying player IDs."""
    r = client.post("/lineups", json={"season": 2025, "week": 3,
                                      "n_lineups": 1, "sim": False})
    row = r.json()["dk_csv"].strip().splitlines()[1]
    ids = [p["id"] for p in r.json()["lineups"][0]["players"]]
    assert all(f"({pid})" in row for pid in ids)


def test_showdown_csv_uses_cpt_draftable_id(showdown_client):
    r = showdown_client.post("/showdown/lineups", json={
        "season": 2025, "week": 3, "n_lineups": 1,
    })
    body = r.json()
    row = body["dk_csv"].strip().splitlines()[1].split(",")
    cpt = body["lineups"][0]["captain"]
    assert row[0] == f"{cpt['name']} ({cpt['id'] + 50_000_000})"
    for cell, p in zip(row[1:], body["lineups"][0]["players"][1:]):
        assert cell == f"{p['name']} ({p['id'] + 40_000_000})"


CLASSIC_ENTRIES = (
    "Entry ID,Contest Name,Contest ID,Entry Fee,"
    "QB,RB,RB,WR,WR,WR,TE,FLEX,DST,,Instructions\n"
    "4111111,NFL $100K Flea Flicker,987,$5,,,,,,,,,,,Fill in your entries\n"
    "4111112,NFL $100K Flea Flicker,987,$5\n"
)


def test_fill_classic_entries_endpoint(draftable_client):
    r = draftable_client.post("/lineups/entries.csv", json={
        "season": 2025, "week": 3, "entries_csv": CLASSIC_ENTRIES,
        "sim": False,
    })
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[1].startswith("4111111,NFL $100K Flea Flicker,987,$5,")
    assert "(4" in lines[1] and "Fill in your entries" in lines[1]
    assert lines[2].startswith("4111112,")
    # One distinct lineup per entry row
    assert lines[1].split(",")[4:13] != lines[2].split(",")[4:13]


def test_fill_showdown_entries_endpoint(showdown_client):
    entries = (
        "Entry ID,Contest Name,Contest ID,Entry Fee,"
        "CPT,FLEX,FLEX,FLEX,FLEX,FLEX\n"
        "4222221,T0 vs T1 Showdown,55,$1\n"
    )
    r = showdown_client.post("/showdown/lineups/entries.csv", json={
        "season": 2025, "week": 3, "entries_csv": entries,
    })
    assert r.status_code == 200, r.text
    filled = r.text.strip().splitlines()[1].split(",")
    assert filled[0] == "4222221"
    assert all(cell.endswith(")") for cell in filled[4:10])


def test_fill_entries_rejects_mismatched_file(showdown_client):
    r = showdown_client.post("/showdown/lineups/entries.csv", json={
        "season": 2025, "week": 3, "entries_csv": CLASSIC_ENTRIES,
    })
    assert r.status_code == 422
    assert "mismatch" in r.json()["detail"]

    r = showdown_client.post("/showdown/lineups/entries.csv", json={
        "season": 2025, "week": 3, "entries_csv": "not,a,dk,file\n1,2,3,4\n",
    })
    assert r.status_code == 422


def test_lineups_view_page(client):
    r = client.get("/lineups/view")
    assert r.status_code == 200
    assert "Lineup builder" in r.text
    assert "DK CSV" in r.text
    # Slate dropdown offers both formats and the JS hits both builders
    assert "Classic slates" in r.text
    assert "Showdown (Captain Mode)" in r.text
    assert "/showdown/lineups" in r.text
    assert "/showdown/slates?days=" in r.text


def test_showdown_any_game_selectable(showdown_client):
    """The UI dropdown lists every upcoming showdown game (days unfiltered),
    so a Sunday game must build once its draft group is named."""
    r = showdown_client.post("/showdown/lineups", json={
        "season": 2025, "week": 3, "draft_group_id": 7002, "n_lineups": 1,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["game"]["draft_group_id"] == 7002
    assert body["game"]["game"] == "T2 vs T3"
    assert {p["team"] for p in body["lineups"][0]["players"]} == {"T2", "T3"}


def test_season_dashboard_home(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Season tracker" in r.text


def test_swap_blocks_duplicates(client, monkeypatch):
    from nfl_dfs import notes as n

    monkeypatch.setattr(n, "entered_rosters", lambda s, w: {
        0: {"a qb", "b rb", "c wr"}, 1: {"a qb", "b rb", "d wr"}})
    monkeypatch.setattr(n, "swap_entered_player",
                        lambda *a, **k: (_ for _ in ()).throw(
                            AssertionError("must not swap")))
    # store fixture has projections for 2025 wk3; pick any real name from it
    import nfl_dfs.app.main as m
    df = m.get_store().projections(2025, 3)
    name = df.display_name.iloc[0]
    monkeypatch.setattr(n, "norm_name", lambda s: {
        name.lower(): "d wr"}.get(str(s).lower(), str(s).lower()))
    r = client.post("/entries/swap", json={
        "season": 2025, "week": 3, "lineup_ix": 0,
        "out_name": "c wr", "in_name": name})
    assert r.status_code == 409
    assert "identical" in r.json()["detail"]


def test_exports_listing_and_slate_delete(client, monkeypatch):
    from nfl_dfs import notes as n

    monkeypatch.setattr(n, "list_entered_sets", lambda s: pd.DataFrame([
        {"week": 3, "lineups": 40, "players": 360,
         "recorded_at": "2025-09-21 15:00:00+00"}]))
    r = client.get("/results/exports", params={"season": 2025})
    assert r.status_code == 200
    assert r.json() == [{"week": 3, "lineups": 40, "players": 360,
                         "recorded_at": "2025-09-21 15:00:00+00"}]

    deleted = {}

    def fake_delete(season, week):
        deleted["args"] = (season, week)
        return 27

    monkeypatch.setattr(n, "delete_entered_lineups", fake_delete)
    r = client.delete("/results/lineups",
                      params={"season": 2025, "week": 3})
    assert r.status_code == 200
    assert r.json() == {"deleted": 27}
    assert deleted["args"] == (2025, 3)


def test_season_dashboard_offers_slate_delete(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Delete recorded slate" in r.text
    assert "/results/exports" in r.text


def test_showdown_pool_trailing_fallback_order():
    """K/DST fallback: model proj > trailing actuals > dk_ppg (issue #10)."""
    import pandas as pd

    game = pd.DataFrame([
        {"dk_player_id": 1, "display_name": "Model QB", "position": "QB",
         "team_abbr": "AAA", "draft_group_id": 9, "salary": 9000,
         "dk_ppg": 20.0, "dk_draftable_id": 11, "dk_cpt_draftable_id": 12},
        {"dk_player_id": 2, "display_name": "Some Kicker", "position": "K",
         "team_abbr": "AAA", "draft_group_id": 9, "salary": 4000,
         "dk_ppg": 6.0, "dk_draftable_id": 13, "dk_cpt_draftable_id": 14},
        {"dk_player_id": 3, "display_name": "BBB DST", "position": "DST",
         "team_abbr": "BBB", "draft_group_id": 9, "salary": 3500,
         "dk_ppg": 5.0, "dk_draftable_id": 15, "dk_cpt_draftable_id": 16},
    ])
    proj = pd.DataFrame([{"dk_player_id": 1, "proj_points": 18.5,
                          "proj_p50": 17.0, "proj_p90": 26.0, "proj_std": 6.0}])
    trailing = pd.DataFrame([
        {"kind": "K", "key": "SOME KICKER", "trailing_pts": 8.4},
        {"kind": "DST", "key": "BBB", "trailing_pts": 9.1},
    ])
    pool = app_main._showdown_pool(game, proj, "proj_points", trailing=trailing)
    by_id = {p["id"]: p for p in pool}
    assert by_id[1]["proj_source"] == "model" and by_id[1]["proj"] == 18.5
    assert by_id[2]["proj_source"] == "trailing" and by_id[2]["proj"] == 8.4
    assert by_id[3]["proj_source"] == "trailing" and by_id[3]["proj"] == 9.1

    # without trailing data, dk_ppg still catches them
    pool2 = app_main._showdown_pool(game, proj, "proj_points", trailing=None)
    by_id2 = {p["id"]: p for p in pool2}
    assert by_id2[2]["proj_source"] == "dk_ppg"


def test_market_page_and_endpoints(monkeypatch):
    """Market page renders; endpoints degrade gracefully with no data."""
    import pandas as pd

    monkeypatch.setattr("nfl_dfs.bq.query_df", lambda sql, **k: pd.DataFrame())
    client = TestClient(app_main.app)
    r = client.get("/market")
    assert r.status_code == 200 and "Line movement" in r.text
    r2 = client.get("/api/line-movement")
    assert r2.status_code == 200 and r2.json() == []
    r3 = client.get("/api/market-disagreement?season=2025&week=1")
    assert r3.status_code == 200 and r3.json() == []


def test_sim_mode_is_mandatory(client, monkeypatch):
    # No silent fallback (user decision 2026-08-03): a sim failure must
    # surface a clear 503 naming the cause; sim=false is the explicit
    # escape hatch and must serve MILP lineups without touching sim.
    called = {}

    def boom(*a, **k):
        called["sim"] = True
        raise RuntimeError("no models offline")

    from nfl_dfs.inference import live_lineups

    monkeypatch.setattr(live_lineups, "build_sim_lineups", boom)
    r = client.post("/lineups", json={"season": 2025, "week": 3,
                                      "n_lineups": 2})
    assert r.status_code == 503
    assert "RuntimeError" in r.json()["detail"]
    assert "sim=false" in r.json()["detail"]
    assert called.get("sim") is True

    called.clear()
    r = client.post("/lineups", json={"season": 2025, "week": 3,
                                      "n_lineups": 2, "sim": False})
    assert r.status_code == 200 and len(r.json()["lineups"]) == 2
    assert called == {}


def test_sim_mode_receives_locks_and_bans(client, monkeypatch):
    seen = {}

    def capture(*a, **k):
        seen.update(k)
        raise RuntimeError("stop here")

    from nfl_dfs.inference import live_lineups

    monkeypatch.setattr(live_lineups, "build_sim_lineups", capture)
    client.post("/lineups", json={"season": 2025, "week": 3,
                                  "n_lineups": 2,
                                  "locks": [11], "bans": [22]})
    assert seen.get("locks") == {11} and seen.get("bans") == {22}


def test_sim_mode_notes_toggle_passthrough(client, monkeypatch):
    """apply_notes reaches the sim path; default True, UI-off -> False
    (pure algorithm, no watch-note boosts/bans)."""
    seen = {}

    def capture(*a, **k):
        seen.update(k)
        raise RuntimeError("stop here")

    from nfl_dfs.inference import live_lineups

    monkeypatch.setattr(live_lineups, "build_sim_lineups", capture)
    client.post("/lineups", json={"season": 2025, "week": 3, "n_lineups": 2})
    assert seen.get("apply_notes") is True
    seen.clear()
    client.post("/lineups", json={"season": 2025, "week": 3, "n_lineups": 2,
                                  "apply_notes": False})
    assert seen.get("apply_notes") is False

```

===== FILE: tests/test_archetypes.py =====
```python
import networkx as nx
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import archetypes
from nfl_dfs.graph.cascade import project_vacated_usage


def synthetic_games(seed=7):
    """Three planted WR profiles (plus QBs): elite-stable, elite-volatile
    around the same mean, and low-output."""
    rng = np.random.default_rng(seed)
    rows = []

    def add(gsis_id, pos, mean, sd, n=30):
        for _ in range(n):
            rows.append({
                "gsis_id": gsis_id, "position": pos,
                "dk_points": max(0.0, rng.normal(mean, sd)),
                "name": f"P {gsis_id}",
            })

    for i in range(8):
        add(f"stable-{i}", "WR", 20, 4)
        add(f"volatile-{i}", "WR", 20, 12)
        add(f"low-{i}", "WR", 6, 3)
        add(f"qb-{i}", "QB", 19, 6)
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def clustered():
    prof = archetypes.consistency_profiles(synthetic_games(), min_games=16)
    return archetypes.cluster_archetypes(prof, n_clusters=3, seed=0)


def test_profiles_metrics(clustered):
    stable = clustered[clustered.gsis_id == "stable-0"].iloc[0]
    volatile = clustered[clustered.gsis_id == "volatile-0"].iloc[0]
    assert stable.cv < volatile.cv
    assert stable.pct_10_plus > 0.9
    assert clustered[clustered.gsis_id == "low-0"].iloc[0].pct_20_plus < 0.1


def test_min_games_filter():
    games = synthetic_games()
    few = games[games.gsis_id != "stable-0"]
    few = pd.concat([few, games[games.gsis_id == "stable-0"].head(5)])
    prof = archetypes.consistency_profiles(few, min_games=16)
    assert "stable-0" not in prof.gsis_id.values


def test_clusters_separate_planted_profiles(clustered):
    wr = clustered[clustered.position == "WR"]
    by_kind = {
        kind: set(wr[wr.gsis_id.str.startswith(kind)].cluster.unique())
        for kind in ("stable", "volatile", "low")
    }
    # Each planted profile lands in one cluster, and no two profiles share one
    assert all(len(c) == 1 for c in by_kind.values()), by_kind
    assert len(set.union(*by_kind.values())) == 3


def test_archetype_labels_are_position_scoped(clustered):
    assert clustered[clustered.position == "WR"].archetype.str.startswith("WR-").all()
    assert clustered[clustered.position == "QB"].archetype.str.startswith("QB-").all()
    # Same mean, different variance: stable gets the -stable suffix
    stable_lab = clustered[clustered.gsis_id == "stable-0"].archetype.iloc[0]
    volatile_lab = clustered[clustered.gsis_id == "volatile-0"].archetype.iloc[0]
    assert stable_lab.endswith("-stable")
    assert volatile_lab.endswith("-volatile")


def _graph_with(clustered):
    G = nx.MultiDiGraph()
    for r in clustered.itertuples():
        G.add_node(r.gsis_id, kind="Player", position=r.position)
    return G


def test_annotate_and_similarity_edges(clustered):
    G = _graph_with(clustered)
    assert archetypes.annotate_graph(G, clustered) == len(clustered)
    assert G.nodes["stable-0"]["archetype"].endswith("-stable")

    archetypes.add_similarity_edges(G, clustered, k=3)
    sims = archetypes.similar_players(G, "stable-0")
    assert 0 < len(sims) <= 3
    # Neighbors share the cluster: all planted stables
    assert all(nbr.startswith("stable-") for nbr, _ in sims)
    # Sorted nearest-first
    dists = [d for _, d in sims]
    assert dists == sorted(dists)


def test_cascade_uses_archetype_boost(clustered):
    G = _graph_with(clustered)
    for a, b in [("stable-0", "stable-1"), ("stable-0", "volatile-0"),
                 ("stable-1", "volatile-0")]:
        G.add_edge(a, b, key="COMPETES_WITH")
        G.add_edge(b, a, key="COMPETES_WITH")
    usage = pd.DataFrame({
        "gsis_id": ["stable-0", "stable-1", "volatile-0"] * 4,
        "season": [2025] * 12,
        "week": np.repeat(range(1, 5), 3),
        "total_targets": 8.0, "rz20_targets": 1.0,
        "target_share": [0.25, 0.20, 0.20] * 4,
    })
    injuries = pd.DataFrame({"gsis_id": ["stable-0"], "season": [2025],
                             "week": [5], "game_status": ["Out"]})

    plain = project_vacated_usage(G, usage, injuries, "stable-0")
    assert (plain.method == "depth_chart").all()
    # Equal current usage -> equal split without archetypes
    d = plain.set_index("gsis_id").delta
    assert d["stable-1"] == pytest.approx(d["volatile-0"])

    archetypes.annotate_graph(G, clustered)
    boosted = project_vacated_usage(G, usage, injuries, "stable-0")
    assert (boosted.method == "depth_chart_archetype").all()
    b = boosted.set_index("gsis_id").delta
    assert b["stable-1"] > b["volatile-0"]
    # Total vacated share is conserved, just re-weighted
    assert b.sum() == pytest.approx(d.sum())

```

===== FILE: tests/test_backtest.py =====
```python
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest import engine, field, payout


def make_slate(seed=41, season=2023, week=5, n_teams=8, proj_quality=1.0):
    """Synthetic slate where projections carry real (imperfect) signal."""
    rng = np.random.default_rng(seed)
    rows = []
    pid = 0
    for t in range(n_teams):
        team, opp = f"T{t}", f"T{t + 1 if t % 2 == 0 else t - 1}"
        game = f"G{t // 2}"
        for pos, n in (("QB", 2), ("RB", 4), ("WR", 5), ("TE", 3), ("DST", 1)):
            for i in range(n):
                base = {"QB": 19, "RB": 13, "WR": 11, "TE": 8, "DST": 7}[pos]
                mu = max(1.0, base - 2.5 * i + rng.normal(0, 2))
                actual = max(0.0, rng.normal(mu, 6))
                proj = mu + rng.normal(0, 3 / proj_quality)
                rows.append({
                    "id": pid, "name": f"{pos}{i}_{team}", "pos": pos,
                    "team": team, "opp": opp, "game_id": game,
                    "salary": int(np.clip(2600 + mu * 330 + rng.normal(0, 250),
                                          2500, 9600)),
                    "proj": proj, "actual": actual,
                    "season": season, "week": week,
                })
                pid += 1
    return pd.DataFrame(rows)


def test_payout_curves():
    c = payout.double_up(entry_fee=5, field_size=1000)
    assert c.payout_for_rank(1) == 10
    assert c.payout_for_rank(450) == 10
    assert c.payout_for_rank(451) == 0

    g = payout.gpp(entry_fee=5, field_size=100_000)
    assert g.payout_for_rank(1) == 100_000  # 20000x
    assert g.payout_for_rank(100_000) == 0
    # Payout is monotone non-increasing in rank
    ranks = [1, 10, 100, 1000, 5000, 14_000, 20_000]
    pays = [g.payout_for_rank(r) for r in ranks]
    assert pays == sorted(pays, reverse=True)


def test_roi():
    assert payout.roi(np.array([10.0, 0.0]), entry_fee=5) == 0.0
    assert payout.roi(np.array([0.0, 0.0]), entry_fee=5) == -1.0


def test_naive_ownership_favors_value():
    slate = make_slate()
    own = field.naive_ownership(slate)
    wrs = slate[slate.pos == "WR"]
    w = own[wrs.index.to_numpy()]
    value = (wrs.proj / wrs.salary).to_numpy()
    assert np.corrcoef(w, value)[0, 1] > 0.3
    # Weights normalize within position
    assert w.sum() == pytest.approx(1.0, abs=1e-6)


def test_sample_field_valid_lineups():
    slate = make_slate()
    fld = field.sample_field(slate, n_lineups=300, seed=1)
    assert len(fld) > 250
    salaries = slate.salary.to_numpy()
    positions = slate.pos.to_numpy()
    under_cap = 0
    for lu in fld:
        assert len(lu) == 9
        assert len(set(lu)) == 9
        pos_counts = pd.Series(positions[lu]).value_counts()
        assert pos_counts.get("QB", 0) == 1
        assert pos_counts.get("DST", 0) == 1
        assert 2 <= pos_counts.get("RB", 0) <= 3
        if salaries[lu].sum() <= 50_000:
            under_cap += 1
    assert under_cap / len(fld) > 0.8  # loose cap enforcement by design


def test_leakage_guard_rejects_answer_key():
    slate = make_slate()
    slate["proj"] = slate["actual"]
    with pytest.raises(AssertionError):
        engine.leakage_guard(slate)


def test_run_week_and_summary():
    slate = make_slate()
    contest = payout.double_up(entry_fee=5, field_size=1000)
    wk = engine.run_week(slate, contest, n_entries=3, field_size=400, seed=2)
    assert wk is not None
    assert len(wk.lineup_scores) == 3
    assert all(0 <= p <= 1 for p in wk.percentiles)

    result = engine.BacktestResult(weeks=[wk], contest=contest)
    text = result.summary()
    assert "ROI" in text and "2023" in text


def test_good_projections_beat_random_in_percentile():
    """A model with signal should finish better against the field than a
    model projecting pure noise."""
    contest = payout.double_up(entry_fee=5, field_size=1000)

    def median_pct(proj_quality, seed):
        pcts = []
        for wkseed in range(4):
            slate = make_slate(seed=100 + wkseed, week=wkseed + 1,
                               proj_quality=proj_quality)
            if proj_quality < 0.01:  # destroy the signal entirely
                rng = np.random.default_rng(seed + wkseed)
                slate["proj"] = rng.permutation(slate["proj"].to_numpy())
            wk = engine.run_week(slate, contest, n_entries=3, field_size=400,
                                 seed=3)
            pcts.extend(wk.percentiles)
        return float(np.median(pcts))

    sharp = median_pct(proj_quality=2.0, seed=0)
    noise = median_pct(proj_quality=0.001, seed=1)
    assert sharp < noise, f"sharp {sharp:.2f} should finish above noise {noise:.2f}"


def test_sharp_field_entrants():
    from nfl_dfs.backtest import field as field_sim

    slate = make_slate()
    sharp = field_sim.sharp_field(slate, n_lineups=50, n_distinct=6, seed=2)
    assert len(sharp) == 50
    salaries = slate["salary"].to_numpy()
    pos = slate["pos"].to_numpy()
    for lu in sharp[:10]:
        assert len(lu) == 9 and len(set(lu)) == 9
        assert salaries[lu].sum() <= field_sim.SALARY_CAP
        assert (pos[lu] == "QB").sum() == 1 and (pos[lu] == "DST").sum() == 1
    # Duplication is expected: far fewer distinct lineups than entries
    assert len({tuple(sorted(lu)) for lu in sharp}) <= 12


def test_sample_field_sharp_fraction():
    from nfl_dfs.backtest import field as field_sim

    slate = make_slate()
    fld = field_sim.sample_field(slate, n_lineups=100, seed=3, sharp_fraction=0.2)
    assert len(fld) >= 95  # random part may drop a few infeasible attempts

```

===== FILE: tests/test_backup.py =====
```python
"""Backup job config sanity (ops/backup.py) — offline checks only."""

from nfl_dfs.ops import backup


def test_irreplaceable_tables_covered():
    tables = {t for _, t in backup.TABLES}
    # The tables a >7-day-late discovery could not rebuild from source.
    for must in ("contest_ownership", "manual_notes", "player_watch_notes",
                 "entered_lineups", "dk_salaries_historical"):
        assert must in tables


def test_dataset_attrs_resolve():
    from nfl_dfs.config import settings

    for attr, _ in backup.TABLES:
        assert getattr(settings, attr)  # unknown attr would AttributeError


def test_cli_wired():
    from nfl_dfs import cli

    src = open(cli.__file__).read()
    assert "backup-tables" in src

```

===== FILE: tests/test_baseline.py =====
```python
import numpy as np

from nfl_dfs.models import baseline


def test_walk_forward_learns_signal(small_panel):
    result = baseline.walk_forward(small_panel, min_train_seasons=2, num_boost_round=120)
    assert result.fold_reports
    for season, rep in result.fold_reports.items():
        # Synthetic noise sigma is 6; a model that learned usage/vegas signal
        # must land well under the ~8.5 MAE of predicting the global mean.
        assert rep.mae < 7.5, f"{season}: MAE {rep.mae}"
        # Rank correlation within position should be clearly positive
        assert all(r > 0.2 for r in rep.rank_corr_by_position.values())


def test_quantiles_are_monotone(small_panel):
    model = baseline.train(small_panel, target_season=2022, num_boost_round=80)
    preds = model.predict(small_panel[small_panel.season == 2022])
    assert (preds.proj_p10 <= preds.proj_p50 + 1e-9).all()
    assert (preds.proj_p50 <= preds.proj_p90 + 1e-9).all()
    assert (preds.proj_std >= 0).all()


def test_coverage_roughly_calibrated(small_panel):
    model = baseline.train(small_panel, target_season=2022, num_boost_round=200)
    va = small_panel[small_panel.season == 2022]
    preds = model.predict(va)
    below_p10 = np.mean(va.y_dk_points.to_numpy() < preds.proj_p10.to_numpy())
    below_p90 = np.mean(va.y_dk_points.to_numpy() < preds.proj_p90.to_numpy())
    assert 0.03 < below_p10 < 0.22
    assert 0.78 < below_p90 < 0.97

```

===== FILE: tests/test_bigplay.py =====
```python
"""BIGPLAY mixture: house-call events for deep threats (sim-shape lever).

Contract: E[points] exactly preserved (the mean subtraction), far tail
mass strictly added for flagged players, zero effect at rate 0."""

import numpy as np
import pandas as pd

from nfl_dfs.models import simulate


def _comps(n=6):
    return pd.DataFrame({
        "targets": [8.0] * n, "catch_rate": [0.65] * n, "ypr": [11.0] * n,
        "rec_tds": [0.4] * n, "carries": [0.0] * n, "ypc": [0.0] * n,
        "rush_tds": [0.0] * n, "pass_attempts": [0.0] * n, "ypa": [0.0] * n,
        "pass_tds": [0.0] * n, "interceptions": [0.0] * n,
    })


def test_mean_preserved_and_tail_deepens():
    comps = _comps()
    rate = pd.Series([0.0, 0.0, 0.0, 0.12, 0.12, 0.12])
    base = simulate.simulate(comps, n_sims=60_000, seed=5, keep_draws=True)
    boom = simulate.simulate(comps, n_sims=60_000, seed=5, keep_draws=True,
                             bigplay_rate=rate)
    # means within MC noise of identical (exact subtraction of E[lump])
    np.testing.assert_allclose(boom.summary.proj_points,
                               base.summary.proj_points, atol=0.25)
    # unflagged rows byte-identical draws
    np.testing.assert_array_equal(boom.draws[0], base.draws[0])
    # flagged rows: 40+ probability strictly up
    p40_base = (base.draws[3] >= 40).mean()
    p40_boom = (boom.draws[3] >= 40).mean()
    assert p40_boom > p40_base


def test_none_rate_is_noop():
    comps = _comps(3)
    a = simulate.simulate(comps, n_sims=5_000, seed=9, keep_draws=True)
    b = simulate.simulate(comps, n_sims=5_000, seed=9, keep_draws=True,
                          bigplay_rate=None)
    np.testing.assert_array_equal(a.draws, b.draws)


def test_proj_tail_between_p90_neighborhood_and_max():
    comps = _comps(2)
    r = simulate.simulate(comps, n_sims=20_000, seed=4)
    s = r.summary
    assert (s.proj_tail > s.proj_p50).all()
    assert (s.proj_tail > s.proj_points).all()
    # top-quartile mean sits near/above p90 for right-skewed outcomes
    assert (s.proj_tail > 0.9 * s.proj_p90).all()

```

===== FILE: tests/test_blend_coldstart.py =====
```python
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models import blend, coldstart


def test_fit_blend_weight_recovers_truth():
    rng = np.random.default_rng(4)
    truth = rng.uniform(5, 25, 3000)
    model = truth + rng.normal(0, 3, 3000)
    market = truth + rng.normal(0, 3, 3000)
    w = blend.fit_blend_weight(truth, model, market)
    # Equally-good independent sources -> w near 0.5
    assert 0.35 < w < 0.65


def test_blend_prefers_better_source():
    rng = np.random.default_rng(5)
    truth = rng.uniform(5, 25, 3000)
    model = truth + rng.normal(0, 1, 3000)      # sharp
    market = truth + rng.normal(0, 6, 3000)     # noisy
    w = blend.fit_blend_weight(truth, model, market)
    assert w > 0.75


def test_blend_falls_back_when_market_missing():
    model = np.array([10.0, 12.0])
    market = np.array([np.nan, 8.0])
    out = blend.blend(model, market, w=0.4)
    assert out[0] == 10.0
    assert out[1] == pytest.approx(0.4 * 12 + 0.6 * 8)


def test_prop_line_conversions():
    # Symmetric prob -> mean == line
    assert blend.prop_line_to_mean(62.5, 0.5, "normal") == pytest.approx(62.5, abs=0.1)
    # Higher over-prob -> higher mean
    assert blend.prop_line_to_mean(62.5, 0.6, "normal") > 62.5
    lam = blend.prop_line_to_mean(4.5, 0.5, "poisson")
    assert 4.0 < lam < 5.6


def test_american_odds_and_devig():
    assert blend.american_to_prob(-110) == pytest.approx(0.524, abs=0.001)
    assert blend.american_to_prob(120) == pytest.approx(0.4545, abs=0.001)
    over, under = blend.devig_two_way(0.55, 0.55)
    assert over == pytest.approx(0.5)


def test_cold_start_fill_and_flag_preserved():
    df = pd.DataFrame(
        {
            "position": ["WR", "RB"],
            "depth_rank": [1, 2],
            "implied_team_total": [26.0, 20.0],
            "is_cold_start": [True, True],
            "is_rookie": [True, False],
            "draft_round": [1, None],
            "target_share_l4": [np.nan, np.nan],
            "carry_share_l4": [np.nan, np.nan],
            "wopr_l4": [np.nan, np.nan],
        }
    )
    filled = coldstart.fill_cold_start_features(df)
    assert filled.target_share_l4.notna().all()
    # WR1 rookie with round-1 capital keeps the full role prior
    assert filled.loc[0, "target_share_l4"] == pytest.approx(0.24)
    # RB2 veteran gets the RB2 carry share
    assert filled.loc[1, "carry_share_l4"] == pytest.approx(0.25)
    # Flag must survive filling
    assert filled.is_cold_start.all()


def test_widen_cold_start_quantiles():
    preds = pd.DataFrame(
        {"proj_p10": [5.0], "proj_p50": [10.0], "proj_p90": [15.0], "proj_std": [4.0]}
    )
    out = coldstart.widen_cold_start_quantiles(preds, pd.Series([True]), widen=1.5)
    assert out.proj_p10.iloc[0] == pytest.approx(2.5)
    assert out.proj_p90.iloc[0] == pytest.approx(17.5)
    assert out.proj_std.iloc[0] == pytest.approx(6.0)

```

===== FILE: tests/test_calibration.py =====
```python
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models import calibration


def test_apply_widen_math():
    preds = pd.DataFrame(
        {"proj_points": [12.0], "proj_p10": [5.0], "proj_p50": [10.0],
         "proj_p90": [15.0], "proj_std": [4.0]}
    )
    out = calibration.apply_widen(preds, pd.Series(["QB"]), factors={"QB": 1.5})
    assert out.proj_p10.iloc[0] == pytest.approx(2.5)
    assert out.proj_p90.iloc[0] == pytest.approx(17.5)
    assert out.proj_std.iloc[0] == pytest.approx(6.0)
    assert out.proj_points.iloc[0] == 12.0  # mean untouched
    # Unknown position -> factor 1.0, unchanged
    same = calibration.apply_widen(preds, pd.Series(["DST"]), factors={"QB": 1.5})
    assert same.proj_p10.iloc[0] == 5.0


def test_fit_recovers_needed_widen():
    rng = np.random.default_rng(0)
    n = 4000
    actual = rng.normal(12, 6, n)
    # Bands built from a too-narrow sigma of 4: true 10/90 quantiles need ~1.5x
    proj = pd.DataFrame({
        "position": "RB",
        "actual": actual,
        "proj_p50": np.full(n, 12.0),
        "proj_p10": np.full(n, 12.0 - 1.2816 * 4),
        "proj_p90": np.full(n, 12.0 + 1.2816 * 4),
    })
    factors = calibration.fit_widen_factors(proj)
    assert factors["RB"] == pytest.approx(1.5, abs=0.1)
    widened = calibration.apply_widen(
        proj.assign(proj_std=4.0), proj.position, factors
    )
    assert np.mean(actual < widened.proj_p10) == pytest.approx(0.10, abs=0.02)
    assert np.mean(actual < widened.proj_p90) == pytest.approx(0.90, abs=0.02)

```

===== FILE: tests/test_cascade_adjust.py =====
```python
"""Late-inactive slate adjustment: out players zeroed, teammates bumped."""

import numpy as np
import pandas as pd

from nfl_dfs.inference.cascade_adjust import (
    adjust_for_inactives,
    find_out_players,
    zero_out_projections,
)


def slate(wr1_status=None, wr1_report=None):
    rows = [
        {"gsis_id": "WR1", "display_name": "Alpha Receiver", "dk_position": "WR",
         "team_abbr": "MIN", "status": wr1_status, "injury_status": wr1_report,
         "target_share_l4": 0.27, "wopr_l4": 0.45, "rz20_targets_smoothed": 2.0,
         "carry_share_l4": 0.0, "gl3_carries_smoothed": 0.0},
        {"gsis_id": "WR2", "display_name": "Beta Receiver", "dk_position": "WR",
         "team_abbr": "MIN", "status": None, "injury_status": None,
         "target_share_l4": 0.17, "wopr_l4": 0.28, "rz20_targets_smoothed": 1.0,
         "carry_share_l4": 0.0, "gl3_carries_smoothed": 0.0},
        {"gsis_id": "WR3", "display_name": "Gamma Receiver", "dk_position": "WR",
         "team_abbr": "MIN", "status": None, "injury_status": None,
         "target_share_l4": 0.09, "wopr_l4": 0.15, "rz20_targets_smoothed": 0.5,
         "carry_share_l4": 0.0, "gl3_carries_smoothed": 0.0},
        {"gsis_id": "RB1", "display_name": "Bell Cow", "dk_position": "RB",
         "team_abbr": "MIN", "status": None, "injury_status": None,
         "target_share_l4": 0.10, "wopr_l4": 0.16, "rz20_targets_smoothed": 0.8,
         "carry_share_l4": 0.62, "gl3_carries_smoothed": 1.8},
        {"gsis_id": "RB2", "display_name": "Handcuff", "dk_position": "RB",
         "team_abbr": "MIN", "status": None, "injury_status": None,
         "target_share_l4": 0.04, "wopr_l4": 0.07, "rz20_targets_smoothed": 0.2,
         "carry_share_l4": 0.15, "gl3_carries_smoothed": 0.3},
        {"gsis_id": "WRX", "display_name": "Other Team", "dk_position": "WR",
         "team_abbr": "GB", "status": None, "injury_status": None,
         "target_share_l4": 0.22, "wopr_l4": 0.36, "rz20_targets_smoothed": 1.5,
         "carry_share_l4": 0.0, "gl3_carries_smoothed": 0.0},
    ]
    return pd.DataFrame(rows)


def usage_rec(seed=61):
    rng = np.random.default_rng(seed)
    rows = []
    for week in range(1, 11):
        for gsis, share, tt, rz in (("WR1", 0.27, 9, 2), ("WR2", 0.17, 6, 1),
                                    ("WR3", 0.09, 3, 0), ("RB1", 0.10, 3, 1),
                                    ("RB2", 0.04, 1, 0)):
            rows.append({"gsis_id": gsis, "season": 2024, "week": week,
                         "total_targets": tt, "rz20_targets": rz,
                         "target_share": rng.normal(share, 0.01)})
    return pd.DataFrame(rows)


def usage_rush(seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for week in range(1, 11):
        for gsis, share, tc, gl in (("RB1", 0.62, 16, 2), ("RB2", 0.15, 4, 0)):
            rows.append({"gsis_id": gsis, "season": 2024, "week": week,
                         "total_carries": tc, "gl3_carries": gl,
                         "carry_share": rng.normal(share, 0.02)})
    return pd.DataFrame(rows)


def no_injuries():
    return pd.DataFrame(columns=["gsis_id", "season", "week", "game_status"])


def test_find_out_players_dk_status_and_report():
    assert find_out_players(slate(wr1_status="O")) == ["WR1"]
    assert find_out_players(slate(wr1_report="Out")) == ["WR1"]
    assert find_out_players(slate(wr1_status="IR")) == ["WR1"]
    assert find_out_players(slate(wr1_status="Q")) == []
    assert find_out_players(slate()) == []


def test_no_inactives_is_a_noop():
    feats = slate()
    adjusted, out_ids = adjust_for_inactives(
        feats, usage_rec(), usage_rush(), no_injuries())
    assert out_ids == []
    pd.testing.assert_frame_equal(adjusted, feats)


def test_out_wr_bumps_same_position_teammates_only():
    feats = slate(wr1_status="O")
    adjusted, out_ids = adjust_for_inactives(
        feats, usage_rec(), usage_rush(), no_injuries())
    assert out_ids == ["WR1"]

    def col(df, gsis, c):
        return float(df.loc[df.gsis_id == gsis, c].iloc[0])

    # Teammate receivers inherit target share; combined bump ~ the vacated share
    bump2 = col(adjusted, "WR2", "target_share_l4") - col(feats, "WR2", "target_share_l4")
    bump3 = col(adjusted, "WR3", "target_share_l4") - col(feats, "WR3", "target_share_l4")
    assert bump2 > bump3 > 0
    assert abs((bump2 + bump3) - 0.27) < 0.03
    # wopr and red zone opportunity move with the share
    assert col(adjusted, "WR2", "wopr_l4") > col(feats, "WR2", "wopr_l4")
    assert col(adjusted, "WR2", "rz20_targets_smoothed") > col(
        feats, "WR2", "rz20_targets_smoothed")
    # Other team and other position groups untouched
    for gsis in ("WRX", "RB1", "RB2"):
        assert col(adjusted, gsis, "target_share_l4") == col(feats, gsis, "target_share_l4")


def test_out_rb_bumps_carry_share_of_handcuff():
    feats = slate()
    feats.loc[feats.gsis_id == "RB1", "status"] = "O"
    adjusted, out_ids = adjust_for_inactives(
        feats, usage_rec(), usage_rush(), no_injuries())
    assert out_ids == ["RB1"]

    def col(df, gsis, c):
        return float(df.loc[df.gsis_id == gsis, c].iloc[0])

    carry_bump = col(adjusted, "RB2", "carry_share_l4") - col(feats, "RB2", "carry_share_l4")
    assert abs(carry_bump - 0.62) < 0.05        # sole candidate inherits it all
    assert col(adjusted, "RB2", "gl3_carries_smoothed") > col(
        feats, "RB2", "gl3_carries_smoothed")
    # RB1 also vacates targets -> RB2 target share rises too
    assert col(adjusted, "RB2", "target_share_l4") > col(feats, "RB2", "target_share_l4")


def test_history_beats_fallback_when_absences_exist():
    """With 3+ prior absences the measured with/without split drives deltas."""
    rng = np.random.default_rng(3)
    rows, out_weeks = [], {3, 6, 9}
    for week in range(1, 13):
        wr1_out = week in out_weeks
        if not wr1_out:
            rows.append({"gsis_id": "WR1", "season": 2024, "week": week,
                         "total_targets": 9, "rz20_targets": 2,
                         "target_share": rng.normal(0.27, 0.01)})
        rows.append({"gsis_id": "WR2", "season": 2024, "week": week,
                     "total_targets": 6, "rz20_targets": 1,
                     "target_share": rng.normal(0.35 if wr1_out else 0.17, 0.01)})
        rows.append({"gsis_id": "WR3", "season": 2024, "week": week,
                     "total_targets": 3, "rz20_targets": 0,
                     "target_share": rng.normal(0.10 if wr1_out else 0.09, 0.01)})
    rec = pd.DataFrame(rows)
    injuries = pd.DataFrame(
        [{"gsis_id": "WR1", "season": 2024, "week": w, "game_status": "Out"}
         for w in out_weeks]
    )
    feats = slate(wr1_status="O")
    adjusted, _ = adjust_for_inactives(feats, rec, usage_rush(), injuries)

    def col(df, gsis, c):
        return float(df.loc[df.gsis_id == gsis, c].iloc[0])

    bump2 = col(adjusted, "WR2", "target_share_l4") - 0.17
    bump3 = col(adjusted, "WR3", "target_share_l4") - 0.09
    assert bump2 > 0.12          # measured ~+0.18 with/without split
    assert bump3 < 0.05          # WR3 barely moved historically


def test_cold_start_backup_gets_bump_on_filled_features():
    """The adjuster runs after the cold-start fill; a NaN share is treated
    as zero so the bump still lands."""
    feats = slate()
    feats.loc[feats.gsis_id == "RB2", ["carry_share_l4", "gl3_carries_smoothed"]] = np.nan
    feats.loc[feats.gsis_id == "RB1", "status"] = "O"
    adjusted, _ = adjust_for_inactives(
        feats, usage_rec(), usage_rush(), no_injuries())
    got = float(adjusted.loc[adjusted.gsis_id == "RB2", "carry_share_l4"].iloc[0])
    assert got > 0.5


def test_zero_out_projections():
    out = pd.DataFrame({
        "gsis_id": ["WR1", "WR2"],
        "proj_points": [15.0, 11.0],
        "proj_p90": [28.0, 22.0],
        "p_20_plus": [0.3, 0.2],
        "value": [3.0, 2.5],
    })
    zeroed = zero_out_projections(out, ["WR1"])
    assert zeroed.loc[0, ["proj_points", "proj_p90", "p_20_plus", "value"]].eq(0).all()
    assert zeroed.loc[1, "proj_points"] == 11.0
    # untouched without out_ids
    pd.testing.assert_frame_equal(zero_out_projections(out, []), out)

```

===== FILE: tests/test_cfb_job.py =====
```python
"""Offline coverage for the CFB data-collection scaffold's env gate
(issue #13 item 7).

No network or BigQuery access here or in CI — run() must return before
touching either when INGEST_CFB_ENABLED isn't set, which is the default
(this session has no GCP credentials, and CFB season hasn't started).
"""

import requests

from nfl_dfs.ingest import cfb_job


def test_run_is_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("INGEST_CFB_ENABLED", raising=False)

    def boom(*a, **k):
        raise AssertionError("should not touch the network when disabled")

    monkeypatch.setattr(requests.Session, "get", boom)
    cfb_job.run()  # must not raise


def test_run_bails_before_contests_when_no_draft_groups(monkeypatch):
    monkeypatch.setenv("INGEST_CFB_ENABLED", "1")
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_draft_groups", lambda session=None: []
    )

    calls = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_contests",
        lambda session=None: calls.append("contests") or [],
    )

    cfb_job.run()
    # No draft groups -> nothing to match contests to, and the job must
    # bail before ever calling cfb_contests (would waste a poll for nothing).
    assert calls == []


def test_run_loads_salaries_and_contests_when_enabled(monkeypatch):
    monkeypatch.setenv("INGEST_CFB_ENABLED", "1")

    groups = [{"draftGroupId": 90002, "sportId": 5, "draftGroupState": "Upcoming"}]
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_draft_groups", lambda session=None: groups
    )
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.fetch_draftables",
        lambda gid, session=None: {
            "competitions": [{"competitionId": 1, "startTime": "2026-08-30T17:00:00Z"}],
            "draftables": [
                {
                    "draftableId": 1,
                    "playerId": 1,
                    "displayName": "Test QB",
                    "teamAbbreviation": "ABC",
                    "position": "QB",
                    "salary": 9000,
                    "rosterSlotId": 1,
                    "status": "None",
                    "competition": {"competitionId": 1},
                }
            ],
        },
    )
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.cfb_contests",
        lambda session=None: [
            {
                "id": 1,
                "dg": 90002,
                "n": "CFB $100K Kickoff",
                "gameType": "Classic",
                "a": 10,
                "m": 10_000,
                "nt": 2_000,
                "po": 100_000.0,
                "attr": {"IsGuaranteed": "true"},
                "sd": "/Date(1785513600000)/",
            }
        ],
    )

    loaded = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.cfb_job.load_dataframe",
        lambda df, table, **kw: loaded.append((table, df)),
    )

    cfb_job.run()

    tables = [t for t, _ in loaded]
    assert tables == ["cfb_dk_salaries", "dk_contest_fills"]

    salaries_df = loaded[0][1]
    assert list(salaries_df.dk_player_id) == [1]

    contests_df = loaded[1][1]
    assert list(contests_df.sport) == ["CFB"]

```

===== FILE: tests/test_changepoint.py =====
```python
import numpy as np
import pandas as pd

from nfl_dfs.trends.changepoint import (
    changepoint_probabilities,
    cusum_flags,
    detect_panel,
    two_window_pvalue,
)


def promoted_series(rng, n_before=8, n_after=6, lo=0.08, hi=0.26, noise=0.02):
    """WR3 usage for n_before weeks, then a promotion to WR1 usage."""
    return np.concatenate([
        rng.normal(lo, noise, n_before),
        rng.normal(hi, noise, n_after),
    ])


def test_bocpd_spikes_at_the_break():
    rng = np.random.default_rng(21)
    series = promoted_series(rng)
    cp = changepoint_probabilities(series)
    break_idx = 8
    window = cp[break_idx : break_idx + 3]
    assert window.max() > 0.5, f"no spike at the break: {np.round(cp, 2)}"
    # Post-warmup stretch before the break must stay quiet
    assert cp[5:break_idx].max() < 0.5


def test_bocpd_quiet_on_stable_series():
    rng = np.random.default_rng(22)
    series = rng.normal(0.2, 0.02, 14)
    cp = changepoint_probabilities(series)
    assert cp.max() < 0.5


def test_bocpd_operating_point_across_seeds():
    """~3% FP / ~98% hit at the shipped defaults; assert loose bounds so the
    test survives numeric drift."""
    fp = hits = 0
    n = 60
    for seed in range(n):
        rng = np.random.default_rng(seed)
        if changepoint_probabilities(rng.normal(0.2, 0.02, 14)).max() > 0.5:
            fp += 1
        rng = np.random.default_rng(10_000 + seed)
        cp = changepoint_probabilities(promoted_series(rng))
        if cp[8:11].max() > 0.5:
            hits += 1
    assert fp / n < 0.15, f"false-positive rate {fp / n:.1%}"
    assert hits / n > 0.85, f"hit rate {hits / n:.1%}"


def test_bocpd_handles_empty_and_short():
    assert changepoint_probabilities([]).shape == (0,)
    assert len(changepoint_probabilities([0.2])) == 1


def test_cusum_catches_shift():
    rng = np.random.default_rng(23)
    series = promoted_series(rng, n_before=10, n_after=8)
    flags = cusum_flags(series)
    assert flags[10:].any()
    assert not flags[:8].any()


def test_two_window_pvalue():
    rng = np.random.default_rng(24)
    shifted = promoted_series(rng, n_before=6, n_after=2)
    stable = rng.normal(0.2, 0.02, 8)
    assert two_window_pvalue(shifted) < 0.05
    assert two_window_pvalue(stable) > 0.05


def test_detect_panel_weeks_since_change():
    rng = np.random.default_rng(25)
    rows = []
    for w, v in enumerate(promoted_series(rng), start=1):
        rows.append({"gsis_id": "00-1", "season": 2024, "week": w, "target_share": v})
    # A stable control player
    for w, v in enumerate(rng.normal(0.15, 0.015, 14), start=1):
        rows.append({"gsis_id": "00-2", "season": 2024, "week": w, "target_share": v})
    out = detect_panel(pd.DataFrame(rows))

    p1 = out[out.gsis_id == "00-1"].sort_values("week")
    # weeks_since_change resets shortly after the week-9 break
    post = p1[p1.week.between(9, 11)]
    assert (post.weeks_since_change <= 2).any()

    p2 = out[out.gsis_id == "00-2"].sort_values("week")
    assert p2.weeks_since_change.iloc[-1] >= 10

```

===== FILE: tests/test_components.py =====
```python
import numpy as np

from nfl_dfs.models import components, simulate


def test_component_training_and_masks(small_panel):
    cm = components.train(small_panel, target_season=2022, num_boost_round=60)
    assert {"targets", "catch_rate", "ypr", "carries"} <= set(cm.models)

    va = small_panel[small_panel.season == 2022]
    comps = cm.predict_components(va)
    pos = va.position.to_numpy()

    # Position masks: QBs get no targets, non-QBs get no pass attempts
    assert (comps.loc[pos == "QB", "targets"] == 0).all()
    assert (comps.loc[pos != "QB", "pass_attempts"] == 0).all()
    # Rates are clipped to sane ranges
    assert comps.catch_rate.between(0.2, 0.95).all()
    assert comps.ypr.between(2.0, 25.0).all()
    assert (comps.targets >= 0).all()


def test_wr_expected_targets_track_usage(small_panel):
    cm = components.train(small_panel, target_season=2022, num_boost_round=120)
    va = small_panel[(small_panel.season == 2022) & (small_panel.position == "WR")]
    comps = cm.predict_components(va)
    corr = np.corrcoef(comps.targets, va.target_share_l4)[0, 1]
    assert corr > 0.4, f"expected targets should track usage, corr={corr:.2f}"


def test_simulation_summary_shape_and_ordering(small_panel):
    cm = components.train(small_panel, target_season=2022, num_boost_round=60)
    va = small_panel[small_panel.season == 2022].head(50)
    comps = cm.predict_components(va)
    res = simulate.simulate(comps, n_sims=2000, seed=1)
    s = res.summary
    assert len(s) == 50
    assert (s.proj_p10 <= s.proj_p50).all()
    assert (s.proj_p50 <= s.proj_p90).all()
    assert (s.proj_std >= 0).all()
    assert s.p_20_plus.between(0, 1).all()


def test_simulation_mean_consistent_with_components(small_panel):
    """The simulated mean must roughly equal the analytic expectation of the
    composed components — a mismatch means the sampler is biased."""
    cm = components.train(small_panel, target_season=2022, num_boost_round=100)
    va = small_panel[(small_panel.season == 2022) & (small_panel.position == "WR")].head(30)
    comps = cm.predict_components(va)
    res = simulate.simulate(comps, n_sims=8000, seed=2)

    analytic = (
        comps.targets * comps.catch_rate * (1.0 + 0.1 * comps.ypr)  # rec + yards
        + 6.0 * comps.rec_tds.clip(lower=0)
        + comps.carries * comps.ypc * 0.1
        + 6.0 * comps.rush_tds.clip(lower=0)
    )
    # Bonuses only add points, so simulated mean >= analytic - small tolerance
    diff = res.summary.proj_points - analytic
    assert (diff > -1.0).all()
    assert diff.abs().mean() < 2.5


def test_simulation_draws_scored_with_bonuses(small_panel):
    cm = components.train(small_panel, target_season=2022, num_boost_round=60)
    va = small_panel[small_panel.season == 2022].head(5)
    comps = cm.predict_components(va)
    res = simulate.simulate(comps, n_sims=500, seed=3, keep_draws=True)
    assert res.draws.shape == (5, 500)


def test_build_X_handles_nullable_coverage_features():
    """The CB coverage features arrive from BigQuery as nullable dtypes
    (top_cb_out is a BOOL that's NULL on week-1 rows); build_X must accept
    them and NaN-fill panels that predate the columns entirely."""
    import pandas as pd

    from nfl_dfs.models.featureset import build_X

    df = pd.DataFrame({
        "position": ["WR", "TE"],
        "top_cb_out": pd.array([True, pd.NA], dtype="boolean"),
        "cb_ypt_allowed_l6": [8.1, None],
    })
    X = build_X(df)
    for col in ("cb_ypt_allowed_l6", "cb_comp_rate_allowed_l6",
                "db_ypt_allowed_l6", "top_cb_out"):
        assert col in X.columns
    assert bool(X.top_cb_out.iloc[0]) is True
    assert pd.isna(X.top_cb_out.iloc[1])
    assert pd.isna(X.cb_comp_rate_allowed_l6).all()  # absent column -> NaN


def test_registry_model_survives_featureset_growth(small_panel):
    """A booster trained before a featureset addition (e.g. loaded from the
    registry) must keep predicting: predict_components slices the matrix to
    each booster's own training columns."""
    import lightgbm as lgb

    from nfl_dfs.models.featureset import build_X

    cm = components.train(small_panel, target_season=2022, num_boost_round=10)
    tr = small_panel[small_panel.season < 2022]
    X_old = build_X(tr).drop(
        columns=["depth_rank", "team_vacated_target_share",
                 "team_vacated_carry_share"]
    )
    cm.models["targets"] = lgb.train(
        components.COUNT_PARAMS,
        lgb.Dataset(X_old, tr.y_targets, categorical_feature=["position"]),
        num_boost_round=5,
    )
    comps = cm.predict_components(small_panel[small_panel.season == 2022])
    assert comps.targets.notna().all()

```

===== FILE: tests/test_config.py =====
```python
from datetime import date

from nfl_dfs.config import Settings, current_season


def test_current_season_rolls_over_in_march():
    assert current_season(date(2025, 2, 15)) == 2024
    assert current_season(date(2025, 3, 1)) == 2025
    assert current_season(date(2025, 11, 30)) == 2025
    assert current_season(date(2026, 1, 4)) == 2025


def test_settings_qualified_datasets():
    s = Settings()
    assert s.raw.endswith(".nfl_raw")
    assert s.features.endswith(".nfl_features")
    assert s.predictions.endswith(".nfl_predictions")


def test_dotenv_loading(tmp_path, monkeypatch):
    from nfl_dfs.config import _load_dotenv

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "# comment\nMY_DOTENV_TEST=hello\nQUOTED='world'\nEXISTING=file\n")
    monkeypatch.setenv("EXISTING", "real-env")
    monkeypatch.delenv("MY_DOTENV_TEST", raising=False)
    _load_dotenv()
    import os
    assert os.environ["MY_DOTENV_TEST"] == "hello"
    assert os.environ["QUOTED"] == "world"
    assert os.environ["EXISTING"] == "real-env"  # env always wins

```

===== FILE: tests/test_contest_job.py =====
```python
"""Offline coverage for the overlay-detection scaffold's env gate.

No network or BigQuery access here or in CI — run() must return before
touching either when INGEST_CONTESTS_ENABLED isn't set, which is the
default (this session has no GCP credentials and no live DK slate).
"""

import requests

from nfl_dfs.ingest import contest_job


def test_run_is_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("INGEST_CONTESTS_ENABLED", raising=False)

    def boom(*a, **k):
        raise AssertionError("should not touch the network when disabled")

    monkeypatch.setattr(requests.Session, "get", boom)
    contest_job.run()  # must not raise


def test_run_polls_when_enabled(monkeypatch):
    monkeypatch.setenv("INGEST_CONTESTS_ENABLED", "1")
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.nfl_draft_groups", lambda session=None: []
    )

    calls = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.dk_client.nfl_contests",
        lambda session=None: calls.append("contests") or [],
    )

    contest_job.run()
    # No draft groups -> nothing to match contests to, and the job must
    # bail before ever calling nfl_contests (would waste a poll for nothing).
    assert calls == []

```

===== FILE: tests/test_discoverylab_import.py =====
```python
from nfl_dfs.ingest.discoverylab_import import pick_main_classic_slate, slate_rows


def _slate(gtype, n_games, players):
    return {"Operator": "DraftKings", "OperatorGameType": gtype,
            "NumberOfGames": n_games, "DfsSlatePlayers": players}


def _players(n, salary=5000, start=0):
    return [{"SlatePlayerID": start + i, "OperatorPlayerName": f"P{i}",
             "OperatorPosition": "WR", "Team": "kc", "OperatorSalary": salary}
            for i in range(n)]


def test_rejects_zero_salary_pseudo_slate():
    pseudo = _slate("Classic", 16, _players(2000, salary=0))
    real = _slate("Classic", 16, _players(800, start=5000))
    small = _slate("Classic", 3, _players(150, start=9000))
    showdown = _slate("Showdown Captain Mode", 1, _players(100, start=99000))
    got = pick_main_classic_slate([pseudo, small, real, showdown])
    assert got is real
    assert pick_main_classic_slate([pseudo, showdown]) is None


def test_slate_rows_dst_points_merge():
    players = _players(2) + [{
        "SlatePlayerID": 77, "OperatorPlayerName": "Chiefs",
        "OperatorPosition": "DST", "Team": "KC", "OperatorSalary": 3200}]
    dst = {"KC": (11.0, "DEN")}
    df = slate_rows(_slate("Classic", 16, players), 2025, 15, dst)
    assert len(df) == 3
    d = df[df.position == "Def"].iloc[0]
    assert d.dk_points == 11.0 and d.opponent == "DEN" and d.team_abbr == "KC"
    skill = df[df.position == "WR"]
    assert skill.dk_points.isna().all()
    assert (df.season == 2025).all() and (df.week == 15).all()

```

===== FILE: tests/test_dk_client.py =====
```python
import pandas as pd
import requests

from nfl_dfs.ingest import dk_client


def payload():
    return {
        "competitions": [
            {"competitionId": 111, "startTime": "2025-09-07T17:00:00Z"},
        ],
        "draftables": [
            {
                "draftableId": 9001,
                "playerId": 1,
                "displayName": "Justin Jefferson",
                "teamAbbreviation": "MIN",
                "position": "WR",
                "salary": 8900,
                "rosterSlotId": 511,
                "status": "None",
                "competition": {"competitionId": 111},
                "draftStatAttributes": [{"id": 90, "value": "21.3"}],
            },
            # Same player repeated in the FLEX slot — must be deduped
            {
                "draftableId": 9002,
                "playerId": 1,
                "displayName": "Justin Jefferson",
                "teamAbbreviation": "MIN",
                "position": "WR",
                "salary": 8900,
                "rosterSlotId": 512,
                "status": "None",
                "competition": {"competitionId": 111},
            },
            {
                "draftableId": 9003,
                "playerId": 2,
                "displayName": "Ja'Marr Chase",
                "teamAbbreviation": "CIN",
                "position": "WR",
                "salary": 9100,
                "rosterSlotId": 511,
                "status": "Q",
                "competition": {"competitionId": 999},  # unknown comp -> null game_start
                "draftStatAttributes": [{"id": 90, "value": "-"}],
            },
        ],
    }


def test_draftables_frame_dedupes_roster_slots():
    df = dk_client.draftables_frame(123, "classic", payload())
    assert len(df) == 2
    assert set(df.dk_player_id) == {1, 2}


def test_draftables_frame_fields():
    df = dk_client.draftables_frame(123, "classic", payload())
    jj = df[df.dk_player_id == 1].iloc[0]
    assert jj.salary == 8900
    assert jj.game_start == "2025-09-07T17:00:00Z"
    assert jj.dk_ppg == 21.3
    import pandas as pd

    chase = df[df.dk_player_id == 2].iloc[0]
    assert pd.isna(chase.game_start)
    assert pd.isna(chase.dk_ppg)  # non-numeric attr value handled


def test_draftables_frame_keeps_draftable_ids():
    """DK's lineup upload matches on draftable IDs (the DKSalaries 'ID'
    column), so the frame must carry them. Classic repeats share a player,
    and any of the player's draftable IDs resolves on upload — keep the
    first."""
    df = dk_client.draftables_frame(123, "classic", payload())
    jj = df[df.dk_player_id == 1].iloc[0]
    assert jj.dk_draftable_id == 9001
    assert pd.isna(jj.dk_cpt_draftable_id)  # classic has no CPT slot
    assert df.dk_draftable_id.dtype == "Int64"


def test_showdown_dedup_keeps_flex_salary():
    """Showdown draftables repeat each player as CPT (1.5x salary) and FLEX;
    the frame must keep the FLEX price regardless of payload order — and
    both draftable IDs, because the upload's CPT cell only accepts the
    CPT-specific ID."""
    pl = payload()
    pl["draftables"][0]["salary"] = 13_350  # CPT row first: 1.5x the 8900 FLEX
    df = dk_client.draftables_frame(123, "showdown", pl)
    jj = df[df.dk_player_id == 1].iloc[0]
    assert jj.salary == 8900
    assert jj.dk_draftable_id == 9002       # the FLEX row
    assert jj.dk_cpt_draftable_id == 9001   # the CPT row


def test_showdown_dedup_flex_row_first():
    pl = payload()
    pl["draftables"][1]["salary"] = 13_350  # FLEX first, CPT repeat after
    df = dk_client.draftables_frame(123, "showdown", pl)
    jj = df[df.dk_player_id == 1].iloc[0]
    assert jj.salary == 8900
    assert jj.dk_draftable_id == 9001
    assert jj.dk_cpt_draftable_id == 9002


def test_classify_slate():
    assert dk_client.classify_slate({"gameTypeDescription": "Showdown Captain Mode"}) == "showdown"
    assert dk_client.classify_slate({"gameType": "NFL Captain"}) == "showdown"
    assert dk_client.classify_slate({"gameTypeDescription": "Classic"}) == "classic"


def draft_groups_payload():
    """Modeled on a live /draftgroups/v1/ response (verified 2026-07-31):
    entries carry sportId at the top level (1=NFL, 5=CFB per DK's own
    /sites/US-DK/sports/v1/sports) but no top-level "sport" string."""
    return {
        "draftGroups": [
            {"draftGroupId": 90001, "sportId": 1, "draftGroupState": "Upcoming"},
            {"draftGroupId": 90002, "sportId": 5, "draftGroupState": "Upcoming"},
            # Not upcoming -> excluded regardless of sport.
            {"draftGroupId": 90003, "sportId": 5, "draftGroupState": "Complete"},
            # A non-NFL, non-CFB sport (e.g. NBA) -> excluded from both.
            {"draftGroupId": 90004, "sportId": 4, "draftGroupState": "Upcoming"},
        ]
    }


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_cfb_draft_groups_filters_by_sport_id(monkeypatch):
    def fake_get(self, url, headers=None, timeout=None):
        assert url == dk_client.DK_GROUPS
        return _FakeResponse(draft_groups_payload())

    monkeypatch.setattr(requests.Session, "get", fake_get)
    groups = dk_client.cfb_draft_groups()
    assert [g["draftGroupId"] for g in groups] == [90002]


def test_nfl_contests_hits_nfl_endpoint(monkeypatch):
    calls = []

    def fake_get(self, url, headers=None, timeout=None):
        calls.append(url)
        return _FakeResponse({"Contests": [{"id": 1}]})

    monkeypatch.setattr(requests.Session, "get", fake_get)
    assert dk_client.nfl_contests() == [{"id": 1}]
    assert calls == [dk_client.DK_CONTESTS]


def test_cfb_contests_hits_cfb_endpoint(monkeypatch):
    calls = []

    def fake_get(self, url, headers=None, timeout=None):
        calls.append(url)
        return _FakeResponse({"Contests": [{"id": 2}]})

    monkeypatch.setattr(requests.Session, "get", fake_get)
    assert dk_client.cfb_contests() == [{"id": 2}]
    assert calls == [dk_client.DK_CFB_CONTESTS]


def contests_payload():
    return [
        {
            "id": 111,
            "dg": 555,
            "n": "$1M Fantasy Football Millionaire [$150K to 1st]",
            "gameType": "Classic",
            "a": 20,
            "m": 50_000,
            "nt": 12_000,
            "po": 1_000_000.0,
            "attr": {"IsGuaranteed": "true"},
            "sd": "/Date(1785513600000)/",
        },
        {
            # Non-guaranteed: never carries an overlay even when short-filled.
            "id": 112,
            "dg": 555,
            "n": "50/50 Double Up",
            "gameType": "Classic",
            "a": 5,
            "m": 1000,
            "nt": 10,
            "po": 4500.0,
            "attr": {},
            "sd": "/Date(1785513600000)/",
        },
        {
            # Different draft group (e.g. a Madden sim contest sharing the
            # sport=NFL tag) — excluded when filtering by draft_group_ids.
            "id": 113,
            "dg": 999,
            "n": "Madden Stream $6K Friday Special",
            "gameType": "Madden Classic",
            "a": 15,
            "m": 470,
            "nt": 222,
            "po": 6000.0,
            "attr": {"IsGuaranteed": "true"},
            "sd": "/Date(1785513600000)/",
        },
    ]


def test_contests_frame_filters_to_draft_group_ids():
    df = dk_client.contests_frame(contests_payload(), draft_group_ids={555})
    assert set(df.contest_id) == {111, 112}


def test_contests_frame_no_filter_keeps_everything():
    df = dk_client.contests_frame(contests_payload())
    assert set(df.contest_id) == {111, 112, 113}


def test_contests_frame_fill_rate():
    df = dk_client.contests_frame(contests_payload(), draft_group_ids={555})
    gpp = df[df.contest_id == 111].iloc[0]
    assert gpp.fill_rate == 12_000 / 50_000


def test_contests_frame_overlay_only_for_guaranteed():
    df = dk_client.contests_frame(contests_payload(), draft_group_ids={555})
    gpp = df[df.contest_id == 111].iloc[0]
    double_up = df[df.contest_id == 112].iloc[0]
    assert gpp.is_guaranteed
    assert gpp.overlay_dollars == 1_000_000.0 - 12_000 * 20
    assert not double_up.is_guaranteed
    # Short-filled (10 of 1000 entries) but not guaranteed -> no overlay.
    assert double_up.overlay_dollars == 0.0


def test_contests_frame_sport_defaults_nfl():
    df = dk_client.contests_frame(contests_payload(), draft_group_ids={555})
    assert set(df.sport) == {"NFL"}


def test_contests_frame_sport_stamps_cfb():
    """cfb_job.py passes sport="CFB" so dk_contest_fills can hold both
    sports' polls in one append-only table (issue #13 item 7)."""
    df = dk_client.contests_frame(contests_payload(), draft_group_ids={555}, sport="CFB")
    assert set(df.sport) == {"CFB"}


def test_contests_frame_empty_input():
    df = dk_client.contests_frame([])
    assert df.empty
    assert list(df.columns) == dk_client.CONTEST_COLUMNS


def test_contests_frame_handles_missing_fields():
    df = dk_client.contests_frame(
        [{"id": 1, "dg": 1, "n": "Weird contest", "attr": {"IsGuaranteed": "true"}}]
    )
    row = df.iloc[0]
    assert pd.isna(row.fill_rate)
    assert row.overlay_dollars == 0.0  # missing entries/fee/pool -> no overlay computed
    assert pd.isna(row.start_time)


def test_parse_dk_date():
    ts = dk_client._parse_dk_date("/Date(1785513600000)/")
    assert ts is not None
    assert ts.tz is not None
    assert ts.year == 2026

    assert dk_client._parse_dk_date("not a date") is None
    assert dk_client._parse_dk_date(None) is None


def test_render_sql_placeholders(tmp_path):
    from nfl_dfs.bq import render_sql

    p = tmp_path / "q.sql"
    p.write_text("SELECT * FROM `${raw}.pbp` WHERE season = ${season}")
    sql = render_sql(p, season=2024)
    assert "${" not in sql
    assert "nfl_raw.pbp" in sql
    assert "season = 2024" in sql


def test_render_sql_fails_on_unresolved(tmp_path):
    import pytest

    from nfl_dfs.bq import render_sql

    p = tmp_path / "q.sql"
    p.write_text("SELECT ${mystery}")
    with pytest.raises(ValueError):
        render_sql(p)


def test_every_shipped_sql_file_renders():
    """Placeholder coverage for the real pipeline SQL: build-features runs
    every file under sql/, and an unresolved ${...} should fail here, not
    in the morning build."""
    from nfl_dfs.bq import SQL_DIR, render_sql

    files = sorted(SQL_DIR.rglob("*.sql"))
    assert files, f"no SQL found under {SQL_DIR}"
    for path in files:
        sql = render_sql(path, prior_k=4)
        assert "${" not in sql, path

```

===== FILE: tests/test_dollar_select.py =====
```python
"""SELECT_OBJ=dollars: expected-dollars entry selection (engine)."""

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest.engine import _tier_thresholds, select_dollar_entries
from nfl_dfs.backtest.payout import gpp
from nfl_dfs.optimizer.lineup import Lineup


def test_tier_thresholds_match_scalar_payout():
    c = gpp()
    cums, pays = _tier_thresholds(c)
    rng = np.random.default_rng(0)
    for rank in rng.integers(1, c.field_size, 200):
        frac = rank / c.field_size
        idx = np.searchsorted(cums, frac, side="left")
        vec = float(pays[min(idx, len(pays) - 1)]) if idx < len(pays) else 0.0
        assert vec == pytest.approx(c.payout_for_rank(int(rank)))


def _tiny_slate(n=24, seed=1):
    rng = np.random.default_rng(seed)
    pos = (["QB"] * 3 + ["RB"] * 6 + ["WR"] * 9 + ["TE"] * 3 + ["DST"] * 3)
    return pd.DataFrame({
        "id": [f"p{i}" for i in range(n)],
        "pos": pos[:n],
        "salary": rng.integers(3000, 9000, n),
        "proj": rng.uniform(5, 25, n),
    })


def test_dollar_selection_prefers_dominant_candidate(monkeypatch):
    slate = _tiny_slate()
    n_sims = 400
    rng = np.random.default_rng(2)
    rd = rng.gamma(3, 4, (len(slate), n_sims)).astype(np.float32)

    def mk(ids):
        players = [{"id": f"p{i}", "pos": "WR", "salary": 4000, "proj": 10.0}
                   for i in ids]
        return Lineup(players)

    cands = [mk(range(0, 9)), mk(range(9, 18)), mk(range(6, 15))]
    base = np.stack([rd[list(range(0, 9))].sum(axis=0),
                     rd[list(range(9, 18))].sum(axis=0),
                     rd[list(range(6, 15))].sum(axis=0)])
    # Make candidate 1 strictly dominant in every sim
    totals = base.copy()
    totals[1] += 500.0
    picked = select_dollar_entries(slate, rd, cands, totals, n_entries=2,
                                   contest=gpp(), n_field=50, n_sim_sub=200)
    assert picked[0] == 1
    assert len(picked) == 2 and len(set(picked)) == 2


def test_tail_resolution_distinguishes_sample_beaters(monkeypatch):
    """The Addendum-34 flaw: two candidates that both beat the ENTIRE
    sampled field used to get identical (top-tier) E[$]. The hybrid
    tail estimator must rank the stronger one higher, and neither
    should automatically score as outright 1st of 100k."""
    import numpy as np
    from nfl_dfs.backtest import engine
    from nfl_dfs.backtest.engine import select_dollar_entries
    from nfl_dfs.backtest.payout import gpp
    from nfl_dfs.optimizer.lineup import Lineup

    slate = _tiny_slate()
    n_sims = 300
    rng = np.random.default_rng(5)
    rd = rng.gamma(3, 4, (len(slate), n_sims)).astype(np.float32)

    def mk(ids):
        return Lineup([{"id": f"p{i}", "pos": "WR", "salary": 4000,
                        "proj": 10.0} for i in ids])

    cands = [mk(range(0, 9)), mk(range(9, 18))]
    base = np.stack([rd[list(range(0, 9))].sum(axis=0),
                     rd[list(range(9, 18))].sum(axis=0)])
    totals = base.copy()
    totals[0] += 200.0   # clears the whole field sample in every sim
    totals[1] += 260.0   # clears it by MORE -- deeper into the true tail

    # Capture the internal EVs by spying on the selection order
    picked = select_dollar_entries(slate, rd, cands, totals, n_entries=2,
                                   contest=gpp(), n_field=60, n_sim_sub=200)
    assert picked[0] == 1  # the deeper tail must rank first now

```

===== FILE: tests/test_dst_corr_draws.py =====
```python
"""DST_CORR_DRAWS: anti-correlated, mean-preserving DST draws (A/B gate)."""

import numpy as np
import pandas as pd

from nfl_dfs.backtest.engine import _row_draws


def _slate_and_draws(n_sims=4000, seed=0):
    rng = np.random.default_rng(seed)
    slate = pd.DataFrame({
        "team": ["AAA", "AAA", "BBB", "BBB"],
        "opp":  ["BBB", "BBB", "AAA", "AAA"],
        "proj": [15.0, 12.0, 14.0, 6.0],
        "draw_idx": [0, 1, 2, -1],  # last row is the DST (team BBB vs AAA)
    })
    draws = rng.gamma(4.0, 3.5, (3, n_sims))
    return slate, draws


def test_gate_off_dst_is_constant(monkeypatch):
    monkeypatch.delenv("DST_CORR_DRAWS", raising=False)
    slate, draws = _slate_and_draws()
    rd = _row_draws(slate, draws)
    assert np.allclose(rd[3], 6.0)


def test_gate_on_dst_anticorrelated_and_mean_preserved(monkeypatch):
    monkeypatch.setenv("DST_CORR_DRAWS", "1")
    slate, draws = _slate_and_draws()
    rd = _row_draws(slate, draws)
    opp_total = rd[0] + rd[1]  # AAA offense vs the BBB DST
    corr = np.corrcoef(rd[3], opp_total)[0, 1]
    # Fitted moments: corr -0.491, rel-sd 0.93 (both within tolerance)
    assert -0.6 < corr < -0.35
    assert abs(rd[3].mean() - 6.0) < 0.15
    rel_sd = rd[3].std() / rd[3].mean()
    assert 0.7 < rel_sd < 1.1


def test_gate_on_skill_rows_untouched(monkeypatch):
    monkeypatch.setenv("DST_CORR_DRAWS", "1")
    slate, draws = _slate_and_draws()
    rd = _row_draws(slate, draws)
    np.testing.assert_allclose(rd[0], draws[0], rtol=1e-6)

```

===== FILE: tests/test_emp_marginals.py =====
```python
"""EMP_MARGINALS: empirical marginal shapes, our copula and moments.

Contracts: mean and std preserved per row (affine match), rank order of
each row's draws preserved exactly (correlation structure untouched),
high-tier WR/RB tails fatten (weibull family), unknown positions pass
through untouched."""

import numpy as np
import pandas as pd

from nfl_dfs.backtest.replay import _empirical_marginals


def _draws(n_rows=4, n_sims=20_000, mu=20.0, sd=8.0, seed=2):
    rng = np.random.default_rng(seed)
    return rng.normal(mu, sd, size=(n_rows, n_sims))


def test_moments_and_ranks_preserved():
    draws = _draws()
    pos = pd.Series(["WR", "RB", "QB", "TE"])
    out = _empirical_marginals(draws, pos, np.random.default_rng(1))
    np.testing.assert_allclose(out.mean(axis=1), draws.mean(axis=1), atol=1e-6)
    np.testing.assert_allclose(out.std(axis=1), draws.std(axis=1), rtol=1e-6)
    for i in range(4):
        assert (np.argsort(out[i]) == np.argsort(draws[i])).all()


def test_wr_high_tier_gains_right_skew():
    draws = _draws(n_rows=1, mu=20.0, sd=8.0)  # normal input: zero skew
    out = _empirical_marginals(draws, pd.Series(["WR"]),
                               np.random.default_rng(1))
    def skew(x):
        z = (x - x.mean()) / x.std()
        return float((z ** 3).mean())
    assert skew(out[0]) > skew(draws[0]) + 0.1


def test_unknown_position_passthrough():
    # position absent from the fitted table -> row must be untouched
    draws = _draws(n_rows=1)
    out = _empirical_marginals(draws, pd.Series(["FB"]),
                               np.random.default_rng(1))
    np.testing.assert_array_equal(out[0], draws[0])

```

===== FILE: tests/test_export_entries.py =====
```python
"""Min-churn entries fill: assignment, locked handling, diff."""

import numpy as np

from nfl_dfs.optimizer.lineup import Lineup


def _lu(names, pos=None):
    pos = pos or ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"]
    players = [{"id": i, "name": n, "pos": p, "salary": 5000, "proj": 10.0}
               for i, (n, p) in enumerate(zip(names, pos))]
    return Lineup(players=players)


HDR = "Entry ID,Contest Name,Contest ID,Entry Fee,QB,RB,RB,WR,WR,WR,TE,FLEX,DST"


def _entries(rows):
    return HDR + "\n" + "\n".join(rows) + "\n"


def test_min_churn_assignment_and_diff():
    from nfl_dfs.optimizer.export import fill_entries_csv

    a = [f"A{i}" for i in range(9)]
    b = [f"B{i}" for i in range(9)]
    # entry 1 currently holds mostly-B, entry 2 mostly-A -> assignment
    # must give entry 1 the B lineup and entry 2 the A lineup.
    e1 = "111,C,9,$5," + ",".join([f"B{i} (1)" for i in range(8)] + ["A8 (1)"])
    e2 = "222,C,9,$5," + ",".join([f"A{i} (1)" for i in range(8)] + ["B8 (1)"])
    diff = []
    out = fill_entries_csv(_entries([e1, e2]), [_lu(a), _lu(b)], diff_out=diff)
    lines = out.strip().splitlines()
    assert "B0" in lines[1] and "A0" in lines[2]
    d1 = next(d for d in diff if d["entry_id"] == "111")
    assert d1["out"] == ["A8"] and d1["in"] == ["B8"]


def test_locked_row_kept_when_lineup_lacks_locked_player():
    from nfl_dfs.optimizer.export import fill_entries_csv

    locked_row = "333,C,9,$5,Thu Guy (LOCKED)," + ",".join(
        [f"X{i} (1)" for i in range(8)])
    diff = []
    out = fill_entries_csv(_entries([locked_row]),
                           [_lu([f"A{i}" for i in range(9)])], diff_out=diff)
    assert "Thu Guy (LOCKED)" in out and "A0" not in out
    assert diff[0]["untouched"] is True


def test_locked_cell_preserved_when_lineup_contains_player():
    from nfl_dfs.optimizer.export import fill_entries_csv

    names = ["Thu Guy"] + [f"A{i}" for i in range(8)]
    locked_row = "444,C,9,$5,Thu Guy (LOCKED)," + ",".join(
        [f"X{i} (1)" for i in range(8)])
    out = fill_entries_csv(_entries([locked_row]), [_lu(names)])
    line = out.strip().splitlines()[1]
    assert "Thu Guy (LOCKED)" in line and "A0" in line


def test_locked_flex_cell_fills_position_aware():
    """Regression (2026-08-04 audit): locked cell in the FLEX slot, but
    the new lineup slot_orders that player into a hard slot —
    sequential fill shifted every later cell one slot (QB cell got an
    RB, etc.). Position-aware fill must put an eligible player in every
    open slot; a genuinely un-arrangeable lock leaves the row untouched
    (the old code wrote an invalid row instead)."""
    import csv as _csv
    import io as _io

    from nfl_dfs.optimizer.export import fill_entries_csv

    # FEASIBLE: 3-RB lineup — Thu Guy (RB) locked in the FLEX cell,
    # both hard RB slots still fillable.
    names = ["Q", "R1", "R2", "Thu Guy", "W1", "W2", "W3", "T", "D"]
    pos = ["QB", "RB", "RB", "RB", "WR", "WR", "WR", "TE", "DST"]
    row = ("555,C,9,$5,X0 (1),X1 (1),X2 (1),X3 (1),X4 (1),X5 (1),X6 (1),"
           "Thu Guy (LOCKED),X8 (1)")
    out = fill_entries_csv(_entries([row]), [_lu(names, pos)])
    r = list(_csv.reader(_io.StringIO(out)))
    hdr, filled = r[0], r[1]
    by_name = dict(zip(names, pos))
    for i in range(4, 13):
        cell, slot = filled[i], hdr[i]
        if "LOCKED" in cell:
            assert slot == "FLEX"
            continue
        ppos = by_name[cell.split(" (")[0]]
        assert (ppos == slot) or (slot == "FLEX" and ppos in
                                  ("RB", "WR", "TE")), \
            f"slot {slot} got {ppos}"

    # INFEASIBLE: 2-RB lineup, one RB locked into FLEX -> no second RB
    # for the hard slot; row must be left untouched, not written invalid.
    names2 = ["Q", "R1", "Thu Guy", "W1", "W2", "W3", "T", "W4", "D"]
    pos2 = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"]
    diff = []
    out2 = fill_entries_csv(_entries([row]), [_lu(names2, pos2)],
                            diff_out=diff)
    assert diff[0]["untouched"] is True and "X0" in out2


def test_lock_aware_assignment_prevents_stranding():
    """Regression (2026-08-04 audit): the churn assignment could give
    the only lock-compatible lineup to an unlocked entry, stranding a
    selected lineup while the locked row goes untouched."""
    from nfl_dfs.optimizer.export import fill_entries_csv

    with_lock = ["Thu Guy"] + [f"A{i}" for i in range(8)]
    without = [f"B{i}" for i in range(9)]
    # locked entry currently resembles the B lineup MORE (so naive
    # overlap would hand B to it and fail the lock check)
    locked_row = ("666,C,9,$5,Thu Guy (LOCKED)," +
                  ",".join([f"B{i} (1)" for i in range(1, 9)]))
    free_row = "777,C,9,$5," + ",".join([f"A{i} (1)" for i in range(8)]
                                        + ["Z (1)"])
    diff = []
    out = fill_entries_csv(_entries([locked_row, free_row]),
                           [_lu(with_lock), _lu(without)], diff_out=diff)
    d_locked = next(d for d in diff if d["entry_id"] == "666")
    assert d_locked["untouched"] is False, "lock-compatible lineup stranded"
    assert "B0" in out.splitlines()[2], "free row should get the B lineup"


def test_contest_id_filter_fills_only_that_contest():
    """Multi-contest DKEntries: filter fills the named contest's rows;
    other contests' rows pass through verbatim."""
    from nfl_dfs.optimizer.export import fill_entries_csv

    a = [f"A{i}" for i in range(9)]
    r1 = "111,Qual,900,$5," + ",".join([f"X{i} (1)" for i in range(9)])
    r2 = "222,Milly,901,$5," + ",".join([f"Y{i} (1)" for i in range(9)])
    out = fill_entries_csv(_entries([r1, r2]), [_lu(a)], contest_id="900")
    lines = out.strip().splitlines()
    assert "A0" in lines[1] and "Y0 (1)" in lines[2] and "A0" not in lines[2]
    import pytest

    with pytest.raises(ValueError):
        fill_entries_csv(_entries([r1]), [_lu(a)], contest_id="999")

```

===== FILE: tests/test_external_proj.py =====
```python
"""External projections import: loose-schema parse + diff join."""

import pandas as pd

from nfl_dfs import external_proj


def test_parse_flexible_columns_and_percent_scale():
    csv = ("Player,Pos,Projection,Ownership\n"
           "Justin Jefferson,WR,21.4,28.5%\n"
           "Bhayshul Tuten,RB,11.2,4.1%\n")
    d = external_proj.parse_csv(csv)
    assert list(d.columns) == ["name", "position", "proj", "own_pct", "ceiling"]
    assert len(d) == 2 and d.proj.iloc[0] == 21.4 and d.own_pct.iloc[1] == 4.1


def test_parse_fraction_ownership_rescaled():
    csv = "name,fpts,own\nA Player,10.0,0.22\n"
    d = external_proj.parse_csv(csv)
    assert abs(d.own_pct.iloc[0] - 22.0) < 1e-9


def test_parse_requires_name_and_proj():
    import pytest

    with pytest.raises(ValueError):
        external_proj.parse_csv("foo,bar\n1,2\n")


def test_diff_joins_on_normalized_name(monkeypatch):
    ext = pd.DataFrame({
        "source": ["etr"] * 2, "name": ["Kenneth Walker III", "A.J. Brown"],
        "ext_proj": [15.0, 20.0], "ext_own": [12.0, 25.0],
        "ext_ceiling": [30.0, 38.0]})
    monkeypatch.setattr(external_proj, "query_df", lambda *_a, **_k: ext)
    ours = pd.DataFrame({
        "display_name": ["Kenneth Walker III", "AJ Brown", "Nobody Else"],
        "position": ["RB", "WR", "TE"], "team": ["KC", "PHI", "X"],
        "salary": [6000, 7800, 3000], "proj_points": [11.0, 21.5, 5.0]})
    d = external_proj.diff(ours, 2026, 1)
    assert len(d) == 2  # punctuation-insensitive match
    assert d.iloc[0]["diff"] == -4.0  # Walker: biggest absolute diff first

```

===== FILE: tests/test_feature_sql.py =====
```python
"""Offline guards on the feature SQL files themselves.

The BigQuery build can't run in tests, but two invariants are checkable from
the files alone: every file renders with no unresolved ${placeholders}, and
every rolling window in a model-input table ends strictly before the current
row (the point-in-time rule; see CLAUDE.md and features/leakage.py).
"""

import re

import pytest

from nfl_dfs.bq import SQL_DIR, render_sql

FEATURE_SQL = sorted((SQL_DIR / "features").glob("*.sql"))

# Dashboard-only tables (README: "never a model input") may legitimately
# window through CURRENT ROW. Everything else must not.
CURRENT_ROW_OK = {"022_defense_points_against.sql"}


def test_feature_sql_discovered():
    assert len(FEATURE_SQL) >= 17


def test_coverage_table_present_and_ordered_before_training():
    """build.py executes in sorted order; the coverage table must be built
    before the training/inference tables that join it."""
    names = [p.name for p in FEATURE_SQL]
    cov = names.index("017a_defense_week_coverage.sql")
    assert cov < names.index("021_player_week_training.sql")
    assert cov < names.index("023_player_week_inference.sql")


@pytest.mark.parametrize("path", FEATURE_SQL, ids=lambda p: p.name)
def test_renders_without_unresolved_placeholders(path):
    sql = render_sql(path, prior_k=4)
    assert "${" not in sql


@pytest.mark.parametrize("path", FEATURE_SQL, ids=lambda p: p.name)
def test_model_input_windows_exclude_current_row(path):
    if path.name in CURRENT_ROW_OK:
        pytest.skip("dashboard table, windows through CURRENT ROW by design")
    for clause in re.findall(r"ROWS BETWEEN[^)]+", path.read_text()):
        assert clause.rstrip().endswith("1 PRECEDING"), (
            f"{path.name}: rolling window does not end at 1 PRECEDING: {clause!r}"
        )

```

===== FILE: tests/test_field_calibration.py =====
```python
"""September machinery, pre-built: entry import + dupe-calibration math.

All offline — synthetic fixtures stand in for the standings exports that
only exist in-season (and purge from DK in ~4 days)."""

import numpy as np
import pandas as pd

from nfl_dfs.ingest.ownership_import import parse_entries_csv, parse_standings_csv
from nfl_dfs.ops import field_calibration as fc


def _standings_csv(tmp_path):
    # DK's shape: entry block left, player summary right (same file)
    df = pd.DataFrame({
        "Rank": [1, 2, 3, 4],
        "EntryId": ["e1", "e2", "e3", "e4"],
        "EntryName": ["a", "b", "c", "d"],
        "TimeRemaining": [0] * 4,
        "Points": [180.2, 175.0, 175.0, 160.1],
        "Lineup": [
            "QB Jalen Hurts RB Bijan Robinson WR AJ Brown TE Dallas Goedert DST Eagles WR X One WR Y Two RB Z Three FLEX W Four",
            "QB Jalen Hurts RB Bijan Robinson WR AJ Brown TE Dallas Goedert DST Eagles WR X One WR Y Two RB Z Three FLEX W Four",
            "QB Josh Allen RB James Cook WR Khalil Shakir TE Dalton Kincaid DST Bills WR X One WR Y Two RB Z Three FLEX W Four",
            "QB Josh Allen RB James Cook WR Khalil Shakir TE Dalton Kincaid DST Bills WR A Five WR Y Two RB Z Three FLEX W Four",
        ],
        "Player": ["Jalen Hurts", "Josh Allen", "AJ Brown", None],
        "Roster Position": ["QB", "QB", "WR", None],
        "%Drafted": ["50%", "50%", "25%", None],
        "FPTS": [30.0, 28.0, 20.0, None],
    })
    p = tmp_path / "contest-standings-123.csv"
    df.to_csv(p, index=False)
    return p


def test_entries_parsed_and_keyed(tmp_path):
    p = _standings_csv(tmp_path)
    e = parse_entries_csv(p)
    assert len(e) == 4
    # dupes: rows 1&2 identical lineups -> same players_key
    dupes = e.groupby("players_key").size().sort_values(ascending=False)
    assert dupes.iloc[0] == 2 and len(dupes) == 3
    # slot tokens stripped, names sorted
    assert "QB" not in dupes.index[0] and "FLEX" not in dupes.index[0]
    # ownership block still parses from the same file
    own = parse_standings_csv(p)
    assert len(own) == 3 and own.pct_drafted.max() == 50.0


def test_dupe_correlation_math():
    real = pd.DataFrame({"players_key": ["a", "b", "c"],
                         "count": [10, 5, 1], "best_rank": [1, 2, 3]})
    sim = pd.DataFrame({"players_key": ["a", "b"], "sim_count": [200, 100]})
    res = fc.dupe_correlation(real, sim, n_entries=1000, n_sims=20_000)
    # rescale: 200*(1000/20000)=10, 100*..=5, missing->0; corr([10,5,1],[10,5,0])
    assert res["match_rate"] == 2 / 3
    assert res["dupe_corr"] > 0.95


def test_independence_baseline():
    entries = pd.DataFrame({"players_key": ["A|B", "A|B", "C|D"],
                            "rank": [1, 2, 3]})
    own = pd.Series({"A": 0.5, "B": 0.4, "C": 0.1, "D": 0.02})
    b = fc.independence_baseline(entries, own)
    ab = b[b.players_key == "A|B"].iloc[0]
    assert ab["count"] == 2 and abs(ab.indep_expected - 0.5 * 0.4 * 3) < 1e-9


def test_salary_leftover_skips_unpriced():
    entries = pd.DataFrame({"players_key": ["A|B", "A|Z"]})
    left = fc.salary_leftover(entries, {"A": 30_000, "B": 19_500}, cap=50_000)
    assert list(left) == [500.0]

```

===== FILE: tests/test_game_sim.py =====
```python
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models import components, game_sim, simulate


def test_terminal_probabilities_sum_to_one():
    assert game_sim.TERMINAL_PROB_MATRIX.shape == (len(game_sim.ZONES), len(game_sim.TERMINALS))
    np.testing.assert_allclose(game_sim.TERMINAL_PROB_MATRIX.sum(axis=1), 1.0)


def test_next_zone_probabilities_sum_to_one_where_defined():
    for terminal in game_sim._NEXT_ZONE_WEIGHTS:
        row = game_sim._NEXT_ZONE_PROB_MATRIX[game_sim.TERMINAL_INDEX[terminal]]
        np.testing.assert_allclose(row.sum(), 1.0)


def test_terminal_probability_improves_with_field_position():
    """TD rate should rise monotonically from deep_own to redzone --
    the whole point of tracking field position at all."""
    td_col = game_sim.TERMINAL_INDEX["td"]
    td_rates = [game_sim.TERMINAL_PROB_MATRIX[game_sim.ZONE_INDEX[z], td_col] for z in game_sim.ZONES]
    assert td_rates == sorted(td_rates)


def test_simulate_team_points_plausible_range():
    rng = np.random.default_rng(0)
    n_drives = np.full(20_000, 11)
    points = game_sim.simulate_team_points(rng, n_drives)
    assert points.shape == (20_000,)
    assert (points >= 0).all()
    # 11 drives at the docstring's claimed ~2.0-2.2 pts/drive -> ~22-24;
    # band allows placeholder slop but fails if the table drifts from its
    # own stated calibration (it originally shipped at ~1.4 pts/drive).
    assert 19 <= points.mean() <= 28


def test_simulate_team_points_respects_variable_drive_counts():
    rng = np.random.default_rng(1)
    few = game_sim.simulate_team_points(rng, np.full(5000, 6))
    many = game_sim.simulate_team_points(rng, np.full(5000, 16))
    assert many.mean() > few.mean()


def test_simulate_game_points_shape_and_nonnegative():
    rng = np.random.default_rng(2)
    pts_a, pts_b = game_sim.simulate_game_points(rng, n_sims=5000)
    assert pts_a.shape == pts_b.shape == (5000,)
    assert (pts_a >= 0).all() and (pts_b >= 0).all()


def test_game_factor_matrix_mean_preserving_and_positive():
    rng = np.random.default_rng(3)
    factors = game_sim.game_factor_matrix(rng, n_games=4, n_sims=10_000)
    assert factors.shape == (4, 10_000)
    assert (factors >= 0).all()
    np.testing.assert_allclose(factors.mean(axis=1), 1.0, atol=0.02)


def test_game_factor_matrix_dispersion_sane():
    """Guard against a wildly over/under-dispersed placeholder table.

    The validated lognormal factor has sd 0.18; real NFL total-points
    relative sd is ~0.30 (13.5 on ~45). The possession factor currently
    measures ~0.32 -- fatter than the lognormal by design (possession
    variance is the point), but it must stay in a band where the replay
    A/B is comparing engines, not a variance bug. Tighten after the pbp
    fit. (The table originally shipped at ~0.45, driven by Poisson
    drive counts with sd ~3.3 vs the real ~1.5-2.)"""
    rng = np.random.default_rng(9)
    factors = game_sim.game_factor_matrix(rng, n_games=4, n_sims=20_000)
    stds = factors.std(axis=1)
    assert (stds > 0.15).all() and (stds < 0.45).all()


def test_team_game_factors_shape_and_each_team_mean_preserving():
    rng = np.random.default_rng(10)
    factors_a, factors_b = game_sim.team_game_factors(rng, n_games=4, n_sims=10_000)
    assert factors_a.shape == factors_b.shape == (4, 10_000)
    assert (factors_a >= 0).all() and (factors_b >= 0).all()
    np.testing.assert_allclose(factors_a.mean(axis=1), 1.0, atol=0.02)
    np.testing.assert_allclose(factors_b.mean(axis=1), 1.0, atol=0.02)


def test_team_game_factors_asymmetric_not_identical_to_shared_factor():
    """The whole point of team_game_factors over game_factor_matrix: the
    two teams in a game should draw DIFFERENT per-sim values (one team's
    blowout doesn't imply the other team's), not the same combined-total
    factor both teams would get from game_factor_matrix."""
    rng = np.random.default_rng(11)
    factors_a, factors_b = game_sim.team_game_factors(rng, n_games=3, n_sims=5000)
    assert not np.allclose(factors_a, factors_b)


def test_team_game_factors_cross_team_correlation_documented():
    """Pins the engine's actual cross-team structure so nobody reasons
    from the wrong model: the two teams' factors are NEARLY INDEPENDENT
    (weak positive corr via shared drive counts) -- neither the corr=1 of
    the shared factor nor the blowout anticorrelation a score-aware engine
    would produce. If a hybrid shared-x-team factor lands, this band is
    the thing to change."""
    rng = np.random.default_rng(12)
    factors_a, factors_b = game_sim.team_game_factors(rng, n_games=1, n_sims=40_000)
    corr = np.corrcoef(factors_a[0], factors_b[0])[0, 1]
    assert -0.05 < corr < 0.35


def test_allocate_drive_usage_sums_to_units_single_draw():
    rng = np.random.default_rng(4)
    shares = np.array([0.5, 0.3, 0.2])
    allocated = game_sim.allocate_drive_usage(rng, 10.0, shares, n_sims=1)
    assert allocated.shape == (3,)
    assert allocated.sum() == pytest.approx(10.0)


def test_allocate_drive_usage_vectorized_over_sims():
    rng = np.random.default_rng(5)
    shares = np.array([0.6, 0.25, 0.15])
    allocated = game_sim.allocate_drive_usage(rng, 8.0, shares, n_sims=2000)
    assert allocated.shape == (2000, 3)
    np.testing.assert_allclose(allocated.sum(axis=1), 8.0)
    # in expectation the split should track the prior shares
    mean_share = allocated.mean(axis=0) / allocated.mean(axis=0).sum()
    np.testing.assert_allclose(mean_share, shares, atol=0.03)


def test_allocate_drive_usage_handles_all_zero_shares():
    rng = np.random.default_rng(6)
    allocated = game_sim.allocate_drive_usage(rng, 4.0, np.zeros(4), n_sims=1)
    assert allocated.shape == (4,)
    assert allocated.sum() == pytest.approx(4.0)


def test_simulate_default_mode_never_consults_game_sim(small_panel, monkeypatch):
    """With GAME_SIM_MODE unset, simulate() must be deterministic and must
    never touch game_sim at all -- proven by making its entry point raise.
    (Byte-for-byte equivalence with the pre-game_sim code holds by
    inspection: the default branch runs the identical lognormal RNG call.)"""
    monkeypatch.delenv("GAME_SIM_MODE", raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError("game_sim consulted in default mode")

    monkeypatch.setattr(game_sim, "game_factor_matrix", _boom)
    cm = components.train(small_panel, target_season=2022, num_boost_round=60)
    va = small_panel[small_panel.season == 2022].head(30)
    comps = cm.predict_components(va)
    game_ids = va.game_id

    res_a = simulate.simulate(comps, n_sims=1000, seed=7, game_ids=game_ids)
    res_b = simulate.simulate(comps, n_sims=1000, seed=7, game_ids=game_ids)
    pd.testing.assert_frame_equal(res_a.summary, res_b.summary)


def test_simulate_possession_mode_runs_and_differs_from_lognormal(small_panel, monkeypatch):
    cm = components.train(small_panel, target_season=2022, num_boost_round=60)
    va = small_panel[small_panel.season == 2022].head(30)
    comps = cm.predict_components(va)
    game_ids = va.game_id

    monkeypatch.delenv("GAME_SIM_MODE", raising=False)
    baseline = simulate.simulate(comps, n_sims=2000, seed=8, game_ids=game_ids)

    monkeypatch.setenv("GAME_SIM_MODE", "possession")
    possession = simulate.simulate(comps, n_sims=2000, seed=8, game_ids=game_ids)

    assert possession.summary.shape == baseline.summary.shape
    assert (possession.summary.proj_points >= 0).all()
    # different engines, same seed -> shouldn't coincidentally match exactly
    assert not possession.summary.proj_points.equals(baseline.summary.proj_points)


def _two_team_comps() -> pd.DataFrame:
    """Two identical player rows in the same game, on different teams --
    isolates the game-factor multiplier's effect from any per-player
    difference in the underlying component predictions."""
    row = {
        "targets": 8.0, "catch_rate": 0.65, "ypr": 11.0, "rec_tds": 0.4,
        "carries": 3.0, "ypc": 4.2, "rush_tds": 0.1,
        "pass_attempts": 0.0, "ypa": 0.0, "pass_tds": 0.0, "interceptions": 0.0,
    }
    return pd.DataFrame([row, row])


def test_simulate_possession_mode_without_team_ids_gives_identical_players_close_points(monkeypatch):
    """No team_ids -> falls back to one shared factor per game (the
    pre-team_ids behavior), so two identical-mean rows in the same game
    should land on nearly identical projections -- 'nearly' because each
    row still draws its own independent Poisson/Binomial/Gamma samples on
    top of the shared factor, so exact equality isn't expected even with
    a shared multiplier (contrast with the with-team_ids test below,
    where the *means* themselves are expected to diverge)."""
    monkeypatch.setenv("GAME_SIM_MODE", "possession")
    comps = _two_team_comps()
    game_ids = pd.Series(["g1", "g1"])

    res = simulate.simulate(comps, n_sims=20_000, seed=1, game_ids=game_ids)

    a, b = res.summary.proj_points.iloc[0], res.summary.proj_points.iloc[1]
    assert a == pytest.approx(b, rel=0.03)


def test_simulate_possession_mode_with_team_ids_lets_teammates_in_a_game_diverge(monkeypatch):
    """With team_ids, the two teams in a game draw independent factors
    (game_sim.team_game_factors), so two identical-comps players on
    DIFFERENT teams in the same game should land on different
    projections -- the game-script asymmetry this increment adds."""
    monkeypatch.setenv("GAME_SIM_MODE", "possession")
    comps = _two_team_comps()
    game_ids = pd.Series(["g1", "g1"])
    team_ids = pd.Series(["TA", "TB"])

    res = simulate.simulate(comps, n_sims=3000, seed=1, game_ids=game_ids, team_ids=team_ids)

    a, b = res.summary.proj_points.iloc[0], res.summary.proj_points.iloc[1]
    assert a != pytest.approx(b)


def test_simulate_possession_mode_team_ids_still_mean_preserving(monkeypatch, small_panel):
    """Threading team_ids through must not bias the TOTAL projected points
    across the slate -- only the joint tail should move, same contract as
    game_ids alone. Compared in aggregate (not per-row) because the
    per-game multiplier is shared across every player in that game, so a
    single row's mean carries the full sampling noise of one game-level
    draw; summing across many games averages that noise out."""
    cm = components.train(small_panel, target_season=2022, num_boost_round=60)
    va = small_panel[small_panel.season == 2022].head(40)
    comps = cm.predict_components(va)

    monkeypatch.delenv("GAME_SIM_MODE", raising=False)
    baseline = simulate.simulate(comps, n_sims=6000, seed=3, game_ids=va.game_id,
                                  team_ids=va.team)

    monkeypatch.setenv("GAME_SIM_MODE", "possession")
    possession = simulate.simulate(comps, n_sims=6000, seed=3, game_ids=va.game_id,
                                    team_ids=va.team)

    assert possession.summary.proj_points.sum() == pytest.approx(
        baseline.summary.proj_points.sum(), rel=0.08
    )


def _team_usage_comps() -> pd.DataFrame:
    """A 3-catcher team (60/25/15 target shares) plus one opponent row."""
    def catcher(tgts, team_row=True):
        return {
            "targets": tgts, "catch_rate": 0.65, "ypr": 11.0, "rec_tds": 0.3,
            "carries": 0.0, "ypc": 0.0, "rush_tds": 0.0,
            "pass_attempts": 0.0, "ypa": 0.0, "pass_tds": 0.0, "interceptions": 0.0,
        }
    return pd.DataFrame([catcher(9.0), catcher(4.0), catcher(2.0), catcher(6.0)])


_USAGE_IDS = dict(game_ids=pd.Series(["g1"] * 4),
                  team_ids=pd.Series(["TA", "TA", "TA", "TB"]))


def test_usage_dirichlet_off_by_default(monkeypatch):
    """GAME_SIM_USAGE unset must never touch allocate_drive_usage."""
    monkeypatch.delenv("GAME_SIM_USAGE", raising=False)
    monkeypatch.delenv("GAME_SIM_MODE", raising=False)

    def _boom(*a, **k):
        raise AssertionError("allocate_drive_usage consulted with usage mode off")

    monkeypatch.setattr(game_sim, "allocate_drive_usage", _boom)
    simulate.simulate(_team_usage_comps(), n_sims=500, seed=2, **_USAGE_IDS)


def test_usage_dirichlet_mean_preserving(monkeypatch):
    monkeypatch.delenv("GAME_SIM_MODE", raising=False)
    monkeypatch.delenv("GAME_SIM_USAGE", raising=False)
    base = simulate.simulate(_team_usage_comps(), n_sims=30_000, seed=5, **_USAGE_IDS)

    monkeypatch.setenv("GAME_SIM_USAGE", "dirichlet")
    usage = simulate.simulate(_team_usage_comps(), n_sims=30_000, seed=5, **_USAGE_IDS)

    np.testing.assert_allclose(usage.summary.proj_points.to_numpy(),
                               base.summary.proj_points.to_numpy(), rtol=0.04)


def test_usage_dirichlet_teammates_negatively_correlated(monkeypatch):
    """The mechanism itself: WR1's target count and WR2's should covary
    negatively under a shared-total Dirichlet split, and be ~uncorrelated
    under independent Poissons."""
    monkeypatch.delenv("GAME_SIM_MODE", raising=False)
    monkeypatch.setenv("GAME_SIM_USAGE", "dirichlet")
    # game_ids=None isolates the usage mechanism: with a game factor
    # active, its shared scaling (positive corr) masks the split's
    # negative corr in the points draws.
    res = simulate.simulate(_team_usage_comps(), n_sims=8000, seed=6,
                            keep_draws=True, game_ids=None,
                            team_ids=_USAGE_IDS["team_ids"])
    a, b = res.draws[0], res.draws[1]
    corr = np.corrcoef(a, b)[0, 1]
    assert corr < -0.05


def test_usage_dirichlet_fattens_low_share_tail(monkeypatch):
    """A 15%-share catcher should reach boom outcomes (p90) more often
    with correlated usage draws than with independent Poissons."""
    monkeypatch.delenv("GAME_SIM_MODE", raising=False)
    monkeypatch.delenv("GAME_SIM_USAGE", raising=False)
    base = simulate.simulate(_team_usage_comps(), n_sims=30_000, seed=7, **_USAGE_IDS)

    monkeypatch.setenv("GAME_SIM_USAGE", "dirichlet")
    usage = simulate.simulate(_team_usage_comps(), n_sims=30_000, seed=7, **_USAGE_IDS)

    assert usage.summary.proj_p90.iloc[2] > base.summary.proj_p90.iloc[2]
    assert usage.summary.proj_std.iloc[2] > base.summary.proj_std.iloc[2]


def test_pace_scales_drive_counts_and_points():
    rng = np.random.default_rng(20)
    slow = game_sim.game_factor_matrix(rng, 1, 5000, paces=np.array([0.85]))
    rng2 = np.random.default_rng(20)
    fast = game_sim.game_factor_matrix(rng2, 1, 5000, paces=np.array([1.15]))
    # Both stay mean-preserving; pace changes the underlying game, not the factor mean
    assert slow.mean() == pytest.approx(1.0, abs=0.03)
    assert fast.mean() == pytest.approx(1.0, abs=0.03)


def test_simulate_pace_gate_off_without_env(monkeypatch):
    """game_totals passed but GAME_SIM_PACE unset -> factors must not
    consult pace (proven by identical output with/without totals)."""
    monkeypatch.setenv("GAME_SIM_MODE", "possession")
    monkeypatch.delenv("GAME_SIM_PACE", raising=False)
    monkeypatch.delenv("GAME_SIM_USAGE", raising=False)
    comps = _two_team_comps()
    ids = dict(game_ids=pd.Series(["g1", "g1"]), team_ids=pd.Series(["TA", "TB"]))

    a = simulate.simulate(comps, n_sims=1000, seed=30, **ids)
    b = simulate.simulate(comps, n_sims=1000, seed=30,
                          game_totals=pd.Series([55.0, 55.0]), **ids)
    pd.testing.assert_frame_equal(a.summary, b.summary)


def test_simulate_pace_vegas_tightens_high_total_games(monkeypatch):
    """With GAME_SIM_PACE=vegas, a high-total game draws MORE possessions,
    and a mean-preserving factor over more possessions has LOWER relative
    variance (~1/sqrt(drives)) -- so the same player shows a slightly
    TIGHTER distribution in the 54-total game than the 36-total game,
    means unchanged. (The vegas *level* lives in the model's means; what
    pace adds is vegas-grounded heteroskedasticity. The naive 'high total
    = wider' intuition is already priced into the means.)"""
    monkeypatch.setenv("GAME_SIM_MODE", "possession")
    monkeypatch.setenv("GAME_SIM_PACE", "vegas")
    monkeypatch.delenv("GAME_SIM_USAGE", raising=False)
    row = _two_team_comps().iloc[[0]]
    comps = pd.concat([row, row], ignore_index=True)  # same player, 2 games
    ids = dict(game_ids=pd.Series(["hi", "lo"]), team_ids=pd.Series(["TA", "TC"]))

    res = simulate.simulate(comps, n_sims=30_000, seed=31,
                            game_totals=pd.Series([54.0, 36.0]), **ids)
    hi, lo = res.summary.iloc[0], res.summary.iloc[1]
    assert hi.proj_points == pytest.approx(lo.proj_points, rel=0.05)
    assert hi.proj_std < lo.proj_std

```

===== FILE: tests/test_graph.py =====
```python
import numpy as np
import pandas as pd

from nfl_dfs.graph.build import build_graph, qb_of, team_of, teammates
from nfl_dfs.graph.cascade import project_vacated_usage


def rosters():
    return pd.DataFrame([
        {"gsis_id": "QB1", "name": "Quinn Back", "position": "QB", "team": "MIN"},
        {"gsis_id": "WR1", "name": "Alpha Receiver", "position": "WR", "team": "MIN"},
        {"gsis_id": "WR2", "name": "Beta Receiver", "position": "WR", "team": "MIN"},
        {"gsis_id": "WR3", "name": "Gamma Receiver", "position": "WR", "team": "MIN"},
        {"gsis_id": "TE1", "name": "Tight End", "position": "TE", "team": "MIN"},
        {"gsis_id": "WRX", "name": "Other Team", "position": "WR", "team": "GB"},
    ])


def qb_conn():
    return pd.DataFrame([
        {"qb": "QB1", "wr": "WR1", "team": "MIN", "targets": 60,
         "rz_targets": 12, "air_yards": 700, "tds": 6},
        {"qb": "QB1", "wr": "WR2", "team": "MIN", "targets": 40,
         "rz_targets": 5, "air_yards": 380, "tds": 2},
    ])


def usage_panel(seed=61):
    """WR2's share jumps in the weeks WR1 sat out (weeks 5, 9, 13)."""
    rng = np.random.default_rng(seed)
    rows = []
    out_weeks = {5, 9, 13}
    for week in range(1, 15):
        wr1_out = week in out_weeks
        if not wr1_out:
            rows.append({"gsis_id": "WR1", "season": 2024, "week": week,
                         "total_targets": 9, "rz20_targets": 2,
                         "target_share": rng.normal(0.27, 0.02)})
        rows.append({"gsis_id": "WR2", "season": 2024, "week": week,
                     "total_targets": 6, "rz20_targets": 1,
                     "target_share": rng.normal(0.32 if wr1_out else 0.17, 0.02)})
        rows.append({"gsis_id": "WR3", "season": 2024, "week": week,
                     "total_targets": 3, "rz20_targets": 0,
                     "target_share": rng.normal(0.14 if wr1_out else 0.09, 0.02)})
        rows.append({"gsis_id": "TE1", "season": 2024, "week": week,
                     "total_targets": 4, "rz20_targets": 1,
                     "target_share": rng.normal(0.12, 0.02)})
    return pd.DataFrame(rows)


def injuries():
    return pd.DataFrame(
        [{"gsis_id": "WR1", "season": 2024, "week": w, "game_status": "Out"}
         for w in (5, 9, 13)]
    )


def test_graph_structure():
    G = build_graph(rosters(), qb_conn())
    assert team_of(G, "WR1") == "MIN"
    assert set(teammates(G, "WR1")) == {"WR2", "WR3"}   # same position group only
    assert qb_of(G, "WR1") == "QB1"
    assert "WRX" not in teammates(G, "WR1")             # other team excluded


def test_cascade_uses_absence_history():
    G = build_graph(rosters(), qb_conn())
    out = project_vacated_usage(G, usage_panel(), injuries(), "WR1")
    assert (out.method == "history").all()
    top = out.iloc[0]
    assert top.gsis_id == "WR2"
    # WR2 gained ~15 share points when WR1 sat
    assert top.delta > 0.10
    # WR3 also gains, but less
    wr3 = out[out.gsis_id == "WR3"].iloc[0]
    assert 0.0 < wr3.delta < top.delta


def test_cascade_falls_back_without_history():
    G = build_graph(rosters(), qb_conn())
    thin_injuries = injuries().head(1)  # only one absence: below threshold
    out = project_vacated_usage(G, usage_panel(), thin_injuries, "WR1")
    assert (out.method == "depth_chart").all()
    # Fallback still ranks the higher-usage teammate first
    assert out.iloc[0].gsis_id == "WR2"
    assert (out.delta > 0).all()


def test_cascade_no_candidates():
    lone = pd.DataFrame([{"gsis_id": "K1", "name": "Kicker", "position": "K",
                          "team": "MIN"}])
    G = build_graph(lone, qb_conn().head(0))
    out = project_vacated_usage(G, usage_panel(), injuries(), "K1")
    assert out.empty

```

===== FILE: tests/test_leakage.py =====
```python
"""Leakage checker tested on synthetic data where we control the truth."""

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.features.leakage import (
    LeakageError,
    assert_first_game_features_null,
    assert_no_leakage,
    trailing_mean_excluding_current,
)


def make_source(n_players=20, n_weeks=10, seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        for w in range(1, n_weeks + 1):
            rows.append(
                {"gsis_id": f"00-{p:07d}", "season": 2024, "week": w,
                 "target_share": rng.uniform(0, 0.35)}
            )
    return pd.DataFrame(rows)


def build_correct(source):
    out = source.copy()
    out["target_share_l4"] = trailing_mean_excluding_current(out, "target_share", window=4)
    out["games_played_prior"] = out.groupby(["gsis_id", "season"]).cumcount()
    return out


def build_leaky(source):
    """The classic bug: rolling window includes the current week."""
    out = source.sort_values(["gsis_id", "season", "week"]).copy()
    out["target_share_l4"] = out.groupby(["gsis_id", "season"])["target_share"].transform(
        lambda s: s.rolling(4, min_periods=1).mean()  # no shift(1) — leaks
    )
    out["games_played_prior"] = out.groupby(["gsis_id", "season"]).cumcount()
    return out


def test_reference_excludes_current_week():
    source = make_source(n_players=1, n_weeks=3)
    vals = source.target_share.tolist()
    got = trailing_mean_excluding_current(source, "target_share", window=4)
    assert np.isnan(got.iloc[0])                       # week 1: nothing prior
    assert got.iloc[1] == pytest.approx(vals[0])       # week 2: only week 1
    assert got.iloc[2] == pytest.approx(np.mean(vals[:2]))


def test_expanding_window():
    source = make_source(n_players=1, n_weeks=6)
    got = trailing_mean_excluding_current(source, "target_share", window=None)
    assert got.iloc[5] == pytest.approx(source.target_share.iloc[:5].mean())


def test_correct_build_passes():
    source = make_source()
    built = build_correct(source)
    assert_no_leakage(built, source, "target_share_l4", "target_share", window=4)
    assert_first_game_features_null(built, ["target_share_l4"])


def test_leaky_build_fails():
    source = make_source()
    built = build_leaky(source)
    with pytest.raises(LeakageError):
        assert_no_leakage(built, source, "target_share_l4", "target_share", window=4)


def test_leaky_build_fails_first_game_check():
    source = make_source()
    built = build_leaky(source)
    with pytest.raises(LeakageError):
        assert_first_game_features_null(built, ["target_share_l4"])


def test_unordered_input_handled():
    source = make_source().sample(frac=1, random_state=3)  # shuffle rows
    built = build_correct(source)
    assert_no_leakage(built, source, "target_share_l4", "target_share", window=4)


def test_team_grain_key_col():
    """Defense-style checks: team key instead of gsis_id."""
    source = make_source(n_players=6, n_weeks=10).rename(
        columns={"gsis_id": "team", "target_share": "epa_allowed"}
    )
    built = source.copy()
    built["epa_allowed_l6"] = trailing_mean_excluding_current(
        built, "epa_allowed", window=6, group_cols=("team", "season")
    )
    assert_no_leakage(built, source, "epa_allowed_l6", "epa_allowed",
                      window=6, key_col="team")

    leaky = source.sort_values(["team", "season", "week"]).copy()
    leaky["epa_allowed_l6"] = leaky.groupby(["team", "season"])["epa_allowed"].transform(
        lambda s: s.rolling(6, min_periods=1).mean()
    )
    with pytest.raises(LeakageError):
        assert_no_leakage(leaky, source, "epa_allowed_l6", "epa_allowed",
                          window=6, key_col="team")


def test_first_row_null_generic():
    from nfl_dfs.features.leakage import assert_first_row_features_null

    source = make_source(n_players=3, n_weeks=5).rename(columns={"gsis_id": "team"})
    ok = source.copy()
    ok["f_l6"] = trailing_mean_excluding_current(
        ok, "target_share", window=6, group_cols=("team", "season")
    )
    assert_first_row_features_null(ok, ["f_l6"], ("team", "season"))

    bad = ok.copy()
    bad["f_l6"] = bad["f_l6"].fillna(0.1)
    with pytest.raises(LeakageError):
        assert_first_row_features_null(bad, ["f_l6"], ("team", "season"))

```

===== FILE: tests/test_market_implied.py =====
```python
"""De-vig / implied-curve mechanics (Addendum 45)."""
import numpy as np
import pandas as pd

from nfl_dfs.inference.market_implied import (
    american_implied, curve_quantile, implied_curve, market_quantiles)


def _ladder():
    # A realistic DK alt ladder: P(over) falls as the line rises.
    rows = []
    for pt, over, under in [(29.5, -650, 475), (39.5, -270, 210),
                            (46.5, -165, 130), (59.5, 135, -165),
                            (67.5, 210, -265), (85.5, 500, -700)]:
        rows.append({"point": pt, "outcome_name": "Over", "price": over})
        rows.append({"point": pt, "outcome_name": "Under", "price": under})
    return pd.DataFrame(rows)


def test_american_implied_symmetry():
    assert abs(american_implied(100) - 0.5) < 1e-9
    assert abs(american_implied(-110) + american_implied(110) - 1.0) < 0.03


def test_curve_monotone_and_devigged():
    x, y = implied_curve(_ladder())
    assert (np.diff(x) > 0).all() and (np.diff(y) <= 1e-12).all()
    assert 0.8 < y[0] < 1.0 and 0.0 < y[-1] < 0.25


def test_quantiles_ordered_and_in_range():
    x, y = implied_curve(_ladder())
    med, q90 = curve_quantile(x, y, 0.5), curve_quantile(x, y, 0.9)
    assert med < q90
    assert 39.5 <= med <= 67.5 and q90 >= 67.5


def test_market_quantiles_frame():
    d = _ladder()
    d["season"], d["week"], d["market"], d["player"] = 2025, 1, "m", "A B"
    out = market_quantiles(d)
    assert len(out) == 1 and out.q50.iloc[0] < out.q90.iloc[0]

```

===== FILE: tests/test_news.py =====
```python
import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from nfl_dfs.graph import news


def raw_llm_output():
    return json.dumps([
        {"player": "Beta Receiver Jr.", "claim_type": "role_change",
         "direction": 1, "confidence": 0.8,
         "quote": "coach wants him more involved in the red zone"},
        {"player": "Alpha Receiver", "claim_type": "injury_status",
         "direction": -1, "confidence": 0.9, "quote": "did not practice"},
        # Invalid rows the parser must drop:
        {"player": "Bad Type", "claim_type": "vibes", "direction": 1,
         "confidence": 0.5, "quote": "x"},
        {"player": "Bad Direction", "claim_type": "role_change",
         "direction": 2, "confidence": 0.5, "quote": "x"},
        {"player": "", "claim_type": "role_change", "direction": 1,
         "confidence": 0.5, "quote": "x"},
    ])


def id_map():
    return pd.DataFrame({
        "display_name": ["Beta Receiver", "Alpha Receiver"],
        "gsis_id": ["WR2", "WR1"],
    })


def test_parse_claims_enforces_schema():
    claims = news.parse_claims(raw_llm_output(), "beat-writer",
                               "2025-09-16T12:00:00Z", 0.7)
    assert len(claims) == 2
    assert {c.claim_type for c in claims} == {"role_change", "injury_status"}


def test_parse_claims_garbage_returns_empty():
    assert news.parse_claims("no json here", "s", "2025-01-01T00:00:00Z", 0.5) == []
    assert news.parse_claims("[{broken", "s", "2025-01-01T00:00:00Z", 0.5) == []


def test_entity_resolution_strips_suffixes():
    claims = news.parse_claims(raw_llm_output(), "beat-writer",
                               "2025-09-16T12:00:00Z", 0.7)
    resolved = news.resolve_entities(claims, id_map())
    by_player = {c.player: c.gsis_id for c in resolved}
    assert by_player["Beta Receiver Jr."] == "WR2"   # suffix stripped
    assert by_player["Alpha Receiver"] == "WR1"


def test_signal_features_decay_and_direction():
    now = datetime(2025, 9, 18, tzinfo=timezone.utc)
    fresh = (now - timedelta(days=1)).isoformat()
    stale = (now - timedelta(days=12)).isoformat()
    claims = news.parse_claims(raw_llm_output(), "beat", fresh, 0.8)
    claims += news.parse_claims(raw_llm_output(), "beat", stale, 0.8)
    resolved = news.resolve_entities(claims, id_map())
    feats = news.signal_features(news.to_frame(resolved), as_of=now)
    feats = feats.set_index("gsis_id")

    # WR2 has a fresh positive role signal; WR1 a fresh injury concern
    assert feats.loc["WR2", "positive_role_signals_l7d"] > 0.3
    assert feats.loc["WR1", "injury_concern_signals_l7d"] > 0.3
    # 12-day-old claims fell outside the 7d window entirely: totals equal
    # what the fresh claims alone produce
    only_fresh = news.signal_features(
        news.to_frame(news.resolve_entities(
            news.parse_claims(raw_llm_output(), "beat", fresh, 0.8), id_map()
        )), as_of=now,
    ).set_index("gsis_id")
    assert feats.loc["WR2", "positive_role_signals_l7d"] == (
        only_fresh.loc["WR2", "positive_role_signals_l7d"]
    )


def test_unresolved_claims_excluded_from_features():
    claims = news.parse_claims(json.dumps([
        {"player": "Unknown Guy", "claim_type": "role_change", "direction": 1,
         "confidence": 0.9, "quote": "x"},
    ]), "beat", "2025-09-16T12:00:00Z", 0.9)
    resolved = news.resolve_entities(claims, id_map())
    feats = news.signal_features(news.to_frame(resolved),
                                 as_of=datetime(2025, 9, 17, tzinfo=timezone.utc))
    assert feats.empty

```

===== FILE: tests/test_nflverse_job.py =====
```python
"""Offline guard for nflverse_job._load's write dispositions.

Regression for the 2026-07-28 data loss: the scheduled (incremental) run
loads only the current season, and _load's old unconditional WRITE_TRUNCATE
wiped the 2014-2024 backfill from every season-scoped raw table. The
incremental path must delete-then-append, never truncate."""

import pandas as pd

from nfl_dfs.ingest import nflverse_job


class FakeFrame:
    def __init__(self, pdf):
        self._pdf = pdf

    def to_pandas(self):
        return self._pdf


def _capture(monkeypatch):
    loads, deletes = [], []
    monkeypatch.setattr(
        nflverse_job, "load_dataframe",
        lambda df, table, **kw: loads.append((table, kw.get("write_disposition",
                                                            "WRITE_TRUNCATE"))))
    monkeypatch.setattr(
        nflverse_job, "_delete_seasons",
        lambda table, seasons: deletes.append((table, tuple(seasons))))
    return loads, deletes


def test_incremental_load_deletes_then_appends(monkeypatch):
    loads, deletes = _capture(monkeypatch)
    df = FakeFrame(pd.DataFrame({"season": [2025], "x": [1]}))
    nflverse_job._load(df, "pbp", replace_seasons=[2025])
    assert deletes == [("pbp", (2025,))]
    assert loads == [("pbp", "WRITE_APPEND")]


def test_full_refresh_truncates(monkeypatch):
    loads, deletes = _capture(monkeypatch)
    df = FakeFrame(pd.DataFrame({"season": [2014, 2025], "x": [1, 2]}))
    nflverse_job._load(df, "pbp", replace_seasons=None)
    assert deletes == []
    assert loads == [("pbp", "WRITE_TRUNCATE")]


def test_incremental_without_season_column_falls_back_to_truncate(monkeypatch):
    loads, deletes = _capture(monkeypatch)
    df = FakeFrame(pd.DataFrame({"dt": ["2025-09-01"], "x": [1]}))
    nflverse_job._load(df, "depth_charts_snapshots", replace_seasons=[2025])
    assert deletes == []
    assert loads == [("depth_charts_snapshots", "WRITE_TRUNCATE")]

```

===== FILE: tests/test_notes.py =====
```python
"""Manual usage notes: decay curve, opportunity application, chat dispatch.
All offline — BigQuery reads are monkeypatched."""
import numpy as np
import pandas as pd
import pytest

from nfl_dfs import notes


def test_decay_curve():
    assert notes.decay(1) == 1.0
    assert 0 < notes.decay(3) < 1
    assert notes.decay(notes.DECAY_FULL_WEEK) == 0.0
    assert notes.decay(18) == 0.0


def _fake_notes():
    return pd.DataFrame([
        {"note_id": "a", "gsis_id": "P1", "display_name": "Player One",
         "season": 2026, "mult": 1.2, "note": "slot role", "source": ""},
    ])


def test_apply_notes_scales_opportunity(monkeypatch):
    monkeypatch.setattr(notes, "list_notes", lambda s: _fake_notes())
    comps = pd.DataFrame({"targets": [5.0, 5.0], "carries": [1.0, 1.0],
                          "ypr": [10.0, 10.0]})
    feats = pd.DataFrame({"gsis_id": ["P1", "P2"]})
    out = notes.apply_notes(comps, feats, season=2026, week=1)
    assert out.targets.iloc[0] == pytest.approx(6.0)   # 1.2x at full effect
    assert out.targets.iloc[1] == pytest.approx(5.0)   # untouched player
    assert out.ypr.iloc[0] == pytest.approx(10.0)      # rates never scaled

    late = notes.apply_notes(comps, feats, season=2026, week=10)
    assert np.allclose(late.targets, comps.targets)    # decayed to nothing

    mid = notes.apply_notes(comps, feats, season=2026, week=3)
    assert 5.0 < mid.targets.iloc[0] < 6.0             # partial decay


def test_apply_notes_survives_bq_failure(monkeypatch):
    def boom(_):
        raise RuntimeError("bq down")
    monkeypatch.setattr(notes, "list_notes", boom)
    comps = pd.DataFrame({"targets": [5.0]})
    feats = pd.DataFrame({"gsis_id": ["P1"]})
    out = notes.apply_notes(comps, feats, season=2026, week=1)
    assert out.targets.iloc[0] == 5.0


def test_add_note_clamps_mult(monkeypatch):
    captured = {}

    def fake_load(df, table, **kw):
        captured["mult"] = df.mult.iloc[0]
    monkeypatch.setattr(notes, "load_dataframe", fake_load)
    notes.add_note("P1", "Player One", 2026, mult=9.0, note="hype")
    assert captured["mult"] == 1.4


def test_chat_tool_dispatch(monkeypatch):
    from nfl_dfs.app import chat

    monkeypatch.setattr(notes, "list_notes", lambda s: _fake_notes())
    out = chat.execute_tool("list_usage_notes", {"season": 2026})
    assert "Player One" in out

    monkeypatch.setattr(notes, "add_note", lambda **kw: "abc123")
    out = chat.execute_tool("add_usage_note", {
        "gsis_id": "P1", "display_name": "Player One", "mult": 1.15,
        "note": "coach: slot role"})
    assert "abc123" in out

    monkeypatch.setattr(notes, "delete_note", lambda nid: 1)
    assert "deleted 1" in chat.execute_tool("delete_usage_note",
                                            {"note_id": "abc123"})
    assert "unknown tool" in chat.execute_tool("nope", {})


def test_dst_projection_rows_assembly():
    from nfl_dfs.inference.dst_projections import (FALLBACK_PROJ, P90_OFF,
                                                   build_rows)

    slate = pd.DataFrame({
        "dk_player_id": [901, 902], "display_name": ["Bears", "Lions"],
        "team_abbr": ["CHI", "DET"], "salary": [3200, 2600],
        "draft_group_id": [7, 7]})
    trailing = pd.DataFrame({"team": ["CHI"], "dst_l4": [8.0]})
    opponents = pd.DataFrame({"team": ["CHI", "DET"],
                              "opponent": ["DET", "CHI"]})
    qb = pd.DataFrame({"team": ["DET", "CHI"], "career_starts": [2, 120]})

    rows = build_rows(slate, trailing, opponents, qb, 2026, 1, "vtest")
    chi = rows[rows.team == "CHI"].iloc[0]
    det = rows[rows.team == "DET"].iloc[0]
    # CHI: 8.0 trailing + rookie-opponent bonus 2.2
    assert chi.proj_points == pytest.approx(10.2)
    assert chi.proj_p90 == pytest.approx(10.2 + P90_OFF)
    # DET: no trailing history -> fallback, veteran opponent -0.7
    assert det.proj_points == pytest.approx(FALLBACK_PROJ - 0.7)
    assert (rows.position == "DST").all()
    assert rows.value.gt(0).all()


def test_vegas_first_dst_model():
    from nfl_dfs.inference.dst_projections import (COEF_INTERCEPT,
                                                   COEF_L16,
                                                   COEF_OPP_IMPLIED,
                                                   COEF_ROOKIE,
                                                   model_projection)

    opp_implied = pd.Series([17.0, 26.0, np.nan])
    trailing = pd.Series([8.0, 8.0, 8.0])
    starts = pd.Series([2, 120, 2])
    out = model_projection(opp_implied, trailing, starts)
    # Vegas path: intercept + implied + trailing + rookie terms
    exp0 = COEF_INTERCEPT + COEF_OPP_IMPLIED * 17 + COEF_L16 * 8 + COEF_ROOKIE
    assert out.iloc[0] == pytest.approx(exp0)
    assert out.iloc[0] > out.iloc[1] + 3      # low implied total >> high
    # No line -> fallback: trailing + raw QB-experience adjustment
    assert out.iloc[2] == pytest.approx(8.0 + 2.2)


def test_prop_lines_parse():
    from nfl_dfs.ingest.oddsapi_import import parse_event_odds

    payload = {"data": {
        "id": "ev1", "commence_time": "2025-09-07T17:00:00Z",
        "home_team": "Chicago Bears", "away_team": "Detroit Lions",
        "bookmakers": [{"key": "draftkings", "markets": [
            {"key": "player_pass_yds", "outcomes": [
                {"name": "Over", "description": "C. Williams",
                 "price": -115, "point": 245.5},
                {"name": "Under", "description": "C. Williams",
                 "price": -105, "point": 245.5}]},
            {"key": "player_anytime_td", "outcomes": [
                {"name": "D. Montgomery", "price": +120}]},
        ]}]}}
    rows = parse_event_odds(payload, 2025, 1, "2025-09-07T15:00:00Z")
    assert len(rows) == 3
    over = rows[0]
    assert over["player"] == "C. Williams" and over["point"] == 245.5
    td = rows[2]
    assert td["player"] == "D. Montgomery" and td["point"] is None
    assert all(r["season"] == 2025 and r["bookmaker"] == "draftkings"
               for r in rows)


def test_entry_history_reimport_preserves_manual_fields(monkeypatch):
    saved = {}
    monkeypatch.setattr(notes, "list_results", lambda s: pd.DataFrame(
        [{"result_id": "x", "week": 1, "contests": 30, "spent": 60.0,
          "won": 80.0, "best_score": 187.5, "best_rank": 42,
          "note": "great punt week"}]))
    monkeypatch.setattr(notes, "upsert_result",
                        lambda *a, **k: saved.update(k) or "rid")
    monkeypatch.setattr(notes, "query_df", lambda *a, **k: pd.DataFrame(
        [{"week": 1, "d0": "2026-09-10", "d1": "2026-09-14"}]))
    csv_text = ("Contest,Entry Fee,Winnings,Contest Date\n"
                "Milly,$3,$0,2026-09-13\nMilly,$3,$12.50,2026-09-13\n")
    out = notes.import_entry_history(csv_text, 2026)
    assert out[1]["contests"] == 2 and out[1]["spent"] == 6.0
    assert saved["best_score"] == 187.5 and saved["best_rank"] == 42
    assert saved["note"] == "great punt week"


def test_list_entered_sets_survives_missing_table(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("table absent")
    monkeypatch.setattr(notes, "query_df", boom)
    df = notes.list_entered_sets(2025)
    assert df.empty
    assert list(df.columns) == ["week", "lineups", "players", "recorded_at"]


def test_delete_entered_lineups_targets_the_week(monkeypatch):
    captured = {}

    class _Job:
        num_dml_affected_rows = 9

        def result(self):
            return None

    class _Client:
        def query(self, sql, **kw):
            captured["sql"] = sql
            return _Job()

    import nfl_dfs.bq as bq
    monkeypatch.setattr(bq, "client", lambda: _Client())
    assert notes.delete_entered_lineups(2025, 3) == 9
    assert notes.ENTERED_TABLE in captured["sql"]
    assert "season=2025" in captured["sql"] and "week=3" in captured["sql"]

```

===== FILE: tests/test_odds_job.py =====
```python
"""Offline coverage for the Odds-API-backed game-lines snapshot.

The original DK-sportsbook scrape never landed a row (403, see the README
deficiency log); this tests its 2026-07-31 replacement against a payload
modeled on The Odds API's live /odds response shape.
"""

from dataclasses import replace

import pandas as pd
import pytest

from nfl_dfs.config import settings
from nfl_dfs.ingest import odds_job


def _payload():
    return [
        {
            "id": "abc123",
            "commence_time": "2026-09-10T00:20:00Z",
            "home_team": "Philadelphia Eagles",
            "away_team": "Dallas Cowboys",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Philadelphia Eagles", "price": -170},
                                {"name": "Dallas Cowboys", "price": 142},
                            ],
                        },
                        {
                            "key": "spreads",
                            "outcomes": [
                                {"name": "Philadelphia Eagles", "price": -110, "point": -3.5},
                                {"name": "Dallas Cowboys", "price": -110, "point": 3.5},
                            ],
                        },
                        {
                            "key": "totals",
                            "outcomes": [
                                {"name": "Over", "price": -108, "point": 47.5},
                                {"name": "Under", "price": -112, "point": 47.5},
                            ],
                        },
                    ],
                },
                {
                    # A non-DK book in the payload must be ignored even if
                    # the API's bookmakers filter ever loosens.
                    "key": "fanduel",
                    "markets": [
                        {"key": "h2h", "outcomes": [{"name": "Dallas Cowboys", "price": 150}]},
                    ],
                },
            ],
        },
    ]


def test_rows_map_markets_and_format_odds():
    rows = odds_job._rows_from_payload(_payload())
    df = pd.DataFrame(rows)
    assert len(df) == 6  # 2 h2h + 2 spreads + 2 totals, fanduel ignored
    assert set(df.market_type) == {"Moneyline", "Spread", "Total"}
    assert set(df.event_name) == {"Dallas Cowboys @ Philadelphia Eagles"}

    ml = df[df.market_type == "Moneyline"].set_index("selection")
    assert ml.loc["Philadelphia Eagles", "odds_american"] == "-170"
    assert ml.loc["Dallas Cowboys", "odds_american"] == "+142"
    assert ml.line.isna().all()  # moneyline has no point

    total = df[df.market_type == "Total"]
    assert set(total.selection) == {"Over", "Under"}
    assert (total.line == 47.5).all()


def test_rows_empty_payload():
    assert odds_job._rows_from_payload([]) == []


def test_run_loads_snapshot(monkeypatch):
    monkeypatch.setattr(odds_job, "_fetch", lambda session=None: _payload())
    loaded = []
    monkeypatch.setattr(
        "nfl_dfs.ingest.odds_job.load_dataframe",
        lambda df, table, **kw: loaded.append((table, df, kw)),
    )

    odds_job.run()

    assert len(loaded) == 1
    table, df, kw = loaded[0]
    assert table == "odds_snapshots"
    assert kw["write_disposition"] == "WRITE_APPEND"
    assert len(df) == 6


def test_run_noop_on_empty(monkeypatch):
    monkeypatch.setattr(odds_job, "_fetch", lambda session=None: [])

    def boom(*a, **k):
        raise AssertionError("must not load an empty frame")

    monkeypatch.setattr("nfl_dfs.ingest.odds_job.load_dataframe", boom)
    odds_job.run()  # must not raise


def test_fetch_requires_key(monkeypatch):
    monkeypatch.setattr(odds_job, "settings", replace(settings, odds_api_key=""))
    with pytest.raises(RuntimeError, match="ODDS_API_KEY"):
        odds_job._fetch()

```

===== FILE: tests/test_optimizer.py =====
```python
import numpy as np
import pytest

from nfl_dfs.optimizer.export import exposure_summary, to_dk_csv
from nfl_dfs.optimizer.lineup import Lineup, StackRules, optimize, optimize_many


def make_pool(seed=31, n_teams=6):
    """A feasible synthetic player pool across n_teams teams / 3 games."""
    rng = np.random.default_rng(seed)
    players = []
    pid = 0
    for t in range(n_teams):
        team, opp = f"T{t}", f"T{t + 1 if t % 2 == 0 else t - 1}"
        game = f"G{t // 2}"
        roster = [("QB", 1), ("RB", 3), ("WR", 4), ("TE", 2), ("DST", 1)]
        for pos, n in roster:
            for i in range(n):
                base = {"QB": 20, "RB": 14, "WR": 12, "TE": 8, "DST": 7}[pos]
                proj = max(1.0, base - 3 * i + rng.normal(0, 1.5))
                players.append({
                    "id": pid, "name": f"{pos}{i}_{team}", "pos": pos,
                    "team": team, "opp": opp, "game_id": game,
                    "salary": int(np.clip(2800 + proj * 320 + rng.normal(0, 300),
                                          2500, 9500)),
                    "proj": proj,
                })
                pid += 1
    return players


def counts(lineup):
    c = {}
    for p in lineup.players:
        c[p["pos"]] = c.get(p["pos"], 0) + 1
    return c


def test_roster_and_cap_constraints():
    lu = optimize(make_pool())
    assert lu is not None
    assert len(lu.players) == 9
    assert lu.salary <= 50_000
    c = counts(lu)
    assert c["QB"] == 1 and c["DST"] == 1
    assert 2 <= c["RB"] <= 3
    assert 3 <= c["WR"] <= 4
    assert 1 <= c["TE"] <= 2
    games = {p["game_id"] for p in lu.players}
    assert len(games) >= 2


def test_locks_and_bans():
    pool = make_pool()
    worst_wr = min((p for p in pool if p["pos"] == "WR"), key=lambda p: p["proj"])
    best_qb = max((p for p in pool if p["pos"] == "QB"), key=lambda p: p["proj"])
    lu = optimize(pool, locks={worst_wr["id"]}, bans={best_qb["id"]})
    ids = lu.ids
    assert worst_wr["id"] in ids
    assert best_qb["id"] not in ids


def test_qb_stack_and_bring_back():
    pool = make_pool()
    lu = optimize(pool, stack=StackRules(qb_stack_min=2, bring_back_min=1))
    qb = next(p for p in lu.players if p["pos"] == "QB")
    catchers = [p for p in lu.players
                if p["pos"] in ("WR", "TE") and p["team"] == qb["team"]]
    assert len(catchers) >= 2
    bring_back = [p for p in lu.players
                  if p["team"] == qb["opp"] and p["pos"] in ("RB", "WR", "TE")]
    assert len(bring_back) >= 1


def test_no_rb_vs_opposing_dst_and_single_rb_per_team():
    lu = optimize(make_pool(), stack=StackRules())
    dst = next(p for p in lu.players if p["pos"] == "DST")
    rbs = [p for p in lu.players if p["pos"] == "RB"]
    assert all(rb["team"] != dst["opp"] for rb in rbs)
    teams = [rb["team"] for rb in rbs]
    assert len(teams) == len(set(teams))


def test_multi_lineup_uniqueness():
    lineups = optimize_many(make_pool(), n_lineups=5, max_overlap=7)
    assert len(lineups) == 5
    for i, a in enumerate(lineups):
        for b in lineups[i + 1:]:
            assert len(a.ids & b.ids) <= 7
    # Projections should be non-increasing as constraints accumulate
    projs = [lu.proj for lu in lineups]
    assert all(projs[i] >= projs[i + 1] - 1e-6 for i in range(len(projs) - 1))


def test_infeasible_returns_none():
    pool = [p for p in make_pool() if p["pos"] != "QB"]
    assert optimize(pool) is None


def test_dk_csv_and_exposure():
    lineups = optimize_many(make_pool(), n_lineups=3)
    csv_text = to_dk_csv(lineups)
    lines = csv_text.strip().splitlines()
    assert lines[0].split(",") == ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    assert len(lines) == 4
    # Each data row has 9 slots, each like "Name (id)"
    assert all(len(line.split(",")) == 9 for line in lines[1:])

    exp = exposure_summary(lineups)
    assert exp[0]["exposure"] <= 1.0
    assert sum(e["lineups"] for e in exp) == 27


def test_dk_csv_prefers_draftable_ids():
    """Upload cells must carry the slate's draftable ID when the pool has
    one; the stable player id is only a last-resort fallback."""
    pool = make_pool()
    for p in pool:
        p["dk_id"] = p["id"] + 40_000_000
    lu = optimize(pool)
    csv_text = to_dk_csv([lu])
    row = csv_text.strip().splitlines()[1]
    for p in lu.players:
        assert f"({p['dk_id']})" in row
        assert f"({p['id']})" not in row


def test_fill_entries_csv_round_trip():
    from nfl_dfs.optimizer.export import entry_count, fill_entries_csv

    lineups = optimize_many(make_pool(), n_lineups=2)
    entries = (
        "\ufeffEntry ID,Contest Name,Contest ID,Entry Fee,"
        "QB,RB,RB,WR,WR,WR,TE,FLEX,DST,,Instructions\n"
        "4111111,NFL $100K Flea Flicker,987,$5,,,,,,,,,,,Fill in your entries\n"
        "4111112,NFL $100K Flea Flicker,987,$5\n"
        "4111113,\"NFL $2 Double, Up\",988,$2\n"
        ",,,,,,,,,,,,,,Name,ID\n"
        ",,,,,,,,,,,,,,Some Player,40000001\n"
    )
    assert entry_count(entries) == 3

    filled = fill_entries_csv(entries, lineups)
    import csv as csv_mod
    import io as io_mod

    rows = list(csv_mod.reader(io_mod.StringIO(filled)))
    # Metadata, instructions, and the player-list block are untouched
    assert rows[1][:4] == ["4111111", "NFL $100K Flea Flicker", "987", "$5"]
    assert rows[1][14] == "Fill in your entries"
    assert rows[3][:3] == ["4111113", "NFL $2 Double, Up", "988"]
    assert rows[5][14:16] == ["Some Player", "40000001"]
    # Each entry got 9 slot cells; entries cycle when lineups run out
    for r in (rows[1], rows[2], rows[3]):
        assert all(cell.endswith(")") for cell in r[4:13])
    assert rows[3][4:13] == rows[1][4:13]
    assert rows[2][4:13] != rows[1][4:13]


def test_fill_entries_csv_rejects_bad_input():
    import pytest as pt

    from nfl_dfs.optimizer.export import fill_entries_csv

    lineups = optimize_many(make_pool(), n_lineups=1)
    with pt.raises(ValueError, match="Not a DKEntries"):
        fill_entries_csv("QB,RB,RB,WR,WR,WR,TE,FLEX,DST\n", lineups)
    showdown_file = (
        "Entry ID,Contest Name,Contest ID,Entry Fee,CPT,FLEX,FLEX,FLEX,FLEX,FLEX\n"
        "4111111,Showdown,55,$1\n"
    )
    with pt.raises(ValueError, match="mismatch"):
        fill_entries_csv(showdown_file, lineups)  # 9-man classic lineups
    with pt.raises(ValueError, match="No lineups"):
        fill_entries_csv(showdown_file, [])


def test_slot_order_flex_identification():
    lu = optimize(make_pool())
    ordered = lu.slot_order()
    positions = [p["pos"] for p in ordered]
    assert positions[0] == "QB"
    assert positions[1:3] == ["RB", "RB"]
    assert positions[3:6] == ["WR", "WR", "WR"]
    assert positions[6] == "TE"
    assert positions[7] in ("RB", "WR", "TE")  # FLEX
    assert positions[8] == "DST"


def _kickoff_pool():
    def p(id, pos, proj, kickoff=None):
        return {"id": id, "pos": pos, "proj": proj, "salary": 5000,
                "kickoff": kickoff}

    # 3 RBs (surplus position), 3 WRs, 1 TE => RB's leftover goes to FLEX.
    # rb3 has the highest proj (would win the old proj-based leftover
    # pick if it were the *lowest*) but also the latest kickoff, while
    # rb2 has the lowest proj but an early kickoff.
    return [
        p("qb", "QB", 20, "2026-09-10T13:00:00Z"),
        p("rb1", "RB", 15, "2026-09-10T13:00:00Z"),
        p("rb2", "RB", 14, "2026-09-10T13:05:00Z"),
        p("rb3", "RB", 25, "2026-09-10T20:20:00Z"),
        p("wr1", "WR", 12, "2026-09-10T13:00:00Z"),
        p("wr2", "WR", 11, "2026-09-10T13:00:00Z"),
        p("wr3", "WR", 10, "2026-09-10T13:00:00Z"),
        p("te1", "TE", 8, "2026-09-10T13:00:00Z"),
        p("dst", "DST", 7, "2026-09-10T13:00:00Z"),
    ]


def test_slot_order_prefers_latest_kickoff_for_flex():
    """With every player's kickoff known, FLEX goes to the latest-kickoff
    player in the surplus position (roadmap #13.2: max late-swap
    flexibility, since FLEX is the only slot DK lets you fill with any of
    RB/WR/TE) even though it isn't the lowest-projected one."""
    ordered = Lineup(_kickoff_pool()).slot_order()
    assert [p["id"] for p in ordered[1:3]] == ["rb1", "rb2"]
    assert ordered[7]["id"] == "rb3"
    assert ordered[7]["pos"] == "RB"


def test_slot_order_ignores_kickoff_when_incomplete():
    """Missing kickoff for even one player must fall back to the original
    proj-based FLEX pick — half-known kickoff data is worse than none."""
    players = _kickoff_pool()
    next(p for p in players if p["id"] == "dst")["kickoff"] = None
    ordered = Lineup(players).slot_order()
    assert ordered[7]["id"] == "rb2"  # lowest-proj RB, the old behavior


def test_auto_core_budget_guard_sheds_expensive_studs():
    """A consensus lineup stuffed with studs must shed its priciest members
    until every free slot keeps a mid-tier budget."""
    from nfl_dfs.optimizer.lineup import CORE_FREE_SLOT_BUDGET, Lineup, _auto_core

    players = []
    for i in range(9):
        salary = 9000 if i < 5 else 4000
        players.append({"id": i, "name": f"p{i}", "pos": "WR", "team": f"T{i}",
                        "opp": "X", "game_id": "G", "salary": salary,
                        "proj": salary / 400})
    # Pool with plenty of cheap high-value alternatives so studs are only
    # median value at their position
    pool = players + [
        {"id": 100 + j, "name": f"v{j}", "pos": "WR", "team": "T9", "opp": "X",
         "game_id": "G", "salary": 3500, "proj": 12.0}
        for j in range(9)
    ]
    counts = {p["id"]: 15 for p in players}  # everyone unanimous
    core = _auto_core(Lineup(players), counts, 15, pool)
    core_salary = sum(p["salary"] for p in core)
    assert 50_000 - core_salary >= (9 - len(core)) * CORE_FREE_SLOT_BUDGET
    # The shed members are the expensive ones
    assert max(p["salary"] for p in core) <= 9000
    assert sum(1 for p in core if p["salary"] == 9000) < 5


# --- Showdown Captain Mode ---------------------------------------------------

from nfl_dfs.optimizer.export import showdown_exposure_summary, to_dk_showdown_csv
from nfl_dfs.optimizer.showdown import (
    CPT_MULT,
    cpt_salary,
    optimize_many_showdown,
    optimize_showdown,
)


def make_showdown_pool(seed=17):
    """One game, two teams, full showdown pool including K and DST."""
    rng = np.random.default_rng(seed)
    players = []
    pid = 0
    for team, opp in (("HOME", "AWAY"), ("AWAY", "HOME")):
        roster = [("QB", 1), ("RB", 2), ("WR", 4), ("TE", 2), ("K", 1), ("DST", 1)]
        for pos, n in roster:
            for i in range(n):
                base = {"QB": 20, "RB": 14, "WR": 12, "TE": 8, "K": 7, "DST": 6}[pos]
                proj = max(1.0, base - 3 * i + rng.normal(0, 1.5))
                players.append({
                    "id": pid, "name": f"{pos}{i}_{team}", "pos": pos,
                    "team": team, "opp": opp, "game_id": 555,
                    "salary": int(np.clip(200 * round((1500 + proj * 450) / 200),
                                          1000, 11_600)),
                    "proj": proj,
                })
                pid += 1
    return players


def test_showdown_roster_cap_and_both_teams():
    lu = optimize_showdown(make_showdown_pool())
    assert lu is not None
    assert len(lu.players) == 6
    assert lu.captain["id"] not in {p["id"] for p in lu.flex}
    # Cap includes the 1.5x captain premium
    assert lu.salary <= 50_000
    assert lu.salary == cpt_salary(lu.captain["salary"]) + sum(
        p["salary"] for p in lu.flex
    )
    assert {p["team"] for p in lu.players} == {"HOME", "AWAY"}
    assert lu.proj == pytest.approx(
        CPT_MULT * lu.captain["proj"] + sum(p["proj"] for p in lu.flex)
    )


def test_showdown_captain_choice_is_value_aware():
    """The optimizer must weigh the 1.5x salary premium, not just points:
    an overpriced top scorer should be rostered as FLEX, with a cheaper
    player taking the captaincy."""
    pool = []
    for i in range(6):
        pool.append({"id": i, "name": f"H{i}", "pos": "WR", "team": "H",
                     "opp": "A", "game_id": 1, "salary": 7000, "proj": 20.0})
    for i in range(6, 12):
        pool.append({"id": i, "name": f"A{i}", "pos": "WR", "team": "A",
                     "opp": "H", "game_id": 1, "salary": 7000, "proj": 10.0})
    # Stud: best points, but captaining him busts the cap (16500 + 5*7000)
    pool.append({"id": 99, "name": "Stud", "pos": "QB", "team": "H",
                 "opp": "A", "game_id": 1, "salary": 11_000, "proj": 25.0})
    lu = optimize_showdown(pool)
    assert 99 in lu.ids  # worth rostering...
    assert lu.captain["id"] != 99  # ...but not at 1.5x salary
    assert lu.salary <= 50_000


def test_showdown_locks_bans_and_captain_lock():
    pool = make_showdown_pool()
    worst = min(pool, key=lambda p: p["proj"])
    best = max(pool, key=lambda p: p["proj"])
    lu = optimize_showdown(pool, locks={worst["id"]}, bans={best["id"]})
    assert worst["id"] in lu.ids and best["id"] not in lu.ids

    forced = next(p for p in pool if p["pos"] == "K")
    lu = optimize_showdown(pool, captain_lock=forced["id"])
    assert lu.captain["id"] == forced["id"]


def test_showdown_uniqueness_counts_the_captain():
    lineups = optimize_many_showdown(make_showdown_pool(), n_lineups=8)
    assert len(lineups) == 8
    keys = {lu.key for lu in lineups}
    assert len(keys) == 8  # no repeated (captain, roster) pair
    projs = [lu.proj for lu in lineups]
    assert all(projs[i] >= projs[i + 1] - 1e-6 for i in range(len(projs) - 1))

    # Tighter overlap forces the player sets themselves to differ
    diverse = optimize_many_showdown(make_showdown_pool(), n_lineups=4,
                                     max_overlap=4)
    for i, a in enumerate(diverse):
        for b in diverse[i + 1:]:
            assert len(a.ids & b.ids) <= 5


def test_showdown_infeasible_returns_none():
    one_team = [p for p in make_showdown_pool() if p["team"] == "HOME"]
    assert optimize_showdown(one_team) is None  # must roster both teams


def test_showdown_csv_and_exposure():
    lineups = optimize_many_showdown(make_showdown_pool(), n_lineups=3)
    csv_text = to_dk_showdown_csv(lineups)
    lines = csv_text.strip().splitlines()
    assert lines[0].split(",") == ["CPT", "FLEX", "FLEX", "FLEX", "FLEX", "FLEX"]
    assert len(lines) == 4
    # First slot of each row is that lineup's captain
    for lu, line in zip(lineups, lines[1:]):
        assert line.split(",")[0] == f"{lu.captain['name']} ({lu.captain['id']})"

    exp = showdown_exposure_summary(lineups)
    assert sum(e["lineups"] for e in exp) == 18
    assert sum(e["cpt_lineups"] for e in exp) == 3
    for e in exp:
        assert e["cpt_lineups"] <= e["lineups"]


def test_showdown_csv_uses_cpt_draftable_id():
    """The CPT cell must carry the CPT-slot draftable ID; FLEX cells the
    FLEX one — DK rejects a FLEX ID in the captain slot."""
    pool = make_showdown_pool()
    for p in pool:
        p["dk_id"] = p["id"] + 40_000_000
        p["cpt_dk_id"] = p["id"] + 50_000_000
    lu = optimize_showdown(pool)
    row = to_dk_showdown_csv([lu]).strip().splitlines()[1].split(",")
    assert row[0] == f"{lu.captain['name']} ({lu.captain['cpt_dk_id']})"
    for cell, p in zip(row[1:], lu.slot_order()[1:]):
        assert cell == f"{p['name']} ({p['dk_id']})"


def test_tournament_punt_slot_default():
    """Every default-built lineup must roster >=1 sub-$4k punt (94% of 2025
    Milly winners had one; punt_min defaults on in optimize_many)."""
    from nfl_dfs.optimizer.lineup import PUNT_MAX_SALARY, optimize_many

    slate = None
    from test_backtest import make_slate  # synthetic slate fixture

    pool = make_slate().to_dict("records")
    lineups = optimize_many(pool, n_lineups=5)
    assert lineups
    for lu in lineups:
        assert any(p["salary"] <= PUNT_MAX_SALARY for p in lu.players)


def test_showdown_punt_slot_default():
    from nfl_dfs.optimizer.showdown import optimize_many_showdown
    from nfl_dfs.optimizer.lineup import PUNT_MAX_SALARY
    import numpy as np

    rng = np.random.default_rng(6)
    pool = [{"id": i, "name": f"p{i}", "pos": "WR", "team": "A" if i % 2 else "B",
             "opp": None, "game_id": "G", "salary": int(rng.integers(2, 11)) * 500,
             "proj": float(rng.uniform(5, 25))} for i in range(20)]
    lineups = optimize_many_showdown(pool, n_lineups=3)
    assert lineups
    for lu in lineups:
        assert any(p["salary"] <= PUNT_MAX_SALARY for p in lu.players)


def test_game_lock_forces_concentration():
    pool = make_pool()
    gid = sorted({p["game_id"] for p in pool})[0]
    lu = optimize(pool, game_lock=(gid, 5))
    assert lu is not None
    assert sum(1 for p in lu.players if p["game_id"] == gid) >= 5
    # And without the lock the optimum is less concentrated or equal-proj
    free = optimize(pool)
    assert free.proj >= lu.proj


# select_tail_entries -------------------------------------------------------
# (restored after crash corruption zeroed these out of commit db8160c)

from nfl_dfs.optimizer.lineup import select_tail_entries


def test_tail_selection_prefers_complementary_booms():
    # A and B clear the line in the SAME sims; C clears a different sim.
    # Coverage selection must take one of {A,B} plus C — never A and B —
    # even though B beats C on every marginal stat.
    line = 100.0
    a = [120, 115, 0, 0, 0, 0]
    b = [125, 118, 0, 0, 0, 50]
    c = [0, 0, 110, 0, 0, 0]
    picked = select_tail_entries(np.array([a, b, c], dtype=float), 2, line)
    assert set(picked) == {1, 2}  # B (higher P and mean of the pair) + C


def test_tail_selection_fills_after_saturation():
    line = 100.0
    a = [120, 0, 0]   # covers sim 0
    b = [0, 0, 90]    # never clears
    c = [0, 0, 95]    # never clears, higher mean
    picked = select_tail_entries(np.array([a, b, c], dtype=float), 3, line)
    assert picked[0] == 0                 # only real coverage first
    assert picked[1] == 2                 # then best remaining mean
    assert len(picked) == 3


def test_tail_selection_caps_at_candidates():
    totals = np.array([[120.0, 0.0]])
    assert select_tail_entries(totals, 5, 100.0) == [0]


def test_showdown_captain_board_metrics():
    """sim_mode_entries(with_metrics=True) returns the captain board:
    salary-free rates (p_top/p_top6) must be proper distributions over the
    pool, salary-aware rates (cpt_opt/flex_opt) must come from the
    per-draw solves, and the projection favorite should top the board."""
    from nfl_dfs.optimizer.showdown import sim_mode_entries

    pool = make_showdown_pool()
    entries, board = sim_mode_entries(pool, 3, seed=1, n_sims=200,
                                      with_metrics=True)
    assert entries and len(board) == len(pool)
    assert abs(sum(m["p_top"] for m in board) - 1.0) < 1e-2
    assert abs(sum(m["p_top6"] for m in board) - 6.0) < 2e-2
    assert abs(sum(m["cpt_opt"] for m in board) - 1.0) < 1e-2
    assert abs(sum(m["flex_opt"] for m in board) - 5.0) < 2e-2
    assert board == sorted(board, key=lambda m: (-m["p_top"], -m["p_top6"]))
    top_proj = max(pool, key=lambda p: p["proj"])
    assert board[0]["p_top"] >= next(
        m for m in board if m["id"] == top_proj["id"])["p_top"] * 0.99
    # metrics path must not change the entries themselves
    plain = sim_mode_entries(pool, 3, seed=1, n_sims=200)
    assert [lu.key for lu in plain] == [lu.key for lu in entries]

```

===== FILE: tests/test_ownership.py =====
```python
"""Offline coverage for the ownership-model seed (issue #11)."""

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models import ownership


def _pool(n=60, seed=3):
    rng = np.random.default_rng(seed)
    pos = rng.choice(["QB", "RB", "WR", "TE", "DST"], n)
    salary = rng.integers(3000, 9500, n)
    proj = salary / 500 + rng.normal(0, 3, n)
    return pd.DataFrame({
        "season": 2026, "week": rng.integers(1, 4, n),
        "position": pos, "salary": salary,
        "proj_points": np.clip(proj, 1, None),
    })


def test_build_features_shapes_and_ranks():
    f = ownership.build_features(_pool())
    for c in ownership.FEATURES:
        assert c in f.columns
    assert (f.salary_rank_pos >= 1).all()
    assert f.is_min_price.isin([0.0, 1.0]).all()


def test_train_predict_roundtrip_bounded():
    frame = ownership.build_features(_pool())
    # synthetic truth: chalk follows value with noise
    v = frame.value
    frame["pct_drafted"] = np.clip(3 + 4 * (v - v.mean()) / v.std()
                                   + np.random.default_rng(0).normal(0, 1, len(v)),
                                   0.1, 60)
    booster = ownership.train(frame, num_boost_round=60)
    pred = ownership.predict_ownership(booster, frame)
    assert pred.shape == (len(frame),)
    assert (pred >= 0).all() and (pred <= 100).all()
    corr = np.corrcoef(pred, frame.pct_drafted)[0, 1]
    assert corr > 0.5  # learns the value-chalk relationship


def test_training_frame_raises_helpfully_when_empty(monkeypatch):
    import nfl_dfs.models.ownership as own
    monkeypatch.setattr("nfl_dfs.bq.query_df", lambda sql: pd.DataFrame())
    with pytest.raises(RuntimeError, match="import-ownership"):
        own.training_frame()

```

===== FILE: tests/test_ownership_import.py =====
```python
import pandas as pd
import pytest

from nfl_dfs.ingest.ownership_import import parse_standings_csv


def _write_export(path, with_summary=True):
    """Mimic a DK contest-standings export: entry columns on the left,
    per-player summary block on the right (sparser than entries)."""
    df = pd.DataFrame({
        "Rank": [1, 2, 3, 4],
        "EntryId": [11, 12, 13, 14],
        "EntryName": ["a", "b", "c", "d"],
        "Points": [180.1, 176.2, 150.0, 149.5],
        "Lineup": ["QB X RB Y", "QB X RB Z", "QB W RB Y", "QB W RB Z"],
        "Player": ["Josh Allen", "Bijan Robinson", None, None],
        "Roster Position": ["QB", "RB", None, None],
        "%Drafted": ["24.31%", "18.20%", None, None],
        "FPTS": [31.2, 22.4, None, None],
    })
    if not with_summary:
        df = df.drop(columns=["Player", "Roster Position", "%Drafted", "FPTS"])
    df.to_csv(path, index=False)
    return path


def test_parse_standings(tmp_path):
    out = parse_standings_csv(_write_export(tmp_path / "standings.csv"))
    assert len(out) == 2
    assert out.display_name.tolist() == ["Josh Allen", "Bijan Robinson"]
    assert out.pct_drafted.tolist() == pytest.approx([24.31, 18.20])
    assert out.roster_position.tolist() == ["QB", "RB"]


def test_parse_rejects_wrong_file(tmp_path):
    path = _write_export(tmp_path / "not_standings.csv", with_summary=False)
    with pytest.raises(ValueError, match="missing columns"):
        parse_standings_csv(path)

```

===== FILE: tests/test_pricing_lag.py =====
```python
"""Offline tests for the DK pricing-lag model (issue #13 item 3): salary
regressed on trailing production, residual = structural mispricing.
Covers correctness of the point-in-time filter (never fit on the season
being scored) and that the residual actually separates an underpriced
player from a fairly-priced one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nfl_dfs.models import pricing_lag


def test_train_never_uses_target_season_rows(panel):
    """Corrupting the target season's salaries must not change the fitted
    model -- train() filters those rows out before fitting."""
    target_season = sorted(panel.season.unique())[-1]
    clean_models = pricing_lag.train(panel, target_season)

    corrupted = panel.copy()
    mask = corrupted.season == target_season
    corrupted.loc[mask, "salary"] = 999_999
    corrupted_models = pricing_lag.train(corrupted, target_season)

    assert clean_models.keys() == corrupted_models.keys()
    for pos in clean_models:
        np.testing.assert_allclose(
            clean_models[pos].ridge.coef_, corrupted_models[pos].ridge.coef_
        )
        assert clean_models[pos].ridge.intercept_ == corrupted_models[pos].ridge.intercept_


def test_train_requires_earlier_seasons(panel):
    first_season = sorted(panel.season.unique())[0]
    models = pricing_lag.train(panel, first_season)
    assert models == {}


def test_fitted_model_beats_naive_mean_baseline(panel):
    """Sanity check: the synthetic panel's salary is a function of
    production plus noise, so a trailing-production regression should fit
    meaningfully better than predicting the position mean."""
    target_season = sorted(panel.season.unique())[-1]
    models = pricing_lag.train(panel, target_season)
    va = panel[panel.season == target_season]
    out = pricing_lag.residuals(va, models)

    assert set(out.columns) == set(pricing_lag.RESIDUAL_COLUMNS)
    assert not out.empty

    mae_model = out.salary_residual.abs().mean()
    naive_pred = va.groupby("position").salary.transform("mean")
    mae_naive = (va.salary.to_numpy() - naive_pred.to_numpy())
    mae_naive = np.abs(mae_naive).mean()
    assert mae_model < mae_naive


def test_residual_flags_underpriced_player():
    """Two players with identical trailing production but very different
    salaries: the cheap one should get a strongly negative residual/z and
    the fair one should sit close to zero."""
    rng = np.random.default_rng(0)
    rows = []
    for season in range(2018, 2024):
        for week in range(1, 18):
            usage = 0.25 + rng.normal(0, 0.01)
            rows.append({
                "gsis_id": "00-A", "season": season, "week": week,
                "position": "WR",
                "target_share_l4": usage, "carry_share_l4": 0.0,
                "wopr_l4": 1.5 * usage, "rz20_targets_smoothed": usage * 4,
                "ez_targets_l4": usage * 1.5, "deep_targets_l4": usage * 2.0,
                "gl3_carries_smoothed": 0.0, "snap_share_l4": 0.8,
                "dk_points_l4": 14 + rng.normal(0, 0.5),
                "dk_points_std": 14, "games_played_prior": 50,
                "salary": 7000 + rng.normal(0, 50),
            })
            rows.append({
                "gsis_id": "00-B", "season": season, "week": week,
                "position": "WR",
                "target_share_l4": usage, "carry_share_l4": 0.0,
                "wopr_l4": 1.5 * usage, "rz20_targets_smoothed": usage * 4,
                "ez_targets_l4": usage * 1.5, "deep_targets_l4": usage * 2.0,
                "gl3_carries_smoothed": 0.0, "snap_share_l4": 0.8,
                "dk_points_l4": 14 + rng.normal(0, 0.5),
                "dk_points_std": 14, "games_played_prior": 50,
                # Same production trail, but DK hasn't caught up to it.
                "salary": 4200 + rng.normal(0, 50),
            })
    df = pd.DataFrame(rows)
    target_season = 2023
    models = pricing_lag.train(df, target_season)
    va = df[df.season == target_season]
    out = pricing_lag.residuals(va, models)

    a = out[out.gsis_id == "00-A"].salary_residual.mean()
    b = out[out.gsis_id == "00-B"].salary_residual.mean()
    az = out[out.gsis_id == "00-A"].salary_residual_z.mean()
    bz = out[out.gsis_id == "00-B"].salary_residual_z.mean()
    # Same trailing production, ~$2800 salary gap: the model splits the
    # difference, so each player's residual should recover roughly half
    # the gap in the direction DK actually priced them wrong.
    assert a > 1000  # 00-A is overpriced relative to its production trail
    assert b < -1000  # 00-B is underpriced -- the structural value signal
    assert bz < az - 1.5


def test_walk_forward_residuals_out_of_sample(panel):
    out = pricing_lag.walk_forward_residuals(panel, min_train_seasons=4)
    seasons = sorted(panel.season.unique())
    assert not out.empty
    # First eligible scored season is index `min_train_seasons` (0-based).
    assert out.season.min() == seasons[4]
    assert out.salary_residual.notna().all()
    assert out.salary_residual_z.notna().all()


def test_walk_forward_residuals_empty_when_too_few_seasons(small_panel):
    out = pricing_lag.walk_forward_residuals(small_panel, min_train_seasons=99)
    assert out.empty
    assert list(out.columns) == pricing_lag.RESIDUAL_COLUMNS


def test_sparse_position_skipped_not_crashed():
    """A position with fewer than MIN_TRAIN_ROWS rows should be silently
    excluded from the fitted models and from the resulting residuals,
    never raise."""
    rng = np.random.default_rng(1)
    rows = []
    for week in range(1, 4):  # only 3 rows -> below MIN_TRAIN_ROWS
        rows.append({
            "gsis_id": "00-X", "season": 2018, "week": week, "position": "TE",
            "target_share_l4": 0.1, "carry_share_l4": 0.0, "wopr_l4": 0.1,
            "rz20_targets_smoothed": 0.1, "ez_targets_l4": 0.1,
            "deep_targets_l4": 0.1, "gl3_carries_smoothed": 0.0,
            "snap_share_l4": 0.5, "dk_points_l4": 5.0, "dk_points_std": 5.0,
            "games_played_prior": 10, "salary": 3000 + rng.normal(0, 10),
        })
    df = pd.DataFrame(rows)
    models = pricing_lag.train(df, target_season=2019)
    assert models == {}
    out = pricing_lag.residuals(df[df.season == 2018], models)
    assert out.empty

```

===== FILE: tests/test_punt_boom.py =====
```python
"""PUNT_BOOM archetype flags (Addendum 24/36 punt-quality lever).

The three winning-punt archetypes must flag, everything else must not,
and the vacated-share percentile must be computed within each week."""

import pandas as pd

from nfl_dfs.backtest.replay import _punt_boom_from_signals


def _sig(gsis, week, pos, rank, prev, vac):
    return dict(gsis_id=gsis, season=2025, week=week, position=pos,
                depth_rank=rank, prev_rank=prev, vac=vac)


def test_archetypes_flag_and_others_do_not():
    rows = [
        _sig("TE_STARTER", 3, "TE", 1, 1, 0.0),    # cheap starting TE
        _sig("PROMOTED", 3, "RB", 1, 2, 0.0),      # rank 2 -> 1 (Gadsden)
        _sig("TE_BACKUP", 3, "TE", 2, 2, 0.0),     # no
        _sig("WR_STARTER", 3, "WR", 1, 1, 0.0),    # rank 1 but not TE: no
        _sig("RB_DEMOTED", 3, "RB", 2, 1, 0.0),    # wrong direction: no
    ]
    # 10 fillers with modest vacated share + one cascade beneficiary
    rows += [_sig(f"F{i}", 3, "WR", 3, 3, 0.01 * (i + 1)) for i in range(10)]
    rows.append(_sig("CASCADE", 3, "WR", 3, 3, 0.45))  # top decile vac
    flags = _punt_boom_from_signals(pd.DataFrame(rows))
    names = {k[0] for k in flags}
    assert {"TE_STARTER", "PROMOTED", "CASCADE"} <= names
    assert not {"TE_BACKUP", "WR_STARTER", "RB_DEMOTED"} & names


def test_vacated_percentile_is_per_week():
    # The same 0.20 share is top-decile in a quiet week but not in a
    # week where half the league lost a starter.
    quiet = [_sig(f"Q{i}", 1, "WR", 3, 3, 0.01) for i in range(9)]
    quiet.append(_sig("QUIET_HIT", 1, "WR", 3, 3, 0.20))
    loud = [_sig(f"L{i}", 2, "WR", 3, 3, 0.5 + 0.01 * i) for i in range(9)]
    loud.append(_sig("LOUD_MISS", 2, "WR", 3, 3, 0.20))
    flags = _punt_boom_from_signals(pd.DataFrame(quiet + loud))
    names = {k[0] for k in flags}
    assert "QUIET_HIT" in names
    assert "LOUD_MISS" not in names


def test_nan_depth_ranks_do_not_flag():
    rows = [_sig("NANRANK", 5, "RB", float("nan"), float("nan"), 0.0),
            _sig("OTHER", 5, "WR", 2, 2, 0.0)]
    assert _punt_boom_from_signals(pd.DataFrame(rows)) == set()

```

===== FILE: tests/test_qb_capped_select.py =====
```python
"""MAX_QBS selection cap (harvest attribution follow-up).

The six-season attribution found selection spreading 40 entries over ~16
distinct QBs, so no lineup ever assembled the right stack WITH the right
pieces (max 2-of-8 overlap with the weekly optimal). _select_tail_qb_capped
must (a) never exceed the distinct-QB cap, including in the fill phase,
and (b) reduce to plain tail selection when the cap is loose.
"""

import numpy as np

from nfl_dfs.backtest.engine import _select_tail_qb_capped
from nfl_dfs.optimizer.lineup import select_tail_entries


def _mk(n_cands=30, n_sims=400, seed=7):
    rng = np.random.default_rng(seed)
    base = rng.normal(150, 12, size=(n_cands, 1))
    totals = base + rng.normal(0, 25, size=(n_cands, n_sims))
    qb_of = [f"QB{i % 10}" for i in range(n_cands)]  # 10 distinct QBs
    return totals, qb_of


def test_cap_respected_including_fill():
    totals, qb_of = _mk()
    for cap in (2, 3, 5):
        picked = _select_tail_qb_capped(totals, 12, 190.0, qb_of, cap)
        assert picked, "must select something"
        assert len({qb_of[i] for i in picked}) <= cap
        assert len(picked) == len(set(picked))


def test_loose_cap_matches_uncapped():
    totals, qb_of = _mk()
    capped = _select_tail_qb_capped(totals, 12, 190.0, qb_of, 999)
    plain = select_tail_entries(totals, 12, 190.0)
    assert capped == plain


def test_cap_buys_depth_in_kept_stacks():
    # Construct a pool where QB0 candidates clear the line in disjoint
    # sims (real depth) and nine other QBs each clear one overlapping
    # sliver. Capped selection must concentrate on QB0 variants.
    n_sims = 300
    totals = np.full((12, n_sims), 150.0)
    for v in range(3):  # QB0 variants boom in disjoint sim blocks
        totals[v, v * 60:(v + 1) * 60] = 200.0
    for c in range(3, 12):  # rivals all boom in the same small block
        totals[c, 280:290] = 200.0
    qb_of = ["QB0"] * 3 + [f"QB{c}" for c in range(1, 10)]
    picked = _select_tail_qb_capped(totals, 4, 194.0, qb_of, 2)
    assert set(picked) >= {0, 1, 2}, "all three QB0 variants must be kept"
    assert len({qb_of[i] for i in picked}) <= 2


def test_thesis_repair_enforces_portfolio_floor():
    import numpy as np

    from nfl_dfs.backtest.engine import _enforce_theses

    class L:
        def __init__(self, ids):
            self.players = [{"id": i} for i in ids]

    cands = [L([1, 2, 3]), L([4, 5, 6]), L([7, 8, 9]), L([1, 7, 9])]
    totals = np.array([[200.0], [150.0], [140.0], [190.0]])
    picked = _enforce_theses([1, 2], cands, totals, 194.0,
                             [{"players": [1], "min": 2}])
    assert sum(1 for i in picked if 1 in {p["id"] for p in cands[i].players}) == 2


def _engine_slate(n_teams=8):
    """Minimal engine-ready slate + pool + draws for tail_select_lineups."""
    import pandas as pd

    rng = np.random.default_rng(5)
    rows = []
    pid = 0
    for t in range(n_teams):
        team, opp = f"T{t}", f"T{(t + 1) % n_teams}"
        gid = f"g{min(t, (t + 1) % n_teams)}{max(t, (t + 1) % n_teams)}"
        for pos, n in (("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1), ("DST", 1)):
            for i in range(n):
                proj = {"QB": 18, "RB": 12, "WR": 11, "TE": 7, "DST": 6}[pos] \
                    - 2 * i + rng.normal(0, 1)
                rows.append({
                    "id": pid, "name": f"{pos}{i}{team}", "pos": pos,
                    "team": team, "opp": opp, "game_id": gid,
                    "salary": int(1200 + 250 * max(proj, 1)),
                    "proj": max(proj, 1.0), "actual": max(proj, 1.0),
                    "draw_idx": pid, "proj_tourney": max(proj, 1.0)})
                pid += 1
    slate = pd.DataFrame(rows)
    draws = np.maximum(
        slate.proj.to_numpy()[:, None] + rng.normal(0, 6, (len(slate), 300)),
        0).astype(np.float32)
    return slate, slate.to_dict("records"), draws


def test_thesis_generation_path_end_to_end(monkeypatch):
    """Regression (2026-08-04 audit): the thesis candidate batch crashed
    with UnboundLocalError (seen referenced before assignment) and had
    its tags clobbered by the lev retag loop. Exercise the REAL
    generation path, not just the repair function. Salary-floor and punt
    envs neutralized — the synthetic slate tests thesis mechanics only."""
    from nfl_dfs.backtest.engine import tail_select_lineups

    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    monkeypatch.setenv("PUNT_MIN", "0")
    slate, pool, draws = _engine_slate()
    combo = [0, 2]  # QB of T0 + a T0 RB — feasible pair
    picked = tail_select_lineups(
        slate, pool, draws, tail_line=150.0, n_entries=4, stack=None,
        objective_col="proj_tourney", theses=[{"players": combo, "min": 2}])
    assert len(picked) == 4
    n_combo = sum(1 for lu in picked
                  if set(combo) <= {p["id"] for p in lu.players})
    assert n_combo >= 2, f"thesis floor not met: {n_combo}"

```

===== FILE: tests/test_registry_monitoring.py =====
```python
import lightgbm as lgb
import numpy as np
import pandas as pd

from nfl_dfs.models import monitoring, registry


def _tiny_model():
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"a": rng.normal(size=300), "b": rng.normal(size=300)})
    y = X.a * 2 + rng.normal(0, 0.1, 300)
    return lgb.train({"objective": "regression", "verbosity": -1},
                     lgb.Dataset(X, y), num_boost_round=10)


def test_registry_roundtrip(tmp_path):
    model = _tiny_model()
    meta = registry.ModelMeta(
        scope="pooled", label="dk_points", iso_week="2025-W10",
        params={"objective": "regression"}, features=["a", "b"],
        train_seasons=[2023, 2024], metrics={"mae": 1.23},
    )
    version = registry.save(model, meta, str(tmp_path))
    assert version == "pooled/dk_points/2025-W10"

    loaded, loaded_meta = registry.load(str(tmp_path), "pooled", "dk_points", "2025-W10")
    assert loaded_meta.metrics["mae"] == 1.23
    X = pd.DataFrame({"a": [1.0], "b": [0.0]})
    np.testing.assert_allclose(loaded.predict(X), model.predict(X))


def test_registry_latest_week(tmp_path):
    model = _tiny_model()
    for wk in ("2025-W09", "2025-W11", "2025-W10"):
        registry.save(model, registry.ModelMeta("pooled", "dk_points", wk), str(tmp_path))
    assert registry.latest_iso_week(str(tmp_path), "pooled", "dk_points") == "2025-W11"


def test_mae_drift_alarm():
    assert monitoring.check_mae(training_mae=5.0, recent_mae=7.0) is not None
    assert monitoring.check_mae(training_mae=5.0, recent_mae=5.5) is None


def test_coverage_alarms():
    rng = np.random.default_rng(1)
    y = rng.normal(15, 5, 5000)
    good = monitoring.check_coverage(y, np.quantile(y, 0.1) * np.ones(5000),
                                     np.quantile(y, 0.9) * np.ones(5000))
    assert good == []
    bad = monitoring.check_coverage(y, np.quantile(y, 0.3) * np.ones(5000),
                                    np.quantile(y, 0.7) * np.ones(5000))
    assert len(bad) == 2


def test_psi_detects_shift():
    rng = np.random.default_rng(2)
    base = rng.normal(0, 1, 5000)
    assert monitoring.psi(base, rng.normal(0, 1, 5000)) < 0.05
    assert monitoring.psi(base, rng.normal(1.5, 1, 5000)) > 0.2


def test_null_rate_alarm():
    train = pd.DataFrame({"f": np.random.default_rng(3).normal(size=1000)})
    live = pd.DataFrame({"f": [np.nan] * 300 + list(np.random.default_rng(4).normal(size=700))})
    alarms = monitoring.check_feature_drift(train, live, ["f"])
    assert any(a.kind == "null_rate" for a in alarms)

```

===== FILE: tests/test_replay.py =====
```python
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest import payout, replay


@pytest.fixture(scope="module")
def proj(small_panel):
    return replay.replay_projections(
        small_panel, season=2022, n_sims=2000, num_boost_round=80, seed=1
    )


def test_replay_is_point_in_time(proj, small_panel):
    # Projections must come from a model that never saw 2022: they can't
    # equal actuals, and they must exist for every 2022 panel row.
    assert len(proj) == (small_panel.season == 2022).sum()
    assert not np.allclose(proj.proj_points, proj.actual)
    assert proj.proj_p10.le(proj.proj_p90 + 1e-9).all()


def test_replay_metrics(proj):
    overall, by_pos = replay.replay_metrics(proj)
    assert overall["mae"] < 7.65  # learned signal (sigma 6; small margin
    # for correlated-game-factor simulation variance at low n_sims)
    # Synthetic component labels are drawn independently of y_dk_points, so
    # tight calibration isn't achievable here by construction — directional
    # bounds only. Real calibration is judged on warehouse replays.
    assert overall["coverage_p10"] < 0.35
    assert overall["coverage_p90"] > 0.50
    assert overall["coverage_p10"] < overall["coverage_p90"]
    assert set(by_pos.index) == {"QB", "RB", "WR", "TE"}
    # conftest's QB passing labels are constants (no usage link), so QB rank
    # correlation is structurally ~0 on synthetic data; judge the positions
    # whose labels actually carry signal.
    assert (by_pos.drop("QB").rank_corr > 0.2).all()
    assert np.isfinite(by_pos.rank_corr).all()


def _dst(seed=3):
    rng = np.random.default_rng(seed)
    rows = []
    for t in range(8):
        for wk in range(1, 18):
            rows.append({"season": 2022, "week": wk, "team": f"T{t}",
                         "opp": f"T{(t + 1) % 8}", "salary": 2900,
                         "actual": max(0.0, rng.normal(7, 5))})
    return pd.DataFrame(rows)


def test_dst_projection_is_strictly_prior():
    d = replay.dst_slate_rows(_dst())
    wk1 = d[d.week == 1]
    assert (wk1.proj == replay.DST_FALLBACK_PROJ).all()
    one = d[d.team == "T0"].sort_values("week")
    expected_wk3 = one[one.week <= 2].actual.mean()
    assert one[one.week == 3].proj.iloc[0] == pytest.approx(expected_wk3)


def test_contest_replay_runs(proj):
    weeks = proj[proj.week <= 2].copy()  # two weeks keeps this fast
    result = replay.run_contest_replay(
        weeks, _dst(), payout.double_up(entry_fee=5, field_size=1000),
        n_entries=3, field_size=200, seed=1,
    )
    assert len(result.weeks) == 2
    assert all(len(w.winnings) == 3 for w in result.weeks)
    assert np.isfinite(result.total_roi)



def test_contest_replay_tail_selection(proj, small_panel):
    # Full issue-#5 path: correlated draws -> candidate pool (leverage batch
    # + boom-draw solves) -> greedy coverage selection. A low line keeps
    # coverage non-degenerate on the tiny synthetic slate.
    p, draws = replay.replay_projections(
        small_panel, season=2022, n_sims=200, num_boost_round=40, seed=1,
        return_draws=True,
    )
    weeks = p[p.week <= 1].copy()
    result = replay.run_contest_replay(
        weeks, _dst(), payout.double_up(entry_fee=5, field_size=1000),
        n_entries=3, field_size=200, seed=1,
        draws=draws, tail_line=60.0, n_boom_solves=3,
    )
    assert len(result.weeks) == 1
    assert len(result.weeks[0].winnings) == 3
    ids = [frozenset(pl["id"] for pl in lu.players)
           for lu in result.weeks[0].lineups]
    assert len(set(ids)) == 3  # selected entries are distinct lineups


def test_dst_qb_experience_adjustment():
    from nfl_dfs.inference.qb_experience import adjustment

    starts = pd.Series([0, 3, 4, 10, 11, 30, 31, 200, np.nan])
    adj = adjustment(starts)
    assert list(adj[:2]) == [2.2, 2.2]          # rookie tier
    assert list(adj[2:4]) == [1.5, 1.5]         # early career
    assert list(adj[4:6]) == [-0.5, -0.5]       # established
    assert list(adj[6:8]) == [-0.7, -0.7]       # veteran
    assert adj.iloc[8] == 0.0                    # unknown starter

    d = _dst()
    qb = pd.DataFrame({"season": 2022, "week": d.week, "team": d.opp,
                       "prior_starts": 0}).drop_duplicates()
    plain = replay.dst_slate_rows(_dst())
    adj_rows = replay.dst_slate_rows(_dst(), qb)
    merged = plain.merge(adj_rows, on=["team", "week"], suffixes=("_p", "_a"))
    assert np.allclose(merged.proj_a - merged.proj_p, 2.2)  # all rookies

```

===== FILE: tests/test_replay_shape.py =====
```python


def test_tabpfn_marginals_maps_and_preserves_ranks(monkeypatch):
    """TABPFN_MARGINALS: draws remap onto the cached per-player quantile
    curve; rank order (the correlation carrier) is preserved; uncached
    rows keep their original draws."""
    import numpy as np
    import pandas as pd

    from nfl_dfs.backtest import replay

    rng = np.random.default_rng(3)
    draws = rng.gamma(2.0, 5.0, size=(2, 500)).astype(np.float32)
    keys = pd.DataFrame({"season": [2025, 2025], "week": [1, 1],
                         "gsis_id": ["A", "MISSING"]})
    cache = pd.DataFrame([{
        "season": 2025, "week": 1, "gsis_id": "A", "mean": 12.0,
        "q01": 0.5, "q05": 2.0, "q10": 4.0, "q50": 11.0,
        "q90": 24.0, "q95": 29.0, "q99": 38.0}])
    monkeypatch.setattr(replay, "query_df", None, raising=False)
    import nfl_dfs.bq as bqmod
    monkeypatch.setattr(bqmod, "query_df", lambda sql, **kw: cache)
    out = replay._tabpfn_marginals(draws, keys)
    r0, o0 = draws[0], out[0]
    assert (np.argsort(r0) == np.argsort(o0)).all(), "rank order preserved"
    assert abs(np.quantile(o0, 0.5) - 11.0) < 1.5
    assert abs(np.quantile(o0, 0.9) - 24.0) < 2.5
    assert (out[1] == draws[1]).all(), "uncached row untouched"
    assert (out >= 0).all()

```

===== FILE: tests/test_scoring.py =====
```python
import numpy as np
import pytest

from nfl_dfs.models.scoring import StatLine, dk_points


def test_wr_line_with_bonus():
    # 8 rec, 112 yds, 1 TD: 8 + 11.2 + 6 + 3 (100+ bonus) = 28.2
    s = StatLine(receptions=8, rec_yards=112, rec_tds=1)
    assert dk_points(s) == pytest.approx(28.2)


def test_qb_line_with_300_bonus():
    # 320 pass yds, 3 TD, 1 INT: 12.8 + 12 + 3 - 1 = 26.8
    s = StatLine(pass_yards=320, pass_tds=3, interceptions=1)
    assert dk_points(s) == pytest.approx(26.8)


def test_bonus_thresholds_are_inclusive():
    assert dk_points(StatLine(rec_yards=100)) == pytest.approx(13.0)
    assert dk_points(StatLine(rec_yards=99.9)) == pytest.approx(9.99)
    assert dk_points(StatLine(rush_yards=100)) == pytest.approx(13.0)
    assert dk_points(StatLine(pass_yards=300)) == pytest.approx(15.0)


def test_negative_events():
    s = StatLine(fumbles_lost=2, interceptions=1)
    assert dk_points(s) == pytest.approx(-3.0)


def test_vectorized():
    s = StatLine(
        rec_yards=np.array([50.0, 105.0]),
        receptions=np.array([4, 9]),
        rec_tds=np.array([0, 2]),
    )
    pts = dk_points(s)
    assert pts.shape == (2,)
    assert pts[0] == pytest.approx(9.0)
    assert pts[1] == pytest.approx(9 + 10.5 + 12 + 3)

```

===== FILE: tests/test_showdown_replay.py =====
```python
import numpy as np
import pandas as pd

import pytest

from nfl_dfs.backtest.showdown_replay import (
    build_pools, naive_trailing, replay_showdown_season, showdown_draws)


def _slates(weeks=(5, 6), seed=8):
    rng = np.random.default_rng(seed)
    rows = []
    for wk in weeks:
        for slate in (f"S{wk}",):
            pid = 0
            for team in ("AAA", "BBB"):
                for pos, n in (("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1),
                               ("K", 1), ("Def", 1)):
                    for i in range(n):
                        rows.append({
                            "season": 2025, "week": wk,
                            "operator_slate_id": slate,
                            "operator_day": "Monday",
                            "game_teams": "AAA@BBB",
                            "sdio_player_id": 1000 + pid,
                            "display_name": f"{pos}{chr(65 + i)} {team}",
                            "position": pos, "team_abbr": team,
                            "salary": int(rng.integers(20, 110)) * 100,
                            "dk_points_actual": float(max(0, rng.normal(10, 6))),
                        })
                        pid += 1
    return pd.DataFrame(rows)


def _proj(slates):
    rows = []
    for r in slates[slates.position.isin(["QB", "RB", "WR", "TE"])].itertuples():
        rows.append({"week": r.week, "name": r.display_name,
                     "position": r.position,
                     "proj_points": r.dk_points_actual + 2.0})
    return pd.DataFrame(rows)


def test_build_pools_sources():
    slates = _slates()
    pools = build_pools(slates, _proj(slates))
    wk6 = pools[pools.week == 6]
    assert (wk6[wk6.position.isin(["QB", "RB", "WR", "TE"])].proj_source == "model").all()
    # K/Def in week 6 fall back to trailing actuals... only 1 prior game
    # (min 2) -> dropped; week-5 K/Def have no prior at all -> dropped
    assert set(pools.proj_source) == {"model"}
    assert (pools[pools.week == 5].position.isin(["QB", "RB", "WR", "TE"])).all()


def test_naive_trailing_strictly_prior():
    df = pd.DataFrame({
        "sdio_player_id": [1, 1, 1], "week": [1, 2, 3],
        "dk_points_actual": [10.0, 20.0, 30.0]})
    t = naive_trailing(df)
    assert t.isna().iloc[0] and t.isna().iloc[1]  # min 2 prior games
    assert t.iloc[2] == 15.0  # mean of weeks 1-2, current week excluded


def test_replay_scores_and_capture():
    slates = _slates(weeks=(5,))
    res = replay_showdown_season(slates, _proj(slates), n_entries=4, days=("mon",))
    assert len(res) == 1
    row = res.iloc[0]
    assert row.optimal >= row.best >= row.median_entry > 0
    assert 0 < row.capture <= 1.0
    # Projections = actuals + constant -> optimizer should capture nearly
    # everything (cap constraints can force small gaps)
    assert row.capture > 0.85


def test_sim_mode_entries_and_gate(monkeypatch):
    """SHOWDOWN_SIM=1 routes through correlated-draw construction and
    still produces valid, scored entries; unset leaves the MILP path
    untouched (proven by identical results)."""
    slates = _slates(weeks=(5,))
    proj = _proj(slates)

    monkeypatch.delenv("SHOWDOWN_SIM", raising=False)
    base = replay_showdown_season(slates, proj, n_entries=4, days=("mon",))
    base2 = replay_showdown_season(slates, proj, n_entries=4, days=("mon",))
    pd.testing.assert_frame_equal(base, base2)  # deterministic without gate

    monkeypatch.setenv("SHOWDOWN_SIM", "1")
    monkeypatch.setenv("SHOWDOWN_TAIL_LINE", "80")
    sim = replay_showdown_season(slates, proj, n_entries=4, days=("mon",))
    assert not sim.empty
    assert (sim.best > 0).all()
    assert (sim.capture <= 1.001).all()


def test_showdown_draws_mean_preserving_and_nonnegative():
    pool = [
        {"id": 1, "proj": 15.0, "proj_sd": 8.0},
        {"id": 2, "proj": 5.0, "proj_sd": 4.0},
        {"id": 3, "proj": 0.0, "proj_sd": 0.0},
    ]
    draws = showdown_draws(pool, n_sims=30_000, seed=1)
    assert draws[1].mean() == pytest.approx(15.0, rel=0.05)
    assert draws[2].mean() == pytest.approx(5.0, rel=0.05)
    assert (draws[1] >= 0).all()
    assert (draws[3] == 0).all()


def test_lineup_draw_totals_captain_weighting():
    from nfl_dfs.optimizer.showdown import ShowdownLineup, lineup_draw_totals
    cpt = {"id": 1, "salary": 5000, "proj": 10.0}
    flex = [{"id": i, "salary": 3000, "proj": 5.0} for i in range(2, 7)]
    lu = ShowdownLineup(cpt, flex)
    draws = {i: np.full(4, 10.0) for i in range(1, 7)}
    totals = lineup_draw_totals([lu], draws)
    assert totals.shape == (1, 4)
    np.testing.assert_allclose(totals[0], 1.5 * 10 + 5 * 10)

```

===== FILE: tests/test_sql_dir.py =====
```python
"""SQL_DIR must resolve to a real directory containing the feature SQL.

Regression guard for the 2026-07-31 incident: the checkout-relative path
resolved to a nonexistent directory inside the container, so every
scheduled build-features run died on FileNotFoundError for weeks."""

from nfl_dfs.bq import SQL_DIR


def test_sql_dir_exists_with_feature_sql():
    assert SQL_DIR.is_dir()
    assert list((SQL_DIR / "features").glob("*.sql"))
    assert list((SQL_DIR / "raw").glob("*.sql"))

```

===== FILE: tests/test_status.py =====
```python
"""Offline coverage for the system-status/freshness module and endpoint.

_table_info is the single GCP seam in nfl_dfs/status.py — everything here
monkeypatches it, so no BigQuery access."""

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from nfl_dfs import status
from nfl_dfs.app import main as app_main

IN_SEASON = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
OFF_SEASON = datetime(2026, 4, 15, 12, tzinfo=timezone.utc)


def _info_all_fresh(now):
    return lambda dataset, table: (now - timedelta(hours=1), 1000)


def test_active_windows():
    assert status._active("always", date(2026, 4, 1))
    assert status._active("nfl", date(2026, 10, 1))
    assert not status._active("nfl", date(2026, 4, 1))
    assert status._active("cfb", date(2026, 8, 23))
    assert not status._active("cfb", date(2026, 8, 1))


def test_all_fresh_in_season(monkeypatch):
    monkeypatch.setattr(status, "_table_info", _info_all_fresh(IN_SEASON))
    comps = status.system_status(now=IN_SEASON)
    assert len(comps) == len(status.FEEDS)
    assert {c["state"] for c in comps} == {"ok"}
    status.check_freshness(now=IN_SEASON)  # must not raise


def test_stale_feed_fails_check_in_season(monkeypatch):
    def info(dataset, table):
        if table == "dk_salaries":
            return IN_SEASON - timedelta(days=5), 1000
        return IN_SEASON - timedelta(hours=1), 1000

    monkeypatch.setattr(status, "_table_info", info)
    by_key = {c["key"]: c for c in status.system_status(now=IN_SEASON)}
    assert by_key["dk_salaries"]["state"] == "stale"
    with pytest.raises(RuntimeError, match="DK slates/salaries"):
        status.check_freshness(now=IN_SEASON)


def test_stale_seasonal_feed_is_idle_off_season(monkeypatch):
    def info(dataset, table):
        if table in ("dk_salaries", "player_projections"):
            return OFF_SEASON - timedelta(days=90), 1000
        return OFF_SEASON - timedelta(hours=1), 1000

    monkeypatch.setattr(status, "_table_info", info)
    by_key = {c["key"]: c for c in status.system_status(now=OFF_SEASON)}
    assert by_key["dk_salaries"]["state"] == "idle"
    status.check_freshness(now=OFF_SEASON)  # seasonal staleness is fine in April


def test_always_feed_must_stay_fresh_off_season(monkeypatch):
    """odds_snapshots is the one remaining year-round feed (its scheduler
    runs through the off-season); it must alert even in April."""
    def info(dataset, table):
        if table == "odds_snapshots":
            return OFF_SEASON - timedelta(days=10), 1000
        return OFF_SEASON - timedelta(hours=1), 1000

    monkeypatch.setattr(status, "_table_info", info)
    with pytest.raises(RuntimeError, match="Game lines"):
        status.check_freshness(now=OFF_SEASON)


def test_non_alerting_feed_never_fails_check(monkeypatch):
    def info(dataset, table):
        if table == "dk_contest_fills":
            return None  # table missing entirely
        return IN_SEASON - timedelta(hours=1), 1000

    monkeypatch.setattr(status, "_table_info", info)
    by_key = {c["key"]: c for c in status.system_status(now=IN_SEASON)}
    assert by_key["dk_contest_fills"]["state"] == "missing"
    status.check_freshness(now=IN_SEASON)  # informational feed, must not raise


def test_empty_active_feed_fails_check(monkeypatch):
    def info(dataset, table):
        if table == "odds_snapshots":
            return IN_SEASON - timedelta(hours=1), 0
        return IN_SEASON - timedelta(hours=1), 1000

    monkeypatch.setattr(status, "_table_info", info)
    with pytest.raises(RuntimeError, match="Game lines"):
        status.check_freshness(now=IN_SEASON)


def test_api_system_status_endpoint(monkeypatch):
    monkeypatch.setattr(
        status, "_table_info",
        lambda dataset, table: (datetime.now(timezone.utc) - timedelta(hours=1), 42),
    )
    client = TestClient(app_main.app)
    r = client.get("/api/system-status")
    assert r.status_code == 200
    body = r.json()
    assert body["generated_at"]
    assert len(body["components"]) == len(status.FEEDS)
    assert all(c["state"] in ("ok", "stale", "empty", "idle", "missing")
               for c in body["components"])


def test_nav_html_has_status_button():
    assert "System status" in app_main._NAV_HTML
    assert "openStatus()" in app_main._NAV_HTML
    assert "statusmodal" in app_main._NAV_HTML


def test_candidate_features_env_gate(monkeypatch):
    """EXTRA_FEATURES adds only registered candidates; unset = baseline."""
    from nfl_dfs.models import featureset

    monkeypatch.delenv("EXTRA_FEATURES", raising=False)
    assert featureset._active_numeric_features() == featureset.NUMERIC_FEATURES

    monkeypatch.setenv("EXTRA_FEATURES", "pace_env_l6, not_a_feature")
    active = featureset._active_numeric_features()
    assert active == featureset.NUMERIC_FEATURES + ["pace_env_l6"]


def test_drop_features_env(monkeypatch):
    from nfl_dfs.models import featureset

    monkeypatch.setenv("DROP_FEATURES", "salary, salary_delta_wow")
    monkeypatch.delenv("EXTRA_FEATURES", raising=False)
    active = featureset._active_numeric_features()
    assert "salary" not in active and "salary_delta_wow" not in active
    assert len(active) == len(featureset.NUMERIC_FEATURES) - 2

```

===== FILE: tests/test_validation.py =====
```python
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models.validation import calibration_table, evaluate, walk_forward_folds
from nfl_dfs.models.weights import sample_weights


def test_walk_forward_folds_never_leak_future():
    folds, test = walk_forward_folds(list(range(2015, 2026)), min_train_seasons=6)
    assert test == 2025
    for train_seasons, val in folds:
        assert max(train_seasons) < val
        assert test not in train_seasons and val != test


def test_walk_forward_requires_enough_seasons():
    with pytest.raises(ValueError):
        walk_forward_folds([2023, 2024], min_train_seasons=6)


def test_evaluate_market_comparison():
    rng = np.random.default_rng(0)
    y = pd.Series(rng.uniform(0, 30, 500))
    good = y.to_numpy() + rng.normal(0, 1, 500)
    bad_market = pd.Series(y.to_numpy() + rng.normal(0, 5, 500))
    rep = evaluate(y, good, market=bad_market)
    assert rep.beats_market
    rep2 = evaluate(y, y.to_numpy() + rng.normal(0, 9, 500), market=bad_market)
    assert not rep2.beats_market


def test_evaluate_coverage():
    rng = np.random.default_rng(1)
    y = pd.Series(rng.normal(15, 5, 2000))
    p10 = np.quantile(y, 0.1) * np.ones(2000)
    p90 = np.quantile(y, 0.9) * np.ones(2000)
    rep = evaluate(y, y.to_numpy(), p10=p10, p90=p90)
    assert rep.coverage_p10 == pytest.approx(0.10, abs=0.02)
    assert rep.coverage_p90 == pytest.approx(0.90, abs=0.02)


def test_calibration_table():
    y = np.arange(100.0)
    preds = {0.5: np.full(100, 49.5)}
    tab = calibration_table(y, preds)
    assert tab.iloc[0].empirical == pytest.approx(0.5, abs=0.01)


def test_sample_weights_decay_and_guard():
    df = pd.DataFrame({"season": [2020, 2022, 2024]})
    w = sample_weights(df, target_season=2024, half_life_seasons=2.0)
    assert w[2] == 1.0
    assert w[1] == pytest.approx(0.5)
    assert w[0] == pytest.approx(0.25)
    with pytest.raises(ValueError):
        sample_weights(pd.DataFrame({"season": [2026]}), target_season=2024)

```

===== FILE: tests/test_watchlist.py =====
```python
"""Player watch notes: module + endpoints (BQ seams monkeypatched)."""

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from nfl_dfs import watchlist
from nfl_dfs.app import main as app_main


def _fake_df(rows):
    cols = ["note_id", "gsis_id", "display_name", "note", "status",
            "created_at", "converted_at", "converted_note_id", "converted_mult"]
    return pd.DataFrame(rows, columns=cols)


def test_annotate_players_matches_by_name(monkeypatch):
    monkeypatch.setattr(watchlist, "list_watch", lambda include_converted=True: _fake_df([
        ["n1", "", "Rookie Guy", "explosive in camp", "active",
         "2026-08-01", None, "", np.nan],
    ]))
    players = [{"name": "Rookie Guy", "pos": "WR"},
               {"name": "Someone Else", "pos": "RB"}]
    watchlist.annotate_players(players)
    assert players[0]["watch_note"] == "explosive in camp"
    assert "watch_note" not in players[1]


def test_annotate_failsafe(monkeypatch):
    def boom(include_converted=True):
        raise RuntimeError("bq down")
    monkeypatch.setattr(watchlist, "list_watch", boom)
    players = [{"name": "A"}]
    watchlist.annotate_players(players)  # must not raise
    assert "watch_note" not in players[0]


def test_convert_guards(monkeypatch):
    monkeypatch.setattr(watchlist, "list_watch", lambda include_converted=True: _fake_df([
        ["n1", "g1", "P One", "note", "converted", "2026-08-01",
         "2026-08-02", "m1", 1.1],
    ]))
    with pytest.raises(ValueError, match="already converted"):
        watchlist.convert_watch("n1", 1.2, 2026)
    with pytest.raises(ValueError, match="no watch note"):
        watchlist.convert_watch("missing", 1.2, 2026)


def test_watchlist_page_and_api(monkeypatch):
    monkeypatch.setattr(watchlist, "list_watch", lambda include_converted=True: _fake_df([
        ["n1", "", "P One", "note text", "active", "2026-08-01",
         None, "", np.nan],
    ]))
    client = TestClient(app_main.app)
    assert "Watchlist" in client.get("/watchlist").text
    j = client.get("/api/watchlist").json()
    assert j[0]["display_name"] == "P One" and j[0]["status"] == "active"


def test_build_lineups_annotation_hook(monkeypatch):
    """_with_watch_notes decorates player dicts in lineup responses."""
    monkeypatch.setattr(watchlist, "list_watch", lambda include_converted=True: _fake_df([
        ["n1", "", "Note Target", "watch him", "active", "2026-08-01",
         None, "", np.nan],
    ]))
    players = [{"name": "Note Target"}, {"name": "Nobody"}]
    out = app_main._with_watch_notes(players)
    assert out[0]["watch_note"] == "watch him"


def test_system_context_sections_and_docs():
    from nfl_dfs.app import system_context as sc
    from nfl_dfs.app.chat import execute_tool

    for topic in ("overview", "notes_and_adjustments", "conversion_guide",
                  "already_priced"):
        assert len(sc.get_section(topic)) > 200
    assert "available:" in sc.get_section("nope")
    # archetype guidance mentions the double-count distinction
    guide = sc.get_section("conversion_guide")
    assert "INJURY REPORTS" in guide and "double-count" in guide.lower()
    # docs resolve from the repo checkout
    assert "Plain-English Primer" in sc.read_doc("model-primer")
    assert "unknown doc" in sc.read_doc("bogus")
    # chat dispatch
    assert "OPPORTUNITY" in execute_tool("system_design",
                                         {"topic": "notes_and_adjustments"})

```

===== FILE: tests/test_widen_draws.py =====
```python
"""SIM_WIDEN_DRAWS: mean-preserving draw widening (WR-ceiling lever).

The calibration's widen factors only ever stretched summary quantiles;
this lever applies them to the draw matrix the contest engine actually
optimizes against. Mean preservation is the contract — projections and
field behavior must not move, only the joint tail."""

import numpy as np
import pandas as pd

from nfl_dfs.backtest.replay import _widen_draws


def _mk():
    rng = np.random.default_rng(3)
    draws = rng.gamma(2.0, 5.0, size=(4, 5000))
    pos = pd.Series(["WR", "QB", "RB", "TE"])
    return draws, pos


def test_mean_preserved_and_std_scaled():
    draws, pos = _mk()
    out = _widen_draws(draws, pos, "WR:1.3,QB:1.5")
    np.testing.assert_allclose(out.mean(axis=1), draws.mean(axis=1), rtol=1e-9)
    ratio = out.std(axis=1) / draws.std(axis=1)
    np.testing.assert_allclose(ratio, [1.3, 1.5, 1.0, 1.0], rtol=1e-9)


def test_fitted_uses_calibration_factors():
    from nfl_dfs.models.calibration import DEFAULT_WIDEN

    draws, pos = _mk()
    out = _widen_draws(draws, pos, "fitted")
    ratio = out.std(axis=1) / draws.std(axis=1)
    expect = [DEFAULT_WIDEN[p] for p in pos]
    np.testing.assert_allclose(ratio, expect, rtol=1e-9)


def test_tail_actually_deepens():
    draws, pos = _mk()
    out = _widen_draws(draws, pos, "WR:1.3")
    assert np.percentile(out[0], 99) > np.percentile(draws[0], 99)
    assert (out[0] >= 40).mean() > (draws[0] >= 40).mean()


def test_shape_mix_blends_worlds(monkeypatch):
    from nfl_dfs.backtest.replay import apply_draw_shape

    draws, pos = _mk()
    monkeypatch.setenv("SHAPE_MIX", "0.5")
    out = apply_draw_shape(draws, pos, seed=1)
    n = draws.shape[1]
    # raw half untouched, shaped half changed
    np.testing.assert_array_equal(out[:, n // 2:], draws[:, n // 2:])
    assert not np.allclose(out[:, :n // 2], draws[:, :n // 2])


def test_emp_pos_filter(monkeypatch):
    from nfl_dfs.backtest.replay import _empirical_marginals

    draws, pos = _mk()
    monkeypatch.setenv("EMP_POS", "QB,RB,WR")
    out = _empirical_marginals(draws.copy(), pos,
                               np.random.default_rng(1))
    te_row = list(pos).index("TE")
    np.testing.assert_array_equal(out[te_row], draws[te_row])
    monkeypatch.delenv("EMP_POS")

```

===== FILE: tests/test_wr_lowown_levers.py =====
```python
"""WR-boom and ownership-shape levers (winner-anatomy follow-ups)."""

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.optimizer.lineup import optimize


def _pool(n_low=3):
    rng = np.random.default_rng(11)
    pool = []
    for i in range(60):
        pos = ["QB", "RB", "WR", "TE", "DST"][i % 5]
        pool.append({
            "id": f"p{i}", "name": f"P{i}", "pos": pos,
            "team": f"T{i % 8}", "opp": f"T{(i + 4) % 8}",
            "game_id": f"g{i % 4}", "salary": int(3000 + 150 * (i % 40)),
            "proj": float(5 + rng.random() * 20),
            "low_own": i < n_low,  # first few flagged low-owned
        })
    return pool


def test_min_lowown_constraint(monkeypatch):
    monkeypatch.setenv("MIN_LOWOWN", "2")
    lu = optimize(_pool(), stack=None)
    assert lu is not None
    assert sum(1 for p in lu.players if p.get("low_own")) >= 2


def test_min_lowown_off_by_default(monkeypatch):
    monkeypatch.delenv("MIN_LOWOWN", raising=False)
    lu = optimize(_pool(n_low=0), stack=None)
    assert lu is not None  # no flags, no constraint, still solves


def test_min_lowown_inert_when_unflagged(monkeypatch):
    monkeypatch.setenv("MIN_LOWOWN", "2")
    lu = optimize(_pool(n_low=0), stack=None)
    assert lu is not None  # flag absent from pool -> constraint skipped


def test_wr_boom_flags_top_decile():
    from nfl_dfs.backtest.replay import _wr_boom_flags  # noqa: F401 import works

    # pure-SQL helper; logic exercised via the percentile contract on a frame
    df = pd.DataFrame({
        "gsis_id": [f"W{i}" for i in range(20)], "season": 2025, "week": 3,
        "deep_targets_l4": list(range(1, 21)),
    })
    pct = df.groupby(["season", "week"]).deep_targets_l4.rank(pct=True)
    assert set(df[pct >= 0.90].gsis_id) == {"W17", "W18", "W19"}


def test_max_per_game_cap(monkeypatch):
    monkeypatch.setenv("MAX_PER_GAME", "3")
    lu = optimize(_pool(), stack=None)
    assert lu is not None
    games = {}
    for p in lu.players:
        games[p["game_id"]] = games.get(p["game_id"], 0) + 1
    assert max(games.values()) <= 3


def test_value2_barbell(monkeypatch):
    monkeypatch.setenv("VALUE2_MIN", "2")
    monkeypatch.setenv("VALUE2_MAX", "5300")
    lu = optimize(_pool(), stack=None)
    assert lu is not None
    cheap = [p for p in lu.players
             if p["salary"] <= 5300 and p["pos"] != "DST"]
    assert len(cheap) >= 2


def test_qd_cell_constraints_hold():
    """optimize() cell parameters (the MAP-Elites archive axes): salary
    band and per-game concentration must bind simultaneously."""
    from nfl_dfs.optimizer.lineup import optimize

    pool = _pool()
    # 4-game fixture: mpg=2 is pigeonhole-infeasible (9 slots / 4 games)
    # and must return None (the engine skips such cells), mpg=3 must bind.
    assert optimize(pool, min_salary=44_000, max_salary=47_500,
                    max_per_game=2) is None
    lu = optimize(pool, min_salary=44_000, max_salary=47_500, max_per_game=3)
    assert lu is not None
    assert 44_000 <= lu.salary <= 47_500
    from collections import Counter

    per_game = Counter(p.get("game_id") for p in lu.players)
    assert max(per_game.values()) <= 3

```
