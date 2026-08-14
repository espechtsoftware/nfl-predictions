# TD competitive-WR allocation terminal result

**Recorded:** 2026-08-14 CDT

**Execution:** `td-competitive-wr-allocation-v1-k46pl`

**Immutable code:** `74df236087664208235a9cf5028abe4a86187e34`

**Immutable image:** `sha256:eb2902ab0d5ba07e4981875513f4c59ae5ea14055ea82160b0c9cb751b3c80c5`

**Report SHA-256:** `e7c590c707fcdee1c93954fb540abf5d4a336baa290b84319cc2a236f7cc87a4`

## Disposition

The Cloud Run execution completed successfully, but the frozen scientific
disposition is exactly
`td-competitive-wr-allocation-invalid-or-inconclusive`. `exact80_licensed` is
false. No exact-80 lineup cell may be built or launched from this result.

Two mandatory reproduction invariants failed:

1. the treatment process's newly generated control score SHA-256 was
   `11a60720ec66d25cb0789a77932722bc8f0633945cc39c78ef1e03d28bee0c30`,
   not the Stage R canonical control score SHA-256
   `2584120b13fa99da99a6f916015c70eb985cb1f06396750de829593d7fd8979e`;
2. the TD rank-source frame was not bit-exact to the control frame in
   `mean_projection`.

The other mechanical checks were healthy: both control and source repeated
bit-exactly, allocation repeated exactly, output was finite, every sorted
player marginal was exact, only eligible WRs changed, and all ineligible rows
were bit-exact. The intervention changed 2,938 WR rows in 1,045 eligible groups.

## Disclosed but non-decisional direction

Because the run is invalid, its score comparisons cannot adjudicate the arm.
For completeness, they also did not point toward a likely rescue: treatment
worsened the aggregate variogram from `1.422472` to `1.447709` with a paired
95% interval for the increase of `[0.016816, 0.033812]`; joint-q90 Brier moved
from `0.0183974` to `0.0184353` with an interval crossing zero. Every frozen
G0/G1 improvement gate was false, and the ungated multiplicity-`>=4`
diagnostic moved away from realized dependence.

The frozen protocol explicitly states that an invalid Stage T closes this
mechanism as unadjudicated and does not license a post-result repair on the
same outcomes. Therefore this centered competitive-WR mechanism is closed on
the historical panel, with no production or exact-80 promotion. The generic
reproduction lessons should be carried into future mechanisms: snapshot
control arrays before loading intervention books, and audit simulated means
with the registered numerical tolerance rather than an accidental bitwise
frame comparison when rank-only permutations can change summation order.
