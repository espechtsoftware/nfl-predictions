# Production adoption review: winner-range and contest-utility objective

**Date:** 2026-09-01

**Status:** adopted direction; production implementation gaps remain

**Audience:** operator, production team, lab team, and external reviewers

**Authoritative directive:**
`../nfl2/handoffs/OBJECTIVE-CHANGE-NOTICE-2026-09-01.md`

## Executive decision

The program is no longer optimizing the number of weekly books whose maximum
score exceeds 194. That threshold remains useful as a backward-compatible
distribution landmark, but it is retired from new generation targets,
admission rules, selection objectives, paid-policy decisions, and adoption
gates.

The new program objective is to build portfolios capable of winning
top-heavy contests and, ultimately, to maximize contest-specific settled
portfolio value. The objective ladder is:

1. `GLOBAL_WEMAX_PROXY`: an inexpensive absolute-score tail proxy based on
   the pooled 2023-2025 winner-score distribution.
2. `SLATE_WEMAX_PROXY`: a strongly shrunk, walk-forward, slate-conditioned
   winner-score proxy.
3. `FIELD_WIN`: first-place and tie probability against a modeled opponent
   field scored in the same football worlds as our candidates.
4. Expected settled portfolio payout net of entry fees, incorporating the
   contest payout ladder, ties, duplication, self-competition, field size,
   entry limits, contest allocation, and late swap.

This is an objective and architecture change, not a relabeling of the old
194 metric. Existing frozen work remains valid for its frozen estimand, but
new production decisions must use the new hierarchy.

## Why the objective changed

Across 31 panel slates matched to recorded Millionaire Maker winners, no
evaluated lab book beat the recorded winner in any of three banks: 0 of 93
book-instances. A zero-win count is not surprising for an 80-entry book in a
field containing roughly 100,000 to 1,000,000 entries and should not be used
alone to condemn a strategy.

The decision-bearing evidence is the continuous shortfall:

- median recorded winning score was approximately 234;
- the mean book-to-winner gap was approximately -55 points;
- almost all recorded winners cleared 194; and
- the small historical movement around 194 measured progress toward a
  qualifier-like threshold, not progress toward first place.

The strongest available D400 result remains useful: it expands the selected
210-230 tail and improves the old exact-K80 endpoint. It does not establish
that the system is close to the Millionaire-winning range. It should be
treated as the strongest compact supply/control candidate currently tested,
not as a demonstrated winning policy.

## Critical estimand correction

`GLOBAL_WEMAX_PROXY` must never be labeled as the probability of beating the
same-slate winner.

It applies a smoothed pooled historical winner-score CDF to our simulated book
maximum. That estimates performance against an independent draw from a pooled
absolute-score distribution. Our book and the actual same-slate field maximum
are not independent: both respond to the same games, scoring environment,
injuries, player outcomes, and slate strength. On the matched panel, the
bank-averaged D400 maximum and winner score were strongly correlated
(approximately Pearson 0.83).

The proxy is still valuable because it places more weight in the approximate
220-260 score range and can cheaply screen selectors. It is not decision-grade
field-win probability. Every consumer and receipt must include:

- estimand ID;
- utility version;
- winner-registry era (`2023-2025` for the current 48-score artifact);
- winner-registry content identity and record count;
- smoothing bandwidth and its version; and
- an explicit `proxy_not_same_slate_win_probability` disclosure.

An older supporting objective memo and the current lab ledger still contain
the superseded probability wording and/or a 2023-24 era label. The objective
notice and independent review are authoritative: the utility era is
2023-2025 and the result is an absolute-score proxy.

## Adopted rule interpretation

### Estimand labels

No proxy receives a probability-of-winning label. Winner, field, and payout
artifacts are immutable, versioned inputs whose identities travel with every
result.

### Tail-class adoption gates

The old every-bank-positive and LOSO hard vetoes were designed for mean or
194-threshold effects and can systematically reject concentrated tail
interventions. A fresh tail-class experiment may use the new carveout only if
the classification and rule are preregistered before outcome contact:

