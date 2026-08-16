"""Score-free world-ranking primitives for the ATLAS construction audit.

The incumbent boom generator ranks a simulated world by the sum of every
player's points.  ATLAS first asks whether a roster-sized upper bound is a
better way to find worlds that can support an exceptional legal lineup.  This
module deliberately knows nothing about realized outcomes, contest ranks, or
payouts.
"""

from __future__ import annotations

from typing import Mapping, Sequence

import numpy as np

from ..optimizer.lineup import Lineup, StackRules, optimize


# Exact DK Classic skill-count shapes once QB=1, DST=1 and FLEX is assigned.
CLASSIC_SKILL_PATTERNS = ((2, 4, 1), (2, 3, 2), (3, 3, 1))
EXACT_IDENTITY_TOLERANCE = 1e-6


def _top_k_sum(draws: np.ndarray, rows: np.ndarray, k: int) -> np.ndarray:
    if len(rows) < k:
        raise ValueError(f"ATLAS roster bound requires at least {k} rows")
    values = draws[rows]
    split = values.shape[0] - k
    return np.partition(values, split, axis=0)[split:].sum(axis=0)


def roster_slot_upper_bound(
    row_draws: np.ndarray,
    positions: Sequence[str],
) -> np.ndarray:
    """Return a cheap roster-sized upper bound for every simulated world.

    It enforces the exact QB/DST and RB/WR/TE slot counts, but relaxes salary,
    team, game, stack and anti-correlation constraints.  Consequently it is
    an upper bound on the exact legal optimum, not a substitute for the MILP.
    Its only purpose is to choose a small world set for exact score-free
    solves.  The final ATLAS diagnostic must compare exact legal optima for
    both selected world sets.
    """
    draws = np.asarray(row_draws, dtype=np.float64)
    pos = np.asarray([str(value).upper() for value in positions], dtype=object)
    if draws.ndim != 2 or draws.shape[0] != len(pos) or draws.shape[1] == 0:
        raise ValueError("ATLAS player draws and positions are misaligned")
    if not np.isfinite(draws).all():
        raise ValueError("ATLAS player draws must be finite")

    rows = {name: np.flatnonzero(pos == name) for name in (
        "QB", "RB", "WR", "TE", "DST"
    )}
    fixed = _top_k_sum(draws, rows["QB"], 1) + _top_k_sum(
        draws, rows["DST"], 1
    )
    skill_bounds = []
    for n_rb, n_wr, n_te in CLASSIC_SKILL_PATTERNS:
        skill_bounds.append(
            _top_k_sum(draws, rows["RB"], n_rb)
            + _top_k_sum(draws, rows["WR"], n_wr)
            + _top_k_sum(draws, rows["TE"], n_te)
        )
    return fixed + np.maximum.reduce(skill_bounds)


def rank_worlds(values: np.ndarray, n_worlds: int) -> np.ndarray:
    """Deterministically rank descending values, breaking ties by world ID."""
    scores = np.asarray(values, dtype=np.float64)
    if scores.ndim != 1 or not np.isfinite(scores).all():
        raise ValueError("ATLAS world-ranking values must be one finite vector")
    n = int(n_worlds)
    if not 1 <= n <= len(scores):
        raise ValueError("ATLAS requested world count is outside the draw book")
    world_id = np.arange(len(scores), dtype=np.int64)
    return np.lexsort((world_id, -scores))[:n]


def compare_world_rankings(
    row_draws: np.ndarray,
    positions: Sequence[str],
    n_worlds: int = 40,
) -> dict:
    """Build the outcome-free incumbent and attainable-proxy world sets."""
    draws = np.asarray(row_draws, dtype=np.float64)
    incumbent_value = draws.sum(axis=0)
    attainable_value = roster_slot_upper_bound(draws, positions)
    incumbent = rank_worlds(incumbent_value, n_worlds)
    attainable = rank_worlds(attainable_value, n_worlds)
    shared = np.intersect1d(incumbent, attainable, assume_unique=True)
    return {
        "version": "atlas-world-ranking-scorefree-v1",
        "uses_realized_outcomes": False,
        "proxy": "classic-roster-slot-upper-bound",
        "relaxed_constraints": [
            "salary", "team", "minimum-games", "stack", "rb-anticorrelation",
        ],
        "worlds": int(draws.shape[1]),
        "selected_worlds": int(n_worlds),
        "incumbent_world_ids": incumbent.tolist(),
        "attainable_world_ids": attainable.tolist(),
        "shared_worlds": int(len(shared)),
        "jaccard": float(
            len(shared) / len(np.union1d(incumbent, attainable))
        ),
    }


