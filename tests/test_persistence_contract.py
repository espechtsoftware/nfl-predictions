"""ACTION 0 persistence contract (post-review-6 plan §C, Sol audit).

Every assertion here is a gate on the canonical harvest: no panel runs
until they pass. They encode the four defects the audit found in the
first persistence patch (34432a5):
  A2.1 provenance recorded for EVERY producer, before the dedupe test
  A2.2 missing actuals -> NULL labels, never false zeros
  A2.3 two-level run identity (panel + slate)
  A2.4 full-length masks with n_worlds/bitorder + the 187/194/200 grid,
       and selection reconstructable from the persisted masks alone
"""
import json
import io
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest import engine
from nfl_dfs.optimizer.lineup import (select_from_support,
                                      select_tail_entries)


def _slate(n_teams: int = 4):
    pool, ix = [], 0
    for pos, n, sal in (("QB", 4, 6000), ("RB", 8, 5200), ("WR", 12, 4800),
                        ("TE", 6, 3600), ("DST", 4, 2800)):
        for k in range(n):
            pool.append({
                "id": f"{pos}{k}", "name": f"{pos}{k}", "pos": pos,
                "team": f"T{ix % n_teams}", "opp": f"T{(ix + 1) % n_teams}",
                "game_id": f"g{ix % 2}", "salary": sal + 111 * k,
                "proj": 8.0 + (k % 6), "actual": 9.0 + (k % 7),
                "season": 2025, "week": 3})
            ix += 1
    slate = pd.DataFrame(pool)
    slate["draw_idx"] = range(len(slate))
    draws = np.abs(np.random.default_rng(5).normal(9, 4.5,
                                                   size=(len(pool), 256)))
    return slate, pool, draws


def _capture(monkeypatch, pool_override=None, **env):
    """Run one selection with persistence on, capturing the rows the
    writer would send to BigQuery."""
    slate, pool, draws = _slate()
    if pool_override is not None:
        pool = pool_override(pool)
        slate = pd.DataFrame(pool)
        slate["draw_idx"] = range(len(slate))
    captured = {}

    def fake_load(df, table, **kw):
        captured["df"] = df
        captured["table"] = table

    monkeypatch.setattr("nfl_dfs.bq.load_dataframe", fake_load)
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    lus = engine.tail_select_lineups(
        slate, pool, draws, tail_line=95.0, n_entries=8, stack=None,
        objective_col="proj",
        cand_log_table="proj.ds.candidates")
    return captured.get("df"), lus, draws, slate


def test_labels_present_and_ranked_when_actuals_complete(monkeypatch):
    df, _, _, _ = _capture(monkeypatch, PANEL_RUN_ID="panel-abc")
    assert df is not None and len(df)
    assert df.labels_complete.all()
    assert df.run_type.eq("replay").all()
    # eligibility is granted by PROMOTION, never by the writer
    assert not df.research_eligible.any()
    assert df.actual_score.notna().all()
    # ranks are 1..n with ties handled by an explicit method
    assert df.actual_rank.min() == 1
    best = df.loc[df.actual_score.idxmax()]
    assert best.actual_rank == 1


def test_missing_actuals_become_null_not_zero(monkeypatch):
    def strip(pool):
        return [{**p, "actual": None} for p in pool]

    df, _, _, _ = _capture(monkeypatch, pool_override=strip)
    assert df is not None and len(df)
    assert not df.labels_complete.any()
    assert df.actual_score.isna().all(), "missing actuals became zeros"
    assert df.actual_rank.isna().all()
    assert df.run_type.eq("live_unlabeled").all()
    assert not df.research_eligible.any()


def test_two_level_run_identity(monkeypatch):
    df, _, _, _ = _capture(monkeypatch, PANEL_RUN_ID="panel-xyz")
    assert df.panel_run_id.eq("panel-xyz").all()
    assert df.slate_run_id.nunique() == 1
    assert df.slate_run_id.iloc[0] != "panel-xyz"
    # without a panel id the rows must not be research-eligible
    df2, _, _, _ = _capture(monkeypatch, PANEL_RUN_ID="")
    assert not df2.research_eligible.any()


