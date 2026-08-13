# SIS QB offensive-line final-served result

Frozen disposition: **fails the score-free gate; no lineup score was read.**

Cloud Run execution `tabpfn-sis-qb-line-final-served-v1-vkx49` completed
successfully in 17m36.59s from immutable audit image
`sha256:c536b05c33b120cea860fb6d0067192c740a33cfe9fd60461195c039ecd40db5`.
The complete machine report is under
`reports/tabpfn-sis-qb-line-runs/20260813-tabpfn-sis-qb-line-final-served-v1/`.

## Registered decision

On 1,520 active-QB rows across 54 evaluation slates, treatment Brier-30 was
`0.0464094132` versus control `0.0463863454`, a treatment-minus-control change
of `+0.0000230678`. Lower is better, so the frozen primary condition did not
pass. Both arms preserved row means within the registered `1e-10` tolerance.

The paired slate-cluster 95% interval for the Brier-30 delta was
`[-0.00007963, +0.00012577]`, spanning zero. This is a tiny and uncertain
regression, but the preregistered rule was strict improvement, not a
significance or noninferiority test.

## Diagnostics

The treatment improved several lower/central metrics:

- point MAE: `5.5986961 -> 5.5877591` (improvement `0.0109370`)
- CRPS: `3.8624910 -> 3.8575673` (improvement `0.0049238`)
- Brier-20: `0.1658319 -> 0.1655211` (improvement `0.0003108`)
- q90 pinball: `1.3930303 -> 1.3907806`

It worsened q95 and q99 pinball slightly. Walk-forward QB scale factors also
changed, showing that the treatment was not inert: control factors for
2023/24/25 were `0.965/0.905/0.925`; treatment selected
`0.975/0.910/0.915`.

## Interpretation and scope

This is the expected marginal-versus-extreme-tail pattern declared before
output. Lagged pass blown-block rate plus blocking Points Earned/play provide
some useful QB distributional information, but do not improve the registered
30-point event. The exact two-column QB-line arm is closed historically. Do
not tune its window, support, features or threshold after this result.

This result does **not** close SIS. In particular, it says nothing adverse
about player-level defender/receiver alignment or conditional competitive
allocation, which target the known teammate-dependence deficit rather than a
QB marginal. The separately frozen RB opponent run-defense Points Saved arm
also remains eligible because it uses a different source family, position and
mechanism.
