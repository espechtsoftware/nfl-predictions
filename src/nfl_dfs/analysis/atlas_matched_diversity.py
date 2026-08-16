"""Score-free construction primitives for the frozen ATLAS 8x5 MVP.

This module is intentionally limited to pre-lock player worlds, candidate
identities and simulator support.  It has no field for realized scores,
contest ranks, payouts or post-lock ownership.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from math import sqrt
from typing import Mapping, Sequence

import numpy as np

from ..backtest.engine import CandidateBatch
from ..optimizer.lineup import Lineup, StackRules, optimize


VERSION = "atlas-matched-diversity-mvp-v1"
REGISTERED_SEEDS = ("R0", "R1", "R2", "R3", "R4")
REGISTERED_TAGS = {"lev", "epi", "game", "dark", "qbvar", "boom"}
TAIL_LINE = 194.0
N_CLUSTERS = 8
LINEUPS_PER_CLUSTER = 5
N_ATLAS_LINEUPS = N_CLUSTERS * LINEUPS_PER_CLUSTER
NEAR_OPTIMAL_FRACTION = 0.98
INTERACTION_TOLERANCE = 1e-9

Interaction = tuple[str, ...]
Roster = tuple[str, ...]


def _roster(lineup: Lineup) -> Roster:
    roster = tuple(sorted(str(value) for value in lineup.ids))
    if len(roster) != 9:
        raise ValueError("ATLAS MVP roster must have nine unique players")
    return roster


def _structure(lineup: Lineup) -> dict:
    players = list(lineup.players)
    qbs = [row for row in players if str(row.get("pos", "")).upper() == "QB"]
    if len(qbs) != 1:
        raise ValueError("ATLAS MVP lineup must contain one quarterback")
    qb = qbs[0]
    catchers = sorted(str(row["id"]) for row in players if (
        str(row.get("team", "")) == str(qb.get("team", ""))
        and str(row.get("pos", "")).upper() in {"WR", "TE"}
    ))
    bring_backs = sorted(str(row["id"]) for row in players if (
        str(row.get("team", "")) == str(qb.get("opp", ""))
        and str(row.get("pos", "")).upper() in {"RB", "WR", "TE"}
    ))
    game_counts = Counter(
        str(row.get("game_id")) for row in players if row.get("game_id")
    )
    dominant_game = min(
        game_counts, key=lambda game: (-game_counts[game], game),
    ) if game_counts else ""
    return {
        "roster": list(_roster(lineup)),
        "qb_stack_core": [str(qb["id"]), *catchers, *bring_backs],
        "dominant_game": dominant_game,
    }


def build_structural_clusters(
    world_order: Sequence[int], exact_worlds: Mapping[int, Mapping],
) -> dict:
    """Freeze eight deterministic anchors and assign all top-40 worlds."""
    order = tuple(int(value) for value in world_order)
    if len(order) != 40 or len(set(order)) != 40 or set(order) != set(exact_worlds):
        raise ValueError("ATLAS MVP clusters require exact top-40 worlds")
    required = {"roster", "qb_stack_core", "dominant_game"}
    normalized: dict[int, dict] = {}
    for world in order:
        row = exact_worlds[world]
        if not required <= set(row):
            raise ValueError("ATLAS MVP exact-world structure is incomplete")
        roster = tuple(sorted(str(value) for value in row["roster"]))
        if len(roster) != 9 or len(set(roster)) != 9:
            raise ValueError("ATLAS MVP exact-world roster is invalid")
        normalized[world] = {
            "roster": roster,
            "qb_stack_core": tuple(str(value) for value in row["qb_stack_core"]),
            "dominant_game": str(row["dominant_game"]),
        }
    if len({row["roster"] for row in normalized.values()}) < N_CLUSTERS:
        raise ValueError("ATLAS MVP has fewer than eight exact unique rosters")

    anchors: list[tuple[int, str]] = []
    anchor_rosters: set[Roster] = set()
    seen_games: set[str] = set()
    for world in order:
        row = normalized[world]
        if row["roster"] not in anchor_rosters and \
                row["dominant_game"] not in seen_games:
            anchors.append((world, "dominant_game"))
            anchor_rosters.add(row["roster"])
            seen_games.add(row["dominant_game"])
            if len(anchors) == N_CLUSTERS:
                break
    if len(anchors) < N_CLUSTERS:
        seen_cores = {
            normalized[world]["qb_stack_core"] for world, _ in anchors
        }
        for world in order:
            row = normalized[world]
            if row["roster"] not in anchor_rosters and \
                    row["qb_stack_core"] not in seen_cores:
                anchors.append((world, "qb_stack_core"))
                anchor_rosters.add(row["roster"])
                seen_cores.add(row["qb_stack_core"])
                if len(anchors) == N_CLUSTERS:
                    break
    if len(anchors) < N_CLUSTERS:
        for world in order:
            roster = normalized[world]["roster"]
            if roster not in anchor_rosters:
                anchors.append((world, "exact_world_identity"))
                anchor_rosters.add(roster)
                if len(anchors) == N_CLUSTERS:
                    break
    if len(anchors) != N_CLUSTERS:
        raise ValueError("ATLAS MVP could not form eight cluster anchors")

    anchor_worlds = {world for world, _ in anchors}
    memberships: list[list[int]] = [[world] for world, _ in anchors]
    for world in order:
        if world in anchor_worlds:
            continue
        row = normalized[world]
        same_game = [
            index for index, (anchor, _) in enumerate(anchors)
            if normalized[anchor]["dominant_game"] == row["dominant_game"]
        ]
        if same_game:
            destination = same_game[0]
        else:
            overlaps = [
                len(set(row["roster"]) & set(normalized[anchor]["roster"]))
                for anchor, _ in anchors
            ]
            destination = max(range(N_CLUSTERS), key=lambda index: (
                overlaps[index], -index,
            ))
        memberships[destination].append(world)
    rank = {world: index for index, world in enumerate(order)}
    for membership in memberships:
        membership.sort(key=lambda world: (rank[world], world))
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "world_order": list(order),
        "anchors": [{
            "cluster": index,
            "world": world,
            "fallback_reason": reason,
            **{key: list(value) if isinstance(value, tuple) else value
               for key, value in normalized[world].items()},
        } for index, (world, reason) in enumerate(anchors)],
        "clusters": [list(values) for values in memberships],
    }


def _lineup_interactions(
    roster: Sequence[str], player_by_id: Mapping[str, Mapping],
) -> tuple[set[Interaction], set[Interaction]]:
    ids = tuple(sorted(str(value) for value in roster))
    pairs = set(combinations(ids, 2))
    qbs = [player_by_id[value] for value in ids if str(
        player_by_id[value].get("pos", "")
    ).upper() == "QB"]
    triples: set[Interaction] = set()
    if len(qbs) == 1:
        qb = qbs[0]
        qb_id = str(qb["id"])
        catchers = sorted(value for value in ids if (
            str(player_by_id[value].get("team", "")) == str(qb.get("team", ""))
            and str(player_by_id[value].get("pos", "")).upper() in {"WR", "TE"}
        ))
        triples.update(
            tuple(sorted((qb_id, first, second)))
            for first, second in combinations(catchers, 2)
        )
    return pairs, triples


def price_native_interactions(
    books: Mapping[str, CandidateBatch], *, tail_line: float = TAIL_LINE,
) -> dict:
    """Price native pairs/cores using the frozen leave-one-seed-out law."""
    if tuple(sorted(books)) != REGISTERED_SEEDS or not np.isfinite(tail_line):
        raise ValueError("ATLAS MVP interaction pricing requires R0--R4")
    base = books["R0"]
    base_ids = {str(value) for value in base.player_ids}
    player_by_id = {
        str(player_id): {**row, "id": str(player_id)}
        for player_id, row in zip(base.player_ids, base.player_rows, strict=True)
    }
    if set(player_by_id) != base_ids:
        raise ValueError("ATLAS MVP base player catalog repeats")
    roster_seeds: dict[Roster, set[str]] = {}
    roster_interactions: dict[Roster, tuple[set[Interaction], set[Interaction]]] = {}
    interaction_seeds: dict[Interaction, set[str]] = {}
    nonboom_covered: set[Interaction] = set()
    for seed in REGISTERED_SEEDS:
        batch = books[seed]
        if {str(value) for value in batch.player_ids} != base_ids or \
                len(batch.candidates) != np.asarray(batch.candidate_totals).shape[0]:
            raise ValueError("ATLAS MVP native book is misaligned")
        for lineup in batch.candidates:
            if str(lineup.tag) not in REGISTERED_TAGS:
                raise ValueError("ATLAS MVP native tag is not registered")
            roster = _roster(lineup)
            roster_seeds.setdefault(roster, set()).add(seed)
            interactions = roster_interactions.setdefault(
                roster, _lineup_interactions(roster, player_by_id),
            )
            for key in interactions[0] | interactions[1]:
                interaction_seeds.setdefault(key, set()).add(seed)
            if str(lineup.tag) != "boom":
                nonboom_covered.update(interactions[0])
                nonboom_covered.update(interactions[1])
    rosters = tuple(sorted(roster_seeds))
    eligible_pairs = set().union(*(roster_interactions[row][0] for row in rosters))
    eligible_triples = set().union(*(roster_interactions[row][1] for row in rosters))
    if not eligible_pairs:
        raise ValueError("ATLAS MVP native pair universe is empty")

    supports: dict[str, dict[Interaction, float]] = {}
    for block in REGISTERED_SEEDS:
        batch = books[block]
        row_index = {str(value): index for index, value in enumerate(batch.player_ids)}
        draws = np.asarray(batch.row_draws, dtype=np.float32)
        if draws.ndim != 2 or draws.shape[1] == 0 or not np.isfinite(draws).all():
            raise ValueError("ATLAS MVP native player worlds are invalid")
        block_support = {
            key: 0.0 for key in eligible_pairs | eligible_triples
        }
        for roster in rosters:
            try:
                rows = [row_index[value] for value in roster]
            except KeyError as exc:
                raise ValueError("ATLAS MVP player universes differ") from exc
            support = float(np.mean(draws[rows].sum(axis=0) >= tail_line))
            pairs, triples = roster_interactions[roster]
            for key in pairs | triples:
                if support > block_support[key]:
                    block_support[key] = support
        supports[block] = block_support

    appearances = {
        key: len(interaction_seeds[key])
        for key in eligible_pairs | eligible_triples
    }
    priced: dict[str, dict[Interaction, float]] = {}
    receipts: dict[str, dict] = {}
    for source in REGISTERED_SEEDS:
        raw: dict[Interaction, float] = {}
        robust: dict[Interaction, float] = {}
        for key in eligible_pairs | eligible_triples:
            values = sorted(
                supports[block][key] for block in REGISTERED_SEEDS
                if block != source
            )
            middle = float((values[1] + values[2]) / 2.0)
            robust[key] = middle
            raw[key] = middle * min(2.0, sqrt(5.0 / appearances[key]))
        pair_total = sum(raw[key] for key in eligible_pairs if raw[key] > 0.0)
        triple_total = sum(raw[key] for key in eligible_triples if raw[key] > 0.0)
        if pair_total <= 0.0:
            raise ValueError("ATLAS MVP positive pair support is empty")
        pair_mass = 1.0 if triple_total <= 0.0 else 0.80
        weights = {
            key: pair_mass * raw[key] / pair_total
            for key in eligible_pairs if raw[key] > 0.0
        }
        if triple_total > 0.0:
            weights.update({
                key: 0.20 * raw[key] / triple_total
                for key in eligible_triples if raw[key] > 0.0
            })
        priced[source] = weights
        receipts[source] = {
            "pricing_excluded_block": source,
            "positive_pairs": sum(key in eligible_pairs for key in weights),
            "positive_triples": sum(key in eligible_triples for key in weights),
            "triple_mass_transferred": triple_total <= 0.0,
            "total_weight": float(sum(weights.values())),
            "conditional_uncovered_weight": float(sum(
                value for key, value in weights.items()
                if key not in nonboom_covered
            )),
        }
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "tail_line": float(tail_line),
        "eligible_pairs": eligible_pairs,
        "eligible_triples": eligible_triples,
        "nonboom_covered": nonboom_covered,
        "supports": supports,
        "appearance_counts": appearances,
        "weights_by_source": priced,
        "receipts": receipts,
    }


def _interaction_value(roster: set[str], weights: Mapping[Interaction, float]) -> float:
    return float(sum(value for key, value in weights.items() if set(key) <= roster))


def enumerate_matched_diversity_lineups(
    *, player_rows: Sequence[Mapping], row_draws: np.ndarray,
    clusters: Mapping, exact_worlds: Mapping[int, Mapping],
    interaction_weights: Mapping[Interaction, float],
    nonboom_lineups: Sequence[Lineup], prior_atlas_rosters: set[frozenset],
    stack: StackRules, env: Mapping[str, str],
) -> tuple[list[Lineup], dict]:
    """Enumerate the frozen round-robin 8x5 near-optimal additions."""
    cluster_worlds = [list(map(int, values)) for values in clusters["clusters"]]
    if len(cluster_worlds) != N_CLUSTERS or any(not values for values in cluster_worlds):
        raise ValueError("ATLAS MVP enumeration requires eight clusters")
    draws = np.asarray(row_draws, dtype=np.float64)
    if draws.ndim != 2 or draws.shape[0] != len(player_rows) or \
            not np.isfinite(draws).all():
        raise ValueError("ATLAS MVP enumeration worlds are misaligned")
    original = [dict(row) for row in player_rows]
    source_index = {str(row["id"]): index for index, row in enumerate(original)}
    if len(source_index) != len(original):
        raise ValueError("ATLAS MVP enumeration player IDs repeat")
    order = sorted(source_index)
    players = [{**original[source_index[player_id]], "id": player_id}
               for player_id in order]
    aligned_draws = draws[[source_index[player_id] for player_id in order]]
    identity_rank = {player_id: index + 1 for index, player_id in enumerate(order)}
    by_id = {str(row["id"]): row for row in players}
    native_nonboom = {_roster(lineup) for lineup in nonboom_lineups}
    banned: set[frozenset] = {
        frozenset(roster) for roster in native_nonboom
    } | {frozenset(str(value) for value in roster) for roster in prior_atlas_rosters}
    weights = {
        tuple(sorted(str(value) for value in key)): float(value)
        for key, value in interaction_weights.items() if float(value) > 0.0
    }
    covered = {
        key for key in weights if any(set(key) <= set(roster) for roster in native_nonboom)
    }
    initially_covered = set(covered)
    states = [{"world_index": 0, "accepted_by_world": Counter(), "exhausted": False}
              for _ in range(N_CLUSTERS)]
    additions: list[Lineup] = []
    proposals: list[dict] = []

    def attempt(cluster_index: int, target_cluster: int, pass_index: int):
        state = states[cluster_index]
        worlds = cluster_worlds[cluster_index]
        while state["world_index"] < len(worlds):
            world = worlds[state["world_index"]]
            exact = exact_worlds[world]
            optimum = float(exact["score"])
            if optimum <= 0.0 or not np.isfinite(optimum):
                raise ValueError("ATLAS MVP world optimum must be positive")
            prior_count = state["accepted_by_world"][world]
            if prior_count == 0:
                roster = tuple(sorted(str(value) for value in exact["roster"]))
                if len(roster) != 9 or frozenset(roster) in banned:
                    proposals.append({
                        "pass": pass_index, "target_cluster": target_cluster,
                        "source_cluster": cluster_index, "world": world,
                        "stage": "exact_optimum", "accepted": False,
                        "reason": "exact_duplicate",
                    })
                    state["world_index"] += 1
                    continue
                lineup = Lineup([by_id[value] for value in roster], tag="atlas")
                world_score = float(sum(
                    aligned_draws[order.index(value), world] for value in roster
                ))
                interaction_value = _interaction_value(set(roster), {
                    key: value for key, value in weights.items() if key not in covered
                })
                receipt = {
                    "stage": "exact_optimum", "optimum": optimum,
                    "score": world_score, "score_floor": optimum,
                    "absolute_regret": optimum - world_score,
                    "percentage_regret": (optimum - world_score) / optimum,
                    "interaction_optimum": interaction_value,
                    "stable_identity_objective": sum(identity_rank[v] for v in roster),
                }
            else:
                score_column = "atlas_world_score"
                identity_column = "atlas_identity_score"
                world_players = [{
                    **row,
                    score_column: float(aligned_draws[index, world]),
                    identity_column: -float(identity_rank[str(row["id"])]),
                } for index, row in enumerate(players)]
                uncovered = {
                    key: value for key, value in weights.items() if key not in covered
                }
                floor = NEAR_OPTIMAL_FRACTION * optimum
                banned_lineups = list(banned)
                stage_two = optimize(
                    world_players, stack=stack,
                    objective_col=score_column,
                    objective_floor_col=score_column, objective_floor=floor,
                    interaction_objective=uncovered,
                    banned_lineups=banned_lineups, max_overlap=8, env=env,
                )
                if stage_two is None:
                    proposals.append({
                        "pass": pass_index, "target_cluster": target_cluster,
                        "source_cluster": cluster_index, "world": world,
                        "stage": "interaction", "accepted": False,
                        "reason": "world_exhausted",
                    })
                    state["world_index"] += 1
                    continue
                interaction_value = _interaction_value(
                    {str(value) for value in stage_two.ids}, uncovered,
                )
                lineup = optimize(
                    world_players, stack=stack,
                    objective_col=identity_column,
                    objective_floor_col=score_column, objective_floor=floor,
                    interaction_floor_weights=uncovered,
                    interaction_floor=interaction_value - INTERACTION_TOLERANCE,
                    banned_lineups=banned_lineups, max_overlap=8, env=env,
                )
                if lineup is None:
                    raise RuntimeError("ATLAS MVP stable interaction solve failed")
                roster = _roster(lineup)
                world_score = float(sum(
                    float(row[score_column]) for row in lineup.players
                ))
                if world_score < floor - 1e-7:
                    raise AssertionError("ATLAS MVP score floor was violated")
                receipt = {
                    "stage": "near_optimal_interaction", "optimum": optimum,
                    "score": world_score, "score_floor": floor,
                    "absolute_regret": optimum - world_score,
                    "percentage_regret": (optimum - world_score) / optimum,
                    "interaction_optimum": interaction_value,
                    "stable_identity_objective": sum(identity_rank[v] for v in roster),
                }
            roster_set = frozenset(_roster(lineup))
            if roster_set in banned:
                raise AssertionError("ATLAS MVP solver returned a banned roster")
            lineup.tag = "atlas"
            banned.add(roster_set)
            additions.append(lineup)
            state["accepted_by_world"][world] += 1
            newly_covered = [
                key for key in weights if key not in covered and set(key) <= set(roster_set)
            ]
            covered.update(newly_covered)
            proposals.append({
                "pass": pass_index, "target_cluster": target_cluster,
                "source_cluster": cluster_index, "world": world,
                "accepted": True, "roster": list(sorted(roster_set)),
                "newly_covered_interactions": len(newly_covered),
                "newly_covered_weight": float(sum(weights[key] for key in newly_covered)),
                **receipt,
            })
            return lineup
        state["exhausted"] = True
        return None

    for pass_index in range(LINEUPS_PER_CLUSTER):
        for target in range(N_CLUSTERS):
            accepted = None
            for offset in range(N_CLUSTERS):
                source = (target + offset) % N_CLUSTERS
                accepted = attempt(source, target, pass_index)
                if accepted is not None:
                    break
            if accepted is None:
                raise RuntimeError("ATLAS MVP clusters cannot supply exact 8x5 count")
    if len(additions) != N_ATLAS_LINEUPS or len({_roster(row) for row in additions}) != N_ATLAS_LINEUPS:
        raise RuntimeError("ATLAS MVP did not produce 40 unique additions")
    return additions, {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "candidate_count": len(additions),
        "proposals": proposals,
        "cluster_states": [{
            "cluster": index,
            "exhausted": state["exhausted"],
            "accepted_by_world": dict(sorted(state["accepted_by_world"].items())),
        } for index, state in enumerate(states)],
        "conditional_weight_covered": float(sum(
            weights[key] for key in covered if key not in initially_covered
        )),
        "conditional_weight_total": float(sum(
            weights[key] for key in weights if key not in initially_covered
        )),
    }


def replace_native_boom_book(
    native: CandidateBatch, additions: Sequence[Lineup],
) -> CandidateBatch:
    """Replace exact 40 native boom rows at fixed budget on native worlds."""
    boom = [lineup for lineup in native.candidates if str(lineup.tag) == "boom"]
    nonboom = [lineup for lineup in native.candidates if str(lineup.tag) != "boom"]
    if len(boom) != N_ATLAS_LINEUPS or len(additions) != N_ATLAS_LINEUPS:
        raise ValueError("ATLAS MVP replacement requires exact 40-for-40")
    candidates = [*nonboom, *additions]
    rosters = [_roster(lineup) for lineup in candidates]
    if len(rosters) != len(set(rosters)) or len(candidates) != len(native.candidates):
        raise ValueError("ATLAS MVP replacement count/identity differs")
    row_index = {str(value): index for index, value in enumerate(native.player_ids)}
    draws = np.asarray(native.row_draws, dtype=np.float32)
    totals = np.stack([
        draws[[row_index[value] for value in roster]].sum(axis=0)
        for roster in rosters
    ]).astype(np.float32)
    all_tags = {
        lineup.ids: (
            native.all_tags.get(lineup.ids, (lineup.tag or "lev",))
            if str(lineup.tag) != "atlas" else ("atlas",)
        )
        for lineup in candidates
    }
    return CandidateBatch(
        candidates=tuple(candidates), candidate_totals=totals,
        player_ids=native.player_ids, player_rows=native.player_rows,
        row_draws=native.row_draws, all_tags=all_tags,
        metadata={
            **native.metadata,
            "candidate_generator": VERSION,
            "native_boom_replaced": len(boom),
            "atlas_additions": len(additions),
            "uses_realized_outcomes": False,
        },
    )
