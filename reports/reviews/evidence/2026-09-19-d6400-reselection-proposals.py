"""Freeze full eligible reselections and delivered-order variants; no audit read."""
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import runpy
import signal
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
from google.cloud import bigquery

HERE = Path(__file__).parent
ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918/d6400-actual-dose-20260919')
OUT = ROOT / 'reselection-proposals'
TOOLS = Path('/home/erich/projects/.nfl2-worktrees/prereg101-review-reply/handoffs/runners/rung1c-v42')
LAB = Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(name, expected):
    p = HERE / name
    assert sha(p) == expected
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    signal.alarm(600)
    started = time.monotonic()
    selector = load('2026-09-19-participation-reselect-v3.py', '1f63c705e53e7e7508f210bad431544685e5208a659c27e4a518cee40e475ae4')
    provider = load('2026-09-19-participation-provider-capture.py', '5fb5e92311fdad7f846858b0ae80655c093d1e2cd2db7a407159b5a760815fc1')
    promoter = load('2026-09-19-first-delivered-promotion.py', '36ffcbcedc9b1b46d5aea5c9d04b425f0b842e3569a53c20802ef39f36af959f')
    selector.runtime(LAB)
    sys.path.insert(0, str(HERE.parents[2] / 'src'))
    from nfl_dfs.inference.week1_participation_mixture import validate_participation_map_v1
    from nfl2.validator import validate_roster
    from nfl2.live import dk_csv
    source = ROOT / 'source'
    for r in json.loads((source / 'MANIFEST.json').read_text())['objects']:
        assert sha(source / r['name']) == r['sha256_local']
    pp = ROOT / 'frontier-proposals/frozen-books.json'
    assert sha(pp) == 'cd604b8fc0c90c27043bd04d2f324acfbe124987d467a480acde36210a657143'
    prior = json.loads(pp.read_text())
    excluded = set(prior['eligibility']['excluded_player_ids'])
    control = prior['books']['control']
    assert sha(ROOT / 'host-v43-rehearsal/replaced/book.csv') == prior['current_book_sha256']
    order_path = ROOT / 'selection-parity/candidate_orders.json'
    parity = json.loads((ROOT / 'selection-parity/receipt.json').read_text())
    assert parity['source_control_exact'] and parity['source_summation_exact']
    assert sha(order_path) == parity['candidate_orders_sha256']
    total_path = ROOT / 'selection-parity/selection_totals.npy'
    assert sha(total_path) == parity['selection_totals_sha256']
    totals = np.load(total_path, mmap_mode='r', allow_pickle=False)
    orders = json.loads(order_path.read_text())
    fr = pd.read_parquet(source / 'frame.parquet', columns=selector.FRAME_COLUMNS)
    assert fr.id.is_unique and fr.dk_player_id.is_unique and len(fr) == 429
    index = {x: i for i, x in enumerate(fr.id)}
    roster = np.asarray([[index[x] for x in o] for o in orders])
    f = fr.set_index('id')
    val_args = [f[n].to_dict() for n in ('pos', 'team', 'opp', 'salary')]
    keep = []
    for i, o in enumerate(orders):
        if not (set(o) & excluded):
            assert not validate_roster(o, *val_args, salary_floor=49000, qb_stack_min=2,
                bring_back_min=1, forbid_rb_vs_dst=True, forbid_two_rb_same_team=True)
            keep.append(i)
    assert len(keep) == 3366 and len(excluded) == 42 and set(control) <= set(keep)
    cap_path = ROOT / 'status-v1/capture.json'
    assert sha(cap_path) == '915a2300075cfa8ef36f4ee594c303fe122ca63972d4f4e14be77a9fc0651b04'
    capture = json.loads(cap_path.read_text())
    inj, dk, cutoff, _ = provider.load_capture(cap_path.parent, as_of=capture['cutoff'])
    mp = ROOT.parent / 'participation-transfer-support/participation-map.json'
    assert sha(mp) == selector.MAP_SHA
    p, unavailable, states = selector.participation(fr, inj, dk, cutoff,
        validate_participation_map_v1(json.loads(mp.read_text())))
    assert unavailable <= excluded
    fresh = dk.set_index('dk_player_id').loc[fr.dk_player_id]
    assert np.array_equal(fresh.salary.to_numpy(), fr.salary.to_numpy())
    assert np.array_equal(fresh.dk_draftable_id.to_numpy(), fr.dk_draftable_id.to_numpy())
    OUT.mkdir(exist_ok=False)
    (OUT / 'RESEARCH-ONLY-NOT-FOR-UPLOAD').write_text('Frozen research; no operational adoption.\n')
    raw = [keep[i] for i in selector.greedy(totals[keep], 97)]
    print('RAW_RESELECTED', flush=True)
    banks = {n: np.load(source / fn, allow_pickle=False) for n, fn in
        [('I', 'incumbent_player_scores.npy'), ('H', 'corrected_hsim_player_scores.npy')]}
    rng = np.random.default_rng(selector.SEED)
    for i in np.flatnonzero((p < 1) & (p > 0)):
        for bank in banks.values():
            bank[i, rng.random(bank.shape[1]) >= p[i]] = 0.
    pmix_totals = selector.totals(banks, roster)
    pmix = [keep[i] for i in selector.greedy(pmix_totals[keep], 97)]
    print('PMIX_RESELECTED', flush=True)
    vetter = TOOLS / 'vet_book_v2.1.py'
    assert sha(vetter) == 'a3c8aede89e13087f7ba861a04bdb629fe62f9effea0c2dcadb429c5e9f984ff'
    qroot = ROOT / 'host-v43-rehearsal'
    qpath = qroot / 'query-captures.json'
    assert sha(qpath) == '0c8e1fd1acbb4598325392fef45fc0daaf14631fd9fc9011d2083372c11954a4'
    qrecords = json.loads(qpath.read_text())[1:5]
    qframes = []
    for q in qrecords:
        assert sha(qroot / q['file']) == q['sha256']
        qframes.append(pd.read_parquet(qroot / q['file']))
    qbflags = qroot / 'qb-flags.csv'
    original_read = pd.read_parquet
    vet_receipts, books, promotions = {}, {'control': control, 'raw_greedy': raw, 'pmix_greedy': pmix}, {}
    for arm, b, own in [('control', control, totals), ('raw', raw, totals), ('pmix', pmix, pmix_totals)]:
        run = OUT / arm
        run.mkdir()
        fr.to_parquet(run / 'frame.parquet', index=False)
        (run / 'receipt.json').write_text(json.dumps(dict(kind='RESEARCH_INPUT', source_manifest_sha256=sha(source / 'MANIFEST.json'))))
        dk_csv([SimpleNamespace(players=[{'id': x} for x in orders[i]]) for i in b], fr, run / 'book.csv')
        calls = []
        def query(client, sql, **kwargs):
            i = len(calls)
            assert i < 4 and sql == qrecords[i]['sql']
            actual = kwargs['job_config'].to_api_repr()['query']['queryParameters']
            expected = qrecords[i]['config']['query']['queryParameters']
            assert actual == expected, 'query parameters differ from captured whole-frame inputs'
            calls.append(i)
            return SimpleNamespace(result=lambda: SimpleNamespace(to_dataframe=lambda: qframes[i].copy(deep=True)))
        def restricted(path, *args, **kwargs):
            if Path(path).name == 'frame.parquet':
                assert not args and 'columns' not in kwargs
                return original_read(path, columns=selector.FRAME_COLUMNS, **kwargs)
            return original_read(path, *args, **kwargs)
        argv = [str(vetter), str(run), '--k', '30', '--season', '2026', '--week', '2',
                '--qb-flags', str(qbflags), '--output-dir', str(run / 'vetted')]
        with (run / 'vet.log').open('x') as log, patch.object(sys, 'argv', argv), \
             patch.object(bigquery.Client, 'query', query), patch.object(pd, 'read_parquet', restricted), \
             contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            runpy.run_path(str(vetter), run_name='__main__')
        assert calls == list(range(4))
        rec = json.loads((run / 'vetted/vetting.json').read_text())
        order = list(range(97)) if arm == 'control' else [n - 1 for n in rec['order_source_ranks']]
        delivered = [b[i] for i in order]
        clean = [not rec['lineups'][i]['hard'] and not rec['lineups'][i]['material'] for i in order]
        key = 'control' if arm == 'control' else arm + '_vetted'
        books[key] = delivered
        books[key + '_promoted'], promotions[key] = promoter.promote(delivered, clean, own)
        vet_receipts[arm] = dict(vetting_sha256=sha(run / 'vetted/vetting.json'),
            input_book_sha256=sha(run / 'book.csv'), order=order, delivered_clean_or_soft=clean,
            current_control_reordered=False if arm == 'control' else None)
    for b in books.values():
        assert len(b) == len(set(b)) == 97 and set(b) <= set(keep)
    exposure = {}
    for name, b in books.items():
        counts = np.bincount(roster[b].ravel(), minlength=len(fr))
        exposure[name] = dict(player_counts={str(fr.id.iloc[i]): int(n) for i, n in enumerate(counts) if n},
            expected_inactive_player_slots=float(np.dot(counts, 1 - p)),
            uncertain_lineups=int(sum(any(p[i] < 1 for i in roster[c]) for c in b)),
            maximum_player_exposure=int(counts.max()))
    stress = sorted(exposure['control']['player_counts'], key=lambda i: (-exposure['control']['player_counts'][i], i))[:10]
    result = dict(schema='d6400-full-reselection/v1', books=books, promotions=promotions,
        exposures=exposure, stress_player_ids=stress, statuses=states, probabilities=p.tolist(),
        eligibility=prior['eligibility'], vetting=vet_receipts, source_reader_sha256=sha(__file__),
        protocol_sha256=sha(HERE.parents[1] / '2026-09-19-d6400-reselection-protocol.md'),
        source_manifest_sha256=sha(source / 'MANIFEST.json'), current_book_sha256=prior['current_book_sha256'],
        status_capture_sha256=sha(cap_path), query_capture_sha256=sha(qpath), qb_flags_sha256=sha(qbflags),
        vetter_sha256=sha(vetter), promotion_sha256=sha(HERE / '2026-09-19-first-delivered-promotion.py'),
        selection_seed=selector.SEED, map_sha256=sha(mp), candidate_orders_sha256=sha(order_path),
        source_frame_columns=selector.FRAME_COLUMNS, source_frame_sha256=sha(source / 'frame.parquet'),
        all_books_legal=True, current_outcomes_read=False, audits_read=False,
        audit_seeds=dict(I=20260919, H=21260919, availability=20260919062), seconds=time.monotonic() - started)
    with (OUT / 'frozen-books.json').open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps(dict(book_sha256=sha(OUT / 'frozen-books.json'), promotions=promotions,
                         exposures={k: {a: v for a, v in r.items() if a != 'player_counts'} for k, r in exposure.items()},
                         seconds=result['seconds']), indent=2), flush=True)


if __name__ == '__main__':
    main()
