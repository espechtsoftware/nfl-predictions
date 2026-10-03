"""Millionaire ("Milly") derivations over the rows the SQL returns.

Input rows (see sql/dashboard/milly_*.sql):
  top      season, week, contest_id, lineup_key, rank, points,
           lineup_slots_json, dupes, n_entries
  slate    season, week, contest_id, display_name, team, position, salary
  games    the season schedule (week, home_team, away_team)
  own      season, week, contest_id, display_name, own (percent), fpts

Construction of a lineup: its QB's team, how many QB teammates it carries
(the stack, "QB+n", DST excluded), how many players from the QB's opponent
(the bring-back, DST excluded), salary used, summed field ownership, and how
many identical rosters the field held (dupes).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .teams import canon_team

SLOTS = ("QB", "RB", "WR", "TE", "FLEX", "DST")


def explode_lineups(top: pd.DataFrame) -> pd.DataFrame:
    """One row per (lineup, slot) from ``lineup_slots_json``."""
    cols = ["season", "week", "contest_id", "lineup_key", "rank", "points", "slot", "player"]
    rows = []
    for r in top.itertuples(index=False):
        try:
            slots = json.loads(r.lineup_slots_json or "[]")
        except (TypeError, ValueError):
            continue
        for s in slots:
            rows.append((r.season, r.week, r.contest_id, r.lineup_key, r.rank, r.points,
                         str(s.get("slot", "")), str(s.get("player", ""))))
    return pd.DataFrame(rows, columns=cols)


def opponent_map(games: pd.DataFrame) -> dict[tuple[int, str], str]:
    """(week, team) -> opponent, canonical codes."""
    out: dict[tuple[int, str], str] = {}
    for g in games.itertuples(index=False):
        h, a = canon_team(g.home_team), canon_team(g.away_team)
        if h and a:
            out[(int(g.week), h)] = a
            out[(int(g.week), a)] = h
    return out


def lineup_construction(top: pd.DataFrame, slate: pd.DataFrame, games: pd.DataFrame,
                        own: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per lineup: qb, qb_team, stack (QB teammates), bring_back, stack_label
    (e.g. "QB+2+1"), salary, own_sum, teams, games, dupes, points, rank.
    Players missing from the slate count as unknown team (no stack credit)."""
    cols = ["season", "week", "contest_id", "lineup_key", "rank", "points", "dupes",
            "qb", "qb_team", "stack", "bring_back", "stack_label", "salary",
            "own_sum", "n_teams", "n_games", "matched"]
    if top.empty:
        return pd.DataFrame(columns=cols)
    long = explode_lineups(top)
    sl = slate.copy()
    sl["team_c"] = sl.team.map(canon_team)
    sl = sl.drop_duplicates(["contest_id", "display_name"])
    long = long.merge(sl[["contest_id", "display_name", "team_c", "position", "salary"]]
                      .rename(columns={"display_name": "player"}),
                      on=["contest_id", "player"], how="left")
    if own is not None and not own.empty:
        o = own[["contest_id", "display_name", "own"]].rename(columns={"display_name": "player"})
        long = long.merge(o.drop_duplicates(["contest_id", "player"]),
                          on=["contest_id", "player"], how="left")
    else:
        long["own"] = np.nan
    opp = opponent_map(games)
    dupes = top.set_index("lineup_key").dupes.to_dict() if "dupes" in top else {}
    rows = []
    for key, g in long.groupby("lineup_key", sort=False):
        first = g.iloc[0]
        qb = g[g.slot == "QB"]
        qb_name = qb.player.iloc[0] if len(qb) else None
        qb_team = qb.team_c.iloc[0] if len(qb) else None
        non_dst = g[(g.slot != "DST") & (g.slot != "QB")]
        stack = int((non_dst.team_c == qb_team).sum()) if qb_team else 0
        opp_team = opp.get((int(first.week), qb_team)) if qb_team else None
        bring = int((non_dst.team_c == opp_team).sum()) if opp_team else 0
        teams = set(g.team_c.dropna())
        game_ids = {tuple(sorted((t, opp.get((int(first.week), t), "?")))) for t in teams}
        rows.append({
            "season": first.season, "week": first.week, "contest_id": first.contest_id,
            "lineup_key": key, "rank": first["rank"], "points": first.points,
            "dupes": dupes.get(key), "qb": qb_name, "qb_team": qb_team,
            "stack": stack, "bring_back": bring,
            "stack_label": f"QB+{stack}" + (f"+{bring}" if bring else ""),
            "salary": float(pd.to_numeric(g.salary, errors="coerce").sum(min_count=1))
            if g.salary.notna().any() else np.nan,
            "own_sum": float(g.own.sum()) if g.own.notna().any() else np.nan,
            "n_teams": len(teams), "n_games": len(game_ids),
            "matched": int(g.team_c.notna().sum()),
        })
    return pd.DataFrame(rows, columns=cols).sort_values(["week", "rank"]).reset_index(drop=True)


