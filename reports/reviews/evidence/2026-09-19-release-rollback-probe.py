"""Exercise snapshot/restore only in retained scratch namespaces, never live tables."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import bigquery

PROJECT = 'nfl-predictions-503414'
OUT = Path(__file__).with_suffix('.json')
PAIRS = [
    (f'{PROJECT}.nfl_features_control.dk_salary_week', 'salary'),
    (f'{PROJECT}.nfl_predictions_control.player_projections', 'projections'),
]
DEST = f'{PROJECT}.nfl_features_salaryfix'


def schema(table):
    return [x.to_api_repr() for x in table.schema]


def main():
    assert not OUT.exists()
    c = bigquery.Client(project=PROJECT)
    point = datetime.now(timezone.utc).isoformat()
    results, jobs = [], []
    allowed_sources = {x[0] for x in PAIRS}
    def execute(sql):
        j = c.query(sql, location='US', job_config=bigquery.QueryJobConfig(maximum_bytes_billed=500_000_000))
        rows = list(j.result(timeout=120))
        jobs.append(dict(id=j.job_id, sql=sql, bytes_processed=j.total_bytes_processed))
        return rows
    for source, label in PAIRS:
        assert source in allowed_sources
        before = c.get_table(source)
        assert before.table_type == 'TABLE' and before.location == 'US'
        snapshot = f'{DEST}.release_probe_20260919_v1_{label}_snapshot'
        restored = f'{DEST}.release_probe_20260919_v1_{label}_restored'
        for target in (snapshot, restored):
            try:
                c.get_table(target)
            except Exception as exc:
                if getattr(exc, 'code', None) != 404:
                    raise
            else:
                raise AssertionError('probe target already exists: ' + target)
        execute(f"CREATE SNAPSHOT TABLE `{snapshot}` CLONE `{source}` "
                f"FOR SYSTEM_TIME AS OF TIMESTAMP('{point}') "
                'OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 3 DAY))')
        execute(f'CREATE TABLE `{restored}` CLONE `{snapshot}`')
        # Exercise replacement too, which is the actual rollback primitive.
        execute(f'CREATE OR REPLACE TABLE `{restored}` CLONE `{snapshot}`')
        execute(f'ALTER TABLE `{restored}` SET OPTIONS '
                '(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 3 DAY))')
        snap, target, after = [c.get_table(x) for x in (snapshot, restored, source)]
        assert snap.table_type == 'SNAPSHOT' and target.table_type == 'TABLE'
        assert (before.etag, before.modified) == (after.etag, after.modified), 'scratch source drift'
        assert schema(before) == schema(snap) == schema(target)
        assert before.time_partitioning == snap.time_partitioning == target.time_partitioning
        assert before.clustering_fields == snap.clustering_fields == target.clustering_fields
        checks = {}
        for name in (source, snapshot, restored):
            row = execute(f'SELECT COUNT(*) AS n, BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS h '
                          f'FROM `{name}` t')[0]
            checks[name] = dict(rows=int(row.n), checksum=int(row.h))
        assert len({(v['rows'], v['checksum']) for v in checks.values()}) == 1
        # Exact bidirectional row comparison; checksum alone is not the proof.
        for left, right in ((source, restored), (restored, source)):
            row = execute(f'SELECT COUNT(*) AS n FROM (SELECT * FROM `{left}` '
                          f'EXCEPT DISTINCT SELECT * FROM `{right}`)')[0]
            assert row.n == 0
        results.append(dict(source=source, snapshot=snapshot, restored=restored, checks=checks,
                            exact_bidirectional_row_match=True, schema_partition_clustering_match=True))
    with OUT.open('x') as f:
        json.dump(dict(point_in_time=point, results=results, jobs=jobs,
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            scope='scratch snapshot/restore rehearsal only; no live writes; probe tables expire in 3 days'),
            f, indent=2)
    print('SCRATCH_SNAPSHOT_RESTORE_PASS', len(results), len(jobs), flush=True)


if __name__ == '__main__':
    main()
