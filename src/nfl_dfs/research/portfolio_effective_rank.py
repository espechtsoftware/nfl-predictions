"""Outcome-blind portfolio dependence diagnostics from persisted score worlds.

The candidate score artifact is the exact candidate-by-world matrix used by
the selector.  These diagnostics describe the simulator-implied diversity of
an already selected book; they never read realized scores and must not be
presented as empirical real-world independence.
"""

from __future__ import annotations

import hashlib
import io
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_LINES = (187.0, 194.0, 200.0, 210.0, 220.0, 230.0, 240.0)
DEFAULT_BOOK_SIZES = (20, 40, 80)
RANDOM_CONTROL_BOOKS = 20
RANDOM_CONTROL_SEED = 20260812
REQUIRED_ARTIFACT_MEMBERS = frozenset({"cand_ix", "totals", "tail_line"})
PLAYER_WORLD_MEMBERS = frozenset({"player_ids", "player_draws"})


def decode_score_artifact(payload: bytes, expected_sha256: str) -> dict[str, np.ndarray]:
    """Verify and decode one immutable candidate score artifact."""
    digest = hashlib.sha256(payload).hexdigest()
    if digest != str(expected_sha256):
        raise ValueError(
            f"score artifact sha256 differs: {digest} != {expected_sha256}")
    with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
        members = set(archive.files)
        allowed = (
            members == REQUIRED_ARTIFACT_MEMBERS
            or members == REQUIRED_ARTIFACT_MEMBERS | PLAYER_WORLD_MEMBERS
        )
        if not allowed:
            raise ValueError(
                f"score artifact members differ: {sorted(members)}")
        artifact = {name: archive[name].copy() for name in archive.files}
    totals = np.asarray(artifact["totals"])
    cand_ix = np.asarray(artifact["cand_ix"])
    if totals.ndim != 2 or totals.shape[0] < 1 or totals.shape[1] < 2:
        raise ValueError("score artifact totals must be candidate-by-world")
    if not np.isfinite(totals).all():
        raise ValueError("score artifact totals contain non-finite values")
    expected_ix = np.arange(totals.shape[0], dtype=np.int64)
    if not np.array_equal(cand_ix.astype(np.int64), expected_ix):
        raise ValueError("score artifact cand_ix is not canonical")
    if PLAYER_WORLD_MEMBERS <= set(artifact):
        player_ids = np.asarray(artifact["player_ids"]).astype(str)
        player_draws = np.asarray(artifact["player_draws"])
        if player_ids.ndim != 1 or len(set(player_ids.tolist())) != len(player_ids):
            raise ValueError("score artifact player ids are not unique")
        if player_draws.ndim != 2 or player_draws.shape != (
            len(player_ids), totals.shape[1]
        ):
            raise ValueError("score artifact player worlds are misaligned")
        if not np.isfinite(player_draws).all():
            raise ValueError("score artifact player worlds contain non-finite values")
    return artifact


def _spectrum(matrix: np.ndarray, *, correlation: bool) -> dict:
    if matrix.ndim != 2 or matrix.shape[0] < 2 or matrix.shape[1] < 2:
        raise ValueError("portfolio matrix must be entry-by-world")
    covariance = np.cov(matrix, rowvar=True, ddof=1)
    if correlation:
        variances = np.diag(covariance)
        if np.any(variances <= 0):
            raise ValueError("correlation spectrum has a zero-variance entry")
        scale = np.sqrt(variances)
        covariance = covariance / np.outer(scale, scale)
        np.fill_diagonal(covariance, 1.0)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.maximum(eigenvalues[order], 0.0)
    eigenvectors = eigenvectors[:, order]
    total = float(eigenvalues.sum())
    if total <= 0:
        raise ValueError("portfolio spectrum has no positive variance")
    shares = eigenvalues / total
    participation = float(total * total / np.square(eigenvalues).sum())
    positive = shares[shares > 0]
    entropy_rank = float(np.exp(-(positive * np.log(positive)).sum()))
    # Eigenvector sign is arbitrary. Orient the leading vector toward the
    # common positive portfolio direction for deterministic loadings.
    leading = eigenvectors[:, 0].copy()
    if float(leading.sum()) < 0:
        leading *= -1
    return {
        "participation_ratio": participation,
        "entropy_effective_rank": entropy_rank,
        "top_eigenvalue_shares": [float(value) for value in shares[:5]],
        "top_five_variance_share": float(shares[:5].sum()),
        "leading_eigenvector": leading,
    }


