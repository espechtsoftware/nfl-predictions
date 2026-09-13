# Player-level "boom similarity" screen — closed at the screen stage (2026-09-13, 05:30 CT)

**Question (operator, Sunday morning):** can a process that compares each player to historical high performers
(similarity search / performance score) order lineups better than the selector does?

**Design (player level, walk-forward, no lineup result read):** 89 development slates (2019, 2021–2024), rosterable
skill players (mean projection ≥ 3; 17,223 player-weeks; 30+ rate 3.3%, 40+ rate 0.6%). For each player-week
in season S, the kNN boom score = share of its 100 nearest player-weeks from seasons < S (same position, euclidean
distance over 55 standardized point-in-time features: salary, projection quantiles, market points, usage windows,
jumps, red-zone/goal-line usage, air yards, WOPR, team totals/spread, pace/PROE, opponent allowed metrics,
practice level, separation, vacated shares, component means) that scored 30+ (40+). Baselines: the projection's
own tail (`proj_p90`, mean projection) and a walk-forward logistic on [mean, p90, std, salary, market] with and
without the kNN score. Script: `scripts/knn_boom_similarity_screen.py`; results: `results.csv` in the sidecar dir.

**Result — the similarity score carries no information beyond the projection, and little on its own:**

| season | target | booms | AUC proj p90 | AUC mean proj | AUC kNN | top-decile boom rate: proj p90 / kNN |
|---|---|---:|---:|---:|---:|---:|
| 2021 | 30+ | 110 | .825 | .825 | .615 | .119 / .065 |
| 2022 | 30+ | 119 | .828 | .842 | .597 | .122 / .032 |
| 2023 | 30+ | 103 | .821 | .824 | .632 | .142 / .048 |
| 2024 | 30+ | 92 | .809 | .828 | .493 | .099 / .022 |
| 2024 | 40+ | 16 | .760 | .797 | .462 | .012 / .009 |

Walk-forward logistic (2024, history 2022–2023 with market points): AUC .827 baseline vs .827 with the kNN
score; log-loss .1104 vs .1109; kNN coefficient −0.08. Same picture at 40+.

**Reading.** "Players who look like past boomers" is already what the projection stack encodes (TabPFN marginals
are an in-context learner over the same rows; the booster and the prop-market blend sit on top), and a plain
similarity over the feature vector is a much weaker version of it. There is no incremental boom information to
order lineups by. This matches the earlier rejections of the fast-role archetype features and the M2 residual judge.
The idea is closed at the screen stage at zero cloud cost; no ordering shadow is frozen from it.

**What would still be worth trying (not tonight):** a signal the projection does not see — late market movement
and cross-book dispersion, activated news, point-in-time tracking traits — evaluated the same walk-forward way
before any lineup-level use (the ledger's frozen reopening condition for selectors).
