# TD-ledger rank-coupling terminal result

## Disposition

`td-ledger-rank-coupling-invalid-or-inconclusive`

The immutable Cloud Run execution
`td-ledger-rank-coupling-v1-d9zdr` completed successfully in 22m25.91s from
full code SHA `934d2c3d0e55312502da83964a6f16e806b8d231` and image digest
`sha256:b9c0480571b2941b6074d78cb577762d9c1658de2dbb70490169be7a8cb0ce88`.
The harvested report SHA-256 is
`6342eab48c2a3b7f417f60d18a2c58111388b03a60a7917e4ad5fee3c833c0c1`.

The conditional exact-80 license is false. The frozen exact-80 addendum
expires without generating, selecting or scoring a TD rank-coupled lineup.
The protocol explicitly permits no fourth repair on these outcomes.

## What passed

The mechanism-local rank permutation behaved exactly as designed:

- every treatment row retained the bit-exact sorted control multiset;
- the independently repeated TD rank source reproduced bit-for-bit;
- all output was finite;
- maximum float64 player-mean drift was `7.105427357601002e-15`;
- 15,396 eligible rows and 137,300,516 world cells changed; and
- player/frame alignment had no failure.

This closes the earlier marginal-identity and repeated-rank implementation
questions. They were not the terminal blocker.

## Terminal blocker

The unchanged control failed the frozen absolute `1e-12` G0/G1 reproduction
gate in 48 registered values: all nine G0 simulated estimates and each of the
13 G1 relationships' simulated lift, joint-q90 Brier and variogram. The
differences were substantive rather than rounding noise. Examples:

| metric | current control | frozen reference | delta |
|---|---:|---:|---:|
| G0 multiplicity >=4 simulated estimate | 6.175472 | 1.037070 | +5.138402 |
| G0 QB-RB simulated estimate | 2.597475 | 1.056682 | +1.540794 |
| G1 QB-RB simulated lift | 2.607059 | 1.075206 | +1.531853 |
| G0 multiplicity >=3 simulated estimate | 2.376971 | 1.012924 | +1.364047 |
| G1 QB-WR simulated lift | 2.418253 | 1.064435 | +1.353817 |

The strongest code-history explanation is the intervening point-in-time
repair `26e73c5` (`Repair season replay usage allocation units`). The frozen
G0 and G1 references were created on 2026-08-12 from `ee94725` and `64e0428`.
The 2026-08-13 repair changed finite-Dirichlet season replay from one
franchise-wide season pool to the correct `(game, team)` allocation unit.
The terminal execution used that repaired current path. That change is
expected to materially alter within-game dependence while leaving the
manifest's cache, K and schedule labels unchanged, which matches the observed
large dependence shifts. This is a forensic attribution, not a license to
rewrite the frozen gate.

On the current repaired path the treatment also had a slightly lower joint
q90 Brier (`0.0183805` versus `0.0183974`) but a higher/worse variogram
(`1.424769` versus `1.422472`) and higher G0/G1 error sums. Those values are
diagnostic only because the control invariant failed; they cannot rescue or
scientifically adjudicate the arm.

## Consequence

TD-ledger and its rank-coupling repair are closed as unadjudicated on the
historical panel. No TD exact-80 run, production change, K=1 transfer or
composition is permitted. The stale-reference finding must enter the final
forensic code/evidence chronology so earlier G0/G1-dependent conclusions are
not presented as current-path validations.

The next frozen mechanism is the adaptive SIS RB opponent run-defense
Boom%/Bust% marginal arm. Its exact source commit is `23fdbba47590af3ba7594ae22bdbf2e764d86389`.
