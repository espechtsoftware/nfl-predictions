"""Player/team knowledge graph (guide §8).

Honest framing: this does not improve point projections — GBDTs on tabular
features own that job. The graph earns its keep on entity resolution,
cascade reasoning (who inherits an injured player's usage), relational
features, and explanation. At NFL scale (~2,000 players, 32 teams) it fits
in memory; NetworkX in a job is sufficient, no graph database needed.

Node kinds: Player, Team. Edge keys: PLAYS_FOR, TARGETED_BY (QB->receiver,
weighted by red zone volume), COMPETES_WITH (same team + position group).
COMPETES_WITH and REPLACED are the edges that pay: target share is
zero-sum within a team, which is natural as a graph property and awkward
as a column.
"""

from __future__ import annotations

import logging

import networkx as nx
import pandas as pd

log = logging.getLogger(__name__)


def build_graph(
    rosters: pd.DataFrame,
    qb_connections: pd.DataFrame,
    news_edges: pd.DataFrame | None = None,
) -> nx.MultiDiGraph:
    """Assemble the graph from prepared frames.

    rosters:        gsis_id, name, position, team   (one row per player)
    qb_connections: qb, wr, team, targets, rz_targets, air_yards, tds
    news_edges:     optional output of news.to_graph_edges
    """
    G = nx.MultiDiGraph()

    for r in rosters.itertuples():
        G.add_node(r.gsis_id, kind="Player", name=r.name, position=r.position)
        G.add_node(r.team, kind="Team")
        G.add_edge(r.gsis_id, r.team, key="PLAYS_FOR")

    for r in qb_connections.itertuples():
        G.add_edge(r.qb, r.wr, key="TARGETED_BY",
                   targets=r.targets, rz_targets=r.rz_targets,
                   air_yards=r.air_yards, tds=r.tds)

    # Intra-team, intra-position competition edges (undirected in spirit;
    # stored both ways for cheap traversal)
    for (_team, _pos), grp in rosters.groupby(["team", "position"]):
        ids = list(grp.gsis_id)
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                G.add_edge(a, b, key="COMPETES_WITH")
                G.add_edge(b, a, key="COMPETES_WITH")

    if news_edges is not None:
        for r in news_edges.itertuples():
            G.add_edge(r.gsis_id, r.team, key="NEWS_SIGNAL",
                       claim_type=r.claim_type, direction=r.direction,
                       confidence=r.confidence, published_at=r.published_at)

    log.info("Graph: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())
    return G


def build_graph_from_warehouse(season: int, through_week: int) -> nx.MultiDiGraph:
    """Production path: pull the frames from BigQuery, then assemble."""
    from ..bq import query_df
    from ..config import settings

    rosters = query_df(
        f"""
        SELECT gsis_id, ANY_VALUE(full_name HAVING MAX week) AS name,
               ANY_VALUE(position HAVING MAX week) AS position,
               ANY_VALUE(team HAVING MAX week) AS team
        FROM `{settings.raw}.rosters_weekly`
        WHERE season = {season} AND week <= {through_week} AND gsis_id IS NOT NULL
        GROUP BY gsis_id
        """
    )
    qb_connections = query_df(
        f"""
        SELECT passer_player_id AS qb, receiver_player_id AS wr, posteam AS team,
               COUNT(*) AS targets,
               COUNTIF(yardline_100 <= 20) AS rz_targets,
               SUM(air_yards) AS air_yards,
               COUNTIF(pass_touchdown = 1) AS tds
        FROM `{settings.raw}.pbp`
        WHERE season = {season} AND week <= {through_week}
          AND pass_attempt = 1 AND receiver_player_id IS NOT NULL
        GROUP BY 1, 2, 3
        """
    )
    return build_graph(rosters, qb_connections)


def teammates(G: nx.MultiDiGraph, gsis_id: str) -> list[str]:
    return [b for _, b, k in G.out_edges(gsis_id, keys=True) if k == "COMPETES_WITH"]


def team_of(G: nx.MultiDiGraph, gsis_id: str) -> str | None:
    for _, t, k in G.out_edges(gsis_id, keys=True):
        if k == "PLAYS_FOR":
            return t
    return None


def qb_of(G: nx.MultiDiGraph, receiver_id: str) -> str | None:
    """Primary passer feeding this receiver, by target volume."""
    best, best_targets = None, -1
    for qb, _, k, data in G.in_edges(receiver_id, keys=True, data=True):
        if k == "TARGETED_BY" and data.get("targets", 0) > best_targets:
            best, best_targets = qb, data["targets"]
    return best
