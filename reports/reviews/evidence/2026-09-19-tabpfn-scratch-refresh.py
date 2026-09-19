"""Run the pinned deployed generator with guarded scratch-only destinations.

Research adapter, not a replacement live generator. Cloud Run args supply
ARM=control|salaryfix and MODE=mechanics|refresh in the execution environment.
"""
import hashlib
import json
import os
import re
from pathlib import Path

PROJECT = 'nfl-predictions-503414'
GEN_SHA = '0d8a355b270e2ef5f6097bef51ca5d3ff1715e20951b4c2762b5594a5b9c9a81'
FEATURE_SHA = '52cc95c500bc3bd4223baacb29be73e3df4d637ce289b6431735cddd46195b83'
PINS = {
    'control': {
        'player_week_training': ('nwKP4TD+rJOayTnS15cL/Q==', 102927, '2026-09-19T00:58:17.124000+00:00'),
        'player_week_inference': ('+sLht3w5x+V15eX3aMCTWw==', 928, '2026-09-19T00:58:25.014000+00:00'),
    },
    'salaryfix': {
        'player_week_training': ('biIB7PKXGMq2eprf6rd+pQ==', 103833, '2026-09-19T00:51:11.798000+00:00'),
        'player_week_inference': ('t4UtM2PtPQS6wnrUcXqMuw==', 928, '2026-09-19T00:51:20.243000+00:00'),
    },
}


def namespace(arm):
    if arm not in PINS:
        raise ValueError('arm must be control or salaryfix; live namespace forbidden')
    return f'{PROJECT}.nfl_features_{arm}'


def replace_exact(source, before, after, count=1):
    if source.count(before) != count:
        raise ValueError(f'source contract drift: expected {count} instances of {before!r}')
    return source.replace(before, after)


def adapted_source(raw, arm):
    namespace(arm)
    if hashlib.sha256(raw).hexdigest() != GEN_SHA:
        raise ValueError('deployed generator source differs')
    source = raw.decode()
    source = replace_exact(source, '{PROJECT}.nfl_features.', '{PROJECT}.nfl_features_' + arm + '.', 6)
    source = replace_exact(source, 'bq = bigquery.Client(project=PROJECT)', 'bq = _scratch_client')
    # Filter in SQL BEFORE downloading any current-week training labels.
    source = replace_exact(source,
        'panel = bq.query(f"SELECT * FROM `{source_table}`").to_dataframe()',
        'panel = bq.query(f"SELECT * FROM `{source_table}` WHERE season < 2026 OR (season = 2026 AND week < 2) ORDER BY season, week, gsis_id").to_dataframe()')
    source = replace_exact(source,
        'f"WHERE season={us} AND week={uw}").to_dataframe()',
        'f"WHERE season={us} AND week={uw} ORDER BY gsis_id").to_dataframe()')
    source = replace_exact(source,
        'else bigquery.WriteDisposition.WRITE_TRUNCATE)',
        'else bigquery.WriteDisposition.WRITE_EMPTY)')
    if '.nfl_features.' in source:
        raise ValueError('live namespace survived adaptation')
    compile(source, 'tabpfn-scratch-adapted.py', 'exec')
    return source


