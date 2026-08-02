"""PUNT_BOOM archetype flags (Addendum 24/36 punt-quality lever).

The three winning-punt archetypes must flag, everything else must not,
and the vacated-share percentile must be computed within each week."""

import pandas as pd

from nfl_dfs.backtest.replay import _punt_boom_from_signals


def _sig(gsis, week, pos, rank, prev, vac):
    return dict(gsis_id=gsis, season=2025, week=week, position=pos,
                depth_rank=rank, prev_rank=prev, vac=vac)


def test_archetypes_flag_and_others_do_not():
    rows = [
        _sig("TE_STARTER", 3, "TE", 1, 1, 0.0),    # cheap starting TE
        _sig("PROMOTED", 3, "RB", 1, 2, 0.0),      # rank 2 -> 1 (Gadsden)
        _sig("TE_BACKUP", 3, "TE", 2, 2, 0.0),     # no
        _sig("WR_STARTER", 3, "WR", 1, 1, 0.0),    # rank 1 but not TE: no
        _sig("RB_DEMOTED", 3, "RB", 2, 1, 0.0),    # wrong direction: no
    ]
    # 10 fillers with modest vacated share + one cascade beneficiary
    rows += [_sig(f"F{i}", 3, "WR", 3, 3, 0.01 * (i + 1)) for i in range(10)]
    rows.append(_sig("CASCADE", 3, "WR", 3, 3, 0.45))  # top decile vac
    flags = _punt_boom_from_signals(pd.DataFrame(rows))
    names = {k[0] for k in flags}
    assert {"TE_STARTER", "PROMOTED", "CASCADE"} <= names
    assert not {"TE_BACKUP", "WR_STARTER", "RB_DEMOTED"} & names


def test_vacated_percentile_is_per_week():
    # The same 0.20 share is top-decile in a quiet week but not in a
    # week where half the league lost a starter.
    quiet = [_sig(f"Q{i}", 1, "WR", 3, 3, 0.01) for i in range(9)]
    quiet.append(_sig("QUIET_HIT", 1, "WR", 3, 3, 0.20))
    loud = [_sig(f"L{i}", 2, "WR", 3, 3, 0.5 + 0.01 * i) for i in range(9)]
    loud.append(_sig("LOUD_MISS", 2, "WR", 3, 3, 0.20))
    flags = _punt_boom_from_signals(pd.DataFrame(quiet + loud))
    names = {k[0] for k in flags}
    assert "QUIET_HIT" in names
    assert "LOUD_MISS" not in names


def test_nan_depth_ranks_do_not_flag():
    rows = [_sig("NANRANK", 5, "RB", float("nan"), float("nan"), 0.0),
            _sig("OTHER", 5, "WR", 2, 2, 0.0)]
    assert _punt_boom_from_signals(pd.DataFrame(rows)) == set()
