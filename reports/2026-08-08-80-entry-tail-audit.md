# 80-entry tail and missed-winner audit

Date: 2026-08-08

## Decision context

The operator clarified before this analysis that the realized weekly maximum
from the submitted portfolio matters much more than average lineup score, and
that 80 entries are more likely than 40. Accordingly, this audit reports the
entire realized-tail grid and treats mean weekly maximum only as a diagnostic.
It does not use average entry score as the optimization target.

No new candidates or simulations were generated for the first stage. The
production selector was reapplied to the immutable candidate/world masks from:

- accepted K=3 control `20260808-deterministic-baseline-c616390`;
- staging K=1 arm `20260808-a02-ensemble1-c616390`.

The reconstructed K=3 and K=1 40-entry portfolios each had **zero mismatches**
from the persisted production selections. This proves that the same selector,
candidate ordering, masks, probability tiebreak, and mean tiebreak were used.

## Frozen-pool result

All rows below select on the persisted 194-point support mask. `N=80` means 80
lineups selected from the candidate pool generated for the original 40-entry
replay.

| worlds | entries | >=187 | >=194 | >=200 | >=210 | >=220 | mean weekly max | mean pool regret |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| K=3 | 40 | 26 | 11 | 1 | 1 | 1 | 173.06 | 4.65 |
| K=3 | 80 | 29 | 18 | 7 | 3 | 1 | 176.35 | 1.37 |
| K=1 | 40 | 26 | 16 | 9 | 5 | 2 | 174.55 | 5.91 |
| K=1 | 80 | **35** | **22** | **15** | **9** | **2** | **179.27** | **1.18** |

K=1's 80-entry book beats K=3 at every measured realized threshold from 187
through 220. The most decision-relevant separation is **15 versus 7 weeks at
200** and **9 versus 3 at 210**.

### Selection-line sensitivity at 80 entries

Every selection target was scored at every outcome threshold; the target was
not judged only at the line it optimized.

| worlds | selection line | >=187 | >=194 | >=200 | >=210 | >=220 | mean weekly max |
|---|---:|---:|---:|---:|---:|---:|---:|
| K=3 | 187 | 27 | 18 | 7 | 3 | 1 | 176.30 |
| K=3 | 194 | 29 | 18 | 7 | 3 | 1 | 176.35 |
| K=3 | 200 | 32 | 18 | 7 | 3 | 1 | 176.31 |
| K=1 | 187 | 35 | 21 | 13 | 7 | 2 | 178.81 |
| K=1 | 194 | 35 | **22** | **15** | **9** | 2 | **179.27** |
| K=1 | 200 | 35 | **22** | **15** | 7 | 2 | 178.93 |

The incumbent 194 selection target is not a post-hoc beneficiary. It ties the
best K=3 high-tail result and is the best or tied-best K=1 target from 194
through 210.

### Season distribution at 80 entries, selection line 194

| season | K3 >=194 | K1 >=194 | delta | K3 >=200 | K1 >=200 | delta |
|---|---:|---:|---:|---:|---:|---:|
| 2019 | 6 | 7 | +1 | 3 | 6 | +3 |
| 2021 | 4 | 2 | -2 | 2 | 2 | 0 |
| 2022 | 1 | 4 | +3 | 1 | 3 | +2 |
| 2023 | 1 | 4 | +3 | 1 | 1 | 0 |
| 2024 | 3 | 2 | -1 | 0 | 1 | +1 |
| 2025 | 3 | 3 | 0 | 0 | 2 | +2 |

At 194, K=1 retains the earlier instability pattern: three positive and two
negative seasons. At 200—the higher-score objective specified by the operator
before the frozen 80 result was computed—K=1 is positive in four seasons,
negative in none, and neutral in two. This is much better discovery evidence,
but it is not yet an adoption because a production-faithful 80-entry replay
generates a larger candidate pool.

## High scores left outside the portfolio

The accepted K=3 pool contains a 194-point lineup in 20 weeks. Its 40-entry
book captured 11 and missed nine; frozen selection of 80 captured 18 and left
two. At 200, it moved from 1 of 8 pool opportunities at 40 entries to 7 of 8
at 80.

The K=1 pool contains a 194-point lineup in 24 weeks. Its 40-entry book
captured 16 and missed eight; frozen selection of 80 captured 22 and left two.
At 200, it moved from 9 of 16 pool opportunities at 40 entries to 15 of 16 at
80.

There were eight K=3 candidates scoring at least 200 outside its 80-entry
book, spread over four slates, but only one was consequential: the other
slates already had a different selected lineup over 200. K=1 had nine such
candidates across seven slates, likewise with only one consequential miss.
Raw counts of high unselected candidates therefore overstate the remaining
weekly opportunity; distinct missed weeks are the correct unit.

