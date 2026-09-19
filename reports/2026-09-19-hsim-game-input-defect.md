# Live hsim consumes frozen game lines instead of its current frame

September19,2026. Confirmed mechanically on the archived Thursday Week2 run. `hsim.world._games` obtains `raw_schedules` from the lab benchmark loader. `scripts/live_week.py` supplies the live frame but does not override that schedule lookup. The frame contains current totals/spreads from production; the hsim game law consumes the benchmark's older values. The exact-bank replay at `bd98a27e` establishes that this path reproduces the archived scores, rather than merely being an unused helper.

The immutable benchmark schedule file is generation1787873748625341, SHA-256 `d80725d03695a33c5f67bf655fc059b09109b201fb79c76bb0d8562b1e9da1ad`; its identity matches the benchmark manifest. Among the archived live frame's26 teams/13games,10games differ in total and10games differ in spread. Sign conventions were normalized consistently: positive home spread means home favored.

| Game | Archived live-frame total | Benchmark total | Live home spread | Benchmark home spread |
|---|---:|---:|---:|---:|
| MIN at CHI |48.5|45.5|4.5|3.5|
| PHI at TEN |39.5|42.5|-7.0|-4.5|
| SEA at ARI |41.5|44.5|-3.5|-10.0|
| CAR at ATL |43.5|43.5|-2.5|1.5|

The paid Odds-source question therefore has another concrete integration issue: newer game information present in the live frame is bypassed by one selector component. This does not yet identify which vendor produced each field or establish that a subscription improves realized performance. Calibration to the same player mean targets does not make differing game environments equivalent; it can change joint tails, opportunity allocation and selection.

[Full census](reviews/evidence/2026-09-19-hsim-schedule-input-census.json) and its [reproduction](reviews/evidence/2026-09-19-hsim-schedule-input-census.py) use input columns only, no current scores. The comparison is against the archived pre-lock frame, not a claim about today's latest lines.

Next: measure a schedule-only sensitivity with frame/means/usage/pool fixed, then review a narrowly explicit live schedule override whose default preserves every historical benchmark caller. Keep this separate from the salary-week repair. No production/lab live source, entries or schedules were changed by this finding.
