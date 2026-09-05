# Production-to-lab routing after SD-C: JPAR-1

**Date:** 2026-09-05  
**Status:** one development experiment nominated for lab design and mechanics implementation; no build or cloud launch is authorized by this document  
**Suggested identity:** experiment 100 / PREREG-071, banks 730–732, subject to the lab confirming that those identities remain unused

## Decision

SD-A, SD-B, and SD-C have answered the immediate routing question. Do not
launch 097's reranker, 099's candidate sieve, another greedy-search variant,
or a global marginal recalibration. Nominate one mechanism instead:

> **JPAR-1 integrates the already-frozen participation draw into the hsim
> opportunity allocator before team targets and carries are distributed.**

This is a joint participation/dependence correction. It is not another
post-score redistribution rule and it is not a pure marginal calibration.
The first test should determine whether a participation-conditioned hsim
component can recognize the beneficiary-linked ceiling already created by
the REDIST D800 pool. Only a
passing mechanics gate may earn a historical development execution; only a
favorable calibration-and-score read may earn a 2026 prospective shadow.

## Why this is the next experiment

The combined evidence rules out several tempting detours:

1. SD-B reproduced the incumbent K80 book in all 410 valid cells and placed
   the loose judge-objective search gap at 3.38% while realized
   oracle-to-book regret remained about 12.7 points. Search is not the binding
   defect; the judge is valuing the wrong candidates.
2. SD-C found 2,275 realized book beaters in 326 of 405 valid cells, but
   judge-mean top-80 recall was only 0.102 and the median empty-book rank was
   363 of 800. A better optimizer over the same belief is unlikely to recover
   them.
3. The largest winner-range calibration error is in beneficiary-only
   candidates: twCRPS 0.022 overall and 0.027 in REDIST, versus 0.008 for
   designated-player rosters. That localizes the next mechanism.
4. Player-level PIT is right-heavy, meaning player upper tails are too light,
   while SD-A found selected-book maxima too optimistic. Those opposite signs
   cannot be repaired honestly by multiplying every player's ceiling or by a
   common PIT remap. They indicate a joint-law/coupling problem.
5. The tested REDIST generator created additional extreme candidates, but its
   post-score transfer did not reliably improve the selected book. A
   participation-conditioned hsim component is the smallest new intervention
   that tests whether those candidates were generated but misunderstood.

This is an outcome-informed development nomination. Historical results can
screen it, but cannot confirm live value.

## Exact mechanism

### J0 — frozen current critic on REDIST

- Use the existing PG_REDIST D800 candidate population.
- Use the incumbent half of the decision bank with frozen P_MIX.
- Use the hsim half with the same frozen P_MIX implementation currently used
  by experiment 095: designated players are zeroed after player fantasy
  points have been simulated.
- Use the unchanged dual-law expected-maximum K80 selector.

### J1 — participation-conditioned coherent hsim critic

Everything is identical to J0 except the hsim half of the decision and
held-out banks:

1. Draw the same designated-player active/inactive Bernoulli masks from the
   same frozen P_MIX artifact.
2. Apply each sampled state **before** opportunity allocation.
3. Remove an inactive player from target and carry eligibility for that world.
4. Preserve sampled team target and carry totals and renormalize the existing
   Dirichlet-multinomial allocation over active eligible teammates.
5. Assign passing production in each world to the highest-projection active
   rostered QB, breaking projection ties by ascending canonical player ID. If
   no rostered QB is active, assign the team passing production to an explicit
   off-pool QB sink so no inactive rostered QB receives points; record every
   such team-world. If a positive target/carry total has no active eligible
   recipient, mark the entire cell unavailable and emit a receipt rather than
   silently dropping or inventing production.
6. Continue through the existing hsim stat and scoring path.

