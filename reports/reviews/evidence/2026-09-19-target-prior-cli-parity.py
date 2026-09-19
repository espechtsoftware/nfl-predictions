"""Full CLI parity against immutable complete-chain and prior-trace artifacts."""
import hashlib
import json
import os
import runpy
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

R = Path(__file__).resolve().parent
REPO = R.parents[2]
LAB = Path('/home/erich/projects/.nfl2-worktrees/live-target-prior')
SHA = '5adc176'
ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918')
CHAIN = ROOT / 'complete-chain-cli'
LOCAL = ROOT / 'target-prior-cli-parity'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def forbidden(*args, **kwargs):
    raise AssertionError('provider query forbidden during frozen CLI parity')


def main():
    rule = sys.argv[1]
    assert rule in ('none', 'one_prior_game', 'past_empirical')
    assert Path.cwd() == LAB
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert actual == subprocess.check_output(['git', 'rev-parse', SHA], text=True).strip()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip()
    src = R / '2026-09-19-repaired-chain-d1600-cli.py'
    assert src.read_bytes() == subprocess.check_output(['git', '-C', str(REPO), 'show',
        '170c3b46:reports/reviews/evidence/' + src.name])
    helpers = runpy.run_path(str(src))
    bigquery.Client.query = forbidden
    router = helpers['SnapshotRouter']('salaryfix')
    run = LOCAL / rule
    run.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    prior = json.loads((R / '2026-09-19-zero-target-prior-simulator.json').read_text())
    model = json.loads((R / '2026-09-19-zero-target-prior-read.json').read_text())['prospective_model']
    baseline = json.loads((CHAIN / 'salaryfix/receipt.json').read_text())
    baseout = Path(baseline['original_run'])
    assert sha(baseout / 'receipt.json') == baseline['original_receipt_sha256']
    base_receipt = json.loads((baseout / 'receipt.json').read_text())
    trace_name = 'baseline' if rule == 'none' else rule
    sys.path.insert(0, str(LAB / 'src'))
    os.environ['NFL2_LIVE_CENTER'] = 'production'
    import nfl2.live as live
    import nfl2.data as data
    live._q = router
    live.CACHE = run / 'training-cache'
    live.training_panel_through.cache_clear()
    replay = json.loads((R / '2026-09-19-hsim-replay-preflight.json').read_text())
    files = {}
    for rec in replay['benchmark']:
        key = rec['uri'].split('/benchmark/v0/', 1)[1]
        path = Path('/home/erich/.cache/nfl2/v0') / key
        assert sha(path) == rec['sha256']
        files[key] = path
    def listing(prefix):
        assert prefix in {'warehouse/' + x + '/' for x in
                          ('player_week_training', 'raw_weekly_stats', 'raw_schedules')}
        return sorted(x for x in files if x.startswith(prefix))
    def fetching(key):
        assert key in files
        return files[key]
    data._list, data._fetch = listing, fetching
    sys.argv = ['scripts/live_week.py', '--season', '2026', '--week', '2', '--group', '153428',
        '--entries', '97', '--lev', '32', '--boom', '128', '--sims', '10000', '--k', '1',
        '--seed', '2026', '--selector', 'dual_emax', '--emit-a5-sidecars', '--hsim-target-prior', rule]
    with data.outcome_firewall(2026):
        state = runpy.run_path(str(LAB / 'scripts/live_week.py'), run_name='__main__')
        from nfl2.hsim import world
        spec = state['hsim_target_prior']
        assert spec == (None if rule == 'none' else {'rule': rule} if rule == 'one_prior_game'
                        else {'rule': rule, 'model': model})
        fr, games = state['fr'], state['live_games']
        kwargs = {} if spec is None else {'target_prior': spec}
        wt, wc, eff = world.calibrate_weights(fr, 2026, 2, 2326, game_inputs=games, **kwargs)
        assert dict(target_weights=wt.tolist(), carry_weights=wc.tolist(), team_eff=eff) == prior['calibration'][trace_name]
        audit = world._sample(fr, 2026, 2, 10000, 2426, wt, wc, recenter=False,
                              team_eff=eff, game_inputs=games).astype(np.float32)
    output = state['out']
    pd.testing.assert_frame_equal(pd.read_parquet(output / 'frame.parquet'), pd.read_parquet(baseout / 'frame.parquet'))
    candidates = pd.read_parquet(output / 'candidates.parquet')
    old_candidates = pd.read_parquet(baseout / 'candidates.parquet')
    omit = [] if rule == 'none' else ['book_rank', 'book_rank_wemax']
    pd.testing.assert_frame_equal(candidates.drop(columns=omit), old_candidates.drop(columns=omit))
    orderrec = baseline['candidate_player_orders']
    assert sha(orderrec['path']) == orderrec['sha256']
    orders = [[str(p['id']) for p in lu.players] for lu in state['cands']]
    assert orders == json.loads(Path(orderrec['path']).read_text())
    arrays = {}
    for name, arr, rec in [
        ('generation', state['draws'], baseline['arrays']['generation']),
        ('I_selection', state['sel_draws'], baseline['arrays']['I_selection']),
        ('I_audit', state['aud_draws'], baseline['arrays']['I_audit']),
        ('H_selection', state['hs'], prior['array_identities'][trace_name + '_selection']),
        ('H_audit', audit, prior['array_identities'][trace_name + '_audit'])]:
        assert sha(rec['path']) == rec['sha256']
        assert arr.dtype == np.float32 and arr.shape == (len(fr), 10000) and np.isfinite(arr).all()
        assert np.array_equal(arr, np.load(rec['path'], allow_pickle=False)), name
        arrays[name] = dict(exact=True, expected_sha256=rec['sha256'])
    for kind, book in [('emax', state['book']), ('wemax', state['book_wemax'])]:
        assert list(map(int, book)) == prior['books'][trace_name + '_' + kind], kind
    receipt = json.loads((output / 'receipt.json').read_text())
    if rule == 'none':
        config = dict(receipt['config'])
        assert config.pop('hsim_target_prior') == {'rule': 'none'}
        assert config == base_receipt['config']
        for name in ('book.csv', 'book_wemax.csv'):
            assert (output / name).read_bytes() == (baseout / name).read_bytes(), name
    elif rule == 'past_empirical':
        assert receipt['config']['hsim_target_prior']['shrinkage_pseudocount'] == 20
    result = dict(rule=rule, source_commit=actual, adapter_sha256=sha(__file__),
        original_run=str(output.resolve()), full_frame_exact=True, candidate_orders_exact=True,
        candidate_nonrank_columns_exact=True, arrays=arrays, calibration_exact=True,
        emax_and_wemax_orders_exact=True, default_receipt_delta={'hsim_target_prior': {'rule': 'none'}},
        expected_trace_sha256=sha(R / '2026-09-19-zero-target-prior-simulator.json'),
        query_snapshots=router.calls, elapsed_seconds=time.monotonic()-started,
        current_outcomes_read=False, provider_queries_forbidden=True)
    with (run / 'receipt.json').open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False, default=str)
    print('PRIOR_CLI_PARITY_PASS', rule, result['elapsed_seconds'], flush=True)


if __name__ == '__main__':
    main()