def _tail_metrics(matrix: np.ndarray, line: float) -> dict:
    events = matrix >= float(line)
    n_entries, n_worlds = events.shape
    rates = events.mean(axis=1)
    multiplicity = events.sum(axis=0)
    upper = np.triu_indices(n_entries, 1)
    joint = (events.astype(np.float64) @ events.T.astype(np.float64)) / n_worlds
    joint_values = joint[upper]
    independent = np.outer(rates, rates)[upper]
    union = rates[:, None] + rates[None, :] - joint
    union_values = union[upper]
    valid_jaccard = union_values > 0
    jaccard = np.divide(
        joint_values,
        union_values,
        out=np.zeros_like(joint_values),
        where=valid_jaccard,
    )
    expected_joint = float(independent.sum())
    return {
        "line": float(line),
        "worlds": int(n_worlds),
        "entry_events": int(events.sum()),
        "worlds_with_any_event": int((multiplicity >= 1).sum()),
        "worlds_with_ge_2_entries": int((multiplicity >= 2).sum()),
        "worlds_with_ge_3_entries": int((multiplicity >= 3).sum()),
        "pair_cells": int(len(joint_values)),
        "pair_joint_events": int(np.rint(joint_values.sum() * n_worlds)),
        "pair_cells_with_joint_event": int((joint_values > 0).sum()),
        "pair_cells_with_union_event": int(valid_jaccard.sum()),
        "entry_rate_mean": float(rates.mean()),
        "entry_rate_min": float(rates.min()),
        "entry_rate_max": float(rates.max()),
        "covered_world_rate": float((multiplicity >= 1).mean()),
        "world_rate_ge_2_entries": float((multiplicity >= 2).mean()),
        "world_rate_ge_3_entries": float((multiplicity >= 3).mean()),
        "mean_entries_clearing_per_world": float(multiplicity.mean()),
        "pair_joint_rate_mean": float(joint_values.mean()),
        "pair_joint_lift_ratio_of_sums": (
            float(joint_values.sum() / expected_joint)
            if expected_joint > 0 else None),
        "pair_jaccard_mean": (
            float(jaccard[valid_jaccard].mean())
            if valid_jaccard.any() else None),
        "pair_jaccard_median": (
            float(np.median(jaccard[valid_jaccard]))
            if valid_jaccard.any() else None),
    }


def _deflate_first_pc(matrix: np.ndarray, leading: np.ndarray) -> np.ndarray:
    centered = matrix - matrix.mean(axis=1, keepdims=True)
    return centered - np.outer(leading, leading @ centered)


def _public_spectrum(value: dict) -> tuple[dict, np.ndarray]:
    value = dict(value)
    leading = np.asarray(value.pop("leading_eigenvector"), dtype=float)
    return value, leading


def _deflated_spectra(matrix: np.ndarray, leading: np.ndarray) -> dict:
    residual = _deflate_first_pc(matrix, leading)
    tolerance = np.finfo(float).eps * max(1.0, float(np.square(matrix).mean()))
    if float(np.square(residual).mean()) <= tolerance:
        return {
            "status": "degenerate-after-first-pc",
            "covariance": None,
            "correlation": None,
        }
    covariance, _ = _public_spectrum(_spectrum(residual, correlation=False))
    try:
        correlation, _ = _public_spectrum(_spectrum(residual, correlation=True))
        status = "valid"
    except ValueError as exc:
        correlation = None
        status = f"correlation-unavailable: {exc}"
    return {
        "status": status,
        "covariance": covariance,
        "correlation": correlation,
    }


