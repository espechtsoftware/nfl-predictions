"""Create-once transport for the R6 full-union 54-slate structural freeze.

The scientific schemas live in :mod:`corpus_r6_full_union_panel_freeze_v1`.
This module is the thin exact-name object-store boundary: prepare one
manifest, run or safely recover one deterministic slate, inspect deterministic
object names, and publish the panel root last.  It has no LIST, warehouse,
graph, or realized-result seam.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_fast_lane_v1 as lane
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as freeze
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as adapter
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_neo4j_transport import (
    ExactObjectStore,
    ObjectIdentity,
    object_identity,
)


PREPARE_RECEIPT_SCHEMA: Final = "corpus-r6-full-union-freeze-prepare-receipt/v1"
SLATE_RECEIPT_SCHEMA: Final = "corpus-r6-full-union-freeze-slate-receipt/v1"
STATUS_SCHEMA: Final = "corpus-r6-full-union-freeze-status/v1"
FINISH_RECEIPT_SCHEMA: Final = "corpus-r6-full-union-freeze-finish-receipt/v1"

_FALSE_FIELDS: Final = (
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "r6_freeze_authority",
    "promotion_authority",
    "decision_authority",
)


class CorpusR6FullUnionPanelFreezeReleaseV1Error(RuntimeError):
    """The create-once release cannot preserve its exact dependency graph."""


def _fail(message: str) -> None:
    raise CorpusR6FullUnionPanelFreezeReleaseV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = batch.canonical_sha256(result)
    return result


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return object_identity(value, label=label).as_dict()
    except Exception as exc:
        raise CorpusR6FullUnionPanelFreezeReleaseV1Error(
            f"{label} differs"
        ) from exc


def _read_exact_callback(storage: ExactObjectStore):
    def read_exact(value: Mapping[str, object]) -> bytes:
        identity = object_identity(value, label="freeze exact-read identity")
        raw = storage.read_exact(identity)
        if len(raw) != identity.bytes or sha256(raw).hexdigest() != identity.sha256:
            _fail("freeze exact-read content identity differs")
        return raw

    return read_exact


def _parse_raw(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        return _mapping(
            batch.parse_canonical_json_bytes(raw, label=label), label=label
        )
    except Exception as exc:
        raise CorpusR6FullUnionPanelFreezeReleaseV1Error(
            f"{label} is not canonical JSON"
        ) from exc


def _publish_or_recover(
    storage: ExactObjectStore,
    *,
    uri: str,
    value: Mapping[str, object],
    label: str,
) -> dict[str, object]:
    """Create once, or recover only byte-identical deterministic content."""
    raw = batch.canonical_json_bytes(dict(value))
    existing = storage.resolve_optional(uri)
    if existing is not None:
        identity, retained = existing
        if retained != raw:
            _fail(f"{label} create-once target already contains different bytes")
        normalized = _identity(identity.as_dict(), label=f"existing {label} identity")
    else:
        try:
            published = storage.publish_create_once(uri, raw)
        except Exception as exc:
            recovered = storage.resolve_optional(uri)
            if recovered is None or recovered[1] != raw:
                raise CorpusR6FullUnionPanelFreezeReleaseV1Error(
                    f"{label} create-once publication failed"
                ) from exc
            published = recovered[0]
        normalized = _identity(
            published.as_dict(), label=f"published {label} identity"
        )
    if (
        normalized["uri"] != uri
        or normalized["sha256"] != sha256(raw).hexdigest()
        or normalized["bytes"] != len(raw)
    ):
        _fail(f"{label} published identity differs")
    reopened = storage.read_exact(
        object_identity(normalized, label=f"{label} exact identity")
    )
    if reopened != raw:
        _fail(f"{label} exact reopen differs")
    return normalized


def _validate_runtime_binding(
    *,
    manifest: Mapping[str, object],
    runtime_source_commit_sha: str,
    runtime_immutable_image: str,
) -> None:
    if (
        runtime_source_commit_sha != manifest.get("source_commit_sha")
        or runtime_immutable_image != manifest.get("immutable_image")
    ):
        _fail("runtime commit or immutable image differs from execution manifest")


def prepare_release_v1(
    *,
    storage: ExactObjectStore,
    panel_index_identity: object,
    source_commit_sha: str,
    immutable_image: str,
    output_prefix: str,
) -> dict[str, object]:
    read_exact = _read_exact_callback(storage)
    panel, _, retained_panel_identity = freeze.reopen_fixed_panel_v1(
        panel_index_identity, read_exact=read_exact
    )
    manifest = freeze.build_execution_manifest_v1(
        panel_index_identity=retained_panel_identity,
        exact_panel_index=panel,
        source_commit_sha=source_commit_sha,
        immutable_image=immutable_image,
        output_prefix=output_prefix,
    )
    manifest_identity = _publish_or_recover(
        storage,
        uri=str(manifest["target_uri"]),
        value=manifest,
        label="execution manifest",
    )
    freeze.reopen_execution_manifest_v1(manifest_identity, read_exact=read_exact)
    return _with_hash({
        "schema_version": PREPARE_RECEIPT_SCHEMA,
        "publication_mode": freeze.PUBLICATION_MODE,
        "manifest_identity": manifest_identity,
        "execution_manifest_sha256": manifest["execution_manifest_sha256"],
        "panel_index_identity": retained_panel_identity,
        "source_slate_count": freeze.AUTHORITATIVE_SLATE_COUNT,
        "rank_80_book_count": freeze.PANEL_BOOK_COUNT,
        "prefix_count": freeze.PANEL_PREFIX_COUNT,
        **{field: False for field in _FALSE_FIELDS},
    }, field="prepare_receipt_sha256")


def _open_or_execute_result(
    *,
    storage: ExactObjectStore,
    manifest_identity: Mapping[str, object],
    manifest: Mapping[str, object],
    panel: Mapping[str, object],
    members: list[dict[str, object]],
    source_ordinal: int,
    runtime_execution_evidence: Mapping[str, object],
    execute: Callable[..., dict[str, object]],
) -> tuple[dict[str, object], dict[str, object], bool]:
    source_members = list(manifest["source_members"])
    source_member = _mapping(
        source_members[source_ordinal], label="manifest source member"
    )
    result_uri = str(source_member["task_result_uri"])
    existing = storage.resolve_optional(result_uri)
    if existing is not None:
        result_identity = _identity(
            existing[0].as_dict(), label="existing task-result identity"
        )
        (
            envelope,
            _,
            _,
            _,
            result,
            retained_result_identity,
        ) = freeze.reopen_task_result_envelope_v1(
            result_identity, read_exact=_read_exact_callback(storage)
        )
        if (
            envelope["manifest_identity"] != dict(manifest_identity)
            or envelope["source_ordinal"] != source_ordinal
            or retained_result_identity != result_identity
        ):
            _fail("existing task-result envelope binding differs")
        return result, retained_result_identity, True

    member = members[source_ordinal]
    read_exact = _read_exact_callback(storage)
    result = execute(
        validated_panel_index=panel,
        panel_index_identity=manifest["panel_index_identity"],
        accepted_slate_membership=member,
        task_acceptance_identity=member["task_acceptance_identity"],
        carrier_identity=member["carrier_identity"],
        read_exact=read_exact,
        worlds_per_block=rw.WORLDS_PER_BLOCK,
        require_authoritative=True,
    )
    validated_result = freeze.validate_task_result_v1(
        result,
        panel_index_identity=manifest["panel_index_identity"],
        panel_index_sha256=str(manifest["panel_index_sha256"]),
        panel_member=member,
    )
    envelope = freeze.build_task_result_envelope_v1(
        manifest_identity=manifest_identity,
        source_ordinal=source_ordinal,
        runtime_execution_evidence=runtime_execution_evidence,
        task_result=validated_result,
        read_exact=read_exact,
    )
    result_identity = _publish_or_recover(
        storage, uri=result_uri, value=envelope, label="task-result envelope"
    )
    (
        _,
        _,
        _,
        _,
        reopened_result,
        retained_result_identity,
    ) = freeze.reopen_task_result_envelope_v1(
        result_identity, read_exact=read_exact
    )
    return reopened_result, retained_result_identity, False


def run_slate_release_v1(
    *,
    storage: ExactObjectStore,
    manifest_identity: object,
    source_ordinal: int,
    runtime_source_commit_sha: str,
    runtime_immutable_image: str,
    runtime_execution_evidence: Mapping[str, object],
    execute: Callable[..., dict[str, object]] = (
        lane.execute_one_accepted_slate_full_union_v1
    ),
) -> dict[str, object]:
    if type(source_ordinal) is not int or not 0 <= source_ordinal < 54:
        _fail("source ordinal must be one exact integer in 0..53")
    read_exact = _read_exact_callback(storage)
    manifest, panel, members, retained_manifest_identity = (
        freeze.reopen_execution_manifest_v1(
            manifest_identity, read_exact=read_exact
        )
    )
    _validate_runtime_binding(
        manifest=manifest,
        runtime_source_commit_sha=runtime_source_commit_sha,
        runtime_immutable_image=runtime_immutable_image,
    )
    retained_runtime_evidence = freeze.validate_runtime_execution_evidence_v1(
        runtime_execution_evidence,
        manifest_identity=retained_manifest_identity,
        manifest=manifest,
        source_ordinal=source_ordinal,
    )
    source_member = _mapping(
        list(manifest["source_members"])[source_ordinal],
        label="manifest source member",
    )
    existing_leaf = storage.resolve_optional(str(source_member["slate_freeze_uri"]))
    if existing_leaf is not None:
        leaf_identity = _identity(
            existing_leaf[0].as_dict(), label="existing slate-freeze identity"
        )
        leaf, _, _, _, result, _ = freeze.reopen_slate_freeze_v1(
            leaf_identity, read_exact=read_exact
        )
        return _with_hash({
            "schema_version": SLATE_RECEIPT_SCHEMA,
            "publication_mode": freeze.PUBLICATION_MODE,
            "manifest_identity": retained_manifest_identity,
            "source_ordinal": source_ordinal,
            "slate_id": leaf["slate_id"],
            "task_result_identity": leaf["task_result_identity"],
            "task_result_envelope_sha256": leaf[
                "task_result_envelope_sha256"
            ],
            "task_result_sha256": result["task_result_sha256"],
            "slate_freeze_identity": leaf_identity,
            "slate_freeze_sha256": leaf["slate_freeze_sha256"],
            "runtime_execution_evidence": retained_runtime_evidence,
            "runtime_execution_evidence_sha256": retained_runtime_evidence[
                "runtime_execution_evidence_sha256"
            ],
            "result_recovered_without_reexecution": True,
            "leaf_recovered_without_republication": True,
            **{field: False for field in _FALSE_FIELDS},
        }, field="slate_receipt_sha256")

    result, result_identity, result_recovered = _open_or_execute_result(
        storage=storage,
        manifest_identity=retained_manifest_identity,
        manifest=manifest,
        panel=panel,
        members=members,
        source_ordinal=source_ordinal,
        runtime_execution_evidence=retained_runtime_evidence,
        execute=execute,
    )
    leaf = freeze.build_slate_freeze_v1(
        manifest_identity=retained_manifest_identity,
        source_ordinal=source_ordinal,
        task_result_identity=result_identity,
        read_exact=read_exact,
    )
    leaf_identity = _publish_or_recover(
        storage,
        uri=str(source_member["slate_freeze_uri"]),
        value=leaf,
        label="slate freeze",
    )
    freeze.reopen_slate_freeze_v1(leaf_identity, read_exact=read_exact)
    return _with_hash({
        "schema_version": SLATE_RECEIPT_SCHEMA,
        "publication_mode": freeze.PUBLICATION_MODE,
        "manifest_identity": retained_manifest_identity,
        "source_ordinal": source_ordinal,
        "slate_id": leaf["slate_id"],
        "task_result_identity": result_identity,
        "task_result_envelope_sha256": leaf[
            "task_result_envelope_sha256"
        ],
        "task_result_sha256": result["task_result_sha256"],
        "slate_freeze_identity": leaf_identity,
        "slate_freeze_sha256": leaf["slate_freeze_sha256"],
        "runtime_execution_evidence": retained_runtime_evidence,
        "runtime_execution_evidence_sha256": retained_runtime_evidence[
            "runtime_execution_evidence_sha256"
        ],
        "result_recovered_without_reexecution": result_recovered,
        "leaf_recovered_without_republication": False,
        **{field: False for field in _FALSE_FIELDS},
    }, field="slate_receipt_sha256")


def panel_status_v1(
    *, storage: ExactObjectStore, manifest_identity: object,
) -> dict[str, object]:
    read_exact = _read_exact_callback(storage)
    manifest, _, _, retained_manifest_identity = freeze.reopen_execution_manifest_v1(
        manifest_identity, read_exact=read_exact
    )
    completed: list[int] = []
    result_only: list[int] = []
    missing: list[int] = []
    leaf_identities: list[dict[str, object]] = []
    for raw_member in manifest["source_members"]:
        member = _mapping(raw_member, label="manifest source member")
        source_ordinal = int(member["source_ordinal"])
        leaf = storage.resolve_optional(str(member["slate_freeze_uri"]))
        if leaf is not None:
            parsed = _parse_raw(leaf[1], label=f"slate freeze[{source_ordinal}]")
            if (
                parsed.get("source_ordinal") != source_ordinal
                or parsed.get("complete") is not True
                or parsed.get("book_count") != freeze.BOOKS_PER_SLATE
                or parsed.get("prefix_count") != freeze.PREFIXES_PER_SLATE
            ):
                _fail(f"slate freeze[{source_ordinal}] status shell differs")
            completed.append(source_ordinal)
            leaf_identities.append(
                _identity(leaf[0].as_dict(), label="status slate-freeze identity")
            )
            continue
        result = storage.resolve_optional(str(member["task_result_uri"]))
        if result is not None:
            result_only.append(source_ordinal)
        else:
            missing.append(source_ordinal)
    return _with_hash({
        "schema_version": STATUS_SCHEMA,
        "manifest_identity": retained_manifest_identity,
        "source_slate_count": freeze.AUTHORITATIVE_SLATE_COUNT,
        "completed_slate_count": len(completed),
        "completed_source_ordinals": completed,
        "result_only_source_ordinals": result_only,
        "missing_source_ordinals": missing,
        "rank_80_book_count": len(completed) * freeze.BOOKS_PER_SLATE,
        "prefix_count": len(completed) * freeze.PREFIXES_PER_SLATE,
        "root_ready": len(completed) == freeze.AUTHORITATIVE_SLATE_COUNT,
        "ordered_slate_freeze_identities": leaf_identities,
        **{field: False for field in _FALSE_FIELDS},
    }, field="status_sha256")


def finish_release_v1(
    *, storage: ExactObjectStore, manifest_identity: object,
) -> dict[str, object]:
    status = panel_status_v1(storage=storage, manifest_identity=manifest_identity)
    if status["root_ready"] is not True:
        _fail(
            "panel root is not ready; missing/result-only ordinals remain: "
            f"{status['missing_source_ordinals']}/{status['result_only_source_ordinals']}"
        )
    read_exact = _read_exact_callback(storage)
    root = freeze.build_panel_freeze_v1(
        manifest_identity=status["manifest_identity"],
        ordered_slate_freeze_identities=status[
            "ordered_slate_freeze_identities"
        ],
        read_exact=read_exact,
    )
    root_identity = _publish_or_recover(
        storage,
        uri=str(root["target_uri"]),
        value=root,
        label="panel freeze",
    )
    freeze.reopen_panel_freeze_v1(root_identity, read_exact=read_exact)
    return _with_hash({
        "schema_version": FINISH_RECEIPT_SCHEMA,
        "publication_mode": freeze.PUBLICATION_MODE,
        "manifest_identity": status["manifest_identity"],
        "panel_freeze_identity": root_identity,
        "panel_freeze_sha256": root["panel_freeze_sha256"],
        "source_slate_count": root["source_slate_count"],
        "rank_80_book_count": root["rank_80_book_count"],
        "prefix_count": root["prefix_count"],
        "outcome_key_projection_inputs_frozen": root[
            "outcome_key_projection_inputs_frozen"
        ],
        **{field: False for field in _FALSE_FIELDS},
    }, field="finish_receipt_sha256")


__all__ = [
    "CorpusR6FullUnionPanelFreezeReleaseV1Error",
    "finish_release_v1",
    "panel_status_v1",
    "prepare_release_v1",
    "run_slate_release_v1",
]
