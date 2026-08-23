# Review: recent failures (residual pricing gate, Week 1 operations, surrogate audit)

Date: 2026-08-18. **No code was changed. No outcome was queried.**

Covers the failures recorded since 2026-08-17 midday: the two residual
exact-pricing gate failures and their repair, the Week 1 operations P0, and the
selected-book tail calibration audit that ran alongside them.

**Headline: none of these is a scientific failure. One repair is numerically
incoherent and should be reversed in direction. The calibration audit is the
most important thing in the window and its strongest finding is not the one it
leads with.**

---

## 1. Residual exact-pricing gate — correct triage, questionable repair

The deferred five-case local gate returned 3 passed / 2 failed after 3,003.70s:

| case | result | cause |
|---|---|---|
| rank-sum ambiguity | pass (5.31s) | — |
| exact no-good next-identity | pass (891.45s) | — |
| semantic evidence binding | pass (1,011.70s) | — |
| exact pricing / brute / player-row-order | **fail** (1,034.25s) | CBC token `9.0315311e-11` exceeded decode epsilon `1e-11` |
| all-three positive-part | **fail** (60.34s) | retained row-display reconstruction rejected one row |

**The triage is right.** Both failed closed at the proof/parser boundary; neither
reached a wrong-roster or wrong-objective assertion. Refusing to rerun or widen
a tolerance before classifying the raw tokens was the correct instinct.

### 1.1 The row-activity removal is correct

Removing the row-activity reconstruction check (`residual_world_columns.py`, now
`_ = row_activity[row]`) is well reasoned. CBC's printed row value is computed in
its own floating-point context, while each printed column token is independently
rounded; recomputing row activity from rounded column tokens and demanding
agreement within a display quantum **checks the printer, not the solution.**
Retaining the token in the solution hash while removing its gating authority is
the right resolution. No objection.

### 1.2 `integerTolerance 1e-12` is the wrong direction and should be reversed

The repair tightened `CBC_INTEGER_TOLERANCE` from `1e-9` to `1e-12` so that CBC
would branch until every integer variable prints at a bound, rather than
loosening the `1e-11` decode epsilon.

I verified the option is genuinely applied — CBC reports
`integerTolerance was changed from 1e-07 to 1e-12` under the exact
single-string option form the code uses. So the mechanism will work. Three
problems remain.

**(a) It is now 1000x tighter than the configured primal tolerance.** The same
options list sets `primalTolerance 1e-9` (`residual_world_columns.py:624`).
Certifying integrality to `1e-12` on an LP solution that is only feasible to
`1e-9` asserts precision the underlying simplex does not provide. CBC's own
default is `1e-07`; the configuration now sits five orders below it and three
orders below its own feasibility tolerance. **An integer tolerance tighter than
the primal tolerance is not a stronger proof — it is an incoherent one.**

**(b) The cost lands in the failure class that has already cost six grids.**
Forcing branching until every variable is bound-fixed deepens the tree and
lengthens solves. The gate already took 3,003s locally with individual cases near
1,000s. Column generation over 54 slates x residual worlds x iterations is
exactly where ATLAS repair2-repair5 died on CBC `PulpSolverError`, `SIGKILL` and
memory limits. This repair increases that risk rather than reducing it.

**(c) The anti-weakening law does not apply here.** The CLAUDE.md rule — never
weaken a check to make a build go green — governs **leakage checks and scientific
gates**. A floating-point decode threshold on a solver token is neither. The
check's entire question is *"is this variable 0 or 1?"*, and `9.03e-11` answers
it unambiguously: it is eight orders of magnitude from the `0.5` decision
boundary. Treating a numeric decode threshold as a scientific gate is a category
error, and it has produced configuration (a).

**Suggestion:** reverse the direction. Set the decode epsilon to the solver's
guaranteed tolerance — at least `primalTolerance`, i.e. `1e-9` — and restore
`integerTolerance` to `1e-9`. That is justified by CBC's own numerical contract
rather than by convenience, keeps the two tolerances coherent, and removes a new
solver-reliability risk from the critical path. If an exact self-certifying proof
is genuinely required, the correct instrument is the retained MPS plus the
canonical integer assignment (which the repair already names as decisive), not a
tolerance below the LP's feasibility floor.

---

## 2. Week 1 operations P0 — the audit working as intended

The read-only audit found that `nfl_forensic_review` holds **both** the original
four `final_forensic_20260814_*` tables and four authoritative `_repair4`
tables, while `cleanup_final_forensic_warehouse.py` and
`resume_2026_production_schedulers.py` accepted and verified only one four-table
manifest. The flow could therefore **delete the originals, leave the repaired
corpus live, and still resume 27 production schedulers.**

