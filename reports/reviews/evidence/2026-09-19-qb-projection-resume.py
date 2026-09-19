#!/usr/bin/env python3
"""Fresh paired runs after reconciled control-only input drift; no image update.

Preserves the first attempt, and reuses its reviewed execution/input/comparison
functions without relaxing a check. Not a retry of an ambiguous mutation.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import pandas as pd

HERE = Path(__file__).resolve().parent
PREVIOUS = Path('/home/erich/projects/review-evidence/overnight-20260918/qb-projection-release-20260919')
OUT = PREVIOUS.with_name(PREVIOUS.name + '-pair2')
SOURCE = Path('/home/erich/projects/.nfl-predictions-worktrees/qb-gate-review-20260919')
IMAGE = 'us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:0993ee01d6d617ed2fa88c51335616c6d473508952fb226201f3cc383db75758'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    assert datetime.now(timezone.utc) < datetime.fromisoformat('2026-09-20T03:00:00+00:00')
    release = load('prior_qb_release', HERE / '2026-09-19-qb-projection-release.py')
    helper = load('prior_qb_helper', HERE / '2026-09-19-release-supervisor.py')
    start = json.loads((PREVIOUS / 'release-start.json').read_text())
    for module, key in [(release, 'runner_sha256'), (helper, 'helper_sha256')]:
        assert hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() == start[key]
    assert start['image'] == IMAGE and start['source'] == release.SOURCE
    assert subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip() == release.SOURCE
    assert not subprocess.check_output(['git', '-C', str(SOURCE), 'status', '--porcelain'], text=True).strip()
    sys.path.insert(0, str(SOURCE / 'src'))
    from nfl_dfs.config import settings
    from nfl_dfs.inference.cascade_adjust import find_backup_qbs
    assert settings.project == release.PROJECT and os.environ.get('QB_BACKUP_GATE', '1') == '1'
    assert not (PREVIOUS / 'gated-execution-identity.json').exists()
    assert not (PREVIOUS / 'gated-execute-claim.json').exists()
    prior = json.loads((PREVIOUS / 'control-execution-result.json').read_text())
    assert prior['name'].endswith('/project-slate-rwkvt')
    assert int(prior.get('succeededCount', 0)) == int(prior['taskCount']) == 1
    installed = json.loads((PREVIOUS / 'release-installed-template-private.json').read_text())
    before = json.loads((PREVIOUS / 'release-before-template-private.json').read_text())
    assert helper.template_without_image(installed) == helper.template_without_image(before)
    release.lanes()
    OUT.mkdir(mode=0o700, exist_ok=False)
    release.OUT, helper.OUT, helper.JOBS = OUT, OUT, (release.JOB,)
    runner = helper.Release()
    release.save('resume-start', dict(at=release.stamp(), image=IMAGE, source=release.SOURCE,
        reason='DK statuses changed during confirmed successful first control; no gated execution attempted',
        prior_execution=prior['name'], previous=str(PREVIOUS), lane=release.lanes(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        original_runner_sha256=start['runner_sha256'], helper_sha256=start['helper_sha256'],
        authorization=start['authorization']))
    try:
        runner.census('resume-before')
        actual_prior = runner.get('https://run.googleapis.com/v2/' + prior['name'])
        assert helper.completed(actual_prior) and actual_prior.get('succeededCount') == 1
        assert actual_prior['template']['containers'][0]['image'] == IMAGE
        assert runner.get(helper.BASE + release.JOB)['template'] == installed['template']
        f0, m0 = release.gate_inputs(runner, 'control')
        control = release.execute(runner, helper, 'control', IMAGE, gate_off=True)
        f1, m1 = release.gate_inputs(runner, 'gated')
        pd.testing.assert_frame_equal(f0.sort_values('dk_player_id').reset_index(drop=True),
                                      f1.sort_values('dk_player_id').reset_index(drop=True))
        assert all(m0[k]['etag'] == m1[k]['etag'] for k in m0), 'input tables changed before gated run'
        ids = find_backup_qbs(f1)
        assert ids
        treatment = release.execute(runner, helper, 'gated', IMAGE)
        f2, m2 = release.gate_inputs(runner, 'after')
        pd.testing.assert_frame_equal(f1.sort_values('dk_player_id').reset_index(drop=True),
                                      f2.sort_values('dk_player_id').reset_index(drop=True))
        assert all(m1[k]['etag'] == m2[k]['etag'] for k in m1), 'input tables changed during gated run'
        result = release.compare(control, treatment, ids)
        assert runner.get(helper.BASE + release.JOB)['template'] == installed['template']
        release.lanes()
        release.save('release-verified', dict(at=release.stamp(), status='VERIFIED', image=IMAGE,
            source=release.SOURCE, unchanged_task_settings=True, **result))
        print('RELEASE_VERIFIED', json.dumps(result), flush=True)
    except BaseException as exc:
        release.save('stopped', dict(at=release.stamp(), error=str(exc), reconciliation_required=True))
        raise


if __name__ == '__main__':
    main()
