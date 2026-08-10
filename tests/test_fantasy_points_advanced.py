import csv

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import fantasy_points_advanced_tail as diagnostic
from nfl_dfs.ingest import fantasy_points_advanced as ingest


def _snapshots() -> pd.DataFrame:
    return pd.DataFrame([
        {"season": season, "gsis_id": "qb-1", "name": "Test Quarterback",
         "pos": "QB", "team": "BAL"}
        for season in range(2022, 2026)
    ] + [
        {"season": season, "gsis_id": "wr-1", "name": "Test Receiver",
         "pos": "WR", "team": "BAL"}
        for season in range(2022, 2026)
    ])


def _record(season=2022, family="passing", name="Test Quarterback",
            pos="QB", team="BLT", metrics=None):
    return {
        "season": season,
        "family": family,
        "vendor_name": name,
        "vendor_team": team,
        "vendor_pos": pos,
        "source_file": "source.csv",
        "source_sha256": "hash",
        "source_row": 3,
        "metrics": metrics or {"fp_adv_qb_cpoe": 0.05},
    }


def test_grouped_parser_preserves_repeated_headers_by_group(tmp_path):
    path = tmp_path / "grouped.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Player Details", "", "Zone Concept", "Man/Gap Concept"])
        writer.writerow(["Name", "Season", "ATT", "ATT"])
        writer.writerow(["Test Player", "2022", "10", "20"])
    columns, rows = ingest._grouped_rows(path)
    assert columns == [
        "Player Details::Name", "Player Details::Season",
        "Zone Concept::ATT", "Man/Gap Concept::ATT",
    ]
    assert rows[0]["Zone Concept::ATT"] == "10"
    assert rows[0]["Man/Gap Concept::ATT"] == "20"


def test_normalize_records_resolves_identity_and_suppresses_known_split():
    rows, audit = ingest.normalize_records(
        [_record(), _record(family="receiving", name="Brock Wright",
                            pos="TE", team="DET",
                            metrics={"fp_adv_rec_tprr": 0.2}),
         _record(family="receiving", name="Brock Wright", pos="TE", team="DET",
                 metrics={"fp_adv_rec_tprr": 0.3})],
        pd.concat([_snapshots(), pd.DataFrame([
            {"season": 2022, "gsis_id": "te-1", "name": "Brock Wright",
             "pos": "TE", "team": "DET"},
        ])], ignore_index=True),
    )
    assert audit["duplicate_groups_coalesced"] == 1
    assert rows[rows.family.eq("passing")].iloc[0].gsis_id == "qb-1"
    split = rows[rows.family.eq("receiving")].iloc[0]
    assert split.split_duplicate
    assert pd.isna(split.fp_adv_rec_tprr)


def test_previous_season_join_never_uses_same_or_stale_season():
    history = []
    for season, value in ((2022, 0.1), (2023, 0.2), (2024, 0.3)):
        row = {
            "season": season, "family": "receiving", "gsis_id": "wr-1",
            "resolution_status": "resolved",
            **{column: np.nan for column in ingest.FEATURE_COLUMNS},
        }
        row["fp_adv_rec_tprr"] = value
        history.append(row)
    targets = pd.DataFrame([
        {"season": 2023, "week": 1, "gsis_id": "wr-1", "pos": "WR"},
        {"season": 2024, "week": 18, "gsis_id": "wr-1", "pos": "WR"},
    ])
    out = diagnostic.attach_previous_season_advanced(
        targets, pd.DataFrame(history))
    assert out.fp_adv_source_season.tolist() == [2022, 2023]
    assert out.fp_adv_rec_tprr.tolist() == pytest.approx([0.1, 0.2])
    assert out.fp_adv_receiving_present.all()


def test_previous_season_join_does_not_claim_source_for_unmatched_player():
    history = pd.DataFrame([{
        "season": 2022, "family": "receiving", "gsis_id": "wr-1",
        "resolution_status": "resolved",
        **{column: np.nan for column in ingest.FEATURE_COLUMNS},
    }])
    targets = pd.DataFrame([{
        "season": 2023, "week": 1, "gsis_id": "wr-missing", "pos": "WR",
    }])
    out = diagnostic.attach_previous_season_advanced(targets, history)
    assert pd.isna(out.iloc[0].fp_adv_source_season)
    assert not out.iloc[0].fp_adv_receiving_present


def test_score_reports_events_and_stable_calibration_deciles():
    rows = pd.DataFrame({
        "actual": [10.0, 20.0, 30.0, 40.0],
        "control_score": [11.0, 21.0, 31.0, 41.0],
        "treatment_score": [10.0, 20.0, 30.0, 40.0],
        "control_tail_20": [0.1, 0.4, 0.7, 0.9],
        "treatment_tail_20": [0.1, 0.5, 0.8, 0.9],
        "control_tail_30": [0.05, 0.2, 0.6, 0.8],
        "treatment_tail_30": [0.05, 0.1, 0.7, 0.9],
    })
    report = diagnostic._score(rows, "test")
    assert report["events_20"] == 3
    assert report["events_30"] == 2
    assert len(report["control_calibration_deciles_30"]) == 4
    assert sum(
        row["rows"] for row in report["treatment_calibration_deciles_30"]
    ) == 4


def test_advanced_gate_is_tail_first_with_position_and_fold_safeguards():
    folds = [
        {"control_brier_30": 0.020, "treatment_brier_30": 0.019},
        {"control_brier_30": 0.022, "treatment_brier_30": 0.0221},
    ]
    positions = [
        {"control_brier_30": 0.020, "treatment_brier_30": 0.019},
        {"control_brier_30": 0.021, "treatment_brier_30": 0.020},
        {"control_brier_30": 0.022, "treatment_brier_30": 0.0221},
    ]
    aggregate = {"control_brier_30": 0.021, "treatment_brier_30": 0.0205}
    coverage = {
        (season, pos): 0.61
        for season in diagnostic.HELD_OUT_SEASONS
        for pos in ("QB", "RB", "WR", "TE")
    }
    assert diagnostic.advanced_gate(
        folds, positions, coverage, aggregate)["passes"]
    coverage[(2024, "TE")] = 0.59
    assert not diagnostic.advanced_gate(
        folds, positions, coverage, aggregate)["passes"]
