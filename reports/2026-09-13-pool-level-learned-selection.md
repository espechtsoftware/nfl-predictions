# Pool-level learned lineup score — historical test (2026-09-13, outcome-blind for 2026)

Training: 216 opened D800_DEMAX books (PREREG-094 banks 940-942, 2021-2024), ridge on within-book-standardised lineup features, held-out season never seen (LOSO). Test corpus: the Neo4j PREREG-083 candidate pools (2023-2024, 36 slates x 2 arms, 200 candidates per slate-arm, realized scores, DEMAX K80 book marked). Rule = which K of the 200 to enter; metric = realized max of the K. Script: scripts/week1_pool_level_test.py; features: scripts/week1_learned_order_live.py; live application: scripts/week1_learned_score_live.py.


### K=30  (72 slate-arms; realized max of the chosen K; delta vs DEMAX)
| rule | mean DEMAX | mean rule | delta | wins | losses | 2023 delta | 2024 delta | ctrl delta | trt delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LEARNED_POOL | 171.06 | 176.17 | +5.11 | 0.57 | 0.24 | +1.08 | +9.14 | +5.24 | +4.98 |
| LEARNED_DIV4 | 171.06 | 175.95 | +4.88 | 0.58 | 0.26 | +2.19 | +7.57 | +6.33 | +3.44 |
| LEARNED_DIV5 | 171.06 | 176.71 | +5.65 | 0.58 | 0.22 | +2.34 | +8.95 | +6.21 | +5.08 |
| LEARNED_DIV6 | 171.06 | 176.99 | +5.93 | 0.58 | 0.22 | +2.61 | +9.25 | +6.21 | +5.65 |
| BLEND_Q99 | 171.06 | 173.57 | +2.51 | 0.40 | 0.29 | +1.24 | +3.78 | +0.36 | +4.66 |
| BLEND_DIV4 | 171.06 | 173.76 | +2.69 | 0.50 | 0.22 | +0.49 | +4.90 | +2.00 | +3.39 |
| BLEND_DIV5 | 171.06 | 174.72 | +3.65 | 0.44 | 0.25 | +1.96 | +5.35 | +2.45 | +4.85 |
| BLEND_DIV6 | 171.06 | 175.00 | +3.93 | 0.46 | 0.24 | +1.78 | +6.08 | +2.31 | +5.56 |
| UNION | 171.06 | 174.15 | +3.08 | 0.38 | 0.19 | +1.61 | +4.56 | +2.27 | +3.90 |
| RESORT | 171.06 | 173.07 | +2.01 | 0.38 | 0.25 | -0.41 | +4.42 | +2.36 | +1.65 |
| Q99 | 171.06 | 169.72 | -1.35 | 0.21 | 0.26 | +0.05 | -2.74 | -3.81 | +1.12 |

mean overlap of LEARNED_POOL top-30 with the DEMAX top-30: 6.6

### K=80  (72 slate-arms; realized max of the chosen K; delta vs DEMAX)
| rule | mean DEMAX | mean rule | delta | wins | losses | 2023 delta | 2024 delta | ctrl delta | trt delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LEARNED_POOL | 179.86 | 181.17 | +1.31 | 0.36 | 0.25 | -0.06 | +2.68 | +1.65 | +0.98 |
| LEARNED_DIV4 | 179.86 | 181.78 | +1.92 | 0.42 | 0.19 | +1.21 | +2.64 | +3.42 | +0.42 |
| LEARNED_DIV5 | 179.86 | 182.52 | +2.66 | 0.39 | 0.17 | +1.61 | +3.71 | +2.48 | +2.85 |
| LEARNED_DIV6 | 179.86 | 182.52 | +2.66 | 0.39 | 0.18 | +1.38 | +3.94 | +2.48 | +2.84 |
| BLEND_Q99 | 179.86 | 181.85 | +2.00 | 0.31 | 0.11 | +1.89 | +2.11 | +2.89 | +1.10 |
| BLEND_DIV4 | 179.86 | 181.90 | +2.05 | 0.40 | 0.12 | +1.57 | +2.52 | +3.78 | +0.31 |
| BLEND_DIV5 | 179.86 | 182.57 | +2.72 | 0.35 | 0.10 | +3.12 | +2.32 | +3.96 | +1.47 |
| BLEND_DIV6 | 179.86 | 182.38 | +2.52 | 0.33 | 0.11 | +2.54 | +2.51 | +3.22 | +1.83 |
| UNION | 179.86 | 181.78 | +1.92 | 0.29 | 0.14 | +1.92 | +1.92 | +3.60 | +0.24 |
| RESORT | 179.86 | 179.86 | +0.00 | 0.00 | 0.00 | +0.00 | +0.00 | +0.00 | +0.00 |
| Q99 | 179.86 | 177.73 | -2.13 | 0.08 | 0.26 | -0.96 | -3.30 | -2.63 | -1.62 |

