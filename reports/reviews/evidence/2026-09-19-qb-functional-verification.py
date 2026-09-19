#!/usr/bin/env python3
"""Supplementary verification of unseeded live forecasts; no cloud mutations.

Operational mean alert declared at shared b374180 before treatment output read.
This never converts the original strict comparison into a numerical match.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd

NUMERIC = ['proj_points', 'proj_p10', 'proj_p50', 'proj_p90', 'proj_std', 'p_20_plus', 'value']
SOURCE = 'f06a192cd9b0aacf798d8f36432a26cac03df206'
IMAGE = 'us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:0993ee01d6d617ed2fa88c51335616c6d473508952fb226201f3cc383db75758'
MEAN_ALERT = 0.75


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(control, treatment, ids):
    assert ids and len(ids) == len(set(ids))
    for frame in (control, treatment):
        assert frame.dk_player_id.notna().all() and frame.dk_player_id.is_unique
        assert frame.generated_at.nunique() == 1
        assert np.isfinite(frame[NUMERIC].to_numpy(float)).all()
        assert frame.proj_p10.le(frame.proj_p50).all() and frame.proj_p50.le(frame.proj_p90).all()
        assert frame.proj_std.ge(0).all() and frame.p_20_plus.between(0, 1).all()
    c = control.set_index('dk_player_id').sort_index()
    t = treatment.set_index('dk_player_id').sort_index()
    assert c.index.equals(t.index), 'population changed'
    for name in ['model_version', 'gsis_id', 'position', 'team', 'opponent', 'salary']:
        pd.testing.assert_series_equal(c[name], t[name])
    gate = t.gsis_id.isin(ids)
    assert set(t.loc[gate, 'gsis_id']) == set(ids)
    assert t.loc[gate, 'position'].eq('QB').all()
    assert (t.loc[gate, NUMERIC].to_numpy(float) == 0).all(), 'gated values not all zero'
    pd.testing.assert_frame_equal(c.loc[c.position.eq('DST'), NUMERIC], t.loc[t.position.eq('DST'), NUMERIC], check_exact=True)
    delta = (t.loc[~gate, NUMERIC] - c.loc[~gate, NUMERIC]).abs()
    maximum = delta.max().to_dict()
    assert maximum['proj_points'] <= MEAN_ALERT, 'non-gated mean exceeds declared operational alert'
    se = np.sqrt(c.loc[~gate, 'proj_std'].to_numpy(float) ** 2 +
                 t.loc[~gate, 'proj_std'].to_numpy(float) ** 2) / np.sqrt(30000)
    dmean = delta.proj_points.to_numpy(float)
    assert not np.any((se == 0) & (dmean != 0)), 'zero-variance mean moved'
    ratio = np.divide(dmean, se, out=np.zeros_like(dmean), where=se > 0)
    return dict(rows=len(t), gate_count=int(gate.sum()), gated_ids=sorted(ids),
        non_gated_max_abs_delta=maximum, non_gated_median_abs_delta=delta.median().to_dict(),
        non_gated_mean_operational_alert=MEAN_ALERT,
        conservative_mc_se={'worlds_per_run': 30000, 'max_abs_mean_delta_over_se': float(ratio.max()),
            'scope': 'diagnostic, not an equivalence test; reported widened SD conservatively ignores blend shrinkage'},
        control_batch=str(c.generated_at.iloc[0]), treatment_batch=str(t.generated_at.iloc[0]),
        control_gated_mean_total=float(c.loc[gate, 'proj_points'].sum()),
        gate_rows=t.loc[gate, ['gsis_id', 'display_name', 'team']].reset_index().to_dict(orient='records'),
        dst_exact=True, identity_exact=True, gated_seven_columns_exact_zero=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--evidence', type=Path, required=True)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    assert subprocess.check_output(['git', '-C', str(a.source), 'rev-parse', 'HEAD'], text=True).strip() == SOURCE
    assert not subprocess.check_output(['git', '-C', str(a.source), 'status', '--porcelain'], text=True).strip()
    sys.path.insert(0, str(a.source / 'src'))
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs, zero_out_projections
    prior = a.evidence.with_name('qb-projection-release-20260919')
    installed = json.loads((prior / 'release-installed-template-private.json').read_text())
    captures = [pd.read_parquet(a.evidence / (x + '-gate-inputs.parquet')) for x in ('control', 'gated', 'after')]
    metas = [json.loads((a.evidence / (x + '-input-metadata.json')).read_text()) for x in ('control', 'gated', 'after')]
    for frame in captures[1:]:
        pd.testing.assert_frame_equal(captures[0].sort_values('dk_player_id').reset_index(drop=True),
                                      frame.sort_values('dk_player_id').reset_index(drop=True), check_exact=True)
    for meta in metas[1:]:
        assert set(meta) == set(metas[0])
        assert all(meta[k]['etag'] == metas[0][k]['etag'] for k in meta)
    ids = find_backup_qbs(captures[1])
    c = pd.read_parquet(a.evidence / 'control-batch.parquet')
    t = pd.read_parquet(a.evidence / 'gated-batch.parquet')
    result = compare(c, t, ids)
    transformed = zero_out_projections(c.copy(), ids)
    mask = c.gsis_id.isin(ids)
    pd.testing.assert_frame_equal(transformed.loc[~mask], c.loc[~mask], check_exact=True)
    assert (transformed.loc[mask, NUMERIC].to_numpy(float) == 0).all()
    executions = {}
    for label, frame in [('control', c), ('gated', t)]:
        execution = json.loads((a.evidence / (label + '-execution-result.json')).read_text())
        identity = json.loads((a.evidence / (label + '-execution-identity.json')).read_text())
        assert execution['name'] == identity['name']
        assert execution['template']['containers'][0]['image'] == IMAGE
        assert int(execution.get('succeededCount', 0)) == int(execution['taskCount']) == 1
        assert not execution.get('failedCount', 0) and not execution.get('cancelledCount', 0)
        assert any(x['type'] == 'Completed' and x['state'] == 'CONDITION_SUCCEEDED' for x in execution['conditions'])
        env = {v['name']: v.get('value') for v in execution['template']['containers'][0].get('env', [])}
        assert env.get('QB_BACKUP_GATE', '1') == ('0' if label == 'control' else '1')
        assert pd.Timestamp(identity['started']) <= frame.generated_at.iloc[0] <= pd.Timestamp(execution['completionTime'])
        executions[label] = {k: execution.get(k) for k in ('name', 'createTime', 'startTime', 'completionTime', 'succeededCount')}
    # Read-only final template check. Do not publish private env/secret references.
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    session = AuthorizedSession(google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])[0])
    response = session.get('https://run.googleapis.com/v2/projects/nfl-predictions-503414/locations/us-central1/jobs/project-slate', timeout=60)
    response.raise_for_status()
    assert response.json()['template'] == installed['template']
    result.update(at=datetime.now(timezone.utc).isoformat(), status='FUNCTIONAL_CHECKS_PASSED',
        source=SOURCE, image=IMAGE, executions=executions, captured_gate_inputs_equal=True,
        tracked_table_etags_equal=True, task_template_unchanged=True, common_upstream_transform_exact=True,
        source_reader_sha256=sha(Path(__file__)),
        paired_random_draws=False, original_strict_comparison_passed=(a.evidence / 'release-verified.json').exists(),
        interpretation='Deployment/gate mechanics and bounded mean drift verified; no exact cross-run identity or NFL efficacy claim.',
        file_sha256={p.name: sha(p) for p in a.evidence.iterdir()
            if p.name.endswith(('-batch.parquet', '-gate-inputs.parquet', '-execution-result.json', '-input-metadata.json'))})
    with a.out.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('file_sha256', 'gate_rows', 'gated_ids')}, indent=2))


if __name__ == '__main__':
    main()
