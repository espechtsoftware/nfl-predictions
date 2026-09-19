"""Five nested selection batches under unchanged laws, with fresh primary audit."""
import hashlib
import json
import runpy
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

R = Path(__file__).resolve().parent
LAB = Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918/complete-chain-d1600')
OUT = Path(__file__).with_suffix('.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def opened(rec):
    path = Path(rec['path'])
    assert sha(path) == rec['sha256']
    return path


def coverage(totals, n):
    clears = totals >= 220
    p = clears.mean(axis=1)
    mu = totals.mean(axis=1, dtype=np.float64)
    covered = np.zeros(totals.shape[1], bool)
    available = np.ones(len(totals), bool)
    book = []
    for _ in range(min(n, len(totals))):
        ids = np.flatnonzero(available)
        gain = clears[ids][:, ~covered].sum(axis=1)
        i = int(ids[np.lexsort((ids, -mu[ids], -p[ids], -gain))[0]])
        book.append(i)
        available[i] = False
        covered |= clears[i]
    return book


def smoke():
    t = np.array([[220, 220, 0, 0], [230, 230, 0, 0], [0, 0, 221, 0], [0, 0, 221, 0]], np.float32)
    assert coverage(t, 4) == [1, 2, 0, 3]
    assert coverage(np.full((100, 3), 100., np.float32), 97) == list(range(97))


def main():
    smoke()
    assert not OUT.exists()
    started = time.monotonic()
    precision = json.loads((R/'2026-09-19-selection-precision-banks.json').read_text())
    assert precision['original_laws_exact']
    assert sha(precision['frame_path']) == precision['frame_sha256']
    old = json.loads((R/'2026-09-19-direct-220-selection.json').read_text())
    chain = json.loads((R / '2026-09-19-repaired-chain-d1600-read.json').read_text())
    state = {}
    for arm in ('control', 'salaryfix'):
        receipt = json.loads((ROOT / arm / 'receipt.json').read_text())
        out = Path(receipt['original_run'])
        for name, digest in chain['provenance'][arm]['artifacts'].items():
            assert sha(out / name) == digest
        frame = pd.read_parquet(out / 'frame.parquet')
        cands = pd.read_parquet(out / 'candidates.parquet')
        orders = json.loads(opened(receipt['candidate_player_orders']).read_text())
        assert cands.index.tolist() == cands.cand.tolist() == list(range(1600))
        assert len(orders) == len(cands) and frame.id.is_unique
        assert all(len(x) == len(set(x)) == 9 and ','.join(sorted(x)) == s for x,s in zip(orders,cands.players))
        banks = {}
        for name in ('I_selection', 'I_audit', 'H_selection', 'H_audit'):
            a = np.load(opened(receipt['arrays'][name]), allow_pickle=False)
            assert a.dtype == np.float32 and a.shape == (len(frame), 10000) and np.isfinite(a).all()
            banks[name] = a
        state[arm] = dict(frame=frame, cands=cands, orders=orders, banks=banks)
    sys.path.insert(0, str(LAB / 'src'))
    for name in ('src/nfl2/selectors.py', 'src/nfl2/live_a5.py'):
        assert (LAB/name).read_bytes() == subprocess.check_output(['git','-C',str(LAB),'show','2dc116c:'+name])
    from nfl2.selectors import select_expected_max
    fr = state['salaryfix']['frame']
    orders = state['salaryfix']['orders']
    index = {str(x): i for i,x in enumerate(fr.id)}
    roster = np.array([[index[x] for x in o] for o in orders])
    def totals(bank, rows):
        return np.stack([bank[row].sum(axis=0, dtype=np.float32) for row in rows])
    selection = np.concatenate([totals(state['salaryfix']['banks'][k], roster)
                                for k in ('I_selection','H_selection')], axis=1)
    baseline = list(map(int, select_expected_max(selection, 97)))
    assert baseline == chain['books']['salaryfix_emax']['candidate_indices']
    books = {k:old['books'][k] for k in ('emax','coverage220','excess220')}
    assert books['emax'] == baseline
    assert coverage(selection,97) == books['coverage220']
    assert list(map(int,select_expected_max(np.maximum(selection-220,0),97))) == books['excess220']
    pd.testing.assert_frame_equal(fr,pd.read_parquet(precision['frame_path']))
    del selection
    pieces = []
    for component in ('I','H'):
        pieces.append(totals(state['salaryfix']['banks'][component+'_selection'],roster))
        for i in range(1,5):
            a=np.load(opened(precision['arrays'][component+'_selection_'+str(i)]),allow_pickle=False)
            assert a.shape==(len(fr),10000) and a.dtype==np.float32 and np.isfinite(a).all()
            pieces.append(totals(a,roster))
    selection=np.concatenate(pieces,axis=1);del pieces,a
    assert selection.shape==(1600,100000)
    books['emax_5x']=list(map(int,select_expected_max(selection,97)))
    print('PRECISION_EMAX_SELECTED',flush=True)
    books['coverage220_5x']=coverage(selection,97)
    print('PRECISION_COVERAGE_SELECTED',flush=True)
    books['excess220_5x']=list(map(int,select_expected_max(np.maximum(selection-220,0),97)))
    fresh={}
    for component in ('I','H'):
        a=np.load(opened(precision['arrays'][component+'_audit']),allow_pickle=False)
        assert a.shape==(len(fr),10000) and a.dtype==np.float32 and np.isfinite(a).all()
        fresh[component+'_audit']=a
    state['fresh_salaryfix']=dict(frame=fr,banks=fresh)
    assert all(len(b) == len(set(b)) == 97 for b in books.values())
    print('PRECISION_ALL_BOOKS_FROZEN', flush=True)
    helper = runpy.run_path(str(R / '2026-09-19-repaired-chain-read.py'))
    regions, uncertainty = helper['REGIONS'], helper['uncertainty']
    raw = subprocess.check_output(['git','-C',str(LAB),'show','e7255e9:results/contest/milly_winners.json'])
    assert hashlib.sha256(raw).hexdigest() == '4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners = np.asarray(sorted(json.loads(raw).values()), float)
    def measure(maxima):
        return {**helper['metrics'](maxima, winners), 'p194': (maxima>=194).astype(float),
                'p240': (maxima>=240).astype(float), 'excess220': np.maximum(maxima-220,0)}
    selection_metrics = {k:{region:{m:float(x.mean()) for m,x in measure(selection[np.asarray(b)[sl]].max(axis=0).astype(float)).items()}
                            for region,sl in regions.items()} for k,b in books.items()}
    del selection
    samples, metrics, support = {}, {}, {}
    for arm,s in state.items():
        assert time.monotonic()-started < 580
        index = {str(x): i for i,x in enumerate(s['frame'].id)}
        for component in ('I_audit','H_audit'):
            law = arm+'_'+component
            samples[law], metrics[law], support[law] = {}, {}, {}
            for name,b in books.items():
                selected_orders = [orders[i] for i in b]
                missing = sorted({x for o in selected_orders for x in o}-set(index))
                support[law][name] = dict(fully_scoreable=not missing, missing_players=missing)
                if missing:
                    continue
                rows = [[index[x] for x in o] for o in selected_orders]
                t = totals(s['banks'][component], rows)
                samples[law][name] = {region:measure(t[sl].max(axis=0).astype(float)) for region,sl in regions.items()}
                metrics[law][name] = {region:{m:float(x.mean()) for m,x in v.items()}
                                      for region,v in samples[law][name].items()}
    laws = {k:[k] for k in samples}
    laws.update({a+'_equal_mixture':[a+'_I_audit',a+'_H_audit'] for a in state})
    for law,parts in laws.items():
        if len(parts)==1:
            continue
        metrics[law] = {b:{region:{m:float(np.mean([metrics[p][b][region][m] for p in parts]))
                       for m in metrics[parts[0]][b][region]} for region in regions}
                       for b in books if all(b in metrics[p] for p in parts)}
    pairs=[(b+'_5x',b) for b in ('emax','coverage220','excess220')]
    pairs += [(b+'_5x','emax') for b in ('coverage220','excess220')]
    contrasts = {after+'-minus-'+before:{law:{region:{m:uncertainty([
        samples[p][after][region][m]-samples[p][before][region][m] for p in parts])
        for m in samples[parts[0]][after][region]} for region in regions}
        for law,parts in laws.items() if all(after in samples[p] and before in samples[p] for p in parts)}
        for after,before in pairs}
    result = dict(source_sha256=sha(__file__), input_result_sha256=sha(R/'2026-09-19-repaired-chain-d1600-read.json'),
        precision_banks_result_sha256=sha(R/'2026-09-19-selection-precision-banks.json'),
        primary_audit='fresh_salaryfix_equal_mixture', selection_draws_per_component=50000,
        baseline_order_exact=True, books=books, first_rosters={k:orders[b[0]] for k,b in books.items()},
        overlap_vs_emax={k:dict(shared_members=len(set(b)&set(baseline)),same_first=b[0]==baseline[0],
                               same_ranks=sum(x==y for x,y in zip(b,baseline))) for k,b in books.items()},
        metrics=metrics, contrasts=contrasts, selection_metrics=selection_metrics, support=support,
        elapsed_seconds=time.monotonic()-started, global_proxy_bandwidth=8,
        scope='Fivefold selection precision under unchanged fitted laws; fresh primary audit, previous audits secondary; no NFL outcomes or adoption.')
    with OUT.open('x') as f:
        json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(overlap=result['overlap_vs_emax'], elapsed_seconds=result['elapsed_seconds'],
                         fresh_repaired_mixture={k:v['prefix97'] for k,v in metrics['fresh_salaryfix_equal_mixture'].items()}),indent=2))


if __name__ == '__main__':
    main()
