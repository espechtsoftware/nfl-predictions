"""Fixed-pool participation transfer to actual deployed inputs and host cache.

No new candidates, provider calls, current scoring outcomes or live adoption.
"""
import hashlib
import importlib.util
import json
import runpy
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from google.cloud import bigquery

HERE=Path(__file__).parent
REPO=HERE.parents[2]
ROOT=Path('/home/erich/projects/review-evidence/overnight-20260918')
LAB=Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
RELEASE=ROOT/'authorized-release-v2'
OUT=ROOT/'participation-host-transfer'
MANIFEST=HERE/'2026-09-19-participation-host-transfer-inputs.json'
SOURCE='2dc116ce95647a776ba9c36cf194f44d022d03a4'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),HERE/name)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def write(p,r):
    with Path(p).open('x') as f:json.dump(r,f,indent=2,default=str,allow_nan=False)
def forbidden(*args,**kwargs):raise AssertionError('provider query forbidden')


def inputs():
    assert subprocess.check_output(['git','-C',str(LAB),'rev-parse','HEAD'],text=True).strip()==SOURCE
    assert not subprocess.check_output(['git','-C',str(LAB),'status','--porcelain','--untracked-files=all'],text=True).strip()
    sys.path[:0]=[str(REPO/'src'),str(LAB/'src')]
    bigquery.Client.query=forbidden
    base=load('2026-09-19-participation-transfer.py')
    select=load('2026-09-19-participation-reselect-v2.py')
    provider=load('2026-09-19-participation-provider-capture.py')
    proof=json.loads((RELEASE/'live-cli-host-proof.json').read_text());run=Path(proof['run'])
    assert sha(run/'receipt.json')==proof['receipt_sha256']
    assert proof['source_sha']==SOURCE and proof['historical_cache_mode']=='host'
    assert sha(RELEASE/'host-training.parquet')==proof['historical_cache_sha256']=='8aaa5daf5a3ebd12bdb471466dabefdc55f774988ff9437710a4e54467b072b7'
    rec=json.loads((run/'receipt.json').read_text());fr=pd.read_parquet(run/'frame.parquet')
    original=LAB/'results/live/2026-w02/20260919T030727287666Z-2dc116c'
    oldfr=pd.read_parquet(original/'frame.parquet');cands=pd.read_parquet(original/'candidates.parquet')
    assert sha(original/'candidates.parquet')=='be97536351092084c3289120114de473d9bc8b7672391aa7239bdfc5445e7695'
    orders=select.candidate_orders(oldfr,cands);index={x:i for i,x in enumerate(fr.id)}
    assert len(index)==len(fr)==428 and len(orders)==1600
    assert all(set(o)<=set(index) for o in orders)
    from nfl2.validator import validate_roster
    frame=fr.set_index('id');args=[frame[k].to_dict() for k in ('pos','team','opp','salary')]
    for o in orders:
        assert not validate_roster(o,*args,salary_floor=49000,qb_stack_min=2,bring_back_min=1,
            forbid_rb_vs_dst=True,forbid_two_rb_same_team=True)
    statusdir=ROOT/'participation-provider-bound-1243'
    cap=json.loads((statusdir/'capture.json').read_text())
    inj,dk,cutoff,_=provider.load_capture(statusdir,as_of=cap['cutoff'])
    mp=ROOT/'participation-transfer-support/participation-map.json'
    assert sha(mp)==select.MAP_SHA
    from nfl_dfs.inference.week1_participation_mixture import validate_participation_map_v1
    probs,excluded,records=select.participation(fr,inj,dk,cutoff,validate_participation_map_v1(json.loads(mp.read_text())))
    assert not excluded
    # Frozen status replay, not a claim that this is a newly collected capture.
    fr['status']=fr.dk_player_id.map(dk.set_index('dk_player_id').status)
    s=dict(fr=fr[base.SAFE].copy(),orders=orders,roster=np.asarray([[index[x] for x in o] for o in orders]),
        keep=list(range(1600)),probs=probs,records=records,original=run,cutoff=str(cutoff))
    files=[Path(__file__),REPO/'reports/2026-09-19-participation-host-transfer-protocol.md',
        RELEASE/'live-cli-host-proof.json',RELEASE/'host-training.parquet',RELEASE/'refreshed-cache.parquet',
        RELEASE/'cache-order-decomposition/host_values_host_order-components.parquet',mp,
        *(run/n for n in ('receipt.json','frame.parquet','candidates.parquet','incumbent_player_scores.npy','corrected_hsim_player_scores.npy')),
        original/'frame.parquet',original/'candidates.parquet',
        *(p for p in statusdir.iterdir() if p.is_file()),
        *(HERE/n for n in ('2026-09-19-participation-transfer.py','2026-09-19-participation-reselect-v2.py',
            '2026-09-19-participation-provider-capture.py','2026-09-19-repaired-chain-read.py',
            '2026-09-19-hsim-replay-preflight.json','2026-09-19-target-prior-cli-dst-input.json')),
        REPO/'scripts/week1_vet_book.py']
    for r in json.loads((base.INPUT/'vetting/query-captures.json').read_text()):files.append(base.opened(r))
    files.append(base.INPUT/'vetting/query-captures.json')
    return base,select,s,fr,rec,run,files


