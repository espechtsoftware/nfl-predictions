# A7 corpus rank-fusion variations v1

Status: frozen retrospective diagnostic protocol; no adoption authority

Frozen: 2026-08-21 after the A7-v2 result was opened and before any variant
was scored

Code parent: `b8234f9`

Run ID: `20260821-a7-corpus-rank-fusion-variations-v1`

## Purpose and interpretation

The operator requested variations of the completed A7 generated-corpus test.
This protocol answers that request with one bounded, fully reported diagnostic
over the already opened 54-slate corpus. It cannot convert a post-outcome
variant into confirmatory evidence. Every output must carry the literal label
`retrospective-post-outcome-exploratory`, and all historical-adoption,
production-change, deployment, and prospective-shadow licenses remain false.

The sole permitted use of this result is to nominate at most one deterministic
rank-fusion law for a fresh, separately frozen, unseen-2026 prospective test.
No result from this diagnostic may itself be deployed. There is no follow-up
grid, weight adjustment, threshold adjustment, or retry on this corpus.

## Exact retained input

The only score-bearing input is the already sealed A7-v2 local harvest:

- A7 run ID: `20260820-a7-select-ladder-phase-s-incumbent-v2`
- report SHA-256:
  `e29c31df96f8d207361504d5db5615e3120ede77d783a0725a4721621bf74b15`
- completion SHA-256:
  `af23011cc3f2d7837e62dedd1c492c999c47498643cc8c362c35dc0089674787`
- finish-ledger SHA-256:
  `e9328355dbf43a1451ef8a705d898688ad5ec4eae1ad4639804b8cf30d70c692`
- lease-close receipt SHA-256:
  `0cb058154da510505100df3be56a9fc4851d073a46a2f962d3e411665632641f`
- independent checker SHA-256:
  `8e967584eb6d210b1c5e54bdba4d4041f82ce775cd9348a5f66a24531280d0a7`

The analyzer must first replay the complete local finish ledger and exact
input hashes. It may not query BigQuery, read GCS, reconstruct source panels,
or obtain another outcome. The report already contains, for each slate, the
aligned candidate identities, the control and A7 score-free 80-deep selection
orders, and the candidate actual scores from the sole registered historical
query.

The report does not retain the candidate-by-50,000-world matrices. Therefore
new ladder thresholds or weights cannot be recomputed and are outside this
protocol. Only deterministic fusion of the two already frozen score-free rank
orders is permitted.

## Two-phase one-read boundary

The implementation has two commands:

1. `freeze-selections` validates the sealed input and constructs every exact
   80-index variant using only candidate identities and the two score-free
   rank orders. It writes one canonical, create-only selection manifest and
   SHA ledger containing all 54 control books, all seven variant books, their
   per-slate hashes, and the aggregate manifest hash. The monolithic report
   bytes may be read for their exact SHA and decoded once for strict canonical
   JSON syntax, which necessarily materializes every JSON value. Phase 1 may
   not dereference, iterate, transform, compare, log, hash separately, or emit
   the `candidate_actual_scores` field. Selection construction and validation
   must receive only an explicit score-free projection that omits that field.
2. Only after that selection manifest is committed and pushed may `score`
   reopen the exact manifest and access the already retained
   `candidate_actual_scores` once. It scores every frozen variant in the fixed
   order below and writes one canonical, create-only result plus SHA ledger.

Identical reruns may only validate the existing bytes. A collision, missing
variant, extra variant, changed selection, changed input, or partial result is
fatal.

## Frozen variation grid

For each slate, let `C` be the control's 80 distinct candidate indices and
`T` the A7 treatment's 80 distinct candidate indices. Let `rC(i)` and `rT(i)`
be one-based ranks in those orders, with missing rank exactly 81. Let
`U = C union T`, and let `d = |C \ T| = |T \ C|`.

The control is the reference and is not one of the seven challengers. The
challengers, in the only permitted reporting order, are:

1. `DS25`: set `k = ceil(d / 4)`; remove the `k` worst-ranked `C`-only
   members (descending `rC`, then descending candidate index) and add the `k`
   best-ranked `T`-only members (ascending `rT`, then ascending candidate
   index).
2. `DS50`: the same law with `k = ceil(2*d / 4)`.
3. `DS75`: the same law with `k = ceil(3*d / 4)`.
4. `RB25`: rank every member of `U` by the tuple
   `((3*rC + rT), max(rC,rT), min(rC,rT), candidate_index)` and retain the
   first 80.
5. `RB50`: rank by
   `((2*rC + 2*rT), max(rC,rT), min(rC,rT), candidate_index)` and retain the
   first 80.
6. `RB75`: rank by
   `((rC + 3*rT), max(rC,rT), min(rC,rT), candidate_index)` and retain the
   first 80.
