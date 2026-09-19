"""Portable fixed-reader numerical replay and exact CSV permutation evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

BASE = Path('/home/erich/projects/review-evidence/overnight-20260918')
ROOT = BASE / 'd6400-actual-dose-20260919'
OUT = BASE / 'd6400-first-entry-tail-portable-v1'
HERE = Path(__file__).parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    paths = ['source/frame.parquet', 'selection-parity/candidate_orders.json',
        'first-entry-tail-proposals/frozen-books.json', 'first-entry-tail-audit/receipt.json',
        'first-entry-tail-audit/I_audit.npy', 'first-entry-tail-audit/H_audit.npy',
        'tail-promotion-proof/control-book.csv', 'tail-promotion-proof/promoted-book.csv', 'tail-promotion-proof/receipt.json',
        'tail-promotion-proof/RESEARCH-ONLY-NOT-FOR-UPLOAD']
    files = {}
    for rel in paths:
        src, dst = ROOT / rel, OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        assert sha(src) == sha(dst)
        files[rel] = dict(sha256=sha(dst), bytes=dst.stat().st_size)
    for rel, src in {'expected-result.json': ROOT / 'first-entry-tail-result.json',
                     'first-entry-tail-proposals/milly_winners.json': ROOT / 'first-entry-tail-proposals/milly_winners.json'}.items():
        dst = OUT / rel
        shutil.copyfile(src, dst)
        files[rel] = dict(sha256=sha(dst), bytes=dst.stat().st_size)
    manifest = dict(schema='d6400-first-entry-tail-numerical-replay/v1', files=files,
        original_result_sha256=sha(ROOT / 'first-entry-tail-result.json'),
        replay_reader_sha256=sha(HERE / '2026-09-19-d6400-first-entry-tail-read.py'),
        original_reader_sha256=sha(HERE / '2026-09-19-d6400-first-entry-tail-read.py'),
        scope='Frozen numerical comparison, not proposal reconstruction or operational adoption.',
        current_outcomes_decoded=False)
    (OUT / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = BASE / 'd6400-first-entry-tail-portable-v1.tar.gz'
    with archive.open('xb') as f:
        with tarfile.open(fileobj=f, mode='w:gz', compresslevel=1) as t:
            t.add(OUT, arcname=OUT.name)
    print(json.dumps(dict(path=str(archive), sha256=sha(archive), bytes=archive.stat().st_size,
                         manifest_sha256=sha(OUT / 'MANIFEST.json')), indent=2), flush=True)


if __name__ == '__main__':
    main()
