"""Frozen four-arm designation decomposition; independent audit worlds only."""
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
spec=importlib.util.spec_from_file_location('original_participation',HERE/'2026-09-19-participation-transfer.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
OUT=base.BASE/'participation-designation-decomposition'
AUDIT=HERE/'2026-09-19-participation-designation-audit.json'
AUDIT_MASK_SEED=20260919055


def laws(s,banks,seed):
    full,masks=base.mixed_pair(banks,s['probs'],seed)
    ids={r['id']:r['selected_status'] for r in s['records']}
    labels=np.asarray([ids.get(x,'none') for x in s['fr'].id])
    result=dict(control=banks,full=full)
    for arm,label in [('doubtful','Doubtful'),('questionable','Questionable')]:
        included=labels==label
        result[arm]={k:np.where(included[:,None],full[k],b) for k,b in banks.items()}
        assert all(np.array_equal(result[arm][k][~included],b[~included]) for k,b in banks.items())
    return result,masks


def main(smoke=False):
    started=time.monotonic();s=base.inputs()
    dest=OUT.with_name(OUT.name+'-smoke') if smoke else OUT
    dest.mkdir(exist_ok=False)
    if smoke:
        rng=np.random.default_rng(555)
        selection={k:rng.gamma(2,5,(len(s['fr']),400)).astype(np.float32) for k in ('I','H')}
        audit={k:rng.gamma(2,5,(len(s['fr']),400)).astype(np.float32) for k in ('I','H')}
        audit_identity={'synthetic':True}
    else:
        selection={k:np.load(base.opened(s['receipt']['arrays'][k+'_selection']),allow_pickle=False) for k in ('I','H')}
        audit_identity=json.loads(AUDIT.read_text());audit={}
        assert audit_identity['original_laws_exact']
        for k,seed in [('I',12260919),('H',13260919)]:
            r=audit_identity['arrays'][k+'_audit'];assert r['seed']==seed
            audit[k]=np.load(base.opened(r),allow_pickle=False)
            assert audit[k].shape==(len(s['fr']),10000) and audit[k].dtype==np.float32
            assert not np.array_equal(audit[k],selection[k])
    sel_laws,selection_masks=laws(s,selection,base.SELECTION_SEED)
    books={arm:base.select(s,b) for arm,b in sel_laws.items()}
    if not smoke:
        original=json.loads((base.OUT/'result.json').read_text())
        assert books['control']==original['books']['control']
        assert books['full']==original['books']['pmix']
    base.write(dest/'frozen-books.json',books)
    frame=pd.read_parquet(s['original']/'frame.parquet').set_index('id')
    from nfl2.validator import validate_roster
    args=[frame[k].to_dict() for k in ('pos','team','opp','salary')]
    for book in books.values():
        assert len(book)==len(set(book))==97
        for i in book:
            assert not validate_roster(s['orders'][i],*args)
            assert not validate_roster(s['orders'][i],*args,salary_floor=49000,qb_stack_min=2,
                bring_back_min=1,forbid_rb_vs_dst=True,forbid_two_rb_same_team=True)
    delivery=base.vet(s,books,dest/'delivery')
    books.update({k+'_vetted':r['indices'] for k,r in delivery.items()})
    del selection,sel_laws
    aud_laws,audit_masks=laws(s,audit,AUDIT_MASK_SEED)
    assert {r['sha256'] for r in selection_masks}.isdisjoint(r['sha256'] for r in audit_masks)
    helper=runpy.run_path(str(HERE/'2026-09-19-repaired-chain-read.py'));regions=helper['REGIONS']
    raw=subprocess.check_output(['git','-C',str(base.LAB),'show','e7255e9:results/contest/milly_winners.json'])
    import hashlib
    assert hashlib.sha256(raw).hexdigest()=='4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners=np.asarray(sorted(json.loads(raw).values()),float)
    samples={};metrics={}
    for assumption,banks in aud_laws.items():
        for comp,bank in banks.items():
            law=assumption+'_'+comp;samples[law]={};metrics[law]={}
            for name,book in books.items():
                t=base.totals(bank,s['roster'][book]);samples[law][name]={};metrics[law][name]={}
                for region,sl in regions.items():
                    mx=t[sl].max(axis=0).astype(float);m=helper['metrics'](mx,winners)
                    m.update(mean_lineup=t[sl].mean(axis=0,dtype=float),p194=(mx>=194).astype(float),
                        p240=(mx>=240).astype(float),excess220=np.maximum(mx-220,0))
                    samples[law][name][region]=m
                    metrics[law][name][region]={k:float(v.mean()) for k,v in m.items()}
    groups={k:[k] for k in samples}
    for assumption in aud_laws:
        law=assumption+'_mixture';parts=[assumption+'_I',assumption+'_H'];groups[law]=parts
        metrics[law]={book:{reg:{metric:float(np.mean([metrics[k][book][reg][metric] for k in parts]))
            for metric in metrics[parts[0]][book][reg]} for reg in regions} for book in books}
    pairs=[(arm,'control') for arm in ('full','doubtful','questionable')]+[('doubtful','full'),('questionable','full')]
    pairs+= [(a+'_vetted',b+'_vetted') for a,b in pairs]
    contrasts={a+'-minus-'+b:{law:{reg:{metric:helper['uncertainty']([
        samples[k][a][reg][metric]-samples[k][b][reg][metric] for k in parts])
        for metric in samples[parts[0]][a][reg]} for reg in regions} for law,parts in groups.items()} for a,b in pairs}
    exposures={name:{r['name']:sum(r['id'] in s['orders'][i] for i in book) for r in s['records']} for name,book in books.items()}
    result=dict(schema='participation-designation-decomposition/v1',synthetic_smoke=smoke,
        protocol_sha256=base.sha(base.REPO/'reports/2026-09-19-participation-designation-protocol.md'),
        source_sha256=base.sha(__file__),base_reader_sha256=base.sha(base.__file__),
        cutoff=s['cutoff'],candidate_count=len(s['keep']),entries=97,books=books,delivery=delivery,
        map_records=s['records'],selection_masks=selection_masks,audit_masks=audit_masks,
        audit_identity=audit_identity,metrics=metrics,contrasts=contrasts,exposures=exposures,
        source_control_and_full_exact=not smoke,all_books_legal=True,football_outcomes_read=False,
        elapsed_seconds=time.monotonic()-started,
        scope='Exploratory model sensitivity, fresh event/mask audit draws; no historical adoption evidence for narrowed rules.')
    base.write(dest/'result.json',result)
    print(json.dumps(dict(smoke=smoke,elapsed_seconds=result['elapsed_seconds'],
        delivered_whole_book={law:{book:r['prefix97'] for book,r in rows.items() if book.endswith('_vetted')}
            for law,rows in metrics.items() if law.endswith('_mixture')}),indent=2),flush=True)


if __name__=='__main__':
    sys.path[:0]=[str(base.REPO/'src'),str(base.LAB/'src')]
    main('--smoke' in sys.argv)
