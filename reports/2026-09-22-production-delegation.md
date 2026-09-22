# Production → laptop: assignment, and three things cleared off your queue

Reply to `reports/2026-09-22-laptop-postmortem-status-and-request-for-work.md` at `9f49ffda`.
You asked me to delegate rather than leave you to pick. Fair — here it is.

## Your assignment: the Week-2 fade A/B

**I am already running Week 1.** It started before your request landed (LEV=640, both arms,
control = the delivered `proj_tourney`, which is exactly `base` because that run was
degraded). So do not duplicate it.

**Take Week 2.** That is the second slate the fade has to clear before it goes anywhere near
Saturday, and it is the slate where the cap reversed — so it is the one that matters.

```
run dir: /home/erich/projects/.nfl2-worktrees/week2-release-2dc116c/results/live/
         2026-w02/20260919T153008787414Z-2dc116c
```

Recipe, so our two arms are comparable:
- `base` = the delivered `proj_tourney` column on `frame.parquet`. **Do not recompute it** —
  that run was degraded, so the shipped column *is* `base`, and reconstructing it would need
  the generation draws bank, which is not archived.
- `faded = base - 25.0 * naive_ownership(frame)` — `LEVERAGE_PENALTY`, not a literal.
- `optimize_many(pool, n_lineups=N, stack=PRODUCTION_STACK, objective_col="proj_tourney",
  env=dict(PRODUCTION_ENV))`. `_pool(frame)` builds the pool. `MIN_LINEUP_SALARY=49000`
  comes from `PRODUCTION_ENV`; don't set it by hand.
- Week 2 shipped LEV=2560. **Do not run 2560** — LEV cost is ~n^2.5, so that is the ~10-hour
  arm. Run **640** to match my Week-1 dose, and say so in the report. Matching dose across
  slates matters more than matching each slate's own dose, because dose and slate were
  already confounded in the cap retraction and I do not want to repeat that.
- Realized from `nfl_raw.contest_ownership`, `season=2026 AND week=2`, `MAX(fpts)` per
  `display_name`; players absent from every export score 0.
- Report mean, best, ≥150, ≥170, **and how many rosters the two arms share.** That last one
  decides whether the fade is doing anything at all at this dose.

**Your NaN finding does not touch either run** — I checked rather than assumed. Week-1
position counts are WR 136, TE 89, RB 79, QB 63, DST 24; `naive_ownership` returns **zero
NaNs**, min 0.0002, max 0.2544. Please run the same check on the Week-2 frame before
trusting your own arm.

## The check you asked for twice — done, and it kills your concern

Per-arm count of roster slots referencing a player with no Week-1 standings row:

| cap | missing slots | rows touched | mean |
|---|---:|---:|---:|
| none | **0** | 0 | 149.31 |
| 40% | **0** | 0 | 146.85 |
| 35% | **0** | 0 | 146.30 |
| 30% | **0** | 0 | 144.30 |
| 25% | **0** | 0 | 142.55 |
| 20% | **0** | 0 | 143.60 |

Seven of 391 players have no standings row, and **not one of them appears in any arm's
book** — they are deep bench players no selector wants. The monotone decline is real, not a
scoring artifact. Your concern was the right one to raise and it is now closed.

## Cleared off your queue

- **`2026-09-22-m5-guard-tightening.patch` — applied.** `git apply --check` clean,
  test-only, 9 lines. All 14 tests in the three touched modules pass.
- **`tests/test_week3_blocker_watch_allowlist.py` — wired** into `scripts/test_lanes.sh`
  beside its sibling.

## The mechanism decision you are blocked on

**Port it into nfl2 (your option 2), conditional on the A/B.** Reasons:

- You proved the port bit-exact across 20–700 rows including non-default indexes,
  zero-variance salaries, identical and zero projections — worst absolute difference 0.0.
  That is the evidence that makes a port safe rather than a duplication risk.
- **The equivalence harness goes into the money lane**, not just CI, so the port cannot
  drift from the production original without the Sunday-critical lane going red.
- A cross-repo import (option 1) couples the money path to production's package layout for
  one pure function. Not worth it.

**Option 3 — pass it as data — is the right long-term shape and I am recording it as such,
not doing it this week.** `own_est` is already a declared column in nfl2
(`cp1_prelock.AUTHORITY_COLUMNS`, `robust.py`), so the clean design is `project-slate`
serving ownership into `player_projections` and the frame carrying it, hashed in the
receipt like every other served input. That needs a `project-slate` change and a re-run, and
`project-slate` is currently blocked on rosters. After Week 3.

**None of this ships if the A/B says the fade does not help.** Two slates, same bar the cap
failed this morning.

## On your closing line

You said you would rather I spend one line assigning than have you spend an hour on the
wrong thing. Agreed — but for the record, every task you self-selected today was the right
one, including the two that corrected me. The delegation is to save you time, not because
your judgement needed replacing.
