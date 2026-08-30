"""Create-once operator boundary for the construction x allocation cross.

The scientific builder remains storage-agnostic.  This module turns a valid
score-blind receipt into a two-object, root-last publication plan, publishes
through injected create-once/exact-read callbacks, and independently reopens
the terminal graph.  It has no outcome API and performs no cloud operation at
import time.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Final

from . import corpus_r6_construction_allocation_cross_v1 as cross


READY_SCHEMA: Final = "corpus-r6-construction-allocation-ready-bundle/v1"
TERMINAL_SCHEMA: Final = "corpus-r6-construction-allocation-terminal/v1"
TERMINAL_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-construction-allocation-terminal-envelope/v1"
)
LOCK_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-construction-allocation-common-lock-authority/v1"
)
AUDIT_BANK_PLACEHOLDER_SCHEMA: Final = (
    "corpus-r6-construction-allocation-unconsumed-audit-placeholder/v1"
)
RUNTIME_BUILD_ATTESTATION_SCHEMA: Final = (
    "corpus-r6-construction-allocation-runtime-build-attestation/v1"
)
RUNTIME_EXECUTION_ATTESTATION_SCHEMA: Final = (
    "corpus-r6-construction-allocation-runtime-execution-attestation/v1"
)
SELECTION_EXECUTION_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-construction-allocation-selection-execution-authority/v1"
)
MULTIPLICITY_FAMILY_SCHEMA: Final = (
    "corpus-r6-construction-allocation-multiplicity-family/v1"
)
MULTIPLICITY_FAMILY_ID: Final = (
    "construction-preset-x-allocation-four-cell-descriptive-v1"
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ConstructionAllocationCrossOperatorError(ValueError):
    """The create-once publication or exact reopen contract differs."""


PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]
ReadExact = Callable[[Mapping[str, object]], bytes]


def _fail(message: str) -> None:
    raise ConstructionAllocationCrossOperatorError(message)


def _canonical_document(value: Mapping[str, object]) -> bytes:
    return cross.canonical_json_bytes(dict(value)) + b"\n"


def _canonical_authority(value: Mapping[str, object]) -> bytes:
    """Canonical upstream authorities never carry the publication newline."""

    return cross.canonical_json_bytes(dict(value))


def _parse_document(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw.endswith(b"\n"):
        _fail(f"{label} bytes are not canonical newline-terminated JSON")
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ConstructionAllocationCrossOperatorError(
            f"{label} JSON differs"
        ) from exc
    if not isinstance(value, Mapping) or _canonical_document(value) != raw:
        _fail(f"{label} canonical replay differs")
    return dict(value)


def _parse_authority(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} bytes differ")
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ConstructionAllocationCrossOperatorError(
            f"{label} JSON differs"
        ) from exc
    canonical = _canonical_authority(value) if isinstance(value, Mapping) else b""
    if not isinstance(value, Mapping) or raw not in {canonical, canonical + b"\n"}:
        _fail(f"{label} canonical replay differs")
    return dict(value)


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> dict[str, object]:
    item = dict(value)
    retained = item.pop(field, None)
    if (
        type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or cross.canonical_sha256(item) != retained
    ):
        _fail(f"{label} self-hash differs")
    item[field] = retained
    return item


def _with_self_hash(
    body: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    retained = dict(body)
    retained[field] = cross.canonical_sha256(retained)
    return retained


def multiplicity_family_v1() -> dict[str, object]:
    """The one explicit descriptive family carried by this four-cell cross."""

    body: dict[str, object] = {
        "schema_version": MULTIPLICITY_FAMILY_SCHEMA,
        "family_id": MULTIPLICITY_FAMILY_ID,
        "experiment_version": cross.VERSION,
        "cell_order": list(cross.CELL_ORDER),
        "primary_estimand": (
            "k80-weekly-max-allocation-effect-difference-by-construction-preset"
        ),
        "family_role": "separate-preseason-descriptive-diagnostic",
        "automatic_policy_promotion": False,
        "production_policy_authority": False,
    }
    return _with_self_hash(body, field="multiplicity_family_sha256")


def validate_multiplicity_family_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("multiplicity family is not a mapping")
    item = _self_hash(
        value,
        field="multiplicity_family_sha256",
        label="multiplicity family",
    )
    if item != multiplicity_family_v1():
        _fail("multiplicity family differs")
    return item


def common_lock_authority_v1(
    *, slate_id: str, input_frame_receipts: Mapping[str, object],
    lock_id: str,
) -> dict[str, object]:
    """Build the minimal typed lock used by injected PIT-frame replays.

    The production fixed later-source freeze uses its existing stricter
    validator instead.  This document exists only for a custom PIT source
    manifest and binds the exact logical input-frame receipts without a
    circular reference to the source manifest that embeds its identity.
    """

    retained_slate = str(slate_id).strip()
    retained_lock = str(lock_id).strip()
    if _ID.fullmatch(retained_slate) is None or _ID.fullmatch(retained_lock) is None:
        _fail("common lock slate or ID differs")
    receipts = dict(input_frame_receipts)
    if not receipts:
        _fail("common lock input-frame receipts are empty")
    body: dict[str, object] = {
        "schema_version": LOCK_AUTHORITY_SCHEMA,
        "lock_id": retained_lock,
        "slate_id": retained_slate,
        "source_schema_version": cross.SOURCE_MANIFEST_SCHEMA,
        "input_frame_receipts_sha256": cross.canonical_sha256(receipts),
        "locked_before_selection": True,
        "target_slate_outcomes_read": False,
        "post_lock_data_read": False,
    }
    return _with_self_hash(body, field="lock_authority_sha256")


def audit_bank_placeholder_v1(
    *, slate_id: str, placeholder_id: str,
) -> dict[str, object]:
    """Declare truthfully that no independent audit bank is yet available.

    This placeholder is never evaluation authority.  It permits the
    outcome-blind selection freeze to name its missing diagnostic dependency
    without inventing an independent bank or claiming that one was consumed.
    """

    retained_slate = str(slate_id).strip()
    retained_placeholder = str(placeholder_id).strip()
    if (
        _ID.fullmatch(retained_slate) is None
        or _ID.fullmatch(retained_placeholder) is None
    ):
        _fail("unconsumed audit placeholder differs")
    body: dict[str, object] = {
        "schema_version": AUDIT_BANK_PLACEHOLDER_SCHEMA,
        "placeholder_id": retained_placeholder,
        "slate_id": retained_slate,
        "role": "unconsumed-audit-placeholder",
        "independent_bank_available": False,
        "independent_from_selection_bank": False,
        "evaluation_authority": False,
        "opened_during_selection": False,
        "uses_target_slate_outcomes": False,
    }
    return _with_self_hash(body, field="audit_placeholder_sha256")


def runtime_build_attestation_v1(
    *, build_id: str, source_repository: str, requested_source_commit: str,
    resolved_source_commit: str, image_tag: str, image_digest: str,
    provider_observed_at: str,
) -> dict[str, object]:
    """Normalize the provider-observed build fact into a frozen authority."""

    retained_build = str(build_id).strip()
    repository = str(source_repository).strip()
    requested = str(requested_source_commit).strip().lower()
    resolved = str(resolved_source_commit).strip().lower()
    tag = str(image_tag).strip()
    digest = str(image_digest).strip().lower()
    observed_at = _utc_timestamp(provider_observed_at, label="provider_observed_at")
    if (
        _ID.fullmatch(retained_build) is None
        or not repository
        or requested != resolved
        or _COMMIT.fullmatch(requested) is None
        or not tag
        or _IMAGE.fullmatch(digest) is None
    ):
        _fail("runtime build attestation facts differ")
    body: dict[str, object] = {
        "schema_version": RUNTIME_BUILD_ATTESTATION_SCHEMA,
        "provider": "google-cloud-build-v1-api",
        "build_id": retained_build,
        "status": "SUCCESS",
        "source_repository": repository,
        "requested_source_commit": requested,
        "resolved_source_commit": resolved,
        "image_tag": tag,
        "image_digest": digest,
        "provider_observed_at": observed_at,
        "provider_observed": True,
        "uses_target_slate_outcomes": False,
    }
    return _with_self_hash(body, field="runtime_build_attestation_sha256")


def validate_runtime_build_attestation_v1(
    value: object, *, expected_code_sha: str, expected_image_digest: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("runtime build attestation is not a mapping")
    item = _self_hash(
        value,
        field="runtime_build_attestation_sha256",
        label="runtime build attestation",
    )
    expected_keys = {
        "schema_version", "provider", "build_id", "status",
        "source_repository", "requested_source_commit",
        "resolved_source_commit", "image_tag", "image_digest",
        "provider_observed_at", "provider_observed",
        "uses_target_slate_outcomes", "runtime_build_attestation_sha256",
    }
    if (
        set(item) != expected_keys
        or item.get("schema_version") != RUNTIME_BUILD_ATTESTATION_SCHEMA
        or item.get("provider") != "google-cloud-build-v1-api"
        or item.get("status") != "SUCCESS"
        or _ID.fullmatch(str(item.get("build_id", ""))) is None
        or type(item.get("source_repository")) is not str
        or not item["source_repository"]
        or item.get("requested_source_commit")
        != item.get("resolved_source_commit")
        or _COMMIT.fullmatch(str(item.get("resolved_source_commit", ""))) is None
        or item.get("resolved_source_commit") != expected_code_sha
        or type(item.get("image_tag")) is not str
        or not item["image_tag"]
        or item.get("image_digest") != expected_image_digest
        or _IMAGE.fullmatch(str(item.get("image_digest", ""))) is None
        or item.get("provider_observed") is not True
        or item.get("uses_target_slate_outcomes") is not False
    ):
        _fail("runtime build attestation differs from selection code/image")
    _utc_timestamp(str(item.get("provider_observed_at", "")), label="provider_observed_at")
    return item


def runtime_execution_attestation_v1(
    *, project_id: str, region: str, job_name: str, job_generation: str,
    execution_name: str, execution_uid: str, task_count: int,
    succeeded_count: int, failed_count: int, cancelled_count: int,
    running_count: int, code_sha: str, image_digest: str,
    provider_observed_at: str,
) -> dict[str, object]:
    """Normalize the provider-observed 54-task Cloud Run execution fact."""

    project = str(project_id).strip()
    retained_region = str(region).strip()
    job = str(job_name).strip()
    generation = str(job_generation).strip()
    execution = str(execution_name).strip()
    uid = str(execution_uid).strip()
    code = str(code_sha).strip().lower()
    image = str(image_digest).strip().lower()
    observed_at = _utc_timestamp(
        provider_observed_at, label="execution provider_observed_at"
    )
    counts = (task_count, succeeded_count, failed_count, cancelled_count,
              running_count)
    if (
        not project
        or not retained_region
        or _ID.fullmatch(job) is None
        or not generation
        or _ID.fullmatch(execution) is None
        or not uid
        or any(type(value) is not int or value < 0 for value in counts)
        or task_count <= 0
        or succeeded_count != task_count
        or failed_count != 0
        or cancelled_count != 0
        or running_count != 0
        or _COMMIT.fullmatch(code) is None
        or _IMAGE.fullmatch(image) is None
    ):
        _fail("runtime execution attestation facts differ")
    body: dict[str, object] = {
        "schema_version": RUNTIME_EXECUTION_ATTESTATION_SCHEMA,
        "provider": "google-cloud-run-v2-api",
        "project_id": project,
        "region": retained_region,
        "job_name": job,
        "job_generation": generation,
        "execution_name": execution,
        "execution_uid": uid,
        "task_count": task_count,
        "succeeded_count": succeeded_count,
        "failed_count": failed_count,
        "cancelled_count": cancelled_count,
        "running_count": running_count,
        "status": "SUCCEEDED",
        "code_sha": code,
        "image_digest": image,
        "provider_observed_at": observed_at,
        "provider_observed": True,
        "uses_target_slate_outcomes": False,
    }
    return _with_self_hash(body, field="runtime_execution_attestation_sha256")


def validate_runtime_execution_attestation_v1(
    value: object, *, expected_code_sha: str, expected_image_digest: str,
    expected_task_count: int,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("runtime execution attestation is not a mapping")
    item = _self_hash(
        value,
        field="runtime_execution_attestation_sha256",
        label="runtime execution attestation",
    )
    expected_keys = {
        "schema_version", "provider", "project_id", "region", "job_name",
        "job_generation", "execution_name", "execution_uid", "task_count",
        "succeeded_count", "failed_count", "cancelled_count",
        "running_count", "status", "code_sha", "image_digest",
        "provider_observed_at", "provider_observed",
        "uses_target_slate_outcomes", "runtime_execution_attestation_sha256",
    }
    if (
        set(item) != expected_keys
        or item.get("schema_version") != RUNTIME_EXECUTION_ATTESTATION_SCHEMA
        or item.get("provider") != "google-cloud-run-v2-api"
        or type(item.get("project_id")) is not str
        or not item["project_id"]
        or type(item.get("region")) is not str
        or not item["region"]
        or _ID.fullmatch(str(item.get("job_name", ""))) is None
        or not str(item.get("job_generation", ""))
        or _ID.fullmatch(str(item.get("execution_name", ""))) is None
        or not str(item.get("execution_uid", ""))
        or item.get("task_count") != expected_task_count
        or item.get("succeeded_count") != expected_task_count
        or item.get("failed_count") != 0
        or item.get("cancelled_count") != 0
        or item.get("running_count") != 0
        or item.get("status") != "SUCCEEDED"
        or item.get("code_sha") != expected_code_sha
        or item.get("image_digest") != expected_image_digest
        or item.get("provider_observed") is not True
        or item.get("uses_target_slate_outcomes") is not False
    ):
        _fail("runtime execution attestation differs from selection runtime")
    _utc_timestamp(
        str(item.get("provider_observed_at", "")),
        label="execution provider_observed_at",
    )
    return item


def selection_execution_authority_v1(
    *, input_manifest_identity: Mapping[str, object],
    input_manifest_sha256: str,
    ordered_shard_identities: Sequence[Mapping[str, object]],
    runtime_execution_attestation_identity: Mapping[str, object],
) -> dict[str, object]:
    """Bind the exact manifest, 54 worker shards, and provider execution."""

    manifest_identity = cross._content_identity(
        input_manifest_identity, label="selection input manifest"
    )
    manifest_sha = str(input_manifest_sha256).strip().lower()
    if _SHA256.fullmatch(manifest_sha) is None:
        _fail("selection input manifest self-hash differs")
    if isinstance(ordered_shard_identities, (str, bytes, bytearray)):
        _fail("ordered shard identities differ")
    shards = [
        cross._content_identity(identity, label=f"selection shard[{ordinal}]")
        for ordinal, identity in enumerate(ordered_shard_identities)
    ]
    if (
        len(shards) != len(cross.EXPECTED_SLATE_IDS)
        or len({identity["uri"] for identity in shards}) != len(shards)
    ):
        _fail("ordered shard identities do not cover the fixed panel")
    execution_identity = cross._content_identity(
        runtime_execution_attestation_identity,
        label="runtime execution attestation",
    )
    body: dict[str, object] = {
        "schema_version": SELECTION_EXECUTION_AUTHORITY_SCHEMA,
        "input_manifest_identity": manifest_identity,
        "input_manifest_sha256": manifest_sha,
        "ordered_shard_identities": shards,
        "ordered_shard_identities_sha256": cross.canonical_sha256(shards),
        "runtime_execution_attestation_identity": execution_identity,
        "task_count": len(shards),
        "uses_target_slate_outcomes": False,
    }
    return _with_self_hash(body, field="execution_authority_sha256")


def validate_selection_execution_authority_v1(
    value: object,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("selection execution authority is not a mapping")
    item = _self_hash(
        value,
        field="execution_authority_sha256",
        label="selection execution authority",
    )
    expected_keys = {
        "schema_version", "input_manifest_identity", "input_manifest_sha256",
        "ordered_shard_identities", "ordered_shard_identities_sha256",
        "runtime_execution_attestation_identity", "task_count",
        "uses_target_slate_outcomes", "execution_authority_sha256",
    }
    if (
        set(item) != expected_keys
        or item.get("schema_version") != SELECTION_EXECUTION_AUTHORITY_SCHEMA
        or item.get("task_count") != len(cross.EXPECTED_SLATE_IDS)
        or item.get("uses_target_slate_outcomes") is not False
        or _SHA256.fullmatch(str(item.get("input_manifest_sha256", ""))) is None
    ):
        _fail("selection execution authority differs")
    return selection_execution_authority_v1(
        input_manifest_identity=item["input_manifest_identity"],
        input_manifest_sha256=str(item["input_manifest_sha256"]),
        ordered_shard_identities=item["ordered_shard_identities"],
        runtime_execution_attestation_identity=item[
            "runtime_execution_attestation_identity"
        ],
    )


def _utc_timestamp(value: str, *, label: str) -> str:
    if type(value) is not str or not value.endswith("Z"):
        _fail(f"{label} must be an explicit UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ConstructionAllocationCrossOperatorError(
            f"{label} differs"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        _fail(f"{label} is not UTC")
    return value


def _identity(
    value: object, *, label: str, expected_uri: str | None = None,
    expected_raw: bytes | None = None,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a create-once identity")
    uri = value.get("uri")
    generation = value.get("generation")
    digest = value.get("sha256")
    size = value.get("bytes")
    create_once = value.get("create_once")
    if (
        type(uri) is not str
        or not uri
        or type(generation) not in {str, int}
        or not str(generation)
        or type(digest) is not str
        or _SHA256.fullmatch(digest) is None
        or type(size) is not int
        or size <= 0
        or create_once is not True
    ):
        _fail(f"{label} create-once identity differs")
    if expected_uri is not None and uri != expected_uri:
        _fail(f"{label} URI differs")
    if expected_raw is not None and (
        size != len(expected_raw)
        or digest != hashlib.sha256(expected_raw).hexdigest()
    ):
        _fail(f"{label} byte identity differs")
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": digest,
        "bytes": size,
        "create_once": True,
    }


def _read_identity_bytes(
    identity: Mapping[str, object], *, read_exact: ReadExact, label: str,
) -> bytes:
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or hashlib.sha256(raw).hexdigest()
        != identity["sha256"]
    ):
        _fail(f"{label} exact content identity differs")
    return raw


def _reopen_fixed_g0_panel_v1(
    selection: Mapping[str, object], *, read_exact: ReadExact,
) -> dict[str, object]:
    """Deep-validate the fixed panel, not merely its four identity strings."""

    from . import corpus_r6_full_union_panel_freeze_v1 as fixed_panel

    raw_authority = selection.get("panel_authority")
    if not isinstance(raw_authority, Mapping):
        _fail("selection panel authority differs")
    identity = cross._content_identity(
        raw_authority.get("identity"), label="fixed G0 panel authority"
    )
    if identity != cross.FOUNDRY_G0_PANEL_IDENTITY:
        _fail("fixed G0 panel identity differs")
    try:
        panel, members, reopened_identity = fixed_panel.reopen_fixed_panel_v1(
            identity, read_exact=read_exact
        )
    except Exception as exc:
        raise ConstructionAllocationCrossOperatorError(
            "fixed G0 panel exact reopen or schema validation differs"
        ) from exc
    expected_slates = [str(row["slate_id"]) for row in selection["slates"]]
    member_slates = [str(member["slate_id"]) for member in members]
    if (
        reopened_identity != identity
        or panel.get("panel_id") != cross.FOUNDRY_G0_PANEL_ID
        or panel.get("panel_index_sha256")
        != cross.FOUNDRY_G0_PANEL_ID.removeprefix("v12:")
        or member_slates != expected_slates
    ):
        _fail("fixed G0 panel membership binding differs")
    return {
        "role": "fixed-g0-panel",
        "identity": identity,
        "panel_id": panel["panel_id"],
        "panel_index_sha256": panel["panel_index_sha256"],
        "accepted_slate_ids_sha256": cross.canonical_sha256(member_slates),
        "accepted_slate_count": len(member_slates),
        "generation_exact_reopened": True,
        "schema_and_self_hash_validated": True,
    }


def _validate_common_lock_v1(
    raw: bytes, *, identity: Mapping[str, object], slate_id: str,
    source_document: Mapping[str, object],
) -> dict[str, object]:
    document = _parse_authority(raw, label=f"{slate_id} common lock")
    schema = document.get("schema_version")
    source_schema = source_document.get("schema_version")
    if source_schema == cross.SOURCE_MANIFEST_SCHEMA:
        item = _self_hash(
            document, field="lock_authority_sha256",
            label=f"{slate_id} common lock",
        )
        expected_keys = {
            "schema_version", "lock_id", "slate_id", "source_schema_version",
            "input_frame_receipts_sha256", "locked_before_selection",
            "target_slate_outcomes_read", "post_lock_data_read",
            "lock_authority_sha256",
        }
        if (
            set(item) != expected_keys
            or schema != LOCK_AUTHORITY_SCHEMA
            or item.get("slate_id") != slate_id
            or _ID.fullmatch(str(item.get("lock_id", ""))) is None
            or item.get("source_schema_version") != cross.SOURCE_MANIFEST_SCHEMA
            or item.get("input_frame_receipts_sha256")
            != cross.canonical_sha256(source_document["input_frame_receipts"])
            or item.get("locked_before_selection") is not True
            or item.get("target_slate_outcomes_read") is not False
            or item.get("post_lock_data_read") is not False
        ):
            _fail(f"{slate_id} common lock authority differs")
        return {
            "schema_version": schema,
            "internal_sha256": item["lock_authority_sha256"],
            "identity": dict(identity),
            "validation_mode": "typed-pit-frame-lock-authority",
        }

    # Frozen historical snapshots point at the already published full
    # later-source freeze.  Reuse its exhaustive schema/self-hash validator.
    if source_schema == cross.frozen_allocation.GENERATION_SNAPSHOT_SCHEMA:
        from . import corpus_r6_player_catalog_fixed_g0_adapter_v1 as fixed_source

        try:
            pins = fixed_source._normalize_pins(fixed_source.FIXED_PINS)
            normalized, *_ = fixed_source._validate_later_source(
                document, normalized_pins=pins
            )
        except Exception as exc:
            raise ConstructionAllocationCrossOperatorError(
                f"{slate_id} fixed later-source lock validation differs"
            ) from exc
        expected_identity = cross._content_identity(
            fixed_source.FIXED_LATER_SOURCE_IDENTITY,
            label="fixed later-source identity",
        )
        if identity != expected_identity:
            _fail(f"{slate_id} fixed later-source identity differs")
        return {
            "schema_version": normalized.get("schema"),
            "internal_sha256": normalized["freeze_sha256"],
            "identity": dict(identity),
            "validation_mode": "published-fixed-later-source-freeze",
        }
    _fail(f"{slate_id} has no supported common-lock authority schema")


def _validate_audit_bank_v1(
    raw: bytes, *, identity: Mapping[str, object], slate_id: str,
    world_blocks: list[str], worlds_per_block: int, read_exact: ReadExact,
) -> dict[str, object]:
    document = _parse_authority(raw, label=f"{slate_id} audit bank")
    schema = document.get("schema_version")
    from . import corpus_r6_independent_bank_contract_v1 as bank_contract

    if schema == bank_contract.PLAN_SCHEMA:
        try:
            plan = bank_contract.validate_independent_bank_plan_v1(
                document, read_exact=read_exact
            )
        except Exception as exc:
            raise ConstructionAllocationCrossOperatorError(
                f"{slate_id} independent selection/audit bank plan differs"
            ) from exc
        root = plan["audit_bank_root"]
        members = list(root["members"])
        if (
            {str(member["slate_id"]) for member in members} != {slate_id}
            or len(members) != len(world_blocks)
            or sorted(int(member["block_ordinal"]) for member in members)
            != list(range(len(world_blocks)))
            or any(
                int(member["player_draws"]["shape"][1]) != worlds_per_block
                for member in members
            )
        ):
            _fail(f"{slate_id} independent audit plan coverage differs")
        return {
            "schema_version": schema,
            "internal_sha256": plan["independent_bank_plan_sha256"],
            "identity": dict(identity),
            "validation_mode": "independent-selection-audit-bank-plan",
            "member_count": root["member_count"],
            "independent_bank_available": True,
            "independence_from_selection_bank_verified": True,
            "evaluation_authority": True,
        }

    if schema == bank_contract.DRAW_BANK_ROOT_SCHEMA:
        try:
            root = bank_contract.validate_draw_bank_root_v1(
                document, expected_role="audit"
            )
        except Exception as exc:
            raise ConstructionAllocationCrossOperatorError(
                f"{slate_id} independent audit draw-bank root differs"
            ) from exc
        members = list(root["members"])
        if (
            {str(member["slate_id"]) for member in members} != {slate_id}
            or len(members) != len(world_blocks)
            or sorted(int(member["block_ordinal"]) for member in members)
            != list(range(len(world_blocks)))
            or any(
                int(member["player_draws"]["shape"][1]) != worlds_per_block
                for member in members
            )
        ):
            _fail(f"{slate_id} audit draw-bank slate coverage differs")
        return {
            "schema_version": schema,
            "internal_sha256": root["draw_bank_root_sha256"],
            "identity": dict(identity),
            "validation_mode": "independent-draw-bank-root",
            "member_count": root["member_count"],
            "independent_bank_available": True,
            "independence_from_selection_bank_verified": False,
            "evaluation_authority": False,
        }

    item = _self_hash(
        document,
        field="audit_placeholder_sha256",
        label=f"{slate_id} unconsumed audit placeholder",
    )
    expected_keys = {
        "schema_version", "placeholder_id", "slate_id", "role",
        "independent_bank_available", "independent_from_selection_bank",
        "evaluation_authority", "opened_during_selection",
        "uses_target_slate_outcomes", "audit_placeholder_sha256",
    }
    if (
        set(item) != expected_keys
        or schema != AUDIT_BANK_PLACEHOLDER_SCHEMA
        or _ID.fullmatch(str(item.get("placeholder_id", ""))) is None
        or item.get("slate_id") != slate_id
        or item.get("role") != "unconsumed-audit-placeholder"
        or item.get("independent_bank_available") is not False
        or item.get("independent_from_selection_bank") is not False
        or item.get("evaluation_authority") is not False
        or item.get("opened_during_selection") is not False
        or item.get("uses_target_slate_outcomes") is not False
    ):
        _fail(f"{slate_id} unconsumed audit placeholder differs")
    return {
        "schema_version": schema,
        "internal_sha256": item["audit_placeholder_sha256"],
        "identity": dict(identity),
        "validation_mode": "typed-unconsumed-audit-placeholder",
        "member_count": 0,
        "independent_bank_available": False,
        "independence_from_selection_bank_verified": False,
        "evaluation_authority": False,
    }


def _reopen_runtime_build_attestation_v1(
    identity_value: object, *, selection: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    identity = cross._content_identity(
        identity_value, label="runtime build attestation"
    )
    raw = _read_identity_bytes(
        identity, read_exact=read_exact, label="runtime build attestation"
    )
    attestation = validate_runtime_build_attestation_v1(
        _parse_authority(raw, label="runtime build attestation"),
        expected_code_sha=str(selection["code_sha"]),
        expected_image_digest=str(selection["image_digest"]),
    )
    return {
        "identity": identity,
        "runtime_build_attestation_sha256": attestation[
            "runtime_build_attestation_sha256"
        ],
        "build_id": attestation["build_id"],
        "source_commit": attestation["resolved_source_commit"],
        "image_digest": attestation["image_digest"],
        "generation_exact_reopened": True,
        "schema_and_self_hash_validated": True,
        "provider_observed": True,
    }


def verify_upstream_authorities_v1(
    selection_receipt: Mapping[str, object], *,
    runtime_build_attestation_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Deep, generation-exact reopen of every publication prerequisite."""

    selection = cross.validate_score_blind_cross_v1(selection_receipt)
    if not callable(read_exact):
        _fail("upstream exact-read callback is not callable")
    panel_reopen = _reopen_fixed_g0_panel_v1(selection, read_exact=read_exact)
    runtime_reopen = _reopen_runtime_build_attestation_v1(
        runtime_build_attestation_identity,
        selection=selection,
        read_exact=read_exact,
    )
    records: list[dict[str, object]] = []
    audit_statuses: list[dict[str, object]] = []
    for slate in selection["slates"]:
        slate_id = str(slate["slate_id"])
        source_identity = cross._content_identity(
            slate["source_identity"], label=f"{slate_id} source-manifest"
        )
        source_raw = _read_identity_bytes(
            source_identity, read_exact=read_exact,
            label=f"{slate_id} source-manifest",
        )
        source_document = _parse_authority(
            source_raw, label=f"{slate_id} source document"
        )
        _, descriptor = cross._source_document_descriptor_v1(
            source_document,
            source_identity=source_identity,
            season=int(slate["season"]),
            week=int(slate["week"]),
            slate_id=slate_id,
            audit_bank_identity=slate["audit_bank_identity"],
        )
        if descriptor != slate["source_descriptor"]:
            _fail(f"{slate_id} source descriptor exact reopen differs")
        records.append({
            "slate_id": slate_id,
            "role": "source-manifest",
            "identity": source_identity,
            "schema_version": source_document.get("schema_version"),
            "canonical_replay_validated": True,
        })

        lock_identity = cross._content_identity(
            slate["lock_identity"], label=f"{slate_id} common-lock"
        )
        lock_validation = _validate_common_lock_v1(
            _read_identity_bytes(
                lock_identity, read_exact=read_exact,
                label=f"{slate_id} common-lock",
            ),
            identity=lock_identity,
            slate_id=slate_id,
            source_document=source_document,
        )
        records.append({
            "slate_id": slate_id,
            "role": "common-lock",
            **lock_validation,
        })

        audit_identity = cross._content_identity(
            slate["audit_bank_identity"], label=f"{slate_id} audit-bank"
        )
        audit_validation = _validate_audit_bank_v1(
            _read_identity_bytes(
                audit_identity, read_exact=read_exact,
                label=f"{slate_id} audit-bank",
            ),
            identity=audit_identity,
            slate_id=slate_id,
            world_blocks=[str(value) for value in selection["seed_labels"]],
            worlds_per_block=int(selection["worlds_per_block"]),
            read_exact=read_exact,
        )
        records.append({
            "slate_id": slate_id,
            "role": "audit-bank",
            **audit_validation,
        })
        audit_statuses.append(audit_validation)
    evaluation_authority_count = sum(
        status["evaluation_authority"] is True for status in audit_statuses
    )
    bank_root_count = sum(
        status["independent_bank_available"] is True
        for status in audit_statuses
    )
    placeholder_count = len(audit_statuses) - bank_root_count
    root_without_disjoint_selection_count = (
        bank_root_count - evaluation_authority_count
    )
    body: dict[str, object] = {
        "schema_version": (
            "corpus-r6-construction-allocation-upstream-reopen/v1"
        ),
        "slate_count": len(selection["slates"]),
        "exact_read_count": len(records) + 2,
        "records_sha256": cross.canonical_sha256(records),
        "fixed_g0_panel_reopen": panel_reopen,
        "runtime_build_attestation_reopen": runtime_reopen,
        "fixed_g0_panel_generation_exact_reopened": True,
        "runtime_code_image_provider_attestation_exact_reopened": True,
        "all_sources_generation_exact_reopened": True,
        "all_locks_generation_exact_reopened": True,
        "all_audit_authority_documents_generation_exact_reopened": True,
        "all_locks_schema_and_self_hash_validated": True,
        "all_audit_authority_documents_schema_and_self_hash_validated": True,
        "independent_audit_bank_root_count": bank_root_count,
        "independent_audit_evaluation_authority_count": (
            evaluation_authority_count
        ),
        "audit_bank_root_without_disjoint_selection_authority_count": (
            root_without_disjoint_selection_count
        ),
        "unconsumed_audit_placeholder_count": placeholder_count,
        "independent_audit_evaluation_authority_available": (
            evaluation_authority_count == len(audit_statuses)
        ),
        "audit_placeholders_have_evaluation_authority": False,
        "audit_bank_payload_used_for_selection": False,
        "outcome_data_accessed": False,
    }
    return {**body, "receipt_sha256": cross.canonical_sha256(body)}


