"""Package only authenticated public research inputs and replay evidence."""
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

HERE=Path(__file__).parent
BASE=Path('/home/erich/projects/review-evidence/overnight-20260918')
OUT=BASE/'participation-host-transfer-portable-v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def target(p):return OUT/'files'/str(p).lstrip('/')


def main():
    assert not OUT.exists();OUT.mkdir()
    inputs=HERE/'2026-09-19-participation-host-transfer-v2-inputs.json'
    frozen=json.loads(inputs.read_text())
    for p,h in frozen['files'].items():assert sha(p)==h
    paths={Path(p) for p in frozen['files']}
    paths.update([inputs,HERE/'2026-09-19-participation-host-transfer-replay.py',HERE/'2026-09-19-participation-host-transfer-package.py'])
    for row in json.loads((HERE/'2026-09-19-hsim-replay-preflight.json').read_text())['benchmark']:
        p=Path('/home/erich/.cache/nfl2/v0')/row['uri'].split('/benchmark/v0/',1)[1]
        assert sha(p)==row['sha256'];paths.add(p)
    paths.update(p for p in (BASE/'participation-host-transfer-v2').rglob('*') if p.is_file())
    for p in sorted(paths):
        dest=target(p);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    manifest=dict(schema='participation-host-transfer-portable/v1',lab_sha=frozen['source'],
        source=str(target(HERE/'2026-09-19-participation-host-transfer-v2.py').relative_to(OUT)),
        result=str(target(BASE/'participation-host-transfer-v2/result.json').relative_to(OUT)),
        files=[dict(path=str(p.relative_to(OUT)),sha256=sha(p),bytes=p.stat().st_size)
            for p in sorted(OUT.rglob('*')) if p.is_file()])
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    archive=OUT.with_suffix('.tar.gz');assert not archive.exists()
    with tarfile.open(archive,'w:gz',compresslevel=3) as t:t.add(OUT,arcname=OUT.name)
    print(json.dumps(dict(path=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,files=len(manifest['files'])),indent=2))


if __name__=='__main__':main()
