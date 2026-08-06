"""Workstream C honest control (SCHAAKE_DIAG=1).

The offline gate compared empirical templates against INDEPENDENT
draws, which our production simulator is not — the possession-Markov
engine already induces correlation. This runs the A/B inside the real
replay: identical marginals, production joint vs template joint,
scored against the realized outcomes of the same players.

Emits one log line per (season, week) that the panel harvester can
grep, so no extra storage is needed.
"""
from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

from .schaake import apply_schaake_game, build_game_bank, match_templates

log = logging.getLogger(__name__)

PAIRS = (("QB", "WR1", "same"), ("QB", "WR2", "same"),
         ("QB", "QB", "opp"), ("WR1", "WR2", "same"),
         ("RB1", "DST", "same"))
_BANK: pd.DataFrame | None = None


def _roles(rows: pd.DataFrame) -> pd.Series:
    out = pd.Series([None] * len(rows), index=rows.index, dtype=object)
    if "salary" not in rows.columns:
        return out
    keys = [c for c in ("season", "week", "team", "position")
            if c in rows.columns]
    for _k, g in rows.groupby(keys):
        # NaN salaries (DST rows, missing prices) make rank() return
        # NaN — int(NaN) raised and killed the whole diagnostic.
        order = g.salary.rank(ascending=False, method="first")
        for idx, k in order.items():
            if pd.isna(k):
                continue
            k = int(k)
            if pos == "QB" and k == 1:
                out[idx] = "QB"
            elif pos == "DST" and k == 1:
                out[idx] = "DST"
            elif pos in ("RB", "WR") and k <= 3:
                out[idx] = f"{pos}{k}"
            elif pos == "TE" and k == 1:
                out[idx] = "TE1"
    return out


def _pair_corr(draws: np.ndarray, meta: pd.DataFrame) -> dict:
    out = {}
    for a, b, rel in PAIRS:
        cs = []
        gkeys = [c for c in ("season", "week", "game_id")
                 if c in meta.columns]
        for _gk, g in meta.groupby(gkeys):
            teams = sorted(pd.unique(g.team.dropna()))
            todo = []
            if rel == "same":
                for t in teams:
                    ia = g[(g.team == t) & (g.role == a)].index
                    ib = g[(g.team == t) & (g.role == b)].index
                    if len(ia) and len(ib) and a != b:
                        todo.append((ia[0], ib[0]))
            elif len(teams) == 2:
                ia = g[(g.team == teams[0]) & (g.role == a)].index
                ib = g[(g.team == teams[1]) & (g.role == b)].index
                if len(ia) and len(ib):
                    todo.append((ia[0], ib[0]))
            for i, j in todo:
                x, y = draws[i], draws[j]
                if x.std() > 1e-9 and y.std() > 1e-9:
                    cs.append(float(np.corrcoef(x, y)[0, 1]))
        out[f"{a}{b}{rel[:1]}"] = float(np.mean(cs)) if cs else np.nan
    return out


def _pair_indices(meta: pd.DataFrame) -> dict[str, list[tuple[int, int]]]:
    """Role-pair row indices used by every diagnostic metric."""
    out: dict[str, list[tuple[int, int]]] = {}
    for a, b, rel in PAIRS:
        key = f"{a}{b}{rel[:1]}"
        pairs: list[tuple[int, int]] = []
        for _, g in meta.groupby("game_id"):
            teams = sorted(pd.unique(g.team.dropna()))
            if rel == "same":
                for team in teams:
                    ia = g[(g.team == team) & (g.role == a)].index
                    ib = g[(g.team == team) & (g.role == b)].index
                    if len(ia) and len(ib) and a != b:
                        pairs.append((int(ia[0]), int(ib[0])))
            elif len(teams) == 2:
                ia = g[(g.team == teams[0]) & (g.role == a)].index
                ib = g[(g.team == teams[1]) & (g.role == b)].index
                if len(ia) and len(ib):
                    pairs.append((int(ia[0]), int(ib[0])))
        out[key] = pairs
    return out


def realized_dependence_scores(draws: np.ndarray, actual: np.ndarray,
                               meta: pd.DataFrame) -> dict[str, float]:
    """Proper held-out scores for a joint forecast, lower is better.

    Each player is standardized by its own forecast marginal.  Since a
    valid Schaake shuffle leaves those marginals unchanged, differences in
    these scores are attributable to the joint distribution rather than a
    change in player means or spreads.
    """
    mu = draws.mean(axis=1)
    sd = np.maximum(draws.std(axis=1), 1e-6)
    z = (draws - mu[:, None]) / sd[:, None]
    y = (np.asarray(actual, dtype=float) - mu) / sd
    variogram, tail = [], []
    for pairs in _pair_indices(meta).values():
        for i, j in pairs:
            if not (np.isfinite(y[i]) and np.isfinite(y[j])):
                continue
            predicted = np.mean(np.abs(z[i] - z[j]) ** 0.5)
            observed = abs(y[i] - y[j]) ** 0.5
            variogram.append((predicted - observed) ** 2)
            qi, qj = np.quantile(draws[i], 0.90), np.quantile(draws[j], 0.90)
            p_joint = np.mean((draws[i] > qi) & (draws[j] > qj))
            event = float((actual[i] > qi) and (actual[j] > qj))
            tail.append((p_joint - event) ** 2)
    return {
        "variogram": float(np.mean(variogram)) if variogram else np.nan,
        "tail_brier": float(np.mean(tail)) if tail else np.nan,
        "n_pairs": float(len(variogram)),
    }


