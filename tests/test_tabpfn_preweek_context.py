"""Execute the real generator up to its first row read, then check SQL semantics."""
from pathlib import Path
import runpy
import sqlite3
import sys
import types

import pytest
from google.cloud import bigquery

ROOT = Path(__file__).parents[1]


class CapturedRead(Exception):
    pass


def first_read(monkeypatch, target, only):
    class Client:
        def __init__(self, **kwargs):
            pass

        def get_table(self, name):
            return object()

        def query(self, sql):
            raise CapturedRead(sql)

    monkeypatch.setattr(bigquery, 'Client', Client)
    monkeypatch.setitem(sys.modules, 'torch', types.ModuleType('torch'))
    original = Path.read_bytes
    monkeypatch.setattr(Path, 'read_bytes', lambda p: b'salary\n' if str(p) == '/app/features.txt' else original(p))
    for key in ('TABPFN_COMPONENTS', 'TABPFN_SEASONS', 'TABPFN_WRITE', 'TABPFN_OUTPUT_TABLE'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('GCP_PROJECT', 'test-project')
    monkeypatch.setenv('TABPFN_UPCOMING', target)
    monkeypatch.setenv('TABPFN_UPCOMING_ONLY', only)
    runpy.run_path(str(ROOT / 'scripts/tabpfn_gen/gen.py'))


@pytest.mark.parametrize('only', ['0', '1'])
@pytest.mark.parametrize('target,expected', [('2026:2', ['last_year', 'prior_week']), ('2026:1', ['last_year'])])
def test_actual_first_query_excludes_target_and_future_labels(monkeypatch, target, expected, only):
    with pytest.raises(CapturedRead) as caught:
        first_read(monkeypatch, target, only)
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE `test-project.nfl_features.player_week_training` (season INT, week INT, name TEXT)')
        db.executemany('INSERT INTO `test-project.nfl_features.player_week_training` VALUES (?,?,?)',
            [(2025,18,'last_year'),(2026,1,'prior_week'),(2026,2,'same_week'),(2026,3,'future_week'),(2027,1,'future_season')])
        assert [x[2] for x in db.execute(caught.value.args[0])] == expected


def test_historical_only_preserves_unfiltered_panel_query(monkeypatch):
    with pytest.raises(CapturedRead) as caught:
        first_read(monkeypatch, '', '0')
    assert caught.value.args[0] == 'SELECT * FROM `test-project.nfl_features.player_week_training`'


@pytest.mark.parametrize('target', ['2026:0', '2026:19', '2026:2; DROP TABLE x', 'bad'])
def test_invalid_target_fails_before_any_row_read(monkeypatch, target):
    with pytest.raises(ValueError):
        first_read(monkeypatch, target, '0')
