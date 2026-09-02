# Default-off pre-lock opportunity lineage — Phase 1 implementation

**Date:** 2026-09-02

**Branch:** `codex/prelock-lineage-phase1`

**Disposition:** code-complete for one bounded candidate-only prospective shadow; not deployed or executed

**Production scoring/policy change:** none

## Outcome

The reviewed first slice is implemented without mounting the observatory UI,
changing a production route, mutating Neo4j, opening outcomes, or altering the
ordinary scoring path. When the new capture is absent, all new callbacks are
`None` and the original generation/selection/export paths remain in force. When
explicitly armed, the implementation freezes an immutable, outcome-free record
of the observed request universe through generation, deduplication, admission,
selection, and final-book construction.

The first runner is deliberately narrow: one explicitly invoked 2026
DraftKings classic slate, canonical five-seed CBWU, 80 entries, the existing
binary-tail production selector, and a candidate-only terminal scope. It is a
shadow observer, not an alternate lineup policy. The `194.0` line in this
runner describes the selector production currently executes; it does **not**
restore weekly-max-over-194 as the lab's objective or grant that objective new
scientific authority.

No cloud object, graph row, deployment, scheduler, paid entry, or outcome
artifact was created during this implementation.

## What is now captured

The runtime adapter emits a closed, self-hashed contract with:

1. every registered proposal request and its terminal state;
2. every solver invocation/retry, including produced, infeasible, solver-error,
   and exhausted-not-attempted paths;
3. every generated occurrence and same-family, cross-family, or cross-seed
   duplicate attribution;
4. every pool-cap and CBWU admission decision, including native retention,
   pool-cap drop, first-source quota, deficit fill, earlier-seed duplicate, and
   fixed-budget drop;
5. an unambiguous internal-player-to-DraftKings-draftable-ID bridge bound to the
   salary catalog;
6. exact native and effective candidate order, generator-configuration bodies,
   matrix dtype/shape/hash, player-world identities, and selected-index hashes;
7. the binary selector's dynamic fresh-world marginal at each selected step,
   individual clear count, probability, mean, phase, and tiebreak tuple, plus
   terminal marginals for every nonselected candidate;
8. raw selector rank separately from post-selector/final export rank; and
9. an optional paid-fill seam that records exact EntryID, contest, internal and
   draftable roster, slot order, source-book ordinal, filled-CSV identity, and
   export-receipt identity without changing the returned CSV.

The recorder independently replays the selector over the exact effective
matrix and refuses to seal unless both the selected order and the complete
trace are identical. Unsupported armed configurations—noncanonical portfolios,
LSE/ladder/dollar/QB-cap selectors, preseeded rosters, ambiguous player
mappings, repeated salary IDs, unsupported transforms, or outcome-bearing
fields—fail closed. They continue to work normally when lineage is off.

## Immutable prospective shadow

The explicit command `shadow-prelock-lineage` writes five create-once GCS
objects beneath one path-safe run ID:

```text
prelock_lineage/<season>/week-<week>/<run-id>/input-authority.json
prelock_lineage/<season>/week-<week>/<run-id>/selector-matrix.raw
prelock_lineage/<season>/week-<week>/<run-id>/candidate-lineage.json
prelock_lineage/<season>/week-<week>/<run-id>/terminal.json
prelock_lineage/<season>/week-<week>/<run-id>/graph-summary-v2.json
```

Every write uses provider create-only preconditions. An exact retry may reopen
and accept an existing object only when its bytes match; a differing object
cannot be overwritten. Provider generation and trusted creation time are
required, and every object must predate the authoritative draft-group lock.
The raw selector matrix is published synchronously before the detailed
sidecar, and both are frozen before the engine reaches its legacy
outcome-diagnostic block. The terminal root binds their exact provider
identities and bytes.

The runner also computes a local implementation manifest over the 13 critical
code/config files and refuses a caller-supplied code hash that differs. At this
reviewed tree the implementation digest is:

```text
963fd4db11d29befc7ed9dd9ae78cc8d0e8b780fb68d57f3b5cbd715e8d4c37b
```

Recompute it immediately before any real run; do not copy the value above if
the branch has changed:

```bash
PYTHONPATH=src .venv/bin/python -c \
  'from nfl_dfs.inference.prospective_prelock_lineage_shadow_v1 import implementation_manifest_v1; print(implementation_manifest_v1()["implementation_sha256"])'
```

After production supplies one exact 2026 draft-group ID and authoritative lock
timestamp, the bounded shadow can be invoked explicitly as:

```bash
PYTHONPATH=src .venv/bin/python -m nfl_dfs.cli shadow-prelock-lineage \
  --run-id <fresh-path-safe-run-id> \
  --season 2026 \
  --week <week> \
  --draft-group-id <draft-group-id> \
  --slate-lock-at <timezone-aware-authoritative-lock> \
  --code-sha256 <fresh-implementation-digest> \
  --bucket <approved-bucket>
```

