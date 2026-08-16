# CBWU-OI paired selector-stability result

**Result date:** 2026-08-15 CDT  
**Evidence class:** score-free paired measurement diagnostic  
**Disposition:** valid and informative; descriptive only; no production change licensed

## Executive result

The strict runner reproduced both full-world exact-80 books on all 54 slates
and completed every frozen split and bootstrap measurement. CBWU-OI had higher
full-book 194-world coverage on all 54 slates, averaging a `+0.05019` absolute
coverage difference, while producing materially less reproducible exact-80
membership than the canonical pool under the same world resamples.

Across the 54 slates, mean pairwise bootstrap overlap was:

- canonical: `61.1252 / 80` (intermediate descriptive band);
- CBWU-OI: `54.5787 / 80` (low descriptive band); and
- paired CBWU-OI minus canonical: `-6.5466` lineups.

CBWU-OI pairwise overlap was lower on 53 of 54 slates. Its disjoint-half
exact-80 overlap averaged `60.8704 / 80`, versus `65.6852 / 80` canonical, a
paired difference of `-4.8148`; it was lower on 44 of 54 slates. The result is
therefore a real operational membership/order stability warning.

Per the frozen interpretation firewall, this diagnostic does not estimate how
candidate-pool gains convert to realized selected scores. It cannot tune the
selector, promote or reject CBWU-OI, reverse its fixed-budget construction
result, or change production.

## Joint construction and stability evidence

The previously observed fixed-budget construction evidence remains:

| Metric | Canonical | CBWU-OI | Difference |
|---|---:|---:|---:|
| Mean realized candidate maximum C | 181.07 | 186.73 | +5.66 |
| Weeks C >=187 / >=194 / >=200 / >=210 | 22 / 11 / 8 / 6 | 25 / 18 / 14 / 10 | +3 / +7 / +6 / +4 |
| Weeks C >=220 / >=230 / >=240 | 3 / 1 / 0 | 3 / 1 / 0 | 0 / 0 / 0 |
| Bootstrap pairwise overlap | 61.1252 | 54.5787 | -6.5466 |
| Disjoint-half overlap | 65.6852 | 60.8704 | -4.8148 |
| Reciprocal selection optimism | 0.003672 | 0.006690 | +0.003017 |

The two results describe different properties: CBWU-OI constructs a stronger
candidate pool by C, but the unchanged greedy selector's membership on that
pool is more sensitive to finite simulation-world sampling. Neither fact
erases the other.

## Season detail

| Season | Canonical pairwise overlap | CBWU-OI pairwise overlap | Paired delta | Canonical band | CBWU-OI band |
|---|---:|---:|---:|---|---|
| 2023 | 61.5349 | 54.1016 | -7.4334 | intermediate | low |
| 2024 | 62.1402 | 55.1817 | -6.9586 | intermediate | low |
| 2025 | 59.7005 | 54.4527 | -5.2478 | intermediate | low |

The cross-pool identity overlap of the two full books averaged `33.1852 / 80`.
The paired bootstrap cross-pool identity overlap averaged `32.6759 / 80`, so
the two candidate construction methods yield substantially different books
rather than merely reordering a common set.

## Mechanical validation and receipts

- Cloud Run execution: `cbwu-oi-selector-stability-v1-sfdvb`
- Terminal state: successful, `2026-08-16T02:07:48.620740Z`
- Runtime: `1h1m31.08s`
- Exact code SHA: `545ddae1b8e1256fde8e345683e0004aa5463b5e`
- Immutable image digest:
  `sha256:ad4604d86f1b1f7938136650f3d3940c9f1d6edd6a3427d618e6f943822602c8`
- Result JSON SHA-256:
  `d6d4055633b2f3202615cf637776b7724d3c2b1945789d9861d41902603896fe`
- Execution receipt SHA-256:
  `e8aaae2b9fd08ac7ab9cacfa6ffba8090c58a50fdd64845ce3cc830e91ef5673`
- Candidate-frequency artifact SHA-256:
  `73b6a4086b157a82877321c8e093a6a683584386989975b316212ca075d01047`
- All 54 slates reproduced both full-world books.
- The two pools used identical resample column indices on every slate.
- No realized candidate or lineup score was read.
- No selector parameter was tuned.

## Consequence

Treat lower CBWU-OI stability as a prospective operational-risk measurement.
Do not mine a historically favorable stability threshold or alter the current
tail-first selector from this result. Any stability-aware selector is a new
mechanism requiring its own frozen protocol and independent prospective
grading. The preregistered ATLAS exact-N diagnostic and production-law
transfer evaluation remain independent and proceed unchanged.
