"""Source-read-only parity/usage preview using job-local temporary tables."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from google.cloud import bigquery
from nfl_dfs.features.leakage import SMOOTHING_PRIOR_K

ROOT = Path(__file__).resolve().parents[1]
PROD = 'nfl-predictions-503414'


def select_only(text, table):
    marker = f'CREATE OR REPLACE TABLE `${{features}}.{table}` AS\n'
    assert text.count(marker) == 1
    query = text.split(marker, 1)[1].strip().removesuffix(';')
    assert 'CREATE ' not in query and 'DELETE ' not in query and 'INSERT ' not in query
    return query


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    name = 'sql/features/001a_dk_salary_week.sql'
    old = subprocess.check_output(['git', 'show', '63a93f247a5aadbe0d7ef9e696df5e68995efb86:' + name], text=True)
    new = (ROOT / name).read_text()
    usage = (ROOT / 'sql/features/014_player_week_usage.sql').read_text()
    oldq, newq = (select_only(x, 'dk_salary_week') for x in (old, new))
    usageq = select_only(usage, 'player_week_usage')
    token = '`${features}.dk_salary_week`'
    assert usageq.count(token) == 1
    usageq = usageq.replace(token, 'repaired_salary', 1)
    query = f'''CREATE TEMP TABLE original_salary AS {oldq};
    CREATE TEMP TABLE repaired_salary AS {newq};
    CREATE TEMP TABLE repaired_usage AS {usageq};
    WITH
    old_rows AS (SELECT season, TO_JSON_STRING(t) AS row FROM original_salary t WHERE season <= 2025),
    new_rows AS (SELECT season, TO_JSON_STRING(t) AS row FROM repaired_salary t WHERE season <= 2025),
    only_old AS (SELECT * FROM old_rows EXCEPT DISTINCT SELECT * FROM new_rows),
    only_new AS (SELECT * FROM new_rows EXCEPT DISTINCT SELECT * FROM old_rows)
    SELECT
      ARRAY(SELECT AS STRUCT 'old' AS version, season, week, COUNT(*) AS n_rows
            FROM original_salary WHERE season >= 2026 GROUP BY season,week
            UNION ALL
            SELECT AS STRUCT 'new' AS version, season, week, COUNT(*) AS n_rows
            FROM repaired_salary WHERE season >= 2026 GROUP BY season,week) AS current_salary_counts,
      (SELECT COUNT(*) FROM only_old) AS historical_only_old,
      (SELECT COUNT(*) FROM only_new) AS historical_only_new,
      (SELECT COUNT(*) FROM original_salary WHERE season <= 2025) AS historical_old_count,
      (SELECT COUNT(*) FROM repaired_salary WHERE season <= 2025) AS historical_new_count,
      (SELECT COUNT(*) FROM (SELECT gsis_id,season,week FROM repaired_salary GROUP BY 1,2,3 HAVING COUNT(*) != 1)) AS duplicate_salary_keys,
      ARRAY(SELECT AS STRUCT season,week,COUNT(*) AS n_rows,
          COUNTIF(is_upcoming) AS upcoming_rows, COUNTIF(was_active) AS active_rows,
          COUNTIF(games_played_prior>0) AS with_prior_games,
          MIN(games_played_prior) AS min_prior_games, MAX(games_played_prior) AS max_prior_games,
          COUNTIF(snap_share_l4 IS NOT NULL) AS snap_supported,
          COUNTIF(target_share_l4 IS NOT NULL) AS target_supported,
          COUNTIF(carry_share_l4 IS NOT NULL) AS carry_supported
        FROM repaired_usage WHERE season=2026 GROUP BY season,week ORDER BY season,week) AS usage_support,
      ARRAY(SELECT AS STRUCT gsis_id,week,snap_share_l4,target_share_l4,carry_share_l4,games_played_prior
        FROM repaired_usage WHERE season=2026 AND week=2 AND gsis_id IN
        ('00-0032398','00-0032464','00-0033307','00-0039792','00-0040729','00-0041037','00-0038416')
        ORDER BY gsis_id) AS diagnosed_players
    '''
    substitutions = [('${raw}', PROD + '.nfl_raw'), ('${features}', PROD + '.nfl_features'),
                     ('${prior_k}', str(SMOOTHING_PRIOR_K))]
    for token, value in substitutions:
        query = query.replace(token, value)
    assert '${' not in query
    assert query.count('CREATE TEMP TABLE ') == query.count('CREATE ') == 3
    client = bigquery.Client(project='nfl-2-506823')
    dry_bytes = []
    # Dry-run each source SELECT. The usage estimate substitutes the existing
    # salary table because job-local tables do not exist until script execution.
    for estimate in (oldq, newq, usageq.replace('FROM repaired_salary sal',
                                              'FROM `${features}.dk_salary_week` sal')):
        for token, value in substitutions:
            estimate = estimate.replace(token, value)
        dry = client.query(estimate, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
        dry_bytes.append(dry.total_bytes_processed)
    print(json.dumps(dict(dry_run_bytes=dry_bytes)), flush=True)
    assert sum(dry_bytes) <= 1_000_000_000, 'preview estimates exceed 1 GB cap'
    job = client.query(query, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
    rows = [dict(r) for r in job.result(timeout=180)]
    assert len(rows) == 1
    values = rows[0]
    # Capture before assertions so any failed parity/support gate stays reviewable.
    evidence = dict(values=values, query=query, query_sha256=hashlib.sha256(query.encode()).hexdigest(),
        job_id=job.job_id, dry_run_bytes=dry_bytes, bytes_processed=job.total_bytes_processed,
        source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        status=subprocess.check_output(['git', 'status', '--porcelain'], text=True),
        sql_sha256=hashlib.sha256(new.encode()).hexdigest(),
        scope='Live raw/feature sources read only; three job-local temporary tables, no durable/live dataset writes. Week1 prior-feature support; no lineup outcome reads.',
        smoothing_prior_k=SMOOTHING_PRIOR_K)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(evidence, handle, indent=2, default=str)
    print(json.dumps(values, indent=2, default=str))
    assert values['historical_only_old'] == values['historical_only_new'] == values['duplicate_salary_keys'] == 0
    assert values['historical_old_count'] == values['historical_new_count']
    byweek = {r['week']: r for r in values['usage_support']}
    assert byweek[1]['n_rows'] > 0 and byweek[1]['max_prior_games'] == 0
    assert byweek[1]['snap_supported'] == byweek[1]['target_supported'] == byweek[1]['carry_supported'] == 0
    assert byweek[2]['with_prior_games'] > 0 and byweek[2]['max_prior_games'] <= 1
    assert byweek[2]['snap_supported'] > 0 and byweek[2]['target_supported'] > 0 and byweek[2]['carry_supported'] > 0
    print('READ_ONLY_PARITY_AND_WEEK2_USAGE_PREVIEW_PASS', flush=True)


if __name__ == '__main__':
    main()
