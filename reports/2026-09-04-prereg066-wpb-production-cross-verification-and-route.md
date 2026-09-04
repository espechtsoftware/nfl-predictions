# PREREG-066 Work Package B production cross-verification and route

**Date:** 2026-09-04  
**Lab seal commits:** `7aad955e645d5875e8bdbdffcdc83b1e9e1d858f`, action-note seal `71c3978bcb253e98ee645a27cdd1d1a21115c0b2`  
**Disposition:** `RESCUE_ELIGIBLE`; route exclusively to PREREG-067 / experiment 096

## Verification

Production reopened the committed create-once artifact
`results/prereg066_rescue_relevance_v1.json` and confirmed SHA-256
`7632fcf4bb827cda6346f8d7f5ed3a10c9cb247fd5c2acbfc7ada4d46fc68855`.
It binds:

- the exact sealed 095 transcript SHA-256
  `044cc4c2b0c9554875e6396b653be7d75b8d12d5b1e6f2228dfce885638beb0f`;
- reader SHA-256
  `e7d725b07ef2405644b5f398004e7a1f59774d7ecb9bf54f183dcfd96b987875`;
- WP-B script SHA-256
  `303e4f7aed139a9ab35b2429f8647803e8ea707c205aaf4edf19335e01bd302d`;
- analysis/release-head commit
  `e84467dcca80944d544cd9d5ad0256869882439f`; and
- production release commit
  `b5d9db1a42ae56b5b57e35b4c3b189ade13055a5` and release-receipt SHA-256
  `a1ba23cab29daf19cee261ba528bd16489d843da712b481fd00064071b115788`.

Production then reran the exact script from the exact analysis commit with a
separate create-once output path. It exited zero and reproduced the committed
artifact byte-for-byte at SHA-256
`7632fcf4bb827cda6346f8d7f5ed3a10c9cb247fd5c2acbfc7ada4d46fc68855`.

## Reproduced result

- disposition: `RESCUE_ELIGIBLE`;
- supported slates: 54;
- candidates: 155,352;
- rescue events: 1,300;
- mean within-slate phi/Spearman: `+0.0102`;
- season-clustered interval: `[+0.0040,+0.0168]`;
- sign-flip p-value: `0.0183`; and
- LOSO: 2022 `+0.0134`, 2023 `+0.0070`, 2024 `+0.0104`.

The 18 excluded slates are all 2021 cells with no beneficiary variation. The
three supported season cuts are all positive, satisfying the frozen 3/3
interpretation of the stated at-least-three positive-cuts rule.

## Interpretation caution

This is a small within-slate association, not a general claim that beneficiary
candidates have a higher unconditional rescue rate. Pooled candidate rescue
rates are lower for beneficiaries (`0.0068` versus `0.0095`), with the sign
reversal caused by season/slate composition; the frozen within-slate statistic
is positive. The correct use of this finding is the predeclared bounded test,
not direct adoption or a larger rescue dose.

## Route

Production confirms the frozen exclusive route:

- build, mechanics-smoke, and return a launch contract for PREREG-067 /
  experiment 096, using its eight-seat beneficiary-rescue sleeve on fresh
  banks 700–702;
- do not run PREREG-068 / experiment 097;
- do not change the 096 eligibility, priority formula, dose, primary,
  diagnostics, or banks using the opened WP-B result;
- keep experiment 091 held; and
- make no live-policy change from this diagnostic.

The separate selection-diagnostics plan may run over sealed artifacts in
parallel, but experiment 096 retains first claim on the score lane.
