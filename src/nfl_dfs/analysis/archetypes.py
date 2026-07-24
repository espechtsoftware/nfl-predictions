"""Scoring-consistency archetypes: cluster players by DK-points profile.

Tabular-first, per the guide's §8.1 honest framing: clustering is a
statistical operation on per-player feature vectors, so it runs as a
Gaussian mixture on warehouse columns — the knowledge graph consumes the
labels (cascade weighting, similar-player pivots), it does not produce them.

Clustering is within-position only: QB scoring distributions dominate any
cross-position fit and the clusters degenerate into position groups.

GMM over k-means because the interesting distinction — consistent vs.
boom-bust at the same scoring level — is a variance difference, which
spherical k-means models poorly.
"""

from __future__ import annotations

import logging

import networkx as nx
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

PROFILE_FEATURES = ["avg_pts", "cv", "pct_20_plus", "pct_10_plus", "skew"]
POSITIONS = ("QB", "RB", "WR", "TE")
SIMILAR_TO = "SIMILAR_TO"


def consistency_profiles(games: pd.DataFrame, min_games: int = 16) -> pd.DataFrame:
    """Per-player consistency profile from per-game rows
    [gsis_id, position, dk_points] (extra columns pass through via first value).

    cv (volatility), floor rate P(10+), ceiling rate P(20+), and skew are the
    clustering signal; avg_pts anchors the tier.
    """
    pts = games.groupby(["gsis_id", "position"])["dk_points"]
    prof = pts.agg(
        games="count",
        avg_pts="mean",
        sd="std",
        skew="skew",
        pct_20_plus=lambda s: (s >= 20).mean(),
        pct_10_plus=lambda s: (s >= 10).mean(),
    ).reset_index()
    prof = prof[prof.games >= min_games].copy()
    prof["sd"] = prof["sd"].fillna(0.0)
    prof["skew"] = prof["skew"].fillna(0.0)  # bracket access: .skew is a method
    prof["cv"] = prof.sd / prof.avg_pts.clip(lower=1.0)
    if "name" in games.columns:
        names = games.groupby("gsis_id")["name"].first()
        prof["name"] = prof.gsis_id.map(names)
    return prof


def _zscore(X: pd.DataFrame) -> np.ndarray:
    v = X.to_numpy(dtype=float)
    return (v - v.mean(axis=0)) / np.where(v.std(axis=0) > 0, v.std(axis=0), 1.0)


def cluster_archetypes(
    profiles: pd.DataFrame, n_clusters: int = 4, seed: int = 0
) -> pd.DataFrame:
    """Assign each player a cluster and a readable archetype label,
    within position. Labels are deterministic: clusters are tiered by mean
    scoring (tier1 = highest) and suffixed stable/volatile by centroid cv
    relative to the position's cluster median.
    """
    from sklearn.mixture import GaussianMixture

    out = []
    for pos, grp in profiles.groupby("position"):
        grp = grp.copy()
        k = int(max(1, min(n_clusters, len(grp) // 5)))
        if k == 1:
            grp["cluster"] = 0
            grp["archetype"] = f"{pos}-tier1-stable"
            out.append(grp)
            continue
        gmm = GaussianMixture(n_components=k, random_state=seed, n_init=3)
        grp["cluster"] = gmm.fit_predict(_zscore(grp[PROFILE_FEATURES]))

        cents = grp.groupby("cluster").agg(
            c_avg=("avg_pts", "mean"), c_cv=("cv", "mean")
        )
        cents["tier"] = cents.c_avg.rank(ascending=False, method="first").astype(int)
        cv_median = cents.c_cv.median()
        names = {
            c: f"{pos}-tier{int(r.tier)}-{'volatile' if r.c_cv > cv_median else 'stable'}"
            for c, r in cents.iterrows()
        }
        grp["archetype"] = grp.cluster.map(names)
        out.append(grp)
    return pd.concat(out, ignore_index=True)


# Graph integration: labels onto nodes, similarity edges for pivot queries --


def annotate_graph(G: nx.MultiDiGraph, clustered: pd.DataFrame) -> int:
    """Stamp `archetype` on Player nodes. The injury cascade reads this
    attribute to weight depth-chart redistribution toward profile-compatible
    inheritors."""
    n = 0
    for r in clustered.itertuples():
        if r.gsis_id in G:
            G.nodes[r.gsis_id]["archetype"] = r.archetype
            n += 1
    return n


def add_similarity_edges(
    G: nx.MultiDiGraph, clustered: pd.DataFrame, k: int = 5
) -> int:
    """SIMILAR_TO edges from each player to its k nearest same-cluster
    neighbors by profile distance — the traversal behind "cheaper player,
    same scoring profile" pivots. Keeps the graph sparse: k edges per node,
    not a clique per cluster."""
    n = 0
    for (_pos, _cl), grp in clustered.groupby(["position", "cluster"]):
        members = [g for g in grp.gsis_id if g in G]
        grp = grp[grp.gsis_id.isin(members)]
        if len(grp) < 2:
            continue
        Z = _zscore(grp[PROFILE_FEATURES])
        ids = grp.gsis_id.to_numpy()
        for i, gid in enumerate(ids):
            dist = np.linalg.norm(Z - Z[i], axis=1)
            order = np.argsort(dist)
            for j in order[1 : k + 1]:
                G.add_edge(gid, ids[j], key=SIMILAR_TO, distance=float(dist[j]))
                n += 1
    return n


def similar_players(G: nx.MultiDiGraph, gsis_id: str) -> list[tuple[str, float]]:
    """Same-archetype neighbors, closest profile first."""
    if gsis_id not in G:
        return []
    sims = [
        (nbr, data["distance"])
        for _, nbr, key, data in G.out_edges(gsis_id, keys=True, data=True)
        if key == SIMILAR_TO
    ]
    return sorted(sims, key=lambda t: t[1])


# Warehouse entry point ------------------------------------------------------

TABLE = "player_archetypes"


def run(trailing_seasons: int = 3, min_games: int = 16) -> pd.DataFrame:
    """Profile + cluster over the last `trailing_seasons` completed seasons
    and write nfl_features.player_archetypes."""
    from datetime import datetime, timezone

    from ..bq import load_dataframe, query_df
    from ..config import settings

    last = int(
        query_df(
            f"SELECT MAX(season) AS s FROM `{settings.features}.player_week_training`"
        ).s.iloc[0]
    )
    first = last - trailing_seasons + 1
    games = query_df(
        f"""
        SELECT t.gsis_id, t.position, t.y_dk_points AS dk_points, i.name
        FROM `{settings.features}.player_week_training` t
        LEFT JOIN `{settings.raw}.player_ids` i USING (gsis_id)
        WHERE t.season BETWEEN {first} AND {last}
          AND t.position IN {POSITIONS}
        """
    )
    clustered = cluster_archetypes(consistency_profiles(games, min_games=min_games))
    clustered["window_first_season"] = first
    clustered["window_last_season"] = last
    clustered["generated_at"] = datetime.now(timezone.utc)
    load_dataframe(clustered, f"{settings.features}.{TABLE}")
    log.info(
        "Wrote %d player archetypes (%s-%s) across %s",
        len(clustered), first, last, sorted(clustered.archetype.unique()),
    )
    return clustered
