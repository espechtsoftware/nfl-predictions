"""Direct no-rescore realized grading for current-bank selector successors.

The grouped and rank-150/DPP selectors publish a successor-native terminal
aggregate.  They do not publish the crossed-screen control receipt schema and
must never be relabelled as that control.  This module follows their own
authority graph instead:

``terminal -> evaluation -> projection bundle -> selection result``

Only after all 54 chains, finalist books, and terminal aggregate hashes have
been exact-reopened and replayed may the supplied full-union attribution
release be opened.  Realized scores are projected from its already-persisted
``realized_score_micro`` rows.  A slate-wide roster cache scores each distinct
selected roster once even when it appears in several folds or finalist books.

The result retains the common ``(source ordinal, slate, fold)`` lattice for
paired comparison.  It reports exact mean weekly maxima and inclusive
200/210/220/230 hit-week counts; it does not choose a winner, refit a selector,
query an outcome source, or grant promotion authority.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_realized_score_authority_adapter_v1 as score_authority,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_cloud_v1 as selection_cloud,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_evaluation_v1 as evaluation,
)


BRIDGE_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-realized-bridge/v1"
)
TERMINAL_BOOK_PROOF_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-terminal-book-proof/v1"
)
ROSTER_SCORE_ROW_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-realized-roster-row/v1"
)
BOOK_WEEK_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-realized-book-week/v1"
)
FOLD_PATH_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-realized-fold-path/v1"
)
FINALIST_RESULT_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-realized-finalist/v1"
)
PUBLICATION_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-realized-publication-envelope/v1"
)
CLOUD_ENTRYPOINT_REGISTRATION_SCHEMA: Final = (
    "corpus-r6-current-bank-selector-successor-realized-cloud-entrypoint/v1"
)
MODE_ONE_SLATE_SMOKE: Final = "one-slate-smoke"
MODE_FULL_PANEL: Final = "full-54"
SMOKE_SOURCE_ORDINAL: Final = 0
PANEL_SLATE_COUNT: Final = contract.PANEL_SLATE_COUNT
FOLD_COUNT: Final = contract.FOLDS_PER_SLATE
THRESHOLDS_DK: Final = (200, 210, 220, 230)
MICRO_DK_PER_POINT: Final = score_authority.MICRO_DK_PER_POINT

MAXIMUM_TERMINAL_BYTES: Final = 256_000_000
MAXIMUM_EVALUATION_BYTES: Final = 256_000_000
MAXIMUM_PROJECTION_BYTES: Final = 256_000_000
MAXIMUM_SELECTION_BYTES: Final = max(
    selection_cloud.MAXIMUM_SLATE_RESULT_BYTES,
    selection_cloud.MAXIMUM_RANK150_DPP_SLATE_RESULT_BYTES,
)
MAXIMUM_ATTRIBUTION_ROOT_BYTES: Final = 4_000_000
MAXIMUM_ATTRIBUTION_SHARD_BYTES: Final = 512_000_000
MAXIMUM_REPORT_BYTES: Final = 512_000_000

ENTRYPOINT_RELATIVE_PATH: Final = (
    "scripts/run_corpus_r6_current_bank_selector_successor_realized_bridge_v1.py"
)
ENTRYPOINT_IMAGE_PATH: Final = f"/app/{ENTRYPOINT_RELATIVE_PATH}"
ENTRYPOINT_COMMAND: Final = (
    "/usr/local/bin/python3.11",
    "-I",
    ENTRYPOINT_IMAGE_PATH,
    "publish",
)
OUTPUT_FILENAME: Final = "selector-successor-realized-bridge.json"

ReadExact = Callable[[Mapping[str, object]], bytes]
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(ValueError):
    """The successor-native terminal-first realized bridge failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(message)


def canonical_json_bytes_v1(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
            str(exc)
        ) from exc


def canonical_sha256_v1(value: object) -> str:
    return sha256(canonical_json_bytes_v1(value)).hexdigest()


def cloud_entrypoint_registration_v1() -> dict[str, object]:
    """Register the one fixed publish command packaged by the challenger image."""
    return _with_hash({
        "schema_version": CLOUD_ENTRYPOINT_REGISTRATION_SCHEMA,
        "process_role": "selector-successor-realized-bridge-publisher",
        "entrypoint_relative_path": ENTRYPOINT_RELATIVE_PATH,
        "entrypoint_image_path": ENTRYPOINT_IMAGE_PATH,
        "command": list(ENTRYPOINT_COMMAND),
        "publication_mode": "create-once-exact-reopen",
        "maximum_report_bytes": MAXIMUM_REPORT_BYTES,
        "outcome_source_query_performed": False,
        "lineup_rescore_performed": False,
        "graph_mutation_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
    }, field="cloud_entrypoint_registration_sha256")


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
            str(exc)
        ) from exc


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
    return value


def _signed_integer(value: object, *, label: str) -> int:
    if type(value) is not int:
        _fail(f"{label} must be one exact integer")
    return value


def _fraction(numerator: int, denominator: int) -> dict[str, int]:
    if denominator < 1:
        _fail("fraction denominator must be positive")
    return {"numerator": numerator, "denominator": denominator}


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    body[field] = canonical_sha256_v1(body)
    return body


