"""Outcome-denying discrete future-role transition model.

This is the score-free first stage of the frozen 2026 latent-role shadow in
``reports/2026-08-15-prospective-latent-role-state-protocol.md``.  It predicts
the Week-W role that is still unobserved at roster lock.  It deliberately does
not generate lineups or read fantasy outcomes; candidate integration is a
later, separately validated stage.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

VERSION = "prospective-latent-role-state-v1"
ARTIFACT_VERSION = "prospective-latent-role-transition-artifact-v1"
SEED = 6419
POSITIONS = ("RB", "WR", "TE")
STATES = ("inactive", "dormant", "rotation", "secondary", "primary")
SHARE_FIELDS = ("target_share", "carry_share", "snap_share")
TEAM_SHARE_CAP = 1.15
PROMOTION_COUNT = 4
MAX_JOINT_STATE_ATTEMPTS = 50

NUMERIC_FEATURES = (
    "target_share_last", "target_share_l4",
    "carry_share_last", "carry_share_l4",
    "snap_share_last", "snap_share_l4",
    "target_share_jump", "carry_share_jump", "snap_share_jump",
    "games_played_prior", "practice_level",
    "team_vacated_target_share", "team_vacated_carry_share",
    "injury_status_missing", "practice_level_missing",
    "vacated_target_missing", "vacated_carry_missing",
)
CATEGORICAL_FEATURES = ("position", "previous_state", "injury_status")
MODEL_FEATURES = (*NUMERIC_FEATURES, *CATEGORICAL_FEATURES)
MISSINGNESS_FEATURES = (
    "injury_status_missing", "practice_level_missing",
    "vacated_target_missing", "vacated_carry_missing",
)
INPUT_FEATURES = tuple(
    name for name in MODEL_FEATURES if name not in MISSINGNESS_FEATURES
)
TARGET = "realized_state"

# A caller may not pass a broad training table and rely on the transformer to
# ignore score columns. The acquisition query must deny them at its boundary.
FORBIDDEN_OUTCOME_COLUMNS = frozenset({
    "actual", "actual_points", "dk_points", "fantasy_points",
    "fantasy_points_ppr", "lineup_score", "selected_score", "winner_score",
    "payout", "roi", "winnings", "rank", "finish_position",
})

TRANSITION_SOURCE_SQL = """
WITH snaps AS (
  SELECT ids.gsis_id, CAST(s.season AS INT64) AS season,
         CAST(s.week AS INT64) AS week,
         CASE s.team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                     WHEN 'STL' THEN 'LA' ELSE s.team END AS team,
         s.offense_pct AS snap_share
  FROM `{raw}.snap_counts` s
  JOIN `{raw}.player_ids` ids ON ids.pfr_id = s.pfr_player_id
  WHERE ids.gsis_id IS NOT NULL AND s.game_type = 'REG'
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY ids.gsis_id, CAST(s.season AS INT64), CAST(s.week AS INT64)
    ORDER BY s.offense_pct DESC
  ) = 1
), weekly AS (
  SELECT player_id AS gsis_id, CAST(season AS INT64) AS season,
         CAST(week AS INT64) AS week,
         CASE team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE team END AS team,
         SUM(COALESCE(carries, 0)) AS carries,
         MAX(target_share) AS target_share
  FROM `{raw}.weekly_stats`
  WHERE season_type = 'REG' AND player_id IS NOT NULL
  GROUP BY gsis_id, season, week, team
), team_carries AS (
  SELECT CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
         CASE team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE team END AS team,
         SUM(COALESCE(carries, 0)) AS carries
  FROM `{raw}.weekly_stats`
  WHERE season_type = 'REG'
  GROUP BY season, week, team
)
SELECT
  t.gsis_id, t.season, t.week, t.team, t.position, t.was_active,
  s.snap_share, w.target_share,
  SAFE_DIVIDE(w.carries, tc.carries) AS carry_share,
  t.target_share_last, t.target_share_l4,
  t.carry_share_last, t.carry_share_l4,
  t.snap_share_last, t.snap_share_l4,
  t.target_share_jump, t.carry_share_jump, t.snap_share_jump,
  t.games_played_prior, t.injury_status, t.practice_level,
  t.team_vacated_target_share, t.team_vacated_carry_share
FROM `{features}.player_week_training` t
LEFT JOIN snaps s
  ON s.gsis_id = t.gsis_id AND s.season = t.season AND s.week = t.week
 AND s.team = t.team
LEFT JOIN weekly w
  ON w.gsis_id = t.gsis_id AND w.season = t.season AND w.week = t.week
 AND w.team = t.team
LEFT JOIN team_carries tc
  ON tc.season = t.season AND tc.week = t.week AND tc.team = t.team
WHERE t.season BETWEEN 2018 AND 2025
  AND t.position IN ('RB', 'WR', 'TE')