def _lineup_structure(lineup: Lineup) -> dict:
    players = list(lineup.players)
    quarterbacks = [
        player for player in players
        if str(player.get("pos", "")).upper() == "QB"
    ]
    if len(quarterbacks) != 1:
        raise ValueError("ATLAS exact world lineup lacks one quarterback")
    qb = quarterbacks[0]
    qb_team = str(qb.get("team", ""))
    qb_opp = str(qb.get("opp", ""))
    catchers = sorted(str(player["id"]) for player in players if (
        str(player.get("team", "")) == qb_team
        and str(player.get("pos", "")).upper() in {"WR", "TE"}
    ))
    bring_backs = sorted(str(player["id"]) for player in players if (
        str(player.get("team", "")) == qb_opp
        and str(player.get("pos", "")).upper() in {"RB", "WR", "TE"}
    ))
    game_counts: dict[str, int] = {}
    for player in players:
        game = str(player.get("game_id", ""))
        if game:
            game_counts[game] = game_counts.get(game, 0) + 1
    dominant_game = min(
        game_counts,
        key=lambda game: (-game_counts[game], game),
    ) if game_counts else ""
    return {
        "roster": sorted(str(player["id"]) for player in players),
        "qb_stack_core": [str(qb["id"]), *catchers, *bring_backs],
        "dominant_game": dominant_game,
    }


def solve_exact_worlds(
    player_rows: Sequence[Mapping],
    row_draws: np.ndarray,
    world_ids: Sequence[int],
    *,
    stack: StackRules,
    env: Mapping[str, str],
) -> dict[int, dict]:
    """Solve exact legal lineups for a bounded score-free world set."""
    original_players = [dict(player) for player in player_rows]
    draws = np.asarray(row_draws, dtype=np.float64)
    if draws.ndim != 2 or draws.shape[0] != len(original_players):
        raise ValueError("ATLAS exact-solve player worlds are misaligned")
    if not np.isfinite(draws).all():
        raise ValueError("ATLAS exact-solve worlds must be finite")
    order = sorted(
        range(len(original_players)),
        key=lambda index: str(original_players[index]["id"]),
    )
    players = [original_players[index] for index in order]
    draws = draws[np.asarray(order, dtype=int)]
    identity_rank = {
        player["id"]: rank for rank, player in enumerate(players, start=1)
    }
    result: dict[int, dict] = {}
    for raw_world in world_ids:
        world = int(raw_world)
        if not 0 <= world < draws.shape[1] or world in result:
            raise ValueError("ATLAS exact-solve world IDs are invalid")
        world_players = [
            {**player, "atlas_world_score": float(draws[index, world])}
            for index, player in enumerate(players)
        ]
        primary = optimize(
            world_players,
            stack=stack,
            objective_col="atlas_world_score",
            env=env,
        )
        if primary is None:
            raise RuntimeError(f"ATLAS world {world} has no legal lineup")
        optimum = float(sum(
            player["atlas_world_score"] for player in primary.players
        ))
        tied_players = [{
            **player,
            "atlas_identity_score": -float(identity_rank[player["id"]]),
        } for player in world_players]
        lineup = optimize(
            tied_players,
            stack=stack,
            objective_col="atlas_identity_score",
            objective_floor_col="atlas_world_score",
            objective_floor=optimum - EXACT_IDENTITY_TOLERANCE,
            env=env,
        )
        if lineup is None:
            raise RuntimeError(
                f"ATLAS world {world} identity tiebreak is infeasible"
            )
        roster_score = float(sum(
            player["atlas_world_score"] for player in lineup.players
        ))
        if roster_score < optimum - EXACT_IDENTITY_TOLERANCE - 1e-8:
            raise AssertionError("ATLAS identity tiebreak violates score floor")
        result[world] = {
            "score": optimum,
            "canonical_roster_score": roster_score,
            "identity_rank_sum": int(sum(
                identity_rank[player["id"]] for player in lineup.players
            )),
            "identity_tolerance": EXACT_IDENTITY_TOLERANCE,
            **_lineup_structure(lineup),
        }
    return result


