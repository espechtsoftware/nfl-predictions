"""Bind one committed actual host observation to the prepared refresh receipt."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

import yaml

HERE=Path(__file__).parent
spec=importlib.util.spec_from_file_location('morning_contract',HERE/'2026-09-19-morning-refresh.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def parse(raw,commit,now):
    assert re.fullmatch('[0-9a-f]{40}',commit)
    text=raw.decode('utf-8')
    blocks=re.findall(r'^```(?:yaml|yml|text)?\s*\n(.*?)^```\s*$',text,re.M|re.S)
    candidates=[s for s in blocks if s.startswith('schema: week2-saturday-consumer-hold/v2\n')]
    if text.startswith('schema: week2-saturday-consumer-hold/v2\n'):candidates.append(text)
    assert len(candidates)==1,'one actual observer record is required'
    r=yaml.safe_load(candidates[0]);assert isinstance(r,dict)
    expected={'schema','refresh_id','owner','checked_at','no_alternate_launch_before_1530z',
        'restore_by_operator_at','restore_method','source_sha','source_clean','historical_cache_sha256',*m.TIMERS}
    assert set(r)==expected,'unexpected or missing observer fields'
    for key in ('checked_at','restore_by_operator_at'):
        if isinstance(r[key],datetime):r[key]=r[key].isoformat()
    r['timers']={name:r.pop(name) for name in m.TIMERS}
    r['evidence_handoff_commit']=commit
    m.validate_hold(r,now)
    r['evidence_handoff_sha256']=hashlib.sha256(raw).hexdigest()
    return r


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--commit',required=True);ap.add_argument('--path',required=True);a=ap.parse_args()
    assert re.fullmatch('[0-9a-f]{40}',a.commit)
    p=Path(a.path);assert not p.is_absolute() and '..' not in p.parts and p.parts[0]=='handoffs'
    subprocess.check_call(['git','-C',str(a.repo),'merge-base','--is-ancestor',a.commit,
        'origin/lab/workstation-reply-bank991-20260918'])
    raw=subprocess.check_output(['git','-C',str(a.repo),'show',a.commit+':'+str(p)])
    r=parse(raw,a.commit,datetime.now(timezone.utc));r['evidence_handoff_path']=str(p)
    assert (m.OUT/'ready.json').is_file(),'readiness must precede the operator hold receipt'
    assert json.loads((m.OUT/'ready.json').read_text())['read_only_preflight_passed'] is True
    m.write(m.HOLD,r)
    print('ACTUAL_COMMITTED_HOLD_BOUND',a.commit,m.HOLD,flush=True)


if __name__=='__main__':main()
