from __future__ import annotations

import base64
import json
from pathlib import Path
import zlib

import numpy as np
import pytest

from nfl_dfs.analysis import g1_archetype_topology as g1
from nfl_dfs.analysis import route_rank_dependence_i1 as rank_gate
from nfl_dfs.analysis.fantasy_points_route_share import ROUTE_FEATURES


ROOT = Path(__file__).parents[1]


def _g0(gap: float) -> dict:
    cells = {}
    for name in ("multiplicity_ge2", "multiplicity_ge3"):
        cells[name] = {
            "kind": "multiplicity", "supported": True,
            "log_simulated_to_realized": gap,
        }
    for name in ("qb_wr", "qb_te", "qb_rb", "wr_wr"):
        cells[name] = {
            "kind": "conditional", "supported": True,
            "log_simulated_to_realized": gap,
        }
    return {"cells": cells}


def _broad(gap: float) -> dict:
    return {
        name: {
            "supported": True,
            "log_simulated_to_realized": gap,
        }
        for name in g1.PRIMARY_RELATIONSHIPS
    }


def _scorecard(value: float) -> dict:
    rows = {
        name: {
            "joint_q90_brier": value,
            "variogram_p0_5": value,
        }
        for name in g1.PRIMARY_RELATIONSHIPS
    }
    rows["overall"] = {
        "joint_q90_brier": value,
        "variogram_p0_5": value,
    }
    return rows


def test_dependence_gate_uses_all_five_families_and_relationship_guards():
    result = rank_gate.dependence_gate(
        _g0(1.0), _g0(0.8), _broad(1.0), _broad(0.8),
        _scorecard(1.0), _scorecard(0.9), 0.0,
    )
    assert result["checks"]["passes"]
    assert set(result["family_ratios"]) == set(rank_gate.FAMILY_NAMES)
    assert len(result["improving_families"]) == 5

    failed = rank_gate.dependence_gate(
        _g0(1.0), _g0(0.8), _broad(1.0), _broad(0.8),
        _scorecard(1.0), _scorecard(0.9), 1e-8,
    )
    assert not failed["checks"]["passes"]
    assert not failed["checks"][
        "sorted_marginal_max_abs_delta_at_most_1e_10"]


def test_relationship_material_regression_fails_gate():
    route = _broad(0.8)
    route["QB_WR"]["log_simulated_to_realized"] = 1.3
    result = rank_gate.dependence_gate(
        _g0(1.0), _g0(0.8), _broad(1.0), route,
        _scorecard(1.0), _scorecard(0.9), 0.0,
    )
    assert not result["checks"]["passes"]
    assert "QB_WR" in result["relationship_regressions"]


def test_component_arm_sets_only_registered_route_fields(monkeypatch):
    monkeypatch.delenv("EXTRA_FEATURES", raising=False)
    with rank_gate._component_environment(route=True):
        assert rank_gate.os.environ["EXTRA_FEATURES"] == ",".join(ROUTE_FEATURES)
    assert "EXTRA_FEATURES" not in rank_gate.os.environ
    monkeypatch.setenv("EXTRA_FEATURES", "another-arm")
    with pytest.raises(ValueError, match="inherited an EXTRA_FEATURES"):
        with rank_gate._component_environment(route=True):
            pass


def test_rank_report_chunks_round_trip(monkeypatch):
    monkeypatch.setattr(rank_gate, "OUTPUT_CHUNK_SIZE", 100)
    report = {"rows": [
        {"value": index, "detail": f"row-{index:06d}"}
        for index in range(200)
    ]}
    lines = rank_gate.encoded_report_lines(report)
    chunks = {}
    for line in lines:
        header, chunk = line.removeprefix(
            rank_gate.OUTPUT_CHUNK_PREFIX).split(":", 1)
        index, total = map(int, header.split("/"))
        chunks[index] = chunk
    encoded = "".join(chunks[index] for index in range(1, total + 1))
    assert json.loads(zlib.decompress(base64.b64decode(encoded))) == report


def test_rank_report_chunks_normalize_numpy_results():
    report = {
        "passes": np.bool_(True),
        "count": np.int64(3),
        "losses": np.array([0.2, 0.4]),
    }
    lines = rank_gate.encoded_report_lines(report)
    encoded = "".join(line.split(":", 1)[1] for line in lines)
    decoded = json.loads(zlib.decompress(base64.b64decode(encoded)))
    assert decoded == {"passes": True, "count": 3, "losses": [0.2, 0.4]}


def test_cloud_path_requires_phase_s_and_registered_loss_families():
    launch = (ROOT / "scripts/cloud_route_rank_dependence_i1.sh").read_text()
    finish = (
        ROOT / "scripts/cloud_finish_route_rank_dependence_i1.sh"
    ).read_text()
    retry = (
        ROOT / "scripts/cloud_retry_route_rank_dependence_i1.sh"
    ).read_text()
    protocol = (
        ROOT / "reports/2026-08-14-route-channel-i1-protocol.md"
    ).read_text()
    assert "Phase S mechanical audit did not pass" in launch
    assert "TABPFN_ROUTE_PHASE_S_ARM" in launch
    assert "sorted_marginal_tolerance=1e-10" in launch
    assert "ROUTE_RANK_DEPENDENCE_I1_CHUNK=" in finish
    assert "retry_execution.txt" in finish
    assert "Object of type bool is not JSON serializable" in retry
    assert "numpy-json-transport-only" in retry
    assert "five equally" in protocol
