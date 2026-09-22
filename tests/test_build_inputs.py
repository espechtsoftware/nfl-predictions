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
    # 2026-09-22: presence alone is no longer a pass -- the sufficiency floor is derived
    # from the slate, so every call now states the slate it was checked against.
    assert assess_tabpfn(400, [1, 2, 3], target_week=3, expected_rows=480)["ok"]
    assert "no rows" in assess_tabpfn(0, [1, 2], target_week=3, expected_rows=480)["reason"]
    assert "beyond the target" in assess_tabpfn(400, [1, 2, 3, 4], target_week=3, expected_rows=480)["reason"]


def test_a_truncated_tabpfn_cache_is_caught_instead_of_passing_on_presence():
    """The real 2026 week-3 failure: a tabpfn-gen run made before build-features wrote 51
    rows against a 633-skill-player slate, and the old gate went green on rows > 0."""
    truncated = assess_tabpfn(51, [3], target_week=3, expected_rows=633)
    assert not truncated["ok"]
    assert "51 rows" in truncated["reason"] and "633" in truncated["reason"]
    assert truncated["sufficiency_floor"] == 506
    # the same 51 rows passed every check the gate made before the floor existed
    assert 51 > 0 and not [w for w in [3] if w > 3]


def test_a_complete_cache_clears_the_floor_at_historic_coverage():
    """2025 full caches ran 637-800 rows on comparable slates: about one row per skill
    player. A complete cache must not sit near the floor, or the floor is mis-set."""
    for rows, slate in ((877, 813), (633, 633), (750, 780)):
        assert assess_tabpfn(rows, [3], target_week=3, expected_rows=slate)["ok"], (rows, slate)


def test_sufficiency_that_cannot_be_computed_fails_closed(caplog):
    """dk_salaries.week is NULL on every row, so the slate is found by draft group. With no
    draft group the floor cannot be derived -- that must not read as a pass."""
    unchecked = assess_tabpfn(400, [3], target_week=3)
    assert not unchecked["ok"]
    assert "not checkable" in unchecked["reason"]
    assert unchecked["expected_rows"] is None and unchecked["sufficiency_floor"] is None
    assert not assess_tabpfn(400, [3], target_week=3, expected_rows=0)["ok"]
    good = assess_files({"CHOSEN_LEV": "2560", "CHOSEN_BOOM": "10240"}, [{"name": "milly", "contest_id": "1", "entries": 1}, {"name": "flea", "contest_id": "2", "entries": 96}])
    assert good["ok"]
    assert "chosen-dose" in assess_files(None, [{"name": "m", "contest_id": "1", "entries": 97}])["reason"]
    assert "minimum" in assess_files({"CHOSEN_LEV": "1", "CHOSEN_BOOM": "1"}, [{"name": "m", "contest_id": "1", "entries": 10}], min_book_entries=90)["reason"]


def test_an_ordinary_small_week_is_not_refused_as_if_it_were_malformed():
    """The floor was 90 and the operator states he typically will not exceed 90, so an
    89-entry week would have failed closed on Sunday morning with nothing wrong."""
    dose = {"CHOSEN_LEV": "2560", "CHOSEN_BOOM": "10240"}
    for total in (89, 40, 1):
        r = assess_files(dose, [{"name": "milly", "contest_id": "1", "entries": total}])
        assert r["ok"], (total, r["reason"])
    # the real malformations still fail
    assert not assess_files(dose, [])["ok"]
    assert not assess_files(dose, [{"name": "m", "contest_id": "1", "entries": 0}])["ok"]
    assert "contest_id" in assess_files(dose, [{"name": "", "contest_id": "", "entries": 50}])["reason"]
    assert not assess_files(dose, [{"name": "m", "contest_id": "1", "entries": "many"}])["ok"]


def test_verdict_names_every_failing_check():
    v = verdict({"ok": True}, {"ok": False, "line": "monitor absent"}, {"ok": True}, {"ok": False, "reason": "no contests"})
    assert v["status"] == "FAIL" and len(v["reasons"]) == 2 and any("monitor absent" in r for r in v["reasons"])
    assert verdict({"ok": True}, {"ok": True}, {"ok": True}, {"ok": True})["status"] == "OK"
