# Complete repaired-chain rehearsal and independent lineup audit

The full live CLI succeeds with both control and repaired features, refreshed TabPFN cache and production projections. Each run produces **97 legal entries from160candidates**, with original identity, eligibility and projection-level guards intact. Both independent incumbent and hsim audit banks are retained. The repaired book improves expected maximum, P220 and GLOBAL proxy under **both repaired-input audit models**. The control-input mixture is approximately flat at97 and prefers the control book's early rows. This is model-conditional evidence, not established NFL scoring improvement.

## Complete-chain effect

| Independent evaluation law | Repair minus control expected maximum | P220 change (percentage points) | GLOBAL proxy change |
|---|---:|---:|---:|
| Control incumbent | −0.559 | +0.030 | −0.002002 |
| Control hsim | +0.462 | −0.040 | +0.000472 |
| Control equal mixture | −0.049 | −0.005 | −0.000765 |
| Repaired incumbent | +0.975 | +0.540 | +0.003311 |
| Repaired hsim | +2.073 | +1.090 | +0.008351 |
| Repaired equal mixture | **+1.524** | **+0.815** | **+0.005831** |

Under the repaired mixture, the97-entry expected maximum rises192.030→193.555 and P220 rises9.150%→9.965%. Conditional paired Monte Carlo95%intervals are[1.311,1.737]points and[0.379,1.251]percentagepoints. Under the control mixture, both corresponding intervals include zero. These intervals cover finite audit draws conditional on the supplied models, inputs and calibration; they do not cover model accuracy, calibration uncertainty, or NFL randomness. The archived6400-candidate usage-only factorial is a different experiment and its larger gain must not be substituted for this160-candidate result.

Only5of160candidates overlap between arms, and only2of97ordinary selected lineups overlap; the first lineup changes. The common player universe has428players; the repair adds RileyNowakowski (RB, served mean1.62), for429total. That additional player appears in none of the four fixed books, so **all books are fully scoreable under all four audits**. No missing player was assigned zero. The repaired rows change316players' recent usage fields and397players' served means; mean/projection, cache-shape and current-prior-context effects are combined here.

## Ordering and contests

All declared prefixes1/10/20/30/40/80/90/97 improve all three metrics under the repaired mixture. Its first lineup gains2.789expected points and0.095percentagepointsP220; the latter's MonteCarlointerval includes zero. The control mixture prefers its original first lineup by3.734expectedpoints and the original early prefixes. This disagreement remains material.

Whole-book and prefix gains do **not** guarantee improvement in each separately entered contest. The single lineup at row25 loses15.999expectedpoints and0.670percentagepointsP220 under the repaired mixture versus the control row25. Several later blocks also trade off metrics. Portfolio marginal order is not automatically the best assignment to every contest; this remains an allocation question for the eventual chosen book, separate from whether the input repair is correct. All12blocks, every prefix and each component law are in the full result.

The existing same-pool WEMAX shadow is a small tradeoff on the repaired pool: under the repaired mixture it changes97-entry expected maximum by−0.024points (interval includes zero), P220by+0.090percentagepoints and GLOBALproxyby+0.000189 versus the ordinary repaired EMAX book. Its first lineup is identical. Under the control mixture, its expected maximum and proxy worsen. This does not establish a general selector promotion; no objective or allocation was changed live.

## Execution and verification

Control run`20260919T024305522029Z-2dc116c` took76.49seconds; repair`20260919T024517639539Z-2dc116c` took60.68seconds. Source is lab`2dc116c`, actual game-input repair`40a9be9`, adapter/reader`90a26b4f`. Both use32leverage+128boom,97entries,10000worlds,K1,seed2026, original EMAX and predeclared WEMAXsidecar. This is a small-dose integration rehearsal, not a production-dose runtime test.

The same102,927historical training rows are exactly equal; current non-arm warehouse reads are frozen and replayed identically. Every retained bank passes shape/dtype/finite checks. Recomputed hsim calibration reproduces the CLI selection bank exactly, and its independent final audit uses the same weights. Preserved candidate player order reproduces the actual CLI's original audit means exactly. Full source/file/query/bank identities and comparisons are in the [frozen reader output](reviews/evidence/2026-09-19-repaired-chain-read.json). [Protocol](2026-09-19-repaired-chain-cli-protocol.md). No2026lineup outcomes, bank991, live warehouse writes, timer changes or uploads were used.

Next: the two historically nominated target priors proceed through the [calibrated simulator trace](2026-09-19-zero-target-prior-simulator-protocol.md). Complete peer source review and prepare the concrete release/rollback package while that runs. The build remains Saturday15:30UTC; no automatic deferral is inferred from the fact that part of the implementation is in the lab repository.
