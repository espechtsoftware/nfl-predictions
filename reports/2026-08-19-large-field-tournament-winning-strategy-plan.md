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

The recommended next selection experiment, after the terminal A3 arm is
strictly harvested, read through its preregistered disposition, and given a
durable logical-lane release, is a frozen, exact-80, multi-threshold
`SELECT_LADDER` arm that protects the useful 194/200 shoulder while rewarding
outcomes only through 210. Scores at 220/230/240 remain mandatory report-only
diagnostics because the current simulator is least trustworthy and the
realized corpus is sparsest there. It should hold candidates, worlds, legal
constraints, compute, and book size fixed, and it should be read as a paired
selection-mechanism test on the incumbent candidate pool under the **Phase-S
finite-K plus SIS-ASOE research law**. That is not the live
production-multinomial simulation law. A positive A7 result can therefore
license only a separately frozen, outcome-blind production-law score-free
selector-transfer test—not a 2026 shadow or production change. The boom-deep
pool remains closed by its own frozen null disposition; A7 does not reopen it.

In parallel, the project should strictly harvest and read the completed
stack-relaxation carve, deploy the already-built 20-book prospective volume
shadow, then test
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

### Registered 54-slate Phase-S CBWU historical baseline

Across the valid 54-slate 2023-2025 Sunday-main corpus, the registered CBWU
selector control under the Phase-S finite-K plus SIS-ASOE research law has a
mean weekly best score of **176.06**. This is the historical source of the
adopted money-book aggregate, but it is not a production-multinomial replay.
Its threshold counts are:

| Score | Slates reaching score |
|---:|---:|
| 187 | 17 / 54 |
| 194 | 8 / 54 |
| 200 | 7 / 54 |
| 210 | 6 / 54 |
| 220 | 3 / 54 |
| 230 | 1 / 54 |
| 240 | 0 / 54 |

The exact W1-W18 weekly-baseline vector, which A7 must reproduce before any
treatment summary, is:

- 2023: `173.64, 187.28, 235.60, 167.72, 173.98, 171.34, 168.16,
  180.28, 224.20, 194.72, 166.98, 162.62, 171.08, 193.28, 188.84,
  169.02, 173.06, 171.20`
- 2024: `170.48, 160.72, 225.28, 153.90, 185.22, 177.90, 144.20,
  166.80, 158.52, 149.72, 192.48, 179.20, 146.94, 218.48, 193.72,
  189.46, 207.26, 188.54`
- 2025: `136.18, 217.20, 168.14, 156.46, 163.86, 170.74, 158.54,
  156.98, 189.10, 167.50, 160.42, 217.34, 151.76, 148.64, 188.80,
  163.62, 161.34, 148.96`

Aggregate mean/grid agreement cannot rescue a weekly-vector mismatch.

The direct winner comparison is sobering but should remain a ceiling
diagnostic rather than the optimization target: the money book beat the
tracked Millionaire Maker winner on 0/50 paired slates, had a median shortfall
of 53.4 points, and recorded a best-ever weekly maximum of 223.9. The tracked
winners had a median score of 233.2 and a 10th percentile of 205.4.

### Simulated candidate supply improved; selected-book conversion did not

The all-boom candidate experiment raised mean pool ceiling C from **187.58 to
196.64 (+9.06)**, with 43 better slates, one worse, and ten tied. The unchanged
selector converted that into only **+1.34** selected-book points
(178.57 to 179.91; p=0.49; 19 better, 18 worse, 16 tied). The treatment C-S gap
widened to roughly 16.7 points. This proves that the unchanged selector did
not convert the extra simulated ceiling. It does **not** prove that all of that
ceiling was real: admission, objective alignment, and simulator artifact
remain competing explanations.

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

### 1. Strictly harvest and read A3: bounded construction-shape relaxation

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
into one exceptional selected lineup under the Phase-S finite-K plus SIS-ASOE
research law? The result is law-specific and cannot be described as a test of
the production-multinomial simulator.

A7's frozen scientific design is:

1. Use only simulated pre-lock worlds during selection. Freeze the clipped
   score ladder `170:10,180:10,187:7,194:7,200:6,210:10`: its cumulative
   utility is 10/20/27/34/40/50, approximating score above 160 and then
   deliberately capping at 210. There is no mean term and no weight, rung, or
   threshold sweep. Scores at 220/230/240 are reported but never rewarded.
