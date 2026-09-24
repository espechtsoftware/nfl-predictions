from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest import engine
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.optimizer.lineup import Lineup
from nfl_dfs.research import boom_first_historical_construction_replay_adapter_v1 as adapter
from nfl_dfs.research import boom_first_historical_replay_adapter_v1 as predecessor
from nfl_dfs.research import corpus_r6_construction_allocation_cross_v1 as cross


def _identity(name: str) -> dict[str, object]:
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": "19",
        "sha256": hashlib.sha256(name.encode()).hexdigest(),
        "bytes": 101,
    }


def _input(*, actual: float | None = None):
    prior = {
        "season": 2024,
        "week": 1,
        "gsis_id": "prior-player",
        "name": "prior-player",
        "position": "QB",
        "team": "X",
        "opponent": "Y",
        "game_id": "X@Y",
        "salary": 6_000,
        "y_dk_points": 20.0,
        "actual": 20.0,
    }
    target = {
        "season": 2025,
        "week": 1,
        "gsis_id": "target-player",
        "name": "target-player",
        "position": "QB",
        "team": "A",
        "opponent": "B",
        "game_id": "A@B",
        "salary": 6_500,
        "y_dk_points": np.nan,
        "actual": actual,
    }
    panel = pd.DataFrame([prior, target])
    dst_prelock = pd.DataFrame([{
            "season": 2025,
            "week": 1,
            "team": "B",
            "opp": "A",
            "salary": 3_000,
            "dst_points_l4": 7.0,
            "opp_implied": 22.0,
            "opp_qb_starts": 10.0,
        }])
    market_points = pd.DataFrame([{
            "season": 2025,
            "week": 1,
            "gsis_id": "target-player",
            "market_points": 17.0,
        }])
    tabpfn_marginals = pd.DataFrame([{
            "season": 2025,
            "week": 1,
            "gsis_id": "target-player",
            "q01": 2.0,
            "q99": 35.0,
        }])
    manifest_panel = panel.copy(deep=True)
    manifest_panel.loc[manifest_panel.season == 2025, "actual"] = np.nan
    validated_panel = predecessor._validate_panel(
        manifest_panel, season=2025, expected_weeks=(1,)
    )
    dst_projected = predecessor._validate_dst_prelock(
        dst_prelock, season=2025, expected_weeks=(1,)
    )
    market = predecessor._validate_market(
        market_points, season=2025, expected_weeks=(1,)
    )
    tabpfn = predecessor._validate_tabpfn(tabpfn_marginals, season=2025)
    lock = _identity("2025-w01-lock")
    audit = _identity("2025-w01-audit")
    manifest = cross.source_manifest_v1(
        season=2025,
        week=1,
        slate_id="2025-w01",
        input_frame_receipts=adapter.source_frame_receipts_v1(
            panel=validated_panel,
            dst_projected=dst_projected,
            market_points=market,
            tabpfn_marginals=tabpfn,
        ),
        lock_identity=lock,
        audit_bank_identity=audit,
    )
    raw = cross.canonical_json_bytes(manifest)
    source = {
        "uri": "gs://fixture/2025-w01-source-manifest.json",
        "generation": "19",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    return adapter.ConstructionAllocationSeasonInputs(
        season=2025,
        panel=panel,
        dst_prelock=dst_prelock,
        market_points=market_points,
        tabpfn_marginals=tabpfn_marginals,
        source_identity_by_slate={"2025-w01": source},
        source_manifest_by_slate={"2025-w01": manifest},
        lock_identity_by_slate={"2025-w01": lock},
        audit_bank_identity_by_slate={"2025-w01": audit},
    )


def _native_frame():
    specs = (
        ("qb-a", "QB", "A", "B", "g1", 6_800),
        ("rb-a", "RB", "A", "B", "g1", 6_000),
        ("rb-c", "RB", "C", "D", "g2", 6_000),
        ("wr-a", "WR", "A", "B", "g1", 5_600),
        ("wr-b", "WR", "B", "A", "g1", 5_600),
        ("wr-c", "WR", "C", "D", "g2", 5_600),
        ("te-a", "TE", "A", "B", "g1", 4_800),
        ("wr-d", "WR", "D", "C", "g2", 5_600),
        ("dst-c", "DST", "C", "D", "g2", 3_000),
    )
    return pd.DataFrame([{
        "id": player_id,
        "name": player_id,
        "pos": position,
        "team": team,
        "opp": opponent,
        "game_id": game,
        "salary": salary,
        "proj": 20.0,
        "proj_tourney": 20.0,
        "draw_idx": index,
    } for index, (
        player_id, position, team, opponent, game, salary
    ) in enumerate(specs)])


def test_successor_accepts_score_blind_2025_but_rejects_target_outcome():
    builder = adapter.ConstructionAllocationReplayNativeBookBuilder([_input()])
    assert [row.slate_id for row in builder.cross_slates()] == ["2025-w01"]
    with pytest.raises(
        adapter.ConstructionAllocationReplayAdapterError,
        match="absent or null",
    ):
        adapter.ConstructionAllocationReplayNativeBookBuilder([
            _input(actual=1.0)
        ])


def test_successor_passes_exact_legality_only_receipt_and_environment(monkeypatch):
    builder = adapter.ConstructionAllocationReplayNativeBookBuilder([_input()])
    frame = _native_frame()
    worlds = np.ones((len(frame), 10_000), dtype=np.float32)
    replay_seed = predecessor._SeedReplay(
        slates={"2025-w01": frame},
        belief_slates={"2025-w01": frame.copy(deep=True)},
        draws=worlds,
        belief_draws=worlds.copy(),
    )
    monkeypatch.setattr(builder, "_materialize_seed", lambda *args, **kwargs: replay_seed)
    seen: dict[str, object] = {}

    def generate(slate, pool, draws, **kwargs):
        seen.update(kwargs)
        lineup = Lineup(list(pool))
        batch = engine.CandidateBatch(
            candidates=(lineup,),
            candidate_totals=np.full((1, 10_000), 9.0, dtype=np.float32),
            player_ids=tuple(slate.id.astype(str)),
            player_rows=tuple(slate.to_dict("records")),
            row_draws=np.asarray(draws, dtype=np.float32),
            all_tags={lineup.ids: ("fixture",)},
            metadata={
                "construction_preset_receipt": dict(
                    kwargs["construction_preset_receipt"]
                ),
            },
        )
        kwargs["candidate_capture"](batch)
        return [lineup]

    monkeypatch.setattr(engine, "tail_select_lineups", generate)
    cell_id = (
        f"{cross.PRESET_ORDER[1]}--{cross.ALLOCATION_BOOM_FIRST}"
    )
    environment = cross.cell_environments({"CODE_SHA": "abcdef1"})[cell_id]
    preset = cross.resolve_construction_preset(cross.PRESET_ORDER[1]).receipt()
    projection_seed, role_seed = ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs[0]
    batch = builder(
        builder.cross_slates()[0],
        cell_id,
        "R0",
        projection_seed,
        role_seed,
        environment,
        preset,
    )
    assert seen["stack"].qb_stack_min == 0
    assert seen["stack"].bring_back_min == 0
    assert seen["policy_env"]["MIN_LINEUP_SALARY"] == "0"
    assert seen["policy_env"]["MIN_GAMES"] == "1"
    assert batch.metadata["construction_preset_receipt"] == preset
    trace = batch.metadata["historical_construction_allocation_adapter"]
    assert trace["cell_id"] == cell_id
    assert trace["uses_target_slate_outcomes"] is False
    assert trace["candidate_persistence"] is False
    projection_seed, role_seed = ADOPTED_CLASSIC_POLICY.multiseed_seed_pairs[1]
    r1 = builder(
        builder.cross_slates()[0],
        cell_id,
        "R1",
        projection_seed,
        role_seed,
        environment,
        preset,
    )
    assert r1.metadata["historical_construction_allocation_adapter"][
        "seed_label"
    ] == "R1"
    drifted = dict(environment)
    drifted["N_DARKGAME"] = "11"
    with pytest.raises(
        adapter.ConstructionAllocationReplayAdapterError,
        match="policy environment differs",
    ):
        builder(
            builder.cross_slates()[0],
            cell_id,
            "R1",
            projection_seed,
            role_seed,
            drifted,
            preset,
        )
