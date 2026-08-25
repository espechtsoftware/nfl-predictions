from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256

import pytest

from nfl_dfs.research import corpus_catalog_realized_grading as grading
from nfl_dfs.research import corpus_core_v1_catalog as catalog
from nfl_dfs.research import corpus_core_v1_grade_publisher as publisher


_publish_validated = getattr(
    publisher, "_publish_validated_sharded_core_v1_realized_grade"
)


@dataclass
class _MemoryStore:
    values_by_uri: dict[str, tuple[dict[str, object], bytes]] = field(
        default_factory=dict
    )
    values_by_key: dict[tuple[str, str], bytes] = field(default_factory=dict)
    publish_attempts: list[str] = field(default_factory=list)
    next_generation: int = 700_000

    def publish_create_once(
        self, uri: str, raw: bytes,
    ) -> publisher.CreateOncePublication:
        self.publish_attempts.append(uri)
        retained = self.values_by_uri.get(uri)
        if retained is not None:
            identity, existing = retained
            if existing != raw:
                raise RuntimeError("create-once conflict")
            return publisher.CreateOncePublication(
                identity=dict(identity), created=False
            )
        identity = {
            "uri": uri,
            "generation": str(self.next_generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.next_generation += 1
        self.values_by_uri[uri] = (dict(identity), raw)
        self.values_by_key[(uri, str(identity["generation"]))] = raw
        return publisher.CreateOncePublication(identity=identity, created=True)

    def read_exact(self, identity: dict[str, object]) -> bytes:
        return self.values_by_key[
            (str(identity["uri"]), str(identity["generation"]))
        ]

    def clone(self) -> _MemoryStore:
        return _MemoryStore(
            values_by_uri={
                uri: (dict(identity), raw)
                for uri, (identity, raw) in self.values_by_uri.items()
            },
            values_by_key=dict(self.values_by_key),
            publish_attempts=list(self.publish_attempts),
            next_generation=self.next_generation,
        )


def _self_hash(value: dict[str, object], field: str) -> dict[str, object]:
    retained = dict(value)
    retained[field] = publisher.canonical_sha256(retained)
    return retained


def _identity(uri: str, character: str) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": character * 64,
        "bytes": 1,
    }


def _book_grade(
    *,
    source_ordinal: int,
    strategy_id: str,
    budget: int,
    score_rows: list[dict[str, object]],
) -> dict[str, object]:
    rows = [
        {
            "selection_rank": selection_rank,
            **score_rows[selection_rank],
        }
        for selection_rank in range(budget)
    ]
    return _self_hash({
        "schema_version": grading.BOOK_GRADE_SCHEMA,
        "source_ordinal": source_ordinal,
        "book_id": f"{source_ordinal:02d}:{strategy_id}:{budget}",
        "book_sha256": "c" * 64,
        "strategy_id": strategy_id,
        "implementation_sha256": "d" * 64,
        "entry_budget": budget,
        "entry_count": budget,
        "roster_score_rows_rank_order": rows,
        "rank_order_score_rows_sha256": publisher.canonical_sha256(rows),
        "exact_prefix_consistency_verified": True,
        "independent_score_map_projection_replayed": True,
    }, "book_grade_sha256")


def _slate_grade(source_ordinal: int) -> dict[str, object]:
    slate = {
        "season": 2020 + source_ordinal // 18,
        "week": source_ordinal % 18 + 1,
        "slate_id": f"main-{source_ordinal:02d}",
    }
    score_rows = [
        {
            "union_index": union_index,
            "lineup_id": f"union-{source_ordinal:02d}-{union_index:02d}",
            "roster_identity_sha256": f"{union_index + 1:064x}",
            "realized_score_micro": (
                200_000 + source_ordinal + union_index
            ),
        }
        for union_index in range(max(catalog.EXPECTED_BOOK_BUDGETS))
    ]
    books = [
        _book_grade(
            source_ordinal=source_ordinal,
            strategy_id=strategy_id,
            budget=budget,
            score_rows=score_rows,
        )
        for strategy_id in catalog.STRATEGY_IDS
        for budget in catalog.EXPECTED_BOOK_BUDGETS
    ]
    return _self_hash({
        "schema_version": grading.SLATE_GRADE_SCHEMA,
        "source_ordinal": source_ordinal,
        "slate": slate,
        "slate_catalog_sha256": f"{source_ordinal + 1:064x}",
        "union_population_sha256": f"{source_ordinal + 101:064x}",
        "union_roster_sum_operation_count": len(score_rows),
        "union_score_rows": score_rows,
        "union_score_map_sha256": publisher.canonical_sha256(score_rows),
        "book_grade_count": len(books),
        "book_grades": books,
        "every_unique_union_roster_scored_once": True,
        "every_book_projected_without_roster_rescore": True,
        "every_book_projection_independently_replayed": True,
    }, "slate_grade_sha256")


@pytest.fixture(scope="module")
def logical_grade() -> dict[str, object]:
    slate_grades = [
        _slate_grade(source_ordinal)
        for source_ordinal in range(catalog.EXPECTED_SOURCE_SLATE_COUNT)
    ]
    weekly_contrasts = [
        _self_hash({
            "schema_version": grading.CONTRAST_ROW_SCHEMA,
            "contrast_id": f"contrast-{contrast_ordinal:02d}",
            "contrast_sha256": f"{contrast_ordinal + 1:064x}",
            "family": "primary-headline",
            "entry_budget": budget,
            "source_ordinal": source_ordinal,
            "challenger_strategy_id": catalog.STRATEGY_IDS[1],
            "comparator_strategy_id": catalog.STRATEGY_IDS[0],
            "direction": "challenger-minus-comparator",
            "evidence_class": catalog.EVIDENCE_CLASS,
        }, "contrast_row_sha256")
        for contrast_ordinal in range(publisher.EXPECTED_CONTRAST_COUNT)
        for budget in catalog.EXPECTED_BOOK_BUDGETS
        for source_ordinal in range(catalog.EXPECTED_SOURCE_SLATE_COUNT)
    ]
    weekly_by_key: dict[tuple[object, object], list[object]] = {}
    for row in weekly_contrasts:
        weekly_by_key.setdefault(
            (row["contrast_id"], row["entry_budget"]), []
        ).append(row["contrast_row_sha256"])
    contrast_summaries = [
        _self_hash({
            "schema_version": grading.CONTRAST_SUMMARY_SCHEMA,
            "contrast_id": f"contrast-{contrast_ordinal:02d}",
            "contrast_sha256": f"{contrast_ordinal + 1:064x}",
            "family": "primary-headline",
            "entry_budget": budget,
            "challenger_strategy_id": catalog.STRATEGY_IDS[1],
            "comparator_strategy_id": catalog.STRATEGY_IDS[0],
            "weekly_contrast_row_count": (
                catalog.EXPECTED_SOURCE_SLATE_COUNT
            ),
            "weekly_contrast_rows_sha256": publisher.canonical_sha256(
                weekly_by_key[(f"contrast-{contrast_ordinal:02d}", budget)]
            ),
            "evidence_class": catalog.EVIDENCE_CLASS,
            "report_regardless_of_sign": True,
        }, "contrast_summary_sha256")
        for contrast_ordinal in range(publisher.EXPECTED_CONTRAST_COUNT)
        for budget in catalog.EXPECTED_BOOK_BUDGETS
    ]
    union_count = sum(
        len(slate["union_score_rows"]) for slate in slate_grades
    )
    coverage = {
        "source_slate_count": catalog.EXPECTED_SOURCE_SLATE_COUNT,
        "strategy_count": catalog.EXPECTED_STRATEGY_COUNT,
        "entry_budget_count": len(catalog.EXPECTED_BOOK_BUDGETS),
        "book_cell_count": catalog.EXPECTED_BOOK_CELL_COUNT,
        "contrast_definition_count": publisher.EXPECTED_CONTRAST_COUNT,
        "weekly_contrast_cell_count": len(weekly_contrasts),
        "contrast_summary_count": len(contrast_summaries),
        "unique_union_roster_membership_count": union_count,
        "union_roster_sum_operation_count": union_count,
        "actual_player_outcome_row_count": union_count * 9,
        "every_unique_union_roster_scored_exactly_once_per_slate": True,
        "every_book_projected_from_shared_score_map": True,
        "every_book_projection_independently_replayed": True,
        "all_registered_contrasts_reported_regardless_of_sign": True,
        "actual_player_outcome_keys_exact": True,
        "complete": True,
    }
    body = {
        "schema_version": grading.RESULT_SCHEMA,
        "phase": "post-catalog-realized-historical",
        "evidence_class": catalog.EVIDENCE_CLASS,
        "catalog_authority": {
            "catalog_identity": _identity(
                "gs://core-grade-test/catalog.json", "a"
            ),
            "catalog_sha256": "a" * 64,
        },
        "actual_player_outcome_authority": {
            "outcome_snapshot_identity": _identity(
                "gs://core-grade-test/outcome-snapshot.json", "b"
            ),
            "outcome_snapshot_sha256": "b" * 64,
            "source_identity": _identity(
                "gs://core-grade-test/player-source.json", "c"
            ),
        },
        "score_unit": "micro_dk",
        "micro_dk_per_point": grading.MICRO_DK_PER_POINT,
        "thresholds_micro": [
            value * grading.MICRO_DK_PER_POINT
            for value in catalog.THRESHOLDS_DK
        ],
        "coverage": coverage,
        "slate_grades": slate_grades,
        "weekly_contrasts": weekly_contrasts,
        "contrast_summaries": contrast_summaries,
        "contest_metrics": {
            "availability": "unavailable",
            "reason": "full_field_standings_and_payout_ladder_not_supplied",
            "full_field_standings_identity": None,
            "payout_ladder_identity": None,
            "rank": None,
            "roi_micro_usd": None,
        },
        "outcome_blind_catalog_mutated": False,
        "uses_realized_outcomes": True,
        "historical_retune_licensed": False,
        "historical_retry_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    return grading.validate_core_v1_realized_grade(
        _self_hash(body, "realized_grade_sha256")
    )


@pytest.fixture(scope="module")
def published_grade(logical_grade: dict[str, object]) -> dict[str, object]:
    store = _MemoryStore()
    publication = _publish_validated(
        realized_grade=logical_grade,
        output_prefix="gs://core-grade-test/results/",
        max_logical_grade_bytes=100_000_000,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )
    return {
        "store": store,
        "publication": publication,
        "logical_grade": logical_grade,
    }


def test_sharded_grade_publishes_root_last_and_exactly_reconstructs(
    published_grade: dict[str, object],
) -> None:
    store = published_grade["store"]
    publication = published_grade["publication"]
    logical_grade = published_grade["logical_grade"]

    assert len(store.publish_attempts) == 56
    assert store.publish_attempts[-2:] == [
        publisher.summary_uri("gs://core-grade-test/results/"),
        publisher.root_uri("gs://core-grade-test/results/"),
    ]
    assert publication.created_slate_shard_count == 54
    assert publication.recovered_slate_shard_count == 0
    assert publication.summary_created is True
    assert publication.root_created is True
    assert len(publication.slate_shard_identities) == 54
    assert publication.root_identity["bytes"] < publication.root[
        "materialization_metrics"
    ]["logical_grade_canonical_bytes"]
    assert publication.root["catalog_identity"] == logical_grade[
        "catalog_authority"
    ]["catalog_identity"]
    assert publication.root["outcome_snapshot_identity"] == logical_grade[
        "actual_player_outcome_authority"
    ]["outcome_snapshot_identity"]
    assert publication.root["player_source_identity"] == logical_grade[
        "actual_player_outcome_authority"
    ]["source_identity"]

    reopened = publisher.reopen_sharded_core_v1_realized_grade(
        root_identity=publication.root_identity,
        read_exact=store.read_exact,
    )
    assert publisher.canonical_json_bytes(reopened) == (
        publisher.canonical_json_bytes(logical_grade)
    )
    assert len(reopened["weekly_contrasts"]) == 7_290
    assert len(reopened["contrast_summaries"]) == 135
    assert [row["contrast_row_sha256"] for row in reopened["weekly_contrasts"]] == [
        row["contrast_row_sha256"] for row in logical_grade["weekly_contrasts"]
    ]


def test_sharded_grade_recovers_equal_create_once_components(
    published_grade: dict[str, object],
) -> None:
    store = published_grade["store"]
    first = published_grade["publication"]
    logical_grade = published_grade["logical_grade"]
    attempts_before = len(store.publish_attempts)

    recovered = _publish_validated(
        realized_grade=logical_grade,
        output_prefix="gs://core-grade-test/results/",
        max_logical_grade_bytes=100_000_000,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )

    assert len(store.publish_attempts) == attempts_before + 56
    assert recovered.created_slate_shard_count == 0
    assert recovered.recovered_slate_shard_count == 54
    assert recovered.summary_created is False
    assert recovered.root_created is False
    assert recovered.root_identity == first.root_identity
    assert recovered.summary_identity == first.summary_identity
    assert recovered.slate_shard_identities == first.slate_shard_identities


def test_sharded_grade_reopen_rejects_changed_generation_bytes(
    published_grade: dict[str, object],
) -> None:
    publication = published_grade["publication"]
    forged_store = published_grade["store"].clone()
    first_identity = publication.slate_shard_identities[0]
    key = (str(first_identity["uri"]), str(first_identity["generation"]))
    forged_store.values_by_key[key] = b"{}"

    with pytest.raises(
        publisher.CorpusCoreV1GradePublisherError,
        match="exact bytes differ from their identity",
    ):
        publisher.reopen_sharded_core_v1_realized_grade(
            root_identity=publication.root_identity,
            read_exact=forged_store.read_exact,
        )


def test_root_rejects_rehashed_catalog_identity_drift(
    published_grade: dict[str, object],
) -> None:
    root = deepcopy(published_grade["publication"].root)
    root["catalog_identity"] = _identity(
        "gs://core-grade-test/other-catalog.json", "f"
    )
    root.pop("sharded_grade_root_sha256")
    root = _self_hash(root, "sharded_grade_root_sha256")

    with pytest.raises(
        publisher.CorpusCoreV1GradePublisherError,
        match="root law differs",
    ):
        publisher.validate_sharded_core_v1_realized_grade_root(root)


def test_logical_grade_payload_ceiling_fails_before_publication(
    logical_grade: dict[str, object],
) -> None:
    store = _MemoryStore()
    with pytest.raises(
        publisher.CorpusCoreV1GradePublisherError,
        match="exceeds its configured payload ceiling",
    ):
        _publish_validated(
            realized_grade=logical_grade,
            output_prefix="gs://core-grade-test/too-large/",
            max_logical_grade_bytes=1,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    assert store.publish_attempts == []


def test_public_grade_rejects_upstream_identity_drift_before_publication(
    logical_grade: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        publisher.grading,
        "grade_core_v1_catalog",
        lambda **_kwargs: logical_grade,
    )
    monkeypatch.setattr(
        publisher.catalog_contract,
        "validate_core_v1_catalog",
        lambda value: {"catalog_sha256": "a" * 64},
    )
    store = _MemoryStore()

    with pytest.raises(
        publisher.CorpusCoreV1GradePublisherError,
        match="identity",
    ):
        publisher.grade_and_publish_sharded_core_v1(
            catalog={"catalog": "drifted"},
            catalog_identity=_identity(
                "gs://core-grade-test/drifted-catalog.json", "e"
            ),
            outcome_snapshot={"snapshot": "provided"},
            outcome_snapshot_identity=_identity(
                "gs://core-grade-test/outcome-snapshot.json", "b"
            ),
            player_source={"source": "provided"},
            player_source_identity=_identity(
                "gs://core-grade-test/player-source.json", "c"
            ),
            outcome_keys=(),
            output_prefix="gs://core-grade-test/identity-drift/",
            max_logical_grade_bytes=100_000_000,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    assert store.publish_attempts == []


def test_grade_and_publish_delegates_once_to_established_grader(
    logical_grade: dict[str, object], monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    authority_calls: list[dict[str, object]] = []

    def _grade_once(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return logical_grade

    def _validate_authority(**kwargs: object) -> None:
        authority_calls.append(dict(kwargs))

    monkeypatch.setattr(publisher.grading, "grade_core_v1_catalog", _grade_once)
    monkeypatch.setattr(
        publisher, "_validate_authoritative_grade_inputs", _validate_authority
    )
    store = _MemoryStore()
    result = publisher.grade_and_publish_sharded_core_v1(
        catalog={"catalog": "provided"},
        catalog_identity={"catalog_identity": "provided"},
        outcome_snapshot={"snapshot": "provided"},
        outcome_snapshot_identity={"snapshot_identity": "provided"},
        player_source={"source": "provided"},
        player_source_identity={"source_identity": "provided"},
        outcome_keys=(),
        output_prefix="gs://core-grade-test/delegation/",
        max_logical_grade_bytes=100_000_000,
        read_exact=store.read_exact,
        publish_create_once=store.publish_create_once,
    )

    assert len(calls) == 1
    assert calls[0]["contest_outcomes"] is None
    assert calls[0]["outcome_keys"] == ()
    assert len(authority_calls) == 1
    assert authority_calls[0]["grade"] is logical_grade
    assert result.created_slate_shard_count == 54
    assert store.publish_attempts[-1] == publisher.root_uri(
        "gs://core-grade-test/delegation/"
    )


def test_duplicate_weekly_cell_fails_before_publication(
    logical_grade: dict[str, object],
) -> None:
    forged = deepcopy(logical_grade)
    forged["weekly_contrasts"][1] = deepcopy(forged["weekly_contrasts"][0])
    forged.pop("realized_grade_sha256")
    forged = _self_hash(forged, "realized_grade_sha256")
    store = _MemoryStore()

    with pytest.raises(
        publisher.CorpusCoreV1GradePublisherError,
        match="weekly contrast key repeats",
    ):
        _publish_validated(
            realized_grade=forged,
            output_prefix="gs://core-grade-test/duplicate-weekly/",
            max_logical_grade_bytes=100_000_000,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    assert store.publish_attempts == []


def test_duplicate_union_score_row_fails_before_publication(
    logical_grade: dict[str, object],
) -> None:
    forged = deepcopy(logical_grade)
    slate = forged["slate_grades"][0]
    slate["union_score_rows"][1]["lineup_id"] = slate[
        "union_score_rows"
    ][0]["lineup_id"]
    slate["union_score_map_sha256"] = publisher.canonical_sha256(
        slate["union_score_rows"]
    )
    slate.pop("slate_grade_sha256")
    forged["slate_grades"][0] = _self_hash(slate, "slate_grade_sha256")
    forged.pop("realized_grade_sha256")
    forged = _self_hash(forged, "realized_grade_sha256")
    store = _MemoryStore()

    with pytest.raises(
        publisher.CorpusCoreV1GradePublisherError,
        match="union score-row census differs",
    ):
        _publish_validated(
            realized_grade=forged,
            output_prefix="gs://core-grade-test/duplicate-score-row/",
            max_logical_grade_bytes=100_000_000,
            read_exact=store.read_exact,
            publish_create_once=store.publish_create_once,
        )
    assert store.publish_attempts == []
