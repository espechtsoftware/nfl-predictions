# Production → laptop: assignment — the cross-repo lever audit. Your finding A, generalised.

Your `2026-09-22-laptop-research-audit-unturned-stones.md` §A is the most valuable thing
either of us has produced today, and it is now your next task.

## Why this and not the other twenty things

You found that `config_manifest.py` guards the adopted stack, reads six `nfl_dfs` modules,
and contains the string `nfl2` **zero times** — while the money path *is* nfl2. That is not
a missing test. That is a **guard pointed at the wrong repository**, and it is the reason an
adopted, twice-proven lever sat at zero for every live week of 2026 while the manifest
correctly reported zero discrepancies.

The chalk fade is one instance. **Nothing rules out others**, and I have already found
evidence there are.

## I ran the first pass. It is worse than one lever.

Grepping every adopted lever name across all of `nfl2/src` and `live_week.py`:

| lever | nfl2 files referencing |
|---|---:|
| **`OWN_MODEL`** | **0** ← the chalk fade, confirmed dead |
| **`MAX_OVERLAP`** | **0** |
| **`N_QB_VARIANTS`** | **0** |
| `MIN_GAMES` | 1 |
| `MIN_LOWOWN` | 2 |
| `VALUE2_MAX` | 2 |
| `OWN_BARBELL` | 2 |
| `MODEL_ENSEMBLE` | 3 |
| `N_BOOM` / `N_LEV` | 5 |
| `PUNT_MIN` | 7 |
| `MIN_LINEUP_SALARY` | 10 |

`N_QB_VARIANTS` is named in `CLAUDE.md`'s adopted stack explicitly — *"QF construction
(N_QB_VARIANTS=4)"*. If the live path never reads it, QB-variant construction may not be
happening at all on the money path.

## The one methodological rule, and it is the whole job

**A zero grep is a hypothesis, not a finding.** I am fairly confident `MAX_OVERLAP` is a
false positive: `optimize_many` takes `max_overlap: int = 7` as a *parameter*, so the lever
is plausibly applied under a different name rather than dead. That is exactly the trap.

The standard is the one the chalk fade had to clear: **trace the call path to the point of
use and show what value actually arrives.** For `own_est` that meant
`live_week.py:191 → proj_tourney_production(fr, draws) → own_est=None → degraded branch`,
plus two receipts showing `penalty 0.0` in production. Nothing less counts. A lever is
**dead** only when you can show the consuming code never receives it; a lever is
**live** when you can point at where its value lands.

Expected outcome: some of those zeros are renames, and some are real. **Both results are
worth having**, and "I chased three and all three were plumbed differently" is a perfectly
good report.

## Deliverables

1. **A verdict per lever** — live / dead / renamed-and-live — each with the call path or
   the receipt field that proves it. Not a grep table.
2. **For anything dead: what it would take to restore, and what it is worth.** The chalk
   fade's answer was "one line, and it is +2 twice-proven in replay". Yours may be
   "nothing, it was superseded" — say so.
3. **A test that fails closed when an adopted lever is declared-but-ignored across the repo
   boundary**, in the money lane, not CI. That is the durable part, and it is the thing that
   stops this recurring. It will need a declared consumption point per lever rather than a
   string match — design that as you see fit; you have seen more of both repos than I have
   today.

## Scope discipline

- **Do not fix anything you find this week.** Report it. The Doubtful change went in because
  it was one token and evidence-backed; anything bigger does not touch Saturday's path on
  four days' notice.
- **`week2-release-2dc116c` stays CLEAN at `2dc116c`.** The money clone
  `week3-live-center` is at `69f98a7` and is mine this week.
- If the Week-2 fade A/B on the real bucket frame is still outstanding, **finish that first**
  — it gates a decision; this audit does not.

## What I am holding

Week-1 fade A/B: control arm done (640 lineups, 44.5 min, mean 158.65, best 218.50,
≥150 409, ≥170 183, ≥194 25). Faded arm solving. I will not ship the fade on one slate.

## One thing I am taking to the operator, not to you

Your §B — tail calibration, the would-be PREREG-101 — is blocked on **three operator
questions, not on evidence or compute**, and the standing instruction is do-not-launch. That
is a signature, not a task, so it goes to him rather than into your queue. You were right
that it is the last stone standing: the simulator says the book's best lineup breaks 220
about 9% of the time against a true ~3%, and selection *amplifies* the error 1.6x → 2.8x.
