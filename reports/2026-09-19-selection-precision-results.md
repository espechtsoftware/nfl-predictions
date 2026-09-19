# Five times as many selection draws: modest precision gains, no clear ordinary P220 gain

The enlarged selection simulation improves ordinary EMAX's fresh-audit expected maximum by **0.099 points**, while its P220 changes by **-0.090 percentage points**, with an interval spanning zero. The first ordinary lineup stays identical. This is a measurable but small precision effect, not an explanation that resolves the missing high scorers by itself.

The same fixed 1,600 candidates, forecasts, served means, fitted components, calibrated hsim weights and equal I/H mixture were used throughout. Four extra independent 10,000-world batches per component were added to the original batch: **100,000 selection worlds instead of 20,000**. Primary evaluation uses a completely fresh pair of audit banks, declared before the run.

| Selector | Fresh expected maximum | Fresh P220 | Fresh GLOBAL proxy | Fresh expected excess above 220 |
|---|---:|---:|---:|---:|
| emax | 199.868 | 16.665% | 0.144641 | 2.316 |
| emax_5x | 199.967 | 16.575% | 0.145221 | 2.326 |
| coverage220 | 199.557 | 16.750% | 0.144924 | 2.399 |
| coverage220_5x | 199.642 | 16.755% | 0.145604 | 2.414 |
| excess220 | 198.925 | 16.690% | 0.142795 | 2.372 |
| excess220_5x | 199.423 | 16.925% | 0.145173 | 2.421 |

## What changes with precision

Ordinary EMAX changes 19 of 97 memberships, with first lineup unchanged. Its paired Monte Carlo 95% interval for expected-maximum gain is **[0.018, 0.180] points**; P220's interval is **[-0.294, +0.114] percentage points**. The new incumbent audit is nearly flat/slightly worse while the new hsim audit provides most of the expected-maximum gain. Older inspected repaired/control audits also prefer the larger-draw EMAX book on expected maximum, but they are secondary cross-checks, not the primary result.

Coverage220 barely changes fresh P220 versus its original small-draw version: **+0.005 percentage points**, interval spanning zero. Its expected maximum improves 0.085 points, also with an interval spanning zero. It still loses 0.225 expected maximum versus original ordinary EMAX; its P220 gain over that baseline is uncertain.

Excess220 benefits most from added draws: versus its own small-draw version it improves **0.498 expected maximum**, **0.235 percentage points P220**, and 0.002378 proxy on the fresh mixture. Against original ordinary EMAX, however, it remains a tradeoff: **-0.445 expected maximum**, **+0.260 percentage points P220** (paired interval [+0.020, +0.500]), and an uncertain proxy gain. Its components pull in opposite directions: incumbent P220 falls 0.830 percentage points while hsim P220 rises 1.350. Under the old-input mixture it loses both expected maximum and P220. All comparisons and intervals are retained; this exploratory screen has multiple contrasts and does not establish NFL efficacy.

Both enlarged tail-objective books choose another first lineup whose fresh mean is 144.426 versus ordinary EMAX's 148.606. Its P220 is 0.930% versus 0.885%: a small modeled probability tradeoff for a substantial mean loss. This is not a demonstrated better Millionaire entry. The ordinary first lineup remains the stable choice in this particular simulation-precision comparison.

## Verification and interpretation

The bank-construction phase first replayed the complete small CLI and authenticated all warehouse snapshots and four benchmark tables. The saved frame, all five original banks, captured incumbent function and fixed hsim calibration reproduced exactly. Ten new banks were saved with full content identities before comparisons. Construction took **63.37 seconds**; the selection/audit reader took **79.01 seconds**, each inside its separate 600-second one-CPU cap.

The first adapter safely refused before generating extra draws because it compared an internal frame with the persisted frame without accounting for the CLI's explicit removal of the normalized-name helper `nkey`. V2 verifies that sole helper exactly and preserves equality of every saved column. Failure evidence remains; no forecast or scoring rule changed. Frozen design/reader `63d9a032`, bank adapter amendment `5e28e22e`, saved bank identities `7844b994`.

More simulation precision is useful, but the observed ordinary-selector effect is much smaller than the current-season input correction's model-conditional effect. The tail-objective findings reinforce unresolved disagreement between the two forecast laws. Improving player/opportunity calibration and testing that disagreement against historical or prospective outcomes remains necessary.

No live change is made. Raising the CLI's `--sims` value would also change candidate generation, so it would not reproduce this experiment: a production implementation needs a separate selection-draw budget. Before considering that implementation, measure its benefit across historical slates and at the actual operational candidate dose. Do not increase production runtime simply because one simulation contrast is favorable.

[Protocol](2026-09-19-selection-precision-protocol.md). [Saved new banks](reviews/evidence/2026-09-19-selection-precision-banks.json). [All independent and secondary audit results](reviews/evidence/2026-09-19-selection-precision-read.json). No new warehouse reads, NFL outcomes or bank991.
