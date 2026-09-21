# End-to-end audit: initial confirmed findings

This is the first pass of the requested full-system audit. It covers the path from raw weather ingestion through model feature construction and the Week-2 post-contest evidence. The remaining stages are being reviewed against the production and lab handoffs.

## Confirmed defect: precipitation is captured and discarded

`src/nfl_dfs/ingest/weather_job.py` requests `precipitation_probability` and writes `precip_prob` to `nfl_raw.weather`. The latest Week-2 MIN–CHI snapshot was 51% precipitation probability at 13:02 UTC, with earlier snapshots at 40% and 72%.

`sql/features/020_game_weather.sql` selects only temperature, wind, and dome status from that table. `021_player_week_training.sql`, `023_player_week_inference.sql`, and `models/featureset.py` likewise carry/use wind, temperature, and dome but no precipitation field. The released Week-2 player-signal table confirms that no precipitation value reached the model or selector.

Classification: **confirmed input-plumbing omission**, not yet a proven scoring improvement. Required repair/test: preserve the field through the feature tables, add a point-in-time historical forecast shadow, and only then consider retraining or a production feature adoption.

## Confirmed attribution correction: the pool inversion is component-specific

The released 12,555-candidate realized table was independently joined to the archived D12800 frame and both score banks. Correlations with realized points were incumbent -0.48794, corrected HSIM -0.08739, and equal-mass pooled -0.33201. The report's -0.49 headline therefore describes the incumbent component, not the combined selection score.

Classification: **analysis attribution error**, not a code defect. No model-weight change should be based on the aggregate headline.

## Audit controls now required for every remaining stage

- Every claimed bug must include serving commit/image, input hashes, a minimal reproducer, regression test, and fixed-path replay.
- A captured field must be traced through raw, normalized, feature, model, candidate, selector, vetter, upload, and settlement artifacts; presence in raw storage is not evidence of use.
- Historical shadows must use one fixed candidate pool, status snapshot, information cutoff, and contest map when comparing selection rules.
- Ownership and standings imports must preserve typed rejection reasons and raw hashes; tolerance changes require entry-count reconciliation.
- Exposure, market-pull, rain, season-window, and selector proposals remain shadows until a walk-forward or paired realized scorecard supports them.

The other agent owns the bulk inventory and repair queue. This branch contains the independent component analysis and the precipitation evidence; no production main or live book was changed.

