from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_paid_source_ablation_v1 as matchup
from nfl_dfs.research import odds_prop_override_ablation_v1 as odds
from nfl_dfs.research import paid_source_ablation_registry_v1 as registry
from tests import test_corpus_r6_matchup_component_producer_v1 as fixture


def _identity_for_body(body: object, label: str) -> dict[str, object]:
    raw = registry.canonical_json_bytes(body)
    return {
        "uri": f"gs://fixture-bucket/paid-source/{label}.json",
        "generation": str(int(sha256(label.encode()).hexdigest()[:12], 16) + 1),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _identity_for_raw(raw: bytes, label: str) -> dict[str, object]:
    return {
        "uri": f"gs://fixture-bucket/paid-source/{label}.bin",
        "generation": str(int(sha256(label.encode()).hexdigest()[:12], 16) + 1),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _opaque_identity(label: str) -> dict[str, object]:
    return _identity_for_body({"fixture": label}, label)


def _rehash(value: dict[str, object], field: str) -> dict[str, object]:
    result = deepcopy(value)
    result.pop(field, None)
    result[field] = registry.canonical_sha256(result)
    return result


def _odds_support() -> dict[str, object]:
    slate = {"slate_id": "2024-w08", "season": 2024, "week": 8}
    common_lock_identity = _opaque_identity("common-lock")
    fallback = odds.build_dk_ppg_fallback_authority_v1(
        slate=slate,
        common_lock_time_utc="2024-10-27T17:00:00Z",
        common_lock_identity=common_lock_identity,
        source_snapshot_time_utc="2024-10-27T15:00:00Z",
        source_snapshot_identity=_opaque_identity("dk-source"),
        rows=[
            {"gsis_id": "p1", "dk_ppg": 12.0},
            {"gsis_id": "p2", "dk_ppg": 14.0},
            {"gsis_id": "p3", "dk_ppg": 16.0},
            {"gsis_id": "p4", "dk_ppg": 18.0},
        ],
    )
    props = odds.build_prop_snapshot_authority_v1(
        slate=slate,
        common_lock_time_utc="2024-10-27T17:00:00Z",
        common_lock_identity=common_lock_identity,
        source_snapshot_identity=_opaque_identity("odds-source"),
        rows=[
            {
                "gsis_id": "p1",
                "prop_market_points": 22.0,
                "latest_snapshot_time_utc": "2024-10-27T16:30:00Z",
            },
            {
                "gsis_id": "p2",
                "prop_market_points": 24.0,
                "latest_snapshot_time_utc": "2024-10-26T14:00:00Z",
            },
            {
                "gsis_id": "p3",
                "prop_market_points": 26.0,
                "latest_snapshot_time_utc": "2024-10-27T18:00:00Z",
            },
            {
                "gsis_id": "p5",
                "prop_market_points": 20.0,
                "latest_snapshot_time_utc": "2024-10-27T16:45:00Z",
            },
        ],
    )
    return odds.build_odds_prop_override_support_census_v1(
        slate=slate,
        model_rows=[
            {"gsis_id": "p1", "model_mean": 10.0},
            {"gsis_id": "p2", "model_mean": 13.0},
            {"gsis_id": "p3", "model_mean": 15.0},
            {"gsis_id": "p4", "model_mean": 17.0},
        ],
        fallback_authority=fallback,
        fallback_authority_identity=_identity_for_body(fallback, "dk-authority"),
        prop_authority=props,
        prop_authority_identity=_identity_for_body(props, "prop-authority"),
    )


def _candidate_rows(candidate_ids: list[str]) -> list[dict[str, object]]:
    return [{
        "candidate_id": candidate_id,
        "player_ids": [f"{candidate_id}-p{index}" for index in range(9)],
    } for candidate_id in candidate_ids]


def _odds_world_matrix_bytes() -> dict[str, bytes]:
    return {
        cell_id: f"fixture-selection-world-{ordinal}".encode()
        for ordinal, cell_id in enumerate(registry.ODDS_CELL_ORDER)
    }


def _odds_cross_outputs(
    census: dict[str, object],
    on_candidates: list[str],
    off_candidates: list[str],
) -> list[dict[str, object]]:
    population_bodies = {
        registry.ODDS_CELL_ORDER[0]: odds.build_odds_candidate_population_body_v1(
            support_census=census,
            population_cell_id=registry.ODDS_CELL_ORDER[0],
            candidate_rows=_candidate_rows(on_candidates),
            solve_failure_count=1,
            retry_count=2,
        ),
        registry.ODDS_CELL_ORDER[1]: odds.build_odds_candidate_population_body_v1(
            support_census=census,
            population_cell_id=registry.ODDS_CELL_ORDER[1],
            candidate_rows=_candidate_rows(off_candidates),
            solve_failure_count=0,
            retry_count=0,
        ),
    }
    population_identities = {
        cell_id: _identity_for_body(body, f"population-{ordinal}")
        for ordinal, (cell_id, body) in enumerate(population_bodies.items())
    }
    selection_raw = _odds_world_matrix_bytes()
    selection_bodies = {
        cell_id: odds.build_odds_selection_world_body_v1(
            support_census=census,
            selection_world_cell_id=cell_id,
            player_order_sha256=registry.canonical_sha256(
                [row["gsis_id"] for row in census["cells"][ordinal]["rows"]]
            ),
            world_count=128,
            world_matrix_sha256=sha256(selection_raw[cell_id]).hexdigest(),
            world_matrix_bytes=len(selection_raw[cell_id]),
        )
        for ordinal, cell_id in enumerate(registry.ODDS_CELL_ORDER)
    }
    selection_identities = {
        cell_id: _identity_for_body(body, f"selection-{ordinal}")
        for ordinal, (cell_id, body) in enumerate(selection_bodies.items())
    }
    selected_by_cross = (
        on_candidates[:80],
        list(reversed(on_candidates[10:90])),
        off_candidates[:80],
        list(reversed(off_candidates[:80])),
    )
    latencies = (40.0, 35.0, 10.0, 5.0)
    result: list[dict[str, object]] = []
    for ordinal, (population_cell_id, selection_cell_id) in enumerate(
        registry.ODDS_CROSS_ORDER
    ):
        candidate_ids = (
            on_candidates
            if population_cell_id == registry.ODDS_CELL_ORDER[0]
            else off_candidates
        )
        book = odds.build_odds_selected_book_body_v1(
            support_census=census,
            population_cell_id=population_cell_id,
            selection_world_cell_id=selection_cell_id,
            candidate_population_identity=population_identities[population_cell_id],
            selection_world_identity=selection_identities[selection_cell_id],
            candidate_ids=candidate_ids,
            selected_lineup_ids=selected_by_cross[ordinal],
            added_latency_ms=latencies[ordinal],
        )
        result.append({
            "population_cell_id": population_cell_id,
            "selection_world_cell_id": selection_cell_id,
            "selection_world_identity": selection_identities[selection_cell_id],
            "selection_world_body": selection_bodies[selection_cell_id],
            "candidate_population_identity": population_identities[
                population_cell_id
            ],
            "candidate_population_body": population_bodies[population_cell_id],
            "selected_book_identity": _identity_for_body(book, f"book-{ordinal}"),
            "selected_book_body": book,
        })
    return result


def test_registry_freezes_incremental_cells_not_model_only_control() -> None:
    value = registry.frozen_paid_source_ablation_registry_v1()
    assert registry.validate_paid_source_ablation_registry_v1(value) == value
    assert value["odds_experiment"]["model_weight"] == 0.45
    assert value["odds_experiment"]["market_weight"] == 0.55
    assert value["odds_experiment"]["consumer_parity_gate"] == (
        "explicit-per-row-prop-else-dk-ppg-market-vector-required-"
        "never-treat-nan-to-model-as-dk-ppg-fallback"
    )
    assert [
        cell["cell_id"] for cell in value["matchup_experiment"]["cells"]
    ] == list(registry.MATCHUP_CELL_ORDER)
    assert all(
        cell["blend_model_weight_one_is_this_control"] is False
        for cell in value["odds_experiment"]["cells"]
    )

    poisoned = deepcopy(value)
    poisoned["odds_experiment"]["model_weight"] = 1.0
    poisoned = _rehash(poisoned, "registry_sha256")
    with pytest.raises(
        registry.PaidSourceAblationRegistryV1Error,
        match="differs from the frozen incremental tests",
    ):
        registry.validate_paid_source_ablation_registry_v1(poisoned)


def test_odds_support_preserves_blend_and_traces_fallback_states() -> None:
    census = _odds_support()
    assert odds.validate_odds_prop_override_support_census_v1(census) == census
    preregistered_slates = [census["slate"]]
    panel = odds.build_odds_prop_override_panel_support_census_v1(
        [census],
        preregistered_slates=preregistered_slates,
        preregistered_panel_identity=_identity_for_body(
            preregistered_slates, "odds-preregistered-panel"
        ),
    )
    assert odds.validate_odds_prop_override_panel_support_census_v1(panel) == panel
    assert panel["slate_count"] == 1
    assert panel[
        "historical_dk_ppg_fallback_authority_gate_passed_all_slates"
    ] is True
    incomplete_panel = [
        census["slate"],
        {"slate_id": "2024-w09", "season": 2024, "week": 9},
    ]
    with pytest.raises(
        odds.OddsPropOverrideAblationV1Error,
        match="exact preregistered panel",
    ):
        odds.build_odds_prop_override_panel_support_census_v1(
            [census],
            preregistered_slates=incomplete_panel,
            preregistered_panel_identity=_identity_for_body(
                incomplete_panel, "odds-incomplete-preregistered-panel"
            ),
        )
    on, off = census["cells"]
    assert on["source_state_counts"] == {
        "model_player_count": 4,
        "input_prop_player_count": 4,
        "retained_prop_player_count": 2,
        "excluded_prop_player_count": 2,
        "missing_prop_player_count": 1,
        "stale_prop_player_count": 1,
        "post_lock_prop_player_count": 1,
        "fallback_player_count": 2,
        "physically_excluded_by_control_count": 0,
        "prop_players_outside_model_count": 1,
    }
    assert off["source_state_counts"]["fallback_player_count"] == 4
    assert off["source_state_counts"]["excluded_prop_player_count"] == 4
    assert off["source_state_counts"]["physically_excluded_by_control_count"] == 4
    assert {row["market_source"] for row in off["rows"]} == {"dk-ppg-fallback"}
    assert next(row for row in on["rows"] if row["gsis_id"] == "p1")[
        "blended_mean"
    ] == pytest.approx(0.45 * 10.0 + 0.55 * 22.0)
    stale = next(row for row in on["rows"] if row["gsis_id"] == "p2")
    assert stale["prop_status"] == "retained_stale"
    assert stale["market_source"] == "odds-api-prop"
    assert census["changed_player_mean_count"] == 2
    assert census["historical_dk_ppg_fallback_authority_gate_passed"] is True
    assert census["source_value_established"] is False

    poisoned = deepcopy(census)
    row = poisoned["cells"][0]["rows"][0]
    row["blended_mean"] = row["model_mean"]
    row["world_row_shift"] = 0.0
    poisoned["cells"][0]["rows_sha256"] = registry.canonical_sha256(
        poisoned["cells"][0]["rows"]
    )
    poisoned["cell_manifest_sha256"] = registry.canonical_sha256(
        poisoned["cells"]
    )
    poisoned = _rehash(poisoned, "support_census_sha256")
    with pytest.raises(
        odds.OddsPropOverrideAblationV1Error,
        match="preserve the 45/55 blend",
    ):
        odds.validate_odds_prop_override_support_census_v1(poisoned)


def test_odds_historical_gate_rejects_partial_dk_ppg_authority() -> None:
    census = _odds_support()
    fallback_rows = census["cells"][0]["rows"][:-1]
    assert len(fallback_rows) == 3
    # The exact support builder, not a model-only switch, fails if the DK PPG
    # fallback universe cannot cover every tested model player.
    slate = {"slate_id": "2024-w08", "season": 2024, "week": 8}
    common_lock_identity = _opaque_identity("partial-common-lock")
    fallback = odds.build_dk_ppg_fallback_authority_v1(
        slate=slate,
        common_lock_time_utc="2024-10-27T17:00:00Z",
        common_lock_identity=common_lock_identity,
        source_snapshot_time_utc="2024-10-27T15:00:00Z",
        source_snapshot_identity=_opaque_identity("partial-dk-source"),
        rows=[
            {"gsis_id": "p1", "dk_ppg": 12.0},
            {"gsis_id": "p2", "dk_ppg": 14.0},
            {"gsis_id": "p3", "dk_ppg": 16.0},
        ],
    )
    props = odds.build_prop_snapshot_authority_v1(
        slate=slate,
        common_lock_time_utc="2024-10-27T17:00:00Z",
        common_lock_identity=common_lock_identity,
        source_snapshot_identity=_opaque_identity("partial-odds-source"),
        rows=[],
    )
    with pytest.raises(
        odds.OddsPropOverrideAblationV1Error,
        match="model rows and exact DK-PPG fallback universe differ",
    ):
        odds.build_odds_prop_override_support_census_v1(
            slate=slate,
            model_rows=[
                {"gsis_id": f"p{index}", "model_mean": 10.0 + index}
                for index in range(1, 5)
            ],
            fallback_authority=fallback,
            fallback_authority_identity=_identity_for_body(
                fallback, "partial-dk-authority"
            ),
            prop_authority=props,
            prop_authority_identity=_identity_for_body(
                props, "partial-prop-authority"
            ),
        )


def test_odds_support_requires_one_exact_common_lock_identity() -> None:
    slate = {"slate_id": "2024-w08", "season": 2024, "week": 8}
    fallback = odds.build_dk_ppg_fallback_authority_v1(
        slate=slate,
        common_lock_time_utc="2024-10-27T17:00:00Z",
        common_lock_identity=_opaque_identity("fallback-common-lock"),
        source_snapshot_time_utc="2024-10-27T15:00:00Z",
        source_snapshot_identity=_opaque_identity("lock-test-dk-source"),
        rows=[{"gsis_id": "p1", "dk_ppg": 12.0}],
    )
    props = odds.build_prop_snapshot_authority_v1(
        slate=slate,
        common_lock_time_utc="2024-10-27T17:00:00Z",
        common_lock_identity=_opaque_identity("prop-common-lock"),
        source_snapshot_identity=_opaque_identity("lock-test-prop-source"),
        rows=[],
    )
    with pytest.raises(
        odds.OddsPropOverrideAblationV1Error,
        match="different common locks",
    ):
        odds.build_odds_prop_override_support_census_v1(
            slate=slate,
            model_rows=[{"gsis_id": "p1", "model_mean": 10.0}],
            fallback_authority=fallback,
            fallback_authority_identity=_identity_for_body(
                fallback, "lock-test-dk-authority"
            ),
            prop_authority=props,
            prop_authority_identity=_identity_for_body(
                props, "lock-test-prop-authority"
            ),
        )


def test_odds_prop_timestamp_at_common_lock_is_excluded() -> None:
    slate = {"slate_id": "2024-w08", "season": 2024, "week": 8}
    lock_identity = _opaque_identity("strict-common-lock")
    fallback = odds.build_dk_ppg_fallback_authority_v1(
        slate=slate,
        common_lock_time_utc="2024-10-27T17:00:00Z",
        common_lock_identity=lock_identity,
        source_snapshot_time_utc="2024-10-27T15:00:00Z",
        source_snapshot_identity=_opaque_identity("strict-dk-source"),
        rows=[{"gsis_id": "p1", "dk_ppg": 12.0}],
    )
    props = odds.build_prop_snapshot_authority_v1(
        slate=slate,
        common_lock_time_utc="2024-10-27T17:00:00Z",
        common_lock_identity=lock_identity,
        source_snapshot_identity=_opaque_identity("strict-prop-source"),
        rows=[{
            "gsis_id": "p1",
            "prop_market_points": 20.0,
            "latest_snapshot_time_utc": "2024-10-27T17:00:00Z",
        }],
    )
    census = odds.build_odds_prop_override_support_census_v1(
        slate=slate,
        model_rows=[{"gsis_id": "p1", "model_mean": 10.0}],
        fallback_authority=fallback,
        fallback_authority_identity=_identity_for_body(
            fallback, "strict-dk-authority"
        ),
        prop_authority=props,
        prop_authority_identity=_identity_for_body(
            props, "strict-prop-authority"
        ),
    )
    on_row = census["cells"][0]["rows"][0]
    assert on_row["prop_status"] == "post_lock_excluded"
    assert on_row["market_source"] == "dk-ppg-fallback"


def test_odds_dk_ppg_snapshot_at_common_lock_is_rejected() -> None:
    with pytest.raises(
        odds.OddsPropOverrideAblationV1Error,
        match="not strictly before common lock",
    ):
        odds.build_dk_ppg_fallback_authority_v1(
            slate={"slate_id": "2024-w08", "season": 2024, "week": 8},
            common_lock_time_utc="2024-10-27T17:00:00Z",
            common_lock_identity=_opaque_identity("fallback-at-lock"),
            source_snapshot_time_utc="2024-10-27T17:00:00Z",
            source_snapshot_identity=_opaque_identity("dk-at-lock"),
            rows=[{"gsis_id": "p1", "dk_ppg": 12.0}],
        )


def test_odds_population_trace_reports_candidate_and_order_turnover() -> None:
    census = _odds_support()
    on_candidates = [f"lineup-{index:03d}" for index in range(100)]
    off_candidates = [f"lineup-{index:03d}" for index in range(20, 120)]
    trace = odds.build_odds_prop_override_influence_trace_v1(
        support_census=census,
        cell_outputs=_odds_cross_outputs(census, on_candidates, off_candidates),
    )
    assert odds.validate_odds_prop_override_influence_trace_v1(trace) == trace
    assert trace["candidate_population_turnover"]["membership_turnover_count"] == 40
    assert trace["selected_book_order_turnover"][
        "operational_on_on_vs_off_off"
    ]["exact_order_equal"] is False
    assert trace["source_supply_effect"] == "not_evaluated_without_independent_grade"

    poisoned = deepcopy(trace)
    poisoned["actual_score"] = 200.0
    poisoned = _rehash(poisoned, "influence_trace_sha256")
    with pytest.raises(
        odds.OddsPropOverrideAblationV1Error,
        match="forbidden outcome field",
    ):
        odds.validate_odds_prop_override_influence_trace_v1(poisoned)

    poisoned = deepcopy(trace)
    poisoned["cell_outputs"][2]["selection_world_identity"] = _opaque_identity(
        "different-selection-on"
    )
    poisoned = _rehash(poisoned, "influence_trace_sha256")
    with pytest.raises(
        odds.OddsPropOverrideAblationV1Error,
        match="differs from its exact canonical body",
    ):
        odds.validate_odds_prop_override_influence_trace_v1(poisoned)


def test_matchup_source_view_accepts_true_enabled_missing_source() -> None:
    slices = {
        slice_kind: []
        for slice_kind in matchup.FP_SLICE_KINDS + matchup.SIS_SLICE_KINDS
    }
    retained, receipt = matchup._source_view(
        slices, fp_enabled=True, sis_enabled=True
    )
    assert retained == slices
    assert receipt["removed_row_count"] == 0


def test_matchup_k80_gate_fails_closed_below_eighty_admitted() -> None:
    candidate_ids = [f"candidate-{index:03d}" for index in range(79)]
    result = matchup._coverage_selection(
        lineup_support=[{
            "candidate_id": candidate_id,
            "qualifies_for_matchup_admission": True,
            "matchup_edge_mean": float(100 - index),
        } for index, candidate_id in enumerate(candidate_ids)],
        candidate_ids=candidate_ids,
        world_scores=np.zeros((79, 16), dtype=np.float32),
    )
    assert result["admitted_candidate_count"] == 79
    assert result["k80_feasible"] is False
    assert result["selection_status"] == "support-gate-failed"
    assert result["selected_k80_candidate_ids"] == []


def test_matchup_world_binding_rejects_opaque_unrelated_identity() -> None:
    candidate_ids = ["a", "b"]
    worlds = np.zeros((2, 4), dtype=np.float32)
    with pytest.raises(
        matchup.CorpusR6PaidSourceAblationV1Error,
        match="differs from canonical bytes",
    ):
        matchup.build_world_matrix_binding_v1(
            world_matrix_identity=_opaque_identity("unrelated-world-object"),
            candidate_ids=candidate_ids,
            world_scores=worlds,
        )


@pytest.fixture(scope="module")
def matchup_census() -> dict[str, object]:
    ordinal = 8  # 2023 Week 9: post-Week-4 FP alignment support is available.
    catalog = fixture._catalog(ordinal)
    task = fixture._candidate_rosters()[ordinal]
    candidates = source.build_accepted_candidate_artifact_v1(
        source_task_ordinal=ordinal,
        rows=task["rows"],
    )
    candidate_ids = [row["candidate_id"] for row in candidates["rows"]]
    worlds = np.empty((len(candidate_ids), 128), dtype=np.float32)
    for index in range(len(candidate_ids)):
        worlds[index] = 175.0 + (index % 11)
        worlds[index, index % worlds.shape[1]] = 195.0 + (index % 7)
    world_raw = matchup.canonical_world_matrix_bytes_v1(candidate_ids, worlds)
    world_binding = matchup.build_world_matrix_binding_v1(
        world_matrix_identity=_identity_for_raw(
            world_raw, "shared-world-matrix"
        ),
        candidate_ids=candidate_ids,
        world_scores=worlds,
    )
    upstream = fixture._upstream()
    return matchup.run_fp_sis_retrieval_support_census_v1(
        structural_catalog=catalog,
        structural_catalog_identity=_identity_for_body(catalog, "catalog-w09"),
        accepted_candidate_artifact=candidates,
        accepted_candidate_artifact_identity=_identity_for_body(
            candidates, "candidates-w09"
        ),
        upstream_source_release=upstream["release"],
        upstream_source_release_identity=upstream["release_identity"],
        upstream_pack_row_objects=upstream["pack_rows"],
        world_matrix_binding=world_binding,
        world_scores=worlds,
    )


def test_fp_sis_recomputes_four_true_missing_source_cells(
    matchup_census: dict[str, object],
) -> None:
    census = matchup_census
    assert matchup.validate_fp_sis_retrieval_support_census_v1(census) == census
    assert [cell["cell"]["cell_id"] for cell in census["cells"]] == list(
        registry.MATCHUP_CELL_ORDER
    )
    on_on, off_on, on_off, off_off = census["cells"]
    assert on_on["fantasy_points_support"]["effective_raw_row_count"] > 0
    assert on_on["sis_support"]["effective_raw_row_count"] > 0
    assert off_on["fantasy_points_support"]["effective_raw_row_count"] == 0
    assert off_on["fantasy_points_support"][
        "cell_missing_observation_status"
    ] == "disabled-physical-removal-before-components"
    assert on_off["sis_support"]["effective_raw_row_count"] == 0
    assert on_off["sis_support"]["cell_missing_observation_status"] == (
        "disabled-physical-removal-before-components"
    )
    assert off_off["fantasy_points_support"]["effective_raw_row_count"] == 0
    assert off_off["sis_support"]["effective_raw_row_count"] == 0
    assert off_off["source_view"]["slices"]["fp-route-share"] == []
    assert off_off["source_view"]["slices"]["sis-run-context"] == []
    assert on_on["source_view"]["slices"]["fp-route-share"]
    assert on_on["source_view"]["slices"]["sis-run-context"]
    for support in (
        on_on["fantasy_points_support"], on_on["sis_support"]
    ):
        assert support["slice_candidate_catalog_join_counts"] == (
            support["slice_stable_identity_counts"]
        )
    for cell in census["cells"]:
        component_support = cell["component_support"]
        assert component_support["available_component_count"] == len(
            component_support["available_component_types"]
        )
        assert component_support["missing_component_count"] == len(
            component_support["missing_component_types"]
        )
        assert "available_component_player_cell_count" in component_support
        assert set(cell["joint_component_loss_vs_on_on"]) == set(
            matchup.JOINT_FP_SIS_COMPONENTS
        )
    for cell in (off_on, on_off, off_off):
        assert all(
            row["raw_component_values"][component] is None
            for row in cell["annotation_rows"]
            if row["family"] == "receiver"
            for component in matchup.JOINT_FP_SIS_COMPONENTS
        )
        disabled = {
            source_name
            for source_name, enabled in (
                ("fantasy-points", cell["cell"]["fantasy_points_enabled"]),
                ("sis", cell["cell"]["sis_enabled"]),
            )
            if not enabled
        }
        assert all(
            isinstance(reason, str)
            and reason.startswith("source-disabled-by-ablation:")
            for row in cell["annotation_rows"]
            for component, reason in row["component_missingness_reasons"].items()
            if row["raw_component_values"][component] is None
            and matchup.SOURCE_REQUIRED_COMPONENTS.get(component, frozenset())
            & disabled
        )
    assert census["candidate_turnover_count_all_cells"] == 0
    assert census["world_matrix_turnover_count_all_cells"] == 0
    assert all(
        cell["candidate_artifact_identity"]
        == census["cells"][0]["candidate_artifact_identity"]
        for cell in census["cells"]
    )
    assert all(
        cell["world_matrix_identity"] == census["cells"][0]["world_matrix_identity"]
        for cell in census["cells"]
    )
    assert census["source_value_established"] is False
    assert census["historical_source_observation_time_status"].startswith(
        "not-measurable"
    )
    assert census["canonical_source_v3_control_reopener"] == (
        matchup.CANONICAL_SOURCE_V3_CONTROL_REOPENER
    )
    assert "never claims canonical source-v3 authority" in census[
        "remaining_integration_seam"
    ]


def test_fp_sis_records_k80_feasibility_and_order_turnover(
    matchup_census: dict[str, object],
) -> None:
    census = matchup_census
    for cell in census["cells"]:
        retrieval_row = cell["retrieval"]
        assert retrieval_row["k80_feasible"] == (
            retrieval_row["admitted_candidate_count"] >= registry.ENTRY_BUDGET
        )
        if retrieval_row["k80_feasible"]:
            assert len(retrieval_row["selected_k80_candidate_ids"]) == 80
            assert cell["selected_k80_order_turnover_vs_on_on"][
                "reference_count"
            ] == 80
        else:
            assert retrieval_row["selected_k80_candidate_ids"] == []
            assert cell["selected_k80_order_turnover_vs_on_on"]["status"] == (
                "not_evaluated_support_gate_failed"
            )
        assert "component_percentile_change_count" in cell["marginal_turnover"]
        assert "membership_turnover_count" in cell[
            "admission_order_turnover_vs_on_on"
        ]
    assert census["support_gate_status"] in {"passed", "failed"}
    assert census["conditional_fantasy_points_effect"] == (
        "not_evaluated_without_independent_grade"
    )
    assert census["additive_vendor_effect_claim_forbidden"] is True


def test_fp_sis_validator_rejects_forged_candidate_turnover(
    matchup_census: dict[str, object],
) -> None:
    poisoned = deepcopy(matchup_census)
    poisoned["cells"][1]["candidate_turnover_count"] = 1
    poisoned["cell_manifest_sha256"] = registry.canonical_sha256(
        poisoned["cells"]
    )
    poisoned = _rehash(poisoned, "slate_support_census_sha256")
    with pytest.raises(
        matchup.CorpusR6PaidSourceAblationV1Error,
        match="do not reuse exact candidate/world authority",
    ):
        matchup.validate_fp_sis_retrieval_support_census_v1(poisoned)


def test_fp_sis_validator_rejects_rehashed_nonremoved_source_view(
    matchup_census: dict[str, object],
) -> None:
    poisoned = deepcopy(matchup_census)
    on_on = poisoned["cells"][0]
    fp_off = poisoned["cells"][1]
    retained_row = deepcopy(on_on["source_view"]["slices"]["fp-route-share"][0])
    fp_off["source_view"]["slices"]["fp-route-share"] = [retained_row]
    fp_off["source_view"]["effective_slice_row_counts"]["fp-route-share"] = 1
    fp_off["source_view"]["effective_row_count"] += 1
    view = fp_off["source_view"]
    view.pop("source_view_sha256")
    view["source_view_sha256"] = registry.canonical_sha256(view)
    poisoned["cell_manifest_sha256"] = registry.canonical_sha256(
        poisoned["cells"]
    )
    poisoned = _rehash(poisoned, "slate_support_census_sha256")
    with pytest.raises(
        matchup.CorpusR6PaidSourceAblationV1Error,
        match="source-view removal receipt differs",
    ):
        matchup.validate_fp_sis_retrieval_support_census_v1(poisoned)


def test_fp_sis_validator_rejects_rehashed_unknown_authority_claim(
    matchup_census: dict[str, object],
) -> None:
    poisoned = deepcopy(matchup_census)
    poisoned["money_strategy_authority"] = True
    poisoned = _rehash(poisoned, "slate_support_census_sha256")
    with pytest.raises(
        matchup.CorpusR6PaidSourceAblationV1Error,
        match="fields differ",
    ):
        matchup.validate_fp_sis_retrieval_support_census_v1(poisoned)


def test_fp_sis_panel_gate_requires_all_54_slates(
    matchup_census: dict[str, object],
) -> None:
    with pytest.raises(
        matchup.CorpusR6PaidSourceAblationV1Error,
        match="requires exactly 54 slates",
    ):
        matchup.build_fp_sis_panel_support_census_v1([matchup_census])