def complete_world_ranking_diagnostic(
    player_rows: Sequence[Mapping],
    row_draws: np.ndarray,
    *,
    stack: StackRules,
    env: Mapping[str, str],
    n_worlds: int = 40,
) -> dict:
    """Compare exact legal quality after both score-free ranking rules."""
    positions = [str(player.get("pos", "")) for player in player_rows]
    report = compare_world_rankings(row_draws, positions, n_worlds=n_worlds)
    incumbent = report["incumbent_world_ids"]
    attainable = report["attainable_world_ids"]
    union = sorted(set(incumbent) | set(attainable))
    exact = solve_exact_worlds(
        player_rows, row_draws, union, stack=stack, env=env
    )
    bound = roster_slot_upper_bound(row_draws, positions)
    if any(exact[world]["score"] > bound[world] + 1e-7 for world in union):
        raise AssertionError("ATLAS exact legal score exceeds its upper bound")

    def summarize(worlds: Sequence[int]) -> dict:
        scores = np.asarray([exact[world]["score"] for world in worlds])
        rosters = {tuple(exact[world]["roster"]) for world in worlds}
        cores = {tuple(exact[world]["qb_stack_core"]) for world in worlds}
        games = {exact[world]["dominant_game"] for world in worlds}
        return {
            "mean_exact_legal_optimum": float(scores.mean()),
            "median_exact_legal_optimum": float(np.median(scores)),
            "q25_exact_legal_optimum": float(np.quantile(scores, 0.25)),
            "unique_exact_rosters": len(rosters),
            "unique_qb_stack_cores": len(cores),
            "unique_dominant_games": len(games - {""}),
        }

    report["incumbent_exact"] = summarize(incumbent)
    report["attainable_exact"] = summarize(attainable)
    report["exact_union_worlds"] = len(union)
    report["exact_world_results"] = {
        str(world): exact[world] for world in union
    }
    incumbent_value = np.asarray(row_draws, dtype=np.float64).sum(axis=0)
    attainable_value = roster_slot_upper_bound(row_draws, positions)
    incumbent_order = rank_worlds(incumbent_value, len(incumbent_value))
    attainable_order = rank_worlds(attainable_value, len(attainable_value))
    union_exact = np.asarray([exact[world]["score"] for world in union])
    union_bound = attainable_value[np.asarray(union, dtype=int)]
    union_proxy_rank = np.empty(len(union), dtype=float)
    union_exact_rank = np.empty(len(union), dtype=float)
    union_proxy_rank[np.lexsort((np.asarray(union), -union_bound))] = np.arange(
        len(union), dtype=float
    )
    union_exact_rank[np.lexsort((np.asarray(union), -union_exact))] = np.arange(
        len(union), dtype=float
    )
    correlation = (
        float(np.corrcoef(union_proxy_rank, union_exact_rank)[0, 1])
        if len(union) > 1 else 1.0
    )
    paired_delta = np.asarray([
        exact[treatment]["score"] - exact[control]["score"]
        for control, treatment in zip(incumbent, attainable)
    ])
    overlap = {}
    for top in (8, 20, 40):
        use = min(top, n_worlds)
        overlap[str(top)] = int(len(set(
            incumbent_order[:use].tolist()
        ) & set(attainable_order[:use].tolist())))
    incumbent_cutoff = incumbent_value[incumbent_order[n_worlds - 1]]
    attainable_cutoff = attainable_value[attainable_order[n_worlds - 1]]
    slack = union_bound - union_exact
    report["proxy_diagnostics"] = {
        "proxy_minus_exact_slack": {
            "mean": float(slack.mean()),
            "median": float(np.median(slack)),
            "q90": float(np.quantile(slack, 0.90)),
            "max": float(slack.max()),
        },
        "proxy_exact_rank_correlation_union": correlation,
        "paired_exact_quality": {
            "wins": int(np.count_nonzero(paired_delta > 1e-9)),
            "ties": int(np.count_nonzero(np.abs(paired_delta) <= 1e-9)),
            "losses": int(np.count_nonzero(paired_delta < -1e-9)),
        },
        "top_world_overlap": overlap,
        "cutoff_ties": {
            "incumbent": int(np.count_nonzero(
                incumbent_value == incumbent_cutoff
            )),
            "attainable": int(np.count_nonzero(
                attainable_value == attainable_cutoff
            )),
        },
    }
    return report