mean overlap of LEARNED_POOL top-80 with the DEMAX top-80: 35.9
mean pairwise overlap K=30: DEMAX 0.98, LEARNED_POOL 1.54, LEARNED_DIV5 1.22, BLEND_DIV5 1.24
mean pairwise overlap K=80: DEMAX 0.95, LEARNED_POOL 1.26, LEARNED_DIV5 0.98, BLEND_DIV5 1.00

pool oracle mean 185.41; pool 200+ lineups per slate-arm 0.33; in DEMAX-80 0.21
K=30 DEMAX: slate-arms with max>=200: 6, >=194: 7
K=30 LEARNED_POOL: slate-arms with max>=200: 12, >=194: 19
K=30 LEARNED_DIV4: slate-arms with max>=200: 10, >=194: 17
K=30 LEARNED_DIV5: slate-arms with max>=200: 12, >=194: 19
K=30 LEARNED_DIV6: slate-arms with max>=200: 12, >=194: 19
K=30 BLEND_Q99: slate-arms with max>=200: 9, >=194: 13
K=30 BLEND_DIV4: slate-arms with max>=200: 8, >=194: 12
K=30 BLEND_DIV5: slate-arms with max>=200: 9, >=194: 14
K=30 BLEND_DIV6: slate-arms with max>=200: 10, >=194: 15
K=30 UNION: slate-arms with max>=200: 8, >=194: 13
K=30 RESORT: slate-arms with max>=200: 9, >=194: 11
K=30 Q99: slate-arms with max>=200: 6, >=194: 8
K=80 DEMAX: slate-arms with max>=200: 13, >=194: 16
K=80 LEARNED_POOL: slate-arms with max>=200: 14, >=194: 24
K=80 LEARNED_DIV4: slate-arms with max>=200: 13, >=194: 22
K=80 LEARNED_DIV5: slate-arms with max>=200: 15, >=194: 24
K=80 LEARNED_DIV6: slate-arms with max>=200: 15, >=194: 24
K=80 BLEND_Q99: slate-arms with max>=200: 12, >=194: 21
K=80 BLEND_DIV4: slate-arms with max>=200: 13, >=194: 21
K=80 BLEND_DIV5: slate-arms with max>=200: 13, >=194: 22
K=80 BLEND_DIV6: slate-arms with max>=200: 12, >=194: 22
K=80 UNION: slate-arms with max>=200: 13, >=194: 21
K=80 RESORT: slate-arms with max>=200: 13, >=194: 16
K=80 Q99: slate-arms with max>=200: 9, >=194: 13

Live caveat (2026 W1 K90 run, 3200-candidate pool): the unconstrained pool rules are far more concentrated than anything in this corpus (top-30 mean pairwise overlap 5.4 vs 1.5 here; one player in 97-100% of lineups; 43 distinct players). The overlap-capped rules reduce pairwise overlap to 3.3 but not single-player exposure. Historical corpus pools were 40 lev + 160 boom; the live pool is 640 lev + 2560 boom.
