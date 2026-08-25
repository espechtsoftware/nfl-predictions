from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from nfl_dfs.research import corpus_catalog_realized_grading as grading
from nfl_dfs.research import corpus_core_v1_catalog as catalog
from nfl_dfs.research import corpus_core_v1_outcome_snapshot as outcome_contract
from nfl_dfs.research.corpus_batch_evidence_contract import MICRO_DK_PER_POINT
from nfl_dfs.research.corpus_v12_import import canonical_lineup_id


def _hex(value: int) -> str:
    return f"{value:064x}"


def _identity_for(value: object, *, path: str, generation: int) -> dict[str, object]:
    raw = catalog.canonical_json_bytes(value)
    return {
        "uri": f"gs://core-v1-test/{path}",
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _dummy_identity(path: str, value: int) -> dict[str, object]:
    return {
        "uri": f"gs://core-v1-test/{path}",
        "generation": str(value + 1),
        "sha256": _hex(value + 1),
        "bytes": value + 1,
    }


def _self_hash(value: dict[str, object], field: str) -> dict[str, object]:
    retained = dict(value)
    retained[field] = catalog.canonical_sha256(retained)
    return retained


def _rosters(source_ordinal: int) -> list[list[str]]:
    common = [f"s{source_ordinal:02d}-common-{index:02d}" for index in range(8)]
    return [
        sorted([*common, f"s{source_ordinal:02d}-unique-{index:03d}"])
        for index in range(80)
    ]


def _rotated(values: list[object], offset: int) -> list[object]:
    offset %= len(values)
    return [*values[offset:], *values[:offset]]


def _source_variant(
    *,
    source_ordinal: int,
    slate: dict[str, object],
    arm_ordinal: int,
    rosters: list[list[str]],
    generation: int,
) -> tuple[dict[str, object], dict[str, object]]:
    selected = _rotated(rosters, arm_ordinal * 3)
    selected_indices = _rotated(list(range(80)), arm_ordinal * 3)
    body = {
        "schema": "corpus-legal-feasibility-variant-result/v2",
        "slate": slate,
        "profile": {
            "ordinal": arm_ordinal,
            "parameter_set_id": catalog.SOURCE_PARAMETER_SET_IDS[arm_ordinal],
            "parameter_set_sha256": _hex(100 + arm_ordinal),
        },
        "later_source_freeze_manifest_sha256": _hex(90),
        "unique_rosters": rosters,
        "selected_rosters": selected,
        "selector": {"selected_indices": selected_indices},
        "visit_rosters": rosters,
        "first_occurrence_visit_indices": list(range(80)),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    result = _self_hash(body, "result_sha256")
    identity = _identity_for(
        result,
        path=f"source/{source_ordinal:02d}/{arm_ordinal}.json",
        generation=generation,
    )
    return result, identity


def _raw_t230_book(
    *,
    source_strategy_id: str,
    budget: int,
    rank_ids: list[str],
    roster_by_id: dict[str, list[str]],
) -> dict[str, object]:
    ids = rank_ids[:budget]
    return _self_hash({
        "schema_version": "extreme-tail-retrieval-book/v1",
        "strategy_id": source_strategy_id,
        "entry_budget": budget,
        "selected_lineup_ids": ids,
        "selected_rosters": [roster_by_id[value] for value in ids],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }, "book_sha256")


def _support_book(
    *, source_strategy_id: str, budget: int, rank_ids: list[str],
) -> dict[str, object]:
    return _self_hash({
        "schema_version": "extreme-tail-support-switched-book/v1",
        "strategy_id": source_strategy_id,
        "entry_budget": budget,
        "entry_count": budget,
        "selected_lineup_ids": rank_ids[:budget],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }, "book_selection_sha256")


def _t230_result(
    *,
    source_ordinal: int,
    slate: dict[str, object],
    panel_member: dict[str, object],
    later_source_freeze_identity: dict[str, object],
    compatibility_import_sha256: str,
    candidate_provenance_sha256: str,
    reconstruction_sha256: str,
    rosters: list[list[str]],
    generation: int,
) -> dict[str, object]:
    lineup_ids = sorted(canonical_lineup_id(slate, roster) for roster in rosters)
    roster_by_id = {
        canonical_lineup_id(slate, roster): roster for roster in rosters
    }
    raw_ranks: dict[str, list[str]] = {}
    raw_books: list[dict[str, object]] = []
    registry: list[dict[str, object]] = []
    for ordinal, source_strategy_id in enumerate(
        catalog.RAW_T230_SOURCE_STRATEGY_IDS
    ):
        # Rotate the stable source-union order so each method is distinct.
        rank = _rotated(lineup_ids, 11 + ordinal * 7)
        raw_ranks[source_strategy_id] = rank
        registry.append({
            "strategy_id": source_strategy_id,
            "strategy_sha256": _hex(200 + ordinal),
        })
        raw_books.extend(
            _raw_t230_book(
                source_strategy_id=source_strategy_id,
                budget=budget,
                rank_ids=rank,
                roster_by_id=roster_by_id,
            )
            for budget in catalog.EXPECTED_BOOK_BUDGETS
        )
    suite = _self_hash({
        "schema_version": "extreme-tail-retrieval-suite/v1",
        "entry_budgets": list(catalog.EXPECTED_BOOK_BUDGETS),
        "ranking_depth": 80,
        "final_fit_is_distinct_all_block_refit": True,
        "strategy_registry": registry,
        "final_fit": {"heldout_block": None, "books": raw_books},
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }, "suite_sha256")
    selected_source = (
        "coverage-ge-230-v1"
        if source_ordinal % 2 == 0
        else "block-robust-bounded-tail-ge-210-250-v1"
    )
    support_rank = raw_ranks[selected_source]
    support_books = [
        _support_book(
            source_strategy_id=selected_source, budget=budget, rank_ids=support_rank
        )
        for budget in catalog.EXPECTED_BOOK_BUDGETS
    ]
    final_switch = _self_hash({
        "scope_kind": "final-fit",
        "heldout_block": None,
        "selected_strategy_id": selected_source,
        "selected_book_count": 3,
        "selected_books": support_books,
    }, "support_switch_scope_sha256")
    policy = _self_hash({
        "schema_version": "extreme-tail-support-switched-policy/v1",
        "entry_budgets": list(catalog.EXPECTED_BOOK_BUDGETS),
        "ranking_depth": 80,
        "final_fit": final_switch,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }, "support_switched_policy_sha256")
    result = _self_hash({
        "schema_version": "foundry-t230-slate-analysis/v1",
        "source_ordinal": source_ordinal,
        "slate_id": slate["slate_id"],
        "source_member_sha256": catalog.canonical_sha256(panel_member),
        "source_task_authority_sha256": panel_member[
            "source_task_authority_sha256"
        ],
        "input_artifact_bindings": {
            "task_acceptance_identity": panel_member["task_acceptance_identity"],
            "carrier_identity": panel_member["carrier_identity"],
            "later_source_freeze_identity": later_source_freeze_identity,
            "compatibility_import_sha256": compatibility_import_sha256,
            "candidate_provenance_sha256": candidate_provenance_sha256,
            "reconstruction_sha256": reconstruction_sha256,
            "lineup_ids_sha256": catalog.canonical_sha256(lineup_ids),
        },
        "reconstruction_receipt": {
            "reconstruction_sha256": reconstruction_sha256,
            "candidate_provenance_sha256": candidate_provenance_sha256,
        },
        "science_contract_bindings": {"support_contract_sha256": _hex(300)},
        "extreme_tail_suite": suite,
        "support_switched_policy": policy,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }, "t230_slate_result_sha256")
    return {
        "result": result,
        "result_identity": _identity_for(
            result,
            path=f"t230/{source_ordinal:02d}.json",
            generation=generation,
        ),
    }


def _build_catalog_inputs() -> dict[str, object]:
    source_inputs: list[dict[str, object]] = []
    t230_results: list[dict[str, object]] = []
    later_source_freeze_identity = _dummy_identity("freeze.json", 90)
    for source_ordinal in range(54):
        season = 2019 + source_ordinal // 9
        week = 1 + source_ordinal % 9
        slate = {
            "season": season,
            "week": week,
            "slate_id": f"s{season}-w{week:02d}",
        }
        rosters = _rosters(source_ordinal)
        retained_variants: list[dict[str, object]] = []
        panel_arms: list[dict[str, object]] = []
        for arm_ordinal in range(7):
            result, identity = _source_variant(
                source_ordinal=source_ordinal,
                slate=slate,
                arm_ordinal=arm_ordinal,
                rosters=rosters,
                generation=10_000 + source_ordinal * 10 + arm_ordinal,
            )
            retained_variants.append({"result": result, "result_identity": identity})
            panel_arms.append({
                "arm_ordinal": arm_ordinal,
                "parameter_set_id": catalog.SOURCE_PARAMETER_SET_IDS[arm_ordinal],
                "result_identity": identity,
            })
        panel_member = {
            "slate_id": slate["slate_id"],
            "lane_ordinal": 0 if source_ordinal < 28 else 1,
            "lane_id": "v12a" if source_ordinal < 28 else "v12b",
            "task_ordinal": source_ordinal if source_ordinal < 28 else source_ordinal - 28,
            "source_task_ordinal": source_ordinal,
            "source_task_authority_sha256": _hex(1_000 + source_ordinal),
            "task_acceptance_identity": _dummy_identity(
                f"accept/{source_ordinal:02d}.json", 2_000 + source_ordinal
            ),
            "carrier_identity": _dummy_identity(
                f"carrier/{source_ordinal:02d}.json", 3_000 + source_ordinal
            ),
            "arms": panel_arms,
        }
        compatibility_sha = _hex(4_000 + source_ordinal)
        provenance_sha = _hex(5_000 + source_ordinal)
        reconstruction_sha = _hex(6_000 + source_ordinal)
        source_inputs.append({
            "source_ordinal": source_ordinal,
            "panel_member": panel_member,
            "later_source_freeze_identity": later_source_freeze_identity,
            "compatibility_import_sha256": compatibility_sha,
            "candidate_provenance_sha256": provenance_sha,
            "reconstruction_sha256": reconstruction_sha,
            "variant_results": retained_variants,
        })
        t230_results.append(_t230_result(
            source_ordinal=source_ordinal,
            slate=slate,
            panel_member=panel_member,
            later_source_freeze_identity=later_source_freeze_identity,
            compatibility_import_sha256=compatibility_sha,
            candidate_provenance_sha256=provenance_sha,
            reconstruction_sha256=reconstruction_sha,
            rosters=rosters,
            generation=20_000 + source_ordinal,
        ))
    panel_members = [row["panel_member"] for row in source_inputs]
    source_panel = _self_hash({
        "schema_version": "foundry-v12-combined-panel-index/v1",
        "accepted_slate_count": 54,
        "accepted_slates": panel_members,
        "exclusions": [],
        "failures": [],
        "missing_tasks": [],
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
        "analytical_authority": False,
        "promotion_authority": False,
        "decision_authority": False,
    }, "panel_index_sha256")
    source_panel_identity = _identity_for(
        source_panel, path="panel.json", generation=60_000
    )
    release_rows = [{
        "source_ordinal": source_ordinal,
        "slate_id": panel_members[source_ordinal]["slate_id"],
        "source_member_sha256": catalog.canonical_sha256(
            panel_members[source_ordinal]
        ),
        "result_identity": t230_results[source_ordinal]["result_identity"],
        "t230_slate_result_sha256": t230_results[source_ordinal]["result"][
            "t230_slate_result_sha256"
        ],
    } for source_ordinal in range(54)]
    result_identities = [row["result_identity"] for row in t230_results]
    t230_release = _self_hash({
        "schema_version": "foundry-t230-panel-release/v1",
        "panel_object_identity": source_panel_identity,
        "panel_index_sha256": source_panel["panel_index_sha256"],
        "source_member_count": 54,
        "accepted_slate_count": 54,
        "ordered_slate_acceptances": release_rows,
        "ordered_slate_acceptances_sha256": catalog.canonical_sha256(release_rows),
        "ordered_result_identities_sha256": catalog.canonical_sha256(
            result_identities
        ),
        "verification": {
            "all_54_result_identities_replayed": True,
            "all_source_ordinals_complete_and_ordered": True,
            "finalizer_science_recomputation_performed": False,
            "realized_outcomes_read": False,
        },
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
        "analytical_authority": False,
        "promotion_authority": False,
        "decision_authority": False,
    }, "t230_panel_release_sha256")
    t230_release_identity = _identity_for(
        t230_release, path="t230-release.json", generation=60_001
    )
    return {
        "source_panel": source_panel,
        "source_panel_identity": source_panel_identity,
        "t230_panel_release": t230_release,
        "t230_panel_release_identity": t230_release_identity,
        "source_slates": source_inputs,
        "t230_results": t230_results,
    }


def _outcome_artifacts(
    core_catalog: dict[str, object],
    core_identity: dict[str, object],
) -> tuple[
    tuple[outcome_contract.CoreOutcomeKey, ...],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    outcome_keys: list[outcome_contract.CoreOutcomeKey] = []
    score_by_key: dict[tuple[int, str], int] = {}
    for slate_row in core_catalog["slates"]:
        source_ordinal = int(slate_row["source_ordinal"])
        slate = slate_row["slate"]
        players = sorted({
            player
            for roster in slate_row["union_population"]["rosters"]
            for player in roster
        })
        for player in players:
            if "-common-" in player:
                score = MICRO_DK_PER_POINT
            else:
                unique_index = int(player.rsplit("-", 1)[1])
                score = (170 + unique_index) * MICRO_DK_PER_POINT
            source_kind = "dst" if player.endswith("common-00") else "skill"
            outcome_keys.append(outcome_contract.CoreOutcomeKey(
                source_ordinal=source_ordinal,
                season=int(slate["season"]),
                week=int(slate["week"]),
                slate_id=str(slate["slate_id"]),
                player_id=player,
                source_kind=source_kind,
                source_key=f"D{source_ordinal:02d}" if source_kind == "dst" else player,
            ))
            score_by_key[(source_ordinal, player)] = score
    retained_keys = tuple(sorted(
        outcome_keys, key=lambda row: (row.source_ordinal, row.player_id)
    ))
    source_rows = [{
        "source_ordinal": row.source_ordinal,
        "season": row.season,
        "week": row.week,
        "slate_id": row.slate_id,
        "source_kind": row.source_kind,
        "source_key": row.source_key,
        "player_id": row.player_id,
        "realized_score_micro": score_by_key[(row.source_ordinal, row.player_id)],
    } for row in sorted(
        retained_keys,
        key=lambda row: (row.season, row.week, row.source_kind, row.source_key),
    )]
    outcome_key_payload = [{
        "source_ordinal": row.source_ordinal,
        "season": row.season,
        "week": row.week,
        "slate_id": row.slate_id,
        "source_kind": row.source_kind,
        "source_key": row.source_key,
        "player_id": row.player_id,
    } for row in retained_keys]
    query_job_id = "core_v1_fast_score_fixture"
    source_snapshot_at = "2026-08-25T00:00:00+00:00"
    source_body = {
        "schema_version": outcome_contract.PLAYER_SOURCE_SCHEMA,
        "catalog_sha256": core_catalog["catalog_sha256"],
        "later_source_freeze_identity": core_catalog[
            "later_source_freeze_identity"
        ],
        "later_source_freeze_sha256": core_catalog[
            "later_source_freeze_sha256"
        ],
        "outcome_key_count": len(retained_keys),
        "outcome_keys_sha256": outcome_contract.canonical_sha256(
            outcome_key_payload
        ),
        "query_contract_sha256": outcome_contract.core_query_contract_sha256(
            outcome_keys=retained_keys,
            query_job_id=query_job_id,
            source_snapshot_at=source_snapshot_at,
        ),
        "query_job_id": query_job_id,
        "source_snapshot_at": source_snapshot_at,
        "table_receipt_set_sha256": _hex(50_001),
        "historical_outcome_lease_sha256": _hex(50_002),
        "row_fields": [
            "source_ordinal",
            "season",
            "week",
            "slate_id",
            "source_kind",
            "source_key",
            "player_id",
            "realized_score_micro",
        ],
        "row_count": len(source_rows),
        "rows_sha256": outcome_contract.canonical_sha256(source_rows),
        "rows": source_rows,
        "one_exact_query": True,
        "query_cache_used": False,
        "table_metadata_stable_during_query": True,
        "historical_outcome_lease_unchanged_during_query": True,
        "full_field_standings_included": False,
        "payout_ladder_included": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    player_source = _self_hash(source_body, "source_sha256")
    player_source_identity = _identity_for(
        player_source, path="outcomes/source.json", generation=60_003
    )
    snapshot = outcome_contract.build_core_outcome_snapshot(
        catalog=core_catalog,
        catalog_identity=core_identity,
        player_source=player_source,
        player_source_identity=player_source_identity,
        outcome_keys=retained_keys,
    )
    snapshot_identity = _identity_for(
        snapshot, path="outcomes/snapshot.json", generation=60_004
    )
    return (
        retained_keys,
        player_source,
        player_source_identity,
        snapshot,
        snapshot_identity,
    )


@pytest.fixture(scope="module")
def frozen_core() -> tuple[
    dict[str, object],
    dict[str, object],
    tuple[outcome_contract.CoreOutcomeKey, ...],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    catalog_inputs = _build_catalog_inputs()
    core = catalog.build_core_v1_catalog(
        catalog_id="core-score-batch-v1-test",
        **catalog_inputs,
    )
    core_identity = _identity_for(core, path="core/catalog.json", generation=60_002)
    outcome_keys, player_source, player_source_identity, outcomes, outcome_identity = (
        _outcome_artifacts(core, core_identity)
    )
    return (
        core,
        core_identity,
        outcome_keys,
        player_source,
        player_source_identity,
        outcomes,
        outcome_identity,
    )


def test_catalog_freezes_exact_12_by_3_by_54_lattice_and_contrasts(
    frozen_core,
) -> None:
    core, *_ = frozen_core

    assert core["strategy_count"] == 12
    assert core["source_slate_count"] == 54
    assert core["book_cell_count"] == 12 * 3 * 54 == 1_944
    assert core["contrast_count"] == 45
    assert core["contrast_cell_count"] == 45 * 3 * 54 == 7_290
    assert core["later_source_freeze_sha256"] == _hex(90)
    assert len(core["slates"][0]["union_population"]["rosters"]) == 80
    assert [row["strategy_id"] for row in core["strategy_registry"]] == list(
        catalog.STRATEGY_IDS
    )
    first = core["slates"][0]
    by_key = {
        (row["strategy_id"], row["entry_budget"]): row for row in first["books"]
    }
    for strategy_id in catalog.STRATEGY_IDS:
        exact80 = by_key[(strategy_id, 80)]["selected_lineup_ids"]
        assert by_key[(strategy_id, 4)]["selected_lineup_ids"] == exact80[:4]
        assert by_key[(strategy_id, 14)]["selected_lineup_ids"] == exact80[:14]
    assert first["support_switch_selected_source_strategy_id"] == (
        "coverage-ge-230-v1"
    )
    assert core["slates"][1]["support_switch_selected_source_strategy_id"] == (
        "block-robust-bounded-tail-ge-210-250-v1"
    )


def test_catalog_builder_rejects_rehashed_release_result_identity_swap() -> None:
    inputs = _build_catalog_inputs()
    forged_release = deepcopy(inputs["t230_panel_release"])
    first = forged_release["ordered_slate_acceptances"][0]
    second = forged_release["ordered_slate_acceptances"][1]
    first["result_identity"], second["result_identity"] = (
        second["result_identity"],
        first["result_identity"],
    )
    forged_release["ordered_slate_acceptances_sha256"] = (
        catalog.canonical_sha256(forged_release["ordered_slate_acceptances"])
    )
    forged_release.pop("t230_panel_release_sha256")
    forged_release = _self_hash(
        forged_release, "t230_panel_release_sha256"
    )
    inputs["t230_panel_release"] = forged_release
    inputs["t230_panel_release_identity"] = _identity_for(
        forged_release, path="forged-release.json", generation=70_000
    )

    with pytest.raises(
        catalog.CorpusCoreV1CatalogError,
        match="ordered result/member binding differs",
    ):
        catalog.build_core_v1_catalog(
            catalog_id="core-score-batch-v1-forged-release", **inputs
        )


def test_generic_grader_scores_each_union_roster_once_and_uses_exact_rationals(
    frozen_core,
) -> None:
    (
        core,
        core_identity,
        outcome_keys,
        player_source,
        player_source_identity,
        outcomes,
        outcome_identity,
    ) = frozen_core
    grade = grading.grade_core_v1_catalog(
        catalog=core,
        catalog_identity=core_identity,
        outcome_snapshot=outcomes,
        outcome_snapshot_identity=outcome_identity,
        player_source=player_source,
        player_source_identity=player_source_identity,
        outcome_keys=outcome_keys,
    )

    coverage = grade["coverage"]
    assert coverage["book_cell_count"] == 1_944
    assert coverage["weekly_contrast_cell_count"] == 7_290
    assert coverage["contrast_summary_count"] == 135
    assert coverage["unique_union_roster_membership_count"] == 54 * 80
    assert coverage["union_roster_sum_operation_count"] == 54 * 80
    assert coverage["every_unique_union_roster_scored_exactly_once_per_slate"]
    slate = grade["slate_grades"][0]
    assert slate["union_metrics"]["maximum_micro"] == 257 * MICRO_DK_PER_POINT
    threshold = {
        row["threshold_dk"]: row for row in slate["union_metrics"]["thresholds"]
    }
    assert threshold[200]["at_or_above_count"] == 58
    assert threshold[230]["at_or_above_count"] == 28
    assert threshold[250]["at_or_above_count"] == 8
    assert len(slate["union_metrics"]["tail_subsets"]["ge_200"]["lineup_ids"]) == 58
    incumbent4 = next(
        row for row in slate["book_grades"]
        if row["strategy_id"] == "r194:incumbent" and row["entry_budget"] == 4
    )
    assert incumbent4["maximum_micro"] == 181 * MICRO_DK_PER_POINT
    assert incumbent4["mean"] == {
        "numerator": 718 * MICRO_DK_PER_POINT,
        "denominator": 4,
        "unit": "micro_dk",
    }
    assert incumbent4["median"] == {
        "numerator": 359 * MICRO_DK_PER_POINT,
        "denominator": 2,
        "unit": "micro_dk",
    }
    assert incumbent4["top_three_mean"]["denominator"] == 3
    assert incumbent4["independent_score_map_projection_replayed"] is True
    # Every registered row is retained even when the challenger loses.
    assert any(
        row["weekly_maximum_delta_micro"] < 0
        for row in grade["weekly_contrasts"]
    )
    assert grade["contest_metrics"]["availability"] == "unavailable"
    assert grade["decision_authority"] is False


def test_grader_rejects_outcome_snapshot_missing_one_required_player(
    frozen_core,
) -> None:
    (
        core,
        core_identity,
        outcome_keys,
        player_source,
        player_source_identity,
        outcomes,
        _,
    ) = frozen_core
    forged = deepcopy(outcomes)
    forged["rows"] = forged["rows"][:-1]
    forged["row_count"] = len(forged["rows"])
    key_rows = [
        {key: row[key] for key in (
            "source_ordinal", "season", "week", "slate_id", "player_id"
        )}
        for row in forged["rows"]
    ]
    forged["row_keys_sha256"] = grading.canonical_sha256(key_rows)
    forged["rows_sha256"] = grading.canonical_sha256(forged["rows"])
    forged.pop("outcome_snapshot_sha256")
    forged = _self_hash(forged, "outcome_snapshot_sha256")
    forged_identity = _identity_for(
        forged, path="outcomes/forged.json", generation=70_001
    )
    with pytest.raises(
        grading.CorpusCatalogRealizedGradingError,
        match="outcome snapshot law differs",
    ):
        grading.grade_core_v1_catalog(
            catalog=core,
            catalog_identity=core_identity,
            outcome_snapshot=forged,
            outcome_snapshot_identity=forged_identity,
            player_source=player_source,
            player_source_identity=player_source_identity,
            outcome_keys=outcome_keys,
        )


def test_grader_rejects_outcome_snapshot_with_one_extra_player(
    frozen_core,
) -> None:
    (
        core,
        core_identity,
        outcome_keys,
        player_source,
        player_source_identity,
        outcomes,
        _,
    ) = frozen_core
    forged = deepcopy(outcomes)
    first = forged["rows"][0]
    forged["rows"].append({
        **first,
        "player_id": "s00-player-not-in-the-core-union",
        "realized_score_micro": 0,
    })
    forged["rows"].sort(
        key=lambda row: (row["source_ordinal"], row["player_id"])
    )
    forged["row_count"] = len(forged["rows"])
    key_rows = [
        {key: row[key] for key in (
            "source_ordinal", "season", "week", "slate_id", "player_id"
        )}
        for row in forged["rows"]
    ]
    forged["row_keys_sha256"] = grading.canonical_sha256(key_rows)
    forged["rows_sha256"] = grading.canonical_sha256(forged["rows"])
    forged.pop("outcome_snapshot_sha256")
    forged = _self_hash(forged, "outcome_snapshot_sha256")
    forged_identity = _identity_for(
        forged, path="outcomes/extra.json", generation=70_002
    )
    with pytest.raises(
        grading.CorpusCatalogRealizedGradingError,
        match="outcome snapshot law differs",
    ):
        grading.grade_core_v1_catalog(
            catalog=core,
            catalog_identity=core_identity,
            outcome_snapshot=forged,
            outcome_snapshot_identity=forged_identity,
            player_source=player_source,
            player_source_identity=player_source_identity,
            outcome_keys=outcome_keys,
        )


def test_grader_rejects_rehashed_score_forgery_not_present_in_player_source(
    frozen_core,
) -> None:
    (
        core,
        core_identity,
        outcome_keys,
        player_source,
        player_source_identity,
        outcomes,
        _,
    ) = frozen_core
    forged = deepcopy(outcomes)
    forged["rows"][0]["realized_score_micro"] += MICRO_DK_PER_POINT
    forged["rows_sha256"] = grading.canonical_sha256(forged["rows"])
    forged.pop("outcome_snapshot_sha256")
    forged = _self_hash(forged, "outcome_snapshot_sha256")
    forged_identity = _identity_for(
        forged, path="outcomes/forged-score.json", generation=70_003
    )

    with pytest.raises(
        grading.CorpusCatalogRealizedGradingError,
        match="outcome snapshot law differs",
    ):
        grading.grade_core_v1_catalog(
            catalog=core,
            catalog_identity=core_identity,
            outcome_snapshot=forged,
            outcome_snapshot_identity=forged_identity,
            player_source=player_source,
            player_source_identity=player_source_identity,
            outcome_keys=outcome_keys,
        )


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("later_source_freeze_sha256", _hex(91)),
        (
            "later_source_freeze_identity",
            _dummy_identity("different-freeze.json", 91),
        ),
    ],
)
def test_catalog_validator_rejects_root_slate_source_freeze_drift(
    frozen_core, field: str, replacement: object,
) -> None:
    core, *_ = frozen_core
    forged = deepcopy(core)
    slate = forged["slates"][0]
    slate["source_authority"][field] = replacement
    slate.pop("slate_catalog_sha256")
    forged["slates"][0] = _self_hash(slate, "slate_catalog_sha256")
    forged["slate_catalog_set_sha256"] = catalog.canonical_sha256([
        row["slate_catalog_sha256"] for row in forged["slates"]
    ])
    forged.pop("catalog_sha256")
    forged = _self_hash(forged, "catalog_sha256")

    with pytest.raises(
        catalog.CorpusCoreV1CatalogError,
        match="differs from catalog root",
    ):
        catalog.validate_core_v1_catalog(forged)


def test_grader_rejects_contest_rank_roi_without_field_contract(frozen_core) -> None:
    (
        core,
        core_identity,
        outcome_keys,
        player_source,
        player_source_identity,
        outcomes,
        outcome_identity,
    ) = frozen_core
    with pytest.raises(
        grading.CorpusCatalogRealizedGradingError,
        match="contest rank/ROI",
    ):
        grading.grade_core_v1_catalog(
            catalog=core,
            catalog_identity=core_identity,
            outcome_snapshot=outcomes,
            outcome_snapshot_identity=outcome_identity,
            player_source=player_source,
            player_source_identity=player_source_identity,
            outcome_keys=outcome_keys,
            contest_outcomes={},
        )
