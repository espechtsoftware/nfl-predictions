"""Millionaire ("Milly") derivations over the rows the SQL returns.

Input rows (see sql/dashboard/milly_*.sql):
  top      season, week, contest_id, lineup_key, rank, points,
           lineup_slots_json, dupes, n_entries
  slate    season, week, contest_id, display_name, team, position, salary
  games    the season schedule (week, home_team, away_team)
  own      season, week, contest_id, display_name, own (percent), fpts

Identity: standings lineups carry display names only. Each name is resolved
to the slate's DraftKings player id by normalised name within the contest's
draft group (scripts/o1_common.py's rule). A normalised name that two slate
players share is a collision: it is never merged, it stays unresolved, and
``slate_collisions`` lists it so callers can print it.

Construction of a lineup: its QB's team, how many QB teammates it carries
(the stack, "QB+n", DST excluded), how many players from the QB's opponent
(the bring-back, DST excluded), salary used, summed field ownership, and how
many identical rosters the field held (dupes).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .teams import canon_team, norm_name

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


def _slate_keyed(slate: pd.DataFrame) -> pd.DataFrame:
    sl = slate.copy()
    sl["k"] = sl.display_name.map(norm_name)
    sl["team_c"] = sl.team.map(canon_team)
    if "dk_player_id" not in sl:
        sl["dk_player_id"] = pd.NA
    return sl


def _ident(sl: pd.DataFrame) -> pd.Series:
    """A slate row's identity: its DraftKings id, else name + team."""
    return sl.dk_player_id.astype("string").fillna(sl.display_name.astype(str) + "|" + sl.team_c.astype(str))


def slate_collisions(slate: pd.DataFrame) -> pd.DataFrame:
    """Slate rows whose normalised name is shared by two or more distinct
    players in the same contest's slate (never merged; left unresolved)."""
    cols = ["contest_id", "k", "display_name", "team", "dk_player_id"]
    if slate.empty:
        return pd.DataFrame(columns=cols)
    sl = _slate_keyed(slate)
    sl["ident"] = _ident(sl)
    n = sl.groupby(["contest_id", "k"]).ident.transform("nunique")
    return sl[n > 1][cols].sort_values(["contest_id", "k"]).reset_index(drop=True)


def resolve_slate(slate: pd.DataFrame) -> pd.DataFrame:
    """One row per (contest_id, normalised name) that identifies exactly one
    slate player: contest_id, k, display_name, dk_player_id, team_c,
    position, salary."""
    cols = ["contest_id", "k", "display_name", "dk_player_id", "team_c", "position", "salary"]
    if slate.empty:
        return pd.DataFrame(columns=cols)
    sl = _slate_keyed(slate)
    sl["ident"] = _ident(sl)
    n = sl.groupby(["contest_id", "k"]).ident.transform("nunique")
    return sl[n == 1].drop_duplicates(["contest_id", "k"])[cols].reset_index(drop=True)


def resolve_names(long: pd.DataFrame, slate: pd.DataFrame, name_col: str = "player") -> pd.DataFrame:
    """Attach dk_player_id, team_c, position, salary to rows carrying a
    contest_id and a display name; collisions and unknown names get NaN."""
    out = long.copy()
    out["k"] = out[name_col].map(norm_name)
    res = resolve_slate(slate).drop(columns=["display_name"])
    return out.merge(res, on=["contest_id", "k"], how="left")


