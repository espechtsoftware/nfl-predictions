from __future__ import annotations

from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research.live_shadow_portfolios import (
    EXPECTED_ENTRIES,
    K1_COVERAGE,
    K1_COVERAGE_187,
    K1_COVERAGE_200,
    K1_EXTREME_LEX,
    K1_NOFLOOR_COVERAGE,
    K1_ROLE_COVERAGE,
    K1_ROLE_EXTREME_LEX,
    K1_REFINED,
    K1_TOP_P,
    K3_COVERAGE,
    MIX_20_60,
    build_portfolios,
    canonical_roster,
    choose_latest_panels,
    coverage_order,
    extreme_lexicographic_order,
    score_portfolios,
    summarize_grades,
    validate_shadow_panel,
)


def _mask(count: int, n_worlds: int = 100) -> str:
    values = np.zeros(n_worlds, dtype=bool)
    values[:count] = True
    return np.packbits(values, bitorder="big").tobytes().hex()


def _roster(model: str, cand_ix: int) -> str:
    # Five deliberate cross-model duplicates exercise mixed-book backfill.
    prefix = "shared" if cand_ix < 5 else model
    return ",".join(f"{prefix}_{cand_ix}_{slot}" for slot in range(9))


def _panel(model: str, *, stamp: str = "2026-09-13T15:30:00Z") -> pd.DataFrame:
    is_k1 = model in {
        "tail_k1", "tail_k1_nofloor", "tail_k1_roleunion"}
    variant = "tail_k1" if is_k1 else "canonical"
    size = 1 if is_k1 else 3
    floor = 0 if model == "tail_k1_nofloor" else 49_000
    panel_stamp = pd.Timestamp(stamp).strftime("%Y%m%dT%H%M%SZ")
    panel = f"live-shadow-{model}-2026w01-{panel_stamp}"
    rows = []
    for cand_ix in range(100):
        count = 100 - cand_ix
        rows.append({
            "generated_at": stamp,
            "panel_run_id": panel,
            "slate_run_id": f"slate-{model}-{panel_stamp}",
            "run_type": "live_shadow",
            "code_sha": "abc123def456",
            "config_hash": "cfg",
            "lever_env": (
                f"MODEL_REGISTRY_VARIANT={variant}|"
                f"MIN_LINEUP_SALARY={floor}"
                + ("|N_CE=12|N_EPISTEMIC=12|N_BOOM=28|"
                   "EPISTEMIC_FAMILY=role_draws|ROLE_BELIEF_SEED=7331|"
                   "ROLE_BELIEF_FEATURES=target_share_last,carry_share_last,"
                   "snap_share_last,target_share_jump,carry_share_jump,"
                   "snap_share_jump"
                   if model == "tail_k1_roleunion" else "")),
            "seeds": f"MODEL_ENSEMBLE_SIZE={size}",
            "labels_complete": False,
            "research_eligible": False,
            "season": 2026,
            "week": 1,
            "cand_ix": cand_ix,
            "players": _roster(model, cand_ix),
            "selected": cand_ix < EXPECTED_ENTRIES,
            "selected_rank": cand_ix if cand_ix < EXPECTED_ENTRIES else -1,
            "p_line": count / 100,
            "sim_mean": 200 - cand_ix,
            "actual_score": np.nan,
            "tail_line": 194.0,
            "n_entries": EXPECTED_ENTRIES,
            "n_worlds": 100,
            "clear_bits_194": _mask(count),
            "clear_bits_187": _mask(count),
            "clear_bits_200": _mask(count),
            "clear_bits_210": _mask(count),
            "clear_bits_220": _mask(count),
            "score_artifact_uri": f"gs://bucket/{panel}.npz",
            "score_artifact_sha256": "f" * 64,
        })
    return pd.DataFrame(rows)


def test_canonical_roster_requires_nine_unique_ids():
    value = "b,a,c,d,e,f,g,h,i"
    assert canonical_roster(value) == "a,b,c,d,e,f,g,h,i"
    with pytest.raises(ValueError, match="9 unique"):
        canonical_roster("a,b,c")
    with pytest.raises(ValueError, match="9 unique"):
        canonical_roster("a,a,b,c,d,e,f,g,h")


