"""Root-last publication for exact R6 full-union lineup attribution.

The release consumes only two already-sealed artifact families:

* the outcome-blind full-union panel freeze and its task-result envelopes; and
* the terminal persisted realized-grade completion, root, and 54 grade shards.

It never opens the outcome snapshot, query evidence, historical lease, or a
scoring implementation.  Each attribution shard is derived from one exact
frozen task result plus its already-published grade shard, published
create-once, exact-reopened, and predecessor-replayed before the root is
eligible to publish.  The release root is therefore a descriptive research
index, not promotion, production, graph-mutation, or causal authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
import json
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_attribution_v1 as attribution
from nfl_dfs.research import corpus_r6_full_union_grade_release_v1 as grade_release
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as freeze
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading
from nfl_dfs.research import corpus_r6_full_union_score_report_v1 as score_report


ATTRIBUTION_RELEASE_SCHEMA: Final = (
    "corpus-r6-full-union-attribution-release/v1"
)
ATTRIBUTION_OBJECT_DESCRIPTOR_SCHEMA: Final = (
    "corpus-r6-full-union-attribution-object-descriptor/v1"
)
PUBLICATION_MODE: Final = "create_once_root_last"
OUTPUT_BUCKET: Final = "nfl-predictions-503414-corpus-retrieval"
OUTPUT_NAMESPACE: Final = "research/corpus-r6-full-union-attributions"
_ROOT_FILENAME: Final = "attribution-release.json"
_OUTPUT_PREFIX = re.compile(
    rf"^gs://{re.escape(OUTPUT_BUCKET)}/{re.escape(OUTPUT_NAMESPACE)}/"
    r"(?P<run_id>[a-z0-9][a-z0-9-]{7,80})$"
)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], object]

_FALSE_AUTHORITY_FIELDS: Final = (
    "outcome_source_read",
    "outcome_snapshot_read",
    "additional_historical_outcome_read",
    "bigquery_client_constructed",
    "outcome_query_executed",
    "lineup_rescore_performed",
    "historical_scoring_licensed",
    "historical_retry_licensed",
    "historical_retune_licensed",
    "corpus_fill_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "promotion_authority",
    "decision_authority",
    "live_money_policy_authority",
    "causal_claims_licensed",
    "structure_only_validation_authority",
)

_DESCRIPTOR_FIELDS: Final = frozenset({
    "schema_version", "source_ordinal", "slate_id", "target_uri",
    "slate_attribution_identity", "slate_attribution_sha256",
    "slate_freeze_identity", "task_result_identity", "task_result_sha256",
    "slate_grade_identity", "slate_grade_sha256", "lineup_count",
    "scope_membership_count", "book_count", "selection_count",
    "slate_attribution_object_sha256",
})
_ROOT_FIELDS: Final = frozenset({
    "schema_version", "publication_mode", "target_uri", "run_id",
    "grade_completion_identity", "persisted_grade_root_identity",
    "panel_freeze_identity", "panel_freeze_sha256", "source_slate_count",
    "slate_attribution_objects", "slate_attribution_objects_sha256",
    "lineup_count", "scope_membership_count", "book_count",
    "selection_count", "reads_freeze_and_grade_artifacts_only",
    "uses_realized_outcomes", "no_rescore", "complete",
    "all_shard_identities_resolved_before_root_build",
    "every_shard_exact_reopened_and_predecessor_replayed",
    "root_create_once_requested_last", *_FALSE_AUTHORITY_FIELDS,
    "attribution_release_sha256",
})


class CorpusR6FullUnionAttributionReleaseV1Error(ValueError):
    """The generation-pinned attribution release failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6FullUnionAttributionReleaseV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionAttributionReleaseV1Error(str(exc)) from exc


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


def _identity(value: object, *, label: str) -> dict[str, object]:
    as_dict = getattr(value, "as_dict", None)
    if callable(as_dict):
        value = as_dict()
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionAttributionReleaseV1Error(str(exc)) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if frozenset(value) != expected:
        _fail(f"{label} fields differ")


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _digest(value.get(field), label=f"{label} SHA")
    expected = canonical_sha256({
        key: nested for key, nested in value.items() if key != field
    })
    if retained != expected:
        _fail(f"{label} self-hash differs")
    return retained


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    body[field] = canonical_sha256(body)
    return body


