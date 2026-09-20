"""Independent synthetic boundary for promotion v2.1 ENTER re-layout.

The tool's row check incorrectly requires per-contest files to be contiguous
slices of the all-rows upload. That is false for both the chain's sequential
keeper/fill layout and the top-per-contest layout (which intentionally repeats
the prefix). This test uses no production data.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).parent
TOOL = Path('/home/erich/projects/.nfl2-worktrees/prereg101-review-reply/handoffs/tools/promote-first-v1.2/relayout_enter.sh')
VERIFY_PROD = Path('/home/erich/projects/.nfl-predictions-worktrees/qb-gate-review-20260919')
PY = '/home/erich/projects/nfl-predictions/.venv/bin/python'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(root, layout):
    out = root / ('out-' + (layout or 'default')); out.mkdir()
    env = dict(os.environ, CONTESTS_JSON=str(root / 'contests.json'), PROD=str(VERIFY_PROD), PY=PY)
    if layout is None: env.pop('ENTER_LAYOUT', None)
    else: env['ENTER_LAYOUT'] = layout
    p = subprocess.run(['bash', str(TOOL), str(root / 'upload.csv'), str(out), 'synthetic-' + (layout or 'default')],
                       env=env, text=True, capture_output=True, check=False)
    enter = out / 'ENTER'
    return dict(layout=layout or 'unset (script default)', exit_code=p.returncode,
                stdout=p.stdout, stderr=p.stderr, enter_exists=enter.exists(),
                published_bundle=sorted(str(x.relative_to(out)) for x in out.rglob('ENTER-*')),
                output_files=sorted(str(x.relative_to(out)) for x in out.rglob('*') if x.is_file()))


def main():
    root = Path(tempfile.mkdtemp(prefix='relayout-enter-row-check-', dir='/home/erich/projects/review-evidence/overnight-20260918'))
    contests = [{"name": "milly", "contest_id": "1", "entries": 2, "keep": 1},
                {"name": "flea", "contest_id": "2", "entries": 3, "keep": 1}]
    (root / 'contests.json').write_text(json.dumps(contests) + '\n')
    with (root / 'upload.csv').open('w', newline='') as f:
        w = csv.writer(f); w.writerow(['QB','RB','RB','WR','WR','WR','TE','FLEX','DST'])
        for i in range(1, 6): w.writerow([f'{i}-{j}' for j in range(9)])
    cases = [run(root, None), run(root, 'top'), run(root, 'sequential')]
    assert all(x['exit_code'] != 0 and not x['enter_exists'] for x in cases)
    assert all('staged bundle does not reproduce the upload order' in x['stdout'] for x in cases)
    result = dict(schema='promotion-v2.1-relayout-row-check/v1', tool_sha256=sha(TOOL),
                  verifier_sha256=sha(VERIFY_PROD / 'scripts/verify_enter_bundle.py'),
                  synthetic_contests=contests, input_sha256=sha(root / 'upload.csv'),
                  cases=cases, no_production_inputs=True, current_outcomes_read=False,
                  root=str(root))
    out = root / 'result.json'; out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({"tool_sha256": result['tool_sha256'], "cases": [
        {"layout": x['layout'], "exit": x['exit_code'], "enter": x['enter_exists'],
         "reason": x['stdout'].splitlines()[-1] if x['stdout'] else x['stderr']} for x in cases],
        "result_sha256": sha(out), "root": str(root)}, indent=2))


if __name__ == '__main__':
    main()
