# G0 final-served teammate-dependence result

The sole valid frozen G0 execution, `g0-final-served-dependence-v2-7fsx6`,
completed cleanly from source `ee94725` and immutable image digest
`sha256:e56549d12c58137d0250a1b4b93698cd5965e88d88f9c32a67b27f4bc500f76f`.
Its disposition is **`dependence-premise-miss`**, which licenses the
preregistered score-free G1 walk-forward archetype topology analysis.

The diagnostic reconstructed the terminal selected final-served distribution
for 7,848 supported active QB/RB/WR/TE player-weeks on all 54 evaluation
slates, with 10,000 draws, the selected active-only cache, fitted
`K=28.154043586960896`, and the selected walk-forward position scales. All
alignment, cache-coverage and mean-preservation invariants passed; maximum
mean drift was `7.11e-15`.

Four supported registered cells are material misses:

| Cell | Realized | Simulated | log(sim/real) | slate-bootstrap 95% interval |
|---|---:|---:|---:|---:|
| team `>=2` q90 exceeders / independence | 1.148 | 1.003 | -0.136 | [-0.266, -0.001] |
| team `>=3` q90 exceeders / independence | 1.835 | 1.013 | -0.594 | [-0.840, -0.281] |
| QB -> WR conditional lift | 3.321 | 1.053 | -1.149 | [-1.346, -0.938] |
| QB -> TE conditional lift | 2.359 | 1.048 | -0.811 | [-1.140, -0.414] |

Thus the terminal simulator materially understates both the QB/receiver hub
and the frequency of multiple same-team ceiling outcomes. The `>=4` point
estimate points in the same direction (realized 2.333 versus simulated 1.037),
but it is correctly unsupported because only seven realized events and 3.00
independence-expected events fall below the frozen minimums. QB-RB, WR-WR and
RB-RB are inconclusive; TE-TE is unsupported. Two of the three preregistered
directional predictions held (QB-WR and `>=4` underprediction); the WR-WR
direction did not, but it was not a gate input.

The prior v1 execution is not a result: it failed during schedule decoding
before loading data and emitted zero G0 result records. Its failure is retained
in the v1 run folder. The valid machine report is
`reports/g0-dependence-runs/20260812-g0-final-served-dependence-v2/report.json`.

No lineup was generated or scored in G0. The next action is to freeze and run
G1 against this same immutable terminal identity. Only G1 evidence that the
QB hub is stable across held-out seasons may license a separately frozen G2
upper-tail QB bi-factor mechanism.
