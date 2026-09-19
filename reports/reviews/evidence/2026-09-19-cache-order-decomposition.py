"""Replay actual incumbent banks, then isolate historical content/order effects."""
import hashlib,json,os,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
LAB=Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
ROOT=Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')
OUT=ROOT/'cache-order-decomposition'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=False)
    sys.path.insert(0,str(LAB/'src'))
    from nfl2 import data
    from nfl2.core import components,coldstart,simulate
    from nfl2.core.draw_shape import apply_draw_shape,apply_served_position_scales
    from nfl2.core.blend import shift_draws_to_means
    from nfl2.pipeline import PRODUCTION_ENV
    proof={k:json.loads((ROOT/('live-cli-'+k+'-proof.json')).read_text()) for k in ['host','fresh']}
    tr={}
    for k in proof:
        p=ROOT/('live-cli-'+k+'-cache')/'training_through_2025.parquet'
        assert sha(p)==proof[k]['historical_cache_sha256'];tr[k]=pd.read_parquet(p)
        assert int(tr[k].season.max())==2025
    keys=['gsis_id','season','week']
    indices={k:pd.MultiIndex.from_frame(d[keys]) for k,d in tr.items()}
    assert all(v.is_unique for v in indices.values()) and set(indices['host'])==set(indices['fresh'])
    assert tr['host'].columns.tolist()==tr['fresh'].columns.tolist()
    fr=pd.read_parquet(Path(proof['host']['run'])/'frame.parquet')
    tab=pd.read_parquet(ROOT/'refreshed-cache.parquet');tab=tab[tab.season.eq(2026)&tab.week.eq(2)].copy()
    skill=fr.position.isin(['QB','RB','WR','TE']).to_numpy();modeled=skill&fr.has_features.to_numpy()
    rows=coldstart.fill_cold_start_features(fr[modeled].copy());rowkeys=rows[keys].reset_index(drop=True)
    target=fr.mean_projection.to_numpy(float);banks={};predictions={};timing={};source={}
    os.environ['MODEL_ENSEMBLE']='1'
    def one(values,order):
        name=values+'_values_'+order+'_order';t=time.monotonic()
        panel=tr[values].copy();panel.index=indices[values];panel=panel.loc[indices[order]].reset_index(drop=True)
        assert pd.MultiIndex.from_frame(panel[keys]).equals(indices[order])
        model=components.train(panel,target_season=2026);comps=model.predict_components(rows)
        seed=2076;d=np.zeros((len(fr),10000))
        sim=simulate.simulate(comps,n_sims=10000,seed=seed,keep_draws=True,
            game_ids=rows.game_id.reset_index(drop=True),team_ids=rows.team.reset_index(drop=True),
            game_totals=rows.game_total.reset_index(drop=True),env=PRODUCTION_ENV)
        shaped=apply_draw_shape(sim.draws,rows.position.reset_index(drop=True),seed,keys=rowkeys,env=PRODUCTION_ENV,tabpfn_cache_rows=tab)
        d[modeled]=apply_served_position_scales(shaped,rows.position.reset_index(drop=True),env=PRODUCTION_ENV)
        rng=np.random.default_rng(seed)
        for i in np.flatnonzero(skill&~modeled):
            mu=float(fr.dk_ppg.iloc[i]) if pd.notna(fr.dk_ppg.iloc[i]) and fr.dk_ppg.iloc[i]>0 else 2.0
            d[i]=rng.gamma(2.0,mu/2.0,size=10000)
        d[skill]=shift_draws_to_means(d[skill],target[skill]);d[~skill]=target[~skill,None]
        bank=d.astype(np.float32);assert np.isfinite(bank).all()
        comps.to_parquet(OUT/(name+'-components.parquet'),index=False);np.save(OUT/(name+'-bank.npy'),bank)
        banks[name]=bank;predictions[name]=comps.to_numpy(float);timing[name]=time.monotonic()-t
        source[name]=dict(component_sha256=sha(OUT/(name+'-components.parquet')),bank_sha256=sha(OUT/(name+'-bank.npy')))
        if values==order:
            original=np.load(Path(proof[values]['run'])/'incumbent_player_scores.npy')
            assert np.array_equal(bank,original),'actual CLI replay failed: '+name
        print('REPLAY_PASS',name,round(timing[name],3),flush=True)
    with data.outcome_firewall(2026):
        one('host','host');one('fresh','fresh')
        one('fresh','host');one('host','fresh')
    contrasts={}
    for a,b in [('fresh_values_host_order','host_values_host_order'),('fresh_values_fresh_order','host_values_fresh_order'),
                ('host_values_fresh_order','host_values_host_order'),('fresh_values_fresh_order','fresh_values_host_order')]:
        x,y=banks[a],banks[b];mask=(x.std(axis=1)>1e-8)&(y.std(axis=1)>1e-8)
        cx,cy=np.corrcoef(x[mask]),np.corrcoef(y[mask]);tri=np.triu_indices(len(cx),1)
        contrasts[a+'-minus-'+b]=dict(changed_components=int(np.count_nonzero(predictions[a]!=predictions[b])),
            component_max_absolute_difference=float(abs(predictions[a]-predictions[b]).max()),
            different_bank_cells=int(np.count_nonzero(x!=y)),max_absolute_cell_difference=float(abs(x-y).max()),
            per_player_multisets_equal=np.array_equal(np.sort(x,axis=1),np.sort(y,axis=1)),
            correlation_pairs=len(tri[0]),mean_absolute_correlation_difference=float(abs(cx-cy)[tri].mean()))
    result=dict(contrasts=contrasts,artifacts=source,seconds=timing,actual_cli_replays_exact=True,
        source_sha256=sha(Path(__file__)),input_cache_sha256={k:r['historical_cache_sha256'] for k,r in proof.items()},
        scope='Engineering content/order factorial, no candidate solves, selector scores or current NFL outcomes; actual host cache untouched')
    with (OUT/'result.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':main()
