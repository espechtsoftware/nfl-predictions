"""Frozen incremental injury-type target-mean screen; forecast before target labels."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor

YEARS=(2019,2021,2022,2023,2024)
KEY=['gsis_id','season','week']
SITES=('knee','ankle','hamstring','shoulder','foot','hip','concussion','illness',
       'groin','back','calf','quadricep','thigh','toe','rib','neck','wrist','hand')
LABEL_SHA='445de23a683c17437723c98f4619296f742d13f5843bcb90a77b97af88308419'
SAFE_SHA='842fa31c6f20e635593d59772cf0aafd9b1e81ff56c97e3261580da4e0874393'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def design(fr,numeric,extra):
    assert not any(c=='was_active' or c=='actual' or c.startswith('y_') for c in fr)
    assert not set(numeric)&{'was_active','actual','y_targets'}
    x=fr[numeric].apply(pd.to_numeric,errors='coerce').to_numpy(float)
    assert not np.isinf(x).any()
    cols=[x]
    for p in ['RB','WR','TE']:cols.append(fr.position.eq(p).to_numpy(float)[:,None])
    status=fr.injury_status.astype('string').fillna('NONE')
    known=['Out','Doubtful','Questionable','Probable','NONE']
    for s in known:cols.append(status.eq(s).to_numpy(float)[:,None])
    cols.extend([(~status.isin(known)).to_numpy(float)[:,None],fr.has_report.to_numpy(float)[:,None]])
    if extra:
        txt=fr.type.astype('string').fillna('').str.lower()
        flags=[txt.str.contains(s,regex=False).to_numpy(bool) for s in SITES]
        flags.append(txt.str.contains('not injury related',regex=False).to_numpy(bool))
        flags.append(txt.ne('').to_numpy(bool)&~np.logical_or.reduce(flags))
        flags.append(fr.has_report.to_numpy(bool)&txt.eq('').to_numpy(bool))
        cols.append(np.column_stack(flags).astype(float))
    return np.column_stack(cols)

def eligible(fr):return fr.receiving_role.astype(bool)&fr.sunday_main.astype(bool)
def new_model():
    return HistGradientBoostingRegressor(loss='poisson',learning_rate=.05,max_iter=100,
        max_leaf_nodes=7,min_samples_leaf=30,l2_regularization=10.,max_features=1.,
        early_stopping=False,categorical_features=None,random_state=20260919)

def fit_predict(safe,prior,year,numeric):
    assert len(prior) and prior.season.max()<year and not prior.duplicated(KEY).any()
    fit=safe[(safe.season<year)&eligible(safe)].merge(prior,on=KEY,how='left',validate='one_to_one')
    y=pd.to_numeric(fit.y_targets,errors='coerce')
    assert not (y.dropna()<0).any()
    use=fit.was_active.eq(True).fillna(False)&y.notna()
    train=fit.loc[use,safe.columns].copy()
    target=safe[(safe.season==year)&eligible(safe)].copy()
    assert len(train)>=200 and len(target)>0
    out=target[KEY+['position','injury_status','practice_level','has_type']].copy()
    training={'year':year,'rows':len(train),'max_training_season':int(train.season.max()),
              'eligible_past':len(fit),'missing_activity':int(fit.was_active.isna().sum()),
              'active_missing_targets':int((fit.was_active.eq(True).fillna(False)&y.isna()).sum())}
    for name,extra in [('control',False),('treatment',True)]:
        x=design(train,numeric,extra);xt=design(target,numeric,extra)
        # sklearn 1.9.1's binning crashes on an entirely missing feature.
        # Such a column contains no train-time split information. Drop it in
        # both fit and prediction, using the training covariates only.
        keep=~np.isnan(x).all(axis=0);assert keep.any()
        training[name+'_all_missing_columns_removed']=np.flatnonzero(~keep).tolist()
        model=new_model();model.fit(x[:,keep],y[use].to_numpy(float))
        mu=model.predict(xt[:,keep])
        assert np.isfinite(mu).all() and (mu>0).all()
        out[name+'_mu']=mu
    return out,training

def deviance(y,mu):
    y=np.asarray(y,dtype=float);mu=np.asarray(mu,dtype=float)
    assert np.isfinite(y).all() and np.isfinite(mu).all() and (y>=0).all() and (mu>0).all()
    t=np.zeros_like(y);m=y>0;t[m]=y[m]*np.log(y[m]/mu[m])
    return 2*(t-y+mu)

def average(rows,column):
    return float(rows.groupby(['season','week'])[column].mean().groupby('season').mean().mean())

def evaluate(pred,actual):
    assert set(pred.season.unique())==set(YEARS) and not pred.duplicated(KEY).any()
    assert set(actual.season.unique())<=set(YEARS) and not actual.duplicated(KEY).any()
    d=pred.merge(actual,on=KEY,how='left',validate='one_to_one',sort=False)
    assert len(d)==len(pred)
    y=pd.to_numeric(d.y_targets,errors='coerce')
    assert not (y.dropna()<0).any()
    active=d.was_active.eq(True).fillna(False)
    support=[]
    for year,g in d.groupby('season'):
        a=g.was_active.eq(True).fillna(False);known=pd.to_numeric(g.y_targets,errors='coerce').notna()
        support.append({'season':int(year),'predicted':len(g),'active':int(a.sum()),
            'missing_activity':int(g.was_active.isna().sum()),'active_missing_targets':int((a&~known).sum()),
            'scored':int((a&known).sum()),'questionable_scored':int((a&known&g.injury_status.eq('Questionable').fillna(False)).sum())})
    d=d.loc[active&y.notna()].copy();d['y']=y[active&y.notna()].to_numpy(float)
    for name in ['control','treatment']:
        d[name+'_deviance']=deviance(d.y,d[name+'_mu'])
        d[name+'_bias']=d[name+'_mu']-d.y
        d[name+'_mae']=abs(d[name+'_mu']-d.y)
    d['delta']=d.treatment_deviance-d.control_deviance
    q=d[d.injury_status.eq('Questionable').fillna(False)]
    assert set(q.season.unique())==set(YEARS)
    assert q.groupby('season').size().min()>=30
    slate=q.groupby(['season','week']).delta.mean()
    assert slate.groupby('season').size().min()>=2
    by_year=slate.groupby('season').mean()
    primary=float(by_year.mean());rng=np.random.default_rng(20260919);reps=np.zeros(10000)
    for year in YEARS:
        x=slate.loc[year].to_numpy();reps+=x[rng.integers(0,len(x),size=(10000,len(x)))].mean(axis=1)/len(YEARS)
    ci=np.quantile(reps,[.025,.975]).tolist()
    secondary=average(d,'delta')
    cols=['control_deviance','treatment_deviance','control_bias','treatment_bias','control_mae','treatment_mae']
    descriptive=[]
    for name,group in [('position','position'),('practice','practice_level')]:
        for value,g in q.groupby(group,dropna=False):
            descriptive.append({'group':name,'value':str(value),'rows':len(g),
                                'scores':{c:average(g,c) for c in cols}})
    return {'primary_delta':primary,'primary_95_interval':ci,
        'primary_scores':{c:average(q,c) for c in cols},'by_season':by_year.to_dict(),
        'all_active_delta':secondary,'all_active_scores':{c:average(d,c) for c in cols},
        'nominate_for_separate_followup':bool(ci[1]<0 and secondary<=0),
        'support':support,'descriptive':descriptive,
        'scope':'One exploratory incremental-information screen; not a served-model or lineup effect'},d

def construct(safe_path,label_path,support_path,out):
    assert sha(safe_path)==SAFE_SHA and sha(label_path)==LABEL_SHA
    support=json.loads(Path(support_path).read_text());assert support['safe_extract_sha256']==SAFE_SHA
    safe=pd.read_parquet(safe_path)
    assert not any(c=='was_active' or c=='actual' or c.startswith('y_') for c in safe)
    assert safe.season.max()==2024 and not safe.duplicated(KEY).any()
    out.mkdir(exist_ok=False);records=[];start=time.monotonic()
    for year in YEARS:
        # Only earlier labels enter memory for this fit; target labels are not loaded here.
        prior=pd.read_parquet(label_path,columns=KEY+['was_active','y_targets'],filters=[('season','<',year)])
        p,meta=fit_predict(safe,prior,year,support['baseline_numeric_features'])
        dest=out/f'{year}-predictions.parquet';p.to_parquet(dest,index=False)
        records.append({**meta,'path':dest.name,'sha256':sha(dest),'prediction_rows':len(p)})
        print('FORECAST_YEAR',json.dumps(meta),flush=True)
    receipt={'records':records,'source_sha256':sha(__file__),'safe_sha256':SAFE_SHA,'label_sha256':LABEL_SHA,
        'runtime':{'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__},
        'elapsed_seconds':time.monotonic()-start}
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2));return receipt

def read(forecast,label_path):
    receipt=json.loads((forecast/'receipt.json').read_text())
    assert receipt['source_sha256']==sha(__file__) and receipt['safe_sha256']==SAFE_SHA and sha(label_path)==LABEL_SHA
    assert [r['year'] for r in receipt['records']]==list(YEARS)
    frames=[]
    for r in receipt['records']:
        p=forecast/r['path'];assert sha(p)==r['sha256']
        f=pd.read_parquet(p);assert len(f)==r['prediction_rows'] and (f.season==r['year']).all();frames.append(f)
    actual=pd.read_parquet(label_path,columns=KEY+['was_active','y_targets'],filters=[('season','in',list(YEARS))])
    return evaluate(pd.concat(frames,ignore_index=True),actual)

def synthetic():
    assert np.allclose(deviance([0,2,3],[1,2,1]),[2,0,2*(3*np.log(3)-2)])
    rows=[];labels=[]
    for year in (2014,*YEARS):
        for week in (1,2):
            for i in range(150):
                rows.append({'gsis_id':str(i),'season':year,'week':week,'position':['RB','WR','TE'][i%3],
                    'injury_status':'Questionable','practice_level':1.,'type':'Hamstring' if i%2 else 'Knee',
                    'has_type':True,'has_report':True,'receiving_role':True,'sunday_main':True,'x':1.})
                labels.append({'gsis_id':str(i),'season':year,'week':week,'was_active':True,'y_targets':1. if i%2 else 8.})
    safe=pd.DataFrame(rows);actual=pd.DataFrame(labels);pred=[]
    for year in YEARS:
        p,_=fit_predict(safe,actual[actual.season<year],year,['x']);pred.append(p)
    p=pd.concat(pred,ignore_index=True);a=actual[actual.season.isin(YEARS)].copy()
    result,_=evaluate(p,a);assert result['nominate_for_separate_followup'] and result['primary_delta']<-.5
    a.loc[a.index[0],'y_targets']=np.nan
    missing,_=evaluate(p,a);assert sum(r['active_missing_targets'] for r in missing['support'])==1
    try:fit_predict(safe,actual,2019,['x'])
    except AssertionError:pass
    else:raise AssertionError('target/future label firewall failed')
    try:design(safe.assign(y_targets=0),['x'],True)
    except AssertionError:pass
    else:raise AssertionError('outcome feature firewall failed')
    print('SYNTHETIC_PASS full forecasts/read, informative injury type, deviance, missingness, label firewalls')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--synthetic',action='store_true');args=ap.parse_args()
    if args.synthetic:synthetic()
    else:raise SystemExit('Use the separately authenticated cloud adapter for real inputs')
