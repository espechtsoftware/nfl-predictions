"""Freeze selection-only exchanges around the authenticated fresh v4.3 book."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918/d6400-actual-dose-20260919')
RUN, VET = ROOT / 'source', ROOT / 'host-v43-rehearsal/replaced'
OUT = ROOT / 'frontier-proposals'
LAB = Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
EXPECTED_BOOK = '86147c51b94b7abb960b88fb38396c457efc96adea66253db392506f78cfdb8b'
POLICY = 'c179892000f2ece60b4ac7258f6489848a245ee4e7ce034f92fa6cfe731595f3'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    started = time.monotonic()
    assert not OUT.exists()
    pp = HERE / '2026-09-19-selection-loss-frontier.py'
    assert sha(pp) == POLICY
    spec = importlib.util.spec_from_file_location('frozen_frontier', pp)
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    source_manifest = json.loads((RUN / 'MANIFEST.json').read_text())
    for r in source_manifest['objects']:
        assert sha(RUN / r['name']) == r['sha256_local']
    parity = json.loads((ROOT / 'selection-parity/receipt.json').read_text())
    assert parity['source_control_exact'] and parity['source_summation_exact']
    total_path = ROOT / 'selection-parity/selection_totals.npy'
    order_path = ROOT / 'selection-parity/candidate_orders.json'
    assert sha(total_path) == parity['selection_totals_sha256']
    assert sha(order_path) == parity['candidate_orders_sha256']
    assert sha(VET / 'book.csv') == EXPECTED_BOOK
    replaced = json.loads((VET / 'replace.json').read_text())
    assert replaced['status'] == 'OK' and replaced['required_k'] == 97 and replaced['admit_risky']
    for name, digest in replaced['output_sha256'].items():
        assert sha(VET / name) == digest
    for path, digest in replaced['input_sha256'].items():
        assert sha(path) == digest
    cols = ['id', 'display_name', 'dk_player_id', 'pos', 'team', 'opp', 'salary', 'status']
    fr = pd.read_parquet(RUN / 'frame.parquet', columns=cols)
    assert fr.id.is_unique and fr.dk_player_id.is_unique and fr.display_name.is_unique
    # The peer receipt uses names for display; require unique exact names before
    # resolving it once to stable player IDs. Every subsequent operation uses IDs.
    names = fr.set_index('display_name').id.to_dict()
    excluded = {names[name] for name in replaced['exclusion_set']}
    orders = json.loads(order_path.read_text())
    key = {frozenset(o): i for i, o in enumerate(orders)}
    assert len(key) == len(orders) == 6399
    dkmap = dict(zip(fr.dk_player_id.astype(str), fr.id))
    csv = pd.read_csv(VET / 'book.csv', dtype=str)
    book = [key[frozenset(dkmap[v] for v in row)] for row in csv.to_numpy()]
    assert len(book) == len(set(book)) == 97
    sys.path.insert(0, str(LAB / 'src'))
    from nfl2.validator import validate_roster
    f = fr.set_index('id')
    args = [f[n].to_dict() for n in ('pos', 'team', 'opp', 'salary')]
    admissible = np.zeros(len(orders), bool)
    illegal = 0
    for i, o in enumerate(orders):
        if set(o) & excluded:
            continue
        problems = validate_roster(o, *args, salary_floor=49000, qb_stack_min=2, bring_back_min=1,
                                  forbid_rb_vs_dst=True, forbid_two_rb_same_team=True)
        illegal += bool(problems)
        admissible[i] = not problems
    assert admissible[book].all()
    totals = np.load(total_path, mmap_mode='r', allow_pickle=False)
    assert totals.shape == (6399, 20000) and totals.dtype == np.float32
    result = policy.proposals(totals, book, admissible)
    result.update(source_reader_sha256=sha(__file__), policy_sha256=POLICY,
        protocol_sha256=sha(HERE.parents[1] / '2026-09-19-selection-loss-frontier-protocol.md'),
        source_manifest_sha256=sha(RUN / 'MANIFEST.json'), current_book_sha256=EXPECTED_BOOK,
        replacement_receipt_sha256=sha(VET / 'replace.json'), selection_parity_sha256=sha(ROOT / 'selection-parity/receipt.json'),
        source_projection_batch='2026-09-19 15:09:52.915006+00:00',
        eligibility=dict(excluded_player_ids=sorted(excluded), admitted_candidates=int(admissible.sum()), illegal_candidates=illegal),
        positions_preserved_except_exchange=True, current_outcomes_read=False, audit_opened=False,
        scope='Research proposals on saved current-consumer selection banks; no audit gain or operating adoption.',
        seconds=time.monotonic() - started)
    OUT.mkdir()
    with (OUT / 'frozen-books.json').open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False)
        f.write('\n')
    print(json.dumps({k: result[k] for k in ('control_selection', 'decisions', 'seconds')}, indent=2))
    print('FROZEN_BOOKS_SHA256', sha(OUT / 'frozen-books.json'), flush=True)


if __name__ == '__main__':
    main()
