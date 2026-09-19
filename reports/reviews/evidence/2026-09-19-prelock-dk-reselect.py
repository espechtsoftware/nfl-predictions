"""Preview ordinary selection on saved candidates after fresh DK exclusions.

No participation priors, official-active inference, player replacement, new
candidate generation, entry upload or source-run mutation. Before first lock only.
"""
import argparse
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import requests

HERE=Path(__file__).parent
HELPER=HERE/'2026-09-19-participation-reselect.py'
assert hashlib.sha256(HELPER.read_bytes()).hexdigest()=='4a861fe92f72e433eab1b1324d325a4be21a5d2b927acbd3407e797c0d6aaad9'
spec=importlib.util.spec_from_file_location('verified_saved_selector',HELPER)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
URI='https://api.draftkings.com/draftgroups/v1/draftgroups/153428/draftables'
LOCK=pd.Timestamp('2026-09-20T17:00:00Z')
OUT_STATUSES={'O','OUT','IR'}
ALLOWED_STATUSES={'','NONE','Q','D',*OUT_STATUSES}


def now():return pd.Timestamp(datetime.now(timezone.utc))
def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,default=str,allow_nan=False)


def normalized(payload,observed):
    from nfl_dfs.ingest.dk_client import draftables_frame
    assert payload['errorStatus']=={},'DK reports an error'
    comps=payload['competitions'];assert len(comps)==13
    assert len({x['competitionId'] for x in comps})==13
    assert all(x['sportId']==1 and x['competitionState']=='Upcoming' for x in comps)
    assert all(x.get('competitionStartedEarly') is not True for x in comps)
    starts=pd.to_datetime([x['startTime'] for x in comps],format='ISO8601',utc=True)
    assert starts.min()==LOCK and starts.max()<pd.Timestamp('2026-09-21T00:00:00Z')
    assert observed<starts.min()
    raw=payload['draftables'];assert raw
    # Classic repeats have different roster-slot/draftable IDs. The existing
    # client keeps their first ordinary-position row. All status, salary and
    # identity fields must agree across those slot variants.
    fields=('displayName','teamAbbreviation','position','salary','status','isDisabled','isSwappable')
    agreed={}
    for row in raw:
        assert set(fields)<=set(row)
        values=tuple(row[k] for k in fields);pid=row['playerId']
        assert pid not in agreed or agreed[pid]==values,'contradictory DK slot variants'
        agreed[pid]=values
        assert row['competition']['competitionId'] in {x['competitionId'] for x in comps}
    fr=draftables_frame(153428,'classic',payload)
    fr=fr[['pulled_at','draft_group_id','dk_player_id','dk_draftable_id','display_name',
        'team_abbr','position','salary','status','game_start']].copy()
    fr['pulled_at']=observed
    fr['dk_disabled']=[agreed[i][-2] for i in fr.dk_player_id]
    fr['dk_swappable']=[agreed[i][-1] for i in fr.dk_player_id]
    assert fr.dk_player_id.is_unique and fr.dk_draftable_id.is_unique
    return fr


def capture(root):
    from nfl_dfs.ingest.dk_client import HEADERS
    root.mkdir(parents=True,exist_ok=False);start=now()
    response=requests.get(URI,headers=HEADERS,timeout=30);response.raise_for_status();received=now()
    p=root/'source.json';p.write_bytes(response.content)
    fr=normalized(response.json(),received);fr.to_parquet(root/'dk.parquet',index=False)
    receipt=dict(schema='prelock-dk-capture/v1',season=2026,week=2,draft_group=153428,uri=URI,
        started_at=str(start),received_at=str(received),response_date=response.headers.get('Date'),
        source_sha256=base.sha(p),source_bytes=p.stat().st_size,frame_sha256=base.sha(root/'dk.parquet'),
        producer_sha256=base.sha(__file__),rows=len(fr),official_active_inference=False)
    write(root/'receipt.json',receipt);load_capture(root)
    print('DIRECT_DK_CAPTURE_VERIFIED',received,len(fr),flush=True)


