from datetime import datetime, timedelta, timezone
import pandas as pd
from nfl_dfs.inference.market_monitor import assess_batch


def _rows(gen, sources):
    return pd.DataFrame({"generated_at": [gen] * len(sources), "gsis_id": [f"g{i}" for i in range(len(sources))], "display_name": [f"P{i}" for i in range(len(sources))],
                         "position": ["DST" if s == "model_only_dst" else "WR" for s in sources], "source": sources, "market_points": [1.0] * len(sources), "proj_points": [2.0] * len(sources)})


def test_fresh_batch_with_props_is_ok():
    now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
    v = assess_batch(_rows(now - timedelta(minutes=30), ["props"] * 7 + ["model_only_no_line", "model_only_dst"]), now=now)
    assert v["ok"] and v["counts"]["props"] == 7 and v["model_only_names"] == ["P7"] and v["line"].startswith("OK")


def test_stale_low_coverage_and_unmatched_fail():
    now = datetime(2026, 9, 26, 15, 0, tzinfo=timezone.utc)
    stale = assess_batch(_rows(now - timedelta(hours=5), ["props"] * 5), now=now); assert not stale["ok"] and "min old" in stale["line"]
    low = assess_batch(_rows(now, ["props"] + ["model_only_no_line"] * 9), now=now); assert not low["ok"] and "props cover" in low["line"]
    bad = assess_batch(_rows(now, ["props"] * 5 + ["unmatched_in_feed"]), now=now); assert not bad["ok"] and "unmatched_in_feed" in bad["line"]
    empty = assess_batch(pd.DataFrame(), now=now); assert not empty["ok"] and "no batch" in empty["line"]
