"""O-3 Amendment 1: the weekly decision record's metric, selection and rule."""
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.research import sis_pass_tail_weekly_record as record

LOCK = datetime(2026, 10, 11, 17, 0, tzinfo=timezone.utc)


def _cache(shift: float) -> pd.DataFrame:
    rows = []
    for gsis_id, centre in (("qb", 20.0), ("wr", 12.0), ("rb", 10.0)):
        row = {"season": 2026, "week": 5, "gsis_id": gsis_id}
        for level, column in zip(record.QUANTILE_LEVELS, record.QUANTILE_COLUMNS):
            row[column] = centre + shift + 10 * (level - 0.5)
        rows.append(row)
    return pd.DataFrame(rows)


def _outcomes() -> pd.DataFrame:
    return pd.DataFrame({"season": 2026, "week": 5, "gsis_id": ["qb", "wr", "rb"],
                         "position": ["QB", "WR", "RB"], "dk_points": [21.0, 0.0, 9.0],
                         "was_active": [True, True, True]})


def test_quantile_score_is_a_proper_pinball_average_and_handles_zeros():
    frame = pd.DataFrame({c: [5.0] for c in record.QUANTILE_COLUMNS})
    # A point mass at the outcome scores 0; away from it, the score grows.
    assert record.quantile_score(frame, pd.Series([5.0])).iloc[0] == 0.0
    assert record.quantile_score(frame, pd.Series([0.0])).iloc[0] > 0
    expected = 2 * np.mean([max(t * -5.0, (t - 1) * -5.0) for t in record.QUANTILE_LEVELS])
    assert record.quantile_score(frame, pd.Series([0.0])).iloc[0] == pytest.approx(expected)


def test_distribution_week_is_treatment_minus_control_on_primary_positions():
    same = record.distribution_week(_cache(0), _cache(0), _outcomes())
    assert same["statistic"] == 0 and same["primary_rows"] == 2 and same["rows"] == 3
    mixed = record.distribution_week(_cache(3), _cache(1), _outcomes())
    assert set(mixed["by_position"]) == {"QB", "WR", "RB"}
    # Treatment exactly at the outcomes, control 5 points off: negative = treatment better.
    exact = pd.DataFrame([{"season": 2026, "week": 5, "gsis_id": g,
                           **{c: y for c in record.QUANTILE_COLUMNS}}
                          for g, y in (("qb", 21.0), ("wr", 0.0), ("rb", 9.0))])
    off = exact.copy()
    off[list(record.QUANTILE_COLUMNS)] += 5.0
    better = record.distribution_week(off, exact, _outcomes())
    assert better["statistic"] < 0 and better["by_position"]["QB"]["mean_d"] < 0
    inactive = _outcomes().assign(was_active=[True, False, True])
    assert record.distribution_week(_cache(0), _cache(1), inactive)["primary_rows"] == 1
    with pytest.raises(ValueError, match="different player-weeks"):
        record.distribution_week(_cache(0), _cache(0).iloc[:2], _outcomes())


def _manifest(stamp: str, *, live=True, sha="s", fallbacks=0, books=10) -> dict:
    labels = ["R0", "R1", "R2", "R3", "R4"]
    out = {}
    for i, label in enumerate(labels):
        for arm in ("control", "treatment"):
            members = [[str(p) for p in range(1, 10)]] * 79 + [
                [str(p) for p in range(1, 9)] + ["99" if arm == "treatment" else "98"]]
            out[f"{label}-{arm}"] = {"seed_label": label, "memberships": members,
                                     "panel_run_id": f"run{stamp}-{label.lower()}-{arm}"}
    out = dict(list(out.items())[:books])
    return {"live": live, "dry_run": not live, "generated_at": stamp,
            "contract": {"contract": record.COMPANION_CONTRACT, "settings_sha256": sha},
            "marginal_reads": {"empty_fallbacks": fallbacks}, "books": out}


def test_lineup_week_scores_book_maxima_per_seed():
    points = {str(p): 20.0 for p in range(1, 9)} | {"99": 40.0, "98": 10.0}
    week = record.lineup_week(_manifest("2026-10-11T11:00:00+00:00"), points)
    assert week["seeds"] == 5 and week["statistic"] == pytest.approx(30.0)
    seed = week["per_seed"]["R0"]
    assert seed["treatment"]["max"] == 200.0 and seed["treatment"]["ge_194"] == 1
    assert seed["control"]["max"] == 170.0  # player 9 unscored -> inactive, 0


def test_week_manifest_selection_by_content_identity():
    early = _manifest("2026-10-11T11:00:00+00:00")
    later = _manifest("2026-10-11T12:00:00+00:00")
    picked = record.select_week_manifest(
        [later, dict(early), early], lock_utc=LOCK, settings_sha256="s")
    assert picked["generated_at"] == early["generated_at"]
    for bad in (_manifest("2026-10-11T11:00:00+00:00", live=False),
                _manifest("2026-10-11T11:00:00+00:00", sha="other"),
                _manifest("2026-10-11T11:00:00+00:00", fallbacks=1),
                _manifest("2026-10-11T11:00:00+00:00", books=8),
                _manifest("2026-10-11T18:00:00+00:00")):
        assert record.select_week_manifest([bad], lock_utc=LOCK, settings_sha256="s") is None


def test_one_retry_duplicate_does_not_double_count():
    """Reviewer ruling (f): a retried execution's rows are never counted twice."""
    manifest = _manifest("2026-10-11T11:00:00+00:00")
    panel = manifest["books"]["R0-control"]["panel_run_id"]
    row = {"season": 2026, "week": 5, "players": "[1,2,3,4,5,6,7,8,9]"}
    rows = pd.DataFrame([
        {**row, "panel_run_id": panel, "cand_ix": 0},
        {**row, "panel_run_id": panel, "cand_ix": 0},             # duplicate write
        {**row, "panel_run_id": "runFAILED-r0-control", "cand_ix": 0},  # failed attempt
        {**row, "panel_run_id": "runFAILED-r0-control", "cand_ix": 5,
         "players": "[9,10,11,12,13,14,15,16,17]"},  # failed attempt, another candidate
        {**row, "panel_run_id": panel, "cand_ix": 1, "players": "[2,3,4,5,6,7,8,9,10]"},
    ])
    kept = record.candidates_for_manifest(rows, manifest)
    assert len(kept) == 2
    assert kept.candidate_id.nunique() == 2


def test_decision_rule_floors_looks_and_leave_one_out():
    assert record.decision([-1.0] * 9, look="final", better="lower")["verdict"] == "NO VERDICT"
    assert record.decision([-1.0] * 6, look="interim", better="lower")["verdict"] == "NO VERDICT"
    steady = [-1.0, -1.2, -0.8, -1.1, -0.9, -1.0, -1.05, -0.95, -1.0, -1.1]
    assert record.decision(steady, look="final", better="lower")["verdict"] == "BETTER"
    assert record.decision(steady, look="final", better="higher")["verdict"] == "WORSE"
    noisy = [-1.0, 1.0] * 5
    assert record.decision(noisy, look="final", better="lower")["verdict"] == "NO DIFFERENCE"
    # The interim look is far stricter than the final one.
    modest = [-1.0, -0.2, -0.9, -0.1, -0.8, -0.3, -0.7]
    assert record.decision(modest, look="interim", better="lower")["verdict"] == "NO DIFFERENCE"
    # One huge week cannot carry BETTER alone: every leave-one-out mean must keep the sign.
    carried = [-50.0] + [0.01] * 9
    out = record.decision(carried, look="final", better="lower")
    assert out["verdict"] in ("NO DIFFERENCE",)
