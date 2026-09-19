"""Read every frozen proposal under fresh, fixed raw and participation audits."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918/d6400-actual-dose-20260919')
LAB = Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
BOOK_SHA = 'cd604b8fc0c90c27043bd04d2f324acfbe124987d467a480acde36210a657143'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(name, expected):
    path = HERE / name
    assert sha(path) == expected
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    started = time.monotonic()
    out = ROOT / 'frontier-audit-result.json'
    assert not out.exists()
    assert sha(ROOT / 'frontier-proposals/frozen-books.json') == BOOK_SHA
    frozen = json.loads((ROOT / 'frontier-proposals/frozen-books.json').read_text())
    books = frozen['books']
    audit = json.loads((ROOT / 'fresh-audit/receipt.json').read_text())
    assert audit['both_selection_banks_exact'] and audit['frozen_books_sha256'] == BOOK_SHA
    assert audit['source_sha256'] == '777e8a660a7a6574e2ad176c3064da6cc840bf65ec8408926e47592192ad5565'
    selector = load('2026-09-19-participation-reselect-v3.py', '1f63c705e53e7e7508f210bad431544685e5208a659c27e4a518cee40e475ae4')
    helper = load('2026-09-19-repaired-chain-read.py', '30df46cd492dc45fa35b6da54285135bc2b8dc633cc33b157f2a390c7f5fb646')
    base = load('2026-09-19-participation-transfer.py', '9354142a7a88e0fa49f00c103c88ea7f040ddb1ecf732c6a9516915d650686c7')
    provider = load('2026-09-19-participation-provider-capture.py', '5fb5e92311fdad7f846858b0ae80655c093d1e2cd2db7a407159b5a760815fc1')
    fr = pd.read_parquet(ROOT / 'source/frame.parquet', columns=selector.FRAME_COLUMNS)
    cap_path = ROOT / 'status-v1/capture.json'
    assert sha(cap_path) == '915a2300075cfa8ef36f4ee594c303fe122ca63972d4f4e14be77a9fc0651b04'
    cap = json.loads(cap_path.read_text())
    inj, dk, cutoff, _ = provider.load_capture(cap_path.parent, as_of=cap['cutoff'])
    map_path = ROOT.parent / 'participation-transfer-support/participation-map.json'
    assert sha(map_path) == selector.MAP_SHA
    sys.path.insert(0, str(HERE.parents[2] / 'src'))
    from nfl_dfs.inference.week1_participation_mixture import validate_participation_map_v1
    probabilities, unavailable, states = selector.participation(fr, inj, dk, cutoff,
        validate_participation_map_v1(json.loads(map_path.read_text())))
    excluded = set(frozen['eligibility']['excluded_player_ids'])
    assert unavailable <= excluded
    orders = json.loads((ROOT / 'selection-parity/candidate_orders.json').read_text())
    index = {v: i for i, v in enumerate(fr.id)}
    roster = np.asarray([[index[v] for v in o] for o in orders])
    for b in books.values():
        assert len(b) == len(set(b)) == 97
        assert not any(set(orders[i]) & excluded for i in b)
    banks = {}
    for name, r in audit['banks'].items():
        assert sha(r['path']) == r['sha256']
        banks[name] = np.load(r['path'], allow_pickle=False)
        assert banks[name].shape == (429, 10000) and np.isfinite(banks[name]).all()
    mixed, mask_receipts = base.mixed_pair(banks, probabilities, 20260919061)
    raw = subprocess.check_output(['git', '-C', str(LAB), 'show', 'e7255e9:results/contest/milly_winners.json'])
    assert hashlib.sha256(raw).hexdigest() == '4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners = np.asarray(sorted(json.loads(raw).values()), float)
    samples, metrics = {}, {}
    for assumption, pair in [('all_active', banks), ('participation', mixed)]:
        for component, bank in pair.items():
            name = assumption + '_' + component
            samples[name], metrics[name] = {}, {}
            for book_name, book in books.items():
                totals = base.totals(bank, roster[book])
                samples[name][book_name], metrics[name][book_name] = {}, {}
                for region, sl in helper.REGIONS.items():
                    m = helper.metrics(totals[sl].max(axis=0).astype(float), winners)
                    samples[name][book_name][region] = m
                    metrics[name][book_name][region] = {k: float(v.mean()) for k, v in m.items()}
    laws = {name: [name] for name in samples}
    for assumption in ('all_active', 'participation'):
        name, parts = assumption + '_mixture', [assumption + '_I', assumption + '_H']
        laws[name] = parts
        metrics[name] = {b: {r: {m: float(np.mean([metrics[p][b][r][m] for p in parts]))
                                 for m in ('emax', 'p220', 'global_proxy')} for r in helper.REGIONS} for b in books}
    contrasts = {b: {law: {region: {m: helper.uncertainty([
        samples[p][b][region][m] - samples[p]['control'][region][m] for p in parts])
        for m in ('emax', 'p220', 'global_proxy')} for region in helper.REGIONS}
        for law, parts in laws.items()} for b in books if b != 'control'}
    for b in contrasts:
        for law in contrasts[b]:
            for region in ('prefix1', 'prefix10', 'prefix20', 'prefix30', 'prefix40'):
                assert all(v['delta'] == 0 and v['monte_carlo_se'] == 0 for v in contrasts[b][law][region].values())
    result = dict(reader_sha256=sha(__file__), frozen_books_sha256=BOOK_SHA,
        audit_receipt_sha256=sha(ROOT / 'fresh-audit/receipt.json'), status_capture_sha256=sha(cap_path),
        participation_map_sha256=sha(map_path), availability_seed=20260919061, availability_masks=mask_receipts,
        books=books, decisions=frozen['decisions'], metrics=metrics, contrasts=contrasts, statuses=states,
        all_proposals_reported=True, no_audit_selected_budget=True, first40_exact=True, current_outcomes_read=False,
        seconds=time.monotonic() - started,
        scope='Exploratory conditional simulation comparison; intervals describe event Monte Carlo error, not NFL efficacy.')
    with out.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps({b: {a: contrasts[b][a]['prefix97'] for a in ('all_active_mixture', 'participation_mixture')}
                      for b in contrasts}, indent=2))
    print('RESULT_SHA256', sha(out), flush=True)


if __name__ == '__main__':
    main()
