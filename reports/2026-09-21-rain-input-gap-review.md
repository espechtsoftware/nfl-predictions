# Rain input gap: captured by ingestion, absent from projections

## Finding

The weather ingest requests and stores `precipitation_probability` as `precip_prob` in `nfl_raw.weather`. The Week-2 Chicago row was present in BigQuery before lock:

| snapshot (UTC) | game | temperature | wind | precipitation probability | dome |
|---|---|---:|---:|---:|---|
| 2026-09-20 13:02 | MIN–CHI | 65.8 F | 14.1 mph | 51% | false |

Earlier snapshots were 40% and 72%. Thus the system had a material rain signal available before the build.

The signal is then dropped. `sql/features/020_game_weather.sql` aggregates only `temp_f`, `wind_mph`, and `is_dome`; `sql/features/021_player_week_training.sql` and `sql/features/023_player_week_inference.sql` join those same three columns; and `src/nfl_dfs/models/featureset.py` includes `is_dome` but neither precipitation probability nor a rain indicator. The Week-2 released player-signal table consequently contains wind and temperature but no precipitation field.

## Interpretation

Rain was not considered by the current player projections or selector. The post-mortem’s attribution of MIN–CHI to wind is incomplete: the game also carried a 51% pre-lock precipitation probability, with prior forecasts as high as 72%. This does not prove rain caused the scoring miss, and a forecast probability is not observed rainfall, but it is a confirmed unused input that should be tested.

## Required experiment

Add a score-free, point-in-time weather shadow with: precipitation probability, binary rain threshold(s), wind × precipitation interaction, temperature × precipitation, and dome gating. Use the exact historical forecast snapshots available at each build cutoff, not current retrospective weather. Compare against the current weather control in walk-forward seasons and report player points MAE, 20+/30+ Brier scores, game/player residuals, and lineup K20/K80 maxima. Do not add the feature to production until the shadow has support, leakage checks, and an independent replay.

The immediate operational repair is to preserve `precip_prob` through `game_weather` and inference artifacts so the shadow can be run. This is plumbing work; it is separate from deciding whether rain improves forecasts.