- its primary endpoint is the named proxy or field endpoint;
- the pooled uncertainty interval must exclude zero;
- no bank may be significantly negative; and
- LOSO and individual bank signs remain reported, but are not automatic
  vetoes.

This is not a blanket weakening of validation. Experiments not explicitly
preregistered as tail-class remain under their frozen laws.

### Historical and prospective authority

Historical panels are screening instruments. They contain too few true
winner-range events to serve as final adoption authorities. Prospective 2026
counterfactual settlement—using books frozen before lock—is the ultimate
authority. Historical binary wins are always reported but do not gate.

### Model governance

Winner, field, duplication, and utility models are versioned artifacts.
Outcomes may update walk-forward models only between weeks. No frozen
probability is retrofitted after observing the outcome, and no proxy bandwidth
or field parameter is tuned on the slate being graded.

### Integrity overrides

The following invalidate efficacy regardless of score:

- a short book;
- duplicate entries where unique entries were requested;
- a known-inactive player at the applicable freeze;
- a DraftKings-illegal lineup;
- a missing or mutable frozen source; or
- an unfrozen late swap.

### Frozen work

Production 068/E4 and lab 047/048/049 must run and be read exactly as frozen.
The new objective may appear only as a clearly labeled secondary receipt or a
fresh companion experiment using new banks and a new preregistration.
Rescoring an already selected historical book with a new transform is
descriptive and cannot establish adoption.

### Belief versus decision validation

Calibration of the player, lineup, winner, and field distributions is a
separate evaluation from realized book utility. The same model should not be
allowed to define both the decision and the only audit of that decision.
Where practical, selection and audit should use different laws or materially
perturbed field models.

## Current production state versus the directive

The objective change is not yet implemented in the live money path.

### P0: the active money path still selects on 194

`src/nfl_dfs/inference/production_policy.py` currently defines the money
policy as:

- boom-first supply with 40 leverage and 160 boom solves, plus role solves;
- K80/CBWU;
- `greedy-tail-coverage`;
- `tail_line = 194`; and
- the incumbent construction preset.

The module explicitly disables alternative selectors on the money route.
`src/nfl_dfs/app/main.py`, `src/nfl_dfs/models/entries_curve.py`, CLI/replay
defaults, deployment prose, and README documentation also retain active 194
semantics.

The frozen Week-1 operating-book v1 contract similarly names coverage-194 for
its core and Tier-2 sources. That artifact must remain immutable for
reproducibility, but it cannot remain the new paid-policy authority.

Required response:

1. preserve all old contracts, memberships, receipts, and historical code;
2. create a versioned live-policy successor rather than editing frozen v1;
3. wire `D400_DEMAX`—80 leverage, 320 boom, dual-law expected-max—as the
   current paid/control candidate;
4. remove 194 from active admission, selection, and adoption routing in the
   successor; and
5. retain 194 only as a labeled diagnostic column.

`D400_DEMAX` is not currently wired into the paid production path. Until the
successor is implemented and validated, the repository must not claim the new
objective is operational.

### P0: paid exact-K and export paths are fail-open

The production audit found several direct score and money risks:

- MILP generation can return fewer lineups after solver failure or pool
  exhaustion;
- coverage, LSE, and ladder selectors use
  `min(requested_entries, available_candidates)`;
- the live engine lacks a universal post-selection exact-count assertion;
- the FastAPI path rejects an empty book but not every short book;
- ordinary lineup CSV export can emit the partial list; and
- the paid-entry filler can cycle a short lineup list across the requested
  entries, producing repeated lineups.

This is not merely code cleanliness. A short or repeated book spends entry
budget without the intended portfolio coverage and directly reduces the
chance of winning.

Required boundary at every paid path:

1. assert `available_candidates >= requested_entries` before selection;
2. select exactly the requested count;
3. assert exact count and unique canonical roster identities afterward;
4. independently validate complete DraftKings legality and active-player
   eligibility; and
