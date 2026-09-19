"""New provider-bound Week2 status capture; read-only sources, no outcomes.

Retain actual published injury bytes and HTTP publication metadata. Normalize
only designation/practice identity fields; DK comes from an exact-group,
time-travel warehouse capture. No retroactive certification of older captures.
"""
import argparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import requests
from google.cloud import bigquery

URI='https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.parquet'
FIELDS=['season','week','team','gsis_id','report_status','practice_status']
SCHEMA='participation-provider-capture/v2'
LOCK=pd.Timestamp('2026-09-20T17:00:00Z')


def now():return pd.Timestamp(datetime.now(timezone.utc))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,r):
    with Path(p).open('x') as f:json.dump(r,f,indent=2,default=str,allow_nan=False)


def normalize(data,received):
    raw=pd.read_parquet(io.BytesIO(data))
    fr=raw[(raw.season==2026)&(raw.week==2)&(raw.game_type=='REG')][FIELDS].copy()
    assert len(fr)>0 and fr.gsis_id.notna().all() and fr.gsis_id.is_unique
    assert set(fr.report_status.dropna())<= {'Questionable','Doubtful','Out'}
    assert set(fr.practice_status.dropna())<= {'Did Not Participate In Practice',
        'Limited Participation in Practice','Full Participation in Practice'}
    fr=fr.sort_values('gsis_id').reset_index(drop=True)
    fr['pulled_at']=received
    return fr


def provider_times(p,cutoff):
    assert p['uri']==URI
    start=pd.Timestamp(p['started_at']);received=pd.Timestamp(p['received_at'])
    modified=pd.Timestamp(parsedate_to_datetime(p['headers']['Last-Modified']))
    server=pd.Timestamp(parsedate_to_datetime(p['headers']['Date']))
    assert all(t.tzinfo is not None for t in (start,received,modified,server,cutoff))
    assert modified<=received<=cutoff<LOCK and start<=received
    assert 0 <= (cutoff-modified).total_seconds() <= 86400,'provider object stale/future'
    assert abs((server-received).total_seconds())<=300,'provider/collector clocks differ'
    assert p['headers']['ETag'] and p['bytes']>0
    return received,modified


def load_capture(root,as_of=None):
    root=Path(root);r=json.loads((root/'capture.json').read_text())
    assert r['schema']==SCHEMA and (r['season'],r['week'],r['draft_group'])==(2026,2,153428)
    cutoff=pd.Timestamp(r['cutoff']);observed=now() if as_of is None else pd.Timestamp(as_of)
    assert observed.tzinfo and cutoff.tzinfo and 0<=(observed-cutoff).total_seconds()<=3600
    assert observed<LOCK,'slate has locked'
    received,modified=provider_times(r['provider'],cutoff)
    assert (observed-modified).total_seconds()<=86400,'provider object aged out since capture'
    for row in [r['provider'],*r['captures']]:
        p=root/row['file'];assert p.parent==root and p.is_file()
        assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],'source bytes changed'
    rows={x['name']:x for x in r['captures']};assert set(rows)=={'injury_snapshots','dk_salaries'}
    inj=pd.read_parquet(root/rows['injury_snapshots']['file'])
    expected=normalize((root/r['provider']['file']).read_bytes(),received)
    pd.testing.assert_frame_equal(inj,expected,check_exact=True)
    dk=pd.read_parquet(root/rows['dk_salaries']['file'])
    assert len(inj)==rows['injury_snapshots']['rows'] and len(dk)==rows['dk_salaries']['rows']
    assert len(dk)>0 and dk.dk_player_id.is_unique and dk.pulled_at.nunique()==1
    assert set(dk.season)=={2026} and set(dk.draft_group_id)=={153428}
    assert cutoff<dk.game_start.min() and dk.game_start.min()==LOCK
    assert (dk.game_start< pd.Timestamp('2026-09-21T00:00:00Z')).all()
    assert 0<=(cutoff-dk.pulled_at.iloc[0]).total_seconds()<=3600,'DK source stale/future'
    assert (observed-dk.pulled_at.iloc[0]).total_seconds()<=3600,'DK source aged out since capture'
    return inj,dk,cutoff,r


def capture(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    start=now();response=requests.get(URI,timeout=90);response.raise_for_status();received=now()
    path=root/'provider-injuries.parquet';path.write_bytes(response.content)
    provider=dict(uri=URI,file=path.name,started_at=str(start),received_at=str(received),
        headers={k:response.headers.get(k) for k in ('Last-Modified','Date','ETag','Content-Type')},
        bytes=path.stat().st_size,sha256=sha(path))
    write(root/'provider-receipt.json',provider)
    cutoff=now();provider_times(provider,cutoff)
    inj=normalize(response.content,received)
    sql='''SELECT pulled_at,season,week,draft_group_id,dk_player_id,dk_draftable_id,
        display_name,team_abbr,position,salary,status,game_start
        FROM `nfl-predictions-503414.nfl_raw.dk_salaries` FOR SYSTEM_TIME AS OF @cutoff
        WHERE season=2026 AND draft_group_id=153428 AND pulled_at<=@cutoff
        AND pulled_at=(SELECT MAX(pulled_at) FROM `nfl-predictions-503414.nfl_raw.dk_salaries`
          FOR SYSTEM_TIME AS OF @cutoff WHERE season=2026 AND draft_group_id=153428 AND pulled_at<=@cutoff)'''
    client=bigquery.Client(project='nfl-predictions-503414')
    cfg=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000,
        query_parameters=[bigquery.ScalarQueryParameter('cutoff','TIMESTAMP',cutoff.to_pydatetime())])
    job=client.query(sql,job_config=cfg);dk=job.result(timeout=180).to_dataframe()
    captures=[]
    for name,fr in [('injury_snapshots',inj),('dk_salaries',dk)]:
        p=root/(name+'.parquet');fr.to_parquet(p,index=False)
        captures.append(dict(name=name,file=p.name,bytes=p.stat().st_size,sha256=sha(p),rows=len(fr)))
    receipt=dict(schema=SCHEMA,season=2026,week=2,draft_group=153428,cutoff=str(cutoff),
        producer_sha256=sha(__file__),provider=provider,captures=captures,
        dk_query=dict(sql=sql,job_id=job.job_id,bytes_processed=job.total_bytes_processed),
        injury_provenance='actual provider object and HTTP snapshot publication time; no per-row publication date claimed',
        dk_provenance='exact-group as-of warehouse collector snapshot; no DK provider publication date claimed',
        football_outcomes_read=False)
    write(root/'capture.json',receipt);load_capture(root)
    print(json.dumps(dict(status='VERIFIED',cutoff=str(cutoff),rows={x['name']:x['rows'] for x in captures},
        capture_sha256=sha(root/'capture.json'),provider=provider),indent=2),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);a=ap.parse_args();capture(a.output)
