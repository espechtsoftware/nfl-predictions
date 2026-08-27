"""Hermetic tests for the terminal-attribution no-rescore funnel.

The 54-shard traversal is real.  The predecessor attribution structure
validator is replaced with a compact already-validated shard fixture so the
test does not allocate the production release's 199,244 lineup rows and
207,360 selection rows.  No cloud, outcome source, scorer, or warehouse is
available to these tests.
"""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_attribution_release_v1 as release
from nfl_dfs.research import corpus_r6_full_union_attribution_v1 as attribution
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading
from nfl_dfs.research import corpus_r6_no_rescore_funnel_v1 as funnel
from tests import test_corpus_r6_full_union_attribution_v1 as attribution_fixture


_OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-corpus-retrieval/"
    "research/corpus-r6-full-union-attributions/synthetic-funnel-v1"
)
_ROOT_URI = f"{_OUTPUT_PREFIX}/attribution-release.json"
_WINNER_URI = str(funnel.ADOPTED_WINNER_REGISTRY_IDENTITY["uri"])
_N = 90


def _sha(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _identity(uri: str, raw: bytes, generation: int) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _MemoryReader:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str, int], bytes] = {}
        self.reads: list[dict[str, object]] = []

    @staticmethod
    def _key(value: object) -> tuple[str, str, str, int]:
        row = dict(value)  # type: ignore[arg-type]
        return (
            str(row["uri"]), str(row["generation"]),
            str(row["sha256"]), int(row["bytes"]),
        )

    def add(self, identity: dict[str, object], raw: bytes) -> None:
        self.values[self._key(identity)] = raw

    def read_exact(self, identity: object) -> bytes:
        row = dict(identity)  # type: ignore[arg-type]
        self.reads.append(row)
        return self.values[self._key(row)]


def _slate_id(source_ordinal: int) -> str:
    return f"{2023 + source_ordinal // 18}-w{source_ordinal % 18 + 1:02d}"


def _fake_object_identity(label: str) -> dict[str, object]:
    return {
        "uri": f"gs://synthetic-r6/{label}.json",
        "generation": "1",
        "sha256": _sha(label),
        "bytes": 1,
    }


def _threshold_captures(
    population_scores: list[int], selected_scores: list[int]
) -> list[dict[str, object]]:
    rows = []
    for threshold in grading.THRESHOLDS_DK:
        threshold_micro = int(threshold) * grading.MICRO_DK_PER_POINT
        eligible_count = sum(score >= threshold_micro for score in population_scores)
        selected_count = sum(score >= threshold_micro for score in selected_scores)
        rows.append({
            "threshold_dk": int(threshold),
            "threshold_micro": threshold_micro,
            "eligible_lineup_count": eligible_count,
            "selected_lineup_count": selected_count,
            "selected_hit": selected_count > 0,
            "eligible_hit": eligible_count > 0,
        })
    return rows


