from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
import hashlib
from itertools import combinations

import numpy as np
import pytest

from nfl_dfs.backtest import engine
from nfl_dfs.inference.generation_exposure import SolveExposureLedger
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.optimizer.lineup import Lineup
from nfl_dfs.research import boom_first_historical_construction_snapshot_adapter_v1 as adapter
from nfl_dfs.research import corpus_r6_boom_first_allocation_v1 as frozen
from nfl_dfs.research import corpus_r6_construction_allocation_cross_v1 as cross


class _MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.calls: list[str] = []

    def add(self, uri: str, raw: bytes, *, generation: str = "19") -> dict[str, object]:
        self.objects[uri] = raw
        return {
            "uri": uri,
            "generation": generation,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        uri = str(identity["uri"])
        self.calls.append(uri)
        return self.objects[uri]


def _players(panel: str, season: int, week: int) -> list[dict[str, object]]:
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"]
    rows = []
    for index in range(30):
        position = positions[index % len(positions)]
        player_id = f"p{index:02d}"
        rows.append({
            "panel_run_id": panel,
            "season": season,
            "week": week,
            "id": player_id,
            "gsis_id": player_id,
            "name": player_id,
            "pos": position,
            "team": f"T{index % 6}",
            "opp": f"T{(index + 1) % 6}",
            "game_id": f"g{index % 3}",
            "salary": 3_000 + index * 100,
            "proj": 10.0 + index / 10,
            "proj_tourney": 11.0 + index / 10,
            "own_est": 0.05,
            "consensus_div": 0.0,
            "market_points": 10.0,
            "model_points_pre": 10.0,
            "mean_projection": 10.0,
            "proj_p10": 2.0,
            "proj_p50": 10.0,
            "proj_p90": 20.0,
            "proj_std": 5.0,
        })
    return rows


def _artifact_raw(
    player_ids: list[str], registered_rosters: list[list[str]],
) -> bytes:
    draws = np.empty((len(player_ids), cross.WORLDS_PER_BLOCK), dtype=np.float32)
    for index in range(len(player_ids)):
        # p08/p17/p26 are the synthetic DST rows. Match retained artifacts:
        # DST worlds are an exactly constant projection broadcast.
        draws[index] = (
            1.0 if index % 9 == 8 else float(index + 1) / 10.0
        )
    id_to_index = {player_id: index for index, player_id in enumerate(player_ids)}
    totals = np.stack([
        draws[[id_to_index[player_id] for player_id in roster]].sum(axis=0)
        for roster in registered_rosters
    ]).astype(np.float32)
    output = BytesIO()
    np.savez_compressed(
        output,
        cand_ix=np.arange(len(registered_rosters), dtype=np.int64),
        totals=totals,
        tail_line=np.asarray([cross.TAIL_LINE], dtype=np.float64),
        player_ids=np.asarray(player_ids),
        player_draws=draws,
    )
    return output.getvalue()


def _fixture() -> tuple[
    _MemoryStore,
    adapter.FrozenSnapshotBinding,
    list[tuple[str, ...]],
    list[tuple[str, ...]],
]:
    store = _MemoryStore()
    season, week, ordinal = 2023, 1, 0
    player_ids = [f"p{index:02d}" for index in range(30)]
    all_rosters = [tuple(values) for values in combinations(player_ids, 9)]
    role_rosters = [list(values) for values in all_rosters[:12]]
    core_rosters = all_rosters[12:212]
    registered_rosters = [list(values) for values in core_rosters] + role_rosters
    player_rows_by_block: dict[str, list[dict[str, object]]] = {}
    candidate_rows_by_block: dict[str, list[dict[str, object]]] = {}
    artifact_receipts: list[dict[str, object]] = []
    for block in frozen.BLOCK_ORDER:
        panel = frozen.candidate_source_panel_v1(season, week, block)
        raw = _artifact_raw(player_ids, registered_rosters)
        identity = store.add(f"gs://fixture/{block}.npz", raw)
        receipt = {
            **identity,
            "block": block,
            "panel_run_id": frozen.SOURCE_PANELS[frozen.BLOCK_ORDER.index(block)],
            "season": season,
            "week": week,
            "candidate_rows": len(registered_rosters),
        }
        artifact_receipts.append(receipt)
        player_rows_by_block[block] = _players(panel, season, week)
        candidate_rows_by_block[block] = [{
            "panel_run_id": panel,
            "season": season,
            "week": week,
            "cand_ix": index,
            "tag": (
                "lev" if index < 160
                else "boom" if index < 200
                else "epi"
            ),
            "player_ids": roster,
            "score_artifact_uri": identity["uri"],
            "score_artifact_sha256": identity["sha256"],
        } for index, roster in enumerate(registered_rosters)]
    later_identity = {
        "uri": "gs://fixture/later-source.json",
        "generation": "18",
        "sha256": "1" * 64,
        "bytes": 101,
    }
    snapshot = frozen.build_generation_snapshot_v1(
        source_ordinal=ordinal,
        later_source_identity=later_identity,
        later_source_freeze_sha256="2" * 64,
        later_slate={
            "season": season,
            "week": week,
            "slate_id": "2023-w01",
            "artifact_receipts": artifact_receipts,
        },
        player_rows_by_block=player_rows_by_block,
        candidate_rows_by_block=candidate_rows_by_block,
        query_receipts={
            "schema_version": "fixture-score-blind-query/v1",
            "target_columns": [],
        },
    )
    snapshot_raw = frozen.canonical_json_bytes_v1(snapshot)
    snapshot_identity = store.add(
        "gs://fixture/inputs/00-2023-w01.json", snapshot_raw
    )
    audit_identity = {
        "uri": "gs://fixture/audit-bank.json",
        "generation": "17",
        "sha256": "3" * 64,
        "bytes": 101,
    }
    return (
        store,
        adapter.FrozenSnapshotBinding(
            snapshot_identity=snapshot_identity,
            audit_bank_identity=audit_identity,
        ),
        role_rosters,
        core_rosters,
    )


def _fake_generator(core_rosters: list[tuple[str, ...]], seen: dict[str, object]):
    def generate(slate, pool, draws, *args, **kwargs):
        environment = dict(kwargs["policy_env"])
        seen["environment"] = environment
        seen["stack"] = kwargs["stack"]
        seen["preset"] = kwargs["construction_preset_receipt"]
        seen["preseeded"] = tuple(kwargs["preseeded_role_identities"])
        record_by_id = {str(row["id"]): row for row in pool}
        definition = (
            int(environment["N_LEV"]), int(environment["N_BOOM"])
        )
        leverage, boom = definition
        lineups = tuple(
            Lineup([record_by_id[player_id] for player_id in roster], tag=(
                "lev" if index < leverage else "boom"
            ))
            for index, roster in enumerate(core_rosters)
        )
        row_index = {
            str(player_id): index
            for index, player_id in enumerate(slate["id"].astype(str))
        }
        totals = np.stack([
            np.asarray(draws)[[
                row_index[str(player["id"])] for player in lineup.players
            ]].sum(axis=0)
            for lineup in lineups
        ])
        ledger = SolveExposureLedger(source_label=environment["MULTISEED_SOURCE_LABEL"])
        for index, lineup in enumerate(lineups[:leverage]):
            ledger.record(
                family="leverage",
                requested_ordinal=index,
                status="new",
                roster_ids=lineup.ids,
            )
        for index, lineup in enumerate(lineups[leverage:]):
            ledger.record(
                family="boom",
                requested_ordinal=index,
                world_id=index,
                status="new",
                roster_ids=lineup.ids,
            )
        batch = engine.CandidateBatch(
            candidates=lineups,
            candidate_totals=totals,
            player_ids=tuple(slate["id"].astype(str)),
            player_rows=tuple(slate.to_dict("records")),
            row_draws=np.asarray(draws),
            all_tags={
                lineup.ids: ("lev" if index < leverage else "boom",)
                for index, lineup in enumerate(lineups)
            },
            metadata={
                "construction_preset_receipt": dict(
                    kwargs["construction_preset_receipt"]
                ),
                "generation_allocation": {
                    "leverage_requested": leverage,
                    "leverage_unique": leverage,
                    "leverage_solve_attempts": leverage,
                    "leverage_solver_errors": 0,
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
                    "role_or_epistemic_requested": 0,
                    "gumbel_requested": 0,
                    "core_requested": leverage + boom,
                    "total_requested_with_replacement_families": leverage + boom,
                    "unique_candidates_after_all_families": leverage + boom,
                },
                "generation_timing_seconds": {
                    "leverage": 0.1,
                    "primary_boom": 0.2,
                    "all_generation_through_candidate_matrix": 0.3,
                },
                "generation_exposure_ledger": ledger.finalize(
                    expected_requests_by_family={
                        "leverage": leverage,
                        "boom": boom,
                    }
                ),
            },
        )
        kwargs["candidate_capture"](batch)
        return list(lineups[: cross.ENTRIES])

    return generate


def test_exact_snapshot_builder_runs_both_named_cells_and_caches_only_inputs(
    monkeypatch,
):
    store, binding, role_rosters, core_rosters = _fixture()
    builder = adapter.FrozenSnapshotConstructionNativeBookBuilder(
        [binding], read_exact=store.read_exact, require_exact_panel=False
    )
    assert [row.slate_id for row in builder.cross_slates()] == ["2023-w01"]
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        engine, "tail_select_lineups", _fake_generator(core_rosters, seen)
    )
    slate = builder.cross_slates()[0]
    projection_seed, role_seed = ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs[0]
    code_sha = "a" * 40
    cell_batches = []
    for cell_id in (
        f"{cross.PRESET_ORDER[0]}--{cross.ALLOCATION_INCUMBENT}",
        f"{cross.PRESET_ORDER[1]}--{cross.ALLOCATION_BOOM_FIRST}",
    ):
        environment = cross.cell_environments({"CODE_SHA": code_sha})[cell_id]
        preset = cross.resolve_construction_preset(
            str(cross.CELL_DEFINITION[cell_id]["construction_preset_id"])
        ).receipt()
        batch = builder(
            slate,
            cell_id,
            "R0",
            int(projection_seed),
            int(role_seed),
            environment,
            preset,
        )
        cell_batches.append(batch)
        assert batch.metadata["construction_preset_receipt"] == preset
        assert batch.metadata["role_input_mode"] == (
            "frozen-role12-candidate-identities"
        )
        role_receipt = batch.metadata["frozen_role_input_receipt"]
        assert role_receipt["requested_count"] == 12
        assert role_receipt["role_rosters_sha256"] == cross.canonical_sha256(
            role_rosters
        )
        assert batch.metadata["source_identity"] == dict(
            binding.snapshot_identity
        )
        assert batch.metadata["lock_identity"]["uri"] == (
            "gs://fixture/later-source.json"
        )
        assert batch.metadata["audit_bank_identity"] == dict(
            binding.audit_bank_identity
        )
        assert batch.metadata["generation_allocation"][
            "role_or_epistemic_requested"
        ] == 12
        _, descriptor = cross._source_document_descriptor_v1(
            slate.source_manifest,
            source_identity=slate.source_identity,
            season=slate.season,
            week=slate.week,
            slate_id=slate.slate_id,
            audit_bank_identity=slate.audit_bank_identity,
        )
        cross._native_receipt(
            batch,
            cell_id=cell_id,
            seed_label="R0",
            expected_preset=preset,
            expected_source_identity=slate.source_identity,
            expected_source_descriptor=descriptor,
            expected_audit_bank_identity=slate.audit_bank_identity,
        )
    # The snapshot is opened once at construction and the shared R0 artifact
    # once on first use. The second construction/allocation cell reuses only
    # that score-blind prepared input, never a generated CandidateBatch.
    assert store.calls.count(str(binding.snapshot_identity["uri"])) == 1
    assert store.calls.count("gs://fixture/R0.npz") == 1
    assert cell_batches[0] is not cell_batches[1]
    assert seen["environment"]["N_EPISTEMIC"] == "0"
    assert seen["environment"]["MULTISEED_SOURCE_LABEL"] == "R0"
    assert seen["preseeded"] == tuple(frozenset(row) for row in role_rosters)
    assert seen["stack"].qb_stack_min == 0
    assert seen["environment"]["N_LEV"] == "40"
    assert seen["environment"]["N_BOOM"] == "160"


