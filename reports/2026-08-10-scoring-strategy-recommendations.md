# Scoring and selection strategy — outside review and recommendations

Date: 2026-08-10. Author: review pass over `README.md`, `HANDOFF.md`,
`reports/2026-07-25-system-study.md` (addenda 87–120),
`reports/2026-08-08-80-entry-tail-audit.md`,
`reports/2026-08-10-tail-first-adoption-review.md`,
`reports/2026-08-10-scoring-opportunity-roadmap.md`,
`reports/2026-08-09-data-acquisition-priorities.md`, plus external literature
and commercial-practice research listed at the end.

This document proposes nothing that has already been validly falsified in the
ledger, and it flags where a proposal is superficially similar to a closed arm
but mechanically distinct. **No code was changed.** Every item is written as a
protocol sketch, not an instruction to deploy.

---

## 1. Where the system actually is

Adopted book `classic-k1-ce12-role12-boom28-v2`, 80 entries, 107 corrected
slates:

| | ≥187 | ≥194 | ≥200 | ≥210 | ≥220 | ≥230 | ≥240 | mean max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| selected | 39 | 27 | 18 | 12 | 6 | 3 | 2 | 182.57 |
| pool oracle | 48 | 32 | 22 | 13 | 6 | 3 | 2 | — |

Two facts dominate everything below.

**Fact A — selection is saturated at the top, generation is not.** At 220, 230
and 240 the selected count *equals* the pool oracle. The selector is already
taking every extreme lineup the generator produces. Below 210 there is a
selection gap (18 vs 22 at 200), but at the thresholds the operator has
declared primary there is none. This is fully consistent with the ledger's own
conclusion that selection is closed for the current simulator and feature set
(Addendum 95, falsified five ways). **Any further selector work cannot move the
220+ counts at all.** It can only move 194–210.

**Fact B — the gap to first place is upstream of everything.** Against 68 known
same-week Millionaire winning lines the book beats 0/68, is within 20 points in
0/68, and the mean gap is ~57 points *for the hindsight pool oracle*, not just
for the selected book. The candidate universe itself is ~57 points short of the
top prize on an average week.

Two corroborating diagnostics say the same thing from different directions:

- 33 of 612 winning-player slots are absent from the entire candidate pool.
  Those players averaged **22.74 actual vs 7.19 projected** — a +15.55 surprise.
- The pool contains 8.51 of the nine winning players *somewhere* on an average
  week, but its closest single candidate contains only **3.46** of them —
  against **3.30** under an exposure-preserving random-assembly null. Given
  which players we expose, our construction assembles winners barely better
  than random.

Fact B is a joint-belief problem (which players co-boom), Fact A's residue is a
marginal-belief problem (which cheap players boom at all). Neither is a
selector problem.

### 1a. A framing question worth deciding explicitly

Reconstructing the K=1 base panel's weekly maxima against representative
Millionaire lines (the one observed data point: 2025-10-05 main Milly,
161,764 entries, min-cash 169.34, first place 246.82):

| line | weeks selected book clears | weeks pool oracle clears |
|---:|---:|---:|
| 160 | 94 / 107 | 94 |
| **169 (min-cash)** | **76 / 107** | 78 |
| 180 | 50 | 56 |
| 194 | 22 | 30 |
| 200 | 12 | 19 |
| **247 (first place)** | ~0 | ~0 |

(Older `K1 base` panel; the adopted role-union book is strictly stronger, so
read these as a floor.)

The portfolio min-cashes a large-field Millionaire in roughly **seven weeks out
of ten** and wins one in approximately zero. Under a top-heavy but not
winner-take-all payout curve, the overwhelming majority of realizable dollars
currently sit between the min-cash line and ~210, not above 240. The 240-count
is 2/107 — with 17 slates per season that is one expected occurrence every
three seasons, and it still would not have won.

