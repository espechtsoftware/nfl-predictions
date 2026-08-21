"""Pure label-and-fit boundary for the LR8 earlier-period anatomy law.

This module deliberately has no warehouse, object-store, lease, CBC, or cloud
client.  A later historical-outcome runner must acquire the shared lease,
publish one canonical authoritative player/DST score map create-once, and pass
that map plus its generation-pinned receipt here.  The adapter then:

* reopens and validates the complete, externally pinned 35-slate training
  source freeze;
* exposes only its post-cross-block candidate identities and anatomy fields;
* reconciles an exact 2019/2021 player universe and independently sums every
  nine-player roster in integer micro-DK;
* applies the sole registered ``>=200`` label and equal-slate fit law from
  :mod:`lr8_historical_arm`; and
* returns deterministic canonical bytes suitable for a create-once publisher.

No function in this file authorizes a score read, later-period construction,
prospective execution, production use, or adoption.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import math
import re
from typing import Final

import numpy as np

from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import lr8_training_source as source
from nfl_dfs.research import residual_world_columns as rw


LABEL_FIT_VERSION: Final = "lr8-earlier-period-label-fit-v1"
SCORE_MAP_VERSION: Final = "lr8-authoritative-player-dst-score-map-v1"
LABEL_READ_ATTEMPT_VERSION: Final = "lr8-label-read-attempt-v1"
AUTHORITATIVE_QUERY_VERSION: Final = "lr8-authoritative-score-query-v1"
AUTHORITATIVE_QUERY_ID: Final = "lr8-2019-2021-player-dst-catalog-score-query-v1"
SCORE_SUPPLIER_BOUNDARY: Final = (
    "external-historical-outcome-lease-protected-runner-v1"
)
SCORE_SUPPLIER_VERSION: Final = "lr8-authoritative-label-score-map-supplier-v1"
SCORE_SOURCE_EXTRACT_VERSION: Final = "lr8-authoritative-score-source-extract-v1"
SCORE_UNIT: Final = "micro_dk_1e-6"
AUTHORITATIVE_SOURCE_ID: Final = (
    "nfl_features.player_week_actuals.dk_points+"
    "nfl_features.team_defense_week.dst_dk_points-v1"
)
SKILL_ACTUAL_SOURCE: Final = "nfl_features.player_week_actuals.dk_points"
DST_ACTUAL_SOURCE: Final = "nfl_features.team_defense_week.dst_dk_points"
HISTORICAL_OUTCOME_LEASE_VERSION: Final = "historical-outcome-active-v1"
HISTORICAL_OUTCOME_LEASE_URI: Final = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "historical-outcome-active-v1.json"
)
SCORE_OUTPUT_ROOT: Final = (
    "gs://nfl-predictions-503414-raw/research/lr8-authoritative-label-score-map"
)
AUTHORITATIVE_SQL_SHA256: Final = (
    "f25fd4c3d0b4dd5d9317ca0aed53fe7a4b1180289f6c98c0a9e100586791b7eb"
)

SCORE_ROW_FIELDS: Final = (
    "season",
    "week",
    "player_id",
    "position",
    "realized_score_micro",
    "actual_source",
)
SCORE_SOURCE_ROW_FIELDS: Final = (
    "season",
    "week",
    "source_kind",
    "source_key",
    "realized_score_micro",
)

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_GENERATION: Final = re.compile(r"[1-9][0-9]*")
_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")

_SOURCE_FIELDS: Final = frozenset({
    "protocol_id",
    "version",
    "canonical_panel_id",
    "target_seasons",
    "excluded_candidate_source_seasons",
    "slate_count",
    "slate_keys",
    "blocks",
    "pre_cross_block_candidates_per_slate",
    "candidate_world_family",
    "role_belief_worlds_used",
    "role_seed_usage",
    "hard_domain_id",
    "former_house_rules_not_applied",
    "anatomy_feature_columns",
    "replay_refits",
    "slates",
    "post_dedup_candidate_rows",
    "post_dedup_candidate_rows_sha256",
    "old_law_candidate_totals_loaded",
    "target_player_labels_read",
    "candidate_labels_read",
    "b1_inputs_used",
    "a2a_inputs_used",
    "later_period_inputs_used",
    "bigquery_outcome_query_present",
    "historical_label_read_licensed",
    "historical_execution_licensed",
    "prospective_confirmation_licensed",
    "production_change_licensed",
    "manifest_sha256",
})

_SLATE_FIELDS: Final = frozenset({
    "season",
    "week",
    "catalog",
    "catalog_sha256",
    "catalog_source_receipts",
    "incumbent_candidate_count",
    "incumbent_candidates_sha256",
    "incumbent_source_receipts",
    "blocks",
    "pre_cross_block_candidate_count",
    "pre_cross_block_sha256",
    "post_cross_block_candidate_count",
    "post_cross_block_candidates",
    "post_cross_block_sha256",
    "cross_block_duplicates",
})

_BLOCK_FIELDS: Final = frozenset({
    "block",
    "projection_seed",
    "source_environment_role_seed_nonoperative",
    "candidate_world_family",
    "role_belief_worlds_used",
    "role_seed_usage",
    "player_ids",
    "player_ids_sha256",
    "player_draws",
    "world_order_law",
    "world_order_sha256",
    "source_receipts",
    "solve_attempt_count",
    "ordered_solve_attempts",
    "ordered_solve_attempts_sha256",
    "unique_candidates",
    "unique_candidate_count",
    "candidate_identities_sha256",
    "anatomy_sha256",
    "legality_sha256",
})

_ATTEMPT_FIELDS: Final = frozenset({
    "block",
    "projection_seed",
    "world_index",
    "roster",
    "objective_micro",
    "admitted_unique",
    "request_sha256",
    "evidence_receipts",
    "evidence_manifest_sha256",
})

_CANDIDATE_FIELDS: Final = frozenset({
    "season",
    "week",
    "roster",
    "anatomy_features",
    "first_source_block",
    "first_source_world_index",
    "source_occurrences",
})

_REPLAY_REFIT_FIELDS: Final = frozenset({
    "target_season",
    "block",
    "projection_seed",
    "source_environment_role_seed_nonoperative",
    "replay_path_id",
    "model_training_seasons",
    "model_fit_input_sha256",
    "model_fit_sha256",
    "fit_source_receipts",
    "target_player_labels_read",
    "candidate_labels_read",
    "candidate_world_family",
    "role_belief_worlds_used",
    "role_seed_usage",
    "b1_inputs_used",
    "a2a_inputs_used",
    "later_period_inputs_used",
})

_SCORE_MAP_FIELDS: Final = frozenset({
    "schema",
    "protocol_id",
    "supplier_boundary",
    "training_source_manifest_sha256",
    "training_source_object",
    "target_seasons",
    "slate_keys",
    "row_fields",
    "score_unit",
    "catalog_universe_sha256",
    "authoritative_source_id",
    "query_identity",
    "query_sha256",
    "score_source_receipts",
    "score_source_extract",
    "score_source_extract_receipt",
    "label_read_attempt",
    "label_read_attempt_receipt",
    "rows",
    "score_rows_sha256",
    "b1_inputs_used",
    "a2a_inputs_used",
    "winner_inputs_used",
    "later_period_inputs_used",
    "production_inputs_used",
})

_SCORE_SOURCE_EXTRACT_FIELDS: Final = frozenset("""
schema supplier_version protocol_id supplier_boundary
training_source_manifest_sha256 training_source_object target_seasons slate_keys
catalog_universe_sha256 catalog_keys catalog_keys_sha256 query_identity query_sha256
sql_sha256 parameters parameters_sha256 source_snapshot_at job_receipt table_receipts
table_metadata_stable_during_query historical_outcome_lease_unchanged_during_query
label_read_attempt label_read_attempt_receipt row_fields rows rows_sha256
query_completed_at b1_inputs_used a2a_inputs_used winner_inputs_used
later_period_inputs_used production_inputs_used
""".split())
_SCORE_SOURCE_CATALOG_KEY_FIELDS: Final = frozenset(
    "season week source_kind source_key player_id position".split()
)

_LEASE_BODY_FIELDS: Final = frozenset({
    "version",
    "run_id",
    "job",
    "code_sha",
    "image",
    "acquired_at",
})

_LEASE_BINDING_FIELDS: Final = frozenset({"body", "object_receipt"})

_LABEL_READ_ATTEMPT_FIELDS: Final = frozenset({
    "schema",
    "protocol_id",
    "supplier_boundary",
    "stage",
    "training_source_manifest_sha256",
    "training_source_object",
    "target_seasons",
    "slate_keys",
    "query_identity",
    "query_sha256",
    "historical_outcome_lease",
    "started_at",
    "uses_realized_outcomes_at_creation",
    "retry_licensed",
    "b1_inputs_used",
    "a2a_inputs_used",
    "winner_inputs_used",
    "later_period_inputs_used",
    "production_inputs_used",
})

_TRAINING_SUMMARY_FIELDS: Final = frozenset({
    "manifest_sha256",
    "object_receipt",
    "canonical_panel_id",
    "target_seasons",
    "slate_keys",
    "post_cross_block_candidate_rows",
    "post_cross_block_candidate_surface_sha256",
    "catalog_universe_sha256",
    "candidate_surface",
})

_SCORE_PROVENANCE_FIELDS: Final = frozenset({
    "supplier_boundary",
    "authoritative_source_id",
    "query_identity",
    "query_sha256",
    "score_map_object",
    "score_source_receipts",
    "score_source_extract",
    "score_source_extract_object",
    "label_read_attempt",
    "label_read_attempt_object",
    "score_unit",
    "score_row_count",
    "score_rows",
    "score_rows_sha256",
    "catalog_universe_sha256",
    "exact_catalog_universe",
    "candidate_totals_independently_summed",
    "b1_inputs_used",
    "a2a_inputs_used",
    "winner_inputs_used",
    "later_period_inputs_used",
    "production_inputs_used",
})

_LABELS_FIELDS: Final = frozenset({
    "target",
    "threshold_micro",
    "row_count",
    "positive_rows",
    "rows",
    "rows_sha256",
    "score_reconciliation",
})

_LABEL_ROW_FIELDS: Final = frozenset({
    "season",
    "week",
    "roster",
    "anatomy_features",
    "realized_total_micro",
    "label_200_plus",
})

_WEIGHTING_FIELDS: Final = frozenset({
    "law",
    "training_cells",
    "training_rows",
    "cells",
    "cells_sha256",
})

_WEIGHT_CELL_FIELDS: Final = frozenset({
    "season",
    "week",
    "candidate_rows",
    "unnormalized_row_weight_numerator",
    "unnormalized_row_weight_denominator",
    "normalized_row_weight_numerator",
    "normalized_row_weight_denominator",
    "cell_total_weight_numerator",
    "cell_total_weight_denominator",
})

_FIT_LAW_FIELDS: Final = frozenset({
    "model_version",
    "feature_columns",
    "c",
    "solver",
    "class_weight",
    "max_iter",
    "feature_sweep",
    "hyperparameter_sweep",
    "target_sweep",
    "threshold_sweep",
})

_LICENSE_FIELDS: Final = (
    "evaluation_2023_2025_construction_licensed",
    "evaluation_2023_2025_score_read_licensed",
    "prospective_2026_execution_licensed",
    "production_change_licensed",
    "adoption_licensed",
)


class LR8LabelFitError(ValueError):
    """A fail-closed LR8 label/fit contract violation."""


@dataclass(frozen=True, slots=True)
class FrozenFitCandidate:
    """The complete and only candidate surface exposed by the source lock."""

    season: int
    week: int
    roster: tuple[str, ...]
    anatomy_features: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class _ValidatedSource:
    manifest_sha256: str
    object_receipt: dict[str, object]
    candidates: tuple[FrozenFitCandidate, ...]
    catalogs: Mapping[tuple[int, int], tuple[rw.PlayerSpec, ...]]
    catalog_universe_sha256: str
    candidate_surface_sha256: str


def canonical_json(value: object) -> bytes:
    """Canonical bytes used by every input and create-once output binding."""
    try:
        return source.canonical_json(value)
    except source.LR8TrainingSourceError as exc:
        raise LR8LabelFitError(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json(value)).hexdigest()


def _same_canonical_value(left: object, right: object) -> bool:
    return canonical_json(left) == canonical_json(right)


def authoritative_query_identity() -> dict[str, object]:
    """Return the sole registered outcome-query contract for the fit stage."""
    return {
        "schema": AUTHORITATIVE_QUERY_VERSION,
        "query_id": AUTHORITATIVE_QUERY_ID,
        "protocol_id": lr8.PROTOCOL_ID,
        "target_seasons": list(source.TARGET_SEASONS),
        "slate_keys": [list(key) for key in source.EXPECTED_SLATE_KEYS],
        "catalog_boundary": "exact_frozen_training_catalog_left_join_v1",
        "skill_actual_source": SKILL_ACTUAL_SOURCE,
        "dst_actual_source": DST_ACTUAL_SOURCE,
        "output_row_fields": list(SCORE_ROW_FIELDS),
        "score_unit": SCORE_UNIT,
        "exact_catalog_coverage_required": True,
        "b1_sources_allowed": False,
        "a2a_sources_allowed": False,
        "winner_sources_allowed": False,
        "later_period_sources_allowed": False,
        "production_sources_allowed": False,
    }


AUTHORITATIVE_QUERY_SHA256: Final = canonical_sha256(
    authoritative_query_identity()
)


def _strict_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise LR8LabelFitError(f"{label} must be a canonical string")
    return value


def _strict_sha256(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise LR8LabelFitError(f"{label} must be a lowercase SHA-256")
    return value


def _exact_int(
    value: object,
    *,
    label: str,
    minimum: int | None = 0,
) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise LR8LabelFitError(f"{label} must be an exact integer")
    result = int(value)
    if minimum is not None and result < minimum:
        raise LR8LabelFitError(f"{label} must be >= {minimum}")
    return result


def _literal_bool(value: object, *, label: str, expected: bool) -> None:
    if not isinstance(value, bool) or value is not expected:
        raise LR8LabelFitError(f"{label} must be literal {expected}")


def _utc_timestamp(value: object, *, label: str) -> str:
    text = _strict_string(value, label=label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LR8LabelFitError(f"{label} must be an ISO-8601 timestamp") from exc
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or parsed.utcoffset().total_seconds() != 0
    ):
        raise LR8LabelFitError(f"{label} must be an aware UTC timestamp")
    return text


def _receipt(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "uri", "generation", "sha256", "bytes",
    }:
        raise LR8LabelFitError(f"{label} is not an exact content receipt")
    uri = value.get("uri")
    generation = value.get("generation")
    digest = value.get("sha256")
    size = value.get("bytes")
    if (
        not isinstance(uri, str)
        or not uri.startswith("gs://")
        or not uri.removeprefix("gs://").partition("/")[0]
        or not uri.removeprefix("gs://").partition("/")[2]
        or not isinstance(generation, str)
        or _GENERATION.fullmatch(generation) is None
        or not isinstance(digest, str)
        or _SHA256.fullmatch(digest) is None
        or isinstance(size, bool)
        or not isinstance(size, int)
        or size <= 0
    ):
        raise LR8LabelFitError(f"{label} is not an exact content receipt")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": size,
    }


def _create_once_receipt(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "uri", "generation", "sha256", "bytes", "create_only",
    }:
        raise LR8LabelFitError(f"{label} is not an exact create-once receipt")
    _literal_bool(value["create_only"], label=f"{label} create_only", expected=True)
    receipt = _receipt(
        {key: value[key] for key in ("uri", "generation", "sha256", "bytes")},
        label=label,
    )
    return {**receipt, "create_only": True}


def _receipts(value: object, *, label: str) -> tuple[dict[str, object], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise LR8LabelFitError(f"{label} must be a receipt sequence")
    rows = tuple(
        _receipt(item, label=f"{label}[{index}]")
        for index, item in enumerate(value)
    )
    if not rows or len({tuple(row.values()) for row in rows}) != len(rows):
        raise LR8LabelFitError(f"{label} is empty or repeats a receipt")
    return rows


def _bound_object_receipt(
    value: object,
    payload: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    receipt = _receipt(value, label=label)
    raw = canonical_json(payload)
    # Existing source publishers use both strict canonical JSON bytes and the
    # same bytes with one terminal newline.  The scientific manifest hash is
    # representation-independent; accept only those two known byte envelopes
    # while retaining the exact generation-pinned content receipt.
    identities = {
        (sha256(candidate).hexdigest(), len(candidate))
        for candidate in (raw, raw + b"\n")
    }
    if (receipt["sha256"], receipt["bytes"]) not in identities:
        raise LR8LabelFitError(f"{label} does not bind the canonical object bytes")
    return receipt


def _bound_create_once_receipt(
    value: object,
    payload: Mapping[str, object],
    *,
    label: str,
    expected_uri: str | None = None,
) -> dict[str, object]:
    receipt = _create_once_receipt(value, label=label)
    if expected_uri is not None and receipt["uri"] != expected_uri:
        raise LR8LabelFitError(f"{label} URI differs")
    raw = canonical_json(payload)
    identities = {
        (sha256(candidate).hexdigest(), len(candidate))
        for candidate in (raw, raw + b"\n")
    }
    if (receipt["sha256"], receipt["bytes"]) not in identities:
        raise LR8LabelFitError(f"{label} does not bind the canonical object bytes")
    return receipt


def _candidate_payload(value: FrozenFitCandidate, raw: Mapping[str, object]) -> dict[str, object]:
    return {
        "season": value.season,
        "week": value.week,
        "roster": list(value.roster),
        "anatomy_features": [
            int(item) if float(item).is_integer() else float(item)
            for item in value.anatomy_features
        ],
        "first_source_block": raw["first_source_block"],
        "first_source_world_index": raw["first_source_world_index"],
        "source_occurrences": raw["source_occurrences"],
    }


def _fit_candidate_payload(value: FrozenFitCandidate) -> dict[str, object]:
    return {
        "season": value.season,
        "week": value.week,
        "roster": list(value.roster),
        "anatomy_features": [
            int(item) if float(item).is_integer() else float(item)
            for item in value.anatomy_features
        ],
    }


def _catalog(
    value: object,
    *,
    season: int,
    week: int,
) -> tuple[rw.PlayerSpec, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, list):
        raise LR8LabelFitError("source catalog must be a JSON list")
    rows: list[rw.PlayerSpec] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping) or set(item) != source.CANONICAL_CATALOG_FIELDS:
            raise LR8LabelFitError(
                f"source catalog row {season}W{week}/{index} fields differ"
            )
        try:
            player = rw.PlayerSpec.from_mapping(item)
        except (KeyError, TypeError, rw.ResidualWorldError) as exc:
            raise LR8LabelFitError("source catalog row is malformed") from exc
        if player.salary <= 0:
            raise LR8LabelFitError("source catalog salary must be positive")
        rows.append(player)
    result = tuple(rows)
    if (
        len(result) < rw.ROSTER_SIZE
        or tuple(player.player_id for player in result)
        != tuple(sorted(player.player_id for player in result))
        or len({player.player_id for player in result}) != len(result)
        or "DST" not in {player.position for player in result}
    ):
        raise LR8LabelFitError("source catalog identity/order differs")
    return result


def _anatomy(value: object, *, label: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != len(lr8.ANATOMY_FEATURES):
        raise LR8LabelFitError(f"{label} width differs")
    result: list[float] = []
    for item in value:
        if type(item) not in (int, float) or not math.isfinite(float(item)):
            raise LR8LabelFitError(f"{label} must contain finite JSON numbers")
        number = float(item)
        if not number.is_integer():
            raise LR8LabelFitError(f"{label} must contain exact integer features")
        result.append(number)
    return tuple(result)


def _candidate(
    value: object,
    *,
    season: int,
    week: int,
    players: tuple[rw.PlayerSpec, ...],
    expected_block: str | None,
) -> tuple[FrozenFitCandidate, dict[str, object]]:
    if not isinstance(value, Mapping) or set(value) != _CANDIDATE_FIELDS:
        raise LR8LabelFitError("frozen candidate fields differ")
    if (
        _exact_int(value["season"], label="candidate season") != season
        or _exact_int(value["week"], label="candidate week", minimum=1) != week
    ):
        raise LR8LabelFitError("frozen candidate slate differs")
    raw_roster = value["roster"]
    if not isinstance(raw_roster, list):
        raise LR8LabelFitError("frozen candidate roster must be a JSON list")
    try:
        roster = rw.canonical_identity(raw_roster)
    except rw.ResidualWorldError as exc:
        raise LR8LabelFitError("frozen candidate roster is malformed") from exc
    if tuple(raw_roster) != roster:
        raise LR8LabelFitError("frozen candidate roster is not canonical")
    try:
        audited = lr8.audit_dk_classic_identity(players, roster)
    except lr8.LR8Error as exc:
        raise LR8LabelFitError("frozen candidate is not DK Classic legal") from exc
    features = _anatomy(value["anatomy_features"], label="candidate anatomy")
    if tuple(lr8.lineup_anatomy(players, audited)) != features:
        raise LR8LabelFitError("frozen candidate anatomy does not replay")
    block = _strict_string(value["first_source_block"], label="candidate block")
    if block not in source.BLOCK_ORDER or (
        expected_block is not None and block != expected_block
    ):
        raise LR8LabelFitError("frozen candidate first-source block differs")
    world_index = _exact_int(
        value["first_source_world_index"],
        label="candidate first-source world",
    )
    if world_index >= source.WORLDS_PER_BLOCK:
        raise LR8LabelFitError("candidate first-source world is outside the block")
    occurrences_raw = value["source_occurrences"]
    if not isinstance(occurrences_raw, list) or not occurrences_raw:
        raise LR8LabelFitError("candidate source occurrences differ")
    occurrences: list[list[object]] = []
    for occurrence in occurrences_raw:
        if not isinstance(occurrence, list) or len(occurrence) != 2:
            raise LR8LabelFitError("candidate source occurrence is malformed")
        occurrence_block = _strict_string(
            occurrence[0], label="candidate occurrence block"
        )
        occurrence_world = _exact_int(
            occurrence[1], label="candidate occurrence world"
        )
        if occurrence_block not in source.BLOCK_ORDER or (
            occurrence_world >= source.WORLDS_PER_BLOCK
        ):
            raise LR8LabelFitError("candidate source occurrence differs")
        occurrences.append([occurrence_block, occurrence_world])
    if occurrences[0] != [block, world_index] or len({
        (str(item[0]), int(item[1])) for item in occurrences
    }) != len(occurrences):
        raise LR8LabelFitError("candidate source occurrences are not canonical")
    if expected_block is not None and occurrences != [[block, world_index]]:
        raise LR8LabelFitError("block candidate has cross-block provenance")
    candidate = FrozenFitCandidate(
        season=season,
        week=week,
        roster=audited,
        anatomy_features=features,
    )
    normalized_raw = {
        **dict(value),
        "source_occurrences": occurrences,
    }
    return candidate, _candidate_payload(candidate, normalized_raw)


def _attempts(
    value: object,
    *,
    block: str,
    projection_seed: int,
) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        raise LR8LabelFitError("ordered solve attempts must be a JSON list")
    rows: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) != _ATTEMPT_FIELDS:
            raise LR8LabelFitError("ordered solve attempt fields differ")
        if (
            item["block"] != block
            or _exact_int(item["projection_seed"], label="attempt seed")
            != projection_seed
        ):
            raise LR8LabelFitError("ordered solve attempt block/seed differs")
        world = _exact_int(item["world_index"], label="attempt world")
        if world >= source.WORLDS_PER_BLOCK:
            raise LR8LabelFitError("ordered solve attempt world is outside the block")
        if not isinstance(item["roster"], list):
            raise LR8LabelFitError("ordered solve attempt roster differs")
        _exact_int(item["objective_micro"], label="attempt objective", minimum=None)
        if not isinstance(item["admitted_unique"], bool):
            raise LR8LabelFitError("attempt admission marker must be literal bool")
        _strict_sha256(item["request_sha256"], label="attempt request hash")
        evidence = _receipts(item["evidence_receipts"], label="attempt evidence")
        if canonical_sha256(list(evidence)) != _strict_sha256(
            item["evidence_manifest_sha256"], label="attempt evidence hash"
        ):
            raise LR8LabelFitError("attempt evidence manifest hash differs")
        rows.append({**dict(item), "evidence_receipts": list(evidence)})
    if not source.UNIQUE_OPTIMA_PER_BLOCK <= len(rows) <= source.MAX_SOLVE_ATTEMPTS_PER_BLOCK:
        raise LR8LabelFitError("ordered solve attempt count differs")
    if len({int(row["world_index"]) for row in rows}) != len(rows):
        raise LR8LabelFitError("ordered solve attempt worlds repeat")
    return tuple(rows)


def _block_candidates(
    value: object,
    *,
    season: int,
    week: int,
    players: tuple[rw.PlayerSpec, ...],
    expected_block: str,
) -> tuple[tuple[FrozenFitCandidate, dict[str, object]], ...]:
    if not isinstance(value, Mapping) or set(value) != _BLOCK_FIELDS:
        raise LR8LabelFitError("frozen source block fields differ")
    projection_seed, role_seed = source.BLOCK_SEED_PAIRS[expected_block]
    if (
        value["block"] != expected_block
        or _exact_int(value["projection_seed"], label="block projection seed")
        != projection_seed
        or _exact_int(
            value["source_environment_role_seed_nonoperative"],
            label="block nonoperative role seed",
        ) != role_seed
        or value["candidate_world_family"] != source.CANDIDATE_WORLD_FAMILY
        or value["role_seed_usage"] != source.ROLE_SEED_USAGE
        or value["world_order_law"] != source.WORLD_ORDER_LAW
    ):
        raise LR8LabelFitError("frozen source block law differs")
    _literal_bool(
        value["role_belief_worlds_used"],
        label="block role-belief worlds used",
        expected=False,
    )
    player_ids = value["player_ids"]
    expected_ids = [player.player_id for player in players]
    if player_ids != expected_ids or source.player_ids_sha256(player_ids) != (
        _strict_sha256(value["player_ids_sha256"], label="block player ids hash")
    ):
        raise LR8LabelFitError("frozen block player universe differs")
    draws = value["player_draws"]
    if (
        not isinstance(draws, Mapping)
        or set(draws) != {"dtype", "shape", "sha256"}
        or draws["dtype"] != np.dtype(np.float32).str
        or draws["shape"] != [len(players), source.WORLDS_PER_BLOCK]
    ):
        raise LR8LabelFitError("frozen block draw identity differs")
    _strict_sha256(draws["sha256"], label="block draw hash")
    _strict_sha256(value["world_order_sha256"], label="block world-order hash")
    _receipts(value["source_receipts"], label="block source receipts")
    attempts = _attempts(
        value["ordered_solve_attempts"],
        block=expected_block,
        projection_seed=projection_seed,
    )
    if (
        _exact_int(value["solve_attempt_count"], label="solve attempt count")
        != len(attempts)
        or canonical_sha256(list(attempts))
        != _strict_sha256(
            value["ordered_solve_attempts_sha256"],
            label="ordered solve attempts hash",
        )
    ):
        raise LR8LabelFitError("ordered solve attempt freeze differs")
    raw_candidates = value["unique_candidates"]
    if not isinstance(raw_candidates, list):
        raise LR8LabelFitError("block unique candidates must be a JSON list")
    candidates = tuple(
        _candidate(
            item,
            season=season,
            week=week,
            players=players,
            expected_block=expected_block,
        )
        for item in raw_candidates
    )
    if (
        len(candidates) != source.UNIQUE_OPTIMA_PER_BLOCK
        or _exact_int(value["unique_candidate_count"], label="unique candidate count")
        != len(candidates)
        or len({candidate.roster for candidate, _ in candidates}) != len(candidates)
    ):
        raise LR8LabelFitError("block unique-candidate dose differs")
    admitted = [row for row in attempts if row["admitted_unique"] is True]
    if [row["roster"] for row in admitted] != [
        list(candidate.roster) for candidate, _ in candidates
    ]:
        raise LR8LabelFitError("solve-attempt admission order differs from candidates")
    identity_payload = [list(candidate.roster) for candidate, _ in candidates]
    anatomy_payload = [{
        "roster": list(candidate.roster),
        "features": raw["anatomy_features"],
    } for candidate, raw in candidates]
    legality_payload = [{
        "roster": list(candidate.roster),
        "hard_domain_id": source.HARD_DOMAIN_ID,
        "dk_classic_legal": True,
        "former_house_rules_applied": [],
    } for candidate, _ in candidates]
    if (
        canonical_sha256(identity_payload) != _strict_sha256(
            value["candidate_identities_sha256"],
            label="block candidate identity hash",
        )
        or canonical_sha256(anatomy_payload) != _strict_sha256(
            value["anatomy_sha256"], label="block anatomy hash"
        )
        or canonical_sha256(legality_payload) != _strict_sha256(
            value["legality_sha256"], label="block legality hash"
        )
    ):
        raise LR8LabelFitError("block candidate/anatomy/legality hash differs")
    return candidates


def _validate_replay_refits(value: object) -> None:
    if not isinstance(value, list) or len(value) != 4:
        raise LR8LabelFitError("source replay-refit lattice differs")
    expected = tuple(
        (season, block)
        for season in source.TARGET_SEASONS
        for block in source.BLOCK_ORDER
    )
    for item, (season, block) in zip(value, expected, strict=True):
        if not isinstance(item, Mapping) or set(item) != _REPLAY_REFIT_FIELDS:
            raise LR8LabelFitError("source replay-refit fields differ")
        projection_seed, role_seed = source.BLOCK_SEED_PAIRS[block]
        if (
            item["target_season"] != season
            or item["block"] != block
            or item["projection_seed"] != projection_seed
            or item["source_environment_role_seed_nonoperative"] != role_seed
            or item["replay_path_id"] != source.PIT_REPLAY_PATH_ID
            or item["model_training_seasons"]
            != list(source.MODEL_TRAINING_SEASONS[season])
            or item["candidate_world_family"] != source.CANDIDATE_WORLD_FAMILY
            or item["role_seed_usage"] != source.ROLE_SEED_USAGE
        ):
            raise LR8LabelFitError("source replay-refit law differs")
        _strict_sha256(item["model_fit_input_sha256"], label="fit input hash")
        _strict_sha256(item["model_fit_sha256"], label="fit object hash")
        _receipts(item["fit_source_receipts"], label="fit source receipts")
        for field in (
            "target_player_labels_read",
            "candidate_labels_read",
            "role_belief_worlds_used",
            "b1_inputs_used",
            "a2a_inputs_used",
            "later_period_inputs_used",
        ):
            _literal_bool(item[field], label=f"replay {field}", expected=False)


def _merge_block_candidates(
    blocks: Sequence[tuple[tuple[FrozenFitCandidate, dict[str, object]], ...]],
) -> list[dict[str, object]]:
    order: list[tuple[str, ...]] = []
    first: dict[tuple[str, ...], tuple[FrozenFitCandidate, dict[str, object]]] = {}
    occurrences: dict[tuple[str, ...], list[list[object]]] = {}
    for block in blocks:
        for candidate, raw in block:
            if candidate.roster not in first:
                first[candidate.roster] = (candidate, raw)
                order.append(candidate.roster)
            occurrences.setdefault(candidate.roster, []).extend(
                [list(item) for item in raw["source_occurrences"]]
            )
    result: list[dict[str, object]] = []
    for roster in order:
        candidate, raw = first[roster]
        result.append(_candidate_payload(candidate, {
            **raw,
            "source_occurrences": occurrences[roster],
        }))
    return result


def _validate_source(
    training_source_freeze: Mapping[str, object],
    *,
    expected_manifest_sha256: str,
    training_source_receipt: Mapping[str, object],
) -> _ValidatedSource:
    expected_digest = _strict_sha256(
        expected_manifest_sha256, label="externally pinned source manifest hash"
    )
    try:
        frozen = source.validate_frozen_training_source(
            training_source_freeze,
            expected_manifest_sha256=expected_digest,
        )
    except source.LR8TrainingSourceError as exc:
        raise LR8LabelFitError(str(exc)) from exc
    if set(frozen) != _SOURCE_FIELDS:
        raise LR8LabelFitError("training-source freeze schema differs")
    source_receipt = _bound_object_receipt(
        training_source_receipt,
        frozen,
        label="training-source freeze receipt",
    )
    if (
        frozen["excluded_candidate_source_seasons"] != [2020, 2022]
        or frozen["blocks"] != [{
            "block": block,
            "projection_seed": source.BLOCK_SEED_PAIRS[block][0],
            "source_environment_role_seed_nonoperative": (
                source.BLOCK_SEED_PAIRS[block][1]
            ),
            "worlds": source.WORLDS_PER_BLOCK,
            "unique_optima": source.UNIQUE_OPTIMA_PER_BLOCK,
            "max_solve_attempts": source.MAX_SOLVE_ATTEMPTS_PER_BLOCK,
        } for block in source.BLOCK_ORDER]
        or frozen["former_house_rules_not_applied"]
        != list(source.FORMER_HOUSE_RULES_NOT_APPLIED)
    ):
        raise LR8LabelFitError("training-source frozen construction law differs")
    _validate_replay_refits(frozen["replay_refits"])

    raw_slates = frozen["slates"]
    if not isinstance(raw_slates, list) or len(raw_slates) != source.EXPECTED_SLATES:
        raise LR8LabelFitError("training-source slate body differs")
    catalogs: dict[tuple[int, int], tuple[rw.PlayerSpec, ...]] = {}
    candidates: list[FrozenFitCandidate] = []
    candidate_payloads: list[dict[str, object]] = []
    universe: list[dict[str, object]] = []
    for raw_slate, (season, week) in zip(
        raw_slates, source.EXPECTED_SLATE_KEYS, strict=True
    ):
        if not isinstance(raw_slate, Mapping) or set(raw_slate) != _SLATE_FIELDS:
            raise LR8LabelFitError("training-source slate schema differs")
        if raw_slate["season"] != season or raw_slate["week"] != week:
            raise LR8LabelFitError("training-source slate order differs")
        players = _catalog(raw_slate["catalog"], season=season, week=week)
        if source.catalog_sha256(players) != _strict_sha256(
            raw_slate["catalog_sha256"], label="slate catalog hash"
        ):
            raise LR8LabelFitError("training-source catalog hash differs")
        _receipts(raw_slate["catalog_source_receipts"], label="catalog receipts")
        incumbent_count = _exact_int(
            raw_slate["incumbent_candidate_count"],
            label="incumbent candidate count",
            minimum=source.UNIQUE_OPTIMA_PER_BLOCK,
        )
        if incumbent_count < source.UNIQUE_OPTIMA_PER_BLOCK:
            raise LR8LabelFitError("incumbent candidate source is empty")
        _strict_sha256(
            raw_slate["incumbent_candidates_sha256"],
            label="incumbent candidates hash",
        )
        _receipts(
            raw_slate["incumbent_source_receipts"], label="incumbent receipts"
        )
        raw_blocks = raw_slate["blocks"]
        if not isinstance(raw_blocks, list) or len(raw_blocks) != len(source.BLOCK_ORDER):
            raise LR8LabelFitError("slate block lattice differs")
        blocks = tuple(
            _block_candidates(
                raw_block,
                season=season,
                week=week,
                players=players,
                expected_block=block,
            )
            for raw_block, block in zip(raw_blocks, source.BLOCK_ORDER, strict=True)
        )
        pre_payload = [raw for block in blocks for _, raw in block]
        post_expected = _merge_block_candidates(blocks)
        raw_post = raw_slate["post_cross_block_candidates"]
        if not isinstance(raw_post, list):
            raise LR8LabelFitError("post-cross-block candidates must be a JSON list")
        post_validated = tuple(
            _candidate(
                item,
                season=season,
                week=week,
                players=players,
                expected_block=None,
            )
            for item in raw_post
        )
        normalized_post = [raw for _, raw in post_validated]
        if normalized_post != post_expected:
            raise LR8LabelFitError("post-cross-block candidate merge differs")
        if (
            raw_slate["pre_cross_block_candidate_count"]
            != source.PRE_CROSS_BLOCK_CANDIDATES
            or canonical_sha256(pre_payload) != raw_slate["pre_cross_block_sha256"]
            or raw_slate["post_cross_block_candidate_count"] != len(post_expected)
            or not source.UNIQUE_OPTIMA_PER_BLOCK
            <= len(post_expected)
            <= source.PRE_CROSS_BLOCK_CANDIDATES
            or canonical_sha256(post_expected)
            != raw_slate["post_cross_block_sha256"]
            or raw_slate["cross_block_duplicates"]
            != source.PRE_CROSS_BLOCK_CANDIDATES - len(post_expected)
        ):
            raise LR8LabelFitError("pre/post cross-block source freeze differs")
        slate_candidates = [candidate for candidate, _ in post_validated]
        if len({candidate.roster for candidate in slate_candidates}) != len(
            slate_candidates
        ):
            raise LR8LabelFitError("post-cross-block candidates repeat")
        catalogs[(season, week)] = players
        candidates.extend(slate_candidates)
        candidate_payloads.extend(normalized_post)
        universe.extend({
            "season": season,
            "week": week,
            "player_id": player.player_id,
            "position": player.position,
        } for player in players)

    if (
        frozen["post_dedup_candidate_rows"] != len(candidates)
        or frozen["post_dedup_candidate_rows_sha256"]
        != canonical_sha256(candidate_payloads)
    ):
        raise LR8LabelFitError("global post-dedup candidate freeze differs")
    fit_surface = tuple(sorted(
        candidates, key=lambda row: (row.season, row.week, row.roster)
    ))
    surface_payload = [_fit_candidate_payload(row) for row in fit_surface]
    return _ValidatedSource(
        manifest_sha256=expected_digest,
        object_receipt=source_receipt,
        candidates=fit_surface,
        catalogs=catalogs,
        catalog_universe_sha256=canonical_sha256(universe),
        candidate_surface_sha256=canonical_sha256(surface_payload),
    )


def frozen_fit_candidates(
    training_source_freeze: Mapping[str, object],
    *,
    expected_manifest_sha256: str,
    training_source_receipt: Mapping[str, object],
) -> tuple[FrozenFitCandidate, ...]:
    """Return only the externally frozen post-cross-block fit surface."""
    return _validate_source(
        training_source_freeze,
        expected_manifest_sha256=expected_manifest_sha256,
        training_source_receipt=training_source_receipt,
    ).candidates


def _historical_outcome_lease(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _LEASE_BINDING_FIELDS:
        raise LR8LabelFitError("historical-outcome lease binding differs")
    raw_body = value["body"]
    if not isinstance(raw_body, Mapping) or set(raw_body) != _LEASE_BODY_FIELDS:
        raise LR8LabelFitError("historical-outcome lease body differs")
    body = dict(raw_body)
    if (
        body["version"] != HISTORICAL_OUTCOME_LEASE_VERSION
        or not isinstance(body["run_id"], str)
        or _RUN_ID.fullmatch(body["run_id"]) is None
        or not isinstance(body["job"], str)
        or _JOB.fullmatch(body["job"]) is None
        or not isinstance(body["code_sha"], str)
        or _CODE_SHA.fullmatch(body["code_sha"]) is None
        or not isinstance(body["image"], str)
        or _IMAGE.fullmatch(body["image"]) is None
    ):
        raise LR8LabelFitError("historical-outcome lease identity differs")
    _utc_timestamp(body["acquired_at"], label="lease acquired_at")
    receipt = _bound_create_once_receipt(
        value["object_receipt"],
        body,
        label="historical-outcome lease receipt",
        expected_uri=HISTORICAL_OUTCOME_LEASE_URI,
    )
    return {"body": body, "object_receipt": receipt}


def _label_read_attempt(
    value: object,
    *,
    attempt_receipt: object,
    training_source_manifest_sha256: str,
    training_source_object: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    if not isinstance(value, Mapping) or set(value) != _LABEL_READ_ATTEMPT_FIELDS:
        raise LR8LabelFitError("label-read attempt body differs")
    attempt = dict(value)
    expected_query = authoritative_query_identity()
    if (
        attempt["schema"] != LABEL_READ_ATTEMPT_VERSION
        or attempt["protocol_id"] != lr8.PROTOCOL_ID
        or attempt["supplier_boundary"] != SCORE_SUPPLIER_BOUNDARY
        or attempt["stage"] != "before-authoritative-score-query"
        or attempt["training_source_manifest_sha256"]
        != training_source_manifest_sha256
        or attempt["training_source_object"] != training_source_object
        or not _same_canonical_value(
            attempt["target_seasons"], list(source.TARGET_SEASONS)
        )
        or not _same_canonical_value(
            attempt["slate_keys"],
            [list(key) for key in source.EXPECTED_SLATE_KEYS],
        )
        or not _same_canonical_value(attempt["query_identity"], expected_query)
        or attempt["query_sha256"] != AUTHORITATIVE_QUERY_SHA256
    ):
        raise LR8LabelFitError("label-read attempt/query boundary differs")
    for field in (
        "uses_realized_outcomes_at_creation",
        "retry_licensed",
        "b1_inputs_used",
        "a2a_inputs_used",
        "winner_inputs_used",
        "later_period_inputs_used",
        "production_inputs_used",
    ):
        _literal_bool(attempt[field], label=f"attempt {field}", expected=False)
    lease = _historical_outcome_lease(attempt["historical_outcome_lease"])
    attempt["historical_outcome_lease"] = lease
    attempt_timestamp = _utc_timestamp(
        attempt["started_at"], label="label-read attempt started_at"
    )
    lease_timestamp = _utc_timestamp(
        lease["body"]["acquired_at"], label="lease acquired_at"
    )
    attempt_time = datetime.fromisoformat(attempt_timestamp.replace("Z", "+00:00"))
    lease_time = datetime.fromisoformat(lease_timestamp.replace("Z", "+00:00"))
    if attempt_time < lease_time:
        raise LR8LabelFitError("label-read attempt predates its outcome lease")
    receipt = _bound_create_once_receipt(
        attempt_receipt,
        attempt,
        label="label-read attempt receipt",
        expected_uri=_score_object_uri(attempt, "label-read-attempt.json"),
    )
    if receipt["uri"] == HISTORICAL_OUTCOME_LEASE_URI:
        raise LR8LabelFitError("label-read attempt URI aliases the outcome lease")
    return attempt, receipt


def _score_object_uri(attempt: Mapping[str, object], name: str) -> str:
    run_id = attempt["historical_outcome_lease"]["body"]["run_id"]
    return f"{SCORE_OUTPUT_ROOT}/{run_id}/{name}"


def _catalog_score_keys(
    catalogs: Mapping[tuple[int, int], tuple[rw.PlayerSpec, ...]],
) -> list[dict[str, object]]:
    return [{
        "season": season,
        "week": week,
        "source_kind": "dst" if player.position == "DST" else "skill",
        "source_key": (
            player.team.upper() if player.position == "DST" else player.player_id
        ),
        "player_id": player.player_id,
        "position": player.position,
    } for season, week in source.EXPECTED_SLATE_KEYS
      for player in catalogs[(season, week)]]


def _score_source_extract(
    value: object,
    *,
    extract_receipt: object,
    source_receipts: object,
    training_source_manifest_sha256: str,
    training_source_object: Mapping[str, object],
    catalog_universe_sha256: str,
    attempt: Mapping[str, object],
    attempt_receipt: Mapping[str, object],
    expected_catalog_keys: Sequence[Mapping[str, object]] | None,
) -> tuple[dict[str, object], dict, dict[str, object], tuple[dict, ...]]:
    """Replay the exact source body retained inside the score map."""
    if not isinstance(value, Mapping) or set(value) != _SCORE_SOURCE_EXTRACT_FIELDS:
        raise LR8LabelFitError("authoritative score-source extract schema differs")
    extract = dict(value)
    if (
        extract["schema"] != SCORE_SOURCE_EXTRACT_VERSION
        or extract["supplier_version"] != SCORE_SUPPLIER_VERSION
        or extract["protocol_id"] != lr8.PROTOCOL_ID
        or extract["supplier_boundary"] != SCORE_SUPPLIER_BOUNDARY
        or extract["training_source_manifest_sha256"]
        != training_source_manifest_sha256
        or extract["training_source_object"] != training_source_object
        or extract["target_seasons"] != list(source.TARGET_SEASONS)
        or extract["slate_keys"] != [list(key) for key in source.EXPECTED_SLATE_KEYS]
        or extract["catalog_universe_sha256"] != catalog_universe_sha256
        or extract["query_identity"] != authoritative_query_identity()
        or extract["query_sha256"] != AUTHORITATIVE_QUERY_SHA256
        or extract["sql_sha256"] != AUTHORITATIVE_SQL_SHA256
        or extract["row_fields"] != list(SCORE_SOURCE_ROW_FIELDS)
        or extract["label_read_attempt"] != attempt
        or extract["label_read_attempt_receipt"] != attempt_receipt
        or extract["table_metadata_stable_during_query"] is not True
        or extract["historical_outcome_lease_unchanged_during_query"] is not True
    ):
        raise LR8LabelFitError("authoritative score-source boundary differs")
    for field in (
        "b1_inputs_used", "a2a_inputs_used", "winner_inputs_used",
        "later_period_inputs_used", "production_inputs_used",
    ):
        _literal_bool(extract[field], label=f"source extract {field}", expected=False)
    catalog_keys = extract["catalog_keys"]
    if not isinstance(catalog_keys, list) or not catalog_keys or any(
        not isinstance(row, Mapping) or set(row) != _SCORE_SOURCE_CATALOG_KEY_FIELDS
        for row in catalog_keys
    ):
        raise LR8LabelFitError("authoritative source catalog keys differ")
    if expected_catalog_keys is not None and catalog_keys != list(expected_catalog_keys):
        raise LR8LabelFitError("authoritative source catalog mapping differs")
    source_to_player: dict[tuple[int, int, str, str], tuple[str, str]] = {}
    player_order: list[tuple[int, int, str]] = []
    for row in catalog_keys:
        season = _exact_int(row["season"], label="source catalog season")
        week = _exact_int(row["week"], label="source catalog week", minimum=1)
        kind = _strict_string(row["source_kind"], label="source catalog kind")
        source_key = _strict_string(row["source_key"], label="source catalog key")
        player_id = _strict_string(row["player_id"], label="source catalog player")
        position = _strict_string(row["position"], label="source catalog position")
        expected_kind = "dst" if position == "DST" else "skill"
        source_id = (season, week, kind, source_key)
        player_id_key = (season, week, player_id)
        if (
            (season, week) not in source.EXPECTED_SLATE_KEYS
            or position not in {"QB", "RB", "WR", "TE", "DST"}
            or kind != expected_kind
            or (kind == "skill" and source_key != player_id)
            or (kind == "dst" and source_key != source_key.upper())
            or source_id in source_to_player
            or player_id_key in player_order
        ):
            raise LR8LabelFitError("authoritative source catalog mapping differs")
        source_to_player[source_id] = (player_id, position)
        player_order.append(player_id_key)
    universe = [{
        "season": row["season"], "week": row["week"],
        "player_id": row["player_id"], "position": row["position"],
    } for row in catalog_keys]
    if (
        player_order != sorted(player_order)
        or canonical_sha256(catalog_keys) != extract["catalog_keys_sha256"]
        or canonical_sha256(universe) != catalog_universe_sha256
    ):
        raise LR8LabelFitError("authoritative source catalog-key binding differs")

    parameters = extract["parameters"]
    job = extract["job_receipt"]
    tables = extract["table_receipts"]
    if (
        not isinstance(parameters, list)
        or extract["parameters_sha256"] != sha256(canonical_json(parameters) + b"\n").hexdigest()
        or not isinstance(job, Mapping)
        or job.get("sql_sha256") != AUTHORITATIVE_SQL_SHA256
        or job.get("parameters_sha256") != extract["parameters_sha256"]
        or job.get("error_result") is not None
        or not isinstance(tables, list)
        or [row.get("table_id") if isinstance(row, Mapping) else None for row in tables]
        != [
            "nfl-predictions-503414.nfl_features.player_week_actuals",
            "nfl-predictions-503414.nfl_features.team_defense_week",
        ]
    ):
        raise LR8LabelFitError("authoritative source query evidence differs")
    _utc_timestamp(extract["source_snapshot_at"], label="source snapshot")
    _utc_timestamp(extract["query_completed_at"], label="query completion")

    rows = extract["rows"]
    if not isinstance(rows, list) or any(
        not isinstance(row, Mapping) or set(row) != set(SCORE_SOURCE_ROW_FIELDS)
        for row in rows
    ):
        raise LR8LabelFitError("authoritative source rows differ")
    observed: dict[tuple[int, int, str, str], int] = {}
    order: list[tuple[int, int, str, str]] = []
    for row in rows:
        key = (
            _exact_int(row["season"], label="source score season"),
            _exact_int(row["week"], label="source score week", minimum=1),
            _strict_string(row["source_kind"], label="source score kind"),
            _strict_string(row["source_key"], label="source score key"),
        )
        score = _exact_int(
            row["realized_score_micro"], label="source score micro-DK", minimum=None
        )
        if key not in source_to_player or key in observed or abs(score) > (
            np.iinfo(np.int64).max // rw.ROSTER_SIZE
        ):
            raise LR8LabelFitError("authoritative source score coverage differs")
        observed[key] = score
        order.append(key)
    if (
        set(observed) != set(source_to_player)
        or order != sorted(order)
        or extract["rows_sha256"] != canonical_sha256(rows)
    ):
        raise LR8LabelFitError("authoritative source-row binding differs")
    player_scores = {
        (season, week, player_id): observed[(season, week, kind, source_key)]
        for (season, week, kind, source_key), (player_id, _) in source_to_player.items()
    }
    object_receipt = _bound_create_once_receipt(
        extract_receipt,
        extract,
        label="authoritative score-source object",
        expected_uri=_score_object_uri(attempt, "authoritative-score-source.json"),
    )
    receipts = _receipts(source_receipts, label="score source receipts")
    if list(receipts) != [{
        key: object_receipt[key] for key in ("uri", "generation", "sha256", "bytes")
    }]:
        raise LR8LabelFitError("score source receipt does not bind its extract")
    if training_source_object["uri"] in {
        HISTORICAL_OUTCOME_LEASE_URI, attempt_receipt["uri"], object_receipt["uri"],
        _score_object_uri(attempt, "authoritative-score-map.json"),
    }:
        raise LR8LabelFitError("authoritative score object URIs alias")
    return extract, player_scores, object_receipt, receipts


def _score_map(
    value: Mapping[str, object],
    *,
    score_map_receipt: Mapping[str, object],
    frozen_source: _ValidatedSource,
) -> tuple[dict[tuple[int, int, str], int], dict[str, object]]:
    if not isinstance(value, Mapping) or set(value) != _SCORE_MAP_FIELDS:
        raise LR8LabelFitError("authoritative score-map schema differs")
    score_map = dict(value)
    expected_query = authoritative_query_identity()
    if (
        score_map["schema"] != SCORE_MAP_VERSION
        or score_map["protocol_id"] != lr8.PROTOCOL_ID
        or score_map["supplier_boundary"] != SCORE_SUPPLIER_BOUNDARY
        or score_map["training_source_manifest_sha256"]
        != frozen_source.manifest_sha256
        or score_map["training_source_object"] != frozen_source.object_receipt
        or not _same_canonical_value(
            score_map["target_seasons"], list(source.TARGET_SEASONS)
        )
        or not _same_canonical_value(
            score_map["slate_keys"],
            [list(key) for key in source.EXPECTED_SLATE_KEYS],
        )
        or not _same_canonical_value(score_map["row_fields"], list(SCORE_ROW_FIELDS))
        or score_map["score_unit"] != SCORE_UNIT
        or score_map["catalog_universe_sha256"]
        != frozen_source.catalog_universe_sha256
        or score_map["authoritative_source_id"] != AUTHORITATIVE_SOURCE_ID
        or not _same_canonical_value(score_map["query_identity"], expected_query)
        or score_map["query_sha256"] != AUTHORITATIVE_QUERY_SHA256
    ):
        raise LR8LabelFitError("authoritative score-map boundary differs")
    attempt, attempt_receipt = _label_read_attempt(
        score_map["label_read_attempt"],
        attempt_receipt=score_map["label_read_attempt_receipt"],
        training_source_manifest_sha256=frozen_source.manifest_sha256,
        training_source_object=frozen_source.object_receipt,
    )
    expected_catalog_keys = _catalog_score_keys(frozen_source.catalogs)
    source_extract, source_scores, source_extract_receipt, source_receipts = (
        _score_source_extract(
        score_map["score_source_extract"],
        extract_receipt=score_map["score_source_extract_receipt"],
        source_receipts=score_map["score_source_receipts"],
        training_source_manifest_sha256=frozen_source.manifest_sha256,
        training_source_object=frozen_source.object_receipt,
        catalog_universe_sha256=frozen_source.catalog_universe_sha256,
        attempt=attempt,
        attempt_receipt=attempt_receipt,
        expected_catalog_keys=expected_catalog_keys,
        )
    )
    for field in (
        "b1_inputs_used",
        "a2a_inputs_used",
        "winner_inputs_used",
        "later_period_inputs_used",
        "production_inputs_used",
    ):
        _literal_bool(score_map[field], label=field, expected=False)

    raw_rows = score_map["rows"]
    if not isinstance(raw_rows, list):
        raise LR8LabelFitError("authoritative score rows must be a JSON list")
    expected: dict[tuple[int, int, str], rw.PlayerSpec] = {
        (season, week, player.player_id): player
        for (season, week), players in frozen_source.catalogs.items()
        for player in players
    }
    observed: dict[tuple[int, int, str], int] = {}
    normalized: list[dict[str, object]] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping) or set(raw) != set(SCORE_ROW_FIELDS):
            raise LR8LabelFitError(
                "score row fields differ; later-period/B1 fields are forbidden"
            )
        season = _exact_int(raw["season"], label="score season")
        week = _exact_int(raw["week"], label="score week", minimum=1)
        if season >= min(lr8.EVALUATION_SEASONS):
            raise LR8LabelFitError("2023+ score rows are forbidden during anatomy fit")
        player_id = _strict_string(raw["player_id"], label="score player id")
        key = (season, week, player_id)
        if key in observed:
            raise LR8LabelFitError("authoritative score rows repeat a player key")
        player = expected.get(key)
        if player is None:
            raise LR8LabelFitError("authoritative score map contains an extra player")
        position = _strict_string(raw["position"], label="score position")
        actual_source = _strict_string(
            raw["actual_source"], label="score actual source"
        )
        expected_actual_source = (
            DST_ACTUAL_SOURCE if player.position == "DST" else SKILL_ACTUAL_SOURCE
        )
        if position != player.position or actual_source != expected_actual_source:
            raise LR8LabelFitError("authoritative player/DST source mapping differs")
        score = _exact_int(
            raw["realized_score_micro"],
            label="realized score micro-DK",
            minimum=None,
        )
        if abs(score) > np.iinfo(np.int64).max // rw.ROSTER_SIZE:
            raise LR8LabelFitError("realized score is outside exact roster-sum range")
        if source_scores.get(key) != score:
            raise LR8LabelFitError(
                "authoritative score row differs from its source extract"
            )
        observed[key] = score
        normalized.append({
            "season": season,
            "week": week,
            "player_id": player_id,
            "position": position,
            "realized_score_micro": score,
            "actual_source": actual_source,
        })
    expected_order = sorted(expected)
    if set(observed) != set(expected):
        missing = len(set(expected) - set(observed))
        extra = len(set(observed) - set(expected))
        raise LR8LabelFitError(
            f"authoritative score map is not exact: missing={missing} extra={extra}"
        )
    if [(row["season"], row["week"], row["player_id"]) for row in normalized] != (
        expected_order
    ):
        raise LR8LabelFitError("authoritative score rows are not canonically ordered")
    if score_map["score_rows_sha256"] != canonical_sha256(normalized):
        raise LR8LabelFitError("authoritative score-row hash differs")
    object_receipt = _bound_create_once_receipt(
        score_map_receipt,
        score_map,
        label="authoritative score-map receipt",
        expected_uri=_score_object_uri(attempt, "authoritative-score-map.json"),
    )
    provenance = {
        "supplier_boundary": SCORE_SUPPLIER_BOUNDARY,
        "authoritative_source_id": AUTHORITATIVE_SOURCE_ID,
        "query_identity": expected_query,
        "query_sha256": score_map["query_sha256"],
        "score_map_object": object_receipt,
        "score_source_receipts": list(source_receipts),
        "score_source_extract": source_extract,
        "score_source_extract_object": source_extract_receipt,
        "label_read_attempt": attempt,
        "label_read_attempt_object": attempt_receipt,
        "score_unit": SCORE_UNIT,
        "score_row_count": len(normalized),
        "score_rows": normalized,
        "score_rows_sha256": score_map["score_rows_sha256"],
        "catalog_universe_sha256": frozen_source.catalog_universe_sha256,
        "exact_catalog_universe": True,
        "candidate_totals_independently_summed": True,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "winner_inputs_used": False,
        "later_period_inputs_used": False,
        "production_inputs_used": False,
    }
    return observed, provenance


def _label_rows(
    frozen_source: _ValidatedSource,
    scores: Mapping[tuple[int, int, str], int],
) -> tuple[list[dict[str, object]], tuple[lr8.AnatomyTrainingRow, ...]]:
    payload: list[dict[str, object]] = []
    fit_rows: list[lr8.AnatomyTrainingRow] = []
    for candidate in frozen_source.candidates:
        total = sum(
            scores[(candidate.season, candidate.week, player_id)]
            for player_id in candidate.roster
        )
        label = total >= lr8.ANATOMY_LABEL_MICRO
        payload.append({
            "season": candidate.season,
            "week": candidate.week,
            "roster": list(candidate.roster),
            "anatomy_features": _fit_candidate_payload(candidate)[
                "anatomy_features"
            ],
            "realized_total_micro": total,
            "label_200_plus": label,
        })
        fit_rows.append(lr8.AnatomyTrainingRow(
            season=candidate.season,
            week=candidate.week,
            features=candidate.anatomy_features,
            realized_total_micro=total,
        ))
    return payload, tuple(fit_rows)


def _weighting_payload(label_rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    counts: dict[tuple[int, int], int] = {key: 0 for key in source.EXPECTED_SLATE_KEYS}
    for row in label_rows:
        counts[(int(row["season"]), int(row["week"]))] += 1
    if not counts or any(count <= 0 for count in counts.values()):
        raise LR8LabelFitError("equal-slate fit has an empty source cell")
    total_rows = len(label_rows)
    cell_count = len(source.EXPECTED_SLATE_KEYS)
    cells = [{
        "season": season,
        "week": week,
        "candidate_rows": counts[(season, week)],
        "unnormalized_row_weight_numerator": 1,
        "unnormalized_row_weight_denominator": counts[(season, week)],
        "normalized_row_weight_numerator": total_rows,
        "normalized_row_weight_denominator": cell_count * counts[(season, week)],
        "cell_total_weight_numerator": total_rows,
        "cell_total_weight_denominator": cell_count,
    } for season, week in source.EXPECTED_SLATE_KEYS]
    return {
        "law": "equal_total_weight_per_season_week",
        "training_cells": cell_count,
        "training_rows": total_rows,
        "cells": cells,
        "cells_sha256": canonical_sha256(cells),
    }


def _fixed_fit_law_payload() -> dict[str, object]:
    return {
        "model_version": lr8.ANATOMY_MODEL_VERSION,
        "feature_columns": list(lr8.ANATOMY_FEATURES),
        "c": 1.0,
        "solver": "lbfgs",
        "class_weight": None,
        "max_iter": 2000,
        "feature_sweep": False,
        "hyperparameter_sweep": False,
        "target_sweep": False,
        "threshold_sweep": False,
    }


def _validate_training_summary(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _TRAINING_SUMMARY_FIELDS:
        raise LR8LabelFitError("label-fit training-source summary differs")
    summary = dict(value)
    manifest_sha = _strict_sha256(
        summary["manifest_sha256"], label="training-source manifest hash"
    )
    object_receipt = _receipt(
        summary["object_receipt"], label="training-source object receipt"
    )
    candidate_rows = _exact_int(
        summary["post_cross_block_candidate_rows"],
        label="post-cross-block candidate rows",
        minimum=source.EXPECTED_SLATES * source.UNIQUE_OPTIMA_PER_BLOCK,
    )
    if (
        summary["canonical_panel_id"] != source.CANONICAL_PANEL_ID
        or not _same_canonical_value(
            summary["target_seasons"], list(source.TARGET_SEASONS)
        )
        or not _same_canonical_value(
            summary["slate_keys"],
            [list(key) for key in source.EXPECTED_SLATE_KEYS],
        )
        or candidate_rows
        > source.EXPECTED_SLATES * source.PRE_CROSS_BLOCK_CANDIDATES
        or summary["candidate_surface"] != "identity_and_anatomy_only"
    ):
        raise LR8LabelFitError("label-fit training-source boundary differs")
    surface_sha = _strict_sha256(
        summary["post_cross_block_candidate_surface_sha256"],
        label="candidate-surface hash",
    )
    catalog_sha = _strict_sha256(
        summary["catalog_universe_sha256"], label="catalog-universe hash"
    )
    return {
        **summary,
        "manifest_sha256": manifest_sha,
        "object_receipt": object_receipt,
        "post_cross_block_candidate_rows": candidate_rows,
        "post_cross_block_candidate_surface_sha256": surface_sha,
        "catalog_universe_sha256": catalog_sha,
    }


def _validate_score_provenance(
    value: object,
    *,
    training_source: Mapping[str, object],
) -> tuple[dict[str, object], dict[tuple[int, int, str], int]]:
    if not isinstance(value, Mapping) or set(value) != _SCORE_PROVENANCE_FIELDS:
        raise LR8LabelFitError("label-fit score-provenance schema differs")
    provenance = dict(value)
    expected_query = authoritative_query_identity()
    if (
        provenance["supplier_boundary"] != SCORE_SUPPLIER_BOUNDARY
        or provenance["authoritative_source_id"] != AUTHORITATIVE_SOURCE_ID
        or not _same_canonical_value(provenance["query_identity"], expected_query)
        or provenance["query_sha256"] != AUTHORITATIVE_QUERY_SHA256
        or provenance["score_unit"] != SCORE_UNIT
        or provenance["catalog_universe_sha256"]
        != training_source["catalog_universe_sha256"]
    ):
        raise LR8LabelFitError("label-fit score-provenance boundary differs")
    for field in ("exact_catalog_universe", "candidate_totals_independently_summed"):
        _literal_bool(provenance[field], label=field, expected=True)
    for field in (
        "b1_inputs_used",
        "a2a_inputs_used",
        "winner_inputs_used",
        "later_period_inputs_used",
        "production_inputs_used",
    ):
        _literal_bool(provenance[field], label=field, expected=False)
    attempt, attempt_object = _label_read_attempt(
        provenance["label_read_attempt"],
        attempt_receipt=provenance["label_read_attempt_object"],
        training_source_manifest_sha256=str(training_source["manifest_sha256"]),
        training_source_object=training_source["object_receipt"],
    )
    source_extract, source_scores, source_extract_object, score_source_receipts = (
        _score_source_extract(
        provenance["score_source_extract"],
        extract_receipt=provenance["score_source_extract_object"],
        source_receipts=provenance["score_source_receipts"],
        training_source_manifest_sha256=str(training_source["manifest_sha256"]),
        training_source_object=training_source["object_receipt"],
        catalog_universe_sha256=str(training_source["catalog_universe_sha256"]),
        attempt=attempt,
        attempt_receipt=attempt_object,
        expected_catalog_keys=None,
        )
    )
    raw_score_rows = provenance["score_rows"]
    if not isinstance(raw_score_rows, list) or not raw_score_rows:
        raise LR8LabelFitError("retained authoritative score rows differ")
    scores: dict[tuple[int, int, str], int] = {}
    normalized_score_rows: list[dict[str, object]] = []
    for raw in raw_score_rows:
        if not isinstance(raw, Mapping) or set(raw) != set(SCORE_ROW_FIELDS):
            raise LR8LabelFitError("retained authoritative score-row schema differs")
        season = _exact_int(raw["season"], label="retained score season")
        week = _exact_int(raw["week"], label="retained score week", minimum=1)
        if (season, week) not in source.EXPECTED_SLATE_KEYS:
            raise LR8LabelFitError("retained score rows contain a non-2019/2021 slate")
        player_id = _strict_string(
            raw["player_id"], label="retained score player id"
        )
        position = _strict_string(raw["position"], label="retained score position")
        if position not in {"QB", "RB", "WR", "TE", "DST"}:
            raise LR8LabelFitError("retained score position differs")
        actual_source = _strict_string(
            raw["actual_source"], label="retained actual source"
        )
        expected_source = DST_ACTUAL_SOURCE if position == "DST" else SKILL_ACTUAL_SOURCE
        if actual_source != expected_source:
            raise LR8LabelFitError("retained player/DST score source differs")
        realized = _exact_int(
            raw["realized_score_micro"],
            label="retained realized score micro-DK",
            minimum=None,
        )
        if abs(realized) > np.iinfo(np.int64).max // rw.ROSTER_SIZE:
            raise LR8LabelFitError("retained realized score is outside roster-sum range")
        key = (season, week, player_id)
        if key in scores:
            raise LR8LabelFitError("retained authoritative score rows repeat")
        if source_scores.get(key) != realized:
            raise LR8LabelFitError("retained score differs from its source extract")
        scores[key] = realized
        normalized_score_rows.append({
            "season": season,
            "week": week,
            "player_id": player_id,
            "position": position,
            "realized_score_micro": realized,
            "actual_source": actual_source,
        })
    observed_order = [
        (row["season"], row["week"], row["player_id"])
        for row in normalized_score_rows
    ]
    if observed_order != sorted(scores):
        raise LR8LabelFitError("retained authoritative score rows are not canonical")
    score_row_count = _exact_int(
        provenance["score_row_count"],
        label="authoritative score row count",
        minimum=1,
    )
    score_rows_sha = _strict_sha256(
        provenance["score_rows_sha256"], label="authoritative score-row hash"
    )
    universe = [{
        "season": row["season"],
        "week": row["week"],
        "player_id": row["player_id"],
        "position": row["position"],
    } for row in normalized_score_rows]
    if (
        score_row_count != len(normalized_score_rows)
        or score_rows_sha != canonical_sha256(normalized_score_rows)
        or canonical_sha256(universe) != training_source["catalog_universe_sha256"]
    ):
        raise LR8LabelFitError("retained authoritative score-row binding differs")
    score_map_payload = {
        "schema": SCORE_MAP_VERSION,
        "protocol_id": lr8.PROTOCOL_ID,
        "supplier_boundary": SCORE_SUPPLIER_BOUNDARY,
        "training_source_manifest_sha256": training_source["manifest_sha256"],
        "training_source_object": training_source["object_receipt"],
        "target_seasons": list(source.TARGET_SEASONS),
        "slate_keys": [list(key) for key in source.EXPECTED_SLATE_KEYS],
        "row_fields": list(SCORE_ROW_FIELDS),
        "score_unit": SCORE_UNIT,
        "catalog_universe_sha256": training_source["catalog_universe_sha256"],
        "authoritative_source_id": AUTHORITATIVE_SOURCE_ID,
        "query_identity": expected_query,
        "query_sha256": AUTHORITATIVE_QUERY_SHA256,
        "score_source_receipts": list(score_source_receipts),
        "score_source_extract": source_extract,
        "score_source_extract_receipt": source_extract_object,
        "label_read_attempt": attempt,
        "label_read_attempt_receipt": attempt_object,
        "rows": normalized_score_rows,
        "score_rows_sha256": score_rows_sha,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "winner_inputs_used": False,
        "later_period_inputs_used": False,
        "production_inputs_used": False,
    }
    score_map_object = _bound_create_once_receipt(
        provenance["score_map_object"],
        score_map_payload,
        label="authoritative score-map object",
        expected_uri=_score_object_uri(attempt, "authoritative-score-map.json"),
    )
    normalized_provenance = {
        **provenance,
        "score_map_object": score_map_object,
        "score_source_receipts": list(score_source_receipts),
        "score_source_extract": source_extract,
        "score_source_extract_object": source_extract_object,
        "label_read_attempt": attempt,
        "label_read_attempt_object": attempt_object,
        "score_row_count": score_row_count,
        "score_rows": normalized_score_rows,
        "score_rows_sha256": score_rows_sha,
    }
    return normalized_provenance, scores


def _validate_label_rows(
    value: object,
    *,
    training_source: Mapping[str, object],
    scores: Mapping[tuple[int, int, str], int],
) -> tuple[dict[str, object], tuple[lr8.AnatomyTrainingRow, ...]]:
    if not isinstance(value, Mapping) or set(value) != _LABELS_FIELDS:
        raise LR8LabelFitError("label-fit labels schema differs")
    labels = dict(value)
    raw_rows = labels["rows"]
    if not isinstance(raw_rows, list) or not raw_rows:
        raise LR8LabelFitError("label-fit label rows differ")
    normalized: list[dict[str, object]] = []
    fit_rows: list[lr8.AnatomyTrainingRow] = []
    keys: list[tuple[int, int, tuple[str, ...]]] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping) or set(raw) != _LABEL_ROW_FIELDS:
            raise LR8LabelFitError("label-fit label-row schema differs")
        season = _exact_int(raw["season"], label="label season")
        week = _exact_int(raw["week"], label="label week", minimum=1)
        if (season, week) not in source.EXPECTED_SLATE_KEYS:
            raise LR8LabelFitError("label-fit contains a non-2019/2021 slate")
        raw_roster = raw["roster"]
        if not isinstance(raw_roster, list):
            raise LR8LabelFitError("label-fit roster must be a JSON list")
        try:
            roster = rw.canonical_identity(raw_roster)
        except rw.ResidualWorldError as exc:
            raise LR8LabelFitError("label-fit roster is malformed") from exc
        if raw_roster != list(roster):
            raise LR8LabelFitError("label-fit roster is not canonical")
        features = _anatomy(raw["anatomy_features"], label="label-fit anatomy")
        feature_payload = [
            int(item) if float(item).is_integer() else float(item)
            for item in features
        ]
        if raw["anatomy_features"] != feature_payload:
            raise LR8LabelFitError("label-fit anatomy is not canonical")
        total = _exact_int(
            raw["realized_total_micro"],
            label="label-fit realized total",
            minimum=0,
        )
        try:
            replayed_total = sum(
                scores[(season, week, player_id)] for player_id in roster
            )
        except KeyError as exc:
            raise LR8LabelFitError(
                "label-fit roster is absent from the authoritative score map"
            ) from exc
        if total != replayed_total:
            raise LR8LabelFitError(
                "label-fit realized total does not replay from player/DST scores"
            )
        label = raw["label_200_plus"]
        if not isinstance(label, bool) or label is not (
            total >= lr8.ANATOMY_LABEL_MICRO
        ):
            raise LR8LabelFitError("label-fit >=200 label differs from its total")
        normalized_row = {
            "season": season,
            "week": week,
            "roster": list(roster),
            "anatomy_features": feature_payload,
            "realized_total_micro": total,
            "label_200_plus": label,
        }
        if not _same_canonical_value(raw, normalized_row):
            raise LR8LabelFitError("label-fit label row is not canonical")
        normalized.append(normalized_row)
        keys.append((season, week, roster))
        fit_rows.append(lr8.AnatomyTrainingRow(
            season=season,
            week=week,
            features=features,
            realized_total_micro=total,
        ))
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        raise LR8LabelFitError("label-fit label rows are not unique canonical order")
    if {key[:2] for key in keys} != set(source.EXPECTED_SLATE_KEYS):
        raise LR8LabelFitError("label-fit does not cover the exact 35-slate lattice")
    candidate_surface = [{
        "season": row["season"],
        "week": row["week"],
        "roster": row["roster"],
        "anatomy_features": row["anatomy_features"],
    } for row in normalized]
    positive_rows = sum(bool(row["label_200_plus"]) for row in normalized)
    if (
        labels["target"] != "realized_total_dk_gte_200"
        or _exact_int(labels["threshold_micro"], label="label threshold")
        != lr8.ANATOMY_LABEL_MICRO
        or _exact_int(labels["row_count"], label="label row count", minimum=1)
        != len(normalized)
        or len(normalized) != training_source["post_cross_block_candidate_rows"]
        or _exact_int(labels["positive_rows"], label="positive label rows")
        != positive_rows
        or labels["rows_sha256"] != canonical_sha256(normalized)
        or labels["score_reconciliation"]
        != "independent_exact_nine_player_micro_dk_sum"
        or canonical_sha256(candidate_surface)
        != training_source["post_cross_block_candidate_surface_sha256"]
    ):
        raise LR8LabelFitError("label-fit label body/binding differs")
    return {**labels, "rows": normalized}, tuple(fit_rows)


def _validate_weighting(
    value: object,
    *,
    label_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != _WEIGHTING_FIELDS:
        raise LR8LabelFitError("label-fit weighting schema differs")
    cells = value["cells"]
    if not isinstance(cells, list) or any(
        not isinstance(cell, Mapping) or set(cell) != _WEIGHT_CELL_FIELDS
        for cell in cells
    ):
        raise LR8LabelFitError("label-fit weighting-cell schema differs")
    expected = _weighting_payload(label_rows)
    if dict(value) != expected:
        raise LR8LabelFitError("label-fit equal-slate weighting differs")
    return expected


def fit_and_freeze(
    *,
    training_source_freeze: Mapping[str, object],
    expected_source_manifest_sha256: str,
    training_source_receipt: Mapping[str, object],
    authoritative_score_map: Mapping[str, object],
    authoritative_score_map_receipt: Mapping[str, object],
) -> dict[str, object]:
    """Label the frozen 2019/2021 candidates and run the sole fixed fit.

    The returned object has no timestamp or mutable external state.  A caller
    may publish its :func:`canonical_json` bytes create-once and generation-pin
    the result; this function itself performs no write.
    """
    frozen_source = _validate_source(
        training_source_freeze,
        expected_manifest_sha256=expected_source_manifest_sha256,
        training_source_receipt=training_source_receipt,
    )
    scores, score_provenance = _score_map(
        authoritative_score_map,
        score_map_receipt=authoritative_score_map_receipt,
        frozen_source=frozen_source,
    )
    label_rows, fit_rows = _label_rows(frozen_source, scores)
    if len({
        (row["season"], row["week"], tuple(row["roster"])) for row in label_rows
    }) != len(label_rows):
        raise LR8LabelFitError("candidate labels repeat a slate/roster key")
    try:
        anatomy_artifact = lr8.fit_soft_anatomy_law(fit_rows)
        anatomy_artifact = lr8.validate_soft_anatomy_artifact(anatomy_artifact)
    except lr8.LR8Error as exc:
        raise LR8LabelFitError(str(exc)) from exc
    weighting = _weighting_payload(label_rows)
    if (
        anatomy_artifact["sample_weight"] != weighting["law"]
        or anatomy_artifact["training_rows"] != len(label_rows)
        or anatomy_artifact["training_cells"] != len(source.EXPECTED_SLATE_KEYS)
        or anatomy_artifact["training_positive_rows"]
        != sum(bool(row["label_200_plus"]) for row in label_rows)
    ):
        raise LR8LabelFitError("fixed fit does not bind the labeled source")
    licenses = {field: False for field in _LICENSE_FIELDS}
    freeze: dict[str, object] = {
        "schema": LABEL_FIT_VERSION,
        "protocol_id": lr8.PROTOCOL_ID,
        "training_source": {
            "manifest_sha256": frozen_source.manifest_sha256,
            "object_receipt": frozen_source.object_receipt,
            "canonical_panel_id": source.CANONICAL_PANEL_ID,
            "target_seasons": list(source.TARGET_SEASONS),
            "slate_keys": [list(key) for key in source.EXPECTED_SLATE_KEYS],
            "post_cross_block_candidate_rows": len(frozen_source.candidates),
            "post_cross_block_candidate_surface_sha256": (
                frozen_source.candidate_surface_sha256
            ),
            "catalog_universe_sha256": frozen_source.catalog_universe_sha256,
            "candidate_surface": "identity_and_anatomy_only",
        },
        "score_provenance": score_provenance,
        "labels": {
            "target": "realized_total_dk_gte_200",
            "threshold_micro": lr8.ANATOMY_LABEL_MICRO,
            "row_count": len(label_rows),
            "positive_rows": sum(
                bool(row["label_200_plus"]) for row in label_rows
            ),
            "rows": label_rows,
            "rows_sha256": canonical_sha256(label_rows),
            "score_reconciliation": "independent_exact_nine_player_micro_dk_sum",
        },
        "weighting": weighting,
        "fit_law": _fixed_fit_law_payload(),
        "anatomy_artifact": anatomy_artifact,
        "anatomy_artifact_sha256": anatomy_artifact["artifact_sha256"],
        "licenses": licenses,
    }
    freeze["freeze_sha256"] = canonical_sha256(freeze)
    return freeze


def validate_label_fit_freeze(
    value: Mapping[str, object],
    *,
    expected_freeze_sha256: str,
) -> dict[str, object]:
    """Validate a generation-pinned create-once label/fit artifact body."""
    expected = _strict_sha256(
        expected_freeze_sha256, label="externally pinned label-fit hash"
    )
    if not isinstance(value, Mapping) or set(value) != {
        "schema",
        "protocol_id",
        "training_source",
        "score_provenance",
        "labels",
        "weighting",
        "fit_law",
        "anatomy_artifact",
        "anatomy_artifact_sha256",
        "licenses",
        "freeze_sha256",
    }:
        raise LR8LabelFitError("label-fit freeze schema differs")
    frozen = dict(value)
    digest = frozen.pop("freeze_sha256")
    if digest != expected or digest != canonical_sha256(frozen):
        raise LR8LabelFitError("label-fit freeze hash differs")
    if frozen["schema"] != LABEL_FIT_VERSION or frozen["protocol_id"] != lr8.PROTOCOL_ID:
        raise LR8LabelFitError("label-fit freeze identity differs")
    training_source = _validate_training_summary(frozen["training_source"])
    licenses = frozen["licenses"]
    if not isinstance(licenses, Mapping) or set(licenses) != set(_LICENSE_FIELDS):
        raise LR8LabelFitError("label-fit license schema differs")
    for field in _LICENSE_FIELDS:
        _literal_bool(licenses[field], label=field, expected=False)
    provenance, scores = _validate_score_provenance(
        frozen["score_provenance"], training_source=training_source
    )
    labels, fit_rows = _validate_label_rows(
        frozen["labels"], training_source=training_source, scores=scores
    )
    weighting = _validate_weighting(
        frozen["weighting"], label_rows=labels["rows"]
    )
    fit_law = frozen["fit_law"]
    if (
        not isinstance(fit_law, Mapping)
        or set(fit_law) != _FIT_LAW_FIELDS
        or dict(fit_law) != _fixed_fit_law_payload()
    ):
        raise LR8LabelFitError("label-fit fixed/no-sweep fit law differs")
    try:
        artifact = lr8.validate_soft_anatomy_artifact(frozen["anatomy_artifact"])
        replayed_artifact = lr8.validate_soft_anatomy_artifact(
            lr8.fit_soft_anatomy_law(fit_rows)
        )
    except lr8.LR8Error as exc:
        raise LR8LabelFitError(str(exc)) from exc
    if (
        frozen["anatomy_artifact_sha256"] != artifact["artifact_sha256"]
        or canonical_json(artifact) != canonical_json(replayed_artifact)
        or artifact["training_rows"] != labels["row_count"]
        or artifact["training_cells"] != weighting["training_cells"]
        or artifact["training_positive_rows"] != labels["positive_rows"]
    ):
        raise LR8LabelFitError("label-fit anatomy artifact binding differs")
    frozen["training_source"] = training_source
    frozen["score_provenance"] = provenance
    frozen["labels"] = labels
    frozen["weighting"] = weighting
    frozen["fit_law"] = _fixed_fit_law_payload()
    frozen["anatomy_artifact"] = artifact
    frozen["freeze_sha256"] = digest
    return frozen


__all__ = [
    "AUTHORITATIVE_QUERY_ID",
    "AUTHORITATIVE_QUERY_SHA256",
    "AUTHORITATIVE_QUERY_VERSION",
    "AUTHORITATIVE_SOURCE_ID",
    "DST_ACTUAL_SOURCE",
    "FrozenFitCandidate",
    "HISTORICAL_OUTCOME_LEASE_URI",
    "HISTORICAL_OUTCOME_LEASE_VERSION",
    "LABEL_FIT_VERSION",
    "LABEL_READ_ATTEMPT_VERSION",
    "LR8LabelFitError",
    "SCORE_MAP_VERSION",
    "SCORE_ROW_FIELDS",
    "SCORE_SUPPLIER_BOUNDARY",
    "SCORE_UNIT",
    "SKILL_ACTUAL_SOURCE",
    "authoritative_query_identity",
    "canonical_json",
    "canonical_sha256",
    "fit_and_freeze",
    "frozen_fit_candidates",
    "validate_label_fit_freeze",
]
