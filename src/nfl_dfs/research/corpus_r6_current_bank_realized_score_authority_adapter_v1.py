"""Pure structural adapter for persisted R6 full-union realized score rows.

This module intentionally does not import the historical grader, outcome
snapshot, attribution builder, warehouse client, or any scorer.  It validates
only the durable root/descriptor law and the already-persisted lineup-level
``realized_score_micro`` authority needed by the current-bank bridge.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch


ATTRIBUTION_RELEASE_SCHEMA: Final = (
    "corpus-r6-full-union-attribution-release/v1"
)
ATTRIBUTION_DESCRIPTOR_SCHEMA: Final = (
    "corpus-r6-full-union-attribution-object-descriptor/v1"
)
SLATE_ATTRIBUTION_SCHEMA: Final = "corpus-r6-full-union-slate-attribution/v1"
PUBLICATION_MODE: Final = "create_once_root_last"
SOURCE_SLATE_COUNT: Final = 54
SCOPES_PER_SLATE: Final = 6
BOOKS_PER_SLATE: Final = 48
SELECTIONS_PER_BOOK: Final = 80
THRESHOLDS_DK: Final = (187, 194, 200, 210, 220, 230, 240)
MICRO_DK_PER_POINT: Final = 1_000_000
ROSTER_SIZE: Final = 9
OUTPUT_NAMESPACE: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-full-union-attributions/"
)
_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,80}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_ROOT_FALSE_FIELDS = frozenset({
    "outcome_source_read", "outcome_snapshot_read",
    "additional_historical_outcome_read", "bigquery_client_constructed",
    "outcome_query_executed", "lineup_rescore_performed",
    "historical_scoring_licensed", "historical_retry_licensed",
    "historical_retune_licensed", "corpus_fill_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "promotion_authority", "decision_authority",
    "live_money_policy_authority", "causal_claims_licensed",
    "structure_only_validation_authority",
})
_SHARD_FALSE_FIELDS = frozenset({
    "outcome_source_read", "additional_historical_outcome_read",
    "bigquery_client_constructed", "outcome_query_executed",
    "historical_scoring_licensed", "historical_retry_licensed",
    "historical_retune_licensed", "corpus_fill_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "promotion_authority", "decision_authority",
    "live_money_policy_authority", "causal_claims_licensed",
})
_ROOT_FIELDS = frozenset({
    "schema_version", "publication_mode", "target_uri", "run_id",
    "grade_completion_identity", "persisted_grade_root_identity",
    "panel_freeze_identity", "panel_freeze_sha256", "source_slate_count",
    "slate_attribution_objects", "slate_attribution_objects_sha256",
    "lineup_count", "scope_membership_count", "book_count",
    "selection_count", "reads_freeze_and_grade_artifacts_only",
    "uses_realized_outcomes", "no_rescore", "complete",
    "all_shard_identities_resolved_before_root_build",
    "every_shard_exact_reopened_and_predecessor_replayed",
    "root_create_once_requested_last", *_ROOT_FALSE_FIELDS,
    "attribution_release_sha256",
})
_DESCRIPTOR_FIELDS = frozenset({
    "schema_version", "source_ordinal", "slate_id", "target_uri",
    "slate_attribution_identity", "slate_attribution_sha256",
    "slate_freeze_identity", "task_result_identity", "task_result_sha256",
    "slate_grade_identity", "slate_grade_sha256", "lineup_count",
    "scope_membership_count", "book_count", "selection_count",
    "slate_attribution_object_sha256",
})
_SHARD_FIELDS = frozenset({
    "schema_version", "source_ordinal", "slate_id",
    "panel_freeze_identity", "slate_freeze_identity",
    "task_result_identity", "task_result_sha256", "slate_grade_identity",
    "slate_grade_sha256", "candidate_provenance_sha256",
    "candidate_provenance_resolution",
    "exact_generation_occurrence_rows_available",
    "player_realized_contributions_available",
    "point_in_time_player_traits_attached", "thresholds_dk",
    "realized_union_rank_law", "selector_regret_law",
    "lineup_count", "lineup_rows", "lineup_rows_sha256",
    "scope_membership_count", "scope_membership_rows",
    "scope_membership_rows_sha256", "book_count", "book_rows",
    "book_rows_sha256", "selection_count", "selection_rows",
    "selection_rows_sha256", "contest_metrics", "fill_effect_interpretation",
    "uses_realized_outcomes", "no_rescore",
    "projected_from_persisted_union_score_lookup", "complete",
    *_SHARD_FALSE_FIELDS, "slate_attribution_sha256",
})
_LINEUP_FIELDS = frozenset({
    "source_ordinal", "slate_id", "union_index", "lineup_id",
    "roster_player_ids", "roster_identity_sha256", "realized_score_micro",
    "realized_union_rank", "realized_score_tie_count",
    "union_maximum_score_micro", "regret_to_union_maximum_micro",
    "at_or_above_thresholds_dk", "training_origin_blocks",
    "training_source_arms", "training_occurrence_counts_by_block",
    "training_source_arms_by_block", "training_occurrence_count",
    "source_arm_count", "origin_block_count", "multi_arm_origin",
    "multi_block_origin", "selected_book_count", "selected_scope_count",
    "selected_strategy_count", "selected_any", "missed_by_every_book",
})


class CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error(ValueError):
    """The persisted no-rescore score authority failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error(message)


