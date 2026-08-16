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
from ..optimizer.lineup import Lineup, StackRules, optimize, select_tail_entries


VERSION = "atlas-matched-diversity-mvp-v1"
REGISTERED_SEEDS = ("R0", "R1", "R2", "R3", "R4")
REGISTERED_TAGS = {"lev", "epi", "game", "dark", "qbvar", "boom"}
TAIL_LINE = 194.0
N_CLUSTERS = 8
LINEUPS_PER_CLUSTER = 5
N_ATLAS_LINEUPS = N_CLUSTERS * LINEUPS_PER_CLUSTER
NEAR_OPTIMAL_FRACTION = 0.98
INTERACTION_TOLERANCE = 1e-9
TAIL_GRID = (187.0, 194.0, 200.0, 210.0, 220.0, 230.0, 240.0)

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


def _validate_legal_lineup(lineup: Lineup) -> None:
    players = list(lineup.players)
    positions = Counter(str(row.get("pos", "")).upper() for row in players)
    legal_shape = (
        len(players) == 9 and len(lineup.ids) == 9
        and positions["QB"] == 1 and positions["DST"] == 1
        and 2 <= positions["RB"] <= 3
        and 3 <= positions["WR"] <= 4
        and 1 <= positions["TE"] <= 2
    )
    salary = sum(int(round(float(row.get("salary", 0)))) for row in players)
    games = {str(row.get("game_id")) for row in players if row.get("game_id")}
    teams = Counter(str(row.get("team", "")) for row in players)
    if not legal_shape or not 49_000 <= salary <= 50_000 or len(games) < 2 or \
            max(teams.values(), default=0) > 8:
        raise ValueError("ATLAS MVP native lineup is not DK Classic legal")
    qb = next(row for row in players if str(row.get("pos", "")).upper() == "QB")
    catchers = sum(
        str(row.get("team", "")) == str(qb.get("team", ""))
        and str(row.get("pos", "")).upper() in {"WR", "TE"}
        for row in players
    )
    bring_backs = sum(
        str(row.get("team", "")) == str(qb.get("opp", ""))
        and str(row.get("pos", "")).upper() in {"RB", "WR", "TE"}
        for row in players
    )
    rb_teams = [
        str(row.get("team", "")) for row in players
        if str(row.get("pos", "")).upper() == "RB"
    ]
    dst = next(
        row for row in players if str(row.get("pos", "")).upper() == "DST"
    )
    if catchers < 2 or bring_backs < 1 or len(rb_teams) != len(set(rb_teams)) or \
            any(str(row.get("pos", "")).upper() == "RB" and
                str(row.get("team", "")) == str(dst.get("opp", ""))
                for row in players):
        raise ValueError("ATLAS MVP native lineup stack constraints differ")


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
        metadata = {
            str(player_id): (
                str(row.get("pos", "")).upper(), str(row.get("team", "")),
                str(row.get("opp", "")), str(row.get("game_id", "")),
                int(round(float(row.get("salary", 0)))),
            )
            for player_id, row in zip(
                batch.player_ids, batch.player_rows, strict=True,
            )
        }
        expected_metadata = {
            player_id: (
                str(row.get("pos", "")).upper(), str(row.get("team", "")),
                str(row.get("opp", "")), str(row.get("game_id", "")),
                int(round(float(row.get("salary", 0)))),
            ) for player_id, row in player_by_id.items()
        }
        if metadata != expected_metadata:
            raise ValueError("ATLAS MVP native player metadata differs")
        for lineup in batch.candidates:
            if str(lineup.tag) not in REGISTERED_TAGS:
                raise ValueError("ATLAS MVP native tag is not registered")
            _validate_legal_lineup(lineup)
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
        pair_total = sum(
            raw[key] for key in sorted(eligible_pairs) if raw[key] > 0.0
        )
        triple_total = sum(
            raw[key] for key in sorted(eligible_triples) if raw[key] > 0.0
        )
        if pair_total <= 0.0:
            raise ValueError("ATLAS MVP positive pair support is empty")
        pair_mass = 1.0 if triple_total <= 0.0 else 0.80
        weights = {
            key: pair_mass * raw[key] / pair_total
            for key in sorted(eligible_pairs) if raw[key] > 0.0
        }
        if triple_total > 0.0:
            weights.update({
                key: 0.20 * raw[key] / triple_total
                for key in sorted(eligible_triples) if raw[key] > 0.0
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
    weights = dict(sorted((
        (tuple(sorted(str(value) for value in key)), float(value))
        for key, value in interaction_weights.items() if float(value) > 0.0
    )))
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
                banned_lineups = [
                    frozenset(roster) for roster in sorted(
                        (tuple(sorted(value)) for value in banned),
                    )
                ]
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
    for lineup in additions:
        if str(lineup.tag) != "atlas":
            raise ValueError("ATLAS MVP addition tag differs")
        _validate_legal_lineup(lineup)
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


def _book_structure(lineups: Sequence[Lineup]) -> dict:
    if not lineups:
        raise ValueError("ATLAS MVP cannot summarize an empty book")
    rosters = [_roster(lineup) for lineup in lineups]
    if len(rosters) != len(set(rosters)):
        raise ValueError("ATLAS MVP summary book repeats rosters")
    player_counts = Counter(value for roster in rosters for value in roster)
    total_slots = float(sum(player_counts.values()))
    proportions = np.asarray(
        [value / total_slots for value in player_counts.values()], dtype=float,
    )
    pairs = set().union(*(set(combinations(roster, 2)) for roster in rosters))
    cores: set[Interaction] = set()
    game_signatures = set()
    overlaps = []
    for index, lineup in enumerate(lineups):
        player_by_id = {str(row["id"]): row for row in lineup.players}
        cores.update(_lineup_interactions(rosters[index], player_by_id)[1])
        counts = Counter(
            str(row.get("game_id")) for row in lineup.players if row.get("game_id")
        )
        maximum = max(counts.values(), default=0)
        game_signatures.add(tuple(sorted(
            game for game, count in counts.items() if count == maximum
        )))
        left = set(rosters[index])
        overlaps.extend(
            len(left & set(rosters[other]))
            for other in range(index + 1, len(rosters))
        )
    entropy = float(-np.sum(proportions * np.log(proportions)))
    top_players = sorted(
        player_counts,
        key=lambda value: (-player_counts[value], value),
    )[:20]
    return {
        "lineups": len(lineups),
        "unique_players": len(player_counts),
        "unique_pairs": len(pairs),
        "unique_stack_cores": len(cores),
        "unique_maximum_game_signatures": len(game_signatures),
        "maximum_game_signatures": [list(value) for value in sorted(game_signatures)],
        "player_entropy_effective_count": float(np.exp(entropy)),
        "player_simpson_effective_count": float(1.0 / np.sum(proportions ** 2)),
        "mean_pairwise_roster_overlap": float(np.mean(overlaps)) if overlaps else 0.0,
        "top_20_players": top_players,
        "player_frequencies": dict(sorted(player_counts.items())),
    }


def _score_effective_rank(matrix: np.ndarray) -> dict:
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] < 2:
        raise ValueError("ATLAS MVP effective-rank matrix is invalid")
    covariance = np.cov(values, rowvar=True, ddof=1)

    def spectrum(source: np.ndarray) -> dict:
        eigenvalues = np.maximum(np.linalg.eigvalsh(source), 0.0)
        total = float(eigenvalues.sum())
        if total <= 0.0:
            raise ValueError("ATLAS MVP effective-rank spectrum is degenerate")
        shares = eigenvalues / total
        positive = shares[shares > 0.0]
        return {
            "participation_ratio": float(1.0 / np.square(shares).sum()),
            "entropy_effective_rank": float(np.exp(
                -np.sum(positive * np.log(positive))
            )),
            "top_five_variance_share": float(np.sort(shares)[-5:].sum()),
        }

    variances = np.diag(covariance)
    if np.any(variances <= 0.0):
        raise ValueError("ATLAS MVP correlation rank has zero variance")
    scale = np.sqrt(variances)
    correlation = covariance / np.outer(scale, scale)
    np.fill_diagonal(correlation, 1.0)
    return {
        "covariance": spectrum(covariance),
        "correlation": spectrum(correlation),
    }


def summarize_candidate_and_exact80(
    batch: CandidateBatch, *, lines: Sequence[float] = TAIL_GRID,
    n_entries: int = 80,
) -> dict:
    """Summarize score-free pool and unchanged exact-80 support."""
    totals = np.asarray(batch.candidate_totals, dtype=np.float32)
    if totals.ndim != 2 or totals.shape[0] != len(batch.candidates) or \
            totals.shape[1] == 0 or not np.isfinite(totals).all():
        raise ValueError("ATLAS MVP summary candidate worlds are invalid")
    if totals.shape[1] % len(REGISTERED_SEEDS):
        raise ValueError("ATLAS MVP summary world blocks differ")
    picked = select_tail_entries(
        totals, n_entries, TAIL_LINE, env={"SELECT_LSE": "0"},
    )
    if len(picked) != n_entries or len(set(picked)) != n_entries:
        raise ValueError("ATLAS MVP exact-80 selector did not return 80")
    block_worlds = totals.shape[1] // len(REGISTERED_SEEDS)

    def tail_metrics(use: np.ndarray) -> dict:
        aggregate = {}
        by_block = {seed: {} for seed in REGISTERED_SEEDS}
        for raw_line in lines:
            line = float(raw_line)
            key = f"{line:g}"
            aggregate[key] = float(np.mean(np.any(use >= line, axis=0)))
            for block_index, seed in enumerate(REGISTERED_SEEDS):
                block = use[:, block_index * block_worlds:(block_index + 1) * block_worlds]
                by_block[seed][key] = float(np.mean(np.any(block >= line, axis=0)))
        return {"aggregate": aggregate, "by_block": by_block}

    selected = [batch.candidates[index] for index in picked]
    candidate_structure = _book_structure(batch.candidates)
    exact80_structure = _book_structure(selected)
    candidate_structure["score_effective_rank"] = _score_effective_rank(totals)
    exact80_structure["score_effective_rank"] = _score_effective_rank(totals[picked])
    return {
        "candidate_budget": len(batch.candidates),
        "worlds": int(totals.shape[1]),
        "candidate_pool_tail": tail_metrics(totals),
        "exact80_tail": tail_metrics(totals[picked]),
        "candidate_structure": candidate_structure,
        "exact80_structure": exact80_structure,
        "exact80_indices": picked,
        "exact80_identities": [list(_roster(lineup)) for lineup in selected],
    }


def conditional_interaction_coverage(
    lineups: Sequence[Lineup], pricing: Mapping, source_seed: str,
) -> dict:
    """Measure fixed pair/core weight beyond the complete non-boom union."""
    weights = pricing["weights_by_source"][source_seed]
    baseline = pricing["nonboom_covered"]
    represented: set[Interaction] = set()
    for lineup in lineups:
        roster = _roster(lineup)
        player_by_id = {str(row["id"]): row for row in lineup.players}
        pairs, triples = _lineup_interactions(roster, player_by_id)
        represented.update(pairs)
        represented.update(triples)
    eligible = {
        key: value for key, value in weights.items() if key not in baseline
    }
    pair_total = float(sum(value for key, value in eligible.items() if len(key) == 2))
    triple_total = float(sum(value for key, value in eligible.items() if len(key) == 3))
    return {
        "source_seed": source_seed,
        "pricing_excluded_block": source_seed,
        "pair_weight_total": pair_total,
        "pair_weight_covered": float(sum(
            value for key, value in eligible.items()
            if len(key) == 2 and key in represented
        )),
        "triple_weight_total": triple_total,
        "triple_weight_covered": float(sum(
            value for key, value in eligible.items()
            if len(key) == 3 and key in represented
        )),
        "conditional_pairs_represented": sum(
            len(key) == 2 and key in represented for key in eligible
        ),
        "conditional_triples_represented": sum(
            len(key) == 3 and key in represented for key in eligible
        ),
    }


def aggregate_mvp_gate(rows: Sequence[Mapping]) -> dict:
    """Apply the preregistered score-free P2-versus-P1 disposition."""
    if len(rows) != 54:
        raise ValueError("ATLAS MVP aggregate requires 54 slates")
    expected_slates = {
        (season, week) for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    keys = {(int(row["season"]), int(row["week"])) for row in rows}
    if keys != expected_slates or any(
        row.get("uses_realized_outcomes") is not False or
        row.get("mechanical_valid") is not True for row in rows
    ):
        raise ValueError("ATLAS MVP slate population/mechanics differ")

    def mean_tail(book: str, tier: str, line: str, block: str | None = None):
        values = []
        for row in rows:
            tail = row[book][tier]
            values.append(float(
                tail["aggregate"][line] if block is None
                else tail["by_block"][block][line]
            ))
        return float(np.mean(values))

    def interaction(book: str, field: str):
        return float(np.mean([
            source[field]
            for row in rows for source in row["interaction_coverage"][book]
        ]))

    p1_pair = interaction("P1", "pair_weight_covered")
    p2_pair = interaction("P2", "pair_weight_covered")
    p1_triple = interaction("P1", "triple_weight_covered")
    p2_triple = interaction("P2", "triple_weight_covered")
    p1_pair_reach = float(np.mean([
        float(row["P1"]["candidate_structure"]["unique_pairs"])
        for row in rows
    ]))
    p2_pair_reach = float(np.mean([
        float(row["P2"]["candidate_structure"]["unique_pairs"])
        for row in rows
    ]))
    p1_pool_210 = mean_tail("P1", "candidate_pool_tail", "210")
    p2_pool_210 = mean_tail("P2", "candidate_pool_tail", "210")
    block_210 = {
        seed: {
            "P1": mean_tail("P1", "candidate_pool_tail", "210", seed),
            "P2": mean_tail("P2", "candidate_pool_tail", "210", seed),
        }
        for seed in REGISTERED_SEEDS
    }
    p1_pool_230 = mean_tail("P1", "candidate_pool_tail", "230")
    p2_pool_230 = mean_tail("P2", "candidate_pool_tail", "230")
    exact = {
        line: {
            "P1": mean_tail("P1", "exact80_tail", line),
            "P2": mean_tail("P2", "exact80_tail", line),
        } for line in ("194", "210", "230")
    }

    def preservation(treatment: float, control: float) -> float:
        if control == 0.0:
            return 1.0 if treatment >= 0.0 else float("-inf")
        return treatment / control

    triple_validly_empty = all(
        float(source["triple_weight_total"]) == 0.0
        for row in rows for source in row["interaction_coverage"]["P1"]
    )
    conditions = {
        "conditional_pair_weight_strictly_higher": p2_pair > p1_pair,
        "candidate_pair_reach_retains_100pct": p2_pair_reach >= p1_pair_reach,
        "conditional_stack_core_retains_90pct": (
            triple_validly_empty or preservation(p2_triple, p1_triple) >= 0.90
        ),
        "candidate_pool_p210_strictly_higher_aggregate": p2_pool_210 > p1_pool_210,
        "candidate_pool_p210_higher_at_least_three_blocks": sum(
            values["P2"] > values["P1"] for values in block_210.values()
        ) >= 3,
        "candidate_pool_p230_retains_95pct": preservation(
            p2_pool_230, p1_pool_230,
        ) >= 0.95,
        "exact80_p194_retains_90pct": preservation(
            exact["194"]["P2"], exact["194"]["P1"],
        ) >= 0.90,
        "exact80_p230_retains_90pct": preservation(
            exact["230"]["P2"], exact["230"]["P1"],
        ) >= 0.90,
    }
    return {
        "version": VERSION,
        "uses_realized_outcomes": False,
        "mechanical_valid": True,
        "slates": len(rows),
        "conditional_interactions": {
            "P1_pair_weight_covered": p1_pair,
            "P2_pair_weight_covered": p2_pair,
            "P1_triple_weight_covered": p1_triple,
            "P2_triple_weight_covered": p2_triple,
            "triple_class_validly_empty": triple_validly_empty,
        },
        "candidate_pair_reach": {
            "P1_mean_unique_pairs": p1_pair_reach,
            "P2_mean_unique_pairs": p2_pair_reach,
            "P2_over_P1": preservation(p2_pair_reach, p1_pair_reach),
        },
        "candidate_pool": {
            "p210": {"P1": p1_pool_210, "P2": p2_pool_210},
            "p210_by_pricing_excluded_block": block_210,
            "p230": {"P1": p1_pool_230, "P2": p2_pool_230},
        },
        "exact80": exact,
        "conditions": conditions,
        "passes_scorefree_gate": all(conditions.values()),
        "disposition": (
            "licensed-2026-prelock-shadow"
            if all(conditions.values()) else "mvp-v1-closed"
        ),
    }
