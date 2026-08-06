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
         ("QB", "QB", "opp"), ("WR1", "WR2", "same"))
_BANK: pd.DataFrame | None = None


def _roles(rows: pd.DataFrame) -> pd.Series:
    out = pd.Series([None] * len(rows), index=rows.index, dtype=object)
    if "salary" not in rows.columns:
        return out
    for (tm, pos), g in rows.groupby(["team", "position"]):
        # NaN salaries (DST rows, missing prices) make rank() return
        # NaN — int(NaN) raised and killed the whole diagnostic.
        order = g.salary.rank(ascending=False, method="first")
        for idx, k in order.items():
            if pd.isna(k):
                continue
            k = int(k)
            if pos == "QB" and k == 1:
                out[idx] = "QB"
            elif pos in ("RB", "WR") and k <= 3:
                out[idx] = f"{pos}{k}"
            elif pos == "TE" and k == 1:
                out[idx] = "TE1"
    return out


def _pair_corr(draws: np.ndarray, meta: pd.DataFrame) -> dict:
    out = {}
    for a, b, rel in PAIRS:
        cs = []
        for gid, g in meta.groupby("game_id"):
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


def _bank(rows: pd.DataFrame) -> pd.DataFrame:
    """Point-in-time bank: only games STRICTLY BEFORE this slate."""
    global _BANK
    if _BANK is None:
        from ..bq import query_df
        season = int(rows.season.iloc[0])
        _BANK = query_df(f"""
          SELECT a.season, a.week, a.dk_points, u.position AS pos, u.team,
                 s.salary, sc.game_id, sc.total_line,
                 ABS(sc.spread_line) AS spread_abs,
                 (sc.total_line + sc.spread_line)/2 AS implied_team_total
          FROM `nfl_features.player_week_actuals` a
          JOIN `nfl_features.player_week_usage` u USING (gsis_id, season, week)
          JOIN `nfl_features.dk_salary_week` s USING (gsis_id, season, week)
          JOIN `nfl_raw.schedules` sc ON sc.season=a.season AND sc.week=a.week
               AND (sc.home_team=u.team OR sc.away_team=u.team)
          WHERE a.season < {season} AND a.week <= 18
            AND u.position IN ('QB','RB','WR','TE')
            AND sc.total_line IS NOT NULL""")
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
    meta["role"] = _roles(meta)
    if "game_id" not in meta.columns or meta.role.isna().all():
        return
    bank = _bank(meta)
    if bank.empty:
        return
    season, week = int(meta.season.iloc[0]), int(meta.week.iloc[0])
    k = int(os.environ.get("SCHAAKE_K", "40"))
    sh = draws.copy()
    for gid, g in meta.groupby("game_id"):
        ctx = {}
        for c in ("total_line", "spread_abs", "implied_team_total"):
            if c in g.columns and pd.notna(g[c].iloc[0]):
                ctx[c] = float(g[c].iloc[0])
        t = match_templates(bank, ctx, season, week, k=k)
        if t.empty:
            continue
        idx = g.index.to_numpy()
        sh[idx] = apply_schaake_game(draws[idx], meta.role.iloc[idx],
                                     meta.team.iloc[idx].to_numpy(), t,
                                     seed=week)
    prod, schk = _pair_corr(draws, meta), _pair_corr(sh, meta)
    err_p = sum(abs(prod[k2] - schk[k2]) for k2 in prod
                if np.isfinite(prod[k2]) and np.isfinite(schk[k2]))
    log.info("schaake-ab %s wk%s prod=%s schaake=%s l1_gap=%.3f",
             season, week,
             {k2: round(v, 3) for k2, v in prod.items()},
             {k2: round(v, 3) for k2, v in schk.items()}, err_p)