def aggregate_transfer_gate(rows: Sequence[Mapping]) -> dict:
    """Apply the frozen production-law Part-A transfer disposition."""
    original = aggregate_scorefree_gate(rows)
    conditions = original["conditions"]
    quality_names = (
        "aggregate_mean_improves",
        "at_least_three_seed_means_improve",
        "aggregate_q25_nonworse",
    )
    diversity_names = (
        "roster_diversity_at_least_80pct",
        "stack_core_diversity_at_least_80pct",
        "dominant_game_diversity_at_least_80pct",
    )
    return {
        **original,
        "version": "atlas-current-money-transfer-gate-v1",
        "quality_conditions": {
            name: bool(conditions[name]) for name in quality_names
        },
        "raw_diversity_diagnostics": {
            name: bool(conditions[name]) for name in diversity_names
        },
        "passes_part_a_transfer": bool(all(
            conditions[name] for name in quality_names
        )),
        "passes_original_all_six": bool(all(conditions.values())),
    }


def aggregate_scorefree_gate(rows: Sequence[Mapping]) -> dict:
    """Apply the frozen five-seed ATLAS world-ranking falsifier."""
    if not rows:
        raise ValueError("ATLAS aggregate requires diagnostic rows")
    frame = []
    for row in rows:
        if row.get("uses_realized_outcomes") is not False:
            raise ValueError("ATLAS aggregate received an outcome-facing row")
        try:
            seed = int(row["seed"])
            control = row["incumbent_exact"]
            treatment = row["attainable_exact"]
            frame.append({
                "seed": seed,
                "mean_delta": float(treatment["mean_exact_legal_optimum"])
                - float(control["mean_exact_legal_optimum"]),
                "q25_delta": float(treatment["q25_exact_legal_optimum"])
                - float(control["q25_exact_legal_optimum"]),
                "roster_ratio": float(treatment["unique_exact_rosters"])
                / max(1.0, float(control["unique_exact_rosters"])),
                "core_ratio": float(treatment["unique_qb_stack_cores"])
                / max(1.0, float(control["unique_qb_stack_cores"])),
                "game_ratio": float(treatment["unique_dominant_games"])
                / max(1.0, float(control["unique_dominant_games"])),
            })
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("ATLAS diagnostic row is incomplete") from exc
    seeds = sorted({row["seed"] for row in frame})
    if seeds != [0, 1, 2, 3, 4]:
        raise ValueError("ATLAS aggregate requires exact seeds R0--R4")
    numeric = np.asarray([
        [
            row["mean_delta"], row["q25_delta"], row["roster_ratio"],
            row["core_ratio"], row["game_ratio"],
        ]
        for row in frame
    ], dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("ATLAS aggregate metrics must be finite")
    per_seed_mean_delta = {
        str(seed): float(np.mean([
            row["mean_delta"] for row in frame if row["seed"] == seed
        ]))
        for seed in seeds
    }
    conditions = {
        "aggregate_mean_improves": float(np.mean([
            row["mean_delta"] for row in frame
        ])) > 0.0,
        "at_least_three_seed_means_improve": sum(
            value > 0.0 for value in per_seed_mean_delta.values()
        ) >= 3,
        "aggregate_q25_nonworse": float(np.mean([
            row["q25_delta"] for row in frame
        ])) >= 0.0,
        "roster_diversity_at_least_80pct": float(np.mean([
            row["roster_ratio"] for row in frame
        ])) >= 0.80,
        "stack_core_diversity_at_least_80pct": float(np.mean([
            row["core_ratio"] for row in frame
        ])) >= 0.80,
        "dominant_game_diversity_at_least_80pct": float(np.mean([
            row["game_ratio"] for row in frame
        ])) >= 0.80,
    }
    return {
        "version": "atlas-world-ranking-scorefree-gate-v1",
        "uses_realized_outcomes": False,
        "rows": len(frame),
        "slates": len({
            (int(row["season"]), int(row["week"])) for row in rows
        }),
        "per_seed_mean_delta": per_seed_mean_delta,
        "aggregate_mean_delta": float(np.mean([
            row["mean_delta"] for row in frame
        ])),
        "aggregate_q25_delta": float(np.mean([
            row["q25_delta"] for row in frame
        ])),
        "mean_diversity_ratios": {
            name: float(np.mean([row[name] for row in frame]))
            for name in ("roster_ratio", "core_ratio", "game_ratio")
        },
        "conditions": conditions,
        "passes_scorefree_falsifier": bool(all(conditions.values())),
    }


__all__ = [
    "CLASSIC_SKILL_PATTERNS",
    "EXACT_IDENTITY_TOLERANCE",
    "aggregate_scorefree_gate",
    "aggregate_transfer_gate",
    "compare_world_rankings",
    "complete_world_ranking_diagnostic",
    "rank_worlds",
    "roster_slot_upper_bound",
    "solve_exact_worlds",
]
