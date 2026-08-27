"""Phase 5: deterministic, identity-bound graph capacity estimator.

Decides NOTHING by itself. The estimator turns an exact, identity-bound
input packet (terminal release counts, release identities, provisioning
parameters) into pre-registered estimates for BOTH candidate graph modes:

- ``full-lineup``  — one node per accepted unique roster, sparse
  trait/cohort memberships, and the Phase 4 bundle/book membership
  relationships;
- ``summary-only`` — strategy/run/book/cohort/trait aggregates plus
  selected-lineup detail only; full-corpus traversal is explicitly
  UNAVAILABLE and is never labeled "full".

Every semantic registry the estimator consults — the node-count and
exact-relationship input registries, the derived relationship set, the
endpoint map, the release-manifest to count/kind linkage, the identity/
version/hash/parameter input names, the closed realized vocabulary, the
modes, and the roster-slot law — lives in ONE deep-frozen versioned
``SEMANTIC_CONTRACT`` whose literal digest is pinned and re-derived from
the live object at import and at every build/validate, and whose body and
digest are embedded in and verified from every receipt. The estimation
law is frozen and pinned the same way. Substituting or altering either
registry cannot emit a receipt nor keep an existing one valid.

Cardinality laws: ``ADMITTED_BY`` = one per StrategyBundle and
``SELECTED_BY`` = one per StrategyBundle plus one per SelectedBook follow
the Phase 4 fixture adapter's endpoint semantics exactly.
``CONTAINS_PLAYER`` = nine per loaded lineup is the separate PRODUCTION
Phase 5 law — the Phase 4 synthetic fixture carries one per lineup, and
the parity test asserts exactly that. Every other open relationship type
is an exact supplied count. Kinds and relationship types whose only
namespace is ``realized`` (winner and outcome vocabulary) are CLOSED in
v1 and contribute nothing.

A receipt (``foundry-graph-capacity-receipt/v1``) binds the estimation
law, the semantic contract, the inputs (hashed, with authority,
identities, count-matched release manifests, and an optional
content-only assertion digest), both estimates, the pre-registered
thresholds, per-mode feasibility, and the forcing result. The mode
DECISION is withheld: fixture-authority inputs always yield
``pending-lead-inputs``; lead-authority inputs with a bound assertion
yield ``estimated-pending-approval`` — a recommendation whose approval
status is ``not-authenticated`` (a detached immutable lead approval
receipt identity is required and is not accepted in this offline phase).
Nothing here approves, selects, or activates a mode.

Everything here is pure and offline: no cloud read, no driver, no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import datetime as _dt
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Final, Literal

from nfl_dfs.research import corpus_graph_vnext_contracts as graph

CAPACITY_RECEIPT_SCHEMA: Final = "foundry-graph-capacity-receipt/v1"
CAPACITY_INPUTS_SCHEMA: Final = "foundry-graph-capacity-inputs/v1"
# An assertion digest binds a packet's content. It is NOT an approval and
# authenticates nobody: approval requires a detached immutable lead
# approval receipt identity, which this offline phase does not accept.
INPUTS_ASSERTION_SUBJECT: Final = "foundry-graph-capacity-inputs/v1#inputs-assertion"
ESTIMATION_LAW_VERSION: Final = "foundry-graph-capacity-estimation-law/v1"

InputAuthority = Literal["synthetic-fixture", "lead-supplied-terminal"]
GraphMode = Literal["full-lineup", "summary-only"]
MODES: Final[tuple[GraphMode, ...]] = ("full-lineup", "summary-only")

MAX_COUNT: Final = 10**12
MAX_URI_BYTES: Final = 2_048
MAX_IDENTITY_OBJECT_BYTES: Final = 256 * 1024**2
MAX_RELEASE_MANIFEST_ENTRIES: Final = 1_024
MAX_FIXTURE_SCALE: Final = 1_000
_GCS_BUCKET: Final = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
SYNTHETIC_URI_PREFIX: Final = "gs://synthetic-fixture.invalid/"
_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$")
_SHA: Final = re.compile(r"^[0-9a-f]{64}$")
_UTC: Final = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

ROSTER_SLOTS: Final = 9


class CorpusGraphCapacityError(ValueError):
    """Raised when inputs, law, or receipt fail closed."""


def _fail(message: str) -> None:
    raise CorpusGraphCapacityError(message)


def _plain(value: object) -> object:
    """Recursively convert frozen views back to JSON-serializable plain data."""

    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, frozenset, set)):
        items = [_plain(item) for item in value]
        return sorted(items, key=json.dumps) if isinstance(value, (frozenset, set)) else items
    return value


def _freeze(value: object) -> object:
    """Recursively deep-freeze: mappings -> MappingProxyType, sequences -> tuple."""

    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted(_freeze(item) for item in value))  # type: ignore[type-var]
    return value


def canonical_sha256(value: object) -> str:
    return sha256(
        json.dumps(
            _plain(value), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


# ------------------------------------------------------------------ #
# Pre-registered estimation law (frozen; its LITERAL digest is pinned)  #
# ------------------------------------------------------------------ #

_ESTIMATION_LAW_CONTENT: Final[dict[str, object]] = {
    "version": ESTIMATION_LAW_VERSION,
    # Store-size coefficients: pre-registered ESTIMATES of on-disk cost
    # per element (record-store family). Observed bytes replace estimates
    # only through a later measured receipt; estimates never do.
    "bytes_per_node": 15,
    "bytes_per_relationship": 34,
    "bytes_per_property": 41,
    "string_chunk_bytes": 128,
    "index_and_overhead_factor_permille": 1_500,  # x1.5
    # Safety fractions (permille) the estimate must stay under.
    "disk_safety_fraction_permille": 500,        # store <= 50% of disk
    "page_cache_fraction_permille": 800,         # store <= 80% of page cache
    "heap_floor_bytes": 2 * 1024**3,
    # Load/rebuild budgets: bounded streamed batches of BATCH_SIZE rows,
    # each allowed the adapter's per-transaction deadline.
    "batch_size": graph.BATCH_SIZE,
    "batch_deadline_ms": 2_000,
    "index_build_seconds_per_million_nodes": 60,
    # Catalogued read-query budgets to be OBSERVED after a live load.
    "query_p50_budget_ms": 200,
    "query_p95_budget_ms": 2_000,
    # Absolute element ceiling for any mode.
    "max_graph_elements": 50_000_000,
}
# Immutable view: item assignment raises TypeError.
ESTIMATION_LAW: Final[Mapping[str, object]] = _freeze(_ESTIMATION_LAW_CONTENT)  # type: ignore[assignment]
# Literal v1 digest, frozen by the lead. A changed law is a NEW law version
# with a new pinned digest. The digest is re-derived from the LIVE law at
# import AND at every build/validate, so a runtime substitution of the law
# object cannot emit or validate a receipt under the frozen hash.
ESTIMATION_LAW_SHA256: Final = (
    "5d20920d5c5e4a779230a966f29322c46e21a05a5c442422f0f9ad3884dc5fdc"
)


def law_digest_now() -> str:
    """Digest of the live law object, recomputed on every call."""

    return canonical_sha256(dict(ESTIMATION_LAW))


def require_frozen_law() -> Mapping[str, object]:
    """Fail closed unless the live law still hashes to the frozen digest."""

    if law_digest_now() != ESTIMATION_LAW_SHA256:
        _fail("estimation law content drifted from its frozen v1 digest")
    return ESTIMATION_LAW


require_frozen_law()


# ------------------------------------------------------------------ #
# Vocabulary derived from the contracts module                          #
# ------------------------------------------------------------------ #

_CLOSED_NAMESPACES: Final = frozenset(
    graph.ALLOWED_NAMESPACES - graph.OFFLINE_ALLOWED_NAMESPACES
)
CLOSED_NODE_KINDS: Final = frozenset(
    kind for kind, namespaces in graph.NODE_NAMESPACE_SCHEMA.items()
    if namespaces <= _CLOSED_NAMESPACES
)
CLOSED_RELATIONSHIP_TYPES: Final = frozenset(
    relationship
    for relationship, namespaces in graph.RELATIONSHIP_NAMESPACE_SCHEMA.items()
    if namespaces <= _CLOSED_NAMESPACES
)
OPEN_NODE_KINDS: Final = graph.NODE_KINDS - CLOSED_NODE_KINDS
OPEN_RELATIONSHIP_TYPES: Final = graph.RELATIONSHIP_TYPES - CLOSED_RELATIONSHIP_TYPES


def property_schema_version() -> str:
    """Bind the positive property schema by COMPLETE rule content."""

    def rule_image(rule: object) -> dict[str, object]:
        allowed = getattr(rule, "allowed_strings", None)
        return {
            "value_type": getattr(rule, "value_type", None),
            "max_string_bytes": getattr(rule, "max_string_bytes", None),
            "max_list_items": getattr(rule, "max_list_items", None),
            "allowed_strings": (
                None if allowed is None else sorted(allowed)
            ),
        }

    schema_image = {
        "nodes": {
            kind: {name: rule_image(rule) for name, rule in sorted(rules.items())}
            for kind, rules in sorted(graph.NODE_PROPERTY_SCHEMA.items())
        },
        "relationships": {
            relationship: {
                name: rule_image(rule) for name, rule in sorted(rules.items())
            }
            for relationship, rules in sorted(
                graph.RELATIONSHIP_PROPERTY_SCHEMA.items()
            )
        },
        "node_namespaces": {
            kind: sorted(namespaces)
            for kind, namespaces in sorted(graph.NODE_NAMESPACE_SCHEMA.items())
        },
        "relationship_namespaces": {
            relationship: sorted(namespaces)
            for relationship, namespaces in sorted(
                graph.RELATIONSHIP_NAMESPACE_SCHEMA.items()
            )
        },
    }
    return f"{graph.GRAPH_SCHEMA_VERSION}+properties-{canonical_sha256(schema_image)[:16]}"



# ------------------------------------------------------------------ #
# ONE canonical, versioned, deep-frozen semantic contract.             #
# Every registry the estimator consults lives here; its literal digest #
# is pinned below and re-derived from the LIVE object at import and at #
# every build/validate; its body and digest travel inside each receipt.#
# ------------------------------------------------------------------ #

SEMANTIC_CONTRACT_VERSION: Final = "foundry-graph-capacity-semantic-contract/v1"


def graph_binding_now() -> dict[str, object]:
    """Exact image of the LIVE graph contract this estimator is bound to.

    Recomputed on every call from ``corpus_graph_vnext_contracts``: graph
    schema version, the complete node/relationship vocabularies, the
    closed/open split, every namespace schema, the forbidden and qualified
    relationship laws, and the complete-property-rule version. Any live
    drift makes the semantic contract's embedded binding stale and fails
    every build and validation.
    """

    closed_namespaces = frozenset(graph.ALLOWED_NAMESPACES - graph.OFFLINE_ALLOWED_NAMESPACES)
    closed_kinds = sorted(
        kind for kind, namespaces in graph.NODE_NAMESPACE_SCHEMA.items()
        if namespaces <= closed_namespaces
    )
    closed_relationships = sorted(
        relationship
        for relationship, namespaces in graph.RELATIONSHIP_NAMESPACE_SCHEMA.items()
        if namespaces <= closed_namespaces
    )
    return {
        "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
        "property_schema_version": property_schema_version(),
        "allowed_namespaces": sorted(graph.ALLOWED_NAMESPACES),
        "offline_allowed_namespaces": sorted(graph.OFFLINE_ALLOWED_NAMESPACES),
        "closed_namespaces": sorted(closed_namespaces),
        "node_kinds": sorted(graph.NODE_KINDS),
        "relationship_types": sorted(graph.RELATIONSHIP_TYPES),
        "forbidden_relationship_types": sorted(graph.FORBIDDEN_RELATIONSHIP_TYPES),
        "qualified_inferred_types": sorted(graph.QUALIFIED_INFERRED_TYPES),
        "closed_node_kinds": closed_kinds,
        "closed_relationship_types": closed_relationships,
        "open_node_kinds": sorted(graph.NODE_KINDS - set(closed_kinds)),
        "open_relationship_types": sorted(graph.RELATIONSHIP_TYPES - set(closed_relationships)),
        "node_namespace_schema": {
            kind: sorted(namespaces)
            for kind, namespaces in sorted(graph.NODE_NAMESPACE_SCHEMA.items())
        },
        "relationship_namespace_schema": {
            relationship: sorted(namespaces)
            for relationship, namespaces in sorted(graph.RELATIONSHIP_NAMESPACE_SCHEMA.items())
        },
    }


_SEMANTIC_CONTRACT_CONTENT: Final[dict[str, object]] = {
    "version": SEMANTIC_CONTRACT_VERSION,
    "graph_binding": graph_binding_now(),
    "modes": ["full-lineup", "summary-only"],
    "roster_slots": ROSTER_SLOTS,
    "closed_node_kinds": sorted(CLOSED_NODE_KINDS),
    "closed_relationship_types": sorted(CLOSED_RELATIONSHIP_TYPES),
    "excluded_from_graph": [
        "world score matrices",
        "per-world nodes or relationships",
        "dense pairwise player/lineup networks (quadratic)",
        "raw licensed Fantasy Points or SIS rows",
        "raw contest standings and contestant identifiers",
        "credentials or secrets",
        "mutable active-policy pointers",
        "realized namespace (closed in v1): winner and outcome node kinds and relationships",
    ],
    # Node-count inputs: name -> {kind, modes}. Lineup counts are mode-bound.
    "node_count_inputs": [
        {"name": "accepted_slate_count", "kind": "Slate", "modes": ["full-lineup", "summary-only"]},
        {"name": "slate_snapshot_count", "kind": "SlateSnapshot", "modes": ["full-lineup", "summary-only"]},
        {"name": "contest_count", "kind": "Contest", "modes": ["full-lineup", "summary-only"]},
        {"name": "game_count", "kind": "Game", "modes": ["full-lineup", "summary-only"]},
        {"name": "team_slate_count", "kind": "TeamSlate", "modes": ["full-lineup", "summary-only"]},
        {"name": "player_slate_count", "kind": "PlayerSlate", "modes": ["full-lineup", "summary-only"]},
        {"name": "world_release_count", "kind": "WorldRelease", "modes": ["full-lineup", "summary-only"]},
        {"name": "corpus_snapshot_count", "kind": "CorpusSnapshot", "modes": ["full-lineup", "summary-only"]},
        {"name": "candidate_snapshot_count", "kind": "CandidateSnapshot", "modes": ["full-lineup", "summary-only"]},
        {"name": "unique_lineup_count", "kind": "Lineup", "modes": ["full-lineup"]},
        {"name": "selected_unique_lineup_count", "kind": "Lineup", "modes": ["summary-only"]},
        {"name": "selected_book_count", "kind": "SelectedBook", "modes": ["full-lineup", "summary-only"]},
        {"name": "science_release_count", "kind": "ScienceRelease", "modes": ["full-lineup", "summary-only"]},
        {"name": "verifier_release_count", "kind": "VerifierRelease", "modes": ["full-lineup", "summary-only"]},
        {"name": "deployment_attestation_count", "kind": "DeploymentAttestation", "modes": ["full-lineup", "summary-only"]},
        {"name": "fill_preset_count", "kind": "FillPreset", "modes": ["full-lineup", "summary-only"]},
        {"name": "admission_preset_count", "kind": "AdmissionPreset", "modes": ["full-lineup", "summary-only"]},
        {"name": "retrieval_preset_count", "kind": "RetrievalPreset", "modes": ["full-lineup", "summary-only"]},
        {"name": "strategy_bundle_count", "kind": "StrategyBundle", "modes": ["full-lineup", "summary-only"]},
        {"name": "experiment_run_count", "kind": "ExperimentRun", "modes": ["full-lineup", "summary-only"]},
        {"name": "experiment_cell_count", "kind": "ExperimentCell", "modes": ["full-lineup", "summary-only"]},
        {"name": "evaluation_count", "kind": "Evaluation", "modes": ["full-lineup", "summary-only"]},
        {"name": "fold_count", "kind": "Fold", "modes": ["full-lineup", "summary-only"]},
        {"name": "metric_set_count", "kind": "MetricSet", "modes": ["full-lineup", "summary-only"]},
        {"name": "trait_definition_count", "kind": "Trait", "modes": ["full-lineup", "summary-only"]},
        {"name": "cohort_count", "kind": "Cohort", "modes": ["full-lineup", "summary-only"]},
        {"name": "source_artifact_count", "kind": "SourceArtifact", "modes": ["full-lineup", "summary-only"]},
        {"name": "verification_receipt_count", "kind": "VerificationReceipt", "modes": ["full-lineup", "summary-only"]},
        {"name": "attempt_count", "kind": "Attempt", "modes": ["full-lineup", "summary-only"]},
        {"name": "promotion_decision_count", "kind": "PromotionDecision", "modes": ["full-lineup", "summary-only"]},
    ],
    # Exact relationship-count inputs: name -> {relationship, modes}.
    "exact_relationship_inputs": [
        {"name": "lineup_occurrence_count", "relationship": "MEMBER_OF_CORPUS", "modes": ["full-lineup"]},
        {"name": "lineup_arm_supply_count", "relationship": "SUPPLIED_BY_ARM", "modes": ["full-lineup"]},
        {"name": "trait_membership_count", "relationship": "HAS_TRAIT", "modes": ["full-lineup"]},
        {"name": "cohort_membership_count", "relationship": "MEMBER_OF_COHORT", "modes": ["full-lineup"]},
        {"name": "selected_lineup_occurrence_count", "relationship": "MEMBER_OF_CORPUS", "modes": ["summary-only"]},
        {"name": "selected_lineup_arm_supply_count", "relationship": "SUPPLIED_BY_ARM", "modes": ["summary-only"]},
        {"name": "selected_trait_membership_count", "relationship": "HAS_TRAIT", "modes": ["summary-only"]},
        {"name": "selected_cohort_membership_count", "relationship": "MEMBER_OF_COHORT", "modes": ["summary-only"]},
        {"name": "selected_book_membership_count", "relationship": "MEMBER_OF_BOOK", "modes": ["full-lineup", "summary-only"]},
        {"name": "plays_for_edge_count", "relationship": "PLAYS_FOR", "modes": ["full-lineup", "summary-only"]},
        {"name": "in_game_edge_count", "relationship": "IN_GAME", "modes": ["full-lineup", "summary-only"]},
        {"name": "derived_from_edge_count", "relationship": "DERIVED_FROM", "modes": ["full-lineup", "summary-only"]},
        {"name": "uses_source_edge_count", "relationship": "USES_SOURCE", "modes": ["full-lineup", "summary-only"]},
        {"name": "uses_world_release_edge_count", "relationship": "USES_WORLD_RELEASE", "modes": ["full-lineup", "summary-only"]},
        {"name": "generated_by_edge_count", "relationship": "GENERATED_BY", "modes": ["full-lineup", "summary-only"]},
        {"name": "verified_by_edge_count", "relationship": "VERIFIED_BY", "modes": ["full-lineup", "summary-only"]},
        {"name": "retried_as_edge_count", "relationship": "RETRIED_AS", "modes": ["full-lineup", "summary-only"]},
        {"name": "evaluated_in_edge_count", "relationship": "EVALUATED_IN", "modes": ["full-lineup", "summary-only"]},
        {"name": "evaluates_bundle_edge_count", "relationship": "EVALUATES_BUNDLE", "modes": ["full-lineup", "summary-only"]},
        {"name": "has_metric_edge_count", "relationship": "HAS_METRIC", "modes": ["full-lineup", "summary-only"]},
        {"name": "paired_against_edge_count", "relationship": "PAIRED_AGAINST", "modes": ["full-lineup", "summary-only"]},
        {"name": "decides_on_bundle_edge_count", "relationship": "DECIDES_ON_BUNDLE", "modes": ["full-lineup", "summary-only"]},
        {"name": "inferred_defender_exposure_edge_count", "relationship": "HAS_INFERRED_DEFENDER_EXPOSURE", "modes": ["full-lineup", "summary-only"]},
    ],
    "scalar_count_inputs": ["mean_string_property_bytes"],
    # Derived structural cardinalities (Phase 4 bundle/book law; production
    # nine-slot roster law for CONTAINS_PLAYER).
    "derived_relationship_types": ["ADMITTED_BY", "SELECTED_BY", "CONTAINS_PLAYER"],
    # Required endpoint populations per open relationship type.
    "relationship_endpoints": {
        "CONTAINS_PLAYER": {"sources": ["Lineup"], "targets": ["PlayerSlate"]},
        "MEMBER_OF_CORPUS": {"sources": ["Lineup"], "targets": ["CorpusSnapshot"]},
        "SUPPLIED_BY_ARM": {"sources": ["Lineup"], "targets": ["FillPreset"]},
        "HAS_TRAIT": {"sources": ["Lineup"], "targets": ["Trait"]},
        "MEMBER_OF_COHORT": {"sources": ["Lineup"], "targets": ["Cohort"]},
        "MEMBER_OF_BOOK": {"sources": ["Lineup"], "targets": ["SelectedBook"]},
        "PLAYS_FOR": {"sources": ["PlayerSlate"], "targets": ["TeamSlate"]},
        "IN_GAME": {"sources": ["TeamSlate"], "targets": ["Game"]},
        "ADMITTED_BY": {"sources": ["StrategyBundle"], "targets": ["AdmissionPreset"]},
        "SELECTED_BY": {"sources": ["StrategyBundle", "SelectedBook"], "targets": ["RetrievalPreset"]},
        "GENERATED_BY": {"sources": ["SelectedBook"], "targets": ["StrategyBundle"]},
        "DERIVED_FROM": {
            "sources": ["VerificationReceipt", "StrategyBundle", "CorpusSnapshot", "CandidateSnapshot", "SelectedBook"],
            "targets": ["SourceArtifact", "FillPreset", "CorpusSnapshot", "CandidateSnapshot"],
        },
        "USES_SOURCE": {"sources": ["ScienceRelease", "VerifierRelease", "CorpusSnapshot"], "targets": ["SourceArtifact"]},
        "USES_WORLD_RELEASE": {"sources": ["CorpusSnapshot", "CandidateSnapshot", "SelectedBook"], "targets": ["WorldRelease"]},
        "VERIFIED_BY": {"sources": ["SelectedBook", "CorpusSnapshot", "Attempt"], "targets": ["VerificationReceipt"]},
        "RETRIED_AS": {"sources": ["Attempt"], "targets": ["Attempt"]},
        "EVALUATED_IN": {"sources": ["Evaluation"], "targets": ["ExperimentRun", "Fold"]},
        "EVALUATES_BUNDLE": {"sources": ["ExperimentRun"], "targets": ["StrategyBundle"]},
        "HAS_METRIC": {"sources": ["ExperimentRun", "ExperimentCell", "Evaluation"], "targets": ["MetricSet"]},
        "PAIRED_AGAINST": {"sources": ["ExperimentCell", "Evaluation", "StrategyBundle"], "targets": ["ExperimentCell", "StrategyBundle"]},
        "DECIDES_ON_BUNDLE": {"sources": ["PromotionDecision"], "targets": ["StrategyBundle"]},
        "HAS_INFERRED_DEFENDER_EXPOSURE": {"sources": ["PlayerSlate"], "targets": ["PlayerSlate"]},
    },
    # Count-matched release manifests: name -> {count_input, kind}.
    "release_manifests": [
        {"name": "world_releases", "count_input": "world_release_count", "kind": "WorldRelease"},
        {"name": "science_releases", "count_input": "science_release_count", "kind": "ScienceRelease"},
        {"name": "verifier_releases", "count_input": "verifier_release_count", "kind": "VerifierRelease"},
        {"name": "deployment_attestations", "count_input": "deployment_attestation_count", "kind": "DeploymentAttestation"},
    ],
    "identity_inputs": [
        "combined_panel_index_identity",
        "r6_full_union_panel_freeze_identity",
        "source_universe_release_identity",
    ],
    "version_inputs": [
        "predecessor_graph_release_id", "graph_schema_version", "property_schema_version",
    ],
    "hash_inputs": ["r6_full_union_panel_self_sha256"],
    "parameter_inputs": [
        "provisioned_disk_bytes", "provisioned_heap_bytes",
        "provisioned_page_cache_bytes", "load_deadline_seconds",
        "rebuild_deadline_seconds",
    ],
}
SEMANTIC_CONTRACT: Final[Mapping[str, object]] = _freeze(_SEMANTIC_CONTRACT_CONTENT)  # type: ignore[assignment]
# Literal v1 digest of the semantic contract (including its live graph
# binding), pinned. A changed registry or graph contract is a NEW contract
# version with a new pinned digest.
SEMANTIC_CONTRACT_SHA256: Final = "18a0ddb1cb97fa674ed3cd7ce8a2491d16e373d9e49ef172a39b266916183bee"


def contract_digest_now() -> str:
    """Digest of the live semantic contract, recomputed on every call."""

    return canonical_sha256(SEMANTIC_CONTRACT)


def require_frozen_contract() -> Mapping[str, object]:
    """Fail closed unless the live contract hashes to its pinned digest AND
    its embedded graph binding equals the live graph contract exactly."""

    if contract_digest_now() != SEMANTIC_CONTRACT_SHA256:
        _fail("semantic contract content drifted from its frozen v1 digest")
    if _plain(SEMANTIC_CONTRACT["graph_binding"]) != graph_binding_now():
        _fail(
            "live graph contract differs from the semantic contract's graph "
            "binding (version, vocabulary, namespace, or property semantics)"
        )
    return SEMANTIC_CONTRACT


require_frozen_contract()

# Frozen read-only views (for callers and tests). The estimator itself
# consults require_frozen_contract() at use time.
RELATIONSHIP_ENDPOINTS: Final[Mapping[str, Mapping[str, tuple[str, ...]]]] = (
    SEMANTIC_CONTRACT["relationship_endpoints"]  # type: ignore[assignment]
)
DERIVED_RELATIONSHIP_TYPES: Final = frozenset(SEMANTIC_CONTRACT["derived_relationship_types"])  # type: ignore[arg-type]
RELEASE_MANIFESTS: Final[tuple[Mapping[str, str], ...]] = SEMANTIC_CONTRACT["release_manifests"]  # type: ignore[assignment]
NODE_COUNT_INPUTS: Final[tuple[Mapping[str, object], ...]] = SEMANTIC_CONTRACT["node_count_inputs"]  # type: ignore[assignment]
EXACT_RELATIONSHIP_INPUTS: Final[tuple[Mapping[str, object], ...]] = SEMANTIC_CONTRACT["exact_relationship_inputs"]  # type: ignore[assignment]


# ------------------------------------------------------------------ #
# Required inputs — the exact list the lead must supply.               #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class RequiredInput:
    name: str
    kind: Literal["count", "identity", "release_manifest", "parameter", "version", "hash"]
    description: str
    modes: tuple[GraphMode, ...]


# Human descriptions are documentation, not semantics: they are keyed by
# name here and deliberately excluded from the semantic contract digest.
_DESCRIPTIONS: Final[dict[str, str]] = {
    "accepted_slate_count": "terminal accepted slates in the panel",
    "slate_snapshot_count": "slate snapshots (source/pricing snapshots) bound to accepted slates",
    "contest_count": "registered contests bound to accepted slates",
    "game_count": "games across accepted slates",
    "team_slate_count": "team-slate rows across accepted slates",
    "player_slate_count": "player-slate rows across accepted slates",
    "world_release_count": "world releases (identity pointers; matrices never load)",
    "corpus_snapshot_count": "corpus snapshots",
    "candidate_snapshot_count": "candidate (admitted) snapshots",
    "unique_lineup_count": "distinct roster_ids across the accepted corpus",
    "selected_unique_lineup_count": "distinct lineups appearing in any selected book",
    "selected_book_count": "exact selected books (bundle x slate x budget)",
    "science_release_count": "science releases",
    "verifier_release_count": "verifier releases",
    "deployment_attestation_count": "deployment attestations",
    "fill_preset_count": "registered fill presets",
    "admission_preset_count": "registered admission presets",
    "retrieval_preset_count": "registered retrieval presets",
    "strategy_bundle_count": "registered strategy bundles",
    "experiment_run_count": "experiment runs bound to the release",
    "experiment_cell_count": "experiment cells",
    "evaluation_count": "evaluations (books-frozen or later)",
    "fold_count": "fold definitions",
    "metric_set_count": "metric-set nodes",
    "trait_definition_count": "versioned trait definitions",
    "cohort_count": "cohort definitions",
    "source_artifact_count": "source artifact identities",
    "verification_receipt_count": "verification receipts",
    "attempt_count": "attempt records",
    "promotion_decision_count": "promotion decisions",
    "lineup_occurrence_count": "corpus memberships incl. cross-arm duplicates",
    "lineup_arm_supply_count": "(lineup, source arm) supply pairs",
    "trait_membership_count": "(lineup, trait) memberships, sparse",
    "cohort_membership_count": "(lineup, cohort) memberships",
    "selected_lineup_occurrence_count": "corpus memberships of selected lineups only",
    "selected_lineup_arm_supply_count": "(selected lineup, source arm) supply pairs",
    "selected_trait_membership_count": "(selected lineup, trait) memberships",
    "selected_cohort_membership_count": "(selected lineup, cohort) memberships",
    "selected_book_membership_count": "(book, lineup) memberships across all books",
    "plays_for_edge_count": "PLAYS_FOR relationships (player-slate -> team-slate)",
    "in_game_edge_count": "IN_GAME relationships (team-slate -> game)",
    "derived_from_edge_count": "DERIVED_FROM lineage relationships",
    "uses_source_edge_count": "USES_SOURCE lineage relationships",
    "uses_world_release_edge_count": "USES_WORLD_RELEASE lineage relationships",
    "generated_by_edge_count": "GENERATED_BY relationships (book -> bundle, ...)",
    "verified_by_edge_count": "VERIFIED_BY relationships",
    "retried_as_edge_count": "RETRIED_AS relationships",
    "evaluated_in_edge_count": "EVALUATED_IN relationships",
    "evaluates_bundle_edge_count": "EVALUATES_BUNDLE relationships",
    "has_metric_edge_count": "HAS_METRIC relationships",
    "paired_against_edge_count": "PAIRED_AGAINST relationships",
    "decides_on_bundle_edge_count": "DECIDES_ON_BUNDLE relationships",
    "inferred_defender_exposure_edge_count": "HAS_INFERRED_DEFENDER_EXPOSURE relationships (qualified)",
    "mean_string_property_bytes": "measured mean UTF-8 bytes of string properties in the release",
    "combined_panel_index_identity": "foundry-v12-combined-panel-index/v1 object identity",
    "r6_full_union_panel_freeze_identity": (
        "accepted R6 full-union panel-freeze/release object identity "
        "(corpus-r6-full-union-freezes/<freeze>/panel-freeze.json; "
        "outcome-blind, complete=true; 54 slates / 2,592 books / 7,776 prefixes census)"
    ),
    "source_universe_release_identity": "artifact-supported source-universe release identity",
    "predecessor_graph_release_id": "predecessor graph release id or null",
    "graph_schema_version": f"must equal {graph.GRAPH_SCHEMA_VERSION}",
    "property_schema_version": "must equal the content hash of the complete positive property schema",
    "r6_full_union_panel_self_sha256": "panel self-hash recorded inside the accepted R6 full-union panel-freeze root",
    "provisioned_disk_bytes": "disk available to the graph store",
    "provisioned_heap_bytes": "JVM heap for the graph service",
    "provisioned_page_cache_bytes": "page cache for the graph store",
    "load_deadline_seconds": "zero-state streamed load deadline",
    "rebuild_deadline_seconds": "zero-state rebuild deadline incl. indexes",
}


def _modes_of(entry: Mapping[str, object]) -> tuple[GraphMode, ...]:
    return tuple(entry["modes"])  # type: ignore[arg-type,return-value]


REQUIRED_COUNTS: Final[tuple[RequiredInput, ...]] = (
    *(
        RequiredInput(str(e["name"]), "count", f"[{e['kind']}] {_DESCRIPTIONS[str(e['name'])]}", _modes_of(e))
        for e in NODE_COUNT_INPUTS
    ),
    *(
        RequiredInput(str(e["name"]), "count", f"[{e['relationship']}] {_DESCRIPTIONS[str(e['name'])]}", _modes_of(e))
        for e in EXACT_RELATIONSHIP_INPUTS
    ),
    *(
        RequiredInput(name, "count", _DESCRIPTIONS[name], MODES)
        for name in SEMANTIC_CONTRACT["scalar_count_inputs"]  # type: ignore[union-attr]
    ),
)
REQUIRED_IDENTITIES: Final[tuple[RequiredInput, ...]] = tuple(
    RequiredInput(name, "identity", _DESCRIPTIONS[name], MODES)
    for name in SEMANTIC_CONTRACT["identity_inputs"]  # type: ignore[union-attr]
)
REQUIRED_RELEASE_MANIFESTS: Final[tuple[RequiredInput, ...]] = tuple(
    RequiredInput(
        str(e["name"]), "release_manifest",
        f"[{e['kind']}] list of {{release_id, identity}} whose length equals {e['count_input']}",
        MODES,
    )
    for e in RELEASE_MANIFESTS
)
REQUIRED_VERSIONS: Final[tuple[RequiredInput, ...]] = tuple(
    RequiredInput(name, "version", _DESCRIPTIONS[name], MODES)
    for name in SEMANTIC_CONTRACT["version_inputs"]  # type: ignore[union-attr]
)
REQUIRED_HASHES: Final[tuple[RequiredInput, ...]] = tuple(
    RequiredInput(name, "hash", _DESCRIPTIONS[name], MODES)
    for name in SEMANTIC_CONTRACT["hash_inputs"]  # type: ignore[union-attr]
)
REQUIRED_PARAMETERS: Final[tuple[RequiredInput, ...]] = tuple(
    RequiredInput(name, "parameter", _DESCRIPTIONS[name], MODES)
    for name in SEMANTIC_CONTRACT["parameter_inputs"]  # type: ignore[union-attr]
)


def required_inputs_manifest() -> list[dict[str, object]]:
    """The exact, ordered list of inputs the lead must supply."""

    contract = require_frozen_contract()
    all_modes = list(contract["modes"])  # type: ignore[arg-type]
    manifest: list[dict[str, object]] = []
    for entry in contract["node_count_inputs"]:  # type: ignore[union-attr]
        name = str(entry["name"])  # type: ignore[index]
        manifest.append({"name": name, "kind": "count", "description": f"[{entry['kind']}] {_DESCRIPTIONS[name]}", "modes": list(entry["modes"])})  # type: ignore[index]
    for entry in contract["exact_relationship_inputs"]:  # type: ignore[union-attr]
        name = str(entry["name"])  # type: ignore[index]
        manifest.append({"name": name, "kind": "count", "description": f"[{entry['relationship']}] {_DESCRIPTIONS[name]}", "modes": list(entry["modes"])})  # type: ignore[index]
    for name in contract["scalar_count_inputs"]:  # type: ignore[union-attr]
        manifest.append({"name": str(name), "kind": "count", "description": _DESCRIPTIONS[str(name)], "modes": all_modes})
    for name in contract["identity_inputs"]:  # type: ignore[union-attr]
        manifest.append({"name": str(name), "kind": "identity", "description": _DESCRIPTIONS[str(name)], "modes": all_modes})
    for entry in contract["release_manifests"]:  # type: ignore[union-attr]
        manifest.append({
            "name": str(entry["name"]), "kind": "release_manifest",  # type: ignore[index]
            "description": f"[{entry['kind']}] list of {{release_id, identity}} whose length equals {entry['count_input']}",  # type: ignore[index]
            "modes": all_modes,
        })
    for name in contract["version_inputs"]:  # type: ignore[union-attr]
        manifest.append({"name": str(name), "kind": "version", "description": _DESCRIPTIONS[str(name)], "modes": all_modes})
    for name in contract["hash_inputs"]:  # type: ignore[union-attr]
        manifest.append({"name": str(name), "kind": "hash", "description": _DESCRIPTIONS[str(name)], "modes": all_modes})
    for name in contract["parameter_inputs"]:  # type: ignore[union-attr]
        manifest.append({"name": str(name), "kind": "parameter", "description": _DESCRIPTIONS[str(name)], "modes": all_modes})
    return manifest


def excluded_from_graph() -> tuple[str, ...]:
    return tuple(require_frozen_contract()["excluded_from_graph"])  # type: ignore[arg-type]


# ------------------------------------------------------------------ #
# Input validation                                                      #
# ------------------------------------------------------------------ #

def _count(value: object, *, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        _fail(f"{label} is not an exact integer")
    if value < 0 or value > MAX_COUNT:
        _fail(f"{label} is outside [0, {MAX_COUNT}]")
    return value


def _identity(value: object, *, label: str, authority: InputAuthority) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} is not a mapping")
    row = dict(value)
    if set(row) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} must carry exactly uri/generation/sha256/bytes")
    uri = row["uri"]
    if (
        not isinstance(uri, str)
        or not uri.startswith("gs://")
        or len(uri.encode("utf-8")) > MAX_URI_BYTES
        or any(ch.isspace() or ord(ch) < 32 for ch in uri)
    ):
        _fail(f"{label}.uri is not a bounded gs:// uri")
    bucket, separator, object_name = uri[5:].partition("/")
    if not separator or not _valid_gcs_bucket(bucket) or not object_name or object_name.endswith("/") or "//" in object_name:
        _fail(f"{label}.uri is not a real gs://bucket/object uri")
    synthetic = uri.startswith(SYNTHETIC_URI_PREFIX)
    if authority == "lead-supplied-terminal" and synthetic:
        _fail(f"{label} is a synthetic identity; lead-supplied inputs may not carry one")
    if authority == "synthetic-fixture" and not synthetic:
        _fail(f"{label} is a non-synthetic identity inside fixture-authority inputs")
    generation = row["generation"]
    if (
        not isinstance(generation, str)
        or not generation.isdigit()
        or len(generation) > 32
        or int(generation) <= 0
        or str(int(generation)) != generation
    ):
        _fail(f"{label}.generation is not bounded positive digits")
    digest = row["sha256"]
    if not isinstance(digest, str) or _SHA.fullmatch(digest) is None:
        _fail(f"{label}.sha256 is not 64-hex")
    byte_count = row["bytes"]
    if (
        not isinstance(byte_count, int)
        or isinstance(byte_count, bool)
        or not 0 < byte_count <= MAX_IDENTITY_OBJECT_BYTES
    ):
        _fail(f"{label}.bytes is not within (0, {MAX_IDENTITY_OBJECT_BYTES}]")
    return {"uri": uri, "generation": generation, "sha256": digest, "bytes": byte_count}


_GCS_BUCKET_CHARS: Final = re.compile(r"^[a-z0-9][a-z0-9._-]*[a-z0-9]$")
_GCS_MISSPELLING_MAP: Final = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t"})


def _valid_gcs_bucket(bucket: str) -> bool:
    """GCS bucket-name grammar: 3-63 chars, or up to 222 when dotted with
    every dot component 1-63 chars; lowercase letters, digits, dashes,
    underscores, dots; no IP-literal names; no ``goog`` prefix; no
    ``google`` or close misspellings (digit-for-letter substitutions)."""

    if _GCS_BUCKET_CHARS.fullmatch(bucket) is None:
        return False
    components = bucket.split(".")
    if any(not 1 <= len(part) <= 63 for part in components):
        return False
    limit = 222 if len(components) > 1 else 63
    if not 3 <= len(bucket) <= limit:
        return False
    if ".." in bucket or ".-" in bucket or "-." in bucket:
        return False
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", bucket) is not None:
        return False
    normalized = bucket.translate(_GCS_MISSPELLING_MAP)
    if bucket.startswith("goog") or normalized.startswith("goog"):
        return False
    if "google" in bucket or "google" in normalized:
        return False
    return True


def _utc(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        _fail(f"{label} is not second-precision UTC")
    try:
        _dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        _fail(f"{label} is not a calendar-valid UTC timestamp")
    return value


def _canonical_id(value: object, *, label: str, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        _fail(f"{label} is not a canonical id")
    return value


def _sha(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA.fullmatch(value) is None:
        _fail(f"{label} is not 64-hex")
    return value


def _coherence(counts: Mapping[str, int]) -> None:
    def require(condition: bool, message: str) -> None:
        if not condition:
            _fail(message)

    full_unique = counts["unique_lineup_count"]
    sel_unique = counts["selected_unique_lineup_count"]
    require(sel_unique <= full_unique, "selected_unique_lineup_count exceeds unique_lineup_count")
    require(counts["lineup_occurrence_count"] >= full_unique, "lineup_occurrence_count is below unique_lineup_count")
    require(counts["lineup_arm_supply_count"] >= full_unique, "lineup_arm_supply_count is below unique_lineup_count")
    for selected, full, name in (
        ("selected_lineup_occurrence_count", "lineup_occurrence_count", "occurrence"),
        ("selected_lineup_arm_supply_count", "lineup_arm_supply_count", "arm supply"),
        ("selected_trait_membership_count", "trait_membership_count", "trait membership"),
        ("selected_cohort_membership_count", "cohort_membership_count", "cohort membership"),
    ):
        require(counts[selected] <= counts[full], f"{selected} exceeds {full}")
    require(
        counts["selected_lineup_occurrence_count"] >= sel_unique,
        "selected_lineup_occurrence_count is below selected_unique_lineup_count",
    )
    require(
        counts["selected_lineup_arm_supply_count"] >= sel_unique,
        "selected_lineup_arm_supply_count is below selected_unique_lineup_count",
    )
    books = counts["selected_book_count"]
    require(
        (books == 0) == (counts["selected_book_membership_count"] == 0),
        "selected books and book memberships must be jointly zero or jointly positive",
    )
    require(
        counts["selected_book_membership_count"] >= books,
        "selected_book_membership_count is below selected_book_count",
    )
    require(
        counts["selected_book_membership_count"] >= sel_unique,
        "selected_book_membership_count is below selected_unique_lineup_count",
    )
    require(
        books == 0 or sel_unique > 0,
        "selected books exist but selected_unique_lineup_count is zero",
    )
    require(
        counts["generated_by_edge_count"] >= books,
        "generated_by_edge_count is below selected_book_count (each book is GENERATED_BY a bundle)",
    )
    require(
        books == 0 or counts["strategy_bundle_count"] > 0,
        "selected books exist without any strategy bundle",
    )
    require(counts["mean_string_property_bytes"] > 0, "mean_string_property_bytes must be positive")


def inputs_assertion_digest(packet: Mapping[str, object]) -> str:
    """Content-binding assertion digest for a packet — NOT an approval.

    digest = sha256(canonical {"subject": INPUTS_ASSERTION_SUBJECT,
    "inputs_sha256": <digest of the NORMALIZED packet body>}). The body is
    normalized exactly as validation normalizes it (release manifests
    sorted by release id, canonical key order), so entry order never
    changes the digest. Anyone holding the packet can compute it; it
    authenticates nobody and grants nothing.
    """

    body = _normalize_packet(packet)
    return canonical_sha256({
        "subject": INPUTS_ASSERTION_SUBJECT,
        "inputs_sha256": canonical_sha256(body),
    })


def _release_manifest(
    value: object, *, label: str, authority: InputAuthority, expected_count: int,
) -> list[dict[str, object]]:
    if not isinstance(value, (list, tuple)):
        _fail(f"{label} is not a list")
    if len(value) > MAX_RELEASE_MANIFEST_ENTRIES:
        _fail(f"{label} exceeds {MAX_RELEASE_MANIFEST_ENTRIES} entries")
    if len(value) != expected_count:
        _fail(
            f"{label} carries {len(value)} entries but its count input is "
            f"{expected_count}; release counts must be bound to identities"
        )
    entries: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_identities: set[tuple[str, str]] = set()
    for index, entry in enumerate(value):
        if not isinstance(entry, Mapping) or set(entry) != {"release_id", "identity"}:
            _fail(f"{label}[{index}] must carry exactly release_id/identity")
        release_id = _canonical_id(entry["release_id"], label=f"{label}[{index}].release_id")
        identity = _identity(
            entry["identity"], label=f"{label}[{index}].identity", authority=authority
        )
        key = (str(identity["uri"]), str(identity["generation"]))
        if release_id in seen_ids or key in seen_identities:
            _fail(f"{label}[{index}] repeats a release id or object identity")
        seen_ids.add(str(release_id))
        seen_identities.add(key)
        entries.append({"release_id": release_id, "identity": identity})
    entries.sort(key=lambda item: str(item["release_id"]))
    return entries


def _normalize_packet(value: Mapping[str, object]) -> dict[str, object]:
    """Validate and canonicalize the packet body against the frozen
    contract (the sole use-time authority). Assertion and approval-slot
    checks are applied by validate_capacity_inputs on top of this."""

    contract = require_frozen_contract()
    packet = dict(value)
    expected_keys = {
        "schema_version", "authority", "counts", "identities",
        "release_manifests", "versions", "hashes", "parameters",
        "created_at_utc",
    }
    optional_keys = {
        "inputs_assertion_sha256", "inputs_sha256",
        "lead_approval_receipt_identity",
    }
    if not expected_keys <= set(packet) or not set(packet) <= expected_keys | optional_keys:
        _fail("capacity inputs must carry exactly the registered packet keys")
    if packet["schema_version"] != CAPACITY_INPUTS_SCHEMA:
        _fail("capacity inputs schema differs")
    authority = packet["authority"]
    if authority not in ("synthetic-fixture", "lead-supplied-terminal"):
        _fail("capacity inputs authority is not registered")
    created = _utc(packet["created_at_utc"], label="created_at_utc")

    counts_in = packet["counts"]
    if not isinstance(counts_in, Mapping):
        _fail("counts is not a mapping")
    required_count_names = [
        *(str(e["name"]) for e in contract["node_count_inputs"]),  # type: ignore[index,union-attr]
        *(str(e["name"]) for e in contract["exact_relationship_inputs"]),  # type: ignore[index,union-attr]
        *(str(n) for n in contract["scalar_count_inputs"]),  # type: ignore[union-attr]
    ]
    missing = [name for name in required_count_names if name not in counts_in]
    if missing:
        _fail(f"required counts absent: {missing}")
    extra = sorted(set(counts_in) - set(required_count_names))
    if extra:
        _fail(f"unregistered counts present: {extra}")
    counts = {name: _count(counts_in[name], label=f"counts.{name}") for name in required_count_names}
    _coherence(counts)

    identities_in = packet["identities"]
    if not isinstance(identities_in, Mapping):
        _fail("identities is not a mapping")
    identity_names = [str(n) for n in contract["identity_inputs"]]  # type: ignore[union-attr]
    if set(identities_in) != set(identity_names):
        _fail(f"identities must carry exactly {identity_names}")
    identities = {
        name: _identity(identities_in[name], label=f"identities.{name}", authority=authority)
        for name in identity_names
    }

    manifests_in = packet["release_manifests"]
    if not isinstance(manifests_in, Mapping):
        _fail("release_manifests is not a mapping")
    manifest_specs = contract["release_manifests"]
    manifest_names = [str(spec["name"]) for spec in manifest_specs]  # type: ignore[index,union-attr]
    if set(manifests_in) != set(manifest_names):
        _fail(f"release_manifests must carry exactly {manifest_names}")
    release_manifests = {
        str(spec["name"]): _release_manifest(  # type: ignore[index]
            manifests_in[str(spec["name"])], label=f"release_manifests.{spec['name']}",  # type: ignore[index]
            authority=authority, expected_count=counts[str(spec["count_input"])],  # type: ignore[index]
        )
        for spec in manifest_specs  # type: ignore[union-attr]
    }

    versions_in = packet["versions"]
    if not isinstance(versions_in, Mapping):
        _fail("versions is not a mapping")
    version_names = [str(n) for n in contract["version_inputs"]]  # type: ignore[union-attr]
    if set(versions_in) != set(version_names):
        _fail(f"versions must carry exactly {version_names}")
    binding = contract["graph_binding"]
    if versions_in["graph_schema_version"] != binding["graph_schema_version"]:  # type: ignore[index]
        _fail("graph_schema_version differs from the contracts module")
    if versions_in["property_schema_version"] != binding["property_schema_version"]:  # type: ignore[index]
        _fail("property_schema_version differs from the contracts module")
    versions = {
        "predecessor_graph_release_id": _canonical_id(
            versions_in["predecessor_graph_release_id"],
            label="versions.predecessor_graph_release_id", nullable=True,
        ),
        "graph_schema_version": str(binding["graph_schema_version"]),  # type: ignore[index]
        "property_schema_version": str(binding["property_schema_version"]),  # type: ignore[index]
    }

    hashes_in = packet["hashes"]
    if not isinstance(hashes_in, Mapping):
        _fail("hashes is not a mapping")
    hash_names = [str(n) for n in contract["hash_inputs"]]  # type: ignore[union-attr]
    if set(hashes_in) != set(hash_names):
        _fail(f"hashes must carry exactly {hash_names}")
    hashes = {name: _sha(hashes_in[name], label=f"hashes.{name}") for name in hash_names}

    parameters_in = packet["parameters"]
    if not isinstance(parameters_in, Mapping):
        _fail("parameters is not a mapping")
    parameter_names = [str(n) for n in contract["parameter_inputs"]]  # type: ignore[union-attr]
    if set(parameters_in) != set(parameter_names):
        _fail(f"parameters must carry exactly {parameter_names}")
    parameters = {name: _count(parameters_in[name], label=f"parameters.{name}") for name in parameter_names}
    for name in parameter_names:
        if parameters[name] <= 0:
            _fail(f"parameters.{name} must be positive")

    return {
        "schema_version": CAPACITY_INPUTS_SCHEMA,
        "authority": authority,
        "counts": counts,
        "identities": identities,
        "release_manifests": release_manifests,
        "versions": versions,
        "hashes": hashes,
        "parameters": parameters,
        "created_at_utc": created,
    }


def validate_capacity_inputs(value: Mapping[str, object]) -> dict[str, object]:
    """Validate the input packet; every contract-required name must be present."""

    packet = dict(value)
    body = _normalize_packet(packet)
    authority = body["authority"]
    if packet.get("lead_approval_receipt_identity") is not None:
        _fail(
            "lead_approval_receipt_identity is reserved: this offline phase "
            "cannot authenticate an approval; supply none"
        )
    assertion = packet.get("inputs_assertion_sha256")
    if assertion is not None:
        _sha(assertion, label="inputs_assertion_sha256")
        if authority == "synthetic-fixture":
            _fail("fixture-authority inputs may not carry an assertion digest")
        if assertion != inputs_assertion_digest(body):
            _fail(
                "inputs_assertion_sha256 does not bind the canonical inputs "
                "subject"
            )
    digest = canonical_sha256({**body, "inputs_assertion_sha256": assertion})
    retained = packet.get("inputs_sha256")
    if retained is not None and retained != digest:
        _fail("inputs_sha256 differs from the canonical packet")
    return {
        **body,
        "inputs_assertion_sha256": assertion,
        "lead_approval_receipt_identity": None,
        "inputs_sha256": digest,
    }


# ------------------------------------------------------------------ #
# Estimation                                                            #
# ------------------------------------------------------------------ #

def _string_rule_count(rules: Mapping[str, object]) -> int:
    return sum(
        1 for rule in rules.values()
        if getattr(rule, "value_type", "") in ("string", "string_list")
    )


def _mode_elements(counts: Mapping[str, int], mode: str) -> tuple[dict[str, int], dict[str, int]]:
    contract = require_frozen_contract()
    if mode not in contract["modes"]:  # type: ignore[operator]
        _fail(f"graph mode {mode!r} is not registered")
    full = mode == "full-lineup"
    slots = int(contract["roster_slots"])  # type: ignore[arg-type]
    lineups = counts["unique_lineup_count"] if full else counts["selected_unique_lineup_count"]
    nodes: dict[str, int] = {}
    for entry in contract["node_count_inputs"]:  # type: ignore[union-attr]
        name = str(entry["name"])  # type: ignore[index]
        if entry["kind"] == "Lineup":  # type: ignore[index]
            continue
        if mode not in entry["modes"]:  # type: ignore[index,operator]
            continue
        nodes[str(entry["kind"])] = counts[name]  # type: ignore[index]
    nodes["Lineup"] = lineups

    bundles = counts["strategy_bundle_count"]
    books = counts["selected_book_count"]
    relationships: dict[str, int] = {
        # Derived structural cardinalities. CONTAINS_PLAYER = roster_slots per
        # loaded lineup is the production Phase 5 law (the Phase 4 synthetic
        # fixture carries one per lineup); ADMITTED_BY/SELECTED_BY follow the
        # Phase 4 bundle/book endpoint semantics exactly.
        "CONTAINS_PLAYER": slots * lineups,
        "ADMITTED_BY": bundles,             # StrategyBundle -> AdmissionPreset
        "SELECTED_BY": bundles + books,     # bundle -> retrieval, book -> retrieval
    }
    if set(relationships) != set(contract["derived_relationship_types"]):  # type: ignore[arg-type]
        _fail("derived relationship set differs from the semantic contract")
    for entry in contract["exact_relationship_inputs"]:  # type: ignore[union-attr]
        if mode not in entry["modes"]:  # type: ignore[index,operator]
            continue
        relationships[str(entry["relationship"])] = counts[str(entry["name"])]  # type: ignore[index]

    closed_kinds = set(contract["closed_node_kinds"])  # type: ignore[arg-type]
    closed_relationships = set(contract["closed_relationship_types"])  # type: ignore[arg-type]
    unknown = (set(nodes) - graph.NODE_KINDS) | (set(relationships) - graph.RELATIONSHIP_TYPES)
    if unknown:  # pragma: no cover - vocabulary drift guard
        _fail(f"estimator references unregistered vocabulary {sorted(unknown)}")
    closed = (set(nodes) & closed_kinds) | (set(relationships) & closed_relationships)
    if closed:  # pragma: no cover - firewall guard
        _fail(f"estimator models closed realized vocabulary {sorted(closed)}")
    endpoints = contract["relationship_endpoints"]
    missing_endpoint_schema = set(relationships) - set(endpoints)  # type: ignore[arg-type]
    if missing_endpoint_schema:  # pragma: no cover - vocabulary drift guard
        _fail(f"relationships lack an endpoint schema: {sorted(missing_endpoint_schema)}")
    for relationship, count in relationships.items():
        if count <= 0:
            continue
        spec = endpoints[relationship]  # type: ignore[index]
        sources = tuple(spec["sources"])  # type: ignore[index]
        targets = tuple(spec["targets"])  # type: ignore[index]
        if not any(nodes.get(kind, 0) > 0 for kind in sources):
            _fail(
                f"{relationship} has {count} relationships in {mode} but no "
                f"populated source kind among {list(sources)}"
            )
        if not any(nodes.get(kind, 0) > 0 for kind in targets):
            _fail(
                f"{relationship} has {count} relationships in {mode} but no "
                f"populated target kind among {list(targets)}"
            )
    return nodes, relationships


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def estimate_mode(counts: Mapping[str, int], parameters: Mapping[str, int], mode: str) -> dict[str, object]:
    law = require_frozen_law()
    nodes, relationships = _mode_elements(counts, mode)

    node_count = sum(nodes.values())
    relationship_count = sum(relationships.values())
    property_count = 0
    string_property_count = 0
    for kind, count in nodes.items():
        rules = graph.NODE_PROPERTY_SCHEMA.get(kind, {})
        property_count += len(rules) * count
        string_property_count += _string_rule_count(rules) * count
    for relationship, count in relationships.items():
        rules = graph.RELATIONSHIP_PROPERTY_SCHEMA.get(relationship, {})
        property_count += len(rules) * count
        string_property_count += _string_rule_count(rules) * count

    string_chunk = int(law["string_chunk_bytes"])
    chunks_per_string = _ceil_div(int(counts["mean_string_property_bytes"]), string_chunk)
    raw_bytes = (
        node_count * int(law["bytes_per_node"])
        + relationship_count * int(law["bytes_per_relationship"])
        + property_count * int(law["bytes_per_property"])
        + string_property_count * chunks_per_string * string_chunk
    )
    estimated_store_bytes = _ceil_div(
        raw_bytes * int(law["index_and_overhead_factor_permille"]), 1_000
    )
    element_count = node_count + relationship_count
    batch_count = _ceil_div(node_count, int(law["batch_size"])) + _ceil_div(
        relationship_count, int(law["batch_size"])
    )
    estimated_load_seconds = _ceil_div(batch_count * int(law["batch_deadline_ms"]), 1_000)
    estimated_index_seconds = _ceil_div(
        node_count * int(law["index_build_seconds_per_million_nodes"]), 1_000_000
    )
    estimated_rebuild_seconds = estimated_load_seconds + estimated_index_seconds

    disk_ceiling = _ceil_div(
        parameters["provisioned_disk_bytes"] * int(law["disk_safety_fraction_permille"]), 1_000
    )
    page_cache_ceiling = _ceil_div(
        parameters["provisioned_page_cache_bytes"] * int(law["page_cache_fraction_permille"]), 1_000
    )
    violations: list[str] = []
    if estimated_store_bytes > disk_ceiling:
        violations.append("estimated_store_bytes exceeds the disk safety ceiling")
    if estimated_store_bytes > page_cache_ceiling:
        violations.append("estimated_store_bytes exceeds the page-cache ceiling")
    if parameters["provisioned_heap_bytes"] < int(law["heap_floor_bytes"]):
        violations.append("provisioned_heap_bytes is below the heap floor")
    if element_count > int(law["max_graph_elements"]):
        violations.append("element_count exceeds max_graph_elements")
    if estimated_load_seconds > parameters["load_deadline_seconds"]:
        violations.append("estimated_load_seconds exceeds load_deadline_seconds")
    if estimated_rebuild_seconds > parameters["rebuild_deadline_seconds"]:
        violations.append("estimated_rebuild_seconds exceeds rebuild_deadline_seconds")

    return {
        "mode": mode,
        "full_corpus_traversal_available": mode == "full-lineup",
        "node_count": node_count,
        "relationship_count": relationship_count,
        "property_count": property_count,
        "string_property_count": string_property_count,
        "element_count": element_count,
        "node_kinds": {kind: nodes[kind] for kind in sorted(nodes)},
        "relationship_types": {
            relationship: relationships[relationship]
            for relationship in sorted(relationships)
        },
        "derived_relationship_types": sorted(require_frozen_contract()["derived_relationship_types"]),  # type: ignore[arg-type]
        "estimated_raw_bytes": raw_bytes,
        "estimated_store_bytes": estimated_store_bytes,
        "batch_count": batch_count,
        "estimated_load_seconds": estimated_load_seconds,
        "estimated_index_seconds": estimated_index_seconds,
        "estimated_rebuild_seconds": estimated_rebuild_seconds,
        "ceilings": {
            "disk_ceiling_bytes": disk_ceiling,
            "page_cache_ceiling_bytes": page_cache_ceiling,
            "heap_floor_bytes": int(law["heap_floor_bytes"]),
            "max_graph_elements": int(law["max_graph_elements"]),
            "load_deadline_seconds": parameters["load_deadline_seconds"],
            "rebuild_deadline_seconds": parameters["rebuild_deadline_seconds"],
        },
        "feasible": not violations,
        "violations": violations,
        "observed": {
            "store_bytes": None,
            "load_seconds": None,
            "rebuild_seconds": None,
            "query_p50_ms": None,
            "query_p95_ms": None,
            "note": "observed values arrive only from a later measured live receipt",
        },
    }


# ------------------------------------------------------------------ #
# Receipt                                                               #
# ------------------------------------------------------------------ #

def build_capacity_receipt(inputs: Mapping[str, object], *, created_at_utc: str) -> dict[str, object]:
    retained = validate_capacity_inputs(inputs)
    created_at_utc = _utc(created_at_utc, label="receipt created_at_utc")
    contract = require_frozen_contract()
    counts = retained["counts"]
    parameters = retained["parameters"]
    estimates = {
        str(mode): estimate_mode(counts, parameters, str(mode))
        for mode in contract["modes"]  # type: ignore[union-attr]
    }
    full_ok = bool(estimates["full-lineup"]["feasible"])
    summary_ok = bool(estimates["summary-only"]["feasible"])
    if full_ok and summary_ok:
        forced_mode: str | None = None
    elif summary_ok:
        forced_mode = "summary-only"
    else:
        forced_mode = "none-feasible"

    asserted = (
        retained["authority"] == "lead-supplied-terminal"
        and retained["inputs_assertion_sha256"] is not None
    )
    approval = {
        "status": "not-authenticated",
        "receipt_identity": None,
        "note": (
            "the inputs assertion digest binds content only; a detached "
            "immutable lead approval receipt identity is required to select "
            "a mode and is not accepted in this offline phase"
        ),
    }
    if asserted:
        if forced_mode == "none-feasible":
            recommended: str | None = None
        elif forced_mode == "summary-only":
            recommended = "summary-only"
        else:
            recommended = "full-lineup"
        decision = {
            "state": "estimated-pending-approval",
            "recommended_mode": recommended,
            "approval": approval,
            "requires_lead_approval": True,
            "self_activating": False,
            "note": (
                "an estimate-derived recommendation only; nothing here "
                "approves, selects, or activates a mode"
            ),
        }
    else:
        decision = {
            "state": "pending-lead-inputs",
            "recommended_mode": None,
            "approval": approval,
            "requires_lead_approval": True,
            "self_activating": False,
            "note": (
                "no mode is chosen until lead-authority terminal counts, "
                "identities, and a bound inputs assertion are supplied"
            ),
        }

    body = {
        "schema_version": CAPACITY_RECEIPT_SCHEMA,
        "created_at_utc": created_at_utc,
        "estimation_law": {
            **dict(require_frozen_law()),
            "estimation_law_sha256": law_digest_now(),
        },
        "semantic_contract": {
            **_plain(require_frozen_contract()),  # type: ignore[dict-item]
            "semantic_contract_sha256": contract_digest_now(),
        },
        "inputs": retained,
        "estimates": estimates,
        "forced_mode": forced_mode,
        "decision": decision,
        "required_inputs_manifest": required_inputs_manifest(),
        "closed_vocabulary": {
            "node_kinds": list(contract["closed_node_kinds"]),  # type: ignore[arg-type]
            "relationship_types": list(contract["closed_relationship_types"]),  # type: ignore[arg-type]
            "note": "realized-only vocabulary is closed in v1 and contributes no elements",
        },
        "excluded_from_graph": list(contract["excluded_from_graph"]),  # type: ignore[arg-type]
        "labels_law": (
            "summary-only is never labeled full; full-lineup applies only "
            "when every declared accepted lineup loads"
        ),
    }
    return {**body, "receipt_sha256": canonical_sha256(body)}


def validate_capacity_receipt(value: Mapping[str, object]) -> dict[str, object]:
    """Re-derive the receipt from its bound inputs and compare exactly."""

    receipt = dict(value)
    if receipt.get("schema_version") != CAPACITY_RECEIPT_SCHEMA:
        _fail("capacity receipt schema differs")
    retained_hash = receipt.get("receipt_sha256")
    body = {key: item for key, item in receipt.items() if key != "receipt_sha256"}
    if retained_hash != canonical_sha256(body):
        _fail("receipt_sha256 differs from the canonical receipt body")
    law = receipt.get("estimation_law")
    if not isinstance(law, Mapping):
        _fail("receipt lacks an estimation law")
    embedded = {key: item for key, item in law.items() if key != "estimation_law_sha256"}
    if (
        law.get("estimation_law_sha256") != ESTIMATION_LAW_SHA256
        or canonical_sha256(embedded) != ESTIMATION_LAW_SHA256
    ):
        _fail("receipt was produced under a different estimation law")
    require_frozen_law()
    contract = receipt.get("semantic_contract")
    if not isinstance(contract, Mapping):
        _fail("receipt lacks a semantic contract")
    embedded_contract = {
        key: item for key, item in contract.items() if key != "semantic_contract_sha256"
    }
    if (
        contract.get("semantic_contract_sha256") != SEMANTIC_CONTRACT_SHA256
        or canonical_sha256(embedded_contract) != SEMANTIC_CONTRACT_SHA256
    ):
        _fail("receipt was produced under a different semantic contract")
    require_frozen_contract()
    rebuilt = build_capacity_receipt(
        dict(receipt["inputs"]), created_at_utc=str(receipt.get("created_at_utc")),
    )
    if rebuilt["receipt_sha256"] != retained_hash:
        _fail("receipt does not replay from its bound inputs")
    return rebuilt


# ------------------------------------------------------------------ #
# Synthetic fixture inputs (tests / local development only)             #
# ------------------------------------------------------------------ #

def fixture_capacity_inputs(*, scale: int = 1) -> dict[str, object]:
    """Deterministic synthetic inputs; authority is always fixture."""

    if not isinstance(scale, int) or isinstance(scale, bool) or not 1 <= scale <= MAX_FIXTURE_SCALE:
        _fail(f"fixture scale must be an integer in [1, {MAX_FIXTURE_SCALE}]")

    def identity(name: str, seed: int) -> dict[str, object]:
        return {
            "uri": f"{SYNTHETIC_URI_PREFIX}{name}.json",
            "generation": str(1_788_000_000_000_000 + seed),
            "sha256": sha256(f"capacity-fixture-{name}".encode()).hexdigest(),
            "bytes": 4_096 + seed,
        }

    # Corpus-scale counts scale; selected/book counts are bounded by the
    # fixed 54x12x3 book lattice and therefore do NOT scale (coherent at
    # every supported scale).
    unique = 60_000 * scale
    selected = 4_320  # 54 slates x 80 entries
    books = 54 * 12 * 3
    return {
        "schema_version": CAPACITY_INPUTS_SCHEMA,
        "authority": "synthetic-fixture",
        "counts": {
            "accepted_slate_count": 54,
            "slate_snapshot_count": 54,
            "contest_count": 54,
            "game_count": 700,
            "team_slate_count": 1_400,
            "player_slate_count": 9_700,
            "world_release_count": 1,
            "corpus_snapshot_count": 54 * 7,
            "candidate_snapshot_count": 54,
            "unique_lineup_count": unique,
            "selected_unique_lineup_count": selected,
            "selected_book_count": books,
            "science_release_count": 1,
            "verifier_release_count": 1,
            "deployment_attestation_count": 1,
            "fill_preset_count": 7,
            "admission_preset_count": 1,
            "retrieval_preset_count": 5,
            "strategy_bundle_count": 36,
            "experiment_run_count": 2,
            "experiment_cell_count": 36,
            "evaluation_count": 1,
            "fold_count": 5,
            "metric_set_count": 108,
            "trait_definition_count": 24,
            "cohort_count": 6,
            "source_artifact_count": 120,
            "verification_receipt_count": 108,
            "attempt_count": 108,
            "promotion_decision_count": 0,
            "lineup_occurrence_count": unique * 2,
            "lineup_arm_supply_count": unique * 2,
            "trait_membership_count": unique * 3,
            "cohort_membership_count": unique,
            "selected_lineup_occurrence_count": selected * 2,
            "selected_lineup_arm_supply_count": selected * 2,
            "selected_trait_membership_count": selected * 3,
            "selected_cohort_membership_count": selected,
            "selected_book_membership_count": 54 * 12 * (4 + 14 + 80),
            "plays_for_edge_count": 9_700,
            "in_game_edge_count": 1_400,
            "derived_from_edge_count": 400,
            "uses_source_edge_count": 240,
            "uses_world_release_edge_count": 54 * 7,
            "generated_by_edge_count": books,
            "verified_by_edge_count": 108,
            "retried_as_edge_count": 0,
            "evaluated_in_edge_count": 7,
            "evaluates_bundle_edge_count": 36,
            "has_metric_edge_count": 108,
            "paired_against_edge_count": 15,
            "decides_on_bundle_edge_count": 0,
            "inferred_defender_exposure_edge_count": 2_000,
            "mean_string_property_bytes": 48,
        },
        "identities": {
            "combined_panel_index_identity": identity("combined-panel-index", 1),
            "r6_full_union_panel_freeze_identity": identity("r6-full-union-panel-freeze", 2),
            "source_universe_release_identity": identity("source-universe", 3),
        },
        "release_manifests": {
            "world_releases": [
                {"release_id": "world-release-fixture-001", "identity": identity("world-release", 4)},
            ],
            "science_releases": [
                {"release_id": "science-release-fixture-001", "identity": identity("science-release", 5)},
            ],
            "verifier_releases": [
                {"release_id": "verifier-release-fixture-001", "identity": identity("verifier-release", 6)},
            ],
            "deployment_attestations": [
                {"release_id": "deployment-attestation-fixture-001", "identity": identity("deployment-attestation", 7)},
            ],
        },
        "versions": {
            "predecessor_graph_release_id": None,
            "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
            "property_schema_version": property_schema_version(),
        },
        "hashes": {
            "r6_full_union_panel_self_sha256": sha256(b"capacity-fixture-panel-self").hexdigest(),
        },
        "parameters": {
            "provisioned_disk_bytes": 64 * 1024**3,
            "provisioned_heap_bytes": 4 * 1024**3,
            "provisioned_page_cache_bytes": 8 * 1024**3,
            "load_deadline_seconds": 14_400,
            "rebuild_deadline_seconds": 21_600,
        },
        "created_at_utc": "2026-08-26T00:00:00Z",
    }
