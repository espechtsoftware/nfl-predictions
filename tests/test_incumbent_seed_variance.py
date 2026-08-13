import importlib.util
from pathlib import Path

import pandas as pd


spec = importlib.util.spec_from_file_location(
    "incumbent_seed_variance",
    Path(__file__).parents[1] / "scripts" /
    "analyze_incumbent_seed_variance.py")
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)


def _frame(scores):
    rows = []
    for week, weekly in enumerate(scores, 1):
        for ix, score in enumerate(weekly):
            rows.append({
                "season": 2025, "week": week, "cand_ix": ix,
                "players": f"{week}-{ix}", "selected": ix < 2,
                "actual_score": score,
                **{f"clear_bits_{t}": "01" for t in audit.MASKS},
            })
    return pd.DataFrame(rows)


def test_support_count_decodes_hex_not_base64():
    assert audit._support_count("00ff") == 8
    assert audit._support_count("8001") == 2
    assert audit._canonical_roster("b,a,c") == "a,b,c"


def test_lever_parser_preserves_comma_valued_fields():
    parsed = audit.lever_values(
        "REPLAY_PROJECTION_SEED=7,ROLE_BELIEF_FEATURES=a,b,c,"
        "SERVED_POSITION_SCALES=QB:1,RB:.9")
    assert parsed == {
        "REPLAY_PROJECTION_SEED": "7",
        "ROLE_BELIEF_FEATURES": "a,b,c",
        "SERVED_POSITION_SCALES": "QB:1,RB:.9",
    }


def test_replicate_metrics_uses_selected_and_pool_oracle():
    metrics, weekly, rosters, pools = audit.replicate_metrics(
        _frame([[190.0, 210.0, 230.0], [180.0, 195.0, 205.0]]))
    assert weekly.tolist() == [210.0, 195.0]
    assert metrics["selected_tail"]["200"] == 1
    assert metrics["oracle_tail"]["220"] == 1
    assert sum(map(len, rosters.values())) == 4
    assert sum(map(len, pools.values())) == 6


def test_seed_report_applies_frozen_range_labels():
    frames = []
    for replicate, bump in zip(audit.PANELS, (0, 0, 0, 0, 0)):
        frame = _frame([[210 + bump, 200, 190], [220, 180, 170]])
        frame["replicate"] = replicate
        frames.append(frame)
    report = audit.seed_report(pd.concat(frames, ignore_index=True))
    assert report["interpretation"] == "stable"
    assert len(report["pairwise"]) == 10
