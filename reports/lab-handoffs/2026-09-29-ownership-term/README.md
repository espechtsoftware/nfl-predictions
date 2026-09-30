# Ownership-term scripts (2026-09-29)

Evidence behind `reports/2026-09-29-ownership-term-week4-arming.md`. Everything is read-only against the warehouse, the
private bucket and the lab's code. All data stays outside the repository: the standings carry user names, the week's
plan file is private, and the LineStar values are third-party.

Environment the scripts read:

| Variable | What |
|---|---|
| `LAB_WT` | a lab checkout at L18's freeze (`fb397d9`), imported read-only; never a worktree a panel runs from |
| `PANEL_DIR` | the directory `01_panel_term.py` is run from (its run directories land there) |
| `PLAN_FILE` | the week's `contests.json` (private; never printed, never committed) |
| `ENTER_LAYOUT_PY` | `src/nfl_dfs/inference/enter_layout.py` of the production checkout |
| `DATA_DIR` | a private data directory holding `winners/own_pts.parquet`, `winners/entries_all.parquet` (from the winners study's `01_pull_entries.py`) and `own/` (the archived run dirs and `own2026_w<W>.parquet`) |

```bash
LAB_PY=~/projects/nfl2/.venv/bin/python; PY=~/projects/nfl-predictions/.venv/bin/python; H=<checkout>/reports/lab-handoffs/2026-09-29-ownership-term
cd $PANEL_DIR
# ownership files per slate: the lab's results/l05_sets/lag (lag model), results/l15_sets/blend_pct (lag + LineStar),
# and `scripts/ownership_sets.py replay-sets --seasons 2023,2024 --out basesets` (base model)
$PY $H/02_build_blend_sets.py basesets baseblend           # base model + LineStar; needs lscache/ (the L15 cache from the private bucket)
$LAB_PY $H/01_panel_term.py 1240 tilt3  base=0,blend20=0.2,blend30=0.3,blend40=0.4 blendsets     # about 5 minutes on 12 workers
$LAB_PY $H/01_panel_term.py 1241 tilt3b base=0,blend10=0.1,blend20=0.2,blend30=0.3 blendsets
$LAB_PY $H/01_panel_term.py 1241 tilt3lag base=0,lag10=0.1,lag20=0.2 lagsets
$LAB_PY $H/01_panel_term.py 1240 tilt4a base=0,bblend10=0.1,bblend20=0.2,bblend30=0.3 baseblend
$LAB_PY $H/01_panel_term.py 1241 tilt4b base=0,bblend10=0.1,bblend20=0.2,bblend30=0.3 baseblend
$LAB_PY $H/01_panel_term.py 1240 tilt4c base=0,bm10=0.1,bm20=0.2 basesets
$PY $H/03_read_arms.py tilt3 tilt3b tilt3lag tilt4a tilt4b tilt4c     # §2.1-2.3: rates, the paired gain, the head-layout tickets
$PY $H/04_by_rank.py tilt3 tilt3b                                     # §2.3: by position in the book
# §2.4: the 2026 replay, with the PATCHED tool and the Week-4 pinned lab clone
PYTHONPATH=<pinned clone>/src:<checkout>/src $LAB_PY $H/05_replay_2026.py <checkout>/scripts rehearsal
# the addendum (reports/2026-09-29-ownership-term-addendum-routing-and-dealing.md): 100 main rows, and the layouts
KROWS=100 WORKERS=14 $LAB_PY $H/01_panel_term.py 1240 k100a base=0,blend20=0.2 blendsets       # about 6 minutes
KROWS=100 WORKERS=14 $LAB_PY $H/01_panel_term.py 1241 k100b base=0,blend20=0.2 blendsets
$PY $H/06_read_k100.py k100a k100b                        # §1: by contest class under head and spread; p99 / p99.8 by row block
$PY $H/07_read_layouts.py routed k100a k100b              # §3: head, spread as built, spread with one offset per contest
$PY $H/07_read_layouts.py filed tilt3 tilt3b
```

`06_read_k100.py` and `07_read_layouts.py` need `ENTER_LAYOUT_PY` from a checkout that has the `spread` layout
(integration `f0da76d5` or later). "routed" holds the plan's deep-line supersats on the main book.

The review of the 35-answers report (`reports/2026-09-29-review-of-the-35-answers-and-the-week4-actions.md`, §3):

```bash
LAB_WT=<lab checkout at fb397d9> $LAB_PY $H/08_projection_vs_market.py     # the served projection vs the market, player level
LAB_WT=<lab checkout at fb397d9> $LAB_PY $H/09_dst_rank_skill.py           # the DST projection's rank skill
PANEL_DIR=$PANEL_DIR $PY $H/10_double_up_read.py tilt3 tilt3b k100a k100b  # the same books in a double-up
```

The 2026 ownership files (`own2026_w<W>.parquet`) are the ownership model's predictions for the week's slate with
`implied_team_total` taken from the archived frame. `ownership_sets.py sets` for a past week finds no rows in
`player_week_inference`, leaves that input empty for every player, and its predictions collapse; see the report's §4.
LineStar's 2026 values were fetched after the fact with `scripts/linestar_ownership_capture.py` and are not provably
pre-lock.
