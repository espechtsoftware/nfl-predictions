"""Fresh all-arm full-reselection read, including fixed concentration stresses."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918/d6400-actual-dose-20260919')
LAB = Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
BOOK_SHA = '87262e06f43a6352f7b92df1a4aacd5d6913fb9c0abb759e630b69b86cd38ecd'
PAIRS = {
    'raw_vetted_minus_control': ('raw_vetted', 'control'),
    'pmix_vetted_minus_control': ('pmix_vetted', 'control'),
    'control_promotion': ('control_promoted', 'control'),
    'raw_promotion': ('raw_vetted_promoted', 'raw_vetted'),
    'pmix_promotion': ('pmix_vetted_promoted', 'pmix_vetted'),
    'raw_vetting': ('raw_vetted', 'raw_greedy'),
    'pmix_vetting': ('pmix_vetted', 'pmix_greedy'),
    'pmix_minus_raw_vetted': ('pmix_vetted', 'raw_vetted'),
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(name, digest):
    p = HERE / name
    assert sha(p) == digest
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    started = time.monotonic()
    output = ROOT / 'reselection-audit-result.json'
    assert not output.exists()
    bp = ROOT / 'reselection-proposals/frozen-books.json'
    assert sha(bp) == BOOK_SHA
    frozen = json.loads(bp.read_text())
    books = frozen['books']
    assert len(books) == 8 and frozen['all_books_legal'] and not frozen['audits_read']
    audit_path = ROOT / 'reselection-fresh-audit/receipt.json'
    audit = json.loads(audit_path.read_text())
    assert audit['both_selection_banks_exact'] and audit['frozen_books_sha256'] == BOOK_SHA
    assert audit['source_sha256'] == sha(HERE / '2026-09-19-d6400-reselection-audit-banks.py')
    helper = load('2026-09-19-repaired-chain-read.py', '30df46cd492dc45fa35b6da54285135bc2b8dc633cc33b157f2a390c7f5fb646')
    base = load('2026-09-19-participation-transfer.py', '9354142a7a88e0fa49f00c103c88ea7f040ddb1ecf732c6a9516915d650686c7')
    assert sha(ROOT / 'source/frame.parquet') == frozen['source_frame_sha256']
    fr = pd.read_parquet(ROOT / 'source/frame.parquet', columns=['id', 'display_name'])
    order_path = ROOT / 'selection-parity/candidate_orders.json'
    assert sha(order_path) == frozen['candidate_orders_sha256']
    orders = json.loads(order_path.read_text())
    index = {x: i for i, x in enumerate(fr.id)}
    roster = np.asarray([[index[x] for x in o] for o in orders])
    excluded = set(frozen['eligibility']['excluded_player_ids'])
    for b in books.values():
        assert len(b) == len(set(b)) == 97 and not any(set(orders[i]) & excluded for i in b)
    banks = {}
    for name, r in audit['banks'].items():
        assert sha(r['path']) == r['sha256'] and r['seed'] == frozen['audit_seeds'][name]
        banks[name] = np.load(r['path'], allow_pickle=False)
        assert banks[name].shape == (429, 10000) and np.isfinite(banks[name]).all()
    p = np.asarray(frozen['probabilities'])
    assert p.shape == (429,) and ((0 <= p) & (p <= 1)).all()
    mixed, masks = base.mixed_pair(banks, p, frozen['audit_seeds']['availability'])
    raw = subprocess.check_output(['git', '-C', str(LAB), 'show', 'e7255e9:results/contest/milly_winners.json'])
    assert hashlib.sha256(raw).hexdigest() == '4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners = np.asarray(sorted(json.loads(raw).values()), float)
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
    pairs = dict(PAIRS)
    pairs.update({b + '_vs_control': (b, 'control') for b in books if b != 'control'})
    contrasts = {key: {law: {r: {m: helper.uncertainty([
        samples[v][a][r][m] - samples[v][b][r][m] for v in parts])
        for m in ('emax', 'p220', 'global_proxy')} for r in helper.REGIONS}
        for law, parts in laws.items()} for key, (a, b) in pairs.items()}
    for key in ('control_promotion', 'raw_promotion', 'pmix_promotion'):
        for law in laws:
            for r in ('prefix30', 'prefix40', 'prefix80', 'prefix90', 'prefix97',
                      'block31_31', 'block32_33', 'block34_43', 'block44_53',
                      'block54_63', 'block64_79', 'block80_95', 'block96_97'):
                assert all(v['delta'] == 0 and v['monte_carlo_se'] == 0 for v in contrasts[key][law][r].values())
    for key in ('raw_vetting', 'pmix_vetting'):
        assert all(v['delta'] == 0 for law in laws for v in contrasts[key][law]['prefix97'].values())
    stress = {}
    for pid in frozen['stress_player_ids']:
        entry = dict(player_name=fr.display_name.iloc[index[pid]], player_id=pid, components={})
        ss = {}
        for component, bank in banks.items():
            forced = bank.copy()
            forced[index[pid]] = 0.
            ss[component], entry['components'][component] = {}, {}
            for name, book in books.items():
                totals = base.totals(forced, roster[book])
                ss[component][name], entry['components'][component][name] = {}, {}
                for region in ('prefix1', 'prefix97'):
                    m = helper.metrics(totals[helper.REGIONS[region]].max(axis=0).astype(float), winners)
                    ss[component][name][region] = m
                    entry['components'][component][name][region] = {
                        metric: dict(value=float(vals.mean()), change_from_active=helper.uncertainty([
                            vals - samples['all_active_' + component][name][region][metric]]))
                        for metric, vals in m.items()}
        entry['mixture'] = {b: {r: {m: dict(
            value=float(np.mean([ss[c][b][r][m].mean() for c in banks])),
            change_from_active=helper.uncertainty([ss[c][b][r][m] - samples['all_active_' + c][b][r][m] for c in banks]),
            versus_stressed_control=helper.uncertainty([ss[c][b][r][m] - ss[c]['control'][r][m] for c in banks]))
            for m in ('emax', 'p220', 'global_proxy')} for r in ('prefix1', 'prefix97')} for b in books}
        stress[pid] = entry
    result = dict(reader_sha256=sha(__file__), frozen_books_sha256=BOOK_SHA,
        audit_receipt_sha256=sha(audit_path), audit_seeds=frozen['audit_seeds'], masks=masks,
        books=books, promotions=frozen['promotions'], exposures=frozen['exposures'],
        metrics=metrics, contrasts=contrasts, comparison_pairs=pairs, stress=stress,
        all_eight_arms_reported=True, no_audit_selected_book=True, current_outcomes_read=False,
        scope='Fixed-law conditional simulation and single-player-zero stress, not NFL efficacy or a cap evaluation.',
        seconds=time.monotonic() - started)
    with output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps({b: {r: contrasts[b]['participation_mixture'][r] for r in ('prefix1', 'prefix30', 'prefix97')}
        for b in ('raw_vetted_minus_control', 'pmix_vetted_minus_control', 'control_promotion')}, indent=2))
    print('RESULT_SHA256', sha(output), 'SECONDS', result['seconds'], flush=True)


if __name__ == '__main__':
    main()