This is not an argument against the tail-first preference; it is the operator's
call. It *is* an argument that the objective should be stated in dollars so the
tradeoff is visible, which is Recommendation 1. If the answer is "I want the
Milly or nothing", that is a legitimate utility — but it should then be
accompanied by an explicit acceptance that the expected number of wins per
season under the current stack is near zero, and that the highest-leverage work
is upstream belief quality (§3.3, §3.4), not portfolio shaping.

---

## 2. Decomposition of the remaining opportunity

| Layer | Evidence of size | Status |
|---|---|---|
| Objective / payout alignment | Selecting for coverage at 194 in a contest whose min-cash is 169 and first is 247 | **Never tested.** Only score thresholds have been tried |
| Player marginal upper tails | Ordinary players clear q90/q99 at **7.37% / 0.72%** vs nominal 10% / 1% | **Measured defect, never repaired** |
| Within-game joint tails | Closest-candidate winner overlap 3.46 vs 3.30 random null | Three mechanisms tried and failed (Schaake, forest templates, Gumbel family) — all were *rank-permutation* mechanisms |
| Candidate generation budget | `lev` is 17,120 of ~25,800 candidates and its deletion costs 1 clear; `boom` deletion costs 15 | **Deletion tested, reallocation never tested** |
| Selection | 220/230/240 selected == oracle | **Closed.** Do not spend here |

---

## 3. Tier 1 — highest expected value

### 3.1 Replace threshold coverage with expected payout against a simulated field

**The claim.** The selector currently maximizes the number of simulated worlds
in which at least one entry clears a fixed 194. That is a proxy for a proxy.
The literature you already cite (Hunter–Vielma–Zaman; Haugh–Singal) and the
entire commercial state of the art (SaberSim, Stokastic, FTN contest sims) all
score a portfolio the same way: simulate the *contest*, not the score — generate
a field of opponent lineups, score every lineup in the same world, rank, apply
the real payout curve, and read expected dollars, win rate and duplication.

**Why this is not the rejected ownership arm.** `OWN_MODEL=fade` and
`milly_fade` both did the same thing: subtract `25 * own_est` from *our own*
objective. That is a hand-tuned penalty on our score. It was correctly
rejected twice. What has never been built is the *right-hand side of the
inequality* — an explicit distribution over opponent lineups. The ledger's own
greenfield note names this exactly: "the objective is not 'score X'; it is
'P(our max beats the field's max)', and the right-hand side deserves as much
modeling as the left." The roadmap repeats it under Priority 4. It remains
unbuilt.

**What you already have that makes it cheap.**

- A contest-aware ownership model that **passed** its frozen calibration gate:
  held-out MAE 2.87, Spearman 0.79, top-quartile MAE 7.73, beating both the
  all-contest model and the naive proxy in every held-out season, over 9,010
  rows and 71 slates (`evaluate-milly-ownership-wd4ll`). It was built, gated,
  and then only ever consumed as a fade coefficient. Its actual use is as the
  marginal of a field generator.
- 103,556 actual ownership records over 1,258 contests, every week 2022–2025.
- 68 real winner rosters for validation.
- `entries_curve.py` (`p_reach(N, line)`), the possession simulator, and the
  world matrices that already score 25,000 candidates per slate.

**Proposed construction.**

1. *Field generator.* Sample F ≈ 50k–150k opponent lineups per slate from a
   sequential conditional sampler: draw a QB from the ownership-implied
   marginal, then draw stack partners from a conditional distribution
   (P(WR from same team | QB), P(bring-back | stack)) fit on the 1,258
   contests of real ownership plus known stack rates, then fill remaining
   slots from ownership marginals renormalized under the salary constraint,
   rejecting illegal lineups. Haugh–Singal's Dirichlet-multinomial and
   Mlčoch–Hubáček's Dirichlet-regression opponent model are the two published
   parameterizations; both are simpler than anything already in this repo.
