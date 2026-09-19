"""Run the cleared peer tools on the authenticated archive; capture input queries.

Research output only. Frame reads are restricted to the columns these consumers
use; actuals and candidate audit summaries are never decoded. No uploader runs.
"""
import contextlib
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from google.cloud import bigquery

ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918/d6400-actual-dose-20260919')
RUN = ROOT / 'source'
OUT = ROOT / 'host-v43-rehearsal'
TOOLS = Path('/home/erich/projects/.nfl2-worktrees/prereg101-review-reply/handoffs/runners/rung1c-v42')
LAB = Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs/src')
FRAME = ['id', 'name', 'display_name', 'dk_player_id', 'dk_draftable_id', 'pos', 'position',
         'team', 'opp', 'salary', 'gsis_id', 'status', 'game_id', 'draft_group_id']
HASHES = {
    'qb_flags.py': '7796cc5a2798f0fe7300e8ecc068ac8be2b8d66a4c844594a6866f1fed95daa6',
    'qb_classify.py': '4c4ae4151ff077f7252110776764771b36c3b4c1366dc5372fab60763ea8ac77',
    'vet_book_v2.1.py': 'a3c8aede89e13087f7ba861a04bdb629fe62f9effea0c2dcadb429c5e9f984ff',
    'vet_replace_v4.py': '914e5da86aeb22265ea9accb383c9c1716b257ea33000204be895e4834b47e45',
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    for name, digest in HASHES.items():
        assert sha(TOOLS / name) == digest
    manifest = json.loads((RUN / 'MANIFEST.json').read_text())
    for r in manifest['objects']:
        assert sha(RUN / r['name']) == r['sha256_local']
    OUT.mkdir(exist_ok=False)
    (OUT / 'RESEARCH-ONLY-NOT-FOR-UPLOAD').write_text('Independent scratch rehearsal; no operational pointers or entries changed.\n')
    original_read = pd.read_parquet
    original_query = bigquery.Client.query
    captures = []

    def restricted(path, *args, **kwargs):
        path = Path(path)
        if path.name == 'frame.parquet':
            assert not args and 'columns' not in kwargs
            return original_read(path, columns=FRAME, **kwargs)
        if path.name == 'candidates.parquet':
            assert not args and 'columns' not in kwargs
            return original_read(path, columns=['players'], **kwargs)
        raise AssertionError(f'unexpected parquet read {path}')

    def query(client, sql, **kwargs):
        assert sql.lstrip().upper().startswith(('SELECT', 'WITH'))
        assert 'actual' not in sql.lower() and 'player_week_training' not in sql
        config = kwargs.get('job_config') or bigquery.QueryJobConfig()
        config.maximum_bytes_billed = 2_000_000_000
        kwargs['job_config'] = config
        started = datetime.now(timezone.utc).isoformat()
        job = original_query(client, sql, **kwargs)
        frame = job.result().to_dataframe()
        assert 'actual' not in frame.columns
        path = OUT / f'query-{len(captures):02}.parquet'
        frame.to_parquet(path, index=False)
        captures.append(dict(file=path.name, sha256=sha(path), rows=len(frame), columns=list(frame.columns),
                             sql=sql, config=config.to_api_repr(), job_id=job.job_id, started=started,
                             received=datetime.now(timezone.utc).isoformat()))
        return SimpleNamespace(result=lambda: SimpleNamespace(to_dataframe=lambda: frame.copy()))

    commands = [
        ('qb_flags.py', [str(OUT / 'qb-flags.csv'), '--season', '2026', '--week', '2', '--group', '153428']),
        ('vet_book_v2.1.py', [str(RUN), '--k', '30', '--season', '2026', '--week', '2',
                             '--qb-flags', str(OUT / 'qb-flags.csv'), '--output-dir', str(OUT / 'vetted')]),
        ('vet_replace_v4.py', [str(OUT / 'vetted'), str(RUN), str(OUT / 'replaced'),
                              '--qb-flags', str(OUT / 'qb-flags.csv'), '--lab-src', str(LAB),
                              '--season', '2026', '--week', '2', '--admit-risky']),
    ]
    sys.path[:0] = [str(TOOLS), str(LAB)]
    with patch.object(pd, 'read_parquet', restricted), patch.object(bigquery.Client, 'query', query):
        for name, argv in commands:
            with (OUT / (name + '.log')).open('x') as log:
                with patch.object(sys, 'argv', [str(TOOLS / name), *argv]), contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                    runpy.run_path(str(TOOLS / name), run_name='__main__')
            print('REHEARSED', name, flush=True)
    for name, digest in HASHES.items():
        assert sha(TOOLS / name) == digest
    (OUT / 'query-captures.json').write_text(json.dumps(captures, indent=2) + '\n')
    result = json.loads((OUT / 'replaced/replace.json').read_text())
    assert result['status'] == 'OK' and not result['problems'] and result['required_k'] == 97
    receipt = dict(kind='independent_real_d6400_v43_scratch_rehearsal', operational_publish=False,
        source_manifest_sha256=sha(RUN / 'MANIFEST.json'), tool_sha256=HASHES, reader_sha256=sha(__file__),
        query_capture_sha256=sha(OUT / 'query-captures.json'), frame_columns=FRAME,
        outcome_columns_decoded=False, output_dir=str(OUT), replacement_receipt_sha256=sha(OUT / 'replaced/replace.json'),
        output_sha256=result['output_sha256'], replacements=len(result['replacements']),
        removed_positions=result['removed_positions'], freshness=result['freshness'], pool=result['pool'])
    (OUT / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2), flush=True)


if __name__ == '__main__':
    main()
