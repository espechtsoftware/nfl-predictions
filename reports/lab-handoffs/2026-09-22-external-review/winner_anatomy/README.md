# Winner anatomy scripts (2026-09-22)

Evidence behind `reports/2026-09-22-winner-anatomy-and-follow-up-review.md`. Read-only against the
warehouse. All data files are written to the **current directory**, which must be outside the repo:
they hold DraftKings standings with entry names, which are never committed.

```bash
export WIN=~/.cache/nfl-dfs-winner-anatomy; mkdir -p $WIN; cd $WIN
export REVIEW_INPUTS=~/.cache/nfl-dfs-external-review     # output of ../pull_inputs.py
export W2_RUN=<archived Week-2 D12800 run dir>
S=<repo>/reports/lab-handoffs/2026-09-22-external-review/winner_anatomy
PY=~/projects/nfl-predictions/.venv/bin/python
cp $REVIEW_INPUTS/live_proj_2026.csv $REVIEW_INPUTS/dk_points_2026.csv .
$PY $S/prep.py && $PY $S/prep2.py      # 1.29M field lineups, salaries, slot-summed ownership, schedules, box scores
$PY $S/build.py                        # per-lineup features for 7 contests (lineups.parquet), ~5 min
$PY $S/tiers.py                        # §2.1 lifts by finishing tier, both Millionaires + replication contests
$PY $S/ours.py && $PY $S/compare.py    # §2.2 field / top 0.1% / our books / our Week-2 pool
$PY $S/own_ctrl.py                     # §2.3 low-owned count within projection quintiles
$PY $S/shapes.py                       # §2.4 house-rule legality and the chalk-core shape
$PY $S/skill.py                        # §2.5 skill persistence and the skilled cohort's construction
$PY $S/registry2.py && $PY $S/registry3.py   # §2.6 the 69 registry winners
$PY $S/hist_own.py && $PY $S/own_model.py && $PY $S/hist_pred.py   # §2.7 72-slate replay books; ownership model
$PY $S/w1_preown.py                    # §3 own_shadow check
```

User names are hashed or factorized in every output; `acct.txt` (our account, found by its Week-2
signature as the cash-shadow script does) stays in the data directory.
