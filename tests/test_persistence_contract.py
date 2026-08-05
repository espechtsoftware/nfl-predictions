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

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest import engine
from nfl_dfs.optimizer.lineup import select_tail_entries


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
                      ("clear_bits_200", 200.0), ("clear_bits", 95.0)):
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
        count("clear_bits_200")


def test_selection_reproducible_from_persisted_masks(monkeypatch):
    """The decisive gate: greedy coverage rebuilt from the stored masks
    must return the ORIGINAL selected set, in order."""
    df, lus, _, _ = _capture(monkeypatch, PANEL_RUN_ID="p")
    n_worlds = int(df.n_worlds.iloc[0])
    masks = np.stack([
        np.unpackbits(np.frombuffer(bytes.fromhex(b), dtype=np.uint8),
                      bitorder="big")[:n_worlds].astype(bool)
        for b in df.clear_bits])
    # rebuild the same greedy pick order the selector used, from masks
    totals = np.where(masks, 1e6, 0.0)  # any value >= line where cleared
    picked = select_tail_entries(totals, len(lus), 1e5)
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
                           MIN_LINEUP_SALARY="0")
    for col in ("code_sha", "code_dirty", "config_hash", "lever_env",
                "seeds", "score_artifact_uri", "score_artifact_sha256"):
        assert col in df.columns, f"missing provenance column {col}"
    # lever_env must record the env that was actually set
    assert "MIN_LINEUP_SALARY=0" in df.lever_env.iloc[0]


def test_staging_rows_never_research_eligible(monkeypatch):
    df, _, _, _ = _capture(monkeypatch, PANEL_RUN_ID="p-elig")
    assert not df.research_eligible.any(), (
        "staging rows must be ineligible until promotion")
