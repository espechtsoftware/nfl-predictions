# Reconciliation: repair cycle and constraint-lattice review

Date: 2026-08-16, while the exact ATLAS 32-GiB full-cell preflight was
nonterminal, after only outcome-free seed-completion markers R0 and R1 had
been read, before repair5 launch and before any constraint-lattice execution.

Source supplied by the operator:
`reports/2026-08-16-repair-cycle-and-constraint-lattice-review.md`.

No ATLAS shard/effect, constraint-lattice treatment, realized outcome, contest
result, ownership, payout or ROI field was opened for this reconciliation.

## Disposition

1. **Bounded mechanical retry: accepted prospectively, with a narrower
   trigger.** A deterministic create-only shard may receive exactly one new
   execution only after its primary execution is terminal failed, the exact
   destination object is absent, and the Cloud Run terminal condition is the
   explicit platform message `Internal error running task`. Memory-limit,
   timeout, signal, solver/nonzero-exit and ambiguous failures are ineligible.
   Primary, retry and accepted ledgers plus both execution metadata records
   must be retained. When all failures are eligible, the retry is mandatory
   for every failed cell and cannot be chosen from scientific content; any
   ineligible failure terminally invalidates the population and suppresses
   futile retries. Repair4's six internal errors occurred
   during the cancellation interval and therefore do not estimate a natural
   11% platform failure rate, but the all-or-nothing 54-cell contract is still
   unnecessarily brittle. Freeze and validate a repair5 amendment/helper
   before repair5 launch; do not change the live 32-GiB preflight.

2. **Constraint-lattice support census: accepted as a required correction.**
   The original v1 protocol was frozen without the standing outcome-blind
   support census. No lattice execution exists, so no treatment result can
   contaminate the repair. Mark the p230 gate incomplete and prohibit launch
   until an immutable control-only census records p194/p210/p230 book-maximum
   event counts for every one of 270 slate/fold cells and their five
   54-slate held-out-block aggregates. Only identity, eligibility and support
   counts may be read. Freeze the census and its decision branches before
   opening those counts; if p230 support is inadequate, re-anchor before any
   treatment execution rather than weakening a gate afterward.

   One correction to the supplied interpretation matters: the final p230
   gate is not applied independently to one 10,000-world slate cell. Each of
   its five block deltas aggregates 54 slates, or 540,000 held-out worlds, and
   the global delta aggregates 2.7 million. Per-cell counts still must be
   recorded because sparse support concentrated in a few slates would make
   the aggregate hard to interpret.

3. **External memory telemetry: accept as a non-gating diagnostic.** Cloud
   Monitoring exposes `run.googleapis.com/container/memory/usage` for
   `cloud_run_job`. A live API check resolved one series for the preflight
   job. It is sampled and labeled by job rather than execution, so its maximum
   observed sample must not be described as an exact process peak or replace
   terminal memory-limit evidence. Repair5 uses one execution per uniquely
   named job, making a per-job/time-window table useful context. Add this
   metadata-only table after the grid is terminal without opening shards.

4. **Constraint-lattice full-cell resource preflight: accepted.** Select the
   preflight slate from frozen source-size/candidate-count metadata, before
   any lattice result. The current source ledger's largest five-artifact byte
   footprint is 2023 Week 1 (`163,064,634` bytes), so that exact full five-fold
   cell is the predeclared resource preflight. Its treatment/effect fields may
   not be opened to make the resource decision. The 54-cell launcher must
   require a strict successful preflight and a frozen bounded-retry contract.

5. **Simulator misspecification boundary: already present.** The original
   constraint-lattice protocol already states that the folds are simulator
   seeds rather than independent NFL seasons and that the design prevents
   same-block selection, not shared simulator misspecification. Its license is
   already limited to a separately labeled 2026 pre-lock shadow. No scientific
   change is needed; retain this wording prominently in the eventual result.

6. **Malformed durable hash: confirmed and corrected.** The narrative census
   result contained a 67-character transcription. The machine-emitted ledger
   and the actual empty inventory both contain the correct SHA-256
   `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
   The tracked narrative is corrected and a regression check must bind it to
   the machine-emitted artifact. A repository-wide scan found no other
   65+-character hexadecimal token in tracked result documents; the supplied
   review repeats the bad value only as evidence of this defect.

## Immediate order

1. Keep polling the unchanged live ATLAS 32-GiB preflight.
2. Before it can release repair5, freeze and implement the exact bounded
   platform-retry amendment and replace the old zero-retry terminal watcher.
3. Freeze and implement the control-only lattice support census, then run it
   before treating the lattice gate as complete.
4. Add the 2023 Week 1 exact-full-cell lattice resource preflight and require
   it before any 54-cell lattice population.
5. Harvest sampled memory telemetry as context after terminal grids; never use
   it to inspect or select scientific effects.

Production, the UI and the money book remain unchanged.
