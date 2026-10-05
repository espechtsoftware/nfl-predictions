"""overlay_monitor: synthetic snapshots only (no BigQuery, no network)."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("overlay_monitor", ROOT / "scripts" / "overlay_monitor.py")
OM = importlib.util.module_from_spec(spec); spec.loader.exec_module(OM)

LOCK = pd.Timestamp("2026-10-11T17:00:00Z")


def snap(cid, mins_before, entries, fee=5.0, mx=100, pool=400.0, g=True, name=None):
    return {"contest_id": cid, "name": name or f"c{cid}", "entry_fee": fee, "max_entries": mx, "entries": entries,
            "prize_pool": pool, "is_guaranteed": g, "pulled_at": LOCK - pd.Timedelta(minutes=mins_before), "start_time": LOCK}


def test_latest_snapshot_is_the_last_one_before_lock_and_now():
    s = pd.DataFrame([snap(1, 120, 10), snap(1, 30, 60), snap(1, -10, 99)])   # -10 = after lock: ignored
    lt = OM.latest_snapshots(s)
    assert len(lt) == 1 and lt.entries.iloc[0] == 60
    lt = OM.latest_snapshots(s, now=LOCK - pd.Timedelta(minutes=60))
    assert lt.entries.iloc[0] == 10


def test_pool_ratio_flags_only_guaranteed_paid_contests_above_one():
    s = pd.DataFrame([
        snap(1, 30, 60, fee=5, pool=400),            # 400 / 300 = 1.33 -> flag
        snap(2, 30, 90, fee=5, pool=400),            # 400 / 450 = 0.89 -> no
        snap(3, 30, 60, fee=5, pool=400, g=False),   # not guaranteed -> excluded
        snap(4, 30, 60, fee=0, pool=400),            # freeroll -> excluded
        snap(5, 30, 0, fee=5, pool=400),             # no entries -> excluded
    ])
    t = OM.overlay_table(OM.latest_snapshots(s))
    assert set(t.contest_id) == {1, 2}
    r1 = t.set_index("contest_id").loc[1]
    assert r1.flag and abs(r1.pool_ratio_now - 400 / 300) < 1e-12 and r1.breakeven_entries == 80
    assert not t.set_index("contest_id").loc[2].flag
    assert t.contest_id.iloc[0] == 1                              # flagged first


def test_finalize_records_materialisation_and_failures():
    s = pd.DataFrame([snap(1, 30, 60, pool=400), snap(6, 30, 50, pool=400), snap(7, 30, 40, pool=400)])
    flags = OM.overlay_table(OM.latest_snapshots(s))
    finals = {"1": {"entries": 70}, "6": {"entries": 95}}       # 1 stays overlaid (400/350), 6 does not (400/475)

    def fetch(cid):
        if cid not in finals:
            raise RuntimeError("404")
        return finals[cid]
    out = OM.finalize(flags, fetch, sleep=0).set_index("contest_id")
    assert bool(out.loc[1, "materialised"]) and not bool(out.loc[6, "materialised"])
    assert pd.isna(out.loc[7, "final_entries"]) and "404" in out.loc[7, "error"]


def test_flag_refuses_a_week_input_tree(tmp_path):
    assert OM.main(["flag", "--slate", "2026-10-11", "--out-dir", str(tmp_path / "week5-sunday")]) == 2
