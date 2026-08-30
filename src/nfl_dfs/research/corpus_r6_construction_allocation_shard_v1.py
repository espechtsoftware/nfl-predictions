"""One-slate workers and deterministic collector for the construction cross.

The expensive optimizer work is naturally slate-local.  This module lets a
54-task Cloud Run execution build one immutable shard per exact Foundry G0
coordinate, then combines those already-validated shards without rerunning a
single optimizer solve.  It owns no storage, publication, outcome, warehouse,
or audit-bank API; callers supply the same score-blind ``CrossSlate`` and
native builder accepted by the monolithic implementation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Final

from . import corpus_r6_construction_allocation_cross_v1 as cross


SHARD_VERSION: Final = "corpus-r6-construction-allocation-shard-v1"
SHARD_SCHEMA: Final = "corpus-r6-construction-allocation-slate-shard/v1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ConstructionAllocationShardError(ValueError):
    """A one-slate shard or exact ordered collection differs."""


def _fail(message: str) -> None:
    raise ConstructionAllocationShardError(message)


def _coordinate(ordinal: int, slate: cross.CrossSlate) -> dict[str, object]:
    if (
        type(ordinal) is not int
        or not 0 <= ordinal < len(cross.EXPECTED_SLATE_IDS)
        or cross.EXPECTED_SLATE_IDS[ordinal] != slate.slate_id
    ):
        _fail("shard does not match its exact G0 panel coordinate")
    return {
        "ordinal": ordinal,
        "slate_id": slate.slate_id,
        "season": slate.season,
        "week": slate.week,
    }


def _authority_from_receipt(
    value: object,
    *,
    panel_id: str,
) -> cross.CrossPanelAuthority:
    if not isinstance(value, Mapping) or set(value) != {
        "foundry_g0_panel_id",
        "selection_panel_id",
        "expected_slate_ids",
        "identity",
        "membership_matches",
    }:
        _fail("shard panel authority differs")
    expected_ids = value.get("expected_slate_ids")
    if (
        value.get("selection_panel_id") != panel_id
        or not isinstance(expected_ids, list)
        or any(type(slate_id) is not str for slate_id in expected_ids)
    ):
        _fail("shard panel authority differs")
    authority = cross.CrossPanelAuthority(
        panel_id=str(value.get("foundry_g0_panel_id", "")),
        expected_slate_ids=tuple(expected_ids),
        identity=(
            dict(value["identity"])
            if isinstance(value.get("identity"), Mapping)
            else {}
        ),
    )
    try:
        expected = cross.panel_authority_receipt_v1(
            authority, panel_id=panel_id,
        )
    except cross.ConstructionAllocationCrossError as exc:
        raise ConstructionAllocationShardError(str(exc)) from exc
    if dict(value) != expected:
        _fail("shard panel authority differs")
    return authority


def build_score_blind_cross_shard_v1(
    slate: cross.CrossSlate,
    native_book_builder: cross.NativeBookBuilder,
    *,
    expected_slate_ordinal: int,
    panel_id: str,
    code_sha: str,
    image_digest: str,
    panel_authority: cross.CrossPanelAuthority,
    runtime_execution_coordinate: Mapping[str, object],
) -> dict[str, object]:
    """Run exactly one slate and return its self-hashed score-blind shard."""

    if not isinstance(slate, cross.CrossSlate):
        _fail("one-slate worker requires one CrossSlate")
    coordinate = _coordinate(expected_slate_ordinal, slate)
    try:
        panel, code, image = cross._identity_fields(
            panel_id=panel_id,
            code_sha=code_sha,
            image_digest=image_digest,
        )
        authority = cross.panel_authority_receipt_v1(
            panel_authority, panel_id=panel,
        )
        registry = cross.validate_registry(
            cross.registry_document(code_sha=code)
        )
        scientific_slate, timing_slate = cross.build_score_blind_slate_v1(
            slate,
            native_book_builder,
            code_sha=code,
            registry=registry,
        )
    except cross.ConstructionAllocationCrossError as exc:
        raise ConstructionAllocationShardError(str(exc)) from exc
    runtime_coordinate = dict(runtime_execution_coordinate)
    if (
        set(runtime_coordinate) != {
            "job_name", "execution_name", "task_index", "task_count",
            "task_attempt",
        }
        or type(runtime_coordinate.get("job_name")) is not str
        or not runtime_coordinate["job_name"]
        or type(runtime_coordinate.get("execution_name")) is not str
        or not runtime_coordinate["execution_name"]
        or runtime_coordinate.get("task_index") != expected_slate_ordinal
        or runtime_coordinate.get("task_count") != len(cross.EXPECTED_SLATE_IDS)
        or type(runtime_coordinate.get("task_attempt")) is not int
        or runtime_coordinate["task_attempt"] < 0
    ):
        _fail("shard runtime execution coordinate differs")

    scientific_body: dict[str, object] = {
        "schema_version": SHARD_SCHEMA,
        "version": SHARD_VERSION,
        "panel_id": panel,
        "panel_authority": authority,
        "expected_slate_coordinate": coordinate,
        "code_sha": code,
        "image_digest": image,
        "registry": registry,
        "registry_sha256": registry["registry_sha256"],
        "selection_scientific": scientific_slate,
        "selection_frozen_before_target_slate_outcome_join": True,
        "target_slate_outcomes_read_during_selection": False,
        "uses_target_slate_outcomes": False,
        "post_lock_data_read": False,
        "audit_bank_opened_during_selection": False,
        "historical_evidence_status": "descriptive-diagnostic-only",
        "automatic_policy_promotion": False,
        "production_policy_authority": False,
    }
    scientific_hash = cross.canonical_sha256(scientific_body)
    shard_body = {
        **scientific_body,
        "scientific_sha256": scientific_hash,
        "execution_observations": {
            "generation_timing_seconds": timing_slate,
            "runtime_execution_coordinate": runtime_coordinate,
        },
    }
    shard = {
        **shard_body,
        "shard_sha256": cross.canonical_sha256(shard_body),
    }
    return validate_score_blind_cross_shard_v1(shard)


def validate_score_blind_cross_shard_v1(
    value: object,
) -> dict[str, object]:
    """Deep-reopen one shard, including exact K80 support replay."""

    if not isinstance(value, Mapping):
        _fail("construction-allocation shard is not a mapping")
    item = dict(value)
    retained = item.pop("shard_sha256", None)
    if (
        type(retained) is not str
        or _SHA256.fullmatch(retained) is None
        or cross.canonical_sha256(item) != retained
    ):
        _fail("construction-allocation shard self-hash differs")
    expected_keys = {
        "schema_version",
        "version",
        "panel_id",
        "panel_authority",
        "expected_slate_coordinate",
        "code_sha",
        "image_digest",
        "registry",
        "registry_sha256",
        "selection_scientific",
        "selection_frozen_before_target_slate_outcome_join",
        "target_slate_outcomes_read_during_selection",
        "uses_target_slate_outcomes",
        "post_lock_data_read",
        "audit_bank_opened_during_selection",
        "historical_evidence_status",
        "automatic_policy_promotion",
        "production_policy_authority",
        "scientific_sha256",
        "execution_observations",
    }
    if set(item) != expected_keys:
        _fail("construction-allocation shard fields differ")
    scientific_hash = item.get("scientific_sha256")
    observations = item.get("execution_observations")
    scientific = {
        key: nested
        for key, nested in item.items()
        if key not in {"scientific_sha256", "execution_observations"}
    }
    if (
        type(scientific_hash) is not str
        or _SHA256.fullmatch(scientific_hash) is None
        or cross.canonical_sha256(scientific) != scientific_hash
        or scientific.get("schema_version") != SHARD_SCHEMA
        or scientific.get("version") != SHARD_VERSION
        or scientific.get(
            "selection_frozen_before_target_slate_outcome_join"
        ) is not True
        or scientific.get(
            "target_slate_outcomes_read_during_selection"
        ) is not False
        or scientific.get("uses_target_slate_outcomes") is not False
        or scientific.get("post_lock_data_read") is not False
        or scientific.get("audit_bank_opened_during_selection") is not False
        or scientific.get("historical_evidence_status")
        != "descriptive-diagnostic-only"
        or scientific.get("automatic_policy_promotion") is not False
        or scientific.get("production_policy_authority") is not False
    ):
        _fail("construction-allocation shard scientific identity differs")
    try:
        panel, code, image = cross._identity_fields(
            panel_id=str(scientific.get("panel_id", "")),
            code_sha=str(scientific.get("code_sha", "")),
            image_digest=str(scientific.get("image_digest", "")),
        )
        registry = cross.validate_registry(scientific.get("registry"))
    except cross.ConstructionAllocationCrossError as exc:
        raise ConstructionAllocationShardError(str(exc)) from exc
    if (
        registry.get("code_sha") != code
        or scientific.get("registry_sha256") != registry["registry_sha256"]
    ):
        _fail("construction-allocation shard registry binding differs")
    authority = _authority_from_receipt(
        scientific.get("panel_authority"), panel_id=panel,
    )

    coordinate = scientific.get("expected_slate_coordinate")
    if not isinstance(coordinate, Mapping) or set(coordinate) != {
        "ordinal", "slate_id", "season", "week",
    }:
        _fail("construction-allocation shard coordinate differs")
    ordinal = coordinate.get("ordinal")
    slate_id = coordinate.get("slate_id")
    season = coordinate.get("season")
    week = coordinate.get("week")
    if (
        type(ordinal) is not int
        or not 0 <= ordinal < len(cross.EXPECTED_SLATE_IDS)
        or cross.EXPECTED_SLATE_IDS[ordinal] != slate_id
        or type(season) is not int
        or type(week) is not int
        or slate_id != f"{season}-w{week:02d}"
    ):
        _fail("construction-allocation shard coordinate differs")
    selection = scientific.get("selection_scientific")
    if (
        not isinstance(selection, Mapping)
        or selection.get("slate_id") != slate_id
        or selection.get("season") != season
        or selection.get("week") != week
    ):
        _fail("construction-allocation shard slate payload differs")
    if (
        not isinstance(observations, Mapping)
        or set(observations) != {
            "generation_timing_seconds", "runtime_execution_coordinate"
        }
        or not isinstance(observations.get("generation_timing_seconds"), Mapping)
        or observations["generation_timing_seconds"].get("slate_id") != slate_id
    ):
        _fail("construction-allocation shard timing payload differs")
    runtime_coordinate = observations.get("runtime_execution_coordinate")
    if (
        not isinstance(runtime_coordinate, Mapping)
        or set(runtime_coordinate) != {
            "job_name", "execution_name", "task_index", "task_count",
            "task_attempt",
        }
        or type(runtime_coordinate.get("job_name")) is not str
        or not runtime_coordinate["job_name"]
        or type(runtime_coordinate.get("execution_name")) is not str
        or not runtime_coordinate["execution_name"]
        or runtime_coordinate.get("task_index") != ordinal
        or runtime_coordinate.get("task_count") != len(cross.EXPECTED_SLATE_IDS)
        or type(runtime_coordinate.get("task_attempt")) is not int
        or runtime_coordinate["task_attempt"] < 0
    ):
        _fail("construction-allocation shard runtime coordinate differs")

    try:
        partial = cross.assemble_score_blind_cross_v1(
            [selection],
            [observations["generation_timing_seconds"]],
            panel_id=panel,
            code_sha=code,
            image_digest=image,
            panel_authority=authority,
            registry=registry,
            _expected_selection_slate_ids=(str(slate_id),),
        )
        cross.validate_score_blind_cross_v1(
            partial,
            _expected_selection_slate_ids=(str(slate_id),),
        )
    except cross.ConstructionAllocationCrossError as exc:
        raise ConstructionAllocationShardError(str(exc)) from exc
    return {**item, "shard_sha256": retained}


def collect_score_blind_cross_shards_v1(
    shard_roots: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Collect the exact ordered slate shards into the canonical receipt."""

    if isinstance(shard_roots, (str, bytes)):
        _fail("construction-allocation shard collection differs")
    try:
        supplied = tuple(shard_roots)
    except TypeError as exc:
        raise ConstructionAllocationShardError(
            "construction-allocation shard collection differs"
        ) from exc
    if len(supplied) != len(cross.EXPECTED_SLATE_IDS):
        _fail("collector requires exactly one shard per G0 slate")
    # Reject task-placement or common-authority drift before performing the
    # more expensive exact support replay for every shard.  These are only
    # preflight observations; every root is still fully reopened below.
    declared_coordinates = [
        root.get("expected_slate_coordinate")
        if isinstance(root, Mapping) else None
        for root in supplied
    ]
    if any(not isinstance(row, Mapping) for row in declared_coordinates):
        _fail("construction-allocation shard coordinates differ")
    if (
        [row.get("ordinal") for row in declared_coordinates]
        != list(range(len(cross.EXPECTED_SLATE_IDS)))
        or [row.get("slate_id") for row in declared_coordinates]
        != list(cross.EXPECTED_SLATE_IDS)
    ):
        _fail("construction-allocation shards are not exact ordered membership")
    common_fields = (
        "panel_id",
        "panel_authority",
        "code_sha",
        "image_digest",
        "registry",
        "registry_sha256",
    )
    first_declared = supplied[0]
    if any(
        not isinstance(root, Mapping)
        or any(root.get(field) != first_declared.get(field)
               for field in common_fields)
        for root in supplied[1:]
    ):
        _fail("construction-allocation shard common authority differs")
    validated = [
        validate_score_blind_cross_shard_v1(root)
        for root in supplied
    ]
    coordinates = [row["expected_slate_coordinate"] for row in validated]
    if (
        [row["ordinal"] for row in coordinates]
        != list(range(len(cross.EXPECTED_SLATE_IDS)))
        or [row["slate_id"] for row in coordinates]
        != list(cross.EXPECTED_SLATE_IDS)
        or len({row["slate_id"] for row in coordinates}) != len(coordinates)
    ):
        _fail("construction-allocation shards are not exact ordered membership")

    first = validated[0]
    for row in validated[1:]:
        if any(row.get(field) != first.get(field) for field in common_fields):
            _fail("construction-allocation shard common authority differs")
    authority = _authority_from_receipt(
        first["panel_authority"], panel_id=str(first["panel_id"]),
    )
    try:
        return cross.assemble_score_blind_cross_v1(
            [row["selection_scientific"] for row in validated],
            [row["execution_observations"]["generation_timing_seconds"]
             for row in validated],
            panel_id=str(first["panel_id"]),
            code_sha=str(first["code_sha"]),
            image_digest=str(first["image_digest"]),
            panel_authority=authority,
            registry=first["registry"],
        )
    except cross.ConstructionAllocationCrossError as exc:
        raise ConstructionAllocationShardError(str(exc)) from exc


__all__ = [
    "ConstructionAllocationShardError",
    "SHARD_SCHEMA",
    "SHARD_VERSION",
    "build_score_blind_cross_shard_v1",
    "collect_score_blind_cross_shards_v1",
    "validate_score_blind_cross_shard_v1",
]
