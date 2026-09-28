# Week-3 review scripts (2026-09-28)

Evidence behind `reports/2026-09-28-week3-review-and-major-changes.md`. Everything is read-only against the warehouse,
the private bucket and the 09-24 review's historical test bed. All data stays outside the repo: the standings carry user
names, and the run dir and contest ladders are private-bucket objects.

Layout the scripts expect (paths are relative to the directory each is run from):

```
$W3DIR/                       # a data directory outside the repo
  contest-details-20260927.json   # gs://.../private/rehearsal/2026-w03/ (public contest ids + payout ladders)
  run/                            # gs://.../private/rehearsal/2026-w03/20260926T153408285093Z-65305f5/ (frame, candidates, both banks, receipt, book)
$TESTBED/                     # the 09-24 review's test bed (pull_testbed.py): cands.parquet, spf_full.parquet, players_bed.parquet
$QDIR/                        # injuries / depth charts pulled by the two hist_pull_* scripts
```

```bash
PY=~/projects/nfl-predictions/.venv/bin/python; S=<checkout>/reports/lab-handoffs/2026-09-28-week3-review
cd $W3DIR
$PY $S/w3_field_lines.py        # §2: every contest's ticket line, field percentile, composition; writes contest_meta.csv, contest_lines.csv, entries/own parquets, pts_w3.csv
$PY $S/w3_economics.py          # §2: rake, base rate, break-even rate, edge needed per contest type
$PY $S/w3_q_active.py           # §5.2: Questionable-at-Saturday players still active at the last pull, Weeks 1-3
$PY $S/w3_pull_field.py         # §4: per-entry shape features for the three Millionaire fields (reuses the laptop's milly_shape_lift.py SQL; ~1.17M rows)
cd run
$PY $S/w3_pool_score.py         # §4/§6: scores every pool row with official points; books vs the real lines; writes cands_scored.parquet
$PY $S/w3_pool_rerank.py        # §7: production's rule vs each bank's mean vs P(>=line) selections
$PY $S/w3_milp.py               # §6: the frame optimum by mean and by the tournament valuation; 30 diverse rows
$PY $S/w3_milp144.py            # §6: 144 diverse rows by mean (about 3 minutes)
$PY $S/w3_hsim_check.py         # §7: the corrected-hsim bank's player shifts vs Sunday's residuals
cd ..
$PY $S/w3_class_model.py        # §4: the walk-forward class model on the fields, and its application to the pool
cd $QDIR
$PY $S/hist_pull_injuries.py && $PY $S/hist_pull_depth.py
$PY $S/hist_vacated.py          # §5.1: backups of an out starter, replay panel (reads ../sel/ = $TESTBED)
cd $TESTBED
$PY $S/w3_market_floor.py       # §7: the market floor at the player level, 107 slates
$PY $S/hist_mean_books.py       # §6: top-mean books with exposure caps, 107 pools
$PY $S/hist_milp.py             # §6: plain-mean optimizer vs the pool's top-mean book, 107 slates (about 35 minutes)
```

`w3_class_model.py` uses scikit-learn from the production venv. `w3_milp*.py` and `hist_milp.py` use `pulp` with CBC.
