"""Behavioral guards for an optional research adapter, including late active news."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

SOURCE=Path(__file__).with_name('2026-09-19-participation-reselect.py')
spec=importlib.util.spec_from_file_location('reselector_candidate',SOURCE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sys.path.insert(0,str(m.LAB/'src'))
from nfl2.selectors import select_expected_max


def fixture():
    at=pd.Timestamp('2026-09-20T15:50:00Z')
    fr=pd.DataFrame(dict(id=['a','b'],gsis_id=['a','b'],dk_player_id=[1,2],draft_group_id=[153428]*2,display_name=['A','B']))
    inj=pd.DataFrame(dict(gsis_id=['a'],pulled_at=[at-pd.Timedelta(hours=5)],report_status=['Questionable'],practice_status=['Full Participation in Practice']))
    dk=pd.DataFrame(dict(dk_player_id=[1,2],draft_group_id=[153428]*2,pulled_at=[at-pd.Timedelta(minutes=5)]*2,status=['Q','None'],game_start=[at+pd.Timedelta(minutes=70)]*2))
    mp={'p_active':{'Questionable|2':.735}}
    confirmation=dict(schema='official-participation-confirmation/v1',observed_at=str(at-pd.Timedelta(minutes=5)),
        source_uri='https://example.test/official-roster',source_sha256='a'*64,season=2026,week=2,draft_group_id=153428,
        players=[{'player_id':'a','state':'active'}])
    return fr,inj,dk,at,mp,confirmation


@pytest.mark.parametrize('chunk',[1,7,128])
def test_chunked_greedy_exact_with_ties_and_near_ties(chunk):
    t=np.random.default_rng(77).normal(120,30,(157,503)).astype(np.float32)
    t[2]=t[1];t[5]=np.nextafter(t[4],np.float32(np.inf))
    assert m.greedy(t,97,chunk)==select_expected_max(t,97)


def test_full_tie_keeps_candidate_order():
    assert m.greedy(np.full((110,8),125,dtype=np.float32),97)==list(range(97))


@pytest.mark.parametrize('state',['active','inactive'])
def test_official_state_replaces_designation_prior(state):
    fr,inj,dk,at,mp,c=fixture();c['players'][0]['state']=state
    p,excluded,r=m.participation(fr,inj,dk,at,mp,c)
    assert p.tolist()==([1.,1.] if state=='active' else [0.,1.])
    assert excluded==(set() if state=='active' else {'a'})
    assert r[0]['official_state']==state


def test_late_questionable_cannot_be_treated_as_unknown():
    fr,inj,dk,at,mp,_=fixture()
    with pytest.raises(AssertionError,match='confirmation required'):m.participation(fr,inj,dk,at,mp)


def test_early_unknown_uses_fixed_map():
    fr,inj,dk,at,mp,_=fixture();dk['game_start']+=pd.Timedelta(hours=6)
    p,excluded,_=m.participation(fr,inj,dk,at,mp)
    assert p.tolist()==[.735,1.] and not excluded


@pytest.mark.parametrize('corruption',['future','stale','unknown_state','duplicate','other_week','bad_sha','conflicting_out','missing_dk','stale_dk','unknown_practice'])
def test_unsafe_status_inputs_refuse(corruption):
    fr,inj,dk,at,mp,c=fixture()
    if corruption=='future':c['observed_at']=str(at+pd.Timedelta(seconds=1))
    if corruption=='stale':c['observed_at']=str(at-pd.Timedelta(hours=2))
    if corruption=='unknown_state':c['players'][0]['state']='likely'
    if corruption=='duplicate':c['players']*=2
    if corruption=='other_week':c['week']=1
    if corruption=='bad_sha':c['source_sha256']='z'*64
    if corruption=='conflicting_out':dk.loc[0,'status']='OUT'
    if corruption=='missing_dk':dk=dk.iloc[:1].copy()
    if corruption=='stale_dk':dk['pulled_at']-=pd.Timedelta(hours=2)
    if corruption=='unknown_practice':inj.loc[0,'practice_status']='unknown'
    with pytest.raises(AssertionError):m.participation(fr,inj,dk,at,mp,c)


def test_candidate_order_recovers_names_not_sorted_ids():
    fr=pd.DataFrame({'id':[str(x) for x in range(9)],'name':[f'p{x}' for x in range(9)]})
    c=pd.DataFrame({'players':[','.join(fr.id)],'names':['|'.join(reversed(fr.name))]})
    assert m.candidate_orders(fr,c)==[list(reversed(fr.id))]
    fr.loc[1,'name']='p0'
    with pytest.raises(AssertionError):m.candidate_orders(fr,c)
