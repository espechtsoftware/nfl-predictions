"""Candidate-level features derived DETERMINISTICALLY from the
immutable per-slate player snapshot (scoring plan §5.3).

The plan's rule: "Prefer deterministic derivation over duplicating
aggregates. If an aggregate is persisted, record its definition
version and test that it recomputes from candidate-player rows."
Nothing here is persisted by the engine — these are computed from
`slate_player_features` joined to the candidate rows' player lists, so
a definition change never invalidates a harvest.

Every feature is computable PRE-LOCK. Anything needing actuals belongs
in the label, not here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Bump when a definition changes; reports and models record it so a
# feature drift can never be mistaken for a modelling result.
FEATURE_DEF_VERSION = "cf-1.0.0"

# Point-in-time player state that must survive projection replay, slate
# construction, and the immutable warehouse snapshot as one contract.  Keeping
# this list in one place prevents an experimental feature from reaching model
# training while being silently discarded before the audit snapshot.
PLAYER_SNAPSHOT_FEATURES = (
    "target_share_last",
    "carry_share_last",
    "snap_share_last",
    "target_share_jump",
    "carry_share_jump",
    "snap_share_jump",
    "target_share_l4",
    "carry_share_l4",
    "snap_share_l4",
    "dk_points_l4",
    "implied_team_total",
    "spread",
    "game_total",
    "is_cold_start",
    "depth_rank",
    "depth_rank_delta",
    "team_vacated_target_share",
    "team_vacated_carry_share",
    "salary_delta_wow",
    "games_played_prior",
)

_SLOTS = ("QB", "RB", "WR", "TE", "DST")


def _stack_shape(pl: pd.DataFrame) -> tuple[int, int]:
    """(same-team pass catchers with the QB, opponent bring-back)."""
    qb = pl[pl.pos == "QB"]
    if qb.empty:
        return 0, 0
    qb_team = qb.team.iloc[0]
    qb_opp = qb.opp.iloc[0] if "opp" in pl.columns else None
    mates = int(((pl.team == qb_team) & (pl.pos.isin(("WR", "TE", "RB")))).sum())
    bring = int((pl.team == qb_opp).sum()) if qb_opp is not None else 0
    return mates, bring


def candidate_aggregates(
    players: pd.DataFrame,
    player_ids: list,
) -> dict:
    """Features for ONE candidate. `players` is the slate's immutable
    player-feature frame (one row per player); `player_ids` the roster.

    Missing optional columns yield NaN features rather than silent
    zeros — a model must be able to see that a family was unavailable.
    """
    pl = players[players.id.isin(player_ids)]
    out: dict = {"feature_def_version": FEATURE_DEF_VERSION,
                 "n_players": len(pl)}
    if pl.empty:
        return out

    def col(name):
        return pl[name] if name in pl.columns else pd.Series(dtype=float)

    out["proj_sum"] = float(col("proj").sum())
    out["salary_sum"] = float(col("salary").sum())
    out["salary_left"] = 50_000 - out["salary_sum"]
    own = col("own_est")
    out["own_sum"] = float(own.sum()) if len(own) else np.nan
    out["own_max"] = float(own.max()) if len(own) else np.nan
    # barbell shape: the winner-anatomy split (chalk + near-zero owned)
    out["own_n_low"] = int((own <= 0.05).sum()) if len(own) else -1
    out["own_n_high"] = int((own >= 0.20).sum()) if len(own) else -1

    # market/model disagreement — the orthogonal signal the reranker
    # exists for (plan §5.3, §7.2 arm A2)
    div = col("consensus_div")
    if len(div) and div.notna().any():
        out["div_abs_sum"] = float(div.abs().sum())
        out["div_abs_max"] = float(div.abs().max())
        out["div_signed_sum"] = float(div.sum())
        qb = pl[pl.pos == "QB"]
        out["div_qb"] = (float(qb.consensus_div.iloc[0])
                         if len(qb) and "consensus_div" in qb else np.nan)
        mates, bring = _stack_shape(pl)
        qb_team = qb.team.iloc[0] if len(qb) else None
        stack_rows = pl[(pl.team == qb_team) & (pl.pos != "QB")] if qb_team else pl.iloc[0:0]
        out["div_stack_sum"] = (float(stack_rows.consensus_div.sum())
                                if "consensus_div" in stack_rows else np.nan)
    else:
        for k in ("div_abs_sum", "div_abs_max", "div_signed_sum",
                  "div_qb", "div_stack_sum"):
            out[k] = np.nan
    out["market_covered"] = (float(col("market_points").notna().mean())
                             if "market_points" in pl.columns else np.nan)

    # marginal-uncertainty width (epistemic-ish proxy until ensemble
    # member spread is plumbed — plan §5.2 allows marking unavailable)
    if {"proj_p10", "proj_p90"} <= set(pl.columns):
        width = col("proj_p90") - col("proj_p10")
        out["q_width_sum"] = float(width.sum())
        out["q_width_max"] = float(width.max())
    else:
        out["q_width_sum"] = out["q_width_max"] = np.nan

    mates, bring = _stack_shape(pl)
    out["stack_mates"] = mates
    out["bring_back"] = bring
    if "game_id" in pl.columns:
        counts = pl.game_id.value_counts()
        out["max_from_game"] = int(counts.iloc[0]) if len(counts) else 0
        out["n_games"] = int(pl.game_id.nunique())
    else:
        out["max_from_game"], out["n_games"] = -1, -1
    for p in _SLOTS:
        out[f"n_{p.lower()}"] = int((pl.pos == p).sum())
    return out


def candidate_feature_frame(
    candidates: pd.DataFrame,
    players: pd.DataFrame,
    id_col: str = "players",
) -> pd.DataFrame:
    """Vectorized wrapper: one feature row per candidate, keyed by
    (slate_run_id, cand_ix). `candidates.players` is the comma-joined
    roster id list the engine persists."""
    rows = []
    for _, c in candidates.iterrows():
        ids = [x for x in str(c[id_col]).split(",") if x]
        feats = candidate_aggregates(players, ids)
        feats["slate_run_id"] = c.get("slate_run_id")
        feats["cand_ix"] = c.get("cand_ix")
        rows.append(feats)
    return pd.DataFrame(rows)
