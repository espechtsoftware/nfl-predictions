import numpy as np

from nfl_dfs.analysis.atlas_matched_diversity import (
    REGISTERED_SEEDS,
    aggregate_mvp_gate,
    build_structural_clusters,
    enumerate_matched_diversity_lineups,
    price_native_interactions,
)
from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.optimizer.lineup import Lineup, StackRules, optimize_many


def _cluster_exact_worlds():
    rows = {}
    for world in range(40):
        variant = world % 10
        roster = [f"p{index}" for index in range(8)] + [f"v{variant}"]
        rows[world] = {
            "score": 250.0 - world / 10.0,
            "roster": roster,
            "qb_stack_core": ["p0", f"v{variant}"],
            "dominant_game": f"g{variant % 4}",
        }
    return rows


def test_structural_clusters_are_deterministic_and_complete():
    exact = _cluster_exact_worlds()
    left = build_structural_clusters(list(range(40)), exact)
    right = build_structural_clusters(
        list(range(40)), dict(reversed(list(exact.items()))),
    )
    assert left == right
    assert len(left["anchors"]) == 8
    memberships = [world for cluster in left["clusters"] for world in cluster]
    assert sorted(memberships) == list(range(40))
    assert len(set(anchor["world"] for anchor in left["anchors"])) == 8
    assert len(set(tuple(anchor["roster"]) for anchor in left["anchors"])) == 8


def _players():
    specs = [
        ("q", "QB", "A"), ("r1", "RB", "A"), ("r2", "RB", "B"),
        ("r3", "RB", "C"), ("w1", "WR", "A"), ("w2", "WR", "A"),
        ("w3", "WR", "B"), ("w4", "WR", "C"), ("t", "TE", "A"),
        ("d", "DST", "D"),
    ]
    return [{
        "id": player_id, "name": player_id, "pos": pos, "team": team,
        "opp": ("Z" if pos == "DST" else "B" if team == "A" else "A"),
        "game_id": "g1" if team in {"A", "B"} else "g2",
        "salary": 5_500, "proj": 10.0,
    } for player_id, pos, team in specs]


def _books(reverse=False):
    players = _players()
    rosters = [
        ("q", "r1", "r2", "w1", "w2", "w3", "w4", "t", "d"),
        ("q", "r1", "r3", "w1", "w2", "w3", "w4", "t", "d"),
    ]
    result = {}
    for seed_index, seed in enumerate(REGISTERED_SEEDS):
        ordered = list(reversed(players)) if reverse else list(players)
        draws = np.full((len(ordered), 8), 20.0 + seed_index, dtype=np.float32)
        by_id = {row["id"]: row for row in ordered}
        lineups = [
            Lineup([by_id[value] for value in roster], tag=tag)
            for roster, tag in zip(rosters, ("lev", "boom"), strict=True)
        ]
        if reverse:
            lineups.reverse()
        totals = np.stack([
            draws[[next(index for index, row in enumerate(ordered)
                         if row["id"] == value) for value in lineup.ids]].sum(axis=0)
            for lineup in lineups
        ])
        result[seed] = CandidateBatch(
            candidates=tuple(lineups), candidate_totals=totals,
            player_ids=tuple(row["id"] for row in ordered),
            player_rows=tuple(ordered), row_draws=draws,
            all_tags={lineup.ids: (lineup.tag,) for lineup in lineups},
        )
    return result


def test_interaction_pricing_is_leave_one_seed_out_and_permutation_stable():
    left = price_native_interactions(_books())
    right = price_native_interactions(_books(reverse=True))
    assert left["eligible_pairs"] == right["eligible_pairs"]
    assert left["eligible_triples"] == right["eligible_triples"]
    assert left["nonboom_covered"] == right["nonboom_covered"]
    assert left["appearance_counts"] == right["appearance_counts"]
    assert left["weights_by_source"] == right["weights_by_source"]
    for seed in REGISTERED_SEEDS:
        assert abs(sum(left["weights_by_source"][seed].values()) - 1.0) < 1e-12
        assert left["receipts"][seed]["pricing_excluded_block"] == seed
        assert left["receipts"][seed]["positive_pairs"] > 0
        assert left["receipts"][seed]["positive_triples"] > 0