def _compact_shard(source_ordinal: int) -> dict[str, object]:
    slate_id = _slate_id(source_ordinal)
    lineup_ids = [f"lineup-{source_ordinal:02d}-{index:03d}" for index in range(_N)]
    scores = [
        240 * grading.MICRO_DK_PER_POINT,
        *([100 * grading.MICRO_DK_PER_POINT] * (_N - 1)),
    ]
    lineup_rows = [
        {
            "lineup_id": lineup_id,
            "realized_score_micro": scores[index],
            "training_source_arms": ["incumbent"],
            "training_origin_blocks": ["R0"],
            "training_occurrence_count": 1,
        }
        for index, lineup_id in enumerate(lineup_ids)
    ]
    books: list[dict[str, object]] = []
    selections: list[dict[str, object]] = []
    for strategy_ordinal, strategy_id in enumerate(funnel.STRATEGY_IDS):
        offset = (10 * strategy_ordinal) % _N
        selected_ids = [
            lineup_ids[(offset + rank) % _N]
            for rank in range(funnel.EXACT_ENTRY_COUNT)
        ]
        selected_scores = [scores[lineup_ids.index(lineup_id)] for lineup_id in selected_ids]
        maximum = max(selected_scores)
        maximum_ids = sorted(
            lineup_id for lineup_id in selected_ids
            if scores[lineup_ids.index(lineup_id)] == maximum
        )
        strategy_sha = _sha(f"strategy-{strategy_id}")
        books.append({
            "scope_ordinal": funnel.FINAL_SCOPE_ORDINAL,
            "fit_scope_id": funnel.FINAL_FIT_SCOPE_ID,
            "strategy_ordinal": strategy_ordinal,
            "strategy_id": strategy_id,
            "strategy_sha256": strategy_sha,
            "book_id": f"book-{source_ordinal:02d}-{strategy_ordinal}",
            "book_sha256": _sha(f"book-{source_ordinal}-{strategy_ordinal}"),
            "eligible_lineup_count": _N,
            "selected_lineup_count": funnel.EXACT_ENTRY_COUNT,
            "eligible_maximum_score_micro": max(scores),
            "eligible_maximum_lineup_ids": [lineup_ids[0]],
            "selected_maximum_score_micro": maximum,
            "selected_maximum_lineup_ids": maximum_ids,
            "selector_regret_micro": max(scores) - maximum,
            "threshold_capture": _threshold_captures(scores, selected_scores),
        })
        selections.extend({
            "scope_ordinal": funnel.FINAL_SCOPE_ORDINAL,
            "fit_scope_id": funnel.FINAL_FIT_SCOPE_ID,
            "strategy_ordinal": strategy_ordinal,
            "strategy_id": strategy_id,
            "selection_rank": rank,
            "lineup_id": lineup_id,
        } for rank, lineup_id in enumerate(selected_ids))
    body: dict[str, object] = {
        "source_ordinal": source_ordinal,
        "slate_id": slate_id,
        "slate_freeze_identity": _fake_object_identity(
            f"slate-freeze-{source_ordinal}"
        ),
        "task_result_identity": _fake_object_identity(
            f"task-result-{source_ordinal}"
        ),
        "task_result_sha256": _sha(f"task-result-body-{source_ordinal}"),
        "slate_grade_identity": _fake_object_identity(
            f"slate-grade-{source_ordinal}"
        ),
        "slate_grade_sha256": _sha(f"slate-grade-body-{source_ordinal}"),
        "candidate_provenance_sha256": _sha(
            f"candidate-provenance-{source_ordinal}"
        ),
        "lineup_count": _N,
        "lineup_rows": lineup_rows,
        "scope_membership_count": grading.SCOPES_PER_SLATE * _N,
        "book_count": grading.BOOKS_PER_SLATE,
        "book_rows": books,
        "selection_count": grading.BOOKS_PER_SLATE * funnel.EXACT_ENTRY_COUNT,
        "selection_rows": selections,
    }
    body["slate_attribution_sha256"] = funnel.canonical_sha256(body)
    return body


def _descriptor(
    shard: dict[str, object], identity: dict[str, object]
) -> dict[str, object]:
    return release._descriptor_from_shard(  # noqa: SLF001
        shard,
        identity=identity,
        target_uri=str(identity["uri"]),
    )


def _root(descriptors: list[dict[str, object]]) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": release.ATTRIBUTION_RELEASE_SCHEMA,
        "publication_mode": release.PUBLICATION_MODE,
        "target_uri": _ROOT_URI,
        "run_id": "synthetic-funnel-v1",
        "grade_completion_identity": _fake_object_identity("grade-completion"),
        "persisted_grade_root_identity": _fake_object_identity("grade-root"),
        "panel_freeze_identity": _fake_object_identity("panel-freeze"),
        "panel_freeze_sha256": _sha("panel-freeze-body"),
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "slate_attribution_objects": descriptors,
        "slate_attribution_objects_sha256": release.canonical_sha256(descriptors),
        "lineup_count": sum(int(row["lineup_count"]) for row in descriptors),
        "scope_membership_count": sum(
            int(row["scope_membership_count"]) for row in descriptors
        ),
        "book_count": sum(int(row["book_count"]) for row in descriptors),
        "selection_count": sum(int(row["selection_count"]) for row in descriptors),
        "reads_freeze_and_grade_artifacts_only": True,
        "uses_realized_outcomes": True,
        "no_rescore": True,
        "complete": True,
        "all_shard_identities_resolved_before_root_build": True,
        "every_shard_exact_reopened_and_predecessor_replayed": True,
        "root_create_once_requested_last": True,
        **{field: False for field in release._FALSE_AUTHORITY_FIELDS},  # noqa: SLF001
    }
    body["attribution_release_sha256"] = release.canonical_sha256(body)
    return body


