# Corrected role + no-floor candidate-union experiment

Preregistered 2026-08-10 before any complete corrected K3/K1 score panel was
available. This is a bounded operational optimization under the operator's
240→230→220→210 tail-first utility, not a revision of the prior no-floor
scientific disposition.

## Why this combination remains open

The prior valid true-80 no-salary-floor arm improved selected 200/210 counts
relative to its K1 base while losing a different 220-point week and one
candidate-pool 200 week. It is dominated by the later CE/role union when each
book is viewed alone, so it was correctly not adopted. What has never been
tested is candidate-level complementarity: retaining every candidate from
the strongest CE/role source while adding the exact no-floor pool before the
same 80-entry selector runs.

An availability-only join of the preserved, pre-correction panels was made
without querying actual scores. Across all 107 slates, the role source had
235--263 candidates and the no-floor control had 224--251. They shared 18,056
rosters, while no-floor contributed 7,848 distinct rosters, or 73.35 per
slate. Only 4,534 of 8,560 selected slots were common. This establishes a
real candidate-set mechanism; it does not establish scoring value, and the
old panels are point-in-time-ineligible after the common-lock defect.

## Frozen construction

Do not launch this work until the common-lock chain has produced its complete
corrected K1, CE12, and twelve-role source and the corrected tail-first
decision has been recorded.

1. Rebuild exactly one corrected no-floor K1 panel on generation image
   `sha256:215a6729b66980310cfad3f63b06a7c25ce4dcf2fa2b6949a04a5c9afa337221`
   and code identity `8677d21`: `MODEL_ENSEMBLE=1`, possession simulation,
   model/market weight 0.45/0.55, `MIN_LINEUP_SALARY=0`, candidate multiple
   2, no CE/role/Gumbel candidates, 40 boom candidates, selection line 194,
   and 80 final entries. Proposed panel id:
   `20260810-lockfix-e80-k1-nofloor-8677d21`.
2. The source is the complete corrected CE12 + twelve-role added-budget union
   from the correction chain. Preserve every source candidate and add every
   distinct corrected no-floor candidate. No quota, intermediate salary
   floor, candidate cap, dose, seed, selection line, or score-based filter is
   permitted.
3. Use the already-persisted candidate support masks only after proving exact
   source versus no-floor equality for shared player identities,
   authoritative actuals, simulated means/probabilities, world count, and
   every 187/194/200/210/220 support mask. Both accepted panel manifests must
   independently prove the corrected market reader, marginal parameters,
   simulator mode and seed. The source's common worlds are authoritative.
4. Deduplicate exact nine-player rosters and run the unchanged greedy
   194-point coverage selector over the union, returning exactly 80 unique
   lineups. The candidate pool may grow; the submitted entry count may not.
5. The comparator must report source containment, added roster counts and
   salary distribution, selected membership movement, full selected and
   pool-oracle grids at 187/194/200/210/220/230/240, paired weekly changes,
   season diagnostics, runtime, and any generation/selection failure.

## Decision rule

Hard requirements are point-in-time validity, all six corrected seasons and
107 slates, exact authoritative joins, reproducibility, legal candidates,
exactly 80 final unique entries, no hidden tuning, and a live-feasible path.

After those pass, compare selected weekly-maximum counts in the fixed order
240, 230, 220, then 210. The union becomes a promotion candidate only if at
least one 210+ count improves and no higher threshold worsens. Counts at 200,
194 and 187, pool oracle, mean/median, season signs, candidate volume and
runtime remain mandatory diagnostics but are not automatic scoring vetoes.
Any tradeoff at a threshold higher than the gain requires an explicit
operator decision. A tie through 210 closes the union.

If the corrected role source is not itself the final corrected incumbent,
promotion additionally requires the union to win the same high-to-low
comparison against that incumbent. Beating a superseded source is not enough.

The mechanism was chosen with knowledge of the superseded no-floor result,
so even a corrected pass must be labeled an operator-directed optimization,
not an independent scientific confirmation. There is exactly one launch and
no retry on the six historical outcomes. A failure does not license an
intermediate salary floor, a reduced no-floor quota, a different selector,
or a no-floor/CE/role parameter sweep.

## Live feasibility

Historical score improvement alone is insufficient. Before replacing the UI
policy, reproduce the union from the already-isolated K1 no-floor and role
candidate builders at one frozen pre-lock snapshot, verify that source
fallback remains labeled and intact, and measure total wall time against the
Week 1 operational window. Extra pre-selection compute is acceptable; a
partial, late, or non-reproducible 80-lineup book is not.