def _bank(rows: pd.DataFrame) -> pd.DataFrame:
    """Point-in-time bank: only games STRICTLY BEFORE this slate."""
    global _BANK
    if _BANK is None:
        from ..bq import query_df
        season = int(rows.season.iloc[0])
        _BANK = query_df(f"""
          SELECT season, week, y_dk_points AS dk_points,
                 position AS pos, team, salary, game_id, game_total,
                 ABS(spread) AS spread_abs, pace_env_l6,
                 neutral_pass_rate_l6, team_top2_target_share_l6
          FROM `nfl_features.player_week_training`
          WHERE season < {season} AND week <= 18
            AND position IN ('QB','RB','WR','TE')
            AND game_total IS NOT NULL AND salary IS NOT NULL""")
        _BANK["role"] = None
        for (se, wk, tm, pos), g in _BANK.groupby(
                ["season", "week", "team", "pos"]):
            order = g.salary.rank(ascending=False, method="first")
            for idx, k in order.items():
                k = int(k)
                if pos == "QB" and k == 1:
                    _BANK.at[idx, "role"] = "QB"
                elif pos in ("RB", "WR") and k <= 3:
                    _BANK.at[idx, "role"] = f"{pos}{k}"
                elif pos == "TE" and k == 1:
                    _BANK.at[idx, "role"] = "TE1"
        _BANK = build_game_bank(_BANK)
        log.info("schaake bank: %d historical GAME templates", len(_BANK))
    return _BANK


def log_dependence_ab(rows: pd.DataFrame, draws: np.ndarray) -> None:
    meta = rows.reset_index(drop=True).copy()
    if "spread_abs" not in meta and "spread" in meta:
        meta["spread_abs"] = pd.to_numeric(meta["spread"],
                                            errors="coerce").abs()
    meta["role"] = _roles(meta)
    if "game_id" not in meta.columns or meta.role.isna().all():
        return
    bank = _bank(meta)
    if bank.empty:
        return
    season = int(meta.season.iloc[0])
    k = int(os.environ.get("SCHAAKE_K", "40"))
    sh = draws.copy()
    for (wk, gid), g in meta.groupby(["week", "game_id"]):
        week = int(wk)
        ctx = {}
        for c in ("game_total", "spread_abs", "pace_env_l6",
                  "neutral_pass_rate_l6", "team_top2_target_share_l6"):
            if c in g.columns and pd.to_numeric(g[c], errors="coerce").notna().any():
                ctx[c] = float(pd.to_numeric(g[c], errors="coerce").mean())
        t = match_templates(bank, ctx, season, week, k=k)
        if t.empty:
            continue
        idx = g.index.to_numpy()
        sh[idx] = apply_schaake_game(draws[idx], meta.role.iloc[idx],
                                     meta.team.iloc[idx].to_numpy(), t,
                                     seed=week)
    prod, schk = _pair_corr(draws, meta), _pair_corr(sh, meta)
    actual_col = "y_dk_points" if "y_dk_points" in meta else "actual"
    if actual_col not in meta:
        log.warning("schaake-ab %s wk%s: realized outcomes unavailable",
                    season, week)
        return
    ps = realized_dependence_scores(draws, meta[actual_col].to_numpy(), meta)
    ss = realized_dependence_scores(sh, meta[actual_col].to_numpy(), meta)
    missing_pairs = [name for name, pairs in _pair_indices(meta).items()
                     if not pairs]
    marginal_ok = all(np.array_equal(np.sort(draws[i]), np.sort(sh[i]))
                      for i in range(len(draws)))
    log.info("schaake-ab %s wk%s prod=%s schaake=%s scores_prod=%s "
             "scores_schaake=%s marginal_exact=%s missing_pairs=%s",
             season, week,
             {k2: round(v, 3) for k2, v in prod.items()},
             {k2: round(v, 3) for k2, v in schk.items()},
             {k2: round(v, 5) for k2, v in ps.items()},
             {k2: round(v, 5) for k2, v in ss.items()}, marginal_ok,
             missing_pairs)
    if missing_pairs:
        log.warning("schaake gate incomplete for %s wk%s: no observations "
                    "for %s", season, week, missing_pairs)
