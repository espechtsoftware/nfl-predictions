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
  to identify this particular hindsight winner.

### Consequential K=1 miss: 2019 week 6

- Selected maximum 190.50; candidate-pool oracle 204.44.
- The oracle was `lev`, ranked 53/161 by `P(>=194)`, 58/161 by simulated mean,
  and 54/161 by simulated q99. Unlike the K=3 miss, it was not deeply buried.
- It used an ATL/NYJ construction led by Matt Ryan, Austin Hooper, Julio Jones,
  Robbie Chosen, and Jamison Crowder. The selected best used a SEA stack led
  by Russell Wilson and Chris Carson; both game theses realized well, but the
  ATL/NYJ combination won by 13.94.
- Swapping the hindsight oracle for one selected lineup could preserve the
  same final simulated-world coverage. This exposes a non-unique/greedy
  selector frontier at 80 entries, not a learnable hindsight rule. Any new
  selector must still use only pre-lock information and requires independent
  confirmation under the project's standing validation law.

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

Runner, acceptance, and comparator interfaces now accept an explicit entry
count while retaining 40 as the default. Tests cover 80-entry panel
validation and the frozen selector diagnostics.
