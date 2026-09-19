"""Frozen historical proper-score reader; no lineup outcomes or selections."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
import numpy as np
import pandas as pd

SKILL=('QB','RB','WR','TE')
YEARS=(2019,2021,2022,2023,2024)
BANKS=(19260901,19260902)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def crps(x,y):
    x=np.sort(np.asarray(x,dtype=np.float64),axis=1)
    n=x.shape[1]
    assert n>1
    return np.abs(x-y[:,None]).mean(axis=1)-(x*(2*np.arange(1,n+1)-n-1)).sum(axis=1)/(n*n)

def terms(i,h,y):
    a,b=crps(i,y),crps(h,y)
    m=crps(np.concatenate([i,h],axis=1),y)
    d=2*(a+b-2*m)
    assert np.min(d)>=-1e-8
    return a,b,np.maximum(d,0)

def mix(a,b,d,w): return w*a+(1-w)*b-w*(1-w)*d
def weight(a,b,d): return float(np.clip((d+b-a)/(2*d),0,1)) if d>1e-12 else .5

def balanced(frame,columns):
    # Equal positions within slate, paired banks within slate, slates within season, seasons.
    f=frame[frame.pos.isin(SKILL)]
    return f.groupby(['season','week','bank','pos'])[columns].mean().groupby(
        ['season','week','bank']).mean().groupby(['season','week']).mean().groupby('season').mean().mean()

def evaluate(root,support,actuals):
    receipt=json.loads((root/'receipt.json').read_text())
    assert not receipt['smoke'] and receipt['current_season_outcomes_accessible'] is False
    expected={(s['season'],s['week'],b) for s in support['slates'] for b in BANKS}
    observed=[(r['season'],r['week'],r['bank']) for r in receipt['records']]
    assert len(observed)==len(set(observed)) and set(observed)==expected
    assert set(actuals.season.unique())<=set(YEARS)
    assert not actuals.duplicated(['season','week','id']).any()
    all_rows=[];missing=[]
    for rec in receipt['records']:
        fp=root/rec['frame'];assert sha(fp)==rec['frame_sha256']
        fr=pd.read_parquet(fp)
        assert not any(c=='actual' or c=='was_active' or c.startswith('y_') for c in fr)
        assert len(fr)==fr.id.nunique() and fr.id.notna().all()
        assert (fr.season==rec['season']).all() and (fr.week==rec['week']).all()
        act=actuals[(actuals.season==rec['season'])&(actuals.week==rec['week'])]
        merged=fr.merge(act[['id','actual']],on='id',how='left',validate='one_to_one',sort=False)
        assert merged.id.tolist()==fr.id.tolist()
        y=pd.to_numeric(merged.actual,errors='coerce').to_numpy(float)
        eligible=fr.pos.isin((*SKILL,'DST')).to_numpy() & (pd.to_numeric(fr.mean_projection,errors='coerce').to_numpy()>=5)
        use=eligible & np.isfinite(y)
        for pos in SKILL: assert np.any(use & (fr.pos.to_numpy()==pos))
        missing.append({'season':rec['season'],'week':rec['week'],'bank':rec['bank'],
            'players':len(fr),'eligible':int(eligible.sum()),'missing_eligible_actual':int((eligible&~np.isfinite(y)).sum()),
            'scored':int(use.sum()),'missing_all_actual':int((~np.isfinite(y)).sum())})
        arrays={}
        for name in ['I','H']:
            p=root/rec['arrays'][name]['path'];assert sha(p)==rec['arrays'][name]['sha256']
            a=np.load(p,allow_pickle=False)
            assert list(a.shape)==rec['arrays'][name]['shape'] and a.shape[0]==len(fr) and np.isfinite(a).all()
            arrays[name]=a[use]
        i,h=arrays['I'],arrays['H'];assert i.shape==h.shape
        out=fr.loc[use,['id','season','week','pos','game_id']].reset_index(drop=True)
        out['bank']=rec['bank'];out['y']=y[use]
        for label,inputs in [('',(i,h,y[use])),('tail20_', (np.maximum(i,20),np.maximum(h,20),np.maximum(y[use],20)))]:
            for key,val in zip(('A','B','D'),terms(*inputs)): out[label+key]=val
        for threshold in [20,30,40]:
            out[f'I_p{threshold}']=(i>=threshold).mean(axis=1)
            out[f'H_p{threshold}']=(h>=threshold).mean(axis=1)
            out[f'y{threshold}']=(y[use]>=threshold).astype(float)
        all_rows.append(out)
    rows=pd.concat(all_rows,ignore_index=True)
    weights={};output=[]
    for year in YEARS[1:]:
        prior=rows[rows.season<year]
        assert len(prior) and prior.season.max()<year
        fit=balanced(prior,['A','B','D'])
        w=weight(fit.A,fit.B,fit.D)
        weights[str(year)]={'I_weight':w,'H_weight':1-w,'training_seasons':sorted(map(int,prior.season.unique())),
                            'training_balanced_terms':fit.to_dict()}
        r=rows[rows.season==year].copy();assert len(r)
        for name,wi in [('I',1.),('H',0.),('equal',.5),('learned',w)]:
            r[name+'_crps']=mix(r.A,r.B,r.D,wi)
            r[name+'_tail20']=mix(r.tail20_A,r.tail20_B,r.tail20_D,wi)
            for t in [20,30,40]:
                prob=wi*r[f'I_p{t}']+(1-wi)*r[f'H_p{t}']
                r[f'{name}_pred{t}']=prob
                r[f'{name}_brier{t}']=(prob-r[f'y{t}'])**2
        r['delta']=r.learned_crps-r.equal_crps
        output.append(r)
    scored=pd.concat(output,ignore_index=True)
    cells=scored[scored.pos.isin(SKILL)].groupby(['season','week','bank','pos']).delta.mean()
    slates=cells.groupby(['season','week','bank']).mean()
    paired=slates.groupby(['season','week']).mean()
    primary=float(paired.groupby('season').mean().mean())
    byseason=paired.groupby('season').mean().to_dict()
    bybank=slates.groupby(['season','bank']).mean().groupby('bank').mean().to_dict()
    rng=np.random.default_rng(20260919);reps=np.zeros(10000)
    for year in YEARS[1:]:
        d=paired.loc[year].to_numpy();assert len(d)>1
        reps+=d[rng.integers(0,len(d),size=(10000,len(d)))].mean(axis=1)/4
    ci=np.quantile(reps,[.025,.975]).tolist()
    advance=bool(all(v<0 for v in bybank.values()) and sum(v<0 for v in byseason.values())>=3 and ci[1]<0)
    cols=[c for c in scored if c.endswith(('_crps','_tail20')) or '_brier' in c or '_pred' in c or c in ['y20','y30','y40']]
    descriptive=scored.groupby(['season','week','bank','pos'])[cols].mean().groupby(['season','pos']).mean().groupby('pos').mean()
    return {'weights':weights,'primary_delta':primary,'primary_95_interval':ci,'by_season':byseason,
        'by_bank':bybank,'advance_to_separate_lineup_study':advance,
        'primary_scores':balanced(scored,['I_crps','H_crps','equal_crps','learned_crps']).to_dict(),
        'by_position':descriptive.to_dict(orient='index'),'support':missing,
        'scope':'Development predictive-quality screen; no lineup read or adoption'},scored

def synthetic():
    # Brute-force empirical CRPS and exact quadratic mixture against independently weighted pairs.
    rng=np.random.default_rng(76)
    for _ in range(20):
        i=rng.normal(size=(1,7));h=rng.normal(1,size=(1,7));y=np.array([.3])
        a,b,d=terms(i,h,y)
        for w in [0,.13,.5,.92,1]:
            x=np.r_[i[0],h[0]];mass=np.r_[np.full(7,w/7),np.full(7,(1-w)/7)]
            brute=np.sum(mass*abs(x-y[0]))-.5*np.sum(mass[:,None]*mass[None,:]*abs(x[:,None]-x[None,:]))
            assert abs(mix(a,b,d,w)[0]-brute)<1e-12
    root=Path(tempfile.mkdtemp(prefix='law-weight-synthetic-'))
    records=[];sl=[];actual=[]
    for year in YEARS:
        for week in [1,2]:
            sl.append({'season':year,'week':week})
            fr=pd.DataFrame({'id':[str(j) for j in range(20)],'pos':list((*SKILL,'DST'))*4,
                'season':year,'week':week,'game_id':'g','mean_projection':10.})
            fp=root/f'{year}-{week}.parquet';fr.to_parquet(fp,index=False)
            actual.append(fr[['id','season','week']].assign(actual=10.))
            for bank in BANKS:
                ar={}
                for name,mu in [('I',10.),('H',15.)]:
                    arr=np.full((20,10),mu);p=root/f'{year}-{week}-{bank}-{name}.npy';np.save(p,arr)
                    ar[name]={'path':p.name,'sha256':sha(p),'shape':list(arr.shape)}
                records.append({'season':year,'week':week,'bank':bank,'frame':fp.name,'frame_sha256':sha(fp),'arrays':ar})
    (root/'receipt.json').write_text(json.dumps({'smoke':False,'current_season_outcomes_accessible':False,'records':records}))
    report,_=evaluate(root,{'slates':sl},pd.concat(actual,ignore_index=True))
    assert all(v['I_weight']==1 for v in report['weights'].values())
    assert report['primary_delta']==-1.25 and report['advance_to_separate_lineup_study']
    # Changing last-year outcomes cannot change that year's fitted weight.
    changed=pd.concat(actual,ignore_index=True);changed.loc[changed.season==2024,'actual']=50
    again,_=evaluate(root,{'slates':sl},changed)
    assert report['weights']==again['weights']
    # Missing outcomes are counted, never converted to zeros.
    changed.loc[(changed.season==2024)&(changed.id=='0'),'actual']=np.nan
    missing,_=evaluate(root,{'slates':sl},changed)
    assert sum(r['missing_eligible_actual'] for r in missing['support'])==4
    print('SYNTHETIC_PASS: brute-force score, mixture quadratic, full walk-forward, label separation, missingness')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--synthetic',action='store_true')
    ap.add_argument('--bundle');ap.add_argument('--out');a=ap.parse_args()
    if a.synthetic: synthetic();return
    assert a.bundle and a.out and not Path(a.out).exists()
    base=Path(__file__).resolve().parent
    support=json.loads((base/'2026-09-19-law-weight-support.json').read_text())
    rec=next(r for r in support['files'] if '/snap_pitclean_k1/' in r['uri'])
    assert sha(rec['path'])==rec['sha256']
    actuals=pd.read_parquet(rec['path'],columns=['season','week','id','actual'])
    report,rows=evaluate(Path(a.bundle),support,actuals)
    report['reader_sha256']=sha(__file__);report['bundle_receipt_sha256']=sha(Path(a.bundle)/'receipt.json')
    rows.to_parquet(Path(a.out).with_suffix('.parquet'),index=False)
    Path(a.out).write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps({k:report[k] for k in ['primary_delta','primary_95_interval','by_season','by_bank','advance_to_separate_lineup_study']},indent=2))

if __name__=='__main__': main()
