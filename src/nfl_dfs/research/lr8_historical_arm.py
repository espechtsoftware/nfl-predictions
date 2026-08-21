"""Default-off mechanics for the LR8 historical residual-column arm.

The module is deliberately transport-free.  It can fit the fixed soft lineup-
anatomy tie-break on an explicitly earlier period, construct matched-budget
cross-fit books from simulated worlds, and replay a frozen later-period score
contract.  It does not query a warehouse, read object storage, launch cloud
work, or alter the production optimizer.

LR8 means *up to eight replacements in each construction fold*.  Fold A and
Fold B are independent matched-budget treatments and receive equal weight;
it never means four replacements per fold or eight combined.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
import json
import math
import re
from typing import Any, Final

import numpy as np
import pulp
from sklearn.linear_model import LogisticRegression

from nfl_dfs.optimizer.lineup import add_classic_lineup_constraints, select_tail_entries
from nfl_dfs.research import residual_world_columns as rw


PROTOCOL_ID: Final = "20260820-lr8-historical-residual-columns-v1"
PROTOCOL_STATUS: Final = "MECHANICS_ONLY_NOT_LAUNCH_READY"
TRAINING_SEASONS: Final = (2019, 2021)
TRAINING_CELLS: Final = tuple(
    [(2019, week) for week in range(1, 18)]
    + [(2021, week) for week in range(1, 19)]
)
EVALUATION_SEASONS: Final = (2023, 2024, 2025)
EVALUATION_WEEKS: Final = tuple(range(1, 19))
ENTRIES: Final = 80
K_MAX_PER_FOLD: Final = 8
CONTROL_LINE_DK: Final = 194
MARGINAL_THRESHOLDS_DK: Final = (210, 200, 194, 187)
MARGINAL_THRESHOLDS_MICRO: Final = tuple(
    value * rw.MICRO_DK_SCALE for value in MARGINAL_THRESHOLDS_DK
)
BOOK_MAX_CAP_DK: Final = 210
BOOK_MAX_CAP_MICRO: Final = BOOK_MAX_CAP_DK * rw.MICRO_DK_SCALE
ANATOMY_LABEL_DK: Final = 200
ANATOMY_LABEL_MICRO: Final = ANATOMY_LABEL_DK * rw.MICRO_DK_SCALE
ANATOMY_MODEL_VERSION: Final = "lr8-soft-anatomy-logistic-v1"
ANATOMY_LINEAR_SCALE: Final = 1_000_000
ANATOMY_LINEAR_ROUNDING: Final = "decimal-round-half-even-v1"
ANATOMY_FEATURE_ABS_UPPER: Final = (
    50_000,  # salary_used
    9,  # games_represented
    9,  # teams_represented
    8,  # max_from_one_game (at least two games are required)
    8,  # max_from_one_team
    6,  # qb_wrte_partners (four WR plus two TE are shape-legal)
    7,  # bring_back_skill_players
    3,  # rb_against_dst_count
    3,  # same_team_rb_pairs
    1,  # naked_qb
    1,  # exact_one_qb_partner
    50_000,  # qb_salary
    50_000,  # rb_salary
    50_000,  # wr_salary
    50_000,  # te_salary
    50_000,  # dst_salary
)
FOLD_WEIGHT: Final = 0.5
MIN_SELECTED_MEAN_DK: Final = 194
MIN_CANDIDATE_CEILING_DK: Final = 205
MAX_CANDIDATE_SELECTION_GAP_DK: Final = 5
FOLD_SPECS: Final = rw.FOLD_SPECS
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_POSITIVE_CANONICAL_DIGITS: Final = re.compile(r"[1-9][0-9]*")

ANATOMY_FEATURES: Final = (
    "salary_used",
    "games_represented",
    "teams_represented",
    "max_from_one_game",
    "max_from_one_team",
    "qb_wrte_partners",
    "bring_back_skill_players",
    "rb_against_dst_count",
    "same_team_rb_pairs",
    "naked_qb",
    "exact_one_qb_partner",
    "qb_salary",
    "rb_salary",
    "wr_salary",
    "te_salary",
    "dst_salary",
)


class LR8Error(ValueError):
    """Fail-closed LR8 contract violation."""


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json(value)).hexdigest()


def _array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    digest = sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(canonical_json(list(array.shape)))
    digest.update(b"\0")
    if array.size:
        digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise LR8Error(f"{label} must be an exact integer")
    result = int(value)
    if result < minimum:
        raise LR8Error(f"{label} must be >= {minimum}")
    return result


def _json_number(value: object, *, label: str) -> float:
    """Return a finite canonical-JSON number, rejecting bools and coercions."""
    if type(value) not in (int, float):
        raise LR8Error(f"{label} must be a finite non-bool JSON number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise LR8Error(
            f"{label} must be a finite non-bool JSON number"
        ) from exc
    if not math.isfinite(result):
        raise LR8Error(f"{label} must be a finite non-bool JSON number")
    return result


def _json_int(value: object, *, label: str, minimum: int = 0) -> int:
    """Return an exact canonical-JSON integer, rejecting bools and coercions."""
    if type(value) is not int or value < minimum:
        raise LR8Error(f"{label} must be an exact non-bool JSON integer")
    return value


def _json_signed_int(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise LR8Error(f"{label} must be an exact non-bool JSON integer")
    return value


def _quantize_anatomy_linear_law(
    means: Sequence[float],
    scales: Sequence[float],
    coefficients: Sequence[float],
    intercept: float,
) -> tuple[tuple[int, ...], int, int]:
    """Freeze the standardized logit as one exact raw-feature integer tier."""
    if not (
        len(means) == len(scales) == len(coefficients) == len(ANATOMY_FEATURES)
        == len(ANATOMY_FEATURE_ABS_UPPER)
    ):
        raise LR8Error("soft-anatomy linear law width differs")
    with localcontext() as context:
        context.prec = 80
        decimal_means = tuple(Decimal(str(float(value))) for value in means)
        decimal_scales = tuple(Decimal(str(float(value))) for value in scales)
        decimal_coefficients = tuple(
            Decimal(str(float(value))) for value in coefficients
        )
        if any(
            not value.is_finite() for value in (
                *decimal_means, *decimal_scales, *decimal_coefficients,
                Decimal(str(float(intercept))),
            )
        ) or any(value <= 0 for value in decimal_scales):
            raise LR8Error("soft-anatomy linear law is nonfinite")
        raw_weights = tuple(
            coefficient / scale
            for coefficient, scale in zip(
                decimal_coefficients, decimal_scales, strict=True
            )
        )
        raw_intercept = Decimal(str(float(intercept))) - sum(
            weight * mean
            for weight, mean in zip(raw_weights, decimal_means, strict=True)
        )
        scale_value = Decimal(ANATOMY_LINEAR_SCALE)
        unit = Decimal(1)
        weight_units = tuple(int((weight * scale_value).quantize(
            unit, rounding=ROUND_HALF_EVEN
        )) for weight in raw_weights)
        intercept_units = int((raw_intercept * scale_value).quantize(
            unit, rounding=ROUND_HALF_EVEN
        ))
    worst_case = abs(intercept_units) + sum(
        abs(weight) * bound
        for weight, bound in zip(
            weight_units, ANATOMY_FEATURE_ABS_UPPER, strict=True
        )
    )
    if worst_case > rw.CBC_EXACT_INTEGER_MAX:
        raise LR8Error("soft-anatomy fixed-point tier exceeds exact CBC range")
    return weight_units, intercept_units, worst_case


def _players(
    values: Sequence[rw.PlayerSpec | Mapping[str, object]],
) -> tuple[rw.PlayerSpec, ...]:
    if isinstance(values, (str, bytes)):
        raise LR8Error("player catalog must be a sequence")
    try:
        rows = tuple(
            value if isinstance(value, rw.PlayerSpec)
            else rw.PlayerSpec.from_mapping(value)
            for value in values
        )
    except (KeyError, TypeError, rw.ResidualWorldError) as exc:
        raise LR8Error("player catalog is malformed") from exc
    if not rows or len({row.player_id for row in rows}) != len(rows):
        raise LR8Error("player catalog is empty or repeats ids")
    if any(row.salary <= 0 for row in rows):
        raise LR8Error("player salaries must be positive")
    return rows


def _identity(value: Sequence[object]) -> tuple[str, ...]:
    try:
        return rw.canonical_identity(value)
    except rw.ResidualWorldError as exc:
        raise LR8Error(str(exc)) from exc


def _worlds(values: Sequence[rw.WorldId]) -> tuple[rw.WorldId, ...]:
    worlds = tuple(values)
    if not worlds or any(not isinstance(world, rw.WorldId) for world in worlds):
        raise LR8Error("world identities are empty or malformed")
    if len(set(worlds)) != len(worlds):
        raise LR8Error("world identities repeat")
    counts: dict[str, list[int]] = {block: [] for block in rw.WORLD_BLOCKS}
    for world in worlds:
        counts[world.block].append(world.index)
    per_block = {block: len(indices) for block, indices in counts.items()}
    if len(set(per_block.values())) != 1 or next(iter(per_block.values())) <= 0:
        raise LR8Error("every R0..R4 block must have the same positive world count")
    expected = tuple(
        rw.WorldId(block, index)
        for block in rw.WORLD_BLOCKS
        for index in range(next(iter(per_block.values())))
    )
    if worlds != expected:
        raise LR8Error("world identities are not in canonical block/index order")
    return worlds


def audit_dk_classic_identity(
    players: Sequence[rw.PlayerSpec | Mapping[str, object]],
    roster: Sequence[object],
) -> tuple[str, ...]:
    """Audit only DraftKings NFL Classic legality, with no house rules."""
    rows = _players(players)
    identity = _identity(roster)
    by_id = {player.player_id: player for player in rows}
    if not set(identity) <= set(by_id):
        raise LR8Error("lineup references an unknown player")
    chosen = [by_id[player_id] for player_id in identity]
    counts = Counter(player.position for player in chosen)
    if not (
        counts["QB"] == 1
        and counts["DST"] == 1
        and 2 <= counts["RB"] <= 3
        and 3 <= counts["WR"] <= 4
        and 1 <= counts["TE"] <= 2
        and sum(counts.values()) == 9
    ):
        raise LR8Error("lineup has an illegal DK Classic position shape")
    salary = sum(player.salary for player in chosen)
    if not 0 < salary <= rw.SALARY_CAP:
        raise LR8Error("lineup exceeds the DK salary cap")
    team_counts = Counter(player.team for player in chosen)
    if max(team_counts.values()) > rw.MAX_FROM_TEAM:
        raise LR8Error("lineup exceeds the DK team cap")
    if len({player.game_id for player in chosen}) < rw.MIN_GAMES:
        raise LR8Error("lineup uses fewer than two games")
    return identity


def build_dk_classic_model(
    players: Sequence[rw.PlayerSpec | Mapping[str, object]],
    *,
    name: str = "lr8_dk_classic_only",
    forbidden_rosters: Sequence[Sequence[object]] = (),
) -> rw.LegalLineupModel:
    """Build the relaxed pricing domain through the shared constraint seam."""
    rows = _players(players)
    forbidden = tuple(_identity(roster) for roster in forbidden_rosters)
    known = {player.player_id for player in rows}
    if len(set(forbidden)) != len(forbidden) or any(
        not set(roster) <= known for roster in forbidden
    ):
        raise LR8Error("forbidden roster set is malformed")
    problem = pulp.LpProblem(name, pulp.LpMaximize)
    decision = {
        player.player_id: pulp.LpVariable(f"x_{index:04d}", cat="Binary")
        for index, player in enumerate(sorted(rows, key=lambda row: row.player_id))
    }
    mappings = [{
        "id": player.player_id,
        "pos": player.position,
        "team": player.team,
        "opp": player.opponent,
        "game_id": player.game_id,
        "salary": player.salary,
    } for player in rows]
    add_classic_lineup_constraints(
        problem,
        decision,
        mappings,
        budget=rw.SALARY_CAP,
        banned_lineups=[frozenset(roster) for roster in forbidden],
        stack=None,
        max_overlap=rw.ROSTER_SIZE - 1,
        punt_max_salary=None,
        punt_min=0,
        game_lock=None,
        min_salary=0,
        max_salary=None,
        max_per_game=0,
        env={},
    )
    problem += pulp.lpSum([])
    return rw.LegalLineupModel(problem=problem, players=rows, decision=decision)


def lineup_anatomy(
    players: Sequence[rw.PlayerSpec | Mapping[str, object]],
    roster: Sequence[object],
) -> tuple[float, ...]:
    """Return the fixed pre-lock anatomy vector; it is never a hard rule."""
    rows = _players(players)
    identity = audit_dk_classic_identity(rows, roster)
    by_id = {player.player_id: player for player in rows}
    chosen = [by_id[player_id] for player_id in identity]
    qb = next(player for player in chosen if player.position == "QB")
    dst = next(player for player in chosen if player.position == "DST")
    qb_partners = sum(
        player.team == qb.team and player.position in {"WR", "TE"}
        for player in chosen
    )
    bring_back = sum(
        player.team == qb.opponent and player.position in {"RB", "WR", "TE"}
        for player in chosen
    )
    rb_against_dst = sum(
        player.position == "RB" and player.team == dst.opponent
        for player in chosen
    )
    rb_teams = Counter(
        player.team for player in chosen if player.position == "RB"
    )
    same_team_rb_pairs = sum(count * (count - 1) // 2 for count in rb_teams.values())
    game_counts = Counter(player.game_id for player in chosen)
    team_counts = Counter(player.team for player in chosen)
    salary_by_position = {
        position: sum(
            player.salary for player in chosen if player.position == position
        )
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    values = (
        sum(player.salary for player in chosen),
        len(game_counts),
        len(team_counts),
        max(game_counts.values()),
        max(team_counts.values()),
        qb_partners,
        bring_back,
        rb_against_dst,
        same_team_rb_pairs,
        int(qb_partners == 0),
        int(qb_partners == 1),
        salary_by_position["QB"],
        salary_by_position["RB"],
        salary_by_position["WR"],
        salary_by_position["TE"],
        salary_by_position["DST"],
    )
    if len(values) != len(ANATOMY_FEATURES):
        raise AssertionError("LR8 anatomy feature width changed")
    return tuple(float(value) for value in values)


@dataclass(frozen=True, slots=True)
class AnatomyTrainingRow:
    season: int
    week: int
    features: tuple[float, ...]
    realized_total_micro: int


def _artifact_payload(artifact: Mapping[str, object]) -> dict[str, object]:
    return {key: value for key, value in artifact.items() if key != "artifact_sha256"}


def fit_soft_anatomy_law(
    rows: Sequence[AnatomyTrainingRow],
) -> dict[str, object]:
    """Fit the sole fixed earlier-period 200+ soft tie-break model."""
    examples = tuple(rows)
    if not examples:
        raise LR8Error("soft-anatomy training rows are empty")
    seasons = tuple(sorted({
        _exact_int(row.season, label="training season") for row in examples
    }))
    if seasons != TRAINING_SEASONS:
        raise LR8Error("soft anatomy must train on exactly seasons 2019 and 2021")
    x = np.asarray([row.features for row in examples], dtype=np.float64)
    if x.shape != (len(examples), len(ANATOMY_FEATURES)) or not np.isfinite(x).all():
        raise LR8Error("soft-anatomy features are malformed")
    cells = [(
        _exact_int(row.season, label="training season"),
        _exact_int(row.week, label="training week", minimum=1),
    ) for row in examples]
    if any(week > 18 for _, week in cells):
        raise LR8Error("training week is outside 1..18")
    if set(cells) != set(TRAINING_CELLS):
        raise LR8Error(
            "soft anatomy must cover exact 2019 Weeks 1..17 and 2021 Weeks 1..18"
        )
    labels = np.asarray([
        int(_exact_int(
            row.realized_total_micro, label="training realized total"
        ) >= ANATOMY_LABEL_MICRO)
        for row in examples
    ], dtype=np.int8)
    if set(labels.tolist()) != {0, 1}:
        raise LR8Error("soft-anatomy training requires both 200+ label classes")
    cell_counts = Counter(cells)
    weights = np.asarray([1.0 / cell_counts[cell] for cell in cells], dtype=np.float64)
    weights *= len(weights) / weights.sum()
    # The estimator and its standardization share the same equal-cell law.
    # Without weighted moments, a large slate would still dominate the
    # coordinate system even though the likelihood weights each slate equally.
    means = np.average(x, axis=0, weights=weights)
    variances = np.average((x - means) ** 2, axis=0, weights=weights)
    scales = np.sqrt(variances)
    scales = np.where(scales > 0.0, scales, 1.0)
    standardized = (x - means) / scales
    model = LogisticRegression(
        C=1.0,
        solver="lbfgs",
        class_weight=None,
        max_iter=2000,
        fit_intercept=True,
    )
    model.fit(standardized, labels, sample_weight=weights)
    if model.n_iter_.shape != (1,) or int(model.n_iter_[0]) >= 2000:
        raise LR8Error("soft-anatomy fixed fit did not converge")
    coefficient_values = model.coef_[0].astype(float).tolist()
    intercept_value = float(model.intercept_[0])
    operative_weights, operative_intercept, operative_bound = (
        _quantize_anatomy_linear_law(
            means.tolist(),
            scales.tolist(),
            coefficient_values,
            intercept_value,
        )
    )
    artifact: dict[str, object] = {
        "version": ANATOMY_MODEL_VERSION,
        "training_seasons": list(TRAINING_SEASONS),
        "evaluation_seasons_forbidden_during_fit": list(EVALUATION_SEASONS),
        "target": "realized_total_dk_gte_200",
        "feature_columns": list(ANATOMY_FEATURES),
        "imputation": "none_finite_required",
        "standardize_means": means.tolist(),
        "standardize_scales": scales.tolist(),
        "coefficients": coefficient_values,
        "intercept": intercept_value,
        "operative_tier": "raw_feature_linear_predictor_fixed_point",
        "operative_linear_scale": ANATOMY_LINEAR_SCALE,
        "operative_rounding": ANATOMY_LINEAR_ROUNDING,
        "operative_raw_weight_units": list(operative_weights),
        "operative_intercept_units": operative_intercept,
        "operative_worst_case_abs_units": operative_bound,
        "c": 1.0,
        "solver": "lbfgs",
        "class_weight": None,
        "max_iter": 2000,
        "sample_weight": "equal_total_weight_per_season_week",
        "training_rows": len(examples),
        "training_cells": len(cell_counts),
        "training_positive_rows": int(labels.sum()),
        "feature_sweep": False,
        "hyperparameter_sweep": False,
        "threshold_sweep": False,
        "sigmoid_probability_operative": False,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "production_change_licensed": False,
    }
    artifact["artifact_sha256"] = canonical_sha256(artifact)
    return artifact


def validate_soft_anatomy_artifact(
    value: Mapping[str, object],
) -> dict[str, object]:
    expected = {
        "version", "training_seasons", "evaluation_seasons_forbidden_during_fit",
        "target", "feature_columns", "imputation", "standardize_means",
        "standardize_scales", "coefficients", "intercept", "c", "solver",
        "operative_tier", "operative_linear_scale", "operative_rounding",
        "operative_raw_weight_units", "operative_intercept_units",
        "operative_worst_case_abs_units",
        "class_weight", "max_iter", "sample_weight", "training_rows",
        "training_cells", "training_positive_rows", "feature_sweep",
        "hyperparameter_sweep", "threshold_sweep",
        "sigmoid_probability_operative", "b1_inputs_used",
        "a2a_inputs_used", "production_change_licensed", "artifact_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise LR8Error("soft-anatomy artifact fields differ")
    artifact = dict(value)
    if (
        artifact["version"] != ANATOMY_MODEL_VERSION
        or artifact["training_seasons"] != list(TRAINING_SEASONS)
        or artifact["evaluation_seasons_forbidden_during_fit"]
        != list(EVALUATION_SEASONS)
        or artifact["target"] != "realized_total_dk_gte_200"
        or artifact["feature_columns"] != list(ANATOMY_FEATURES)
        or artifact["imputation"] != "none_finite_required"
        or artifact["operative_tier"]
        != "raw_feature_linear_predictor_fixed_point"
        or artifact["operative_rounding"] != ANATOMY_LINEAR_ROUNDING
        or artifact["solver"] != "lbfgs"
        or artifact["class_weight"] is not None
        or artifact["sample_weight"] != "equal_total_weight_per_season_week"
        or any(artifact[key] is not False for key in (
            "feature_sweep", "hyperparameter_sweep", "threshold_sweep",
            "sigmoid_probability_operative",
            "b1_inputs_used", "a2a_inputs_used", "production_change_licensed",
        ))
    ):
        raise LR8Error("soft-anatomy artifact law differs")
    if _json_number(artifact["c"], label="soft-anatomy c") != 1.0:
        raise LR8Error("soft-anatomy artifact law differs")
    if _json_int(
        artifact["operative_linear_scale"],
        label="soft-anatomy operative_linear_scale",
        minimum=1,
    ) != ANATOMY_LINEAR_SCALE:
        raise LR8Error("soft-anatomy artifact law differs")
    if _json_int(
        artifact["max_iter"], label="soft-anatomy max_iter", minimum=1
    ) != 2000:
        raise LR8Error("soft-anatomy artifact law differs")
    width = len(ANATOMY_FEATURES)
    vectors = []
    for key in ("standardize_means", "standardize_scales", "coefficients"):
        raw_vector = artifact[key]
        if not isinstance(raw_vector, list) or len(raw_vector) != width:
            raise LR8Error(f"soft-anatomy artifact {key} differs")
        vector = np.asarray([
            _json_number(value, label=f"soft-anatomy {key}")
            for value in raw_vector
        ], dtype=np.float64)
        vectors.append(vector)
    _json_number(artifact["intercept"], label="soft-anatomy intercept")
    if np.any(vectors[1] <= 0.0):
        raise LR8Error("soft-anatomy artifact numeric law differs")
    training_rows = _json_int(
        artifact["training_rows"], label="soft-anatomy training_rows", minimum=1
    )
    training_cells = _json_int(
        artifact["training_cells"], label="soft-anatomy training_cells", minimum=1
    )
    training_positive_rows = _json_int(
        artifact["training_positive_rows"],
        label="soft-anatomy training_positive_rows",
        minimum=1,
    )
    if (
        training_cells != len(TRAINING_CELLS)
        or training_rows < training_cells
        or not 0 < training_positive_rows < training_rows
    ):
        raise LR8Error("soft-anatomy artifact training lattice differs")
    raw_units = artifact["operative_raw_weight_units"]
    if not isinstance(raw_units, list) or len(raw_units) != width:
        raise LR8Error("soft-anatomy operative weight units differ")
    operative_weights = tuple(
        _json_signed_int(value, label="soft-anatomy operative weight unit")
        for value in raw_units
    )
    operative_intercept = _json_signed_int(
        artifact["operative_intercept_units"],
        label="soft-anatomy operative intercept units",
    )
    operative_bound = _json_int(
        artifact["operative_worst_case_abs_units"],
        label="soft-anatomy operative worst-case bound",
    )
    expected_weights, expected_intercept, expected_bound = (
        _quantize_anatomy_linear_law(
            vectors[0].tolist(),
            vectors[1].tolist(),
            vectors[2].tolist(),
            float(artifact["intercept"]),
        )
    )
    if (
        operative_weights != expected_weights
        or operative_intercept != expected_intercept
        or operative_bound != expected_bound
    ):
        raise LR8Error("soft-anatomy operative fixed-point law differs")
    digest = artifact["artifact_sha256"]
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None or (
        digest != canonical_sha256(_artifact_payload(artifact))
    ):
        raise LR8Error("soft-anatomy artifact hash differs")
    return artifact


def anatomy_probability(
    artifact: Mapping[str, object], features: Sequence[float],
) -> float:
    frozen = validate_soft_anatomy_artifact(artifact)
    vector = np.asarray(features, dtype=np.float64)
    if vector.shape != (len(ANATOMY_FEATURES),) or not np.isfinite(vector).all():
        raise LR8Error("soft-anatomy prediction features differ")
    means = np.asarray(frozen["standardize_means"], dtype=np.float64)
    scales = np.asarray(frozen["standardize_scales"], dtype=np.float64)
    coefficients = np.asarray(frozen["coefficients"], dtype=np.float64)
    logit = float(((vector - means) / scales) @ coefficients) + float(
        frozen["intercept"]
    )
    if logit >= 0:
        probability = 1.0 / (1.0 + math.exp(-logit))
    else:
        exp_logit = math.exp(logit)
        probability = exp_logit / (1.0 + exp_logit)
    if not 0.0 <= probability <= 1.0 or not math.isfinite(probability):
        raise LR8Error("soft-anatomy probability is malformed")
    return probability


def operative_anatomy_linear_units(
    artifact: Mapping[str, object], features: Sequence[float],
) -> int:
    """Replay the exact fixed-point raw-feature linear-predictor tier."""
    frozen = validate_soft_anatomy_artifact(artifact)
    if isinstance(features, (str, bytes)) or len(features) != len(
        ANATOMY_FEATURES
    ):
        raise LR8Error("operative anatomy features differ")
    integers: list[int] = []
    for value in features:
        if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, np.integer, np.floating)
        ) or not math.isfinite(float(value)) or not float(value).is_integer():
            raise LR8Error("operative anatomy features must be exact integers")
        integers.append(int(value))
    result = int(frozen["operative_intercept_units"]) + sum(
        int(weight) * value
        for weight, value in zip(
            frozen["operative_raw_weight_units"], integers, strict=True
        )
    )
    if abs(result) > int(frozen["operative_worst_case_abs_units"]):
        raise LR8Error("operative anatomy tier exceeds its frozen bound")
    return result


@dataclass(frozen=True, slots=True)
class PricingRequest:
    fold_name: str
    iteration: int
    construction_blocks: tuple[str, ...]
    players: tuple[rw.PlayerSpec, ...]
    world_ids: tuple[rw.WorldId, ...]
    player_scores_micro: np.ndarray = field(compare=False, repr=False)
    book_maxima_micro: np.ndarray = field(compare=False, repr=False)
    control_rosters: tuple[tuple[str, ...], ...]
    previous_columns: tuple[tuple[str, ...], ...]
    forbidden_rosters: tuple[tuple[str, ...], ...]
    marginal_thresholds_micro: tuple[int, ...]
    book_max_cap_micro: int
    portfolio_improvement_required: bool
    anatomy_linear_scale: int
    anatomy_artifact: Mapping[str, object] = field(compare=False, repr=False)


PricingStep = Callable[[PricingRequest], Sequence[object] | None]


@dataclass(frozen=True, slots=True)
class MarginalReceipt:
    iteration: int
    roster: tuple[str, ...] | None
    threshold_counts: tuple[int, ...]
    anatomy_tier_units: int | None
    clipped_residual_gain_micro: int
    objective_vector: tuple[int, ...]
    anatomy_probability: float | None
    admitted: bool
    null: bool
    reference_book_sha256: str
    treatment_book_after_sha256: str | None


@dataclass(frozen=True, slots=True)
class FoldMechanicsResult:
    fold_name: str
    construction_blocks: tuple[str, ...]
    evaluation_blocks: tuple[str, ...]
    fold_weight: float
    candidate_budget: int
    control_candidates: tuple[tuple[str, ...], ...]
    control_book: tuple[tuple[str, ...], ...]
    treatment_candidates: tuple[tuple[str, ...], ...]
    treatment_book: tuple[tuple[str, ...], ...]
    pruning: rw.PruningResult
    generated_columns: tuple[tuple[str, ...], ...]
    steps: tuple[MarginalReceipt, ...]
    stopped_on_first_null: bool
    null_iteration: int | None
    control_selector_calls: int
    simulated_evaluation: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class LR8MechanicsResult:
    season: int
    week: int
    slate_id: str
    anatomy_artifact_sha256: str
    player_catalog_sha256: str
    player_worlds_sha256: str
    incumbent_candidates_sha256: str
    folds: tuple[FoldMechanicsResult, ...]
    deployment_fold: str
    control_deployment_book: tuple[tuple[str, ...], ...]
    treatment_deployment_book: tuple[tuple[str, ...], ...]
    primary_simulated_evaluation: Mapping[str, object]
    equal_fold_weighted_simulated_evaluation: Mapping[str, object]


def clipped_marginal_utility(
    candidate_scores_micro: Sequence[int] | np.ndarray,
    book_maxima_micro: Sequence[int] | np.ndarray,
) -> tuple[tuple[int, ...], tuple[int, ...], int, tuple[int, ...]]:
    candidate = np.asarray(candidate_scores_micro)
    maxima = np.asarray(book_maxima_micro)
    if (
        candidate.dtype.kind not in "iu"
        or maxima.dtype.kind not in "iu"
        or candidate.ndim != 1
        or maxima.shape != candidate.shape
        or not len(candidate)
    ):
        raise LR8Error("marginal score vectors must be aligned integer vectors")
    candidate = candidate.astype(np.int64, copy=False)
    maxima = maxima.astype(np.int64, copy=False)
    counts = tuple(int(np.count_nonzero(
        (maxima < threshold) & (candidate >= threshold)
    )) for threshold in MARGINAL_THRESHOLDS_MICRO)
    residuals = np.maximum(
        np.minimum(candidate, BOOK_MAX_CAP_MICRO)
        - np.minimum(maxima, BOOK_MAX_CAP_MICRO),
        0,
    ).astype(np.int64)
    gain = sum(int(value) for value in residuals)
    return counts, tuple(int(value) for value in residuals), gain, (*counts, gain)


def deployment_fold(season: int, week: int) -> str:
    """Return the pre-outcome single-book mapping: odd=A, even=B."""
    season_value = _exact_int(season, label="deployment season")
    week_value = _exact_int(week, label="deployment week", minimum=1)
    if season_value not in (*EVALUATION_SEASONS, 2026) or week_value > 18:
        raise LR8Error("deployment cell is outside the registered seasons/weeks")
    return "A" if week_value % 2 else "B"


def _read_only(value: np.ndarray) -> np.ndarray:
    result = np.array(value, copy=True)
    result.flags.writeable = False
    return result


def _select_exact80(
    identities: tuple[tuple[str, ...], ...],
    selector_totals: np.ndarray,
    columns: np.ndarray,
) -> tuple[tuple[tuple[str, ...], ...], tuple[int, ...]]:
    selected = tuple(select_tail_entries(
        selector_totals[:, columns],
        ENTRIES,
        float(CONTROL_LINE_DK),
        env={"SELECT_LSE": "0", "SELECT_LADDER": ""},
    ))
    if (
        len(selected) != ENTRIES
        or len(set(selected)) != ENTRIES
        or any(isinstance(index, bool) or not isinstance(index, (int, np.integer))
               or not 0 <= int(index) < len(identities) for index in selected)
    ):
        raise LR8Error("unchanged incumbent selector did not return exact-80")
    normalized = tuple(int(index) for index in selected)
    return tuple(identities[index] for index in normalized), normalized


def _materialize_treatment(
    controls: tuple[tuple[str, ...], ...],
    control_selector: np.ndarray,
    control_micro: np.ndarray,
    pruning: rw.PruningResult,
    generated: tuple[tuple[str, ...], ...],
    generated_selector: Sequence[np.ndarray],
    generated_micro: Sequence[np.ndarray],
) -> tuple[tuple[tuple[str, ...], ...], np.ndarray, np.ndarray]:
    identities = rw.matched_budget_treatment_pool(controls, pruning, generated)
    removed = set(pruning.removal_order[:len(generated)])
    retained_indices = [
        index for index, identity in enumerate(controls) if identity not in removed
    ]
    selector_rows = [control_selector[index] for index in retained_indices]
    micro_rows = [control_micro[index] for index in retained_indices]
    selector_rows.extend(generated_selector)
    micro_rows.extend(generated_micro)
    selector = np.stack(selector_rows).astype(np.float32, copy=False)
    micro = np.stack(micro_rows).astype(np.int64, copy=False)
    if selector.shape[0] != len(controls) or micro.shape != selector.shape:
        raise LR8Error("matched-budget treatment matrices differ")
    return identities, selector, micro


def _simulated_book_evaluation(
    players: tuple[rw.PlayerSpec, ...],
    raw_player_draws: np.ndarray,
    control_book: tuple[tuple[str, ...], ...],
    treatment_book: tuple[tuple[str, ...], ...],
    evaluation_columns: np.ndarray,
) -> dict[str, object]:
    micro = rw.to_micro_dk(raw_player_draws)
    control_raw, _ = rw._cross_score_rosters(  # noqa: SLF001 - reused frozen seam
        players, raw_player_draws, micro, control_book
    )
    treatment_raw, _ = rw._cross_score_rosters(  # noqa: SLF001
        players, raw_player_draws, micro, treatment_book
    )
    control_max = control_raw[:, evaluation_columns].max(axis=0).astype(np.float64)
    treatment_max = treatment_raw[:, evaluation_columns].max(axis=0).astype(np.float64)
    thresholds = (187.0, 194.0, 200.0, 210.0)
    return {
        "worlds": int(len(evaluation_columns)),
        "control_mean_book_max_dk": float(control_max.mean()),
        "treatment_mean_book_max_dk": float(treatment_max.mean()),
        "mean_book_max_delta_dk": float((treatment_max - control_max).mean()),
        "control_threshold_rates": {
            str(int(threshold)): float(np.mean(control_max >= threshold))
            for threshold in thresholds
        },
        "treatment_threshold_rates": {
            str(int(threshold)): float(np.mean(treatment_max >= threshold))
            for threshold in thresholds
        },
        "control_maxima_sha256": _array_sha256(control_max),
        "treatment_maxima_sha256": _array_sha256(treatment_max),
        "uses_realized_outcomes": False,
    }


def run_fold_mechanics(
    fold_name: str,
    players: Sequence[rw.PlayerSpec | Mapping[str, object]],
    world_ids: Sequence[rw.WorldId],
    raw_player_draws: np.ndarray,
    incumbent_candidates: Sequence[Sequence[object]],
    anatomy_artifact: Mapping[str, object],
    pricing_step: PricingStep,
) -> FoldMechanicsResult:
    """Run one independent matched-budget construction/evaluation fold."""
    frozen_artifact = validate_soft_anatomy_artifact(anatomy_artifact)
    specs = [spec for spec in FOLD_SPECS if spec.name == fold_name]
    if len(specs) != 1:
        raise LR8Error("fold name must be A or B")
    spec = specs[0]
    rows = _players(players)
    worlds = _worlds(world_ids)
    raw = np.asarray(raw_player_draws)
    if raw.dtype != np.float32 or raw.shape != (len(rows), len(worlds)) or (
        not np.isfinite(raw).all()
    ):
        raise LR8Error("player worlds must be one aligned finite float32 matrix")
    controls = tuple(_identity(roster) for roster in incumbent_candidates)
    if len(controls) < ENTRIES + K_MAX_PER_FOLD or len(set(controls)) != len(controls):
        raise LR8Error("incumbent pool must contain at least 88 unique candidates")
    for identity in controls:
        audit_dk_classic_identity(rows, identity)
    player_micro = rw.to_micro_dk(raw)
    control_selector, control_micro = rw._cross_score_rosters(  # noqa: SLF001
        rows, raw, player_micro, controls
    )
    construction_columns = np.asarray([
        index for index, world in enumerate(worlds)
        if world.block in spec.construction_blocks
    ], dtype=int)
    evaluation_columns = np.asarray([
        index for index, world in enumerate(worlds)
        if world.block in spec.evaluation_blocks
    ], dtype=int)
    control_book, control_rows = _select_exact80(
        controls, control_selector, construction_columns
    )
    pruning = rw.reverse_greedy_pruning_order(
        controls,
        control_micro[:, construction_columns],
        control_book,
        steps=K_MAX_PER_FOLD,
        expected_protected_count=ENTRIES,
        thresholds_micro=MARGINAL_THRESHOLDS_MICRO,
        sum_max_cap_micro=BOOK_MAX_CAP_MICRO,
    )
    if len(pruning.steps) != K_MAX_PER_FOLD or set(
        pruning.removal_order
    ) & set(control_book):
        raise LR8Error("pruning is not eight unselected incumbent candidates")
    selector_calls = 1
    for dose in range(1, K_MAX_PER_FOLD + 1):
        removed = set(pruning.removal_order[:dose])
        retained_indices = [
            index for index, identity in enumerate(controls)
            if identity not in removed
        ]
        retained = tuple(controls[index] for index in retained_indices)
        book, _ = _select_exact80(
            retained, control_selector[retained_indices], construction_columns
        )
        selector_calls += 1
        if book != control_book:
            raise LR8Error("protected incumbent exact-80 changes under pruning")

    generated: list[tuple[str, ...]] = []
    generated_selector: list[np.ndarray] = []
    generated_micro: list[np.ndarray] = []
    steps: list[MarginalReceipt] = []
    current_identities = controls
    current_selector = control_selector
    current_micro = control_micro
    current_book = control_book
    current_rows = control_rows
    stopped = False
    null_iteration: int | None = None
    construction_worlds = tuple(worlds[index] for index in construction_columns)

    for iteration in range(1, K_MAX_PER_FOLD + 1):
        reference_book = current_book
        reference_sha = canonical_sha256([list(value) for value in reference_book])
        maxima = current_micro[
            np.asarray(current_rows, dtype=int)[:, None], construction_columns
        ].max(axis=0)
        previous = tuple(generated)
        forbidden = (*controls, *previous)
        request = PricingRequest(
            fold_name=spec.name,
            iteration=iteration,
            construction_blocks=spec.construction_blocks,
            players=rows,
            world_ids=construction_worlds,
            player_scores_micro=_read_only(player_micro[:, construction_columns]),
            book_maxima_micro=_read_only(maxima),
            control_rosters=controls,
            previous_columns=previous,
            forbidden_rosters=forbidden,
            marginal_thresholds_micro=MARGINAL_THRESHOLDS_MICRO,
            book_max_cap_micro=BOOK_MAX_CAP_MICRO,
            portfolio_improvement_required=True,
            anatomy_linear_scale=ANATOMY_LINEAR_SCALE,
            anatomy_artifact=frozen_artifact,
        )
        proposal = pricing_step(request)
        if proposal is None:
            stopped = True
            null_iteration = iteration
            steps.append(MarginalReceipt(
                iteration=iteration,
                roster=None,
                threshold_counts=(0,) * len(MARGINAL_THRESHOLDS_MICRO),
                anatomy_tier_units=None,
                clipped_residual_gain_micro=0,
                objective_vector=(0,) * (len(MARGINAL_THRESHOLDS_MICRO) + 2),
                anatomy_probability=None,
                admitted=False,
                null=True,
                reference_book_sha256=reference_sha,
                treatment_book_after_sha256=None,
            ))
            break
        identity = audit_dk_classic_identity(rows, proposal)
        if identity in forbidden:
            raise LR8Error("residual proposal repeats an incumbent or prior column")
        column_selector, column_micro = rw._cross_score_rosters(  # noqa: SLF001
            rows, raw, player_micro, (identity,)
        )
        counts, _, gain, _ = clipped_marginal_utility(
            column_micro[0, construction_columns], maxima
        )
        anatomy_features = lineup_anatomy(rows, identity)
        probability = anatomy_probability(frozen_artifact, anatomy_features)
        anatomy_tier = operative_anatomy_linear_units(
            frozen_artifact, anatomy_features
        )
        # The fixed anatomy law is an operative tier below all four clear
        # counts and above capped book-max gain.  It cannot manufacture a
        # positive column: admission still requires a portfolio improvement
        # in a registered clear count or clipped book maximum.
        pricing_objective = (*counts, anatomy_tier, gain)
        if not any((*counts, gain)):
            raise LR8Error(
                "pricing proposed a portfolio-null roster; null must be explicit"
            )
        generated.append(identity)
        generated_selector.append(column_selector[0])
        generated_micro.append(column_micro[0])
        current_identities, current_selector, current_micro = _materialize_treatment(
            controls,
            control_selector,
            control_micro,
            pruning,
            tuple(generated),
            generated_selector,
            generated_micro,
        )
        current_book, current_rows = _select_exact80(
            current_identities, current_selector, construction_columns
        )
        selector_calls += 1
        treatment_sha = canonical_sha256([list(value) for value in current_book])
        steps.append(MarginalReceipt(
            iteration=iteration,
            roster=identity,
            threshold_counts=counts,
            anatomy_tier_units=anatomy_tier,
            clipped_residual_gain_micro=gain,
            objective_vector=pricing_objective,
            anatomy_probability=probability,
            admitted=True,
            null=False,
            reference_book_sha256=reference_sha,
            treatment_book_after_sha256=treatment_sha,
        ))

    if len(current_identities) != len(controls) or len(current_book) != ENTRIES:
        raise LR8Error("LR8 changed the candidate or entry budget")
    if len(generated) > K_MAX_PER_FOLD:
        raise LR8Error("LR8 exceeded eight replacements in one fold")
    simulated = _simulated_book_evaluation(
        rows, raw, control_book, current_book, evaluation_columns
    )
    return FoldMechanicsResult(
        fold_name=spec.name,
        construction_blocks=spec.construction_blocks,
        evaluation_blocks=spec.evaluation_blocks,
        fold_weight=FOLD_WEIGHT,
        candidate_budget=len(controls),
        control_candidates=controls,
        control_book=control_book,
        treatment_candidates=current_identities,
        treatment_book=current_book,
        pruning=pruning,
        generated_columns=tuple(generated),
        steps=tuple(steps),
        stopped_on_first_null=stopped,
        null_iteration=null_iteration,
        control_selector_calls=selector_calls,
        simulated_evaluation=simulated,
    )


def run_lr8_mechanics(
    *,
    season: int,
    week: int,
    slate_id: str,
    players: Sequence[rw.PlayerSpec | Mapping[str, object]],
    world_ids: Sequence[rw.WorldId],
    raw_player_draws: np.ndarray,
    incumbent_candidates: Sequence[Sequence[object]],
    anatomy_artifact: Mapping[str, object],
    pricing_steps: Mapping[str, PricingStep],
) -> LR8MechanicsResult:
    """Run both independent folds and aggregate them with equal weight."""
    season_value = _exact_int(season, label="mechanics season")
    week_value = _exact_int(week, label="mechanics week", minimum=1)
    if season_value not in EVALUATION_SEASONS or week_value > 18:
        raise LR8Error("historical mechanics cell is outside 2023..2025 Weeks 1..18")
    if not isinstance(slate_id, str) or not slate_id:
        raise LR8Error("slate id must be a nonempty string")
    if set(pricing_steps) != {spec.name for spec in FOLD_SPECS}:
        raise LR8Error("pricing steps must contain exactly folds A and B")
    rows = _players(players)
    worlds = _worlds(world_ids)
    raw = np.asarray(raw_player_draws)
    controls = tuple(_identity(roster) for roster in incumbent_candidates)
    frozen_artifact = validate_soft_anatomy_artifact(anatomy_artifact)
    folds = tuple(run_fold_mechanics(
        spec.name,
        rows,
        worlds,
        raw,
        controls,
        frozen_artifact,
        pricing_steps[spec.name],
    ) for spec in FOLD_SPECS)
    if tuple(fold.fold_weight for fold in folds) != (FOLD_WEIGHT, FOLD_WEIGHT):
        raise LR8Error("cross-fit folds do not have equal weight")
    mean_delta = sum(
        FOLD_WEIGHT * float(fold.simulated_evaluation["mean_book_max_delta_dk"])
        for fold in folds
    )
    threshold_deltas = {
        str(threshold): sum(FOLD_WEIGHT * (
            float(fold.simulated_evaluation["treatment_threshold_rates"][str(threshold)])
            - float(fold.simulated_evaluation["control_threshold_rates"][str(threshold)])
        ) for fold in folds)
        for threshold in (187, 194, 200, 210)
    }
    primary_fold = deployment_fold(season_value, week_value)
    primary = next(fold for fold in folds if fold.fold_name == primary_fold)
    return LR8MechanicsResult(
        season=season_value,
        week=week_value,
        slate_id=slate_id,
        anatomy_artifact_sha256=str(frozen_artifact["artifact_sha256"]),
        player_catalog_sha256=canonical_sha256([{
            "id": player.player_id,
            "pos": player.position,
            "team": player.team,
            "opp": player.opponent,
            "game_id": player.game_id,
            "salary": player.salary,
        } for player in rows]),
        player_worlds_sha256=_array_sha256(raw),
        incumbent_candidates_sha256=canonical_sha256([
            list(roster) for roster in controls
        ]),
        folds=folds,
        deployment_fold=primary_fold,
        control_deployment_book=primary.control_book,
        treatment_deployment_book=primary.treatment_book,
        primary_simulated_evaluation=dict(primary.simulated_evaluation),
        equal_fold_weighted_simulated_evaluation={
            "mean_book_max_delta_dk": mean_delta,
            "threshold_rate_deltas": threshold_deltas,
            "fold_weights": {"A": FOLD_WEIGHT, "B": FOLD_WEIGHT},
            "uses_realized_outcomes": False,
        },
    )


def _pruning_payload(value: rw.PruningResult) -> dict[str, object]:
    return {
        "original_candidates": value.original_candidates,
        "steps": [{
            "dose": step.dose,
            "removed_identity": list(step.removed_identity),
            "utility_before": list(step.utility_before.vector),
            "utility_after": list(step.utility_after.vector),
            "remaining_candidates": step.remaining_candidates,
        } for step in value.steps],
    }


def mechanics_payload(result: LR8MechanicsResult) -> dict[str, object]:
    if not isinstance(result, LR8MechanicsResult):
        raise LR8Error("mechanics result has the wrong type")
    payload: dict[str, object] = {
        "schema": "lr8-historical-mechanics-result-v1",
        "protocol_id": PROTOCOL_ID,
        "protocol_status": PROTOCOL_STATUS,
        "season": result.season,
        "week": result.week,
        "slate_id": result.slate_id,
        "training_seasons": list(TRAINING_SEASONS),
        "evaluation_seasons": list(EVALUATION_SEASONS),
        "anatomy_artifact_sha256": result.anatomy_artifact_sha256,
        "player_catalog_sha256": result.player_catalog_sha256,
        "player_worlds_sha256": result.player_worlds_sha256,
        "incumbent_candidates_sha256": result.incumbent_candidates_sha256,
        "candidate_budget_fixed": True,
        "entry_budget": ENTRIES,
        "k_max_per_fold": K_MAX_PER_FOLD,
        "k_max_combined": None,
        "marginal_thresholds_dk": list(MARGINAL_THRESHOLDS_DK),
        "book_max_gain_cap_dk": BOOK_MAX_CAP_DK,
        "anatomy_linear_scale": ANATOMY_LINEAR_SCALE,
        "pricing_objective_order": [
            "g_210", "g_200", "g_194", "g_187",
            "soft_anatomy_linear_predictor_units",
            "clipped_book_max_gain_micro",
        ],
        "deployment_fold": result.deployment_fold,
        "deployment_fold_rule": "odd_week_A_even_week_B",
        "control_deployment_book": [
            list(value) for value in result.control_deployment_book
        ],
        "treatment_deployment_book": [
            list(value) for value in result.treatment_deployment_book
        ],
        "primary_simulated_evaluation": dict(result.primary_simulated_evaluation),
        "folds": [{
            "fold_name": fold.fold_name,
            "construction_blocks": list(fold.construction_blocks),
            "evaluation_blocks": list(fold.evaluation_blocks),
            "fold_weight": fold.fold_weight,
            "candidate_budget": fold.candidate_budget,
            "control_candidates": [list(value) for value in fold.control_candidates],
            "control_book": [list(value) for value in fold.control_book],
            "treatment_candidates": [list(value) for value in fold.treatment_candidates],
            "treatment_book": [list(value) for value in fold.treatment_book],
            "pruning": _pruning_payload(fold.pruning),
            "generated_columns": [list(value) for value in fold.generated_columns],
            "steps": [{
                "iteration": step.iteration,
                "roster": None if step.roster is None else list(step.roster),
                "threshold_counts": list(step.threshold_counts),
                "anatomy_tier_units": step.anatomy_tier_units,
                "clipped_residual_gain_micro": step.clipped_residual_gain_micro,
                "objective_vector": list(step.objective_vector),
                "anatomy_probability": step.anatomy_probability,
                "admitted": step.admitted,
                "null": step.null,
                "reference_book_sha256": step.reference_book_sha256,
                "treatment_book_after_sha256": step.treatment_book_after_sha256,
            } for step in fold.steps],
            "stopped_on_first_null": fold.stopped_on_first_null,
            "null_iteration": fold.null_iteration,
            "selector_call_count": fold.control_selector_calls,
            "simulated_evaluation": dict(fold.simulated_evaluation),
        } for fold in result.folds],
        "equal_fold_weighted_simulated_evaluation": dict(
            result.equal_fold_weighted_simulated_evaluation
        ),
        "hard_constraints": "dk_nfl_classic_only",
        "salary_floor": None,
        "qb_stack_min": None,
        "bring_back_min": None,
        "forbid_rb_vs_dst": False,
        "forbid_two_rb_same_team": False,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "later_period_realized_outcomes_used": False,
        "pricing_optimality_proven": False,
        "historical_execution_licensed": False,
        "prospective_confirmation_licensed": False,
        "production_change_licensed": False,
    }
    payload["report_sha256"] = canonical_sha256(payload)
    return payload


@dataclass(frozen=True, slots=True)
class FrozenBookCell:
    season: int
    week: int
    fold_name: str
    candidate_budget_control: int
    candidate_budget_treatment: int
    control_candidates: tuple[tuple[str, ...], ...]
    treatment_candidates: tuple[tuple[str, ...], ...]
    control_book: tuple[tuple[str, ...], ...]
    treatment_book: tuple[tuple[str, ...], ...]
    freeze_sha256: str


@dataclass(frozen=True, slots=True)
class LaterPeriodScoreRow:
    season: int
    week: int
    roster: tuple[str, ...]
    realized_total_micro: int


def _attempt_identity(value: Mapping[str, object]) -> dict[str, object]:
    expected = {
        "uri", "generation", "sha256", "bytes", "create_once",
        "stage", "historical_outcome_lease_generation",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise LR8Error("later-period attempt identity fields differ")
    result = dict(value)
    if (
        not isinstance(result["uri"], str)
        or not result["uri"].startswith("gs://")
        or not isinstance(result["generation"], str)
        or _POSITIVE_CANONICAL_DIGITS.fullmatch(result["generation"]) is None
        or not isinstance(result["historical_outcome_lease_generation"], str)
        or _POSITIVE_CANONICAL_DIGITS.fullmatch(
            result["historical_outcome_lease_generation"]
        ) is None
        or not isinstance(result["sha256"], str)
        or _SHA256.fullmatch(result["sha256"]) is None
        or _exact_int(result["bytes"], label="attempt bytes", minimum=1) < 1
        or result["create_once"] is not True
        or result["stage"] != "lr8-2023-2025-later-period-score-read"
    ):
        raise LR8Error("later-period attempt identity differs")
    return result


def evaluate_frozen_later_period_once(
    book_cells: Sequence[FrozenBookCell],
    score_rows: Sequence[LaterPeriodScoreRow],
    *,
    attempt_identity: Mapping[str, object],
) -> dict[str, object]:
    """Replay the sole frozen 2023--2025 score read over exact paired books."""
    attempt = _attempt_identity(attempt_identity)
    cells = tuple(book_cells)
    expected_keys = {
        (season, week, fold)
        for season in EVALUATION_SEASONS
        for week in EVALUATION_WEEKS
        for fold in ("A", "B")
    }
    keys = {(cell.season, cell.week, cell.fold_name) for cell in cells}
    if len(cells) != len(expected_keys) or keys != expected_keys:
        raise LR8Error("later-period books do not cover exact 2023..2025 x 18 x A/B")
    required_scores: set[tuple[int, int, tuple[str, ...]]] = set()
    normalized_cells: list[FrozenBookCell] = []
    for cell in cells:
        control_candidates = tuple(
            _identity(roster) for roster in cell.control_candidates
        )
        treatment_candidates = tuple(
            _identity(roster) for roster in cell.treatment_candidates
        )
        control = tuple(_identity(roster) for roster in cell.control_book)
        treatment = tuple(_identity(roster) for roster in cell.treatment_book)
        control_budget = _exact_int(
            cell.candidate_budget_control,
            label="control candidate budget",
            minimum=ENTRIES,
        )
        treatment_budget = _exact_int(
            cell.candidate_budget_treatment,
            label="treatment candidate budget",
            minimum=ENTRIES,
        )
        if (
            control_budget != treatment_budget
            or len(control_candidates) != control_budget
            or len(treatment_candidates) != treatment_budget
            or len(set(control_candidates)) != control_budget
            or len(set(treatment_candidates)) != treatment_budget
            or len(control) != ENTRIES
            or len(treatment) != ENTRIES
            or len(set(control)) != ENTRIES
            or len(set(treatment)) != ENTRIES
            or not set(control) <= set(control_candidates)
            or not set(treatment) <= set(treatment_candidates)
            or not isinstance(cell.freeze_sha256, str)
            or _SHA256.fullmatch(cell.freeze_sha256) is None
        ):
            raise LR8Error("later-period frozen book budget or identity differs")
        required_scores.update(
            (cell.season, cell.week, roster) for roster in control_candidates
        )
        required_scores.update(
            (cell.season, cell.week, roster) for roster in treatment_candidates
        )
        normalized_cells.append(FrozenBookCell(
            season=cell.season,
            week=cell.week,
            fold_name=cell.fold_name,
            candidate_budget_control=control_budget,
            candidate_budget_treatment=treatment_budget,
            control_candidates=control_candidates,
            treatment_candidates=treatment_candidates,
            control_book=control,
            treatment_book=treatment,
            freeze_sha256=cell.freeze_sha256,
        ))
    score_map: dict[tuple[int, int, tuple[str, ...]], int] = {}
    for row in score_rows:
        key = (
            _exact_int(row.season, label="score season"),
            _exact_int(row.week, label="score week", minimum=1),
            _identity(row.roster),
        )
        if key in score_map:
            raise LR8Error("later-period score rows repeat a roster")
        score_map[key] = _exact_int(
            row.realized_total_micro, label="later-period realized total"
        )
    if set(score_map) != required_scores:
        raise LR8Error(
            "later-period score rows are not the exact frozen-candidate union"
        )

    per_cell: list[dict[str, object]] = []
    for cell in sorted(normalized_cells, key=lambda row: (
        row.season, row.week, row.fold_name
    )):
        control_ceiling = max(
            score_map[(cell.season, cell.week, roster)]
            for roster in cell.control_candidates
        )
        treatment_ceiling = max(
            score_map[(cell.season, cell.week, roster)]
            for roster in cell.treatment_candidates
        )
        control_max = max(
            score_map[(cell.season, cell.week, roster)]
            for roster in cell.control_book
        )
        treatment_max = max(
            score_map[(cell.season, cell.week, roster)]
            for roster in cell.treatment_book
        )
        if control_max > control_ceiling or treatment_max > treatment_ceiling:
            raise LR8Error("later-period selected maximum exceeds candidate ceiling")
        assigned_fold = deployment_fold(cell.season, cell.week)
        per_cell.append({
            "season": cell.season,
            "week": cell.week,
            "fold_name": cell.fold_name,
            "fold_weight": FOLD_WEIGHT,
            "deployment_fold": assigned_fold,
            "is_primary_deployment_book": cell.fold_name == assigned_fold,
            "control_candidate_ceiling_micro": control_ceiling,
            "treatment_candidate_ceiling_micro": treatment_ceiling,
            "control_selected_max_micro": control_max,
            "treatment_selected_max_micro": treatment_max,
            "control_conversion_gap_micro": control_ceiling - control_max,
            "treatment_conversion_gap_micro": treatment_ceiling - treatment_max,
            "selected_max_delta_micro": treatment_max - control_max,
            "freeze_sha256": cell.freeze_sha256,
        })

    slate_count = len(EVALUATION_SEASONS) * len(EVALUATION_WEEKS)
    primary_cells = tuple(
        row for row in per_cell if bool(row["is_primary_deployment_book"])
    )
    if len(primary_cells) != slate_count or len({
        (int(row["season"]), int(row["week"])) for row in primary_cells
    }) != slate_count:
        raise LR8Error("deployment rule did not produce one primary book per slate")

    def mean_micro(rows: Sequence[Mapping[str, object]], field_name: str) -> float:
        return sum(int(row[field_name]) for row in rows) / len(rows)

    primary_control_s = mean_micro(primary_cells, "control_selected_max_micro")
    primary_treatment_s = mean_micro(primary_cells, "treatment_selected_max_micro")
    primary_control_c = mean_micro(
        primary_cells, "control_candidate_ceiling_micro"
    )
    primary_treatment_c = mean_micro(
        primary_cells, "treatment_candidate_ceiling_micro"
    )
    primary_control_gap = mean_micro(
        primary_cells, "control_conversion_gap_micro"
    )
    primary_treatment_gap = mean_micro(
        primary_cells, "treatment_conversion_gap_micro"
    )
    primary_threshold_counts: dict[str, dict[str, int]] = {}
    equal_fold_threshold_counts: dict[str, dict[str, float]] = {}
    for threshold in (187, 194, 200, 210):
        line = threshold * rw.MICRO_DK_SCALE
        primary_threshold_counts[str(threshold)] = {
            "control_slates": sum(
                int(int(row["control_selected_max_micro"]) >= line)
                for row in primary_cells
            ),
            "treatment_slates": sum(
                int(int(row["treatment_selected_max_micro"]) >= line)
                for row in primary_cells
            ),
        }
        equal_fold_threshold_counts[str(threshold)] = {
            "control_equal_fold_weighted_slates": sum(
                FOLD_WEIGHT * int(
                    int(row["control_selected_max_micro"]) >= line
                )
                for row in per_cell
            ),
            "treatment_equal_fold_weighted_slates": sum(
                FOLD_WEIGHT * int(
                    int(row["treatment_selected_max_micro"]) >= line
                )
                for row in per_cell
            ),
        }

    equal_fold_control_s = sum(
        FOLD_WEIGHT * int(row["control_selected_max_micro"])
        for row in per_cell
    ) / slate_count
    equal_fold_treatment_s = sum(
        FOLD_WEIGHT * int(row["treatment_selected_max_micro"])
        for row in per_cell
    ) / slate_count
    gates = {
        "candidate_and_exact80_budgets_match": True,
        "one_primary_deployable_exact80_book_per_slate": True,
        "primary_mean_selected_max_strictly_improves": (
            primary_treatment_s > primary_control_s
        ),
        "primary_selected_max_200_strictly_improves": (
            primary_threshold_counts["200"]["treatment_slates"]
            > primary_threshold_counts["200"]["control_slates"]
        ),
        "primary_selected_max_210_no_worse": (
            primary_threshold_counts["210"]["treatment_slates"]
            >= primary_threshold_counts["210"]["control_slates"]
        ),
        "primary_selected_max_194_no_worse": (
            primary_threshold_counts["194"]["treatment_slates"]
            >= primary_threshold_counts["194"]["control_slates"]
        ),
        "primary_treatment_mean_candidate_ceiling_at_least_205": (
            primary_treatment_c
            >= MIN_CANDIDATE_CEILING_DK * rw.MICRO_DK_SCALE
        ),
        "primary_treatment_mean_candidate_to_selected_gap_at_most_5": (
            primary_treatment_gap
            <= MAX_CANDIDATE_SELECTION_GAP_DK * rw.MICRO_DK_SCALE
        ),
        "primary_treatment_mean_selected_max_at_least_194": (
            primary_treatment_s >= MIN_SELECTED_MEAN_DK * rw.MICRO_DK_SCALE
        ),
    }
    passed = all(gates.values())
    report: dict[str, object] = {
        "schema": "lr8-historical-later-period-result-v1",
        "protocol_id": PROTOCOL_ID,
        "training_seasons": list(TRAINING_SEASONS),
        "evaluation_seasons": list(EVALUATION_SEASONS),
        "evaluation_weeks": list(EVALUATION_WEEKS),
        "attempt_identity": attempt,
        "primary_deployment_rule": "odd_week_A_even_week_B",
        "primary_deployable_books_per_slate": 1,
        "primary_deployment": {
            "slates": slate_count,
            "control_mean_candidate_ceiling_dk": (
                primary_control_c / rw.MICRO_DK_SCALE
            ),
            "treatment_mean_candidate_ceiling_dk": (
                primary_treatment_c / rw.MICRO_DK_SCALE
            ),
            "control_mean_selected_max_dk": (
                primary_control_s / rw.MICRO_DK_SCALE
            ),
            "treatment_mean_selected_max_dk": (
                primary_treatment_s / rw.MICRO_DK_SCALE
            ),
            "mean_selected_max_delta_dk": (
                (primary_treatment_s - primary_control_s)
                / rw.MICRO_DK_SCALE
            ),
            "control_mean_candidate_to_selected_gap_dk": (
                primary_control_gap / rw.MICRO_DK_SCALE
            ),
            "treatment_mean_candidate_to_selected_gap_dk": (
                primary_treatment_gap / rw.MICRO_DK_SCALE
            ),
            "threshold_counts": primary_threshold_counts,
        },
        "fold_weights": {"A": FOLD_WEIGHT, "B": FOLD_WEIGHT},
        "equal_fold_diagnostics": {
            "license_bearing": False,
            "control_mean_selected_max_dk": (
                equal_fold_control_s / rw.MICRO_DK_SCALE
            ),
            "treatment_mean_selected_max_dk": (
                equal_fold_treatment_s / rw.MICRO_DK_SCALE
            ),
            "mean_selected_max_delta_dk": (
                (equal_fold_treatment_s - equal_fold_control_s)
                / rw.MICRO_DK_SCALE
            ),
            "threshold_counts": equal_fold_threshold_counts,
        },
        "frozen_minimum_treatment_mean_selected_max_dk": MIN_SELECTED_MEAN_DK,
        "target_mean_selected_max_dk": 200,
        "frozen_minimum_treatment_mean_candidate_ceiling_dk": (
            MIN_CANDIDATE_CEILING_DK
        ),
        "frozen_maximum_treatment_mean_candidate_to_selected_gap_dk": (
            MAX_CANDIDATE_SELECTION_GAP_DK
        ),
        "gates": gates,
        "historical_pass": passed,
        "disposition": (
            "lr8-historical-pass-prospective-confirmation-licensed"
            if passed else "lr8-historical-fail-closed-no-retune"
        ),
        "per_fold_cell": per_cell,
        "uses_realized_outcomes": True,
        "one_later_period_score_read": True,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "historical_refit_licensed": False,
        "prospective_2026_weeks_1_6_confirmation_licensed": passed,
        "production_change_licensed": False,
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


def validate_prelock_timestamp(as_of_utc: str, lock_time_utc: str) -> None:
    """Small future-transport guard retained for the 2026 confirmation."""
    try:
        as_of = datetime.fromisoformat(as_of_utc.replace("Z", "+00:00"))
        lock = datetime.fromisoformat(lock_time_utc.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise LR8Error("timestamps must be ISO-8601 UTC values") from exc
    if as_of.tzinfo is None or lock.tzinfo is None or (
        as_of.utcoffset() != timezone.utc.utcoffset(as_of)
        or lock.utcoffset() != timezone.utc.utcoffset(lock)
        or as_of >= lock
    ):
        raise LR8Error("source snapshot must be strictly pre-lock in UTC")


__all__ = [
    "ANATOMY_FEATURES",
    "ANATOMY_LABEL_DK",
    "ANATOMY_MODEL_VERSION",
    "ANATOMY_FEATURE_ABS_UPPER",
    "ANATOMY_LINEAR_ROUNDING",
    "ANATOMY_LINEAR_SCALE",
    "AnatomyTrainingRow",
    "BOOK_MAX_CAP_DK",
    "EVALUATION_SEASONS",
    "ENTRIES",
    "FOLD_SPECS",
    "FrozenBookCell",
    "K_MAX_PER_FOLD",
    "LR8Error",
    "LR8MechanicsResult",
    "LaterPeriodScoreRow",
    "MARGINAL_THRESHOLDS_DK",
    "MAX_CANDIDATE_SELECTION_GAP_DK",
    "MIN_CANDIDATE_CEILING_DK",
    "MIN_SELECTED_MEAN_DK",
    "MarginalReceipt",
    "PROTOCOL_ID",
    "PROTOCOL_STATUS",
    "PricingRequest",
    "TRAINING_SEASONS",
    "TRAINING_CELLS",
    "anatomy_probability",
    "audit_dk_classic_identity",
    "build_dk_classic_model",
    "canonical_json",
    "canonical_sha256",
    "clipped_marginal_utility",
    "deployment_fold",
    "evaluate_frozen_later_period_once",
    "fit_soft_anatomy_law",
    "lineup_anatomy",
    "mechanics_payload",
    "operative_anatomy_linear_units",
    "run_fold_mechanics",
    "run_lr8_mechanics",
    "validate_prelock_timestamp",
    "validate_soft_anatomy_artifact",
]