def _output_prefix(value: object) -> tuple[str, str]:
    if type(value) is not str:
        _fail("attribution output prefix must be one string")
    retained = value.rstrip("/")
    matched = _OUTPUT_PREFIX.fullmatch(retained)
    if matched is None or retained != value:
        _fail("attribution output prefix is outside the isolated namespace")
    return retained, matched.group("run_id")


def _root_prefix_from_identity(identity: Mapping[str, object]) -> tuple[str, str]:
    uri = str(identity["uri"])
    suffix = f"/{_ROOT_FILENAME}"
    if not uri.endswith(suffix):
        _fail("attribution release root URI differs")
    return _output_prefix(uri.removesuffix(suffix))


def _scoped_output_reader(*, read_exact: ReadExact, output_prefix: str) -> ReadExact:
    if not callable(read_exact):
        _fail("attribution exact reader differs")
    prefix = f"{output_prefix}/"

    def read_scoped(identity_value: Mapping[str, object]) -> bytes:
        retained = _identity(identity_value, label="attribution object identity")
        if not str(retained["uri"]).startswith(prefix):
            _fail("attribution object identity escapes the selected output prefix")
        return read_exact(retained)

    return read_scoped


def _identity_key(value: object, *, label: str) -> tuple[str, str, str, int]:
    identity = _identity(value, label=label)
    return (
        str(identity["uri"]), str(identity["generation"]),
        str(identity["sha256"]), int(identity["bytes"]),
    )


