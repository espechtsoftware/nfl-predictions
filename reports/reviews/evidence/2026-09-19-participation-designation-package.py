"""Package the exact frozen inputs, new audit banks and provider rehearsal."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

HERE=Path(__file__).parent
BASE=Path('/home/erich/projects/review-evidence/overnight-20260918')
REPO=HERE.parents[2]
OUT=BASE/'participation-designation-portable-v1'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dest(p):return OUT/'files'/str(p).lstrip('/')


def main():
    assert not OUT.exists()
    shutil.copytree(BASE/'participation-portable-v1',OUT)
    (OUT/'manifest.json').rename(OUT/'base-manifest.json')
    paths=[REPO/'reports/2026-09-19-participation-designation-protocol.md']
    paths += [HERE/name for name in ('2026-09-19-participation-designation-banks.py',
        '2026-09-19-participation-designation-audit.json','2026-09-19-participation-designation-read.py',
        '2026-09-19-participation-provider-capture.py','2026-09-19-participation-reselect-v2.py')]
    paths += [BASE/'participation-designation-audit'/name for name in ('I_audit.npy','H_audit.npy')]
    for name in ('participation-designation-decomposition','participation-provider-bound-1243',
                 'participation-provider-reselection-v2'):
        paths += [p for p in (BASE/name).rglob('*') if p.is_file()]
    for p in paths:
        q=dest(p);q.parent.mkdir(parents=True,exist_ok=True)
        if q.exists():assert sha(p)==sha(q),'never overwrite a different frozen byte'
        else:shutil.copyfile(p,q)
    files=[dict(relative_path=str(p.relative_to(OUT)),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(OUT.rglob('*')) if p.is_file()]
    manifest=dict(schema='participation-designation-portable/v1',files=files,
        source_relative_path=str(dest(HERE/'2026-09-19-participation-designation-read.py').relative_to(OUT)),
        result_relative_path=str(dest(BASE/'participation-designation-decomposition/result.json').relative_to(OUT)),
        required_lab_source='2dc116ce95647a776ba9c36cf194f44d022d03a4',
        scope='Exact outcome-free reader inputs plus separate provider-bound research rehearsal')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    tar=OUT.with_suffix('.tar.gz');assert not tar.exists()
    with tarfile.open(tar,'w:gz',compresslevel=3) as f:f.add(OUT,arcname=OUT.name)
    print(json.dumps(dict(path=str(tar),bytes=tar.stat().st_size,sha256=sha(tar),files=len(files)),indent=2))


if __name__=='__main__':main()
