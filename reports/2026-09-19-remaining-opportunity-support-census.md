# Remaining zero-opportunity support after usage recovery

Restoring usage fixes the large missing-history failure, but it does not make every simulator opportunity prior nonzero. A descriptive read of the already-opened four-case D audit finds **29 RB/WR/TE players that pass hsim's activity mask yet score exactly zero in all 10,000 saved worlds**. Twenty-five have positive prior-week snap shares; eighteen have positive Fantasy Points prior-week route shares. None of these 29 is in D's selected book. One other, inactive-mask WR with zero hsim support remains selected.

| Position | All zero-score players | Active-mask zero-score players | Active zeros with positive snaps | Active zeros with positive FP routes |
|---|---:|---:|---:|---:|
| RB | 35 | 3 | 3 | 0 |
| WR | 59 | 3 | 3 | 3 |
| TE | 43 | 23 | 19 | 15 |

For example, the archived/repaired-usage inputs give Calvin Ridley snap share 0.64 and FP route share 0.59, but target/carry priors and final calibrated weights are zero. His archived incumbent mean is 3.016 while the saved hsim scores are all zero. This is a model-input/support observation, not a claim about current status or future scoring.

The mechanism is explicit in `hsim/shares.py`: missing share priors receive a small positional fallback, but observed zero priors stay zero. Allocation includes only positive weights. Multiplicative calibration cannot revive a zero weight. With only one prior game, an observed zero can therefore become a structural exclusion from a scoring opportunity family. That is a modeling choice to investigate, not permission to add arbitrary floors to the entered book.

All eighteen positive-route cases also have positive free snap-share evidence. This census therefore does **not** establish incremental paid-data value beyond the free activity signal. Routes may still distinguish pass participation from blocking more precisely than snaps; that needs a comparison after the repaired baseline is complete.

Next bounded question: compare a predeclared weak prior for eligible observed-zero shares against the current zero-preserving implementation, using the same served means and a separate route-informed arm. Fit any prior strength using prior seasons only; distinguish players with no observed opportunities from players with credible inactivity evidence; preserve team opportunity totals and evaluate marginal calibration before selection. Report whether the effect survives full candidate generation and independent I/H audits, including first lineup and contest blocks. This census itself does not nominate a live change or justify renewing either vendor.

[Complete rows and counts](reviews/evidence/2026-09-19-recovered-usage-zero-support.json), source `1f37f98b`. No new simulations, cloud queries or current outcome reads; it reuses the authenticated archived frame, recovered usage, fixed D calibration/audit and saved 265-row FP support extract. It is a descriptive follow-up, not a new confirmatory experiment.