def load_capture(root,checked_at=None):
    r=json.loads((root/'receipt.json').read_text());at=pd.Timestamp(r['received_at'])
    checked=now() if checked_at is None else pd.Timestamp(checked_at)
    assert r['schema']=='prelock-dk-capture/v1' and r['uri']==URI
    assert (r['season'],r['week'],r['draft_group'])==(2026,2,153428)
    assert at.tzinfo and checked.tzinfo and 0<=(checked-at).total_seconds()<=600
    assert pd.Timestamp(r['started_at'])<=at and checked<LOCK
    server=pd.Timestamp(parsedate_to_datetime(r['response_date']))
    assert abs((server-at).total_seconds())<=300,'DK response clock differs'
    p=root/'source.json';assert p.stat().st_size==r['source_bytes'] and base.sha(p)==r['source_sha256']
    assert base.sha(root/'dk.parquet')==r['frame_sha256']
    fr=pd.read_parquet(root/'dk.parquet');expected=normalized(json.loads(p.read_bytes()),at)
    pd.testing.assert_frame_equal(fr,expected,check_exact=True)
    assert len(fr)==r['rows']
    return fr,r


def eligible_candidates(fr,orders,dk):
    assert fr.dk_player_id.is_unique and dk.dk_player_id.is_unique
    assert set(fr.dk_player_id)<=set(dk.dk_player_id),'missing fresh DK identity'
    latest=dk.set_index('dk_player_id').loc[fr.dk_player_id]
    for name in ('salary','dk_draftable_id','position'):
        assert np.array_equal(latest[name].to_numpy(),fr[name].to_numpy()),name+' changed since build'
    status=latest.status.fillna('').astype(str).str.strip().str.upper()
    assert set(status)<=ALLOWED_STATUSES,'unknown DK status; no inferred removal'
    inactive=status.isin(OUT_STATUSES).to_numpy()
    assert latest.loc[~inactive,'dk_disabled'].eq(False).all(),'retained player is disabled'
    assert latest.loc[~inactive,'dk_swappable'].eq(True).all(),'retained player is not swappable'
    excluded=set(fr.loc[inactive,'id'])
    keep=[i for i,roster in enumerate(orders) if not (set(roster)&excluded)]
    return keep,sorted(excluded),latest.status.to_numpy()


