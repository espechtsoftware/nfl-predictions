from __future__ import annotations

import base64
import json
from pathlib import Path
import zlib

import numpy as np
import pytest

from nfl_dfs.analysis import route_rank_dependence_r2 as r2


ROOT = Path(__file__).parents[1]


def test_midpoint_rank_remap_preserves_exact_control_marginals():
    control = np.array([
        [0.0, 10.0, 20.0, 30.0],
        [2.5, 1.5, 4.5, 3.5],
    ])
    route = np.array([
        [100.0, 0.0, 0.0, 0.0],
        [0.0, 10.0, 0.0, 10.0],
    ])
    treatment = r2.midpoint_rank_remap(control, route)
    assert treatment[0].tolist() == [30.0, 0.0, 10.0, 20.0]
    assert np.array_equal(
        np.sort(treatment, axis=1, kind="stable"),
        np.sort(control, axis=1, kind="stable"),
    )
    assert np.allclose(
        treatment.mean(axis=1), control.mean(axis=1), rtol=0, atol=1e-12)


def test_midpoint_rank_remap_is_stable_and_deterministic_on_ties():
    control = np.array([[3.0, 1.0, 4.0, 2.0]])
    route = 10.0 - control
    first = r2.midpoint_rank_remap(control, route)
    second = r2.midpoint_rank_remap(control, route)
    assert np.array_equal(first, second)
    assert first.tolist() == [[1.0, 2.0, 3.0, 4.0]]


@pytest.mark.parametrize(
    "control,route",
    [
        (np.ones(4), np.ones((1, 4))),
        (np.ones((1, 4)), np.ones((2, 4))),
        (np.array([[np.nan]]), np.ones((1, 1))),
    ],
)
def test_midpoint_rank_remap_rejects_invalid_draws(control, route):
    with pytest.raises(ValueError, match="R2 control and Route draws"):
        r2.midpoint_rank_remap(control, route)


def test_r2_report_chunks_round_trip_and_normalize_numpy(monkeypatch):
    monkeypatch.setattr(r2, "OUTPUT_CHUNK_SIZE", 100)
    report = {
        "passes": np.bool_(True),
        "values": np.arange(200, dtype=np.int64),
    }
    lines = r2.encoded_report_lines(report)
    chunks = {}
    total = None
    for line in lines:
        header, chunk = line.removeprefix(r2.OUTPUT_CHUNK_PREFIX).split(":", 1)
        index, total = map(int, header.split("/"))
        chunks[index] = chunk
    encoded = "".join(chunks[index] for index in range(1, total + 1))
    decoded = json.loads(zlib.decompress(base64.b64decode(encoded)))
    assert decoded == {"passes": True, "values": list(range(200))}


def test_r2_cloud_path_is_fixed_midpoint_and_fail_closed():
    launch = (ROOT / "scripts/cloud_route_rank_dependence_r2.sh").read_text()
    finish = (
        ROOT / "scripts/cloud_finish_route_rank_dependence_r2.sh"
    ).read_text()
    protocol = (
        ROOT / "reports/2026-08-14-route-rank-r2-shrinkage-protocol.md"
    ).read_text()
    assert "midpoint_weight=0.5" in launch
    assert "ROUTE_RANK_R2_PANEL_ID" in launch
    assert "sorted_marginal_tolerance=1e-10" in launch
    assert "ROUTE_RANK_DEPENDENCE_R2_CHUNK=" in finish
    assert "route-rank-dependence-r2-passes" in finish
    assert "one natural midpoint shrinkage value" in protocol
