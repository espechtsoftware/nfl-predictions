# Per-contest selection objectives: tested on the live Week-2 book (2026-09-18)

The operator asked for a different selection per contest, with the objective tuned to the contest's size and to how
many entries he holds in it. That is a well-posed idea and the machinery already exists (`live_week.py --selector
{dual_emax, cov194}`, and every run dir stores three orderings: `book_rank` = dual expected-max, `book_rank_cov` =
coverage of the 194 line, `book_rank_wemax` = the winner-utility proxy). This is the test.

## Method

The live Week-2 rehearsal book (`20260917T150719330879Z-e7255e9`, 6,400 candidates, 20,000 worlds from the incumbent
and corrected-hsim banks) was re-selected **per contest** by greedy coverage of that contest's own payout threshold,
then compared with the entered dual expected-max order truncated to that contest's entry count. Thresholds come from
what each contest actually pays:

| contest | entries | its cutoff | why |
|---|---:|---:|---|
| $3M Millionaire | 1 | 228 | Week-1 top-1,000 line |
| Flea Flicker | 23 | 194 | top-heavy, needs a deep run |
| Nickel | 5 | 190 | top few % |
| SUPERSat 25x | 16 / 10 | 190 | a seat at roughly the top 4 % |
| FFWC satellite 4x | 2 | 168 | a seat at roughly the top 25 % |
| $19 satellite 2x | 2 | 145 | a seat at roughly the top 50 % |

## Result: the objectives agree, so tuning gains nothing

Probability that at least one of that contest's entries reaches its own cutoff:

| contest | cutoff | current (dual e-max top-N) | tuned (coverage at its cutoff) | gain |
|---|---:|---:|---:|---:|
| Millionaire (1) | 228 | 0.009 | 0.009 | +0.000 |
| Flea Flicker (23) | 194 | 0.401 | 0.404 | +0.003 |
| Nickel (5) | 190 | 0.259 | 0.260 | +0.001 |
| SUPERSat 25x (16) | 190 | 0.415 | 0.419 | +0.003 |
| SUPERSat 25x (10) | 190 | 0.351 | 0.353 | +0.002 |
| FFWC sat (2) | 168 | 0.417 | 0.417 | +0.000 |
| $19 sat (2) | 145 | 0.774 | 0.774 | +0.000 |

**Why it is null, and this is the important part:** the entered book is *already* the best answer to every one of these
questions at the single-lineup level. For every cutoff from 145 to 228, the entered rank-1 lineup **is** the candidate
with the highest probability of clearing it (0.606 at 145, 0.282 at 168, 0.100 at 190, 0.009 at 228 — identical to the
best of all 6,400 candidates), and entered rank 2 is the second best. Greedy expected-max produces an ordering that is
simultaneously near-optimal for a whole family of thresholds, because a lineup that clears 190 in many worlds is
usually the same lineup that clears 145 and 228 in many worlds.

Where the tuned selection does differ is deeper in the block (18 of 23 shared for the Flea Flicker, 10 of 16 for the
big satellite), and those differences are worth about a third of a percentage point.

## What this means for the operator's request

- **Per-contest *objectives* are already satisfied by the single ordering.** There is no separate "satellite lineup"
  worth building: the highest-floor lineup for a 50 %-cutoff satellite and the highest-ceiling lineup for a
  1-in-100,000 Millionaire are the same lineup in this book, and that is a property of the book, not an assumption.
- **Per-contest *entry counts* are already handled**: each contest takes ranks 1..N, which is exactly greedy
  expected-max's answer for a book of size N, since the greedy sequence is nested.
- **The live remaining choice is the allocation one** (repeat the top block in the five satellites, or give each its
  own block), which is a variance decision, not a selection-objective decision, and is the subject of the separate
  decision document.

This is consistent with the ledger: coverage-194, novelty ladders and union expected-max were all measured against
expected-max in PREREG-060/066/076/094/095 and none moved the book more than ±0.006. The same result appears here on
live Week-2 data.

**Caveat.** Both orderings are scored on the same simulated worlds, so this shows the objectives agree *under the
current law*. It does not show that either is right about reality; the simulator's extreme tail is known to be
optimistic. It also uses no field model — a real satellite cutoff is field-relative and stochastic, not a fixed score.