For any sampled-inactive position not represented in target/carry allocation,
including a DST if one ever enters the frozen designation universe, set that
player's final DK points to zero exactly as J0 does and record the event. The
mechanics invariant is position-independent: every sampled-inactive rostered
player has zero final DK points. PIT `active_mask` determines the base
eligible set; the sampled P_MIX mask may only remove from that set, never add
a player that the PIT mask excluded.

The existing hsim mean-calibration loop must remain identical between J0 and
J1. Freeze its calibrated weights and team-efficiency factors first; apply the
participation-conditioned eligibility only to the final decision-bank and
held-out-bank samples. Re-fitting the mean calibration after adding activity
would be a second treatment and is outside JPAR-1.

The incumbent half must remain byte-identical between J0 and J1. There is no
generation change, no fantasy-point transfer, no new projection, no new
selector, and no tunable dose.

Do **not** reuse experiment 095's `_redistribute` function. It moves
already-realized DK points through static shares. JPAR-1 changes eligibility
inside the team opportunity model and conserves football opportunity before
fantasy scoring.

## Frozen participation law

Reuse the exact existing P_MIX map and no other activity model:

- Questionable/Doubtful by practice bucket;
- Laplace smoothing alpha 2;
- target season S fitted only from seasons strictly before S; and
- 2021 no-op.

The primary historical panel is therefore 2022–2024. Report 2022 separately
because its map is trained only on 2021 and may reflect a regime transition.
No target-season outcomes may fit participation probabilities or any JPAR-1
parameter.

## Candidate population and comparator

The first test is intentionally aimed at **conversion**, not at proving the
REDIST generator again.

- Preferred implementation: recover each sealed 095 REDIST D800 population,
  require its exact ordered roster-signature match, and apply J0 and J1 to the
  identical rows. Declare every expected cell before regeneration. A
  non-reproducing cell is unavailable; never replace it, select another cell,
  or inspect its outcomes to decide inclusion.
- If the lab demonstrates that exact fixed-pool recovery is not reliable
  enough for a clean comparison, stop before efficacy and propose one fresh
  shared-pool implementation. In that version the REDIST population is
  generated once per cell and shared byte-for-byte by J0 and J1. It is not
  regenerated independently by arm.

Include the unchanged current production policy, PG_CTRL D800 with the
current P_MIX critic, as an operational **reference** whenever its already
computed book can be joined without extra generation. It is not a third
mechanism search. J1 must ultimately beat this reference before the combined
REDIST-plus-JPAR path can displace current production; a J1-versus-J0 gain
alone proves only that REDIST conversion improved.

The lab should return the exact fixed-pool feasibility census and a one-cell
runtime before production chooses between recovered and fresh shared pools.

The experiment runner must not open the outcome-bearing 095 envelopes. If the
required REDIST roster identities are not already available in a separate
pre-lock artifact, use the established PREREG-069 boundary pattern: one
outcome-exposed extraction role writes a create-once, outcome-stripped
`prelock_trace_redist_v1` containing only expected run/cell identity,
`cand_ix`, ordered canonical roster hash, generation tag/family, and frozen
J0 selected rank needed for reproduction. A separate root binds every child,
generation, byte count, and SHA-256. The JPAR runner may open only that trace
and point-in-time inputs; it must not import or name actual scores, settlement,
winner data, or the source envelopes. Outcome fields become accessible only
to the terminally released reader.

## Randomness boundary

Changing eligibility must not shift the incumbent hsim's sequential RNG and
thereby change unrelated games or later scoring components. The minimal
implementation is:

1. Run the existing target/carry allocation so the incumbent RNG consumes
   exactly the same draws as J0.
2. Keep those counts byte-identical for every unengaged team-world cell.
3. Build J1 as a copy of J0's completed path and intermediate game/team
   states. For an engaged team-world cell, discard its original target/carry
   counts before they enter J1 and recompute the complete allocation over
   active eligible players using an auxiliary RNG keyed by
   `(experiment, source_bank, season, week, game, team, world,
   target_or_carry)`.
