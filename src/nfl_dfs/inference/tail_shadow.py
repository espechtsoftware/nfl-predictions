"""Prospective Sunday-main lineup-policy shadows.

The historical K=1 and no-salary-floor results are outcome-viewed, so the next
honest evidence is an immutable paired portfolio created before each 2026
slate. These jobs do not publish projections or alter the app: each loads its
declared registry, builds its frozen 80-entry/194-tail book, and synchronously
stores the complete candidate pool and support artifacts for later paired
grading.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone

import pandas as pd

from ..config import current_season, settings
from ..models.components import effective_ensemble_size
from ..models.train_job import CANONICAL_VARIANT, registry_variant
from ..optimizer.lineup import StackRules

log = logging.getLogger(__name__)

K1_VARIANT = "tail_k1"
K1_ROLE_VARIANT = "tail_k1_role"
K1_ROUTE_VARIANT = "tail_k1_route"
K1_ROUTE_ROLE_VARIANT = "tail_k1_route_role"
K3_VARIANT = CANONICAL_VARIANT
VARIANT_K = {K1_VARIANT: 1, K1_ROUTE_VARIANT: 1, K3_VARIANT: 3}
VARIANT_LABEL = {
    K1_VARIANT: "tail_k1",
    K1_ROUTE_VARIANT: "tail_k1_route",
    K3_VARIANT: "tail_k3",
}
K1_NOFLOOR_LABEL = "tail_k1_nofloor"
K1_ROLE_UNION_LABEL = "tail_k1_roleunion"
K1_ROUTE_ROLE_UNION_LABEL = "tail_k1_route_roleunion"
ROLE_FEATURES = (
    "target_share_last,carry_share_last,snap_share_last,"
    "target_share_jump,carry_share_jump,snap_share_jump"
)
ROUTE_FEATURES = (
    "fp_route_share_last,fp_route_share_l4,fp_route_share_jump,"
    "fp_route_cross_season"
)
POLICY_SPEC = {
    "tail_k1": (K1_VARIANT, 49_000),
    K1_NOFLOOR_LABEL: (K1_VARIANT, 0),
    K1_ROLE_UNION_LABEL: (K1_VARIANT, 49_000),
    K1_ROUTE_ROLE_UNION_LABEL: (K1_ROUTE_VARIANT, 49_000),
    "tail_k3": (K3_VARIANT, 49_000),
}
SHADOW_ENTRIES = 80
SHADOW_TAIL_LINE = 194.0


def upcoming_season_week() -> tuple[int, int, date]:
    """Current season, next regular week, and that week's Sunday date."""
    from ..bq import query_df

    season = current_season()
    frame = query_df(
        f"""SELECT week, gameday FROM `{settings.raw}.schedules`
            WHERE season = @season
              AND game_type = 'REG'
              AND gameday >= CAST(CURRENT_DATE() AS STRING)
            ORDER BY week, gameday""",
        params={"season": season},
    )
    if frame.empty or pd.isna(frame.week.iloc[0]):
        raise RuntimeError(f"no upcoming regular-season week for {season}")
    week = int(frame.week.min())
    dates = pd.to_datetime(
        frame.loc[frame.week == week, "gameday"], errors="coerce")
    sundays = dates[dates.dt.dayofweek == 6]
    if sundays.empty:
        raise RuntimeError(
            f"regular-season {season} week {week} has no Sunday games")
    return season, week, sundays.min().date()


