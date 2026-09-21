# Week-2 residual gap after confirmed repairs

The confirmed prop-source/fallback and weather omissions explain major projection errors, but they do not explain the full contest result.

## Evidence from the realized candidate pool

The 12,555-candidate pool's best realized lineup scored 197.26, while contest winners scored roughly 232–235. The best pool lineup had a simulated selection mean of only 115.99 and was never ranked into the delivered book. Thus there were two separate losses:

1. the pool did not contain the full realized-winning structure; and
2. the selector failed to surface the best realized row that the pool did contain.

The perfect-lineup components were unevenly represented in the pool:

| player/team | pool rows | projection | realized |
|---|---:|---:|---:|
| Jaxon Smith-Njigba | 1,385 | 17.33 | 45.5 |
| CeeDee Lamb | 1,255 | 16.55 | 38.3 |
| Dalton Schultz | 1,028 | 10.40 | 29.0 |
| Dak Prescott | 468 | 21.55 | 29.8 |
| DeVonta Smith | 672 | 12.76 | 30.7 |
| Tre Tucker | 119 | 6.70 | 25.9 |
| Jonah Coleman | 1 | 0.53 | 14.8 |
| Omarion Hampton | 605 | 13.77 | 18.5 |
| Panthers DST | 86 | 7.00 | 26.0 |

The low-supply players were not simply selector omissions. Coleman was projected at 0.53 with no prior mean and appeared once; Tre Tucker had no market line and a 6.70 projection; Panthers DST had no player market and an ordinary 7.0 projection. The generator therefore had little opportunity to assemble the realized winner.

## What this means

The prop identity/fallback defect and rain omission are necessary repairs, but they cannot create missing cheap-player/DST scenarios retroactively. The residual gap requires separate tests of:

- cold-start and minimum-price candidate supply;
- DST projection calibration and opponent/game-context features;
- low-projection touchdown/role uncertainty;
- whether the generation law overweights simulated variance in expensive players;
- whether the selector's expected-max objective suppresses rare, complementary cheap-player combinations.

These tests must use a fixed candidate pool and preserve a control. A cheap-player floor or blanket randomization is not justified by this slate; the correct shadow is a controlled supply arm (minimum-price/cold-start inclusion) crossed with the current selector and the ladder selector, with realized 200+/210+/220+ and best-of-book endpoints.

