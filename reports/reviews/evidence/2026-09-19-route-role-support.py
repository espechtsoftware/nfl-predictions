"""Prior-week vendor participation support; no outcome or model-effect query."""
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from google.cloud import bigquery

R = Path('reports/reviews/evidence')
OUT = R / '2026-09-19-route-role-support.json'
assert not OUT.exists()
role_path = R / '2026-09-19-hsim-role-trace.json'
role_raw = role_path.read_bytes()
assert hashlib.sha256(role_raw).hexdigest() == '5e51dd47ca2d210a154a8bf96a3bfcc387c6a52c582000eca017e78e7c967797'
role = json.loads(role_raw)
query = '''SELECT season, week, gsis_id, resolution_status, vendor_name, vendor_team, pos,
 route_share, source_file, source_sha256, source_row, source_target_week,
 source_retrieved_at, source_run_id, archive_uri, ingested_at
 FROM `nfl-predictions-503414.nfl_raw.fantasy_points_route_share`
 WHERE season=2026 AND week=1
 AND ingested_at <= TIMESTAMP('2026-09-19 00:26:00+00')
 ORDER BY gsis_id, source_row'''
client = bigquery.Client(project='nfl-2-506823')
job = client.query(query, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=100_000_000))
raw_rows = [dict(x) for x in job.result(timeout=60)]
invalid, eligible = [], []
cut = datetime(2026, 9, 19, 0, 26, tzinfo=timezone.utc)
for r in raw_rows:
    reasons = []
    if not r['gsis_id']: reasons.append('unresolved_id')
    if r['source_target_week'] not in (None, 2): reasons.append('wrong_target_week')
    if r['route_share'] is None or not 0 <= r['route_share'] <= 1: reasons.append('invalid_route_share')
    if r['source_retrieved_at'] is not None and r['source_retrieved_at'] > cut: reasons.append('retrieved_after_cutoff')
    if reasons: invalid.append(dict(row=r, reasons=reasons))
    else: eligible.append(r)
ids = [r['gsis_id'] for r in eligible]
assert len(ids) == len(set(ids)), 'duplicate resolved vendor identity'
lookup = {r['gsis_id']: r for r in eligible}
groups = []
for population in ('all', 'selected'):
    for pos in ('QB', 'RB', 'WR', 'TE', 'DST'):
        for active in (True, False):
            rows = [r for r in role['all_players'] if r['pos'] == pos and r['hsim_activity_mask'] == active
                    and (population == 'all' or r['book_count'] > 0)]
            matched = [lookup[r['id']] for r in rows if r['id'] in lookup]
            groups.append(dict(population=population, position=pos, hsim_active=active, players=len(rows),
                matched=len(matched), positive_routes=sum(r['route_share'] > 0 for r in matched)))
zero_rows = []
for player in role['selected_zero_opportunity_skill']:
    zero_rows.append(dict(id=player['id'], name=player['display_name'], team=player['team'],
        depth_rank=player['depth_rank'], book_count=player['book_count'], route=lookup.get(player['id'])))
result = dict(recorded_at=datetime.now(timezone.utc).isoformat(), query=query, job_id=job.job_id,
    bytes_processed=job.total_bytes_processed, source_rows=len(raw_rows), eligible_rows=len(eligible), invalid_rows=invalid,
    source_hashes=sorted(set(str(r['source_sha256']) for r in raw_rows)), groups=groups,
    selected_zero_opportunity=zero_rows, source_records=raw_rows,
    role_trace_sha256=hashlib.sha256(role_raw).hexdigest(),
    provenance=dict(git_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        git_status=subprocess.check_output(['git', 'status', '--porcelain'], text=True),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
    scope='Prior-week participation support only; no prediction-quality or live adoption claim.')
with OUT.open('x') as handle:
    json.dump(result, handle, indent=2, default=str, allow_nan=False)
print(json.dumps({key: result[key] for key in ('source_rows', 'eligible_rows', 'invalid_rows', 'groups', 'selected_zero_opportunity')}, indent=2, default=str))