def _book_metrics(matrix: np.ndarray, lines: Iterable[float]) -> tuple[dict, np.ndarray]:
    covariance, leading = _public_spectrum(
        _spectrum(matrix, correlation=False))
    correlation, _ = _public_spectrum(_spectrum(matrix, correlation=True))
    return {
        "covariance": covariance,
        "correlation": correlation,
        "after_first_pc_deflation": _deflated_spectra(matrix, leading),
        "tails": [_tail_metrics(matrix, float(line)) for line in lines],
    }, leading


def _numeric_summary(values: list[float]) -> dict:
    array = np.asarray(values, dtype=float)
    if not len(array) or not np.isfinite(array).all():
        raise ValueError("random-control summary contains invalid values")
    return {
        "mean": float(array.mean()),
        "p10": float(np.quantile(array, 0.10)),
        "median": float(np.median(array)),
        "p90": float(np.quantile(array, 0.90)),
        "min": float(array.min()),
        "max": float(array.max()),
    }


def _random_control_summary(
    totals: np.ndarray,
    *,
    entries: int,
    lines: tuple[float, ...],
    season: int,
    week: int,
    count: int = RANDOM_CONTROL_BOOKS,
) -> dict:
    seed = np.random.SeedSequence([RANDOM_CONTROL_SEED, season, week])
    rng = np.random.default_rng(seed)
    covariance_pr: list[float] = []
    correlation_pr: list[float] = []
    deflated_correlation_pr: list[float] = []
    coverage = {line: [] for line in lines}
    for _ in range(count):
        indices = rng.choice(totals.shape[0], size=entries, replace=False)
        matrix = totals[indices]
        metrics, _ = _book_metrics(matrix, ())
        covariance_pr.append(metrics["covariance"]["participation_ratio"])
        correlation_pr.append(metrics["correlation"]["participation_ratio"])
        deflated = metrics["after_first_pc_deflation"]["correlation"]
        if deflated is not None:
            deflated_correlation_pr.append(deflated["participation_ratio"])
        for line in lines:
            coverage[line].append(float((matrix >= line).any(axis=0).mean()))
    return {
        "books": int(count),
        "base_seed": RANDOM_CONTROL_SEED,
        "seed_components": [RANDOM_CONTROL_SEED, int(season), int(week)],
        "covariance_participation_ratio": _numeric_summary(covariance_pr),
        "correlation_participation_ratio": _numeric_summary(correlation_pr),
        "deflated_correlation_participation_ratio": (
            _numeric_summary(deflated_correlation_pr)
            if deflated_correlation_pr else None),
        "covered_world_rate": {
            f"{line:g}": _numeric_summary(values)
            for line, values in coverage.items()
        },
    }


def _player_loadings(rows: pd.DataFrame, leading: np.ndarray, limit: int = 12) -> list[dict]:
    weights: dict[str, float] = {}
    exposure: dict[str, int] = {}
    for roster, weight in zip(rows.players.astype(str), np.abs(leading)):
        players = [value for value in roster.split(",") if value]
        if len(players) != 9 or len(set(players)) != 9:
            raise ValueError("selected portfolio contains an invalid roster key")
        for player in players:
            weights[player] = weights.get(player, 0.0) + float(weight)
            exposure[player] = exposure.get(player, 0) + 1
    ordered = sorted(weights, key=lambda player: (-weights[player], player))
    return [
        {
            "player_id": player,
            "absolute_loading": weights[player],
            "entries": exposure[player],
        }
        for player in ordered[:limit]
    ]


