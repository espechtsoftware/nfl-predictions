# R2(a): the crowd's recency-chasing, replicated on our own point-in-time data: R2 KILLED under its pre-declared criteria

**Laptop, 2026-09-24.** Plan `reports/2026-09-25-plan-from-outside-the-box-review.md` §1, R2(a), "the kill test for R2".
- **Script:** `reports/lab-handoffs/2026-09-25-r2a-recency-replication.py`. Its decision criteria were **committed before
  its first run** (`74ba70a7`), and it was run once.
- **Data:** the replay panel `slate_player_features` (`20260811-pitclean-e80-k1-a12ab31`) and the largest Sunday Millionaire
  in `contest_ownership`, over **72 slates (2022–2025)**: 12,081 skill rows with PP ≥ 4, of which 10,514 played.
  Our projection's r with actual is 0.525; LineStar's was 0.50–0.54.

## Verdict (criteria fixed in advance)
| criterion | primary (PP = `mean_projection`) | sensitivity (PP = `model_points_pre`) |
|---|---|---|
| (i) T4, the crowd chases: last week's surprise → excess actual ownership, needs ρ > 0 and t ≥ 3 | **+0.270, t 20.3, 67/67: PASS** | +0.278, t 20.2: PASS |
| (ii) T6a, the chased part carries no information: recency part of excess ownership → residual, needs \|t\| < 2 | **+0.027, t 2.0, 42/67: FAIL** | +0.037, t 2.8: FAIL |
| (iii) T6b, the rest is informative: needs ρ > 0 and t ≥ 3 | **+0.165, t 12.2, 61/67: PASS** | +0.186, t 13.6: PASS |
| **R2** | **KILLED** (by ii) | KILLED (by ii) |

**Also:**
- T1, excess actual ownership → residual: +0.159, t 12.9, 70/72. Quintiles −1.69, +0.13, +0.42, +0.91, +1.98 points.
- T5, last week's surprise → this week's residual, is identical to T6a by construction (the recency part is a linear
  function of the surprise within a slate).
- Per season, T6a (primary): 2022 +0.044 (t 1.9), 2023 +0.044 (1.4), 2024 +0.007 (0.5), 2025 +0.013 (0.4). T6b: +0.14 to
  +0.20 in every season.

## Against the review's LineStar numbers (§2.4)
| test | LineStar (review) | ours (primary) |
|---|---|---|
| T1 excess actual ownership → residual | +0.170 (t 17.0) | +0.159 (t 12.9) |
| T4 surprise → excess ownership | +0.226 (t 18.9) | +0.270 (t 20.3) |
| T6a recency part → residual | +0.015 (t 1.3) | **+0.027 (t 2.0)** |
| T6b rest → residual | +0.176 (t 15.4) | +0.165 (t 12.2) |

## Reading
- **What replicates, strongly:**
  - The crowd chases last week's surprise (T4, 67/67 slates).
  - The crowd's excess ownership as a whole is informative (T1, T6b), about +2 points per slate-quintile step at the top.
    The review's "don't fade total ownership" stands.
- **What does not:** "the chased part carries no information". Against **our** projections, last week's surprise predicts
  this week's residual weakly but detectably: ρ +0.03 to +0.04, t 2.0 (primary) and 2.8 (model-only). So it is at least
  partly information our projection under-uses, not pure behavioural error.
  - The effect sits mostly in 2022–23; 2024–25 are near zero. On LineStar's projections (the review) it was zero. Against a
    better projection, the chase could still be uninformative.
  - The criterion decides, not this reading.
- **Consequences under the plan:**
  - **R2(b), the recency-aware ownership predictor, is not built.** The plan gates it on R2(a) holding.
  - **PREREG-L07 loses its "recency-deflated LOW slots" and "recency-only fade" arms.** Its informed-chalk anchor is still
    supported by T6b.
  - The ownership model's own lag inputs (`own_prev` etc., used by L05) are unaffected; they predict **ownership**, not
    points.
- **Reopening:** only with a projection that absorbs last-week form. If T5 is then ~0 for **our** projection, the recency
  split becomes clean and R2 can be re-tested with a new pre-declared criterion. Never by re-running this script with a
  different threshold.
