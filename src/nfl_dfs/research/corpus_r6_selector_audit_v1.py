"""Pure repeat-selection and independent-audit evaluation for R6 books.

The module cross-scores canonical rosters from immutable player-draw members,
runs the already-frozen selector dispatcher, and evaluates every book on one
shared audit matrix per law.  It contains no I/O, cloud client, historical
label, or policy/promotion seam.  Existing pinned retrieval modules remain
unchanged.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import corpus_retrieval_engine as retrieval
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    CorpusLegalFeasibilityError,
    _score_matrix_sha256,
    cross_score_full_union,
)
from nfl_dfs.research.object_identity import content_identity
from nfl_dfs.research.corpus_r6_independent_bank_contract_v1 import (
    CONTROL_COUNT,
    CHALLENGER_CAP,
    ENTRY_BUDGET,
    FINAL_FIT_SCOPE_ID,
    THRESHOLD_METRICS,
    PublishCreateOnce,
    ReadExact,
    CorpusR6IndependentBankContractV1Error,
    add_self_hash_v1,
    assert_outcome_free_v1,
    assert_selection_audit_disjoint_members_v1,
    canonical_json_bytes_v1,
    canonical_sha256_v1,
    control_strategy_definitions_v1,
    exact_control_registry_v1,
    normalize_code_identity_v1,
    normalize_content_identity_v1,
    publish_body_create_once_v1,
    reopen_body_exact_v1,
    reopen_draw_source_v1,
    reopen_json_identity_v1,
    strategy_executable_fingerprint_v1,
    validate_challenger_registry_v1,
    validate_candidate_authority_v1,
    validate_crn_pairing_v1,
    validate_draw_bank_member_v1,
    validate_fixed_precision_rule_v1,
    validate_independent_bank_plan_v1,
    validate_self_hash_v1,
)


MATRIX_BINDING_SCHEMA: Final = "corpus-r6-candidate-score-matrix-binding/v1"
BOOK_SCHEMA: Final = "corpus-r6-selection-bank-book/v1"
BOOK_FREEZE_SCHEMA: Final = "corpus-r6-selection-bank-book-freeze/v2"
BOOK_METRICS_SCHEMA: Final = "corpus-r6-independent-book-metrics/v1"
PAIRED_DISCORDANCE_SCHEMA: Final = "corpus-r6-paired-discordance/v1"
AUDIT_BOOK_SCHEMA: Final = "corpus-r6-independent-audit-book/v1"
AUDIT_RESULT_SCHEMA: Final = "corpus-r6-independent-selector-audit/v2"
REPEAT_SELECTION_SCHEMA: Final = "corpus-r6-repeat-selection-summary/v2"
FIXED_LEDGER_SCHEMA: Final = "corpus-r6-fixed-ledger-audit-summary/v2"
BOOK_FREEZE_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-selection-book-freeze-authority/v2"
)
AUDIT_RESULT_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-selector-audit-result-authority/v2"
)

DEFAULT_THRESHOLDS: Final = tuple(
    (metric_id, threshold, operator)
    for metric_id, (threshold, operator) in THRESHOLD_METRICS.items()
)

class CorpusR6SelectorAuditV1Error(ValueError):
    """A selection or audit receipt cannot preserve its frozen binding."""


def _fail(message: str) -> None:
    raise CorpusR6SelectorAuditV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _keys(value: Mapping[str, object], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        _fail(f"{label} fields differ")


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _sha256(value: object, *, label: str) -> str:
    retained = _string(value, label=label)
    if len(retained) != 64 or any(character not in "0123456789abcdef" for character in retained):
        _fail(f"{label} must be lowercase SHA-256")
    return retained


def _finite_float(value: object, *, label: str) -> float:
    if type(value) not in {int, float} or type(value) is bool:
        _fail(f"{label} must be a finite number")
    retained = float(value)
    if not math.isfinite(retained):
        _fail(f"{label} must be finite")
    return retained


def _exact_body_identity_v1(
    body: Mapping[str, object],
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
) -> dict[str, object]:
    try:
        return reopen_body_exact_v1(
            body, identity_value, read_exact=read_exact, label=label
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc


def _validated_exact_plan_v1(
    plan_value: object, plan_identity_value: object, *, read_exact: ReadExact
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        plan = validate_independent_bank_plan_v1(
            plan_value, read_exact=read_exact
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    identity = _exact_body_identity_v1(
        plan,
        plan_identity_value,
        read_exact=read_exact,
        label="independent-bank plan",
    )
    return plan, identity


def _require_draw_source_reopen_v1(
    *,
    member: Mapping[str, object],
    players: Sequence[rw.PlayerSpec],
    player_draws: np.ndarray,
    read_exact: ReadExact,
) -> None:
    try:
        validate_draw_bank_member_v1(
            member,
            players=players,
            player_draws=player_draws,
        )
        reopen_draw_source_v1(
            source_identity=member["source_identity"],
            players=players,
            player_draws=player_draws,
            precursor_design_identity=member["precursor_design_identity"],
            precursor_design_sha256=member["precursor_design_sha256"],
            read_exact=read_exact,
        )
    except (CorpusR6IndependentBankContractV1Error, TypeError, ValueError) as exc:
        raise CorpusR6SelectorAuditV1Error(
            f"draw source exact-generation reopen failed: {exc}"
        ) from exc


def _candidate_ids(value: object) -> list[str]:
    ids = [
        _string(item, label="candidate lineup id")
        for item in _sequence(value, label="candidate lineup ids")
    ]
    if len(ids) < ENTRY_BUDGET or ids != sorted(set(ids)):
        _fail("candidate lineup ids must be sorted, unique, and support exact-80")
    return ids


def _candidate_inputs_from_plan_v1(
    plan: Mapping[str, object], *, read_exact: ReadExact
) -> tuple[list[str], dict[str, tuple[str, ...]]]:
    try:
        raw, identity = reopen_json_identity_v1(
            plan["candidate_authority_identity"],
            read_exact=read_exact,
            label="candidate authority",
        )
        authority = validate_candidate_authority_v1(raw)
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    if (
        identity != plan["candidate_authority_identity"]
        or authority["candidate_authority_sha256"]
        != plan["candidate_authority_sha256"]
        or authority["candidate_lineup_count"] != plan["candidate_lineup_count"]
        or authority["candidate_lineup_ids_sha256"]
        != plan["candidate_lineup_ids_sha256"]
        or authority["candidate_rosters_sha256"]
        != plan["candidate_rosters_sha256"]
    ):
        _fail("candidate authority differs from the exact plan")
    ids = [str(value) for value in authority["candidate_lineup_ids"]]
    rosters = {
        str(row["lineup_id"]): tuple(str(value) for value in row["roster_player_ids"])
        for row in authority["candidate_rosters"]
    }
    return ids, rosters


def _canonical_rosters(
    lineup_ids: Sequence[str], roster_by_lineup_id: Mapping[str, Sequence[object]]
) -> tuple[tuple[str, ...], ...]:
    if not isinstance(roster_by_lineup_id, Mapping) or any(
        type(key) is not str for key in roster_by_lineup_id
    ):
        _fail("roster map must be string keyed")
    ids = list(lineup_ids)
    if set(roster_by_lineup_id) != set(ids):
        _fail("roster map does not exactly cover the candidate ids")
    rosters: list[tuple[str, ...]] = []
    for lineup_id in ids:
        raw = _sequence(
            roster_by_lineup_id[lineup_id], label=f"roster {lineup_id}"
        )
        roster = tuple(_string(value, label="roster player id") for value in raw)
        if (
            len(roster) != rw.ROSTER_SIZE
            or len(set(roster)) != rw.ROSTER_SIZE
            or roster != tuple(sorted(roster))
        ):
            _fail("candidate roster must be nine unique canonical sorted ids")
        rosters.append(roster)
    if len(rosters) != len(set(rosters)):
        _fail("distinct candidate ids cannot bind duplicate rosters")
    return tuple(rosters)


def candidate_rosters_sha256_v1(
    lineup_ids: Sequence[str], roster_by_lineup_id: Mapping[str, Sequence[object]]
) -> str:
    ids = _candidate_ids(lineup_ids)
    rosters = _canonical_rosters(ids, roster_by_lineup_id)
    return canonical_sha256_v1([
        {"lineup_id": lineup_id, "roster_player_ids": list(roster)}
        for lineup_id, roster in zip(ids, rosters, strict=True)
    ])


def cross_score_candidate_matrix_v1(
    *,
    bank_member: Mapping[str, object],
    players: Sequence[rw.PlayerSpec],
    player_draws: np.ndarray,
    candidate_lineup_ids: Sequence[str],
    roster_by_lineup_id: Mapping[str, Sequence[object]],
) -> tuple[np.ndarray, dict[str, object]]:
    """Cross-score a roster universe and bind the derived matrix to its draw member."""
    try:
        member = validate_draw_bank_member_v1(
            bank_member, players=players, player_draws=player_draws
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    ids = _candidate_ids(candidate_lineup_ids)
    rosters = _canonical_rosters(ids, roster_by_lineup_id)
    try:
        scores = cross_score_full_union(
            players,
            player_draws,
            rosters,
            expected_worlds=int(member["player_draws"]["shape"][1]),
        )
    except CorpusLegalFeasibilityError as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    body = {
        "schema_version": MATRIX_BINDING_SCHEMA,
        "draw_bank_member_sha256": member["draw_bank_member_sha256"],
        "bank_role": member["role"],
        "slate_id": member["slate_id"],
        "law_id": member["law_id"],
        "law_sha256": member["law_sha256"],
        "player_ids_sha256": member["player_ids_sha256"],
        "player_catalog_sha256": member["player_catalog_sha256"],
        "player_draws_sha256": member["player_draws"]["sha256"],
        "candidate_lineup_ids_sha256": canonical_sha256_v1(ids),
        "candidate_rosters_sha256": candidate_rosters_sha256_v1(
            ids, roster_by_lineup_id
        ),
        "score_matrix_shape": [int(scores.shape[0]), int(scores.shape[1])],
        "score_matrix_sha256": _score_matrix_sha256(scores),
    }
    assert_outcome_free_v1(body, label="candidate score matrix binding")
    return scores, add_self_hash_v1(body, field="matrix_binding_sha256")


def validate_matrix_binding_v1(
    value: object,
    *,
    bank_member: Mapping[str, object],
    candidate_lineup_ids: Sequence[str],
    scores: np.ndarray,
    candidate_rosters_sha256: str | None = None,
) -> dict[str, object]:
    binding = _mapping(value, label="candidate score matrix binding")
    _keys(binding, {
        "schema_version",
        "draw_bank_member_sha256",
        "bank_role",
        "slate_id",
        "law_id",
        "law_sha256",
        "player_ids_sha256",
        "player_catalog_sha256",
        "player_draws_sha256",
        "candidate_lineup_ids_sha256",
        "candidate_rosters_sha256",
        "score_matrix_shape",
        "score_matrix_sha256",
        "matrix_binding_sha256",
    }, label="candidate score matrix binding")
    assert_outcome_free_v1(binding, label="candidate score matrix binding")
    try:
        member = validate_draw_bank_member_v1(bank_member)
        validate_self_hash_v1(
            binding,
            field="matrix_binding_sha256",
            label="candidate score matrix binding",
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    if binding["schema_version"] != MATRIX_BINDING_SCHEMA:
        _fail("candidate score matrix binding schema differs")
    matrix = np.asarray(scores)
    ids = _candidate_ids(candidate_lineup_ids)
    if (
        matrix.dtype != np.dtype(np.float64)
        or matrix.ndim != 2
        or matrix.shape[0] != len(ids)
        or matrix.shape[1] != member["player_draws"]["shape"][1]
        or not np.isfinite(matrix).all()
    ):
        _fail("candidate score matrix shape/dtype/content differs")
    expected = {
        "draw_bank_member_sha256": member["draw_bank_member_sha256"],
        "bank_role": member["role"],
        "slate_id": member["slate_id"],
        "law_id": member["law_id"],
        "law_sha256": member["law_sha256"],
        "player_ids_sha256": member["player_ids_sha256"],
        "player_catalog_sha256": member["player_catalog_sha256"],
        "player_draws_sha256": member["player_draws"]["sha256"],
        "candidate_lineup_ids_sha256": canonical_sha256_v1(ids),
        "score_matrix_shape": [int(matrix.shape[0]), int(matrix.shape[1])],
        "score_matrix_sha256": _score_matrix_sha256(matrix),
    }
    for key, expected_value in expected.items():
        if binding[key] != expected_value:
            _fail(f"candidate score matrix binding {key} differs")
    _sha256(binding["candidate_rosters_sha256"], label="candidate rosters sha256")
    if (
        candidate_rosters_sha256 is not None
        and binding["candidate_rosters_sha256"] != candidate_rosters_sha256
    ):
        _fail("candidate roster binding differs")
    return binding


def _run_strategy(
    strategy: Mapping[str, object],
    *,
    scores: np.ndarray,
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    try:
        selected, trace = runner._run_strategy_v2(
            strategy, training_scores=scores, lineup_ids=lineup_ids
        )
    except (runner.CorpusBatchRetrievalV2Error, retrieval.CorpusRetrievalError) as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    if (
        len(selected) != ENTRY_BUDGET
        or len(set(selected)) != ENTRY_BUDGET
        or any(index < 0 or index >= len(lineup_ids) for index in selected)
        or len(trace) != ENTRY_BUDGET
    ):
        _fail("registered selector did not return exact-80 unique entries")
    return [int(value) for value in selected], [dict(value) for value in trace]


def _validate_trace_row_v1(
    value: object,
    *,
    strategy: Mapping[str, object],
    rank: int,
    position: int,
    lineup_id: str,
) -> dict[str, object]:
    row = _mapping(value, label="selection trace row")
    expected = {
        "selection_rank", "lineup_index", "lineup_id", "marginal_utility",
        "discovery_primary_event_count", "discovery_mean_score",
    }
    if strategy["method"] == "greedy-blockmin-ladder-v1":
        expected |= {
            "block_utilities_before", "block_utilities_added",
            "block_utilities_after", "leximin_profile_after",
        }
    _keys(row, expected, label="selection trace row")
    if (
        row["selection_rank"] != rank
        or row["lineup_index"] != position
        or row["lineup_id"] != lineup_id
    ):
        _fail("selection trace row differs")
    _finite_float(row["marginal_utility"], label="trace marginal utility")
    _integer(
        row["discovery_primary_event_count"],
        label="trace discovery primary event count",
    )
    _finite_float(row["discovery_mean_score"], label="trace discovery mean score")
    if strategy["method"] == "greedy-blockmin-ladder-v1":
        arrays = [
            [
                _integer(item, label=f"trace {field} value")
                for item in _sequence(row[field], label=f"trace {field}")
            ]
            for field in (
                "block_utilities_before", "block_utilities_added",
                "block_utilities_after", "leximin_profile_after",
            )
        ]
        if not arrays[0] or any(len(values) != len(arrays[0]) for values in arrays):
            _fail("blockmin trace arrays differ")
    return row


def _freeze_books_on_verified_selection_matrix_v1(
    *,
    independent_bank_plan: Mapping[str, object],
    independent_bank_plan_identity: Mapping[str, object],
    selection_member: Mapping[str, object],
    candidate_lineup_ids: Sequence[str],
    selection_scores: np.ndarray,
    selection_matrix_binding: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Internal selector runner; callers cannot use this as certification."""
    try:
        plan, plan_identity = _validated_exact_plan_v1(
            independent_bank_plan,
            independent_bank_plan_identity,
            read_exact=read_exact,
        )
        member = validate_draw_bank_member_v1(
            selection_member, expected_role="selection"
        )
        normalized_challengers = validate_challenger_registry_v1(
            plan["challengers"]
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    ids = _candidate_ids(candidate_lineup_ids)
    matrix = np.asarray(selection_scores)
    binding = validate_matrix_binding_v1(
        selection_matrix_binding,
        bank_member=member,
        candidate_lineup_ids=ids,
        scores=matrix,
    )
    planned_members = {
        str(value["draw_bank_member_sha256"]): value
        for value in plan["selection_bank_root"]["members"]
    }
    member_sha = str(member["draw_bank_member_sha256"])
    if (
        member_sha not in planned_members
        or canonical_json_bytes_v1(member)
        != canonical_json_bytes_v1(planned_members[member_sha])
        or len(ids) != plan["candidate_lineup_count"]
        or canonical_sha256_v1(ids) != plan["candidate_lineup_ids_sha256"]
        or binding["candidate_rosters_sha256"]
        != plan["candidate_rosters_sha256"]
        or member["generation_code_identity"]
        not in plan["generation_code_identities"]
    ):
        _fail("selection inputs differ from the exact independent-bank plan")
    freeze_role = (
        "designated-audit-book"
        if member_sha == plan["designated_selection_member_sha256"]
        else "repeat-selection-diagnostic"
    )
    replicate_id = str(member["member_id"])
    strategies: list[tuple[str, Mapping[str, object]]] = [
        ("control", strategy) for strategy in control_strategy_definitions_v1()
    ] + [
        ("challenger", row["strategy"]) for row in normalized_challengers
    ]
    books: list[dict[str, object]] = []
    for family, strategy in strategies:
        selected, trace = _run_strategy(
            strategy, scores=matrix, lineup_ids=ids
        )
        selected_ids = [ids[index] for index in selected]
        for rank, (index, row) in enumerate(zip(selected, trace, strict=True)):
            _validate_trace_row_v1(
                row,
                strategy=strategy,
                rank=rank,
                position=index,
                lineup_id=ids[index],
            )
        body = {
            "schema_version": BOOK_SCHEMA,
            "book_id": (
                f"{replicate_id}:{FINAL_FIT_SCOPE_ID}:{strategy['strategy_id']}"
            ),
            "strategy_family": family,
            "strategy_ordinal": strategy["ordinal"],
            "strategy_id": strategy["strategy_id"],
            "strategy_sha256": strategy["strategy_sha256"],
            "executable_fingerprint_sha256": (
                strategy_executable_fingerprint_v1(strategy)
            ),
            "fit_scope_id": FINAL_FIT_SCOPE_ID,
            "entry_count": ENTRY_BUDGET,
            "selection_member_sha256": member["draw_bank_member_sha256"],
            "selection_matrix_binding_sha256": binding["matrix_binding_sha256"],
            "selected_indices": selected,
            "selected_lineup_ids": selected_ids,
            "selection_trace": trace,
        }
        assert_outcome_free_v1(body, label="selection book")
        books.append(add_self_hash_v1(body, field="selection_book_sha256"))
    if (
        len(books) != CONTROL_COUNT + len(normalized_challengers)
        or [book["strategy_id"] for book in books[:CONTROL_COUNT]]
        != [row[1] for row in exact_control_registry_v1_identities()]
    ):
        _fail("selection book registry differs")
    body = {
        "schema_version": BOOK_FREEZE_SCHEMA,
        "replicate_id": replicate_id,
        "slate_id": member["slate_id"],
        "law_id": member["law_id"],
        "fit_scope_id": FINAL_FIT_SCOPE_ID,
        "freeze_role": freeze_role,
        "selection_member": member,
        "selection_matrix_binding": binding,
        "independent_bank_plan_sha256": plan[
            "independent_bank_plan_sha256"
        ],
        "independent_bank_plan_identity": plan_identity,
        "candidate_authority_identity": plan["candidate_authority_identity"],
        "candidate_authority_sha256": plan["candidate_authority_sha256"],
        "candidate_lineup_ids": ids,
        "candidate_lineup_count": len(ids),
        "candidate_lineup_ids_sha256": canonical_sha256_v1(ids),
        "candidate_rosters_sha256": binding["candidate_rosters_sha256"],
        "control_registry": exact_control_registry_v1(),
        "challengers": normalized_challengers,
        "challenger_registry_sha256": plan["challenger_registry_sha256"],
        "primary_control_id": plan["primary_control_id"],
        "primary_strategy_id": plan["primary_strategy_id"],
        "designated_selection_member_id": plan[
            "designated_selection_member_id"
        ],
        "designated_selection_member_sha256": plan[
            "designated_selection_member_sha256"
        ],
        "contract_code_identity": plan["contract_code_identity"],
        "selector_audit_code_identity": plan["selector_audit_code_identity"],
        "generation_code_identity": member["generation_code_identity"],
        "control_count": CONTROL_COUNT,
        "challenger_count": len(normalized_challengers),
        "book_count": len(books),
        "books": books,
        "audit_bank_opened": False,
        "analysis_mode": plan["analysis_mode"],
        "eligibility_class": plan["eligibility_class"],
        "inference_claims_allowed": False,
        "evidence_tier": "simulated-selection-only",
    }
    assert_outcome_free_v1(body, label="selection book freeze")
    return add_self_hash_v1(body, field="book_freeze_sha256")


def cross_score_and_freeze_books_v1(
    *,
    independent_bank_plan: Mapping[str, object],
    independent_bank_plan_identity: Mapping[str, object],
    selection_member: Mapping[str, object],
    players: Sequence[rw.PlayerSpec],
    player_draws: np.ndarray,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Cross-score exact rosters and freeze books in one indivisible operation."""
    plan, _ = _validated_exact_plan_v1(
        independent_bank_plan,
        independent_bank_plan_identity,
        read_exact=read_exact,
    )
    candidate_lineup_ids, roster_by_lineup_id = _candidate_inputs_from_plan_v1(
        plan, read_exact=read_exact
    )
    _require_draw_source_reopen_v1(
        member=selection_member,
        players=players,
        player_draws=player_draws,
        read_exact=read_exact,
    )
    scores, binding = cross_score_candidate_matrix_v1(
        bank_member=selection_member,
        players=players,
        player_draws=player_draws,
        candidate_lineup_ids=candidate_lineup_ids,
        roster_by_lineup_id=roster_by_lineup_id,
    )
    return _freeze_books_on_verified_selection_matrix_v1(
        independent_bank_plan=independent_bank_plan,
        independent_bank_plan_identity=independent_bank_plan_identity,
        selection_member=selection_member,
        candidate_lineup_ids=candidate_lineup_ids,
        selection_scores=scores,
        selection_matrix_binding=binding,
        read_exact=read_exact,
    )


def exact_control_registry_v1_identities() -> tuple[tuple[int, str, str], ...]:
    return tuple(
        (row["ordinal"], row["strategy_id"], row["strategy_sha256"])
        for row in exact_control_registry_v1()
    )


def validate_book_freeze_v1(value: object) -> dict[str, object]:
    """Validate retained structure only; this grants no replay authority."""
    freeze = _mapping(value, label="selection book freeze")
    _keys(freeze, {
        "schema_version",
        "replicate_id",
        "slate_id",
        "law_id",
        "fit_scope_id",
        "freeze_role",
        "selection_member",
        "selection_matrix_binding",
        "independent_bank_plan_sha256",
        "independent_bank_plan_identity",
        "candidate_authority_identity",
        "candidate_authority_sha256",
        "candidate_lineup_ids",
        "candidate_lineup_count",
        "candidate_lineup_ids_sha256",
        "candidate_rosters_sha256",
        "control_registry",
        "challengers",
        "challenger_registry_sha256",
        "primary_control_id",
        "primary_strategy_id",
        "designated_selection_member_id",
        "designated_selection_member_sha256",
        "contract_code_identity",
        "selector_audit_code_identity",
        "generation_code_identity",
        "control_count",
        "challenger_count",
        "book_count",
        "books",
        "audit_bank_opened",
        "analysis_mode",
        "eligibility_class",
        "inference_claims_allowed",
        "evidence_tier",
        "book_freeze_sha256",
    }, label="selection book freeze")
    assert_outcome_free_v1(freeze, label="selection book freeze")
    try:
        validate_self_hash_v1(
            freeze, field="book_freeze_sha256", label="selection book freeze"
        )
        member = validate_draw_bank_member_v1(
            freeze["selection_member"], expected_role="selection"
        )
        controls = exact_control_registry_v1()
        if canonical_json_bytes_v1(freeze["control_registry"]) != canonical_json_bytes_v1(controls):
            raise CorpusR6IndependentBankContractV1Error(
                "control registry is not the exact-eight all-block final-fit registry"
            )
        challengers = validate_challenger_registry_v1(freeze["challengers"])
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    if (
        freeze["schema_version"] != BOOK_FREEZE_SCHEMA
        or freeze["fit_scope_id"] != FINAL_FIT_SCOPE_ID
        or freeze["slate_id"] != member["slate_id"]
        or freeze["law_id"] != member["law_id"]
        or freeze["replicate_id"] != member["member_id"]
        or freeze["freeze_role"]
        not in {"designated-audit-book", "repeat-selection-diagnostic"}
        or freeze["control_count"] != CONTROL_COUNT
        or freeze["challenger_count"] != len(challengers)
        or freeze["audit_bank_opened"] is not False
        or freeze["analysis_mode"]
        != "descriptive-fixed-ledger-no-inference-v1"
        or freeze["eligibility_class"]
        != "descriptive-only-no-promotion-authority"
        or freeze["inference_claims_allowed"] is not False
        or freeze["evidence_tier"] != "simulated-selection-only"
    ):
        _fail("selection book freeze fixed law differs")
    _string(freeze["replicate_id"], label="replicate id")
    _string(freeze["slate_id"], label="slate id")
    _string(freeze["law_id"], label="law id")
    _sha256(
        freeze["independent_bank_plan_sha256"],
        label="independent-bank plan sha256",
    )
    try:
        plan_identity = normalize_content_identity_v1(
            freeze["independent_bank_plan_identity"],
            label="independent-bank plan",
        )
        candidate_authority_identity = normalize_content_identity_v1(
            freeze["candidate_authority_identity"], label="candidate authority"
        )
        contract_code = normalize_code_identity_v1(
            freeze["contract_code_identity"],
            label="independent-bank contract code",
        )
        selector_code = normalize_code_identity_v1(
            freeze["selector_audit_code_identity"],
            label="selector-audit code",
        )
        generation_code = normalize_code_identity_v1(
            freeze["generation_code_identity"],
            label="draw generation code",
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    if (
        plan_identity != freeze["independent_bank_plan_identity"]
        or candidate_authority_identity != freeze["candidate_authority_identity"]
        or contract_code != freeze["contract_code_identity"]
        or selector_code != freeze["selector_audit_code_identity"]
        or generation_code != freeze["generation_code_identity"]
        or generation_code != member["generation_code_identity"]
    ):
        _fail("selection freeze authority identities are not canonical")
    _sha256(
        freeze["candidate_authority_sha256"], label="candidate authority sha256"
    )
    _sha256(
        freeze["designated_selection_member_sha256"],
        label="designated selection member sha256",
    )
    _string(
        freeze["designated_selection_member_id"],
        label="designated selection member id",
    )
    ids = _candidate_ids(freeze["candidate_lineup_ids"])
    if (
        freeze["candidate_lineup_count"] != len(ids)
        or freeze["candidate_lineup_ids_sha256"] != canonical_sha256_v1(ids)
    ):
        _fail("selection book freeze candidate ids differ")
    _sha256(freeze["candidate_rosters_sha256"], label="candidate rosters sha256")
    _sha256(
        freeze["challenger_registry_sha256"],
        label="challenger registry sha256",
    )
    registered_strategy_ids = [
        *[row[1] for row in exact_control_registry_v1_identities()],
        *[str(row["challenger_id"]) for row in challengers],
    ]
    if (
        freeze["challenger_registry_sha256"] != canonical_sha256_v1(challengers)
        or freeze["primary_control_id"]
        not in [row[1] for row in exact_control_registry_v1_identities()]
        or freeze["primary_strategy_id"] not in registered_strategy_ids
        or freeze["primary_strategy_id"] == freeze["primary_control_id"]
        or (
            freeze["freeze_role"] == "designated-audit-book"
            and (
                freeze["designated_selection_member_id"] != member["member_id"]
                or freeze["designated_selection_member_sha256"]
                != member["draw_bank_member_sha256"]
            )
        )
        or (
            freeze["freeze_role"] == "repeat-selection-diagnostic"
            and member["draw_bank_member_sha256"]
            == freeze["designated_selection_member_sha256"]
        )
    ):
        _fail("selection freeze plan-owned strategy authority differs")
    binding = _mapping(freeze["selection_matrix_binding"], label="selection matrix binding")
    _keys(binding, {
        "schema_version",
        "draw_bank_member_sha256",
        "bank_role",
        "slate_id",
        "law_id",
        "law_sha256",
        "player_ids_sha256",
        "player_catalog_sha256",
        "player_draws_sha256",
        "candidate_lineup_ids_sha256",
        "candidate_rosters_sha256",
        "score_matrix_shape",
        "score_matrix_sha256",
        "matrix_binding_sha256",
    }, label="selection matrix binding")
    try:
        validate_self_hash_v1(
            binding, field="matrix_binding_sha256", label="selection matrix binding"
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    if (
        binding.get("schema_version") != MATRIX_BINDING_SCHEMA
        or binding.get("draw_bank_member_sha256") != member["draw_bank_member_sha256"]
        or binding.get("bank_role") != "selection"
        or binding.get("slate_id") != member["slate_id"]
        or binding.get("law_id") != member["law_id"]
        or binding.get("law_sha256") != member["law_sha256"]
        or binding.get("player_ids_sha256") != member["player_ids_sha256"]
        or binding.get("player_catalog_sha256") != member["player_catalog_sha256"]
        or binding.get("player_draws_sha256") != member["player_draws"]["sha256"]
        or binding.get("candidate_lineup_ids_sha256") != freeze["candidate_lineup_ids_sha256"]
        or binding.get("candidate_rosters_sha256") != freeze["candidate_rosters_sha256"]
        or binding.get("score_matrix_shape")
        != [len(ids), member["player_draws"]["shape"][1]]
    ):
        _fail("selection matrix binding differs from freeze")
    _sha256(binding.get("score_matrix_sha256"), label="selection score matrix sha256")
    books = _sequence(freeze["books"], label="selection books")
    expected_strategies = list(control_strategy_definitions_v1()) + [
        row["strategy"] for row in challengers
    ]
    if freeze["book_count"] != len(books) or len(books) != len(expected_strategies):
        _fail("selection book count differs")
    seen_book_ids: set[str] = set()
    for index, (raw_book, strategy) in enumerate(zip(books, expected_strategies, strict=True)):
        book = _mapping(raw_book, label=f"selection book[{index}]")
        _keys(book, {
            "schema_version",
            "book_id",
            "strategy_family",
            "strategy_ordinal",
            "strategy_id",
            "strategy_sha256",
            "executable_fingerprint_sha256",
            "fit_scope_id",
            "entry_count",
            "selection_member_sha256",
            "selection_matrix_binding_sha256",
            "selected_indices",
            "selected_lineup_ids",
            "selection_trace",
            "selection_book_sha256",
        }, label="selection book")
        try:
            validate_self_hash_v1(
                book, field="selection_book_sha256", label="selection book"
            )
        except CorpusR6IndependentBankContractV1Error as exc:
            raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
        expected_family = "control" if index < CONTROL_COUNT else "challenger"
        if (
            book["schema_version"] != BOOK_SCHEMA
            or book["book_id"]
            != f"{freeze['replicate_id']}:{FINAL_FIT_SCOPE_ID}:{strategy['strategy_id']}"
            or book["strategy_family"] != expected_family
            or book["strategy_ordinal"] != strategy["ordinal"]
            or book["strategy_id"] != strategy["strategy_id"]
            or book["strategy_sha256"] != strategy["strategy_sha256"]
            or book["executable_fingerprint_sha256"]
            != strategy_executable_fingerprint_v1(strategy)
            or book["fit_scope_id"] != FINAL_FIT_SCOPE_ID
            or book["entry_count"] != ENTRY_BUDGET
            or book["selection_member_sha256"] != member["draw_bank_member_sha256"]
            or book["selection_matrix_binding_sha256"] != binding["matrix_binding_sha256"]
        ):
            _fail("selection book authority differs")
        selected = [
            _integer(value, label="selected index")
            for value in _sequence(book["selected_indices"], label="selected indices")
        ]
        selected_ids = [
            _string(value, label="selected lineup id")
            for value in _sequence(
                book["selected_lineup_ids"], label="selected lineup ids"
            )
        ]
        if (
            len(selected) != ENTRY_BUDGET
            or len(set(selected)) != ENTRY_BUDGET
            or max(selected) >= len(ids)
            or selected_ids != [ids[position] for position in selected]
        ):
            _fail("selection book membership differs")
        trace = _sequence(book["selection_trace"], label="selection trace")
        if len(trace) != ENTRY_BUDGET:
            _fail("selection trace length differs")
        for rank, (position, raw_trace) in enumerate(zip(selected, trace, strict=True)):
            _validate_trace_row_v1(
                raw_trace,
                strategy=strategy,
                rank=rank,
                position=position,
                lineup_id=ids[position],
            )
        book_id = _string(book["book_id"], label="selection book id")
        if book_id in seen_book_ids:
            _fail("selection book ids repeat")
        seen_book_ids.add(book_id)
    return freeze


def _validate_book_freeze_plan_binding_v1(
    freeze: Mapping[str, object],
    *,
    independent_bank_plan: Mapping[str, object],
    independent_bank_plan_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    plan, plan_identity = _validated_exact_plan_v1(
        independent_bank_plan,
        independent_bank_plan_identity,
        read_exact=read_exact,
    )
    member = freeze["selection_member"]
    if (
        freeze["independent_bank_plan_sha256"]
        != plan["independent_bank_plan_sha256"]
        or freeze["independent_bank_plan_identity"] != plan_identity
        or freeze["candidate_authority_identity"]
        != plan["candidate_authority_identity"]
        or freeze["candidate_authority_sha256"]
        != plan["candidate_authority_sha256"]
        or freeze["candidate_lineup_count"] != plan["candidate_lineup_count"]
        or freeze["candidate_lineup_ids_sha256"]
        != plan["candidate_lineup_ids_sha256"]
        or freeze["candidate_rosters_sha256"]
        != plan["candidate_rosters_sha256"]
        or freeze["challengers"] != plan["challengers"]
        or freeze["challenger_registry_sha256"]
        != plan["challenger_registry_sha256"]
        or freeze["primary_control_id"] != plan["primary_control_id"]
        or freeze["primary_strategy_id"] != plan["primary_strategy_id"]
        or freeze["designated_selection_member_id"]
        != plan["designated_selection_member_id"]
        or freeze["designated_selection_member_sha256"]
        != plan["designated_selection_member_sha256"]
        or freeze["contract_code_identity"] != plan["contract_code_identity"]
        or freeze["selector_audit_code_identity"]
        != plan["selector_audit_code_identity"]
        or freeze["generation_code_identity"]
        != member["generation_code_identity"]
        or member["generation_code_identity"]
        not in plan["generation_code_identities"]
        or freeze["analysis_mode"] != plan["analysis_mode"]
        or freeze["eligibility_class"] != plan["eligibility_class"]
        or freeze["inference_claims_allowed"]
        != plan["inference_claims_allowed"]
    ):
        _fail("selection freeze differs from the exact independent-bank plan")
    planned_members = {
        str(value["draw_bank_member_sha256"]): value
        for value in plan["selection_bank_root"]["members"]
    }
    member_sha = str(member["draw_bank_member_sha256"])
    if (
        member_sha not in planned_members
        or canonical_json_bytes_v1(member)
        != canonical_json_bytes_v1(planned_members[member_sha])
        or (
            freeze["freeze_role"] == "designated-audit-book"
            and member_sha != plan["designated_selection_member_sha256"]
        )
        or (
            freeze["freeze_role"] == "repeat-selection-diagnostic"
            and member_sha == plan["designated_selection_member_sha256"]
        )
    ):
        _fail("selection freeze member role differs from the ex-ante plan")
    return plan, plan_identity


def validate_book_freeze_authority_v1(
    value: object,
    *,
    independent_bank_plan: Mapping[str, object],
    independent_bank_plan_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    authority = _mapping(value, label="selection book freeze authority")
    _keys(authority, {
        "schema_version",
        "book_freeze",
        "book_freeze_publication_identity",
        "book_freeze_sha256",
        "independent_bank_plan_sha256",
        "independent_bank_plan_identity",
        "publication_mode",
        "book_freeze_authority_sha256",
    }, label="selection book freeze authority")
    assert_outcome_free_v1(authority, label="selection book freeze authority")
    try:
        validate_self_hash_v1(
            authority,
            field="book_freeze_authority_sha256",
            label="selection book freeze authority",
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    freeze = validate_book_freeze_v1(authority["book_freeze"])
    plan, plan_identity = _validate_book_freeze_plan_binding_v1(
        freeze,
        independent_bank_plan=independent_bank_plan,
        independent_bank_plan_identity=independent_bank_plan_identity,
        read_exact=read_exact,
    )
    publication_identity = _exact_body_identity_v1(
        freeze,
        authority["book_freeze_publication_identity"],
        read_exact=read_exact,
        label="published selection book freeze",
    )
    if (
        authority["schema_version"] != BOOK_FREEZE_AUTHORITY_SCHEMA
        or authority["book_freeze_publication_identity"]
        != publication_identity
        or authority["book_freeze_sha256"] != freeze["book_freeze_sha256"]
        or authority["independent_bank_plan_sha256"]
        != plan["independent_bank_plan_sha256"]
        or authority["independent_bank_plan_identity"] != plan_identity
        or authority["publication_mode"]
        != "create-once-generation-pinned-exact-reopen"
    ):
        _fail("selection book freeze authority differs")
    return authority


def authoritative_replay_book_freeze_v1(
    value: object,
    *,
    players: Sequence[rw.PlayerSpec],
    player_draws: np.ndarray,
    independent_bank_plan: Mapping[str, object],
    independent_bank_plan_identity: Mapping[str, object],
    publication_uri: str,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Rebuild a freeze from exact draw inputs and byte-compare it."""
    retained = validate_book_freeze_v1(value)
    _validate_book_freeze_plan_binding_v1(
        retained,
        independent_bank_plan=independent_bank_plan,
        independent_bank_plan_identity=independent_bank_plan_identity,
        read_exact=read_exact,
    )
    rebuilt = cross_score_and_freeze_books_v1(
        independent_bank_plan=independent_bank_plan,
        independent_bank_plan_identity=independent_bank_plan_identity,
        selection_member=retained["selection_member"],
        players=players,
        player_draws=player_draws,
        read_exact=read_exact,
    )
    if canonical_json_bytes_v1(retained) != canonical_json_bytes_v1(rebuilt):
        _fail("selection book freeze authoritative replay differs")
    try:
        published_identity = publish_body_create_once_v1(
            rebuilt,
            uri=publication_uri,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
            label="selection book freeze",
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    body = {
        "schema_version": BOOK_FREEZE_AUTHORITY_SCHEMA,
        "book_freeze": rebuilt,
        "book_freeze_publication_identity": published_identity,
        "book_freeze_sha256": rebuilt["book_freeze_sha256"],
        "independent_bank_plan_sha256": rebuilt[
            "independent_bank_plan_sha256"
        ],
        "independent_bank_plan_identity": rebuilt[
            "independent_bank_plan_identity"
        ],
        "publication_mode": "create-once-generation-pinned-exact-reopen",
    }
    authority = add_self_hash_v1(
        body, field="book_freeze_authority_sha256"
    )
    return validate_book_freeze_authority_v1(
        authority,
        independent_bank_plan=independent_bank_plan,
        independent_bank_plan_identity=independent_bank_plan_identity,
        read_exact=read_exact,
    )


def _threshold_mask(values: np.ndarray, threshold: float, operator: str) -> np.ndarray:
    if operator == ">":
        return values > threshold
    if operator == ">=":
        return values >= threshold
    _fail("threshold operator differs")


def book_metrics_v1(book_scores: np.ndarray) -> dict[str, object]:
    matrix = np.asarray(book_scores)
    if (
        matrix.dtype != np.dtype(np.float64)
        or matrix.ndim != 2
        or not matrix.shape[0]
        or not matrix.shape[1]
        or not np.isfinite(matrix).all()
    ):
        _fail("book metrics require one nonempty finite float64 matrix")
    maxima = matrix.max(axis=0)
    body = {
        "schema_version": BOOK_METRICS_SCHEMA,
        "lineup_count": int(matrix.shape[0]),
        "world_count": int(matrix.shape[1]),
        "expected_book_max": float(maxima.mean(dtype=np.float64)),
        "maximum_book_score": float(maxima.max()),
        "thresholds": [
            {
                "metric_id": metric_id,
                "threshold": threshold,
                "operator": operator,
                "event_count": int(
                    np.count_nonzero(_threshold_mask(maxima, threshold, operator))
                ),
            }
            for metric_id, threshold, operator in DEFAULT_THRESHOLDS
        ],
    }
    return add_self_hash_v1(body, field="book_metrics_sha256")


def paired_discordance_v1(
    control_maxima: np.ndarray, challenger_maxima: np.ndarray
) -> dict[str, object]:
    control = np.asarray(control_maxima)
    challenger = np.asarray(challenger_maxima)
    if (
        control.dtype != np.dtype(np.float64)
        or challenger.dtype != np.dtype(np.float64)
        or control.ndim != 1
        or challenger.shape != control.shape
        or not control.size
        or not np.isfinite(control).all()
        or not np.isfinite(challenger).all()
    ):
        _fail("paired discordance requires aligned finite float64 maxima")
    rows = []
    for metric_id, threshold, operator in DEFAULT_THRESHOLDS:
        control_event = _threshold_mask(control, threshold, operator)
        challenger_event = _threshold_mask(challenger, threshold, operator)
        both = int(np.count_nonzero(control_event & challenger_event))
        neither = int(np.count_nonzero(~control_event & ~challenger_event))
        challenger_only = int(np.count_nonzero(~control_event & challenger_event))
        control_only = int(np.count_nonzero(control_event & ~challenger_event))
        rows.append({
            "metric_id": metric_id,
            "threshold": threshold,
            "operator": operator,
            "both_count": both,
            "neither_count": neither,
            "challenger_only_count": challenger_only,
            "control_only_count": control_only,
            "paired_delta_rate": float(
                (challenger_only - control_only) / control.size
            ),
        })
    body = {
        "schema_version": PAIRED_DISCORDANCE_SCHEMA,
        "world_count": int(control.size),
        "mean_book_max_delta": float(
            (challenger - control).mean(dtype=np.float64)
        ),
        "thresholds": rows,
    }
    return add_self_hash_v1(body, field="paired_discordance_sha256")


def evaluate_books_on_audit_player_draws_v1(
    *,
    audit_member: Mapping[str, object],
    players: Sequence[rw.PlayerSpec],
    player_draws: np.ndarray,
    book_freeze_authority: Mapping[str, object],
    independent_bank_plan: Mapping[str, object],
    independent_bank_plan_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Evaluate every frozen book on one exact shared audit draw matrix."""
    plan, plan_identity = _validated_exact_plan_v1(
        independent_bank_plan,
        independent_bank_plan_identity,
        read_exact=read_exact,
    )
    freeze_authority = validate_book_freeze_authority_v1(
        book_freeze_authority,
        independent_bank_plan=plan,
        independent_bank_plan_identity=plan_identity,
        read_exact=read_exact,
    )
    freeze = freeze_authority["book_freeze"]
    if freeze["freeze_role"] != "designated-audit-book":
        _fail("independent audit requires the ex-ante designated selection book")
    _require_draw_source_reopen_v1(
        member=audit_member,
        players=players,
        player_draws=player_draws,
        read_exact=read_exact,
    )
    try:
        audit = validate_draw_bank_member_v1(
            audit_member,
            expected_role="audit",
            players=players,
            player_draws=player_draws,
        )
        assert_selection_audit_disjoint_members_v1(
            freeze["selection_member"], audit
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    if (
        audit["slate_id"] != freeze["slate_id"]
        or audit["law_id"] != freeze["law_id"]
        or audit["law_sha256"]
        != freeze["selection_member"]["law_sha256"]
        or audit["player_catalog_sha256"]
        != freeze["selection_member"]["player_catalog_sha256"]
        or audit["player_ids_sha256"]
        != freeze["selection_member"]["player_ids_sha256"]
    ):
        _fail("audit member differs from the frozen slate/law/player universe")
    if (
        audit["draw_bank_member_sha256"]
        not in plan["audit_bank_root"]["ordered_member_sha256s"]
        or audit["generation_code_identity"]
        not in plan["generation_code_identities"]
    ):
        _fail("audit member differs from the exact independent-bank plan")
    primary_control_id = str(plan["primary_control_id"])
    candidate_ids, roster_by_lineup_id = _candidate_inputs_from_plan_v1(
        plan, read_exact=read_exact
    )
    if candidate_ids != freeze["candidate_lineup_ids"]:
        _fail("candidate authority order differs from the selection freeze")
    roster_hash = candidate_rosters_sha256_v1(candidate_ids, roster_by_lineup_id)
    if roster_hash != freeze["candidate_rosters_sha256"]:
        _fail("audit candidate rosters differ from the selection freeze")
    selected_union = {
        lineup_id
        for book in freeze["books"]
        for lineup_id in book["selected_lineup_ids"]
    }
    union_ids = [lineup_id for lineup_id in candidate_ids if lineup_id in selected_union]
    union_rosters = {lineup_id: roster_by_lineup_id[lineup_id] for lineup_id in union_ids}
    audit_scores, audit_binding = cross_score_candidate_matrix_v1(
        bank_member=audit,
        players=players,
        player_draws=player_draws,
        candidate_lineup_ids=union_ids,
        roster_by_lineup_id=union_rosters,
    )
    union_index = {lineup_id: index for index, lineup_id in enumerate(union_ids)}
    maxima_by_strategy: dict[str, np.ndarray] = {}
    book_rows: list[dict[str, object]] = []
    for book in freeze["books"]:
        indices = np.asarray(
            [union_index[lineup_id] for lineup_id in book["selected_lineup_ids"]],
            dtype=np.int64,
        )
        scores = np.ascontiguousarray(audit_scores[indices], dtype=np.float64)
        maxima = np.ascontiguousarray(scores.max(axis=0), dtype=np.float64)
        maxima.flags.writeable = False
        strategy_id = str(book["strategy_id"])
        maxima_by_strategy[strategy_id] = maxima
        body = {
            "schema_version": AUDIT_BOOK_SCHEMA,
            "strategy_family": book["strategy_family"],
            "strategy_id": strategy_id,
            "strategy_sha256": book["strategy_sha256"],
            "executable_fingerprint_sha256": book[
                "executable_fingerprint_sha256"
            ],
            "selection_book_sha256": book["selection_book_sha256"],
            "audit_member_sha256": audit["draw_bank_member_sha256"],
            "audit_matrix_binding_sha256": audit_binding["matrix_binding_sha256"],
            "entry_count": ENTRY_BUDGET,
            "book_maxima": [float(value) for value in maxima],
            "book_maxima_sha256": _score_matrix_sha256(maxima.reshape(1, -1)),
            "metrics": book_metrics_v1(scores),
        }
        assert_outcome_free_v1(body, label="audit book")
        book_rows.append(add_self_hash_v1(body, field="audit_book_sha256"))
    control_maxima = maxima_by_strategy[primary_control_id]
    paired = []
    for book in book_rows:
        comparison = paired_discordance_v1(
            control_maxima, maxima_by_strategy[str(book["strategy_id"])]
        )
        body = {
            "primary_control_id": primary_control_id,
            "compared_strategy_id": book["strategy_id"],
            "audit_member_sha256": audit["draw_bank_member_sha256"],
            "crn_scope": "exact-same-audit-member-within-law",
            "paired_discordance": comparison,
        }
        paired.append(add_self_hash_v1(body, field="paired_comparison_sha256"))
    body = {
        "schema_version": AUDIT_RESULT_SCHEMA,
        "slate_id": audit["slate_id"],
        "law_id": audit["law_id"],
        "replicate_id": freeze["replicate_id"],
        "fit_scope_id": FINAL_FIT_SCOPE_ID,
        "book_freeze_sha256": freeze["book_freeze_sha256"],
        "book_freeze_publication_identity": freeze_authority[
            "book_freeze_publication_identity"
        ],
        "book_freeze_authority_sha256": freeze_authority[
            "book_freeze_authority_sha256"
        ],
        "independent_bank_plan_sha256": plan[
            "independent_bank_plan_sha256"
        ],
        "independent_bank_plan_identity": plan_identity,
        "candidate_authority_identity": plan["candidate_authority_identity"],
        "candidate_authority_sha256": plan["candidate_authority_sha256"],
        "audit_member": audit,
        "candidate_rosters_sha256": roster_hash,
        "audit_union_lineup_ids": union_ids,
        "audit_union_lineup_ids_sha256": canonical_sha256_v1(union_ids),
        "audit_matrix_binding": audit_binding,
        "primary_control_id": primary_control_id,
        "primary_strategy_id": plan["primary_strategy_id"],
        "challenger_registry_sha256": plan["challenger_registry_sha256"],
        "contract_code_identity": plan["contract_code_identity"],
        "selector_audit_code_identity": plan["selector_audit_code_identity"],
        "generation_code_identity": audit["generation_code_identity"],
        "control_count": CONTROL_COUNT,
        "challenger_count": freeze["challenger_count"],
        "book_count": len(book_rows),
        "books": book_rows,
        "paired_comparisons": paired,
        "crn_scope": "exact-same-audit-member-within-law",
        "analysis_mode": plan["analysis_mode"],
        "eligibility_class": plan["eligibility_class"],
        "inference_claims_allowed": False,
        "evidence_tier": "simulated-independent-audit-only",
    }
    assert_outcome_free_v1(body, label="selector audit result")
    return add_self_hash_v1(body, field="selector_audit_sha256")


def validate_selector_audit_result_v1(value: object) -> dict[str, object]:
    """Validate retained structure only; this grants no replay authority."""
    result = _mapping(value, label="selector audit result")
    _keys(result, {
        "schema_version",
        "slate_id",
        "law_id",
        "replicate_id",
        "fit_scope_id",
        "book_freeze_sha256",
        "book_freeze_publication_identity",
        "book_freeze_authority_sha256",
        "independent_bank_plan_sha256",
        "independent_bank_plan_identity",
        "candidate_authority_identity",
        "candidate_authority_sha256",
        "audit_member",
        "candidate_rosters_sha256",
        "audit_union_lineup_ids",
        "audit_union_lineup_ids_sha256",
        "audit_matrix_binding",
        "primary_control_id",
        "primary_strategy_id",
        "challenger_registry_sha256",
        "contract_code_identity",
        "selector_audit_code_identity",
        "generation_code_identity",
        "control_count",
        "challenger_count",
        "book_count",
        "books",
        "paired_comparisons",
        "crn_scope",
        "analysis_mode",
        "eligibility_class",
        "inference_claims_allowed",
        "evidence_tier",
        "selector_audit_sha256",
    }, label="selector audit result")
    assert_outcome_free_v1(result, label="selector audit result")
    try:
        validate_self_hash_v1(
            result, field="selector_audit_sha256", label="selector audit result"
        )
        member = validate_draw_bank_member_v1(
            result["audit_member"], expected_role="audit"
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    if (
        result["schema_version"] != AUDIT_RESULT_SCHEMA
        or result["slate_id"] != member["slate_id"]
        or result["law_id"] != member["law_id"]
        or result["fit_scope_id"] != FINAL_FIT_SCOPE_ID
        or result["control_count"] != CONTROL_COUNT
        or result["crn_scope"] != "exact-same-audit-member-within-law"
        or result["analysis_mode"]
        != "descriptive-fixed-ledger-no-inference-v1"
        or result["eligibility_class"]
        != "descriptive-only-no-promotion-authority"
        or result["inference_claims_allowed"] is not False
        or result["evidence_tier"] != "simulated-independent-audit-only"
    ):
        _fail("selector audit result fixed law differs")
    _sha256(result["book_freeze_sha256"], label="book freeze sha256")
    _sha256(
        result["book_freeze_authority_sha256"],
        label="book freeze authority sha256",
    )
    _sha256(
        result["independent_bank_plan_sha256"],
        label="independent-bank plan sha256",
    )
    _sha256(
        result["challenger_registry_sha256"],
        label="challenger registry sha256",
    )
    try:
        freeze_publication_identity = normalize_content_identity_v1(
            result["book_freeze_publication_identity"],
            label="published selection book freeze",
        )
        plan_identity = normalize_content_identity_v1(
            result["independent_bank_plan_identity"],
            label="independent-bank plan",
        )
        candidate_authority_identity = normalize_content_identity_v1(
            result["candidate_authority_identity"], label="candidate authority"
        )
        contract_code = normalize_code_identity_v1(
            result["contract_code_identity"], label="contract code identity"
        )
        selector_code = normalize_code_identity_v1(
            result["selector_audit_code_identity"],
            label="selector-audit code identity",
        )
        generation_code = normalize_code_identity_v1(
            result["generation_code_identity"],
            label="draw generation code identity",
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    if (
        freeze_publication_identity
        != result["book_freeze_publication_identity"]
        or plan_identity != result["independent_bank_plan_identity"]
        or candidate_authority_identity != result["candidate_authority_identity"]
        or contract_code != result["contract_code_identity"]
        or selector_code != result["selector_audit_code_identity"]
        or generation_code != result["generation_code_identity"]
        or generation_code != member["generation_code_identity"]
    ):
        _fail("selector audit authority identities are not canonical")
    _sha256(
        result["candidate_authority_sha256"], label="candidate authority sha256"
    )
    _sha256(result["candidate_rosters_sha256"], label="candidate rosters sha256")
    union_ids = _candidate_ids(result["audit_union_lineup_ids"])
    if result["audit_union_lineup_ids_sha256"] != canonical_sha256_v1(union_ids):
        _fail("audit union lineup ids differ")
    binding = _mapping(result["audit_matrix_binding"], label="audit matrix binding")
    _keys(binding, {
        "schema_version",
        "draw_bank_member_sha256",
        "bank_role",
        "slate_id",
        "law_id",
        "law_sha256",
        "player_ids_sha256",
        "player_catalog_sha256",
        "player_draws_sha256",
        "candidate_lineup_ids_sha256",
        "candidate_rosters_sha256",
        "score_matrix_shape",
        "score_matrix_sha256",
        "matrix_binding_sha256",
    }, label="audit matrix binding")
    try:
        validate_self_hash_v1(
            binding, field="matrix_binding_sha256", label="audit matrix binding"
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    if (
        binding.get("schema_version") != MATRIX_BINDING_SCHEMA
        or binding.get("draw_bank_member_sha256")
        != member["draw_bank_member_sha256"]
        or binding.get("bank_role") != "audit"
        or binding.get("slate_id") != member["slate_id"]
        or binding.get("law_id") != member["law_id"]
        or binding.get("law_sha256") != member["law_sha256"]
        or binding.get("player_ids_sha256") != member["player_ids_sha256"]
        or binding.get("player_catalog_sha256") != member["player_catalog_sha256"]
        or binding.get("player_draws_sha256") != member["player_draws"]["sha256"]
        or binding.get("candidate_lineup_ids_sha256")
        != result["audit_union_lineup_ids_sha256"]
        or binding.get("score_matrix_shape")
        != [len(union_ids), member["player_draws"]["shape"][1]]
    ):
        _fail("audit matrix binding differs")
    _sha256(binding.get("candidate_rosters_sha256"), label="audit union rosters sha256")
    _sha256(binding.get("score_matrix_sha256"), label="audit score matrix sha256")
    books = _sequence(result["books"], label="audit books")
    challenger_count = _integer(
        result["challenger_count"], label="challenger count"
    )
    book_count = _integer(result["book_count"], label="book count")
    if (
        book_count != len(books)
        or challenger_count > CHALLENGER_CAP
        or len(books) != CONTROL_COUNT + challenger_count
    ):
        _fail("audit book count differs")
    maxima_by_strategy: dict[str, np.ndarray] = {}
    strategy_hashes: set[str] = set()
    executable_fingerprints: set[str] = set()
    for index, raw_book in enumerate(books):
        book = _mapping(raw_book, label=f"audit book[{index}]")
        _keys(book, {
            "schema_version",
            "strategy_family",
            "strategy_id",
            "strategy_sha256",
            "executable_fingerprint_sha256",
            "selection_book_sha256",
            "audit_member_sha256",
            "audit_matrix_binding_sha256",
            "entry_count",
            "book_maxima",
            "book_maxima_sha256",
            "metrics",
            "audit_book_sha256",
        }, label="audit book")
        try:
            validate_self_hash_v1(book, field="audit_book_sha256", label="audit book")
        except CorpusR6IndependentBankContractV1Error as exc:
            raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
        if (
            book["schema_version"] != AUDIT_BOOK_SCHEMA
            or book["strategy_family"]
            != ("control" if index < CONTROL_COUNT else "challenger")
            or book["audit_member_sha256"] != member["draw_bank_member_sha256"]
            or book["audit_matrix_binding_sha256"] != binding["matrix_binding_sha256"]
            or book["entry_count"] != ENTRY_BUDGET
        ):
            _fail("audit book authority differs")
        _sha256(book["strategy_sha256"], label="audit strategy sha256")
        _sha256(
            book["executable_fingerprint_sha256"],
            label="audit executable fingerprint sha256",
        )
        if (
            str(book["strategy_sha256"]) in strategy_hashes
            or str(book["executable_fingerprint_sha256"])
            in executable_fingerprints
        ):
            _fail("audit strategies repeat an identity or executable")
        strategy_hashes.add(str(book["strategy_sha256"]))
        executable_fingerprints.add(
            str(book["executable_fingerprint_sha256"])
        )
        _sha256(book["selection_book_sha256"], label="selection book sha256")
        if index < CONTROL_COUNT:
            _, expected_id, expected_hash = exact_control_registry_v1_identities()[index]
            if (
                book["strategy_id"] != expected_id
                or book["strategy_sha256"] != expected_hash
                or book["executable_fingerprint_sha256"]
                != exact_control_registry_v1()[index][
                    "executable_fingerprint_sha256"
                ]
            ):
                _fail("audit exact-eight control identity/order differs")
        elif book["strategy_id"] in {
            row[1] for row in exact_control_registry_v1_identities()
        }:
            _fail("audit challenger collides with an exact control")
        maxima = np.asarray(
            [_finite_float(value, label="book maximum") for value in _sequence(
                book["book_maxima"], label="book maxima"
            )],
            dtype=np.float64,
        )
        if maxima.shape != (member["player_draws"]["shape"][1],):
            _fail("audit book maxima world count differs")
        if book["book_maxima_sha256"] != _score_matrix_sha256(maxima.reshape(1, -1)):
            _fail("audit book maxima hash differs")
        metrics = _mapping(book["metrics"], label="book metrics")
        _keys(metrics, {
            "schema_version",
            "lineup_count",
            "world_count",
            "expected_book_max",
            "maximum_book_score",
            "thresholds",
            "book_metrics_sha256",
        }, label="book metrics")
        try:
            validate_self_hash_v1(
                metrics, field="book_metrics_sha256", label="book metrics"
            )
        except CorpusR6IndependentBankContractV1Error as exc:
            raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
        if (
            metrics.get("schema_version") != BOOK_METRICS_SCHEMA
            or metrics.get("world_count") != maxima.size
            or metrics.get("lineup_count") != ENTRY_BUDGET
            or not math.isclose(
                float(metrics.get("expected_book_max")),
                float(maxima.mean(dtype=np.float64)),
                rel_tol=0.0,
                abs_tol=0.0,
            )
            or float(metrics.get("maximum_book_score")) != float(maxima.max())
        ):
            _fail("audit book metrics differ")
        metric_rows = _sequence(metrics.get("thresholds"), label="book thresholds")
        for raw_metric in metric_rows:
            _keys(
                _mapping(raw_metric, label="book threshold"),
                {"metric_id", "threshold", "operator", "event_count"},
                label="book threshold",
            )
        expected_rows = []
        for metric_id, threshold, operator in DEFAULT_THRESHOLDS:
            expected_rows.append({
                "metric_id": metric_id,
                "threshold": threshold,
                "operator": operator,
                "event_count": int(
                    np.count_nonzero(_threshold_mask(maxima, threshold, operator))
                ),
            })
        if metric_rows != expected_rows:
            _fail("audit book threshold metrics differ")
        strategy_id = _string(book["strategy_id"], label="strategy id")
        if strategy_id in maxima_by_strategy:
            _fail("audit strategy ids repeat")
        maxima_by_strategy[strategy_id] = maxima
    primary_id = _string(result["primary_control_id"], label="primary control id")
    if primary_id not in [row[1] for row in exact_control_registry_v1_identities()]:
        _fail("audit primary control differs")
    primary_strategy_id = _string(
        result["primary_strategy_id"], label="primary strategy id"
    )
    if (
        primary_strategy_id not in maxima_by_strategy
        or primary_strategy_id == primary_id
    ):
        _fail("audit primary strategy differs")
    paired = _sequence(result["paired_comparisons"], label="paired comparisons")
    if len(paired) != len(books):
        _fail("paired comparison count differs")
    for raw_pair, book in zip(paired, books, strict=True):
        pair = _mapping(raw_pair, label="paired comparison")
        _keys(pair, {
            "primary_control_id",
            "compared_strategy_id",
            "audit_member_sha256",
            "crn_scope",
            "paired_discordance",
            "paired_comparison_sha256",
        }, label="paired comparison")
        try:
            validate_self_hash_v1(
                pair, field="paired_comparison_sha256", label="paired comparison"
            )
        except CorpusR6IndependentBankContractV1Error as exc:
            raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
        expected_comparison = paired_discordance_v1(
            maxima_by_strategy[primary_id],
            maxima_by_strategy[str(book["strategy_id"])],
        )
        expected_body = {
            "primary_control_id": primary_id,
            "compared_strategy_id": book["strategy_id"],
            "audit_member_sha256": member["draw_bank_member_sha256"],
            "crn_scope": "exact-same-audit-member-within-law",
            "paired_discordance": expected_comparison,
        }
        expected_pair = add_self_hash_v1(
            expected_body, field="paired_comparison_sha256"
        )
        if canonical_json_bytes_v1(pair) != canonical_json_bytes_v1(expected_pair):
            _fail("paired comparison differs")
    return result


def _validate_selector_audit_plan_binding_v1(
    result: Mapping[str, object],
    *,
    book_freeze_authority: Mapping[str, object],
    independent_bank_plan: Mapping[str, object],
    independent_bank_plan_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    plan, plan_identity = _validated_exact_plan_v1(
        independent_bank_plan,
        independent_bank_plan_identity,
        read_exact=read_exact,
    )
    freeze_authority = validate_book_freeze_authority_v1(
        book_freeze_authority,
        independent_bank_plan=plan,
        independent_bank_plan_identity=plan_identity,
        read_exact=read_exact,
    )
    freeze = freeze_authority["book_freeze"]
    audit_member = result["audit_member"]
    planned_members = {
        str(member["draw_bank_member_sha256"]): member
        for member in plan["audit_bank_root"]["members"]
    }
    member_sha = str(audit_member["draw_bank_member_sha256"])
    if member_sha not in planned_members or canonical_json_bytes_v1(
        audit_member
    ) != canonical_json_bytes_v1(planned_members[member_sha]):
        _fail("selector audit member differs from the exact plan ledger")
    if (
        result["slate_id"] != freeze["slate_id"]
        or result["law_id"] != freeze["law_id"]
        or result["replicate_id"] != freeze["replicate_id"]
        or result["book_freeze_sha256"] != freeze["book_freeze_sha256"]
        or result["book_freeze_publication_identity"]
        != freeze_authority["book_freeze_publication_identity"]
        or result["book_freeze_authority_sha256"]
        != freeze_authority["book_freeze_authority_sha256"]
        or result["independent_bank_plan_sha256"]
        != plan["independent_bank_plan_sha256"]
        or result["independent_bank_plan_identity"] != plan_identity
        or result["candidate_authority_identity"]
        != plan["candidate_authority_identity"]
        or result["candidate_authority_sha256"]
        != plan["candidate_authority_sha256"]
        or result["candidate_rosters_sha256"]
        != plan["candidate_rosters_sha256"]
        or result["primary_control_id"] != plan["primary_control_id"]
        or result["primary_strategy_id"] != plan["primary_strategy_id"]
        or result["challenger_registry_sha256"]
        != plan["challenger_registry_sha256"]
        or result["contract_code_identity"] != plan["contract_code_identity"]
        or result["selector_audit_code_identity"]
        != plan["selector_audit_code_identity"]
        or result["generation_code_identity"]
        != audit_member["generation_code_identity"]
        or audit_member["generation_code_identity"]
        not in plan["generation_code_identities"]
        or result["control_count"] != freeze["control_count"]
        or result["challenger_count"] != freeze["challenger_count"]
        or result["book_count"] != freeze["book_count"]
        or result["analysis_mode"] != plan["analysis_mode"]
        or result["eligibility_class"] != plan["eligibility_class"]
        or result["inference_claims_allowed"]
        != plan["inference_claims_allowed"]
    ):
        _fail("selector audit differs from its plan or published book freeze")
    selected_union = {
        str(lineup_id)
        for book in freeze["books"]
        for lineup_id in book["selected_lineup_ids"]
    }
    exact_union = [
        lineup_id for lineup_id in freeze["candidate_lineup_ids"]
        if lineup_id in selected_union
    ]
    if result["audit_union_lineup_ids"] != exact_union:
        _fail("selector audit union differs from the exact frozen-book union")
    if len(result["books"]) != len(freeze["books"]):
        _fail("selector audit book ledger differs from the published freeze")
    for audit_book, selection_book in zip(
        result["books"], freeze["books"], strict=True
    ):
        if any(
            audit_book[field] != selection_book[field]
            for field in (
                "strategy_family",
                "strategy_id",
                "strategy_sha256",
                "executable_fingerprint_sha256",
            )
        ) or audit_book["selection_book_sha256"] != selection_book[
            "selection_book_sha256"
        ]:
            _fail("selector audit book differs from the published freeze")
    return plan, plan_identity, freeze_authority


def validate_selector_audit_result_authority_v1(
    value: object,
    *,
    book_freeze_authority: Mapping[str, object],
    independent_bank_plan: Mapping[str, object],
    independent_bank_plan_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Validate a published audit plus its deterministic-replay attestation."""
    authority = _mapping(value, label="selector audit result authority")
    _keys(authority, {
        "schema_version",
        "selector_audit_result",
        "selector_audit_publication_identity",
        "selector_audit_sha256",
        "book_freeze_authority_sha256",
        "book_freeze_publication_identity",
        "independent_bank_plan_sha256",
        "independent_bank_plan_identity",
        "candidate_authority_identity",
        "candidate_authority_sha256",
        "audit_member_sha256",
        "publication_mode",
        "selector_audit_result_authority_sha256",
    }, label="selector audit result authority")
    assert_outcome_free_v1(authority, label="selector audit result authority")
    try:
        validate_self_hash_v1(
            authority,
            field="selector_audit_result_authority_sha256",
            label="selector audit result authority",
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    result = validate_selector_audit_result_v1(
        authority["selector_audit_result"]
    )
    plan, plan_identity, freeze_authority = (
        _validate_selector_audit_plan_binding_v1(
            result,
            book_freeze_authority=book_freeze_authority,
            independent_bank_plan=independent_bank_plan,
            independent_bank_plan_identity=independent_bank_plan_identity,
            read_exact=read_exact,
        )
    )
    publication_identity = _exact_body_identity_v1(
        result,
        authority["selector_audit_publication_identity"],
        read_exact=read_exact,
        label="published selector audit result",
    )
    if (
        authority["schema_version"] != AUDIT_RESULT_AUTHORITY_SCHEMA
        or authority["selector_audit_publication_identity"]
        != publication_identity
        or authority["selector_audit_sha256"]
        != result["selector_audit_sha256"]
        or authority["book_freeze_authority_sha256"]
        != freeze_authority["book_freeze_authority_sha256"]
        or authority["book_freeze_publication_identity"]
        != freeze_authority["book_freeze_publication_identity"]
        or authority["independent_bank_plan_sha256"]
        != plan["independent_bank_plan_sha256"]
        or authority["independent_bank_plan_identity"] != plan_identity
        or authority["candidate_authority_identity"]
        != plan["candidate_authority_identity"]
        or authority["candidate_authority_sha256"]
        != plan["candidate_authority_sha256"]
        or authority["audit_member_sha256"]
        != result["audit_member"]["draw_bank_member_sha256"]
        or authority["publication_mode"]
        != "create-once-generation-pinned-exact-reopen"
    ):
        _fail("selector audit result authority differs")
    return authority


def authoritative_replay_selector_audit_v1(
    value: object,
    *,
    players: Sequence[rw.PlayerSpec],
    player_draws: np.ndarray,
    book_freeze_authority: Mapping[str, object],
    independent_bank_plan: Mapping[str, object],
    independent_bank_plan_identity: Mapping[str, object],
    publication_uri: str,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Rebuild, byte-compare, and attest one published selector audit."""
    retained = validate_selector_audit_result_v1(value)
    plan, plan_identity, freeze_authority = (
        _validate_selector_audit_plan_binding_v1(
            retained,
            book_freeze_authority=book_freeze_authority,
            independent_bank_plan=independent_bank_plan,
            independent_bank_plan_identity=independent_bank_plan_identity,
            read_exact=read_exact,
        )
    )
    rebuilt = evaluate_books_on_audit_player_draws_v1(
        audit_member=retained["audit_member"],
        players=players,
        player_draws=player_draws,
        book_freeze_authority=freeze_authority,
        independent_bank_plan=plan,
        independent_bank_plan_identity=plan_identity,
        read_exact=read_exact,
    )
    if canonical_json_bytes_v1(retained) != canonical_json_bytes_v1(rebuilt):
        _fail("selector audit authoritative replay differs")
    try:
        published_identity = publish_body_create_once_v1(
            rebuilt,
            uri=publication_uri,
            publish_create_once=publish_create_once,
            read_exact=read_exact,
            label="selector audit result",
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc
    body = {
        "schema_version": AUDIT_RESULT_AUTHORITY_SCHEMA,
        "selector_audit_result": rebuilt,
        "selector_audit_publication_identity": published_identity,
        "selector_audit_sha256": rebuilt["selector_audit_sha256"],
        "book_freeze_authority_sha256": freeze_authority[
            "book_freeze_authority_sha256"
        ],
        "book_freeze_publication_identity": freeze_authority[
            "book_freeze_publication_identity"
        ],
        "independent_bank_plan_sha256": plan[
            "independent_bank_plan_sha256"
        ],
        "independent_bank_plan_identity": plan_identity,
        "candidate_authority_identity": plan["candidate_authority_identity"],
        "candidate_authority_sha256": plan["candidate_authority_sha256"],
        "audit_member_sha256": rebuilt["audit_member"][
            "draw_bank_member_sha256"
        ],
        "publication_mode": "create-once-generation-pinned-exact-reopen",
    }
    authority = add_self_hash_v1(
        body, field="selector_audit_result_authority_sha256"
    )
    return validate_selector_audit_result_authority_v1(
        authority,
        book_freeze_authority=freeze_authority,
        independent_bank_plan=plan,
        independent_bank_plan_identity=plan_identity,
        read_exact=read_exact,
    )


def summarize_repeat_selection_v1(
    *,
    book_freeze_authorities: Sequence[Mapping[str, object]],
    independent_bank_plan: Mapping[str, object],
    independent_bank_plan_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Summarize only published, authoritatively replayed selection freezes."""
    plan, plan_identity = _validated_exact_plan_v1(
        independent_bank_plan,
        independent_bank_plan_identity,
        read_exact=read_exact,
    )
    authorities = [
        validate_book_freeze_authority_v1(
            value,
            independent_bank_plan=plan,
            independent_bank_plan_identity=plan_identity,
            read_exact=read_exact,
        )
        for value in _sequence(
            book_freeze_authorities, label="book freeze authorities"
        )
    ]
    freezes = [authority["book_freeze"] for authority in authorities]
    if len(freezes) < 2:
        _fail("repeat-selection summary requires at least two freezes")
    reference = freezes[0]
    member_hashes = [
        str(freeze["selection_member"]["draw_bank_member_sha256"])
        for freeze in freezes
    ]
    if member_hashes != plan["selection_bank_root"]["ordered_member_sha256s"]:
        _fail("repeat-selection freezes must consume the exact selection grid")
    publication_identities = [
        content_identity(authority["book_freeze_publication_identity"])
        for authority in authorities
    ]
    authority_hashes = [
        str(authority["book_freeze_authority_sha256"])
        for authority in authorities
    ]
    if (
        len(publication_identities) != len(set(publication_identities))
        or len(authority_hashes) != len(set(authority_hashes))
    ):
        _fail("repeat-selection publication authority repeats")
    for freeze in freezes[1:]:
        if (
            freeze["slate_id"] != reference["slate_id"]
            or freeze["law_id"] != reference["law_id"]
            or freeze["candidate_lineup_ids_sha256"]
            != reference["candidate_lineup_ids_sha256"]
            or freeze["candidate_rosters_sha256"]
            != reference["candidate_rosters_sha256"]
            or freeze["independent_bank_plan_sha256"]
            != plan["independent_bank_plan_sha256"]
            or freeze["independent_bank_plan_identity"] != plan_identity
            or freeze["candidate_authority_identity"]
            != plan["candidate_authority_identity"]
            or freeze["control_registry"] != reference["control_registry"]
            or freeze["challengers"] != reference["challengers"]
        ):
            _fail("repeat-selection freeze authority differs")
    strategy_ids = [str(book["strategy_id"]) for book in reference["books"]]
    summaries = []
    for strategy_id in strategy_ids:
        memberships: list[tuple[str, ...]] = []
        ordered: list[tuple[str, ...]] = []
        for freeze in freezes:
            matches = [
                book for book in freeze["books"] if book["strategy_id"] == strategy_id
            ]
            if len(matches) != 1:
                _fail("repeat-selection strategy book differs")
            selected = tuple(str(value) for value in matches[0]["selected_lineup_ids"])
            ordered.append(selected)
            memberships.append(tuple(sorted(selected)))
        pairwise = []
        for left in range(len(memberships)):
            for right in range(left + 1, len(memberships)):
                overlap = len(set(memberships[left]) & set(memberships[right]))
                pairwise.append({
                    "left_replicate_id": freezes[left]["replicate_id"],
                    "right_replicate_id": freezes[right]["replicate_id"],
                    "overlap_count": overlap,
                    "departed_count": ENTRY_BUDGET - overlap,
                    "entered_count": ENTRY_BUDGET - overlap,
                    "jaccard": float(overlap / (2 * ENTRY_BUDGET - overlap)),
                })
        consecutive = []
        for index in range(1, len(memberships)):
            overlap = len(set(memberships[index - 1]) & set(memberships[index]))
            consecutive.append({
                "from_replicate_id": freezes[index - 1]["replicate_id"],
                "to_replicate_id": freezes[index]["replicate_id"],
                "overlap_count": overlap,
                "departed_count": ENTRY_BUDGET - overlap,
                "entered_count": ENTRY_BUDGET - overlap,
            })
        frequency = Counter(lineup_id for membership in memberships for lineup_id in membership)
        summaries.append({
            "strategy_id": strategy_id,
            "membership_sha256_by_replicate": [
                canonical_sha256_v1(list(membership)) for membership in memberships
            ],
            "ordered_book_sha256_by_replicate": [
                canonical_sha256_v1(list(values)) for values in ordered
            ],
            "unique_membership_count": len(set(memberships)),
            "pairwise_churn": pairwise,
            "consecutive_churn": consecutive,
            "selection_frequency": [
                {"lineup_id": lineup_id, "replicate_count": count}
                for lineup_id, count in sorted(
                    frequency.items(), key=lambda item: (-item[1], item[0])
                )
            ],
        })
    body = {
        "schema_version": REPEAT_SELECTION_SCHEMA,
        "slate_id": reference["slate_id"],
        "law_id": reference["law_id"],
        "replicate_ids": [freeze["replicate_id"] for freeze in freezes],
        "selection_member_sha256s": member_hashes,
        "book_freeze_publication_identities": [
            authority["book_freeze_publication_identity"]
            for authority in authorities
        ],
        "book_freeze_authority_sha256s": authority_hashes,
        "independent_bank_plan_sha256": plan["independent_bank_plan_sha256"],
        "independent_bank_plan_identity": plan_identity,
        "candidate_authority_identity": plan["candidate_authority_identity"],
        "candidate_authority_sha256": plan["candidate_authority_sha256"],
        "replicate_count": len(freezes),
        "candidate_lineup_ids_sha256": reference["candidate_lineup_ids_sha256"],
        "candidate_rosters_sha256": reference["candidate_rosters_sha256"],
        "strategy_count": len(strategy_ids),
        "strategies": summaries,
        "analysis_mode": "descriptive-fixed-ledger-no-inference-v1",
        "eligibility_class": "descriptive-only-no-promotion-authority",
        "inference_claims_allowed": False,
        "evidence_tier": "simulated-repeat-selection-only",
    }
    assert_outcome_free_v1(body, label="repeat-selection summary")
    return add_self_hash_v1(body, field="repeat_selection_sha256")


def validate_audit_result_crn_pair_v1(
    left_result: Mapping[str, object],
    right_result: Mapping[str, object],
    *,
    coupling_receipt: Mapping[str, object] | None = None,
) -> str:
    left = validate_selector_audit_result_v1(left_result)
    right = validate_selector_audit_result_v1(right_result)
    try:
        return validate_crn_pairing_v1(
            left["audit_member"],
            right["audit_member"],
            coupling_receipt=coupling_receipt,
        )
    except CorpusR6IndependentBankContractV1Error as exc:
        raise CorpusR6SelectorAuditV1Error(str(exc)) from exc


def summarize_fixed_audit_ledger_v1(
    *,
    independent_bank_plan: Mapping[str, object],
    independent_bank_plan_identity: Mapping[str, object],
    book_freeze_authorities: Sequence[Mapping[str, object]],
    audit_result_authorities: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Consume the plan-owned, published/replayed ledger with no early stop."""
    plan, plan_identity = _validated_exact_plan_v1(
        independent_bank_plan,
        independent_bank_plan_identity,
        read_exact=read_exact,
    )
    rule = plan["precision_rule"]
    freeze_authorities = [
        validate_book_freeze_authority_v1(
            value,
            independent_bank_plan=plan,
            independent_bank_plan_identity=plan_identity,
            read_exact=read_exact,
        )
        for value in _sequence(
            book_freeze_authorities, label="book freeze authorities"
        )
    ]
    freeze_by_authority_sha = {
        str(value["book_freeze_authority_sha256"]): value
        for value in freeze_authorities
    }
    if len(freeze_by_authority_sha) != len(freeze_authorities):
        _fail("fixed-ledger book-freeze authorities repeat")
    if len(freeze_authorities) != 1:
        _fail("v1 fixed ledger requires one equivalent book-freeze authority")
    audit_authorities: list[dict[str, object]] = []
    for raw in _sequence(
        audit_result_authorities, label="audit result authorities"
    ):
        untrusted = _mapping(raw, label="audit result authority")
        freeze_sha = _sha256(
            untrusted.get("book_freeze_authority_sha256"),
            label="book freeze authority sha256",
        )
        if freeze_sha not in freeze_by_authority_sha:
            _fail("audit result references an unprovided book-freeze authority")
        audit_authorities.append(
            validate_selector_audit_result_authority_v1(
                untrusted,
                book_freeze_authority=freeze_by_authority_sha[freeze_sha],
                independent_bank_plan=plan,
                independent_bank_plan_identity=plan_identity,
                read_exact=read_exact,
            )
        )
    results = [authority["selector_audit_result"] for authority in audit_authorities]
    observed_ledger = [
        str(result["audit_member"]["draw_bank_member_sha256"])
        for result in results
    ]
    if observed_ledger != rule["ordered_audit_member_sha256s"]:
        _fail("audit results do not consume the exact fixed ledger in order")
    consumed_freeze_authorities = {
        str(authority["book_freeze_authority_sha256"])
        for authority in audit_authorities
    }
    if consumed_freeze_authorities != set(freeze_by_authority_sha):
        _fail("fixed-ledger book-freeze authority set has missing or extra entries")
    audit_publication_identities = [
        content_identity(authority["selector_audit_publication_identity"])
        for authority in audit_authorities
    ]
    audit_authority_hashes = [
        str(authority["selector_audit_result_authority_sha256"])
        for authority in audit_authorities
    ]
    if (
        len(audit_publication_identities)
        != len(set(audit_publication_identities))
        or len(audit_authority_hashes) != len(set(audit_authority_hashes))
    ):
        _fail("fixed-ledger audit publication authority repeats")
    reference = results[0]
    if freeze_authorities[0]["book_freeze"]["freeze_role"] != "designated-audit-book":
        _fail("fixed ledger requires the ex-ante designated selection book")
    strategy_ids = [str(book["strategy_id"]) for book in reference["books"]]
    strategy_identities = [
        (
            str(book["strategy_id"]),
            str(book["strategy_sha256"]),
            str(book["executable_fingerprint_sha256"]),
        )
        for book in reference["books"]
    ]
    for result in results[1:]:
        if (
            result["slate_id"] != reference["slate_id"]
            or result["law_id"] != reference["law_id"]
            or result["audit_member"]["law_sha256"]
            != reference["audit_member"]["law_sha256"]
            or result["audit_member"]["player_ids_sha256"]
            != reference["audit_member"]["player_ids_sha256"]
            or result["audit_member"]["player_catalog_sha256"]
            != reference["audit_member"]["player_catalog_sha256"]
            or result["audit_member"]["generation_code_identity"]
            != reference["audit_member"]["generation_code_identity"]
            or result["book_freeze_authority_sha256"]
            != reference["book_freeze_authority_sha256"]
            or result["book_freeze_publication_identity"]
            != reference["book_freeze_publication_identity"]
            or result["candidate_rosters_sha256"]
            != reference["candidate_rosters_sha256"]
            or result["primary_control_id"] != reference["primary_control_id"]
            or result["primary_strategy_id"]
            != reference["primary_strategy_id"]
            or [str(book["strategy_id"]) for book in result["books"]]
            != strategy_ids
            or [
                (
                    str(book["strategy_id"]),
                    str(book["strategy_sha256"]),
                    str(book["executable_fingerprint_sha256"]),
                )
                for book in result["books"]
            ]
            != strategy_identities
            or result["independent_bank_plan_sha256"]
            != plan["independent_bank_plan_sha256"]
            or result["independent_bank_plan_identity"] != plan_identity
            or result["candidate_authority_identity"]
            != plan["candidate_authority_identity"]
        ):
            _fail("fixed-ledger audit authority differs across members")
    aggregate_books = []
    for strategy_id in strategy_ids:
        books = [
            next(book for book in result["books"] if book["strategy_id"] == strategy_id)
            for result in results
        ]
        world_count = sum(int(book["metrics"]["world_count"]) for book in books)
        threshold_counts = {
            metric_id: sum(
                int(next(
                    row["event_count"]
                    for row in book["metrics"]["thresholds"]
                    if row["metric_id"] == metric_id
                ))
                for book in books
            )
            for metric_id, _, _ in DEFAULT_THRESHOLDS
        }
        aggregate_books.append({
            "strategy_id": strategy_id,
            "strategy_sha256": str(books[0]["strategy_sha256"]),
            "executable_fingerprint_sha256": str(
                books[0]["executable_fingerprint_sha256"]
            ),
            "world_count": world_count,
            "expected_book_max": float(sum(
                float(book["metrics"]["expected_book_max"])
                * int(book["metrics"]["world_count"])
                for book in books
            ) / world_count),
            "maximum_book_score": max(
                float(book["metrics"]["maximum_book_score"]) for book in books
            ),
            "threshold_event_counts": [
                {"metric_id": metric_id, "event_count": threshold_counts[metric_id]}
                for metric_id, _, _ in DEFAULT_THRESHOLDS
            ],
        })
    aggregate_pairs = []
    for strategy_id in strategy_ids:
        pairs = [
            next(
                pair
                for pair in result["paired_comparisons"]
                if pair["compared_strategy_id"] == strategy_id
            )["paired_discordance"]
            for result in results
        ]
        world_count = sum(int(pair["world_count"]) for pair in pairs)
        rows = []
        for metric_id, threshold, operator in DEFAULT_THRESHOLDS:
            relevant = [
                next(row for row in pair["thresholds"] if row["metric_id"] == metric_id)
                for pair in pairs
            ]
            challenger_only = sum(int(row["challenger_only_count"]) for row in relevant)
            control_only = sum(int(row["control_only_count"]) for row in relevant)
            rows.append({
                "metric_id": metric_id,
                "threshold": threshold,
                "operator": operator,
                "both_count": sum(int(row["both_count"]) for row in relevant),
                "neither_count": sum(int(row["neither_count"]) for row in relevant),
                "challenger_only_count": challenger_only,
                "control_only_count": control_only,
                "paired_delta_rate": float(
                    (challenger_only - control_only) / world_count
                ),
            })
        aggregate_pairs.append({
            "primary_control_id": reference["primary_control_id"],
            "compared_strategy_id": strategy_id,
            "world_count": world_count,
            "mean_book_max_delta": float(sum(
                float(pair["mean_book_max_delta"]) * int(pair["world_count"])
                for pair in pairs
            ) / world_count),
            "thresholds": rows,
        })
    primary_comparisons = [
        row for row in aggregate_pairs
        if row["compared_strategy_id"] == plan["primary_strategy_id"]
    ]
    if len(primary_comparisons) != 1:
        _fail("fixed ledger does not resolve the plan-owned primary strategy")
    primary_comparison = primary_comparisons[0]
    primary_metric_rows = [
        row for row in primary_comparison["thresholds"]
        if row["metric_id"] == rule["primary_metric"]["metric_id"]
    ]
    if len(primary_metric_rows) != 1:
        _fail("fixed ledger does not resolve the plan-owned primary metric")
    body = {
        "schema_version": FIXED_LEDGER_SCHEMA,
        "slate_id": reference["slate_id"],
        "law_id": reference["law_id"],
        "law_sha256": reference["audit_member"]["law_sha256"],
        "independent_bank_plan_sha256": plan["independent_bank_plan_sha256"],
        "independent_bank_plan_identity": plan_identity,
        "candidate_authority_identity": plan["candidate_authority_identity"],
        "candidate_authority_sha256": plan["candidate_authority_sha256"],
        "precision_rule_sha256": rule["precision_rule_sha256"],
        "stopping_law": rule["stopping_law"],
        "ordered_audit_member_sha256s": observed_ledger,
        "audit_result_publication_identities": [
            authority["selector_audit_publication_identity"]
            for authority in audit_authorities
        ],
        "audit_result_authority_sha256s": audit_authority_hashes,
        "book_freeze_authority_sha256s": [
            authority["book_freeze_authority_sha256"]
            for authority in freeze_authorities
        ],
        "fixed_member_count": rule["fixed_member_count"],
        "consumed_member_count": len(results),
        "fixed_ledger_exhausted": True,
        "stop_reason": "fixed-ledger-exhausted",
        "primary_metric": rule["primary_metric"],
        "primary_control_id": plan["primary_control_id"],
        "primary_strategy_id": plan["primary_strategy_id"],
        "primary_comparison": primary_comparison,
        "primary_metric_result": primary_metric_rows[0],
        "analysis_mode": rule["analysis_mode"],
        "uncertainty_estimator": rule["uncertainty_estimator"],
        "family_rule": rule["family_rule"],
        "eligibility_class": rule["eligibility_class"],
        "inference_claims_allowed": False,
        "books": aggregate_books,
        "paired_comparisons": aggregate_pairs,
        "evidence_tier": "simulated-fixed-ledger-summary-only",
    }
    assert_outcome_free_v1(body, label="fixed-ledger audit summary")
    return add_self_hash_v1(body, field="fixed_ledger_summary_sha256")
