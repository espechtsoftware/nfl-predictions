"""Frozen four-case usage/game-line sensitivity, canonical game order, fixed calibration audits."""
import hashlib
import io
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from google.cloud import storage

R=Path('reports/reviews/evidence')
OUT=R/'2026-09-19-usage-schedule-factorial.json'
LOCAL=Path('/home/erich/projects/review-evidence/overnight-20260918/hsim-factorial')
CACHE=Path('/home/erich/projects/review-evidence/overnight-20260918/hsim-replay')
LAB=Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
SOURCE='40a9be9'
assert not OUT.exists() and not LOCAL.exists();LOCAL.mkdir()
features=['snap_share_l4','target_share_l4','carry_share_l4','games_played_prior','rz20_target_share_l4','gl3_carry_share_l4']
raw=(R/'2026-09-19-salaryfix-usage-input.json').read_bytes()
input_sha=hashlib.sha256(raw).hexdigest()
assert input_sha=='a021f3ae048033b02a974f616b5b9d68524fe731d9f3d89e35d5cb8670c90025'
usage=pd.DataFrame(json.loads(raw)['rows']).set_index('gsis_id');assert usage.index.is_unique
replay=json.loads((R/'2026-09-19-hsim-replay-preflight.json').read_text());assert replay['exact_equal']
source_hashes={}
for name in sorted(set(replay['source_hashes'])|{'src/nfl2/hsim/live_games.py'}):
    expected=subprocess.check_output(['git','-C',str(LAB),'show',SOURCE+':'+name])
    assert (LAB/name).read_bytes()==expected
    source_hashes[name]=hashlib.sha256(expected).hexdigest()
files={}
for rec in replay['benchmark']:
    rel=rec['uri'].split('/benchmark/v0/',1)[1];p=Path('/home/erich/.cache/nfl2/v0')/rel
    assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['sha256'];files[rel]=p
sys.path.insert(0,str(LAB/'src'))
import nfl2.data as data

def allowed_list(prefix):
    assert prefix in {'warehouse/'+x+'/' for x in ['player_week_training','raw_weekly_stats','raw_schedules']}
    return sorted(x for x in files if x.startswith(prefix))

def allowed_fetch(key):
    assert key in files;return files[key]

data._list=allowed_list;data._fetch=allowed_fetch
from nfl2.hsim import world
from nfl2.hsim.live_games import from_live_schedule,validate_game_inputs,game_input_receipt
manifest=json.loads((R/'2026-09-18-week2-archive-preflight.json').read_text())
verified={}