4. Recompute every downstream offensive result affected within that engaged
   team-world—receptions, receiving/rushing yards, touchdown allocation, and
   active-QB scoring—using separate keyed auxiliary component streams. Copy
   J0 values for every unengaged team-world and for components that are not
   downstream of the intervention. Do not feed changed arrays back through a
   shared sequential RNG, because severity and bin-dependent draws can shift
   unrelated results even when the nominal draw count looks unchanged.

The final engaged allocation must therefore be exactly the allocation that
enters J1 scoring; the discarded original counts exist only to preserve the
control trajectory. Activity masks retain their already-frozen Bernoulli
seeds. In a fixture with no inactive draw, J1 must reproduce J0's full hsim
matrix exactly. In a fixture where one team-world cell is engaged, every
unengaged player-world must remain byte-identical to J0. The lab may propose a
mathematically equivalent common-random-number construction, but it must
prove these invariants on a real artifact.

## Bank and support mapping

For the preferred recovered-pool path, freeze this mapping:

| new execution identity | sealed source pool | source bank used by every J0 seed |
| --- | --- | --- |
| 100 / bank 730 | `095b690r1-20260904T164737Z` | 690 |
| 100 / bank 731 | `095b691r1-20260904T165019Z` | 691 |
| 100 / bank 732 | `095b692r1-20260904T180305Z` | 692 |

The 730–732 values are new execution/storage identities; they do not replace
the sealed 690–692 simulation seeds. J0 reproduction means exact ordered J0
K80 roster hashes, decision/held-out matrix identities, and receipts from the
corresponding 095 source run. J1 shares all J0 base seeds and adds only its
named auxiliary streams.

If fixed-pool recovery fails the census and production separately authorizes
the fresh shared-pool path, 730–732 become both generation and simulation
banks. In that case J0 is a same-cohort control and is **not** claimed to
reproduce 095. PREREG-071 must bind exactly one of these paths before its
mechanics gate; it may never switch paths after a score read.

Before mechanics, run an outcome-disabled census over all expected 2022–2024
cells: 54 declared slates × three source banks = 162 cells. Report exact pool
reproduction, treatment engagement, active target/carry support, active-QB
support, and all unavailable reasons. The recovered-pool path may proceed
only with at least 90% of all cells and at least 85% within every season
available under rules frozen before outcomes; every unavailable cell remains
in the authority and can never be replaced. J0 and J1 must have the identical
valid-cell set. The full census and its hash are frozen before mechanics
release.

## Outcome-disabled mechanics gate

Run one real-artifact engaged cell, preferably 2022 Week 8, before any
efficacy build or launch. The gate must prove:

1. exact source, candidate, roster-order, P_MIX, selector, K80, and matrix
   identities;
2. no outcome, settlement, winner, payout, final-rank, or actual-score field
   is opened by the runner, and the runner physically opens only the stripped
   pre-lock trace plus allowlisted point-in-time inputs;
3. J0 reproduces the frozen control and the incumbent half is byte-identical
   across J0/J1;
4. J0 and J1 share the exact activity masks, incumbent RNG trajectory, and
   all non-treatment random components;
5. every sampled-inactive player at every position has zero final DK points;
6. team target and carry totals are conserved exactly;
7. zero-target/carry-eligibility cells fail closed, while zero-active-QB
   team-worlds use only the recorded off-pool sink;
8. finite matrices, deterministic replay, real treatment engagement, and
   nonzero hsim/K80 turnover, with per-cell receipts for engaged team-worlds,
   conserved mass, sink use, and turnover; and
9. decision and held-out bank identities are disjoint and neither held-out
   bank enters selection.

The mechanics runner must also deny importing the existing 095
`winner_utility` self-test or opening `milly_winners.json`; those belong only
to the outcome-open reader.

A fixture-only smoke is insufficient. Any failed item stops the efficacy
launch without repair-by-fallback.

## Development efficacy read

### Co-primary requirements

