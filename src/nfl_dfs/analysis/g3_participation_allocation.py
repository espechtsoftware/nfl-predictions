"""Frozen G3 participation-conditioned target/carry allocation gate."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.optimize import minimize_scalar
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

from . import usage_dirichlet_calibration as usage


SOURCE_SEASONS = tuple(range(2016, 2025))
TARGET_SEASONS = usage.ALL_SEASONS
CALIBRATION_SEASONS = usage.CALIBRATION_SEASONS
EVALUATION_SEASONS = usage.EVALUATION_SEASONS
GLOBAL_K = 28.154043586960896
EMBEDDING_DIMENSION = 16
NEGATIVE_SAMPLES = 5
ACTOR_CONTEXT_BONUS = 3.0
SVD_ITERATIONS = 7
SVD_SEED = 8_112_026
MIN_GEOMETRY_MASS = 0.80
BETA_BOUNDS = (-1.5, 1.5)
BETA_L2 = 0.05
BETA_X_TOL = 1e-6
BETA_ACTIVITY_FLOOR = 0.01
K_BOUNDS = (5.0, 500.0)
BOOTSTRAP_RESAMPLES = 2_000
BOOTSTRAP_SEED = 8_113_026
OUTPUT_PREFIX = "G3_PARTICIPATION_ALLOCATION_JSON="
ACCEPTED_CACHE = "tabpfn_active_label_treatment_v2"
HISTORICAL_PANEL = "20260811-pitclean-e80-k1-role12union-a12ab31"
EXPECTED_SELECTION = {
    "allocation": "dirichlet",
    "selected_k": str(GLOBAL_K),
    "cache_table": ACCEPTED_CACHE,
    "historical_source": HISTORICAL_PANEL,
}
FORBIDDEN_ENVS = usage.FORBIDDEN_ENVS


@dataclass(frozen=True)
class GroupGeometry:
    dispersion: float
    known_players: int
    known_probability_mass: float
    valid: bool


def _validate_environment() -> None:
    ensemble = os.environ.get("MODEL_ENSEMBLE", "").strip()
    if ensemble not in ("", "1"):
        raise ValueError("G3 requires MODEL_ENSEMBLE=1")
    active = [
        name for name in FORBIDDEN_ENVS
        if os.environ.get(name, "").strip() not in ("", "0")
    ]
    if active:
        raise ValueError(f"G3 has active model levers: {active}")


def _stable_frame_sha256(frame: pd.DataFrame, columns: list[str]) -> str:
    selected = frame.loc[:, columns].copy()
    selected = selected.sort_values(columns[:2], kind="mergesort").reset_index(
        drop=True)
    hashes = pd.util.hash_pandas_object(selected, index=False).to_numpy(
        dtype=np.uint64)
    digest = hashlib.sha256()
    digest.update("|".join(columns).encode("utf-8"))
    digest.update(hashes.tobytes())
    return digest.hexdigest()


def _players(value: object) -> tuple[str, ...]:
    if not isinstance(value, str) or not value:
        return ()
    return tuple(sorted({
        token for token in value.split(";") if token.startswith("00-")
    }))


def build_season_cooccurrence(
    participation: pd.DataFrame,
    pbp: pd.DataFrame,
) -> tuple[dict[tuple[str, str], float], dict]:
    """Aggregate the frozen on-field and explicit-actor SGNS contexts."""
    pcols = ["nflverse_game_id", "play_id", "offense_players", "n_offense"]
    bcols = [
        "game_id", "play_id", "passer_player_id", "receiver_player_id",
        "rusher_player_id",
    ]
    pmissing = set(pcols) - set(participation.columns)
    bmissing = set(bcols) - set(pbp.columns)
    if pmissing or bmissing:
        raise ValueError(
            f"G3 source columns missing participation={sorted(pmissing)} "
            f"pbp={sorted(bmissing)}")

    part = participation[pcols].copy()
    part["play_id"] = pd.to_numeric(part.play_id, errors="coerce")
    part["parsed_players"] = part.offense_players.map(_players)
    valid = part[
        part.n_offense.eq(11) & part.parsed_players.map(len).eq(11)
    ].copy()
    if valid.empty:
        raise ValueError("G3 source contains no valid 11-player offense rows")

    plays = pbp[bcols].copy()
    plays["play_id"] = pd.to_numeric(plays.play_id, errors="coerce")
    plays = plays.drop_duplicates(["game_id", "play_id"], keep="last")
    merged = valid.merge(
        plays,
        left_on=["nflverse_game_id", "play_id"],
        right_on=["game_id", "play_id"],
        how="left",
        validate="one_to_one",
    )

    vocabulary = sorted({
        player for row in merged.parsed_players for player in row
    })
    index = {player: offset for offset, player in enumerate(vocabulary)}
    x_rows: list[int] = []
    x_cols: list[int] = []
    a_rows: list[int] = []
    a_cols: list[int] = []
    rows_with_actor = 0
    actor_mentions = 0
    actor_columns = (
        "passer_player_id", "receiver_player_id", "rusher_player_id")
    for row_number, row in enumerate(merged.itertuples(index=False)):
        players = row.parsed_players
        player_set = set(players)
        for player in players:
            x_rows.append(row_number)
            x_cols.append(index[player])
        actors = {
            str(getattr(row, column)) for column in actor_columns
            if isinstance(getattr(row, column), str)
            and str(getattr(row, column)) in player_set
        }
        if actors:
            rows_with_actor += 1
            actor_mentions += len(actors)
        for player in actors:
            a_rows.append(row_number)
            a_cols.append(index[player])

    shape = (len(merged), len(vocabulary))
    incidence = sparse.csr_matrix(
        (np.ones(len(x_rows), dtype=np.float64), (x_rows, x_cols)),
        shape=shape,
    )
    actors = sparse.csr_matrix(
        (np.ones(len(a_rows), dtype=np.float64), (a_rows, a_cols)),
        shape=shape,
    )
    base = (incidence.T @ incidence).tocsr()
    directed = (actors.T @ incidence).tocsr()
    weights = base + ACTOR_CONTEXT_BONUS * (directed + directed.T)
    weights.setdiag(0)
    weights.eliminate_zeros()
    upper = sparse.triu(weights, k=1).tocoo()
    edges = {
        (vocabulary[int(left)], vocabulary[int(right)]): float(weight)
        for left, right, weight in zip(upper.row, upper.col, upper.data)
    }
    audit = {
        "participation_rows": int(len(participation)),
        "pbp_rows": int(len(pbp)),
        "valid_11_player_rows": int(len(merged)),
        "rows_with_explicit_actor": int(rows_with_actor),
        "actor_mentions": int(actor_mentions),
        "players": int(len(vocabulary)),
        "undirected_edges": int(len(edges)),
        "edge_weight_sum": float(sum(edges.values())),
    }
    return edges, audit


def fit_shifted_pmi_embedding(
    edges: dict[tuple[str, str], float],
    dimension: int = EMBEDDING_DIMENSION,
) -> tuple[dict[str, np.ndarray], dict]:
    """Factor the fixed symmetric positive shifted-PMI matrix."""
    players = sorted({player for edge in edges for player in edge})
    if len(players) <= dimension:
        raise ValueError("G3 player vocabulary is too small for frozen dimension")
    index = {player: offset for offset, player in enumerate(players)}
    rows: list[int] = []
    cols: list[int] = []
    values: list[float] = []
    for (left, right), value in sorted(edges.items()):
        if not np.isfinite(value) or value <= 0 or left == right:
            raise ValueError("G3 co-occurrence edge is invalid")
        i, j = index[left], index[right]
        rows.extend((i, j))
        cols.extend((j, i))
        values.extend((value, value))
    matrix = sparse.csr_matrix(
        (values, (rows, cols)), shape=(len(players), len(players)))
    row_sums = np.asarray(matrix.sum(axis=1)).ravel()
    total = float(row_sums.sum())
    coo = matrix.tocoo()
    shifted = (
        np.log(coo.data * total / (row_sums[coo.row] * row_sums[coo.col]))
        - math.log(NEGATIVE_SAMPLES)
    )
    keep = shifted > 0
    ppmi = sparse.csr_matrix(
        (shifted[keep], (coo.row[keep], coo.col[keep])),
        shape=matrix.shape,
    )
    if ppmi.nnz == 0:
        raise ValueError("G3 shifted-PMI matrix is empty")
    fitted = TruncatedSVD(
        n_components=dimension,
        n_iter=SVD_ITERATIONS,
        random_state=SVD_SEED,
    ).fit_transform(ppmi)
    fitted = normalize(fitted, norm="l2", axis=1)
    nonzero = np.linalg.norm(fitted, axis=1) > 0
    embeddings = {
        player: fitted[offset].astype(np.float64, copy=True)
        for offset, player in enumerate(players) if nonzero[offset]
    }
    audit = {
        "players": int(len(players)),
        "embedded_players": int(len(embeddings)),
        "undirected_edges": int(len(edges)),
        "shifted_pmi_nonzero": int(ppmi.nnz),
        "dimension": int(dimension),
        "negative_samples": NEGATIVE_SAMPLES,
        "svd_iterations": SVD_ITERATIONS,
        "svd_seed": SVD_SEED,
    }
    return embeddings, audit


def build_walk_forward_embeddings() -> tuple[dict[int, dict[str, np.ndarray]], dict]:
    """Load each source once, then construct cumulative target-season folds."""
    import nflreadpy as nfl

    edges_by_season: dict[int, dict[tuple[str, str], float]] = {}
    source_audit: dict[str, dict] = {}
    for season in SOURCE_SEASONS:
        participation = nfl.load_participation([season]).select([
            "nflverse_game_id", "play_id", "offense_players", "n_offense",
        ]).to_pandas()
        pbp = nfl.load_pbp([season]).select([
            "game_id", "play_id", "passer_player_id", "receiver_player_id",
            "rusher_player_id",
        ]).to_pandas()
        edges, audit = build_season_cooccurrence(participation, pbp)
        audit["participation_sha256"] = _stable_frame_sha256(
            participation,
            ["nflverse_game_id", "play_id", "offense_players", "n_offense"],
        )
        audit["pbp_sha256"] = _stable_frame_sha256(
            pbp,
            [
                "game_id", "play_id", "passer_player_id",
                "receiver_player_id", "rusher_player_id",
            ],
        )
        edges_by_season[season] = edges
        source_audit[str(season)] = audit

    cumulative: defaultdict[tuple[str, str], float] = defaultdict(float)
    embeddings: dict[int, dict[str, np.ndarray]] = {}
    fold_audit: dict[str, dict] = {}
    targets = set(TARGET_SEASONS)
    for source_season in SOURCE_SEASONS:
        for edge, value in edges_by_season[source_season].items():
            cumulative[edge] += value
        target = source_season + 1
        if target not in targets:
            continue
        fitted, audit = fit_shifted_pmi_embedding(dict(cumulative))
        embeddings[target] = fitted
        fold_audit[str(target)] = {
            **audit,
            "source_seasons": list(range(SOURCE_SEASONS[0], target)),
            "maximum_source_season": int(source_season),
            "pit_valid": bool(source_season < target),
        }
    if set(embeddings) != set(TARGET_SEASONS):
        raise ValueError("G3 embedding folds are incomplete")
    return embeddings, {
        "sources": source_audit,
        "folds": fold_audit,
    }


def group_geometry(
    group: usage.UsageGroup,
    embeddings: dict[str, np.ndarray],
) -> GroupGeometry:
    probabilities = np.asarray(group.probabilities, dtype=np.float64)
    known = np.asarray([player in embeddings for player in group.players])
    mass = float(probabilities[known].sum())
    count = int(known.sum())
    valid = count >= 2 and mass >= MIN_GEOMETRY_MASS
    if not valid:
        return GroupGeometry(0.0, count, mass, False)
    weights = probabilities[known] / mass
    matrix = np.vstack([
        embeddings[player] for player, keep in zip(group.players, known) if keep
    ])
    centroid = np.average(matrix, axis=0, weights=weights)
    dispersion = float(np.sum(weights * np.square(matrix - centroid).sum(axis=1)))
    if not np.isfinite(dispersion) or dispersion < 0:
        raise ValueError("G3 embedding dispersion is invalid")
    return GroupGeometry(dispersion, count, mass, True)


def build_geometry_frame(
    groups: Iterable[usage.UsageGroup],
    embeddings_by_season: dict[int, dict[str, np.ndarray]],
) -> pd.DataFrame:
    records = []
    for ordinal, group in enumerate(groups):
        geometry = group_geometry(group, embeddings_by_season[group.season])
        records.append({
            "ordinal": ordinal,
            "season": group.season,
            "week": group.week,
            "team": group.team,
            "kind": group.kind,
            "dispersion": geometry.dispersion,
            "known_players": geometry.known_players,
            "known_probability_mass": geometry.known_probability_mass,
            "geometry_valid": geometry.valid,
            "group": group,
        })
    return pd.DataFrame.from_records(records)


def standardize_geometry(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    output = frame.copy()
    output["z"] = 0.0
    scaling: dict[str, dict] = {}
    calibration = output.season.isin(CALIBRATION_SEASONS)
    for kind in usage.KINDS:
        fit_rows = output[
            calibration & output.kind.eq(kind) & output.geometry_valid]
        if len(fit_rows) < 2:
            raise ValueError(f"G3 lacks calibration geometry for {kind}")
        mean = float(fit_rows.dispersion.mean())
        std = float(fit_rows.dispersion.std(ddof=0))
        if not np.isfinite(std) or std <= 0:
            raise ValueError(f"G3 calibration geometry is constant for {kind}")
        eligible = output.kind.eq(kind) & output.geometry_valid
        output.loc[eligible, "z"] = (
            output.loc[eligible, "dispersion"] - mean) / std
        scaling[kind] = {
            "mean": mean,
            "standard_deviation": std,
            "calibration_groups": int(len(fit_rows)),
        }
    return output, scaling


def group_k(z: float, beta: float, valid: bool = True) -> float:
    if not valid:
        return GLOBAL_K
    return float(np.clip(GLOBAL_K * math.exp(beta * z), *K_BOUNDS))


def _beta_objective(frame: pd.DataFrame, beta: float) -> float:
    losses = [
        usage.dirichlet_multinomial_nll(
            row.group, group_k(row.z, beta, bool(row.geometry_valid)))
        for row in frame.itertuples(index=False)
    ]
    return float(np.mean(losses) + BETA_L2 * beta * beta)


def fit_beta(frame: pd.DataFrame) -> dict:
    if frame.empty:
        raise ValueError("G3 beta fit has no groups")
    result = minimize_scalar(
        lambda value: _beta_objective(frame, float(value)),
        bounds=BETA_BOUNDS,
        method="bounded",
        options={"xatol": BETA_X_TOL},
    )
    candidates = [float(result.x), 0.0, *BETA_BOUNDS]
    scored = [(value, _beta_objective(frame, value)) for value in candidates]
    minimum = min(objective for _, objective in scored)
    tied = [
        pair for pair in scored if abs(pair[1] - minimum) <= usage.OBJECTIVE_TIE_TOL
    ]
    selected, objective = min(tied, key=lambda pair: abs(pair[0]))
    return {
        "beta": float(selected),
        "beta_display": round(float(selected), 6),
        "objective": float(objective),
        "optimizer_success": bool(result.success),
        "optimizer_message": str(result.message),
        "optimizer_iterations": int(result.nit),
        "bounds": list(BETA_BOUNDS),
        "x_tolerance": BETA_X_TOL,
        "l2_penalty": BETA_L2,
    }


def score_frame(frame: pd.DataFrame, fits: dict[str, dict]) -> pd.DataFrame:
    records = []
    for row in frame.itertuples(index=False):
        beta = float(fits[row.kind]["beta"])
        treatment_k = group_k(row.z, beta, bool(row.geometry_valid))
        records.append({
            "season": int(row.season),
            "week": int(row.week),
            "team": str(row.team),
            "kind": str(row.kind),
            "opportunities": int(row.group.total),
            "geometry_valid": bool(row.geometry_valid),
            "treatment_k": treatment_k,
            "control_nll": usage.dirichlet_multinomial_nll(row.group, GLOBAL_K),
            "treatment_nll": usage.dirichlet_multinomial_nll(
                row.group, treatment_k),
        })
    scores = pd.DataFrame.from_records(records)
    scores["treatment_minus_control"] = (
        scores.treatment_nll - scores.control_nll)
    return scores


def summarize(scores: pd.DataFrame) -> dict:
    if scores.empty:
        raise ValueError("G3 score summary has no groups")
    return {
        "groups": int(len(scores)),
        "opportunities": int(scores.opportunities.sum()),
        "control_nll_sum": float(scores.control_nll.sum()),
        "treatment_nll_sum": float(scores.treatment_nll.sum()),
        "control_mean_nll_per_group": float(scores.control_nll.mean()),
        "treatment_mean_nll_per_group": float(scores.treatment_nll.mean()),
        "mean_treatment_minus_control": float(
            scores.treatment_minus_control.mean()),
        "geometry_coverage": float(scores.geometry_valid.mean()),
        "treatment_k_min": float(scores.treatment_k.min()),
        "treatment_k_median": float(scores.treatment_k.median()),
        "treatment_k_max": float(scores.treatment_k.max()),
    }


def clustered_bootstrap(scores: pd.DataFrame) -> dict:
    frame = scores.copy()
    frame["cluster"] = (
        frame.season.astype(str) + ":" + frame.week.astype(str) + ":"
        + frame.team.astype(str)
    )
    clusters = [
        group.treatment_minus_control.to_numpy(np.float64)
        for _, group in frame.groupby("cluster", sort=True)
    ]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = np.empty(BOOTSTRAP_RESAMPLES, dtype=np.float64)
    for index in range(BOOTSTRAP_RESAMPLES):
        chosen = rng.integers(0, len(clusters), size=len(clusters))
        values = np.concatenate([clusters[item] for item in chosen])
        draws[index] = float(values.mean())
    return {
        "clusters": int(len(clusters)),
        "resamples": BOOTSTRAP_RESAMPLES,
        "seed": BOOTSTRAP_SEED,
        "observed_mean_treatment_minus_control": float(
            frame.treatment_minus_control.mean()),
        "bootstrap_mean": float(draws.mean()),
        "ci95": [
            float(np.quantile(draws, 0.025)),
            float(np.quantile(draws, 0.975)),
        ],
    }


def gate_report(
    scores: pd.DataFrame,
    fits: dict[str, dict],
    source_audit: dict,
) -> dict:
    evaluation = scores[scores.season.isin(EVALUATION_SEASONS)]
    aggregate = summarize(evaluation)
    by_kind = {
        kind: summarize(evaluation[evaluation.kind.eq(kind)])
        for kind in usage.KINDS
    }
    by_season = {
        str(season): summarize(evaluation[evaluation.season.eq(season)])
        for season in EVALUATION_SEASONS
    }
    coverage_cells = {
        f"{season}:{kind}": float(evaluation[
            evaluation.season.eq(season) & evaluation.kind.eq(kind)
        ].geometry_valid.mean())
        for season in EVALUATION_SEASONS for kind in usage.KINDS
    }
    active_kinds = [
        kind for kind in usage.KINDS
        if abs(float(fits[kind]["beta"])) >= BETA_ACTIVITY_FLOOR
        and evaluation[evaluation.kind.eq(kind)].treatment_k.nunique() > 1
    ]
    bootstrap = clustered_bootstrap(evaluation)
    checks = {
        "point_in_time_sources": all(
            fold.get("pit_valid")
            and fold.get("maximum_source_season", 9999) < int(target)
            for target, fold in source_audit["folds"].items()),
        "source_identities_present": all(
            item.get("participation_sha256") and item.get("pbp_sha256")
            for item in source_audit["sources"].values()),
        "optimizers_succeeded": all(
            fits[kind]["optimizer_success"] for kind in usage.KINDS),
        "treatment_k_in_bounds": bool(
            np.isfinite(scores.treatment_k).all()
            and scores.treatment_k.between(*K_BOUNDS).all()),
        "evaluation_geometry_coverage_each_cell_at_least_80pct": all(
            value >= MIN_GEOMETRY_MASS for value in coverage_cells.values()),
        "conditional_law_active": bool(active_kinds),
        "aggregate_mean_nll_improves": (
            aggregate["mean_treatment_minus_control"] < 0),
        "target_mean_nll_improves": (
            by_kind["targets"]["mean_treatment_minus_control"] < 0),
        "carry_mean_nll_improves": (
            by_kind["carries"]["mean_treatment_minus_control"] < 0),
        "at_least_two_of_three_seasons_improve": sum(
            report["mean_treatment_minus_control"] < 0
            for report in by_season.values()) >= 2,
        "clustered_bootstrap_upper_below_zero": bootstrap["ci95"][1] < 0,
    }
    checks["passes"] = all(checks.values())
    return {
        **checks,
        "active_kinds": active_kinds,
        "coverage_cells": coverage_cells,
        "bootstrap": bootstrap,
    }


def run() -> dict:
    """Execute the preregistered score-free G3 Stage A gate."""
    _validate_environment()
    from ..backtest.replay import load_panel_and_dst
    from ..models import coldstart, components

    embeddings, source_audit = build_walk_forward_embeddings()
    groups_by_season: dict[int, list[usage.UsageGroup]] = {}
    population: dict[str, dict] = {}
    for season in TARGET_SEASONS:
        panel, _ = load_panel_and_dst(season)
        fitted = components.train(
            panel,
            target_season=season,
            num_boost_round=usage.NUM_BOOST_ROUND,
        )
        rows = panel[panel.season.eq(season)].reset_index(drop=True)
        model_rows = coldstart.fill_cold_start_features(rows.copy())
        predictions = fitted.predict_components(model_rows)
        groups, audit = usage.build_usage_groups(rows, predictions, season)
        groups_by_season[season] = groups
        population[str(season)] = audit

    groups = [
        group for season in TARGET_SEASONS for group in groups_by_season[season]
    ]
    geometry, scaling = standardize_geometry(
        build_geometry_frame(groups, embeddings))
    calibration = geometry[geometry.season.isin(CALIBRATION_SEASONS)]
    fits = {
        kind: fit_beta(calibration[calibration.kind.eq(kind)])
        for kind in usage.KINDS
    }
    scores = score_frame(geometry, fits)
    calibration_scores = scores[scores.season.isin(CALIBRATION_SEASONS)]
    evaluation_scores = scores[scores.season.isin(EVALUATION_SEASONS)]
    gate = gate_report(scores, fits, source_audit)
    report = {
        "branch": {
            "control": "accepted-global-dirichlet-k",
            "global_k": GLOBAL_K,
            "treatment": "participation-conditioned-dirichlet-hierarchy",
            "accepted_cache": ACCEPTED_CACHE,
            "historical_panel": HISTORICAL_PANEL,
        },
        "representation": {
            "objective": "symmetric-positive-shifted-pmi-sgns",
            "embedding_dimension": EMBEDDING_DIMENSION,
            "negative_samples": NEGATIVE_SAMPLES,
            "actor_context_bonus": ACTOR_CONTEXT_BONUS,
            "svd_iterations": SVD_ITERATIONS,
            "svd_seed": SVD_SEED,
            "minimum_geometry_probability_mass": MIN_GEOMETRY_MASS,
        },
        "source_audit": source_audit,
        "population": population,
        "scaling": scaling,
        "fits": fits,
        "calibration": {
            "aggregate": summarize(calibration_scores),
            "by_kind": {
                kind: summarize(calibration_scores[calibration_scores.kind.eq(kind)])
                for kind in usage.KINDS
            },
        },
        "evaluation": {
            "aggregate": summarize(evaluation_scores),
            "by_kind": {
                kind: summarize(evaluation_scores[evaluation_scores.kind.eq(kind)])
                for kind in usage.KINDS
            },
            "by_season": {
                str(season): summarize(
                    evaluation_scores[evaluation_scores.season.eq(season)])
                for season in EVALUATION_SEASONS
            },
        },
        "gate": gate,
        "disposition": (
            "g3-stage-a-passes-to-dependence-gate"
            if gate["passes"] else "g3-stage-a-conditional-allocation-fails"
        ),
    }
    print(OUTPUT_PREFIX + json.dumps(report, sort_keys=True))
    return report

