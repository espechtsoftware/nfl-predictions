"""Read-only release/rollback inventory; never reads table contents or updates jobs."""
import concurrent.futures
import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import bigquery

PROJECT='nfl-predictions-503414'
SOURCE=Path('/home/erich/projects/.nfl-predictions-worktrees/salary-week-resolution')
parser=argparse.ArgumentParser()
parser.add_argument('--out',default=str(Path(__file__).with_suffix('.json')))
parser.add_argument('--private-root',default='/home/erich/projects/review-evidence/overnight-20260918/release-inventory')
args=parser.parse_args()
OUT=Path(args.out)
PRIVATE=Path(args.private_root)
assert not OUT.exists() and not PRIVATE.exists();PRIVATE.mkdir(mode=0o700)
client=bigquery.Client(project=PROJECT)
names={};views={}
for path in sorted((SOURCE/'sql/features').glob('*.sql')):
    for kind,name in re.findall(r'CREATE\s+(?:OR REPLACE\s+)?(TABLE|VIEW)\s+(?:IF NOT EXISTS\s+)?`\$\{features\}\.([a-z_0-9]+)`',path.read_text()):
        dest=f'{PROJECT}.nfl_features.{name}'
        (views if kind=='VIEW' else names).setdefault(dest,[]).append(path.name)
names[f'{PROJECT}.nfl_features.tabpfn_projections']=['tabpfn-gen']
names[f'{PROJECT}.nfl_predictions.player_projections']=['project-slate']
names[f'{PROJECT}.nfl_predictions.div_shadow']=['optional projection shadow consumer']

def metadata(item):
    table,source=item
    try:t=client.get_table(table)
    except Exception as e:
        if getattr(e,'code',None)==404:return table,dict(exists=False,source=source)
        raise
    return table,dict(exists=True,source=source,kind=t.table_type,location=t.location,rows=t.num_rows,
        bytes=t.num_bytes,etag=t.etag,modified=t.modified.isoformat(),
        schema_sha256=hashlib.sha256(json.dumps([f.to_api_repr() for f in t.schema],sort_keys=True).encode()).hexdigest(),
        partitioning=t.time_partitioning.to_api_repr() if t.time_partitioning else None,
        clustering=t.clustering_fields,view_query=t.view_query if t.table_type=='VIEW' else None)

with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    tables=dict(pool.map(metadata,list(names.items())+list(views.items())))
creds,_=google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
session=AuthorizedSession(creds);jobs={}
for name in ('build-features','tabpfn-gen','project-slate'):
    r=session.get(f'https://run.googleapis.com/v2/projects/{PROJECT}/locations/us-central1/jobs/{name}',timeout=30)
    r.raise_for_status();value=r.json();path=PRIVATE/(name+'-private.json')
    with path.open('x') as f:
        os.chmod(path,0o600);json.dump(value,f,indent=2)
    c=value['template']['template']['containers'][0]
    jobs[name]=dict(image=c['image'],command=c.get('command'),args=c.get('args'),
        environment_names=sorted(x['name'] for x in c.get('env',[])),etag=value['etag'],
        template_sha256=hashlib.sha256(json.dumps(value['template'],sort_keys=True).encode()).hexdigest(),
        private_config_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
result=dict(checked_at=datetime.now(timezone.utc).isoformat(),tables=tables,jobs=jobs,
            sql_source='0db37c09',scope='read-only metadata; no table contents, job updates or snapshots created')
with OUT.open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(dict(table_objects=len(names),view_objects=len(views),existing_tables=sum(v['exists'] and v['kind']!='VIEW' for v in tables.values()),jobs={k:v['image'] for k,v in jobs.items()}),indent=2))
