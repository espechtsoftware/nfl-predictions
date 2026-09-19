"""Frozen head-policy diagnostic with fresh audit draws and unchanged membership."""
import hashlib
import importlib.util
import json
from pathlib import Path
import runpy
import subprocess
import sys
import time
import numpy as np
import pandas as pd
HERE=Path(__file__).parent

def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),HERE/name)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
h=load('2026-09-19-participation-host-transfer-v2.py')
assert h.sha(h.__file__)=='b2a4dad35eb98989a880ccdc60ff71ee958e6934d4c5141aa07c5c5ee9c70b38'
policy=load('2026-09-19-first-delivered-promotion.py')
assert h.sha(policy.__file__)=='36ffcbcedc9b1b46d5aea5c9d04b425f0b842e3569a53c20802ef39f36af959f'
ROOT=h.ROOT;LAB=h.LAB;RELEASE=h.RELEASE;sha=h.sha
OUT=ROOT/'first-delivered-promotion'

# Verbatim frozen host audit constructor, only the two fresh audit seeds changed.
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
        banks={'I':incumbent(16260919),'H':hsim(17260919)}
    identities={}
    for k,bank in banks.items():
        assert bank.shape==(428,10000) and bank.dtype==np.float32 and np.isfinite(bank).all()
        p=dest/(k+'_audit.npy')
        with p.open('xb') as f:np.save(f,bank,allow_pickle=False)
        identities[k]=dict(path=str(p),sha256=sha(p),seed={'I':16260919,'H':17260919}[k])
    return banks,identities


def main():
    started=time.monotonic();OUT.mkdir(exist_ok=False)
    base,selector,s,fr,rec,run,_=h.inputs()
    manifest=json.loads(h.MANIFEST.read_text())
    for p,v in manifest['files'].items():assert sha(p)==v
    rp=HERE/'2026-09-19-participation-host-transfer-result.json'
    assert sha(rp)=='7a66df1d54aaedb9aad9da2abd39bce48f7fd6a04ccbd5d6d748214986f733bf'
    original=json.loads(rp.read_text())
    selection={k:np.load(run/(n+'.npy'),allow_pickle=False) for k,n in
        [('I','incumbent_player_scores'),('H','corrected_hsim_player_scores')]}
    mixed,_=base.mixed_pair(selection,s['probs'],20260919054)
    books={};decisions={}
    for arm,banks in [('control',selection),('full',mixed)]:
        assert base.select(s,banks)==original['books'][arm]
        delivered=original['books'][arm+'_vetted']
        v=json.loads((h.OUT/'delivery'/arm/'vetted/vetting.json').read_text())
        assert v['order_source_ranks']==original['delivery'][arm]['order_source_ranks']
        clean=[not(v['lineups'][i-1]['hard'] or v['lineups'][i-1]['material']) for i in v['order_source_ranks']]
        books[arm]=delivered
        books[arm+'_promoted'],decisions[arm]=policy.promote(delivered,clean,selector.totals(banks,s['roster']))
    h.write(OUT/'frozen-books.json',dict(books=books,decisions=decisions))
    audit,audit_identity=audit_banks(fr,rec,run,OUT)
    mixed,audit_masks=base.mixed_pair(audit,s['probs'],20260919058)
    helper=runpy.run_path(str(HERE/'2026-09-19-repaired-chain-read.py'));regions=helper['REGIONS']
    raw=subprocess.check_output(['git','-C',str(LAB),'show','e7255e9:results/contest/milly_winners.json'])
    assert hashlib.sha256(raw).hexdigest()=='4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners=np.asarray(sorted(json.loads(raw).values()),float);samples={};metrics={}
    for assumption,bb in [('all_active',audit),('participation',mixed)]:
        for component,bank in bb.items():
            law=assumption+'_'+component;samples[law]={};metrics[law]={}
            for name,book in books.items():
                t=base.totals(bank,s['roster'][book]);samples[law][name]={};metrics[law][name]={}
                for region,sl in regions.items():
                    m=helper['metrics'](t[sl].max(axis=0).astype(float),winners)
                    m['mean_lineup']=t[sl].mean(axis=0,dtype=float)
                    samples[law][name][region]=m;metrics[law][name][region]={k:float(v.mean()) for k,v in m.items()}
            for arm in ('control','full'):
                for region,sl in regions.items():
                    if (region.startswith('prefix') and int(region[6:])>=30) or (region.startswith('block') and sl.start>=30):
                        for metric in samples[law][arm][region]:
                            assert np.array_equal(samples[law][arm][region][metric],samples[law][arm+'_promoted'][region][metric])
    laws={k:[k] for k in samples}
    for assumption in ('all_active','participation'):
        key=assumption+'_mixture';parts=[assumption+'_I',assumption+'_H'];laws[key]=parts
        metrics[key]={b:{r:{m:float(np.mean([metrics[p][b][r][m] for p in parts])) for m in metrics[parts[0]][b][r]}
            for r in regions} for b in books}
    contrasts={arm:{law:{r:{metric:helper['uncertainty']([samples[p][arm+'_promoted'][r][metric]-samples[p][arm][r][metric]
        for p in parts]) for metric in samples[parts[0]][arm][r]} for r in regions} for law,parts in laws.items()}
        for arm in ('control','full')}
    result=dict(schema='first-delivered-promotion/v1',source_sha256=sha(__file__),policy_sha256=sha(policy.__file__),
        protocol_sha256=sha(HERE.parents[1]/'2026-09-19-first-delivered-promotion-protocol.md'),
        original_result_sha256=sha(rp),host_input_manifest_sha256=sha(h.MANIFEST),books=books,decisions=decisions,
        metrics=metrics,contrasts=contrasts,audit_identity=audit_identity,audit_masks=audit_masks,
        membership_unchanged=True,prefix30_and_all_later_regions_exact=True,original_selection_banks_exact=True,
        seconds=time.monotonic()-started,current_scoring_outcomes_read=False,
        scope='New post-inspection exploratory head policy; fixed selection decision and fresh audits; no historical adoption validation or live entry changes.')
    h.write(OUT/'result.json',result)
    print(json.dumps(dict(seconds=result['seconds'],decisions=decisions,
        affected={arm:{r:contrasts[arm]['participation_mixture'][r] for r in ['prefix1','prefix10','prefix30','block2_24']}
            for arm in ('control','full')}),indent=2),flush=True)


if __name__=='__main__':main()
