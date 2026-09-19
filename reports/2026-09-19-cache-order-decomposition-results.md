# Historical values and row order both change the incumbent simulation

The four-way engineering comparison separates two causes: **changing historical values at fixed row order changes the fitted components and simulated worlds; changing row order while preserving all historical values also changes them.** Neither effect implies an improvement. The workstation cache remains unchanged.

Both original arms first reproduced their real saved CLI incumbent banks **bit for bit**. Two additional fits then swapped values/order separately, using the identical live frame, TabPFN cache, source, component-model count and seed. There were no new lineup solves, selection scores or current NFL outcome reads.

| Controlled change | Other factor held fixed | Different bank cells, of 4,280,000 | Mean absolute correlation change |
|---|---|---:|---:|
| Host → fresh historical values | Host order | 3,817,536 | 0.011196 |
| Host → fresh historical values | Fresh order | 3,817,854 | 0.011241 |
| Host → fresh row order | Host values | 3,817,601 | 0.011236 |
| Host → fresh row order | Fresh values | 3,818,553 | 0.011195 |

In every contrast, every player's complete score multiset remains identical. Correlation summaries cover the same 402 nonconstant players and 80,601 pairs. About 3,200 of 4,378 component predictions change in each contrast. Component predictions have mixed units, so their maximum numeric difference is not an overall model-accuracy metric.

This establishes computational sensitivity to training order as well as source values. It does **not** establish that the true joint distribution changed dramatically: a small change in component rates can rearrange the simulator's pseudorandom draws, and these are single-bank descriptive correlations without an independent Monte Carlo baseline. Nor does it establish that order alone changes 89 selected lineups; that membership count came from the original two-cache comparison, which changed both factors. The model-only counterfactuals do not generate books.

A durable cache contract should bind source/query identity, schema, content and ordered keys, and training should use a deliberate reproducible ordering. That is a future implementation and validation task, not an instruction to rewrite the current cache on build morning. Reproducibility alone is not a scoring gain; any later ensemble or order-robustness proposal needs a distinct frozen predictive/lineup test and cost budget.

All four fits completed in approximately 15.6–15.9 seconds each. The original reporting stage failed because `np.std` on float32 constant rows had rounding noise, admitting constant defenses into a correlation calculation and producing NaN. The original partial JSON and log are retained. A separate read-only reader uses exact row range to exclude constant rows and float64 covariance, then rereads the same saved outputs. No refitting, changed contrasts or source-data edits followed that failure.

[Protocol](2026-09-19-cache-order-decomposition-protocol.md), [complete result and hashes](reviews/evidence/2026-09-19-cache-order-decomposition.json), [frozen producer](reviews/evidence/2026-09-19-cache-order-decomposition.py), [corrected diagnostic reader](reviews/evidence/2026-09-19-cache-order-decomposition-read.py), [original two-cache proof](2026-09-19-host-cache-effect-results.md). Independent review requested; this is engineering evidence, not an efficacy ledger entry.
