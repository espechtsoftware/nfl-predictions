# Offseason selection ideas toward a ~194 mean weekly maximum

**Date:** 2026-08-18
**Author:** Claude (Fable 5), orchestration session
**Prompted by:** operator request for *simple ways to better select lineups from
the corpus, provable during the offseason with existing historical data*, with a
target of **mean weekly maximum ≈ 194**.
**Sources:** HANDOFF.md (2026-08-18 states), the 2026-08-14 final preseason
forensic result, the exact-stack addendum gaps, the CBWU-OI construction
diagnostic, the discordant-pair feasibility census, and code
(`optimizer/lineup.py::select_tail_entries`, `research/candidate_union.py`,
`research/tail_portfolio.py`, `research/exact_p_generator_census.py`).
This document proposes; every idea needs its own frozen one-shot protocol, and
several need an operator law amendment (noted inline).

---

## 0. Status of the prior report's suggestions (for context)

From `2026-08-18-boom-lineup-capability-review-and-suggestions.md`, per the
handoff record: **S1 (null-calibrated P−C floor) APPROVED** (score-free,
design lane; W and world rule frozen first); **S4 (marginal-vs-dependence
attribution) APPROVED** (q95/q99 descriptive); **S2 (OT v2 dependence-only
mixture) protocol draft APPROVED**, arm gated on the dependence scorecard;
**S8 (surprise ledger) APPROVED**; heavy-slot order set to **ATLAS C first,
then S1's result decides residual-columns vs DST/law work**; S5's premise was
corrected (unique-fill genuinely absent only at the primary boom pass,
`engine.py:1117`) with no run decision; S3/S6 undecided; S7 partially standing
in the Week-1 lane. Separately the operator set **Week 1 = 100 entries**
(money 80 + the CBWU-OI shadow's frozen top-20 entered live), and the
discordant-pair census confirmed `replay_candidates_staging` retains rosters +
actual scores for **104 panel_run_ids** — a fact several ideas below use.

---

## 1. The ceiling arithmetic — read this before any idea

All numbers are the current production stack on its 54 comparable 2023–2025
slates (final preseason forensic result; exact-stack oracle addendum;
CBWU-OI construction diagnostic):

| Quantity | Mean weekly max | 187/194/200/210/220/230/240 |
|---|---|---|
| Selected 80-entry book (today) | **176.06** | 17/8/7/6/3/1/0 |
| Best candidate in today's pool (C) | **181.07** | 11ᶜ/8ᶜ/6ᶜ at 194/200/210; 3/1/0 |
| Best candidate in the CBWU-OI pool | **186.73** | 18ᶜ/14ᶜ/10ᶜ at 194/200/210; 3/1/0 |
| Hindsight pool-player optimum (P) | ≈ 250 | (C + 68.91) |
| **Operator target** | **194** | — |

(ᶜ = candidate-level counts, not selected-book counts.)

The decomposition is H−P = 4.06, **P−C = 68.91**, **C−S = 5.01**, and at ≥210
selection is the first failed layer on **0 of 54** slates (construction on 44).

Three consequences, stated plainly:

1. **No selector on today's pool can exceed 181.07 mean.** The entire
   selection layer is worth at most +5.01 mean points, and the threshold
   counts are already nearly captured (C vs S at 194/200/210: 11/8/6 vs
   8/7/6 — three recoverable weeks at 194, one at 200, zero at 210+).
2. **No selector on the best measured pool (CBWU-OI) can exceed 186.73 mean**
   — still 7.3 points short of 194. Reaching a 194-mean book requires a pool
   whose mean C is roughly **196+** (assuming a residual ~2-point selection
   loss), i.e., closing ~20 more points of the 69-point construction gap
   beyond what CBWU-OI already closed.
3. Recent empirical scale of selection-layer wins: the naive conditional-mean
   recourse reoptimization — the best selection-adjacent diagnostic result of
   the last week — gained **+1.15 mean** (176.06→177.21) and the tail-aware
   variant *lost* 0.74. One-point effects are the realistic size class here.

So the honest answer to "can better selection get the weekly max average to
194?" is **no — not from any existing pool**. What existing historical data
*can* do in the offseason is (A) capture most of the remaining +5 on the pool
we have, (B) measure and then exploit the union of everything ever generated,
and (C) manufacture new rosters offline against the stored pre-lock worlds,
which is construction but runs entirely on existing data. The ideas below are
organized in those three rings, cheapest first, each with its evaluation
design and its ledger pressure-test.

**A utility decision is needed first.** The stated target (a *mean*) is a
different objective from both the standing operational law (lexicographic
240→230→…→187 counts) and the production selector's objective (world coverage
at the fixed 194 line). These three genuinely conflict: the ledger shows
mean/shoulder and extreme tail trading against each other repeatedly
(CAND_MULT: mean up, 210 collapsed 5→2; member-sample worlds: mean up,
200/210 down; the CBWU adoption itself paid one 194 crossing for +5 weeks at
210+). Every idea below needs the operator to fix `u` — pure mean,
the sparse ladder, or lexicographic — **before** the one-shot evaluation, or
the result will be unreadable.

