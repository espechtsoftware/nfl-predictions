"""BOOM_UNIQUE_FILL lever (N6/S5 arm): the default primary boom pass solves
exactly the top-N worlds, so duplicate optima deliver fewer than N unique
boom candidates; the lever walks further down the world order until N unique
boom rosters exist. Off-by-default must leave behavior byte-identical
(vacuity law), and the lever must actually fire on an engineered slate whose
top-ranked worlds share one optimum.
"""
import numpy as np
import pandas as pd

from nfl_dfs.backtest import engine
from nfl_dfs.inference.generation_exposure import validate_ledger


def _slate(n_worlds: int = 64, dup_top_worlds: int = 6):
    """34-player slate whose `dup_top_worlds` highest-total worlds are
    byte-identical columns (one shared boom optimum), with genuinely
    varied worlds below them."""
    pool, ix = [], 0
    for pos, n, sal in (("QB", 4, 6000), ("RB", 8, 5200), ("WR", 12, 4800),
                        ("TE", 6, 3600), ("DST", 4, 2800)):
        for k in range(n):
            pool.append({
                "id": f"{pos}{k}", "name": f"{pos}{k}", "pos": pos,
                "team": f"T{ix % 4}", "opp": f"T{(ix + 1) % 4}",
                "game_id": f"g{ix % 2}", "salary": sal + 111 * k,
                "proj": 8.0 + (k % 6), "actual": 9.0 + (k % 7),
                "season": 2025, "week": 3})
            ix += 1
    slate = pd.DataFrame(pool)
    slate["draw_idx"] = range(len(slate))
    rng = np.random.default_rng(11)
    draws = np.abs(rng.normal(9, 4.5, size=(len(pool), n_worlds)))
    # One shared high column dominates the total-points world ranking.
    spike = np.abs(rng.normal(16, 2.0, size=len(pool)))
    for w in range(dup_top_worlds):
        draws[:, w] = spike
    return slate, pool, draws


def _boom_candidates(policy_env):
    slate, pool, draws = _slate()
    captured = {}

    def capture(batch):
        captured["batch"] = batch

    lus = engine.tail_select_lineups(
        slate, pool, draws, tail_line=95.0, n_entries=4, stack=None,
        objective_col="proj", n_boom_solves=4,
        policy_env=policy_env, candidate_capture=capture)
    batch = captured["batch"]
    boom = [c for c in batch.candidates if c.tag == "boom"]
    return boom, batch, lus


def test_default_under_delivers_on_duplicate_top_worlds():
    boom, _, _ = _boom_candidates({"MIN_LINEUP_SALARY": "0"})
    # The four solved worlds include the duplicated spike columns, so
    # strictly fewer than four unique boom rosters can exist.
    assert len(boom) < 4


def test_lever_fills_to_the_full_unique_quota():
    boom, _, _ = _boom_candidates(
        {"MIN_LINEUP_SALARY": "0", "BOOM_UNIQUE_FILL": "1"})
    assert len(boom) == 4
    ids = [c.ids for c in boom]
    assert len(set(ids)) == 4


def test_off_by_default_is_byte_identical_to_zero():
    unset, _, lus_unset = _boom_candidates({"MIN_LINEUP_SALARY": "0"})
    zero, _, lus_zero = _boom_candidates(
        {"MIN_LINEUP_SALARY": "0", "BOOM_UNIQUE_FILL": "0"})
    assert [c.ids for c in unset] == [c.ids for c in zero]
    assert [lu.ids for lu in lus_unset] == [lu.ids for lu in lus_zero]


def test_exact_leverage_and_boom_requests_are_captured():
    _, batch, _ = _boom_candidates({
        "MIN_LINEUP_SALARY": "0",
        "N_LEV": "2",
        "N_BOOM": "4",
        "BOOM_UNIQUE_FILL": "0",
    })
    allocation = batch.metadata["generation_allocation"]
    assert allocation["leverage_requested"] == 2
    assert allocation["leverage_unique"] == 2
    assert allocation["leverage_successful"] == 2
    assert allocation["leverage_solver_errors"] == 0
    assert allocation["leverage_infeasible"] == 0
    assert allocation["boom_requested"] == 4
    assert allocation["boom_attempted"] == 4
    assert allocation["boom_successful"] == 4
    assert allocation["boom_solver_errors"] == 0
    assert allocation["boom_infeasible"] == 0
    assert (
        allocation["boom_unique_added"] + allocation["boom_duplicates"]
        == allocation["boom_successful"]
    )
    assert allocation["boom_failures"] == 0
    assert allocation["core_requested"] == 6
    assert allocation["boom_unique_fill"] is False
    timing = batch.metadata["generation_timing_seconds"]
    assert timing["leverage"] >= 0
    assert timing["primary_boom"] >= 0


def test_prospective_exposure_ledger_captures_every_core_attempt():
    slate, pool, draws = _slate()
    captured = []
    engine.tail_select_lineups(
        slate,
        pool,
        draws,
        tail_line=95.0,
        n_entries=2,
        stack=None,
        objective_col="proj",
        n_boom_solves=2,
        n_game_stacks=0,
        n_per_game=0,
        policy_env={
            "MIN_LINEUP_SALARY": "0",
            "N_LEV": "2",
            "N_BOOM": "2",
            "N_EPISTEMIC": "0",
            "N_QB_VARIANTS": "0",
            "N_DARKGAME": "0",
            "BOOM_UNIQUE_FILL": "0",
            "MULTISEED_SOURCE_LABEL": "R0",
            "PROSPECTIVE_GENERATION_EXPOSURE": "1",
        },
        candidate_capture=captured.append,
    )
    ledger = validate_ledger(
        captured[0].metadata["generation_exposure_ledger"]
    )

    assert ledger["expected_requests_by_family"] == {
        "boom": 2,
        "leverage": 2,
    }
    assert ledger["attempt_count"] == 4
    assert [row["family"] for row in ledger["rows"]] == [
        "leverage",
        "leverage",
        "boom",
        "boom",
    ]
    assert all(row["uses_realized_outcomes"] is False for row in ledger["rows"])
    assert all(row["duration_seconds"] >= 0.0 for row in ledger["rows"])
    assert set(ledger["duration_seconds_by_family"]) == {"boom", "leverage"}


def test_lever_changes_candidates_but_never_removes_boom_uniques():
    control, cbatch, _ = _boom_candidates({"MIN_LINEUP_SALARY": "0"})
    treatment, tbatch, _ = _boom_candidates(
        {"MIN_LINEUP_SALARY": "0", "BOOM_UNIQUE_FILL": "1"})
    # Every control boom roster must survive in the treatment pool: the
    # lever only extends the walk, it never skips an attempted world.
    treatment_all = {c.ids for c in tbatch.candidates}
    for c in control:
        assert c.ids in treatment_all
    assert len(treatment) > len(control)