def test_coverage_order_uses_the_requested_persisted_mask():
    rows = _panel("tail_k1")
    rows["clear_bits_200"] = _mask(0)
    rows.loc[99, "clear_bits_200"] = _mask(100)
    _, at_194 = coverage_order(rows, 194)
    _, at_200 = coverage_order(rows, 200)
    assert int(at_194[0]) == 0
    assert int(at_200[0]) == 99
    _, at_210 = coverage_order(rows, 210)
    assert int(at_210[0]) == 0
    with pytest.raises(ValueError, match="unsupported"):
        coverage_order(rows, 230)


def test_extreme_lexicographic_order_prioritizes_220_then_210_then_200():
    rows = _panel("tail_k1")
    for column in ("clear_bits_200", "clear_bits_210", "clear_bits_220"):
        rows[column] = _mask(0)
    rows.loc[3, ["clear_bits_200", "clear_bits_210", "clear_bits_220"]] = \
        _mask(1)
    rows.loc[4, ["clear_bits_200", "clear_bits_210"]] = _mask(100)
    rows.loc[5, "clear_bits_200"] = _mask(100)

    _, order = extreme_lexicographic_order(rows)

    assert order[:3].tolist() == [3, 4, 5]

    invalid = rows.copy()
    invalid.loc[6, "clear_bits_220"] = _mask(2)
    with pytest.raises(ValueError, match="not nested"):
        extreme_lexicographic_order(invalid)


def test_builds_frozen_top_p_and_duplicate_backfilled_mix():
    memberships = build_portfolios(
        _panel("tail_k1"), _panel("tail_k1_nofloor"),
        _panel("tail_k1_roleunion"), _panel("tail_k3"),
        portfolio_run_id="live-tail-portfolios-2026w01-early",
        snapshot_slot="early",
        frozen_at=datetime(2026, 9, 13, 16, 5, tzinfo=timezone.utc),
    )
    assert set(memberships.portfolio_id) == {
        K1_COVERAGE, K1_COVERAGE_187, K1_COVERAGE_200,
        K1_EXTREME_LEX, K1_TOP_P, K1_NOFLOOR_COVERAGE, K1_REFINED,
        K1_ROLE_COVERAGE, K1_ROLE_EXTREME_LEX, K3_COVERAGE, MIX_20_60}
    counts = memberships.groupby("portfolio_id").size()
    assert counts.eq(EXPECTED_ENTRIES).all()
    assert not memberships.groupby("portfolio_id").roster_key.apply(
        lambda values: values.duplicated().any()).any()

    top = memberships[memberships.portfolio_id.eq(K1_TOP_P)]
    assert top.sort_values("portfolio_entry_rank").cand_ix.tolist() == \
        list(range(80))
    refined = memberships[memberships.portfolio_id.eq(K1_REFINED)]
    assert refined.selection_method.eq(
        "coverage194_one_swap_lexicographic").all()
    assert refined.sort_values("portfolio_entry_rank").cand_ix.tolist() == \
        list(range(80))
    assert memberships[
        memberships.portfolio_id.eq(K1_COVERAGE_187)
    ].selection_method.eq("coverage187").all()
    assert memberships[
        memberships.portfolio_id.eq(K1_COVERAGE_200)
    ].selection_method.eq("coverage200").all()
    assert memberships[
        memberships.portfolio_id.eq(K1_EXTREME_LEX)
    ].selection_method.eq("coverage_lex_220_210_200").all()
    assert memberships[
        memberships.portfolio_id.eq(K1_ROLE_COVERAGE)
    ].selection_method.eq("coverage194_roleunion").all()
    assert memberships[
        memberships.portfolio_id.eq(K1_ROLE_EXTREME_LEX)
    ].selection_method.eq("coverage_lex_220_210_200_roleunion").all()
    nofloor = memberships[
        memberships.portfolio_id.eq(K1_NOFLOOR_COVERAGE)]
    assert nofloor.source_model.eq("tail_k1_nofloor").all()
    assert nofloor.sort_values("portfolio_entry_rank").cand_ix.tolist() == \
        list(range(80))
    mixed = memberships[memberships.portfolio_id.eq(MIX_20_60)]
    assert mixed.groupby("source_model").size().to_dict() == {
        "tail_k1": 20, "tail_k3": 60}
    assert mixed.duplicate_backfills.eq(5).all()
    k3 = mixed[mixed.source_model.eq("tail_k3")]
    assert k3.sort_values("portfolio_entry_rank").cand_ix.tolist() == \
        list(range(5, 65))


