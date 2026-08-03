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
