"""Bounded localhost graph projection of accepted R6 historical evidence.

This module is deliberately a pure adapter.  Its only input is a caller-
supplied set of exact, generation-pinned canonical JSON objects.  It performs
no network, warehouse, outcome, Docker, Neo4j, or application operation.

The production entry point accepts only the already-published fixed-G0
candidate-authority v2 chain, fixed-G0 structural catalog outer chain, and
full-union attribution chain.  It validates the complete populations before
slicing.  The output keeps only persisted >=200 DK lineups, their structural
player joins, exact generation recurrence, and final-fit selector decisions;
full-population generation denominators remain as compact aggregate nodes.

The result is descriptive development evidence.  It grants no feedback,
promotion, winner, scoring, policy, deployment, or live-money authority.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Final, TypeAlias

from nfl_dfs.research import corpus_parametric_batch as parametric
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_release_v2 as candidate_release
from nfl_dfs.research import corpus_r6_fixed_g0_candidate_authority_v1 as candidate_v1
from nfl_dfs.research import corpus_r6_fixed_g0_catalog_recovery_v1 as catalog_recovery
from nfl_dfs.research import corpus_r6_full_union_attribution_v1 as attribution
from nfl_dfs.research import corpus_r6_matchup_source_v2 as candidate_source
from nfl_dfs.research import corpus_r6_no_rescore_funnel_v1 as no_rescore_funnel
from nfl_dfs.research import corpus_r6_player_catalog_v1 as player_catalog
from nfl_dfs.research import residual_world_columns
from nfl_dfs.research.corpus_batch_evidence_contract import MICRO_DK_PER_POINT


PLAN_SCHEMA: Final = "corpus-r6-historical-neo4j-slice-plan/v1"
MANIFEST_SCHEMA: Final = "corpus-r6-historical-neo4j-slice-manifest/v1"
NODE_SCHEMA: Final = "corpus-r6-historical-neo4j-node/v1"
RELATIONSHIP_SCHEMA: Final = "corpus-r6-historical-neo4j-relationship/v1"
EXACT_OBJECT_SCHEMA: Final = "corpus-r6-historical-exact-object/v1"
EVIDENCE_CLASS: Final = "descriptive-development-only"
THRESHOLD_DK: Final = 200
THRESHOLD_MICRO: Final = THRESHOLD_DK * MICRO_DK_PER_POINT
FINAL_SCOPE_ORDINAL: Final = 5
FINAL_FIT_SCOPE_ID: Final = "all-block-final-fit"

EXPECTED_SLATE_COUNT: Final = 54
EXPECTED_CANDIDATE_COUNT: Final = 199_244
EXPECTED_VISIT_COUNT: Final = 378_000
EXPECTED_PLAYER_SLATE_COUNT: Final = 29_605
EXPECTED_SCOPE_MEMBERSHIP_COUNT: Final = 1_195_464
EXPECTED_BOOK_COUNT: Final = 2_592
EXPECTED_SELECTION_COUNT: Final = 207_360
EXPECTED_FINAL_BOOK_COUNT: Final = 432
EXPECTED_FINAL_SELECTION_COUNT: Final = 34_560
EXPECTED_HIGH_SCORE_LINEUP_COUNT: Final = 279
EXPECTED_SELECTED_HIGH_SCORE_LINEUP_COUNT: Final = 38
EXPECTED_MISSED_HIGH_SCORE_LINEUP_COUNT: Final = 241
EXPECTED_OPPORTUNITY_SLATE_COUNT: Final = 29
EXPECTED_CONVERTED_SLATE_COUNT: Final = 10
# Only graph-bearing leaves are required locally.  The accepted terminal roots
# retain and validate the identities of the interstitial publication objects;
# downloading receipt/release bodies that add no graph rows would needlessly
# duplicate hundreds of megabytes and is not part of this bounded projection.
EXPECTED_CANDIDATE_OBJECT_COUNT: Final = 109  # root + 54 artifacts + 54 lineages
EXPECTED_CATALOG_OBJECT_COUNT: Final = 55  # outer + 54 structural catalogs
EXPECTED_ATTRIBUTION_OBJECT_COUNT: Final = 55
EXPECTED_EXACT_OBJECT_COUNT: Final = (
    EXPECTED_CANDIDATE_OBJECT_COUNT
    + EXPECTED_CATALOG_OBJECT_COUNT
    + EXPECTED_ATTRIBUTION_OBJECT_COUNT
)

ARM_IDS: Final = tuple(parametric.PARAMETER_SET_ORDER)
BLOCK_IDS: Final = tuple(residual_world_columns.WORLD_BLOCKS)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_GENERATION: Final = re.compile(r"^[1-9][0-9]*$")


class CorpusR6HistoricalNeo4jSliceV1Error(ValueError):
    """The bounded historical graph projection failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6HistoricalNeo4jSliceV1Error(message)


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
        raise CorpusR6HistoricalNeo4jSliceV1Error(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be one nonempty string")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if frozenset(item) != frozenset({"uri", "generation", "sha256", "bytes"}):
        _fail(f"{label} fields differ")
    uri = _string(item["uri"], label=f"{label}.uri")
    generation = _string(item["generation"], label=f"{label}.generation")
    digest = _digest(item["sha256"], label=f"{label}.sha256")
    byte_count = _integer(item["bytes"], label=f"{label}.bytes", minimum=1)
    if _GENERATION.fullmatch(generation) is None:
        _fail(f"{label}.generation differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": byte_count,
    }


def _identity_key(value: Mapping[str, object]) -> tuple[str, str, str, int]:
    return (
        str(value["uri"]),
        str(value["generation"]),
        str(value["sha256"]),
        int(value["bytes"]),
    )


def _parse_canonical_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")

    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                _fail(f"{label} repeats key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        _fail(f"{label} contains non-finite value {value}")

    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6HistoricalNeo4jSliceV1Error(
            f"{label} is not valid UTF-8 JSON"
        ) from exc
    body = _mapping(parsed, label=label)
    if canonical_json_bytes(body) != raw:
        _fail(f"{label} bytes are not canonical JSON")
    return body


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> str:
    retained = _digest(value.get(field), label=f"{label}.{field}")
    expected = canonical_sha256({
        key: item for key, item in value.items() if key != field
    })
    if retained != expected:
        _fail(f"{label} self-hash differs")
    return retained


@dataclass(frozen=True, slots=True)
class ExactJsonObjectV1:
    """One caller-supplied immutable in-memory object."""

    identity: Mapping[str, object]
    raw: bytes


@dataclass(frozen=True, slots=True)
class ExactJsonFileV1:
    """One caller-selected local file bound to an immutable source identity."""

    identity: Mapping[str, object]
    path: Path


ExactJsonInputV1: TypeAlias = ExactJsonObjectV1 | ExactJsonFileV1


@dataclass(frozen=True, slots=True)
class HistoricalNeo4jGraphPlanV1:
    """Storage-neutral graph rows and their immutable decision manifest."""

    schema_version: str
    manifest: Mapping[str, object]
    nodes: tuple[dict[str, object], ...]
    relationships: tuple[dict[str, object], ...]
    plan_sha256: str

    def summary(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "evidence_class": EVIDENCE_CLASS,
            "threshold_dk": THRESHOLD_DK,
            "node_count": len(self.nodes),
            "relationship_count": len(self.relationships),
            "manifest_sha256": self.manifest["manifest_sha256"],
            "plan_sha256": self.plan_sha256,
            "production_policy_mutation": False,
            "promotion_authority": False,
        }


@dataclass(frozen=True, slots=True)
class _Expectations:
    slate_count: int
    candidate_count: int
    visit_count: int
    player_slate_count: int
    scope_membership_count: int
    book_count: int
    selection_count: int
    final_book_count: int
    final_selection_count: int
    high_score_count: int
    selected_high_score_count: int
    missed_high_score_count: int
    opportunity_slate_count: int
    converted_slate_count: int
    arms: tuple[str, ...]
    blocks: tuple[str, ...]
    visits_per_arm_block: int
    strategies_per_scope: int
    selections_per_book: int
    final_scope_ordinal: int
    final_fit_scope_id: str


_PRODUCTION_EXPECTATIONS: Final = _Expectations(
    slate_count=EXPECTED_SLATE_COUNT,
    candidate_count=EXPECTED_CANDIDATE_COUNT,
    visit_count=EXPECTED_VISIT_COUNT,
    player_slate_count=EXPECTED_PLAYER_SLATE_COUNT,
    scope_membership_count=EXPECTED_SCOPE_MEMBERSHIP_COUNT,
    book_count=EXPECTED_BOOK_COUNT,
    selection_count=EXPECTED_SELECTION_COUNT,
    final_book_count=EXPECTED_FINAL_BOOK_COUNT,
    final_selection_count=EXPECTED_FINAL_SELECTION_COUNT,
    high_score_count=EXPECTED_HIGH_SCORE_LINEUP_COUNT,
    selected_high_score_count=EXPECTED_SELECTED_HIGH_SCORE_LINEUP_COUNT,
    missed_high_score_count=EXPECTED_MISSED_HIGH_SCORE_LINEUP_COUNT,
    opportunity_slate_count=EXPECTED_OPPORTUNITY_SLATE_COUNT,
    converted_slate_count=EXPECTED_CONVERTED_SLATE_COUNT,
    arms=ARM_IDS,
    blocks=BLOCK_IDS,
    visits_per_arm_block=candidate_v1.VISITS_PER_BLOCK,
    strategies_per_scope=8,
    selections_per_book=80,
    final_scope_ordinal=FINAL_SCOPE_ORDINAL,
    final_fit_scope_id=FINAL_FIT_SCOPE_ID,
)


class _ExactObjectStore:
    def __init__(self, objects: Iterable[ExactJsonInputV1]) -> None:
        self._objects: dict[
            tuple[str, str, str, int], bytes | Path
        ] = {}
        self._uri_keys: dict[str, tuple[str, str, str, int]] = {}
        self._parsed: dict[tuple[str, str, str, int], dict[str, object]] = {}
        self._consumed: set[tuple[str, str, str, int]] = set()
        self._manifest: list[dict[str, object]] = []
        for ordinal, exact in enumerate(objects):
            identity = _identity(exact.identity, label=f"exact object[{ordinal}]")
            if isinstance(exact, ExactJsonObjectV1):
                source: bytes | Path = exact.raw
                if (
                    type(source) is not bytes
                    or len(source) != identity["bytes"]
                    or sha256(source).hexdigest() != identity["sha256"]
                ):
                    _fail(f"exact object[{ordinal}] differs from its identity")
            elif isinstance(exact, ExactJsonFileV1):
                source = exact.path
                if (
                    not isinstance(source, Path)
                    or not source.is_absolute()
                    or source.is_symlink()
                    or not source.is_file()
                ):
                    _fail(
                        f"exact object[{ordinal}] local path must be one "
                        "absolute regular non-symlink file"
                    )
            else:
                _fail(f"exact object[{ordinal}] input type differs")
            key = _identity_key(identity)
            uri = str(identity["uri"])
            if key in self._objects or uri in self._uri_keys:
                _fail("exact object bundle aliases an identity or URI")
            self._objects[key] = source
            self._uri_keys[uri] = key

    def read(
        self,
        identity_value: object,
        *,
        role: str,
        source_ordinal: int | None,
    ) -> dict[str, object]:
        identity = _identity(identity_value, label=f"{role} identity")
        key = _identity_key(identity)
        source = self._objects.get(key)
        if source is None:
            _fail(f"caller did not supply exact {role} bytes")
        if key not in self._parsed:
            try:
                raw = source if type(source) is bytes else source.read_bytes()
            except OSError as exc:
                raise CorpusR6HistoricalNeo4jSliceV1Error(
                    f"caller-supplied local {role} file could not be read"
                ) from exc
            if (
                len(raw) != identity["bytes"]
                or sha256(raw).hexdigest() != identity["sha256"]
            ):
                _fail(f"caller-supplied exact {role} bytes differ")
            self._parsed[key] = _parse_canonical_json(raw, label=role)
        if key not in self._consumed:
            row = {
                "schema_version": EXACT_OBJECT_SCHEMA,
                "source_object_ordinal": len(self._manifest),
                "role": role,
                "source_ordinal": source_ordinal,
                "identity": identity,
            }
            row["source_object_row_sha256"] = canonical_sha256(row)
            self._manifest.append(row)
            self._consumed.add(key)
        return self._parsed[key]

    def finish(self, *, expected_count: int) -> tuple[dict[str, object], ...]:
        if len(self._objects) != expected_count:
            _fail(
                f"exact object bundle count {len(self._objects)} differs from "
                f"required {expected_count}"
            )
        if self._consumed != set(self._objects):
            _fail("exact object bundle contains unconsumed or unbound bytes")
        return tuple(self._manifest)


def _validate_false_authorities(value: Mapping[str, object], *, label: str) -> None:
    forbidden_true = {
        "graph_mutation_licensed",
        "production_change_licensed",
        "promotion_authority",
        "decision_authority",
        "live_money_policy_authority",
        "causal_claims_licensed",
        "historical_retune_licensed",
        "corpus_fill_licensed",
        "selection_authority",
        "production_policy_authority",
    }
    for field in forbidden_true:
        if field in value and value[field] is not False:
            _fail(f"{label}.{field} must remain false")


def _validate_lineage_sidecar(
    value: Mapping[str, object],
    *,
    artifact: Mapping[str, object],
    expectations: _Expectations,
) -> tuple[dict[str, object], ...]:
    sidecar = _mapping(value, label="candidate lineage sidecar")
    _self_hash(
        sidecar,
        field="candidate_lineage_sidecar_sha256",
        label="candidate lineage sidecar",
    )
    _validate_false_authorities(sidecar, label="candidate lineage sidecar")
    if (
        sidecar.get("schema_version") != candidate_v1.LINEAGE_SIDECAR_SCHEMA
        or sidecar.get("source_task_ordinal")
        != artifact.get("source_task_ordinal")
        or sidecar.get("task_id") != artifact.get("task_id")
        or sidecar.get("slate") != artifact.get("slate")
        or sidecar.get("candidate_count") != artifact.get("candidate_count")
        or sidecar.get("arm_count") != len(expectations.arms)
        or sidecar.get("visits_per_block") != expectations.visits_per_arm_block
        or sidecar.get("uses_realized_outcomes") is not False
        or sidecar.get("outcome_columns_read") != []
    ):
        _fail("candidate lineage sidecar authority/task contract differs")
    rows = [
        _mapping(row, label=f"candidate lineage[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(sidecar.get("candidates"), label="candidate lineages")
        )
    ]
    artifact_rows = [
        _mapping(row, label=f"candidate row[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(artifact.get("rows"), label="candidate rows")
        )
    ]
    if (
        len(rows) != len(artifact_rows)
        or sidecar.get("candidate_lineage_manifest_sha256")
        != canonical_sha256(rows)
    ):
        _fail("candidate lineage population/hash differs")
    arm_visit_coordinates: dict[int, set[int]] = defaultdict(set)
    arm_block_visits: Counter[tuple[int, str]] = Counter()
    total_visits = 0
    normalized: list[dict[str, object]] = []
    expected_row_fields = frozenset({
        "candidate_id",
        "player_ids",
        "roster_sha256",
        "source_arm_ordinals",
        "source_arms",
        "origin_blocks",
        "occurrence_counts_by_block",
        "source_arms_by_block",
        "occurrence_count",
        "occurrences",
    })
    occurrence_fields = frozenset({
        "arm_ordinal",
        "parameter_set_id",
        "visit_ordinal",
        "block_id",
        "objective_world_index",
    })
    for ordinal, (row, artifact_row) in enumerate(
        zip(rows, artifact_rows, strict=True)
    ):
        if frozenset(row) != expected_row_fields:
            _fail(f"candidate lineage[{ordinal}] fields differ")
        candidate_id = _string(row["candidate_id"], label="lineage candidate ID")
        player_ids = [
            _string(item, label="lineage player ID")
            for item in _sequence(row["player_ids"], label="lineage player IDs")
        ]
        if (
            candidate_id != artifact_row.get("candidate_id")
            or player_ids != artifact_row.get("player_ids")
            or row.get("roster_sha256") != canonical_sha256(player_ids)
        ):
            _fail("candidate artifact/lineage roster equality differs")
        occurrences = [
            _mapping(item, label="candidate occurrence")
            for item in _sequence(row["occurrences"], label="candidate occurrences")
        ]
        if not occurrences:
            _fail("candidate lineage has no generation occurrence")
        counts_by_block: Counter[str] = Counter()
        arms_by_block: dict[str, set[str]] = defaultdict(set)
        arm_ordinals: set[int] = set()
        seen_coordinates: set[tuple[int, int]] = set()
        for occurrence in occurrences:
            if frozenset(occurrence) != occurrence_fields:
                _fail("candidate occurrence fields differ")
            arm_ordinal = _integer(
                occurrence["arm_ordinal"], label="occurrence arm ordinal"
            )
            visit_ordinal = _integer(
                occurrence["visit_ordinal"], label="occurrence visit ordinal"
            )
            block = _string(occurrence["block_id"], label="occurrence block")
            if (
                arm_ordinal >= len(expectations.arms)
                or occurrence["parameter_set_id"]
                != expectations.arms[arm_ordinal]
                or block not in expectations.blocks
                or (arm_ordinal, visit_ordinal) in seen_coordinates
                or type(occurrence["objective_world_index"]) is not int
                or occurrence["objective_world_index"] < 0
            ):
                _fail("candidate occurrence coordinate differs")
            seen_coordinates.add((arm_ordinal, visit_ordinal))
            arm_visit_coordinates[arm_ordinal].add(visit_ordinal)
            arm_block_visits[(arm_ordinal, block)] += 1
            arm_ordinals.add(arm_ordinal)
            counts_by_block[block] += 1
            arms_by_block[block].add(expectations.arms[arm_ordinal])
        expected_ordinals = sorted(arm_ordinals)
        expected_arms = [expectations.arms[index] for index in expected_ordinals]
        expected_blocks = [
            block for block in expectations.blocks if counts_by_block[block]
        ]
        expected_counts = {
            block: counts_by_block[block] for block in expectations.blocks
        }
        expected_block_arms = {
            block: sorted(arms_by_block[block]) for block in expectations.blocks
        }
        if (
            row["source_arm_ordinals"] != expected_ordinals
            or row["source_arms"] != expected_arms
            or row["origin_blocks"] != expected_blocks
            or row["occurrence_counts_by_block"] != expected_counts
            or row["source_arms_by_block"] != expected_block_arms
            or row["occurrence_count"] != len(occurrences)
        ):
            _fail("candidate recurrence summary differs from exact occurrences")
        total_visits += len(occurrences)
        normalized.append(row)
    expected_visits_per_arm = (
        len(expectations.blocks) * expectations.visits_per_arm_block
    )
    for arm_ordinal in range(len(expectations.arms)):
        if (
            arm_visit_coordinates[arm_ordinal]
            != set(range(expected_visits_per_arm))
        ):
            _fail("candidate lineage does not cover every arm visit exactly once")
        for block in expectations.blocks:
            if (
                arm_block_visits[(arm_ordinal, block)]
                != expectations.visits_per_arm_block
            ):
                _fail("candidate lineage arm/block visit denominator differs")
    if (
        sidecar.get("visit_occurrence_count") != total_visits
        or total_visits
        != len(expectations.arms)
        * len(expectations.blocks)
        * expectations.visits_per_arm_block
    ):
        _fail("candidate lineage visit census differs")
    return tuple(normalized)


def _validate_candidate_chain(
    store: _ExactObjectStore,
    *,
    root_identity: Mapping[str, object],
    catalog_outer_identity: Mapping[str, object],
    expectations: _Expectations,
    production_contract: bool,
) -> tuple[
    dict[str, object],
    tuple[dict[str, object], ...],
    tuple[tuple[dict[str, object], ...], ...],
    tuple[dict[str, object], ...],
]:
    root = store.read(root_identity, role="candidate_v2_root", source_ordinal=None)
    if production_contract:
        try:
            root = candidate_release.validate_fixed_g0_candidate_authority_release_structure_v2(
                root
            )
        except Exception as exc:
            raise CorpusR6HistoricalNeo4jSliceV1Error(
                "candidate-v2 terminal root validation failed"
            ) from exc
    else:
        _self_hash(
            root,
            field="candidate_authority_release_sha256",
            label="candidate-v2 terminal root",
        )
    if (
        root.get("schema_version") != candidate_release.RELEASE_SCHEMA
        or root.get("catalog_recovery_outer_identity")
        != _identity(catalog_outer_identity, label="catalog outer identity")
        or root.get("task_count") != expectations.slate_count
        or root.get("total_candidate_count") != expectations.candidate_count
        or root.get("total_visit_occurrence_count") != expectations.visit_count
        or root.get("candidate_population_authority") is not True
        or root.get("exact_occurrence_provenance_authority") is not True
        or root.get("uses_realized_outcomes") is not False
        or root.get("world_matrix_bodies_read") is not False
    ):
        _fail("candidate-v2 population or authority contract differs")
    _validate_false_authorities(root, label="candidate-v2 root")
    publication_rows = [
        _mapping(row, label=f"candidate publication[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(
                root.get("non_root_publication_manifest"),
                label="candidate publication manifest",
            )
        )
    ]
    descriptors = [
        _mapping(row, label=f"candidate descriptor[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(root.get("objects"), label="candidate descriptors")
        )
    ]
    if len(descriptors) != expectations.slate_count:
        _fail("candidate-v2 descriptor count differs")
    artifacts: dict[int, dict[str, object]] = {}
    sidecars: dict[int, dict[str, object]] = {}
    for row in publication_rows:
        role = _string(row.get("role"), label="candidate publication role")
        source_ordinal = row.get("source_task_ordinal")
        if source_ordinal is not None:
            source_ordinal = _integer(source_ordinal, label="candidate source ordinal")
        if role not in {
            "candidate_artifact",
            "exact_occurrence_lineage_sidecar",
        }:
            if role not in {
                "outer_bound_slate_derivation_receipt",
                "accepted_candidate_release",
                "outer_bound_panel_derivation_receipt",
            }:
                _fail(f"candidate publication role {role!r} is not allowed")
            # The exact terminal root binds these interstitial identities and
            # internal hashes.  They produce no graph rows and are intentionally
            # not required in the bounded caller-supplied byte bundle.
            continue
        body = store.read(
            row.get("identity"), role=f"candidate_{role}", source_ordinal=source_ordinal
        )
        if role == "candidate_artifact":
            if source_ordinal is None:
                _fail("candidate artifact has no source ordinal")
            try:
                artifacts[source_ordinal] = (
                    candidate_source.validate_accepted_candidate_artifact_v1(body)
                )
            except Exception as exc:
                raise CorpusR6HistoricalNeo4jSliceV1Error(
                    f"candidate artifact[{source_ordinal}] validation failed"
                ) from exc
        elif role == "exact_occurrence_lineage_sidecar":
            if source_ordinal is None:
                _fail("candidate lineage has no source ordinal")
            sidecars[source_ordinal] = body
    expected_ordinals = set(range(expectations.slate_count))
    if (
        set(artifacts) != expected_ordinals
        or set(sidecars) != expected_ordinals
    ):
        _fail("candidate-v2 graph-bearing leaf chain is incomplete")
    validated_lineages: list[tuple[dict[str, object], ...]] = []
    ordered_artifacts: list[dict[str, object]] = []
    ordered_descriptors: list[dict[str, object]] = []
    total_candidates = 0
    total_visits = 0
    for ordinal, descriptor in enumerate(descriptors):
        artifact = artifacts[ordinal]
        sidecar = sidecars[ordinal]
        lineages = _validate_lineage_sidecar(
            sidecar, artifact=artifact, expectations=expectations
        )
        if (
            descriptor.get("source_task_ordinal") != ordinal
            or descriptor.get("candidate_artifact_identity")
            != next(
                row["identity"]
                for row in publication_rows
                if row["role"] == "candidate_artifact"
                and row["source_task_ordinal"] == ordinal
            )
            or descriptor.get("lineage_sidecar_identity")
            != next(
                row["identity"]
                for row in publication_rows
                if row["role"] == "exact_occurrence_lineage_sidecar"
                and row["source_task_ordinal"] == ordinal
            )
            or descriptor.get("candidate_artifact_sha256")
            != artifact.get("candidate_artifact_sha256")
            or descriptor.get("lineage_sidecar_sha256")
            != sidecar.get("candidate_lineage_sidecar_sha256")
            or descriptor.get("candidate_count") != len(lineages)
            or descriptor.get("visit_occurrence_count")
            != sidecar.get("visit_occurrence_count")
        ):
            _fail(f"candidate-v2 object[{ordinal}] cross-binding differs")
        ordered_artifacts.append(artifact)
        ordered_descriptors.append(descriptor)
        validated_lineages.append(lineages)
        total_candidates += len(lineages)
        total_visits += int(sidecar["visit_occurrence_count"])
    if (
        total_candidates != expectations.candidate_count
        or total_visits != expectations.visit_count
    ):
        _fail("candidate-v2 aggregate/root reconciliation differs")
    return (
        root,
        tuple(ordered_artifacts),
        tuple(validated_lineages),
        tuple(ordered_descriptors),
    )


def _validate_catalog_chain(
    store: _ExactObjectStore,
    *,
    outer_identity: Mapping[str, object],
    candidate_root: Mapping[str, object],
    expectations: _Expectations,
) -> tuple[
    dict[str, object],
    tuple[dict[str, object], ...],
]:
    outer = store.read(
        outer_identity, role="catalog_outer_attestation", source_ordinal=None
    )
    _self_hash(
        outer,
        field="recovery_attestation_sha256",
        label="catalog outer attestation",
    )
    _validate_false_authorities(outer, label="catalog outer attestation")
    if (
        outer.get("schema_version") != catalog_recovery.OUTER_ATTESTATION_SCHEMA
        or outer.get("inner_object_count") != 2 * expectations.slate_count + 2
        or outer.get("all_inner_catalogs_exact_reopened") is not True
        or outer.get("outer_attestation_published_last") is not True
        or outer.get("world_matrix_bodies_read") is not False
        or outer.get("uses_realized_outcomes") is not False
        or candidate_root.get("catalog_recovery_outer_attestation_sha256")
        != outer.get("recovery_attestation_sha256")
        or candidate_root.get("catalog_release_identity")
        != outer.get("inner_catalog_release_identity")
    ):
        _fail("catalog outer/candidate binding differs")
    manifest = [
        _mapping(row, label=f"catalog manifest[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(outer.get("inner_object_manifest"), label="catalog manifest")
        )
    ]
    if (
        len(manifest) != 2 * expectations.slate_count + 2
        or outer.get("inner_object_manifest_sha256") != canonical_sha256(manifest)
    ):
        _fail("catalog outer manifest count/hash differs")
    catalogs: dict[int, dict[str, object]] = {}
    for ordinal, row in enumerate(manifest):
        role = _string(row.get("role"), label="catalog manifest role")
        source_ordinal = row.get("source_task_ordinal")
        if source_ordinal is not None:
            source_ordinal = _integer(source_ordinal, label="catalog source ordinal")
        if role != "player_catalog":
            if role not in {
                "catalog_derivation_receipt",
                "catalog_release",
                "inner_replay_receipt",
            }:
                _fail(f"catalog role {role!r} is not allowed")
            # The accepted outer attestation binds all 110 identities.  Only
            # structural catalogs contribute graph rows in this local slice.
            continue
        body = store.read(
            row.get("identity"), role=f"catalog_{role}", source_ordinal=source_ordinal
        )
        if row.get("object_ordinal") != ordinal:
            _fail("catalog object ordinal differs")
        if source_ordinal is None:
            _fail("player catalog has no source ordinal")
        try:
            catalogs[source_ordinal] = player_catalog.validate_player_catalog_v1(body)
        except Exception as exc:
            raise CorpusR6HistoricalNeo4jSliceV1Error(
                f"player catalog[{source_ordinal}] validation failed"
            ) from exc
    expected_ordinals = set(range(expectations.slate_count))
    if set(catalogs) != expected_ordinals:
        _fail("catalog graph-bearing leaf chain is incomplete")
    ordered_catalogs: list[dict[str, object]] = []
    total_players = 0
    for ordinal in range(expectations.slate_count):
        catalog = catalogs[ordinal]
        manifest_derivation = manifest[ordinal * 2]
        manifest_catalog = manifest[ordinal * 2 + 1]
        if (
            manifest_derivation.get("role") != "catalog_derivation_receipt"
            or manifest_catalog.get("role") != "player_catalog"
            or manifest_derivation.get("source_task_ordinal") != ordinal
            or manifest_catalog.get("source_task_ordinal") != ordinal
            or catalog.get("source_authority") != manifest_derivation.get("identity")
            or catalog.get("source_task_ordinal") != ordinal
        ):
            _fail(f"catalog[{ordinal}] outer/derivation identity binding differs")
        ordered_catalogs.append(catalog)
        total_players += int(catalog["player_count"])
    if (
        total_players != expectations.player_slate_count
    ):
        _fail("structural PlayerSlate population differs")
    return outer, tuple(ordered_catalogs)


def _validate_attribution_chain(
    store: _ExactObjectStore,
    *,
    root_identity: Mapping[str, object],
    expectations: _Expectations,
    production_contract: bool,
) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    root = store.read(
        root_identity, role="no_rescore_funnel_root", source_ordinal=None
    )
    if production_contract:
        try:
            root = no_rescore_funnel.validate_no_rescore_funnel_release_v1(root)
        except Exception as exc:
            raise CorpusR6HistoricalNeo4jSliceV1Error(
                "no-rescore funnel terminal root validation failed"
            ) from exc
    else:
        _self_hash(
            root,
            field="funnel_release_sha256",
            label="no-rescore funnel terminal root",
        )
    population = _mapping(root.get("population_result"), label="population result")
    population_thresholds = [
        _mapping(row, label=f"population threshold[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(population.get("thresholds"), label="population thresholds")
        )
    ]
    high_population_rows = [
        row for row in population_thresholds if row.get("threshold_dk") == THRESHOLD_DK
    ]
    diagnostic_union = _mapping(
        root.get("diagnostic_union_result"), label="diagnostic union result"
    )
    diagnostic_thresholds = [
        _mapping(row, label=f"diagnostic threshold[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(diagnostic_union.get("thresholds"), label="diagnostic thresholds")
        )
    ]
    high_diagnostic_rows = [
        row for row in diagnostic_thresholds if row.get("threshold_dk") == THRESHOLD_DK
    ]
    if (
        root.get("schema_version") != no_rescore_funnel.FUNNEL_RELEASE_SCHEMA
        or root.get("source_slate_count") != expectations.slate_count
        or population.get("lineup_count") != expectations.candidate_count
        or population.get("nominal_generation_occurrence_count")
        != expectations.visit_count
        or len(high_population_rows) != 1
        or high_population_rows[0].get("population_lineup_count")
        != expectations.high_score_count
        or high_population_rows[0].get("population_opportunity_slates")
        != expectations.opportunity_slate_count
        or len(high_diagnostic_rows) != 1
        or high_diagnostic_rows[0].get("selected_qualifying_lineup_count")
        != expectations.selected_high_score_count
        or high_diagnostic_rows[0].get("observed_hit_slates")
        != expectations.converted_slate_count
        or root.get("uses_realized_outcomes") is not True
        or root.get("no_rescore") is not True
        or root.get("raw_outcome_source_read") is not False
        or root.get("outcome_snapshot_read") is not False
        or root.get("outcome_query_executed") is not False
        or root.get("lineup_rescore_performed") is not False
        or root.get("realized_lineup_scores_from_terminal_attribution_only")
        is not True
    ):
        _fail("no-rescore funnel population or authority law differs")
    _validate_false_authorities(root, label="no-rescore funnel root")
    predecessors = _mapping(root.get("predecessors"), label="funnel predecessors")
    shard_identities = [
        _identity(row, label=f"attribution shard identity[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(
                predecessors.get("attribution_shard_identities"),
                label="attribution shard identities",
            )
        )
    ]
    slate_rows = [
        _mapping(row, label=f"funnel slate row[{ordinal}]")
        for ordinal, row in enumerate(
            _sequence(root.get("slate_rows"), label="funnel slate rows")
        )
    ]
    if (
        len(shard_identities) != expectations.slate_count
        or len(slate_rows) != expectations.slate_count
    ):
        _fail("attribution shard count differs")
    shards: list[dict[str, object]] = []
    for ordinal, (identity, slate_row) in enumerate(
        zip(shard_identities, slate_rows, strict=True)
    ):
        body = store.read(
            identity,
            role="attribution_slate_shard",
            source_ordinal=ordinal,
        )
        try:
            shard = attribution.validate_slate_attribution_structure_v1(body)
        except Exception as exc:
            raise CorpusR6HistoricalNeo4jSliceV1Error(
                f"attribution shard[{ordinal}] validation failed"
            ) from exc
        if (
            slate_row.get("source_ordinal") != ordinal
            or shard.get("source_ordinal") != ordinal
            or slate_row.get("slate_id") != shard.get("slate_id")
            or slate_row.get("attribution_shard_identity") != identity
            or slate_row.get("attribution_shard_sha256")
            != shard.get("slate_attribution_sha256")
            or _mapping(
                slate_row.get("corpus"), label=f"funnel corpus row[{ordinal}]"
            ).get("lineup_count")
            != shard.get("lineup_count")
        ):
            _fail(f"attribution shard[{ordinal}] funnel binding differs")
        shards.append(shard)
    return root, tuple(shards)


