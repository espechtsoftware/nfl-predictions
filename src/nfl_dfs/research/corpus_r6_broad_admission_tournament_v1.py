"""Fixed-corpus A250/A500 admission tournament for the combined R6 union.

This module changes admission only.  It never generates a candidate, reads an
outcome while freezing a slate, chooses K80, or treats the full-union hindsight
maximum as a recoverable target.  The two score-free admissions are a direct
extension of the existing modeled-tail order and a source-quota/disagreement
union.  A small weighted ridge ranker can be fitted later from prior seasons
only and then applied to one untouched future season.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
import math
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_combined_frontier_reportfolio_v1 as frontier,
)
from nfl_dfs.research import (
    corpus_r6_combined_population_all_block_v1 as combined,
)
from nfl_dfs.research import (
    corpus_r6_v2_matchup_candidate_analysis_controller_v1 as score_free,
)


VERSION: Final = "corpus-r6-broad-admission-tournament-v1"
SLATE_FREEZE_SCHEMA: Final = "corpus-r6-broad-admission-slate-freeze/v1"
ADMISSION_SCHEMA: Final = "corpus-r6-broad-admission/v1"
RANKER_SCHEMA: Final = "corpus-r6-broad-admission-ridge-ranker/v1"
BLEND_SCHEMA: Final = "corpus-r6-broad-admission-fixed-budget-blend/v1"
GRADE_SCHEMA: Final = "corpus-r6-broad-admission-retention-grade/v1"
ADMISSION_BUDGETS: Final = (250, 500)
THRESHOLDS: Final = (194, 200, 210, 220, 230, 240)
SOURCE_ORDER: Final = tuple(combined.SOURCE_ORDER)
REFERENCE_ADMISSION_ID: Final = "modeled-tail-reference"
QUOTA_ADMISSION_ID: Final = "source-quota-disagreement"
DIRECT_ADMISSION_ID: Final = "past-season-direct-ridge"
BLEND_LAW: Final = (
    "first-half-reference-then-first-half-novel-challenger-v1"
)
REFERENCE_LAW: Final = (
    "complete-union-modeled-tail-lexicographic-float64-v2"
)
PARENT_REFERENCE_LAW: Final = frontier.SIEVE_LAW
RIDGE_PENALTY: Final = 10.0
SLATE_TOTAL_SAMPLE_WEIGHT: Final = 500.0
WALK_FORWARD_TARGET_SEASONS: Final = (2024, 2025)
HISTORICAL_PANEL_WEEKS: Final = tuple(range(1, 19))
_MICRO: Final = 1_000_000
_RARITY_MICRO: Final = 1_000_000_000
_QUOTA_BASIS_POINTS: Final = {
    "exclusive-per-source": 400,
    "inclusive-per-source": 400,
    "multi-source-consensus": 1_000,
    "rare-source-detail": 1_000,
}
_UNION_LINEUP_FIELDS: Final = frozenset({
    "lineup_id", "roster_player_ids", "source_population_ids",
    "source_population_count", "source_lineup_ids_by_population",
    "source_occurrence_counts_by_population", "source_detail_ids_by_population",
})
_FEATURE_FIELDS: Final = frozenset({
    "lineup_id", "source_population_ids", "source_population_count",
    "exclusive_source_id", "source_occurrence_total", "source_occurrence_max",
    "source_detail_count", "source_detail_rarity_micro",
    "source_detail_rarity_components",
    *(f"strict_gt_{threshold}_world_count" for threshold in THRESHOLDS),
    "modeled_mean_micro", "modeled_mean_float64_hex", "modeled_std_micro",
    "reference_rank",
})
_FREEZE_FIELDS: Final = frozenset({
    "schema_version", "version", "slate", "source_binding",
    "source_binding_sha256", "source_order", "candidate_count",
    "candidate_lineup_ids_sha256", "modeled_score_matrix_sha256",
    "modeled_score_shape", "world_count", "threshold_operator", "thresholds",
    "reference_law", "parent_a250_reference_law", "feature_names",
    "candidate_features", "candidate_features_sha256", "admission_budgets",
    "uses_realized_outcomes", "candidate_generation_performed",
    "world_generation_performed", "k80_selection_performed",
    "full_union_oracle_is_training_target", "production_change_licensed",
    "slate_freeze_sha256",
})


class CorpusR6BroadAdmissionTournamentV1Error(ValueError):
    """The fixed-corpus admission estimand or its inputs differed."""


def _fail(message: str) -> None:
    raise CorpusR6BroadAdmissionTournamentV1Error(message)


def _canonical(value: object) -> bytes:
    return batch.canonical_json_bytes(value)


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except Exception as exc:
        raise CorpusR6BroadAdmissionTournamentV1Error(
            f"{label} is not one generation-exact object identity"
        ) from exc


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    return {**body, field: _hash(body)}


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _slate(value: object) -> dict[str, object]:
    item = _mapping(value, label="slate")
    if set(item) != {"season", "week", "slate_id"}:
        _fail("slate fields differ")
    season, week, slate_id = item["season"], item["week"], item["slate_id"]
    if (
        type(season) is not int
        or type(week) is not int
        or not 1 <= week <= 18
        or slate_id != f"{season}-w{week:02d}"
    ):
        _fail("slate values differ")
    return item


def _candidate_rows(value: object) -> list[dict[str, object]]:
    rows = [
        _mapping(row, label=f"candidate[{ordinal}]")
        for ordinal, row in enumerate(_sequence(value, label="candidates"))
    ]
    if len(rows) <= max(ADMISSION_BUDGETS):
        _fail("fixed corpus must exceed the largest admission budget")
    seen: set[str] = set()
    normalized: list[dict[str, object]] = []
    for row in rows:
        if set(row) != _UNION_LINEUP_FIELDS:
            _fail("candidate fields differ from the combined R6 union")
        lineup_id = row["lineup_id"]
        roster = _sequence(row["roster_player_ids"], label="candidate roster")
        sources = _sequence(row["source_population_ids"], label="candidate sources")
        source_lineups = _mapping(
            row["source_lineup_ids_by_population"], label="source lineup IDs",
        )
        occurrences = _mapping(
            row["source_occurrence_counts_by_population"],
            label="source occurrence counts",
        )
        details = _mapping(
            row["source_detail_ids_by_population"], label="source detail IDs",
        )
        expected_sources = [source for source in SOURCE_ORDER if source in sources]
        if (
            type(lineup_id) is not str
            or not lineup_id
            or lineup_id in seen
            or any(type(value) is not str or not value for value in roster)
            or len(roster) != 9
            or roster != sorted(set(roster))
            or any(type(value) is not str or not value for value in sources)
            or sources != expected_sources
            or not sources
            or row["source_population_count"] != len(sources)
            or list(source_lineups) != sources
            or list(occurrences) != sources
            or list(details) != sources
            or any(type(occurrences[source]) is not int or occurrences[source] < 1
                   for source in sources)
            or any(
                type(source_lineups[source]) is not str
                or not source_lineups[source]
                for source in sources
            )
            or any(
                _sequence(
                    details[source], label="source details",
                )
                != sorted(set(details[source]))
                or not details[source]
                or any(
                    type(item) is not str or not item
                    for item in details[source]
                )
                for source in sources
            )
        ):
            _fail("candidate values differ from the combined R6 union")
        seen.add(lineup_id)
        normalized.append(row)
    if [str(row["lineup_id"]) for row in normalized] != sorted(seen):
        _fail("combined candidate order must be stable lineup-ID order")
    return normalized


def _matrix(value: object, *, row_count: int) -> np.ndarray:
    scores = np.asarray(value)
    if (
        scores is not value
        or scores.dtype != np.dtype(np.float64)
        or not scores.flags.c_contiguous
        or scores.ndim != 2
        or scores.shape[0] != row_count
        or scores.shape[1] < 1
        or not np.isfinite(scores).all()
    ):
        _fail("modeled score matrix differs")
    return scores


def _feature_names() -> tuple[str, ...]:
    return (
        *(f"modeled_gt_{threshold}_rate" for threshold in THRESHOLDS),
        "modeled_mean_points", "modeled_std_points", "reference_rank_fraction",
        "source_population_share", "source_occurrence_log1p",
        "source_detail_count", "source_detail_rarity",
        *(f"member::{source}" for source in SOURCE_ORDER),
        *(f"exclusive::{source}" for source in SOURCE_ORDER),
    )


FEATURE_NAMES: Final = _feature_names()
_RANKER_FIELDS: Final = frozenset({
    "schema_version", "version", "target_season", "training_seasons",
    "training_slates", "training_slate_count", "training_candidate_count",
    "training_bindings", "training_bindings_sha256", "feature_names",
    "feature_mean_hex", "feature_scale_hex", "feature_standardization",
    "coefficient_hex", "ridge_penalty",
    "target", "top_five_percent_weight",
    "same_slate_hard_negative_definition", "same_slate_hard_negative_weight",
    "slate_total_sample_weight", "each_training_slate_has_equal_total_weight",
    "future_or_target_season_rows_used", "automatic_policy_promotion",
    "ranker_sha256",
})


def _numeric_features(
    row: Mapping[str, object], *, world_count: int, candidate_count: int,
) -> np.ndarray:
    sources = set(str(value) for value in row["source_population_ids"])
    exclusive = row["exclusive_source_id"]
    values = [
        float(row[f"strict_gt_{threshold}_world_count"]) / world_count
        for threshold in THRESHOLDS
    ]
    values.extend((
        float(row["modeled_mean_micro"]) / _MICRO,
        float(row["modeled_std_micro"]) / _MICRO,
        float(row["reference_rank"]) / max(1, candidate_count - 1),
        float(row["source_population_count"]) / len(SOURCE_ORDER),
        math.log1p(float(row["source_occurrence_total"])),
        float(row["source_detail_count"]),
        float(row["source_detail_rarity_micro"]) / _RARITY_MICRO,
    ))
    values.extend(1.0 if source in sources else 0.0 for source in SOURCE_ORDER)
    values.extend(1.0 if exclusive == source else 0.0 for source in SOURCE_ORDER)
    retained = np.asarray(values, dtype=np.float64)
    if retained.shape != (len(FEATURE_NAMES),) or not np.isfinite(retained).all():
        _fail("numeric admission feature vector differs")
    return retained


def freeze_slate_inputs_v1(
    *, slate: Mapping[str, object], candidates: Sequence[Mapping[str, object]],
    modeled_score_matrix: np.ndarray, source_binding: Mapping[str, object],
) -> dict[str, object]:
    """Freeze score-free candidate evidence for both admission budgets."""

    retained_slate = _slate(slate)
    rows = _candidate_rows(candidates)
    scores = _matrix(modeled_score_matrix, row_count=len(rows))
    binding = _mapping(source_binding, label="source binding")
    if not binding:
        _fail("source binding is empty")

    detail_frequency: Counter[tuple[str, str]] = Counter()
    for row in rows:
        for source in row["source_population_ids"]:
            for detail in row["source_detail_ids_by_population"][source]:
                detail_frequency[(str(source), str(detail))] += 1

    threshold_counts = {
        threshold: np.count_nonzero(scores > float(threshold), axis=1)
        for threshold in THRESHOLDS
    }
    means = scores.mean(axis=1, dtype=np.float64)
    stds = scores.std(axis=1, dtype=np.float64)
    evidence: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        sources = [str(value) for value in row["source_population_ids"]]
        details = [
            (source, str(detail))
            for source in sources
            for detail in row["source_detail_ids_by_population"][source]
        ]
        rarity_components = [{
            "source_id": source,
            "detail_id": detail,
            "corpus_count": detail_frequency[(source, detail)],
            "inverse_frequency_micro": int(round(
                _RARITY_MICRO / detail_frequency[(source, detail)]
            )),
        } for source, detail in details]
        occurrences = row["source_occurrence_counts_by_population"]
        evidence.append({
            "lineup_id": row["lineup_id"],
            "source_population_ids": sources,
            "source_population_count": len(sources),
            "exclusive_source_id": sources[0] if len(sources) == 1 else None,
            "source_occurrence_total": sum(int(occurrences[s]) for s in sources),
            "source_occurrence_max": max(int(occurrences[s]) for s in sources),
            "source_detail_count": len(details),
            "source_detail_rarity_micro": sum(
                int(component["inverse_frequency_micro"])
                for component in rarity_components
            ),
            "source_detail_rarity_components": rarity_components,
            **{
                f"strict_gt_{threshold}_world_count": int(
                    threshold_counts[threshold][index]
                )
                for threshold in THRESHOLDS
            },
            "modeled_mean_micro": int(round(float(means[index]) * _MICRO)),
            "modeled_mean_float64_hex": float(means[index]).hex(),
            "modeled_std_micro": int(round(float(stds[index]) * _MICRO)),
        })
    reference_indices = sorted(
        range(len(evidence)),
        key=lambda index: (
            *(
                -int(evidence[index][f"strict_gt_{threshold}_world_count"])
                for threshold in (230, 220, 210, 200)
            ),
            -float.fromhex(str(evidence[index]["modeled_mean_float64_hex"])),
            str(evidence[index]["lineup_id"]),
        ),
    )
    rank_by_index = {index: rank for rank, index in enumerate(reference_indices)}
    evidence = [
        {**row, "reference_rank": rank_by_index[index]}
        for index, row in enumerate(evidence)
    ]
    body = {
        "schema_version": SLATE_FREEZE_SCHEMA,
        "version": VERSION,
        "slate": retained_slate,
        "source_binding": binding,
        "source_binding_sha256": _hash(binding),
        "source_order": list(SOURCE_ORDER),
        "candidate_count": len(rows),
        "candidate_lineup_ids_sha256": _hash([
            row["lineup_id"] for row in rows
        ]),
        "modeled_score_matrix_sha256": combined._score_matrix_sha256(scores),
        "modeled_score_shape": list(scores.shape),
        "world_count": int(scores.shape[1]),
        "threshold_operator": ">",
        "thresholds": list(THRESHOLDS),
        "reference_law": REFERENCE_LAW,
        "parent_a250_reference_law": PARENT_REFERENCE_LAW,
        "feature_names": list(FEATURE_NAMES),
        "candidate_features": evidence,
        "candidate_features_sha256": _hash(evidence),
        "admission_budgets": list(ADMISSION_BUDGETS),
        "uses_realized_outcomes": False,
        "candidate_generation_performed": False,
        "world_generation_performed": False,
        "k80_selection_performed": False,
        "full_union_oracle_is_training_target": False,
        "production_change_licensed": False,
    }
    try:
        score_free.reject_outcome_carriers_v1(
            body, label="broad-admission score-free freeze"
        )
    except Exception as exc:
        raise CorpusR6BroadAdmissionTournamentV1Error(
            f"score-free freeze carries outcome authority: {exc}"
        ) from exc
    return _with_hash(body, field="slate_freeze_sha256")


def freeze_combined_slate_inputs_v1(
    *, combined_result: Mapping[str, object],
    all_block_score_matrix: np.ndarray, source_ordinal: int,
) -> dict[str, object]:
    """Adapt one deeply validated combined R6 result into the pure seam."""

    result, rows, scores = frontier._validated_parent_v1(
        combined_result=combined_result,
        all_block_score_matrix=all_block_score_matrix,
        source_ordinal=source_ordinal,
    )
    union = _mapping(result["union"], label="combined union")
    return freeze_slate_inputs_v1(
        slate=_mapping(union["slate"], label="combined slate"),
        candidates=rows,
        modeled_score_matrix=scores,
        source_binding={
            "combined_result_sha256": result["result_sha256"],
            "combined_union_sha256": union["union_sha256"],
            "combined_matrix_binding_sha256": result["matrix_binding_sha256"],
            "later_source_identity": union["later_source_identity"],
            "source_ordinal": source_ordinal,
        },
    )


def _validated_freeze(value: object) -> dict[str, object]:
    item = _mapping(value, label="admission slate freeze")
    try:
        score_free.reject_outcome_carriers_v1(
            item, label="broad-admission score-free freeze"
        )
    except Exception as exc:
        raise CorpusR6BroadAdmissionTournamentV1Error(
            f"score-free freeze carries outcome authority: {exc}"
        ) from exc
    source_binding = item.get("source_binding")
    if (
        set(item) != _FREEZE_FIELDS
        or item.get("schema_version") != SLATE_FREEZE_SCHEMA
        or item.get("version") != VERSION
        or _slate(item.get("slate")) != item.get("slate")
        or not isinstance(source_binding, Mapping)
        or not source_binding
        or item.get("source_binding_sha256") != _hash(source_binding)
        or item.get("source_order") != list(SOURCE_ORDER)
        or item.get("admission_budgets") != list(ADMISSION_BUDGETS)
        or item.get("threshold_operator") != ">"
        or item.get("thresholds") != list(THRESHOLDS)
        or item.get("reference_law") != REFERENCE_LAW
        or item.get("parent_a250_reference_law") != PARENT_REFERENCE_LAW
        or item.get("feature_names") != list(FEATURE_NAMES)
        or item.get("uses_realized_outcomes") is not False
        or item.get("candidate_generation_performed") is not False
        or item.get("world_generation_performed") is not False
        or item.get("k80_selection_performed") is not False
        or item.get("full_union_oracle_is_training_target") is not False
        or item.get("production_change_licensed") is not False
        or item.get("slate_freeze_sha256")
        != _hash({key: val for key, val in item.items()
                  if key != "slate_freeze_sha256"})
    ):
        _fail("admission slate freeze authority differs")
    rows = _sequence(item.get("candidate_features"), label="candidate features")
    world_count = item.get("world_count")
    if (
        item.get("candidate_count") != len(rows)
        or len(rows) <= max(ADMISSION_BUDGETS)
        or item.get("candidate_features_sha256") != _hash(rows)
        or type(world_count) is not int
        or world_count < 1
        or item.get("modeled_score_shape") != [len(rows), world_count]
        or not _is_sha256(item.get("candidate_lineup_ids_sha256"))
        or not _is_sha256(item.get("modeled_score_matrix_sha256"))
    ):
        _fail("admission slate freeze candidates differ")
    normalized_rows: list[dict[str, object]] = []
    for ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"candidate feature[{ordinal}]")
        if set(row) != _FEATURE_FIELDS:
            _fail("admission feature fields differ")
        lineup_id = row["lineup_id"]
        sources = _sequence(
            row["source_population_ids"], label="admission feature sources"
        )
        expected_sources = [source for source in SOURCE_ORDER if source in sources]
        threshold_counts = [
            row[f"strict_gt_{threshold}_world_count"] for threshold in THRESHOLDS
        ]
        raw_components = _sequence(
            row["source_detail_rarity_components"],
            label="source detail rarity components",
        )
        components: list[dict[str, object]] = []
        for raw_component in raw_components:
            component = _mapping(raw_component, label="source detail rarity component")
            if set(component) != {
                "source_id", "detail_id", "corpus_count",
                "inverse_frequency_micro",
            }:
                _fail("source detail rarity component fields differ")
            corpus_count = component["corpus_count"]
            if (
                component["source_id"] not in sources
                or type(component["detail_id"]) is not str
                or not component["detail_id"]
                or type(corpus_count) is not int
                or corpus_count < 1
                or component["inverse_frequency_micro"]
                != int(round(_RARITY_MICRO / corpus_count))
            ):
                _fail("source detail rarity component values differ")
            components.append(component)
        try:
            exact_mean = float.fromhex(row["modeled_mean_float64_hex"])
        except (TypeError, ValueError):
            _fail("admission exact modeled mean differs")
        if (
            type(lineup_id) is not str
            or not lineup_id
            or any(type(source) is not str for source in sources)
            or sources != expected_sources
            or not sources
            or row["source_population_count"] != len(sources)
            or row["exclusive_source_id"]
            != (sources[0] if len(sources) == 1 else None)
            or type(row["source_occurrence_total"]) is not int
            or type(row["source_occurrence_max"]) is not int
            or row["source_occurrence_total"] < row["source_occurrence_max"]
            or row["source_occurrence_max"] < 1
            or type(row["source_detail_count"]) is not int
            or row["source_detail_count"] != len(components)
            or row["source_detail_count"] < len(sources)
            or type(row["source_detail_rarity_micro"]) is not int
            or row["source_detail_rarity_micro"]
            != sum(int(component["inverse_frequency_micro"])
                   for component in components)
            or components != sorted(
                components,
                key=lambda component: (
                    SOURCE_ORDER.index(str(component["source_id"])),
                    str(component["detail_id"]),
                ),
            )
            or len({
                (component["source_id"], component["detail_id"])
                for component in components
            }) != len(components)
            or any(type(count) is not int or not 0 <= count <= world_count
                   for count in threshold_counts)
            or threshold_counts != sorted(threshold_counts, reverse=True)
            or type(row["modeled_mean_micro"]) is not int
            or not math.isfinite(exact_mean)
            or int(round(exact_mean * _MICRO)) != row["modeled_mean_micro"]
            or type(row["modeled_std_micro"]) is not int
            or row["modeled_std_micro"] < 0
            or type(row["reference_rank"]) is not int
        ):
            _fail("admission feature values differ")
        normalized_rows.append(row)
    ranks = [row["reference_rank"] for row in normalized_rows]
    ids = [row["lineup_id"] for row in normalized_rows]
    replayed = sorted(
        range(len(normalized_rows)),
        key=lambda index: (
            *(
                -int(normalized_rows[index][
                    f"strict_gt_{threshold}_world_count"
                ])
                for threshold in (230, 220, 210, 200)
            ),
            -float.fromhex(str(normalized_rows[index][
                "modeled_mean_float64_hex"
            ])),
            str(normalized_rows[index]["lineup_id"]),
        ),
    )
    replayed_rank_by_index = {
        index: rank for rank, index in enumerate(replayed)
    }
    if (
        sorted(ranks) != list(range(len(rows)))
        or ids != sorted(ids)
        or len(set(ids)) != len(rows)
        or item.get("candidate_lineup_ids_sha256") != _hash(ids)
        or any(
            row["reference_rank"] != replayed_rank_by_index[index]
            for index, row in enumerate(normalized_rows)
        )
    ):
        _fail("admission reference rank differs")
    return item


def _admission(
    *, slate_freeze: Mapping[str, object], admission_id: str, budget: int,
    selected: Sequence[str], trace: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    item = _validated_freeze(slate_freeze)
    rows = _sequence(item["candidate_features"], label="candidate features")
    eligible = {str(row["lineup_id"]) for row in rows if isinstance(row, Mapping)}
    ids = [str(value) for value in selected]
    retained_trace = [dict(row) for row in trace]
    if (
        budget not in ADMISSION_BUDGETS
        or len(ids) != budget
        or len(set(ids)) != budget
        or not set(ids) <= eligible
        or len(retained_trace) != budget
        or [row.get("lineup_id") for row in retained_trace] != ids
    ):
        _fail("fixed-budget admission differs")
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "version": VERSION,
        "slate": item["slate"],
        "slate_freeze_sha256": item["slate_freeze_sha256"],
        "admission_id": admission_id,
        "admission_budget": budget,
        "selected_lineup_ids": ids,
        "selected_lineup_ids_sha256": _hash(ids),
        "selection_trace": retained_trace,
        "selection_trace_sha256": _hash(retained_trace),
        "candidate_generation_performed": False,
        "uses_realized_outcomes": False,
        "past_season_labels_used": False,
        "target_slate_labels_used": False,
        "k80_selection_performed": False,
        "automatic_policy_promotion": False,
    }
    return _with_hash(body, field="admission_sha256")


def build_reference_admission_v1(
    slate_freeze: Mapping[str, object], *, budget: int,
) -> dict[str, object]:
    item = _validated_freeze(slate_freeze)
    rows = sorted(
        (dict(row) for row in item["candidate_features"]),
        key=lambda row: int(row["reference_rank"]),
    )[:budget]
    return _admission(
        slate_freeze=item,
        admission_id=REFERENCE_ADMISSION_ID,
        budget=budget,
        selected=[str(row["lineup_id"]) for row in rows],
        trace=[{
            "selection_rank": rank,
            "lineup_id": row["lineup_id"],
            "selection_stratum": "modeled-tail-reference",
            "stratum_rank": rank,
            "reference_rank": row["reference_rank"],
        } for rank, row in enumerate(rows)],
    )


def build_quota_admission_v1(
    slate_freeze: Mapping[str, object], *, budget: int,
) -> dict[str, object]:
    item = _validated_freeze(slate_freeze)
    if budget not in ADMISSION_BUDGETS:
        _fail("quota admission budget differs")
    rows = [dict(row) for row in item["candidate_features"]]
    by_id = {str(row["lineup_id"]): row for row in rows}
    reference = sorted(rows, key=lambda row: int(row["reference_rank"]))
    selected: list[str] = []
    selected_set: set[str] = set()
    trace: list[dict[str, object]] = []
    quota_census: list[dict[str, object]] = []

    def take(
        *, stratum: str, requested: int,
        ordered: Sequence[Mapping[str, object]],
    ) -> None:
        if requested < 0:
            _fail("quota stratum request differs")
        eligible_before_deduplication = len(ordered)
        available_lineup_ids = [
            str(candidate["lineup_id"])
            for candidate in ordered
            if str(candidate["lineup_id"]) not in selected_set
        ]
        delivered = 0
        if requested > 0:
            for candidate in ordered:
                lineup_id = str(candidate["lineup_id"])
                if lineup_id in selected_set:
                    continue
                selected_set.add(lineup_id)
                selected.append(lineup_id)
                trace_row = {
                    "selection_rank": len(selected) - 1,
                    "lineup_id": lineup_id,
                    "selection_stratum": stratum,
                    "stratum_rank": delivered,
                    "reference_rank": candidate["reference_rank"],
                }
                if "_quota_novelty_micro" in candidate:
                    trace_row["new_detail_rarity_micro"] = candidate[
                        "_quota_novelty_micro"
                    ]
                trace.append(trace_row)
                delivered += 1
                if delivered == requested or len(selected) == budget:
                    break
        quota_census.append({
            "selection_stratum": stratum,
            "requested": requested,
            "eligible_before_deduplication": eligible_before_deduplication,
            "available_after_prior_strata": len(available_lineup_ids),
            "available_after_prior_strata_sha256": _hash(available_lineup_ids),
            "delivered": delivered,
            "shortfall": requested - delivered,
        })

    per_source_exclusive = (
        budget * _QUOTA_BASIS_POINTS["exclusive-per-source"] // 10_000
    )
    per_source_inclusive = (
        budget * _QUOTA_BASIS_POINTS["inclusive-per-source"] // 10_000
    )
    for source in SOURCE_ORDER:
        take(
            stratum=f"exclusive::{source}", requested=per_source_exclusive,
            ordered=[row for row in reference
                     if row["exclusive_source_id"] == source],
        )
    for source in SOURCE_ORDER:
        take(
            stratum=f"member::{source}", requested=per_source_inclusive,
            ordered=[row for row in reference
                     if source in row["source_population_ids"]],
        )
    take(
        stratum="multi-source-consensus",
        requested=(
            budget * _QUOTA_BASIS_POINTS["multi-source-consensus"] // 10_000
        ),
        ordered=sorted(
            (row for row in rows if int(row["source_population_count"]) >= 2),
            key=lambda row: (
                -int(row["source_population_count"]),
                int(row["reference_rank"]),
            ),
        ),
    )

    covered_details = {
        (str(component["source_id"]), str(component["detail_id"]))
        for lineup_id in selected
        for component in by_id[lineup_id]["source_detail_rarity_components"]
    }
    rare_order: list[dict[str, object]] = []
    rare_remaining = [
        dict(row) for row in rows if str(row["lineup_id"]) not in selected_set
    ]
    while rare_remaining:
        def novelty(candidate: Mapping[str, object]) -> int:
            return sum(
                int(component["inverse_frequency_micro"])
                for component in candidate["source_detail_rarity_components"]
                if (
                    str(component["source_id"]),
                    str(component["detail_id"]),
                ) not in covered_details
            )

        chosen = min(
            rare_remaining,
            key=lambda row: (
                -novelty(row),
                int(row["reference_rank"]),
                str(row["lineup_id"]),
            ),
        )
        chosen_novelty = novelty(chosen)
        chosen["_quota_novelty_micro"] = chosen_novelty
        rare_order.append(chosen)
        covered_details.update(
            (str(component["source_id"]), str(component["detail_id"]))
            for component in chosen["source_detail_rarity_components"]
        )
        rare_remaining.remove(chosen)
    take(
        stratum="rare-source-detail",
        requested=budget * _QUOTA_BASIS_POINTS["rare-source-detail"] // 10_000,
        ordered=rare_order,
    )
    take(
        stratum="modeled-tail-reference-fill",
        requested=budget - len(selected),
        ordered=reference,
    )
    if len(selected) != budget or any(lineup_id not in by_id for lineup_id in selected):
        _fail("quota admission could not satisfy its fixed budget")
    result = _admission(
        slate_freeze=item,
        admission_id=QUOTA_ADMISSION_ID,
        budget=budget,
        selected=selected,
        trace=trace,
    )
    result["quota_policy"] = {
        "basis_points": dict(_QUOTA_BASIS_POINTS),
        "source_order": list(SOURCE_ORDER),
        "availability_census": quota_census,
        "availability_census_sha256": _hash(quota_census),
        "quota_sizes_use_fixed_budget_not_outcomes": True,
        "shortfalls_fill_by_reference_order": True,
    }
    result["quota_policy_sha256"] = _hash(result["quota_policy"])
    result["admission_sha256"] = _hash({
        key: value for key, value in result.items() if key != "admission_sha256"
    })
    return result


def _rank_percentiles(
    scores: Mapping[str, int], *, lineup_ids: Sequence[str],
) -> dict[str, float]:
    if set(scores) != set(lineup_ids) or any(type(value) is not int for value in scores.values()):
        _fail("training realized-score coverage differs")
    ordered = sorted(lineup_ids, key=lambda lineup_id: (scores[lineup_id], lineup_id))
    denominator = max(1, len(ordered) - 1)
    percentiles: dict[str, float] = {}
    start = 0
    while start < len(ordered):
        stop = start + 1
        while stop < len(ordered) and scores[ordered[stop]] == scores[ordered[start]]:
            stop += 1
        average_rank = (start + stop - 1) / 2.0
        for lineup_id in ordered[start:stop]:
            percentiles[lineup_id] = average_rank / denominator
        start = stop
    return percentiles


def _expected_walk_forward_training_slates(target_season: int) -> list[str]:
    return [
        f"{season}-w{week:02d}"
        for season in range(2023, target_season)
        for week in HISTORICAL_PANEL_WEEKS
    ]


def fit_past_season_direct_ranker_v1(
    *, training: Sequence[
        tuple[
            Mapping[str, object], Mapping[str, int], Mapping[str, object]
        ]
    ],
    target_season: int,
    expected_training_slate_ids: Sequence[str],
) -> dict[str, object]:
    """Fit one transparent listwise ridge model from earlier seasons only."""

    expected_slates = _sequence(
        expected_training_slate_ids, label="expected training slate IDs"
    )
    if (
        type(target_season) is not int
        or target_season not in WALK_FORWARD_TARGET_SEASONS
    ):
        _fail("direct-ranker target season differs")
    frozen_expected_slates = _expected_walk_forward_training_slates(target_season)
    if (
        any(type(slate_id) is not str or not slate_id for slate_id in expected_slates)
        or expected_slates != sorted(set(expected_slates))
        or expected_slates != frozen_expected_slates
    ):
        _fail("direct-ranker target season differs")
    matrices: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    weights: list[np.ndarray] = []
    training_slates: list[str] = []
    training_seasons: set[int] = set()
    training_bindings: list[dict[str, object]] = []
    prepared: list[
        tuple[dict[str, object], dict[str, int], dict[str, object]]
    ] = []
    for raw_entry in training:
        if not isinstance(raw_entry, Sequence) or len(raw_entry) != 3:
            _fail("direct-ranker training entry differs")
        raw_freeze, raw_scores, raw_outcome_identity = raw_entry
        freeze = _validated_freeze(raw_freeze)
        slate = _slate(freeze["slate"])
        realized = {
            str(key): value
            for key, value in _mapping(
                raw_scores, label="training realized scores"
            ).items()
        }
        outcome_identity = _identity(
            raw_outcome_identity, label="training outcome identity"
        )
        prepared.append((freeze, realized, outcome_identity))
    prepared.sort(key=lambda entry: str(entry[0]["slate"]["slate_id"]))
    for freeze, realized, outcome_identity in prepared:
        slate = _slate(freeze["slate"])
        if slate["season"] >= target_season or slate["slate_id"] in training_slates:
            _fail("direct ranker must fit distinct past-season slates only")
        rows = [dict(row) for row in freeze["candidate_features"]]
        lineup_ids = [str(row["lineup_id"]) for row in rows]
        percentiles = _rank_percentiles(realized, lineup_ids=lineup_ids)
        x = np.vstack([
            _numeric_features(
                row,
                world_count=int(freeze["world_count"]),
                candidate_count=len(rows),
            )
            for row in rows
        ])
        y = np.asarray([percentiles[lineup_id] for lineup_id in lineup_ids])
        reference_top = np.asarray([
            int(row["reference_rank"]) < max(1, math.ceil(len(rows) * 0.10))
            for row in rows
        ])
        top_positive = y >= 0.95
        hard_negative = reference_top & (y < 0.50)
        sample_weight = (
            np.ones(len(rows), dtype=np.float64)
            + 4.0 * top_positive.astype(np.float64)
            + 2.0 * hard_negative.astype(np.float64)
        )
        sample_weight *= SLATE_TOTAL_SAMPLE_WEIGHT / sample_weight.sum()
        matrices.append(x)
        targets.append(y)
        weights.append(sample_weight)
        training_slates.append(str(slate["slate_id"]))
        training_seasons.add(int(slate["season"]))
        training_bindings.append({
            "slate_id": slate["slate_id"],
            "slate_freeze_sha256": freeze["slate_freeze_sha256"],
            "candidate_count": len(rows),
            "realized_scores_sha256": _hash(realized),
            "outcome_identity": outcome_identity,
            "outcome_identity_sha256": _hash(outcome_identity),
            "sample_weight_sum_hex": float(sample_weight.sum()).hex(),
        })
    if not matrices:
        _fail("direct ranker requires at least one past-season slate")
    expected_seasons = list(range(2023, target_season))
    if (
        training_slates != expected_slates
        or sorted(training_seasons) != expected_seasons
        or any(
            not any(
                str(slate_id).startswith(f"{season}-w")
                for slate_id in training_slates
            )
            for season in expected_seasons
        )
    ):
        _fail("direct ranker walk-forward fold differs")
    x_all = np.vstack(matrices)
    y_all = np.concatenate(targets)
    weight_all = np.concatenate(weights)
    total_weight = weight_all.sum(dtype=np.float64)
    means = np.sum(
        x_all * weight_all[:, None], axis=0, dtype=np.float64
    ) / total_weight
    variances = np.sum(
        ((x_all - means) ** 2) * weight_all[:, None],
        axis=0,
        dtype=np.float64,
    ) / total_weight
    scales = np.sqrt(variances)
    scales[scales < 1e-12] = 1.0
    standardized = (x_all - means) / scales
    design = np.column_stack((np.ones(len(x_all)), standardized))
    root_weight = np.sqrt(weight_all)
    weighted_x = design * root_weight[:, None]
    weighted_y = y_all * root_weight
    penalty = np.eye(design.shape[1], dtype=np.float64) * RIDGE_PENALTY
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(
        weighted_x.T @ weighted_x + penalty,
        weighted_x.T @ weighted_y,
    )
    if not np.isfinite(coefficients).all():
        _fail("direct-ranker coefficients are not finite")
    body = {
        "schema_version": RANKER_SCHEMA,
        "version": VERSION,
        "target_season": target_season,
        "training_seasons": sorted(training_seasons),
        "training_slates": sorted(training_slates),
        "training_slate_count": len(training_slates),
        "training_candidate_count": int(len(x_all)),
        "training_bindings": training_bindings,
        "training_bindings_sha256": _hash(training_bindings),
        "feature_names": list(FEATURE_NAMES),
        "feature_mean_hex": [float(value).hex() for value in means],
        "feature_scale_hex": [float(value).hex() for value in scales],
        "feature_standardization": "equal-slate-sample-weighted-mean-variance",
        "coefficient_hex": [float(value).hex() for value in coefficients],
        "ridge_penalty": RIDGE_PENALTY,
        "target": "within-slate-realized-score-percentile",
        "top_five_percent_weight": 5.0,
        "same_slate_hard_negative_definition": (
            "reference-top-decile-and-realized-below-median"
        ),
        "same_slate_hard_negative_weight": 3.0,
        "slate_total_sample_weight": SLATE_TOTAL_SAMPLE_WEIGHT,
        "each_training_slate_has_equal_total_weight": True,
        "future_or_target_season_rows_used": False,
        "automatic_policy_promotion": False,
    }
    return _with_hash(body, field="ranker_sha256")


def build_direct_ranker_admission_v1(
    slate_freeze: Mapping[str, object], *, ranker: Mapping[str, object],
    budget: int,
) -> dict[str, object]:
    freeze = _validated_freeze(slate_freeze)
    model = _mapping(ranker, label="direct admission ranker")
    slate = _slate(freeze["slate"])
    if (
        set(model) != _RANKER_FIELDS
        or model.get("schema_version") != RANKER_SCHEMA
        or model.get("version") != VERSION
        or model.get("target_season") != slate["season"]
        or model.get("feature_names") != list(FEATURE_NAMES)
        or model.get("feature_standardization")
        != "equal-slate-sample-weighted-mean-variance"
        or model.get("ridge_penalty") != RIDGE_PENALTY
        or model.get("target") != "within-slate-realized-score-percentile"
        or model.get("top_five_percent_weight") != 5.0
        or model.get("same_slate_hard_negative_definition")
        != "reference-top-decile-and-realized-below-median"
        or model.get("same_slate_hard_negative_weight") != 3.0
        or model.get("slate_total_sample_weight") != SLATE_TOTAL_SAMPLE_WEIGHT
        or model.get("each_training_slate_has_equal_total_weight") is not True
        or model.get("ranker_sha256")
        != _hash({key: value for key, value in model.items()
                  if key != "ranker_sha256"})
    ):
        _fail("direct admission ranker authority differs")
    training_seasons = _sequence(
        model.get("training_seasons"), label="ranker training seasons"
    )
    training_slates = _sequence(
        model.get("training_slates"), label="ranker training slates"
    )
    training_bindings = _sequence(
        model.get("training_bindings"), label="ranker training bindings"
    )
    validated_bindings: list[dict[str, object]] = []
    for raw_binding in training_bindings:
        binding = _mapping(raw_binding, label="ranker training binding")
        outcome_identity = binding.get("outcome_identity")
        normalized_outcome_identity = _identity(
            outcome_identity, label="ranker training outcome identity"
        )
        try:
            sample_weight_sum = float.fromhex(binding.get("sample_weight_sum_hex"))
        except (TypeError, ValueError):
            _fail("direct admission ranker training binding differs")
        if (
            set(binding) != {
                "slate_id", "slate_freeze_sha256", "candidate_count",
                "realized_scores_sha256", "outcome_identity",
                "outcome_identity_sha256", "sample_weight_sum_hex",
            }
            or type(binding.get("slate_id")) is not str
            or not _is_sha256(binding.get("slate_freeze_sha256"))
            or not _is_sha256(binding.get("realized_scores_sha256"))
            or type(binding.get("candidate_count")) is not int
            or binding.get("candidate_count") <= max(ADMISSION_BUDGETS)
            or outcome_identity != normalized_outcome_identity
            or binding.get("outcome_identity_sha256") != _hash(outcome_identity)
            or not math.isclose(
                sample_weight_sum,
                SLATE_TOTAL_SAMPLE_WEIGHT,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
        ):
            _fail("direct admission ranker training binding differs")
        validated_bindings.append(binding)
    if (
        not training_seasons
        or any(type(season) is not int for season in training_seasons)
        or training_seasons != sorted(set(training_seasons))
        or training_seasons != list(range(2023, int(slate["season"])))
        or slate["season"] not in WALK_FORWARD_TARGET_SEASONS
        or training_seasons[-1] >= slate["season"]
        or any(type(slate_id) is not str for slate_id in training_slates)
        or training_slates != sorted(set(training_slates))
        or training_slates
        != _expected_walk_forward_training_slates(int(slate["season"]))
        or model.get("training_slate_count") != len(training_slates)
        or type(model.get("training_candidate_count")) is not int
        or model.get("training_candidate_count")
        != sum(int(binding["candidate_count"])
               for binding in validated_bindings)
        or len(validated_bindings) != len(training_slates)
        or model.get("training_bindings_sha256") != _hash(validated_bindings)
        or [
            binding.get("slate_id")
            for binding in validated_bindings
        ] != training_slates
        or model.get("future_or_target_season_rows_used") is not False
        or model.get("automatic_policy_promotion") is not False
    ):
        _fail("direct admission ranker training authority differs")
    try:
        means = np.asarray(
            [float.fromhex(value) for value in _sequence(
                model.get("feature_mean_hex"), label="ranker feature means"
            )],
            dtype=np.float64,
        )
        scales = np.asarray(
            [float.fromhex(value) for value in _sequence(
                model.get("feature_scale_hex"), label="ranker feature scales"
            )],
            dtype=np.float64,
        )
        coefficients = np.asarray(
            [float.fromhex(value) for value in _sequence(
                model.get("coefficient_hex"), label="ranker coefficients"
            )],
            dtype=np.float64,
        )
    except (TypeError, ValueError):
        _fail("direct admission ranker numeric payload differs")
    if (
        means.shape != (len(FEATURE_NAMES),)
        or scales.shape != means.shape
        or coefficients.shape != (len(FEATURE_NAMES) + 1,)
        or not np.isfinite(means).all()
        or not np.isfinite(scales).all()
        or not np.isfinite(coefficients).all()
        or np.any(scales <= 0)
    ):
        _fail("direct admission ranker numeric payload differs")
    rows = [dict(row) for row in freeze["candidate_features"]]
    ranked: list[tuple[float, int, str, dict[str, object]]] = []
    for row in rows:
        features = _numeric_features(
            row,
            world_count=int(freeze["world_count"]),
            candidate_count=len(rows),
        )
        score = float(coefficients[0] + ((features - means) / scales) @ coefficients[1:])
        ranked.append((score, int(row["reference_rank"]), str(row["lineup_id"]), row))
    ranked.sort(key=lambda value: (-value[0], value[1], value[2]))
    selected = ranked[:budget]
    result = _admission(
        slate_freeze=freeze,
        admission_id=DIRECT_ADMISSION_ID,
        budget=budget,
        selected=[lineup_id for _score, _rank, lineup_id, _row in selected],
        trace=[{
            "selection_rank": rank,
            "lineup_id": lineup_id,
            "selection_stratum": "past-season-direct-ridge",
            "stratum_rank": rank,
            "reference_rank": reference_rank,
            "direct_score_hex": float(score).hex(),
        } for rank, (score, reference_rank, lineup_id, _row) in enumerate(selected)],
    )
    result["ranker_sha256"] = model["ranker_sha256"]
    result["ranker"] = model
    result["past_season_only"] = True
    result["uses_realized_outcomes"] = True
    result["past_season_labels_used"] = True
    result["admission_sha256"] = _hash({
        key: value for key, value in result.items() if key != "admission_sha256"
    })
    return result


def _validated_admission(
    value: object, *, slate_freeze: Mapping[str, object],
) -> dict[str, object]:
    freeze = _validated_freeze(slate_freeze)
    item = _mapping(value, label="broad-corpus admission")
    admission_id = item.get("admission_id")
    if admission_id != DIRECT_ADMISSION_ID:
        try:
            score_free.reject_outcome_carriers_v1(
                item, label="broad-corpus score-free admission"
            )
        except Exception as exc:
            raise CorpusR6BroadAdmissionTournamentV1Error(
                f"score-free admission carries outcome authority: {exc}"
            ) from exc
    base_fields = {
        "schema_version", "version", "slate", "slate_freeze_sha256",
        "admission_id", "admission_budget", "selected_lineup_ids",
        "selected_lineup_ids_sha256", "selection_trace",
        "selection_trace_sha256", "candidate_generation_performed",
        "uses_realized_outcomes", "past_season_labels_used",
        "target_slate_labels_used", "k80_selection_performed",
        "automatic_policy_promotion", "admission_sha256",
    }
    if admission_id == REFERENCE_ADMISSION_ID:
        expected_fields = base_fields
    elif admission_id == QUOTA_ADMISSION_ID:
        expected_fields = base_fields | {"quota_policy", "quota_policy_sha256"}
    elif admission_id == DIRECT_ADMISSION_ID:
        expected_fields = base_fields | {
            "ranker", "ranker_sha256", "past_season_only"
        }
    else:
        _fail("broad-corpus admission ID differs")
    ids = _sequence(
        item.get("selected_lineup_ids"), label="admitted lineup IDs"
    )
    trace = _sequence(item.get("selection_trace"), label="admission trace")
    budget = item.get("admission_budget")
    eligible = {
        str(row["lineup_id"]) for row in freeze["candidate_features"]
    }
    if (
        set(item) != expected_fields
        or item.get("schema_version") != ADMISSION_SCHEMA
        or item.get("version") != VERSION
        or item.get("slate") != freeze["slate"]
        or item.get("slate_freeze_sha256") != freeze["slate_freeze_sha256"]
        or budget not in ADMISSION_BUDGETS
        or len(ids) != budget
        or any(type(lineup_id) is not str for lineup_id in ids)
        or len(set(ids)) != budget
        or not set(ids) <= eligible
        or item.get("selected_lineup_ids_sha256") != _hash(ids)
        or len(trace) != budget
        or [
            row.get("lineup_id") for row in trace if isinstance(row, Mapping)
        ] != ids
        or [
            row.get("selection_rank") for row in trace
            if isinstance(row, Mapping)
        ] != list(range(budget))
        or item.get("selection_trace_sha256") != _hash(trace)
        or item.get("candidate_generation_performed") is not False
        or item.get("target_slate_labels_used") is not False
        or item.get("uses_realized_outcomes")
        is not (admission_id == DIRECT_ADMISSION_ID)
        or item.get("past_season_labels_used")
        is not (admission_id == DIRECT_ADMISSION_ID)
        or item.get("k80_selection_performed") is not False
        or item.get("automatic_policy_promotion") is not False
        or item.get("admission_sha256")
        != _hash({key: child for key, child in item.items()
                  if key != "admission_sha256"})
    ):
        _fail("broad-corpus admission authority differs")
    if admission_id == QUOTA_ADMISSION_ID:
        policy = _mapping(item.get("quota_policy"), label="quota policy")
        census = _sequence(
            policy.get("availability_census"), label="quota availability census"
        )
        if (
            set(policy) != {
                "basis_points", "source_order", "availability_census",
                "availability_census_sha256",
                "quota_sizes_use_fixed_budget_not_outcomes",
                "shortfalls_fill_by_reference_order",
            }
            or policy.get("basis_points") != _QUOTA_BASIS_POINTS
            or policy.get("source_order") != list(SOURCE_ORDER)
            or policy.get("availability_census_sha256") != _hash(census)
            or policy.get("quota_sizes_use_fixed_budget_not_outcomes") is not True
            or policy.get("shortfalls_fill_by_reference_order") is not True
            or item.get("quota_policy_sha256") != _hash(policy)
        ):
            _fail("broad-corpus quota admission authority differs")
    if admission_id == DIRECT_ADMISSION_ID and (
        not isinstance(item.get("ranker"), Mapping)
        or item.get("ranker_sha256") != item["ranker"].get("ranker_sha256")
        or not _is_sha256(item.get("ranker_sha256"))
        or item.get("past_season_only") is not True
    ):
        _fail("broad-corpus direct admission authority differs")
    return item


def build_fixed_budget_reference_challenger_blend_v1(
    *, slate_freeze: Mapping[str, object],
    reference_admission: Mapping[str, object],
    challenger_admission: Mapping[str, object],
) -> dict[str, object]:
    """Freeze an outcome-blind reference/challenger union at the same total A."""

    freeze = _validated_freeze(slate_freeze)
    reference = _validated_admission(
        reference_admission, slate_freeze=freeze
    )
    challenger = _validated_admission(
        challenger_admission, slate_freeze=freeze
    )
    budget = int(reference["admission_budget"])
    if (
        reference["admission_id"] != REFERENCE_ADMISSION_ID
        or challenger["admission_id"] == REFERENCE_ADMISSION_ID
        or challenger["admission_budget"] != budget
    ):
        _fail("fixed-budget admission blend inputs differ")
    reference_quota = budget // 2
    challenger_quota = budget - reference_quota
    selected = list(reference["selected_lineup_ids"][:reference_quota])
    selected_set = set(selected)
    challenger_selected: list[str] = []
    for lineup_id in challenger["selected_lineup_ids"]:
        if lineup_id in selected_set:
            continue
        selected.append(str(lineup_id))
        selected_set.add(str(lineup_id))
        challenger_selected.append(str(lineup_id))
        if len(challenger_selected) == challenger_quota:
            break
    if len(selected) != budget or len(selected_set) != budget:
        _fail("fixed-budget admission blend could not fill exact budget")
    trace = [{
        "selection_rank": rank,
        "lineup_id": lineup_id,
        "source_admission_id": (
            REFERENCE_ADMISSION_ID if rank < reference_quota
            else str(challenger["admission_id"])
        ),
        "source_admission_rank": (
            reference["selected_lineup_ids"].index(lineup_id)
            if rank < reference_quota
            else challenger["selected_lineup_ids"].index(lineup_id)
        ),
    } for rank, lineup_id in enumerate(selected)]
    past_labels_used = challenger["admission_id"] == DIRECT_ADMISSION_ID
    body = {
        "schema_version": BLEND_SCHEMA,
        "version": VERSION,
        "slate": freeze["slate"],
        "slate_freeze_sha256": freeze["slate_freeze_sha256"],
        "admission_budget": budget,
        "blend_law": BLEND_LAW,
        "reference_admission_sha256": reference["admission_sha256"],
        "challenger_admission_id": challenger["admission_id"],
        "challenger_admission_sha256": challenger["admission_sha256"],
        "reference_reserved_count": reference_quota,
        "challenger_reserved_novel_count": challenger_quota,
        "selected_lineup_ids": selected,
        "selected_lineup_ids_sha256": _hash(selected),
        "selection_trace": trace,
        "selection_trace_sha256": _hash(trace),
        "total_admission_budget_held_fixed": True,
        "uses_realized_outcomes": past_labels_used,
        "past_season_labels_used": past_labels_used,
        "target_slate_labels_used": False,
        "k80_selection_performed": False,
        "automatic_policy_promotion": False,
    }
    if not past_labels_used:
        try:
            score_free.reject_outcome_carriers_v1(
                body, label="fixed-budget score-free admission blend"
            )
        except Exception as exc:
            raise CorpusR6BroadAdmissionTournamentV1Error(
                f"score-free blend carries outcome authority: {exc}"
            ) from exc
    return _with_hash(body, field="blend_sha256")


def _validated_blend(
    value: object, *, slate_freeze: Mapping[str, object],
    admissions_by_id: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    freeze = _validated_freeze(slate_freeze)
    item = _mapping(value, label="fixed-budget admission blend")
    expected_fields = {
        "schema_version", "version", "slate", "slate_freeze_sha256",
        "admission_budget", "blend_law", "reference_admission_sha256",
        "challenger_admission_id", "challenger_admission_sha256",
        "reference_reserved_count", "challenger_reserved_novel_count",
        "selected_lineup_ids", "selected_lineup_ids_sha256", "selection_trace",
        "selection_trace_sha256", "total_admission_budget_held_fixed",
        "uses_realized_outcomes", "past_season_labels_used",
        "target_slate_labels_used", "k80_selection_performed",
        "automatic_policy_promotion", "blend_sha256",
    }
    challenger_id = item.get("challenger_admission_id")
    reference = admissions_by_id.get(REFERENCE_ADMISSION_ID)
    challenger = admissions_by_id.get(str(challenger_id))
    ids = _sequence(item.get("selected_lineup_ids"), label="blend lineup IDs")
    trace = _sequence(item.get("selection_trace"), label="blend trace")
    budget = item.get("admission_budget")
    if (
        set(item) != expected_fields
        or item.get("schema_version") != BLEND_SCHEMA
        or item.get("version") != VERSION
        or item.get("slate") != freeze["slate"]
        or item.get("slate_freeze_sha256") != freeze["slate_freeze_sha256"]
        or reference is None
        or challenger is None
        or challenger_id == REFERENCE_ADMISSION_ID
        or item.get("reference_admission_sha256")
        != reference.get("admission_sha256")
        or item.get("challenger_admission_sha256")
        != challenger.get("admission_sha256")
        or budget not in ADMISSION_BUDGETS
        or item.get("blend_law") != BLEND_LAW
        or item.get("reference_reserved_count") != budget // 2
        or item.get("challenger_reserved_novel_count") != budget - budget // 2
        or len(ids) != budget
        or len(set(ids)) != budget
        or item.get("selected_lineup_ids_sha256") != _hash(ids)
        or len(trace) != budget
        or [row.get("lineup_id") for row in trace if isinstance(row, Mapping)]
        != ids
        or item.get("selection_trace_sha256") != _hash(trace)
        or item.get("total_admission_budget_held_fixed") is not True
        or item.get("uses_realized_outcomes")
        is not (challenger_id == DIRECT_ADMISSION_ID)
        or item.get("past_season_labels_used")
        is not (challenger_id == DIRECT_ADMISSION_ID)
        or item.get("target_slate_labels_used") is not False
        or item.get("k80_selection_performed") is not False
        or item.get("automatic_policy_promotion") is not False
        or item.get("blend_sha256")
        != _hash({key: child for key, child in item.items()
                  if key != "blend_sha256"})
    ):
        _fail("fixed-budget admission blend authority differs")
    replay = build_fixed_budget_reference_challenger_blend_v1(
        slate_freeze=freeze,
        reference_admission=reference,
        challenger_admission=challenger,
    )
    if replay != item:
        _fail("fixed-budget admission blend replay differs")
    return item


def _best_realized(
    lineup_ids: Sequence[str], scores: Mapping[str, int],
) -> tuple[str, int]:
    if not lineup_ids:
        _fail("realized candidate set is empty")
    best_id = min(lineup_ids, key=lambda lineup_id: (-scores[lineup_id], lineup_id))
    return best_id, scores[best_id]


def _retention_metrics(
    *, lineup_ids: Sequence[str], scores: Mapping[str, int],
    full_max_micro: int,
) -> dict[str, object]:
    ids = list(lineup_ids)
    best_id, best_score = _best_realized(ids, scores)
    return {
        "candidate_count": len(ids),
        "realized_max_lineup_id": best_id,
        "realized_max_micro": best_score,
        "realized_max_points": best_score / _MICRO,
        "fixed_corpus_max_micro": full_max_micro,
        "fixed_corpus_max_retained": any(
            scores[lineup_id] == full_max_micro for lineup_id in ids
        ),
        "fixed_corpus_max_gap_micro": full_max_micro - best_score,
        "threshold_operator": ">=",
        "threshold_retention": [{
            "threshold": threshold,
            "fixed_corpus_candidate_count": full_count,
            "retained_candidate_count": retained_count,
            "retained_fraction_ppm": (
                retained_count * _MICRO // full_count if full_count else None
            ),
            "fixed_corpus_has_opportunity": full_count > 0,
            "slate_opportunity_retained": (
                retained_count > 0 if full_count else None
            ),
        } for threshold in THRESHOLDS for full_count, retained_count in [(
            sum(score >= threshold * _MICRO for score in scores.values()),
            sum(scores[lineup_id] >= threshold * _MICRO for lineup_id in ids),
        )]],
    }


def grade_fixed_budget_admissions_v1(
    *, slate_freeze: Mapping[str, object],
    admissions: Sequence[Mapping[str, object]],
    blends: Sequence[Mapping[str, object]],
    realized_scores_micro: Mapping[str, int],
    outcome_identity: Mapping[str, object],
) -> dict[str, object]:
    """Open outcomes only after all fixed-A admissions and blends are frozen."""

    freeze = _validated_freeze(slate_freeze)
    slate = _slate(freeze["slate"])
    if slate["season"] not in (2023, 2024, 2025):
        _fail("admission grade slate is outside the fixed historical program")
    retained_admissions = [
        _validated_admission(value, slate_freeze=freeze)
        for value in admissions
    ]
    admissions_by_id = {
        str(item["admission_id"]): item for item in retained_admissions
    }
    expected_ids = {REFERENCE_ADMISSION_ID, QUOTA_ADMISSION_ID}
    if slate["season"] >= 2024:
        expected_ids.add(DIRECT_ADMISSION_ID)
    budgets = {item["admission_budget"] for item in retained_admissions}
    if (
        set(admissions_by_id) != expected_ids
        or len(admissions_by_id) != len(retained_admissions)
        or len(budgets) != 1
    ):
        _fail("admission grade arm or budget census differs")
    budget = next(iter(budgets))
    for admission_id, item in admissions_by_id.items():
        if admission_id == REFERENCE_ADMISSION_ID:
            replay = build_reference_admission_v1(freeze, budget=budget)
        elif admission_id == QUOTA_ADMISSION_ID:
            replay = build_quota_admission_v1(freeze, budget=budget)
        else:
            replay = build_direct_ranker_admission_v1(
                freeze,
                ranker=_mapping(item["ranker"], label="embedded ranker"),
                budget=budget,
            )
        if replay != item:
            _fail("admission grade arm replay differs")
    retained_blends = [
        _validated_blend(
            value,
            slate_freeze=freeze,
            admissions_by_id=admissions_by_id,
        )
        for value in blends
    ]
    if (
        {item["challenger_admission_id"] for item in retained_blends}
        != expected_ids - {REFERENCE_ADMISSION_ID}
        or len(retained_blends) != len(expected_ids) - 1
    ):
        _fail("admission grade blend census differs")
    raw_scores = _mapping(
        realized_scores_micro, label="fixed-corpus realized scores"
    )
    scores = {str(key): value for key, value in raw_scores.items()}
    candidate_ids = [
        str(row["lineup_id"]) for row in freeze["candidate_features"]
    ]
    outcome = _identity(
        outcome_identity, label="admission grade outcome identity"
    )
    if (
        set(scores) != set(candidate_ids)
        or any(type(score) is not int for score in scores.values())
    ):
        _fail("admission grade realized-score authority differs")
    full_best_id, full_max = _best_realized(candidate_ids, scores)
    admission_grades = [{
        "admission_id": item["admission_id"],
        "admission_sha256": item["admission_sha256"],
        **_retention_metrics(
            lineup_ids=item["selected_lineup_ids"],
            scores=scores,
            full_max_micro=full_max,
        ),
    } for item in sorted(
        retained_admissions, key=lambda item: str(item["admission_id"])
    )]
    reference_grade = next(
        item for item in admission_grades
        if item["admission_id"] == REFERENCE_ADMISSION_ID
    )
    blend_grades = [{
        "challenger_admission_id": item["challenger_admission_id"],
        "blend_sha256": item["blend_sha256"],
        **_retention_metrics(
            lineup_ids=item["selected_lineup_ids"],
            scores=scores,
            full_max_micro=full_max,
        ),
    } for item in sorted(
        retained_blends,
        key=lambda item: str(item["challenger_admission_id"]),
    )]
    for item in blend_grades:
        item["incremental_realized_max_vs_reference_micro"] = (
            int(item["realized_max_micro"])
            - int(reference_grade["realized_max_micro"])
        )
    body = {
        "schema_version": GRADE_SCHEMA,
        "version": VERSION,
        "slate": slate,
        "slate_freeze_sha256": freeze["slate_freeze_sha256"],
        "admission_budget": budget,
        "outcome_identity": outcome,
        "outcome_identity_sha256": _hash(outcome),
        "realized_scores_sha256": _hash(scores),
        "fixed_corpus_candidate_count": len(candidate_ids),
        "fixed_corpus_realized_max_lineup_id": full_best_id,
        "fixed_corpus_realized_max_micro": full_max,
        "fixed_corpus_realized_max_points": full_max / _MICRO,
        "fixed_corpus_hindsight_max_is_diagnostic_only": True,
        "hindsight_union_gap_is_not_a_recovery_target": True,
        "admission_grades": admission_grades,
        "admission_grades_sha256": _hash(admission_grades),
        "fixed_total_budget_blend_grades": blend_grades,
        "fixed_total_budget_blend_grades_sha256": _hash(blend_grades),
        "k80_selection_is_secondary_and_not_performed": True,
        "automatic_policy_promotion": False,
        "uses_realized_outcomes": True,
    }
    return _with_hash(body, field="grade_sha256")


__all__ = [
    "ADMISSION_BUDGETS",
    "BLEND_LAW",
    "DIRECT_ADMISSION_ID",
    "FEATURE_NAMES",
    "QUOTA_ADMISSION_ID",
    "REFERENCE_ADMISSION_ID",
    "THRESHOLDS",
    "VERSION",
    "CorpusR6BroadAdmissionTournamentV1Error",
    "build_direct_ranker_admission_v1",
    "build_fixed_budget_reference_challenger_blend_v1",
    "build_quota_admission_v1",
    "build_reference_admission_v1",
    "fit_past_season_direct_ranker_v1",
    "freeze_combined_slate_inputs_v1",
    "freeze_slate_inputs_v1",
    "grade_fixed_budget_admissions_v1",
]
