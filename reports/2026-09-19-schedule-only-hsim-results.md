# Schedule-only sensitivity changes 25 of 97 selected lineups

Frozen source/design `7bd27f8e`; runtime31.147seconds. The original97 selection reproduced exactly. Changing only hsim's game totals/spreads from the benchmark to the archived live frame, with the435player frame, served means, usage and6400candidate pool held fixed, changes **25/97 memberships**. Seventy-two lineups remain;11retain the same rank. The first lineup is unchanged. Every activity classification and zero-score-player count is unchanged.

| Evaluation bank | Original book Emax | New book Emax | Original P220 | New P220 |
|---|---:|---:|---:|---:|
| Incumbent selection |190.768908|190.836378|7.51%|7.42%|
| Original hsim selection |210.640880|210.182502|31.11%|30.42%|
| Live-line hsim selection |211.414684|211.885498|32.75%|33.25%|
| Original hsim repeat, seed2426 |209.919074|209.809264|29.95%|29.56%|
| Live-line hsim repeat, seed2426 |209.791940|209.761938|29.34%|28.89%|

These are model quantities, not probabilities validated against real football. The new selection's advantage in its own hsim selection worlds does not persist in this first independent complete-simulator repeat. This is not evidence that stale inputs are preferable.

**Audit qualification:** `simulate_hsim` uses its seed for both400-world pilot calibration and final draws. Thus the seed2426 repeats also refit calibration weights; they are independent repeated simulator runs, not draws conditional on exactly the same calibrated weights used for selection. Their differences mix calibration randomness and final-world randomness. The design originally called these hsim-half audit worlds; that description needs this qualification. A separately frozen follow-up will retain the seed2326 calibrated weights and draw fresh final worlds. No incumbent independent audit is available in this archive.

Largest player mean shifts include Arizona DST+1.315, Jalen Milroe-1.253, Courtland Sutton+1.088 and Deebo Samuel+1.065. Mean absolute changes by position: DST0.366,QB0.159,RB0.173,WR0.144,TE0.177. The paid book would therefore differ even though its projected means and candidate supply stayed fixed. These values measure sensitivity, not which player will outperform.

Full [result](reviews/evidence/2026-09-19-schedule-only-hsim.json) records all players, book indices, prefixes, actual contest blocks, GLOBAL proxy, exact source/input identities and local score-array hashes. Arrays remain under `review-evidence/overnight-20260918/hsim-replay/`. No policy, live warehouse or entries changed. Next: fixed-calibration audit, independent code review and explicit live-only schedule-input repair design.
