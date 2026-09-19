"""Frozen descriptive full-chain reader: original summation order; no selection or outcomes."""
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).parent
LOCAL=Path('/home/erich/projects/review-evidence/overnight-20260918/complete-chain-d1600')
OUT=ROOT/'2026-09-19-repaired-chain-d1600-read.json'
LAB=Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
PREFIXES=(1,10,20,30,40,80,90,97)
SPANS=((0,1),(1,24),(24,25),(25,30),(30,31),(31,33),(33,43),(43,53),(53,63),(63,79),(79,95),(95,97))
REGIONS={f'prefix{k}':slice(0,k) for k in PREFIXES}
REGIONS.update({f'block{a+1}_{b}':slice(a,b) for a,b in SPANS})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def opened(rec):
    p=Path(rec['path'])
    assert sha(p)==rec['sha256'],p
    return p


def metrics(x,winners):
    return dict(emax=x,p220=(x>=220).astype(float),
                global_proxy=(1/(1+np.exp(-(x[:,None]-winners[None,:])/8))).mean(axis=1))


def uncertainty(parts):
    """Equal-weight independent strata; pairing is within each fixed audit bank."""
    mean=float(np.mean([x.mean() for x in parts]))
    se=float(np.sqrt(sum(x.var(ddof=1)/len(x) for x in parts))/len(parts))
    return dict(delta=mean,monte_carlo_se=se,normal_95=[mean-1.96*se,mean+1.96*se])


