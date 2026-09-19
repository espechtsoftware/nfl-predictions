# Scratch prediction refresh completed and passed

Both isolated full-refresh executions succeeded. Their **65,455 historical prediction rows are exactly identical** across every compared mean and quantile. Both have the same 877 Week2 player keys, finite values and ordered quantiles. The shared Cloud Run job template is unchanged, and the registered launcher completed and released its lane at **02:41:47 UTC**, well before the 14:45 UTC operator refresh window.

| Arm | Execution | Start UTC | Finish UTC | Rows |
|---|---|---|---|---:|
| Control | `tabpfn-gen-djgpj` | 02:11:52 | 02:26:50 | 66,332 |
| Salary repair | `tabpfn-gen-22x8d` | 02:27:24 | 02:41:35 | 66,332 |

The repaired Week2 predictions differ for all 877 players. Across that complete feature universe, mean absolute change is 0.95 points for the cache mean, 2.08 at the 95th percentile and 2.52 at the 99th percentile. Signed changes average −0.17, −1.24 and −1.75 points, respectively. Those are marginal-cache changes, not changes to lineup scores: the live lab consumer subsequently recenters the draws to served production means. The full generation/selection rehearsal will establish the downstream effects on the eligible slate.

Both arms ran the same immutable image and source-checked adapter, four estimators, seed7, context cap28,000 and historical RNG progression. Common sorted training order and strict pre-Week2 label filtering were applied to both. The repaired arm adds 863 legitimate prior-week context rows and repaired inference features; the 43 same-week labeled rows were excluded before label materialization. This is the complete repair effect under a shared valid context rule, not an isolated feature-only or context-only experiment. Exact historical parity supports the comparability of the runs. These newly generated caches are not claimed to reproduce the old unordered live cache bit for bit.

The first attempt's erroneous 928-Week2-row guard and safe failure remain documented in the [protocol](2026-09-19-tabpfn-scratch-refresh-protocol.md). The corrected key census was frozen before the successful retry; no prediction threshold or model was tuned after failure. Only the two previously absent scratch cache tables were written. Live features, caches and projections remain untouched.

[Execution and registry evidence](reviews/evidence/2026-09-19-tabpfn-refresh-v2-completion.json); [cache checks and differences](reviews/evidence/2026-09-19-tabpfn-scratch-read.json). Sources `32646535` and `83a2f27d`. The bounded full CLI control run has started against these frozen inputs, followed serially by the repaired arm.
