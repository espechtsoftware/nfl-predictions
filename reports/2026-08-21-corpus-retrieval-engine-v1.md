# Corpus retrieval engine v1

Date: 2026-08-21
Run ID: `20260821-corpus-retrieval-engine-v1`
Status: outcome-blind engineering pilot; default-off research deployment only

## Objective

Turn an immutable candidate corpus into a reusable intelligence surface.  For
each slate, score every distinct corpus lineup in every retained simulated
world, preserve every strict score-above-200 event, analyze where those events
come from, and compare fixed retrieval laws at one exact 80-lineup budget.
The resulting fill insight is an input to a separate, versioned corpus producer;
the retrieval engine never mutates its own input corpus.

This first run is an engineering pilot because preliminary outcome-blind
simulated-score summaries were inspected while the implementation was being
built.  It has no historical-outcome, live-money, default-on, or automatic
corpus-fill authority.

## Immutable task-0 input

Task 0 is the current-money 2023 Week 1 slate.  It binds the exact five
generation-pinned R0--R4 NPZ artifacts registered by the retained source lock:

`gs://nfl-predictions-503414-raw/research/production-law-dependence-runs/20260817-production-law-dependence-source-lock-v1/source-lock.json`

The source-lock identity is generation `1786950155692968`, SHA-256
`7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c`,
and 1,341,911 bytes.  The five task artifacts are:

| Block | Panel | Generation | Bytes | SHA-256 |
|---|---|---:|---:|---|
| R0 | `20260815-atlas-money-worlds-r0-v1` | 1786843060343205 | 31,752,021 | `c35ecb83ecc8cacb802735f5b4f44c64b8733822e0d36e9475bab1b68de65498` |
| R1 | `20260815-atlas-money-worlds-r1-v1` | 1786842999474453 | 31,826,199 | `391e770f5a0d51f4375b7239a7184681039e1769d4fe4122b0d7e216c30b2f8f` |
| R2 | `20260815-atlas-money-worlds-r2-v1` | 1786843081394196 | 31,713,457 | `e5de1cd0be8ee3ad990f9ea8a399f8b03bf3e0b18d8441f2ad98fc6b66a52046` |
| R3 | `20260815-atlas-money-worlds-r3-v1` | 1786843100083841 | 31,788,248 | `17f66dd5727513182c8634dc1184e616d41bb60c474209075b6043925b3c5ef3` |
| R4 | `20260815-atlas-money-worlds-r4-v1` | 1786843157821536 | 31,718,004 | `1b0e7bce938bfb532b4f563f2f466645ff5a18039cb0c1b41e36f0b5713daba0` |

Candidate identities, ordered roster IDs, `tag`, and `all_tags` are captured
from the five matching `replay_candidates_staging` panels without selecting
any realized-score column.  Point-in-time player identity, position, team,
opponent, game, salary, and projection fields are frozen separately.  Runtime
scoring has no BigQuery client and consumes only generation-pinned objects.
Each query receipt retains the raw query-row digest and separately binds the
canonical normalized-row digest.  Runtime replay recomputes the latter for
both candidate and player bodies, so a same-count substitution fails closed.

## Complete scoring law

1. Validate each source object by URI, generation, SHA-256, byte count, NPZ
   member order, dtype, shape, and finite-value checks.
2. Validate exact candidate-index coverage in each block.
3. Form the union of canonical sorted nine-player roster identities and retain
   complete source membership and all source tags for each unique lineup.
4. Reconstruct every lineup total from the exact player-world matrix in each
   block.  Every native candidate row, including repeated roster identities,
   is an independent reconstruction check.  The numeric tolerance may not
   change either side of any registered `>=` or `>` boundary at 194, 200, 210,
   or 220.
5. Concatenate R0--R4 in fixed order.  The retained score matrix shape is
   `[unique_lineups, 50_000]`, float32.  No lineup or world may be sampled,
   truncated, or omitted.
6. Materialize every event satisfying the literal condition `score > 200.0`.
   Event order is block, world, lineup.  Lineup lineage remains in the indexed
   lineup table rather than being duplicated once per event.

Task completion must state and independently replay
`every_unique_lineup_scored_in_every_world=true` and the exact
`unique_lineups * 50_000` score count.

## Analysis retained from the strict event population

The compact analytical layer records:

- a producer-safe R0--R3 discovery enrichment and a distinct R0--R4
  descriptive enrichment; only the former may feed the fill-insight object.
  The discovery universe excludes lineups found only by the R4 candidate
  panel and removes every R4 membership and tag from shared lineups.  Those
  R4-origin lineups remain fully scored in the descriptive union;
- event counts by block, world, lineup, source family, player, player pair,
  team, team pair, game, tag, and roster structure;
- supported player-pair, team-pair, and stack enrichment, with both event and
  lineup support retained so sparse apparent lifts cannot masquerade as broad
  evidence;
- correlations for the fixed top high-overlap lineup-pair set, clearly labeled
  as overlap-prefiltered rather than global top correlations, plus a global
  exact duplicate score-vector census;
- complete source lineage for every lineup;
- a graph projection containing compact nodes, relationships, measurements,
  and exact generation/SHA/byte pointers to every analytic sidecar; and
- a score-free fill-insight object for the independent corpus producer.

