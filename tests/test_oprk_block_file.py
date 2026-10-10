"""reports/2026-10-10-oprk/oprk_block_file.py (study 38 amendment 6z6's paper DK-opponent-rank block): the bonus mapping, the
term-block format (every skill player once, the DST omitted, pred_own = bonus / 0.20), the join by dk_player_id, the timing
refusals, the capture-file and synthetic inputs. Offline."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reports" / "2026-10-10-oprk"))
import oprk_block_file as O  # noqa: E402


def _frame(n=40):
    pos = ["QB", "RB", "WR", "TE"]
    rows = [{"id": f"00-{k:04d}", "dk_player_id": 1000 + k, "display_name": f"P{k}", "pos": pos[k % 4], "team": f"T{k % 8}",
             "opp": f"T{(k + 1) % 8}", "salary": 5000} for k in range(n)]
    rows.append({"id": "T0_DST", "dk_player_id": 9, "display_name": "D", "pos": "DST", "team": "T0", "opp": "T1", "salary": 3000})
    return pd.DataFrame(rows)


def _cap(frame, ranks):
    sk = frame[frame.pos != "DST"]
    return pd.DataFrame({"dk_player_id": sk.dk_player_id.astype(str), "oprk": [ranks[k % len(ranks)] for k in range(len(sk))]})


def test_the_bonus_mapping():
    got = O.bonus(pd.Series([32, 24, 20, 16, 1, np.nan]))
    assert list(got) == [2.0, 1.0, 0.5, 0.0, 0.0, 0.0]                                      # 32 -> +2, 24 -> +1, 16 or tougher -> 0


def test_the_file_format_and_join():
    fr = _frame()
    cap = _cap(fr, [32, 24, 8, np.nan])
    out, unranked = O.build(fr, cap, "2026-10-11T15:35:00Z")
    assert list(out.columns) == O.COLUMNS and len(out) == 40 and "DST" not in set(out.pos)
    assert out.dk_player_id.tolist() == [str(1000 + k) for k in range(40)]
    assert list(out.bonus_points[:4]) == [2.0, 1.0, 0.0, 0.0] and unranked == 10
    assert np.allclose(out.pred_own, out.bonus_points / 0.20) and (out.snapshot_ts == "2026-10-11T15:35:00Z").all()


def test_the_refusals_in_build():
    fr = _frame()
    with pytest.raises(ValueError, match="no player carries a bonus"):
        O.build(fr, _cap(fr, [8, 16]), "t")
    dup = pd.concat([_cap(fr, [32]), _cap(fr, [32]).head(1)])
    with pytest.raises(ValueError, match="repeats in the capture"):
        O.build(fr, dup, "t")
    with pytest.raises(ValueError, match="repeats in the frame"):
        O.build(pd.concat([fr, fr.head(1)]), _cap(fr, [32]), "t")


def test_the_timing_refusals():
    O.check_timing("2026-10-11T15:35:00Z", "2026-10-11T15:40:00Z", 24)
    with pytest.raises(ValueError, match="no time zone"):
        O.check_timing("2026-10-11T15:35:00Z", "2026-10-11T15:40:00", 24)
    with pytest.raises(ValueError, match="not before"):
        O.check_timing("2026-10-11T15:40:00Z", "2026-10-11T15:40:00Z", 24)
    with pytest.raises(ValueError, match="more than 24 h"):
        O.check_timing("2026-10-10T14:31:41Z", "2026-10-11T15:40:00Z", 24)                # Saturday's capture on Sunday: refused


def test_the_capture_csv_takes_the_last_pull_before_as_of(tmp_path):
    fr = _frame(); fp = tmp_path / "frame.parquet"; fr.to_parquet(fp)
    c1 = _cap(fr, [8]).assign(pulled_at="2026-10-11T15:00:00Z")
    c2 = _cap(fr, [32]).assign(pulled_at="2026-10-11T15:35:00Z")
    c3 = _cap(fr, [1]).assign(pulled_at="2026-10-11T16:00:00Z")                              # after --as-of: never used
    cp = tmp_path / "cap.csv"; pd.concat([c1, c2, c3]).to_csv(cp, index=False)
    out = tmp_path / "paper-oprk-w05.csv"
    rc = O.main(["--week", "5", "--group", "154468", "--frame", str(fp), "--as-of", "2026-10-11T15:40:00Z",
                 "--capture-csv", str(cp), "--out", str(out)])
    got = pd.read_csv(out, dtype={"dk_player_id": str})
    assert rc == 0 and (got.oprk == 32).all() and (got.snapshot_ts == "2026-10-11T15:35:00Z").all()


def test_the_synthetic_capture_is_deterministic_and_labelled(tmp_path):
    fr = _frame(); fp = tmp_path / "frame.parquet"; fr.to_parquet(fp)
    o1, o2 = tmp_path / "a.csv", tmp_path / "b.csv"
    assert O.main(["--week", "4", "--group", "0", "--frame", str(fp), "--synthetic", "--out", str(o1)]) == 0
    assert O.main(["--week", "4", "--group", "0", "--frame", str(fp), "--synthetic", "--out", str(o2)]) == 0
    a, b = pd.read_csv(o1), pd.read_csv(o2)
    assert a.equals(b) and (a.snapshot_ts == O.SYNTHETIC_TS).all()
    assert sorted(a.oprk.unique()) == [1.0, 5.0, 10.0, 14.0, 19.0, 23.0, 28.0, 32.0]        # 8 opponents spread over 1-32
    assert (a.bonus_points > 0).any() and (a.bonus_points == 0).any()


def test_a_missing_as_of_is_refused(tmp_path):
    fr = _frame(); fp = tmp_path / "frame.parquet"; fr.to_parquet(fp)
    assert O.main(["--week", "5", "--group", "154468", "--frame", str(fp), "--capture-csv", str(fp),
                   "--out", str(tmp_path / "x.csv")]) == 3
