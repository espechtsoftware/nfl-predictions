# E0 known-law experiment: completed first read

September 18, 2026. Exploratory synthetic study; independent peer review pending. No NFL outcomes, vendor requests, cloud executions or production changes.

## What the experiment establishes

The implementation separates decision-sample optimism from true selection value under an exactly known law. Across the four declared law/book-size cells, increasing decision worlds from 32 to 2048 reduced average true regret. This is a measurement demonstration, not an estimate of recoverable NFL regret or a recommendation to increase live simulation budgets.

| Law | Book size | Worlds | Mean true regret | Mean decision optimism | Mean independent audit error |
|---|---:|---:|---:|---:|---:|
| A (p=.5) | 1 | 32 | 2.5000 | 6.1437 | 0.0001 |
| A (p=.5) | 1 | 128 | 1.0800 | 3.0309 | -0.0302 |
| A (p=.5) | 1 | 512 | 0.3400 | 0.6303 | -0.0280 |
| A (p=.5) | 1 | 2048 | 0.0000 | 0.0216 | -0.0400 |
| A (p=.5) | 3 | 32 | 2.5580 | 4.0273 | -0.0018 |
| A (p=.5) | 3 | 128 | 0.6658 | 1.2573 | -0.0095 |
| A (p=.5) | 3 | 512 | 0.2642 | 0.2471 | 0.0053 |
| A (p=.5) | 3 | 2048 | 0.0000 | -0.0058 | -0.0055 |
| B (p=.1) | 1 | 32 | 1.0600 | 2.5859 | 0.0825 |
| B (p=.1) | 1 | 128 | 0.3200 | 0.6277 | 0.0476 |
| B (p=.1) | 1 | 512 | 0.0400 | 0.1705 | 0.0548 |
| B (p=.1) | 1 | 2048 | 0.0000 | 0.0201 | 0.0529 |
| B (p=.1) | 3 | 32 | 1.3217 | 2.9948 | 0.0774 |
| B (p=.1) | 3 | 128 | 0.5073 | 0.9085 | 0.0566 |
| B (p=.1) | 3 | 512 | 0.0984 | 0.4118 | 0.0532 |
| B (p=.1) | 3 | 2048 | 0.0084 | 0.0232 | 0.0478 |

All values are arbitrary synthetic score units. Each cell uses 100 selection replicates; audit samples contain 8192 independent states. Audit errors can share a sign across world counts because the same audit bank is deliberately reused within each replicate. Near-zero average error does not mean every individual audit is precise.

## Important limits and next decision

- The exact population greedy gap is zero, up to floating-point error, for both declared laws and both book sizes. Thus this construction does **not** demonstrate a nonzero population greedy limitation. Keep that limitation; do not tune the construction after seeing results and present the tuned result as prespecified.
- The signed empirical-exact versus greedy comparison was negative in 34 of 1600 cases: greedy sometimes beat the empirical optimum when evaluated under truth. Optimization of noisy estimates and optimization under truth are different. The decomposition accounts for this without calling the signed component a necessarily positive search loss.
- All 2048-world cells had zero average true regret except law B/K3 (0.0084). This small synthetic candidate population is easy relative to real lineup selection; these rates cannot prescribe NFL world counts.
- Threshold 220 here is merely a threshold on invented scores. No finding measures real P(220+), improvement in an entered book, vendor value, or profitability.
- Next step: inspect metadata and schemas of the already identified Week-1 D800 candidate/frame/player-score archive, without reading actual scores. Establish identity, ordering and independent-audit feasibility before drafting a bounded real-pool pilot. Do not regenerate a historical panel.

## Reproducibility and checks

Frozen source commit: `db6a565337f63b4a0b46de8a61de4d4b21691f93`; clean working tree at execution. Script SHA256 `c83833e50373effbaabe0bc72df2c1aa8f0ad9a23f1ac4884aed2d1e8b359218`. Python 3.14.4, NumPy 2.5.3. All three BLAS/OpenMP thread limits set to 1. Experiment compute time 0.184 seconds, below the five-minute cap; no cloud spend.

Initial mechanics checked probability mass, deterministic ties, exact-objective dominance, K1 agreement, and a complementary-candidate fixture that distinguishes marginal gain from standalone mean. The run asserted the decomposition for every case. A separate direct scalar calculation subsequently recomputed all 1600 greedy true values and regrets from the saved arrays and confirmed the complete unique-key census. This is internal verification, not an independent agent reproduction.

Executable: [E0 script](reviews/evidence/2026-09-18-e0-known-law.py). Full arrays, seeds-by-contract, books, per-case values, quantiles, Monte Carlo standard errors and paired contrasts: [results JSON](reviews/evidence/2026-09-18-e0-known-law-results.json). [Protocol and explicit pre-execution amendment](2026-09-18-e0-known-law-protocol-draft.md).

The operator directed continued progress without waiting. The pre-execution amendment explicitly changed review-before-execution sequencing; the workstation review remains outstanding. Results must not be labelled independently cleared.
