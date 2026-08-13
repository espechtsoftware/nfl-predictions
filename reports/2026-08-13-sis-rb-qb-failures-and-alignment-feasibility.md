# SIS RB/QB failures, and a free answer to the alignment-feasibility question

Date: 2026-08-13. **No code was changed.** The measurement in §3 reads local
licensed Fantasy Points files and reports only aggregate summary statistics.

---

## 1. Both SIS marginal arms failed, as predeclared

| arm | mean-side | tail/distribution side |
|---|---|---|
| **SIS QB line** (pass blown-block rate + blocking PE/play) | Brier-20 `0.1658319 → 0.1655211`, q90 pinball improved | Brier-30 not improved; q95 and q99 pinball worse |
| **SIS RB run defense** (opponent Run Defense Points Saved/play) | point MAE `3.8366509 → 3.8268668` | Brier-30 `+0.0000014275`, CI `[−0.0000234, +0.0000263]`; CRPS, Brier-20 and all three pinball losses worse |

The RB null is about as clean as this program has produced: a point estimate of
essentially zero with a symmetric interval and mixed fold signs
(`−0.0000369 / +0.0000226 / +0.0000190`). There is nothing to argue with.

Two process notes worth recording as positives:

- **The QB result was predeclared.** "This is the expected
  marginal-versus-extreme-tail pattern declared before output." That is the
  right way to run an arm with a known prior, and it turns a null into
  confirmation rather than surprise.
- **Per-arm calibration refitting is now live.** Control QB scale factors were
  `0.965/0.905/0.925`, treatment selected `0.975/0.910/0.915`. Each arm fits its
  own scales, which closes the control/treatment calibration confound I raised
  earlier. That is why the RB arm's worse CRPS is a real property of the
  feature and not a recalibration artifact.

The pattern is now at **eight** instances. But there is a distinction inside it
worth separating.

## 2. A sub-pattern: team-broadcast features degrade the distribution

Not all eight failures have the same shape.

| arm | grain | MAE | CRPS |
|---|---|---|---|
| Route share components | **player-level** | better every fold | **better every fold** |
| Team-QB quality | team → broadcast to receivers | better | **worse** |
| SIS RB run defense | opponent team → broadcast to RBs | better | **worse** |

Three cases is suggestive, not established. But the direction is coherent: a
team-level column is constant across every player on that team, so it cannot
discriminate *within* a team. It shifts a whole team's predictions together —
which lowers MAE, because team effects are real — while supplying no
within-team conditioning. For a distributional learner that can concentrate the
predictive distribution where true variance is high, which is exactly what
worsening CRPS and every pinball loss looks like.

**Recommendation: record this as a predeclared expectation for the remaining SIS
queue.** Any further team-broadcast column should be expected to improve MAE and
degrade CRPS, and should be gated on CRPS rather than MAE so the trade is
visible before an exact-80 is contemplated. It also argues, independently of §3
and §4, for prioritising player-grain over team-grain SIS content.

## 3. The alignment feasibility question is answerable for free — and the answer is unfavourable

The SIS alignment sample is paused at 7 of 12 immutable queries with no accepted
artifact. The pause discipline is right — no raw row was inspected, so this is
neither a pass nor a fail, and not spending speculatively is correct.

But **the receiver half of that question does not need SIS at all.** The
already-downloaded, hash-validated Fantasy Points *Separation by Alignment*
exports carry Wide / Slot / Inline / Backfield route counts per player, and the
intake audit confirmed those four sum exactly to Overall routes on every row in
all four seasons.

Measured on 2025, players with ≥100 routes, reporting each player's share of
routes in his single most common alignment:

| position | n | median modal share | p25 | p75 | share ≥ 0.70 |
|---|---:|---:|---:|---:|---:|
| WR | 146 | **0.673** | 0.596 | 0.776 | **45%** |
| TE | 69 | **0.542** | 0.473 | 0.652 | **17%** |
| RB | 59 | 0.858 | 0.829 | 0.900 | 93% |

Read this carefully, because it is an **upper bound** on crossing sharpness:

