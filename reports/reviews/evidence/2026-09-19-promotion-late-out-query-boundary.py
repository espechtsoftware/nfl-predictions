"""Replay the actual vetter with a synthetic newly OUT provider response.

Strengthens the earlier direct final-vetter fixture by generating every output,
including the vetter's changed row order, with the cleared original vetter.
"""
import contextlib
import importlib.util
import json
from pathlib import Path
import runpy
import shutil
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from google.cloud import bigquery

HERE = Path(__file__).parent
rp = HERE / '2026-09-19-promotion-consumer-review.py'
spec = importlib.util.spec_from_file_location('promotion_review_v11', rp)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.sha(rp) == 'ff784944b0e388499537c033a9c0069f8108c4a8cfa5e411c53bb1f16c7f7cab'
case = m.OUT / 'new_out_via_actual_vetter-r2'
case.mkdir(exist_ok=False)
for d in ['run', 'vet', 'staging']:
    shutil.copytree(m.OUT / 'baseline' / d, case / d)
fr = m.restricted(case / 'run/frame.parquet')
dk = m.rows(case / 'vet/book.csv')[4][1]
person = fr.loc[fr.dk_player_id.astype(str) == dk].iloc[0]
qroot = m.ROOT / 'host-v43-rehearsal'
qs = json.loads((qroot / 'query-captures.json').read_text())[1:5]
frames = []
for q in qs:
    assert m.sha(qroot / q['file']) == q['sha256']
    frames.append(m.read(qroot / q['file']))
inj = frames[0]
synthetic = dict(gsis_id=person.gsis_id, report_status='Out', practice_status='Full',
                 practice_primary_injury='SYNTHETIC REVIEW BOUNDARY', date_modified=inj.date_modified.max())
frames[0] = pd.concat([inj.loc[inj.gsis_id != person.gsis_id], pd.DataFrame([synthetic])], ignore_index=True)
calls = []
def query(client, sql, **kwargs):
    i = len(calls)
    assert sql == qs[i]['sql']
    assert kwargs['job_config'].to_api_repr()['query']['queryParameters'] == qs[i]['config']['query']['queryParameters']
    calls.append(i)
    return SimpleNamespace(result=lambda: SimpleNamespace(to_dataframe=lambda: frames[i].copy(deep=True)))
sys.path.insert(0, str(m.VETTER.parent))
sys.path.insert(0, '/home/erich/projects/nfl-predictions/src')
argv = [str(m.VETTER), str(case / 'staging'), '--k', '30', '--season', '2026', '--week', '2',
        '--qb-flags', str(qroot / 'qb-flags.csv'), '--output-dir', str(case / 'fv')]
with (case / 'vetter.log').open('x') as log, patch.object(sys, 'argv', argv), \
        patch.object(bigquery.Client, 'query', query), patch.object(pd, 'read_parquet', m.restricted), \
        contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
    runpy.run_path(str(m.VETTER), run_name='__main__')
assert calls == [0, 1, 2, 3]
r = m.invoke(case)
fv = json.loads((case / 'fv/vetting.json').read_text())
assert 'report:out' in [v.lower() for v in fv['player_flags'][person['name']]['flags']]
r.update(tool_sha256=m.sha(m.TOOL), reader_sha256=m.sha(__file__),
         original_vetter_sha256=m.sha(m.VETTER), synthetic_injury_query_response=True,
         player=dict(name=person['name'], dk=dk),
         final_vetter_flags=fv['player_flags'][person['name']],
         input_rows_with_player=sum(dk in x for x in m.rows(case / 'vet/book.csv')),
         output_rows_with_player=sum(dk in x for x in m.rows(case / 'out/book.csv')) if r['output_exists'] else 0,
         provider_calls=0, outcome_columns_decoded=False)
m.dump(case / 'result.json', r)
print(json.dumps(r, indent=2))
