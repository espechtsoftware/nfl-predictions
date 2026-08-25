# Core v1 fast realized-scoring implementation plan

**Date:** 2026-08-25
**Status:** controlling fast-score amendment; implementation is outcome-blind
until the immutable Core v1 catalog closes

## 1. Decision

Do not wait for the entire offseason strategy census before producing the
first actual historical scores. Freeze and grade one complete, prespecified
Core Score Batch v1 containing:

- the accepted 54-slate Foundry v12 source panel;
- every accepted source-arm `coverage-194-v1` book at exact prefixes
  `4/14/80`;
- the four T230 final-fit retrieval laws at exact prefixes `4/14/80`;
- the final-fit support-switched T230 book at exact prefixes `4/14/80`; and
- the complete unique roster union from which those books were selected.

This is an exact **12-strategy x 3-budget x 54-slate** book lattice: seven
source-arm R194 strategies, four raw T230 strategies, and one support-switched
T230 strategy, each at 4/14/80 entries.  It therefore contains 1,944 frozen
book cells.  The strategy and contrast registries in section 4 are part of the
catalog authority, not choices that may be made after grading.

The Core v1 outcome boundary remains closed until all of those books exist,
are exact-replayed, and are immutable. It does **not** wait for future F/G/A
challengers, the 53-slate factorial, or every later selector.

Later experiments become separately versioned exploratory tranches. Each
tranche freezes its definitions and books before it is graded. Repeated use of
the same historical outcomes is labeled exploratory; it does not create fresh
confirmation. A separate confirmation/prospective boundary remains untouched.

## 2. Why this is faster without becoming misleading

The current pipeline couples three different events:

1. defining and selecting books;
2. acquiring historical player outcomes; and
3. computing book metrics.

They must be separated. Historical player outcomes are stable facts and should
be materialized once as one immutable score snapshot. Every strategy should
publish only lineup identities and indices into a shared slate union. One pure
grader can then project any frozen book from the same union score map without a
new deployment, matrix reconstruction, BigQuery query, or lineup rescore.

This preserves the important rule—selection precedes outcomes—while removing
the slow rule that every future idea must precede the first outcome read.

## 3. Core data flow

```text
G0 54-slate panel + accepted source carriers
        |
        +--> all source-arm unique rosters and R194 ranks
        |
T230 54-slate panel release
        |
        +--> four raw final-fit ranks + support-switched final rank
        |
        v
immutable Core v1 catalog (no outcomes)
        |
        +--> one exact player/DST source-key union
        |
        v
one historical outcome snapshot / one query
        |
        v
one union score map per slate
        |
        +--> corpus ceiling and >=200/>=230/>=250 supply
        +--> R194 4/14/80 books
        +--> raw T230 4/14/80 books
        +--> support-switched T230 4/14/80 books
        v
Core v1 realized grade and paired comparison report
```

## 4. Immutable Core v1 catalog

Add a pure module such as
`src/nfl_dfs/research/corpus_core_v1_catalog.py` and a narrow CLI. It must
exact-read and replay the published G0 panel, the terminal T230 panel release,
all 54 T230 results, the accepted carriers, and the seven source-arm result
objects.

For each source ordinal it retains:

- slate, panel-member, task-acceptance, carrier, T230 result and source-freeze
  identities;
- every source-arm unique roster, plus exact identities/hashes and aggregate
  summaries for occurrence lineage;
- one deterministic, deduplicated nine-player roster union;
- a roster-ID-to-union-index map and its hash;
- each source-arm R194 rank, represented as union indices;
- each of four raw T230 final-fit ranks, represented as union indices;
- the final-fit support-switched rank, represented as union indices;
- exact 4/14/80 prefix books for every retained rank; and
- exact book, strategy, population, scope, budget and implementation hashes.

The exact source-arm strategy order is:

1. `r194:incumbent`;
2. `r194:remove-salary-floor`;
3. `r194:remove-qb-stack`;
4. `r194:remove-bring-back`;
5. `r194:allow-rb-vs-dst`;
6. `r194:allow-two-rb`; and
7. `r194:remove-all-five-shared-constraints`.

The exact raw T230 strategy order is:

1. `t230:coverage-ge-230-v1`;
2. `t230:bounded-tail-ladder-ge-210-250-v1`;
3. `t230:block-robust-bounded-tail-ge-210-250-v1`; and
4. `t230:individual-ge-230-rank-v1`.