Both must pass; neither may be traded off against the other. Treat these as
co-primary intersection-union requirements, so each uses its own paired 95%
season-clustered interval:

1. **Score:** paired realized K80 winner-CDF utility, J1 minus J0, using the
   current frozen winner-utility implementation; interval lower bound must be
   greater than zero.
2. **Calibration:** slate-balanced held-out 200–260 twCRPS for
   beneficiary-only candidates, J1 minus J0; interval upper bound must be
   less than zero.

Use the slate as the inferential unit and average simulation banks within
slate. On each co-primary, no bank may have its own 95% season-clustered
interval entirely in the adverse direction and no more than one LOSO season
may be adverse. These are vetoes, not substitute passes. The valid-cell set is
the frozen census intersection; unavailable cells remain visible and no
complete-case rule may be changed after mechanics. Realized inactive-player
contamination may not worsen. PREREG-071 must bind the exact source SHA of the
winner-proxy and bootstrap implementations before mechanics release.

### Required co-reports

- raw weekly maximum and winner-CDF utility at K3/K10/K20/K57/K80;
- weeks and candidate instances at 194/200/210/220/230;
- per-bank, per-season, LOSO, W/L/T, and paired uncertainty;
- selected-book maximum, full-pool oracle, and oracle-to-book regret;
- book-max PIT and 194–230 exceedance calibration;
- player PIT and zero-mass calibration for designated, beneficiary-only,
  active, inactive, and control groups, with QB/RB/WR/TE splits;
- beater recall at top 20/40/57/80/160, empty-book ranks, and rank-biased
  overlap;
- J0/J1 K80 turnover and exact rescued/displaced roster hashes; and
- PG_CTRL current-policy reference deltas when that reference is available
  without changing the registered population.

### Disposition

- **Calibration and score both improve, safety holds, and J1 also improves on
  the current-policy reference:** nominate one separately named 2026
  prospective shadow or one fresh-bank end-to-end confirmation. Do not alter
  paid Week-1 policy from this historical development read.
- **Calibration improves but score does not:** retain JPAR-1 as a more honest
  shadow critic; do not adopt it for lineup selection.
- **Score improves but calibration does not:** reject the claimed mechanism.
  Do not tune it on the opened outcomes.
- **Both fail:** close only this binary designated-player, pre-allocation hsim
  treatment. Do not claim that richer role states, all-player participation,
  or market-conditioned dependence have been tested.

## Queue and ownership

This route supersedes no live capture work and authorizes no cloud mutation.
It does establish the next score-bearing scientific path after SD-C:

1. Lab confirms unused identity/banks, fixed-pool feasibility, exact code
   touch points, keyed-RNG plan, and one-cell compute estimate.
2. Lab writes PREREG-071, runner, outcome-disabled mechanics gate, reader,
   and focused tests.
3. Production independently reviews the mechanics boundary and immutable
   launch contract.
4. Only after a real-artifact gate passes may production build and launch the
   fresh cohort.
5. The lab performs the first outcome read after production's terminal
   release; production then cross-verifies it.

Keep 097, 099/S0, and 091 held. The prop-coverage P0 census may continue as
score-free background work, but experiment 098 may not launch until its exact
800-row donor contract is resolved by a separate amendment. T1
market-dependence feasibility may proceed in parallel, but it must not be
combined with JPAR-1's first test.

## Lab response requested

Please respond with only:

1. confirmation that experiment 100 / PREREG-071 and banks 730–732 are unused;
2. whether exact sealed REDIST D800 membership can be recovered reliably, with
   the expected/valid/unavailable cell census;
3. the proposed keyed-RNG substream scheme and explicit empty-eligibility
   behavior;
4. one real-cell runtime/memory estimate and total cloud estimate;
5. the exact outcome-disabled mechanics artifact and pass/fail contract; and
6. any code-level reason the treatment cannot remain confined to the hsim
   half while leaving the incumbent half byte-identical.

Do not build or launch before production reviews that response.
