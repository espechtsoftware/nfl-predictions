# Review of the Foundry crossed-arm retest and simulated-scoring plan

**Date:** 2026-08-27
**Reviewer:** Claude (Fable 5), independent review requested by the operator
**Document reviewed:** `reports/2026-08-27-foundry-crossed-arm-retest-and-simulated-scoring-plan.md`
**Companion:** `reports/2026-08-27-scoring-improvement-suggestions.md` (its "candidate shape" row has been reworded to distinguish the legacy incumbent corpus from the R6 seven-profile union, as the plan correctly requested)
**Status:** advisory; outcome-blind; authorizes nothing.

## Verdict in one paragraph

The plan is scientifically sound and its core decisions — relabel old results by feasible-set scope, make only DK legality hard, keep an incumbent sentinel, generate once and select repeatedly, separate population from retrieval, screen broadly on simulated banks and read history sparsely — are the right ones. My objections are almost entirely about **sequencing and omission**, not correctness. As written, the plan puts the experiments with the highest realized-tail potential (belief laws, late-swap recourse, entry count, union-structure of the book) either last, behind provenance work they do not need, or nowhere, and it does not name what ships as a shadow in Week 1 (≈two weeks away). Below, C-items are correctness findings; J-items are scientific-judgment differences. Each material objection carries replacement language or a concrete cell.

---

## Correctness findings

### C1 — Stage 0 gates Stage 1 on artifacts Stage 1 does not consume

Stage 0 requires the fixed-G0 catalog recovery authority, the fixed-G0 candidate authority, **seven immutable matchup/source packs across all 54 slates**, the terminal source-v2 root, and independent banks before Stage 1 runs. Stage 1 is defined as "using the already-generated R6 candidates and independent simulated bank … reconstruct profile-isolated corpora … apply every retained selector." Those inputs — frozen task results, world arrays, score matrices, and five R0–R4 blocks — already exist and were read in full by the deep review. Nothing in Stage 1 reads a matchup pack or a catalog root.

*Replacement language:* "Stage 1 runs immediately from the sealed R6 full-union freeze (`panel-freeze.json` generation `1787756181440564`) and the five R0–R4 world blocks. Stage 0 items are prerequisites for the **next generated bank** (Stage 2 onward) and for the matchup arm specifically; they are not prerequisites for the current-bank crossed baseline."

### C2 — The plan treats "independent evaluation bank" as a gate for selector primitives that can be evaluated today with rotated-block holdout

"Future selector candidates may include a slate-conditional target, explicit overlap caps, or anti-correlated 'evil twin' pairing. They should enter only after the reusable independent-bank contract is operational." These are pure array operations on the frozen candidate×world matrix. The R6 release already fits selectors on four blocks and holds out one (the rotated-scope results in the score report), which is an out-of-sample simulated evaluation. An independent CRN bank is a strict upgrade for precision, not a validity precondition.

*Replacement language:* "Selector primitives enter Stage 1 immediately under the existing rotated-block fit/holdout design; the independent CRN bank replaces rotated-block holdout when operational and the Stage 1 tables are re-emitted on it."

### C3 — The portfolio-stage endpoints omit the quantity the objective is made of

`P(max ≥ T)` is a union probability. The plan's portfolio row lists "player/game/arm/belief exposures; lineup overlap; modeled scenario redundancy" but not the effective number of independent tail events in the book (effective rank of the tail-event correlation matrix, or `(Σλ)²/Σλ²` on the candidate×world tail-indicator submatrix). Without it, two 80-books with identical coverage counts but 12 vs 60 effective shots are indistinguishable, and the eight-book Jaccard 0.995 finding would have been visible weeks earlier.

*Replacement language:* add to the Portfolio row: "effective independent tail shots at each ladder rung, computed on the evaluation bank; reported for every book, every stage."

### C4 — Retrieval comparisons across nested corpora need size standardization, not only density

Equal work and density per 1,000 distinct candidates are sufficient for **population** fairness. For **retrieval**, a selector applied to a larger union is compared against one applied to a smaller isolated corpus, and the union will be credited for size. The plan's isolated/incremental/LOO/Shapley views describe the corpora, not the selector.

*Replacement language:* "Every retrieval comparison across corpora of unequal size is also reported at equal distinct-candidate count via fixed-seed subsampling of the larger corpus (bootstrap over ≥20 subsamples), alongside the full-size result."

