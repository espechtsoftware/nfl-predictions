"""Paired, outcome-free world-resampling diagnostics for CBWU and CBWU-OI."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from ..optimizer.lineup import select_tail_entries


LINE = 194.0
ENTRY_COUNT = 80
BLOCK_COUNT = 5
WORLDS_PER_BLOCK = 10_000
BOOTSTRAP_RESAMPLES = 32
BOOTSTRAP_PER_BLOCK = 2_000
BOOTSTRAP_SEED = 8_132_027
SPLIT_SEED = 19_408_014
PREFIXES = (1, 5, 10, 20, 40, 60, 80)


def _identity(value: Sequence[object]) -> tuple[str, ...]:
    result = tuple(sorted(str(item) for item in value))
    if len(result) != 9 or len(set(result)) != 9:
        raise ValueError("selector-stability candidate identity is malformed")
    return result


def _identities(values: Sequence[Sequence[object]]) -> tuple[tuple[str, ...], ...]:
    result = tuple(_identity(value) for value in values)
    if len(result) != len(set(result)):
        raise ValueError("selector-stability candidate identities repeat")
    return result


def _select(totals: np.ndarray, entry_count: int, line: float) -> list[int]:
    return select_tail_entries(
        totals, entry_count, line, env={"SELECT_LSE": "0"}
    )


def _coverage(totals: np.ndarray, selected: Sequence[int], line: float) -> float:
    return float(np.any(totals[list(selected)] >= line, axis=0).mean())


def _overlap_summary(books: Sequence[Sequence[int]]) -> tuple[dict, dict]:
    if len(books) < 2:
        raise ValueError("selector stability requires at least two books")
    overlaps: list[int] = []
    prefixes: dict[int, list[int]] = {prefix: [] for prefix in PREFIXES}
    for index, left in enumerate(books):
        for right in books[index + 1:]:
            overlaps.append(len(set(left) & set(right)))
            for prefix in PREFIXES:
                width = min(prefix, len(left), len(right))
                prefixes[prefix].append(
                    len(set(left[:width]) & set(right[:width]))
                )
    values = np.asarray(overlaps, dtype=float)
    return {
        "pair_count": int(len(values)),
        "mean": float(values.mean()),
        "min": int(values.min()),
        "q05": float(np.quantile(values, 0.05)),
        "q50": float(np.quantile(values, 0.50)),
        "q95": float(np.quantile(values, 0.95)),
    }, {
        str(prefix): float(np.mean(prefixes[prefix])) for prefix in PREFIXES
    }


def stratified_world_samples(
    *,
    season: int,
    week: int,
    block_count: int = BLOCK_COUNT,
    worlds_per_block: int = WORLDS_PER_BLOCK,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
    bootstrap_per_block: int = BOOTSTRAP_PER_BLOCK,
) -> tuple[np.ndarray, np.ndarray, tuple[np.ndarray, ...]]:
    """Return the immutable paired split/bootstrap column indices."""
    if block_count <= 0 or worlds_per_block <= 1:
        raise ValueError("selector-stability world block contract is invalid")
    if bootstrap_resamples < 2 or bootstrap_per_block <= 0:
        raise ValueError("selector-stability bootstrap contract is invalid")
    left: list[np.ndarray] = []
    right: list[np.ndarray] = []
    for block in range(block_count):
        rng = np.random.default_rng(np.random.SeedSequence([
            SPLIT_SEED, int(season), int(week), block,
        ]))
        permutation = rng.permutation(worlds_per_block) + block * worlds_per_block
        first, second = np.array_split(permutation, 2)
        left.append(first)
        right.append(second)

    bootstraps: list[np.ndarray] = []
    for replicate in range(bootstrap_resamples):
        blocks = []
        for block in range(block_count):
            rng = np.random.default_rng(np.random.SeedSequence([
                BOOTSTRAP_SEED, int(season), int(week), replicate, block,
            ]))
            blocks.append(
                rng.integers(
                    0, worlds_per_block, size=bootstrap_per_block,
                ) + block * worlds_per_block
            )
        bootstraps.append(np.concatenate(blocks))
    return np.concatenate(left), np.concatenate(right), tuple(bootstraps)


def _measure_pool(
    totals: np.ndarray,
    identities: tuple[tuple[str, ...], ...],
    expected_full: tuple[tuple[str, ...], ...],
    *,
    left_columns: np.ndarray,
    right_columns: np.ndarray,
    bootstrap_columns: Sequence[np.ndarray],
    entry_count: int,
    line: float,
) -> tuple[dict[str, Any], dict[str, list[list[str]]]]:
    full = _select(totals, entry_count, line)
    full_identities = tuple(identities[index] for index in full)
    if full_identities != expected_full:
        raise ValueError("selector-stability full book does not reproduce")

    left = _select(totals[:, left_columns], entry_count, line)
    right = _select(totals[:, right_columns], entry_count, line)
    bootstrap_books = [
        _select(totals[:, columns], entry_count, line)
        for columns in bootstrap_columns
    ]
    pairwise, prefixes = _overlap_summary(bootstrap_books)
    full_set = set(full)
    full_overlaps = np.asarray([
        len(set(book) & full_set) for book in bootstrap_books
    ], dtype=float)
    counts = np.bincount(
        np.concatenate([np.asarray(book, dtype=int) for book in bootstrap_books]),
        minlength=len(identities),
    )
    frequencies = counts / float(len(bootstrap_books))
    metrics = {
        "candidate_count": int(len(identities)),
        "world_count": int(totals.shape[1]),
        "entry_count": int(entry_count),
        "line": float(line),
        "full_book_reproduced": True,
        "full_book_coverage": _coverage(totals, full, line),
        "disjoint_halves": {
            "worlds_per_half": [
                int(len(left_columns)), int(len(right_columns)),
            ],
            "selected_overlap": int(len(set(left) & set(right))),
            "left_overlap_full": int(len(set(left) & full_set)),
            "right_overlap_full": int(len(set(right) & full_set)),
            "left_train_coverage": _coverage(
                totals[:, left_columns], left, line,
            ),
            "left_validation_coverage": _coverage(
                totals[:, right_columns], left, line,
            ),
            "right_train_coverage": _coverage(
                totals[:, right_columns], right, line,
            ),
            "right_validation_coverage": _coverage(
                totals[:, left_columns], right, line,
            ),
        },
        "bootstrap": {
            "resamples": int(len(bootstrap_books)),
            "worlds_per_resample": int(len(bootstrap_columns[0])),
            "pairwise_overlap": pairwise,
            "prefix_overlap_mean": prefixes,
            "overlap_with_full": {
                "mean": float(full_overlaps.mean()),
                "min": int(full_overlaps.min()),
                "q05": float(np.quantile(full_overlaps, 0.05)),
                "q50": float(np.quantile(full_overlaps, 0.50)),
                "q95": float(np.quantile(full_overlaps, 0.95)),
            },
            "frequency_counts": {
                "ge_90pct": int(np.sum(frequencies >= 0.90)),
                "ge_50_lt_90pct": int(np.sum(
                    (frequencies >= 0.50) & (frequencies < 0.90)
                )),
                "gt_0_lt_50pct": int(np.sum(
                    (frequencies > 0.0) & (frequencies < 0.50)
                )),
                "zero": int(np.sum(frequencies == 0.0)),
            },
        },
    }
    books = {
        "full": [list(identities[index]) for index in full],
        "left": [list(identities[index]) for index in left],
        "right": [list(identities[index]) for index in right],
        "bootstrap": [
            [list(identities[index]) for index in book]
            for book in bootstrap_books
        ],
        "frequencies": [
            {
                "identity": list(identity),
                "selected_count": int(counts[index]),
                "selection_frequency": float(frequencies[index]),
                "full_book_selected": bool(index in full_set),
            }
            for index, identity in enumerate(identities)
        ],
    }
    return metrics, books


def _matched_overlap(
    canonical: Sequence[Sequence[str]],
    treatment: Sequence[Sequence[str]],
) -> int:
    return int(len({tuple(value) for value in canonical} & {
        tuple(value) for value in treatment
    }))


def analyze_paired_selector_stability(
    canonical_totals: np.ndarray,
    canonical_identities: Sequence[Sequence[object]],
    expected_canonical_full: Sequence[Sequence[object]],
    oi_totals: np.ndarray,
    oi_identities: Sequence[Sequence[object]],
    expected_oi_full: Sequence[Sequence[object]],
    *,
    season: int,
    week: int,
    entry_count: int = ENTRY_COUNT,
    line: float = LINE,
    block_count: int = BLOCK_COUNT,
    worlds_per_block: int = WORLDS_PER_BLOCK,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
    bootstrap_per_block: int = BOOTSTRAP_PER_BLOCK,
) -> dict[str, Any]:
    """Measure canonical and OI pools on identical fixed world samples."""
    canonical_matrix = np.asarray(canonical_totals, dtype=np.float32)
    oi_matrix = np.asarray(oi_totals, dtype=np.float32)
    total_worlds = block_count * worlds_per_block
    for matrix, label in (
        (canonical_matrix, "canonical"), (oi_matrix, "OI"),
    ):
        if matrix.ndim != 2 or matrix.shape[0] < entry_count:
            raise ValueError(f"selector-stability {label} matrix is invalid")
        if matrix.shape[1] != total_worlds or not np.isfinite(matrix).all():
            raise ValueError(f"selector-stability {label} worlds differ")
    if canonical_matrix.shape[0] != oi_matrix.shape[0]:
        raise ValueError("selector-stability candidate budgets differ")

    canonical_ids = _identities(canonical_identities)
    oi_ids = _identities(oi_identities)
    if len(canonical_ids) != canonical_matrix.shape[0] or (
        len(oi_ids) != oi_matrix.shape[0]
    ):
        raise ValueError("selector-stability identity count differs")
    expected_canonical = tuple(
        _identity(value) for value in expected_canonical_full
    )
    expected_oi = tuple(_identity(value) for value in expected_oi_full)
    if len(expected_canonical) != entry_count or len(expected_oi) != entry_count:
        raise ValueError("selector-stability expected book size differs")

    left, right, bootstraps = stratified_world_samples(
        season=season,
        week=week,
        block_count=block_count,
        worlds_per_block=worlds_per_block,
        bootstrap_resamples=bootstrap_resamples,
        bootstrap_per_block=bootstrap_per_block,
    )
    canonical_metrics, canonical_books = _measure_pool(
        canonical_matrix, canonical_ids, expected_canonical,
        left_columns=left, right_columns=right,
        bootstrap_columns=bootstraps, entry_count=entry_count, line=line,
    )
    oi_metrics, oi_books = _measure_pool(
        oi_matrix, oi_ids, expected_oi,
        left_columns=left, right_columns=right,
        bootstrap_columns=bootstraps, entry_count=entry_count, line=line,
    )
    cross_bootstrap = np.asarray([
        _matched_overlap(control, treatment)
        for control, treatment in zip(
            canonical_books["bootstrap"], oi_books["bootstrap"], strict=True,
        )
    ], dtype=float)
    return {
        "season": int(season),
        "week": int(week),
        "uses_realized_outcomes": False,
        "samples_identical_across_pools": True,
        "canonical": canonical_metrics,
        "cbwu_oi": oi_metrics,
        "cross_pool_identity_overlap": {
            "full": _matched_overlap(
                canonical_books["full"], oi_books["full"],
            ),
            "left_half": _matched_overlap(
                canonical_books["left"], oi_books["left"],
            ),
            "right_half": _matched_overlap(
                canonical_books["right"], oi_books["right"],
            ),
            "bootstrap_mean": float(cross_bootstrap.mean()),
            "bootstrap_min": int(cross_bootstrap.min()),
            "bootstrap_q05": float(np.quantile(cross_bootstrap, 0.05)),
            "bootstrap_q50": float(np.quantile(cross_bootstrap, 0.50)),
            "bootstrap_q95": float(np.quantile(cross_bootstrap, 0.95)),
        },
        "candidate_frequencies": {
            "canonical": canonical_books["frequencies"],
            "cbwu_oi": oi_books["frequencies"],
        },
    }


def _stability_band(value: float) -> str:
    if value >= 72.0:
        return "high"
    if value >= 56.0:
        return "intermediate"
    return "low"


def summarize_paired_selector_stability(rows: Sequence[dict]) -> dict[str, Any]:
    """Aggregate paired stability with equal slate weight."""
    if not rows:
        raise ValueError("paired selector-stability result is empty")

    def arm_summary(group: Sequence[dict], arm: str) -> dict[str, Any]:
        pairwise = np.asarray([
            row[arm]["bootstrap"]["pairwise_overlap"]["mean"] for row in group
        ])
        split = np.asarray([
            row[arm]["disjoint_halves"]["selected_overlap"] for row in group
        ])
        optimism = np.asarray([
            0.5 * (
                row[arm]["disjoint_halves"]["left_train_coverage"]
                - row[arm]["disjoint_halves"]["left_validation_coverage"]
                + row[arm]["disjoint_halves"]["right_train_coverage"]
                - row[arm]["disjoint_halves"]["right_validation_coverage"]
            )
            for row in group
        ])
        mean_pairwise = float(pairwise.mean())
        return {
            "mean_pairwise_overlap": mean_pairwise,
            "pairwise_overlap_q05": float(np.quantile(pairwise, 0.05)),
            "pairwise_overlap_q50": float(np.quantile(pairwise, 0.50)),
            "pairwise_overlap_q95": float(np.quantile(pairwise, 0.95)),
            "mean_disjoint_half_overlap": float(split.mean()),
            "mean_reciprocal_selection_optimism": float(optimism.mean()),
            "mean_prefix_overlap": {
                str(prefix): float(np.mean([
                    row[arm]["bootstrap"]["prefix_overlap_mean"][str(prefix)]
                    for row in group
                ]))
                for prefix in PREFIXES
            },
            "stability_band": _stability_band(mean_pairwise),
        }

    def group_summary(group: Sequence[dict]) -> dict[str, Any]:
        canonical = arm_summary(group, "canonical")
        treatment = arm_summary(group, "cbwu_oi")
        numeric = (
            "mean_pairwise_overlap", "mean_disjoint_half_overlap",
            "mean_reciprocal_selection_optimism",
        )
        cross_keys = tuple(rows[0]["cross_pool_identity_overlap"])
        return {
            "slates": int(len(group)),
            "canonical": canonical,
            "cbwu_oi": treatment,
            "cbwu_oi_minus_canonical": {
                **{
                    key: float(treatment[key] - canonical[key])
                    for key in numeric
                },
                "mean_prefix_overlap": {
                    str(prefix): float(
                        treatment["mean_prefix_overlap"][str(prefix)]
                        - canonical["mean_prefix_overlap"][str(prefix)]
                    )
                    for prefix in PREFIXES
                },
            },
            "cross_pool_identity_overlap": {
                key: float(np.mean([
                    row["cross_pool_identity_overlap"][key] for row in group
                ]))
                for key in cross_keys
            },
        }

    compact = [
        {key: value for key, value in row.items()
         if key != "candidate_frequencies"}
        for row in rows
    ]
    return {
        "overall": group_summary(rows),
        "by_season": {
            str(season): group_summary([
                row for row in rows if int(row["season"]) == season
            ])
            for season in sorted({int(row["season"]) for row in rows})
        },
        "slates": compact,
    }


__all__ = [
    "BLOCK_COUNT", "BOOTSTRAP_PER_BLOCK", "BOOTSTRAP_RESAMPLES",
    "ENTRY_COUNT", "LINE", "WORLDS_PER_BLOCK",
    "analyze_paired_selector_stability", "stratified_world_samples",
    "summarize_paired_selector_stability",
]
