"""Outcome-denying conditional scenario factory for the 2026 role shadow.

The factory is deliberately separate from the production lineup path.  It
fits the frozen score-free transition model through W-1, persists its exact
artifact create-only, samples the preregistered joint role worlds, and invokes
the already-registered ``tail_k1_role`` component model on role-conditioned
feature rows.  The returned vectors generate candidates only; the lineup
engine cross-scores them on the unchanged incumbent CBWU worlds.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..config import settings
from ..research.latent_role_state import (
    FORBIDDEN_OUTCOME_COLUMNS,
    INPUT_FEATURES,
    LIVE_TRANSITION_SOURCE_SQL,
    POSITIONS,
    JointRoleStateWorld,
    LatentRoleStateError,
    apply_role_state_world,
    build_joint_role_state_worlds,
    decode_role_transition_artifact,
    encode_role_transition_artifact,
    fit_role_transition,
    load_live_transition_history,
    predict_role_transition_artifact,
)


VERSION = "prospective-latent-role-scenario-factory-v1"
EXPECTED_MODEL_VARIANT = "tail_k1_role"
EXPECTED_WORLDS = 10_000
ROLE_MODEL_FEATURES = (
    "target_share_last", "carry_share_last", "snap_share_last",
    "target_share_jump", "carry_share_jump", "snap_share_jump",
)
_CODE_SHA = re.compile(r"^[0-9a-f]{40}$")
_SEED_LABELS = frozenset({"R0", "R1", "R2", "R3", "R4", "single"})
_INJURY_SOURCE_SQL = """
SELECT gsis_id, season, week, injury_status, practice_level,
       injury_source_modified_at, injury_snapshot_pulled_at,
       injury_information_at, injury_source_kind, slate_lock_at