2. *Validation gate — and this is the key point, it does not touch the 107
   portfolio outcomes.* The field model is graded against field data, not
   against our lineup scores:
   - reproduce held-out contest ownership marginals (already measured);
   - reproduce observed **pairwise co-ownership** (stack rates) in the 1,258
     contests;
   - assign the 68 known winner rosters a likelihood materially above an
     ownership-independent product baseline;
   - reproduce the observed min-cash and first-place lines when the field is
     scored in our own worlds (this is the strongest single check available
     and needs only the winning-line labels you already hold).
3. *Only after that gate*, replace the selector's coverage objective with
   greedy maximization of expected payout: for each world, rank our 80 against
   the sampled field, apply the payout curve, split ties by duplication count,
   average over worlds. The greedy structure is unchanged — expected payout of
   a max over entries is submodular in the same way coverage is, which is
   precisely Haugh–Singal's multiple-entry argument, so the existing selector
   machinery and its determinism/tiebreak guarantees carry over.

**Expected effect.** This should *not* be sold as "more 240-point weeks." Its
first-order effects are (a) a target line that automatically adapts to slate
and field size, (b) duplication-aware entry differentiation, which is the one
thing that converts a 200-point week into money in a 161,764-entry field, and
(c) a decision currency in which the qualifier/Milly allocation question has an
answer. It is the only proposal here that changes what the system is optimizing
rather than how well it optimizes.

**Cost.** Field generator + payout scorer is meaningful new code but no new
data purchase. This is the largest single item in the document.

### 3.2 Make the target line slate-specific and pre-lock-predicted

**The claim.** The selection line is a global constant of 194. Winning scores
are not constant across slates — a 13-game slate with three 50-point totals has
a materially higher winning line than a 9-game slate in December wind. Selecting
for coverage at 194 systematically over-shoots on weak slates (wasting entries
on scenarios that cannot happen) and under-shoots on strong ones (optimizing a
min-cash line on a slate where the winner scores 260).

**Why this is not threshold mining.** The tested alternatives (187, 194, 200,
and the 220→210→200 lexicographic book) are all *global* constants chosen and
compared on the 107 known portfolio outcomes. What is proposed is a model
`line_w = f(pre-lock slate features)` fit on a **different label set** — the 68
known Millionaire winning lines, and any additional winning/min-cash lines
recoverable per §3.8 — never on our own lineup scores. Fitting on winning-line
labels and evaluating on the 107 portfolio outcomes exactly once, with the
model frozen first, is a clean preregistration.

**Features** (all pre-lock, all in house): number of games in the slate, sum
and max of implied team totals, spread dispersion, number of games with total
≥ 48, dome/outdoor and wind, mean and dispersion of salary-adjusted projections,
and DK salary-cap slack (median projected points per $1k).

**Gate.** Held-out MAE and calibration of the predicted winning line on the 68
labels, walk-forward by season, versus a constant-194 baseline and versus a
constant-mean baseline. Only a pass licenses a single frozen scoring arm using
`line_w` in place of 194, evaluated under the current 240→230→220→210 law. Note
in advance that under Fact A this arm can only move the 194–210 counts; do not
expect 220+ movement and do not retry it if 220+ is flat.

**Cost.** Small. This is the cheapest item in the document with a plausible
positive effect.

### 3.3 Repair the measured upper-tail miscalibration on ordinary players

**This is the single most concrete, already-quantified defect in the ledger and
it has not been fixed.**

The walk-forward TabPFN calibration audit found:

| segment | q90 exceedance | q99 exceedance |
|---|---:|---:|
| nominal | 10.00% | 1.00% |
| fast-role | 9.76% | 1.06% |
| vacancy / promotion | 9.03% | 1.20% |
| **ordinary players** | **7.37%** | **0.72%** |

The ledger drew the correct conclusion that a *generic* role-tail widening is
not the answer — role states are already calibrated. But the conclusion that was
never drawn is the mirror image: **the ordinary segment, which is the
overwhelming majority of every roster, has an upper tail roughly 25–30% too
thin at both q90 and q99.** Every candidate's simulated `p_line`, `q99`, and
support mask inherits that error, and the extreme tail of a nine-player sum is
far more sensitive to per-player q99 error than the mean is.

