"""Hermetic tests for the direct selector-successor realized bridge."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as contract,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_rank150_dpp_mode_v1 as rank150_dpp,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_authority_v1 as authority,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_process_adapter_v1 as adapter,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_realized_bridge_v1 as bridge,
)
from tests import (
    test_corpus_r6_current_bank_selector_successor_evaluation_v1
    as frozen_successor_fixture,
)


def _raw(value: object) -> bytes:
    return batch.canonical_json_bytes(value)


def _identity(uri: str, value: object, generation: str = "1") -> dict[str, object]:
    raw = _raw(value)
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _hash(value: object) -> str:
    return batch.canonical_sha256(value)


class _Store:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str, str, int], bytes] = {}
        self.calls: list[dict[str, object]] = []

    @staticmethod
    def _key(value: object) -> tuple[str, str, str, int]:
        row = dict(value)  # type: ignore[arg-type]
        return (
            str(row["uri"]),
            str(row["generation"]),
            str(row["sha256"]),
            int(row["bytes"]),
        )

    def put(self, identity: object, value: object) -> None:
        self.values[self._key(identity)] = _raw(value)

    def read_exact(self, identity: object) -> bytes:
        row = dict(identity)  # type: ignore[arg-type]
        self.calls.append(row)
        return self.values[self._key(row)]


def _selector_coordinate(selector_id: str) -> dict[str, object]:
    body = {
        "schema_version": bridge.evaluation.SELECTOR_COORDINATE_SCHEMA,
        "selector_family_id": "synthetic-rank150-dpp-v1",
        "selector_ordinal": 0,
        "selector_id": selector_id,
        "selector_semantics_sha256": sha256(
            f"semantics:{selector_id}".encode()
        ).hexdigest(),
        "adapter_id": "synthetic-native-adapter-v1",
        "executable_fingerprint_sha256": sha256(
            f"executable:{selector_id}".encode()
        ).hexdigest(),
    }
    body["selector_coordinate_sha256"] = _hash(body)
    return body


def _candidate_rows(*, roster_mismatch: bool = False) -> list[dict[str, object]]:
    rows = []
    for index in range(150):
        roster_index = 148 if index == 149 else index
        roster = tuple(f"p-{roster_index:03d}-{slot}" for slot in range(9))
        if roster_mismatch and index == 0:
            roster = ("wrong-player", *roster[1:])
        rows.append({
            "lineup_id": f"lineup-{index:03d}",
            "roster_player_ids": list(roster),
        })
    return rows


def _make_case(
    monkeypatch: pytest.MonkeyPatch,
    *,
    selector_mode: str,
    outcome_roster_mismatch: bool = False,
) -> dict[str, object]:
    budgets = [80] if selector_mode == "grouped" else [80, 100, 150]
    selector_id = (
        "grouped-expected-max-v1"
        if selector_mode == "grouped"
        else "rank150-native-v1"
    )
    coordinate = _selector_coordinate(selector_id)
    selected_ids = [f"lineup-{index:03d}" for index in range(150)]
    canonical_candidates = _candidate_rows()
    candidate_by_id = {
        str(row["lineup_id"]): row for row in canonical_candidates
    }
    prefixes = []
    for budget in budgets:
        ids = selected_ids[:budget]
        rosters = [candidate_by_id[lineup_id]["roster_player_ids"] for lineup_id in ids]
        prefixes.append({
            "prefix_size": budget,
            "selected_lineup_ids_sha256": _hash(ids),
            "selected_rosters_sha256": _hash(rosters),
            "prefix_payload_sha256": _hash({
                "selected_lineup_ids": ids,
                "selected_rosters": rosters,
            }),
        })
    if selector_mode == "grouped":
        cell = {
            "schema_version": authority.AUTHORITY_CELL_SCHEMA,
            "view_id": "U",
            "preset_ordinal": 0,
            "preset_id": selector_id,
            "preset_sha256": coordinate["selector_semantics_sha256"],
            "adapter_id": coordinate["adapter_id"],
            "executable_fingerprint_sha256": coordinate[
                "executable_fingerprint_sha256"
            ],
            "selected_lineup_ids": selected_ids[:80],
            "prefixes": prefixes,
        }
        selected_for_roster_hash = selected_ids[:80]
    else:
        cell = {
            "schema_version": rank150_dpp.AUTHORITY_CELL_SCHEMA,
            "view_id": "U",
            "selector_coordinate": coordinate,
            "selected_lineup_ids": selected_ids,
            "prefixes": prefixes,
        }
        selected_for_roster_hash = selected_ids
    if selector_mode == "grouped":
        coordinate = bridge._cell_selector_coordinate(cell)
    cell["selected_lineup_ids_sha256"] = _hash(selected_for_roster_hash)
    cell["selected_rosters_sha256"] = _hash([
        candidate_by_id[lineup_id]["roster_player_ids"]
        for lineup_id in selected_for_roster_hash
    ])
    cell["authority_cell_sha256"] = _hash(cell)

    def validate_terminal(value: object) -> dict[str, object]:
        return dict(value)  # type: ignore[arg-type]

    def validate_evaluation(value: object) -> dict[str, object]:
        return dict(value)  # type: ignore[arg-type]

    def validate_projection(value: object) -> dict[str, object]:
        return dict(value)  # type: ignore[arg-type]

    def validate_selection(
        value: object, *, projection_bundle: object,
    ) -> dict[str, object]:
        assert dict(projection_bundle)["panel_identity"] == contract.PANEL_IDENTITY
        return dict(value)  # type: ignore[arg-type]

    def validate_fold(
        value: object, **_: object,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        receipt = dict(value)  # type: ignore[arg-type]
        return receipt, [dict(row) for row in receipt["authority_response"]["cells"]]

    monkeypatch.setattr(
        bridge.evaluation, "validate_terminal_aggregate_v1", validate_terminal
    )
    monkeypatch.setattr(
        bridge.evaluation, "validate_evaluation_result_v1", validate_evaluation
    )
    monkeypatch.setattr(
        bridge.contract, "validate_projection_bundle_v1", validate_projection
    )
    monkeypatch.setattr(
        bridge, "_validate_selection_for_projection", validate_selection
    )
    monkeypatch.setattr(bridge, "_validate_fold_receipt", validate_fold)
    monkeypatch.setattr(
        bridge.score_authority,
        "validate_attribution_release_score_authority_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        bridge.score_authority,
        "validate_slate_score_row_authority_v1",
        lambda value: dict(value),
    )

    terminal_store = _Store()
    predecessors = []
    all_metric_hashes = {budget: [] for budget in budgets}
    all_pairing_hashes = {budget: [] for budget in budgets}
    for source in range(bridge.PANEL_SLATE_COUNT):
        slate_id = f"synthetic-2024-w{source + 1:02d}"
        projection_folds = [
            {"candidates": deepcopy(canonical_candidates)}
            for _ in range(bridge.FOLD_COUNT)
        ]
        projection = {
            "source_ordinal": source,
            "slate_id": slate_id,
            "panel_identity": dict(contract.PANEL_IDENTITY),
            "panel_self_sha256": contract.PANEL_SELF_SHA256,
            "fold_projections": projection_folds,
            "projection_bundle_sha256": sha256(
                f"projection:{source}".encode()
            ).hexdigest(),
        }
        projection_identity = _identity(
            f"gs://synthetic/projection/{source:02d}.json", projection
        )
        terminal_store.put(projection_identity, projection)

        fold_receipts = []
        for fold in range(bridge.FOLD_COUNT):
            if selector_mode == "grouped":
                receipt = {
                    "schema_version": adapter.FOLD_RECEIPT_SCHEMA,
                    "successor_fold_receipt_sha256": sha256(
                        f"grouped-fold:{source}:{fold}".encode()
                    ).hexdigest(),
                    "authority_response": {"cells": [deepcopy(cell)]},
                }
            else:
                receipt = {
                    "schema_version": rank150_dpp.FOLD_RECEIPT_SCHEMA,
                    "rank150_dpp_fold_receipt_sha256": sha256(
                        f"rank-fold:{source}:{fold}".encode()
                    ).hexdigest(),
                    "authority_response": {"cells": [deepcopy(cell)]},
                }
            fold_receipts.append(receipt)
        selection = {
            "source_ordinal": source,
            "slate_id": slate_id,
            "fold_receipts": fold_receipts,
            "slate_result_sha256": sha256(
                f"selection:{selector_mode}:{source}".encode()
            ).hexdigest(),
        }
        selection_identity = _identity(
            f"gs://synthetic/selection/{selector_mode}/{source:02d}.json",
            selection,
        )
        terminal_store.put(selection_identity, selection)

        evaluation_folds = []
        for fold in range(bridge.FOLD_COUNT):
            rows = []
            for budget in budgets:
                prefix = next(row for row in prefixes if row["prefix_size"] == budget)
                pairing_hash = sha256(
                    f"pairing:{selector_mode}:{source}:{fold}:{budget}".encode()
                ).hexdigest()
                row = {
                    "view_id": "U",
                    "selector_coordinate_sha256": coordinate[
                        "selector_coordinate_sha256"
                    ],
                    "entry_budget": budget,
                    "selection_cell_sha256": cell["authority_cell_sha256"],
                    "book_payload_sha256": prefix["prefix_payload_sha256"],
                    "selected_lineup_ids_sha256": prefix[
                        "selected_lineup_ids_sha256"
                    ],
                    "selected_rosters_sha256": prefix[
                        "selected_rosters_sha256"
                    ],
                    "pairing_coordinate_sha256": pairing_hash,
                }
                row["book_metric_row_sha256"] = _hash(row)
                all_metric_hashes[budget].append(row["book_metric_row_sha256"])
                all_pairing_hashes[budget].append(pairing_hash)
                rows.append(row)
            evaluation_folds.append({"book_metric_rows": rows})
        evaluation_result = {
            "source_ordinal": source,
            "slate_id": slate_id,
            "projection_bundle_identity": projection_identity,
            "projection_bundle_sha256": projection["projection_bundle_sha256"],
            "selection_slate_result_identity": selection_identity,
            "selection_slate_result_sha256": selection["slate_result_sha256"],
            "folds": evaluation_folds,
            "evaluation_result_sha256": sha256(
                f"evaluation:{selector_mode}:{source}".encode()
            ).hexdigest(),
        }
        evaluation_identity = _identity(
            f"gs://synthetic/evaluation/{selector_mode}/{source:02d}.json",
            evaluation_result,
        )
        terminal_store.put(evaluation_identity, evaluation_result)
        predecessors.append({
            "source_ordinal": source,
            "slate_id": slate_id,
            "evaluation_identity": evaluation_identity,
            "evaluation_result_sha256": evaluation_result[
                "evaluation_result_sha256"
            ],
            "selection_slate_result_identity": selection_identity,
        })

    aggregate_rows = []
    finalists = []
    for budget in budgets:
        aggregate = {
            "view_id": "U",
            "selector_coordinate_sha256": coordinate[
                "selector_coordinate_sha256"
            ],
            "entry_budget": budget,
            "complete_cell_count": bridge.PANEL_SLATE_COUNT * bridge.FOLD_COUNT,
            "book_metric_row_sha256s_sha256": _hash(
                sorted(all_metric_hashes[budget])
            ),
            "pairing_coordinate_sha256s_sha256": _hash(
                sorted(all_pairing_hashes[budget])
            ),
        }
        aggregate["aggregate_metric_row_sha256"] = _hash(aggregate)
        aggregate_rows.append(aggregate)
        finalists.append({
            "entry_budget": budget,
            "view_id": "U",
            "profile_id": "all-profiles",
            "profile_ordinal": -1,
            "selector_coordinate": coordinate,
            "selector_coordinate_sha256": coordinate[
                "selector_coordinate_sha256"
            ],
            "aggregate_metric_row_sha256": aggregate[
                "aggregate_metric_row_sha256"
            ],
            "roles": ["synthetic-finalist"],
            "finalist_sha256": sha256(
                f"finalist:{selector_mode}:{budget}".encode()
            ).hexdigest(),
        })
    terminal = {
        "terminal_before_realized_outcome_read": True,
        "predecessors": predecessors,
        "aggregate_metric_rows": aggregate_rows,
        "finalists": finalists,
        "terminal_aggregate_sha256": sha256(
            f"terminal:{selector_mode}".encode()
        ).hexdigest(),
    }
    terminal_identity = _identity(
        f"gs://synthetic/terminal/{selector_mode}.json", terminal
    )
    terminal_store.put(terminal_identity, terminal)

    outcome_store = _Store()
    descriptors = []
    for source in range(bridge.PANEL_SLATE_COUNT):
        slate_id = f"synthetic-2024-w{source + 1:02d}"
        score = [
            199_000_000,
            200_000_000,
            210_000_000,
            220_000_000,
            230_000_000,
        ][source % 5]
        outcome_candidates = _candidate_rows(
            roster_mismatch=outcome_roster_mismatch and source == 0
        )
        lineup_rows = [
            {
                "source_ordinal": source,
                "slate_id": slate_id,
                "union_index": index,
                "lineup_id": row["lineup_id"],
                "roster_player_ids": row["roster_player_ids"],
                "roster_identity_sha256": _hash(row["roster_player_ids"]),
                "realized_score_micro": score,
            }
            for index, row in enumerate(outcome_candidates)
        ]
        shard = {
            "source_ordinal": source,
            "slate_id": slate_id,
            "panel_freeze_identity": dict(contract.PANEL_IDENTITY),
            "lineup_count": len(lineup_rows),
            "lineup_rows": lineup_rows,
            "lineup_rows_sha256": _hash(lineup_rows),
            "slate_attribution_sha256": sha256(
                f"attribution:{source}".encode()
            ).hexdigest(),
        }
        shard_identity = _identity(
            f"gs://synthetic/outcome/{source:02d}-{slate_id}.json", shard
        )
        outcome_store.put(shard_identity, shard)
        descriptors.append({
            "source_ordinal": source,
            "slate_id": slate_id,
            "slate_attribution_identity": shard_identity,
            "slate_attribution_sha256": shard["slate_attribution_sha256"],
            "lineup_count": shard["lineup_count"],
        })
    outcome_root = {
        "target_uri": "gs://synthetic/outcome/attribution-release.json",
        "panel_freeze_identity": dict(contract.PANEL_IDENTITY),
        "panel_freeze_sha256": contract.PANEL_SELF_SHA256,
        "slate_attribution_objects": descriptors,
        "attribution_release_sha256": sha256(
            f"outcome-root:{selector_mode}".encode()
        ).hexdigest(),
    }
    outcome_identity = _identity(str(outcome_root["target_uri"]), outcome_root)
    outcome_store.put(outcome_identity, outcome_root)
    return {
        "terminal": terminal,
        "terminal_identity": terminal_identity,
        "terminal_store": terminal_store,
        "outcome_identity": outcome_identity,
        "outcome_store": outcome_store,
        "budgets": budgets,
    }


@pytest.mark.parametrize(
    ("selector_mode", "expected_unique_per_slate"),
    [("grouped", 80), ("rank150-dpp", 149)],
)
def test_scores_native_grouped_and_rank_dpp_books_on_one_paired_lattice(
    monkeypatch: pytest.MonkeyPatch,
    selector_mode: str,
    expected_unique_per_slate: int,
) -> None:
    case = _make_case(monkeypatch, selector_mode=selector_mode)
    report = bridge.build_successor_realized_bridge_v1(
        terminal_aggregate_identity=case["terminal_identity"],
        outcome_authority_identity=case["outcome_identity"],
        mode=bridge.MODE_FULL_PANEL,
        read_terminal_exact=case["terminal_store"].read_exact,
        read_outcome_exact=case["outcome_store"].read_exact,
    )
    assert report["terminal_exact_open_count_before_outcome"] == 1 + 54 * 3
    assert len(case["terminal_store"].calls) == 1 + 54 * 3
    assert report["outcome_exact_open_count"] == 55
    assert len(case["outcome_store"].calls) == 55
    assert report["lineup_rescore_performed"] is False
    assert report["source_control_schema_adaptation_performed"] is False
    assert report["roster_score_lookup_count"] == 54 * expected_unique_per_slate
    assert report["unique_selected_roster_count"] == (
        report["roster_score_lookup_count"]
    )
    assert {row["entry_budget"] for row in report["finalist_results"]} == set(
        case["budgets"]
    )
    coordinate_hashes = {
        row["paired_book_week_coordinate_sha256"]
        for row in report["finalist_results"]
    }
    assert len(coordinate_hashes) == 1
    for result in report["finalist_results"]:
        assert result["paired_book_week_count"] == 54 * 5
        assert result["at_or_above_threshold_book_week_counts"] == {
            "200": 43 * 5,
            "210": 32 * 5,
            "220": 21 * 5,
            "230": 10 * 5,
        }
        assert result["paired_mean_weekly_maximum_micro"] == {
            "numerator": (
                11 * (199_000_000 + 200_000_000 + 210_000_000 + 220_000_000)
                + 10 * 230_000_000
            )
            * 5,
            "denominator": 54 * 5,
        }


def test_terminal_failure_makes_no_outcome_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _make_case(monkeypatch, selector_mode="grouped")

    def reject(_: object) -> dict[str, object]:
        raise bridge.evaluation.CorpusR6CurrentBankSelectorSuccessorEvaluationV1Error(
            "synthetic terminal failure"
        )

    monkeypatch.setattr(
        bridge.evaluation, "validate_terminal_aggregate_v1", reject
    )
    with pytest.raises(
        bridge.CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error,
        match="synthetic terminal failure",
    ):
        bridge.build_successor_realized_bridge_v1(
            terminal_aggregate_identity=case["terminal_identity"],
            outcome_authority_identity=case["outcome_identity"],
            mode=bridge.MODE_FULL_PANEL,
            read_terminal_exact=case["terminal_store"].read_exact,
            read_outcome_exact=case["outcome_store"].read_exact,
        )
    assert case["outcome_store"].calls == []


def test_selected_roster_must_match_persisted_score_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _make_case(
        monkeypatch,
        selector_mode="rank150-dpp",
        outcome_roster_mismatch=True,
    )
    with pytest.raises(
        bridge.CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error,
        match="roster differs from score authority",
    ):
        bridge.build_successor_realized_bridge_v1(
            terminal_aggregate_identity=case["terminal_identity"],
            outcome_authority_identity=case["outcome_identity"],
            mode=bridge.MODE_FULL_PANEL,
            read_terminal_exact=case["terminal_store"].read_exact,
            read_outcome_exact=case["outcome_store"].read_exact,
        )


def test_smoke_still_reopens_full_terminal_before_one_outcome_shard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _make_case(monkeypatch, selector_mode="grouped")
    report = bridge.build_successor_realized_bridge_v1(
        terminal_aggregate_identity=case["terminal_identity"],
        outcome_authority_identity=case["outcome_identity"],
        mode=bridge.MODE_ONE_SLATE_SMOKE,
        read_terminal_exact=case["terminal_store"].read_exact,
        read_outcome_exact=case["outcome_store"].read_exact,
    )
    assert len(case["terminal_store"].calls) == 1 + 54 * 3
    assert len(case["outcome_store"].calls) == 2
    assert report["scored_source_ordinals"] == [0]
    result = report["finalist_results"][0]
    assert result["paired_book_week_count"] == 5
    assert result["paired_mean_weekly_maximum_micro"] == {
        "numerator": 5 * 199_000_000,
        "denominator": 5,
    }


def test_exact_terminal_identity_is_enforced_before_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _make_case(monkeypatch, selector_mode="grouped")
    bad_identity = dict(case["terminal_identity"])
    bad_identity["sha256"] = "f" * 64
    with pytest.raises(
        bridge.CorpusR6CurrentBankSelectorSuccessorRealizedBridgeV1Error,
        match="exact bytes differ",
    ):
        bridge.build_successor_realized_bridge_v1(
            terminal_aggregate_identity=bad_identity,
            outcome_authority_identity=case["outcome_identity"],
            mode=bridge.MODE_FULL_PANEL,
            read_terminal_exact=lambda _: _raw(case["terminal"]),
            read_outcome_exact=case["outcome_store"].read_exact,
        )
    assert case["outcome_store"].calls == []


def test_real_grouped_fixture_reopens_exact_80_book_without_control_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection, bundle, projections, later_body, matrices = (
        frozen_successor_fixture._fixture(monkeypatch)
    )
    selection_identity = frozen_successor_fixture._identity(
        "gs://fixture/selection.json", selection
    )
    evaluation_result = bridge.evaluation.build_evaluation_result_v1(
        selection_slate_result=selection,
        selection_slate_result_identity=selection_identity,
        projection_bundle=bundle,
        projection_bundle_identity=frozen_successor_fixture._identity(
            "gs://fixture/projection.json", bundle
        ),
        heldout_fold_input_stream=[
            {
                "fold_ordinal": fold,
                "heldout_artifact_identity": projections[fold][
                    "world_artifact_identities"
                ][f"world_artifact_{contract.WORLD_BLOCKS[fold].lower()}"],
                "heldout_score_matrix": matrices[fold],
            }
            for fold in range(contract.FOLDS_PER_SLATE)
        ],
        later_source_body=later_body,
    )
    evaluation_identity = frozen_successor_fixture._identity(
        "gs://fixture/evaluation.json", evaluation_result
    )
    fold_receipt, cells = bridge._validate_fold_receipt(
        selection["fold_receipts"][0],
        source_ordinal=0,
        fold_ordinal=0,
        projection=projections[0],
    )
    cell = cells[0]
    coordinate = bridge._cell_selector_coordinate(cell)
    finalist = {
        "entry_budget": 80,
        "view_id": cell["view_id"],
        "selector_coordinate_sha256": coordinate[
            "selector_coordinate_sha256"
        ],
    }
    proof, rosters, metric_hash, pairing_hash = bridge._book_from_cell_v1(
        source_ordinal=0,
        slate_id=str(bundle["slate_id"]),
        fold_ordinal=0,
        finalist=finalist,
        cell=cell,
        projection=projections[0],
        selection=selection,
        selection_identity=selection_identity,
        fold_receipt=fold_receipt,
        evaluation_result=evaluation_result,
        evaluation_identity=evaluation_identity,
    )
    assert proof["entry_budget"] == 80
    assert len(proof["selected_lineup_ids"]) == 80
    assert len(rosters) == 80
    metric_row = next(
        row
        for row in evaluation_result["folds"][0]["book_metric_rows"]
        if row["view_id"] == finalist["view_id"]
        and row["selector_coordinate_sha256"]
        == finalist["selector_coordinate_sha256"]
        and row["entry_budget"] == 80
    )
    assert metric_hash == metric_row["book_metric_row_sha256"]
    assert pairing_hash == metric_row["pairing_coordinate_sha256"]
    assert proof["selection_fold_receipt_sha256"] == fold_receipt[
        "successor_fold_receipt_sha256"
    ]
