"""Prospective leaderboard and missed-player diagnostics.

Historical project data contains winner rosters and aggregate ownership, not
the entry-level top 20. This module operates on the lossless standings rows
captured by ``import-ownership`` from 2026 onward. All transformation helpers
are pure DataFrame operations so their definitions are testable before the
first slate.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..ingest.ownership_import import parse_lineup_slots
from ..research.breakout_state import classify_breakout_state


def _norm_name(value: object) -> str:
    text = re.sub(r"\s+(JR|SR|II|III|IV|V)\.?$", "", str(value).upper())
    return re.sub(r"[^A-Z ]", "", text).strip()


def top_entries(entries: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """The first ``n`` actual entries, retaining duplicate lineups."""
    if entries.empty:
        return entries.copy()
    order = ["rank"] + (["points"] if "points" in entries else [])
    ascending = [True] + ([False] if "points" in entries else [])
    return entries.sort_values(order, ascending=ascending).head(n).copy()


def explode_entry_slots(entries: pd.DataFrame) -> pd.DataFrame:
    """One row per player-slot appearance with its originating entry."""
    rows: list[dict] = []
    for row_ix, row in entries.reset_index(drop=True).iterrows():
        raw = row.get("lineup_slots_json")
        if isinstance(raw, str) and raw.strip():
            slots = json.loads(raw)
        else:
            slots = parse_lineup_slots(str(row["lineup"]))
        for slot_ix, item in enumerate(slots):
            rows.append({
                "entry_row": row_ix,
                "entry_id": row.get("entry_id", str(row_ix)),
                "rank": row.get("rank"),
                "points": row.get("points"),
                "players_key": row.get("players_key"),
                "slot_index": slot_ix,
                "slot": item["slot"],
                "display_name": item["player"],
                "clean_name": _norm_name(item["player"]),
            })
    return pd.DataFrame(rows)


def leaderboard_tables(
    entries: pd.DataFrame, ownership: pd.DataFrame, n: int = 20
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return entry-level leverage and player-appearance summaries."""
    leaders = top_entries(entries, n=n)
    slots = explode_entry_slots(leaders)
    own = ownership.copy()
    own["clean_name"] = own["display_name"].map(_norm_name)
    own = own.groupby("clean_name", as_index=False).agg(
        pct_drafted=("pct_drafted", "mean"),
        actual_fpts=("fpts", "max"),
    )
    slots = slots.merge(own, on="clean_name", how="left")

    dupe = entries.groupby("players_key").size().rename("duplicate_count")
    entry = slots.groupby("entry_row", as_index=False).agg(
        entry_id=("entry_id", "first"),
        rank=("rank", "first"),
        points=("points", "first"),
        players_key=("players_key", "first"),
        ownership_sum=("pct_drafted", "sum"),
        min_ownership=("pct_drafted", "min"),
        low_owned_players=("pct_drafted", lambda s: int((s < 5).sum())),
        ownership_matches=("pct_drafted", "count"),
        n_players=("display_name", "count"),
    )
    entry["duplicate_count"] = entry["players_key"].map(dupe).fillna(1).astype(int)

    players = slots.groupby(["clean_name", "display_name"], as_index=False).agg(
        top20_appearances=("entry_row", "nunique"),
        best_rank=("rank", "min"),
        mean_rank=("rank", "mean"),
        pct_drafted=("pct_drafted", "mean"),
        actual_fpts=("actual_fpts", "max"),
    ).sort_values(["best_rank", "top20_appearances"], ascending=[True, False])
    return entry, players