This connects directly to Fact B: the 33 winning-player slots absent from the
entire pool averaged 7.19 projected and 22.74 actual. A player projected at 7
with a correctly fat tail is a live q99 candidate; the same player with a 28%
under-covered q99 never enters a boom world and never gets built into a lineup.

**Why the shaper does not already fix this.** `emp_marginals.py` fits shape
families per (position, projection window) and then **affine-matches them to our
own (mean, std)**. The shape is empirical; the scale is ours. If our predicted
std is too small for cheap players, no shape family recovers the tail.
`conformal.py` implements exactly the right correction — a multiplier that makes
recent q90 coverage exact — but it is a single global factor, at q90 only, and
per the handoff it is prospective (auto-activates at ≥100 scored rows), so it
was not active in any of the historical panels that produced these verdicts.

**Proposed construction.** Segment-conditional distributional recalibration,
walk-forward:

1. Define segments on pre-lock observables only: position × salary tercile ×
   projection bucket, plus the existing role-state flags as a cross.
2. For each segment and each target level in {0.75, 0.90, 0.95, 0.99}, fit a
   monotone scale/shift correction on strictly prior seasons so that realized
   exceedance matches nominal. Enforce monotonicity across levels so the
   corrected quantile function stays valid, and shrink small segments toward
   the global correction (a hierarchical or simple empirical-Bayes shrinkage —
   the q99 cell counts will be thin by construction).
3. Apply before the empirical-marginal shaper, so the shaper's affine match
   uses corrected dispersion.

**Gate (player-level, no lineup scoring).** Held-out 2024/2025 exceedance at all
four levels within tolerance in every segment; CRPS and pinball loss
non-worsening; 20-point and 30-point Brier non-worsening; **mean predictions
byte-invariant** (this is a dispersion repair, not a new point belief — that
invariance is what distinguishes it from every rejected "widen the tails" arm).
Only a pass licenses one candidate-union arm, then one fixed-budget arm.

**Expected effect.** Unlike most items here, this one plausibly moves 220+,
because it directly increases the probability mass the simulator assigns to the
cheap-WR/TE explosions that the missed-winner audit identified. It is also the
item most likely to be dismissed as "we already tried widening tails" — the
distinction is that every prior widening was a *guessed dose applied to a
segment that was already calibrated*, and this is a *measured correction applied
to the segment that is measurably broken*, with mean-invariance enforced.

**Cost.** Small-to-moderate code, no new data.

### 3.4 Within-team allocation variance: the untried joint mechanism

**The claim.** Three joint-dependence mechanisms have been validly rejected —
fixed-distance Schaake, forest-learned conditional templates, and the whole
Gumbel family. All three share one property: **they permute or shock ranks over
players whose marginals are already fixed.** They rearrange who is high; they
cannot create the event "one receiver absorbed 14 targets this week."

The current simulator's game-level coupling is a single shared mean-preserving
multiplier per game (possession simulator → `game_factor_matrix` → one value per
game per sim). Within a team, once total points are drawn, each player's share
is effectively at expectation plus independent noise. That construction can make
shootouts. It cannot make the *allocative* extremes that actually win Millies:
the WR3 who runs 92% of routes because WR1 left in the first quarter, the TE who
catches all three red-zone touchdowns, the RB who takes 100% of goal-line work.

The missed-winner decomposition supports this precisely. 2019w9 required four
simultaneous positive surprises (Wilson +20.18, McCaffrey +16.31, Samuels
+11.52, Hollister +14.19) — a broad joint-tail miss with 2/9 overlap to the
selected book, explicitly *not* a locally interchangeable player.

**Proposed construction.** Draw per-world team allocation shares rather than
holding them at expectation:

- Team target share vector ~ Dirichlet(α · s), where `s` is the projected share
  vector and α is a concentration parameter **fit from historical week-to-week
  share dispersion** conditional on team and role, not tuned.
