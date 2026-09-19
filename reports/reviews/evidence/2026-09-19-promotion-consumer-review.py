"""Independent scratch-only boundaries for production promote_first v1.1.

Never decode current outcome/audit columns. Exact original source files are copied;
the pandas reader is restricted in-process, with every intercepted call recorded.
Final vetting replays the four captured, hash-bound provider query responses.
"""
import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import runpy
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
from google.cloud import bigquery

ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918/d6400-actual-dose-20260919')
OUT = ROOT.parent / 'promotion-consumer-review-v11-r2'
SHARED = Path('/home/erich/projects/.nfl2-worktrees/prereg101-review-reply/handoffs')
TOOL = SHARED / 'tools/promote-first-v1.1/promote_first.py'
VETTER = SHARED / 'runners/rung1c-v42/vet_book_v2.1.py'
FRAME = ['id', 'name', 'gsis_id', 'pos', 'position', 'team', 'opp', 'salary', 'status',
         'display_name', 'dk_player_id', 'dk_draftable_id', 'draft_group_id']
BANKS = ['incumbent_player_scores.npy', 'corrected_hsim_player_scores.npy']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = pd.read_parquet
calls = []


def restricted(path, *args, **kwargs):
    name = Path(path).name
    if name in ('frame.parquet', 'candidates.parquet'):
        allowed = FRAME if name == 'frame.parquet' else ['players']
        requested = kwargs.get('columns')
        assert not args
        if requested is not None:
            assert set(requested) <= set(allowed)
        calls.append(dict(path=str(path), requested=requested, decoded=requested or allowed))
        kwargs['columns'] = requested or allowed
    return read(path, **kwargs)


def dump(p, v):
    p.write_text(json.dumps(v, indent=2, allow_nan=False) + '\n')


def rows(p):
    return list(csv.reader(p.open()))[1:]


def invoke(case):
    argv = [str(TOOL), str(case / 'vet'), str(case / 'run'), str(case / 'out'),
            '--final-vetting', str(case / 'fv')]
    code, log = 0, io.StringIO()
    begin = len(calls)
    with patch.object(sys, 'argv', argv), patch.object(pd, 'read_parquet', restricted), \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            runpy.run_path(str(TOOL), run_name='__main__')
        except SystemExit as e:
            code = e.code
    (case / 'log.txt').write_text(log.getvalue())
    receipt = case / 'out/promotion.json'
    rec = json.loads(receipt.read_text()) if receipt.exists() else None
    return dict(exit_code=code, output_exists=receipt.exists(),
                promotion=rec['promotion'] if rec else None,
                tier_counts=rec['tier_counts'] if rec else None,
                unrestricted_reads=[x for x in calls[begin:] if x['requested'] is None],
                input_bank_sha256={b: sha(case / 'run' / b) for b in BANKS},
                receipt_sha256=sha(receipt) if rec else None)