def verify_selection_execution_authority_v1(
    selection_receipt: Mapping[str, object], *,
    execution_authority: Mapping[str, object], read_exact: ReadExact,
) -> dict[str, object]:
    """Deep-replay the manifest, all 54 shards, and Cloud Run execution."""

    from . import corpus_r6_construction_allocation_shard_v1 as shard_science

    selection = cross.validate_score_blind_cross_v1(selection_receipt)
    authority = validate_selection_execution_authority_v1(execution_authority)
    if not callable(read_exact):
        _fail("execution authority exact-read callback is not callable")

    manifest_identity = authority["input_manifest_identity"]
    manifest_raw = _read_identity_bytes(
        manifest_identity, read_exact=read_exact,
        label="selection input manifest",
    )
    manifest = _parse_document(manifest_raw, label="selection input manifest")
    manifest_body = dict(manifest)
    retained_manifest_sha = manifest_body.pop("manifest_sha256", None)
    task_bindings = manifest.get("task_bindings")
    expected_slates = list(cross.EXPECTED_SLATE_IDS)
    if (
        retained_manifest_sha != authority["input_manifest_sha256"]
        or retained_manifest_sha != cross.canonical_sha256(manifest_body)
        or manifest.get("schema_version")
        != "corpus-r6-construction-allocation-snapshot-shard-manifest/v1"
        or manifest.get("run_id") != selection["panel_id"]
        or manifest.get("code_sha") != selection["code_sha"]
        or manifest.get("image_digest") != selection["image_digest"]
        or manifest.get("task_count") != len(expected_slates)
        or manifest.get("expected_slate_ids") != expected_slates
        or not isinstance(task_bindings, list)
        or len(task_bindings) != len(expected_slates)
        or manifest.get("task_bindings_sha256")
        != cross.canonical_sha256(task_bindings)
        or manifest.get("foundry_g0_panel_id") != cross.FOUNDRY_G0_PANEL_ID
        or cross._content_identity(
            manifest.get("foundry_g0_panel_identity"), label="manifest G0 panel"
        ) != cross.FOUNDRY_G0_PANEL_IDENTITY
        or manifest.get("uses_target_slate_outcomes") is not False
        or manifest.get("target_slate_outcome_columns") != []
    ):
        _fail("selection input manifest predecessor closure differs")

    shard_roots: list[dict[str, object]] = []
    shard_records: list[dict[str, object]] = []
    for ordinal, (slate_id, identity, binding) in enumerate(zip(
        expected_slates,
        authority["ordered_shard_identities"],
        task_bindings,
        strict=True,
    )):
        if not isinstance(binding, Mapping):
            _fail(f"selection task binding[{ordinal}] differs")
        shard_identity = cross._content_identity(
            identity, label=f"selection shard[{ordinal}]"
        )
        if (
            binding.get("source_ordinal") != ordinal
            or binding.get("slate_id") != slate_id
            or binding.get("shard_uri") != shard_identity["uri"]
        ):
            _fail(f"selection task binding[{ordinal}] differs")
        shard_raw = _read_identity_bytes(
            shard_identity, read_exact=read_exact,
            label=f"selection shard[{ordinal}]",
        )
        try:
            shard = shard_science.validate_score_blind_cross_shard_v1(
                _parse_document(shard_raw, label=f"selection shard[{ordinal}]")
            )
        except Exception as exc:
            raise ConstructionAllocationCrossOperatorError(
                f"selection shard[{ordinal}] predecessor replay differs"
            ) from exc
        coordinate = shard["expected_slate_coordinate"]
        if (
            coordinate.get("ordinal") != ordinal
            or coordinate.get("slate_id") != slate_id
            or shard.get("panel_id") != selection["panel_id"]
            or shard.get("code_sha") != selection["code_sha"]
            or shard.get("image_digest") != selection["image_digest"]
        ):
            _fail(f"selection shard[{ordinal}] authority differs")
        shard_roots.append(shard)
        shard_records.append({
            "ordinal": ordinal,
            "slate_id": slate_id,
            "identity": shard_identity,
            "shard_sha256": shard["shard_sha256"],
            "scientific_sha256": shard["scientific_sha256"],
        })
    try:
        replayed_selection = shard_science.collect_score_blind_cross_shards_v1(
            shard_roots
        )
    except Exception as exc:
        raise ConstructionAllocationCrossOperatorError(
            "selection shard predecessor collection differs"
        ) from exc
    if replayed_selection != selection:
        _fail("selection does not replay from its declared ordered shards")

    execution_identity = authority["runtime_execution_attestation_identity"]
    execution_raw = _read_identity_bytes(
        execution_identity, read_exact=read_exact,
        label="runtime execution attestation",
    )
    execution = validate_runtime_execution_attestation_v1(
        _parse_authority(execution_raw, label="runtime execution attestation"),
        expected_code_sha=str(selection["code_sha"]),
        expected_image_digest=str(selection["image_digest"]),
        expected_task_count=len(expected_slates),
    )
    if any(
        shard["execution_observations"]["runtime_execution_coordinate"].get(
            "job_name"
        ) != execution["job_name"]
        or shard["execution_observations"]["runtime_execution_coordinate"].get(
            "execution_name"
        ) != execution["execution_name"]
        or shard["execution_observations"]["runtime_execution_coordinate"].get(
            "task_index"
        ) != ordinal
        or shard["execution_observations"]["runtime_execution_coordinate"].get(
            "task_count"
        ) != len(expected_slates)
        for ordinal, shard in enumerate(shard_roots)
    ):
        _fail("declared shards do not belong to the attested Cloud Run execution")
    body: dict[str, object] = {
        "schema_version": (
            "corpus-r6-construction-allocation-execution-reopen/v1"
        ),
        "execution_authority_sha256": authority[
            "execution_authority_sha256"
        ],
        "input_manifest_identity": manifest_identity,
        "input_manifest_sha256": retained_manifest_sha,
        "ordered_shard_identities_sha256": authority[
            "ordered_shard_identities_sha256"
        ],
        "ordered_shard_records_sha256": cross.canonical_sha256(shard_records),
        "runtime_execution_attestation_identity": execution_identity,
        "runtime_execution_attestation_sha256": execution[
            "runtime_execution_attestation_sha256"
        ],
        "runtime_job_name": execution["job_name"],
        "runtime_job_generation": execution["job_generation"],
        "runtime_execution_name": execution["execution_name"],
        "runtime_execution_uid": execution["execution_uid"],
        "task_count": len(expected_slates),
        "all_shards_generation_exact_reopened": True,
        "all_shards_schema_and_scientific_hash_validated": True,
        "selection_replayed_from_declared_shards": True,
        "all_shards_match_runtime_execution": True,
        "runtime_execution_provider_attestation_exact_reopened": True,
        "uses_target_slate_outcomes": False,
    }
    return {**body, "receipt_sha256": cross.canonical_sha256(body)}