- Team TD allocation ~ Multinomial over red-zone-weighted shares, conditioned on
  the possession simulator's already-drawn team touchdown count.
- Carry rush-attempt share similarly for backfields.
- The Dirichlet mean equals the projected share vector, so **team-level
  marginals are preserved by construction** — the same invariance property that
  made Schaake and the forest scientifically clean.

This is a genuinely different mechanism class from everything rejected:
it is *allocative* (it changes how a drawn team total is divided) rather than
*permutational* (it changes which of fixed values goes to whom). It should be
gated on the identical metrics the forest failed — pair-weighted variogram error
and **joint-q90 tail Brier** — with the same diagnostic-only exit before
candidates. Add one metric the prior gates lacked: the realized frequency of
"≥2 players from one team simultaneously above their own q90", compared to the
historical rate. That statistic is the direct target and the current simulator
almost certainly under-produces it.

**Cost.** Moderate — a real change to `simulate.py`. But it is the one dependence
mechanism the ledger has not closed, and the ledger's own diagnosis (broad
co-boom misses, near-random assembly) points at it.

---

## 4. Tier 2 — cheap, plausible, untested

### 4.1 Reallocate the candidate budget rather than deleting from it

`lev` is 17,120 of ~25,800 candidates per true-80 panel (≈66%; 48% in the older
40-entry panels). Leave-one-generator-out found that removing `lev` entirely
costs **1** clear, while removing `boom` costs **15**, and `dark` is the best
value-per-candidate batch. Per thousand candidates that is roughly two orders of
magnitude of difference in yield.

What was tested is *deletion at reduced total budget*. What has never been
tested is **reallocation at constant total budget**: hold total candidates fixed
and shift half of `lev`'s allocation to `boom` / `dark` / CE / role. That is a
single-lever, exact-budget, self-identifying arm of exactly the kind the
existing runner/comparator infrastructure already validates.

One honest complication to preregister: `lev` produced 21 of 24 unselected 200+
rows. So `lev` does generate raw upside that the selector declines. Either that
budget is wasted or the selector is wrong about it — under Fact A (selection
saturated at 220+) the first reading is more likely, but the arm should report
both the selected grid and the pool oracle so the two hypotheses separate.

### 4.2 Scenario-conditional generation (world-argmax) as a scored arm

During the GFlowNet gate, per-world argmax was the *best* generator measured —
frontier gain +7.9 versus Gumbel-MILP +6.8 and GFlowNet +5.4 at equal count. It
was used as a baseline to reject GFlowNet and then, as far as the ledger shows,
never run as a scored panel arm in its own right.

The natural tail-focused version: restrict to the upper decile of worlds by
total slate scoring (or by max game total), solve the MILP to argmax realized
points *in that world*, and take the distinct rosters. These are lineups that
are optimal conditional on a plausible extreme scenario — structurally different
from CE, which deforms deterministic means globally, and from `boom`, which
applies a fixed upside tilt. Given Fact A this is aimed squarely at the layer
that binds.

Budget it out of `lev` per §4.1 so total compute is unchanged.

### 4.3 Slice the portfolio per contest instead of serving one book everywhere

The weekly entry plan is roughly 3 qualifiers × 14 plus 4 Millionaire seats, but
one 80-lineup book selected at one global line is served to all of them. A
14-entry small-field qualifier and a 4-entry seat in a 161,764-entry Millionaire
have different optimal target lines and radically different uniqueness needs.

`entries_curve.p_reach(N, line)` already exists to price this. Under §3.1's
expected-payout objective this falls out automatically; even without §3.1 it can
be done immediately as a deterministic split — select the Millionaire seats at
the extreme lexicographic line (the already-frozen 220→210→200 book) and the
qualifier entries at a lower line — with no new modeling at all. This is a
prospective policy change; grade it on frozen 2026 outcomes.

### 4.4 Cheap data moves