def _node(kind: str, logical_id: str, properties: Mapping[str, object]) -> dict[str, object]:
    normalized = dict(properties)
    payload_sha = canonical_sha256(normalized)
    node_id = f"historical-r6:{kind}:{canonical_sha256(logical_id)}"
    return {
        "schema_version": NODE_SCHEMA,
        "id": node_id,
        "kind": kind,
        "logical_id": logical_id,
        "properties_json": canonical_json_bytes(normalized).decode("utf-8"),
        "payload_sha256": payload_sha,
        "evidence_class": EVIDENCE_CLASS,
        "promotion_authority": False,
        "policy_feedback_authority": False,
    }


def _relationship(
    from_id: str,
    to_id: str,
    relationship_type: str,
    properties: Mapping[str, object],
) -> dict[str, object]:
    normalized = dict(properties)
    coordinate = {
        "from_id": from_id,
        "to_id": to_id,
        "relationship_type": relationship_type,
    }
    return {
        "schema_version": RELATIONSHIP_SCHEMA,
        **coordinate,
        "edge_key": canonical_sha256(coordinate),
        "properties_json": canonical_json_bytes(normalized).decode("utf-8"),
        "payload_sha256": canonical_sha256(normalized),
        "evidence_class": EVIDENCE_CLASS,
        "promotion_authority": False,
        "policy_feedback_authority": False,
    }


