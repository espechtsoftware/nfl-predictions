import numpy as np

from nfl_dfs.analysis.atlas_matched_diversity import (
    REGISTERED_SEEDS,
    aggregate_mvp_gate,
    build_structural_clusters,
    price_native_interactions,
)
from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.optimizer.lineup import Lineup


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