def construction_summary(cons: pd.DataFrame) -> pd.DataFrame:
    """Per week, over the lineups given (the top 1% by default): share with
    a QB+2-or-more stack, share with a bring-back, mean salary used, mean
    summed ownership, median dupes, the most common stack shape."""
    cols = ["week", "n", "share_qb_stack2", "share_bring_back", "mean_salary",
            "mean_own_sum", "median_dupes", "top_shape", "top_shape_share"]
    if cons.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    for wk, g in cons.groupby("week"):
        shapes = g.stack_label.value_counts(normalize=True)
        rows.append({
            "week": int(wk), "n": len(g),
            "share_qb_stack2": float((g["stack"] >= 2).mean()),
            "share_bring_back": float((g.bring_back >= 1).mean()),
            "mean_salary": float(g.salary.mean()),
            "mean_own_sum": float(g.own_sum.mean()),
            "median_dupes": float(pd.to_numeric(g.dupes, errors="coerce").median()),
            "top_shape": shapes.index[0] if len(shapes) else None,
            "top_shape_share": float(shapes.iloc[0]) if len(shapes) else np.nan,
        })
    return pd.DataFrame(rows, columns=cols)


def winners(cons: pd.DataFrame) -> pd.DataFrame:
    """The best-ranked lineup of each week (ties: the first listed)."""
    if cons.empty:
        return cons
    return (cons.sort_values(["week", "rank", "points"], ascending=[True, True, False])
            .groupby("week").head(1).reset_index(drop=True))


def lineup_players(top: pd.DataFrame, lineup_key: str) -> list[tuple[str, str]]:
    """(slot, player) for one lineup, in DraftKings' printed order."""
    long = explode_lineups(top[top.lineup_key == lineup_key])
    order = {s: i for i, s in enumerate(SLOTS)}
    long["o"] = long.slot.map(lambda s: order.get(s, 99))
    return list(long.sort_values("o")[["slot", "player"]].itertuples(index=False, name=None))


def most_owned(own: pd.DataFrame, k: int = 10) -> pd.DataFrame:
    """The field's k most-owned players per week."""
    if own.empty:
        return own
    return (own.sort_values(["week", "own"], ascending=[True, False])
            .groupby("week").head(k).reset_index(drop=True))


def ours_vs_winner(lines: pd.DataFrame, arms: pd.DataFrame) -> pd.DataFrame:
    """Per week: the winner and lines next to our best published lineup
    (arms of kind entered/book), with its rank in the Millionaire field."""
    if lines.empty:
        return pd.DataFrame()
    out = lines[["week", "n_entries", "winning_score", "top_01pct_line",
                 "top_1pct_line", "cash_line"]].copy()
    if arms.empty:
        out["our_best_points"] = np.nan
        out["our_best_rank"] = np.nan
        out["our_arm"] = None
        return out
    a = arms[arms.kind.isin(["entered", "book"])].copy()
    a["best_points"] = pd.to_numeric(a.best_points, errors="coerce")
    a = a.dropna(subset=["best_points"]).sort_values("best_points", ascending=False)
    best = a.groupby("week").head(1)[["week", "arm", "best_points", "best_rank"]]
    out = out.merge(best.rename(columns={"arm": "our_arm", "best_points": "our_best_points",
                                         "best_rank": "our_best_rank"}), on="week", how="left")
    out["gap_to_winner"] = out.winning_score - out.our_best_points
    return out
