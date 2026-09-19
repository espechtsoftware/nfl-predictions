"""Create the portable numerical replay from unchanged, authenticated files."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

BASE = Path('/home/erich/projects/review-evidence/overnight-20260918')
ROOT = BASE / 'd6400-actual-dose-20260919'
OUT = BASE / 'd6400-frontier-portable-v1'
HERE = Path(__file__).parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    paths = ['source/frame.parquet', 'selection-parity/candidate_orders.json',
             'frontier-proposals/frozen-books.json', 'fresh-audit/receipt.json',
             'fresh-audit/I_audit.npy', 'fresh-audit/H_audit.npy']
    paths += [str(p.relative_to(ROOT)) for p in sorted((ROOT / 'status-v1').iterdir()) if p.is_file()]
    files = {}
    for rel in paths:
        src, dst = ROOT / rel, OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        assert sha(src) == sha(dst)
        files[rel] = dict(sha256=sha(dst), bytes=dst.stat().st_size)
    extras = {
        'participation-map.json': BASE / 'participation-transfer-support/participation-map.json',
        'expected-result.json': ROOT / 'frontier-audit-result.json',
    }
    for rel, src in extras.items():
        dst = OUT / rel
        shutil.copyfile(src, dst)
        files[rel] = dict(sha256=sha(dst), bytes=dst.stat().st_size)
    raw = subprocess.check_output(['git', '-C', '/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs',
                                   'show', 'e7255e9:results/contest/milly_winners.json'])
    (OUT / 'milly_winners.json').write_bytes(raw)
    assert sha(OUT / 'milly_winners.json') == '4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    files['milly_winners.json'] = dict(sha256=sha(OUT / 'milly_winners.json'), bytes=len(raw))
    manifest = dict(schema='d6400-frontier-numerical-replay/v1', files=files,
        original_result_sha256=sha(ROOT / 'frontier-audit-result.json'),
        replay_reader_sha256=sha(HERE / '2026-09-19-d6400-frontier-replay-v2.py'),
        original_reader_sha256=sha(HERE / '2026-09-19-d6400-frontier-read.py'),
        scope='Numerical frozen-reader replay; audit construction parity remains separately recorded.',
        current_outcomes_decoded=False)
    (OUT / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    archive = BASE / 'd6400-frontier-portable-v1.tar.gz'
    with archive.open('xb') as f:
        with tarfile.open(fileobj=f, mode='w:gz', compresslevel=1) as t:
            t.add(OUT, arcname=OUT.name)
    print(json.dumps(dict(path=str(archive), sha256=sha(archive), bytes=archive.stat().st_size,
                         manifest_sha256=sha(OUT / 'MANIFEST.json')), indent=2), flush=True)


if __name__ == '__main__':
    main()