def test_adapter_fails_closed_on_artifact_body_and_exact_panel_drift(monkeypatch):
    store, binding, _role_rosters, core_rosters = _fixture()
    with pytest.raises(
        adapter.ConstructionSnapshotAdapterError,
        match="exact Foundry G0 54-slate panel",
    ):
        adapter.FrozenSnapshotConstructionNativeBookBuilder(
            [binding], read_exact=store.read_exact
        )
    builder = adapter.FrozenSnapshotConstructionNativeBookBuilder(
        [binding], read_exact=store.read_exact, require_exact_panel=False
    )
    monkeypatch.setattr(
        engine, "tail_select_lineups", _fake_generator(core_rosters, {})
    )
    store.objects["gs://fixture/R0.npz"] += b"tamper"
    cell_id = f"{cross.PRESET_ORDER[0]}--{cross.ALLOCATION_INCUMBENT}"
    environment = cross.cell_environments({"CODE_SHA": "b" * 40})[cell_id]
    preset = cross.resolve_construction_preset(cross.PRESET_ORDER[0]).receipt()
    projection_seed, role_seed = ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs[0]
    with pytest.raises(
        adapter.ConstructionSnapshotAdapterError,
        match="exact bytes differ",
    ):
        builder(
            builder.cross_slates()[0],
            cell_id,
            "R0",
            int(projection_seed),
            int(role_seed),
            environment,
            preset,
        )


