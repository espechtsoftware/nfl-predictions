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
REQUIRED_ARTIFACT_MEMBERS = frozenset({"cand_ix", "totals", "tail_line"})


def decode_score_artifact(payload: bytes, expected_sha256: str) -> dict[str, np.ndarray]:
    """Verify and decode one immutable candidate score artifact."""
    digest = hashlib.sha256(payload).hexdigest()
    if digest != str(expected_sha256):
        raise ValueError(
            f"score artifact sha256 differs: {digest} != {expected_sha256}")
    with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
        members = set(archive.files)
        if members != REQUIRED_ARTIFACT_MEMBERS:
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
        "n_worlds", "tail_line",
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
    covariance = _spectrum(selected_totals, correlation=False)
    correlation = _spectrum(selected_totals, correlation=True)
    leading = np.asarray(covariance.pop("leading_eigenvector"))
    correlation.pop("leading_eigenvector")

    nested: dict[str, dict] = {}
    for size in sorted(set(int(value) for value in book_sizes)):
        if size < 2 or size > len(selected):
            continue
        matrix = selected_totals[:size]
        cov = _spectrum(matrix, correlation=False)
        corr = _spectrum(matrix, correlation=True)
        cov.pop("leading_eigenvector")
        corr.pop("leading_eigenvector")
        nested[str(size)] = {
            "covariance": cov,
            "correlation": corr,
            "tails": [
                _tail_metrics(matrix, float(line)) for line in lines
            ],
        }

    return {
        "season": int(rows.season.iloc[0]),
        "week": int(rows.week.iloc[0]),
        "candidates": int(len(rows)),
        "selected_entries": int(len(selected)),
        "worlds": int(totals.shape[1]),
        "simulator_implied_only": True,
        "covariance": covariance,
        "correlation": correlation,
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
    }