def _gate_rows(p2_pool_210=0.30, p2_unique_pairs=110):
    rows = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            def book(p194, p210, p230):
                aggregate = {"194": p194, "210": p210, "230": p230}
                by_block = {
                    seed: dict(aggregate) for seed in REGISTERED_SEEDS
                }
                return {
                    "candidate_pool_tail": {
                        "aggregate": dict(aggregate), "by_block": by_block,
                    },
                    "exact80_tail": {
                        "aggregate": dict(aggregate), "by_block": by_block,
                    },
                    "candidate_structure": {"unique_pairs": 100},
                }
            interactions = {
                "P1": [{
                    "pair_weight_covered": 0.20,
                    "triple_weight_covered": 0.10,
                    "triple_weight_total": 0.20,
                } for _ in REGISTERED_SEEDS],
                "P2": [{
                    "pair_weight_covered": 0.25,
                    "triple_weight_covered": 0.095,
                    "triple_weight_total": 0.20,
                } for _ in REGISTERED_SEEDS],
            }
            rows.append({
                "season": season, "week": week,
                "uses_realized_outcomes": False, "mechanical_valid": True,
                "P1": book(0.50, 0.25, 0.10),
                "P2": book(0.48, p2_pool_210, 0.096),
                "interaction_coverage": interactions,
            })
            rows[-1]["P2"]["candidate_structure"]["unique_pairs"] = (
                p2_unique_pairs
            )
    return rows


def test_aggregate_gate_applies_all_frozen_conditions():
    passed = aggregate_mvp_gate(_gate_rows())
    assert passed["passes_scorefree_gate"] is True
    assert passed["disposition"] == "licensed-2026-prelock-shadow"
    failed = aggregate_mvp_gate(_gate_rows(p2_pool_210=0.24))
    assert failed["passes_scorefree_gate"] is False
    assert failed["conditions"][
        "candidate_pool_p210_strictly_higher_aggregate"
    ] is False
    failed_reach = aggregate_mvp_gate(_gate_rows(p2_unique_pairs=99))
    assert failed_reach["passes_scorefree_gate"] is False
    assert failed_reach["conditions"][
        "candidate_pair_reach_retains_100pct"
    ] is False


def _enumeration_pool():
    players = []
    for team_index in range(6):
        team = f"T{team_index}"
        opponent = f"T{team_index + 1 if team_index % 2 == 0 else team_index - 1}"
        game = f"G{team_index // 2}"
        for position, count in (("QB", 1), ("RB", 3), ("WR", 4),
                                ("TE", 2), ("DST", 1)):
            for index in range(count):
                player_id = f"{team}-{position}-{index}"
                players.append({
                    "id": player_id, "name": player_id, "pos": position,
                    "team": team, "opp": opponent, "game_id": game,
                    "salary": 5_500, "proj": 20.0,
                })
    return players


def test_full_8x5_enumeration_is_deterministic_and_receipt_complete():
    players = _enumeration_pool()
    stack = StackRules(qb_stack_min=2, bring_back_min=1)
    exact_lineups = optimize_many(
        players, n_lineups=8, max_overlap=8, stack=stack,
        punt_max_salary=None, punt_min=0, env={"MIN_LINEUP_SALARY": "49000"},
    )
    assert len(exact_lineups) == 8
    draws = np.full((len(players), 8), 20.0, dtype=np.float32)
    exact = {
        world: {
            "score": 180.0, "canonical_roster_score": 180.0,
            "identity_tolerance": 1e-6,
            "identity_rank_sum": sum(
                sorted(str(row["id"]) for row in players).index(str(player_id)) + 1
                for player_id in lineup.ids
            ),
            "roster": sorted(str(value) for value in lineup.ids),
        }
        for world, lineup in enumerate(exact_lineups)
    }
    clusters = {"clusters": [[world] for world in range(8)]}
    first_roster = frozenset(str(value) for value in exact_lineups[0].ids)
    first_ids = sorted(first_roster)
    weights = {
        tuple(first_ids[:2]): 0.8,
        tuple(first_ids[:3]): 0.2,
    }

    def run_once():
        return enumerate_matched_diversity_lineups(
            player_rows=players, row_draws=draws,
            clusters=clusters, exact_worlds=exact,
            interaction_weights=weights, nonboom_lineups=[],
            prior_atlas_rosters={first_roster}, stack=stack,
            env={"MIN_LINEUP_SALARY": "49000"},
        )

    left_additions, left = run_once()
    right_additions, right = run_once()
    assert [sorted(lineup.ids) for lineup in left_additions] == [
        sorted(lineup.ids) for lineup in right_additions
    ]
    assert left == right
    assert len(left_additions) == 40
    assert len({lineup.ids for lineup in left_additions}) == 40
    assert any(
        not row["accepted"] and row["reason"] == "exact_duplicate"
        for row in left["proposals"]
    )
    required = {
        "optimum", "score", "score_floor", "absolute_regret",
        "percentage_regret", "interaction_optimum",
        "stable_identity_objective",
    }
    for row in left["proposals"]:
        assert required <= set(row)
        if row["accepted"]:
            assert {
                "newly_covered_pairs", "newly_covered_pair_weight",
                "newly_covered_triples", "newly_covered_triple_weight",
            } <= set(row)
            assert abs(
                row["newly_covered_weight"]
                - row["newly_covered_pair_weight"]
                - row["newly_covered_triple_weight"]
            ) < 1e-12
