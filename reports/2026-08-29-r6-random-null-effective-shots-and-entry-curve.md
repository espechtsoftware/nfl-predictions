# R6 random-book null, effective-shot proxy, and nested entry curve

**Date:** 2026-08-29
**Scope:** local analysis of already-frozen current-R6 and hard-230 books and
already-materialized realized grades. No BigQuery read, new outcome query,
population generation, selection rerun, cloud access, or production change.

## Result

The clearest scoring lever in these artifacts is entry count. On the strongest
complete hard-230 ranking, support-switched selection rises from **179.523 at
K=80** to **182.177 at K=100** and **185.517 at K=150**. That is **+5.994 DK
points from 80 to 150 entries**. The matched score-blind population reaches
183.872 at K=150, so the hard-230 population retains a paired **+1.645** at
that budget.

The K=80 retrieval results are also materially better than a uniform-random
book after adjusting for how many qualifying lineups were actually available.
For the support-switched hard-230 book:

- at 200+, it captured 8 of 22 opportunity slates versus 6.510 expected under
  an exact uniform random 80-book;
- at 220+, it captured 4 of 7 versus 1.194 expected; and
- at 230+, it captured 3 of 6 versus 0.769 expected.

That is strong descriptive evidence that retrieval is finding realized tail
opportunities rather than merely benefiting from a rich population. The 220
and 230 samples remain only seven and six opportunity slates, so their large
lifts are case-series evidence, not stable promotion estimates.

## Frozen entry-count curves

### Current R6

The persisted current-R6 score report contains only K=4/14/80 for one frozen
all-block final-fit ranking. It does **not** contain a K=100 or K=150 ranking,
and this analysis does not invent one.

| K | Mean weekly max | >=194 | >=200 | >=220 | >=230 |
|---:|---:|---:|---:|---:|---:|
| 4 | 146.394 | 0/54 | 0/54 | 0/54 | 0/54 |
| 14 | 160.144 | 1/54 | 1/54 | 1/54 | 0/54 |
| 80 | **178.435** | 8/54 | 6/54 | 4/54 | 2/54 |
| 100 | unavailable | — | — | — | — |
| 150 | unavailable | — | — | — | — |

Only aggregate current-R6 cells are local. Its per-slate population
opportunity counts are not in this persisted score report, so an exact
current-R6 random-book null or a slate-paired comparison to hard-230 cannot be
reconstructed from the local artifact without opening additional grade
objects. None were opened for this diagnostic.

### Hard-230: DPP / effective-independent-tail-shots ranking

The hard-230 terminal preserves a single 150-lineup order for each population
and selector. K=4 and K=14 below are exact nested prefixes of that frozen
order; K=80/100/150 are persisted books and were replayed exactly against the
realized grade.

| K | Hard-230 mean | P0 mean | Paired delta | Hard hits 194/200/220/230 | P0 hits 194/200/220/230 | Hard W/T/L |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 144.596 | 143.023 | +1.573 | 3 / 3 / 2 / 1 | 2 / 2 / 1 / 1 | 27 / 6 / 21 |
| 14 | 161.791 | 157.819 | +3.971 | 5 / 4 / 2 / 1 | 4 / 3 / 1 / 1 | 28 / 8 / 18 |
| 80 | **179.549** | 177.298 | **+2.251** | 13 / 11 / 3 / 1 | 14 / 9 / 1 / 1 | 22 / 7 / 25 |
| 100 | 181.954 | 179.431 | +2.523 | 16 / 14 / 4 / 2 | 16 / 10 / 1 / 1 | 25 / 8 / 21 |
| 150 | 184.983 | 184.613 | +0.370 | 19 / 15 / 4 / 2 | 18 / 13 / 3 / 2 | 20 / 10 / 24 |

The mean gain does not increase monotonically versus P0. It is largest at
K=14 and remains useful at K=100, then narrows sharply at K=150. The DPP
hard-230 benefit therefore looks like better ordering/conversion in the early
and middle prefix, not a uniformly superior 150-lineup population.

### Hard-230: support-switched ranking

