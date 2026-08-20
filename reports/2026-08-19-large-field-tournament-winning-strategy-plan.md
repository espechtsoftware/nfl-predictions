# Large-field tournament winning strategy plan

**Date:** 2026-08-19
**Status:** strategy proposal for independent review; not a frozen protocol,
production-policy change, or claim that a Millionaire Maker win can be
guaranteed.
**Primary use case:** one exceptional DraftKings NFL Classic lineup from an
exact-80 weekly portfolio.
**Secondary use case:** large, sharp championship qualifiers with roughly
40,000 entries, where the relevant outcome may be one or several tickets
rather than a cash-payout curve.

## Executive conclusion

The strongest current diagnosis is not that the project needs a more exact
greedy selector. It is that the money path asks the selector the wrong
question.

Production currently builds an exact-80 book primarily to cover simulated
worlds above one 194-point threshold. Once a world is covered at 194, a lineup
that scores 245 in that world is not materially preferred to one that scores
195. The exact-selector audit showed that the greedy algorithm already solves
that objective to within 0.134%, while the all-boom experiment showed that a
much stronger candidate ceiling mostly failed to transfer into the selected
book. The next selection experiment should therefore change the **portfolio
utility**, not the optimizer algorithm.

The recommended next selection experiment, after the already-running A3 arm
releases the historical-outcome lease, is a frozen, exact-80,
multi-threshold `SELECT_LADDER` arm that protects the useful 194/200 shoulder
while materially valuing 210/220/230/240 outcomes. It should hold candidates,
worlds, legal constraints, compute, and book size fixed, and it should be read
as a paired selection-mechanism test on the incumbent candidate pool. The
boom-deep pool was explicitly shelved by its frozen null disposition and may be
revisited only in a separately frozen follow-up after a selector change first
proves that it can harvest the incumbent ceiling.

In parallel, the project should finish the already-running stack-relaxation
carve, deploy the already-built 20-book prospective volume shadow, then test
the measured dependence defect: generic teammate booms are over-coupled while
QB-to-WR booms are under-coupled. Full standings and pre-lock ownership
collection are prerequisites before adopting a genuine field-, duplication-,
and payout-aware strategy.

## What the project is optimizing today

The production policy is `classic-k1-role12-boom40-poscal-cbwu-v4`. It uses
five independent candidate books and an exact-80 greedy tail-coverage
portfolio at line 194. The UI accepts field size and contest entry cap, then
classifies caps as single-entry, 2-3-max, 4-20-max, or greater-than-20-max.
Smaller books are effectively prefixes of the same 80-entry selection ordering.
Contest size currently changes leverage heuristics more than it changes
portfolio utility.

The durable objective is the weekly maximum of the entered book, not average
lineup score. For a qualifier, however, even weekly maximum score is only a
proxy: the real utility is the probability of finishing at or above the last
ticket rank, adjusted for the contest's tie rule and duplication.

## Current evidence

### Baseline

Across the valid 54-slate 2023-2025 Sunday-main corpus, the adopted money book
has a mean weekly best score of **176.06**. Its threshold counts are:

| Score | Slates reaching score |
|---:|---:|
| 187 | 17 / 54 |
| 194 | 8 / 54 |
| 200 | 7 / 54 |
| 210 | 6 / 54 |
| 220 | 3 / 54 |
| 230 | 1 / 54 |
| 240 | 0 / 54 |

The direct winner comparison is sobering but should remain a ceiling
diagnostic rather than the optimization target: the money book beat the
tracked Millionaire Maker winner on 0/50 paired slates, had a median shortfall
of 53.4 points, and recorded a best-ever weekly maximum of 223.9. The tracked
winners had a median score of 233.2 and a 10th percentile of 205.4.

### Candidate supply improved; selected-book conversion did not

The all-boom candidate experiment raised mean pool ceiling C from **187.58 to
196.64 (+9.06)**, with 43 better slates, one worse, and ten tied. The unchanged
selector converted that into only **+1.34** selected-book points
(178.57 to 179.91; p=0.49; 19 better, 18 worse, 16 tied). The treatment C-S gap
widened to roughly 16.7 points. This is the clearest evidence that additional
tail supply is being stranded by admission or objective alignment.

