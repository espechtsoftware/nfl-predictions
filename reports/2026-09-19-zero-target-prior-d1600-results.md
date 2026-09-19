# Target-prior selection at 1,600 candidates

The two historical priors change more selected lineups when the pool is larger, but **whole-book gains remain small and depend on the evaluation law**. Neither changes the ordinary EMAX first lineup. This does not support presenting the historical 27.94% eligible target-weight MSE reduction as a comparable lineup-performance gain.

The fixed one-prior-game book retains 81 of 97 baseline memberships; the learned past-empirical book retains 74. Both retain only five original ranks. All player banks, fitted coefficients and calibration weights are reused unchanged from the previously frozen simulator trace; the repaired 1,600-candidate pool is the only enlarged ingredient. Baseline bank and ordinary/WEMAX book parity pass exactly.

| New ordinary EMAX book | Independent evaluation mixture | Expected maximum change | P220 change (percentage points) | GLOBAL proxy change |
|---|---|---:|---:|---:|
| one_prior_game | baseline_equal_mixture | -0.095 | -0.040 | -0.000788 |
| one_prior_game | one_prior_game_equal_mixture | +0.037 | +0.125 | +0.000117 |
| one_prior_game | past_empirical_equal_mixture | -0.048 | -0.080 | -0.000579 |
| past_empirical | baseline_equal_mixture | -0.084 | -0.120 | -0.001288 |
| past_empirical | one_prior_game_equal_mixture | +0.086 | +0.075 | -0.000207 |
| past_empirical | past_empirical_equal_mixture | +0.062 | +0.050 | +0.000037 |

Under each prior's own evaluation mixture, ordinary selection gains only 0.037 or 0.062 expected maximum, with P220 changes +0.125 or +0.050 percentage points. Under the baseline mixture both lose expected maximum, P220 and proxy. The first lineup is identical across all three ordinary books, so its paired differences are exactly zero under every law. All component laws, paired Monte Carlo intervals, prefixes and contest blocks are published; no choice is based only on these headline rows.

WEMAX also remains a tradeoff. Against the corresponding prior's ordinary EMAX book, it loses expected maximum under all three mixtures. P220 sometimes rises, while the proxy changes are small. For both priors its first lineup is identical to the ordinary EMAX first lineup; this removes the baseline WEMAX first-row loss, but does not demonstrate a better whole-book selector.

The earlier simulator trace's support repair remains real: 19 previously zero-score eligible players recover, and the eligible players' simulated means move closer to the already-served model means. Those are model mechanics, not observed NFL correctness. This larger-pool result separates that useful repair from the still unproven selection benefit.

## Verification and next decision

Frozen expanded reader `60bcbb51`, elapsed 59.73 seconds, one CPU; no refit, new simulation, warehouse query or current outcome read. The frame's complete player order, original roster summation orders and every retained bank hash match the original trace and D1600 chain. Six books are scored under seven component/mixture laws over all declared prefixes and contest blocks. GLOBAL bandwidth remains 8.

The optional live implementation remains default-off. Its numerical parity validation is being completed for a concrete reviewable candidate; the larger result provides no strong reason to choose a prior for this weekend. Prior settings, selector adoption and contest assignments remain explicit operator decisions. The stronger immediate engineering case is the independently verified current-season input and pre-week-context repair, whose model-conditional full-chain effects are much larger.

[Full frozen result](reviews/evidence/2026-09-19-zero-target-prior-d1600-read.json). [Expanded protocol](2026-09-19-repaired-chain-d1600-protocol.md). [Original prior trace](2026-09-19-zero-target-prior-simulator-results.md). [Historical player-level screen](2026-09-19-zero-target-prior-results.md).
