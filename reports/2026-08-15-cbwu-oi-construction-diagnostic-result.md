# CBWU-OI fixed-budget construction diagnostic result

Date: 2026-08-15  
Protocol: `20260815-cbwu-oi-construction-diagnostic-v1`  
Evidence class: outcome-viewed candidate-layer forensic; no selected-book score

## Immutable execution

- Cloud Run execution: `cbwu-oi-construction-diagnostic-v1-4rr8d`
- Analysis code: `486643cd6b453dbed6bae79ba350e6a72c62cacd`
- Analysis image:
  `sha256:710490b4bde4b0933d1d35d49a6ed30e322ad9760b0dfe82533127c8d3acf693`
- Protocol SHA-256:
  `3b458263b165b380e6adf1efdf6ed08fb423c91d6988b5741aa32b11beafe1ec`
- Strict report SHA-256:
  `adfa9c0a5d23f5ce1ea4f70d7443affbcb84ee7cae72ac6c176e065abf23dfd6`

All 270 source artifacts, 54 canonical retained pools, five OI rotations per
slate, corrected-P identities, legal rosters and equal frozen R0 candidate
budgets passed their mechanical gates before realized player scores were
queried. The report does not score the OI selected 80 and cannot authorize an
historical arm or production change.

## Candidate-layer result

CBWU-OI materially improves the best available candidate at the same admitted
candidate count.

| metric | canonical CBWU C | CBWU-OI C | change |
|---|---:|---:|---:|
| mean weekly C | 181.07 | 186.73 | **+5.66** |
| weeks >=187 | 22 | 25 | **+3** |
| weeks >=194 | 11 | 18 | **+7** |
| weeks >=200 | 8 | 14 | **+6** |
| weeks >=210 | 6 | 10 | **+4** |
| weeks >=220 | 3 | 3 | 0 |
| weeks >=230 | 1 | 1 | 0 |
| weeks >=240 | 0 | 0 | 0 |

Paired weekly C improves on 25 slates, ties on 25 and declines on four. The
median change is zero because half the weeks tie; the largest gain is +49.82
and the largest decline is -27.20. The six newly created 200+ candidate weeks
are 2023 Weeks 5/10/16 and 2025 Weeks 9/14/15. Four of those also newly clear
210: 2023 Weeks 10/16 and 2025 Weeks 14/15.

The effect is directionally positive in every season:

| season | canonical mean C | OI mean C | delta | >=200 | >=210 |
|---:|---:|---:|---:|---:|---:|
| 2023 | 185.63 | 191.57 | +5.93 | 2 -> 5 | 2 -> 4 |
| 2024 | 181.15 | 183.12 | +1.97 | 3 -> 3 | 2 -> 2 |
| 2025 | 176.43 | 185.50 | +9.07 | 3 -> 6 | 2 -> 4 |

## What changed structurally

- Candidate budget remains exactly equal on every slate: 241--265, mean
  253.81.
- The complete native discovery union is 500--801 candidates, mean 579.80.
- Canonical and OI admitted pools share only 103.26 identities on average,
  40.72% of the fixed budget. This is a real admission change, not numerical
  comparison noise.
- Mean unique player-pair reach rises 3,056.35 -> 4,307.80.
- Mean QB stack-core reach rises 118.78 -> 181.09.
- Mean minimum swaps to corrected P improves 5.17 -> 4.87: better on 16
  slates, tied on 35 and worse on three.
- The mean corrected P-to-C score gap narrows 68.91 -> 63.25 points.

OI retains all nine P players somewhere in its admitted pool on 44 slates and
eight on ten; canonical retains all nine on all 54. Therefore the gain is not
simple player coverage. It comes from admitting different combinations with
substantially broader pair and stack-core reach.

## Consequence

This is the strongest current evidence that fixed-budget construction can be
improved without merely generating more candidates. It validates CBWU-OI as a
high-priority **prospective 2026 construction shadow** and supports further
new-combination work such as ATLAS.

It does not establish that the OI-selected exact-80 book would have achieved
these oracle C gains, and the frozen protocol deliberately forbids computing
that hindsight result. Production remains
`classic-k1-role12-boom40-poscal-cbwu-v4`. Promotion requires prospective
evidence and full P/C/S plus selector revalidation against the changed pool.