The outcome-blind merge/selection primitive is implemented in
`src/nfl_dfs/research/candidate_union.py`. It preserves incumbent ordering,
adds only novel roster keys, checks exact shared 194 support masks and tight
actual/probability/mean parity, and returns an exact-size reselected book plus
membership audit. Offline tests cover containment, support mismatch,
incomplete source books, and the high-to-low tail decision. This does not
authorize a panel launch before the corrected role source is complete.

The common-lock launcher now has a guarded `nofloor` mode for the exact panel
above. It refuses to run until the complete corrected role source is present
in the accepted table, then changes only `MIN_LINEUP_SALARY=0` on the frozen
K1 control settings. This is implementation readiness, not launch authority;
the role chain and its tail-first disposition must still finish first.

The guarded evaluator `research/floor_union_confirmation.py` and CLI command
`corrected-floor-union` build exactly one union, report its candidate/salary/
membership diagnostics, and require a high-to-low win against both the role
source and the actual corrected incumbent. Shared candidates must match on
all five persisted support masks; there is no outcome-dependent retry.

Full exact-tree validation completed before any corrected union outcome was
available. Cloud Build `a4079b03-2a23-453f-85b1-917550fc73c0` passed 742
tests with 2 skipped and produced immutable evaluator digest
`sha256:ef0747eb3232ad797488dd8f38dcec522ea8815615120d31b2f7a39e332da85f`.
Only that digest may run the eventual guarded union confirmation.

## Pre-launch source-prerequisite amendment — 2026-08-10

The corrected chain did not launch the anticipated CE12+role branch: CE12 was
not the corrected incumbent, while the separately tested direct-role union
`20260810-lockfix-e80-k1-role12union-8677d21` passed and was promoted. Before
any corrected no-floor generation or outcome read, the launcher's sequencing
prerequisite is therefore amended from the nonexistent CE12+role panel to that
accepted direct-role panel. This does not change the no-floor treatment, image,
code identity, simulation, candidate budget, selector, or 80-entry output.
The eventual union source is the accepted direct-role pool; it must additionally
beat any Route Share incumbent selected before the comparison. This is the only
source amendment and does not license a retry.

## Pre-result execution repair — 2026-08-10

All six corrected no-floor seasons completed and check-only acceptance
execution `accept-replay-panel-jbxkq` passed all 107 exact-80 slates. The
first comparator execution, `corrected-floor-union-6rv2c`, failed before
emitting `FLOOR_UNION_CONFIRMATION_JSON` or any score comparison. The guarded
loader required `research_eligible=TRUE` for the add-on even though check-only
accepted rows in `replay_candidates_staging` are false by construction; all
25,890 valid no-floor rows were therefore filtered away. The identical rule
had already been fixed in the Route comparator but was missing here.

The mechanical repair applies the eligibility predicate only to the accepted
table and reads the explicitly named staging treatment without changing any
row. A regression test proves accepted queries retain the predicate and
staging queries omit it. The launcher also passes the unchanged evaluator CLI
as one shell argument because the current gcloud list parser rejects the same
direct-role panel value appearing separately as both source and incumbent.
Neither repair changes a panel, candidate, world, selector, threshold, entry
count, or decision rule. A new full-test immutable evaluator image is required
before the one comparison is rerun; the failed execution produced no result
or new score outcome and does not license any further retry.

The required exact-tree validation succeeded in Cloud Build
`cb203be1-0765-479b-8fc4-e5d69c8dd056`, producing immutable evaluator digest
`sha256:bcb88cff4e7f70ea34e0f52997254f420a39041e680eb4e26752ed2f9596fd69`.
The repaired execution uses a distinct durable run directory ending in
`-loaderfix`; the original failed execution record remains untouched.

## Final result — 2026-08-10 CDT

Repaired execution `corrected-floor-union-k8v5b` completed successfully from
the immutable digest above. All 107 slates passed source-containment, shared
support-mask and exact-80 checks. The union retained 27,036 source candidates,
added 6,969 novel no-floor candidates, selected 611 add-on slots, and changed
723 selected slots in each direction.

The final selected 187/194/200/210/220/230/240 grid changed from
`34/22/11/7/5/3/2` to `34/22/13/7/5/3/2`. Mean weekly maximum changed from
`180.1207` to `180.0084`, with 5 weekly wins, 98 ties and 4 losses. The pool
oracle improved from `42/28/16/9/5/3/2` to `43/28/18/10/6/3/2`.

This is a real candidate and ≥200 improvement, but the registered active
decision tied at every threshold from 240 through 210 and therefore returned
`keep-corrected-incumbent`. The no-floor union is not promoted and receives no
parameter, salary-floor, quota or selector retry on these outcomes. The
direct-role incumbent remains production policy.
