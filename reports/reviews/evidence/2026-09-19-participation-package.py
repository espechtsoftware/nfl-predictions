"""Create a portable authenticated forecast-only review bundle; no cloud writes."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

REPO=Path(__file__).resolve().parents[3]
HERE=Path(__file__).parent
BASE=Path('/home/erich/projects/review-evidence/overnight-20260918')
DEST=BASE/'participation-portable-v1'


def main():
    DEST.mkdir(exist_ok=False)
    paths=set()
    rpath=BASE/'complete-chain-d1600/salaryfix/receipt.json';r=json.loads(rpath.read_text());paths.add(rpath)
    prior=HERE/'2026-09-19-repaired-chain-d1600-read.json';j=json.loads(prior.read_text());paths.add(prior)
    paths.update(Path(r['original_run'])/n for n in j['provenance']['salaryfix']['artifacts'])
    paths.add(Path(r['candidate_player_orders']['path']))
    paths.update(Path(r['arrays'][k]['path']) for k in ('I_selection','H_selection','I_audit','H_audit'))
    for sub in ('participation-transfer-inputs','participation-transfer-support','participation-transfer','participation-transfer-smoke'):
        paths.update(p for p in (BASE/sub).rglob('*') if p.is_file())
    source=HERE/'2026-09-19-participation-transfer.py'
    paths.update([source,HERE/'2026-09-19-participation-replay.py',HERE/'2026-09-19-repaired-chain-read.py',
        REPO/'scripts/week1_vet_book.py',REPO/'reports/2026-09-19-participation-transfer-protocol.md'])
    files=[]
    for p in sorted(paths):
        rel='files/'+str(p).lstrip('/');dest=DEST/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
        files.append(dict(source_path=str(p),relative_path=rel,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    result=BASE/'participation-transfer/result.json'
    manifest=dict(files=files,source_relative_path='files/'+str(source).lstrip('/'),
        result_relative_path='files/'+str(result).lstrip('/'),scope='Prelock Week2 forecasts, research books and raw status inputs; no entered CSV or football labels')
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2))
    archive=BASE/'participation-portable-v1.tar.gz'
    with tarfile.open(archive,'x:gz') as t:
        t.add(DEST,arcname='participation-portable-v1')
    print(json.dumps(dict(path=str(archive),bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),files=len(files)),indent=2),flush=True)


if __name__=='__main__':main()
