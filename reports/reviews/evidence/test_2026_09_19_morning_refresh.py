"""Exercise the host-hold contract and real nested registry ancestry, offline."""
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

SOURCE=Path(__file__).with_name('2026-09-19-morning-refresh.py')
spec=importlib.util.spec_from_file_location('morning_refresh_candidate',SOURCE)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def hold():
    return dict(schema='week2-saturday-consumer-hold/v2',refresh_id=m.TARGET,owner='operator-erich',
        checked_at=(m.START-timedelta(minutes=5)).isoformat(),
        timers={n:dict(timer_active_state='inactive',service=n.replace('.timer','.service'),
            service_active_state='inactive') for n in m.TIMERS},
        no_alternate_launch_before_1530z=True,restore_by_operator_at='2026-09-19T15:20:00+00:00',
        restore_method='recreate-reviewed-transient-units',evidence_handoff_commit='a'*40,
        source_sha=m.HOST_SHA,source_clean=True,historical_cache_sha256=m.CACHE_SHA)


def test_stopped_and_garbage_collected_transients_both_valid():
    r=hold();m.validate_hold(r,m.START)
    for row in r['timers'].values():
        row['timer_active_state']='not-found';row['service_active_state']='not-found'
    m.validate_hold(r,m.START)


@pytest.mark.parametrize('case',['one_timer','active_timer','running_service','stale','future',
    'wrong_source','dirty_source','wrong_cache','restore_start','late_restore','bad_commit','manual_race'])
def test_unsafe_hold_refuses(case):
    r=hold();first=r['timers'][m.TIMERS[0]]
    if case=='one_timer':del r['timers'][m.TIMERS[1]]
    if case=='active_timer':first['timer_active_state']='active'
    if case=='running_service':first['service_active_state']='activating'
    if case=='stale':r['checked_at']=(m.START-timedelta(seconds=601)).isoformat()
    if case=='future':r['checked_at']=(m.START+timedelta(seconds=1)).isoformat()
    if case=='wrong_source':r['source_sha']='b'*40
    if case=='dirty_source':r['source_clean']=False
    if case=='wrong_cache':r['historical_cache_sha256']='b'*64
    if case=='restore_start':r['restore_method']='systemctl-start'
    if case=='late_restore':r['restore_by_operator_at']='2026-09-19T15:35:00+00:00'
    if case=='bad_commit':r['evidence_handoff_commit']='z'*40
    if case=='manual_race':r['no_alternate_launch_before_1530z']=False
    with pytest.raises(AssertionError):m.validate_hold(r,m.START)


def test_real_nested_registry_ancestry_and_terminal_release(tmp_path):
    # The actual wrapper writes/removes its receipts. Isolated state and lane
    # names ensure this test cannot acquire a real cloud writer lane.
    state=tmp_path/'state';fixture=tmp_path/'verify.py';record=tmp_path/'verified.json'
    lanes=tuple('offline-test-'+n for n in m.JOBS)
    fixture.write_text(
        'import importlib.util,json\nfrom pathlib import Path\n'
        f's=importlib.util.spec_from_file_location("m",{str(SOURCE)!r})\n'
        'm=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n'
        f'm.STATE=Path({str(state)!r});m.JOBS={lanes!r}\n'
        f'Path({str(record)!r}).write_text(json.dumps(m.lane_receipts()))\n')
    command=[sys.executable,str(fixture)]
    registry=str(m.REPO/'scripts/launcher_registry.sh')
    for lane in reversed(lanes):
        command=[registry,'run','--root',str(m.REPO),'--state-root',str(state),
            '--lane',lane,'--owner','production','--target-prefixes',m.TARGET,'--',*command]
    r=subprocess.run(command,capture_output=True,text=True,timeout=40)
    assert r.returncode==0,r.stderr
    assert {x['lane'] for x in json.loads(record.read_text())}==set(lanes)
    assert list((state/'launchers').glob('*.json'))==[]
    completions=[json.loads(p.read_text()) for p in (state/'launcher-completions').glob('*.json')]
    assert len(completions)==3 and all(r['exit_status']==0 for r in completions)
