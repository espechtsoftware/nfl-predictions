"""Create-once internal research replay publication with round-trip identity."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from google.cloud import storage

BASE = Path('/home/erich/projects/review-evidence/overnight-20260918')
PATH = BASE / 'd6400-frontier-portable-v1.tar.gz'
BUCKET = 'nfl-2-506823-lab'
KEY = 'research/d6400-frontier-20260919/portable-v1.tar.gz'
EXPECTED = 'cf00b1fa101bac0771fde8594fe7532fa1efe5bb426680aefddb68545ea2d7e9'


def main():
    raw = PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED
    out = BASE / 'd6400-frontier-publication'
    out.mkdir(exist_ok=False)
    claim = dict(uri=f'gs://{BUCKET}/{KEY}', sha256=EXPECTED, bytes=len(raw),
                 condition='if_generation_match=0', claimed_at=datetime.now(timezone.utc).isoformat())
    (out / 'claim.json').write_text(json.dumps(claim, indent=2) + '\n')
    blob = storage.Client(project='nfl-2-506823').bucket(BUCKET).blob(KEY)
    blob.upload_from_filename(str(PATH), if_generation_match=0, checksum='crc32c', timeout=120)
    blob.reload()
    returned = blob.download_as_bytes(if_generation_match=int(blob.generation), checksum='crc32c', timeout=120)
    assert len(returned) == len(raw) == int(blob.size)
    assert hashlib.sha256(returned).hexdigest() == EXPECTED
    result = dict(**claim, generation=str(blob.generation), roundtrip_exact=True,
                  publisher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out / 'publication.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
