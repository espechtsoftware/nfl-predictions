#!/usr/bin/env python3
"""Run one outcome-blind extreme-tail smoke from a published v12 panel.

The command consumes the local create-once publication receipt directly,
exact-reads its generation-pinned panel object, chooses one explicit accepted
slate, and delegates reconstruction plus census replay to the pure one-slate
executor.  It never lists or writes GCS, reads outcomes, retries, or grants
promotion authority.  Its sole optional write is one absolute create-once
local JSON result.  Strict proper-subset membership cannot be recovered from
digest-only threshold rows; the validator therefore checks every derivable
count, degree-distribution, endpoint, and nesting invariant while retaining
explicitly false analytical, decision, and promotion authority.
"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from functools import lru_cache
from hashlib import sha256
import os
from pathlib import Path
import sys
from typing import Final, Protocol

from nfl_dfs.research import corpus_extreme_tail_one_slate_execution as execution
from nfl_dfs.research import corpus_extreme_tail_census as census
from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_v12_import as v12_import
from nfl_dfs.research import corpus_v12_panel_index as panel
from nfl_dfs.research import residual_world_columns as rw


PUBLICATION_RECEIPT_SCHEMA: Final = (
    "foundry-v12-panel-index-publication/v1"
)
_FALSE_PUBLICATION_FIELDS: Final = (
    "automatic_retry_licensed",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "promotion_authority",
    "decision_authority",
)
_PUBLICATION_KEYS: Final = frozenset({
    "schema_version",
    "mode",
    "panel_uri",
    "panel_id",
    "panel_object_identity",
    "panel_content_sha256",
    "panel_content_bytes",
    "panel_index_sha256",
    "lane_count",
    "accepted_slate_count",
    "exact_input_replay_verified",
    "published",
    *_FALSE_PUBLICATION_FIELDS,
    "publication_receipt_sha256",
})
_MEMBER_KEYS: Final = frozenset({
    "slate_id",
    "lane_ordinal",
    "lane_id",
    "task_ordinal",
    "source_task_ordinal",
    "source_task_authority_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "arms",
})
_ARM_KEYS: Final = frozenset({
    "arm_ordinal",
    "parameter_set_id",
    "result_identity",
})
_COVERAGE_KEYS: Final = frozenset({
    "expected_task_count",
    "accepted_task_count",
    "excluded_task_count",
    "failed_task_count",
    "missing_task_count",
    "complete",
})
_RESULT_KEYS: Final = frozenset({
    "schema_version",
    "execution_mode",
    "slate_id",
    "panel_index_identity",
    "panel_index_sha256",
    "accepted_slate_membership",
    "accepted_slate_membership_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "later_source_freeze_identity",
    "world_artifact_identities",
    "world_artifact_identity_set_sha256",
    "configuration",
    "verification",
    "output_hashes",
    "reconstruction_receipt",
    "support_census",
    *execution._FALSE_AUTHORITY_FIELDS,
    "one_slate_execution_sha256",
})
_CONFIGURATION_KEYS: Final = frozenset({
    "worlds_per_block",
    "require_authoritative",
})
_VERIFICATION_KEYS: Final = frozenset({
    "panel_content_identity_verified",
    "panel_membership_binding_verified",
    "task_acceptance_content_identity_verified",
    "task_acceptance_carrier_binding_verified",
    "carrier_source_receipts_verified",
    "canonical_reconstruction_verified",
    "support_census_canonical_replay_verified",
    "canonical_authoritative_dose_verified",
})
_OUTPUT_HASH_KEYS: Final = frozenset({
    "compatibility_import_sha256",
    "candidate_provenance_sha256",
    "reconstruction_sha256",
    "matrix_binding_sha256",
    "score_matrix_sha256",
    "support_census_sha256",
})
_RECONSTRUCTION_KEYS: Final = frozenset({
    "schema_version",
    "compatibility_import_sha256",
    "candidate_provenance_sha256",
    "matrix_binding",
    "verified_arm_score_hashes",
    "uses_realized_outcomes",
    "promotion_authority",
    "reconstruction_sha256",
})
_MATRIX_BINDING_KEYS: Final = frozenset({
    "schema_version",
    "slate",
    "candidate_provenance_sha256",
    "lineup_ids_sha256",
    "world_ids_sha256",
    "shape",
    "score_matrix_sha256",
    "uses_realized_outcomes",
    "matrix_binding_sha256",
})
_VERIFIED_ARM_HASH_KEYS: Final = frozenset({
    "ordinal",
    "parameter_set_id",
    "candidate_score_sha256",
    "selected_score_sha256",
    "unique_count",
    "selected_count",
    "verified",
})
_SLATE_KEYS: Final = frozenset({"season", "week", "slate_id"})
_CENSUS_INPUT_KEYS: Final = frozenset({
    "reconstruction_sha256",
    "candidate_provenance_sha256",
    "matrix_binding_sha256",
    "score_matrix_sha256",
    "lineup_ids_sha256",
    "world_ids_sha256",
    "score_shape",
})
_WORLD_BASIS_KEYS: Final = frozenset({
    "blocks",
    "worlds_per_block",
    "world_count",
    "ordinary_unweighted_r_worlds",
})
_CARRIER_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "batch_manifest_identity",
    "batch_id",
    "batch_manifest_sha256",
    "parameter_schema_sha256",
    "common_law_sha256",
    "task_index",
    "task_sha256",
    "slate_id",
    "world_artifact_receipts",
    "world_artifact_receipt_set_sha256",
    "artifact_source_authority_task_sha256",
    "code_source",
    "immutable_image",
    "source_receipts",
    "source_receipt_set_sha256",
    "later_source_freeze_manifest_sha256",
    "artifact_source_authority_completion",
    "artifact_source_authority_completion_sha256",
    "effective_policy_inventory_identity",
    "effective_policy_inventory_sha256",
    "effective_policy_rule_universe_sha256",
    "effective_policy_inventory_source_set_sha256",
    "effective_policy_classified_input_projection_sha256",
    "world_schedule",
    "world_seed",
    "solver",
    "execution",
    "variant_results",
    "task_result_sha256",
})
_CARRIER_VARIANT_KEYS: Final = frozenset({
    "ordinal",
    "parameter_set_id",
    "parameter_set_sha256",
    "effective_policy_receipt",
    "result_object",
})
_CENSUS_KEYS: Final = frozenset({
    "schema_version",
    "census_law_id",
    "slate",
    "input_binding",
    "world_basis",
    "threshold_registry",
    "source_arm_order",
    "source_arm_order_sha256",
    "universe_order_law",
    "universe_count",
    "universes",
    "coverage_ge_230_support_gate",
    "dose_authority",
    "require_authoritative",
    "evidence_class",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "automatic_retry_licensed",
    "live_policy_access_licensed",
    "r6_freeze_authority",
    "analytical_authority",
    "promotion_authority",
    "decision_authority",
    "support_census_sha256",
})
_UNIVERSE_KEYS: Final = frozenset({
    "schema_version",
    "universe_id",
    "universe_kind",
    "parameter_set_id",
    "heldout_block",
    "training_blocks",
    "membership_law",
    "lineup_count",
    "lineup_ids_sha256",
    "heldout_only_excluded_lineup_count",
    "fit_candidate_view_sha256",
    "selection_provenance_sha256",
    "source_support",
    "training_metrics",
    "heldout_metrics_descriptive",
    "uses_realized_outcomes",
    "analytical_authority",
    "promotion_authority",
    "universe_sha256",
})
_OPPORTUNITY_METRIC_KEYS: Final = frozenset({
    "schema_version",
    "blocks",
    "worlds_per_block",
    "world_count",
    "world_ids_sha256",
    "lineup_count",
    "lineup_ids_sha256",
    "thresholds",
    "ordinary_unweighted_r_worlds",
    "uses_realized_outcomes",
    "opportunity_metrics_sha256",
})
_COUNT_ROW_KEYS: Final = frozenset({
    "label",
    "threshold",
    "operator",
    "event_lineup_count",
    "event_lineup_ids_sha256",
    "lineup_world_event_count",
    "opportunity_world_count",
    "opportunity_world_ids_sha256",
    "non_opportunity_world_count",
    "opportunity_rate_fraction",
    "summed_individual_event_rate_fraction",
    "mean_individual_event_rate_fraction",
    "event_union_efficiency_fraction",
})
_AGGREGATE_THRESHOLD_KEYS: Final = _COUNT_ROW_KEYS | frozenset({
    "event_score_block_breadth_histogram",
    "event_positive_lineup_generation_origin_block_breadth_histogram",
    "event_source_lineage",
    "by_block",
})
_BLOCK_THRESHOLD_KEYS: Final = _COUNT_ROW_KEYS | frozenset({
    "block_id",
    "world_count",
    "world_ids_sha256",
})
_FRACTION_KEYS: Final = frozenset({"numerator", "denominator"})
_SOURCE_SUPPORT_KEYS: Final = frozenset({
    "candidate_counts_are_nonexclusive_across_arms_and_blocks",
    "occurrence_counts_partition_occurrences_by_arm_and_block",
    "candidate_count",
    "candidate_count_by_training_origin_block",
    "training_occurrence_count_by_block",
    "candidate_count_by_training_source_arm",
    "training_occurrence_count_by_source_arm",
    "training_origin_block_breadth_histogram",
    "training_source_arm_breadth_histogram",
    "training_visit_occurrence_count_total",
    "distinct_training_arm_visit_count",
    "training_visit_occurrence_count_minimum",
    "training_visit_occurrence_count_maximum",
    "training_visit_occurrence_count_mean_fraction",
})
_EVENT_SOURCE_LINEAGE_KEYS: Final = frozenset({
    "event_lineup_counts_are_nonexclusive_across_arms_and_blocks",
    "event_occurrence_counts_partition_occurrences_by_arm_and_block",
    "event_lineup_count_by_training_source_arm",
    "event_training_occurrence_count_by_source_arm",
    "event_lineup_count_by_training_origin_block",
    "event_training_occurrence_count_by_origin_block",
    "event_distinct_training_arm_visit_count",
})
_SUPPORT_GATE_KEYS: Final = frozenset({
    "role",
    "requires_every_training_block_nonzero",
    "minimum_training_opportunity_world_count",
    "failure_role",
    "fold_observations",
})
_SUPPORT_OBSERVATION_KEYS: Final = frozenset({
    "heldout_block",
    "training_blocks",
    "every_training_block_nonzero",
    "training_opportunity_world_count",
    "nomination_support_passed",
})
_NESTED_FALSE_AUTHORITY_FIELDS: Final = frozenset({
    *execution._FALSE_AUTHORITY_FIELDS,
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
})


class CorpusExtremeTailOneSlateSmokeCLIError(RuntimeError):
    """The smoke cannot proceed without weakening its read-only contract."""


class ReadStore(Protocol):
    def read(self, identity: Mapping[str, object]) -> bytes: ...


def _fail(message: str) -> None:
    raise CorpusExtremeTailOneSlateSmokeCLIError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _sha(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise CorpusExtremeTailOneSlateSmokeCLIError(
            f"{label} differs"
        ) from exc


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if batch.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _split_gcs_uri(value: object, *, label: str) -> tuple[str, str]:
    if type(value) is not str or not value.startswith("gs://"):
        _fail(f"{label} must be an explicit GCS object URI")
    bucket, separator, object_name = value[5:].partition("/")
    if (
        not bucket
        or not separator
        or not object_name
        or object_name.endswith("/")
        or "//" in object_name
    ):
        _fail(f"{label} must name one canonical GCS object")
    return bucket, object_name


class GCSReadStore:
    """One generation-matched GET method; no list, write, or retry path."""

    def __init__(self, client: object) -> None:
        self._client = client

    def read(self, identity: Mapping[str, object]) -> bytes:
        retained = _identity(identity, label="GCS exact-read identity")
        bucket_name, object_name = _split_gcs_uri(
            retained["uri"], label="GCS exact-read URI"
        )
        generation = int(str(retained["generation"]))
        blob = self._client.bucket(bucket_name).blob(
            object_name, generation=generation
        )
        return blob.download_as_bytes(
            if_generation_match=generation,
            retry=None,
        )


def _absolute_for_checks(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def _reject_symlink_components(path: Path, *, label: str) -> None:
    checked = _absolute_for_checks(path)
    for component in (checked, *checked.parents):
        if component.is_symlink():
            _fail(f"{label} cannot contain a symlink")


def _preflight_publication_receipt_path(path: Path) -> None:
    _reject_symlink_components(path, label="panel publication receipt path")
    try:
        if not path.exists() or not path.is_file():
            _fail("panel publication receipt must be an existing regular file")
    except OSError as exc:
        raise CorpusExtremeTailOneSlateSmokeCLIError(
            "panel publication receipt path preflight failed"
        ) from exc


def _preflight_result_output(path: Path | None) -> None:
    if path is None:
        return
    if (
        not path.is_absolute()
        or path.name in {"", ".", ".."}
        or ".." in path.parts
    ):
        _fail("result output must be one canonical absolute file path")
    _reject_symlink_components(path, label="result output path")
    try:
        if os.path.lexists(path):
            _fail("result output create-once collision already exists")
        if not path.parent.exists() or not path.parent.is_dir():
            _fail("result output parent must be an existing directory")
        if not os.access(path.parent, os.W_OK):
            _fail("result output parent is not writable")
    except OSError as exc:
        raise CorpusExtremeTailOneSlateSmokeCLIError(
            "result output path preflight failed"
        ) from exc


def _parse_newline_canonical_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw.endswith(b"\n"):
        _fail(f"{label} is not newline-canonical JSON")
    try:
        value = batch.parse_canonical_json_bytes(raw[:-1], label=label)
    except Exception as exc:
        raise CorpusExtremeTailOneSlateSmokeCLIError(
            f"{label} is not newline-canonical JSON"
        ) from exc
    if batch.canonical_json_bytes(value) + b"\n" != raw:
        _fail(f"{label} is not newline-canonical JSON")
    return dict(_mapping(value, label=label))


def _load_publication_receipt(path: Path) -> dict[str, object]:
    _preflight_publication_receipt_path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorpusExtremeTailOneSlateSmokeCLIError(
            "panel publication receipt cannot be read"
        ) from exc
    receipt = _parse_newline_canonical_json(
        raw, label="panel publication receipt"
    )
    _exact_keys(receipt, _PUBLICATION_KEYS, label="panel publication receipt")
    if (
        receipt.get("schema_version") != PUBLICATION_RECEIPT_SCHEMA
        or receipt.get("mode") != "create_once"
        or receipt.get("published") is not True
        or receipt.get("exact_input_replay_verified") is not True
        or any(
            receipt.get(field) is not False
            for field in _FALSE_PUBLICATION_FIELDS
        )
    ):
        _fail("panel publication receipt mode or authority differs")
    _validate_self_hash(
        receipt,
        field="publication_receipt_sha256",
        label="panel publication receipt",
    )
    panel_identity = _identity(
        receipt.get("panel_object_identity"),
        label="published panel object identity",
    )
    panel_uri = receipt.get("panel_uri")
    _split_gcs_uri(panel_uri, label="published panel URI")
    _sha(
        receipt.get("panel_index_sha256"),
        label="publication panel index SHA",
    )
    if (
        panel_uri != panel_identity["uri"]
        or receipt.get("panel_content_sha256") != panel_identity["sha256"]
        or receipt.get("panel_content_bytes") != panel_identity["bytes"]
        or type(receipt.get("panel_id")) is not str
        or not receipt["panel_id"]
        or _exact_int(receipt.get("lane_count"), label="publication lane count")
        != 2
        or _exact_int(
            receipt.get("accepted_slate_count"),
            label="publication accepted-slate count",
        )
        != panel.V12_SOURCE_TASK_COUNT
    ):
        _fail("panel publication receipt content binding differs")
    result = dict(receipt)
    result["panel_object_identity"] = panel_identity
    return result


def _exact_read_raw(
    identity: Mapping[str, object], *, store: ReadStore, label: str
) -> tuple[dict[str, object], bytes]:
    retained = _identity(identity, label=f"{label} identity")
    try:
        raw = store.read(retained)
    except Exception as exc:
        raise CorpusExtremeTailOneSlateSmokeCLIError(
            f"{label} cannot be exact-read"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != retained["bytes"]
        or sha256(raw).hexdigest() != retained["sha256"]
    ):
        _fail(f"{label} content differs from exact identity")
    return retained, raw


def _load_carrier_bindings(
    *,
    carrier_identity: Mapping[str, object],
    membership: Mapping[str, object],
    store: ReadStore,
) -> dict[str, object]:
    normalized_carrier, raw = _exact_read_raw(
        carrier_identity,
        store=store,
        label="accepted task carrier",
    )
    try:
        parsed = batch.parse_canonical_json_bytes(
            raw, label="accepted task carrier"
        )
    except Exception as exc:
        raise CorpusExtremeTailOneSlateSmokeCLIError(
            "accepted task carrier is not exact canonical JSON"
        ) from exc
    if batch.canonical_json_bytes(parsed) != raw:
        _fail("accepted task carrier is not exact canonical JSON")
    carrier = dict(_mapping(parsed, label="accepted task carrier"))
    _exact_keys(carrier, _CARRIER_KEYS, label="accepted task carrier")
    if (
        carrier.get("schema_version") != batch.TASK_RESULT_SCHEMA
        or carrier.get("publication_mode") != batch.PUBLICATION_MODE
        or carrier.get("slate_id") != membership.get("slate_id")
        or carrier.get("task_index") != membership.get("task_ordinal")
    ):
        _fail("accepted task carrier membership or publication differs")
    _validate_self_hash(
        carrier,
        field="task_result_sha256",
        label="accepted task carrier",
    )
    raw_sources = _mapping(
        carrier.get("source_receipts"), label="accepted task carrier sources"
    )
    _exact_keys(
        raw_sources,
        frozenset(batch.SOURCE_RECEIPT_ROLES),
        label="accepted task carrier sources",
    )
    source_receipts = {
        role: _identity(
            raw_sources[role], label=f"accepted task carrier source {role}"
        )
        for role in batch.SOURCE_RECEIPT_ROLES
    }
    source_set_sha = _sha(
        carrier.get("source_receipt_set_sha256"),
        label="accepted task carrier source receipt set SHA",
    )
    if source_set_sha != batch.canonical_sha256(source_receipts):
        _fail("accepted task carrier source receipt set differs")
    raw_worlds = _mapping(
        carrier.get("world_artifact_receipts"),
        label="accepted task carrier world artifacts",
    )
    _exact_keys(
        raw_worlds,
        frozenset(batch.TASK_WORLD_SOURCE_ROLES),
        label="accepted task carrier world artifacts",
    )
    world_artifacts = {
        role: _identity(
            raw_worlds[role],
            label=f"accepted task carrier world artifact {role}",
        )
        for role in batch.TASK_WORLD_SOURCE_ROLES
    }
    world_set_sha = _sha(
        carrier.get("world_artifact_receipt_set_sha256"),
        label="accepted task carrier world artifact set SHA",
    )
    if (
        len({value["uri"] for value in world_artifacts.values()})
        != len(world_artifacts)
        or world_set_sha != batch.canonical_sha256(world_artifacts)
    ):
        _fail("accepted task carrier world artifact set differs")
    raw_variants = _sequence(
        carrier.get("variant_results"),
        label="accepted task carrier variant results",
    )
    membership_arms = _sequence(
        membership.get("arms"), label="accepted task carrier membership arms"
    )
    if len(raw_variants) != len(batch.PARAMETER_SET_ORDER):
        _fail("accepted task carrier does not bind exactly seven variants")
    for ordinal, (raw_variant, raw_arm) in enumerate(
        zip(raw_variants, membership_arms, strict=True)
    ):
        variant = _mapping(
            raw_variant, label=f"accepted task carrier variant[{ordinal}]"
        )
        _exact_keys(
            variant,
            _CARRIER_VARIANT_KEYS,
            label=f"accepted task carrier variant[{ordinal}]",
        )
        arm = _mapping(raw_arm, label=f"accepted membership arm[{ordinal}]")
        _sha(
            variant.get("parameter_set_sha256"),
            label=f"accepted task carrier variant[{ordinal}] parameter SHA",
        )
        _identity(
            variant.get("effective_policy_receipt"),
            label=f"accepted task carrier variant[{ordinal}] policy receipt",
        )
        if (
            variant.get("ordinal") != ordinal
            or variant.get("parameter_set_id")
            != batch.PARAMETER_SET_ORDER[ordinal]
            or _identity(
                variant.get("result_object"),
                label=f"accepted task carrier variant[{ordinal}] result",
            )
            != arm.get("result_identity")
        ):
            _fail("accepted task carrier variant membership differs")
    return {
        "carrier_identity": normalized_carrier,
        "source_receipts": source_receipts,
        "source_receipt_set_sha256": source_set_sha,
        "world_artifact_receipts": world_artifacts,
        "world_artifact_receipt_set_sha256": world_set_sha,
    }


def _validate_member(value: object, *, ordinal: int) -> dict[str, object]:
    row = dict(_mapping(value, label=f"accepted slate[{ordinal}]"))
    _exact_keys(row, _MEMBER_KEYS, label=f"accepted slate[{ordinal}]")
    slate_id = row.get("slate_id")
    lane_id = row.get("lane_id")
    if (
        type(slate_id) is not str
        or not slate_id
        or type(lane_id) is not str
        or not lane_id
        or _exact_int(
            row.get("lane_ordinal"), label="membership lane ordinal"
        )
        not in {0, 1}
        or _exact_int(
            row.get("task_ordinal"), label="membership task ordinal"
        )
        < 0
        or _exact_int(
            row.get("source_task_ordinal"),
            label="membership source task ordinal",
        )
        != ordinal
    ):
        _fail("accepted slate identity or ordinal differs")
    _sha(
        row.get("source_task_authority_sha256"),
        label="membership source-task authority SHA",
    )
    row["task_acceptance_identity"] = _identity(
        row.get("task_acceptance_identity"),
        label="membership task acceptance identity",
    )
    row["carrier_identity"] = _identity(
        row.get("carrier_identity"), label="membership carrier identity"
    )
    raw_arms = _sequence(row.get("arms"), label="membership arms")
    if len(raw_arms) != len(batch.PARAMETER_SET_ORDER):
        _fail("accepted slate does not bind exactly seven arms")
    arms: list[dict[str, object]] = []
    for arm_ordinal, raw_arm in enumerate(raw_arms):
        arm = dict(_mapping(raw_arm, label=f"membership arm[{arm_ordinal}]"))
        _exact_keys(arm, _ARM_KEYS, label=f"membership arm[{arm_ordinal}]")
        if (
            arm.get("arm_ordinal") != arm_ordinal
            or arm.get("parameter_set_id")
            != batch.PARAMETER_SET_ORDER[arm_ordinal]
        ):
            _fail("accepted slate arm order or identity differs")
        arm["result_identity"] = _identity(
            arm.get("result_identity"),
            label=f"membership arm[{arm_ordinal}] result identity",
        )
        arms.append(arm)
    row["arms"] = arms
    return row


def _parse_and_select_panel(
    *,
    receipt: Mapping[str, object],
    store: ReadStore,
    slate_id: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    panel_identity, raw = _exact_read_raw(
        _mapping(
            receipt["panel_object_identity"], label="published panel identity"
        ),
        store=store,
        label="published v12 panel index",
    )
    try:
        parsed = batch.parse_canonical_json_bytes(raw, label="published v12 panel")
    except Exception as exc:
        raise CorpusExtremeTailOneSlateSmokeCLIError(
            "published v12 panel is not exact canonical JSON"
        ) from exc
    body = dict(_mapping(parsed, label="published v12 panel"))
    try:
        panel._exact_keys(body, panel._PANEL_KEYS, label="published v12 panel")
        panel._validate_self_hash(
            body, field="panel_index_sha256", label="published v12 panel"
        )
    except panel.CorpusV12PanelIndexError as exc:
        raise CorpusExtremeTailOneSlateSmokeCLIError(str(exc)) from exc
    coverage = _mapping(body.get("coverage"), label="published panel coverage")
    _exact_keys(coverage, _COVERAGE_KEYS, label="published panel coverage")
    raw_members = _sequence(
        body.get("accepted_slates"), label="published panel accepted slates"
    )
    if (
        body.get("schema_version") != panel.PANEL_INDEX_SCHEMA
        or body.get("publication_mode") != panel.PUBLICATION_MODE
        or any(body.get(field) is not False for field in panel._FALSE_PANEL_FIELDS)
        or body.get("lane_count") != 2
        or len(_sequence(body.get("lanes"), label="published panel lanes")) != 2
        or body.get("accepted_slate_count") != panel.V12_SOURCE_TASK_COUNT
        or len(raw_members) != panel.V12_SOURCE_TASK_COUNT
        or body.get("exclusions") != []
        or body.get("failures") != []
        or body.get("missing_tasks") != []
        or coverage
        != {
            "expected_task_count": panel.V12_SOURCE_TASK_COUNT,
            "accepted_task_count": panel.V12_SOURCE_TASK_COUNT,
            "excluded_task_count": 0,
            "failed_task_count": 0,
            "missing_task_count": 0,
            "complete": True,
        }
    ):
        _fail("published v12 panel completeness or authority differs")
    _identity(
        body.get("artifact_source_authority_completion"),
        label="panel source-authority identity",
    )
    _sha(
        body.get("artifact_source_authority_completion_sha256"),
        label="panel source-authority SHA",
    )
    members = [
        _validate_member(value, ordinal=ordinal)
        for ordinal, value in enumerate(raw_members)
    ]
    slate_ids = [str(value["slate_id"]) for value in members]
    if len(set(slate_ids)) != len(slate_ids):
        _fail("published v12 panel contains duplicate slate_id membership")
    matches = [value for value in members if value["slate_id"] == slate_id]
    if len(matches) != 1:
        _fail("explicit slate_id is not exactly one accepted panel member")
    if (
        receipt.get("panel_uri") != panel_identity["uri"]
        or receipt.get("panel_content_sha256") != sha256(raw).hexdigest()
        or receipt.get("panel_content_bytes") != len(raw)
        or receipt.get("panel_id") != body.get("panel_id")
        or receipt.get("panel_index_sha256")
        != body.get("panel_index_sha256")
        or receipt.get("lane_count") != body.get("lane_count")
        or receipt.get("accepted_slate_count")
        != body.get("accepted_slate_count")
    ):
        _fail("publication receipt differs from exact-read panel content")
    return body, panel_identity, matches[0]


def _require_nested_authorities_false(value: object, *, label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _NESTED_FALSE_AUTHORITY_FIELDS and item is not False:
                _fail(f"{label}.{key} carries forbidden authority")
            _require_nested_authorities_false(
                item, label=f"{label}.{key}"
            )
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, item in enumerate(value):
            _require_nested_authorities_false(
                item, label=f"{label}[{ordinal}]"
            )


def _validate_fraction(
    value: object,
    *,
    numerator: int,
    denominator: int,
    label: str,
) -> None:
    if denominator == 0:
        if value is not None:
            _fail(f"{label} must be null for a zero denominator")
        return
    fraction = _mapping(value, label=label)
    _exact_keys(fraction, _FRACTION_KEYS, label=label)
    if (
        _exact_int(fraction.get("numerator"), label=f"{label} numerator")
        != numerator
        or _exact_int(
            fraction.get("denominator"),
            label=f"{label} denominator",
            minimum=1,
        )
        != denominator
    ):
        _fail(f"{label} differs from its exact counts")


@lru_cache(maxsize=None)
def _canonical_world_scope_sha256(
    blocks: tuple[str, ...], worlds_per_block: int
) -> str:
    return batch.canonical_sha256([
        {"block": block, "index": index}
        for block in blocks
        for index in range(worlds_per_block)
    ])


def _exact_count_mapping(
    value: object,
    *,
    expected_keys: Sequence[str],
    maximum: int | None,
    label: str,
) -> dict[str, int]:
    retained = _mapping(value, label=label)
    _exact_keys(retained, frozenset(expected_keys), label=label)
    result: dict[str, int] = {}
    for key in expected_keys:
        count = _exact_int(retained.get(key), label=f"{label}.{key}")
        if maximum is not None and count > maximum:
            _fail(f"{label}.{key} exceeds its population")
        result[key] = count
    return result


def _validate_breadth_histogram(
    value: object,
    *,
    breadth_field: str,
    minimum_breadth: int,
    maximum_breadth: int,
    population: int,
    expected_weighted_sum: int,
    label: str,
) -> list[dict[str, int]]:
    rows = _sequence(value, label=label)
    retained: list[dict[str, int]] = []
    prior_breadth = minimum_breadth - 1
    for ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"{label}[{ordinal}]")
        _exact_keys(
            row,
            frozenset({breadth_field, "lineup_count"}),
            label=f"{label}[{ordinal}]",
        )
        breadth = _exact_int(
            row.get(breadth_field),
            label=f"{label}[{ordinal}].{breadth_field}",
            minimum=minimum_breadth,
        )
        frequency = _exact_int(
            row.get("lineup_count"),
            label=f"{label}[{ordinal}].lineup_count",
            minimum=1,
        )
        if breadth > maximum_breadth or breadth <= prior_breadth:
            _fail(f"{label} breadth order or range differs")
        prior_breadth = breadth
        retained.append({breadth_field: breadth, "lineup_count": frequency})
    if (
        (population > 0 and not retained)
        or (population == 0 and retained)
        or sum(row["lineup_count"] for row in retained) != population
        or sum(
            row[breadth_field] * row["lineup_count"] for row in retained
        )
        != expected_weighted_sum
    ):
        _fail(f"{label} population or weighted breadth differs")
    return retained


def _validate_bipartite_degree_feasibility(
    histogram: Sequence[Mapping[str, int]],
    *,
    breadth_field: str,
    column_counts: Sequence[int],
    label: str,
) -> None:
    row_degrees = sorted(
        (
            int(row[breadth_field])
            for row in histogram
            for _ in range(int(row["lineup_count"]))
        ),
        reverse=True,
    )
    retained_columns = sorted((int(value) for value in column_counts), reverse=True)
    if sum(row_degrees) != sum(retained_columns):
        _fail(f"{label} row/column degree totals differ")
    prefix = 0
    for count, degree in enumerate(row_degrees, start=1):
        prefix += degree
        if prefix > sum(min(count, column) for column in retained_columns):
            _fail(f"{label} is not a realizable degree distribution")


def _validate_source_support(
    value: object,
    *,
    lineup_count: int,
    expected_blocks: Sequence[str],
    universe_kind: str,
    parameter_set_id: str | None,
    label: str,
) -> dict[str, object]:
    support = dict(_mapping(value, label=label))
    _exact_keys(support, _SOURCE_SUPPORT_KEYS, label=label)
    if (
        support.get("candidate_counts_are_nonexclusive_across_arms_and_blocks")
        is not True
        or support.get(
            "occurrence_counts_partition_occurrences_by_arm_and_block"
        )
        is not True
        or _exact_int(
            support.get("candidate_count"),
            label=f"{label}.candidate_count",
            minimum=1,
        )
        != lineup_count
    ):
        _fail(f"{label} population law differs")
    candidate_by_block = _exact_count_mapping(
        support.get("candidate_count_by_training_origin_block"),
        expected_keys=rw.WORLD_BLOCKS,
        maximum=lineup_count,
        label=f"{label} candidates by block",
    )
    occurrence_by_block = _exact_count_mapping(
        support.get("training_occurrence_count_by_block"),
        expected_keys=rw.WORLD_BLOCKS,
        maximum=None,
        label=f"{label} occurrences by block",
    )
    candidate_by_arm = _exact_count_mapping(
        support.get("candidate_count_by_training_source_arm"),
        expected_keys=batch.PARAMETER_SET_ORDER,
        maximum=lineup_count,
        label=f"{label} candidates by arm",
    )
    occurrence_by_arm = _exact_count_mapping(
        support.get("training_occurrence_count_by_source_arm"),
        expected_keys=batch.PARAMETER_SET_ORDER,
        maximum=None,
        label=f"{label} occurrences by arm",
    )
    total = _exact_int(
        support.get("training_visit_occurrence_count_total"),
        label=f"{label} total occurrences",
        minimum=1,
    )
    distinct = _exact_int(
        support.get("distinct_training_arm_visit_count"),
        label=f"{label} distinct arm visits",
        minimum=1,
    )
    minimum = _exact_int(
        support.get("training_visit_occurrence_count_minimum"),
        label=f"{label} minimum candidate occurrences",
        minimum=1,
    )
    maximum = _exact_int(
        support.get("training_visit_occurrence_count_maximum"),
        label=f"{label} maximum candidate occurrences",
        minimum=1,
    )
    if (
        any(
            candidate_by_block[block] != 0
            or occurrence_by_block[block] != 0
            for block in rw.WORLD_BLOCKS
            if block not in expected_blocks
        )
        or any(
            occurrence_by_block[block] < candidate_by_block[block]
            for block in rw.WORLD_BLOCKS
        )
        or any(
            occurrence_by_arm[arm] < candidate_by_arm[arm]
            for arm in batch.PARAMETER_SET_ORDER
        )
        or sum(occurrence_by_block.values()) != total
        or sum(occurrence_by_arm.values()) != total
        or distinct != total
        or total < lineup_count
        or minimum > maximum
        or (
            lineup_count == 1
            and (minimum != total or maximum != total)
        )
        or (
            lineup_count > 1
            and (
                total < maximum + minimum * (lineup_count - 1)
                or total > minimum + maximum * (lineup_count - 1)
            )
        )
        or total
        > (
            len(rw.WORLD_BLOCKS)
            * len(batch.PARAMETER_SET_ORDER)
            * runner.VISITS_PER_BLOCK
        )
        or any(
            occurrence_by_arm[arm]
            > len(rw.WORLD_BLOCKS) * runner.VISITS_PER_BLOCK
            for arm in batch.PARAMETER_SET_ORDER
        )
        or any(
            occurrence_by_block[block]
            > len(batch.PARAMETER_SET_ORDER) * runner.VISITS_PER_BLOCK
            for block in rw.WORLD_BLOCKS
        )
    ):
        _fail(f"{label} count relationships differ")
    _validate_fraction(
        support.get("training_visit_occurrence_count_mean_fraction"),
        numerator=total,
        denominator=lineup_count,
        label=f"{label} mean occurrences",
    )
    origin_histogram = _validate_breadth_histogram(
        support.get("training_origin_block_breadth_histogram"),
        breadth_field="block_count",
        minimum_breadth=1,
        maximum_breadth=len(expected_blocks),
        population=lineup_count,
        expected_weighted_sum=sum(candidate_by_block.values()),
        label=f"{label} origin-block breadth",
    )
    _validate_bipartite_degree_feasibility(
        origin_histogram,
        breadth_field="block_count",
        column_counts=list(candidate_by_block.values()),
        label=f"{label} origin-block breadth",
    )
    arm_histogram = _validate_breadth_histogram(
        support.get("training_source_arm_breadth_histogram"),
        breadth_field="arm_count",
        minimum_breadth=1,
        maximum_breadth=len(batch.PARAMETER_SET_ORDER),
        population=lineup_count,
        expected_weighted_sum=sum(candidate_by_arm.values()),
        label=f"{label} source-arm breadth",
    )
    _validate_bipartite_degree_feasibility(
        arm_histogram,
        breadth_field="arm_count",
        column_counts=list(candidate_by_arm.values()),
        label=f"{label} source-arm breadth",
    )
    visits_per_block = runner.VISITS_PER_BLOCK
    if universe_kind == "source-arm-all-block":
        if (
            parameter_set_id not in batch.PARAMETER_SET_ORDER
            or candidate_by_arm[parameter_set_id] != lineup_count
            or occurrence_by_arm[parameter_set_id]
            != len(rw.WORLD_BLOCKS) * visits_per_block
            or any(
                occurrence_by_block[block] < visits_per_block
                for block in rw.WORLD_BLOCKS
            )
        ):
            _fail(f"{label} source-arm authoritative dose differs")
    elif universe_kind == "cross-arm-fold-eligible":
        expected_total = (
            len(expected_blocks)
            * len(batch.PARAMETER_SET_ORDER)
            * visits_per_block
        )
        if (
            total != expected_total
            or any(
                occurrence_by_arm[arm]
                != len(expected_blocks) * visits_per_block
                for arm in batch.PARAMETER_SET_ORDER
            )
            or any(
                occurrence_by_block[block]
                != (
                    len(batch.PARAMETER_SET_ORDER) * visits_per_block
                    if block in expected_blocks
                    else 0
                )
                for block in rw.WORLD_BLOCKS
            )
        ):
            _fail(f"{label} fold authoritative dose differs")
    elif universe_kind == "cross-arm-all-block-union":
        expected_total = (
            len(rw.WORLD_BLOCKS)
            * len(batch.PARAMETER_SET_ORDER)
            * visits_per_block
        )
        if (
            total != expected_total
            or any(
                occurrence_by_arm[arm]
                != len(rw.WORLD_BLOCKS) * visits_per_block
                for arm in batch.PARAMETER_SET_ORDER
            )
            or any(
                occurrence_by_block[block]
                != len(batch.PARAMETER_SET_ORDER) * visits_per_block
                for block in rw.WORLD_BLOCKS
            )
        ):
            _fail(f"{label} all-block authoritative dose differs")
    else:
        _fail(f"{label} universe kind is not registered")
    return support


def _validate_count_row(
    row: Mapping[str, object],
    *,
    expected_threshold: tuple[str, float, str],
    lineup_count: int,
    world_count: int,
    lineup_ids_sha256: str,
    world_ids_sha256: str,
    label: str,
) -> dict[str, object]:
    expected_label, expected_score, expected_operator = expected_threshold
    if (
        row.get("label") != expected_label
        or type(row.get("threshold")) is not float
        or row.get("threshold") != expected_score
        or row.get("operator") != expected_operator
    ):
        _fail(f"{label} threshold identity differs")
    event_lineups = _exact_int(
        row.get("event_lineup_count"), label=f"{label} event lineups"
    )
    event_total = _exact_int(
        row.get("lineup_world_event_count"),
        label=f"{label} lineup-world events",
    )
    opportunities = _exact_int(
        row.get("opportunity_world_count"),
        label=f"{label} opportunity worlds",
    )
    non_opportunities = _exact_int(
        row.get("non_opportunity_world_count"),
        label=f"{label} non-opportunity worlds",
    )
    event_ids_sha = _sha(
        row.get("event_lineup_ids_sha256"), label=f"{label} event lineup IDs SHA"
    )
    opportunity_ids_sha = _sha(
        row.get("opportunity_world_ids_sha256"),
        label=f"{label} opportunity world IDs SHA",
    )
    if (
        event_lineups > lineup_count
        or opportunities > world_count
        or non_opportunities != world_count - opportunities
        or event_total > lineup_count * world_count
        or event_total > event_lineups * world_count
        or event_total > event_lineups * opportunities
        or event_total < event_lineups
        or event_total < opportunities
        or (event_total == 0) != (event_lineups == 0)
        or (event_total == 0) != (opportunities == 0)
    ):
        _fail(f"{label} counts exceed or contradict their population")
    empty_ids_sha = batch.canonical_sha256([])
    if (
        (event_lineups == 0 and event_ids_sha != empty_ids_sha)
        or (event_lineups == lineup_count and event_ids_sha != lineup_ids_sha256)
        or (opportunities == 0 and opportunity_ids_sha != empty_ids_sha)
        or (
            opportunities == world_count
            and opportunity_ids_sha != world_ids_sha256
        )
    ):
        _fail(f"{label} endpoint identity hashes differ")
    _validate_fraction(
        row.get("opportunity_rate_fraction"),
        numerator=opportunities,
        denominator=world_count,
        label=f"{label} opportunity rate",
    )
    _validate_fraction(
        row.get("summed_individual_event_rate_fraction"),
        numerator=event_total,
        denominator=world_count,
        label=f"{label} summed event rate",
    )
    _validate_fraction(
        row.get("mean_individual_event_rate_fraction"),
        numerator=event_total,
        denominator=lineup_count * world_count,
        label=f"{label} mean event rate",
    )
    _validate_fraction(
        row.get("event_union_efficiency_fraction"),
        numerator=opportunities,
        denominator=event_total,
        label=f"{label} union efficiency",
    )
    return {
        "event_lineup_count": event_lineups,
        "lineup_world_event_count": event_total,
        "opportunity_world_count": opportunities,
        "non_opportunity_world_count": non_opportunities,
        "event_lineup_ids_sha256": event_ids_sha,
        "opportunity_world_ids_sha256": opportunity_ids_sha,
    }


def _validate_event_source_lineage(
    value: object,
    *,
    event_lineup_count: int,
    source_support: Mapping[str, object],
    expected_blocks: Sequence[str],
    label: str,
) -> dict[str, object]:
    lineage = dict(_mapping(value, label=label))
    _exact_keys(lineage, _EVENT_SOURCE_LINEAGE_KEYS, label=label)
    if (
        lineage.get(
            "event_lineup_counts_are_nonexclusive_across_arms_and_blocks"
        )
        is not True
        or lineage.get(
            "event_occurrence_counts_partition_occurrences_by_arm_and_block"
        )
        is not True
    ):
        _fail(f"{label} counting law differs")
    lineup_by_arm = _exact_count_mapping(
        lineage.get("event_lineup_count_by_training_source_arm"),
        expected_keys=batch.PARAMETER_SET_ORDER,
        maximum=event_lineup_count,
        label=f"{label} event lineups by arm",
    )
    occurrence_by_arm = _exact_count_mapping(
        lineage.get("event_training_occurrence_count_by_source_arm"),
        expected_keys=batch.PARAMETER_SET_ORDER,
        maximum=None,
        label=f"{label} event occurrences by arm",
    )
    lineup_by_block = _exact_count_mapping(
        lineage.get("event_lineup_count_by_training_origin_block"),
        expected_keys=rw.WORLD_BLOCKS,
        maximum=event_lineup_count,
        label=f"{label} event lineups by block",
    )
    occurrence_by_block = _exact_count_mapping(
        lineage.get("event_training_occurrence_count_by_origin_block"),
        expected_keys=rw.WORLD_BLOCKS,
        maximum=None,
        label=f"{label} event occurrences by block",
    )
    source_candidate_by_arm = _mapping(
        source_support["candidate_count_by_training_source_arm"],
        label=f"{label} source candidates by arm",
    )
    source_occurrence_by_arm = _mapping(
        source_support["training_occurrence_count_by_source_arm"],
        label=f"{label} source occurrences by arm",
    )
    source_candidate_by_block = _mapping(
        source_support["candidate_count_by_training_origin_block"],
        label=f"{label} source candidates by block",
    )
    source_occurrence_by_block = _mapping(
        source_support["training_occurrence_count_by_block"],
        label=f"{label} source occurrences by block",
    )
    distinct = _exact_int(
        lineage.get("event_distinct_training_arm_visit_count"),
        label=f"{label} distinct arm visits",
    )
    source_lineup_count = int(source_support["candidate_count"])
    source_minimum = int(
        source_support["training_visit_occurrence_count_minimum"]
    )
    source_maximum = int(
        source_support["training_visit_occurrence_count_maximum"]
    )
    if (
        any(
            lineup_by_arm[arm] > source_candidate_by_arm[arm]
            or lineup_by_arm[arm]
            < max(
                0,
                int(source_candidate_by_arm[arm])
                + event_lineup_count
                - source_lineup_count,
            )
            or occurrence_by_arm[arm] < lineup_by_arm[arm]
            or occurrence_by_arm[arm] > source_occurrence_by_arm[arm]
            for arm in batch.PARAMETER_SET_ORDER
        )
        or any(
            lineup_by_block[block] > source_candidate_by_block[block]
            or lineup_by_block[block]
            < max(
                0,
                int(source_candidate_by_block[block])
                + event_lineup_count
                - source_lineup_count,
            )
            or occurrence_by_block[block] < lineup_by_block[block]
            or occurrence_by_block[block] > source_occurrence_by_block[block]
            or (
                block not in expected_blocks
                and (lineup_by_block[block] != 0 or occurrence_by_block[block] != 0)
            )
            for block in rw.WORLD_BLOCKS
        )
        or sum(occurrence_by_arm.values()) != distinct
        or sum(occurrence_by_block.values()) != distinct
        or distinct < event_lineup_count
        or distinct < event_lineup_count * source_minimum
        or distinct > event_lineup_count * source_maximum
        or distinct > source_support["training_visit_occurrence_count_total"]
        or (
            event_lineup_count == source_lineup_count
            and (
                lineup_by_arm != source_candidate_by_arm
                or occurrence_by_arm != source_occurrence_by_arm
                or lineup_by_block != source_candidate_by_block
                or occurrence_by_block != source_occurrence_by_block
                or distinct
                != source_support["training_visit_occurrence_count_total"]
            )
        )
        or (
            event_lineup_count == 0
            and (
                distinct != 0
                or any(lineup_by_arm.values())
                or any(lineup_by_block.values())
            )
        )
    ):
        _fail(f"{label} counts differ from source support")
    return lineage


def _validate_opportunity_metrics(
    value: object,
    *,
    expected_blocks: Sequence[str],
    source_training_blocks: Sequence[str],
    worlds_per_block: int,
    source_support: Mapping[str, object],
    expected_scope_world_hashes: Mapping[tuple[str, ...], str],
    expected_block_world_hashes: Mapping[str, str],
    label: str,
) -> dict[str, object]:
    metrics = dict(_mapping(value, label=label))
    _exact_keys(metrics, _OPPORTUNITY_METRIC_KEYS, label=label)
    lineup_count = _exact_int(
        metrics.get("lineup_count"), label=f"{label} lineups", minimum=1
    )
    world_count = len(expected_blocks) * worlds_per_block
    if (
        metrics.get("schema_version") != census.METRIC_SCHEMA
        or metrics.get("blocks") != list(expected_blocks)
        or metrics.get("worlds_per_block") != worlds_per_block
        or metrics.get("world_count") != world_count
        or metrics.get("ordinary_unweighted_r_worlds") is not True
        or metrics.get("uses_realized_outcomes") is not False
        or source_support.get("candidate_count") != lineup_count
    ):
        _fail(f"{label} scope or authority differs")
    world_ids_sha = _sha(
        metrics.get("world_ids_sha256"), label=f"{label} world IDs SHA"
    )
    block_scope = tuple(expected_blocks)
    if world_ids_sha != expected_scope_world_hashes.get(block_scope):
        _fail(f"{label} world identity differs from canonical block/world IDs")
    lineup_ids_sha = _sha(
        metrics.get("lineup_ids_sha256"), label=f"{label} lineup IDs SHA"
    )
    _validate_self_hash(
        metrics,
        field="opportunity_metrics_sha256",
        label=label,
    )
    raw_thresholds = _sequence(
        metrics.get("thresholds"), label=f"{label} thresholds"
    )
    if len(raw_thresholds) != len(census.THRESHOLDS):
        _fail(f"{label} threshold count differs")
    aggregate_counts: list[dict[str, object]] = []
    block_counts_by_threshold: list[list[dict[str, object]]] = []
    lineage_by_threshold: list[dict[str, object]] = []
    score_breadth_by_threshold: list[list[dict[str, int]]] = []
    origin_breadth_by_threshold: list[list[dict[str, int]]] = []
    retained_block_world_hashes: list[str] | None = None
    for threshold_ordinal, (raw_threshold, expected_threshold) in enumerate(
        zip(raw_thresholds, census.THRESHOLDS, strict=True)
    ):
        threshold_label = f"{label} threshold[{threshold_ordinal}]"
        threshold_row = dict(_mapping(raw_threshold, label=threshold_label))
        _exact_keys(
            threshold_row, _AGGREGATE_THRESHOLD_KEYS, label=threshold_label
        )
        aggregate = _validate_count_row(
            threshold_row,
            expected_threshold=expected_threshold,
            lineup_count=lineup_count,
            world_count=world_count,
            lineup_ids_sha256=lineup_ids_sha,
            world_ids_sha256=world_ids_sha,
            label=threshold_label,
        )
        raw_blocks = _sequence(
            threshold_row.get("by_block"), label=f"{threshold_label} blocks"
        )
        if len(raw_blocks) != len(expected_blocks):
            _fail(f"{threshold_label} block coverage differs")
        block_counts: list[dict[str, object]] = []
        block_world_hashes: list[str] = []
        for block_ordinal, (raw_block, expected_block) in enumerate(
            zip(raw_blocks, expected_blocks, strict=True)
        ):
            block_label = f"{threshold_label} block[{block_ordinal}]"
            block_row = dict(_mapping(raw_block, label=block_label))
            _exact_keys(block_row, _BLOCK_THRESHOLD_KEYS, label=block_label)
            block_world_sha = _sha(
                block_row.get("world_ids_sha256"),
                label=f"{block_label} world IDs SHA",
            )
            if (
                block_row.get("block_id") != expected_block
                or block_row.get("world_count") != worlds_per_block
            ):
                _fail(f"{block_label} world scope differs")
            if block_world_sha != expected_block_world_hashes[expected_block]:
                _fail(
                    f"{block_label} world identity differs from canonical "
                    "carrier-bound block/world IDs"
                )
            block_counts.append(_validate_count_row(
                block_row,
                expected_threshold=expected_threshold,
                lineup_count=lineup_count,
                world_count=worlds_per_block,
                lineup_ids_sha256=lineup_ids_sha,
                world_ids_sha256=block_world_sha,
                label=block_label,
            ))
            block_world_hashes.append(block_world_sha)
        if retained_block_world_hashes is None:
            retained_block_world_hashes = block_world_hashes
        elif block_world_hashes != retained_block_world_hashes:
            _fail(f"{threshold_label} block world identities drift across thresholds")
        if (
            aggregate["lineup_world_event_count"]
            != sum(row["lineup_world_event_count"] for row in block_counts)
            or aggregate["opportunity_world_count"]
            != sum(row["opportunity_world_count"] for row in block_counts)
            or aggregate["non_opportunity_world_count"]
            != sum(row["non_opportunity_world_count"] for row in block_counts)
            or aggregate["event_lineup_count"]
            < max(row["event_lineup_count"] for row in block_counts)
            or aggregate["event_lineup_count"]
            > min(
                lineup_count,
                sum(row["event_lineup_count"] for row in block_counts),
            )
        ):
            _fail(f"{threshold_label} aggregate/block counts differ")
        if any(
            (
                row["event_lineup_count"]
                == aggregate["event_lineup_count"]
                and row["event_lineup_ids_sha256"]
                != aggregate["event_lineup_ids_sha256"]
            )
            or (
                row["opportunity_world_count"]
                == aggregate["opportunity_world_count"]
                and row["opportunity_world_ids_sha256"]
                != aggregate["opportunity_world_ids_sha256"]
            )
            for row in block_counts
        ):
            _fail(f"{threshold_label} aggregate/block endpoint hashes differ")
        if len(block_counts) == 1 and (
            aggregate != block_counts[0]
            or world_ids_sha != block_world_hashes[0]
        ):
            _fail(f"{threshold_label} one-block aggregate identity differs")
        score_breadth = _validate_breadth_histogram(
            threshold_row.get("event_score_block_breadth_histogram"),
            breadth_field="block_count",
            minimum_breadth=0,
            maximum_breadth=len(expected_blocks),
            population=lineup_count,
            expected_weighted_sum=sum(
                row["event_lineup_count"] for row in block_counts
            ),
            label=f"{threshold_label} score-block breadth",
        )
        if (
            sum(
                row["lineup_count"]
                for row in score_breadth
                if row["block_count"] > 0
            )
            != aggregate["event_lineup_count"]
        ):
            _fail(f"{threshold_label} event-lineup breadth differs")
        _validate_bipartite_degree_feasibility(
            score_breadth,
            breadth_field="block_count",
            column_counts=[
                int(row["event_lineup_count"]) for row in block_counts
            ],
            label=f"{threshold_label} score-block breadth",
        )
        lineage = _validate_event_source_lineage(
            threshold_row.get("event_source_lineage"),
            event_lineup_count=aggregate["event_lineup_count"],
            source_support=source_support,
            expected_blocks=source_training_blocks,
            label=f"{threshold_label} source lineage",
        )
        event_lineup_by_block = _mapping(
            lineage["event_lineup_count_by_training_origin_block"],
            label=f"{threshold_label} lineage lineups by block",
        )
        origin_breadth = _validate_breadth_histogram(
            threshold_row.get(
                "event_positive_lineup_generation_origin_block_breadth_histogram"
            ),
            breadth_field="block_count",
            minimum_breadth=1,
            maximum_breadth=len(source_training_blocks),
            population=aggregate["event_lineup_count"],
            expected_weighted_sum=sum(event_lineup_by_block.values()),
            label=f"{threshold_label} positive-origin breadth",
        )
        _validate_bipartite_degree_feasibility(
            origin_breadth,
            breadth_field="block_count",
            column_counts=[
                int(event_lineup_by_block[block])
                for block in rw.WORLD_BLOCKS
            ],
            label=f"{threshold_label} positive-origin breadth",
        )
        aggregate_counts.append(aggregate)
        block_counts_by_threshold.append(block_counts)
        lineage_by_threshold.append(lineage)
        score_breadth_by_threshold.append(score_breadth)
        origin_breadth_by_threshold.append(origin_breadth)
    for ordinal in range(1, len(aggregate_counts)):
        prior = aggregate_counts[ordinal - 1]
        current = aggregate_counts[ordinal]
        for field in (
            "event_lineup_count",
            "lineup_world_event_count",
            "opportunity_world_count",
        ):
            if current[field] > prior[field]:
                _fail(f"{label} threshold counts are not nested")
        prior_row = _mapping(
            raw_thresholds[ordinal - 1], label=f"{label} prior threshold"
        )
        current_row = _mapping(
            raw_thresholds[ordinal], label=f"{label} current threshold"
        )
        if (
            current["event_lineup_count"] == prior["event_lineup_count"]
            and current_row.get("event_lineup_ids_sha256")
            != prior_row.get("event_lineup_ids_sha256")
        ) or (
            current["opportunity_world_count"]
            == prior["opportunity_world_count"]
            and current_row.get("opportunity_world_ids_sha256")
            != prior_row.get("opportunity_world_ids_sha256")
        ):
            _fail(f"{label} equal nested counts carry different identities")
        for block_ordinal in range(len(expected_blocks)):
            prior_block = block_counts_by_threshold[ordinal - 1][block_ordinal]
            current_block = block_counts_by_threshold[ordinal][block_ordinal]
            if any(
                current_block[field] > prior_block[field]
                for field in (
                    "event_lineup_count",
                    "lineup_world_event_count",
                    "opportunity_world_count",
                )
            ):
                _fail(f"{label} block threshold counts are not nested")
            if (
                current_block["event_lineup_count"]
                == prior_block["event_lineup_count"]
                and current_block["event_lineup_ids_sha256"]
                != prior_block["event_lineup_ids_sha256"]
            ) or (
                current_block["opportunity_world_count"]
                == prior_block["opportunity_world_count"]
                and current_block["opportunity_world_ids_sha256"]
                != prior_block["opportunity_world_ids_sha256"]
            ):
                _fail(f"{label} equal block counts carry different identities")
        prior_lineage = lineage_by_threshold[ordinal - 1]
        current_lineage = lineage_by_threshold[ordinal]
        for mapping_field in (
            "event_lineup_count_by_training_source_arm",
            "event_training_occurrence_count_by_source_arm",
            "event_lineup_count_by_training_origin_block",
            "event_training_occurrence_count_by_origin_block",
        ):
            prior_mapping = _mapping(
                prior_lineage[mapping_field],
                label=f"{label} prior lineage {mapping_field}",
            )
            current_mapping = _mapping(
                current_lineage[mapping_field],
                label=f"{label} current lineage {mapping_field}",
            )
            if any(
                int(current_mapping[key]) > int(prior_mapping[key])
                for key in prior_mapping
            ):
                _fail(f"{label} source lineage is not threshold-nested")
        if (
            current_lineage["event_distinct_training_arm_visit_count"]
            > prior_lineage["event_distinct_training_arm_visit_count"]
        ):
            _fail(f"{label} distinct source lineage is not threshold-nested")
        prior_score_histogram = score_breadth_by_threshold[ordinal - 1]
        current_score_histogram = score_breadth_by_threshold[ordinal]
        for minimum_degree in range(1, len(expected_blocks) + 1):
            prior_tail = sum(
                row["lineup_count"]
                for row in prior_score_histogram
                if row["block_count"] >= minimum_degree
            )
            current_tail = sum(
                row["lineup_count"]
                for row in current_score_histogram
                if row["block_count"] >= minimum_degree
            )
            if current_tail > prior_tail:
                _fail(f"{label} score breadth is not threshold-nested")
        prior_origin_histogram = {
            row["block_count"]: row["lineup_count"]
            for row in origin_breadth_by_threshold[ordinal - 1]
        }
        current_origin_histogram = {
            row["block_count"]: row["lineup_count"]
            for row in origin_breadth_by_threshold[ordinal]
        }
        if any(
            current_origin_histogram.get(degree, 0)
            > prior_origin_histogram.get(degree, 0)
            for degree in set(prior_origin_histogram)
            | set(current_origin_histogram)
        ):
            _fail(f"{label} origin breadth is not threshold-nested")
    return metrics


def _validate_nested_result_evidence(
    result: Mapping[str, object],
    *,
    slate_id: str,
) -> None:
    output_hashes = _mapping(
        result.get("output_hashes"), label="execution output hashes"
    )
    _exact_keys(
        output_hashes, _OUTPUT_HASH_KEYS, label="execution output hashes"
    )
    for key in _OUTPUT_HASH_KEYS:
        _sha(output_hashes.get(key), label=f"execution output hash {key}")

    reconstruction = _mapping(
        result.get("reconstruction_receipt"),
        label="execution reconstruction receipt",
    )
    _exact_keys(
        reconstruction,
        _RECONSTRUCTION_KEYS,
        label="execution reconstruction receipt",
    )
    if (
        reconstruction.get("schema_version")
        != v12_import.RECONSTRUCTION_SCHEMA
        or reconstruction.get("uses_realized_outcomes") is not False
        or reconstruction.get("promotion_authority") is not False
    ):
        _fail("execution reconstruction receipt schema or authority differs")
    reconstruction_sha = _validate_self_hash(
        reconstruction,
        field="reconstruction_sha256",
        label="execution reconstruction receipt",
    )
    matrix_binding = _mapping(
        reconstruction.get("matrix_binding"),
        label="execution matrix binding",
    )
    _exact_keys(
        matrix_binding,
        _MATRIX_BINDING_KEYS,
        label="execution matrix binding",
    )
    matrix_slate = dict(_mapping(
        matrix_binding.get("slate"), label="execution matrix slate"
    ))
    _exact_keys(matrix_slate, _SLATE_KEYS, label="execution matrix slate")
    matrix_season = _exact_int(
        matrix_slate.get("season"), label="execution matrix slate season",
        minimum=2_000,
    )
    matrix_week = _exact_int(
        matrix_slate.get("week"), label="execution matrix slate week",
        minimum=1,
    )
    if (
        matrix_binding.get("schema_version")
        != v12_import.MATRIX_BINDING_SCHEMA
        or matrix_binding.get("uses_realized_outcomes") is not False
        or matrix_slate.get("slate_id") != slate_id
        or matrix_week > 18
        or slate_id != f"{matrix_season}-w{matrix_week:02d}"
    ):
        _fail("execution matrix binding schema, slate, or authority differs")
    matrix_sha = _validate_self_hash(
        matrix_binding,
        field="matrix_binding_sha256",
        label="execution matrix binding",
    )
    matrix_lineup_ids_sha = _sha(
        matrix_binding.get("lineup_ids_sha256"),
        label="execution matrix lineup IDs SHA",
    )
    matrix_world_ids_sha = _sha(
        matrix_binding.get("world_ids_sha256"),
        label="execution matrix world IDs SHA",
    )
    score_shape = _sequence(
        matrix_binding.get("shape"), label="execution score shape"
    )
    configuration = _mapping(
        result.get("configuration"), label="execution configuration"
    )
    worlds_per_block = _exact_int(
        configuration.get("worlds_per_block"),
        label="execution worlds_per_block",
        minimum=1,
    )
    if (
        worlds_per_block != rw.WORLDS_PER_BLOCK
        or type(score_shape) is not list
        or len(score_shape) != 2
        or _exact_int(score_shape[0], label="execution lineup count", minimum=1)
        < 1
        or _exact_int(score_shape[1], label="execution world count", minimum=1)
        != len(rw.WORLD_BLOCKS) * worlds_per_block
        or reconstruction.get("candidate_provenance_sha256")
        != matrix_binding.get("candidate_provenance_sha256")
    ):
        _fail("execution reconstruction score/dose binding differs")
    arm_rows = _sequence(
        reconstruction.get("verified_arm_score_hashes"),
        label="execution verified arm hashes",
    )
    if len(arm_rows) != len(batch.PARAMETER_SET_ORDER):
        _fail("execution reconstruction does not verify all seven arms")
    verified_unique_count_by_arm: dict[str, int] = {}
    for ordinal, raw_row in enumerate(arm_rows):
        row = _mapping(raw_row, label=f"execution arm hash[{ordinal}]")
        _exact_keys(
            row,
            _VERIFIED_ARM_HASH_KEYS,
            label=f"execution arm hash[{ordinal}]",
        )
        unique_count = _exact_int(
            row.get("unique_count"),
            label=f"execution arm hash[{ordinal}] unique count",
            minimum=1,
        )
        selected_count = _exact_int(
            row.get("selected_count"),
            label=f"execution arm hash[{ordinal}] selected count",
            minimum=1,
        )
        if (
            row.get("ordinal") != ordinal
            or row.get("parameter_set_id")
            != batch.PARAMETER_SET_ORDER[ordinal]
            or unique_count < selected_count
            or unique_count
            > len(rw.WORLD_BLOCKS) * runner.VISITS_PER_BLOCK
            or selected_count
            != batch.SELECTED_ENTRY_BUDGET
            or row.get("verified") is not True
        ):
            _fail("execution reconstruction arm order or verification differs")
        verified_unique_count_by_arm[batch.PARAMETER_SET_ORDER[ordinal]] = (
            unique_count
        )
        for field in ("candidate_score_sha256", "selected_score_sha256"):
            _sha(row.get(field), label=f"execution arm hash[{ordinal}].{field}")

    support = _mapping(
        result.get("support_census"), label="execution support census"
    )
    _exact_keys(support, _CENSUS_KEYS, label="execution support census")
    census_slate = dict(_mapping(
        support.get("slate"), label="execution support census slate"
    ))
    _exact_keys(
        census_slate, _SLATE_KEYS, label="execution support census slate"
    )
    if (
        support.get("schema_version") != census.CENSUS_SCHEMA
        or support.get("census_law_id") != census.CENSUS_LAW_ID
        or census_slate != matrix_slate
        or support.get("require_authoritative") is not True
        or support.get("evidence_class")
        != "outcome-blind-simulated-instrument"
    ):
        _fail("execution support census schema, slate, or evidence differs")
    support_sha = _validate_self_hash(
        support,
        field="support_census_sha256",
        label="execution support census",
    )
    census_input = _mapping(
        support.get("input_binding"), label="support census input binding"
    )
    _exact_keys(
        census_input,
        _CENSUS_INPUT_KEYS,
        label="support census input binding",
    )
    world_basis = _mapping(
        support.get("world_basis"), label="support census world basis"
    )
    _exact_keys(
        world_basis, _WORLD_BASIS_KEYS, label="support census world basis"
    )
    expected_thresholds = [
        {"threshold_id": label, "score": threshold, "operator": operator}
        for label, threshold, operator in census.THRESHOLDS
    ]
    universes = _sequence(
        support.get("universes"), label="support census universes"
    )
    expected_census_input = {
        "reconstruction_sha256": reconstruction_sha,
        "candidate_provenance_sha256": reconstruction.get(
            "candidate_provenance_sha256"
        ),
        "matrix_binding_sha256": matrix_sha,
        "score_matrix_sha256": matrix_binding.get("score_matrix_sha256"),
        "lineup_ids_sha256": matrix_lineup_ids_sha,
        "world_ids_sha256": matrix_world_ids_sha,
        "score_shape": list(score_shape),
    }
    expected_world_basis = {
        "blocks": list(rw.WORLD_BLOCKS),
        "worlds_per_block": worlds_per_block,
        "world_count": len(rw.WORLD_BLOCKS) * worlds_per_block,
        "ordinary_unweighted_r_worlds": True,
    }
    if (
        support.get("threshold_registry") != expected_thresholds
        or support.get("source_arm_order") != list(census.SOURCE_ARM_ORDER)
        or support.get("source_arm_order_sha256")
        != census.SOURCE_ARM_ORDER_SHA256
        or support.get("universe_order_law")
        != (
            "seven-source-arms-parameter-order-then-five-heldout-blocks-"
            "then-cross-arm-all-block-union"
        )
        or support.get("universe_count") != 13
        or len(universes) != 13
        or support.get("dose_authority") != runner.AUTHORITATIVE_DOSE
        or dict(world_basis) != expected_world_basis
        or dict(census_input) != expected_census_input
    ):
        _fail("execution support census input or world binding differs")
    expected_universe_contract = [
        (
            f"source-arm-all-block:{arm}",
            "source-arm-all-block",
            arm,
            None,
            list(rw.WORLD_BLOCKS),
            "any-all-block-provenance-occurrence-from-source-arm",
        )
        for arm in batch.PARAMETER_SET_ORDER
    ] + [
        (
            f"cross-arm-fold-eligible:holdout-{heldout}",
            "cross-arm-fold-eligible",
            None,
            heldout,
            [block for block in rw.WORLD_BLOCKS if block != heldout],
            (
                "cross-arm-union-with-heldout-only-origins-and-heldout-"
                "occurrences-removed-before-selection"
            ),
        )
        for heldout in rw.WORLD_BLOCKS
    ] + [
        (
            "cross-arm-all-block-union",
            "cross-arm-all-block-union",
            None,
            None,
            list(rw.WORLD_BLOCKS),
            "canonical-deduplicated-cross-arm-all-block-union",
        )
    ]
    registered_scopes = {
        tuple(rw.WORLD_BLOCKS),
        *((block,) for block in rw.WORLD_BLOCKS),
        *(
            tuple(value for value in rw.WORLD_BLOCKS if value != heldout)
            for heldout in rw.WORLD_BLOCKS
        ),
    }
    expected_scope_world_hashes = {
        scope: _canonical_world_scope_sha256(scope, worlds_per_block)
        for scope in registered_scopes
    }
    expected_block_world_hashes = {
        block: expected_scope_world_hashes[(block,)]
        for block in rw.WORLD_BLOCKS
    }
    if (
        matrix_world_ids_sha
        != expected_scope_world_hashes[tuple(rw.WORLD_BLOCKS)]
    ):
        _fail("execution matrix world IDs differ from canonical carrier scope")
    fold_ge_230: dict[str, dict[str, object]] = {}
    source_support_by_arm: dict[str, dict[str, object]] = {}
    source_metrics_by_arm: dict[str, dict[str, object]] = {}
    fold_support_by_heldout: dict[str, dict[str, object]] = {}
    fold_excluded_by_heldout: dict[str, int] = {}
    full_union_source_support: dict[str, object] | None = None
    full_union_training_metrics: dict[str, object] | None = None
    for ordinal, (raw_universe, expected_contract) in enumerate(
        zip(universes, expected_universe_contract, strict=True)
    ):
        universe = dict(_mapping(
            raw_universe, label=f"support census universe[{ordinal}]"
        ))
        _exact_keys(
            universe,
            _UNIVERSE_KEYS,
            label=f"support census universe[{ordinal}]",
        )
        (
            expected_id,
            expected_kind,
            expected_arm,
            expected_heldout,
            expected_training_blocks,
            expected_membership_law,
        ) = expected_contract
        lineup_count = _exact_int(
            universe.get("lineup_count"),
            label=f"support census universe[{ordinal}] lineups",
            minimum=1,
        )
        universe_lineup_ids_sha = _sha(
            universe.get("lineup_ids_sha256"),
            label=f"support census universe[{ordinal}] lineup IDs SHA",
        )
        excluded_count = _exact_int(
            universe.get("heldout_only_excluded_lineup_count"),
            label=f"support census universe[{ordinal}] excluded lineups",
        )
        if (
            universe.get("schema_version") != census.UNIVERSE_SCHEMA
            or universe.get("universe_id") != expected_id
            or universe.get("universe_kind") != expected_kind
            or universe.get("parameter_set_id") != expected_arm
            or universe.get("heldout_block") != expected_heldout
            or universe.get("training_blocks") != expected_training_blocks
            or universe.get("membership_law") != expected_membership_law
            or universe.get("uses_realized_outcomes") is not False
            or universe.get("analytical_authority") is not False
            or universe.get("promotion_authority") is not False
        ):
            _fail("support census universe registered content differs")
        if (
            expected_kind == "source-arm-all-block"
            and lineup_count != verified_unique_count_by_arm[expected_arm]
        ):
            _fail("source-arm support universe verified membership differs")
        if (
            lineup_count == score_shape[0]
            and universe_lineup_ids_sha != matrix_lineup_ids_sha
        ):
            _fail("full-population support universe membership differs")
        if expected_kind == "cross-arm-fold-eligible":
            _sha(
                universe.get("fit_candidate_view_sha256"),
                label=f"support census universe[{ordinal}] candidate view SHA",
            )
            _sha(
                universe.get("selection_provenance_sha256"),
                label=f"support census universe[{ordinal}] selection SHA",
            )
            if lineup_count + excluded_count != score_shape[0]:
                _fail("fold support universe candidate coverage differs")
        elif (
            universe.get("fit_candidate_view_sha256") is not None
            or universe.get("selection_provenance_sha256") is not None
            or excluded_count != 0
        ):
            _fail("non-fold support universe carries fold-only evidence")
        if (
            expected_kind == "cross-arm-all-block-union"
            and lineup_count != score_shape[0]
        ):
            _fail("all-block support universe candidate coverage differs")
        source_support = _validate_source_support(
            universe.get("source_support"),
            lineup_count=lineup_count,
            expected_blocks=expected_training_blocks,
            universe_kind=expected_kind,
            parameter_set_id=expected_arm,
            label=f"support census universe[{ordinal}] source support",
        )
        if expected_kind == "source-arm-all-block":
            source_support_by_arm[str(expected_arm)] = source_support
        elif expected_kind == "cross-arm-fold-eligible":
            fold_support_by_heldout[str(expected_heldout)] = source_support
            fold_excluded_by_heldout[str(expected_heldout)] = excluded_count
        elif expected_kind == "cross-arm-all-block-union":
            full_union_source_support = source_support
        training_metrics = _validate_opportunity_metrics(
            universe.get("training_metrics"),
            expected_blocks=expected_training_blocks,
            source_training_blocks=expected_training_blocks,
            worlds_per_block=worlds_per_block,
            source_support=source_support,
            expected_scope_world_hashes=expected_scope_world_hashes,
            expected_block_world_hashes=expected_block_world_hashes,
            label=f"support census universe[{ordinal}] training metrics",
        )
        if (
            training_metrics.get("lineup_count") != lineup_count
            or training_metrics.get("lineup_ids_sha256")
            != universe.get("lineup_ids_sha256")
        ):
            _fail("support census universe training membership differs")
        if expected_kind == "source-arm-all-block":
            source_metrics_by_arm[str(expected_arm)] = training_metrics
        elif expected_kind == "cross-arm-all-block-union":
            full_union_training_metrics = training_metrics
        heldout_metrics = universe.get("heldout_metrics_descriptive")
        if expected_heldout is None:
            if heldout_metrics is not None:
                _fail("non-fold support universe carries held-out metrics")
        else:
            validated_heldout = _validate_opportunity_metrics(
                heldout_metrics,
                expected_blocks=[expected_heldout],
                source_training_blocks=expected_training_blocks,
                worlds_per_block=worlds_per_block,
                source_support=source_support,
                expected_scope_world_hashes=expected_scope_world_hashes,
                expected_block_world_hashes=expected_block_world_hashes,
                label=f"support census universe[{ordinal}] held-out metrics",
            )
            if (
                validated_heldout.get("lineup_count") != lineup_count
                or validated_heldout.get("lineup_ids_sha256")
                != universe.get("lineup_ids_sha256")
            ):
                _fail("support census universe held-out membership differs")
            ge_230_rows = [
                _mapping(item, label="fold ge-230 threshold")
                for item in _sequence(
                    training_metrics.get("thresholds"),
                    label="fold training thresholds",
                )
                if _mapping(item, label="fold threshold").get("label")
                == "ge_230"
            ]
            if len(ge_230_rows) != 1:
                _fail("fold support census lacks one ge-230 threshold")
            fold_ge_230[expected_heldout] = dict(ge_230_rows[0])
        _validate_self_hash(
            universe,
            field="universe_sha256",
            label=f"support census universe[{ordinal}]",
        )

    if (
        set(source_support_by_arm) != set(batch.PARAMETER_SET_ORDER)
        or set(source_metrics_by_arm) != set(batch.PARAMETER_SET_ORDER)
        or set(fold_support_by_heldout) != set(rw.WORLD_BLOCKS)
        or set(fold_excluded_by_heldout) != set(rw.WORLD_BLOCKS)
        or full_union_source_support is None
        or full_union_training_metrics is None
    ):
        _fail("support census source-arm/full-union lineage is incomplete")
    full_candidate_by_arm = _mapping(
        full_union_source_support[
            "candidate_count_by_training_source_arm"
        ],
        label="full-union candidates by source arm",
    )
    if any(
        full_candidate_by_arm[arm] != verified_unique_count_by_arm[arm]
        for arm in batch.PARAMETER_SET_ORDER
    ):
        _fail("full-union arm marginals differ from reconstructed arms")
    pairwise_overlap_total = 0
    for left_ordinal, left_arm in enumerate(batch.PARAMETER_SET_ORDER):
        left_marginals = _mapping(
            source_support_by_arm[left_arm][
                "candidate_count_by_training_source_arm"
            ],
            label=f"source-arm {left_arm} candidate marginals",
        )
        for right_arm in batch.PARAMETER_SET_ORDER[left_ordinal + 1:]:
            right_marginals = _mapping(
                source_support_by_arm[right_arm][
                    "candidate_count_by_training_source_arm"
                ],
                label=f"source-arm {right_arm} candidate marginals",
            )
            if left_marginals[right_arm] != right_marginals[left_arm]:
                _fail("source-arm pairwise overlap marginals are asymmetric")
            pairwise_overlap_total += int(left_marginals[right_arm])

    def histogram_by_degree(
        value: object, *, breadth_field: str, label: str
    ) -> dict[int, int]:
        return {
            int(row[breadth_field]): int(row["lineup_count"])
            for row in _sequence(value, label=label)
        }

    full_arm_histogram = histogram_by_degree(
        full_union_source_support["training_source_arm_breadth_histogram"],
        breadth_field="arm_count",
        label="full-union source-arm breadth histogram",
    )
    if pairwise_overlap_total != sum(
        degree * (degree - 1) // 2 * count
        for degree, count in full_arm_histogram.items()
    ):
        _fail("full-union arm breadth differs from pairwise overlaps")
    source_arm_histograms = {
        arm: histogram_by_degree(
            source_support_by_arm[arm][
                "training_source_arm_breadth_histogram"
            ],
            breadth_field="arm_count",
            label=f"source-arm {arm} breadth histogram",
        )
        for arm in batch.PARAMETER_SET_ORDER
    }
    for degree in range(1, len(batch.PARAMETER_SET_ORDER) + 1):
        if sum(
            source_arm_histograms[arm].get(degree, 0)
            for arm in batch.PARAMETER_SET_ORDER
        ) != degree * full_arm_histogram.get(degree, 0):
            _fail("source-arm/full-union breadth distributions differ")

    full_candidate_by_block = _mapping(
        full_union_source_support[
            "candidate_count_by_training_origin_block"
        ],
        label="full-union candidates by origin block",
    )
    full_origin_histogram = histogram_by_degree(
        full_union_source_support[
            "training_origin_block_breadth_histogram"
        ],
        breadth_field="block_count",
        label="full-union origin-block breadth histogram",
    )
    if sum(fold_excluded_by_heldout.values()) != full_origin_histogram.get(1, 0):
        _fail("fold exclusions differ from full-union origin breadth")
    fold_origin_histograms: dict[str, dict[int, int]] = {}
    for heldout in rw.WORLD_BLOCKS:
        fold_support = fold_support_by_heldout[heldout]
        fold_candidates_by_block = _mapping(
            fold_support["candidate_count_by_training_origin_block"],
            label=f"fold {heldout} candidates by origin block",
        )
        if any(
            fold_candidates_by_block[block]
            != (0 if block == heldout else full_candidate_by_block[block])
            for block in rw.WORLD_BLOCKS
        ):
            _fail("fold/full-union origin-block marginals differ")
        fold_origin_histograms[heldout] = histogram_by_degree(
            fold_support["training_origin_block_breadth_histogram"],
            breadth_field="block_count",
            label=f"fold {heldout} origin-block breadth histogram",
        )
    for degree in range(1, len(rw.WORLD_BLOCKS)):
        if sum(
            histogram.get(degree, 0)
            for histogram in fold_origin_histograms.values()
        ) != (
            (len(rw.WORLD_BLOCKS) - degree)
            * full_origin_histogram.get(degree, 0)
            + (degree + 1) * full_origin_histogram.get(degree + 1, 0)
        ):
            _fail("fold/full-union origin breadth distributions differ")

    full_thresholds = _sequence(
        full_union_training_metrics["thresholds"],
        label="full-union training thresholds",
    )
    source_thresholds = {
        arm: _sequence(
            source_metrics_by_arm[arm]["thresholds"],
            label=f"source-arm {arm} training thresholds",
        )
        for arm in batch.PARAMETER_SET_ORDER
    }
    for threshold_ordinal, raw_full_threshold in enumerate(full_thresholds):
        full_threshold = _mapping(
            raw_full_threshold,
            label=f"full-union threshold[{threshold_ordinal}]",
        )
        full_lineage = _mapping(
            full_threshold["event_source_lineage"],
            label=f"full-union threshold[{threshold_ordinal}] lineage",
        )
        full_event_by_arm = _mapping(
            full_lineage["event_lineup_count_by_training_source_arm"],
            label=f"full-union threshold[{threshold_ordinal}] events by arm",
        )
        full_occurrence_by_arm = _mapping(
            full_lineage["event_training_occurrence_count_by_source_arm"],
            label=(
                f"full-union threshold[{threshold_ordinal}] occurrences by arm"
            ),
        )
        source_lineages: dict[str, Mapping[str, object]] = {}
        for arm in batch.PARAMETER_SET_ORDER:
            source_threshold = _mapping(
                source_thresholds[arm][threshold_ordinal],
                label=f"source-arm {arm} threshold[{threshold_ordinal}]",
            )
            source_lineage = _mapping(
                source_threshold["event_source_lineage"],
                label=f"source-arm {arm} threshold lineage",
            )
            source_lineages[arm] = source_lineage
            source_event_count = source_threshold["event_lineup_count"]
            source_event_by_arm = _mapping(
                source_lineage[
                    "event_lineup_count_by_training_source_arm"
                ],
                label=f"source-arm {arm} threshold events by arm",
            )
            source_occurrence_by_arm = _mapping(
                source_lineage[
                    "event_training_occurrence_count_by_source_arm"
                ],
                label=f"source-arm {arm} threshold occurrences by arm",
            )
            if (
                full_event_by_arm[arm] != source_event_count
                or source_event_by_arm[arm] != source_event_count
                or full_occurrence_by_arm[arm]
                != source_occurrence_by_arm[arm]
            ):
                _fail("full/source-arm threshold lineage differs")
        for left_ordinal, left_arm in enumerate(batch.PARAMETER_SET_ORDER):
            left_events = _mapping(
                source_lineages[left_arm][
                    "event_lineup_count_by_training_source_arm"
                ],
                label=f"source-arm {left_arm} threshold overlaps",
            )
            for right_arm in batch.PARAMETER_SET_ORDER[left_ordinal + 1:]:
                right_events = _mapping(
                    source_lineages[right_arm][
                        "event_lineup_count_by_training_source_arm"
                    ],
                    label=f"source-arm {right_arm} threshold overlaps",
                )
                if left_events[right_arm] != right_events[left_arm]:
                    _fail("source-arm threshold overlaps are asymmetric")

    support_gate = _mapping(
        support.get("coverage_ge_230_support_gate"),
        label="coverage-ge-230 support gate",
    )
    _exact_keys(
        support_gate,
        _SUPPORT_GATE_KEYS,
        label="coverage-ge-230 support gate",
    )
    observations = _sequence(
        support_gate.get("fold_observations"),
        label="coverage-ge-230 fold observations",
    )
    if (
        support_gate.get("role")
        != "support-observation-not-selector-or-promotion-authority"
        or support_gate.get("requires_every_training_block_nonzero") is not True
        or support_gate.get("minimum_training_opportunity_world_count")
        != census.LITERAL_230_MIN_TRAINING_OPPORTUNITY_WORLDS
        or support_gate.get("failure_role")
        != "literal-230-remains-diagnostic-use-bounded-tail-fallback"
        or len(observations) != len(rw.WORLD_BLOCKS)
    ):
        _fail("coverage-ge-230 support gate contract differs")
    for heldout, raw_observation in zip(
        rw.WORLD_BLOCKS, observations, strict=True
    ):
        observation = _mapping(
            raw_observation, label=f"coverage-ge-230 gate[{heldout}]"
        )
        _exact_keys(
            observation,
            _SUPPORT_OBSERVATION_KEYS,
            label=f"coverage-ge-230 gate[{heldout}]",
        )
        training_blocks = [
            block for block in rw.WORLD_BLOCKS if block != heldout
        ]
        ge_230 = fold_ge_230[heldout]
        by_block = [
            _mapping(item, label=f"fold {heldout} ge-230 block")
            for item in _sequence(
                ge_230.get("by_block"),
                label=f"fold {heldout} ge-230 blocks",
            )
        ]
        if [item.get("block_id") for item in by_block] != training_blocks:
            _fail("fold ge-230 block order differs")
        block_counts = [
            _exact_int(
                item.get("opportunity_world_count"),
                label=f"fold {heldout} block opportunity count",
            )
            for item in by_block
        ]
        opportunity_count = _exact_int(
            ge_230.get("opportunity_world_count"),
            label=f"fold {heldout} opportunity count",
        )
        every_nonzero = all(count > 0 for count in block_counts)
        passed = (
            every_nonzero
            and opportunity_count
            >= census.LITERAL_230_MIN_TRAINING_OPPORTUNITY_WORLDS
        )
        if (
            opportunity_count != sum(block_counts)
            or observation.get("heldout_block") != heldout
            or observation.get("training_blocks") != training_blocks
            or observation.get("every_training_block_nonzero")
            is not every_nonzero
            or observation.get("training_opportunity_world_count")
            != opportunity_count
            or observation.get("nomination_support_passed") is not passed
        ):
            _fail("coverage-ge-230 fold observation differs from census")

    if (
        output_hashes.get("compatibility_import_sha256")
        != reconstruction.get("compatibility_import_sha256")
        or output_hashes.get("candidate_provenance_sha256")
        != reconstruction.get("candidate_provenance_sha256")
        or output_hashes.get("reconstruction_sha256") != reconstruction_sha
        or output_hashes.get("matrix_binding_sha256") != matrix_sha
        or output_hashes.get("score_matrix_sha256")
        != matrix_binding.get("score_matrix_sha256")
        or output_hashes.get("support_census_sha256") != support_sha
    ):
        _fail("execution output hashes differ from nested evidence")
    _require_nested_authorities_false(result, label="one-slate execution result")


def _validate_execution_result(
    value: object,
    *,
    slate_id: str,
    panel_identity: Mapping[str, object],
    panel_body: Mapping[str, object],
    membership: Mapping[str, object],
    carrier_bindings: Mapping[str, object],
) -> dict[str, object]:
    result = dict(_mapping(value, label="one-slate execution result"))
    _exact_keys(result, _RESULT_KEYS, label="one-slate execution result")
    if (
        result.get("schema_version") != execution.RESULT_SCHEMA
        or result.get("execution_mode")
        != "authoritative-dose-one-slate-outcome-blind-smoke"
        or result.get("slate_id") != slate_id
        or result.get("panel_index_identity") != panel_identity
        or result.get("panel_index_sha256")
        != panel_body.get("panel_index_sha256")
        or batch.canonical_json_bytes(result.get("accepted_slate_membership"))
        != batch.canonical_json_bytes(dict(membership))
        or result.get("task_acceptance_identity")
        != membership.get("task_acceptance_identity")
        or result.get("carrier_identity") != membership.get("carrier_identity")
        or any(
            result.get(field) is not False
            for field in execution._FALSE_AUTHORITY_FIELDS
        )
    ):
        _fail("one-slate execution result binding or authority differs")
    configuration = _mapping(
        result.get("configuration"), label="execution configuration"
    )
    _exact_keys(
        configuration,
        _CONFIGURATION_KEYS,
        label="execution configuration",
    )
    verification = _mapping(
        result.get("verification"), label="execution verification"
    )
    _exact_keys(
        verification,
        _VERIFICATION_KEYS,
        label="execution verification",
    )
    if (
        configuration.get("require_authoritative") is not True
        or any(verification.get(field) is not True for field in _VERIFICATION_KEYS)
        or result.get("accepted_slate_membership_sha256")
        != batch.canonical_sha256(dict(membership))
    ):
        _fail("one-slate execution result is not authoritative-dose")
    source_identity = _identity(
        result.get("later_source_freeze_identity"),
        label="execution later-source identity",
    )
    world_artifacts = _mapping(
        result.get("world_artifact_identities"),
        label="execution world artifact identities",
    )
    if set(world_artifacts) != set(batch.TASK_WORLD_SOURCE_ROLES):
        _fail("execution world artifact roles differ")
    normalized_world_artifacts = {
        role: _identity(
            world_artifacts[role], label=f"execution world artifact {role}"
        )
        for role in batch.TASK_WORLD_SOURCE_ROLES
    }
    expected_sources = _mapping(
        carrier_bindings.get("source_receipts"),
        label="validated carrier source receipts",
    )
    expected_world_artifacts = _mapping(
        carrier_bindings.get("world_artifact_receipts"),
        label="validated carrier world artifacts",
    )
    if (
        result.get("carrier_identity")
        != carrier_bindings.get("carrier_identity")
        or source_identity != result.get("later_source_freeze_identity")
        or source_identity != expected_sources.get("later_source_freeze")
        or normalized_world_artifacts != dict(world_artifacts)
        or normalized_world_artifacts != dict(expected_world_artifacts)
        or len({value["uri"] for value in normalized_world_artifacts.values()})
        != len(normalized_world_artifacts)
        or result.get("world_artifact_identity_set_sha256")
        != carrier_bindings.get("world_artifact_receipt_set_sha256")
        or result.get("world_artifact_identity_set_sha256")
        != batch.canonical_sha256(normalized_world_artifacts)
    ):
        _fail("execution source/world artifact binding differs")
    _validate_nested_result_evidence(result, slate_id=slate_id)
    _validate_self_hash(
        result,
        field="one_slate_execution_sha256",
        label="one-slate execution result",
    )
    try:
        batch.canonical_json_bytes(result)
    except Exception as exc:
        raise CorpusExtremeTailOneSlateSmokeCLIError(
            "one-slate execution result is not finite canonical JSON"
        ) from exc
    return result


def _write_result_create_once(path: Path, result: Mapping[str, object]) -> None:
    raw = batch.canonical_json_bytes(dict(result)) + b"\n"
    _reject_symlink_components(path, label="result output path")
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        raise CorpusExtremeTailOneSlateSmokeCLIError(
            "result output create-once collision already exists"
        ) from None
    except OSError as exc:
        raise CorpusExtremeTailOneSlateSmokeCLIError(
            "result output create-once write failed"
        ) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run one read-only extreme-tail census smoke from the published "
            "Foundry v12 panel"
        )
    )
    parser.add_argument(
        "--panel-publication-receipt",
        required=True,
        type=Path,
        help="canonical local foundry-v12-panel-index-publication/v1 receipt",
    )
    parser.add_argument(
        "--slate-id",
        required=True,
        help="exact accepted panel slate_id to smoke",
    )
    parser.add_argument(
        "--result-output",
        type=Path,
        help="optional absolute create-once local result JSON path",
    )
    return parser


def run(argv: Sequence[str], *, store: ReadStore) -> dict[str, object]:
    args = _parser().parse_args(list(argv))
    if type(args.slate_id) is not str or not args.slate_id:
        _fail("slate_id must be one explicit nonempty value")

    # The complete local filesystem boundary is checked before the first GCS
    # read.  Existing outputs are collisions, never resume/retry signals.
    _preflight_result_output(args.result_output)
    receipt = _load_publication_receipt(args.panel_publication_receipt)

    panel_body, panel_identity, membership = _parse_and_select_panel(
        receipt=receipt,
        store=store,
        slate_id=args.slate_id,
    )
    carrier_bindings = _load_carrier_bindings(
        carrier_identity=membership["carrier_identity"],
        membership=membership,
        store=store,
    )
    try:
        raw_result = execution.execute_one_slate_extreme_tail_census(
            validated_panel_index=panel_body,
            panel_index_identity=panel_identity,
            accepted_slate_membership=membership,
            task_acceptance_identity=membership["task_acceptance_identity"],
            carrier_identity=membership["carrier_identity"],
            read_exact=store.read,
            require_authoritative=True,
        )
    except execution.CorpusExtremeTailOneSlateExecutionError as exc:
        raise CorpusExtremeTailOneSlateSmokeCLIError(str(exc)) from exc
    result = _validate_execution_result(
        raw_result,
        slate_id=args.slate_id,
        panel_identity=panel_identity,
        panel_body=panel_body,
        membership=membership,
        carrier_bindings=carrier_bindings,
    )
    if args.result_output is not None:
        _write_result_create_once(args.result_output, result)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    try:
        from google.cloud import storage
    except ImportError as exc:  # pragma: no cover - production dependency gate
        raise CorpusExtremeTailOneSlateSmokeCLIError(
            "google-cloud-storage is required for this command"
        ) from exc
    result = run(
        sys.argv[1:] if argv is None else argv,
        store=GCSReadStore(storage.Client()),
    )
    sys.stdout.buffer.write(batch.canonical_json_bytes(result) + b"\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
