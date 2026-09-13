# Pool-level learned lineup score — historical test (2026-09-13, outcome-blind for 2026)

Training: 216 opened D800_DEMAX books (PREREG-094 banks 940-942, 2021-2024), ridge on within-book-standardised lineup features, held-out season never seen (LOSO). Test corpus: the Neo4j PREREG-083 candidate pools (2023-2024, 36 slates x 2 arms, 200 candidates per slate-arm, realized scores, DEMAX K80 book marked). Rule = which K of the 200 to enter; metric = realized max of the K. Script: scripts/week1_pool_level_test.py; features: scripts/week1_learned_order_live.py; live application: scripts/week1_learned_score_live.py. DIVn = greedy by score with pairwise overlap <= n; EXPm = additionally single-player exposure <= m%.


### K=30  (72 slate-arms; realized max of the chosen K; delta vs DEMAX)
| rule | mean DEMAX | mean rule | delta | wins | losses | 2023 delta | 2024 delta | ctrl delta | trt delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LEARNED_POOL | 171.06 | 176.17 | +5.11 | 0.57 | 0.24 | +1.08 | +9.14 | +5.24 | +4.98 |
| LEARNED_DIV5 | 171.06 | 176.71 | +5.65 | 0.58 | 0.22 | +2.34 | +8.95 | +6.21 | +5.08 |
| LEARNED_DIV5_EXP40 | 171.06 | 177.14 | +6.07 | 0.58 | 0.21 | +3.03 | +9.11 | +6.92 | +5.22 |
| LEARNED_DIV5_EXP50 | 171.06 | 176.73 | +5.67 | 0.57 | 0.22 | +2.34 | +8.99 | +6.26 | +5.08 |
| LEARNED_DIV5_EXP60 | 171.06 | 176.80 | +5.74 | 0.58 | 0.22 | +2.34 | +9.13 | +6.40 | +5.08 |
| BLEND_Q99 | 171.06 | 173.57 | +2.51 | 0.40 | 0.29 | +1.24 | +3.78 | +0.36 | +4.66 |
| BLEND_DIV5 | 171.06 | 174.72 | +3.65 | 0.44 | 0.25 | +1.96 | +5.35 | +2.45 | +4.85 |
| BLEND_DIV5_EXP40 | 171.06 | 174.09 | +3.02 | 0.39 | 0.25 | +1.25 | +4.79 | +2.84 | +3.20 |
| BLEND_DIV5_EXP50 | 171.06 | 173.94 | +2.87 | 0.43 | 0.26 | +0.40 | +5.35 | +1.46 | +4.29 |
| BLEND_DIV5_EXP60 | 171.06 | 174.24 | +3.18 | 0.43 | 0.26 | +1.01 | +5.35 | +1.50 | +4.85 |
| UNION | 171.06 | 174.15 | +3.08 | 0.38 | 0.19 | +1.61 | +4.56 | +2.27 | +3.90 |
| RESORT | 171.06 | 173.07 | +2.01 | 0.38 | 0.25 | -0.41 | +4.42 | +2.36 | +1.65 |
| Q99 | 171.06 | 169.72 | -1.35 | 0.21 | 0.26 | +0.05 | -2.74 | -3.81 | +1.12 |

mean overlap of LEARNED_POOL top-30 with the DEMAX top-30: 6.6

### K=80  (72 slate-arms; realized max of the chosen K; delta vs DEMAX)
| rule | mean DEMAX | mean rule | delta | wins | losses | 2023 delta | 2024 delta | ctrl delta | trt delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LEARNED_POOL | 179.86 | 181.17 | +1.31 | 0.36 | 0.25 | -0.06 | +2.68 | +1.65 | +0.98 |
| LEARNED_DIV5 | 179.86 | 182.52 | +2.66 | 0.39 | 0.17 | +1.61 | +3.71 | +2.48 | +2.85 |
| LEARNED_DIV5_EXP40 | 179.86 | 183.03 | +3.17 | 0.40 | 0.14 | +2.51 | +3.83 | +3.49 | +2.85 |
| LEARNED_DIV5_EXP50 | 179.86 | 182.55 | +2.69 | 0.39 | 0.15 | +1.67 | +3.71 | +2.54 | +2.85 |
| LEARNED_DIV5_EXP60 | 179.86 | 182.52 | +2.66 | 0.39 | 0.17 | +1.61 | +3.71 | +2.48 | +2.85 |
| BLEND_Q99 | 179.86 | 181.85 | +2.00 | 0.31 | 0.11 | +1.89 | +2.11 | +2.89 | +1.10 |
| BLEND_DIV5 | 179.86 | 182.57 | +2.72 | 0.35 | 0.10 | +3.12 | +2.32 | +3.96 | +1.47 |
| BLEND_DIV5_EXP40 | 179.86 | 182.59 | +2.73 | 0.36 | 0.10 | +3.22 | +2.23 | +4.19 | +1.26 |
| BLEND_DIV5_EXP50 | 179.86 | 182.67 | +2.81 | 0.36 | 0.10 | +3.12 | +2.51 | +4.09 | +1.54 |
| BLEND_DIV5_EXP60 | 179.86 | 182.44 | +2.58 | 0.35 | 0.11 | +3.12 | +2.04 | +3.69 | +1.47 |
| UNION | 179.86 | 181.78 | +1.92 | 0.29 | 0.14 | +1.92 | +1.92 | +3.60 | +0.24 |
| RESORT | 179.86 | 179.86 | +0.00 | 0.00 | 0.00 | +0.00 | +0.00 | +0.00 | +0.00 |
| Q99 | 179.86 | 177.73 | -2.13 | 0.08 | 0.26 | -0.96 | -3.30 | -2.63 | -1.62 |

