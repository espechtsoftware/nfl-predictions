"""Phase 5: deterministic, identity-bound graph capacity estimator.

Decides NOTHING by itself. The estimator turns an exact, identity-bound
input packet (terminal release counts, release identities, provisioning
parameters) into pre-registered estimates for BOTH candidate graph modes:

- ``full-lineup``  — one node per accepted unique roster, nine bounded
  lineup-player relationships each, sparse trait/cohort memberships, and
  the Phase 4 bundle/book membership relationships;
- ``summary-only`` — strategy/run/book/cohort/trait aggregates plus
  selected-lineup detail only; full-corpus traversal is explicitly
  UNAVAILABLE and is never labeled "full".

Vocabulary law: every node kind and relationship type the estimator
models is registered in ``corpus_graph_vnext_contracts``; kinds and
relationship types whose only namespace is ``realized`` (winner and
outcome vocabulary) are CLOSED in v1 and contribute nothing. Structural
relationship cardinalities follow the Phase 4 fixture adapter exactly:
``ADMITTED_BY`` = one per StrategyBundle, ``SELECTED_BY`` = one per
StrategyBundle plus one per SelectedBook, ``MEMBER_OF_BOOK`` = one per
book membership, ``CONTAINS_PLAYER`` = nine per loaded lineup. Every
other registered relationship type is an exact supplied count.

A receipt (``foundry-graph-capacity-receipt/v1``) binds the estimation law
(literal frozen digest), the inputs (hashed, with authority, identities,
and a lead confirmation bound to the canonical inputs digest), both
estimates, the pre-registered thresholds, per-mode feasibility, and the
forcing result. The mode DECISION is withheld: fixture-authority inputs
always yield ``pending-lead-inputs``; lead-authority inputs produce only a
recommendation that requires lead approval and never self-activates.

Everything here is pure and offline: no cloud read, no driver, no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Final, Literal

from nfl_dfs.research import corpus_graph_vnext_contracts as graph

CAPACITY_RECEIPT_SCHEMA: Final = "foundry-graph-capacity-receipt/v1"
CAPACITY_INPUTS_SCHEMA: Final = "foundry-graph-capacity-inputs/v1"
LEAD_CONFIRMATION_SUBJECT: Final = "foundry-graph-capacity-inputs/v1#lead-confirmation"
ESTIMATION_LAW_VERSION: Final = "foundry-graph-capacity-estimation-law/v1"

InputAuthority = Literal["synthetic-fixture", "lead-supplied-terminal"]
GraphMode = Literal["full-lineup", "summary-only"]
MODES: Final[tuple[GraphMode, ...]] = ("full-lineup", "summary-only")

MAX_COUNT: Final = 10**12
MAX_URI_BYTES: Final = 2_048
SYNTHETIC_URI_PREFIX: Final = "gs://synthetic-fixture.invalid/"
_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._/-]{0,199}$")
_SHA: Final = re.compile(r"^[0-9a-f]{64}$")
_UTC: Final = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

ROSTER_SLOTS: Final = 9


class CorpusGraphCapacityError(ValueError):
    """Raised when inputs, law, or receipt fail closed."""


def _fail(message: str) -> None:
    raise CorpusGraphCapacityError(message)


def canonical_sha256(value: object) -> str:
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


# ------------------------------------------------------------------ #
# Pre-registered estimation law (frozen; its LITERAL digest is pinned)  #
# ------------------------------------------------------------------ #

ESTIMATION_LAW: Final[dict[str, object]] = {
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
# Literal v1 digest, frozen by the lead. Any drift in the law above fails
# at import: a changed law is a NEW law version with a new pinned digest.
ESTIMATION_LAW_SHA256: Final = (
    "5d20920d5c5e4a779230a966f29322c46e21a05a5c442422f0f9ad3884dc5fdc"
)
if canonical_sha256(ESTIMATION_LAW) != ESTIMATION_LAW_SHA256:  # pragma: no cover
    raise CorpusGraphCapacityError(
        "estimation law content drifted from its frozen v1 digest"
    )


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

# Structural relationships whose cardinality is derived from node counts,
# mirroring the Phase 4 fixture adapter's endpoint law.
DERIVED_RELATIONSHIP_TYPES: Final = frozenset({
    "ADMITTED_BY", "SELECTED_BY", "MEMBER_OF_BOOK", "CONTAINS_PLAYER",
})


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
# Required inputs — the exact list the lead must supply.               #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class RequiredInput:
    name: str
    kind: Literal["count", "identity", "parameter", "version", "hash"]
    description: str
    modes: tuple[GraphMode, ...]


_NODE_COUNT_INPUTS: Final[tuple[tuple[str, str, str, tuple[GraphMode, ...]], ...]] = (
    ("accepted_slate_count", "Slate", "terminal accepted slates in the panel", MODES),
    ("slate_snapshot_count", "SlateSnapshot", "slate snapshots (source/pricing snapshots) bound to accepted slates", MODES),
    ("contest_count", "Contest", "registered contests bound to accepted slates", MODES),
    ("game_count", "Game", "games across accepted slates", MODES),
    ("team_slate_count", "TeamSlate", "team-slate rows across accepted slates", MODES),
    ("player_slate_count", "PlayerSlate", "player-slate rows across accepted slates", MODES),
    ("world_release_count", "WorldRelease", "world releases (identity pointers; matrices never load)", MODES),
    ("corpus_snapshot_count", "CorpusSnapshot", "corpus snapshots", MODES),
    ("candidate_snapshot_count", "CandidateSnapshot", "candidate (admitted) snapshots", MODES),
    ("unique_lineup_count", "Lineup", "distinct roster_ids across the accepted corpus", ("full-lineup",)),
    ("selected_unique_lineup_count", "Lineup", "distinct lineups appearing in any selected book", MODES),
    ("selected_book_count", "SelectedBook", "exact selected books (bundle x slate x budget)", MODES),
    ("science_release_count", "ScienceRelease", "science releases", MODES),
    ("verifier_release_count", "VerifierRelease", "verifier releases", MODES),
    ("deployment_attestation_count", "DeploymentAttestation", "deployment attestations", MODES),
    ("fill_preset_count", "FillPreset", "registered fill presets", MODES),
    ("admission_preset_count", "AdmissionPreset", "registered admission presets", MODES),
    ("retrieval_preset_count", "RetrievalPreset", "registered retrieval presets", MODES),
    ("strategy_bundle_count", "StrategyBundle", "registered strategy bundles", MODES),
    ("experiment_run_count", "ExperimentRun", "experiment runs bound to the release", MODES),
    ("experiment_cell_count", "ExperimentCell", "experiment cells", MODES),
    ("evaluation_count", "Evaluation", "evaluations (books-frozen or later)", MODES),
    ("fold_count", "Fold", "fold definitions", MODES),
    ("metric_set_count", "MetricSet", "metric-set nodes", MODES),
    ("trait_definition_count", "Trait", "versioned trait definitions", MODES),
    ("cohort_count", "Cohort", "cohort definitions", MODES),
    ("source_artifact_count", "SourceArtifact", "source artifact identities", MODES),
    ("verification_receipt_count", "VerificationReceipt", "verification receipts", MODES),
    ("attempt_count", "Attempt", "attempt records", MODES),
    ("promotion_decision_count", "PromotionDecision", "promotion decisions", MODES),
)

_EXACT_RELATIONSHIP_INPUTS: Final[tuple[tuple[str, str, str, tuple[GraphMode, ...]], ...]] = (
    ("lineup_occurrence_count", "MEMBER_OF_CORPUS", "corpus memberships incl. cross-arm duplicates", ("full-lineup",)),
    ("lineup_arm_supply_count", "SUPPLIED_BY_ARM", "(lineup, source arm) supply pairs", ("full-lineup",)),
    ("trait_membership_count", "HAS_TRAIT", "(lineup, trait) memberships, sparse", ("full-lineup",)),
    ("cohort_membership_count", "MEMBER_OF_COHORT", "(lineup, cohort) memberships", ("full-lineup",)),
    ("selected_lineup_occurrence_count", "MEMBER_OF_CORPUS", "corpus memberships of selected lineups only", ("summary-only",)),
    ("selected_lineup_arm_supply_count", "SUPPLIED_BY_ARM", "(selected lineup, source arm) supply pairs", ("summary-only",)),
    ("selected_trait_membership_count", "HAS_TRAIT", "(selected lineup, trait) memberships", ("summary-only",)),
    ("selected_cohort_membership_count", "MEMBER_OF_COHORT", "(selected lineup, cohort) memberships", ("summary-only",)),
    ("selected_book_membership_count", "MEMBER_OF_BOOK", "(book, lineup) memberships across all books", MODES),
    ("plays_for_edge_count", "PLAYS_FOR", "PLAYS_FOR relationships (player-slate -> team-slate)", MODES),
    ("in_game_edge_count", "IN_GAME", "IN_GAME relationships (team-slate -> game)", MODES),
    ("derived_from_edge_count", "DERIVED_FROM", "DERIVED_FROM lineage relationships", MODES),
    ("uses_source_edge_count", "USES_SOURCE", "USES_SOURCE lineage relationships", MODES),
    ("uses_world_release_edge_count", "USES_WORLD_RELEASE", "USES_WORLD_RELEASE lineage relationships", MODES),
    ("generated_by_edge_count", "GENERATED_BY", "GENERATED_BY relationships (book -> bundle, ...)", MODES),
    ("verified_by_edge_count", "VERIFIED_BY", "VERIFIED_BY relationships", MODES),
    ("retried_as_edge_count", "RETRIED_AS", "RETRIED_AS relationships", MODES),
    ("evaluated_in_edge_count", "EVALUATED_IN", "EVALUATED_IN relationships", MODES),
    ("evaluates_bundle_edge_count", "EVALUATES_BUNDLE", "EVALUATES_BUNDLE relationships", MODES),
    ("has_metric_edge_count", "HAS_METRIC", "HAS_METRIC relationships", MODES),
    ("paired_against_edge_count", "PAIRED_AGAINST", "PAIRED_AGAINST relationships", MODES),
    ("decides_on_bundle_edge_count", "DECIDES_ON_BUNDLE", "DECIDES_ON_BUNDLE relationships", MODES),
    ("inferred_defender_exposure_edge_count", "HAS_INFERRED_DEFENDER_EXPOSURE", "HAS_INFERRED_DEFENDER_EXPOSURE relationships (qualified)", MODES),
)

REQUIRED_COUNTS: Final[tuple[RequiredInput, ...]] = (
    *(RequiredInput(name, "count", f"[{kind}] {description}", modes)
      for name, kind, description, modes in _NODE_COUNT_INPUTS),
    *(RequiredInput(name, "count", f"[{relationship}] {description}", modes)
      for name, relationship, description, modes in _EXACT_RELATIONSHIP_INPUTS),
    RequiredInput(
        "mean_string_property_bytes", "count",
        "measured mean UTF-8 bytes of string properties in the release", MODES,
    ),
)

REQUIRED_IDENTITIES: Final[tuple[RequiredInput, ...]] = tuple(
    RequiredInput(name, "identity", description, MODES)
    for name, description in (
        ("combined_panel_index_identity", "foundry-v12-combined-panel-index/v1 object identity"),
        (
            "r6_full_union_panel_freeze_identity",
            "accepted R6 full-union panel-freeze/release object identity "
            "(corpus-r6-full-union-freezes/<freeze>/panel-freeze.json; "
            "outcome-blind, complete=true; 54 slates / 2,592 books / 7,776 prefixes census)",
        ),
        ("source_universe_release_identity", "artifact-supported source-universe release identity"),
        ("world_release_identity", "world release identity (matrices never load; pointer only)"),
    )
)

REQUIRED_VERSIONS: Final[tuple[RequiredInput, ...]] = (
    RequiredInput("science_release_id", "version", "science release canonical id", MODES),
    RequiredInput("verifier_release_id", "version", "verifier release canonical id", MODES),
    RequiredInput("deployment_attestation_id", "version", "deployment attestation canonical id", MODES),
    RequiredInput("predecessor_graph_release_id", "version", "predecessor graph release id or null", MODES),
    RequiredInput("graph_schema_version", "version", f"must equal {graph.GRAPH_SCHEMA_VERSION}", MODES),
    RequiredInput("property_schema_version", "version", "must equal the content hash of the complete positive property schema", MODES),
)

REQUIRED_HASHES: Final[tuple[RequiredInput, ...]] = (
    RequiredInput(
        "r6_full_union_panel_self_sha256", "hash",
        "panel self-hash recorded inside the accepted R6 full-union panel-freeze root", MODES,
    ),
)

REQUIRED_PARAMETERS: Final[tuple[RequiredInput, ...]] = tuple(
    RequiredInput(name, "parameter", description, MODES)
    for name, description in (
        ("provisioned_disk_bytes", "disk available to the graph store"),
        ("provisioned_heap_bytes", "JVM heap for the graph service"),
        ("provisioned_page_cache_bytes", "page cache for the graph store"),
        ("load_deadline_seconds", "zero-state streamed load deadline"),
        ("rebuild_deadline_seconds", "zero-state rebuild deadline incl. indexes"),
    )
)


def required_inputs_manifest() -> list[dict[str, object]]:
    """The exact, ordered list of inputs the lead must supply."""

    return [
        {
            "name": item.name,
            "kind": item.kind,
            "description": item.description,
            "modes": list(item.modes),
        }
        for group in (
            REQUIRED_COUNTS, REQUIRED_IDENTITIES, REQUIRED_VERSIONS,
            REQUIRED_HASHES, REQUIRED_PARAMETERS,
        )
        for item in group
    ]


EXCLUDED_FROM_GRAPH: Final = (
    "world score matrices",
    "per-world nodes or relationships",
    "dense pairwise player/lineup networks (quadratic)",
    "raw licensed Fantasy Points or SIS rows",
    "raw contest standings and contestant identifiers",
    "credentials or secrets",
    "mutable active-policy pointers",
    "realized namespace (closed in v1): winner and outcome node kinds and relationships",
)


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
        or byte_count <= 0
    ):
        _fail(f"{label}.bytes is not positive")
    return {"uri": uri, "generation": generation, "sha256": digest, "bytes": byte_count}


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


def lead_confirmation_for(packet: Mapping[str, object]) -> str:
    """The canonical subject a lead confirmation must bind.

    subject = sha256(canonical {"subject": ..., "inputs_sha256": <digest of
    the packet body without confirmation or inputs hash>}).
    """

    body = _canonical_body(packet)
    return canonical_sha256({
        "subject": LEAD_CONFIRMATION_SUBJECT,
        "inputs_sha256": canonical_sha256(body),
    })


def _canonical_body(packet: Mapping[str, object]) -> dict[str, object]:
    return {
        key: packet[key]
        for key in (
            "schema_version", "authority", "counts", "identities", "versions",
            "hashes", "parameters", "created_at_utc",
        )
    }


def validate_capacity_inputs(value: Mapping[str, object]) -> dict[str, object]:
    """Validate the input packet; every required name must be present."""

    packet = dict(value)
    expected_keys = {
        "schema_version", "authority", "counts", "identities", "versions",
        "hashes", "parameters", "created_at_utc",
    }
    optional_keys = {"lead_confirmation_sha256", "inputs_sha256"}
    if not expected_keys <= set(packet) or not set(packet) <= expected_keys | optional_keys:
        _fail("capacity inputs must carry exactly the registered packet keys")
    if packet["schema_version"] != CAPACITY_INPUTS_SCHEMA:
        _fail("capacity inputs schema differs")
    authority = packet["authority"]
    if authority not in ("synthetic-fixture", "lead-supplied-terminal"):
        _fail("capacity inputs authority is not registered")
    created = packet["created_at_utc"]
    if not isinstance(created, str) or _UTC.fullmatch(created) is None:
        _fail("created_at_utc is not second-precision UTC")

    counts_in = packet["counts"]
    if not isinstance(counts_in, Mapping):
        _fail("counts is not a mapping")
    required_count_names = [item.name for item in REQUIRED_COUNTS]
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
    identity_names = [item.name for item in REQUIRED_IDENTITIES]
    if set(identities_in) != set(identity_names):
        _fail(f"identities must carry exactly {identity_names}")
    identities = {
        name: _identity(identities_in[name], label=f"identities.{name}", authority=authority)
        for name in identity_names
    }

    versions_in = packet["versions"]
    if not isinstance(versions_in, Mapping):
        _fail("versions is not a mapping")
    version_names = [item.name for item in REQUIRED_VERSIONS]
    if set(versions_in) != set(version_names):
        _fail(f"versions must carry exactly {version_names}")
    if versions_in["graph_schema_version"] != graph.GRAPH_SCHEMA_VERSION:
        _fail("graph_schema_version differs from the contracts module")
    if versions_in["property_schema_version"] != property_schema_version():
        _fail("property_schema_version differs from the contracts module")
    versions = {
        "science_release_id": _canonical_id(versions_in["science_release_id"], label="versions.science_release_id"),
        "verifier_release_id": _canonical_id(versions_in["verifier_release_id"], label="versions.verifier_release_id"),
        "deployment_attestation_id": _canonical_id(versions_in["deployment_attestation_id"], label="versions.deployment_attestation_id"),
        "predecessor_graph_release_id": _canonical_id(
            versions_in["predecessor_graph_release_id"],
            label="versions.predecessor_graph_release_id", nullable=True,
        ),
        "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
        "property_schema_version": property_schema_version(),
    }

    hashes_in = packet["hashes"]
    if not isinstance(hashes_in, Mapping):
        _fail("hashes is not a mapping")
    hash_names = [item.name for item in REQUIRED_HASHES]
    if set(hashes_in) != set(hash_names):
        _fail(f"hashes must carry exactly {hash_names}")
    hashes = {name: _sha(hashes_in[name], label=f"hashes.{name}") for name in hash_names}

    parameters_in = packet["parameters"]
    if not isinstance(parameters_in, Mapping):
        _fail("parameters is not a mapping")
    parameter_names = [item.name for item in REQUIRED_PARAMETERS]
    if set(parameters_in) != set(parameter_names):
        _fail(f"parameters must carry exactly {parameter_names}")
    parameters = {name: _count(parameters_in[name], label=f"parameters.{name}") for name in parameter_names}
    for name in parameter_names:
        if parameters[name] <= 0:
            _fail(f"parameters.{name} must be positive")

    body = {
        "schema_version": CAPACITY_INPUTS_SCHEMA,
        "authority": authority,
        "counts": counts,
        "identities": identities,
        "versions": versions,
        "hashes": hashes,
        "parameters": parameters,
        "created_at_utc": created,
    }
    confirmation = packet.get("lead_confirmation_sha256")
    if confirmation is not None:
        _sha(confirmation, label="lead_confirmation_sha256")
        if authority == "synthetic-fixture":
            _fail("fixture-authority inputs may not carry a lead confirmation")
        if confirmation != lead_confirmation_for(body):
            _fail(
                "lead_confirmation_sha256 does not bind the canonical inputs "
                "subject"
            )
    digest = canonical_sha256({**body, "lead_confirmation_sha256": confirmation})
    retained = packet.get("inputs_sha256")
    if retained is not None and retained != digest:
        _fail("inputs_sha256 differs from the canonical packet")
    return {**body, "lead_confirmation_sha256": confirmation, "inputs_sha256": digest}


# ------------------------------------------------------------------ #
# Estimation                                                            #
# ------------------------------------------------------------------ #

def _string_rule_count(rules: Mapping[str, object]) -> int:
    return sum(
        1 for rule in rules.values()
        if getattr(rule, "value_type", "") in ("string", "string_list")
    )


def _mode_elements(counts: Mapping[str, int], mode: GraphMode) -> tuple[dict[str, int], dict[str, int]]:
    full = mode == "full-lineup"
    lineups = counts["unique_lineup_count"] if full else counts["selected_unique_lineup_count"]
    nodes: dict[str, int] = {}
    for name, kind, _, modes in _NODE_COUNT_INPUTS:
        if name == "unique_lineup_count" or name == "selected_unique_lineup_count":
            continue
        if mode not in modes:
            continue
        nodes[kind] = counts[name]
    nodes["Lineup"] = lineups

    bundles = counts["strategy_bundle_count"]
    books = counts["selected_book_count"]
    relationships: dict[str, int] = {
        # Phase 4 endpoint law (structural, derived from node counts).
        "CONTAINS_PLAYER": ROSTER_SLOTS * lineups,
        "ADMITTED_BY": bundles,             # StrategyBundle -> AdmissionPreset
        "SELECTED_BY": bundles + books,     # bundle -> retrieval, book -> retrieval
        "MEMBER_OF_BOOK": counts["selected_book_membership_count"],
    }
    for name, relationship, _, modes in _EXACT_RELATIONSHIP_INPUTS:
        if mode not in modes:
            continue
        if relationship == "MEMBER_OF_BOOK":
            continue
        relationships[relationship] = counts[name]

    unknown_nodes = set(nodes) - graph.NODE_KINDS
    unknown_relationships = set(relationships) - graph.RELATIONSHIP_TYPES
    if unknown_nodes or unknown_relationships:  # pragma: no cover - vocabulary drift guard
        _fail(
            f"estimator references unregistered vocabulary "
            f"{sorted(unknown_nodes | unknown_relationships)}"
        )
    closed_nodes = set(nodes) & CLOSED_NODE_KINDS
    closed_relationships = set(relationships) & CLOSED_RELATIONSHIP_TYPES
    if closed_nodes or closed_relationships:  # pragma: no cover - firewall guard
        _fail(
            f"estimator models closed realized vocabulary "
            f"{sorted(closed_nodes | closed_relationships)}"
        )
    return nodes, relationships


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def estimate_mode(counts: Mapping[str, int], parameters: Mapping[str, int], mode: GraphMode) -> dict[str, object]:
    law = ESTIMATION_LAW
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
        "derived_relationship_types": sorted(DERIVED_RELATIONSHIP_TYPES),
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
    if not isinstance(created_at_utc, str) or _UTC.fullmatch(created_at_utc) is None:
        _fail("receipt created_at_utc is not second-precision UTC")
    counts = retained["counts"]
    parameters = retained["parameters"]
    estimates = {mode: estimate_mode(counts, parameters, mode) for mode in MODES}
    full_ok = bool(estimates["full-lineup"]["feasible"])
    summary_ok = bool(estimates["summary-only"]["feasible"])
    if full_ok and summary_ok:
        forced_mode: str | None = None
    elif summary_ok:
        forced_mode = "summary-only"
    else:
        forced_mode = "none-feasible"

    decidable = (
        retained["authority"] == "lead-supplied-terminal"
        and retained["lead_confirmation_sha256"] is not None
    )
    if decidable:
        if forced_mode == "none-feasible":
            recommended: str | None = None
        elif forced_mode == "summary-only":
            recommended = "summary-only"
        else:
            recommended = "full-lineup"
        decision = {
            "state": "decidable",
            "recommended_mode": recommended,
            "requires_lead_approval": True,
            "self_activating": False,
            "note": (
                "a recommendation only; the lead's explicit approval receipt "
                "selects the mode"
            ),
        }
    else:
        decision = {
            "state": "pending-lead-inputs",
            "recommended_mode": None,
            "requires_lead_approval": True,
            "self_activating": False,
            "note": (
                "no mode is chosen until the lead supplies exact terminal "
                "release counts and identities with a bound lead confirmation"
            ),
        }

    body = {
        "schema_version": CAPACITY_RECEIPT_SCHEMA,
        "created_at_utc": created_at_utc,
        "estimation_law": {
            **ESTIMATION_LAW,
            "estimation_law_sha256": ESTIMATION_LAW_SHA256,
        },
        "inputs": retained,
        "estimates": estimates,
        "forced_mode": forced_mode,
        "decision": decision,
        "required_inputs_manifest": required_inputs_manifest(),
        "closed_vocabulary": {
            "node_kinds": sorted(CLOSED_NODE_KINDS),
            "relationship_types": sorted(CLOSED_RELATIONSHIP_TYPES),
            "note": "realized-only vocabulary is closed in v1 and contributes no elements",
        },
        "excluded_from_graph": list(EXCLUDED_FROM_GRAPH),
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
    if not isinstance(law, Mapping) or law.get("estimation_law_sha256") != ESTIMATION_LAW_SHA256:
        _fail("receipt was produced under a different estimation law")
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

    if not isinstance(scale, int) or isinstance(scale, bool) or scale < 1:
        _fail("fixture scale must be a positive integer")

    def identity(name: str, seed: int) -> dict[str, object]:
        return {
            "uri": f"{SYNTHETIC_URI_PREFIX}{name}.json",
            "generation": str(1_788_000_000_000_000 + seed),
            "sha256": sha256(f"capacity-fixture-{name}".encode()).hexdigest(),
            "bytes": 4_096 + seed,
        }

    unique = 60_000 * scale
    selected = 4_320 * scale  # 54 slates x 80 entries
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
            "world_release_identity": identity("world-release", 4),
        },
        "versions": {
            "science_release_id": "science-release-fixture-001",
            "verifier_release_id": "verifier-release-fixture-001",
            "deployment_attestation_id": "deployment-attestation-fixture-001",
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
