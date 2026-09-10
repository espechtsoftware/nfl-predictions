# R6 prefix ranking and breakout-capture audit

**Date:** 2026-09-10  
**Evidence class:** retrospective development diagnostic  
**Decision:** the historical K80 books are not reliably ordered for a reduced
bankroll, and the candidate population supplies too few 230-point outcomes.
Preserve full-book generation, but do not represent entry rank as calibrated
breakout priority until a held-out reranker passes.

## Exact source and authority

The audit uses the 54 already-scored, structurally validated R6 attribution
shards under the accepted E0/Neo4j evidence chain. It performs no raw outcome
query, lineup rescore, Neo4j mutation, or production-policy change. The exact
persisted grade-root identity remains:

- URI:
  `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-full-union-realized-grades/20260826-foundry-v12-r6-full-union-realized-v2/realized-grade-root.json`
- generation: `1787823913707002`
- SHA-256:
  `7e5da240f6ad3978553fa3101e12d4414c993f9547bb76cfa999cf32acdb6dfc`
- bytes: `5,480,030`

The new deterministic reader validates all 54 full attribution shards before
calculating a row-free summary. Its complete audit SHA-256 is
`2731f8c25e8c49b13781f929e163f2c39e81f7a60a9ca0427b32f3dcdf00198d`.
The panel has already been opened, so this result is not adoption authority.

## The failure has three distinct stages

For any target and paid prefix K, every slate is assigned to exactly one of:

1. no eligible candidate reaches the target;
2. the eligible union reaches it, but the K80 book misses it;
3. K80 captures it, but the scorer falls below the paid prefix; or
4. the paid prefix captures it.

This prevents a selector miss from being described as a generator miss, and
prevents a poor ordering from being hidden by a good K80 maximum.

At 230 points, the shared eligible union has supply on only 3 of 54 slates.
That is the dominant failure: 51 slates have no 230-point candidate to rank.
But ordering also fails on the rare opportunity slates. The strongest K80
strategies capture two of the three; none places a 230 scorer in its first 20
entries. Tail-ladder and regime-robust first capture at K40 and retain both by
K57. Coverage-194's sole captured 230 scorer is rank 61, while expected-max's
two captures both fall below rank 57. Mean-score is the only strategy with a
230 capture by K3, but captures only one of the three opportunity slates.

At 200 points, eligible supply exists on 29 of 54 slates, yet each K80 strategy
captures only 6 or 7. Depending on strategy, K20 captures only 1 to 4 slates.
This remains poor even though 200 points is below the operator's stated
winning-score target.

## Final-book ordering signal

`selection_priority` is `-selection_rank`, so a positive Spearman value means
the selector tends to place higher realized scores earlier. The reported value
is the mean of 54 within-slate correlations; it does not pool incompatible
slate score levels.

| Strategy | Mean K80 max | Mean union max | Mean regret | Median rank of realized book max | Priority rho | Training-mean rho |
|---|---:|---:|---:|---:|---:|---:|
| Block-supported tail ladder | 178.435 | 202.662 | 24.227 | 41.5 | +0.0296 | +0.1768 |
| Coverage 194 | 176.882 | 202.662 | 25.780 | 45.0 | +0.0341 | +0.1632 |
| Expected max | 176.537 | 202.662 | 26.125 | 51.0 | +0.0353 | +0.1701 |
| Mean score | 176.003 | 202.662 | 26.660 | 44.5 | +0.0357 | +0.0357 |
| Regime-robust ladder | 177.103 | 202.662 | 25.559 | 32.5 | +0.0161 | +0.1702 |
| Strict 200 coverage | 176.359 | 202.662 | 26.303 | 37.0 | +0.0424 | +0.1769 |
| Strict 230 coverage | 177.462 | 202.662 | 25.200 | 40.5 | +0.0319 | +0.1764 |
| Tail ladder 200/210/220 | 178.435 | 202.662 | 24.227 | 41.5 | +0.0292 | +0.1749 |

The current rank is therefore nearly uncorrelated with realized score. The
training-mean feature contains a modest signal for seven strategies, but the
sequential book objective largely destroys it in the final order. Mean-score's
special case confirms that simply sorting by its current training mean is also
not enough: its historical priority correlation is only `+0.0357`.

## Bankroll consequence

The generated 80/90-lineup book and the paid subset must be treated as separate
objects. Full-book generation should continue because it preserves candidate
coverage and supports late news. A reduced bankroll should be expressed as a
declared top-K prefix only after that order has its own validation. The present
historical order is not safe to use as evidence that entries 1--20 or 1--40
have the best breakout probability.

This audit does not prescribe a spend amount. It establishes that reducing
spend by blindly truncating the existing order would discard rare tail captures
in the very cases the book succeeded.

## What Neo4j knows and does not know

The accepted E0 graph can answer candidate supply, final-book membership,
realized threshold, selector regret, and selection-rank questions. It already
shows that 241 of 279 generated 200-plus lineups never appear in any final-fit
book and that only 10 of 29 opportunity slates are converted by the union of
all observed strategies.

It still cannot attribute those misses to portable pre-lock predictors because
the graph lacks the complete candidate transition lineage and the point-in-time
feature overlay: projection distribution, ownership/leverage, boom traits,
Fantasy Points/SIS matchup traits, duplication, selector marginals for every
candidate, and D800 generation/admission/replacement edges. Those absences are
now explicit data requirements, not assumptions that the metrics are
uncorrelated.

## Required experiments

Two arms must be kept separate.

1. **Supply arm:** under the same compute and legality budget, test whether a
   direct extreme-tail generator increases held-out eligible-union opportunity
   at 220/230 without a material loss at 187/200. This addresses the 51-of-54
   no-supply result.
2. **Same-pool ranking arm:** freeze an identical candidate pool and learn a
   walk-forward, pre-lock-only breakout score from prior folds. Compare the
   incumbent order with one hybrid reranker that combines portable phenotype
   probability and existing book-marginal value. Report K1/K3/K5/K10/K20/K40/
   K57/K80 capture at 187/194/200/210/220/230/240, prefix weekly maximum,
   first-hit rank, NDCG/rank correlation, calibration, scenario overlap, and
   full-book utility.

The ranking arm must use separate search and audit world banks. Player identity
must not be a primary feature, and source/as-of/missingness identities must be
explicit. Historical results from this opened panel remain development-only;
prospective 2026 freeze and settlement retain adoption authority.

## Reproduction

```bash
PYTHONPATH=src python scripts/analyze_corpus_r6_prefix_ranking_v1.py \
  --execute \
  --attribution-shard-dir \
  /home/erich/projects/nfl-predictions/.scratch-neo4j-intelligence-20260901/attribution-shards
```

The command emits canonical compact JSON to stdout. It includes no individual
lineup, player, entry, or contest rows.