def lineup_construction(top: pd.DataFrame, slate: pd.DataFrame, games: pd.DataFrame,
                        own: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per lineup: qb, qb_team, stack (QB teammates), bring_back, stack_label
    (e.g. "QB+2+1"), salary, own_sum, teams, games, dupes, points, rank.
    Players missing from the slate, or whose normalised name collides with
    another slate player's, count as unknown team (no stack credit)."""
    cols = ["season", "week", "contest_id", "lineup_key", "rank", "points", "dupes",
            "qb", "qb_team", "stack", "bring_back", "stack_label", "salary",
            "own_sum", "n_teams", "n_games", "matched"]
    if top.empty:
        return pd.DataFrame(columns=cols)
    long = resolve_names(explode_lineups(top), slate)
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
        known_qb = isinstance(qb_team, str)
        # An unresolved QB (or a week without a slate) is unknown, never "QB+0".
        stack = int((non_dst.team_c == qb_team).sum()) if known_qb else np.nan
        opp_team = opp.get((int(first.week), qb_team)) if known_qb else None
        bring = int((non_dst.team_c == opp_team).sum()) if opp_team else (0 if known_qb else np.nan)
        teams = set(g.team_c.dropna())
        game_ids = {tuple(sorted((t, opp.get((int(first.week), t), "?")))) for t in teams}
        rows.append({
            "season": first.season, "week": first.week, "contest_id": first.contest_id,
            "lineup_key": key, "rank": first["rank"], "points": first.points,
            "dupes": dupes.get(key), "qb": qb_name, "qb_team": qb_team,
            "stack": stack, "bring_back": bring,
            "stack_label": (f"QB+{stack}" + (f"+{bring}" if bring else "")) if known_qb else None,
            "salary": float(pd.to_numeric(g.salary, errors="coerce").sum())
            if g.salary.notna().all() and len(g) == 9 else np.nan,
            "own_sum": float(g.own.sum()) if g.own.notna().any() else np.nan,
            "n_teams": len(teams), "n_games": len(game_ids),
            "matched": int(g.team_c.notna().sum()),
        })
    return pd.DataFrame(rows, columns=cols).sort_values(["week", "rank"]).reset_index(drop=True)


def construction_summary(cons: pd.DataFrame) -> pd.DataFrame:
    """Per week, over the lineups given (the top 1% by default) whose nine
    players all resolved to the slate: share with a QB+2-or-more stack, share
    with a bring-back, mean salary used, mean summed ownership, median dupes,
    the most common stack shape. ``n_excluded`` counts the lineups left out
    because a player did not resolve (a week without a slate excludes all)."""
    cols = ["week", "n", "n_excluded", "share_qb_stack2", "share_bring_back", "mean_salary",
            "mean_own_sum", "median_dupes", "top_shape", "top_shape_share"]
    if cons.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    for wk, g_all in cons.groupby("week"):
        g = g_all[g_all.matched == 9]
        if g.empty:
            rows.append({"week": int(wk), "n": 0, "n_excluded": len(g_all)})
            continue
        shapes = g.stack_label.value_counts(normalize=True)
        rows.append({
            "week": int(wk), "n": len(g), "n_excluded": len(g_all) - len(g),
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
    """Per week: the winner and lines next to our two books, side by side and
    never substituted for each other: ``played`` (the upload files after
    R4/swap) and ``book`` (the pre-R4 union book.csv), each with its best
    lineup's points and rank in the Millionaire field."""
    if lines.empty:
        return pd.DataFrame()
    out = lines[["week", "n_entries", "winning_score", "top_01pct_line",
                 "top_1pct_line", "cash_line"]].copy()
    for kind in ("played", "book"):
        a = arms[arms.kind == kind] if not arms.empty and "kind" in arms else pd.DataFrame()
        if a.empty:
            out[f"{kind}_best"] = np.nan
            out[f"{kind}_rank"] = np.nan
            continue
        a = a.assign(best_points=pd.to_numeric(a.best_points, errors="coerce"))
        best = (a.sort_values("best_points", ascending=False).groupby("week").head(1)
                [["week", "best_points", "best_rank"]]
                .rename(columns={"best_points": f"{kind}_best", "best_rank": f"{kind}_rank"}))
        out = out.merge(best, on="week", how="left")
    # "Our best" is the played (entered) arm; the pre-R4 book stands in only
    # when no played arm was published, and says so.
    has_played = out.played_best.notna()
    out["our_best"] = out.played_best.where(has_played, out.book_best)
    out["our_rank"] = out.played_rank.where(has_played, out.book_rank)
    out["our_source"] = np.where(has_played, "played",
                                 np.where(out.book_best.notna(), "book (no played arm published)", None))
    out["gap"] = out.winning_score - out.our_best
    return out
