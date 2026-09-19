"""Fixed release actions under three registry lanes, with reviewed checkpoints.

Never retries a mutation. An error retains exact claims/logs and stops for
provider reconciliation. Checkpoint files authorize only the fixed next action;
they do not contain executable commands. No workstation/timer changes.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime, timezone

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).parent
OUT = Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')
RESUME = OUT.parent/'authorized-release-v1'
STATE = Path('/home/erich/.local/state/nfl-dfs/lab-launcher-registry')
PROJECT = 'nfl-predictions-503414'
BASE = f'https://run.googleapis.com/v2/projects/{PROJECT}/locations/us-central1/jobs/'
JOBS = ('build-features', 'tabpfn-gen', 'project-slate')
BEFORE = {
 'build-features':'us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:cdbf96ad190925b2c96a94568f173c4bded328442441838427fa473d2fd450b2',
 'tabpfn-gen':'us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/tabpfn-gen@sha256:7eeff44e7c225fed62682b3649dfa86d77f86227e3e9858c967d132deff2a10a',
}
AFTER = {
 'build-features':'us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:8d9b3cb55865edc66c99e01b28a7a6ba0d588458ac921c1485069fac32814e03',
 'tabpfn-gen':'us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/tabpfn-gen@sha256:fdb120dc2291b7d09538987d97e8b30d0e8fe5f7e9d9d40995b6adcc4d4692d6',
}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()
def save(path, value):
    with Path(path).open('x') as f:
        os.chmod(path, 0o600)
        json.dump(value, f, indent=2, default=str, allow_nan=False)

def template_without_image(value):
    value=copy.deepcopy(value['template'])
    # gcloud writes its own version as execution-template client metadata.
    # This is outside the actual task template; preserve/receipt both versions.
    value.pop('clientVersion',None)
    assert len(value['template']['containers']) == 1
    del value['template']['containers'][0]['image']
    return value

def completed(e):
    return bool(e.get('completionTime')) or any(c.get('type')=='Completed' and
        c.get('state') in ('CONDITION_SUCCEEDED','CONDITION_FAILED') for c in e.get('conditions',[]))

def require_lanes():
    ancestors=set(); pid=os.getpid()
    while pid>1:
        ancestors.add(pid)
        stat=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        pid=int(stat[1])
    receipts=[]
    for path in (STATE/'launchers').glob('*.json'):
        r=json.loads(path.read_text())
        if r['lane'] in JOBS:
            assert r['pid'] in ancestors and r['owner']=='production'
            assert r['target_run_id_prefixes']==['input-repair-20260919']
            actual=Path(f"/proc/{r['pid']}/stat").read_text().rsplit(')',1)[1].split()
            assert int(actual[19])==r['process_start_ticks']
            receipts.append(dict(path=str(path),sha256=sha(path),**r))
    assert sorted(r['lane'] for r in receipts)==sorted(JOBS)
    return receipts

class Release:
    def __init__(self):
        self.session=AuthorizedSession(google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])[0])
        self.bq=bigquery.Client(project=PROJECT)
        self.plan=json.loads((EVIDENCE/'2026-09-19-release-plan.json').read_text())
        self.before={}

    def get(self,url,params=None):
        r=self.session.get(url,params=params,timeout=60);r.raise_for_status();return r.json()

    def census(self,label):
        result={}
        for name in JOBS:
            records=[];token=None
            while True:
                p={'pageSize':100}
                if token:p['pageToken']=token
                value=self.get(BASE+name+'/executions',p)
                records.extend(value.get('executions',[]));token=value.get('nextPageToken')
                if not token:break
            result[name]=[dict(name=e['name'],createTime=e.get('createTime'),completionTime=e.get('completionTime'),
                conditions=e.get('conditions'),succeededCount=e.get('succeededCount'),taskCount=e.get('taskCount')) for e in records]
        save(OUT/(label+'-provider.json'),dict(at=now(),jobs=result))
        active=[e['name'] for rows in result.values() for e in rows if not completed(e)]
        assert not active,active
        return {name:{e['name'] for e in rows} for name,rows in result.items()}

    def command(self,label,args):
        save(OUT/(label+'-claim.json'),dict(at=now(),args=args))
        with (OUT/(label+'-stdout-private.json')).open('xb') as out, (OUT/(label+'-stderr.log')).open('xb') as err:
            p=subprocess.run(args,stdout=out,stderr=err)
        save(OUT/(label+'-return.json'),dict(at=now(),returncode=p.returncode))
        assert p.returncode==0, f'{label} returned {p.returncode}; reconcile provider before any retry'
        return json.loads((OUT/(label+'-stdout-private.json')).read_text())

    def table_meta(self,name):
        t=self.bq.get_table(name)
        return dict(name=name,kind=t.table_type,rows=t.num_rows,modified=t.modified.isoformat(),etag=t.etag,
          schema=[f.to_api_repr() for f in t.schema],partitioning=t.time_partitioning.to_api_repr() if t.time_partitioning else None,
          range_partitioning=t.range_partitioning.to_api_repr() if t.range_partitioning else None,clustering=t.clustering_fields,
          snapshot=t.to_api_repr().get('snapshotDefinition'),view_query=t.view_query if t.table_type=='VIEW' else None)

    def backups(self):
        self.census('before-backup')
        if RESUME.exists():
            old=json.loads((RESUME/'backup-result.json').read_text())
            assert old['verified_count']==36 and old['source_metadata_unchanged']
            assert sha(RESUME/'backup-result.json')=='9fca91e9ca04e7046513da98574053f058ba2471d3973a22b5e1c46048856ef3'
            original=json.loads((RESUME/'before-tables-private.json').read_text())
            for rec in self.plan['tables']:
                snap=self.table_meta(rec['snapshot']);assert snap==old['tables'][rec['snapshot']]
                live=self.table_meta(rec['source']);assert live==original[rec['source']]
            for name,view in old['views'].items():assert self.table_meta(name)==view
            for name in JOBS:
                baseline=json.loads((RESUME/(name+'-before-private.json')).read_text())
                current=self.get(BASE+name)
                if name=='build-features':
                    stopped=json.loads((RESUME/'build-features-after-stop-private.json').read_text())
                    assert current['template']==stopped['template']
                    assert current['template']['template']['containers'][0]['image']==AFTER[name]
                    assert template_without_image(current)==template_without_image(baseline)
                else: assert current['template']==baseline['template']
                self.before[name]=baseline
                save(OUT/(name+'-before-private.json'),baseline)
            save(OUT/'backup-result.json',dict(**old,reused_from=str(RESUME/'backup-result.json'),reverified_at=now(),
                original_sha256=sha(RESUME/'backup-result.json')))
            print('EXISTING_BACKUPS_REVERIFIED',36,flush=True)
            return
        for name in JOBS:
            value=self.get(BASE+name);save(OUT/(name+'-before-private.json'),value);self.before[name]=value
            if name in BEFORE: assert value['template']['template']['containers'][0]['image']==BEFORE[name]
        reference=json.loads((EVIDENCE/'2026-09-19-release-inventory-refresh.json').read_text())
        for name,value in self.before.items():
            assert hashlib.sha256(json.dumps(value['template'],sort_keys=True).encode()).hexdigest()==reference['jobs'][name]['template_sha256']
        source={r['source']:self.table_meta(r['source']) for r in self.plan['tables']}
        views={name:self.table_meta(name) for name,r in reference['tables'].items() if r['kind']=='VIEW'}
        assert len(source)==36 and len(views)==1
        for r in self.plan['tables']:
            assert hashlib.sha256(json.dumps(source[r['source']]['schema'],sort_keys=True).encode()).hexdigest()==r['expected_schema_sha256']
        save(OUT/'before-tables-private.json',source);save(OUT/'before-views.json',views)
        sql=(EVIDENCE/'2026-09-19-release-snapshot.sql').read_text()
        save(OUT/'backup-claim.json',dict(at=now(),sql_sha256=sha(EVIDENCE/'2026-09-19-release-snapshot.sql')))
        job=self.bq.query(sql,location='US',job_id_prefix='input_repair_20260919_backup_',job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
        save(OUT/'backup-job.json',dict(job_id=job.job_id,project=job.project,location=job.location))
        timestamps=[str(dict(row)['release_snapshot_ts']) for row in job.result(timeout=1800)]
        snapshots={};ts=set()
        for r in self.plan['tables']:
            s=self.table_meta(r['snapshot']);a=source[r['source']]
            assert s['kind']=='SNAPSHOT' and s['snapshot']
            assert all(s[k]==a[k] for k in ('schema','rows','partitioning','range_partitioning','clustering')),(r['source'],s['rows'],a['rows'])
            base=s['snapshot']['baseTableReference']; assert '.'.join(base[k] for k in ('projectId','datasetId','tableId'))==r['source']
            ts.add(s['snapshot']['snapshotTime']);snapshots[r['snapshot']]=s
            after=self.table_meta(r['source']);assert after['etag']==a['etag'],r['source']
        assert len(ts)==1 and len(timestamps)==1
        save(OUT/'backup-result.json',dict(at=now(),query_job=job.job_id,snapshot_times=sorted(ts),sql_timestamp=timestamps,
          tables=snapshots,views=views,verified_count=len(snapshots),source_metadata_unchanged=True))
        print('BACKUPS_VERIFIED',len(snapshots),flush=True)

    def gate(self,next_stage,previous):
        expected=sha(OUT/previous)
        print('AWAIT_REVIEW',next_stage,expected,flush=True)
        deadline=time.monotonic()+7200
        p=OUT/('continue-'+next_stage+'.json')
        while not p.exists():
            if (OUT/'STOP').exists():raise RuntimeError('supervisor stop requested')
            assert time.monotonic()<deadline,'review checkpoint timed out'
            time.sleep(5)
        value=json.loads(p.read_text());assert value['previous_sha256']==expected and value['stage']==next_stage
        require_lanes()

    def refresh(self,name):
        before_names=self.census('before-'+name)
        current=self.get(BASE+name)
        already_applied=name=='build-features' and RESUME.exists()
        if already_applied:
            assert current['template']==json.loads((RESUME/'build-features-after-stop-private.json').read_text())['template']
        else:assert current['template']==self.before[name]['template'],'template changed before own update'
        if name in AFTER and not already_applied:
            self.command(name+'-update',['gcloud','run','jobs','update',name,'--project='+PROJECT,'--region=us-central1','--image='+AFTER[name],'--format=json'])
        installed=self.get(BASE+name)
        assert template_without_image(installed)==template_without_image(self.before[name])
        image=installed['template']['template']['containers'][0]['image']
        assert image==(AFTER.get(name) or self.before[name]['template']['template']['containers'][0]['image'])
        save(OUT/(name+'-installed-private.json'),installed)
        args=['gcloud','run','jobs','execute',name,'--project='+PROJECT,'--region=us-central1','--wait','--format=json']
        if name=='tabpfn-gen':args.append('--update-env-vars=TABPFN_UPCOMING=2026:2')
        result=self.command(name+'-execute',args)
        execution_name=result.get('name') or result.get('metadata',{}).get('name')
        assert execution_name,'no exact provider identity; reconcile before proceeding'
        execution_name=execution_name.split('/')[-1]
        actual=self.get(BASE+name+'/executions/'+execution_name)
        assert actual['name'] not in before_names[name]
        assert completed(actual) and int(actual.get('succeededCount',0))==int(actual['taskCount'])
        assert not actual.get('failedCount',0) and not actual.get('cancelledCount',0)
        assert any(c['type']=='Completed' and c['state']=='CONDITION_SUCCEEDED' for c in actual.get('conditions',[]))
        assert self.get(BASE+name)['template']==installed['template'],'template drift during execution'
        save(OUT/(name+'-result.json'),dict(at=now(),execution=actual['name'],completionTime=actual.get('completionTime'),
          succeededCount=actual.get('succeededCount'),taskCount=actual['taskCount'],image=image,only_image_changed=True,
          client_version_before=self.before[name]['template'].get('clientVersion'),client_version_after=installed['template'].get('clientVersion'),
          image_update_already_applied=already_applied,
          execution_receipt=actual))
        print('REFRESH_COMPLETE',name,actual['name'],flush=True)

def main():
    OUT.mkdir(mode=0o700,exist_ok=False)
    try:
        save(OUT/'launch.json',dict(at=now(),source_sha256=sha(__file__),lanes=require_lanes(),
             authorization_handoff='nfl2 cef83e8677946278402c021c5ae3d6d001b40565'))
        r=Release();r.backups();r.gate('build-features','backup-result.json')
        r.refresh('build-features');r.gate('tabpfn-gen','build-features-result.json')
        r.refresh('tabpfn-gen');r.gate('project-slate','tabpfn-gen-result.json')
        r.refresh('project-slate');r.gate('finish','project-slate-result.json')
        r.census('finished');save(OUT/'complete.json',dict(at=now(),scope='cloud refresh; host activation separate'))
    except BaseException as exc:
        save(OUT/'stopped.json',dict(at=now(),error=str(exc),reconciliation_required=True))
        raise

if __name__=='__main__':main()
