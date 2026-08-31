from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from nfl_dfs.research import odds_prop_override_ablation_v1 as odds
from nfl_dfs.research import (
    corpus_r6_construction_allocation_grade_operator_v1 as outcome_operator,
)
from nfl_dfs.research import paid_source_ablation_grade_v1 as grade
from nfl_dfs.research import paid_source_ablation_operator_v1 as operator
from nfl_dfs.research import paid_source_ablation_registry_v1 as registry
from nfl_dfs.research import paid_source_odds_execution_adapter_v1 as execution
from tests import test_paid_source_ablations_v1 as paid_fixture
from tests import test_paid_source_odds_execution_adapter_v1 as execution_fixture


def _published_callbacks() -> tuple[dict[str, tuple[str, bytes]], object, object]:
    storage: dict[str, tuple[str, bytes]] = {}

    def publish(uri: str, raw: bytes) -> dict[str, object]:
        if uri in storage:
            raise AssertionError("create-once collision")
        generation = str(len(storage) + 1)
        storage[uri] = (generation, raw)
        return {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
            "create_once": True,
        }

    def read(identity: object) -> bytes:
        assert isinstance(identity, dict)
        generation, raw = storage[str(identity["uri"])]
        assert generation == str(identity["generation"])
        return raw

    return storage, publish, read


def _frozen_odds() -> tuple[dict[str, object], dict[str, object]]:
    census = paid_fixture._odds_support()
    panel = odds.build_odds_prop_override_panel_support_census_v1(
        [census],
        preregistered_slates=[census["slate"]],
        preregistered_panel_identity=paid_fixture._identity_for_body(
            [census["slate"]], "operator-preregistered-panel"
        ),
    )
    on_candidates = [f"lineup-{index:03d}" for index in range(100)]
    off_candidates = [f"lineup-{index:03d}" for index in range(20, 120)]
    trace = odds.build_odds_prop_override_influence_trace_v1(
        support_census=census,
        cell_outputs=paid_fixture._odds_cross_outputs(
            census, on_candidates, off_candidates
        ),
    )
    return panel, trace


def _odds_matrix_authority() -> dict[str, bytes]:
    return {
        sha256(raw).hexdigest(): raw
        for raw in paid_fixture._odds_world_matrix_bytes().values()
    }


def _executed_odds_ready(
    run_id: str,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, tuple[str, bytes]],
    object,
    object,
]:
    (
        census,
        player_input,
        player_identity,
        candidate_input,
        candidate_identity,
        centered_bytes,
        centered_identity,
    ) = execution_fixture._support_and_inputs()
    storage, publish, read = _published_callbacks()
    for identity, raw in (
        (player_identity, registry.canonical_json_bytes(player_input)),
        (candidate_identity, registry.canonical_json_bytes(candidate_input)),
        (centered_identity, centered_bytes),
    ):
        storage[str(identity["uri"])] = (str(identity["generation"]), raw)
    ready = operator.run_odds_panel_to_ready_v1(
        slate_inputs=[{
            "slate": census["slate"],
            "model_rows": [
                {"gsis_id": row["gsis_id"], "model_mean": row["model_mean"]}
                for row in census["cells"][0]["rows"]
            ],
            "fallback_authority": census["fallback_authority_body"],
            "fallback_authority_identity": census["fallback_authority_identity"],
            "prop_authority": census["prop_authority_body"],
            "prop_authority_identity": census["prop_authority_identity"],
            "player_input_identity": player_identity,
            "candidate_input_identity": candidate_identity,
            "centered_world_identity": centered_identity,
            "runtime_attestation": execution_fixture._runtime(),
        }],
        preregistered_slates=[census["slate"]],
        preregistered_panel_identity=paid_fixture._identity_for_body(
            [census["slate"]], f"{run_id}-panel"
        ),
        run_id=run_id,
        output_prefix="gs://fixture-bucket/paid-source-ablation",
        frozen_at="2026-08-30T12:00:00Z",
        publish_execution_create_once=publish,  # type: ignore[arg-type]
        read_exact=read,  # type: ignore[arg-type]
    )
    trace_raw = ready["documents_raw_by_name"]["slates/0000/evidence"]
    trace = json.loads(trace_raw)
    return ready, trace, storage, publish, read


