"""Phase 5: deterministic, identity-bound graph capacity estimator.

Decides NOTHING by itself. The estimator turns an exact, identity-bound
input packet (terminal release counts, release identities, provisioning
parameters) into pre-registered estimates for BOTH candidate graph modes:

- ``full-lineup``  — one node per accepted unique roster, nine bounded
  lineup-player relationships each, sparse trait/cohort memberships, and
  admitted/selected relationships;
- ``summary-only`` — strategy/run/book/cohort/trait aggregates plus
  selected-lineup detail only; full-corpus traversal is explicitly
  UNAVAILABLE and is never labeled "full".

A receipt (``foundry-graph-capacity-receipt/v1``) binds the estimation law
(frozen coefficients, hashed), the inputs (hashed, with their authority
and identities), both estimates, the pre-registered thresholds, the
per-mode feasibility verdicts, and the forcing result. The mode DECISION
is withheld until the lead supplies exact terminal counts and identities:
fixture-authority inputs always yield ``decision_state ==
"pending-lead-inputs"``; even lead-authority inputs produce only a
recommendation that requires lead approval and never self-activates.

World matrices, per-world nodes, dense pairwise networks, raw licensed
rows, raw standings, credentials, mutable pointers, and the realized
namespace stay outside Neo4j in BOTH modes.

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
# Pre-registered estimation law (frozen; its hash is bound in receipts) #
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
ESTIMATION_LAW_SHA256: Final = canonical_sha256(ESTIMATION_LAW)


# ------------------------------------------------------------------ #
# Required inputs — the exact list the lead must supply.               #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class RequiredInput:
    name: str
    kind: Literal["count", "identity", "parameter", "version"]
    description: str
    modes: tuple[GraphMode, ...]


REQUIRED_COUNTS: Final[tuple[RequiredInput, ...]] = tuple(
    RequiredInput(name, "count", description, modes)
    for name, description, modes in (
        ("accepted_slate_count", "terminal accepted slates in the panel", MODES),
        ("contest_count", "registered contests bound to accepted slates", MODES),
        ("game_count", "games across accepted slates", MODES),
        ("team_slate_count", "team-slate rows across accepted slates", MODES),
        ("player_slate_count", "player-slate rows across accepted slates", MODES),
        ("unique_lineup_count", "distinct roster_ids across the accepted corpus", ("full-lineup",)),
        ("lineup_occurrence_count", "corpus memberships incl. cross-arm duplicates", ("full-lineup",)),
        ("lineup_arm_supply_count", "(lineup, source arm) supply pairs", ("full-lineup",)),
        ("admitted_membership_count", "(lineup, admission) admitted pairs", ("full-lineup",)),
        ("trait_membership_count", "(lineup, trait) memberships, sparse", ("full-lineup",)),
        ("cohort_membership_count", "(lineup, cohort) memberships", ("full-lineup",)),
        ("selected_unique_lineup_count", "distinct lineups appearing in any selected book", MODES),
        ("selected_lineup_occurrence_count", "corpus memberships of selected lineups only", ("summary-only",)),
        ("selected_lineup_arm_supply_count", "(selected lineup, source arm) supply pairs", ("summary-only",)),
        ("selected_trait_membership_count", "(selected lineup, trait) memberships", ("summary-only",)),
        ("selected_cohort_membership_count", "(selected lineup, cohort) memberships", ("summary-only",)),
        ("selected_book_count", "exact selected books (bundle x slate x budget)", MODES),
        ("selected_book_membership_count", "(book, lineup) memberships across all books", MODES),
        ("fill_preset_count", "registered fill presets", MODES),
        ("admission_preset_count", "registered admission presets", MODES),
        ("retrieval_preset_count", "registered retrieval presets", MODES),
        ("strategy_bundle_count", "registered strategy bundles", MODES),
        ("experiment_run_count", "experiment runs bound to the release", MODES),
        ("experiment_cell_count", "experiment cells", MODES),
        ("evaluation_count", "evaluations (books-frozen or later)", MODES),
        ("fold_count", "fold definitions", MODES),
        ("metric_set_count", "metric-set nodes", MODES),
        ("metric_edge_count", "HAS_METRIC relationships", MODES),
        ("trait_definition_count", "versioned trait definitions", MODES),
        ("cohort_count", "cohort definitions", MODES),
        ("winner_release_count", "winner releases (governed)", MODES),
        ("winner_observation_count", "winner observations in the bound release", MODES),
        ("winner_observation_edge_count", "OBSERVED_IN_WINNER_RELEASE relationships", MODES),
        ("source_artifact_count", "source artifact identities", MODES),
        ("verification_receipt_count", "verification receipts", MODES),
        ("attempt_count", "attempt records", MODES),
        ("promotion_decision_count", "promotion decisions", MODES),
        ("lineage_edge_count", "DERIVED_FROM/USES_*/GENERATED_BY/VERIFIED_BY/RETRIED_AS/EVALUATED_IN/PAIRED_AGAINST/EVALUATES_BUNDLE/DECIDES_ON_BUNDLE relationships combined", MODES),
        ("inferred_defender_exposure_edge_count", "HAS_INFERRED_DEFENDER_EXPOSURE relationships (qualified)", MODES),
        ("mean_string_property_bytes", "measured mean UTF-8 bytes of string properties in the release", MODES),
    )
)

REQUIRED_IDENTITIES: Final[tuple[RequiredInput, ...]] = tuple(
    RequiredInput(name, "identity", description, MODES)
    for name, description in (
        ("combined_panel_index_identity", "foundry-v12-combined-panel-index/v1 object identity"),
        ("t230_panel_release_identity", "foundry-t230-panel-release/v1 object identity"),
        ("source_universe_release_identity", "artifact-supported source-universe release identity"),
        ("world_release_identity", "world release identity (matrices never load; pointer only)"),
        ("winner_release_identity", "governed winner release identity (required when cohort/trait namespaces load)"),
    )
)

REQUIRED_VERSIONS: Final[tuple[RequiredInput, ...]] = (
    RequiredInput("science_release_id", "version", "science release canonical id", MODES),
    RequiredInput("verifier_release_id", "version", "verifier release canonical id", MODES),
    RequiredInput("deployment_attestation_id", "version", "deployment attestation canonical id", MODES),
    RequiredInput("predecessor_graph_release_id", "version", "predecessor graph release id or null", MODES),
    RequiredInput("graph_schema_version", "version", f"must equal {graph.GRAPH_SCHEMA_VERSION}", MODES),
    RequiredInput("property_schema_version", "version", "must equal the contracts' positive property schema version", MODES),
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
            REQUIRED_PARAMETERS,
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
    "realized namespace (closed offline)",
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


def validate_capacity_inputs(value: Mapping[str, object]) -> dict[str, object]:
    """Validate the input packet; every required name must be present."""

    packet = dict(value)
    expected_keys = {
        "schema_version", "authority", "counts", "identities", "versions",
        "parameters", "created_at_utc",
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

    # Cross-count coherence.
    if counts["selected_unique_lineup_count"] > counts["unique_lineup_count"]:
        _fail("selected_unique_lineup_count exceeds unique_lineup_count")
    if counts["lineup_occurrence_count"] < counts["unique_lineup_count"]:
        _fail("lineup_occurrence_count is below unique_lineup_count")
    if counts["selected_lineup_occurrence_count"] > counts["lineup_occurrence_count"]:
        _fail("selected_lineup_occurrence_count exceeds lineup_occurrence_count")
    if counts["selected_lineup_arm_supply_count"] > counts["lineup_arm_supply_count"]:
        _fail("selected_lineup_arm_supply_count exceeds lineup_arm_supply_count")
    if counts["selected_trait_membership_count"] > counts["trait_membership_count"]:
        _fail("selected_trait_membership_count exceeds trait_membership_count")
    if counts["selected_cohort_membership_count"] > counts["cohort_membership_count"]:
        _fail("selected_cohort_membership_count exceeds cohort_membership_count")
    if counts["selected_book_membership_count"] < counts["selected_unique_lineup_count"]:
        _fail("selected_book_membership_count is below selected_unique_lineup_count")
    if counts["mean_string_property_bytes"] <= 0:
        _fail("mean_string_property_bytes must be positive")

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
    if versions_in["property_schema_version"] != _property_schema_version():
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
        "property_schema_version": _property_schema_version(),
    }

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

    confirmation = packet.get("lead_confirmation_sha256")
    if confirmation is not None and (
        not isinstance(confirmation, str) or _SHA.fullmatch(confirmation) is None
    ):
        _fail("lead_confirmation_sha256 is not 64-hex")
    if authority == "synthetic-fixture" and confirmation is not None:
        _fail("fixture-authority inputs may not carry a lead confirmation")

    body = {
        "schema_version": CAPACITY_INPUTS_SCHEMA,
        "authority": authority,
        "counts": counts,
        "identities": identities,
        "versions": versions,
        "parameters": parameters,
        "created_at_utc": created,
        "lead_confirmation_sha256": confirmation,
    }
    digest = canonical_sha256(body)
    retained = packet.get("inputs_sha256")
    if retained is not None and retained != digest:
        _fail("inputs_sha256 differs from the canonical packet")
    return {**body, "inputs_sha256": digest}


def _property_schema_version() -> str:
    """Bind the positive property schema by content, not by name."""

    schema_image = {
        "nodes": {
            kind: sorted(rules) for kind, rules in graph.NODE_PROPERTY_SCHEMA.items()
        },
        "relationships": {
            relationship: sorted(rules)
            for relationship, rules in graph.RELATIONSHIP_PROPERTY_SCHEMA.items()
        },
    }
    return f"{graph.GRAPH_SCHEMA_VERSION}+properties-{canonical_sha256(schema_image)[:16]}"


# ------------------------------------------------------------------ #
# Estimation                                                            #
# ------------------------------------------------------------------ #

def _string_rule_count(rules: Mapping[str, object]) -> int:
    return sum(
        1 for rule in rules.values()
        if getattr(rule, "value_type", "") in ("string", "string_list")
    )


def _node_kind_costs() -> dict[str, tuple[int, int]]:
    """(property_count, string_property_count) per node kind, from schema."""

    return {
        kind: (len(rules), _string_rule_count(rules))
        for kind, rules in graph.NODE_PROPERTY_SCHEMA.items()
    }


def _relationship_costs() -> dict[str, tuple[int, int]]:
    return {
        relationship: (len(rules), _string_rule_count(rules))
        for relationship, rules in graph.RELATIONSHIP_PROPERTY_SCHEMA.items()
    }


def _mode_elements(counts: Mapping[str, int], mode: GraphMode) -> tuple[dict[str, int], dict[str, int]]:
    full = mode == "full-lineup"
    lineups = counts["unique_lineup_count"] if full else counts["selected_unique_lineup_count"]
    nodes = {
        "Slate": counts["accepted_slate_count"],
        "Contest": counts["contest_count"],
        "Game": counts["game_count"],
        "TeamSlate": counts["team_slate_count"],
        "PlayerSlate": counts["player_slate_count"],
        "Lineup": lineups,
        "SelectedBook": counts["selected_book_count"],
        "FillPreset": counts["fill_preset_count"],
        "AdmissionPreset": counts["admission_preset_count"],
        "RetrievalPreset": counts["retrieval_preset_count"],
        "StrategyBundle": counts["strategy_bundle_count"],
        "ExperimentRun": counts["experiment_run_count"],
        "ExperimentCell": counts["experiment_cell_count"],
        "Evaluation": counts["evaluation_count"],
        "Fold": counts["fold_count"],
        "MetricSet": counts["metric_set_count"],
        "Trait": counts["trait_definition_count"],
        "Cohort": counts["cohort_count"],
        "WinnerRelease": counts["winner_release_count"],
        "WinnerObservation": counts["winner_observation_count"],
        "SourceArtifact": counts["source_artifact_count"],
        "VerificationReceipt": counts["verification_receipt_count"],
        "Attempt": counts["attempt_count"],
        "PromotionDecision": counts["promotion_decision_count"],
    }
    relationships = {
        "CONTAINS_PLAYER": ROSTER_SLOTS * lineups,
        "MEMBER_OF_CORPUS": counts["lineup_occurrence_count"] if full else counts["selected_lineup_occurrence_count"],
        "SUPPLIED_BY_ARM": counts["lineup_arm_supply_count"] if full else counts["selected_lineup_arm_supply_count"],
        "ADMITTED_BY": counts["admitted_membership_count"] if full else 0,
        "SELECTED_BY": counts["selected_book_membership_count"],
        "MEMBER_OF_BOOK": counts["selected_book_membership_count"],
        "HAS_TRAIT": counts["trait_membership_count"] if full else counts["selected_trait_membership_count"],
        "MEMBER_OF_COHORT": counts["cohort_membership_count"] if full else counts["selected_cohort_membership_count"],
        "PLAYS_FOR": counts["player_slate_count"],
        "IN_GAME": counts["team_slate_count"],
        "HAS_METRIC": counts["metric_edge_count"],
        "OBSERVED_IN_WINNER_RELEASE": counts["winner_observation_edge_count"],
        "HAS_INFERRED_DEFENDER_EXPOSURE": counts["inferred_defender_exposure_edge_count"],
        "LINEAGE_COMBINED": counts["lineage_edge_count"],
    }
    unknown = set(nodes) - graph.NODE_KINDS
    if unknown:  # pragma: no cover - vocabulary drift guard
        _fail(f"estimator references unregistered node kinds {sorted(unknown)}")
    return nodes, relationships


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def estimate_mode(counts: Mapping[str, int], parameters: Mapping[str, int], mode: GraphMode) -> dict[str, object]:
    law = ESTIMATION_LAW
    nodes, relationships = _mode_elements(counts, mode)
    node_costs = _node_kind_costs()
    relationship_costs = _relationship_costs()
    lineage_cost = (0, 0)

    node_count = sum(nodes.values())
    relationship_count = sum(relationships.values())
    property_count = 0
    string_property_count = 0
    for kind, count in nodes.items():
        props, strings = node_costs.get(kind, (0, 0))
        property_count += props * count
        string_property_count += strings * count
    for relationship, count in relationships.items():
        props, strings = relationship_costs.get(relationship, lineage_cost)
        property_count += props * count
        string_property_count += strings * count

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
        "node_kinds": nodes,
        "relationship_types": relationships,
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
                "release counts and identities with a lead confirmation"
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
        {k: v for k, v in dict(receipt["inputs"]).items()},
        created_at_utc=str(receipt.get("created_at_utc")),
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
    return {
        "schema_version": CAPACITY_INPUTS_SCHEMA,
        "authority": "synthetic-fixture",
        "counts": {
            "accepted_slate_count": 54,
            "contest_count": 54,
            "game_count": 700,
            "team_slate_count": 1_400,
            "player_slate_count": 9_700,
            "unique_lineup_count": unique,
            "lineup_occurrence_count": unique * 2,
            "lineup_arm_supply_count": unique * 2,
            "admitted_membership_count": unique,
            "trait_membership_count": unique * 3,
            "cohort_membership_count": unique,
            "selected_unique_lineup_count": selected,
            "selected_lineup_occurrence_count": selected * 2,
            "selected_lineup_arm_supply_count": selected * 2,
            "selected_trait_membership_count": selected * 3,
            "selected_cohort_membership_count": selected,
            "selected_book_count": 54 * 12 * 3,
            "selected_book_membership_count": 54 * 12 * (4 + 14 + 80),
            "fill_preset_count": 7,
            "admission_preset_count": 1,
            "retrieval_preset_count": 5,
            "strategy_bundle_count": 36,
            "experiment_run_count": 2,
            "experiment_cell_count": 36,
            "evaluation_count": 1,
            "fold_count": 5,
            "metric_set_count": 108,
            "metric_edge_count": 108,
            "trait_definition_count": 24,
            "cohort_count": 6,
            "winner_release_count": 1,
            "winner_observation_count": 51,
            "winner_observation_edge_count": 51,
            "source_artifact_count": 120,
            "verification_receipt_count": 108,
            "attempt_count": 108,
            "promotion_decision_count": 0,
            "lineage_edge_count": 600,
            "inferred_defender_exposure_edge_count": 2_000,
            "mean_string_property_bytes": 48,
        },
        "identities": {
            "combined_panel_index_identity": identity("combined-panel-index", 1),
            "t230_panel_release_identity": identity("t230-panel-release", 2),
            "source_universe_release_identity": identity("source-universe", 3),
            "world_release_identity": identity("world-release", 4),
            "winner_release_identity": identity("winner-release", 5),
        },
        "versions": {
            "science_release_id": "science-release-fixture-001",
            "verifier_release_id": "verifier-release-fixture-001",
            "deployment_attestation_id": "deployment-attestation-fixture-001",
            "predecessor_graph_release_id": None,
            "graph_schema_version": graph.GRAPH_SCHEMA_VERSION,
            "property_schema_version": _property_schema_version(),
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


def property_schema_version() -> str:
    """Public accessor for the content-bound property schema version."""

    return _property_schema_version()