def _dk_structural_phenotype(
    roster: Sequence[str], catalog_by_id: Mapping[str, Mapping[str, object]]
) -> dict[str, object]:
    players = [catalog_by_id[player_id] for player_id in roster]
    positions = Counter(str(player["pos"]) for player in players)
    teams = Counter(str(player["team"]) for player in players)
    games = Counter(str(player["game_id"]) for player in players)
    if (
        len(players) != 9
        or positions["QB"] != 1
        or positions["DST"] != 1
        or positions["RB"] not in {2, 3}
        or positions["WR"] not in {3, 4}
        or positions["TE"] not in {1, 2}
        or positions["RB"] + positions["WR"] + positions["TE"] != 7
    ):
        _fail("accepted lineup no longer has DraftKings Classic roster shape")
    total_salary = sum(int(player["salary"]) for player in players)
    if total_salary > 50_000:
        _fail("accepted lineup exceeds the DraftKings salary cap")
    qb = next(player for player in players if player["pos"] == "QB")
    qb_team = str(qb["team"])
    qb_opponent = str(qb["opp"])
    return {
        "salary": total_salary,
        "position_counts": {
            position: positions[position]
            for position in ("QB", "RB", "WR", "TE", "DST")
        },
        "distinct_team_count": len(teams),
        "distinct_game_count": len(games),
        "maximum_same_team_count": max(teams.values()),
        "maximum_same_game_count": max(games.values()),
        "qb_team": qb_team,
        "qb_opponent": qb_opponent,
        "qb_teammate_count": sum(
            player["team"] == qb_team and player["pos"] != "QB"
            for player in players
        ),
        "qb_opponent_count": sum(
            player["team"] == qb_opponent for player in players
        ),
    }


