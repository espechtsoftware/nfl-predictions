# Production review: pre-lock lineage Phase 1 and Neo4j integration

**Date:** 2026-09-02

**Production revision reviewed:** `origin/codex/prelock-lineage-phase1`
at `22dc9cf1314bf960d5daaa751df9afc596b29f45` (implementation
`43c55e2747d5675ac4920fc06e4093e0f2965e31`)

**Production base used for review:** `main` / `origin/main`
`e61b25e25b3fd680f775d96e929df48ab9ff766d`

**Lab companion reviewed:** `nfl2` commit
`5f3ade361b17f4f5a6b80b07e0d44f129c16d8bb`

## Decision

**NO-GO** to merge the ready branch wholesale, activate its CLI, publish its
artifacts, deploy it, or load its packet into the production graph.

**GO** to use it as the donor for a selective port after the P0 repairs below.
The implementation contains the right central idea: observe the existing
pipeline without changing its choices, preserve detailed rows in immutable
object storage, and put only bounded summaries in Neo4j. The runtime collector,
request/attempt/dedupe/admission records, raw matrix capture, paid-preparation
seam, and physically separate settlement readers are valuable work and should
be retained.

This is a compatibility and correctness rejection, not a rejection of the
lineage direction. No scoring or lineup policy change is needed or recommended.

## What this should become

```text
one frozen pre-lock input snapshot
                 |
       R0  R1  R2  R3  R4 generation
                 |
      native-union admission census
                 |
          fixed-budget CBWU
                 |
  current typed selector-event interface
                 |
        raw selection -> final book
                 |
 detailed create-once objects + final manifest
                 |
 production v2 aggregate graph projection

 post-lock sourced outcomes -> separate keyed first-loss/rescue settlement
```

The graph is the index and comparison surface. Immutable object storage remains
the detailed evidence authority. Neo4j should not become a second scoring
engine or the canonical home of matrices and candidate rows.

## P0 blockers

### 1. Two immutable v1 contracts are changed or duplicated in place

The branch expands eligibility, objective, marginal, and selection fields
while retaining `prelock-candidate-lineage-sidecar/v1` and its nested v1 schema
names (`src/nfl_dfs/inference/prelock_candidate_lineage_v1.py:26`, `:69`, and
`:236`). Current production deliberately keeps that v1 contract closed.

The branch also adds a second incompatible packet named
`prelock-lineage-graph-summary/v1`
(`src/nfl_dfs/research/prelock_lineage_graph_summary_v1.py:28`). Current main
already uses that identifier in the hardened production adapter
`src/nfl_dfs/research/prelock_lineage_graph_v2.py:24`, with a different packet,
mapping identity, selector/preset binding, publication contract, and nine false
authority flags.

A merge-tree check against current main reports conflicts in `HANDOFF.md`,
`prelock_candidate_lineage_v1.py`, `optimizer/lineup.py`, and the v1 contract
tests. More importantly, resolving those conflicts by choosing the branch
version would silently redefine already frozen schemas.

**Required repair:** leave production v1 byte-semantically unchanged. For the
fastest first shadow, normalize the five sources into one v1-compatible
native-union admission stage followed by one CBWU stage. If preserving a true
multi-parent admission graph is required, mint an explicit sidecar v2 DAG
contract; do not broaden v1.

### 2. The canonical five-seed route is incompatible with current v1 and is not
tested end to end

The donor recorder emits one sequential native stage for each seed and lets
each stage consume generated occurrences
(`src/nfl_dfs/inference/prelock_lineage_runtime_v1.py:444-506`). Current v1
permits occurrences only in the initial admission stage; each later stage must
consume the exact retained membership of its immediate predecessor
(`src/nfl_dfs/inference/prelock_candidate_lineage_v1.py:1127` on current main).

The bounded runner test monkeypatches `build_sim_lineups`, emits a single
`"single"` source, and never executes the real five-seed recorder path
(`tests/test_prelock_lineage_runtime_v1.py:645-692`). The live-CBWU test checks
callback propagation and one admission event, not a five-source recorder seal
(`tests/test_live_multiseed.py:82-195`).

**Required repair:** add an actual R0-R4 -> union -> CBWU -> typed selector ->
sealed sidecar integration test. It must reconcile every request, occurrence,
dedupe, admission, selected row, and final-book row.

### 3. Real GCS publication has a confirmed same-second failure

The runner converts its clock to whole seconds
(`prospective_prelock_lineage_shadow_v1.py:63-66`) but retains the provider's
fractional `time_created` (`:132-150`). It then supplies a truncated graph
creation time (`:414-423`). The graph adapter compares that whole-second value
directly with the terminal object's fractional provider timestamp
(`prelock_lineage_graph_summary_v1.py:240-244`).

When the terminal is created at, for example,
`16:30:00.500000+00:00` and the graph adapter runs at truncated
`16:30:00Z`, it fails with:

