"""Materialize the frozen research permutation, preserving exact CSV row bytes."""
import csv
import hashlib
import io
import json
from pathlib import Path

import pandas as pd

ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918/d6400-actual-dose-20260919')
OUT = ROOT / 'promotion-proof'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    p = ROOT / 'reselection-proposals/frozen-books.json'
    assert sha(p) == '87262e06f43a6352f7b92df1a4aacd5d6913fb9c0abb759e630b69b86cd38ecd'
    frozen = json.loads(p.read_text())
    src = ROOT / 'host-v43-rehearsal/replaced/book.csv'
    assert sha(src) == frozen['current_book_sha256']
    raw = src.read_bytes()
    lines = raw.splitlines(keepends=True)
    assert len(lines) == 98 and len(set(lines[1:])) == 97
    rows = list(csv.reader(io.StringIO(raw.decode())))
    assert rows[0] == ['QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST']
    orders = json.loads((ROOT / 'selection-parity/candidate_orders.json').read_text())
    assert sha(ROOT / 'source/frame.parquet') == frozen['source_frame_sha256']
    fr = pd.read_parquet(ROOT / 'source/frame.parquet', columns=['id', 'dk_player_id'])
    ids = dict(zip(fr.dk_player_id.astype(str), fr.id))
    control, promoted = frozen['books']['control'], frozen['books']['control_promoted']
    assert all(set(orders[c]) == {ids[v] for v in row} for c, row in zip(control, rows[1:]))
    permutation = [control.index(c) for c in promoted]
    assert sorted(permutation) == list(range(97)) and set(permutation[:30]) == set(range(30))
    assert permutation[30:] == list(range(30, 97))
    OUT.mkdir(exist_ok=False)
    (OUT / 'RESEARCH-ONLY-NOT-FOR-UPLOAD').write_text('Candidate ordering proof; operator adoption and final-book rerun remain separate.\n')
    (OUT / 'control-book.csv').write_bytes(raw)
    derived = lines[0] + b''.join(lines[i + 1] for i in permutation)
    (OUT / 'promoted-book.csv').write_bytes(derived)
    outrows = list(csv.reader(io.StringIO(derived.decode())))
    assert outrows[0] == rows[0] and outrows[1:] == [rows[i + 1] for i in permutation]
    assert sorted(outrows[1:]) == sorted(rows[1:])
    result = dict(kind='research_order_permutation_proof', operational_publish=False,
        producer_sha256=sha(__file__), frozen_books_sha256=sha(p),
        control_csv_sha256=sha(src), promoted_csv_sha256=sha(OUT / 'promoted-book.csv'),
        source_ranks_in_delivered_order=[i + 1 for i in permutation],
        promoted_from_rank=frozen['promotions']['control']['promoted_from_rank'],
        membership_exact=True, original_cell_and_row_bytes_preserved=True,
        unique_legal_k97_inherited_from_authenticated_control=True,
        entry_identifiers_read=False, current_outcomes_read=False,
        limitation='Not a complete upload/sheet rehearsal; peer must verify current final book, fresh statuses and actual contest mapping.')
    (OUT / 'receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