def main():
    assert not OUT.exists()
    raw=subprocess.check_output(['git','-C',str(LAB),'show','e7255e9:results/contest/milly_winners.json'])
    assert hashlib.sha256(raw).hexdigest()=='4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners=np.asarray(sorted(json.loads(raw).values()),dtype=float);assert len(winners)==48
    arms={};books={};banks={};provenance={}
    for arm in ('control','salaryfix'):
        p=LOCAL/arm/'receipt.json';r=json.loads(p.read_text());out=Path(r['original_run'])
        assert sha(out/'receipt.json')==r['original_receipt_sha256']
        original=json.loads((out/'receipt.json').read_text())
        assert original['written']==97 and original['config']['operational_k']==97
        assert original['config']['selector']=='dual_emax' and r['hsim_calibration_reproduced']
        frame=pd.read_parquet(out/'frame.parquet');cands=pd.read_parquet(out/'candidates.parquet')
        assert len(frame)==frame.id.nunique() and not cands.players.duplicated().any()
        assert cands.index.tolist()==list(range(len(cands))) and cands.cand.tolist()==list(range(len(cands)))
        orders=json.loads(opened(r['candidate_player_orders']).read_text())
        assert len(orders)==len(cands)
        assert all(len(x)==len(set(x))==9 and ','.join(sorted(x))==s for x,s in zip(orders,cands.players))
        ids=set(frame.id.astype(str));assert all(set(x)<=ids for x in orders)
        for kind,col in [('emax','book_rank'),('wemax','book_rank_wemax')]:
            selected=cands[cands[col].notna()].sort_values(col)
            assert selected[col].tolist()==list(range(1,98))
            books[arm+'_'+kind]=dict(arm=arm,orders=[orders[i] for i in selected.index],
                                   rosters=selected.players.tolist(),candidate_indices=selected.index.tolist())
        own_banks={}
        for name,rec in r['arrays'].items():
            a=np.load(opened(rec),allow_pickle=False)
            assert a.dtype==np.float32 and a.shape==(len(frame),10000) and np.isfinite(a).all()
            own_banks[name]=a
        for law in ('I_audit','H_audit'):
            banks[arm+'_'+law]=(frame,own_banks[law])
        # Check saved order against the original CLI's candidate audit receipts.
        index={str(pid):i for i,pid in enumerate(frame.id)}
        aud=np.stack([own_banks['I_audit'][[index[x] for x in order]].sum(axis=0,dtype=np.float32) for order in orders])
        assert np.array_equal(aud.mean(axis=1),cands.aud_mean.to_numpy()),'original candidate summation differs'
        arms[arm]=dict(frame=frame,cands=cands,arrays=own_banks)
        provenance[arm]=dict(adapter_receipt_sha256=sha(p),original_receipt=original,
            artifacts={name:sha(out/name) for name in ('frame.parquet','candidates.parquet','book.csv','book_wemax.csv')},
            elapsed_seconds=r['elapsed_seconds'],arrays=r['arrays'])
    support={};samples={};result_metrics={}
    for law,(fr,bank) in banks.items():
        index={str(pid):i for i,pid in enumerate(fr.id)}
        support[law]={};samples[law]={};result_metrics[law]={}
        for name,book in books.items():
            missing=sorted(set(x for order in book['orders'] for x in order)-set(index))
            support[law][name]=dict(fully_scoreable=not missing,missing_players=missing)
            if missing:continue
            totals=np.stack([bank[[index[x] for x in order]].sum(axis=0,dtype=np.float32) for order in book['orders']])
            samples[law][name]={};result_metrics[law][name]={}
            for region,sl in REGIONS.items():
                m=metrics(totals[sl].max(axis=0).astype(float),winners)
                samples[law][name][region]=m
                result_metrics[law][name][region]={k:float(x.mean()) for k,x in m.items()}
    evals={k:[k] for k in banks}
    evals.update({arm+'_equal_mixture':[arm+'_I_audit',arm+'_H_audit'] for arm in arms})
    for law,parts in evals.items():
        if len(parts)==1:continue
        result_metrics[law]={name:{region:{m:float(np.mean([result_metrics[p][name][region][m] for p in parts]))
            for m in ('emax','p220','global_proxy')} for region in REGIONS}
            for name in books if all(name in samples[p] for p in parts)}
    contrasts={}
    comparisons=[('salaryfix_emax','control_emax'),('salaryfix_wemax','control_wemax'),
                 ('control_wemax','control_emax'),('salaryfix_wemax','salaryfix_emax')]
    for after,before in comparisons:
        contrasts[after+'-minus-'+before]={}
        for law,parts in evals.items():
            if not all(after in samples[p] and before in samples[p] for p in parts):continue
            contrasts[after+'-minus-'+before][law]={region:{m:uncertainty([
                samples[p][after][region][m]-samples[p][before][region][m] for p in parts])
                for m in ('emax','p220','global_proxy')} for region in REGIONS}
    af,bf=arms['control']['frame'].set_index('id'),arms['salaryfix']['frame'].set_index('id')
    common=af.index.intersection(bf.index).sort_values()
    frame_diffs={}
    for col in af.columns.intersection(bf.columns):
        a,b=af.loc[common,col],bf.loc[common,col]
        equal=a.eq(b)|(a.isna()&b.isna());changed=int((~equal.fillna(False)).sum())
        if changed:frame_diffs[col]=changed
    marginals={}
    for bank in ('generation','I_selection','I_audit','H_selection','H_audit'):
        a=arms['control']['arrays'][bank][af.index.get_indexer(common)]
        b=arms['salaryfix']['arrays'][bank][bf.index.get_indexer(common)]
        cols={}
        for stat,x,y in [('mean',a.mean(axis=1,dtype=float),b.mean(axis=1,dtype=float)),
                         ('p95',np.quantile(a,.95,axis=1),np.quantile(b,.95,axis=1)),
                         ('p99',np.quantile(a,.99,axis=1),np.quantile(b,.99,axis=1))]:
            d=y-x;cols[stat]=dict(mean_signed=float(d.mean()),mean_absolute=float(abs(d).mean()),
                max_absolute=float(abs(d).max()),changed_players=int((d!=0).sum()),
                largest=[dict(id=str(common[i]),name=str(bf.loc[common[i],'name']),control=float(x[i]),salaryfix=float(y[i]),delta=float(d[i]))
                    for i in np.argsort(-abs(d),kind='stable')[:15]])
        marginals[bank]=cols
    ca,cb=(set(arms[x]['cands'].players) for x in ('control','salaryfix'))
    overlap={a:{b:dict(shared_members=len(set(x['rosters'])&set(y['rosters'])),
                      same_rank_count=sum(i==j for i,j in zip(x['rosters'],y['rosters'])),
                      same_first=x['rosters'][0]==y['rosters'][0]) for b,y in books.items()} for a,x in books.items()}
    result=dict(provenance=provenance,player_universe=dict(control=len(af),salaryfix=len(bf),common=len(common),
        control_only=sorted(set(af.index)-set(bf.index)),salaryfix_only=sorted(set(bf.index)-set(af.index))),
        changed_frame_columns=frame_diffs,marginal_differences=marginals,
        candidates=dict(control=len(ca),salaryfix=len(cb),shared=len(ca&cb),control_only=len(ca-cb),salaryfix_only=len(cb-ca)),
        books=books,book_overlap=overlap,cross_law_support=support,metrics=result_metrics,contrasts=contrasts,
        global_proxy_bandwidth=8,missing_contrasts='Any unavailable comparison is explicitly explained by cross_law_support missing_players; no zero imputation.',reader_sha256=sha(__file__),scope='Conditional independent-bank audit of frozen generated books; no current outcomes, selection, or real NFL efficacy claim. Mixture MC errors use independent equal-weight strata.')
    with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False,default=str)
    print(json.dumps(dict(player_universe=result['player_universe'],candidates=result['candidates'],book_overlap=overlap,
                         whole_book={law:{name:m['prefix97'] for name,m in bs.items()} for law,bs in result_metrics.items()}),indent=2),flush=True)


if __name__=='__main__':main()