def canonical_json_bytes_v1(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error(
            str(exc)
        ) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_json_bytes_v1(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error(
            str(exc)
        ) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> str:
    retained = _digest(value.get(field), label=f"{label} {field}")
    body = {key: nested for key, nested in value.items() if key != field}
    if canonical_sha256_v1(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def validate_attribution_release_score_authority_v1(
    value: object,
) -> dict[str, object]:
    """Validate the root-last release and exact 54-shard score ledger."""
    root = _mapping(value, label="attribution release root")
    if frozenset(root) != _ROOT_FIELDS:
        _fail("attribution release root fields differ")
    _self_hash(root, field="attribution_release_sha256", label="attribution release root")
    target_uri = root.get("target_uri")
    suffix = "/attribution-release.json"
    if type(target_uri) is not str or not target_uri.endswith(suffix):
        _fail("attribution release target URI differs")
    prefix = target_uri[:-len(suffix)]
    if not prefix.startswith(OUTPUT_NAMESPACE):
        _fail("attribution release namespace differs")
    run_id = prefix[len(OUTPUT_NAMESPACE):]
    if _RUN_ID.fullmatch(run_id) is None or "/" in run_id:
        _fail("attribution release run ID differs")
    for field in (
        "grade_completion_identity", "persisted_grade_root_identity",
        "panel_freeze_identity",
    ):
        _identity(root[field], label=f"attribution root {field}")
    if (
        root["schema_version"] != ATTRIBUTION_RELEASE_SCHEMA
        or root["publication_mode"] != PUBLICATION_MODE
        or root["run_id"] != run_id
        or root["source_slate_count"] != SOURCE_SLATE_COUNT
        or root["reads_freeze_and_grade_artifacts_only"] is not True
        or root["uses_realized_outcomes"] is not True
        or root["no_rescore"] is not True
        or root["complete"] is not True
        or root["all_shard_identities_resolved_before_root_build"] is not True
        or root["every_shard_exact_reopened_and_predecessor_replayed"] is not True
        or root["root_create_once_requested_last"] is not True
        or any(root[field] is not False for field in _ROOT_FALSE_FIELDS)
    ):
        _fail("attribution release no-rescore authority law differs")
    _digest(root["panel_freeze_sha256"], label="attribution panel SHA")
    descriptors = [
        _mapping(row, label=f"attribution descriptor[{index}]")
        for index, row in enumerate(_sequence(
            root["slate_attribution_objects"], label="attribution descriptors",
        ))
    ]
    if (
        len(descriptors) != SOURCE_SLATE_COUNT
        or root["slate_attribution_objects_sha256"]
        != canonical_sha256_v1(descriptors)
    ):
        _fail("attribution descriptor census/hash differs")
    identity_keys: set[tuple[str, str, str, int]] = set()
    slate_ids: set[str] = set()
    for source, descriptor in enumerate(descriptors):
        if frozenset(descriptor) != _DESCRIPTOR_FIELDS:
            _fail("attribution descriptor fields differ")
        _self_hash(
            descriptor, field="slate_attribution_object_sha256",
            label=f"attribution descriptor[{source}]",
        )
        slate_id = descriptor["slate_id"]
        identity = _identity(
            descriptor["slate_attribution_identity"],
            label=f"attribution shard identity[{source}]",
        )
        expected_uri = f"{prefix}/slate-attributions/{source:02d}-{slate_id}.json"
        identity_key = (
            str(identity["uri"]), str(identity["generation"]),
            str(identity["sha256"]), int(identity["bytes"]),
        )
        if (
            descriptor["schema_version"] != ATTRIBUTION_DESCRIPTOR_SCHEMA
            or descriptor["source_ordinal"] != source
            or type(slate_id) is not str or not slate_id
            or slate_id in slate_ids
            or descriptor["target_uri"] != expected_uri
            or identity["uri"] != expected_uri
            or identity_key in identity_keys
            or descriptor["book_count"] != BOOKS_PER_SLATE
            or descriptor["selection_count"]
            != BOOKS_PER_SLATE * SELECTIONS_PER_BOOK
            or type(descriptor["lineup_count"]) is not int
            or int(descriptor["lineup_count"]) < SELECTIONS_PER_BOOK
            or descriptor["scope_membership_count"]
            != SCOPES_PER_SLATE * int(descriptor["lineup_count"])
        ):
            _fail(f"attribution descriptor[{source}] differs")
        for field in (
            "slate_freeze_identity", "task_result_identity", "slate_grade_identity",
        ):
            _identity(descriptor[field], label=f"attribution descriptor {field}")
        for field in (
            "slate_attribution_sha256", "task_result_sha256", "slate_grade_sha256",
        ):
            _digest(descriptor[field], label=f"attribution descriptor {field}")
        identity_keys.add(identity_key)
        slate_ids.add(str(slate_id))
    totals = {
        "lineup_count": sum(int(row["lineup_count"]) for row in descriptors),
        "scope_membership_count": sum(
            int(row["scope_membership_count"]) for row in descriptors
        ),
        "book_count": sum(int(row["book_count"]) for row in descriptors),
        "selection_count": sum(int(row["selection_count"]) for row in descriptors),
    }
    if any(root[field] != expected for field, expected in totals.items()):
        _fail("attribution release aggregate census differs")
    return root


def _threshold_hits(score_micro: int) -> list[int]:
    return [
        threshold for threshold in THRESHOLDS_DK
        if score_micro >= threshold * MICRO_DK_PER_POINT
    ]


def validate_slate_score_row_authority_v1(value: object) -> dict[str, object]:
    """Validate one no-rescore shard and its ordered realized-score rows."""
    shard = _mapping(value, label="slate score authority")
    if frozenset(shard) != _SHARD_FIELDS:
        _fail("slate score authority fields differ")
    _self_hash(shard, field="slate_attribution_sha256", label="slate score authority")
    source = _integer(shard["source_ordinal"], label="slate source ordinal")
    slate_id = shard["slate_id"]
    if source >= SOURCE_SLATE_COUNT or type(slate_id) is not str or not slate_id:
        _fail("slate score coordinate differs")
    for field in (
        "panel_freeze_identity", "slate_freeze_identity", "task_result_identity",
        "slate_grade_identity",
    ):
        _identity(shard[field], label=f"slate score {field}")
    for field in (
        "task_result_sha256", "slate_grade_sha256",
        "candidate_provenance_sha256", "lineup_rows_sha256",
        "scope_membership_rows_sha256", "book_rows_sha256",
        "selection_rows_sha256",
    ):
        _digest(shard[field], label=f"slate score {field}")
    if (
        shard["schema_version"] != SLATE_ATTRIBUTION_SCHEMA
        or shard["candidate_provenance_resolution"]
        != "arm-block-count-summary-only"
        or shard["exact_generation_occurrence_rows_available"] is not False
        or shard["player_realized_contributions_available"] is not False
        or shard["point_in_time_player_traits_attached"] is not False
        or shard["thresholds_dk"] != list(THRESHOLDS_DK)
        or shard["realized_union_rank_law"]
        != "zero-based-score-desc-lineup-id-ascending-tiebreak-not-contest-rank"
        or shard["selector_regret_law"]
        != "realized-eligible-maximum-minus-selected-maximum-descriptive-only"
        or shard["contest_metrics"] != {
            "availability": "unavailable",
            "reason": (
                "full_field_standings_duplicate_tie_settlement_and_"
                "payout_ladder_not_supplied"
            ),
            "rank": None,
            "roi_micro_usd": None,
        }
        or shard["fill_effect_interpretation"]
        != "descriptive-only-pooled-multi-arm"
        or shard["uses_realized_outcomes"] is not True
        or shard["no_rescore"] is not True
        or shard["projected_from_persisted_union_score_lookup"] is not True
        or shard["complete"] is not True
        or any(shard[field] is not False for field in _SHARD_FALSE_FIELDS)
    ):
        _fail("slate score no-rescore authority law differs")
    rows = [
        _mapping(row, label=f"lineup score row[{index}]")
        for index, row in enumerate(_sequence(shard["lineup_rows"], label="lineup rows"))
    ]
    if (
        shard["lineup_count"] != len(rows)
        or len(rows) < SELECTIONS_PER_BOOK
        or shard["lineup_rows_sha256"] != canonical_sha256_v1(rows)
    ):
        _fail("lineup score-row census/hash differs")
    by_id: dict[str, dict[str, object]] = {}
    scores: dict[str, int] = {}
    for union_index, row in enumerate(rows):
        if frozenset(row) != _LINEUP_FIELDS:
            _fail("lineup score-row fields differ")
        lineup_id = row["lineup_id"]
        roster = _sequence(row["roster_player_ids"], label="lineup roster")
        score = row["realized_score_micro"]
        source_arms = _sequence(row["training_source_arms"], label="training source arms")
        origin_blocks = _sequence(row["training_origin_blocks"], label="training origin blocks")
        source_arm_count = _integer(
            row["source_arm_count"], label="lineup source-arm count",
        )
        origin_block_count = _integer(
            row["origin_block_count"], label="lineup origin-block count",
        )
        _integer(
            row["training_occurrence_count"],
            label="lineup training occurrence count",
        )
        selected_book_count = _integer(
            row["selected_book_count"], label="lineup selected-book count",
        )
        _integer(row["selected_scope_count"], label="lineup selected-scope count")
        _integer(
            row["selected_strategy_count"],
            label="lineup selected-strategy count",
        )
        _mapping(
            row["training_occurrence_counts_by_block"],
            label="lineup occurrence counts by block",
        )
        _mapping(
            row["training_source_arms_by_block"],
            label="lineup source arms by block",
        )
        if (
            row["source_ordinal"] != source
            or row["slate_id"] != slate_id
            or row["union_index"] != union_index
            or type(lineup_id) is not str or not lineup_id or lineup_id in by_id
            or any(type(player_id) is not str or not player_id for player_id in roster)
            or len(roster) != ROSTER_SIZE or roster != sorted(roster)
            or len(set(roster)) != ROSTER_SIZE
            or any(type(value) is not str or not value for value in source_arms)
            or any(type(value) is not str or not value for value in origin_blocks)
            or row["roster_identity_sha256"] != canonical_sha256_v1(roster)
            or type(score) is not int
            or row["at_or_above_thresholds_dk"] != _threshold_hits(int(score))
            or source_arm_count != len(source_arms)
            or origin_block_count != len(origin_blocks)
            or row["multi_arm_origin"] is not (source_arm_count > 1)
            or row["multi_block_origin"] is not (origin_block_count > 1)
            or row["selected_any"] is not (selected_book_count > 0)
            or row["missed_by_every_book"] is not (not row["selected_any"])
        ):
            _fail("lineup score-row coordinate, roster, or score differs")
        by_id[str(lineup_id)] = row
        scores[str(lineup_id)] = int(score)
    realized_order = sorted(scores, key=lambda lineup_id: (-scores[lineup_id], lineup_id))
    maximum = max(scores.values())
    tie_counts = Counter(scores.values())
    for rank, lineup_id in enumerate(realized_order):
        row = by_id[lineup_id]
        if (
            row["realized_union_rank"] != rank
            or row["union_maximum_score_micro"] != maximum
            or row["regret_to_union_maximum_micro"] != maximum - scores[lineup_id]
            or row["realized_score_tie_count"] != tie_counts[scores[lineup_id]]
        ):
            _fail("lineup realized rank/regret differs")
    nested_censuses = (
        ("scope_membership_rows", "scope_membership_rows_sha256",
         "scope_membership_count", SCOPES_PER_SLATE * len(rows)),
        ("book_rows", "book_rows_sha256", "book_count", BOOKS_PER_SLATE),
        ("selection_rows", "selection_rows_sha256", "selection_count",
         BOOKS_PER_SLATE * SELECTIONS_PER_BOOK),
    )
    for rows_field, hash_field, count_field, expected_count in nested_censuses:
        nested = [
            _mapping(row, label=f"slate score {rows_field}[{index}]")
            for index, row in enumerate(_sequence(shard[rows_field], label=rows_field))
        ]
        if (
            shard[count_field] != expected_count
            or len(nested) != expected_count
            or shard[hash_field] != canonical_sha256_v1(nested)
        ):
            _fail(f"slate score {rows_field} census/hash differs")
    return shard


__all__ = [
    "ATTRIBUTION_DESCRIPTOR_SCHEMA", "ATTRIBUTION_RELEASE_SCHEMA",
    "BOOKS_PER_SLATE",
    "CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error",
    "SCOPES_PER_SLATE", "SELECTIONS_PER_BOOK", "SLATE_ATTRIBUTION_SCHEMA",
    "SOURCE_SLATE_COUNT", "validate_attribution_release_score_authority_v1",
    "validate_slate_score_row_authority_v1",
]
