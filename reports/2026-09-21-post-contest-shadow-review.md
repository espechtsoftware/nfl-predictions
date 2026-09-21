# Week-2 post-contest shadow review: D6400, D12800, and the next reads

This review separates three questions that are easy to conflate: whether a larger candidate dose creates more strong candidates, whether the selector recovers them, and whether a delivery or contest-ordering rule changes the entered result.

## D6400 versus D12800

The bank991 cross-read confirms that D12800 increased historical 200+ candidate supply from 365 to 716 (ratio 1.962, with the preregistered doubling verdict). The descriptive 220+ supply ratio was 1.676, but that was secondary and must not be called a confirmed doubling.

The larger dose did not reliably improve K80 retrieval: D12800 minus D6400 proxy was -0.01384, negative in both simulator components (-0.00201 and -0.02568), with a single-slate interval spanning zero. This is consistent with the Week-2 realized result: a larger pool can contain stronger lineups while the objective and projection errors prevent them from reaching the book.

The dose comparison is therefore not evidence that D12800 itself was a mistake. It says that increasing generation without fixing the forecast law and selection objective is insufficient. The Week-2 post-mortem's realized pool inversion makes the same point, but its -0.49 correlation is incumbent-specific; the independent bank review found incumbent -0.488, corrected HSIM -0.087, and equal-mass pooled -0.332.

## What the completed shadows already establish

- Greedy optimization is effectively solved for its current objective (historical exact audit gap about 0.134%). The next selector test must change the objective or calibration, not replace greedy with CBC.
- D6400's one-row frontier found a small modeled P220 gain only in a lower block (rank 94 exchange), with participation-adjusted interval spanning zero and no effect on the first 40 entries.
- D12800's individual-tail diagnostic found the delivered book enriched for simulated P220/P230, while omitted high-tail rows were often near-duplicates. Raw P220 sorting is not a valid fix.
- The D12800 ordering screen found a simulated first-row mean/P220 tradeoff. The fresh-book paired shadow, not the preview, is the relevant prospective read.
- The Week-3 runner is wired for `dual_emax` versus `cap_prefix_then_fill`, with prefix endpoints and realized 200+/210+/220+ reads. This is the highest-value next selector shadow.

## Post-contest process queue

1. Finish the Week-2 outcomes and standings capture audit. Keep rejected ownership-summary files rejected until entry-count reconciliation proves an entries-based tolerance is safe.
2. Trace Jefferson's served pre-blend value and the season-window contract at the exact serving commit. Label cross-season windows as a repair only after a reproducer and regression test show an implementation defect.
3. Attribute the pool inversion by simulator component (already independently measured) and by generator tag; do not tune mixture weights from this one slate.
4. Run the fixed-Week-3 selection-only arms: `dual_emax` control, `cap_prefix_then_fill`, exposure cap, market-agreement pull, top-salary spread, row-shape/late-game mix, and Week-1-riser guard. Freeze all arms before outcomes and retain one common pool, status snapshot, and contest map.
5. Keep the injured/no-prop exposure rule as a bounded shadow: questionable/doubtful cap 10%, 5% without a prop line, and explicit exception receipts. This is an insurance policy to test, not a claim that missing props mean zero availability.
6. After settlement, compare first-entry ordering and contest block costs separately from whole-book score. A first-row gain can be worthwhile for the Millionaire while lowering the displaced block; that tradeoff must be visible.

No selector or exposure rule should be promoted from D12800 simulated results alone. The operational priority is a clean, paired realized shadow with complete code/image/input identities and a rollback path.

