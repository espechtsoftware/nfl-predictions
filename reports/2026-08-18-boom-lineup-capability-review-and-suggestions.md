# Boom-lineup capability: state review and suggestions

**Date:** 2026-08-18
**Author:** Claude (Fable 5), orchestration session
**Sources of truth used:** `HANDOFF.md` (current state 2026-08-18 13:20 CDT and prior
states), `README.md`, `reports/2026-07-25-system-study.md` (Addenda 101–120), and
the code (`backtest/engine.py`, `models/game_sim.py`, `inference/market_implied.py`,
`inference/live_lineups.py`, `research/residual_world_columns.py`,
`research/exact_p_generator_census.py`, `research/final_forensic.py`). Reports under
`reports/` were used only as leads and are cited only where the handoff or code
confirms them. This document proposes; it changes nothing. Every proposal here
requires its own frozen protocol before any outcome is read, and protocol/money
decisions remain the operator's.

---

## 1. Where the system stands (verified)

- **Production policy** `classic-k1-role12-boom40-poscal-cbwu-v4`: K=1 `tail_k1` +
  `tail_k1_role`, 12 role / 40 boom generation, 45/55 model/market blend, $49k
  floor, final-served position factors, five-seed CBWU transport cross-scored in
  5×10,000-world blocks, unchanged greedy line-194 selector, 80 entries.
- **Headline (107 corrected slates):** selected weekly maxima
  **34/24/13/7/5/3/2** at ≥187/194/200/210/220/230/240; candidate-pool oracle
  **43/31/19/9/5/3/2** (README, 2026-08-14 promotion).
- **Forensic decomposition (54-slate 2023–25 corpus, production stack):**
  H−P ≈ **4.06** (player-support loss), P−C ≈ **68.91** (combination/construction
  loss), C−S ≈ **5.01** (selection loss). Exact-P census: candidates sit a mean
  minimum of ~5 player-swaps from the pool-player hindsight optimum.
- **Book-tail calibration (frozen audit, 54 slates):** realized/expected clears
  17/16.01 at 187, **8/10.26 at 194 (over-predicted)**, 7/6.53 at 200,
  **6/2.76 at 210 (under-predicted)**; all intervals cross zero, candidate-level
  sim/actual Spearman ≈ 0.16–0.24. Weak signal overall, but the shoulder-over /
  extreme-under shape is the working hypothesis, with a same-law production
  remeasurement already queued.
- **CBWU-OI construction diagnostic (fixed 241–265 budget):** mean C
  181.07→186.73 (+5.66, positive every season); C tails 11/8/6 → 18/14/10 at
  194/200/210; **220/230/240 unchanged at 3/1/0**; pair reach +41%, stack-core
  reach +52%; selector-stability cost −4.81/80 disjoint-half overlap. Prospective
  paired shadow is wired (`CBWU_OI_SHADOW`), gated on discordant-pairs-at-194.
- **In flight / queued:** coherent-market-state chain running (parity → score-free
  → historical → production-law dependence watcher `1273069`); residual-world
  column generation fully implemented and score-free-GREEN through phase 4 plus
  the exact-pricing gate, awaiting source-lock/orchestration/launcher/harvester;
  DST lane at D0 complete with the outcome-based sizing step next; minimal ATLAS
  world-ranking C test implemented (predeclared negative prior); McNemar
  discordant-pair reanalysis is the top analytical item.

### The single most decision-relevant table

| Threshold | 187 | 194 | 200 | 210 | 220 | 230 | 240 |
|---|---|---|---|---|---|---|---|
| Selected book (107) | 34 | 24 | 13 | 7 | 5 | 3 | 2 |
| Pool oracle (107) | 43 | 31 | 19 | 9 | **5** | **3** | **2** |
| Recoverable by selection | 9 | 7 | 6 | 2 | **0** | **0** | **0** |

**At 220+, selection already captures everything the pool contains.** Selection
loss exists only in the 187–210 shoulder. Every additional 220/230/240 week must
come from *generation*: either a lineup the current generators never build, or a
world/belief state the current law never produces. This is consistent with the
54-slate corpus (CBWU-OI moved C at 194–210, not at 220+) and with the exact-P
census (combination assembly, not player coverage, is the failure). Any plan to
"create high-scoring boom lineups" should be scored against this table: shoulder
mechanisms and extreme-tail mechanisms are different problems.

---

## 2. Anatomy of the missing points

Three independent measurements agree on where boom capability is lost:

