#!/usr/bin/env python3
"""Registry-owned, serial Cloud Run execution; never updates the shared job."""
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import google.auth
from google.auth.transport.requests import AuthorizedSession

PROJECT = 'nfl-predictions-503414'
REGION = 'us-central1'
JOB = f'projects/{PROJECT}/locations/{REGION}/jobs/tabpfn-gen'
API = 'https://run.googleapis.com/v2/'
IMAGE = 'us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/tabpfn-gen@sha256:7eeff44e7c225fed62682b3649dfa86d77f86227e3e9858c967d132deff2a10a'
ROOT = Path(__file__).resolve().parents[3]
ADAPTER = Path(__file__).with_name('2026-09-19-tabpfn-scratch-refresh.py')


def save(path, value):
    with path.open('x') as f:
        os.chmod(path, 0o600)
        json.dump(value, f, indent=2)


def main():
    mode = sys.argv[1]
    if mode not in ('mechanics', 'refresh'):
        raise ValueError('mode must be mechanics or refresh')
    registry = Path(os.environ['NFL_LAUNCHER_REGISTRY_RECEIPT'])
    raw = registry.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == os.environ['NFL_LAUNCHER_REGISTRY_RECEIPT_SHA256']
    reg = json.loads(raw)
    assert reg['lane'] == 'tabpfn-gen' and reg['owner'] == 'production'
    assert Path(reg['script_path']).resolve() == Path(__file__).resolve()
    assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    adapter = ADAPTER.read_bytes()
    assert adapter == subprocess.check_output(['git', 'show', sha + ':' + str(ADAPTER.relative_to(ROOT))], cwd=ROOT)
    launch_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + mode
    out = Path('/home/erich/projects/review-evidence/overnight-20260918/tabpfn-cloud') / launch_id
    out.mkdir(parents=True, exist_ok=False)
    creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    session = AuthorizedSession(creds)

    def get(name):
        while True:
            try:
                r = session.get(API + name, timeout=45)
                r.raise_for_status()
                return r.json()
            except Exception as error:
                # Read-only retries retain ownership if the provider is running.
                print('PROVIDER_READ_RETRY', name, type(error).__name__, flush=True)
                time.sleep(30)

    before = get(JOB)
    save(out / 'base-before-private.json', before)
    c = before['template']['template']['containers']
    assert len(c) == 1 and c[0]['image'] == IMAGE
    assert not c[0].get('command') and not c[0].get('args')
    census = get(JOB + '/executions?pageSize=100')
    pending = [x['name'] for x in census.get('executions', []) if not x.get('completionTime')]
    assert not pending, pending
    code = "exec(__import__('base64').b64decode(" + repr(base64.b64encode(adapter).decode()) + "))"
    # No shell interprets this list. With image ENTRYPOINT unset, args replaces
    # its CMD [python, /app/gen.py]. The sentinel disables the original script.
    for arm in (['control'] if mode == 'mechanics' else ['control', 'salaryfix']):
        assert datetime.now(timezone.utc).isoformat() < '2026-09-19T13:30:00+00:00'
        env = dict(GCP_PROJECT=PROJECT, TABPFN_REHEARSAL_ARM=arm, TABPFN_REHEARSAL_MODE=mode,
                   TABPFN_REHEARSAL_ID=launch_id + '-' + arm,
                   TABPFN_OUTPUT_TABLE='scratch_adapter_required', CODE_SHA=sha,
                   TABPFN_COMPONENTS='0', TABPFN_SEASONS='', TABPFN_WRITE='')
        body = {'overrides': {'containerOverrides': [{'args': ['python', '-c', code],
                  'env': [{'name': k, 'value': v} for k, v in env.items()]}],
                  'taskCount': 1, 'timeout': '1200s' if mode == 'refresh' else '300s'}}
        save(out / (arm + '-claim.json'), dict(job=JOB, mode=mode, source_sha=sha,
             adapter_sha256=hashlib.sha256(adapter).hexdigest(), run_id=env['TABPFN_REHEARSAL_ID'],
             request_sha256=hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()))
        # Exactly one POST. An ambiguous return leaves its claim for manual
        # provider reconciliation; the script never retries a launch.
        print('LAUNCH', arm, mode, out, flush=True)
        try:
            response = session.post(API + JOB + ':run', json=body, timeout=45)
            response.raise_for_status()
            operation = response.json()
        except Exception as error:
            print('AMBIGUOUS_LAUNCH_REQUIRES_PROVIDER_RECONCILIATION', arm,
                  type(error).__name__, 'retaining lane; no launch retry', flush=True)
            # The supervising agent must inspect exact provider executions and
            # resolve this claim before interrupting/releasing or retrying.
            while True:
                time.sleep(30)
        save(out / (arm + '-operation-start.json'), operation)
        op_name = operation['name']
        print('OPERATION', op_name, flush=True)
        while not operation.get('done'):
            time.sleep(15)
            operation = get(op_name)
        save(out / (arm + '-operation-end.json'), operation)
        if operation.get('error'):
            raise RuntimeError(operation['error'])
        execution = operation['response']
        name = execution['name']
        while not execution.get('completionTime'):
            time.sleep(15)
            execution = get(name)
        save(out / (arm + '-execution.json'), execution)
        assert execution.get('succeededCount') == 1 and not execution.get('failedCount'), name
        print('COMPLETED', arm, name, execution.get('startTime'), execution['completionTime'], flush=True)
        current = get(JOB)
        assert current['template'] == before['template'], 'shared job base configuration changed'
    after = get(JOB)
    save(out / 'base-after-private.json', after)
    assert after['template'] == before['template']
    print('SHARED_JOB_CONFIGURATION_UNCHANGED', launch_id, flush=True)


if __name__ == '__main__':
    main()
