# Production `us_dfs` endpoint census for the lab

Date: 2026-09-03

Status: score-free, one-event/one-market feasibility observation; not a coverage conclusion or model input

Lab contract: `nfl2/docs/us-dfs-coverage-contract-v1.md`

## Result

Production verified the existing Odds API account without exposing its credential. The free `/sports` request
returned HTTP 200, reported NFL active, cost zero credits, and showed 99,781 credits remaining before the paid
census calls. The live NFL events endpoint returned 272 current/future events at zero cost.

Two deliberately bounded requests were then made for the earliest listed NFL event using:

```text
regions=us_dfs
markets=player_pass_yds
oddsFormat=american
includeMultipliers=true
```

Each event-market request cost one credit. The second, fixture-producing request ended with 99,779 credits
remaining. It returned HTTP 200 with:

- platforms `prizepicks` and `underdog`;
- one `player_pass_yds` market per platform;
- nine total outcomes covering two redacted players;
- outcome fields `description`, `multiplier`, `name`, `point`, and `price`;
- multipliers represented as `null` on PrizePicks and `1.0` on Underdog in this snapshot.

Dabble and DraftKings Pick6 were absent from this one event/market response. That is not evidence they are
globally unsupported: it must be classified as `market_absent` or platform state only after the planned
multi-event census and health checks.

## Parser implications visible in the first response

The parser must not assume symmetric Over/Under rows or a single line per player/platform. PrizePicks emitted an
additional one-sided `Over 0.5` row for a player alongside a normal 228.5 Over/Under pair. It must preserve the
raw line/side rows, classify incomplete pairs, and never collapse the stray row into the main line. It must also
distinguish a present-but-null multiplier from a missing multiplier key and retain platform/market `last_update`
as the quote-time source.

The redacted schema fixture is:

`reports/fixtures/2026-09-03-odds-us-dfs-player-pass-yds-redacted.json`

No API key, player name, team name, or provider event ID is present in the fixture. Production has not stored
these rows in a scoring table, changed any model, initiated a historical backfill, or interpreted displayed
multipliers as SGP probabilities.

## Next bounded step

The lab can implement and test `scripts/us_dfs_parse.py` against the fixture now. Production should next run a
score-free census over the current Week-1 event set and a small frozen market bundle, recording platform health,
listing breadth, quote age, pairing completeness, multiplier coverage, and exact quota cost. Do not start a
historical backfill until that census shows useful NFL coverage and the expected cost is frozen.