def test_explicit_shadow_identity_overrides_process_env(monkeypatch):
    slate, pool, draws = _slate()
    writes = []
    monkeypatch.setattr(
        "nfl_dfs.bq.load_dataframe",
        lambda df, table, **kw: writes.append((table, df)),
    )
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    monkeypatch.setenv("PANEL_RUN_ID", "wrong-process-id")
    monkeypatch.setenv("MODEL_REGISTRY_VARIANT", "tail_k1")
    engine.tail_select_lineups(
        slate, pool, draws, tail_line=95.0, n_entries=8, stack=None,
        objective_col="proj", cand_log_table="proj.ds.candidates",
        panel_run_id="prospective-k1", candidate_run_type="live_shadow",
    )
    df = next(d for t, d in writes if t.endswith("candidates"))
    assert df.panel_run_id.eq("prospective-k1").all()
    assert df.run_type.eq("live_shadow").all()
    assert "MODEL_REGISTRY_VARIANT=tail_k1" in df.lever_env.iloc[0]


def test_required_persistence_propagates_warehouse_failure(monkeypatch):
    slate, pool, draws = _slate()
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    monkeypatch.setattr(
        "nfl_dfs.bq.load_dataframe",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("warehouse down")),
    )
    with pytest.raises(RuntimeError, match="warehouse down"):
        engine.tail_select_lineups(
            slate, pool, draws, tail_line=95.0, n_entries=8, stack=None,
            objective_col="proj", cand_log_table="proj.ds.candidates",
            cand_log_required=True,
        )


def test_required_persistence_rejects_async_mode():
    slate, pool, draws = _slate()
    with pytest.raises(ValueError, match="cannot run asynchronously"):
        engine.tail_select_lineups(
            slate, pool, draws, tail_line=95.0, n_entries=8, stack=None,
            objective_col="proj", cand_log_table="proj.ds.candidates",
            cand_log_async=True, cand_log_required=True,
        )


def test_explicit_empty_candidate_table_disables_process_default(monkeypatch):
    """Auxiliary CBWU searches must never persist native selected books."""
    slate, pool, draws = _slate()
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    monkeypatch.setenv("CAND_LOG_TABLE", "proj.ds.must-not-write")
    monkeypatch.setattr(
        "nfl_dfs.bq.load_dataframe",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("explicit empty table was ignored")),
    )
    lineups = engine.tail_select_lineups(
        slate, pool, draws, tail_line=95.0, n_entries=8, stack=None,
        objective_col="proj", cand_log_table="",
    )
    assert len(lineups) == 8


def test_multi_generator_provenance_records_every_producer(monkeypatch):
    df, _, _, _ = _capture(monkeypatch, PANEL_RUN_ID="p", N_GUMBEL="6",
                           HYPER_BOOM="2")
    tags = df.all_tags.map(json.loads)
    assert tags.map(len).max() >= 2, (
        "no roster recorded two producers — provenance is still "
        "first-producer-only (A2.1)")
    # the primary tag must always appear inside the provenance list
    assert all(row.tag in tags.iloc[i]
               for i, (_, row) in enumerate(df.iterrows()))


def test_masks_full_length_and_grid_decodes(monkeypatch):
    df, _, draws, _ = _capture(monkeypatch, PANEL_RUN_ID="p")
    n_worlds = int(df.n_worlds.iloc[0])
    assert df.bitorder.eq("big").all()
    for col, line in (("clear_bits_187", 187.0), ("clear_bits_194", 194.0),
                      ("clear_bits_200", 200.0), ("clear_bits_210", 210.0),
                      ("clear_bits_220", 220.0), ("clear_bits", 95.0)):
        bits = np.unpackbits(
            np.frombuffer(bytes.fromhex(df[col].iloc[0]), dtype=np.uint8),
            bitorder="big")[:n_worlds]
        assert len(bits) == n_worlds, f"{col} truncated"
    # monotone: a lower line can never clear fewer worlds than a higher one
    def count(col):
        return np.unpackbits(np.frombuffer(
            bytes.fromhex(df[col].iloc[0]), dtype=np.uint8),
            bitorder="big")[:n_worlds].sum()
    assert count("clear_bits_187") >= count("clear_bits_194") >= \
        count("clear_bits_200") >= count("clear_bits_210") >= \
        count("clear_bits_220")


def test_score_artifact_can_retain_aligned_player_worlds():
    slate = pd.DataFrame({"id": ["p2", "DST-p1"]})
    player_draws = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.float32)
    totals = np.array([[5, 7, 9]], dtype=np.float32)
    payload = engine._score_artifact_payload(
        totals, 194.0, slate=slate, row_draws=player_draws,
        include_player_worlds=True,
    )
    with np.load(io.BytesIO(payload), allow_pickle=False) as artifact:
        assert artifact["player_ids"].tolist() == ["p2", "DST-p1"]
        np.testing.assert_array_equal(artifact["player_draws"], player_draws)
        np.testing.assert_array_equal(artifact["totals"], totals)
        assert float(artifact["tail_line"]) == 194.0


