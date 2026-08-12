# Fantasy Points projected-ownership protocol

Status: prospective 2026 acquisition and field-model input; collector and
scoring branch still to be implemented. This protocol is frozen before the
2026 NFL ownership page becomes available and before any 2026 contest result
is known.

## Decision

Collect and use Fantasy Points' DraftKings projected ownership beginning with
the first 2026 main slate. The source is valuable for modeling the opposing
field, likely lineup duplication and payout leverage. It is **not** a player
scoring feature and must not be converted into a generic chalk-fade penalty.
The historical `milly_fade` arm answered that different question and was
rejected because it reduced the submitted portfolio's scoring tail.

Fantasy Points describes the ownership table as subscriber content with
player, position, team, salary and ownership fields. Its optimizer describes
the projected ownership as powered by FanShare. The standalone Data Suite
purchase may not include the required Premium entitlement, so access must be
confirmed when the 2026 page opens; no access control may be bypassed.

## Collection contract

Target only DraftKings NFL Classic Sunday Main. The collector must use the
normal authenticated website, establish the exact operator/style/slate
context, press Apply whenever the surface exposes that control, and verify the
rendered context before reading or exporting rows.

For every target week, capture four immutable snapshots:

1. first available after the weekly projections are posted;
2. Saturday at approximately 18:00 America/Chicago;
3. Sunday at approximately 10:10 America/Chicago, before the early book
   freezes; and
4. Sunday at approximately 11:00 America/Chicago, before the final book
   freezes.

If kickoff or the portfolio-freeze schedule changes, derive the final two
times as at least 20 minutes before their corresponding freeze rather than
silently using stale clock times. A failed or late capture remains missing; it
must never be relabeled as pre-lock.

Each snapshot must preserve the raw response/export in a create-only licensed
GCS archive and append normalized rows to
`nfl_raw.fantasy_points_ownership_snapshots`. Required metadata:

- capture ID and UTC retrieval timestamp;
- season, week and exact slate/draft-group identity;
- operator, contest style and slate label;
- source URL and raw SHA-256;
- vendor player name, position, team, salary and projected ownership;
- resolved DraftKings player ID and GSIS ID, with unresolved rows retained in
  the manifest rather than silently dropped; and
- target lock time plus a mechanically derived pre-lock flag.

The table name intentionally begins with `fantasy_points_`, so the existing
daily backup discovery includes it automatically. The ignored local licensed
archive and manifest conventions used by the current Fantasy Points
Playwright project still apply.

## Evaluation contract

After settlement, grade each snapshot against actual ownership from the exact
large-field Sunday-main contest imported from DraftKings. Report coverage,
MAE, RMSE, rank correlation, calibration by projected-ownership band and
position, and late-snapshot improvement over the first snapshot. Compare:

- the current walk-forward in-house ownership model;
- Fantasy Points alone; and
- a predeclared blend fit only on earlier completed 2026 slates.

Never train or choose a blend using the same slate being graded. Preserve the
prediction available at each portfolio freeze; a later vendor update cannot
replace it. Individual ownership marginals do not identify stack and
bring-back dependence, so historical field structure must still govern legal
opponent-lineup generation.

## Live use

The first implementation has three stages:

1. display Fantasy Points versus in-house ownership disagreements and retain
   both vectors with every frozen lineup book;
2. use the pre-lock vector as the marginal distribution for conditional,
   legal opponent-field simulation and projected duplicate counts; and
3. compare the incumbent exact-80 portfolio with a separately labeled
   payout-aware exact-80 portfolio using win/top-1% probability, expected
   duplicate-adjusted payout and realized ROI—not raw average lineup score.

For Week 1, Fantasy Points may be used immediately as a field-simulation
scenario because it is contemporaneous information unavailable to a purely
historical model. It must remain identifiable alongside the in-house scenario
so the project does not invent an unvalidated blend weight. A permanent
source/blend choice requires the prospective calibration evidence above.

Do not buy a duplicate projected-ownership product automatically. First
confirm the existing Fantasy Points entitlement and exportability. An ETR or
other feed is justified later only as an independently measured second source
or if Fantasy Points access is unavailable.

## Implementation queue

1. Extend the authenticated Playwright project with a dedicated ownership-page
   collector and fail-closed context/row validation.
2. Add append-only BigQuery import, identity audit, raw archive and tests.
3. Add the source to the in-app weekly guide and status/freshness checks.
4. Persist all ownership vectors and their capture IDs with frozen books.
5. Implement the field-simulation and payout-aware comparison without
   reviving the rejected ownership-fade scoring arm.
6. Validate the full path on the first real 2026 slate before DraftKings lock.