2. Retain each implemented arm's tie law: control uses marginal uncovered
   worlds, individual p194, then simulated mean and must exactly reproduce its
   registered order; treatment uses marginal ladder gain, simulated mean, then
   lower candidate index. Pass an explicit environment to both arms so neither
   process state nor a host-level research lever can change selection.
3. Separately preregister the **realized-result** non-inferiority margin at
   194/200: treatment may lose at most one net slate at each threshold over
   the same 54-slate population. This is an evaluation gate after both books
   are frozen and can never enter selection.
4. Keep exact-80 legality, candidate identities, common worlds, candidate and
   solver budgets, and random seeds equal between arms. The treatment changes
   only the selector utility.
5. Add a score-free realism falsifier. A player is extreme only when its draw
   is **strictly greater than** its own within-block q99 computed with
   `method="higher"`; equality does not count, and constant/zero-variance
   series are never extreme. Attribute each positive marginal ladder-gain
   event by simultaneous-extreme count and define R3 as the share of marginal
   utility from events with at least three extreme players.
6. Freeze support before interpreting R3: each arm must contain at least 100
   positive-gain R3 events across the 54 slates and strictly more than zero in
   every one of the five aggregated world blocks. Unsupported R3 is `invalid`
   before outcomes. Once supported, a treatment-minus-control R3 difference
   strictly above `+0.01` is the outcome-blind
   `tail-artifact-risk-phase-s` closure; `<= +0.01` may proceed. Report R2, R4,
   and q99.5 analogues as non-gating score-free diagnostics. Decide the exact
   `1/100` boundary by integer cross-multiplication of retained utility
   numerators/denominators, not binary floating-point rounding.

S80, the maximum of the exact-80 book, is the sole realized gate. Historical
positive requires the intersection of a positive mean paired delta with its
deterministic two-sided paired sign-flip `p <= .05`, a favorable signed-rank
direction with its deterministic paired sign-flip `p <= .05`, and the two
`-1`-slate non-inferiority guards at 194 and 200. The arm reports the complete
187/194/200/210/220/230/240 grid, all aligned leave-one-slate/season influence,
and the frozen 10,000-draw season-stratified bootstrap (`default_rng(20260820)`,
NumPy linear 0.025/0.975 quantiles). It does not promise selector-resampling,
winner-overlap, or never-realized-player diagnostics.

The frozen sign-flip implementation enumerates exactly only with at most 20
nonzero deltas; otherwise it uses exactly 200,000 fixed-seed Monte Carlo sign
draws from NumPy `default_rng(20260818)` with the standing add-one correction.
At A7's normal 54-slate support, those p-values are therefore deterministic
Monte Carlo estimates, not exact permutation p-values.

Its causal control is the canonical 54-slate Phase-S CBWU historical baseline
and must reproduce the exact weekly vector above, mean
`176.06296296296293`, and the 17/8/7/6/3/1/0 grid before treatment scores can
be interpreted. The separate 53-slate ATLAS production-multinomial comparator
(mean 178.57; 16/9/7/2/1/0/0) remains contextual for the arms built on that
reconstruction, not A7's control. Denominators must never be mixed.

After the weekly baseline passes, A7 reports C-to-S conversion exactly: C is
the maximum realized score of the shared admitted candidate pool, S is the
arm's selected exact-80 maximum, and C-S is the conversion gap. Persist all 54
C, S, and C-S values and their means; C must be identical across arms. The
immutable result must also retain every finite candidate actual score aligned
to the shared canonical candidate order, derived from a retained complete
native actual-query row key-and-score vector and its full content receipt. That
lets the finisher reconstruct both the native query and every admitted/selected
score without querying outcomes again. C-to-S remains diagnostic rather than
an adoption gate: a high common C is not evidence that treatment converted it.

Persist the ordered 80 identities and per-lineup scores. Report maxima of the
first 4, first 14, and all 80 for both arms. The N=4 and N=14 prefixes are
registered non-gating diagnostics for today's slicing behavior; they cannot
rescue or veto the exact-80 primary, and they license no cardinality-specific
money policy. S80 remains the sole disposition gate.

Run A7 on the incumbent pool only. A historical positive licenses only one
separately frozen, outcome-blind production-multinomial-law score-free
selector-transfer test. It does not license shadow scoring, production, or a
boom-deep follow-up. A null or rejection closes only this exact Phase-S dose;
it does not establish a production-law selector null.