def reselect(run,capture_root,out,lab_checkout=base.LAB):
    lab_checkout=lab_checkout.resolve()
    runtime_sha=subprocess.check_output(['git','-C',str(lab_checkout),'rev-parse','HEAD'],text=True).strip()
    assert runtime_sha==base.SOURCE
    assert not subprocess.check_output(['git','-C',str(lab_checkout),'status','--porcelain','--untracked-files=all'],text=True).strip()
    sys.path.insert(0,str(lab_checkout/'src'))
    import nfl2
    assert Path(nfl2.__file__).resolve().is_relative_to(lab_checkout/'src'),'wrong imported lab checkout'
    assert not out.exists();rec=json.loads((run/'receipt.json').read_text());cfg=rec['config']
    assert rec['identity']['sha']==base.SOURCE and not rec['identity']['dirty']
    assert (rec['season'],rec['week'],rec['draft_group'])==(2026,2,153428)
    assert cfg['selector']=='dual_emax' and cfg['seed']==2026 and cfg['sims']==10000
    assert cfg['operational_k']==rec['written']==97
    dk,cap=load_capture(capture_root)
    assert pd.Timestamp(rec['built_utc'])<=pd.Timestamp(cap['received_at'])<pd.Timestamp(rec['lock_utc'])
    fr=pd.read_parquet(run/'frame.parquet',columns=base.FRAME_COLUMNS)
    cands=pd.read_parquet(run/'candidates.parquet',columns=['cand','players','names','book_rank','sel_mean'])
    assert len(cands)==rec['candidates'] and cands.cand.tolist()==list(range(len(cands)))
    assert fr.id.is_unique and cands.players.is_unique
    orders=base.candidate_orders(fr,cands);index={x:i for i,x in enumerate(fr.id)}
    roster=np.asarray([[index[x] for x in order] for order in orders],int)
    keep,excluded,status=eligible_candidates(fr,orders,dk);assert len(keep)>=97,'insufficient eligible saved candidates'
    banks={}
    for component,key in [('I','incumbent_player_scores'),('H','corrected_hsim_player_scores')]:
        p=run/(key+'.npy');identity=rec['a5_sidecars'][key]
        assert base.sha(p)==identity['sha256'] and p.stat().st_size==identity['bytes']
        bank=np.load(p,allow_pickle=False)
        assert list(bank.shape)==identity['shape']==[len(fr),10000] and str(bank.dtype)==identity['dtype']=='float32'
        assert np.isfinite(bank).all();banks[component]=bank
    totals=base.totals(banks,roster);original=base.greedy(totals,97)
    assert original==cands[cands.book_rank.notna()].sort_values('book_rank').index.tolist()
    assert np.array_equal(totals[:,:10000].mean(axis=1),cands.sel_mean.to_numpy())
    book=[keep[i] for i in base.greedy(totals[keep],97)]
    from nfl2.validator import validate_roster
    full=pd.read_parquet(run/'frame.parquet').set_index('id');args=[full[k].to_dict() for k in ('pos','team','opp','salary')]
    assert len(set(book))==97
    for i in book:
        assert not validate_roster(orders[i],*args,salary_floor=49000,qb_stack_min=2,
            bring_back_min=1,forbid_rb_vs_dst=True,forbid_two_rb_same_team=True)
    # Reselect may take minutes at full dose; require the source still fresh
    # and every game still unlocked immediately before any output is written.
    load_capture(capture_root)
    out.mkdir(parents=True);fr['status']=status;fr.to_parquet(out/'frame.parquet',index=False)
    from nfl2.live import dk_csv
    assert dk_csv([SimpleNamespace(players=[{'id':x} for x in orders[i]]) for i in book],fr,out/'book.csv')==97
    result=dict(schema='prelock-dk-reselection/v1',disposition='RESEARCH_PREVIEW_NOT_ENTERED',
        source_run=str(run),source_sha=base.SOURCE,source_receipt_sha256=base.sha(run/'receipt.json'),
        source_artifacts={p:base.sha(run/p) for p in ('frame.parquet','candidates.parquet','book.csv',
            'incumbent_player_scores.npy','corrected_hsim_player_scores.npy')},
        capture_receipt_sha256=base.sha(capture_root/'receipt.json'),capture=cap,
        producer_sha256=base.sha(__file__),selector_helper_sha256=base.sha(HELPER),
        runtime_lab_checkout=str(lab_checkout),runtime_lab_sha=runtime_sha,runtime_lab_clean=True,
        source_control_exact=True,unchanged_objective='ordinary dual_emax',source_candidates=len(cands),
        eligible_candidates=len(keep),excluded_players=excluded,book_indices=book,entries=97,
        shared_members=len(set(book)&set(original)),all_books_legal=True,official_active_inference=False,
        current_scoring_outcomes_read=False,
        limits='Before first lock only; same saved forecasts/candidates, no teammate redistribution, no official-active inference, no entry upload')
    write(out/'receipt.json',result);print('ORDINARY_DK_RESELECTION_PREVIEW_VERIFIED',len(keep),excluded,flush=True)


if __name__=='__main__':
    sys.path.insert(0,str(base.REPO/'src'))
    ap=argparse.ArgumentParser();subs=ap.add_subparsers(dest='mode',required=True)
    cap=subs.add_parser('capture');cap.add_argument('output',type=Path)
    sel=subs.add_parser('reselect');sel.add_argument('--run',type=Path,required=True)
    sel.add_argument('--capture',type=Path,required=True);sel.add_argument('--output',type=Path,required=True)
    sel.add_argument('--lab-checkout',type=Path,default=base.LAB)
    a=ap.parse_args()
    if a.mode=='capture':capture(a.output)
    else:reselect(a.run,a.capture,a.output,a.lab_checkout)