1. **Combination assembly (P−C ≈ 69).** The pool's players support the hindsight
   optimum to within ~4 points, but no generated candidate combines them; the
   closest candidate is ~5 swaps away. Candidates are individually-optimal
   solves (lev objective, top worlds, roles, stacks); nothing prices a lineup by
   its marginal contribution to uncovered tail states. Residual-world column
   generation is the accepted answer and is nearly ready.
2. **Missing joint co-boom mass in the law.** Marginals are, if anything, wide
   (walk-forward TabPFN audit: ordinary players' q90 exceeded only 7.37% vs
   nominal 10%), yet the *book* tail at 210+ realizes more than the sim expects
   (6 vs 2.76). Wide marginals + thin book tail points at under-modeled
   co-movement, and the system has three named, verified holes there:
   - **DST is constant across all 30,000/50,000 worlds** (`draw_idx=-1`,
     `DST_CORR_DRAWS=""`) — one of nine slots contributes zero world variance
     (only verified structural omission; D-lane in flight).
   - **Overtime is absent as a shared mechanism.** Measured on 2025's 14
     current-rule regular-season OT games: **+23.77 skill DK points per OT
     game**, +10.12 to the top-three sum, seven extra yardage-bonus crossings.
     At ~5% per game, ≈47% of 12-game slates contain an OT game. Marginals
     already carry OT mass (they're fit on real outcomes); the *joint* spike —
     same-game players booming together when a game goes long — is not in the
     law. The predictive OT model failed (AUC 0.507) so the duration shadow is
     unlicensed, but see S2 below: prediction is not required for the
     dependence-only version.
   - **Cross-team coupling is nearly independent** in the possession engine
     (factor corr ~0.1–0.2; `SCRIPT_FEEDBACK` chase/kill lever exists but is
     off, never panel-tested). Whether this is a deficiency is exactly what the
     queued production-law dependence scorecard will measure — real-game
     cross-team scoring correlation is itself ≈0.016, so do not prejudge.
3. **Rare individual booms on thin-history players.** 33/612 Milly-winner slots
   were absent from every candidate (+15.55 surprise, concentrated WR/TE);
   matched-pair analysis shows fast-role-rise +2.19 DK mean / +3.79pp P(20+)
   and vacancy/promotion +1.38 / +1.92pp, positive in all six seasons. The
   wholesale fast-role model was validly rejected; the targeted role12 arm is
   in production; tracking-traits shadow features on thin-history players are
   the open gate here.

---

## 3. Endorsements (in-flight work, with sequencing opinion)

Nothing below is new; it is the review's confirmation that the current queue is
pointed at the measured problem, with a recommended order for the one heavy slot:

1. **Residual-world portfolio columns** — highest-priority scorable experiment.
   It is the only mechanism in the codebase that optimizes the operator's
   actual utility *during generation* (`TAIL_THRESHOLDS_DK` 240→187,
   consecutive exact solves, K≤8 doses). Finish the remaining prerequisites
   (source-lock, 54-slate orchestration, stability, reviewed launcher, strict
   harvester) and give it the first heavy slot after the coherent chain.
2. **DST event lane (D0→D1/D2 + the paired outcome-based sizing step)** — the
   only verified structural omission; the sizing step (DST points-above-
   projection inside H/P solves, net of stack-side displacement) is cheap and
   correctly sequenced before modeling. Keep the predeclared two-sided prior:
   real DST dependence also *removes* coverage from opposing-offense stacks.
3. **CBWU-OI prospective shadow** — enable the two schedulers on build success
   as decided; grade on the frozen discordant-pairs-at-194 gate. This is the
   shoulder mechanism with the strongest fixed-budget evidence.
4. **Coherent-market-state chain** — let it run to historical completion; it
   unblocks the production-law dependence scorecard (watcher `1273069`), which
   in turn decides whether a sparse event-identity dependence repair (e.g.,
   exact QB↔receiver TD identities) is warranted. Do not design that repair
   before the scorecard exists.
5. **Minimal ATLAS C test** — cheap, decisive, already implemented; run it in
   queue order; a null closes the world-ranking family permanently.
6. **McNemar discordant-pair reanalysis of closed paired arms** — top
   analytical item; costs no slot; may change the read on several
   `unsupported-neutral` verdicts' evidential weight (diagnostic only — it
   cannot reopen a closed arm by itself).
