"""Score-free Fantasy Points x SIS retrieval ablation for R6.

The ablation starts from one exact, validated seven-pack source, one exact
structural catalog, one exact accepted-candidate artifact, and one exact
simulated world matrix.  It then creates four derived source views by
physically removing Fantasy Points and/or SIS raw slices *before* invoking
the existing component reducer.  The immutable full seven-pack validator is
never weakened and no missing vendor is represented by a ranked zero.

Every cell recomputes components, percentiles, edge scores, admission and the
fixed coverage-194 K80 selector.  Candidate rows and the world matrix remain
byte-identical across cells, so candidate turnover is asserted to be zero by
construction.  Historical source periods have no authoritative observation
timestamps; staleness is therefore explicitly not measurable and this output
is retrospective mechanism evidence only.

This module is a pure scientific builder.  It owns no cloud or warehouse
client and reads no realized score or contest outcome.  The separate bounded
operator requires the complete immutable 54-slate inputs, persists the exact
matrix bytes and every physically stripped view create-once, exact-reopens
them, and publishes a distinct ablation terminal root last.  A stripped view
never claims the canonical full-seven-pack source-v3 release type.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
import math
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import corpus_r6_matchup_component_producer_v1 as producer
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1
from nfl_dfs.research import paid_source_ablation_registry_v1 as registry


WORLD_BINDING_SCHEMA: Final = "r6-paid-source-world-matrix-binding/v1"
DISCOVERY_WORLD_BINDING_SCHEMA: Final = (
    "r6-paid-source-discovery-world-matrix-binding/v2"
)
DISCOVERY_WORLD_BYTES_SCHEMA: Final = (
    "r6-paid-source-discovery-world-matrix-bytes/v2"
)
DISCOVERY_BLOCK_ORDER: Final = ("R0", "R1", "R2", "R3")
DISCOVERY_WORLDS_PER_BLOCK: Final = 10_000
DISCOVERY_WORLD_COUNT: Final = 40_000
DISCOVERY_SCORING_LAW_ID: Final = "candidate-roster-r0-r3-float64-sum/v1"
SLATE_CENSUS_SCHEMA: Final = "r6-fp-sis-retrieval-support-census/v1"
PANEL_CENSUS_SCHEMA: Final = "r6-fp-sis-retrieval-panel-census/v1"

CANONICAL_SOURCE_V3_CONTROL_REOPENER: Final = (
    "corpus_r6_matchup_source_release_outer_candidate_authority_v3."
    "reopen_matchup_source_release_outer_candidate_authority_ordinal_v3"
)
PRODUCTION_EXECUTION_STATUS: Final = (
    "guarded-runner-available-awaiting-exact-immutable-panel-inputs"
)
REMAINING_INTEGRATION_SEAM: Final = (
    "supply the exact immutable 54-slate candidate-v2, canonical full-seven-"
    "pack source-v3 control predecessor, and canonical world-matrix bodies to "
    "the bounded runner; it must publish physically stripped views under a "
    "distinct paid-source-ablation terminal that never claims canonical "
    "source-v3 authority"
)

FP_SLICE_KINDS: Final = (
    "fp-route-share",
    "fp-alignment",
    "fp-receiver-shell",
    "fp-defense-shell",
)
SIS_SLICE_KINDS: Final = (
    "sis-defender-alignment",
    "sis-run-context",
)
JOINT_FP_SIS_COMPONENTS: Final = (
    "alignment_vulnerability",
    "defender_workload_quality",
)
SOURCE_REQUIRED_COMPONENTS: Final = {
    "alignment_vulnerability": frozenset({"fantasy-points", "sis"}),
    "defender_workload_quality": frozenset({"fantasy-points", "sis"}),
    "shell_fit": frozenset({"fantasy-points"}),
    "run_context": frozenset({"sis"}),
}

_FORBIDDEN_OUTCOME_KEYS: Final = frozenset({
    "actual_points",
    "actual_score",
    "contest_finish",
    "contest_rank",
    "lineup_score",
    "payout",
    "realized_points",
    "realized_score",
    "winner",
    "winning_score",
})


class CorpusR6PaidSourceAblationV1Error(ValueError):
    """The score-free paid-source retrieval ablation is invalid."""


def _fail(message: str) -> None:
    raise CorpusR6PaidSourceAblationV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _number(value: object, *, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        _fail(f"{label} must be a finite number")
    return float(value)


def _reject_outcomes(value: object, *, label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string field")
            normalized = key.strip().lower()
            if normalized in _FORBIDDEN_OUTCOME_KEYS or (
                "realized" in normalized
                and normalized not in {"uses_realized_outcomes"}
            ) or "grade" in normalized:
                _fail(f"{label} contains forbidden outcome field {key!r}")
            if normalized == "uses_realized_outcomes" and item is not False:
                _fail(f"{label}.uses_realized_outcomes must be false")
            if normalized == "outcome_columns_read" and item != []:
                _fail(f"{label}.outcome_columns_read must be empty")
            _reject_outcomes(item, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, item in enumerate(value):
            _reject_outcomes(item, label=f"{label}[{ordinal}]")


def _policy() -> dict[str, object]:
    return {
        "evidence_class": "retrospective-prior-period-source-mechanism",
        "historical_source_observation_time_status": (
            "not-measurable-no-authoritative-observation-timestamps"
        ),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "value_claim": "not_evaluated",
        **{field: False for field in registry.FALSE_AUTHORITY_FIELDS},
    }


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in value:
        _fail(f"{field} must not be supplied before hashing")
    result = dict(value)
    result[field] = registry.canonical_sha256(result)
    return result


def _validate_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    retained = value.get(field)
    if not registry.is_sha256(retained):
        _fail(f"{label} self-hash is invalid")
    body = {key: item for key, item in value.items() if key != field}
    if registry.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")


def _bind_body(
    value: object, identity: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    normalized = source.normalize_object_identity_v2(identity, label=label)
    raw = registry.canonical_json_bytes(value)
    if (
        normalized["sha256"] != sha256(raw).hexdigest()
        or normalized["bytes"] != len(raw)
    ):
        _fail(f"{label} differs from its exact body")
    return normalized


def _score_matrix_sha256(values: np.ndarray) -> str:
    matrix = np.asarray(values)
    if matrix.ndim != 2 or matrix.size == 0:
        _fail("world score matrix must be a nonempty two-dimensional array")
    if not np.issubdtype(matrix.dtype, np.floating):
        _fail("world score matrix must use a floating dtype")
    if not np.isfinite(matrix).all():
        _fail("world score matrix contains a non-finite value")
    contiguous = np.ascontiguousarray(matrix)
    body_digest = sha256()
    body_digest.update(memoryview(contiguous).cast("B"))
    envelope = {
        "dtype": contiguous.dtype.str,
        "shape": list(contiguous.shape),
        "body_sha256": body_digest.hexdigest(),
    }
    return registry.canonical_sha256(envelope)


def canonical_world_matrix_bytes_v1(
    candidate_ids: Sequence[str], world_scores: np.ndarray,
) -> bytes:
    """Encode the sole byte representation admitted by the ablation.

    The identity is over both candidate order and the exact contiguous matrix
    body.  This closes the prior gap where an opaque object identity and an
    unrelated in-memory array could be asserted together without proof that
    they described the same object.
    """

    ids = [str(value) for value in candidate_ids]
    if not ids or len(ids) != len(set(ids)):
        _fail("world matrix candidate IDs must be nonempty and unique")
    values = np.asarray(world_scores)
    if values.ndim != 2 or values.shape[0] != len(ids):
        _fail("world matrix rows differ from candidate order")
    _score_matrix_sha256(values)
    contiguous = np.ascontiguousarray(values)
    header = {
        "schema_version": "r6-paid-source-world-matrix-bytes/v1",
        "candidate_ids": ids,
        "dtype": contiguous.dtype.str,
        "shape": [int(part) for part in contiguous.shape],
    }
    return registry.canonical_json_bytes(header) + b"\n" + contiguous.tobytes(
        order="C"
    )


def build_world_matrix_binding_v1(
    *,
    world_matrix_identity: Mapping[str, object],
    candidate_ids: Sequence[str],
    world_scores: np.ndarray,
) -> dict[str, object]:
    ids = [str(value) for value in candidate_ids]
    if not ids or len(ids) != len(set(ids)):
        _fail("world matrix candidate IDs must be nonempty and unique")
    values = np.asarray(world_scores)
    if values.ndim != 2 or values.shape[0] != len(ids):
        _fail("world matrix rows differ from candidate order")
    score_sha = _score_matrix_sha256(values)
    raw = canonical_world_matrix_bytes_v1(ids, values)
    identity = source.normalize_object_identity_v2(
        world_matrix_identity, label="paid-source world matrix"
    )
    if identity["sha256"] != sha256(raw).hexdigest() or identity["bytes"] != len(raw):
        _fail("paid-source world matrix identity differs from canonical bytes")
    body: dict[str, object] = {
        "schema_version": WORLD_BINDING_SCHEMA,
        "world_matrix_identity": identity,
        "candidate_count": len(ids),
        "world_count": int(values.shape[1]),
        "candidate_order_sha256": registry.canonical_sha256(ids),
        "score_matrix_sha256": score_sha,
        "matrix_dtype": values.dtype.str,
        "matrix_representation": "candidate-by-simulated-world-dk-points",
        "matrix_byte_representation": "r6-paid-source-world-matrix-bytes/v1",
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    return _with_hash(body, field="world_matrix_binding_sha256")


def validate_world_matrix_binding_v1(
    value: object,
    *,
    candidate_ids: Sequence[str],
    world_scores: np.ndarray,
) -> dict[str, object]:
    item = _mapping(value, label="world matrix binding")
    _reject_outcomes(item, label="world matrix binding")
    _validate_hash(
        item, field="world_matrix_binding_sha256", label="world matrix binding"
    )
    rebuilt = build_world_matrix_binding_v1(
        world_matrix_identity=_mapping(
            item.get("world_matrix_identity"), label="world matrix identity"
        ),
        candidate_ids=candidate_ids,
        world_scores=world_scores,
    )
    if item != rebuilt:
        _fail("world matrix binding canonical replay differs")
    return rebuilt


def build_discovery_world_matrix_binding_v2(
    *,
    world_matrix_identity: Mapping[str, object],
    candidate_ids: Sequence[str],
    world_scores: np.ndarray,
    matrix_header: Mapping[str, object],
    matrix_registry_entry: Mapping[str, object],
) -> dict[str, object]:
    """Bind the faithful coverage-194 R0--R3 matrix without copying its body."""

    ids = [str(value) for value in candidate_ids]
    if not ids or len(ids) != len(set(ids)):
        _fail("discovery world matrix candidate IDs must be nonempty and unique")
    values = np.asarray(world_scores)
    if (
        values.ndim != 2
        or values.shape != (len(ids), DISCOVERY_WORLD_COUNT)
        or values.dtype.str != "<f8"
        or not values.flags.c_contiguous
    ):
        _fail("discovery world matrix shape/dtype/order differs")
    score_sha = _score_matrix_sha256(values)
    identity = source.normalize_object_identity_v2(
        world_matrix_identity, label="paid-source discovery world matrix"
    )
    header = _mapping(matrix_header, label="discovery world matrix header")
    lineage = _mapping(
        matrix_registry_entry, label="discovery world matrix registry entry"
    )
    required_lineage = {
        "source_task_ordinal", "slate", "matrix_identity",
        "candidate_artifact_identity", "candidate_ids_sha256",
        "source_world_artifact_identities",
        "source_world_artifact_manifest_sha256", "block_order",
        "worlds_per_block", "world_count", "dtype", "scoring_law_id",
        "r4_heldout_identity", "r4_heldout_not_read",
        "matrix_lineage_sha256", "matrix_body_sha256",
    }
    source_identities = [
        source.normalize_object_identity_v2(value, label="discovery R0-R3 identity")
        for value in _sequence(
            lineage.get("source_world_artifact_identities"),
            label="discovery R0-R3 identities",
        )
    ]
    candidate_identity = source.normalize_object_identity_v2(
        lineage.get("candidate_artifact_identity"),
        label="discovery candidate artifact identity",
    )
    heldout_identity = source.normalize_object_identity_v2(
        lineage.get("r4_heldout_identity"),
        label="discovery R4 heldout identity",
    )
    expected_header = {
        "schema_version": DISCOVERY_WORLD_BYTES_SCHEMA,
        "candidate_ids": ids,
        "candidate_artifact_identity": candidate_identity,
        "candidate_ids_sha256": registry.canonical_sha256(ids),
        "dtype": "<f8",
        "shape": [len(ids), DISCOVERY_WORLD_COUNT],
        "block_order": list(DISCOVERY_BLOCK_ORDER),
        "worlds_per_block": DISCOVERY_WORLDS_PER_BLOCK,
        "source_world_artifact_identities": source_identities,
        "source_world_artifact_manifest_sha256": registry.canonical_sha256(
            source_identities
        ),
        "r4_heldout_not_read": True,
    }
    if (
        set(lineage) != required_lineage
        or lineage.get("matrix_identity") != identity
        or lineage.get("candidate_artifact_identity") != candidate_identity
        or lineage.get("candidate_ids_sha256") != registry.canonical_sha256(ids)
        or lineage.get("source_world_artifact_identities") != source_identities
        or lineage.get("source_world_artifact_manifest_sha256")
        != registry.canonical_sha256(source_identities)
        or lineage.get("block_order") != list(DISCOVERY_BLOCK_ORDER)
        or lineage.get("worlds_per_block") != DISCOVERY_WORLDS_PER_BLOCK
        or lineage.get("world_count") != DISCOVERY_WORLD_COUNT
        or lineage.get("dtype") != "<f8"
        or lineage.get("scoring_law_id") != DISCOVERY_SCORING_LAW_ID
        or lineage.get("r4_heldout_identity") != heldout_identity
        or lineage.get("r4_heldout_not_read") is not True
        or not registry.is_sha256(lineage.get("matrix_lineage_sha256"))
        or not registry.is_sha256(lineage.get("matrix_body_sha256"))
        or header != expected_header
    ):
        _fail("discovery world matrix lineage/header differs")
    header_raw = registry.canonical_json_bytes(header) + b"\n"
    digest = sha256(header_raw)
    body_view = memoryview(values).cast("B")
    digest.update(body_view)
    if (
        identity["sha256"] != digest.hexdigest()
        or identity["bytes"] != len(header_raw) + values.nbytes
        or lineage["matrix_body_sha256"] != sha256(body_view).hexdigest()
    ):
        _fail("discovery world matrix identity differs from exact bytes")
    body: dict[str, object] = {
        "schema_version": DISCOVERY_WORLD_BINDING_SCHEMA,
        "world_matrix_identity": identity,
        "candidate_count": len(ids),
        "world_count": DISCOVERY_WORLD_COUNT,
        "candidate_order_sha256": registry.canonical_sha256(ids),
        "score_matrix_sha256": score_sha,
        "matrix_dtype": "<f8",
        "matrix_representation": "candidate-by-simulated-world-dk-points",
        "matrix_byte_representation": DISCOVERY_WORLD_BYTES_SCHEMA,
        "matrix_registry_entry": lineage,
        "matrix_header": header,
        "selection_bank_law": {
            "block_order": list(DISCOVERY_BLOCK_ORDER),
            "worlds_per_block": DISCOVERY_WORLDS_PER_BLOCK,
            "world_count": DISCOVERY_WORLD_COUNT,
            "scoring_law_id": DISCOVERY_SCORING_LAW_ID,
            "r4_heldout_bound_but_not_read": True,
        },
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    return _with_hash(body, field="world_matrix_binding_sha256")


def validate_discovery_world_matrix_binding_v2(
    value: object,
    *,
    candidate_ids: Sequence[str],
    world_scores: np.ndarray,
) -> dict[str, object]:
    item = _mapping(value, label="discovery world matrix binding")
    _reject_outcomes(item, label="discovery world matrix binding")
    _validate_hash(
        item,
        field="world_matrix_binding_sha256",
        label="discovery world matrix binding",
    )
    rebuilt = build_discovery_world_matrix_binding_v2(
        world_matrix_identity=_mapping(
            item.get("world_matrix_identity"),
            label="discovery world matrix identity",
        ),
        candidate_ids=candidate_ids,
        world_scores=world_scores,
        matrix_header=_mapping(
            item.get("matrix_header"), label="discovery world matrix header"
        ),
        matrix_registry_entry=_mapping(
            item.get("matrix_registry_entry"),
            label="discovery world matrix registry entry",
        ),
    )
    if item != rebuilt:
        _fail("discovery world matrix binding canonical replay differs")
    return rebuilt


def _validated_source(
    *,
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    packs = [
        source.validate_upstream_pack_rows_v1(value)
        for value in upstream_pack_row_objects
    ]
    if tuple(str(pack["pack_id"]) for pack in packs) != source.PACK_IDS:
        _fail("paid-source ablation requires the exact full seven-pack order")
    release = source.validate_upstream_release_v1(
        upstream_source_release, pack_row_objects=packs
    )
    identity = _bind_body(
        release,
        upstream_source_release_identity,
        label="full seven-pack source release identity",
    )
    if identity["uri"] != f"{release['namespace']}upstream-release.json":
        _fail("seven-pack source release identity differs from its namespace")
    return release, identity, packs


def _catalog_join_authority(
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
) -> dict[str, object]:
    """Bind the exact offensive-player and structural-team join domains."""

    players = [
        _mapping(row, label="catalog join player") for row in catalog["players"]
    ]
    player_rows = [
        {
            "gsis_id": str(row["id"]),
            "team": str(row["team"]),
            "opponent": str(row["opp"]),
        }
        for row in players
    ]
    teams = sorted({
        value
        for row in player_rows
        for value in (str(row["team"]), str(row["opponent"]))
    })
    body: dict[str, object] = {
        "schema_version": "r6-paid-source-catalog-join-authority/v1",
        "structural_catalog_identity": dict(catalog_identity),
        "player_rows": player_rows,
        "player_ids_sha256": registry.canonical_sha256([
            row["gsis_id"] for row in player_rows
        ]),
        "teams": teams,
        "teams_sha256": registry.canonical_sha256(teams),
        "defender_identity_crosswalk_status": (
            "unavailable-use-defender-id-plus-structural-defense-team"
        ),
    }
    return _with_hash(body, field="catalog_join_authority_sha256")


def _slice_support(
    slices: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    slice_kinds: Sequence[str],
    vendor: str,
    catalog_player_ids: frozenset[str],
    catalog_teams: frozenset[str],
) -> dict[str, object]:
    row_counts: dict[str, int] = {}
    stable_counts: dict[str, int] = {}
    catalog_join_counts: dict[str, int | None] = {}
    for slice_kind in slice_kinds:
        rows = [dict(row) for row in slices[slice_kind]]
        row_counts[slice_kind] = len(rows)
        if vendor == "fantasy-points":
            if slice_kind in {"fp-route-share", "fp-alignment", "fp-receiver-shell"}:
                stable_counts[slice_kind] = sum(
                    type(row.get("gsis_id")) is str
                    and row.get("gsis_id") in catalog_player_ids
                    for row in rows
                )
                catalog_join_counts[slice_kind] = stable_counts[slice_kind]
            else:
                stable_counts[slice_kind] = sum(
                    type(row.get("team")) is str
                    and row.get("team") in catalog_teams
                    for row in rows
                )
                catalog_join_counts[slice_kind] = stable_counts[slice_kind]
        else:
            if slice_kind == "sis-defender-alignment":
                stable_counts[slice_kind] = sum(
                    type(row.get("defender_player_id")) is str
                    and bool(row.get("defender_player_id"))
                    and type(row.get("defense")) is str
                    and row.get("defense") in catalog_teams
                    for row in rows
                )
                catalog_join_counts[slice_kind] = stable_counts[slice_kind]
            else:
                stable_counts[slice_kind] = sum(
                    type(row.get("team")) is str
                    and row.get("team") in catalog_teams
                    for row in rows
                )
                catalog_join_counts[slice_kind] = stable_counts[slice_kind]
    total = sum(row_counts.values())
    stable = sum(stable_counts.values())
    return {
        "vendor": vendor,
        "slice_row_counts": row_counts,
        "slice_stable_identity_counts": stable_counts,
        "slice_candidate_catalog_join_counts": catalog_join_counts,
        "catalog_join_semantics": {
            slice_kind: (
                "exact-offensive-gsis-id-in-structural-catalog"
                if slice_kind in {
                    "fp-route-share", "fp-alignment", "fp-receiver-shell"
                }
                else "nonempty-defender-id-and-defense-in-structural-team-domain"
                if slice_kind == "sis-defender-alignment"
                else "team-in-structural-team-domain"
            )
            for slice_kind in slice_kinds
        },
        "slice_missing_observation_status": {
            slice_kind: (
                "observed" if row_counts[slice_kind] > 0 else "missing-no-row"
            )
            for slice_kind in slice_kinds
        },
        "raw_row_count": total,
        "stable_identity_row_count": stable,
        "identity_unresolved_row_count": total - stable,
        "missing_observation_status": (
            "observed-at-least-one-raw-row"
            if total > 0
            else "missing-all-vendor-slices"
        ),
        "observation_timestamp_available_row_count": 0,
        "stale_row_count": None,
        "staleness_status": (
            "not-measurable-retrospective-prior-period-reconstruction"
        ),
    }


def _source_view(
    full_slices: Mapping[str, Sequence[Mapping[str, object]]],
    *,
    fp_enabled: bool,
    sis_enabled: bool,
) -> tuple[dict[str, list[dict[str, object]]], dict[str, object]]:
    result = {
        slice_kind: [dict(row) for row in rows]
        for slice_kind, rows in full_slices.items()
    }
    removed: dict[str, int] = {}
    if not fp_enabled:
        for slice_kind in FP_SLICE_KINDS:
            removed[slice_kind] = len(result[slice_kind])
            result[slice_kind] = []
    if not sis_enabled:
        for slice_kind in SIS_SLICE_KINDS:
            removed[slice_kind] = len(result[slice_kind])
            result[slice_kind] = []
    # An enabled source may legitimately have no observation for this slate.
    # Only the off state asserts physical absence; treating an empty enabled
    # slice as an operator failure would erase the missing-source condition
    # this census is designed to measure.
    if not fp_enabled and any(result[kind] for kind in FP_SLICE_KINDS):
        _fail("Fantasy Points source view did not physically apply its state")
    if not sis_enabled and any(result[kind] for kind in SIS_SLICE_KINDS):
        _fail("SIS source view did not physically apply its state")
    view_body: dict[str, object] = {
        "schema_version": "r6-paid-source-derived-source-view/v1",
        "fantasy_points_enabled": fp_enabled,
        "sis_enabled": sis_enabled,
        "removed_slice_row_counts": removed,
        "removed_row_count": sum(removed.values()),
        "effective_slice_row_counts": {
            slice_kind: len(rows) for slice_kind, rows in result.items()
        },
        "effective_row_count": sum(len(rows) for rows in result.values()),
        "slices": result,
    }
    return result, {
        **view_body,
        "source_view_sha256": registry.canonical_sha256(view_body),
    }


def _component_support(
    annotations: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    supported = Counter()
    missing = Counter()
    reason_counts: Counter[str] = Counter()
    for row in annotations:
        for component, present in row["component_support"].items():
            (supported if present is True else missing)[str(component)] += 1
        for reason in row["component_missingness_reasons"].values():
            if reason is not None:
                reason_counts[str(reason)] += 1
    components = sorted(set(supported) | set(missing))
    available_types = [
        component for component in components if supported[component] > 0
    ]
    missing_types = [
        component for component in components if missing[component] > 0
    ]
    return {
        # The plan's "available component count" is a count of distinct
        # component types, not the number of player-component cells.  Retain
        # the latter under an explicit name so the two quantities cannot be
        # silently conflated in downstream analysis.
        "available_component_count": len(available_types),
        "missing_component_count": len(missing_types),
        "available_component_player_cell_count": sum(supported.values()),
        "missing_component_player_cell_count": sum(missing.values()),
        "available_component_types": available_types,
        "missing_component_types": missing_types,
        "supported_player_counts_by_component": {
            component: supported[component] for component in components
        },
        "missing_player_counts_by_component": {
            component: missing[component] for component in components
        },
        "missingness_reason_counts": dict(sorted(reason_counts.items())),
    }


def _lineup_support(
    *,
    catalog: Mapping[str, object],
    candidate_rows: Sequence[Mapping[str, object]],
    annotations: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    positions = {str(player["id"]): str(player["pos"]) for player in catalog["players"]}
    annotation_by_id = {str(row["gsis_id"]): dict(row) for row in annotations}
    rows: list[dict[str, object]] = []
    for raw in candidate_rows:
        candidate = _mapping(raw, label="paid-source candidate")
        candidate_id = str(candidate["candidate_id"])
        player_ids = [str(value) for value in candidate["player_ids"]]
        if any(player_id not in positions for player_id in player_ids):
            _fail("paid-source candidate contains a non-catalog player")
        skill_ids = [
            player_id for player_id in player_ids if positions[player_id] != "DST"
        ]
        if len(skill_ids) != 8 or sum(
            positions[player_id] == "QB" for player_id in skill_ids
        ) != 1:
            _fail("paid-source candidate must contain eight skill players and one QB")
        if any(player_id not in annotation_by_id for player_id in skill_ids):
            _fail("paid-source annotations do not cover the candidate skill universe")
        candidate_annotations = [annotation_by_id[player_id] for player_id in skill_ids]
        qb_annotation = next(
            row for row in candidate_annotations if row["family"] == "qb"
        )
        supported = [
            row for row in candidate_annotations if row["matchup_edge_score"] is not None
        ]
        completeness = len(supported) / len(skill_ids)
        edge = (
            float(np.mean([
                float(row["matchup_edge_score"]) for row in supported
            ], dtype=np.float64))
            if supported
            else None
        )
        qualifies = (
            qb_annotation["qb_depth1"] is True
            and len(supported) >= registry.MATCHUP_MINIMUM_SUPPORTED_PLAYERS
            and completeness >= registry.MATCHUP_MINIMUM_COMPLETENESS
        )
        rows.append({
            "candidate_id": candidate_id,
            "qb_depth1_eligible": qb_annotation["qb_depth1"] is True,
            "supported_matchup_player_count": len(supported),
            "annotation_completeness": completeness,
            "matchup_edge_mean": edge,
            "qualifies_for_matchup_admission": qualifies,
            "missing_semantics": "missing-not-zero",
        })
    return rows


def _coverage_selection(
    *,
    lineup_support: Sequence[Mapping[str, object]],
    candidate_ids: Sequence[str],
    world_scores: np.ndarray,
) -> dict[str, object]:
    qualifying = [
        dict(row) for row in lineup_support
        if row["qualifies_for_matchup_admission"] is True
    ]
    ranked = sorted(
        qualifying,
        key=lambda row: (-float(row["matchup_edge_mean"]), str(row["candidate_id"])),
    )
    admission_ranked_ids = [
        str(row["candidate_id"])
        for row in ranked[: min(registry.MATCHUP_ADMISSION_CAP, len(ranked))]
    ]
    admitted_ids = sorted(admission_ranked_ids)
    feasible = len(admitted_ids) >= registry.ENTRY_BUDGET
    selected_ids: list[str] = []
    trace: list[dict[str, object]] = []
    if feasible:
        global_index = {lineup_id: index for index, lineup_id in enumerate(candidate_ids)}
        indices = [global_index[lineup_id] for lineup_id in admitted_ids]
        scores = np.asarray(world_scores)[np.asarray(indices, dtype=np.int64)]
        strategy = next(
            value for value in retrieval.frozen_retrieval_strategies(
                registry.ENTRY_BUDGET
            ) if value["strategy_id"] == "coverage-194-v1"
        )
        selected_local, base_trace = retrieval._run_strategy(
            strategy, discovery_scores=scores, lineup_ids=admitted_ids
        )
        selected_ids = [admitted_ids[index] for index in selected_local]
        trace = [{
            "selection_rank": rank,
            "candidate_id": selected_ids[rank],
            "marginal_new_world_count": int(row["marginal_utility"]),
            "individual_threshold_world_count": int(
                row["discovery_primary_event_count"]
            ),
        } for rank, row in enumerate(base_trace)]
        if len(selected_ids) != registry.ENTRY_BUDGET:
            _fail("coverage-194 did not return exact K80")
    return {
        "qualifying_candidate_count": len(qualifying),
        "admission_cap": registry.MATCHUP_ADMISSION_CAP,
        "admitted_candidate_count": len(admitted_ids),
        "admission_ranked_candidate_ids": admission_ranked_ids,
        "admission_ranked_candidate_ids_sha256": registry.canonical_sha256(
            admission_ranked_ids
        ),
        "admitted_candidate_ids": admitted_ids,
        "admitted_candidate_ids_sha256": registry.canonical_sha256(admitted_ids),
        "k80_feasible": feasible,
        "selection_status": "complete" if feasible else "support-gate-failed",
        "selected_k80_candidate_ids": selected_ids,
        "selected_k80_candidate_ids_sha256": registry.canonical_sha256(selected_ids),
        "selected_k80_order_is_selector_order": True,
        "selection_trace": trace,
        "selection_trace_sha256": registry.canonical_sha256(trace),
    }


def _rank_map(
    rows: Sequence[Mapping[str, object]], *, id_field: str, value_field: str,
) -> dict[str, int]:
    supported = [row for row in rows if row[value_field] is not None]
    ordered = sorted(
        supported,
        key=lambda row: (-float(row[value_field]), str(row[id_field])),
    )
    return {str(row[id_field]): rank for rank, row in enumerate(ordered)}


def _turnover(
    reference: Sequence[str], treatment: Sequence[str], *, label: str,
) -> dict[str, object]:
    left = [str(value) for value in reference]
    right = [str(value) for value in treatment]
    if len(left) != len(set(left)) or len(right) != len(set(right)):
        _fail(f"{label} repeats a candidate ID")
    left_set, right_set = set(left), set(right)
    shared = left_set & right_set
    union = left_set | right_set
    right_rank = {value: rank for rank, value in enumerate(right)}
    displacement = [
        abs(rank - right_rank[value])
        for rank, value in enumerate(left) if value in right_rank
    ]
    return {
        "reference_count": len(left),
        "cell_count": len(right),
        "shared_count": len(shared),
        "jaccard": len(shared) / len(union) if union else 1.0,
        "membership_turnover_count": len(left_set ^ right_set),
        "exact_membership_equal": left_set == right_set,
        "exact_order_equal": left == right,
        "shared_mean_absolute_rank_displacement": (
            sum(displacement) / len(displacement) if displacement else None
        ),
    }


def run_fp_sis_retrieval_support_census_v1(
    *,
    structural_catalog: Mapping[str, object],
    structural_catalog_identity: Mapping[str, object],
    accepted_candidate_artifact: Mapping[str, object],
    accepted_candidate_artifact_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    world_matrix_binding: Mapping[str, object],
    world_scores: np.ndarray,
) -> dict[str, object]:
    """Execute the full score-free four-cell source support census."""
    registry.validate_paid_source_ablation_registry_v1(
        registry.frozen_paid_source_ablation_registry_v1()
    )
    catalog = source.validate_structural_catalog_v2(structural_catalog)
    catalog_identity = _bind_body(
        catalog, structural_catalog_identity, label="structural catalog identity"
    )
    catalog_join = _catalog_join_authority(catalog, catalog_identity)
    candidates = source.validate_accepted_candidate_artifact_v1(
        accepted_candidate_artifact
    )
    candidate_identity = _bind_body(
        candidates,
        accepted_candidate_artifact_identity,
        label="accepted candidate artifact identity",
    )
    if (
        candidates["source_task_ordinal"] != catalog["source_task_ordinal"]
        or candidates["slate"] != catalog["slate"]
    ):
        _fail("accepted candidates and structural catalog have different tasks")
    candidate_ids = [str(row["candidate_id"]) for row in candidates["rows"]]
    world_values = np.asarray(world_scores)
    raw_matrix_binding = _mapping(
        world_matrix_binding, label="world matrix binding"
    )
    matrix = (
        validate_discovery_world_matrix_binding_v2(
            raw_matrix_binding,
            candidate_ids=candidate_ids,
            world_scores=world_values,
        )
        if raw_matrix_binding.get("schema_version")
        == DISCOVERY_WORLD_BINDING_SCHEMA
        else validate_world_matrix_binding_v1(
            raw_matrix_binding,
            candidate_ids=candidate_ids,
            world_scores=world_values,
        )
    )
    release, release_identity, packs = _validated_source(
        upstream_source_release=upstream_source_release,
        upstream_source_release_identity=upstream_source_release_identity,
        upstream_pack_row_objects=upstream_pack_row_objects,
    )
    full_slices = producer._pack_slices(packs)
    catalog_player_ids = frozenset(
        str(player["id"]) for player in catalog["players"]
    )
    catalog_teams = frozenset(
        str(value)
        for player in catalog["players"]
        for value in (player["team"], player["opp"])
    )
    fp_support = _slice_support(
        full_slices,
        slice_kinds=FP_SLICE_KINDS,
        vendor="fantasy-points",
        catalog_player_ids=catalog_player_ids,
        catalog_teams=catalog_teams,
    )
    sis_support = _slice_support(
        full_slices,
        slice_kinds=SIS_SLICE_KINDS,
        vendor="sis",
        catalog_player_ids=catalog_player_ids,
        catalog_teams=catalog_teams,
    )

    cells: list[dict[str, object]] = []
    for cell_id in registry.MATCHUP_CELL_ORDER:
        cell = registry.matchup_cell_v1(cell_id)
        fp_enabled = cell["fantasy_points_enabled"] is True
        sis_enabled = cell["sis_enabled"] is True
        slices, removal = _source_view(
            full_slices, fp_enabled=fp_enabled, sis_enabled=sis_enabled
        )
        semantic = producer._derive_semantic_slate(catalog=catalog, slices=slices)
        annotations = [dict(row) for row in semantic["annotation_rows"]]
        disabled_sources = {
            source_name
            for source_name, enabled in (
                ("fantasy-points", fp_enabled), ("sis", sis_enabled)
            )
            if not enabled
        }
        for row in annotations:
            reasons = dict(row["component_missingness_reasons"])
            for component, dependencies in SOURCE_REQUIRED_COMPONENTS.items():
                if (
                    component in reasons
                    and row["raw_component_values"].get(component) is None
                    and dependencies & disabled_sources
                ):
                    reasons[component] = (
                        "source-disabled-by-ablation:"
                        + ",".join(sorted(dependencies & disabled_sources))
                    )
            row["component_missingness_reasons"] = reasons
        if not (fp_enabled and sis_enabled):
            for row in annotations:
                if row["family"] == "receiver" and any(
                    row["raw_component_values"][component] is not None
                    for component in JOINT_FP_SIS_COMPONENTS
                ):
                    _fail(
                        "joint Fantasy Points/SIS component survived a missing source"
                    )
        lineup_support = _lineup_support(
            catalog=catalog,
            candidate_rows=candidates["rows"],
            annotations=annotations,
        )
        selection = _coverage_selection(
            lineup_support=lineup_support,
            candidate_ids=candidate_ids,
            world_scores=world_values,
        )
        if _score_matrix_sha256(world_values) != matrix["score_matrix_sha256"]:
            _fail("FP/SIS retrieval mutated the immutable world matrix")
        cells.append({
            "cell": cell,
            "candidate_artifact_identity": candidate_identity,
            "candidate_count": len(candidate_ids),
            "candidate_order_sha256": registry.canonical_sha256(candidate_ids),
            "world_matrix_identity": matrix["world_matrix_identity"],
            "world_matrix_binding_sha256": matrix["world_matrix_binding_sha256"],
            "source_view": removal,
            "fantasy_points_support": {
                **fp_support,
                "enabled_in_cell": fp_enabled,
                "effective_raw_row_count": (
                    fp_support["raw_row_count"] if fp_enabled else 0
                ),
                "cell_missing_observation_status": (
                    fp_support["missing_observation_status"]
                    if fp_enabled
                    else "disabled-physical-removal-before-components"
                ),
            },
            "sis_support": {
                **sis_support,
                "enabled_in_cell": sis_enabled,
                "effective_raw_row_count": sis_support["raw_row_count"] if sis_enabled else 0,
                "cell_missing_observation_status": (
                    sis_support["missing_observation_status"]
                    if sis_enabled
                    else "disabled-physical-removal-before-components"
                ),
            },
            "component_support": _component_support(annotations),
            "annotation_rows": annotations,
            "annotation_rows_sha256": registry.canonical_sha256(annotations),
            "lineup_support_rows": lineup_support,
            "lineup_support_rows_sha256": registry.canonical_sha256(lineup_support),
            "retrieval": selection,
            "candidate_turnover_count": 0,
            "world_matrix_turnover_count": 0,
        })

    reference = cells[0]
    reference_annotations = {
        str(row["gsis_id"]): row for row in reference["annotation_rows"]
    }
    for cell in cells:
        annotations = {str(row["gsis_id"]): row for row in cell["annotation_rows"]}
        if set(annotations) != set(reference_annotations):
            _fail("FP/SIS cells do not preserve the annotation player universe")
        changed_raw = 0
        changed_percentile = 0
        for player_id, reference_row in reference_annotations.items():
            row = annotations[player_id]
            changed_raw += sum(
                reference_row["raw_component_values"][component]
                != row["raw_component_values"][component]
                for component in reference_row["raw_component_values"]
            )
            changed_percentile += sum(
                reference_row["component_values"][component]
                != row["component_values"][component]
                for component in reference_row["component_values"]
            )
        reference_ranks = _rank_map(
            list(reference_annotations.values()),
            id_field="gsis_id",
            value_field="matchup_edge_score",
        )
        cell_ranks = _rank_map(
            list(annotations.values()),
            id_field="gsis_id",
            value_field="matchup_edge_score",
        )
        common_rank_ids = set(reference_ranks) & set(cell_ranks)
        cell["marginal_turnover"] = {
            "raw_component_value_change_count": changed_raw,
            "component_percentile_change_count": changed_percentile,
            "player_edge_value_change_count": sum(
                reference_annotations[player_id]["matchup_edge_score"]
                != annotations[player_id]["matchup_edge_score"]
                for player_id in reference_annotations
            ),
            "shared_supported_player_count": len(common_rank_ids),
            "player_edge_rank_change_count": sum(
                reference_ranks[player_id] != cell_ranks[player_id]
                for player_id in common_rank_ids
            ),
        }
        cell["joint_component_loss_vs_on_on"] = {
            component: sum(
                reference_annotations[player_id]["component_support"].get(component)
                is True
                and annotations[player_id]["component_support"].get(component)
                is not True
                for player_id in reference_annotations
            )
            for component in JOINT_FP_SIS_COMPONENTS
        }
        cell["admission_order_turnover_vs_on_on"] = _turnover(
            reference["retrieval"]["admission_ranked_candidate_ids"],
            cell["retrieval"]["admission_ranked_candidate_ids"],
            label="matchup admission order",
        )
        cell["selected_k80_order_turnover_vs_on_on"] = (
            _turnover(
                reference["retrieval"]["selected_k80_candidate_ids"],
                cell["retrieval"]["selected_k80_candidate_ids"],
                label="matchup selected K80 order",
            )
            if reference["retrieval"]["k80_feasible"]
            and cell["retrieval"]["k80_feasible"]
            else {
                "status": "not_evaluated_support_gate_failed",
                "reference_k80_feasible": reference["retrieval"]["k80_feasible"],
                "cell_k80_feasible": cell["retrieval"]["k80_feasible"],
            }
        )

    all_feasible = all(cell["retrieval"]["k80_feasible"] for cell in cells)
    body: dict[str, object] = {
        "schema_version": SLATE_CENSUS_SCHEMA,
        "experiment_id": registry.MATCHUP_EXPERIMENT_ID,
        "source_task_ordinal": catalog["source_task_ordinal"],
        "task_id": catalog["task_id"],
        "slate": catalog["slate"],
        "registry_sha256": registry.frozen_paid_source_ablation_registry_v1()[
            "registry_sha256"
        ],
        "structural_catalog_identity": catalog_identity,
        "structural_catalog_body": catalog,
        "catalog_join_authority": catalog_join,
        "accepted_candidate_artifact_identity": candidate_identity,
        "accepted_candidate_artifact_body": candidates,
        "upstream_source_release_identity": release_identity,
        "upstream_source_release_body": release,
        "upstream_pack_row_objects": packs,
        "upstream_source_release_sha256": release["upstream_release_sha256"],
        "world_matrix_binding": matrix,
        "raw_source_support": {
            "fantasy_points": fp_support,
            "sis": sis_support,
        },
        "cells": cells,
        "cell_manifest_sha256": registry.canonical_sha256(cells),
        "candidate_authority_byte_identical_all_cells": True,
        "candidate_turnover_count_all_cells": 0,
        "world_matrix_authority_byte_identical_all_cells": True,
        "world_matrix_turnover_count_all_cells": 0,
        "all_cells_k80_feasible": all_feasible,
        "support_gate_status": "passed" if all_feasible else "failed",
        "production_execution_status": (
            PRODUCTION_EXECUTION_STATUS
        ),
        "canonical_source_v3_control_reopener": (
            CANONICAL_SOURCE_V3_CONTROL_REOPENER
        ),
        "remaining_integration_seam": REMAINING_INTEGRATION_SEAM,
        "conditional_fantasy_points_effect": (
            "not_evaluated_without_independent_grade"
        ),
        "conditional_sis_effect": "not_evaluated_without_independent_grade",
        "fp_by_sis_interaction": "not_evaluated_without_independent_grade",
        "additive_vendor_effect_claim_forbidden": True,
        **_policy(),
    }
    return _with_hash(body, field="slate_support_census_sha256")


def validate_fp_sis_retrieval_support_census_v1(
    value: object,
) -> dict[str, object]:
    item = _mapping(value, label="FP/SIS support census")
    _reject_outcomes(item, label="FP/SIS support census")
    _validate_hash(
        item,
        field="slate_support_census_sha256",
        label="FP/SIS support census",
    )
    expected_fields = set(_policy()) | {
        "schema_version",
        "experiment_id",
        "source_task_ordinal",
        "task_id",
        "slate",
        "registry_sha256",
        "structural_catalog_identity",
        "structural_catalog_body",
        "catalog_join_authority",
        "accepted_candidate_artifact_identity",
        "accepted_candidate_artifact_body",
        "upstream_source_release_identity",
        "upstream_source_release_body",
        "upstream_pack_row_objects",
        "upstream_source_release_sha256",
        "world_matrix_binding",
        "raw_source_support",
        "cells",
        "cell_manifest_sha256",
        "candidate_authority_byte_identical_all_cells",
        "candidate_turnover_count_all_cells",
        "world_matrix_authority_byte_identical_all_cells",
        "world_matrix_turnover_count_all_cells",
        "all_cells_k80_feasible",
        "support_gate_status",
        "production_execution_status",
        "canonical_source_v3_control_reopener",
        "remaining_integration_seam",
        "conditional_fantasy_points_effect",
        "conditional_sis_effect",
        "fp_by_sis_interaction",
        "additive_vendor_effect_claim_forbidden",
        "slate_support_census_sha256",
    }
    if set(item) != expected_fields:
        _fail("FP/SIS support census fields differ")
    if (
        item.get("schema_version") != SLATE_CENSUS_SCHEMA
        or item.get("experiment_id") != registry.MATCHUP_EXPERIMENT_ID
        or item.get("registry_sha256")
        != registry.frozen_paid_source_ablation_registry_v1()["registry_sha256"]
        or item.get("candidate_authority_byte_identical_all_cells") is not True
        or item.get("candidate_turnover_count_all_cells") != 0
        or item.get("world_matrix_authority_byte_identical_all_cells") is not True
        or item.get("world_matrix_turnover_count_all_cells") != 0
        or item.get("conditional_fantasy_points_effect")
        != "not_evaluated_without_independent_grade"
        or item.get("conditional_sis_effect")
        != "not_evaluated_without_independent_grade"
        or item.get("fp_by_sis_interaction")
        != "not_evaluated_without_independent_grade"
        or item.get("additive_vendor_effect_claim_forbidden") is not True
        or item.get("production_execution_status")
        != PRODUCTION_EXECUTION_STATUS
        or item.get("canonical_source_v3_control_reopener")
        != CANONICAL_SOURCE_V3_CONTROL_REOPENER
        or item.get("remaining_integration_seam") != REMAINING_INTEGRATION_SEAM
        or item.get("historical_source_observation_time_status")
        != "not-measurable-no-authoritative-observation-timestamps"
        or item.get("value_claim") != "not_evaluated"
        or item.get("source_value_established") is not False
    ):
        _fail("FP/SIS support census policy differs")
    ordinal = _integer(
        item.get("source_task_ordinal"), label="FP/SIS source task ordinal"
    )
    try:
        expected_slate = catalog_v1.expected_slate_for_source_task(ordinal)
        expected_task_id = catalog_v1.task_id_for_source_task(ordinal)
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6PaidSourceAblationV1Error(str(exc)) from exc
    if item.get("slate") != expected_slate or item.get("task_id") != expected_task_id:
        _fail("FP/SIS support census differs from the fixed slate lattice")
    matrix = _mapping(
        item.get("world_matrix_binding"), label="FP/SIS world matrix binding"
    )
    _reject_outcomes(matrix, label="FP/SIS world matrix binding")
    _validate_hash(
        matrix,
        field="world_matrix_binding_sha256",
        label="FP/SIS world matrix binding",
    )
    matrix_candidate_count = _integer(
        matrix.get("candidate_count"), label="world candidate count", minimum=1
    )
    _integer(matrix.get("world_count"), label="world count", minimum=1)
    if (
        matrix.get("schema_version") not in {
            WORLD_BINDING_SCHEMA, DISCOVERY_WORLD_BINDING_SCHEMA,
        }
        or matrix.get("matrix_representation")
        != "candidate-by-simulated-world-dk-points"
        or matrix.get("matrix_byte_representation")
        not in {
            "r6-paid-source-world-matrix-bytes/v1",
            DISCOVERY_WORLD_BYTES_SCHEMA,
        }
        or not registry.is_sha256(matrix.get("candidate_order_sha256"))
        or not registry.is_sha256(matrix.get("score_matrix_sha256"))
    ):
        _fail("FP/SIS world matrix binding policy differs")
    if matrix.get("schema_version") == DISCOVERY_WORLD_BINDING_SCHEMA:
        law = _mapping(
            matrix.get("selection_bank_law"),
            label="FP/SIS discovery selection bank law",
        )
        if law != {
            "block_order": list(DISCOVERY_BLOCK_ORDER),
            "worlds_per_block": DISCOVERY_WORLDS_PER_BLOCK,
            "world_count": DISCOVERY_WORLD_COUNT,
            "scoring_law_id": DISCOVERY_SCORING_LAW_ID,
            "r4_heldout_bound_but_not_read": True,
        }:
            _fail("FP/SIS discovery selection bank law differs")
    world_identity = _mapping(
        matrix.get("world_matrix_identity"), label="FP/SIS world identity"
    )
    if source.normalize_object_identity_v2(
        world_identity, label="FP/SIS world identity"
    ) != world_identity:
        _fail("FP/SIS world identity differs from its canonical projection")
    for field, label in (
        ("structural_catalog_identity", "structural catalog identity"),
        ("accepted_candidate_artifact_identity", "candidate artifact identity"),
        ("upstream_source_release_identity", "source release identity"),
    ):
        retained_identity = _mapping(item.get(field), label=f"FP/SIS {label}")
        if source.normalize_object_identity_v2(
            retained_identity, label=f"FP/SIS {label}"
        ) != retained_identity:
            _fail(f"FP/SIS {label} differs from its canonical projection")
    structural_catalog = source.validate_structural_catalog_v2(
        _mapping(
            item.get("structural_catalog_body"),
            label="FP/SIS structural catalog body",
        )
    )
    _bind_body(
        structural_catalog,
        _mapping(
            item.get("structural_catalog_identity"),
            label="FP/SIS structural catalog identity",
        ),
        label="FP/SIS structural catalog identity",
    )
    pack_bodies = [
        _mapping(row, label="FP/SIS upstream pack body")
        for row in _sequence(
            item.get("upstream_pack_row_objects"),
            label="FP/SIS upstream pack bodies",
        )
    ]
    release_body, release_identity, validated_packs = _validated_source(
        upstream_source_release=_mapping(
            item.get("upstream_source_release_body"),
            label="FP/SIS upstream source release body",
        ),
        upstream_source_release_identity=_mapping(
            item.get("upstream_source_release_identity"),
            label="FP/SIS upstream source release identity",
        ),
        upstream_pack_row_objects=pack_bodies,
    )
    if (
        release_identity != item["upstream_source_release_identity"]
        or release_body["upstream_release_sha256"]
        != item.get("upstream_source_release_sha256")
        or structural_catalog["source_task_ordinal"] != ordinal
    ):
        _fail("FP/SIS exact source/catalog bodies differ")
    candidate_body = source.validate_accepted_candidate_artifact_v1(
        _mapping(
            item.get("accepted_candidate_artifact_body"),
            label="FP/SIS accepted candidate body",
        )
    )
    _bind_body(
        candidate_body,
        _mapping(
            item.get("accepted_candidate_artifact_identity"),
            label="FP/SIS candidate artifact identity",
        ),
        label="FP/SIS accepted candidate artifact identity",
    )
    if (
        candidate_body["source_task_ordinal"] != ordinal
        or len(candidate_body["rows"]) != matrix_candidate_count
        or registry.canonical_sha256([
            row["candidate_id"] for row in candidate_body["rows"]
        ]) != matrix["candidate_order_sha256"]
    ):
        _fail("FP/SIS accepted candidate body differs from matrix authority")
    catalog_join = _mapping(
        item.get("catalog_join_authority"),
        label="FP/SIS catalog join authority",
    )
    _validate_hash(
        catalog_join,
        field="catalog_join_authority_sha256",
        label="FP/SIS catalog join authority",
    )
    expected_catalog_join_fields = {
        "schema_version",
        "structural_catalog_identity",
        "player_rows",
        "player_ids_sha256",
        "teams",
        "teams_sha256",
        "defender_identity_crosswalk_status",
        "catalog_join_authority_sha256",
    }
    player_join_rows = [
        _mapping(row, label="FP/SIS catalog join player")
        for row in _sequence(
            catalog_join.get("player_rows"),
            label="FP/SIS catalog join players",
        )
    ]
    teams = _sequence(catalog_join.get("teams"), label="FP/SIS catalog teams")
    if (
        set(catalog_join) != expected_catalog_join_fields
        or catalog_join.get("schema_version")
        != "r6-paid-source-catalog-join-authority/v1"
        or catalog_join.get("structural_catalog_identity")
        != item["structural_catalog_identity"]
        or any(
            set(row) != {"gsis_id", "team", "opponent"}
            or any(type(row[field]) is not str or not row[field] for field in row)
            for row in player_join_rows
        )
        or len({row["gsis_id"] for row in player_join_rows})
        != len(player_join_rows)
        or catalog_join.get("player_ids_sha256")
        != registry.canonical_sha256([
            row["gsis_id"] for row in player_join_rows
        ])
        or any(type(team) is not str or not team for team in teams)
        or list(teams) != sorted(set(teams))
        or catalog_join.get("teams_sha256") != registry.canonical_sha256(teams)
        or catalog_join.get("defender_identity_crosswalk_status")
        != "unavailable-use-defender-id-plus-structural-defense-team"
    ):
        _fail("FP/SIS catalog join authority differs")
    catalog_player_ids = frozenset(str(row["gsis_id"]) for row in player_join_rows)
    catalog_teams = frozenset(str(team) for team in teams)
    raw_source_support = _mapping(
        item.get("raw_source_support"), label="FP/SIS raw source support"
    )
    if set(raw_source_support) != {"fantasy_points", "sis"}:
        _fail("FP/SIS raw source support fields differ")
    for vendor, slice_kinds in (
        ("fantasy_points", FP_SLICE_KINDS),
        ("sis", SIS_SLICE_KINDS),
    ):
        support = _mapping(
            raw_source_support[vendor], label=f"FP/SIS {vendor} support"
        )
        row_counts = _mapping(
            support.get("slice_row_counts"), label=f"FP/SIS {vendor} row counts"
        )
        stable_counts = _mapping(
            support.get("slice_stable_identity_counts"),
            label=f"FP/SIS {vendor} stable identity counts",
        )
        catalog_counts = _mapping(
            support.get("slice_candidate_catalog_join_counts"),
            label=f"FP/SIS {vendor} catalog join counts",
        )
        join_semantics = _mapping(
            support.get("catalog_join_semantics"),
            label=f"FP/SIS {vendor} catalog join semantics",
        )
        missing_statuses = _mapping(
            support.get("slice_missing_observation_status"),
            label=f"FP/SIS {vendor} missing-observation statuses",
        )
        if (
            support.get("vendor")
            != ("fantasy-points" if vendor == "fantasy_points" else "sis")
            or set(row_counts) != set(slice_kinds)
            or set(stable_counts) != set(slice_kinds)
            or set(catalog_counts) != set(slice_kinds)
            or set(join_semantics) != set(slice_kinds)
            or set(missing_statuses) != set(slice_kinds)
        ):
            _fail(f"FP/SIS {vendor} raw support differs")
        for slice_kind in slice_kinds:
            row_count = _integer(
                row_counts[slice_kind], label=f"{vendor} {slice_kind} row count"
            )
            stable_count = _integer(
                stable_counts[slice_kind],
                label=f"{vendor} {slice_kind} stable count",
            )
            catalog_count = _integer(
                catalog_counts[slice_kind],
                label=f"{vendor} {slice_kind} catalog join count",
            )
            expected_semantics = (
                "exact-offensive-gsis-id-in-structural-catalog"
                if slice_kind in {
                    "fp-route-share", "fp-alignment", "fp-receiver-shell"
                }
                else "nonempty-defender-id-and-defense-in-structural-team-domain"
                if slice_kind == "sis-defender-alignment"
                else "team-in-structural-team-domain"
            )
            if (
                stable_count > row_count
                or catalog_count != stable_count
                or join_semantics[slice_kind] != expected_semantics
                or missing_statuses[slice_kind] != (
                "observed" if row_count > 0 else "missing-no-row"
                )
            ):
                _fail(f"FP/SIS {vendor} slice support differs")
        total = sum(int(value) for value in row_counts.values())
        stable = sum(int(value) for value in stable_counts.values())
        if (
            support.get("raw_row_count") != total
            or support.get("stable_identity_row_count") != stable
            or support.get("identity_unresolved_row_count") != total - stable
            or support.get("missing_observation_status")
            != (
                "observed-at-least-one-raw-row"
                if total > 0
                else "missing-all-vendor-slices"
            )
            or support.get("observation_timestamp_available_row_count") != 0
            or support.get("stale_row_count") is not None
            or support.get("staleness_status")
            != "not-measurable-retrospective-prior-period-reconstruction"
        ):
            _fail(f"FP/SIS {vendor} support census differs")
    cells = [
        _mapping(cell, label="FP/SIS cell")
        for cell in _sequence(item.get("cells"), label="FP/SIS support cells")
    ]
    if len(cells) != len(registry.MATCHUP_CELL_ORDER):
        _fail("FP/SIS support census requires exactly four cells")
    registry.validate_cell_order_v1(
        [_mapping(cell, label="FP/SIS cell")["cell"] for cell in cells],
        experiment="matchup",
    )
    full_source_view = _mapping(
        _mapping(cells[0].get("source_view"), label="FP/SIS on/on source view").get(
            "slices"
        ),
        label="FP/SIS on/on source slices",
    )
    normalized_full_slices = {
        slice_kind: [
            _mapping(row, label=f"FP/SIS full {slice_kind} row")
            for row in _sequence(rows, label=f"FP/SIS full {slice_kind} rows")
        ]
        for slice_kind, rows in full_source_view.items()
    }
    if (
        not set(FP_SLICE_KINDS).issubset(normalized_full_slices)
        or not set(SIS_SLICE_KINDS).issubset(normalized_full_slices)
    ):
        _fail("FP/SIS on/on source view lacks paid-source slices")
    if normalized_full_slices != producer._pack_slices(validated_packs):
        _fail("FP/SIS on/on source view differs from exact seven-pack bodies")
    expected_fp_support = _slice_support(
        normalized_full_slices,
        slice_kinds=FP_SLICE_KINDS,
        vendor="fantasy-points",
        catalog_player_ids=catalog_player_ids,
        catalog_teams=catalog_teams,
    )
    expected_sis_support = _slice_support(
        normalized_full_slices,
        slice_kinds=SIS_SLICE_KINDS,
        vendor="sis",
        catalog_player_ids=catalog_player_ids,
        catalog_teams=catalog_teams,
    )
    if raw_source_support != {
        "fantasy_points": expected_fp_support,
        "sis": expected_sis_support,
    }:
        _fail("FP/SIS raw source support differs from persisted on/on view")
    if item.get("cell_manifest_sha256") != registry.canonical_sha256(cells):
        _fail("FP/SIS support cell manifest differs")
    candidate_identities = [cell["candidate_artifact_identity"] for cell in cells]
    world_identities = [cell["world_matrix_identity"] for cell in cells]
    candidate_order_hashes = [cell["candidate_order_sha256"] for cell in cells]
    if (
        len({registry.canonical_sha256(value) for value in candidate_identities}) != 1
        or len({registry.canonical_sha256(value) for value in world_identities}) != 1
        or len(set(candidate_order_hashes)) != 1
        or candidate_identities[0] != item["accepted_candidate_artifact_identity"]
        or world_identities[0] != matrix["world_matrix_identity"]
        or any(
            cell["world_matrix_binding_sha256"]
            != matrix["world_matrix_binding_sha256"]
            for cell in cells
        )
        or any(cell["candidate_count"] != matrix_candidate_count for cell in cells)
        or candidate_order_hashes[0] != matrix["candidate_order_sha256"]
        or any(cell["candidate_turnover_count"] != 0 for cell in cells)
        or any(cell["world_matrix_turnover_count"] != 0 for cell in cells)
    ):
        _fail("FP/SIS cells do not reuse exact candidate/world authority")
    for cell in cells:
        state = cell["cell"]
        if set(cell) != {
            "cell",
            "candidate_artifact_identity",
            "candidate_count",
            "candidate_order_sha256",
            "world_matrix_identity",
            "world_matrix_binding_sha256",
            "source_view",
            "fantasy_points_support",
            "sis_support",
            "component_support",
            "annotation_rows",
            "annotation_rows_sha256",
            "lineup_support_rows",
            "lineup_support_rows_sha256",
            "retrieval",
            "candidate_turnover_count",
            "world_matrix_turnover_count",
            "marginal_turnover",
            "joint_component_loss_vs_on_on",
            "admission_order_turnover_vs_on_on",
            "selected_k80_order_turnover_vs_on_on",
        }:
            _fail("FP/SIS cell fields differ")
        annotations = [
            _mapping(row, label="FP/SIS annotation row")
            for row in _sequence(
                cell.get("annotation_rows"), label="FP/SIS annotation rows"
            )
        ]
        lineup_rows = [
            _mapping(row, label="FP/SIS lineup support row")
            for row in _sequence(
                cell.get("lineup_support_rows"), label="FP/SIS lineup support rows"
            )
        ]
        retrieval_row = _mapping(
            cell.get("retrieval"), label="FP/SIS retrieval row"
        )
        source_view = _mapping(
            cell.get("source_view"), label="FP/SIS source-view receipt"
        )
        view_slices_raw = _mapping(
            source_view.get("slices"), label="FP/SIS persisted source-view slices"
        )
        view_slices = {
            slice_kind: [
                _mapping(row, label=f"FP/SIS {slice_kind} source-view row")
                for row in _sequence(rows, label=f"FP/SIS {slice_kind} source-view rows")
            ]
            for slice_kind, rows in view_slices_raw.items()
        }
        removed_counts = _mapping(
            source_view.get("removed_slice_row_counts"),
            label="FP/SIS removed slice counts",
        )
        effective_counts = _mapping(
            source_view.get("effective_slice_row_counts"),
            label="FP/SIS effective slice counts",
        )
        expected_removed_counts: dict[str, object] = {}
        if not state["fantasy_points_enabled"]:
            expected_removed_counts.update(
                raw_source_support["fantasy_points"]["slice_row_counts"]
            )
        if not state["sis_enabled"]:
            expected_removed_counts.update(
                raw_source_support["sis"]["slice_row_counts"]
            )
        expected_view_slices = {
            slice_kind: (
                []
                if (
                    slice_kind in FP_SLICE_KINDS
                    and not state["fantasy_points_enabled"]
                ) or (
                    slice_kind in SIS_SLICE_KINDS
                    and not state["sis_enabled"]
                )
                else rows
            )
            for slice_kind, rows in normalized_full_slices.items()
        }
        expected_effective_counts = {
            slice_kind: len(rows)
            for slice_kind, rows in expected_view_slices.items()
        }
        retained_view_hash = source_view.get("source_view_sha256")
        view_body = {
            field: field_value
            for field, field_value in source_view.items()
            if field != "source_view_sha256"
        }
        if (
            set(source_view) != {
                "schema_version",
                "fantasy_points_enabled",
                "sis_enabled",
                "removed_slice_row_counts",
                "removed_row_count",
                "effective_slice_row_counts",
                "effective_row_count",
                "slices",
                "source_view_sha256",
            }
            or source_view.get("schema_version")
            != "r6-paid-source-derived-source-view/v1"
            or source_view.get("fantasy_points_enabled")
            is not state["fantasy_points_enabled"]
            or source_view.get("sis_enabled") is not state["sis_enabled"]
            or view_slices != expected_view_slices
            or removed_counts != expected_removed_counts
            or effective_counts != expected_effective_counts
            or source_view.get("removed_row_count")
            != sum(int(count) for count in expected_removed_counts.values())
            or source_view.get("effective_row_count")
            != sum(
                _integer(count, label="FP/SIS effective slice row count")
                for count in effective_counts.values()
            )
            or not registry.is_sha256(retained_view_hash)
            or retained_view_hash != registry.canonical_sha256(view_body)
        ):
            _fail("FP/SIS raw source-view removal receipt differs")
        for vendor, enabled_field, slice_kinds in (
            ("fantasy_points", "fantasy_points_enabled", FP_SLICE_KINDS),
            ("sis", "sis_enabled", SIS_SLICE_KINDS),
        ):
            if any(
                effective_counts.get(slice_kind)
                != (
                    raw_source_support[vendor]["slice_row_counts"][slice_kind]
                    if state[enabled_field]
                    else 0
                )
                for slice_kind in slice_kinds
            ):
                _fail(f"FP/SIS {vendor} effective source-view counts differ")
        for vendor, enabled_field, support_field in (
            ("fantasy_points", "fantasy_points_enabled", "fantasy_points_support"),
            ("sis", "sis_enabled", "sis_support"),
        ):
            retained_support = _mapping(
                cell.get(support_field), label=f"FP/SIS {vendor} cell support"
            )
            base_support = _mapping(
                raw_source_support[vendor], label=f"FP/SIS {vendor} base support"
            )
            enabled = state[enabled_field] is True
            if (
                any(
                    retained_support.get(field) != field_value
                    for field, field_value in base_support.items()
                )
                or retained_support.get("enabled_in_cell") is not enabled
                or retained_support.get("effective_raw_row_count")
                != (base_support["raw_row_count"] if enabled else 0)
                or retained_support.get("cell_missing_observation_status")
                != (
                    base_support["missing_observation_status"]
                    if enabled
                    else "disabled-physical-removal-before-components"
                )
            ):
                _fail(f"FP/SIS {vendor} cell support differs")
        if (
            cell.get("annotation_rows_sha256")
            != registry.canonical_sha256(annotations)
            or cell.get("lineup_support_rows_sha256")
            != registry.canonical_sha256(lineup_rows)
            or cell.get("candidate_count") != len(lineup_rows)
            or cell.get("candidate_order_sha256")
            != registry.canonical_sha256([
                row["candidate_id"] for row in lineup_rows
            ])
        ):
            _fail("FP/SIS cell row manifests differ")
        if cell.get("component_support") != _component_support(annotations):
            _fail("FP/SIS component support census differs")
        disabled_sources = {
            source_name
            for source_name, enabled in (
                ("fantasy-points", state["fantasy_points_enabled"]),
                ("sis", state["sis_enabled"]),
            )
            if not enabled
        }
        for row in annotations:
            raw_values = _mapping(
                row.get("raw_component_values"),
                label="FP/SIS raw component values",
            )
            support_values = _mapping(
                row.get("component_support"),
                label="FP/SIS component support",
            )
            reasons = _mapping(
                row.get("component_missingness_reasons"),
                label="FP/SIS component missingness reasons",
            )
            if set(raw_values) != set(support_values) or set(raw_values) != set(reasons):
                _fail("FP/SIS component support fields differ")
            for component, raw_value in raw_values.items():
                if support_values[component] is not (raw_value is not None):
                    _fail("FP/SIS raw component support differs")
                dependencies = SOURCE_REQUIRED_COMPONENTS.get(component, frozenset())
                disabled_dependencies = dependencies & disabled_sources
                if raw_value is None and disabled_dependencies:
                    expected_reason = (
                        "source-disabled-by-ablation:"
                        + ",".join(sorted(disabled_dependencies))
                    )
                    if reasons[component] != expected_reason:
                        _fail("FP/SIS disabled-source missingness reason differs")
        lineup_ids = [row.get("candidate_id") for row in lineup_rows]
        for row in lineup_rows:
            supported_count = _integer(
                row.get("supported_matchup_player_count"),
                label="supported matchup player count",
            )
            completeness = _number(
                row.get("annotation_completeness"),
                label="annotation completeness",
            )
            edge = row.get("matchup_edge_mean")
            if edge is not None:
                _number(edge, label="matchup edge mean")
            if (
                supported_count > 8
                or not math.isclose(
                    completeness, supported_count / 8.0, abs_tol=1e-12
                )
                or (edge is None) is not (supported_count == 0)
                or row.get("qualifies_for_matchup_admission")
                is not (
                    row.get("qb_depth1_eligible") is True
                    and supported_count
                    >= registry.MATCHUP_MINIMUM_SUPPORTED_PLAYERS
                    and completeness >= registry.MATCHUP_MINIMUM_COMPLETENESS
                )
            ):
                _fail("FP/SIS lineup support semantics differ")
        if (
            any(type(candidate_id) is not str or not candidate_id for candidate_id in lineup_ids)
            or len(lineup_ids) != len(set(lineup_ids))
            or any(
                row.get("missing_semantics") != "missing-not-zero"
                or type(row.get("qb_depth1_eligible")) is not bool
                or type(row.get("qualifies_for_matchup_admission")) is not bool
                for row in lineup_rows
            )
        ):
            _fail("FP/SIS lineup support rows differ")
        qualifying = [
            row for row in lineup_rows
            if row["qualifies_for_matchup_admission"] is True
        ]
        if any(row.get("matchup_edge_mean") is None for row in qualifying):
            _fail("FP/SIS qualifying lineup lacks an edge mean")
        ranked = sorted(
            qualifying,
            key=lambda row: (
                -_number(row["matchup_edge_mean"], label="matchup edge mean"),
                str(row["candidate_id"]),
            ),
        )
        expected_admission_ranked = [
            str(row["candidate_id"])
            for row in ranked[: registry.MATCHUP_ADMISSION_CAP]
        ]
        admission_ranked = [
            str(value)
            for value in _sequence(
                retrieval_row.get("admission_ranked_candidate_ids"),
                label="FP/SIS admission-ranked IDs",
            )
        ]
        selected = _sequence(
            retrieval_row.get("selected_k80_candidate_ids"),
            label="FP/SIS selected K80 IDs",
        )
        admitted = _sequence(
            retrieval_row.get("admitted_candidate_ids"),
            label="FP/SIS admitted IDs",
        )
        if any(type(value) is not str or not value for value in selected + admitted):
            _fail("FP/SIS retrieval IDs must be nonempty strings")
        feasible = len(admitted) >= registry.ENTRY_BUDGET
        if (
            admission_ranked != expected_admission_ranked
            or admitted != sorted(admission_ranked)
            or retrieval_row.get("qualifying_candidate_count") != len(qualifying)
            or retrieval_row.get("admission_cap") != registry.MATCHUP_ADMISSION_CAP
            or retrieval_row.get("admitted_candidate_count") != len(admitted)
            or retrieval_row.get("admission_ranked_candidate_ids_sha256")
            != registry.canonical_sha256(admission_ranked)
            or retrieval_row.get("selected_k80_candidate_ids_sha256")
            != registry.canonical_sha256(selected)
            or retrieval_row.get("admitted_candidate_ids_sha256")
            != registry.canonical_sha256(admitted)
            or retrieval_row.get("k80_feasible") is not feasible
            or retrieval_row.get("selection_status")
            != ("complete" if feasible else "support-gate-failed")
            or (
                feasible
                and (
                    len(selected) != registry.ENTRY_BUDGET
                    or len(selected) != len(set(selected))
                    or not set(selected).issubset(admitted)
                )
            )
            or (not feasible and selected)
        ):
            _fail("FP/SIS selected K80 membership differs from support gate")
        selection_trace = [
            _mapping(row, label="FP/SIS selection trace row")
            for row in _sequence(
                retrieval_row.get("selection_trace"),
                label="FP/SIS selection trace",
            )
        ]
        if (
            retrieval_row.get("selection_trace_sha256")
            != registry.canonical_sha256(selection_trace)
            or retrieval_row.get("selected_k80_order_is_selector_order") is not True
            or len(selection_trace) != (registry.ENTRY_BUDGET if feasible else 0)
            or any(
                set(row) != {
                    "selection_rank",
                    "candidate_id",
                    "marginal_new_world_count",
                    "individual_threshold_world_count",
                }
                or row.get("selection_rank") != rank
                or row.get("candidate_id") != selected[rank]
                or _integer(
                    row.get("marginal_new_world_count"),
                    label="marginal new-world count",
                ) < 0
                or _integer(
                    row.get("individual_threshold_world_count"),
                    label="individual threshold-world count",
                ) < 0
                for rank, row in enumerate(selection_trace)
            )
        ):
            _fail("FP/SIS selection trace differs")
        if not (
            state["fantasy_points_enabled"] and state["sis_enabled"]
        ) and any(
            row["family"] == "receiver"
            and any(
                row["raw_component_values"][component] is not None
                for component in JOINT_FP_SIS_COMPONENTS
            )
            for row in annotations
        ):
            _fail("FP/SIS missing-source cell retained a joint component")
    reference_annotations = {
        str(row["gsis_id"]): row for row in cells[0]["annotation_rows"]
    }
    reference_retrieval = cells[0]["retrieval"]
    for cell in cells:
        annotations = {
            str(row["gsis_id"]): row for row in cell["annotation_rows"]
        }
        if set(annotations) != set(reference_annotations):
            _fail("FP/SIS cells changed the annotation player universe")
        changed_raw = sum(
            reference_annotations[player_id]["raw_component_values"][component]
            != annotations[player_id]["raw_component_values"][component]
            for player_id in reference_annotations
            for component in reference_annotations[player_id][
                "raw_component_values"
            ]
        )
        changed_percentile = sum(
            reference_annotations[player_id]["component_values"][component]
            != annotations[player_id]["component_values"][component]
            for player_id in reference_annotations
            for component in reference_annotations[player_id]["component_values"]
        )
        reference_ranks = _rank_map(
            list(reference_annotations.values()),
            id_field="gsis_id",
            value_field="matchup_edge_score",
        )
        cell_ranks = _rank_map(
            list(annotations.values()),
            id_field="gsis_id",
            value_field="matchup_edge_score",
        )
        common_rank_ids = set(reference_ranks) & set(cell_ranks)
        expected_marginal = {
            "raw_component_value_change_count": changed_raw,
            "component_percentile_change_count": changed_percentile,
            "player_edge_value_change_count": sum(
                reference_annotations[player_id]["matchup_edge_score"]
                != annotations[player_id]["matchup_edge_score"]
                for player_id in reference_annotations
            ),
            "shared_supported_player_count": len(common_rank_ids),
            "player_edge_rank_change_count": sum(
                reference_ranks[player_id] != cell_ranks[player_id]
                for player_id in common_rank_ids
            ),
        }
        if cell.get("marginal_turnover") != expected_marginal:
            _fail("FP/SIS marginal turnover differs")
        expected_joint_loss = {
            component: sum(
                reference_annotations[player_id]["component_support"].get(component)
                is True
                and annotations[player_id]["component_support"].get(component)
                is not True
                for player_id in reference_annotations
            )
            for component in JOINT_FP_SIS_COMPONENTS
        }
        if cell.get("joint_component_loss_vs_on_on") != expected_joint_loss:
            _fail("FP/SIS joint-component loss differs")
        expected_admission_turnover = _turnover(
            reference_retrieval["admission_ranked_candidate_ids"],
            cell["retrieval"]["admission_ranked_candidate_ids"],
            label="matchup admission order",
        )
        if cell.get("admission_order_turnover_vs_on_on") != (
            expected_admission_turnover
        ):
            _fail("FP/SIS admission-order turnover differs")
        expected_selected_turnover = (
            _turnover(
                reference_retrieval["selected_k80_candidate_ids"],
                cell["retrieval"]["selected_k80_candidate_ids"],
                label="matchup selected K80 order",
            )
            if reference_retrieval["k80_feasible"]
            and cell["retrieval"]["k80_feasible"]
            else {
                "status": "not_evaluated_support_gate_failed",
                "reference_k80_feasible": reference_retrieval["k80_feasible"],
                "cell_k80_feasible": cell["retrieval"]["k80_feasible"],
            }
        )
        if cell.get("selected_k80_order_turnover_vs_on_on") != (
            expected_selected_turnover
        ):
            _fail("FP/SIS selected-K80 order turnover differs")
    if item.get("all_cells_k80_feasible") != all(
        cell["retrieval"]["k80_feasible"] for cell in cells
    ):
        _fail("FP/SIS panel gate differs from cell support")
    expected_gate_status = (
        "passed" if item["all_cells_k80_feasible"] else "failed"
    )
    if item.get("support_gate_status") != expected_gate_status:
        _fail("FP/SIS support-gate status differs")
    for field in registry.FALSE_AUTHORITY_FIELDS:
        if item.get(field) is not False:
            _fail("FP/SIS support census claims downstream authority")
    return item


def build_fp_sis_panel_support_census_v1(
    slate_censuses: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Aggregate the exact 54-slate pre-freeze support gate."""
    values = [
        validate_fp_sis_retrieval_support_census_v1(value)
        for value in slate_censuses
    ]
    if len(values) != source.TASK_COUNT:
        _fail("FP/SIS panel support census requires exactly 54 slates")
    if [value["source_task_ordinal"] for value in values] != list(
        range(source.TASK_COUNT)
    ):
        _fail("FP/SIS panel support censuses differ from fixed task order")
    cell_rows = []
    for cell_id in registry.MATCHUP_CELL_ORDER:
        cells = [
            next(cell for cell in value["cells"] if cell["cell"]["cell_id"] == cell_id)
            for value in values
        ]
        cell_rows.append({
            "cell_id": cell_id,
            "slate_count": len(cells),
            "k80_feasible_slate_count": sum(
                cell["retrieval"]["k80_feasible"] for cell in cells
            ),
            "minimum_qualifying_candidate_count": min(
                cell["retrieval"]["qualifying_candidate_count"] for cell in cells
            ),
            "fantasy_points_raw_support_row_count": sum(
                cell["fantasy_points_support"]["raw_row_count"] for cell in cells
            ),
            "sis_raw_support_row_count": sum(
                cell["sis_support"]["raw_row_count"] for cell in cells
            ),
        })
    passed = all(
        row["k80_feasible_slate_count"] == source.TASK_COUNT for row in cell_rows
    )
    body: dict[str, object] = {
        "schema_version": PANEL_CENSUS_SCHEMA,
        "experiment_id": registry.MATCHUP_EXPERIMENT_ID,
        "slate_count": len(values),
        "slate_census_sha256s": [
            value["slate_support_census_sha256"] for value in values
        ],
        "slate_census_manifest_sha256": registry.canonical_sha256([
            value["slate_support_census_sha256"] for value in values
        ]),
        "cells": cell_rows,
        "cell_manifest_sha256": registry.canonical_sha256(cell_rows),
        "all_cells_all_slates_k80_feasible": passed,
        "support_gate_status": "passed" if passed else "failed-redesign-before-grade",
        "production_execution_status": (
            PRODUCTION_EXECUTION_STATUS
        ),
        "canonical_source_v3_control_reopener": (
            CANONICAL_SOURCE_V3_CONTROL_REOPENER
        ),
        "remaining_integration_seam": REMAINING_INTEGRATION_SEAM,
        **_policy(),
    }
    return _with_hash(body, field="panel_support_census_sha256")