The authoritative large bodies are compressed NPZ objects in object storage:
the full score matrix, the strict-event table, and each selected score matrix.
A graph database may index relationships and summaries, but it must not replace
or inline those large immutable bodies.

## Frozen retrieval suite

All strategies select exactly 80 lineups from the R0--R3-origin eligible
lineup universe using R0--R3 discovery scores only and are evaluated unchanged
on held-out R4.  A lineup first exposed by the R4 candidate panel can never be
selected:

1. `coverage-194-v1`: greedy marginal world coverage at `score >= 194`.
2. `strict-200-coverage-v1`: greedy marginal strict coverage at `score > 200`.
3. `tail-ladder-200-210-220-v1`: greedy marginal strict tail utility with
   weights 1, 4, and 12 at `>200`, `>210`, and `>220`.
4. `mean-score-v1`: highest discovery-world mean score with stable identity
   ties after strict-`>200` event count.

Every strategy reports discovery, held-out, and all-world mean-max and tail
coverage summaries.  No result may alter a strategy, threshold, weight,
budget, split, or tie law.  All secondary objectives and identity ties are
part of each strategy's hashed registry row, and v1 rejects any budget other
than literal 80.

## Production boundary and storage

The reusable Cloud Run job is permanently deployed in a generic, default-off
`parked` command.  A task requires a literal execute flag, an enable gate, one
immutable image digest, one task, parallelism one, attempt zero, and retries
zero.  The task writes create-once objects only and publishes its authority
last.  Terminal acceptance reopens every object by generation, SHA-256, and
byte count, semantically rebuilds both enrichments, redundancy, fill insight,
selection traces, and graph projection, and proves the job remains parked.

Runtime storage is a dedicated `us-central1` bucket,
`gs://nfl-predictions-503414-corpus-retrieval`, with uniform bucket-level
access and public-access prevention.  The dedicated runtime service account
has no project role.  Its only planned grants are conditional object-viewer
access to the exact input and output prefixes and object-creator access to the
exact output prefix.  The existing broad Editor compute identity and the
legacy ACL-based raw bucket are forbidden for this run.  Immediately before
the smoke, the operator must also retain an effective-access census covering
inherited, group, and public-principal grants; ambiguous effective access is a
NO-GO even when the direct bucket-policy validator passes.

The first accepted milestone is one task-0 score-and-analysis receipt.  It does
not authorize a live strategy change.  Subsequent fill work is a separate
producer run with a new snapshot ID; improvement is measured by rerunning the
same frozen retrieval suite and comparing held-out R4 before any broader
rollout.

## Implementation checkpoint — 2026-08-21 13:55 CDT

The pure engine and its focused adversarial suite are 17/17 green.  Tests
cover exact complete scoring, strict `>200`, literal exact-80 rejection at 79
and 81, exclusion of R4-only candidate identities and R4 tags from discovery,
R4 score invariance of both selection and fill insight, exact score-vector
duplicates, noncontiguous eligible-to-global index mapping, source replay,
same-count candidate/player source substitution, graph semantic corruption,
and batch completion.
The graph, fill insight, and live-policy licenses remain false where required.

The deterministic input-publication suite is 5/5 green.  It builds the core's
canonical outcome-blind query authority, validates the complete candidate,
player, producer, snapshot, and suite chain before its first write, publishes
candidate/player objects against the real returned query-authority generation,
reopens every staged object exactly, and publishes completion last.  A crash
after a partial write is terminal for this run ID; partial state is never
deleted or silently resumed, and only the final completion receipt proves a
usable snapshot.  The added adversarial capture test proves a normalized-row
hash mismatch causes zero publication calls.

The reuse-only Cloud Run transport suite is 23/23 green.  It binds the clean
source commit, Cloud Build, immutable image digest, dedicated service account,
UBLA/PAP-enforced bucket and exact two-prefix IAM law; records create-once execution intent,
launch consumption, execution name, terminal state, result, and inventory;
and never relaunches after an absent or ambiguous execute response.  The
worker waits for its own durable execution-name binding before it scores.
All worker-side governance and ledger discovery uses exact-object GET followed
by a generation-pinned reopen; the worker never requests bucket LIST, which a
prefix-conditioned object-viewer grant cannot authorize.  Namespace and
sole-generation censuses remain mandatory operator-side immediately before
launch and again during terminal acceptance.

The first exact cloud receipt is not yet claimed.  The execution environment
currently cannot resolve `oauth2.googleapis.com`; consequently no input query,
bucket/service-account/IAM mutation, image build, job update, or Cloud Run
execution occurred during this checkpoint.  The frozen query job IDs and
generation-pinned source identities remain safe to retry once connectivity is
restored.  The local Git metadata is also mounted read-only, so this milestone
cannot be committed or pushed from the current session.

Two independent read-only audits of the final hashes found no code P0/P1 in
the worker-list/PAP lane and no remaining code P0 in the combined scoring,
input, and transport chain.  The implementation verdict is GO for exactly one
gated, outcome-blind, real-artifact task-0 smoke; immediate cloud execution is
still NO-GO until the external prerequisites above and the mandatory effective-
access census pass.  Raw query-row digests are retained but the raw rows are
not, so those raw digests cannot be recomputed later; the normalized bodies
that determine scoring are retained and fully replayed.  Semantic parsing of
the exact-reopened snapshot-producer authority is deferred provenance
hardening and does not license a broader rollout.
