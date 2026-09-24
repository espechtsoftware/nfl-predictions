# The WR "bust gap" is mostly a measurement artifact; the real lower-tail misses are TE zeros and QB early exits

Production, 2026-09-23. Sizing request from the operator ("size the WR bust gap"), following the laptop's
`reports/2026-09-22-laptop-player-tails-are-not-too-thin.md`, which found WRs land below their simulated p10 only
3.5% (2021) / 4.5% (2019) of the time against a nominal 10%.

**Why re-measure first.** That check drops every player-game whose realized score is exactly 0
(`act[i] != 0`), and it computes PIT as `P(draw <= actual)`. Zero is the deepest bust, and the simulator puts
6-7% of each WR's mass exactly at 0, so both choices push WR PITs up and the <p10 rate down.

**Design.** Same banks, seeds, law env (`NFL2_ENSEMBLE=1`, `NFL2_CENTER=mean`) and filter (skill positions,
projection >= 5) as the laptop's script, nfl2 `9b341d7`, 2019 and 2021 k1 slates (outside L01's panel).
Realized zeros are kept for players who were active; PIT is randomized over point masses
(`P(d < a) + U * P(d == a)`). Script: `reports/lab-handoffs/2026-09-23-lower-tail-pit-with-zeros.py <season> <out>`.
`was_active` is post-game truth, which is correct for scoring calibration (not a feature).

| position | <p10, zeros dropped (2019 / 2021) | <p10, active zeros kept | nominal |
|---|---:|---:|---:|
| WR | 4.5% / 3.5% | 6.8% / 5.9% | 10% |
| TE | 5.9% / 6.2% | **13.5% / 13.1%** | 10% |
| QB | 10.8% / 14.6% | 11.1% / 15.4% | 10% |
| RB | 7.5% / 9.9% | 9.9% / 12.1% | 10% |

Percentile PIT near a point mass still overstates the WR gap, so the decisive view is in **points**: mean
simulated P(X < t) against the realized share, active players, both seasons pooled.

| position (n) | < 0.01 | < 3 | < 6 | < 10 | >= 20 | >= 30 |
|---|---|---|---|---|---|---|
| WR (2,237) | 6.6 vs 6.9 | 19.6 vs 18.4 | 35.9 vs 35.9 | 54.5 vs 54.4 | 16.1 vs 14.7 | 4.4 vs 4.1 |
| TE (753) | **0.2 vs 7.7** | 21.5 vs 24.3 | 42.4 vs 43.4 | 63.9 vs 64.8 | 9.4 vs 8.1 | 1.5 vs 1.2 |
| QB (864) | 0.5 vs 1.7 | 3.5 vs 6.2 | 8.3 vs 10.6 | 19.6 vs 21.5 | 36.4 vs 36.3 | 9.2 vs 9.6 |
| RB (1,585) | 1.8 vs 3.7 | 16.3 vs 18.6 | 32.7 vs 34.8 | 52.0 vs 54.2 | 16.8 vs 16.4 | 4.5 vs 4.0 |

(sim % vs realized %)

## Reading
1. **WR busts are calibrated in points.** At 3, 6 and 10 points the simulated and realized WR rates agree
   within 1.2 pp, and the zero mass matches (6.6 vs 6.9). What remains of the percentile gap lives between 0
   and about 2 points, which moves no lineup decision. **Size of the distortion: nil; no fix proposed.**
   The one small WR miss is on the upside: 20+ games simulated 16.1% vs 14.7% realized (about 10% relative).
2. **TEs are the real lower-tail defect.** The simulator almost never gives an active TE a zero (0.2%), while
   7.7% of active TE games score 0. Below 6 points it is close again (42.4 vs 43.4), so the missing zeros are
   mostly blocking TEs with 1-4 point projections of receiving. It matters for cash lineups; for tournaments it
   is small.
3. **QBs bust slightly more than simulated** (below 6 points 10.6% vs 8.3%): early exits and benchings, already
   partly addressed this season by the availability repairs.
4. **Correction to the laptop's report:** "WRs bust less than simulated (replicates in both seasons)" is an
   artifact of dropping zero games and should not be used for the cash shadow or anything else.

Limits: two seasons, lab replay centring (not the live production-centred path), incumbent bank only.