def forced_player_counterfactual(
    candidates: pd.DataFrame, player_id: str
) -> dict[str, float | bool | int | str]:
    """Candidate-level forced-lock diagnostic for one missed player.

    This does not pretend to be a new MILP solve. It answers the first causal
    question cheaply: did the frozen candidate pool contain a strong lineup
    with the player, and if so did selection leave it out?
    """
    required = {"players", "actual_score", "selected"}
    missing = required - set(candidates.columns)
    if missing:
        raise ValueError(f"candidate rows missing {sorted(missing)}")
    pid = str(player_id)
    has = candidates["players"].fillna("").map(
        lambda value: pid in {x for x in str(value).split(",") if x}
    )
    selected = candidates["selected"].astype(bool)
    actual = pd.to_numeric(candidates["actual_score"], errors="coerce")

    def best(mask: pd.Series) -> float:
        values = actual[mask].dropna()
        return float(values.max()) if not values.empty else float("nan")

    selected_best = best(selected)
    with_best = best(has)
    return {
        "player_id": pid,
        "generated": bool(has.any()),
        "selected": bool((has & selected).any()),
        "n_candidates_with_player": int(has.sum()),
        "best_selected_score": selected_best,
        "best_with_player_score": with_best,
        "selection_opportunity": (
            float(with_best - selected_best)
            if np.isfinite(with_best) and np.isfinite(selected_best) else float("nan")
        ),
        "pool_oracle_score": best(pd.Series(True, index=candidates.index)),
    }


def missed_player_rows(
    candidates: pd.DataFrame,
    player_features: pd.DataFrame,
    actual_threshold: float = 20.0,
) -> pd.DataFrame:
    """Attribute every high-scoring unselected player to a failure stage."""
    need_c = {"season", "week", "players", "actual_score", "selected"}
    need_p = {"season", "week", "id", "actual"}
    if missing := need_c - set(candidates.columns):
        raise ValueError(f"candidate rows missing {sorted(missing)}")
    if missing := need_p - set(player_features.columns):
        raise ValueError(f"player feature rows missing {sorted(missing)}")
    rows: list[dict] = []
    group_cols = ["season", "week"]
    if "slate_run_id" in candidates and "slate_run_id" in player_features:
        group_cols.append("slate_run_id")
    for key, cand in candidates.groupby(group_cols, dropna=False):
        key_tuple = key if isinstance(key, tuple) else (key,)
        filt = pd.Series(True, index=player_features.index)
        for col, value in zip(group_cols, key_tuple):
            filt &= player_features[col].eq(value)
        feats = player_features[filt].drop_duplicates("id")
        selected_ids: set[str] = set()
        for value in cand.loc[cand.selected.astype(bool), "players"]:
            selected_ids.update(x for x in str(value).split(",") if x)
        misses = feats[
            pd.to_numeric(feats.actual, errors="coerce").ge(actual_threshold)
            & ~feats.id.astype(str).isin(selected_ids)
        ]
        for player in misses.itertuples():
            cf = forced_player_counterfactual(cand, str(player.id))
            if not cf["generated"]:
                stage = "generation"
            elif (np.isfinite(cf["selection_opportunity"])
                  and cf["selection_opportunity"] > 0):
                stage = "selection"
            else:
                stage = "combination_or_projection"
            row = dict(zip(group_cols, key_tuple))
            archetype = classify_breakout_state({
                "position": getattr(player, "pos", None),
                "salary": getattr(player, "salary", None),
                "is_cold_start": getattr(player, "is_cold_start", None),
                "depth_rank_delta": getattr(player, "depth_rank_delta", None),
                "team_vacated_target_share": getattr(
                    player, "team_vacated_target_share", None),
                "team_vacated_carry_share": getattr(
                    player, "team_vacated_carry_share", None),
                "target_share_jump": getattr(player, "target_share_jump", None),
                "carry_share_jump": getattr(player, "carry_share_jump", None),
                "snap_share_jump": getattr(player, "snap_share_jump", None),
                "snap_share_last": getattr(player, "snap_share_last", None),
                "spread": getattr(player, "spread", None),
                "implied_team_total": getattr(
                    player, "implied_team_total", None),
            })
            row.update({
                "player_id": str(player.id),
                "display_name": getattr(player, "name", None),
                "position": getattr(player, "pos", None),
                "team": getattr(player, "team", None),
                "salary": getattr(player, "salary", None),
                "projection": getattr(player, "proj", None),
                "actual": float(player.actual),
                "projected_ownership": getattr(player, "own_est", None),
                "breakout_archetype": archetype,
                "failure_stage": stage,
                **cf,
            })
            rows.append(row)
    return pd.DataFrame(rows)


