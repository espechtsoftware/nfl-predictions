# E0b results: candidate count increases optimism without equal selection loss

September 18, 2026. Exploratory synthetic K1 study following workstation review 88db03f. No NFL outcomes read; no operational changes. Independent replication pending.

## Result

At a fixed 10,000 decision worlds, decision optimism rose across the nested candidate counts in these constructions. With heterogeneous true means, it reached about 0.45–0.47 synthetic points at 12,560 candidates, while true selection regret was only about 0.052. With equal true means, optimism reached about 0.67 while regret was exactly zero by construction. Thus selection optimism and recoverable selection loss are different quantities; the former cannot be used as the latter.

| Law | Quality | Candidates | Mean optimism | Mean true regret | Mean independent audit error |
|---|---|---:|---:|---:|---:|
| A (.5) | FLAT | 12 | 0.2462 | 0.0000 | 0.0204 |
| A (.5) | FLAT | 100 | 0.3973 | 0.0000 | 0.0135 |
| A (.5) | FLAT | 1000 | 0.5343 | 0.0000 | 0.0007 |
| A (.5) | FLAT | 3200 | 0.6073 | 0.0000 | 0.0242 |
| A (.5) | FLAT | 12560 | 0.6668 | 0.0000 | 0.0170 |
| A (.5) | GAPS | 12 | 0.0207 | 0.0000 | -0.0193 |
| A (.5) | GAPS | 100 | 0.0531 | 0.0282 | -0.0151 |
| A (.5) | GAPS | 1000 | 0.2471 | 0.0647 | -0.0197 |
| A (.5) | GAPS | 3200 | 0.3877 | 0.0659 | 0.0166 |
| A (.5) | GAPS | 12560 | 0.4534 | 0.0525 | 0.0089 |
| B (.1) | FLAT | 12 | 0.2520 | 0.0000 | 0.0108 |
| B (.1) | FLAT | 100 | 0.3866 | 0.0000 | -0.0116 |
| B (.1) | FLAT | 1000 | 0.5475 | 0.0000 | 0.0016 |
| B (.1) | FLAT | 3200 | 0.6066 | 0.0000 | -0.0011 |
| B (.1) | FLAT | 12560 | 0.6733 | 0.0000 | -0.0099 |
| B (.1) | GAPS | 12 | -0.0042 | 0.0000 | 0.0177 |
| B (.1) | GAPS | 100 | 0.0149 | 0.0158 | 0.0143 |
| B (.1) | GAPS | 1000 | 0.2979 | 0.0965 | -0.0095 |
| B (.1) | GAPS | 3200 | 0.3992 | 0.0686 | 0.0006 |
| B (.1) | GAPS | 12560 | 0.4663 | 0.0519 | 0.0278 |

## Review disposition and limitations

The review correctly requested the candidate-count axis. This follow-up includes 12/100/1000/3200/12560 nested candidates, with 100 replicates per law/quality/count cell: 2000 selections. It is deliberately K1, whose exact optimum is available without combinatorial search. The result cannot answer the review’s stronger question of whether noise dominates real NFL error at production counts. Matching nominal counts does not match candidate dependence, quality gaps, heavy tails, book size or world-law error.

All candidates share six factors; larger pools are not more independent candidates. Their factor loadings, and therefore volatility, vary. Increasing the nested pool can expose larger loadings. Both arms share coefficients, samples and candidate order. GAPS offsets are fixed independently before sampling. Its true regret is not monotonic in candidate count here; no monotonicity claim was frozen.

Independent audit estimates retain finite sampling error. Conditional independence gives unbiasedness for the selected fixed book; it does not make any one audit estimate exact. Original E0’s population greedy gap was zero; that result still cannot quantify general greedy search loss.

## Checks and provenance

Frozen source `efdf9e92462312145aec29c84ac559f96a08ea84`; recorded working tree clean: True. Runtime 0.103 seconds. Python 3.14.4, NumPy 2.5.3; BLAS/OpenMP single-threaded. Script hash `884b089d40272de1e6bde81846ebb5098c894a18518e3c85462d076e076606cd`.

All 2000 unique cells passed exact-mean centering, nonnegative true regret, flat-arm zero regret, and nested decision-maximum checks. Every selected decision/audit value was independently recalculated within the script using scalar weighted sums. RNG streams for generation, decision and audit are distinct by construction. These are internal checks, not independent peer reproduction.

[Frozen protocol](2026-09-18-e0-candidate-count-protocol.md), [script](reviews/evidence/2026-09-18-e0-candidate-count.py), [full results and Monte Carlo uncertainty](reviews/evidence/2026-09-18-e0-candidate-count-results.json).

## Next step

Stop extending synthetic examples for now. Transfer the measurement contract to the existing pool only after defining an honest independent evaluation target. The archive identity census establishes an 800-candidate pool but shows that both saved matrices were selection components. Existing per-candidate audit means cannot evaluate a portfolio maximum. See the updated archive-readiness report for the next bounded choices.