- The median WR spends only **67%** of routes in his most common alignment on a
  *four-way* partition. A quarter of WRs are below 0.596.
- **SIS partitions more finely** — Left / Slot / Right for receivers,
  LCB / RCB / SCB for defenders. "Wide" splits into left and right, roughly
  evenly for many receivers. So a WR's modal share on the SIS partition will be
  materially below 0.673, plausibly in the 0.35–0.45 range.
- Combined with a corner playing ~70–85% at one alignment, the expected fraction
  of a given WR's routes covered by a specific CB lands somewhere near a third.
- **TEs are worse than diffuse** — a median modal share of 0.542 with only 17%
  above 0.70 means TE alignment carries almost no matchup identity.
- RB concentration is high but meaningless: the modal alignment is "backfield,"
  which carries no cornerback information.

**Conclusion: alignment crossing degrades toward a weighted blend of defender
qualities — which is structurally the same object as the team-shell construct
whose effect ceiling was measured at 0.04–0.09 DK points.** It is not the
concentrated individual matchup that justified reopening the coverage family.

I want to be fair about the exception: a handful of genuine shadow corners each
season do travel with an opponent's WR1, and for those specific pairings the
crossing is sharp regardless of alignment. But a small subset of a 0.05-point
effect is not a lineup lever, and identifying shadow assignment requires data
this subscription does not appear to expose.

**Recommendation: do not spend the remaining five SIS queries on the alignment
feasibility sample.** The receiver side already answers it unfavourably at zero
cost, and preserving the five queries is worth more than confirming a bound we
can already compute. Diagnose the response-listener bug on a throwaway query
class if it needs fixing for other reasons — but not as part of this test.

## 4. What survives: conditional allocation without defender identity

My earlier conditional-allocation proposal assumed crossing worked. §3 says it
mostly does not. But the idea survives in a cheaper and better-supported form,
because **it never actually required identifying individual defenders.**

The mechanism that matters for the copula is: *when a quarterback has a big
game, which receiver absorbs it?* That needs a **defense profile**, not a
defender identity:

- **Receiver side (free, already held):** each receiver's alignment profile —
  wide / slot / inline shares — from the Fantasy Points alignment exports,
  strictly lagged.
- **Defense side (SIS, cheap):** team pass-defense strength *by receiver
  alignment faced* and by coverage shell. This is **team-game grain — 32 rows
  per week**, comfortably inside the cap, and it is exactly the filtered-view
  content the inventory ranked as SIS's distinct value.
- **Use:** modulate the centering and concentration of the per-team Dirichlet
  target allocation for that game. A defense strong against slot and weak
  outside shifts allocation weight toward outside receivers. Team-level mean
  preservation still holds; only the split changes.

This construct:

- targets the **copula**, which G0 showed is the binding channel
  (QB→WR simulated 1.053 vs realized 3.3228);
- is **conditional**, which is precisely what G2 lacked — its single
  context-free Gumbel strength per position could not activate for WR;
- avoids the defender-identity problem §3 just exposed;
- fits the query budget, unlike a player-level pass-defense backfill; and
- should be gated on the **G0/G1 dependence scorecard** with WR–WR
  must-not-worsen, not on a 30-point Brier.

It also composes with the TD/production-ledger arm proposed after G2: the
ledger supplies the shared-production force that lifts QB→every receiver, and
conditional allocation supplies the competitive force with the *right
per-receiver weights*. Neither alone reproduces the measured structure; together
they plausibly do.

---

## Recommended order

1. Record the §2 team-broadcast expectation and gate remaining team-grain SIS
   columns on CRPS rather than MAE.
2. **Cancel the alignment feasibility sample**; preserve the five remaining
   queries. §3 answers it.
3. Acquire the **team pass-defense-by-receiver-alignment and by-coverage-shell
   filtered views** — 32 rows per week, within budget, the highest-value
   remaining SIS content.
4. Preregister **conditional allocation** (§4) against the G0/G1 scorecard.
5. Leave individual player-level pass-defense backfill unfunded until something
   in 3–4 justifies it.