def test_paid_source_operator_persists_bodies_and_publishes_root_last() -> None:
    ready, _, storage, publish, read = _executed_odds_ready(
        "odds-body-bound-fixture"
    )
    assert operator.validate_ready_bundle_v1(ready) == ready
    kinds = {row["kind"] for row in ready["document_manifest"]}
    assert {
        "odds-candidate-population",
        "odds-selection-world",
        "odds-selected-book",
        "odds-support-census",
        "odds-genuine-execution-receipt",
        "odds-centered-player-worlds",
    }.issubset(kinds)
    envelope = operator.publish_paid_source_bundle_v1(
        ready, publish_create_once=publish, read_exact=read
    )
    assert list(storage)[-1].endswith("/terminal.json")
    reopened = operator.reopen_paid_source_terminal_v1(envelope, read_exact=read)
    assert reopened["complete"] is True
    assert reopened["outcome_data_accessed"] is False
    assert len(reopened["slate_evidence"]) == 1
    assert any(
        name.endswith("/books/odds-prop-override-on-v1--odds-prop-override-off-v1")
        for name in reopened["documents_by_name"]
    )

    # The terminal does not merely trust copied trace bodies: it reopens the
    # solver-emitted object at its original staged generation and replays K80.
    selected_uri = next(
        uri for uri in storage
        if "/staging/" in uri and "/selected-books/" in uri
    )
    generation, selected_raw = storage[selected_uri]
    storage[selected_uri] = (generation, selected_raw + b"tamper")
    with pytest.raises(
        operator.PaidSourceAblationOperatorV1Error,
        match="generation-exact content differs",
    ):
        operator.reopen_paid_source_terminal_v1(envelope, read_exact=read)


def _recognized_authority(
    trace: dict[str, object], players: list[str],
) -> tuple[dict[str, object], outcome_operator.OpenedOutcomeAuthorityV1]:
    completion = {
        "schema_version": outcome_operator.RECOGNIZED_OUTCOME_COMPLETION_SCHEMA,
        "run_id": "recognized-catalog-fixture",
        "completion_sha256": registry.canonical_sha256({"fixture": "completion"}),
    }
    snapshot = {
        "outcome_snapshot_sha256": registry.canonical_sha256({"fixture": "snapshot"}),
    }
    completion_identity = paid_fixture._identity_for_body(
        completion, "recognized-catalog-completion"
    )
    snapshot_identity = paid_fixture._identity_for_body(
        snapshot, "recognized-catalog-snapshot"
    )
    closure = {
        "recognized_authority_only": True,
        "all_content_identities_generation_exact_reopened": True,
        "complete": True,
        "closure_sha256": registry.canonical_sha256({"fixture": "closure"}),
    }
    lease_body = {
        "version": "historical-outcome-active-v1",
        "run_id": completion["run_id"],
    }
    lease_identity = paid_fixture._identity_for_body(
        lease_body, "recognized-catalog-live-lease"
    )
    slate = trace["slate"]
    authority = outcome_operator.OpenedOutcomeAuthorityV1(
        completion=completion,
        completion_identity=completion_identity,
        snapshot=snapshot,
        snapshot_identity=snapshot_identity,
        player_scores={
            (0, player_id): (10 + index % 17) * 1_000_000
            for index, player_id in enumerate(players)
        },
        slate_keys={0: (
            int(slate["season"]), int(slate["week"]), str(slate["slate_id"])
        )},
        lease_body=lease_body,
        lease_identity=lease_identity,
        lease_body_sha256=registry.canonical_sha256(lease_body),
        closure_receipt=closure,
    )
    return completion_identity, authority


