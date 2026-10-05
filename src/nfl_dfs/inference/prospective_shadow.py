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

# --- CBWU-OI collection contract (O-27, 2026-10-05) -------------------------
# reports/2026-08-18-cbwu-oi-prospective-shadow-spec.md froze the comparison
# (and its 2026-08-30 clarification froze the 160-leverage / 40-boom
# population). Every run from Week 1 to Week 4 then died on a stale image
# while the checker called the job "running". The job now has to DECLARE the
# contract it collects for (there is no default), and the settings the spec
# froze are literals here -- never derived from production_policy -- so a
# later edit of the incumbent allocation, the seeds or the selector fails this
# shadow closed instead of silently changing what it measures.
CBWU_OI_CONTRACT_ENV = "CBWU_OI_CONTRACT"
CBWU_OI_CONTRACT = "2026-cbwu-oi-v1"
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
# Fixed by every paired spec and passed by this runner, not by the environment.
PAIRED_SHADOW_ENTRIES = 80
PAIRED_SHADOW_TAIL_LINE = 194.0


def check_cbwu_oi_contract(
    environ: Mapping[str, str], policy_env: Mapping[str, str],
) -> dict:
    """Refuse a CBWU-OI run that is not the declared, frozen comparison.

    Returns the receipt frozen into the manifest: the contract name, every
    checked setting and the settings' canonical sha256.
    """
    declared = environ.get(CBWU_OI_CONTRACT_ENV)
    if declared != CBWU_OI_CONTRACT:
        raise RuntimeError(
            f"CBWU-OI shadow requires {CBWU_OI_CONTRACT_ENV}="
            f"{CBWU_OI_CONTRACT} on the job; got {declared!r}. There is no "
            "default: a job that does not declare the contract it collects "
            "for is refused."
        )
    wrong = {
        key: (policy_env.get(key), value)
        for key, value in CBWU_OI_FROZEN_SETTINGS.items()
        if policy_env.get(key) != value
    }
    if wrong:
        raise RuntimeError(
            "CBWU-OI shadow environment contradicts its frozen contract "
            f"(found, frozen): {wrong}"
        )
    settings_ = {
        **dict(sorted(CBWU_OI_FROZEN_SETTINGS.items())),
        "ENTRIES": str(PAIRED_SHADOW_ENTRIES),
        "TAIL_LINE": repr(PAIRED_SHADOW_TAIL_LINE),
    }
    return {
        "contract": CBWU_OI_CONTRACT,
        "settings": settings_,
        "settings_sha256": hashlib.sha256(json.dumps(
            settings_, sort_keys=True, separators=(",", ":"),
        ).encode("utf-8")).hexdigest(),
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
        "contract_check": check_cbwu_oi_contract,
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
    ``*_dryrun`` candidate run type, a ``recourse_worlds/dryrun/`` root outside
    the per-week panel tree, and no ``own_shadow`` append. The spec grades the
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
    # that does not collect the frozen comparison fails in seconds.
    policy = ADOPTED_CLASSIC_POLICY
    construction = policy.construction_preset()
    policy_env = getattr(policy, spec["env_method"])(os.environ)
    policy_env.update(construction.optimizer_environment())
    contract_check = spec.get("contract_check")
    contract = (
        contract_check(os.environ, policy_env)
        if contract_check is not None else None
    )
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
        f"{spec['panel_prefix']}-{season}w{week:02d}-"
        f"{stamp.strftime('%Y%m%dT%H%M%SZ')}"
    )
    candidate_run_type = (
        f"{spec['candidate_run_type']}{'_dryrun' if dry_run else ''}"
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
        _log_ownership_shadow=not dry_run,
    )
    if len(control_capture) != 1 or len(treatment_capture) != 1:
        raise RuntimeError("prospective shadow did not capture one paired batch")
    control_lineups, paired = paired_shadow_receipt(
        control_capture[0],
        treatment_capture[0],
        treatment_lineups,
        dk_mapping,
        # This older prospective comparison retains its frozen pre-adoption
        # population; it must not silently inherit the Week-1 money switch.
        control_selector_env=policy.incumbent_control_environment(os.environ),
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
    "CBWU_OI_CONTRACT",
    "CBWU_OI_CONTRACT_ENV",
    "CBWU_OI_FROZEN_SETTINGS",
    "check_cbwu_oi_contract",
    "PROSPECTIVE_PAIRED_SHADOW_VERSION",
    "paired_shadow_receipt",
    "run_paired_prospective_shadow",
]
