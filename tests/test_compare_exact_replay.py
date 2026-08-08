import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


spec = importlib.util.spec_from_file_location(
    "compare_exact_replay",
    Path(__file__).parents[1] / "scripts" / "compare_exact_replay.py")
compare = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(compare)


def test_frame_report_requires_exact_values_and_keys():
    source = pd.DataFrame([
        {"season": 2025, "week": 1, "id": "a", "score": 1.0},
        {"season": 2025, "week": 1, "id": "b", "score": None},
    ])
    report, failures = compare._frame_report(
        source, source.copy(), ["season", "week", "id"], ["score"])
    assert failures == []
    assert report["common_rows"] == 2
    assert report["mismatch_counts"]["score"] == 0

    changed = source.copy()
    changed.loc[changed.id.eq("a"), "score"] += 0.000001
    _, failures = compare._frame_report(
        source, changed, ["season", "week", "id"], ["score"])
    assert "score differs in 1 rows" in failures


def test_frame_report_allows_only_registered_numeric_roundoff():
    source = pd.DataFrame([{"id": "a", "score": 100.0}])
    close = pd.DataFrame([{"id": "a", "score": 100.00002}])
    report, failures = compare._frame_report(
        source, close, ["id"], ["score"], {"score": 1e-4})
    assert failures == []
    assert report["max_abs_deltas"]["score"] < 1e-4

    far = pd.DataFrame([{"id": "a", "score": 100.001}])
    _, failures = compare._frame_report(
        source, far, ["id"], ["score"], {"score": 1e-4})
    assert "score differs in 1 rows" in failures


def test_frame_report_rejects_missing_and_duplicate_keys():
    source = pd.DataFrame([
        {"id": "a", "score": 1.0},
        {"id": "b", "score": 2.0},
    ])
    _, failures = compare._frame_report(
        source, source.iloc[:1].copy(), ["id"], ["score"])
    assert "reference has 1 keys absent from candidate" in failures

    duplicate = pd.concat([source, source.iloc[:1]], ignore_index=True)
    _, failures = compare._frame_report(
        source, duplicate, ["id"], ["score"])
    assert "candidate frame has duplicate keys" in failures


def test_array_report_requires_full_exact_world_matrix():
    source = {
        "cand_ix": np.array([0, 1], dtype=np.int32),
        "totals": np.array([[180.0, 200.0], [190.0, 210.0]],
                           dtype=np.float32),
    }
    report, failures = compare._array_report(
        source, {name: value.copy() for name, value in source.items()})
    assert failures == []
    assert report["totals"]["exact"] is True

    changed = {name: value.copy() for name, value in source.items()}
    changed["totals"][0, 0] += 0.01
    report, failures = compare._array_report(source, changed)
    assert "artifact member totals differs" in failures
    assert report["totals"]["max_abs_delta"] > 0


def test_artifacts_are_aligned_by_roster_not_candidate_index():
    source_rows = pd.DataFrame([
        {"players": "A,B", "cand_ix": 0},
        {"players": "C,D", "cand_ix": 1},
    ])
    candidate_rows = pd.DataFrame([
        {"players": "C,D", "cand_ix": 0},
        {"players": "A,B", "cand_ix": 1},
    ])
    source = {
        "cand_ix": np.array([0, 1], dtype=np.int32),
        "totals": np.array([[180.0, 200.0], [190.0, 210.0]],
                           dtype=np.float32),
        "tail_line": np.array(194.0, dtype=np.float32),
    }
    candidate = {
        "cand_ix": np.array([0, 1], dtype=np.int32),
        "totals": source["totals"][[1, 0]],
        "tail_line": source["tail_line"].copy(),
    }
    left, right, moved, failures = compare._align_artifacts_by_roster(
        source_rows, candidate_rows, source, candidate)
    assert failures == []
    assert moved == 2
    _, failures = compare._array_report(left, right)
    assert failures == []


def test_artifact_alignment_rejects_roster_difference():
    source_rows = pd.DataFrame([{"players": "A,B", "cand_ix": 0}])
    candidate_rows = pd.DataFrame([{"players": "C,D", "cand_ix": 0}])
    arrays = {
        "cand_ix": np.array([0], dtype=np.int32),
        "totals": np.array([[180.0]], dtype=np.float32),
        "tail_line": np.array(194.0, dtype=np.float32),
    }
    _, _, _, failures = compare._align_artifacts_by_roster(
        source_rows, candidate_rows, arrays, arrays)
    assert "artifact roster universes differ" in failures