### The selector algorithm is effectively closed

The A5 audit solved all 255 tested selection blocks exactly with CBC. The
production greedy selector missed only 2.84 covered worlds on average, or
**0.134%** of its fixed-194 objective; the worst observed gap was 0.70%.
Replacing greedy with beam search or a more exact optimizer cannot produce a
material change while the objective remains fixed.

### Construction occupies the wrong structural region

Of 51 tracked winners, 43 fail the current mandatory construction contract.
Production generates 100% of candidates with QB stack at least two and a
bring-back, a region containing only 16% of winners. In the winner set:

- 22% use a naked quarterback;
- 41% use exactly one quarterback partner;
- 61% use no bring-back; and
- 69% put no more than three players in any one game.

This does not prove that stacks are bad. It says that correlation should be
rewarded by a realistic simulation law and selected when useful, rather than
forced into every lineup. The bounded A3 carve is the correct current test;
wholesale deletion or a post-hoc dose sweep is not.

### Historical winners are chalk core plus leverage, not pure contrarianism

Winner ownership has median cumulative ownership of 104.5% and a median of
four players below 10% ownership. The practical template is a recognizable
chalk core combined with roughly three to five lower-owned pieces. The
registered candidate pool already contains both chalk and leverage, but its
best winner overlap is only chance-level: median best overlap is 4/9 and no
winner has a candidate at 7/9 or better.

### The joint scoring law has a directional defect

Recent dependence remeasurement found excess generic teammate co-booms,
especially high-multiplicity outcomes, while QB-to-WR co-booms are
underproduced. Deep simulated optima also carry about three times the
never-realized score excess of actual winning rosters in the same worlds.
This argues for reallocating dependence toward plausible passing-game
co-booms, not for another generic marginal-tail inflation.

## Recommended execution sequence

### 1. Finish A3: bounded construction-shape relaxation

The frozen arm replaces exactly 8 of 40 boom solves per seed with open solves
that remove only the QB-stack and bring-back minima. Salary bounds and the
existing RB prohibitions remain. Its outcome-blind smoke was non-vacuous: all
40 open candidates survived and the unchanged selector admitted 11 into the
80-lineup treatment book.

Read the result only through the frozen branches:

- positive selected-book score with mechanism improvement: design a 2026
  prospective shadow;
- null with open candidates admitted: the law/objective, rather than legality,
  remains binding;
- null with no open candidates admitted: the selector rejects the shapes;
- negative: close this dose.

Do not rerun, change the dose, or combine this result with A7 after observing
it. Any combined construction-plus-objective arm must be newly frozen. A3 is
already the sole historical-outcome arm, so it must be harvested and the lease
released before A7 or another historical arm begins.

### 2. Deploy and collect B1: 20-book volume admission shadow

The historical 51-panel union reaches a mean ceiling of 198.10. At a fixed
registered selection budget, admitted volume improved selected-book mean from
178.38 at five books to 181.13 at 51 books. Most ceiling growth came from
independent volume rather than arm diversity.

The 20-book prospective shadow implementation, CLI, schedule, and frozen
six-slate grading law are complete. It should be deployed and graded exactly
as frozen. The historical curve is selection-biased evidence and cannot
license production by itself. Deployment and live-path rehearsal may proceed
in their allowed prospective/score-free lanes without opening another
historical-outcome arm.

### 3. Freeze and run A7: a tail-aligned exact-80 selector

The causal question should be: with identical candidates and simulated
worlds, can a different exact-80 utility convert more of the available tail
into one exceptional selected lineup?

A preferred design for review is:

1. Use only simulated pre-lock worlds during selection. Include lower rungs
   such as 170 and 180 so weak simulated slates still discriminate, retain the
   194/200 shoulder, and materially reward 210/220/230/240 with fixed weights.
2. Freeze the exact threshold list, weights, optional mean term, and existing
   tie law before outcome access. The implemented seam breaks remaining ties
   by mean and then candidate index; q99 is not currently part of it.
