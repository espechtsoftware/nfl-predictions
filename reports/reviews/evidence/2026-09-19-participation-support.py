"""Capture outcome-free current injury/DK inputs and exact vetting query inputs."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import sys

import pandas as pd
from google.cloud import bigquery

HERE = Path(__file__).parent
BASE = Path('/home/erich/projects/review-evidence/overnight-20260918')
OUT = BASE / 'participation-transfer-inputs'
PROJECT = 'nfl-predictions-503414'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    assert not OUT.exists()
    # Execute the unchanged existing helper capture first. It binds its own cutoff.
    capture = HERE / '2026-09-19-vetting-order-trace.py'
    sys.argv = [str(capture), str(OUT / 'vetting')]
    runpy.run_path(str(capture), run_name='__main__')
    cutoff = datetime.fromisoformat(json.loads((OUT/'vetting/result.json').read_text())['capture_at'])
    c = bigquery.Client(project=PROJECT)
    rows = []
    queries = {
        'injury_snapshots': '''SELECT pulled_at, capture_id, season, week, team, gsis_id,
            report_status, practice_status, date_modified, source_row_sha256
            FROM `nfl-predictions-503414.nfl_raw.injury_snapshots` FOR SYSTEM_TIME AS OF @cutoff
            WHERE season=2026 AND week=2 AND pulled_at<=@cutoff
            AND pulled_at=(SELECT MAX(pulled_at) FROM `nfl-predictions-503414.nfl_raw.injury_snapshots`
                FOR SYSTEM_TIME AS OF @cutoff WHERE season=2026 AND week=2 AND pulled_at<=@cutoff)''',
        'dk_salaries': '''SELECT pulled_at, draft_group_id, dk_player_id, dk_draftable_id,
            display_name, team_abbr, position, salary, status, game_start
            FROM `nfl-predictions-503414.nfl_raw.dk_salaries` FOR SYSTEM_TIME AS OF @cutoff
            WHERE season=2026 AND week=2 AND draft_group_id=153428 AND pulled_at<=@cutoff
            AND pulled_at=(SELECT MAX(pulled_at) FROM `nfl-predictions-503414.nfl_raw.dk_salaries`
                FOR SYSTEM_TIME AS OF @cutoff WHERE season=2026 AND week=2 AND draft_group_id=153428 AND pulled_at<=@cutoff)''',
    }
    for name, sql in queries.items():
        assert not any(x in sql.lower() for x in ('y_dk_points', 'y_targets', 'was_active'))
        params = [bigquery.ScalarQueryParameter('cutoff', 'TIMESTAMP', cutoff)]
        dry = c.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, query_parameters=params))
        assert dry.total_bytes_processed < 1_000_000_000
        job = c.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params, maximum_bytes_billed=1_000_000_000))
        fr = job.result().to_dataframe()
        p = OUT / (name+'.parquet'); fr.to_parquet(p, index=False)
        row = dict(name=name, path=str(p), sha256=sha(p), rows=len(fr), sql=sql,
                   job_id=job.job_id, bytes_processed=job.total_bytes_processed)
        rows.append(row)
        print(name, 'rows', len(fr), 'pulled_at', fr.pulled_at.astype(str).unique().tolist(), flush=True)
        for col in ('status','report_status','practice_status'):
            if col in fr: print(col, fr[col].value_counts(dropna=False).to_dict(), flush=True)
    with (OUT/'capture.json').open('x') as f:
        json.dump(dict(cutoff=cutoff.isoformat(), source_sha256=sha(__file__),
            captures=rows, football_outcomes_read=False), f, indent=2)


if __name__ == '__main__':
    main()
