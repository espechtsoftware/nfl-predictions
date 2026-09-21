from datetime import datetime, timedelta, timezone
import pandas as pd
from nfl_dfs.inference.build_inputs import assess_files, assess_projections, assess_tabpfn, verdict


def test_projection_batch_freshness_and_coverage():
    now = datetime(2026, 9, 26, 15, 30, tzinfo=timezone.utc)
    fresh = pd.DataFrame({"generated_at": [now - timedelta(minutes=20)] * 320, "gsis_id": [f"g{i}" for i in range(320)], "position": ["WR"] * 300 + ["DST"] * 20, "proj_points": [10.0] * 320})
    assert assess_projections(fresh, now=now)["ok"]
    stale = fresh.assign(generated_at=now - timedelta(hours=3)); assert "min old" in assess_projections(stale, now=now)["reason"]
    thin = fresh.head(100); assert "skill rows" in assess_projections(thin, now=now)["reason"]
    assert not assess_projections(pd.DataFrame(), now=now)["ok"]


def test_tabpfn_and_files():
    assert assess_tabpfn(400, [1, 2, 3], target_week=3)["ok"]
    assert "no rows" in assess_tabpfn(0, [1, 2], target_week=3)["reason"]
    assert "beyond the target" in assess_tabpfn(400, [1, 2, 3, 4], target_week=3)["reason"]
    good = assess_files({"CHOSEN_LEV": "2560", "CHOSEN_BOOM": "10240"}, [{"name": "milly", "contest_id": "1", "entries": 1}, {"name": "flea", "contest_id": "2", "entries": 96}])
    assert good["ok"]
    assert "chosen-dose" in assess_files(None, [{"name": "m", "contest_id": "1", "entries": 97}])["reason"]
    assert "minimum" in assess_files({"CHOSEN_LEV": "1", "CHOSEN_BOOM": "1"}, [{"name": "m", "contest_id": "1", "entries": 10}])["reason"]


def test_verdict_names_every_failing_check():
    v = verdict({"ok": True}, {"ok": False, "line": "monitor absent"}, {"ok": True}, {"ok": False, "reason": "no contests"})
    assert v["status"] == "FAIL" and len(v["reasons"]) == 2 and any("monitor absent" in r for r in v["reasons"])
    assert verdict({"ok": True}, {"ok": True}, {"ok": True}, {"ok": True})["status"] == "OK"
