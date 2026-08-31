"""Paired five-seed runner for the outcome-unseen 2026 latent-role shadow."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

from ..backtest.engine import CandidateBatch
from ..config import settings
from .latent_role_shadow import create_live_latent_role_scenario_factory
from .production_policy import ADOPTED_CLASSIC_POLICY
from .prospective_shadow import _validated_code_sha, paired_shadow_receipt
from .recourse_worlds import persist_recourse_world_artifact


VERSION = "prospective-latent-role-paired-shadow-v1"
ENTRIES = 80
TAIL_LINE = 194.0


def validate_latent_seed_receipts(batch: CandidateBatch) -> dict:
    """Fail closed unless every R0--R4 scenario/optimization ledger exists."""
    metadata = batch.metadata
    if metadata.get("portfolio") != "CBWU_LATENT_ROLE_SHADOW":
        raise ValueError("latent-role paired treatment portfolio differs")
    if metadata.get("uses_realized_outcomes") is not False:
        raise ValueError("latent-role paired treatment is not score-free")
    receipts = metadata.get("latent_seed_receipts")
    expected = {"R0", "R1", "R2", "R3", "R4"}
    if not isinstance(receipts, dict) or set(receipts) != expected:
        raise ValueError("latent-role paired seed receipt grid is incomplete")
    summary = {}
    for label in sorted(expected):
        item = receipts[label]
        scenario = item.get("latent_scenario_receipt")
        optimization = list(item.get("latent_optimization_receipt", ()))
        if (
            not isinstance(scenario, dict)
            or scenario.get("uses_realized_outcomes") is not False
            or scenario.get("uses_fantasy_or_lineup_outcomes") is not False
            or scenario.get("source_label") != label
            or int(scenario.get("promotion_scenarios", -1)) != 4
            or int(scenario.get("sampled_cap_valid_scenarios", -1)) < 8
        ):
            raise ValueError(f"latent-role {label} scenario receipt is invalid")
        accepted = [
            row for row in optimization if row.get("disposition") == "accepted"
        ]
        promotions = [row for row in accepted if row.get("kind") == "promotion"]
        sampled = [row for row in accepted if row.get("kind") == "sampled"]
        if len(promotions) != 4 or len(sampled) != 8:
            raise ValueError(
                f"latent-role {label} optimization receipt is not exact 4+8"
            )
        if any(
            not isinstance(row.get("roster_sha256"), str)
            or len(row["roster_sha256"]) != 64
            for row in accepted
        ):
            raise ValueError(f"latent-role {label} roster hashes are invalid")
        summary[label] = {
            "scenario_receipt": scenario,
            "optimization_receipt": optimization,
            "accepted_promotions": 4,
            "accepted_sampled": 8,
        }
    return summary


def _slate_identity(store, draft_group_id: int):
    salaries = store.classic_salaries(draft_group_id).drop_duplicates(
        "dk_player_id"
    )
    required = {"dk_player_id", "dk_draftable_id", "salary"}
    if salaries.empty or required - set(salaries.columns):
        raise RuntimeError("latent-role salary snapshot is incomplete")
    if salaries[list(required)].isna().any().any():
        raise RuntimeError("latent-role salary identity is incomplete")
    allowed = {int(value) for value in salaries.dk_player_id}
    salary_overrides = {
        int(row.dk_player_id): int(row.salary) for row in salaries.itertuples()
    }
    dk_mapping = {
        int(row.dk_player_id): str(int(row.dk_draftable_id))
        for row in salaries.itertuples()
    }
    return allowed, salary_overrides, dk_mapping


def run(
    *,
    store=None,
    season: int | None = None,
    week: int | None = None,
    draft_group_id: int | None = None,
    generated_at: datetime | None = None,
    storage_client=None,
    bucket_name: str | None = None,
) -> dict:
    """Build, pair-check and create-only persist control/treatment books."""
    code_sha = _validated_code_sha(os.environ.get("CODE_SHA"))
    if store is None:
        from ..app.store import BigQueryStore

        store = BigQueryStore()
    if season is None or week is None or draft_group_id is None:
        from .tail_shadow import upcoming_season_week, sunday_main_group

        found_season, found_week, sunday = upcoming_season_week()
        season = found_season if season is None else season
        week = found_week if week is None else week
        if draft_group_id is None:
            draft_group_id = sunday_main_group(store.classic_slates(), sunday)
    season, week, draft_group_id = int(season), int(week), int(draft_group_id)
    if season != 2026 or not 1 <= week <= 18:
        raise ValueError("latent-role paired shadow v1 is frozen to 2026")
    stamp = generated_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("latent-role generated_at must be timezone-aware")
    stamp = stamp.astimezone(timezone.utc)
    run_id = (
        f"prospective-latent-role-{season}w{week:02d}-"
        f"{stamp.strftime('%Y%m%dT%H%M%SZ')}"
    )
    bucket = bucket_name or settings.gcs_bucket
    root = f"latent_role_shadow/{season}/week-{week:02d}/{run_id}"
    allowed, salary_overrides, dk_mapping = _slate_identity(
        store, draft_group_id,
    )
    factory = create_live_latent_role_scenario_factory(
        season=season,
        week=week,
        as_of=stamp,
        code_sha=code_sha,
        bucket_name=bucket,
        object_name=f"{root}/transition-artifact.json",
        storage_client=storage_client,
    )
    policy = ADOPTED_CLASSIC_POLICY
    construction = policy.construction_preset()
    common = {
        "season": season,
        "week": week,
        "n_entries": ENTRIES,
        "stack": construction.stack,
        "tail_line": TAIL_LINE,
        "lev_scale": 1.0,
        "allowed_ids": allowed,
        "salary_overrides": salary_overrides,
        "apply_notes": False,
        "model_variant": policy.model_variant,
        "cand_log_table": f"{settings.predictions}.live_candidates_shadow",
        "cand_log_async": False,
        "cand_log_required": True,
        "expected_model_k": policy.model_ensemble,
        "belief_model_variant": policy.role_model_variant,
        "construction_preset_receipt": construction.receipt(),
    }
    from .live_lineups import build_sim_lineups

    control_capture: list[CandidateBatch] = []
    # This shadow was frozen against the pre-adoption 160/40 population.
    # Keep that comparator explicit now that the money path is boom-first.
    control_env = policy.incumbent_control_environment(os.environ)
    control_env.update({
        "CAND_ARTIFACT_BUCKET": bucket,
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "PROSPECTIVE_SHADOW_ID": run_id,
    })
    control_lineups = build_sim_lineups(
        **common,
        panel_run_id=f"{run_id}-control",
        candidate_run_type="prospective_latent_role_control",
        policy_env=control_env,
        _candidate_capture=control_capture.append,
    )

    treatment_capture: list[CandidateBatch] = []
    treatment_env = policy.latent_role_shadow_environment(os.environ)
    treatment_env.update({
        "CAND_ARTIFACT_BUCKET": bucket,
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
        "PROSPECTIVE_SHADOW_ID": run_id,
    })
    treatment_lineups = build_sim_lineups(
        **common,
        panel_run_id=f"{run_id}-treatment",
        candidate_run_type="prospective_latent_role_treatment",
        policy_env=treatment_env,
        _candidate_capture=treatment_capture.append,
        _latent_scenario_factory=factory,
    )
    if len(control_capture) != 1 or len(treatment_capture) != 1:
        raise RuntimeError("latent-role paired shadow did not capture both books")
    if len(control_lineups) != ENTRIES:
        raise RuntimeError("latent-role control selection is not exact-80")
    _, paired = paired_shadow_receipt(
        control_capture[0],
        treatment_capture[0],
        treatment_lineups,
        dk_mapping,
        n_entries=ENTRIES,
        tail_line=TAIL_LINE,
        control_selector_env=control_env,
        shadow_version=VERSION,
    )
    if paired["candidate_overlap"] == paired["candidate_budget"]:
        raise RuntimeError("latent-role treatment is candidate-inert")
    seed_receipts = validate_latent_seed_receipts(treatment_capture[0])
    if len(factory.receipts) != 5:
        raise RuntimeError("latent-role factory did not emit five seed receipts")

    context = {
        "shadow_version": VERSION,
        "run_id": run_id,
        "season": season,
        "week": week,
        "draft_group_id": draft_group_id,
        "code_sha": code_sha,
        "production_policy": policy.policy_id,
    }
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
        "transition_artifact": factory.artifact_receipt,
        "seed_receipts": seed_receipts,
        "control_artifact": control_artifact,
        "treatment_artifact": treatment_artifact,
        "uses_post_lock_outcomes": False,
        "uses_fantasy_or_lineup_outcomes": False,
        "production_enabled": False,
    }
    payload = json.dumps(
        manifest, separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    if storage_client is None:
        from google.cloud import storage

        storage_client = storage.Client()
    name = f"{root}/manifest.json"
    storage_client.bucket(bucket).blob(name).upload_from_string(
        payload,
        content_type="application/json",
        if_generation_match=0,
    )
    return {
        **manifest,
        "manifest_uri": f"gs://{bucket}/{name}",
        "manifest_sha256": digest,
        "manifest_bytes": len(payload),
        "manifest_create_only": True,
    }


def main() -> None:
    print(json.dumps(run(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()


__all__ = ["ENTRIES", "TAIL_LINE", "VERSION", "run", "validate_latent_seed_receipts"]
