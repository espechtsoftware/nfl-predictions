"""Held-out production-vs-Schaake dependence gate.

The replay calls this once with a whole season.  It applies the empirical
game-template copula separately to every game, preserves every player's
marginal draw multiset exactly, and scores both joints against realized
outcomes.  Machine-readable week and season summaries make silent diagnostic
failure impossible to confuse with a successful scientific result.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os

import numpy as np
import pandas as pd

from .schaake import apply_schaake_game, build_game_bank, match_templates

log = logging.getLogger(__name__)

PAIR_SPECS = (("QB", "WR1", "same"), ("QB", "WR2", "same"),
              ("QB", "QB", "opp"), ("WR1", "WR2", "same"))
REQUIRED_PAIR_KEYS = tuple(f"{a}{b}{rel[:1]}" for a, b, rel in PAIR_SPECS)
_BANK: pd.DataFrame | None = None


def _stable_game_seed(season: int, week: int, game_id: object,
                      base: int = 0) -> int:
    """Stable, distinct seed per game (never Python's salted hash)."""
    raw = f"{base}|{season}|{week}|{game_id}".encode()
    return int.from_bytes(hashlib.blake2b(raw, digest_size=8).digest(),
                          "little")


def _roles(rows: pd.DataFrame) -> pd.Series:
    """Salary-defined roles independently for every team-week-position."""
    out = pd.Series([None] * len(rows), index=rows.index, dtype=object)
    if not {"salary", "team", "position"}.issubset(rows.columns):
        return out
    keys = [c for c in ("season", "week", "team", "position")
            if c in rows.columns]
    for _, group in rows.groupby(keys, dropna=False):
        pos = str(group["position"].iloc[0])
        order = group.salary.rank(ascending=False, method="first")
        for idx, rank in order.items():
            if pd.isna(rank):
                continue
            rank = int(rank)
            if pos == "QB" and rank == 1:
                out[idx] = "QB"
            elif pos == "DST" and rank == 1:
                out[idx] = "DST"
            elif pos in ("RB", "WR") and rank <= 3:
                out[idx] = f"{pos}{rank}"
            elif pos == "TE" and rank == 1:
                out[idx] = "TE1"
    return out


def _pair_indices(meta: pd.DataFrame) -> dict[str, list[tuple[int, int]]]:
    """Row-index pairs at game grain; game ids need not be globally unique."""
    out: dict[str, list[tuple[int, int]]] = {}
    group_cols = [c for c in ("season", "week", "game_id")
                  if c in meta.columns]
    for a, b, relation in PAIR_SPECS:
        key = f"{a}{b}{relation[:1]}"
        pairs: list[tuple[int, int]] = []
        for _, game in meta.groupby(group_cols, dropna=False):
            teams = sorted(pd.unique(game.team.dropna()))
            if relation == "same":
                for team in teams:
                    ia = game[(game.team == team) & (game.role == a)].index
                    ib = game[(game.team == team) & (game.role == b)].index
                    if len(ia) and len(ib) and a != b:
                        pairs.append((int(ia[0]), int(ib[0])))
            elif len(teams) == 2:
                ia = game[(game.team == teams[0]) & (game.role == a)].index
                ib = game[(game.team == teams[1]) & (game.role == b)].index
                if len(ia) and len(ib):
                    pairs.append((int(ia[0]), int(ib[0])))
        out[key] = pairs
    return out


def dependence_scores(draws: np.ndarray, actual: np.ndarray,
                      meta: pd.DataFrame) -> dict:
    """Role-pair variogram and joint-q90 Brier scores (lower is better)."""
    mu = draws.mean(axis=1)
    sd = np.maximum(draws.std(axis=1), 1e-6)
    z = (draws - mu[:, None]) / sd[:, None]
    y = (np.asarray(actual, dtype=float) - mu) / sd
    by_pair = {}
    all_variogram, all_tail = [], []
    for key, pairs in _pair_indices(meta).items():
        variogram, tail = [], []
        for i, j in pairs:
            if not (np.isfinite(y[i]) and np.isfinite(y[j])):
                continue
            predicted = np.mean(np.abs(z[i] - z[j]) ** 0.5)
            observed = abs(y[i] - y[j]) ** 0.5
            variogram.append(float((predicted - observed) ** 2))
            qi = float(np.quantile(draws[i], 0.90))
            qj = float(np.quantile(draws[j], 0.90))
            probability = float(np.mean((draws[i] > qi) & (draws[j] > qj)))
            event = float((actual[i] > qi) and (actual[j] > qj))
            tail.append((probability - event) ** 2)
        all_variogram.extend(variogram)
        all_tail.extend(tail)
        by_pair[key] = {
            "n": len(variogram),
            "variogram": float(np.mean(variogram)) if variogram else None,
            "tail_brier": float(np.mean(tail)) if tail else None,
        }
    return {
        "n_pairs": len(all_variogram),
        "variogram": (float(np.mean(all_variogram))
                       if all_variogram else None),
        "tail_brier": float(np.mean(all_tail)) if all_tail else None,
        "by_pair": by_pair,
    }


def realized_dependence_scores(draws: np.ndarray, actual: np.ndarray,
                               meta: pd.DataFrame) -> dict[str, float]:
    """Backward-compatible aggregate view used by existing tests."""
    report = dependence_scores(draws, actual, meta)
    return {k: report[k] for k in ("variogram", "tail_brier", "n_pairs")}


def _bank(rows: pd.DataFrame) -> pd.DataFrame:
    """Historical skill-player templates from seasons before the replay."""
    global _BANK
    if _BANK is None:
        from ..bq import query_df

        season = int(rows.season.iloc[0])
        _BANK = query_df(f"""
          SELECT season, week, y_dk_points AS dk_points,
                 position AS pos, team, salary, game_id, game_total,
                 implied_team_total, ABS(spread) AS spread_abs, pace_env_l6,
                 neutral_pass_rate_l6, team_top2_target_share_l6
          FROM `nfl_features.player_week_training`
          WHERE season < {season} AND week <= 18
            AND position IN ('QB','RB','WR','TE')
            AND game_total IS NOT NULL AND salary IS NOT NULL""")
        _BANK["role"] = None
        for (_, _, _, pos), group in _BANK.groupby(
                ["season", "week", "team", "pos"]):
            order = group.salary.rank(ascending=False, method="first")
            for idx, rank in order.items():
                if pd.isna(rank):
                    continue
                rank = int(rank)
                if pos == "QB" and rank == 1:
                    _BANK.at[idx, "role"] = "QB"
                elif pos in ("RB", "WR") and rank <= 3:
                    _BANK.at[idx, "role"] = f"{pos}{rank}"
                elif pos == "TE" and rank == 1:
                    _BANK.at[idx, "role"] = "TE1"
        _BANK = build_game_bank(_BANK)
        log.info("schaake bank: %d historical game templates", len(_BANK))
    return _BANK


def _metric_better(candidate, control) -> bool:
    return (candidate is not None and control is not None
            and np.isfinite(candidate) and np.isfinite(control)
            and candidate < control)


def log_dependence_ab(rows: pd.DataFrame, draws: np.ndarray) -> dict:
    """Run and log the complete season gate; return its structured report."""
    meta = rows.reset_index(drop=True).copy()
    if "spread_abs" not in meta and "spread" in meta:
        meta["spread_abs"] = pd.to_numeric(meta["spread"],
                                            errors="coerce").abs()
    meta["role"] = _roles(meta)
    if "game_id" not in meta.columns or meta.role.isna().all():
        raise ValueError("Schaake diagnostic has no role-mapped games")
    bank = _bank(meta)
    if bank.empty:
        raise ValueError("Schaake diagnostic template bank is empty")

    season = int(meta.season.iloc[0])
    neighbors = int(os.environ.get("SCHAAKE_K", "40"))
    shuffled = draws.copy()
    for (week_value, game_id), game in meta.groupby(["week", "game_id"]):
        week = int(week_value)
        context = {}
        for col in ("game_total", "spread_abs", "pace_env_l6",
                    "neutral_pass_rate_l6", "team_top2_target_share_l6"):
            values = (pd.to_numeric(game[col], errors="coerce")
                      if col in game else pd.Series(dtype=float))
            if values.notna().any():
                context[col] = float(values.mean())
        templates = match_templates(bank, context, season, week, k=neighbors)
        if templates.empty:
            continue
        idx = game.index.to_numpy()
        team_values = (meta.implied_team_total.iloc[idx].to_numpy()
                       if "implied_team_total" in meta else None)
        shuffled[idx] = apply_schaake_game(
            draws[idx], meta.role.iloc[idx], meta.team.iloc[idx].to_numpy(),
            templates, seed=_stable_game_seed(season, week, game_id),
            team_values=team_values)

    actual_col = "y_dk_points" if "y_dk_points" in meta else "actual"
    if actual_col not in meta:
        raise ValueError("Schaake diagnostic realized outcomes unavailable")
    actual = meta[actual_col].to_numpy(dtype=float)
    marginal_exact = all(
        np.array_equal(np.sort(draws[i]), np.sort(shuffled[i]))
        for i in range(len(draws)))

    weekly = []
    for week, week_meta in meta.groupby("week"):
        idx = week_meta.index.to_numpy()
        local_meta = week_meta.reset_index(drop=True)
        prod = dependence_scores(draws[idx], actual[idx], local_meta)
        sch = dependence_scores(shuffled[idx], actual[idx], local_meta)
        record = {"season": season, "week": int(week),
                  "production": prod, "schaake": sch}
        weekly.append(record)
        log.info("schaake-week %s", json.dumps(record, sort_keys=True))

    production = dependence_scores(draws, actual, meta)
    schaake = dependence_scores(shuffled, actual, meta)
    missing = [key for key in REQUIRED_PAIR_KEYS
               if production["by_pair"][key]["n"] == 0]
    complete = not missing
    gate_pass = bool(
        marginal_exact and complete
        and _metric_better(schaake["variogram"], production["variogram"])
        and _metric_better(schaake["tail_brier"], production["tail_brier"]))
    report = {
        "season": season,
        "marginal_exact": marginal_exact,
        "required_pairs_complete": complete,
        "missing_pairs": missing,
        "production": production,
        "schaake": schaake,
        "gate_pass": gate_pass,
        "weeks": len(weekly),
        "scope_note": "skill-player copula; DST has no production marginal draws",
    }
    log.info("schaake-gate %s", json.dumps(report, sort_keys=True))
    if os.environ.get("SCHAAKE_DIAG_STRICT") and (
            not marginal_exact or not complete or len(weekly) < 1):
        raise RuntimeError("Schaake mechanism gate incomplete: "
                           + json.dumps(report, sort_keys=True))
    return report


def cloud_smoke() -> dict:
    """Dependency-free image smoke test used before an expensive replay."""
    rows = []
    for week in (1, 2):
        for team, opp in (("A", "B"), ("B", "A")):
            for pos, salaries in (("QB", [7000]), ("RB", [6500, 5200]),
                                  ("WR", [7200, 6100, 4300]), ("TE", [4000])):
                for rank, salary in enumerate(salaries):
                    rows.append({"season": 2025, "week": week, "team": team,
                                 "opponent": opp, "game_id": f"g{week}",
                                 "position": pos, "salary": salary - rank})
    frame = pd.DataFrame(rows)
    roles = _roles(frame)
    assert (roles == "QB").sum() == 4
    assert (roles == "WR1").sum() == 4
    assert _stable_game_seed(2025, 1, "g1") != _stable_game_seed(2025, 1, "g2")

    rng = np.random.default_rng(7)
    draws = rng.normal(size=(4, 1000))
    templates = pd.DataFrame({"QB_fav": [0.1, 0.4, 0.8],
                              "WR1_fav": [0.2, 0.5, 0.9],
                              "QB_dog": [0.2, 0.6, 0.7],
                              "WR1_dog": [0.1, 0.3, 0.8]})
    shuffled = apply_schaake_game(
        draws, pd.Series(["QB", "WR1", "QB", "WR1"]),
        np.array(["A", "A", "B", "B"]), templates, seed=11,
        team_values=np.array([25.0, 25.0, 20.0, 20.0]))
    assert all(np.array_equal(np.sort(a), np.sort(b))
               for a, b in zip(draws, shuffled))
    result = {"status": "PASS", "role_rows": int(roles.notna().sum()),
              "marginal_rows": len(draws), "distinct_game_seeds": True}
    print("schaake-smoke " + json.dumps(result, sort_keys=True))
    return result
