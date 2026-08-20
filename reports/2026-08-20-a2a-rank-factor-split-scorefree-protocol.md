# A2a half-residualized, one-hot QB-WR rank factor split

**Protocol ID:** `20260820-a2a-rank-factor-split-scorefree-v1`

**Status:** FROZEN before treatment output

**Scope:** outcome-free mechanism census only. This protocol cannot query
realized player scores, construct or select lineups, score a historical book,
license a shadow, or change production.

## 1. Question

Can one deterministic, exact-marginal rank transform move the simulator's
measured same-team dependence in both required directions at once:

- reduce the generic teammate/multiplicity coupling that is too high; and
- increase the specifically under-coupled QB-to-WR relationship?

This is the mechanism gate before any repaired-law historical remeasurement.
It is not itself evidence that the transformed law is closer to reality.

## 2. Frozen source

Use only the already-created outcome-free production-law source lock:

- local path:
  `reports/production-law-dependence-runs/20260817-production-law-dependence-source-lock-v1/source-lock.json`
- local/raw SHA-256:
  `7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c`
- GCS generation: `1786950155692968`
- bytes: `1341911`
- catalog SHA-256:
  `f18abb6302730f233665c06b353eb71b6997f3ced3bc91d12a9562a2815f96bc`
- grid: 54 slates × five registered blocks (`R0`–`R4`) = 270
  generation-pinned score artifacts;
- worlds: exactly 10,000 per block;
- locked catalog: 10,729 unique player-slate rows;
- eligible G0 population: exactly 9,469 QB/RB/WR/TE rows with served
  `mean_projection >= 4.0`.

The source policy is
`classic-k1-role12-boom40-poscal-cbwu-v4`: production-multinomial usage,
possession game mode, team factors on, no Dirichlet usage allocation and no TD
ledger. Every artifact URI/generation/SHA/byte count and the catalog must
revalidate before body use. The census may read only `player_ids`,
`player_draws`, and the locked score-free catalog fields needed for alignment.
It must not read candidate totals or identities for a scoring decision.

Forbidden input/query/output fields include `actual`, `actual_score`, rank,
ownership, payout, standings, winner identity, contest result, selected lineup,
and any equivalent post-lock label. The runner must contain no outcome query.

## 3. Frozen intervention

### 3.1 Eligibility and grouping

Within each block, group the exact eligible rows by
`(season, week, team)`, sorted canonically. A group is transform-eligible only
when it has exactly one eligible QB and at least two eligible WRs. Rows outside
an eligible group, the QB row inside an eligible group, and every ineligible
catalog/artifact row remain bit-exact.

Canonical WR order is ascending `(player_id, source_row_index)`. Any duplicate
player-slate key, ambiguous QB group, misaligned player universe, missing row,
nonfinite draw, noncanonical block/slate order, or non-10,000-world artifact is
terminal invalidity.

### 3.2 Stable open-unit ranks

For player row `i` and world `w`, compute the stable ordinal rank of the
control draw within that row. Ties are broken by ascending original world
index. With `W=10,000`:

```text
u_i(w) = (ordinal_rank_i(w) + 0.5) / W
```

For each eligible team-world define:

```text
g_T(w) = mean_i u_i(w)       over every eligible QB/RB/WR/TE in the group
q_T(w) = u_QB(w)
```

Select exactly one WR in every eligible team-world:

```text
a_T(w) = argmax_WR u_WR(w)
```

Ties use the canonical WR order. The one-hot count must therefore be exactly
one for every eligible group-world.

### 3.3 Fixed factor split

There is one dose and no parameter grid:

```text
generic attenuation = 0.5
one-hot QB-WR allocation = 1.0
```

For every non-QB row in an eligible group:

```text
b_i(w) = u_i(w) - 0.5 * (g_T(w) - 0.5)
```

For RB and TE, `priority_i(w) = b_i(w)`. For WR `j`:

```text
priority_j(w) = b_j(w)
                + 1[j = a_T(w)] * (q_T(w) - 0.5)
```

Stable-sort worlds by ascending priority, with original world index breaking
priority ties, and place the stable-sorted original control values into that
order. This is a permutation of the original row and must preserve its exact
sorted value multiset. No value is synthesized, widened, clipped, averaged,
or rounded.

The coefficient `0.5` is the single midpoint attenuation of the empirical
team-rank source. The coefficient `1.0` is one natural open-rank-scale unit
allocated competitively to one WR per world. Neither is fitted to the locked
2023–2025 treatment output. There is no alternate coefficient, WR identity
weight, season branch, position branch, context feature, parameter sweep, or
fallback. Failure closes this exact dose.

## 4. Score-free census estimands