def main():
    assert sha(TOOL) == '3590193e2483d4eef1229c33d87fa820c1706b502af356b8bcc8ccf1913a1464'
    assert sha(VETTER) == 'a3c8aede89e13087f7ba861a04bdb629fe62f9effea0c2dcadb429c5e9f984ff'
    OUT.mkdir(exist_ok=False)
    base = OUT / 'baseline'
    for d in ['run', 'vet', 'staging']:
        (base / d).mkdir(parents=True)
    for name in ['frame.parquet', 'candidates.parquet', 'receipt.json', *BANKS]:
        shutil.copy2(ROOT / 'source' / name, base / 'run' / name)
    for name in ['book.csv', 'vetting_final.json', 'frame.parquet', 'replace.json', 'source_receipt.json']:
        shutil.copy2(ROOT / 'host-v43-rehearsal/replaced' / name, base / 'vet' / name)
    for name in ['book.csv', 'frame.parquet']:
        shutil.copy2(base / 'vet' / name, base / 'staging' / name)
    shutil.copy2(base / 'vet/source_receipt.json', base / 'staging/receipt.json')
    qroot = ROOT / 'host-v43-rehearsal'
    qp = qroot / 'query-captures.json'
    assert sha(qp) == '0c8e1fd1acbb4598325392fef45fc0daaf14631fd9fc9011d2083372c11954a4'
    qs = json.loads(qp.read_text())[1:5]
    qframes = []
    for q in qs:
        assert sha(qroot / q['file']) == q['sha256']
        qframes.append(read(qroot / q['file']))
    queries = []
    def query(client, sql, **kwargs):
        i = len(queries)
        assert sql == qs[i]['sql']
        assert kwargs['job_config'].to_api_repr()['query']['queryParameters'] == qs[i]['config']['query']['queryParameters']
        queries.append(i)
        return SimpleNamespace(result=lambda: SimpleNamespace(to_dataframe=lambda: qframes[i].copy(deep=True)))
    sys.path.insert(0, str(VETTER.parent))
    sys.path.insert(0, '/home/erich/projects/nfl-predictions/src')
    argv = [str(VETTER), str(base / 'staging'), '--k', '30', '--season', '2026', '--week', '2',
            '--qb-flags', str(qroot / 'qb-flags.csv'), '--output-dir', str(base / 'fv')]
    with (base / 'vetter.log').open('x') as log, patch.object(sys, 'argv', argv), \
            patch.object(bigquery.Client, 'query', query), patch.object(pd, 'read_parquet', restricted), \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        runpy.run_path(str(VETTER), run_name='__main__')
    assert queries == [0, 1, 2, 3]
    result = dict(tool_sha256=sha(TOOL), reader_sha256=sha(__file__),
                  outcome_columns_decoded=False, original_vetter_replayed=True, cases={})
    result['cases']['baseline'] = invoke(base)
    assert result['cases']['baseline']['exit_code'] == 0
    assert result['cases']['baseline']['promotion']['promoted_from_rank'] == 5
    def clone(name):
        dest = OUT / name
        for d in ['run', 'vet', 'fv']:
            shutil.copytree(base / d, dest / d)
        return dest
    case = clone('foreign_same_shape_bank')
    bank = np.load(case / 'run' / BANKS[0], allow_pickle=False)
    bank += np.float32(1.0)
    np.save(case / 'run' / BANKS[0], bank, allow_pickle=False)
    result['cases'][case.name] = invoke(case)
    case = clone('missing_source_receipt')
    (case / 'run/receipt.json').unlink()
    result['cases'][case.name] = invoke(case)
    case = clone('new_confirmed_out_in_final_vetting')
    fr = restricted(case / 'run/frame.parquet')
    source_rows = rows(case / 'vet/book.csv')
    dk = source_rows[4][1]
    person = fr.loc[fr.dk_player_id.astype(str) == dk].iloc[0]
    fv = json.loads((case / 'fv/vetting.json').read_text())
    fv['player_flags'][person['name']] = dict(dk=dk, pos=person['pos'], team=person['team'],
                                             weight=100.0, flags=['report:Out'])
    weights = {str(v['dk']): float(v['weight']) for v in fv['player_flags'].values()}
    for r, line in zip(source_rows, fv['lineups']):
        line['risk'] = sum(weights.get(d, 0.0) for d in r)
        line['hard'] = any(weights.get(d, 0.0) >= 100 for d in r)
        line['material'] = not line['hard'] and line['risk'] >= fv['material_threshold']
        if dk in r:
            line['flags'][person['name']] = ['report:Out']
    dump(case / 'fv/vetting.json', fv)
    rr = invoke(case)
    rr.update(injected_player=dict(dk=dk, name=person['name']),
              confirmed_out_input_rows=sum(dk in r for r in source_rows),
              confirmed_out_output_rows=sum(dk in r for r in rows(case / 'out/book.csv')) if rr['output_exists'] else 0)
    result['cases'][case.name] = rr
    case = clone('not_publishable_consumer')
    rep = json.loads((case / 'vet/replace.json').read_text())
    rep['publishable'] = False
    rep['rehearsal_flags']['no_fresh_dk'] = True
    dump(case / 'vet/replace.json', rep)
    result['cases'][case.name] = invoke(case)
    result['current_book_sha256'] = sha(base / 'vet/book.csv')
    dump(OUT / 'result.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
