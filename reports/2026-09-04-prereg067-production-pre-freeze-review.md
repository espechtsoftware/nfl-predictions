# Production pre-freeze review: PREREG-067 / experiment 096

**Date:** 2026-09-04  
**Reviewed lab implementation:** `464a466320326ae9bded8e0ea35e50585ec99d23`  
**Disposition:** treatment mechanics acceptable; two reader/co-report gaps should be repaired before the efficacy freeze

## Scope and validation

Production reviewed the runner, mechanics gate, reader, focused tests,
preregistration, conditional design, and draft launch contract from a clean
detached worktree. The focused suite passed 24/24. Ruff and Python compilation
also passed.

The implemented treatment matches the decision-bearing Route C1 mechanics:

- the exact shared redistributed D800 pool and shared P_MIX judge;
- an eight-seat beneficiary-rescue sleeve;
- eligibility from the 094/095 participation relation;
- priority equal to current-book marginal expected-max value multiplied by
  `1 - min(linked P_active)`;
- recomputation after each accepted swap;
- removal restricted to remaining original control-book members;
- deterministic tie rules;
- an outcome-disabled 2022-W8/bank-700 mechanics boundary; and
- disjoint held-out-bank identities for the D3 co-report.

No issue found requires changing the arm, dose, priority law, bank cohort, or
primary endpoint. The current local mechanics smoke may finish unchanged.

## Required pre-freeze corrections

### 1. Preserve the preregistered D2 `both` class

`PREREG-067-DESIGN.md` and `PREREG-067.md` require D2 classes for designated
rostered, beneficiary with linked absence, neither, and both. The current
reader defines only:

- `designated_rostered`;
- `beneficiary_linked_absent`;
- `beneficiary_linked_played`; and
- `neither`.

It tests `has_designated` first, so a lineup containing a modeled designated
player and a linked beneficiary is absorbed into `designated_rostered` even
though the trace's nonempty `linked_designation_ids` can identify that
combination. Add an explicit `both` branch before the designated-only branch,
then retain the absent/played split for beneficiary-only lineups. Add one
focused reader regression proving all classes are reachable and exclusive.

This is a diagnostic-only repair and must not alter selection or the primary
verdict.

### 2. Implement or explicitly amend the mandatory D4/N2 co-report

The frozen conditional design calls D4 spike robustness (N2 decomposition) a
mandatory diagnostic. The implementation and launch contract currently list
and emit D1, D2, D3, and D5 only. Before freezing efficacy, do one of:

1. add the already-defined N2 decomposition as an immutable reader-side
   sidecar/co-report using exact roster-hash settlement joins; or
2. if the required N2 inputs cannot be reopened without expanding the 096
   artifact, commit a pre-outcome amendment that names the exact existing N2
   artifact and states that D4 will be run after the first read as a
   non-decision-bearing sidecar.

Do not silently omit it. D4 must remain outside the selector and must not
change the primary verdict or promotion rule.

## Non-blocking cleanup

- Change the reader's two stale `092 metadata` error strings to `096
  metadata`.
- In the prose, `1 - min(P_active)` is the largest linked absence
  probability; avoid describing it as the absence probability of the
  “highest-confidence” active designation unless that terminology is defined
  explicitly.

## Launch route

After the clean real-artifact smoke passes, repair the two co-report gaps,
rerun the focused tests and the same outcome-disabled mechanics validation,
then freeze and return the single-file launch contract with exact source,
image, gate-run, and gate-receipt identities. Production will then build and
launch banks 700-702 through the registered lanes. Experiment 091 remains
held, and PREREG-068 / experiment 097 remains unexecuted.