7. **Week-1 operations lane** — contest fills, ownership, standings/payout
   capture, DKEntries rehearsal, odds-key rotation. Prospective 2026 data is
   the only non-mined evidence source left; every collector that isn't running
   by Week 1 forfeits a season of the one thing that can license adoptions.

---

## 4. New suggestions

Each is pressure-tested against the ledger; none reopens a closed family as
tested. All are adopt-only-as-proven and need frozen protocols first.

### S1. Null-calibrate the P−C gap (self-law forensic floor) — do this first

**Claim:** 68.91 is not the size of the prize. P is a hindsight max over an
astronomically larger lineup space than C's few hundred candidates, evaluated on
one realized draw. Even a generator holding the *true* outcome law would show a
large P−C gap from order statistics alone. Today nothing distinguishes "beliefs
are wrong by 69 points" from "any finite candidate set loses ~55 points to the
hindsight max even under perfect beliefs."

**Mechanism:** rerun the existing forensic decomposition (`decompose_slate`,
`_solve_oracle`) with the realized outcome replaced by held-out simulated worlds
drawn from the frozen production law itself (worlds outside the 50k selection
blocks, or a reserved block). For each of the 54 slates and each of W held-out
worlds: solve H and P on the simulated "actual," score C and S on it, and report
the distribution of self-law H−P, P−C, C−S. The observed 4.06/68.91/5.01 then
gets a same-instrument noise floor.

**Why it matters for boom capability:** it converts "construction is the
bottleneck" from a relative statement into a budgeted one. If self-law P−C ≈ 55,
the belief-plus-construction winnable gap is ~14 points and residual columns
plus CBWU-OI are plausibly most of the answer; if self-law P−C ≈ 25, beliefs are
far off and law work (DST/OT/dependence) deserves the marginal slot over more
construction. It also sets the honest effect-size prior for the residual-column
K-doses before their outcome is read.

**Ledger check:** no prior art found (searched handoff, ledger, forensic
modules; the Addendum 116 exposure-preserving null is a different quantity).
Score-free (reads no realized outcomes), so it does not consume the historical
outcome lease. Cost: one CBC-solve batch per slate×world — a small cloud job,
not the 32 GiB slot. Kill criterion: none needed — it is a measurement, and its
protocol should freeze W, the world-selection rule, and the reporting before any
number is seen.

### S2. Overtime as a dependence-only shared-duration mixture (v2 protocol)

**Claim:** the strongest *new* extreme-tail mechanism available without new data.
The failed piece of the OT work was predicting *which* games go to OT
(2022–24 spread/total model, AUC 0.507 on 2025). The valuable piece — OT adds
~24 concentrated skill points to one game — needs no prediction: a base-rate
mixture already changes the joint law in exactly the direction the 210+
under-coverage indicates.

**Mechanism:** with per-game P(OT) set to the frozen league base rate (optionally
lightly modulated only if a market OT/Draw price exists pre-lock — never by the
failed model), flag each simulated world's games as OT with that probability and
apply a shared duration uplift to that game's players, then **rank-remap back to
the unchanged marginals** (the established dependence-only transform pattern:
exact sorted-marginal preservation, mean delta ≤1e-10, as in the Route R2
harness). Player means/quantiles stay byte-identical; only *who booms together*
changes. Evaluate on the frozen dependence scorecard first (variogram,
joint-q90 Brier, multiplicity, hub families), then — only on a pass — one
fixed-budget candidate/oracle arm under standard laws.

**Ledger check:** the frozen OT protocol licensed only a market-priced duration
arm and its predictive gate failed, so this needs a *new* protocol (operator
decision), not a reinterpretation — the v2 estimand (unconditional base-rate
mixture, dependence-only) is materially different from the failed v1 estimand
(conditional prediction). It is not the closed TD-ledger (global coupling
increase), not CE/Gumbel (law deformation without weights): marginals are
exactly preserved and the mixture probability is a frozen constant. The bounded
`h2h_3_way` Draw-price availability probe at the first live 2026 window is
already planned — keep it; a real market P(OT) upgrades this arm later.
Predeclare the two-sided risk: mixing in OT worlds necessarily thins other
co-boom mass at fixed marginals.

### S3. Exact-weight importance tilting at the game-factor layer (rare-event v1)