---

## 2. Ring A — selector ideas on existing pools (cap: +5.01 mean)

### A1. Optimize the target directly: E[u(max)] portfolio-marginal greedy

**The one selector idea matched to the stated goal.** The production selector
greedily maximizes newly covered worlds above the fixed 194 line — it
optimizes `P(max ≥ 194)`, not the mean weekly max. If the objective is a mean
near 194, the aligned selector is: at each of the 80 steps, add the candidate
`l` maximizing

`Σ_w q(w) · [u(max(m(w), S(l,w))) − u(m(w))]`

where `m(w)` is the book's best score so far in world `w`. With `u(x) = x`
this is greedy **E[max]**; with `u = Σ_t λ_t·1[x ≥ t]` it is weighted
multi-threshold coverage (the review's sparse ladder); the current selector is
the special case `u = 1[x ≥ 194]`. For any nondecreasing `u` the objective is
monotone submodular, so greedy keeps the same (1−1/e) guarantee the current
selector enjoys.

- **Why it can move the mean:** the C−S gap is a *mean* gap (5.01) with almost
  no threshold gap — exactly the signature of a threshold objective that is
  indifferent among lineups once a world is covered. E[max] credits raising an
  already-covered world from 195 to 215; the current objective does not.
- **Ledger pressure-test:** not previously tested. What *was* tested and
  failed/exchanged: global line sweeps (flat), single-metric rankings
  (top-p-line/mean/q99 — marginal rankings, not portfolio-marginal), fixed
  hedged books (60/20 splits), one-swap refinements (recover nothing). None of
  those is this mechanism. Selection remains formally closed under the
  reopening condition, so running this on historical outcomes needs an
  **operator amendment** scoped as a one-shot offseason family (precedent: the
  tail-first override was an operator utility decision after a machine
  verdict).
- **Cost:** trivial — candidate-total matrices for all 54 slates are stored;
  this is a laptop-scale pass (single process, per repo compute rules).
- **Predeclare:** the mean-vs-tail tradeoff (E[max] may drop a 210+ count);
  report the full 240→187 grid, mean with slate-bootstrap CI, and discordant
  slates vs the incumbent book. Include lower ladder rungs (e.g., 170/180) so
  weak slates still discriminate.
- **Honest expectation:** +1.5 to +3 mean in-sim; realized transfer uncertain
  (candidate-level sim/actual Spearman ≈ 0.16–0.24). Kill if in-sim mean gain
  < +1 or if the 210+ grid worsens beyond the predeclared allowance.

### A2. Per-slate self-normalized selection line

Replace the fixed 194 with `line_s` = a fixed quantile `q*` of slate `s`'s own
simulated book-max (or candidate-total) distribution. On weak slates a global
194 covers almost nothing (the greedy degenerates toward argmax; little
portfolio structure); on strong slates it covers nearly everything (no
discrimination). Normalizing keeps the selector in its informative regime.
Distinct from the closed global line sweeps, which moved one shared constant.
Small preregistered family (e.g., `q*` matching 194's historical average
exceedance, ±one alternative), one shot, same reporting as A1. Expected ≤ +1
mean; mostly a robustness idea. Largely subsumed by A1's ladder if that runs.

### A3. Greedy optimality-gap audit (closure evidence, run first)

Before any objective debate: measure how far the greedy selector sits from the
*exact* optimum of its own objective. On a sample of slates (or all 54 with a
reduced world set), solve the max-coverage selection exactly (MILP over
candidates × world indicators, or exhaustively over the small candidate
counts) and report greedy-vs-optimal coverage and the implied score delta.
One-swap evidence already suggests the gap is ≈ 0; proving it **closes the
selector-algorithm family permanently** and redirects all attention to the
objective (A1) and the pool (Rings B/C). Score-free (uses simulated coverage
only), cheap, no amendment needed. This is the best value-per-hour item in
this document.

### A4. Value-based tie-breaking (minimal-change variant)

The tie-census primitive (`stable_identity_tail_selection`) exists because
greedy coverage ties are real: integer covered-world counts tie frequently and
are currently broken by mean-total then identity. Breaking ties by ladder
value (A1's `u`) instead changes nothing except tie resolution — the smallest
possible selector change, plausibly worth a fraction of a point, and a natural
rider on the tie census that is already queued to be wired. Evaluate inside
the same one-shot family as A1.

### A5. Block-robust (LCB) selection — stability, not score

Maximize a lower-confidence coverage bound across the five 10k-world blocks
(mean − λ·std, λ frozen; or worst-block). The naive bagged selector is
provably vacuous; this is the genuinely different objective the resampling
reconciliation named. Expected realized-mean effect ≈ 0; the value is
reproducibility (the CBWU-OI overlap regression 65.69→60.87/80 is an
operational risk). Run score-free under the existing stability harness only;
promote to a 2026 shadow if it improves overlap at no simulated-coverage cost.

---

## 3. Ring B — select from a bigger existing corpus (the real offseason lever)

### B1. Measure the all-arms union C first (one number that sets the agenda)

The discordant-pair census established that `replay_candidates_staging`
retains rosters **with actual scores** for 104 panels — every same-image
arm/control family ever run. The mechanically-complete cross-arm union
candidate ceiling on the 54-slate corpus is therefore a single aggregate over
already-registered data:

1. Take every distinct roster ever generated for each of the 54 slates, from
   **all** panels (mechanical inclusion — no per-arm cherry-picking, which is
   what keeps the selection effect bounded and disclosable).
2. Re-validate each roster's legality under the corrected slate (salary cap,
   $49k floor, positions, teams, active status) — old-universe rosters that
   fail repricing drop out mechanically.
3. Report union mean C and the full C-tail grid, alongside canonical
   (181.07) and CBWU-OI (186.73), plus per-arm source attribution of the
   union's slate maxima.

**Why this number matters more than any selector idea:** it is the exact
ceiling of "better selection from the corpus" in the widest defensible sense
of *corpus*. If union C ≈ 192–196, a union-admission policy (B2) is the
fastest existing-data path toward the target and deserves the next analysis
slot. If union C ≈ 187–189, then *everything ever generated* still caps below
the target, the operator's 194 requires Ring C construction and/or law work,
and we will have learned that for the cost of one BigQuery aggregation.
Evidence it won't be trivial: the fast-role union added six treatment-only
194-clears on the old panel; role-union added +1.45 mean; CBWU-OI added +5.66
mean C from five seeds of the *same* generator — cross-arm diversity is wider
than that.

- **Caveats to freeze in the protocol:** outcome-facing (actual scores are
  read), so diagnostic-only labeling; arms were already outcome-viewed at
  panel level, so the union C is a slightly optimistic ceiling estimate —
  report per-arm attribution so concentration in one rejected arm is visible;
  cross-era rosters are only identities (their generating beliefs don't
  transfer, and nothing here claims they do).
- **Cost:** one frozen SQL/report job. No cloud simulation, no heavy slot.

### B2. Union-admission selection policy (if B1 is promising)

Generalize the proven CBWU-OI mechanism from five seeds to the mechanical
all-arms union: complete distinct roster union → cross-score every roster on
the current five 10k-world blocks (the 270 stored artifacts make this exact) →
score-blind admission to the fixed R0 budget → unchanged selector (or A1's,
if the utility decision lands there). `candidate_union.py` already implements
the pairwise pattern; this extends it to n-ary with the OI admission rule.
Evaluate one-shot, LOSO by season, with the frozen utility from §1 and
McNemar discordant-slate reporting. Realistic gain: whatever B1 shows, minus
~2–5 selection loss. This is "selection from the corpus" in exactly the
user's sense — no new candidate is invented; the budget and selector are
unchanged; only the admission universe grows.

### B3. Exact-100 versus 80+20 (rides the operator's fresh decision)

Week 1 now runs 100 entries as money-80 + OI-top-20. The stored totals
matrices make the historical comparison free: on each of the 54 slates,
compare (i) the composite 80+20 book, (ii) a unified exact-100 selection from
the OI (or B2 union) pool, and (iii) exact-80, all under the frozen utility.
This measures the marginal 20 entries' mean-max value (my prior: +0.5 to
+1.5) and whether composite construction leaves anything vs unified
selection. Uses only stored data; one-shot; informs the standing entry-budget
decision rather than any closed selector family.

