# Realistic recourse sizing result

Date: 2026-08-15 09:55 CDT  
Status: terminal valid; tail-aware policy rejected; no production promotion

## Decision

Do not adopt `prospective-recourse-policy-v1`. Under the registered 3:55 PM
Eastern lock boundary it reduced the mean weekly maximum, lost high-score
weeks and never beat the ordinary projected-mean comparator.

Do not change the adopted exact-80 baseline. Preserve
`naive-mean-reoptimization-v1` only as a 2026 paired shadow candidate: it was
nonnegative on all 54 historical slates and improved seven, but added no
`>=200` week and did not raise the historical maximum. This outcome-viewed
sizing run is not ROI or production evidence.

## Provenance and integrity

- Replacement execution: `realistic-recourse-sizing-v1-vxdwf`, one task,
  zero retries, completed `2026-08-15T14:47:53.663312Z`.
- Analysis code: `b5ef048655bf124337239fdcd11397881e494f0d`.
- Immutable image:
  `sha256:20163fdc7374e5e8c93955a6237503d2fdaf2a894ac8da32b1db39fd265e55c7`.
- Full validation: Cloud Build `63847619-ec7f-497b-ae71-451bfa81a34c`;
  1,451 passed, 2 skipped, 5 warnings.
- Same-image scorer audit: generation `1786804489195743`, SHA256
  `89528a620e203b2e8660c9e1d8b844dfef55fec17d04d639e5ec9fb156399ca4`;
  all 75,712 player weeks reconciled with zero differences.
- Proposal set: create-only generation `1786805243398712`, object SHA256
  `a700c5cc671e447ffe4daeeb29528e0a1b1b97eedca58a812269cd1f4315d63b`,
  logical proposal-set SHA256
  `5d2a40266154ef0dabd2fa3595a841a300368df8502072ec8f46931e20e0f477`.
  All 54 per-slate hashes were independently reverified; the ledger records
  `outcomes_opened=false` and was created before the outcome query.
- Result: create-only generation `1786805268693190`, SHA256
  `847c6822a61e972dfa0395009312bd4ca36fd8c6efca60663d4907941b3e6b77`.
- The first execution `realistic-recourse-sizing-v1-p2n4c` failed before
  proposal freeze on NumPy scalar serialization. Its proposal and result
  objects never existed. The registered operational repair changed only JSON
  scalar representation and was independently rebuilt/re-audited.

## Weekly high-score comparison

| Portfolio | Mean | Median | Maximum | Improved / tied / worsened vs initial |
|---|---:|---:|---:|---:|
| Initial exact-80 baseline | 176.063 | 170.910 | 235.600 | -- |
| Tail-aware realistic policy | 175.325 | 170.610 | 235.600 | 4 / 48 / 2 |
| Naive conditional-mean policy | 177.212 | 171.140 | 235.600 | 7 / 47 / 0 |
| Perfect-information hindsight | 213.870 | 213.160 | 283.480 | descriptive ceiling only |

The tail-aware policy's realized delta averaged `-0.738`, ranging from
`-56.760` to `+13.460`. Its aggregate recovery of the perfect-information
gain was `-1.95%`. The naive policy averaged `+1.149`, ranged from `0` to
`+31.000`, and beat the tail-aware policy on five slates while losing on none.

## Tail counts

| Portfolio | >=187 | >=194 | >=200 | >=210 | >=220 | >=230 | >=240 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Initial | 17 | 8 | 7 | 6 | 3 | 1 | 0 |
| Tail-aware realistic | 17 | 8 | 6 | 5 | 2 | 1 | 0 |
| Naive conditional mean | 18 | 9 | 7 | 6 | 3 | 1 | 0 |
| Perfect-information hindsight | 45 | 41 | 35 | 30 | 23 | 13 | 9 |

The naive policy's only new registered crossings were 2024 Week 5, which rose
from `185.22` to `198.68`. It created no new `>=200` week. The tail-aware
policy made the same gain but destroyed 2024 Week 3's `225.28` weekly maximum,
reducing it to `168.52`; the naive comparator preserved `225.28`.

## Slates with any change in weekly maximum

| Slate | Initial | Tail-aware | Tail delta | Naive | Naive delta |
|---|---:|---:|---:|---:|---:|
| 2023 W16 | 169.02 | 170.16 | +1.14 | 170.16 | +1.14 |
| 2024 W3 | 225.28 | 168.52 | -56.76 | 225.28 | 0.00 |
| 2024 W4 | 153.90 | 158.80 | +4.90 | 162.10 | +8.20 |
| 2024 W5 | 185.22 | 198.68 | +13.46 | 198.68 | +13.46 |
| 2024 W13 | 146.94 | 146.94 | 0.00 | 148.46 | +1.52 |
| 2025 W1 | 136.18 | 136.18 | 0.00 | 142.78 | +6.60 |
| 2025 W10 | 167.50 | 167.62 | +0.12 | 167.62 | +0.12 |
| 2025 W18 | 148.96 | 146.24 | -2.72 | 179.96 | +31.00 |

## Mechanism interpretation

The pre-outcome 194-reach classes do not explain enough of the realized
variation to rescue the tail-aware rule. Correlations with realized gain were
small (absolute Pearson at most `0.061`; absolute Spearman at most `0.203`).
Association with tail-aware-minus-naive was also descriptive and modest. The
policy changed 273 entries and 1,147 players, versus 462 entries and 2,095
players for naive mean re-optimization, yet its concentrated simulated-tail
choices were much less robust to the realized world.

Late swap also cannot close most of exact P. For the corrected hindsight
roster, exact P was missing a mean `5.148` players, of which `4.500` were
already locked and only `0.648` remained unlocked at 3:55 PM. The realistic
final weekly best still missed `6.370` P players on average. This reinforces
the review's conclusion that construction/player-support and constraint
attribution are the higher-value next target; late swap is a limited recourse
layer, not a substitute for reaching the right structural region initially.

## Next actions

1. Close `prospective-recourse-policy-v1` as a failed historical mechanism;
   do not tune it post hoc around the two bad weeks.
2. Add a no-swap versus naive-mean paired 2026 shadow to the already planned
   late-swap rehearsal. It remains non-production until prospective evidence.
3. Run the exact-P structure and construction-rule constraint-attribution
   census before assigning any fixed-budget candidate reallocation.
4. Continue the separately registered SIS receiver-copula/dependence protocol
   with fresh repaired-path controls; do not treat marginal SIS features as
   revived by this result.

The production baseline remains `classic-k1-role12-boom40-poscal-cbwu-v4`.
