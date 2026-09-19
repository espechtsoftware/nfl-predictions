"""Read all frozen first-entry objectives; primary comparison is proxy vs mean."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
DEFAULT = Path('/home/erich/projects/review-evidence/overnight-20260918/d6400-actual-dose-20260919')
BOOK_SHA = 'b65abc84096a60efd4e0652bc3b76dfe97978151cb9847a777160bcc8d74dcc6'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(name, digest):
    p = HERE / name
    assert sha(p) == digest
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, default=DEFAULT)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    root = args.root
    out = args.output or root / 'first-entry-tail-result.json'
    assert not out.exists()
    started = time.monotonic()
    bp = root / 'first-entry-tail-proposals/frozen-books.json'
    assert sha(bp) == BOOK_SHA
    frozen = json.loads(bp.read_text())
    books = frozen['books']
    assert set(books) == {'control', 'mean', 'p220', 'proxy'} and not frozen['audits_read']
    apath = root / 'first-entry-tail-audit/receipt.json'
    audit = json.loads(apath.read_text())
    assert audit['both_selection_banks_exact'] and audit['frozen_books_sha256'] == BOOK_SHA
    assert audit['source_sha256'] == sha(HERE / '2026-09-19-d6400-first-entry-tail-audit-banks.py')
    helper = load('2026-09-19-repaired-chain-read.py', '30df46cd492dc45fa35b6da54285135bc2b8dc633cc33b157f2a390c7f5fb646')
    base = load('2026-09-19-participation-transfer.py', '9354142a7a88e0fa49f00c103c88ea7f040ddb1ecf732c6a9516915d650686c7')
    fp, op = root / 'source/frame.parquet', root / 'selection-parity/candidate_orders.json'
    assert sha(fp) == frozen['source_frame_sha256'] and sha(op) == frozen['candidate_orders_sha256']
    fr = pd.read_parquet(fp, columns=['id'])
    orders = json.loads(op.read_text()); index = {x: i for i, x in enumerate(fr.id)}
    roster = np.asarray([[index[x] for x in o] for o in orders])
    for b in books.values():
        assert len(b) == len(set(b)) == 97 and set(b) == set(books['control'])
        assert set(b[:30]) == set(books['control'][:30]) and b[30:] == books['control'][30:]
    banks = {}
    for name, r in audit['banks'].items():
        p = root / 'first-entry-tail-audit' / (name + '_audit.npy')
        assert sha(p) == r['sha256'] and r['seed'] == frozen['audit_seeds'][name]
        banks[name] = np.load(p, allow_pickle=False)
        assert banks[name].shape == (429, 10000) and np.isfinite(banks[name]).all()
    mixed, masks = base.mixed_pair(banks, np.asarray(frozen['probabilities']), frozen['audit_seeds']['availability'])
    wp = root / 'first-entry-tail-proposals/milly_winners.json'
    assert sha(wp) == '4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners = np.asarray(sorted(json.loads(wp.read_text()).values()), float)
    samples, metrics = {}, {}
    for assumption, pair in [('all_active', banks), ('participation', mixed)]:
        for component, bank in pair.items():
            law = assumption + '_' + component
            samples[law], metrics[law] = {}, {}
            for name, book in books.items():
                totals = base.totals(bank, roster[book])
                samples[law][name], metrics[law][name] = {}, {}
                for region, sl in helper.REGIONS.items():
                    m = helper.metrics(totals[sl].max(axis=0).astype(float), winners)
                    samples[law][name][region] = m
                    metrics[law][name][region] = {k: float(v.mean()) for k, v in m.items()}
    laws = {name: [name] for name in samples}
    for assumption in ('all_active', 'participation'):
        name, parts = assumption + '_mixture', [assumption + '_I', assumption + '_H']
        laws[name] = parts
        metrics[name] = {b: {r: {m: float(np.mean([metrics[v][b][r][m] for v in parts]))
            for m in ('emax', 'p220', 'global_proxy')} for r in helper.REGIONS} for b in books}
    pairs = {name + '_minus_control': (name, 'control') for name in books if name != 'control'}
    pairs.update({name + '_minus_mean': (name, 'mean') for name in ('p220', 'proxy')})
    contrasts = {key: {law: {r: {m: helper.uncertainty([
        samples[v][a][r][m] - samples[v][b][r][m] for v in parts])
        for m in ('emax', 'p220', 'global_proxy')} for r in helper.REGIONS}
        for law, parts in laws.items()} for key, (a, b) in pairs.items()}
    for c in contrasts.values():
        for law in laws:
            for r in ('prefix30', 'prefix40', 'prefix80', 'prefix90', 'prefix97',
                      'block31_31', 'block32_33', 'block34_43', 'block44_53',
                      'block54_63', 'block64_79', 'block80_95', 'block96_97'):
                assert all(v['delta'] == 0 and v['monte_carlo_se'] == 0 for v in c[law][r].values())
    result = dict(reader_sha256=sha(__file__), frozen_books_sha256=BOOK_SHA,
        audit_receipt_sha256=sha(apath), audit_seeds=frozen['audit_seeds'], masks=masks,
        books=books, choices=frozen['choices'], metrics=metrics, contrasts=contrasts,
        primary='proxy_minus_mean', secondary='p220_minus_mean', all_arms_reported=True,
        current_outcomes_read=False, no_audit_selected_book=True,
        scope='Post-inspection fixed-law head-objective comparison; MC intervals are not NFL efficacy.',
        seconds=time.monotonic() - started)
    with out.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    print(json.dumps({k: {r: contrasts[k]['all_active_mixture'][r] for r in ('prefix1', 'block2_24')}
        for k in ('mean_minus_control', 'proxy_minus_control', 'proxy_minus_mean')}, indent=2))
    print('RESULT_SHA256', sha(out), flush=True)


if __name__ == '__main__':
    main()