def build_publication_envelope_v1(
    *, report: object, report_identity: object,
) -> dict[str, object]:
    """Bind a completed bridge report to its create-once object identity."""
    retained = _mapping(report, label="successor realized bridge report")
    if (
        retained.get("schema_version") != BRIDGE_SCHEMA
        or retained.get("mode") not in {MODE_ONE_SLATE_SMOKE, MODE_FULL_PANEL}
        or retained.get("realized_bridge_sha256")
        != canonical_sha256_v1({
            key: value
            for key, value in retained.items()
            if key != "realized_bridge_sha256"
        })
    ):
        _fail("successor realized bridge report self hash differs")
    identity = _identity(
        report_identity, label="successor realized bridge report identity"
    )
    raw = canonical_json_bytes_v1(retained)
    if (
        identity["sha256"] != sha256(raw).hexdigest()
        or identity["bytes"] != len(raw)
        or not str(identity["uri"]).startswith(contract.OUTPUT_NAMESPACE)
        or not str(identity["uri"]).endswith(f"/{OUTPUT_FILENAME}")
    ):
        _fail("successor realized bridge publication identity differs")
    return _with_hash({
        "schema_version": PUBLICATION_ENVELOPE_SCHEMA,
        "mode": retained["mode"],
        "realized_bridge_identity": identity,
        "realized_bridge_sha256": retained["realized_bridge_sha256"],
        "terminal_aggregate_identity": retained["terminal_aggregate_identity"],
        "outcome_authority_identity": retained["outcome_authority_identity"],
        "scored_slate_count": retained["scored_slate_count"],
        "finalist_count": retained["finalist_count"],
        "publication_mode": "create-once-exact-reopen",
        "lineup_rescore_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
    }, field="publication_envelope_sha256")


def _open_json_v1(
    identity_value: object,
    *,
    read_exact: ReadExact,
    maximum_bytes: int,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    if int(identity["bytes"]) > maximum_bytes:
        _fail(f"{label} identity exceeds its byte ceiling before read")
    if not callable(read_exact):
        _fail(f"{label} exact reader must be callable")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact bytes differ from identity")
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
            str(exc)
        ) from exc
    return _mapping(value, label=label), identity


def _require_canonical_replay(
    opened: Mapping[str, object], validated: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    if canonical_json_bytes_v1(opened) != canonical_json_bytes_v1(validated):
        _fail(f"{label} validator replay differs from opened bytes")
    return dict(validated)


def _native_fold_receipt_hash(receipt: Mapping[str, object]) -> str:
    # The evaluator owns the schema dispatch between grouped and rank/DPP
    # receipts.  Reusing it avoids inventing a third compatibility schema.
    try:
        return evaluation._selection_fold_receipt_sha256_v1(receipt)
    except evaluation.CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
            str(exc)
        ) from exc


def _cell_selector_coordinate(cell: Mapping[str, object]) -> dict[str, object]:
    try:
        return evaluation._selector_coordinate_v1(cell)
    except evaluation.CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
            str(exc)
        ) from exc


def _validate_selection_for_projection(
    value: object, *, projection_bundle: Mapping[str, object],
) -> dict[str, object]:
    try:
        return evaluation._validate_selection_slate_result_v1(
            value, projection_bundle=projection_bundle
        )
    except evaluation.CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
            str(exc)
        ) from exc


def _validate_fold_receipt(
    value: object,
    *,
    source_ordinal: int,
    fold_ordinal: int,
    projection: Mapping[str, object],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    try:
        return evaluation._validate_fold_receipt_v1(
            value,
            source_ordinal=source_ordinal,
            fold_ordinal=fold_ordinal,
            projection=projection,
        )
    except evaluation.CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
            str(exc)
        ) from exc