def test_paid_source_independent_grade_reopens_then_computes_exact_cross(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready, trace, storage, publish, read = _executed_odds_ready(
        "odds-grade-fixture"
    )
    envelope = operator.publish_paid_source_bundle_v1(
        ready, publish_create_once=publish, read_exact=read
    )
    players = sorted({
        player_id
        for output in trace["cell_outputs"]
        for row in output["candidate_population_body"]["candidate_rows"]
        for player_id in row["player_ids"]
    })
    outcome_identity, authority = _recognized_authority(trace, players)
    opened: list[object] = []
    lease_checks: list[object] = []

    def verify_live_lease(
        *, expected_identity: object, catalog_run_id: str,
    ) -> object:
        lease_checks.append((expected_identity, catalog_run_id))
        assert expected_identity == authority.lease_identity
        assert catalog_run_id == authority.completion["run_id"]
        return {
            "body": authority.lease_body,
            "object_receipt": authority.lease_identity,
        }

    def open_authority(
        identity: object, *, read_exact: object, verify_live_lease: object,
    ) -> object:
        opened.append((identity, read_exact, verify_live_lease))
        assert identity == outcome_identity
        verify_live_lease(
            expected_identity=authority.lease_identity,
            catalog_run_id=authority.completion["run_id"],
        )
        return authority

    monkeypatch.setattr(
        grade.outcomes, "open_recognized_outcome_authority_v1", open_authority
    )
    result = grade.grade_paid_source_terminal_v1(
        envelope,
        read_exact=read,
        verify_live_lease=verify_live_lease,
        grade_id="odds-grade-v1",
        outcome_authority_identity=outcome_identity,
    )
    assert opened == [(outcome_identity, read, verify_live_lease)]
    assert lease_checks == [
        (authority.lease_identity, authority.completion["run_id"]),
        (authority.lease_identity, authority.completion["run_id"]),
    ]
    assert grade.validate_paid_source_grade_v1(result) == result
    assert result["selection_terminal_exact_reopened_before_outcome_join"] is True
    assert result["production_authority"] is False
    weekly = result["weekly_results"][0]
    assert result["prefixes"] == [20, 40, 80]
    assert result["thresholds"] == [194, 200, 210, 220, 230, 240]
    assert result[
        "outcome_authority_and_all_predecessors_generation_exact_reopened"
    ] is True
    effect_row = next(
        row for row in weekly["effects_by_prefix"]
        if row["prefix"] == 80
    )
    effects = effect_row["selected_book_effects"]
    assert set(effects) == {
        "selected_book_generation_effect_at_retrieval_off_micro",
        "selected_book_retrieval_effect_at_generation_on_micro",
        "selected_book_interaction_micro",
        "selected_book_operational_on_on_vs_off_off_micro",
    }
    cells = weekly["cells"]
    on, off = registry.ODDS_CELL_ORDER
    k80 = lambda cell_id: next(
        row for row in cells[cell_id]["selected_book"]["prefixes"]
        if row["prefix"] == 80
    )["weekly_max_micro"]
    assert effects["selected_book_interaction_micro"] == (
        k80(f"{on}--{on}")
        - k80(f"{on}--{off}")
        - k80(f"{off}--{on}")
        + k80(f"{off}--{off}")
    )
    for cell in cells.values():
        candidate = cell["candidate_pool"]
        selected = cell["selected_book"]
        decomposition = cell["k80_decomposition"]
        assert candidate["candidate_count"] >= 80
        assert candidate["realized_ceiling_micro"] >= next(
            row["weekly_max_micro"] for row in selected["prefixes"]
            if row["prefix"] == 80
        )
        assert decomposition[
            "selector_regret_candidate_pool_to_selected_micro"
        ] >= 0
        assert cell["admission"] == {
            "available": False,
            "reason": "no-distinct-admission-stage-direct-population-to-k80-selection",
        }
        assert [
            row["threshold"] for row in decomposition["thresholds"]
        ] == [194, 200, 210, 220, 230, 240]
    aggregate_k80 = next(
        row for row in result["aggregate"]["prefix_results"]
        if row["prefix"] == 80
    )
    for cell in aggregate_k80["cells"].values():
        assert cell["candidate_supply"]["bootstrap_mean_interval_95"][
            "resamples"
        ] == 10_000
        assert cell["selected_book"]["bootstrap_mean_interval_95"][
            "estimator"
        ] == "season-stratified-slate-bootstrap-mean-95pct"

    poisoned = deepcopy(result)
    poisoned["weekly_results"][0]["effects_by_prefix"][-1][
        "selected_book_effects"
    ][
        "selected_book_interaction_micro"
    ] += 1
    poisoned["weekly_result_manifest_sha256"] = registry.canonical_sha256(
        poisoned["weekly_results"]
    )
    poisoned.pop("grade_sha256")
    poisoned["grade_sha256"] = registry.canonical_sha256(poisoned)
    with pytest.raises(
        grade.PaidSourceAblationGradeV1Error,
        match="weekly factor effects differ",
    ):
        grade.validate_paid_source_grade_v1(poisoned)


def test_paid_source_grade_fails_closed_when_any_frozen_candidate_lacks_actuals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready, trace, _, publish, read = _executed_odds_ready(
        "odds-grade-missing-candidate-actual"
    )
    envelope = operator.publish_paid_source_bundle_v1(
        ready, publish_create_once=publish, read_exact=read
    )
    players = sorted({
        player_id
        for output in trace["cell_outputs"]
        for row in output["candidate_population_body"]["candidate_rows"]
        for player_id in row["player_ids"]
    })
    outcome_identity, authority = _recognized_authority(trace, players)
    selected_ids = {
        candidate_id
        for output in trace["cell_outputs"]
        for candidate_id in output["selected_book_body"]["selected_lineup_ids"]
    }
    unselected = next(
        row for output in trace["cell_outputs"]
        for row in output["candidate_population_body"]["candidate_rows"]
        if row["candidate_id"] not in selected_ids
    )
    authority.player_scores.pop((0, unselected["player_ids"][0]))
    monkeypatch.setattr(
        grade.outcomes,
        "open_recognized_outcome_authority_v1",
        lambda identity, *, read_exact, verify_live_lease: authority,
    )
    verify_live_lease = lambda **kwargs: {
        "body": authority.lease_body,
        "object_receipt": authority.lease_identity,
    }
    with pytest.raises(
        grade.PaidSourceAblationGradeV1Error,
        match="lacks realized players",
    ):
        grade.grade_paid_source_terminal_v1(
            envelope,
            read_exact=read,
            verify_live_lease=verify_live_lease,
            grade_id="odds-grade-missing-candidate-actual-v1",
            outcome_authority_identity=outcome_identity,
        )


def test_matchup_grade_decomposes_admission_and_retrieval_conversion() -> None:
    candidates = [{
        "candidate_id": f"candidate-{index:03d}",
        "player_ids": [f"candidate-{index:03d}-p{player}" for player in range(9)],
    } for index in range(100)]
    actuals = {
        player_id: 0
        for candidate in candidates
        for player_id in candidate["player_ids"]
    }
    actuals[candidates[0]["player_ids"][0]] = 250_000_000
    actuals[candidates[10]["player_ids"][0]] = 220_000_000
    actuals[candidates[20]["player_ids"][0]] = 200_000_000
    scores, candidate_pool = grade._score_population(
        candidate_rows=candidates,
        actuals=actuals,
        label="matchup-decomposition-fixture",
    )
    admission = grade._score_admission(
        admitted_ids=[row["candidate_id"] for row in candidates[10:]],
        score_by_id=scores,
        label="matchup-decomposition-fixture",
    )
    selected_book = grade._score_book(
        selected_ids=[row["candidate_id"] for row in candidates[20:]],
        score_by_id=scores,
        label="matchup-decomposition-fixture",
    )
    decomposition = grade._decomposition(
        candidate_pool=candidate_pool,
        admission=admission,
        selected_book=selected_book,
    )
    assert decomposition["candidate_pool_realized_ceiling_micro"] == 250_000_000
    assert decomposition["admitted_pool_realized_ceiling_micro"] == 220_000_000
    assert decomposition["selected_k80_weekly_max_micro"] == 200_000_000
    assert decomposition[
        "selector_regret_candidate_pool_to_selected_micro"
    ] == 50_000_000
    assert decomposition["admission_regret_micro"] == 30_000_000
    assert decomposition["retrieval_regret_within_admission_micro"] == 20_000_000
    by_threshold = {
        row["threshold"]: row for row in decomposition["thresholds"]
    }
    assert by_threshold[194]["admission_conversion"] is True
    assert by_threshold[194]["retrieval_conversion_within_admission"] is True
    assert by_threshold[210]["admission_conversion"] is True
    assert by_threshold[210]["retrieval_conversion_within_admission"] is False
    assert by_threshold[230]["admission_conversion"] is False
    assert by_threshold[230]["retrieval_conversion_within_admission"] is None

    cell = {
        "candidate_pool": candidate_pool,
        "admission": admission,
        "selected_book": selected_book,
        "k80_decomposition": decomposition,
    }
    cells = {cell_id: deepcopy(cell) for cell_id in registry.MATCHUP_CELL_ORDER}
    weekly = [{
        "slate_id": "2024-w08",
        "season": 2024,
        "week": 8,
        "cells": cells,
        "effects_by_prefix": [{
            "prefix": prefix,
            "candidate_supply_effects": grade._factor_effects(
                registry.MATCHUP_EXPERIMENT_ID,
                {
                    cell_id: candidate_pool["realized_ceiling_micro"]
                    for cell_id in cells
                },
                metric="candidate_supply",
            ),
            "selected_book_effects": grade._factor_effects(
                registry.MATCHUP_EXPERIMENT_ID,
                {
                    cell_id: grade._prefix_row(
                        value, prefix=prefix
                    )["weekly_max_micro"]
                    for cell_id, value in cells.items()
                },
                metric="selected_book",
            ),
            "selector_regret_effects": grade._factor_effects(
                registry.MATCHUP_EXPERIMENT_ID,
                {
                    cell_id: (
                        candidate_pool["realized_ceiling_micro"]
                        - grade._prefix_row(value, prefix=prefix)["weekly_max_micro"]
                    ) for cell_id, value in cells.items()
                },
                metric="selector_regret",
            ),
        } for prefix in grade.PREFIXES],
    }]
    aggregate = grade._aggregate(
        registry.MATCHUP_EXPERIMENT_ID, weekly
    )
    k80 = next(
        row for row in aggregate["prefix_results"] if row["prefix"] == 80
    )
    on_on = k80["cells"][registry.MATCHUP_CELL_ORDER[0]]
    assert on_on["admission"]["available"] is True
    assert on_on["admission"]["admission_regret_candidate_to_admitted"][
        "mean_admission_regret_points"
    ] == 30.0
    threshold_210 = next(
        row for row in on_on["thresholds"] if row["threshold"] == 210
    )
    assert threshold_210["candidate_pool_opportunity_weeks"] == 1
    assert threshold_210["admission_converted_weeks"] == 1
    assert threshold_210["retrieval_converted_weeks_within_admission"] == 0


def test_paid_source_operator_fails_closed_on_incomplete_evidence() -> None:
    panel, _ = _frozen_odds()
    with pytest.raises(
        operator.PaidSourceAblationOperatorV1Error,
        match="complete preregistered support panel",
    ):
        operator.prepare_paid_source_bundle_v1(
            experiment_id=registry.ODDS_EXPERIMENT_ID,
            panel_support=panel,
            slate_evidence=[],
            run_id="missing-slate",
            output_prefix="gs://fixture-bucket/paid-source-ablation",
            frozen_at="2026-08-30T12:00:00Z",
            world_matrix_bytes_by_sha256=_odds_matrix_authority(),
        )


def test_paid_source_operator_fails_closed_on_unbound_world_bytes() -> None:
    panel, trace = _frozen_odds()
    with pytest.raises(
        operator.PaidSourceAblationOperatorV1Error,
        match="genuine execution record",
    ):
        operator.prepare_paid_source_bundle_v1(
            experiment_id=registry.ODDS_EXPERIMENT_ID,
            panel_support=panel,
            slate_evidence=[trace],
            run_id="tampered-world",
            output_prefix="gs://fixture-bucket/paid-source-ablation",
            frozen_at="2026-08-30T12:00:00Z",
            world_matrix_bytes_by_sha256=_odds_matrix_authority(),
        )


def test_bounded_odds_runner_builds_complete_ready_bundle() -> None:
    ready, _, _, _, _ = _executed_odds_ready("bounded-odds-runner")
    assert operator.validate_ready_bundle_v1(ready) == ready
    assert ready["slate_count"] == 1
    assert any(
        row["kind"] == "odds-genuine-execution-receipt"
        for row in ready["document_manifest"]
    )


def test_bounded_odds_runner_rejects_caller_prebuilt_crossing() -> None:
    _, trace = _frozen_odds()
    census = trace["support_census_body"]
    storage, publish, read = _published_callbacks()
    with pytest.raises(
        operator.PaidSourceAblationOperatorV1Error,
        match=r"input\[0\] fields differ",
    ):
        operator.run_odds_panel_to_ready_v1(
            slate_inputs=[{
                "slate": census["slate"],
                "model_rows": [],
                "fallback_authority": census["fallback_authority_body"],
                "fallback_authority_identity": census["fallback_authority_identity"],
                "prop_authority": census["prop_authority_body"],
                "prop_authority_identity": census["prop_authority_identity"],
                "cell_outputs": trace["cell_outputs"],
            }],
            preregistered_slates=[census["slate"]],
            preregistered_panel_identity=paid_fixture._identity_for_body(
                [census["slate"]], "prebuilt-rejected-panel"
            ),
            run_id="prebuilt-rejected",
            output_prefix="gs://fixture-bucket/paid-source-ablation",
            frozen_at="2026-08-30T12:00:00Z",
            publish_execution_create_once=publish,
            read_exact=read,
        )


def test_fp_sis_runner_requires_canonical_source_v3_deep_reopener() -> None:
    with pytest.raises(
        operator.PaidSourceAblationOperatorV1Error,
        match="canonical source-v3 deep reopener",
    ):
        operator.run_fp_sis_panel_to_ready_v1(
            slate_inputs=[{} for _ in range(54)],
            run_id="no-source-v3",
            output_prefix="gs://fixture-bucket/paid-source-ablation",
            frozen_at="2026-08-30T12:00:00Z",
            world_matrix_bytes_by_sha256={},
            canonical_source_v3_reopen_by_ordinal=None,  # type: ignore[arg-type]
        )
