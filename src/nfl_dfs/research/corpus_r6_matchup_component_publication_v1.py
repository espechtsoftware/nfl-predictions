"""Root-last publication boundary for the R6-v2 matchup component panel.

The deterministic reducer in :mod:`corpus_r6_matchup_component_producer_v1`
has two modes: a hash-only offline mode and an explicit body-materialization
mode.  This module owns the latter boundary.  It exact-reopens every supplied
predecessor body before the first output write, passes canonical bytes to an
injected create-once publisher, exact-reopens every returned generation, and
requires the complete 54-entry producer release to be the final new URI.

The module constructs no cloud or warehouse client.  Its callbacks may be a
memory store in tests or a separately reviewed create-once object store in an
operator.  It reads no realized lineup or contest outcome and grants no
source, scoring, fill, retrieval, promotion, graph, production, or decision
authority.  The returned receipt is bounded publication evidence, not the
later tracked capture-plan lock or terminal matchup-source release.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
from typing import Final

from nfl_dfs.research import corpus_r6_matchup_component_producer_v1 as producer
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


PUBLICATION_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-component-publication-receipt/v1"
)


class CorpusR6MatchupComponentPublicationV1Error(ValueError):
    """The input replay or create-once component publication is invalid."""


PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]
ReadExact = Callable[[Mapping[str, object]], bytes]


def _fail(message: str) -> None:
    raise CorpusR6MatchupComponentPublicationV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupComponentPublicationV1Error(str(exc)) from exc


def _bind_raw(
    raw: bytes, identity: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    normalized = _identity(identity, label=label)
    if (
        len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        _fail(f"{label} bytes differ from content identity")
    return normalized


def _read_exact(
    read_exact: ReadExact,
    identity: Mapping[str, object],
    *,
    label: str,
) -> bytes:
    normalized = _identity(identity, label=label)
    try:
        raw = read_exact(normalized)
    except Exception as exc:
        raise CorpusR6MatchupComponentPublicationV1Error(
            f"{label} exact reopen failed"
        ) from exc
    if type(raw) is not bytes:
        _fail(f"{label} exact reader must return bytes")
    _bind_raw(raw, normalized, label=label)
    return raw


def _reopen_body(
    body: object,
    identity: Mapping[str, object],
    *,
    read_exact: ReadExact,
    label: str,
) -> dict[str, object]:
    raw = source.canonical_json_bytes(body)
    normalized = _bind_raw(raw, identity, label=label)
    if _read_exact(read_exact, normalized, label=label) != raw:
        _fail(f"{label} exact-reopened bytes differ")
    return normalized


def _reject_outcome_carriers(value: object, *, label: str) -> None:
    forbidden = {
        "actual_score", "actual_points", "contest_finish", "contest_place",
        "contest_rank", "contest_score", "entry_rank", "lineup_actual",
        "lineup_points", "lineup_score", "payout", "realized_outcome",
        "realized_points", "realized_score", "winner", "winning_score",
    }
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string field")
            normalized = key.strip().lower()
            if normalized in forbidden or (
                "realized" in normalized
                and normalized not in {"uses_realized_outcomes"}
            ):
                _fail(f"{label} contains forbidden outcome field {key!r}")
            if normalized == "outcome_columns_read" and nested != []:
                _fail(f"{label}.outcome_columns_read must be empty")
            if normalized == "uses_realized_outcomes" and nested is not False:
                _fail(f"{label}.uses_realized_outcomes must be false")
            _reject_outcome_carriers(nested, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, nested in enumerate(value):
            _reject_outcome_carriers(nested, label=f"{label}[{ordinal}]")


def _reopen_provenance_body(
    identity: Mapping[str, object],
    *,
    read_exact: ReadExact,
    label: str,
) -> dict[str, object]:
    normalized = _identity(identity, label=label)
    raw = _read_exact(read_exact, normalized, label=label)
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6MatchupComponentPublicationV1Error(
            f"{label} must be canonical JSON"
        ) from exc
    body = _mapping(parsed, label=label)
    if source.canonical_json_bytes(body) != raw:
        _fail(f"{label} canonical bytes differ")
    _reject_outcome_carriers(body, label=label)
    return normalized


def _preflight_exact_inputs(
    *,
    fixed_g0_replay_receipt: Mapping[str, object],
    fixed_g0_replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    structural_catalogs: Sequence[Mapping[str, object]],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
) -> list[dict[str, object]]:
    """Exact-open all supplied roots, bodies, and provenance before writes."""
    reopened: list[dict[str, object]] = []

    def reopen(body: object, identity: object, label: str) -> dict[str, object]:
        normalized = _reopen_body(
            body,
            _mapping(identity, label=f"{label} identity"),
            read_exact=read_exact,
            label=label,
        )
        reopened.append(normalized)
        return normalized

    reopen(
        fixed_g0_replay_receipt,
        fixed_g0_replay_receipt_identity,
        "fixed-G0 replay receipt",
    )
    reopen(catalog_release, catalog_release_identity, "catalog release")
    catalog_entries = _sequence(
        catalog_release.get("entries"), label="catalog release entries"
    )
    catalogs = _sequence(structural_catalogs, label="structural catalogs")
    if len(catalog_entries) != source.TASK_COUNT or len(catalogs) != source.TASK_COUNT:
        _fail("exact input preflight requires 54 catalog entries and bodies")
    for ordinal, (entry_value, catalog) in enumerate(
        zip(catalog_entries, catalogs, strict=True)
    ):
        entry = _mapping(entry_value, label=f"catalog entry[{ordinal}]")
        reopen(catalog, entry.get("catalog_identity"), f"catalog[{ordinal}]")

    reopen(
        accepted_candidate_release,
        accepted_candidate_release_identity,
        "accepted candidate release",
    )
    candidate_entries = _sequence(
        accepted_candidate_release.get("entries"),
        label="accepted candidate entries",
    )
    if len(candidate_entries) != source.TASK_COUNT:
        _fail("exact input preflight requires 54 candidate entries")
    for ordinal, entry_value in enumerate(candidate_entries):
        entry = _mapping(
            entry_value, label=f"accepted candidate entry[{ordinal}]"
        )
        reopen(
            entry.get("candidate_artifact"),
            entry.get("candidate_artifact_identity"),
            f"accepted candidate artifact[{ordinal}]",
        )

    reopen(
        upstream_source_release,
        upstream_source_release_identity,
        "upstream source release",
    )
    upstream_packs = _sequence(
        upstream_source_release.get("packs"), label="upstream packs"
    )
    pack_rows = _sequence(
        upstream_pack_row_objects, label="upstream pack row objects"
    )
    if len(upstream_packs) != len(source.PACK_IDS) or len(pack_rows) != len(
        source.PACK_IDS
    ):
        _fail("exact input preflight requires seven pack entries and bodies")
    for ordinal, (pack_value, rows) in enumerate(
        zip(upstream_packs, pack_rows, strict=True)
    ):
        pack = _mapping(pack_value, label=f"upstream pack[{ordinal}]")
        reopen(rows, pack.get("exact_rows_identity"), f"upstream rows[{ordinal}]")

    provenance: list[dict[str, object]] = []
    provenance.append(_reopen_provenance_body(
        _mapping(
            upstream_source_release.get("fixed_source_root_identity"),
            label="fixed source root identity",
        ),
        read_exact=read_exact,
        label="fixed source root",
    ))
    for ordinal, pack_value in enumerate(upstream_packs):
        pack = _mapping(pack_value, label=f"upstream pack[{ordinal}]")
        query_identity = pack.get("warehouse_query_receipt_identity")
        if query_identity is not None:
            provenance.append(_reopen_provenance_body(
                _mapping(query_identity, label=f"query receipt[{ordinal}]"),
                read_exact=read_exact,
                label=f"warehouse query receipt[{ordinal}]",
            ))
        for manifest_ordinal, identity_value in enumerate(_sequence(
            pack.get("frozen_artifact_manifest_identities"),
            label=f"artifact manifest identities[{ordinal}]",
        )):
            provenance.append(_reopen_provenance_body(
                _mapping(
                    identity_value,
                    label=f"artifact manifest[{ordinal},{manifest_ordinal}]",
                ),
                read_exact=read_exact,
                label=f"frozen artifact manifest[{ordinal},{manifest_ordinal}]",
            ))

    all_identities = [*reopened, *provenance]
    uri_generation = [
        (str(identity["uri"]), str(identity["generation"]))
        for identity in all_identities
    ]
    if len(uri_generation) != len(set(uri_generation)):
        _fail("exact input preflight repeats an identity across semantic roles")
    return provenance


def _with_self_hash(body: Mapping[str, object]) -> dict[str, object]:
    result = dict(body)
    result["component_publication_receipt_sha256"] = source.canonical_sha256(
        result
    )
    return result


def validate_component_publication_receipt_v1(
    value: object,
) -> dict[str, object]:
    item = _mapping(value, label="component publication receipt")
    fields = {
        "schema_version", "producer_id", "producer_release_id",
        "producer_namespace", "source_task_count",
        "fixed_g0_replay_receipt_identity", "catalog_release_identity",
        "accepted_candidate_release_identity", "upstream_source_release_identity",
        "upstream_provenance_identities",
        "upstream_provenance_identity_manifest_sha256",
        "materialized_object_count", "materialized_object_identities",
        "materialized_object_identity_manifest_sha256",
        "producer_release_identity", "producer_release_object_sha256",
        "producer_release_sha256",
        "all_inputs_exact_reopened_before_publication",
        "all_outputs_exact_reopened", "producer_release_published_last",
        "outcome_columns_read", "uses_realized_outcomes",
        *source.FALSE_AUTHORITY_FIELDS,
        "component_publication_receipt_sha256",
    }
    if set(item) != fields:
        _fail("component publication receipt fields differ")
    retained = item.get("component_publication_receipt_sha256")
    if type(retained) is not str or len(retained) != 64:
        _fail("component publication receipt self-hash is invalid")
    body = dict(item)
    del body["component_publication_receipt_sha256"]
    if source.canonical_sha256(body) != retained:
        _fail("component publication receipt self-hash differs")
    if item.get("schema_version") != PUBLICATION_RECEIPT_SCHEMA:
        _fail("component publication receipt schema differs")
    for field, expected in _policy().items():
        if item.get(field) != expected:
            _fail("component publication receipt claims forbidden authority")
    provenance = [
        _identity(value, label="upstream provenance identity")
        for value in _sequence(
            item.get("upstream_provenance_identities"),
            label="upstream provenance identities",
        )
    ]
    objects = [
        _identity(value, label="materialized object identity")
        for value in _sequence(
            item.get("materialized_object_identities"),
            label="materialized object identities",
        )
    ]
    root = _identity(item.get("producer_release_identity"), label="producer root")
    if (
        item.get("source_task_count") != source.TASK_COUNT
        or item.get("materialized_object_count") != len(objects)
        or not objects
        or objects[-1] != root
        or len({str(value["uri"]) for value in objects}) != len(objects)
        or item.get("upstream_provenance_identity_manifest_sha256")
        != source.canonical_sha256(provenance)
        or item.get("materialized_object_identity_manifest_sha256")
        != source.canonical_sha256(objects)
        or item.get("producer_release_object_sha256") != root["sha256"]
        or type(item.get("producer_release_sha256")) is not str
        or len(str(item.get("producer_release_sha256"))) != 64
        or item.get("all_inputs_exact_reopened_before_publication") is not True
        or item.get("all_outputs_exact_reopened") is not True
        or item.get("producer_release_published_last") is not True
    ):
        _fail("component publication receipt root/manifest law differs")
    normalized = dict(item)
    normalized.update({
        "fixed_g0_replay_receipt_identity": _identity(
            item.get("fixed_g0_replay_receipt_identity"), label="fixed replay"
        ),
        "catalog_release_identity": _identity(
            item.get("catalog_release_identity"), label="catalog release"
        ),
        "accepted_candidate_release_identity": _identity(
            item.get("accepted_candidate_release_identity"),
            label="accepted candidate release",
        ),
        "upstream_source_release_identity": _identity(
            item.get("upstream_source_release_identity"),
            label="upstream source release",
        ),
        "upstream_provenance_identities": provenance,
        "materialized_object_identities": objects,
        "producer_release_identity": root,
    })
    if source.canonical_json_bytes(normalized) != source.canonical_json_bytes(item):
        _fail("component publication receipt canonical replay differs")
    return normalized


def publish_all_54_component_release_v1(
    *,
    producer_id: str,
    producer_release_id: str,
    producer_namespace: str,
    fixed_g0_replay_receipt: Mapping[str, object],
    fixed_g0_replay_receipt_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    structural_catalogs: Sequence[Mapping[str, object]],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    producer_code_identity: Mapping[str, object],
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Materialize the complete producer DAG and producer release root last."""
    provenance = _preflight_exact_inputs(
        fixed_g0_replay_receipt=fixed_g0_replay_receipt,
        fixed_g0_replay_receipt_identity=fixed_g0_replay_receipt_identity,
        catalog_release=catalog_release,
        catalog_release_identity=catalog_release_identity,
        structural_catalogs=structural_catalogs,
        accepted_candidate_release=accepted_candidate_release,
        accepted_candidate_release_identity=accepted_candidate_release_identity,
        upstream_source_release=upstream_source_release,
        upstream_source_release_identity=upstream_source_release_identity,
        upstream_pack_row_objects=upstream_pack_row_objects,
        read_exact=read_exact,
    )
    seen_raw: dict[str, bytes] = {}
    seen_identities: dict[str, dict[str, object]] = {}
    first_seen_order: list[str] = []

    def materialize(uri: str, raw: bytes) -> Mapping[str, object]:
        if uri in seen_raw:
            if seen_raw[uri] != raw:
                _fail("one output URI was requested with different bytes")
            return seen_identities[uri]
        try:
            supplied = publish_create_once(uri, raw)
        except Exception as exc:
            raise CorpusR6MatchupComponentPublicationV1Error(
                f"create-once publication failed for {uri}"
            ) from exc
        identity = _bind_raw(raw, supplied, label=f"published {uri}")
        if identity["uri"] != uri:
            _fail("create-once publisher returned a different URI")
        if _read_exact(read_exact, identity, label=f"published {uri}") != raw:
            _fail("create-once published bytes differ on exact reopen")
        seen_raw[uri] = raw
        seen_identities[uri] = identity
        first_seen_order.append(uri)
        return identity

    try:
        panel = producer.produce_all_54_component_panel_v1(
            producer_id=producer_id,
            producer_release_id=producer_release_id,
            producer_namespace=producer_namespace,
            fixed_g0_replay_receipt=fixed_g0_replay_receipt,
            fixed_g0_replay_receipt_identity=fixed_g0_replay_receipt_identity,
            catalog_release=catalog_release,
            catalog_release_identity=catalog_release_identity,
            structural_catalogs=structural_catalogs,
            accepted_candidate_release=accepted_candidate_release,
            accepted_candidate_release_identity=accepted_candidate_release_identity,
            upstream_source_release=upstream_source_release,
            upstream_source_release_identity=upstream_source_release_identity,
            upstream_pack_row_objects=upstream_pack_row_objects,
            producer_code_identity=producer_code_identity,
            body_materializer=materialize,
            read_exact=read_exact,
        )
    except producer.CorpusR6MatchupComponentProducerV1Error as exc:
        raise CorpusR6MatchupComponentPublicationV1Error(str(exc)) from exc
    root = _identity(
        panel.get("producer_release_identity"), label="producer release root"
    )
    identities = [seen_identities[uri] for uri in first_seen_order]
    expected_bundle_uris = {
        str(identity["uri"]) for identity in panel["input_bundle_identities"]
    }
    expected_receipt_uris = {
        str(identity["uri"]) for identity in panel["producer_receipt_identities"]
    }
    if (
        not first_seen_order
        or first_seen_order[-1] != root["uri"]
        or root["uri"] != f"{panel['producer_namespace']}producer-release.json"
        or seen_raw[str(root["uri"])]
        != source.canonical_json_bytes(panel["producer_release"])
        or len(expected_bundle_uris) != source.TASK_COUNT
        or len(expected_receipt_uris) != source.TASK_COUNT
        or not expected_bundle_uris.issubset(seen_raw)
        or not expected_receipt_uris.issubset(seen_raw)
    ):
        _fail("producer release was not published root-last after all 54 tasks")
    receipt = _with_self_hash({
        "schema_version": PUBLICATION_RECEIPT_SCHEMA,
        "producer_id": panel["producer_id"],
        "producer_release_id": panel["producer_release"]["release_id"],
        "producer_namespace": panel["producer_namespace"],
        "source_task_count": source.TASK_COUNT,
        "fixed_g0_replay_receipt_identity": panel[
            "fixed_g0_replay_receipt_identity"
        ],
        "catalog_release_identity": panel["catalog_release_identity"],
        "accepted_candidate_release_identity": panel[
            "accepted_candidate_release_identity"
        ],
        "upstream_source_release_identity": panel[
            "upstream_source_release_identity"
        ],
        "upstream_provenance_identities": provenance,
        "upstream_provenance_identity_manifest_sha256": (
            source.canonical_sha256(provenance)
        ),
        "materialized_object_count": len(identities),
        "materialized_object_identities": identities,
        "materialized_object_identity_manifest_sha256": (
            source.canonical_sha256(identities)
        ),
        "producer_release_identity": root,
        "producer_release_object_sha256": root["sha256"],
        "producer_release_sha256": panel["producer_release"][
            "producer_release_sha256"
        ],
        "all_inputs_exact_reopened_before_publication": True,
        "all_outputs_exact_reopened": True,
        "producer_release_published_last": True,
        **_policy(),
    })
    return {
        "publication_receipt": validate_component_publication_receipt_v1(
            receipt
        ),
        "offline_panel": panel,
    }


__all__ = [
    "CorpusR6MatchupComponentPublicationV1Error",
    "PUBLICATION_RECEIPT_SCHEMA",
    "publish_all_54_component_release_v1",
    "validate_component_publication_receipt_v1",
]
