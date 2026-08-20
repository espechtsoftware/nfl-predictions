# Beat-the-winner scorecard, and what "one good lineup" can honestly mean

**Date:** 2026-08-20. Operator ask: prove in the offseason that we
consistently produce at least one good-scoring lineup, ideally one that
would have beaten a Millionaire-Maker winner, and have Week-1's exact
configuration already tested before Week 1.

The first half of that ask has never been computed explicitly. It is
computed here, from committed receipts only (ATLAS attempt-2 control
cells = the registered money book; all-boom S cells = the boom-deep
book; N1 winner report = the 51 tracked winning scores). No new run,
no new outcome exposure.

## 1. The scorecard, paired slate by slate

| Book | Beat that week's winner | Within 10 | Within 25 | Median gap |
|---|---|---|---|---|
| Money book best (S) | **0 / 50** | 0 | 1 | **+53.4** |
| Registered pool ceiling (C) | 0 / 51 | 0 | 2 | +43.2 |
| Boom-deep book (S) | 0 / 50 | 0 | 2 | +52.5 |
| Boom-deep pool ceiling (C) | 0 / 51 | 1 | 10 | +36.2 |

Winner scores: median **233.2**, 10th percentile 205.4, minimum 178.3;
only 2 of 51 winners scored under 190. Our book's weekly best: mean
178.6, median 177.5, best-ever 223.9, worst 150.2.

**Read it plainly: we have never once, on any of 50 paired slates, had
a lineup that would have won the Millionaire.** Not with the production
book, not with the pool ceiling, not with the boom-deep variant. The
median shortfall is ~53 points — roughly a third of a winning score.
Even our single best week in three seasons (223.9) sits below the
median winner. The gap is structural, not a near miss.

## 2. What our book DOES deliver, weekly

Probability that the 80-entry book's best lineup clears a line, over 53
slates:

| Line | 160 | 170 | 180 | 187 | 194 | 200 | 210 |
|---|---|---|---|---|---|---|---|
| Hit rate | 87% | 66% | 42% | 30% | **17%** | 13% | 4% |

The 80-lineup *average* is 115.0. So the honest characterization of
"one good lineup" today: we reliably (≈2 weeks in 3) produce at least
one lineup in the 170s, we clear 187 in about 3 weeks of 10, and we
clear the operator's 194 target in about 1 week in 6.

## 3. Reframing the goal so it is provable and worth proving

Beating the #1 finisher of a ~150,000-entry field is not the
profitability bar and not a reachable offseason proof point. The
Millionaire pays thousands of places; the money is made by consistently
placing, with occasional deep finishes. Three consequences:

1. **Retire "beat the winner" as a program target.** Keep it as a
   diagnostic ceiling (it is exactly the H-oracle style upper bound we
   already track), not a goal. Chasing it directly is what produced the
   winner-anatomy findings: the winners' shapes are unreachable under
   our mandates, and the law does not rank them first anyway.
2. **Adopt a payout-relevant target instead.** The right Week-1
   scorecard is the score needed to CASH and to reach the top ~1% of
   the field, which we can measure from real contest data we already
   hold (`nfl_raw.contest_ownership` names the contest and entry count
   each week; the standings imports from Week 1 give the actual
   score-to-rank curve). Preregister the cash line and the top-1% line
   BEFORE Week 1, then grade against them weekly.
3. **The 194 target keeps its meaning as a construction ceiling** — it
   is where our own tail lives, and every arm is still measured on it.
   But it should not be conflated with winning.

## 4. Week-1 readiness plan (the "already tested what we'll run" half)

What must be true before the Week-1 lock, in dependency order:

| # | Item | Status |
|---|---|---|
| W1 | **Dress rehearsal of the exact production path** on a stored real slate: `project-slate` → shadow freeze → DK CSV export → legality check on every exported lineup. Proves the code we will run actually runs, end to end, before it matters | TO BUILD — highest priority |
| W2 | **Preregistered Week-1 scorecard**: expected book-best distribution (from §2), the cash line and top-1% line from real contest data, and the grading procedure | TO WRITE |
| W3 | Shadow fleet complete: `shadow-cbwu-volume` (B1) implemented + scheduled alongside the existing shadows | Core done; CLI + schedule + grading spec remain |
| W4 | `contest_entries` collection verified on the first Monday download (never received a row; DK purges in ~4 days) | Operator cadence |
| W5 | Scheduler resume (~Aug 24) with no research lever enabled on the money path | Operator action |
| W6 | A3 stack-carve verdict folded in (if it clears, its shape relaxation is a Week-1 candidate ONLY through a shadow, never direct adoption) | Grid running |

**W1 is the item that most directly answers the operator's ask.** It is
not a score experiment — it is a machinery rehearsal: run the real jobs,
on the real image, against a real stored slate, and verify every
artifact the Sunday path must produce. Failures found in a rehearsal
cost nothing; failures found at 11:20 Sunday cost the week.

## 5. Rehearsal results (2026-08-19/20) — three legs exercised

**Leg 1 — `ingest-dk` (slates/salaries): WAS BROKEN, NOW FIXED AND VERIFIED.**
Three independent defects each fatal to Week 1 (draft-group filter matched
zero groups; showdown slates misclassified; timestamp + clustering both
rejected by BigQuery). `dk_salaries` had been empty with the scheduler
enabled. Repaired and verified live: 17 slates, 2,413 rows. See the
deficiency log row dated 2026-08-20.

**Leg 2 — `build-features` crosswalk: BLOCKED BY LEG 1, NOW UNBLOCKED
(needs a run).** `nfl_features.player_id_map` holds ZERO rows — a direct
cascade of the empty `dk_salaries`, since the crosswalk is built from it.
Nothing is wrong with the crosswalk logic; it has simply never had input.
Tested read-only against the newly ingested real slates: the join matches
**564 of 1,049** preseason players (54%).

**Leg 3 — `project`: FAILS, correctly, and this is the operational
finding.** `run_projections.upcoming_slate_features` raises hard when ANY
slate player lacks a GSIS mapping ("a dropped player is a lineup you
can't build"). With the crosswalk empty it refused on 990 players.

The 54% preseason match rate is NOT itself alarming — preseason rosters
carry third-string and camp players (long snappers, UDFAs) that nflverse
has no ID for, and `nfl_raw.player_ids` currently holds 7,985 entries with
no 2026 additions because `s-nflverse` is paused and nflverse serves only
started seasons. A regular-season Sunday-main slate is ~300–400 mostly
established players and will match far better.

**But the fail-closed design makes ANY unmatched player a hard stop.** So
the Week-1 sequence must be, in order and verified before Sunday:

1. Resume `s-nflverse`; confirm 2026 rows land in `player_ids` /
   `rosters_weekly`.
2. Let `ingest-dk` land a real Week-1 slate (now that it works).
3. Run `build-features`; confirm `player_id_map` is non-empty.
4. **Run `project` and read the unmatched list.** Every straggler
   (rookies, new signings, name variants) must be added to
   `nfl_features.player_id_overrides` BEFORE the Sunday path runs.
5. Only then are the book-freeze and CSV-export legs rehearsable.

Steps 1–3 are gated on the season starting and on the operator resuming
schedulers; step 4 is the one that historically bites and should be run
the moment step 3 succeeds, not on Sunday morning.