def test_score_artifact_omits_player_worlds_by_default():
    payload = engine._score_artifact_payload(
        np.array([[5, 7, 9]], dtype=np.float32), 194.0,
    )
    with np.load(io.BytesIO(payload), allow_pickle=False) as artifact:
        assert "player_ids" not in artifact.files
        assert "player_draws" not in artifact.files


def test_selection_reproducible_from_persisted_masks(monkeypatch):
    """The decisive gate: greedy coverage rebuilt from the stored masks
    must return the ORIGINAL selected set, in order."""
    df, lus, _, _ = _capture(monkeypatch, PANEL_RUN_ID="p")
    n_worlds = int(df.n_worlds.iloc[0])
    masks = np.stack([
        np.unpackbits(np.frombuffer(bytes.fromhex(b), dtype=np.uint8),
                      bitorder="big")[:n_worlds].astype(bool)
        for b in df.clear_bits])
    # Rebuild via the SHARED selector helper with the persisted
    # tiebreakers. The old form (binary 1e6/0 totals) silently dropped
    # the mean-total tiebreak and only passed while no candidates tied;
    # adding the CE batch to the default pool produced ties and exposed
    # it — the same class of defect the helper was extracted to prevent.
    picked = select_from_support(masks, df.p_line.to_numpy(),
                                 df.sim_mean.to_numpy(), len(lus))
    stored = df[df.selected].sort_values("selected_rank").cand_ix.tolist()
    assert list(picked) == stored, (
        f"mask-reconstructed selection {picked} != persisted {stored}")


def test_selector_tiebreak_uses_mean_total():
    """Adversarial (Sol audit 3): candidates that tie on coverage AND
    p_line must be broken by mean total. A binary-mask reconstruction
    that drops mean_total would pick the wrong one — this is why
    production and the acceptance gate share select_from_support."""
    from nfl_dfs.optimizer.lineup import select_from_support

    clears = np.array([[True, False], [True, False]])   # identical support
    p_line = np.array([0.5, 0.5])                        # identical p_line
    mean_total = np.array([100.0, 180.0])                # only difference
    picked = select_from_support(clears, p_line, mean_total, 1)
    assert picked == [1], f"mean-total tiebreak ignored: {picked}"
    # and with the means swapped, the other candidate must win
    picked2 = select_from_support(clears, p_line, mean_total[::-1], 1)
    assert picked2 == [0]


