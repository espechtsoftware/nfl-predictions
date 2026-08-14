from __future__ import annotations

import base64
import json
from pathlib import Path
import zlib

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import tabpfn_route_channel_final_served as final_served
from nfl_dfs.backtest import replay
from nfl_dfs.research.sis_asoe_final_served import FROZEN_BETA


ROOT = Path(__file__).parents[1]


def _served_folds() -> dict[int, tuple[pd.DataFrame, np.ndarray]]:
    folds = {}
    offsets = np.linspace(-8.0, 8.0, 10_000)
    for season in (2022, 2023, 2024, 2025):
        rows = []
        draws = []
        for pos_index, position in enumerate(("QB", "RB", "WR", "TE")):
            for row_index in range(2):
                center = 12.0 + 4 * pos_index + row_index
                rows.append({
                    "season": season,
                    "week": row_index + 1,
                    "gsis_id": f"{season}-{position}-{row_index}",
                    "position": position,
                    "actual": center + (3 if row_index else -2),
                    "market_covered": True,
                    "tabpfn_covered": True,
                })
                draws.append(center + offsets)
        folds[season] = (pd.DataFrame(rows), np.asarray(draws))
    return folds


def test_route_gate_reports_registered_primary_metrics(monkeypatch):
    monkeypatch.setattr(final_served, "EXPECTED_PRIMARY_ROWS", {
        2023: 6, 2024: 6, 2025: 6,
    })
    control = _served_folds()
    marginal = {
        season: (frame.copy(), draws.copy())
        for season, (frame, draws) in control.items()
    }
    report = final_served.evaluate_route_arms(control, marginal)
    assert not report["gate"]["passes"]
    assert report["proper_score_ratios"][
        "equal_position_equal_quantile_mean_ratio"] == pytest.approx(1.0)
    assert set(report["control"]["positions"]) == {"RB", "WR", "TE"}
    assert "brier_25" in report["control"]["aggregate"]
    assert "reliability_gap_25" in report["control"]["aggregate"]
    assert "pinball_q99" in report["paired_loss_uncertainty"]


def test_phase_s_asoe_branch_is_explicit_and_exact():
    assert final_served.selected_asoe_law({
        "TABPFN_ROUTE_PHASE_S_ARM": "control",
    }) == {"selected_arm": "control", "enabled": False, "beta": None}
    assert final_served.selected_asoe_law({
        "TABPFN_ROUTE_PHASE_S_ARM": "treatment",
        "SIS_ASOE_TARGET_ALLOCATION": "1",
        "SIS_ASOE_BETA": str(FROZEN_BETA),
    })["enabled"] is True
    with pytest.raises(ValueError, match="stray ASOE"):
        final_served.selected_asoe_law({
            "TABPFN_ROUTE_PHASE_S_ARM": "control",
            "SIS_ASOE_TARGET_ALLOCATION": "1",
        })
    with pytest.raises(ValueError, match="frozen beta"):
        final_served.selected_asoe_law({
            "TABPFN_ROUTE_PHASE_S_ARM": "treatment",
            "SIS_ASOE_TARGET_ALLOCATION": "1",
            "SIS_ASOE_BETA": "0.1",
        })


def test_cache_tables_are_research_licensed_and_context_restores(monkeypatch):
    monkeypatch.setenv("TABPFN_MARGINAL_TABLE", "outside")
    for table in final_served.TABLES.values():
        assert replay._tabpfn_marginal_table(
            {"TABPFN_MARGINAL_TABLE": table}) == table
        with final_served._cache_environment(table):
            assert replay._tabpfn_marginal_table() == table
        assert final_served.os.environ["TABPFN_MARGINAL_TABLE"] == "outside"


def test_route_report_chunks_round_trip_below_log_limit(monkeypatch):
    monkeypatch.setattr(final_served, "OUTPUT_CHUNK_SIZE", 100)
    report = {"rows": [
        {"value": index, "detail": f"row-{index:06d}"}
        for index in range(200)
    ]}
    lines = final_served.encoded_report_lines(report)
    assert len(lines) > 1
    assert max(map(len, lines)) < 100_000
    chunks = {}
    for line in lines:
        header, chunk = line.removeprefix(
            final_served.OUTPUT_CHUNK_PREFIX).split(":", 1)
        index, total = map(int, header.split("/"))
        chunks[index] = chunk
    encoded = "".join(chunks[index] for index in range(1, total + 1))
    assert json.loads(zlib.decompress(base64.b64decode(encoded))) == report


def test_cloud_gate_requires_phase_s_and_cache_completion():
    launch = (
        ROOT / "scripts/cloud_tabpfn_route_channel_final_served_i1.sh"
    ).read_text()
    finish = (
        ROOT / "scripts/cloud_finish_tabpfn_route_channel_final_served_i1.sh"
    ).read_text()
    retry = (
        ROOT / "scripts/cloud_retry_tabpfn_route_channel_final_served_i1.sh"
    ).read_text()
    assert "tabpfn-route-channel-caches-valid" in launch
    assert "Phase S mechanical audit did not pass" in launch
    assert "TABPFN_ROUTE_PHASE_S_ARM" in launch
    assert "equal-position-equal-q95-q99" in launch
    assert "TABPFN_ROUTE_CHANNEL_FINAL_SERVED_CHUNK=" in finish
    assert "retry_execution.txt" in finish
    assert "configured memory limit was reached" in retry
    assert "--memory 32Gi" in retry