```text
PrelockLineageGraphSummaryError: graph summary creation predates its terminal provider object
```

This was reproduced locally. The passing test hides the defect by using an
exact whole-second provider timestamp and a later fixed clock.

**Required repair:** use one canonical timestamp precision everywhere, derive
the graph timestamp deterministically from trusted provider metadata, and test
the same-second/subsecond case.

### 4. The claimed exact retry is not a real-clock retry

The candidate `frozen_at_utc` is regenerated at runtime
(`prelock_lineage_runtime_v1.py:607-611` and runner `:350-357`), and graph
creation time is regenerated again
(`prospective_prelock_lineage_shadow_v1.py:414-423`). A retry minutes later
therefore produces different canonical bytes,
which the create-once reopen correctly rejects. The retry test passes only
because it gives both runs the identical `now_factory`
(`tests/test_prelock_lineage_runtime_v1.py:829-842`).

This is especially serious because the timestamp defect can strand a run after
the candidate, matrix, and terminal objects have already been published.

**Required repair:** make the runner reopen-first and state-aware. Reuse exact
timestamps and bytes from the first immutable object, resume from the last
valid boundary, and return an already complete final manifest without
regenerating the lineup book. Test retries at different clock times and after
failure at every publication boundary.

### 5. No durable root proves all five advertised objects

The terminal root binds only the candidate sidecar and selector matrix
(`prelock_lineage_runtime_v1.py:1285-1288`, `:1408-1415`). The candidate's
input-authority reference omits trusted creation time
(`prospective_prelock_lineage_shadow_v1.py:281-310`). The graph-summary provider
receipt exists only in the function result/stdout (`:424-449`). There is no
final create-once object that independently binds input authority, matrix,
candidate sidecar, terminal, and graph packet by URI, provider generation,
bytes, hash, and trusted pre-lock creation time.

**Required repair:** publish a root-last final manifest containing all object
identities and reopen every exact generation before declaring completion. Use
the already integrated production publication contract rather than inventing a
parallel receipt format.

### 6. Rescue scores can be assigned to the wrong candidates silently

`build_individual_rescue_v1` accepts a position-aligned `Sequence[int]`
(`prelock_lineage_settlement_v1.py:342-393`). A permuted score vector remains
valid but changes which candidate receives each realized score.

**Required repair:** accept keyed score rows containing both exact
`candidate_instance_id` and `roster_id`, reject duplicates/missing/extra rows,
and prove a complete one-to-one join before any rescue calculation. Bind the
winner score and outcome rows to their exact provider receipts. Keep the sum of
force-one rescues explicitly non-joint.

## P1 integration and authority findings

### 7. The donor replaces the current reviewed selector interface

The branch implements a mapping-based `trace_capture`
(`src/nfl_dfs/optimizer/lineup.py:640-829`). Current main already has the typed
`CoverageSelectorEvent` / keyword-only `event_sink` interface and exhaustive
instrumentation parity coverage. Replacing it would also invalidate the exact
source-set v6 identity. The four shared donor files have different hashes from
the v6-pinned engine, live-lineup, multiseed, and selector sources.

**Required repair:** adapt the recorder to current typed events. Preserve v5
and v6 exactly; if the port changes any frozen shared source, mint an explicit
later source/evidence version and run its complete gate.

### 8. The graph packet conflates strategy, objective, and retrieval preset

The donor obtains the selector objective at
`prelock_lineage_graph_summary_v1.py:373-375`, then writes that objective as
`retrieval_preset_id` at `:389` and `:402`. It also places the effective stage
ID in `admission_preset_id` at `:388`. Those substitutions would make the graph
answer the user's central strategy-comparison question incorrectly.

**Required repair:** retain current production
`prelock_lineage_graph_v2.py`, its immutable mapping-transform identity, and
its exact total selector-ID -> retrieval-preset-ID map. Do not add the donor's
second graph adapter.

### 9. The code/source identity is incomplete

The claimed implementation manifest at
`prospective_prelock_lineage_shadow_v1.py:38-52` omits directly imported
executable helpers `prospective_boom_first.py` and
`prospective_generation_shadow_suite.py` (`:29-31`). It also does not bind the
full transitive simulation/model/construction surface, model artifacts, solver
version, immutable image, or compute envelope.

**Required repair:** derive the execution identity from production's effective
policy source inventory and add a separately versioned lineage-adapter identity.
Bind the immutable image and solver/compute receipt for a real shadow. Do not
describe the current 13-file digest as the complete executable method.

### 10. The write boundary is broader than the five advertised GCS objects

The CLI accepts any bucket (`src/nfl_dfs/cli.py:139-145`; runner `:258`). The
runner also leaves the existing best-effort asynchronous BigQuery ownership
shadow enabled (`src/nfl_dfs/inference/live_lineups.py:491-496`; runner
`:360-382`). Thus the command is neither restricted to an approved location nor
limited to its advertised outputs.

