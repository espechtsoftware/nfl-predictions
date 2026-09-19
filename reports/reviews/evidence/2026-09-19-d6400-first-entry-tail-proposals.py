"""Freeze standalone mean / P220 / proxy head choices from selection banks only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import numpy as np

HERE = Path(__file__).parent
ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918/d6400-actual-dose-20260919')
OUT = ROOT / 'first-entry-tail-proposals'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def choose(book, eligible, values):
    assert len(book) == len(set(book)) == len(eligible) == len(values)
    ranks = [i for i in range(min(30, len(book))) if eligible[i]]
    if not ranks:
        return list(book), 0
    assert np.isfinite(np.asarray(values)[ranks]).all()
    chosen = ranks[int(np.argmax(np.asarray(values)[ranks]))]
    result = [book[chosen], *book[:chosen], *book[chosen + 1:]]
    assert set(result) == set(book) and set(result[:30]) == set(book[:30]) and result[30:] == book[30:]
    return result, chosen


def mechanics():
    # Highest score can be ineligible or outside the allowed delivery prefix.
    book = list(range(40)); eligible = [True] * 40; eligible[3] = False
    values = [0.] * 40; values[3] = 100.; values[35] = 200.; values[4] = values[8] = 10.
    proposed, chosen = choose(book, eligible, values)
    assert chosen == 4 and proposed == [4, 0, 1, 2, 3, *range(5, 40)]
    assert choose(book, [False] * 40, values) == (book, 0)
    # A lower-mean lineup can have greater tail probability; don't collapse objectives.
    toy = np.asarray([[200, 200, 200, 200], [0, 0, 221, 221]], float)
    assert choose([0, 1], [True, True], toy.mean(axis=1))[1] == 0
    assert choose([0, 1], [True, True], (toy >= 220).mean(axis=1))[1] == 1


def main():
    mechanics()
    prior_path = ROOT / 'reselection-proposals/frozen-books.json'
    assert sha(prior_path) == '87262e06f43a6352f7b92df1a4aacd5d6913fb9c0abb759e630b69b86cd38ecd'
    prior = json.loads(prior_path.read_text())
    book = prior['books']['control']
    eligible = prior['vetting']['control']['delivered_clean_or_soft']
    assert sum(eligible[:30]) == 29
    parity = json.loads((ROOT / 'selection-parity/receipt.json').read_text())
    tp = ROOT / 'selection-parity/selection_totals.npy'
    assert sha(tp) == parity['selection_totals_sha256'] and parity['source_control_exact']
    t = np.load(tp, mmap_mode='r', allow_pickle=False)[book]
    hp = HERE / '2026-09-19-repaired-chain-read.py'
    assert sha(hp) == '30df46cd492dc45fa35b6da54285135bc2b8dc633cc33b157f2a390c7f5fb646'
    spec = importlib.util.spec_from_file_location('head_metrics', hp)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    raw = subprocess.check_output(['git', '-C', '/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs',
                                   'show', 'e7255e9:results/contest/milly_winners.json'])
    assert hashlib.sha256(raw).hexdigest() == '4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners = np.asarray(sorted(json.loads(raw).values()), float)
    scores = [helper.metrics(row.astype(float), winners) for row in t]
    values = {metric: [float(s[metric].mean()) for s in scores] for metric in ('emax', 'p220', 'global_proxy')}
    books, choices = {'control': book}, {}
    for name, metric in [('mean', 'emax'), ('p220', 'p220'), ('proxy', 'global_proxy')]:
        books[name], rank = choose(book, eligible, values[metric])
        choices[name] = dict(promoted_from_rank=rank + 1, candidate=book[rank],
            selection_metrics={m: values[m][rank] for m in values})
    assert books['mean'] == prior['books']['control_promoted']
    result = dict(schema='first-entry-tail-objective/v1', books=books, choices=choices,
        selection_metrics_by_original_rank=values, eligible=eligible,
        source_packet_sha256=sha(prior_path), producer_sha256=sha(__file__),
        protocol_sha256=sha(HERE.parents[1] / '2026-09-19-d6400-first-entry-tail-protocol.md'),
        candidate_orders_sha256=prior['candidate_orders_sha256'], source_frame_sha256=prior['source_frame_sha256'],
        probabilities=prior['probabilities'], eligibility=prior['eligibility'],
        current_book_sha256=prior['current_book_sha256'], statuses=prior['statuses'],
        audit_seeds=dict(I=22260919, H=23260919, availability=20260919063),
        all_memberships_exact=True, current_outcomes_read=False, audits_read=False,
        primary='proxy_minus_mean', secondary='p220_minus_mean')
    OUT.mkdir(exist_ok=False)
    (OUT / 'milly_winners.json').write_bytes(raw)
    with (OUT / 'frozen-books.json').open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    print(json.dumps(choices, indent=2), flush=True)
    print('FROZEN_BOOKS_SHA256', sha(OUT / 'frozen-books.json'), flush=True)


if __name__ == '__main__':
    main()
