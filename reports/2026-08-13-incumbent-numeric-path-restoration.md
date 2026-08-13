# Incumbent numeric-path restoration

Status: completed 2026-08-13 before launching the SIS QB line-context arm or
freezing a replacement dependence experiment.

## Decision

The default replay and live final-served calculation path is restored to the
byte-compatible implementation that preceded commits `b9c47e6` and
`89615a6`. The permutation-invariant sorted-float64 mean helper is removed
from shared production/replay transforms. No selected policy, model cache,
position scale, lineup or score changes in this milestone.

## Reason

TD-ledger v1 showed that the old float32 market-shift reduction can move a
player marginal by a few millionths when a dependence-only treatment permutes
world order. The general precision repair fixed that defect in v2, but it also
changed every one of the 13 frozen incumbent G1 variogram metrics by roughly
`2.8e-10` to `1.28e-8`. That exceeded the preregistered `1e-12` control
reproduction tolerance, so v2 remained invalid/inconclusive and licensed no
lineup test.

Because the repair was not part of an adopted arm and did not preserve the
frozen incumbent control, leaving it in the shared path would silently change
the accepted baseline. The diagnostic and both immutable runs remain in Git
and cloud artifacts; this restoration does not reinterpret them.

## Forward rule

The next dependence experiment must be isolated from shared numeric
transforms. Freeze it before output as a terminal rank-coupling treatment:
derive treatment ranks from the TD-ledger simulator, then use those ranks to
permute the *unchanged incumbent final-served marginal values*. That design
preserves exact player multisets by construction and leaves the control on its
original byte-compatible path. It may not reuse v1 or v2 as a pass.

## Validation

Focused blend, replay-shape, served-position and lineup tests pass 48/48 after
the restoration. Full-suite validation remains a cloud-build requirement
before any new immutable research image is used.