7. `A7-100`: use exactly the frozen treatment set `T`.

Every retained book is serialized as ascending candidate indices because the
only estimand is the exact-80 weekly maximum. `freeze-selections` must prove
80 unique in-range indices per book, exact control/A7 endpoints, equal
directional-difference cardinality, nonvacuity of every challenger on every
slate, and complete 54-slate coverage. Individual variants may coincide on an
individual slate; that fact is reported and never repaired.

## Frozen scoring and reporting law

Candidate scores must be literal non-boolean finite Python JSON integers or
floats. Convert each score to exact integer cents as
`cents = round(float(score) * 100)`, using Python's nearest-even `round`; then
require `abs(float(score) * 100 - cents) <= 1e-9`. Values outside that bound
are fatal. Convert cents to exact integer micro-DK points as
`micro = cents * 10_000`; all thresholds use `threshold * 1_000_000`.
Before scoring any new variant, reconstruct the sealed control and A7 ordered
score vectors from the aligned candidate rows and require exact cent/micro
equality with each arm's retained `realized.scores`, exact identity equality,
and exact N=80 prefix maxima. Recomputed control/A7 means and threshold counts
must match the sealed A7 outcome at `EPSILON = 1e-12` after rendering micro-DK
values back to DK points.

All maxima, thresholds, signs, and ties use the exact integer micro-DK values.
The co-primary implementation excludes exactly zero differences, assigns
average ranks to equal absolute nonzero differences using stable rank order,
and defines `W+` as the sum of ranks having positive differences. For at most
20 nonzero differences, enumerate all `2^n` sign assignments. Otherwise draw
exactly 200,000 sign vectors in chunks of 65,536 and use add-one p-values.
For each challenger separately, initialize a fresh
`rng = numpy.random.default_rng(20_260_818)`; for each chunk call exactly
`rng.choice((-1.0, 1.0), size=(take, n_nonzero))` and use that same sign
matrix for both the mean and W+ hit counts. Both tests are inclusive,
two-sided comparisons against the absolute observed statistic with
`EPSILON = 1e-12`; p-values are capped at 1.0. The mean test uses the signed
sum, and the rank test uses distance of `W+` from half the total rank.

For Holm adjustment, sort the seven `(p_joint, fixed_variant_index)` pairs.
At zero-based sorted position `j`, form `(7-j) * p_joint`; the adjusted sorted
value is the capped-at-one running maximum of those values through `j`, then
is mapped back to its variant. Eligibility and nomination use the full
unrounded statistics, never rendered decimal strings.

The score command reports all seven variants, without filtering or favorable
ordering, with:

- exact-80 mean and median weekly maximum and mean delta versus control;
- treatment-better, tied, and control-better slate counts;
- the independently implemented paired mean sign-flip p-value, signed-rank
  `W+`, and signed-rank sign-flip p-value under the already registered A7
  co-primary law;
- `p_joint = max(p_mean, p_signed_rank)` and Holm-adjusted `p_joint` across
  all seven challengers;
- total counts and deltas versus control at 187, 194, 200, 210, 220, 230,
  and 240 DK points;
- mean delta for each of 2023, 2024, and 2025; and
- minimum, mean, and maximum control-book swaps over the 54 slates.

There are seven post-outcome comparisons. Holm adjustment is descriptive and
does not restore confirmatory status. N=4 and N=14 prefixes are deliberately
excluded: these fused sets have no separately frozen internal selection order.

## At-most-one future nominee

A challenger is eligible for nomination only if all of the following hold at
exact 80:

- mean delta versus control is strictly positive;
- 194 and 200 threshold-count deltas are each at least -1;
- treatment-better slates are at least control-better slates; and
- at least two of the three season mean deltas are nonnegative.

Among eligible challengers, choose exactly one by the fixed tuple: smallest
Holm-adjusted `p_joint`, then largest mean delta, then smallest mean swap
count, then the fixed variant order above. If none is eligible, the nominee is
null. Nomination permits only drafting and freezing one new unseen-2026
prospective challenger. It does not imply a pass and sets no deployment,
production, adoption, or shadow license.

## Required output assertions

Both selection and score artifacts must bind the protocol SHA-256, exact input
hashes, fixed variant order, exact 54-slate order, implementation receipt, and
their own canonical body SHA in a separate create-only ledger. The scored
artifact must additionally assert:

- `retrospective_post_outcome_exploratory = true`
- `new_outcome_query_executed = false`
- `historical_adoption_licensed = false`
- `production_change_licensed = false`
- `deployment_licensed = false`
- `prospective_shadow_licensed = false`
- `followup_corpus_variation_licensed = false`

All validation failures are terminal for this diagnostic identity.