This command is not scheduled, auto-enabled, or called by the application.
A run ID is single-use across code/input changes: exact retry is supported,
repurposing an existing ID is not.

## Neo4j boundary

The new graph adapter produces a summary-only packet under the already merged
`corpus-graph-vnext/v2` contract. It includes source receipts, one run/slate/
science identity, stage censuses, structural transition counts, one strategy,
and one selected-book summary. It includes no `Lineup` nodes, candidate rows,
rosters, matrix bytes, actual scores, winner values, or rescue results. It
retains false decision, promotion, and graph-mutation authority and performs no
Neo4j I/O.

The packet exact-rebuilds from the immutable candidate and terminal objects.
This closes the v1/v2 merge hazard: the new work targets v2 selectively and
does not mount, merge, or depend on the older observatory projection.

## Separate post-lock intelligence

The outcome-bearing module remains physically and contractually separate. It
can:

- reopen and verify the exact frozen raw selector matrix;
- classify caller-supplied valuable rosters into one earliest observed state:
  not produced in the observed request universe, not admitted,
  selector-ineligible, eligible/not selected, selected then replaced, final
  book/not prepared, prepared/not confirmed, or prepared/confirmed; and
- force each omitted eligible candidate into an exact-K selector replay one at
  a time, reporting its individual change in realized book maximum.

Confirmation requires exact `(contest_id, EntryID, sorted DraftKings
draftable roster)`. A roster-only match is rejected. The sum of individual
rescue deltas is explicitly labelled non-joint. These readers have no scoring,
promotion, graph-mutation, production, or decision authority.

## Validation evidence

The final focused command passed **141 tests** across the immutable contract,
runtime/settlement/shadow runner, canonical CBWU, paid export, live multiseed
plumbing, selector behavior, QB-capped and ladder regressions, preseeded
identity behavior, and the existing generation-shadow suite. Specific evidence
includes:

- complete engine return order and candidate-matrix bytes are identical with
  capture off and on;
- the traced selector is output-identical to the ordinary selector and its
  dynamic trace exactly replays;
- CBWU candidate order and matrix/world bytes are identical with capture off
  and on;
- paid CSV bytes and export receipt are identical with capture off and on;
- create-once exact retry returns the identical five-object result, while a
  wrong code hash, unsafe run ID, repeated salary identity, mismatched object,
  or post-lock boundary fails before an authorized publication;
- graph-v2 summary counts reconcile exactly and outcome-like graph properties
  remain rejected; and
- confirmed EntryID/roster joins, exact matrix reopening, first-loss
  classification, and one-at-a-time non-joint rescue are covered.

Ruff passed for every new module/test; fatal Python lint passed on the touched
legacy files; Python compilation and `git diff --check` passed. CLI help was
smoke-tested.

The repository-wide suite was sampled through 3% and then interrupted because
it is very large. It exposed three failures already present at the branch's
base: an app-policy fixture expects an older allocation shape, and two old
ATLAS tests compare current unrelated source files to stale historical hashes.
None of those files or policy surfaces is changed by this branch. A separate
persistence-contract run also has five pre-existing assertions that expect
direct process-environment fallback where the current production code requires
an explicit policy environment. Historical receipt hashes were not rewritten
to hide these baseline failures.

## Deliberate Phase 1 limits

This milestone is not yet an exact paid-production settlement chain:

- The application endpoint does not yet archive the filled CSV and prepared
  sidecar create-once. The exact capture seam exists and is parity-tested, but
  mounting it in the paid route should be a separately reviewed production
  integration.
- The candidate-only input authority snapshots the draft-group lock and salary
  bridge before lock; it does not claim the stronger paid-contest authority of
  an exact existing `dk-contest-manifest/v2` object.
- The post-lock readers are strict libraries, but they do not yet fetch and
  bind a complete standings object, field bridge, access receipt, or accepted
  winner-registry-v2 receipt. Callers presently supply the outcome rows and
  winner score, so the result is not yet an autonomous exact-settlement claim.
- Phase 1 observes the finite registered request universe. “Not produced” does
  not mean absent from the literal full legal lineup universe.
- Detailed rows remain in immutable object storage. Only the bounded structural
  projection is suitable for Neo4j v2.

## Exact next action

Merge this default-off code after review, then have production choose one fresh
2026 main-slate run ID, exact draft group, authoritative lock, and approved
bucket. Recompute the implementation digest and execute **one** candidate-only
shadow far enough before lock to finish safely. Reopen all five exact objects,
validate the terminal and graph packet offline, compare the returned book to
the ordinary canonical-CBWU book, and only then consider generalization.

After that shadow proves the real provider path, the next two small integrations
should remain separate:

1. mount the already-tested prepared-entry callback behind a default-off paid
   archive flag, binding the exact contest manifest and create-once CSV; and
2. add a post-lock source adapter that exact-reopens the complete standings,
   validated field bridge/access receipt, and accepted winner registry before
   calling the existing first-loss and rescue readers.

Do not make the React observatory, full-lineup Neo4j projection, or a selector
policy change prerequisites for either step.
