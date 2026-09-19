"""Seven fixed selection-stage books; same pool, bounded greedy exposure caps."""
import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import time

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918/d6400-actual-dose-20260919')
OUT = ROOT / 'exposure-cap-proposals'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def capped(t, roster, entries, limit, chunk=128):
    assert t.ndim == 2 and roster.shape == (len(t), 9) and entries <= len(t)
    assert np.isfinite(t).all() and all(len(set(row)) == 9 for row in roster)
    assert 0 < limit <= entries
    counts = np.zeros(int(roster.max()) + 1, int)
    current = np.full(t.shape[1], -np.inf, np.float64)
    taken = np.zeros(len(t), bool); book = []
    for _ in range(entries):
        forbidden = taken | (counts[roster] >= limit).any(axis=1)
        assert not forbidden.all(), 'cap cannot complete the required K; no automatic relaxation'
        base = current.mean() if book else 0.
        gains = np.empty(len(t), float)
        for start in range(0, len(t), chunk):
            gains[start:start + chunk] = np.maximum(t[start:start + chunk].astype(float), current).mean(axis=1) - base
        gains[forbidden] = -np.inf
        chosen = int(np.argmax(gains))
        assert np.isfinite(gains[chosen])
        book.append(chosen); taken[chosen] = True
        counts[roster[chosen]] += 1
        current = np.maximum(current, t[chosen])
    assert counts.max() <= limit and len(set(book)) == entries
    return book


def mechanics():
    r = np.arange(27).reshape(3, 9)
    r[1, 0] = r[0, 0]
    t = np.asarray([[10, 10], [11, 0], [0, 9]], np.float32)
    assert capped(t, r, 2, 1) == [0, 2]
    assert capped(t, r, 2, 2) == [0, 1]
    assert capped(np.ones((3, 2)), r, 2, 2) == [0, 1]
    try:
        capped(t[:2], r[:2], 2, 1)
    except AssertionError as exc:
        assert 'cannot complete' in str(exc)
    else:
        raise AssertionError('infeasible cap silently relaxed')


def main():
    mechanics(); signal.alarm(600); started = time.monotonic()
    pp = ROOT / 'reselection-proposals/frozen-books.json'
    assert sha(pp) == '87262e06f43a6352f7b92df1a4aacd5d6913fb9c0abb759e630b69b86cd38ecd'
    prior = json.loads(pp.read_text())
    sp = HERE / '2026-09-19-participation-reselect-v3.py'
    assert sha(sp) == '1f63c705e53e7e7508f210bad431544685e5208a659c27e4a518cee40e475ae4'
    spec = importlib.util.spec_from_file_location('cap_selector', sp)
    selector = importlib.util.module_from_spec(spec); spec.loader.exec_module(selector)
    selector.runtime(Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs'))
    from nfl2.validator import validate_roster
    source = ROOT / 'source'
    for r in json.loads((source / 'MANIFEST.json').read_text())['objects']:
        assert sha(source / r['name']) == r['sha256_local']
    fr = pd.read_parquet(source / 'frame.parquet', columns=['id', 'pos', 'team', 'opp', 'salary'])
    op = ROOT / 'selection-parity/candidate_orders.json'
    assert sha(op) == prior['candidate_orders_sha256']
    orders = json.loads(op.read_text()); index = {x: i for i, x in enumerate(fr.id)}
    roster = np.asarray([[index[x] for x in o] for o in orders])
    excluded = set(prior['eligibility']['excluded_player_ids'])
    keep = [i for i, o in enumerate(orders) if not set(o) & excluded]
    assert len(keep) == 3366
    f = fr.set_index('id'); args = [f[c].to_dict() for c in ('pos', 'team', 'opp', 'salary')]
    for i in keep:
        assert not validate_roster(orders[i], *args, salary_floor=49000, qb_stack_min=2,
            bring_back_min=1, forbid_rb_vs_dst=True, forbid_two_rb_same_team=True)
    parity = json.loads((ROOT / 'selection-parity/receipt.json').read_text())
    tp = ROOT / 'selection-parity/selection_totals.npy'
    assert sha(tp) == parity['selection_totals_sha256'] and parity['source_control_exact']
    p = np.asarray(prior['probabilities'])
    books = {'control': prior['books']['control']}
    for law in ('raw', 'pmix'):
        if law == 'raw':
            t = np.load(tp, mmap_mode='r', allow_pickle=False)[keep]
        else:
            banks = {n: np.load(source / fn, allow_pickle=False) for n, fn in
                [('I', 'incumbent_player_scores.npy'), ('H', 'corrected_hsim_player_scores.npy')]}
            rng = np.random.default_rng(selector.SEED)
            for i in np.flatnonzero((p < 1) & (p > 0)):
                for bank in banks.values():
                    bank[i, rng.random(bank.shape[1]) >= p[i]] = 0.
            t = selector.totals(banks, roster[keep])
        ordinary = [keep[i] for i in selector.greedy(t, 97)]
        assert ordinary == prior['books'][law + '_greedy'], 'uncapped control parity failed'
        books[law] = ordinary
        for limit in (48, 38):
            books[law + '_cap' + str(limit)] = [keep[i] for i in capped(t, roster[keep], 97, limit)]
            print('FROZEN', law, limit, flush=True)
        del t
    exposures = {}
    for name, book in books.items():
        assert len(book) == len(set(book)) == 97 and set(book) <= set(keep)
        counts = np.bincount(roster[book].ravel(), minlength=len(fr))
        exposures[name] = dict(player_counts={str(fr.id.iloc[i]): int(n) for i, n in enumerate(counts) if n},
            maximum_player_exposure=int(counts.max()), expected_inactive_player_slots=float(np.dot(counts, 1 - p)),
            uncertain_lineups=int(sum(any(p[i] < 1 for i in roster[c]) for c in book)))
        if '_cap' in name:
            assert counts.max() <= int(name.split('_cap')[1])
    result = dict(schema='d6400-exposure-caps/v1', books=books, exposures=exposures,
        source_reader_sha256=sha(__file__), source_packet_sha256=sha(pp),
        protocol_sha256=sha(HERE.parents[1] / '2026-09-19-d6400-exposure-cap-protocol.md'),
        source_frame_sha256=prior['source_frame_sha256'], candidate_orders_sha256=sha(op),
        probabilities=p.tolist(), eligibility=prior['eligibility'], stress_player_ids=prior['stress_player_ids'],
        promotions={}, all_books_legal=True, both_uncapped_controls_exact=True,
        audit_seeds=dict(I=24260919, H=25260919, availability=20260919064),
        primary='pmix_cap48_minus_pmix', order_stage='greedy before delivery vetting, except actual control',
        current_outcomes_read=False, audits_read=False, seconds=time.monotonic() - started)
    OUT.mkdir(exist_ok=False)
    with (OUT / 'frozen-books.json').open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    print('FROZEN_BOOKS_SHA256', sha(OUT / 'frozen-books.json'), 'SECONDS', result['seconds'], flush=True)


if __name__ == '__main__':
    main()
