# Production independent review of PREREG-059 / experiment 090

Date: 2026-09-03  
Production review basis: lab `main` at `db571c567a3b22319d2bf6bf5e6123c825a5dd5f`  
Disposition: **the accepted 090 result is valid for non-adoption of the exact frozen arm; no 090 rerun is requested**

This is the production response that was previously communicated to the
operator but had not been written to a shared repository file. It is intended
for the lab's 088/090/087 cross-verification queue. It does not block the 085
mechanics gate, build, or launch.

## Production finding

The accepted 090 cohort was an operationally successful experiment with a
scientifically negative adoption result. All three efficacy executions
completed 18/18 tasks with zero failures and zero retries:

- bank 630: run `090b630r1-20260903T005015Z`, execution `lab-run-xgczs`;
- bank 631: run `090b631r1-20260903T005253Z`, execution
  `lab-run-slow-kdkkg`;
- bank 632: run `090b632r1-20260903T020559Z`, execution `lab-run-bzkvv`.

The mechanics execution `lab-run-rghm8` also completed 1/1 with zero retries.
The accepted cohort contains 54 result objects, 216 validated bank-slate-arm
groups, and 72 unique historical slates. Image, source, resource envelope,
candidate lineage, settlement joins, selected-book lineage, and exact-K
mechanics passed the frozen reader's fail-closed checks.

Production independently reran the frozen reader. It reproduced the lab's
published numbers exactly. The independent transcript has SHA-256:

`e9cdb5e628d75969ed9420fcac5cd90faf47a1b72bd8dfb84abb56754516e167`

The decision-bearing results reproduced were:

- proxy delta, `RG_COHERENT - RG_CTRL`: `-0.00388`, family interval
  `[-0.01220, +0.00428]`;
- bank proxy deltas: `-0.0044514`, `+0.0072850`, `-0.01448375`;
- win/loss/tie: `32/40/0`;
- all four leave-one-season-out estimates negative;
- sign-flip `p = 0.505`;
- realized K80 weekly-maximum delta: `-0.601`, interval
  `[-1.651, +0.449]`;
- realized bank deltas: `+0.747`, `+0.055`, `-2.604`;
- control versus treatment mean weekly maximum: `181.096` versus `180.495`.

The frozen arm therefore should not be adopted. A rerun of the same arm would
not add decision value merely because the result was unfavorable.

## Required scope of the conclusion

`FAIL` is the preregistered adoption category. It is not statistical proof
that the intervention is generally harmful: the aggregate intervals include
zero, the randomization result is not significant, and bank 631 was positive.

Production therefore recommends this wording:

> The exact PREREG-059 additive coherent overlay, at its frozen dose and under
> the current historical panel and winner proxy, did not transport and is not
> adopted. This closes dose search for that preregistered additive arm. It does
> not establish that all dependence models or all materially different
> coherent interventions are harmful.

The lab's phrases "old-stack artifact" and "the overlay family closes" are
acceptable only with that frozen-arm/frozen-dose scope. They should not be
read as a causal finding covering every joint-law design.

## Test-quality assessment

The final accepted cohort was tested sufficiently and its non-adoption
decision is trustworthy. The original launch package, however, was not fully
correct when first declared ready:

1. The reader carried stale PREREG-056 gate/schema identities.
2. The influence trace incorrectly described shared joint worlds even though
   treatment changed generation and selection worlds.
3. Production's first launcher attempt also exposed an overly strict
   eight-character image-tag SHA check against a seven-character tag.

All three faults failed closed before outcome-bearing execution. The lab's
pre-execution repair at `bed33a6` changed no arm, dose, endpoint, or outcome.
Tree comparison confirms that the experiment module, `src/nfl2`, benchmark
data, runtime configuration, and Docker inputs used by the accepted image did
not subsequently drift.

The real-artifact, outcome-blind mechanics gate was the important protection:
it exercised an actual 800-candidate slate and validated four-arm generation,
mixture identities, exact K80, candidate and selection lineage, registry
probing, and the no-outcome boundary. The efficacy reader subsequently
validated those contracts on every result.

There is still a test-coverage improvement for future experiments: 090 has
generic joint-law and launch-contract tests, but no dedicated negative unit
test module for `experiments/090_regime_overlay.py` or
`scripts/prereg059_mechanics_gate.py`. This is future process work and is not
a reason to invalidate or rerun the accepted result.

Also retain the following external-validity limits:

- the panel has 72 reused historical slates over four seasons and no untouched
  holdout remains;
- the objective uses the pooled 48-winner `winner_cdf_v1` proxy pending
  registry-v2 adjudication, not a same-slate live win probability;
- the reported approximately 93% row engagement was demonstrated in smoke
  evidence; the full reader proves positive engagement on every slate but does
  not publish a full-panel 93% aggregate.

These limits make 090 a valid development-screen rejection, not a universal
live-performance theorem.

## Lab action requested

Only two closeout actions are requested, and neither should delay 085:

1. Commit the exact frozen-reader output transcript and its SHA-256 alongside
   the PREREG-059 seal. The current lab seal records the result but does not
   include a standalone durable reader-output artifact comparable to the 087
   evidence package.
2. Scope the terminal wording to the exact frozen additive arm and dose, as
   stated above. No scientific rerun, new arm, image rebuild, or 085 queue
   change is requested.

Production's 090 cross-verification is complete subject only to those
non-blocking evidence-package and wording corrections.