- **Contest metadata backfill is much cheaper than full fields, and is enough
  for §3.2 and part of §3.1.** The DFS Hero trial failed the full-field gate but
  *did* expose per-contest metadata (161,764 entries, 169.34 min-cash, 246.82
  first place for one slate). A backfill of just {field size, entry fee, payout
  curve, min-cash line, first-place score} for 2022–2025 main slates — no
  opponent rosters — would supply the labels for the winning-line model and let
  the field generator be calibrated against realized cash lines. Ask every
  vendor in the acquisition doc for *this* narrower export before asking for
  entry-level rosters; it is far more likely to be available.
- **Full standings from Week 1, 2026** remains correctly ranked as Priority 1 in
  the existing acquisition doc. Nothing here changes that. It is the only path
  to a duplication model.
- **Route data**: the pass-participation proxy passed its gate
  (`pass-participation-proxy-vmxdq`: MAE 3.71089→3.67957, 20-pt Brier
  0.045375→0.045226, both seasons positive). The effect is small but the WR/TE
  slot is where the winner misses concentrate. At $200 for Fantasy Points with
  confirmed CSV export and 2022+ history, this is inexpensive relative to the
  cloud spend already going into panels. Recommend proceeding, with the caveat
  the roadmap already states: it is one input to a calibration gate, not a
  forecast lineup lift.

---

## 5. Tier 3 — defer, with reasons

- **Deep generative dependence models (copulas, diffusion, flows).** Correctly
  deferred. 107 realized slates cannot support them, and the flexible-model
  failure mode here is panel mining, not underfitting. Revisit only after §3.4
  and route data.
- **Importance-sampled rare-event support estimation** (roadmap Priority 5).
  The stated prerequisite — exposing the possession simulator's own latent
  variables with an exact log density before any change of measure — is exactly
  right, and the ledger is right that CE weights cannot be reused. Given Fact A
  (selection saturated at 220+), the payoff even on success is limited to better
  *ranking* of candidates that already exist. Rank it below §3.1–3.4.
- **Further selector search on the 107 slates.** Closed. Fact A says the ceiling
  is +0 at 220/230/240 and +4 at 200 even with perfect hindsight.
- **Ensemble world-mode variants.** `member_sample` was tested and damaged the
  high tail (8→6 at 200). K=1 won. Leave it.

---

## 6. A statistical-power guardrail worth adopting explicitly

The revised tail-first law promotes an arm that "improves at least one 210+
threshold and does not worsen any higher threshold." With 107 slates the control
counts at those thresholds are 12 / 6 / 3 / 2. A change of 1→2 at 240, or 2→3 at
230, is a single Bernoulli event. Under any plausible null it is indistinguishable
from noise, and there are enough arms in flight that something will move by one
somewhere.

The role-union adoption itself illustrates both sides. Its threshold gains
(11→12, 5→6, 2→3, 1→2) are individually single events. But its *paired* record —
15 weekly maxima improved, 6 declined, 86 tied — gives a one-sided exact sign
test around p ≈ 0.04, and mean weekly max +1.448 positive in five of six
seasons. That paired evidence, not the threshold table, is what actually
supports the decision.

**Recommended addition to the decision law:** an arm may not be promoted on a
threshold whose control count is below ~5 unless the paired weekly-maximum
comparison is also favorable at a preregistered significance level. Report the
paired sign test and the mean-delta by season on every arm as a required field,
not a diagnostic. This costs nothing, does not weaken the tail-first preference,
and prevents the revised law from becoming a license to mine 240-counts.

---

## 7. What I would not retry

Consistent with the ledger; listed so the recommendations above are not misread
as reopening any of it.

- Generic ownership fade on our own objective (rejected twice, two distinct
  targets). §3.1 is the opponent-side model, not this.
- The whole Gumbel candidate family, Schaake shuffle, EPI, forest templates.
- Raw candidate-budget scaling (`CAND_MULT=4`: +1 at 200, −3 at 210).
- Salary-floor deletion, stack-mandate loosening, punt mandates, no-floor as a
  standalone book.