5. repeat the exact count, uniqueness, and legality checks immediately before
   either CSV export.

Ordinary paid upload must never fill a shortfall by cycling lineups. If an
explicit duplicate-entry experiment is ever desired, it must be a separate,
named, receipted strategy—not a fallback.

### P1: contest capture exists but is not operational

Production already contains a strong validate-first, create-only workflow at
`nfl-dfs capture-dk-standings`. It can validate and archive complete settled
fields and import entry rosters, ranks, scores, ownership, payout, duplicate
keys, source hashes, and provenance.

However:

- `contest_entries` has not received a production row;
- the workflow is manual and unscheduled;
- `dk_contest_fills` is a lobby-snapshot scaffold, not the required canonical
  contest registry;
- there is no complete versioned manifest containing contest identity, field
  size, fee, entry limit, payout ladder, winner/tie data, late-swap state,
  capture provenance, and correction lineage; and
- no deployed weekly bundle yet supplies all field-model and settlement
  inputs.

The September 13 Week-1 capture window is nonrecoverable. Full standings,
final ownership, complete field rosters where permitted, payouts, our actual
entries, and every frozen shadow must be captured promptly after settlement.

### P1: current settlement is not yet portfolio-counterfactual EV

The prospective field bridge already supports field ranks, percentiles,
duplicate matching, payout-table validation, and actual split-payout
reconciliation. That is valuable groundwork.

It does not yet produce the required counterfactual settled value of an
unentered K-book. Current logic can evaluate insertion rank for an individual
lineup and assigns unentered lineups no actual payout. Product settlement must
jointly insert the entire shadow book into the observed field, recompute:

- ranks and ties;
- duplicate counts;
- payout splits;
- self-competition among our entries;
- gross portfolio payout;
- entry fees; and
- net portfolio payout.

The receipt must distinguish actual entered payout from counterfactual payout
and must never present the latter as observed money.

## Construction-law consequence

The historical winner conformance question is already answered strongly:

| Winner structure | Share of 51 winners |
|---|---:|
| Naked QB | 22% |
| Exactly one QB stack partner | 41% |
| No bring-back | 61% |
| Full QB+2 plus bring-back house shape | 16% (8/51) |

Meanwhile, 100% of the audited production pool and selected books used the
full QB+2 plus bring-back shape. The current incumbent preset also imposes
the $49,000 salary floor, RB-versus-DST restriction, and same-team-RB
restriction.

Therefore:

- DraftKings legality is the only universal lineup law;
- house topology and salary rules become named, receipted strategies;
- DK-legality-only, QB+1, no-bring-back, and crossed variants are eligible for
  fresh testing;
- a strategy may deliberately choose a stack profile, but the corpus and
  validator may not treat that profile as universal legality; and
- existing frozen experiments retain the construction contract under which
  they were run.

This implements the operator's prior architectural direction without
pretending that historical winner structure alone proves which relaxed
strategy will be best prospectively.

## Production evidence map

The following paths are the starting points for implementation and independent
review. Line numbers describe the 2026-09-01 worktree and may move after the
successor is implemented.