def analyze_selected_book(
    rows: pd.DataFrame,
    artifact: dict[str, np.ndarray],
    *,
    lines: Iterable[float] = DEFAULT_LINES,
    book_sizes: Iterable[int] = DEFAULT_BOOK_SIZES,
) -> dict:
    """Describe one slate's exact selected book without realized outcomes."""
    required = {
        "season", "week", "cand_ix", "players", "selected", "selected_rank",
        "n_worlds", "tail_line", "sim_mean",
    }
    missing = required - set(rows.columns)
    if missing:
        raise ValueError(f"candidate rows missing {sorted(missing)}")
    if rows.empty or rows.season.nunique() != 1 or rows.week.nunique() != 1:
        raise ValueError("candidate rows must contain exactly one slate")
    if rows.cand_ix.duplicated().any():
        raise ValueError("candidate rows contain duplicate cand_ix")
    totals = np.asarray(artifact.get("totals"), dtype=np.float64)
    artifact_ix = np.asarray(artifact.get("cand_ix"), dtype=np.int64)
    if totals.ndim != 2 or not np.array_equal(
            artifact_ix, np.arange(totals.shape[0], dtype=np.int64)):
        raise ValueError("score artifact is not canonical")
    if len(rows) != totals.shape[0]:
        raise ValueError("candidate rows and artifact row count differ")
    ordered_all = rows.sort_values("cand_ix")
    if not np.array_equal(
            ordered_all.cand_ix.astype(int).to_numpy(), artifact_ix):
        raise ValueError("candidate rows are not the artifact universe")
    sim_mean = pd.to_numeric(ordered_all.sim_mean, errors="raise").to_numpy()
    if not np.isfinite(sim_mean).all() or not np.allclose(
            sim_mean, totals.mean(axis=1), rtol=0.0, atol=1e-3):
        raise ValueError("candidate sim_mean differs from the score artifact")
    n_worlds = pd.to_numeric(rows.n_worlds, errors="raise").astype(int)
    if n_worlds.nunique() != 1 or int(n_worlds.iloc[0]) != totals.shape[1]:
        raise ValueError("candidate n_worlds differs from the artifact")
    selected = rows[rows.selected.astype(bool)].copy()
    selected["selected_rank"] = pd.to_numeric(
        selected.selected_rank, errors="raise").astype(int)
    selected = selected.sort_values("selected_rank")
    if len(selected) < 2 or selected.selected_rank.tolist() != list(range(len(selected))):
        raise ValueError("selected ranks are not complete and zero-based")
    selected_ix = selected.cand_ix.astype(int).to_numpy()
    selected_totals = totals[selected_ix]
    line_values = tuple(float(line) for line in lines)
    selected_metrics, leading = _book_metrics(selected_totals, line_values)

    nested: dict[str, dict] = {}
    for size in sorted(set(int(value) for value in book_sizes)):
        if size < 2 or size > len(selected):
            continue
        matrix = selected_totals[:size]
        nested[str(size)], _ = _book_metrics(matrix, line_values)

    entries = len(selected)
    if len(rows) < entries:
        raise ValueError("candidate pool is smaller than the selected book")
    top_mean_ix = (ordered_all.sort_values(
        ["sim_mean", "cand_ix"], ascending=[False, True])
        .head(entries).cand_ix.astype(int).to_numpy())
    top_mean_metrics, _ = _book_metrics(totals[top_mean_ix], line_values)

    return {
        "season": int(rows.season.iloc[0]),
        "week": int(rows.week.iloc[0]),
        "candidates": int(len(rows)),
        "selected_entries": int(len(selected)),
        "worlds": int(totals.shape[1]),
        "simulator_implied_only": True,
        "expected_bias": (
            "likely optimistic effective rank while QB-receiver upper-tail "
            "dependence is under-modelled; not a formal bound"),
        **selected_metrics,
        "leading_factor_top_entries": [
            {
                "selected_rank": int(selected.iloc[ix].selected_rank),
                "cand_ix": int(selected.iloc[ix].cand_ix),
                "absolute_loading": float(abs(leading[ix])),
            }
            for ix in np.argsort(np.abs(leading))[::-1][:10]
        ],
        "leading_factor_top_players": _player_loadings(selected, leading),
        "nested_books": nested,
        "same_world_controls": {
            "interpretation": (
                "All controls remain in-sample because selection consumed "
                "the same worlds; they isolate selector versus pool structure."),
            "top_sim_mean": top_mean_metrics,
            "random_books": _random_control_summary(
                totals,
                entries=entries,
                lines=line_values,
                season=int(rows.season.iloc[0]),
                week=int(rows.week.iloc[0]),
            ),
        },
    }