The protocol bytes must remain unchanged through smoke, full score-free
support census, and outcome execution. Passing preflights do not edit
or promote the protocol. Instead, an external create-only operator-approval
and freeze manifest must bind the exact unchanged protocol SHA, code/archive
and image identities, exact source hashes/receipts, and smoke/support receipt
identities. It must explicitly approve the frozen utility, support/realism
law, S80 co-primary intersection, and 194/200 non-inferiority margins. The full
runner must fail closed without that exact manifest. Any repair requires a new
protocol ID and new outcome-blind preflights.

The compact pre-freeze support receipt discloses only event support and its
pass/fail state; it hash-binds, but does not expose, selector effects, utility,
R3 deltas, identities, or traces. The manifest freezes those hidden inputs and
the decision law. The full runner evaluates nonvacuity, utility, block, and
exact R3 gates only after loading the manifest and still before constructing or
executing the historical outcome query.

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
  implausible lottery ticket. In the Phase-S-law A7 test, reward through 210
  and report 220-240 without optimizing them.
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
  outcome-unseen 2026 confirmation record. A7 is narrower still: even a
  positive licenses only an outcome-blind production-law score-free transfer,
  not the confirmation shadow itself.

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
- a mechanism gate specific to the arm.

Events at 230 and 240 are too sparse for one threshold crossing to prove an
arm. A frozen continuous or multi-threshold utility should be primary, with
registered threshold and shoulder guards. Historical results are decision
support; production adoption requires a prospective shadow on unseen 2026
slates. For A7, a positive historical result first licenses only the separate
production-law score-free transfer; it does not license that shadow.

## Current operational state relevant to this plan

- A3 stack relaxation has reached strict terminal success for all 54 registered
  executions and the exact 54-object inventory, but remains deliberately
  unharvested and unread. Its preregistered read, durable finish receipts, and
  separate logical historical-outcome-lane release must complete before A7
  can reuse the lane. Do not relaunch the chain or inspect partial science.
- A7 must not update the reused research job even for an outcome-blind smoke
  until that A3 release explicitly transfers the job to A7 and A7 creates a
  generation-matched, create-only remote job claim. Smoke and support then run
  sequentially with strict terminal receipts; no broad deployment script or
  B1 job/scheduler is in scope.
- The B1 20-book shadow is implemented and frozen; deployment and prospective
  collection remain.
- `SELECT_LADDER` exists behind a default-off research seam. A7 now has fixed
  scientific wording and a locally validated fail-closed transport, but it is
  not externally frozen: the bound smoke, compact support receipt, and operator
  manifest remain required. The approved image build uses the exact public Git
  origin at the frozen commit, binds the committed Cloud Build recipe, and
  requires an independent finisher replay inside the immutable image before
  any result upload; the later local harvest must match that retained replay
  exactly. A caller-supplied commit label, local working-tree build, or
  local-only replay is insufficient. Realized lease release is additionally
  protected by a create-only remote intent so a crash cannot license a retry.
- A4's current ownership-template entry gate failed: `own_est` precision and
  rank association are too weak to support a roster constraint. That exact arm
  is closed at current input quality; revisit field-aware selection only after
  a materially better PIT ownership model is calibrated from prospective
  standings/ownership capture.
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

## Resolved reviewer questions and remaining review prompts

1. **Resolved before outcomes:** A7 uses the explicitly approved `-1`-slate
   non-inferiority margin at both 194 and 200, not strict no-decline.
2. Does the separately frozen production-law score-free transfer preserve the
   A7 utility mechanism and supported realism law without relying on Phase-S
   transport?
3. Are there any remaining pre-outcome implementation defects in the fixed
   freeze-candidate ladder `170:10,180:10,187:7,194:7,200:6,210:10`? Its
   utility bytes are not externally frozen until the real outcome-blind smoke,
   all-54 support census, and operator freeze manifest pass; its weights are
   already closed to outcome-informed revision on this corpus.
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

---

## Review notes (orchestrating agent, 2026-08-20)

Every figure I can check against committed receipts is accurate: the
baseline table and 176.06; the A5 gap (0.134%, worst 0.70%, 255/255
exact); 43/51 winners failing the construction contract; the winner
structure percentages (22/41/61/69); ownership 104.5% median with four
sub-10% pieces; chance-level overlap at median 4/9 with none at 7/9;
union ceiling 198.10; B2-prime 178.38 → 181.13; boom C +9.06 → S +1.34.
The "closed or deprioritized" list is well-supported and I endorse it as
written. Four disagreements, ranked by how much they would change the
plan, follow. A fifth governance correction was added while disposing them.

### 1. The 80-lineup book is not the object we actually enter (first-order)