### B4. Relationship to the queued capacity curve

The frozen `20260817-same-law-capacity-curve-v1` (1x/2x/5x/10x generation
scaling, identity-only so far) answers the *generation-budget* capacity
question; B1–B3 answer the *admission/selection* capacity question on compute
already spent. They are complementary, and B1 should run first because it is
nearly free.

---

## 4. Ring C — construct offline against stored pre-lock worlds

Included for completeness; the heavy-slot decision (ATLAS C → S1 decides
residual-columns vs DST/law) is already recorded and this document does not
relitigate it. Two notes connect Ring C to the 194 target:

1. **Residual-world columns are the sanctioned instrument for exactly the
   ~10–20 mean C points that Rings A+B cannot supply.** All of its pricing and
   scoring runs against the stored 270 world artifacts and frozen snapshots —
   it *is* an existing-historical-data offseason experiment in the user's
   sense, with one scored read at the end.
2. If residual licensing lags the offseason, two cheap column sources use the
   same stored artifacts and the same admission/selection machinery:
   **top-K near-optimal enumeration per elite world** (no-good cuts on the
   best attainable worlds — diversifying within a world instead of taking one
   argmax, which directly attacks the exact-P finding that winners sit ~5
   swaps from every candidate), and **single-game onslaught sleeves** (bounded
   count, story-coherent). Both are MILPs over stored draws; both stay
   score-free until one frozen read.