def _project_graph_from_validated_sources(
    *,
    candidate_artifacts: Sequence[Mapping[str, object]],
    candidate_lineages: Sequence[Sequence[Mapping[str, object]]],
    catalogs: Sequence[Mapping[str, object]],
    attribution_shards: Sequence[Mapping[str, object]],
    source_root_identities: Mapping[str, Mapping[str, object]],
    source_manifest: Sequence[Mapping[str, object]],
    expectations: _Expectations,
) -> HistoricalNeo4jGraphPlanV1:
    if not (
        len(candidate_artifacts)
        == len(candidate_lineages)
        == len(catalogs)
        == len(attribution_shards)
        == expectations.slate_count
    ):
        _fail("validated source-slate vectors differ")
    nodes: list[dict[str, object]] = []
    relationships: list[dict[str, object]] = []
    source_nodes: dict[str, dict[str, object]] = {}
    for role, identity in sorted(source_root_identities.items()):
        source_node = _node(
            "SourceAuthority",
            f"source:{role}:{identity['sha256']}",
            {"role": role, "identity": dict(identity)},
        )
        source_nodes[role] = source_node
        nodes.append(source_node)
    slice_node = _node(
        "HistoricalCorpusSlice",
        "r6-fixed-g0-full-union-realized-ge200-v1",
        {
            "threshold_dk": THRESHOLD_DK,
            "evidence_class": EVIDENCE_CLASS,
            "winner_evidence_included": False,
            "feedback_authority": False,
        },
    )
    nodes.append(slice_node)
    for role, source_node in sorted(source_nodes.items()):
        relationships.append(_relationship(
            slice_node["id"],
            source_node["id"],
            "DERIVED_FROM",
            {"source_role": role},
        ))

    total_candidates = 0
    total_visits = 0
    total_players = 0
    total_scope_memberships = 0
    total_books = 0
    total_selections = 0
    final_book_count = 0
    final_selection_count = 0
    high_score_count = 0
    selected_high_score_count = 0
    missed_high_score_count = 0
    opportunity_slate_count = 0
    converted_slate_count = 0
    denominator_rows: list[dict[str, object]] = []
    candidate_digest_rows: list[dict[str, object]] = []
    catalog_digest_rows: list[dict[str, object]] = []
    attribution_digest_rows: list[dict[str, object]] = []
    final_book_digest_rows: list[dict[str, object]] = []
    final_selection_digest_rows: list[dict[str, object]] = []

    for source_ordinal, (artifact, lineages, catalog, shard) in enumerate(
        zip(
            candidate_artifacts,
            candidate_lineages,
            catalogs,
            attribution_shards,
            strict=True,
        )
    ):
        slate = _mapping(artifact.get("slate"), label="candidate slate")
        slate_id = _string(slate.get("slate_id"), label="candidate slate ID")
        if (
            artifact.get("source_task_ordinal") != source_ordinal
            or catalog.get("source_task_ordinal") != source_ordinal
            or shard.get("source_ordinal") != source_ordinal
            or shard.get("slate_id") != slate_id
            or _mapping(catalog.get("slate"), label="catalog slate").get("slate_id")
            != slate_id
        ):
            _fail(f"source slate[{source_ordinal}] identity differs across chains")
        artifact_rows = [
            _mapping(row, label="candidate artifact row")
            for row in _sequence(artifact.get("rows"), label="candidate rows")
        ]
        lineup_rows = [
            _mapping(row, label="attribution lineup row")
            for row in _sequence(shard.get("lineup_rows"), label="lineup rows")
        ]
        if len(artifact_rows) != len(lineages) or len(lineup_rows) != len(lineages):
            _fail("candidate/lineage/realized lineup population differs")
        candidate_ids = [str(row["candidate_id"]) for row in artifact_rows]
        realized_ids = [str(row["lineup_id"]) for row in lineup_rows]
        lineage_ids = [str(row["candidate_id"]) for row in lineages]
        if (
            candidate_ids != sorted(set(candidate_ids))
            or realized_ids != candidate_ids
            or lineage_ids != candidate_ids
        ):
            _fail("candidate set/order equality differs before slicing")
        catalog_rows = [
            _mapping(row, label="structural PlayerSlate row")
            for row in _sequence(catalog.get("players"), label="catalog players")
        ]
        catalog_by_id = {str(row["id"]): row for row in catalog_rows}
        if len(catalog_by_id) != len(catalog_rows):
            _fail("structural PlayerSlate IDs repeat within a slate")
        for candidate_row, realized_row in zip(
            artifact_rows, lineup_rows, strict=True
        ):
            roster = list(candidate_row["player_ids"])
            if (
                realized_row.get("roster_player_ids") != roster
                or realized_row.get("roster_identity_sha256")
                != canonical_sha256(roster)
                or len(roster) != 9
                or any(player_id not in catalog_by_id for player_id in roster)
            ):
                _fail("candidate/realized/catalog roster equality differs")
        high_rows = [
            row for row in lineup_rows
            if int(row["realized_score_micro"]) >= THRESHOLD_MICRO
        ]
        high_ids = {str(row["lineup_id"]) for row in high_rows}
        if any(
            (THRESHOLD_DK in row["at_or_above_thresholds_dk"])
            != (str(row["lineup_id"]) in high_ids)
            for row in lineup_rows
        ):
            _fail("persisted threshold flags differ from persisted score")
        high_score_count += len(high_rows)
        if high_rows:
            opportunity_slate_count += 1
        total_candidates += len(artifact_rows)
        total_players += len(catalog_rows)
        total_visits += sum(int(row["occurrence_count"]) for row in lineages)
        total_scope_memberships += int(shard["scope_membership_count"])
        total_books += int(shard["book_count"])
        total_selections += int(shard["selection_count"])

        slate_node = _node(
            "Slate",
            f"slate:{source_ordinal}:{slate_id}",
            {
                "source_ordinal": source_ordinal,
                "slate_id": slate_id,
                "season": slate.get("season"),
                "week": slate.get("week"),
                "candidate_count": len(artifact_rows),
                "high_score_lineup_count": len(high_rows),
            },
        )
        nodes.append(slate_node)
        relationships.append(_relationship(
            slice_node["id"], slate_node["id"], "CONTAINS_SLATE", {}
        ))

        lineage_by_id = {str(row["candidate_id"]): row for row in lineages}
        high_lineup_nodes: dict[str, dict[str, object]] = {}
        for realized_row in high_rows:
            lineup_id = str(realized_row["lineup_id"])
            lineage = lineage_by_id[lineup_id]
            realized_arms = sorted(
                _string(value, label="attribution training source arm")
                for value in _sequence(
                    realized_row.get("training_source_arms"),
                    label="attribution training source arms",
                )
            )
            lineage_arms = sorted(
                _string(value, label="lineage source arm")
                for value in _sequence(
                    lineage.get("source_arms"), label="lineage source arms"
                )
            )
            realized_block_arms = {
                str(block): sorted(
                    _string(value, label="attribution block source arm")
                    for value in _sequence(values, label="attribution block source arms")
                )
                for block, values in _mapping(
                    realized_row.get("training_source_arms_by_block"),
                    label="attribution source arms by block",
                ).items()
            }
            lineage_block_arms = {
                str(block): sorted(
                    _string(value, label="lineage block source arm")
                    for value in _sequence(values, label="lineage block source arms")
                )
                for block, values in _mapping(
                    lineage.get("source_arms_by_block"),
                    label="lineage source arms by block",
                ).items()
            }
            if (
                realized_row.get("training_origin_blocks")
                != lineage.get("origin_blocks")
                or realized_arms != lineage_arms
                or realized_row.get("training_occurrence_counts_by_block")
                != lineage.get("occurrence_counts_by_block")
                or realized_block_arms != lineage_block_arms
                or realized_row.get("training_occurrence_count")
                != lineage.get("occurrence_count")
            ):
                _fail("attribution generation summary differs from exact lineage")
            roster = [str(value) for value in realized_row["roster_player_ids"]]
            phenotype = _dk_structural_phenotype(roster, catalog_by_id)
            lineup_node = _node(
                "LineupCandidate",
                f"lineup:{source_ordinal}:{lineup_id}",
                {
                    "source_ordinal": source_ordinal,
                    "slate_id": slate_id,
                    "lineup_id": lineup_id,
                    "roster_identity_sha256": realized_row[
                        "roster_identity_sha256"
                    ],
                    "realized_score_micro": realized_row[
                        "realized_score_micro"
                    ],
                    "realized_union_rank": realized_row[
                        "realized_union_rank"
                    ],
                    "regret_to_union_maximum_micro": realized_row[
                        "regret_to_union_maximum_micro"
                    ],
                    "selected_final_book_count": 0,
                    "structural_phenotype": phenotype,
                    "persisted_no_rescore": True,
                    "winner_claim": False,
                },
            )
            nodes.append(lineup_node)
            high_lineup_nodes[lineup_id] = lineup_node
            relationships.append(_relationship(
                slate_node["id"],
                lineup_node["id"],
                "HAS_HIGH_SCORER",
                {"threshold_dk": THRESHOLD_DK},
            ))
            for roster_ordinal, player_id in enumerate(roster):
                player = catalog_by_id[player_id]
                player_node = _node(
                    "PlayerSlate",
                    f"player-slate:{source_ordinal}:{player_id}",
                    {
                        "source_ordinal": source_ordinal,
                        "slate_id": slate_id,
                        "player_id": player_id,
                        "position": player["pos"],
                        "team": player["team"],
                        "opponent": player["opp"],
                        "game_id": player["game_id"],
                        "salary": player["salary"],
                    },
                )
                nodes.append(player_node)
                relationships.append(_relationship(
                    lineup_node["id"],
                    player_node["id"],
                    "CONTAINS_PLAYER",
                    {"roster_ordinal": roster_ordinal},
                ))

        denom: dict[tuple[str, str, str], dict[str, int]] = {}
        dimension_coordinates = [
            ("arm", arm, "") for arm in expectations.arms
        ] + [
            ("block", block, "") for block in expectations.blocks
        ] + [
            ("arm-block", arm, block)
            for arm in expectations.arms
            for block in expectations.blocks
        ]
        for coordinate in dimension_coordinates:
            denom[coordinate] = {
                "candidate_count": 0,
                "visit_count": 0,
                "high_score_candidate_count": 0,
                "high_score_visit_count": 0,
            }
        high_cell_counts: dict[str, Counter[tuple[str, str]]] = {}
        for lineage in lineages:
            lineup_id = str(lineage["candidate_id"])
            occurrences = [
                _mapping(row, label="denominator occurrence")
                for row in lineage["occurrences"]
            ]
            cell_counts = Counter(
                (str(row["parameter_set_id"]), str(row["block_id"]))
                for row in occurrences
            )
            high_cell_counts[lineup_id] = cell_counts
            arm_counts = Counter()
            block_counts = Counter()
            for (arm, block), count in cell_counts.items():
                arm_counts[arm] += count
                block_counts[block] += count
                row = denom[("arm-block", arm, block)]
                row["candidate_count"] += 1
                row["visit_count"] += count
                if lineup_id in high_ids:
                    row["high_score_candidate_count"] += 1
                    row["high_score_visit_count"] += count
            for arm, count in arm_counts.items():
                row = denom[("arm", arm, "")]
                row["candidate_count"] += 1
                row["visit_count"] += count
                if lineup_id in high_ids:
                    row["high_score_candidate_count"] += 1
                    row["high_score_visit_count"] += count
            for block, count in block_counts.items():
                row = denom[("block", block, "")]
                row["candidate_count"] += 1
                row["visit_count"] += count
                if lineup_id in high_ids:
                    row["high_score_candidate_count"] += 1
                    row["high_score_visit_count"] += count
        for (kind, value, block), counts in sorted(denom.items()):
            expected_visits = {
                "arm": len(expectations.blocks) * expectations.visits_per_arm_block,
                "block": len(expectations.arms) * expectations.visits_per_arm_block,
                "arm-block": expectations.visits_per_arm_block,
            }[kind]
            if counts["visit_count"] != expected_visits:
                _fail("full-population generation denominator differs")
            denominator_row = {
                "source_ordinal": source_ordinal,
                "slate_id": slate_id,
                "dimension_kind": kind,
                "dimension_value": value,
                "block_id": block or None,
                **counts,
                "full_population_candidate_count": len(lineages),
            }
            denominator_rows.append(denominator_row)
            denom_node = _node(
                "GenerationDenominator",
                f"denominator:{source_ordinal}:{kind}:{value}:{block}",
                denominator_row,
            )
            nodes.append(denom_node)
            relationships.append(_relationship(
                slate_node["id"], denom_node["id"], "HAS_DENOMINATOR", {}
            ))
            if kind == "arm-block":
                for lineup_id, lineup_node in sorted(high_lineup_nodes.items()):
                    count = high_cell_counts[lineup_id][(value, block)]
                    if count:
                        relationships.append(_relationship(
                            lineup_node["id"],
                            denom_node["id"],
                            "GENERATED_IN_CELL",
                            {"visit_occurrence_count": count},
                        ))

        book_rows = [
            _mapping(row, label="attribution book row")
            for row in _sequence(shard.get("book_rows"), label="book rows")
        ]
        selection_rows = [
            _mapping(row, label="attribution selection row")
            for row in _sequence(shard.get("selection_rows"), label="selection rows")
        ]
        final_books = [
            row for row in book_rows
            if row.get("scope_ordinal") == expectations.final_scope_ordinal
        ]
        final_selections = [
            row for row in selection_rows
            if row.get("scope_ordinal") == expectations.final_scope_ordinal
        ]
        if (
            len(final_books) != expectations.strategies_per_scope
            or len(final_selections)
            != expectations.strategies_per_scope * expectations.selections_per_book
            or any(
                row.get("fit_scope_id") != expectations.final_fit_scope_id
                for row in [*final_books, *final_selections]
            )
        ):
            _fail("final-fit book/selection slice differs")
        selections_by_book: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in final_selections:
            selections_by_book[str(row["book_id"])].append(row)
        selected_final_count: Counter[str] = Counter()
        for book in sorted(final_books, key=lambda row: int(row["strategy_ordinal"])):
            book_id = str(book["book_id"])
            selections = sorted(
                selections_by_book[book_id], key=lambda row: int(row["selection_rank"])
            )
            selected_ids = [str(row["lineup_id"]) for row in selections]
            if (
                len(selections) != expectations.selections_per_book
                or [row["selection_rank"] for row in selections]
                != list(range(expectations.selections_per_book))
                or book.get("selected_lineup_count")
                != expectations.selections_per_book
                or book.get("selected_lineup_ids_sha256")
                != canonical_sha256(selected_ids)
                or book.get("eligible_lineup_count") != len(lineages)
            ):
                _fail("final-fit selected book roster/order differs")
            selection_by_id = {str(row["lineup_id"]): row for row in selections}
            book_node = _node(
                "FinalFitBook",
                f"book:{source_ordinal}:{book_id}",
                {
                    "source_ordinal": source_ordinal,
                    "slate_id": slate_id,
                    "book_id": book_id,
                    "strategy_ordinal": book["strategy_ordinal"],
                    "strategy_id": book["strategy_id"],
                    "eligible_lineup_count": book["eligible_lineup_count"],
                    "selected_lineup_count": book["selected_lineup_count"],
                    "eligible_maximum_score_micro": book[
                        "eligible_maximum_score_micro"
                    ],
                    "selected_maximum_score_micro": book[
                        "selected_maximum_score_micro"
                    ],
                    "selector_regret_micro": book["selector_regret_micro"],
                    "threshold_capture": book["threshold_capture"],
                },
            )
            nodes.append(book_node)
            relationships.append(_relationship(
                slate_node["id"], book_node["id"], "HAS_FINAL_FIT_BOOK", {}
            ))
            for lineup_id, lineup_node in sorted(high_lineup_nodes.items()):
                selected_row = selection_by_id.get(lineup_id)
                if selected_row is None:
                    relationships.append(_relationship(
                        book_node["id"],
                        lineup_node["id"],
                        "MISSED_HIGH_SCORER",
                        {"reason": "not-selected-by-final-fit-book"},
                    ))
                else:
                    selected_final_count[lineup_id] += 1
                    relationships.append(_relationship(
                        book_node["id"],
                        lineup_node["id"],
                        "SELECTED_HIGH_SCORER",
                        {
                            "selection_rank": selected_row["selection_rank"],
                            "realized_score_micro": selected_row[
                                "realized_score_micro"
                            ],
                        },
                    ))
        # Replace each high-lineup node once so its selection-stability property is exact.
        replacements = {
            node["id"]: _node(
                "LineupCandidate",
                node["logical_id"],
                {
                    **json.loads(node["properties_json"]),
                    "selected_final_book_count": selected_final_count[
                        str(json.loads(node["properties_json"])["lineup_id"])
                    ],
                },
            )
            for node in high_lineup_nodes.values()
        }
        nodes = [replacements.get(str(node["id"]), node) for node in nodes]
        high_lineup_nodes = {
            lineup_id: replacements[str(node["id"])]
            for lineup_id, node in high_lineup_nodes.items()
        }
        selected_on_slate = sum(
            selected_final_count[lineup_id] > 0 for lineup_id in high_ids
        )
        selected_high_score_count += selected_on_slate
        missed_high_score_count += len(high_ids) - selected_on_slate
        if selected_on_slate:
            converted_slate_count += 1

        final_book_count += len(final_books)
        final_selection_count += len(final_selections)
        candidate_digest_rows.append({
            "source_ordinal": source_ordinal,
            "candidate_row_manifest_sha256": artifact[
                "candidate_row_manifest_sha256"
            ],
            "candidate_lineage_manifest_sha256": canonical_sha256(list(lineages)),
        })
        catalog_digest_rows.append({
            "source_ordinal": source_ordinal,
            "structural_player_rows_sha256": canonical_sha256(catalog_rows),
        })
        attribution_digest_rows.append({
            "source_ordinal": source_ordinal,
            "lineup_rows_sha256": shard["lineup_rows_sha256"],
            "scope_membership_rows_sha256": shard[
                "scope_membership_rows_sha256"
            ],
            "book_rows_sha256": shard["book_rows_sha256"],
            "selection_rows_sha256": shard["selection_rows_sha256"],
        })
        final_book_digest_rows.append({
            "source_ordinal": source_ordinal,
            "final_book_rows_sha256": canonical_sha256(final_books),
        })
        final_selection_digest_rows.append({
            "source_ordinal": source_ordinal,
            "final_selection_rows_sha256": canonical_sha256(final_selections),
        })

    reconciliation = {
        "source_slate_count": expectations.slate_count,
        "candidate_count": total_candidates,
        "visit_occurrence_count": total_visits,
        "player_slate_count": total_players,
        "scope_membership_count": total_scope_memberships,
        "book_count": total_books,
        "selection_count": total_selections,
        "final_fit_book_count": final_book_count,
        "final_fit_selection_count": final_selection_count,
        "high_score_lineup_count": high_score_count,
        "selected_high_score_lineup_count": selected_high_score_count,
        "missed_high_score_lineup_count": missed_high_score_count,
        "opportunity_slate_count": opportunity_slate_count,
        "converted_slate_count": converted_slate_count,
        "candidate_attribution_roster_equality": True,
        "exact_nine_player_catalog_join": True,
        "candidate_lineage_recurrence_reconciled": True,
        "full_population_denominators_retained": True,
    }
    expected_reconciliation = {
        "candidate_count": expectations.candidate_count,
        "visit_occurrence_count": expectations.visit_count,
        "player_slate_count": expectations.player_slate_count,
        "scope_membership_count": expectations.scope_membership_count,
        "book_count": expectations.book_count,
        "selection_count": expectations.selection_count,
        "final_fit_book_count": expectations.final_book_count,
        "final_fit_selection_count": expectations.final_selection_count,
        "high_score_lineup_count": expectations.high_score_count,
        "selected_high_score_lineup_count": expectations.selected_high_score_count,
        "missed_high_score_lineup_count": expectations.missed_high_score_count,
        "opportunity_slate_count": expectations.opportunity_slate_count,
        "converted_slate_count": expectations.converted_slate_count,
    }
    if any(
        reconciliation[field] != expected
        for field, expected in expected_reconciliation.items()
    ):
        _fail("historical graph pre-slice reconciliation differs")

    # PlayerSlate nodes are intentionally shared across high lineups.  Exact payload
    # equality is required before deduplication; any identity collision fails.
    deduped_nodes: dict[str, dict[str, object]] = {}
    for node in nodes:
        prior = deduped_nodes.setdefault(str(node["id"]), node)
        if prior != node:
            _fail("historical graph node identity collision")
    deduped_relationships: dict[str, dict[str, object]] = {}
    for row in relationships:
        prior = deduped_relationships.setdefault(str(row["edge_key"]), row)
        if prior != row:
            _fail("historical graph relationship identity collision")
    ordered_nodes = tuple(sorted(
        deduped_nodes.values(), key=lambda row: (str(row["kind"]), str(row["logical_id"]))
    ))
    ordered_relationships = tuple(sorted(
        deduped_relationships.values(),
        key=lambda row: (
            str(row["from_id"]),
            str(row["to_id"]),
            str(row["relationship_type"]),
        ),
    ))
    row_digest_manifest = {
        "candidate_rows": candidate_digest_rows,
        "candidate_rows_sha256": canonical_sha256(candidate_digest_rows),
        "catalog_rows": catalog_digest_rows,
        "catalog_rows_sha256": canonical_sha256(catalog_digest_rows),
        "attribution_rows": attribution_digest_rows,
        "attribution_rows_sha256": canonical_sha256(attribution_digest_rows),
        "final_fit_book_rows": final_book_digest_rows,
        "final_fit_book_rows_sha256": canonical_sha256(final_book_digest_rows),
        "final_fit_selection_rows": final_selection_digest_rows,
        "final_fit_selection_rows_sha256": canonical_sha256(
            final_selection_digest_rows
        ),
        "generation_denominator_rows_sha256": canonical_sha256(denominator_rows),
    }
    source_rows = [dict(row) for row in source_manifest]
    manifest_body: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA,
        "evidence_class": EVIDENCE_CLASS,
        "threshold_dk": THRESHOLD_DK,
        "threshold_micro": THRESHOLD_MICRO,
        "source_root_identities": {
            role: dict(identity)
            for role, identity in sorted(source_root_identities.items())
        },
        "source_object_count": len(source_rows),
        "source_object_manifest": source_rows,
        "source_object_manifest_sha256": canonical_sha256(source_rows),
        "source_row_digest_manifest": row_digest_manifest,
        "source_row_digest_manifest_sha256": canonical_sha256(row_digest_manifest),
        "reconciliation": reconciliation,
        "node_count": len(ordered_nodes),
        "node_rows_sha256": canonical_sha256(list(ordered_nodes)),
        "relationship_count": len(ordered_relationships),
        "relationship_rows_sha256": canonical_sha256(
            list(ordered_relationships)
        ),
        "persisted_realized_labels_only": True,
        "raw_outcome_query_performed": False,
        "lineup_rescore_performed": False,
        "winner_nodes_included": False,
        "official_claims_included": False,
        "paid_or_live_data_included": False,
        "world_matrix_bodies_included": False,
        "neo4j_mutation_performed": False,
        "ui_or_route_change_performed": False,
        "deployment_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
        "policy_feedback_authority": False,
        "complete": True,
    }
    manifest_body["manifest_sha256"] = canonical_sha256(manifest_body)
    plan_body = {
        "schema_version": PLAN_SCHEMA,
        "manifest": manifest_body,
        "nodes": list(ordered_nodes),
        "relationships": list(ordered_relationships),
    }
    return HistoricalNeo4jGraphPlanV1(
        schema_version=PLAN_SCHEMA,
        manifest=manifest_body,
        nodes=ordered_nodes,
        relationships=ordered_relationships,
        plan_sha256=canonical_sha256(plan_body),
    )


