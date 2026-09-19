"""Forecast-only reader-contract check; never opens or fabricates actual outcomes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path('/home/erich/projects/review-evidence/overnight-20260918/prospective-d1600-bundle')
READER = Path('/home/erich/projects/.nfl-predictions-worktrees/prospective-proper-score-review/reports/reviews/evidence/2026-09-19-prospective-proper-score-reader.py')
PEER = Path('/home/erich/projects/.nfl2-worktrees/prereg101-review-reply/handoffs/patches/2026-09-19-prospective-bundle-manifest-v4.json')
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

assert sha(READER) == '99d43b7e90b1e9f1bee4d9642e03467dfdb7f745a2940e5c935f3d5281130b13'
assert sha(ROOT / 'manifest.json') == '839f4b887a45a8c89a60c3c021063c4d9f7a16d70a3dad205e6eb2a51fc46bd8'
spec = importlib.util.spec_from_file_location('prospective_v4', READER)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
m = json.loads((ROOT / 'manifest.json').read_text())
p = json.loads(PEER.read_text())
def subset(want, got):
    if isinstance(want, dict):
        for k, v in want.items():
            subset(v, got[k])
    else:
        assert want == got, (want, got)
subset(p, m)
assert 'entered_book' not in m
games = r.bundle_games(m, ROOT)
side_to_game = {sides: gid for gid, sides in games.items()}
assert len(side_to_game) == len(games) == 13
arms = {}
frames = {}
for name, arm in m['arms'].items():
    fr, banks = r.load_arm(arm, ROOT)
    assert not {'actual', 'points'} & set(fr.columns)
    ids = set(fr.id.astype(str))
    book = r.load_book(arm['book_orders'], ROOT, ids)
    assert len(book) == arm['expected_book_size'] == 97
    assert all(set(lineup) <= ids for lineup in book)
    for row in fr.itertuples():
        assert side_to_game[frozenset((row.team, row.opp))] == str(row.game_id)
        assert int(row.season) == 2026 and int(row.week) == 2
    frames[name] = fr.set_index('id')
    arms[name] = {'players': len(fr), 'banks': {k: list(v.shape) for k, v in banks.items()},
                  'book_size': len(book), 'all_rosters_supported': True,
                  'every_frame_row_bound_to_own_game': True}
common = frames['control'].index.intersection(frames['salaryfix'].index)
assert frames['control'].loc[common, ['pos','team','opp','game_id']].equals(
    frames['salaryfix'].loc[common, ['pos','team','opp','game_id']])
eligible = json.loads(r.opened(m['prior_eligible_ids'], ROOT).read_text())
assert len(eligible) == len(set(eligible)) == 27
assert set(eligible) <= set(frames['salaryfix'].index)
# Real CLI clock, deliberately nonexistent outcome paths. The time guard must precede any file read.
cmd = [sys.executable, str(READER), '--bundle', str(ROOT), '--actuals', '/nonexistent/actuals.parquet',
       '--actuals-manifest', '/nonexistent/actuals-manifest.json', '--actuals-manifest-sha256', 'none',
       '--out', '/nonexistent/result.json']
proc = subprocess.run(cmd, capture_output=True, text=True)
assert proc.returncode != 0 and 'outcome gate:' in proc.stderr
assert 'FileNotFoundError' not in proc.stderr
print(json.dumps({'reader_sha256': sha(READER), 'bundle_manifest_sha256': sha(ROOT/'manifest.json'),
                  'peer_manifest_required_fields_exact': True, 'arms': arms, 'games': len(games),
                  'shared_players': len(common), 'prior_eligible_players': len(eligible),
                  'cross_arm_metadata_exact': True, 'real_clock_refuses_before_file_reads': True,
                  'outcomes_read': False, 'entered_book_claim': False}, indent=2))
