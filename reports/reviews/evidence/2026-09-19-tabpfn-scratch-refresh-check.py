"""Safety checks for the isolated refresh adapter; no writes or inference."""
import importlib.util
import json
import types
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('scratch_adapter', ROOT / '2026-09-19-tabpfn-scratch-refresh.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
source = Path('/home/erich/projects/review-evidence/overnight-20260918/tabpfn-image/gen.py').read_bytes()
checks = []


def refuses(label, action):
    try:
        action()
    except ValueError:
        checks.append(label)
    else:
        raise AssertionError(label + ' did not refuse')


refuses('live namespace', lambda: m.namespace('nfl_features'))
refuses('modified deployed source', lambda: m.adapted_source(source + b'\n', 'control'))
fake = Mock()
guard = m.GuardedClient(fake, 'control')
refuses('live read', lambda: guard.query('SELECT * FROM `nfl-predictions-503414.nfl_features.player_week_training`'))
refuses('unfiltered scratch labels', lambda: guard.query(f'SELECT * FROM `{guard.ns}.player_week_training`'))
refuses('scratch DML', lambda: guard.query(f'DELETE FROM `{guard.ns}.player_week_training` WHERE TRUE'))
refuses('live write', lambda: guard.load_table_from_dataframe(None, 'nfl-predictions-503414.nfl_features.tabpfn_projections', types.SimpleNamespace(write_disposition='WRITE_EMPTY')))
refuses('scratch overwrite', lambda: guard.load_table_from_dataframe(None, guard.output, types.SimpleNamespace(write_disposition='WRITE_TRUNCATE')))
assert not fake.mock_calls, fake.mock_calls
checks.append('all rejected calls stopped before provider access')

from google.cloud import bigquery
client = bigquery.Client(project=m.PROJECT)
dry_runs = []
for arm in ('control', 'salaryfix'):
    adapted = m.adapted_source(source, arm)
    guard = m.GuardedClient(client, arm)
    guard.check_sources()
    sql = f'SELECT * FROM `{guard.ns}.player_week_training` WHERE season < 2026 OR (season = 2026 AND week < 2) ORDER BY season, week, gsis_id'
    j = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, maximum_bytes_billed=1_000_000_000))
    dry_runs.append(dict(arm=arm, bytes=j.total_bytes_processed, adapted_bytes=len(adapted.encode())))
    checks.append(arm + ' source identity and actual filtered query dry-run')
result = dict(checks=checks, count=len(checks), dry_runs=dry_runs, cloud_writes=0)
print(json.dumps(result, indent=2))
with (ROOT / '2026-09-19-tabpfn-scratch-refresh-check.json').open('x') as f:
    json.dump(result, f, indent=2)