3. Separately preregister the **realized-result** shoulder guard or
   non-inferiority margin at 194/200. It is an evaluation gate after the book
   is frozen and can never enter selection.
4. Keep exact-80 legality, candidate identities, common worlds, candidate and
   solver budgets, and random seeds equal between arms.

The arm should report the complete 187/194/200/210/220/230/240 grid, paired
weekly-best delta, C-to-S conversion, selected source composition, book
overlap, selector stability under world resampling, and leave-one-slate/season
influence. A historical positive can license only an unseen 2026 shadow, not a
money-policy change.

Run A7 on the incumbent pool only. If it clears its frozen mechanism and
realized-result gates, that result may license a separately frozen test of the
same selector law on boom-deep supply. This preserves the all-boom null's
preregistered closure and avoids a post-result rescue or immediate 2x2
multiplicity problem.

### 4. Test the A2 dependence-factor split

The next simulation-law arm should reduce the generic team factor and add a
specific QB-to-pass-catcher factor. Its stages must remain distinct:

1. A simulated-only, score-free mechanism census verifies that the intended
   factor split is active, marginals remain controlled, budgets match, and the
   treatment is not vacuous.
2. A frozen one-shot outcome-bearing remeasurement asks whether registered
   co-boom cells move toward observed equivalence, protected cells avoid
   regression, and book-tail calibration plus optimum-realism avoid their
   preregistered failure conditions.
3. Only if that outcome-bearing gate licenses continuation may the fixed-budget
   C/S endpoint run, followed by a separate unseen 2026 shadow if favorable.

### 5. Make field and ownership capture a prerequisite for field-aware policy

The warehouse currently has **zero rows** in `contest_entries` and therefore
lacks a dependable corpus of full contest entries.
DraftKings standings are short-lived, so every relevant contest must be
downloaded promptly after settlement. Pre-lock projected ownership must also
be source-locked before the slate.

The minimum retained field data are:

- contest ID, field size, maximum entries per user, payout curve, and tickets
  awarded;
- every ranked roster and final score;
- actual ownership and duplicate counts;
- cash, top-1%, top-0.1%, final-ticket, and winning cutoffs; and
- the exact pre-lock projected-ownership snapshot used by the generator.

This enables expected duplicate count, score-to-rank calibration, effective
field size, and contest-specific expected utility. Post-settlement standings
and actual ownership cannot gate the current week's pre-lock production book;
they are calibration evidence and a prerequisite for **adopting a future
field-/duplication-/payout-aware policy**. Until then, a formula based only on
nominal field size is provisional.

### 6. Introduce contest-specific portfolio utility

The same 80 lineups should not automatically be reused or truncated across
materially different payout structures.

For a Millionaire Maker, the eventual target should be expected payout under a
calibrated field simulation, with special attention to first-place utility and
tie splitting. For a qualifier awarding `K` tickets, the target should be
approximately:

`P(rank <= K | pre-lock information, field model)`

with the contest's tie/tiebreaker rule represented explicitly. A one-ticket
qualifier is not equivalent to a generic 194-point threshold, and a ten-ticket
qualifier is not equivalent to a one-ticket qualifier.

The UI already accepts field size, requested entries, and contest entry cap.
After validation, it should additionally expose or ingest:

- contest objective: cash GPP, one-ticket qualifier, or multi-ticket
  qualifier;
- ticket count or full payout curve;
- exact contest max entries; and
- validated strategy identity and whether it is production, shadow, or
  research-only.

The frozen exact-N score-free result licensed separate 2026 pre-lock shadows
for N=1, N=3, and N=20. N=40 failed and is closed. None is a live money policy;
current small-N behavior mostly takes the first N entries from the large-book
ordering.

### 7. Add duplication awareness only after ownership calibration

The first usable form should be a bounded tie-break or carved sleeve, not a
wholesale expected-dollar optimizer. A lineup should not be rejected merely
for using popular players; winners often retain a chalk core. The target is
the joint combination's projected duplication, conditional on roster
structure and correlated ownership, not the product of nine independent
marginal ownership estimates.