def test_adapter_rejects_seed_environment_and_preset_drift(monkeypatch):
    store, binding, _role_rosters, core_rosters = _fixture()
    builder = adapter.FrozenSnapshotConstructionNativeBookBuilder(
        [binding], read_exact=store.read_exact, require_exact_panel=False
    )
    monkeypatch.setattr(
        engine, "tail_select_lineups", _fake_generator(core_rosters, {})
    )
    slate = builder.cross_slates()[0]
    cell_id = f"{cross.PRESET_ORDER[1]}--{cross.ALLOCATION_BOOM_FIRST}"
    environment = cross.cell_environments({"CODE_SHA": "c" * 40})[cell_id]
    preset = cross.resolve_construction_preset(cross.PRESET_ORDER[1]).receipt()
    projection_seed, role_seed = ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs[0]
    with pytest.raises(
        adapter.ConstructionSnapshotAdapterError, match="seed identity differs"
    ):
        builder(
            slate, cell_id, "R0", int(projection_seed) + 1,
            int(role_seed), environment, preset,
        )
    drifted = dict(environment)
    drifted["N_DARKGAME"] = "11"
    with pytest.raises(
        adapter.ConstructionSnapshotAdapterError,
        match="policy environment differs",
    ):
        builder(
            slate, cell_id, "R0", int(projection_seed), int(role_seed),
            drifted, preset,
        )
    wrong_preset = dict(preset)
    wrong_preset["sha256"] = "0" * 64
    with pytest.raises(
        adapter.ConstructionSnapshotAdapterError,
        match="preset receipt differs",
    ):
        builder(
            slate, cell_id, "R0", int(projection_seed), int(role_seed),
            environment, wrong_preset,
        )