def validate_fp_sis_panel_support_census_v1(
    value: object,
) -> dict[str, object]:
    item = _mapping(value, label="FP/SIS panel support census")
    _reject_outcomes(item, label="FP/SIS panel support census")
    _validate_hash(
        item,
        field="panel_support_census_sha256",
        label="FP/SIS panel support census",
    )
    if set(item) != set(_policy()) | {
        "schema_version",
        "experiment_id",
        "slate_count",
        "slate_census_sha256s",
        "slate_census_manifest_sha256",
        "cells",
        "cell_manifest_sha256",
        "all_cells_all_slates_k80_feasible",
        "support_gate_status",
        "production_execution_status",
        "canonical_source_v3_control_reopener",
        "remaining_integration_seam",
        "panel_support_census_sha256",
    }:
        _fail("FP/SIS panel support census fields differ")
    if (
        item.get("schema_version") != PANEL_CENSUS_SCHEMA
        or item.get("experiment_id") != registry.MATCHUP_EXPERIMENT_ID
        or item.get("slate_count") != source.TASK_COUNT
        or item.get("production_execution_status")
        != PRODUCTION_EXECUTION_STATUS
        or item.get("canonical_source_v3_control_reopener")
        != CANONICAL_SOURCE_V3_CONTROL_REOPENER
        or item.get("remaining_integration_seam") != REMAINING_INTEGRATION_SEAM
        or item.get("historical_source_observation_time_status")
        != "not-measurable-no-authoritative-observation-timestamps"
        or item.get("value_claim") != "not_evaluated"
        or item.get("source_value_established") is not False
    ):
        _fail("FP/SIS panel support census policy differs")
    slate_hashes = _sequence(
        item.get("slate_census_sha256s"), label="FP/SIS slate census hashes"
    )
    if (
        len(slate_hashes) != source.TASK_COUNT
        or any(not registry.is_sha256(value) for value in slate_hashes)
        or item.get("slate_census_manifest_sha256")
        != registry.canonical_sha256(slate_hashes)
    ):
        _fail("FP/SIS panel slate manifest differs")
    cells = [
        _mapping(cell, label="FP/SIS panel cell")
        for cell in _sequence(item.get("cells"), label="FP/SIS panel cells")
    ]
    if [cell.get("cell_id") for cell in cells] != list(registry.MATCHUP_CELL_ORDER):
        _fail("FP/SIS panel cells differ from frozen order")
    if item.get("cell_manifest_sha256") != registry.canonical_sha256(cells):
        _fail("FP/SIS panel cell manifest differs")
    for cell in cells:
        feasible_count = _integer(
            cell.get("k80_feasible_slate_count"),
            label="FP/SIS K80-feasible slate count",
        )
        if (
            cell.get("slate_count") != source.TASK_COUNT
            or feasible_count > source.TASK_COUNT
            or _integer(
                cell.get("minimum_qualifying_candidate_count"),
                label="FP/SIS minimum qualifying candidate count",
            ) < 0
            or _integer(
                cell.get("fantasy_points_raw_support_row_count"),
                label="FP/SIS Fantasy Points raw support row count",
            ) < 0
            or _integer(
                cell.get("sis_raw_support_row_count"),
                label="FP/SIS SIS raw support row count",
            ) < 0
        ):
            _fail("FP/SIS panel support counts differ")
    passed = all(
        cell["k80_feasible_slate_count"] == source.TASK_COUNT for cell in cells
    )
    if (
        item.get("all_cells_all_slates_k80_feasible") is not passed
        or item.get("support_gate_status")
        != ("passed" if passed else "failed-redesign-before-grade")
    ):
        _fail("FP/SIS panel support gate differs")
    for field in registry.FALSE_AUTHORITY_FIELDS:
        if item.get(field) is not False:
            _fail("FP/SIS panel support census claims downstream authority")
    return item


__all__ = [
    "CANONICAL_SOURCE_V3_CONTROL_REOPENER",
    "CorpusR6PaidSourceAblationV1Error",
    "FP_SLICE_KINDS",
    "JOINT_FP_SIS_COMPONENTS",
    "PRODUCTION_EXECUTION_STATUS",
    "REMAINING_INTEGRATION_SEAM",
    "SIS_SLICE_KINDS",
    "SOURCE_REQUIRED_COMPONENTS",
    "build_discovery_world_matrix_binding_v2",
    "build_fp_sis_panel_support_census_v1",
    "build_world_matrix_binding_v1",
    "canonical_world_matrix_bytes_v1",
    "run_fp_sis_retrieval_support_census_v1",
    "validate_fp_sis_panel_support_census_v1",
    "validate_fp_sis_retrieval_support_census_v1",
    "validate_discovery_world_matrix_binding_v2",
    "validate_world_matrix_binding_v1",
]
