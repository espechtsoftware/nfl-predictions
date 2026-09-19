"""Observer YAML normalization must not weaken the execution hold contract."""
from datetime import datetime,timezone
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('hold_binding',Path(__file__).with_name('2026-09-19-morning-hold-receipt.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def observed():
    return '''schema: week2-saturday-consumer-hold/v2
refresh_id: morning-refresh-20260919
owner: operator-erich
checked_at: 2026-09-19T14:40:00Z
nfl-week2-d12800-sat-build.timer:
  timer_active_state: inactive
  service: nfl-week2-d12800-sat-build.service
  service_active_state: inactive
nfl-week2-d6400-sat-build.timer:
  timer_active_state: not-found
  service: nfl-week2-d6400-sat-build.service
  service_active_state: not-found
no_alternate_launch_before_1530z: true
restore_by_operator_at: 2026-09-19T15:20:00+00:00
restore_method: recreate-reviewed-transient-units
source_sha: 2dc116ce95647a776ba9c36cf194f44d022d03a4
source_clean: true
historical_cache_sha256: 8aaa5daf5a3ebd12bdb471466dabefdc55f774988ff9437710a4e54467b072b7
'''


def test_literal_observer_timestamps_and_timer_nesting():
    raw=('Observation\n\n```yaml\n'+observed()+'```\n').encode()
    r=m.parse(raw,'a'*40,datetime(2026,9,19,14,45,tzinfo=timezone.utc))
    assert r['checked_at']=='2026-09-19T14:40:00+00:00'
    assert set(r['timers'])==set(m.m.TIMERS) and r['evidence_handoff_commit']=='a'*40


@pytest.mark.parametrize('case',['active','failed','template','duplicate','stale','foreign_sha','unknown_field'])
def test_nonactual_or_unsafe_observation_refuses(case):
    raw=observed()
    if case=='active':raw=raw.replace('timer_active_state: inactive','timer_active_state: active')
    if case=='failed':raw=raw.replace('timer_active_state: inactive','timer_active_state: unverified-read-failed(rc=7)')
    if case=='template':raw=raw.replace('2026-09-19T14:40:00Z','<date-u>')
    if case=='stale':raw=raw.replace('14:40:00Z','14:20:00Z')
    if case=='foreign_sha':raw=raw.replace('2dc116ce95647a776ba9c36cf194f44d022d03a4','a'*40)
    if case=='unknown_field':raw+='unexpected: true\n'
    raw='```\n'+raw+'```\n'
    if case=='duplicate':raw*=2
    with pytest.raises((AssertionError,ValueError)):m.parse(raw.encode(),'a'*40,datetime(2026,9,19,14,45,tzinfo=timezone.utc))
