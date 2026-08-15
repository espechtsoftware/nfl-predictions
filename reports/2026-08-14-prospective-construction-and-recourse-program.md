# Prospective construction and recourse program

Date: 2026-08-14 CDT. This charter was written after the final forensic result
and before any 2026 regular-season outcome. It converts the forensic leads into
prospective work without reopening the historical arm program.

## Standing boundaries

- The money baseline remains
  `classic-k1-role12-boom40-poscal-cbwu-v4`, exact 80.
- No 2019–2025 realized player score, candidate score, contest finish, payout,
  or forensic label may be used to fit, tune, select, or promote either new
  mechanism.
- Historical outcomes may be used only to describe the already-completed
  forensic evidence. Development tests must use synthetic fixtures or
  outcome-free frozen inputs.
- Every shadow must preserve PIT joins and record the information timestamp at
  each decision stage.
- A 2026 shadow does not alter submitted money lineups unless a separate,
  predeclared promotion review explicitly authorizes it.

## Program A: structural-archetype candidate generation

### Question

Can a fixed candidate budget cover more genuinely distinct tail-relevant
lineup structures than the incumbent generator, without changing the selector
or merely adding compute?

### Mechanism-design phase

Before the first shadow slate, implementation must freeze a deterministic
archetype function computed entirely from pre-lock lineup attributes. It must
include at least:

- team-block and game-block sizes;
- QB stack size and bring-back count;
- salary-spend band;
- projected ownership-sum band when live ownership is available, with a
  documented fallback when it is not;
- simulated q99 band and `p_line` band;
- a structural player-incidence embedding or equivalent outcome-free distance
  used only for diversity, never fitted on realized scores.

The historical subgroup labels in the forensic report are hypothesis seeds.
They may define named strata, but their thresholds may not be optimized against
historical actual scores. Thresholds must instead be fixed from pre-lock
quantiles within each slate, so they remain portable across scoring eras.

### Control and treatment

- **Control:** the incumbent K=1 CBWU candidate generation and exact-80
  selection path.
- **Treatment:** the identical worlds, projections, ownership input, optimizer,
  legal constraints, candidate count, and exact-80 selector, with candidate
  generation budget allocated across the frozen structural archetypes.
- The total number of optimization attempts and retained candidates must be
  identical. Treatment is budget-neutral: it cannot add candidates, worlds,
  CPU, or selector capacity relative to control.
- Candidate identity overlap, archetype occupancy, player support frequency,
  and effective rank must be emitted before any result is evaluated.
- If a requested archetype is infeasible on a slate, its attempts move through
  a frozen fallback order recorded before Week 1; they may not be redistributed
  after observing scores.

The first allocation law is frozen as
`prospective-archetype-allocation-v1`: within each slate's complete five-seed
unique union, q99 and `p_line` top terciles are the first `ceil(N/3)` rows under
descending metric and ascending canonical-roster tie breaking. The four
mutually exclusive quota strata are `block3_joint_tail` 30%,
`block3_q99_tail` 25%, `other_high_tail` 25%, and
`structural_diversity` 20%. Each source seed receives an equal
largest-remainder quota. Allocation rotates source seeds within each stratum,
then fills any infeasible stratum from the best remaining candidate while
preserving source quota. Source quota relaxes only when a source lacks enough
unique candidates, and that exception must be explicit in the receipt.

The outcome-blind classifier and allocator live in
`src/nfl_dfs/inference/archetype_candidate_allocator.py`. The separately
labeled integration lives in `inference/multiseed_portfolio.py` and is reached
only when `MULTISEED_PORTFOLIO=CBWU_ARCHETYPE_SHADOW`. It freezes the canonical
roster key as the SHA-256 of sorted roster ids, native-source q99 as NumPy's
0.99 quantile, and `p_line` as the native-world fraction at or above 194. The
live entry point requires the exact allocation version and tail line, plus the
same registered R0–R4 seed-pair contract, 80-entry candidate basis, five equal
world blocks, and final selector as the money control. The production policy
continues to emit `MULTISEED_PORTFOLIO=CBWU`; only the explicit
`archetype_shadow_environment()` opts in. Candidate persistence records the
full batch/allocation receipt and shadow levers. Program A remains a non-money
shadow.

### Measurements

For each 2026 slate, retain:

- exact 20-, 40-, and 80-entry selected memberships;
- candidate and selected weekly maxima;
- 187/194/200/210/220/230/240 crossings;
- candidate-support count and frequency bands;
- structural-archetype coverage and effective rank;
- control/treatment player-union and candidate overlap;
- runtime and optimization attempts;
- contest finish, payout, duplication, and ROI when complete contest data are
  available.

The primary operator-aligned comparison is lexicographic at
240/230/220/210/200/194/187 for the exact-80 book. Distinct improving and
worsening slates must accompany nested threshold totals. Mean weekly maximum is
secondary.

