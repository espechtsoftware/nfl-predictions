"""Freeze the paired five-seed prospective SIS pass-tail portfolio."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..config import settings
from ..optimizer.construction_presets import (
    INCUMBENT_GPP_PRESET_ID,
    resolve_construction_preset_from_environment,
)
from .recourse_worlds import persist_recourse_world_artifact
from .sis_pass_tail_shadow import (
    CONTROL_TABLE,
    ENTRIES,
    PROTOCOL_VERSION,
    SEEDS,
    TABLES,
    TAIL_LINE,
    TREATMENT_TABLE,
    WORLDS,
    arm_environment,
    environment_failures,
)


_CODE_SHA = re.compile(r"^[0-9a-f]{7,40}$")


def cache_pair_receipt(
    control: pd.DataFrame,
    treatment: pd.DataFrame,
    *,
    season: int,
    week: int,
    code_sha: str,
) -> dict:
    """Prove that the two live caches share one target/source identity."""
    keys = ["season", "week", "gsis_id"]
    metadata = {
        "protocol_version", "code_sha", "training_source_checksum",
        "inference_source_checksum", "sis_source_checksum",
        "sis_source_run_ids",
    }
    required = {*keys, "arm", "mean", "q99", *metadata}
    for name, rows, arm in (
        ("control", control, "control"),
        ("treatment", treatment, "treatment"),
    ):
        if missing := required - set(rows.columns):
            raise ValueError(f"{name} live pass-tail cache lacks {sorted(missing)}")
        if rows.empty or rows.duplicated(keys).any():
            raise ValueError(f"{name} live pass-tail cache keys are invalid")
        if not rows.season.eq(season).all() or not rows.week.eq(week).all():
            raise ValueError(f"{name} live pass-tail cache target differs")
        if set(rows.arm.astype(str)) != {arm}:
            raise ValueError(f"{name} live pass-tail arm identity differs")
        if set(rows.protocol_version.astype(str)) != {PROTOCOL_VERSION}:
            raise ValueError(f"{name} live pass-tail protocol differs")
        if set(rows.code_sha.astype(str)) != {code_sha}:
            raise ValueError(f"{name} live pass-tail code SHA differs")
        for field in metadata:
            if rows[field].astype(str).nunique(dropna=False) != 1:
                raise ValueError(f"{name} live pass-tail {field} is not singular")
    left = control.set_index(keys).sort_index()
    right = treatment.set_index(keys).sort_index()
    if not left.index.equals(right.index):
        raise ValueError("live pass-tail cache player keys differ")
    for field in metadata:
        if str(left[field].iloc[0]) != str(right[field].iloc[0]):
            raise ValueError(f"live pass-tail cache {field} differs")
    qcols = sorted(
        column for column in control.columns
        if column.startswith("q") and column[1:].isdigit()
    )
    if not qcols or not set(qcols) <= set(treatment.columns):
        raise ValueError("live pass-tail cache quantile schema differs")
    changed = ~np.isclose(
        left[["mean", *qcols]].to_numpy(float),
        right[["mean", *qcols]].to_numpy(float),
        rtol=0,
        atol=1e-12,
    )
    if not changed.any():
        raise ValueError("live pass-tail treatment cache is inert")
    return {
        "control_table": CONTROL_TABLE,
        "treatment_table": TREATMENT_TABLE,
        "rows_per_arm": int(len(left)),
        "changed_player_distribution_rows": int(changed.any(axis=1).sum()),
        "training_source_checksum": str(left.training_source_checksum.iloc[0]),
        "inference_source_checksum": str(left.inference_source_checksum.iloc[0]),
        "sis_source_checksum": str(left.sis_source_checksum.iloc[0]),
        "sis_source_run_ids": str(left.sis_source_run_ids.iloc[0]),
        "code_sha": code_sha,
    }


def _membership(lineups, dk_mapping: dict[int, str]) -> list[list[str]]:
    output = []
    for lineup in lineups:
        try:
            roster = sorted(dk_mapping[int(player_id)] for player_id in lineup.ids)
        except KeyError as exc:
            raise ValueError(f"pass-tail lineup lacks DK id for {exc.args[0]}") from exc
        if len(roster) != 9 or len(set(roster)) != 9:
            raise ValueError("pass-tail lineup is not exact-nine")
        output.append(roster)
    if len(output) != ENTRIES or len({tuple(row) for row in output}) != ENTRIES:
        raise ValueError("pass-tail selected book is not exact-80 unique")
    return output


def run(
    *, store=None, season: int | None = None, week: int | None = None,
    draft_group_id: int | None = None, generated_at: datetime | None = None,
    storage_client=None, bucket_name: str | None = None,
) -> dict:
    """Build all ten books and create a single complete-grid manifest."""
    code_sha = str(os.environ.get("CODE_SHA", "")).strip().lower()
    if not _CODE_SHA.fullmatch(code_sha):
        raise ValueError("prospective SIS pass-tail requires immutable CODE_SHA")
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
    if season != 2026:
        raise ValueError("prospective SIS pass-tail v1 is frozen to 2026")
    if week < 5:
        return {
            "disposition": "prospective-sis-pass-tail-not-yet-eligible",
            "protocol_version": PROTOCOL_VERSION,
            "season": season,
            "week": week,
            "minimum_week": 5,
        }

    salaries = store.classic_salaries(draft_group_id).drop_duplicates(
        "dk_player_id"
    )
    required = {"dk_player_id", "dk_draftable_id", "salary"}
    if salaries.empty or (required - set(salaries)):
        raise ValueError("prospective pass-tail salary snapshot is incomplete")
    if salaries[list(required)].isna().any().any():
        raise ValueError("prospective pass-tail salary identity is incomplete")
    allowed = {int(value) for value in salaries.dk_player_id}
    salary_overrides = {
        int(row.dk_player_id): int(row.salary) for row in salaries.itertuples()
    }
    dk_mapping = {
        int(row.dk_player_id): str(int(row.dk_draftable_id))
        for row in salaries.itertuples()
    }
    from ..bq import query_df

    cache_frames = {
        arm: query_df(f"""
            SELECT * FROM `{settings.features}.{table}`
            WHERE season=@season AND week=@week
        """, params={"season": season, "week": week})
        for arm, table in TABLES.items()
    }
    cache_receipt = cache_pair_receipt(
        cache_frames["control"], cache_frames["treatment"],
        season=season, week=week, code_sha=code_sha,
    )
    stamp = generated_at or datetime.now(timezone.utc)
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("prospective pass-tail generated_at must be timezone-aware")
    stamp = stamp.astimezone(timezone.utc)
    run_id = (
        f"prospective-sis-pass-tail-{season}w{week:02d}-"
        f"{stamp.strftime('%Y%m%dT%H%M%SZ')}"
    )
    bucket = bucket_name or settings.gcs_bucket
    root = f"sis_pass_tail_shadow/{season}/week-{week:02d}/{run_id}"
    from .live_lineups import build_sim_lineups
    from .route_share_shadow import ROLE_FEATURES

    books = {}
    for label, (projection_seed, role_seed) in SEEDS.items():
        for arm in ("control", "treatment"):
            env = dict(os.environ)
            env.update(arm_environment(
                arm, projection_seed=projection_seed, role_seed=role_seed,
            ))
            construction = resolve_construction_preset_from_environment(
                INCUMBENT_GPP_PRESET_ID, env,
            )
            env.update(construction.optimizer_environment())
            env["CAND_ARTIFACT_BUCKET"] = bucket
            if failures := environment_failures(arm, env):
                raise ValueError(
                    f"prospective pass-tail {label}/{arm} drift: {failures}"
                )
            panel_id = f"{run_id}-{label.lower()}-{arm}"
            captured = []
            lineups = build_sim_lineups(
                season,
                week,
                n_entries=ENTRIES,
                stack=construction.stack,
                tail_line=TAIL_LINE,
                n_sims=WORLDS,
                seed=projection_seed,
                lev_scale=1.0,
                allowed_ids=allowed,
                salary_overrides=salary_overrides,
                apply_notes=False,
                model_variant="tail_k1",
                cand_log_table=f"{settings.predictions}.live_candidates_shadow",
                cand_log_async=False,
                cand_log_required=True,
                panel_run_id=panel_id,
                candidate_run_type="prospective_sis_pass_tail",
                policy_env=env,
                construction_preset_receipt=construction.receipt(),
                expected_model_k=1,
                belief_model_variant="tail_k1_role",
                model_forbidden_features=ROLE_FEATURES,
                belief_required_features=ROLE_FEATURES,
                _candidate_capture=captured.append,
            )
            if len(captured) != 1:
                raise RuntimeError("pass-tail build did not capture one candidate book")
            context = {
                "protocol_version": PROTOCOL_VERSION,
                "run_id": run_id,
                "panel_run_id": panel_id,
                "season": season,
                "week": week,
                "draft_group_id": draft_group_id,
                "seed_label": label,
                "projection_seed": projection_seed,
                "role_seed": role_seed,
                "arm": arm,
                "code_sha": code_sha,
                "cache_table": TABLES[arm],
            }
            artifact = persist_recourse_world_artifact(
                captured[0],
                dk_mapping,
                generated_at=stamp,
                bucket_name=bucket,
                object_name=f"{root}/{label.lower()}-{arm}.npz",
                context=context,
                storage_client=storage_client,
            )
            books[f"{label}-{arm}"] = {
                **context,
                "entries": ENTRIES,
                "tail_line": TAIL_LINE,
                "memberships": _membership(lineups, dk_mapping),
                "artifact": artifact,
            }
    if set(books) != {
        f"{label}-{arm}" for label in SEEDS for arm in ("control", "treatment")
    }:
        raise RuntimeError("prospective pass-tail book grid is incomplete")
    manifest = {
        "disposition": "prospective-sis-pass-tail-shadow-frozen",
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "generated_at": stamp.isoformat(),
        "season": season,
        "week": week,
        "draft_group_id": draft_group_id,
        "code_sha": code_sha,
        "cache_pair": cache_receipt,
        "books": books,
        "uses_post_lock_outcomes": False,
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
        payload, content_type="application/json", if_generation_match=0,
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


__all__ = ["cache_pair_receipt", "run"]
