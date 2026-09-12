# Recourse-aware initial-book rotated-fit realized diagnostic protocol

Date frozen: 2026-08-29, before the score-free grid may license this realized
diagnostic and before this bridge opens any persisted realized attribution.

Protocol ID: `20260829-recourse-aware-initial-book-realized-bridge-v1`.

## Purpose and evidence class

The score-free experiment selects one unchanged control and one recourse-aware
treatment exact-80 initial book for each of five held-out world blocks on every
R6 slate. For each fold, four blocks train the selector and the fifth is held
out. This bridge asks whether treatment improved realized weekly maxima on
those frozen initial books.

Its evidence class is strictly
`five-fold-heldout-rotation-paired-diagnostic`. Each historical slate appears
once in each held-out rotation, yielding five explicit 54-week fold rows and a
pooled 270-book-week paired diagnostic. Those 270 observations are not 270
independent weeks, and their pooled mean is not a 54-week production final-fit
score.

The bridge does not fit one selector on all five blocks and score that final
selector across 54 weeks. Therefore:

- `all_block_final_fit_performed=false`;
- `all_block_54_week_benchmark_comparable=false`;
- `fold_rows_are_production_final_fit=false`;
- `scorecard_eligible=false`; and
- `ranking_beside_all_block_54_week_benchmark_forbidden=true`.

The output must not be inserted into, ranked beside, or described as improving
the project's all-block 54-week historical benchmark. It has no common-table
headline. A separately preregistered all-block final-fit run is required for
that comparison.

## Terminal score-free authority and causal order

The bridge accepts only the create-once terminal root at

`gs://nfl-predictions-503414-raw/research/recourse-aware-initial-book-runs/20260817-recourse-aware-initial-book-scorefree-v1/terminal-root.json`.

The root must have a supplied exact generation/content identity and satisfy
`reports/2026-08-29-recourse-aware-initial-book-terminal-root-amendment.md`
(SHA-256
`d43588901cb9c47f927646e5d394a4036cb5e8a7e626fb4208674bb82f93501a`).
It must bind the exact report identity, ordered 54-row shard identity ledger,
harvest/completion evidence hashes, fixed Job/UID, runtime code/image, passed
score-free gate, diagnostic license and terminal-before-outcome law.

Before invoking the realized reader, the bridge must:

1. exact-open and self-hash the terminal root;
2. prove the complete ordered shard identity ledger;
3. exact-open the root-bound newline-terminated report;
4. reject `realized_score_micro` and every outcome-like field at any depth;
5. enforce exact report, shard, fold and metric field sets;
6. prove every embedded shard's canonical bytes against its terminal-ledger
   identity; and
7. replay all 54 slates, 270 folds, source receipts, exact-80 books, aggregate
   values, conditions and passed disposition.

Any failure ends the bridge with zero realized reads. A report identity alone
is not sufficient authority.

## Frozen persisted attribution authority

The only admitted realized authority is the existing no-rescore full-union
attribution release:

- URI:
  `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-full-union-attributions/20260827-foundry-v12-r6-full-union-attribution-v1/attribution-release.json`
- generation: `1787852572673874`
- SHA-256:
  `caaddba5ef709b1e4df8c60480e2a50a37063917ef9b8d3c788f5e107133722b`
- bytes: `114551`

The bridge exact-opens this root and its manifest-known slate shards and maps
each frozen selected roster to its already persisted `realized_score_micro`.
It truthfully records `uses_realized_outcomes=true` and
`persisted_realized_attribution_read=true`, while
`raw_outcome_source_queried=false`. It may not query BigQuery, read raw contest
rank/ownership/payout, call a scorer, derive an outcome from player rows, list
a bucket, resolve a mutable generation, or substitute another snapshot. A
missing selected roster is terminal rather than permission to rescore.

All GCS reads, uploads, reloads and exact reopens use a timeout of at least 900
seconds. Generation-known reads/reopens carry an exact generation precondition
and the provider's generation-conditional retry policy. Create-once upload
carries `if_generation_match=0` with the same policy. Collision recovery may
reload boundedly, but only a generation-pinned exact reopen with identical
bytes can recover the operation.

## Scored objects and rotated-fit law

Only the frozen `control` and `treatment` initial books are scored. The
reachable union and hindsight-best alternative remain unscored. Each arm
publishes all `(slate, heldout_block)` weekly maxima plus five separately
identified held-out-rotation fold rows. The paired diagnostic compares
treatment and control at the same slate and same held-out fold.

Threshold counts use inclusive `>=` at 187, 194, 200, 210, 220, 230 and 240 DK
points. The report may show the pooled 270-book-week mean and deltas only under
names containing `rotated_fit` or `rotated`; it must accompany them with the
non-comparability laws above. No winner is selected, no favorable fold is
chosen and no historical retuning or production adoption is licensed.

## Mode-specific topology

`one-slate-smoke` validates the complete terminal score-free authority, opens
the attribution root and only source ordinal 0's shard, and publishes beneath
the fixed namespace with filename
`recourse-aware-initial-realized-one-slate-smoke.json`.

`full-54` opens all 54 attribution shards, exposes exactly five 54-week
held-out-rotation rows per arm, and publishes with filename
`recourse-aware-initial-realized-full-54-rotated-fit-diagnostic.json`.

The two filenames are mutually exclusive and machine-enforced. Both live only
beneath
`gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-recourse-aware-initial-realized/`.
Equal-byte create-once recovery is permitted; a different-byte collision is
terminal. Neither mode permits a parameter retry after scores are seen.

## Explicit exclusions and interpretation

This bridge does not score a reachable-union ceiling, apply a late-swap policy,
fit an all-block production selector, rescore a lineup, modify the graph,
change a live system, promote an arm, or authorize a money entry. A positive
treatment delta is evidence only that the held-out-rotation initial selector
improved this descriptive paired target. Flat or negative evidence means it
did not. Production comparison requires the separate all-block final-fit
54-week experiment.