### Review schedule and adoption

Report descriptive checkpoints after Weeks 4, 8, 13, and 18. No checkpoint
may promote treatment. After Week 18, promotion requires all of the following:

1. Reproducible, complete PIT-safe paired data.
2. No candidate-budget, world-budget, selector, legality, or compute drift.
3. Improvement at the first differing tail threshold, with distinct-slate
   breadth reported.
4. No unresolved operational or data-quality failure.
5. A separate written adoption decision that accounts for entry fees, contest
   type, and available ROI evidence.

If the first differing tail threshold favors control, treatment is rejected.
If all thresholds tie, compare distinct high-tail slate breadth, then mean
weekly maximum only as a final diagnostic; a mean-only gain cannot promote the
treatment.

## Program B: recourse-aware late-swap policy

### Question

Can entries built before the early lock preserve useful late-game option value,
then use only newly available early-game information to improve the chance of
one exceptional final lineup?

### Information stages

The implementation must represent at least:

1. Initial Sunday-main lock.
2. The late-afternoon lock.
3. Sunday-night lock when a Sunday-night game is on the slate.

At each stage, locked players are immutable. Projections, ownership, news, and
scores must carry an `available_at` time no later than the decision time. Final
player outcomes are prohibited from policy inputs. The already-measured
perfect-hindsight ceiling is a feasibility bound only and cannot be the
treatment algorithm.

### Control and treatment

- **Control:** the incumbent exact-80 entries, with only injury/inactive safety
  swaps under the existing behavior.
- **Treatment:** 80 initial entries selected by a frozen two-stage objective
  that values legal late-slot alternatives under retained joint simulated
  worlds, followed by a deterministic stage-specific re-optimization rule.
- Entry count, contest allocation, initial simulation budget, late-swap compute
  budget, and legal constraints must be fixed between control and treatment.
- The policy must specify how entries are classified as alive, marginal, or
  effectively dead using simulated conditional reach probability rather than a
  realized final-score target. Version `prospective-recourse-state-v1` freezes
  `alive` at conditional reach probability >=5%, `marginal` at >=0.5% and
  `effectively_dead` below 0.5%; changing these bands is a new prospective
  policy version.
- Swaps must be generated early enough for human review and DraftKings upload.
  A failure to produce and validate the file by the operational deadline is a
  treatment failure, not missing data.

### Required rehearsal

Before use with money, run an authenticated end-to-end rehearsal that:

- loads a saved or test DraftKings entry CSV;
- identifies locked and unlocked roster slots correctly;
- creates legal swap candidates without changing locked players;
- preserves unique entry identifiers and contest assignments;
- exports a DraftKings-compatible CSV;
- validates salary, positions, game locks, duplicate lineups, and row counts;
- records a no-secret receipt and a manual rollback path.

The UI must show the current stage, entries needing action, validation errors,
and the remaining upload deadline. If any fail-closed check is red, the system
keeps the existing lineups.

The first outcome-free implementation is
`src/nfl_dfs/optimizer/late_swap.py`. It defines timezone-aware initial,
late-afternoon and optional Sunday-night stages; derives player locks from
kickoff rather than trusting only the DK marker; rejects information whose
`available_at` exceeds the decision time; and validates original versus filled
DKEntries files for immutable entry metadata, locked cells, player identity,
positions, salary cap, row count and exact duplicates. Its receipt contains no
realized outcome. The separate prospective
`POST /lineups/entries/validated.csv` route now applies that validation to an
already-filled, single-contest classic file using an explicit DK draft group
and server-controlled decision time. It leaves the established production
exporter unchanged and exposes a no-outcome validation receipt in response
headers.

Before implementation or any 2026 result, the first conditional assignment
law is frozen as `prospective-recourse-policy-v1`:

- its simulated score input is explicitly **remaining score after the current
  decision time**, generated no later than that time; observed points-to-date
  are separately timestamped and added to those residual worlds;
- every original and alternative roster must be a legal unique classic roster,
  and every alternative for an entry must retain all players whose kickoff is
  no later than the decision time;
- for tractable fixed compute, each entry considers at most 24 compatible
  alternatives, pre-ranked without outcomes by individual simulated crossings
  at `240/230/220/210/200/194/187`, then q99, then mean and canonical roster
  identity;
- entries are visited from the lowest simulated 194-point reach probability to
  the highest (entry id breaks ties). At each visit, the policy compares the
  current roster with those frozen alternatives against the other current
  entries and accepts only a strict lexicographic improvement in the simulated
  book maximum at `240/230/220/210/200/194/187`, then its q99 and mean;
- an alternative already present in the current book is ineligible, so the
  proposal cannot create exact duplicate lineups. Every entry has its original
  roster as the fail-safe fallback; no simulated improvement means no swap;
