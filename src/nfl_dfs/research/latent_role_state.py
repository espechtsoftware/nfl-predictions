"""Outcome-denying discrete future-role transition model.

This is the score-free first stage of the frozen 2026 latent-role shadow in
``reports/2026-08-15-prospective-latent-role-state-protocol.md``.  It predicts
the Week-W role that is still unobserved at roster lock.  It deliberately does
not generate lineups or read fantasy outcomes; candidate integration is a
later, separately validated stage.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

VERSION = "prospective-latent-role-state-v1"
SEED = 6419
POSITIONS = ("RB", "WR", "TE")
STATES = ("inactive", "dormant", "rotation", "secondary", "primary")

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
