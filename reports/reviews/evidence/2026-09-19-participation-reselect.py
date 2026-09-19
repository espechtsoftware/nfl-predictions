"""Outcome-free research reselection from ordinary live_week artifacts.

Produces a separate candidate book only. No warehouse, timer, source-run,
entered-book pointer or upload is changed. No probability/model fitting.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd

REPO=Path(__file__).resolve().parents[3]
LAB=Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
SOURCE='2dc116ce95647a776ba9c36cf194f44d022d03a4'
MAP_SHA='fc5a22bb9c3cab895e8260ef00caca4c389888f4110ceff0b21a59b97b005cbb'
SEED=20260919054
FRAME_COLUMNS=['id','name','gsis_id','pos','position','team','opp','salary','status',
               'display_name','dk_player_id','dk_draftable_id','draft_group_id']


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read_verified(row):
    p=Path(row['path']);assert sha(p)==row['sha256'],p;return pd.read_parquet(p)
def status(x):
    x='' if pd.isna(x) else str(x).strip().upper()
    mapping={'':None,'NONE':None,'Q':'Questionable','QUESTIONABLE':'Questionable',
        'D':'Doubtful','DOUBTFUL':'Doubtful','O':'Out','OUT':'Out','IR':'Out',
        'PUP':'Out','NFI':'Out','SUS':'Out','SUSPENDED':'Out'}
    assert x in mapping,('unknown status',x);return mapping[x]
def practice(x):
    if pd.isna(x):return None
    mapping={'Did Not Participate In Practice':0,'Limited Participation in Practice':1,
             'Full Participation in Practice':2}
    assert x in mapping,('unknown practice',x);return mapping[x]


def greedy(t,entries,chunk=128):
    """Same float64 row reductions/tie order, bounded temporary allocation."""
    assert t.ndim==2 and entries<=len(t) and np.isfinite(t).all()
    current=np.full(t.shape[1],-np.inf,dtype=np.float64)
    taken=np.zeros(len(t),bool);book=[]
    for _ in range(entries):
        base=0. if not book else current.mean()
        gains=np.empty(len(t),np.float64)
        for start in range(0,len(t),chunk):
            gains[start:start+chunk]=np.maximum(t[start:start+chunk].astype(np.float64),current).mean(axis=1)-base
        gains[taken]=-np.inf;i=int(np.argmax(gains));assert np.isfinite(gains[i])
        book.append(i);taken[i]=True;current=np.maximum(current,t[i])
    return book


def candidate_orders(fr,cands):
    """Recover the stored original names order, never sorted-ID summation."""
    names=fr.set_index('id')['name'].astype(str).to_dict();orders=[]
    for row in cands.itertuples():
        ids=row.players.split(',');given=row.names.split('|')
        assert len(ids)==len(set(ids))==len(given)==9
        by_name={names[i]:i for i in ids}
        assert len(by_name)==9 and set(given)==set(by_name),'ambiguous stored candidate names'
        orders.append([by_name[n] for n in given])
    return orders


def participation(fr,inj,dk,cutoff,mp,confirmed=None):
    assert inj.gsis_id.is_unique and dk.dk_player_id.is_unique
    assert set(fr.dk_player_id)<=set(dk.dk_player_id),'missing fresh DK identities'
    assert inj.pulled_at.nunique()==dk.pulled_at.nunique()==1
    for df,age in ((inj,86400),(dk,3600)):
        seconds=(cutoff-df.pulled_at.iloc[0]).total_seconds();assert 0<=seconds<=age,'stale source'
    assert set(dk.draft_group_id.astype(str))==set(fr.draft_group_id.astype(str))
    assert cutoff<dk.game_start.min(),'a game has locked'
    official={}
    if confirmed is not None:
        assert confirmed['schema']=='official-participation-confirmation/v1'
        at=pd.Timestamp(confirmed['observed_at']);assert at.tzinfo and 0<=(cutoff-at).total_seconds()<=3600
        assert confirmed['source_uri'].startswith(('https://','gs://'))
        assert re.fullmatch(r'[0-9a-f]{64}',confirmed['source_sha256'])
        assert confirmed['season']==2026 and confirmed['week']==2
        assert str(confirmed['draft_group_id'])==str(fr.draft_group_id.iloc[0])
        assert len({x['player_id'] for x in confirmed['players']})==len(confirmed['players'])
        assert {x['player_id'] for x in confirmed['players']}<=set(fr.id)
        for x in confirmed['players']:
            assert x['state'] in ('active','inactive');official[x['player_id']]=x['state']
    inj=inj.set_index('gsis_id');dk=dk.set_index('dk_player_id')
    probs=np.ones(len(fr));excluded=set();records=[]
    rank={None:0,'Questionable':1,'Doubtful':2,'Out':3}
    for n,row in enumerate(fr.itertuples()):
        raw=inj.loc[row.gsis_id] if row.gsis_id in inj.index else None
        d=dk.loc[row.dk_player_id];a=status(d.status);b=status(raw.report_status) if raw is not None else None
        st=max((a,b),key=lambda x:rank[x]);pr=practice(raw.practice_status) if raw is not None else None
        state=official.get(row.id)
        if state=='active':
            assert st!='Out','official active contradicts Out/IR; reconcile instead of overriding'
            probability=1.
        elif state=='inactive' or st=='Out':probability=0.;excluded.add(row.id)
        elif st is None:probability=1.
        else:
            # DK Q/D may survive an official active announcement. Do not keep
            # the historical nonparticipation prior once those reports are due.
            assert d.game_start-cutoff>pd.Timedelta(minutes=90),('official active/inactive confirmation required',row.id)
            key=st+'|'+('none' if pr is None else str(pr));probability=float(mp['p_active'][key])
        probs[n]=probability
        if st is not None or state is not None:
            records.append(dict(id=row.id,name=row.display_name,dk_status=d.status,
                report_status=b,practice_raw=None if raw is None else raw.practice_status,
                normalized_status=st,practice_level=pr,p_active=probability,official_state=state,
                source_disagreement=a!=b))
    return probs,excluded,records


def totals(banks,roster):
    return np.concatenate([np.stack([bank[row].sum(axis=0,dtype=np.float32) for row in roster]) for bank in banks.values()],axis=1)


def execute(run,status_dir,map_path,out,confirmed=None,as_of=None):
    assert not out.exists(),'never overwrite a research book'
    rec=json.loads((run/'receipt.json').read_text());cfg=rec['config'];ident=rec['identity']
    assert ident['sha']==SOURCE and not ident['dirty']
    assert rec['season']==2026 and rec['week']==2 and str(rec['draft_group'])=='153428'
    assert cfg['selector']=='dual_emax' and cfg['seed']==2026 and cfg['sims']==10000
    entries=rec['written'];assert entries==cfg['operational_k']==97
    assert sha(map_path)==MAP_SHA
    from nfl_dfs.inference.week1_participation_mixture import validate_participation_map_v1
    mp=validate_participation_map_v1(json.loads(map_path.read_text()))
    capture=json.loads((status_dir/'capture.json').read_text());cutoff=pd.Timestamp(capture['cutoff'])
    now=pd.Timestamp(as_of or datetime.now(timezone.utc));assert 0<=(now-cutoff).total_seconds()<=3600,'capture is stale/future'
    assert pd.Timestamp(rec['built_utc'])<=cutoff<pd.Timestamp(rec['lock_utc'])
    raw={x['name']:x for x in capture['captures']};inj=read_verified(raw['injury_snapshots'])
    dk=read_verified(json.loads((status_dir/'dk-capture-repair.json').read_text()))
    fr=pd.read_parquet(run/'frame.parquet',columns=FRAME_COLUMNS)
    cands=pd.read_parquet(run/'candidates.parquet',columns=['cand','players','names','book_rank','sel_mean'])
    assert fr.id.is_unique and fr.dk_player_id.is_unique and cands.cand.tolist()==list(range(len(cands)))
    assert cands.players.is_unique and len(cands)==rec['candidates']
    orders=candidate_orders(fr,cands);index={x:i for i,x in enumerate(fr.id)}
    roster=np.asarray([[index[x] for x in o] for o in orders],int)
    banks={}
    for name,key in [('I','incumbent_player_scores'),('H','corrected_hsim_player_scores')]:
        p=run/(key+'.npy');identity=rec['a5_sidecars'][key]
        assert sha(p)==identity['sha256'] and p.stat().st_size==identity['bytes']
        bank=np.load(p,allow_pickle=False)
        assert list(bank.shape)==identity['shape']==[len(fr),10000] and str(bank.dtype)==identity['dtype']=='float32'
        assert np.isfinite(bank).all();banks[name]=bank
    t=totals(banks,roster)
    baseline=greedy(t,entries)
    expected=cands[cands.book_rank.notna()].sort_values('book_rank').index.tolist()
    assert baseline==expected,'ordinary live control failed exact reconstruction'
    # live_week's sel_mean is the incumbent component, not the concatenated law.
    assert np.array_equal(t[:,:10000].mean(axis=1),cands.sel_mean.to_numpy())
    p,excluded,records=participation(fr,inj,dk,cutoff,mp,confirmed)
    keep=[i for i,o in enumerate(orders) if not(set(o)&excluded)];assert len(keep)>=entries
    control=[keep[i] for i in greedy(t[keep],entries)];del t
    rng=np.random.default_rng(SEED)
    for i in np.flatnonzero((p<1)&(p>0)):
        for bank in banks.values():bank[i,rng.random(bank.shape[1])>=p[i]]=0.
    t=totals(banks,roster[keep]);book=[keep[i] for i in greedy(t,entries)];del t
    from nfl2.validator import validate_roster
    f=fr.set_index('id');args=[f[k].to_dict() for k in ('pos','team','opp','salary')]
    for b in (control,book):
        assert len(b)==len(set(b))==entries
        for i in b:
            assert not validate_roster(orders[i],*args)
            assert not validate_roster(orders[i],*args,salary_floor=49000,qb_stack_min=2,
                bring_back_min=1,forbid_rb_vs_dst=True,forbid_two_rb_same_team=True)
    out.mkdir(parents=True)
    from nfl2.live import dk_csv
    fr['status']=fr.dk_player_id.map(dk.set_index('dk_player_id').status)
    fr.to_parquet(out/'frame.parquet',index=False)
    for name,b in [('book.csv',book),('control.csv',control)]:
        dk_csv([SimpleNamespace(players=[{'id':x} for x in orders[i]]) for i in b],fr,out/name)
    source_files=['receipt.json','frame.parquet','candidates.parquet','book.csv','incumbent_player_scores.npy','corrected_hsim_player_scores.npy']
    result=dict(schema='participation-candidate-reselection/v1',disposition='RESEARCH_ONLY_NOT_ADOPTED',
        season=2026,week=2,draft_group=153428,source_run=str(run),source_sha=SOURCE,
        producer_sha256=sha(__file__),source_files={n:sha(run/n) for n in source_files},
        status_capture_sha256=sha(status_dir/'capture.json'),status_dk_sha256=sha(status_dir/'dk-capture-repair.json'),
        cutoff=str(cutoff),checked_at=str(now),replay_as_of_override=as_of is not None,
        source_candidate_count=len(cands),eligible_candidates=len(keep),entries=entries,
        source_control_exact=True,source_summation_exact=True,selection_seed=SEED,map_sha256=MAP_SHA,
        excluded_players=sorted(excluded),probabilities=records,control_indices=control,pmix_indices=book,
        official_confirmation=confirmed,all_books_legal=True,football_outcomes_read=False)
    (out/'receipt.json').write_text(json.dumps(result,indent=2,allow_nan=False,default=str))
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True)
    ap.add_argument('--status-dir',type=Path,required=True);ap.add_argument('--map',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--confirmed',type=Path)
    a=ap.parse_args();sys.path[:0]=[str(REPO/'src'),str(LAB/'src')]
    result=execute(a.run,a.status_dir,a.map,a.output,json.loads(a.confirmed.read_text()) if a.confirmed else None)
    print(json.dumps(result,indent=2,default=str),flush=True)