def audit_banks(fr,rec,run,dest):
    from nfl2 import data
    from nfl2.core import simulate
    from nfl2.core.draw_shape import apply_draw_shape,apply_served_position_scales
    from nfl2.core.blend import shift_draws_to_means
    from nfl2.pipeline import PRODUCTION_ENV
    from nfl2.hsim import world
    from nfl2.hsim.live_games import from_live_schedule,game_input_receipt
    compspath=RELEASE/'cache-order-decomposition/host_values_host_order-components.parquet'
    assert sha(compspath)=='e87316f4d05968aeba989637ad29014256b05b953c801a72cb55e5a5b106febc'
    comps=pd.read_parquet(compspath)
    tab=pd.read_parquet(RELEASE/'refreshed-cache.parquet');tab=tab[tab.season.eq(2026)&tab.week.eq(2)].copy()
    assert len(tab)==877
    skill=fr.position.isin(['QB','RB','WR','TE']).to_numpy();modeled=skill&fr.has_features.to_numpy()
    rows=fr[modeled].copy();keys=rows[['gsis_id','season','week']].reset_index(drop=True)
    assert len(comps)==len(rows)
    target=fr.mean_projection.to_numpy(float)
    def incumbent(seed):
        d=np.zeros((len(fr),10000))
        sim=simulate.simulate(comps,n_sims=10000,seed=seed,keep_draws=True,
            game_ids=rows.game_id.reset_index(drop=True),team_ids=rows.team.reset_index(drop=True),
            game_totals=rows.game_total.reset_index(drop=True),env=PRODUCTION_ENV)
        shaped=apply_draw_shape(sim.draws,rows.position.reset_index(drop=True),seed,keys=keys,env=PRODUCTION_ENV,tabpfn_cache_rows=tab)
        d[modeled]=apply_served_position_scales(shaped,rows.position.reset_index(drop=True),env=PRODUCTION_ENV)
        rng=np.random.default_rng(seed)
        for i in np.flatnonzero(skill&~modeled):
            mu=float(fr.dk_ppg.iloc[i]) if pd.notna(fr.dk_ppg.iloc[i]) and fr.dk_ppg.iloc[i]>0 else 2.
            d[i]=rng.gamma(2.,mu/2.,10000)
        d[skill]=shift_draws_to_means(d[skill],target[skill]);d[~skill]=target[~skill,None]
        return d.astype(np.float32)
    local={}
    for r in json.loads((HERE/'2026-09-19-hsim-replay-preflight.json').read_text())['benchmark']:
        key=r['uri'].split('/benchmark/v0/',1)[1];p=Path('/home/erich/.cache/nfl2/v0')/key
        assert sha(p)==r['sha256'];local[key]=p
    def listing(prefix):
        assert prefix in {'warehouse/'+x+'/' for x in ('player_week_training','raw_weekly_stats','raw_schedules')}
        return sorted(k for k in local if k.startswith(prefix))
    def fetching(key):assert key in local;return local[key]
    data._list,data._fetch=listing,fetching
    recorded=rec['config']['hsim_game_inputs']
    sched=pd.DataFrame(recorded['games']).rename(columns={'home':'home_team','away':'away_team','spread_home':'spread_line'})
    games=from_live_schedule(fr,sched,2026,2)
    assert game_input_receipt(games)==recorded
    with data.outcome_firewall(2026):
        assert np.array_equal(incumbent(2076),np.load(run/'incumbent_player_scores.npy',allow_pickle=False))
        wt,wc,eff=world.calibrate_weights(fr,2026,2,2326,game_inputs=games)
        def hsim(seed):return world._sample(fr,2026,2,10000,seed,wt,wc,recenter=False,team_eff=eff,game_inputs=games).astype(np.float32)
        assert np.array_equal(hsim(2326),np.load(run/'corrected_hsim_player_scores.npy',allow_pickle=False))
        print('BOTH_ACTUAL_HOST_SELECTION_BANKS_EXACT',flush=True)
        banks={'I':incumbent(14260919),'H':hsim(15260919)}
    identities={}
    for k,bank in banks.items():
        assert bank.shape==(428,10000) and bank.dtype==np.float32 and np.isfinite(bank).all()
        p=dest/(k+'_audit.npy')
        with p.open('xb') as f:np.save(f,bank,allow_pickle=False)
        identities[k]=dict(path=str(p),sha256=sha(p),seed={'I':14260919,'H':15260919}[k])
    return banks,identities