def _book_from_cell_v1(
    *,
    source_ordinal: int,
    slate_id: str,
    fold_ordinal: int,
    finalist: Mapping[str, object],
    cell: Mapping[str, object],
    projection: Mapping[str, object],
    selection: Mapping[str, object],
    selection_identity: Mapping[str, object],
    fold_receipt: Mapping[str, object],
    evaluation_result: Mapping[str, object],
    evaluation_identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, tuple[str, ...]], str, str]:
    entry_budget = _integer(
        finalist.get("entry_budget"), label="successor finalist entry budget"
    )
    if entry_budget not in evaluation.FINALIST_ENTRY_BUDGETS:
        _fail("successor finalist entry budget is not 80/100/150")
    selected_all = [
        str(value)
        for value in _sequence(
            cell.get("selected_lineup_ids"), label="successor selected lineup IDs"
        )
    ]
    selected_ids = selected_all[:entry_budget]
    prefixes = [
        _mapping(row, label="successor selection prefix")
        for row in _sequence(cell.get("prefixes"), label="successor prefixes")
    ]
    matching_prefixes = [
        row for row in prefixes if row.get("prefix_size") == entry_budget
    ]
    if len(selected_ids) != entry_budget or len(matching_prefixes) != 1:
        _fail("successor finalist book lacks its exact entry-budget prefix")
    prefix = matching_prefixes[0]
    if prefix.get("selected_lineup_ids_sha256") != canonical_sha256_v1(selected_ids):
        _fail("successor finalist selected lineup prefix differs")

    candidates = [
        _mapping(row, label="successor projection candidate")
        for row in _sequence(
            projection.get("candidates"), label="successor projection candidates"
        )
    ]
    candidate_by_id = {str(row.get("lineup_id")): row for row in candidates}
    if len(candidate_by_id) != len(candidates) or not set(selected_ids) <= set(
        candidate_by_id
    ):
        _fail("successor finalist lineup is outside its exact projection")
    roster_by_id = {
        lineup_id: tuple(
            str(player_id)
            for player_id in _sequence(
                candidate_by_id[lineup_id].get("roster_player_ids"),
                label="successor candidate roster",
            )
        )
        for lineup_id in selected_ids
    }
    selected_rosters = [list(roster_by_id[lineup_id]) for lineup_id in selected_ids]
    if prefix.get("selected_rosters_sha256") != canonical_sha256_v1(selected_rosters):
        _fail("successor finalist selected roster prefix differs")

    selector_hash = str(finalist["selector_coordinate_sha256"])
    evaluation_rows = [
        _mapping(row, label="successor finalist evaluation row")
        for row in _sequence(
            evaluation_result["folds"][fold_ordinal]["book_metric_rows"],
            label="successor evaluation rows",
        )
        if isinstance(row, Mapping)
        and row.get("view_id") == finalist.get("view_id")
        and row.get("selector_coordinate_sha256") == selector_hash
        and row.get("entry_budget") == entry_budget
    ]
    if len(evaluation_rows) != 1:
        _fail("successor finalist evaluation row is missing or repeated")
    metric_row = evaluation_rows[0]
    selection_cell_hash = _digest(
        cell.get("authority_cell_sha256"), label="successor selection cell"
    )
    if (
        metric_row.get("selection_cell_sha256") != selection_cell_hash
        or metric_row.get("book_payload_sha256")
        != prefix.get("prefix_payload_sha256")
        or metric_row.get("selected_lineup_ids_sha256")
        != prefix.get("selected_lineup_ids_sha256")
        or metric_row.get("selected_rosters_sha256")
        != prefix.get("selected_rosters_sha256")
    ):
        _fail("successor finalist evaluation row differs from selected book")
    pairing_hash = _digest(
        metric_row.get("pairing_coordinate_sha256"),
        label="successor finalist pairing coordinate",
    )
    metric_row_hash = _digest(
        metric_row.get("book_metric_row_sha256"),
        label="successor finalist book metric row",
    )
    proof = _with_hash({
        "schema_version": TERMINAL_BOOK_PROOF_SCHEMA,
        "source_ordinal": source_ordinal,
        "slate_id": slate_id,
        "fold_ordinal": fold_ordinal,
        "heldout_block": contract.WORLD_BLOCKS[fold_ordinal],
        "view_id": finalist["view_id"],
        "selector_coordinate_sha256": selector_hash,
        "entry_budget": entry_budget,
        "selection_slate_result_identity": dict(selection_identity),
        "selection_slate_result_sha256": selection["slate_result_sha256"],
        "selection_fold_receipt_sha256": _native_fold_receipt_hash(fold_receipt),
        "selection_cell_sha256": selection_cell_hash,
        "selected_lineup_ids": selected_ids,
        "selected_lineup_ids_sha256": prefix["selected_lineup_ids_sha256"],
        "selected_rosters_sha256": prefix["selected_rosters_sha256"],
        "book_payload_sha256": prefix["prefix_payload_sha256"],
        "evaluation_result_identity": dict(evaluation_identity),
        "evaluation_result_sha256": evaluation_result[
            "evaluation_result_sha256"
        ],
        "book_metric_row_sha256": metric_row_hash,
        "pairing_coordinate_sha256": pairing_hash,
    }, field="terminal_book_proof_sha256")
    return proof, roster_by_id, metric_row_hash, pairing_hash


