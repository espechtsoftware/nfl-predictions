"""Actual refreshed warehouse through unchanged candidate CLI; no scratch router."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

LAB=Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
ROOT=Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')
EXPECTED='2dc116ce95647a776ba9c36cf194f44d022d03a4'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    assert (ROOT/'project-slate-result.json').exists()
    assert Path.cwd()==LAB
    assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==EXPECTED
    assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
    sys.path.insert(0,str(LAB/'src'))
    os.environ['NFL2_LIVE_CENTER']='production'
    from nfl2 import live,data
    # A fresh local model-training cache, populated by the real warehouse query.
    live.CACHE=ROOT/'live-cli-cache';assert not live.CACHE.exists()
    live.training_panel_through.cache_clear()
    sys.argv=['scripts/live_week.py','--season','2026','--week','2','--group','153428',
       '--entries','97','--lev','32','--boom','128','--sims','10000','--k','1',
       '--seed','2026','--selector','dual_emax','--emit-a5-sidecars']
    with data.outcome_firewall(2026):
        state=runpy.run_path(str(LAB/'scripts/live_week.py'),run_name='__main__')
    out=state['out'].resolve();r=json.loads((out/'receipt.json').read_text())
    assert r['identity']['sha']==EXPECTED and not r['identity']['dirty']
    assert r['season']==2026 and r['week']==2 and r['draft_group']==153428
    assert r['written']==97 and r['candidates']>=97
    assert r['inputs']['book_contract']['dk_violations']==r['inputs']['book_contract']['strategy_violations']==0
    assert r['config']['selector']=='dual_emax' and r['config']['production_rows']>0
    assert r['config']['production_generated_at'][:10]=='2026-09-19'
    assert r['config']['hsim_game_inputs']['source']=='live_schedule_validated_against_frame'
    assert len(r['config']['hsim_game_inputs']['games'])==r['inputs']['games']==13
    assert len(state['book'])==97 if 'book' in state else r['written']==97
    result=dict(run=str(out),source_sha=EXPECTED,receipt_sha256=sha(out/'receipt.json'),
      adapter_sha256=sha(__file__),receipt=r,all_normal_cli_guards_enabled=True,
      warehouse='live production, no router or scratch substitutions',current_outcomes_read=False,
      scope='small D160 engineering proof; not entered or uploaded; production doses unchanged')
    with (ROOT/'live-cli-proof.json').open('x') as f:json.dump(result,f,indent=2)
    print('LIVE_RELEASE_CLI_PROOF_PASS',out,flush=True)

if __name__=='__main__':main()
