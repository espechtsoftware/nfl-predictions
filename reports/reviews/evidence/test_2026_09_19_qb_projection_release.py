import importlib.util
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location(
    'qb_release_review', Path(__file__).with_name('2026-09-19-qb-projection-release.py'))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def pair():
    rows = []
    for dk, gsis, pos in [(1, 'QB1', 'QB'), (2, 'QB2', 'QB'), (3, 'WR1', 'WR'), (4, None, 'DST')]:
        row = dict(dk_player_id=dk, gsis_id=gsis, position=pos, team='CHI', opponent='GB',
                   model_version='fixed', salary=5000, generated_at=pd.Timestamp('2026-09-19T20:00:00Z'))
        row.update({k: 10.0 for k in release.NUMERIC})
        rows.append(row)
    c = pd.DataFrame(rows)
    t = c.copy()
    t['generated_at'] = pd.Timestamp('2026-09-19T20:05:00Z')
    t.loc[t.gsis_id.eq('QB2'), release.NUMERIC] = 0.0
    return c, t


def test_exact_gate_passes_with_output_order_changed():
    c, t = pair()
    got = release.compare(c, t.iloc[::-1], ['QB2'])
    assert got['gated'] == 1 and got['non_gated_max_abs_delta'] == 0
    assert got['removed_projected_points'] == 10.0


def test_partly_zeroed_law_refuses():
    c, t = pair()
    t.loc[t.gsis_id.eq('QB2'), 'proj_p90'] = 12.0
    with pytest.raises(AssertionError):
        release.compare(c, t, ['QB2'])


def test_non_gated_change_refuses():
    c, t = pair()
    t.loc[t.gsis_id.eq('WR1'), 'proj_points'] += 0.1
    with pytest.raises(AssertionError, match='ungated output changed'):
        release.compare(c, t, ['QB2'])


def test_declared_float_tolerance_accepts_tiny_reduction_difference():
    c, t = pair()
    t.loc[t.gsis_id.eq('WR1'), 'proj_points'] += 1e-7
    assert release.compare(c, t, ['QB2'])['non_gated_max_abs_delta'] < 1e-6


def test_population_change_refuses():
    c, t = pair()
    with pytest.raises(AssertionError, match='population changed'):
        release.compare(c, t.iloc[:-1], ['QB2'])


def test_identity_change_refuses_even_if_values_match():
    c, t = pair()
    t.loc[t.gsis_id.eq('WR1'), 'gsis_id'] = 'DIFFERENT_PLAYER'
    with pytest.raises(AssertionError):
        release.compare(c, t, ['QB2'])


def test_missing_expected_gate_id_refuses():
    c, t = pair()
    with pytest.raises(AssertionError, match='absent from output'):
        release.compare(c, t, ['QB2', 'ABSENT'])
