# Usage-only sensitivity input identity

After workstation handoff `b72e465` reports the full isolated feature build and unchanged leakage checks passing, read only the six declared usage fields for2026Week2 from `nfl-predictions-503414.nfl_features_salaryfix.player_week_usage`. The ordered922-row receipt is [salaryfix usage input](reviews/evidence/2026-09-19-salaryfix-usage-input.json), SHA-256 **a021f3ae048033b02a974f616b5b9d68524fe731d9f3d89e35d5cb8670c90025**. The source table modified timestamp and etag were identical before/after export; full metadata/query is retained in the receipt. Job `ebc2906c-2dd2-46c0-ac24-d935fd6ab417`,6,880,940bytes.

This newer full-build usage table has922Week2rows, versus930in the earlier temporary preview that reused existing derived tables. Do not silently substitute their counts. The simulation joins exact GSIS identities, enumerates unmatched rows and leaves them unchanged as preregistered. No target-week actuals were selected. Source usage guards and unchanged-frame assertions must pass before simulation. This supplement pins the input before effects are read.

Run the usage-only script at `c6fb424f`, including its fixed-calibration audit amendment. All unmodified archived inputs and model identities remain those of the exact-replay preflight. No adoption or complete refreshed-projection claim is made.
