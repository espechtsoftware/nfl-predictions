"""Shared research infrastructure (plan §3.5/§4.1/§4.2/§4.3): run
context, candidate schemas, shipping-defaults manifest, dependence
suite. All synthetic/offline — no GCP.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research import config_manifest, dependence, schemas
from nfl_dfs.research.run_context import (
    DEFAULT_RNG_STREAMS,
    RunContext,
    stable_hash,
    stream_seed,
)


# ---------------------------------------------------------------- 4.1

def test_run_context_identity_and_bq_row():
    ctx = RunContext.new(
        "replay", config={"OWN_MODEL": "", "PUNT_BOOM": 0},
        seed=42, season=2025, week=1, n_sims=10_000, n_entries=40,
        tail_threshold=237.0,
    )
    assert len(ctx.run_id) == 32
    assert ctx.run_type == "replay"
    # repo tests run inside git — a real 40-hex SHA (or the declared
    # fallback if git ever disappears from the environment).
    assert ctx.code_sha == "unknown" or len(ctx.code_sha) == 40
    assert ctx.started_at and ctx.status == "running"

    row = ctx.to_bq_row()
    json.dumps(row)  # every value BQ/JSON-safe
    assert row["run_id"] == ctx.run_id
    assert isinstance(row["model_versions"], str)
    assert json.loads(row["rng_stream_seeds"]) == ctx.rng_stream_seeds

    ctx.complete()
    assert ctx.status == "complete" and ctx.completed_at

    ctx2 = RunContext.new("replay").fail("boom")
    assert ctx2.status == "failed" and ctx2.failure_reason == "boom"


def test_run_context_rejects_unknown_type():
    with pytest.raises(ValueError):
        RunContext.new("vibes")


def test_config_hash_order_insensitive():
    a = RunContext.new("replay", config={"a": 1, "b": 2})
    b = RunContext.new("replay", config={"b": 2, "a": 1})
    assert a.config_hash == b.config_hash
    assert a.run_id != b.run_id
    assert stable_hash({"x": 1}) != stable_hash({"x": 2})


def test_named_rng_streams_deterministic_and_independent():
    a = RunContext.new("replay", seed=7)
    b = RunContext.new("live_build", seed=7)
    assert a.rng_stream_seeds == b.rng_stream_seeds  # seed-determined
    assert set(a.rng_stream_seeds) == set(DEFAULT_RNG_STREAMS)
    # distinct streams, distinct seeds; a new name never renumbers old
    assert len(set(a.rng_stream_seeds.values())) == len(DEFAULT_RNG_STREAMS)
    assert stream_seed(7, "targets") == a.rng_stream_seeds["targets"]
    assert stream_seed(7, "targets") != stream_seed(8, "targets")
    # generators reproduce and streams differ
    assert np.allclose(a.rng("targets").normal(size=3),
                       b.rng("targets").normal(size=3))
    assert not np.allclose(a.rng("targets").normal(size=3),
                           a.rng("carries").normal(size=3))
    with pytest.raises(KeyError):
        a.rng("not_registered")


# ---------------------------------------------------------------- 4.2

def test_candidate_ddl_shape():
    for ddl, table in zip(schemas.ALL_DDL,
                          ("candidate_run", "candidate_lineup",
                           "candidate_player")):
        assert f"`${{predictions}}.{table}`" in ddl
        assert "CREATE TABLE IF NOT EXISTS" in ddl
        assert "PARTITION BY DATE(generated_at)" in ddl
    assert "player_set_hash STRING" in schemas.CANDIDATE_LINEUP_DDL
    assert "manifest_hash STRING" in schemas.CANDIDATE_RUN_DDL
    assert "roster_slot STRING" in schemas.CANDIDATE_PLAYER_DDL


def test_player_set_hash_canonical():
    h1 = schemas.player_set_hash(["b", "a", "c"])
    h2 = schemas.player_set_hash(["c", "b", "a"])
    h3 = schemas.player_set_hash(["a", "b"])
    assert h1 == h2 and h1 != h3
    assert len(h1) == 64
    # ints and strings hash identically (dk ids arrive as both)
    assert schemas.player_set_hash([1, 2]) == schemas.player_set_hash(["2", "1"])


def _engine_cand_rows():
    """Rows in the exact shape backtest/engine.py CAND_LOG_TABLE writes."""
    ts = pd.Timestamp("2025-09-07T16:00:00Z")
    rows = []
    for ix, (tag, sel, rank, players) in enumerate([
        ("lev", True, 0, "00-A,00-B,00-C"),
        ("boom", False, -1, "00-C,00-B,00-D"),
        ("lev", True, 1, "00-D,00-E,00-F"),
    ]):
        rows.append({
            "generated_at": ts, "run_id": "abc123def456",
            "season": 2025, "week": 1, "cand_ix": ix, "tag": tag,
            "selected": sel, "selected_rank": rank, "salary": 49_500,
            "p_line": 0.02 + ix / 100, "sim_mean": 140.0 + ix,
            "sim_q99": 210.0 + ix, "tail_line": 237.0,
            "n_entries": 40, "n_sims": 10_000, "n_locks": 0,
            "n_theses": 1, "players": players,
        })
    return pd.DataFrame(rows)


def test_normalize_cand_log():
    out = schemas.normalize_cand_log(_engine_cand_rows())
    run, lu, pl = (out["candidate_run"], out["candidate_lineup"],
                   out["candidate_player"])
    assert len(run) == 1
    r = run.iloc[0]
    assert r.run_id == "abc123def456" and r.n_candidates == 3
    assert r.tail_line == 237.0 and r.n_sims == 10_000

    assert len(lu) == 3
    assert list(lu.candidate_id) == [
        "abc123def456:00000", "abc123def456:00001", "abc123def456:00002"]
    assert list(lu.selected) == [True, False, True]
    assert list(lu.selected_rank) == [0, -1, 1]
    assert lu.p_tail.iloc[1] == pytest.approx(0.03)
    # canonical hash: order inside the players string must not matter
    assert lu.player_set_hash.iloc[0] == schemas.player_set_hash(
        ["00-C", "00-A", "00-B"])
    assert lu.player_set_hash.nunique() == 3

    assert len(pl) == 9
    assert set(pl[pl.candidate_id == "abc123def456:00001"].player_id) \
        == {"00-B", "00-C", "00-D"}


def test_normalize_cand_log_missing_columns():
    with pytest.raises(ValueError):
        schemas.normalize_cand_log(pd.DataFrame({"run_id": ["x"]}))


# ---------------------------------------------------------------- 3.5

# The shipping defaults as measured 2026-08-05. This test is the
# reconciliation gate: changing a code default MUST break it, forcing
# a conscious manifest (and review-package) update.
EXPECTED_DEFAULTS = {
    "OWN_MODEL": "",
    "PUNT_MIN": 0,
    "PUNT_BOOM": 0.0,
    "MIN_LINEUP_SALARY": 49_000,
    "SELECT_LSE": 0.0,
    "TD_LEDGER": False,
    "TABPFN_MARGINALS": True,
    "TABPFN_MARGINAL_TABLE": "",
    "MODEL_ENSEMBLE": 3,
    "GAME_SIM_MODE": "lognormal",
    "LIVE_SIMS": 30_000,
    "BLEND_WEIGHT": 0.45,
    # The independent CE confirmation did not improve clears; the resolver
    # records the retained 0-CE/40-boom production baseline in code.
    "N_CE": 0,
    "N_EPISTEMIC": 0,
    "N_BOOM": 40,
    "GEN_TOTAL_BUDGET": 40,
}


def test_manifest_matches_live_code(monkeypatch):
    m = config_manifest.manifest()
    assert m["defaults"] == EXPECTED_DEFAULTS

    # cross-check against the importable live constants
    from nfl_dfs.inference.live_lineups import LIVE_SIMS_DEFAULT
    from nfl_dfs.models.blend import BLEND_W
    from nfl_dfs.optimizer.lineup import PUNT_MIN

    assert m["defaults"]["PUNT_MIN"] == PUNT_MIN
    assert m["defaults"]["LIVE_SIMS"] == LIVE_SIMS_DEFAULT
    assert m["defaults"]["BLEND_WEIGHT"] == BLEND_W

    # behavioral check: with no env override, own_mode() is the
    # manifest's OWN_MODEL default (falsy -> naive-fade "")
    monkeypatch.delenv("OWN_MODEL", raising=False)
    from nfl_dfs.backtest.replay import own_mode

    assert own_mode() == m["defaults"]["OWN_MODEL"]


def test_manifest_has_no_config_drift():
    # The manifest's first run caught app/main.py shipping PUNT_BOOM=2
    # against the adopted 0 (Addendum 77/79b) — fixed same day. The
    # standing invariant is now ZERO discrepancies: any future drift
    # between code paths fails this test by name.
    m = config_manifest.manifest()
    assert m["discrepancies"] == [], m["discrepancies"]


def test_tabpfn_feature_contract_freezes_only_the_known_sched_gap():
    from pathlib import Path

    from nfl_dfs.models.featureset import TABPFN_NUMERIC_FEATURES

    tracked = tuple((
        Path(__file__).parents[1] / "scripts" / "tabpfn_gen" / "features.txt"
    ).read_text(encoding="utf-8").split())
    assert tracked == TABPFN_NUMERIC_FEATURES
    contract = config_manifest.manifest()["tabpfn_feature_contract"]
    assert contract["missing_from_tabpfn"] == [
        "net_rest_diff", "body_clock_hour"]
    assert contract["known_omissions"] == contract["missing_from_tabpfn"]
    assert contract["unexpected_in_tabpfn"] == []
    assert contract["shared_order_matches"]


def test_manifest_hash_stable_and_content_sensitive():
    m = config_manifest.manifest()
    h1 = config_manifest.manifest_hash(m)
    h2 = config_manifest.manifest_hash()  # recollect from code
    assert h1 == h2 and len(h1) == 64
    m2 = json.loads(config_manifest.manifest_json(m))
    m2["defaults"]["PUNT_BOOM"] = 2.0
    assert config_manifest.manifest_hash(m2) != h1


# ---------------------------------------------------------------- 4.3

TRUE_CORR = {
    "qb_wr1_same_team": 0.6,
    "qb_opp_qb": 0.5,
    "wr1_wr2_same_team": -0.5,
    "rb_own_dst": 0.4,
}
ROLES_PER_TEAM = ("QB", "WR1", "WR2", "RB1", "DST")


def _game_cov() -> np.ndarray:
    """Correlation matrix over one game's 10 players (two teams of
    QB, WR1, WR2, RB1, DST) implementing TRUE_CORR."""
    n = 2 * len(ROLES_PER_TEAM)
    c = np.eye(n)

    def _set(i, j, rho):
        c[i, j] = c[j, i] = rho

    for t in (0, 5):  # team offsets
        _set(t + 0, t + 1, TRUE_CORR["qb_wr1_same_team"])   # QB-WR1
        _set(t + 1, t + 2, TRUE_CORR["wr1_wr2_same_team"])  # WR1-WR2
        _set(t + 3, t + 4, TRUE_CORR["rb_own_dst"])         # RB1-DST
    _set(0, 5, TRUE_CORR["qb_opp_qb"])                      # QB-oppQB
    # nudge to positive definite
    w, v = np.linalg.eigh(c)
    c = v @ np.diag(np.maximum(w, 1e-3)) @ v.T
    d = np.sqrt(np.diag(c))
    return c / np.outer(d, d)


def _synthetic_slate(n_games=160, n_sims=4000, seed=0):
    """Actuals from a KNOWN correlated law + two sims on identical
    marginals: one with the true copula, one independent."""
    rng = np.random.default_rng(seed)
    cov = _game_cov()
    chol = np.linalg.cholesky(cov)
    mean, sd = 15.0, 6.0
    roles, teams, games = [], [], []
    actuals, good, indep = [], [], []
    for g in range(n_games):
        z = chol @ rng.standard_normal(10)
        actuals.append(mean + sd * z)
        good.append(mean + sd * (chol @ rng.standard_normal((10, n_sims))))
        indep.append(mean + sd * rng.standard_normal((10, n_sims)))
        for team in (f"g{g}A", f"g{g}B"):
            for role in ROLES_PER_TEAM:
                roles.append(role)
                teams.append(team)
                games.append(f"game{g}")
    return (np.concatenate(actuals), np.vstack(good), np.vstack(indep),
            roles, teams, games)


def test_role_pair_indices_counts():
    _, _, _, roles, teams, games = _synthetic_slate(n_games=4, n_sims=10)
    pairs = dependence.role_pair_indices(roles, teams, games)
    assert len(pairs["qb_wr1_same_team"]) == 8   # one per team
    assert len(pairs["wr1_wr2_same_team"]) == 8
    assert len(pairs["rb_own_dst"]) == 8
    assert len(pairs["qb_opp_qb"]) == 4          # one per game
    # bare "RB" aliases to RB1
    pairs2 = dependence.role_pair_indices(
        ["QB", "RB", "DST"], ["t", "t", "t"], ["g", "g", "g"])
    assert len(pairs2["rb_own_dst"]) == 1


def test_variogram_orders_correlated_above_independent():
    actuals, good, indep, roles, teams, games = _synthetic_slate()
    rep_good = dependence.dependence_report(
        good, actuals, roles, teams, games)
    rep_ind = dependence.dependence_report(
        indep, actuals, roles, teams, games)
    # every registered pair type found
    assert all(n > 0 for n in rep_good.n_pairs.values())
    # the true-copula sim wins on every role pair — including the
    # NEGATIVE WR1-WR2 usage-competition pair — and on the gate number
    for name in dependence.DEFAULT_ROLE_WEIGHTS:
        assert rep_good.variogram[name] < rep_ind.variogram[name], name
    assert rep_good.weighted_total < rep_ind.weighted_total


def test_tail_cooccurrence_orders_and_calibrates():
    actuals, good, indep, roles, teams, games = _synthetic_slate()
    rep_good = dependence.dependence_report(
        good, actuals, roles, teams, games)
    rep_ind = dependence.dependence_report(
        indep, actuals, roles, teams, games)
    # independent sim's joint tail sits at (1-q)^2 whatever the truth
    for q in dependence.DEFAULT_TAIL_QUANTILES:
        assert rep_ind.tail["qb_wr1_same_team"][q]["sim"] == pytest.approx(
            (1 - q) ** 2, abs=0.004)
        # positively-dependent truth exceeds that; the good sim knows it
        assert rep_good.tail["qb_wr1_same_team"][q]["sim"] > (1 - q) ** 2
    # aggregate tail gap: true copula closer to realized joints
    assert rep_good.tail_gap_total < rep_ind.tail_gap_total


def test_dependence_report_validates_shapes():
    with pytest.raises(ValueError):
        dependence.dependence_report(
            np.zeros((3, 10)), np.zeros(4), ["QB"] * 3, ["t"] * 3,
            ["g"] * 3)


def test_variogram_empty_pairs_nan():
    assert np.isnan(dependence.variogram_score(
        np.zeros((2, 5)), np.zeros(2), []))


def test_manifest_pins_adopted_generation_budget():
    """The retained boom-only baseline must be provable from code, rather
    than relying on a deployment environment variable."""
    m = config_manifest.manifest()
    d = m["defaults"]
    assert d["N_CE"] == 0 and d["N_BOOM"] == 40
    assert d["GEN_TOTAL_BUDGET"] == 40
    assert d["N_CE"] + d["N_EPISTEMIC"] + d["N_BOOM"] == 40
