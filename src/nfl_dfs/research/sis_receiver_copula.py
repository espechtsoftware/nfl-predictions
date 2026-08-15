"""Receiver-specific, marginal-preserving SIS copula rank treatment."""

from __future__ import annotations

from hashlib import sha256
import json

import numpy as np
import pandas as pd


MIN_ROUTE_MASS = 0.50
POSITIONS = ("QB", "RB", "WR", "TE")


def stable_percentile_ranks(values: np.ndarray) -> np.ndarray:
    row = np.asarray(values)
    if row.ndim != 1 or len(row) < 2 or not np.isfinite(row).all():
        raise ValueError("receiver-copula rank row is invalid")
    order = np.argsort(row, kind="stable")
    ranks = np.empty(len(row), dtype=np.float64)
    ranks[order] = np.arange(len(row), dtype=np.float64)
    ranks /= float(len(row) - 1)
    return ranks


def build_receiver_context(
    frame: pd.DataFrame,
    player_profiles: pd.DataFrame,
    defense_prior: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Return scaled receiver scores and eligible WR rows on the served book."""
    required_frame = {
        "season", "week", "game_id", "team", "opp", "gsis_id",
        "position", "mean_projection",
    }
    required_profiles = {
        "season", "target_week", "team", "gsis_id", "position",
        "overall_routes", "wide_slot_routes", "player_wide_share",
        "alignment_supported",
    }
    required_defense = {
        "season", "target_week", "defense", "alignment",
        "vulnerability", "context_supported",
    }
    for supplied, required, label in (
        (frame, required_frame, "frame"),
        (player_profiles, required_profiles, "player profiles"),
        (defense_prior, required_defense, "defense prior"),
    ):
        if missing := required - set(supplied):
            raise ValueError(f"receiver-copula {label} missing {sorted(missing)}")
    if not frame.index.equals(pd.RangeIndex(len(frame))):
        raise ValueError("receiver-copula frame must have a canonical row index")
    if frame.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("receiver-copula frame repeats player weeks")
    resolved_profiles = player_profiles[player_profiles.gsis_id.notna()]
    if resolved_profiles.duplicated(
        ["season", "target_week", "gsis_id"]
    ).any():
        raise ValueError("receiver-copula player profiles repeat player weeks")
    if defense_prior.duplicated(
        ["season", "target_week", "defense", "alignment"]
    ).any():
        raise ValueError("receiver-copula defense prior repeats alignment cells")

    scores = np.zeros(len(frame), dtype=np.float64)
    eligible = np.zeros(len(frame), dtype=bool)
    group_keys: list[tuple[str, ...]] = []
    support_failures: dict[str, int] = {}

    def fail(reason: str) -> None:
        support_failures[reason] = support_failures.get(reason, 0) + 1

    supported_frame = frame[
        frame.position.isin(POSITIONS) & frame.mean_projection.ge(4.0)
    ]
    for key, group in supported_frame.groupby(
        ["season", "week", "game_id", "team"], sort=True, dropna=False,
    ):
        season, week, _game, team = key
        qbs = group.index[group.position.eq("QB")].to_numpy(int)
        if len(qbs) != 1:
            fail("qb-count")
            continue
        opponent_values = group.opp.dropna().astype(str).unique()
        if len(opponent_values) != 1:
            fail("opponent")
            continue
        opponent = opponent_values[0]
        profiles = player_profiles[
            player_profiles.season.eq(int(season))
            & player_profiles.target_week.eq(int(week))
            & player_profiles.team.eq(str(team))
            & player_profiles.position.eq("WR")
        ].copy()
        if profiles.empty:
            fail("player-profile")
            continue
        all_routes = pd.to_numeric(profiles.overall_routes, errors="coerce")
        denominator = float(all_routes[all_routes.ge(0)].sum())
        profile = profiles.set_index(profiles.gsis_id.astype(str), drop=False)
        wr_rows = group.index[group.position.eq("WR")].to_numpy(int)
        receiver_rows: list[int] = []
        receiver_routes: list[float] = []
        receiver_wide: list[float] = []
        for row in wr_rows:
            player = str(frame.at[row, "gsis_id"])
            if player not in profile.index:
                continue
            value = profile.loc[player]
            if isinstance(value, pd.DataFrame):
                raise ValueError("receiver-copula profile key is ambiguous")
            routes = float(value.overall_routes)
            wide_share = float(value.player_wide_share)
            if (
                not bool(value.alignment_supported)
                or not np.isfinite(routes) or routes <= 0
                or not np.isfinite(wide_share) or not 0 <= wide_share <= 1
            ):
                continue
            receiver_rows.append(int(row))
            receiver_routes.append(routes)
            receiver_wide.append(wide_share)
        if len(receiver_rows) < 2 or denominator <= 0:
            fail("receiver-support")
            continue
        supported_routes = float(sum(receiver_routes))
        route_mass = supported_routes / denominator
        if route_mass < MIN_ROUTE_MASS:
            fail("route-mass")
            continue
        defense = defense_prior[
            defense_prior.season.eq(int(season))
            & defense_prior.target_week.eq(int(week))
            & defense_prior.defense.eq(str(opponent))
            & defense_prior.alignment.isin(["wide", "slot"])
        ].copy()
        if (
            set(defense.alignment) != {"wide", "slot"}
            or not defense.context_supported.astype(bool).all()
        ):
            fail("defense-context")
            continue
        vulnerability = defense.set_index("alignment").vulnerability.astype(float)
        if not np.isfinite(vulnerability.to_numpy()).all():
            fail("defense-context")
            continue
        routes = np.asarray(receiver_routes, dtype=np.float64)
        wide = np.asarray(receiver_wide, dtype=np.float64)
        route_share = routes / routes.sum()
        context = (
            wide * float(vulnerability["wide"])
            + (1.0 - wide) * float(vulnerability["slot"])
        )
        allocation = route_share * context
        centered = allocation - float(allocation.mean())
        scale = float(np.max(np.abs(centered), initial=0.0))
        if not np.isfinite(scale) or scale <= 0:
            fail("constant-context")
            continue
        scaled = centered / scale
        receiver_index = np.asarray(receiver_rows, dtype=int)
        scores[receiver_index] = scaled
        eligible[receiver_index] = True
        group_keys.append(tuple(str(value) for value in key))

    content = json.dumps(
        group_keys, sort_keys=True, separators=(",", ":")
    ).encode()
    return scores, eligible, {
        "eligible_groups": len(group_keys),
        "eligible_wr_rows": int(eligible.sum()),
        "eligible_group_keys_sha256": sha256(content).hexdigest(),
        "support_failures": dict(sorted(support_failures.items())),
        "minimum_route_mass": MIN_ROUTE_MASS,
    }


def apply_receiver_copula(
    control_draws: np.ndarray,
    frame: pd.DataFrame,
    receiver_scores: np.ndarray,
    eligible: np.ndarray,
    *,
    strength: float,
) -> tuple[np.ndarray, dict]:
    """Apply the sole stable-rank treatment while preserving every marginal."""
    control = np.asarray(control_draws)
    scores = np.asarray(receiver_scores, dtype=np.float64)
    mask = np.asarray(eligible, dtype=bool)
    if (
        control.ndim != 2 or len(frame) != len(control)
        or scores.shape != (len(frame),) or mask.shape != (len(frame),)
        or not np.isfinite(control).all() or not np.isfinite(scores).all()
        or not np.isfinite(strength) or strength < 0
    ):
        raise ValueError("receiver-copula treatment inputs are invalid")
    if not frame.index.equals(pd.RangeIndex(len(frame))):
        raise ValueError("receiver-copula frame must have a canonical row index")
    if np.any(mask & ~frame.position.eq("WR").to_numpy(bool)):
        raise ValueError("receiver-copula eligibility includes a non-WR")
    treatment = control.copy()
    changed_groups = 0
    for _key, group in frame.groupby(
        ["season", "week", "game_id", "team"], sort=True, dropna=False,
    ):
        qbs = group.index[group.position.eq("QB")].to_numpy(int)
        wr_rows = group.index[mask[group.index]].to_numpy(int)
        if len(wr_rows) == 0:
            continue
        if len(qbs) != 1 or len(wr_rows) < 2:
            raise ValueError("receiver-copula eligible group geometry changed")
        q = stable_percentile_ranks(control[qbs[0]])
        for row in sorted(wr_rows):
            u = stable_percentile_ranks(control[row])
            priority = u + float(strength) * scores[row] * (q - 0.5)
            order = np.argsort(priority, kind="stable")
            treatment[row, order] = np.sort(control[row], kind="stable")
        changed_groups += 1
    changed = np.not_equal(control, treatment)
    return treatment, {
        "formula": "u_wr+lambda*z_receiver*(q_qb-0.5)",
        "rank_tie_rule": "stable_ascending_world_index",
        "strength": float(strength),
        "eligible_groups": int(changed_groups),
        "eligible_wr_rows": int(mask.sum()),
        "changed_rows": int(changed.any(axis=1).sum()),
        "changed_world_cells": int(changed.sum()),
        "maximum_mean_delta": float(np.max(np.abs(
            control.mean(axis=1, dtype=np.float64)
            - treatment.mean(axis=1, dtype=np.float64)
        ), initial=0.0)),
    }


__all__ = [
    "MIN_ROUTE_MASS", "POSITIONS", "apply_receiver_copula",
    "build_receiver_context", "stable_percentile_ranks",
]
