"""Bounded offline adapter for the lab epistemics/run-lineage packet.

The adapter consumes caller-supplied, content-bound CSV bytes and emits only
the governed graph-vNext logical rows plus a deterministic projection receipt.
It has no filesystem, cloud, Neo4j, outcome, or policy side effect.  The lab
Cypher loader is deliberately not imported.

Phase B v1 keeps realized, winner, and settlement evidence closed.  A future
schema may open that boundary only with a separately reviewed evidence
identity-and-scope contract; putting an identity-shaped value in this manifest
does not grant authority.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Final

from nfl_dfs.research import corpus_graph_vnext_contracts as graph
from nfl_dfs.research.object_identity import IDENTITY_FIELDS, content_identity

MANIFEST_SCHEMA: Final = "lab-epistemics-phase-b-manifest/v1"
PROJECTION_SCHEMA: Final = "lab-epistemics-phase-b-projection/v1"
RECEIPT_SCHEMA: Final = "lab-epistemics-phase-b-receipt/v1"
ARTIFACT_FORMAT: Final = "neo4j-import-csv/v1"

MAX_MANIFEST_BYTES: Final = 256 * 1024
MAX_ARTIFACT_BYTES: Final = 8 * 1024 * 1024
MAX_ROWS_PER_ARTIFACT: Final = 10_000
MAX_TEXT_BYTES: Final = 512

NODE_ARTIFACT_ROLES: Final = frozenset({"base_nodes", "run_nodes"})
EDGE_ARTIFACT_ROLES: Final = frozenset({"base_edges", "run_edges"})
ARTIFACT_ROLES: Final = NODE_ARTIFACT_ROLES | EDGE_ARTIFACT_ROLES

BASE_NODE_KINDS: Final = frozenset({
    "Question", "Claim", "Read", "Hold", "Experiment", "Preregistration",
})
RUN_NODE_KINDS: Final = frozenset({
    "ExperimentRun", "ProposalAttemptAggregate", "Slate",
})
LAB_NODE_KINDS: Final = BASE_NODE_KINDS | RUN_NODE_KINDS
BASE_RELATIONSHIPS: Final = frozenset({"EVIDENCED_BY", "BLOCKED_BY"})
RUN_RELATIONSHIPS: Final = frozenset({"PROPOSED_IN"})
LAB_RELATIONSHIPS: Final = BASE_RELATIONSHIPS | RUN_RELATIONSHIPS

LAB_NODE_ID_PREFIX: Final = {
    "Question": "q:",
    "Claim": "c:",
    "Read": "read:",
    "Hold": "hold:",
    "Experiment": "exp:",
    "Preregistration": "prereg:",
    "ExperimentRun": "run:",
    "ProposalAttemptAggregate": "attempts:",
    "Slate": "slate:",
}
PROPOSAL_FAMILIES: Final = frozenset({
    "single", "split", "split_stream1", "split_stream2",
})
OUTCOME_EVIDENCE_PATTERN: Final = (
    r"(?<![A-Za-z0-9])(actual|realized|winner|winning|won|win|settlement|"
    r"settled|payout|"
    r"winnings|roi|rank|ranked|place|placed|finish|finished|score|scored|"
    r"points|fantasy[_ -]?points|dk[_ -]?points|cash|cashed|profit|loss|lost)"
    r"(?![A-Za-z0-9])"
)
OUTCOME_COMPACT_FRAGMENTS: Final = (
    "actualpoints", "contestplace", "dkpoints", "fantasypoints",
    "finishedfirst", "lineupscore", "payout", "realized", "settlement",
    "tournamentrank", "winner", "winning", "winnings",
)

PRODUCTION_NODE_KIND: Final = {
    "Question": "Question",
    "Claim": "Claim",
    "Read": "Read",
    "Hold": "Hold",
    "Experiment": "ExperimentDefinition",
    "Preregistration": "Preregistration",
    "ExperimentRun": "RunObservation",
    "ProposalAttemptAggregate": "ProposalAttemptAggregate",
    "Slate": "Slate",
}
PRODUCTION_RELATIONSHIP: Final = {
    ("Claim", "EVIDENCED_BY", "Read"): "EVIDENCED_BY",
    ("Experiment", "BLOCKED_BY", "Hold"): "BLOCKED_BY",
    ("ExperimentRun", "PROPOSED_IN", "Experiment"): "RUN_OF",
    ("ProposalAttemptAggregate", "PROPOSED_IN", "Slate"): "FOR_SLATE",
}
PRODUCTION_NODE_KINDS: Final = frozenset(PRODUCTION_NODE_KIND.values())
PRODUCTION_RELATIONSHIPS: Final = frozenset(PRODUCTION_RELATIONSHIP.values())
PRODUCTION_NODE_NAMESPACE: Final = {
    "Question": "epistemic",
    "Claim": "epistemic",
    "Read": "epistemic",
    "Hold": "epistemic",
    "ExperimentDefinition": "epistemic",
    "Preregistration": "epistemic",
    "RunObservation": "lineage",
    "ProposalAttemptAggregate": "lineage",
    "Slate": "identity",
}
PRODUCTION_RELATIONSHIP_NAMESPACE: Final = {
    "EVIDENCED_BY": "epistemic",
    "BLOCKED_BY": "epistemic",
    "RUN_OF": "lineage",
    "FOR_SLATE": "lineage",
}

NODE_PROPERTY_TRANSFORMS: Final = {
    "Question": {
        "source_id": "copy:id:ID", "text": "copy:text",
        "status": "copy:status", "decision_channel": "rename:score_channel",
        "note": "copy_nonblank:note",
    },
    "Claim": {
        "source_id": "copy:id:ID", "text": "copy:text",
        "strength": "copy:strength",
    },
    "Read": {
        "source_id": "copy:id:ID",
        "preregistration_reference": "rename:prereg",
        "verdict": "copy:verdict", "endpoint_era": "copy:endpoint_era",
        "evidence_class": "rename:class",
    },
    "Hold": {
        "source_id": "copy:id:ID", "reason": "copy:reason",
        "releaser": "copy:releaser",
    },
    "Experiment": {
        "source_id": "copy:id:ID", "name": "copy:name",
    },
    "Preregistration": {
        "source_id": "copy:id:ID", "file_name": "rename:file",
        "amendment_count": "canonical_nonnegative_integer:amendments",
    },
    "ExperimentRun": {
        "source_id": "copy:id:ID", "run_id": "strip_required_prefix:run:",
        "experiment_name": "rename:experiment",
        "code_commit": "exact_git_commit:code_sha",
        "image_digest": "immutable_sha256:image",
        "shard_count": "canonical_nonnegative_integer:shards",
        "slate_count": "canonical_nonnegative_integer:slates",
        "reported_reconciled_ledger_count": (
            "canonical_nonnegative_integer:ledger_reconciles"
        ),
        "reported_ledger_violation_count": (
            "canonical_nonnegative_integer:ledger_violations"
        ),
        "source_prefix_uri": (
            "canonical_gcs_prefix_bound_to_experiment_and_run:uri"
        ),
        "verification_status": "constant:reported_unverified",
    },
    "ProposalAttemptAggregate": {
        "source_id": "copy:id:ID", "family": "copy:family",
        "reported_attempt_count": "canonical_nonnegative_integer:attempts",
        "reported_new_count": "canonical_nonnegative_integer:new",
        "reported_duplicate_count": "canonical_nonnegative_integer:dup",
        "reported_reconciles": "canonical_boolean:reconciles",
        "reconciliation_verified": "constant:false",
    },
    "Slate": {
        "source_id": "copy:id:ID",
        "season": "canonical_nonnegative_integer:season",
        "week": "canonical_nonnegative_integer:week",
    },
}

RELATIONSHIP_ENDPOINT_KINDS: Final = {
    "EVIDENCED_BY": frozenset({("Claim", "Read")}),
    "BLOCKED_BY": frozenset({("Experiment", "Hold")}),
    "PROPOSED_IN": frozenset({
        ("ProposalAttemptAggregate", "Slate"),
        ("ExperimentRun", "Experiment"),
    }),
}

SOURCE_EVIDENCE_CLASSES: Final = frozenset({
    "epistemic_registry", "governance", "outcome_blind_mechanics",
})
REQUIRED_SOURCE_ROLES: Final = frozenset({
    "base_registry", "base_release_manifest", "run_receipt",
    "run_mechanics_shard",
})
SOURCE_ROLE_EVIDENCE_CLASS: Final = {
    "base_registry": "epistemic_registry",
    "base_release_manifest": "governance",
    "run_receipt": "governance",
    "run_mechanics_shard": "outcome_blind_mechanics",
}
ARTIFACT_SOURCE_ROLES: Final = {
    "base_nodes": frozenset({"base_registry", "base_release_manifest"}),
    "base_edges": frozenset({"base_registry", "base_release_manifest"}),
    "run_nodes": frozenset({"run_receipt", "run_mechanics_shard"}),
    "run_edges": frozenset({"run_receipt", "run_mechanics_shard"}),
}
AUTHORITY_FLAGS: Final = {
    "database_load_authority": False,
    "decision_authority": False,
    "graph_mutation_authority": False,
    "historical_outcome_read_authority": False,
    "lineup_population_authority": False,
    "live_money_policy_authority": False,
    "production_default_change_authority": False,
}

MAPPING_SCHEMA_VERSION: Final = "lab-epistemics-production-mapping/v1"
MAPPING_CONTRACT: Final = {
    "schema_version": MAPPING_SCHEMA_VERSION,
    "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
    "node_kinds": dict(sorted(PRODUCTION_NODE_KIND.items())),
    "node_id": {
        "production_template": "lab:{source_id}",
        "required_source_prefix_by_kind": dict(sorted(LAB_NODE_ID_PREFIX.items())),
    },
    "node_namespaces": {
        source_kind: PRODUCTION_NODE_NAMESPACE[production_kind]
        for source_kind, production_kind in sorted(PRODUCTION_NODE_KIND.items())
    },
    "node_property_transforms": {
        kind: dict(sorted(transforms.items()))
        for kind, transforms in sorted(NODE_PROPERTY_TRANSFORMS.items())
    },
    "source_control_columns_dropped": [":LABEL", "id:ID"],
    "source_blank_policy": "omit_optional_else_reject",
    "relationships": [
        {
            "source_kind": source_kind,
            "source_relationship": relationship,
            "target_kind": target_kind,
            "production_relationship": production,
            "production_namespace": PRODUCTION_RELATIONSHIP_NAMESPACE[production],
            "production_properties": {},
        }
        for (source_kind, relationship, target_kind), production in sorted(
            PRODUCTION_RELATIONSHIP.items()
        )
    ],
    "derived_relationships": [],
    "semantic_reconciliation": [
        "all_claims_have_explicit_evidence_endpoint",
        "all_read_preregistration_references_resolve_without_derived_edges",
        "one_run_one_slate",
        "one_run_of_endpoint_matching_experiment_name",
        "one_for_slate_endpoint_per_aggregate",
        "exact_proposal_family_coverage",
        "run_shard_count_equals_one_manifested_mechanics_shard",
        "run_slate_count_equals_explicit_slate_count",
        "reported_run_ledger_count_equals_aggregate_count",
        "exact_manifest_census_and_isolated_node_census",
    ],
    "proposal_families": sorted(PROPOSAL_FAMILIES),
    "proposal_reconciliation_semantics": "reported_consistency_only",
    "verified_reconciliation_requires_complete_raw_status_ledger": True,
    "outcome_evidence_policy": {
        "disposition": "closed",
        "scanned_source_kinds": sorted(LAB_NODE_KINDS - {"Hold"}),
        "denied_text_pattern": OUTCOME_EVIDENCE_PATTERN,
        "camel_case_normalization": "split_lower_to_upper_before_scan",
        "denied_compact_fragments": sorted(OUTCOME_COMPACT_FRAGMENTS),
        "hold_text_class": "governance_blocker_not_evidence",
    },
}
MAPPING_CONTRACT_SHA256: Final = sha256(
    json.dumps(
        MAPPING_CONTRACT, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
).hexdigest()

NODE_CONTROL_HEADERS: Final = frozenset({"id:ID", ":LABEL"})
EDGE_HEADERS: Final = frozenset({":START_ID", ":END_ID", ":TYPE"})
NODE_SOURCE_PROPERTIES: Final = {
    "Question": frozenset({"text", "status", "score_channel", "note"}),
    "Claim": frozenset({"text", "strength"}),
    "Read": frozenset({"prereg", "verdict", "endpoint_era", "class"}),
    "Hold": frozenset({"reason", "releaser"}),
    "Experiment": frozenset({"name"}),
    "Preregistration": frozenset({"file", "amendments"}),
    "ExperimentRun": frozenset({
        "experiment", "code_sha", "image", "shards", "slates",
        "ledger_reconciles", "ledger_violations", "uri",
    }),
    "ProposalAttemptAggregate": frozenset({
        "family", "attempts", "new", "dup", "reconciles",
    }),
    "Slate": frozenset({"season", "week"}),
}
REQUIRED_NODE_SOURCE_PROPERTIES: Final = {
    "Question": frozenset({"text", "status", "score_channel"}),
    "Claim": NODE_SOURCE_PROPERTIES["Claim"],
    "Read": NODE_SOURCE_PROPERTIES["Read"],
    "Hold": NODE_SOURCE_PROPERTIES["Hold"],
    "Experiment": NODE_SOURCE_PROPERTIES["Experiment"],
    "Preregistration": NODE_SOURCE_PROPERTIES["Preregistration"],
    "ExperimentRun": NODE_SOURCE_PROPERTIES["ExperimentRun"],
    "ProposalAttemptAggregate": NODE_SOURCE_PROPERTIES[
        "ProposalAttemptAggregate"
    ],
    "Slate": NODE_SOURCE_PROPERTIES["Slate"],
}
ALL_NODE_SOURCE_PROPERTIES: Final = frozenset().union(
    *NODE_SOURCE_PROPERTIES.values()
)

_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$")
_ROLE: Final = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_DIGEST: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
_INTEGER: Final = re.compile(r"^(0|[1-9][0-9]*)$")
_POSITIVE_INTEGER: Final = re.compile(r"^[1-9][0-9]*$")
_PREREG_REFERENCE: Final = re.compile(r"^PREREG-[0-9]{3}$")
_PREREG_FILE: Final = re.compile(r"^PREREG-[0-9]{3}\.md$")
_UTC: Final = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_OUTCOME_EVIDENCE_TEXT: Final = re.compile(
    OUTCOME_EVIDENCE_PATTERN, re.IGNORECASE
)
_CAMEL_BOUNDARY: Final = re.compile(r"([a-z0-9])([A-Z])")
_NON_ALNUM: Final = re.compile(r"[^A-Za-z0-9]+")


class LabEpistemicsPhaseBError(ValueError):
    """Raised when the bounded lab packet fails closed."""


@dataclass(frozen=True, slots=True)
class LabEpistemicsProjection:
    """Validated logical rows and their compact deterministic authorities."""

    manifest: dict[str, object]
    manifest_identity: dict[str, object]
    governed_manifest: dict[str, object]
    nodes: tuple[dict[str, object], ...]
    relationships: tuple[dict[str, object], ...]
    load_plan: dict[str, object]
    receipt: dict[str, object]


def _fail(message: str) -> None:
    raise LabEpistemicsPhaseBError(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise LabEpistemicsPhaseBError(
            "value is not finite canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _governed_node(value: Mapping[str, object]) -> dict[str, object]:
    try:
        return graph.validate_node_row(value)
    except graph.CorpusGraphVNextError as exc:
        raise LabEpistemicsPhaseBError(
            f"governed node validation failed: {exc}"
        ) from exc


def _governed_edge(value: Mapping[str, object]) -> dict[str, object]:
    try:
        return graph.validate_edge_row(value)
    except graph.CorpusGraphVNextError as exc:
        raise LabEpistemicsPhaseBError(
            f"governed edge validation failed: {exc}"
        ) from exc


def _exact_keys(
    value: Mapping[str, object], *, expected: set[str], label: str,
) -> None:
    if set(value) != expected:
        _fail(
            f"{label} keys differ: missing={sorted(expected - set(value))}, "
            f"extra={sorted(set(value) - expected)}"
        )


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not an object")
    return value


def _sequence(
    value: object, *, label: str, maximum: int, nonempty: bool = False,
) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} is not an array")
    if nonempty and not value:
        _fail(f"{label} is empty")
    if len(value) > maximum:
        _fail(f"{label} exceeds the {maximum} item bound")
    return value


def _string(value: object, *, label: str, maximum: int = MAX_TEXT_BYTES) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} is not a nonempty string")
    if len(value.encode("utf-8")) > maximum:
        _fail(f"{label} exceeds its UTF-8 byte bound")
    return value


def _id(value: object, *, label: str) -> str:
    retained = _string(value, label=label, maximum=200)
    if _ID.fullmatch(retained) is None:
        _fail(f"{label} is not a canonical identifier")
    return retained


def _role(value: object, *, label: str) -> str:
    retained = _string(value, label=label, maximum=64)
    if _ROLE.fullmatch(retained) is None:
        _fail(f"{label} is not a canonical role")
    return retained


def _utc(value: object, *, label: str) -> str:
    retained = _string(value, label=label, maximum=32)
    if _UTC.fullmatch(retained) is None:
        _fail(f"{label} is not second-precision UTC")
    try:
        datetime.strptime(retained, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=UTC
        )
    except ValueError as exc:
        raise LabEpistemicsPhaseBError(
            f"{label} is not a valid UTC timestamp"
        ) from exc
    return retained


def _nonnegative(value: object, *, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail(f"{label} is not a nonnegative integer")
    return value


def _csv_nonnegative(value: str, *, label: str) -> int:
    if _INTEGER.fullmatch(value) is None:
        _fail(f"{label} is not a canonical nonnegative integer")
    return int(value)


def _csv_boolean(value: str, *, label: str) -> bool:
    if value == "true":
        return True
    if value == "false":
        return False
    _fail(f"{label} is not canonical true/false")


def _gcs_location(value: object, *, label: str) -> str:
    uri = _string(value, label=label, maximum=2_048)
    uri_remainder = uri[5:] if uri.startswith("gs://") else ""
    bucket_name, separator, object_name = uri_remainder.partition("/")
    if (
        not uri.startswith("gs://")
        or not bucket_name
        or separator != "/"
        or not object_name
        or any(character.isspace() or ord(character) < 32 for character in uri)
    ):
        _fail(f"{label} is not a canonical gs:// location")
    return uri


def _contains_outcome_evidence(value: str) -> bool:
    expanded = _CAMEL_BOUNDARY.sub(r"\1 \2", value)
    if _OUTCOME_EVIDENCE_TEXT.search(expanded) is not None:
        return True
    compact = _NON_ALNUM.sub("", expanded).lower()
    return any(fragment in compact for fragment in OUTCOME_COMPACT_FRAGMENTS)


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = dict(_mapping(value, label=label))
    _exact_keys(
        item, expected=set(IDENTITY_FIELDS), label=label
    )
    uri = _gcs_location(item["uri"], label=f"{label}.uri")
    generation = _string(
        item["generation"], label=f"{label}.generation", maximum=32
    )
    if _POSITIVE_INTEGER.fullmatch(generation) is None:
        _fail(f"{label}.generation is not positive digits")
    digest = _string(item["sha256"], label=f"{label}.sha256", maximum=64)
    if _SHA256.fullmatch(digest) is None:
        _fail(f"{label}.sha256 is not 64-hex")
    byte_count = item["bytes"]
    if type(byte_count) is not int or not 0 < byte_count <= (1 << 63) - 1:
        _fail(f"{label}.bytes is not a bounded positive integer")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": byte_count,
    }


def object_identity(uri: str, generation: str, raw: bytes) -> dict[str, object]:
    """Build an exact identity for already supplied bytes; performs no read."""
    if type(raw) is not bytes or not raw:
        _fail("identity body must be nonempty bytes")
    return _identity(
        {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        },
        label="object identity",
    )


def _count_map(
    value: object,
    *,
    label: str,
    allowed: frozenset[str],
    exact_keys: bool,
) -> dict[str, int]:
    item = dict(_mapping(value, label=label))
    if exact_keys and set(item) != set(allowed):
        _fail(f"{label} coverage differs")
    if not set(item) <= set(allowed):
        _fail(f"{label} contains unknown keys")
    result: dict[str, int] = {}
    for key, count in item.items():
        if not isinstance(key, str):
            _fail(f"{label} key is not a string")
        result[key] = _nonnegative(count, label=f"{label}.{key}")
    return dict(sorted(result.items()))


def _expected_census(value: object) -> dict[str, object]:
    item = dict(_mapping(value, label="expected census"))
    _exact_keys(
        item,
        expected={
            "artifact_row_counts", "node_kind_counts",
            "relationship_type_counts", "isolated_node_kind_counts",
            "ledger_totals",
        },
        label="expected census",
    )
    artifact_counts = _count_map(
        item["artifact_row_counts"],
        label="expected artifact row counts",
        allowed=ARTIFACT_ROLES,
        exact_keys=True,
    )
    node_counts = _count_map(
        item["node_kind_counts"],
        label="expected node kind counts",
        allowed=LAB_NODE_KINDS,
        exact_keys=True,
    )
    relationship_counts = _count_map(
        item["relationship_type_counts"],
        label="expected relationship type counts",
        allowed=LAB_RELATIONSHIPS,
        exact_keys=True,
    )
    isolated_counts = _count_map(
        item["isolated_node_kind_counts"],
        label="expected isolated node kind counts",
        allowed=LAB_NODE_KINDS,
        exact_keys=False,
    )
    ledger = dict(_mapping(item["ledger_totals"], label="expected ledger totals"))
    ledger_keys = (
        "reported_attempts", "reported_new", "reported_duplicate",
        "reported_reconciles", "reported_violations",
        "verified_reconciliations",
    )
    _exact_keys(ledger, expected=set(ledger_keys), label="expected ledger totals")
    normalized_ledger = {
        key: _nonnegative(ledger[key], label=f"expected ledger totals.{key}")
        for key in ledger_keys
    }
    if normalized_ledger["reported_attempts"] != (
        normalized_ledger["reported_new"]
        + normalized_ledger["reported_duplicate"]
    ):
        _fail("expected reported proposal ledger is internally inconsistent")
    if (
        normalized_ledger["reported_violations"] != 0
        or normalized_ledger["verified_reconciliations"] != 0
    ):
        _fail("Phase B may not claim verified proposal reconciliation")
    if (
        artifact_counts["base_nodes"] + artifact_counts["run_nodes"]
        != sum(node_counts.values())
        or artifact_counts["base_edges"] + artifact_counts["run_edges"]
        != sum(relationship_counts.values())
        or normalized_ledger["reported_reconciles"]
        != node_counts["ProposalAttemptAggregate"]
    ):
        _fail("expected census totals do not reconcile")
    return {
        "artifact_row_counts": artifact_counts,
        "node_kind_counts": node_counts,
        "relationship_type_counts": relationship_counts,
        "isolated_node_kind_counts": isolated_counts,
        "ledger_totals": normalized_ledger,
    }


def _source_entries(value: object) -> list[dict[str, object]]:
    rows = _sequence(value, label="sources", maximum=64, nonempty=True)
    result: list[dict[str, object]] = []
    seen_roles: set[str] = set()
    for index, raw in enumerate(rows):
        item = dict(_mapping(raw, label=f"sources[{index}]"))
        _exact_keys(
            item,
            expected={
                "role", "identity", "evidence_class",
                "contains_realized_evidence", "contains_winner_evidence",
                "contains_settlement_evidence",
            },
            label=f"sources[{index}]",
        )
        role = _role(item["role"], label=f"sources[{index}].role")
        if role in seen_roles:
            _fail(f"source role {role!r} repeats")
        seen_roles.add(role)
        evidence_class = _string(
            item["evidence_class"], label=f"sources[{index}].evidence_class",
            maximum=64,
        )
        if evidence_class not in SOURCE_EVIDENCE_CLASSES:
            _fail(f"source role {role!r} has a closed evidence class")
        if SOURCE_ROLE_EVIDENCE_CLASS.get(role) != evidence_class:
            _fail(f"source role {role!r} evidence class differs")
        for key in (
            "contains_realized_evidence", "contains_winner_evidence",
            "contains_settlement_evidence",
        ):
            if item[key] is not False:
                _fail(
                    f"source role {role!r} carries {key}; a separately bound "
                    "authorized evidence contract is required"
                )
        result.append({
            "role": role,
            "identity": _identity(
                item["identity"], label=f"sources[{index}].identity"
            ),
            "evidence_class": evidence_class,
            "contains_realized_evidence": False,
            "contains_winner_evidence": False,
            "contains_settlement_evidence": False,
        })
    if seen_roles != set(REQUIRED_SOURCE_ROLES):
        _fail("required source role coverage differs")
    return sorted(result, key=lambda row: str(row["role"]))


def _artifact_entries(
    value: object, *, source_roles: frozenset[str],
) -> list[dict[str, object]]:
    rows = _sequence(
        value, label="artifacts", maximum=len(ARTIFACT_ROLES), nonempty=True
    )
    result: list[dict[str, object]] = []
    seen_roles: set[str] = set()
    used_sources: set[str] = set()
    for index, raw in enumerate(rows):
        item = dict(_mapping(raw, label=f"artifacts[{index}]"))
        _exact_keys(
            item,
            expected={"role", "row_kind", "format", "identity", "source_roles"},
            label=f"artifacts[{index}]",
        )
        role = _role(item["role"], label=f"artifacts[{index}].role")
        if role not in ARTIFACT_ROLES or role in seen_roles:
            _fail(f"artifact role {role!r} is unknown or repeated")
        seen_roles.add(role)
        row_kind = _string(
            item["row_kind"], label=f"artifacts[{index}].row_kind", maximum=16
        )
        expected_kind = "nodes" if role in NODE_ARTIFACT_ROLES else "edges"
        if row_kind != expected_kind or item["format"] != ARTIFACT_FORMAT:
            _fail(f"artifact role {role!r} contract differs")
        role_values = _sequence(
            item["source_roles"],
            label=f"artifacts[{index}].source_roles",
            maximum=16,
            nonempty=True,
        )
        normalized_roles = [
            _role(source_role, label=f"artifacts[{index}].source_roles")
            for source_role in role_values
        ]
        if len(set(normalized_roles)) != len(normalized_roles):
            _fail(f"artifact role {role!r} repeats a source role")
        if not set(normalized_roles) <= set(source_roles):
            _fail(f"artifact role {role!r} references an absent source")
        if set(normalized_roles) != set(ARTIFACT_SOURCE_ROLES[role]):
            _fail(f"artifact role {role!r} source binding differs")
        used_sources.update(normalized_roles)
        result.append({
            "role": role,
            "row_kind": row_kind,
            "format": ARTIFACT_FORMAT,
            "identity": _identity(
                item["identity"], label=f"artifacts[{index}].identity"
            ),
            "source_roles": sorted(normalized_roles),
        })
    if seen_roles != set(ARTIFACT_ROLES):
        _fail("artifact role coverage differs")
    if used_sources != set(source_roles):
        _fail("one or more manifested sources are not bound to an artifact")
    return sorted(result, key=lambda row: str(row["role"]))


def _validate_identity_set(
    artifacts: Sequence[Mapping[str, object]],
    sources: Sequence[Mapping[str, object]],
    *,
    additional_identities: Sequence[Mapping[str, object]] = (),
) -> None:
    exact_seen: set[tuple[str, str, str, int]] = set()
    object_seen: set[tuple[str, str]] = set()
    identities = [
        *[row["identity"] for row in (*artifacts, *sources)],
        *additional_identities,
    ]
    for raw in identities:
        identity = _mapping(raw, label="content identity")
        exact = content_identity(identity)
        object_key = exact[:2]
        if exact in exact_seen:
            _fail("artifact/source content identities repeat")
        if object_key in object_seen:
            _fail("artifact/source object identity conflicts")
        exact_seen.add(exact)
        object_seen.add(object_key)


def validate_release_manifest(value: object) -> dict[str, object]:
    item = dict(_mapping(value, label="Phase-B release manifest"))
    required = {
        "schema_version", "graph_schema_version", "graph_release_id",
        "created_at_utc", "artifacts", "sources", "expected_census",
        "authorized_evidence_identity", "authority_flags",
        "content_set_sha256", "mapping_schema_version",
        "mapping_contract_sha256", "manifest_sha256",
    }
    _exact_keys(item, expected=required, label="Phase-B release manifest")
    if item["schema_version"] != MANIFEST_SCHEMA:
        _fail("Phase-B release manifest schema differs")
    if item["graph_schema_version"] != graph.GRAPH_SCHEMA_VERSION:
        _fail("Phase-B graph schema binding differs")
    if (
        item["mapping_schema_version"] != MAPPING_SCHEMA_VERSION
        or item["mapping_contract_sha256"] != MAPPING_CONTRACT_SHA256
    ):
        _fail("Phase-B mapping contract binding differs")
    graph_release_id = _id(item["graph_release_id"], label="graph_release_id")
    created_at_utc = _utc(item["created_at_utc"], label="created_at_utc")
    sources = _source_entries(item["sources"])
    source_roles = frozenset(str(row["role"]) for row in sources)
    artifacts = _artifact_entries(item["artifacts"], source_roles=source_roles)
    _validate_identity_set(artifacts, sources)
    expected = _expected_census(item["expected_census"])
    if item["authorized_evidence_identity"] is not None:
        _identity(
            item["authorized_evidence_identity"],
            label="authorized_evidence_identity",
        )
        _fail(
            "Phase B cannot open realized/winner/settlement evidence; a "
            "separately reviewed later schema is required"
        )
    flags = dict(_mapping(item["authority_flags"], label="authority flags"))
    if (
        set(flags) != set(AUTHORITY_FLAGS)
        or any(flags[key] is not False for key in AUTHORITY_FLAGS)
    ):
        _fail("Phase-B authority flags differ")
    content_body = {"artifacts": artifacts, "sources": sources}
    content_digest = _string(
        item["content_set_sha256"], label="content_set_sha256", maximum=64
    )
    if (
        _SHA256.fullmatch(content_digest) is None
        or content_digest != canonical_sha256(content_body)
    ):
        _fail("content_set_sha256 differs")
    body: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA,
        "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
        "graph_release_id": graph_release_id,
        "created_at_utc": created_at_utc,
        "artifacts": artifacts,
        "sources": sources,
        "expected_census": expected,
        "authorized_evidence_identity": None,
        "authority_flags": dict(AUTHORITY_FLAGS),
        "content_set_sha256": content_digest,
        "mapping_schema_version": MAPPING_SCHEMA_VERSION,
        "mapping_contract_sha256": MAPPING_CONTRACT_SHA256,
    }
    expected_hash = canonical_sha256(body)
    retained_hash = _string(
        item["manifest_sha256"], label="manifest_sha256", maximum=64
    )
    if _SHA256.fullmatch(retained_hash) is None or retained_hash != expected_hash:
        _fail("manifest_sha256 differs")
    return {**body, "manifest_sha256": expected_hash}


def build_release_manifest(
    *,
    graph_release_id: str,
    created_at_utc: str,
    artifacts: Sequence[Mapping[str, object]],
    sources: Sequence[Mapping[str, object]],
    expected_census: Mapping[str, object],
) -> dict[str, object]:
    """Build and validate the complete source/content manifest."""
    sources_normalized = _source_entries(sources)
    artifacts_normalized = _artifact_entries(
        artifacts,
        source_roles=frozenset(
            str(row["role"]) for row in sources_normalized
        ),
    )
    candidate = {
        "schema_version": MANIFEST_SCHEMA,
        "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
        "graph_release_id": graph_release_id,
        "created_at_utc": created_at_utc,
        "artifacts": artifacts_normalized,
        "sources": sources_normalized,
        "expected_census": dict(
            _mapping(expected_census, label="expected census")
        ),
        "authorized_evidence_identity": None,
        "authority_flags": dict(AUTHORITY_FLAGS),
        "content_set_sha256": canonical_sha256({
            "artifacts": artifacts_normalized,
            "sources": sources_normalized,
        }),
        "mapping_schema_version": MAPPING_SCHEMA_VERSION,
        "mapping_contract_sha256": MAPPING_CONTRACT_SHA256,
    }
    candidate["manifest_sha256"] = canonical_sha256(candidate)
    return validate_release_manifest(candidate)


def _parse_canonical_manifest(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_MANIFEST_BYTES:
        _fail("manifest body is not bounded nonempty bytes")

    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                _fail(f"manifest contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        _fail(f"manifest contains nonfinite constant {value}")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except LabEpistemicsPhaseBError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LabEpistemicsPhaseBError(
            "manifest is not valid UTF-8 JSON"
        ) from exc
    item = dict(_mapping(value, label="manifest"))
    if canonical_json_bytes(item) != raw:
        _fail("manifest bytes are not canonical JSON")
    return validate_release_manifest(item)


def _verify_body(raw: object, identity: Mapping[str, object], *, label: str) -> bytes:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_ARTIFACT_BYTES:
        _fail(f"{label} body is not bounded nonempty bytes")
    if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
        _fail(f"{label} content identity differs")
    return raw


def _csv_rows(raw: bytes, *, role: str) -> tuple[list[dict[str, str]], list[str]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LabEpistemicsPhaseBError(
            f"{role} is not valid UTF-8 CSV"
        ) from exc
    if "\x00" in text:
        _fail(f"{role} contains NUL")
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    headers = reader.fieldnames
    if headers is None or any(not isinstance(header, str) for header in headers):
        _fail(f"{role} has no valid CSV header")
    if len(set(headers)) != len(headers):
        _fail(f"{role} CSV headers repeat")
    expected_controls = NODE_CONTROL_HEADERS if role in NODE_ARTIFACT_ROLES else EDGE_HEADERS
    if role in NODE_ARTIFACT_ROLES:
        if not NODE_CONTROL_HEADERS <= set(headers):
            _fail(f"{role} node control headers differ")
        unknown = set(headers) - NODE_CONTROL_HEADERS - ALL_NODE_SOURCE_PROPERTIES
        if unknown:
            _fail(f"{role} has ungoverned node columns {sorted(unknown)}")
    elif set(headers) != set(EDGE_HEADERS):
        _fail(f"{role} edge headers differ")
    if not expected_controls <= set(headers):
        _fail(f"{role} control headers differ")
    rows: list[dict[str, str]] = []
    try:
        for ordinal, raw_row in enumerate(reader):
            if ordinal >= MAX_ROWS_PER_ARTIFACT:
                _fail(f"{role} exceeds the row bound")
            if None in raw_row or any(value is None for value in raw_row.values()):
                _fail(f"{role} row {ordinal} has a malformed column count")
            row = {str(key): str(value) for key, value in raw_row.items()}
            if not any(row.values()):
                _fail(f"{role} row {ordinal} is blank")
            rows.append(row)
    except csv.Error as exc:
        raise LabEpistemicsPhaseBError(f"{role} CSV is malformed") from exc
    return rows, headers


def _properties_for_node(
    *, source_id: str, kind: str, values: Mapping[str, str], ordinal: int,
) -> dict[str, object]:
    label = f"{kind} {source_id} at row {ordinal}"
    if any(
        value != "" and (not value.strip() or value != value.strip())
        for value in values.values()
    ):
        _fail(f"{label} contains a noncanonical whitespace-only/padded value")
    nonblank = {key: value for key, value in values.items() if value != ""}
    unknown = set(nonblank) - set(NODE_SOURCE_PROPERTIES[kind])
    missing = set(REQUIRED_NODE_SOURCE_PROPERTIES[kind]) - set(nonblank)
    if unknown or missing:
        _fail(
            f"{label} property coverage differs: missing={sorted(missing)}, "
            f"extra={sorted(unknown)}"
        )
    if kind != "Hold" and any(
        _contains_outcome_evidence(value)
        for value in nonblank.values()
    ):
        _fail(
            f"{label} contains realized/winner/settlement evidence text; a "
            "separately bound authorized evidence contract is required"
        )
    if kind == "Question":
        result = {
            "source_id": source_id,
            "text": nonblank["text"],
            "status": nonblank["status"],
            "decision_channel": nonblank["score_channel"],
        }
        if "note" in nonblank:
            result["note"] = nonblank["note"]
        return result
    if kind == "Claim":
        return {
            "source_id": source_id,
            "text": nonblank["text"],
            "strength": nonblank["strength"],
        }
    if kind == "Read":
        if _PREREG_REFERENCE.fullmatch(nonblank["prereg"]) is None:
            _fail(f"{label}.prereg is not a canonical preregistration reference")
        return {
            "source_id": source_id,
            "preregistration_reference": nonblank["prereg"],
            "verdict": nonblank["verdict"],
            "endpoint_era": nonblank["endpoint_era"],
            "evidence_class": nonblank["class"],
        }
    if kind == "Hold":
        return {
            "source_id": source_id,
            "reason": nonblank["reason"],
            "releaser": nonblank["releaser"],
        }
    if kind == "Experiment":
        return {"source_id": source_id, "name": nonblank["name"]}
    if kind == "Preregistration":
        if _PREREG_FILE.fullmatch(nonblank["file"]) is None:
            _fail(f"{label}.file is not a canonical preregistration file")
        return {
            "source_id": source_id,
            "file_name": nonblank["file"],
            "amendment_count": _csv_nonnegative(
                nonblank["amendments"], label=f"{label}.amendments"
            ),
        }
    if kind == "ExperimentRun":
        code_commit = nonblank["code_sha"]
        image_digest = nonblank["image"]
        artifact_uri = _gcs_location(
            nonblank["uri"], label=f"{label}.uri"
        )
        run_id = source_id.removeprefix("run:")
        if _GIT_SHA.fullmatch(code_commit) is None:
            _fail(f"{label}.code_sha is not an exact Git commit")
        if _IMAGE_DIGEST.fullmatch(image_digest) is None:
            _fail(f"{label}.image is not an immutable sha256 digest")
        expected_suffix = f"/{nonblank['experiment']}/{run_id}/"
        if not artifact_uri.endswith(expected_suffix):
            _fail(
                f"{label}.uri is not bound to its experiment and run ID"
            )
        return {
            "source_id": source_id,
            "run_id": run_id,
            "experiment_name": nonblank["experiment"],
            "code_commit": code_commit,
            "image_digest": image_digest,
            "shard_count": _csv_nonnegative(
                nonblank["shards"], label=f"{label}.shards"
            ),
            "slate_count": _csv_nonnegative(
                nonblank["slates"], label=f"{label}.slates"
            ),
            "reported_reconciled_ledger_count": _csv_nonnegative(
                nonblank["ledger_reconciles"],
                label=f"{label}.ledger_reconciles",
            ),
            "reported_ledger_violation_count": _csv_nonnegative(
                nonblank["ledger_violations"],
                label=f"{label}.ledger_violations",
            ),
            "source_prefix_uri": artifact_uri,
            "verification_status": "reported_unverified",
        }
    if kind == "ProposalAttemptAggregate":
        return {
            "source_id": source_id,
            "family": nonblank["family"],
            "reported_attempt_count": _csv_nonnegative(
                nonblank["attempts"], label=f"{label}.attempts"
            ),
            "reported_new_count": _csv_nonnegative(
                nonblank["new"], label=f"{label}.new"
            ),
            "reported_duplicate_count": _csv_nonnegative(
                nonblank["dup"], label=f"{label}.dup"
            ),
            "reported_reconciles": _csv_boolean(
                nonblank["reconciles"], label=f"{label}.reconciles"
            ),
            "reconciliation_verified": False,
        }
    if kind == "Slate":
        return {
            "source_id": source_id,
            "season": _csv_nonnegative(
                nonblank["season"], label=f"{label}.season"
            ),
            "week": _csv_nonnegative(nonblank["week"], label=f"{label}.week"),
        }
    _fail(f"unhandled lab node kind {kind}")


def _project_node_rows(
    rows: Sequence[Mapping[str, str]], *, role: str,
) -> tuple[list[dict[str, object]], dict[str, str], dict[str, str]]:
    allowed_kinds = BASE_NODE_KINDS if role == "base_nodes" else RUN_NODE_KINDS
    result: list[dict[str, object]] = []
    source_to_production: dict[str, str] = {}
    source_kinds: dict[str, str] = {}
    for ordinal, row in enumerate(rows):
        source_id = _id(row["id:ID"], label=f"{role} row {ordinal} id")
        kind = _string(row[":LABEL"], label=f"{role} row {ordinal} label", maximum=64)
        if kind not in allowed_kinds:
            _fail(f"{role} row {ordinal} kind {kind!r} is outside its contract")
        prefix = LAB_NODE_ID_PREFIX[kind]
        if not source_id.startswith(prefix) or len(source_id) == len(prefix):
            _fail(f"{role} row {ordinal} ID prefix differs for {kind}")
        if source_id in source_to_production:
            _fail(f"lab node ID {source_id!r} repeats")
        values = {
            key: value for key, value in row.items() if key not in NODE_CONTROL_HEADERS
        }
        properties = _properties_for_node(
            source_id=source_id,
            kind=kind,
            values=values,
            ordinal=ordinal,
        )
        production_id = f"lab:{source_id}"
        source_to_production[source_id] = production_id
        source_kinds[source_id] = kind
        production_kind = PRODUCTION_NODE_KIND[kind]
        result.append(_governed_node({
            "kind": production_kind,
            "node_id": production_id,
            "namespace": PRODUCTION_NODE_NAMESPACE[production_kind],
            "properties": properties,
        }))
    return result, source_to_production, source_kinds


def _project_edge_rows(
    rows: Sequence[Mapping[str, str]],
    *,
    role: str,
    source_to_production: Mapping[str, str],
    node_kinds: Mapping[str, str],
) -> list[dict[str, object]]:
    allowed_relationships = (
        BASE_RELATIONSHIPS if role == "base_edges" else RUN_RELATIONSHIPS
    )
    result: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for ordinal, row in enumerate(rows):
        source = _id(row[":START_ID"], label=f"{role} row {ordinal} source")
        target = _id(row[":END_ID"], label=f"{role} row {ordinal} target")
        relationship = _string(
            row[":TYPE"], label=f"{role} row {ordinal} type", maximum=64
        )
        if relationship not in allowed_relationships:
            _fail(f"{role} row {ordinal} relationship is outside its contract")
        if source not in source_to_production or target not in source_to_production:
            _fail(f"{role} row {ordinal} has a dangling endpoint")
        pair = (node_kinds[source], node_kinds[target])
        if pair not in RELATIONSHIP_ENDPOINT_KINDS[relationship]:
            _fail(
                f"{role} row {ordinal} endpoint kinds {pair} are invalid for "
                f"{relationship}"
            )
        logical_key = (source, relationship, target)
        if logical_key in seen:
            _fail(f"{role} repeats relationship {logical_key}")
        seen.add(logical_key)
        production_relationship = PRODUCTION_RELATIONSHIP[
            (pair[0], relationship, pair[1])
        ]
        result.append(_governed_edge({
            "relationship": production_relationship,
            "source_id": source_to_production[source],
            "target_id": source_to_production[target],
            "namespace": PRODUCTION_RELATIONSHIP_NAMESPACE[
                production_relationship
            ],
            "properties": {},
        }))
    return result


def _nonzero_counts(values: Sequence[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _production_kind_counts(
    nodes: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    counts = Counter(str(node["kind"]) for node in nodes)
    return {kind: counts[kind] for kind in sorted(PRODUCTION_NODE_KINDS)}


def _production_relationship_counts(
    relationships: Sequence[Mapping[str, object]],
) -> dict[str, int]:
    counts = Counter(str(edge["relationship"]) for edge in relationships)
    return {
        relationship: counts[relationship]
        for relationship in sorted(PRODUCTION_RELATIONSHIPS)
    }


def _reconcile_semantics(
    nodes: Sequence[Mapping[str, object]],
    relationships: Sequence[Mapping[str, object]],
    *,
    expected: Mapping[str, object],
    source_kind_by_production_id: Mapping[str, str],
) -> tuple[dict[str, int], dict[str, int]]:
    nodes_by_id = {str(node["node_id"]): node for node in nodes}
    degree: Counter[str] = Counter()
    outgoing: dict[tuple[str, str], list[Mapping[str, object]]] = {}
    for edge in relationships:
        source_id = str(edge["source_id"])
        target_id = str(edge["target_id"])
        degree[source_id] += 1
        degree[target_id] += 1
        outgoing.setdefault(
            (source_id, str(edge["relationship"])), []
        ).append(edge)

    claims = [node for node in nodes if node["kind"] == "Claim"]
    if any(not outgoing.get((str(node["node_id"]), "EVIDENCED_BY")) for node in claims):
        _fail("one or more claims lack explicit evidence endpoints")

    preregistration_references = {
        str(node["properties"]["file_name"]).removesuffix(".md")
        for node in nodes
        if node["kind"] == "Preregistration"
    }
    preregistration_count = sum(
        node["kind"] == "Preregistration" for node in nodes
    )
    if len(preregistration_references) != preregistration_count:
        _fail("preregistration file references repeat")
    reads = [node for node in nodes if node["kind"] == "Read"]
    if any(
        str(node["properties"]["preregistration_reference"])
        not in preregistration_references
        for node in reads
    ):
        _fail("one or more Read preregistration references are unresolved")

    runs = [node for node in nodes if node["kind"] == "RunObservation"]
    slates = [node for node in nodes if node["kind"] == "Slate"]
    aggregates = [
        node for node in nodes if node["kind"] == "ProposalAttemptAggregate"
    ]
    if len(runs) != 1 or len(slates) != 1 or not aggregates:
        _fail("Phase-B run slice must contain one run, one slate, and ledgers")
    families: list[str] = []
    for aggregate in aggregates:
        properties = _mapping(
            aggregate["properties"], label="proposal aggregate properties"
        )
        families.append(str(properties["family"]))
        if (
            properties["reported_reconciles"] is not True
            or properties["reported_attempt_count"]
            != properties["reported_new_count"]
            + properties["reported_duplicate_count"]
            or properties["reconciliation_verified"] is not False
        ):
            _fail("proposal-attempt aggregate reported consistency differs")
        edges = outgoing.get((str(aggregate["node_id"]), "FOR_SLATE"), [])
        if len(edges) != 1 or nodes_by_id[str(edges[0]["target_id"])]["kind"] != "Slate":
            _fail("proposal-attempt aggregate lacks one explicit Slate endpoint")
    if len(set(families)) != len(families) or set(families) != set(PROPOSAL_FAMILIES):
        _fail("proposal-attempt aggregate family coverage differs")
    run = runs[0]
    run_edges = outgoing.get((str(run["node_id"]), "RUN_OF"), [])
    if (
        len(run_edges) != 1
        or nodes_by_id[str(run_edges[0]["target_id"])]["kind"]
        != "ExperimentDefinition"
    ):
        _fail("ExperimentRun lacks one explicit Experiment endpoint")
    run_properties = _mapping(run["properties"], label="run properties")
    experiment_properties = _mapping(
        nodes_by_id[str(run_edges[0]["target_id"])]["properties"],
        label="ExperimentDefinition properties",
    )
    if (
        run_properties["experiment_name"] != experiment_properties["name"]
        or run_properties["shard_count"] != 1
        or run_properties["slate_count"] != len(slates)
        or run_properties["reported_reconciled_ledger_count"] != len(aggregates)
        or run_properties["reported_ledger_violation_count"] != 0
    ):
        _fail("ExperimentRun endpoint, shard, slate, or ledger does not reconcile")

    ledger_totals = {
        "reported_attempts": sum(
            int(node["properties"]["reported_attempt_count"])
            for node in aggregates
        ),
        "reported_new": sum(
            int(node["properties"]["reported_new_count"])
            for node in aggregates
        ),
        "reported_duplicate": sum(
            int(node["properties"]["reported_duplicate_count"])
            for node in aggregates
        ),
        "reported_reconciles": sum(
            node["properties"]["reported_reconciles"] is True
            for node in aggregates
        ),
        "reported_violations": sum(
            node["properties"]["reported_reconciles"] is not True
            or node["properties"]["reported_attempt_count"]
            != node["properties"]["reported_new_count"]
            + node["properties"]["reported_duplicate_count"]
            for node in aggregates
        ),
        "verified_reconciliations": 0,
    }
    if ledger_totals != expected["ledger_totals"]:
        _fail("proposal ledger totals differ from the manifest")
    isolated = _nonzero_counts([
        source_kind_by_production_id[str(node["node_id"])]
        for node in nodes
        if degree[str(node["node_id"])] == 0
    ])
    if isolated != expected["isolated_node_kind_counts"]:
        _fail("isolated-node census differs from the manifest")
    return ledger_totals, isolated


def project_lab_packet(
    *,
    manifest_raw: bytes,
    manifest_identity: Mapping[str, object],
    artifact_bodies: Mapping[str, bytes],
) -> LabEpistemicsProjection:
    """Validate exact supplied bytes and build the offline Phase-B projection."""
    if type(manifest_raw) is not bytes:
        _fail("manifest body is not bytes")
    if not isinstance(artifact_bodies, Mapping):
        _fail("artifact_bodies is not a role-to-bytes mapping")
    normalized_manifest_identity = _identity(
        manifest_identity, label="manifest identity"
    )
    if (
        len(manifest_raw) != normalized_manifest_identity["bytes"]
        or sha256(manifest_raw).hexdigest()
        != normalized_manifest_identity["sha256"]
    ):
        _fail("manifest content identity differs")
    manifest = _parse_canonical_manifest(manifest_raw)
    _validate_identity_set(
        manifest["artifacts"],
        manifest["sources"],
        additional_identities=(normalized_manifest_identity,),
    )
    if set(artifact_bodies) != set(ARTIFACT_ROLES):
        _fail("supplied artifact body roles differ")
    artifact_by_role = {
        str(item["role"]): item for item in manifest["artifacts"]
    }
    parsed: dict[str, list[dict[str, str]]] = {}
    artifact_row_counts: dict[str, int] = {}
    for role in sorted(ARTIFACT_ROLES):
        artifact = artifact_by_role[role]
        raw = _verify_body(
            artifact_bodies[role],
            _mapping(artifact["identity"], label=f"{role} identity"),
            label=role,
        )
        rows, _ = _csv_rows(raw, role=role)
        parsed[role] = rows
        artifact_row_counts[role] = len(rows)

    nodes: list[dict[str, object]] = []
    source_to_production: dict[str, str] = {}
    source_node_kinds: dict[str, str] = {}
    for role in ("base_nodes", "run_nodes"):
        role_nodes, role_mapping, role_kinds = _project_node_rows(
            parsed[role], role=role
        )
        overlap = set(source_to_production) & set(role_mapping)
        if overlap:
            _fail(f"lab node IDs repeat across artifacts: {sorted(overlap)}")
        nodes.extend(role_nodes)
        source_to_production.update(role_mapping)
        source_node_kinds.update(role_kinds)

    relationships: list[dict[str, object]] = []
    logical_edge_keys: set[str] = set()
    for role in ("base_edges", "run_edges"):
        role_edges = _project_edge_rows(
            parsed[role],
            role=role,
            source_to_production=source_to_production,
            node_kinds=source_node_kinds,
        )
        overlap = logical_edge_keys & {
            str(edge["edge_key"]) for edge in role_edges
        }
        if overlap:
            _fail("relationships repeat across artifacts")
        logical_edge_keys.update(str(edge["edge_key"]) for edge in role_edges)
        relationships.extend(role_edges)

    nodes.sort(key=lambda row: (str(row["kind"]), str(row["node_id"])))
    relationships.sort(key=lambda row: str(row["edge_key"]))
    expected = _mapping(manifest["expected_census"], label="expected census")
    source_node_counts_counter = Counter(
        row[":LABEL"] for role in ("base_nodes", "run_nodes") for row in parsed[role]
    )
    source_relationship_counts_counter = Counter(
        row[":TYPE"] for role in ("base_edges", "run_edges") for row in parsed[role]
    )
    source_node_counts = {
        kind: source_node_counts_counter[kind] for kind in sorted(LAB_NODE_KINDS)
    }
    source_relationship_counts = {
        relationship: source_relationship_counts_counter[relationship]
        for relationship in sorted(LAB_RELATIONSHIPS)
    }
    production_node_counts = _production_kind_counts(nodes)
    production_relationship_counts = _production_relationship_counts(
        relationships
    )
    if artifact_row_counts != expected["artifact_row_counts"]:
        _fail("artifact row census differs from the manifest")
    if source_node_counts != expected["node_kind_counts"]:
        _fail("node kind census differs from the manifest")
    if source_relationship_counts != expected["relationship_type_counts"]:
        _fail("relationship type census differs from the manifest")
    source_kind_by_production_id = {
        production_id: source_node_kinds[source_id]
        for source_id, production_id in source_to_production.items()
    }
    ledger_totals, isolated_counts = _reconcile_semantics(
        nodes,
        relationships,
        expected=expected,
        source_kind_by_production_id=source_kind_by_production_id,
    )

    all_identities = [
        item["identity"] for item in (*manifest["artifacts"], *manifest["sources"])
    ]
    try:
        governed_manifest = graph.validate_load_manifest({
            "schema_version": graph.LOAD_MANIFEST_SCHEMA,
            "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
            "graph_release_id": manifest["graph_release_id"],
            "predecessor_graph_release_id": None,
            "allowed_namespaces": ["epistemic", "identity", "lineage"],
            "source_releases": all_identities,
            "authorized_outcome_release_id": None,
            "created_at_utc": manifest["created_at_utc"],
        })
        load_plan = graph.build_load_plan(
            manifest=governed_manifest,
            node_rows=nodes,
            edge_rows=[
                {key: value for key, value in edge.items() if key != "edge_key"}
                for edge in relationships
            ],
        )
    except graph.CorpusGraphVNextError as exc:
        raise LabEpistemicsPhaseBError(
            f"governed load-plan validation failed: {exc}"
        ) from exc
    id_mapping = [
        {"source_id": source_id, "production_id": production_id}
        for source_id, production_id in sorted(source_to_production.items())
    ]
    projection_body: dict[str, object] = {
        "schema_version": PROJECTION_SCHEMA,
        "manifest_sha256": manifest["manifest_sha256"],
        "manifest_identity": normalized_manifest_identity,
        "mapping_schema_version": MAPPING_SCHEMA_VERSION,
        "mapping_contract_sha256": MAPPING_CONTRACT_SHA256,
        "governed_manifest_sha256": governed_manifest["manifest_sha256"],
        "load_plan_sha256": load_plan["plan_sha256"],
        "node_count": len(nodes),
        "relationship_count": len(relationships),
        "id_mapping_count": len(id_mapping),
        "id_mapping_sha256": canonical_sha256(id_mapping),
    }
    projection_sha256 = canonical_sha256(projection_body)
    receipt_body: dict[str, object] = {
        "schema_version": RECEIPT_SCHEMA,
        "projection_schema_version": PROJECTION_SCHEMA,
        "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
        "graph_release_id": manifest["graph_release_id"],
        "manifest_identity": normalized_manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "content_set_sha256": manifest["content_set_sha256"],
        "mapping_schema_version": MAPPING_SCHEMA_VERSION,
        "mapping_contract_sha256": MAPPING_CONTRACT_SHA256,
        "projection_sha256": projection_sha256,
        "governed_manifest_sha256": governed_manifest["manifest_sha256"],
        "load_plan_sha256": load_plan["plan_sha256"],
        "artifact_row_counts": artifact_row_counts,
        "node_count": len(nodes),
        "relationship_count": len(relationships),
        "source_node_kind_counts": source_node_counts,
        "source_relationship_type_counts": source_relationship_counts,
        "production_node_kind_counts": production_node_counts,
        "production_relationship_type_counts": production_relationship_counts,
        "isolated_node_count": sum(isolated_counts.values()),
        "isolated_node_kind_counts": isolated_counts,
        "dangling_endpoint_count": 0,
        "invalid_endpoint_kind_pair_count": 0,
        "claims_without_evidence_count": 0,
        "unresolved_preregistration_reference_count": 0,
        "reported_proposal_ledger_totals": ledger_totals,
        "verified_proposal_reconciliation_count": 0,
        "id_mapping_count": len(id_mapping),
        "id_mapping_sha256": canonical_sha256(id_mapping),
        "artifact_bodies_content_verified": True,
        "source_bodies_content_verified": False,
        "artifact_source_derivation_verified": False,
        "database_load_performed": False,
        "authoritative_sources_remain_external": True,
        "declared_source_outcome_evidence_flags_all_false": True,
        "governed_non_hold_outcome_token_scan_passed": True,
        "hold_text_class": "governance_blocker_not_evidence",
        "authority_flags": dict(AUTHORITY_FLAGS),
    }
    receipt = {
        **receipt_body,
        "receipt_sha256": canonical_sha256(receipt_body),
    }
    return LabEpistemicsProjection(
        manifest=manifest,
        manifest_identity=normalized_manifest_identity,
        governed_manifest=governed_manifest,
        nodes=tuple(nodes),
        relationships=tuple(relationships),
        load_plan=load_plan,
        receipt=receipt,
    )


__all__ = [
    "ARTIFACT_FORMAT",
    "ARTIFACT_ROLES",
    "AUTHORITY_FLAGS",
    "MANIFEST_SCHEMA",
    "PROJECTION_SCHEMA",
    "RECEIPT_SCHEMA",
    "LabEpistemicsPhaseBError",
    "LabEpistemicsProjection",
    "build_release_manifest",
    "canonical_json_bytes",
    "canonical_sha256",
    "object_identity",
    "project_lab_packet",
    "validate_release_manifest",
]