The plan treats contest-specific allocation as a later layer ("a future
allocation layer... rather than implying that all 80 necessarily enter
one Milly"). I think this understates it. The standing entry memory in
`CLAUDE.md` is **3 qualifiers x 14 + 4 Milly**. If the Millionaire gets
four entries, then every S number in this document — 176.06, the +1.34
conversion, all threshold grids — is the maximum of **eighty** lineups,
while the realized Milly outcome is the maximum of **four**. Those are
very different distributions, and the gap is large precisely because the
book is built for coverage breadth.

Consequences the plan should absorb rather than defer:

- The headline baseline overstates realized Millionaire performance. A
  max-of-4 baseline should be computed from the same receipts (take the
  first 4 of the selection ordering per slate) and reported alongside
  176.06. This is cheap, needs no new run, and I would do it before
  A7 is frozen.
- Arm ranking may not be invariant to N. A utility change that improves
  the max of 80 can fail at the max of 4 (breadth-vs-concentration
  trades reverse), so A7's frozen report should include the max-of-4 and
  max-of-14 cuts as registered secondaries. That costs nothing at
  freeze time and is impossible to add credibly afterward.
- This also reframes the exact-N work from "nice to have" to the
  primary deployment question.

#### Project response

**Partly accepted, with two overrides.** The estimand warning is correct:
max-of-80 is the weekly master-book mechanism, not automatically the maximum
actually entered into one contest. A7 will therefore persist the ordered book
and register first-4 and first-14 maxima as non-gating secondaries. They are
prefix diagnostics for today's slicing behavior, not purpose-built exact-N
books and not a license to deploy at N=4 or N=14. The frozen exact-N work
remains the only current cardinality-specific evidence (N=1/3/20 shadow
licenses; N=40 closed).

I override the recommendation to inspect max-of-4 before freezing A7. The
committed summary receipts do not retain enough ordered lineup/score evidence
to reconstruct it independently, and a separate outcome look before choosing
weights would create an avoidable tuning channel. A7 registers N4/N14 now and
computes them inside the same one-shot result. S80 is the sole gating endpoint;
N4/N14 are non-gating and cannot rescue or veto it. The external freeze
manifest must explicitly record the operator's approval of that estimand law
before outcomes. The older `3 x 14 + 4` memory may not describe the stated
80-entry weekly plan, but later contest allocation cannot alter this A7 gate.

### 2. A7 before A2 weights the least trustworthy region of the law

The plan sequences the ladder (step 3) ahead of the dependence repair
(step 4), and its ladder materially rewards 210/220/230/240 **simulated**
outcomes. But this document's own evidence says the extreme simulated
region is where the law is least believable: deep-world optima carry
about three times the never-realized excess of real winning rosters, and
generic teammate co-booms are over-produced. Weighting those rungs
heavily means weighting the law's known error heavily, and the selector
will faithfully chase it.

I am not arguing to block A7 — it is cheap and the incumbent pool is
what exists. I am arguing that either (a) A2's factor split should
precede it, or (b) the frozen ladder should stop at a rung with
calibration support (210 is defensible; 230/240 are ~1 and ~0 events in
54 slates) and treat higher rungs as reported-not-rewarded. Freezing
weights on 230/240 is fitting to a region with almost no support in
either the corpus or the law.

#### Project response

**Accepted via option (b); sequencing retained.** A7 remains ahead of A2
because it is a small, clean selector-only causal test under the existing
Phase-S finite-K plus SIS-ASOE **research** law, while A2 is a larger staged law
repair whose mechanism may fail before book scoring. Phase S is not the
production-multinomial law. The A7 utility is clipped at 210 and has no mean
term: `170:10,180:10,187:7,194:7,200:6,210:10`. Scores at 220/230/240 remain
mandatory report-only diagnostics and cannot affect membership. A7 does not
transport to either A2 or production worlds. Even a positive licenses only a
separately frozen, outcome-blind production-law score-free transfer test.

### 3. "Stranded supply" is one of three readings, and not the leading one

The plan reads the boom null as tail supply "stranded by admission or
objective alignment." There is a third possibility it does not weigh:
the extra ceiling may be substantially **simulator artifact**. The
winner-overlap instrument on that arm showed the boom-deep book sitting
*closer to chance* than the incumbent (+0.11 vs +0.24), i.e. the added
supply aimed worse, not merely unconverted. Combined with the
mirage-optima finding, the most parsimonious reading is that a
meaningful share of the +9.06 was never real points.

This matters because it changes what A7 is expected to do. If part of
the ceiling is fake, a utility that harvests more of it can be actively
harmful, and A7's mechanism gate should include a realism check (do the
newly selected lineups rely on never-realized player draws?) rather than
only score and composition.

