"""Winner anatomy (2026-08-19): positive characterization of the 51
tracked Milly winners against the corpus, the field, and the law.

The winner-law audits used the winners to falsify hypotheses (N1d: the
score extremity is a field-max selection effect; N1c: winners are never
their worlds' optima; the stack finding: production rules exclude
43/51). This module extracts their POSITIVE structure — three descriptive
components, each answering a question the falsifications opened:

1. Roster distance (runner, via research.real_winner_overlap): how close
   does the registered pool or any selected book come to each winner in
   player space? Splits by the 8 production-constructible winners versus
   the 43 rule-violating ones — if the pool cannot approach even the
   constructible winners, stack relaxation is not their binding
   constraint.
2. Ownership profile: the winners' chalk-versus-leverage shape from the
   actual Millionaire contest ownership (nfl_raw.contest_ownership) —
   cumulative ownership, sub-5%/sub-10% leverage counts, and the
   duplication proxy (log10 of the ownership product).
3. World-optimum realism: N1c's optima sit a median 47 points above the
   winners in their own worlds — are those optima carried by per-player
   simulated scores beyond anything the player ever realized in the
   corpus? If yes, depth-harvested rosters are mirages and the marginal
   upper tail is a law defect; the winners' own draws are the control.

Descriptive and outcome-aware: realized ownership, realized maxima and
candidate actual scores are read. It fits nothing, gates nothing, and
licenses nothing; its one downstream use is to sharpen the
stack-relaxation freeze. Pure computation lives here; BQ/artifact IO
stays in the runner so this module remains offline-testable.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

PROTOCOL_ID = "20260819-winner-anatomy-v1"
ROSTER_SIZE = 9
LEVERAGE_THRESHOLDS = (5.0, 10.0)
# DST nickname resolution reuses research.real_winner_overlap's
# _TEAM_NICKNAMES (single source of truth); this module only needs the
# code-alias equivalence below.
# Team-code spellings that refer to the same franchise across sources.
TEAM_CODE_ALIASES = (
    {"JAX", "JAC"}, {"WAS", "WSH"}, {"LAR", "LA"}, {"LV", "OAK"},
)


class WinnerAnatomyError(ValueError):
    """Fail-closed contract violation."""


def same_team_code(first: str, second: str) -> bool:
    a, b = str(first).upper(), str(second).upper()
    if a == b:
        return True
    return any(a in group and b in group for group in TEAM_CODE_ALIASES)


def ownership_profile(pcts: Sequence[float | None]) -> dict:
    """Chalk/leverage shape of one nine-slot roster's ownership."""
    if len(pcts) != ROSTER_SIZE:
        raise WinnerAnatomyError("ownership profile needs nine slots")
    matched = [float(p) for p in pcts if p is not None]
    if any(not 0.0 < p <= 100.0 for p in matched):
        raise WinnerAnatomyError("ownership percentages outside (0, 100]")
    profile: dict = {"n_matched": len(matched)}
    if not matched:
        return {**profile, "sum_pct": None, "min_pct": None,
                "max_pct": None, "log10_product": None,
                **{f"n_below_{int(t)}": None for t in LEVERAGE_THRESHOLDS}}
    arr = np.asarray(matched, dtype=np.float64)
    profile.update({
        "sum_pct": float(arr.sum()),
        "min_pct": float(arr.min()),
        "max_pct": float(arr.max()),
        # Duplication proxy: log10 of the product of ownership fractions;
        # comparable across winners only at equal n_matched.
        "log10_product": float(np.log10(arr / 100.0).sum()),
    })
    for threshold in LEVERAGE_THRESHOLDS:
        profile[f"n_below_{int(threshold)}"] = int((arr < threshold).sum())
    return profile


def optimum_realism(
    world_scores: Mapping[str, float],
    realized_max: Mapping[str, float],
    roster: Sequence[str],
) -> dict:
    """How much of a roster's simulated world total is beyond reality?

    ``world_scores``: player id -> simulated score in the solved world;
    ``realized_max``: player id -> the player's maximum realized score
    across the corpus. Players absent from ``realized_max`` (never
    scored in the corpus) count as beyond-max at any positive score and
    are reported separately.
    """
    ids = [str(p) for p in roster]
    if len(ids) != ROSTER_SIZE or len(set(ids)) != ROSTER_SIZE:
        raise WinnerAnatomyError("realism roster must hold nine unique ids")
    missing = [p for p in ids if p not in world_scores]
    if missing:
        raise WinnerAnatomyError(
            f"roster players lack world scores: {missing[:3]}")
    beyond: list[str] = []
    unseen: list[str] = []
    excess = 0.0
    max_single = 0.0
    for player in ids:
        sim = float(world_scores[player])
        ceiling = realized_max.get(player)
        if ceiling is None:
            unseen.append(player)
            continue
        gap = sim - float(ceiling)
        if gap > 0:
            beyond.append(player)
            excess += gap
            max_single = max(max_single, gap)
    return {
        "n_beyond_realized_max": len(beyond),
        "players_beyond": sorted(beyond),
        "n_never_realized": len(unseen),
        "excess_total": float(excess),
        "max_single_excess": float(max_single),
    }