def artifact(name):
    rec=next(x for x in manifest['objects'] if x['name']==name)
    raw=(CACHE/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==rec['sha256']
    verified[name]={'sha256':rec['sha256'],'generation':rec['generation']};return raw

cols=replay['frame_columns']+['game_id','game_total','spread']
fr=pq.read_table(io.BytesIO(artifact('frame.parquet')),columns=cols).to_pandas()
assert len(fr)==fr.id.nunique()==435
changed=fr.copy(deep=True);match=fr.id.isin(usage.index)
for col in features:changed[col]=fr[col].where(~match,pd.to_numeric(fr.id.map(usage[col]),errors='raise'))
assert changed[[c for c in cols if c not in features]].equals(fr[[c for c in cols if c not in features]])
c=pq.read_table(io.BytesIO(artifact('candidates.parquet')),columns=['players']).to_pydict()
index={str(v):i for i,v in enumerate(fr.id)}
rosters=np.asarray([[index[v] for v in text.split(',')] for text in c['players']],dtype=int)
assert rosters.shape==(6400,9) and len(set(tuple(sorted(r)) for r in rosters))==6400
I=np.load(io.BytesIO(artifact('incumbent_player_scores.npy')),allow_pickle=False)
assert I.shape==(435,10000) and I.dtype==np.float32 and np.isfinite(I).all()
started=time.monotonic();selection={};audit={};calibration={};array_ids={}
with data.outcome_firewall(2026):
    old_games=world._games(fr,2026,2)
    old_games['game_id']=[f'2026_02_{a}_{h}' for h,a in zip(old_games.home,old_games.away)]
    old_games['season']=2026;old_games['week']=2
    old_games=old_games.sort_values('game_id',kind='stable').reset_index(drop=True)
    old_games=validate_game_inputs(fr,old_games,2026,2)
    # Live schedule rows are independently reconstructed from the archived frame,
    # then the patch validates team coverage, opposing signs and frame consistency.
    schedule=[]
    for gid,rows in fr.groupby('game_id',sort=True):
        _,_,away,home=gid.split('_');h=rows[rows.team==home].iloc[0]
        schedule.append(dict(game_id=gid,home_team=home,away_team=away,total_line=h.game_total,spread_line=h.spread))
    live_games=from_live_schedule(fr,pd.DataFrame(schedule),2026,2)
    unchanged=[c for c in old_games if c not in ['total_line','spread_home']]
    pd.testing.assert_frame_equal(old_games[unchanged],live_games[unchanged],check_dtype=False)
    cases={'A':(fr,old_games),'B':(changed,old_games),'C':(fr,live_games),'D':(changed,live_games)}
    for label,(frame,games) in cases.items():
        wt,wc,eff=world.calibrate_weights(frame,2026,2,2326,game_inputs=games)
        calibration[label]=dict(target_weights=wt.tolist(),carry_weights=wc.tolist(),team_eff=eff)
        for bank,seed in [('selection',2326),('audit',2426)]:
            p=world._sample(frame,2026,2,10000,seed,wt,wc,recenter=False,team_eff=eff,game_inputs=games).astype(np.float32)
            assert p.shape==(435,10000) and np.isfinite(p).all()
            path=LOCAL/(label+'_'+bank+'.npy')
            with path.open('xb') as h:np.save(h,p,allow_pickle=False)
            array_ids[label+'_'+bank]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            (selection if bank=='selection' else audit)[label]=p
T=np.empty((6400,20000),dtype=np.float32)
for i,r in enumerate(rosters):T[i,:10000]=I[r].sum(axis=0,dtype=np.float32)
books={}
for label in 'ABCD':
    for i,r in enumerate(rosters):T[i,10000:]=selection[label][r].sum(axis=0,dtype=np.float32)
    book=[];cur=np.full(20000,-np.inf)
    for _ in range(97):
        assert time.monotonic()-started<580,'compute cap exceeded'
        values=np.empty(6400)
        for start in range(0,6400,64):values[start:start+64]=np.maximum(T[start:start+64].astype(np.float64),cur).mean(axis=1)
        values[book]=-np.inf;pick=int(np.argmax(values));book.append(pick);cur=np.maximum(cur,T[pick])
    assert len(set(book))==97;books[label]=book
    print('selected',label,flush=True)
del T,selection
prior=json.loads((R/'2026-09-18-week2-current-selector-diagnostic.json').read_text());assert prior['baseline_reproduced']
books['archived']=prior['selected']
raw=subprocess.check_output(['git','-C',str(LAB),'show','e7255e9:results/contest/milly_winners.json'])
assert hashlib.sha256(raw).hexdigest()=='4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
winners=np.asarray(sorted(json.loads(raw).values()),dtype=np.float64);assert len(winners)==48
spans=[(0,1),(1,24),(24,25),(25,30),(30,31),(31,33),(33,43),(43,53),(53,63),(63,79),(79,95),(95,97)]
regions={f'prefix{k}':list(range(k)) for k in (1,10,20,30,40,80,90,97)}
regions.update({f'block{a+1}_{z}':list(range(a,z)) for a,z in spans})

def util(x):return (1/(1+np.exp(-(x[:,None]-winners)/8))).mean(axis=1)

def maximum(p,book):return np.stack([p[rosters[c]].sum(axis=0,dtype=np.float32) for c in book])

metrics={}
for law,p in [('incumbent_selection',I)]+[(key+'_hsim_audit',audit[key]) for key in 'ABCD']:
    metrics[law]={}
    for label,book in books.items():
        totals=maximum(p,book);measures={}
        for key,region in regions.items():
            mx=totals[region].max(axis=0).astype(np.float64)
            measures[key]=dict(emax=float(mx.mean()),p220=float((mx>=220).mean()),global_proxy=float(util(mx).mean()))
        metrics[law][label]=measures
contrasts={};after=maximum(audit['D'],books['D']).max(axis=0).astype(np.float64)
for label in 'ABC':
    before=maximum(audit['D'],books[label]).max(axis=0).astype(np.float64);contrasts['D-'+label]={}
    for name,delta in [('emax',after-before),('p220',(after>=220).astype(float)-(before>=220).astype(float)),('global_proxy',util(after)-util(before))]:
        mean=float(delta.mean());se=float(delta.std(ddof=1)/np.sqrt(len(delta)))
        contrasts['D-'+label][name]=dict(delta=mean,monte_carlo_se=se,normal_95=[mean-1.96*se,mean+1.96*se])
overlap={a:{b:len(set(x)&set(y)) for b,y in books.items()} for a,x in books.items()}
result=dict(cases={'A':'archived usage/benchmark lines','B':'recovered usage/benchmark lines','C':'archived usage/live-frame lines','D':'recovered usage/live-frame lines'},
    books=books,overlap=overlap,first_rosters={k:[str(fr.id.iloc[i]) for i in rosters[b[0]]] for k,b in books.items()},
    metrics=metrics,contrasts_under_D_audit=contrasts,calibration=calibration,
    game_inputs={'benchmark':game_input_receipt(old_games),'live_frame':game_input_receipt(live_games)},
    array_identities=array_ids,verified_archive=verified,usage_input_sha256=input_sha,source_hashes=source_hashes,
    elapsed_seconds=time.monotonic()-started,
    provenance=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_status=subprocess.check_output(['git','status','--porcelain'],text=True),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),python=platform.python_version(),numpy=np.__version__),
    scope='Canonical-order co-run factorial; fixed means/pool; hsim-only independent audits; no real-world efficacy or live adoption claim.')
with OUT.open('x') as h:json.dump(result,h,indent=2,allow_nan=False)
print(json.dumps(dict(contrasts=contrasts,overlap=overlap,elapsed_seconds=result['elapsed_seconds'],whole_book={law:{book:ms['prefix97'] for book,ms in bs.items()} for law,bs in metrics.items()}),indent=2),flush=True)
