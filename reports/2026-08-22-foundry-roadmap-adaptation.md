# Foundry adaptation of the offseason fill/selection roadmap

**Date:** 2026-08-22 (deployment lead)
**Source under review:**
[`2026-08-22-offseason-corpus-fill-and-selection-roadmap.md`](./2026-08-22-offseason-corpus-fill-and-selection-roadmap.md)
**Verdict:** adopted as the Foundry research program, with the concrete
bindings, one machinery gap, and the calendar constraint below. The source
document stays authoritative for rationale and statistics; this report is the
execution mapping and does not restate it.

"The Foundry" = the fill x retrieval corpus experiment engine now deployed:
parametric fill arms populate a per-slate lineup corpus, retrieval laws select
exact-80 books from the upper tail, all scored on the frozen 50,000-world
Atlas matrices, every experiment recorded in the versioned strategy registry.

## 1. What the review endorses without change

- The two-stage population/retrieval framing, the concordance matrix (§6),
  the set-level marginal-utility objective (§8.4), the A/B/C/D factorial with
  its fixed comparison law (§11), the evaluation tiers (§11.2), the
  statistics discipline (§11.3), and the entire no-go list (§16). These match
  the validation laws in `CLAUDE.md` and the registry's already-enforced
  comparison contract.
- The denominator warning (§2): lineup-world events cluster within slates,
  worlds and shared players; transferable claims are supported by slates and
  seasons. Every cross-slate report must carry lineup/slate/season/block
  support columns.
- The closed-experiment list (§5). None of the four closed mechanisms may be
  re-run in substance under a new name.

## 2. Binding the roadmap to machinery that exists today

| Roadmap item | Foundry binding |
|---|---|
| §12.2 / P0.3 all-slate scoring for phenotype expansion | **The running 54-slate x 7-arm production batch is the compute vehicle.** Batch `20260822-corpus-parametric-production-batch-v5`, image digest `232c1087...`, foundation `...production-foundation-v5`. Each accepted task yields one slate's per-arm corpora, the cross-arm union, and full 50k-world score matrices — exactly the §9.1 "structured super-pool with source attribution," produced per slate with equal budgets and shared worlds. Do not build a separate super-pool generator first. |
| §9.2 fill preset F2 (winner-support topology sleeves) | **The seven parametric arms are F2's first bounded form.** They one-factor-ablate precisely the rules the winner census says winners violate: `remove-qb-stack` admits the naked/one-teammate shapes (32/51 winners violate stack-2), `remove-bring-back` admits the no-bring-back shape (31/51), plus salary-floor, RB-v-DST, two-RB ablations and the all-relaxed arm, against the `incumbent` control. The batch therefore measures, at 54-slate scale, how much simulated-tail support each winner-blocking rule suppresses — outcome-blind. |
| §9.2 F1 (tail-family / boom enrichment) | Already queued as the registered boom-enriched challenger fill preset (live handoff "Boom direction"): score its snapshot once, apply all retrieval presets to the same snapshot, keep the baseline on every slate. Enters only after the baseline batch is accepted. |
| §9.2 F3 (phenotype-conditional) | Gated on P0.4 (cross-slate shrunk-effect report). No identity coefficients, per §16. |
| §10.2 retrieval presets | `R0-coverage-194` and `R1-strict-200` exist (accepted task-0 laws); `tail-ladder-200-210-220-v1` is a third existing law the roadmap table omits — keep it as an additional comparator; `mean-score-v1` stays the negative control. **R2/R3/R5 are now implemented and frozen** in the additive v2 registry (`frozen_retrieval_strategies_v2`, commit `10bdb07`; v1 bodies byte-identical): `expected-max-v1` (greedy submodular expected book maximum), `block-supported-tail-ladder-v1` (ladder coverage scaled by distinct-discovery-block event support — the exact-integer realization of shrunk cross-block support, chosen over pseudo-credible bounds), and `regime-robust-ladder-v1` (leximin over the sorted per-block coverage profile; leximin replaced plain maximin after a constructed test showed maximin is degenerate while any block is empty). Suite-manifest integration deliberately waits for the parametric-snapshot adapter. R4-hybrid-support waits for the §8.2/§8.3 models. |
| §11 factorial evaluator | The strategy registry already enforces the causal separation (retrieval cells share one snapshot/fill; fill cells share retrieval/worlds). The named-scenario release path (green as of today) is the registration vehicle for every A/B/C/D cell and its `MetricSet`/`PromotionDecision`. |
| §7.4 realized labels | The existing one-read realized grader (`corpus_realized_grading.py`) runs once against the complete accepted batch, after books/features are frozen — this is the roadmap's outcome firewall in code. |
| §12.1 winner reconciliation | New P0 work. The source-integrity findings are now a Data deficiency log row in README (2026-08-22). |

## 3. The one real machinery gap the roadmap missed

The sparse phenotype analyzer (`corpus_gt200_analysis.py`) consumes the
**retrieval-engine task-result schema** (nine pinned objects from the accepted
retrieval run). The parametric batch worker publishes **legal-feasibility
variant results** under a different schema. P0.3 therefore needs a bounded
adapter — either a parametric-result reader for the analyzer or a
retrieval-shaped projection emitted per accepted task — before per-slate
phenotype extraction can run over the 54x7 outputs. This is the first
post-batch code deliverable, alongside R2/R3/R5. Scope it as read-only over
accepted create-once artifacts with the same generation-pinned identity
discipline; no score-matrix reads beyond the sparse event projections.

## 4. Corrections and cautions on the source document

- §4 task-0 numbers (585 lineups, 27,117 events) are one slate under the
  smoke corpus; per-slate counts in the production batch will differ. All
  cross-slate claims must be re-derived from the batch, not scaled from
  task 0.
- The §13 phase calendar (8–14 focused days before a Week-1 freeze at T-3)
  fits **only if** the 54x7 batch completes by roughly Aug 25–26. One lane
  finishes in ~2–3 days once the job frees; the sanctioned accelerator is a
  second lane on another reused existing job, which needs its own transport
  contract designed deliberately — this is the single biggest calendar lever
  and an explicit operator decision.
- §8.3 winner-support density: with 51 positives, ship it only with the
  preregistered small feature set, matched same-slate controls, and
  leave-one-season-out stability, exactly as written; treat any unstable
  coefficient as disqualifying.
- The arm-vs-arm results of the running batch are simulated support
  evidence (outcome-blind). They inform fill-preset design; they are not
  adoption authority. Realized reads happen once, after freezing, per §11.2.

## 5. Sequenced plan from here

1. **Live chain first** (in flight): v4 smoke close/verify -> v5 configure ->
   task-0 equivalence gate -> tasks 1..53. Scores accumulate per slate.
2. **During the batch (offline, parallel):** P0.2 winner reconciliation +
   receipts; P0.1 `lineup_slate_evidence` schema; the §3 analyzer adapter;
   R2/R3/R5 implementation with focused tests.
3. **After batch acceptance:** realized grading (one read); per-slate
   phenotype extraction; P0.4 cross-slate shrunk-effect and discordance
   report keyed by the concordance matrix.
4. **Then:** F1 boom challenger snapshot; A/B/C/D cells via the registry;
   at most one nominated joint strategy plus one fallback for the Week-1
   freeze, under the §15 gates.