def test_shadow_validation_rejects_labels_and_wrong_registry():
    labeled = _panel("tail_k1")
    labeled.loc[0, "actual_score"] = 1.0
    with pytest.raises(ValueError, match="actual labels"):
        validate_shadow_panel(labeled, "tail_k1")
    wrong = _panel("tail_k1")
    wrong["lever_env"] = "MODEL_REGISTRY_VARIANT=canonical"
    with pytest.raises(ValueError, match="wrong registry"):
        validate_shadow_panel(wrong, "tail_k1")
    wrong_floor = _panel("tail_k1_nofloor")
    wrong_floor["lever_env"] = (
        "MODEL_REGISTRY_VARIANT=tail_k1|MIN_LINEUP_SALARY=49000")
    with pytest.raises(ValueError, match="wrong salary floor"):
        validate_shadow_panel(wrong_floor, "tail_k1_nofloor")


def test_choose_latest_panels_is_date_and_ct_slot_bounded():
    old_k1 = _panel("tail_k1", stamp="2026-09-13T15:25:00Z")
    new_k1 = _panel("tail_k1", stamp="2026-09-13T15:35:00Z")
    nofloor = _panel("tail_k1_nofloor", stamp="2026-09-13T15:33:00Z")
    k3 = _panel("tail_k3", stamp="2026-09-13T15:34:00Z")
    late = pd.concat([
        _panel("tail_k1", stamp="2026-09-13T16:20:00Z"),
        _panel("tail_k1_nofloor", stamp="2026-09-13T16:20:00Z"),
        _panel("tail_k1_roleunion", stamp="2026-09-13T16:20:00Z"),
        _panel("tail_k3", stamp="2026-09-13T16:20:00Z"),
    ])
    role = _panel("tail_k1_roleunion", stamp="2026-09-13T15:32:00Z")
    rows = pd.concat(
        [old_k1, new_k1, nofloor, role, k3, late], ignore_index=True)
    chosen_k1, chosen_nofloor, chosen_role, chosen_k3 = choose_latest_panels(
        rows, season=2026, week=1, target_sunday=date(2026, 9, 13),
        snapshot_slot="early")
    assert chosen_k1.panel_run_id.nunique() == 1
    assert chosen_k1.panel_run_id.iloc[0].endswith("20260913T153500Z")
    assert chosen_nofloor.panel_run_id.iloc[0].endswith("20260913T153300Z")
    assert chosen_role.panel_run_id.iloc[0].endswith("20260913T153200Z")
    assert chosen_k3.panel_run_id.iloc[0].endswith("20260913T153400Z")


def test_scores_frozen_memberships_and_fails_on_missing_actual():
    memberships = build_portfolios(
        _panel("tail_k1"), _panel("tail_k1_nofloor"),
        _panel("tail_k1_roleunion"), _panel("tail_k3"),
        portfolio_run_id="live-tail-portfolios-2026w01-early",
        snapshot_slot="early")
    player_ids = sorted({
        player
        for value in memberships.players
        for player in str(value).split(",")
    })
    actuals = pd.DataFrame({
        "season": 2026,
        "week": 1,
        "id": player_ids,
        "actual": 1.0,
    })
    grades = score_portfolios(memberships, actuals)
    assert len(grades) == 11
    assert grades.n_entries.eq(80).all()
    assert grades.weekly_max.eq(9.0).all()
    summary = summarize_grades(grades)
    assert len(summary) == 11
    assert summary.ge_200.eq(0).all()
    assert summary.mean_weekly_max.eq(9.0).all()
    with pytest.raises(ValueError, match="missing actuals"):
        score_portfolios(memberships, actuals.iloc[1:])