def prepare_create_once_bundle_v1(
    selection_receipt: Mapping[str, object],
    *, run_id: str, output_prefix: str, frozen_at: str,
    runtime_build_attestation_identity: Mapping[str, object],
    execution_authority: Mapping[str, object],
) -> dict[str, object]:
    """Prepare exact bytes and URIs without mutating storage."""

    selection = cross.validate_score_blind_cross_v1(selection_receipt)
    retained_run_id = str(run_id).strip()
    if _ID.fullmatch(retained_run_id) is None:
        _fail("run ID differs")
    prefix = str(output_prefix).strip().rstrip("/")
    if not prefix.startswith("gs://") or "//" in prefix[5:]:
        _fail("output prefix must be one normalized GCS prefix")
    retained_frozen_at = _utc_timestamp(frozen_at, label="frozen_at")
    runtime_identity = cross._content_identity(
        runtime_build_attestation_identity,
        label="runtime build attestation",
    )
    retained_execution_authority = validate_selection_execution_authority_v1(
        execution_authority
    )
    multiplicity = multiplicity_family_v1()
    selection_uri = f"{prefix}/{retained_run_id}/selection.json"
    terminal_uri = f"{prefix}/{retained_run_id}/terminal.json"
    if selection_uri == terminal_uri:
        _fail("selection and terminal URIs must differ")
    selection_raw = _canonical_document(selection)
    body: dict[str, object] = {
        "schema_version": READY_SCHEMA,
        "version": cross.VERSION,
        "run_id": retained_run_id,
        "frozen_at": retained_frozen_at,
        "selection_uri": selection_uri,
        "selection_sha256": hashlib.sha256(
            selection_raw
        ).hexdigest(),
        "selection_bytes": len(selection_raw),
        "selection_receipt_sha256": selection["receipt_sha256"],
        "selection_scientific_sha256": selection["scientific_sha256"],
        "runtime_build_attestation_identity": runtime_identity,
        "execution_authority": retained_execution_authority,
        "execution_authority_sha256": retained_execution_authority[
            "execution_authority_sha256"
        ],
        "multiplicity_family": multiplicity,
        "multiplicity_family_sha256": multiplicity[
            "multiplicity_family_sha256"
        ],
        "terminal_uri": terminal_uri,
        "publication_order": ["selection", "terminal-root-last"],
        "publication_mode": "create-once-if-generation-match-zero-exact-reopen",
        "status": "ready-for-create-once-publication",
        "uses_target_slate_outcomes": False,
        "post_lock_data_read": False,
        "cloud_mutation_performed": False,
        "automatic_policy_promotion": False,
    }
    return {
        **body,
        "ready_sha256": cross.canonical_sha256(body),
        # Raw bytes are execution material and deliberately excluded from the
        # canonical ready hash above.
        "selection_raw": selection_raw,
    }