def _freeze_allowlist_from_untrusted_root(
    root: Mapping[str, object],
    *,
    root_identity: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    """Resolve only deterministic freeze roles before following any identity."""
    retained_root_identity = _identity(
        root_identity, label="panel freeze root identity"
    )
    root_uri = str(retained_root_identity["uri"])
    suffix = "/panel-freeze.json"
    if not root_uri.endswith(suffix) or root.get("target_uri") != root_uri:
        _fail("panel freeze root target differs before dependency reads")
    prefix = root_uri.removesuffix(suffix)
    retained_hash = _digest(
        root.get("panel_freeze_sha256"), label="panel freeze SHA"
    )
    if retained_hash != batch.canonical_sha256({
        key: nested for key, nested in root.items()
        if key != "panel_freeze_sha256"
    }):
        _fail("panel freeze self-hash differs before dependency reads")
    manifest_identity = _identity(
        root.get("manifest_identity"), label="panel execution manifest identity"
    )
    panel_index_identity = _identity(
        root.get("panel_index_identity"), label="fixed panel index identity"
    )
    if manifest_identity["uri"] != f"{prefix}/execution-manifest.json":
        _fail("panel execution manifest escapes the freeze-run prefix")
    rows = [
        _mapping(raw, label=f"panel slate descriptor[{ordinal}]")
        for ordinal, raw in enumerate(
            _sequence(root.get("slate_freezes"), label="panel slate descriptors")
        )
    ]
    if len(rows) != grading.SOURCE_SLATE_COUNT:
        _fail("panel freeze descriptor census differs before dependency reads")
    identities = [
        retained_root_identity, manifest_identity, panel_index_identity,
    ]
    for source_ordinal, row in enumerate(rows):
        slate_id = row.get("slate_id")
        if (
            row.get("source_ordinal") != source_ordinal
            or type(slate_id) is not str
            or not slate_id
        ):
            _fail(f"panel freeze descriptor[{source_ordinal}] coordinate differs")
        leaf_identity = _identity(
            row.get("slate_freeze_identity"),
            label=f"slate freeze identity[{source_ordinal}]",
        )
        task_identity = _identity(
            row.get("task_result_identity"),
            label=f"task-result identity[{source_ordinal}]",
        )
        slate_prefix = f"{prefix}/slates/{source_ordinal:02d}-{slate_id}"
        if (
            leaf_identity["uri"] != f"{slate_prefix}/slate-freeze.json"
            or task_identity["uri"] != f"{slate_prefix}/task-result.json"
        ):
            _fail(
                f"panel freeze descriptor[{source_ordinal}] dependency URI differs"
            )
        identities.extend((leaf_identity, task_identity))
    keys = [
        _identity_key(value, label="allowed freeze identity")
        for value in identities
    ]
    if len(keys) != len(set(keys)):
        _fail("allowed freeze dependency identity repeats")
    return tuple(identities)


def _scoped_freeze_reader(
    *,
    read_exact: ReadExact,
    allowed_identities: Sequence[Mapping[str, object]],
) -> ReadExact:
    if not callable(read_exact):
        _fail("freeze exact reader differs")
    allowed = {
        _identity_key(value, label="allowed freeze identity")
        for value in allowed_identities
    }
    if len(allowed) != 3 + 2 * grading.SOURCE_SLATE_COUNT:
        _fail("freeze exact-reader allowlist census differs")

    def read_scoped(identity_value: Mapping[str, object]) -> bytes:
        retained = _identity(
            identity_value, label="requested freeze dependency identity"
        )
        if _identity_key(retained, label="requested freeze identity") not in allowed:
            _fail("freeze dependency identity is outside the exact allowlist")
        return read_exact(retained)

    return read_scoped


def _exact_json(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    retained = _identity(identity_value, label=f"{label} identity")
    try:
        raw = read_exact(retained)
    except CorpusR6FullUnionAttributionReleaseV1Error:
        raise
    except Exception as exc:
        raise CorpusR6FullUnionAttributionReleaseV1Error(
            f"{label} exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != retained["bytes"]
        or sha256(raw).hexdigest() != retained["sha256"]
    ):
        _fail(f"{label} content identity differs")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6FullUnionAttributionReleaseV1Error(
            f"{label} is not canonical JSON"
        ) from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != raw:
        _fail(f"{label} canonical bytes differ")
    return value, retained


def _verify_published_json(
    value: object,
    *,
    target_uri: str,
    raw: bytes,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(value, label=f"{label} identity")
    if (
        identity["uri"] != target_uri
        or identity["bytes"] != len(raw)
        or identity["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} create-once identity differs")
    body, reopened_identity = _exact_json(
        identity, read_exact=read_exact, label=label
    )
    if reopened_identity != identity or canonical_json_bytes(body) != raw:
        _fail(f"{label} exact-reopened bytes differ")
    return body, identity


@dataclass(frozen=True)
class _UpstreamSourcesV1:
    grade_completion: dict[str, object]
    grade_completion_identity: dict[str, object]
    persisted_grade_root: dict[str, object]
    persisted_grade_root_identity: dict[str, object]
    logical_grade_root: dict[str, object]
    grade_shards: tuple[dict[str, object], ...]
    grade_shard_identities: tuple[dict[str, object], ...]
    panel_freeze: dict[str, object]
    panel_freeze_identity: dict[str, object]
    panel_slate_descriptors: tuple[dict[str, object], ...]
    freeze_allowed_identities: tuple[dict[str, object], ...] = ()
    prederived_validation_cache: dict[int, dict[str, object]] = field(
        default_factory=dict, compare=False, repr=False
    )


def _reopen_upstream_sources_v1(
    *,
    grade_completion_identity: object,
    grade_release_config: grade_release.FullUnionGradeReleaseConfigV1,
    read_exact: ReadExact,
) -> _UpstreamSourcesV1:
    """Open terminal grade/freeze artifacts without opening outcome artifacts."""
    completion_identity = _identity(
        grade_completion_identity, label="grade completion identity"
    )
    try:
        grade_prefix, uri_run_id = score_report._grade_run_prefix(  # noqa: SLF001
            completion_identity
        )
        config = grade_release.validate_grade_release_config_v1(
            grade_release_config
        )
        if (
            config.run_id != uri_run_id
            or config.output_root != grade_prefix
            or config.completion_uri != completion_identity["uri"]
        ):
            _fail("grade completion URI/runtime coordinate differs")
        grade_reader = score_report._scoped_reader(  # noqa: SLF001
            read_exact=read_exact, grade_run_prefix=grade_prefix
        )
        completion, reopened_completion_identity = score_report._exact_json(  # noqa: SLF001
            completion_identity,
            read_exact=grade_reader,
            label="grade completion",
        )
        completion, identities = score_report._validated_completion_before_root(  # noqa: SLF001
            completion=completion,
            completion_identity=reopened_completion_identity,
            config=config,
            grade_run_prefix=grade_prefix,
        )
        grade_root_identity = identities["persisted_grade_root_identity"]
        grade_root, _ = score_report._exact_json(  # noqa: SLF001
            grade_root_identity,
            read_exact=grade_reader,
            label="persisted grade root",
        )
        score_report._validate_exact_strategy_registry_before_shards(  # noqa: SLF001
            grade_root
        )
        (
            retained_grade_root,
            reopened_grade_root_identity,
            logical_grade_root,
            grade_shards,
            grade_shard_identities,
            retained_grade_prefix,
        ) = grading._validate_persisted_root_structure_v1(  # noqa: SLF001
            grade_root,
            identity=grade_root_identity,
            read_exact=grade_reader,
        )
        if retained_grade_prefix != grade_prefix:
            _fail("persisted grade output prefix differs")
        score_report._validate_completion_root_binding(  # noqa: SLF001
            completion=completion,
            identities=identities,
            persisted_root=retained_grade_root,
            persisted_root_identity=reopened_grade_root_identity,
            logical_root=logical_grade_root,
            shard_count=len(grade_shards),
        )
        untrusted_panel, untrusted_panel_identity = _exact_json(
            identities["panel_freeze_identity"],
            read_exact=read_exact,
            label="panel freeze root preflight",
        )
        freeze_allowed_identities = _freeze_allowlist_from_untrusted_root(
            untrusted_panel, root_identity=untrusted_panel_identity
        )
        freeze_reader = _scoped_freeze_reader(
            read_exact=read_exact,
            allowed_identities=freeze_allowed_identities,
        )
        panel, panel_identity = freeze.reopen_panel_freeze_v1(
            identities["panel_freeze_identity"], read_exact=freeze_reader
        )
    except CorpusR6FullUnionAttributionReleaseV1Error:
        raise
    except Exception as exc:
        raise CorpusR6FullUnionAttributionReleaseV1Error(
            f"terminal grade/freeze exact reopen failed: {exc}"
        ) from exc

    panel_rows = tuple(
        _mapping(raw, label=f"panel slate descriptor[{ordinal}]")
        for ordinal, raw in enumerate(
            _sequence(panel.get("slate_freezes"), label="panel slate descriptors")
        )
    )
    if (
        panel_identity != identities["panel_freeze_identity"]
        or logical_grade_root.get("panel_freeze_identity") != panel_identity
        or logical_grade_root.get("panel_freeze_sha256")
        != panel.get("panel_freeze_sha256")
        or len(panel_rows) != grading.SOURCE_SLATE_COUNT
        or len(grade_shards) != grading.SOURCE_SLATE_COUNT
        or len(grade_shard_identities) != grading.SOURCE_SLATE_COUNT
    ):
        _fail("terminal grade/panel root binding differs")
    for source_ordinal, (panel_row, shard, shard_identity) in enumerate(
        zip(panel_rows, grade_shards, grade_shard_identities, strict=True)
    ):
        if (
            panel_row.get("source_ordinal") != source_ordinal
            or shard.get("source_ordinal") != source_ordinal
            or panel_row.get("slate_id") != shard.get("slate_id")
            or shard.get("panel_freeze_identity") != panel_identity
            or shard.get("slate_freeze_identity")
            != panel_row.get("slate_freeze_identity")
            or shard.get("task_result_identity")
            != panel_row.get("task_result_identity")
            or shard.get("task_result_sha256")
            != panel_row.get("task_result_sha256")
            or _identity(
                shard_identity, label=f"grade shard identity[{source_ordinal}]"
            ) != shard_identity
        ):
            _fail(f"grade/panel slate binding[{source_ordinal}] differs")
    return _UpstreamSourcesV1(
        grade_completion=completion,
        grade_completion_identity=reopened_completion_identity,
        persisted_grade_root=retained_grade_root,
        persisted_grade_root_identity=reopened_grade_root_identity,
        logical_grade_root=logical_grade_root,
        grade_shards=tuple(grade_shards),
        grade_shard_identities=tuple(grade_shard_identities),
        panel_freeze=panel,
        panel_freeze_identity=panel_identity,
        panel_slate_descriptors=panel_rows,
        freeze_allowed_identities=freeze_allowed_identities,
    )


def _derive_slate_attribution_v1(
    *,
    sources: _UpstreamSourcesV1,
    source_ordinal: int,
    read_exact: ReadExact,
) -> dict[str, object]:
    ordinal = _integer(source_ordinal, label="source ordinal")
    if ordinal >= grading.SOURCE_SLATE_COUNT:
        _fail("source ordinal is outside the 54-slate panel")
    descriptor = sources.panel_slate_descriptors[ordinal]
    grade_shard = sources.grade_shards[ordinal]
    grade_identity = sources.grade_shard_identities[ordinal]
    freeze_reader = _scoped_freeze_reader(
        read_exact=read_exact,
        allowed_identities=sources.freeze_allowed_identities,
    )
    try:
        leaf, _manifest, _panel, _members, task_result, leaf_identity = (
            freeze.reopen_slate_freeze_v1(
                descriptor["slate_freeze_identity"], read_exact=freeze_reader
            )
        )
    except Exception as exc:
        raise CorpusR6FullUnionAttributionReleaseV1Error(
            f"slate freeze[{ordinal}] exact reopen failed: {exc}"
        ) from exc
    task_identity = _identity(
        leaf.get("task_result_identity"), label=f"task result identity[{ordinal}]"
    )
    slate_id = str(descriptor.get("slate_id"))
    if (
        leaf_identity != descriptor.get("slate_freeze_identity")
        or leaf.get("source_ordinal") != ordinal
        or leaf.get("slate_id") != slate_id
        or task_identity != descriptor.get("task_result_identity")
        or task_result.get("task_result_sha256")
        != descriptor.get("task_result_sha256")
        or grade_shard.get("source_ordinal") != ordinal
        or grade_shard.get("slate_id") != slate_id
    ):
        _fail(f"slate attribution upstream coordinate[{ordinal}] differs")
    try:
        return attribution.build_slate_attribution_v1(
            source_ordinal=ordinal,
            slate_id=slate_id,
            task_result=task_result,
            realized_slate_grade=grade_shard,
            panel_freeze_identity=sources.panel_freeze_identity,
            slate_freeze_identity=leaf_identity,
            task_result_identity=task_identity,
            slate_grade_identity=grade_identity,
            candidate_provenance=None,
        )
    except attribution.CorpusR6FullUnionAttributionV1Error as exc:
        raise CorpusR6FullUnionAttributionReleaseV1Error(
            f"slate attribution[{ordinal}] derivation failed: {exc}"
        ) from exc


def _validate_slate_against_sources_v1(
    value: object,
    *,
    sources: _UpstreamSourcesV1,
    source_ordinal: int,
    read_exact: ReadExact,
) -> dict[str, object]:
    try:
        observed = attribution.validate_slate_attribution_structure_v1(value)
    except attribution.CorpusR6FullUnionAttributionV1Error as exc:
        raise CorpusR6FullUnionAttributionReleaseV1Error(str(exc)) from exc
    # During publication, the immediately preceding exact derivation is
    # supplied through a one-item cache and removed here.  This preserves full
    # structural/coordinate validation without parsing the ~19 MB task
    # envelope twice.  An independent authoritative reopen has an empty cache
    # and therefore replays the predecessors from scratch.
    expected = sources.prederived_validation_cache.pop(source_ordinal, None)
    if expected is None:
        expected = _derive_slate_attribution_v1(
            sources=sources,
            source_ordinal=source_ordinal,
            read_exact=read_exact,
        )
    if canonical_json_bytes(observed) != canonical_json_bytes(expected):
        _fail(
            f"slate attribution[{source_ordinal}] canonical predecessor replay differs"
        )
    return expected


def _descriptor_from_shard(
    shard: Mapping[str, object],
    *,
    identity: Mapping[str, object],
    target_uri: str,
) -> dict[str, object]:
    source_ordinal = _integer(shard.get("source_ordinal"), label="source ordinal")
    normalized_identity = _identity(
        identity, label=f"slate attribution identity[{source_ordinal}]"
    )
    if normalized_identity["uri"] != target_uri:
        _fail("slate attribution descriptor target differs")
    return _with_hash({
        "schema_version": ATTRIBUTION_OBJECT_DESCRIPTOR_SCHEMA,
        "source_ordinal": source_ordinal,
        "slate_id": shard["slate_id"],
        "target_uri": target_uri,
        "slate_attribution_identity": normalized_identity,
        "slate_attribution_sha256": shard["slate_attribution_sha256"],
        "slate_freeze_identity": shard["slate_freeze_identity"],
        "task_result_identity": shard["task_result_identity"],
        "task_result_sha256": shard["task_result_sha256"],
        "slate_grade_identity": shard["slate_grade_identity"],
        "slate_grade_sha256": shard["slate_grade_sha256"],
        "lineup_count": shard["lineup_count"],
        "scope_membership_count": shard["scope_membership_count"],
        "book_count": shard["book_count"],
        "selection_count": shard["selection_count"],
    }, field="slate_attribution_object_sha256")


def _build_root_v1(
    *,
    output_prefix: str,
    run_id: str,
    sources: _UpstreamSourcesV1,
    descriptors: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    rows = [dict(value) for value in descriptors]
    if len(rows) != grading.SOURCE_SLATE_COUNT:
        _fail("attribution root requires exactly 54 shard descriptors")
    body: dict[str, object] = {
        "schema_version": ATTRIBUTION_RELEASE_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "target_uri": f"{output_prefix}/{_ROOT_FILENAME}",
        "run_id": run_id,
        "grade_completion_identity": sources.grade_completion_identity,
        "persisted_grade_root_identity": sources.persisted_grade_root_identity,
        "panel_freeze_identity": sources.panel_freeze_identity,
        "panel_freeze_sha256": sources.panel_freeze["panel_freeze_sha256"],
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "slate_attribution_objects": rows,
        "slate_attribution_objects_sha256": canonical_sha256(rows),
        "lineup_count": sum(int(row["lineup_count"]) for row in rows),
        "scope_membership_count": sum(
            int(row["scope_membership_count"]) for row in rows
        ),
        "book_count": sum(int(row["book_count"]) for row in rows),
        "selection_count": sum(int(row["selection_count"]) for row in rows),
        "reads_freeze_and_grade_artifacts_only": True,
        "uses_realized_outcomes": True,
        "no_rescore": True,
        "complete": True,
        "all_shard_identities_resolved_before_root_build": True,
        "every_shard_exact_reopened_and_predecessor_replayed": True,
        "root_create_once_requested_last": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    return _with_hash(body, field="attribution_release_sha256")


def validate_attribution_release_structure_v1(value: object) -> dict[str, object]:
    """Validate root/descriptor structure only; this grants no authority."""
    root = _mapping(value, label="attribution release root")
    _exact_keys(root, _ROOT_FIELDS, label="attribution release root")
    _self_hash(
        root,
        field="attribution_release_sha256",
        label="attribution release root",
    )
    target_uri = root.get("target_uri")
    if type(target_uri) is not str:
        _fail("attribution release target URI differs")
    prefix, run_id = _root_prefix_from_identity({
        "uri": target_uri,
        "generation": "1",
        "sha256": "0" * 64,
        "bytes": 1,
    })
    for field in (
        "grade_completion_identity", "persisted_grade_root_identity",
        "panel_freeze_identity",
    ):
        _identity(root.get(field), label=field)
    if (
        root.get("schema_version") != ATTRIBUTION_RELEASE_SCHEMA
        or root.get("publication_mode") != PUBLICATION_MODE
        or root.get("run_id") != run_id
        or root.get("source_slate_count") != grading.SOURCE_SLATE_COUNT
        or root.get("reads_freeze_and_grade_artifacts_only") is not True
        or root.get("uses_realized_outcomes") is not True
        or root.get("no_rescore") is not True
        or root.get("complete") is not True
        or root.get("all_shard_identities_resolved_before_root_build") is not True
        or root.get("every_shard_exact_reopened_and_predecessor_replayed") is not True
        or root.get("root_create_once_requested_last") is not True
        or any(root.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("attribution release authority law differs")
    _digest(root.get("panel_freeze_sha256"), label="panel freeze SHA")
    rows = [
        _mapping(raw, label=f"attribution descriptor[{ordinal}]")
        for ordinal, raw in enumerate(
            _sequence(
                root.get("slate_attribution_objects"),
                label="attribution descriptors",
            )
        )
    ]
    if (
        len(rows) != grading.SOURCE_SLATE_COUNT
        or root.get("slate_attribution_objects_sha256") != canonical_sha256(rows)
    ):
        _fail("attribution descriptor census/hash differs")
    seen_identities: set[tuple[str, str, str, int]] = set()
    seen_slate_ids: set[str] = set()
    for source_ordinal, row in enumerate(rows):
        _exact_keys(row, _DESCRIPTOR_FIELDS, label="attribution descriptor")
        _self_hash(
            row,
            field="slate_attribution_object_sha256",
            label=f"attribution descriptor[{source_ordinal}]",
        )
        slate_id = row.get("slate_id")
        identity = _identity(
            row.get("slate_attribution_identity"),
            label=f"attribution identity[{source_ordinal}]",
        )
        expected_uri = (
            f"{prefix}/slate-attributions/{source_ordinal:02d}-{slate_id}.json"
        )
        identity_key = (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )
        if (
            row.get("schema_version") != ATTRIBUTION_OBJECT_DESCRIPTOR_SCHEMA
            or row.get("source_ordinal") != source_ordinal
            or type(slate_id) is not str
            or not slate_id
            or slate_id in seen_slate_ids
            or row.get("target_uri") != expected_uri
            or identity["uri"] != expected_uri
            or identity_key in seen_identities
            or row.get("book_count") != grading.BOOKS_PER_SLATE
            or row.get("selection_count") != grading.BOOKS_PER_SLATE * 80
            or type(row.get("lineup_count")) is not int
            or int(row["lineup_count"]) < 80
            or row.get("scope_membership_count")
            != grading.SCOPES_PER_SLATE * int(row["lineup_count"])
        ):
            _fail(f"attribution descriptor[{source_ordinal}] differs")
        for field in (
            "slate_freeze_identity", "task_result_identity",
            "slate_grade_identity",
        ):
            _identity(row.get(field), label=f"descriptor {field}")
        for field in (
            "slate_attribution_sha256", "task_result_sha256",
            "slate_grade_sha256",
        ):
            _digest(row.get(field), label=f"descriptor {field}")
        seen_identities.add(identity_key)
        seen_slate_ids.add(slate_id)
    expected_totals = {
        "lineup_count": sum(int(row["lineup_count"]) for row in rows),
        "scope_membership_count": sum(
            int(row["scope_membership_count"]) for row in rows
        ),
        "book_count": sum(int(row["book_count"]) for row in rows),
        "selection_count": sum(int(row["selection_count"]) for row in rows),
    }
    if any(root.get(field) != expected for field, expected in expected_totals.items()):
        _fail("attribution release aggregate census differs")
    return root


def publish_r6_full_union_attribution_release_v1(
    *,
    grade_completion_identity: object,
    grade_release_config: grade_release.FullUnionGradeReleaseConfigV1,
    output_prefix: object,
    read_exact: ReadExact,
    publish_create_once: PublishCreateOnce,
) -> tuple[dict[str, object], dict[str, object]]:
    """Publish 54 fully replayed attribution shards and their root last."""
    prefix, run_id = _output_prefix(output_prefix)
    if not callable(read_exact) or not callable(publish_create_once):
        _fail("attribution read/publish boundary differs")
    sources = _reopen_upstream_sources_v1(
        grade_completion_identity=grade_completion_identity,
        grade_release_config=grade_release_config,
        read_exact=read_exact,
    )
    output_reader = _scoped_output_reader(
        read_exact=read_exact, output_prefix=prefix
    )
    descriptors: list[dict[str, object]] = []
    for source_ordinal in range(grading.SOURCE_SLATE_COUNT):
        derived = _derive_slate_attribution_v1(
            sources=sources,
            source_ordinal=source_ordinal,
            read_exact=read_exact,
        )
        sources.prederived_validation_cache[source_ordinal] = derived
        # Replay before the irreversible create-once boundary.  A derivation
        # defect must not poison a resumable prefix with an invalid shard.
        shard = _validate_slate_against_sources_v1(
            derived,
            sources=sources,
            source_ordinal=source_ordinal,
            read_exact=read_exact,
        )
        target_uri = (
            f"{prefix}/slate-attributions/"
            f"{source_ordinal:02d}-{shard['slate_id']}.json"
        )
        raw = canonical_json_bytes(shard)
        published = publish_create_once(target_uri, raw)
        reopened, identity = _verify_published_json(
            published,
            target_uri=target_uri,
            raw=raw,
            read_exact=output_reader,
            label=f"published slate attribution[{source_ordinal}]",
        )
        retained = reopened
        if canonical_json_bytes(retained) != raw:
            _fail(
                f"published slate attribution[{source_ordinal}] canonical "
                "derivation differs"
            )
        descriptors.append(_descriptor_from_shard(
            retained, identity=identity, target_uri=target_uri
        ))
    if sources.prederived_validation_cache:
        _fail("attribution prepublication validation cache did not drain")
    root = _build_root_v1(
        output_prefix=prefix,
        run_id=run_id,
        sources=sources,
        descriptors=descriptors,
    )
    validate_attribution_release_structure_v1(root)
    target_uri = str(root["target_uri"])
    raw = canonical_json_bytes(root)
    published = publish_create_once(target_uri, raw)
    reopened, identity = _verify_published_json(
        published,
        target_uri=target_uri,
        raw=raw,
        read_exact=output_reader,
        label="published attribution release root",
    )
    retained = validate_attribution_release_structure_v1(reopened)
    if canonical_json_bytes(retained) != raw:
        _fail("published attribution release root canonical replay differs")
    return retained, identity


def reopen_r6_full_union_attribution_release_v1(
    root_identity: object,
    *,
    grade_completion_identity: object,
    grade_release_config: grade_release.FullUnionGradeReleaseConfigV1,
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    """Exact-open and predecessor-replay every shard one at a time."""
    retained_root_identity = _identity(
        root_identity, label="attribution release root identity"
    )
    prefix, _run_id = _root_prefix_from_identity(retained_root_identity)
    output_reader = _scoped_output_reader(
        read_exact=read_exact, output_prefix=prefix
    )
    root, reopened_root_identity = _exact_json(
        retained_root_identity,
        read_exact=output_reader,
        label="attribution release root",
    )
    retained_root = validate_attribution_release_structure_v1(root)
    if retained_root.get("target_uri") != reopened_root_identity["uri"]:
        _fail("attribution release root outer target differs")
    sources = _reopen_upstream_sources_v1(
        grade_completion_identity=grade_completion_identity,
        grade_release_config=grade_release_config,
        read_exact=read_exact,
    )
    if (
        retained_root.get("grade_completion_identity")
        != sources.grade_completion_identity
        or retained_root.get("persisted_grade_root_identity")
        != sources.persisted_grade_root_identity
        or retained_root.get("panel_freeze_identity")
        != sources.panel_freeze_identity
        or retained_root.get("panel_freeze_sha256")
        != sources.panel_freeze.get("panel_freeze_sha256")
    ):
        _fail("attribution release root upstream binding differs")
    expected_descriptors: list[dict[str, object]] = []
    rows = _sequence(
        retained_root.get("slate_attribution_objects"),
        label="attribution descriptors",
    )
    for source_ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"attribution descriptor[{source_ordinal}]")
        shard, shard_identity = _exact_json(
            row["slate_attribution_identity"],
            read_exact=output_reader,
            label=f"slate attribution[{source_ordinal}]",
        )
        retained_shard = _validate_slate_against_sources_v1(
            shard,
            sources=sources,
            source_ordinal=source_ordinal,
            read_exact=read_exact,
        )
        expected_row = _descriptor_from_shard(
            retained_shard,
            identity=shard_identity,
            target_uri=str(row["target_uri"]),
        )
        if canonical_json_bytes(row) != canonical_json_bytes(expected_row):
            _fail(f"attribution descriptor[{source_ordinal}] body binding differs")
        expected_descriptors.append(expected_row)
    expected_root = _build_root_v1(
        output_prefix=prefix,
        run_id=str(retained_root["run_id"]),
        sources=sources,
        descriptors=expected_descriptors,
    )
    if canonical_json_bytes(retained_root) != canonical_json_bytes(expected_root):
        _fail("attribution release root canonical predecessor replay differs")
    return retained_root, reopened_root_identity


__all__ = [
    "ATTRIBUTION_OBJECT_DESCRIPTOR_SCHEMA",
    "ATTRIBUTION_RELEASE_SCHEMA",
    "CorpusR6FullUnionAttributionReleaseV1Error",
    "OUTPUT_BUCKET",
    "OUTPUT_NAMESPACE",
    "PUBLICATION_MODE",
    "canonical_json_bytes",
    "canonical_sha256",
    "publish_r6_full_union_attribution_release_v1",
    "reopen_r6_full_union_attribution_release_v1",
    "validate_attribution_release_structure_v1",
]
