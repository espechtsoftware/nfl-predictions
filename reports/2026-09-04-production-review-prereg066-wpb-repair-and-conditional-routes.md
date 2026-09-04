# Production review: repaired Work Package B and conditional Routes C1/C2

Date: 2026-09-04 UTC

Reviewed lab identities:

- Work Package B repair: `da5241b59285de9886d14b3f24dbc6c7842f8891`;
- lab response: `1f00a7fe7d921e9932c6234ec6a22d08a7d829a1`;
- conditional designs: `e926f060ea4b339035d61980d738ea1a209be74b`;
- `PREREG-067-DESIGN.md` (Route C1 / experiment 096);
- `PREREG-068-DESIGN.md` (Route C2 / experiment 097).

No 095 outcome was opened. Experiment 095 continues under its frozen source,
image, runs, and registered coordinator. Experiment 091 remains held.

## Disposition

The Work Package B repair is accepted in substance, subject to one final
identity repair before execution. Both conditional route designs are useful
pre-outcome commitments. Route C1 is accepted subject to two implementation
clarifications. Route C2 needs three bounded design clarifications before its
conditional freeze. None of this blocks the running 095 cohort.

Independent validation on lab tip `e926f06` passed **12/12** focused Work
Package B plus frozen-reader tests; Ruff is clean.

## Work Package B: one remaining pre-execution repair

The transcript, reader, sign-flip implementation, Work Package B source, raw
routing, descriptive denominators, and create-once output are now properly
guarded. The remaining gap is the eligibility-release input.

`check_eligibility_release` currently accepts any existing local JSON file. It
does not prove that the file is tracked at `HEAD`, byte-equal to its `HEAD`
blob, or generation-bound in immutable storage. It also accepts any nonempty
`released_by` and `release_commit`. Thus an untracked mutable file can satisfy
the gate despite Update 59 describing the receipt as immutable.

Before Work Package B executes:

1. require the release file to be tracked at the lab execution commit and
   byte-equal to its `HEAD` blob, using the same proof pattern as the transcript
   (or bind a create-once GCS URI, generation, byte count, and SHA-256);
2. require `released_by == "production"`;
3. require `release_commit` to be a full 40-hex production commit;
4. retain the exact transcript SHA and exact three-run cohort equality checks;
5. add a regression showing an untracked or locally modified release is
   refused.

The production eligibility decision should be a separate post-seal commit.
The lab may copy that exact receipt into its own tracked execution commit; the
receipt's `release_commit` should identify the production decision, not attempt
to self-reference the lab commit containing the copy.

## Route C1 / PREREG-067: accepted with implementation clarifications

The fixed eight-seat rescue sleeve, single primary contrast, P_MIX judge,
fresh banks, and priority formula are aligned with the adopted plan. Preserve
these two details in the runner and mechanics gate:

1. `linked(c)` must be exactly the 094/095 `_participation_geometry` relation:
   same team and `_pos_group`, with WR/TE merged, only modeled designations,
   and modeled designated players excluded from the beneficiary set. Do not
   substitute a generic teammate or position label.
2. Each successful replacement removes only a remaining member of the
   original control book. A rescue inserted on an earlier iteration cannot be
   removed on a later iteration. Recompute marginal gain/loss after every
   accepted swap, use the frozen deterministic tie law, and receipt attempted,
   accepted, and shortfall counts separately.

No sleeve-size, exponent, cap, or alternate linkage search is authorized.

## Route C2 / PREREG-068: required pre-freeze clarifications

### 1. Keep the base family exactly F2

The design lists `total_salary` inside the “frozen F2” base family. In
PREREG-062, total salary is F1, not F2. Remove it from the base list. Adding an
F1 feature would be a different family decision and is not authorized by the
adopted Route C2 plan.

The exact F2 base is:

- `sim_mean`;
- `sim_q99`;
- `market_points_sum`;
- `own_est_sum`;
- `consensus_div_sum`;
- `salary_weighted_own`.

### 2. Freeze the multi-link beneficiary formula

A rostered beneficiary can be linked to more than one modeled designation.
Define one value per beneficiary before summing across the lineup:

`beneficiary_absence(b) = 1 - min(P_active(d) for d in linked(b))`

and then:

`beneficiary_absence_exposure(c) = sum(beneficiary_absence(b) for rostered b)`.

This uses the same “most absence-prone linked designation” convention as
Route C1 and prevents an implementation from choosing or double-counting
links after outcomes are available. Receipt linked IDs, their P(active)
values, each per-beneficiary value, and the candidate sum.

### 3. Resolve F3 inclusion before the 095/WP-B route is known

PREREG-062 did not define a binary F3 coverage-pass gate; it published
missingness and then screened the frozen features. Therefore “if its coverage
and source hashes pass the same gate PREREG-062 used” is not executable as
written and leaves post-read discretion.

The source identities and pre-lock coverage are already observable without
095 outcomes. Freeze now:

- the exact F3 column list and source hashes;
- the fold-specific missing-value law, including all-missing columns;
- an exact, mechanical all-block inclusion rule based only on the published
  pre-lock coverage receipt;
- the resulting decision: full F3 block included or full F3 block excluded.

No individual F3 column may be selected. If the block is included, an
all-missing fit-fold column must be inert exactly as in the frozen PREREG-064
ridge implementation.

### 4. State the fold and greedy-selection mechanics explicitly

Before implementation, state whether each bank's season-S model trains on only
that bank's prior-season candidates or on a shared cross-bank training frame.
Do not leave that choice to the runner. Also bind:

- mean/SD fitting and missing-value treatment to training rows only;
- the zero-variance fallback;
- within-slate z-score handling;
- whether candidate-score z-scores are fixed while marginal judge values are
  recomputed at each greedy step;
- start-from-empty K80 construction and deterministic ties.

This is specification completion, not a request for another parameter grid.
The already chosen ridge alpha 10 and hybrid weight 0.25 remain fixed.

## Sequencing

1. Continue 095 unchanged through three clean terminal banks.
2. Lab opens and commits the frozen first read; production independently
   reproduces it.
3. Production publishes the B1 eligibility decision.
4. If eligible, run the repaired Work Package B exactly once.
5. Freeze and execute exactly one conditional route selected by Work Package
   B. Do not launch 091.
6. Run the final fresh-bank generation × retrieval crossing only if the routed
   selector earns it under the adopted plan.

## Final pre-outcome disposition after lab Update 61

Production reviewed lab commits
`2c418677b721993aff038b006629b8ac227df0f2` and
`b6479e39881ef020d14cbe9b230802be2a2d30f8` before any 095 outcome was
opened.

The Work Package B release-identity gap is closed. The diagnostic now refuses
an outside-repository, untracked, or locally modified release; requires the
release bytes to equal the tracked `HEAD` blob; requires
`released_by == "production"`; requires a full 40-hex production decision
commit; and preserves exact transcript-SHA and three-run equality. The output
receipt also records the release path, release SHA, and lab execution commit.

The Route C1 specification now binds the exact 094/095 participation linkage,
monotone original-incumbent-only replacement, per-step recomputation,
deterministic ties, and attempted/accepted/shortfall receipts. The Route C2
specification now binds the exact six-column PREREG-062 F2 family, the
multi-link beneficiary absence formula, the mechanical all-or-none F3 decision
(included minus `f3_designated_count`), bank-local walk-forward training, and
the complete standardization, imputation, greedy, and tie mechanics. These
changes satisfy the production clarifications without changing alpha 10,
weight 0.25, or either route's conditional status.

Independent validation at lab tip `b6479e3` passed 12/12 focused Work Package
B and frozen-reader tests in 57.52 seconds; Ruff passed. A subsequent complete
lab-suite run at the same exact tip passed 645/645 tests in 175.97 seconds
(warnings only). **Production therefore
accepts Work Package B and both conditional designs as ready for their frozen
post-095 routing sequence.** This is not an eligibility release, an execution
authorization, or a route choice. Experiment 095 continues unchanged;
Work Package B remains sealed until the lab commits the 095 first-read
transcript and production independently reproduces it; experiment 091 remains
held.
