# Forensic implementation review, and one remaining gap

Date: 2026-08-14. Review of `research/final_forensic*.py` and the executed
forensic run. **No code was changed. No outcome was queried.**

---

## 1. The implementation is comprehensive

It covers substantially the whole of the end-of-program forensic plan, plus
both ideas raised earlier today.

| plan item | implementation |
|---|---|
| §1 L1–L4 master decomposition | `decompose_slate`, `_solve_oracle` |
| EVT on weekly maxima | `evt_diagnostic` |
| recourse ceiling | `recourse_ceiling_slate` |
| pool-admission check | `route_pool_admission_diagnostics` |
| §6.1 missingness as error predictor | `feature_missingness_diagnostics` |
| §4 regime and drift | `regime_and_drift_diagnostics` |
| §5 ownership | ownership handling throughout (69 references) |
| §3 winner benchmarking | `winner_benchmark`, `audit_roster` |
| rank metrics | `_ndcg`, `_average_precision` |
| calibration | `player_calibration_diagnostics`, `_normal_crps` |
| candidate forensics | `candidate_scorecard`, `aggregate_candidate_diagnostics` |
| uncertainty | `_bootstrap_mean_interval`, `paired_scope_diagnostics` |
| §0.1 preregistration discipline | `build_freeze_manifest`, `validate_freeze_manifest`, `manifest_digest` |

Three items I expected to have to argue for are already handled:

- the **recourse ceiling distinguishes hindsight from realistic** — the
  distinction that determines whether a large ceiling is convertible;
- **liveness is tracked per stage**, which is the input a real recourse policy
  needs and the diagnostic that explains *why* the ceiling is whatever it is;
- **ownership is scored against the submitted book**, closing a gap where
  103,556 rows across 1,258 contests had been used only as a twice-rejected
  fade coefficient.

The freeze-manifest machinery is the right shape for §0.1: it makes the
"pre-register the complete list before running any of it" rule mechanical rather
than aspirational.

## 2. The gap: between-arm variance across the fourteen panels

This was §6.4 of the plan and I find no trace of it — no cross-panel pooling,
no `weekly_max ~ arm + slate` fit.

It matters more than its position in the plan implied.

The **incumbent seed-variance result** established the *within*-arm noise floor:
how much a book moves when only the seed changes. Between-arm variance is the
complement: **how much do differently-configured arms differ once slate effects
are removed?**

Together they answer the question every gate in this project has needed and none
has had — **how large must a threshold delta be before it means anything** — and
they permit decomposing observed arm-to-arm variation into a seed component and
a mechanism component.

Concretely, that would have changed how several past decisions were read. The
fitted-usage adoption turned on `2→3` at 240 and `2→3` at 230 with zero weeks at
both on the evaluation panel; the pass-tail result on `+2/+2/+3` across nested
thresholds. Neither was ever placed against an empirical distribution of "what
does an arm-to-arm difference normally look like."

### Protocol sketch

1. **Population.** All complete, mechanically valid panels on their common
   slates. Fourteen candidate panels exist; state the exact list and the common
   slate set in the manifest.
2. **Model.** Fit `weekly_max ~ arm + slate` (arm and slate as factors) and
   report the arm-variance component, the residual, and their ratio. Report the
   same on the threshold indicators at 200 and 210, where counts still support
   estimation.
3. **Outputs.** The standard deviation of arm effects; the implied minimum
   detectable difference at conventional power; and the placement of each
   historical adoption's observed delta within that distribution.
4. **Constraints, preregistered.**
   - The fourteen panels are the arms that were *chosen* to be launched, so
     pooling inherits that selection. State it; do not correct for it silently.
   - Panels differ in more than one lever, so arm effects are not clean
     contrasts. The estimand is the **dispersion** of arm effects, not any
     individual arm's effect.
   - **This may not revive, re-adjudicate or relabel any rejected arm.** Its
     output is a variance estimate and a reporting standard for future work,
     nothing else.

### Why now

It is the cheapest remaining item in the entire program: fourteen panels already
exist on common slates, no new execution, no new data, no acquisition. And it is
the one output whose value is *retrospective as well as prospective* — it
contextualises the existing ledger at the same time as it sets the bar for 2026.

## 3. Two interpretation notes for reading the outputs

These apply to the run that has already executed, so they are reporting rather
than design changes.

### 3.1 Carry distinct-slate counts wherever a nested grid appears

Any output reported as a `240/230/220/210/200/194/187` grid — the recourse
ceiling above all — should carry the count of **distinct slates improved**
alongside it.

The thresholds are nested: a week crossing 220 necessarily crosses 210, 200 and
194. A ceiling reported as "+2/+2/+3" may be three slates rather than seven
improvements. The same caution applied to the pass-tail result, and it applies
with more force here, because a ceiling is an upper bound that will be quoted
in the register.

### 3.2 The register's `size_estimate` should take the realistic figure, not the hindsight one

The perfect-hindsight recourse ceiling assumes knowledge of the outcomes of the
very games being swapped into. It is a valid bound and worth reporting, but it
is structurally unattainable.

**The realistic-recourse figure — early results known, late games only
simulated — is the convertible quantity**, and it is what belongs in the
opportunity register's `size_estimate` field. If the hindsight number lands
there unqualified, the 2026 charter inherits an opportunity nobody can realise,
and the gap between the two will be rediscovered expensively.

Report both; register the smaller.

---

## Summary

No design changes needed to what has run. One addition worth making as a
tracked addendum — **between-arm variance across the fourteen existing panels**,
which is nearly free and answers the standing question about how large an effect
must be to be believed. And two reporting conventions for the outputs: distinct
slate counts beside every nested grid, and the realistic rather than hindsight
recourse figure in the register.
