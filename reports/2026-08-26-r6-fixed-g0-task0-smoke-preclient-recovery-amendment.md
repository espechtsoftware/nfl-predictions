# R6 fixed-G0 task-0 smoke pre-client recovery amendment

Date: 2026-08-26

## Purpose and preserved history

The original task-0 real-artifact smoke invocation is consumed. Its fixed v1
attempt marker remains at
`reports/2026-08-26-r6-player-catalog-fixed-g0-task0-real-artifact-smoke-attempt.json`
with outer SHA-256
`35d2a32334f7b06074a8f37245042881f4dd100796e3093b1e09639a6d81ae48`,
3,278 bytes, and internal self-hash
`2e3adc38313f2811cf7d245e77d7838915cb9602cc416e3c581e20d029d57eff`.
It is never deleted, overwritten, renamed, or reclassified as a successful
attempt.

The exact v1 command exited before construction of a GCS client and before
any GCS read. The isolated temporary worktree's `.venv` was not a complete
Python virtual environment: it lacked `pyvenv.cfg` and its expected library
layout, so importing the Google storage dependency failed. The invocation
made zero cloud reads, zero cloud mutations, zero GCS publications, zero
outcome reads, and created no success receipt. This is an execution-environment
failure, not evidence about the fixed-G0 artifact or its derivation.

## Bounded v2 correction

After exact-byte independent review reports P0/P1/P2 counts of zero, one new
tracked recovery review lock may authorize at most one v2 task-0 smoke
invocation. The lock must bind:

- the exact preserved v1 marker file and internal self-hash;
- the original preliminary adapter review lock;
- this amendment and the exact corrected implementation measurements;
- the pre-client import-failure classification and zero-cloud facts; and
- lifetime counts of one consumed v1 invocation, at most one v2 invocation,
  and no third invocation.

The v2 command must exact-reopen that tracked recovery lock and the v1 marker
before reserving a distinct create-once v2 marker. The v2 marker must be
created and fsynced before constructing a GCS client or making any cloud read.
An existing, unequal, ambiguous, partially written, symlinked, or failed v2
marker consumes or blocks the correction and can never authorize another
attempt. A v2 process failure after marker creation also consumes the sole v2
allowance.

The corrected command may perform only the same seven generation-pinned,
outcome-blind task-0 source reads previously reviewed. It may create only the
fixed local tracked success receipt. It may not list a bucket, resolve latest
objects, read world matrices, result objects, outcome columns, scores, or
lineups, mutate GCS, publish a projection, submit compute, or grant source,
scoring, selection, corpus, graph, production, promotion, or decision
authority.

The existing final-release-lock validator remains v1-only and must reject a
v2 receipt. A successful v2 smoke therefore still cannot release the 54-task
projection until a separate, outcome-blind, reviewed final-lock amendment
adds exact v2 receipt and both-attempt replay. This recovery does not silently
widen the downstream release contract.

The v1 production entry remains fail-closed once its marker exists. No public
entry may accept caller-selected pins, paths, marker bodies, review-lock
bindings, transports, backends, or failure facts. Test-only injection remains
private.

## Authority closure

This amendment authorizes no test, smoke, cloud contact, or publication by
itself. The v2 implementation and tests must be frozen and independently
reviewed first; the recovery lock must then be deterministically built and
committed at a later clean HEAD. Until those gates are satisfied, all source,
historical-scoring, corpus-fill, corpus-retrieval, selection, graph-mutation,
production-change, promotion, and decision authority remains false.
