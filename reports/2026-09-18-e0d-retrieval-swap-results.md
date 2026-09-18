# E0d retrieval search: small K80 gain, prefix screen fails

September 18, 2026. Frozen bounded search under the same finite D800 archive as E0c. No 2026 actual-score reads or live change. Independent review pending.

Three exhaustive best one-for-one replacements raised the modeled K80 GLOBAL_WEMAX_PROXY from 0.005977178 to 0.005992725 (+0.000015548, about 0.26%). The third accepted swap exhausted the declared budget; this is not proof of local or global optimality. Reordering the final set harmed K10 and K20 proxy values. The prespecified prefix no-harm screen FAILED. This treatment is not nominated for weekend use.

| Prefix | Proxy before | Proxy after reordering | Difference | P220 before | P220 after |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.000333012 | 0.000333012 | +0.000000000 | 0.00015 | 0.00015 |
| 10 | 0.001776994 | 0.001757469 | -0.000019525 | 0.00050 | 0.00050 |
| 20 | 0.002782421 | 0.002762354 | -0.000020067 | 0.00065 | 0.00060 |
| 40 | 0.004200361 | 0.004201719 | +0.000001358 | 0.00100 | 0.00105 |
| 80 | 0.005977178 | 0.005992725 | +0.000015548 | 0.00135 | 0.00135 |

K80 P220 remained 0.00135 (27/20000 archived columns). Raw expected K80 maximum changed by approximately -0.00165 points. The optimization changed three candidates, not predictive beliefs. These are conditional model quantities and not evidence against all retrieval improvements.

## Scope and verification

This is a heuristic-search diagnostic for the WEMAX sidecar objective, not a validated replacement for the live DEMAX selector. Prior PREREG-056 already tested WEMAX versus DEMAX on historical D800 pools with a flat primary result and harmed raw prefixes; that past test is not being rebranded as new here. Changing the search method, current population or calibrated law would require its own comparison.

Frozen source `976d2b820d6b4177848e99e0764fa5dcc6a23f78`, clean execution; script SHA256 `8e54629aeefa2b6601f0574cc4f85c327514ca7f3f1d179e9e91d4a9ee5e0eac`. Computation 8.034 seconds. Both exact397-player matrix hashes verified; baseline book reproduced E0c exactly. Optimized replacement evaluation passed a tied-best-world fixture and every accepted replacement matched full evaluation. Unique books, increasing K80 utility and permutation invariance passed.

[Protocol](2026-09-18-e0d-retrieval-swap-protocol.md), [source](reviews/evidence/2026-09-18-e0d-retrieval-swap.py), [full results](reviews/evidence/2026-09-18-e0d-retrieval-swap-results.json).