def sunday_main_group(slates: pd.DataFrame, target_sunday: date) -> int:
    """Largest all-Sunday group on the target regular-season Sunday."""
    required = {"draft_group_id", "game_start", "teams", "players"}
    missing = required - set(slates.columns)
    if missing:
        raise ValueError(f"classic slate rows missing {sorted(missing)}")
    choices: list[tuple[int, int, int]] = []
    for gid, grp in slates.groupby("draft_group_id", sort=False):
        starts = pd.to_datetime(grp.game_start, utc=True)
        eastern = starts.dt.tz_convert("America/New_York")
        days = set(eastern.dt.day_name())
        if days != {"Sunday"}:
            continue
        slate_dates = set(eastern.dt.date)
        if slate_dates != {target_sunday}:
            continue
        games = int(pd.to_numeric(grp.teams, errors="coerce").fillna(0).sum()) // 2
        players = int(pd.to_numeric(
            grp.players, errors="coerce").fillna(0).sum())
        choices.append((games, players, int(gid)))
    if not choices:
        raise RuntimeError(
            f"no all-Sunday classic draft group is available for "
            f"{target_sunday}")
    return max(choices)[2]


def run(*, expected_variant: str = K1_VARIANT,
        shadow_label: str | None = None, store=None,
        generated_at: datetime | None = None) -> dict:
    """Freeze one declared shadow arm and return its immutable identity."""
    if expected_variant not in VARIANT_K:
        raise ValueError(f"unsupported shadow variant {expected_variant!r}")
    variant = registry_variant()
    if variant != expected_variant:
        raise RuntimeError(
            f"tail shadow requires MODEL_REGISTRY_VARIANT={expected_variant}, "
            f"got {variant}")
    size = effective_ensemble_size()
    expected_k = VARIANT_K[variant]
    if size != expected_k:
        raise RuntimeError(
            f"{VARIANT_LABEL[variant]} shadow requires "
            f"MODEL_ENSEMBLE={expected_k}, got {size}")
    label = shadow_label or VARIANT_LABEL[variant]
    if label not in POLICY_SPEC:
        raise ValueError(f"unsupported shadow policy {label!r}")
    policy_variant, expected_floor = POLICY_SPEC[label]
    if policy_variant != variant:
        raise RuntimeError(
            f"shadow policy {label} requires MODEL_REGISTRY_VARIANT="
            f"{policy_variant}, got {variant}")
    try:
        actual_floor = int(os.environ.get(
            "MIN_LINEUP_SALARY", "49000") or 0)
    except ValueError as exc:
        raise RuntimeError("MIN_LINEUP_SALARY must be an integer") from exc
    if actual_floor != expected_floor:
        raise RuntimeError(
            f"shadow policy {label} requires MIN_LINEUP_SALARY="
            f"{expected_floor}, got {actual_floor}")
    if label in {K1_ROLE_UNION_LABEL, K1_ROUTE_ROLE_UNION_LABEL}:
        exact = {
            "GEN_TOTAL_BUDGET": "52",
            "N_CE": "12", "N_EPISTEMIC": "12", "N_BOOM": "28",
            "N_GUMBEL": "0", "REPLACEMENT_SLOTS": "12",
            "EPISTEMIC_FAMILY": "role_draws",
            "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
            "ROLE_BELIEF_SEED": "7331", "CE_SEED": "1701",
        }
        wrong = {
            key: (os.environ.get(key), value)
            for key, value in exact.items()
            if os.environ.get(key) != value
        }
        if wrong:
            raise RuntimeError(
                f"role-union shadow has incorrect frozen settings: {wrong}")
    if not os.environ.get("CAND_ARTIFACT_BUCKET", "").strip():
        raise RuntimeError(
            "tail shadow requires CAND_ARTIFACT_BUCKET so the full "
            "candidate-by-world matrix is frozen")

    if store is None:
        from ..app.store import BigQueryStore

        store = BigQueryStore()
    season, week, target_sunday = upcoming_season_week()
    gid = sunday_main_group(store.classic_slates(), target_sunday)
    salary_frame = store.classic_salaries(gid)
    if salary_frame.empty:
        raise RuntimeError(f"Sunday-main draft group {gid} has no salaries")
    salary_frame = salary_frame.drop_duplicates("dk_player_id")
    allowed = {int(v) for v in salary_frame.dk_player_id.dropna()}
    salaries = {
        int(r.dk_player_id): int(r.salary)
        for r in salary_frame[["dk_player_id", "salary"]].dropna().itertuples()
    }

    stamp = generated_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    stamp = stamp.astimezone(timezone.utc)
    panel_run_id = (
        f"live-shadow-{label}-{season}w{week:02d}-"
        f"{stamp.strftime('%Y%m%dT%H%M%SZ')}")

    from .live_lineups import build_sim_lineups

    is_control_pair = label == K1_ROLE_UNION_LABEL
    is_route_pair = label == K1_ROUTE_ROLE_UNION_LABEL
    if is_route_pair:
        from .route_share_shadow import require_prior_week_source

        require_prior_week_source(season, week)

    role_model_variant = None
    artifact_spec = None
    model_required_features: tuple[str, ...] = ()
    model_forbidden_features: tuple[str, ...] = ()
    belief_required_features: tuple[str, ...] = ()
    belief_forbidden_features: tuple[str, ...] = ()
    if is_control_pair or is_route_pair:
        from .route_share_shadow import (
            DistributionArtifactSpec,
            ROLE_FEATURES as ROLE_FEATURE_NAMES,
            ROUTE_FEATURES as ROUTE_FEATURE_NAMES,
        )

        bucket = os.environ["CAND_ARTIFACT_BUCKET"].strip()
        if is_control_pair:
            role_model_variant = K1_ROLE_VARIANT
            model_forbidden_features = (*ROLE_FEATURE_NAMES,
                                        *ROUTE_FEATURE_NAMES)
            belief_required_features = ROLE_FEATURE_NAMES
            belief_forbidden_features = ROUTE_FEATURE_NAMES
            arm = "control"
        else:
            role_model_variant = K1_ROUTE_ROLE_VARIANT
            model_required_features = ROUTE_FEATURE_NAMES
            model_forbidden_features = ROLE_FEATURE_NAMES
            belief_required_features = (*ROLE_FEATURE_NAMES,
                                        *ROUTE_FEATURE_NAMES)
            arm = "treatment"
        artifact_spec = DistributionArtifactSpec(
            bucket=bucket,
            panel_run_id=panel_run_id,
            arm=arm,
            model_variant=variant,
            belief_model_variant=role_model_variant,
        )

    lineups = build_sim_lineups(
        season, week, n_entries=SHADOW_ENTRIES,
        stack=StackRules(qb_stack_min=2, bring_back_min=1,
                         forbid_rb_vs_dst=True),
        tail_line=SHADOW_TAIL_LINE, seed=42, lev_scale=1.0,
        allowed_ids=allowed, salary_overrides=salaries,
        apply_notes=False, model_variant=variant,
        cand_log_table=f"{settings.predictions}.live_candidates_shadow",
        cand_log_async=False, cand_log_required=True,
        panel_run_id=panel_run_id,
        candidate_run_type="live_shadow",
        policy_env=dict(os.environ),
        belief_model_variant=role_model_variant,
        model_required_features=model_required_features,
        model_forbidden_features=model_forbidden_features,
        belief_required_features=belief_required_features,
        belief_forbidden_features=belief_forbidden_features,
        route_source_policy=is_route_pair,
        distribution_artifact_spec=artifact_spec,
    )
    if len(lineups) != SHADOW_ENTRIES:
        raise RuntimeError(
            f"{label} shadow built {len(lineups)} lineups, expected "
            f"{SHADOW_ENTRIES}")
    log.info("froze %s shadow %s: draft_group=%s lineups=%d tail=%.1f",
             label, panel_run_id, gid, len(lineups),
             SHADOW_TAIL_LINE)
    return {
        "panel_run_id": panel_run_id,
        "season": season,
        "week": week,
        "draft_group_id": gid,
        "entries": len(lineups),
        "tail_line": SHADOW_TAIL_LINE,
        "model_variant": variant,
        "role_model_variant": (
            role_model_variant),
        "shadow_label": label,
        "minimum_lineup_salary": actual_floor,
    }
