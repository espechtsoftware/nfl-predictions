# Historical evidence for replacing structural zero target priors

Both predeclared priors improve target-share calibration in **all six evaluated seasons**. The prior learned only from earlier seasons reduces squared error by **27.94% among the affected observed-zero players** and **1.09% across all active receiving players after team normalization**. The smaller fixed prior improves those measures by 15.98% and 0.41%. Both qualify for the planned simulator influence trace. Neither result establishes a lineup-score gain or authorizes a live change.

| Rule | Affected-player target-share MSE | All-active, team-normalized MSE | Seasons with lower affected-player error |
|---|---:|---:|---:|
| Current observed zero | 0.00202680 | 0.00602047 | — |
| One-prior-game rule | 0.00170284 | 0.00599573 | 6/6 |
| Past-season empirical rule | 0.00146051 | 0.00595488 | 6/6 |

The affected group consists of RB/WR/TE players with zero prior target share, at least 20% prior snaps, at least one prior game and the existing activity mask true. Across 2019, 2021, 2022, 2023, 2024 and 2025, **349 of 938 eligible player-weeks subsequently received targets** (37.2%), totaling 673 targets. That directly contradicts a structural assumption that these players cannot receive a target. It does not imply that all deserve large shares or that most become high-scoring players.

Each season's learned prior uses only earlier seasons. It groups by position, prior snaps and prior-games count, with fixed shrinkage; no strength or bin search was performed. The fixed alternative uses existing positional fallbacks, diminished by prior-games count. All noneligible weights and all carry priors remain unchanged. After normalizing each team's full target-weight basket, average error across all active receiving players also improves in each of the six seasons. This addresses displacement costs before the simulator's separate, nonlinear calibration step.

There were no missing or negative target labels among these evaluation panels and all 938 eligible rows had valid team totals. However, these are warehouse training-universe team totals, not a separately authenticated complete play-by-play census. Between 950 and 1,332 known annual targets fell outside the existing activity mask in the evaluated years; neither tested rule changes that mask. This remains a separate support limitation. The repeated historical panel is development data, and these player-level errors are exploratory; no p-value, fresh-holdout claim or realized 220+ result is asserted.

The next step is to apply both frozen rules to the completed repaired-chain frame, recalibrate hsim, retain separate audit worlds, and compare their fixed-pool selections against the repaired baseline under all component laws. Check recovered support, changes to established players, first lineup, all prefixes and contest blocks. The incoming peer suggestion to make the rule tight-end-only is not adopted after seeing these results: the predeclared scope includes all three receiving positions, and residual structural zeros can matter even when they were present before the salary repair.

[Protocol](2026-09-19-zero-target-prior-protocol.md), frozen reader `1938d377`, [full result](reviews/evidence/2026-09-19-zero-target-prior-read.json). Synthetic temporal/missing-label/nullable-type/index tests passed before freezing. Execution took under one second locally, with no cloud job, warehouse write, vendor request, current-season label read or lineup-outcome read. The common 102,927-row historical input is the same immutable snapshot used in the complete-chain rehearsal; the older hsim benchmark itself ends in 2024 and was not changed.
