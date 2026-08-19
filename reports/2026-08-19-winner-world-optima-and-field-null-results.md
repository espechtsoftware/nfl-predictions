# N1c + N1d results: the winners are not world optima — they are excluded by our stacking rules

**Date:** 2026-08-19. One-shot executions of the frozen protocols
`20260819-winner-world-optima-v1` (report SHA `50ea349c…`) and
`20260819-field-max-null-v1` (report SHA `c37b93c3…`), both under
`reports/winner-law-audit-runs/`. Diagnostic only; licenses nothing.

## N1d — the N1 score headline is formally dead

Under our own archived law, treating every world as a contest won by the
pool argmax: at pool size (~252 candidates) the null produces only 3.33
expected beyond-p999 winners of 51 (P(>=47) ~ 4e-51), **but** the
field-size scaling closes the argument the other way. Implied effective
field size grows 18.7 → 29.1 → 43.8 → 67.5 across pool sizes 32 → 64 →
128 → 252 (effectiveness ratio 0.58 → 0.27, candidates increasingly
correlated). Reproducing the observed 47/51 requires an effective field
of ~2,544 — a raw field of roughly **9,500 rosters at the measured
ratio**, far inside any real Milly field (~150k+ entries; frozen cap
300k). Frozen verdict: **`n1_nondiagnostic_within_plausible_field`**.
A correct law WOULD produce what N1 observed. Even one `Pr=0` winner has
38% null probability at pool size alone. The surviving law-deficit
evidence at winner scale is exactly one number: the book-tail
factor-of-two (realized 6 vs expected 2.76 at 210).

Consequence for the research queue: winner-implied law calibration (the
SBI lane proposed this morning) is DOWNGRADED — the winner score series
is selection noise, not law signal; the book-tail exceedance series
remains the legitimate calibration target.

## N1c — no winner is the optimum of any world, at any depth

For each of the 51 winners, its best generating world (maximum margin
over our pool, recomputed and matched to the frozen N1b census at 1e-6)
was solved to exact optimality:

- **0/51 winners are their world's DraftKings-legal optimum; 0/51 are
  within 2 points.** Median gap below the optimum: **47.4** (quartiles
  38.5–57.2, max 77.8). Median player overlap with the optimum: **4 of
  9**. Uniform across seasons (medians 57.0 / 44.8 / 42.1).
- Winners DO reach winning scale in their best worlds (median simulated
  total 212.6) — the worlds are real winner-territory; the winners are
  simply not what the law ranks best there.

This kills the "one world past the solve horizon" narrative from the
N1b reading: solving deeper worlds — by rank, by regret, at any budget —
harvests world OPTIMA, and the winners are never the optima. Whether
those optima still capture realized tails at fixed budget is exactly
what the in-flight all-boom arm measures; its read stands as the
decisive prior for all depth-family levers, including the proposed
regret-targeted generator.

## The sharpest new fact: stacking mandates exclude 43/51 winners

Winner legality under the exact production construction contract
(QB stack >= 2, bring-back >= 1, $49k floor, same-team-RB and RB-vs-DST
bans), measured in our own snapshots:

| Rule | Winners violating |
|---|---|
| QB stack >= 2 (same-team WR/TE) | 32 of 51 |
| Bring-back >= 1 (opponent skill) | 31 of 51 |
| $49k salary floor | 0 |
| Same-team-RB ban | 0 |
| RB-vs-DST ban | 0 |

8/51 winners satisfy the full contract; 43/51 fail on stacking rules
ALONE (20 fail both, 23 one). All 51 are DK-legal in our snapshot. The
production oracle still beats every winner in its best world (median
+34; no negative gaps), so the rules never cap the SIMULATED ceiling —
but they structurally forbid 84% of the ACTUAL winning rosters. No
depth, ranking, or admission change can ever emit a roster the
constraint set excludes.

Ledger honesty: a wholesale stack-mandate deletion was tested in the
old regime and REJECTED ("true-deletion tests cost tails"). Two things
have changed: the post-ensemble/post-selection law says that verdict
does not transfer across the CBWU-era selector, and a CARVED BUDGET
(k of 40 boom solves run without stack/bring-back, floor and bans kept
— the floor excludes no winner) is a different lever from wholesale
deletion. This finding licenses nothing by itself; it motivates a
frozen, fixed-budget, exact-paired corpus arm.

## Updated queue (supersedes this morning's ordering)

1. **All-boom aggregate** (in flight) — unchanged; now also the decisive
   prior for every depth-family lever.
2. **Stack-relaxation carved-budget arm** — NEW, now ahead of
   regret-targeted generation on direct evidence (43/51 structural
   exclusion). Freeze after the all-boom read: same chain pattern,
   k relaxed solves inside the fixed budget, exact pairing, one shot.
3. **Regret-targeted generation** — motivation reframed (close
   sim-coverage holes, not "reach the winners"); gated on the all-boom
   read.
4. **Law lanes** — dependence remeasurement continues (relaunch after
   the attempt-3 lease repair); book-tail factor-of-two stays the law
   target; winner-implied SBI calibration demoted per N1d.
5. **Field model** — N1d contributes the first empirical anchor
   (required effective field ~2.5k, ratio curve by pool size); Week-1
   contest collectors remain the data gate.
