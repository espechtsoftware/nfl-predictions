"""Run one bounded canonical-CBWU pre-lock lineage shadow.

The runner is intentionally separate from the established generation-shadow
suite.  It changes no deployed policy, score, graph, or existing artifact
schema.  When explicitly invoked before lock, it writes an outcome-free input
authority, the detailed lineage envelope, and a candidate-only terminal root
with GCS create-once preconditions.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Final

from ..config import settings
from .prelock_candidate_lineage_v1 import (
    canonical_json_bytes,
    canonical_sha256,
)
from .prelock_lineage_runtime_v1 import (
    RuntimePrelockLineageRecorder,
    build_terminal_root_v1,
)
from .production_policy import ADOPTED_CLASSIC_POLICY
from .prospective_boom_first import _slate_identity
from .prospective_generation_shadow_suite import _draft_group_lock_at

VERSION: Final = "prospective-prelock-lineage-shadow/v1"
ENTRY_BUDGET: Final = 80
TAIL_LINE: Final = 194.0
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_IMPLEMENTATION_PATHS: Final = (
    "pyproject.toml",
    "src/nfl_dfs/backtest/engine.py",
    "src/nfl_dfs/cli.py",
    "src/nfl_dfs/inference/generation_exposure.py",
    "src/nfl_dfs/inference/live_lineups.py",
    "src/nfl_dfs/inference/multiseed_portfolio.py",
    "src/nfl_dfs/inference/prelock_candidate_lineage_v1.py",
    "src/nfl_dfs/inference/prelock_lineage_runtime_v1.py",
    "src/nfl_dfs/inference/production_policy.py",
    "src/nfl_dfs/inference/prospective_prelock_lineage_shadow_v1.py",
    "src/nfl_dfs/optimizer/lineup.py",
    "src/nfl_dfs/research/corpus_graph_vnext_contracts.py",
    "src/nfl_dfs/research/prelock_lineage_graph_summary_v1.py",
)


class ProspectivePrelockLineageShadowError(ValueError):
    """The bounded prospective lineage shadow violated its freeze law."""


def _fail(message: str) -> None:
    raise ProspectivePrelockLineageShadowError(message)


def _utc_seconds(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        _fail("lineage shadow timestamp must be timezone-aware")
    return value.astimezone(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def implementation_manifest_v1() -> dict[str, object]:
    """Hash the exact local code surface used by the bounded shadow."""

    repository = Path(__file__).resolve().parents[3]
    files = []
    for relative in _IMPLEMENTATION_PATHS:
        path = repository / relative
        if not path.is_file() or path.is_symlink():
            _fail(f"lineage implementation file is unavailable: {relative}")
        payload = path.read_bytes()
        files.append(
            {
                "path": relative,
                "sha256": sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    body: dict[str, object] = {
        "schema_version": "prelock-lineage-implementation-manifest/v1",
        "files": files,
    }
    body["implementation_sha256"] = canonical_sha256(body)
    return body


def _create_only_payload(
    storage_client,
    *,
    bucket_name: str,
    object_name: str,
    payload: bytes,
    content_type: str,
    must_precede: datetime,
) -> dict[str, object]:
    blob = storage_client.bucket(bucket_name).blob(object_name)
    try:
        blob.upload_from_string(
            payload,
            content_type=content_type,
            if_generation_match=0,
        )
    except Exception as upload_error:
        reload_blob = getattr(blob, "reload", None)
        download_blob = getattr(blob, "download_as_bytes", None)
        if not callable(reload_blob) or not callable(download_blob):
            raise ProspectivePrelockLineageShadowError(
                "create-once retry cannot exact-reopen the provider object"
            ) from upload_error
        try:
            reload_blob()
            existing = download_blob()
        except Exception as reopen_error:
            raise ProspectivePrelockLineageShadowError(
                "create-once publication failed and exact reopen failed"
            ) from reopen_error
        if bytes(existing) != payload:
            raise ProspectivePrelockLineageShadowError(
                "create-once provider object already exists with other bytes"
            ) from upload_error
    reload_blob = getattr(blob, "reload", None)
    if not callable(reload_blob):
        _fail("create-once object cannot prove trusted creation time")
    reload_blob()
    generation = getattr(blob, "generation", None)
    created = getattr(blob, "time_created", None)
    if generation in (None, ""):
        _fail("create-once object lacks a provider generation")
    if (
        created is None
        or getattr(created, "tzinfo", None) is None
        or created.utcoffset() is None
    ):
        _fail("create-once object lacks trusted creation time")
    created = created.astimezone(UTC)
    if created >= must_precede:
        _fail("create-once object was not provider-created before lock")
    return {
        "uri": f"gs://{bucket_name}/{object_name}",
        "generation": str(generation),
        "sha256": sha256(payload).hexdigest(),
        "bytes": len(payload),
        "time_created": created.isoformat(),
        "create_only": True,
    }


def _create_only_json(
    storage_client,
    *,
    bucket_name: str,
    object_name: str,
    value: Mapping[str, object],
    must_precede: datetime,
) -> dict[str, object]:
    return _create_only_payload(
        storage_client,
        bucket_name=bucket_name,
        object_name=object_name,
        payload=canonical_json_bytes(value),
        content_type="application/json",
        must_precede=must_precede,
    )


def run_prelock_lineage_shadow_v1(
    *,
    store,
    storage_client,
    bucket_name: str | None,
    run_id: str,
    season: int,
    week: int,
    draft_group_id: int,
    expected_lock_at: datetime | str,
    code_sha256: str,
    started_at: datetime | None = None,
    now_factory: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Build and create-once freeze one outcome-free canonical-CBWU trace."""

    if not isinstance(code_sha256, str) or _SHA256.fullmatch(code_sha256) is None:
        _fail("code_sha256 must be one lowercase SHA-256")
    implementation_manifest = implementation_manifest_v1()
    if code_sha256 != implementation_manifest["implementation_sha256"]:
        _fail("code_sha256 differs from the exact local implementation manifest")
    if not isinstance(run_id, str) or _RUN_ID.fullmatch(run_id) is None:
        _fail("run_id must be a canonical path-safe identifier")
    season, week, draft_group_id = int(season), int(week), int(draft_group_id)
    if season != 2026 or not 1 <= week <= 18 or draft_group_id <= 0:
        _fail("lineage shadow v1 requires one explicit 2026 slate")
    lock_at = _draft_group_lock_at(store, draft_group_id)
    if isinstance(expected_lock_at, str):
        try:
            expected_lock = datetime.fromisoformat(expected_lock_at)
        except ValueError as exc:
            raise ProspectivePrelockLineageShadowError(
                "expected_lock_at is invalid"
            ) from exc
    else:
        expected_lock = expected_lock_at
    if (
        expected_lock.tzinfo is None
        or expected_lock.utcoffset() is None
        or expected_lock.astimezone(UTC) != lock_at
    ):
        _fail("expected lock differs from the draft-group authority")

    def _now() -> datetime:
        value = datetime.now(UTC) if now_factory is None else now_factory()
        if value.tzinfo is None or value.utcoffset() is None:
            _fail("lineage shadow clock must be timezone-aware")
        return value.astimezone(UTC)

    stamp = started_at or _now()
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        _fail("lineage shadow start must be timezone-aware")
    stamp = stamp.astimezone(UTC)
    if stamp >= lock_at:
        _fail("lineage shadow started at or after slate lock")

    salaries = store.classic_salaries(draft_group_id)
    required = {"dk_player_id", "dk_draftable_id", "salary"}
    if salaries.empty or required - set(salaries.columns):
        _fail("lineage shadow salary catalog is incomplete")
    if salaries[list(required)].isna().any().any():
        _fail("lineage shadow salary identities are incomplete")
    if salaries["dk_player_id"].duplicated().any():
        _fail("lineage shadow salary catalog repeats an internal player ID")
    if salaries["dk_draftable_id"].duplicated().any():
        _fail("lineage shadow salary catalog repeats a draftable player ID")
    allowed, salary_overrides, dk_mapping = _slate_identity(store, draft_group_id)
    catalog_rows = sorted(
        (
            {
                "internal_player_id": str(int(row.dk_player_id)),
                "dk_draftable_id": str(int(row.dk_draftable_id)),
                "salary": int(row.salary),
            }
            for row in salaries.itertuples()
        ),
        key=lambda row: row["internal_player_id"],
    )
    salary_catalog_sha256 = canonical_sha256(catalog_rows)
    policy = ADOPTED_CLASSIC_POLICY
    construction = policy.construction_preset()
    environment = policy.engine_environment(construction_preset=construction)
    environment["PROSPECTIVE_GENERATION_EXPOSURE"] = "1"
    if environment.get("MULTISEED_PORTFOLIO") != "CBWU":
        _fail("lineage shadow requires canonical CBWU")
    bucket = bucket_name or settings.gcs_bucket
    root = f"prelock_lineage/{season}/week-{week:02d}/{run_id}"
    input_authority = {
        "schema_version": "prelock-lineage-input-authority/v1",
        "run_id": run_id,
        "season": season,
        "week": week,
        "slate_id": f"dk-{draft_group_id}",
        "draft_group_id": draft_group_id,
        "slate_lock_at_utc": _utc_seconds(lock_at),
        "code_sha256": code_sha256,
        "implementation_manifest": implementation_manifest,
        "policy_id": policy.policy_id,
        "policy_environment_sha256": canonical_sha256(
            dict(sorted(environment.items()))
        ),
        "policy_environment": dict(sorted(environment.items())),
        "construction_receipt": construction.receipt(),
        "salary_catalog_sha256": salary_catalog_sha256,
        "salary_catalog_rows": catalog_rows,
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
    }
    input_receipt = _create_only_json(
        storage_client,
        bucket_name=bucket,
        object_name=f"{root}/input-authority.json",
        value=input_authority,
        must_precede=lock_at,
    )
    run_header = {
        "run_id": run_id,
        "run_type": "prospective-lineage-shadow",
        "season": season,
        "week": week,
        "slate_id": f"dk-{draft_group_id}",
        "draft_group_id": draft_group_id,
        "contest_id": None,
        "slate_lock_at_utc": _utc_seconds(lock_at),
        "frozen_at_utc": None,
        "entry_budget": ENTRY_BUDGET,
        "policy_id": policy.policy_id,
        "selector_ids": ["binary-tail-coverage-v1"],
        "effective_candidate_stage_id": "effective-candidates",
        "paid_strategy_id": None,
        "code_sha256": code_sha256,
        "input_source_identities": [
            {
                key: input_receipt[key]
                for key in ("uri", "generation", "sha256", "bytes")
            }
            | {"role": "input-authority"}
        ],
    }
    candidate_receipts: list[dict[str, object]] = []
    matrix_receipts: list[dict[str, object]] = []

    def _publish_matrix(payload: bytes, identity: Mapping[str, object]) -> None:
        if matrix_receipts:
            _fail("selector matrix was published more than once")
        if (
            identity.get("schema_version") != "prelock-selector-matrix-raw/v1"
            or identity.get("sha256") != sha256(payload).hexdigest()
            or identity.get("bytes") != len(payload)
            or identity.get("uses_realized_outcomes") is not False
            or identity.get("post_lock_data_read") is not False
        ):
            _fail("selector matrix capture identity differs")
        matrix_receipts.append(
            _create_only_payload(
                storage_client,
                bucket_name=bucket,
                object_name=f"{root}/selector-matrix.raw",
                payload=payload,
                content_type="application/octet-stream",
                must_precede=lock_at,
            )
        )

    def _publish_candidate(value: Mapping[str, object]) -> None:
        if candidate_receipts:
            _fail("candidate lineage was published more than once")
        candidate_receipts.append(
            _create_only_json(
                storage_client,
                bucket_name=bucket,
                object_name=f"{root}/candidate-lineage.json",
                value=value,
                must_precede=lock_at,
            )
        )

    recorder = RuntimePrelockLineageRecorder(
        run_header=run_header,
        internal_to_draftable=dk_mapping,
        salary_catalog_sha256=salary_catalog_sha256,
        artifact_capture=_publish_candidate,
        matrix_artifact_capture=_publish_matrix,
        frozen_at_utc_factory=lambda: _utc_seconds(_now()),
    )
    from .live_lineups import build_sim_lineups

    lineups = build_sim_lineups(
        season,
        week,
        n_entries=ENTRY_BUDGET,
        stack=construction.stack,
        tail_line=TAIL_LINE,
        n_sims=int(environment["MULTISEED_WORLDS_PER_BLOCK"]),
        lev_scale=1.0,
        allowed_ids=allowed,
        salary_overrides=salary_overrides,
        apply_notes=False,
        model_variant=policy.model_variant,
        cand_log_table="",
        cand_log_async=False,
        cand_log_required=False,
        panel_run_id=run_id,
        candidate_run_type="prospective_prelock_lineage_shadow_v1",
        policy_env=environment,
        construction_preset_receipt=construction.receipt(),
        expected_model_k=policy.model_ensemble,
        belief_model_variant=policy.role_model_variant,
        _prelock_lineage_capture=recorder,
    )
    if len(lineups) != ENTRY_BUDGET or recorder.artifact is None:
        _fail("lineage shadow did not produce one exact candidate book")
    if len(candidate_receipts) != 1 or len(matrix_receipts) != 1:
        _fail("lineage shadow did not create one sidecar and selector matrix")
    if _now() >= lock_at:
        _fail("lineage shadow did not complete before lock")
    candidate_object = {
        key: candidate_receipts[0][key]
        for key in ("uri", "generation", "sha256", "bytes", "time_created")
    }
    terminal = build_terminal_root_v1(
        candidate_envelope=recorder.artifact,
        candidate_object_identity=candidate_object,
        selector_matrix_object_identity={
            key: matrix_receipts[0][key]
            for key in ("uri", "generation", "sha256", "bytes", "time_created")
        },
    )
    terminal_receipt = _create_only_json(
        storage_client,
        bucket_name=bucket,
        object_name=f"{root}/terminal.json",
        value=terminal,
        must_precede=lock_at,
    )
    if _now() >= lock_at:
        _fail("lineage graph summary cannot be frozen at or after lock")
    from ..research.prelock_lineage_graph_summary_v1 import (
        build_prelock_lineage_graph_summary_v1,
    )

    graph_summary = build_prelock_lineage_graph_summary_v1(
        candidate_envelope=recorder.artifact,
        terminal_root=terminal,
        terminal_object_identity={
            key: terminal_receipt[key]
            for key in ("uri", "generation", "sha256", "bytes", "time_created")
        },
        graph_release_id=f"prelock:{run_id}",
        created_at_utc=_utc_seconds(_now()),
    )
    graph_summary_receipt = _create_only_json(
        storage_client,
        bucket_name=bucket,
        object_name=f"{root}/graph-summary-v2.json",
        value=graph_summary,
        must_precede=lock_at,
    )
    return {
        "schema_version": VERSION,
        "complete": True,
        "run_id": run_id,
        "season": season,
        "week": week,
        "draft_group_id": draft_group_id,
        "input_authority": input_receipt,
        "candidate_lineage": candidate_receipts[0],
        "selector_matrix": matrix_receipts[0],
        "terminal": terminal_receipt,
        "graph_summary": graph_summary_receipt,
        "selected_roster_order_sha256": canonical_sha256(
            [sorted(str(value) for value in lineup.ids) for lineup in lineups]
        ),
        "uses_realized_outcomes": False,
        "post_lock_data_read": False,
        "production_enabled": False,
    }


def main(
    *,
    run_id: str,
    season: int,
    week: int,
    draft_group_id: int,
    expected_lock_at: str,
    code_sha256: str,
    bucket_name: str | None = None,
) -> None:
    from google.cloud import storage

    from ..app.store import BigQueryStore

    result = run_prelock_lineage_shadow_v1(
        store=BigQueryStore(),
        storage_client=storage.Client(),
        bucket_name=bucket_name,
        run_id=run_id,
        season=season,
        week=week,
        draft_group_id=draft_group_id,
        expected_lock_at=expected_lock_at,
        code_sha256=code_sha256,
    )
    print(json.dumps(result, sort_keys=True))


__all__ = [
    "ENTRY_BUDGET",
    "TAIL_LINE",
    "VERSION",
    "ProspectivePrelockLineageShadowError",
    "implementation_manifest_v1",
    "main",
    "run_prelock_lineage_shadow_v1",
]