### C5 — The human loop, not the bank boundary, is the overfitting risk

The banks and folds are adequately separated. But everyone choosing Stage 5 finalists already knows, from the deep review, which profiles produced the seven 230+ rows and on which slates. The plan requires "a small frozen finalist set" without saying how it is chosen.

*Replacement language:* "Finalist selection rules are written as deterministic functions of the outcome-blind Stage 1–4 metrics (named metrics, thresholds, tie-breaks) and committed **before** Stage 1 output is published. The finalist set is produced by that rule, not by inspection."

---

## Judgment differences (with the tail potential that is at stake)

### J1 — Belief laws are the binding constraint at 230 and the plan starts building them last

Stage 4 admits belief laws "only if they pass independent walk-forward calibration," but no stage in this plan **constructs** them, and they enter after Stages 1–3. The evidence is unambiguous that schedulers, fill and profiles operating under the incumbent law cannot create tail mass the law does not have: candidate doubling raised availability and damaged the selected tail (Addendum 117); world optima are never winners (N1c); the R6 230+ rows carried 1–22 simulated >230 worlds out of 50,000; corpus 230+ availability is 3/54. Stages 1–3 will sharpen the picture of *retrieval* under one law and will not move 230+ availability materially.

The two highest-potential laws are (a) a two-regime game-environment law (shootout state raising pace, pass rate and both teams' factors jointly; the mechanisms — `GAME_SIM_PACE=vegas`, TD ledger, Dirichlet usage, big-play — are built and OFF), calibrated outcome-blind against public co-exceedance tables (QB+WR1 ≥50 pts in 15.3% of games, ≥70 in 2.1%; QB+WR1+RB1 ≥75 in 7.8%; opposing-WR1 correlation 0.56), and (b) a breakout/role-jump mixture on the marginals with historical base rates (33/612 winner slots absent from every candidate, +15.5 surprise). Both calibrate on `CAL19/WF21/HOLD22` player-level folds and consume no historical lineup lease.

*Replacement cell:* "Stage 1′ (parallel with Stage 1, starts now): construct laws `L1-shootout-regime` and `L2-breakout-mixture`; deliverables are the co-exceedance calibration table for the incumbent law and each challenger, joint-q90 tail Brier, variogram, marginal exceedance calibration at 20/25/30/40 by position, and a population census under each passing law on the R6 slate set with the seven profiles and equal solver work. Owner and calibration deadline named."

### J2 — Late-swap recourse is absent, and it is the only in-week source of genuinely new information

Realized 1 p.m. results are exactly the "genuinely new pre-lock signal" that Addendum 95 requires to reopen selection. The hindsight bound is +69 mean best; the +0.9 null (Addendum 67) tested q90-chasing from a book not built for it. The corrected two-stage design — recourse-aware initial book plus a 3:55 p.m. policy — is frozen (`reports/2026-08-17-recourse-aware-initial-book-*.md`, `analysis/recourse_aware_initial.py`) and unrun. It does not appear in this plan.

*Replacement cell:* add Factor F, decision stage ∈ {initial-only, initial+late-afternoon recourse}, crossed with the selector factor only; run the already-frozen score-free 54-shard execution now; register the "trailing entries become fresh late-game tickets" rule as a second variant.

### J3 — Entry count is the largest quantified lever and it is not a reported dimension

The R6 4/14/80 prefixes give mean weekly max 148.5 / 163.2 / 178.4 — log-linear in k. Extrapolation to DK's 150-entry cap is ≈ +5 mean weekly max, about three times the best selector gain ever measured (+1.55). Nested prefixes are free to emit.

*Replacement language:* "Every retrieval table reports k ∈ {4, 14, 80, 100, 150} nested prefixes. The k-curve fit `a + b·ln k` and threshold-hit curves are published so the operator can decide entry volume with the curve in hand."

### J4 — F7 isolates the pair, but the winner evidence asks for two targeted profiles, not only relaxations

F7 (remove QB and bring-back minima, keep floor and RB rules) does isolate the A3 interaction. The winner structure census motivates two *targeted* shapes that no current relaxation aims at: maximum game concentration ≤ 3 (69% of winners; mechanically unreachable when stack + bring-back are forced) and exactly one QB partner (41% of winners, the modal shape; a `qb_stack_max=1` producer already exists at `backtest/engine.py:1230`). Once a shootout law exists, a ≥5-from-one-game over-stack profile is the complementary hypothesis-driven cell.

*Replacement cells:* `F8-game-cap-3`, `F9-single-partner`, and (after J1) `F10-overstack-5`. All three carry an explicit structural hypothesis, satisfying the plan's own "no arbitrary lattice" rule.

### J5 — Primary endpoint

Use paired **mean weekly maximum** as the powered primary with a non-inferiority guard at 200+ hit weeks; 200/210 hit weeks and corpus regret as secondaries; effective tail shots and tail density as mechanism endpoints. Not a composite — composites hide which stage moved. 230 remains a case series until availability exceeds ~10 slates.

### J6 — A faster crossed design exists

Do not cross all five factors. Essential crossings: profile×selector (Stage 1, free); law×profile (relaxed shapes only pay if the law values them — the census already flagged this tension); law×selector (the joint multi-law book). Scheduler is a main effect screenable outcome-blind alone. Fill×profile: screen fill on outcome-blind tail density, cross only the finalist fill. This is a fractional factorial that preserves every interaction with a stated mechanism and drops the ones without one.

### J7 — Retiring an arm

Retire only when, at equal work, an arm fails the outcome-blind population endpoints under ≥2 belief laws **and** its leave-one-arm-out union loss is ≈0 — never on one historical null under one partner (the plan's own principle). Symmetrically, cap resurrection at two crossed retests so no arm lives forever on "wrong partner" grounds.

### J8 — Universally hard rules

Agree: none beyond DK legality. The salary floor excludes zero winners and its deletion failed a safeguard once; keep it soft and let the crossed design decide.

### J9 — Too cautious / not cautious enough

Too cautious: C1, C2, J1 (serialization), and the absence of any named Week-1 shadow. Not cautious enough: Stage 6 says "freeze the leading portfolio before each slate" without stating **what** leads or **how** it is produced live. The R6 foundry has no prospective path, but the served path already exposes the levers (`SELECT_LADDER`, `STACK_BRING_BACK`, `qb_stack_min`/`bring_back_min`, the `nostk` producer, per-family `N_*` budgets), and the `shadow-k1`/`shadow-k3`/`shadow-cbwu-volume` job pattern exists.

*Replacement language for Stage 6:* "Week-1 shadows are named and frozen by 2026-09-04: **S0** incumbent sentinel; **S1** relaxed-producer union (nostk/no-bring-back sleeves at the R6 arm proportions) + 200/210/220 tail ladder, the strongest documented historical book (178.4 vs 176.1); **S2** = S1 selected for late-game option value with the 3:55 p.m. recourse policy. Each is an env-configured `shadow-*` job on the existing image pattern, graded weekly against the incumbent under the frozen realized rule. Stages 1–5 may replace S1/S2 for later weeks under a new prospective clock; weeks before a version's activation never count for it."

---

## Answers to the plan's ten questions, in order

1. Yes, with one addition: the A7 ladder null should be labeled "null on incumbent candidates under the Phase-S research law" — it has since been contradicted on the R6 union (tail ladder +1.55 over coverage-194), which is precisely the plan's thesis.
2. F7 isolates the pair; add F8/F9 (and F10 after a shootout law) as targeted profiles — J4.
3. Essential: profile×selector, law×profile, law×selector, decision-stage×selector. Screen alone: scheduler; fill (cross only the finalist).
4. Sufficient for population; retrieval also needs size-standardized subsampling — C4.
5. None — J8.
6. Bank/fold boundaries are strong; the finalist-choice rule must be pre-committed — C5.
7. Paired mean weekly maximum with a 200+ non-inferiority guard — J5.
8. Fractional factorial — J6; and run Stage 1 today — C1/C2.
9. Failure at equal work on outcome-blind population endpoints under ≥2 laws with ≈0 LOO union loss — J7.
10. Too cautious on provenance-before-science and serialization; not cautious enough on the unspecified Week-1 deliverable — J9.

## What I would do in the next ten days, in priority order

1. Run Stage 1 today from the sealed R6 freeze, including effective-tail-shots, k-prefixes, the per-slate random-book null, γ caps and evil-twin pairing under rotated-block holdout (C1–C3, J3).
2. Start L1/L2 belief-law construction and player-level walk-forward calibration in parallel (J1).
3. Execute the frozen recourse-aware initial-book protocol (J2).
4. Freeze and schedule S0/S1/S2 Week-1 shadows (J9).
5. Continue Stage 0 provenance for the next generated bank without blocking 1–4.
