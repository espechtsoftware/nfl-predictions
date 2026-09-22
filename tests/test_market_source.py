"""No silent market stand-in: fail closed on a feed-present name miss, record every model-only row (2026-09-21)."""
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.inference.market_source import MarketMatchError, resolve_live_market, source_log_frame
from nfl_dfs.models.blend import blend


def _feats():
    return pd.DataFrame({
        "gsis_id": ["00-0036322", "00-0036358", "00-0040001", "00-0040002", None],
        "display_name": ["Justin Jefferson", "CeeDee Lamb", "Ladd McConkey", "Backup Guy", "Panthers"],
        "position": ["WR", "WR", "WR", "RB", "DST"],
    })


def _market(*ids_points):
    return pd.DataFrame({"gsis_id": [i for i, _ in ids_points], "market_points": [p for _, p in ids_points]})


def test_matched_rows_use_props_and_no_line_rows_are_model_only_and_recorded():
    market, src = resolve_live_market(_feats(), _market(("00-0036322", 16.4), ("00-0036358", 16.7)),
                                      {"Justin Jefferson", "CeeDee Lamb", "Someone Else"})
    assert market[0] == 16.4 and market[1] == 16.7 and np.isnan(market[2]) and np.isnan(market[3]) and np.isnan(market[4])
    assert src.source.tolist() == ["props", "props", "model_only_no_line", "model_only_no_line", "model_only_dst"]
    blended = blend(np.array([18.1, 11.0, 17.0, 9.0, 8.0]), market, 0.45)
    assert blended[0] == pytest.approx(0.45 * 18.1 + 0.55 * 16.4) and blended[2] == 17.0 and blended[4] == 8.0


def test_name_in_feed_but_unmatched_fails_closed():
    with pytest.raises(MarketMatchError, match="Justin Jefferson"):
        resolve_live_market(_feats(), _market(("00-0036358", 16.7)), {"Justin Jefferson", "CeeDee Lamb"})


def test_feed_present_but_low_coverage_fails_closed():
    filler = pd.DataFrame({"gsis_id": [f"00-005{i:04d}" for i in range(15)], "display_name": [f"Filler Player{i}" for i in range(15)], "position": ["WR"] * 15})
    feats = pd.concat([_feats(), filler], ignore_index=True)          # 19 non-DST rows, one matched
    with pytest.raises(MarketMatchError, match="matched only"):
        resolve_live_market(feats, _market(("00-0036358", 16.7)), {"CeeDee Lamb"}, min_coverage=0.30)


def test_no_feed_at_all_is_model_only_for_everyone_and_recorded():
    market, src = resolve_live_market(_feats(), _market(), set())
    assert np.isnan(market).all() and set(src.source) == {"model_only_no_feed", "model_only_dst"}


def test_duplicate_market_ids_fail_closed():
    with pytest.raises(MarketMatchError, match="duplicate"):
        resolve_live_market(_feats(), _market(("00-0036358", 16.7), ("00-0036358", 17.0)), {"CeeDee Lamb"})


def test_source_log_frame_shape():
    _, src = resolve_live_market(_feats(), _market(("00-0036322", 16.4), ("00-0036358", 16.7)), {"Justin Jefferson", "CeeDee Lamb"})
    log = source_log_frame(src, season=2026, week=3, proj_points=np.arange(5, dtype=float), path="project-slate")
    # model_points_pre/model_weight added 2026-09-21: the log records the blend's
    # inputs, not only its output, so a row can be checked forward instead of by
    # inverting the weight. Kept as an exact list on purpose -- a silently added
    # or dropped column in a money-path audit record should fail here.
    assert list(log.columns) == ["generated_at", "season", "week", "gsis_id", "display_name", "position", "source", "market_points", "path", "proj_points", "model_points_pre", "model_weight"]
    # not supplied here, so they must be NULL rather than reconstructed
    assert log.model_points_pre.isna().all() and log.model_weight.isna().all()
    assert len(log) == 5 and log.week.eq(3).all() and log.path.eq("project-slate").all() and log.proj_points.tolist() == [0, 1, 2, 3, 4]