def build_historical_corpus_graph_plan_v1(
    *,
    exact_objects: Iterable[ExactJsonInputV1],
    candidate_root_identity: Mapping[str, object],
    catalog_outer_identity: Mapping[str, object],
    attribution_root_identity: Mapping[str, object],
) -> HistoricalNeo4jGraphPlanV1:
    """Validate the three accepted chains and build the bounded graph plan.

    The signature intentionally exposes neither a reader callback nor an
    expectations override.  Therefore the adapter cannot fetch alternate
    objects and cannot silently project a partial population.
    """

    store = _ExactObjectStore(exact_objects)
    candidate_root, artifacts, lineages, _descriptors = _validate_candidate_chain(
        store,
        root_identity=candidate_root_identity,
        catalog_outer_identity=catalog_outer_identity,
        expectations=_PRODUCTION_EXPECTATIONS,
        production_contract=True,
    )
    _catalog_outer, catalogs = _validate_catalog_chain(
        store,
        outer_identity=catalog_outer_identity,
        candidate_root=candidate_root,
        expectations=_PRODUCTION_EXPECTATIONS,
    )
    _attribution_root, shards = _validate_attribution_chain(
        store,
        root_identity=attribution_root_identity,
        expectations=_PRODUCTION_EXPECTATIONS,
        production_contract=True,
    )
    source_manifest = store.finish(expected_count=EXPECTED_EXACT_OBJECT_COUNT)
    root_identities = {
        "candidate_v2": _identity(
            candidate_root_identity, label="candidate root identity"
        ),
        "catalog_outer": _identity(
            catalog_outer_identity, label="catalog outer identity"
        ),
        "no_rescore_funnel": _identity(
            attribution_root_identity, label="attribution root identity"
        ),
    }
    return _project_graph_from_validated_sources(
        candidate_artifacts=artifacts,
        candidate_lineages=lineages,
        catalogs=catalogs,
        attribution_shards=shards,
        source_root_identities=root_identities,
        source_manifest=source_manifest,
        expectations=_PRODUCTION_EXPECTATIONS,
    )


