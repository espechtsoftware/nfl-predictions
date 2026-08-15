# Frozen paired CBWU-OI selector-stability protocol

**Frozen:** 2026-08-15 CDT, before running this diagnostic and without reading
any new realized candidate or lineup outcome.

## Question and evidence class

Does the exact-80 greedy 194-coverage selector have materially different
finite-world membership and ordering stability on the passed order-invariant
CBWU-OI pool than on the canonical CBWU pool?

This is a score-free, paired measurement diagnostic. It varies only the world
sample used to measure the unchanged selector on each already-frozen candidate
pool. It is not a candidate-quality, realized-score, selector-treatment or
production-adoption test.

## Immutable sources

- Source panels, in canonical order:
  `20260813-sis-asoe-treatment-r0-v1` through
  `20260813-sis-asoe-treatment-r4-v1`.
- Exactly 54 Phase-S slates in 2023--2025 and exactly 270 checksum-verified
  candidate/world artifacts.
- Forensic manifest SHA-256:
  `51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02`.
- Passed CBWU-OI source report:
  `reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json`,
  SHA-256
  `556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33`.
- Canonical and OI reconstruction functions and the unchanged
  `select_tail_entries(..., 80, 194, env={"SELECT_LSE": "0"})` selector.

The runner may query only source identities, candidate identities/tags,
pre-lock player metadata and score-artifact identities. It must reject any
query or frame containing player actuals, candidate actual scores, standings,
ownership outcomes, contest ranks, payouts or winnings.

## Mechanical gates

For every slate:

1. load one checksum-valid artifact for each of R0--R4, each containing the
   exact contiguous native candidate order and 10,000 player/candidate worlds;
2. reconstruct canonical CBWU and all five cyclic CBWU-OI rotations;
3. require every OI rotation to have byte-identical ordered candidate
   identities and candidate totals;
4. require canonical and OI candidate counts to equal the frozen R0 budget and
   require both pools to contain at least 80 unique legal candidates;
5. concatenate worlds in the fixed R0--R4 order for exactly 50,000 worlds;
6. reproduce the canonical and OI full-world ordered exact-80 identities in
   the passed CBWU-OI source report; and
7. use identical resample column indices for the two pools.

Any failure invalidates the whole diagnostic. No partial slate result may be
interpreted.

## Fixed resampling

All streams use `numpy.random.SeedSequence` and are independent by slate and
R-block.

### Stratified disjoint halves

For each 10,000-world R-block, permute columns with seed components
`[19408014, season, week, block_index]` and split into two 5,000-world halves.
Concatenate the five left halves and five right halves in R0--R4 order, giving
two disjoint 25,000-world measurements. Select exact 80 independently from
each pool on each half.

### Stratified bootstrap

Create exactly 32 resamples. For each replicate and each R-block, draw 2,000
columns with replacement from that block using seed components
`[8132027, season, week, replicate_index, block_index]`. Concatenate the five
samples in R0--R4 order for exactly 10,000 worlds. Recompute support,
probability and mean-total tiebreaks, then select exact 80. The reduced
10,000-world bootstrap measurement keeps compute and information size
comparable with the earlier R0 diagnostic while every resample represents all
five blocks. The full 50,000-world book remains the reference.

No resample count, seed, sampling width, block weighting, line, entry count,
candidate filter or tiebreak may change after a result is read.

## Required outputs

For canonical and OI separately, by slate, season and overall, report:

- full-world book reproduction and coverage;
- disjoint-half overlap, each half's overlap with the full book, and reciprocal
  train/validation coverage;
- all 32 bootstrap overlaps with the full book;
- pairwise bootstrap overlap mean/min/q05/q50/q95;
- pairwise prefix overlap at 1/5/10/20/40/60/80;
- identity-keyed candidate selection frequencies and the fixed frequency
  bands used by the prior diagnostic; and
- full-book and resampled exact-80 canonical-versus-OI overlap.

Report paired OI-minus-canonical deltas for every aggregate stability metric.
Retain the prior descriptive bands for mean pairwise exact-80 overlap: high at
least 72, intermediate at least 56 and below 72, low below 56. These bands are
labels, not a pass gate. Do not compare raw candidate indices across pools;
cross-pool overlap is always canonical roster identity.

## Decision firewall and order

This diagnostic cannot score C or S, change the tail-first law, select a
resampling method, tune the greedy selector, promote/reject CBWU-OI or change
production. A low or worsened stability result is an operational-risk finding
for the prospective shadow, not permission to mine a historically favorable
book. Any future stability-aware selector is a new mechanism requiring an
independent frozen protocol and prospective grading.

Run only after the already-frozen ATLAS score-free execution is terminal and
strictly harvested. It must not modify, condition or reinterpret ATLAS's
predeclared gate.
