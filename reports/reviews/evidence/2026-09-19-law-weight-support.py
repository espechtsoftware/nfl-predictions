"""Outcome-blind benchmark support census for a whole-law weighting study."""
import base64
import hashlib
import json
from pathlib import Path
import google_crc32c
import pandas as pd

LAB = Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
CACHE = Path('/home/erich/.cache/nfl2')
manifest = LAB / 'benchmark/MANIFEST-v1.json'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(manifest) == '04710846d67fb6c6d1eb06335d857846bc206dda696917a379149739851f87cf'
records = json.loads(manifest.read_text())['objects']
tables = ['player_week_training', 'raw_weekly_stats', 'raw_schedules', 'tabpfn_projections']
prefixes = [f'benchmark/v0/warehouse/{t}/' for t in tables] + ['benchmark/v1/panel107/snap_pitclean_k1/']
files = []
for rec in records:
    key = rec['uri'].split('nfl-2-506823-lab/', 1)[-1]
    if not any(key.startswith(p) for p in prefixes): continue
    assert key.endswith('.parquet')
    p = CACHE / key.removeprefix('benchmark/')
    assert p.stat().st_size == int(rec['bytes'])
    assert base64.b64encode(google_crc32c.value(p.read_bytes()).to_bytes(4,'big')).decode() == rec['crc32c']
    files.append({**rec, 'path': str(p), 'sha256': sha(p)})
assert len(files) == 8
snap = CACHE / 'v1/panel107/snap_pitclean_k1/000000000000.parquet'
columns = ['season','week','id','gsis_id','pos','team','opp','game_id','salary','mean_projection']
fr = pd.read_parquet(snap, columns=columns)
assert set(fr.season.unique()) == {2019,2021,2022,2023,2024}
assert not fr.duplicated(['season','week','id']).any()
assert fr[['id','team','opp','game_id']].notna().all().all()
fr['eligible'] = fr.pos.isin(['QB','RB','WR','TE','DST']) & (pd.to_numeric(fr.mean_projection,errors='coerce') >= 5)
slates = []
for (season,week), sub in fr.groupby(['season','week'],sort=True):
    e = sub[sub.eligible]
    counts = e.groupby('pos').size().to_dict()
    assert set(counts) == {'QB','RB','WR','TE','DST'}
    slates.append({'season':int(season),'week':int(week),'players':len(sub),'eligible':len(e),
                   'eligible_by_position':{p:int(n) for p,n in counts.items()},'games':sub.game_id.nunique()})
print(json.dumps({'manifest_sha256':sha(manifest),'files':files,'safe_columns_read':columns,
                  'outcomes_read':False,'slates':slates,'slate_count':len(slates),
                  'player_rows':len(fr),'eligible_rows':int(fr.eligible.sum()),
                  'seasons':fr.groupby('season').agg(players=('id','size'),slates=('week','nunique'),
                       eligible=('eligible','sum')).reset_index().to_dict(orient='records')},indent=2))