SCHEMA_STATEMENTS: Final[tuple[str, ...]] = (
    "CREATE CONSTRAINT historical_corpus_entity_id IF NOT EXISTS "
    "FOR (n:HistoricalCorpusEntity) REQUIRE n.id IS UNIQUE",
    "CREATE INDEX historical_corpus_entity_kind IF NOT EXISTS "
    "FOR (n:HistoricalCorpusEntity) ON (n.kind)",
    "CREATE INDEX historical_corpus_entity_logical_id IF NOT EXISTS "
    "FOR (n:HistoricalCorpusEntity) ON (n.logical_id)",
    "CREATE INDEX historical_corpus_relation_key IF NOT EXISTS "
    "FOR ()-[r:HISTORICAL_CORPUS_RELATION]-() ON (r.edge_key)",
)

NODE_UPSERT_CYPHER: Final = """
UNWIND $rows AS row
MERGE (node:HistoricalCorpusEntity {id: row.id})
ON CREATE SET
  node.kind = row.kind,
  node.logical_id = row.logical_id,
  node.properties_json = row.properties_json,
  node.payload_sha256 = row.payload_sha256,
  node.evidence_class = row.evidence_class,
  node.promotion_authority = row.promotion_authority,
  node.policy_feedback_authority = row.policy_feedback_authority
WITH node, row,
  node.kind = row.kind AND
  node.logical_id = row.logical_id AND
  node.properties_json = row.properties_json AND
  node.payload_sha256 = row.payload_sha256 AND
  node.evidence_class = row.evidence_class AND
  node.promotion_authority = false AND
  node.policy_feedback_authority = false AS accepted
RETURN count(row) AS row_count,
       sum(CASE WHEN accepted THEN 1 ELSE 0 END) AS accepted_count
""".strip()

