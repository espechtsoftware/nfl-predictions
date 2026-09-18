# E0c: real D800 pool, conditional archive selection stability

September 18, 2026. Completed bounded empirical-distribution pilot. Five replicates × three world counts = 15 K80 selections. No 2026 actual outcomes, model retraining, new candidate solves or live changes. Independent peer review pending.

## Finding and practical meaning

Within the fixed archived distribution, moving from 1000 to 20000 decision worlds improved full-archive K80 GLOBAL_WEMAX_PROXY in all five paired replicates. The mean improvement was 0.001165864, range 0.001038920–0.001274964, Monte Carlo SE 0.000038031. This is an engineering diagnostic conditional on one archive, not a five-slate football result.

At 20000 worlds, the mean proxy shortfall versus full-archive greedy was 0.000182962, about 3.06% of the reference proxy. The associated raw expected book maximum was 0.267 synthetic points lower on average. Book membership still varied: mean Jaccard overlap with the reference was 0.554. Consequently, considerable membership turnover can coexist with relatively close estimated values. None of these differences establishes an actual NFL gain or optimal K80 selection.

| Decision worlds (total) | Mean proxy difference vs reference | Mean decision optimism | Mean raw-max difference | Mean K80 Jaccard |
|---:|---:|---:|---:|---:|
| 1000 | -0.001348826 | +0.004344080 | -2.3633 | 0.1894 |
| 5000 | -0.000560096 | +0.001581730 | -0.9269 | 0.3811 |
| 20000 | -0.000182962 | +0.000535986 | -0.2667 | 0.5543 |

Full-archive K80 greedy reference: proxy 0.005977178, raw expected maximum 148.5112, P(max ≥220) 0.00135 (27 of 20000 equally weighted component-world columns). The proxy is the fixed pooled historical winner utility, not the probability of winning this slate or a payout forecast.

## Prefix behavior

| Prefix K | Mean proxy gain: 20000 vs 1000 worlds | Mean overlap with reference at 20000 |
|---:|---:|---:|
| 1 | +0.000156659 | 1.0000 |
| 10 | +0.000400252 | 0.2667 |
| 20 | +0.000571923 | 0.3927 |
| 40 | +0.000751246 | 0.4742 |
| 80 | +0.001165864 | 0.5543 |

All five 20000-world replicates picked the same first candidate as the full-distribution reference. That does not establish the best real Millionaire entry: the objective is the fixed model proxy, and no realized score or contest payout was evaluated. The smaller-prefix overlap results caution against interpreting row/order changes alone as stronger lineups.

## What was actually measured

The finite law contains two different 10000-world selection components, weighted equally. Both were used in the historical selection process. We fixed that empirical law, resampled full joint-world columns with replacement within each component, selected a book, and evaluated that book over every original column. Duplicate worlds were collapsed into frequency weights. The full-archive greedy reference is not a globally optimal book. Signed differences are reference comparisons, not true regret.

Even a 20000-draw bootstrap contains duplicate and omitted columns. This run does not compare original 20000 worlds with 20000 fresh model worlds; it measures instability when resampling the finite empirical law. It cannot reveal events absent from the archive, original-law calibration error, or the original selected book’s independent performance.

This archive is an older D800 Week-1 construction, not a current D3200/12560 population. Only five engineering replicates were frozen. The sparse 220 tail (27 reference columns) makes tail diagnostics fragile; they do not justify a 220-focused adoption rule. The fixed historical utility registry is deliberately part of the objective. It was read, but current-slate actuals and historical experiment result payloads were not.

## Verification and provenance

Frozen executable commit `cd714b7ecaae1941154bf4e72c44749154cbe672`; clean tree at execution. Script SHA256 `3bf2ea98918b2d4c0d105faa0db447c638d2556de7ac9f92e4549dc2abab8e33`. Python 3.14.4, NumPy 2.5.3. Single-threaded computation 12.125 seconds, below the five-minute bound. No cloud compute execution.

Both complete NPY payloads matched this exact 397-player archive’s receipt SHA256; all input generations and parquet hashes were pinned. Frame/roster order hashes, unique candidates, array shape/dtype and finite values passed. The fixed historical utility registry hash and 48-record census matched. Weighted greedy passed a complementary fixture and duplicated-world equivalence check; every selection had 80 unique candidates and correct K1 mean-utility choice. Every reported full-law utility was independently scalar-summed and prefixes were monotonic. Internal checks do not substitute for independent review.

[Protocol](2026-09-18-e0c-archive-resampling-protocol.md), [executable](reviews/evidence/2026-09-18-e0c-archive-resampling.py), [complete results, books, uncertainty and input identities](reviews/evidence/2026-09-18-e0c-archive-resampling-results.json).

## Next routing decision

Do not expand bootstrap counts or tune the selector on this single archive. Request independent reproduction and critique, then prioritize retaining complete independent audit banks and frozen law/calibration inputs on future builds. This is needed to ask the original-law question honestly. A replay against mutable current inputs is not a substitute. Any archival change must be isolated and checked by the operating agent before deployment.

The present pilot supports investigating precision under a fixed model, but does not support spending on a full historical rebuild, adopting a new selector, or changing the entered spreadsheet. It also does not close predictive-data or K80 search improvements. Those are separate questions left open.
