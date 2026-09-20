"""Outcome-blind D12800 first-entry ordering screen.

Uses only the archived frame identity/salary/name columns, candidates' players
column, the two selection banks, and DK-id books. It never reads actual/audit
columns or provider data. This is a pre-vetter screen; it does not authorize a
Sunday publication or replace fresh status/replacement checks.
"""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ARCH = Path('/home/erich/projects/review-evidence/overnight-20260918/d12800-archive-20260920')
PREVIEW = Path('/home/erich/projects/.nfl2-worktrees/prereg101-review-reply/handoffs/receipts/2026-09-20-install-and-d12800/d12800-preview-final-book.csv')
OUT = ARCH / 'ordering-screen-result.json'
BANKS = ['incumbent_player_scores.npy', 'corrected_hsim_player_scores.npy']
FRAME_COLS = ['id', 'dk_player_id', 'salary', 'name']
SLOTS = ['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_book(p):
    with Path(p).open(newline='') as f:
        r = list(csv.reader(f))
    assert r[0] == SLOTS and len(r) == 98 and all(len(x) == 9 for x in r[1:])
    return r[1:]


def main():
    manifest = json.loads((ARCH / 'MANIFEST.json').read_text())
    manifest_by_name = {x['name']: x for x in manifest['objects']}
    for name in ['frame.parquet', 'candidates.parquet', 'receipt.json', *BANKS]:
        assert sha(ARCH / name) == manifest_by_name[name]['sha256_local'], name
    fr = pd.read_parquet(ARCH / 'frame.parquet', columns=FRAME_COLS)
    candidates = pd.read_parquet(ARCH / 'candidates.parquet', columns=['players'])
    receipt = json.loads((ARCH / 'receipt.json').read_text())
    assert receipt['config']['operational_k'] == 97 and receipt['config']['sims'] == 10000
    assert len(candidates) == receipt['candidates'] == 12555
    banks = [np.load(ARCH / b, mmap_mode='r', allow_pickle=False) for b in BANKS]
    assert all(x.shape == (len(fr), receipt['config']['sims']) and x.dtype == np.float32 for x in banks)
    frame_idx = {str(x): i for i, x in enumerate(fr.id.astype(str))}
    dk_to_id = dict(zip(fr.dk_player_id.astype(int).astype(str), fr.id.astype(str)))
    id_to_name = dict(zip(fr.id.astype(str), fr.name.astype(str)))
    orders = {}
    for ci, toks in enumerate(candidates.players):
        toks = [x.strip() for x in toks.split(',') if x.strip()]
        idx = tuple(sorted(frame_idx[x] for x in toks))
        orders.setdefault(frozenset(idx), (ci, idx))
    def candidate_rows(book):
        found = []
        for rank, row in enumerate(book, 1):
            ids = [dk_to_id[x] for x in row]
            key = frozenset(frame_idx[x] for x in ids)
            assert key in orders, (rank, row)
            ci, idx = orders[key]
            found.append(dict(rank=rank, candidate=int(ci), frame_indices=list(idx), dk_ids=row,
                              names=[id_to_name[x] for x in ids]))
        assert len({x['candidate'] for x in found}) == 97
        return found
    def metric(book, label):
        rows = candidate_rows(book)
        vals = np.empty((97, 20000), dtype=np.float32)
        for j, x in enumerate(rows):
            for bi, bank in enumerate(banks):
                vals[j, bi * 10000:(bi + 1) * 10000] = bank[x['frame_indices']].sum(axis=0)
        assert np.isfinite(vals).all()
        mean = vals.mean(axis=1, dtype=np.float64)
        p220 = (vals >= 220).mean(axis=1, dtype=np.float64)
        p230 = (vals >= 230).mean(axis=1, dtype=np.float64)
        pooled = dict(mean=mean, p220=p220, p230=p230)
        choices = {}
        for objective, score in pooled.items():
            order = sorted(range(30), key=lambda i: (-float(score[i]), i))
            choices[objective] = dict(source_rank=int(order[0] + 1), candidate=rows[order[0]]['candidate'],
                                      value=float(score[order[0]]), original_first=float(score[0]),
                                      delta=float(score[order[0]] - score[0]),
                                      first30_order=[int(i + 1) for i in order[:10]])
        # Block 2-24 cost/gain of putting each selected head row first, holding all later rows fixed.
        block = slice(1, 24)
        base_max = vals[block].max(axis=0)
        block_choices = {}
        for objective, score in pooled.items():
            order = sorted(range(30), key=lambda i: (-float(score[i]), i)); pick = order[0]
            alt = vals[block].copy(); alt[0] = vals[pick]
            block_choices[objective] = dict(source_rank=int(pick + 1),
                mean_max_delta=float(alt.max(axis=0).mean(dtype=np.float64) - base_max.mean(dtype=np.float64)),
                p220_delta=float((alt.max(axis=0) >= 220).mean() - (base_max >= 220).mean(),),
                p230_delta=float((alt.max(axis=0) >= 230).mean() - (base_max >= 230).mean(),))
        bank_choice = {}
        for bi, name in enumerate(['incumbent', 'corrected_hsim']):
            arr = vals[:, bi * 10000:(bi + 1) * 10000]
            bank_choice[name] = dict(mean_rank=int(np.argmax(arr[:30].mean(axis=1)) + 1),
                                     p220_rank=int(np.argmax((arr[:30] >= 220).mean(axis=1)) + 1),
                                     mean_first=float(arr[0].mean()), p220_first=float((arr[0] >= 220).mean()))
        return dict(label=label, book_sha256=sha(PREVIEW if label == 'preview-final' else ARCH / 'book.csv'),
                    rows=rows, choices=choices, block_2_24=block_choices, bank_choice=bank_choice,
                    first_lineup=dict(mean=float(mean[0]), p220=float(p220[0]), p230=float(p230[0]), names=rows[0]['names']))
    raw = load_book(ARCH / 'book.csv')
    wemax = load_book(ARCH / 'book_wemax.csv')
    preview = load_book(PREVIEW)
    result = dict(schema='d12800-ordering-screen/v1', reader_sha256=sha(__file__), archive_manifest_sha256=sha(ARCH / 'MANIFEST.json'),
                  archive_receipt_sha256=sha(ARCH / 'receipt.json'), frame_columns=FRAME_COLS,
                  source_frame_sha256=sha(ARCH / 'frame.parquet'), source_candidate_count=len(candidates),
                  source_banks={b: sha(ARCH / b) for b in BANKS}, current_outcomes_read=False,
                  provider_calls=0, pre_vetter=True, books={
                      'raw-book': metric(raw, 'raw-book'), 'raw-wemax-book': metric(wemax, 'raw-wemax-book'),
                      'preview-final': metric(preview, 'preview-final')})
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({k: {o: v for o, v in x['choices'].items()} for k, x in result['books'].items()}, indent=2))
    print('RESULT_SHA256', sha(OUT), 'OUT', OUT)


if __name__ == '__main__':
    main()