RELATIONSHIP_UPSERT_CYPHER: Final = """
UNWIND $rows AS row
MATCH (source:HistoricalCorpusEntity {id: row.from_id})
MATCH (target:HistoricalCorpusEntity {id: row.to_id})
MERGE (source)-[rel:HISTORICAL_CORPUS_RELATION {edge_key: row.edge_key}]->(target)
ON CREATE SET
  rel.relationship_type = row.relationship_type,
  rel.properties_json = row.properties_json,
  rel.payload_sha256 = row.payload_sha256,
  rel.evidence_class = row.evidence_class,
  rel.promotion_authority = row.promotion_authority,
  rel.policy_feedback_authority = row.policy_feedback_authority
WITH rel, row,
  rel.relationship_type = row.relationship_type AND
  rel.properties_json = row.properties_json AND
  rel.payload_sha256 = row.payload_sha256 AND
  rel.evidence_class = row.evidence_class AND
  rel.promotion_authority = false AND
  rel.policy_feedback_authority = false AS accepted
RETURN count(row) AS row_count,
       sum(CASE WHEN accepted THEN 1 ELSE 0 END) AS accepted_count
""".strip()


__all__ = [
    "EVIDENCE_CLASS",
    "EXPECTED_ATTRIBUTION_OBJECT_COUNT",
    "EXPECTED_CANDIDATE_COUNT",
    "EXPECTED_CANDIDATE_OBJECT_COUNT",
    "EXPECTED_CATALOG_OBJECT_COUNT",
    "EXPECTED_CONVERTED_SLATE_COUNT",
    "EXPECTED_EXACT_OBJECT_COUNT",
    "EXPECTED_HIGH_SCORE_LINEUP_COUNT",
    "EXPECTED_MISSED_HIGH_SCORE_LINEUP_COUNT",
    "EXPECTED_OPPORTUNITY_SLATE_COUNT",
    "EXPECTED_PLAYER_SLATE_COUNT",
    "EXPECTED_SELECTED_HIGH_SCORE_LINEUP_COUNT",
    "EXPECTED_SLATE_COUNT",
    "EXPECTED_VISIT_COUNT",
    "ExactJsonFileV1",
    "ExactJsonObjectV1",
    "HistoricalNeo4jGraphPlanV1",
    "MANIFEST_SCHEMA",
    "NODE_UPSERT_CYPHER",
    "PLAN_SCHEMA",
    "RELATIONSHIP_UPSERT_CYPHER",
    "SCHEMA_STATEMENTS",
    "THRESHOLD_DK",
    "CorpusR6HistoricalNeo4jSliceV1Error",
    "build_historical_corpus_graph_plan_v1",
    "canonical_json_bytes",
    "canonical_sha256",
]