- Any selector reranker on the 107 outcomes; `corr(oracle sim-rank, regret)` is
  +0.030, so there is no gradient to learn in the current signals.
- Chronos-style time-series marginals (baselines won everywhere).

---

## 8. Suggested sequence

Ordered by (expected effect) / (cost × risk of invalidation):

1. **§3.3 ordinary-player tail recalibration.** Small code, measured defect,
   player-level gate that never touches the 107 portfolio outcomes, and the
   only Tier-1 item with a plausible path to 220+.
2. **§3.2 predicted per-slate line.** Small code, fits on a disjoint label set,
   one frozen arm.
3. **§4.1 candidate-budget reallocation** and **§4.2 world-argmax arm.** Both
   reuse existing runner/comparator infrastructure at constant compute.
4. **§4.4 contest-metadata backfill request** and the Fantasy Points purchase —
   both are asks/spends that can run in parallel with 1–3.
5. **§3.1 field model and expected-payout objective.** Largest build; start the
   field generator and its ownership/co-ownership/winner-likelihood gate now
   (it needs no lineup panel), and let the 2026 standings collection feed it.
6. **§3.4 within-team allocation variance.** Real simulator change; gate on
   variogram + joint-q90 Brier + the new co-exceedance statistic before any
   candidate work.
7. **§4.3 per-contest slicing** as a prospective policy for Week 1, graded on
   frozen 2026 outcomes.

Items 1, 2, 3 are historical arms and must obey the existing validation law
(same-image co-run control, exact entry count, self-identifying levers,
no post-hoc dose tuning). Items 5 and 7 are prospective and should be graded on
2026 outcomes rather than mined on the 107.

---

## Sources

Project-internal evidence is cited inline by report and execution ID. External:

- [Picking Winners in Daily Fantasy Sports Using Integer Programming — Hunter, Vielma, Zaman](https://arxiv.org/abs/1604.01455)
- [How to Play Fantasy Sports Strategically (and Win) — Haugh, Singal](https://pubsonline.informs.org/doi/abs/10.1287/mnsc.2019.3528) ([preprint](http://www.columbia.edu/~mh2078/DFS_Revision_1_May2019.pdf)) — Dirichlet-multinomial opponent model, multiple-entry submodularity
- [Competing in daily fantasy sports using generative models — Mlčoch, Hubáček (2024), ITOR](https://onlinelibrary.wiley.com/doi/full/10.1111/itor.13344) — generative-ensemble marginals, Dirichlet-regression opponent model, MIQP over mean/variance/covariance for top-heavy payouts
- [How Contest Sims Work — SaberSim](https://support.sabersim.com/en/articles/12079199-how-contest-sims-work) — commercial practice: stake-bucketed field generation, dupes, exact payout curves, ROI/win-rate outputs
- [How Expected Value in DFS Works — Stokastic](https://www.stokastic.com/articles/dfs-strategy/how-expected-value-works-in-dfs)
- [DFS Simulator FAQ — The Solver](https://thesolver.com/simulator/faq)
- [Optimizing Daily Fantasy Lineups: A Linear Programming Approach](https://arxiv.org/pdf/2411.11012)
- [Rare-Event Simulation Techniques: An Introduction and Recent Advances](https://www.sciencedirect.com/science/article/pii/S092705070613011X) — background for the deferred importance-sampling item
- [nflreadr data dictionary / release index](https://nflreadr.nflverse.com/) — participation, FTN charting (2022+), NGS weekly
- [Fantasy Points Data Suite contents and export](https://newsletter.fantasypoints.com/p/fantasy-points-data-free-this-week)
- [DraftKings full-standings CSV, 10-day retention](https://help.draftkings.com/hc/en-us/articles/4412213454099-How-do-I-download-a-CSV-to-see-GameCenter-standings-for-a-contest-US)
