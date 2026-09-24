# Corpus, selection and sorting scripts (2026-09-24)

Evidence behind `reports/2026-09-24-corpus-selection-sorting-research.md`. Read-only against the warehouse and
the panel's archived GCS score matrices; nothing touches the money path. All data stays outside the repo.

Prerequisites (from the earlier external-review scripts, now on `origin/main` and the integration branch under
`reports/lab-handoffs/2026-09-22-external-review/`):

- `REVIEW_INPUTS`: the output directory of `pull_inputs.py`.
- `WIN`: the winner-anatomy data directory after `prep.py`, `prep2.py`, `build.py`, `ours.py` and
  `registry2.py`/`registry3.py` have run in it.
- `WIN_SCRIPTS`: the `winner_anatomy/` script folder (for `feat.py`).

```bash
export REVIEW_INPUTS=~/.cache/nfl-dfs-external-review WIN=~/.cache/nfl-dfs-winner-anatomy
export WIN_SCRIPTS=<checkout>/reports/lab-handoffs/2026-09-22-external-review/winner_anatomy
export TESTBED=~/.cache/nfl-dfs-selection-testbed W2_RUN=<archived Week-2 D12800 run dir>
S=<checkout>/reports/lab-handoffs/2026-09-24-corpus-selection-sorting
PY=~/projects/nfl-predictions/.venv/bin/python
mkdir -p $TESTBED && cd $TESTBED
$PY $S/pull_testbed.py        # 107 historical pools + their world matrices (~0.9 GB), W1/W2 served p90
$PY $S/bed.py                 # player table: actual Millionaire ownership (2022-25) and leave-one-season-out predicted ownership
$PY $S/run_sel.py && $PY $S/summarize.py     # §4 selectors and §5.1 within-book orders
$PY $S/run_sort2.py           # §5.2 prefix maxima and disjoint slices
$PY $S/layout.py              # §5.3 sequential vs snake vs top layout on the Week-2 contest sizes
git -C <checkout> show origin/production/week3-integration-20260921:src/nfl_dfs/inference/enter_layout.py > enter_layout.py
ENTER_LAYOUT_PY=$PWD/enter_layout.py $PY $S/head_replay.py   # follow-up note §2: the Week-3 head layout, production's own rule
$PY $S/corpus.py              # §3.4 which candidates reach each pool's top 5
$PY $S/sort_pitk1.py          # §5.1 replication on the 72 replay books
cd $WIN
$PY $S/sleeve_reach.py        # §3.1 real top finishers inside the sleeve region (RULE=oracle for the oracle-sized set)
$PY $S/reach2.py              # §3.2 the same with the house stack rule vs a relaxed stack
$PY $S/reach_registry.py && $PY $S/reach_check2.py    # §3.2-3.3 the registry winners (50 with a full team match)
```

Low-owned ("LOW") everywhere means production's live rule: skill players outside the top 10.1% of the slate's
skill players by predicted ownership. CHALK means the top 15 players by predicted ownership. Runtime is a few minutes
per script on one core, apart from the download.
