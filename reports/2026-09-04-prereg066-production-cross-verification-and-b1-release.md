# PREREG-066 / experiment 095 production cross-verification and B1 release

**Date:** 2026-09-04  
**Production branch:** `codex/week1-pmix-live-certification`  
**Lab seal commit inspected:** `f6c85c98a7a84d2254ba00307c67e7cec1404b22`  
**Disposition:** 095 novelty retrieval closes; redistributed supply remains eligible for exactly one Work Package B diagnostic

## Scope

Production independently reproduced the frozen PREREG-066 reader after the
lab committed its first-read transcript and ledger entry. This review does
not amend experiment 095, adopt a lineup policy, authorize experiment 091,
or inspect any new outcome family. It adjudicates only the already specified
B1 condition in the production-to-lab generation/selection follow-up plan.

## Identity and terminal-state checks

- Runs: `095b690r1-20260904T164737Z`,
  `095b691r1-20260904T165019Z`, and
  `095b692r1-20260904T180305Z`.
- Cloud Run executions: `lab-run-t92g4`, `lab-run-slow-46fg6`, and
  `lab-run-wf6d7`; each completed 18/18 with no failed task.
- Frozen reader SHA-256:
  `e7d725b07ef2405644b5f398004e7a1f59774d7ecb9bf54f183dcfd96b987875`.
- Lab transcript SHA-256:
  `044cc4c2b0c9554875e6396b653be7d75b8d12d5b1e6f2228dfce885638beb0f`.
- The production reader ran from a clean detached worktree at lab commit
  `f6c85c98a7a84d2254ba00307c67e7cec1404b22`, exited zero, emitted the same
  SHA-256, and compared byte-for-byte equal to the committed transcript.
- The committed `PREREG-066.md` disposition and `LEDGER.md` row agree with
  that transcript. No conflicting run, arm, primary, family level, or
  interpretation was found.

## Reproduced result

- Primary `REDIST_NOV - REDIST_DEMAX`:
  `+0.00195`, family interval `[-0.00212, +0.00693]` —
  **UNPASSED_NEAR_MISS**. Conditional-novelty retrieval therefore closes in
  its tested form. There is no ladder, weight search, K search, or adoption.
- Prespecified interaction:
  `+0.00112`, family interval `[+0.00035, +0.00158]` — **PASS**. This is
  development evidence that the effect of retrieval differs on redistributed
  supply; it is not evidence that the tested novelty law is adoptable.
- Safety veto: both novelty books exceeded the control contamination rate.
  The novelty arms remain unadoptable regardless of their descriptive values.

## B1 eligibility decision

Production releases Work Package B exactly once. The release is justified by
the supply evidence, not by the failed novelty primary:

1. The redistributed pool contains 278 candidates at or above 200 versus 222
   in control, with mean pool oracle 194.438 versus 193.632.
2. `REDIST_DEMAX` lowers selected-roster contamination to 15.91% from the
   `CTRL_DEMAX` rate of 16.36%; the eligible diagnostic therefore does not
   depend on the vetoed novelty books.
3. The prespecified positive interaction is consistent across all four
   leave-one-season-out cuts and establishes that the redistributed supply
   can interact differently with retrieval, even though the tested novelty
   law failed to convert it.
4. Only 13 of 92 redistributed-only beneficiary candidates scoring at least
   200 were captured by either tested retrieval law. That is the exact
   beneficiary-rescue question Work Package B was frozen to diagnose.

This is a narrow scientific-eligibility determination. It does **not** claim
that redistributed generation improves the realized K80 maximum, that the
beneficiary flag is predictive, or that Route C1 will be eligible. Work
Package B must use the already frozen binary statistic, support rules, sealed
095 cohort, and exactly-once publication contract. Its result alone selects
one downstream route:

- `RESCUE_ELIGIBLE` routes to PREREG-067 / experiment 096;
- `INSUFFICIENT_SUPPORT` or `RESCUE_NOT_SUPPORTED` routes to PREREG-068 /
  experiment 097.

The lab must not run both routes. Experiment 091 remains held. No Week-1 live
policy changes as a result of this release.

## Next action

Publish a tracked `prereg066-wpb-eligibility-release/v1` receipt in the lab
repository binding this production decision commit, the exact sealed
transcript SHA-256, and the three run IDs. The lab may then execute
`scripts/prereg066_rescue_relevance.py` once and commit its create-once result
before implementing or launching the single routed successor.
