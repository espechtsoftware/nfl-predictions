"""Exact-80 multi-seed candidate/world factorial on immutable artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from ..optimizer.lineup import select_from_support


ARMS = ("C0W0", "C0WU", "CUW0", "CUWU")
CONFIRMATION_ARMS = ("CBW0", "CBWU")
TAILS = (240, 230, 220, 210, 200, 194, 187)
LEAST_CHANGE_ORDER = ARMS
PRODUCTION_ELIGIBLE_ARMS = ("C0W0", "C0WU")
PROPER_SCORE_QUANTILES = (0.95, 0.99)


def canonical_roster(value: str) -> str:
    ids = [item for item in str(value).split(",") if item]
    if len(ids) != 9 or len(set(ids)) != 9:
        raise ValueError("candidate roster must contain nine unique player ids")
    return ",".join(sorted(ids))


def _pinball(actual: np.ndarray, predicted: np.ndarray, level: float) -> float:
    residual = actual - predicted
    return float(np.mean(np.maximum(level * residual, (level - 1.0) * residual)))


def _evaluate_book(
    frame: pd.DataFrame,
    matrix: np.ndarray,
    picked: Sequence[int],
    seeds: Sequence[int],
) -> dict:
    selected = frame.iloc[list(picked)]
    selected_matrix = matrix[list(picked)]
    simulated_weekly_best = selected_matrix.max(axis=0)
    return {
        "candidate_count": int(len(frame)),
        "world_count": int(matrix.shape[1]),
        "selected_rosters": selected.roster_key.tolist(),
        "selected_best": float(selected.actual_score.max()),
        "oracle_best": float(frame.actual_score.max()),
        "selected_from_seed": {
            f"R{seed}": int(selected.source_seed.eq(seed).sum())
            for seed in seeds
        },
        "simulated_coverage": {
            str(tail): float((selected_matrix >= tail).any(axis=0).mean())
            for tail in TAILS
        },
        "simulated_weekly_best_quantile": {
            str(level): float(np.quantile(simulated_weekly_best, level))
            for level in PROPER_SCORE_QUANTILES
        },
    }


def _fixed_budget_records(
    union_records: Sequence[tuple[int, int, str, float]],
    seeds: Sequence[int],
    budget: int,
) -> list[tuple[int, int, str, float]]:
    """Take a score-blind near-equal source quota at the R0 pool budget."""
    by_seed = {
        seed: [record for record in union_records if record[0] == seed]
        for seed in seeds
    }
    base_quota, remainder = divmod(budget, len(seeds))
    chosen: list[tuple[int, int, str, float]] = []
    used = {seed: 0 for seed in seeds}
    for seed_index, seed in enumerate(seeds):
        quota = base_quota + int(seed_index < remainder)
        take = min(quota, len(by_seed[seed]))
        chosen.extend(by_seed[seed][:take])
        used[seed] = take
    while len(chosen) < budget:
        advanced = False
        for seed in seeds:
            if used[seed] < len(by_seed[seed]):
                chosen.append(by_seed[seed][used[seed]])
                used[seed] += 1
                advanced = True
                if len(chosen) == budget:
                    break
        if not advanced:
            raise ValueError("union cannot fill the fixed candidate budget")
    return chosen


def validate_and_cross_score_slate(
    seed_rows: Mapping[int, pd.DataFrame],
    seed_artifacts: Mapping[int, Mapping[str, np.ndarray]],
    *,
    entry_count: int = 80,
    tolerance: float = 1e-4,
) -> tuple[dict[int, pd.DataFrame], dict[tuple[int, int], np.ndarray]]:
    """Validate native replays and score every seed's roster in every world.

    Returns canonical candidate frames by source seed and matrices keyed
    ``(candidate_seed, world_seed)``.  No realized score is used in selection.
    """
    seeds = sorted(seed_rows)
    if not seeds or set(seeds) != set(seed_artifacts):
        raise ValueError("candidate and artifact seed sets differ")
    canonical: dict[int, pd.DataFrame] = {}
    worlds: dict[int, tuple[list[str], np.ndarray]] = {}
    player_universe: tuple[str, ...] | None = None

    for seed in seeds:
        rows = seed_rows[seed].sort_values("cand_ix", kind="stable").copy()
        cand_ix = pd.to_numeric(rows.cand_ix, errors="raise").astype(int)
        if cand_ix.tolist() != list(range(len(rows))):
            raise ValueError(f"R{seed} candidate indices are not canonical")
        if int(rows.selected.fillna(False).astype(bool).sum()) != entry_count:
            raise ValueError(f"R{seed} does not select exactly {entry_count}")
        rows["roster_key"] = rows.players.map(canonical_roster)
        if rows.roster_key.duplicated().any():
            raise ValueError(f"R{seed} contains duplicate rosters")

        artifact = seed_artifacts[seed]
        required = {"cand_ix", "totals", "tail_line", "player_ids", "player_draws"}
        if not required <= set(artifact):
            raise ValueError(f"R{seed} artifact lacks player worlds")
        totals = np.asarray(artifact["totals"], dtype=np.float32)
        ids = np.asarray(artifact["player_ids"]).astype(str).tolist()
        draws = np.asarray(artifact["player_draws"], dtype=np.float32)
        if totals.shape[0] != len(rows):
            raise ValueError(f"R{seed} artifact candidate count differs")
        if draws.ndim != 2 or draws.shape[0] != len(ids) or \
                draws.shape[1] != totals.shape[1]:
            raise ValueError(f"R{seed} player worlds are misaligned")
        if len(set(ids)) != len(ids):
            raise ValueError(f"R{seed} player ids repeat")
        universe = tuple(sorted(ids))
        if player_universe is None:
            player_universe = universe
        elif universe != player_universe:
            raise ValueError("player-id universes differ across seeds")
        id_to_row = {player_id: index for index, player_id in enumerate(ids)}
        reconstructed = np.stack([
            draws[[id_to_row[player] for player in str(value).split(",")]].sum(axis=0)
            for value in rows.players
        ]).astype(np.float32)
        if not np.allclose(reconstructed, totals, rtol=0.0, atol=tolerance):
            raise ValueError(f"R{seed} native candidate totals do not reconstruct")
        picked = select_from_support(
            totals >= 194.0,
            (totals >= 194.0).mean(axis=1),
            totals.mean(axis=1),
            entry_count,
        )
        expected = rows[rows.selected.fillna(False).astype(bool)].sort_values(
            "selected_rank", kind="stable"
        ).cand_ix.astype(int).tolist()
        if picked != expected:
            raise ValueError(f"R{seed} native selected order does not reproduce")
        canonical[seed] = rows
        worlds[seed] = (ids, draws)

    actual_by_roster: dict[str, float] = {}
    for seed in seeds:
        for row in canonical[seed].itertuples():
            actual = float(row.actual_score)
            prior = actual_by_roster.setdefault(row.roster_key, actual)
            if not np.isclose(prior, actual, rtol=0.0, atol=1e-8):
                raise ValueError("shared roster actual scores differ")

    cross: dict[tuple[int, int], np.ndarray] = {}
    for candidate_seed in seeds:
        rosters = canonical[candidate_seed].players.astype(str).tolist()
        for world_seed in seeds:
            ids, draws = worlds[world_seed]
            id_to_row = {player_id: index for index, player_id in enumerate(ids)}
            cross[(candidate_seed, world_seed)] = np.stack([
                draws[[id_to_row[player] for player in roster.split(",")]].sum(axis=0)
                for roster in rosters
            ]).astype(np.float32)
    return canonical, cross


def evaluate_factorial_slate(
    seed_rows: Mapping[int, pd.DataFrame],
    seed_artifacts: Mapping[int, Mapping[str, np.ndarray]],
    *,
    entry_count: int = 80,
) -> dict:
    """Evaluate all four frozen candidate/world books for one slate."""
    canonical, cross = validate_and_cross_score_slate(
        seed_rows, seed_artifacts, entry_count=entry_count
    )
    seeds = sorted(canonical)
    base = seeds[0]

    union_records: list[tuple[int, int, str, float]] = []
    seen: set[str] = set()
    novelty: dict[str, int] = {}
    for seed in seeds:
        added = 0
        for row_index, row in enumerate(canonical[seed].itertuples()):
            if row.roster_key in seen:
                continue
            seen.add(row.roster_key)
            union_records.append((seed, row_index, row.roster_key, float(row.actual_score)))
            added += 1
        novelty[f"R{seed}"] = added

    base_records = [record for record in union_records if record[0] == base]
    fixed_budget_records = _fixed_budget_records(
        union_records, seeds, len(base_records)
    )

    def build(
        records: Sequence[tuple[int, int, str, float]],
        world_union: bool,
    ) -> tuple[pd.DataFrame, np.ndarray]:
        world_seeds = seeds if world_union else [base]
        blocks = []
        for world_seed in world_seeds:
            blocks.append(np.stack([
                cross[(candidate_seed, world_seed)][row_index]
                for candidate_seed, row_index, _, _ in records
            ]))
        matrix = np.concatenate(blocks, axis=1)
        frame = pd.DataFrame({
            "source_seed": [record[0] for record in records],
            "roster_key": [record[2] for record in records],
            "actual_score": [record[3] for record in records],
        })
        return frame, matrix

    output = {
        "novel_candidates_by_seed": novelty,
        "standalone_seed_books": {},
        "arms": {},
        "fixed_budget_confirmation": {},
    }
    for seed in seeds:
        frame = canonical[seed].copy()
        frame["source_seed"] = seed
        matrix = cross[(seed, seed)]
        picked = frame[
            frame.selected.fillna(False).astype(bool)
        ].sort_values("selected_rank", kind="stable").cand_ix.astype(int).tolist()
        output["standalone_seed_books"][f"R{seed}"] = _evaluate_book(
            frame, matrix, picked, seeds
        )
    for arm in ARMS:
        records = union_records if "CU" in arm else base_records
        frame, matrix = build(records, "WU" in arm)
        clears = matrix >= 194.0
        picked = select_from_support(
            clears, clears.mean(axis=1), matrix.mean(axis=1), entry_count
        )
        output["arms"][arm] = _evaluate_book(
            frame, matrix, picked, seeds
        )
    for arm in CONFIRMATION_ARMS:
        frame, matrix = build(fixed_budget_records, "WU" in arm)
        clears = matrix >= 194.0
        picked = select_from_support(
            clears, clears.mean(axis=1), matrix.mean(axis=1), entry_count
        )
        output["fixed_budget_confirmation"][arm] = _evaluate_book(
            frame, matrix, picked, seeds
        )
    incumbent = set(output["arms"]["C0W0"]["selected_rosters"])
    for arm in ARMS:
        rosters = set(output["arms"][arm]["selected_rosters"])
        output["arms"][arm]["selected_overlap_c0w0"] = len(rosters & incumbent)
    for arm in CONFIRMATION_ARMS:
        comparator = "C0WU" if "WU" in arm else "C0W0"
        rosters = set(output["fixed_budget_confirmation"][arm]["selected_rosters"])
        comparison_rosters = set(output["arms"][comparator]["selected_rosters"])
        output["fixed_budget_confirmation"][arm][
            f"selected_overlap_{comparator.lower()}"
        ] = len(rosters & comparison_rosters)
    return output


def reconstruct_fixed_budget_book(
    seed_rows: Mapping[int, pd.DataFrame],
    seed_artifacts: Mapping[int, Mapping[str, np.ndarray]],
    *,
    world_union: bool = True,
    entry_count: int = 80,
) -> pd.DataFrame:
    """Return the frozen fixed-budget candidate pool and selected membership.

    This is the forensic transport for the adopted CBWU mechanism.  It uses
    the same first-supplying-seed deduplication, source quota/fill order and
    cross-world selector as the registered factorial, while exposing the
    complete fixed-budget candidate frame needed for H/P/C/S decomposition.
    No realized score enters candidate allocation or selection.
    """
    canonical, cross = validate_and_cross_score_slate(
        seed_rows, seed_artifacts, entry_count=entry_count
    )
    seeds = sorted(canonical)
    base = seeds[0]
    union_records: list[tuple[int, int, str, float]] = []
    seen: set[str] = set()
    for seed in seeds:
        for row_index, row in enumerate(canonical[seed].itertuples()):
            if row.roster_key in seen:
                continue
            seen.add(row.roster_key)
            union_records.append(
                (seed, row_index, row.roster_key, float(row.actual_score))
            )
    base_budget = sum(record[0] == base for record in union_records)
    records = _fixed_budget_records(union_records, seeds, base_budget)
    world_seeds = seeds if world_union else [base]
    matrix = np.concatenate([
        np.stack([
            cross[(candidate_seed, world_seed)][row_index]
            for candidate_seed, row_index, _, _ in records
        ])
        for world_seed in world_seeds
    ], axis=1)
    clears = matrix >= 194.0
    picked = select_from_support(
        clears, clears.mean(axis=1), matrix.mean(axis=1), entry_count
    )
    selected_rank = {row_index: rank for rank, row_index in enumerate(picked)}
    return pd.DataFrame({
        "cand_ix": list(range(len(records))),
        "players": [record[2] for record in records],
        "actual_score": [record[3] for record in records],
        "source_seed": [record[0] for record in records],
        "tag": [f"CBWU_R{record[0]}" for record in records],
        "all_tags": [f"CBWU_R{record[0]}" for record in records],
        "p_line": clears.mean(axis=1),
        "sim_mean": matrix.mean(axis=1),
        "sim_q99": np.quantile(matrix, 0.99, axis=1),
        "selected": [index in selected_rank for index in range(len(records))],
        "selected_rank": [
            selected_rank.get(index) for index in range(len(records))
        ],
    })


def _book_metrics(slates: Sequence[dict], key: str, book: str) -> dict:
    best = np.asarray([slate[key][book]["selected_best"] for slate in slates])
    oracle = np.asarray([slate[key][book]["oracle_best"] for slate in slates])
    metrics = {
        "selected_tail": {str(t): int((best >= t).sum()) for t in TAILS},
        "oracle_tail": {str(t): int((oracle >= t).sum()) for t in TAILS},
        "selected_mean": float(best.mean()),
        "selected_median": float(np.median(best)),
        "candidate_count_mean": float(np.mean([
            slate[key][book]["candidate_count"] for slate in slates
        ])),
    }
    metrics["selected_weekly_best_pinball"] = {
        str(level): _pinball(
            best,
            np.asarray([
                slate[key][book]["simulated_weekly_best_quantile"][str(level)]
                for slate in slates
            ]),
            level,
        )
        for level in PROPER_SCORE_QUANTILES
    }
    return metrics


def summarize_standalone_seed_books(slates: Sequence[dict]) -> dict:
    if not slates:
        raise ValueError("standalone result has no slates")
    seeds = tuple(sorted(slates[0]["standalone_seed_books"]))
    metrics = {
        seed: _book_metrics(slates, "standalone_seed_books", seed)
        for seed in seeds
    }
    pairwise_overlap = {}
    overlap_values = []
    for left_index, left in enumerate(seeds):
        for right in seeds[left_index + 1:]:
            values = [
                len(
                    set(slate["standalone_seed_books"][left]["selected_rosters"])
                    & set(slate["standalone_seed_books"][right]["selected_rosters"])
                )
                for slate in slates
            ]
            pairwise_overlap[f"{left}_{right}"] = float(np.mean(values))
            overlap_values.extend(values)
    return {
        "metrics": metrics,
        "tail_count_envelope": {
            str(tail): {
                "min": int(min(
                    metrics[seed]["selected_tail"][str(tail)]
                    for seed in seeds
                )),
                "max": int(max(
                    metrics[seed]["selected_tail"][str(tail)]
                    for seed in seeds
                )),
                "range": int(
                    max(metrics[seed]["selected_tail"][str(tail)] for seed in seeds)
                    - min(metrics[seed]["selected_tail"][str(tail)] for seed in seeds)
                ),
            }
            for tail in TAILS
        },
        "selected_mean_envelope": {
            "min": float(min(metrics[seed]["selected_mean"] for seed in seeds)),
            "max": float(max(metrics[seed]["selected_mean"] for seed in seeds)),
            "range": float(
                max(metrics[seed]["selected_mean"] for seed in seeds)
                - min(metrics[seed]["selected_mean"] for seed in seeds)
            ),
        },
        "selected_median_envelope": {
            "min": float(min(metrics[seed]["selected_median"] for seed in seeds)),
            "max": float(max(metrics[seed]["selected_median"] for seed in seeds)),
            "range": float(
                max(metrics[seed]["selected_median"] for seed in seeds)
                - min(metrics[seed]["selected_median"] for seed in seeds)
            ),
        },
        "pairwise_selected_overlap_mean": float(np.mean(overlap_values)),
        "pairwise_selected_overlap_by_pair": pairwise_overlap,
    }


def summarize_factorial(slates: Sequence[dict]) -> dict:
    if not slates:
        raise ValueError("factorial result has no slates")
    metrics: dict[str, dict] = {}
    for arm in ARMS:
        metrics[arm] = _book_metrics(slates, "arms", arm)
        metrics[arm]["selected_overlap_c0w0_mean"] = float(np.mean([
                slate["arms"][arm]["selected_overlap_c0w0"] for slate in slates
        ]))

    def rank(eligible: Sequence[str]) -> list[str]:
        return sorted(
            eligible,
            key=lambda arm: (
                *[-metrics[arm]["selected_tail"][str(t)] for t in TAILS],
                -metrics[arm]["selected_mean"],
                LEAST_CHANGE_ORDER.index(arm),
            ),
        )
    order = rank(ARMS)
    production_order = rank(PRODUCTION_ELIGIBLE_ARMS)
    confirmation_metrics = {
        arm: _book_metrics(slates, "fixed_budget_confirmation", arm)
        for arm in CONFIRMATION_ARMS
    }

    def rank_with_metrics(
        eligible: Sequence[str], values: Mapping[str, dict]
    ) -> list[str]:
        return sorted(
            eligible,
            key=lambda arm: (
                *[-values[arm]["selected_tail"][str(t)] for t in TAILS],
                -values[arm]["selected_mean"],
                eligible.index(arm),
            ),
        )

    incumbent = np.asarray([
        slate["arms"]["C0W0"]["selected_best"] for slate in slates
    ])
    large_deltas = []
    for index, slate in enumerate(slates):
        for arm in ARMS[1:]:
            delta = float(slate["arms"][arm]["selected_best"] - incumbent[index])
            if abs(delta) >= 10.0:
                large_deltas.append({"slate_index": index, "arm": arm, "delta": delta})
    contrasts = {}
    for metric_name in ("selected_mean",):
        values = {arm: metrics[arm][metric_name] for arm in ARMS}
        contrasts[metric_name] = {
            "candidate_main_at_w0": values["CUW0"] - values["C0W0"],
            "candidate_main_at_wu": values["CUWU"] - values["C0WU"],
            "world_main_at_c0": values["C0WU"] - values["C0W0"],
            "world_main_at_cu": values["CUWU"] - values["CUW0"],
            "interaction": (
                values["CUWU"] - values["CUW0"]
                - values["C0WU"] + values["C0W0"]
            ),
        }
    contrasts["selected_tail"] = {}
    for tail in TAILS:
        values = {arm: metrics[arm]["selected_tail"][str(tail)] for arm in ARMS}
        contrasts["selected_tail"][str(tail)] = {
            "candidate_main_at_w0": values["CUW0"] - values["C0W0"],
            "candidate_main_at_wu": values["CUWU"] - values["C0WU"],
            "world_main_at_c0": values["C0WU"] - values["C0W0"],
            "world_main_at_cu": values["CUWU"] - values["CUW0"],
            "interaction": (
                values["CUWU"] - values["CUW0"]
                - values["C0WU"] + values["C0W0"]
            ),
        }
    world_union = production_order[0] == "C0WU"
    incumbent_production = production_order[0]
    confirmation_arm = "CBWU" if world_union else "CBW0"
    confirmation_order = rank_with_metrics(
        (incumbent_production, confirmation_arm),
        {**metrics, **confirmation_metrics},
    )
    candidate_union_required = order[0].startswith("CU")
    final_production_arm = (
        confirmation_order[0]
        if candidate_union_required
        else incumbent_production
    )
    return {
        "metrics": metrics,
        "selected_arm": order[0],
        "ranked_arms": order,
        "production_selected_arm": production_order[0],
        "production_ranked_arms": production_order,
        "candidate_union_confirmation_required": candidate_union_required,
        "fixed_budget_confirmation": {
            "metrics": confirmation_metrics,
            "applicable_arm": confirmation_arm,
            "ranked_against_incumbent": confirmation_order,
            "passes_if_required": confirmation_order[0] == confirmation_arm,
        },
        "final_production_arm": final_production_arm,
        "factorial_contrasts": contrasts,
        "weekly_deltas_at_least_10": large_deltas,
    }


__all__ = [
    "ARMS", "CONFIRMATION_ARMS", "TAILS", "canonical_roster",
    "evaluate_factorial_slate",
    "summarize_factorial", "summarize_standalone_seed_books",
    "validate_and_cross_score_slate",
]