def _synthetic_expected(winner_registry: dict[str, object]) -> dict[str, object]:
    targets, _ = funnel._winner_targets_from_registry_v1(winner_registry)  # noqa: SLF001
    maximum = 240 * grading.MICRO_DK_PER_POINT
    gaps = [maximum - target for target in targets.values()]
    return {
        "source_slate_count": grading.SOURCE_SLATE_COUNT,
        "lineup_count": grading.SOURCE_SLATE_COUNT * _N,
        "nominal_generation_occurrence_count": grading.SOURCE_SLATE_COUNT * _N,
        "diagnostic_union_lineup_count": grading.SOURCE_SLATE_COUNT * _N,
        "thresholds": {
            str(threshold): {
                "population_lineup_count": grading.SOURCE_SLATE_COUNT,
                "population_opportunity_slates": grading.SOURCE_SLATE_COUNT,
                "diagnostic_union_hit_slates": grading.SOURCE_SLATE_COUNT,
            }
            for threshold in grading.THRESHOLDS_DK
        },
        "diagnostic_union_exact_oracle_capture_slates": grading.SOURCE_SLATE_COUNT,
        "winner_target_included_slates": len(targets),
        "corpus_reaches_winner_slates": sum(gap >= 0 for gap in gaps),
        "corpus_within_10_winner_slates": sum(
            gap >= -10 * grading.MICRO_DK_PER_POINT for gap in gaps
        ),
        "corpus_within_25_winner_slates": sum(
            gap >= -25 * grading.MICRO_DK_PER_POINT for gap in gaps
        ),
    }


def _winner_authority(identity: dict[str, object]) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": funnel.WINNER_REGISTRY_AUTHORITY_SCHEMA,
        "authority_id": funnel.WINNER_REGISTRY_AUTHORITY_ID,
        "winner_registry_identity": identity,
        "winner_registry_sha256": funnel.ADOPTED_WINNER_REGISTRY_SHA256,
        "expected_contest_count": 68,
        "expected_governed_cohort_count": 51,
        "expected_governed_seasons": [2023, 2024, 2025],
        "expected_per_season_contest_counts": {
            "2019": 17, "2023": 17, "2024": 17, "2025": 17,
        },
        "expected_provenance_gaps": [
            "contest-id-absent", "source-url-absent", "capture-time-absent",
        ],
        "higher_level_operator_prepin_required": True,
        "terminal": True,
        "automatic_promotion": False,
        "production_policy_authority": False,
    }
    body["winner_registry_authority_sha256"] = funnel.canonical_sha256(body)
    return body


def _fixture() -> tuple[
    _MemoryReader, dict[str, object], dict[str, object], dict[str, object]
]:
    reader = _MemoryReader()
    descriptors: list[dict[str, object]] = []
    for source_ordinal in range(grading.SOURCE_SLATE_COUNT):
        shard = _compact_shard(source_ordinal)
        raw = funnel.canonical_json_bytes(shard)
        uri = (
            f"{_OUTPUT_PREFIX}/slate-attributions/"
            f"{source_ordinal:02d}-{shard['slate_id']}.json"
        )
        identity = _identity(uri, raw, source_ordinal + 1)
        reader.add(identity, raw)
        descriptors.append(_descriptor(shard, identity))
    root = _root(descriptors)
    root_raw = funnel.canonical_json_bytes(root)
    root_identity = _identity(_ROOT_URI, root_raw, 1000)
    reader.add(root_identity, root_raw)

    winner_path = Path("reports/winner-registry/winner-registry-v1.json")
    winner_raw = winner_path.read_bytes()
    winner_registry = json.loads(winner_raw)
    winner_identity = dict(funnel.ADOPTED_WINNER_REGISTRY_IDENTITY)
    assert winner_identity == _identity(
        _WINNER_URI,
        winner_raw,
        int(str(funnel.ADOPTED_WINNER_REGISTRY_IDENTITY["generation"])),
    )
    reader.add(winner_identity, winner_raw)
    return reader, root_identity, winner_identity, winner_registry