**Required repair:** require an allowlisted bucket and prefix, pass
`_log_ownership_shadow=False`, and enforce a closed read/write manifest before
launch.

### 11. Salary authority is read twice without one snapshot

The runner reads and hashes `classic_salaries` at
`prospective_prelock_lineage_shadow_v1.py:229-251`, then calls `_slate_identity`
at `:239`; that helper independently re-queries salaries at
`prospective_boom_first.py:169-186`. If the store changes between calls, the
recorded catalog can differ from the allowed IDs, bridge, and salary overrides
actually used.

**Required repair:** read once, freeze one exact provider-backed dataframe, and
derive the catalog, bridge, allowed IDs, and overrides from those same bytes.

### 12. Outcome exclusion and feature intelligence are not yet complete

No direct outcome read was found in the capture path, and the settlement code
is physically separate. That is good. However, input exclusion remains an
exact-name denylist (`live_lineups.py:47-65`, `:105-133`) and misses aliases
such as `actual_ownership`, `field_ownership`, and `actual_rank`. The recursive
envelope guard checks mapping keys, not the strings stored in a `columns` list.

The score-blind input receipt hashes the effective player frame, but it does
not persist the values or a provider URI. Consequently this Phase 1 packet can
tell us where a candidate was lost, but cannot yet explain which boom,
coverage-map, ownership, role, matchup, projection, or correlation features
distinguished rescued and missed lineups.

**Required repair:** use a closed pre-lock input/read allowlist and create-once
archive the exact effective player-feature snapshot outside Neo4j. Bind that
artifact to the lineage root. Later aggregate analyses may join it by stable
player/slate identity; detailed feature and roster rows should remain outside
the v2 summary graph.

### 13. Settlement is correctly non-authoritative, and must remain so

Winner score, opportunity scores, confirmation rows, and settlement timestamp
are caller-supplied (`prelock_lineage_settlement_v1.py:139-202`, `:342-392`).
The false authority flags are appropriate. Do not use these readers for an
adoption claim until they exact-reopen complete standings, exact entries/field
bridge and access receipts, and accepted winner-registry-v2 evidence.

## Lab implementation disposition

The `nfl2` opportunity-lineage work at `5f3ade3` is useful as an isolated,
disposable lab-local shadow. Its focused suite passed 24/24 independently and
it improves several identity and settlement details. It is still **NO-GO** for
the production graph because it materializes full candidates under a separate
schema/custom loader, does not prove upstream first-loss stages from its
post-generation trace, uses mutable-on-match APOC loading, and still describes
the sum of mutually exclusive force-one rescues as a total. Full current 084
reference membership also remains unavailable.

Do not merge that branch wholesale. Reuse only compatible analysis ideas after
the production pre-lock root exists.

## Validation performed during this review

- All 70 directly changed contract/runtime/live-CBWU/paid-export focused tests
  passed on the donor branch.
- The same-second provider timestamp probe reproduced the failure above.
- `git merge-tree` against current main confirmed four source/test conflicts.
- Current production graph-publication hardening passed 39/39 focused tests,
  Python compilation, and `git diff --check`, and is now on `main`.
- The lab opportunity-lineage focused suite passed 24/24 independently.
- No lineup score, selector setting, policy, cloud job, deployment, graph row,
  or paid entry was changed during review.

Passing unit tests do not override the P0 failures because the bounded runner
test substitutes a single-source fake and freezes away both the real retry and
provider timestamp conditions.

## Fastest safe implementation sequence

1. Create a new integration branch from current `main`; do not merge the donor
   branch.
2. Port the runtime collector, settlement library, runner, admission callbacks,
   and paid seam selectively. Keep current v1 contract, typed selector events,
   v6 evidence, and hardened graph-v2 adapter.
3. Normalize R0-R4 into one v1-compatible union stage for the first shadow, or
   explicitly approve and implement a v2 DAG if multi-parent semantics are
   immediately necessary.
4. Implement reopen-first resume, uniform timestamp precision, and a root-last
   five-object manifest.
5. Make salary/input authority single-read, provider-backed, pre-lock-only, and
   feature-snapshot complete; close the bucket and write allowlists.
6. Change settlement joins from positional scores to exact candidate+roster
   keys.
7. Add actual five-seed end-to-end, instrumentation parity, same-second,
   later-clock retry, partial-resume, score-permutation, write-set, and
   salary-snapshot-race tests. Rerun the current graph, selector, source-v6, and
   paid-boundary gates.
8. Build from clean source and run one candidate-only 2026 shadow well before
   lock. Reopen the final manifest and all exact generations, prove the selected
   book equals the ordinary canonical-CBWU book, and inspect the graph packet
   offline.
9. Only then load the summary packet into a dedicated shadow graph. Keep
   post-lock settlement descriptive until its official source adapters exist.

This path preserves almost all useful donor work while protecting the scoring
pipeline and the identity of the evidence we are building to compare corpus
population and selection strategies.
