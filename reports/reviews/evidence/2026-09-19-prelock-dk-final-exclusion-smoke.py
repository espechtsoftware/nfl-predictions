"""Engineering smoke: hypothetical OUT labels on real saved candidates.

No real status capture is edited and no entry/delivery book is emitted.
Only exact-K, non-exposure, source preservation and roster legality are tested.
"""
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('dk_reselector',HERE/'2026-09-19-prelock-dk-reselect.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sys.path[:0]=[str(m.base.REPO/'src'),str(m.base.LAB/'src')]
BASE=Path('/home/erich/projects/review-evidence/overnight-20260918')
CAPTURE=BASE/'prelock-dk-final-exclusion-capture'
RUN=m.base.LAB/'results/live/2026-w02/20260919T030727287666Z-2dc116c'
OUTPUT=BASE/'prelock-dk-final-exclusion-smoke.json'
assert m.base.sha(HERE/'2026-09-19-prelock-dk-reselect.py')=='a2a240aa4a44d15bc8f973246722dc986978ceda9a8af69dccd3420d7f6c82cf'
assert not OUTPUT.exists()
original_hashes={p.name:m.base.sha(p) for p in CAPTURE.iterdir() if p.is_file()}
fr=pd.read_parquet(RUN/'frame.parquet');cands=pd.read_parquet(RUN/'candidates.parquet')
rec=json.loads((RUN/'receipt.json').read_text())
orders=m.base.candidate_orders(fr,cands)
dk,_=m.load_capture(CAPTURE)
# Hypothetical only: both are currently D, not confirmed OUT.
ids=['00-0036212','00-0039064']
flowers=fr.loc[fr.display_name.eq('Zay Flowers'),'id'].tolist();assert len(flowers)==1
assert ids[1]==flowers[0]
assert set(ids)<=set(fr.id)
pids=set(fr.loc[fr.id.isin(ids),'dk_player_id'])
assert set(dk.loc[dk.dk_player_id.isin(pids),'status'])=={'D'}
synthetic=dk.copy(deep=True);synthetic.loc[synthetic.dk_player_id.isin(pids),'status']='OUT'
keep,excluded,_=m.eligible_candidates(fr,orders,synthetic)
assert set(excluded)==set(ids) and 97<=len(keep)<len(cands)
banks={}
for component,key in [('I','incumbent_player_scores'),('H','corrected_hsim_player_scores')]:
    p=RUN/(key+'.npy');assert m.base.sha(p)==rec['a5_sidecars'][key]['sha256']
    banks[component]=np.load(p,allow_pickle=False)
index={x:i for i,x in enumerate(fr.id)};roster=np.asarray([[index[x] for x in orders[i]] for i in keep],int)
t=m.base.totals(banks,roster);book=[keep[i] for i in m.base.greedy(t,97)]
from nfl2.validator import validate_roster
f=fr.set_index('id');args=[f[k].to_dict() for k in ('pos','team','opp','salary')]
assert len(book)==len(set(book))==97
for i in book:
    assert not(set(orders[i])&set(excluded))
    assert not validate_roster(orders[i],*args,salary_floor=49000,qb_stack_min=2,bring_back_min=1,
        forbid_rb_vs_dst=True,forbid_two_rb_same_team=True)
assert original_hashes=={p.name:m.base.sha(p) for p in CAPTURE.iterdir() if p.is_file()}
m.write(OUTPUT,dict(passed=True,synthetic_status_scenario=True,real_statuses_remain='D',
    no_real_capture_modified=True,no_book_emitted=True,no_scoring_metrics_evaluated=True,
    candidates_before=len(cands),eligible_candidates=len(keep),selected=97,unique=97,
    excluded_ids=excluded,zero_excluded_exposure=True,all_rosters_legal=True,
    script_sha256=m.base.sha(__file__),selector_source_sha256=m.base.sha(HERE/'2026-09-19-prelock-dk-reselect.py')))
print('REAL_CORPUS_SYNTHETIC_EXCLUSION_SMOKE_PASS',len(keep),97,flush=True)