ORDER BY t.gsis_id, t.season, t.week
"""


class LatentRoleStateError(ValueError):
    """The frozen role-state data or model contract was violated."""


@dataclass(frozen=True)
class JointRoleStateWorld:
    """One deterministic, identity-keyed prospective role-state world."""

    kind: str
    sequence: int
    states: tuple[tuple[str, str], ...]
    cap_accepted: bool
    rejection_reason: str | None = None
    promoted_player_id: str | None = None
    modal_state: str | None = None
    promoted_state: str | None = None
    entropy: float | None = None


def _number(frame: pd.DataFrame, name: str) -> pd.Series:
    return pd.to_numeric(frame[name], errors="coerce")


def classify_realized_states(rows: pd.DataFrame) -> pd.Series:
    """Classify completed skill-player weeks using the frozen state law.

    Active rows with missing snap share cannot be labeled honestly and remain
    ``pd.NA``. An inactive row does not need a snap observation.
    """
    required = {
        "position", "was_active", "snap_share", "target_share", "carry_share",
    }
    if missing := required - set(rows.columns):
        raise LatentRoleStateError(
            f"role-state labels missing columns {sorted(missing)}"
        )
    position = rows["position"].astype("string").str.upper()
    if invalid := sorted(set(position.dropna()) - set(POSITIONS)):
        raise LatentRoleStateError(f"unsupported role-state positions {invalid}")
    active = rows["was_active"].astype("boolean")
    snap = _number(rows, "snap_share")
    target = _number(rows, "target_share")
    carry = _number(rows, "carry_share")
    rb_opportunity = pd.Series(
        np.maximum(target.fillna(0.0), carry.fillna(0.0)), index=rows.index,
    )
    rb_opportunity.loc[target.isna() & carry.isna()] = np.nan
    opportunity = target.where(position.isin(("WR", "TE")), rb_opportunity)

    out = pd.Series(pd.NA, index=rows.index, dtype="string")
    inactive = active.eq(False) | snap.eq(0.0)
    out.loc[inactive] = "inactive"
    eligible = active.eq(True) & snap.notna() & opportunity.notna() & ~inactive
    dormant = eligible & snap.lt(0.25) & opportunity.lt(0.08)
    rotation = eligible & ~dormant & (
        snap.lt(0.60) | opportunity.lt(0.15)
    )
    secondary = eligible & ~dormant & ~rotation & opportunity.lt(0.25)
    primary = eligible & ~dormant & ~rotation & ~secondary
    out.loc[dormant] = "dormant"
    out.loc[rotation] = "rotation"
    out.loc[secondary] = "secondary"
    out.loc[primary] = "primary"
    return out


def add_previous_state(rows: pd.DataFrame) -> pd.DataFrame:
    """Attach the strictly-prior within-season state in total key order."""
    required = {"gsis_id", "season", "week", TARGET}
    if missing := required - set(rows.columns):
        raise LatentRoleStateError(
            f"previous-state frame missing columns {sorted(missing)}"
        )
    if rows.duplicated(["gsis_id", "season", "week"]).any():
        raise LatentRoleStateError("duplicate player-season-week role labels")
    ordered = rows.sort_values(
        ["gsis_id", "season", "week"], kind="mergesort",
    ).copy()
    ordered["previous_state"] = ordered.groupby(
        ["gsis_id", "season"], sort=False,
    )[TARGET].shift(1).fillna("unknown")
    return ordered.sort_index()


def prepare_transition_frame(
    rows: pd.DataFrame,
    *,
    require_target: bool = True,
) -> pd.DataFrame:
    """Enforce the score-free model contract and deterministic missingness."""
    forbidden = sorted(FORBIDDEN_OUTCOME_COLUMNS & set(rows.columns))
    if forbidden:
        raise LatentRoleStateError(
            f"role transition input contains forbidden outcomes {forbidden}"
        )
    required = set(INPUT_FEATURES)
    if require_target:
        required.add(TARGET)
    if missing := required - set(rows.columns):
        raise LatentRoleStateError(
            f"role transition input missing columns {sorted(missing)}"
        )
    selected = [*INPUT_FEATURES]
    if require_target:
        selected.append(TARGET)
    out = rows.loc[:, selected].copy()
    out["position"] = out["position"].astype("string").str.upper()
    out["previous_state"] = out["previous_state"].fillna(
        "unknown"
    ).astype("string")
    out["injury_status_missing"] = out["injury_status"].isna().astype(float)
    out["practice_level_missing"] = out["practice_level"].isna().astype(float)
    out["vacated_target_missing"] = out[
        "team_vacated_target_share"
    ].isna().astype(float)
    out["vacated_carry_missing"] = out[
        "team_vacated_carry_share"
    ].isna().astype(float)
    out["injury_status"] = out["injury_status"].fillna(
        "UNKNOWN"
    ).astype("string")
    invalid_positions = sorted(set(out["position"].dropna()) - set(POSITIONS))
    if invalid_positions:
        raise LatentRoleStateError(
            f"unsupported transition positions {invalid_positions}"
        )
    if require_target:
        out[TARGET] = out[TARGET].astype("string")
        invalid_states = sorted(set(out[TARGET].dropna()) - set(STATES))
        if invalid_states or out[TARGET].isna().any():
            raise LatentRoleStateError(
                f"invalid realized role states {invalid_states}"
            )
    if out.empty:
        raise LatentRoleStateError("no valid role-transition rows")
    columns = [*MODEL_FEATURES]
    if require_target:
        columns.append(TARGET)
    return out.loc[:, columns]


def _pipeline() -> Pipeline:
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    transform = ColumnTransformer([
        ("numeric", numeric, list(NUMERIC_FEATURES)),
        ("categorical", categorical, list(CATEGORICAL_FEATURES)),
    ])
    return Pipeline([
        ("transform", transform),
        ("model", LogisticRegression(
            C=1.0, solver="lbfgs", max_iter=1000,
            random_state=SEED,
        )),
    ])


@dataclass(frozen=True)
class FittedRoleTransition:
    pipeline: Pipeline
    n_rows: int

    @property
    def classes(self) -> tuple[str, ...]:
        model = self.pipeline.named_steps["model"]
        return tuple(str(value) for value in model.classes_)

    def predict_proba(self, rows: pd.DataFrame) -> pd.DataFrame:
        prepared = prepare_transition_frame(rows, require_target=False)
        values = self.pipeline.predict_proba(prepared[list(MODEL_FEATURES)])
        by_class = {
            state: values[:, index]
            for index, state in enumerate(self.classes)
        }
        return pd.DataFrame(
            {state: by_class[state] for state in STATES}, index=prepared.index,
        )


def fit_role_transition(rows: pd.DataFrame) -> FittedRoleTransition:
    """Fit the one frozen multinomial transition model."""
    prepared = prepare_transition_frame(rows)
    observed = set(prepared[TARGET])
    if observed != set(STATES):
        raise LatentRoleStateError(
            f"role transition requires all states; observed {sorted(observed)}"
        )
    pipeline = _pipeline()
    pipeline.fit(prepared[list(MODEL_FEATURES)], prepared[TARGET])
    fitted = FittedRoleTransition(pipeline=pipeline, n_rows=len(prepared))
    if set(fitted.classes) != set(STATES):
        raise LatentRoleStateError(
            f"role transition fit lost states {fitted.classes}"
        )
    return fitted


def load_transition_history() -> pd.DataFrame:
    """Load only usage/availability columns and attach exact role labels."""
    from ..bq import query_df
    from ..config import settings

    rows = query_df(TRANSITION_SOURCE_SQL.format(
        raw=settings.raw, features=settings.features,
    ))
    forbidden = FORBIDDEN_OUTCOME_COLUMNS & set(rows.columns)
    if forbidden:
        raise LatentRoleStateError(
            f"warehouse role source exposed outcomes {sorted(forbidden)}"
        )
    rows = rows.copy()
    rows[TARGET] = classify_realized_states(rows)
    rows = rows[rows[TARGET].notna()].copy()
    if rows.empty:
        raise LatentRoleStateError("warehouse role source produced no labels")
    return add_previous_state(rows)


def empirical_transition_probabilities(
    training: pd.DataFrame,
    target: pd.DataFrame,
) -> pd.DataFrame:
    """Dirichlet-one position/previous-state baseline from prior rows."""
    train = prepare_transition_frame(training)
    test = prepare_transition_frame(target)
    counts = train.groupby(
        ["position", "previous_state", TARGET], observed=True,
    ).size()
    rows: list[list[float]] = []
    for _, item in test.iterrows():
        values = np.ones(len(STATES), dtype=float)
        for index, state in enumerate(STATES):
            values[index] += float(counts.get(
                (item["position"], item["previous_state"], state), 0,
            ))
        rows.append((values / values.sum()).tolist())
    return pd.DataFrame(rows, columns=STATES, index=test.index)


def expanding_role_audit(
    rows: pd.DataFrame,
    evaluation_seasons: tuple[int, ...] = (2023, 2024, 2025),
) -> pd.DataFrame:
    """Expanding-season score-free model versus empirical transition audit."""
    required = {"season", *INPUT_FEATURES, TARGET}
    if missing := required - set(rows.columns):
        raise LatentRoleStateError(
            f"expanding role audit missing columns {sorted(missing)}"
        )
    records = []
    for season in evaluation_seasons:
        training = rows[pd.to_numeric(rows["season"]).lt(season)]
        target = rows[pd.to_numeric(rows["season"]).eq(season)]
        if training.empty or target.empty:
            raise LatentRoleStateError(
                f"expanding role audit season {season} has no train/test rows"
            )
        fitted = fit_role_transition(training)
        model_prob = fitted.predict_proba(target)
        baseline_prob = empirical_transition_probabilities(training, target)
        truth = target.loc[model_prob.index, TARGET]
        model_score = multiclass_scores(truth, model_prob)
        baseline_score = multiclass_scores(truth, baseline_prob)
        records.append({
            "season": int(season),
            "n_train": int(len(training)),
            "n_test": int(len(target)),
            "model_log_loss": model_score["log_loss"],
            "model_multiclass_brier": model_score["multiclass_brier"],
            "baseline_log_loss": baseline_score["log_loss"],
            "baseline_multiclass_brier": baseline_score["multiclass_brier"],
        })
    return pd.DataFrame(records)


def transition_frame_sha256(rows: pd.DataFrame) -> str:
    """Hash exact score-free training identities, features, labels and shares."""
    identity = ("gsis_id", "season", "week")
    artifact_inputs = (*identity, *SHARE_FIELDS)
    if missing := set(artifact_inputs) - set(rows.columns):
        raise LatentRoleStateError(
            f"role transition artifact input missing columns {sorted(missing)}"
        )
    prepared = prepare_transition_frame(rows)
    frame = pd.concat([
        rows.loc[prepared.index, list(artifact_inputs)].copy(), prepared,
    ], axis=1)
    if frame.duplicated(list(identity)).any():
        raise LatentRoleStateError("role transition artifact identities repeat")
    frame = frame.sort_values(list(identity), kind="mergesort")
    payload = frame.to_csv(
        index=False, na_rep="<NULL>", float_format="%.17g", lineterminator="\n",
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def compute_role_state_emissions(rows: pd.DataFrame) -> dict:
    """Compute frozen training-only share medians for every position/state."""
    forbidden = sorted(FORBIDDEN_OUTCOME_COLUMNS & set(rows.columns))
    if forbidden:
        raise LatentRoleStateError(
            f"role emission input contains forbidden outcomes {forbidden}"
        )
    required = {"position", TARGET, *SHARE_FIELDS}
    if missing := required - set(rows.columns):
        raise LatentRoleStateError(
            f"role emission input missing columns {sorted(missing)}"
        )
    prepared = prepare_transition_frame(rows)
    source = rows.loc[prepared.index, list(SHARE_FIELDS)].apply(
        pd.to_numeric, errors="coerce",
    )
    positions = prepared["position"].astype(str)
    states = prepared[TARGET].astype(str)
    emissions: dict[str, dict[str, dict[str, float]]] = {}
    for position in POSITIONS:
        emissions[position] = {}
        for state in STATES:
            if state == "inactive":
                values = {field: 0.0 for field in SHARE_FIELDS}
            else:
                mask = positions.eq(position) & states.eq(state)
                values = {}
                for field in SHARE_FIELDS:
                    observed = source.loc[mask, field]
                    observed = observed[np.isfinite(observed)]
                    if observed.empty:
                        raise LatentRoleStateError(
                            "role emission has no finite "
                            f"{position}/{state}/{field} observations"
                        )
                    value = float(observed.median())
                    if not 0.0 <= value <= TEAM_SHARE_CAP:
                        raise LatentRoleStateError(
                            "role emission share is outside bounds for "
                            f"{position}/{state}/{field}: {value}"
                        )
                    values[field] = value
            emissions[position][state] = values
    return emissions


def _validate_state_emissions(value) -> dict:
    if not isinstance(value, dict) or set(value) != set(POSITIONS):
        raise LatentRoleStateError("role artifact emission positions differ")
    normalized: dict[str, dict[str, dict[str, float]]] = {}
    for position in POSITIONS:
        by_state = value[position]
        if not isinstance(by_state, dict) or set(by_state) != set(STATES):
            raise LatentRoleStateError(
                f"role artifact emission states differ for {position}"
            )
        normalized[position] = {}
        for state in STATES:
            shares = by_state[state]
            if not isinstance(shares, dict) or set(shares) != set(SHARE_FIELDS):
                raise LatentRoleStateError(
                    "role artifact emission share fields differ for "
                    f"{position}/{state}"
                )
            normalized[position][state] = {}
            for field in SHARE_FIELDS:
                try:
                    number = float(shares[field])
                except (TypeError, ValueError) as exc:
                    raise LatentRoleStateError(
                        "role artifact emission is nonnumeric for "
                        f"{position}/{state}/{field}"
                    ) from exc
                if not np.isfinite(number) or not 0.0 <= number <= TEAM_SHARE_CAP:
                    raise LatentRoleStateError(
                        "role artifact emission is outside bounds for "
                        f"{position}/{state}/{field}"
                    )
                if state == "inactive" and number != 0.0:
                    raise LatentRoleStateError(
                        f"inactive role artifact emission is nonzero for {position}"
                    )
                normalized[position][state][field] = number
    return normalized


def _model_payload(
    fitted: FittedRoleTransition,
    rows: pd.DataFrame,
    *,
    code_sha: str,
) -> dict:
    code_sha = str(code_sha).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        raise LatentRoleStateError("role artifact requires a full git code SHA")
    required_keys = {"season", "week"}
    if missing := required_keys - set(rows.columns):
        raise LatentRoleStateError(
            f"role artifact fit boundary missing {sorted(missing)}"
        )
    prepared = prepare_transition_frame(rows)
    keyed = rows.loc[prepared.index]
    order = keyed.assign(
        _season=pd.to_numeric(keyed["season"], errors="raise"),
        _week=pd.to_numeric(keyed["week"], errors="raise"),
    ).sort_values(["_season", "_week"], kind="mergesort")
    first = order.iloc[0]
    last = order.iloc[-1]

    transform = fitted.pipeline.named_steps["transform"]
    numeric = transform.named_transformers_["numeric"]
    categorical = transform.named_transformers_["categorical"]
    num_imputer = numeric.named_steps["impute"]
    scaler = numeric.named_steps["scale"]
    cat_imputer = categorical.named_steps["impute"]
    onehot = categorical.named_steps["onehot"]
    model = fitted.pipeline.named_steps["model"]
    if len(num_imputer.statistics_) != len(NUMERIC_FEATURES):
        raise LatentRoleStateError("numeric role artifact feature count differs")
    if len(onehot.categories_) != len(CATEGORICAL_FEATURES):
        raise LatentRoleStateError(
            "categorical role artifact feature count differs"
        )
    return {
        "artifact_version": ARTIFACT_VERSION,
        "mechanism_version": VERSION,
        "code_sha": code_sha,
        "source_sql_sha256": hashlib.sha256(
            TRANSITION_SOURCE_SQL.encode()
        ).hexdigest(),
        "training_frame_sha256": transition_frame_sha256(rows),
        "fit_boundary": {
            "first_season": int(first["_season"]),
            "first_week": int(first["_week"]),
            "last_season": int(last["_season"]),
            "last_week": int(last["_week"]),
            "rows": int(fitted.n_rows),
        },
        "states": list(STATES),
        "numeric_features": list(NUMERIC_FEATURES),
        "categorical_features": list(CATEGORICAL_FEATURES),
        "numeric_imputer": [float(value) for value in num_imputer.statistics_],
        "numeric_mean": [float(value) for value in scaler.mean_],
        "numeric_scale": [float(value) for value in scaler.scale_],
        "categorical_imputer": [str(value) for value in cat_imputer.statistics_],
        "categorical_levels": [
            [str(value) for value in values] for values in onehot.categories_
        ],
        "classifier_classes": [str(value) for value in model.classes_],
        "classifier_coef": np.asarray(model.coef_, dtype=float).tolist(),
        "classifier_intercept": np.asarray(
            model.intercept_, dtype=float,
        ).tolist(),
        "classifier_iterations": np.asarray(model.n_iter_, dtype=int).tolist(),
        "state_emissions": compute_role_state_emissions(rows),
        "uses_fantasy_or_lineup_outcomes": False,
    }


def encode_role_transition_artifact(
    fitted: FittedRoleTransition,
    rows: pd.DataFrame,
    *,
    code_sha: str,
) -> tuple[bytes, dict]:
    """Encode the fitted transition as deterministic portable JSON."""
    artifact = _model_payload(fitted, rows, code_sha=code_sha)
    payload = json.dumps(
        artifact, allow_nan=False, separators=(",", ":"), sort_keys=True,
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    return payload, {
        "artifact_version": ARTIFACT_VERSION,
        "sha256": digest,
        "code_sha": artifact["code_sha"],
        "training_frame_sha256": artifact["training_frame_sha256"],
        "fit_boundary": artifact["fit_boundary"],
        "uses_fantasy_or_lineup_outcomes": False,
    }


def decode_role_transition_artifact(
    payload: bytes,
    expected_sha256: str,
) -> dict:
    """Verify checksum and the exact portable role-transition contract."""
    digest = hashlib.sha256(payload).hexdigest()
    if digest != str(expected_sha256):
        raise LatentRoleStateError(
            f"role artifact sha256 differs: {digest} != {expected_sha256}"
        )
    try:
        artifact = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LatentRoleStateError("role artifact JSON is invalid") from exc
    if artifact.get("artifact_version") != ARTIFACT_VERSION:
        raise LatentRoleStateError("role artifact version differs")
    if artifact.get("mechanism_version") != VERSION:
        raise LatentRoleStateError("role mechanism version differs")
    if artifact.get("states") != list(STATES):
        raise LatentRoleStateError("role artifact states differ")
    if artifact.get("numeric_features") != list(NUMERIC_FEATURES):
        raise LatentRoleStateError("role artifact numeric features differ")
    if artifact.get("categorical_features") != list(CATEGORICAL_FEATURES):
        raise LatentRoleStateError("role artifact categorical features differ")
    if artifact.get("uses_fantasy_or_lineup_outcomes") is not False:
        raise LatentRoleStateError("role artifact outcome boundary differs")
    artifact["state_emissions"] = _validate_state_emissions(
        artifact.get("state_emissions")
    )
    if not re.fullmatch(r"[0-9a-f]{40}", str(artifact.get("code_sha", ""))):
        raise LatentRoleStateError("role artifact code SHA differs")
    if not re.fullmatch(
        r"[0-9a-f]{64}", str(artifact.get("training_frame_sha256", "")),
    ):
        raise LatentRoleStateError("role artifact training hash differs")
    if artifact.get("source_sql_sha256") != hashlib.sha256(
        TRANSITION_SOURCE_SQL.encode()
    ).hexdigest():
        raise LatentRoleStateError("role artifact source query differs")
    classes = artifact.get("classifier_classes", [])
    if set(classes) != set(STATES) or len(classes) != len(STATES):
        raise LatentRoleStateError("role artifact classifier classes differ")
    n_numeric = len(NUMERIC_FEATURES)
    levels = artifact.get("categorical_levels", [])
    if (not isinstance(levels, list)
            or len(levels) != len(CATEGORICAL_FEATURES)
            or any(not isinstance(values, list) for values in levels)):
        raise LatentRoleStateError("role artifact categorical levels differ")
    n_encoded = n_numeric + sum(len(values) for values in levels)
    coef = np.asarray(artifact.get("classifier_coef"), dtype=float)
    intercept = np.asarray(artifact.get("classifier_intercept"), dtype=float)
    for key in ("numeric_imputer", "numeric_mean", "numeric_scale"):
        values = np.asarray(artifact.get(key), dtype=float)
        if values.shape != (n_numeric,) or not np.isfinite(values).all():
            raise LatentRoleStateError(f"role artifact {key} is invalid")
    if np.any(np.asarray(artifact["numeric_scale"], dtype=float) <= 0):
        raise LatentRoleStateError("role artifact numeric scale is invalid")
    if len(artifact.get("categorical_imputer", [])) != len(
        CATEGORICAL_FEATURES
    ):
        raise LatentRoleStateError("role artifact categorical imputer differs")
    boundary = artifact.get("fit_boundary", {})
    if not isinstance(boundary, dict) or int(boundary.get("rows", 0)) < 1:
        raise LatentRoleStateError("role artifact fit boundary is invalid")
    if coef.shape != (len(STATES), n_encoded) or intercept.shape != (
        len(STATES),
    ):
        raise LatentRoleStateError("role artifact classifier shape differs")
    if not np.isfinite(coef).all() or not np.isfinite(intercept).all():
        raise LatentRoleStateError("role artifact classifier is nonfinite")
    artifact["sha256"] = digest
    return artifact


def validate_team_role_share_caps(
    rows: pd.DataFrame,
    *,
    cap: float = TEAM_SHARE_CAP,
) -> dict[str, dict[str, float]]:
    """Reject a joint role state whose emitted team shares exceed the cap."""
    if float(cap) != TEAM_SHARE_CAP:
        raise LatentRoleStateError(
            f"role team-share cap differs: {cap} != {TEAM_SHARE_CAP}"
        )
    required = {"team", "target_share_last", "carry_share_last"}
    if missing := required - set(rows.columns):
        raise LatentRoleStateError(
            f"role team-cap frame missing columns {sorted(missing)}"
        )
    if rows.empty or rows["team"].isna().any():
        raise LatentRoleStateError("role team-cap frame has missing teams")
    shares = rows[["target_share_last", "carry_share_last"]].apply(
        pd.to_numeric, errors="coerce",
    )
    if not np.isfinite(shares.to_numpy(dtype=float)).all():
        raise LatentRoleStateError("role team-cap frame has nonfinite shares")
    grouped = pd.concat([rows[["team"]], shares], axis=1).groupby(
        "team", sort=True, dropna=False,
    )[["target_share_last", "carry_share_last"]].sum()
    violations = grouped.gt(TEAM_SHARE_CAP + 1e-12)
    if violations.any(axis=None):
        details = []
        for team, item in grouped.loc[violations.any(axis=1)].iterrows():
            for field in ("target_share_last", "carry_share_last"):
                if item[field] > TEAM_SHARE_CAP + 1e-12:
                    details.append(f"{team}/{field}={item[field]:.6f}")
        raise LatentRoleStateError(
            "sampled role state exceeds frozen team-share cap: "
            + ", ".join(details)
        )
    return {
        str(team): {
            "target_share": float(item["target_share_last"]),
            "carry_share": float(item["carry_share_last"]),
        }
        for team, item in grouped.iterrows()
    }


def apply_sampled_role_states(
    artifact: dict,
    rows: pd.DataFrame,
    sampled_states: pd.Series,
) -> pd.DataFrame:
    """Return a pure conditional frame with only six role fields replaced."""
    forbidden = sorted(FORBIDDEN_OUTCOME_COLUMNS & set(rows.columns))
    if forbidden:
        raise LatentRoleStateError(
            f"conditional role frame contains forbidden outcomes {forbidden}"
        )
    required = {
        "position", "team", "injury_status",
        "target_share_last", "target_share_l4", "target_share_jump",
        "carry_share_last", "carry_share_l4", "carry_share_jump",
        "snap_share_last", "snap_share_l4", "snap_share_jump",
    }
    if missing := required - set(rows.columns):
        raise LatentRoleStateError(
            f"conditional role frame missing columns {sorted(missing)}"
        )
    if artifact.get("artifact_version") != ARTIFACT_VERSION:
        raise LatentRoleStateError("unverified conditional role artifact")
    emissions = _validate_state_emissions(artifact.get("state_emissions"))
    if not isinstance(sampled_states, pd.Series) or not sampled_states.index.equals(
        rows.index
    ):
        raise LatentRoleStateError(
            "sampled role states must be a Series exactly aligned to players"
        )
    states = sampled_states.astype("string")
    invalid_states = sorted(set(states.dropna()) - set(STATES))
    if invalid_states or states.isna().any():
        raise LatentRoleStateError(
            f"sampled role states are invalid {invalid_states}"
        )
    positions = rows["position"].astype("string").str.upper()
    invalid_positions = sorted(set(positions.dropna()) - set(POSITIONS))
    if invalid_positions or positions.isna().any():
        raise LatentRoleStateError(
            f"sampled role positions are invalid {invalid_positions}"
        )
    out_mask = rows["injury_status"].astype("string").str.strip().str.upper().eq(
        "OUT"
    ).fillna(False)
    if (out_mask & states.ne("inactive")).any():
        raise LatentRoleStateError("players listed Out must be fixed to inactive")

    out = rows.copy(deep=True)
    for field in SHARE_FIELDS:
        emitted = pd.Series([
            emissions[str(position)][str(state)][field]
            for position, state in zip(positions, states, strict=True)
        ], index=out.index, dtype=float)
        out[f"{field}_last"] = emitted
        prior = pd.to_numeric(out[f"{field}_l4"], errors="coerce")
        out[f"{field}_jump"] = emitted - prior
    out["sampled_role_state"] = states
    validate_team_role_share_caps(out)
    return out


def _validate_role_probabilities(
    rows: pd.DataFrame,
    probabilities: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {"gsis_id", "position", "team", "injury_status"}
    if missing := required - set(rows.columns):
        raise LatentRoleStateError(
            f"joint role-state frame missing columns {sorted(missing)}"
        )
    if rows.empty or rows["gsis_id"].isna().any():
        raise LatentRoleStateError("joint role-state frame has missing players")
    if rows["gsis_id"].astype(str).duplicated().any():
        raise LatentRoleStateError("joint role-state frame repeats players")
    if not probabilities.index.equals(rows.index):
        raise LatentRoleStateError(
            "joint role probabilities are not exactly player-aligned"
        )
    if list(probabilities.columns) != list(STATES):
        raise LatentRoleStateError("joint role probabilities are not canonical")
    values = probabilities.to_numpy(dtype=float)
    if (
        not np.isfinite(values).all()
        or np.any(values < 0.0)
        or not np.allclose(values.sum(axis=1), 1.0, atol=1e-9)
    ):
        raise LatentRoleStateError("joint role probabilities are invalid")
    ordered = rows.assign(_player_id=rows["gsis_id"].astype(str)).sort_values(
        "_player_id", kind="mergesort",
    )
    return ordered, probabilities.loc[ordered.index]


def role_state_world_series(
    world: JointRoleStateWorld,
    rows: pd.DataFrame,
) -> pd.Series:
    """Reconstruct a world's sampled states in the caller's player order."""
    if not world.cap_accepted:
        raise LatentRoleStateError("cannot apply a cap-rejected role-state world")
    if "gsis_id" not in rows:
        raise LatentRoleStateError("role-state world frame has no player identity")
    identities = rows["gsis_id"].astype("string")
    if identities.isna().any() or identities.duplicated().any():
        raise LatentRoleStateError("role-state world player identity is invalid")
    if len(world.states) != len(rows):
        raise LatentRoleStateError("role-state world player count differs")
    world_ids = [str(player_id) for player_id, _ in world.states]
    world_states = [str(state) for _, state in world.states]
    if len(set(world_ids)) != len(world_ids) or not set(world_states).issubset(
        STATES
    ):
        raise LatentRoleStateError("role-state world mapping is invalid")
    mapping = dict(world.states)
    if set(mapping) != set(identities.astype(str)):
        raise LatentRoleStateError("role-state world player set differs")
    return identities.astype(str).map(mapping).astype("string").rename(
        "sampled_role_state"
    )


def apply_role_state_world(
    artifact: dict,
    rows: pd.DataFrame,
    world: JointRoleStateWorld,
) -> pd.DataFrame:
    """Apply a verified identity-keyed state world to a conditional frame."""
    return apply_sampled_role_states(
        artifact, rows, role_state_world_series(world, rows),
    )


def build_joint_role_state_worlds(
    artifact: dict,
    rows: pd.DataFrame,
    probabilities: pd.DataFrame,
) -> tuple[tuple[JointRoleStateWorld, ...], tuple[JointRoleStateWorld, ...]]:
    """Build four cap-valid promotions and the frozen 50 seeded attempts.

    The caller optimizes sampled attempts in order and stops after eight
    distinct rosters. Every rejected, optimized or duplicate sampled attempt
    consumes one of the returned 50 identities.
    """
    ordered, ordered_probabilities = _validate_role_probabilities(
        rows, probabilities,
    )
    identities = ordered["_player_id"].astype(str).tolist()
    values = ordered_probabilities.to_numpy(dtype=float)
    modal_index = np.argmax(values, axis=1)
    out_mask = ordered["injury_status"].astype("string").str.strip().str.upper().eq(
        "OUT"
    ).fillna(False).to_numpy(dtype=bool)
    modal_index[out_mask] = STATES.index("inactive")
    modal_states = pd.Series(
        [STATES[index] for index in modal_index], index=ordered.index,
        dtype="string",
    )

    entropy_values = -np.sum(
        np.where(values > 0.0, values * np.log(np.clip(values, 1e-300, 1.0)), 0.0),
        axis=1,
    )
    eligible = []
    for row_number, player_id in enumerate(identities):
        current = int(modal_index[row_number])
        if out_mask[row_number] or current >= len(STATES) - 1:
            continue
        higher = values[row_number, current + 1:]
        if higher.size == 0 or float(higher.max()) <= 0.0:
            continue
        promoted = current + 1 + int(np.argmax(higher))
        eligible.append((
            -float(entropy_values[row_number]), player_id, row_number, promoted,
        ))
    eligible.sort()

    promotions: list[JointRoleStateWorld] = []
    for negative_entropy, player_id, row_number, promoted in eligible:
        states = modal_states.copy()
        states.iloc[row_number] = STATES[promoted]
        world = JointRoleStateWorld(
            kind="promotion",
            sequence=len(promotions) + 1,
            states=tuple(zip(identities, states.astype(str), strict=True)),
            cap_accepted=True,
            promoted_player_id=player_id,
            modal_state=STATES[int(modal_index[row_number])],
            promoted_state=STATES[promoted],
            entropy=-negative_entropy,
        )
        try:
            apply_role_state_world(artifact, rows, world)
        except LatentRoleStateError as exc:
            if "team-share cap" in str(exc):
                continue
            raise
        promotions.append(world)
        if len(promotions) == PROMOTION_COUNT:
            break
    if len(promotions) != PROMOTION_COUNT:
        raise LatentRoleStateError(
            "fewer than four cap-valid deterministic role promotions"
        )

    rng = np.random.default_rng(SEED)
    attempts: list[JointRoleStateWorld] = []
    for sequence in range(1, MAX_JOINT_STATE_ATTEMPTS + 1):
        sampled = []
        for row_number in range(len(ordered)):
            if out_mask[row_number]:
                sampled.append("inactive")
            else:
                sampled.append(str(rng.choice(STATES, p=values[row_number])))
        state_pairs = tuple(zip(identities, sampled, strict=True))
        candidate = JointRoleStateWorld(
            kind="sampled",
            sequence=sequence,
            states=state_pairs,
            cap_accepted=True,
        )
        try:
            apply_role_state_world(artifact, rows, candidate)
        except LatentRoleStateError as exc:
            if "team-share cap" not in str(exc):
                raise
            candidate = JointRoleStateWorld(
                kind="sampled",
                sequence=sequence,
                states=state_pairs,
                cap_accepted=False,
                rejection_reason=str(exc),
            )
        attempts.append(candidate)
    return tuple(promotions), tuple(attempts)


def predict_role_transition_artifact(
    artifact: dict,
    rows: pd.DataFrame,
) -> pd.DataFrame:
    """Predict with the portable artifact and return canonical state order."""
    # Re-encode/decode is unnecessary here; callers load through the decoder.
    if artifact.get("artifact_version") != ARTIFACT_VERSION:
        raise LatentRoleStateError("unverified role artifact version")
    prepared = prepare_transition_frame(rows, require_target=False)
    numeric = prepared[list(NUMERIC_FEATURES)].apply(
        pd.to_numeric, errors="coerce",
    ).to_numpy(dtype=float)
    imputer = np.asarray(artifact["numeric_imputer"], dtype=float)
    mean = np.asarray(artifact["numeric_mean"], dtype=float)
    scale = np.asarray(artifact["numeric_scale"], dtype=float)
    missing = ~np.isfinite(numeric)
    numeric[missing] = np.broadcast_to(imputer, numeric.shape)[missing]
    numeric = (numeric - mean) / scale

    encoded = [numeric]
    for index, feature in enumerate(CATEGORICAL_FEATURES):
        fill = str(artifact["categorical_imputer"][index])
        values = prepared[feature].fillna(fill).astype(str).to_numpy()
        levels = [str(value) for value in artifact["categorical_levels"][index]]
        encoded.append(np.column_stack([values == level for level in levels]))
    design = np.column_stack(encoded).astype(float)
    coef = np.asarray(artifact["classifier_coef"], dtype=float)
    intercept = np.asarray(artifact["classifier_intercept"], dtype=float)
    logits = design @ coef.T + intercept
    logits -= logits.max(axis=1, keepdims=True)
    probability = np.exp(logits)
    probability /= probability.sum(axis=1, keepdims=True)
    by_class = {
        state: probability[:, index]
        for index, state in enumerate(artifact["classifier_classes"])
    }
    return pd.DataFrame(
        {state: by_class[state] for state in STATES}, index=prepared.index,
    )


def persist_role_transition_artifact(
    fitted: FittedRoleTransition,
    rows: pd.DataFrame,
    *,
    code_sha: str,
    bucket_name: str,
    object_name: str,
    storage_client=None,
) -> dict:
    """Create one checksum-bound GCS artifact; never overwrite an identity."""
    bucket_name = str(bucket_name).strip()
    object_name = str(object_name).strip().lstrip("/")
    if not bucket_name or not object_name or ".." in object_name.split("/"):
        raise LatentRoleStateError("role artifact bucket/object is invalid")
    payload, receipt = encode_role_transition_artifact(
        fitted, rows, code_sha=code_sha,
    )
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client()
    storage_client.bucket(bucket_name).blob(object_name).upload_from_string(
        payload, content_type="application/json", if_generation_match=0,
    )
    return {
        **receipt,
        "uri": f"gs://{bucket_name}/{object_name}",
        "create_only": True,
    }


def multiclass_scores(
    truth: pd.Series,
    probabilities: pd.DataFrame,
) -> dict[str, float]:
    """Return the frozen score-only-on-role-label calibration metrics."""
    if list(probabilities.columns) != list(STATES):
        raise LatentRoleStateError("role probabilities are not canonical")
    labels = truth.astype("string")
    if not labels.isin(STATES).all() or not probabilities.index.equals(
        truth.index
    ):
        raise LatentRoleStateError("role score labels/probabilities misalign")
    values = probabilities.to_numpy(dtype=float)
    if (not np.isfinite(values).all()
            or not np.allclose(values.sum(axis=1), 1.0, atol=1e-9)):
        raise LatentRoleStateError("invalid role probability simplex")
    target = np.column_stack([labels.eq(state).to_numpy() for state in STATES])
    chosen = values[np.arange(len(labels)), np.argmax(target, axis=1)]
    return {
        "log_loss": float(-np.mean(np.log(np.clip(chosen, 1e-15, 1.0)))),
        "multiclass_brier": float(np.mean(np.sum((values - target) ** 2, axis=1))),
    }
