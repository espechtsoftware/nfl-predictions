"""Fixed archived-frame game-line sensitivity; all usage features and means held fixed."""
import argparse
import base64
import hashlib
import io
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import google_crc32c
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from google.cloud import storage

R=Path('reports/reviews/evidence')
LAB=Path('/home/erich/projects/.nfl2-worktrees/audit-capture-review')
LOCAL=Path('/home/erich/projects/review-evidence/overnight-20260918/hsim-replay')
SHA='e7255e98bf87297452befb61fb508ad4b368b59f'
FEATURES=['snap_share_l4','target_share_l4','carry_share_l4','games_played_prior',
          'rz20_target_share_l4','gl3_carry_share_l4']
COLUMNS=['id','display_name','pos','team','proj','mean_projection','depth_rank','snap_share_l4',
         'is_cold_start','games_played_prior','target_share_l4','carry_share_l4',
         'rz20_target_share_l4','gl3_carry_share_l4','neutral_pass_rate_l6',
         'yards_per_target_l8','yards_per_carry_l8','game_id','game_total','spread']
SPANS=[(0,1),(1,24),(24,25),(25,30),(30,31),(31,33),(33,43),(43,53),(53,63),(63,79),(79,95),(95,97)]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    assert not args.output.exists()
    args.input_sha256='90a762654111126aefad1950217044443291251918ab70edb925ff341d226635'
    receipt={'table':'archived frame.parquet; authenticated generation1789768711580236'}
    replay_receipt=json.loads((R/'2026-09-19-hsim-replay-preflight.json').read_text())
    assert replay_receipt['exact_equal']
    source_hashes={}
    for name,expected in replay_receipt['source_hashes'].items():
        data=(LAB/name).read_bytes()
        assert hashlib.sha256(data).hexdigest()==expected
        source_hashes[name]=expected
    files={}
    for rec in replay_receipt['benchmark']:
        rel=rec['uri'].split('/benchmark/v0/',1)[1]
        path=Path('/home/erich/.cache/nfl2/v0')/rel
        data=path.read_bytes()
        assert hashlib.sha256(data).hexdigest()==rec['sha256'] and len(data)==int(rec['bytes'])
        files[rel]=path
    sys.path.insert(0,str(LAB/'src'))
    import nfl2.data as data
    def allowed_list(prefix):
        assert prefix in {'warehouse/'+x+'/' for x in ('player_week_training','raw_weekly_stats','raw_schedules')}
        return sorted(k for k in files if k.startswith(prefix))
    def allowed_fetch(path):
        assert path in files
        return files[path]
    data._list=allowed_list;data._fetch=allowed_fetch
    from nfl2.hsim.world import simulate_hsim,POS_FALLBACK_T,POS_FALLBACK_C
    from nfl2.hsim.shares import active_mask,_prior_weights,TARGET_POS,CARRY_POS
    archive=json.loads((R/'2026-09-18-week2-archive-preflight.json').read_text())
    bucket=storage.Client(project='nfl-2-506823').bucket('nfl-2-506823-lab')
    prefix=archive['prefix'].split(bucket.name+'/',1)[1];verified={}
    def get(name):
        rec=next(x for x in archive['objects'] if x['name']==name)
        path=LOCAL/name
        if path.exists(): raw=path.read_bytes()
        else:
            raw=bucket.blob(prefix+name).download_as_bytes(if_generation_match=int(rec['generation']))
            assert hashlib.sha256(raw).hexdigest()==rec['sha256']
            with path.open('xb') as f:f.write(raw)
        assert hashlib.sha256(raw).hexdigest()==rec['sha256']
        verified[name]=dict(sha256=rec['sha256'],generation=rec['generation'])
        return raw
    fr=pq.read_table(io.BytesIO(get('frame.parquet')),columns=COLUMNS).to_pandas()
    assert len(fr)==fr.id.nunique()==435
    changed=fr.copy(deep=True);match=np.ones(len(fr),dtype=bool)
    input_deltas={col:0 for col in FEATURES}
    import nfl2.hsim.world as world
    original_games=world._games
    game_comparison=[]
    assert fr.groupby('team')[['game_id','game_total','spread']].nunique().max().max()==1
    team_inputs=fr.drop_duplicates('team').set_index('team')
    def frame_games(frame,season,week):
        assert season==2026 and week==2
        games=original_games(frame,season,week)
        assert len(games)==13 and len(set(games.home)|set(games.away))==26
        out=games.copy(deep=True)
        for i,row in games.iterrows():
            h=team_inputs.loc[row.home];a=team_inputs.loc[row.away]
            assert h.game_id==a.game_id==f'2026_02_{row.away}_{row.home}'
            assert np.isfinite([h.game_total,a.game_total,h.spread,a.spread]).all()
            assert h.game_total==a.game_total and abs(h.spread+a.spread)<1e-8
            out.loc[i,'total_line']=float(h.game_total)
            out.loc[i,'spread_home']=float(h.spread)
        keep=[c for c in games.columns if c not in ['total_line','spread_home']]
        assert games[keep].equals(out[keep])
        if not game_comparison:
            for old,new in zip(games.to_dict('records'),out.to_dict('records')):
                game_comparison.append({'old':old,'new':new})
        return out
    c=pq.read_table(io.BytesIO(get('candidates.parquet')),columns=['players']).to_pydict()
    idx={str(x):i for i,x in enumerate(fr.id)}
    rosters=np.asarray([[idx[v] for v in x.split(',')] for x in c['players']],dtype=int)
    assert rosters.shape==(6400,9) and all(len(set(x))==9 for x in rosters)
    assert len(set(tuple(sorted(x)) for x in rosters))==6400
    incumbent=np.load(io.BytesIO(get('incumbent_player_scores.npy')),allow_pickle=False)
    old_h=np.load(io.BytesIO(get('corrected_hsim_player_scores.npy')),allow_pickle=False)
    for p in (incumbent,old_h):assert p.shape==(435,10000) and p.dtype==np.float32 and np.isfinite(p).all()
    started=time.monotonic()
    calibration={}
    with data.outcome_firewall(2026):
        old_weights=world.calibrate_weights(fr,2026,2,seed=2326)
        def frozen_sample(frame,weights,seed):
            wt,wc,eff=weights
            return world._sample(frame,2026,2,10000,seed,wt,wc,recenter=False,team_eff=eff).astype(np.float32)
        check=frozen_sample(fr,old_weights,2326)
        assert np.array_equal(check,old_h),'fixed control calibration does not reproduce archive'
        del check
        old_a=frozen_sample(fr,old_weights,2426)
        world._games=frame_games
        try:
            new_weights=world.calibrate_weights(changed,2026,2,seed=2326)
            new_h=frozen_sample(changed,new_weights,2326)
            prior=np.load(LOCAL/'schedule_only_hsim_selection.npy',allow_pickle=False)
            assert np.array_equal(new_h,prior),'fixed treatment calibration does not reproduce prior run'
            del prior
            new_a=frozen_sample(changed,new_weights,2426)
        finally:
            world._games=original_games
        for name,weights in [('control',old_weights),('treatment',new_weights)]:
            calibration[name]=dict(target_weights=weights[0].tolist(),carry_weights=weights[1].tolist(),team_eff=weights[2])
    outputs={}
    for name,p in [('schedule_only_hsim_selection',new_h),('schedule_control_hsim_audit',old_a),('schedule_only_hsim_audit',new_a)]:
        assert p.shape==(435,10000) and np.isfinite(p).all()
        path=LOCAL/('fixedcal_'+name+'.npy')
        with path.open('xb') as f:np.save(f,p,allow_pickle=False)
        outputs[name]=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),path=str(path))
    T=np.empty((6400,20000),dtype=np.float32)
    def populate(p,start):
        for i,r in enumerate(rosters):T[i,start:start+10000]=p[r].sum(axis=0,dtype=np.float32)
    populate(incumbent,0);populate(old_h,10000)
    def select():
        book=[];cur=np.full(20000,-np.inf)
        for _ in range(97):
            assert time.monotonic()-started<400,'compute cap exceeded'
            values=np.empty(6400)
            for start in range(0,6400,64):values[start:start+64]=np.maximum(T[start:start+64].astype(np.float64),cur).mean(axis=1)
            values[book]=-np.inf;pick=int(np.argmax(values));book.append(pick);cur=np.maximum(cur,T[pick])
        assert len(set(book))==97
        return book
    original=select()
    previous=json.loads((R/'2026-09-18-week2-current-selector-diagnostic.json').read_text())
    assert previous['baseline_reproduced'] and original==previous['selected'],'baseline K97 replay mismatch'
    populate(new_h,10000);new_book=select();del T
    raw=subprocess.check_output(['git','-C',str(LAB),'show',SHA+':results/contest/milly_winners.json'])
    assert hashlib.sha256(raw).hexdigest()=='4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners=np.asarray(sorted(json.loads(raw).values()),dtype=np.float64);assert len(winners)==48
    regions={f'prefix{k}':list(range(k)) for k in (1,10,20,30,40,80,90,97)}
    regions.update({f'block{a+1}_{z}':list(range(a,z)) for a,z in SPANS})
    def evaluate(p,book):
        totals=np.stack([p[rosters[c]].sum(axis=0,dtype=np.float32) for c in book])
        result={}
        for key,indices in regions.items():
            maximum=totals[indices].max(axis=0).astype(np.float64)
            result[key]=dict(emax=float(maximum.mean()),p220=float((maximum>=220).mean()),
                global_proxy=float((1/(1+np.exp(-(maximum[:,None]-winners)/8))).mean()))
        return result
    measures={name:{'original_book':evaluate(p,original),'schedule_only_book':evaluate(p,new_book)}
        for name,p in [('incumbent_selection',incumbent),('original_hsim_selection',old_h),
            ('schedule_only_hsim_selection',new_h),('original_hsim_audit',old_a),('schedule_only_hsim_audit',new_a)]}
    paired_audit={}
    for label,p in [('original_hsim_audit',old_a),('treatment_hsim_audit',new_a)]:
        before=np.stack([p[rosters[c]].sum(axis=0,dtype=np.float32) for c in original]).max(axis=0).astype(np.float64)
        after=np.stack([p[rosters[c]].sum(axis=0,dtype=np.float32) for c in new_book]).max(axis=0).astype(np.float64)
        def util(x):return (1/(1+np.exp(-(x[:,None]-winners)/8))).mean(axis=1)
        paired_audit[label]={}
        for metric,delta in [('emax',after-before),('p220',(after>=220).astype(float)-(before>=220).astype(float)),('global_proxy',util(after)-util(before))]:
            mean=float(delta.mean());se=float(delta.std(ddof=1)/np.sqrt(len(delta)))
            paired_audit[label][metric]=dict(delta=mean,monte_carlo_se=se,normal_95=[mean-1.96*se,mean+1.96*se])
    players=fr[['id','display_name','pos','team','mean_projection']].copy()
    for label,f,p,book in [('old',fr,old_h,original),('new',changed,new_h,new_book)]:
        players[label+'_active']=active_mask(f)
        players[label+'_target_positive']=_prior_weights(f,'target_share_l4',TARGET_POS,POS_FALLBACK_T)>0
        players[label+'_carry_positive']=_prior_weights(f,'carry_share_l4',CARRY_POS,POS_FALLBACK_C)>0
        players[label+'_mean']=p.mean(axis=1,dtype=np.float64)
        players[label+'_zero_all_worlds']=(p==0).all(axis=1)
        players[label+'_book_exposure']=np.bincount(rosters[book].ravel(),minlength=435)
    players['new_minus_old_mean']=players.new_mean-players.old_mean
    records=json.loads(players.to_json(orient='records',double_precision=12))
    group=[]
    for pos in sorted(set(fr.pos)):
        x=players[players.pos==pos]
        group.append(dict(position=pos,n=len(x),mean_delta=float(x.new_minus_old_mean.mean()),
            mean_absolute_delta=float(x.new_minus_old_mean.abs().mean()),old_zero=int(x.old_zero_all_worlds.sum()),
            new_zero=int(x.new_zero_all_worlds.sum()),became_active=int((~x.old_active&x.new_active).sum()),
            became_inactive=int((x.old_active&~x.new_active).sum())))
    result=dict(input_receipt_sha256=args.input_sha256,input_table=receipt['table'],input_deltas=input_deltas,
        matched_frame_rows=int(match.sum()),unmatched_ids=fr.loc[~match,'id'].tolist(),groups=group,all_players=records,
        original_book=original,schedule_only_book=new_book,membership_overlap=len(set(original)&set(new_book)),
        same_rank_count=sum(a==b for a,b in zip(original,new_book)),first_roster_changed=original[0]!=new_book[0],
        original_first_roster=[str(fr.id.iloc[i]) for i in rosters[original[0]]],
        schedule_only_first_roster=[str(fr.id.iloc[i]) for i in rosters[new_book[0]]],
        paired_audit=paired_audit,calibration_seed=2326,audit_final_seed=2426,calibration=calibration,metrics=measures,verified_archive=verified,output_arrays=outputs,source_hashes=source_hashes,
        elapsed_seconds=time.monotonic()-started,game_inputs=json.loads(pd.DataFrame(game_comparison).to_json(orient='records')),scope='Fixed archived frame/pool/means; game totals/spreads only; audit is hsim half only. No real-world efficacy or adoption claim.',
        provenance=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            source_status=subprocess.check_output(['git','status','--porcelain'],text=True),
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__))
    with args.output.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({k:result[k] for k in ['input_deltas','matched_frame_rows','groups','membership_overlap','same_rank_count','first_roster_changed','elapsed_seconds']},indent=2),flush=True)
    print(json.dumps({name:{b:metrics['prefix97'] for b,metrics in books.items()} for name,books in measures.items()},indent=2),flush=True)

if __name__=='__main__':main()