def run(season: int, week: int, contest_id: str, top_n: int = 20) -> dict:
    """Analyze a captured contest and persist reproducible result tables."""
    from ..bq import load_dataframe, query_df
    from ..config import settings

    entries = query_df(
        f"""SELECT * FROM `{settings.raw}.contest_entries`
            WHERE season=@season AND week=@week AND contest_id=@contest_id
            QUALIFY ROW_NUMBER() OVER (
              PARTITION BY contest_id, entry_id ORDER BY imported_at DESC
            ) = 1""",
        params={"season": int(season), "week": int(week),
                "contest_id": str(contest_id)},
    )
    if entries.empty:
        raise RuntimeError(
            f"no contest_entries for {season} week {week} contest {contest_id}"
        )
    ownership = query_df(
        f"""SELECT display_name, AVG(pct_drafted) AS pct_drafted,
                   MAX(fpts) AS fpts
            FROM `{settings.raw}.contest_ownership`
            WHERE season=@season AND week=@week AND contest_id=@contest_id
            GROUP BY display_name""",
        params={"season": int(season), "week": int(week),
                "contest_id": str(contest_id)},
    )
    entry, players = leaderboard_tables(entries, ownership, n=top_n)
    generated_at = datetime.now(timezone.utc)
    for frame in (entry, players):
        frame.insert(0, "generated_at", generated_at)
        frame.insert(1, "season", int(season))
        frame.insert(2, "week", int(week))
        frame.insert(3, "contest_id", str(contest_id))
    load_dataframe(
        entry, f"{settings.predictions}.leaderboard_entry_analysis",
        write_disposition="WRITE_APPEND",
    )
    load_dataframe(
        players, f"{settings.predictions}.leaderboard_player_analysis",
        write_disposition="WRITE_APPEND",
    )
    return {
        "entries_analyzed": len(entry),
        "players_analyzed": len(players),
        "winner_ownership_sum": float(entry.sort_values("rank").ownership_sum.iloc[0]),
        "winner_min_ownership": float(entry.sort_values("rank").min_ownership.iloc[0]),
    }


def run_missed_panel(panel_run_id: str, actual_threshold: float = 20.0) -> dict:
    """Persist high-score player misses from an accepted frozen panel."""
    from ..bq import load_dataframe, query_df
    from ..config import settings

    candidates = query_df(
        f"""SELECT season, week, slate_run_id, players, actual_score, selected
            FROM `{settings.predictions}.replay_candidates`
            WHERE panel_run_id=@panel AND research_eligible""",
        params={"panel": panel_run_id},
    )
    features = query_df(
        f"""SELECT *
            FROM `{settings.predictions}.slate_player_features`
            WHERE panel_run_id=@panel AND research_eligible""",
        params={"panel": panel_run_id},
    )
    if candidates.empty or features.empty:
        raise RuntimeError(f"accepted panel data unavailable for {panel_run_id}")
    out = missed_player_rows(candidates, features, actual_threshold)
    out.insert(0, "generated_at", datetime.now(timezone.utc))
    out.insert(1, "panel_run_id", panel_run_id)
    out.insert(2, "actual_threshold", float(actual_threshold))
    load_dataframe(
        out, f"{settings.predictions}.missed_player_analysis",
        write_disposition="WRITE_APPEND",
    )
    return {
        "missed_players": int(len(out)),
        "generation_misses": int((out.failure_stage == "generation").sum()),
        "selection_misses": int((out.failure_stage == "selection").sum()),
    }