def reopen_successor_terminal_books_v1(
    *, terminal_aggregate_identity: object, read_terminal_exact: ReadExact,
) -> dict[str, object]:
    """Exact-reopen all native successor books before any outcome capability."""
    root_body, root_identity = _open_json_v1(
        terminal_aggregate_identity,
        read_exact=read_terminal_exact,
        maximum_bytes=MAXIMUM_TERMINAL_BYTES,
        label="successor terminal aggregate",
    )
    try:
        root = evaluation.validate_terminal_aggregate_v1(root_body)
    except evaluation.CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
            str(exc)
        ) from exc
    root = _require_canonical_replay(root_body, root, label="successor terminal")
    if root.get("terminal_before_realized_outcome_read") is not True:
        _fail("successor terminal is not frozen before realized outcome read")

    predecessors = [
        _mapping(row, label=f"successor terminal predecessor[{index}]")
        for index, row in enumerate(
            _sequence(root.get("predecessors"), label="successor predecessors")
        )
    ]
    if (
        len(predecessors) != PANEL_SLATE_COUNT
        or [row.get("source_ordinal") for row in predecessors]
        != list(range(PANEL_SLATE_COUNT))
    ):
        _fail("successor terminal predecessor slate lattice differs")

    finalists = [
        _mapping(row, label=f"successor finalist[{index}]")
        for index, row in enumerate(
            _sequence(root.get("finalists"), label="successor finalists")
        )
    ]
    aggregate_rows = {
        str(row["aggregate_metric_row_sha256"]): row
        for row in [
            _mapping(value, label="successor aggregate metric row")
            for value in _sequence(
                root.get("aggregate_metric_rows"),
                label="successor aggregate metric rows",
            )
        ]
    }
    finalist_states: list[dict[str, object]] = []
    for finalist in finalists:
        aggregate_hash = str(finalist.get("aggregate_metric_row_sha256"))
        aggregate = aggregate_rows.get(aggregate_hash)
        if aggregate is None or (
            aggregate.get("view_id") != finalist.get("view_id")
            or aggregate.get("selector_coordinate_sha256")
            != finalist.get("selector_coordinate_sha256")
            or aggregate.get("entry_budget") != finalist.get("entry_budget")
        ):
            _fail("successor finalist differs from terminal aggregate row")
        finalist_states.append({
            "finalist": finalist,
            "aggregate": aggregate,
            "books": [],
            "book_metric_row_sha256s": [],
            "pairing_coordinate_sha256s": [],
        })

    slate_ids: list[str] = []
    roster_by_source: dict[int, dict[str, tuple[str, ...]]] = {}
    exact_open_count = 1
    for source, predecessor in enumerate(predecessors):
        if set(predecessor) != {
            "source_ordinal", "slate_id", "evaluation_identity",
            "evaluation_result_sha256", "selection_slate_result_identity",
        }:
            _fail("successor terminal predecessor fields differ")
        slate_id = predecessor.get("slate_id")
        if type(slate_id) is not str or not slate_id:
            _fail("successor terminal slate ID differs")
        slate_ids.append(slate_id)

        evaluation_body, evaluation_identity = _open_json_v1(
            predecessor["evaluation_identity"],
            read_exact=read_terminal_exact,
            maximum_bytes=MAXIMUM_EVALUATION_BYTES,
            label=f"successor evaluation[{source}]",
        )
        exact_open_count += 1
        try:
            evaluation_result = evaluation.validate_evaluation_result_v1(
                evaluation_body
            )
        except evaluation.CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error as exc:
            raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
                str(exc)
            ) from exc
        evaluation_result = _require_canonical_replay(
            evaluation_body,
            evaluation_result,
            label=f"successor evaluation[{source}]",
        )
        if (
            evaluation_result.get("source_ordinal") != source
            or evaluation_result.get("slate_id") != slate_id
            or predecessor.get("evaluation_result_sha256")
            != evaluation_result.get("evaluation_result_sha256")
            or predecessor.get("selection_slate_result_identity")
            != evaluation_result.get("selection_slate_result_identity")
        ):
            _fail("successor terminal/evaluation predecessor binding differs")

        projection_body, projection_identity = _open_json_v1(
            evaluation_result["projection_bundle_identity"],
            read_exact=read_terminal_exact,
            maximum_bytes=MAXIMUM_PROJECTION_BYTES,
            label=f"successor projection bundle[{source}]",
        )
        exact_open_count += 1
        try:
            projection_bundle = contract.validate_projection_bundle_v1(
                projection_body
            )
        except contract.CorpusR6CurrentBankCrossedScreenContractV1Error as exc:
            raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
                str(exc)
            ) from exc
        projection_bundle = _require_canonical_replay(
            projection_body,
            projection_bundle,
            label=f"successor projection bundle[{source}]",
        )
        if (
            projection_bundle.get("source_ordinal") != source
            or projection_bundle.get("slate_id") != slate_id
            or projection_bundle.get("projection_bundle_sha256")
            != evaluation_result.get("projection_bundle_sha256")
            or projection_bundle.get("panel_identity") != contract.PANEL_IDENTITY
            or projection_bundle.get("panel_self_sha256")
            != contract.PANEL_SELF_SHA256
        ):
            _fail("successor evaluation/projection/panel binding differs")

        selection_body, selection_identity = _open_json_v1(
            evaluation_result["selection_slate_result_identity"],
            read_exact=read_terminal_exact,
            maximum_bytes=MAXIMUM_SELECTION_BYTES,
            label=f"successor selection result[{source}]",
        )
        exact_open_count += 1
        selection = _validate_selection_for_projection(
            selection_body, projection_bundle=projection_bundle
        )
        selection = _require_canonical_replay(
            selection_body,
            selection,
            label=f"successor selection result[{source}]",
        )
        if (
            selection.get("source_ordinal") != source
            or selection.get("slate_id") != slate_id
            or selection.get("slate_result_sha256")
            != evaluation_result.get("selection_slate_result_sha256")
            or selection_identity
            != _identity(
                predecessor["selection_slate_result_identity"],
                label="successor predecessor selection identity",
            )
        ):
            _fail("successor evaluation/selection binding differs")

        selected_rosters: dict[str, tuple[str, ...]] = {}
        for fold_ordinal in range(FOLD_COUNT):
            projection = _mapping(
                projection_bundle["fold_projections"][fold_ordinal],
                label="successor fold projection",
            )
            fold_receipt, cells = _validate_fold_receipt(
                selection["fold_receipts"][fold_ordinal],
                source_ordinal=source,
                fold_ordinal=fold_ordinal,
                projection=projection,
            )
            cell_by_coordinate: dict[tuple[str, str], dict[str, object]] = {}
            for cell in cells:
                coordinate = _cell_selector_coordinate(cell)
                key = (
                    str(cell.get("view_id")),
                    str(coordinate["selector_coordinate_sha256"]),
                )
                if key in cell_by_coordinate:
                    _fail("successor selection coordinate repeats within a fold")
                cell_by_coordinate[key] = cell
            for state in finalist_states:
                finalist = state["finalist"]
                key = (
                    str(finalist["view_id"]),
                    str(finalist["selector_coordinate_sha256"]),
                )
                if key not in cell_by_coordinate:
                    _fail("successor finalist is absent from selected fold")
                proof, rosters, metric_hash, pairing_hash = _book_from_cell_v1(
                    source_ordinal=source,
                    slate_id=slate_id,
                    fold_ordinal=fold_ordinal,
                    finalist=finalist,
                    cell=cell_by_coordinate[key],
                    projection=projection,
                    selection=selection,
                    selection_identity=selection_identity,
                    fold_receipt=fold_receipt,
                    evaluation_result=evaluation_result,
                    evaluation_identity=evaluation_identity,
                )
                state["books"].append(proof)
                state["book_metric_row_sha256s"].append(metric_hash)
                state["pairing_coordinate_sha256s"].append(pairing_hash)
                for lineup_id, roster in rosters.items():
                    prior = selected_rosters.setdefault(lineup_id, roster)
                    if prior != roster:
                        _fail("successor lineup ID aliases distinct fold rosters")
        roster_by_source[source] = selected_rosters

    if len(set(slate_ids)) != PANEL_SLATE_COUNT:
        _fail("successor terminal slate IDs repeat")
    expected_book_count = PANEL_SLATE_COUNT * FOLD_COUNT
    finalist_proofs: list[dict[str, object]] = []
    common_pairing_lattice: list[tuple[int, str, int, str]] | None = None
    for state in finalist_states:
        books = list(state["books"])
        aggregate = state["aggregate"]
        if (
            len(books) != expected_book_count
            or aggregate.get("complete_cell_count") != expected_book_count
            or aggregate.get("book_metric_row_sha256s_sha256")
            != canonical_sha256_v1(sorted(state["book_metric_row_sha256s"]))
            or aggregate.get("pairing_coordinate_sha256s_sha256")
            != canonical_sha256_v1(sorted(state["pairing_coordinate_sha256s"]))
        ):
            _fail("successor terminal aggregate differs from reopened books")
        lattice = sorted(
            (
                int(book["source_ordinal"]),
                str(book["slate_id"]),
                int(book["fold_ordinal"]),
                str(book["heldout_block"]),
            )
            for book in books
        )
        if common_pairing_lattice is None:
            common_pairing_lattice = lattice
        elif lattice != common_pairing_lattice:
            _fail("successor finalists do not share one paired book-week lattice")
        finalist_proofs.append({
            "finalist": state["finalist"],
            "aggregate_metric_row_sha256": aggregate[
                "aggregate_metric_row_sha256"
            ],
            "books": books,
            "books_sha256": canonical_sha256_v1(books),
        })
    if common_pairing_lattice is None:
        _fail("successor terminal contains no realized-eligible finalist")
    proof = {
        "terminal_aggregate": root,
        "terminal_aggregate_identity": root_identity,
        "terminal_aggregate_sha256": root["terminal_aggregate_sha256"],
        "slate_ids": slate_ids,
        "finalist_proofs": finalist_proofs,
        "roster_by_source": roster_by_source,
        "paired_book_week_lattice": common_pairing_lattice,
        "paired_book_week_lattice_sha256": canonical_sha256_v1(
            common_pairing_lattice
        ),
        "terminal_exact_open_count": exact_open_count,
        "terminal_proof_complete": True,
        "outcome_capability_used": False,
    }
    return proof