### Consequential K=3 miss: 2023 week 3

- Selected maximum 184.86; candidate-pool oracle 208.56.
- The oracle was `qbvar`, ranked 144/159 by simulated `P(>=194)`, 147/159 by
  simulated mean, and 136/159 by simulated q99. It was genuinely buried by
  the K=3 beliefs.
- The oracle's decisive swap was the LAC stack led by Keenan Allen (48.46
  actual versus 17.85 expected, a +30.61 surprise) and Justin Herbert. The
  selected best used a MIA stack led by Tyreek Hill and Tua Tagovailoa.
- One selected candidate could be exchanged for this oracle without reducing
  final simulated-world coverage, but its pre-lock ranks supplied no reason
  to identify this particular hindsight winner. This was not a rare greedy
  defect: 32 of the 79 unselected candidates on the slate had some
  non-worsening one-for-one coverage swap.
- Inside that 32-candidate free-swap frontier, the oracle still ranked only
  25th by `P(>=194)`, 30th by simulated mean, and 26th by q99; it was the only
  member that happened to realize 200. A deterministic pre-lock one-swap hill
  climb improved simulated coverage 1,795→1,797 worlds in four swaps but
  still excluded the oracle and left the realized best at 184.86.

### Consequential K=1 miss: 2019 week 6

- Selected maximum 190.50; candidate-pool oracle 204.44.
- The oracle was `lev`, ranked 53/161 by `P(>=194)`, 58/161 by simulated mean,
  and 54/161 by simulated q99. Unlike the K=3 miss, it was not deeply buried.
- It used an ATL/NYJ construction led by Matt Ryan, Austin Hooper, Julio Jones,
  Robbie Chosen, and Jamison Crowder. The selected best used a SEA stack led
  by Russell Wilson and Chris Carson; both game theses realized well, but the
  ATL/NYJ combination won by 13.94.
- Swapping the hindsight oracle for one selected lineup could preserve the
  same final simulated-world coverage. But 24 of 81 unselected candidates on
  the slate also had a non-worsening swap, so the oracle was one of many
  coverage-equivalent alternatives. This exposes a non-unique frontier at 80
  entries, not a learnable hindsight rule or evidence that exact maximum
  coverage would choose the winner. Any new selector must still use only
  pre-lock information and requires independent confirmation under the
  project's standing validation law.
- The oracle was more plausible inside this free frontier—4th of 24 by both
  `P(>=194)` and q99, and 10th by mean—but it was still the only member to
  realize 200. A deterministic lexicographic hill climb using only covered
  worlds, summed `P(>=194)`, and summed simulated mean improved coverage
  3,595→3,598 worlds in three swaps, yet selected other candidates, omitted
  the oracle, and left the realized best at 190.50. Thus even the most direct
  non-hindsight local repair suggested by this miss does not recover it.

The other 80-entry miss at 194 is 2021 week 18 (oracle 194.12). It appears in
both K=3 and K=1, is not a 200-point outcome, and costs three simulated
coverage worlds in its best one-for-one swap. It is not a priority relative
to the true high-tail miss.

## Critical limitation: frozen 80 is a lower-bound diagnostic

Replay calls the leverage optimizer for `CAND_MULT * n_entries` lineups.
Consequently, a true 80-entry run produces 160 initial leverage candidates,
while these immutable 40-entry panels produced 80. Boom/game/dark budgets are
otherwise unchanged. Selecting 80 from the old pool is paired and exact, but
it is not the candidate universe the application will produce for 80 entries.

## Primary-research implications