---

## 5. What "proven in the offseason" can honestly mean

Every 2019–2025 outcome has been viewed at panel level, and the standing law
forbids retrospective selector tuning on these slates. The workable standard,
consistent with how this project already operates:

1. **One-shot preregistered families.** Freeze the exact variant list, the
   utility `u`, the decision rule, and code hashes before the first aggregate;
   no iteration after the read (repair budget 0 for analysis reruns).
2. **LOSO by season + the standing stability law** for any adoption-flavored
   claim; slate-bootstrap CIs on mean deltas; the full 240→187 grid always.
3. **McNemar discordant-slate tables** for every paired comparison (now the
   house standard per the reconciled briefing review).
4. **Labels:** Ring A/B results are decision support for a 2026 prospective
   confirmation (shadow or paired live book), never direct money-policy
   proof. The OI precedent applies: its selected-80 was deliberately left
   unscored historically to keep the prospective gate clean — whether to
   spend that cleanliness anywhere else is an operator-only decision.
5. **Law amendments needed:** Ring A and B2/B3 evaluations touch realized
   outcomes on closed-selector territory and therefore need an explicit
   operator amendment authorizing one offseason one-shot family under the
   frozen utility. A3, A5, and B1's mechanical census are score-free or
   purely descriptive and fit existing lanes.

---

## 6. Recommended order and expected value

| # | Item | Cost | Needs amendment? | Expected mean gain (in-sim) |
|---|---|---|---|---|
| 1 | A3 greedy optimality-gap audit | hours | no (score-free) | 0 (closure evidence) |
| 2 | B1 all-arms union-C census | one query job | diagnostic label | 0 (sets the agenda) |
| 3 | Utility decision (`u`: mean / ladder / lexicographic) | operator | — | — |
| 4 | A1 (+A4 tie-break) one-shot on the pool B1 selects | laptop-scale | **yes** | +1.5–3 |
| 5 | B2 union-admission one-shot (if B1 ≥ ~190) | small cloud job | **yes** | +2–6 |
| 6 | B3 exact-100 vs 80+20 | free (stored totals) | **yes** | +0.5–1.5 |
| 7 | A5 LCB stability (score-free harness) | small | no | ~0 (operational) |
| 8 | Ring C per the recorded heavy-slot decision | heavy slot | already governed | the remainder |

Stacked realistically: 176.1 (today) → ~181–182 (OI admission + A1-class
selection, both already evidenced at their layers) → +B2's measured headroom →
the rest is Ring C / law work. **A 194 mean weekly max is not reachable by
selection alone on any measured pool; whether it is reachable on the union of
everything ever generated is answerable this week for the cost of one query
(B1), and that number should decide how much of the offseason goes to
selection versus construction.**
