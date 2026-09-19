#!/usr/bin/env python3
"""Authorized image-only release; one same-image control then gated execution.

Run only under the canonical project-slate lane. A failed/ambiguous mutation is
never retried by this program. Logs and exact provider claims survive failure.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import time
from datetime import datetime, timezone

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import bigquery
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STATE = Path('/home/erich/.local/state/nfl-dfs/lab-launcher-registry')
OUT = Path('/home/erich/projects/review-evidence/overnight-20260918/qb-projection-release-20260919')
PROJECT = 'nfl-predictions-503414'
JOB = 'project-slate'
TARGET = 'qb-projection-release-20260919'
SOURCE = 'f06a192cd9b0aacf798d8f36432a26cac03df206'
BUILD = 'd7089008-a38d-4df5-87b2-4121b7119260'
OLD_TAG = 'us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:week1-live-193e1b44d2b4'
OLD_DIGEST = 'sha256:f630fc8c88ed1625fa7873d959e0dcc217a55bd4d95b4e0edb9c1386fb3d5f5d'
NUMERIC = ['proj_points', 'proj_p10', 'proj_p50', 'proj_p90', 'proj_std', 'p_20_plus', 'value']


def stamp():
    return datetime.now(timezone.utc).isoformat()


def save(name, value):
    with (OUT / (name + '.json')).open('x') as f:
        os.chmod(f.name, 0o600)
        json.dump(value, f, indent=2, default=str, allow_nan=False)


def lanes():
    ancestors, pid = set(), os.getpid()
    while pid > 1:
        ancestors.add(pid)
        pid = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[1])
    matched = []
    for path in (STATE / 'launchers').glob('*.json'):
        row = json.loads(path.read_text())
        if row['lane'] != JOB:
            continue
        assert row['owner'] == 'production' and row['pid'] in ancestors
        assert row['target_run_id_prefixes'] == [TARGET]
        stat = Path(f"/proc/{row['pid']}/stat").read_text().rsplit(')', 1)[1].split()
        assert int(stat[19]) == row['process_start_ticks']
        matched.append(row)
    assert len(matched) == 1, 'exact owned project-slate lane required'
    return matched[0]


def gate_inputs(runner, name):
    """Same production joins/guards, restricted to identity and gate inputs."""
    from nfl_dfs.inference import run_projections as rp
    original = rp.query_df
    needle = '''SELECT sl.* EXCEPT (
          active_gsis_id, active_exact_name, season
        ), t.gsis_id IS NOT NULL AS inference_row_present, t.*'''
    replacement = '''SELECT sl.dk_player_id, sl.display_name, sl.dk_position, sl.team_abbr,
          sl.status, sl.draft_group_id, sl.roster_receipt_is_valid,
          t.gsis_id IS NOT NULL AS inference_row_present, t.gsis_id,
          t.position, t.team, t.opponent, t.is_cold_start, t.depth_rank, t.injury_status'''
    def restricted(sql, params=None):
        if 'FROM classified_slate sl' in sql:
            assert sql.count(needle) == 1
            sql = sql.replace(needle, replacement)
        return original(sql, params)
    rp.query_df = restricted
    try:
        frame = rp.upcoming_slate_features(2026, 2)
    finally:
        rp.query_df = original
    frame.to_parquet(OUT / (name + '-gate-inputs.parquet'), index=False)
    tables = ['nfl_features.player_week_inference', 'nfl_features.tabpfn_projections',
              'nfl_raw.dk_salaries', 'nfl_raw.prop_lines', 'nfl_raw.rosters_weekly']
    meta = {table: runner.table_meta(PROJECT + '.' + table) for table in tables}
    save(name + '-input-metadata', meta)
    return frame, meta


def batch(runner, label, start, end):
    columns = ['generated_at', 'model_version', 'gsis_id', 'dk_player_id', 'display_name',
               'position', 'team', 'opponent', 'salary'] + NUMERIC
    sql = ('SELECT ' + ','.join(columns) + f' FROM `{PROJECT}.nfl_predictions.player_projections` '
           'WHERE season=2026 AND week=2 AND generated_at BETWEEN @start AND @end')
    job = runner.bq.query(sql, job_config=bigquery.QueryJobConfig(
        maximum_bytes_billed=2_000_000_000, query_parameters=[
            bigquery.ScalarQueryParameter('start', 'TIMESTAMP', start),
            bigquery.ScalarQueryParameter('end', 'TIMESTAMP', end)]))
    frame = job.result().to_dataframe()
    assert len(frame) and frame.generated_at.nunique() == 1
    assert frame.dk_player_id.notna().all() and frame.dk_player_id.is_unique
    assert frame.loc[frame.position != 'DST', 'gsis_id'].notna().all()
    assert frame.loc[frame.position != 'DST', 'gsis_id'].is_unique
    assert np.isfinite(frame[NUMERIC].to_numpy(float)).all()
    assert (frame.proj_p10 <= frame.proj_p50).all() and (frame.proj_p50 <= frame.proj_p90).all()
    assert frame.proj_std.ge(0).all() and frame.p_20_plus.between(0, 1).all()
    frame.to_parquet(OUT / (label + '-batch.parquet'), index=False)
    save(label + '-batch', dict(rows=len(frame), generated_at=str(frame.generated_at.iloc[0]),
                              query_job=job.job_id, columns=columns))
    return frame


def execute(runner, helper, label, image, gate_off=False):
    lanes()
    before = runner.census(label + '-before')[JOB]
    started = stamp()
    args = ['gcloud', 'run', 'jobs', 'execute', JOB, '--project=' + PROJECT,
            '--region=us-central1', '--async', '--format=json']
    if gate_off:
        args.append('--update-env-vars=QB_BACKUP_GATE=0')
    response = runner.command(label + '-execute', args)
    name = response.get('metadata', {}).get('name') or response.get('name', '')
    assert re.fullmatch(r'project-slate-[a-z0-9]+', name.rsplit('/', 1)[-1]), (
        'ambiguous execution response; reconcile provider before any retry', name)
    full = f'projects/{PROJECT}/locations/us-central1/jobs/{JOB}/executions/' + name.rsplit('/', 1)[-1]
    assert full not in before
    save(label + '-execution-identity', dict(name=full, started=started, gate_off=gate_off))
    print('EXECUTION_STARTED', label, full, flush=True)
    deadline = time.monotonic() + 3900
    while True:
        actual = runner.get('https://run.googleapis.com/v2/' + full)
        if helper.completed(actual):
            break
        assert time.monotonic() < deadline, 'execution needs provider reconciliation'
        time.sleep(10)
    assert int(actual.get('succeededCount', 0)) == int(actual['taskCount']) == 1, actual.get('conditions')
    assert not actual.get('failedCount', 0) and not actual.get('cancelledCount', 0)
    assert any(c['type'] == 'Completed' and c['state'] == 'CONDITION_SUCCEEDED' for c in actual['conditions'])
    assert actual['template']['containers'][0]['image'] == image
    env = {v['name']: v.get('value') for v in actual['template']['containers'][0].get('env', [])}
    assert env.get('QB_BACKUP_GATE', '1') == ('0' if gate_off else '1')
    save(label + '-execution-result', actual)
    print('EXECUTION_COMPLETED', label, full, flush=True)
    return batch(runner, label, started, stamp())


def compare(control, treatment, gate_ids):
    c = control.set_index('dk_player_id').sort_index()
    t = treatment.set_index('dk_player_id').sort_index()
    assert c.index.equals(t.index), 'projection population changed between control and treatment'
    for column in ['model_version', 'gsis_id', 'position', 'team', 'opponent', 'salary']:
        pd.testing.assert_series_equal(c[column], t[column])
    gated = t.gsis_id.isin(gate_ids)
    assert set(t.loc[gated, 'gsis_id']) == set(gate_ids), 'gated input IDs absent from output'
    assert (t.loc[gated, NUMERIC].to_numpy(float) == 0).all()
    delta = np.abs(t.loc[~gated, NUMERIC].to_numpy(float) - c.loc[~gated, NUMERIC].to_numpy(float))
    assert np.allclose(t.loc[~gated, NUMERIC], c.loc[~gated, NUMERIC], rtol=1e-6, atol=1e-6), (
        'ungated output changed beyond declared tolerance', float(delta.max()))
    return dict(rows=len(t), gated=len(gate_ids), gated_ids=sorted(gate_ids),
                non_gated_max_abs_delta=float(delta.max()) if delta.size else 0,
                tolerance={'absolute': 1e-6, 'relative': 1e-6},
                removed_projected_points=float(c.loc[gated, 'proj_points'].sum()),
                control_batch=str(c.generated_at.iloc[0]), treatment_batch=str(t.generated_at.iloc[0]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', required=True)
    ap.add_argument('--source', type=Path, required=True)
    a = ap.parse_args()
    assert re.fullmatch(r'us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}', a.image)
    assert datetime.now(timezone.utc) < datetime.fromisoformat('2026-09-20T03:00:00+00:00')
    assert subprocess.check_output(['git', '-C', str(a.source), 'rev-parse', 'HEAD'], text=True).strip() == SOURCE
    assert not subprocess.check_output(['git', '-C', str(a.source), 'status', '--porcelain'], text=True).strip()
    sys_path = str(a.source / 'src')
    import sys
    sys.path.insert(0, sys_path)
    from nfl_dfs.config import settings
    assert settings.project == PROJECT and settings.predictions == PROJECT + '.nfl_predictions'
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs
    build = json.loads(subprocess.check_output(['gcloud', 'builds', 'describe', BUILD,
                                               '--project=' + PROJECT, '--format=json'], text=True))
    assert build['status'] == 'SUCCESS'
    assert any(v['digest'] == a.image.rsplit('@', 1)[1] for v in build['results']['images'])
    lanes()
    spec = importlib.util.spec_from_file_location('reviewed_release_helper', HERE / '2026-09-19-release-supervisor.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.OUT, helper.JOBS = OUT, (JOB,)
    runner = helper.Release()
    save('release-start', dict(at=stamp(), source=SOURCE, image=a.image, build=BUILD, lane=lanes(),
                               runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                               helper_sha256=hashlib.sha256(Path(helper.__file__).read_bytes()).hexdigest(),
                               authorization='lab shared 81d809f: operator Tonight after premise correction'))
    runner.census('release-before')
    before = runner.get(helper.BASE + JOB)
    assert before['template']['template']['containers'][0]['image'] == OLD_TAG
    resolved = subprocess.check_output(['gcloud', 'artifacts', 'docker', 'images', 'describe', OLD_TAG,
                                        '--project=' + PROJECT, '--format=value(image_summary.digest)'], text=True).strip()
    assert resolved == OLD_DIGEST
    save('release-before-template-private', before)
    runner.command('image-update', ['gcloud', 'run', 'jobs', 'update', JOB, '--project=' + PROJECT,
                                    '--region=us-central1', '--image=' + a.image, '--format=json'])
    installed = runner.get(helper.BASE + JOB)
    assert helper.template_without_image(before) == helper.template_without_image(installed)
    assert installed['template']['template']['containers'][0]['image'] == a.image
    save('release-installed-template-private', installed)
    f0, metadata0 = gate_inputs(runner, 'control')
    control = execute(runner, helper, 'control', a.image, gate_off=True)
    f1, metadata1 = gate_inputs(runner, 'gated')
    pd.testing.assert_frame_equal(f0.sort_values('dk_player_id').reset_index(drop=True),
                                  f1.sort_values('dk_player_id').reset_index(drop=True))
    assert all(metadata0[k]['etag'] == metadata1[k]['etag'] for k in metadata0), 'input tables changed before gated run'
    gate_ids = find_backup_qbs(f1)
    assert gate_ids, 'candidate gate is unexpectedly inert'
    treatment = execute(runner, helper, 'gated', a.image)
    f2, metadata2 = gate_inputs(runner, 'after')
    pd.testing.assert_frame_equal(f1.sort_values('dk_player_id').reset_index(drop=True),
                                  f2.sort_values('dk_player_id').reset_index(drop=True))
    assert all(metadata1[k]['etag'] == metadata2[k]['etag'] for k in metadata1), 'input tables changed during gated run'
    result = compare(control, treatment, gate_ids)
    assert runner.get(helper.BASE + JOB)['template'] == installed['template']
    lanes()
    save('release-verified', dict(at=stamp(), status='VERIFIED', image=a.image, source=SOURCE,
                                  unchanged_task_settings=True, **result))
    print('RELEASE_VERIFIED', json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
