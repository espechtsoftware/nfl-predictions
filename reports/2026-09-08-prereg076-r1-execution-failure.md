# PREREG-076 R1 execution failure disposition

Date: 2026-09-08 America/Chicago  
Frozen bank: `103b770r1-20260908T180000Z`  
Execution: `lab-run-7hl86`

## Disposition

**R1 is consumed and invalid; preserve all artifacts. No score or outcome was
opened.** Banks 771 and 772 were never claimed or launched.

## What happened

After R4d repaired the launch preflight and produced a clean no-mutation
transcript, production launched the registered three-bank score-free
coordinator. Bank 770 began on the exact immutable image
`sha256:f4398f6ce84d0cc41c461ec0adaa8604d05a0ba2146918722f322a72699741f8`.

Task 10, cell `2023-w11-b740`, exited 1 with:

```text
excluded_ids_malformed: CP-1 frame binding refused - 2023-w11-b740
```

Once one task failed, exact 36/0/0 success was impossible. Production cancelled
the execution to avoid spending the remaining bank. Final provider state is
17 succeeded / 1 failed / 18 cancelled / 0 retried. Seventeen create-once cell
objects exist; they are preserved under the R1 prefix. The registered
coordinator exited 1 and did not proceed to banks 771 or 772.

## Root cause

This is deterministic and already understood from PREREG-074's earlier FM1
failure. The frozen R1 image's `src/nfl2/cp1_frame_binding.py` uses:

```python
_ID = re.compile(r"00-00\d{5}")
```

The accepted CP-1 artifact's 2023-W11 exclusions are the canonical values
`00-0036999`, `DST_LV`, and `DST_TEN`. The old validator admits only one narrow
numeric shape and rejects DraftKings DST identifiers. PREREG-074 repaired this
at lab commit `05236d5` by separating the canonical private-ID validator
(numeric player or `DST_[A-Z]{2,3}`) from the public redaction detector and by
validating every supported cell before launch. PREREG-076's older source
`b130be6f...` predates that repair.

## Required successor

R2 must:

1. preserve the R1 intent, claim, execution, and 17 objects as consumed
   evidence;
2. incorporate the already-reviewed canonical-ID validator and its exact
   behavioral tests into a fresh PREREG-076 source;
3. authenticate every expected cell's private exclusion facts against the
   frozen CP-1 artifact before any cloud execution, so the 2023-W11 boundary
   is exercised;
4. update the runtime closure and perform one new immutable build/image/binding;
5. roll the entire cohort to fresh R2 run IDs, including all three banks; and
6. keep candidates, judges, retrieval arms, banks, resource envelope, score
   boundary, and outcome boundary unchanged.

This is an implementation repair, not adverse evidence about fresh-judge
retrieval.