The weekly-maximum objective is supported by the relevant optimization
literature. Hunter, Vielma, and Zaman formulate top-heavy DFS portfolio choice
as maximizing the probability that at least one entry wins, emphasize the
tradeoff between individual win probability and inter-lineup correlation, and
show why greedy maximum coverage is a principled approximation. That is close
to the current correlated-world coverage selector, so the clarified objective
does **not** justify replacing coverage with average lineup score. Source:
[Picking Winners in Daily Fantasy Sports Using Integer Programming](https://arxiv.org/abs/1604.01455).

Haugh and Singal go one economic step further: a risk-neutral top-heavy DFS
objective is expected reward against an explicit model of opponents' lineup
choices, including a multiple-entry algorithm motivated by submodularity.
This means fixed score thresholds remain only a proxy for dollars. Real
classic standings, payout curves, field ownership, and duplication behavior
are required before expected profit can honestly replace the score-tail grid.
Source: [How to Play Fantasy Sports Strategically (and Win)](https://pubsonline.informs.org/doi/abs/10.1287/mnsc.2019.3528).

The K=1/K=3 result also suggests a distinct future simulator arm. The deep
ensemble formulation treats regression output as a uniformly weighted
**mixture of predictive distributions**, not merely one averaged point
prediction. The current K=3 path averages member point predictions before
downstream marginal shaping, which may suppress useful between-model joint
tail beliefs even though it is sensible for central accuracy. A future arm
should draw a coherent ensemble member per simulation world (then apply the
same calibrated aleatoric layer), instead of choosing K=1 globally or
averaging all members into every world. This is an inference from the source,
not a claimed result of that paper. Sources:
[Simple and Scalable Predictive Uncertainty Estimation Using Deep Ensembles](https://proceedings.neurips.cc/paper_files/paper/2017/hash/9ef2ed4b7fd2c810847ffa5fa85bce38-Abstract.html)
and [Ensemble Sampling](https://proceedings.neurips.cc/paper/2017/hash/49ad23d1ec9fa4bd8d77d02681df5cfa-Abstract.html).

The immediate 80-entry K=3/K=1 pair remains first because it requires no new
simulator design. Member-sampled worlds are a separately preregistered,
same-image arm only after that pair establishes the production-faithful
frontier.

The off-by-default mechanism plumbing is now implemented but has not been
launched. `ENSEMBLE_WORLD_MODE=member_sample` assigns one of the three fitted
members to each world with balanced deterministic seed
`ENSEMBLE_WORLD_SEED=8161`, then adds that member's centered point-belief
delta coherently to every player in the world *before* the existing
TabPFN/empirical rank shaper. The shaper restores each player's frozen
marginal values, retaining only the changed joint-world ordering. The mode is
research-only, requires the draw-returning replay path, rejects K=1, records
its mode/seed in candidate provenance, and leaves the default averaged path
unchanged. Focused replay, persistence, deterministic-assignment, SBI, and
live-smoke tests pass; the full local suite also passes. A new experiment still
requires a written same-image protocol after the running 80-entry result—not
retrospective activation of this switch.

The next experiment is therefore a same-image, production-faithful 80-entry
pair on immutable generation digest
`sha256:98a31edd1921660df6c4f0c9d606e0096ea703ffe250ccc650af706e06798fd6`:

1. K=3 control, `--entries 80`, 45/55 blend, $49k floor, possession mode,
   `N_CE/N_EPISTEMIC/N_GUMBEL/N_BOOM=0/0/0/40`.
2. Same configuration and image with only `MODEL_ENSEMBLE=1` changed.
3. Six corrected seasons and 107 Sunday-main slates; full acceptance,
   immutable artifacts, mechanism audit, and same-image provenance.
4. Keep selection line 194. Report the predeclared realized grid at
   187/194/200/210/220/230/240.
5. Primary high-tail gate: aggregate >=200 lift of at least two weeks,
   positive in at least four seasons, negative in at most one. Require >=210
   not to worsen, >=194 aggregate not to worsen, pool-oracle >=200 not to
   worsen, valid mechanism, and mean weekly max not to regress by more than
   2.0 points. The old 194 stability result is still reported and is not
   erased.
6. Do not tune the selection line, K, generator quotas, or candidate multiple
   after seeing this pair. Candidate-budget scaling is a separate future arm.

### Preregistered cross-model portfolio mix

Before querying any realized scores from the running true-80 panels, a second
diagnostic was frozen around the operator's actual decision: how to allocate
80 entries. Model averaging is not the only way to use K=1 and K=3; their
errors may be complementary enough that two smaller books have a better
weekly maximum than one homogeneous book.

After both panels pass acceptance, reapply each panel's unchanged 194-point
coverage selector to its own production-faithful candidate/world pool and
report the complete K=1/K=3 allocation grid **0/80, 20/60, 40/40, 60/20,
80/0**. For every allocation, score the realized weekly maximum at
187/194/200/210/220/230/240 and by season. The primary mixed-book hypothesis
is 40/40, declared before outcomes; the other three non-endpoint allocations
are sensitivity analysis, not a menu from which to pick the historical
winner.

The comparison is the stronger of the two homogeneous 80-entry endpoints,
defined first by >=200 count, then >=210, >=194, and mean weekly maximum as
fixed tiebreakers.
The 40/40 mix must add at least two >=200 weeks, improve at least four seasons
with no more than one negative season at >=200, and not worsen aggregate
>=194, aggregate >=210, pool-oracle >=200, or mean weekly maximum by more than
2.0 points. Duplicate rosters across the two model books must be counted and
reported. They remain in the historical maximum calculation (a duplicate
cannot create a false higher maximum), making the result a conservative
lower bound on a live implementation that backfills duplicates. A passing
diagnostic motivates that deterministic backfill/joint-book implementation;
it does not silently change the current live selector.

Runner, acceptance, and comparator interfaces now accept an explicit entry
count while retaining 40 as the default. Tests cover 80-entry panel
validation and the frozen selector diagnostics.

## Production-faithful 80-entry result

Both preregistered panels completed all 107 slates on generation digest
`sha256:98a31edd...`: K=3 `20260808-e80-k3-c616390` persisted 25,813
candidates and K=1 `20260808-e80-k1-c616390` persisted 25,787. Every slate
selected exactly 80 entries. Acceptance executions
`accept-replay-panel-vlw7c` / `accept-replay-panel-cjct8` passed with zero
missing player joins, zero duplicate feature keys, complete score artifacts,
and candidate/player mean errors below `2.36e-05`. K=3 was promoted only
after the independent second audit `accept-replay-panel-d6fbn`.

### Realized tail grid

| worlds | selection line | >=187 | >=194 | >=200 | >=210 | >=220 | >=230 | >=240 | mean weekly max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| K=3 | 187 | 27 | 19 | 8 | 4 | 1 | 1 | 1 | 176.84 |
| K=3 | **194** | **29** | **19** | **8** | **5** | **1** | **1** | **1** | **177.08** |
| K=3 | 200 | 30 | 19 | 7 | 4 | 1 | 1 | 0 | 176.44 |
| K=1 | 187 | 37 | 22 | 14 | 8 | 3 | 1 | 1 | 179.88 |
| K=1 | **194** | **36** | **22** | **12** | **6** | **3** | **1** | **1** | **179.60** |
| K=1 | 200 | 36 | 22 | 15 | 6 | 3 | 1 | 1 | 179.29 |

The frozen lower-bound result direction survived but its size shrank: at the
preregistered selection line, K=1 beat K=3 **12→8 at 200**, not 15→7. K=1
also improved 29→36 at 187, 19→22 at 194, 5→6 at 210, 1→3 at 220, and mean
weekly maximum by 2.52 points. The complete week-level maxima and both pool
oracles are in `reports/2026-08-08-true80-weekly-max.csv`.

### K=1 gate: aggregate win, stability failure

Official comparator `compare-adoption-panel-x9tsz` ran on reporting digest
`sha256:458dd21d9074a1a3a35222c5b3aa67c4e331b4ee2e3ea62768c7870ef52fe4a1`
after Cloud Build `1520f9b3-9f76-47bc-ba15-47f4d621c22b` passed 636 tests.
The ensemble mechanism audit had zero failures: all 47,692 offensive rows
recorded K=3 member disagreement, immutable inputs matched, non-ensemble
seeds matched, K=1 moved 0.281 points from the K=3 member mean on average,
and post-shaping marginal means were invariant.

| season | K3 >=194 | K1 >=194 | delta | K3 >=200 | K1 >=200 | delta |
|---|---:|---:|---:|---:|---:|---:|
| 2019 | 5 | 6 | +1 | 2 | 5 | +3 |
| 2021 | 5 | 2 | -3 | 2 | 1 | -1 |
| 2022 | 1 | 4 | +3 | 1 | 3 | +2 |
| 2023 | 2 | 4 | +2 | 2 | 1 | -1 |
| 2024 | 3 | 2 | -1 | 1 | 1 | 0 |
| 2025 | 3 | 4 | +1 | 0 | 1 | +1 |

At 200, K=1 has only three positive seasons and two negative seasons. At 194
it has four positive but still two negative. It passes every aggregate,
oracle, mean, and mechanism safeguard but fails the standing distribution
law at both thresholds. The disposition remains **unsupported-neutral**;
K=3 stays the validated incumbent. The rule is not weakened after seeing the
result.

Selection-line sensitivity is useful but not an adoption loophole. Selecting
K=1 at 200 would have captured 15 high weeks, yet its >=200 season delta
against the preregistered K=3 control is `{2019:+3, 2021:0, 2022:+2,
2023:0, 2024:0, 2025:+2}`—only three positive seasons. This target was also
not the declared production choice. It is a prospective hypothesis, not a
retrospective switch.

### Cross-model allocation result

| K1/K3 entries | >=187 | >=194 | >=200 | >=210 | >=220 | mean weekly max | duplicate roster slots |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0/80 | 29 | 19 | 8 | 5 | 1 | 177.08 | 0 |
| 20/60 | 32 | 22 | 12 | 7 | 3 | 178.51 | 283 |
| **40/40** | **34** | **23** | **9** | **5** | **3** | **179.30** | **392** |
| 60/20 | 34 | 25 | 11 | 6 | 3 | 179.61 | 248 |
| 80/0 | 36 | 22 | 12 | 6 | 3 | 179.60 | 0 |

The primary 40/40 allocation fails: it loses three >=200 weeks to K=1 and is
negative in 2019, 2022, and 2023. The 20/60 sensitivity ties K=1 at 12 weeks
and improves 6→7 at 210, but it was not the primary allocation and improves
only three seasons versus K=3. It cannot be selected as the historical winner
after the fact. Cross-book overlap is also substantial: the 40/40 book has
392 duplicate roster slots across 96 slates (maximum 12 on one slate), so a
future joint implementation would require deterministic backfill.

### High scores still outside the true-80 books

The larger production-faithful pools create more opportunity than the frozen
diagnostic. K=3's pool has 12 weeks >=200 and selects 8, leaving four
recoverable weeks: **2019w9 216.42**, **2025w12 214.36**, **2021w11 205.20**,
and **2019w6 204.44**. Their simulated probability ranks are respectively
185/232, 53/237, 150/238, and 67/242. Every best oracle swap costs at least
one covered world, and outcome-blind one-swap refinement still misses all
four.

K=1's pool has 19 weeks >=200 and selects 12, leaving seven recoverable
weeks: **2021w4 215.38**, **2025w12 214.36**, **2019w6 204.44**,
**2023w16 202.74**, **2025w9 202.50**, **2019w10 201.14**, and
**2019w15 200.36**. Only 2025w12 offers a coverage-improving oracle swap and
2019w15 a coverage-neutral swap. Even there, deterministic local refinement
chooses other pre-lock improvements and leaves the realized maxima at 199.06
and 190.36. Across all seven misses, the local repair recovers **zero**
winners. The problem is not an obvious greedy bug; the changed simulator
beliefs and candidate ranking remain the appropriate research target.

## Next preregistered arm: coherent member-sampled worlds

Because K=1 did not earn adoption, the accepted K=3 configuration remains the
control. The next experiment is frozen before launch on same-image generation
digest
`sha256:458dd21d9074a1a3a35222c5b3aa67c4e331b4ee2e3ea62768c7870ef52fe4a1`
(code `d99b125`):

1. Control `20260808-e80-msctl-d99b125`: K=3 averaged model belief, true 80
   entries, 194 selection line, 45/55 blend, $49k floor, possession mode, and
   `0/0/0/40` generation budget.
2. Treatment `20260808-e80-msarm-d99b125`: identical, changing only
   `ENSEMBLE_WORLD_MODE=member_sample` with fixed seed 8161.
3. One coherent fitted member is assigned to each simulation world before the
   existing rank shaper. Player marginal values must remain byte-identical;
   only joint world ordering may change. The mechanism gate requires K=3 and
   member identities on both arms, identical non-world seeds and feature
   snapshots, candidate/player mean parity, changed support/candidate
   portfolios, and changed selected rosters.
4. Apply the same primary >=200 law: aggregate lift >=2, at least four
   positive and at most one negative season, with non-worsening 194, 210,
   pool-oracle 200, no more than 2.0 mean-max regression, and a valid
   mechanism/panel.
5. Report 187/194/200/210/220/230/240. Do not change K, selection line,
   allocation, member seed, or candidate budgets after the result.

Both one-week preflights passed before season launch: control
`replay-e80msc-smoke-mzzgb` and treatment `replay-e80msm-smoke-ns5pj`.
Treatment logs mechanically confirmed seed 8161 assigned the 10,000 worlds
`[3334, 3333, 3333]` across members before marginal shaping. The six control
executions are `replay-e80msc-2019-7p54c`, `...-2021-jqlxm`,
`...-2022-l95kh`, `...-2023-8svsn`, `...-2024-7w6bz`, and
`...-2025-k2tdn`; treatment executions are `replay-e80msm-2019-t4m94`,
`...-2021-cs8sk`, `...-2022-g6hjm`, `...-2023-hwd4q`,
`...-2024-nfmlg`, and `...-2025-c4gnw`.

The acceptance/comparison image is independently pinned: Cloud Build
`b9c6fb26-6a7d-4e40-bd49-4863fc0d2a99` passed 638 tests (2 skipped) and
produced reporting digest
`sha256:29bb404d84e1a6d8d27d94f4204ffa6fbac7d97dab164c54069c4a4a9ec02dea`.
