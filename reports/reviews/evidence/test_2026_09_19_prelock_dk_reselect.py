"""Fresh DK status and prelock boundaries, including slot-variant ambiguity."""
import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

SOURCE=Path(__file__).with_name('2026-09-19-prelock-dk-reselect.py')
spec=importlib.util.spec_from_file_location('prelock_dk_reselection_test',SOURCE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sys.path.insert(0,str(m.base.REPO/'src'))


def payload():
    comps=[dict(competitionId=i,sportId=1,competitionState='Upcoming',competitionStartedEarly=False,
        startTime=m.LOCK.isoformat()) for i in range(13)]
    rows=[dict(playerId=i,draftableId=100+i,displayName=f'Player {i}',position='WR',
        teamAbbreviation='A',salary=5000,status=status,isDisabled=False,isSwappable=True,
        competition={'competitionId':0},rosterSlotId=3) for i,status in enumerate(['Q','D','OUT'])]
    rows.append({**rows[0],'draftableId':200,'rosterSlotId':7})
    return dict(errorStatus={},competitions=comps,draftables=rows)


def fixture():
    dk=m.normalized(payload(),m.LOCK-pd.Timedelta(hours=2))
    fr=dk[['dk_player_id','dk_draftable_id','salary','position']].copy();fr['id']=['a','b','c']
    return fr,dk


def test_only_confirmed_dk_out_is_excluded_and_q_d_remain():
    fr,dk=fixture();keep,excluded,_=m.eligible_candidates(fr,[['a','b'],['a','c'],['b','c']],dk)
    assert keep==[0] and excluded==['c']
    assert dk.dk_draftable_id.tolist()==[100,101,102], 'keep the existing client slot identity'


@pytest.mark.parametrize('bad',['status_conflict','salary_conflict','wrong_sport','started_early','started_game','missing_game'])
def test_ambiguous_or_nonfuture_capture_refuses(bad):
    p=payload()
    if bad=='status_conflict':p['draftables'][-1]['status']='OUT'
    if bad=='salary_conflict':p['draftables'][-1]['salary']=6000
    if bad=='wrong_sport':p['competitions'][0]['sportId']=2
    if bad=='started_early':p['competitions'][0]['competitionStartedEarly']=True
    if bad=='started_game':p['competitions'][0]['competitionState']='InProgress'
    if bad=='missing_game':p['competitions'].pop()
    with pytest.raises(AssertionError):m.normalized(p,m.LOCK-pd.Timedelta(hours=2))


@pytest.mark.parametrize('bad',['missing','salary','draftable','position','unknown','disabled','unswappable'])
def test_changed_candidate_eligibility_identity_refuses(bad):
    fr,dk=fixture()
    if bad=='missing':dk=dk.iloc[:2]
    if bad=='salary':dk.loc[0,'salary']=5100
    if bad=='draftable':dk.loc[0,'dk_draftable_id']=999
    if bad=='position':dk.loc[0,'position']='TE'
    if bad=='unknown':dk.loc[0,'status']='PUP'
    if bad=='disabled':dk.loc[0,'dk_disabled']=True
    if bad=='unswappable':dk.loc[0,'dk_swappable']=False
    with pytest.raises(AssertionError):m.eligible_candidates(fr,[['a','b']],dk)


def saved(tmp_path):
    at=pd.Timestamp('2026-09-20T15:50:00Z');p=payload()
    (tmp_path/'source.json').write_text(json.dumps(p));f=m.normalized(p,at);f.to_parquet(tmp_path/'dk.parquet',index=False)
    r=dict(schema='prelock-dk-capture/v1',uri=m.URI,season=2026,week=2,draft_group=153428,
        started_at=str(at-pd.Timedelta(seconds=1)),received_at=str(at),response_date='Sun, 20 Sep 2026 15:50:00 GMT',
        source_bytes=(tmp_path/'source.json').stat().st_size,source_sha256=m.base.sha(tmp_path/'source.json'),
        frame_sha256=m.base.sha(tmp_path/'dk.parquet'),rows=len(f))
    m.write(tmp_path/'receipt.json',r);return at


def test_raw_bytes_and_normalized_rows_reopen_exactly(tmp_path):
    at=saved(tmp_path);f,_=m.load_capture(tmp_path,at)
    assert len(f)==3


@pytest.mark.parametrize('bad',['stale','future','changed_bytes','changed_frame','locked'])
def test_temporal_and_artifact_refusal(tmp_path,bad):
    at=saved(tmp_path);checked=at
    if bad=='stale':checked=at+pd.Timedelta(seconds=601)
    if bad=='future':checked=at-pd.Timedelta(seconds=1)
    if bad=='changed_bytes':(tmp_path/'source.json').write_text('{}')
    if bad=='changed_frame':(tmp_path/'dk.parquet').write_bytes(b'changed')
    if bad=='locked':
        # Move the use clock just after a lock without making the capture stale.
        original=m.LOCK;m.LOCK=at+pd.Timedelta(minutes=5);checked=m.LOCK
        try:
            with pytest.raises(AssertionError):m.load_capture(tmp_path,checked)
        finally:m.LOCK=original
        return
    with pytest.raises(AssertionError):m.load_capture(tmp_path,checked)
