"""Strict offline contracts for a rebuildable Foundry graph projection.

This module has no driver and performs no I/O. It validates caller-supplied
rows against a positive, versioned property schema and produces a compact
deterministic batch index. Actual rows are exposed only by the separate
bounded batch iterator; they are never embedded in the root plan.

Phase 3 deliberately keeps realized outcomes closed. Opening that namespace
requires a later schema version and a separately reviewed accepted
OutcomeRelease identity-and-scope contract; a caller-supplied name is never
authorization.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
import math
import re
from typing import Final

GRAPH_SCHEMA_VERSION: Final = "corpus-graph-vnext/v1"
LOAD_MANIFEST_SCHEMA: Final = "foundry-graph-load-manifest/v1"
BATCH_SIZE: Final = 500

# Bounds apply before duplicate collapse. Phase 4 may add a shard-backed
# streaming surface, but an in-memory Phase 3 caller is always bounded.
MAX_NODE_ROWS: Final = 100_000
MAX_EDGE_ROWS: Final = 200_000
MAX_TOTAL_BATCHES: Final = 600
MAX_SOURCE_RELEASES: Final = 64
MAX_SOURCE_IDENTITY_BYTES: Final = 128 * 1024
MAX_SOURCE_URI_BYTES: Final = 2_048
MAX_SOURCE_OBJECT_BYTES: Final = (1 << 63) - 1

MAX_PROPERTIES: Final = 32
MAX_PROPERTY_KEY_BYTES: Final = 64
MAX_PROPERTY_STRING_BYTES: Final = 512
MAX_PROPERTY_LIST_LENGTH: Final = 32
MAX_PROPERTY_LIST_ITEM_BYTES: Final = 256
MAX_PROPERTY_LIST_BYTES: Final = 4 * 1024
MAX_PROPERTY_BYTES: Final = 4 * 1024
MAX_NEO4J_INTEGER: Final = (1 << 63) - 1

NODE_KINDS: Final = frozenset({
    "Slate", "Contest", "SlateSnapshot", "PlayerSlate", "TeamSlate", "Game",
    "WorldRelease", "CorpusSnapshot", "CandidateSnapshot", "Lineup",
    "SelectedBook", "ScienceRelease", "VerifierRelease",
    "DeploymentAttestation", "FillPreset", "AdmissionPreset",
    "RetrievalPreset", "StrategyBundle", "ExperimentRun", "ExperimentCell",
    "Evaluation", "Fold", "MetricSet", "Trait", "Cohort", "WinnerRelease",
    "WinnerObservation", "OutcomeRelease", "OutcomeGrade", "SourceArtifact",
    "VerificationReceipt", "Attempt", "PromotionDecision",
})

RELATIONSHIP_TYPES: Final = frozenset({
    "DERIVED_FROM", "USES_SOURCE", "USES_WORLD_RELEASE", "GENERATED_BY",
    "SUPPLIED_BY_ARM", "MEMBER_OF_CORPUS", "CONTAINS_PLAYER", "PLAYS_FOR",
    "IN_GAME", "HAS_TRAIT", "MEMBER_OF_COHORT", "ADMITTED_BY",
    "SELECTED_BY", "MEMBER_OF_BOOK", "EVALUATED_IN", "HAS_METRIC",
    "PAIRED_AGAINST", "GRADED_IN_CONTEST", "DERIVED_FROM_OUTCOME",
    "OBSERVED_IN_WINNER_RELEASE", "EVALUATES_BUNDLE", "RETRIED_AS",
    "VERIFIED_BY", "DECIDES_ON_BUNDLE", "HAS_INFERRED_DEFENDER_EXPOSURE",
})

FORBIDDEN_RELATIONSHIP_TYPES: Final = frozenset({"COVERED_BY"})
QUALIFIED_INFERRED_TYPES: Final = frozenset({
    "HAS_INFERRED_DEFENDER_EXPOSURE",
})
OUTCOME_NODE_KINDS: Final = frozenset({
    "WinnerRelease", "WinnerObservation", "OutcomeRelease", "OutcomeGrade",
})
OUTCOME_RELATIONSHIP_TYPES: Final = frozenset({
    "GRADED_IN_CONTEST", "DERIVED_FROM_OUTCOME",
    "OBSERVED_IN_WINNER_RELEASE",
})

ALLOWED_NAMESPACES: Final = frozenset({
    "identity", "membership", "trait", "metric", "lineage", "realized",
})
OFFLINE_ALLOWED_NAMESPACES: Final = ALLOWED_NAMESPACES - {"realized"}

_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$")
_SHA: Final = re.compile(r"^[0-9a-f]{64}$")
_PROPERTY_KEY: Final = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_UTC: Final = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class CorpusGraphVNextError(ValueError):
    """Raised when a graph contract fails closed."""


def _fail(message: str) -> None:
    raise CorpusGraphVNextError(message)


@dataclass(frozen=True)
class PropertyRule:
    """Positive type and optional tighter size rule for one property."""

    value_type: str
    max_string_bytes: int = MAX_PROPERTY_STRING_BYTES
    max_list_items: int = MAX_PROPERTY_LIST_LENGTH
    allowed_strings: frozenset[str] | None = None


def _string(
    max_bytes: int = MAX_PROPERTY_STRING_BYTES,
    *, allowed: frozenset[str] | None = None,
) -> PropertyRule:
    return PropertyRule(
        "string", max_string_bytes=max_bytes, allowed_strings=allowed
    )


def _integer() -> PropertyRule:
    return PropertyRule("integer")


def _number() -> PropertyRule:
    return PropertyRule("number")


def _boolean() -> PropertyRule:
    return PropertyRule("boolean")


def _strings(max_items: int = MAX_PROPERTY_LIST_LENGTH) -> PropertyRule:
    return PropertyRule("string_list", max_list_items=max_items)


OFFLINE_METRIC_SCOPES: Final = frozenset({
    "outcome_blind", "simulated", "structural", "prospective",
})


# A Phase 4 adapter must add a reviewed property here before it can enter the
# graph. Unknown metadata is never passed through opportunistically.
NODE_PROPERTY_SCHEMA: Final[dict[str, dict[str, PropertyRule]]] = {
    "Slate": {
        "season": _integer(), "week": _integer(), "slate_type": _string(32),
        "lock_at_utc": _string(32), "game_count": _integer(),
    },
    "Contest": {
        "contest_id": _string(200), "name": _string(256),
        "field_size": _integer(), "entry_fee_micro": _integer(),
    },
    "SlateSnapshot": {
        "captured_at_utc": _string(32), "player_count": _integer(),
        "source_release_id": _string(200), "status": _string(32),
    },
    "PlayerSlate": {
        "player_id": _string(200), "display_name": _string(128),
        "position": _string(8), "team": _string(8), "opponent": _string(8),
        "salary": _integer(), "status": _string(32), "role": _string(64),
        "alignment": _string(64), "source_release_id": _string(200),
    },
    "TeamSlate": {
        "team": _string(8), "opponent": _string(8), "home": _boolean(),
        "game_id": _string(200),
    },
    "Game": {
        "game_id": _string(200), "home_team": _string(8),
        "away_team": _string(8), "kickoff_at_utc": _string(32),
    },
    "WorldRelease": {
        "release_id": _string(200), "world_count": _integer(),
        "block_count": _integer(), "schema_version": _string(128),
        "source_release_ids": _strings(16),
    },
    "CorpusSnapshot": {
        "snapshot_id": _string(200), "lineup_count": _integer(),
        "schema_version": _string(128), "fill_preset_id": _string(200),
    },
    "CandidateSnapshot": {
        "snapshot_id": _string(200), "lineup_count": _integer(),
        "schema_version": _string(128), "admission_preset_id": _string(200),
    },
    "Lineup": {
        "roster_hash": _string(64), "salary": _integer(),
        "legal": _boolean(), "ordinal": _integer(),
    },
    "SelectedBook": {
        "book_id": _string(200), "entry_budget": _integer(),
        "selected_count": _integer(), "retrieval_preset_id": _string(200),
    },
    "ScienceRelease": {
        "release_id": _string(200), "schema_version": _string(128),
        "code_sha256": _string(64), "accepted": _boolean(),
    },
    "VerifierRelease": {
        "release_id": _string(200), "schema_version": _string(128),
        "code_sha256": _string(64), "accepted": _boolean(),
    },
    "DeploymentAttestation": {
        "attestation_id": _string(200), "image_digest": _string(256),
        "verified_at_utc": _string(32), "accepted": _boolean(),
    },
    "FillPreset": {
        "preset_id": _string(200), "version": _string(64),
        "name": _string(128), "description": _string(512),
    },
    "AdmissionPreset": {
        "preset_id": _string(200), "version": _string(64),
        "name": _string(128), "description": _string(512),
    },
    "RetrievalPreset": {
        "preset_id": _string(200), "version": _string(64),
        "name": _string(128), "description": _string(512),
    },
    "StrategyBundle": {
        "bundle_id": _string(200), "version": _string(64),
        "entry_budget": _integer(), "fill_preset_id": _string(200),
        "admission_preset_id": _string(200),
        "retrieval_preset_id": _string(200),
    },
    "ExperimentRun": {
        "run_id": _string(200), "status": _string(32),
        "started_at_utc": _string(32), "completed_at_utc": _string(32),
        "task_count": _integer(), "accepted_task_count": _integer(),
    },
    "ExperimentCell": {
        "cell_id": _string(200), "arm_id": _string(200),
        "fold_id": _string(200), "status": _string(32),
    },
    "Evaluation": {
        "evaluation_id": _string(200),
        "scope": _string(32, allowed=OFFLINE_METRIC_SCOPES),
        "evidence_tier": _string(64), "fold_id": _string(200),
        "denominator": _integer(), "missing": _integer(),
    },
    "Fold": {
        "fold_id": _string(200), "training_blocks": _strings(16),
        "heldout_block": _string(200),
    },
    "MetricSet": {
        "metric_set_id": _string(200), "definition_id": _string(200),
        "scope": _string(32, allowed=OFFLINE_METRIC_SCOPES),
        "value": _number(), "support": _integer(), "missing": _integer(),
        "uncertainty_lower": _number(), "uncertainty_upper": _number(),
    },
    "Trait": {
        "trait_id": _string(200), "definition_version": _string(64),
        "name": _string(128), "evidence_class": _string(64),
    },
    "Cohort": {
        "cohort_id": _string(200), "definition_version": _string(64),
        "name": _string(128), "denominator": _integer(),
        "missing": _integer(),
    },
    # Outcome-bearing kinds stay registered vocabulary but are closed in v1.
    "WinnerRelease": {}, "WinnerObservation": {},
    "OutcomeRelease": {}, "OutcomeGrade": {},
    "SourceArtifact": {
        "artifact_id": _string(200), "uri": _string(512),
        "generation": _string(32), "sha256": _string(64),
        "byte_count": _integer(), "schema_version": _string(128),
    },
    "VerificationReceipt": {
        "receipt_id": _string(200), "schema_version": _string(128),
        "sha256": _string(64), "accepted": _boolean(),
        "verified_at_utc": _string(32),
    },
    "Attempt": {
        "attempt_id": _string(200), "ordinal": _integer(),
        "status": _string(32), "started_at_utc": _string(32),
        "completed_at_utc": _string(32),
    },
    "PromotionDecision": {
        "decision_id": _string(200), "disposition": _string(32),
        "decided_at_utc": _string(32), "evidence_tier": _string(64),
    },
}

RELATIONSHIP_PROPERTY_SCHEMA: Final[dict[str, dict[str, PropertyRule]]] = {
    relationship: {} for relationship in RELATIONSHIP_TYPES
}
RELATIONSHIP_PROPERTY_SCHEMA.update({
    "SUPPLIED_BY_ARM": {"arm_id": _string(200)},
    "CONTAINS_PLAYER": {"roster_slot": _string(8), "ordinal": _integer()},
    "HAS_TRAIT": {
        "trait_value": _number(), "definition_version": _string(64),
        "evidence_class": _string(64),
    },
    "MEMBER_OF_COHORT": {"membership_reason": _string(256)},
    "MEMBER_OF_BOOK": {"ordinal": _integer()},
    "HAS_METRIC": {"definition_id": _string(200)},
    "PAIRED_AGAINST": {"pair_id": _string(200)},
    "RETRIED_AS": {"attempt_ordinal": _integer()},
    "HAS_INFERRED_DEFENDER_EXPOSURE": {
        "qualified_inferred": _boolean(), "method_id": _string(200),
        "confidence": _number(), "exposure_share": _number(),
        "source_release_id": _string(200),
    },
})

NODE_NAMESPACE_SCHEMA: Final[dict[str, frozenset[str]]] = {
    kind: frozenset({"identity"}) for kind in NODE_KINDS
}
NODE_NAMESPACE_SCHEMA.update({
    "WorldRelease": frozenset({"identity", "lineage"}),
    "CorpusSnapshot": frozenset({"identity", "membership"}),
    "CandidateSnapshot": frozenset({"identity", "membership"}),
    "Lineup": frozenset({"identity", "membership"}),
    "SelectedBook": frozenset({"identity", "membership"}),
    "ScienceRelease": frozenset({"identity", "lineage"}),
    "VerifierRelease": frozenset({"identity", "lineage"}),
    "SourceArtifact": frozenset({"identity", "lineage"}),
    "VerificationReceipt": frozenset({"identity", "lineage"}),
    "Trait": frozenset({"trait"}), "Cohort": frozenset({"trait"}),
    "Evaluation": frozenset({"metric"}), "MetricSet": frozenset({"metric"}),
    "WinnerRelease": frozenset({"realized"}),
    "WinnerObservation": frozenset({"realized"}),
    "OutcomeRelease": frozenset({"realized"}),
    "OutcomeGrade": frozenset({"realized"}),
})

RELATIONSHIP_NAMESPACE_SCHEMA: Final[dict[str, frozenset[str]]] = {
    relationship: frozenset({"lineage"}) for relationship in RELATIONSHIP_TYPES
}
RELATIONSHIP_NAMESPACE_SCHEMA.update({
    "SUPPLIED_BY_ARM": frozenset({"membership"}),
    "MEMBER_OF_CORPUS": frozenset({"membership"}),
    "CONTAINS_PLAYER": frozenset({"membership"}),
    "PLAYS_FOR": frozenset({"membership"}),
    "IN_GAME": frozenset({"membership"}),
    "HAS_TRAIT": frozenset({"trait"}),
    "MEMBER_OF_COHORT": frozenset({"trait"}),
    "ADMITTED_BY": frozenset({"membership"}),
    "SELECTED_BY": frozenset({"membership"}),
    "MEMBER_OF_BOOK": frozenset({"membership"}),
    "EVALUATED_IN": frozenset({"metric"}),
    "HAS_METRIC": frozenset({"metric"}),
    "PAIRED_AGAINST": frozenset({"metric"}),
    "GRADED_IN_CONTEST": frozenset({"realized"}),
    "DERIVED_FROM_OUTCOME": frozenset({"realized"}),
    "OBSERVED_IN_WINNER_RELEASE": frozenset({"realized"}),
    "EVALUATES_BUNDLE": frozenset({"metric"}),
    "HAS_INFERRED_DEFENDER_EXPOSURE": frozenset({"trait"}),
})


def canonical_sha256(value: object) -> str:
    try:
        body = json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusGraphVNextError(
            "canonical value is not finite JSON"
        ) from exc
    return sha256(body).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusGraphVNextError(
            "graph value is not finite canonical JSON"
        ) from exc


def _require_exact_keys(
    value: Mapping[str, object], *, expected: set[str], label: str
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        _fail(f"{label} keys differ: missing={missing}, extra={extra}")


def _require_sequence(
    value: object, *, label: str, maximum: int, nonempty: bool = False
) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} is not a bounded sequence")
    if nonempty and not value:
        _fail(f"{label} is empty")
    if len(value) > maximum:
        _fail(f"{label} exceeds the {maximum} item bound")
    return value


def _require_utc(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        _fail(f"{label} is not second-precision UTC")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise CorpusGraphVNextError(
            f"{label} is not a valid UTC timestamp"
        ) from exc
    return value


def _require_identity(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a mapping")
    row = dict(value)
    _require_exact_keys(
        row, expected={"uri", "generation", "sha256", "bytes"}, label=label
    )
    uri = row["uri"]
    if (
        not isinstance(uri, str)
        or not uri.startswith("gs://")
        or len(uri.encode("utf-8")) > MAX_SOURCE_URI_BYTES
        or any(character.isspace() or ord(character) < 32 for character in uri)
        or uri.count("/") < 3
    ):
        _fail(f"{label}.uri is not a bounded canonical gs:// uri")
    generation = row["generation"]
    if (
        not isinstance(generation, str)
        or not generation.isdigit()
        or len(generation) > 32
        or int(generation) <= 0
    ):
        _fail(f"{label}.generation is not bounded positive digits")
    digest = row["sha256"]
    if not isinstance(digest, str) or _SHA.fullmatch(digest) is None:
        _fail(f"{label}.sha256 is not 64-hex")
    byte_count = row["bytes"]
    if (
        not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or not 0 < byte_count <= MAX_SOURCE_OBJECT_BYTES
    ):
        _fail(f"{label}.bytes is not a bounded positive integer")
    return {
        "uri": uri, "generation": generation, "sha256": digest,
        "bytes": byte_count,
    }


def _property_tokens(key: str) -> tuple[str, ...]:
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key)
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", expanded).strip("_").lower()
    return tuple(token for token in normalized.split("_") if token)


def _looks_secret(key: str) -> bool:
    tokens = _property_tokens(key)
    compact = "".join(tokens)
    token_set = set(tokens)
    if token_set & {"credential", "credentials", "secret", "password", "pwd"}:
        return True
    if token_set & {"token", "apikey", "privatekey"}:
        return True
    return compact in {
        "apikey", "accesstoken", "refreshtoken", "clientsecret",
        "privatekey", "bearertoken", "authtoken",
    } or ({"api", "key"} <= token_set) or ({"private", "key"} <= token_set)


def _looks_outcome(key: str) -> bool:
    tokens = _property_tokens(key)
    compact = "".join(tokens)
    token_set = set(tokens)
    if token_set & {
        "actual", "realized", "payout", "payouts", "winnings", "roi",
        "rank", "ranking", "winner", "winning", "place", "finish",
    }:
        return True
    if token_set & {"score", "points"}:
        return True
    return any(fragment in compact for fragment in (
        "dkpoints", "fantasypoints", "lineupscore", "contestplace",
        "tournamentrank", "cashamount",
    ))


def _validate_integer(value: object, *, label: str) -> int:
    if (
        not isinstance(value, int) or isinstance(value, bool)
        or not -MAX_NEO4J_INTEGER - 1 <= value <= MAX_NEO4J_INTEGER
    ):
        _fail(f"{label} is not a bounded Neo4j integer")
    return value


def _validate_number(value: object, *, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{label} is not numeric")
    if isinstance(value, int):
        return _validate_integer(value, label=label)
    if not math.isfinite(value):
        _fail(f"{label} is not finite")
    return 0.0 if value == 0 else value


def _validate_property(
    key: object, value: object, *, rule: PropertyRule, label: str
) -> object:
    if not isinstance(key, str):
        _fail(f"{label} property key is not a string")
    if (
        _PROPERTY_KEY.fullmatch(key) is None
        or len(key.encode("utf-8")) > MAX_PROPERTY_KEY_BYTES
    ):
        _fail(f"{label} property key {key!r} is not canonical and bounded")
    if _looks_secret(key):
        _fail(f"{label} secret-like property {key!r} is forbidden")
    if _looks_outcome(key):
        _fail(f"{label} outcome-like property {key!r} is closed offline")
    if value is None:
        _fail(f"{label} property {key!r} is null; Neo4j would delete it")

    property_label = f"{label} property {key!r}"
    if rule.value_type == "string":
        if not isinstance(value, str):
            _fail(f"{property_label} is not a string")
        if len(value.encode("utf-8")) > rule.max_string_bytes:
            _fail(f"{property_label} exceeds its UTF-8 byte bound")
        if rule.allowed_strings is not None and value not in rule.allowed_strings:
            _fail(f"{property_label} is not in its closed value vocabulary")
        if key == "definition_id" and _looks_outcome(value):
            _fail(f"{property_label} refers to an outcome closed offline")
        retained: object = value
    elif rule.value_type == "integer":
        retained = _validate_integer(value, label=property_label)
    elif rule.value_type == "number":
        retained = _validate_number(value, label=property_label)
    elif rule.value_type == "boolean":
        if not isinstance(value, bool):
            _fail(f"{property_label} is not boolean")
        retained = value
    elif rule.value_type == "string_list":
        values = _require_sequence(
            value, label=property_label, maximum=rule.max_list_items
        )
        retained_list: list[str] = []
        for index, item in enumerate(values):
            if not isinstance(item, str):
                _fail(f"{property_label}[{index}] is not a string")
            if len(item.encode("utf-8")) > MAX_PROPERTY_LIST_ITEM_BYTES:
                _fail(f"{property_label}[{index}] exceeds its UTF-8 byte bound")
            retained_list.append(item)
        if len(_canonical_bytes(retained_list)) > MAX_PROPERTY_LIST_BYTES:
            _fail(f"{property_label} exceeds its aggregate byte bound")
        retained = retained_list
    else:  # pragma: no cover - schema definitions are module-owned constants.
        _fail(f"{property_label} has an unknown schema rule")
    return retained


def _validate_properties(
    properties: object, *, schema: Mapping[str, PropertyRule], label: str
) -> dict[str, object]:
    if not isinstance(properties, Mapping):
        _fail(f"{label} properties is not a mapping")
    if len(properties) > MAX_PROPERTIES:
        _fail(f"{label} property count exceeds {MAX_PROPERTIES}")
    retained: dict[str, object] = {}
    for key in sorted(properties, key=lambda candidate: str(candidate)):
        if not isinstance(key, str):
            _fail(f"{label} property key is not a string")
        if _looks_secret(key):
            _fail(f"{label} secret-like property {key!r} is forbidden")
        if _looks_outcome(key):
            _fail(f"{label} outcome-like property {key!r} is closed offline")
        if (
            _PROPERTY_KEY.fullmatch(key) is None
            or len(key.encode("utf-8")) > MAX_PROPERTY_KEY_BYTES
        ):
            _fail(f"{label} property key {key!r} is not canonical and bounded")
        if key not in schema:
            _fail(f"{label} property {key!r} is not in its positive schema")
        retained[key] = _validate_property(
            key, properties[key], rule=schema[key], label=label
        )
    if len(_canonical_bytes(retained)) > MAX_PROPERTY_BYTES:
        _fail(f"{label} properties exceed the aggregate byte bound")
    return retained


def validate_node_row(row: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(row, Mapping):
        _fail("node row is not a mapping")
    retained_row = dict(row)
    _require_exact_keys(
        retained_row,
        expected={"kind", "node_id", "namespace", "properties"},
        label="node row",
    )
    kind = retained_row["kind"]
    node_id = retained_row["node_id"]
    namespace = retained_row["namespace"]
    if kind not in NODE_KINDS:
        _fail(f"node kind {kind!r} is not registered")
    if kind in OUTCOME_NODE_KINDS:
        _fail(f"outcome node kind {kind} is closed in offline schema v1")
    if not isinstance(node_id, str) or _ID.fullmatch(node_id) is None:
        _fail("node_id is not canonical")
    if namespace not in NODE_NAMESPACE_SCHEMA[str(kind)]:
        _fail(f"node kind {kind} does not allow namespace {namespace!r}")
    if namespace not in OFFLINE_ALLOWED_NAMESPACES:
        _fail(f"node namespace {namespace!r} is closed offline")
    properties = _validate_properties(
        retained_row["properties"], schema=NODE_PROPERTY_SCHEMA[str(kind)],
        label=f"node {node_id}",
    )
    if kind in {"Evaluation", "MetricSet"} and "scope" not in properties:
        _fail(f"node kind {kind} requires an explicit offline scope")
    return {
        "kind": kind, "node_id": node_id, "namespace": namespace,
        "properties": properties,
    }


def validate_edge_row(row: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(row, Mapping):
        _fail("edge row is not a mapping")
    retained_row = dict(row)
    _require_exact_keys(
        retained_row,
        expected={
            "relationship", "source_id", "target_id", "namespace",
            "properties",
        },
        label="edge row",
    )
    relationship = retained_row["relationship"]
    source = retained_row["source_id"]
    target = retained_row["target_id"]
    namespace = retained_row["namespace"]
    if relationship in FORBIDDEN_RELATIONSHIP_TYPES:
        _fail(
            f"relationship {relationship} is forbidden: inferred matchup "
            "evidence may never become factual coverage"
        )
    if relationship not in RELATIONSHIP_TYPES:
        _fail(f"relationship {relationship!r} is not registered")
    if relationship in OUTCOME_RELATIONSHIP_TYPES:
        _fail(
            f"outcome relationship {relationship} is closed in offline schema v1"
        )
    for label, value in (("source_id", source), ("target_id", target)):
        if not isinstance(value, str) or _ID.fullmatch(value) is None:
            _fail(f"edge {label} is not canonical")
    if namespace not in RELATIONSHIP_NAMESPACE_SCHEMA[str(relationship)]:
        _fail(
            f"relationship {relationship} does not allow namespace {namespace!r}"
        )
    if namespace not in OFFLINE_ALLOWED_NAMESPACES:
        _fail(f"edge namespace {namespace!r} is closed offline")
    properties = _validate_properties(
        retained_row["properties"],
        schema=RELATIONSHIP_PROPERTY_SCHEMA[str(relationship)],
        label=f"edge {source}->{target}",
    )
    if (
        relationship in QUALIFIED_INFERRED_TYPES
        and properties.get("qualified_inferred") is not True
    ):
        _fail(
            f"relationship {relationship} must carry qualified_inferred=true"
        )
    edge_key = f"{namespace}|{source}|{relationship}|{target}"
    return {
        "relationship": relationship, "source_id": source,
        "target_id": target, "namespace": namespace, "edge_key": edge_key,
        "properties": properties,
    }


def validate_load_manifest(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail("load manifest is not a mapping")
    manifest = dict(value)
    required = {
        "schema_version", "graph_schema_version", "graph_release_id",
        "predecessor_graph_release_id", "allowed_namespaces",
        "source_releases", "authorized_outcome_release_id", "created_at_utc",
    }
    actual = set(manifest)
    if actual not in (required, required | {"manifest_sha256"}):
        _require_exact_keys(manifest, expected=required, label="load manifest")
    if manifest["schema_version"] != LOAD_MANIFEST_SCHEMA:
        _fail("load manifest schema differs")
    if manifest["graph_schema_version"] != GRAPH_SCHEMA_VERSION:
        _fail("load manifest graph schema version differs")
    release = manifest["graph_release_id"]
    if not isinstance(release, str) or _ID.fullmatch(release) is None:
        _fail("graph_release_id is not canonical")
    predecessor = manifest["predecessor_graph_release_id"]
    if predecessor is not None and (
        not isinstance(predecessor, str) or _ID.fullmatch(predecessor) is None
    ):
        _fail("predecessor_graph_release_id is not canonical")

    namespaces_raw = _require_sequence(
        manifest["allowed_namespaces"], label="allowed_namespaces",
        maximum=len(ALLOWED_NAMESPACES), nonempty=True,
    )
    if any(not isinstance(item, str) for item in namespaces_raw):
        _fail("allowed_namespaces contains a non-string")
    if len(set(namespaces_raw)) != len(namespaces_raw):
        _fail("allowed_namespaces contains a duplicate")
    namespaces = sorted(namespaces_raw)
    if not set(namespaces) <= OFFLINE_ALLOWED_NAMESPACES:
        _fail("realized or unknown namespace is closed in offline schema v1")
    if manifest["authorized_outcome_release_id"] is not None:
        _fail(
            "authorized_outcome_release_id cannot open realized data in "
            "offline schema v1"
        )

    sources_raw = _require_sequence(
        manifest["source_releases"], label="source_releases",
        maximum=MAX_SOURCE_RELEASES, nonempty=True,
    )
    sources = [
        _require_identity(source, label=f"source_releases[{index}]")
        for index, source in enumerate(sources_raw)
    ]
    source_keys: set[tuple[str, str]] = set()
    exact_sources: set[tuple[str, str, str, int]] = set()
    for source in sources:
        exact = (
            str(source["uri"]), str(source["generation"]),
            str(source["sha256"]), int(source["bytes"]),
        )
        key = exact[:2]
        if exact in exact_sources:
            _fail(f"source_releases contains duplicate identity {key}")
        if key in source_keys:
            _fail(f"source_releases contains conflicting identity {key}")
        exact_sources.add(exact)
        source_keys.add(key)
    sources.sort(key=lambda source: (
        str(source["uri"]), str(source["generation"]),
        str(source["sha256"]), int(source["bytes"]),
    ))
    if len(_canonical_bytes(sources)) > MAX_SOURCE_IDENTITY_BYTES:
        _fail("source_releases exceeds the aggregate byte bound")

    created = _require_utc(manifest["created_at_utc"], label="created_at_utc")
    body = {
        "schema_version": LOAD_MANIFEST_SCHEMA,
        "graph_schema_version": GRAPH_SCHEMA_VERSION,
        "graph_release_id": release,
        "predecessor_graph_release_id": predecessor,
        "allowed_namespaces": namespaces,
        "source_releases": sources,
        "authorized_outcome_release_id": None,
        "created_at_utc": created,
    }
    expected_hash = canonical_sha256(body)
    retained_hash = manifest.get("manifest_sha256")
    if retained_hash is not None:
        if not isinstance(retained_hash, str) or _SHA.fullmatch(retained_hash) is None:
            _fail("manifest_sha256 is not 64-hex")
        if retained_hash != expected_hash:
            _fail("manifest_sha256 differs from the canonical body")
    return {**body, "manifest_sha256": expected_hash}


def _validated_graph_rows(
    *, node_rows: Sequence[Mapping[str, object]],
    edge_rows: Sequence[Mapping[str, object]], allowed: set[str],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    _require_sequence(node_rows, label="node_rows", maximum=MAX_NODE_ROWS)
    _require_sequence(edge_rows, label="edge_rows", maximum=MAX_EDGE_ROWS)
    nodes_by_id: dict[str, dict[str, object]] = {}
    for row in node_rows:
        node = validate_node_row(row)
        if node["namespace"] not in allowed:
            _fail(
                f"node namespace {node['namespace']} is outside the manifest"
            )
        node_id = str(node["node_id"])
        existing = nodes_by_id.get(node_id)
        if existing is not None and existing != node:
            _fail(f"conflicting identity for node {node_id}")
        nodes_by_id[node_id] = node

    edges_by_key: dict[str, dict[str, object]] = {}
    for row in edge_rows:
        edge = validate_edge_row(row)
        if edge["namespace"] not in allowed:
            _fail(
                f"edge namespace {edge['namespace']} is outside the manifest"
            )
        for endpoint in (str(edge["source_id"]), str(edge["target_id"])):
            if endpoint not in nodes_by_id:
                _fail(f"edge endpoint {endpoint} is not a loaded node")
            if nodes_by_id[endpoint]["kind"] in OUTCOME_NODE_KINDS:
                _fail(f"edge endpoint {endpoint} is outcome-bearing")
        edge_key = str(edge["edge_key"])
        existing = edges_by_key.get(edge_key)
        if existing is not None and existing != edge:
            _fail(f"conflicting identity for edge {edge_key}")
        edges_by_key[edge_key] = edge

    nodes = sorted(
        nodes_by_id.values(),
        key=lambda node: (str(node["kind"]), str(node["node_id"])),
    )
    edges = sorted(edges_by_key.values(), key=lambda edge: str(edge["edge_key"]))
    return nodes, edges


def _batch_windows(
    rows: list[dict[str, object]], *, unwind: str, key_name: str
) -> Iterator[dict[str, object]]:
    for ordinal, start in enumerate(range(0, len(rows), BATCH_SIZE)):
        window = rows[start : start + BATCH_SIZE]
        keys = [str(row[key_name]) for row in window]
        digest = canonical_sha256(window)
        yield {
            "unwind": unwind, "ordinal": ordinal, "row_count": len(window),
            "first_key": keys[0], "last_key": keys[-1],
            "batch_sha256": digest, "batch_id": f"{unwind}:{ordinal}:{digest}",
            "rows": window,
        }


def iter_load_batches(
    *, manifest: Mapping[str, object],
    node_rows: Sequence[Mapping[str, object]],
    edge_rows: Sequence[Mapping[str, object]],
) -> Iterator[dict[str, object]]:
    """Yield bounded row-bearing batches; callers must checkpoint each hash."""

    retained_manifest = validate_load_manifest(manifest)
    nodes, edges = _validated_graph_rows(
        node_rows=node_rows, edge_rows=edge_rows,
        allowed=set(retained_manifest["allowed_namespaces"]),
    )
    yield from _batch_windows(nodes, unwind="nodes", key_name="node_id")
    yield from _batch_windows(edges, unwind="edges", key_name="edge_key")


def build_load_plan(
    *, manifest: Mapping[str, object],
    node_rows: Sequence[Mapping[str, object]],
    edge_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build a compact deterministic index and exact terminal census.

    The plan holds only per-batch identities, never graph rows. Input order is
    irrelevant; duplicate equal identities collapse and conflicts fail.
    """

    retained_manifest = validate_load_manifest(manifest)
    nodes, edges = _validated_graph_rows(
        node_rows=node_rows, edge_rows=edge_rows,
        allowed=set(retained_manifest["allowed_namespaces"]),
    )
    index: list[dict[str, object]] = []
    for batch in _batch_windows(nodes, unwind="nodes", key_name="node_id"):
        index.append({
            key: value for key, value in batch.items() if key != "rows"
        })
    for batch in _batch_windows(edges, unwind="edges", key_name="edge_key"):
        index.append({
            key: value for key, value in batch.items() if key != "rows"
        })
    if len(index) > MAX_TOTAL_BATCHES:
        _fail(f"load plan exceeds the {MAX_TOTAL_BATCHES} batch bound")
    node_batch_index = [item for item in index if item["unwind"] == "nodes"]
    edge_batch_index = [item for item in index if item["unwind"] == "edges"]

    node_kind_census = {
        kind: sum(1 for node in nodes if node["kind"] == kind)
        for kind in sorted({str(node["kind"]) for node in nodes})
    }
    edge_type_census = {
        relationship: sum(
            1 for edge in edges if edge["relationship"] == relationship
        )
        for relationship in sorted(
            {str(edge["relationship"]) for edge in edges}
        )
    }
    property_count = sum(len(node["properties"]) for node in nodes) + sum(
        len(edge["properties"]) for edge in edges
    )
    plan_body = {
        "schema_version": GRAPH_SCHEMA_VERSION,
        "manifest_sha256": retained_manifest["manifest_sha256"],
        "batch_size": BATCH_SIZE,
        "node_batch_index": node_batch_index,
        "edge_batch_index": edge_batch_index,
        "terminal_census": {
            "node_count": len(nodes), "edge_count": len(edges),
            "property_count": property_count, "node_kinds": node_kind_census,
            "relationship_types": edge_type_census,
            "namespaces": sorted(
                {str(node["namespace"]) for node in nodes}
                | {str(edge["namespace"]) for edge in edges}
            ),
        },
    }
    return {**plan_body, "plan_sha256": canonical_sha256(plan_body)}
