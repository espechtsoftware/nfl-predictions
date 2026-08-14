# Frozen score-free selector-resampling diagnostic

**Frozen:** 2026-08-14, before running this diagnostic and without reading any
candidate or lineup outcome from the active pass-tail panel.

## Question and channel

Holding the candidate set, simulated law, coverage line and entry count fixed,
how stable is the production greedy selector to resampling its finite world
sample? This varies only the **portfolio-selection measurement sample**. It is
not a marginal, dependence, generation or candidate-set arm.

## Immutable source

- Phase S selected law: `treatment`, beta `0.07771181538347656`.
- Source panel: `20260813-sis-asoe-treatment-r0-v1`.
- Source generation code: `4d6f5cf`.
- Source image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:757f0784937492c23917c245b082e052508fcac693840a1469e0020257fad6a4`.
- Population: every one of the 54 Phase S slates in 2023--2025, with no slate,
  candidate or season exclusion.
- Candidate set: exact canonical R0 candidates for each slate.
- Worlds: the checksum-verified R0 candidate-total artifact, exactly 10,000
  worlds.
- Selector: unchanged `select_from_support`, line 194, exactly 80 entries,
  including its probability and mean-total tie breaks.

The analyzer may query only identity, candidate index, selected flag/rank,
simulation contract and score-artifact identity. It may not query
`actual_score`, player actuals, standings or payout data.

## Mechanical gates

For every slate require one immutable artifact URI/hash, contiguous candidate
indices, `n_entries=80`, `n_sims=n_worlds=10000`, a 194 artifact line, and
exactly 80 persisted selections. Re-running the selector on all 10,000 worlds
must reproduce the persisted selected candidate order exactly. Any failure
invalidates the complete diagnostic.

## Fixed resampling

All randomness is derived with `numpy.random.SeedSequence([seed, season,
week])` so slates have deterministic independent streams.

1. **Disjoint halves:** permute the 10,000 columns once with seed `19,408,014`
   and split into two 5,000-world halves. Select 80 independently on each half.
   Report their overlap, their overlap with the full book, and each half-book's
   union coverage on both its selection half and the opposite validation half.
2. **Bootstrap:** make exactly 32 size-10,000 column resamples with replacement
   using seed `8,132,027`. Recompute clear probability and mean-total tie
   breaks within each resample and select exactly 80.

No resample count, seed, line, entry count, candidate filter or sampling scheme
may be changed after the result.

## Outputs

For every slate report:

- exact full-book reproduction;
- disjoint-half book overlap and reciprocal train/validation coverage;
- all 32 bootstrap overlaps with the full book;
- mean/min/5th/50th/95th-percentile pairwise overlap across the 496 bootstrap
  book pairs;
- mean pairwise prefix overlap at prefixes 1, 5, 10, 20, 40, 60 and 80;
- candidate selection frequency across the 32 books, including whether the
  candidate belongs to the full book; and
- counts selected in at least 90%, 50%--under-90%, above 0%--under-50%, and 0%
  of bootstrap books.

Aggregate with equal slate weight and report season splits. Descriptive bands
for mean pairwise exact-80 overlap are fixed as high (`>=72`), intermediate
(`>=56` and `<72`) and low (`<56`). These bands are labels, not adoption gates.

Per-candidate frequencies are stored in one checksum-addressed compressed
artifact; the mechanically validated summary is tracked in the repository.

## Decision firewall

This diagnostic cannot adopt, reject or tune a selector. In particular it does
not license mean bootstrap bagging, which converges to the existing empirical
greedy objective. The pending multi-seed candidate/world factorial retains its
unchanged tail-first exact-80 decision and production authority.

If stability is intermediate or low, the result enters the final forensic
opportunity register. Any later stability-penalized selector must name a
non-redundant objective, freeze all penalties on score-free evidence, use
independent selection and measurement worlds, and then face a separately
registered exact-80 tail-first comparison.
