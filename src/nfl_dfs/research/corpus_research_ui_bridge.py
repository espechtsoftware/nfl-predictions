"""Governed read-only bridge from the strategy graph to the web projection.

The retained registry query receipt contains row counts and hashes, not the
rows themselves.  This bridge therefore re-runs the immutable six-query
catalog through the dedicated reader, requires exact equality with that
receipt, builds the web application's validated materialization, and
publishes both the projection and a create-once receipt.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from nfl_dfs.app import corpus_research as ui
from nfl_dfs.research import corpus_strategy_registry as registry
from nfl_dfs.research.corpus_neo4j_transport import (
    CorpusNeo4jTransportError,
    ExactObjectStore,
    GraphBackend,
    ObjectIdentity,
    REALIZED_OUTCOME_NAMESPACE,
    ValidatedLoadBundle,
    _json,
    _require_allowed_census,
    _strategy_registry_load_uri,
    _validate_component,
    _validate_existing_strategy_registry_load_receipt,
)
from nfl_dfs.research.corpus_retrieval_neo4j import (
    canonical_json_bytes,
    canonical_sha256,
)


BRIDGE_RECEIPT_SCHEMA: Final = (
    "corpus-research-ui-materialization-receipt/v1"
)


class CorpusResearchUIBridgeError(RuntimeError):
    """Graph rows cannot be accepted as the browser projection."""


@dataclass(frozen=True, slots=True)
class PublishedUIProjection:
    projection_identity: ObjectIdentity
    receipt_identity: ObjectIdentity
    projection: dict[str, object]
    receipt: dict[str, object]


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusResearchUIBridgeError(f"{label} must be an object")
    return dict(value)


def _resolve(
    storage: ExactObjectStore, uri: str, *, label: str,
) -> tuple[ObjectIdentity, dict[str, object]]:
    resolved = storage.resolve_optional(uri)
    if resolved is None:
        raise CorpusResearchUIBridgeError(f"{label} is absent")
    identity, raw = resolved
    try:
        body = _json(raw, label=label)
    except CorpusNeo4jTransportError as exc:
        raise CorpusResearchUIBridgeError(f"{label} differs") from exc
    return identity, body


def _publish(
    storage: ExactObjectStore, uri: str, value: Mapping[str, object],
) -> ObjectIdentity:
    raw = canonical_json_bytes(value)
    identity = storage.publish_create_once(uri, raw)
    if storage.read_exact(identity) != raw:
        raise CorpusResearchUIBridgeError(
            "published UI materialization did not reopen exactly"
        )
    return identity


def materialize_ui_projection(
    *,
    storage: ExactObjectStore,
    graph: GraphBackend,
    bundle: ValidatedLoadBundle,
    generated_at_utc: str,
) -> PublishedUIProjection:
    """Materialize the six exact views and bind them to retained receipts."""
    if bundle.manifest_identity is None:
        raise CorpusResearchUIBridgeError(
            "published graph load manifest identity is required"
        )
    try:
        _validate_component(bundle.deployment, graph.component())
        census = _require_allowed_census(
            bundle.deployment, graph.census(), initially_empty=False
        )
    except CorpusNeo4jTransportError as exc:
        raise CorpusResearchUIBridgeError(
            "graph component/census authority differs"
        ) from exc
    if REALIZED_OUTCOME_NAMESPACE in census["workstream_namespaces"]:
        raise CorpusResearchUIBridgeError(
            "realized-outcome namespace is not reserved empty"
        )

    load_identity, load_receipt = _resolve(
        storage,
        _strategy_registry_load_uri(bundle),
        label="strategy registry load receipt",
    )
    try:
        _validate_existing_strategy_registry_load_receipt(
            canonical_json_bytes(load_receipt), bundle=bundle
        )
    except CorpusNeo4jTransportError as exc:
        raise CorpusResearchUIBridgeError(
            "strategy registry load receipt differs"
        ) from exc
    receipt_uris = _mapping(bundle.manifest["receipt_uris"], label="receipt URIs")
    source_identity, source_receipt = _resolve(
        storage,
        str(receipt_uris["strategy_registry_projection"]),
        label="strategy registry projection receipt",
    )
    query_identity, retained_query = _resolve(
        storage,
        str(receipt_uris["strategy_registry_query"]),
        label="strategy registry query receipt",
    )
    try:
        registry.validate_registry_receipt(
            bundle=bundle.strategy_registry_bundle,
            receipt=source_receipt,
        )
        registry.validate_registry_receipt(
            bundle=bundle.strategy_registry_bundle,
            receipt=retained_query,
        )
    except registry.CorpusStrategyRegistryError as exc:
        raise CorpusResearchUIBridgeError(
            "retained registry receipt does not validate"
        ) from exc
    if (
        source_receipt.get("governed_load_manifest")
        != bundle.manifest_identity.as_dict()
        or source_receipt.get("governed_registry_load_receipt")
        != load_identity.as_dict()
        or retained_query.get("registry_projection_receipt")
        != source_identity.as_dict()
        or retained_query.get("governed_load_manifest")
        != bundle.manifest_identity.as_dict()
        or retained_query.get("governed_registry_load_receipt")
        != load_identity.as_dict()
    ):
        raise CorpusResearchUIBridgeError(
            "retained registry receipt chain differs"
        )

    exact_queries = tuple(registry.READ_ONLY_QUERIES)
    catalog = registry.query_catalog()
    manifest_registry = _mapping(
        bundle.manifest["strategy_registry"], label="strategy registry manifest"
    )
    if (
        manifest_registry.get("query_catalog") != catalog
        or manifest_registry.get("query_catalog_sha256")
        != canonical_sha256(catalog)
        or retained_query.get("query_catalog") != catalog
        or retained_query.get("query_catalog_sha256")
        != canonical_sha256(catalog)
    ):
        raise CorpusResearchUIBridgeError("registry query catalog differs")

    calls: list[str] = []
    expected_parameters = {
        "namespace": registry.REGISTRY_NAMESPACE,
        "registry_id": bundle.strategy_registry_bundle.release["registry_id"],
    }

    def run_exact(
        database: str, cypher: str, parameters: Mapping[str, object],
    ) -> list[dict[str, object]]:
        call_index = len(calls)
        if (
            call_index >= len(exact_queries)
            or database != graph.database
            or cypher != exact_queries[call_index].cypher
            or dict(parameters) != expected_parameters
        ):
            raise CorpusResearchUIBridgeError(
                "UI bridge attempted a query outside the immutable catalog"
            )
        calls.append(exact_queries[call_index].name)
        rows = graph.run_read_only_query(database, cypher, parameters)
        return [dict(_mapping(row, label="graph query row")) for row in rows]

    try:
        projection = ui.build_read_only_projection(
            source_projection_receipt=source_receipt,
            database=graph.database,
            queries=[
                ui.ReadOnlyQuery(query.name, query.cypher)
                for query in exact_queries
            ],
            query_runner=run_exact,
            generated_at_utc=generated_at_utc,
        )
        projection = ui.validate_read_only_projection(projection)
    except (ui.CorpusResearchProjectionError, CorpusResearchUIBridgeError) as exc:
        raise CorpusResearchUIBridgeError(
            f"UI projection materialization differs: {exc}"
        ) from exc
    if calls != [query.name for query in exact_queries]:
        raise CorpusResearchUIBridgeError("UI query coverage differs")

    ui_queries = _mapping(
        {
            str(row["name"]): row
            for row in projection["query_receipt"]["queries"]
        },
        label="UI query receipt rows",
    )
    retained_results = _mapping(
        {
            str(row["name"]): row
            for row in retained_query["results"]
        },
        label="retained query results",
    )
    if set(ui_queries) != set(retained_results):
        raise CorpusResearchUIBridgeError(
            "UI/registry query result coverage differs"
        )
    for query, catalog_row in zip(exact_queries, catalog, strict=True):
        ui_row = _mapping(ui_queries[query.name], label="UI query result")
        retained_row = _mapping(
            retained_results[query.name], label="retained query result"
        )
        if (
            ui_row["cypher_sha256"] != catalog_row["sha256"]
            or ui_row["row_count"] != retained_row["row_count"]
            or ui_row["rows_sha256"] != retained_row["rows_sha256"]
        ):
            raise CorpusResearchUIBridgeError(
                f"query {query.name} drifted after its retained receipt"
            )
    total_rows = sum(
        int(row["row_count"]) for row in ui_queries.values()
        if isinstance(row, Mapping)
    )
    if total_rows > ui.MAX_QUERY_ROWS:
        raise CorpusResearchUIBridgeError("combined UI rows exceed 100,000")

    try:
        post_query_census = _require_allowed_census(
            bundle.deployment, graph.census(), initially_empty=False
        )
    except CorpusNeo4jTransportError as exc:
        raise CorpusResearchUIBridgeError(
            "graph census changed to foreign or realized data during UI reads"
        ) from exc
    if post_query_census != census:
        raise CorpusResearchUIBridgeError(
            "graph census changed during the exact UI query catalog"
        )

    output_prefix = str(bundle.manifest["output_prefix"])
    projection_uri = f"{output_prefix}strategy-registry/ui-projection.json"
    receipt_uri = (
        f"{output_prefix}strategy-registry/ui-projection-receipt.json"
    )
    projection_bytes = len(canonical_json_bytes(projection))
    if projection_bytes > ui.MAX_PROJECTION_BYTES:
        raise CorpusResearchUIBridgeError(
            "UI projection exceeds the application's byte limit"
        )
    projection_identity = _publish(storage, projection_uri, projection)
    body = {
        "schema_version": BRIDGE_RECEIPT_SCHEMA,
        "publication_mode": "create_once",
        "governed_load_manifest": bundle.manifest_identity.as_dict(),
        "governed_registry_load_receipt": load_identity.as_dict(),
        "registry_projection_receipt": source_identity.as_dict(),
        "registry_query_receipt": query_identity.as_dict(),
        "ui_projection": projection_identity.as_dict(),
        "registry_release": bundle.strategy_registry_bundle.release_identity.as_dict(),
        "registry_id": bundle.strategy_registry_bundle.release["registry_id"],
        "database": graph.database,
        "query_catalog": catalog,
        "query_catalog_sha256": canonical_sha256(catalog),
        "view_names": [query.name for query in exact_queries],
        "combined_row_count": total_rows,
        "maximum_combined_row_count": ui.MAX_QUERY_ROWS,
        "projection_bytes": projection_bytes,
        "maximum_projection_bytes": ui.MAX_PROJECTION_BYTES,
        "pre_query_graph_census": census,
        "post_query_graph_census": post_query_census,
        "source_projection_schema": registry.PROJECTION_RECEIPT_SCHEMA,
        "ui_projection_schema": ui.UI_PROJECTION_SCHEMA,
        "read_only": True,
        "graph_mutation": False,
        "realized_namespace_reserved": True,
        "uses_realized_outcomes": False,
        "historical_outcome_read_authority": False,
        "outcome_namespace_read": False,
        "outcome_columns_read": [],
        "automatic_promotion": False,
        "application_config_mutation": False,
        "production_policy_authority": False,
        "gcs_remains_authoritative": True,
        "world_matrices_stored_in_graph": False,
        "generated_at_utc": projection["generated_at_utc"],
    }
    receipt = {**body, "bridge_receipt_sha256": canonical_sha256(body)}
    receipt_identity = _publish(storage, receipt_uri, receipt)
    return PublishedUIProjection(
        projection_identity=projection_identity,
        receipt_identity=receipt_identity,
        projection=projection,
        receipt=receipt,
    )


__all__ = [
    "BRIDGE_RECEIPT_SCHEMA",
    "CorpusResearchUIBridgeError",
    "PublishedUIProjection",
    "materialize_ui_projection",
]
