"""Exact-80 multi-seed candidate/world factorial on immutable artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from ..optimizer.lineup import select_from_support


ARMS = ("C0W0", "C0WU", "CUW0", "CUWU")
TAILS = (240, 230, 220, 210, 200, 194, 187)
LEAST_CHANGE_ORDER = ARMS


def canonical_roster(value: str) -> str:
    ids = [item for item in str(value).split(",") if item]
    if len(ids) != 9 or len(set(ids)) != 9:
        raise ValueError("candidate roster must contain nine unique player ids")
    return ",".join(sorted(ids))


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

    def build(candidate_union: bool, world_union: bool) -> tuple[pd.DataFrame, np.ndarray]:
        records = (
            union_records
            if candidate_union
            else [record for record in union_records if record[0] == base]
        )
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

    output = {"novel_candidates_by_seed": novelty, "arms": {}}
    for arm in ARMS:
        frame, matrix = build("CU" in arm, "WU" in arm)
        clears = matrix >= 194.0
        picked = select_from_support(
            clears, clears.mean(axis=1), matrix.mean(axis=1), entry_count
        )
        selected = frame.iloc[picked]
        selected_matrix = matrix[picked]
        output["arms"][arm] = {
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
        }
    incumbent = set(output["arms"]["C0W0"]["selected_rosters"])
    for arm in ARMS:
        rosters = set(output["arms"][arm]["selected_rosters"])
        output["arms"][arm]["selected_overlap_c0w0"] = len(rosters & incumbent)
    return output


def summarize_factorial(slates: Sequence[dict]) -> dict:
    if not slates:
        raise ValueError("factorial result has no slates")
    metrics: dict[str, dict] = {}
    for arm in ARMS:
        best = np.asarray([slate["arms"][arm]["selected_best"] for slate in slates])
        oracle = np.asarray([slate["arms"][arm]["oracle_best"] for slate in slates])
        metrics[arm] = {
            "selected_tail": {str(t): int((best >= t).sum()) for t in TAILS},
            "oracle_tail": {str(t): int((oracle >= t).sum()) for t in TAILS},
            "selected_mean": float(best.mean()),
            "selected_median": float(np.median(best)),
            "candidate_count_mean": float(np.mean([
                slate["arms"][arm]["candidate_count"] for slate in slates
            ])),
            "selected_overlap_c0w0_mean": float(np.mean([
                slate["arms"][arm]["selected_overlap_c0w0"] for slate in slates
            ])),
        }
    order = sorted(
        ARMS,
        key=lambda arm: (
            *[-metrics[arm]["selected_tail"][str(t)] for t in TAILS],
            -metrics[arm]["selected_mean"],
            LEAST_CHANGE_ORDER.index(arm),
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
    return {
        "metrics": metrics,
        "selected_arm": order[0],
        "ranked_arms": order,
        "weekly_deltas_at_least_10": large_deltas,
    }


__all__ = [
    "ARMS", "TAILS", "canonical_roster", "evaluate_factorial_slate",
    "summarize_factorial", "validate_and_cross_score_slate",
]