mean overlap of LEARNED_POOL top-80 with the DEMAX top-80: 35.9
max single-player exposure K=30: DEMAX 0.49, LEARNED_DIV5 0.47, LEARNED_DIV5_EXP50 0.43
max single-player exposure K=80: DEMAX 0.46, LEARNED_DIV5 0.43, LEARNED_DIV5_EXP50 0.41
mean pairwise overlap K=30: DEMAX 0.98, LEARNED_POOL 1.54, LEARNED_DIV5 1.22, BLEND_DIV5 1.24
mean pairwise overlap K=80: DEMAX 0.95, LEARNED_POOL 1.26, LEARNED_DIV5 0.98, BLEND_DIV5 1.00

pool oracle mean 185.41; pool 200+ lineups per slate-arm 0.33; in DEMAX-80 0.21
K=30 DEMAX: slate-arms with max>=200: 6, >=194: 7
K=30 LEARNED_POOL: slate-arms with max>=200: 12, >=194: 19
K=30 LEARNED_DIV5: slate-arms with max>=200: 12, >=194: 19
K=30 LEARNED_DIV5_EXP40: slate-arms with max>=200: 12, >=194: 19
K=30 LEARNED_DIV5_EXP50: slate-arms with max>=200: 12, >=194: 19
K=30 LEARNED_DIV5_EXP60: slate-arms with max>=200: 12, >=194: 19
K=30 BLEND_Q99: slate-arms with max>=200: 9, >=194: 13
K=30 BLEND_DIV5: slate-arms with max>=200: 9, >=194: 14
K=30 BLEND_DIV5_EXP40: slate-arms with max>=200: 8, >=194: 13
K=30 BLEND_DIV5_EXP50: slate-arms with max>=200: 9, >=194: 14
K=30 BLEND_DIV5_EXP60: slate-arms with max>=200: 9, >=194: 14
K=30 UNION: slate-arms with max>=200: 8, >=194: 13
K=30 RESORT: slate-arms with max>=200: 9, >=194: 11
K=30 Q99: slate-arms with max>=200: 6, >=194: 8
K=80 DEMAX: slate-arms with max>=200: 13, >=194: 16
K=80 LEARNED_POOL: slate-arms with max>=200: 14, >=194: 24
K=80 LEARNED_DIV5: slate-arms with max>=200: 15, >=194: 24
K=80 LEARNED_DIV5_EXP40: slate-arms with max>=200: 15, >=194: 24
K=80 LEARNED_DIV5_EXP50: slate-arms with max>=200: 15, >=194: 24
K=80 LEARNED_DIV5_EXP60: slate-arms with max>=200: 15, >=194: 24
K=80 BLEND_Q99: slate-arms with max>=200: 12, >=194: 21
K=80 BLEND_DIV5: slate-arms with max>=200: 13, >=194: 22
K=80 BLEND_DIV5_EXP40: slate-arms with max>=200: 12, >=194: 22
K=80 BLEND_DIV5_EXP50: slate-arms with max>=200: 12, >=194: 22
K=80 BLEND_DIV5_EXP60: slate-arms with max>=200: 12, >=194: 22
K=80 UNION: slate-arms with max>=200: 13, >=194: 21
K=80 RESORT: slate-arms with max>=200: 13, >=194: 16
K=80 Q99: slate-arms with max>=200: 9, >=194: 13

Live (2026 W1 K90 run, 3200-candidate pool): unconstrained pool rules collapse onto one core (top-30 pairwise overlap 5.4 vs 1.5 here; one player in 97-100% of lineups). The adopted TODAY rule LEARNED_DIV5_EXP40 gives max exposure 40%, 90 distinct players, pairwise overlap 1.6 (paid book 1.3), mean simulated q99 180 vs the paid top-30 189 (the learned score deliberately trades simulator tail for market-backed floor; historically that trade paid +6.1 at K=30).
