"""Additional selection batches and fresh audit with fixed, replay-proved fitted laws."""
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
LAB = Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918')
LOCAL = ROOT / 'selection-precision'
OUT = Path(__file__).with_suffix('.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def forbidden(*args, **kwargs):
    raise AssertionError('provider query forbidden')


def main():
    assert not LOCAL.exists() and not OUT.exists()
    assert Path.cwd() == LAB
    source = subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
    assert source == '2dc116ce95647a776ba9c36cf194f44d022d03a4'
    assert not subprocess.check_output(['git','status','--porcelain'], text=True).strip()
    routerfile = R / '2026-09-19-repaired-chain-d1600-cli.py'
    assert routerfile.read_bytes() == subprocess.check_output(['git','-C',str(R.parents[2]),'show',
        '170c3b46:reports/reviews/evidence/'+routerfile.name])
    bigquery.Client.query = forbidden
    router = runpy.run_path(str(routerfile))['SnapshotRouter']('salaryfix')
    LOCAL.mkdir()
    started = time.monotonic()
    original = json.loads((ROOT/'complete-chain-cli/salaryfix/receipt.json').read_text())
    baseout = Path(original['original_run'])
    assert sha(baseout/'receipt.json') == original['original_receipt_sha256']
    sys.path.insert(0,str(LAB/'src'))
    os.environ['NFL2_LIVE_CENTER'] = 'production'
    import nfl2.live as live
    import nfl2.data as data
    live._q = router
    live.CACHE = LOCAL / 'training-cache'
    live.training_panel_through.cache_clear()
    files = {}
    for rec in json.loads((R/'2026-09-19-hsim-replay-preflight.json').read_text())['benchmark']:
        key = rec['uri'].split('/benchmark/v0/',1)[1]
        path = Path('/home/erich/.cache/nfl2/v0')/key
        assert sha(path) == rec['sha256']
        files[key] = path
    dst = json.loads((R/'2026-09-19-target-prior-cli-dst-input.json').read_text())
    assert sha(LAB/'benchmark/MANIFEST-v1.json') == dst['manifest_sha256']
    assert sha(dst['path']) == dst['sha256']
    files[dst['key']] = Path(dst['path'])
    def listing(prefix):
        assert prefix in ({'warehouse/'+x+'/' for x in ('player_week_training','raw_weekly_stats','raw_schedules')}
                          | {'panel107/snap_pitclean_k1/'})
        return sorted(x for x in files if x.startswith(prefix))
    def fetching(key):
        assert key in files
        return files[key]
    data._list,data._fetch = listing,fetching
    sys.argv = ['scripts/live_week.py','--season','2026','--week','2','--group','153428',
        '--entries','97','--lev','32','--boom','128','--sims','10000','--k','1','--seed','2026',
        '--selector','dual_emax','--emit-a5-sidecars']
    records = {}
    with data.outcome_firewall(2026):
        state = runpy.run_path(str(LAB/'scripts/live_week.py'),run_name='__main__')
        fr = state['fr']
        pd.testing.assert_frame_equal(fr,pd.read_parquet(baseout/'frame.parquet'))
        for label,key in [('generation','draws'),('I_selection','sel_draws'),('I_audit','aud_draws'),('H_selection','hs')]:
            rec = original['arrays'][label]
            assert sha(rec['path']) == rec['sha256']
            assert np.array_equal(state[key],np.load(rec['path'],allow_pickle=False)),label
        assert np.array_equal(state['finish_bank'](state['model_draws'](2076)),state['sel_draws'])
        from nfl2.hsim import world
        cal = original['calibration']
        wt,wc,eff = np.array(cal['target_weights']),np.array(cal['carry_weights']),cal['team_eff']
        def hsim(seed):
            return world._sample(fr,2026,2,10000,seed,wt,wc,recenter=False,team_eff=eff,
                                 game_inputs=state['live_games']).astype(np.float32)
        for label,seed in [('H_selection',2326),('H_audit',2426)]:
            rec = original['arrays'][label]
            assert sha(rec['path']) == rec['sha256']
            assert np.array_equal(hsim(seed),np.load(rec['path'],allow_pickle=False)),label
        print('PRECISION_ORIGINAL_LAWS_EXACT',flush=True)
        for component,draw,seeds in [('I',lambda seed:state['finish_bank'](state['model_draws'](seed)),
                                       [(f'selection_{i}',6202600+i) for i in range(1,5)]+[('audit',8202601)]),
                                     ('H',hsim,[(f'selection_{i}',7202600+i) for i in range(1,5)]+[('audit',9202601)])]:
            for name,seed in seeds:
                assert time.monotonic()-started < 580
                arr = draw(seed)
                assert arr.dtype == np.float32 and arr.shape == (len(fr),10000) and np.isfinite(arr).all()
                dest = LOCAL / (component+'_'+name+'.npy')
                with dest.open('xb') as f:
                    np.save(f,arr,allow_pickle=False)
                records[component+'_'+name] = dict(path=str(dest),sha256=sha(dest),seed=seed,shape=list(arr.shape))
                print('PRECISION_BANK_SAVED',component,name,seed,flush=True)
    result = dict(source_commit=source, source_sha256=sha(__file__), original_laws_exact=True,
        frame_path=str(baseout/'frame.parquet'),frame_sha256=sha(baseout/'frame.parquet'),
        original_receipt_sha256=sha(ROOT/'complete-chain-cli/salaryfix/receipt.json'),
        calibration_sha256=hashlib.sha256(json.dumps(cal,sort_keys=True).encode()).hexdigest(),
        arrays=records,query_snapshots=router.calls,elapsed_seconds=time.monotonic()-started,
        scope='Additional independent event draws only; original fits/calibration/frame/centering exact; no provider query or current outcomes.')
    with OUT.open('x') as f:
        json.dump(result,f,indent=2,allow_nan=False,default=str)
    print('PRECISION_BANK_CONSTRUCTION_PASS',result['elapsed_seconds'],flush=True)


if __name__=='__main__':
    main()