# --- Route Share pair reader (O-25, 2026-10-05) ---------------------------------------

def _companion_lever(variant: str) -> str:
    """The lever record the engine writes for a companion-v1 arm."""
    from nfl_dfs.backtest.engine import _lever_keys
    from nfl_dfs.inference import tail_shadow
    from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY

    env = {
        **tail_shadow.route_share_job_environment("companion-v1"),
        **ADOPTED_CLASSIC_POLICY.construction_preset().optimizer_environment(),
        "MODEL_REGISTRY_VARIANT": variant,
        "PROSPECTIVE_SHADOW_ID": tail_shadow.COMPANION_V1_SHADOW_ID,
    }
    return ",".join(sorted(f"{k}={v}" for k, v in env.items() if k in _lever_keys))


def _route_panel(model: str, contract: str, *,
                 stamp: str = "2026-09-13T15:30:00Z") -> pd.DataFrame:
    """A role-union arm (control tail_k1_roleunion or treatment tail_k1_route_roleunion)."""
    base = _panel("tail_k1_roleunion", stamp=stamp)
    panel_stamp = pd.Timestamp(stamp).strftime("%Y%m%dT%H%M%SZ")
    panel = f"live-shadow-{model}-2026w01-{panel_stamp}"
    variant = "tail_k1" if model == "tail_k1_roleunion" else "tail_k1_route"
    out = base.copy()
    out["panel_run_id"] = panel
    out["slate_run_id"] = f"slate-{model}-{panel_stamp}"
    out["score_artifact_uri"] = f"gs://bucket/{panel}.npz"
    out["players"] = [_roster(model, ix) for ix in out.cand_ix]
    if contract == "companion-v1":
        out["lever_env"] = _companion_lever(variant)
        n_worlds = 30_000
        out["n_worlds"] = n_worlds
        for column in ("clear_bits_187", "clear_bits_194", "clear_bits_200",
                       "clear_bits_210", "clear_bits_220"):
            out[column] = [_mask(100 - ix, n_worlds) for ix in out.cand_ix]
        out["p_line"] = [(100 - ix) / n_worlds for ix in out.cand_ix]
    else:
        out["lever_env"] = out.lever_env.str.replace(
            "MODEL_REGISTRY_VARIANT=tail_k1|", f"MODEL_REGISTRY_VARIANT={variant}|")
    return out


def _old_freeze_world(monkeypatch, rows: pd.DataFrame):
    """Offline BigQuery for freeze(): candidates in, memberships captured."""
    import nfl_dfs.bq as bq
    from nfl_dfs.inference import tail_shadow

    monkeypatch.setattr(tail_shadow, "upcoming_season_week",
                        lambda: (2026, 1, date(2026, 9, 13)))
    written: list[pd.DataFrame] = []

    def query_df(sql, params=None):
        if "live_candidates_shadow" in sql:
            assert "run_type = 'live_shadow'" in sql
            return rows.copy()
        return pd.DataFrame()  # no portfolio run frozen yet

    monkeypatch.setattr(bq, "query_df", query_df)
    monkeypatch.setattr(bq, "load_dataframe",
                        lambda df, table, write_disposition=None: written.append(df))
    return written


def test_panel_id_recognises_the_route_treatment():
    from nfl_dfs.research.live_shadow_portfolios import _panel_started_at

    stamp = _panel_started_at(
        "live-shadow-tail_k1_route_roleunion-2026w05-20261011T152000Z")
    assert stamp == pd.Timestamp("2026-10-11T15:20:00Z")
    with pytest.raises(ValueError):
        _panel_started_at("dryrun-live-shadow-tail_k1_roleunion-2026w05-20261011T152000Z")


def test_freeze_works_with_route_rows_present(monkeypatch):
    """Before 2026-10-05 a single treatment row made freeze() raise on its panel id."""
    from nfl_dfs.research import live_shadow_portfolios as lsp

    rows = pd.concat([
        _panel("tail_k1"), _panel("tail_k1_nofloor"), _panel("tail_k1_roleunion"),
        _panel("tail_k3"),
        _route_panel("tail_k1_route_roleunion", "frozen-2026-08"),
    ], ignore_index=True)
    written = _old_freeze_world(monkeypatch, rows)
    result = lsp.freeze("early")
    assert result["idempotent"] is False
    assert len(written) == 1
    assert set(written[0].source_model) == {
        "tail_k1", "tail_k1_nofloor", "tail_k1_roleunion", "tail_k3"}


