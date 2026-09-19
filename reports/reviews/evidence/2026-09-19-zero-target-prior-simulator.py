"""Fixed-pool calibrated trace of two historically nominated target-prior rules."""
import hashlib
import json
import runpy
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd

R=Path(__file__).parent
OUT=R/'2026-09-19-zero-target-prior-simulator.json'
LOCAL=Path('/home/erich/projects/review-evidence/overnight-20260918/zero-target-prior-simulator')
CHAIN=Path('/home/erich/projects/review-evidence/overnight-20260918/complete-chain-cli')
LAB=Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert not OUT.exists() and not LOCAL.exists();LOCAL.mkdir()
    started=time.monotonic()
    prior_result=json.loads((R/'2026-09-19-zero-target-prior-read.json').read_text())
    assert all(x['nominated_for_simulator_trace'] for x in prior_result['nominations'].values())
    model=prior_result['prospective_model'];assert model['max_training_season']==2025 and model['target_season']==2026
    chain=json.loads((R/'2026-09-19-repaired-chain-read.json').read_text())
    r=json.loads((CHAIN/'salaryfix'/'receipt.json').read_text());p=Path(r['original_run'])
    for name,digest in chain['provenance']['salaryfix']['artifacts'].items():assert sha(p/name)==digest
    assert sha(p/'receipt.json')==r['original_receipt_sha256']
    fr=pd.read_parquet(p/'frame.parquet');cands=pd.read_parquet(p/'candidates.parquet')
    orderrec=r['candidate_player_orders'];assert sha(orderrec['path'])==orderrec['sha256']
    orders=json.loads(Path(orderrec['path']).read_text());index={str(x):i for i,x in enumerate(fr.id)}
    roster=np.asarray([[index[x] for x in order] for order in orders]);assert roster.shape==(160,9)
    assert all(','.join(sorted(x))==s for x,s in zip(orders,cands.players))
    original=json.loads((p/'receipt.json').read_text())
    rec=next(x for x in r['query_snapshots'] if set(x['tables'])=={'nfl-predictions-503414.nfl_raw.schedules'})
    schedpath=CHAIN/'queries'/(rec['key']+'.parquet');assert sha(schedpath)==rec['sha256']
    schedule=pd.read_parquet(schedpath)
    banks={}
    for key in ('I_selection','I_audit','H_selection','H_audit'):
        ar=r['arrays'][key];assert sha(ar['path'])==ar['sha256'];banks[key]=np.load(ar['path'],allow_pickle=False)
        assert banks[key].shape==(len(fr),10000) and banks[key].dtype==np.float32
    sys.path.insert(0,str(LAB/'src'))
    replay=json.loads((R/'2026-09-19-hsim-replay-preflight.json').read_text());files={}
    for rec in replay['benchmark']:
        rel=rec['uri'].split('/benchmark/v0/',1)[1];f=Path('/home/erich/.cache/nfl2/v0')/rel
        assert sha(f)==rec['sha256'];files[rel]=f
    for name in list(replay['source_hashes'])+['src/nfl2/hsim/live_games.py','src/nfl2/selectors.py']:
        assert (LAB/name).read_bytes()==subprocess.check_output(['git','-C',str(LAB),'show','2dc116c:'+name])
    import nfl2.data as data
    def listing(prefix):
        assert prefix in {'warehouse/'+x+'/' for x in ('player_week_training','raw_weekly_stats','raw_schedules')}
        return sorted(x for x in files if x.startswith(prefix))
    def fetching(key):assert key in files;return files[key]
    data._list=listing;data._fetch=fetching
    from nfl2.hsim import shares,world
    from nfl2.hsim.live_games import from_live_schedule,game_input_receipt
    from nfl2.selectors import select_expected_max
    from nfl2.live_a5 import select_same_pool_wemax
    games=from_live_schedule(fr,schedule,2026,2)
    assert game_input_receipt(games)==original['config']['hsim_game_inputs']
    original_prior=shares._prior_weights
    eligible=(fr.pos.isin(world.POS_FALLBACK_T)&fr.target_share_l4.eq(0)&fr.snap_share_l4.ge(.2)&
              fr.games_played_prior.ge(1)&shares.active_mask(fr)).to_numpy(bool,na_value=False)
    gp=fr.games_played_prior.to_numpy(float);snaps=fr.snap_share_l4.to_numpy(float)
    fixed=np.asarray([world.POS_FALLBACK_T.get(x,0) for x in fr.pos])/(1+np.minimum(gp,4))
    learned=[]
    for pos,s,g in zip(fr.pos,snaps,gp):
        sb='20-49' if s<.5 else '50-79' if s<.8 else '80+'
        gb='1' if g<2 else '2-4' if g<5 else '5+'
        learned.append(model['cells'].get('|'.join((pos,sb,gb)),{}).get('value',model['positions'].get(pos,world.POS_FALLBACK_T.get(pos,0))))
    learned=np.asarray(learned)
    values={'baseline':None,'one_prior_game':fixed,'past_empirical':learned}
    selection={};audits={'I':banks['I_audit']};calibration={};array_ids={};initial={}
    with data.outcome_firewall(2026):
        for label,prior in values.items():
            assert time.monotonic()-started<580
            def adapted(frame,col,positions,fallback):
                assert frame is fr
                w=original_prior(frame,col,positions,fallback)
                if prior is not None and col=='target_share_l4':
                    before=w.copy();w[eligible]=prior[eligible]
                    assert np.array_equal(before[~eligible],w[~eligible])
                return w
            shares._prior_weights=adapted
            try:
                initial[label]=dict(targets=adapted(fr,'target_share_l4',world.TARGET_POS,world.POS_FALLBACK_T).tolist(),
                                    carries=adapted(fr,'carry_share_l4',world.CARRY_POS,world.POS_FALLBACK_C).tolist())
                wt,wc,eff=world.calibrate_weights(fr,2026,2,2326,game_inputs=games)
            finally:shares._prior_weights=original_prior
            calibration[label]=dict(target_weights=wt.tolist(),carry_weights=wc.tolist(),team_eff=eff)
            for kind,seed in [('selection',2326),('audit',2426)]:
                a=world._sample(fr,2026,2,10000,seed,wt,wc,recenter=False,team_eff=eff,game_inputs=games).astype(np.float32)
                assert a.shape==(len(fr),10000) and np.isfinite(a).all()
                if label=='baseline':assert np.array_equal(a,banks['H_'+kind]),'baseline hsim replay differs'
                dest=LOCAL/(label+'_'+kind+'.npy');np.save(dest,a,allow_pickle=False)
                array_ids[label+'_'+kind]=dict(path=str(dest),sha256=sha(dest))
                (selection if kind=='selection' else audits)[label]=a
            print('PRIOR_SIMULATED',label,flush=True)
    assert all(x['carries']==initial['baseline']['carries'] for x in initial.values())
    def totals(bank):return np.stack([bank[row].sum(axis=0,dtype=np.float32) for row in roster])
    I=totals(banks['I_selection']);books={}
    for label,bank in selection.items():
        T=np.concatenate([I,totals(bank)],axis=1)
        for kind,fn in [('emax',select_expected_max),('wemax',select_same_pool_wemax)]:
            b=list(map(int,fn(T,97)));assert len(b)==len(set(b))==97
            if label=='baseline':assert b==chain['books']['salaryfix_'+kind]['candidate_indices'],'baseline selected book differs'
            books[label+'_'+kind]=b
    del selection,I,T
    helper=runpy.run_path(str(R/'2026-09-19-repaired-chain-read.py'))
    raw=subprocess.check_output(['git','-C',str(LAB),'show','e7255e9:results/contest/milly_winners.json'])
    assert hashlib.sha256(raw).hexdigest()=='4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners=np.asarray(sorted(json.loads(raw).values()),dtype=float)
    metric=helper['metrics'];uncertainty=helper['uncertainty'];regions=helper['REGIONS']
    samples={};metrics={}
    for law,bank in audits.items():
        t=totals(bank);samples[law]={};metrics[law]={}
        for label,b in books.items():
            samples[law][label]={};metrics[law][label]={}
            for region,sl in regions.items():
                m=metric(t[np.asarray(b)[sl]].max(axis=0).astype(float),winners)
                samples[law][label][region]=m
                metrics[law][label][region]={k:float(v.mean()) for k,v in m.items()}
    laws={k:[k] for k in audits};laws.update({k+'_equal_mixture':['I',k] for k in values})
    for law,parts in laws.items():
        if len(parts)==1:continue
        metrics[law]={b:{region:{m:float(np.mean([metrics[x][b][region][m] for x in parts])) for m in ('emax','p220','global_proxy')}
                             for region in regions} for b in books}
    contrasts={}
    pairs=[(rule+'_'+kind,'baseline_'+kind) for rule in ('one_prior_game','past_empirical') for kind in ('emax','wemax')]
    pairs += [(rule+'_wemax',rule+'_emax') for rule in values]
    for after,before in pairs:
        contrasts[after+'-minus-'+before]={law:{region:{m:uncertainty([samples[p][after][region][m]-samples[p][before][region][m] for p in parts])
            for m in ('emax','p220','global_proxy')} for region in regions} for law,parts in laws.items()}
    player_rows=[];served=fr.mean_projection.to_numpy(float)
    for i,row in fr.iterrows():
        x=dict(id=str(row.id),name=row['name'],pos=row.pos,eligible=bool(eligible[i]),served_mean=float(served[i]))
        for law,bank in audits.items():
            x[law]=dict(mean=float(bank[i].mean(dtype=float)),p95=float(np.quantile(bank[i],.95)),
                        all_zero=bool((bank[i]==0).all()))
        player_rows.append(x)
    calibration_fit={law:{label:dict(players=int(mask.sum()),mean_absolute_gap=float(np.abs(bank.mean(axis=1,dtype=float)[mask]-served[mask]).mean()),
                                    zero_score_players=int((bank[mask]==0).all(axis=1).sum()))
                         for label,mask in [('all',np.ones(len(fr),bool)),('prior_eligible',eligible),('others',~eligible)]}
                     for law,bank in audits.items()}
    overlap={a:{b:dict(shared_members=len(set(x)&set(y)),same_ranks=sum(i==j for i,j in zip(x,y)),same_first=x[0]==y[0])
                for b,y in books.items()} for a,x in books.items()}
    result=dict(source_sha256=sha(__file__),protocol_sha256=sha(R.parent.parent/'2026-09-19-zero-target-prior-simulator-protocol.md'),
        input_chain_result_sha256=sha(R/'2026-09-19-repaired-chain-read.json'),prior_result_sha256=sha(R/'2026-09-19-zero-target-prior-read.json'),
        baseline_exact_replay=True,baseline_books_exact=True,eligible_players=int(eligible.sum()),initial_weights=initial,
        calibration=calibration,array_identities=array_ids,books=books,book_overlap=overlap,
        first_rosters={k:[str(fr.id.iloc[i]) for i in roster[b[0]]] for k,b in books.items()},
        metrics=metrics,contrasts=contrasts,players=player_rows,calibration_fit=calibration_fit,
        elapsed_seconds=time.monotonic()-started,
        scope='Fixed repaired pool, conditional model audit; no current outcomes, generation changes or live adoption. Historical target-share evidence is separate.')
    with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(eligible_players=result['eligible_players'],calibration_fit=calibration_fit,book_overlap=overlap,
        whole_book={law:{b:m['prefix97'] for b,m in bs.items()} for law,bs in metrics.items()},elapsed_seconds=result['elapsed_seconds']),indent=2))


if __name__=='__main__':main()
