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
    is_k1 = model in {"tail_k1", "tail_k1_nofloor"}
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
                f"MIN_LINEUP_SALARY={floor}"),
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
        _panel("tail_k1"), _panel("tail_k1_nofloor"), _panel("tail_k3"),
        portfolio_run_id="live-tail-portfolios-2026w01-early",
        snapshot_slot="early",
        frozen_at=datetime(2026, 9, 13, 16, 5, tzinfo=timezone.utc),
    )
    assert set(memberships.portfolio_id) == {
        K1_COVERAGE, K1_COVERAGE_187, K1_COVERAGE_200,
        K1_EXTREME_LEX, K1_TOP_P, K1_NOFLOOR_COVERAGE, K1_REFINED,
        K3_COVERAGE, MIX_20_60}
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
        _panel("tail_k3", stamp="2026-09-13T16:20:00Z"),
    ])
    rows = pd.concat(
        [old_k1, new_k1, nofloor, k3, late], ignore_index=True)
    chosen_k1, chosen_nofloor, chosen_k3 = choose_latest_panels(
        rows, season=2026, week=1, target_sunday=date(2026, 9, 13),
        snapshot_slot="early")
    assert chosen_k1.panel_run_id.nunique() == 1
    assert chosen_k1.panel_run_id.iloc[0].endswith("20260913T153500Z")
    assert chosen_nofloor.panel_run_id.iloc[0].endswith("20260913T153300Z")
    assert chosen_k3.panel_run_id.iloc[0].endswith("20260913T153400Z")


def test_scores_frozen_memberships_and_fails_on_missing_actual():
    memberships = build_portfolios(
        _panel("tail_k1"), _panel("tail_k1_nofloor"), _panel("tail_k3"),
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
    assert len(grades) == 9
    assert grades.n_entries.eq(80).all()
    assert grades.weekly_max.eq(9.0).all()
    summary = summarize_grades(grades)
    assert len(summary) == 9
    assert summary.ge_200.eq(0).all()
    assert summary.mean_weekly_max.eq(9.0).all()
    with pytest.raises(ValueError, match="missing actuals"):
        score_portfolios(memberships, actuals.iloc[1:])
