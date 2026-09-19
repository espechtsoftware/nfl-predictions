import importlib.util
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location('functional_qb', Path(__file__).with_name('2026-09-19-qb-functional-verification.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def pair():
    c = pd.DataFrame([dict(dk_player_id=i, gsis_id=g, position=pos, display_name=g or 'DST', team='CHI',
        opponent='GB', model_version='fixed', salary=5000, generated_at=pd.Timestamp('2026-09-19T20:00Z'),
        proj_points=10., proj_p10=2., proj_p50=9., proj_p90=20., proj_std=8., p_20_plus=.1, value=2.)
        for i, g, pos in [(1, 'QB1', 'QB'), (2, 'QB2', 'QB'), (3, 'WR', 'WR'), (4, None, 'DST')]])
    t = c.copy()
    t['generated_at'] = pd.Timestamp('2026-09-19T20:05Z')
    t.loc[t.gsis_id.eq('QB2'), audit.NUMERIC] = 0.
    return c, t


def test_independent_draw_mean_change_is_reported_not_called_equal():
    c, t = pair()
    t.loc[t.gsis_id.eq('WR'), 'proj_points'] += .1
    got = audit.compare(c, t.iloc[::-1], ['QB2'])
    assert got['non_gated_max_abs_delta']['proj_points'] == pytest.approx(.1)
    assert got['conservative_mc_se']['max_abs_mean_delta_over_se'] > 0


def test_material_mean_drift_refuses():
    c, t = pair()
    t.loc[t.gsis_id.eq('WR'), 'proj_points'] += .751
    with pytest.raises(AssertionError, match='operational alert'):
        audit.compare(c, t, ['QB2'])


def test_unzeroed_tail_refuses():
    c, t = pair()
    t.loc[t.gsis_id.eq('QB2'), 'proj_p90'] = 1.
    with pytest.raises(AssertionError, match='gated values'):
        audit.compare(c, t, ['QB2'])


def test_deterministic_dst_change_refuses():
    c, t = pair()
    t.loc[t.position.eq('DST'), 'proj_points'] += .00001
    with pytest.raises(AssertionError):
        audit.compare(c, t, ['QB2'])
