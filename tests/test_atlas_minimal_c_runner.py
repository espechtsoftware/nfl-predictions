"""Offline contract tests for the minimal ATLAS world-selection C runner.

These run before any cloud spend, in the spirit of the 2026-08-18 process
finding: every ATLAS grid failure and both parity launch failures were
offline-detectable contract defects. Everything here is outcome-blind.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import scripts.run_atlas_minimal_world_selection_c as runner


def test_frozen_inputs_match_their_pins():
    runner.validate_frozen_inputs()


def test_source_grid_is_the_complete_270_cell_book():
    grid = json.loads(runner.SOURCE_GRID.read_text())
    assert isinstance(grid, list) and len(grid) == 270
    cells = {(c["panel_run_id"], int(c["season"]), int(c["week"]))
             for c in grid}
    assert len(cells) == 270
    for cell in grid:
        assert cell["panel_run_id"] in runner.SOURCE_PANEL_IDS
        assert str(cell["score_artifact_uri"]).startswith("gs://")
        assert len(str(cell["score_artifact_sha256"])) == 64
        assert "lever_env" in cell
    # Five panels x 54 slates; every panel appears exactly 54 times.
    for panel in runner.SOURCE_PANEL_IDS:
        assert sum(c["panel_run_id"] == panel for c in grid) == 54


def test_recovery_cell_is_r3_2025_week1():
    panel, season, week = runner.RECOVERY_CELL
    assert panel == runner.SOURCE_PANEL_IDS[3]
    assert (season, week) == (2025, 1)


def test_expected_candidate_census_totals():
    assert sum(runner.EXPECTED_PANEL_CANDIDATES.values()) == 67951
    assert set(runner.EXPECTED_PANEL_CANDIDATES) == set(
        runner.SOURCE_PANEL_IDS)


def test_lever_env_validation_catches_drift():
    cell = {"lever_env": "N_BOOM=40,CAND_MULT=2"}
    runner._validate_lever_env(cell, {"N_BOOM": "40", "CAND_MULT": "2"})
    # Comma-containing values must not fragment (the smoke-2 defect).
    commas = {"lever_env": "ROLE_BELIEF_FEATURES=a,b,c,N_BOOM=40"}
    runner._validate_lever_env(
        commas, {"ROLE_BELIEF_FEATURES": "a,b,c", "N_BOOM": "40"})
    with pytest.raises(RuntimeError, match="acquisition record"):
        runner._validate_lever_env(
            cell, {"N_BOOM": "40", "CAND_MULT": "4"})
    with pytest.raises(RuntimeError, match="acquisition record"):
        runner._validate_lever_env(cell, {"N_BOOM": "40"})


def _synthetic_snapshot():
    rows = []
    for index in range(6):
        rows.append({
            "id": f"P{index}", "pos": "QB" if index < 2 else "WR",
            "team": f"T{index % 3}", "salary": 5000,
            "proj_tourney": 10.0 + index,
        })
    rows.append({"id": "DST_B", "pos": "DST", "team": "BBB",
                 "salary": 3000, "proj_tourney": 5.0})
    rows.append({"id": "DST_A", "pos": "DST", "team": "AAA",
                 "salary": 2800, "proj_tourney": 4.0})
    return pd.DataFrame(rows)


def test_slate_frame_preserves_artifact_order_dst_inclusive():
    # The pinned artifacts store the COMPLETE generation slate, DST rows
    # included (2026-08-18 smoke disposition); every row keeps artifact
    # order and gets a real draw index.
    snapshot = _synthetic_snapshot()
    artifact_ids = np.array(
        ["P3", "P0", "DST_B", "P5", "P1", "P2", "P4", "DST_A"])
    slate = runner._slate_frame(snapshot, artifact_ids)
    assert slate["id"].tolist() == list(artifact_ids)
    assert slate["draw_idx"].tolist() == list(range(8))


def test_slate_frame_rejects_missing_artifact_player():
    with pytest.raises(RuntimeError, match="missing from snapshot"):
        runner._slate_frame(
            _synthetic_snapshot(),
            np.array(["P0", "P1", "DST_A", "GHOST"]))


def test_slate_frame_rejects_snapshot_leftovers():
    snapshot = _synthetic_snapshot()
    with pytest.raises(RuntimeError, match="absent from the artifact"):
        # P5 left out of the artifact must fail: the artifact stores the
        # complete slate, so an unmatched snapshot row is a defect.
        runner._slate_frame(
            snapshot,
            np.array(["P3", "P0", "P1", "P2", "P4", "DST_A", "DST_B"]))


def test_slate_frame_rejects_dst_free_artifact():
    snapshot = _synthetic_snapshot().query("pos != 'DST'").copy()
    with pytest.raises(RuntimeError, match="no DST rows"):
        runner._slate_frame(
            snapshot, np.array([f"P{i}" for i in range(6)]))


def test_slate_frame_rejects_duplicate_artifact_ids():
    with pytest.raises(RuntimeError, match="ids repeat"):
        runner._slate_frame(
            _synthetic_snapshot(),
            np.array(["P0", "P0", "P1", "P2", "P3", "P4", "P5",
                      "DST_A", "DST_B"]))


class _Lineup:
    def __init__(self, ids):
        self.ids = frozenset(ids)


class _Batch:
    def __init__(self, rosters, totals):
        self.candidates = tuple(_Lineup(r) for r in rosters)
        self.candidate_totals = np.asarray(totals, dtype=float)


def _native_frame(rosters):
    return pd.DataFrame({
        "cand_ix": range(len(rosters)),
        "players": [",".join(sorted(r)) for r in rosters],
    })


def test_reproduction_check_passes_on_exact_match():
    rosters = [("a", "b"), ("c", "d")]
    totals = [[1.0, 2.0], [3.0, 4.0]]
    artifact = {"cand_ix": np.arange(2), "totals": np.asarray(totals)}
    result = runner._reproduction_check(
        _Batch(rosters, totals), _native_frame(rosters), artifact)
    assert result["generated_candidates"] == 2
    assert result["registered_candidates"] == 2
    assert result["max_total_delta"] == 0.0


def test_reproduction_check_rejects_budget_totals_and_identity_drift():
    rosters = [("a", "b"), ("c", "d")]
    totals = [[1.0, 2.0], [3.0, 4.0]]
    artifact = {"cand_ix": np.arange(2), "totals": np.asarray(totals)}
    with pytest.raises(RuntimeError, match="budget differs"):
        runner._reproduction_check(
            _Batch(rosters[:1], totals[:1]), _native_frame(rosters),
            artifact)
    with pytest.raises(RuntimeError, match="totals differ"):
        runner._reproduction_check(
            _Batch(rosters, [[1.0, 2.0], [3.0, 9.0]]),
            _native_frame(rosters), artifact)
    with pytest.raises(RuntimeError, match="does not reproduce"):
        runner._reproduction_check(
            _Batch([("a", "b"), ("c", "x")], totals),
            _native_frame(rosters), artifact)


def test_actual_parity_detects_mismatch():
    natives = pd.DataFrame({
        "players": ["a,b"], "actual_score": [30.0],
    })
    assert runner._actual_parity(
        natives, {"a": 10.0, "b": 20.0}) == 0.0
    with pytest.raises(RuntimeError, match="parity failed"):
        runner._actual_parity(natives, {"a": 10.0, "b": 20.5})


def test_generation_env_blanks_persistence_only():
    env = runner._generation_env(0, 2023, "0" * 40)
    for key in runner.BLANKED_ENV:
        assert env[key] == ""
    # The behavioural lever set must be intact (spot-check the pillars).
    assert env["N_BOOM"] == "40"
    assert env["CAND_MULT"] == "2"
    assert env["REPLAY_PROJECTION_SEED"] == "0"
    assert "ATLAS_BOOM_WORLD_RANKING" not in env


def test_output_prefix_is_immutable_run_scoped():
    assert runner.OUTPUT_PREFIX.startswith(
        "gs://nfl-predictions-503414-raw/research/")
    assert runner.RUN_ID in runner.OUTPUT_PREFIX


def test_freeze_doc_sha_constant_matches_file():
    digest = hashlib.sha256(
        Path(runner.FREEZE_DOC).read_bytes()).hexdigest()
    assert digest == runner.FREEZE_DOC_SHA256


def test_inject_role_natives_splices_by_registered_positions():
    slate = _synthetic_snapshot().copy()
    extra = pd.DataFrame([
        {"id": "P6", "pos": "RB", "team": "T0", "salary": 5000,
         "proj_tourney": 9.0},
    ])
    slate = pd.concat([slate, extra], ignore_index=True)
    slate["draw_idx"] = range(len(slate))
    n_worlds = 4
    draws = np.arange(len(slate) * n_worlds, dtype=float).reshape(
        len(slate), n_worlds)
    from nfl_dfs.backtest.engine import CandidateBatch
    from nfl_dfs.optimizer.lineup import Lineup
    records = {str(r["id"]): r for r in slate.to_dict("records")}

    def _lineup(ids, tag):
        return Lineup(players=[records[i] for i in ids], tag=tag)

    role_roster = "P0,P1,P2,P3,P4,P5,P6,DST_A,DST_B"
    regen = (_lineup(["P0", "P1"], "lev"), _lineup(["P2", "P3"], "boom"))
    regen_totals = np.ones((2, n_worlds))
    batch = CandidateBatch(
        candidates=regen, candidate_totals=regen_totals,
        player_ids=tuple(slate["id"].tolist()),
        player_rows=tuple(slate.to_dict("records")),
        row_draws=draws,
        all_tags={regen[0].ids: ("lev",), regen[1].ids: ("boom",)},
        metadata={},
    )
    natives = pd.DataFrame({
        "cand_ix": [0, 1, 2],
        "tag": ["lev", "epi", "boom"],
        "players": ["P0,P1", role_roster, "P2,P3"],
    })
    artifact = {"totals": np.stack([
        np.full(n_worlds, 10.0), np.full(n_worlds, 77.0),
        np.full(n_worlds, 30.0),
    ])}
    spliced = runner._inject_role_natives(batch, natives, slate, artifact)
    assert len(spliced.candidates) == 3
    assert spliced.candidates[1].tag == "epi"
    assert [p["id"] for p in spliced.candidates[1].players] == \
        role_roster.split(",")
    np.testing.assert_array_equal(
        spliced.candidate_totals[1], np.full(n_worlds, 77.0))
    np.testing.assert_array_equal(spliced.candidate_totals[0], np.ones(4))
    assert spliced.metadata["role_injection"]["count"] == 1
    assert spliced.metadata["role_injection"]["cand_ix"] == [1]

    # Collision with a regenerated identity fails closed.
    collide = natives.copy()
    collide.loc[1, "players"] = "P1,P0"
    with pytest.raises(RuntimeError, match="nine unique ids"):
        runner._inject_role_natives(batch, collide, slate, artifact)

    # Budget mismatch fails closed.
    short = natives.iloc[:2]
    with pytest.raises(RuntimeError, match="splice budget"):
        runner._inject_role_natives(batch, short, slate, artifact)

    # Missing role natives with a role dose fails closed.
    no_role = natives[natives.tag.ne("epi")]
    with pytest.raises(RuntimeError, match="registered no role natives"):
        runner._inject_role_natives(batch, no_role, slate, artifact)


def test_score_books_four_seed_recovery_reports_c_without_s():
    # Amendment 5: the four-seed recovery slate (r3/2025-W1 never
    # registered) reports C normally and S absent by design; any other
    # short seed count still fails via the CBWU five-seed contract.
    from nfl_dfs.backtest.engine import CandidateBatch
    from nfl_dfs.optimizer.lineup import Lineup

    def _batch(offset):
        players = [
            {"id": f"p{offset}{i}", "pos": "WR", "salary": 5000, "proj": 9.0}
            for i in range(9)
        ]
        lineup = Lineup(players=players, tag="lev")
        return CandidateBatch(
            candidates=(lineup,),
            candidate_totals=np.ones((1, 4)),
            player_ids=tuple(p["id"] for p in players),
            player_rows=tuple(players),
            row_draws=np.ones((9, 4)),
            all_tags={lineup.ids: ("lev",)},
            metadata={},
        )

    batches = {f"R{i}": _batch(i) for i in (0, 1, 2, 4)}
    actuals = {f"p{o}{i}": float(10 + o + i)
               for o in (0, 1, 2, 4) for i in range(9)}
    result = runner._score_books(batches, actuals)
    assert result["four_seed_recovery"] is True
    assert result["s_score"] is None
    best = max(
        sum(actuals[f"p{o}{i}"] for i in range(9)) for o in (0, 1, 2, 4))
    assert result["c_score"] == pytest.approx(best)
    assert "194" in result["thresholds"]
