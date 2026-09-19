"""Run the unchanged full live CLI against guarded, frozen scratch reads."""
import hashlib
import json
import os
import re
import runpy
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

PROJECT = 'nfl-predictions-503414'
LAB = Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
LAB_SHA = '2dc116c'
RESEARCH = Path(__file__).resolve().parents[3]
LOCAL = Path('/home/erich/projects/review-evidence/overnight-20260918/complete-chain-cli')
RAW = {'dk_salaries', 'rosters_weekly', 'injury_snapshots', 'injuries', 'schedules', 'prop_lines'}
FEATURES = {'player_week_inference', 'tabpfn_projections', 'dk_salary_week', 'player_week_training'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def frozen_json(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, default=str, allow_nan=False)


class SnapshotRouter:
    def __init__(self, arm):
        assert arm in ('control', 'salaryfix')
        self.arm = arm
        self.client = bigquery.Client(project=PROJECT)
        self.calls = []
        self.base = LOCAL / 'queries'
        self.base.mkdir(parents=True, exist_ok=True)

    def __call__(self, sql):
        norm = ' '.join(sql.split())
        assert norm.startswith(('SELECT ', 'WITH latest AS (SELECT ')), norm[:80]
        assert ';' not in norm
        refs = set(re.findall(r'`([^`]+)`', norm))
        allowed = ({f'{PROJECT}.nfl_raw.{x}' for x in RAW} |
                   {f'{PROJECT}.nfl_features.{x}' for x in FEATURES} |
                   {f'{PROJECT}.nfl_predictions.player_projections'})
        assert refs and refs <= allowed, refs
        arm_read = any('.nfl_features.' in x or '.nfl_predictions.' in x for x in refs)
        if f'{PROJECT}.nfl_features.player_week_training' in refs:
            assert norm == f'SELECT * FROM `{PROJECT}.nfl_features.player_week_training` WHERE season <= 2025'
        routed = norm.replace(f'{PROJECT}.nfl_features.', f'{PROJECT}.nfl_features_{self.arm}.')
        routed = routed.replace(f'{PROJECT}.nfl_predictions.', f'{PROJECT}.nfl_predictions_{self.arm}.')
        key = sha((routed if arm_read else norm).encode())
        path, receipt_path = self.base / (key + '.parquet'), self.base / (key + '.json')
        if path.exists() or receipt_path.exists():
            assert path.exists() and receipt_path.exists(), 'incomplete frozen query; inspect before retry'
            receipt = json.loads(receipt_path.read_text())
            assert receipt['query'] == routed and sha(path.read_bytes()) == receipt['sha256']
            result = pd.read_parquet(path)
        else:
            routed_refs = set(re.findall(r'`([^`]+)`', routed))
            before = {name: self.client.get_table(name) for name in routed_refs}
            j = self.client.query(routed, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
            result = j.result(timeout=300).to_dataframe()
            after = {name: self.client.get_table(name) for name in routed_refs}
            for name, t in before.items():
                assert (t.etag, t.modified, t.num_rows) == (after[name].etag, after[name].modified, after[name].num_rows), f'source changed during read: {name}'
            # Fix row order where it affects model fitting and crosswalk ties.
            keys = [x for x in ('season', 'week', 'gsis_id', 'team', 'position', 'display_name', 'dk_player_id', 'pulled_at') if x in result]
            if keys:
                result = result.sort_values(keys, kind='stable').reset_index(drop=True)
            if f'{PROJECT}.nfl_features_{self.arm}.player_week_training' in routed_refs:
                assert result.season.max() <= 2025
            result.to_parquet(path, index=False)
            restored = pd.read_parquet(path)
            pd.testing.assert_frame_equal(result, restored)
            receipt = dict(query=routed, original_query=norm, arm=self.arm if arm_read else 'common',
                           sha256=sha(path.read_bytes()), rows=len(result), query_job=j.job_id,
                           bytes_processed=j.total_bytes_processed,
                           tables={name: dict(etag=t.etag, modified=t.modified, rows=t.num_rows) for name,t in before.items()})
            frozen_json(receipt_path, receipt)
        self.calls.append(dict(key=key, **receipt))
        return result.copy(deep=True)


def main():
    arm = sys.argv[1]
    assert arm in ('control', 'salaryfix')
    assert Path.cwd() == LAB
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip() == subprocess.check_output(['git', 'rev-parse', LAB_SHA], text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    for name in ('scripts/live_week.py', 'src/nfl2/live.py', 'src/nfl2/hsim/world.py', 'src/nfl2/hsim/live_games.py'):
        assert (LAB / name).read_bytes() == subprocess.check_output(['git', 'show', LAB_SHA + ':' + name])
    run = LOCAL / arm
    run.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    sys.path.insert(0, str(LAB / 'src'))
    os.environ['NFL2_LIVE_CENTER'] = 'production'
    import nfl2.live as live
    import nfl2.data as data
    router = SnapshotRouter(arm)
    live._q = router
    live.CACHE = run / 'training-cache'
    live.training_panel_through.cache_clear()
    # Materialize and compare historical training before any model fitting.
    tr = live.training_panel_through(2025)
    if arm == 'salaryfix':
        control = pd.read_parquet(LOCAL / 'control' / 'training-cache' / 'training_through_2025.parquet')
        pd.testing.assert_frame_equal(control, tr)
    sys.argv = ['scripts/live_week.py', '--season', '2026', '--week', '2', '--group', '153428',
                '--entries', '97', '--lev', '32', '--boom', '128', '--sims', '10000', '--k', '1',
                '--seed', '2026', '--selector', 'dual_emax', '--emit-a5-sidecars']
    with data.outcome_firewall(2026):
        state = runpy.run_path(str(LAB / 'scripts/live_week.py'), run_name='__main__')
        from nfl2.hsim import world
        fr, games = state['fr'], state['live_games']
        wt, wc, eff = world.calibrate_weights(fr, 2026, 2, 2326, game_inputs=games)
        replay = world._sample(fr, 2026, 2, 10000, 2326, wt, wc, recenter=False, team_eff=eff, game_inputs=games).astype(np.float32)
        assert np.array_equal(replay, state['hs']), 'hsim calibration replay differs'
        ha = world._sample(fr, 2026, 2, 10000, 2426, wt, wc, recenter=False, team_eff=eff, game_inputs=games).astype(np.float32)
    arrays = {}
    for label, arr in [('generation', state['draws']), ('I_selection', state['sel_draws']),
                       ('I_audit', state['aud_draws']), ('H_selection', state['hs']), ('H_audit', ha)]:
        assert arr.dtype == np.float32 and np.isfinite(arr).all()
        p = run / (label + '.npy')
        with p.open('xb') as f:
            np.save(f, arr, allow_pickle=False)
        arrays[label] = dict(path=str(p), sha256=sha(p.read_bytes()), shape=list(arr.shape))
    frozen_json(run / 'receipt.json', dict(arm=arm, lab_source_sha=state['sha'],
        adapter_sha256=sha(Path(__file__).read_bytes()), research_source_sha=subprocess.check_output(['git','-C',str(RESEARCH),'rev-parse','HEAD'],text=True).strip(),
        original_run=str(state['out'].resolve()), original_receipt_sha256=sha((state['out']/'receipt.json').read_bytes()),
        query_snapshots=router.calls, arrays=arrays, hsim_calibration_reproduced=True,
        calibration=dict(target_weights=wt.tolist(), carry_weights=wc.tolist(), team_eff=eff),
        elapsed_seconds=time.monotonic()-started, current_outcomes_read=False,
        scope='research scratch namespaces; unchanged full CLI; not an entered book'))
    print('COMPLETE_CHAIN_ARM_PASS', arm, state['out'], time.monotonic()-started, flush=True)


if __name__ == '__main__':
    main()
