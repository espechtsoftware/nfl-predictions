# Predeclared paid-source role and coverage feature gate

**Frozen before execution:** 2026-09-20  
**Population:** active WR/TE player-weeks, seasons 2022--2025, target Weeks 5--18, from the existing `player_week_training` table. Sources are strictly prior-window tables joined on `(season, target_week, gsis_id)` or opponent team.

## Arms

- **Control:** fixed baseline player forecast features plus the already operating Fantasy Points weekly route-share fields (`fp_route_share_last`, `fp_route_share_l4`, `fp_route_share_jump`).
- **FP role arm:** control plus position/route interactions (`route_share × TE`, `route_share × target_share_l4`), prior-window alignment shares (wide, slot, inline, backfield), and route-shape shares (horizontal, vertical, static, shallow, backfield). Missing values remain missing until fold-fitted median imputation; no outcome-derived thresholds are used.
- **FP coverage arm:** control plus the four registered same-season FP coverage edges (Man/Zone TPRR, YPRR, FP/RR and shell separation), the support indicator, and route share × coverage interactions. The arm is reported even if its existing mechanism has a prior failed gate; this is a distinct combined role/coverage consumer and is not used to retune the old mechanism.
- **SIS coverage arm:** control plus SIS prior eight-game defender coverage rates by opponent and alignment (wide/slot target rate, yards per coverage snap, vulnerability), the receiver's prior alignment shares, and the predeclared alignment-exposure interaction `wide_share × (wide_target_rate - slot_target_rate)`. SIS features are only populated when the source context is supported.
- **Combined arm:** FP role + FP coverage + SIS coverage, with no coefficients selected from outcomes.

## Fixed evaluation

For each test season (2024 and 2025), train on all earlier seasons and evaluate once on the held-out season. Use a ridge residual model (`alpha=10`) for DK points and logistic regression (`C=0.1`, lbfgs, max_iter=2000) for 20+ and 30+ outcomes. Standardization and median imputation are fitted on the training fold only. Position is one-hot encoded. No feature selection, threshold, fold, or arm is changed after results.

Report aggregate and season-fold MAE, Brier-20, Brier-30, support/row counts, feature missingness, residual correlations, and changes in the 30+ event rate by route-share and position bands. This is a forecast gate only; it does not authorize lineup generation or production changes.