The twelfth strategy is `t230:support-switched-policy-v1`; each slate records
whether its frozen switch projected the literal-coverage or block-robust raw
book.  Budgets are always ordered `4, 14, 80`.

The frozen contrast registry is:

- **primary headline contrasts:** each of the five T230 strategies minus
  `r194:incumbent`, on the same slate and entry budget;
- **mandatory secondary fill-arm contrasts:** each of the five T230 strategies
  minus each of the other six R194 source arms, on the same slate and budget;
- **support-switch mechanism contrasts:** support-switched T230 minus each of
  the four raw T230 strategies, on the same slate and budget; and
- **source-arm diagnostics:** each of the six non-incumbent R194 arms minus
  `r194:incumbent`, on the same slate and budget.

Every registered contrast is published regardless of direction.  Because the
T230 population is the cross-arm union, the primary headline is explicitly a
whole-system strategy-book comparison, not a claim that only retrieval caused
the difference.

Core v1 uses only final-fit ranks for realized book comparison. Cross-fit
books and simulated heldout metrics remain retained in T230 evidence but do
not silently multiply the realized grade.

The catalog must prove:

- exactly 54 ordered unique source members;
- every roster is sorted, unique, legal and contains nine player IDs;
- every book is an exact prefix of one immutable rank;
- every selected roster occurs in the shared union;
- all expected baseline and T230 strategy/budget cells are present;
- no outcome, score, rank, payout or winner field was read; and
- all publication, promotion, decision and production authorities are false.

Catalog creation must use the already-terminal T230 release's structural
reopen.  It must not call a public per-slate validator that recomputes the
four-law science stack: the authorized T230 panel contains exactly 54 worker
computations and 54 independent verifier computations, and catalog extraction
is not a 109th science execution.  Source occurrence lineage may be retained
by exact identity and aggregate hash rather than duplicated into the root
catalog.  If the payload is large, publish 54 create-once slate shards plus one
small immutable root index.

Publish the catalog create-once outside the source and T230 prefixes. An equal
reopen is recovery; unequal content is a hard collision.

## 5. Reusable historical outcome snapshot

Add one generic outcome snapshot schema keyed by:

```text
(source_ordinal, season, week, slate_id, player_id)
```

The catalog's common later-source freeze provides the canonical player
catalog. Skill players query by GSIS/player ID; DST rows query by uppercase
team. Reuse the validated source projection and SQL primitives in
`corpus_realized_outcome_transport.py`, but bind them to the Core catalog
rather than a nonexistent single 54-task batch acceptance.

The snapshot must:

- derive the exact player/DST key union from every roster in the shared union;
- create the outcome-read attempt before the query;
- use one historical-outcome lease and one exact BigQuery query;
- convert scores once to signed integer micro-DK points;
- contain exactly one row for every required player/slate key and no extras;
- publish and exact-reopen outside every outcome-blind prefix; and
- record that field standings and payout ladders are absent in v1.

Before the query, catalog construction closes the exact player/DST projection
from the common later-source freeze.  Reuse the existing skill-player GSIS ID
and uppercase-team DST source-key law, exact decimal-to-micro conversion,
query-row rejection, table-metadata checks, historical-outcome lease and
create-once reopen primitives.  Bind them to `(source_ordinal, catalog_sha256)`
rather than to either lane's local task index.  The create-once read-attempt
object contains the complete sorted key union before BigQuery is invoked.  A
missing, extra or duplicate key is terminal; partial scoring is forbidden.

The snapshot is reusable by every later catalog fragment whose required key
set is a subset. A fragment needing new slates or players receives a new
versioned additive snapshot, not a rewrite.

## 6. Generic score-once grader

Add `corpus_catalog_realized_grading.py` as a pure, cloud-free module. For each
slate it must:

1. sum the nine exact player scores for every unique union roster once;
2. retain a content-addressed roster-to-realized-score map;
3. project every book by union index without summing a roster again; and
4. independently replay the projection before accepting the grade.

Per-slate union metrics:

- unique roster count and complete score coverage;
- actual maximum and top 3/5/10;
- counts at or above 180, 194, 200, 210, 220, 230, 240 and 250;
- fraction at or above each threshold; and
- the identities of `>=200` and `>=230` subsets for later characteristic
  analysis.

Per-book metrics at 4/14/80:

- maximum, mean, median, top-three mean and score distribution hashes;
- threshold counts and whether the book produced at least one hit;
- gap to the shared corpus ceiling;
- exact roster-score rows in rank order; and
- complete prefix consistency across 4, 14 and 80.

All score arithmetic remains signed integer micro-DK.  Means are retained as
exact integer `sum/count` rationals; medians are exact integer or two-value
rationals.  Floating-point summaries are not authoritative.  Core v1 freezes
the exact threshold vector `180/194/200/210/220/230/240/250`, which is a new
catalog-specific vector rather than an implicit reuse of the older seven-arm
grader's threshold registry.

Paired comparison output follows the frozen contrast registry above:

- T230 minus the named primary incumbent R194 weekly maximum and
  threshold-conversion changes, plus every mandatory secondary comparison;
- support-switched versus each raw T230 law;
- season summaries and leave-one-slate/leave-one-season sensitivity;
- every method reported, regardless of sign; and
- multiplicity labels and exploratory/confirmatory evidence class.

No contest rank, ROI or Milly payout claim is allowed in v1. Those require a
separately validated full-field entry file, duplicate/tie settlement law and
payout ladder. Actual DK points and threshold hits are available immediately.

## 7. Rapid recurring experiment interface

Every later experiment publishes the same small `book-catalog-fragment/v1`:

- fragment/strategy/implementation identity;
- source slates and shared-union identity;
- prespecified evidence class and family;
- one immutable rank plus exact 4/14/80 prefixes;
- one disposition per required scope; and
- false outcome authority at creation.

The grading service performs:

```text
validate fragment -> confirm books predate grade -> reuse outcome snapshot
-> project union scores -> publish grade fragment -> update experiment graph
```

A new selector therefore requires no deployment if its implementation is
already present in the reusable image. Parameter presets are data rows, not
code changes. A run records the fill preset, admission preset, selector
preset, source/matrix/catalog identities, runtime, scores and evidence class.

## 8. Research-validity labels

Use three explicit labels:

- `core-v1-prespecified`: baseline/T230 books frozen before the Core v1 read;
- `historical-exploratory-tranche`: later books frozen before their own grade
  but developed with prior historical grades visible; and
- `prospective-or-protected-confirmation`: outcomes unavailable during method
  development.

Exploratory improvement can inform Week-1 candidates, but it must not be
reported as independent confirmation. The already-frozen prospective k20/OI
shadow remains byte-identical.

## 9. Implementation order and target

Run these tracks in parallel:

1. finish the Rule-1 T230 smoke, G0 lock, two-phase image release and ordinal-0
   benchmark;
2. implement/test the Core v1 catalog and expected-cell census without
   outcomes;
3. implement/test the generic outcome snapshot and pure grader with synthetic
   fixtures;
4. run and finalize the 54-slate T230 panel;
5. create and exact-replay the Core v1 catalog;
6. acquire the outcome lease once, create the reusable snapshot and release
   it correctly; and
7. grade/publish Core v1, then expose it to Neo4j and the React UI.

The implementation is deliberately three small components on the score
critical path:

1. a pure catalog builder plus narrow outcome-blind CLI;
2. a Core adapter around the already-tested one-query/lease/snapshot
   primitives, with no grade embedded in the query transaction; and
3. a pure score-once catalog grader.

Neo4j, UI work, new matrices, full-field reconstruction and additional
selector families are downstream consumers, not prerequisites for the first
actual DK score report.

Target: complete T230 outcome-blind panel on August 26, actual Core v1 DK score
comparisons on August 27, with August 28 reserved for a source/schema repair.

## 10. Definition of done

- [ ] Core v1 catalog contains all 54 slates and every expected R194/raw-T230/
      support-switched final book at exact 4/14/80 prefixes.
- [ ] Every unique corpus roster is scored exactly once per slate.
- [ ] One exact outcome snapshot covers every required player/DST key.
- [ ] Every book score is a projection from the shared score map.
- [ ] Baseline and T230 results are paired on the same 54 slates.
- [ ] Actual DK score, threshold and corpus-ceiling metrics are published.
- [ ] Contest rank/ROI is explicitly unavailable until field/payout sources
      close.
- [ ] No historical result mutates a frozen selector or grants automatic
      promotion authority.
- [ ] Later experiments can submit catalog fragments without rebuilding the
      outcome source or rescoring shared rosters.