| Finding | Evidence |
|---|---|
| Active policy is K80, greedy coverage, line 194 | `src/nfl_dfs/inference/production_policy.py:101-121` |
| Code identifies boom-first 40/160 as the money path | `src/nfl_dfs/inference/production_policy.py:251-280` |
| App description/request defaults remain at 194 | `src/nfl_dfs/app/main.py:111-134` |
| App selection/entry logic still derives from 194 | `src/nfl_dfs/app/main.py:1634`, `:2267` |
| Selector functions silently cap requested K | `src/nfl_dfs/optimizer/lineup.py:703`, `:731`, `:806` |
| Generator may return a partial solution set | `src/nfl_dfs/optimizer/lineup.py:582`, `:609-624` |
| Live engine lacks a universal exact-K terminal assertion | `src/nfl_dfs/backtest/engine.py:2341`, `:2771`, `:2851` |
| App checks empty, not every short book | `src/nfl_dfs/app/main.py:2569` |
| Partial standard CSV can reach export | `src/nfl_dfs/app/main.py:3119` |
| Paid-entry filler cycles a short list | `src/nfl_dfs/optimizer/export.py:116-128`, `:197`; route at `src/nfl_dfs/app/main.py:3236` |
| Full-field schema groundwork exists | `sql/raw/004_ownership.sql:6-70` |
| Validate-first capture implementation exists | `src/nfl_dfs/ingest/ownership_import.py:601` |
| Capture remains a manual workflow | `docs/dk-full-field-capture.md:3` |
| Current contest-fill schema is not a complete registry | `sql/raw/005_dk_contests.sql:5` |
| Current field bridge handles rank/duplicates/payout components | `src/nfl_dfs/inference/prospective_generation_shadow_field_bridge.py:663-877` |
| Unentered lineup handling is not joint-book counterfactual EV | `src/nfl_dfs/inference/prospective_generation_shadow_field_bridge.py:807-841`, `:1136-1148` |
| 43/51 winners fail the historical stack rules | `reports/2026-08-19-winner-world-optima-and-field-null-results.md:52` |
| Only 8/51 use QB+2 plus bring-back | `reports/2026-08-19-winner-structure-census-results.md:7-25` |
| Incumbent preset still mandates the house bundle | `src/nfl_dfs/optimizer/construction_presets.py:127` |

Frozen paths such as `src/nfl_dfs/inference/week1_operating_book.py`,
`src/nfl_dfs/inference/week1_operating_book_suite_adapter.py`, and existing
prospective shadow contracts are evidence to preserve, not files to mutate
into the new estimand.

## Recommended product freeze (A5)

The recommended terminal utility is:

> **Expected settled portfolio payout net of entry fees**, subject to a hard
> non-inferiority guardrail on modeled sole/shared first-place probability
> versus the named control.

The system should report, separately:

- expected net payout;
- gross expected payout;
- probability of sole first;
- probability of sole or shared first;
- expected first-place split payout;
- probability of any cash and major payout tiers;
- expected duplication at the top;
- self-competition cost;
- entry fees and number of entries; and
- contest allocation.

This recommendation prevents a strategy from buying small expected-value
improvements by materially reducing the chance of the top result, while still
respecting ties, duplication, and contest economics. If the operator later
chooses first-place probability at any economic cost, that preference must be
frozen explicitly as a new policy version.

K80 is an accounting and experimental basis, not a universal product law.
Entry count, contest choice, contest allocation, bankroll, and exposure caps
must be explicit decision variables and part of the receipt.

## Implementation sequence

### Phase 0: preserve and separate

1. Mark the objective notice as the governing operator directive.
2. Preserve frozen 194-era experiments and operating-book v1 byte-for-byte.
3. Create distinct IDs for the new live policy, objective, selector, field
   model, settlement model, and contest registry.
4. Amend stale descriptive documentation without rewriting historical
   receipts or verdicts.

### Phase 1: protect the paid boundary

1. Remove every fail-open exact-K truncation from paid generation, selection,
   and export routes.
2. Prohibit implicit duplicate cycling in ordinary paid export.
3. Add boundary fixtures for 0/1/2/3 same-team catchers and 0/1 bring-back to
   every independent validator that reimplements strategy rules.
4. Require an exact, unique, DK-legal, active K-book before producing a paid
   CSV.

This phase precedes any claim that a policy is money-ready.

### Phase 2: create the new paid/control policy

1. Implement a versioned successor to `ClassicProductionPolicy`.
2. Make D400 dual-law expected-max the named control candidate.
3. Make only DK legality universal; construction topology is supplied as a
   strategy preset and receipted.
4. Remove 194 from active selection and admission.
5. Keep global winner proxy, raw maximum, 194, 210, 220, 230, 240, and 250 as
   separately labeled diagnostics.
