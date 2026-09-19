# Direct 220 objectives: selection gains did not survive the independent audit

On the repaired fixed pool of 1,600 candidates, directly optimizing simulated 220+ coverage does **not** improve independent 220+ coverage over ordinary EMAX. Optimizing expected excess above 220 also fails to improve the mixture's independent tail metric. Both sacrifice expected maximum and the GLOBAL proxy. The apparent selection-bank advantage is not enough.

| Objective | Selection-bank P220 | Independent repaired-mixture P220 | Independent expected maximum | Independent GLOBAL proxy |
|---|---:|---:|---:|---:|
| emax | 17.430% | 17.195% | 199.900 | 0.146607 |
| wemax | 17.790% | 17.245% | 199.773 | 0.146376 |
| coverage220 | 18.100% | 17.120% | 199.449 | 0.144781 |
| excess220 | 17.590% | 17.055% | 198.872 | 0.143387 |

Coverage220 changes 28 of 97 memberships and loses **0.451 expected maximum** (paired Monte Carlo 95% interval [-0.556, -0.346]), **0.075 percentage points P220** (interval [-0.326, +0.176]) and 0.001827 GLOBAL proxy versus ordinary EMAX. Expected excess220 selection changes 25 memberships, loses **1.027 expected maximum**, and changes P220 by **-0.140 percentage points** (interval includes zero). Its own target, independent expected positive excess above 220, changes by -0.007 (interval includes zero).

Both methods choose the same alternative first lineup as the existing WEMAX shadow. Under the repaired mixture that first lineup loses 2.516 expected points while P220 changes only +0.010 percentage points, with an interval spanning zero. Under the old mixture it loses expected points and P220. Thus this test does not justify putting that alternative into the first, highest-prize entry.

The components disagree in a revealing way. Excess220 improves repaired hsim P220 by +0.390 percentage points and its expected positive excess by +0.113, while incumbent P220 falls 0.670 percentage points and expected excess falls 0.127. The mixture-level tradeoff is unfavorable; a hsim-only headline would hide that. Complete prefixes, all 12 contest blocks, P194/P240 and both old/repaired cross-audits are retained.

Selection noise remains a plausible part of the problem: coverage220 gets 18.100% on its selection worlds versus 17.120% on independent worlds. That observed gap is not an unbiased estimate of all optimizer bias, and not proof that simply adding draws fixes selection. It motivates a bounded test using additional independent selection draws and a fresh audit. The candidate pool, forecasts and calibration should stay fixed in that test, so it can distinguish finite-simulation precision from model correction.

Frozen protocol/reader `f16ad722`; 13.32 seconds on one CPU. Synthetic objective/tie fixtures and all real input-bank identities passed before freeze. Original ordinary EMAX order and all previously published ordinary/WEMAX audit metrics reproduce exactly. Every tested book is fully scoreable under every law. No fitting, warehouse query, actual outcome, threshold sweep or live change occurred. [Protocol](2026-09-19-direct-220-selection-protocol.md). [Full result](reviews/evidence/2026-09-19-direct-220-selection.json).
