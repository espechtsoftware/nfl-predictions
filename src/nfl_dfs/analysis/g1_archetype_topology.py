"""G1 walk-forward archetype-pair dependence topology diagnostic.

The immutable scientific contract is
``reports/2026-08-12-g1-walk-forward-archetype-topology-protocol.md``.
This module is deliberately score-free and cannot create lineups.
"""

from __future__ import annotations

import base64
from collections import defaultdict
import gzip
from hashlib import sha256
import json
from math import log
import os

import numpy as np
import pandas as pd

from . import archetypes
from . import final_served_dependence as g0


OUTPUT_PREFIX = "G1_ARCHETYPE_TOPOLOGY_JSON="
EVALUATION_SEASONS = (2023, 2024, 2025)
HISTORY_SEASONS = (2019, 2021, 2022, 2023, 2024)
POSITIONS = ("QB", "RB", "WR", "TE")
N_BOOTSTRAPS = 2_000
BOOTSTRAP_SEED = 1_702
CELL_MIN_PAIRS = 100
CELL_MIN_BOOMS = 10
BROAD_MIN_PAIRS = 500
BROAD_MIN_BOOMS = 30
CELL_MATERIAL_BAND = log(1.25)
CELL_EQUIVALENCE_BAND = log(1.15)
PRIMARY_RELATIONSHIPS = (
    "QB_WR", "QB_TE", "QB_RB", "WR_WR", "RB_RB", "TE_TE",
    "QB_OPP_QB", "QB_OPP_WR", "QB_OPP_TE", "WR_OPP_WR",
)
CROSS_GAME_RELATIONSHIPS = ("QB_XGAME_WR", "QB_XGAME_TE", "WR_XGAME_WR")
ALL_RELATIONSHIPS = PRIMARY_RELATIONSHIPS + CROSS_GAME_RELATIONSHIPS
COUNT_COLUMNS = (
    "actual_n00", "actual_n01", "actual_n10", "actual_n11",
    "sim_n00", "sim_n01", "sim_n10", "sim_n11",
)


def fit_walk_forward_archetypes(
    games: pd.DataFrame,
    target_season: int,
) -> pd.DataFrame:
    """Fit the frozen position-scoped labels using strictly-prior active games."""
    required = {"gsis_id", "position", "season", "dk_points", "was_active"}
    missing = required - set(games.columns)
    if missing:
        raise ValueError(f"G1 archetype games missing {sorted(missing)}")
    if target_season not in EVALUATION_SEASONS:
        raise ValueError("G1 target season is outside the frozen evaluation set")
    source = games[
        games.season.astype(int).lt(target_season)
        & games.season.astype(int).isin(HISTORY_SEASONS)
        & games.was_active.fillna(False).astype(bool)
        & games.position.astype(str).str.upper().isin(POSITIONS)
    ].copy()
    source["position"] = source.position.astype(str).str.upper()
    if source.empty or source.season.max() >= target_season:
        raise ValueError("G1 archetype source is empty or not strictly prior")
    profiles = archetypes.consistency_profiles(source, min_games=16)
    clustered = archetypes.cluster_archetypes(
        profiles, n_clusters=4, seed=0)
    if clustered.duplicated(["gsis_id", "position"]).any():
        raise ValueError("G1 archetype labels are not player-position unique")
    clustered["target_season"] = int(target_season)
    clustered["source_first_season"] = int(source.season.min())
    clustered["source_last_season"] = int(source.season.max())
    return clustered


