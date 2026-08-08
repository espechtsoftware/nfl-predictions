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
    # Salary-spined replay intentionally retains listed inactive/cold-start
    # rows, whose roster metadata may be nullable.  pandas.NA has no truth
    # value, so all boolean provenance must use an explicit false fallback.
    cold = out.is_cold_start.fillna(False).astype(bool)

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
        rookie = row.get("is_rookie", False)
        if pd.notna(rookie) and bool(rookie):
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