**Claim:** the accepted rare-event priority (adaptive splitting / conditional
SMC) is gated on a restartable possession-simulator latent state, which does not
exist and is a real project to build. There is a v1 that dodges the
prerequisite: the extreme book states are driven substantially by the
game/team-factor layer, whose sampling distribution is known in closed form
(rounded-normal drive counts, pace multipliers, drive-chain draws). An
exponential tilt on total drive counts (or on the realized game factors) has
exactly computable likelihood ratios, so weighted same-law estimates stay
auditable without any simulator restart capability.

**Mechanism:** draw a stratum of worlds with tilted drive-count/pace parameters,
carry w = p(law)/p(tilt) per world, verify agreement with ordinary MC at 187/194
(the frozen Priority-4 gate structure), and use the weighted stratum as the
pricing set for residual-world columns (the review's Track A step 5), with
final cross-scoring on ordinary production worlds unchanged.

**Ledger check:** this is the same-law estimand with weights — the property that
distinguishes it from the closed CE/Gumbel/Schaake family, all of which
deformed the law without importance weights. It should be sequenced *after* the
first residual-column result: if columns priced on ordinary worlds already move
C at 210+, the extra supply may not be the binding constraint.

### S4. Marginal-vs-dependence attribution audit (cheap, diagnostic-only)

**Claim:** the shoulder-over/extreme-under calibration shape is currently
attributed to dependence by inference. One cheap audit can pin it: compare the
production shaped marginals' q90/q95/q99 against the market-implied quantiles
from alt-line ladders (`market_implied.py` — validated calibrated at q90,
Addendum 45) on the honest pre-lock snapshot, walk-forward, stratified by
position and breakout state; report exceedance and pinball loss alongside the
queued same-law dependence scorecard. If marginal upper tails verify while the
book tail stays thin, dependence is confirmed as the deficit and marginal work
stays closed; if specific strata (e.g., ordinary veterans wide, thin-history
narrow) fail, that licenses a *targeted* marginal repair rather than the
rejected generic widening.

**Ledger check:** distinct from the **closed** player-level market-tail feature
gate (that arm used signed disagreement as a *model feature* to predict
residuals and failed its 2024 separation gate). Here the market curve is the
*calibration instrument* and nothing feeds a model or candidate. Uses the
already-repaired pre-lock prop snapshot discipline (the post-lock line defect
found 2026-08-10). Costs no heavy slot. Output is a diagnosis that routes the
next law experiment; it licenses nothing by itself.

### S5. Boom-solve unique-fill inside CBWU (small, supply-side)

**Claim:** `_add_boom` solves the top-`N_BOOM` worlds in rank order; duplicate
optima are discarded, so the *effective* unique boom count per seed is <40 and
varies by slate. The CBWU-OI lesson, codified in the review's revision 9, is
that a fixed admitted budget should not require a fixed native supply.
`unique_target` already exists in the function signature and is unused by the
production path.

**Mechanism:** one arm that walks further down the (possibly ATLAS-ranked, if
the C test passes) world order until exactly 40 *unique* boom rosters exist per
seed, with the admitted budget unchanged (CBWU quota/fill untouched). Report
realized unique counts per slate as the mechanism audit.

**Ledger check:** not raw candidate scaling (CAND_MULT, closed — that scaled the
lev batch and admitted more); the admitted budget stays fixed. Not the closed
Gumbel/CE families (no law change). Prior is modest — mark it a shoulder
mechanism and batch it with, or behind, the residual-column work rather than
spending a slot alone.

### S6. Selector stability only as score-free engineering + prospective shadow

The CBWU-OI stability regression (65.69→60.87/80 disjoint-half) plus weak
sim-signal means book identity is partly a draw from selector noise. The naive
bagged selector is provably vacuous (already established); the genuinely
different objective — maximize a lower-confidence coverage bound across the
five world blocks (mean − λ·std, λ frozen; or worst-block coverage) — is worth
implementing **only** under the score-free stability harness
(`cbwu_oi_selector_stability`) and, if it improves reproducibility without
coverage loss, as a 2026 prospective shadow. **Never** as a historical selector
sweep: selection remains closed on the current signals, and the preregistered
reopening condition stands. This suggestion is operational (deployment
determinism, fewer coin-flip books), not a claimed tail gain.

### S7. New-information collection to satisfy the reopening condition

The preregistered paths that could legitimately reopen selection/construction
with new signal, ranked by expected value against the measured misses:

1. **Tracking-traits shadow features on thin-history players** (gate already
   defined; the 33 missed winner slots are exactly this population; in-season
   refresh via nflverse NGS weekly is free).
2. **Multi-book player-prop collection now** — the Addendum 96 cross-book
   dispersion NULL was measured on the signals then available; the 2026
   warehouse currently holds one book/one market, which cannot support a
   dispersion law. Collection is cheap and prospective; the retest happens only
   if/when real dispersion data exists (respecting the frozen evaluation-first
   rule).
3. **Regulation 3-way/OT market probe** (already planned) — feeds S2's upgrade.
4. **Activated evidence + contest-fill/ownership/payout capture** — already
   built/deployed; the discipline is just to have them live by Week 1.

### S8. A prospective "surprise ledger" for 2026

Formalize what the missed-player analyses did retrospectively: every scored
week, automatically record all players ≥20 actual DK points absent from every
candidate, with their pre-lock breakout-state classification, salary, ownership,
and which generator families came closest. Frozen format, append-only,
outcome-facing but decision-free. After 6–8 weeks this is the highest-quality
evidence for *which* belief mechanism (role, tracking, market, news) would have
generated the misses — the exact question the historical corpus can no longer
answer without mining. Cost: a small extension to existing grading jobs.

---

## 5. What not to do (closures respected)

- No selector/threshold sweeps on the 54- or 107-slate corpora (closed five
  ways; reopening condition preregistered and unmet).
- No CE/Gumbel/Schaake/GFlowNet revivals; no unweighted law tilts (S3 is
  weighted, S2 is marginal-preserving — those properties are the distinction).
- No raw candidate-volume scaling (CAND_MULT closed; capacity curve stays a
  later descriptive item where it is already queued).
- No generic role-model adoption, no generic marginal-tail widening (both
  rejected; the targeted role12 arm and calibrated exceptions stand).
- No DST_CORR_DRAWS multiplier revival — the D-series event lane supersedes it,
  and any D-series acceptance must engage the twice-negative record with
  instrument tail-calibration criteria (operator decision D2 already says this).
- No dollars/ROI objective until the field layer is rebuilt on real contest
  fill/duplication/payout data (field legality fix is in; data collection is
  the gate).
- No new heavy work that jumps the one-heavy-chain lease or touches the
  historical-outcome lease out of order.

---

## 6. Suggested sequencing

**Heavy slot (serialized):** coherent chain (running) → residual-world columns
54-slate run (after its prerequisites freeze) → minimal ATLAS C → DST D1/D2
event fitting → (conditional on scorecard) dependence repair or S2 OT arm →
(conditional on residual result) S3 weighted supply.

**Design/analysis lane (parallel, no heavy slot):** D0 gate-3 acceptance freeze
and DST sizing step (already next actions) → McNemar reanalysis → S1 null-gap
protocol + small solve job → S4 attribution audit → S2 v2 protocol draft for
operator review → S8 surprise-ledger spec.

**Season ops lane (hard deadline):** Week-1 runbook (odds key rotation,
contest-fill verification, shadow fleet + CBWU-OI schedulers, DKEntries
rehearsal, standings/payout capture), S7 collectors live before the first slate.

**Operator decisions requested:** (a) whether S1 and S4 may run as score-free/
diagnostic protocols in the design lane; (b) whether an S2 v2 OT protocol may be
drafted for review given v1's failed predictive gate; (c) priority order between
DST D1/D2 and the first residual-column score if both become ready for the same
slot; (d) whether S8's outcome-facing ledger is acceptable as a standing
post-settlement job.

---

## 7. Bottom line

The system's remaining boom-lineup gap is not one problem but three, and they
now have different best moves. The **shoulder (194–210)** responds to
construction breadth — CBWU-OI (proven at C, in shadow) and residual-world
columns (implemented, next in the queue) are the right bets, and selection has
~6–7 recoverable weeks there. The **extreme tail (220+)** is generation-bound —
selection already captures everything the pool holds — and the only mechanisms
that plausibly add pool mass there are missing *joint* co-boom sources: the DST
event lane, overtime as a dependence-only mixture (S2), a dependence repair if
the queued scorecard confirms under-coupling, and weighted rare-world supply
(S3) feeding the column generator. The **rare-individual-boom** losses are an
information problem, and only the prospective 2026 paths (tracking traits,
multi-book props, evidence, surprise ledger) can address them without mining.
Before spending the next heavy slot on any of it, S1's null-calibrated forensic
floor is a one-job measurement that tells you how much of the 69-point
construction gap is actually winnable — and therefore which of these three
problems deserves the season's scarce slots.