def test_provenance_fields_present(monkeypatch):
    df, _, _, _ = _capture(monkeypatch, PANEL_RUN_ID="p-prov",
                           MIN_LINEUP_SALARY="0",
                           EXTRA_FEATURES="target_share_last",
                           EPISTEMIC_FAMILY="role_draws",
                           ROLE_BELIEF_FEATURES="target_share_last",
                           ROLE_BELIEF_SEED="7331",
                           REPLAY_PROJECTION_SEED="1137260708",
                           SIS_ASOE_TARGET_ALLOCATION="1",
                           SIS_ASOE_BETA="0.07771181538347656",
                           TD_LEDGER_RANK_COUPLING="1",
                           TD_COMPETITIVE_WR_ALLOCATION="1",
                           TD_COMP_WR_EXACT80_LICENSED="1",
                           TD_COMP_WR_PROTOCOL_SHA256="a" * 64,
                           TD_COMP_WR_REFERENCE_REPORT_SHA256="b" * 64,
                           TD_COMP_WR_TREATMENT_REPORT_SHA256="c" * 64,
                           GAME_SIM_USAGE="dirichlet",
                           DIRICHLET_K="28.246898139750336",
                           TABPFN_MARGINAL_TABLE="tabpfn_active_label_treatment_v1",
                           SERVED_TAIL_SCALE="1.025",
                           SERVED_POSITION_SCALES="QB:0.97,RB:1.005,TE:0.94,WR:1.07",
                           ENSEMBLE_WORLD_MODE="member_sample",
                           ENSEMBLE_WORLD_SEED="8161",
                           ARCHETYPE_ALLOCATION_VERSION=(
                               "prospective-archetype-allocation-v1"),
                           ARCHETYPE_TAIL_LINE="194.0",
                           PROSPECTIVE_SHADOW_ID="2026-archetype-cbwu-v1")
    for col in (
        "code_sha", "code_dirty", "config_hash", "lever_env", "seeds",
        "candidate_batch_metadata", "score_artifact_uri",
        "score_artifact_sha256",
    ):
        assert col in df.columns, f"missing provenance column {col}"
    # lever_env must record the env that was actually set
    assert "MIN_LINEUP_SALARY=0" in df.lever_env.iloc[0]
    assert "EXTRA_FEATURES=target_share_last" in df.lever_env.iloc[0]
    assert "EPISTEMIC_FAMILY=role_draws" in df.lever_env.iloc[0]
    assert "ROLE_BELIEF_FEATURES=target_share_last" in df.lever_env.iloc[0]
    assert "REPLAY_PROJECTION_SEED=1137260708" in df.lever_env.iloc[0]
    assert "SIS_ASOE_TARGET_ALLOCATION=1" in df.lever_env.iloc[0]
    assert "SIS_ASOE_BETA=0.07771181538347656" in df.lever_env.iloc[0]
    assert "TD_LEDGER_RANK_COUPLING=1" in df.lever_env.iloc[0]
    assert "TD_COMPETITIVE_WR_ALLOCATION=1" in df.lever_env.iloc[0]
    assert "TD_COMP_WR_EXACT80_LICENSED=1" in df.lever_env.iloc[0]
    assert f"TD_COMP_WR_PROTOCOL_SHA256={'a' * 64}" in df.lever_env.iloc[0]
    assert f"TD_COMP_WR_REFERENCE_REPORT_SHA256={'b' * 64}" \
        in df.lever_env.iloc[0]
    assert f"TD_COMP_WR_TREATMENT_REPORT_SHA256={'c' * 64}" \
        in df.lever_env.iloc[0]
    assert "GAME_SIM_USAGE=dirichlet" in df.lever_env.iloc[0]
    assert "DIRICHLET_K=28.246898139750336" in df.lever_env.iloc[0]
    assert "TABPFN_MARGINAL_TABLE=tabpfn_active_label_treatment_v1" \
        in df.lever_env.iloc[0]
    assert "SERVED_TAIL_SCALE=1.025" in df.lever_env.iloc[0]
    assert "SERVED_POSITION_SCALES=QB:0.97,RB:1.005,TE:0.94,WR:1.07" \
        in df.lever_env.iloc[0]
    assert "ENSEMBLE_WORLD_MODE=member_sample" in df.lever_env.iloc[0]
    assert "ARCHETYPE_ALLOCATION_VERSION=prospective-archetype-allocation-v1" \
        in df.lever_env.iloc[0]
    assert "ARCHETYPE_TAIL_LINE=194.0" in df.lever_env.iloc[0]
    assert "PROSPECTIVE_SHADOW_ID=2026-archetype-cbwu-v1" \
        in df.lever_env.iloc[0]
    batch_metadata = json.loads(df.candidate_batch_metadata.iloc[0])
    assert batch_metadata["tail_line"] == 95.0
    assert batch_metadata["n_entries"] == 8
    assert "ROLE_BELIEF_SEED=7331" in df.seeds.iloc[0]
    assert "REPLAY_PROJECTION_SEED=1137260708" in df.seeds.iloc[0]
    assert "MODEL_ENSEMBLE_SIZE=3" in df.seeds.iloc[0]
    assert "ENSEMBLE_WORLD_SEED=8161" in df.seeds.iloc[0]
    member_spec = json.loads(
        df.seeds.iloc[0].split("MODEL_MEMBER_SPEC=", 1)[1])
    assert [member["seeds"]["seed"] for member in member_spec] == [
        9000, 9001, 9002]


def test_single_member_provenance_is_explicit(monkeypatch):
    df, _, _, _ = _capture(
        monkeypatch, PANEL_RUN_ID="p-ens1", MODEL_ENSEMBLE="1")
    assert "MODEL_ENSEMBLE=1" in df.lever_env.iloc[0]
    assert "MODEL_ENSEMBLE_SIZE=1" in df.seeds.iloc[0]
    member_spec = json.loads(
        df.seeds.iloc[0].split("MODEL_MEMBER_SPEC=", 1)[1])
    assert member_spec[0]["column_order"] == "canonical"
    assert member_spec[0]["seeds"] == "library-defaults"


