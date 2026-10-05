"""Prospective Sunday-main lineup-policy shadows.

The historical K=1 and no-salary-floor results are outcome-viewed, so the next
honest evidence is an immutable paired portfolio created before each 2026
slate. These jobs do not publish projections or alter the app: each loads its
declared registry, builds its frozen 80-entry/194-tail book, and synchronously
stores the complete candidate pool and support artifacts for later paired
grading.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timezone
from hashlib import sha256
from types import MappingProxyType
from typing import Mapping

import pandas as pd

from ..config import current_season, settings
from ..models.components import effective_ensemble_size
from ..models.train_job import CANONICAL_VARIANT, registry_variant
from ..optimizer.construction_presets import (
    INCUMBENT_GPP_PRESET_ID,
    resolve_construction_preset_from_environment,
)

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

# --- Route Share gate contracts (O-2 / O-25, 2026-10-05) --------------------
# The paired role-union shadows run under exactly ONE declared contract. There
# is no default: a job that does not say which contract it is producing books
# for is refused, because a book built under an undeclared mixture of the two
# (Weeks 3-4: N_BOOM=160 beside the frozen N_CE=12/GEN_TOTAL_BUDGET=52) is an
# invalid week that looks complete.
ROUTE_SHARE_CONTRACT_ENV = "ROUTE_SHARE_CONTRACT"
ROUTE_SHARE_FROZEN_2026_08 = "frozen-2026-08"
ROUTE_SHARE_COMPANION_V1 = "companion-v1"
ROUTE_SHARE_CONTRACTS = (ROUTE_SHARE_FROZEN_2026_08, ROUTE_SHARE_COMPANION_V1)
# The 2026-08-11 frozen gate contract (12 CE / 12 role / 28 boom,
# reports/2026-08-11-route-share-2026-shadow-gate.md). Never edited in place.
FROZEN_2026_08_SETTINGS = MappingProxyType({
    "GEN_TOTAL_BUDGET": "52",
    "N_CE": "12", "N_EPISTEMIC": "12", "N_BOOM": "28",
    "N_GUMBEL": "0", "REPLACEMENT_SLOTS": "12",
    "EPISTEMIC_FAMILY": "role_draws",
    "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
    "ROLE_BELIEF_SEED": "7331", "CE_SEED": "1701",
})
# Companion v1 (reports/2026-09-19-route-share-current-policy-companion.md):
# the same pair under the adopted money-path generation. Only the KEYS are
# listed here; every VALUE is read from ClassicProductionPolicy's
# engine_environment(), so the contract cannot drift from production_policy.
COMPANION_V1_KEYS = (
    "GEN_TOTAL_BUDGET", "N_LEV", "N_CE", "N_EPISTEMIC", "N_BOOM",
    "N_GUMBEL", "REPLACEMENT_SLOTS", "BOOM_UNIQUE_FILL",
    "EPISTEMIC_FAMILY", "ROLE_BELIEF_FEATURES", "ROLE_BELIEF_SEED",
    "CE_SEED", "BLEND_MODEL_WEIGHT", "LIVE_SIMS", "GAME_SIM_MODE",
    "SERVED_POSITION_SCALES", "MODEL_ENSEMBLE", "MIN_LINEUP_SALARY",
)
# The gate freezes one single-seed player-distribution artifact per arm, which
# the five-seed CBWU build cannot capture (live_lineups refuses the pair), so
# the companion is the money-path generation on ONE seed. These stay unset.
COMPANION_V1_SINGLE_SEED_KEYS = (
    "MULTISEED_PORTFOLIO", "MULTISEED_SEED_PAIRS",
    "MULTISEED_WORLDS_PER_BLOCK", "MULTISEED_CANDIDATE_ENTRY_BASIS",
)
# Recorded in every candidate row's lever_env (a registered lever key), so a
# weekly reader can tell a companion book from a frozen-contract book.
COMPANION_V1_SHADOW_ID = "2026-route-share-companion-v1"
# An execution-scoped override (gcloud run jobs execute --update-env-vars
# SHADOW_DRY_RUN=1): the full path runs and persists, but under a panel id and
# run type no graded reader selects.
SHADOW_DRY_RUN_ENV = "SHADOW_DRY_RUN"
DRY_RUN_PANEL_PREFIX = "dryrun-"
DRY_RUN_CANDIDATE_RUN_TYPE = "live_shadow_dryrun"


def _adopted_policy():
    from .production_policy import ADOPTED_CLASSIC_POLICY

    return ADOPTED_CLASSIC_POLICY


def companion_v1_settings(policy=None) -> dict[str, str]:
    """The companion-v1 settings, derived from the adopted money path."""
    engine = (policy or _adopted_policy()).engine_environment()
    return {key: engine[key] for key in COMPANION_V1_KEYS}


def route_share_contract_settings(contract: str) -> dict[str, str]:
    """Exact environment one declared contract requires."""
    if contract == ROUTE_SHARE_FROZEN_2026_08:
        return dict(FROZEN_2026_08_SETTINGS)
    if contract == ROUTE_SHARE_COMPANION_V1:
        return companion_v1_settings()
    raise RuntimeError(
        f"{ROUTE_SHARE_CONTRACT_ENV} must be one of "
        f"{list(ROUTE_SHARE_CONTRACTS)}, got {contract!r}")


def route_share_job_environment(contract: str) -> dict[str, str]:
    """What a paired job must declare: the contract name plus its settings."""
    return {ROUTE_SHARE_CONTRACT_ENV: contract,
            **route_share_contract_settings(contract)}


def check_route_share_contract(environ: Mapping[str, str]) -> dict:
    """Refuse anything but one declared contract's exact settings.

    Returns the receipt recorded with the book: the contract name, every
    checked setting and the settings' canonical sha256.
    """
    contract = environ.get(ROUTE_SHARE_CONTRACT_ENV)
    if contract in (None, ""):
        raise RuntimeError(
            f"role-union shadow requires {ROUTE_SHARE_CONTRACT_ENV} in "
            f"{list(ROUTE_SHARE_CONTRACTS)}; there is no default")
    expected = route_share_contract_settings(contract)
    wrong = {
        key: (environ.get(key), value)
        for key, value in expected.items()
        if environ.get(key) != value
    }
    if wrong:
        raise RuntimeError(
            f"role-union shadow has incorrect frozen settings for "
            f"{ROUTE_SHARE_CONTRACT_ENV}={contract}: {wrong}")
    if contract == ROUTE_SHARE_COMPANION_V1:
        policy = _adopted_policy()
        multiseed = {
            key: environ[key] for key in COMPANION_V1_SINGLE_SEED_KEYS
            if environ.get(key) not in (None, "")
        }
        if multiseed:
            raise RuntimeError(
                f"companion-v1 is single-seed; unset {multiseed}")
        engine = policy.engine_environment()
        ignored = (
            set(COMPANION_V1_KEYS) | set(COMPANION_V1_SINGLE_SEED_KEYS)
            | {"MODEL_REGISTRY_VARIANT"}
            # Construction is resolved by the named preset and compared as a
            # whole in run(); infrastructure keys pass through untouched.
            | set(policy.construction_preset().optimizer_environment())
        )
        drift = {
            key: (environ[key], engine[key])
            for key in sorted(set(engine) - ignored)
            if key in environ and environ[key] != engine[key]
        }
        shadow_id = environ.get("PROSPECTIVE_SHADOW_ID")
        if shadow_id not in (None, "", COMPANION_V1_SHADOW_ID):
            drift["PROSPECTIVE_SHADOW_ID"] = (
                shadow_id, COMPANION_V1_SHADOW_ID)
        if drift:
            raise RuntimeError(
                f"companion-v1 job env contradicts the adopted money path "
                f"(found, adopted): {drift}")
    settings_ = dict(sorted(expected.items()))
    return {
        "contract": contract,
        "settings": settings_,
        "settings_sha256": sha256(json.dumps(
            settings_, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
    }


# From this target week the gate's graded pair is produced ONLY under companion
# v1 (fp-route-share-2026-companion-v1 supersedes fp-route-share-2026 from W5).
# A frozen-contract book may still be built as a labelled dry run, never live.
COMPANION_V1_FIRST_LIVE = (2026, 5)


def require_live_contract(contract: str | None, season: int, week: int,
                          *, dry_run: bool) -> None:
    """Refuse a live frozen-2026-08 freeze once companion v1 owns the weeks."""
    if (
        contract == ROUTE_SHARE_FROZEN_2026_08
        and not dry_run
        and (int(season), int(week)) >= COMPANION_V1_FIRST_LIVE
    ):
        first_season, first_week = COMPANION_V1_FIRST_LIVE
        raise RuntimeError(
            f"{ROUTE_SHARE_CONTRACT_ENV}={ROUTE_SHARE_FROZEN_2026_08} may not "
            f"produce a live run for {season} Week {week}: from "
            f"{first_season} Week {first_week} the graded pair runs under "
            f"{ROUTE_SHARE_COMPANION_V1}. Use {SHADOW_DRY_RUN_ENV}=1 for a "
            f"labelled non-live book.")


def shadow_dry_run(environ: Mapping[str, str]) -> bool:
    raw = environ.get(SHADOW_DRY_RUN_ENV)
    if raw in (None, ""):
        return False
    if raw == "1":
        return True
    raise RuntimeError(f"{SHADOW_DRY_RUN_ENV} must be unset or 1, got {raw!r}")


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
    contract_receipt = None
    if label in {K1_ROLE_UNION_LABEL, K1_ROUTE_ROLE_UNION_LABEL}:
        contract_receipt = check_route_share_contract(os.environ)
    elif os.environ.get(ROUTE_SHARE_CONTRACT_ENV, ""):
        raise RuntimeError(
            f"{ROUTE_SHARE_CONTRACT_ENV} applies only to the Route Share "
            f"role-union pair, not {label}")
    dry_run = shadow_dry_run(os.environ)
    if not os.environ.get("CAND_ARTIFACT_BUCKET", "").strip():
        raise RuntimeError(
            "tail shadow requires CAND_ARTIFACT_BUCKET so the full "
            "candidate-by-world matrix is frozen")

    if store is None:
        from ..app.store import BigQueryStore

        store = BigQueryStore()
    season, week, target_sunday = upcoming_season_week()
    require_live_contract(
        contract_receipt["contract"] if contract_receipt else None,
        season, week, dry_run=dry_run)
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
        f"{DRY_RUN_PANEL_PREFIX if dry_run else ''}"
        f"live-shadow-{label}-{season}w{week:02d}-"
        f"{stamp.strftime('%Y%m%dT%H%M%SZ')}")
    candidate_run_type = (
        DRY_RUN_CANDIDATE_RUN_TYPE if dry_run else "live_shadow")

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

    construction = resolve_construction_preset_from_environment(
        INCUMBENT_GPP_PRESET_ID, os.environ,
    )
    policy_env = dict(os.environ)
    policy_env.update(construction.optimizer_environment())
    if (contract_receipt or {}).get("contract") == ROUTE_SHARE_COMPANION_V1:
        adopted = _adopted_policy().construction_preset()
        if (
            construction.optimizer_environment()
            != adopted.optimizer_environment()
            or construction.stack != adopted.stack
        ):
            raise RuntimeError(
                "companion-v1 construction differs from the adopted money "
                f"path: {construction.receipt()} vs {adopted.receipt()}")
        policy_env["PROSPECTIVE_SHADOW_ID"] = COMPANION_V1_SHADOW_ID
    # 2026-10-05 (O-27 follow-up): a shadow never appends own_shadow, live or
    # dry. Its readers take a week's latest generation, so a Sunday shadow
    # row would silently become "the" pre-lock ownership prediction; ownership
    # is not part of either Route Share contract.
    extra = {"_log_ownership_shadow": False}
    lineups = build_sim_lineups(
        season, week, n_entries=SHADOW_ENTRIES,
        stack=construction.stack,
        tail_line=SHADOW_TAIL_LINE, seed=42, lev_scale=1.0,
        allowed_ids=allowed, salary_overrides=salaries,
        apply_notes=False, model_variant=variant,
        cand_log_table=f"{settings.predictions}.live_candidates_shadow",
        cand_log_async=False, cand_log_required=True,
        panel_run_id=panel_run_id,
        candidate_run_type=candidate_run_type,
        policy_env=policy_env,
        construction_preset_receipt=construction.receipt(),
        belief_model_variant=role_model_variant,
        model_required_features=model_required_features,
        model_forbidden_features=model_forbidden_features,
        belief_required_features=belief_required_features,
        belief_forbidden_features=belief_forbidden_features,
        route_source_policy=is_route_pair,
        distribution_artifact_spec=artifact_spec,
        **extra,
    )
    if len(lineups) != SHADOW_ENTRIES:
        raise RuntimeError(
            f"{label} shadow built {len(lineups)} lineups, expected "
            f"{SHADOW_ENTRIES}")
    log.info("froze %s shadow %s: draft_group=%s lineups=%d tail=%.1f",
             label, panel_run_id, gid, len(lineups),
             SHADOW_TAIL_LINE)
    receipt = {
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
        "candidate_run_type": candidate_run_type,
        "dry_run": dry_run,
        # Only a live run is a candidate for the gate's graded freeze; a dry
        # run (including any frozen-2026-08 book from W5) is flagged non-live.
        "live": not dry_run,
        "route_share_contract": (
            contract_receipt["contract"] if contract_receipt else None),
        "route_share_contract_settings": (
            contract_receipt["settings"] if contract_receipt else None),
        "route_share_contract_settings_sha256": (
            contract_receipt["settings_sha256"] if contract_receipt else None),
    }
    log.info("shadow receipt %s", json.dumps(receipt, sort_keys=True))
    return receipt
