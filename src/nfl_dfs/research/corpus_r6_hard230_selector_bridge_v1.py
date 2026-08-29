"""Outcome-blind selected-book bridge for the native R6 hard-230 panel.

The hard-230 successor deliberately emits populations, not portfolios.  This
module turns each terminal control/challenger population into comparable
deployable books without reading realized outcomes or changing either source
population.

The bridge is intentionally thin:

* retain both complete source populations for corpus-ceiling grading;
* take one equal-count, score-blind SHA-256 sample from each population;
* score that sample only on the generation-pinned R1--R4 simulation blocks;
* reuse the existing native grouped/rank-150 and effective-shots DPP kernels;
* expose exact nested 80/100/150 books from each of four ranked orders.

R0 is excluded from selector fitting because it is the hard-230 generator's
objective-world origin.  Hard-230 admission itself used all five blocks, so
R1--R4 is an out-of-origin selector bank, not an independent population
holdout.  The result records that limitation explicitly.

All storage, source reconstruction, publication and realized grading stay in
the operator layer.  Public functions here accept only already-validated
JSON-like values and an in-memory simulated score matrix.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Final

import numpy as np

from nfl_dfs.research import (
    corpus_extreme_tail_generation_additions as generation_source,
)
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_population_process_v1 as hard_process,
)
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_population_successor_v1 as hard_successor,
)
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_r6_cloud_entrypoint_v1 as hard_cloud,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_diversity_selector_v1 as diversity,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_rank150_v1 as rank150,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as grouped,
)
from nfl_dfs.research import (
    corpus_r6_novel_roster_realized_grader_v1 as grader,
)


CONTRACT_ID: Final = "20260829-hard230-selected-book-bridge-v1"
SLATE_RESULT_SCHEMA: Final = "corpus-r6-hard230-selector-bridge-slate/v1"
TERMINAL_SCHEMA: Final = "corpus-r6-hard230-selector-bridge-terminal/v1"
ADAPTER_ID: Final = "hard230-selected-book-bridge-v1"

WORLD_BLOCKS: Final = tuple(hard_successor.WORLD_BLOCKS)
GENERATOR_ORIGIN_BLOCK: Final = "R0"
SELECTOR_BLOCKS: Final = ("R1", "R2", "R3", "R4")
SELECTOR_BLOCK_COUNT: Final = 4
MAXIMUM_SAMPLE_COUNT: Final = 250
MINIMUM_SAMPLE_COUNT: Final = 150
ENTRY_BUDGETS: Final = (80, 100, 150)
ROSTER_SIZE: Final = 9
MILLI_PER_DK: Final = 1_000

CONTROL_ROLE: Final = "score-blind-control"
CHALLENGER_ROLE: Final = "hard230-challenger"
POPULATION_SPECS: Final = (
    (
        CONTROL_ROLE,
        hard_successor.CONTROL_POPULATION_ID,
        "score_blind_control_population",
        "score_blind_control_population_count",
        "score_blind_control_population_sha256",
    ),
    (
        CHALLENGER_ROLE,
        hard_successor.CHALLENGER_POPULATION_ID,
        "hard230_challenger_population",
        "hard230_challenger_population_count",
        "hard230_challenger_population_sha256",
    ),
)

NATIVE_SELECTORS: Final = (
    (
        "native-convex-excess-expected-max-v1",
        "native-convex-excess-expected-max-rank150-v1",
    ),
    (
        "native-correlation-aware-expected-max-v1",
        "native-correlation-aware-expected-max-rank150-v1",
    ),
    (
        "native-support-switched-scenario-ticket-v1",
        "native-support-switched-scenario-ticket-rank150-v1",
    ),
)
DPP_SELECTOR_ID: Final = "effective-independent-tail-shots-dpp-ge-230-v1"

_FALSE_AUTHORITY_FIELDS: Final = (
    "uses_realized_outcomes",
    "uses_heldout_scores",
    "historical_scoring_licensed",
    "publication_authority",
    "promotion_authority",
    "decision_authority",
    "production_change_licensed",
    "graph_mutation_licensed",
)

_SLATE_RESULT_FIELDS: Final = frozenset({
    "schema_version", "contract", "contract_sha256", "source_ordinal",
    "slate_id", "later_source_identity", "task_result_identity",
    "task_result_sha256", "process_receipt_identity",
    "process_receipt_sha256", "source_member_identity",
    "score_matrix_identity", "source_lineage", "worlds_per_block",
    "generator_origin_block", "selector_fit_blocks",
    "equal_sample_lineup_count", "population_results",
    "population_results_sha256", "outcome_columns_read",
    *_FALSE_AUTHORITY_FIELDS, "slate_result_sha256",
})
_POPULATION_RESULT_FIELDS: Final = frozenset({
    "population_role", "population_id", "full_population_lineup_count",
    "full_population_lineups", "full_population_lineups_sha256",
    "equal_sample_lineup_count", "sampled_lineup_ids",
    "sampled_lineup_ids_sha256", "selector_fit_score_shape",
    "selector_fit_score_matrix_sha256", "shared_preprocessing_sha256",
    "selector_summaries", "selector_summaries_sha256", "books",
    "books_sha256", "population_result_sha256",
})
_BOOK_FIELDS: Final = frozenset({
    "coordinate", "coordinate_sha256", "selected_lineup_ids",
    "selected_lineup_ids_sha256", "book_sha256",
})
_COORDINATE_FIELDS: Final = frozenset({
    "adapter_id", "metric_kind", "population_role", "population_id",
    "selector_family", "selector_id", "entry_budget",
})


class CorpusR6Hard230SelectorBridgeV1Error(ValueError):
    """The hard-230 selected-book bridge cannot replay exactly."""


def _fail(message: str) -> None:
    raise CorpusR6Hard230SelectorBridgeV1Error(message)


def _canonical(value: object) -> bytes:
    try:
        return grader.canonical_json_bytes_v1(value)
    except (TypeError, ValueError) as exc:
        raise CorpusR6Hard230SelectorBridgeV1Error(
            "value is not finite canonical JSON"
        ) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _with_hash(
    value: Mapping[str, object], *, field: str
) -> dict[str, object]:
    result = dict(value)
    if field in result:
        _fail(f"{field} cannot already be present")
    result[field] = _hash(result)
    return result


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return grader._identity(value, label=label)
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise CorpusR6Hard230SelectorBridgeV1Error(str(exc)) from exc


def _digest(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _implementation_contract_v1() -> dict[str, object]:
    if (
        WORLD_BLOCKS != ("R0", "R1", "R2", "R3", "R4")
        or GENERATOR_ORIGIN_BLOCK in SELECTOR_BLOCKS
        or tuple(block for block in WORLD_BLOCKS if block != GENERATOR_ORIGIN_BLOCK)
        != SELECTOR_BLOCKS
    ):
        _fail("hard230 generator-origin/selector block partition differs")
    grouped_implementation = grouped.frozen_successor_implementation_v1()
    rank_implementation = rank150.frozen_rank150_implementation_v1()
    dpp_contract = diversity.frozen_diversity_selector_contract_v1()
    return _with_hash({
        "contract_id": CONTRACT_ID,
        "adapter_id": ADAPTER_ID,
        "source_population_contract_id": hard_successor.CONTRACT_ID,
        "grouped_implementation_sha256": grouped_implementation[
            "implementation_sha256"
        ],
        "rank150_implementation_sha256": rank_implementation[
            "implementation_sha256"
        ],
        "dpp_contract_sha256": dpp_contract["contract_sha256"],
        "generator_origin_block": GENERATOR_ORIGIN_BLOCK,
        "selector_fit_blocks": list(SELECTOR_BLOCKS),
        "selector_fit_law": (
            "fixed-r1-through-r4-out-of-r0-origin-simulated-bank"
        ),
        "population_admission_independent_of_selector_fit_claimed": False,
        "population_admission_used_all_five_blocks": True,
        "sample_law": (
            "equal-count-lowest-sha256-of-contract-slate-role-lineup-id"
        ),
        "maximum_sample_count": MAXIMUM_SAMPLE_COUNT,
        "minimum_sample_count": MINIMUM_SAMPLE_COUNT,
        "entry_budgets": list(ENTRY_BUDGETS),
        "full_source_populations_preserved": True,
        "population_ceiling_and_selected_book_metrics_separate": True,
        "outcome_columns_read": [],
        **_false_authorities(),
    }, field="contract_sha256")


def frozen_hard230_selector_bridge_contract_v1() -> dict[str, object]:
    """Return the deterministic, outcome-blind bridge contract."""
    return _implementation_contract_v1()


def _lineups(
    population_value: object,
    *,
    expected_population_id: str,
    label: str,
) -> list[dict[str, object]]:
    population = _mapping(population_value, label=label)
    rows = _sequence(population.get("population_rosters"), label=f"{label} rosters")
    normalized: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_rosters: set[tuple[str, ...]] = set()
    for ordinal, raw in enumerate(rows):
        row = _mapping(raw, label=f"{label} roster[{ordinal}]")
        if set(row) != {
            "lineup_id",
            "roster_player_ids",
            "roster_sha256",
            "first_occurrence_ordinal",
            "fit_world_score_vector_sha256",
        }:
            _fail(f"{label} roster fields differ")
        lineup_id = row.get("lineup_id")
        roster = tuple(str(value) for value in _sequence(
            row.get("roster_player_ids"), label=f"{label} player IDs"
        ))
        roster_sha = _hash(list(roster))
        if (
            type(lineup_id) is not str
            or len(roster) != ROSTER_SIZE
            or len(set(roster)) != ROSTER_SIZE
            or list(roster) != sorted(roster)
            or row.get("roster_sha256") != roster_sha
            or lineup_id != f"lineup-v1-{roster_sha}"
            or type(row.get("first_occurrence_ordinal")) is not int
            or int(row["first_occurrence_ordinal"]) < 0
            or type(row.get("fit_world_score_vector_sha256")) is not str
            or len(str(row["fit_world_score_vector_sha256"])) != 64
            or lineup_id in seen_ids
            or roster in seen_rosters
        ):
            _fail(f"{label} roster identity differs")
        seen_ids.add(lineup_id)
        seen_rosters.add(roster)
        normalized.append({
            "lineup_id": lineup_id,
            "roster_player_ids": list(roster),
            "roster_sha256": roster_sha,
        })
    if (
        population.get("population_id") != expected_population_id
        or population.get("population_lineup_count") != len(normalized)
        or population.get("population_rosters_sha256") != _hash(rows)
        or population.get("uses_heldout_scores") is not False
        or population.get("uses_realized_outcomes") is not False
        or not normalized
    ):
        _fail(f"{label} population binding differs")
    return normalized


def _validated_source_receipts(
    *, task_result: object, process_receipt: object
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    try:
        task = hard_cloud.validate_task_result_v1(task_result)
        process = hard_process.validate_process_receipt_v1(process_receipt)
    except (
        hard_cloud.Hard230R6CloudEntrypointV1Error,
        hard_process.Hard230PopulationProcessV1Error,
        hard_successor.Hard230PopulationSuccessorV1Error,
    ) as exc:
        raise CorpusR6Hard230SelectorBridgeV1Error(str(exc)) from exc
    scientific = _mapping(
        process.get("scientific_receipt"), label="hard230 scientific receipt"
    )
    if (
        task.get("schema_version") != "hard230-r6-task-result/v1"
        or task.get("complete") is not True
        or task.get("process_receipt_sha256")
        != process.get("process_receipt_sha256")
        or task.get("task_index") != process.get("task_index")
        or task.get("slate_id") != process.get("slate_id")
        or task.get("score_matrix_identity") is None
        or task.get("source_member_identity") is None
        or task.get("uses_heldout_scores") is not False
        or task.get("uses_realized_outcomes") is not False
        or task.get("outcome_columns_read") != []
    ):
        _fail("hard230 task/process binding differs")
    return task, process, scientific


def _validated_matrix(
    *,
    score_matrix: object,
    score_matrix_identity: object,
    player_registry: object,
    source_lineage: Mapping[str, object],
) -> tuple[np.ndarray, list[str]]:
    if not isinstance(score_matrix, np.ndarray):
        _fail("hard230 score matrix must be one numpy array")
    matrix = np.asarray(score_matrix)
    registry_rows = [
        _mapping(row, label="hard230 player registry row")
        for row in _sequence(player_registry, label="hard230 player registry")
    ]
    player_ids = [str(row.get("id")) for row in registry_rows]
    identity = _mapping(score_matrix_identity, label="hard230 score matrix identity")
    if (
        matrix is not score_matrix
        or matrix.dtype != np.dtype("<i8")
        or matrix.ndim != 2
        or not matrix.flags.c_contiguous
        or matrix.shape[0] != len(player_ids)
        or matrix.shape[1] % len(WORLD_BLOCKS) != 0
        or player_ids != sorted(set(player_ids))
        or _hash(registry_rows) != source_lineage.get("player_registry_sha256")
        or generation_source.canonical_score_matrix_sha256_v1(matrix)
        != source_lineage.get("score_matrix_sha256")
        or identity.get("canonical_score_matrix_sha256")
        != source_lineage.get("score_matrix_sha256")
        or identity.get("player_registry_sha256")
        != source_lineage.get("player_registry_sha256")
    ):
        _fail("hard230 matrix/registry/source-lineage binding differs")
    return matrix, player_ids


def _sample_lineup_ids(
    *,
    slate_id: str,
    population_role: str,
    lineup_ids: Sequence[str],
    sample_count: int,
) -> list[str]:
    if not MINIMUM_SAMPLE_COUNT <= sample_count <= MAXIMUM_SAMPLE_COUNT:
        _fail("hard230 selector sample count is outside 150..250")
    ranked = sorted(
        lineup_ids,
        key=lambda lineup_id: (
            sha256(_canonical({
                "contract_id": CONTRACT_ID,
                "slate_id": slate_id,
                "population_role": population_role,
                "lineup_id": lineup_id,
            })).digest(),
            lineup_id,
        ),
    )
    return sorted(ranked[:sample_count])


def _lineup_score_matrix_dk(
    *,
    lineups: Sequence[Mapping[str, object]],
    sampled_ids: Sequence[str],
    player_ids: Sequence[str],
    player_score_matrix_milli: np.ndarray,
) -> np.ndarray:
    by_id = {str(row["lineup_id"]): row for row in lineups}
    player_index = {player_id: ordinal for ordinal, player_id in enumerate(player_ids)}
    worlds_per_block = player_score_matrix_milli.shape[1] // len(WORLD_BLOCKS)
    if GENERATOR_ORIGIN_BLOCK in SELECTOR_BLOCKS:
        _fail("hard230 generator-origin block entered selector fitting")
    selector_columns = np.concatenate([
        np.arange(
            WORLD_BLOCKS.index(block) * worlds_per_block,
            (WORLD_BLOCKS.index(block) + 1) * worlds_per_block,
            dtype=np.int64,
        )
        for block in SELECTOR_BLOCKS
    ])
    result = np.empty(
        (len(sampled_ids), SELECTOR_BLOCK_COUNT * worlds_per_block),
        dtype=np.float64,
    )
    for ordinal, lineup_id in enumerate(sampled_ids):
        roster = by_id[lineup_id]["roster_player_ids"]
        try:
            indices = [player_index[str(player_id)] for player_id in roster]
        except KeyError as exc:
            raise CorpusR6Hard230SelectorBridgeV1Error(
                f"hard230 roster player is absent from matrix registry: {exc}"
            ) from exc
        score_milli = player_score_matrix_milli[np.ix_(indices, selector_columns)].sum(
            axis=0, dtype=np.int64
        )
        result[ordinal] = score_milli.astype(np.float64) / MILLI_PER_DK
    if not result.flags.c_contiguous or not np.isfinite(result).all():
        _fail("hard230 sampled lineup score matrix differs")
    result.flags.writeable = False
    return result


def _book(
    *, selector_family: str, selector_id: str, selected_ids: Sequence[str],
    population_role: str, population_id: str, entry_budget: int,
) -> dict[str, object]:
    ids = list(selected_ids[:entry_budget])
    if len(ids) != entry_budget or len(set(ids)) != entry_budget:
        _fail("hard230 selected book is not exact and unique")
    coordinate = {
        "adapter_id": ADAPTER_ID,
        "metric_kind": "selected-book",
        "population_role": population_role,
        "population_id": population_id,
        "selector_family": selector_family,
        "selector_id": selector_id,
        "entry_budget": entry_budget,
    }
    return _with_hash({
        "coordinate": coordinate,
        "coordinate_sha256": _hash(coordinate),
        "selected_lineup_ids": ids,
        "selected_lineup_ids_sha256": _hash(ids),
    }, field="book_sha256")


def _native_orders(
    *, scores: np.ndarray, lineup_ids: Sequence[str],
) -> tuple[list[dict[str, object]], Mapping[str, object]]:
    shared = grouped._build_shared_preprocessing_v1(
        scores=scores,
        training_blocks=SELECTOR_BLOCKS,
        worlds_per_block=scores.shape[1] // SELECTOR_BLOCK_COUNT,
    )
    grouped_calls = (
        lambda: grouped._run_convex_v1(
            scores=scores, lineup_ids=lineup_ids, shared=shared
        ),
        lambda: grouped._run_correlation_v1(
            scores=scores,
            lineup_ids=lineup_ids,
            training_blocks=SELECTOR_BLOCKS,
            worlds_per_block=scores.shape[1] // SELECTOR_BLOCK_COUNT,
            shared=shared,
        ),
        lambda: grouped._run_scenario_v1(
            scores=scores,
            lineup_ids=lineup_ids,
            training_blocks=SELECTOR_BLOCKS,
            worlds_per_block=scores.shape[1] // SELECTOR_BLOCK_COUNT,
            shared=shared,
        ),
    )
    ranked_calls = (
        lambda: rank150._run_convex_rank150_v1(
            scores=scores, lineup_ids=lineup_ids, shared=shared
        ),
        lambda: rank150._run_correlation_rank150_v1(
            scores=scores,
            lineup_ids=lineup_ids,
            training_blocks=SELECTOR_BLOCKS,
            worlds_per_block=scores.shape[1] // SELECTOR_BLOCK_COUNT,
            shared=shared,
        ),
        lambda: rank150._run_scenario_rank150_v1(
            lineup_ids=lineup_ids,
            training_blocks=SELECTOR_BLOCKS,
            worlds_per_block=scores.shape[1] // SELECTOR_BLOCK_COUNT,
            shared=shared,
        ),
    )
    rows: list[dict[str, object]] = []
    for (grouped_id, ranked_id), grouped_call, ranked_call in zip(
        NATIVE_SELECTORS, grouped_calls, ranked_calls, strict=True
    ):
        grouped_indices, grouped_diagnostics = grouped_call()
        ranked_indices, ranked_diagnostics = ranked_call()
        if (
            len(grouped_indices) != 80
            or len(ranked_indices) != 150
            or grouped_indices != ranked_indices[:80]
            or len(set(ranked_indices)) != 150
        ):
            _fail("hard230 native grouped/rank150 prefix parity differs")
        rows.append({
            "grouped_selector_id": grouped_id,
            "rank150_selector_id": ranked_id,
            "grouped_rank80_lineup_ids": [lineup_ids[index] for index in grouped_indices],
            "ranked_lineup_ids": [lineup_ids[index] for index in ranked_indices],
            "grouped_diagnostics_sha256": _hash(grouped_diagnostics),
            "rank150_diagnostics_sha256": _hash(ranked_diagnostics),
            "exact_grouped_rank80_prefix_parity": True,
        })
    return rows, shared.diagnostics


def _dpp_order(
    *, scores: np.ndarray, lineup_ids: Sequence[str],
    lineups_by_id: Mapping[str, Mapping[str, object]],
) -> tuple[list[str], dict[str, object]]:
    candidates = [lineups_by_id[lineup_id] for lineup_id in lineup_ids]
    packed, tail_counts = diversity._packed_tail_signatures_v1(scores)
    roster_overlaps = diversity._roster_overlap_counts_v1(candidates)
    kernel, tail_similarity, intersections = (
        diversity._build_quality_weighted_kernel_v1(
            packed=packed,
            tail_counts=tail_counts,
            roster_overlaps=roster_overlaps,
        )
    )
    selected, trace = diversity._greedy_dpp_order_v1(
        kernel=kernel, lineup_ids=lineup_ids
    )
    if len(selected) != 150 or len(set(selected)) != 150:
        _fail("hard230 DPP order is not exact rank 150")
    diagnostics = {
        "selection_trace_sha256": _hash(trace),
        "packed_tail_sha256": grouped._array_sha(
            packed, label="hard230-dpp-packed-tail", dtype=np.uint8
        ),
        "tail_counts_sha256": grouped._array_sha(
            tail_counts, label="hard230-dpp-tail-counts", dtype=np.int64
        ),
        "tail_intersections_sha256": grouped._array_sha(
            intersections, label="hard230-dpp-tail-intersections", dtype=np.int32
        ),
        "roster_overlaps_sha256": grouped._array_sha(
            roster_overlaps, label="hard230-dpp-roster-overlaps", dtype=np.uint8
        ),
        "kernel_sha256": grouped._array_sha(
            kernel, label="hard230-dpp-kernel", dtype=np.float64
        ),
        "tail_similarity_shape": list(tail_similarity.shape),
    }
    return [lineup_ids[index] for index in selected], diagnostics


def run_hard230_selector_slate_v1(
    *,
    source_ordinal: int,
    later_source_identity: object,
    task_result_identity: object,
    task_result: object,
    process_receipt_identity: object,
    process_receipt: object,
    player_registry: object,
    score_matrix: np.ndarray,
    score_matrix_identity: object,
) -> dict[str, object]:
    """Build both populations' outcome-blind nested books for one slate."""
    if type(source_ordinal) is not int or source_ordinal < 0:
        _fail("hard230 source ordinal must be one nonnegative integer")
    later_identity = _identity(later_source_identity, label="later source")
    task_identity = _identity(task_result_identity, label="hard230 task result")
    process_identity = _identity(
        process_receipt_identity, label="hard230 process receipt"
    )
    task, process, scientific = _validated_source_receipts(
        task_result=task_result, process_receipt=process_receipt
    )
    if (
        task.get("task_index") != source_ordinal
        or process.get("task_index") != source_ordinal
        or task.get("process_receipt_identity") != process_identity
        or task.get("score_matrix_identity") != score_matrix_identity
    ):
        _fail("hard230 source ordinal or exact identity binding differs")
    source_lineage = _mapping(
        scientific.get("source_lineage"), label="hard230 source lineage"
    )
    matrix, player_ids = _validated_matrix(
        score_matrix=score_matrix,
        score_matrix_identity=score_matrix_identity,
        player_registry=player_registry,
        source_lineage=source_lineage,
    )
    slate_id = str(task["slate_id"])

    population_inputs: list[tuple[str, str, list[dict[str, object]]]] = []
    for role, population_id, field, count_field, hash_field in POPULATION_SPECS:
        lineups = _lineups(
            scientific.get(field),
            expected_population_id=population_id,
            label=f"hard230 {role}",
        )
        population = scientific[field]
        if (
            task.get(count_field) != len(lineups)
            or task.get(hash_field) != population["population_rosters_sha256"]
        ):
            _fail("hard230 task/population summary differs")
        population_inputs.append((role, population_id, lineups))
    common_count = min(
        MAXIMUM_SAMPLE_COUNT,
        *(len(lineups) for _role, _population_id, lineups in population_inputs),
    )
    if common_count < MINIMUM_SAMPLE_COUNT:
        _fail("hard230 populations cannot support exact rank 150 at equal count")

    population_results: list[dict[str, object]] = []
    for role, population_id, lineups in population_inputs:
        lineup_ids = [str(row["lineup_id"]) for row in lineups]
        sampled_ids = _sample_lineup_ids(
            slate_id=slate_id,
            population_role=role,
            lineup_ids=lineup_ids,
            sample_count=common_count,
        )
        lineups_by_id = {str(row["lineup_id"]): row for row in lineups}
        sampled_scores = _lineup_score_matrix_dk(
            lineups=lineups,
            sampled_ids=sampled_ids,
            player_ids=player_ids,
            player_score_matrix_milli=matrix,
        )
        native_rows, shared_diagnostics = _native_orders(
            scores=sampled_scores, lineup_ids=sampled_ids
        )
        dpp_ids, dpp_diagnostics = _dpp_order(
            scores=sampled_scores,
            lineup_ids=sampled_ids,
            lineups_by_id=lineups_by_id,
        )
        books: list[dict[str, object]] = []
        selector_summaries: list[dict[str, object]] = []
        for native in native_rows:
            ranked_ids = native["ranked_lineup_ids"]
            selector_id = str(native["rank150_selector_id"])
            selector_books = [
                _book(
                    selector_family="native-grouped-rank150",
                    selector_id=selector_id,
                    selected_ids=ranked_ids,
                    population_role=role,
                    population_id=population_id,
                    entry_budget=budget,
                )
                for budget in ENTRY_BUDGETS
            ]
            books.extend(selector_books)
            selector_summaries.append({
                **native,
                "book_sha256s": [row["book_sha256"] for row in selector_books],
            })
        dpp_books = [
            _book(
                selector_family="effective-independent-shots-dpp",
                selector_id=DPP_SELECTOR_ID,
                selected_ids=dpp_ids,
                population_role=role,
                population_id=population_id,
                entry_budget=budget,
            )
            for budget in ENTRY_BUDGETS
        ]
        books.extend(dpp_books)
        selector_summaries.append({
            "grouped_selector_id": None,
            "rank150_selector_id": DPP_SELECTOR_ID,
            "grouped_rank80_lineup_ids": None,
            "ranked_lineup_ids": dpp_ids,
            "grouped_diagnostics_sha256": None,
            "rank150_diagnostics_sha256": _hash(dpp_diagnostics),
            "exact_grouped_rank80_prefix_parity": None,
            "book_sha256s": [row["book_sha256"] for row in dpp_books],
        })
        population_results.append(_with_hash({
            "population_role": role,
            "population_id": population_id,
            "full_population_lineup_count": len(lineups),
            "full_population_lineups": lineups,
            "full_population_lineups_sha256": _hash(lineups),
            "equal_sample_lineup_count": common_count,
            "sampled_lineup_ids": sampled_ids,
            "sampled_lineup_ids_sha256": _hash(sampled_ids),
            "selector_fit_score_shape": list(sampled_scores.shape),
            "selector_fit_score_matrix_sha256": grouped._matrix_sha(sampled_scores),
            "shared_preprocessing_sha256": _hash(shared_diagnostics),
            "selector_summaries": selector_summaries,
            "selector_summaries_sha256": _hash(selector_summaries),
            "books": books,
            "books_sha256": _hash(books),
        }, field="population_result_sha256"))

    contract = frozen_hard230_selector_bridge_contract_v1()
    body = {
        "schema_version": SLATE_RESULT_SCHEMA,
        "contract": contract,
        "contract_sha256": contract["contract_sha256"],
        "source_ordinal": source_ordinal,
        "slate_id": slate_id,
        "later_source_identity": later_identity,
        "task_result_identity": task_identity,
        "task_result_sha256": task["task_result_sha256"],
        "process_receipt_identity": process_identity,
        "process_receipt_sha256": process["process_receipt_sha256"],
        "source_member_identity": task["source_member_identity"],
        "score_matrix_identity": task["score_matrix_identity"],
        "source_lineage": source_lineage,
        "worlds_per_block": matrix.shape[1] // len(WORLD_BLOCKS),
        "generator_origin_block": GENERATOR_ORIGIN_BLOCK,
        "selector_fit_blocks": list(SELECTOR_BLOCKS),
        "equal_sample_lineup_count": common_count,
        "population_results": population_results,
        "population_results_sha256": _hash(population_results),
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    return _with_hash(body, field="slate_result_sha256")


def validate_hard230_selector_slate_v1(
    value: object,
    **replay_inputs: object,
) -> dict[str, object]:
    """Pure-replay one persisted slate result byte exactly."""
    retained = _mapping(value, label="hard230 selector slate result")
    expected = run_hard230_selector_slate_v1(**replay_inputs)
    if _canonical(retained) != _canonical(expected):
        _fail("hard230 selector slate result differs from exact pure replay")
    return expected


def normalized_slate_for_grader_v1(value: object) -> dict[str, object]:
    """Project one exact bridge result onto the generic direct-roster seam."""
    result = _mapping(value, label="hard230 selector slate result")
    if (
        set(result) != _SLATE_RESULT_FIELDS
        or result.get("schema_version") != SLATE_RESULT_SCHEMA
        or result.get("slate_result_sha256")
        != _hash({key: item for key, item in result.items() if key != "slate_result_sha256"})
        or result.get("contract") != frozen_hard230_selector_bridge_contract_v1()
        or result.get("contract_sha256")
        != result["contract"]["contract_sha256"]
        or result.get("generator_origin_block") != GENERATOR_ORIGIN_BLOCK
        or result.get("selector_fit_blocks") != list(SELECTOR_BLOCKS)
        or type(result.get("worlds_per_block")) is not int
        or int(result["worlds_per_block"]) < 1
        or result.get("outcome_columns_read") != []
        or any(result.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail("hard230 selector slate fixed law differs")
    raw_population_results = _sequence(
        result.get("population_results"), label="hard230 population results"
    )
    if (
        result.get("population_results_sha256") != _hash(raw_population_results)
        or len(raw_population_results) != len(POPULATION_SPECS)
    ):
        _fail("hard230 population result collection differs")
    populations: list[dict[str, object]] = []
    books: list[dict[str, object]] = []
    retained_equal_count: int | None = None
    for pop_ordinal, (raw_population, population_spec) in enumerate(zip(
        raw_population_results, POPULATION_SPECS, strict=True
    )):
        population = _mapping(raw_population, label="hard230 population result")
        expected_role, expected_population_id, *_unused = population_spec
        role = str(population["population_role"])
        population_id = str(population["population_id"])
        lineups = _sequence(
            population["full_population_lineups"], label="hard230 full lineups"
        )
        if any(
            set(_mapping(row, label=f"hard230 full lineup[{pop_ordinal}]"))
            != {"lineup_id", "roster_player_ids", "roster_sha256"}
            for row in lineups
        ):
            _fail("hard230 normalized full-lineup fields differ")
        lineup_ids = [
            str(_mapping(row, label="hard230 full lineup")["lineup_id"])
            for row in lineups
        ]
        sampled = [
            str(lineup_id)
            for lineup_id in _sequence(
                population.get("sampled_lineup_ids"),
                label="hard230 sampled lineup IDs",
            )
        ]
        equal_count = population.get("equal_sample_lineup_count")
        if retained_equal_count is None:
            retained_equal_count = equal_count if type(equal_count) is int else None
        if (
            set(population) != _POPULATION_RESULT_FIELDS
            or role != expected_role
            or population_id != expected_population_id
            or population.get("population_result_sha256")
            != _hash({
                key: item
                for key, item in population.items()
                if key != "population_result_sha256"
            })
            or population.get("full_population_lineup_count") != len(lineups)
            or population.get("full_population_lineups_sha256") != _hash(lineups)
            or len(lineups) < MINIMUM_SAMPLE_COUNT
            or equal_count != retained_equal_count
            or equal_count != len(sampled)
            or not MINIMUM_SAMPLE_COUNT <= int(equal_count) <= MAXIMUM_SAMPLE_COUNT
            or sampled != sorted(set(sampled))
            or not set(sampled) <= set(lineup_ids)
            or population.get("sampled_lineup_ids_sha256") != _hash(sampled)
            or population.get("selector_fit_score_shape")
            != [equal_count, SELECTOR_BLOCK_COUNT * int(result["worlds_per_block"])]
        ):
            _fail("hard230 population result binding differs")
        _digest(
            population.get("selector_fit_score_matrix_sha256"),
            label="hard230 selector fit matrix",
        )
        _digest(
            population.get("shared_preprocessing_sha256"),
            label="hard230 shared preprocessing",
        )

        selector_summaries = [
            _mapping(row, label="hard230 selector summary")
            for row in _sequence(
                population.get("selector_summaries"),
                label="hard230 selector summaries",
            )
        ]
        raw_books = [
            _mapping(row, label="hard230 book")
            for row in _sequence(population.get("books"), label="hard230 books")
        ]
        expected_selectors = [
            ("native-grouped-rank150", grouped_id, rank_id)
            for grouped_id, rank_id in NATIVE_SELECTORS
        ] + [("effective-independent-shots-dpp", None, DPP_SELECTOR_ID)]
        if (
            len(selector_summaries) != len(expected_selectors)
            or population.get("selector_summaries_sha256")
            != _hash(selector_summaries)
            or len(raw_books) != len(expected_selectors) * len(ENTRY_BUDGETS)
            or population.get("books_sha256") != _hash(raw_books)
        ):
            _fail("hard230 selector summary/book lattice differs")

        for selector_ordinal, (
            summary, (family, expected_grouped_id, expected_rank_id)
        ) in enumerate(zip(selector_summaries, expected_selectors, strict=True)):
            if set(summary) != {
                "grouped_selector_id", "rank150_selector_id",
                "grouped_rank80_lineup_ids", "ranked_lineup_ids",
                "grouped_diagnostics_sha256", "rank150_diagnostics_sha256",
                "exact_grouped_rank80_prefix_parity", "book_sha256s",
            }:
                _fail("hard230 selector summary fields differ")
            ranked = [
                str(lineup_id)
                for lineup_id in _sequence(
                    summary.get("ranked_lineup_ids"),
                    label="hard230 ranked lineup IDs",
                )
            ]
            selector_books = raw_books[
                selector_ordinal * len(ENTRY_BUDGETS):
                (selector_ordinal + 1) * len(ENTRY_BUDGETS)
            ]
            if (
                summary.get("grouped_selector_id") != expected_grouped_id
                or summary.get("rank150_selector_id") != expected_rank_id
                or len(ranked) != max(ENTRY_BUDGETS)
                or len(set(ranked)) != len(ranked)
                or not set(ranked) <= set(sampled)
                or summary.get("book_sha256s")
                != [book.get("book_sha256") for book in selector_books]
            ):
                _fail("hard230 selector rank/persisted-book binding differs")
            _digest(
                summary.get("rank150_diagnostics_sha256"),
                label="hard230 selector rank diagnostics",
            )
            if family == "native-grouped-rank150":
                grouped_rank80 = [
                    str(lineup_id)
                    for lineup_id in _sequence(
                        summary.get("grouped_rank80_lineup_ids"),
                        label="hard230 grouped rank-80 lineup IDs",
                    )
                ]
                if (
                    grouped_rank80 != ranked[:80]
                    or summary.get("exact_grouped_rank80_prefix_parity") is not True
                ):
                    _fail("hard230 native grouped/rank150 prefix parity differs")
                _digest(
                    summary.get("grouped_diagnostics_sha256"),
                    label="hard230 grouped diagnostics",
                )
            elif (
                summary.get("grouped_rank80_lineup_ids") is not None
                or summary.get("grouped_diagnostics_sha256") is not None
                or summary.get("exact_grouped_rank80_prefix_parity") is not None
            ):
                _fail("hard230 DPP grouped fields differ")

            for book, budget in zip(selector_books, ENTRY_BUDGETS, strict=True):
                coordinate = _mapping(
                    book.get("coordinate"), label="hard230 coordinate"
                )
                selected = [
                    str(lineup_id)
                    for lineup_id in _sequence(
                        book.get("selected_lineup_ids"),
                        label="hard230 selected lineup IDs",
                    )
                ]
                expected_coordinate = {
                    "adapter_id": ADAPTER_ID,
                    "metric_kind": "selected-book",
                    "population_role": role,
                    "population_id": population_id,
                    "selector_family": family,
                    "selector_id": expected_rank_id,
                    "entry_budget": budget,
                }
                if (
                    set(book) != _BOOK_FIELDS
                    or set(coordinate) != _COORDINATE_FIELDS
                    or coordinate != expected_coordinate
                    or selected != ranked[:budget]
                    or book.get("coordinate_sha256") != _hash(coordinate)
                    or book.get("selected_lineup_ids_sha256") != _hash(selected)
                    or book.get("book_sha256")
                    != _hash({
                        key: item for key, item in book.items()
                        if key != "book_sha256"
                    })
                ):
                    _fail("hard230 selected book differs from exact nested prefix")

        populations.append({
            "population_id": population_id,
            "dimensions": {
                "population_role": role,
                "population_id": population_id,
                "full_population_lineup_count": len(lineups),
                "equal_sample_lineup_count": population["equal_sample_lineup_count"],
            },
            "lineups": lineups,
        })
        for book in raw_books:
            selected_ids = [
                str(lineup_id)
                for lineup_id in _sequence(
                    book.get("selected_lineup_ids"),
                    label="hard230 normalized selected lineup IDs",
                )
            ]
            books.append({
                "coordinate": book["coordinate"],
                "coordinate_sha256": book["coordinate_sha256"],
                "population_id": population_id,
                "selected_lineup_ids": selected_ids,
            })
    if (
        retained_equal_count != result.get("equal_sample_lineup_count")
        or retained_equal_count is None
    ):
        _fail("hard230 cross-population equal-count law differs")
    normalized = {
        "source_ordinal": result["source_ordinal"],
        "slate_id": result["slate_id"],
        "populations": populations,
        "books": books,
        "later_source_identity": result["later_source_identity"],
    }
    return normalized


def build_hard230_selector_terminal_v1(
    *,
    hard230_final_root_identity: object,
    hard230_final_root_sha256: str,
    hard230_source_task_manifest_identity: object,
    hard230_source_task_manifest_sha256: str,
    task0_smoke_receipt_identity: object,
    task0_smoke_receipt_sha256: str,
    later_source_identity: object,
    output_prefix: str,
    slate_results: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build one compact create-last terminal after 54 exact slate replays."""
    root_identity = _identity(
        hard230_final_root_identity, label="hard230 final root"
    )
    source_manifest_identity = _identity(
        hard230_source_task_manifest_identity,
        label="hard230 source task manifest",
    )
    smoke_identity = _identity(
        task0_smoke_receipt_identity, label="hard230 task0 smoke receipt"
    )
    later_identity = _identity(later_source_identity, label="later source")
    _digest(hard230_final_root_sha256, label="hard230 final root")
    _digest(
        hard230_source_task_manifest_sha256,
        label="hard230 source task manifest",
    )
    _digest(task0_smoke_receipt_sha256, label="hard230 task0 smoke receipt")
    if (
        type(output_prefix) is not str
        or not output_prefix.startswith("gs://")
        or not output_prefix.endswith("/selector-bridge/")
        or "//" in output_prefix[5:]
    ):
        _fail("hard230 selector output prefix differs")
    results = [
        _mapping(row, label=f"hard230 selector slate[{ordinal}]")
        for ordinal, row in enumerate(slate_results)
    ]
    if (
        len(results) != grader.SOURCE_SLATE_COUNT
        or [row.get("source_ordinal") for row in results]
        != list(range(grader.SOURCE_SLATE_COUNT))
        or len({str(row.get("slate_id")) for row in results})
        != grader.SOURCE_SLATE_COUNT
    ):
        _fail("hard230 selector terminal requires exact ordered 54-slate coverage")
    normalized = [normalized_slate_for_grader_v1(row) for row in results]
    if any(row["later_source_identity"] != later_identity for row in normalized):
        _fail("hard230 terminal later-source binding differs")
    try:
        grader.validate_external_normalized_terminal_v1(
            adapter_id=ADAPTER_ID, slates=normalized
        )
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise CorpusR6Hard230SelectorBridgeV1Error(str(exc)) from exc
    descriptors = [
        {
            "source_ordinal": row["source_ordinal"],
            "slate_id": row["slate_id"],
            "task_result_identity": row["task_result_identity"],
            "process_receipt_identity": row["process_receipt_identity"],
            "slate_result_sha256": row["slate_result_sha256"],
        }
        for row in results
    ]
    contract = frozen_hard230_selector_bridge_contract_v1()
    return _with_hash({
        "schema_version": TERMINAL_SCHEMA,
        "adapter_id": ADAPTER_ID,
        "contract": contract,
        "contract_sha256": contract["contract_sha256"],
        "hard230_final_root_identity": root_identity,
        "hard230_final_root_sha256": hard230_final_root_sha256,
        "hard230_source_task_manifest_identity": source_manifest_identity,
        "hard230_source_task_manifest_sha256": hard230_source_task_manifest_sha256,
        "task0_smoke_receipt_identity": smoke_identity,
        "task0_smoke_receipt_sha256": task0_smoke_receipt_sha256,
        "later_source_identity": later_identity,
        "output_prefix": output_prefix,
        "terminal_uri": f"{output_prefix}full-54/terminal.json",
        "source_slate_count": grader.SOURCE_SLATE_COUNT,
        "slate_results": results,
        "slate_result_descriptors": descriptors,
        "slate_result_descriptors_sha256": _hash(descriptors),
        "all_slate_results_exact_replayed_before_terminal": True,
        "generic_normalized_terminal_validated": True,
        "complete": True,
        "outcome_columns_read": [],
        **_false_authorities(),
    }, field="terminal_sha256")


def validate_hard230_selector_terminal_v1(value: object) -> dict[str, object]:
    """Validate terminal structure; source replay remains an operator gate."""
    terminal = _mapping(value, label="hard230 selector terminal")
    if terminal.get("terminal_sha256") != _hash({
        key: item for key, item in terminal.items() if key != "terminal_sha256"
    }):
        _fail("hard230 selector terminal self-hash differs")
    expected = build_hard230_selector_terminal_v1(
        hard230_final_root_identity=terminal.get("hard230_final_root_identity"),
        hard230_final_root_sha256=str(terminal.get("hard230_final_root_sha256", "")),
        hard230_source_task_manifest_identity=terminal.get(
            "hard230_source_task_manifest_identity"
        ),
        hard230_source_task_manifest_sha256=str(
            terminal.get("hard230_source_task_manifest_sha256", "")
        ),
        task0_smoke_receipt_identity=terminal.get("task0_smoke_receipt_identity"),
        task0_smoke_receipt_sha256=str(
            terminal.get("task0_smoke_receipt_sha256", "")
        ),
        later_source_identity=terminal.get("later_source_identity"),
        output_prefix=str(terminal.get("output_prefix", "")),
        slate_results=_sequence(
            terminal.get("slate_results"), label="hard230 terminal slate results"
        ),
    )
    if _canonical(terminal) != _canonical(expected):
        _fail("hard230 selector terminal structure differs")
    return expected


def normalized_terminal_for_grader_v1(
    value: object,
) -> tuple[dict[str, object], ...]:
    """Return the generic grader surface after terminal validation."""
    terminal = validate_hard230_selector_terminal_v1(value)
    normalized = tuple(
        normalized_slate_for_grader_v1(row)
        for row in terminal["slate_results"]
    )
    try:
        return grader.validate_external_normalized_terminal_v1(
            adapter_id=ADAPTER_ID, slates=normalized
        )
    except grader.CorpusR6NovelRosterRealizedGraderV1Error as exc:
        raise CorpusR6Hard230SelectorBridgeV1Error(str(exc)) from exc


__all__ = [
    "ADAPTER_ID",
    "CONTRACT_ID",
    "CorpusR6Hard230SelectorBridgeV1Error",
    "ENTRY_BUDGETS",
    "SLATE_RESULT_SCHEMA",
    "TERMINAL_SCHEMA",
    "build_hard230_selector_terminal_v1",
    "frozen_hard230_selector_bridge_contract_v1",
    "normalized_slate_for_grader_v1",
    "normalized_terminal_for_grader_v1",
    "run_hard230_selector_slate_v1",
    "validate_hard230_selector_slate_v1",
    "validate_hard230_selector_terminal_v1",
]
