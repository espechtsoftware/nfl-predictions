# SIS NFL subscription inventory and acquisition priority

Audited 2026-08-13 through the authenticated SIS DataHub Pro NFL user
interface after the NFL-only subscription was activated. This inventory does
not commit licensed vendor rows. Raw files, cookies and storage state remain
outside Git.

## What the subscription exposes

Both Player and Team Leaderboards support seasons 2015--2025, week ranges,
Split by Game, offense/opponent team filters, conference/division,
home/away, indoor/outdoor, field position, quarter/down/distance/score/time,
offensive personnel and formation. The normal paid UI returns up to 200 rows;
one default passing query returned 95 rows, confirming the account is no
longer under the 20-row trial cap. An exact 200-row Week 1 pass-defense result
proved the paid cap is still binding and must be split rather than treated as
complete.

The guarded exporter then passed a real end-to-end smoke for 2025 Week 1,
player pass-defense Value, SIS team ID 1: 11 API rows and 11 CSV rows, exact
season/week/team scope, API `Games=1`, visible table/download parity and a
hash manifest. Rates/Value CSVs omit their visible `Games` column, so the
exporter requires `Games=1` from the exact API response and independently
requires Week/Opponent in the downloaded CSV. The licensed smoke files remain
under gitignored `sis/smoke-v4/`.

The rendered table contains stable SIS player and team IDs in its detail
links, and the normal UI response contains numeric `playerId`/`teamId`. The
CSV display export omits those identifiers, so acquisition should retain a
secret-free identity sidecar/manifest derived from the same rendered query.

### Player and team report families

- Passing: totals, rates and value. Value adds Points Earned, PE/play,
  Points Above Average, EPA, Positive%, PAR, WAR, Boom% and Bust%. Situation
  filters include pressure, pocket, play action, RPO, motion, target in motion,
  depth, direction, coverage shell, route, target alignment and position.
- Rushing: totals, rates and value. Distinct fields include yards after
  contact, broken/missed tackles, hit-at-line, stuff rate, designed gap,
  Points Earned/PAA/EPA/PAR/WAR and boom/bust. Filters include run concept,
  blocking scheme, box count, motion, lead blocker and designed-gap success.
- Receiving: totals, rates and value. Distinct fields include routes, target
  quality, air yards, YAC/contact, DPI, yards/route, ADoT/ADoC, receiver
  rating, Points Earned/PAA/EPA/PAR/WAR and boom/bust. Filters cover receiver
  alignment, coverage shell, route, motion, QB pressure and end-zone targets.
- Pass defense: totals, rates and value. Distinct fields include coverage
  snaps, primary-defender targets, catchable/completions allowed, intended air
  yards, deserved catch rate, rating against, yards/coverage snap, Points
  Saved/PAA/EPA/PAR/WAR and boom/bust. Filters cover coverage shell, defender
  and receiver alignment/position, route, direction, rushers, pressure, play
  action and motion.
- Pass rush: totals, rates and value. It separates pass snaps/rushes, sacks,
  unblocked sacks, hurries, hits, knockdowns and pressures, plus Points Saved,
  PAA, PAR and WAR. Filters include coverage shell, technique, rushers, drop
  type, side of center, play action and motion.
- Run defense: totals, rates and value. It contains run/rush snaps, tackle
  depth, TFL/stuffs, broken/missed tackles and Points Saved/PAA/PAR/WAR, with
  concept, gap, blocking scheme, box count, technique and motion filters.
- Blocking: overall totals/rates/value plus Runs to Gap and Adjusted Blown
  Blocks. It separates pass/run snaps, blown blocks, holds, Points Earned/PAA,
  PAR/WAR and run direction/scheme/alignment. This is potentially valuable
  OL context not duplicated by the previously downloaded player-usage files.
- Returning, punting and kicking are also available. They are retained in the
  catalog but ranked lower for the initial DFS feature program.

## Acquisition priorities

1. Pull team passing, receiving, pass defense, pass rush and blocking Value
   views plus the Totals denominators at game grain. These are the strongest
   new offense/defense/line context candidates and are only 32 team-games per
   week, safely below the cap.
2. Pull player passing, receiving and pass-defense Value plus Totals at game
   grain, split by SIS team ID whenever the unsliced query reaches 200.
3. Pull team/player rushing and run defense after the pass-game bundle.
4. Preserve special teams as a later diagnostic, not an initial broad
   backfill.

For the historical DFS panel, acquire only seasons actually used by the
accepted replay path (2019, 2021--2025) before expanding further. Prefer one
team-season Split-by-Game query when it stays below 200; otherwise narrow by
week. Every manifest must record the exact filter scope, schema, hash, row
count, retrieval time and stable identity mapping. This keeps the pull under
the documented 1,000-query weekly allowance and provides explicit
completeness evidence.

The paid-surface automation audit confirmed that Runs to Gap is metric group
15 and Adjusted Blown Blocks is group 17. Runs to Gap exposes designed-run
share, same-side share, bounces/bounce rate, yards before contact, EPA and
per-carry fields. Adjusted Blown Blocks separates pass/run plays, raw blown
blocks, adjusted blown blocks and position. These are now explicit catalog
entries, but they remain priority 2: the first tranche should establish
whether broad team blocking and pass-game context add signal before spending
more requests on granular gap or individual-lineman features.

## Modeling order

Do not add every column to TabPFN at once. First create lagged, shrinkage-aware
team/player summaries using only completed games before the target-week lock.
Evaluate correlation and incremental walk-forward calibration by position,
then preregister small bundles: QB pressure/coverage context; WR route,
alignment and opponent pass-defense context; RB line/run-front context; and
DST opponent pressure/blocking context. Only score-free feature/calibration
passes should proceed to an exact-80 lineup comparison. Same-week rows are
outcomes and are forbidden as predictors.
