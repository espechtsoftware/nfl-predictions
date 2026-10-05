"""Paired, outcome-unseen 2026 archetype and recourse shadow runner."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Mapping

import numpy as np

from ..backtest.engine import CandidateBatch, _validate_candidate_batch
from ..config import settings
from ..optimizer.lineup import Lineup, select_tail_entries
from .production_policy import ADOPTED_CLASSIC_POLICY
from .recourse_worlds import persist_recourse_world_artifact


log = logging.getLogger(__name__)
PROSPECTIVE_PAIRED_SHADOW_VERSION = "prospective-archetype-paired-shadow-v1"
_CODE_SHA = re.compile(r"^[0-9a-f]{7,40}$")

# --- CBWU-OI collection contracts (O-27, 2026-10-05) ------------------------
# reports/2026-08-18-cbwu-oi-prospective-shadow-spec.md froze the comparison
# on the 160-leverage / 40-boom population (clarification 2026-08-30). Every
# run from Week 1 to Week 4 then died on a stale image while the checker
# called the job "running". Operator 2026-10-04: from Week 5 the shadow runs
# under the CURRENT money-path policy (companion v1); the frozen 160/40
# comparison ends after its one panel (Week 1) and is not adjudicated.
#
# The job must DECLARE which contract it collects for; there is no default.
# The frozen v1 set stays selectable for dry runs and replays only.
CBWU_OI_CONTRACT_ENV = "CBWU_OI_CONTRACT"
CBWU_OI_FROZEN_V1 = "2026-cbwu-oi-v1"
CBWU_OI_COMPANION_V1 = "2026-cbwu-oi-companion-v1"
CBWU_OI_CONTRACTS = (CBWU_OI_FROZEN_V1, CBWU_OI_COMPANION_V1)
# The 2026-08-18 frozen set as literals (never derived from production_policy,
# so a later policy edit cannot silently move it). Never edited in place.
CBWU_OI_FROZEN_SETTINGS = MappingProxyType({
    # Population (spec clarification 2026-08-30: 160-leverage / 40-boom).
    "GEN_TOTAL_BUDGET": "52",
    "N_LEV": "160",
    "N_BOOM": "40",
    "N_CE": "0",
    "N_EPISTEMIC": "12",
    "REPLACEMENT_SLOTS": "12",
    "BOOM_UNIQUE_FILL": "0",
    # The only treatment difference: the five-book combination law.
    "MULTISEED_PORTFOLIO": "CBWU_OI_SHADOW",
    # Identical registered seeds R0-R4, world blocks and entry basis.
    "MULTISEED_SEED_PAIRS": (
        "R0=0:7331;R1=1137260708:2690847602;R2=2875959182:1630284992;"
        "R3=253722715:3374646876;R4=1643280042:3977633467"
    ),
    "MULTISEED_WORLDS_PER_BLOCK": "10000",
    "MULTISEED_CANDIDATE_ENTRY_BASIS": "80",
    # The unchanged coverage selector on both arms.
    "SELECT_LSE": "0",
})
# Companion v1: the adopted money-path generation and selector, with only the
# five-book combination law swapped to CBWU-OI in the treatment. Only the KEYS
# are listed; every VALUE is read from ClassicProductionPolicy's
# engine_environment(), so the contract cannot drift from production_policy
# (a test pins the derived values as literals and the settings sha256).
CBWU_OI_COMPANION_V1_KEYS = (
    "GEN_TOTAL_BUDGET", "N_LEV", "N_CE", "N_EPISTEMIC", "N_BOOM",
    "N_GUMBEL", "REPLACEMENT_SLOTS", "BOOM_UNIQUE_FILL",
    "EPISTEMIC_FAMILY", "ROLE_BELIEF_FEATURES", "ROLE_BELIEF_SEED",
    "CE_SEED", "BLEND_MODEL_WEIGHT", "LIVE_SIMS", "GAME_SIM_MODE",
    "SERVED_POSITION_SCALES", "MODEL_ENSEMBLE", "MIN_LINEUP_SALARY",
    "MULTISEED_SEED_PAIRS", "MULTISEED_WORLDS_PER_BLOCK",
    "MULTISEED_CANDIDATE_ENTRY_BASIS", "SELECT_LSE",
)
CBWU_OI_COMPANION_V1_SHADOW_ID = "2026-cbwu-oi-companion-v1"
# From this target week only the companion may freeze a live panel.
CBWU_OI_COMPANION_V1_FIRST_LIVE = (2026, 5)
# Panel and candidate-row identities per contract. They never overlap (the
# companion prefix does not begin with the frozen one), so companion weeks
# cannot be pooled with the 160/40 panel by a prefix glob.
CBWU_OI_IDENTITIES = MappingProxyType({
    CBWU_OI_FROZEN_V1: ("prospective-cbwu-oi", "prospective_cbwu_oi_shadow"),
    CBWU_OI_COMPANION_V1: (
        "companion-cbwu-oi-v1", "companion_cbwu_oi_v1_shadow"),
})
# Fixed by every paired spec and passed by this runner, not by the environment.
PAIRED_SHADOW_ENTRIES = 80
PAIRED_SHADOW_TAIL_LINE = 194.0


def _adopted_policy():
    return ADOPTED_CLASSIC_POLICY


def cbwu_oi_companion_v1_settings(policy=None) -> dict[str, str]:
    """Companion-v1 settings, derived from the adopted money path."""
    engine = (policy or _adopted_policy()).engine_environment()
    settings_ = {key: engine[key] for key in CBWU_OI_COMPANION_V1_KEYS}
    settings_["MULTISEED_PORTFOLIO"] = "CBWU_OI_SHADOW"
    return settings_


def cbwu_oi_contract_settings(contract: str | None) -> dict[str, str]:
    """Exact settings one declared contract requires."""
    if contract == CBWU_OI_FROZEN_V1:
        return dict(CBWU_OI_FROZEN_SETTINGS)
    if contract == CBWU_OI_COMPANION_V1:
        return cbwu_oi_companion_v1_settings()
    raise RuntimeError(
        f"CBWU-OI shadow requires {CBWU_OI_CONTRACT_ENV} in "
        f"{list(CBWU_OI_CONTRACTS)} on the job; got {contract!r}. There is "
        "no default: a job that does not declare the contract it collects "
        "for is refused."
    )


def cbwu_oi_job_environment(contract: str) -> dict[str, str]:
    """What the Cloud Run job must declare for one contract.

    The companion job carries its complete settings (self-describing, and
    audited by check_prospective_gates / verify_deployment); the frozen set
    is code-built and the job declares only its name.
    """
    if contract == CBWU_OI_COMPANION_V1:
        return {CBWU_OI_CONTRACT_ENV: contract,
                **cbwu_oi_companion_v1_settings()}
    cbwu_oi_contract_settings(contract)
    return {CBWU_OI_CONTRACT_ENV: contract}


def cbwu_oi_environment(
    contract: str, environ: Mapping[str, str], policy=None,
) -> tuple[dict[str, str], dict[str, str]]:
    """(treatment build env, control selector env) for one contract."""
    policy = policy or _adopted_policy()
    construction = policy.construction_preset().optimizer_environment()
    if contract == CBWU_OI_FROZEN_V1:
        build = policy.cbwu_oi_shadow_environment(environ)
        control = policy.incumbent_control_environment(environ)
    elif contract == CBWU_OI_COMPANION_V1:
        build = policy.engine_environment(environ)
        build.update({
            "MULTISEED_PORTFOLIO": "CBWU_OI_SHADOW",
            "PROSPECTIVE_SHADOW_ID": CBWU_OI_COMPANION_V1_SHADOW_ID,
        })
        control = policy.engine_environment(environ)
    else:
        cbwu_oi_contract_settings(contract)
        raise AssertionError("unreachable")
    build.update(construction)
    return build, control


def check_cbwu_oi_contract(
    environ: Mapping[str, str], policy_env: Mapping[str, str],
) -> dict:
    """Refuse a CBWU-OI run that is not one declared contract, exactly.

    Returns the receipt frozen into the manifest: the contract name, every
    checked setting and the settings' canonical sha256.
    """
    contract = environ.get(CBWU_OI_CONTRACT_ENV)
    expected = cbwu_oi_contract_settings(contract)
    wrong = {
        key: (policy_env.get(key), value)
        for key, value in expected.items()
        if policy_env.get(key) != value
    }
    if wrong:
        raise RuntimeError(
            f"CBWU-OI shadow environment contradicts its declared contract "
            f"{contract} (found, required): {wrong}"
        )
    if contract == CBWU_OI_COMPANION_V1:
        policy = _adopted_policy()
        job_drift = {
            key: (environ.get(key), value)
            for key, value in expected.items()
            if environ.get(key) != value
        }
        if job_drift:
            raise RuntimeError(
                f"{CBWU_OI_COMPANION_V1} job env contradicts the adopted money "
                f"path (found, adopted): {job_drift}"
            )
        if (policy.default_entries, float(policy.tail_line)) != (
                PAIRED_SHADOW_ENTRIES, PAIRED_SHADOW_TAIL_LINE):
            raise RuntimeError(
                "the adopted entries/tail line moved from the paired "
                f"runner's {PAIRED_SHADOW_ENTRIES}/{PAIRED_SHADOW_TAIL_LINE}")
    settings_ = {
        **dict(sorted(expected.items())),
        "ENTRIES": str(PAIRED_SHADOW_ENTRIES),
        "TAIL_LINE": repr(PAIRED_SHADOW_TAIL_LINE),
    }
    return {
        "contract": contract,
        "settings": settings_,
        "settings_sha256": hashlib.sha256(json.dumps(
            settings_, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
    }


def require_live_cbwu_oi_contract(
    contract: str, season: int, week: int, *, dry_run: bool,
) -> None:
    """Refuse a live frozen-v1 panel once the companion owns the weeks."""
    if (
        contract == CBWU_OI_FROZEN_V1
        and not dry_run
        and (int(season), int(week)) >= CBWU_OI_COMPANION_V1_FIRST_LIVE
    ):
        first_season, first_week = CBWU_OI_COMPANION_V1_FIRST_LIVE
        raise RuntimeError(
            f"{CBWU_OI_CONTRACT_ENV}={CBWU_OI_FROZEN_V1} may not freeze a live "
            f"panel for {season} Week {week}: from {first_season} Week "
            f"{first_week} the shadow runs under {CBWU_OI_COMPANION_V1} "
            "(operator 2026-10-04). Use SHADOW_DRY_RUN=1 for a labelled "
            "non-live book or replay."
        )


def _cbwu_oi_build(environ: Mapping[str, str]) -> dict:
    """Contract-aware environment, receipt and identities for cbwu_oi."""
    contract = environ.get(CBWU_OI_CONTRACT_ENV)
    cbwu_oi_contract_settings(contract)  # refuse undeclared before building
    build, control = cbwu_oi_environment(contract, environ)
    panel_prefix, run_type = CBWU_OI_IDENTITIES[contract]
    return {
        "policy_env": build,
        "control_selector_env": control,
        "contract": check_cbwu_oi_contract(environ, build),
        "panel_prefix": panel_prefix,
        "candidate_run_type": run_type,
        "require_live": require_live_cbwu_oi_contract,
    }


def _validated_code_sha(value: object) -> str:
    code_sha = str(value or "").strip().lower()
    if not _CODE_SHA.fullmatch(code_sha):
        raise ValueError(
            "prospective shadow requires CODE_SHA as 7-40 lowercase hex digits"
        )
    return code_sha


def _canonical_dk_roster(
    lineup: Lineup, dk_id_by_player_id: dict[object, str | int],
) -> list[str]:
    try:
        ids = sorted(str(dk_id_by_player_id[player_id]) for player_id in lineup.ids)
    except KeyError as exc:
        raise ValueError(
            f"paired shadow lacks DK id for player {exc.args[0]}"
        ) from exc
    if len(ids) != 9 or len(set(ids)) != 9:
        raise ValueError("paired shadow selected roster is not exact-nine")
    return ids


def paired_shadow_receipt(
    control: CandidateBatch,
    treatment: CandidateBatch,
    treatment_lineups: list[Lineup],
    dk_id_by_player_id: dict[object, str | int],
    *,
    n_entries: int = 80,
    tail_line: float = 194.0,
    control_selector_env: dict[str, str] | None = None,
    shadow_version: str = PROSPECTIVE_PAIRED_SHADOW_VERSION,
) -> tuple[list[Lineup], dict]:
    """Validate one same-world pair and freeze exact 20/40/80 memberships."""
    _validate_candidate_batch(control)
    _validate_candidate_batch(treatment)
    if n_entries <= 0:
        raise ValueError("paired shadow entry count must be positive")
    if control.player_ids != treatment.player_ids:
        raise ValueError("paired shadow player order differs")
    if not np.array_equal(control.row_draws, treatment.row_draws):
        raise ValueError("paired shadow player worlds differ")
    if len(control.candidates) != len(treatment.candidates):
        raise ValueError("paired shadow candidate budgets differ")
    if control.candidate_totals.shape != treatment.candidate_totals.shape:
        raise ValueError("paired shadow score-world budgets differ")
    if len(treatment_lineups) != n_entries:
        raise ValueError(
            f"paired shadow treatment has {len(treatment_lineups)} entries, "
            f"expected {n_entries}"
        )
    treatment_universe = {lineup.ids for lineup in treatment.candidates}
    if (
        len({lineup.ids for lineup in treatment_lineups}) != n_entries
        or any(lineup.ids not in treatment_universe for lineup in treatment_lineups)
    ):
        raise ValueError("paired shadow treatment selection is invalid")
    picked = select_tail_entries(
        control.candidate_totals,
        n_entries,
        tail_line,
        env=control_selector_env,
    )
    control_lineups = [control.candidates[index] for index in picked]
    if len(control_lineups) != n_entries:
        raise ValueError("paired shadow control selection is not exact")

    control_dk = [
        _canonical_dk_roster(lineup, dk_id_by_player_id)
        for lineup in control_lineups
    ]
    treatment_dk = [
        _canonical_dk_roster(lineup, dk_id_by_player_id)
        for lineup in treatment_lineups
    ]
    sizes = sorted({min(size, n_entries) for size in (20, 40, 80)})
    memberships = {
        str(size): {
            "control": control_dk[:size],
            "treatment": treatment_dk[:size],
        }
        for size in sizes
    }
    control_candidates = {lineup.ids for lineup in control.candidates}
    treatment_candidates = {lineup.ids for lineup in treatment.candidates}
    return control_lineups, {
        "shadow_version": str(shadow_version),
        "tail_line": float(tail_line),
        "entries": int(n_entries),
        "candidate_budget": len(control.candidates),
        "worlds": int(control.row_draws.shape[1]),
        "player_worlds_identical": True,
        "candidate_budget_identical": True,
        "candidate_overlap": len(control_candidates & treatment_candidates),
        "candidate_union": len(control_candidates | treatment_candidates),
        "memberships": memberships,
        "uses_post_lock_outcomes": False,
        "production_enabled": False,
    }


SHADOW_VARIANTS = {
    "archetype": {
        "env_method": "archetype_shadow_environment",
        "panel_prefix": "prospective-archetype",
        "candidate_run_type": "prospective_archetype_shadow",
    },
    "cbwu_oi": {
        "env_method": "cbwu_oi_shadow_environment",
        "panel_prefix": "prospective-cbwu-oi",
        "candidate_run_type": "prospective_cbwu_oi_shadow",
        # O-27: the declared contract chooses environment, identities and
        # the live/dry-run rule (see _cbwu_oi_build).
        "contract_build": _cbwu_oi_build,
    },
    # B1 (2026-08-19): the volume-OI admission shadow. Same paired
    # control/treatment machinery; the treatment widens the CANDIDATE
    # books to twenty while world blocks and budget stay registered.
    "cbwu_volume": {
        "env_method": "cbwu_volume_shadow_environment",
        "panel_prefix": "prospective-cbwu-volume",
        "candidate_run_type": "prospective_cbwu_volume_shadow",
    },
}


def run_paired_prospective_shadow(
    *,
    variant: str = "archetype",
    store=None,
    season: int | None = None,
    week: int | None = None,
    draft_group_id: int | None = None,
    generated_at: datetime | None = None,
    storage_client=None,
    bucket_name: str | None = None,
) -> dict:
    """Build, pair-check, and durably freeze the control/treatment shadow.

    ``SHADOW_DRY_RUN=1`` (execution-scoped) runs and persists the complete
    path under identities no graded reader selects: a ``dryrun-`` panel id, a
    ``*_dryrun`` candidate run type and a ``recourse_worlds/dryrun/`` root
    outside the per-week panel tree (no paired shadow, live or dry, appends
    ``own_shadow``). The spec grades the
    earliest frozen panel of each week, so an undistinguished mid-week smoke
    would otherwise become that week's canonical panel.
    """
    if variant not in SHADOW_VARIANTS:
        raise ValueError(f"unknown prospective shadow variant {variant!r}")
    spec = SHADOW_VARIANTS[variant]
    code_sha = _validated_code_sha(os.environ.get("CODE_SHA"))
    from .tail_shadow import DRY_RUN_PANEL_PREFIX, shadow_dry_run

    dry_run = shadow_dry_run(os.environ)
    # The declared contract is checked before any warehouse read, so a job
    # that does not collect under one declared contract fails in seconds.
    policy = ADOPTED_CLASSIC_POLICY
    construction = policy.construction_preset()
    contract_build = spec.get("contract_build")
    if contract_build is not None:
        built = contract_build(os.environ)
        policy_env = built["policy_env"]
        control_selector_env = built["control_selector_env"]
        contract = built["contract"]
        panel_prefix = built["panel_prefix"]
        base_run_type = built["candidate_run_type"]
        require_live = built["require_live"]
    else:
        policy_env = getattr(policy, spec["env_method"])(os.environ)
        policy_env.update(construction.optimizer_environment())
        # These older prospective comparisons retain their frozen
        # pre-adoption population; they must not silently inherit the
        # Week-1 money switch.
        control_selector_env = policy.incumbent_control_environment(os.environ)
        contract = None
        panel_prefix = spec["panel_prefix"]
        base_run_type = spec["candidate_run_type"]
        require_live = None
    if store is None:
        from ..app.store import BigQueryStore

        store = BigQueryStore()
    if season is None or week is None or draft_group_id is None:
        from .tail_shadow import upcoming_season_week, sunday_main_group

        found_season, found_week, target_sunday = upcoming_season_week()
        season = found_season if season is None else season
        week = found_week if week is None else week
        if draft_group_id is None:
            draft_group_id = sunday_main_group(
                store.classic_slates(), target_sunday
            )
    season, week, draft_group_id = int(season), int(week), int(draft_group_id)
    if require_live is not None:
        require_live(contract["contract"], season, week, dry_run=dry_run)
    salaries = store.classic_salaries(draft_group_id)
    if salaries.empty:
        raise RuntimeError(f"Sunday-main draft group {draft_group_id} is empty")
    required = {"dk_player_id", "dk_draftable_id", "salary"}
    missing = required - set(salaries.columns)
    if missing:
        raise RuntimeError(
            "prospective shadow salary snapshot missing "
            + ", ".join(sorted(missing))
        )
    salaries = salaries.drop_duplicates("dk_player_id")
    if salaries[list(required)].isna().any().any():
        raise RuntimeError("prospective shadow salary snapshot is incomplete")
    allowed = {int(value) for value in salaries.dk_player_id}
    salary_overrides = {
        int(row.dk_player_id): int(row.salary)
        for row in salaries.itertuples()
    }
    dk_mapping = {
        int(row.dk_player_id): str(int(row.dk_draftable_id))
        for row in salaries.itertuples()
    }

    stamp = generated_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("prospective shadow generated_at must be timezone-aware")
    stamp = stamp.astimezone(timezone.utc)
    panel_run_id = (
        f"{DRY_RUN_PANEL_PREFIX if dry_run else ''}"
        f"{panel_prefix}-{season}w{week:02d}-"
        f"{stamp.strftime('%Y%m%dT%H%M%SZ')}"
    )
    candidate_run_type = (
        f"{base_run_type}{'_dryrun' if dry_run else ''}"
    )
    policy_env.update({
        "CAND_ARTIFACT_BUCKET": bucket_name or settings.gcs_bucket,
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "PROSPECTIVE_SHADOW_ID": panel_run_id,
    })
    control_capture: list[CandidateBatch] = []
    treatment_capture: list[CandidateBatch] = []
    from .live_lineups import build_sim_lineups

    treatment_lineups = build_sim_lineups(
        season,
        week,
        n_entries=PAIRED_SHADOW_ENTRIES,
        stack=construction.stack,
        tail_line=PAIRED_SHADOW_TAIL_LINE,
        lev_scale=1.0,
        allowed_ids=allowed,
        salary_overrides=salary_overrides,
        apply_notes=False,
        model_variant=policy.model_variant,
        cand_log_table=f"{settings.predictions}.live_candidates_shadow",
        cand_log_async=False,
        cand_log_required=True,
        panel_run_id=panel_run_id,
        candidate_run_type=candidate_run_type,
        policy_env=policy_env,
        construction_preset_receipt=construction.receipt(),
        expected_model_k=policy.model_ensemble,
        belief_model_variant=policy.role_model_variant,
        _candidate_capture=treatment_capture.append,
        _control_candidate_capture=control_capture.append,
        # O-27 (2026-10-05): a paired shadow never appends own_shadow, live or
        # dry. Every reader of that table takes a week's LATEST generation
        # (MAX(generated_at)); the table has no writer/run column, and in W1-W4
        # 2026 no other job wrote it after Thursday, so a Sunday shadow's
        # append would silently become "the pre-lock ownership prediction".
        # Ownership is not part of any paired shadow's contract.
        _log_ownership_shadow=False,
    )
    if len(control_capture) != 1 or len(treatment_capture) != 1:
        raise RuntimeError("prospective shadow did not capture one paired batch")
    control_lineups, paired = paired_shadow_receipt(
        control_capture[0],
        treatment_capture[0],
        treatment_lineups,
        dk_mapping,
        control_selector_env=control_selector_env,
    )
    del control_lineups  # memberships are durably retained in the receipt.
    bucket = bucket_name or settings.gcs_bucket
    root = (
        f"recourse_worlds/{'dryrun/' if dry_run else ''}"
        f"{season}/week-{week:02d}/{panel_run_id}"
    )
    context = {
        "season": season,
        "week": week,
        "draft_group_id": draft_group_id,
        "panel_run_id": panel_run_id,
        "code_sha": code_sha,
        "production_policy": policy.policy_id,
        "candidate_run_type": candidate_run_type,
        "dry_run": dry_run,
        "live": not dry_run,
    }
    if contract is not None:
        context["contract"] = contract
    control_artifact = persist_recourse_world_artifact(
        control_capture[0],
        dk_mapping,
        generated_at=stamp,
        bucket_name=bucket,
        object_name=f"{root}/control.npz",
        context={**context, "arm": "control"},
        storage_client=storage_client,
    )
    treatment_artifact = persist_recourse_world_artifact(
        treatment_capture[0],
        dk_mapping,
        generated_at=stamp,
        bucket_name=bucket,
        object_name=f"{root}/treatment.npz",
        context={**context, "arm": "treatment"},
        storage_client=storage_client,
    )
    manifest = {
        **context,
        **paired,
        "generated_at": stamp.isoformat(),
        "control_artifact": control_artifact,
        "treatment_artifact": treatment_artifact,
    }
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client()
    manifest_name = f"{root}/manifest.json"
    manifest_payload = json.dumps(
        manifest, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    storage_client.bucket(bucket).blob(manifest_name).upload_from_string(
        manifest_payload,
        content_type="application/json",
        if_generation_match=0,
    )
    manifest["manifest_uri"] = f"gs://{bucket}/{manifest_name}"
    manifest["manifest_sha256"] = manifest_sha256
    manifest["manifest_bytes"] = len(manifest_payload)
    manifest["manifest_create_only"] = True
    log.info(
        "froze paired prospective shadow %s: control=%s treatment=%s",
        panel_run_id,
        control_artifact["sha256"],
        treatment_artifact["sha256"],
    )
    return manifest


def main() -> None:
    print(json.dumps(run_paired_prospective_shadow(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()


__all__ = [
    "CBWU_OI_COMPANION_V1",
    "CBWU_OI_COMPANION_V1_KEYS",
    "CBWU_OI_CONTRACT_ENV",
    "CBWU_OI_CONTRACTS",
    "CBWU_OI_FROZEN_SETTINGS",
    "CBWU_OI_FROZEN_V1",
    "cbwu_oi_companion_v1_settings",
    "cbwu_oi_contract_settings",
    "cbwu_oi_environment",
    "cbwu_oi_job_environment",
    "check_cbwu_oi_contract",
    "require_live_cbwu_oi_contract",
    "PROSPECTIVE_PAIRED_SHADOW_VERSION",
    "paired_shadow_receipt",
    "run_paired_prospective_shadow",
]