#### Project response

**Accepted, with a PIT correction.** The main text now says "unconverted
simulated supply" and explicitly retains simulator artifact as a competing
explanation. A7 adds a score-free simultaneous-extremes falsifier on the same
pre-lock worlds: for each ordered lineup addition, it attributes marginal
ladder utility by the number of roster players **strictly greater than** their
own within-block simulated q99; equality does not count, and constant or
zero-variance player series are never extreme. The falsifier is supported only
if each arm has at least 100 positive-gain R3 events in aggregate and more than
zero in every aggregated world block. Unsupported is `invalid` before outcomes.
Once supported, treatment R3 more than one percentage point above control is
the outcome-blind `tail-artifact-risk-phase-s` closure; `<= +0.01` may proceed.
R2/R4 and q99.5 cells are non-gating score-free diagnostics.

I do not use a full-history "never realized" ceiling as the selection input or
the score-free gate: that would be outcome-facing and can punish legitimate
new breakouts. A7 makes no mandatory selector-resampling, winner-overlap, or
never-realized-player diagnostic promise.

### 4. Two baselines are used without labeling (minor but fixable)

The baseline table is the registered **money book** (54 slates,
17/8/7/6/3/1/0, mean 176.06); the conversion figures are the **arm
comparator** reconstruction (53 slates, mean 178.57). Both are correct
and they are different books. A reader can easily conflate "8/54 at 194"
with the comparator's 9/53. Recommend labeling each occurrence, since
downstream arms are graded against the comparator, not the money book.

#### Project response

**Accepted and made arm- and law-specific.** A7's control is the 54-slate
Phase-S finite-K plus SIS-ASOE CBWU historical baseline that supplied the
registered money-book aggregate; it is not a production-multinomial replay.
A7 must reproduce the exact 54-value weekly vector printed above, its mean
`176.06296296296293`, and 17/8/7/6/3/1/0 before treatment is interpretable.
The 53-slate ATLAS production-multinomial comparator—178.57 and
16/9/7/2/1/0/0—remains contextual only for arms built on that reconstruction.
No law or denominator is mixed. A7 also freezes weekly C-to-S conversion: C is
the shared admitted-pool realized maximum, S the selected-book maximum, and
C-S the gap; C must match across arms.

### On the document's own question 1

With 8 of 54 slates at 194 and 6 at 210, a strict no-decline guard is
close to untestable — one slate flipping is noise, not evidence, and a
strict guard will mostly fail arms for chance. A preregistered
non-inferiority margin is the more defensible instrument at this event
density, and it should be stated in slates-at-threshold terms with an
explicit margin rather than as "no decline."

#### Project response

**Accepted.** A7 freezes a one-slate non-inferiority margin at both 194 and
200 over the same 54 slates: treatment minus control must be at least `-1` at
each. This is a realized evaluation guard, never a selection input. Historical
success additionally requires positive paired mean direction and both standing
paired sign-flip tests at `p <= .05`; even a full pass can license only a
separately frozen, outcome-blind production-law score-free transfer test. It
does not license a shadow or production.

### 5. Preflight-to-freeze sequencing must not be circular

A protocol cannot be described as editable `PRE-FREEZE`, run a smoke/support
census, and then change its own status or scientific bytes before the outcome
run. That would leave ambiguity about whether the preflights tested the
outcome-bearing protocol and whether the operator approved the actual utility,
support, endpoint, and non-inferiority laws.

#### Project response

**Accepted.** A7 now uses unchanged freeze-candidate bytes plus an external,
create-only operator-approval/freeze manifest. The real-artifact smoke and the
54-slate score-free support census bind the exact candidate protocol, code,
image, source, hidden score-free row hashes, and receipt hashes without
disclosing arm effects. Neither changes this document. The external manifest
then binds those exact receipts and identities and records
explicit operator approval of (1) the exact ladder with no mean term, (2) the
R3 support floor and `+0.01` margin, (3) the S80 co-primary intersection, and
(4) the `-1`-slate guards at both 194 and 200. The full runner must reject a
missing or mismatched manifest, then evaluate the hidden mechanism and R3
effect gates before any outcome query. Any protocol, selector, science,
runner, or direct scientific-dependency repair gets a new protocol ID and
repeats both outcome-blind preflights. Only a transport-proof repair to the
launcher/watcher/finisher may use the project's explicit exact-current-hash
override seam, with independent review and no scientific/input/outcome change.