def test_container_provenance_uses_deployed_code_sha(monkeypatch):
    """The production image has no .git directory.  A failed git command
    returns blank stdout rather than raising, so CODE_SHA must be the explicit
    fallback and must never become a falsely successful blank value."""
    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=128, stdout="", stderr="not a git repository"),
    )
    df, _, _, _ = _capture(
        monkeypatch, PANEL_RUN_ID="p-container", CODE_SHA="b9e33eb12345")
    assert df.code_sha.eq("b9e33eb12345").all()


def test_staging_rows_never_research_eligible(monkeypatch):
    df, _, _, _ = _capture(monkeypatch, PANEL_RUN_ID="p-elig")
    assert not df.research_eligible.any(), (
        "staging rows must be ineligible until promotion")


def test_player_feature_snapshot_written(monkeypatch):
    """A2.6: the point-in-time features construction used must persist
    during the run, with explicit missingness — never reconstructed
    later from mutable tables."""
    slate, pool, draws = _slate()
    slate["own_est"] = 0.12
    slate["consensus_div"] = 1.5
    slate["market_points"] = slate.proj - 0.5
    slate["model_points_pre"] = slate.proj + 0.3
    slate["ensemble_point_0"] = slate.proj - 0.2
    slate["ensemble_point_1"] = slate.proj + 0.1
    slate["ensemble_point_2"] = slate.proj + 0.4
    slate["target_share_last"] = 0.22
    slate["carry_share_jump"] = 0.08
    slate["is_cold_start"] = False
    writes: list = []
    monkeypatch.setattr("nfl_dfs.bq.load_dataframe",
                        lambda df, table, **kw: writes.append((table, df)))
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    monkeypatch.setenv("PANEL_RUN_ID", "p-feat")
    engine.tail_select_lineups(
        slate, slate.to_dict("records"), draws, tail_line=95.0,
        n_entries=8, stack=None, objective_col="proj",
        cand_log_table="proj.ds.candidates")
    tables = {t for t, _ in writes}
    assert any(t.endswith("slate_player_features") for t in tables), tables
    fdf = next(d for t, d in writes if t.endswith("slate_player_features"))
    # one row per slate player, carrying the orthogonal features
    assert len(fdf) == len(slate)
    for col in ("market_points", "model_points_pre", "consensus_div",
                "own_est", "proj", "salary", "panel_run_id", "slate_run_id",
                "target_share_last", "carry_share_jump", "is_cold_start",
                "ensemble_point_0", "ensemble_point_1", "ensemble_point_2",
                "model_ensemble_size", "model_member_spec",
                "feature_missing", "code_sha"):
        assert col in fdf.columns, f"missing {col}"
    assert fdf.target_share_last.eq(0.22).all()
    assert fdf.carry_share_jump.eq(0.08).all()
    assert str(fdf.is_cold_start.dtype) == "boolean"
    assert fdf.model_ensemble_size.eq(3).all()
    specs = json.loads(fdf.model_member_spec.iloc[0])
    assert [member["seeds"]["seed"] for member in specs] == [9000, 9001, 9002]
    assert not fdf.research_eligible.any()
    # quantile columns absent from this fixture must be declared missing
    assert "proj_p90" in json.loads(fdf.feature_missing.iloc[0])


def test_feature_snapshot_is_warehouse_typed(monkeypatch):
    """2026-08-05 harvest failure: all-None object columns made every
    feature write fail pyarrow conversion while candidates wrote fine.
    Missing families must be TYPED (float NaN / string NA), and present
    columns coerced, so the frame is loadable."""
    import pyarrow as pa

    slate, pool, draws = _slate()          # no market/quantile columns
    writes: list = []
    monkeypatch.setattr("nfl_dfs.bq.load_dataframe",
                        lambda df, table, **kw: writes.append((table, df)))
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    monkeypatch.setenv("PANEL_RUN_ID", "p-typed")
    engine.tail_select_lineups(
        slate, pool, draws, tail_line=95.0, n_entries=8, stack=None,
        objective_col="proj", cand_log_table="proj.ds.candidates")
    fdf = next(d for t, d in writes if t.endswith("slate_player_features"))
    for col in ("market_points", "model_points_pre", "proj_p90",
                "target_share_last", "depth_rank_delta", "dk_points_l4"):
        assert fdf[col].dtype.kind == "f", f"{col} is {fdf[col].dtype}"
    assert str(fdf.is_cold_start.dtype) == "boolean"
    # the decisive check: the frame must survive arrow conversion, which
    # is what the warehouse loader does internally
    pa.Table.from_pandas(fdf, preserve_index=False)