6. Require immutable source, objective, utility, model, construction,
   selector, K, contest, and allocation identities in every book receipt.

### Phase 3: operationalize Week-1 capture before September 13

1. Define the append-only contest manifest and correction lineage.
2. Run a complete dry run of `capture-dk-standings` on a representative CSV.
3. Validate field-size equality, settled state, roster parsing, ownership,
   payout reconciliation, tie handling, archive creation, and idempotent
   import.
4. Establish a durable operator checklist/reminder for the short DK download
   window.
5. Bind every prospective shadow and actual entry book to the contest
   manifest before lock.
6. Capture the complete field and settle every bound book after the contest.

### Phase 4: add objective-ladder endpoints

1. Add `GLOBAL_WEMAX_PROXY` as a secondary screen with exact artifact
   identity and honest labels.
2. Build the shrunk walk-forward `SLATE_WEMAX_PROXY` without tuning on
   same-slate outcomes.
3. Build a shared-world opponent-field sampler from point-in-time ownership
   and lineup-construction distributions.
4. Score candidate and opponent lineups in identical football worlds.
5. Add tie-aware `FIELD_WIN` selection and calibration receipts.
6. Implement joint-book counterfactual settlement and expected net payout.
7. Reopen late swap only as a new contest-state policy using standings,
   ownership, payout, and remaining-game state.

### Phase 5: run fresh crossed experiments

The decisive experiments should cross supply, retrieval, and construction
rather than assume gains stack:

- D400 supply versus alternative finalist supplies;
- dual-law expected-max versus global proxy and field-aware selectors;
- incumbent house topology versus DK-legality-only and selected relaxed
  variants;
- entry-count and contest-allocation policies; and
- field-model robustness under alternate/perturbed opponent models.

Use fresh banks and preregistrations. Do not reuse selected historical books
as confirmatory evidence. Historical panels nominate shadows; prospective
counterfactual settlement decides adoption.

## What continues unchanged now

- In-flight frozen experiments continue exactly as frozen.
- Production 068/E4 are not restarted or rewritten for the new objective.
- Lab 047/048/049 retain their frozen primaries.
- Existing 194 results remain valid descriptions of their old estimands.
- Point-in-time, immutable artifact, exact source, no-outcome, cloud registry,
  and single-writer controls remain in force.
- The objective change does not authorize reading outcomes early, relaunching
  claimed work, or tuning a new endpoint on results already observed.

At the status poll used for this review:

- PREREG-046/076 bank 480 completed successfully, 18/18 tasks, with zero
  failures, cancellations, or task retries;
- the coordinator released bank 481 as the next frozen bank;
- PREREG-039/068 mechanics remained healthy and running;
- production E4 remained healthy and running; and
- neither 068 efficacy nor E4 result collection was yet unlocked.

## Immediate next actions

1. Complete the in-flight frozen cohort without changing its objectives.
2. Review and merge only the bounded 078/079 mechanics-contract repairs;
   those repairs must not import the new objective into frozen primaries.
3. Implement the paid exact-K/unique-export boundary.
4. Create the versioned post-194 production-policy successor with
   D400_DEMAX as control candidate.
5. Implement and rehearse the canonical contest manifest and full-field
   capture before September 13.
6. Add the global proxy as an honestly labeled secondary receipt.
7. Build shared-world field-win and joint-book settled-payout evaluation.
8. Launch fresh, crossed, objective-appropriate shadows rather than mining
   already selected historical books.

## Adoption statement

The production team accepts the direction of L1-L8 and A1-A6 with the
implementation interpretation in this document. The only deliberate
qualification is that frozen 194-era artifacts remain immutable and
reproducible; “retired everywhere” means retired from active decisions, not
deleted from historical evidence.

The new objective is adopted in program direction but **not yet fully adopted
in running production code**. The active coverage-194 money path, fail-open
paid exact-K/export boundary, incomplete contest registry, and missing
joint-book counterfactual settlement must be closed before the system can
claim end-to-end winner-range or contest-utility operation.
