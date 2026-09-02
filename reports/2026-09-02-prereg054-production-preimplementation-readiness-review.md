# PREREG-054 / experiment 085 — production preimplementation readiness review

**Date:** 2026-09-02

**Scope:** outcome-blind design and launch readiness only

**Disposition:** **Not ready for runner/reader freeze or a mechanics launch.** The participation hypothesis remains high-value, and the blockers below are bounded enough to resolve in one prelaunch amendment. Nothing here requires stopping experiment 084.

## The decision that must be made first

PREREG-054 currently defines identical generated supply and independently zeroes designated players only in selection worlds. That can answer a narrow question:

> Does a same-pool, zero-only participation risk penalty improve selection?

It cannot support the document's broader conclusion that the result is a live-eligible participation **generative law**. The accepted PREREG-043 amendment required one shared player state per world, consistent use across all candidates and components, teammate opportunity redistribution, and an explicit quarterback treatment.

Production recommends preserving the higher-value live-law estimand:

1. generate one fixed D400 candidate population per slate;
2. evaluate that identical population with coherent participation-adjusted critic worlds;
3. draw one participation state per player/world and share it everywhere in that world;
4. redistribute vacated targets/carries through a frozen next-player-up rule; and
5. freeze an explicit quarterback treatment.

This still isolates the belief/selection effect because candidate supply remains identical. If the lab instead wants the cheaper zero-only diagnostic, rename it accordingly and remove live-law adoption authority.

## Must-fix design items before code freeze

### 1. Freeze the participation estimator completely

“Walk-forward,” “prior weeks,” and “Laplace-smoothed” do not identify an executable law. The amendment must fix:

- training seasons/weeks for every target season;
- whether fitting is leave-prior-season or strictly prior-week;
- exact designation and practice-status cells;
- Laplace numerator/denominator constants;
- missing-status and unseen-cell backoff;
- eligible positions;
- probability bounds; and
- exact model/artifact identity used by every bank.

`was_active` should be described as observed participation/appearance, not an official active-list label. Prior-fold labels may train a frozen belief artifact; target-slate labels must be physically unavailable to the runner and joined only by the reader.

### 2. Bind row-level point-in-time injury authority

The lab benchmark carries `injury_status` and `practice_level`, but not the timestamps and source fields needed to prove that those values were available before slate lock. Production's source table contains `injury_information_at`, `injury_source_kind`, `injury_snapshot_pulled_at`, and `slate_lock_at`, but that provenance is lost in the exported lab rows.

Before 085 freezes, publish a content-bound sidecar keyed by season/week/player containing:

- the exact status and practice value consumed;
- source kind/object identity;
- information/snapshot timestamp;
- slate-lock timestamp; and
- a one-to-one reconciliation digest against the experiment frame.

### 3. Make `P_ELIG` executable without changing the estimand accidentally

“Exclude (projection to zero)” is ambiguous. It could change generation supply, make existing candidates inadmissible, or merely zero their selection worlds.

For an identical-supply experiment, define it as a selector-side eligibility mask over the same frozen candidates and specify the deterministic exact-K fallback. If it removes players before generation, it is a separate supply-law experiment and must not share the same estimand or count-matched reference.

### 4. Freeze the cohort and inherited control

The design must name:

- exact target seasons/slates;
- fresh bank IDs and all RNG streams;
- the inherited D400 allocation/topology and legality contract;
- critic-world and selection-world counts;
- exact K80 selector/objective; and
- how zero-engagement or eligibility-shortfall slates are handled.

The clean control is the exact 084 `T_BASE` D400 package, not merely “400 solves.” If 2023–2024 remains the regime-valid primary panel, state that explicitly.

### 5. Make the contamination co-primary executable—or demote it

The phrases “integrity clean,” “materially reduced,” and “no proxy cost” do not define a verdict. Either retain contamination as a descriptive mechanism report, or freeze:

- the exact denominator and missing-label policy;
- the paired slate-level treatment contrast;
- uncertainty and multiplicity handling;
- any noninferiority margin for proxy cost; and
- the exact veto/adoption threshold.

Exact-K failure and any outcome leakage should remain hard void conditions. “No observed appearance” is the correct label for `was_active=0`.

### 6. Retain the complete 084 diagnostic surface

The 085 reader should preserve:

- treatment-specific influence stages 1–5;
- K-prefix and threshold reports;
- candidate oracle/regret;
- book turnover/Jaccard, EITS, and novelty;
- exact candidate and selected-rank traces;
- winner-registry byte identity; and
- the synthetic mechanics/scorecard probe.

Same-supply invariants may make some values equal across arms; emitting them still proves that the intended estimand was executed.

The historical experiment should be labelled an initial-lock estimand. A prospective late-swap policy is separate.

## Implementation facts, not additional design objections

At lab `main` commit `c61a10ff797a7fb172fc6b59d6a5b400b4d42ed0`, no 085 runner, reader, gate, bank assignment, immutable image binding, or registered coordinator exists. The old experiment 073 implementation is not a safe starting authority: it uses a different logistic model, changes generation supply, independently zeroes all skill players, hard-removes Out and Doubtful, permits short books, and lacks the 084 trace/gate contract.

## Minimal fast build and gate sequence

1. Land one design amendment resolving the six items above.
2. Freeze the PIT injury sidecar and the walk-forward participation-belief artifacts.
3. Reuse the 084 runner structure and prove identical candidate hashes across selector-treatment arms.
4. Receipt probability vectors, participation states/masks, RNG seeds, critic matrices, engagement, eligibility displacement, legality, and exact K80.
5. Include canonical roster player IDs or a hash-verified composition artifact so the reader can join target-slate appearance labels without guessing from a digest.
6. Test the earliest walk-forward target and a genuinely engaged slate, plus zero engagement, unseen cells, missing status, eligibility shortfall, NaN/tamper, and exact-key label failures.
7. Freeze runner and reader, build one immutable image, run an outcome-disabled mechanics gate, bind the receipt and reader SHA, assign fresh banks, and launch through the canonical registered coordinator.

Until those steps exist, 085 is next in scientific priority but is not the next authorized Cloud Run execution. After 084's cohort succeeds, the immediate authorized transition remains the frozen 084 first read and production cross-verification.
