"""Separately frozen whole-book-only diagnostic; exact parent source, asserted edits."""
import hashlib
from pathlib import Path

base = Path(__file__).with_name('2026-09-19-fixed-k-retrieval.py')
raw = base.read_bytes()
EXPECTED = '579cc99a137a431cbbf861b04079b72d3d2f643d6305302b53ad5e1dbf3c69b0'
assert hashlib.sha256(raw).hexdigest() == EXPECTED
source = raw.decode()
changes = [
    ("OUT = R / '2026-09-19-fixed-k-retrieval.json'", "OUT = R / '2026-09-19-fixed-k-tradeoff.json'"),
    ("stop = 'three_replacement_budget'", "stop = 'one_replacement_budget'"),
    ('for iteration in range(3):', 'for iteration in range(1):'),
    ('affected = [key for key, rows in sets.items() if row in rows]', "affected = ['prefix97']"),
    ('assert all(np.all(after[key] >= before[key] - 1e-12) for key in sets)',
     "assert np.all(after['prefix97'] >= before['prefix97'] - 1e-12)"),
    ('final_no_harm_all_sets=True, milly_unchanged=True',
     "final_no_harm_whole_book=True, final_no_harm_all_sets=all(bool(np.all(after[key] >= before[key] - 1e-12)) for key in sets), milly_unchanged=True"),
    ("caveat='Selection-bank diagnostic on older D6400 pool. No independent law or realized-score validation.'",
     "caveat='Whole-book-only guarded ONE-swap headroom measurement, not live nomination or global bound. Selection banks, older D6400 pool; no independent or realized validation.'"),
    ('with OUT.open(\'x\') as handle:',
     "result['transform_provenance'] = dict(parent_sha256=PARENT_HASH, transformed_sha256=TRANSFORMED_HASH)\nwith OUT.open('x') as handle:"),
]
for old, new in changes:
    assert source.count(old) == 1, old
    source = source.replace(old, new, 1)
scope = dict(__file__=__file__, __name__='__main__', PARENT_HASH=EXPECTED,
             TRANSFORMED_HASH=hashlib.sha256(source.encode()).hexdigest())
exec(compile(source, str(Path(__file__)), 'exec'), scope)