FROM `{features}.player_week_injury`
WHERE season = @season AND week = @week
  AND injury_information_at <= @as_of
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY gsis_id, season, week
  ORDER BY injury_information_at DESC, injury_source_kind, gsis_id
) = 1
ORDER BY gsis_id
"""


def _aware(value, label: str) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise LatentRoleStateError(f"{label} must be timezone-aware")
    return stamp.tz_convert("UTC")


def _frame_sha256(
    frame: pd.DataFrame,
    columns: tuple[str, ...] | list[str],
    *,
    sort_by: tuple[str, ...] | list[str],
) -> str:
    missing = set(columns) - set(frame.columns)
    if missing:
        raise LatentRoleStateError(
            f"latent-role hash frame lacks {sorted(missing)}"
        )
    selected = frame.loc[:, list(columns)].copy()
    for column in selected:
        if pd.api.types.is_datetime64_any_dtype(selected[column]):
            selected[column] = pd.to_datetime(
                selected[column], utc=True, errors="coerce",
            ).astype("string")
    selected = selected.sort_values(list(sort_by), kind="mergesort")
    payload = selected.to_csv(
        index=False,
        na_rep="<NULL>",
        float_format="%.17g",
        lineterminator="\n",
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _world_sha256(world: JointRoleStateWorld) -> str:
    payload = json.dumps(
        {
            "kind": world.kind,
            "sequence": int(world.sequence),
            "states": [[str(player), str(state)] for player, state in world.states],
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_live_injury_context(
    season: int,
    week: int,
    *,
    as_of,
) -> pd.DataFrame:
    """Read only timestamp-qualified target-week availability information."""
    from ..bq import query_df

    stamp = _aware(as_of, "latent-role injury as-of")
    rows = query_df(
        _INJURY_SOURCE_SQL.format(features=settings.features),
        params={
            "season": int(season),
            "week": int(week),
            "as_of": stamp.to_pydatetime(),
        },
    )
    if rows.empty:
        return pd.DataFrame(columns=(
            "gsis_id", "season", "week", "injury_status", "practice_level",
            "injury_source_modified_at", "injury_snapshot_pulled_at",
            "injury_information_at", "injury_source_kind", "slate_lock_at",
        ))
    if rows.gsis_id.isna().any() or rows.gsis_id.astype(str).duplicated().any():
        raise LatentRoleStateError("live injury context player keys are invalid")
    information = pd.to_datetime(rows.injury_information_at, utc=True, errors="coerce")
    locks = pd.to_datetime(rows.slate_lock_at, utc=True, errors="coerce")
    if information.isna().any() or locks.isna().any():
        raise LatentRoleStateError("live injury context timestamps are missing")
    if information.gt(stamp).any() or information.gt(locks).any():
        raise LatentRoleStateError("live injury context is not pre-as-of/pre-lock")
    pulled = pd.to_datetime(
        rows.injury_snapshot_pulled_at, utc=True, errors="coerce",
    )
    modified = pd.to_datetime(
        rows.injury_source_modified_at, utc=True, errors="coerce",
    )
    invalid_collector = (
        rows.injury_source_kind.astype(str).eq("collector_snapshot")
        & pulled.isna()
    )
    if invalid_collector.any() or (modified.notna() & pulled.notna() & modified.gt(pulled)).any():
        raise LatentRoleStateError("live injury source chronology is invalid")
    return rows.copy()


def build_live_transition_rows(
    slate: pd.DataFrame,
    features: pd.DataFrame,
    history: pd.DataFrame,
    injury: pd.DataFrame,
) -> pd.DataFrame:
    """Construct exact player-aligned score-free transition inputs."""
    forbidden = sorted(FORBIDDEN_OUTCOME_COLUMNS & set(slate.columns))
    if forbidden:
        raise LatentRoleStateError(
            f"live latent-role slate contains outcomes {forbidden}"
        )
    required_slate = {"gsis_id", "pos", "team", "salary"}
    if missing := required_slate - set(slate.columns):
        raise LatentRoleStateError(
            f"live latent-role slate lacks {sorted(missing)}"
        )
    skill_slate = slate[slate.pos.astype(str).str.upper().isin(POSITIONS)].copy()
    if skill_slate.empty or skill_slate.gsis_id.isna().any():
        raise LatentRoleStateError("live latent-role slate has no keyed skill rows")
    if skill_slate.gsis_id.astype(str).duplicated().any():
        raise LatentRoleStateError("live latent-role slate repeats skill players")
    target_seasons = pd.to_numeric(slate.season, errors="raise")
    target_weeks = pd.to_numeric(slate.week, errors="raise")
    if target_seasons.nunique() != 1 or target_weeks.nunique() != 1:
        raise LatentRoleStateError("live latent-role slate target is not singular")
    target_season = int(target_seasons.iloc[0])
    target_week = int(target_weeks.iloc[0])
    if not history.empty:
        history_season = pd.to_numeric(history.season, errors="raise")
        history_week = pd.to_numeric(history.week, errors="raise")
        target_or_future = history_season.gt(target_season) | (
            history_season.eq(target_season) & history_week.ge(target_week)
        )
        if target_or_future.any():
            raise LatentRoleStateError(
                "live latent-role history contains target/future rows"
            )

    required_features = {
        "gsis_id", "position", "team", "status",
        *(name for name in INPUT_FEATURES if name not in {"position", "previous_state"}),
    }
    if missing := required_features - set(features.columns):
        raise LatentRoleStateError(
            f"live latent-role features lack {sorted(missing)}"
        )
    indexed = features.copy()
    indexed["gsis_id"] = indexed.gsis_id.astype("string")
    indexed = indexed[
        indexed.position.astype(str).str.upper().isin(POSITIONS)
        & indexed.gsis_id.isin(skill_slate.gsis_id.astype("string"))
    ]
    if indexed.gsis_id.duplicated().any():
        raise LatentRoleStateError("live latent-role feature rows repeat players")
    indexed = indexed.set_index("gsis_id", drop=False)
    order = skill_slate.gsis_id.astype("string").tolist()
    missing_players = sorted(set(order) - set(indexed.index.astype(str)))
    if missing_players:
        raise LatentRoleStateError(
            f"live latent-role features miss players {missing_players[:8]}"
        )
    live = indexed.loc[order].reset_index(drop=True)

    # Previous state is strictly within-season. Week 1 therefore remains
    # ``unknown`` instead of quietly carrying the final role from 2025.
    prior = history[
        pd.to_numeric(history.season, errors="coerce").eq(
            target_season
        )
    ].sort_values(["gsis_id", "week"], kind="mergesort")
    previous = (
        prior.groupby("gsis_id", sort=False).tail(1)
        .set_index(prior.groupby("gsis_id", sort=False).tail(1).gsis_id.astype(str))[
            "realized_state"
        ]
        if not prior.empty else pd.Series(dtype="string")
    )
    live["previous_state"] = live.gsis_id.astype(str).map(previous).fillna(
        "unknown"
    )

    # Same-week availability is sourced from the timestamp-bearing table, not
    # trusted merely because a value happens to exist on the feature row.
    live["injury_status"] = pd.NA
    live["practice_level"] = np.nan
    if not injury.empty:
        availability = injury.set_index(injury.gsis_id.astype(str))
        live["injury_status"] = live.gsis_id.astype(str).map(
            availability.injury_status
        )
        live["practice_level"] = pd.to_numeric(
            live.gsis_id.astype(str).map(availability.practice_level),
            errors="coerce",
        )
    dk_out = live.status.astype("string").str.strip().str.upper().eq("OUT")
    live.loc[dk_out.fillna(False), "injury_status"] = "Out"
    live["position"] = live.position.astype("string").str.upper()
    live["team"] = live.team.astype("string")
    return live


def build_transition_artifact(
    history: pd.DataFrame,
    *,
    code_sha: str,
    bucket_name: str,
    object_name: str,
    storage_client=None,
) -> tuple[dict, dict]:
    """Fit, persist create-only, and decode one live transition artifact."""
    code_sha = str(code_sha).strip().lower()
    if not _CODE_SHA.fullmatch(code_sha):
        raise LatentRoleStateError("live role artifact requires a full code SHA")
    fitted = fit_role_transition(history)
    payload, receipt = encode_role_transition_artifact(
        fitted,
        history,
        code_sha=code_sha,
        source_sql=LIVE_TRANSITION_SOURCE_SQL,
    )
    bucket_name = str(bucket_name).strip()
    object_name = str(object_name).strip().lstrip("/")
    if not bucket_name or not object_name or ".." in object_name.split("/"):
        raise LatentRoleStateError("live role artifact target is invalid")
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client()
    storage_client.bucket(bucket_name).blob(object_name).upload_from_string(
        payload,
        content_type="application/json",
        if_generation_match=0,
    )
    full_receipt = {
        **receipt,
        "uri": f"gs://{bucket_name}/{object_name}",
        "bytes": len(payload),
        "create_only": True,
    }
    return decode_role_transition_artifact(payload, receipt["sha256"]), full_receipt


class LiveLatentRoleScenarioFactory:
    """Cached callable used by all five books of one paired shadow run."""

    def __init__(
        self,
        *,
        season: int,
        week: int,
        as_of,
        code_sha: str,
        artifact: dict,
        artifact_receipt: dict,
        history: pd.DataFrame,
        features: pd.DataFrame,
        injury: pd.DataFrame,
        conditional_model,
        conditional_model_version: str,
        tabpfn_marginal_rows: pd.DataFrame | None = None,
        expected_n_sims: int = EXPECTED_WORLDS,
    ):
        self.season = int(season)
        self.week = int(week)
        self.as_of = _aware(as_of, "latent-role factory as-of")
        self.code_sha = str(code_sha)
        self.artifact = artifact
        self.artifact_receipt = dict(artifact_receipt)
        self.history = history.copy(deep=True)
        self.features = features.copy(deep=True)
        self.injury = injury.copy(deep=True)
        self.conditional_model = conditional_model
        self.conditional_model_version = str(conditional_model_version)
        self.tabpfn_marginal_rows = (
            None if tabpfn_marginal_rows is None
            else tabpfn_marginal_rows.copy(deep=True)
        )
        self.expected_n_sims = int(expected_n_sims)
        self.receipts: list[dict] = []

    def _conditional_projection(
        self,
        world: JointRoleStateWorld,
        live_rows: pd.DataFrame,
        slate: pd.DataFrame,
        *,
        role_seed: int,
        n_sims: int,
        policy_env: dict[str, str],
    ) -> tuple[np.ndarray, np.ndarray]:
        from ..backtest.replay import (
            apply_draw_shape,
            apply_served_position_scales,
            apply_served_tail_scale,
        )
        from ..models import simulate
        from ..models.blend import blend, effective_model_weight, shift_draws_to_means
        from ..optimizer.lineup import PUNT_MAX_SALARY

        feature_rows = self.features.copy(deep=True)
        feature_rows["gsis_id"] = feature_rows.gsis_id.astype("string")
        slate_skill = slate[slate.pos.astype(str).str.upper().ne("DST")].copy()
        skill_order = slate_skill.gsis_id.astype("string").tolist()
        feature_rows = feature_rows[
            feature_rows.gsis_id.isin(skill_order)
            & feature_rows.position.astype(str).str.upper().isin(("QB", *POSITIONS))
        ]
        if feature_rows.gsis_id.duplicated().any():
            raise LatentRoleStateError("conditional model feature players repeat")
        feature_rows = feature_rows.set_index("gsis_id", drop=False).loc[
            skill_order
        ].reset_index(drop=True)
        salary_map = slate_skill.set_index(
            slate_skill.gsis_id.astype("string")
        ).salary
        feature_rows["salary"] = feature_rows.gsis_id.astype(str).map(salary_map)

        role_index = feature_rows[
            feature_rows.position.astype(str).str.upper().isin(POSITIONS)
        ].index
        aligned_role = live_rows.set_index(live_rows.gsis_id.astype("string")).loc[
            feature_rows.loc[role_index, "gsis_id"].astype(str)
        ].reset_index(drop=True)
        aligned_role.index = role_index
        conditioned = apply_role_state_world(self.artifact, aligned_role, world)
        for column in ROLE_MODEL_FEATURES:
            feature_rows.loc[role_index, column] = conditioned[column].to_numpy()

        components = self.conditional_model.predict_components(feature_rows)
        sim = simulate.simulate(
            components,
            n_sims=n_sims,
            seed=role_seed,
            keep_draws=True,
            game_ids=feature_rows.get("game_id"),
            team_ids=feature_rows.get("team"),
            game_totals=feature_rows.get("game_total"),
            env=policy_env,
        )
        keys = feature_rows[[
            column for column in ("season", "week", "gsis_id", "is_rookie")
            if column in feature_rows.columns
        ]]
        draws = apply_draw_shape(
            sim.draws,
            feature_rows.position,
            role_seed,
            keys=keys,
            env=policy_env,
            tabpfn_cache_rows=self.tabpfn_marginal_rows,
        )
        model_mean = draws.mean(axis=1, dtype=np.float64)
        market = slate_skill.set_index(
            slate_skill.gsis_id.astype("string")
        ).loc[skill_order, "market_points"].to_numpy(dtype=float)
        target = blend(model_mean, market, effective_model_weight(policy_env))
        draws = shift_draws_to_means(draws, target)
        draws = apply_served_tail_scale(
            draws, feature_rows.position, env=policy_env,
        )
        draws = apply_served_position_scales(
            draws, feature_rows.position, env=policy_env,
        )

        full_draws = np.empty((len(slate), n_sims), dtype=np.float64)
        lookup = {
            str(player_id): draws[index]
            for index, player_id in enumerate(feature_rows.gsis_id)
        }
        for row_number, item in enumerate(slate.itertuples(index=False)):
            if str(item.pos).upper() == "DST":
                full_draws[row_number] = float(item.proj)
            else:
                try:
                    full_draws[row_number] = lookup[str(item.gsis_id)]
                except KeyError as exc:
                    raise LatentRoleStateError(
                        f"conditional draws miss player {item.gsis_id}"
                    ) from exc

        conditional_proj = full_draws.mean(axis=1, dtype=np.float64)
        punt = (
            pd.to_numeric(slate.salary, errors="coerce").to_numpy() <= PUNT_MAX_SALARY
        ) & slate.pos.astype(str).str.upper().ne("DST").to_numpy()
        conditional_p90 = np.percentile(full_draws, 90, axis=1)
        conditional_proj[punt] = np.maximum(
            conditional_proj[punt], conditional_p90[punt],
        )
        offset = (
            pd.to_numeric(slate.proj_tourney, errors="coerce").to_numpy(float)
            - pd.to_numeric(slate.proj, errors="coerce").to_numpy(float)
        )
        objective = conditional_proj + offset
        if not np.isfinite(objective).all() or not np.isfinite(full_draws).all():
            raise LatentRoleStateError("conditional role projections are nonfinite")
        return objective, full_draws

    def __call__(self, **kwargs):
        season, week = int(kwargs["season"]), int(kwargs["week"])
        if (season, week) != (self.season, self.week):
            raise LatentRoleStateError("latent-role factory target differs")
        source_label = str(kwargs["source_label"])
        if source_label not in _SEED_LABELS:
            raise LatentRoleStateError("latent-role source label is unregistered")
        n_sims = int(kwargs["n_sims"])
        if n_sims != self.expected_n_sims:
            raise LatentRoleStateError(
                f"latent-role worlds differ: {n_sims} != {self.expected_n_sims}"
            )
        variant = str(kwargs["conditional_model_variant"])
        if variant != EXPECTED_MODEL_VARIANT:
            raise LatentRoleStateError("latent-role conditional registry differs")
        env = dict(kwargs["policy_env"])
        if (
            env.get("EPISTEMIC_FAMILY") != "latent_role_states"
            or env.get("PROSPECTIVE_LATENT_ROLE_VERSION")
            != "prospective-latent-role-state-v1"
            or any(int(env.get(name, "0") or 0) for name in (
                "N_ROUTE_TAIL", "N_COVERAGE_TAIL", "N_CE", "N_GUMBEL",
            ))
            or env.get("MULTISEED_PORTFOLIO") not in {
                "", "CBWU_LATENT_ROLE_SHADOW",
            }
        ):
            raise LatentRoleStateError("latent-role policy bundles another arm")

        slate = kwargs["slate"].copy(deep=True).reset_index(drop=True)
        required = {
            "id", "gsis_id", "pos", "team", "salary", "season", "week",
            "proj", "proj_tourney", "market_points",
        }
        if missing := required - set(slate.columns):
            raise LatentRoleStateError(
                f"latent-role scenario slate lacks {sorted(missing)}"
            )
        live_rows = build_live_transition_rows(
            slate, self.features, self.history, self.injury,
        )
        probabilities = predict_role_transition_artifact(
            self.artifact, live_rows,
        )
        promotions, attempts = build_joint_role_state_worlds(
            self.artifact, live_rows, probabilities,
        )
        scenarios: list[tuple[str, np.ndarray]] = []
        scenario_receipts = []
        role_seed = int(kwargs["role_seed"])

        for world in promotions:
            objective, draws = self._conditional_projection(
                world,
                live_rows,
                slate,
                role_seed=role_seed,
                n_sims=n_sims,
                policy_env=env,
            )
            world_hash = _world_sha256(world)
            name = (
                f"latent_promotion:{world.sequence}:"
                f"{world.promoted_player_id}:{world.modal_state}>"
                f"{world.promoted_state}:{world_hash}"
            )
            scenarios.append((name, objective))
            scenario_receipts.append({
                "scenario": name,
                "kind": "promotion",
                "world_sha256": world_hash,
                "conditional_draw_sha256": hashlib.sha256(
                    np.asarray(draws, dtype="<f8").tobytes()
                ).hexdigest(),
                "draw_index": None,
            })

        cap_rejections = []
        for world in attempts:
            world_hash = _world_sha256(world)
            if not world.cap_accepted:
                cap_rejections.append({
                    "attempt": int(world.sequence),
                    "world_sha256": world_hash,
                    "reason": str(world.rejection_reason),
                })
                continue
            _, draws = self._conditional_projection(
                world,
                live_rows,
                slate,
                role_seed=role_seed,
                n_sims=n_sims,
                policy_env=env,
            )
            skill_mask = slate.pos.astype(str).str.upper().ne("DST").to_numpy()
            totals = draws[skill_mask].sum(axis=0, dtype=np.float64)
            draw_index = int(np.argmax(totals))
            name = (
                f"latent_sampled:{world.sequence}:draw:{draw_index}:"
                f"{world_hash}"
            )
            scenarios.append((name, draws[:, draw_index].copy()))
            scenario_receipts.append({
                "scenario": name,
                "kind": "sampled",
                "world_sha256": world_hash,
                "conditional_draw_sha256": hashlib.sha256(
                    np.asarray(draws, dtype="<f8").tobytes()
                ).hexdigest(),
                "draw_index": draw_index,
            })

        transition_columns = ["gsis_id", *INPUT_FEATURES]
        probability_frame = pd.concat(
            [live_rows[["gsis_id"]].reset_index(drop=True), probabilities.reset_index(drop=True)],
            axis=1,
        )
        injury_hash = (
            _frame_sha256(
                self.injury,
                [
                    "gsis_id", "season", "week", "injury_status",
                    "practice_level", "injury_information_at",
                    "injury_source_kind", "slate_lock_at",
                ],
                sort_by=["gsis_id", "season", "week"],
            )
            if not self.injury.empty else hashlib.sha256(b"").hexdigest()
        )
        receipt = {
            "factory_version": VERSION,
            "uses_realized_outcomes": False,
            "uses_fantasy_or_lineup_outcomes": False,
            "season": season,
            "week": week,
            "as_of": self.as_of.isoformat(),
            "source_label": source_label,
            "projection_seed": int(kwargs["projection_seed"]),
            "role_seed": role_seed,
            "worlds": n_sims,
            "conditional_model_variant": variant,
            "conditional_model_version": self.conditional_model_version,
            "tabpfn_marginal_cache_rows": (
                None if self.tabpfn_marginal_rows is None
                else int(len(self.tabpfn_marginal_rows))
            ),
            "transition_artifact": self.artifact_receipt,
            "transition_input_sha256": _frame_sha256(
                live_rows, transition_columns, sort_by=["gsis_id"],
            ),
            "role_probability_sha256": _frame_sha256(
                probability_frame,
                ["gsis_id", "inactive", "dormant", "rotation", "secondary", "primary"],
                sort_by=["gsis_id"],
            ),
            "injury_context_sha256": injury_hash,
            "promotion_scenarios": 4,
            "sampled_cap_valid_scenarios": len(scenarios) - 4,
            "sampled_cap_rejections": cap_rejections,
            "scenarios": scenario_receipts,
            "code_sha": self.code_sha,
        }
        self.receipts.append(receipt)
        return tuple(scenarios), receipt


def create_live_latent_role_scenario_factory(
    *,
    season: int,
    week: int,
    as_of: datetime | None,
    code_sha: str,
    bucket_name: str,
    object_name: str,
    storage_client=None,
) -> LiveLatentRoleScenarioFactory:
    """Load all score-free inputs once for a five-seed paired shadow run."""
    stamp = as_of or datetime.now(timezone.utc)
    history = load_live_transition_history(season, week)
    artifact, artifact_receipt = build_transition_artifact(
        history,
        code_sha=code_sha,
        bucket_name=bucket_name,
        object_name=object_name,
        storage_client=storage_client,
    )
    from ..backtest.replay import load_tabpfn_marginal_cache
    from ..models import coldstart
    from ..models.train_job import load_latest_component_models
    from .route_share_shadow import validate_component_feature_contract
    from .run_projections import upcoming_slate_features

    features = coldstart.fill_cold_start_features(
        upcoming_slate_features(int(season), int(week))
    )
    injury = load_live_injury_context(season, week, as_of=stamp)
    model, version = load_latest_component_models(EXPECTED_MODEL_VARIANT)
    marginal_rows = load_tabpfn_marginal_cache(
        int(season), {"TABPFN_MARGINAL_TABLE": ""},
    )
    from ..models.train_job import registered_ensemble_size

    if registered_ensemble_size(model) != 1:
        raise LatentRoleStateError(
            "latent-role conditional registry must contain exactly K=1"
        )
    validate_component_feature_contract(
        model,
        registry_variant=EXPECTED_MODEL_VARIANT,
        required=ROLE_MODEL_FEATURES,
    )
    return LiveLatentRoleScenarioFactory(
        season=season,
        week=week,
        as_of=stamp,
        code_sha=code_sha,
        artifact=artifact,
        artifact_receipt=artifact_receipt,
        history=history,
        features=features,
        injury=injury,
        conditional_model=model,
        conditional_model_version=version,
        tabpfn_marginal_rows=marginal_rows,
    )


__all__ = [
    "EXPECTED_MODEL_VARIANT",
    "LiveLatentRoleScenarioFactory",
    "VERSION",
    "build_live_transition_rows",
    "build_transition_artifact",
    "create_live_latent_role_scenario_factory",
    "load_live_injury_context",
]