Verified: all eight tables are present, and the cleanup script now requires both
manifests (`REQUIRED_MANIFEST_SUFFIXES = frozenset({"", "_repair4"})`, with
`--manifest` supplied once per freeze).

**This is a genuine data-destruction risk caught before it fired, and fixed the
same day.** It is the clearest justification for the audit discipline in recent
memory and should be recorded as such rather than filed as another failure.

Two items from the same audit should not wait:

- **Literal `ODDS_API_KEY` values in non-odds jobs.** Remove them and rotate the
  provider key if those values are live. This is a standing credential exposure,
  not a research question.
- **`dk_contest_fills` is implemented but empty and has no deployed job or
  schedule.** This is the single dataset the project has never had and cannot
  reconstruct retrospectively. It needs a running collector before the first live
  slate, not after.

---

## 3. Selected-book tail calibration — the important result, and a framing issue

This is the surrogate-validity test, and it is well executed: 54 slates, 50,000
worlds per book, 10,000 stratified resamples, and an independent stdlib-only
reimplementation that recomputed every aggregate with zero mismatches
(max delta `4.44e-16`).

### 3.1 The stated conclusion is underpowered, not negative

Every Brier-skill interval crosses zero and every ROC-AUC interval crosses 0.5.
But with **6 to 17 events per threshold**, intervals crossing zero is close to
guaranteed *regardless of whether signal exists.* The honest label is
**uninformative at this sample size**, not *calibration not demonstrated* — the
latter reads as a negative finding to anyone skimming.

The document is careful in places ("diagnostic clues rather than licenses",
"does not support the stronger claim that the simulator is useless"), and
consequence 1 — do not use simulated book coverage as the sole promotion or
closure criterion — is the right operational conclusion. But it is right because
of **the six mechanisms that passed simulated criteria and failed realized
outcomes** (Schaake, three Gumbel variants, CE, fast-role), not because of these
confidence intervals. The evidence chain should say so.

### 3.2 The strongest finding is the direction, not the intervals

| threshold | realized | expected from simulated q | ratio |
|---:|---:|---:|---:|
| 194 | 8 | 10.26 | **0.78 (over-predicted)** |
| 200 | 7 | 6.53 | 1.07 |
| **210** | **6** | **2.76** | **2.17 (under-predicted)** |

The simulated book-maximum distribution is **too fat in the shoulder and too thin
in the tail.** At 210 alone this is roughly 2 standard deviations under a Poisson
reference — suggestive, not decisive.

**What makes it decisive is that it agrees with an independent measurement.** The
dependence diagnostic found an under-coupled QB hub (realized QB→WR 3.32 versus
simulated 2.42) with over-produced high multiplicity. An under-coupled hub
produces *too few* correlated tail outcomes — exactly the 210 shortfall — while
inflating middling co-exceedance, which is exactly the 194 excess. **Two
independent measurements, different methods, same shape error.**

That convergence is far stronger evidence than any single interval in the table,
and it points directly at consequence 3 (upstream marginal/dependence
calibration) as the correct next work. It deserves to be the headline.

One caveat to carry: the dependence figures were measured under the
**fitted-Dirichlet research law**, not the production multinomial law. The
frozen production-law remeasurement should confirm the shape before this
convergence is treated as established.

---

## 4. Overall

Against yesterday's process assessment, this window is a marked improvement. The
surrogate audit was run, the DK-legal forensic layer was added, the DST event
frame was implemented, residual column generation was built, field legality was
fixed, and a shared heavy-experiment lease now serializes the queue — essentially
every outstanding recommendation.

**None of the three "failures" reviewed here is scientific:**

| item | class | disposition |
|---|---|---|
| Two pricing-gate failures | numeric decode / parser boundary | triage correct; **reverse the tolerance direction (§1.2)** |
| Week 1 cleanup P0 | operational, caught pre-fire | **process success**, already fixed |
| Calibration audit | underpowered but informative | **reframe around the shape error (§3.2)** |

| # | action | priority |
|---|---|---|
| 1 | **Reverse the tolerance repair**: decode epsilon `>= 1e-9`, `integerTolerance` back to `1e-9` | **high — on the critical path** |
| 2 | **Rotate the Odds API key** and strip literal values from non-odds jobs | high |
| 3 | **Deploy a `dk_contest_fills` collector** before the first live slate | high |
| 4 | Reframe the calibration result around the 194-over / 210-under shape error and its agreement with the dependence diagnostic | medium |
