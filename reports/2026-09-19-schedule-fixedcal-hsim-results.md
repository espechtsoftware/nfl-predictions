# Schedule sensitivity audited with fixed calibration

Frozen amendment/source`c6fb424f`. Both control and live-line treatment selection score banks reproduced exactly after separating pilot calibration from final draws. Fixed calibrated weights/efficiencies are retained in the [full receipt](reviews/evidence/2026-09-19-schedule-fixedcal-hsim.json). Final audit worlds use seed2426; pilot calibration remains seed2326 for each law. Runtime33.617seconds. The original and treatment books are unchanged from the previous study:72/97overlap, first lineup identical.

| Conditional hsim audit law | New−original Emax | MonteCarlo95% interval | New−original P220 | MonteCarlo95% interval |
|---|---:|---:|---:|---:|
| Original benchmark lines |−0.276856|[−0.414787,−0.138925]|−0.45pp|[−0.8502,−0.0498]pp|
| Archived live-frame lines |+0.067016|[−0.075027,+0.209059]|+0.16pp|[−0.2800,+0.6000]pp|

The corrected-law audit gives a small positive difference with intervals spanning zero. GLOBAL proxy differences are−0.002558under the original law and+0.000494under the corrected law; the corrected-law interval also spans zero. These intervals measure finite-world uncertainty conditional on each fitted simulator, candidate pool and selected books. They do not measure uncertainty about actual football, and there is still no independent incumbent audit half.

The original complete-simulator-repeat results remain published. Their different seed also recalibrated pilot weights, which explains why they answer a different question. This follow-up isolates fresh final-world evaluation. No extra seed search or selection tuning occurred; full prefix/block metrics and calibrated weights are retained.

This confirms selection sensitivity to the stale-input defect and supplies a correctly labeled audit. It does not establish real-world220+improvement or compel adoption. A concrete live-only input repair and release rehearsal can now be evaluated independently of optimistic model scores.
