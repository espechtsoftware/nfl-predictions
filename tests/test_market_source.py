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
    assert list(log.columns) == ["generated_at", "season", "week", "gsis_id", "display_name", "position", "source", "market_points", "path", "proj_points"]
    assert len(log) == 5 and log.week.eq(3).all() and log.path.eq("project-slate").all() and log.proj_points.tolist() == [0, 1, 2, 3, 4]


def test_thin_line_resolved_player_is_model_only_and_recorded_not_raised():
    # Backup Guy's feed lines resolved to his gsis_id but price only an anytime-TD market (below the >=2 boundary):
    # a thin line, not a name miss (2026-09-23: 172 such main-slate players on the Week-2 Sunday feed).
    market, src = resolve_live_market(
        _feats(), _market(("00-0036322", 16.4), ("00-0036358", 16.7)),
        {"Justin Jefferson", "CeeDee Lamb", "Backup Guy"},
        resolved_ids={"00-0036322", "00-0036358", "00-0040002"})
    by = src.set_index("display_name").source
    assert by["Backup Guy"] == "model_only_no_line_thin"
    assert np.isnan(market[3]) and by["Ladd McConkey"] == "model_only_no_line"
    assert by["Backup Guy"].startswith("model_only_no_line")   # the gate checker and exposure flags key on this prefix


def test_thin_line_does_not_excuse_a_name_miss():
    # Jefferson is in the feed but resolved to no gsis_id (the Week-2 ambiguous-name drop): still fails closed
    # even when other players are thin-lined.
    with pytest.raises(MarketMatchError, match="Justin Jefferson"):
        resolve_live_market(_feats(), _market(("00-0036358", 16.7)),
                            {"Justin Jefferson", "CeeDee Lamb", "Backup Guy"},
                            resolved_ids={"00-0036358", "00-0040002"})


def test_without_resolved_ids_a_thin_line_still_fails_closed():
    # The default keeps the original behaviour for callers that have not opted in.
    with pytest.raises(MarketMatchError, match="Backup Guy"):
        resolve_live_market(_feats(), _market(("00-0036322", 16.4), ("00-0036358", 16.7)),
                            {"Justin Jefferson", "CeeDee Lamb", "Backup Guy"})