def main(mode):
    started=time.monotonic();base,selector,s,fr,rec,run,files=inputs()
    if mode=='prepare':
        write(MANIFEST,dict(files={str(p):sha(p) for p in files},source=SOURCE,
            candidates=1600,all_candidates_legal_and_scoreable=True,removed_universe_player_not_in_candidates='Michael Carter',
            source_projection=rec['config']['production_generated_at'],status_cutoff=s['cutoff']))
        print('HOST_TRANSFER_INPUT_SUPPORT_FROZEN',flush=True);return
    manifest=json.loads(MANIFEST.read_text())
    for p,h in manifest['files'].items():assert sha(p)==h,p
    dest=OUT.with_name(OUT.name+'-smoke') if mode=='smoke' else OUT;dest.mkdir(exist_ok=False)
    if mode=='smoke':
        rng=np.random.default_rng(123)
        banks={k:rng.gamma(2,5,(len(fr),400)).astype(np.float32) for k in ('I','H')}
    else:
        banks={}
        for k,n in [('I','incumbent_player_scores'),('H','corrected_hsim_player_scores')]:
            assert sha(run/(n+'.npy'))==rec['a5_sidecars'][n]['sha256']
            banks[k]=np.load(run/(n+'.npy'),allow_pickle=False)
        own=pd.read_parquet(run/'candidates.parquet');ownorders=selector.candidate_orders(fr,own)
        idx={p:i for i,p in enumerate(fr.id)};r=np.asarray([[idx[p] for p in o] for o in ownorders])
        t=selector.totals(banks,r)
        assert selector.greedy(t,97)==own[own.book_rank.notna()].sort_values('book_rank').index.tolist()
        assert np.array_equal(t[:,:10000].mean(axis=1),own.sel_mean.to_numpy())
    mixed,selection_masks=base.mixed_pair(banks,s['probs'],20260919054)
    books={name:base.select(s,b) for name,b in [('control',banks),('full',mixed)]}
    write(dest/'frozen-books.json',books)
    delivery=base.vet(s,books,dest/'delivery')
    books.update({name+'_vetted':r['indices'] for name,r in delivery.items()})
    if mode=='smoke':write(dest/'smoke.json',dict(passed=True,synthetic=True,delivery=delivery));print('HOST_TRANSFER_SYNTHETIC_PATH_PASS');return
    audit,audit_identity=audit_banks(fr,rec,run,dest)
    mix,audit_masks=base.mixed_pair(audit,s['probs'],20260919056)
    assert {r['sha256'] for r in selection_masks}.isdisjoint(r['sha256'] for r in audit_masks)
    helper=runpy.run_path(str(HERE/'2026-09-19-repaired-chain-read.py'));regions=helper['REGIONS']
    raw=subprocess.check_output(['git','-C',str(LAB),'show','e7255e9:results/contest/milly_winners.json'])
    assert hashlib.sha256(raw).hexdigest()=='4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners=np.asarray(sorted(json.loads(raw).values()),float);samples={};metrics={}
    for assumption,bb in [('all_active',audit),('participation',mix)]:
        for k,bank in bb.items():
            law=assumption+'_'+k;samples[law]={};metrics[law]={}
            for name,b in books.items():
                t=base.totals(bank,s['roster'][b]);samples[law][name]={};metrics[law][name]={}
                for region,sl in regions.items():
                    m=helper['metrics'](t[sl].max(axis=0).astype(float),winners)
                    m['mean_lineup']=t[sl].mean(axis=0,dtype=float)
                    samples[law][name][region]=m;metrics[law][name][region]={k:float(v.mean()) for k,v in m.items()}
    laws={k:[k] for k in samples}
    for assumption in ('all_active','participation'):
        key=assumption+'_mixture';parts=[assumption+'_I',assumption+'_H'];laws[key]=parts
        metrics[key]={b:{r:{m:float(np.mean([metrics[p][b][r][m] for p in parts])) for m in metrics[parts[0]][b][r]}
            for r in regions} for b in books}
    contrasts={a+'-minus-'+b:{law:{r:{m:helper['uncertainty']([samples[p][a][r][m]-samples[p][b][r][m] for p in parts])
        for m in samples[parts[0]][a][r]} for r in regions} for law,parts in laws.items()}
        for a,b in [('full','control'),('full_vetted','control_vetted')]}
    result=dict(schema='host-input-participation-transfer/v1',manifest_sha256=sha(MANIFEST),source_sha256=sha(__file__),
        actual_host_selection_banks_exact=True,actual_host_d160_control_exact=True,all1600_candidates_legal=True,
        source_projection=rec['config']['production_generated_at'],books=books,delivery=delivery,metrics=metrics,contrasts=contrasts,
        map_records=s['records'],selection_masks=selection_masks,audit_masks=audit_masks,audit_identity=audit_identity,
        shared_members=len(set(books['control'])&set(books['full'])),
        first_same=books['control_vetted'][0]==books['full_vetted'][0],
        exposures={name:{r['name']:sum(r['id'] in s['orders'][i] for i in b) for r in s['records']} for name,b in books.items()},
        seconds=time.monotonic()-started,current_scoring_outcomes_read=False,
        scope='Actual deployed laws/host cache on a borrowed fixed D1600 research pool. No full-dose corpus, morning-refreshed inputs or live efficacy claim.')
    write(dest/'result.json',result)
    print(json.dumps(dict(seconds=result['seconds'],first_same=result['first_same'],
        whole_book={k:{b:r['prefix97'] for b,r in v.items() if b.endswith('_vetted')}
            for k,v in metrics.items() if k.endswith('mixture')}),indent=2),flush=True)


if __name__=='__main__':
    assert sys.argv[1] in ('prepare','smoke','run');main(sys.argv[1])
