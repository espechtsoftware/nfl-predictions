"""SBI observation-summary builder (Workstream B, plan §6.4).

From a DK-point draws matrix (n_players, n_sims) plus each player's role,
team, and game label, compute the summary vector that both observed data
and simulator output are reduced to for inference:

- marginal moments and registered upper quantiles by role;
- catcher spike/shape stats targeted at TD-allocation burstiness;
- within-team point-share concentration (mean HHI, top-share dispersion);
- dependence on the REGISTERED role pairs (instrument #0): pair discovery
  is reused from `research.dependence.role_pair_indices`, and the
  sim-side upper-tail co-occurrence comes from
  `research.dependence.tail_cooccurrence` — same pairs, same quantile
  convention as the mechanism gate, so §6.8's real-data step scores the
  posterior with the identical instrument;
- a reconciliation-style statistic: the variance ratio of the team passing
  unit (QB + catchers) versus independence, which is what the TD ledger's
  same-event coupling moves. True yardage-level passing-vs-receiving
  reconciliation gaps need stat-line draws the simulator does not retain
  in v0 — noted for §6.8's real-data step.

Everything is deterministic given the draws matrix. Normalization (§6.4:
training-only location/scale) is the CALLER's job — the ABC script
normalizes by reference-table dispersion; raw summaries are what this
module returns, retained for posterior predictive checks.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .dependence import role_pair_indices, tail_cooccurrence

__all__ = ["summarize", "SUMMARY_ROLES"]

SUMMARY_ROLES = ("QB", "RB", "WR", "TE")

# Registered pair types consumed from the dependence suite. rb_own_dst is
# omitted in v0: the synthetic slate (and the simulator's comps frame)
# carries no DST rows.
_PAIR_CORRS = ("qb_wr1_same_team", "qb_opp_qb", "wr1_wr2_same_team")
_TAIL_PAIR = "qb_wr1_same_team"
_TAIL_Q = 0.90


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if a.std() <= 0 or b.std() <= 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _slot_roles(draws: np.ndarray, roles: np.ndarray, teams: np.ndarray) -> np.ndarray:
    """Map generic position labels to the dependence suite's slot labels
    (WR1/WR2 by mean simulated points within team, RB1 likewise, QB kept).
    Deterministic given the draws matrix."""
    # unique filler labels: role_pair_indices ignores unregistered roles
    # but warns on duplicates within a (game, team)
    slots = np.array([f"OTHER{i}" for i in range(len(roles))], dtype=object)
    means = draws.mean(axis=1)
    for t in np.unique(teams):
        rows = np.flatnonzero(teams == t)
        for role, labels in (("WR", ("WR1", "WR2")), ("RB", ("RB1",))):
            cand = rows[roles[rows] == role]
            ranked = cand[np.argsort(-means[cand])]
            for label, ix in zip(labels, ranked):
                slots[ix] = label
        for ix in rows[roles[rows] == "QB"]:
            slots[ix] = "QB"
    return slots


def summarize(
    draws: np.ndarray,
    roles: np.ndarray,
    teams: np.ndarray | pd.Series,
    games: np.ndarray | pd.Series,
) -> pd.Series:
    """Named summary vector from a (n_players, n_sims) DK-point draws
    matrix. Fixed key order — inference code relies on it."""
    draws = np.asarray(draws, dtype=float)
    roles = np.asarray(roles)
    teams = np.asarray(pd.Series(teams).astype(str))
    games = np.asarray(pd.Series(games).astype(str))
    out: dict[str, float] = {}

    # ---- marginal moments + upper quantiles by role (§6.4 bullet 1) ----
    for role in SUMMARY_ROLES:
        rows = np.flatnonzero(roles == role)
        if not len(rows):
            for stat in ("mean", "std", "zero_rate", "p90", "p95"):
                out[f"{role}_{stat}"] = 0.0
            continue
        d = draws[rows]
        out[f"{role}_mean"] = float(d.mean())
        out[f"{role}_std"] = float(d.std(axis=1).mean())
        out[f"{role}_zero_rate"] = float((d <= 0.0).mean())
        out[f"{role}_p90"] = float(np.percentile(d, 90, axis=1).mean())
        out[f"{role}_p95"] = float(np.percentile(d, 95, axis=1).mean())

    # ---- catcher spike/shape stats ----
    # Targeted at TD-allocation burstiness (td_alloc_k): a burstier TD
    # split shows up as multi-TD spike mass and heavier skew for WR/TE,
    # which the role-level std/p90 above dilute away — the first
    # truth-recovery run returned NOT-identifiable for td_alloc_k until
    # these were registered (§6.7: fix the summaries or drop the param).
    catch_rows = np.flatnonzero(np.isin(roles, ("WR", "TE")))
    if len(catch_rows):
        c = draws[catch_rows]
        mu = c.mean(axis=1, keepdims=True)
        sd = c.std(axis=1, keepdims=True)
        sd = np.where(sd > 0, sd, 1.0)
        z = (c - mu) / sd
        out["catcher_skew"] = float((z ** 3).mean())
        out["catcher_kurt"] = float((z ** 4).mean())
        # ~two-TD outlier games: 12+ points above the player's own mean
        out["catcher_spike_rate"] = float((c >= mu + 12.0).mean())
        out["catcher_p99"] = float(np.percentile(c, 99, axis=1).mean())
    else:
        out["catcher_skew"] = 0.0
        out["catcher_kurt"] = 0.0
        out["catcher_spike_rate"] = 0.0
        out["catcher_p99"] = 0.0

    # ---- within-team concentration (§6.4 bullet 2) ----
    hhis, top_stds = [], []
    for t in np.unique(teams):
        rows = np.flatnonzero(teams == t)
        if len(rows) < 2:
            continue
        pos = np.clip(draws[rows], 0.0, None)
        tot = pos.sum(axis=0)
        ok = tot > 0
        if not ok.any():
            continue
        shares = pos[:, ok] / tot[ok]
        hhis.append(float((shares ** 2).sum(axis=0).mean()))
        top_stds.append(float(shares.max(axis=0).std()))
    out["team_hhi_mean"] = float(np.mean(hhis)) if hhis else 0.0
    out["team_top_share_std"] = float(np.mean(top_stds)) if top_stds else 0.0

    # ---- dependence on registered role pairs (§6.4 bullets 3-5) ----
    slots = _slot_roles(draws, roles, teams)
    pairs = role_pair_indices(slots, teams, games)
    for name in _PAIR_CORRS:
        plist = pairs.get(name, [])
        corrs = [_safe_corr(draws[i], draws[j]) for i, j in plist]
        out[f"{name}_corr"] = float(np.mean(corrs)) if corrs else 0.0
    # Sim-side joint upper-tail rate on the registered QB-WR1 pair, via
    # the shared instrument. Only the "sim" component is meaningful here
    # (there are no actuals inside a summary vector); expressed as lift
    # over independence, 1.0 == independent.
    plist = pairs.get(_TAIL_PAIR, [])
    if plist:
        dummy = draws.mean(axis=1)  # placeholder actuals; "sim" ignores them
        rate = tail_cooccurrence(draws, dummy, plist, _TAIL_Q)["sim"]
        out["qb_wr1_tail_lift"] = float(rate / (1.0 - _TAIL_Q) ** 2)
    else:
        out["qb_wr1_tail_lift"] = 1.0

    # ---- reconciliation-style variance ratio (§6.4 bullet 6 proxy) ----
    var_ratios = []
    for t in np.unique(teams):
        rows = np.flatnonzero(teams == t)
        qb_rows = rows[roles[rows] == "QB"]
        catchers_rows = rows[np.isin(roles[rows], ("WR", "TE"))]
        if not len(qb_rows) or not len(catchers_rows):
            continue
        qb = draws[qb_rows].sum(axis=0)
        catchers = draws[catchers_rows].sum(axis=0)
        denom = qb.var() + catchers.var()
        if denom > 0:
            # >1 = positive coupling (same-event TDs, shared environment),
            # 1 = independence — the reconciliation-style ratio the TD
            # ledger and game factor jointly control.
            var_ratios.append(float((qb + catchers).var() / denom))
    out["team_pass_var_ratio"] = float(np.mean(var_ratios)) if var_ratios else 1.0

    return pd.Series(out)
