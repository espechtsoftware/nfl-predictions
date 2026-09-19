"""Frozen two-rule, season walk-forward target-share calibration screen."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).parent
OUT=ROOT/'2026-09-19-zero-target-prior-read.json'
LAB=Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
SEASONS=(2019,2021,2022,2023,2024,2025)
FALLBACK={'RB':.02,'WR':.03,'TE':.02}
sys.path.insert(0,str(LAB/'src'))
from nfl2.hsim.shares import active_mask,_prior_weights,TARGET_POS


def prepare(d):
    d=d.copy()
    d['pos']=d.position
    d['active']=active_mask(d)
    d['eligible']=d.pos.isin(FALLBACK)&d.target_share_l4.eq(0)&d.snap_share_l4.ge(.2)&d.games_played_prior.ge(1)&d.active
    d['snap_bin']=np.select([d.snap_share_l4.lt(.5).to_numpy(bool,na_value=False),d.snap_share_l4.lt(.8).to_numpy(bool,na_value=False)],['20-49','50-79'],default='80+')
    d['gp_bin']=np.select([d.games_played_prior.lt(2).to_numpy(bool,na_value=False),d.games_played_prior.lt(5).to_numpy(bool,na_value=False)],['1','2-4'],default='5+')
    d['known']=d.y_targets.notna()&d.y_targets.ge(0)
    keys=['season','week','team']
    d['team_targets']=d.y_targets.where(d.known).groupby([d[x] for x in keys]).transform('sum')
    d['valid']=d.known&d.team_targets.gt(0)
    d['observed_share']=d.y_targets.where(d.valid)/d.team_targets.where(d.team_targets.gt(0))
    d['original_weight']=_prior_weights(d,'target_share_l4',TARGET_POS,FALLBACK)
    d['fixed_prior']=d.pos.map(FALLBACK)/(1+d.games_played_prior.clip(upper=4))
    return d


def fit(d,target):
    train=d[d.season.lt(target)&d.eligible&d.valid]
    assert len(train) and train.season.max()<target
    positions=train.groupby('pos').observed_share.mean().to_dict()
    cells={}
    for key,g in train.groupby(['pos','snap_bin','gp_bin']):
        center=positions.get(key[0],FALLBACK[key[0]])
        cells['|'.join(key)]=dict(n=len(g),value=float((g.observed_share.sum()+20*center)/(len(g)+20)))
    return dict(target_season=target,max_training_season=int(train.season.max()),
                n_training=len(train),positions=positions,cells=cells)


def predict(d,model):
    return np.asarray([model['cells'].get('|'.join((p,s,g)),{}).get('value',model['positions'].get(p,FALLBACK.get(p,0)))
                       for p,s,g in zip(d.pos,d.snap_bin,d.gp_bin)],dtype=float)


def evaluate(d,model):
    d=d.copy();d['learned_prior']=predict(d,model)
    eligible=d.eligible&d.valid
    weights={'control':d.original_weight.to_numpy(float)}
    for name,col in [('one_prior_game','fixed_prior'),('past_empirical','learned_prior')]:
        w=d.original_weight.where(~d.eligible,d[col]).to_numpy(float)
        assert np.array_equal(w[~d.eligible],weights['control'][~d.eligible])
        assert np.isfinite(w).all() and (w>=0).all()
        weights[name]=w
    norms={};zero={}
    for name,w in weights.items():
        denom=pd.Series(w,index=d.index).groupby([d.season,d.week,d.team]).transform('sum').to_numpy(float)
        zero[name]=denom<=0
        norms[name]=np.divide(w,denom,out=np.zeros_like(w),where=denom>0)
    common_supported=np.logical_and.reduce([~z for z in zero.values()])
    secondary=d.valid&d.active&d.pos.isin(FALLBACK)&common_supported
    losses={}
    y=d.observed_share.to_numpy(float)
    for name in weights:
        pred=weights[name]  # eligible control is exactly zero; treatment inserts its predicted share.
        primary=(pred[eligible]-y[eligible])**2
        sec=(norms[name][secondary]-y[secondary])**2
        assert len(primary) and len(sec)
        losses[name]=dict(eligible_mse=float(primary.mean()),eligible_n=len(primary),
            team_normalized_mse=float(sec.mean()),team_normalized_n=len(sec),
            eligible_loss_sum=float(primary.sum()),team_normalized_loss_sum=float(sec.sum()),
            zero_weight_teams=int(d.loc[zero[name],['season','week','team']].drop_duplicates().shape[0]))
    groups=[]
    for cols in [('pos',),('snap_bin',),('gp_bin',),('pos','snap_bin','gp_bin')]:
        for key,g in d[eligible].groupby(list(cols)):
            key=key if isinstance(key,tuple) else (key,)
            idx=d.index.get_indexer(g.index)
            groups.append(dict(group=dict(zip(cols,key)),n=len(g),positive_target_rows=int(g.y_targets.gt(0).sum()),
                observed_target_mass=float(g.y_targets.sum()),mean_observed_share=float(g.observed_share.mean()),
                mse={name:float(((w[idx]-y[idx])**2).mean()) for name,w in weights.items()}))
    summary=dict(rows=len(d),eligible_support=int(d.eligible.sum()),eligible_valid=int(eligible.sum()),
        eligible_missing_or_zero_team=int((d.eligible&~d.valid).sum()),missing_target_labels=int(d.y_targets.isna().sum()),
        negative_target_labels=int(d.y_targets.lt(0).sum()),
        known_target_mass=float(d.loc[d.known,'y_targets'].sum()),
        known_target_mass_outside_activity=float(d.loc[d.known&~d.active,'y_targets'].sum()),
        positive_target_eligible_rows=int(d.loc[eligible,'y_targets'].gt(0).sum()),
        eligible_target_mass=float(d.loc[eligible,'y_targets'].sum()),
        common_supported_secondary_rows=int(secondary.sum()))
    return dict(model=model,summary=summary,losses=losses,groups=groups)


def main():
    assert not OUT.exists()
    meta=json.loads((ROOT/'2026-09-19-zero-target-prior-current-support.json').read_text())
    p=Path(meta['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==meta['input']['sha256']
    cols=['gsis_id','season','week','team','position','snap_share_l4','target_share_l4',
          'games_played_prior','is_cold_start','depth_rank','y_targets']
    raw=pd.read_parquet(p,columns=cols,filters=[('season','<',2026)])
    assert len(raw)==102927 and raw.season.max()==2025
    assert not raw.duplicated(['gsis_id','season','week']).any()
    d=prepare(raw);reads={}
    for season in SEASONS:reads[str(season)]=evaluate(d[d.season.eq(season)],fit(d,season))
    pooled={}
    for arm in ('control','one_prior_game','past_empirical'):
        ls=[r['losses'][arm] for r in reads.values()]
        pooled[arm]=dict(eligible_mse=sum(x['eligible_loss_sum'] for x in ls)/sum(x['eligible_n'] for x in ls),
            team_normalized_mse=sum(x['team_normalized_loss_sum'] for x in ls)/sum(x['team_normalized_n'] for x in ls))
    nominations={}
    for arm in ('one_prior_game','past_empirical'):
        positive=sum(r['losses'][arm]['eligible_mse']<r['losses']['control']['eligible_mse'] for r in reads.values())
        qualifies=positive>=5 and pooled[arm]['eligible_mse']<pooled['control']['eligible_mse'] and pooled[arm]['team_normalized_mse']<=pooled['control']['team_normalized_mse']
        nominations[arm]=dict(positive_primary_seasons=positive,nominated_for_simulator_trace=qualifies)
    result=dict(input=meta['input'],source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        reads=reads,pooled=pooled,nominations=nominations,prospective_model=fit(d,2026),
        scope='Exploratory historical target-share calibration, season walk-forward; no 2026 labels, lineup outcomes or adoption.')
    with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(pooled=pooled,nominations=nominations,season_summary={s:r['summary'] for s,r in reads.items()}),indent=2))


if __name__=='__main__':main()
