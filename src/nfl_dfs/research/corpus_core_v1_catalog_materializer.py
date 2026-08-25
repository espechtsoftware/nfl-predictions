"""Pure exact-read and create-once sharding for the Core v1 catalog.

The materializer is deliberately callback-driven.  It owns no cloud client,
process runner, outcome reader, graph writer, or T230 science entry point.  It
exact-reads the terminal source panel, terminal T230 release, their 378 bound
source-arm results, and their 54 bound T230 results.  Those already-retained
payloads are passed to the stable Core v1 catalog builder without science
recomputation.

V1 assembles the logical catalog in memory so its existing ``catalog_sha256``
remains authoritative.  It publishes that byte-valid logical authority first,
then each already-validated slate as a verbatim create-once shard, and a small
root index last.  The explicit payload ceiling fails before the first
publication.  Shards make publication resumable and support narrow consumers;
they do not remove V1's monolithic authority object or in-memory peak.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Final

from nfl_dfs.research import corpus_core_v1_catalog as core
from nfl_dfs.research import corpus_parametric_batch as batch


SHARDED_ROOT_SCHEMA: Final = "corpus-core-v1-sharded-catalog-root/v1"
SLATE_SMOKE_SCHEMA: Final = "corpus-core-v1-slate-smoke-projection/v1"
PUBLICATION_MODE: Final = "create_once"
ROOT_FILENAME: Final = "catalog-root.json"
CATALOG_FILENAME: Final = "catalog.json"

_FALSE_AUTHORITY_FIELDS: Final = (
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "historical_retune_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "live_policy_access_licensed",
    "production_change_licensed",
    "analytical_authority",
    "promotion_authority",
    "decision_authority",
)
_ROOT_KEYS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "create_once",
    "catalog_id",
    "catalog_sha256",
    "catalog_identity",
    "catalog_header",
    "catalog_header_sha256",
    "shard_uri_law",
    "shard_count",
    "shard_descriptors",
    "shard_descriptors_sha256",
    "materialization_metrics",
    "complete",
    "outcome_fields_read",
    "science_recomputation_performed",
    *_FALSE_AUTHORITY_FIELDS,
    "sharded_catalog_root_sha256",
})
_DESCRIPTOR_KEYS: Final = frozenset({
    "source_ordinal",
    "slate",
    "lineup_count",
    "rank_count",
    "book_count",
    "slate_catalog_sha256",
    "shard_identity",
    "descriptor_sha256",
})
_METRIC_KEYS: Final = frozenset({
    "peak_logical_catalog_bytes_materialized",
    "logical_catalog_payload_ceiling_bytes",
    "union_roster_membership_count",
    "source_arm_result_read_count",
    "t230_result_read_count",
    "logical_catalog_assembled_in_memory",
    "payload_ceiling_passed",
})
_SLATE_KEYS: Final = frozenset({"season", "week", "slate_id"})
_SMOKE_REPORT_KEYS: Final = frozenset({
    "schema_version",
    "execution_mode",
    "source_ordinal",
    "slate",
    "source_panel_identity",
    "panel_member_sha256",
    "source_arm_result_identities_sha256",
    "t230_result_identity",
    "t230_slate_result_sha256",
    "slate_catalog",
    "slate_catalog_sha256",
    "structural_counts",
    "structural_hashes",
    "outcome_fields_read",
    "science_recomputation_performed",
    "root_publication_authority",
    "production_change_licensed",
    "decision_authority",
    "smoke_projection_sha256",
})


class CorpusCoreV1CatalogMaterializerError(ValueError):
    """The sharded Core v1 materialization failed closed."""


@dataclass(frozen=True, slots=True)
class CreateOncePublication:
    """A caller-owned create-once result.

    ``created=False`` means an equal create-once object was recovered.  The
    materializer never trusts that claim: it exact-reopens the generation and
    requires byte equality before continuing.
    """

    identity: Mapping[str, object]
    created: bool


@dataclass(frozen=True, slots=True)
class PublishedShardedCoreV1Catalog:
    root: Mapping[str, object]
    root_identity: Mapping[str, object]
    catalog_identity: Mapping[str, object]
    shard_identities: tuple[Mapping[str, object], ...]
    logical_catalog: Mapping[str, object]
    catalog_created: bool
    created_shard_count: int
    recovered_shard_count: int
    root_created: bool


@dataclass(frozen=True, slots=True)
class ReopenedShardedCoreV1Catalog:
    """Exact generation-pinned authority recovered from a sharded root."""

    root: Mapping[str, object]
    root_identity: Mapping[str, object]
    catalog_identity: Mapping[str, object]
    shard_identities: tuple[Mapping[str, object], ...]
    logical_catalog: Mapping[str, object]


ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], CreateOncePublication]


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1CatalogMaterializerError(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _fail(message: str) -> None:
    raise CorpusCoreV1CatalogMaterializerError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1CatalogMaterializerError(str(exc)) from exc


def _json_identity(
    value: object, identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return batch.validate_json_identity(value, identity, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1CatalogMaterializerError(str(exc)) from exc


def _parse_json(raw: bytes, *, label: str) -> object:
    try:
        return batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1CatalogMaterializerError(str(exc)) from exc


def _self_hash(value: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    retained = value.get(field)
    body = {key: item for key, item in value.items() if key != field}
    if (
        type(retained) is not str
        or len(retained) != 64
        or any(character not in "0123456789abcdef" for character in retained)
        or canonical_sha256(body) != retained
    ):
        _fail(f"{label} self-hash differs")


def _output_prefix(value: object) -> str:
    try:
        # Reuse the repository's one canonical GCS-prefix law.
        return batch._gcs_uri(  # noqa: SLF001
            value, label="Core v1 catalog output prefix", prefix=True
        )
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1CatalogMaterializerError(str(exc)) from exc


def shard_uri(output_prefix: str, source_ordinal: int) -> str:
    prefix = _output_prefix(output_prefix)
    ordinal = _exact_int(
        source_ordinal, label="Core v1 shard source ordinal"
    )
    if ordinal >= core.EXPECTED_SOURCE_SLATE_COUNT:
        _fail("Core v1 shard source ordinal is outside 0..53")
    return f"{prefix}slates/{ordinal:02d}.json"


def root_uri(output_prefix: str) -> str:
    return _output_prefix(output_prefix) + ROOT_FILENAME


def logical_catalog_uri(output_prefix: str) -> str:
    return _output_prefix(output_prefix) + CATALOG_FILENAME


def _read_json_exact(
    identity: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object], bytes]:
    retained_identity = _identity(identity, label=f"{label} identity")
    try:
        raw = read_exact(retained_identity)
    except Exception as exc:
        raise CorpusCoreV1CatalogMaterializerError(
            f"{label} exact read failed"
        ) from exc
    if type(raw) is not bytes:
        _fail(f"{label} exact reader did not return bytes")
    if (
        len(raw) != retained_identity["bytes"]
        or sha256(raw).hexdigest() != retained_identity["sha256"]
    ):
        _fail(f"{label} exact bytes differ from their identity")
    value = dict(_mapping(_parse_json(raw, label=label), label=label))
    _json_identity(value, retained_identity, label=f"{label} identity")
    return retained_identity, value, raw


def _publish_exact(
    *,
    uri: str,
    value: Mapping[str, object],
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
    label: str,
) -> tuple[dict[str, object], bool]:
    raw = canonical_json_bytes(value)
    try:
        publication = publish_create_once(uri, raw)
    except Exception as exc:
        raise CorpusCoreV1CatalogMaterializerError(
            f"{label} create-once publication failed"
        ) from exc
    if (
        not isinstance(publication, CreateOncePublication)
        or type(publication.created) is not bool
    ):
        _fail(f"{label} create-once publication result differs")
    identity = _identity(publication.identity, label=f"{label} identity")
    if (
        identity["uri"] != uri
        or identity["sha256"] != sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
    ):
        _fail(f"{label} create-once identity differs")
    _, reopened, reopened_raw = _read_json_exact(
        identity, read_exact=read_exact, label=f"reopened {label}"
    )
    if reopened_raw != raw or reopened != value:
        _fail(f"{label} create-once reopen differs")
    return identity, publication.created


def _bound_builder_inputs(
    *,
    source_panel_identity: object,
    t230_panel_release_identity: object,
    read_exact: ReadExact,
) -> dict[str, object]:
    panel_identity, panel, _ = _read_json_exact(
        source_panel_identity,
        read_exact=read_exact,
        label="terminal source panel",
    )
    release_identity, release, _ = _read_json_exact(
        t230_panel_release_identity,
        read_exact=read_exact,
        label="terminal T230 panel release",
    )
    panel_members = list(
        _sequence(panel.get("accepted_slates"), label="source panel members")
    )
    release_rows = list(
        _sequence(
            release.get("ordered_slate_acceptances"),
            label="T230 release rows",
        )
    )
    if (
        len(panel_members) != core.EXPECTED_SOURCE_SLATE_COUNT
        or len(release_rows) != core.EXPECTED_SOURCE_SLATE_COUNT
    ):
        _fail("terminal panel/release does not contain exactly 54 members")

    source_slates: list[dict[str, object]] = []
    t230_results: list[dict[str, object]] = []
    retained_bound_identities: set[tuple[object, ...]] = set()
    for source_ordinal, (member_raw, release_row_raw) in enumerate(
        zip(panel_members, release_rows, strict=True)
    ):
        member = _mapping(member_raw, label=f"source panel member[{source_ordinal}]")
        release_row = _mapping(
            release_row_raw, label=f"T230 release row[{source_ordinal}]"
        )
        t230_identity, t230_result, _ = _read_json_exact(
            release_row.get("result_identity"),
            read_exact=read_exact,
            label=f"T230 result[{source_ordinal}]",
        )
        inputs = _mapping(
            t230_result.get("input_artifact_bindings"),
            label=f"T230 result[{source_ordinal}] input bindings",
        )
        variants: list[dict[str, object]] = []
        arms = list(_sequence(member.get("arms"), label="source panel arms"))
        if len(arms) != len(core.SOURCE_STRATEGY_IDS):
            _fail("source panel member does not contain exactly seven arms")
        for arm_ordinal, arm_raw in enumerate(arms):
            arm = _mapping(
                arm_raw,
                label=f"source panel member[{source_ordinal}] arm[{arm_ordinal}]",
            )
            arm_identity, arm_result, _ = _read_json_exact(
                arm.get("result_identity"),
                read_exact=read_exact,
                label=(
                    f"source result[{source_ordinal}][{arm_ordinal}]"
                ),
            )
            key = (
                arm_identity["uri"],
                arm_identity["generation"],
                arm_identity["sha256"],
                arm_identity["bytes"],
            )
            if key in retained_bound_identities:
                _fail("source-arm/T230 result identities repeat")
            retained_bound_identities.add(key)
            variants.append({
                "result": arm_result,
                "result_identity": arm_identity,
            })
        t230_key = (
            t230_identity["uri"],
            t230_identity["generation"],
            t230_identity["sha256"],
            t230_identity["bytes"],
        )
        if t230_key in retained_bound_identities:
            _fail("source-arm/T230 result identities repeat")
        retained_bound_identities.add(t230_key)
        source_slates.append({
            "source_ordinal": source_ordinal,
            "panel_member": dict(member),
            "later_source_freeze_identity": inputs.get(
                "later_source_freeze_identity"
            ),
            "compatibility_import_sha256": inputs.get(
                "compatibility_import_sha256"
            ),
            "candidate_provenance_sha256": inputs.get(
                "candidate_provenance_sha256"
            ),
            "reconstruction_sha256": inputs.get("reconstruction_sha256"),
            "variant_results": variants,
        })
        t230_results.append({
            "result": t230_result,
            "result_identity": t230_identity,
        })
    expected_bound_count = core.EXPECTED_SOURCE_SLATE_COUNT * (
        len(core.SOURCE_STRATEGY_IDS) + 1
    )
    if len(retained_bound_identities) != expected_bound_count:
        _fail("source-arm/T230 exact-read identity census differs")
    return {
        "source_panel": panel,
        "source_panel_identity": panel_identity,
        "t230_panel_release": release,
        "t230_panel_release_identity": release_identity,
        "source_slates": source_slates,
        "t230_results": t230_results,
    }


def _descriptor(
    *, slate: Mapping[str, object], shard_identity: Mapping[str, object],
) -> dict[str, object]:
    union = _mapping(slate.get("union_population"), label="catalog shard union")
    body = {
        "source_ordinal": slate["source_ordinal"],
        "slate": dict(_mapping(slate.get("slate"), label="catalog shard slate")),
        "lineup_count": union["lineup_count"],
        "rank_count": slate["rank_count"],
        "book_count": slate["book_count"],
        "slate_catalog_sha256": slate["slate_catalog_sha256"],
        "shard_identity": dict(shard_identity),
    }
    return _self_hash(body, "descriptor_sha256")


def build_core_v1_slate_smoke_projection(
    *,
    source_ordinal: int,
    source_panel_identity: Mapping[str, object],
    t230_result_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Project one real outcome-blind T230 smoke result into a slate shard."""
    ordinal = _exact_int(
        source_ordinal, label="Core v1 smoke source ordinal"
    )
    if ordinal >= core.EXPECTED_SOURCE_SLATE_COUNT:
        _fail("Core v1 smoke source ordinal is outside 0..53")
    panel_identity, panel, _ = _read_json_exact(
        source_panel_identity,
        read_exact=read_exact,
        label="Core v1 smoke source panel",
    )
    _validate_self_hash(
        panel,
        field="panel_index_sha256",
        label="Core v1 smoke source panel",
    )
    members = list(
        _sequence(panel.get("accepted_slates"), label="smoke panel members")
    )
    if (
        panel.get("schema_version") != core.SOURCE_PANEL_SCHEMA
        or panel.get("accepted_slate_count")
        != core.EXPECTED_SOURCE_SLATE_COUNT
        or len(members) != core.EXPECTED_SOURCE_SLATE_COUNT
        or panel.get("exclusions") != []
        or panel.get("failures") != []
        or panel.get("missing_tasks") != []
    ):
        _fail("Core v1 smoke source panel structural root differs")
    member = dict(
        _mapping(members[ordinal], label="Core v1 smoke panel member")
    )
    arms = list(_sequence(member.get("arms"), label="smoke source arms"))
    if len(arms) != len(core.SOURCE_STRATEGY_IDS):
        _fail("Core v1 smoke panel member does not contain seven arms")

    retained_arm_identities: list[dict[str, object]] = []
    variants: list[dict[str, object]] = []
    for arm_ordinal, raw_arm in enumerate(arms):
        arm = _mapping(raw_arm, label=f"smoke source arm[{arm_ordinal}]")
        arm_identity, arm_result, _ = _read_json_exact(
            arm.get("result_identity"),
            read_exact=read_exact,
            label=f"smoke source result[{arm_ordinal}]",
        )
        retained_arm_identities.append(arm_identity)
        variants.append({
            "result": arm_result,
            "result_identity": arm_identity,
        })
    retained_t230_identity, t230_result, _ = _read_json_exact(
        t230_result_identity,
        read_exact=read_exact,
        label="Core v1 smoke T230 result",
    )
    inputs = _mapping(
        t230_result.get("input_artifact_bindings"),
        label="Core v1 smoke T230 input bindings",
    )
    source_input = {
        "source_ordinal": ordinal,
        "panel_member": member,
        "later_source_freeze_identity": inputs.get(
            "later_source_freeze_identity"
        ),
        "compatibility_import_sha256": inputs.get(
            "compatibility_import_sha256"
        ),
        "candidate_provenance_sha256": inputs.get(
            "candidate_provenance_sha256"
        ),
        "reconstruction_sha256": inputs.get("reconstruction_sha256"),
        "variant_results": variants,
    }
    try:
        slate_catalog = core.build_core_v1_catalog_slate(
            source_input=source_input,
            t230_result={
                "result": t230_result,
                "result_identity": retained_t230_identity,
            },
        )
    except core.CorpusCoreV1CatalogError as exc:
        raise CorpusCoreV1CatalogMaterializerError(str(exc)) from exc
    union = _mapping(
        slate_catalog.get("union_population"), label="smoke union population"
    )
    ranks = list(_sequence(slate_catalog.get("ranks"), label="smoke ranks"))
    books = list(_sequence(slate_catalog.get("books"), label="smoke books"))
    source_populations = list(
        _sequence(
            slate_catalog.get("source_populations"),
            label="smoke source populations",
        )
    )
    body = {
        "schema_version": SLATE_SMOKE_SCHEMA,
        "execution_mode": "outcome-blind-structural-one-slate-smoke",
        "source_ordinal": ordinal,
        "slate": slate_catalog["slate"],
        "source_panel_identity": panel_identity,
        "panel_member_sha256": canonical_sha256(member),
        "source_arm_result_identities_sha256": canonical_sha256(
            retained_arm_identities
        ),
        "t230_result_identity": retained_t230_identity,
        "t230_slate_result_sha256": t230_result[
            "t230_slate_result_sha256"
        ],
        "slate_catalog": slate_catalog,
        "slate_catalog_sha256": slate_catalog["slate_catalog_sha256"],
        "structural_counts": {
            "source_arm_result_count": len(retained_arm_identities),
            "union_lineup_count": union["lineup_count"],
            "source_population_count": len(source_populations),
            "rank_count": len(ranks),
            "book_count": len(books),
        },
        "structural_hashes": {
            "union_population_sha256": union["population_sha256"],
            "source_population_set_sha256": canonical_sha256([
                row["source_population_sha256"] for row in source_populations
            ]),
            "rank_set_sha256": canonical_sha256([
                row["rank_sha256"] for row in ranks
            ]),
            "book_set_sha256": canonical_sha256([
                row["book_sha256"] for row in books
            ]),
        },
        "outcome_fields_read": [],
        "science_recomputation_performed": False,
        "root_publication_authority": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    report = _self_hash(body, "smoke_projection_sha256")
    _exact_keys(report, _SMOKE_REPORT_KEYS, label="Core v1 smoke projection")
    _validate_self_hash(
        report,
        field="smoke_projection_sha256",
        label="Core v1 smoke projection",
    )
    return report


def validate_sharded_core_v1_catalog_root(value: object) -> dict[str, object]:
    """Validate the small root's internal census without reading shards."""
    root = dict(_mapping(value, label="sharded Core v1 catalog root"))
    _exact_keys(root, _ROOT_KEYS, label="sharded Core v1 catalog root")
    _validate_self_hash(
        root,
        field="sharded_catalog_root_sha256",
        label="sharded Core v1 catalog root",
    )
    header = dict(_mapping(root.get("catalog_header"), label="catalog header"))
    catalog_identity = _identity(
        root.get("catalog_identity"), label="logical catalog identity"
    )
    catalog_sha256 = root.get("catalog_sha256")
    if (
        type(catalog_sha256) is not str
        or len(catalog_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in catalog_sha256
        )
    ):
        _fail("logical catalog SHA-256 differs")
    descriptors = list(
        _sequence(root.get("shard_descriptors"), label="shard descriptors")
    )
    metrics = _mapping(
        root.get("materialization_metrics"), label="materialization metrics"
    )
    _exact_keys(metrics, _METRIC_KEYS, label="materialization metrics")
    if (
        root.get("schema_version") != SHARDED_ROOT_SCHEMA
        or root.get("publication_mode") != PUBLICATION_MODE
        or root.get("create_once") is not True
        or root.get("catalog_id") != header.get("catalog_id")
        or root.get("catalog_identity") != catalog_identity
        or root.get("catalog_header_sha256") != canonical_sha256(header)
        or root.get("shard_uri_law")
        != "{output_prefix}slates/{source_ordinal:02d}.json"
        or root.get("shard_count") != core.EXPECTED_SOURCE_SLATE_COUNT
        or len(descriptors) != core.EXPECTED_SOURCE_SLATE_COUNT
        or root.get("shard_descriptors_sha256")
        != canonical_sha256(descriptors)
        or root.get("complete") is not True
        or root.get("outcome_fields_read") != []
        or root.get("science_recomputation_performed") is not False
        or any(root.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("sharded Core v1 catalog root law differs")
    logical_bytes = _exact_int(
        metrics.get("peak_logical_catalog_bytes_materialized"),
        label="peak logical catalog bytes",
        minimum=1,
    )
    ceiling = _exact_int(
        metrics.get("logical_catalog_payload_ceiling_bytes"),
        label="logical catalog payload ceiling",
        minimum=1,
    )
    if (
        logical_bytes > ceiling
        or catalog_identity["bytes"] != logical_bytes
        or _exact_int(
            metrics.get("union_roster_membership_count"),
            label="union roster membership count",
            minimum=1,
        ) < core.EXPECTED_SOURCE_SLATE_COUNT * core.EXPECTED_RANK_DEPTH
        or metrics.get("source_arm_result_read_count")
        != core.EXPECTED_SOURCE_SLATE_COUNT * len(core.SOURCE_STRATEGY_IDS)
        or metrics.get("t230_result_read_count")
        != core.EXPECTED_SOURCE_SLATE_COUNT
        or metrics.get("logical_catalog_assembled_in_memory") is not True
        or metrics.get("payload_ceiling_passed") is not True
    ):
        _fail("sharded Core v1 materialization metrics differ")

    observed_uris: set[str] = set()
    observed_slate_keys: set[tuple[object, ...]] = set()
    for source_ordinal, raw in enumerate(descriptors):
        descriptor = _mapping(raw, label=f"shard descriptor[{source_ordinal}]")
        _exact_keys(
            descriptor, _DESCRIPTOR_KEYS, label="shard descriptor"
        )
        _validate_self_hash(
            descriptor,
            field="descriptor_sha256",
            label="shard descriptor",
        )
        slate = _mapping(descriptor.get("slate"), label="descriptor slate")
        _exact_keys(slate, _SLATE_KEYS, label="descriptor slate")
        identity = _identity(
            descriptor.get("shard_identity"), label="descriptor shard identity"
        )
        slate_key = (slate.get("season"), slate.get("week"), slate.get("slate_id"))
        if (
            descriptor.get("source_ordinal") != source_ordinal
            or descriptor.get("rank_count") != core.EXPECTED_STRATEGY_COUNT
            or descriptor.get("book_count")
            != core.EXPECTED_STRATEGY_COUNT * len(core.EXPECTED_BOOK_BUDGETS)
            or descriptor.get("shard_identity") != identity
            or identity["uri"] in observed_uris
            or slate_key in observed_slate_keys
        ):
            _fail("sharded Core v1 descriptor census differs")
        _exact_int(
            descriptor.get("lineup_count"),
            label="descriptor lineup count",
            minimum=core.EXPECTED_RANK_DEPTH,
        )
        observed_uris.add(str(identity["uri"]))
        observed_slate_keys.add(slate_key)
    return root


def _logical_catalog_from_root_and_shards(
    *,
    root: Mapping[str, object],
    read_exact: ReadExact,
) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    header = dict(_mapping(root.get("catalog_header"), label="catalog header"))
    strategy_registry = header.get("strategy_registry")
    freeze_identity = header.get("later_source_freeze_identity")
    freeze_sha256 = header.get("later_source_freeze_sha256")
    slates: list[dict[str, object]] = []
    identities: list[dict[str, object]] = []
    for source_ordinal, raw_descriptor in enumerate(root["shard_descriptors"]):
        descriptor = _mapping(raw_descriptor, label="shard descriptor")
        identity, shard, _ = _read_json_exact(
            descriptor.get("shard_identity"),
            read_exact=read_exact,
            label=f"Core v1 catalog shard[{source_ordinal}]",
        )
        try:
            retained = core.validate_core_v1_catalog_slate(
                shard,
                source_ordinal=source_ordinal,
                strategy_registry=strategy_registry,
                later_source_freeze_identity=freeze_identity,
                later_source_freeze_sha256=freeze_sha256,
            )
        except core.CorpusCoreV1CatalogError as exc:
            raise CorpusCoreV1CatalogMaterializerError(str(exc)) from exc
        union = _mapping(retained["union_population"], label="reopened shard union")
        if descriptor != _descriptor(slate=retained, shard_identity=identity):
            _fail("reopened Core v1 shard differs from its root descriptor")
        if union.get("lineup_count") != descriptor.get("lineup_count"):
            _fail("reopened Core v1 shard lineup count differs")
        slates.append(retained)
        identities.append(identity)
    logical = {
        **header,
        "slates": slates,
        "catalog_sha256": root["catalog_sha256"],
    }
    try:
        retained_catalog = core.validate_core_v1_catalog(logical)
    except core.CorpusCoreV1CatalogError as exc:
        raise CorpusCoreV1CatalogMaterializerError(str(exc)) from exc
    metrics = _mapping(root["materialization_metrics"], label="root metrics")
    if (
        len(canonical_json_bytes(retained_catalog))
        != metrics["peak_logical_catalog_bytes_materialized"]
        or sum(
            int(row["union_population"]["lineup_count"])
            for row in retained_catalog["slates"]
        ) != metrics["union_roster_membership_count"]
    ):
        _fail("reopened logical Core v1 payload metrics differ")
    return retained_catalog, tuple(identities)


def reopen_sharded_core_v1_catalog_authority(
    *, root_identity: Mapping[str, object], read_exact: ReadExact,
) -> ReopenedShardedCoreV1Catalog:
    """Exact-reopen the logical authority and prove all shards reproduce it."""
    retained_root_identity, root, _ = _read_json_exact(
        root_identity, read_exact=read_exact, label="sharded Core v1 catalog root"
    )
    validate_sharded_core_v1_catalog_root(root)
    retained_root_uri = str(retained_root_identity["uri"])
    if not retained_root_uri.endswith(ROOT_FILENAME):
        _fail("sharded Core v1 root URI differs from the deterministic law")
    prefix = retained_root_uri[:-len(ROOT_FILENAME)]
    retained_catalog_identity, monolith, monolith_raw = _read_json_exact(
        root["catalog_identity"],
        read_exact=read_exact,
        label="logical Core v1 catalog authority",
    )
    if retained_catalog_identity["uri"] != logical_catalog_uri(prefix):
        _fail("logical Core v1 catalog URI differs from the deterministic law")
    try:
        retained_monolith = core.validate_core_v1_catalog(monolith)
    except core.CorpusCoreV1CatalogError as exc:
        raise CorpusCoreV1CatalogMaterializerError(str(exc)) from exc
    monolith_header = {
        key: value
        for key, value in retained_monolith.items()
        if key not in {"slates", "catalog_sha256"}
    }
    if (
        retained_monolith["catalog_sha256"] != root["catalog_sha256"]
        or monolith_header != root["catalog_header"]
    ):
        _fail("logical Core v1 catalog authority differs from its root")
    for source_ordinal, descriptor in enumerate(root["shard_descriptors"]):
        identity = _identity(
            _mapping(descriptor, label="root shard descriptor").get(
                "shard_identity"
            ),
            label="root shard identity",
        )
        if identity["uri"] != shard_uri(prefix, source_ordinal):
            _fail("sharded Core v1 shard URI differs from the deterministic law")
    logical, shard_identities = _logical_catalog_from_root_and_shards(
        root=root, read_exact=read_exact
    )
    if (
        canonical_json_bytes(logical) != monolith_raw
        or logical != retained_monolith
    ):
        _fail("Core v1 catalog shards differ from the logical authority")
    return ReopenedShardedCoreV1Catalog(
        root=root,
        root_identity=retained_root_identity,
        catalog_identity=retained_catalog_identity,
        shard_identities=shard_identities,
        logical_catalog=retained_monolith,
    )


def reopen_sharded_core_v1_catalog(
    *, root_identity: Mapping[str, object], read_exact: ReadExact,
) -> dict[str, object]:
    """Compatibility wrapper returning the exact-reopened logical catalog."""
    return dict(reopen_sharded_core_v1_catalog_authority(
        root_identity=root_identity,
        read_exact=read_exact,
    ).logical_catalog)


def materialize_sharded_core_v1_catalog(
    *,
    catalog_id: str,
    source_panel_identity: Mapping[str, object],
    t230_panel_release_identity: Mapping[str, object],
    output_prefix: str,
    max_logical_catalog_bytes: int,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> PublishedShardedCoreV1Catalog:
    """Create/recover the logical authority, 54 shards, then the root last."""
    prefix = _output_prefix(output_prefix)
    ceiling = _exact_int(
        max_logical_catalog_bytes,
        label="Core v1 logical catalog payload ceiling",
        minimum=1,
    )
    inputs = _bound_builder_inputs(
        source_panel_identity=source_panel_identity,
        t230_panel_release_identity=t230_panel_release_identity,
        read_exact=read_exact,
    )
    try:
        logical_catalog = core.build_core_v1_catalog(
            catalog_id=catalog_id, **inputs
        )
    except core.CorpusCoreV1CatalogError as exc:
        raise CorpusCoreV1CatalogMaterializerError(str(exc)) from exc
    logical_raw = canonical_json_bytes(logical_catalog)
    logical_bytes = len(logical_raw)
    membership_count = sum(
        int(row["union_population"]["lineup_count"])
        for row in logical_catalog["slates"]
    )
    if logical_bytes > ceiling:
        _fail(
            "logical Core v1 catalog exceeds its configured payload ceiling "
            f"({logical_bytes} > {ceiling})"
        )

    catalog_identity, catalog_created = _publish_exact(
        uri=logical_catalog_uri(prefix),
        value=logical_catalog,
        read_exact=read_exact,
        publish_create_once=publish_create_once,
        label="logical Core v1 catalog authority",
    )

    descriptors: list[dict[str, object]] = []
    shard_identities: list[dict[str, object]] = []
    created_shards = 0
    for source_ordinal, slate in enumerate(logical_catalog["slates"]):
        try:
            retained_slate = core.validate_core_v1_catalog_slate(
                slate,
                source_ordinal=source_ordinal,
                strategy_registry=logical_catalog["strategy_registry"],
                later_source_freeze_identity=logical_catalog[
                    "later_source_freeze_identity"
                ],
                later_source_freeze_sha256=logical_catalog[
                    "later_source_freeze_sha256"
                ],
            )
        except core.CorpusCoreV1CatalogError as exc:
            raise CorpusCoreV1CatalogMaterializerError(str(exc)) from exc
        identity, created = _publish_exact(
            uri=shard_uri(prefix, source_ordinal),
            value=retained_slate,
            read_exact=read_exact,
            publish_create_once=publish_create_once,
            label=f"Core v1 catalog shard[{source_ordinal}]",
        )
        created_shards += int(created)
        shard_identities.append(identity)
        descriptors.append(_descriptor(
            slate=retained_slate, shard_identity=identity
        ))

    header = {
        key: value
        for key, value in logical_catalog.items()
        if key not in {"slates", "catalog_sha256"}
    }
    root_body = {
        "schema_version": SHARDED_ROOT_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "create_once": True,
        "catalog_id": logical_catalog["catalog_id"],
        "catalog_sha256": logical_catalog["catalog_sha256"],
        "catalog_identity": catalog_identity,
        "catalog_header": header,
        "catalog_header_sha256": canonical_sha256(header),
        "shard_uri_law": "{output_prefix}slates/{source_ordinal:02d}.json",
        "shard_count": len(descriptors),
        "shard_descriptors": descriptors,
        "shard_descriptors_sha256": canonical_sha256(descriptors),
        "materialization_metrics": {
            "peak_logical_catalog_bytes_materialized": logical_bytes,
            "logical_catalog_payload_ceiling_bytes": ceiling,
            "union_roster_membership_count": membership_count,
            "source_arm_result_read_count": (
                core.EXPECTED_SOURCE_SLATE_COUNT * len(core.SOURCE_STRATEGY_IDS)
            ),
            "t230_result_read_count": core.EXPECTED_SOURCE_SLATE_COUNT,
            "logical_catalog_assembled_in_memory": True,
            "payload_ceiling_passed": True,
        },
        "complete": True,
        "outcome_fields_read": [],
        "science_recomputation_performed": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    root = validate_sharded_core_v1_catalog_root(
        _self_hash(root_body, "sharded_catalog_root_sha256")
    )
    retained_root_identity, root_created = _publish_exact(
        uri=root_uri(prefix),
        value=root,
        read_exact=read_exact,
        publish_create_once=publish_create_once,
        label="Core v1 sharded catalog root",
    )
    reopened = reopen_sharded_core_v1_catalog_authority(
        root_identity=retained_root_identity, read_exact=read_exact
    )
    if (
        reopened.catalog_identity != catalog_identity
        or canonical_json_bytes(reopened.logical_catalog) != logical_raw
    ):
        _fail("published sharded Core v1 catalog differs after exact reopen")
    return PublishedShardedCoreV1Catalog(
        root=root,
        root_identity=retained_root_identity,
        catalog_identity=catalog_identity,
        shard_identities=tuple(shard_identities),
        logical_catalog=logical_catalog,
        catalog_created=catalog_created,
        created_shard_count=created_shards,
        recovered_shard_count=len(shard_identities) - created_shards,
        root_created=root_created,
    )


__all__ = [
    "CorpusCoreV1CatalogMaterializerError",
    "CreateOncePublication",
    "PublishedShardedCoreV1Catalog",
    "ReopenedShardedCoreV1Catalog",
    "SHARDED_ROOT_SCHEMA",
    "SLATE_SMOKE_SCHEMA",
    "build_core_v1_slate_smoke_projection",
    "canonical_json_bytes",
    "canonical_sha256",
    "logical_catalog_uri",
    "materialize_sharded_core_v1_catalog",
    "reopen_sharded_core_v1_catalog",
    "reopen_sharded_core_v1_catalog_authority",
    "root_uri",
    "shard_uri",
    "validate_sharded_core_v1_catalog_root",
]