Contingent on A3 and prospective validation, a future 80-lineup portfolio may
contain distinct game theses across conventional stacks, single stacks, naked
quarterbacks, and no-bring-back structures. Only then should it consider
explicit structure sleeves or quotas, control pairwise overlap and repeated
chalk cores, and retain the lower-owned pieces needed for first-place
uniqueness. The descriptive winner census alone does not license those rules.

### 8. Rehearse the complete live path and preserve late-swap optionality

The DraftKings slate/salary ingest has been repaired and verified, but the
full live projection-to-freeze-to-DK-CSV path still needs a production-scale
rehearsal before Week 1. Late-swap-aware construction and validation exist in
prospective form; they should remain separate from the pre-lock A7/A3/B1
experiments unless separately frozen.

## Contest-specific interpretation

### Exact-80 weekly master and large-max contests

The project researches one exact-80 weekly master book, but the number entered
into any particular contest is its actual permitted/requested N. The current
UI Millionaire Maker preset purchases four entries; low-max contests slice the
first N from the adopted ordering. A future allocation layer should build or
select contest-specific exact-N books and decide how the weekly 80-entry budget
is distributed across Millionaire Makers and qualifiers rather than implying
that all 80 necessarily enter one Milly.

- Optimize the maximum of the book, not average lineup score.
- Protect enough shoulder coverage to avoid turning every entry into an
  implausible lottery ticket, then reward 210-240 outcomes.
- Build multiple coherent paths to first rather than 80 minor variants of the
  same four-player game stack.
- Prefer chalk-core-plus-leverage combinations over indiscriminate ownership
  fading.
- Once calibrated, penalize likely duplicated complete lineups because cash
  ties split the covered prize positions.

### Roughly 40,000-entry sharp qualifier

- Ingest the actual number of tickets and its payout/tiebreaker terms.
- Optimize ticket probability rather than a generic winning-score estimate.
- Treat nominal field size and effective field strength as different inputs;
  thousands of correlated professional lineups are not thousands of
  independent draws.
- For a single ticket, uniqueness and the far upper tail matter heavily. For
  multiple tickets, excessive first-place-only variance can reduce ticket
  probability.
- Do not assume that a sharp field requires nine low-owned players. The
  observed winner template still favors a chalk core with a limited number of
  differentiated pieces.

## Paths that should remain closed or deprioritized

- A more exact greedy, beam, or generic selector algorithm under the same
  fixed-194 objective.
- More all-boom depth under the unchanged selector.
- Ordinary world ranking or chasing each world's mathematical optimum; no
  tracked winner is a world optimum and ATLAS world ranking was negative.
- Direct winner-nearness as an optimization target; best overlap is
  chance-level.
- Generic marginal-tail inflation without a named calibration defect.
- Broad arm diversity as a substitute for independent volume.
- Wholesale deletion of stack rules based on the winner census.
- Post-hoc dose sweeps or threshold-weight tuning on the same 54 slates.
- Production promotion from any favorable historical result without an
  outcome-unseen 2026 confirmation record.

## Evaluation and adoption law

Every proposed historical arm should be frozen before outcome access and use:

- an exact matched candidate/compute budget;
- common pre-lock inputs and common random seeds/base noise, with the frozen
  protocol defining the exact paired-artifact contract; treatments that change
  the world law cannot be required to produce identical worlds;
- exact legal and unique book size;
- deterministic identities and create-only receipts;
- the full registered tail grid rather than a selectively reported threshold;
- paired weekly-book maximum, bootstrap and sign-based uncertainty,
  McNemar-style threshold changes, season direction, and leave-one-slate-out
  influence;
- a mechanism gate specific to the arm; and
- winner overlap only as a diagnostic, never as a promotion endpoint.

Events at 230 and 240 are too sparse for one threshold crossing to prove an
arm. A frozen continuous or multi-threshold utility should be primary, with
registered threshold and shoulder guards. Historical results are decision
support; production adoption requires a prospective shadow on unseen 2026
slates.

## Current operational state relevant to this plan

- A3 stack relaxation is in flight. A metadata-only snapshot late on
  2026-08-19 showed 54/54 executions registered, 11 terminal successful, 43
  queued/running, zero terminal failures, and ten expected result objects.
  `scripts/chain_status.sh` is the current status surface. Do not relaunch the
  chain.
