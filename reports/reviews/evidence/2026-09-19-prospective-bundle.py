"""Package already-frozen forecast artifacts; optionally publish create-only to the research bucket."""
import argparse
import base64
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import google_crc32c
import numpy as np
import pandas as pd

R = Path(__file__).resolve().parent
ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918')
BUNDLE = ROOT / 'prospective-d1600-bundle'
BUCKET = 'nfl-2-506823-lab'
PREFIX = 'research/week2-prospective-d1600/20260919-prelock-v1/'
RECEIPT = R / '2026-09-19-prospective-bundle.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(path):
    return dict(path=path.name,sha256=sha(path),bytes=path.stat().st_size)


def prepare():
    assert not BUNDLE.exists()
    BUNDLE.mkdir()
    chain_path = R/'2026-09-19-repaired-chain-d1600-read.json'
    chain = json.loads(chain_path.read_text())
    manifest = dict(version='week2-prospective-d1600-v1',created_utc=datetime.now(timezone.utc).isoformat(),
        season=2026,week=2,draft_group=153428,slate='sunday_main',scoring='dk_classic_v1',arms={},
        chain_result_sha256=sha(chain_path),source_commit='2dc116ce95647a776ba9c36cf194f44d022d03a4',
        description='Paired D1600 ordinary EMAX shadow books; both arms share live game-input correction. No entered-book claim, actual outcomes or prior treatment. Minimal frame preserves original bank row order.')
    expected_games = None
    for arm in ('control','salaryfix'):
        adapter = json.loads((ROOT/'complete-chain-d1600'/arm/'receipt.json').read_text())
        run = Path(adapter['original_run'])
        for name,digest in chain['provenance'][arm]['artifacts'].items():
            assert sha(run/name)==digest
        assert sha(run/'receipt.json')==adapter['original_receipt_sha256']
        config = json.loads((run/'receipt.json').read_text())['config']
        games = [{k:g[k] for k in ('game_id','home','away')} for g in config['hsim_game_inputs']['games']]
        if expected_games is None:
            expected_games=games
        assert games==expected_games and len(games)==13
        game_map={g['game_id']:frozenset((g['home'],g['away'])) for g in games}
        frame=pd.read_parquet(run/'frame.parquet',columns=['id','name','pos','team','opp','game_id','season','week'])
        assert frame.id.is_unique and frame.id.notna().all()
        assert frame.season.eq(2026).all() and frame.week.eq(2).all()
        assert all(game_map[g]==frozenset((t,o)) for g,t,o in zip(frame.game_id,frame.team,frame.opp))
        path=BUNDLE/(arm+'-frame.parquet');frame.to_parquet(path,index=False)
        spec=dict(frame=record(path),original_full_frame_sha256=sha(run/'frame.parquet'),banks={},expected_book_size=97)
        for name in ('I_audit','H_audit'):
            rec=adapter['arrays'][name];assert sha(rec['path'])==rec['sha256']
            array=np.load(rec['path'],allow_pickle=False)
            assert array.shape==(len(frame),10000) and array.dtype==np.float32 and np.isfinite(array).all()
            dest=BUNDLE/(arm+'-'+name+'.npy');shutil.copyfile(rec['path'],dest)
            assert sha(dest)==rec['sha256'];spec['banks'][name]=record(dest)
        book=chain['books'][arm+'_emax']['orders']
        assert len(book)==len({tuple(sorted(o)) for o in book})==97
        assert all(len(o)==len(set(o))==9 and set(o)<=set(frame.id.astype(str)) for o in book)
        path=BUNDLE/(arm+'-book.json');path.write_text(json.dumps(book,indent=2)+'\n');spec['book_orders']=record(path)
        manifest['arms'][arm]=spec
    path=BUNDLE/'games.json';path.write_text(json.dumps(expected_games,indent=2)+'\n');manifest['games']=record(path)
    trace=json.loads((R/'2026-09-19-zero-target-prior-simulator.json').read_text())
    eligible=[x['id'] for x in trace['players'] if x['eligible']];assert len(eligible)==len(set(eligible))==27
    path=BUNDLE/'prior-eligible.json';path.write_text(json.dumps(eligible,indent=2)+'\n');manifest['prior_eligible_ids']=record(path)
    (BUNDLE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('FORECAST_BUNDLE_PREPARED',len(list(BUNDLE.iterdir())),sum(p.stat().st_size for p in BUNDLE.iterdir()),flush=True)


def publish():
    assert BUNDLE.is_dir() and not RECEIPT.exists()
    from google.cloud import storage
    client=storage.Client(project='nfl-2-506823');bucket=client.bucket(BUCKET)
    # Publish the manifest last. A partially uploaded bundle is never represented as complete.
    paths=sorted(BUNDLE.iterdir(),key=lambda p:(p.name=='manifest.json',p.name))
    assert len(paths)==11 and all(p.is_file() for p in paths)
    records=[]
    for path in paths:
        raw=path.read_bytes();blob=bucket.blob(PREFIX+path.name)
        blob.upload_from_filename(str(path),if_generation_match=0,checksum='crc32c',timeout=120)
        blob.reload()
        crc=base64.b64encode(google_crc32c.Checksum(raw).digest()).decode()
        assert int(blob.size)==len(raw) and blob.crc32c==crc
        records.append(dict(uri=f'gs://{BUCKET}/{blob.name}',generation=str(blob.generation),
                            bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),crc32c=crc))
    with RECEIPT.open('x') as f:
        json.dump(dict(bundle_uri=f'gs://{BUCKET}/{PREFIX}',local=str(BUNDLE),objects=records,
                       source_sha256=sha(__file__),scope='Forecast-only create-once transfer; no outcomes or live configuration'),f,indent=2)
    print('FORECAST_BUNDLE_PUBLISHED',f'gs://{BUCKET}/{PREFIX}',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','publish'))
    mode=parser.parse_args().mode
    (prepare if mode=='prepare' else publish)()
