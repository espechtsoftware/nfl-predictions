"""Fixed refresh preparation/execution. No image updates or mutation retries.

Not scheduled by import or preparation. Execution requires all registry lanes,
the morning clock window, a fresh reviewed host hold and the frozen manifest.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

from google.cloud import bigquery, storage

REPO = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
BASE = Path('/home/erich/projects/review-evidence/overnight-20260918')
OLD = BASE / 'authorized-release-v2'
OUT = BASE / 'morning-refresh-20260919'
MANIFEST = HERE / '2026-09-19-morning-refresh-manifest.json'
PROJECT = 'nfl-predictions-503414'
BUCKET = 'nfl-2-506823-lab'
PREFIX = 'research/week2-input-release-20260919/morning-refresh-v1/'
STATE = Path('/home/erich/.local/state/nfl-dfs/lab-launcher-registry')
JOBS = ('build-features', 'tabpfn-gen', 'project-slate')
TARGET = 'morning-refresh-20260919'
START = datetime.fromisoformat('2026-09-19T14:45:00+00:00')
READY_START = datetime.fromisoformat('2026-09-19T14:33:00+00:00')
READY_END = datetime.fromisoformat('2026-09-19T14:38:00+00:00')
LAST_START = datetime.fromisoformat('2026-09-19T14:46:00+00:00')
BUILD_AT = datetime.fromisoformat('2026-09-19T15:30:00+00:00')
HOLD = OUT / 'operator-hold.json'
TIMERS = ('nfl-week2-d12800-sat-build.timer','nfl-week2-d6400-sat-build.timer')
SNAPSHOT_DATASET = PROJECT+'.nfl_release_20260919_morning'
HOST_SHA = '2dc116ce95647a776ba9c36cf194f44d022d03a4'
CACHE_SHA = '8aaa5daf5a3ebd12bdb471466dabefdc55f774988ff9437710a4e54467b072b7'
HELPERS = ('2026-09-19-release-supervisor.py', '2026-09-19-release-cache-check.py',
           '2026-09-19-release-projection-check.py', '2026-09-19-release-live-cli-proof.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stamp():
    return datetime.now(timezone.utc)


def write(path, value):
    with Path(path).open('x') as f:
        os.chmod(path, 0o600)
        json.dump(value, f, indent=2, default=str, allow_nan=False)


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), HERE / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def lane_receipts():
    ancestors = set()
    pid = os.getpid()
    while pid > 1:
        ancestors.add(pid)
        pid = int(Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[1])
    receipts = []
    for path in (STATE/'launchers').glob('*.json'):
        r = json.loads(path.read_text())
        if r['lane'] not in JOBS:
            continue
        assert r['pid'] in ancestors and r['owner'] == 'production'
        assert r['target_run_id_prefixes'] == [TARGET]
        actual = Path(f"/proc/{r['pid']}/stat").read_text().rsplit(')', 1)[1].split()
        assert int(actual[19]) == r['process_start_ticks']
        receipts.append(dict(path=str(path), sha256=sha(path), **r))
    assert sorted(r['lane'] for r in receipts) == sorted(JOBS)
    return receipts


def validate_hold(r, now):
    assert r['schema'] == 'week2-saturday-consumer-hold/v2'
    assert r['refresh_id'] == TARGET and r['owner'] == 'operator-erich'
    at = datetime.fromisoformat(r['checked_at'])
    assert at.tzinfo is not None and 0 <= (now-at).total_seconds() <= 600
    assert set(r['timers']) == set(TIMERS)
    for name,row in r['timers'].items():
        assert row['timer_active_state'] in ('inactive','not-found')
        assert row['service'] == name.replace('.timer','.service')
        assert row['service_active_state'] in ('inactive','not-found')
    assert r['no_alternate_launch_before_1530z'] is True
    assert r['restore_by_operator_at'] == '2026-09-19T15:20:00+00:00'
    assert r['restore_method'] == 'recreate-reviewed-transient-units'
    assert re.fullmatch(r'[0-9a-f]{40}', r['evidence_handoff_commit'])
    assert r['source_sha'] == HOST_SHA and r['source_clean'] is True
    assert r['historical_cache_sha256'] == CACHE_SHA


def verify_manifest(m):
    assert m['refresh_id'] == TARGET
    for path, expected in m['files'].items():
        assert sha(path) == expected, f'frozen source/artifact changed: {path}'


def prepare():
    assert not MANIFEST.exists(), 'preserve the frozen preparation'
    paths = [*(HERE/name for name in HELPERS), HERE/'2026-09-19-release-plan.json',
             REPO/'scripts/launcher_registry.sh', OLD/'host-training.parquet',
             OLD/'backup-result.json',
             *(OLD/(name+'-installed-private.json') for name in JOBS)]
    paths += [REPO/n for n in ('src/nfl_dfs/inference/run_projections.py', 'src/nfl_dfs/models/prop_market.py')]
    scheduler = scheduler_configuration()
    relevant = [r for r in scheduler if any(r.get('httpTarget',{}).get('uri','').endswith('/'+n+':run') for n in JOBS)]
    expected = {('s-features','30 6 * * 2','ENABLED'),('s-features-sun','30 5-10 * * 7','ENABLED'),
        ('s-features-route','30 6 * * 4','PAUSED'),('s-project-tu','30 9 * * 2','ENABLED'),('s-project-su','0 6-11 * * 7','ENABLED')}
    assert {(r['name'].split('/')[-1],r['schedule'],r['state']) for r in relevant} == expected
    assert all(r['timeZone']=='America/Chicago' for r in relevant)
    manifest = dict(refresh_id=TARGET, prepared_at=stamp(), files={str(p):sha(p) for p in paths},
        producer_sha256=sha(__file__), target_start=START, latest_start=LAST_START, consumer_hold_path=str(HOLD),
        scheduler_configuration=relevant,
        jobs={name:dict(image=(r:=json.loads((OLD/(name+'-installed-private.json')).read_text()))['template']['template']['containers'][0]['image'],
            template_sha256=hashlib.sha256(json.dumps(r['template'],sort_keys=True).encode()).hexdigest()) for name in JOBS},
        status='PREPARED_NOT_SCHEDULED', source_sha=HOST_SHA, historical_cache_sha256=CACHE_SHA)
    manifest['jobs']['project-slate']['resolved_digest']='sha256:f630fc8c88ed1625fa7873d959e0dcc217a55bd4d95b4e0edb9c1386fb3d5f5d'
    # Public manifest contains file identities, never job environment values.
    write(MANIFEST, manifest)
    print('PREPARED', sha(MANIFEST), flush=True)


def read_hold():
    raw = HOLD.read_bytes()
    r = json.loads(raw)
    validate_hold(r, stamp())
    write(OUT/'host-hold-validated.json', dict(record=r, sha256=hashlib.sha256(raw).hexdigest()))
    return r


def scheduler_configuration():
    raw=subprocess.check_output(['gcloud','scheduler','jobs','list','--project='+PROJECT,
        '--location=us-central1','--format=json(name,state,schedule,timeZone,httpTarget.uri)'])
    return json.loads(raw)


def check_schedulers(m,label):
    rows=scheduler_configuration()
    relevant=[r for r in rows if any(r.get('httpTarget',{}).get('uri','').endswith('/'+n+':run') for n in JOBS)]
    assert sorted(relevant,key=lambda r:r['name'])==sorted(m['scheduler_configuration'],key=lambda r:r['name'])
    write(OUT/(label+'-schedulers.json'),dict(at=stamp(),jobs=relevant,no_saturday_producer=True))


def check_templates(runner,m,label):
    current={}
    for name in JOBS:
        r=runner.get(load(HELPERS[0]).BASE+name)
        assert hashlib.sha256(json.dumps(r['template'],sort_keys=True).encode()).hexdigest()==m['jobs'][name]['template_sha256'],name
        current[name]=r
    image=m['jobs']['project-slate']['image']
    digest=subprocess.check_output(['gcloud','artifacts','docker','images','describe',image,
        '--project='+PROJECT,'--format=value(image_summary.digest)'],text=True).strip()
    assert digest==m['jobs']['project-slate']['resolved_digest'],'mutable projection tag moved'
    write(OUT/(label+'-templates-verified.json'),dict(at=stamp(),templates_unchanged=True,projection_digest=digest))
    return current


def check_table_metadata(runner,label):
    old=json.loads((OLD/'backup-result.json').read_text());tables={}
    for row in runner.plan['tables']:
        source=runner.table_meta(row['source']);snap=runner.table_meta(row['snapshot'])
        assert source['kind']=='TABLE'
        assert hashlib.sha256(json.dumps(source['schema'],sort_keys=True).encode()).hexdigest()==row['expected_schema_sha256']
        assert snap==old['tables'][row['snapshot']],'original rollback snapshot changed'
        tables[row['source']]=source
    assert len(tables)==36
    for name,view in old['views'].items():
        current=runner.table_meta(name)
        assert current['kind']=='VIEW' and current['view_query']==view['view_query']
    write(OUT/(label+'-tables.json'),tables)
    return tables


def morning_backups(runner,before):
    # Preserve the already repaired last-good warehouse, separately from the
    # original pre-repair rollback. No live source table is modified here.
    sql=["DECLARE snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP();",
        f"CREATE SCHEMA `{SNAPSHOT_DATASET}` OPTIONS(location='US', default_table_expiration_days=14);"]
    dests={}
    for source in before:
        dest=SNAPSHOT_DATASET+'.'+source.split('.',1)[1].replace('.','__');dests[source]=dest
        sql.append(f"CREATE SNAPSHOT TABLE `{dest}` CLONE `{source}` FOR SYSTEM_TIME AS OF snapshot_at OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 14 DAY));")
    sql.append('SELECT snapshot_at;');script='\n'.join(sql)
    write(OUT/'morning-backup-claim.json',dict(at=stamp(),sql=script))
    j=runner.bq.query(script,location='US',job_id_prefix='morning_refresh_backup_',job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
    write(OUT/'morning-backup-job.json',dict(job_id=j.job_id));list(j.result(timeout=240))
    snapshots={}
    for source,dest in dests.items():
        s=runner.table_meta(dest);prior=before[source]
        assert s['kind']=='SNAPSHOT'
        assert all(s[k]==prior[k] for k in ('schema','rows','partitioning','range_partitioning','clustering'))
        assert runner.table_meta(source)['etag']==prior['etag'],'another table writer during backup'
        snapshots[dest]=s
    assert len({s['snapshot']['snapshotTime'] for s in snapshots.values()})==1
    write(OUT/'morning-backup-validation.json',dict(job_id=j.job_id,source_to_snapshot=dests,tables=snapshots,verified_count=36))
    print('MORNING_LAST_GOOD_BACKUP_VERIFIED',flush=True)


def query(c, sql, label):
    assert sql.lstrip().startswith(('SELECT', 'WITH')) and ';' not in sql
    j = c.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
    rows = [dict(r) for r in j.result(timeout=180)]
    write(OUT/(label+'.json'), dict(sql=sql, job_id=j.job_id, bytes_processed=j.total_bytes_processed, rows=rows))
    return rows


def fresh_inputs(c):
    raw = f'{PROJECT}.nfl_raw'
    sql = f'''SELECT
      (SELECT MAX(pulled_at) FROM `{raw}.injury_snapshots` WHERE season=2026 AND week=2) AS injury,
      (SELECT MAX(pulled_at) FROM `{raw}.weather` WHERE game_id IN
         (SELECT game_id FROM `{raw}.schedules` WHERE season=2026 AND week=2)) AS weather,
      (SELECT MAX(pulled_at) FROM `{raw}.odds_snapshots` WHERE
         SAFE_CAST(start_time AS TIMESTAMP) >= TIMESTAMP('2026-09-20 17:00:00+00') AND
         SAFE_CAST(start_time AS TIMESTAMP) < TIMESTAMP('2026-09-21 00:00:00+00')) AS odds,
      (SELECT MAX(SAFE_CAST(snapshot_ts AS TIMESTAMP)) FROM `{raw}.prop_lines` WHERE season=2026 AND week=2) AS props'''
    r = query(c, sql, 'raw-freshness')[0]
    for name, hour in [('injury',10), ('weather',13), ('odds',14), ('props',14.5)]:
        lower = datetime(2026,9,19,int(hour),30 if hour % 1 else 0,tzinfo=timezone.utc)
        assert r[name] is not None and lower <= r[name] <= stamp(), f'{name} morning capture missing'
    # Max timestamps alone can bless a partial capture. Require complete
    # Sunday-main game support in each scheduled market/weather arrival.
    sql=f'''WITH games AS (SELECT game_id FROM `{raw}.schedules` WHERE season=2026 AND week=2
        AND gameday='2026-09-20' AND gametime BETWEEN '13:00' AND '16:30'),
      w AS (SELECT game_id,MAX(pulled_at) latest FROM `{raw}.weather` WHERE game_id IN (SELECT game_id FROM games) GROUP BY game_id)
      SELECT (SELECT COUNT(*) FROM games) games,
        (SELECT COUNT(*) FROM w WHERE latest>=TIMESTAMP('2026-09-19 13:00:00+00')) weather,
        (SELECT COUNT(DISTINCT event_id) FROM `{raw}.odds_snapshots`
          WHERE pulled_at>=TIMESTAMP('2026-09-19 14:00:00+00')
          AND SAFE_CAST(start_time AS TIMESTAMP)>=TIMESTAMP('2026-09-20 17:00:00+00')
          AND SAFE_CAST(start_time AS TIMESTAMP)<TIMESTAMP('2026-09-21 00:00:00+00')) odds,
        (SELECT COUNT(DISTINCT event_id) FROM `{raw}.prop_lines` WHERE season=2026 AND week=2
          AND SAFE_CAST(snapshot_ts AS TIMESTAMP)>=TIMESTAMP('2026-09-19 14:30:00+00')
          AND commence_time>=TIMESTAMP('2026-09-20 17:00:00+00')
          AND commence_time<TIMESTAMP('2026-09-21 00:00:00+00')) props'''
    support=query(c,sql,'raw-game-support')[0]
    assert all(support[k]==13 for k in ('games','weather','odds','props')),support


def check_features(c):
    f = f'{PROJECT}.nfl_features'
    sql = f'''SELECT
      (SELECT COUNT(*) FROM `{f}.dk_salary_week` WHERE season=2026 AND week=1) AS salary_w1,
      (SELECT COUNT(*) FROM `{f}.dk_salary_week` WHERE season=2026 AND week=2) AS salary_w2,
      (SELECT COUNT(*) FROM (SELECT gsis_id,season,week FROM `{f}.dk_salary_week` GROUP BY 1,2,3 HAVING COUNT(*)>1)) AS salary_duplicates,
      (SELECT COUNT(*) FROM (SELECT gsis_id,season,week FROM `{f}.player_week_inference` GROUP BY 1,2,3 HAVING COUNT(*)>1)) AS inference_duplicates,
      (SELECT COUNT(*) FROM (SELECT gsis_id,season,week FROM `{f}.player_week_training` GROUP BY 1,2,3 HAVING COUNT(*)>1)) AS training_duplicates,
      (SELECT COUNT(*) FROM `{f}.player_week_inference` WHERE season=2026 AND week=2) AS upcoming,
      (SELECT COUNTIF(games_played_prior>0) FROM `{f}.player_week_inference` WHERE season=2026 AND week=2) AS prior_game,
      (SELECT COUNTIF(snap_share_l4 IS NOT NULL) FROM `{f}.player_week_inference` WHERE season=2026 AND week=2) AS prior_snap,
      (SELECT MAX(games_played_prior) FROM `{f}.player_week_inference` WHERE season=2026 AND week=2) AS max_prior,
      (SELECT COUNTIF(games_played_prior>0) FROM `{f}.player_week_usage` WHERE season=2026 AND week=1) AS future_support'''
    r = query(c, sql, 'feature-support')[0]
    assert min(r[k] for k in ('salary_w1','salary_w2','upcoming','prior_game','prior_snap')) > 0
    assert r['max_prior'] == 1
    assert all(r[k] == 0 for k in ('salary_duplicates','inference_duplicates','training_duplicates','future_support'))


def execute():
    now = stamp()
    assert READY_START <= now <= READY_END, 'outside the fixed readiness window'
    m = json.loads(MANIFEST.read_text()); verify_manifest(m)
    lanes = lane_receipts()
    OUT.mkdir(mode=0o700, exist_ok=False)
    helper = load(HELPERS[0]); helper.OUT = OUT
    runner = helper.Release()
    store = storage.Client(project='nfl-2-506823')
    try:
        write(OUT/'launch.json', dict(at=now, manifest_sha256=sha(MANIFEST), lanes=lanes))
        runner.census('initial')
        check_schedulers(m,'initial')
        check_templates(runner,m,'initial')
        before=check_table_metadata(runner,'before')
        fresh_inputs(runner.bq)
        write(OUT/'ready.json',dict(at=stamp(),refresh_id=TARGET,lanes_acquired=True,read_only_preflight_passed=True,
            next='Operator hold evidence then fixed 14:45 start; no shared table mutation yet'))
        print('MORNING_REFRESH_READY_FOR_OPERATOR_HOLD',flush=True)
        while stamp()<START:
            if (OUT/'STOP').exists():raise RuntimeError('operator/root stopped before refresh')
            time.sleep(5)
        assert stamp()<=LAST_START,'late readiness; do not start after the operator window'
        read_hold()
        runner.census('before-mutation')
        check_schedulers(m,'before-mutation')
        installed=check_templates(runner,m,'before-mutation')
        for name,r in installed.items():
            write(OUT/(name+'-installed-private.json'),r)
        morning_backups(runner,before)
        for name in JOBS:
            lane_receipts()
            assert stamp()<BUILD_AT,'build deadline reached; report and reconcile immediately'
            if (OUT/'STOP').exists():raise RuntimeError('stopped at inter-job boundary')
            before = runner.census('before-'+name)
            assert runner.get(helper.BASE+name)['template'] == installed[name]['template']
            args = ['gcloud','run','jobs','execute',name,'--project='+PROJECT,'--region=us-central1','--wait','--format=json']
            if name == 'tabpfn-gen': args.append('--update-env-vars=TABPFN_UPCOMING=2026:2')
            answer = runner.command(name+'-execute',args)
            identity = answer.get('name') or answer.get('metadata',{}).get('name')
            assert identity, 'missing exact execution ID; reconcile without retry'
            e = runner.get(helper.BASE+name+'/executions/'+identity.split('/')[-1])
            assert e['name'] not in before[name] and helper.completed(e)
            assert e.get('succeededCount',0) == e['taskCount'] and not e.get('failedCount',0) and not e.get('cancelledCount',0)
            assert any(x['type']=='Completed' and x['state']=='CONDITION_SUCCEEDED' for x in e['conditions'])
            assert runner.get(helper.BASE+name)['template'] == installed[name]['template']
            write(OUT/(name+'-result.json'), dict(at=stamp(),execution=e['name'],execution_receipt=e,image=m['jobs'][name]['image'],template_unchanged=True))
            print('MORNING_STAGE_COMPLETE',name,e['name'],flush=True)
            if name == 'build-features': check_features(runner.bq)
            elif name == 'tabpfn-gen':
                checker = load(HELPERS[1]); checker.P = OUT; checker.main()
            else:
                checker = load(HELPERS[2]); checker.P = OUT; checker.main()
        proof = load(HELPERS[3]); proof.ROOT = OUT
        import shutil
        shutil.copyfile(OLD/'host-training.parquet',OUT/'host-training.parquet')
        os.chdir(proof.LAB); sys.argv = [str(HERE/HELPERS[3]),'host']; proof.main()
        runner.census('finished')
        completion = dict(status='VALIDATED',refresh_id=TARGET,completed_at=stamp(),manifest_sha256=sha(MANIFEST),
          executions={n:json.loads((OUT/(n+'-result.json')).read_text())['execution'] for n in JOBS},
          projection=json.loads((OUT/'projection-validation.json').read_text()),
          proof_sha256=sha(OUT/'live-cli-host-proof.json'),consumer_may_resume_after_independent_verification=True,
          operator_restore_at='2026-09-19T15:20:00+00:00',lanes_still_held_until_process_exit=True)
        write(OUT/'validated.json',completion)
        store.bucket(BUCKET).blob(PREFIX+'validated.json').upload_from_filename(str(OUT/'validated.json'),if_generation_match=0)
        print('MORNING_REFRESH_VALIDATED',flush=True)
    except BaseException as exc:
        write(OUT/'stopped.json',dict(at=stamp(),error=str(exc),reconciliation_required=True,
            operator_fixed_restore='2026-09-19T15:20:00+00:00',consistency_not_certified=True))
        raise


def preflight():
    """Read-only rehearsal, separate evidence directory, no launch or hold."""
    global OUT
    OUT=BASE/('morning-readonly-preflight-'+stamp().strftime('%H%M%S'))
    OUT.mkdir(exist_ok=False)
    m=json.loads(MANIFEST.read_text());verify_manifest(m)
    helper=load(HELPERS[0]);helper.OUT=OUT;runner=helper.Release()
    runner.census('preflight');check_schedulers(m,'preflight');check_templates(runner,m,'preflight')
    check_table_metadata(runner,'preflight')
    print('READONLY_PREFLIGHT_PASS',OUT,flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('mode',choices=['prepare','preflight','execute']); args=p.parse_args()
    if args.mode == 'prepare': prepare()
    elif args.mode == 'preflight':preflight()
    else: execute()