class GuardedClient:
    def __init__(self, client, arm):
        self.client, self.arm, self.ns = client, arm, namespace(arm)
        self.output = self.ns + '.tabpfn_projections'
        self.sources = {self.ns + '.' + name for name in PINS[arm]}
        self.jobs, self.writes = [], 0

    def check_sources(self):
        for name, expected in PINS[self.arm].items():
            t = self.client.get_table(self.ns + '.' + name)
            actual = (t.etag, int(t.num_rows), t.modified.isoformat())
            if actual != expected:
                raise ValueError(f'scratch source changed: {name}, {actual!r}')

    def get_table(self, table):
        if table not in self.sources | {self.output}:
            raise ValueError('foreign table metadata request')
        return self.client.get_table(table)

    def query(self, sql):
        from google.cloud import bigquery
        refs = set(re.findall(r'`([^`]+)`', sql))
        if not sql.lstrip().upper().startswith('SELECT ') or not refs or not refs <= self.sources:
            raise ValueError('query is not an allowed scratch read')
        if ';' in sql:
            raise ValueError('multiple statements forbidden')
        # Every training row download must carry the pre-read temporal filter.
        if re.search(r'SELECT\s+\*', sql, re.I) and self.ns + '.player_week_training' in refs:
            if 'WHERE season < 2026 OR (season = 2026 AND week < 2)' not in sql:
                raise ValueError('training read lacks the target-week firewall')
        j = self.client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
        self.jobs.append(j.job_id)
        return j

    def load_table_from_dataframe(self, frame, destination, job_config):
        if destination != self.output or job_config.write_disposition != 'WRITE_EMPTY' or self.writes:
            raise ValueError('only one create-only write to the declared scratch cache is allowed')
        # Output validation and source stability precede the one permitted write.
        self.check_sources()
        if frame.empty or frame.duplicated(['season', 'week', 'gsis_id']).any():
            raise ValueError('invalid cache keys')
        if ((frame.season > 2026) | ((frame.season == 2026) & (frame.week != 2))).any():
            raise ValueError('unexpected cache target')
        if int(((frame.season == 2026) & (frame.week == 2)).sum()) != 928:
            raise ValueError('upcoming target does not contain 928 rows')
        self.writes += 1
        j = self.client.load_table_from_dataframe(frame, destination, job_config=job_config)
        self.jobs.append(j.job_id)
        return j


def main():
    from google.api_core.exceptions import NotFound
    from google.cloud import bigquery
    arm, mode = os.environ['TABPFN_REHEARSAL_ARM'], os.environ['TABPFN_REHEARSAL_MODE']
    namespace(arm)
    if mode not in ('mechanics', 'refresh'):
        raise ValueError('unknown rehearsal mode')
    if os.environ.get('GCP_PROJECT') != PROJECT:
        raise ValueError('project differs')
    for key in ['TABPFN_COMPONENTS', 'TABPFN_SEASONS', 'TABPFN_WRITE']:
        if os.environ.get(key, '').strip() not in ('', '0'):
            raise ValueError('foreign mode override: ' + key)
    # If execution args were ignored, the ORIGINAL generator must refuse this
    # unlicensed output name before querying or writing anything.
    if os.environ.get('TABPFN_OUTPUT_TABLE') != 'scratch_adapter_required':
        raise ValueError('execution lacks the original-generator refusal sentinel')
    raw = Path('/app/gen.py').read_bytes()
    if hashlib.sha256(Path('/app/features.txt').read_bytes()).hexdigest() != FEATURE_SHA:
        raise ValueError('feature contract differs')
    source = adapted_source(raw, arm)
    guard = GuardedClient(bigquery.Client(project=PROJECT), arm)
    guard.check_sources()
    try:
        guard.get_table(guard.output)
    except NotFound:
        pass
    else:
        raise ValueError('scratch output already exists; do not overwrite or retry blindly')
    os.environ.update(TABPFN_UPCOMING='2026:2', TABPFN_UPCOMING_ONLY='0',
                      TABPFN_COMPONENTS='0', TABPFN_OUTPUT_TABLE='tabpfn_projections')
    before = dict(arm=arm, mode=mode, source_sha256=GEN_SHA,
                  adapted_sha256=hashlib.sha256(source.encode()).hexdigest(),
                  feature_sha256=FEATURE_SHA, sources=PINS[arm], output=guard.output,
                  temporal_rule='training season/week strictly before 2026/2',
                  ordering='training: season/week/gsis_id; inference: gsis_id',
                  write_disposition='WRITE_EMPTY')
    print('TABPFN_REHEARSAL_PREFLIGHT=' + json.dumps(before, sort_keys=True), flush=True)
    if mode == 'mechanics':
        print('TABPFN_REHEARSAL_MECHANICS_PASS', flush=True)
        return
    exec(compile(source, 'tabpfn-scratch-adapted.py', 'exec'), {'__name__': '__main__', '_scratch_client': guard})
    guard.check_sources()
    if guard.writes != 1:
        raise ValueError('expected exactly one output write')
    t = guard.get_table(guard.output)
    print('TABPFN_REHEARSAL_DONE=' + json.dumps(dict(before, query_and_load_jobs=guard.jobs,
          rows=t.num_rows, output_etag=t.etag, output_modified=t.modified.isoformat()), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
