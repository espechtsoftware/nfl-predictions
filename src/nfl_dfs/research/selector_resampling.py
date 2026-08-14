"""Score-free stability diagnostics for the exact-80 coverage selector."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ..optimizer.lineup import select_from_support


LINE = 194.0
ENTRY_COUNT = 80
WORLD_COUNT = 10_000
BOOTSTRAP_RESAMPLES = 32
BOOTSTRAP_SEED = 8_132_027
SPLIT_SEED = 19_408_014
PREFIXES = (1, 5, 10, 20, 40, 60, 80)


def _selector(totals: np.ndarray, entry_count: int, line: float) -> list[int]:
    clears = totals >= line
    return select_from_support(
        clears,
        clears.mean(axis=1),
        totals.mean(axis=1),
        entry_count,
    )


def _book_coverage(totals: np.ndarray, picked: Sequence[int], line: float) -> float:
    return float((totals[list(picked)] >= line).any(axis=0).mean())


def _overlap_summary(books: Sequence[Sequence[int]]) -> tuple[dict, dict[str, float]]:
    if len(books) < 2:
        raise ValueError("selector stability needs at least two books")
    overlaps: list[int] = []
    prefix: dict[int, list[int]] = {value: [] for value in PREFIXES}
    for left_index, left in enumerate(books):
        for right in books[left_index + 1:]:
            overlaps.append(len(set(left) & set(right)))
            for value in PREFIXES:
                width = min(value, len(left), len(right))
                prefix[value].append(
                    len(set(left[:width]) & set(right[:width]))
                )
    values = np.asarray(overlaps, dtype=float)
    summary = {
        "pair_count": int(len(values)),
        "mean": float(values.mean()),
        "min": int(values.min()),
        "q05": float(np.quantile(values, 0.05)),
        "q50": float(np.quantile(values, 0.50)),
        "q95": float(np.quantile(values, 0.95)),
    }
    prefix_summary = {
        str(value): float(np.mean(prefix[value])) for value in PREFIXES
    }
    return summary, prefix_summary


def analyze_selector_resampling(
    totals: np.ndarray,
    expected_picked: Sequence[int],
    *,
    season: int,
    week: int,
    entry_count: int = ENTRY_COUNT,
    line: float = LINE,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
    expected_world_count: int | None = WORLD_COUNT,
) -> dict:
    """Analyze one slate without consuming realized lineup outcomes."""
    matrix = np.asarray(totals, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] < entry_count:
        raise ValueError("candidate totals have invalid shape")
    if expected_world_count is not None and matrix.shape[1] != expected_world_count:
        raise ValueError("candidate totals world count differs")
    if not np.isfinite(matrix).all():
        raise ValueError("candidate totals contain non-finite values")
    if bootstrap_resamples < 2:
        raise ValueError("bootstrap resamples must be at least two")

    full = _selector(matrix, entry_count, line)
    expected = [int(value) for value in expected_picked]
    if full != expected:
        raise ValueError("full-world selected order does not reproduce")

    split_rng = np.random.default_rng(
        np.random.SeedSequence([SPLIT_SEED, int(season), int(week)])
    )
    permutation = split_rng.permutation(matrix.shape[1])
    left_ix, right_ix = np.array_split(permutation, 2)
    left_matrix = matrix[:, left_ix]
    right_matrix = matrix[:, right_ix]
    left_book = _selector(left_matrix, entry_count, line)
    right_book = _selector(right_matrix, entry_count, line)

    bootstrap_rng = np.random.default_rng(
        np.random.SeedSequence([BOOTSTRAP_SEED, int(season), int(week)])
    )
    books: list[list[int]] = []
    for _ in range(bootstrap_resamples):
        sample = bootstrap_rng.integers(
            0, matrix.shape[1], size=matrix.shape[1]
        )
        books.append(_selector(matrix[:, sample], entry_count, line))

    pairwise, prefix = _overlap_summary(books)
    full_set = set(full)
    full_overlaps = np.asarray(
        [len(set(book) & full_set) for book in books], dtype=float
    )
    counts = np.bincount(
        np.concatenate([np.asarray(book, dtype=int) for book in books]),
        minlength=matrix.shape[0],
    )
    frequencies = counts / float(bootstrap_resamples)
    frequency_rows = [
        {
            "cand_ix": int(index),
            "selected_count": int(counts[index]),
            "selection_frequency": float(frequencies[index]),
            "full_book_selected": bool(index in full_set),
        }
        for index in range(matrix.shape[0])
    ]

    return {
        "season": int(season),
        "week": int(week),
        "candidate_count": int(matrix.shape[0]),
        "world_count": int(matrix.shape[1]),
        "entry_count": int(entry_count),
        "line": float(line),
        "full_book_reproduced": True,
        "full_book_coverage": _book_coverage(matrix, full, line),
        "disjoint_halves": {
            "worlds_per_half": [int(len(left_ix)), int(len(right_ix))],
            "selected_overlap": int(len(set(left_book) & set(right_book))),
            "left_overlap_full": int(len(set(left_book) & full_set)),
            "right_overlap_full": int(len(set(right_book) & full_set)),
            "left_train_coverage": _book_coverage(left_matrix, left_book, line),
            "left_validation_coverage": _book_coverage(
                right_matrix, left_book, line
            ),
            "right_train_coverage": _book_coverage(
                right_matrix, right_book, line
            ),
            "right_validation_coverage": _book_coverage(
                left_matrix, right_book, line
            ),
            "full_left_coverage": _book_coverage(left_matrix, full, line),
            "full_right_coverage": _book_coverage(right_matrix, full, line),
        },
        "bootstrap": {
            "resamples": int(bootstrap_resamples),
            "pairwise_overlap": pairwise,
            "prefix_overlap_mean": prefix,
            "overlap_with_full": {
                "mean": float(full_overlaps.mean()),
                "min": int(full_overlaps.min()),
                "q05": float(np.quantile(full_overlaps, 0.05)),
                "q50": float(np.quantile(full_overlaps, 0.50)),
                "q95": float(np.quantile(full_overlaps, 0.95)),
            },
            "frequency_counts": {
                "ge_90pct": int((frequencies >= 0.90).sum()),
                "ge_50_lt_90pct": int(
                    ((frequencies >= 0.50) & (frequencies < 0.90)).sum()
                ),
                "gt_0_lt_50pct": int(
                    ((frequencies > 0.0) & (frequencies < 0.50)).sum()
                ),
                "zero": int((frequencies == 0.0).sum()),
            },
        },
        "candidate_frequencies": frequency_rows,
    }


def _stability_band(value: float) -> str:
    if value >= 72.0:
        return "high"
    if value >= 56.0:
        return "intermediate"
    return "low"


def summarize_selector_resampling(slates: Sequence[dict]) -> dict:
    if not slates:
        raise ValueError("selector-resampling result has no slates")

    def summary(rows: Sequence[dict]) -> dict:
        pairwise = np.asarray([
            row["bootstrap"]["pairwise_overlap"]["mean"] for row in rows
        ])
        split = np.asarray([
            row["disjoint_halves"]["selected_overlap"] for row in rows
        ])
        optimism = np.asarray([
            0.5 * (
                row["disjoint_halves"]["left_train_coverage"]
                - row["disjoint_halves"]["left_validation_coverage"]
                + row["disjoint_halves"]["right_train_coverage"]
                - row["disjoint_halves"]["right_validation_coverage"]
            )
            for row in rows
        ])
        frequency_keys = (
            "ge_90pct", "ge_50_lt_90pct", "gt_0_lt_50pct", "zero"
        )
        mean_pairwise = float(pairwise.mean())
        return {
            "slates": int(len(rows)),
            "mean_pairwise_overlap": mean_pairwise,
            "pairwise_overlap_q05": float(np.quantile(pairwise, 0.05)),
            "pairwise_overlap_q50": float(np.quantile(pairwise, 0.50)),
            "pairwise_overlap_q95": float(np.quantile(pairwise, 0.95)),
            "mean_disjoint_half_overlap": float(split.mean()),
            "mean_reciprocal_selection_optimism": float(optimism.mean()),
            "mean_frequency_counts": {
                key: float(np.mean([
                    row["bootstrap"]["frequency_counts"][key] for row in rows
                ]))
                for key in frequency_keys
            },
            "mean_prefix_overlap": {
                str(prefix): float(np.mean([
                    row["bootstrap"]["prefix_overlap_mean"][str(prefix)]
                    for row in rows
                ]))
                for prefix in PREFIXES
            },
            "stability_band": _stability_band(mean_pairwise),
        }

    compact = [
        {key: value for key, value in row.items()
         if key != "candidate_frequencies"}
        for row in slates
    ]
    return {
        "overall": summary(slates),
        "by_season": {
            str(season): summary([
                row for row in slates if int(row["season"]) == season
            ])
            for season in sorted({int(row["season"]) for row in slates})
        },
        "slates": compact,
    }
