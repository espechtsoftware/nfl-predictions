"""Hermetic adversarial tests for the R6 attribution root-last release.

The release mechanics are exercised at their exact 54-slate census while the
private upstream/scientific seams are replaced with tiny deterministic
fixtures.  No outcome source, cloud object, score artifact, or graph is read.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import inspect
from typing import Any

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_attribution_release_v1 as release
from nfl_dfs.research import corpus_r6_full_union_attribution_v1 as attribution
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading
from tests import test_corpus_r6_full_union_grade_release_v1 as grade_fixture


_OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-corpus-retrieval/"
    "research/corpus-r6-full-union-attributions/synthetic-attribution-v1"
)
_ROOT_URI = f"{_OUTPUT_PREFIX}/attribution-release.json"

_FALSE_AUTHORITY_FIELDS = (
    "outcome_source_read",
    "additional_historical_outcome_read",
    "bigquery_client_constructed",
    "outcome_query_executed",
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
)


def _sha(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _rehash(value: dict[str, object], field: str) -> None:
    value.pop(field, None)
    value[field] = release.canonical_sha256(value)


def _identity(uri: str, label: str, *, generation: str = "1") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _sha(f"identity:{label}:{generation}"),
        "bytes": 1,
    }


def _freeze_root_fixture() -> tuple[
    dict[str, object], dict[str, object], tuple[dict[str, object], ...]
]:
    """Build the untrusted-but-canonical metadata needed for an exact allowlist."""
    prefix = "gs://synthetic-r6/freeze-run-v1"
    rows: list[dict[str, object]] = []
    for source_ordinal in range(grading.SOURCE_SLATE_COUNT):
        slate_id = _slate_id(source_ordinal)
        slate_prefix = f"{prefix}/slates/{source_ordinal:02d}-{slate_id}"
        rows.append({
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "slate_freeze_identity": _identity(
                f"{slate_prefix}/slate-freeze.json",
                f"allowlisted-slate-freeze-{source_ordinal}",
            ),
            "task_result_identity": _identity(
                f"{slate_prefix}/task-result.json",
                f"allowlisted-task-result-{source_ordinal}",
            ),
        })
    root: dict[str, object] = {
        "target_uri": f"{prefix}/panel-freeze.json",
        "manifest_identity": _identity(
            f"{prefix}/execution-manifest.json", "allowlisted-manifest"
        ),
        "panel_index_identity": _identity(
            "gs://synthetic-r6/fixed-panel-index.json",
            "allowlisted-fixed-panel-index",
        ),
        "slate_freezes": rows,
    }
    root["panel_freeze_sha256"] = batch.canonical_sha256(root)
    root_raw = batch.canonical_json_bytes(root)
    root_identity = {
        "uri": root["target_uri"],
        "generation": "17",
        "sha256": sha256(root_raw).hexdigest(),
        "bytes": len(root_raw),
    }
    allowlist = release._freeze_allowlist_from_untrusted_root(
        root, root_identity=root_identity
    )
    return root, root_identity, allowlist


class _MemoryStore:
    """Versioned exact-read store with create-or-exact-equal callback semantics."""

    def __init__(self) -> None:
        self.generation = 0
        self.values: dict[tuple[str, str, str, int], bytes] = {}
        self.current: dict[str, tuple[dict[str, object], bytes]] = {}
        self.created_order: list[str] = []
        self.publish_attempts: list[str] = []
        self.read_identities: list[dict[str, object]] = []

    @staticmethod
    def _key(identity: object) -> tuple[str, str, str, int]:
        row = dict(identity)  # type: ignore[arg-type]
        return (
            str(row["uri"]),
            str(row["generation"]),
            str(row["sha256"]),
            int(row["bytes"]),
        )

    def read_exact(self, identity: object) -> bytes:
        retained = dict(identity)  # type: ignore[arg-type]
        self.read_identities.append(retained)
        return self.values[self._key(retained)]

    def publish_create_once(self, uri: str, raw: bytes) -> dict[str, object]:
        self.publish_attempts.append(uri)
        existing = self.current.get(uri)
        if existing is not None:
            if existing[1] != raw:
                raise RuntimeError("create-once collision contains different bytes")
            return dict(existing[0])
        return self.force_generation(uri, raw)

    def force_generation(self, uri: str, raw: bytes) -> dict[str, object]:
        """Install another version while retaining all prior exact generations."""
        self.generation += 1
        identity = {
            "uri": uri,
            "generation": str(self.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.values[self._key(identity)] = bytes(raw)
        self.current[uri] = (dict(identity), bytes(raw))
        self.created_order.append(uri)
        return identity

    def corrupt_exact(self, identity: object, raw: bytes) -> None:
        self.values[self._key(identity)] = bytes(raw)


def _slate_id(source_ordinal: int) -> str:
    return f"{2020 + source_ordinal // 18}-w{source_ordinal % 18 + 1:02d}"


def _synthetic_sources() -> Any:
    panel_identity = _identity(
        "gs://synthetic-r6/panel-freeze.json", "panel-freeze"
    )
    grade_completion_identity = _identity(
        "gs://synthetic-r6/grade-completion.json", "grade-completion"
    )
    grade_root_identity = _identity(
        "gs://synthetic-r6/realized-grade-root.json", "grade-root"
    )
    grade_shards: list[dict[str, object]] = []
    grade_identities: list[dict[str, object]] = []
    panel_descriptors: list[dict[str, object]] = []
    for source_ordinal in range(grading.SOURCE_SLATE_COUNT):
        slate_id = _slate_id(source_ordinal)
        grade_identity = _identity(
            f"gs://synthetic-r6/slate-grades/{source_ordinal:02d}-{slate_id}.json",
            f"slate-grade-{source_ordinal}",
        )
        slate_freeze_identity = _identity(
            f"gs://synthetic-r6/slate-freezes/{source_ordinal:02d}-{slate_id}.json",
            f"slate-freeze-{source_ordinal}",
        )
        task_result_identity = _identity(
            f"gs://synthetic-r6/task-results/{source_ordinal:02d}-{slate_id}.json",
            f"task-result-{source_ordinal}",
        )
        grade_shards.append({
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "panel_freeze_identity": panel_identity,
            "slate_freeze_identity": slate_freeze_identity,
            "task_result_identity": task_result_identity,
            "task_result_sha256": _sha(f"task-result-{source_ordinal}"),
            "slate_grade_sha256": _sha(f"slate-grade-{source_ordinal}"),
            "complete": True,
        })
        grade_identities.append(grade_identity)
        panel_descriptors.append({
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "slate_freeze_identity": slate_freeze_identity,
            "task_result_identity": task_result_identity,
            "task_result_sha256": _sha(f"task-result-{source_ordinal}"),
        })

    logical_grade_root = {
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "realized_grade_sha256": _sha("logical-grade-root"),
        "complete": True,
    }
    persisted_grade_root = {
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "slate_grade_objects": [
            {
                "source_ordinal": source_ordinal,
                "slate_id": _slate_id(source_ordinal),
                "slate_grade_identity": grade_identities[source_ordinal],
            }
            for source_ordinal in range(grading.SOURCE_SLATE_COUNT)
        ],
        "logical_grade_root": logical_grade_root,
        "persisted_grade_root_sha256": _sha("persisted-grade-root"),
    }
    panel_freeze = {
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "panel_freeze_sha256": _sha("panel-freeze"),
        "slate_freezes": panel_descriptors,
        "complete": True,
    }
    grade_completion = {
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "slate_grade_object_count": grading.SOURCE_SLATE_COUNT,
        "panel_freeze_identity": panel_identity,
        "persisted_grade_root_identity": grade_root_identity,
        "grade_completion_sha256": _sha("grade-completion"),
        "complete": True,
    }
    return release._UpstreamSourcesV1(
        grade_completion=grade_completion,
        grade_completion_identity=grade_completion_identity,
        persisted_grade_root=persisted_grade_root,
        persisted_grade_root_identity=grade_root_identity,
        logical_grade_root=logical_grade_root,
        grade_shards=tuple(grade_shards),
        grade_shard_identities=tuple(grade_identities),
        panel_freeze=panel_freeze,
        panel_freeze_identity=panel_identity,
        panel_slate_descriptors=tuple(panel_descriptors),
    )


def _synthetic_attribution(sources: Any, source_ordinal: int) -> dict[str, object]:
    grade = sources.grade_shards[source_ordinal]
    panel_row = sources.panel_slate_descriptors[source_ordinal]
    empty_sha = attribution.canonical_sha256([])
    body: dict[str, object] = {
        "schema_version": attribution.SLATE_ATTRIBUTION_SCHEMA,
        "source_ordinal": source_ordinal,
        "slate_id": grade["slate_id"],
        "panel_freeze_identity": sources.panel_freeze_identity,
        "slate_freeze_identity": panel_row["slate_freeze_identity"],
        "task_result_identity": panel_row["task_result_identity"],
        "task_result_sha256": panel_row["task_result_sha256"],
        "slate_grade_identity": sources.grade_shard_identities[source_ordinal],
        "slate_grade_sha256": grade["slate_grade_sha256"],
        "candidate_provenance_sha256": _sha(
            f"candidate-provenance-{source_ordinal}"
        ),
        "candidate_provenance_resolution": (
            attribution.CANDIDATE_PROVENANCE_RESOLUTION
        ),
        "exact_generation_occurrence_rows_available": False,
        "player_realized_contributions_available": False,
        "point_in_time_player_traits_attached": False,
        "thresholds_dk": list(grading.THRESHOLDS_DK),
        "lineup_count": 84,
        "lineup_rows": [],
        "lineup_rows_sha256": empty_sha,
        "scope_membership_count": 6 * 84,
        "scope_membership_rows": [],
        "scope_membership_rows_sha256": empty_sha,
        "book_count": 48,
        "book_rows": [],
        "book_rows_sha256": empty_sha,
        "selection_count": 48 * 80,
        "selection_rows": [],
        "selection_rows_sha256": empty_sha,
        "contest_metrics": {
            "availability": "unavailable",
            "reason": attribution.CONTEST_UNAVAILABLE_REASON,
            "rank": None,
            "roi_micro_usd": None,
        },
        "fill_effect_interpretation": "descriptive-only-pooled-multi-arm",
        "uses_realized_outcomes": True,
        "no_rescore": True,
        "projected_from_persisted_union_score_lookup": True,
        "complete": True,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["slate_attribution_sha256"] = attribution.canonical_sha256(body)
    return body


@dataclass
class _SeamTrace:
    opened: int = 0
    derived_ordinals: list[int] | None = None
    validated_ordinals: list[int] | None = None

    def __post_init__(self) -> None:
        self.derived_ordinals = []
        self.validated_ordinals = []


def _install_scientific_seams(
    monkeypatch: pytest.MonkeyPatch,
    sources: Any,
    *,
    mutate_derived: Callable[[dict[str, object], int], None] | None = None,
) -> _SeamTrace:
    trace = _SeamTrace()

    def reopen_sources(**kwargs: object) -> Any:
        del kwargs
        trace.opened += 1
        return sources

    def derive(*, sources: Any, source_ordinal: int, read_exact: object) -> dict[str, object]:
        del read_exact
        assert sources is not None
        assert trace.derived_ordinals is not None
        trace.derived_ordinals.append(source_ordinal)
        value = _synthetic_attribution(sources, source_ordinal)
        if mutate_derived is not None:
            mutate_derived(value, source_ordinal)
            value.pop("slate_attribution_sha256", None)
            value["slate_attribution_sha256"] = attribution.canonical_sha256(value)
        return value

    def validate(
        value: object,
        *,
        sources: Any,
        source_ordinal: int,
        read_exact: object,
    ) -> dict[str, object]:
        del read_exact
        sources.prederived_validation_cache.pop(source_ordinal, None)
        assert trace.validated_ordinals is not None
        trace.validated_ordinals.append(source_ordinal)
        expected = _synthetic_attribution(sources, source_ordinal)
        if attribution.canonical_json_bytes(value) != (
            attribution.canonical_json_bytes(expected)
        ):
            raise release.CorpusR6FullUnionAttributionReleaseV1Error(
                "slate attribution does not fully replay from pinned sources"
            )
        return expected

    monkeypatch.setattr(release, "_reopen_upstream_sources_v1", reopen_sources)
    monkeypatch.setattr(release, "_derive_slate_attribution_v1", derive)
    monkeypatch.setattr(
        release, "_validate_slate_against_sources_v1", validate
    )
    return trace


def _publish(
    store: _MemoryStore,
    sources: Any,
    *,
    publish_create_once: Callable[[str, bytes], Mapping[str, object]] | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    return release.publish_r6_full_union_attribution_release_v1(
        grade_completion_identity=sources.grade_completion_identity,
        grade_release_config=grade_fixture._config(enabled=True),
        output_prefix=_OUTPUT_PREFIX,
        read_exact=store.read_exact,
        publish_create_once=(
            store.publish_create_once
            if publish_create_once is None
            else publish_create_once
        ),
    )


def _reopen(
    store: _MemoryStore,
    sources: Any,
    root_identity: object,
) -> tuple[dict[str, object], dict[str, object]]:
    return release.reopen_r6_full_union_attribution_release_v1(
        root_identity,
        grade_completion_identity=sources.grade_completion_identity,
        grade_release_config=grade_fixture._config(enabled=True),
        read_exact=store.read_exact,
    )


@pytest.mark.parametrize("escaped_role", ["slate", "task"])
def test_canonical_panel_dependency_escape_is_rejected_before_following(
    escaped_role: str,
) -> None:
    root, root_identity, _ = _freeze_root_fixture()
    changed = deepcopy(root)
    rows = changed["slate_freezes"]
    assert isinstance(rows, list) and isinstance(rows[0], dict)
    field = (
        "slate_freeze_identity"
        if escaped_role == "slate"
        else "task_result_identity"
    )
    retained_identity = rows[0][field]
    assert isinstance(retained_identity, dict)
    retained_identity["uri"] = (
        "gs://nfl-predictions-503414-corpus-retrieval/"
        "research/corpus-r6-full-union-realized-grades/"
        f"fixture/{escaped_role}-outcome-snapshot.json"
    )
    _rehash(changed, "panel_freeze_sha256")
    raw = batch.canonical_json_bytes(changed)
    assert batch.parse_canonical_json_bytes(raw, label="untrusted panel") == changed
    changed_root_identity = {
        **root_identity,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    delegated_reads: list[dict[str, object]] = []

    with pytest.raises(
        release.CorpusR6FullUnionAttributionReleaseV1Error,
        match="dependency URI differs",
    ):
        release._freeze_allowlist_from_untrusted_root(
            changed, root_identity=changed_root_identity
        )

    # Allowlist construction has no delegated reader seam: the escaped
    # identity is rejected mechanically before it can become followable.
    assert delegated_reads == []


@pytest.mark.parametrize(
    "forbidden_name",
    ["outcome-snapshot", "realized-source", "historical-outcome-lease"],
)
def test_scoped_freeze_reader_denies_outcome_identity_before_delegate(
    forbidden_name: str,
) -> None:
    _, _, allowlist = _freeze_root_fixture()
    delegated_reads: list[dict[str, object]] = []

    def backing_reader(identity: Mapping[str, object]) -> bytes:
        delegated_reads.append(dict(identity))
        return b"must-not-be-read"

    scoped = release._scoped_freeze_reader(
        read_exact=backing_reader,
        allowed_identities=allowlist,
    )
    forbidden_identity = _identity(
        (
            "gs://nfl-predictions-503414-corpus-retrieval/"
            "research/corpus-r6-full-union-realized-grades/fixture/"
            f"{forbidden_name}.json"
        ),
        forbidden_name,
    )

    with pytest.raises(
        release.CorpusR6FullUnionAttributionReleaseV1Error,
        match="outside the exact allowlist",
    ):
        scoped(forbidden_identity)

    assert delegated_reads == []


def test_scoped_freeze_reader_allows_exactly_three_plus_108_identities() -> None:
    _, _, allowlist = _freeze_root_fixture()
    assert len(allowlist) == 3 + 2 * grading.SOURCE_SLATE_COUNT
    assert len({release._identity_key(row, label="test") for row in allowlist}) == (
        len(allowlist)
    )
    delegated_reads: list[dict[str, object]] = []

    def backing_reader(identity: Mapping[str, object]) -> bytes:
        delegated_reads.append(dict(identity))
        return b"allowlisted"

    scoped = release._scoped_freeze_reader(
        read_exact=backing_reader,
        allowed_identities=allowlist,
    )
    for identity in allowlist:
        assert scoped(identity) == b"allowlisted"
    assert delegated_reads == list(allowlist)

    generation_splice = dict(allowlist[-1])
    generation_splice["generation"] = "999999"
    with pytest.raises(
        release.CorpusR6FullUnionAttributionReleaseV1Error,
        match="outside the exact allowlist",
    ):
        scoped(generation_splice)
    assert delegated_reads == list(allowlist)


@pytest.mark.parametrize("census_drift", ["missing", "extra"])
def test_scoped_freeze_reader_rejects_nonexact_allowlist_census(
    census_drift: str,
) -> None:
    _, _, retained = _freeze_root_fixture()
    allowlist = list(retained)
    if census_drift == "missing":
        allowlist.pop()
    else:
        allowlist.append(_identity(
            "gs://synthetic-r6/freeze-run-v1/unregistered.json",
            "unregistered-freeze-dependency",
        ))
    delegated = False

    def backing_reader(identity: Mapping[str, object]) -> bytes:
        del identity
        nonlocal delegated
        delegated = True
        return b"must-not-be-read"

    with pytest.raises(
        release.CorpusR6FullUnionAttributionReleaseV1Error,
        match="allowlist census differs",
    ):
        release._scoped_freeze_reader(
            read_exact=backing_reader,
            allowed_identities=allowlist,
        )

    assert delegated is False


def test_public_publisher_has_no_caller_supplied_attribution_bypass() -> None:
    parameters = inspect.signature(
        release.publish_r6_full_union_attribution_release_v1
    ).parameters

    assert "slate_attributions" not in parameters
    assert "attributions" not in parameters
    assert set(parameters) == {
        "grade_completion_identity",
        "grade_release_config",
        "output_prefix",
        "read_exact",
        "publish_create_once",
    }


def test_identical_byte_resume_reuses_all_54_shards_and_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = _synthetic_sources()
    store = _MemoryStore()
    _install_scientific_seams(monkeypatch, sources)

    first, first_identity = _publish(store, sources)
    created_after_first = list(store.created_order)
    second, second_identity = _publish(store, sources)

    assert batch.canonical_json_bytes(second) == batch.canonical_json_bytes(first)
    assert second_identity == first_identity
    assert store.created_order == created_after_first
    assert len(store.created_order) == grading.SOURCE_SLATE_COUNT + 1
    assert store.created_order[-1] == _ROOT_URI
    assert len(store.publish_attempts) == 2 * (grading.SOURCE_SLATE_COUNT + 1)


def test_different_byte_collision_fails_before_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = _synthetic_sources()
    store = _MemoryStore()
    _install_scientific_seams(monkeypatch, sources)
    first_uri = (
        f"{_OUTPUT_PREFIX}/slate-attributions/00-{_slate_id(0)}.json"
    )
    store.force_generation(first_uri, b"different-existing-bytes")

    with pytest.raises(
        (RuntimeError, release.CorpusR6FullUnionAttributionReleaseV1Error),
        match="collision|different|create-once",
    ):
        _publish(store, sources)

    assert _ROOT_URI not in store.current


def test_root_is_absent_until_all_54_shards_fully_validate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = _synthetic_sources()
    store = _MemoryStore()

    def drift_last(value: dict[str, object], source_ordinal: int) -> None:
        if source_ordinal == grading.SOURCE_SLATE_COUNT - 1:
            value["slate_grade_identity"] = sources.grade_shard_identities[0]

    trace = _install_scientific_seams(
        monkeypatch, sources, mutate_derived=drift_last
    )

    with pytest.raises(
        release.CorpusR6FullUnionAttributionReleaseV1Error,
        match="fully replay|identity|slate attribution",
    ):
        _publish(store, sources)

    assert trace.validated_ordinals == list(range(grading.SOURCE_SLATE_COUNT))
    assert _ROOT_URI not in store.current
    # Replay occurs before create-once, so the invalid final shard cannot
    # poison the resumable prefix and the terminal root remains absent.
    assert len(store.created_order) == grading.SOURCE_SLATE_COUNT - 1


def test_reopen_uses_root_pinned_generation_not_new_uri_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = _synthetic_sources()
    store = _MemoryStore()
    _install_scientific_seams(monkeypatch, sources)
    root, root_identity = _publish(store, sources)
    first_uri = (
        f"{_OUTPUT_PREFIX}/slate-attributions/00-{_slate_id(0)}.json"
    )
    original_identity = dict(store.current[first_uri][0])
    newer_identity = store.force_generation(first_uri, b"newer-uri-head")
    store.read_identities.clear()

    reopened, reopened_identity = _reopen(store, sources, root_identity)

    assert reopened == root
    assert reopened_identity == root_identity
    assert original_identity in store.read_identities
    assert newer_identity not in store.read_identities


@pytest.mark.parametrize("drift", ["ordinal", "slate-identity", "grade-identity"])
def test_ordinal_or_upstream_identity_swap_is_rejected_before_root(
    monkeypatch: pytest.MonkeyPatch, drift: str,
) -> None:
    sources = _synthetic_sources()
    store = _MemoryStore()

    def mutate(value: dict[str, object], source_ordinal: int) -> None:
        if source_ordinal != 1:
            return
        if drift == "ordinal":
            value["source_ordinal"] = 0
        elif drift == "slate-identity":
            value["slate_freeze_identity"] = (
                sources.panel_slate_descriptors[0]["slate_freeze_identity"]
            )
        else:
            value["slate_grade_identity"] = sources.grade_shard_identities[0]

    _install_scientific_seams(monkeypatch, sources, mutate_derived=mutate)

    with pytest.raises(
        release.CorpusR6FullUnionAttributionReleaseV1Error,
        match="fully replay|identity|slate attribution",
    ):
        _publish(store, sources)

    assert _ROOT_URI not in store.current


def test_coherently_rehashed_root_ordinal_swap_fails_structure_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = _synthetic_sources()
    store = _MemoryStore()
    _install_scientific_seams(monkeypatch, sources)
    root, _ = _publish(store, sources)
    changed = deepcopy(root)
    rows = changed["slate_attribution_objects"]
    assert isinstance(rows, list)
    assert isinstance(rows[0], dict) and isinstance(rows[1], dict)
    rows[0]["source_ordinal"], rows[1]["source_ordinal"] = 1, 0
    _rehash(rows[0], "slate_attribution_object_sha256")
    _rehash(rows[1], "slate_attribution_object_sha256")
    changed["slate_attribution_objects_sha256"] = release.canonical_sha256(rows)
    _rehash(changed, "attribution_release_sha256")

    with pytest.raises(
        release.CorpusR6FullUnionAttributionReleaseV1Error,
        match="descriptor.*differs",
    ):
        release.validate_attribution_release_structure_v1(changed)


@pytest.mark.parametrize(
    "field",
    ["slate_freeze_identity", "task_result_identity", "slate_grade_identity"],
)
def test_structure_valid_upstream_identity_swap_fails_full_root_replay(
    monkeypatch: pytest.MonkeyPatch, field: str,
) -> None:
    sources = _synthetic_sources()
    store = _MemoryStore()
    _install_scientific_seams(monkeypatch, sources)
    root, _ = _publish(store, sources)
    changed = deepcopy(root)
    rows = changed["slate_attribution_objects"]
    assert isinstance(rows, list)
    assert isinstance(rows[0], dict) and isinstance(rows[1], dict)
    rows[0][field], rows[1][field] = rows[1][field], rows[0][field]
    _rehash(rows[0], "slate_attribution_object_sha256")
    _rehash(rows[1], "slate_attribution_object_sha256")
    changed["slate_attribution_objects_sha256"] = release.canonical_sha256(rows)
    _rehash(changed, "attribution_release_sha256")
    assert release.validate_attribution_release_structure_v1(changed) == changed
    changed_identity = store.force_generation(
        _ROOT_URI, release.canonical_json_bytes(changed)
    )

    with pytest.raises(
        release.CorpusR6FullUnionAttributionReleaseV1Error,
        match="body binding|predecessor replay|upstream binding",
    ):
        _reopen(store, sources, changed_identity)


def test_root_is_published_last_and_exact_reopen_replays_every_shard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = _synthetic_sources()
    store = _MemoryStore()
    trace = _install_scientific_seams(monkeypatch, sources)
    root, root_identity = _publish(store, sources)
    assert trace.validated_ordinals == list(range(grading.SOURCE_SLATE_COUNT))
    assert store.created_order[-1] == _ROOT_URI
    assert all(uri != _ROOT_URI for uri in store.created_order[:-1])
    assert len(store.created_order) == grading.SOURCE_SLATE_COUNT + 1
    trace.validated_ordinals.clear()  # type: ignore[union-attr]

    reopened, retained_identity = _reopen(store, sources, root_identity)

    assert reopened == root
    assert retained_identity == root_identity
    assert trace.validated_ordinals == list(range(grading.SOURCE_SLATE_COUNT))


def test_structure_only_validation_cannot_authorize_corrupt_shards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = _synthetic_sources()
    store = _MemoryStore()
    _install_scientific_seams(monkeypatch, sources)
    root, root_identity = _publish(store, sources)

    structured = release.validate_attribution_release_structure_v1(root)
    assert structured == root
    for field in (
        "promotion_authority",
        "decision_authority",
        "production_change_licensed",
        "graph_mutation_licensed",
    ):
        assert structured[field] is False
    assert structured["structure_only_validation_authority"] is False

    first_uri = (
        f"{_OUTPUT_PREFIX}/slate-attributions/00-{_slate_id(0)}.json"
    )
    first_identity = store.current[first_uri][0]
    retained_raw = store.read_exact(first_identity)
    store.corrupt_exact(first_identity, b"x" * len(retained_raw))

    assert release.validate_attribution_release_structure_v1(root) == root
    with pytest.raises(
        (release.CorpusR6FullUnionAttributionReleaseV1Error, KeyError),
        match="exact|identity|SHA|bytes|reopen|canonical",
    ):
        _reopen(store, sources, root_identity)
