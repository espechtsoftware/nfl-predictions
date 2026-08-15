"""Outcome-viewed tools for understanding the frozen candidate corpus.

These diagnostics are intentionally descriptive.  They may generate a future
hypothesis, but their outputs are forbidden from changing a historical arm
decision or entering a production score/selector without a new outcome-unseen
protocol.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Any, Mapping, Sequence

import lightgbm as lgb
import networkx as nx
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neighbors import NearestNeighbors


CORPUS_SEED = 20260814
HIGH_SCORE = 200.0
EMBEDDING_POINT_LIMIT = 15_000


def _roster(value: object) -> tuple[str, ...]:
    players = tuple(item for item in str(value).split(",") if item)
    if len(players) != 9 or len(set(players)) != 9:
        raise ValueError("corpus diagnostic roster is not nine unique players")
    return players


def _finite(value: float | np.floating | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def _candidate_structure(
    candidates: pd.DataFrame,
    players: pd.DataFrame,
) -> pd.DataFrame:
    """Attach deterministic roster and slate structure to candidate appearances."""
    required_candidates = {
        "panel_run_id", "season", "week", "cand_ix", "players", "selected",
        "actual_score", "salary", "tag", "p_line", "sim_mean", "sim_sd",
        "sim_q50", "sim_q90", "sim_q99", "sim_rank_p_line",
    }
    required_players = {
        "season", "week", "id", "pos", "team", "opp", "game_id", "salary",
    }
    if not required_candidates <= set(candidates):
        raise ValueError("candidate corpus lacks required fields")
    if not required_players <= set(players):
        raise ValueError("player corpus lacks required fields")
    if players.duplicated(["season", "week", "id"]).any():
        raise ValueError("player corpus repeats season/week/player")

    player_lookup: dict[tuple[int, int, str], tuple[str, str, str, str, float]] = {}
    for row in players.itertuples(index=False):
        ownership = getattr(row, "own_est", np.nan)
        player_lookup[(int(row.season), int(row.week), str(row.id))] = (
            str(row.pos).upper(), str(row.team), str(row.opp), str(row.game_id),
            float(ownership) if pd.notna(ownership) else np.nan,
        )

    records: list[dict[str, Any]] = []
    for row in candidates.itertuples(index=False):
        ids = _roster(row.players)
        roster = []
        for player_id in ids:
            key = (int(row.season), int(row.week), player_id)
            if key not in player_lookup:
                raise ValueError(f"candidate player absent from feature lookup: {key}")
            roster.append((player_id, *player_lookup[key]))
        quarterbacks = [item for item in roster if item[1] == "QB"]
        if len(quarterbacks) != 1:
            raise ValueError("candidate does not contain one quarterback")
        _, _, qb_team, qb_opp, _, _ = quarterbacks[0]
        team_counts = Counter(item[2] for item in roster if item[1] != "DST")
        qb_stack = sum(
            item[2] == qb_team and item[1] in {"RB", "WR", "TE"}
            for item in roster
        )
        bring_back = sum(
            item[2] == qb_opp and item[1] in {"RB", "WR", "TE"}
            for item in roster
        )
        ownership = np.asarray([item[5] for item in roster], dtype=float)
        records.append({
            "games_represented": len({item[4] for item in roster}),
            "largest_team_block": max(team_counts.values()),
            "qb_stack_count": int(qb_stack),
            "bring_back_count": int(bring_back),
            "ownership_sum": (
                float(ownership.sum()) if np.isfinite(ownership).all() else np.nan
            ),
            "ownership_missing": int((~np.isfinite(ownership)).sum()),
        })
    structure = pd.DataFrame(records, index=candidates.index)
    frame = pd.concat([candidates.copy(), structure], axis=1)
    keys = ["panel_run_id", "season", "week"]
    for source, target in (
        ("p_line", "p_line_percentile"),
        ("sim_q99", "sim_q99_percentile"),
        ("ownership_sum", "ownership_sum_percentile"),
    ):
        values = pd.to_numeric(frame[source], errors="coerce")
        frame[target] = values.groupby(
            [frame[key] for key in keys], sort=False
        ).rank(method="average", pct=True)
    return frame


def _categorical_conditions(frame: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]:
    salary = pd.to_numeric(frame.salary, errors="coerce")
    games = pd.to_numeric(frame.games_represented, errors="coerce")
    largest = pd.to_numeric(frame.largest_team_block, errors="coerce")
    stack = pd.to_numeric(frame.qb_stack_count, errors="coerce")
    bring = pd.to_numeric(frame.bring_back_count, errors="coerce")

    def tercile(column: str) -> pd.Series:
        values = pd.to_numeric(frame[column], errors="coerce")
        return pd.Series(
            np.select(
                [values.le(1 / 3), values.ge(2 / 3)],
                ["bottom", "top"],
                default="middle",
            ),
            index=frame.index,
        )

    categories: dict[str, pd.Series] = {
        "tag": frame.tag.fillna("missing").astype(str),
        "salary_band": pd.Series(np.select(
            [salary.lt(47_000), salary.ge(49_000)],
            ["lt_47000", "ge_49000"], default="47000_48999",
        ), index=frame.index),
        "games_represented": pd.Series(np.select(
            [games.le(3), games.ge(5)], ["le_3", "ge_5"], default="4",
        ), index=frame.index),
        "largest_team_block": pd.Series(np.select(
            [largest.le(2), largest.ge(4)], ["le_2", "ge_4"], default="3",
        ), index=frame.index),
        "qb_stack_count": pd.Series(np.select(
            [stack.eq(0), stack.ge(2)], ["0", "ge_2"], default="1",
        ), index=frame.index),
        "bring_back_count": pd.Series(
            np.where(bring.ge(1), "ge_1", "0"), index=frame.index
        ),
        "p_line_tercile": tercile("p_line_percentile"),
        "sim_q99_tercile": tercile("sim_q99_percentile"),
        "ownership_sum_tercile": tercile("ownership_sum_percentile"),
    }
    return {
        field: {
            str(value): series.eq(value).to_numpy(bool)
            for value in sorted(series.dropna().unique(), key=str)
        }
        for field, series in categories.items()
    }


def _beam_subgroups(
    frame: pd.DataFrame,
    *,
    target: np.ndarray,
    population: np.ndarray,
    target_name: str,
    beam_width: int = 24,
    max_depth: int = 3,
) -> dict[str, Any]:
    target = np.asarray(target, dtype=bool)
    population = np.asarray(population, dtype=bool)
    if len(target) != len(frame) or len(population) != len(frame):
        raise ValueError("subgroup masks differ from corpus")
    population_rows = int(population.sum())
    positives = int((target & population).sum())
    if population_rows == 0 or positives == 0:
        return {
            "target": target_name,
            "population_rows": population_rows,
            "positive_rows": positives,
            "status": "not_estimable",
            "subgroups": [],
        }
    base_rate = positives / population_rows
    minimum_support = max(20, int(np.ceil(population_rows * 0.001)))
    conditions = _categorical_conditions(frame)
    atoms = [
        (field, value, mask)
        for field, values in conditions.items()
        for value, mask in values.items()
    ]

    def score(mask: np.ndarray, clauses: tuple[tuple[str, str], ...]) -> dict[str, Any] | None:
        matched = mask & population
        support = int(matched.sum())
        if support < minimum_support:
            return None
        hits = int((matched & target).sum())
        rate = hits / support
        if rate <= base_rate:
            return None
        return {
            "clauses": [f"{field}={value}" for field, value in clauses],
            "depth": len(clauses),
            "support": support,
            "support_fraction": support / population_rows,
            "positive_rows": hits,
            "positive_rate": rate,
            "base_rate": base_rate,
            "lift": rate / base_rate,
            "positive_coverage": hits / positives,
            "weighted_relative_accuracy": (
                support / population_rows * (rate - base_rate)
            ),
            "_mask": matched,
            "_fields": frozenset(field for field, _ in clauses),
        }

    beam: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    for field, value, mask in atoms:
        row = score(mask, ((field, value),))
        if row is not None:
            beam.append(row)
    beam.sort(key=lambda row: (-row["weighted_relative_accuracy"], -row["lift"], row["clauses"]))
    beam = beam[:beam_width]
    retained.extend(beam)
    for _depth in range(2, max_depth + 1):
        expanded: dict[tuple[str, ...], dict[str, Any]] = {}
        for parent in beam:
            for field, value, mask in atoms:
                if field in parent["_fields"]:
                    continue
                clauses = tuple(sorted([
                    *(tuple(clause.split("=", 1)) for clause in parent["clauses"]),
                    (field, value),
                ]))
                key = tuple(f"{left}={right}" for left, right in clauses)
                if key in expanded:
                    continue
                row = score(parent["_mask"] & mask, clauses)
                if row is not None:
                    expanded[key] = row
        beam = sorted(
            expanded.values(),
            key=lambda row: (
                -row["weighted_relative_accuracy"], -row["lift"], row["clauses"]
            ),
        )[:beam_width]
        retained.extend(beam)
    retained.sort(key=lambda row: (
        -row["weighted_relative_accuracy"], -row["lift"], row["clauses"]
    ))
    clean = []
    seen: set[tuple[str, ...]] = set()
    for row in retained:
        key = tuple(row["clauses"])
        if key in seen:
            continue
        seen.add(key)
        clean.append({
            field: value for field, value in row.items() if not field.startswith("_")
        })
        if len(clean) == 25:
            break
    return {
        "target": target_name,
        "population_rows": population_rows,
        "positive_rows": positives,
        "base_rate": base_rate,
        "minimum_support": minimum_support,
        "beam_width": beam_width,
        "maximum_depth": max_depth,
        "status": "descriptive_only",
        "subgroups": clean,
    }


def subgroup_discovery(frame: pd.DataFrame) -> dict[str, Any]:
    """Search plain-language conjunctions for unselected missed value."""
    selected = frame.selected.fillna(False).astype(bool).to_numpy()
    actual = pd.to_numeric(frame.actual_score, errors="raise")
    keys = [frame.panel_run_id, frame.season, frame.week]
    selected_best = actual.where(selected).groupby(keys, sort=False).transform("max")
    unselected = ~selected
    return {
        "unselected_ge200": _beam_subgroups(
            frame,
            target=actual.ge(HIGH_SCORE).to_numpy(),
            population=unselected,
            target_name="actual_score_ge_200_among_unselected_candidates",
        ),
        "unselected_outscored_selected_best": _beam_subgroups(
            frame,
            target=actual.gt(selected_best).to_numpy(),
            population=unselected,
            target_name="outscored_same_panel_slate_selected_best_among_unselected",
        ),
        "winning_player_slots_absent_from_pool": {
            "status": "covered_by_separate_player_level_bound",
            "evidence": (
                "construction_selection_regime_and_data_quality.data_quality"
                ".route_pool_admission_bound"
            ),
            "reason": (
                "Absent player-slots are outside the candidate-row grain and must "
                "not be forced into candidate conjunctions."
            ),
        },
    }


def _model_matrix(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    numeric = [
        "p_line", "sim_mean", "sim_sd", "sim_q50", "sim_q90", "sim_q99",
        "sim_rank_p_line", "salary", "games_represented", "largest_team_block",
        "qb_stack_count", "bring_back_count", "ownership_sum", "ownership_missing",
    ]
    data = pd.DataFrame(index=frame.index)
    for column in numeric:
        values = pd.to_numeric(frame[column], errors="coerce")
        median = values.median()
        data[column] = values.fillna(float(median) if pd.notna(median) else 0.0)
    tags = pd.get_dummies(
        frame.tag.fillna("missing").astype(str), prefix="tag", dtype=float
    )
    data = pd.concat([data, tags], axis=1)
    return data, numeric


def weak_model_diagnostic(frame: pd.DataFrame) -> dict[str, Any]:
    """Read a deliberately weak tree model; never return a deployable artifact."""
    matrix, numeric = _model_matrix(frame)
    labels = pd.to_numeric(frame.actual_score, errors="raise").ge(HIGH_SCORE).to_numpy()
    group = frame.season.astype(str) + "-" + frame.week.astype(str).str.zfill(2)
    unique_groups = sorted(group.unique())
    test_groups = {
        value for index, value in enumerate(unique_groups) if index % 5 == 4
    }
    test = group.isin(test_groups).to_numpy()
    train = ~test
    if labels[train].sum() == 0 or labels[test].sum() == 0:
        return {
            "status": "not_estimable",
            "reason": "deterministic slate holdout lacks both outcome classes",
        }
    model = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=120,
        learning_rate=0.05,
        max_depth=3,
        num_leaves=7,
        min_child_samples=max(100, int(train.sum() * 0.002)),
        reg_lambda=2.0,
        random_state=CORPUS_SEED,
        deterministic=True,
        force_col_wise=True,
        verbosity=-1,
        n_jobs=-1,
    )
    model.fit(matrix.loc[train], labels[train])
    probability = model.predict_proba(matrix.loc[test])[:, 1]
    auc = float(roc_auc_score(labels[test], probability))
    average_precision = float(average_precision_score(labels[test], probability))

    test_positions = np.flatnonzero(test)
    if len(test_positions) > 50_000:
        rng = np.random.default_rng(CORPUS_SEED)
        explain_positions = np.sort(rng.choice(
            test_positions, size=50_000, replace=False
        ))
    else:
        explain_positions = test_positions
    explain = matrix.iloc[explain_positions]
    contribution = model.booster_.predict(explain, pred_contrib=True)
    contribution = np.asarray(contribution, dtype=float)[:, :-1]
    importance = []
    for index, column in enumerate(matrix.columns):
        shap_values = pd.Series(contribution[:, index])
        feature_values = pd.Series(explain[column].to_numpy(float))
        direction = (
            _finite(shap_values.corr(feature_values, method="spearman"))
            if shap_values.nunique() > 1 and feature_values.nunique() > 1
            else None
        )
        importance.append({
            "feature": str(column),
            "mean_absolute_tree_shap": float(np.abs(contribution[:, index]).mean()),
            "shap_value_direction_correlation": direction,
        })
    importance.sort(key=lambda row: -row["mean_absolute_tree_shap"])

    # Pairwise holdout permutation excess is used in place of a heavyweight
    # SHAP-interaction dependency.  Positive excess means the joint loss is
    # larger than the two marginal losses added together.
    baseline_auc = auc
    rng = np.random.default_rng(CORPUS_SEED)
    permutation = rng.permutation(len(probability))
    top_features = [row["feature"] for row in importance[:8]]
    holdout = matrix.loc[test].reset_index(drop=True)

    def permuted_auc(columns: Sequence[str]) -> float:
        changed = holdout.copy()
        for column in columns:
            changed[column] = changed[column].to_numpy()[permutation]
        prediction = model.predict_proba(changed)[:, 1]
        return float(roc_auc_score(labels[test], prediction))

    marginal_drop = {
        column: baseline_auc - permuted_auc([column]) for column in top_features
    }
    interactions = []
    for left, right in combinations(top_features, 2):
        joint_drop = baseline_auc - permuted_auc([left, right])
        interactions.append({
            "left": left,
            "right": right,
            "joint_auc_drop": joint_drop,
            "interaction_excess_over_marginal_drops": (
                joint_drop - marginal_drop[left] - marginal_drop[right]
            ),
        })
    interactions.sort(
        key=lambda row: -abs(row["interaction_excess_over_marginal_drops"])
    )

    holdout_rows = frame.loc[test].copy()
    holdout_rows["descriptive_probability"] = probability
    false_positive = holdout_rows[
        holdout_rows.actual_score.lt(180)
    ].nlargest(20, "descriptive_probability")
    false_negative = holdout_rows[
        holdout_rows.actual_score.ge(HIGH_SCORE)
    ].nsmallest(20, "descriptive_probability")

    def mistakes(rows: pd.DataFrame) -> list[dict[str, Any]]:
        return [{
            "panel_run_id": str(row.panel_run_id),
            "season": int(row.season),
            "week": int(row.week),
            "cand_ix": int(row.cand_ix),
            "players": str(row.players),
            "tag": str(row.tag),
            "selected": bool(row.selected),
            "actual_score": float(row.actual_score),
            "descriptive_probability": float(row.descriptive_probability),
        } for row in rows.itertuples(index=False)]

    return {
        "status": "outcome_viewed_descriptive_only",
        "target": "actual_score_ge_200",
        "model": "LightGBM shallow trees; max_depth=3; no artifact retained",
        "training_rows": int(train.sum()),
        "holdout_rows": int(test.sum()),
        "holdout_unit": "entire season-week groups, deterministic every fifth slate",
        "holdout_prevalence": float(labels[test].mean()),
        "holdout_roc_auc": auc,
        "holdout_average_precision": average_precision,
        "tree_shap_sample_rows": len(explain_positions),
        "tree_shap_feature_importance": importance,
        "pairwise_permutation_interactions": interactions,
        "confidently_wrong": {
            "high_belief_actual_below_180": mistakes(false_positive),
            "low_belief_actual_at_least_200": mistakes(false_negative),
        },
        "method_boundary": (
            "Native LightGBM TreeSHAP is used for main effects. Pairwise "
            "permutation excess substitutes for SHAP interaction tensors so the "
            "existing image needs no SHAP/Numba dependency."
        ),
    }


def co_selection_graph_diagnostic(
    frame: pd.DataFrame,
    players: pd.DataFrame,
) -> dict[str, Any]:
    """Compare all-candidate and high-score player co-occurrence graphs."""
    pair_all: Counter[tuple[str, str]] = Counter()
    pair_high: Counter[tuple[str, str]] = Counter()
    player_all: Counter[str] = Counter()
    player_high: Counter[str] = Counter()
    player_high_panels: dict[str, set[str]] = {}
    player_high_scores: dict[str, list[float]] = {}
    high_rows = 0
    for row in frame.itertuples(index=False):
        roster = tuple(sorted(_roster(row.players)))
        is_high = float(row.actual_score) >= HIGH_SCORE
        high_rows += int(is_high)
        player_all.update(roster)
        pair_all.update(combinations(roster, 2))
        if is_high:
            player_high.update(roster)
            pair_high.update(combinations(roster, 2))
            for player_id in roster:
                player_high_panels.setdefault(player_id, set()).add(str(row.panel_run_id))
                player_high_scores.setdefault(player_id, []).append(float(row.actual_score))
    baseline = high_rows / len(frame) if len(frame) else 0.0
    minimum_pair_appearances = max(10, int(np.ceil(len(frame) * 0.00005)))
    pair_rows = []
    for pair, total in pair_all.items():
        high = pair_high[pair]
        if total < minimum_pair_appearances or high < 2:
            continue
        smoothed_rate = (high + 1) / (total + 2)
        lift = smoothed_rate / baseline if baseline else np.nan
        pair_rows.append({
            "players": list(pair),
            "candidate_appearances": int(total),
            "high_score_appearances": int(high),
            "smoothed_high_score_rate": smoothed_rate,
            "lift_over_candidate_base_rate": _finite(lift),
            "priority_score": _finite(np.log2(max(lift, 1e-12)) * np.sqrt(high)),
        })
    pair_rows.sort(key=lambda row: (
        -(row["priority_score"] if row["priority_score"] is not None else -np.inf),
        -row["high_score_appearances"], row["players"],
    ))

    all_graph = nx.Graph()
    for pair, total in pair_all.items():
        if total >= minimum_pair_appearances:
            all_graph.add_edge(*pair, weight=float(total))
    high_graph = nx.Graph()
    for pair, count in pair_high.items():
        if count >= 2:
            high_graph.add_edge(*pair, weight=float(count))

    def communities(graph: nx.Graph) -> dict[str, Any]:
        if graph.number_of_edges() == 0:
            return {"nodes": graph.number_of_nodes(), "edges": 0, "communities": 0}
        groups = nx.community.louvain_communities(
            graph, weight="weight", seed=CORPUS_SEED
        )
        return {
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "communities": len(groups),
            "community_sizes": sorted((len(group) for group in groups), reverse=True),
            "modularity": float(nx.community.modularity(graph, groups, weight="weight")),
        }

    names = {
        str(row.id): str(getattr(row, "name", row.id))
        for row in players.drop_duplicates("id").itertuples(index=False)
    }
    if high_graph.number_of_nodes() > 2:
        sample = min(200, high_graph.number_of_nodes())
        betweenness = nx.betweenness_centrality(
            high_graph, k=sample, normalized=True, weight=None, seed=CORPUS_SEED
        )
    else:
        betweenness = {node: 0.0 for node in high_graph}
    bridge_rows = []
    for player_id, high in player_high.items():
        peers = len(set(high_graph.neighbors(player_id))) if player_id in high_graph else 0
        bridge_rows.append({
            "player_id": player_id,
            "name": names.get(player_id, player_id),
            "candidate_appearances": int(player_all[player_id]),
            "high_score_appearances": int(high),
            "distinct_high_score_peers": peers,
            "distinct_high_score_panels": len(player_high_panels.get(player_id, set())),
            "mean_high_score": float(np.mean(player_high_scores[player_id])),
            "approximate_high_graph_betweenness": float(betweenness.get(player_id, 0.0)),
        })
    bridge_rows.sort(key=lambda row: (
        -row["approximate_high_graph_betweenness"],
        -row["distinct_high_score_peers"],
        -row["high_score_appearances"],
        row["player_id"],
    ))
    return {
        "status": "outcome_viewed_descriptive_only",
        "candidate_appearances": len(frame),
        "high_score_appearances": high_rows,
        "high_score_base_rate": baseline,
        "minimum_pair_appearances": minimum_pair_appearances,
        "all_candidate_graph": communities(all_graph),
        "high_score_graph": communities(high_graph),
        "high_score_pair_lift": pair_rows[:50],
        "high_score_bridge_players": bridge_rows[:50],
        "unit_warning": (
            "Rows are candidate appearances across launched panels; repeated "
            "rosters measure generator/selector exposure and are not deduplicated."
        ),
    }


def lineup_embedding_diagnostic(frame: pd.DataFrame) -> dict[str, Any]:
    """Build a deterministic sparse two-dimensional map of lineup space."""
    high = frame.actual_score.ge(210)
    high_frame = frame[high]
    if len(high_frame) >= EMBEDDING_POINT_LIMIT:
        sample = high_frame.nlargest(EMBEDDING_POINT_LIMIT, "actual_score")
    else:
        remaining = frame[~high]
        take = min(EMBEDDING_POINT_LIMIT - len(high_frame), len(remaining))
        sample = pd.concat([
            high_frame,
            remaining.sample(n=take, random_state=CORPUS_SEED) if take else remaining.iloc[:0],
        ]).sort_values(
            ["panel_run_id", "season", "week", "cand_ix"], kind="stable"
        )
    rosters = [_roster(value) for value in sample.players]
    player_ids = sorted({player for roster in rosters for player in roster})
    column = {player: index for index, player in enumerate(player_ids)}
    row_index = np.repeat(np.arange(len(sample)), 9)
    column_index = np.asarray([
        column[player] for roster in rosters for player in roster
    ], dtype=int)
    incidence = sparse.csr_matrix(
        (np.ones(len(row_index)), (row_index, column_index)),
        shape=(len(sample), len(player_ids)),
    )
    structural_fields = [
        "salary", "p_line", "sim_mean", "sim_sd", "sim_q99",
        "games_represented", "largest_team_block", "qb_stack_count",
        "bring_back_count", "ownership_sum",
    ]
    structural = np.column_stack([
        pd.to_numeric(sample[field], errors="coerce").to_numpy(float)
        for field in structural_fields
    ])
    medians = np.nanmedian(structural, axis=0)
    missing = np.where(~np.isfinite(structural))
    structural[missing] = medians[missing[1]]
    scale = np.std(structural, axis=0)
    scale[scale == 0] = 1.0
    structural = (structural - np.mean(structural, axis=0)) / scale
    matrix = sparse.hstack([
        incidence,
        sparse.csr_matrix(structural * 0.5),
    ], format="csr")
    embedding = TruncatedSVD(
        n_components=2, n_iter=7, random_state=CORPUS_SEED
    ).fit_transform(matrix)
    labels = sample.actual_score.ge(HIGH_SCORE).to_numpy(bool)
    local_enrichment = None
    centroid_separation = None
    if len(sample) > 25 and labels.any() and (~labels).any():
        neighbors = NearestNeighbors(n_neighbors=min(21, len(sample))).fit(embedding)
        indices = neighbors.kneighbors(return_distance=False)
        local_rate = labels[indices[:, 1:]].mean(axis=1)
        base = float(labels.mean())
        local_enrichment = {
            "base_rate": base,
            "mean_local_rate_for_high_scores": float(local_rate[labels].mean()),
            "mean_local_rate_for_other_scores": float(local_rate[~labels].mean()),
            "high_score_local_enrichment": (
                float(local_rate[labels].mean() / base) if base else None
            ),
        }
        high_center = embedding[labels].mean(axis=0)
        low_center = embedding[~labels].mean(axis=0)
        within = np.mean(np.linalg.norm(embedding - embedding.mean(axis=0), axis=1))
        centroid_separation = (
            float(np.linalg.norm(high_center - low_center) / within)
            if within > 0 else None
        )
    points = []
    for coordinate, row in zip(embedding, sample.itertuples(index=False), strict=True):
        points.append({
            "panel_run_id": str(row.panel_run_id),
            "season": int(row.season),
            "week": int(row.week),
            "cand_ix": int(row.cand_ix),
            "x": float(coordinate[0]),
            "y": float(coordinate[1]),
            "actual_score": float(row.actual_score),
            "selected": bool(row.selected),
            "tag": str(row.tag),
        })
    return {
        "status": "outcome_viewed_descriptive_only",
        "method": "sparse player-incidence plus structure; deterministic TruncatedSVD",
        "method_boundary": (
            "This is the dependency-lean registered substitute for UMAP. It "
            "preserves a reproducible global map but not UMAP's local geometry."
        ),
        "candidate_appearances": len(frame),
        "sample_rows": len(sample),
        "all_score_ge210_rows_included": len(high_frame) < EMBEDDING_POINT_LIMIT,
        "player_dimensions": len(player_ids),
        "structural_fields": structural_fields,
        "high_score_local_concentration": local_enrichment,
        "normalized_high_vs_other_centroid_separation": centroid_separation,
        "points": points,
    }


def _single_changepoint(data: pd.DataFrame, metric: str) -> dict[str, Any]:
    values = pd.to_numeric(data[metric], errors="coerce").to_numpy(float)
    valid = np.isfinite(values)
    data = data.loc[valid].reset_index(drop=True)
    values = values[valid]
    minimum_segment = max(8, min(16, len(values) // 4))
    if len(values) < minimum_segment * 2:
        return {"status": "not_estimable", "observations": len(values)}
    baseline_sse = float(np.square(values - values.mean()).sum())
    candidates = []
    for split in range(minimum_segment, len(values) - minimum_segment + 1):
        left, right = values[:split], values[split:]
        sse = float(
            np.square(left - left.mean()).sum()
            + np.square(right - right.mean()).sum()
        )
        candidates.append((sse, split, float(left.mean()), float(right.mean())))
    sse, split, before, after = min(candidates, key=lambda row: (row[0], row[1]))
    marker = data.iloc[split]
    return {
        "status": "descriptive_single_break",
        "observations": len(values),
        "minimum_segment": minimum_segment,
        "first_post_break": {"season": int(marker.season), "week": int(marker.week)},
        "mean_before": before,
        "mean_after": after,
        "mean_shift": after - before,
        "sse_without_break": baseline_sse,
        "sse_with_break": sse,
        "relative_sse_reduction": (
            (baseline_sse - sse) / baseline_sse if baseline_sse > 0 else None
        ),
    }


def changepoint_diagnostic(frame: pd.DataFrame) -> dict[str, Any]:
    """Locate descriptive breaks in candidate/selection opportunity series."""
    selected = frame.selected.fillna(False).astype(bool)
    grouped = frame.groupby(
        ["panel_run_id", "season", "week"], sort=True
    )
    weekly = grouped.agg(candidate_oracle=("actual_score", "max")).reset_index()
    selected_best = frame[selected].groupby(
        ["panel_run_id", "season", "week"], sort=True
    ).actual_score.max().rename("selected_best").reset_index()
    weekly = weekly.merge(
        selected_best,
        on=["panel_run_id", "season", "week"],
        how="left",
        validate="one_to_one",
    )
    exceed = frame.assign(
        _exceed=pd.to_numeric(frame.actual_score, errors="raise").gt(
            pd.to_numeric(frame.sim_q99, errors="coerce")
        )
    ).groupby(
        ["panel_run_id", "season", "week"], sort=True
    )._exceed.mean().rename("calibration_exceedance_q99").reset_index()
    weekly = weekly.merge(
        exceed, on=["panel_run_id", "season", "week"], validate="one_to_one"
    )
    weekly["selection_regret"] = weekly.candidate_oracle - weekly.selected_best
    aggregate = weekly.groupby(["season", "week"], sort=True).agg(
        weekly_max=("selected_best", "mean"),
        candidate_oracle=("candidate_oracle", "mean"),
        selection_regret=("selection_regret", "mean"),
        calibration_exceedance_q99=("calibration_exceedance_q99", "mean"),
    ).reset_index()
    metrics = (
        "weekly_max", "candidate_oracle", "selection_regret",
        "calibration_exceedance_q99",
    )
    return {
        "status": "outcome_viewed_descriptive_only",
        "aggregation": "equal-weight mean across the fourteen launched panels per slate",
        "metrics": {
            metric: _single_changepoint(aggregate, metric) for metric in metrics
        },
        "series": aggregate.to_dict("records"),
        "attribution_boundary": (
            "Historical replays apply each panel's code to every season. A break "
            "can identify football/data-time drift, but cannot be attributed to a "
            "calendar-time code deployment without separate evidence."
        ),
    }


def corpus_understanding_diagnostics(
    candidates: pd.DataFrame,
    players: pd.DataFrame,
) -> dict[str, Any]:
    """Run all five registered corpus-understanding views."""
    frame = _candidate_structure(candidates, players)
    return {
        "contract": {
            "unit": "candidate appearances across frozen complete panels",
            "candidate_rows": len(frame),
            "unique_panel_slate_rosters": int(frame[[
                "panel_run_id", "season", "week", "players"
            ]].drop_duplicates().shape[0]),
            "panels": sorted(frame.panel_run_id.astype(str).unique()),
            "use_restriction": (
                "Outcome-viewed and hypothesis-generating only. These diagnostics "
                "may not promote, retune, reopen, or relabel any arm; any lead "
                "requires a new prospective outcome-unseen protocol."
            ),
        },
        "subgroup_discovery": subgroup_discovery(frame),
        "weak_interpretable_model": weak_model_diagnostic(frame),
        "co_selection_graphs": co_selection_graph_diagnostic(frame, players),
        "lineup_space_embedding": lineup_embedding_diagnostic(frame),
        "changepoints": changepoint_diagnostic(frame),
    }


__all__ = [
    "changepoint_diagnostic",
    "co_selection_graph_diagnostic",
    "corpus_understanding_diagnostics",
    "lineup_embedding_diagnostic",
    "subgroup_discovery",
    "weak_model_diagnostic",
]
