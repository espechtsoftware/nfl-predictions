# Reconciliation: retry narrowing and lattice support response

Date: 2026-08-16. This reconciliation was written before either future
constraint-lattice population launched and without reading any support count,
constraint-lattice effect or realized outcome.

Reviewed source:
`reports/2026-08-16-retry-narrowing-and-lattice-support-response.md`.

## Verdict

The response is correct on its two confirmations and both open items are
accepted.

1. The retry class remains deliberately narrow. Only the literal Cloud Run
   platform condition `Internal error running task`, terminal failure and an
   absent exact output object may receive one separately receipted unchanged
   execution. Memory, timeout, signal, solver, nonzero-exit, cancellation and
   ambiguous failures remain scientific/mechanical findings and are never
   retried under this rule.
2. Repair3 was a launch-namespace defect that no retry should conceal. The
   forthcoming ATLAS repair5 grid itself, as well as both future 54-cell
   lattice populations, now uses its actual 2023 Week 1 cell, job name,
   command and immutable prefix as a canary. The remaining 53 cells cannot
   launch until its exact execution specification, terminal success and
   positive object metadata pass without downloading the object. An earlier
   version of this reconciliation applied the recommendation only to the
   lattice populations; that scope was too narrow and was corrected while the
   32-GiB preflight was still nonterminal and before repair5 launched.
3. The response correctly accepts the magnitude correction: each final block
   pools 54 slates and 540,000 held-out worlds. The support census remains
   necessary because the five blocks share slate context and rare tail support
   may be concentrated.
4. The census now reports the complete 54-slate vector per block/threshold,
   positive slates, top-1/3/5/10 event shares, Herfindahl/effective-slate
   concentration, positive-slate median/max and all ten pairwise block
   correlations for p194/p210/p220/p230. Correlations are diagnostic only.
   The prospectively frozen >=540-event and >=41/54-positive-slate rule remains
   the support decision; no threshold will be invented after viewing counts.

## Implemented contracts

- `reports/2026-08-16-constraint-lattice-bounded-platform-retry-amendment.md`
- `reports/2026-08-16-constraint-lattice-real-path-canary-amendment.md`
- `reports/2026-08-16-constraint-lattice-support-distribution-amendment.md`
- `reports/2026-08-16-atlas-repair5-real-path-canary-amendment.md`
- `reports/2026-08-16-atlas-historical-score-repair5-canary-binding-amendment.md`
- `scripts/cloud_wait_atlas_repair5_canary.sh`
- `scripts/cloud_prepare_constraint_lattice_attempts.sh`
- `scripts/validate_constraint_lattice_attempts.py`
- `scripts/cloud_wait_constraint_lattice_canary.sh`

The repair5, support and scientific launchers bind their canary sources,
execute the real canary before the release loop, and retain a 53-cell
grid-release receipt. Their attempt resolvers and finishers require the canary
evidence and an exact accepted-attempt population before any shard is
downloaded. The support aggregator emits the added distribution diagnostics
and the strict finisher validates their full schema.

## Consequence boundary

The canary validates launch-path correctness, not workload sufficiency. The
resource preflight validates one deliberately large full workload, not the
other 53 cells. The bounded attempt rule removes only a literal platform error
and cannot rescue substantive failures. The support census can license the
original p230 design or require a newly frozen lower-anchor design, but it
cannot license production. Five held-out simulator blocks establish seed
robustness only; they do not establish independence or cure simulator
misspecification.
