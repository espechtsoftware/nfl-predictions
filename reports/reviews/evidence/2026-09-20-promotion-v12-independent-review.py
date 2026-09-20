"""Repeat the reported promotion failures against exact production v1.2 bytes."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import runpy
import shutil
import sys
from unittest.mock import patch

HERE = Path(__file__).parent
rp = HERE / '2026-09-19-promotion-consumer-review.py'
spec = importlib.util.spec_from_file_location('promotion_old_review', rp)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.sha(rp) == 'ff784944b0e388499537c033a9c0069f8108c4a8cfa5e411c53bb1f16c7f7cab'
m.TOOL = m.SHARED / 'tools/promote-first-v1.2/promote_first.py'
assert m.sha(m.TOOL) == '48d95c1b7f5f9a363e37f00810291ff201eced73a4af6921696e49772ff0d3ab'
OUT = m.ROOT.parent / 'promotion-v12-review-20260920'
OUT.mkdir(exist_ok=False)
result = dict(reader_sha256=m.sha(__file__), consumer_sha256=m.sha(m.TOOL), cases={})
checks = [('baseline', 0), ('foreign_same_shape_bank', 2), ('missing_source_receipt', 2),
          ('new_confirmed_out_in_final_vetting', 3), ('not_publishable_consumer', 2),
          ('new_out_via_actual_vetter-r2', 3)]
for name, expected in checks:
    case = OUT / name
    for d in ['run', 'vet', 'fv']:
        shutil.copytree(m.OUT / name / d, case / d)
    r = m.invoke(case)
    assert r['exit_code'] == expected, (name, r)
    assert r['output_exists'] == (expected == 0)
    assert not r['unrestricted_reads']
    r['expected_exit_code'] = expected
    r['message'] = (case / 'log.txt').read_text().splitlines()[0]
    result['cases'][name] = r
base = result['cases']['baseline']
assert base['promotion']['promoted_from_rank'] == 5
assert base['promotion']['selection_mean'] == 143.5388748758316
assert base['promotion']['eligible_delivered_ranks'] == [*range(1, 29), 30]
bp = OUT / 'baseline/out/book.csv'
before = m.rows(OUT / 'baseline/vet/book.csv')
after = m.rows(bp)
assert after == [before[4], *before[:4], *before[5:]]
result['baseline_csv_exact_permutation'] = True
result['baseline_book_sha256'] = m.sha(bp)
# Additional semantic boundaries from the final-vetter flag vocabulary.
spec = importlib.util.spec_from_file_location('promotion_v12', m.TOOL)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
stops = ['DK:OUT', 'DK:O', 'report:OUT', 'features:OUT', 'backup_qb:behind-healthy-primary',
         'backup_qb:depth2:behind-healthy-starter', 'qb:gated/healthy', 'placeholder_salary']
nostops = ['backup_qb:ambiguous(doubtful)', 'backup_qb:unknown(healthy)',
           'backup_qb:depth2:no-depth-1-on-file', 'backup_qb:depth2:starter-doubtful',
           'market:VANISHED', 'market:no_props', 'DK:Doubtful', 'DK:Q',
           'report:Questionable', 'qb:ambiguous/doubtful', 'qb:unknown/unknown',
           'practice:DNP(knee, market silent)']
assert all(tool.unavailable_by_flag(f) for f in stops)
assert not any(tool.unavailable_by_flag(f) for f in nostops)
result['flag_classification'] = dict(stops=stops, does_not_stop=nostops, passed=True)
# The existing check-packet path must also remain outcome-column restricted.
packet = m.ROOT / 'reselection-proposals/frozen-books.json'
argv = [str(m.TOOL), '--check-packet', str(packet), '--run-dir', str(OUT / 'baseline/run')]
log = io.StringIO()
start = len(m.calls)
with patch.object(sys, 'argv', argv), patch.object(m.pd, 'read_parquet', m.restricted), \
        contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
    try:
        runpy.run_path(str(m.TOOL), run_name='__main__')
    except SystemExit as e:
        assert e.code == 0
packet_result = json.loads(log.getvalue())
assert packet_result['PASS'] and packet_result['abs_diff'] == 0
assert all(x['requested'] is not None for x in m.calls[start:])
result['packet'] = packet_result
result['current_outcome_values_read'] = False
result['provider_calls'] = 0
result['all_expected_behaviors_pass'] = True
m.dump(OUT / 'result.json', result)
print(json.dumps(dict(cases={k: dict(exit=v['exit_code'], expected=v['expected_exit_code'],
                                   output=v['output_exists']) for k, v in result['cases'].items()},
                     baseline=base['promotion'], csv_exact=True, packet=packet_result,
                     result_sha256=m.sha(OUT / 'result.json')), indent=2))
