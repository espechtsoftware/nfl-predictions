"""Construct historical I/H forecasts with current-season outcomes inaccessible."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import pandas as pd

LAB = Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
EVIDENCE = Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out',required=True)
    ap.add_argument('--smoke',action='store_true')
    ap.add_argument('--lab-root',default=str(LAB))
    ap.add_argument('--support',default=str(EVIDENCE/'2026-09-19-law-weight-support.json'))
    ap.add_argument('--source-contract')
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True,exist_ok=False)
    assert not os.environ.get('NFL2_UNSEAL_2025')
    lab=Path(a.lab_root)
    if a.source_contract:
        contract=json.loads(Path(a.source_contract).read_text())
        assert contract['commit']=='2dc116ce95647a776ba9c36cf194f44d022d03a4'
        assert set(contract['files'])=={str(p.relative_to(lab)) for p in (lab/'src').rglob('*.py')}
        for name,digest in contract['files'].items(): assert sha(lab/name)==digest
    else:
        assert subprocess.check_output(['git','-C',str(lab),'rev-parse','HEAD'],text=True).strip() == '2dc116ce95647a776ba9c36cf194f44d022d03a4'
        assert not subprocess.check_output(['git','-C',str(lab),'status','--porcelain'],text=True).strip()
    support = json.loads(Path(a.support).read_text())
    files = {}
    for rec in support['files']:
        assert sha(rec['path']) == rec['sha256']
        key = rec['uri'].split('/benchmark/',1)[1].split('/',1)[1]
        files[key] = Path(rec['path'])
    sys.path.insert(0,str(lab/'src'))
    import nfl2.data as data
    def listing(prefix):
        answer = sorted(k for k in files if k.startswith(prefix))
        assert answer, prefix
        return answer
    def fetching(key):
        assert key in files, key
        return files[key]
    data._list, data._fetch = listing, fetching
    def forbidden(*args,**kwargs): raise AssertionError('provider access forbidden')
    data._client = forbidden
    from nfl2.pipeline import slate_frame,simulate_slate,slate_seed
    from nfl2.hsim.world import simulate_hsim
    todo = support['slates'][:1] if a.smoke else support['slates']
    draws = 1000 if a.smoke else 4000
    banks = [19260901] if a.smoke else [19260901,19260902]
    records=[]
    start=time.monotonic()
    for row in todo:
        season,week=row['season'],row['week']
        t=time.monotonic()
        with data.outcome_firewall(season):
            fr=slate_frame(season,week)
            labelcols=[c for c in fr if c=='actual' or c=='was_active' or c.startswith('y_')]
            assert labelcols and fr[labelcols].isna().all().all()
            assert fr.id.nunique()==len(fr)==row['players']
            safe=fr.drop(columns=labelcols)
            fp=out/f'{season}-w{week:02}-frame.parquet'
            safe.to_parquet(fp,index=False)
            for bank in banks:
                inc=simulate_slate(fr,n_sims=draws,seed=slate_seed(bank,season,week),
                                   law_env={'NFL2_ENSEMBLE':'1','NFL2_CENTER':'mean'})
                hsim=simulate_hsim(fr,season,week,draws,seed=slate_seed(bank+100,season,week)).astype(np.float32)
                arrays={}
                for name,arr in [('I',inc),('H',hsim)]:
                    assert arr.shape==(len(fr),draws) and np.isfinite(arr).all()
                    dest=out/f'{season}-w{week:02}-b{bank}-{name}.npy'
                    with dest.open('xb') as f: np.save(f,arr,allow_pickle=False)
                    arrays[name]={'path':dest.name,'sha256':sha(dest),'shape':list(arr.shape)}
                records.append({'season':season,'week':week,'bank':bank,'frame':fp.name,
                                'frame_sha256':sha(fp),'arrays':arrays})
        print(json.dumps({'season':season,'week':week,'rows':len(fr),'seconds':time.monotonic()-t,
                           'current_season_outcomes_accessible':False}),flush=True)
    receipt={'smoke':a.smoke,'source_sha256':sha(__file__),'lab_commit':'2dc116ce95647a776ba9c36cf194f44d022d03a4',
             'support_sha256':sha(a.support),'records':records,
             'runtime':{'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__},
             'elapsed_seconds':time.monotonic()-start,'current_season_outcomes_accessible':False}
    with (out/'receipt.json').open('x') as f: json.dump(receipt,f,indent=2,allow_nan=False)
    print('FORECAST_CONSTRUCTION_PASS',receipt['elapsed_seconds'],flush=True)

if __name__=='__main__': main()
