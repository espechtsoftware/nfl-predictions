"""Source-authentication and temporal tests for the new status capture."""
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

SOURCE=Path(__file__).with_name('2026-09-19-participation-provider-capture.py')
spec=importlib.util.spec_from_file_location('provider_capture_test',SOURCE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def fixture(root):
    at=pd.Timestamp('2026-09-19T12:00:00Z')
    raw=pd.DataFrame(dict(season=[2026],week=[2],game_type=['REG'],team=['A'],gsis_id=['a'],
        report_status=['Questionable'],practice_status=['Full Participation in Practice']))
    p=root/'source.parquet';raw.to_parquet(p,index=False)
    provider=dict(uri=m.URI,file=p.name,started_at=str(at-pd.Timedelta(seconds=1)),received_at=str(at),
        headers={'Last-Modified':'Sat, 19 Sep 2026 11:54:00 GMT','Date':'Sat, 19 Sep 2026 12:00:00 GMT','ETag':'test'},
        bytes=p.stat().st_size,sha256=m.sha(p))
    inj=m.normalize(p.read_bytes(),at)
    dk=pd.DataFrame(dict(season=[2026],week=[None],draft_group_id=[153428],dk_player_id=[1],
        pulled_at=[at-pd.Timedelta(minutes=10)],game_start=[m.LOCK],status=['Q']))
    captures=[]
    for name,fr in [('injury_snapshots',inj),('dk_salaries',dk)]:
        p=root/(name+'.parquet');fr.to_parquet(p,index=False)
        captures.append(dict(name=name,file=p.name,bytes=p.stat().st_size,sha256=m.sha(p),rows=len(fr)))
    r=dict(schema=m.SCHEMA,season=2026,week=2,draft_group=153428,cutoff=str(at),provider=provider,captures=captures)
    return at,r


def test_provider_bytes_reconstruct_normalization_and_null_dk_week_is_valid(tmp_path):
    at,r=fixture(tmp_path);m.write(tmp_path/'capture.json',r)
    inj,dk,cutoff,_=m.load_capture(tmp_path,at)
    assert cutoff==at and inj.report_status.tolist()==['Questionable'] and dk.week.isna().all()


def test_fresh_capture_cannot_hide_an_aged_out_dk_snapshot(tmp_path):
    at,r=fixture(tmp_path);m.write(tmp_path/'capture.json',r)
    with pytest.raises(AssertionError,match='aged out since capture'):
        m.load_capture(tmp_path,at+pd.Timedelta(minutes=51))


@pytest.mark.parametrize('bad',['future_publication','stale_publication','future_ingest','wrong_uri',
    'clock_skew','missing_etag','wrong_payload','altered_normalized_status','stale_dk','future_dk','wrong_group','late_cutoff'])
def test_wrong_source_or_timing_refuses(tmp_path,bad):
    at,r=fixture(tmp_path);p=r['provider']
    if bad=='future_publication':p['headers']['Last-Modified']='Sat, 19 Sep 2026 12:01:00 GMT'
    if bad=='stale_publication':p['headers']['Last-Modified']='Thu, 17 Sep 2026 12:00:00 GMT'
    if bad=='future_ingest':p['received_at']=str(at+pd.Timedelta(seconds=1))
    if bad=='wrong_uri':p['uri']='https://example.test/injury.parquet'
    if bad=='clock_skew':p['headers']['Date']='Sat, 19 Sep 2026 11:00:00 GMT'
    if bad=='missing_etag':p['headers']['ETag']=''
    if bad=='wrong_payload':(tmp_path/p['file']).write_bytes(b'not the published bytes')
    if bad in ('altered_normalized_status','stale_dk','future_dk','wrong_group'):
        row=r['captures'][0 if bad=='altered_normalized_status' else 1];path=tmp_path/row['file']
        fr=pd.read_parquet(path)
        if bad=='altered_normalized_status':fr.loc[0,'report_status']='Doubtful'
        if bad=='stale_dk':fr['pulled_at']=[at-pd.Timedelta(hours=2)]
        if bad=='future_dk':fr['pulled_at']=[at+pd.Timedelta(seconds=1)]
        if bad=='wrong_group':fr['draft_group_id']=[153429]
        fr.to_parquet(path,index=False);row['bytes']=path.stat().st_size;row['sha256']=m.sha(path)
    if bad=='late_cutoff':r['cutoff']=str(m.LOCK)
    m.write(tmp_path/'capture.json',r)
    with pytest.raises(AssertionError):m.load_capture(tmp_path,at)
