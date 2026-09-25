# Integrity checks §5.2 (DST coefficient) and §5.3 (anytime-TD side): laptop, 2026-09-24

Answering the plan `reports/2026-09-25-plan-from-outside-the-box-review.md` §0 (items 5.2 and 5.3, due Mon 09-28).
Read-only; no outcome of any running panel was touched.

## 5.3 — anytime-TD feed: only the "Yes" side exists today; unguarded for more books
- **Code:** `models/prop_market.py:284-289` prices every `player_anytime_td` row as a "Yes" price
  (`6 × −ln(1 − p/1.15)`), with **no filter on `outcome_name`**. `ingest/oddsapi_import.py:117` stores whatever outcomes the
  API returns.
- **Data** (`nfl_raw.prop_lines`, `market='player_anytime_td'`): every row in 2023–2026 is `outcome_name = 'Yes'`.
  - Rows: 14,248 / 15,665 / 18,138 / 15,817.
  - Two books: DraftKings and FanDuel.
- **Verdict: not a defect today; a latent one.** A book that quotes the "No" side would be averaged in as if it were a
  "Yes" price, and a No at p ≈ 0.7 prices as ~7 TD points. **R4(a) (8–10 books) is exactly the change that could introduce
  such a book.**
- **Fix, before R4(a) goes live (small, default-safe):** filter `outcome_name = 'Yes'` in the TD branch, and fail closed on
  any other value (a test with a synthetic "No" row).

## 5.2 — the DST `COEF_L16` is applied to a last-4 average: confirmed, small, a Week-4 fix
- **Code:** `inference/dst_projections.py:30-35` sets `COEF_L16 = 0.118` ("Vegas-first model, fit 2026-07-26 on 6,126
  DST-weeks"). `:157-165` computes the trailing input as the **last-4** mean of `team_defense_week.dst_dk_points`; the replay
  path uses `shift(1).rolling(4)` as well.
  - The fit script was never committed. `4507d743` added the coefficients only, so what 0.118 was fitted on cannot be
    confirmed from the repository.
- **Refit here, the same design** (intercept + opponent implied total + trailing; fit ≤ 2020, evaluate 2021 + 2025;
  5,785 DST-weeks with lines; without the QB-experience terms):

| trailing input | trailing coefficient | opp-implied coefficient | OOS r |
|---|---:|---:|---:|
| last-4 mean (`dst_points_l4`, sd 3.73) | **0.016** | −0.444 | 0.295 |
| last-16 mean (`dst_points_l16`, sd 2.15) | **0.068** | −0.436 | 0.298 |
| live: 0.118 × last-4 (plus the live intercept and implied) | — | — | **0.284** |
| live coefficients × last-16 | — | — | 0.299 |

- **Reading:**
  - A 4-game average carries almost no signal once the implied total is in (0.016). A 16-game average carries some (0.068).
  - 0.118 is closer to an L16-type coefficient, and applying it to the noisier L4 over-weights noise.
  - Out of sample, live loses a little (r 0.284 vs 0.299 with L16 as the input).
  - The size is small: 0.118 × (L4 − L16) has an sd of **0.31 points** per DST projection.
- **Suggested fix (Week 4, player-level validation first; money path, so the operator decides):** feed `dst_points_l16` to
  the Vegas-first model (the feature exists), or refit the trailing coefficient on L4. Then record the refit script in the
  repository. Check it on history by DST MAE/CRPS before any live change.

## Reproduction
`reports/lab-handoffs/2026-09-25-dst-coef-and-td-side-check.py` reproduces both tables. It reads `nfl_raw.prop_lines`,
`nfl_features.team_defense_week` and `nfl_raw.schedules` only.
