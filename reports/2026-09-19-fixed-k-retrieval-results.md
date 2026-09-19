# Fixed-K retrieval: no replacement survives the declared guards

The frozen search considered every replacement of rows 2–97 with an unselected candidate in the archived D6400 pool. **965 pairs improved combined modeled 220+ coverage without reducing coverage in either component. None preserved all the required score, utility, prefix and contest-block checks.** The diagnostic K97 book remains unchanged.

Source was frozen at `d0a41807`; [protocol](2026-09-19-fixed-k-retrieval-protocol.md), [executable](reviews/evidence/2026-09-19-fixed-k-retrieval.py), and [result](reviews/evidence/2026-09-19-fixed-k-retrieval.json) retain the inputs and identities. Synthetic replacement-count checks passed before freeze. The real run checked all 965 proposed pairs and terminated normally in 1.429 seconds after download, without reaching either cap.

| First failed check in the declared evaluation order | Pairs |
|---|---:|
| Component P220 in an affected protected set | 557 |
| Component expected maximum in an affected protected set | 402 |
| Component GLOBAL proxy in an affected protected set | 6 |
| All checks passed | 0 |

These are first-failure counts, not mutually exclusive causal explanations: a rejected pair might also fail later checks. Actual contest blocks were checked first, then affected prefixes in increasing size. The study does not establish which constraint causes the largest economic tradeoff.

Whole-book baseline estimates remain incumbent Emax 190.768908 and P220 7.51%; hsim Emax 210.640880 and P220 31.11%; mixture Emax 200.704894 and P220 19.31%. All input hashes, uniqueness, fixed Millionaire row and final no-harm invariants passed. No actual scores, current outcomes or bank 991 results were read.

The result closes only this **single-replacement, component-by-component no-harm search with all declared prefix/block guards on this finite Thursday archive**. It does not establish global optimality, eliminate multi-lineup exchanges, show that simulated probabilities are accurate, or establish that no useful tradeoff exists. In particular, the 965 initial pairs show that better modeled 220 coverage exists if some other constraints are allowed to change; this study does not authorize or evaluate those sacrifices as a live policy.

The next useful work is to trace the large component disagreement and assess a bounded reconstruction of already-opened historical missed candidates, where feasible. Repeatedly optimizing the same uncalibrated selection banks is not independent evidence. The earlier [allocation exchange](2026-09-19-contest-allocation-results.md) remains a separate model-conditional finding and cannot increase whole-book 220 coverage.
