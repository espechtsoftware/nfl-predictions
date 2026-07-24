import networkx as nx
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import archetypes
from nfl_dfs.graph.cascade import project_vacated_usage


def synthetic_games(seed=7):
    """Three planted WR profiles (plus QBs): elite-stable, elite-volatile
    around the same mean, and low-output."""
    rng = np.random.default_rng(seed)
    rows = []

    def add(gsis_id, pos, mean, sd, n=30):
        for _ in range(n):
            rows.append({
                "gsis_id": gsis_id, "position": pos,
                "dk_points": max(0.0, rng.normal(mean, sd)),
                "name": f"P {gsis_id}",
            })

    for i in range(8):
        add(f"stable-{i}", "WR", 20, 4)
        add(f"volatile-{i}", "WR", 20, 12)
        add(f"low-{i}", "WR", 6, 3)
        add(f"qb-{i}", "QB", 19, 6)
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def clustered():
    prof = archetypes.consistency_profiles(synthetic_games(), min_games=16)
    return archetypes.cluster_archetypes(prof, n_clusters=3, seed=0)


def test_profiles_metrics(clustered):
    stable = clustered[clustered.gsis_id == "stable-0"].iloc[0]
    volatile = clustered[clustered.gsis_id == "volatile-0"].iloc[0]
    assert stable.cv < volatile.cv
    assert stable.pct_10_plus > 0.9
    assert clustered[clustered.gsis_id == "low-0"].iloc[0].pct_20_plus < 0.1


def test_min_games_filter():
    games = synthetic_games()
    few = games[games.gsis_id != "stable-0"]
    few = pd.concat([few, games[games.gsis_id == "stable-0"].head(5)])
    prof = archetypes.consistency_profiles(few, min_games=16)
    assert "stable-0" not in prof.gsis_id.values


def test_clusters_separate_planted_profiles(clustered):
    wr = clustered[clustered.position == "WR"]
    by_kind = {
        kind: set(wr[wr.gsis_id.str.startswith(kind)].cluster.unique())
        for kind in ("stable", "volatile", "low")
    }
    # Each planted profile lands in one cluster, and no two profiles share one
    assert all(len(c) == 1 for c in by_kind.values()), by_kind
    assert len(set.union(*by_kind.values())) == 3


def test_archetype_labels_are_position_scoped(clustered):
    assert clustered[clustered.position == "WR"].archetype.str.startswith("WR-").all()
    assert clustered[clustered.position == "QB"].archetype.str.startswith("QB-").all()
    # Same mean, different variance: stable gets the -stable suffix
    stable_lab = clustered[clustered.gsis_id == "stable-0"].archetype.iloc[0]
    volatile_lab = clustered[clustered.gsis_id == "volatile-0"].archetype.iloc[0]
    assert stable_lab.endswith("-stable")
    assert volatile_lab.endswith("-volatile")


def _graph_with(clustered):
    G = nx.MultiDiGraph()
    for r in clustered.itertuples():
        G.add_node(r.gsis_id, kind="Player", position=r.position)
    return G


def test_annotate_and_similarity_edges(clustered):
    G = _graph_with(clustered)
    assert archetypes.annotate_graph(G, clustered) == len(clustered)
    assert G.nodes["stable-0"]["archetype"].endswith("-stable")

    archetypes.add_similarity_edges(G, clustered, k=3)
    sims = archetypes.similar_players(G, "stable-0")
    assert 0 < len(sims) <= 3
    # Neighbors share the cluster: all planted stables
    assert all(nbr.startswith("stable-") for nbr, _ in sims)
    # Sorted nearest-first
    dists = [d for _, d in sims]
    assert dists == sorted(dists)


def test_cascade_uses_archetype_boost(clustered):
    G = _graph_with(clustered)
    for a, b in [("stable-0", "stable-1"), ("stable-0", "volatile-0"),
                 ("stable-1", "volatile-0")]:
        G.add_edge(a, b, key="COMPETES_WITH")
        G.add_edge(b, a, key="COMPETES_WITH")
    usage = pd.DataFrame({
        "gsis_id": ["stable-0", "stable-1", "volatile-0"] * 4,
        "season": [2025] * 12,
        "week": np.repeat(range(1, 5), 3),
        "total_targets": 8.0, "rz20_targets": 1.0,
        "target_share": [0.25, 0.20, 0.20] * 4,
    })
    injuries = pd.DataFrame({"gsis_id": ["stable-0"], "season": [2025],
                             "week": [5], "game_status": ["Out"]})

    plain = project_vacated_usage(G, usage, injuries, "stable-0")
    assert (plain.method == "depth_chart").all()
    # Equal current usage -> equal split without archetypes
    d = plain.set_index("gsis_id").delta
    assert d["stable-1"] == pytest.approx(d["volatile-0"])

    archetypes.annotate_graph(G, clustered)
    boosted = project_vacated_usage(G, usage, injuries, "stable-0")
    assert (boosted.method == "depth_chart_archetype").all()
    b = boosted.set_index("gsis_id").delta
    assert b["stable-1"] > b["volatile-0"]
    # Total vacated share is conserved, just re-weighted
    assert b.sum() == pytest.approx(d.sum())
