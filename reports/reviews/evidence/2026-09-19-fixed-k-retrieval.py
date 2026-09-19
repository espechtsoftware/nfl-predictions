"""Frozen fixed-K coverage replacements with component, prefix and contest guards."""
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


def covered_delta(packed, counts, old_hits):
    lost = old_hits & (counts == 1)
    masks = np.packbits((counts == 0) | lost, axis=1)
    gains = []
    for part in range(2):
        n = np.bitwise_count(packed[:, part] & masks[part]).sum(axis=1, dtype=np.int64)
        gains.append(n - int(lost[part].sum()))
    return np.stack(gains, axis=1)


def fixture():
    rng = np.random.default_rng(8413)
    for chance in (0., .15, .6, 1.):
        hits = rng.random((13, 2, 24)) < chance
        book = [0, 1, 2, 3]
        counts = hits[book].sum(axis=0)
        packed = np.packbits(hits, axis=2)
        before = (counts > 0).sum(axis=1)
        for row in range(4):
            delta = covered_delta(packed, counts, hits[book[row]])
            remaining = book[:row] + book[row + 1:]
            for new in range(4, 13):
                expected = hits[remaining + [new]].any(axis=0).sum(axis=1) - before
                assert np.array_equal(delta[new], expected)
    print('synthetic packed-coverage replacement checks passed', flush=True)


fixture()
if '--mechanics-only' in sys.argv:
    sys.exit(0)

import pyarrow.parquet as pq
from google.cloud import storage

R = Path('reports/reviews/evidence')
OUT = R / '2026-09-19-fixed-k-retrieval.json'
assert not OUT.exists()
manifest = json.loads((R / '2026-09-18-week2-archive-preflight.json').read_text())
prior = json.loads((R / '2026-09-18-week2-current-selector-diagnostic.json').read_text())
assert prior['baseline_reproduced']
original = np.asarray(prior['selected'], dtype=int)
assert len(original) == len(set(original)) == 97
bucket = storage.Client(project='nfl-2-506823').bucket('nfl-2-506823-lab')
prefix = manifest['prefix'].split(bucket.name + '/', 1)[1]
verified = {}


def get(name):
    rec = next(r for r in manifest['objects'] if r['name'] == name)
    raw = bucket.blob(prefix + name).download_as_bytes(if_generation_match=int(rec['generation']))
    assert hashlib.sha256(raw).hexdigest() == rec['sha256']
    verified[name] = dict(sha256=rec['sha256'], generation=rec['generation'])
    return raw


frame = pq.read_table(io.BytesIO(get('frame.parquet')), columns=['id']).to_pydict()
candidate = pq.read_table(io.BytesIO(get('candidates.parquet')), columns=['players']).to_pydict()
index = {str(v): i for i, v in enumerate(frame['id'])}
rosters = [[index[p] for p in text.split(',')] for text in candidate['players']]
assert len(index) == 435 and len(rosters) == 6400
assert len(set(tuple(sorted(x)) for x in rosters)) == 6400
assert all(len(x) == len(set(x)) == 9 for x in rosters)
T = np.empty((6400, 20000), dtype=np.float32)
for part, name in enumerate(('incumbent_player_scores.npy', 'corrected_hsim_player_scores.npy')):
    P = np.load(io.BytesIO(get(name)), allow_pickle=False)
    assert P.shape == (435, 10000) and P.dtype == np.float32 and np.isfinite(P).all()
    for i, rows in enumerate(rosters):
        T[i, part * 10000:(part + 1) * 10000] = P[rows].sum(axis=0, dtype=np.float32)
    del P
raw = subprocess.check_output(['git', '-C', '/home/erich/projects/.nfl2-worktrees/prereg101-review-reply',
    'show', 'e7255e98bf87297452befb61fb508ad4b368b59f:results/contest/milly_winners.json'])
registry_sha = hashlib.sha256(raw).hexdigest()
assert registry_sha == '4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
WINNERS = np.asarray(sorted(json.loads(raw).values()), dtype=np.float64)
assert len(WINNERS) == 48
START = time.monotonic()
packed = np.packbits((T >= 220).reshape(6400, 2, 10000), axis=2)
spans = [(0, 1), (1, 24), (24, 25), (25, 30), (30, 31), (31, 33),
         (33, 43), (43, 53), (53, 63), (63, 79), (79, 95), (95, 97)]
sets = {f'prefix{k}': np.arange(k) for k in (1, 10, 20, 30, 40, 80, 90, 97)}
sets.update({f'block{a + 1}_{z}': np.arange(a, z) for a, z in spans})


def utility(x):
    x = np.asarray(x, dtype=np.float64)
    return (1 / (1 + np.exp(-(x[:, None] - WINNERS) / 8))).mean(axis=1)


def metrics(maximum):
    u = utility(maximum)
    return np.asarray([float(v) for sl in (slice(0, 10000), slice(10000, 20000))
        for v in (maximum[sl].mean(dtype=np.float64), u[sl].mean(), (maximum[sl] >= 220).mean())])


def evaluate(book):
    return {key: metrics(T[book[rows]].max(axis=0)) for key, rows in sets.items()}


