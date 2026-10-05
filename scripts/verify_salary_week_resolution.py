"""Execute the actual own-snapshot SQL against literal BigQuery fixtures.

Read-only: fixture SELECT only, no warehouse table reads or DDL. Also writes
the exact query and result locally for the independent repair review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from google.cloud import bigquery


def literal(value, kind):
    if value is None:
        return f'CAST(NULL AS {kind})'
    if kind in ('INT64', 'FLOAT64'):
        return f'CAST({value} AS {kind})'
    text = str(value).replace("'", "''")
    return f"TIMESTAMP('{text}')" if kind == 'TIMESTAMP' else f"'{text}'"


def relation(rows, types):
    return '\nUNION ALL\n'.join('SELECT ' + ', '.join(
        f'{literal(row[name], kind)} AS {name}' for name, kind in types.items()
    ) for row in rows)


def own_snapshot_select(sql):
    start = 'CREATE OR REPLACE TABLE `${features}.dk_salary_week` AS\n'
    end = '),\nnorm_ids AS ('
    assert sql.count(start) == sql.count(end) == 1
    return sql.split(start, 1)[1].split(end, 1)[0] + ')\nSELECT * FROM own_log'


def fixture_query(sql):
    schedules = [
        dict(season=2026, week=1, game_id='sun-night', gameday='2026-09-13', home_team='NE', away_team='CHI', game_type='REG'),
        dict(season=2026, week=2, game_id='week-two', gameday='2026-09-20', home_team='LA', away_team='TB', game_type='REG'),
        dict(season=2026, week=1, game_id='preseason', gameday='2026-08-20', home_team='NE', away_team='CHI', game_type='PRE'),
        dict(season=2026, week=18, game_id='january', gameday='2027-01-03', home_team='NE', away_team='CHI', game_type='REG'),
        dict(season=2026, week=1, game_id='ambiguous-a', gameday='2026-09-13', home_team='ARI', away_team='BAL', game_type='REG'),
        dict(season=2026, week=2, game_id='ambiguous-b', gameday='2026-09-13', home_team='ARI', away_team='DAL', game_type='REG'),
        dict(season=2026, week=1, game_id='same-id', gameday='2026-09-13', home_team='GB', away_team='SEA', game_type='REG'),
        dict(season=2026, week=2, game_id='same-id', gameday='2026-09-13', home_team='GB', away_team='SEA', game_type='REG'),
        dict(season=2026, week=1, game_id='extra-game', gameday='2026-09-13', home_team='BAL', away_team='CLE', game_type='REG'),
    ]
    schedules.append(dict(schedules[0]))  # identical duplicate must not multiply salary rows
    def salary(i, **changes):
        row = dict(dk_player_id=i, season=2026, week=None, game_start='2026-09-14 00:20:00+00',
            team_abbr='NWE', pulled_at='2026-09-12 16:00:00+00', slate_type='classic', salary=5000,
            status='None', dk_ppg=10.0, display_name=f'Fixture {i}', position='WR')
        row.update(changes)
        return row
    salaries = [
        salary(1),  # Eastern Sunday, UTC Monday
        salary(2, game_start='2026-09-20 17:00:00+00', team_abbr='LAR'),
        salary(3, game_start='2026-08-20 23:00:00+00'),  # preseason excluded
        salary(4, game_start='2027-01-03 18:00:00+00'),  # January remains season 2026
        salary(5, team_abbr='UNKNOWN'),
        salary(6, season=2025),  # season cannot be inferred from date alone
        salary(7, team_abbr='ARZ', game_start='2026-09-13 17:00:00+00'),  # two different weeks
        salary(8, week=3, team_abbr='NYJ'),  # preserve original non-null week contract
        salary(9, salary=5100),
        salary(9, salary=5200, pulled_at='2026-09-13 12:00:00+00'),  # latest snapshot wins
        salary(10, game_start=None),
        salary(11, slate_type='showdown'),
        salary(12, salary=0),
        salary(13, team_abbr='GNB', game_start='2026-09-13 17:00:00+00'),  # conflicting week for same id
        salary(14, team_abbr='BLT', game_start='2026-09-13 17:00:00+00'),  # two games, same week
        salary(15, team_abbr='TAM', game_start='2026-09-20 20:25:00+00'),  # per-player date, same pull as wk1
        salary(16, game_start='2026-09-21 00:20:00+00', team_abbr='LAR'),  # week2 Sunday-night boundary
    ]
    schedule_types = dict(season='INT64', week='INT64', game_id='STRING', gameday='STRING',
                          home_team='STRING', away_team='STRING', game_type='STRING')
    salary_types = dict(dk_player_id='INT64', season='INT64', week='INT64', game_start='TIMESTAMP',
        team_abbr='STRING', pulled_at='TIMESTAMP', slate_type='STRING', salary='INT64', status='STRING',
        dk_ppg='FLOAT64', display_name='STRING', position='STRING')
    maps = [dict(dk_player_id=i, gsis_id=f'fixture-{i}') for i in range(1, 17)]
    query = own_snapshot_select(sql)
    for table, name in [('`${raw}.schedules`', 'schedule_fixture'), ('`${raw}.dk_salaries`', 'salary_fixture'),
                        ('`${features}.player_id_map`', 'map_fixture')]:
        assert query.count(table) == 1
        query = query.replace(table, name, 1)
    assert query.startswith('WITH ')
    fixtures = [('schedule_fixture', schedules, schedule_types), ('salary_fixture', salaries, salary_types),
                ('map_fixture', maps, dict(dk_player_id='INT64', gsis_id='STRING'))]
    query = 'WITH ' + ',\n'.join(name + ' AS (\n' + relation(rows, types) + '\n)' for name, rows, types in fixtures) + ',\n' + query[5:]
    expected = {1: (2026, 1, 'NE', 5000), 2: (2026, 2, 'LA', 5000), 4: (2026, 18, 'NE', 5000),
        8: (2026, 3, 'NYJ', 5000), 9: (2026, 1, 'NE', 5200), 15: (2026, 2, 'TB', 5000), 16: (2026, 2, 'LA', 5000)}
    return query, expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    path = Path(__file__).resolve().parents[1] / 'sql/features/001a_dk_salary_week.sql'
    sql = path.read_text()
    query, expected = fixture_query(sql)
    assert '${' not in query and 'CREATE ' not in query and 'nfl_raw.' not in query
    job = bigquery.Client(project='nfl-2-506823').query(query,
        job_config=bigquery.QueryJobConfig(maximum_bytes_billed=10_000_000))
    rows = [dict(r) for r in job.result(timeout=60)]
    actual = {r['dk_player_id']: (r['season'], r['week'], r['team'], r['salary']) for r in rows}
    result = dict(passed=actual == expected and len(rows) == len(expected), expected=expected, actual=actual,
        rows=rows, query=query, query_sha256=hashlib.sha256(query.encode()).hexdigest(), job_id=job.job_id,
        bytes_processed=job.total_bytes_processed, sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
        source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        status=subprocess.check_output(['git', 'status', '--porcelain'], text=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2, default=str)
    print(json.dumps({key: result[key] for key in ('passed', 'expected', 'actual', 'job_id', 'bytes_processed')}, indent=2))
    assert result['passed'], 'actual SQL failed the fixture contract'


if __name__ == '__main__':
    main()
