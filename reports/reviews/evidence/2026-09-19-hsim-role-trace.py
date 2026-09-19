"""Hash-pinned outcome-free role trace of the two archived simulation banks."""
import hashlib
import io
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from google.cloud import storage

R = Path('reports/reviews/evidence')
OUT = R / '2026-09-19-hsim-role-trace.json'
assert not OUT.exists()
LAB = Path('/home/erich/projects/.nfl2-worktrees/audit-capture-review')
SHA = 'e7255e98bf87297452befb61fb508ad4b368b59f'
source_hashes = {}
for name in ('src/nfl2/hsim/shares.py', 'src/nfl2/hsim/world.py'):
    raw = subprocess.check_output(['git', '-C', str(LAB), 'show', SHA + ':' + name])
    assert raw == (LAB / name).read_bytes()
    source_hashes[name] = hashlib.sha256(raw).hexdigest()
sys.path.insert(0, str(LAB / 'src'))
from nfl2.hsim.shares import active_mask, _prior_weights, TARGET_POS, CARRY_POS
from nfl2.hsim.world import POS_FALLBACK_T, POS_FALLBACK_C

manifest = json.loads((R / '2026-09-18-week2-archive-preflight.json').read_text())
prior = json.loads((R / '2026-09-18-week2-current-selector-diagnostic.json').read_text())
assert prior['baseline_reproduced']
selected = prior['selected']; assert len(selected) == len(set(selected)) == 97
bucket = storage.Client(project='nfl-2-506823').bucket('nfl-2-506823-lab')
prefix = manifest['prefix'].split(bucket.name + '/', 1)[1]
verified = {}


def get(name):
    rec = next(x for x in manifest['objects'] if x['name'] == name)
    raw = bucket.blob(prefix + name).download_as_bytes(if_generation_match=int(rec['generation']))
    assert hashlib.sha256(raw).hexdigest() == rec['sha256']
    verified[name] = dict(sha256=rec['sha256'], generation=rec['generation'])
    return raw


columns = ['id', 'display_name', 'pos', 'team', 'proj', 'mean_projection', 'depth_rank', 'snap_share_l4',
    'is_cold_start', 'games_played_prior', 'target_share_l4', 'carry_share_l4', 'has_features',
    'model_points_pre', 'market_points', 'game_total', 'spread']
fr = pq.read_table(io.BytesIO(get('frame.parquet')), columns=columns).to_pandas()
c = pq.read_table(io.BytesIO(get('candidates.parquet')), columns=['players']).to_pydict()
index = {str(v): i for i, v in enumerate(fr.id)}
assert len(index) == len(fr) == 435 and len(c['players']) == 6400
rosters = [[index[v] for v in x.split(',')] for x in c['players']]
assert all(len(x) == len(set(x)) == 9 for x in rosters)
means = {}
for key, name in (('incumbent', 'incumbent_player_scores.npy'), ('hsim', 'corrected_hsim_player_scores.npy')):
    P = np.load(io.BytesIO(get(name)), allow_pickle=False)
    assert P.shape == (435, 10000) and P.dtype == np.float32 and np.isfinite(P).all()
    means[key] = P.mean(axis=1, dtype=np.float64)
    del P
start = time.monotonic()
pool_count = np.bincount(np.asarray(rosters).ravel(), minlength=435)
book_count = np.bincount(np.asarray([rosters[i] for i in selected]).ravel(), minlength=435)
active = active_mask(fr)
wt = _prior_weights(fr, 'target_share_l4', TARGET_POS, POS_FALLBACK_T)
wc = _prior_weights(fr, 'carry_share_l4', CARRY_POS, POS_FALLBACK_C)
proj = pd.to_numeric(fr.proj, errors='coerce').fillna(0).to_numpy()
primary = np.zeros(435, dtype=bool)
for team in sorted(set(fr.team)):
    rows = np.flatnonzero((fr.team == team) & (fr.pos == 'QB'))
    if len(rows):
        primary[rows[np.argmax(proj[rows])]] = True
fr['incumbent_mean'] = means['incumbent']
fr['hsim_mean'] = means['hsim']
fr['hsim_minus_incumbent'] = means['hsim'] - means['incumbent']
fr['candidate_count'] = pool_count
fr['book_count'] = book_count
fr['hsim_activity_mask'] = active
fr['hsim_positive_target_prior'] = wt > 0
fr['hsim_positive_carry_prior'] = wc > 0
fr['hsim_primary_qb'] = primary


def rows_json(data):
    return json.loads(data.to_json(orient='records', double_precision=12))


def describe(mask):
    x = fr.loc[mask, 'hsim_minus_incumbent'].to_numpy()
    return dict(n=len(x), mean=float(x.mean()), median=float(np.median(x)), min=float(x.min()), max=float(x.max())) if len(x) else dict(n=0)


groups = []
for population, mask in [('all', np.ones(435, dtype=bool)), ('selected', book_count > 0)]:
    for pos in sorted(set(fr.pos)):
        for a in (True, False):
            m = mask & (fr.pos == pos) & (active == a)
            groups.append(dict(population=population, position=pos, active=a, delta=describe(m)))
    for flag in (True, False):
        groups.append(dict(population=population, position='QB', primary=flag,
            delta=describe(mask & (fr.pos == 'QB') & (primary == flag))))
team_rows = []
for team in sorted(set(fr.team)):
    skill = (fr.team == team) & fr.pos.isin(['RB', 'WR', 'TE'])
    team_rows.append(dict(team=team, skill_players=int(skill.sum()),
        served_skill_total=float(fr.loc[skill, 'mean_projection'].sum()),
        incumbent_skill_total=float(fr.loc[skill, 'incumbent_mean'].sum()),
        hsim_skill_total=float(fr.loc[skill, 'hsim_mean'].sum()),
        selected_skill_players=int((skill & (book_count > 0)).sum())))
top = fr.loc[book_count > 0].assign(absolute_delta=lambda x: abs(x.hsim_minus_incumbent)).sort_values(
    ['absolute_delta', 'id'], ascending=[False, True]).head(30)
result = dict(groups=groups, top_selected_offsets=rows_json(top),
    selected_nonprimary_qbs=rows_json(fr[(book_count > 0) & (fr.pos == 'QB') & ~primary]),
    selected_zero_opportunity_skill=rows_json(fr[(book_count > 0) & fr.pos.isin(['RB', 'WR', 'TE']) & (wt == 0) & (wc == 0)]),
    team_skill_totals=team_rows, all_players=rows_json(fr), verified_inputs=verified, source_hashes=source_hashes,
    elapsed_seconds=time.monotonic() - start,
    caveat='Roles are exact archived code rules, not independently verified Sunday roles. No outcomes or resimulation.',
    provenance=dict(git_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        git_status=subprocess.check_output(['git', 'status', '--porcelain'], text=True),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), python=platform.python_version(), numpy=np.__version__))
assert result['elapsed_seconds'] < 60
with OUT.open('x') as handle:
    json.dump(result, handle, indent=2, allow_nan=False)
print(json.dumps({key: result[key] for key in ('groups', 'selected_nonprimary_qbs', 'selected_zero_opportunity_skill')}, indent=2))
print(top[['id', 'display_name', 'pos', 'team', 'mean_projection', 'incumbent_mean', 'hsim_mean',
    'hsim_minus_incumbent', 'hsim_activity_mask', 'hsim_primary_qb', 'book_count']].to_string(index=False))