def validate_ready_bundle_v1(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("ready bundle is not a mapping")
    item = dict(value)
    selection_raw = item.pop("selection_raw", None)
    retained = item.pop("ready_sha256", None)
    if (
        type(selection_raw) is not bytes
        or type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or cross.canonical_sha256(item) != retained
        or item.get("schema_version") != READY_SCHEMA
        or item.get("status") != "ready-for-create-once-publication"
        or item.get("publication_order") != ["selection", "terminal-root-last"]
        or item.get("uses_target_slate_outcomes") is not False
        or item.get("post_lock_data_read") is not False
        or item.get("cloud_mutation_performed") is not False
    ):
        _fail("ready bundle differs")
    runtime_identity = cross._content_identity(
        item.get("runtime_build_attestation_identity"),
        label="ready runtime build attestation",
    )
    execution_authority = validate_selection_execution_authority_v1(
        item.get("execution_authority")
    )
    multiplicity = validate_multiplicity_family_v1(
        item.get("multiplicity_family")
    )
    if (
        item.get("runtime_build_attestation_identity") != runtime_identity
        or item.get("execution_authority_sha256")
        != execution_authority["execution_authority_sha256"]
        or item.get("multiplicity_family_sha256")
        != multiplicity["multiplicity_family_sha256"]
    ):
        _fail("ready authority binding differs")
    selection = cross.validate_score_blind_cross_v1(
        _parse_document(selection_raw, label="ready selection")
    )
    digest = hashlib.sha256(selection_raw).hexdigest()
    if (
        item.get("selection_sha256") != digest
        or item.get("selection_bytes") != len(selection_raw)
        or item.get("selection_receipt_sha256") != selection["receipt_sha256"]
        or item.get("selection_scientific_sha256")
        != selection["scientific_sha256"]
    ):
        _fail("ready selection binding differs")
    return {**item, "ready_sha256": retained, "selection_raw": selection_raw}


def publish_create_once_bundle_v1(
    ready_bundle: Mapping[str, object],
    *, publish_create_once: PublishCreateOnce, read_exact: ReadExact,
) -> dict[str, object]:
    """Publish selection first and the terminal root last, exact-reopening both."""

    ready = validate_ready_bundle_v1(ready_bundle)
    if not callable(publish_create_once) or not callable(read_exact):
        _fail("publication callbacks are not callable")
    # This occurs before the first write.  A missing or mutable upstream root
    # therefore cannot leave a partial experiment publication behind.
    upstream_reopen = verify_upstream_authorities_v1(
        _parse_document(ready["selection_raw"], label="ready selection"),
        runtime_build_attestation_identity=ready[
            "runtime_build_attestation_identity"
        ],
        read_exact=read_exact,
    )
    execution_reopen = verify_selection_execution_authority_v1(
        _parse_document(ready["selection_raw"], label="ready selection"),
        execution_authority=ready["execution_authority"],
        read_exact=read_exact,
    )
    selection_raw = ready["selection_raw"]
    selection_identity = _identity(
        publish_create_once(str(ready["selection_uri"]), selection_raw),
        label="published selection",
        expected_uri=str(ready["selection_uri"]),
        expected_raw=selection_raw,
    )
    if read_exact(selection_identity) != selection_raw:
        _fail("published selection exact reopen differs")
    terminal_body: dict[str, object] = {
        "schema_version": TERMINAL_SCHEMA,
        "version": cross.VERSION,
        "run_id": ready["run_id"],
        "frozen_at": ready["frozen_at"],
        "ready_sha256": ready["ready_sha256"],
        "selection_identity": selection_identity,
        "selection_receipt_sha256": ready["selection_receipt_sha256"],
        "selection_scientific_sha256": ready["selection_scientific_sha256"],
        "runtime_build_attestation_identity": ready[
            "runtime_build_attestation_identity"
        ],
        "execution_authority": ready["execution_authority"],
        "execution_authority_sha256": ready["execution_authority_sha256"],
        "execution_reopen_receipt": execution_reopen,
        "multiplicity_family": ready["multiplicity_family"],
        "multiplicity_family_sha256": ready["multiplicity_family_sha256"],
        "upstream_reopen_receipt": upstream_reopen,
        "independent_audit_evaluation_authority_available": upstream_reopen[
            "independent_audit_evaluation_authority_available"
        ],
        "unconsumed_audit_placeholder_count": upstream_reopen[
            "unconsumed_audit_placeholder_count"
        ],
        "cell_order": list(cross.CELL_ORDER),
        "slate_count": len(cross.EXPECTED_SLATE_IDS),
        "publication_order_completed": ["selection", "terminal-root-last"],
        "all_outputs_create_once": True,
        "all_outputs_exact_reopened": True,
        "input_manifest_and_ordered_shards_generation_exact_reopened": True,
        "runtime_execution_provider_attestation_exact_reopened": True,
        "terminal_published_last": True,
        "selection_frozen_before_target_slate_outcome_join": True,
        "target_slate_outcomes_already_existed_before_replay": True,
        "target_slate_outcomes_read_during_selection": False,
        "uses_target_slate_outcomes": False,
        "post_lock_data_read": False,
        "complete": True,
        "automatic_policy_promotion": False,
        "production_policy_authority": False,
    }
    terminal_body["terminal_sha256"] = cross.canonical_sha256(terminal_body)
    terminal_raw = _canonical_document(terminal_body)
    terminal_identity = _identity(
        publish_create_once(str(ready["terminal_uri"]), terminal_raw),
        label="published terminal",
        expected_uri=str(ready["terminal_uri"]),
        expected_raw=terminal_raw,
    )
    if read_exact(terminal_identity) != terminal_raw:
        _fail("published terminal exact reopen differs")
    envelope_body: dict[str, object] = {
        "schema_version": TERMINAL_ENVELOPE_SCHEMA,
        "terminal_identity": terminal_identity,
        "terminal_sha256": terminal_body["terminal_sha256"],
        "selection_identity": selection_identity,
        "selection_receipt_sha256": ready["selection_receipt_sha256"],
        "runtime_build_attestation_identity": ready[
            "runtime_build_attestation_identity"
        ],
        "execution_authority_sha256": ready["execution_authority_sha256"],
        "execution_reopen_receipt_sha256": execution_reopen["receipt_sha256"],
        "runtime_execution_attestation_identity": ready[
            "execution_authority"
        ]["runtime_execution_attestation_identity"],
        "multiplicity_family_sha256": ready["multiplicity_family_sha256"],
        "independent_audit_evaluation_authority_available": upstream_reopen[
            "independent_audit_evaluation_authority_available"
        ],
        "unconsumed_audit_placeholder_count": upstream_reopen[
            "unconsumed_audit_placeholder_count"
        ],
        "upstream_reopen_receipt_sha256": upstream_reopen["receipt_sha256"],
        "complete": True,
        "create_once": True,
        "uses_target_slate_outcomes": False,
    }
    envelope_body["envelope_sha256"] = cross.canonical_sha256(envelope_body)
    return envelope_body


def reopen_terminal_bundle_v1(
    terminal_envelope: Mapping[str, object], *, read_exact: ReadExact,
) -> dict[str, object]:
    """Independently reopen terminal then selection by exact generations."""

    if not isinstance(terminal_envelope, Mapping):
        _fail("terminal envelope is not a mapping")
    envelope = dict(terminal_envelope)
    retained = envelope.pop("envelope_sha256", None)
    if (
        type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or cross.canonical_sha256(envelope) != retained
        or envelope.get("schema_version") != TERMINAL_ENVELOPE_SCHEMA
        or envelope.get("complete") is not True
        or envelope.get("create_once") is not True
        or envelope.get("uses_target_slate_outcomes") is not False
    ):
        _fail("terminal envelope differs")
    envelope_runtime_identity = cross._content_identity(
        envelope.get("runtime_build_attestation_identity"),
        label="terminal envelope runtime build attestation",
    )
    if envelope.get("runtime_build_attestation_identity") != envelope_runtime_identity:
        _fail("terminal envelope runtime identity differs")
    terminal_identity = _identity(
        envelope.get("terminal_identity"), label="terminal identity"
    )
    terminal_raw = _read_identity_bytes(
        terminal_identity, read_exact=read_exact, label="terminal"
    )
    terminal = _parse_document(terminal_raw, label="terminal")
    terminal_hash = terminal.get("terminal_sha256")
    terminal_without_hash = dict(terminal)
    terminal_without_hash.pop("terminal_sha256", None)
    if (
        terminal.get("schema_version") != TERMINAL_SCHEMA
        or terminal.get("complete") is not True
        or terminal.get("all_outputs_create_once") is not True
        or terminal.get("all_outputs_exact_reopened") is not True
        or terminal.get(
            "input_manifest_and_ordered_shards_generation_exact_reopened"
        ) is not True
        or terminal.get(
            "runtime_execution_provider_attestation_exact_reopened"
        ) is not True
        or terminal.get("terminal_published_last") is not True
        or terminal.get(
            "selection_frozen_before_target_slate_outcome_join"
        ) is not True
        or terminal.get(
            "target_slate_outcomes_already_existed_before_replay"
        ) is not True
        or terminal.get("target_slate_outcomes_read_during_selection")
        is not False
        or terminal.get("uses_target_slate_outcomes") is not False
        or terminal.get("post_lock_data_read") is not False
        or terminal.get("runtime_build_attestation_identity")
        != envelope_runtime_identity
        or terminal.get("independent_audit_evaluation_authority_available")
        is not envelope.get("independent_audit_evaluation_authority_available")
        or terminal.get("unconsumed_audit_placeholder_count")
        != envelope.get("unconsumed_audit_placeholder_count")
        or type(terminal_hash) is not str
        or cross.canonical_sha256(terminal_without_hash) != terminal_hash
        or terminal_hash != envelope.get("terminal_sha256")
    ):
        _fail("terminal document differs")
    selection_identity = _identity(
        terminal.get("selection_identity"), label="selection identity"
    )
    if selection_identity != envelope.get("selection_identity"):
        _fail("terminal/selection envelope binding differs")
    selection = cross.validate_score_blind_cross_v1(_parse_document(
        _read_identity_bytes(
            selection_identity, read_exact=read_exact, label="selection"
        ),
        label="selection",
    ))
    if (
        selection["receipt_sha256"]
        != terminal.get("selection_receipt_sha256")
        or selection["scientific_sha256"]
        != terminal.get("selection_scientific_sha256")
        or selection["receipt_sha256"]
        != envelope.get("selection_receipt_sha256")
    ):
        _fail("terminal selection binding differs")
    execution_authority = validate_selection_execution_authority_v1(
        terminal.get("execution_authority")
    )
    if (
        terminal.get("execution_authority_sha256")
        != execution_authority["execution_authority_sha256"]
        or envelope.get("execution_authority_sha256")
        != execution_authority["execution_authority_sha256"]
        or envelope.get("runtime_execution_attestation_identity")
        != execution_authority["runtime_execution_attestation_identity"]
    ):
        _fail("terminal execution-authority binding differs")
    execution_reopen = verify_selection_execution_authority_v1(
        selection,
        execution_authority=execution_authority,
        read_exact=read_exact,
    )
    if (
        terminal.get("execution_reopen_receipt") != execution_reopen
        or envelope.get("execution_reopen_receipt_sha256")
        != execution_reopen["receipt_sha256"]
    ):
        _fail("terminal execution predecessor replay differs")
    multiplicity = validate_multiplicity_family_v1(
        terminal.get("multiplicity_family")
    )
    if (
        terminal.get("multiplicity_family_sha256")
        != multiplicity["multiplicity_family_sha256"]
        or envelope.get("multiplicity_family_sha256")
        != multiplicity["multiplicity_family_sha256"]
    ):
        _fail("terminal multiplicity-family binding differs")
    upstream_reopen = verify_upstream_authorities_v1(
        selection,
        runtime_build_attestation_identity=envelope_runtime_identity,
        read_exact=read_exact,
    )
    if (
        terminal.get("upstream_reopen_receipt") != upstream_reopen
        or envelope.get("upstream_reopen_receipt_sha256")
        != upstream_reopen["receipt_sha256"]
        or envelope.get("independent_audit_evaluation_authority_available")
        is not upstream_reopen[
            "independent_audit_evaluation_authority_available"
        ]
        or envelope.get("unconsumed_audit_placeholder_count")
        != upstream_reopen["unconsumed_audit_placeholder_count"]
    ):
        _fail("terminal upstream reopen binding differs")
    return {
        "schema_version": "corpus-r6-construction-allocation-reopen/v1",
        "terminal_envelope": {**envelope, "envelope_sha256": retained},
        "terminal": terminal,
        "selection": selection,
        "complete": True,
        "outcome_data_accessed": False,
        "post_lock_data_read": False,
        "multiplicity_family": multiplicity,
        "upstream_reopen_receipt": upstream_reopen,
        "execution_authority": execution_authority,
        "execution_reopen_receipt": execution_reopen,
    }


__all__ = [
    "AUDIT_BANK_PLACEHOLDER_SCHEMA",
    "ConstructionAllocationCrossOperatorError",
    "LOCK_AUTHORITY_SCHEMA",
    "MULTIPLICITY_FAMILY_ID",
    "MULTIPLICITY_FAMILY_SCHEMA",
    "READY_SCHEMA",
    "RUNTIME_BUILD_ATTESTATION_SCHEMA",
    "RUNTIME_EXECUTION_ATTESTATION_SCHEMA",
    "SELECTION_EXECUTION_AUTHORITY_SCHEMA",
    "TERMINAL_ENVELOPE_SCHEMA",
    "TERMINAL_SCHEMA",
    "audit_bank_placeholder_v1",
    "common_lock_authority_v1",
    "multiplicity_family_v1",
    "prepare_create_once_bundle_v1",
    "publish_create_once_bundle_v1",
    "reopen_terminal_bundle_v1",
    "runtime_build_attestation_v1",
    "runtime_execution_attestation_v1",
    "selection_execution_authority_v1",
    "validate_multiplicity_family_v1",
    "validate_ready_bundle_v1",
    "validate_runtime_build_attestation_v1",
    "validate_runtime_execution_attestation_v1",
    "validate_selection_execution_authority_v1",
    "verify_selection_execution_authority_v1",
    "verify_upstream_authorities_v1",
]