book = original.copy()
before = evaluate(book)
steps = []
stop = 'three_replacement_budget'
for iteration in range(3):
    counts = (T[book] >= 220).reshape(97, 2, 10000).sum(axis=0)
    proposals = []
    for row in range(1, 97):
        if time.monotonic() - START > 300:
            stop = 'compute_cap_during_coverage_enumeration'
            break
        delta = covered_delta(packed, counts, (T[book[row]] >= 220).reshape(2, 10000))
        total = delta.sum(axis=1)
        keep = (delta >= 0).all(axis=1) & (total > 0)
        keep[book] = False
        for cand in np.flatnonzero(keep):
            proposals.append((-int(total[cand]), row, int(cand), delta[cand].tolist()))
    if stop.startswith('compute_cap'):
        steps.append(dict(iteration=iteration, status=stop)); break
    proposals.sort()
    base = {key: T[book[rows]].max(axis=0) for key, rows in sets.items()}
    base_metrics = {key: metrics(mx) for key, mx in base.items()}
    cache = {}
    rejected = dict(p220=0, Emax=0, proxy=0)
    accepted = None
    screened = 0
    for negative_gain, row, cand, hit_delta in proposals:
        if screened >= 10000 or time.monotonic() - START > 300:
            stop = 'proposal_cap' if screened >= 10000 else 'compute_cap_during_guards'
            break
        screened += 1
        affected = [key for key, rows in sets.items() if row in rows]
        # Most discriminating contexts first, deterministic: actual block, then increasing prefix.
        affected.sort(key=lambda key: (0 if key.startswith('block') else 1, len(sets[key]), key))
        passed = True
        proposed_metrics = {}
        for key in affected:
            pair = (key, row)
            if pair not in cache:
                remaining = sets[key][sets[key] != row]
                cache[pair] = T[book[remaining]].max(axis=0) if len(remaining) else np.full(20000, -np.inf)
            newmax = np.maximum(cache[pair], T[cand])
            old = base_metrics[key]
            p220 = (newmax >= 220).reshape(2, 10000).mean(axis=1)
            if np.any(p220 < old[[2, 5]]):
                rejected['p220'] += 1; passed = False; break
            emax = newmax.reshape(2, 10000).mean(axis=1, dtype=np.float64)
            if np.any(emax < old[[0, 3]] - 1e-12):
                rejected['Emax'] += 1; passed = False; break
            proxy = old[[1, 4]].copy()
            for part in range(2):
                sl = slice(part * 10000, (part + 1) * 10000)
                changed = newmax[sl] != base[key][sl]
                if changed.any():
                    proxy[part] += (utility(newmax[sl][changed]) - utility(base[key][sl][changed])).sum() / 10000
            if np.any(proxy < old[[1, 4]] - 1e-12):
                rejected['proxy'] += 1; passed = False; break
            proposed_metrics[key] = np.asarray([emax[0], proxy[0], p220[0], emax[1], proxy[1], p220[1]])
        if passed:
            old_candidate = int(book[row])
            book[row] = cand
            direct = evaluate(book)
            for key in affected:
                assert np.allclose(direct[key], proposed_metrics[key], atol=1e-12, rtol=0)
            assert np.allclose((direct['prefix97'][[2, 5]] - base_metrics['prefix97'][[2, 5]]) * 10000,
                               hit_delta, atol=1e-9, rtol=0)
            accepted = dict(row=row + 1, old_candidate=old_candidate, new_candidate=cand,
                covered_world_gain=hit_delta, total_covered_world_gain=-negative_gain)
            break
    step = dict(iteration=iteration, coverage_eligible_pairs=len(proposals), screened=screened,
                rejections=rejected, accepted=accepted)
    steps.append(step)
    print(json.dumps(step), flush=True)
    if accepted is None:
        if not stop.endswith('cap') and not stop.startswith('compute_cap'):
            stop = 'no_eligible_guarded_replacement'
        break
after = evaluate(book)
assert len(set(book)) == 97 and book[0] == original[0]
assert all(np.all(after[key] >= before[key] - 1e-12) for key in sets)
result = dict(steps=steps, stop=stop, selected=book.tolist(), original_selected=original.tolist(),
    metrics_order=['incumbent_Emax', 'incumbent_GLOBALproxy', 'incumbent_P220', 'hsim_Emax', 'hsim_GLOBALproxy', 'hsim_P220'],
    sets={key: dict(before=before[key].tolist(), after=after[key].tolist(), delta=(after[key] - before[key]).tolist()) for key in sets},
    final_no_harm_all_sets=True, milly_unchanged=True, fixed_k=97, verified_inputs=verified,
    registry_sha256=registry_sha, elapsed_seconds=time.monotonic() - START,
    caveat='Selection-bank diagnostic on older D6400 pool. No independent law or realized-score validation.',
    provenance=dict(git_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        git_status=subprocess.check_output(['git', 'status', '--porcelain'], text=True),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), python=platform.python_version(), numpy=np.__version__,
        threads={key: os.environ.get(key) for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')}))
with OUT.open('x') as handle:
    json.dump(result, handle, indent=2, allow_nan=False)
print(json.dumps(dict(stop=stop, steps=len(steps), whole_book=result['sets']['prefix97'], elapsed_seconds=result['elapsed_seconds'])), flush=True)
