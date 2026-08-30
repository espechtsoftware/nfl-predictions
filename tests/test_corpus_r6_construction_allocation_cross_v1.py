from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
from itertools import combinations

import numpy as np
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference.generation_exposure import SolveExposureLedger
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.optimizer.lineup import Lineup
from nfl_dfs.research import corpus_r6_construction_allocation_cross_v1 as cross
from nfl_dfs.research import corpus_r6_construction_allocation_cross_operator_v1 as operator
from nfl_dfs.research import corpus_r6_construction_allocation_grade_v1 as grade


def _identity(name: str) -> dict[str, object]:
    raw = name.encode("ascii")
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": "17",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _identity_for_raw(name: str, raw: bytes) -> dict[str, object]:
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": "17",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _outcome_fixture(
    slate_id: str,
    actuals: dict[str, float],
    *,
    name: str = "outcomes",
) -> tuple[dict[str, object], bytes]:
    document = grade.outcome_document_v1(
        slate_id=slate_id, actual_points=actuals
    )
    raw = cross.canonical_json_bytes(document)
    identity = {
        "uri": f"gs://fixture/{name}.json",
        "generation": "17",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    return identity, raw


def _source_authority():
    receipts = {
        role: {
            "sha256": hashlib.sha256(role.encode()).hexdigest(),
            "bytes": 17,
            "rows": 1,
            "columns": ["fixture"],
        }
        for role in (
            "mixed_walk_forward_panel",
            "prelock_dst_projection",
            "common_lock_market_points",
            "tabpfn_marginals",
        )
    }
    lock_document = operator.common_lock_authority_v1(
        slate_id="2023-w01",
        input_frame_receipts=receipts,
        lock_id="fixture-common-lock-v1",
    )
    lock = _identity_for_raw(
        "lock", cross.canonical_json_bytes(lock_document)
    )
    audit_document = operator.audit_bank_placeholder_v1(
        slate_id="2023-w01",
        placeholder_id="fixture-audit-placeholder-v1",
    )
    audit = _identity_for_raw(
        "audit", cross.canonical_json_bytes(audit_document)
    )
    manifest = cross.source_manifest_v1(
        season=2023,
        week=1,
        slate_id="2023-w01",
        input_frame_receipts=receipts,
        lock_identity=lock,
        audit_bank_identity=audit,
    )
    raw = cross.canonical_json_bytes(manifest)
    source = {
        "uri": "gs://fixture/source-manifest.json",
        "generation": "17",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    return source, manifest, audit


def _players() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    games = (("A", "B", "g1"), ("C", "D", "g2"))
    for left, right, game in games:
        for team, opp in ((left, right), (right, left)):
            specs = [
                (f"qb-{team}", "QB", 6_800),
                (f"rb-{team}-1", "RB", 6_000),
                (f"rb-{team}-2", "RB", 6_000),
                (f"wr-{team}-1", "WR", 5_600),
                (f"wr-{team}-2", "WR", 5_600),
                (f"wr-{team}-3", "WR", 5_600),
                (f"te-{team}", "TE", 4_800),
                (f"dst-{team}", "DST", 3_000),
            ]
            for player_id, position, salary in specs:
                rows.append({
                    "id": player_id,
                    "name": player_id,
                    "pos": position,
                    "team": team,
                    "opp": opp,
                    "game_id": game,
                    "salary": salary,
                    "proj": 20.0,
                })
    return rows


def _roster_pools(players: list[dict[str, object]]) -> dict[str, list[Lineup]]:
    by_pos = {
        position: [index for index, row in enumerate(players) if row["pos"] == position]
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    eligible = by_pos["RB"] + by_pos["WR"] + by_pos["TE"]
    pools = {preset: [] for preset in cross.PRESET_ORDER}
    catalogs = {str(row["id"]): row for row in players}
    presets = {
        preset: cross.resolve_construction_preset(preset)
        for preset in cross.PRESET_ORDER
    }
    seen: set[tuple[int, ...]] = set()
    for qb in by_pos["QB"]:
        for rbs in combinations(by_pos["RB"], 2):
            for wrs in combinations(by_pos["WR"], 3):
                for te in by_pos["TE"]:
                    used = {qb, *rbs, *wrs, te}
                    for flex in eligible:
                        if flex in used:
                            continue
                        for dst in by_pos["DST"]:
                            roster = tuple(sorted((*used, flex, dst)))
                            if roster in seen:
                                continue
                            seen.add(roster)
                            lineup = Lineup([players[index] for index in roster])
                            canonical = sorted(lineup.ids)
                            try:
                                anatomy = cross._lineup_anatomy(canonical, catalogs)
                            except cross.ConstructionAllocationCrossError:
                                continue
                            for preset_id in cross.PRESET_ORDER:
                                if cross._preset_satisfied(anatomy, presets[preset_id]):
                                    pools[preset_id].append(lineup)
                            if all(len(value) >= 280 for value in pools.values()):
                                return pools
    assert all(len(value) >= 280 for value in pools.values())
    return pools


@pytest.fixture
def compact_contract(monkeypatch):
    policy = replace(
        ADOPTED_CLASSIC_POLICY,
        multiseed_worlds_per_block=3,
    )
    monkeypatch.setattr(cross, "ADOPTED_CLASSIC_POLICY", policy)
    monkeypatch.setattr(cross, "WORLDS_PER_BLOCK", 3)
    monkeypatch.setattr(cross, "EXPECTED_SLATE_IDS", ("2023-w01",))
    return policy


def _fixture_builder(compact_contract):
    players = _players()
    pools = _roster_pools(players)
    calls: list[tuple[str, str, str, dict[str, str], dict[str, object]]] = []
    cached_ledgers: dict[tuple[str, str], dict[str, object]] = {}

    def build(slate, cell_id, seed_label, projection_seed, role_seed, env, preset):
        calls.append((slate.slate_id, cell_id, seed_label, dict(env), dict(preset)))
        definition = cross.CELL_DEFINITION[cell_id]
        preset_id = str(definition["construction_preset_id"])
        seed_index = int(seed_label[1:])
        pool = pools[preset_id]
        offset = (
            seed_index * 7
            + (13 if definition["allocation_id"] == cross.ALLOCATION_BOOM_FIRST else 0)
        ) % (len(pool) - 212)
        lineups = tuple(pool[offset:offset + 212])
        draws = np.asarray([
            [25.0 + index / 10 + world / 100 for world in range(3)]
            for index in range(len(players))
        ], dtype=np.float32)
        ordinal = {str(row["id"]): index for index, row in enumerate(players)}
        totals = np.stack([
            draws[[ordinal[str(player["id"])] for player in lineup.players]].sum(axis=0)
            for lineup in lineups
        ]).astype(np.float32)
        leverage = int(definition["leverage"])
        boom = int(definition["boom"])
        ledger_key = (cell_id, seed_label)
        retry_fixture = (
            cell_id == cross.CELL_ORDER[-1] and seed_label == "R2"
        )
        if ledger_key not in cached_ledgers:
            ledger = SolveExposureLedger(source_label=seed_label)
            for requested in range(leverage):
                if retry_fixture and requested == 0:
                    ledger.record(
                        family="leverage",
                        requested_ordinal=requested,
                        retry_ordinal=0,
                        status="error",
                    )
                ledger.record(
                    family="leverage",
                    requested_ordinal=requested,
                    retry_ordinal=(1 if retry_fixture and requested == 0 else 0),
                    status="new",
                    roster_ids=lineups[requested].ids,
                )
            for requested in range(boom):
                ledger.record(
                    family="boom",
                    requested_ordinal=requested,
                    world_id=requested % 3,
                    status="new",
                    roster_ids=lineups[leverage + requested].ids,
                )
            cached_ledgers[ledger_key] = ledger.finalize(
                expected_requests_by_family={
                    "leverage": leverage,
                    "boom": boom,
                }
            )
        allocation = {
            "leverage_requested": leverage,
            "leverage_unique": leverage,
            "leverage_solve_attempts": leverage + int(retry_fixture),
            "leverage_solver_errors": int(retry_fixture),
            "leverage_infeasible": 0,
            "leverage_successful": leverage,
            "boom_requested": boom,
            "boom_attempted": boom,
            "boom_successful": boom,
            "boom_solver_errors": 0,
            "boom_infeasible": 0,
            "boom_duplicates": 0,
            "boom_failures": 0,
            "boom_unique_added": boom,
            "boom_unique_fill": False,
            "ce_requested": 0,
            "role_or_epistemic_requested": 12,
            "gumbel_requested": 0,
            "core_requested": 200,
            "total_requested_with_replacement_families": 212,
            "unique_candidates_after_all_families": 212,
        }
        _, source_descriptor = cross._source_document_descriptor_v1(
            slate.source_manifest,
            source_identity=slate.source_identity,
            season=slate.season,
            week=slate.week,
            slate_id=slate.slate_id,
            audit_bank_identity=slate.audit_bank_identity,
        )
        return CandidateBatch(
            candidates=lineups,
            candidate_totals=totals,
            player_ids=tuple(str(row["id"]) for row in players),
            player_rows=tuple(dict(row) for row in players),
            row_draws=draws,
            all_tags={lineup.ids: ("lev", "boom") for lineup in lineups},
            metadata={
                "construction_preset_receipt": dict(preset),
                "role_input_mode": "role-player-worlds",
                "source_identity": dict(slate.source_identity),
                "source_document_internal_sha256": source_descriptor[
                    "source_document_internal_sha256"
                ],
                "source_descriptor_sha256": source_descriptor[
                    "descriptor_sha256"
                ],
                "lock_identity": dict(source_descriptor["lock_identity"]),
                "audit_bank_identity": dict(slate.audit_bank_identity),
                "audit_bank_opened_during_selection": False,
                "role_player_world_receipt": cross.role_player_world_receipt(
                    tuple(str(row["id"]) for row in players), draws
                ),
                "generation_allocation": allocation,
                "generation_timing_seconds": {
                    "leverage": 1.0,
                    "primary_boom": 2.0,
                    "all_generation_through_candidate_matrix": 3.0,
                },
                "generation_exposure_ledger": cached_ledgers[ledger_key],
            },
        )

    return build, calls, players


def _selection(compact_contract):
    builder, calls, players = _fixture_builder(compact_contract)
    source, manifest, audit = _source_authority()
    slate = cross.CrossSlate(
        2023, 1, "2023-w01", source, manifest, audit
    )
    authority = cross.CrossPanelAuthority(
        panel_id=cross.FOUNDRY_G0_PANEL_ID,
        expected_slate_ids=("2023-w01",),
        identity=dict(cross.FOUNDRY_G0_PANEL_IDENTITY),
    )
    selection = cross.build_score_blind_cross_v1(
        [slate],
        builder,
        panel_id="construction-allocation-fixture-v1",
        code_sha="a" * 40,
        image_digest="sha256:" + "b" * 64,
        panel_authority=authority,
    )
    return selection, calls, players


def _rehash_selection(value: dict[str, object]) -> dict[str, object]:
    value = deepcopy(value)
    scientific = {
        key: nested for key, nested in value.items()
        if key not in {"scientific_sha256", "execution_observations", "receipt_sha256"}
    }
    value["scientific_sha256"] = cross.canonical_sha256(scientific)
    receipt = {key: nested for key, nested in value.items() if key != "receipt_sha256"}
    value["receipt_sha256"] = cross.canonical_sha256(receipt)
    return value


def test_registry_is_exact_54_by_default():
    assert len(cross.EXPECTED_SLATE_IDS) == 54
    assert cross.EXPECTED_SLATE_IDS[0] == "2023-w01"
    assert cross.EXPECTED_SLATE_IDS[-1] == "2025-w18"
    registry = cross.registry_document(code_sha="abcdef123456")
    assert registry["slate_count"] == 54
    assert registry["foundry_g0_panel_id"] == cross.FOUNDRY_G0_PANEL_ID
    assert registry["foundry_g0_panel_identity"] == cross.FOUNDRY_G0_PANEL_IDENTITY
    assert [row["cell_id"] for row in registry["cells"]] == list(cross.CELL_ORDER)
    assert all(row["per_block_requested"]["core"] == 200 for row in registry["cells"])
    assert all(row["per_block_requested"]["role"] == 12 for row in registry["cells"])
    assert registry["worlds_per_block"] == 10_000
    assert registry["thresholds"] == [194, 200, 210, 220, 230, 240]
    assert cross.validate_registry(registry) == registry


def test_builds_exact_four_cell_same_world_cross_and_influence_trace(compact_contract):
    selection, calls, _ = _selection(compact_contract)
    assert len(calls) == 20
    assert [(row[1], row[2]) for row in calls] == [
        (cell, f"R{seed}")
        for seed in range(5)
        for cell in cross.CELL_ORDER
    ]
    for _, cell_id, _, env, preset in calls:
        definition = cross.CELL_DEFINITION[cell_id]
        assert (env["N_LEV"], env["N_BOOM"]) == (
            str(definition["leverage"]), str(definition["boom"])
        )
        assert env["N_EPISTEMIC"] == "12"
        assert env["PROSPECTIVE_GENERATION_EXPOSURE"] == "1"
        assert preset["base_preset_id"] == definition["construction_preset_id"]
    slate = selection["slates"][0]
    assert slate["same_player_worlds_all_cells"] is True
    assert slate["same_role_worlds_all_cells"] is True
    assert len(slate["pairwise_population_overlap"]) == 6
    for cell_id in cross.CELL_ORDER:
        cell = slate["cells"][cell_id]
        assert len(cell["selected_rosters"]) == 80
        assert cell["selected_rule_incidence"][
            "all_selected_satisfy_named_preset"
        ] is True
        assert len(cell["native_books"]) == 5
        assert all(
            row["exposure_ledger_summary"]["attempt_count"] >= 200
            for row in cell["native_books"]
        )
    retry_trace = slate["cells"][cross.CELL_ORDER[-1]]["native_books"][2][
        "exposure_ledger_summary"
    ]
    assert retry_trace["retry_attempt_count"] == 1
    assert retry_trace["failure_or_exhaustion_count"] == 1
    assert cross.validate_score_blind_cross_v1(selection) == selection

    forged = deepcopy(selection)
    forged["slates"][0]["cells"][cross.CELL_ORDER[0]][
        "construction_preset_receipt"
    ]["min_salary"] = 0
    forged = _rehash_selection(forged)
    with pytest.raises(
        cross.ConstructionAllocationCrossError,
        match="construction_preset_receipt|candidate/K80|cell",
    ):
        cross.validate_score_blind_cross_v1(forged)

    arbitrary = deepcopy(selection)
    first = arbitrary["slates"][0]["cells"][cross.CELL_ORDER[0]]
    replacement = next(
        index for index in range(len(first["combined_candidate_rosters"]))
        if index not in first["selected_candidate_ordinals"]
    )
    first["selected_candidate_ordinals"][0] = replacement
    first["selected_rosters"][0] = first["combined_candidate_rosters"][replacement]
    first["selected_order_sha256"] = cross.canonical_sha256(
        first["selected_rosters"]
    )
    arbitrary = _rehash_selection(arbitrary)
    with pytest.raises(
        cross.ConstructionAllocationCrossError,
        match="selector certificate",
    ):
        cross.validate_score_blind_cross_v1(arbitrary)


def test_isolated_grade_reports_exact_k80_difference_in_differences(compact_contract):
    selection, _, players = _selection(compact_contract)
    actuals = {
        str(row["id"]): 4.0 + index * 0.5
        for index, row in enumerate(players)
    }
    outcome_identity, _ = _outcome_fixture("2023-w01", actuals)
    report = grade.grade_cross_v1(
        selection,
        grade_id="construction-allocation-grade-fixture-v1",
        actual_points_by_slate={"2023-w01": actuals},
        outcome_identities={"2023-w01": outcome_identity},
    )
    weekly = report["weekly_results"][0]
    incumbent_control = f"{cross.PRESET_ORDER[0]}--{cross.ALLOCATION_INCUMBENT}"
    incumbent_boom = f"{cross.PRESET_ORDER[0]}--{cross.ALLOCATION_BOOM_FIRST}"
    legality_control = f"{cross.PRESET_ORDER[1]}--{cross.ALLOCATION_INCUMBENT}"
    legality_boom = f"{cross.PRESET_ORDER[1]}--{cross.ALLOCATION_BOOM_FIRST}"
    score = lambda cell: next(
        row for row in weekly["cells"][cell]["prefixes"] if row["prefix"] == 80
    )["weekly_max_micro"]
    expected = (
        score(legality_boom) - score(legality_control)
        - (score(incumbent_boom) - score(incumbent_control))
    )
    primary = report["primary_estimand"]["estimate"]
    assert primary["sum_micro"] == expected
    assert primary["mean_points"] == expected / 1_000_000
    assert primary["lower_95_points"] == primary["upper_95_points"]
    assert [row["prefix"] for row in report["aggregate_results"]] == [20, 40, 80]
    assert [row["season"] for row in report["season_aggregate_results"]] == [
        2023,
    ]
    for aggregate in report["aggregate_results"]:
        for cell in aggregate["cells"].values():
            assert [row["threshold"] for row in cell["thresholds"]] == [
                194, 200, 210, 220, 230, 240,
            ]
            assert cell["mean_selector_regret_points"] >= 0
    assert grade.validate_grade_v1(report) == report
    forged = deepcopy(report)
    forged_estimate = dict(forged["primary_estimand"]["estimate"])
    forged_estimate["sum_micro"] += 1
    forged["primary_estimand"]["estimate"] = forged_estimate
    forged["aggregate_results"][-1]["effects"][
        "difference_in_differences"
    ] = forged_estimate
    body = {key: value for key, value in forged.items() if key != "report_sha256"}
    forged["report_sha256"] = cross.canonical_sha256(body)
    with pytest.raises(
        grade.ConstructionAllocationGradeError,
        match="paired effect|primary difference",
    ):
        grade.validate_grade_v1(forged)


class _MemoryStore:
    def __init__(self):
        self.rows: dict[str, tuple[str, bytes]] = {}
        self.order: list[str] = []

    def prime(self, identity, raw: bytes) -> None:
        assert len(raw) == identity["bytes"]
        assert hashlib.sha256(raw).hexdigest() == identity["sha256"]
        self.rows[str(identity["uri"])] = (str(identity["generation"]), raw)

    def publish(self, uri: str, raw: bytes) -> dict[str, object]:
        if uri in self.rows:
            raise RuntimeError("create-once collision")
        generation = str(len(self.rows) + 1)
        self.rows[uri] = (generation, raw)
        self.order.append(uri)
        return {
            "uri": uri,
            "generation": generation,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "create_once": True,
        }

    def read(self, identity) -> bytes:
        generation, raw = self.rows[str(identity["uri"])]
        assert generation == str(identity["generation"])
        return raw


def test_create_once_operator_is_root_last_and_independently_reopens(
    compact_contract, monkeypatch,
):
    selection, _, players = _selection(compact_contract)
    monkeypatch.setattr(
        operator,
        "_reopen_fixed_g0_panel_v1",
        lambda selection, *, read_exact: {
            "role": "fixed-g0-panel",
            "identity": dict(cross.FOUNDRY_G0_PANEL_IDENTITY),
            "panel_id": cross.FOUNDRY_G0_PANEL_ID,
            "panel_index_sha256": cross.FOUNDRY_G0_PANEL_ID.removeprefix(
                "v12:"
            ),
            "accepted_slate_ids_sha256": cross.canonical_sha256([
                row["slate_id"] for row in selection["slates"]
            ]),
            "accepted_slate_count": len(selection["slates"]),
            "generation_exact_reopened": True,
            "schema_and_self_hash_validated": True,
        },
    )
    runtime_document = operator.runtime_build_attestation_v1(
        build_id="fixture-construction-build-v1",
        source_repository="https://github.com/fixture/nfl-predictions.git",
        requested_source_commit=selection["code_sha"],
        resolved_source_commit=selection["code_sha"],
        image_tag=(
            "us-central1-docker.pkg.dev/fixture/nfl-dfs/"
            "construction:fixture"
        ),
        image_digest=selection["image_digest"],
        provider_observed_at="2026-08-30T12:00:00Z",
    )
    runtime_raw = cross.canonical_json_bytes(runtime_document)
    runtime_identity = _identity_for_raw(
        "runtime-build-attestation", runtime_raw
    )
    execution_identity = _identity_for_raw(
        "runtime-execution-attestation", b'{"fixture":true}'
    )
    execution_authority = {
        "execution_authority_sha256": "e" * 64,
        "runtime_execution_attestation_identity": execution_identity,
    }
    execution_reopen = {
        "receipt_sha256": "f" * 64,
        "all_shards_generation_exact_reopened": True,
        "selection_replayed_from_declared_shards": True,
        "runtime_execution_provider_attestation_exact_reopened": True,
        "uses_target_slate_outcomes": False,
    }
    monkeypatch.setattr(
        operator,
        "validate_selection_execution_authority_v1",
        lambda value: dict(value),
    )
    monkeypatch.setattr(
        operator,
        "verify_selection_execution_authority_v1",
        lambda selection, *, execution_authority, read_exact: dict(
            execution_reopen
        ),
    )
    ready = operator.prepare_create_once_bundle_v1(
        selection,
        run_id="construction-allocation-fixture-v1",
        output_prefix="gs://fixture/cross",
        frozen_at="2026-08-30T12:00:00Z",
        runtime_build_attestation_identity=runtime_identity,
        execution_authority=execution_authority,
    )
    assert ready["cloud_mutation_performed"] is False
    assert operator.validate_ready_bundle_v1(ready) == ready
    store = _MemoryStore()
    _, fixture_manifest, _ = _source_authority()
    store.prime(runtime_identity, runtime_raw)
    for slate in selection["slates"]:
        store.prime(
            slate["source_identity"],
            cross.canonical_json_bytes(fixture_manifest),
        )
        lock_document = operator.common_lock_authority_v1(
            slate_id=slate["slate_id"],
            input_frame_receipts=fixture_manifest["input_frame_receipts"],
            lock_id="fixture-common-lock-v1",
        )
        store.prime(
            slate["lock_identity"],
            cross.canonical_json_bytes(lock_document),
        )
        audit_document = operator.audit_bank_placeholder_v1(
            slate_id=slate["slate_id"],
            placeholder_id="fixture-audit-placeholder-v1",
        )
        store.prime(
            slate["audit_bank_identity"],
            cross.canonical_json_bytes(audit_document),
        )
    envelope = operator.publish_create_once_bundle_v1(
        ready, publish_create_once=store.publish, read_exact=store.read
    )
    assert store.order == [ready["selection_uri"], ready["terminal_uri"]]
    reopened = operator.reopen_terminal_bundle_v1(
        envelope, read_exact=store.read
    )
    assert reopened["complete"] is True
    assert reopened["outcome_data_accessed"] is False
    assert reopened[
        "upstream_reopen_receipt"
    ]["independent_audit_evaluation_authority_available"] is False
    assert reopened["selection"] == selection
    actuals = {
        str(row["id"]): 4.0 + index * 0.5
        for index, row in enumerate(players)
    }
    outcome_identity, outcome_raw = _outcome_fixture(
        "2023-w01", actuals, name="published-outcomes"
    )
    store.prime(outcome_identity, outcome_raw)
    published_grade = grade.grade_published_cross_v1(
        envelope,
        read_exact=store.read,
        grade_id="construction-allocation-published-grade-fixture-v1",
        outcome_identities={"2023-w01": outcome_identity},
    )
    assert published_grade[
        "selection_reopened_from_create_once_terminal"
    ] is True
    assert grade.validate_published_grade_v1(published_grade) == published_grade