def attach_walk_forward_archetypes(
    frame: pd.DataFrame,
    games: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Attach each target row's prior-only label or the frozen short-history label."""
    out = []
    audits = {}
    for season in EVALUATION_SEASONS:
        target = frame[frame.season.eq(season)].copy()
        labels = fit_walk_forward_archetypes(games, season)
        use = labels[["gsis_id", "position", "archetype"]]
        target = target.merge(
            use, on=["gsis_id", "position"], how="left", validate="many_to_one")
        fallback = target.position.astype(str) + "-history-lt16"
        target["archetype"] = target.archetype.fillna(fallback)
        if target.archetype.str.split("-", n=1).str[0].ne(target.position).any():
            raise ValueError(f"G1 {season} archetype position disagreement")
        audits[str(season)] = {
            "rows": int(len(target)),
            "labeled_rows": int(target.archetype.ne(fallback).sum()),
            "fallback_rows": int(target.archetype.eq(fallback).sum()),
            "fitted_players": int(len(labels)),
            "source_first_season": int(labels.source_first_season.iloc[0]),
            "source_last_season": int(labels.source_last_season.iloc[0]),
            "labels_sha256": sha256(
                labels[["gsis_id", "position", "archetype"]]
                .sort_values(["gsis_id", "position"])
                .to_csv(index=False).encode()
            ).hexdigest(),
        }
        out.append(target)
    joined = pd.concat(out, ignore_index=True)
    if len(joined) != len(frame):
        raise ValueError("G1 archetype attachment changed row count")
    return joined, audits


def _stable_pair_hash(
    season: int,
    week: int,
    relationship: str,
    source: str,
    target: str,
) -> str:
    return sha256(
        f"{season}|{week}|{relationship}|{source}|{target}".encode()
    ).hexdigest()


def build_pair_book(frame: pd.DataFrame) -> pd.DataFrame:
    """Create the 13 frozen directed pair classes on the aligned G1 frame."""
    required = {
        "season", "week", "gsis_id", "position", "team", "opp", "game_id",
        "archetype",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"G1 pair frame missing {sorted(missing)}")
    source = frame.reset_index(drop=True).copy()
    source["_row"] = np.arange(len(source), dtype=int)
    for column in ("position", "team", "opp"):
        source[column] = source[column].astype(str).str.upper()
    if source.duplicated(["season", "week", "gsis_id"]).any():
        raise ValueError("G1 pair frame has duplicate player-week keys")
    if source[["team", "opp", "game_id"]].isna().any().any() or (
        source[["team", "opp", "game_id"]].astype(str).eq("").any().any()
    ):
        raise ValueError("G1 pair frame has unresolved game metadata")

    rows: list[dict] = []

    def add(relationship: str, left: int, right: int) -> None:
        a = source.iloc[left]
        b = source.iloc[right]
        rows.append({
            "season": int(a.season),
            "week": int(a.week),
            "relationship": relationship,
            "source_index": int(left),
            "target_index": int(right),
            "source_gsis_id": str(a.gsis_id),
            "target_gsis_id": str(b.gsis_id),
            "source_archetype": str(a.archetype),
            "target_archetype": str(b.archetype),
        })

    for (_season, _week, _team), group in source.groupby(
        ["season", "week", "team"], sort=True
    ):
        qbs = group[group.position.eq("QB")]._row.to_list()
        if len(qbs) > 1:
            raise ValueError("G1 team-week has multiple supported QBs")
        if qbs:
            qb = int(qbs[0])
            for position, relationship in (
                ("WR", "QB_WR"), ("TE", "QB_TE"), ("RB", "QB_RB")):
                for target in group[group.position.eq(position)]._row:
                    add(relationship, qb, int(target))
        for position, relationship in (
            ("WR", "WR_WR"), ("RB", "RB_RB"), ("TE", "TE_TE")):
            members = [int(value) for value in group[
                group.position.eq(position)]._row]
            for offset, left in enumerate(members):
                for right in members[offset + 1:]:
                    add(relationship, left, right)
                    add(relationship, right, left)

    for (_season, _week, _game), game in source.groupby(
        ["season", "week", "game_id"], sort=True
    ):
        teams = sorted(game.team.unique().tolist())
        if len(teams) != 2:
            raise ValueError("G1 game does not contain exactly two teams")
        by_team = {team: game[game.team.eq(team)] for team in teams}
        for team, opponent in ((teams[0], teams[1]), (teams[1], teams[0])):
            left = by_team[team]
            right = by_team[opponent]
            if left.opp.ne(opponent).any():
                raise ValueError("G1 opponent metadata disagrees with game")
            qbs = left[left.position.eq("QB")]._row.to_list()
            opp_qbs = right[right.position.eq("QB")]._row.to_list()
            if len(qbs) > 1 or len(opp_qbs) > 1:
                raise ValueError("G1 game has multiple supported QBs per team")
            if qbs:
                qb = int(qbs[0])
                if opp_qbs:
                    add("QB_OPP_QB", qb, int(opp_qbs[0]))
                for position, relationship in (
                    ("WR", "QB_OPP_WR"), ("TE", "QB_OPP_TE")):
                    for target in right[right.position.eq(position)]._row:
                        add(relationship, qb, int(target))
        left_wrs = [int(value) for value in by_team[teams[0]][
            by_team[teams[0]].position.eq("WR")]._row]
        right_wrs = [int(value) for value in by_team[teams[1]][
            by_team[teams[1]].position.eq("WR")]._row]
        for left in left_wrs:
            for right in right_wrs:
                add("WR_OPP_WR", left, right)
                add("WR_OPP_WR", right, left)

    for (season, week), slate in source.groupby(["season", "week"], sort=True):
        for source_pos, target_pos, relationship in (
            ("QB", "WR", "QB_XGAME_WR"),
            ("QB", "TE", "QB_XGAME_TE"),
            ("WR", "WR", "WR_XGAME_WR"),
        ):
            targets = slate[slate.position.eq(target_pos)]
            for source_row in slate[slate.position.eq(source_pos)]._row:
                item = source.iloc[int(source_row)]
                eligible = targets[
                    targets.game_id.ne(item.game_id)
                    & targets._row.ne(int(source_row))
                ]
                if eligible.empty:
                    continue
                target_row = min(
                    (int(value) for value in eligible._row),
                    key=lambda value: _stable_pair_hash(
                        int(season), int(week), relationship,
                        str(item.gsis_id), str(source.iloc[value].gsis_id)),
                )
                add(relationship, int(source_row), target_row)

    pairs = pd.DataFrame(rows)
    if pairs.empty or set(pairs.relationship) != set(ALL_RELATIONSHIPS):
        raise ValueError("G1 pair book lacks a frozen relationship class")
    if pairs.duplicated(["relationship", "source_index", "target_index"]).any():
        raise ValueError("G1 pair book contains duplicate directed pairs")
    return pairs.sort_values([
        "season", "week", "relationship", "source_gsis_id", "target_gsis_id",
    ]).reset_index(drop=True)


def _counts_for_pairs(
    pairs: pd.DataFrame,
    actual: np.ndarray,
    simulated: np.ndarray,
    *,
    chunk_size: int = 256,
) -> dict[str, float]:
    left = pairs.source_index.to_numpy(int)
    right = pairs.target_index.to_numpy(int)
    a = actual[left]
    b = actual[right]
    result = {
        "pairs": float(len(pairs)),
        "actual_n00": float(np.count_nonzero((~a) & (~b))),
        "actual_n01": float(np.count_nonzero((~a) & b)),
        "actual_n10": float(np.count_nonzero(a & (~b))),
        "actual_n11": float(np.count_nonzero(a & b)),
        "sim_n00": 0.0, "sim_n01": 0.0,
        "sim_n10": 0.0, "sim_n11": 0.0,
    }
    n_sims = simulated.shape[1]
    for start in range(0, len(left), chunk_size):
        stop = start + chunk_size
        sim_a = simulated[left[start:stop]]
        sim_b = simulated[right[start:stop]]
        result["sim_n00"] += np.count_nonzero((~sim_a) & (~sim_b)) / n_sims
        result["sim_n01"] += np.count_nonzero((~sim_a) & sim_b) / n_sims
        result["sim_n10"] += np.count_nonzero(sim_a & (~sim_b)) / n_sims
        result["sim_n11"] += np.count_nonzero(sim_a & sim_b) / n_sims
    return result


def pair_contributions(
    pairs: pd.DataFrame,
    actual: np.ndarray,
    simulated: np.ndarray,
) -> pd.DataFrame:
    """Aggregate realized and expected-simulation 2x2 counts by slate/cell."""
    rows = []
    keys = [
        "season", "week", "relationship", "source_archetype", "target_archetype",
    ]
    for values, group in pairs.groupby(keys, sort=True):
        row = dict(zip(keys, values))
        row.update(_counts_for_pairs(group, actual, simulated))
        rows.append(row)
    return pd.DataFrame(rows)


def _lift(values: np.ndarray, offset: int) -> np.ndarray:
    n00, n01, n10, n11 = (
        values[:, offset], values[:, offset + 1],
        values[:, offset + 2], values[:, offset + 3],
    )
    p1 = (n11 + 0.5) / (n10 + n11 + 1.0)
    p0 = (n01 + 0.5) / (n00 + n01 + 1.0)
    return p1 / p0


def _classification(
    point: float,
    low: float,
    high: float,
    supported: bool,
) -> str:
    if not supported or not np.isfinite([point, low, high]).all():
        return "unsupported"
    if low >= -CELL_EQUIVALENCE_BAND and high <= CELL_EQUIVALENCE_BAND:
        return "equivalent"
    if abs(point) > CELL_MATERIAL_BAND and (low > 0 or high < 0):
        return "material-miss"
    return "inconclusive"


def _summarize_contributions(
    data: pd.DataFrame,
    *,
    min_pairs: int,
    min_booms: int,
    seed: int = BOOTSTRAP_SEED,
) -> dict:
    clusters = sorted({(int(r.season), int(r.week)) for r in data.itertuples()})
    fields = ["pairs", *COUNT_COLUMNS]
    matrix = np.zeros((len(clusters), len(fields)), dtype=float)
    lookup = {cluster: index for index, cluster in enumerate(clusters)}
    for (season, week), group in data.groupby(["season", "week"], sort=True):
        matrix[lookup[(int(season), int(week))]] = group[fields].sum().to_numpy(float)
    totals = matrix.sum(axis=0, keepdims=True)
    real = _lift(totals, 1)[0]
    sim = _lift(totals, 5)[0]
    point = float(np.log(sim / real))
    rng = np.random.default_rng(seed)
    weights = rng.multinomial(
        len(clusters), np.full(len(clusters), 1.0 / len(clusters)),
        size=N_BOOTSTRAPS,
    )
    boot = weights @ matrix
    gaps = np.log(_lift(boot, 5) / _lift(boot, 1))
    finite = gaps[np.isfinite(gaps)]
    if len(finite) < 0.95 * N_BOOTSTRAPS:
        low = high = float("nan")
    else:
        low, high = np.quantile(finite, [0.025, 0.975]).tolist()
    pairs = int(totals[0, 0])
    source_booms = int(totals[0, 3] + totals[0, 4])
    supported = pairs >= min_pairs and source_booms >= min_booms
    return {
        "pairs": pairs,
        "realized_source_booms": source_booms,
        "realized_lift": float(real),
        "simulated_lift": float(sim),
        "log_simulated_to_realized": point,
        "cluster_ci95_low": float(low) if np.isfinite(low) else None,
        "cluster_ci95_high": float(high) if np.isfinite(high) else None,
        "supported": bool(supported),
        "classification": _classification(point, low, high, supported),
    }


def summarize_cells(contributions: pd.DataFrame) -> tuple[dict, dict]:
    cells = {}
    for keys, group in contributions.groupby(
        ["relationship", "source_archetype", "target_archetype"], sort=True
    ):
        relationship, source, target = keys
        cell = f"{relationship}|{source}|{target}"
        cells[cell] = {
            "relationship": relationship,
            "source_archetype": source,
            "target_archetype": target,
            **_summarize_contributions(
                group, min_pairs=CELL_MIN_PAIRS, min_booms=CELL_MIN_BOOMS),
        }
    broad = {}
    for relationship, group in contributions.groupby("relationship", sort=True):
        aggregate = _summarize_contributions(
            group, min_pairs=BROAD_MIN_PAIRS, min_booms=BROAD_MIN_BOOMS)
        by_season = {}
        for season, season_group in group.groupby("season", sort=True):
            by_season[str(int(season))] = _summarize_contributions(
                season_group,
                min_pairs=max(1, BROAD_MIN_PAIRS // 3),
                min_booms=max(1, BROAD_MIN_BOOMS // 3),
            )
        broad[str(relationship)] = {**aggregate, "by_season": by_season}
    return cells, broad


def _graph_matrix(cells: dict, estimate: str) -> tuple[list[str], np.ndarray]:
    eligible = [
        row for row in cells.values()
        if row["supported"] and row["relationship"] in PRIMARY_RELATIONSHIPS
    ]
    nodes = sorted({
        value for row in eligible
        for value in (row["source_archetype"], row["target_archetype"])
    })
    index = {node: offset for offset, node in enumerate(nodes)}
    weights: dict[tuple[int, int], list[float]] = defaultdict(list)
    for row in eligible:
        left = index[row["source_archetype"]]
        right = index[row["target_archetype"]]
        strength = row["pairs"] * max(log(float(row[estimate])), 0.0)
        weights[tuple(sorted((left, right)))].append(strength)
    matrix = np.zeros((len(nodes), len(nodes)), dtype=float)
    for (left, right), values in weights.items():
        value = float(np.mean(values))
        matrix[left, right] = value
        matrix[right, left] = value
    return nodes, matrix


def _laplacian(matrix: np.ndarray) -> np.ndarray:
    degree = matrix.sum(axis=1)
    active = degree > 0
    inverse = np.zeros_like(degree)
    inverse[active] = 1.0 / np.sqrt(degree[active])
    normalized = inverse[:, None] * matrix * inverse[None, :]
    result = np.eye(len(matrix)) - normalized
    result[~active, :] = 0.0
    result[:, ~active] = 0.0
    return result


def topology_diagnostics(cells: dict) -> dict:
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score

    real_nodes, real = _graph_matrix(cells, "realized_lift")
    sim_nodes, sim = _graph_matrix(cells, "simulated_lift")
    if real_nodes != sim_nodes:
        raise ValueError("G1 realized/simulated graph nodes differ")
    if not real_nodes:
        return {"nodes": 0, "disposition": "unsupported"}
    denom = max(float(np.linalg.norm(real)), np.finfo(float).eps)
    relative = float(np.linalg.norm(sim - real) / denom)
    real_lap = _laplacian(real)
    sim_lap = _laplacian(sim)
    eigen_real = np.linalg.eigvalsh(real_lap)
    eigen_sim = np.linalg.eigvalsh(sim_lap)
    active = (real.sum(axis=1) > 0) & (sim.sum(axis=1) > 0)
    labels_real = labels_sim = np.array([], dtype=int)
    if int(active.sum()) >= 2:
        n_clusters = min(4, int(active.sum()))
        feature_count = min(n_clusters, int(active.sum()))
        real_active = real[np.ix_(active, active)]
        sim_active = sim[np.ix_(active, active)]
        real_active_lap = _laplacian(real_active)
        sim_active_lap = _laplacian(sim_active)
        _, vectors_real = np.linalg.eigh(real_active_lap)
        _, vectors_sim = np.linalg.eigh(sim_active_lap)
        labels_real = KMeans(
            n_clusters=n_clusters, random_state=0, n_init=20,
        ).fit_predict(vectors_real[:, :feature_count])
        labels_sim = KMeans(
            n_clusters=n_clusters, random_state=0, n_init=20,
        ).fit_predict(vectors_sim[:, :feature_count])
        agreement = float(adjusted_rand_score(labels_real, labels_sim))
    else:
        n_clusters = int(active.sum())
        agreement = None
    return {
        "nodes": int(len(real_nodes)),
        "nonisolated_shared_nodes": int(active.sum()),
        "spectral_clusters": n_clusters,
        "relative_frobenius_distance": relative,
        "normalized_laplacian_eigen_l1": float(
            np.mean(np.abs(eigen_real - eigen_sim))),
        "adjusted_rand_agreement": agreement,
        "node_order": real_nodes,
        "realized_labels": labels_real.tolist(),
        "simulated_labels": labels_sim.tolist(),
    }


def pair_scorecard(
    pairs: pd.DataFrame,
    frame: pd.DataFrame,
    draws: np.ndarray,
) -> dict:
    thresholds = np.quantile(draws, 0.90, axis=1)
    actual = frame.actual.to_numpy(float)
    rows = {}
    for relationship, group in pairs.groupby("relationship", sort=True):
        squared = []
        brier = []
        left = group.source_index.to_numpy(int)
        right = group.target_index.to_numpy(int)
        for start in range(0, len(group), 256):
            stop = start + 256
            sim_left = draws[left[start:stop]]
            sim_right = draws[right[start:stop]]
            expected = np.mean(np.abs(sim_left - sim_right) ** 0.5, axis=1)
            observed = np.abs(
                actual[left[start:stop]] - actual[right[start:stop]]) ** 0.5
            squared.extend(np.square(observed - expected).tolist())
            probability = np.mean(
                (sim_left > thresholds[left[start:stop], None])
                & (sim_right > thresholds[right[start:stop], None]),
                axis=1,
            )
            outcome = (
                (actual[left[start:stop]] > thresholds[left[start:stop]])
                & (actual[right[start:stop]] > thresholds[right[start:stop]])
            )
            brier.extend(np.square(outcome.astype(float) - probability).tolist())
        rows[str(relationship)] = {
            "pairs": int(len(group)),
            "variogram_p0_5": float(np.mean(squared)),
            "joint_q90_brier": float(np.mean(brier)),
        }
    total_pairs = sum(row["pairs"] for row in rows.values())
    rows["overall"] = {
        "pairs": int(total_pairs),
        "variogram_p0_5": float(sum(
            row["pairs"] * row["variogram_p0_5"] for row in rows.values()
        ) / total_pairs),
        "joint_q90_brier": float(sum(
            row["pairs"] * row["joint_q90_brier"] for row in rows.values()
        ) / total_pairs),
    }
    return rows


def stable_qb_hub_decision(cells: dict, broad: dict, invariants_pass: bool) -> dict:
    failures = []
    unevaluable = []
    for relationship in ("QB_WR", "QB_TE"):
        row = broad.get(relationship)
        if not row or not row["supported"] or row["cluster_ci95_low"] is None:
            unevaluable.append(f"{relationship}:broad-support")
            continue
        if not (
            row["log_simulated_to_realized"] < -CELL_MATERIAL_BAND
            and row["cluster_ci95_high"] < 0
        ):
            failures.append(f"{relationship}:aggregate-not-material-under")
        seasons_under = 0
        seasons_supported = 0
        for season in map(str, EVALUATION_SEASONS):
            fold = row["by_season"].get(season)
            if not fold or not fold["supported"] or fold["cluster_ci95_low"] is None:
                continue
            seasons_supported += 1
            seasons_under += fold["log_simulated_to_realized"] < 0
            if (
                fold["classification"] == "material-miss"
                and fold["log_simulated_to_realized"] > 0
            ):
                failures.append(f"{relationship}:{season}:opposite-material")
        if seasons_supported < 2:
            unevaluable.append(f"{relationship}:fewer-than-two-supported-seasons")
        elif seasons_under < 2:
            failures.append(f"{relationship}:fewer-than-two-seasons-under")
        matching = [
            value for value in cells.values()
            if value["relationship"] == relationship and value["supported"]
            and value["classification"] == "material-miss"
            and value["log_simulated_to_realized"] < 0
        ]
        if not matching:
            failures.append(f"{relationship}:no-material-archetype-edge")
    if not invariants_pass:
        failures.append("terminal-invariants")
    if failures:
        disposition = "dependence-miss-not-stable-qb-hub"
    elif unevaluable:
        disposition = "g1-inconclusive"
    else:
        disposition = "stable-qb-hub-confirmed"
    return {
        "disposition": disposition,
        "g2_licensed": disposition == "stable-qb-hub-confirmed",
        "failures": failures,
        "unevaluable": unevaluable,
    }


def _decode_json_env(name: str) -> dict:
    encoded = os.environ.get(name, "").strip()
    if not encoded:
        raise ValueError(f"G1 environment {name} is missing")
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        return json.loads(base64.b64decode(padded, validate=True).decode())
    except Exception as exc:
        raise ValueError(f"G1 environment {name} is invalid") from exc


def _load_terminal_book(panel_id: str) -> tuple[pd.DataFrame, np.ndarray, dict]:
    expected_panel = os.environ.get("G1_PANEL_ID", "").strip()
    table = os.environ.get("G1_CACHE_TABLE", "").strip()
    if panel_id != expected_panel or not panel_id:
        raise ValueError("G1 panel differs from terminal selection")
    if table not in g0.LICENSED_CACHES:
        raise ValueError("G1 cache differs from terminal selection")
    schedule = g0._selected_schedule({
        "G0_POSITION_SCHEDULE_B64": os.environ.get(
            "G1_POSITION_SCHEDULE_B64", "")})

    from . import route_final_served_calibration as calibration
    from . import served_position_calibration as position_calibration
    from . import served_tail_calibration as served
    from . import tabpfn_sched_final_served as inherited
    from ..backtest.replay import _market_blend_worlds, load_panel_and_dst, replay_projections
    from ..bq import query_df
    from ..config import settings
    from ..models.blend import effective_model_weight
    from ..models.prop_market import market_points

    served._validate_environment()
    usage = inherited.accepted_usage_law()
    cache_keys = query_df(f"""
        SELECT season, week, gsis_id
        FROM `{settings.features}.{table}`
        WHERE season IN UNNEST(@seasons)
        ORDER BY season, week, gsis_id
        """, params={"seasons": list(calibration.ALL_SEASONS)})
    if len(cache_keys) != 52_307 or cache_keys.duplicated(
        ["season", "week", "gsis_id"]
    ).any():
        raise ValueError("G1 selected cache keys differ from terminal contract")
    accepted = query_df(f"""
        SELECT season, week, gsis_id, pos, team, opp, game_id, actual,
               model_points_pre, mean_projection
        FROM `{settings.predictions}.slate_player_features`
        WHERE panel_run_id = @panel_id AND research_eligible
          AND season IN UNNEST(@seasons)
          AND pos IN UNNEST(@positions)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY season, week, gsis_id ORDER BY generated_at DESC
        ) = 1
        """, params={
            "panel_id": panel_id,
            "seasons": list(calibration.ALL_SEASONS),
            "positions": list(calibration.POSITIONS),
        })

    frames = []
    draw_parts = []
    parity = []
    max_mean_delta = 0.0
    with inherited._common_environment(usage):
        weight = effective_model_weight()
        if not np.isclose(weight, 0.45, rtol=0, atol=0):
            raise ValueError("G1 blend weight differs from terminal law")
        for season in EVALUATION_SEASONS:
            panel, _ = load_panel_and_dst(season)
            market = market_points((season,)).drop_duplicates(
                ["season", "week", "gsis_id"])
            with g0._selected_cache(table):
                projected, draws = replay_projections(
                    panel, season, n_sims=10_000, seed=0, return_draws=True)
            projected, draws, _ = _market_blend_worlds(
                projected, draws, market, weight)
            frame, aligned, arm_parity = calibration._align_arm(
                projected, draws, accepted,
                cache_keys[cache_keys.season.eq(season)], season,
                require_control_parity=False,
            )
            metadata = accepted[accepted.season.eq(season)][[
                "season", "week", "gsis_id", "pos", "team", "opp", "game_id",
            ]].rename(columns={"pos": "position"})
            frame = frame.merge(
                metadata,
                on=["season", "week", "gsis_id", "position"],
                how="left", validate="one_to_one",
            )
            if frame[["team", "opp", "game_id"]].isna().any().any():
                raise ValueError(f"G1 {season} game metadata does not align")
            corrected = position_calibration.apply_position_scales(
                aligned, frame.position, schedule[season]["factors"])
            before = np.asarray(aligned, dtype=float).mean(axis=1)
            after = corrected.mean(axis=1)
            max_mean_delta = max(
                max_mean_delta,
                float(np.max(np.abs(after - before), initial=0.0)),
            )
            frame["mean_projection"] = after
            frames.append(frame)
            draw_parts.append(corrected)
            parity.append(arm_parity)
    frame = pd.concat(frames, ignore_index=True)
    draws = np.concatenate(draw_parts, axis=0)
    return frame, draws, {
        "schedule": schedule,
        "usage_law": usage,
        "parity": parity,
        "cache_table": table,
        "cache_rows": int(len(cache_keys)),
        "maximum_mean_delta": max_mean_delta,
    }


def run(panel_id: str) -> dict:
    """Run the sole frozen score-free G1 topology diagnostic."""
    from ..bq import query_df
    from ..config import settings

    frame, draws, terminal = _load_terminal_book(panel_id)
    g0_reference = _decode_json_env("G1_G0_REFERENCE_B64")
    reproduced = g0.evaluate_dependence(frame, draws)
    reproduction_failures = []
    for key in ("rows", "slates", "n_sims"):
        if reproduced["population"].get(key) != g0_reference["population"].get(key):
            reproduction_failures.append(f"population:{key}")
    for cell in g0.CELL_BANDS:
        for metric in ("realized_estimate", "simulated_estimate"):
            left = reproduced["cells"][cell].get(metric)
            right = g0_reference["cells"][cell].get(metric)
            if left is None or right is None or not np.isclose(
                left, right, rtol=0, atol=1e-12
            ):
                reproduction_failures.append(f"{cell}:{metric}")

    supported = frame[
        frame.position.isin(POSITIONS) & frame.mean_projection.ge(g0.MIN_MEAN)
    ].reset_index(drop=True)
    draw_indices = frame.index[
        frame.position.isin(POSITIONS) & frame.mean_projection.ge(g0.MIN_MEAN)
    ].to_numpy(int)
    supported_draws = draws[draw_indices]
    if len(supported) != 7_848 or supported[["season", "week"]].drop_duplicates().shape[0] != 54:
        raise ValueError("G1 supported G0 population differs")
    games = query_df(f"""
        SELECT gsis_id, position, season, week, y_dk_points AS dk_points,
               was_active
        FROM `{settings.features}.player_week_training`
        WHERE season IN UNNEST(@seasons)
          AND position IN UNNEST(@positions)
          AND was_active
        ORDER BY season, week, gsis_id
        """, params={
            "seasons": list(HISTORY_SEASONS),
            "positions": list(POSITIONS),
        })
    supported, archetype_audit = attach_walk_forward_archetypes(supported, games)
    label_rows = supported[[
        "season", "gsis_id", "position", "archetype",
    ]].drop_duplicates().sort_values(["season", "gsis_id", "position"])
    label_csv = label_rows.to_csv(index=False).encode()
    label_gzip = gzip.compress(label_csv, mtime=0)
    pairs = build_pair_book(supported)
    thresholds = np.quantile(supported_draws, 0.90, axis=1)
    actual_flags = supported.actual.to_numpy(float) > thresholds
    simulated_flags = supported_draws > thresholds[:, None]
    contributions = pair_contributions(pairs, actual_flags, simulated_flags)
    cells, broad = summarize_cells(contributions)
    terminal_invariants = {
        "g0_reproduction_failures": reproduction_failures,
        "g0_supported_rows": int(len(supported)),
        "g0_slates": int(supported[["season", "week"]].drop_duplicates().shape[0]),
        "cache_rows": terminal["cache_rows"],
        "tabpfn_coverage_is_one": all(
            np.isclose(row["tabpfn_coverage"], 1.0, rtol=0, atol=0)
            for row in terminal["parity"]
        ),
        "maximum_mean_delta": terminal["maximum_mean_delta"],
        "passes": False,
    }
    terminal_invariants["passes"] = (
        not reproduction_failures
        and terminal_invariants["g0_supported_rows"] == 7_848
        and terminal_invariants["g0_slates"] == 54
        and terminal_invariants["cache_rows"] == 52_307
        and terminal_invariants["tabpfn_coverage_is_one"]
        and terminal_invariants["maximum_mean_delta"] <= 1e-10
    )
    decision = stable_qb_hub_decision(
        cells, broad, terminal_invariants["passes"])
    report = {
        "version": "v1",
        "panel": panel_id,
        "cache_table": terminal["cache_table"],
        "position_schedule": {
            str(key): value for key, value in terminal["schedule"].items()},
        "usage_law": terminal["usage_law"],
        "population": {
            "rows": int(len(supported)),
            "slates": 54,
            "pairs": int(len(pairs)),
            "relationship_counts": {
                str(key): int(value)
                for key, value in pairs.relationship.value_counts().sort_index().items()
            },
        },
        "archetypes": archetype_audit,
        "archetype_label_artifact": {
            "rows": int(len(label_rows)),
            "csv_sha256": sha256(label_csv).hexdigest(),
            "gzip_sha256": sha256(label_gzip).hexdigest(),
            "gzip_base64": base64.b64encode(label_gzip).decode(),
        },
        "cells": cells,
        "broad_relationships": broad,
        "topology": topology_diagnostics(cells),
        "scorecard": pair_scorecard(pairs, supported, supported_draws),
        "g0_multiplicity_reproduction": {
            cell: reproduced["cells"][cell]
            for cell in ("multiplicity_ge2", "multiplicity_ge3", "multiplicity_ge4")
        },
        "bootstrap": {
            "replicates": N_BOOTSTRAPS,
            "seed": BOOTSTRAP_SEED,
            "cluster": "season-week-slate",
        },
        "invariants": terminal_invariants,
        **decision,
    }
    print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True, allow_nan=False))
    return report
