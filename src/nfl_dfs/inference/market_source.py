"""Live market resolution with no silent stand-in (operator directive 2026-09-20).

Week 2 2026: two slate WRs lost their prop lines to an ambiguous-name drop and the
blend silently substituted their one-game DraftKings points-per-game as the
"market" at 55% weight (Jefferson served 25.3 from 0.45 x 18.1 + 0.55 x 31.2).
The operator's rule: a projection either works as designed or the run stops,
and anything that stands in for a missing input is recorded per player.

Rules implemented by :func:`resolve_live_market`:

* a player with a matched prop market uses it (``source = "props"``);
* a non-DST slate player whose spelling IS in the week's prop feed but did not
  match raises :class:`MarketMatchError` (the Week-2 defect; fail closed);
* a prop feed that exists but matches fewer than ``min_coverage`` of the
  non-DST slate raises :class:`MarketMatchError` (broken feed; fail closed);
* a player for whom the books posted no line, or a DST, or a week with no feed
  at all, is served by the model alone (NaN market; ``blend`` uses the model)
  and is recorded as ``model_only_no_line`` / ``model_only_dst`` /
  ``model_only_no_feed``.  Nothing else is substituted.

Every resolution is returned as a frame for the ``market_source_log`` table so
the exposure sheet and the gate checker can show which players were served
without a market.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..names import norm_name

log = logging.getLogger(__name__)

SOURCE_LOG_TABLE = "market_source_log"


class MarketMatchError(RuntimeError):
    """A slate player with prop lines in the feed did not receive a market."""


def resolve_live_market(
    feats: pd.DataFrame,
    market_week: pd.DataFrame,
    feed_player_names: set[str] | frozenset[str],
    *,
    min_coverage: float = 0.30,
) -> tuple[np.ndarray, pd.DataFrame]:
    """Return (market vector aligned with ``feats``, per-player source frame).

    ``feats`` needs ``gsis_id``, ``display_name`` and ``position``.
    ``market_week`` is ``prop_market.market_points`` restricted to the week
    (``gsis_id``, ``market_points``).  ``feed_player_names`` are the raw prop
    feed names for the week (matched or not).
    """
    if not 0.0 <= min_coverage <= 1.0:
        raise ValueError("min_coverage must be between 0 and 1")
    n = len(feats)
    gsis = feats["gsis_id"].astype(object).where(feats["gsis_id"].notna(), None)
    names = feats.get("display_name", pd.Series("?", index=feats.index)).astype(str)
    # 2026-09-25: live slate rows carry `position` blank for DSTs and `dk_position` = "DST"; fill the blank from
    # dk_position so DSTs are recognised (before: 30 DSTs counted as "no line" in the coverage denominator).
    position = feats.get("position", pd.Series(pd.NA, index=feats.index))
    if "dk_position" in feats:
        position = position.fillna(feats["dk_position"])
    position = position.fillna("?").astype(str)
    is_dst = position.str.upper().eq("DST").to_numpy()

    mw = market_week.dropna(subset=["gsis_id", "market_points"]) if len(market_week) else market_week
    if len(mw) and mw.gsis_id.duplicated().any():
        raise MarketMatchError("market_points carries duplicate gsis_id rows; refusing to align")
    points_by_id = dict(zip(mw.gsis_id.astype(str), mw.market_points.astype(float))) if len(mw) else {}
    feed_norms = {norm_name(x) for x in feed_player_names if str(x).strip()}
    feed_present = bool(feed_norms)

    market = np.full(n, np.nan, dtype=float)
    source = np.empty(n, dtype=object)
    unmatched_in_feed: list[str] = []
    for k in range(n):
        gid = gsis.iloc[k]
        key = str(gid) if gid is not None else None
        if is_dst[k]:
            source[k] = "model_only_dst"
            continue
        if key is not None and key in points_by_id:
            market[k] = points_by_id[key]
            source[k] = "props"
            continue
        if not feed_present:
            source[k] = "model_only_no_feed"
            continue
        if norm_name(names.iloc[k]) in feed_norms:
            source[k] = "unmatched_in_feed"
            unmatched_in_feed.append(names.iloc[k])
            continue
        source[k] = "model_only_no_line"

    if unmatched_in_feed:
        raise MarketMatchError(
            "prop lines exist in the feed for %d slate player(s) but did not match a projection row: %s"
            % (len(unmatched_in_feed), ", ".join(sorted(unmatched_in_feed)[:25]))
        )
    non_dst = int((~is_dst).sum())
    matched = int((source == "props").sum())
    if feed_present and non_dst and matched < min_coverage * non_dst:
        raise MarketMatchError(
            "prop feed present but matched only %d of %d non-DST slate rows (minimum %.0f%%)"
            % (matched, non_dst, 100 * min_coverage)
        )
    frame = pd.DataFrame({
        "gsis_id": [str(g) if g is not None else None for g in gsis],
        "display_name": names.to_numpy(),
        "position": position.to_numpy(),
        "source": source,
        "market_points": market,
    })
    log.info(
        "live market sources: props %d, model_only_no_line %d, model_only_dst %d, model_only_no_feed %d%s",
        matched, int((source == "model_only_no_line").sum()), int((source == "model_only_dst").sum()),
        int((source == "model_only_no_feed").sum()),
        (": no line for " + ", ".join(sorted(names[source == "model_only_no_line"])[:25])) if (source == "model_only_no_line").any() else "",
    )
    return market, frame


def source_log_frame(
    frame: pd.DataFrame,
    *,
    season: int,
    week: int,
    proj_points: np.ndarray | pd.Series | None = None,
    model_points_pre: np.ndarray | pd.Series | None = None,
    model_weight: float | None = None,
    path: str,
    generated_at: datetime | None = None,
) -> pd.DataFrame:
    """Rows for ``nfl_predictions.market_source_log`` (one per slate player per run).

    Records the blend's INPUTS, not only its output.  Before 2026-09-21 this
    logged ``market_points`` and the blended ``proj_points`` but nothing of the
    model side, so reconstructing what the model said required inverting the
    nominal weight.  That inversion is unsafe: on the Week-2 signals export the
    inverted value disagreed with the independently recorded pre-blend value on
    175 of 175 rows, worst on quarterbacks, and for Justin Jefferson -- the row
    the Week-2 post-mortem turns on -- no pre-blend value was recorded anywhere
    at all.

    With ``model_points_pre`` and ``model_weight`` present a reader can check

        proj_points == model_weight * model_points_pre
                       + (1 - model_weight) * market_points

    directly, instead of assuming the weight and solving backwards.  A caller
    that does not supply the model side leaves these NULL: filling them by
    inversion would recreate the exact defect the columns exist to end.
    """
    out = frame.copy()
    out.insert(0, "generated_at", generated_at or datetime.now(timezone.utc))
    out.insert(1, "season", int(season))
    out.insert(2, "week", int(week))
    out["path"] = str(path)
    out["proj_points"] = (np.asarray(proj_points, dtype=float) if proj_points is not None else np.nan)
    out["model_points_pre"] = (
        np.asarray(model_points_pre, dtype=float) if model_points_pre is not None else np.nan)
    out["model_weight"] = (float(model_weight) if model_weight is not None else np.nan)
    return out
