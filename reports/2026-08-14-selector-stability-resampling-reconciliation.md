# Reconciliation: selector stability under world resampling

Date: 2026-08-14. This reconciles
`reports/2026-08-14-selector-stability-under-world-resampling.md` against the
current selector, Phase S artifacts and the frozen multi-seed factorial. No
candidate or lineup outcome was read.

## Accepted

Re-running the deterministic selector on identical worlds is empty, while
resampling worlds with a fixed candidate set is a useful score-free stability
diagnostic. Selection frequency, pairwise/prefix overlap and reciprocal
half-sample validation directly measure how much of the exact-80 book is stable
under Monte Carlo sampling. This is distinct from candidate-generation seed
sensitivity and can run from already persisted worlds without re-simulation.

The proposed realized-maximum slice is not score-free. It is excluded from the
diagnostic and deferred to the final forensic analysis, where it remains
descriptive and cannot choose a selector.

## Corrections

The current Phase S artifacts contain 10,000 worlds per seed, not the note's
illustrative 30,000. The diagnostic therefore binds to the selected Phase S
treatment R0 candidate set and its exact 10,000 worlds on all 54 slates.

`C0W0` versus `C0WU` in the pending multi-seed factorial already holds the R0
candidate set fixed. It changes only selection worlds from R0's 10,000 to the
equal-weight R0--R4 union of 50,000. Candidate generation changes in the `C0`
versus `CU` contrast, not in `C0W0` versus `C0WU`. The new diagnostic is still
complementary: it estimates within-R0 resampling stability and held-out
selection optimism rather than the production value of five independent world
books.

The proposed mean-bagged greedy selector is not a distinct arm. For any fixed
covered set and equal-sized partition, averaging marginal clear counts across
all parts equals the full-sample marginal clear count. Likewise, the expected
ordinary bootstrap marginal gain equals the empirical full-sample gain. With
many resamples it converges to the existing selector; with finitely many it
adds Monte Carlo noise. A new selector would need a separately frozen
stability penalty, lower-confidence objective or genuinely independent world
information. None is licensed by this diagnostic.

## Adopted response

Run one separately frozen, score-free R0 diagnostic. It reports exact full-book
reproduction, deterministic disjoint-half selection/validation, 32 fixed-seed
bootstrap selections, per-candidate frequency, pairwise and prefix overlap,
and selection-coverage optimism. It cannot change production or launch an
outcome-facing selector arm.

Interpret it alongside the already-frozen multi-seed factorial. If five-seed
world union wins the tail-first exact-80 decision, that supplies genuinely new
world information and may change production under its existing protocol. If
the resampling diagnostic is unstable but world union does not win, record the
instability in the forensic opportunity register rather than inventing a
post-hoc selector.