Use the control row's numeric q90 as the boom threshold, with the frozen G0
strict comparison `draw > q90`. Exact marginal preservation requires the boom
count for every player to remain identical.

For the following cells, reproduce the simulated side of the registered G0
contribution law for control and treatment:

- multiplicity `>=2`, `>=3`, and `>=4` within a team-world;
- directed conditional QB-WR, QB-TE, and QB-RB lift;
- both directed orders of WR-WR, RB-RB, and TE-TE lift.

Conditional lift is retained as integer contributions
`both`, `conditioned`, `other_only`, and `not_conditioned`. Compare two lifts
by exact integer cross-multiplication of
`(both * not_conditioned) / (conditioned * other_only)`; do not decide a gate
from rounded floats. Zero denominators are invalid. Multiplicity comparisons
use exact event counts because the control/treatment group-world denominator
is identical. Floats may be emitted only as labeled diagnostics derived after
the exact decision.

## 5. Mandatory mechanism gate

All of the following must pass:

### Identity and mechanical invariants

1. Exact source-lock and complete 54×5 artifact-grid reproduction.
2. Finite deterministic output and a bit-exact repeated transform.
3. Exact sorted marginal multiset for every row in every block.
4. Exact per-row q90 boom counts and unchanged row/world budgets.
5. QB and all ineligible/unsupported rows bit-exact.
6. At least one eligible row and one world cell change; every eligible
   group-world has exactly one selected WR.

### Directional mechanism conditions

1. Aggregate simulated QB-WR conditional lift is strictly greater than
   control, and it is strictly greater in at least three of five blocks.
2. Aggregate simulated multiplicity `>=3` event count is strictly less than
   control, and it is strictly less in at least three of five blocks.
3. Aggregate multiplicity `>=2` and `>=4`, QB-RB, QB-TE, WR-WR, RB-RB, and
   TE-TE must each be no greater than control under their exact integer
   comparison.

There is no realized equivalence-band claim at this stage. A transform can
pass this census and still be too weak, too strong, or wrong relative to real
football; that is what the separately frozen remeasurement must decide.

## 6. Execution sequence

1. Unit/synthetic validation may exercise the fixed formula but may not use a
   real frozen artifact before this protocol is committed.
2. Run one outcome-blind real-artifact smoke on `2023-W1/R0`. It must validate
   the exact source/object identity, transform one slate, serialize the
   score-free receipt, and execute no outcome or lineup path.
3. If and only if the smoke is strict-green, run the complete 270-artifact
   score-free census once and create one canonical result.
4. Any scientific gate failure closes this dose with no coefficient, formula,
   support, or block-count repair. A transport defect may be repaired only
   without changing these scientific bytes and without accepting a partial
   treatment result.

This lane does not need or acquire the historical-outcome lease. It must still
remain serialized with other heavy use of the reused research job and must be
visible in `scripts/chain_status.sh`.

## 7. Dispositions and licenses

- All source/mechanical/directional conditions pass:
  `a2a-scorefree-mechanism-passes`. This licenses only preparation of one
  separately frozen outcome-bearing dependence remeasurement.
- Source, identity, support, finiteness, marginal, determinism, or receipt
  failure: `a2a-scorefree-invalid`. No inference and no retry under changed
  science.
- Valid mechanics but any directional condition fails:
  `a2a-scorefree-mechanism-fails`. Close this dose; no parameter sweep.

Every receipt must carry literal false values for:

```text
uses_realized_outcomes
actual_outcomes_queried
candidate_or_lineup_scores_read
historical_remeasurement_licensed       # true only in the final passing result
exact80_scoring_licensed
single_stack_arm_licensed
prospective_shadow_licensed
production_change_licensed
```

The final passing census may set only
`historical_remeasurement_licensed=true`; every other license remains false.
Even a later historical law-shape pass can only license the next frozen
research arm. Production construction cannot change without an unseen 2026
prospective shadow that passes its registered score endpoint and protected
guards.

## 8. Relationship to the winner-structure work

This transform is not fitted to reproduce the observed winner frequencies.
Its sparse one-hot QB-WR source is motivated by the measured combination of
under-coupled QB-WR and over-coupled WR-WR/high multiplicity, while the later
`SINGLE_STACK_BOOM_SOLVES` arm tests the distinct roster-construction question.

The order is strict:

```text
A2a score-free census
  -> frozen outcome-bearing A2a remeasurement, only on a census pass
  -> exact-one construction arm, only on a law-shape pass
  -> unseen prospective shadow, only on a historical score pass
  -> production consideration
```

Bring-back/game dependence, ownership/duplication, max-game spread, residual
world generation, and A7 v2 are not part of this protocol.
