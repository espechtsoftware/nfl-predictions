"""Dashboard chat: manage manual usage notes and query system data in
plain English. Backed by the Claude API with a small tool set; the manual
tool loop follows the Anthropic tool-use pattern.

Requires ANTHROPIC_API_KEY in the environment (.env is loaded by config).
"""

from __future__ import annotations

import json
import logging

import pandas as pd

from .. import notes
from ..bq import query_df
from ..config import current_season, settings

log = logging.getLogger(__name__)

MODEL = "claude-opus-5"
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

You can also read the system's current projections and a player's recent
form. If asked for something you have no tool for, say so briefly."""

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


def chat_turn(messages: list[dict]) -> list[dict]:
    """Run one user turn through Claude's tool loop. `messages` is the
    prior API-shaped history plus the new user message; returns the
    full updated history (assistant turns + tool results appended)."""
    import anthropic

    client = anthropic.Anthropic()
    for _ in range(MAX_TOOL_TURNS):
        response = client.messages.create(
            model=MODEL, max_tokens=4000, system=SYSTEM,
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
                                "content": f"Error: {exc}", "is_error": True})
        messages.append({"role": "user", "content": results})
    return messages


def reply_text(messages: list[dict]) -> str:
    """Concatenated text of the last assistant turn."""
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            return "".join(b.get("text", "") for b in msg["content"]
                           if b.get("type") == "text")
    return ""