def _bind_attribution_root_v1(
    value: object, *, identity: Mapping[str, object],
) -> dict[str, object]:
    try:
        root = score_authority.validate_attribution_release_score_authority_v1(
            value
        )
    except score_authority.CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
            str(exc)
        ) from exc
    if (
        root.get("target_uri") != identity["uri"]
        or canonical_sha256_v1(root) != identity["sha256"]
        or len(canonical_json_bytes_v1(root)) != identity["bytes"]
    ):
        _fail("successor attribution root differs from exact identity")
    return root


def _bind_attribution_shard_v1(
    value: object,
    *,
    identity: Mapping[str, object],
    descriptor: Mapping[str, object],
    source_ordinal: int,
    slate_id: str,
) -> dict[str, object]:
    try:
        shard = score_authority.validate_slate_score_row_authority_v1(value)
    except score_authority.CorpusR6CurrentBankRealizedScoreAuthorityAdapterV1Error as exc:
        raise CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error(
            str(exc)
        ) from exc
    if (
        descriptor.get("source_ordinal") != source_ordinal
        or descriptor.get("slate_id") != slate_id
        or descriptor.get("slate_attribution_identity") != identity
        or descriptor.get("slate_attribution_sha256")
        != shard.get("slate_attribution_sha256")
        or descriptor.get("lineup_count") != shard.get("lineup_count")
        or shard.get("source_ordinal") != source_ordinal
        or shard.get("slate_id") != slate_id
        or shard.get("panel_freeze_identity") != contract.PANEL_IDENTITY
        or canonical_sha256_v1(shard) != identity["sha256"]
        or len(canonical_json_bytes_v1(shard)) != identity["bytes"]
    ):
        _fail("successor attribution shard descriptor/slate binding differs")
    return shard


