# CBC silent non-optimality at lexicographic coefficient scale

Date: 2026-08-23. Status: defect proven, fixed at `f032f0c`
(exact-gaps CBC flags), fix validated on every known-bad cell; no
accepted artifact is affected.

## The finding

On slate 2023-w02, CBC 2.10.x returned `Result - Optimal solution
found` for two of 7,000 (arm, world) cells while a strictly better
legal roster existed — better by **644,231 and 1,347,217 micro-points
(0.64 and 1.35 DK points) on the PRIMARY objective**, not tiebreak
noise (relative gap ~9e-7, orders above every configured tolerance).
Both values are exact integer reconstructions from decoded rosters.

Root cause: the frozen options payload CLAIMED
`gap_abs/gap_rel = 0.0`, but the actual CBC command line never passed
`allowableGap`, `ratioGap`, `increment`, or `cuts off`. At the combined
lexicographic objective's ~1e12 coefficient scale, CBC's default cut
and cutoff-increment fathoming pruned optimal nodes. With the flags
passed for real, both cells (and every historically pathological cell
across two slates, 14 probed) solve exactly, worst 1.6 s.

## Why no prior run could see it

The original uniqueness law froze `combined == claimed_optimum` and
demanded infeasibility after excluding the witness. At a WRONG claimed
optimum that proof still reads "unique" — infeasibility at the wrong
value is vacuous. Every historical corpus result produced under
radix-combined CBC objectives inherited this exposure silently. The
second-best certificate (adopted 2026-08-23) maximizes the
witness-excluded objective and compares exact integers, so a wrong
stage-1 optimum surfaces as `second-best exceeds the proven combined
optimum` — which is precisely how this was caught, at a measured rate
of ~2 per 7,000 worlds on the first slate that expressed it.

## Soundness of accepted artifacts

Every VERIFIER-ACCEPTED task (v11: 2023-w01, 2024-w11, 2024-w12)
carries the per-cell strict-gap proof on all 7,000 cells, re-proved
independently by the verifier — those optima are exact. Tasks where
CBC erred were killed by the all-optimal law before publication.
Nothing accepted is tainted; the fix only stops correct-but-fatal
task kills.

## Standing implication

Any future exact-optimum claim built on large synthetic coefficient
scales must pass explicit zero-gap/zero-increment/cuts-off flags AND
carry a second-best (or equivalent bound-independent) certificate; a
pinned-equality infeasibility proof alone cannot detect solver
non-optimality.