def anatomy_report(entries: Sequence[dict]) -> dict:
    """Aggregate the frozen anatomy report over per-winner entries.

    Each entry carries season/week/production_valid plus the component
    payloads: ``overlap`` ({"pool": {...}, "selected": {...},
    "exact_winner_in_pool": bool}), ``ownership`` (from
    :func:`ownership_profile`) and ``realism`` ({"optimum": ...,
    "winner": ...} from :func:`optimum_realism`).
    """
    if not entries:
        raise WinnerAnatomyError("no winner entries to aggregate")
    frame = pd.DataFrame([
        {
            "season": int(e["season"]),
            "week": int(e["week"]),
            "constructible": bool(e["production_valid"]),
            "pool_max_overlap": int(e["overlap"]["pool"]["max_overlap"]),
            "selected_max_overlap": int(
                e["overlap"]["selected"]["max_overlap"]),
            "exact_in_pool": bool(e["overlap"]["exact_winner_in_pool"]),
            "own_matched": (
                None if e["ownership"] is None
                else int(e["ownership"]["n_matched"])),
            "own_sum": (
                None if e["ownership"] is None
                else e["ownership"]["sum_pct"]),
            "own_below_10": (
                None if e["ownership"] is None
                else e["ownership"]["n_below_10"]),
            "optimum_beyond": int(
                e["realism"]["optimum"]["n_beyond_realized_max"]),
            "optimum_excess": float(e["realism"]["optimum"]["excess_total"]),
            "winner_beyond": int(
                e["realism"]["winner"]["n_beyond_realized_max"]),
            "winner_excess": float(e["realism"]["winner"]["excess_total"]),
        }
        for e in entries
    ])
    if frame.duplicated(["season", "week"]).any():
        raise WinnerAnatomyError("duplicate winner slates in the entries")

    def overlap_block(rows: pd.DataFrame) -> dict:
        return {
            "n": int(len(rows)),
            "pool_max_overlap_median": float(
                rows.pool_max_overlap.median()),
            "pool_max_overlap_min": int(rows.pool_max_overlap.min()),
            "pool_at_or_above_7": int((rows.pool_max_overlap >= 7).sum()),
            "selected_max_overlap_median": float(
                rows.selected_max_overlap.median()),
            "n_exact_in_pool": int(rows.exact_in_pool.sum()),
        }

    owned = frame[frame.own_sum.notna()]
    realism_beyond = frame.optimum_beyond
    return {
        "protocol_id": PROTOCOL_ID,
        "n_winners": int(len(frame)),
        "overlap": {
            "all": overlap_block(frame),
            "constructible": overlap_block(frame[frame.constructible]),
            "rule_violating": overlap_block(frame[~frame.constructible]),
        },
        "ownership": {
            "n_with_ownership": int(len(owned)),
            "sum_pct_median": (
                float(owned.own_sum.median()) if len(owned) else None),
            "sum_pct_q25": (
                float(owned.own_sum.quantile(0.25)) if len(owned) else None),
            "sum_pct_q75": (
                float(owned.own_sum.quantile(0.75)) if len(owned) else None),
            "below_10_median": (
                float(owned.own_below_10.median()) if len(owned) else None),
            "fully_matched": int((owned.own_matched == ROSTER_SIZE).sum()),
        },
        "realism": {
            "optima_with_any_beyond_max": int((realism_beyond > 0).sum()),
            "optimum_beyond_median": float(realism_beyond.median()),
            "optimum_excess_median": float(frame.optimum_excess.median()),
            "winners_with_any_beyond_max": int(
                (frame.winner_beyond > 0).sum()),
            "winner_beyond_median": float(frame.winner_beyond.median()),
            "winner_excess_median": float(frame.winner_excess.median()),
        },
        "winners": list(entries),
        # Outcome-aware descriptive diagnostic; flags are literal.
        "uses_realized_outcomes": True,
        "fit_performed": False,
        "tuning_performed": False,
        "gate_decision": None,
        "production_change_licensed": False,
    }