def _score_row_authority_v1(
    *,
    source_ordinal: int,
    slate_id: str,
    selected_rosters: Mapping[str, tuple[str, ...]],
    shard: Mapping[str, object],
    shard_identity: Mapping[str, object],
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    lineup_rows = [
        _mapping(row, label="persisted successor score row")
        for row in _sequence(shard.get("lineup_rows"), label="persisted lineup rows")
    ]
    by_id: dict[str, dict[str, object]] = {}
    for row in lineup_rows:
        lineup_id = row.get("lineup_id")
        if type(lineup_id) is not str or not lineup_id or lineup_id in by_id:
            _fail("persisted successor score row lineup IDs differ")
        by_id[lineup_id] = row
    missing = sorted(set(selected_rosters) - set(by_id))
    if missing:
        _fail("selected successor lineup is missing from no-rescore authority")

    aliases_by_roster: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for lineup_id, expected_roster in selected_rosters.items():
        row = by_id[lineup_id]
        actual_roster = tuple(
            str(value)
            for value in _sequence(
                row.get("roster_player_ids"), label="persisted lineup roster"
            )
        )
        if actual_roster != expected_roster:
            _fail("selected successor lineup roster differs from score authority")
        aliases_by_roster[actual_roster].append(row)

    roster_rows: list[dict[str, object]] = []
    authority_by_lineup: dict[str, dict[str, object]] = {}
    for roster in sorted(aliases_by_roster):
        source_rows = sorted(
            aliases_by_roster[roster], key=lambda row: str(row["lineup_id"])
        )
        scores = {
            _signed_integer(
                row.get("realized_score_micro"), label="persisted realized score"
            )
            for row in source_rows
        }
        if len(scores) != 1:
            _fail("one selected roster has conflicting persisted realized scores")
        lineup_ids = [str(row["lineup_id"]) for row in source_rows]
        source_row_hashes = [canonical_sha256_v1(row) for row in source_rows]
        body = _with_hash({
            "schema_version": ROSTER_SCORE_ROW_SCHEMA,
            "source_ordinal": source_ordinal,
            "slate_id": slate_id,
            "roster_player_ids": list(roster),
            "roster_identity_sha256": canonical_sha256_v1(list(roster)),
            "lineup_ids": lineup_ids,
            "lineup_ids_sha256": canonical_sha256_v1(lineup_ids),
            "persisted_lineup_row_sha256s": source_row_hashes,
            "persisted_lineup_row_sha256s_sha256": canonical_sha256_v1(
                source_row_hashes
            ),
            "realized_score_micro": next(iter(scores)),
            "slate_attribution_identity": dict(shard_identity),
            "slate_attribution_sha256": shard["slate_attribution_sha256"],
            "lineup_rows_sha256": shard["lineup_rows_sha256"],
        }, field="roster_score_row_sha256")
        roster_rows.append(body)
        for lineup_id in lineup_ids:
            authority_by_lineup[lineup_id] = body
    return roster_rows, authority_by_lineup


def _threshold_counts(maxima: Sequence[int]) -> dict[str, int]:
    return {
        str(threshold): sum(
            value >= threshold * MICRO_DK_PER_POINT for value in maxima
        )
        for threshold in THRESHOLDS_DK
    }


def _score_finalist_v1(
    *,
    proof: Mapping[str, object],
    scored_by_source: Mapping[int, Mapping[str, Mapping[str, object]]],
    source_ordinals: Sequence[int],
    paired_lattice_sha256: str,
) -> dict[str, object]:
    finalist = _mapping(proof["finalist"], label="successor realized finalist")
    by_coordinate = {
        (int(book["source_ordinal"]), int(book["fold_ordinal"])): book
        for book in [
            _mapping(row, label="successor terminal book proof")
            for row in _sequence(proof["books"], label="successor terminal books")
        ]
    }
    fold_paths: list[dict[str, object]] = []
    all_maxima: list[int] = []
    all_coordinates: list[list[object]] = []
    for fold_ordinal in range(FOLD_COUNT):
        book_weeks: list[dict[str, object]] = []
        maxima: list[int] = []
        for source in source_ordinals:
            coordinate = (source, fold_ordinal)
            if coordinate not in by_coordinate:
                _fail("successor realized book coordinate is missing")
            book = by_coordinate[coordinate]
            selected_ids = [
                str(value)
                for value in _sequence(
                    book["selected_lineup_ids"], label="realized selected lineup IDs"
                )
            ]
            authorities = scored_by_source[source]
            if not set(selected_ids) <= set(authorities):
                _fail("realized successor book lacks a cached roster score")
            scores = [
                int(authorities[lineup_id]["realized_score_micro"])
                for lineup_id in selected_ids
            ]
            maximum = max(scores)
            maximum_ids = sorted(
                lineup_id
                for lineup_id, score in zip(selected_ids, scores, strict=True)
                if score == maximum
            )
            selected_roster_row_hashes = [
                str(authorities[lineup_id]["roster_score_row_sha256"])
                for lineup_id in selected_ids
            ]
            unique_roster_hashes = sorted(set(selected_roster_row_hashes))
            threshold_hits = {
                str(threshold): maximum >= threshold * MICRO_DK_PER_POINT
                for threshold in THRESHOLDS_DK
            }
            row = _with_hash({
                "schema_version": BOOK_WEEK_SCHEMA,
                "source_ordinal": source,
                "slate_id": book["slate_id"],
                "fold_ordinal": fold_ordinal,
                "heldout_block": book["heldout_block"],
                "terminal_book_proof_sha256": book[
                    "terminal_book_proof_sha256"
                ],
                "selected_lineup_count": len(selected_ids),
                "unique_selected_roster_count": len(unique_roster_hashes),
                "selected_lineup_ids_sha256": book[
                    "selected_lineup_ids_sha256"
                ],
                "selected_roster_score_row_sha256s_sha256": canonical_sha256_v1(
                    selected_roster_row_hashes
                ),
                "unique_roster_score_row_sha256s_sha256": canonical_sha256_v1(
                    unique_roster_hashes
                ),
                "weekly_maximum_realized_score_micro": maximum,
                "weekly_maximum_lineup_ids": maximum_ids,
                "weekly_maximum_lineup_ids_sha256": canonical_sha256_v1(
                    maximum_ids
                ),
                "at_or_above_threshold_dk": threshold_hits,
            }, field="book_week_sha256")
            book_weeks.append(row)
            maxima.append(maximum)
            all_maxima.append(maximum)
            all_coordinates.append([
                source, book["slate_id"], fold_ordinal, book["heldout_block"]
            ])
        path = _with_hash({
            "schema_version": FOLD_PATH_SCHEMA,
            "fold_ordinal": fold_ordinal,
            "heldout_block": contract.WORLD_BLOCKS[fold_ordinal],
            "scored_week_count": len(book_weeks),
            "book_weeks": book_weeks,
            "book_weeks_sha256": canonical_sha256_v1(book_weeks),
            "weekly_maximum_sum_micro": sum(maxima),
            "mean_weekly_maximum_micro": _fraction(sum(maxima), len(maxima)),
            "at_or_above_threshold_week_counts": _threshold_counts(maxima),
        }, field="fold_path_sha256")
        fold_paths.append(path)
    coordinate_sha = canonical_sha256_v1(sorted(all_coordinates))
    expected_coordinate_sha = (
        paired_lattice_sha256
        if len(source_ordinals) == PANEL_SLATE_COUNT
        else canonical_sha256_v1(sorted(all_coordinates))
    )
    if coordinate_sha != expected_coordinate_sha:
        _fail("successor realized finalist paired coordinate lattice differs")
    total = sum(all_maxima)
    hit_counts = _threshold_counts(all_maxima)
    result = {
        "schema_version": FINALIST_RESULT_SCHEMA,
        "finalist": finalist,
        "aggregate_metric_row_sha256": proof["aggregate_metric_row_sha256"],
        "terminal_book_proofs_sha256": proof["books_sha256"],
        "terminal_book_proof_sha256s_sha256": canonical_sha256_v1([
            by_coordinate[(source, fold)]["terminal_book_proof_sha256"]
            for fold in range(FOLD_COUNT)
            for source in source_ordinals
        ]),
        "entry_budget": finalist["entry_budget"],
        "fold_path_count": FOLD_COUNT,
        "fold_paths": fold_paths,
        "fold_paths_sha256": canonical_sha256_v1(fold_paths),
        "paired_book_week_count": len(all_maxima),
        "paired_book_week_coordinate_sha256": coordinate_sha,
        "weekly_maximum_sum_micro": total,
        "paired_mean_weekly_maximum_micro": _fraction(total, len(all_maxima)),
        "at_or_above_threshold_book_week_counts": hit_counts,
        "mean_at_or_above_threshold_weeks_per_fold": {
            threshold: _fraction(count, FOLD_COUNT)
            for threshold, count in hit_counts.items()
        },
        "inclusive_threshold_law": "weekly-maximum-greater-than-or-equal-to",
        "path_choice_or_union_performed": False,
        "lineup_rescore_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    result["finalist_result_sha256"] = canonical_sha256_v1(result)
    return result


def build_successor_realized_bridge_v1(
    *,
    terminal_aggregate_identity: object,
    outcome_authority_identity: object,
    mode: str,
    read_terminal_exact: ReadExact,
    read_outcome_exact: ReadExact,
) -> dict[str, object]:
    """Grade one successor terminal from persisted no-rescore score rows."""
    if mode not in {MODE_ONE_SLATE_SMOKE, MODE_FULL_PANEL}:
        _fail("successor realized bridge mode differs")
    if not callable(read_outcome_exact):
        _fail("successor outcome exact reader must be callable")
    terminal = reopen_successor_terminal_books_v1(
        terminal_aggregate_identity=terminal_aggregate_identity,
        read_terminal_exact=read_terminal_exact,
    )
    if terminal.get("terminal_proof_complete") is not True:
        _fail("successor terminal proof is incomplete before outcome boundary")

    # This is intentionally the first use of the realized-outcome capability.
    outcome_body, outcome_identity = _open_json_v1(
        outcome_authority_identity,
        read_exact=read_outcome_exact,
        maximum_bytes=MAXIMUM_ATTRIBUTION_ROOT_BYTES,
        label="successor no-rescore attribution release",
    )
    outcome_open_count = 1
    outcome_root = _bind_attribution_root_v1(
        outcome_body, identity=outcome_identity
    )
    if (
        outcome_root.get("panel_freeze_identity") != contract.PANEL_IDENTITY
        or outcome_root.get("panel_freeze_sha256") != contract.PANEL_SELF_SHA256
    ):
        _fail("successor outcome authority corpus differs from terminal panel")
    descriptors = [
        _mapping(row, label=f"successor attribution descriptor[{index}]")
        for index, row in enumerate(
            _sequence(
                outcome_root.get("slate_attribution_objects"),
                label="successor attribution descriptors",
            )
        )
    ]
    if (
        len(descriptors) != PANEL_SLATE_COUNT
        or [row.get("source_ordinal") for row in descriptors]
        != list(range(PANEL_SLATE_COUNT))
        or [row.get("slate_id") for row in descriptors] != terminal["slate_ids"]
    ):
        _fail("successor outcome authority slate lattice differs")
    source_ordinals = (
        [SMOKE_SOURCE_ORDINAL]
        if mode == MODE_ONE_SLATE_SMOKE
        else list(range(PANEL_SLATE_COUNT))
    )

    score_row_ledgers: list[dict[str, object]] = []
    scored_by_source: dict[int, dict[str, dict[str, object]]] = {}
    for source in source_ordinals:
        descriptor = descriptors[source]
        shard_body, shard_identity = _open_json_v1(
            descriptor["slate_attribution_identity"],
            read_exact=read_outcome_exact,
            maximum_bytes=MAXIMUM_ATTRIBUTION_SHARD_BYTES,
            label=f"successor no-rescore attribution shard[{source}]",
        )
        outcome_open_count += 1
        shard = _bind_attribution_shard_v1(
            shard_body,
            identity=shard_identity,
            descriptor=descriptor,
            source_ordinal=source,
            slate_id=str(terminal["slate_ids"][source]),
        )
        roster_rows, by_lineup = _score_row_authority_v1(
            source_ordinal=source,
            slate_id=str(terminal["slate_ids"][source]),
            selected_rosters=terminal["roster_by_source"][source],
            shard=shard,
            shard_identity=shard_identity,
        )
        score_row_ledgers.append({
            "source_ordinal": source,
            "slate_id": terminal["slate_ids"][source],
            "selected_lineup_count": len(terminal["roster_by_source"][source]),
            "unique_selected_roster_count": len(roster_rows),
            "roster_score_lookup_count": len(roster_rows),
            "roster_score_rows": roster_rows,
            "roster_score_rows_sha256": canonical_sha256_v1(roster_rows),
            "slate_attribution_identity": shard_identity,
            "slate_attribution_sha256": shard["slate_attribution_sha256"],
            "lineup_rows_sha256": shard["lineup_rows_sha256"],
        })
        scored_by_source[source] = by_lineup

    finalist_results = [
        _score_finalist_v1(
            proof=proof,
            scored_by_source=scored_by_source,
            source_ordinals=source_ordinals,
            paired_lattice_sha256=terminal["paired_book_week_lattice_sha256"],
        )
        for proof in terminal["finalist_proofs"]
    ]
    report = {
        "schema_version": BRIDGE_SCHEMA,
        "mode": mode,
        "terminal_aggregate_identity": terminal["terminal_aggregate_identity"],
        "terminal_aggregate_sha256": terminal["terminal_aggregate_sha256"],
        "terminal_exact_open_count_before_outcome": terminal[
            "terminal_exact_open_count"
        ],
        "terminal_proof_complete_before_outcome_open": True,
        "outcome_authority_identity": outcome_identity,
        "outcome_authority_sha256": outcome_root[
            "attribution_release_sha256"
        ],
        "panel_freeze_identity": contract.PANEL_IDENTITY,
        "panel_freeze_sha256": contract.PANEL_SELF_SHA256,
        "scored_source_ordinals": source_ordinals,
        "scored_slate_count": len(source_ordinals),
        "outcome_exact_open_count": outcome_open_count,
        "score_row_ledgers": score_row_ledgers,
        "score_row_ledgers_sha256": canonical_sha256_v1(score_row_ledgers),
        "unique_selected_roster_count": sum(
            int(row["unique_selected_roster_count"])
            for row in score_row_ledgers
        ),
        "roster_score_lookup_count": sum(
            int(row["roster_score_lookup_count"]) for row in score_row_ledgers
        ),
        "score_lookup_deduplication_law": (
            "one-persisted-realized-score-per-distinct-roster-per-slate-"
            "reused-across-folds-finalists-and-lineup-id-aliases"
        ),
        "finalist_count": len(finalist_results),
        "finalist_results": finalist_results,
        "finalist_results_sha256": canonical_sha256_v1(finalist_results),
        "paired_book_week_lattice_sha256": terminal[
            "paired_book_week_lattice_sha256"
        ],
        "thresholds_dk": list(THRESHOLDS_DK),
        "inclusive_threshold_law": "weekly-maximum-greater-than-or-equal-to",
        "outcome_source_read": False,
        "bigquery_client_constructed": False,
        "lineup_rescore_performed": False,
        "score_row_authority": (
            "persisted-full-union-attribution-lineup-realized-score-micro"
        ),
        "source_control_schema_adaptation_performed": False,
        "historical_retune_licensed": False,
        "promotion_authority": False,
        "decision_authority": False,
        "graph_mutation_performed": False,
    }
    report["realized_bridge_sha256"] = canonical_sha256_v1(report)
    if len(canonical_json_bytes_v1(report)) > MAXIMUM_REPORT_BYTES:
        _fail("successor realized bridge report exceeds its byte ceiling")
    return report


__all__ = [
    "BOOK_WEEK_SCHEMA",
    "BRIDGE_SCHEMA",
    "CLOUD_ENTRYPOINT_REGISTRATION_SCHEMA",
    "CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error",
    "ENTRYPOINT_COMMAND",
    "ENTRYPOINT_IMAGE_PATH",
    "ENTRYPOINT_RELATIVE_PATH",
    "FINALIST_RESULT_SCHEMA",
    "FOLD_PATH_SCHEMA",
    "MICRO_DK_PER_POINT",
    "MODE_FULL_PANEL",
    "MODE_ONE_SLATE_SMOKE",
    "OUTPUT_FILENAME",
    "PUBLICATION_ENVELOPE_SCHEMA",
    "ROSTER_SCORE_ROW_SCHEMA",
    "THRESHOLDS_DK",
    "build_publication_envelope_v1",
    "build_successor_realized_bridge_v1",
    "canonical_json_bytes_v1",
    "canonical_sha256_v1",
    "cloud_entrypoint_registration_v1",
    "reopen_successor_terminal_books_v1",
]