@pytest.mark.parametrize("contract", ["companion-v1", "frozen-2026-08"])
def test_freeze_route_share_pair_books_both_arms(monkeypatch, contract):
    from nfl_dfs.research import live_shadow_portfolios as lsp

    rows = pd.concat([
        _panel("tail_k1"), _panel("tail_k3"),
        _route_panel("tail_k1_roleunion", contract),
        _route_panel("tail_k1_route_roleunion", contract),
        # an older treatment run in the same slot loses to the latest
        _route_panel("tail_k1_route_roleunion", contract, stamp="2026-09-13T15:21:00Z"),
    ], ignore_index=True)
    written = _old_freeze_world(monkeypatch, rows)
    result = lsp.freeze_route_share_pair("early")
    assert result == {"portfolio_run_id": "live-route-share-pair-2026w01-early",
                      "rows": 160, "route_share_contract": contract,
                      "idempotent": False}
    books = written[0]
    assert set(books.policy_version) == {lsp.ROUTE_PAIR_POLICY_VERSION[contract]}
    assert books.groupby("portfolio_id").size().to_dict() == {
        lsp.ROUTE_CONTROL_COVERAGE: 80, lsp.ROUTE_TREATMENT_COVERAGE: 80}
    treatment = books[books.portfolio_id.eq(lsp.ROUTE_TREATMENT_COVERAGE)]
    assert set(treatment.source_model) == {"tail_k1_route_roleunion"}
    assert set(treatment.source_panel_run_id) == {
        "live-shadow-tail_k1_route_roleunion-2026w01-20260913T153000Z"}


def test_route_pair_refuses_mixed_contracts():
    from nfl_dfs.research.live_shadow_portfolios import build_route_share_books

    with pytest.raises(ValueError, match="different contracts"):
        build_route_share_books(
            _route_panel("tail_k1_roleunion", "companion-v1"),
            _route_panel("tail_k1_route_roleunion", "frozen-2026-08"),
            portfolio_run_id="x", snapshot_slot="early")


def test_route_pair_refuses_arms_that_differ_outside_the_variant():
    from nfl_dfs.research.live_shadow_portfolios import build_route_share_books

    treatment = _route_panel("tail_k1_route_roleunion", "companion-v1")
    treatment["lever_env"] = treatment.lever_env + ",OWN_MODEL=x"
    with pytest.raises(ValueError, match="outside MODEL_REGISTRY_VARIANT"):
        build_route_share_books(
            _route_panel("tail_k1_roleunion", "companion-v1"), treatment,
            portfolio_run_id="x", snapshot_slot="early")


@pytest.mark.parametrize("old,new", [
    ("N_CE=0", "N_CE=12"),
    ("GEN_TOTAL_BUDGET=172", "GEN_TOTAL_BUDGET=52"),
    ("SERVED_POSITION_SCALES=QB:0.970,RB:1.005,TE:0.940,WR:1.070",
     "SERVED_POSITION_SCALES=QB:0.970,RB:1.005,TE:0.940"),
])
def test_companion_panel_with_wrong_settings_is_refused(old, new):
    panel = _route_panel("tail_k1_route_roleunion", "companion-v1")
    assert panel.lever_env.str.contains(old, regex=False).all()
    panel["lever_env"] = panel.lever_env.str.replace(old, new, regex=False)
    with pytest.raises(ValueError, match="wrong role provenance for companion-v1"):
        validate_shadow_panel(panel, "tail_k1_route_roleunion")


def test_companion_panel_with_too_few_worlds_is_refused():
    panel = _route_panel("tail_k1_roleunion", "companion-v1")
    panel["n_worlds"] = 10_000
    with pytest.raises(ValueError, match="30000 worlds"):
        validate_shadow_panel(panel, "tail_k1_roleunion")