def test_public_builder_has_no_caller_supplied_row_or_score_bypass() -> None:
    parameters = inspect.signature(
        funnel.build_no_rescore_funnel_release_v1
    ).parameters

    assert set(parameters) == {
        "attribution_release_root_identity", "winner_registry_authority",
        "read_exact",
    }
    assert not {
        "rows", "lineup_rows", "scores", "winner_targets", "shards",
        "attributions",
    }.intersection(parameters)


def test_random_book_null_uses_exact_hypergeometric_formula() -> None:
    assert funnel._random_hit_probability(  # noqa: SLF001
        population=90, qualifying=1, draw=80
    ) == "0.888888888888888889"
    assert funnel._random_hit_probability(  # noqa: SLF001
        population=90, qualifying=1, draw=90
    ) == "1.000000000000000000"
    assert funnel._random_hit_probability(  # noqa: SLF001
        population=90, qualifying=0, draw=80
    ) == "0.000000000000000000"


def test_terminal_consumer_separates_exact_80_from_actual_k_s_union(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, root_identity, winner_identity, winner_registry = _fixture()
    monkeypatch.setattr(
        attribution,
        "validate_slate_attribution_structure_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        funnel, "EXPECTED_REVIEW_HEADLINES", _synthetic_expected(winner_registry)
    )

    result = funnel.build_no_rescore_funnel_release_v1(
        attribution_release_root_identity=root_identity,
        winner_registry_authority=_winner_authority(winner_identity),
        read_exact=reader.read_exact,
    )

    assert result["no_rescore"] is True
    assert result["raw_outcome_source_read"] is False
    assert result["lineup_rescore_performed"] is False
    assert result["winner_registry_prepinned_identity_required"] is True
    assert result["winner_registry_generation_exact_read"] is True
    assert result["winner_registry_internal_self_hash_verified"] is True
    assert "winner_targets_from_self_hashed_registry_only" not in result
    assert len(reader.reads) == 1 + 1 + grading.SOURCE_SLATE_COUNT
    assert reader.reads[0] == root_identity
    assert reader.reads[1] == winner_identity
    assert all(
        row["entry_count_k"] == 80
        for row in result["exact_80_strategy_results"]
    )
    exact_probability = result["slate_rows"][0]["exact_80_books"][0][
        "thresholds"
    ][0]["descriptive_random_hit_probability_decimal"]
    assert exact_probability == "0.888888888888888889"
    union = result["diagnostic_union_result"]
    assert union["deployable_book"] is False
    assert union["actual_k_s_minimum"] == _N
    assert union["actual_k_s_maximum"] == _N
    union_probability = result["slate_rows"][0]["diagnostic_union"][
        "thresholds"
    ][0]["descriptive_random_hit_probability_decimal"]
    assert union_probability == "1.000000000000000000"
    assert result["descriptive_attribution"]["interpretation"] == (
        "descriptive-only-not-causal-allocation-evidence"
    )
    assert result["winner_target_census"]["included_slate_count"] == 51
    assert result["winner_target_census"]["excluded_slate_count"] == 3
    assert funnel.validate_no_rescore_funnel_release_v1(result) == result


def test_allowlisted_reader_rejects_unregistered_identity_before_delegate() -> None:
    reader, _root_identity, winner_identity, _winner_registry = _fixture()
    delegated_before = len(reader.reads)
    scoped = funnel._allowlisted_reader(  # noqa: SLF001
        read_exact=reader.read_exact,
        allowed_identities=[
            winner_identity,
            *[
                _fake_object_identity(f"allowed-{ordinal}")
                for ordinal in range(grading.SOURCE_SLATE_COUNT)
            ],
        ],
    )

    with pytest.raises(
        funnel.CorpusR6NoRescoreFunnelV1Error,
        match="outside the exact allowlist",
    ):
        scoped(_fake_object_identity("raw-outcome-snapshot"))

    assert len(reader.reads) == delegated_before


def test_headline_guard_fails_closed_on_one_count_drift() -> None:
    changed = deepcopy(funnel.EXPECTED_REVIEW_HEADLINES)
    changed["lineup_count"] = int(changed["lineup_count"]) - 1

    with pytest.raises(
        funnel.CorpusR6NoRescoreFunnelV1Error,
        match="does not reproduce",
    ):
        funnel._enforce_review_headlines_v1(changed)  # noqa: SLF001


def test_release_validator_rejects_self_hash_preserving_authority_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, root_identity, winner_identity, winner_registry = _fixture()
    monkeypatch.setattr(
        attribution,
        "validate_slate_attribution_structure_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        funnel, "EXPECTED_REVIEW_HEADLINES", _synthetic_expected(winner_registry)
    )
    result = funnel.build_no_rescore_funnel_release_v1(
        attribution_release_root_identity=root_identity,
        winner_registry_authority=_winner_authority(winner_identity),
        read_exact=reader.read_exact,
    )
    changed = deepcopy(result)
    changed["lineup_rescore_performed"] = True
    changed.pop("funnel_release_sha256")
    changed["funnel_release_sha256"] = funnel.canonical_sha256(changed)

    with pytest.raises(
        funnel.CorpusR6NoRescoreFunnelV1Error,
        match="authority law differs",
    ):
        funnel.validate_no_rescore_funnel_release_v1(changed)


def test_compact_production_attribution_validator_replay_is_unmocked() -> None:
    generator = attribution_fixture.case.__wrapped__()
    case = next(generator)
    try:
        shard = case.build()
        retained = attribution.validate_slate_attribution_structure_v1(shard)
        raw = funnel.canonical_json_bytes(retained)
        identity = _identity("gs://synthetic-r6/production-validator.json", raw, 9)
        descriptor = _descriptor(retained, identity)

        # The production fixture deliberately names its strategies generically;
        # after the real production validator accepts the shard, the funnel must
        # still fail closed rather than reinterpret that registry as the adopted
        # eight strategies.
        with pytest.raises(
            funnel.CorpusR6NoRescoreFunnelV1Error,
            match="exact-80 strategy",
        ):
            funnel._slate_funnel_v1(  # noqa: SLF001
                shard=retained,
                descriptor=descriptor,
                shard_identity=identity,
                winner_target_micro=None,
            )
    finally:
        with pytest.raises(StopIteration):
            next(generator)


def test_rehashed_registry_replacement_cannot_select_winner_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, root_identity, winner_identity, winner_registry = _fixture()
    changed = deepcopy(winner_registry)
    contest = changed["contests"][0]
    contest["players"][0]["listed_points"] += 1.0
    contest["roster_points_total"] += 1.0
    changed.pop("winner_registry_sha256")
    changed["winner_registry_sha256"] = funnel.canonical_sha256(changed)
    raw = funnel.canonical_json_bytes(changed)
    changed_identity = _identity(f"{_WINNER_URI}.replacement", raw, 2001)
    reader.add(changed_identity, raw)
    monkeypatch.setattr(
        attribution,
        "validate_slate_attribution_structure_v1",
        lambda value: dict(value),
    )

    with pytest.raises(
        funnel.CorpusR6NoRescoreFunnelV1Error,
        match="authority law differs",
    ):
        funnel.build_no_rescore_funnel_release_v1(
            attribution_release_root_identity=root_identity,
            winner_registry_authority=_winner_authority(changed_identity),
            read_exact=reader.read_exact,
        )

    assert winner_identity != changed_identity


def test_coherently_rehashed_registry_identity_cannot_replace_fixed_authority(
) -> None:
    _reader, _root_identity, winner_identity, _winner_registry = _fixture()
    changed_identity = deepcopy(winner_identity)
    changed_identity["uri"] = f"{winner_identity['uri']}.mirror"
    changed = _winner_authority(changed_identity)
    assert changed["winner_registry_authority_sha256"] != (
        funnel.ADOPTED_WINNER_REGISTRY_AUTHORITY_SHA256
    )

    with pytest.raises(
        funnel.CorpusR6NoRescoreFunnelV1Error,
        match="authority law differs",
    ):
        funnel.validate_winner_registry_authority_v1(changed)


def test_structure_validator_rejects_coherent_nested_aggregate_rehash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, root_identity, winner_identity, winner_registry = _fixture()
    monkeypatch.setattr(
        attribution,
        "validate_slate_attribution_structure_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        funnel, "EXPECTED_REVIEW_HEADLINES", _synthetic_expected(winner_registry)
    )
    result = funnel.build_no_rescore_funnel_release_v1(
        attribution_release_root_identity=root_identity,
        winner_registry_authority=_winner_authority(winner_identity),
        read_exact=reader.read_exact,
    )
    changed = deepcopy(result)
    changed["exact_80_strategy_results"][0][
        "selected_maximum_score_mean_micro_decimal"
    ] = "239999999.000000000000000000"
    changed.pop("funnel_release_sha256")
    changed["funnel_release_sha256"] = funnel.canonical_sha256(changed)

    with pytest.raises(
        funnel.CorpusR6NoRescoreFunnelV1Error,
        match="aggregate differs",
    ):
        funnel.validate_no_rescore_funnel_release_v1(changed)


def test_authoritative_reopen_byte_replays_predecessors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader, root_identity, winner_identity, winner_registry = _fixture()
    monkeypatch.setattr(
        attribution,
        "validate_slate_attribution_structure_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        funnel, "EXPECTED_REVIEW_HEADLINES", _synthetic_expected(winner_registry)
    )
    authority = _winner_authority(winner_identity)
    result = funnel.build_no_rescore_funnel_release_v1(
        attribution_release_root_identity=root_identity,
        winner_registry_authority=authority,
        read_exact=reader.read_exact,
    )
    raw = funnel.canonical_json_bytes(result)
    result_identity = _identity("gs://synthetic-r6/funnel-release.json", raw, 3000)
    reader.add(result_identity, raw)

    reopened, reopened_identity = funnel.reopen_no_rescore_funnel_release_v1(
        result_identity,
        attribution_release_root_identity=root_identity,
        winner_registry_authority=authority,
        read_exact=reader.read_exact,
    )

    assert reopened == result
    assert reopened_identity == result_identity

    # A coherent nested rewrite can remain structurally self-consistent.  The
    # structure validator is intentionally non-authoritative; exact predecessor
    # replay is what rejects this replacement.
    changed = deepcopy(result)
    changed["slate_rows"][0]["exact_80_books"][0]["book_id"] = "replacement"
    changed["slate_rows_sha256"] = funnel.canonical_sha256(
        changed["slate_rows"]
    )
    changed.pop("funnel_release_sha256")
    changed["funnel_release_sha256"] = funnel.canonical_sha256(changed)
    assert funnel.validate_no_rescore_funnel_release_v1(changed) == changed
    changed_raw = funnel.canonical_json_bytes(changed)
    changed_identity = _identity(
        "gs://synthetic-r6/funnel-release-replacement.json", changed_raw, 3001
    )
    reader.add(changed_identity, changed_raw)

    with pytest.raises(
        funnel.CorpusR6NoRescoreFunnelV1Error,
        match="canonical predecessor replay differs",
    ):
        funnel.reopen_no_rescore_funnel_release_v1(
            changed_identity,
            attribution_release_root_identity=root_identity,
            winner_registry_authority=authority,
            read_exact=reader.read_exact,
        )


def test_module_has_no_cloud_or_scoring_import_surface() -> None:
    source = inspect.getsource(funnel)
    assert "google.cloud" not in source
    assert "bigquery" not in source.lower()
    assert "score_lineup" not in source
    assert "outcome_snapshot" in source  # explicit deny flag, never an import/read
    assert "publish_create_once" not in inspect.signature(
        funnel.build_no_rescore_funnel_release_v1
    ).parameters