| K | Hard-230 mean | P0 mean | Paired delta | Hard hits 194/200/220/230 | P0 hits 194/200/220/230 | Hard W/T/L |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 145.200 | 136.336 | +8.865 | 2 / 1 / 0 / 0 | 1 / 1 / 0 / 0 | 35 / 0 / 19 |
| 14 | 159.323 | 154.746 | +4.577 | 3 / 2 / 0 / 0 | 2 / 1 / 0 / 0 | 30 / 2 / 22 |
| 80 | 179.523 | 178.221 | +1.301 | 14 / 8 / 4 / 3 | 12 / 9 / 1 / 1 | 18 / 7 / 29 |
| 100 | **182.177** | 180.409 | +1.768 | 17 / 10 / 4 / 3 | 15 / 11 / 1 / 1 | 20 / 7 / 27 |
| 150 | **185.517** | 183.872 | **+1.645** | 20 / 15 / 4 / 3 | 17 / 13 / 2 / 2 | 20 / 9 / 25 |

The support-switched book is the best measured hard-230 curve at K=100 and
K=150. From 80 to 150 it gains 5.994 mean points, six 194+ weeks, and seven
200+ weeks. Its 220+/230+ weeks are already present within the first 80, so
the added entries improve the denser tail rather than finding another extreme
case in this panel.

These selector comparisons were already exposed to the same spent 54-slate
development outcomes. Choosing the best selector separately at each K would
be post-outcome selection; the two complete frozen rankings are shown, not
combined into an artificial hindsight envelope.

## Exact uniform-random-book reference

For each slate and threshold, the analyzer uses the realized population size
`N`, number of qualifying population lineups `M`, and exact book size `K`:

`P(at least one hit) = 1 - C(N-M, K) / C(N, K)`

This is sampling without replacement and is evaluated from integer
combinations, not Monte Carlo. All hard-230 populations have 1,000 lineups per
slate except both matched 2025-w07 populations, which have 999. The full
analyzer output carries the exact hit numerator, no-hit
numerator, and denominator for every slate, population, selector, K, and
threshold.

### K=80 hard-230 opportunity adjustment

"Random expected" is the sum of the 54 slate-specific exact probabilities;
slates with no qualifying population lineup contribute zero. "Capture lift"
is observed conditional capture minus random conditional capture.

| Ranking | Threshold | Opportunities | Observed hits | Random expected | Observed conditional | Random conditional | Capture lift | Capture-equivalent shots* |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| DPP | 194 | 26 | 13 | 8.930 | 50.0% | 34.3% | +15.7 pp | 158.9 |
| DPP | 200 | 22 | 11 | 6.510 | 50.0% | 29.6% | +20.4 pp | 186.4 |
| DPP | 220 | 7 | 3 | 1.194 | 42.9% | 17.1% | +25.8 pp | 259.8 |
| DPP | 230 | 6 | 1 | 0.769 | 16.7% | 12.8% | +3.9 pp | 111.3 |
| Support | 194 | 26 | 14 | 8.930 | 53.8% | 34.3% | +19.5 pp | 185.4 |
| Support | 200 | 22 | 8 | 6.510 | 36.4% | 29.6% | +6.8 pp | 111.2 |
| Support | 220 | 7 | 4 | 1.194 | 57.1% | 17.1% | **+40.1 pp** | 407.2 |
| Support | 230 | 6 | 3 | 0.769 | 50.0% | 12.8% | **+37.2 pp** | 446.2 |

At K=150, the support ranking captures 20/26 194+ opportunities, 15/22 200+,
4/7 220+, and 3/6 230+. The corresponding exact-random expectations are
13.143, 10.177, 2.106, and 1.391. Thus the K=150 conditional capture lifts are
+26.4, +21.9, +27.1, and +26.8 percentage points respectively.

\*The capture-equivalent count solves
`sum_s[1-(1-M_s/N_s)^n_eff] = observed hit slates` over opportunity slates.
It answers how many independent uniform random shots would be needed to match
the book's observed opportunity capture. Values above K indicate selection
enrichment. They are not literal entries, are outcome-driven, and become
unstable in the sparse 220/230 tail.

