"""Frozen descriptive cache-input comparison. No NFL outcomes or efficacy scores."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def summarize(a,b):
    d=np.asarray(b,float)-np.asarray(a,float)
    assert np.isfinite(d).all()
    return dict(changed=int(np.count_nonzero(d)),above_1e_6=int(np.count_nonzero(abs(d)>1e-6)),
                mean_signed=float(d.mean()),mean_absolute=float(abs(d).mean()),max_absolute=float(abs(d).max()))

def main():
    proofs={k:json.loads((ROOT/('live-cli-'+k+'-proof.json')).read_text()) for k in ['host','fresh']}
    runs={k:Path(v['run']) for k,v in proofs.items()}
    rec={k:v['receipt'] for k,v in proofs.items()}
    for k in proofs:assert sha(runs[k]/'receipt.json')==proofs[k]['receipt_sha256']
    checks={}
    for key in ['season','week','draft_group','lock_utc','salary_pull','identity','config','banks']:
        checks[key]=rec['host'][key]==rec['fresh'][key]
    checks['live_input_hashes']=rec['host']['inputs']['content_hashes']==rec['fresh']['inputs']['content_hashes']
    frames={k:pd.read_parquet(p/'frame.parquet') for k,p in runs.items()}
    checks['player_order']=frames['host'].id.tolist()==frames['fresh'].id.tolist()
    checks['columns']=frames['host'].columns.tolist()==frames['fresh'].columns.tolist()
    # Config contains fitted numerical diagnostics which can legitimately change;
    # isolate structural choices from those diagnostics, but publish the full diff.
    config_diff={k:{a:rec[a]['config'].get(k) for a in rec} for k in set(rec['host']['config'])|set(rec['fresh']['config'])
                 if rec['host']['config'].get(k)!=rec['fresh']['config'].get(k)}
    structural=['lev','boom','k','operational_k','sims','seed','selector','production_generated_at','production_rows',
                'matched_skill','unmatched_skill_fallback_lab_blend','dst_matched','dst_unmatched_fallback_prior','arm','hsim_game_inputs']
    checks['config']=all(rec['host']['config'].get(k)==rec['fresh']['config'].get(k) for k in structural)
    result=dict(checks=checks,matched_live_pair=all(checks.values()),config_differences=config_diff,
       proof_sha256={k:sha(ROOT/('live-cli-'+k+'-proof.json')) for k in runs},
       cache_sha256={k:v['historical_cache_sha256'] for k,v in proofs.items()},
       reader_sha256=sha(Path(__file__)),scope='D160 engineering sensitivity; selection-bank distribution changes, no efficacy scores or NFL outcomes; pre-vetting books')
    if result['matched_live_pair']:
        a,b=frames['host'],frames['fresh'];diffs={}
        for col in a:
            equal=a[col].eq(b[col])|(a[col].isna()&b[col].isna())
            n=int((~equal.fillna(False)).sum())
            if n:diffs[col]=n
        result['changed_frame_columns']=diffs
        result['mean_differences']={c:summarize(a[c],b[c]) for c in ['model_points_pre','mean_projection','proj']}
        marginals={}
        for kind in ['incumbent','corrected_hsim']:
            x,y=[np.load(runs[k]/(kind+'_player_scores.npy'),allow_pickle=False) for k in ['host','fresh']]
            assert x.shape==y.shape==(len(a),10000) and np.isfinite(x).all() and np.isfinite(y).all()
            marginals[kind]={n:summarize(f(x),f(y)) for n,f in [('mean',lambda z:z.mean(axis=1,dtype=float)),
              ('p95',lambda z:np.quantile(z,.95,axis=1)),('p99',lambda z:np.quantile(z,.99,axis=1))]}
        result['selection_bank_marginals']=marginals
        c={k:pd.read_parquet(p/'candidates.parquet',columns=['players','book_rank']) for k,p in runs.items()}
        sets={k:set(v.players) for k,v in c.items()}
        result['candidates']=dict(host=len(sets['host']),fresh=len(sets['fresh']),shared=len(sets['host']&sets['fresh']))
        books={k:v[v.book_rank.notna()].sort_values('book_rank').players.tolist() for k,v in c.items()}
        assert all(len(v)==len(set(v))==97 for v in books.values())
        result['prefix_overlap']={str(n):dict(shared=len(set(books['host'][:n])&set(books['fresh'][:n])),
            same_rank=sum(a==b for a,b in zip(books['host'][:n],books['fresh'][:n]))) for n in [1,10,20,30,40,80,97]}
    else:result['attribution']='Confounded pair; no cache-only effect claim.'
    with (ROOT/'host-cache-effect.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
