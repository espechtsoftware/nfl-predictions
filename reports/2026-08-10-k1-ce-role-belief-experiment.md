# K=1 CE role-belief candidate experiment

Preregistered 2026-08-10 before either treatment panel was launched or any
treatment outcome was inspected.

## Decision context

The accepted source is `20260809-e80-k1-ce12-c616390`: true 80 entries,
K=1, line 194, $49,000 minimum salary, 45/55 model/market blend, possession
simulation, seed 1701, and the fixed 12 CE / 28 boom generator budget. Its
selected weekly maxima clear 187/194/200/210/220/230/240 on
40/26/18/11/5/2/1 of 107 slates. The corresponding pool oracle is
47/32/22/13/5/2/1.

The accepted pool misses part of the real tournament-winning roster on 28 of
68 matched Millionaire slates. The 36 missing roster slots are concentrated
at WR (12), TE (11), and RB (7), and average 21.11 actual points against 7.82
projected. The pool also contains an unselected weekly maximum on 25 of 107
slates, although only four nonredundant unselected oracles clear 200. This
means both rare player beliefs and portfolio selection matter, but the fixed
pool has too few recoverable 200-point weeks to justify another flexible
reranker search on these same outcomes.

## Why this mechanism is eligible

This is not a new feature sweep. The exact alternate role model and its exact
six inputs were frozen before the current accepted panel existed:

`target_share_last,carry_share_last,snap_share_last,target_share_jump,carry_share_jump,snap_share_jump`

It creates four alternate-role mean candidates and eight high-total
alternate-role-world candidates, then evaluates every roster under the
unchanged baseline worlds. Its only earlier full panel,
`20260807-role-belief-v1-7976636-*`, was invalidated before scoring because it
inherited an incomplete DST universe and reduced both realized pools below
their source. It therefore never received a valid current-universe score
verdict.

Two outcome-independent diagnostics now justify one corrected test:

- Same-slate, same-position matched controls on the accepted point-in-time
  snapshots show `fast_role_rise` players add 2.19 mean DK points and 3.79
  percentage points of 20+ tail probability across 5,540 pairs. The tail
  lift is positive in all six seasons. `vacancy_or_promotion` adds 1.38 mean
  points and 1.92 tail points across 8,490 pairs, also with positive mean and
  tail lift in every season.
- Walk-forward TabPFN calibration is already close to correct for these
  states: fast-role players exceed q90/q99 9.76%/1.06% of the time and
  vacancy/promotion players 9.03%/1.20%, while ordinary players do so only
  7.37%/0.72%. This argues against a generic variance multiplier. The
  bounded candidate generator is the cleaner way to translate alternative
  role beliefs into roster diversity.

The matched-control and calibration results are mechanism diagnostics only.
They do not choose a feature subset, seed, dose, salary band, or threshold.
Those remain exactly the pre-existing frozen values.

## Frozen arms

All arms use immutable generation image
`sha256:98a31edd1921660df6c4f0c9d606e0096ea703ffe250ccc650af706e06798fd6`
and embedded code `c616390` so the source and treatments share the same
projection, simulation, CE, optimizer, and persistence implementation.

| Arm | Panel | Generator allocation | Purpose |
|---|---|---|---|
| Accepted source | `20260809-e80-k1-ce12-c616390` | CE 12 / role 0 / boom 28 | incumbent |
| Union diagnostic | `20260810-e80-k1-ce12-roleunion-c616390` | CE 12 / role 12 / boom 28 | prove novel role candidates add 200+ opportunities |
| Fixed treatment | `20260810-e80-k1-ce12-role12-c616390` | CE 12 / role 12 / boom 16 | equal 40-solve adoptable comparison |

The union arm is not adoptable because it adds 12 solves. The fixed arm may
launch only after the machine-readable union gate passes. It uses the exact
accepted source pool size for every slate and protects the 12 CE plus 12 role
replacement candidates during deterministic trimming.

## Frozen gates

Both comparisons must first pass mechanical validity: 107 aligned slates,
exactly 80 selected lineups per slate, one immutable code/config/seed identity,
point-in-time player-feature invariance, exact baseline-world scores on common
rosters, the exact role feature list and seed 7331, 12 retained role candidates
on every slate, and no unrelated lever drift. The union must retain every
source roster. The fixed treatment must match every source pool size and must
preserve all source CE candidates.

The union gate passes only if role-tagged candidates themselves create at
least two new 200-point pool-oracle weeks relative to the source. Overall
union gains from uncapped incumbent candidates do not count.

The fixed treatment passes only if all of the following are true:

- selected 200-point weeks improve by at least two;
- selected 210/220/230/240-point counts are each nonworse;
- pool-oracle 200/210/220/230/240-point counts are each nonworse; and
- at least one novel role candidate reaches the realized slate frontier and
  role candidates enter at least one selected portfolio.

Counts at 187 and 194, mean/median weekly maximum, and individual-season
signs are reported but are not vetoes. This matches the operator's stated
preference for the best weekly lineup over average score or uniform
season-level stability. There is no parameter retry after a rejection.

## Execution status

Preregistration commit `c02cded` was pushed before launch. The union's 2022
one-week preflight `replay-e80k1ru-smoke-l4fjb` passed on the frozen generation
digest. The six immutable season executions are
`replay-e80k1ru-2019-kn4jf`, `replay-e80k1ru-2021-6sj8b`,
`replay-e80k1ru-2022-6n9gr`, `replay-e80k1ru-2023-t5r9v`,
`replay-e80k1ru-2024-zg8lx`, and `replay-e80k1ru-2025-wtsxz`.
No partial union score may be inspected. Full comparator validation build
`35ec292e-94ea-48b2-8597-23292b77dbd3` is running independently.

## Additional data path, separate from this test

The Odds API officially offers historical player props from May 2023 and
markets such as passing/rushing attempts, completions, touchdowns, and
yardage combinations. Those can proxy expected opportunity and role, but a
nine-market historical backfill would consume most of the current quota.
No historical API credits are spent by this experiment. A later, separately
approved pilot should start with a small volume/role market set and a fixed
credit ceiling. Route share, target share, alignment, and coverage fields
from the Fantasy Points Data Suite are the higher-priority paid-data trial
because they address the observed WR/TE generation misses more directly.