## Effective-tail-shots limitation

The predeclared simulated effective-tail-shots endpoint is a different
quantity: form each selected-lineup by held-out-world tail-event matrix,
standardize nonconstant rows, and compute the correlation eigenvalue
participation ratio `(sum(lambda)^2 / sum(lambda^2))` plus entropy effective
rank.

That quantity cannot honestly be calculated for all 54 hard-230 books from
the local terminal and realized grade. The terminal preserves score-matrix
identities, shapes, and hashes but not all 54 matrix bodies; the realized grade
contains one observed score per lineup, not 10,000 or 50,000 simulated worlds.
The fact that one selector is named
`effective-independent-tail-shots-dpp-ge-230-v1` is a selection-law label, not
a measured 54-slate effective-rank result. This report therefore provides the
clearly named **realized opportunity-capture equivalent** above and marks the
simulated tail-correlation effective rank unavailable. It does not substitute
roster overlap or one-slate task-0 evidence for the missing panel-wide matrix
diagnostic.

## Interpretation and immediate use

1. **Plan for K=100 and K=150 as first-class operating budgets.** The measured
   80-to-150 gain of 5.4 to 6.0 mean points is larger than the current
   population/selector gains. Contest caps and bankroll decide whether all
   entries are used, but the system should produce a stable nested 150 order
   so 4/14/80/100/150 are exports of one ranking rather than separately tuned
   books.
2. **Keep both DPP and support-switched challengers in the next fixed
   comparison.** DPP is better at K=80 mean and 200+ capture; support is better
   at K=100/150 mean and at 220/230 conversion. Do not collapse those endpoints
   into one post-hoc winner.
3. **Use the exact random null in every realized grade.** A binary conversion
   count without `N`, `M`, and `K` hides whether selection solved a difficult
   retrieval problem or merely encountered a dense opportunity slate.
4. **Persist the simulated effective-shot diagnostics with future books.** The
   diversity selector code already computes the correct matrix-based endpoint.
   Future terminal artifacts should retain its compact per-threshold summaries
   so analysis does not need to reopen large score matrices.

## Reproducibility

Inputs were exact local copies:

| Artifact | Bytes | File SHA-256 | Internal SHA-256 |
|---|---:|---|---|
| Current-R6 score report | 350,520 | `b0ccc59416b61c46b586a4b477639d95664870db1d2c466c390b88c1af62395d` | `bebe8688f73bcd5a497c2617aaee642e33c378830586c89d36444bc29cac3638` |
| Hard-230 selector terminal | 55,023,048 | `08fa65cc26efcae0f430a28b2eb729040ce8acfd6271984c29536cb5352cf9e4` | `ee736c2eb37e20fe7b5c9ab5a44ba639810d736f356641b85c31138b62fc72cf` |
| Hard-230 realized grade | 15,126,123 | `a0fd3dc7b2ffae28b7dec97048da4fe99fedaf717b481b239c52c65819f01ef5` | `fa6fe6f87b70736221d0696f781f5fc5e331ddefeb690e2f0fc281f146ccdea5` |

Implementation:

- `src/nfl_dfs/research/corpus_r6_random_null_kcurve_v1.py`
- `scripts/analyze_r6_random_null_kcurve_v1.py`
- `tests/test_corpus_r6_random_null_kcurve_v1.py`

The full local JSON diagnostic was 5,148,800 bytes with file SHA-256
`728be42915002e12ae92721a31c8d51deb9b6c7088e106b349502987b7447423`
and internal diagnostic SHA-256
`c320636f1592533c7eadaa854ae4b659627be494ad0ada741e9e698fc4ecafa0`.
It was generated under `/tmp` and is intentionally not treated as durable;
the analyzer reproduces it deterministically from the three exact inputs.

Focused validation: **4/4 tests passed**. The tests cover the exact
hypergeometric law, capture-equivalent inversion, nested-prefix replay and
matched pairing, plus fail-closed rejection when a persisted book is not the
frozen ranking prefix.
