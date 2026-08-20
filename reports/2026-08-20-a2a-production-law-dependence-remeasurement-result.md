# A2a Production-Law Dependence Remeasurement Result

**Date:** 2026-08-20  
**Protocol:** `20260820-a2a-production-law-dependence-remeasurement-v1`  
**Execution:** `atlas-minimal-c-s2023-w1-v1-8cnxz`  
**Disposition:** `a2a-law-shape-miss-qb-wr-not-equivalent`

## Result

The single frozen A2a dose did not pass the registered production-law
dependence gate. The execution completed strictly with one succeeded task and
zero failed, cancelled, or retried tasks. The finisher generation-pinned the
sole result, independently recomputed the registered judgment, and closed the
exact historical-outcome lease generation.

The targeted QB-WR point estimate was close to the realized value:

- simulated: `3.2855004723`;
- realized: `3.3392156863`;
- log simulated/realized ratio: `-0.0162169638`; and
- cluster 95% interval: `[-0.2125188522, 0.1949844749]`.

That interval did not establish equivalence, and zero of five registered
blocks were equivalent. The aggregate QB-TE and WR-WR cells were material
misses. Multiplicity >=3 was inconclusive and also had zero equivalent blocks.
The fixed pass law therefore returns false without a coefficient change,
alternate interval, block substitution, or another historical look.

## Disposition and licenses

- `single_stack_protocol_licensed=false`
- `single_stack_arm_licensed=false`
- `exact80_scoring_licensed=false`
- `prospective_shadow_licensed=false`
- `production_change_licensed=false`
- `historical_retry_licensed=false`

This closes the exact A2a dose and its contingent exact-one-stack successor on
this corpus. It does not close the separately frozen B1 corpus-tail selector
test, which may proceed after this terminal closure is committed and pushed.

## Durable evidence

- Source commit:
  `c088dc2636825db3016d00a4b53498b06bca00e6`
- Build:
  `50f7858d-9b83-4654-8f22-f3a41ce91e7a`
- Image digest:
  `sha256:9a57af8c6b49aca50bf75dfa26d358f58576dd1e0354bc01f81e819dd990b13a`
- Result object generation: `1787263427489841`
- Result SHA-256:
  `aed876f38733153506bd6c8fb8c90d2423ff2a20af231d2f4a2132e168247534`
- Lease generation closed: `1787262763096602`
- Release-intent generation: `1787263593683877`
- Release-intent SHA-256:
  `48cde66d5532c607a1b394813a47842c1eea593e3e27b9e5d6ded3f769c31510`

The first provisioning poll carried `Completed=Unknown`. The frozen watcher
incorrectly classified that ordinary nonterminal state as malformed and
stopped while retaining the lease. No relaunch occurred. The same execution
was polled metadata-only to strict terminal success, then the unchanged frozen
finisher harvested and closed the lease. The initial metadata is retained as
diagnostic evidence; the watcher parser must be repaired before its next use.
