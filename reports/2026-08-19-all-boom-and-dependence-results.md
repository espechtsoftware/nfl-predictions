# All-boom reallocation and production-law dependence: two results that agree

**Date:** 2026-08-19. Two frozen one-shot arms completed within minutes of
each other. Neither licenses a production change; both are decisive within
their declared endpoints.

- All-boom: `20260819-all-boom-reallocation-c-v1`, aggregate SHA
  `503c9b04…`, 54/54 cells.
- Dependence: `20260817-production-law-dependence-remeasurement-v1`,
  report SHA in `report.sha256`, 54 slates / 5 blocks, lease released.

## 1. All-boom reallocation — C endpoint clears decisively

Replacing the entire `lev` batch with boom-family depth (N_BOOM=200,
BOOM_UNIQUE_FILL=1, CAND_MULT=0) at the **exact** registered budget:

| Endpoint | Control | Treatment | Delta |
|---|---|---|---|
| Mean pool C | 187.58 | 196.64 | **+9.06** |
| Median paired ΔC | — | — | +7.94 |
| Slates better / worse / tied | — | — | **43 / 1 / 10** |

Paired weekly-max co-primary (`20260818-paired-max-coprimary-v1`):
`p_mean_two_sided = 0.0`, `p_signed_rank_two_sided = 0.0` (Monte Carlo,
44 non-zero pairs, W+ = 961.5).

Threshold grid (slates with at least one candidate at or above the line),
control → treatment, McNemar exact two-sided:

| Line | Control | Treatment | Discordant (T-only / C-only) | p |
|---|---|---|---|---|
| 187 | 29 | 41 | 12 / 0 | 0.00049 |
| 194 | 19 | 30 | 12 / 1 | 0.0034 |
| 200 | 14 | 20 | 7 / 1 | 0.070 |
| 210 | 5 | 11 | 6 / 0 | 0.031 |
| 220 | 3 | 5 | 2 / 0 | 0.50 |
| 230 | 0 | 1 | 1 / 0 | 1.0 |
| 240 | 0 | 1 | 1 / 0 | 1.0 |

**Mechanism gate passed exactly:** across all 269 seed blocks,
`native_count == treatment_count` (mean 252.6), max |difference| = 0, max
shortfall = 0, and boom uniques = 200 in every block. Treatment family
totals: boom 53,800 / qbvar 8,580 / epi 3,228 / game 2,136 / dark 207.

### Two caveats that must travel with the number

1. **This is C, not S.** The protocol declares no selection endpoint: pool
   ceiling improving does not mean the 80-lineup book improves. The
   measured C−S gap on this corpus is ~5 points, and prior arms have
   improved pools without moving selected books. The protocol licenses an
   S follow-up *only now that C has improved*; it needs its own freeze.
2. **The union roughly doubles.** Deduplicated across the five seed books,
   control holds 550 unique lineups and treatment 1,106 (per-seed budget
   identical). The treatment converts the same budget into about twice as
   many DISTINCT lineups, because the incumbent `lev` batch is largely
   seed-invariant while boom depth at ranks 1–200 is not. Part of the C
   gain is therefore the order-statistic consequence of more distinct
   draws — which is exactly B1's "volume, not diversity" finding arriving
   through a different door. It is not a budget violation, but it means
   the honest mechanism claim is *same budget → more distinct lineups →
   higher ceiling*, and whether a selector can harvest that is untested.

## 2. Production-law dependence — the premise misses, in a specific shape

Simulated versus realized teammate co-boom rates, 54 slates, 1,194 team-weeks,
9,469 eligible player rows, zero missing outcomes; 2,000-replicate cluster
bootstrap over 54 slate clusters.

| Cell | Simulated | Realized | log(sim/real) | Classification |
|---|---|---|---|---|
| multiplicity ≥2 | 1.063 | 0.821 | +0.259 | material miss |
| multiplicity ≥3 | 2.097 | 0.997 | +0.744 | material miss |
| multiplicity ≥4 | 5.654 | 1.088 | +1.648 | material miss |
| QB–RB | 2.925 | 0.911 | +1.167 | material miss |
| QB–TE | 2.353 | 1.852 | +0.239 | inconclusive |
| **QB–WR** | **2.572** | **3.339** | **−0.261** | material miss |
| RB–RB | 2.189 | 0.494 | +1.488 | material miss |
| TE–TE | 1.609 | 0.420 | +1.343 | material miss |
| WR–WR | 1.977 | 0.991 | +0.691 | material miss |

Gate: all four conditions true (aggregate ≥3 over-coupled, aggregate QB–WR
under-coupled, each reproduced in at least three of five blocks).
Disposition **`dependence-premise-miss`** with
`production-law-shape-reproduced-ledger-prototype-licensed`;
`sparse_ledger_prototype_licensed = true`,
`exact80_scoring_licensed = false`, no production change licensed.

**Reading.** The law does not lack co-boom mass — it has too much of the
wrong kind and too little of the right kind. It piles same-team players up
together far more often than reality (five-fold at four-plus, four-fold at
RB–RB and TE–TE), while under-producing the single pairing tournaments are
actually won with: **QB→WR**. Every generic teammate coupling is
over-cooked; the stack correlation is under-cooked.

## 3. Why these two, plus the winner series, are one story

- **Anatomy C** found deep-world optima leaning on never-demonstrated
  player performances (3 per optimum, +19.3 points) versus winners' 1 and
  +5.8, and the Stage-1 census proved the marginals are not fat — so the
  defect had to be *allocation*, and was routed here.
- **Dependence** now names the allocation defect exactly: too much generic
  same-team pile-up, too little QB–WR.
- **N1c** found winners are never their world's optimum (median 47.4 below,
  4/9 overlap). That is what an over-coupled law would produce: its optima
  are implausible whole-team explosions, while real winners ride the
  QB–WR correlation the law under-generates.
- **Anatomy A** found pool-to-winner proximity at exactly chance level —
  consistent with a generator whose worlds favor the wrong co-occurrences.

Four independent audits, one coherent diagnosis. The dependence lane is
now the highest-value law target, and it has a named, measured direction
rather than "make the tails fatter".

## 4. Queue after these results

1. **Freeze an S follow-up for all-boom** (now licensed): does the 80-entry
   CBWU book improve when the pool is boom-deep, at the exact money budget?
   Add the anatomy mechanism gate (winner-overlap versus the chance null).
2. **Dependence repair design** on the measured shape: suppress generic
   teammate coupling, raise QB–WR. The sparse ledger prototype is licensed
   by this disposition; `exact80` scoring is not.
3. **Stack-relaxation arm** stays queued — note it becomes *more*
   interesting given QB–WR under-coupling, since production mandates the
   stack the law under-rewards.
4. Marginal-tail Stage 2/3 remain parked (correctly — the defect is
   dependence, not marginals).