- The B1 20-book shadow is implemented and frozen; deployment and prospective
  collection remain.
- `SELECT_LADDER` exists behind a default-off research seam; its utility and
  one-shot execution have not yet been frozen for this recommendation.
- Residual-world column generation has a validated score-free core, but its
  real source-lock, 54-slate runner, reviewed launcher, and historical
  evaluation boundary are incomplete. It remains a later construction arm,
  not an immediate money-path feature.
- No recommendation in this document changes the current money policy.

## DraftKings mechanics that affect the plan

- NFL Classic uses a $50,000 salary cap and requires players from at least two
  teams.
- Every contest has its own entry cap. DraftKings' current fair-play policy
  generally limits Salary Cap tournaments below $5 to 20 entries per player,
  except mini-MAX. Therefore a generic `$3 Large GPP / 80 entries` UI preset is
  not universally valid and should be conditioned on the actual contest.
- Cash ties split the covered prize positions. Qualifier ties generally lead
  to a later tiebreaker contest, while specialty terms can differ.
- Eligible NFL Classic contests support late swap, which makes retained
  flexibility and conditional ownership strategically relevant.

Official references:

- <https://support.draftkings.com/dk/en-us/game-style-classic-overview?id=kb_article_view&sysparm_article=KB0010665>
- <https://help.draftkings.com/hc/en-us/articles/4405223983635-Fantasy-Sports-Fair-Play-Commitment-US>
- <https://support.draftkings.com/dk/en-us/what-happens-when-i-tie-with-others-in-a-fantasy-sports-contest?id=kb_article_view&sysparm_article=KB0010633>
- <https://support.draftkings.com/dk/en-us/contest-type-satellite-and-qualifiers-overview?id=kb_article_view&sysparm_article=KB0010643>

## Questions for the reviewing agent

1. Is a strict 194/200 no-decline guard the right protection for A7, or would
   a frozen non-inferiority margin better serve the stated one-monster-lineup
   goal?
2. If incumbent-pool A7 clears, what exact evidence should be required before
   freezing the separate boom-deep selector follow-up?
3. What exact ladder ordering or weights best approximate first-place utility
   without over-rewarding the simulator's least realistic extreme worlds?
4. Is the A3 k=8 carve a sufficient first representation of winner-like
   structures, or does a future prospective arm need explicit structural
   quotas?
5. What is the smallest defensible duplication model once pre-lock projected
   ownership and full standings are available?
6. For a 40,000-entry qualifier, what minimum payout/ticket and field data are
   needed before replacing the provisional field-size line with rank utility?
7. Should residual-world pricing remain behind A7/A3/A2, given that exact
   world-optimum pursuit has poor winner realism, or can it generate useful
   near-optimal diverse candidates under a tail ladder?
8. Are any proposed historical arms insufficiently separated, vulnerable to
   repeated-corpus tuning, or missing a fail-closed point-in-time gate?
9. Which Week 1 standings and ownership captures are load-bearing and must be
   rehearsed before the regular season?

## Primary project evidence

- `README.md`
- `CLAUDE.md`
- `HANDOFF.md`
- `reports/current-baseline.json`
- `reports/2026-08-19-external-reviewer-briefing-v3.md`
- `reports/2026-08-20-beat-the-winner-scorecard-and-week1-readiness.md`
- `reports/2026-08-19-winner-world-optima-and-field-null-results.md`
- `reports/2026-08-19-winner-anatomy-results.md`
- `reports/2026-08-19-winner-structure-census-results.md`
- `reports/2026-08-19-all-boom-selection-s-results.md`
- `reports/2026-08-19-selector-optimality-results.md`
- `reports/2026-08-15-exact-n-scorefree-result.md`
- `reports/2026-08-19-selection-volume-admission-plan.md`
- `reports/2026-08-19-cbwu-volume-prospective-shadow-spec.md`
- `reports/2026-08-19-dependence-repair-design.md`
- `reports/2026-08-19-stack-relaxation-carve-protocol.md`
