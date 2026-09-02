"""Bounded aggregate companion for the accepted historical E0 graph slice.

This outcome-bearing contract is deliberately separate from
``corpus-graph-vnext/v2``.  It consumes only caller-supplied exact bytes and
an already rebuilt E0 plan, emits no individual lineup or graph rows, and
grants no scoring, selection, promotion, or policy authority.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Final

from nfl_dfs.research import corpus_r6_historical_neo4j_slice_v1 as historical
from nfl_dfs.research import corpus_r6_no_rescore_funnel_v1 as funnel_contract

SUMMARY_SCHEMA: Final = "corpus-r6-historical-realized-summary/v1"
EVIDENCE_CLASS: Final = "historical-realized-descriptive-development-only"
FIRST_OBSERVED_ABSENCE_CLASS: Final = "FIRST_OBSERVED_ABSENCE_AT_FINAL_BOOK"
ACCEPTED_E0_RECEIPT_FILE_SHA256: Final = (
    "91de6d80c567e620292a6b52e8007b57fc8f7ee63580b9c37f93af0110bbe0b0"
)
ACCEPTED_E0_RECEIPT_SHA256: Final = (
    "b405975d2946b48542695216912f0e3bbc57c118b1666b6d609707b00d7adef8"
)
ACCEPTED_E0_PLAN_SHA256: Final = (
    "e852521d97d3cb37d8e46c6336694f003114b72aa9908277ee7783a1fe1b6821"
)
ACCEPTED_E0_MANIFEST_SHA256: Final = (
    "89da9f017feed892b5aa0ba3e3b39671ad122abd7b0c317bf459c50639f4b7d8"
)
ACCEPTED_FUNNEL_INTERNAL_SHA256: Final = (
    "4bb8dc9ba83a52c46604354f77549d98c21d3e1751bcdbe1695cc1de62196965"
)

_RECEIPT_FIELDS: Final = frozenset(
    {
        "complete",
        "decision_authority",
        "evidence_class",
        "lineup_rescore_performed",
        "manifest_sha256",
        "neo4j_mutation_performed",
        "network_access_performed",
        "node_count",
        "node_kinds",
        "node_rows_sha256",
        "official_claims_included",
        "plan_sha256",
        "policy_feedback_authority",
        "promotion_authority",
        "raw_outcome_query_performed",
        "receipt_sha256",
        "reconciliation",
        "relationship_count",
        "relationship_rows_sha256",
        "relationship_types",
        "schema_version",
        "source_object_count",
        "source_object_manifest_sha256",
        "source_root_identities",
        "source_row_digest_manifest_sha256",
        "threshold_dk",
        "winner_nodes_included",
        "world_matrix_bodies_included",
    }
)
_NODE_FIELDS: Final = frozenset(
    {
        "schema_version",
        "id",
        "kind",
        "logical_id",
        "properties_json",
        "payload_sha256",
        "evidence_class",
        "promotion_authority",
        "policy_feedback_authority",
    }
)
_RELATIONSHIP_FIELDS: Final = frozenset(
    {
        "schema_version",
        "from_id",
        "to_id",
        "relationship_type",
        "edge_key",
        "properties_json",
        "payload_sha256",
        "evidence_class",
        "promotion_authority",
        "policy_feedback_authority",
    }
)


class CorpusR6HistoricalRealizedSummaryV1Error(ValueError):
    """The historical-realized summary failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6HistoricalRealizedSummaryV1Error(message)


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
        raise CorpusR6HistoricalRealizedSummaryV1Error(
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


def _digest(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: set[str] | frozenset[str], *, label: str
) -> None:
    if set(value) != set(expected):
        _fail(f"{label} fields differ")


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

    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=lambda value: _fail(
                f"{label} contains non-finite value {value}"
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6HistoricalRealizedSummaryV1Error(
            f"{label} is not valid UTF-8 JSON"
        ) from exc
    result = _mapping(parsed, label=label)
    if canonical_json_bytes(result) != raw:
        _fail(f"{label} bytes are not canonical JSON")
    return result


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, {"uri", "generation", "sha256", "bytes"}, label=label)
    if (
        type(item["uri"]) is not str
        or not item["uri"]
        or type(item["generation"]) is not str
        or not item["generation"].isdigit()
        or type(item["sha256"]) is not str
        or len(item["sha256"]) != 64
        or any(character not in "0123456789abcdef" for character in item["sha256"])
        or type(item["bytes"]) is not int
        or item["bytes"] <= 0
    ):
        _fail(f"{label} identity differs")
    return item


def _properties(row: Mapping[str, object], *, label: str) -> dict[str, object]:
    raw = row.get("properties_json")
    if type(raw) is not str:
        _fail(f"{label}.properties_json differs")
    properties = _parse_canonical_json(raw.encode("utf-8"), label=f"{label} properties")
    if row.get("payload_sha256") != canonical_sha256(properties):
        _fail(f"{label} property hash differs")
    return properties


@dataclass(frozen=True, slots=True)
class _Binding:
    receipt_file_sha256: str
    receipt_sha256: str
    plan_sha256: str
    manifest_sha256: str
    funnel_internal_sha256: str
    funnel_identity: Mapping[str, object]
    source_object_count: int
    source_object_manifest_sha256: str
    source_row_digest_manifest_sha256: str
    node_rows_sha256: str
    relationship_rows_sha256: str
    threshold_dk: int
    slate_count: int
    strategy_ids: tuple[str, ...]
    arm_ids: tuple[str, ...]
    block_ids: tuple[str, ...]
    expected_reconciliation: Mapping[str, object]


_PRODUCTION_BINDING: Final = _Binding(
    receipt_file_sha256=ACCEPTED_E0_RECEIPT_FILE_SHA256,
    receipt_sha256=ACCEPTED_E0_RECEIPT_SHA256,
    plan_sha256=ACCEPTED_E0_PLAN_SHA256,
    manifest_sha256=ACCEPTED_E0_MANIFEST_SHA256,
    funnel_internal_sha256=ACCEPTED_FUNNEL_INTERNAL_SHA256,
    funnel_identity={
        "uri": (
            "gs://nfl-predictions-503414-corpus-retrieval/research/"
            "corpus-r6-no-rescore-funnels/20260827-r6-no-rescore-funnel-v1/"
            "no-rescore-funnel-release.json"
        ),
        "generation": "1787859076719874",
        "sha256": "782a1d88c27b3160e3f91f8c8efcf07d92ab7d5f5ef60c90bca4712449bdfcbb",
        "bytes": 2_448_874,
    },
    source_object_count=219,
    source_object_manifest_sha256=(
        "7a96c70f23efb3d69a32a6b709929410469f03afae52654bdc11adc6d22812e4"
    ),
    source_row_digest_manifest_sha256=(
        "fe10310f512ce80f71403a6cb80cde9d25bdaa43cdfec38151e5b355669d91a0"
    ),
    node_rows_sha256=(
        "4ba40f3673867957ca22b9db96e278b1d4721ac6e9a66a1a969ea4509bfe23bc"
    ),
    relationship_rows_sha256=(
        "f2e6271fc9753847e8687346d6fa12be33fff1a2b31919b976d86927d43af302"
    ),
    threshold_dk=historical.THRESHOLD_DK,
    slate_count=historical.EXPECTED_SLATE_COUNT,
    strategy_ids=tuple(funnel_contract.STRATEGY_IDS),
    arm_ids=tuple(historical.ARM_IDS),
    block_ids=tuple(historical.BLOCK_IDS),
    expected_reconciliation={
        "source_slate_count": 54,
        "candidate_count": 199_244,
        "visit_occurrence_count": 378_000,
        "player_slate_count": 29_605,
        "scope_membership_count": 1_195_464,
        "book_count": 2_592,
        "selection_count": 207_360,
        "final_fit_book_count": 432,
        "final_fit_selection_count": 34_560,
        "high_score_lineup_count": 279,
        "selected_high_score_lineup_count": 38,
        "missed_high_score_lineup_count": 241,
        "opportunity_slate_count": 29,
        "converted_slate_count": 10,
        "candidate_attribution_roster_equality": True,
        "exact_nine_player_catalog_join": True,
        "candidate_lineage_recurrence_reconciled": True,
        "full_population_denominators_retained": True,
    },
)


def _bind_sources(
    *,
    accepted_e0_receipt_raw: bytes,
    no_rescore_funnel_raw: bytes,
    e0_plan: historical.HistoricalNeo4jGraphPlanV1,
    binding: _Binding,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    if (
        type(accepted_e0_receipt_raw) is not bytes
        or sha256(accepted_e0_receipt_raw).hexdigest() != binding.receipt_file_sha256
        or not accepted_e0_receipt_raw.endswith(b"\n")
        or accepted_e0_receipt_raw.endswith(b"\n\n")
    ):
        _fail("accepted E0 receipt file identity differs")
    receipt = _parse_canonical_json(
        accepted_e0_receipt_raw[:-1], label="accepted E0 receipt"
    )
    _exact_keys(receipt, _RECEIPT_FIELDS, label="accepted E0 receipt")
    receipt_body = {
        key: value for key, value in receipt.items() if key != "receipt_sha256"
    }
    if (
        receipt.get("receipt_sha256") != canonical_sha256(receipt_body)
        or receipt.get("receipt_sha256") != binding.receipt_sha256
        or receipt.get("schema_version")
        != "corpus-r6-historical-neo4j-slice-local-receipt/v1"
        or receipt.get("threshold_dk") != binding.threshold_dk
        or receipt.get("plan_sha256") != binding.plan_sha256
        or receipt.get("manifest_sha256") != binding.manifest_sha256
        or receipt.get("reconciliation") != binding.expected_reconciliation
        or receipt.get("complete") is not True
        or any(
            receipt.get(field) is not False
            for field in (
                "raw_outcome_query_performed",
                "lineup_rescore_performed",
                "winner_nodes_included",
                "official_claims_included",
                "neo4j_mutation_performed",
                "network_access_performed",
                "promotion_authority",
                "decision_authority",
                "policy_feedback_authority",
            )
        )
    ):
        _fail("accepted E0 receipt contract differs")
    roots = _mapping(receipt.get("source_root_identities"), label="source roots")
    _exact_keys(
        roots,
        {"candidate_v2", "catalog_outer", "no_rescore_funnel"},
        label="source roots",
    )
    roots = {
        role: _identity(value, label=f"{role} identity")
        for role, value in roots.items()
    }
    funnel_identity = roots["no_rescore_funnel"]
    if (
        funnel_identity != binding.funnel_identity
        or receipt.get("source_object_count") != binding.source_object_count
        or receipt.get("source_object_manifest_sha256")
        != binding.source_object_manifest_sha256
        or receipt.get("source_row_digest_manifest_sha256")
        != binding.source_row_digest_manifest_sha256
        or receipt.get("node_rows_sha256") != binding.node_rows_sha256
        or receipt.get("relationship_rows_sha256") != binding.relationship_rows_sha256
        or type(no_rescore_funnel_raw) is not bytes
        or len(no_rescore_funnel_raw) != funnel_identity["bytes"]
        or sha256(no_rescore_funnel_raw).hexdigest() != funnel_identity["sha256"]
    ):
        _fail("no-rescore funnel bytes differ from accepted identity")
    funnel = _parse_canonical_json(no_rescore_funnel_raw, label="no-rescore funnel")
    try:
        funnel = funnel_contract.validate_no_rescore_funnel_release_v1(funnel)
    except Exception as exc:
        raise CorpusR6HistoricalRealizedSummaryV1Error(
            "no-rescore funnel contract validation failed"
        ) from exc
    if funnel.get("funnel_release_sha256") != binding.funnel_internal_sha256:
        _fail("no-rescore funnel internal identity differs")

    if not isinstance(e0_plan, historical.HistoricalNeo4jGraphPlanV1):
        _fail("E0 plan type differs")
    manifest = _mapping(e0_plan.manifest, label="E0 manifest")
    retained_manifest_hash = manifest.get("manifest_sha256")
    manifest_body = {
        key: value for key, value in manifest.items() if key != "manifest_sha256"
    }
    plan_body = {
        "schema_version": e0_plan.schema_version,
        "manifest": manifest,
        "nodes": list(e0_plan.nodes),
        "relationships": list(e0_plan.relationships),
    }
    source_manifest = _sequence(
        manifest.get("source_object_manifest"), label="E0 source object manifest"
    )
    row_digest_manifest = _mapping(
        manifest.get("source_row_digest_manifest"),
        label="E0 source row digest manifest",
    )
    if (
        e0_plan.schema_version != historical.PLAN_SCHEMA
        or retained_manifest_hash != canonical_sha256(manifest_body)
        or retained_manifest_hash != binding.manifest_sha256
        or e0_plan.plan_sha256 != canonical_sha256(plan_body)
        or e0_plan.plan_sha256 != binding.plan_sha256
        or manifest.get("source_root_identities") != roots
        or manifest.get("reconciliation") != binding.expected_reconciliation
        or manifest.get("source_object_count") != len(source_manifest)
        or manifest.get("source_object_manifest_sha256")
        != canonical_sha256(source_manifest)
        or manifest.get("source_row_digest_manifest_sha256")
        != canonical_sha256(row_digest_manifest)
        or manifest.get("node_count") != len(e0_plan.nodes)
        or manifest.get("node_rows_sha256") != canonical_sha256(list(e0_plan.nodes))
        or manifest.get("relationship_count") != len(e0_plan.relationships)
        or manifest.get("relationship_rows_sha256")
        != canonical_sha256(list(e0_plan.relationships))
        or receipt.get("node_count") != len(e0_plan.nodes)
        or receipt.get("node_rows_sha256") != manifest.get("node_rows_sha256")
        or receipt.get("relationship_count") != len(e0_plan.relationships)
        or receipt.get("relationship_rows_sha256")
        != manifest.get("relationship_rows_sha256")
        or receipt.get("source_object_count") != manifest.get("source_object_count")
        or receipt.get("source_object_manifest_sha256")
        != manifest.get("source_object_manifest_sha256")
        or receipt.get("source_row_digest_manifest_sha256")
        != manifest.get("source_row_digest_manifest_sha256")
        or manifest.get("persisted_realized_labels_only") is not True
        or manifest.get("complete") is not True
        or any(
            manifest.get(field) is not False
            for field in (
                "raw_outcome_query_performed",
                "lineup_rescore_performed",
                "winner_nodes_included",
                "official_claims_included",
                "neo4j_mutation_performed",
                "promotion_authority",
                "decision_authority",
                "policy_feedback_authority",
            )
        )
    ):
        _fail("accepted E0 receipt/plan binding differs")
    node_kinds = Counter(str(row.get("kind")) for row in e0_plan.nodes)
    relationship_types = Counter(
        str(row.get("relationship_type")) for row in e0_plan.relationships
    )
    if receipt.get("node_kinds") != dict(sorted(node_kinds.items())) or receipt.get(
        "relationship_types"
    ) != dict(sorted(relationship_types.items())):
        _fail("accepted E0 receipt row census differs")
    return receipt, funnel, roots


def _validated_rows(
    plan: historical.HistoricalNeo4jGraphPlanV1,
) -> tuple[
    dict[str, tuple[dict[str, object], dict[str, object]]],
    list[tuple[dict[str, object], dict[str, object]]],
]:
    nodes: dict[str, tuple[dict[str, object], dict[str, object]]] = {}
    for ordinal, raw_row in enumerate(plan.nodes):
        row = _mapping(raw_row, label=f"E0 node[{ordinal}]")
        _exact_keys(row, _NODE_FIELDS, label=f"E0 node[{ordinal}]")
        node_id = row.get("id")
        if (
            row.get("schema_version") != historical.NODE_SCHEMA
            or type(node_id) is not str
            or not node_id
            or type(row.get("kind")) is not str
            or type(row.get("logical_id")) is not str
            or row.get("evidence_class") != historical.EVIDENCE_CLASS
            or row.get("promotion_authority") is not False
            or row.get("policy_feedback_authority") is not False
            or node_id in nodes
        ):
            _fail(f"E0 node[{ordinal}] envelope differs")
        nodes[node_id] = (row, _properties(row, label=f"E0 node[{ordinal}]"))

    relationships: list[tuple[dict[str, object], dict[str, object]]] = []
    seen_edges: set[str] = set()
    for ordinal, raw_row in enumerate(plan.relationships):
        row = _mapping(raw_row, label=f"E0 relationship[{ordinal}]")
        _exact_keys(row, _RELATIONSHIP_FIELDS, label=f"E0 relationship[{ordinal}]")
        coordinate = {
            "from_id": row.get("from_id"),
            "to_id": row.get("to_id"),
            "relationship_type": row.get("relationship_type"),
        }
        edge_key = row.get("edge_key")
        if (
            row.get("schema_version") != historical.RELATIONSHIP_SCHEMA
            or any(type(value) is not str or not value for value in coordinate.values())
            or coordinate["from_id"] not in nodes
            or coordinate["to_id"] not in nodes
            or edge_key != canonical_sha256(coordinate)
            or edge_key in seen_edges
            or row.get("evidence_class") != historical.EVIDENCE_CLASS
            or row.get("promotion_authority") is not False
            or row.get("policy_feedback_authority") is not False
        ):
            _fail(f"E0 relationship[{ordinal}] envelope differs")
        seen_edges.add(str(edge_key))
        relationships.append(
            (row, _properties(row, label=f"E0 relationship[{ordinal}]"))
        )
    return nodes, relationships


def _threshold_row(
    value: object, *, label: str, threshold_dk: int
) -> dict[str, object]:
    rows = [
        _mapping(row, label=f"{label} row") for row in _sequence(value, label=label)
    ]
    matches = [row for row in rows if row.get("threshold_dk") == threshold_dk]
    if len(matches) != 1:
        _fail(f"{label} has no unique threshold {threshold_dk} row")
    return matches[0]


def _ratio(numerator: int, denominator: int) -> dict[str, int]:
    if denominator <= 0:
        _fail("ratio denominator must be positive")
    return {"numerator": numerator, "denominator": denominator}


def _aggregate_bound_plan(
    *,
    plan: historical.HistoricalNeo4jGraphPlanV1,
    funnel: Mapping[str, object],
    receipt: Mapping[str, object],
    roots: Mapping[str, object],
    binding: _Binding,
) -> dict[str, object]:
    nodes, relationships = _validated_rows(plan)
    node_rows_by_kind: dict[str, list[tuple[str, dict[str, object]]]] = defaultdict(
        list
    )
    for node_id, (row, properties) in nodes.items():
        node_rows_by_kind[str(row["kind"])].append((node_id, properties))

    slate_rows = node_rows_by_kind["Slate"]
    lineup_rows = node_rows_by_kind["LineupCandidate"]
    book_rows = node_rows_by_kind["FinalFitBook"]
    denominator_rows = node_rows_by_kind["GenerationDenominator"]
    if (
        len(slate_rows) != binding.slate_count
        or len(book_rows) != binding.slate_count * len(binding.strategy_ids)
        or len(lineup_rows)
        != binding.expected_reconciliation["high_score_lineup_count"]
    ):
        _fail("E0 aggregate source row census differs")

    slates: dict[int, tuple[str, dict[str, object]]] = {}
    high_lineups: dict[str, dict[str, object]] = {}
    for node_id, properties in slate_rows:
        ordinal = _integer(properties.get("source_ordinal"), label="slate ordinal")
        if ordinal in slates:
            _fail("E0 slate ordinal repeats")
        slates[ordinal] = (node_id, properties)
    if set(slates) != set(range(binding.slate_count)):
        _fail("E0 slate ordinals differ")
    for node_id, properties in lineup_rows:
        ordinal = _integer(
            properties.get("source_ordinal"), label="lineup slate ordinal"
        )
        score = _integer(properties.get("realized_score_micro"), label="lineup score")
        selected_count = _integer(
            properties.get("selected_final_book_count"),
            label="lineup selected-book count",
        )
        if (
            ordinal not in slates
            or score < binding.threshold_dk * historical.MICRO_DK_PER_POINT
            or selected_count > len(binding.strategy_ids)
        ):
            _fail("E0 high-lineup properties differ")
        high_lineups[node_id] = properties

    books: dict[tuple[int, int], tuple[str, dict[str, object]]] = {}
    for node_id, properties in book_rows:
        ordinal = _integer(properties.get("source_ordinal"), label="book slate ordinal")
        strategy_ordinal = _integer(
            properties.get("strategy_ordinal"), label="book strategy ordinal"
        )
        if (
            ordinal not in slates
            or strategy_ordinal >= len(binding.strategy_ids)
            or properties.get("strategy_id") != binding.strategy_ids[strategy_ordinal]
            or (ordinal, strategy_ordinal) in books
        ):
            _fail("E0 final-fit strategy coordinate differs")
        eligible = _integer(
            properties.get("eligible_maximum_score_micro"), label="eligible maximum"
        )
        selected = _integer(
            properties.get("selected_maximum_score_micro"), label="selected maximum"
        )
        regret = _integer(
            properties.get("selector_regret_micro"), label="selector regret"
        )
        if regret != eligible - selected:
            _fail("E0 final-fit selector regret differs")
        books[(ordinal, strategy_ordinal)] = (node_id, properties)
    if set(books) != {
        (ordinal, strategy_ordinal)
        for ordinal in range(binding.slate_count)
        for strategy_ordinal in range(len(binding.strategy_ids))
    }:
        _fail("E0 final-fit book grid differs")

    selected_by_lineup: Counter[str] = Counter()
    selected_by_strategy: Counter[int] = Counter()
    selected_by_slate: Counter[int] = Counter()
    classified_by_lineup: Counter[str] = Counter()
    selected_edge_count = 0
    absent_edge_count = 0
    denominator_edges: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
    book_coordinates = {
        node_id: coordinate for coordinate, (node_id, _) in books.items()
    }
    denominator_by_id = {
        node_id: properties for node_id, properties in denominator_rows
    }
    classified_pairs: set[tuple[str, str]] = set()
    for row, properties in relationships:
        relationship = row["relationship_type"]
        if relationship in {"SELECTED_HIGH_SCORER", "MISSED_HIGH_SCORER"}:
            book_coordinate = book_coordinates.get(str(row["from_id"]))
            lineup = high_lineups.get(str(row["to_id"]))
            if book_coordinate is None or lineup is None:
                _fail("E0 high-score classification endpoints differ")
            if int(lineup["source_ordinal"]) != book_coordinate[0]:
                _fail("E0 high-score classification crosses slates")
            classification_pair = (str(row["from_id"]), str(row["to_id"]))
            if classification_pair in classified_pairs:
                _fail("E0 high-score book/lineup classification repeats")
            classified_pairs.add(classification_pair)
            classified_by_lineup[str(row["to_id"])] += 1
            if relationship == "SELECTED_HIGH_SCORER":
                _exact_keys(
                    properties,
                    {"selection_rank", "realized_score_micro"},
                    label="selected high-score edge properties",
                )
                if properties["realized_score_micro"] != lineup["realized_score_micro"]:
                    _fail("E0 selected-edge score differs")
                _integer(
                    properties["selection_rank"],
                    label="selected high-score edge rank",
                )
                selected_edge_count += 1
                selected_by_lineup[str(row["to_id"])] += 1
                selected_by_strategy[book_coordinate[1]] += 1
                selected_by_slate[book_coordinate[0]] += 1
            else:
                _exact_keys(properties, {"reason"}, label="absent edge properties")
                if properties["reason"] != "not-selected-by-final-fit-book":
                    _fail("E0 absent-edge reason differs")
                absent_edge_count += 1
        elif relationship == "GENERATED_IN_CELL":
            if str(row["from_id"]) not in high_lineups:
                _fail("E0 generated-cell edge source differs")
            denominator = denominator_by_id.get(str(row["to_id"]))
            if denominator is None or denominator.get("dimension_kind") != "arm-block":
                _fail("E0 generated-cell edge target differs")
            lineup = high_lineups[str(row["from_id"])]
            if denominator.get("source_ordinal") != lineup.get("source_ordinal"):
                _fail("E0 generated-cell edge crosses slates")
            _exact_keys(
                properties,
                {"visit_occurrence_count"},
                label="generated-cell edge properties",
            )
            visit_count = _integer(
                properties["visit_occurrence_count"],
                label="generated-cell edge visit count",
                minimum=1,
            )
            edge_count, edge_visits = denominator_edges[str(row["to_id"])]
            denominator_edges[str(row["to_id"])] = (
                edge_count + 1,
                edge_visits + visit_count,
            )
    if (
        any(
            count != len(binding.strategy_ids)
            for count in classified_by_lineup.values()
        )
        or set(classified_by_lineup) != set(high_lineups)
        or any(
            selected_by_lineup[node_id] != properties["selected_final_book_count"]
            for node_id, properties in high_lineups.items()
        )
        or selected_edge_count + absent_edge_count
        != len(high_lineups) * len(binding.strategy_ids)
    ):
        _fail("E0 high-score classification partition differs")

    funnel_slate_rows = [
        _mapping(row, label="funnel slate row")
        for row in _sequence(funnel.get("slate_rows"), label="funnel slate rows")
    ]
    if len(funnel_slate_rows) != binding.slate_count:
        _fail("funnel slate-row census differs")
    funnel_by_ordinal: dict[int, dict[str, object]] = {}
    opportunity_count = 0
    converted_count = 0
    for raw_slate in funnel_slate_rows:
        ordinal = _integer(
            raw_slate.get("source_ordinal"), label="funnel slate ordinal"
        )
        if ordinal in funnel_by_ordinal or ordinal not in slates:
            _fail("funnel slate coordinate differs")
        funnel_by_ordinal[ordinal] = raw_slate
        corpus = _mapping(raw_slate.get("corpus"), label="funnel corpus row")
        corpus_threshold = _threshold_row(
            corpus.get("thresholds"),
            label="funnel corpus thresholds",
            threshold_dk=binding.threshold_dk,
        )
        slate_high_count = _integer(
            slates[ordinal][1].get("high_score_lineup_count"),
            label="E0 slate high-score count",
        )
        if corpus_threshold.get(
            "population_lineup_count"
        ) != slate_high_count or corpus_threshold.get("population_available") is not (
            slate_high_count > 0
        ):
            _fail("funnel/E0 slate opportunity differs")
        opportunity_count += slate_high_count > 0
        union = _mapping(raw_slate.get("diagnostic_union"), label="diagnostic union")
        union_threshold = _threshold_row(
            union.get("thresholds"),
            label="diagnostic union thresholds",
            threshold_dk=binding.threshold_dk,
        )
        unique_selected = sum(
            selected_by_lineup[node_id] > 0
            for node_id, properties in high_lineups.items()
            if properties["source_ordinal"] == ordinal
        )
        if union_threshold.get(
            "selected_lineup_count"
        ) != unique_selected or union_threshold.get("selected_hit") is not (
            unique_selected > 0
        ):
            _fail("funnel/E0 slate conversion differs")
        converted_count += unique_selected > 0

        raw_books = [
            _mapping(row, label="funnel exact-80 book")
            for row in _sequence(
                raw_slate.get("exact_80_books"), label="exact-80 books"
            )
        ]
        if len(raw_books) != len(binding.strategy_ids):
            _fail("funnel exact-80 book census differs")
        for strategy_ordinal, raw_book in enumerate(raw_books):
            plan_book = books[(ordinal, strategy_ordinal)][1]
            selected = _integer(
                plan_book["selected_maximum_score_micro"], label="selected maximum"
            )
            eligible = _integer(
                plan_book["eligible_maximum_score_micro"], label="eligible maximum"
            )
            plan_threshold = _threshold_row(
                plan_book.get("threshold_capture"),
                label="plan book thresholds",
                threshold_dk=binding.threshold_dk,
            )
            raw_threshold = _threshold_row(
                raw_book.get("thresholds"),
                label="funnel book thresholds",
                threshold_dk=binding.threshold_dk,
            )
            if (
                raw_book.get("strategy_ordinal") != strategy_ordinal
                or raw_book.get("strategy_id") != binding.strategy_ids[strategy_ordinal]
                or raw_book.get("selected_maximum_score_micro") != selected
                or raw_book.get("selector_regret_micro") != eligible - selected
                or corpus.get("corpus_maximum_score_micro") != eligible
                or raw_threshold.get("selected_lineup_count")
                != plan_threshold.get("selected_lineup_count")
                or raw_threshold.get("selected_hit")
                is not plan_threshold.get("selected_hit")
                or raw_threshold.get("population_lineup_count")
                != plan_threshold.get("eligible_lineup_count")
            ):
                _fail("funnel/E0 exact-80 book differs")
        eligible_values = {
            books[(ordinal, strategy_ordinal)][1]["eligible_maximum_score_micro"]
            for strategy_ordinal in range(len(binding.strategy_ids))
        }
        if len(eligible_values) != 1:
            _fail("E0 eligible maximum differs across final-fit strategies")

    population_threshold = _threshold_row(
        _mapping(funnel.get("population_result"), label="population result").get(
            "thresholds"
        ),
        label="population thresholds",
        threshold_dk=binding.threshold_dk,
    )
    union_threshold = _threshold_row(
        _mapping(funnel.get("diagnostic_union_result"), label="union result").get(
            "thresholds"
        ),
        label="union thresholds",
        threshold_dk=binding.threshold_dk,
    )
    captured_count = sum(count > 0 for count in selected_by_lineup.values())
    absent_count = len(high_lineups) - captured_count
    if (
        population_threshold.get("population_lineup_count") != len(high_lineups)
        or population_threshold.get("population_opportunity_slates")
        != opportunity_count
        or union_threshold.get("selected_qualifying_lineup_count") != captured_count
        or union_threshold.get("observed_hit_slates") != converted_count
        or opportunity_count
        != binding.expected_reconciliation["opportunity_slate_count"]
        or converted_count != binding.expected_reconciliation["converted_slate_count"]
        or captured_count
        != binding.expected_reconciliation["selected_high_score_lineup_count"]
        or absent_count
        != binding.expected_reconciliation["missed_high_score_lineup_count"]
    ):
        _fail("funnel/E0 outcome-funnel aggregate differs")

    raw_strategy_results = [
        _mapping(row, label="funnel strategy result")
        for row in _sequence(
            funnel.get("exact_80_strategy_results"), label="funnel strategy results"
        )
    ]
    if len(raw_strategy_results) != len(binding.strategy_ids):
        _fail("funnel strategy-result census differs")
    strategy_summaries: list[dict[str, object]] = []
    for strategy_ordinal, strategy_id in enumerate(binding.strategy_ids):
        raw_result = raw_strategy_results[strategy_ordinal]
        strategy_books = [books[(ordinal, strategy_ordinal)][1] for ordinal in slates]
        eligible_sum = sum(
            int(row["eligible_maximum_score_micro"]) for row in strategy_books
        )
        selected_sum = sum(
            int(row["selected_maximum_score_micro"]) for row in strategy_books
        )
        rescue_sum = sum(int(row["selector_regret_micro"]) for row in strategy_books)
        positive_rescue = sum(
            int(row["selector_regret_micro"]) > 0 for row in strategy_books
        )
        eligible_high_selected_under = 0
        selected_high_slates = 0
        for row in strategy_books:
            threshold = _threshold_row(
                row["threshold_capture"],
                label="strategy book thresholds",
                threshold_dk=binding.threshold_dk,
            )
            eligible_hit = threshold.get("eligible_hit")
            selected_hit = threshold.get("selected_hit")
            if type(eligible_hit) is not bool or type(selected_hit) is not bool:
                _fail("strategy book threshold hit flags differ")
            eligible_high_selected_under += eligible_hit and not selected_hit
            selected_high_slates += selected_hit
        raw_threshold = _threshold_row(
            raw_result.get("thresholds"),
            label="strategy-result thresholds",
            threshold_dk=binding.threshold_dk,
        )
        if (
            raw_result.get("strategy_ordinal") != strategy_ordinal
            or raw_result.get("strategy_id") != strategy_id
            or raw_result.get("source_slate_count") != binding.slate_count
            or raw_result.get("entry_count_k") != 80
            or raw_threshold.get("observed_hit_slates") != selected_high_slates
            or raw_threshold.get("population_opportunity_slates") != opportunity_count
            or raw_threshold.get("selected_qualifying_lineup_count")
            != selected_by_strategy[strategy_ordinal]
            or eligible_sum - selected_sum != rescue_sum
        ):
            _fail("funnel/E0 strategy aggregate differs")
        strategy_sha256 = _digest(
            raw_result.get("strategy_sha256"), label="strategy SHA-256"
        )
        strategy_summaries.append(
            {
                "strategy_id": strategy_id,
                "strategy_sha256": strategy_sha256,
                "cohort": "one-final-fit-book-per-source-slate",
                "threshold_operator": "greater-than-or-equal",
                "score_unit": "micro_dk",
                "mean_denominator_slate_count": binding.slate_count,
                "source_slate_count": binding.slate_count,
                "entry_count_k": 80,
                "eligible_maximum_score_sum_micro": eligible_sum,
                "eligible_maximum_score_mean_micro": _ratio(
                    eligible_sum, binding.slate_count
                ),
                "selected_maximum_score_sum_micro": selected_sum,
                "selected_maximum_score_mean_micro": _ratio(
                    selected_sum, binding.slate_count
                ),
                "sum_individual_rescue_deltas_micro": rescue_sum,
                "mean_individual_rescue_delta_micro": _ratio(
                    rescue_sum, binding.slate_count
                ),
                "positive_rescue_slate_count": positive_rescue,
                "eligible_high_selected_below_threshold_slate_count": (
                    eligible_high_selected_under
                ),
                "selected_high_slate_count": selected_high_slates,
                "selected_high_score_lineup_slot_count": selected_by_strategy[
                    strategy_ordinal
                ],
                "rescue_sum_is_jointly_achievable": False,
            }
        )

    denominator_groups: dict[tuple[str, str, str], dict[str, int]] = {}
    denominator_coordinates_seen: set[tuple[int, str, str, str]] = set()
    for node_id, properties in denominator_rows:
        source_ordinal = _integer(
            properties.get("source_ordinal"), label="denominator slate ordinal"
        )
        kind = properties.get("dimension_kind")
        value = properties.get("dimension_value")
        block = properties.get("block_id")
        if (
            kind not in {"arm", "block", "arm-block"}
            or type(value) is not str
            or not value
            or (block is not None and (type(block) is not str or not block))
        ):
            _fail("E0 generation denominator coordinate differs")
        if kind == "arm" and (value not in binding.arm_ids or block is not None):
            _fail("E0 arm denominator coordinate differs")
        if kind == "block" and (value not in binding.block_ids or block is not None):
            _fail("E0 block denominator coordinate differs")
        if kind == "arm-block" and (
            value not in binding.arm_ids or block not in binding.block_ids
        ):
            _fail("E0 arm-block denominator coordinate differs")
        source_coordinate = (
            source_ordinal,
            str(kind),
            str(value),
            str(block or ""),
        )
        if (
            source_ordinal not in slates
            or source_coordinate in denominator_coordinates_seen
        ):
            _fail("E0 generation denominator slate coordinate differs")
        denominator_coordinates_seen.add(source_coordinate)
        if kind == "arm-block":
            edge_count, edge_visits = denominator_edges.get(node_id, (0, 0))
            if edge_count != properties.get(
                "high_score_candidate_count"
            ) or edge_visits != properties.get("high_score_visit_count"):
                _fail("E0 arm-block high-score edge reconciliation differs")
        coordinate = (str(kind), str(value), str(block or ""))
        aggregate = denominator_groups.setdefault(
            coordinate,
            {
                "source_slate_count": 0,
                "full_population_candidate_count": 0,
                "candidate_membership_count": 0,
                "visit_count": 0,
                "high_score_candidate_membership_count": 0,
                "high_score_visit_count": 0,
            },
        )
        aggregate["source_slate_count"] += 1
        aggregate["full_population_candidate_count"] += _integer(
            properties.get("full_population_candidate_count"),
            label="denominator full population",
        )
        for source, target in (
            ("candidate_count", "candidate_membership_count"),
            ("visit_count", "visit_count"),
            ("high_score_candidate_count", "high_score_candidate_membership_count"),
            ("high_score_visit_count", "high_score_visit_count"),
        ):
            aggregate[target] += _integer(
                properties.get(source), label=f"denominator {source}"
            )

    expected_coordinates = (
        {("arm", arm, "") for arm in binding.arm_ids}
        | {("block", block, "") for block in binding.block_ids}
        | {
            ("arm-block", arm, block)
            for arm in binding.arm_ids
            for block in binding.block_ids
        }
    )
    if set(denominator_groups) != expected_coordinates:
        _fail("E0 generation denominator grid differs")
    expected_source_coordinates = {
        (source_ordinal, *coordinate)
        for source_ordinal in range(binding.slate_count)
        for coordinate in expected_coordinates
    }
    if denominator_coordinates_seen != expected_source_coordinates:
        _fail("E0 generation denominator per-slate grid differs")

    def generation_row(
        coordinate: tuple[str, str, str],
        aggregate: Mapping[str, int],
    ) -> dict[str, object]:
        if (
            aggregate["source_slate_count"] != binding.slate_count
            or aggregate["full_population_candidate_count"]
            != binding.expected_reconciliation["candidate_count"]
        ):
            _fail("E0 generation denominator panel census differs")
        row: dict[str, object] = dict(aggregate)
        row["high_score_visit_rate"] = _ratio(
            aggregate["high_score_visit_count"], aggregate["visit_count"]
        )
        if coordinate[0] == "arm":
            row["fill_arm_id"] = coordinate[1]
        elif coordinate[0] == "block":
            row["world_block_id"] = coordinate[1]
        else:
            row["fill_arm_id"] = coordinate[1]
            row["world_block_id"] = coordinate[2]
        return row

    by_arm = [
        generation_row(("arm", arm, ""), denominator_groups[("arm", arm, "")])
        for arm in binding.arm_ids
    ]
    by_block = [
        generation_row(("block", block, ""), denominator_groups[("block", block, "")])
        for block in binding.block_ids
    ]
    by_cell = [
        generation_row(
            ("arm-block", arm, block), denominator_groups[("arm-block", arm, block)]
        )
        for arm in binding.arm_ids
        for block in binding.block_ids
    ]
    total_visits = _integer(
        binding.expected_reconciliation["visit_occurrence_count"],
        label="expected visit count",
    )
    if any(
        sum(int(row["visit_count"]) for row in rows) != total_visits
        for rows in (by_arm, by_block, by_cell)
    ):
        _fail("E0 generation visit partitions differ")
    high_visit_totals = {
        sum(int(row["high_score_visit_count"]) for row in rows)
        for rows in (by_arm, by_block, by_cell)
    }
    if len(high_visit_totals) != 1:
        _fail("E0 high-score generation visit partitions differ")

    body: dict[str, object] = {
        "schema_version": SUMMARY_SCHEMA,
        "evidence_class": EVIDENCE_CLASS,
        "threshold_dk": binding.threshold_dk,
        "threshold_micro": binding.threshold_dk * historical.MICRO_DK_PER_POINT,
        "source_binding": {
            "accepted_e0_receipt_file_sha256": binding.receipt_file_sha256,
            "accepted_e0_receipt_sha256": binding.receipt_sha256,
            "e0_plan_sha256": binding.plan_sha256,
            "e0_manifest_sha256": binding.manifest_sha256,
            "no_rescore_funnel_identity": roots["no_rescore_funnel"],
            "no_rescore_funnel_internal_sha256": binding.funnel_internal_sha256,
            "source_object_count": receipt["source_object_count"],
            "source_object_manifest_sha256": receipt["source_object_manifest_sha256"],
            "source_row_digest_manifest_sha256": receipt[
                "source_row_digest_manifest_sha256"
            ],
            "node_rows_sha256": receipt["node_rows_sha256"],
            "relationship_rows_sha256": receipt["relationship_rows_sha256"],
        },
        "outcome_funnel_summary": {
            "cohort": "persisted-eligible-lineups-at-or-above-threshold",
            "threshold_operator": "greater-than-or-equal",
            "score_unit": "micro_dk",
            "source_slate_count": binding.slate_count,
            "final_fit_strategy_count": len(binding.strategy_ids),
            "eligible_high_score_lineup_count": len(high_lineups),
            "observed_in_any_final_fit_book_count": captured_count,
            "first_observed_absence_count": absent_count,
            "opportunity_slate_count": opportunity_count,
            "converted_slate_count": converted_count,
            "unconverted_opportunity_slate_count": opportunity_count - converted_count,
            "selected_high_scorer_book_edge_count": selected_edge_count,
            "absent_high_scorer_book_edge_count": absent_edge_count,
            "book_classification_edge_count": selected_edge_count + absent_edge_count,
            "first_observed_absence_class": FIRST_OBSERVED_ABSENCE_CLASS,
            "absence_derivation": "synthesized-set-difference-across-observed-final-fit-books",
            "source_emitted_selector_rejection": False,
            "causal_first_loss_claim": False,
        },
        "strategy_rescue_summary": strategy_summaries,
        "generation_yield_summary": {
            "cohort": "full-fixed-g0-candidate-population",
            "threshold_operator": "greater-than-or-equal",
            "score_unit": "micro_dk",
            "rate_denominator_unit": "generation_visit",
            "total_candidate_count": binding.expected_reconciliation["candidate_count"],
            "total_visit_count": total_visits,
            "total_high_score_visit_count": next(iter(high_visit_totals)),
            "candidate_membership_semantics": "overlapping-within-dimension-not-additive-across-rows",
            "visit_semantics": "partitioned-generation-occurrences",
            "by_fill_arm": by_arm,
            "by_world_block": by_block,
            "by_fill_arm_world_block": by_cell,
        },
        "uses_realized_outcomes": True,
        "persisted_realized_labels_only": True,
        "separate_from_corpus_graph_vnext_v2": True,
        "raw_outcome_query_performed": False,
        "lineup_rescore_performed": False,
        "individual_rows_included": False,
        "neo4j_mutation_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
        "policy_feedback_authority": False,
        "complete": True,
    }
    body["summary_sha256"] = canonical_sha256(body)
    return body


_ROOT_FIELDS: Final = frozenset(
    {
        "schema_version",
        "evidence_class",
        "threshold_dk",
        "threshold_micro",
        "source_binding",
        "outcome_funnel_summary",
        "strategy_rescue_summary",
        "generation_yield_summary",
        "uses_realized_outcomes",
        "persisted_realized_labels_only",
        "separate_from_corpus_graph_vnext_v2",
        "raw_outcome_query_performed",
        "lineup_rescore_performed",
        "individual_rows_included",
        "neo4j_mutation_performed",
        "promotion_authority",
        "decision_authority",
        "policy_feedback_authority",
        "complete",
        "summary_sha256",
    }
)
_SOURCE_BINDING_FIELDS: Final = frozenset(
    {
        "accepted_e0_receipt_file_sha256",
        "accepted_e0_receipt_sha256",
        "e0_plan_sha256",
        "e0_manifest_sha256",
        "no_rescore_funnel_identity",
        "no_rescore_funnel_internal_sha256",
        "source_object_count",
        "source_object_manifest_sha256",
        "source_row_digest_manifest_sha256",
        "node_rows_sha256",
        "relationship_rows_sha256",
    }
)
_OUTCOME_FIELDS: Final = frozenset(
    {
        "cohort",
        "threshold_operator",
        "score_unit",
        "source_slate_count",
        "final_fit_strategy_count",
        "eligible_high_score_lineup_count",
        "observed_in_any_final_fit_book_count",
        "first_observed_absence_count",
        "opportunity_slate_count",
        "converted_slate_count",
        "unconverted_opportunity_slate_count",
        "selected_high_scorer_book_edge_count",
        "absent_high_scorer_book_edge_count",
        "book_classification_edge_count",
        "first_observed_absence_class",
        "absence_derivation",
        "source_emitted_selector_rejection",
        "causal_first_loss_claim",
    }
)
_STRATEGY_FIELDS: Final = frozenset(
    {
        "strategy_id",
        "strategy_sha256",
        "cohort",
        "threshold_operator",
        "score_unit",
        "mean_denominator_slate_count",
        "source_slate_count",
        "entry_count_k",
        "eligible_maximum_score_sum_micro",
        "eligible_maximum_score_mean_micro",
        "selected_maximum_score_sum_micro",
        "selected_maximum_score_mean_micro",
        "sum_individual_rescue_deltas_micro",
        "mean_individual_rescue_delta_micro",
        "positive_rescue_slate_count",
        "eligible_high_selected_below_threshold_slate_count",
        "selected_high_slate_count",
        "selected_high_score_lineup_slot_count",
        "rescue_sum_is_jointly_achievable",
    }
)
_GENERATION_FIELDS: Final = frozenset(
    {
        "cohort",
        "threshold_operator",
        "score_unit",
        "rate_denominator_unit",
        "total_candidate_count",
        "total_visit_count",
        "total_high_score_visit_count",
        "candidate_membership_semantics",
        "visit_semantics",
        "by_fill_arm",
        "by_world_block",
        "by_fill_arm_world_block",
    }
)
_GENERATION_COMMON_FIELDS: Final = frozenset(
    {
        "source_slate_count",
        "full_population_candidate_count",
        "candidate_membership_count",
        "visit_count",
        "high_score_candidate_membership_count",
        "high_score_visit_count",
        "high_score_visit_rate",
    }
)
_FORBIDDEN_ROW_FIELDS: Final = frozenset(
    {
        "lineup_id",
        "candidate_id",
        "player_id",
        "book_id",
        "slate_id",
        "source_ordinal",
        "roster_identity_sha256",
        "roster_sha256",
        "roster_player_ids",
        "player_ids",
        "realized_union_rank",
        "selection_rank",
        "node_id",
        "logical_id",
        "edge_key",
        "from_id",
        "to_id",
        "nodes",
        "relationships",
        "properties_json",
    }
)


def _reject_floats_and_row_fields(value: object, *, path: str = "summary") -> None:
    if type(value) is float:
        _fail(f"{path} contains a floating-point value")
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if type(key) is not str:
                _fail(f"{path} contains a non-string key")
            if key in _FORBIDDEN_ROW_FIELDS:
                _fail(f"{path} contains forbidden individual-row field {key!r}")
            _reject_floats_and_row_fields(nested, path=f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, nested in enumerate(value):
            _reject_floats_and_row_fields(nested, path=f"{path}[{ordinal}]")


def _validate_ratio(
    value: object, *, numerator: int, denominator: int, label: str
) -> None:
    ratio = _mapping(value, label=label)
    _exact_keys(ratio, {"numerator", "denominator"}, label=label)
    if ratio != {"numerator": numerator, "denominator": denominator}:
        _fail(f"{label} arithmetic differs")


def _validate_historical_realized_summary_v1(
    value: object,
    *,
    binding: _Binding,
) -> dict[str, object]:
    summary = _mapping(value, label="historical-realized summary")
    _reject_floats_and_row_fields(summary)
    _exact_keys(summary, _ROOT_FIELDS, label="historical-realized summary")
    retained_hash = _digest(summary.get("summary_sha256"), label="summary SHA-256")
    if retained_hash != canonical_sha256(
        {key: nested for key, nested in summary.items() if key != "summary_sha256"}
    ):
        _fail("historical-realized summary self-hash differs")
    if (
        summary.get("schema_version") != SUMMARY_SCHEMA
        or summary.get("evidence_class") != EVIDENCE_CLASS
        or summary.get("threshold_dk") != binding.threshold_dk
        or summary.get("threshold_micro")
        != binding.threshold_dk * historical.MICRO_DK_PER_POINT
        or summary.get("uses_realized_outcomes") is not True
        or summary.get("persisted_realized_labels_only") is not True
        or summary.get("separate_from_corpus_graph_vnext_v2") is not True
        or summary.get("complete") is not True
        or any(
            summary.get(field) is not False
            for field in (
                "raw_outcome_query_performed",
                "lineup_rescore_performed",
                "individual_rows_included",
                "neo4j_mutation_performed",
                "promotion_authority",
                "decision_authority",
                "policy_feedback_authority",
            )
        )
    ):
        _fail("historical-realized summary authority law differs")

    source = _mapping(summary.get("source_binding"), label="summary source binding")
    _exact_keys(source, _SOURCE_BINDING_FIELDS, label="summary source binding")
    if (
        source.get("accepted_e0_receipt_file_sha256") != binding.receipt_file_sha256
        or source.get("accepted_e0_receipt_sha256") != binding.receipt_sha256
        or source.get("e0_plan_sha256") != binding.plan_sha256
        or source.get("e0_manifest_sha256") != binding.manifest_sha256
        or source.get("no_rescore_funnel_identity") != binding.funnel_identity
        or source.get("no_rescore_funnel_internal_sha256")
        != binding.funnel_internal_sha256
        or source.get("source_object_count") != binding.source_object_count
        or source.get("source_object_manifest_sha256")
        != binding.source_object_manifest_sha256
        or source.get("source_row_digest_manifest_sha256")
        != binding.source_row_digest_manifest_sha256
        or source.get("node_rows_sha256") != binding.node_rows_sha256
        or source.get("relationship_rows_sha256") != binding.relationship_rows_sha256
    ):
        _fail("historical-realized source binding differs")
    _identity(source["no_rescore_funnel_identity"], label="summary funnel identity")

    outcome = _mapping(
        summary.get("outcome_funnel_summary"), label="outcome funnel summary"
    )
    _exact_keys(outcome, _OUTCOME_FIELDS, label="outcome funnel summary")
    if (
        outcome.get("cohort") != "persisted-eligible-lineups-at-or-above-threshold"
        or outcome.get("threshold_operator") != "greater-than-or-equal"
        or outcome.get("score_unit") != "micro_dk"
        or outcome.get("source_slate_count") != binding.slate_count
        or outcome.get("final_fit_strategy_count") != len(binding.strategy_ids)
        or outcome.get("eligible_high_score_lineup_count")
        != binding.expected_reconciliation["high_score_lineup_count"]
        or outcome.get("observed_in_any_final_fit_book_count")
        != binding.expected_reconciliation["selected_high_score_lineup_count"]
        or outcome.get("first_observed_absence_count")
        != binding.expected_reconciliation["missed_high_score_lineup_count"]
        or outcome.get("opportunity_slate_count")
        != binding.expected_reconciliation["opportunity_slate_count"]
        or outcome.get("converted_slate_count")
        != binding.expected_reconciliation["converted_slate_count"]
        or outcome.get("first_observed_absence_class") != FIRST_OBSERVED_ABSENCE_CLASS
        or outcome.get("absence_derivation")
        != "synthesized-set-difference-across-observed-final-fit-books"
        or outcome.get("source_emitted_selector_rejection") is not False
        or outcome.get("causal_first_loss_claim") is not False
    ):
        _fail("outcome funnel summary semantics differ")
    high_count = _integer(
        outcome["eligible_high_score_lineup_count"], label="eligible high count"
    )
    captured_count = _integer(
        outcome["observed_in_any_final_fit_book_count"], label="captured count"
    )
    absent_count = _integer(
        outcome["first_observed_absence_count"], label="absence count"
    )
    opportunity_count = _integer(
        outcome["opportunity_slate_count"], label="opportunity slate count"
    )
    converted_count = _integer(
        outcome["converted_slate_count"], label="converted slate count"
    )
    selected_edges = _integer(
        outcome["selected_high_scorer_book_edge_count"],
        label="selected high-scorer edge count",
    )
    absent_edges = _integer(
        outcome["absent_high_scorer_book_edge_count"],
        label="absent high-scorer edge count",
    )
    classification_edges = _integer(
        outcome["book_classification_edge_count"],
        label="book classification edge count",
    )
    if (
        captured_count + absent_count != high_count
        or outcome.get("unconverted_opportunity_slate_count")
        != opportunity_count - converted_count
        or selected_edges + absent_edges != classification_edges
        or classification_edges != high_count * len(binding.strategy_ids)
    ):
        _fail("outcome funnel summary arithmetic differs")

    strategies = [
        _mapping(row, label="strategy rescue row")
        for row in _sequence(
            summary.get("strategy_rescue_summary"), label="strategy rescue summary"
        )
    ]
    if len(strategies) != len(binding.strategy_ids):
        _fail("strategy rescue row census differs")
    eligible_sums: set[int] = set()
    selected_slot_sum = 0
    for ordinal, (strategy_id, row) in enumerate(
        zip(binding.strategy_ids, strategies, strict=True)
    ):
        _exact_keys(row, _STRATEGY_FIELDS, label=f"strategy rescue row[{ordinal}]")
        if (
            row.get("strategy_id") != strategy_id
            or row.get("cohort") != "one-final-fit-book-per-source-slate"
            or row.get("threshold_operator") != "greater-than-or-equal"
            or row.get("score_unit") != "micro_dk"
            or row.get("mean_denominator_slate_count") != binding.slate_count
            or row.get("source_slate_count") != binding.slate_count
            or row.get("entry_count_k") != 80
            or row.get("rescue_sum_is_jointly_achievable") is not False
        ):
            _fail(f"strategy rescue row[{ordinal}] semantics differ")
        _digest(row.get("strategy_sha256"), label=f"strategy row[{ordinal}] SHA")
        eligible_sum = _integer(
            row.get("eligible_maximum_score_sum_micro"), label="eligible maximum sum"
        )
        selected_sum = _integer(
            row.get("selected_maximum_score_sum_micro"), label="selected maximum sum"
        )
        rescue_sum = _integer(
            row.get("sum_individual_rescue_deltas_micro"), label="rescue sum"
        )
        if eligible_sum - selected_sum != rescue_sum:
            _fail(f"strategy rescue row[{ordinal}] score arithmetic differs")
        _validate_ratio(
            row.get("eligible_maximum_score_mean_micro"),
            numerator=eligible_sum,
            denominator=binding.slate_count,
            label="eligible maximum mean",
        )
        _validate_ratio(
            row.get("selected_maximum_score_mean_micro"),
            numerator=selected_sum,
            denominator=binding.slate_count,
            label="selected maximum mean",
        )
        _validate_ratio(
            row.get("mean_individual_rescue_delta_micro"),
            numerator=rescue_sum,
            denominator=binding.slate_count,
            label="rescue mean",
        )
        for field in (
            "positive_rescue_slate_count",
            "eligible_high_selected_below_threshold_slate_count",
            "selected_high_slate_count",
        ):
            count = _integer(row.get(field), label=f"strategy {field}")
            if count > binding.slate_count:
                _fail(f"strategy rescue row[{ordinal}] {field} exceeds panel")
        selected_slot_sum += _integer(
            row.get("selected_high_score_lineup_slot_count"),
            label="selected high-score lineup slot count",
        )
        eligible_sums.add(eligible_sum)
    if len(eligible_sums) != 1 or selected_slot_sum != selected_edges:
        _fail("strategy rescue cross-row reconciliation differs")

    generation = _mapping(
        summary.get("generation_yield_summary"), label="generation yield summary"
    )
    _exact_keys(generation, _GENERATION_FIELDS, label="generation yield summary")
    total_candidates = _integer(
        generation.get("total_candidate_count"), label="total candidate count"
    )
    total_visits = _integer(
        generation.get("total_visit_count"), label="total visit count", minimum=1
    )
    total_high_visits = _integer(
        generation.get("total_high_score_visit_count"),
        label="total high-score visit count",
    )
    if (
        generation.get("cohort") != "full-fixed-g0-candidate-population"
        or generation.get("threshold_operator") != "greater-than-or-equal"
        or generation.get("score_unit") != "micro_dk"
        or generation.get("rate_denominator_unit") != "generation_visit"
        or total_candidates != binding.expected_reconciliation["candidate_count"]
        or total_visits != binding.expected_reconciliation["visit_occurrence_count"]
        or generation.get("candidate_membership_semantics")
        != "overlapping-within-dimension-not-additive-across-rows"
        or generation.get("visit_semantics") != "partitioned-generation-occurrences"
    ):
        _fail("generation yield summary semantics differ")

    def validate_generation_rows(
        value: object,
        *,
        coordinates: Sequence[tuple[str, str]],
        label: str,
    ) -> list[dict[str, object]]:
        rows = [
            _mapping(row, label=f"{label} row") for row in _sequence(value, label=label)
        ]
        if len(rows) != len(coordinates):
            _fail(f"{label} row census differs")
        for ordinal, (row, coordinate) in enumerate(
            zip(rows, coordinates, strict=True)
        ):
            id_fields = (
                {"fill_arm_id", "world_block_id"}
                if coordinate[0] and coordinate[1]
                else {"fill_arm_id"}
                if coordinate[0]
                else {"world_block_id"}
            )
            _exact_keys(
                row,
                _GENERATION_COMMON_FIELDS | id_fields,
                label=f"{label} row[{ordinal}]",
            )
            if (
                (coordinate[0] and row.get("fill_arm_id") != coordinate[0])
                or (coordinate[1] and row.get("world_block_id") != coordinate[1])
                or row.get("source_slate_count") != binding.slate_count
                or row.get("full_population_candidate_count") != total_candidates
            ):
                _fail(f"{label} row[{ordinal}] coordinate/census differs")
            candidate_membership = _integer(
                row.get("candidate_membership_count"), label="candidate membership"
            )
            visits = _integer(
                row.get("visit_count"), label="generation visits", minimum=1
            )
            high_membership = _integer(
                row.get("high_score_candidate_membership_count"),
                label="high-score candidate membership",
            )
            high_visits = _integer(
                row.get("high_score_visit_count"), label="high-score visits"
            )
            if (
                candidate_membership > total_candidates
                or high_membership > candidate_membership
                or high_visits > visits
            ):
                _fail(f"{label} row[{ordinal}] bounds differ")
            _validate_ratio(
                row.get("high_score_visit_rate"),
                numerator=high_visits,
                denominator=visits,
                label=f"{label} row[{ordinal}] visit rate",
            )
        return rows

    arm_rows = validate_generation_rows(
        generation.get("by_fill_arm"),
        coordinates=[(arm, "") for arm in binding.arm_ids],
        label="fill-arm yield",
    )
    block_rows = validate_generation_rows(
        generation.get("by_world_block"),
        coordinates=[("", block) for block in binding.block_ids],
        label="world-block yield",
    )
    cell_rows = validate_generation_rows(
        generation.get("by_fill_arm_world_block"),
        coordinates=[
            (arm, block) for arm in binding.arm_ids for block in binding.block_ids
        ],
        label="arm-block yield",
    )
    if any(
        sum(int(row["visit_count"]) for row in rows) != total_visits
        for rows in (arm_rows, block_rows, cell_rows)
    ):
        _fail("generation visit partition arithmetic differs")
    if any(
        sum(int(row["high_score_visit_count"]) for row in rows) != total_high_visits
        for rows in (arm_rows, block_rows, cell_rows)
    ):
        _fail("generation high-score visit partition arithmetic differs")
    return summary


def validate_historical_realized_summary_v1(value: object) -> dict[str, object]:
    """Validate one accepted-E0 aggregate companion and return a plain copy."""

    return _validate_historical_realized_summary_v1(value, binding=_PRODUCTION_BINDING)


def _build_historical_realized_summary_v1(
    *,
    accepted_e0_receipt_raw: bytes,
    no_rescore_funnel_raw: bytes,
    e0_plan: historical.HistoricalNeo4jGraphPlanV1,
    binding: _Binding,
) -> dict[str, object]:
    receipt, funnel, roots = _bind_sources(
        accepted_e0_receipt_raw=accepted_e0_receipt_raw,
        no_rescore_funnel_raw=no_rescore_funnel_raw,
        e0_plan=e0_plan,
        binding=binding,
    )
    summary = _aggregate_bound_plan(
        plan=e0_plan,
        funnel=funnel,
        receipt=receipt,
        roots=roots,
        binding=binding,
    )
    return _validate_historical_realized_summary_v1(summary, binding=binding)


def build_historical_realized_summary_v1(
    *,
    accepted_e0_receipt_raw: bytes,
    no_rescore_funnel_raw: bytes,
    e0_plan: historical.HistoricalNeo4jGraphPlanV1,
) -> dict[str, object]:
    """Build the fixed accepted-E0 summary from caller-supplied exact inputs.

    There is intentionally no reader callback, threshold override, expectations
    override, Neo4j surface, or output path in this production entry point.
    """

    return _build_historical_realized_summary_v1(
        accepted_e0_receipt_raw=accepted_e0_receipt_raw,
        no_rescore_funnel_raw=no_rescore_funnel_raw,
        e0_plan=e0_plan,
        binding=_PRODUCTION_BINDING,
    )


__all__ = [
    "ACCEPTED_E0_MANIFEST_SHA256",
    "ACCEPTED_E0_PLAN_SHA256",
    "ACCEPTED_E0_RECEIPT_FILE_SHA256",
    "ACCEPTED_E0_RECEIPT_SHA256",
    "EVIDENCE_CLASS",
    "FIRST_OBSERVED_ABSENCE_CLASS",
    "SUMMARY_SCHEMA",
    "CorpusR6HistoricalRealizedSummaryV1Error",
    "build_historical_realized_summary_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "validate_historical_realized_summary_v1",
]