- 194-point reach probability still determines the frozen alive/marginal/dead
  labels. Those labels are reported, not used as a post-hoc threshold change.

This treatment can propose roster identities only. It is not uploadable until
the DKEntries filler and validator both pass, and it cannot use a final score,
actual ownership, contest rank, payout, or any information timestamped after
the decision.

The retained simulation transport is frozen as
`prospective-recourse-worlds-v1`. The outer archetype build may expose both
the incumbent CBWU control batch and archetype treatment batch from the exact
same five native seed books; it may not rebuild the control later from a new
data snapshot. Each batch is encoded as a checksum-bound create-only artifact
containing only DK player ids, candidate roster ids, player-by-world simulated
scores, generation time and outcome-free batch metadata. Outcome-named
metadata fields are rejected.

The paired runner is exposed as `nfl-dfs shadow-archetype-paired`. It requires
a valid code SHA, captures control and treatment during one outer build,
persists both artifacts with create-only generation preconditions, and writes
a create-only manifest whose exact JSON bytes are SHA-256 identified in the
returned receipt. The seasonal deployment runs it at 9:15am and 10:30am CT on
Sunday; both schedulers remain paused with the other NFL-only jobs until the
forensic cleanup/resume gate passes.

At a recourse decision, the adapter applies this fixed transformation to the
initial player worlds:

- a not-started player retains the initial full-game simulated distribution
  and must have zero observed points;
- a final player is fixed at timestamped points-to-date with zero remaining
  score;
- an in-progress player's total becomes
  `max(initial full-game draw, points-to-date)`, represented to the proposer as
  `points-to-date + max(draw - points-to-date, 0)`.

The in-progress rule is a deliberately simple prospective floor, not a claim
that fantasy scores cannot decline. It retains the initial joint-world rank
information while ensuring a simulated total cannot contradict points already
observed. Any future, timezone-naive, unknown, missing-locked, stale-status or
pre-kickoff nonzero observation fails closed. A later residual model would be
a separately versioned mechanism; it cannot silently replace this rule.

The rehearsal endpoint
`POST /lineups/entries/recourse/rehearsal` binds every proposed roster to its
exact DK Entry ID, fills kickoff- and marker-locked cells in place, and runs the
strict metadata/position/salary/lock/duplicate validator. It returns only the
validation receipt plus source/generated byte counts and SHA-256 values; it
deliberately withholds the generated CSV bytes and keeps
`upload_licensed=false`. This lets the authenticated UI exercise the complete
fill path before an upload route is licensed.

### Measurement and adoption

Measure initial-book and final-book tail counts, the number and type of swaps,
conditional reach probabilities, operational misses, contest results, payout,
and ROI. Report separately:

- gain attributable to information revealed after initial lock;
- gain attributable to choosing a more flexible initial roster;
- any cost to the initial one-shot book;
- the number of entries that could not be safely updated.

The same 240-to-187 tail-first order applies, but a treatment cannot promote if
it depends on an operational success rate the user cannot reliably execute.
Promotion requires the full 2026 season or a separately preregistered earlier
decision rule. The hindsight mean gain of 42.62 points is never an adoption
benchmark.

## Related shadows kept separate

- The finite-K SIS pass-tail treatment retains its existing 2026 shadow and
  schedule. It is not a factor inside either program above until separately
  tested in composition.
- Live Fantasy Points ownership projections first enter as a calibrated input
  with timestamp, vendor snapshot, missingness, and a fallback. They may not be
  backfilled from actual ownership.
- Route-share admission remains budget-neutral and lower priority. It must not
  dilute Program A by becoming an unregistered second treatment.
- Latent role-state generation is a distinct future mechanism. It cannot be
  introduced into the same first prospective comparison.

## Immediate implementation queue

1. Cloud-validate the integrated shadow and retain the immutable image receipt.
2. Run a score-free live shadow smoke when the first complete 2026 slate inputs
   are available; verify exact control candidate/world budgets and warehouse
   receipt fields before joining an outcome.
3. Wire the tested late-swap state/CSV validator into a fail-closed preview and
   upload route; the existing churn-minimizing filler remains only a candidate
   proposal until the new validator passes.
4. Implement the frozen `prospective-recourse-policy-v1` conditional-world
   assignment law that proposes the swaps.
5. Persist the paired `prospective-recourse-worlds-v1` artifacts and expose a
   fail-closed UI preview of the proposed entry changes.
6. Run the authenticated UI-to-CSV dress rehearsal; retain the receipt, while
   the rehearsal endpoint withholds the CSV bytes.
7. Keep both paths in shadow mode while the incumbent generates the money book.

This queue replaces retrospective arm mining. It does not replace the existing
Week 1 operational checklist, forensic warehouse cleanup gate, or weekly paid-
data acquisition schedule.
